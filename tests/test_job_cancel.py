"""0.31.0 (the six AI plugins, 2026-11-16: a model's download runs for a long time, and until now a job ran to its end
whatever the page did): a plugin's job under way can be asked to stop, POST api/machines/NAME/job/cancel. Only one of
its hooks run as a job, and only a hook the plugin names in its CANCEL_HOOKS (liminal-libs 1.62.0's AiPlugin: its
install; a model server's download of a model). Nothing is ended from outside: the job's output is told
(Output.cancel), the hook looks at it between its steps (`log.cancelled`) and ends by itself. The job says `cancels`
(the page offers Cancel while it runs), `cancelling` (it was asked) and `cancelled` (it had been asked when its work
ended, and it has ended). A setup, a packages' update and any other hook run to their end, and so does every job with a
liminal-libs before 1.62.0, whose output takes no cancel: the refusal says so (the platform's floor stays 1.54.0). A
cancel that comes as the work ends, or one meant for a job that has ended (its `startedAt`), is refused (409): the job
is said as it ended, and the next job is never stopped by a page not told yet. A cancel is no failure in who talks to
whom.

A stand-in plugin asked of the app itself: nothing is served, no port is opened, no process is started (conftest's
no_outside fails a test that does). Run on a liminal-libs before 1.62.0, the tests give the platform a job's output in
1.62.0's shape (conftest's `Cancellable`), so what the platform does with one is tested on every library it runs on."""
from __future__ import annotations

import json
import threading
import time

import pytest

from liminal_libs.machines import MachinePlugin
from liminal_libs.machines.terminal import Output

from conftest import api_answer as _api

import liminal_platform.app as app_module
from liminal_platform.app import PlatformApp, Setup, cancel_hooks

pytestmark = pytest.mark.usefixtures("no_outside", "an_output_that_takes_a_cancel")

NO_JOB = {"machine": "fetcher", "running": False, "lines": [], "done": None, "text": "", "from": 0, "offset": 0}


class Fetcher(MachinePlugin):
    """A stand-in whose download is a job that looks at its log's cancel flag between its steps, and whose build and
    setup run to their end. Each waits until the test lets it go (or, the download, until it is asked to stop)."""

    name, title, about, api, order = "fetcher", "Fetcher", "a stand-in whose download can be cancelled", "2.2", 912
    HOOKS = (*MachinePlugin.HOOKS, "fetch", "build")
    JOB_HOOKS = ("fetch", "build")
    CANCEL_HOOKS = ("fetch",)

    def __init__(self):
        self.began, self.go = threading.Event(), threading.Event()
        self.seen, self.end = threading.Event(), threading.Event()  # a cancel seen; its end let go (held by a test)
        self.end.set()
        self.saw: list[bool] = []  # what each download saw of the flag when it stopped waiting

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "here", "why": ""}

    def _held(self, log) -> bool:
        """Until the test lets it go (False) or its log is asked to cancel (True), looked at every few milliseconds as
        a download looks between two reads; 20 s at the most, so no test hangs on it."""
        self.began.set()
        for _ in range(2000):
            if getattr(log, "cancelled", False):
                return True
            if self.go.wait(0.01):
                return False
        raise AssertionError("the test neither cancelled the job nor let it go")

    def fetch(self, what, log=None):
        log(f"downloading {what}")
        cancelled = self._held(log)
        self.saw.append(cancelled)
        if not cancelled:
            return {"said": f"{what} is here", "ok": True}
        self.seen.set()
        assert self.end.wait(20), "the test never let the cancelled job end"
        log("cancelled: what was downloaded is kept")
        return {"said": f"cancelled: nothing of {what} was installed (what was downloaded is kept for the next try)",
                "ok": False}

    def build(self, log=None):
        log("building")
        self._held(log)
        return {"said": "built", "ok": True}

    def setup(self, log=print, steps=None):
        log("fetcher: setting up")
        self._held(log)
        return [{"step": "all", "ok": True, "detail": "done"}]


class OldOutput:
    """A job's output as liminal-libs before 1.62.0 has it: its text, read from an offset; no cancel and no flag."""

    def __init__(self):
        self._text = Output()

    def write(self, text):
        self._text.write(text)

    def __call__(self, line):
        self._text(line)

    def finish(self):
        self._text.finish()

    def wait(self, since, timeout):
        return self._text.wait(since, timeout)

    def read(self, since=0):
        return self._text.read(since)

    @property
    def finished(self):
        return self._text.finished

    @property
    def end(self):
        return self._text.end

    @property
    def text(self):
        return self._text.text


