"""A hook asked as a job lets go of its call once it has run (0.31.0): the job is kept for its panel, and its call
holds the hook's arguments, a sudo password typed into the form among them. Nothing of them may stay reachable from
the job afterwards, however it ended (it answered, it failed, it refused before its first line, it was cancelled),
while what the panel reads (its answer, its lines, whether it was a hook) stays as it was. Asked of a Setup itself and
through the platform's own route (POST api/machines/NAME/job), the app asked directly: nothing is served, no port is
opened, no process is started (conftest's no_outside fails a test that does)."""
from __future__ import annotations

import gc
import threading
import time
import weakref

import pytest

from liminal_libs.apps import Refused
from liminal_libs.machines import MachinePlugin

from liminal_platform.app import PlatformApp, Setup

pytestmark = pytest.mark.usefixtures("no_outside")


class Box:
    name = "box"
    CANCEL_HOOKS = ()

    def ask(self, hook, *args, log=None):
        log("done")
        return {"said": "installed", "ok": True}


def a_call(box):
    """The call the platform makes for a form asked as a job: it holds the form's arguments."""
    args = ["nftables", "Sesame-standin-not-a-password"]

    def call(log):
        return box.ask("install_nftables", *args, log=log)
    return call


def test_a_finished_job_keeps_no_argument_it_was_given():
    box = Box()
    call = a_call(box)
    held = weakref.ref(call)  # the call, and through it the arguments: gone once nothing keeps it
    job = Setup(box, None, "install_nftables", call=call)
    del call
    job.thread.start()
    job.thread.join(5)
    gc.collect()
    assert not job.running and job.call is None and job.hooked is True
    assert held() is None  # the job kept for its panel no longer holds the call or its arguments
    told = job.describe()
    assert told["hook"] is True and told["answer"] == {"said": "installed", "ok": True} and told["lines"] == ["done"]
    assert "Sesame" not in repr(told)


def test_a_job_still_says_it_was_a_hook_and_whether_it_cancels():
    box = Box()
    job = Setup(box, None, "install_nftables", call=lambda log: box.ask("install_nftables", log=log))
    job.thread.start()
    job.thread.join(5)
    assert job.cancels is False and job.describe()["hook"] is True  # (not a hook the plugin names as cancellable)
    plain = Setup(box, ["update"], "update")
    assert plain.hooked is False and "hook" not in plain.describe()


class Secret(dict):
    """A form's password as its hook is given it, in a type a weak reference can follow (a str cannot be), so that
    nothing keeping it is seen, not guessed."""


class Risky(ValueError):
    """A refusal naming the argument that accepts it: the page's second confirmation."""

    accept = "accept_risk"


class Rights(MachinePlugin):
    """A stand-in whose forms carry a password, each hook asked as a job: one answers, one fails, one refuses before
    its first line, one runs until it is asked to stop."""

    name, title, about, api, order = "rights", "Rights", "a stand-in with a password in its forms", "2.2", 918
    HOOKS = (*MachinePlugin.HOOKS, "fine", "fails", "refuses", "slow")
    JOB_HOOKS = ("fine", "fails", "refuses", "slow")
    CANCEL_HOOKS = ("slow",)

    def __init__(self):
        self.began = threading.Event()

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def fine(self, password, log=None):
        log("working")
        return {"said": "done", "ok": True}

    def fails(self, password, log=None):
        log("working")
        raise RuntimeError("it broke")

    def refuses(self, password, accept_risk=False, log=None):
        raise Risky("it is risky: accept it first")

    def slow(self, password, log=None):
        log("downloading")
        self.began.set()
        for _ in range(2000):
            if getattr(log, "cancelled", False):
                return {"said": "cancelled", "ok": False}
            time.sleep(0.005)
        return {"said": "nobody stopped it", "ok": False}


@pytest.mark.usefixtures("an_output_that_takes_a_cancel")  # a library before 1.62.0: its output in 1.62.0's shape
@pytest.mark.parametrize("hook, answered", [("fine", 202), ("fails", 202), ("refuses", 400), ("slow", 202)])
def test_the_platforms_job_route_lets_go_of_a_password_however_its_job_ends(hook, answered):
    plugin = Rights()
    app = PlatformApp(log=lambda m: None, machines={"rights": plugin}, assistants={})
    secret = Secret(password="Sesame-standin-not-a-password")
    held = weakref.ref(secret)
    body = {"action": "hook", "hook": hook, "args": [secret]}
    del secret
    try:
        try:
            status = app.api(None, "POST", "/api/machines/rights/job", {}, body)[0]
        except Refused as e:
            status = e.status
        del body
        if hook == "slow":
            assert plugin.began.wait(5)
            assert app.api(None, "POST", "/api/machines/rights/job/cancel", {}, {})[0] == 202
        job = app._setups.get("rights")  # kept for its panel; one refused before its first line is forgotten
        if job is not None:
            job.thread.join(10)
        gc.collect()
        assert status == answered and (job is None) == (hook == "refuses")
        assert job is None or (not job.running and job.call is None and "Sesame" not in repr(job.describe()))
        assert held() is None, [type(r).__name__ for r in gc.get_referrers(held())]  # nothing the platform keeps
    finally:
        app.stop()
