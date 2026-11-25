"""0.31.0 (the user, 2026-11-16: "the plugins manage the services, the app can be started @ boot like a service"): a
server a plugin started by a click stops when the platform stops, so the platform tells each machine plugin that it
stops: the plugin's `app_stopping()` when it has one (liminal-libs 1.62.0's AiPlugin), after the page has ended,
enabled or not, attached or not; 0.35.0: all together under one deadline (test_stop_deadline.py), logged in the
registry's order. One that raises is logged and the rest are still told. A second stop (the command's, after the
serve's own) finds the first's end and tells nobody again. Before they are told, nothing new is begun (an ask or a job: 503), a
job under way that takes a cancel is asked to stop, and those jobs and the asks under way (a Start clicked as the
platform stops) are waited for, STOP_WAIT_S at most, so what they start is there to be stopped.

Stand-in plugins and an app that is never started: nothing is served, no port is opened, no process is started
(conftest's no_outside fails a test that does)."""
from __future__ import annotations

import threading

import pytest

from liminal_libs.apps import App, Refused
from liminal_libs.machines import MachinePlugin

from conftest import Box, Other, Served
from conftest import api_answer as _api

import liminal_platform.app as app_module
from liminal_platform.app import STOPPING, PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside", "an_output_that_takes_a_cancel")


class Faulty(Served):
    """One whose server does not end as asked."""

    name, title = "faulty", "Faulty"

    def app_stopping(self):
        super().app_stopping()
        raise RuntimeError("its server would not end")


class Worded(Box):
    """One whose app_stopping is no hook to call: a word."""

    name, title = "worded", "Worded"
    app_stopping = "soon"


class Unsaid(Box):
    """One that cannot even say whether it has the hook."""

    name, title = "unsaid", "Unsaid"

    @property
    def app_stopping(self):
        raise OSError("it cannot say")


def test_each_plugin_is_told_once_that_the_platform_stops_after_its_page_has_ended(monkeypatch):
    told, lines = [], []
    monkeypatch.setattr(App, "_end_server",  # noted in its place, once (a second end of no server does nothing)
                        lambda self: "the page ended" in told or told.append("the page ended"))
    machines = {"served": Served(told), "box": Box(), "other": Other(told)}  # the box: a plugin with no such hook
    app = PlatformApp(log=lines.append, machines=machines, assistants={})
    app.stop()
    assert told[0] == "the page ended" and sorted(told[1:]) == ["other", "served"]  # told together (0.35.0)
    assert lines == []  # nothing to say


def test_one_that_raises_is_logged_and_the_rest_are_still_told():
    told, lines = [], []
    machines = {"faulty": Faulty(told), "worded": Worded(), "unsaid": Unsaid(), "served": Served(told)}
    app = PlatformApp(log=lines.append, machines=machines, assistants={})
    app.stop()
    assert sorted(told) == ["faulty", "served"]
    assert sorted(lines) == ["platform: faulty did not stop cleanly: RuntimeError: its server would not end",
                             "platform: unsaid did not stop cleanly: OSError: it cannot say"]


def test_stopping_twice_tells_each_plugin_once():
    """0.35.0: the second stop of an ordinary end finds the first's (the frame's terminate, once); until then each
    plugin was told twice."""
    told, lines = [], []
    app = PlatformApp(log=lines.append, machines={"served": Served(told), "faulty": Faulty(told)}, assistants={})
    app.stop()  # as the serve ends
    app.stop()  # and again, as a command that stops it would
    assert sorted(told) == ["faulty", "served"]
    assert lines == ["platform: faulty did not stop cleanly: RuntimeError: its server would not end"]


def test_a_plugin_is_told_whether_it_is_enabled_or_attached_or_neither():
    told = []
    served, other = Served(told), Other(told)
    app = PlatformApp(log=lambda m: None, machines={"served": served, "other": other}, assistants={})
    assert app.attach_plugins([served]) == ["served"] and other.app is None  # one attached, one never
    assert app.set_enabled("other", False)["state"] == "disabled"
    app.stop()
    assert sorted(told) == ["other", "served"]  # what a disabled one may still run ends with the platform too