def _job(app, hook, *args):
    return _api(app, "POST", "/api/machines/fetcher/job", {"action": "hook", "hook": hook, "args": list(args)})


def _cancel(app, name="fetcher", body=None):
    return _api(app, "POST", f"/api/machines/{name}/job/cancel", body)


def _now(app) -> dict:
    return _api(app, "GET", "/api/machines/fetcher/job", query={"since": "0"})[1]


def _ended(app) -> dict:
    for _ in range(1000):
        got = _now(app)
        if not got["running"]:
            return got
        time.sleep(0.01)
    raise AssertionError("the job did not end")


def _three(job: dict) -> tuple:
    return job["cancels"], job["cancelling"], job["cancelled"]


def _made(**given):
    p, lines = Fetcher(), []
    return PlatformApp(log=lines.append, machines={"fetcher": p}, assistants={}, **given), p, lines


def test_a_job_the_plugin_names_is_asked_to_stop_sees_it_and_ends_by_itself():
    app, p, lines = _made()
    p.end.clear()  # its end held, so what the page is told while it is being cancelled can be read
    try:
        status, job = _job(app, "fetch", "a model")
        assert status == 202 and job["running"] is True and _three(job) == (True, False, False)  # Cancel is offered
        assert p.began.wait(5)
        status, asked = _cancel(app)
        assert status == 202 and (asked["machine"], asked["action"], asked["running"]) == ("fetcher", "fetch", True)
        assert _three(asked) == (True, True, False)  # asked to stop, not ended yet: "cancelling"
        assert p.seen.wait(5) and p.saw == [True]  # the hook saw the flag between two steps
        assert _cancel(app)[0] == 202 and _three(_now(app)) == (True, True, False)  # asked again: nothing changes
        p.end.set()
        done = _ended(app)
        assert _three(done) == (True, True, True) and done["ok"] is False and done["error"] is None  # stopped: no fault
        said = "cancelled: nothing of a model was installed (what was downloaded is kept for the next try)"
        assert done["answer"] == {"said": said, "ok": False}
        assert done["done"] == [{"step": "fetch", "ok": False, "said": said}]
        assert done["text"] == "downloading a model\ncancelled: what was downloaded is kept\n"
        assert lines.count("platform: fetcher asked to cancel fetch") == 2  # each ask, by the job's name alone
        assert _cancel(app) == (409, {"error": "fetcher runs no job now"})  # ended: nothing left to cancel
        assert _three(app.machine_status(p)["setup"]) == (True, True, True)  # the status shows it as it ended
        # who talks to whom: asked to stop, then its end said as a cancel, not as a failure
        changes = [r["what"] for r in app.traffic.recent()
                   if (r["from"], r["to"], r["kind"]) == ("platform", "fetcher", "change")]
        assert changes == ["fetch ended: cancelled", "fetch asked to stop", "fetch started"]  # the newest first
        # a cancel is no failure: Connections draws the link without "(1 failed)"
        assert all(r["ok"] and not r["failed"] for r in app.traffic.recent() if r["to"] == "fetcher")
        link = [k for k in app.traffic.links() if (k["from"], k["to"], k["kind"]) == ("platform", "fetcher", "change")]
        assert [(k["count"], k["failed"]) for k in link] == [(4, 0)]  # started, asked to stop twice, ended
        # the next job starts with a flag of its own
        p.began.clear()
        status, job = _job(app, "fetch", "another")
        assert status == 202 and _three(job) == (True, False, False) and p.began.wait(5)
        p.go.set()
        again = _ended(app)
        assert again["ok"] is True and _three(again) == (True, False, False) and p.saw == [True, False]
    finally:
        p.go.set()
        p.end.set()
        app.stop()


def test_with_no_job_running_there_is_nothing_to_cancel():
    app, p, lines = _made()
    assert _cancel(app) == (409, {"error": "fetcher runs no job now"})
    assert _cancel(app, "nothing") == (404, {"error": "no machine plugin named 'nothing'"})
    assert _api(app, "GET", "/api/machines/fetcher/job/cancel")[0] == 404  # asked for by a POST alone
    assert app.classify("POST", "/api/machines/fetcher/job/cancel") == "change"  # in who talks to whom: no stream
    assert _now(app) == NO_JOB and lines == []  # no job to follow, as before; nothing logged