def test_the_plugins_are_told_even_when_the_page_does_not_end_cleanly(monkeypatch):
    told = []

    def broken(self):
        raise OSError("the server would not close")

    monkeypatch.setattr(App, "_end_server", broken)
    app = PlatformApp(log=lambda m: None, machines={"served": Served(told)}, assistants={})
    with pytest.raises(OSError, match="the server would not close"):
        app.stop()
    assert told == ["served"]


def test_a_registry_that_cannot_say_is_logged_and_the_platform_ends_all_the_same(monkeypatch):
    lines = []
    app = PlatformApp(log=lines.append, machines={}, assistants={})

    def lost():
        raise RuntimeError("the plugins could not be found")

    monkeypatch.setattr(app, "machines", lost)
    app.stop()
    assert lines == ["platform: its plugins could not be told that it stops: "
                     "RuntimeError: the plugins could not be found"]


class Starter(MachinePlugin):
    """A stand-in whose Start is held until the test lets it go (a server's launch under way), noting when it has
    started and when it is told that the platform stops."""

    name, title, about, api, order = "starter", "Starter", "a stand-in whose start takes a while", "2.2", 915
    HOOKS = (*MachinePlugin.HOOKS, "start")

    def __init__(self, events: list):
        self.events = events
        self.inside, self.go = threading.Event(), threading.Event()

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def start(self, name):
        self.inside.set()
        assert self.go.wait(20), "the test never let the start go"
        self.events.append(f"started {name}")
        return {"said": f"{name} started", "ok": True}

    def app_stopping(self):
        self.events.append("told")


class Puller(Starter):
    """A stand-in whose pull is a job that takes a cancel (it looks at its log's flag between its reads) and whose build
    is a job that runs to its end."""

    name, title, about, order = "puller", "Puller", "a stand-in with a long download", 916
    HOOKS = (*MachinePlugin.HOOKS, "pull", "build")
    JOB_HOOKS = ("pull", "build")
    CANCEL_HOOKS = ("pull",)

    def pull(self, what, log=None):
        self.inside.set()
        for _ in range(2000):
            if getattr(log, "cancelled", False):
                self.events.append(f"{what}: stopped as asked")
                return {"said": f"cancelled: {what} is not pulled", "ok": False}
            if self.go.wait(0.01):
                return {"said": f"{what} pulled", "ok": True}
        raise AssertionError("nobody stopped the pull")

    def build(self, log=None):
        self.inside.set()
        assert self.go.wait(20), "the test never let the build go"
        return {"said": "built", "ok": True}


def _a_new_life(self, port=None, open_browser=False):
    """The frame's start as far as its end goes (liminal-libs 1.86.0's App.start: a new life after an end), and no
    page served."""
    with self._term_lock:
        self._terminating, self._terminated = False, None
    return "its page"


def _start(app, name="default"):
    return _api(app, "POST", "/api/machines/starter/ask", {"hook": "start", "args": [name]})


def test_a_job_that_takes_a_cancel_is_asked_to_stop_and_waited_for_before_the_plugins_are_told(monkeypatch):
    monkeypatch.setattr(app_module, "JOB_REFUSAL_S", 0.05)  # the pull prints no first line: its start waits this long
    events, lines = [], []
    puller = Puller(events)
    app = PlatformApp(log=lines.append, machines={"puller": puller}, assistants={})
    try:
        job = {"action": "hook", "hook": "pull", "args": ["a model"]}
        assert _api(app, "POST", "/api/machines/puller/job", job)[0] == 202 and puller.inside.wait(5)
        app.stop()
        assert events == ["a model: stopped as asked", "told"]  # ended (and what it ran with it) before it is told
        assert lines == ["platform: puller asked pull as a job (1 argument)",
                         "platform: puller's pull asked to stop: the platform stops"]
        done = _api(app, "GET", "/api/machines/puller/job")[1]
        assert (done["running"], done["cancelling"], done["cancelled"], done["ok"]) == (False, True, True, False)
        assert "pull asked to stop" in [r["what"] for r in app.traffic.recent() if r["to"] == "puller"]
        app.stop()  # a second stop: the first's end (0.35.0), nothing asked, waited for or told again
        assert events == ["a model: stopped as asked", "told"] and len(lines) == 2
    finally:
        puller.go.set()