def test_a_job_the_plugin_does_not_name_runs_to_its_end():
    app, p, lines = _made()
    try:
        status, job = _job(app, "build")
        assert status == 202 and _three(job) == (False, False, False) and p.began.wait(5)  # no Cancel offered
        assert _cancel(app) == (400, {"error": "fetcher's build cannot be cancelled: it runs to its end"})
        still = _now(app)
        assert still["running"] is True and _three(still) == (False, False, False)
        p.go.set()
        done = _ended(app)
        assert done["ok"] is True and done["answer"] == {"said": "built", "ok": True}
        assert _three(done) == (False, False, False)
        # its setup, which is no hook's job: not even when the plugin names it
        p.began.clear()
        p.go.clear()
        p.CANCEL_HOOKS = ("fetch", "setup")
        status, job = _api(app, "POST", "/api/machines/fetcher/setup", {})
        assert status == 202 and _three(job) == (False, False, False) and p.began.wait(5)
        assert _cancel(app) == (400, {"error": "fetcher's setup cannot be cancelled: it runs to its end"})
        p.go.set()
        done = _ended(app)
        assert done["ok"] is True and _three(done) == (False, False, False)
        assert not any("asked to cancel" in x for x in lines)
        ends = [r["what"] for r in app.traffic.recent() if r["to"] == "fetcher" and "ended" in r["what"]]
        assert ends == ["setup ended", "build ended"]
    finally:
        p.go.set()
        app.stop()


def test_a_failure_is_still_said_as_a_failure():
    app, p, lines = _made()
    try:
        assert _job(app, "fetch")[0] == 202  # an argument short: the hook's own TypeError ends the job
        failed = _ended(app)
        assert failed["ok"] is False and failed["error"].startswith("TypeError: ")
        assert _three(failed) == (True, False, False)  # nobody asked it to stop
        assert [r["what"] for r in app.traffic.recent() if "ended" in r["what"]] == ["fetch ended: it failed"]
    finally:
        app.stop()


def test_a_job_of_a_plugin_disabled_meanwhile_can_still_be_stopped():
    app, p, lines = _made()
    try:
        assert _job(app, "fetch", "a model")[0] == 202 and p.began.wait(5)
        assert _api(app, "POST", "/api/plugins/fetcher/enabled", {"on": False})[1]["state"] == "disabled"
        assert _job(app, "fetch", "another")[0] == 409  # disabled: asked nothing new
        status, asked = _cancel(app)  # the flag is the job's: the plugin itself is asked nothing
        assert status == 202 and asked["cancelling"] is True
        assert _ended(app)["cancelled"] is True and p.saw == [True]
    finally:
        p.go.set()
        app.stop()


def test_an_older_librarys_output_takes_no_cancel_and_the_refusal_says_so(monkeypatch):
    monkeypatch.setattr(app_module, "Output", OldOutput)
    app, p, lines = _made()
    try:
        status, job = _job(app, "fetch", "a model")
        assert status == 202 and _three(job) == (False, False, False) and p.began.wait(5)  # the page offers no Cancel
        assert _cancel(app) == (400, {"error": "this liminal-libs cannot cancel a job (1.62.0 can)"})
        assert _three(_now(app)) == (False, False, False) and not any("asked to cancel" in x for x in lines)
        p.go.set()
        done = _ended(app)  # it ran to its end, as every job did
        assert done["ok"] is True and done["answer"] == {"said": "a model is here", "ok": True} and p.saw == [False]
        assert done["text"] == "downloading a model\n" and _three(done) == (False, False, False)
    finally:
        p.go.set()
        app.stop()


def test_a_job_by_itself_says_the_three_and_takes_a_cancel_only_with_an_output_that_can():
    p = Fetcher()
    hooked = Setup(p, None, "fetch", call=lambda log: None)
    assert _three(hooked.describe()) == (True, False, False) and hooked.cancels and not hooked.cancelling
    assert hooked.cancel() is True and hooked.output.cancelled is True
    assert _three(hooked.describe()) == (True, True, False)  # asked; its work has not ended (it was never started)
    hooked.thread.start()
    hooked.thread.join(5)
    assert _three(hooked.describe()) == (True, True, True)  # it had been asked when its work ended: cancelled
    assert _three(hooked.describe(since=0)) == _three(hooked.describe(last=5)) == (True, True, True)
    assert hooked.cancel() is False and _three(hooked.describe()) == (True, True, True)  # after its end: nothing
    done = Setup(p, None, "fetch", call=lambda log: None)
    done.thread.start()
    done.thread.join(5)
    assert done.cancel() is False and done.output.cancelled is False  # ended unasked: a cancel now is too late
    assert _three(done.describe()) == (True, False, False) and done.describe()["ok"] is True
    assert Setup(p, None, "build", call=lambda log: None).cancels is False  # a hook it does not name
    assert Setup(p, ("all",)).cancels is False and Setup(p, None, "update").cancels is False  # no hook's job
    old = Setup(p, None, "fetch", call=lambda log: None)
    old.output = OldOutput()
    assert old.cancel() is False and _three(old.describe()) == (False, False, False)


def test_what_a_plugin_names_as_cancellable_is_read_with_care():
    class Odd(MachinePlugin):
        name = "odd"
        CANCEL_HOOKS = ("pull", 7, None, "install")

    class Unset(MachinePlugin):
        name = "unset"
        CANCEL_HOOKS = None

    class Broken(MachinePlugin):
        name = "broken"

        @property
        def CANCEL_HOOKS(self):  # noqa: N802 - the declaration's own name
            raise RuntimeError("it cannot say")

    assert cancel_hooks(Odd()) == ("pull", "install") and cancel_hooks(Fetcher()) == ("fetch",)
    assert cancel_hooks(Unset()) == () and cancel_hooks(Broken()) == ()
    assert cancel_hooks(MachinePlugin()) == () and cancel_hooks(object()) == ()  # an older library's plugin: none
    assert Setup(Broken(), None, "pull", call=lambda log: None).describe()["cancels"] is False  # its status stays whole


def _held_output(gate: threading.Event, at_end: threading.Event):
    """The job's output in use (the library's; Cancellable before 1.62.0) whose end waits until the test lets it go: the
    job's thread is still alive with its work over and its end noted, as it is for an instant in a real run."""

    class Held(app_module.Output):
        def finish(self):
            at_end.set()
            assert gate.wait(20), "the test never let the job's end go"
            super().finish()

    return Held


def test_a_cancel_that_comes_as_its_work_ends_is_refused_and_the_job_is_said_as_it_ended(monkeypatch):
    gate, at_end = threading.Event(), threading.Event()
    monkeypatch.setattr(app_module, "Output", _held_output(gate, at_end))
    monkeypatch.setattr(app_module, "JOB_REFUSAL_S", 0.05)  # no first line and its end held: its start waits this long
    app, p, lines = _made()
    try:
        assert _job(app, "fetch")[0] == 202  # an argument short: its work fails at once, by itself
        assert at_end.wait(5)  # its work over and its end noted, its thread not ended yet
        now = _now(app)
        assert now["running"] is True and _three(now) == (True, False, False)  # the page still offers Cancel
        assert _cancel(app) == (409, {"error": "fetcher's fetch has ended: there is nothing left to cancel"})
        assert _three(_now(app)) == (True, False, False) and not any("asked to cancel" in x for x in lines)
        gate.set()
        done = _ended(app)
        assert _three(done) == (True, False, False) and done["ok"] is False and done["error"].startswith("TypeError: ")
        # said as it ended (the page: "ended with a failure"), never as cancelled, and nobody asked it to stop
        whats = [r["what"] for r in app.traffic.recent() if r["to"] == "fetcher"]
        assert sorted(whats) == ["fetch ended: it failed", "fetch started"]  # (it ended before its start was noted)
    finally:
        gate.set()
        p.go.set()
        app.stop()


def test_a_cancel_meant_for_a_job_that_has_ended_never_stops_the_next_one():
    app, p, lines = _made()
    try:
        status, first = _job(app, "fetch", "a model")
        assert status == 202 and p.began.wait(5)
        p.go.set()
        assert _ended(app)["answer"] == {"said": "a model is here", "ok": True}
        while time.time() == first["startedAt"]:  # the next job's start told apart from the first's
            time.sleep(0.001)
        p.go.clear()
        p.began.clear()
        status, second = _job(app, "fetch", "another")
        assert status == 202 and p.began.wait(5) and second["startedAt"] != first["startedAt"]
        # a page not told yet that the first has ended sends its Cancel for it, the job's mark as JSON carries it
        stale = json.loads(json.dumps({"startedAt": first["startedAt"]}))
        assert _cancel(app, body=stale) == (409, {"error": "the job asked to stop has ended: fetcher runs another now "
                                                           "(fetch)"})
        assert _three(_now(app)) == (True, False, False) and p.saw == [False]  # the next job goes on, unasked
        for wrong in ("then", True, [1], {"at": 1}):
            assert _cancel(app, body={"startedAt": wrong}) == (400, {"error": "startedAt is the job's own, a number as "
                                                                              "its state says it"})
        named = json.loads(json.dumps({"startedAt": second["startedAt"]}))
        status, asked = _cancel(app, body=named)  # the one under way, named: asked to stop
        assert status == 202 and asked["cancelling"] is True and asked["startedAt"] == second["startedAt"]
        assert _ended(app)["cancelled"] is True and p.saw == [False, True]
        assert lines.count("platform: fetcher asked to cancel fetch") == 1
    finally:
        p.go.set()
        app.stop()