def test_a_job_that_runs_to_its_end_is_neither_asked_nor_waited_for(monkeypatch):
    monkeypatch.setattr(app_module, "STOP_WAIT_S", 60.0)  # a wait for it would show: the stop would take a minute
    monkeypatch.setattr(app_module, "JOB_REFUSAL_S", 0.05)  # the build prints no first line: its start waits this long
    events, lines = [], []
    puller = Puller(events)
    app = PlatformApp(log=lines.append, machines={"puller": puller}, assistants={})
    try:
        job = {"action": "hook", "hook": "build", "args": []}
        assert _api(app, "POST", "/api/machines/puller/job", job)[0] == 202 and puller.inside.wait(5)
        stopper = threading.Thread(target=app.stop)
        stopper.start()
        stopper.join(30)
        assert not stopper.is_alive() and events == ["told"]  # told at once; the build runs on, as every job did
        assert _api(app, "GET", "/api/machines/puller/job")[1]["running"] is True
        assert not any("asked to stop" in x for x in lines)
    finally:
        puller.go.set()


def test_an_ask_under_way_is_waited_for_before_the_plugins_are_told():
    events = []
    starter = Starter(events)
    app = PlatformApp(log=lambda m: None, machines={"starter": starter}, assistants={})
    waiting = threading.Event()

    class Watched(threading.Condition):
        """The stop's wait for the asks under way, seen as it begins."""

        def wait(self, timeout=None):
            waiting.set()
            return super().wait(timeout)

    app._asked = Watched(app._lock)
    answers = []
    asker = threading.Thread(target=lambda: answers.append(_start(app)))
    asker.start()
    stopper = threading.Thread(target=app.stop)
    try:
        assert starter.inside.wait(5)  # a Start clicked as the platform stops: its server's launch under way
        stopper.start()
        assert waiting.wait(5)  # the stop waits for it: without the wait it would tell the plugin now
        assert events == [] and _start(app, "another") == (503, {"error": STOPPING})  # nothing new is begun
        starter.go.set()
        stopper.join(10)
        asker.join(10)
        assert not stopper.is_alive() and events == ["started default", "told"]  # started, then told: it is stopped
        assert answers == [(200, {"answer": {"said": "default started", "ok": True}})]
    finally:
        starter.go.set()
        asker.join(10)
        if stopper.is_alive():
            stopper.join(10)


def test_an_ask_that_does_not_end_holds_the_stop_for_a_bounded_time(monkeypatch):
    monkeypatch.setattr(app_module, "STOP_WAIT_S", 0.2)
    events, lines = [], []
    starter = Starter(events)
    app = PlatformApp(log=lines.append, machines={"starter": starter}, assistants={})
    asker = threading.Thread(target=lambda: _start(app))
    asker.start()
    try:
        assert starter.inside.wait(5)
        app.stop()  # held 0.2 s, then the plugins are told all the same
        assert events == ["told"]
        assert lines[-1] == ("platform: 1 ask of its plugins still under way after 0.2 s: the plugins are told that it "
                             "stops all the same")
    finally:
        starter.go.set()
        asker.join(10)
    assert events == ["told", "started default"]


def test_once_it_stops_nothing_new_is_begun_until_it_starts_again(monkeypatch):
    events = []
    puller, starter = Puller(events), Starter(events)
    app = PlatformApp(log=lambda m: None, machines={"puller": puller, "starter": starter}, assistants={})
    app.stop()
    refused = (503, {"error": STOPPING})
    assert _start(app) == refused
    assert _api(app, "POST", "/api/machines/puller/job", {"action": "hook", "hook": "pull", "args": ["m"]}) == refused
    assert _api(app, "POST", "/api/machines/puller/setup", {}) == refused
    with pytest.raises(Refused, match="the platform is stopping"):
        app.ask("starter", "start", ["default"])  # a plugin asking another through the platform, likewise
    assert not starter.inside.is_set() and not puller.inside.is_set() and events == ["told", "told"]
    assert _api(app, "GET", "/api/machines/starter")[0] == 200  # a read of its state is no ask: answered
    monkeypatch.setattr(App, "start", lambda self, port=None, open_browser=False: "its page")  # nothing is served
    assert app.start(0) == "its page"
    starter.go.set()
    assert _start(app) == (200, {"answer": {"said": "default started", "ok": True}})
    app.stop()


class Term:
    """A stand-in login terminal (no program is started): open until it is closed, its close noted."""

    def __init__(self, argv, title, events: list):
        self.argv, self.title, self.alive, self.seen, self.events = list(argv), title, True, float("inf"), events

        class Printed:
            end = 0
        self.output = Printed()

    def read(self, since=0, wait=0):
        return {"text": "", "from": 0, "offset": 0, "alive": self.alive}

    def close(self):
        if self.alive:
            self.events.append("terminal closed")
        self.alive = False


class Shell(MachinePlugin):
    """A stand-in with a login terminal and a command, either held until the test lets it go (the plugin working out
    which program its terminal opens; a command under way), noting what it ran and when it is told that the platform
    stops."""

    name, title, about, api, order = "shell", "Shell", "a stand-in with a terminal and a command", "2.2", 917
    HOOKS = (*MachinePlugin.HOOKS, "terminal")

    def __init__(self, events: list):
        self.events = events
        self.inside, self.go = threading.Event(), threading.Event()

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def terminal(self):
        self.inside.set()
        assert self.go.wait(20), "the test never let the terminal go"
        return ["a-stand-in-shell"]

    def run(self, *command, **options):
        self.inside.set()
        assert self.go.wait(20), "the test never let the command go"
        self.events.append("ran " + " ".join(command))
        return "ran\n"

    def app_stopping(self):
        self.events.append("told")


def _shell_app(events: list, lines: list | None = None):
    made: list[Term] = []
    shell = Shell(events)
    app = PlatformApp(log=(lines.append if lines is not None else lambda m: None), machines={"shell": shell},
                      assistants={}, terminal=lambda argv, title: made.append(Term(argv, title, events)) or made[-1])
    return app, shell, made


def _stopping_while(app, shell, ask):
    """`ask` asked in a thread, held inside the plugin; then the platform stopped in another, the stop seen waiting
    for it (its wait for what is under way, as it begins). Returns the two threads and what `ask` answered."""
    waiting = threading.Event()

    class Watched(threading.Condition):
        def wait(self, timeout=None):
            waiting.set()
            return super().wait(timeout)

    app._asked = Watched(app._lock)
    answers: list = []
    asker = threading.Thread(target=lambda: answers.append(ask()))
    asker.start()
    assert shell.inside.wait(5)  # inside the plugin: what it opens or runs is under way
    stopper = threading.Thread(target=app.stop)
    stopper.start()
    assert waiting.wait(5), "the stop did not wait for what was under way"
    return asker, stopper, answers


def test_a_terminal_opened_as_the_platform_stops_is_waited_for_closed_and_refused(monkeypatch):
    monkeypatch.setattr(app_module, "STOP_WAIT_S", 30.0)  # held only by what is under way: the test lets it go
    events = []
    app, shell, made = _shell_app(events)
    asker = stopper = None
    try:
        asker, stopper, answers = _stopping_while(app, shell, lambda: _api(app, "POST", "/api/machines/shell/terminal"))
        assert events == []  # the plugin is not told while its terminal is being opened
        assert _api(app, "POST", "/api/machines/shell/terminal") == (503, {"error": STOPPING})  # no other is begun
        shell.go.set()
        stopper.join(10)
        asker.join(10)
        assert not stopper.is_alive() and not asker.is_alive()
        # made after the stop had closed the terminals: closed at once, before the plugin is told, and refused
        assert answers == [(503, {"error": STOPPING})] and events == ["terminal closed", "told"]
        assert len(made) == 1 and not made[0].alive and app.terminal_of("shell") is None
    finally:
        shell.go.set()
        for t in (asker, stopper):
            if t is not None and t.is_alive():
                t.join(10)


def test_once_it_stops_no_terminal_is_opened_and_no_command_run_until_it_starts_again(monkeypatch):
    events, lines = [], []
    app, shell, made = _shell_app(events, lines)
    shell.go.set()  # nothing is held: what is asked is done at once
    app.stop()
    refused = (503, {"error": STOPPING})
    assert _api(app, "POST", "/api/machines/shell/terminal") == refused
    assert not shell.inside.is_set() and made == [] and events == ["told"] and lines == []
    monkeypatch.setattr(App, "start", _a_new_life)  # nothing is served
    assert app.start(0) == "its page"
    assert _api(app, "POST", "/api/machines/shell/terminal")[0] == 200 and app.terminal_of("shell") is made[0]
    app.stop()
    assert events == ["told", "terminal closed", "told"]


class Ticks:
    """A stand-in for the sweep's end event: its wait answers "not yet" `n` times (one sweep each), then "ended",
    so the sweep's steps are run one by one with no time passing."""

    def __init__(self, n: int, before=None):
        self.n, self.before = n, before

    def wait(self, timeout=None):
        if self.n <= 0:
            return True
        self.n -= 1
        if self.before is not None:
            self.before()
        return False


def test_a_terminal_no_page_reads_is_closed_by_the_sweep_with_no_terminal_request():
    # 0.34.2 (the review of 2026-11-21, item 26): a closed tab stops reading without closing its terminal; idle ones
    # were closed only when another terminal request came, so its login shell ran on until then
    events = []
    app, shell, made = _shell_app(events)
    shell.go.set()
    now = [1000.0]
    app._clock = lambda: now[0]
    assert _api(app, "POST", "/api/machines/shell/terminal")[0] == 200
    term = made[0]
    term.seen = 1000.0  # read last at 1000
    now[0] = 1000.0 + app_module.TERMINAL_IDLE_S - 1  # not idle long enough yet
    app._sweep(Ticks(1))
    assert term.alive and app.terminal_of("shell") is term
    now[0] = 1000.0 + app_module.TERMINAL_IDLE_S + 1  # no page has read it since: the next sweep closes it
    app._sweep(Ticks(1))
    assert not term.alive and app.terminal_of("shell") is None and events == ["terminal closed"]


def test_the_sweep_runs_while_it_is_served_and_ends_with_the_stop(monkeypatch):
    events = []
    app, shell, made = _shell_app(events)
    monkeypatch.setattr(App, "start", lambda self, port=None, open_browser=False: "its page")  # nothing is served
    monkeypatch.setattr(app_module, "TERMINAL_SWEEP_S", 3600.0)  # it never sweeps here: only its start and end
    assert app.start(0) == "its page"
    sweeper = app._sweeper
    assert sweeper is not None and sweeper.is_alive()
    app.start(0)  # a second start begins no second sweep
    assert app._sweeper is sweeper
    app.stop()
    assert not sweeper.is_alive() and app._sweeper is None
    once = PlatformApp(log=lambda m: None, machines={"shell": shell}, assistants={}, once=True)
    assert once.start(0) == "its page" and once._sweeper is None  # a one-shot app sweeps nothing
    once.stop()


def test_a_job_that_takes_no_cancel_is_named_in_the_log_as_running_on(monkeypatch):
    # 0.34.2 (the review of 2026-11-21, item 26): a setup, an update or a hook's job with no cancel runs on at the stop,
    # and what it started may outlive the platform: said in the log, not left unsaid
    monkeypatch.setattr(app_module, "JOB_REFUSAL_S", 0.05)
    events, lines = [], []
    puller = Puller(events)
    app = PlatformApp(log=lines.append, machines={"puller": puller}, assistants={})
    try:
        job = {"action": "hook", "hook": "build", "args": []}
        assert _api(app, "POST", "/api/machines/puller/job", job)[0] == 202 and puller.inside.wait(5)
        app.stop()
        assert ("platform: puller's build runs on as the platform stops: it takes no cancel, and what it started may "
                "outlive the platform") in lines
    finally:
        puller.go.set()
