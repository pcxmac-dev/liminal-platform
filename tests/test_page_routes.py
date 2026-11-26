"""0.39.1 (the review of the sweep after PLT-H1, 2026-11-25; its findings on the platform, rated high): the page's own
routes ask the login too. A plugin's PAGE_ONLY_HOOKS holds a hook asked by name (POST /api/machines/{name}/ask, and
/job for one of its JOB_HOOKS: test_page_only.py). The routes here ask no hook by name: a plugin's settings kept, its
switches (enabled, hidden), its setup, its install or its packages' update as a job, a job's Cancel, its login terminal
opened, read, typed into or closed, a change in the Databases section. So no plugin's word reached them, and any
program on this machine sent them with the two headers PLT-H1 named and no sign-in: a shell in a WSL distribution (the
library's WSL base says `terminal` is its page's alone; the route called it and never read the word), a cloud plugin's
Dynamic DNS hosts set, which its own background then writes as records, a model server stopped by switching its plugin
off.

Each is refused (401) when the login says the person at the browser is not shown to be there (App.present False),
before the request is read any further: nothing is looked up, changed, started, typed or logged. Each is answered as
before when the login says they are, or when the platform holds no login (None). The reads beside them are answered as
before, and the login is asked nothing for them. The plugin here says neither word: the routes are the page's whatever
a plugin says.

A stand-in plugin, a stand-in shell and a login kept in a dict; the app asked directly, as its server asks it: nothing
is served, no port is opened, no process is started (conftest's no_outside fails a test that does). Each job's thread
is joined; none is left to luck."""
from __future__ import annotations

import time

import pytest

from liminal_libs.apps import App, EnvironmentLogin, Refused
from liminal_libs.machines import MachinePlugin
from liminal_libs.machines.terminal import Output
from liminal_libs.sources.keys import KeyVar

from liminal_platform.app import PlatformApp
from liminal_platform.routes import AT_THE_PAGE, MACHINE, ROUTES

pytestmark = pytest.mark.usefixtures("no_outside")

PROVES = callable(getattr(App, "present", None))  # liminal-libs 1.66.0: the login says whether you are there
REQUEST = object()  # the request as the server hands it over: what the login is shown
WORDS = (" only from the platform's page, and the platform's login does not show that you are there: sign in on the "
         "platform's page, then ask again.")
SAID = "refused (401) when the login says you are not at the page"  # what routes.py says of each
CHANGES = ("new", "connect", "share", "port", "credentials", "forget")  # the Databases section's (databases.CHANGES)


def _form(action: str) -> dict:
    """One of a database plugin's forms as its page sends it, confirmed."""
    return {"plugin": "duck", "action": action, "name": "main", "confirm": True}


# Every route the login is asked for: (method, path, body, the refusal's first words). Each is named here, so the check
# taken out of one fails test_each_is_refused... at that route.
GATED = (
    ("POST", "/api/plugins/distro/settings", {"values": {"DISTRO_DDNS_HOSTS": "new.example.com"}},
     "A plugin's settings are kept"),
    ("POST", "/api/plugins/distro/settings", {"forget": ["DISTRO_DDNS_HOSTS"]}, "A plugin's settings are kept"),
    ("POST", "/api/plugins/distro/enabled", {"on": False}, "A plugin is enabled or disabled"),
    ("POST", "/api/machines/distro/enabled", {"on": False}, "A plugin is enabled or disabled"),
    ("POST", "/api/plugins/distro/hidden", {"on": True}, "A plugin's icon is hidden or shown"),
    ("POST", "/api/machines/distro/setup", {}, "A plugin's setup is started"),
    ("POST", "/api/machines/distro/job", {"action": "install"}, "A plugin's install or its packages' update is started"),
    ("POST", "/api/machines/distro/job", {"action": "update"}, "A plugin's install or its packages' update is started"),
    ("POST", "/api/machines/distro/job/cancel", {}, "A job is asked to stop"),
    ("POST", "/api/machines/distro/terminal", {}, "A terminal is opened"),
    ("GET", "/api/machines/distro/terminal", None, "A terminal is read"),
    ("POST", "/api/machines/distro/terminal/input", {"data": "id\r"}, "A terminal is typed into"),
    ("POST", "/api/machines/distro/terminal/close", {}, "A terminal is closed"),
    *(("POST", "/api/databases/instances", _form(action), "A database's instance is changed") for action in CHANGES),
)


class Distro(MachinePlugin):
    """A stand-in system with what the page's own routes reach: a setting, a setup, its packages' update and a login
    terminal. It says neither PAGE_ONLY_HOOKS nor PLUGIN_ONLY_HOOKS, and notes what was done to it."""

    name, title, about, api, order = "distro", "A distro", "a stand-in system", "2.2", 960
    STEPS = ("wsl", "distribution")
    HOOKS = (*MachinePlugin.HOOKS, "update_packages", "terminal")
    keys = (KeyVar("DISTRO_DDNS_HOSTS", label="Dynamic DNS hosts", secret=False),)

    def __init__(self):
        self.setups: list = []
        self.updates = self.changed = self.terminals = 0

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "installed", "why": ""}

    def setup(self, log=print, steps=None):
        self.setups.append(steps)
        return [{"step": step, "ok": True, "detail": "done"} for step in steps or self.STEPS]

    def update_packages(self, log=print):
        self.updates += 1
        return [{"step": "packages", "ok": True, "detail": "up to date"}]

    def terminal(self, user=None):
        self.terminals += 1
        return ["wsl", "-d", "Liminal-Distro"]

    def settings_changed(self):
        self.changed += 1


class Shell:
    """A login shell's stand-in: the keys typed into it, how often it was read, whether it was closed."""

    def __init__(self, argv, title):
        self.argv, self.title, self.typed, self.reads, self.closed = argv, title, "", 0, False
        self.output = Output()
        self.output.write("liminal@pc:~$ ")
        self.seen = time.monotonic()

    @property
    def alive(self):
        return not self.closed

    def read(self, since=0, wait=0.0):
        self.reads += 1
        self.seen = time.monotonic()
        text, start, end = self.output.read(since)
        return {"text": text, "from": start, "offset": end, "alive": self.alive, "title": self.title}

    def write(self, data):
        self.typed += data

    def close(self):
        self.closed = True


def _platform():
    """A platform over the stand-in: the plugin, what its login keeps, the shells made and the log's lines."""
    distro, kept, shells, lines = Distro(), {}, [], []
    app = PlatformApp(log=lines.append, login=EnvironmentLogin(env=kept), machines={"distro": distro}, assistants={},
                      terminal=lambda argv, title: shells.append(Shell(argv, title)) or shells[-1])
    return app, distro, kept, shells, lines


def _answer(app, method: str, path: str, body=None):
    """The app asked as its server asks it, the request handed over with it: its status and answer; a Refused raised
    is its status with {"error": its reason}, as the server sends it."""
    try:
        status, data, *_ = app.api(REQUEST, method, path, {}, None if method == "GET" else (body or {}))
    except Refused as e:
        return e.status, {"error": e.reason}
    return status, data


def _ended(app, name: str) -> None:
    """The job just started for `name`, waited for."""
    job = app._setups[name]
    job.thread.join(10)
    assert not job.thread.is_alive(), "the job never ended"


@pytest.mark.skipif(not PROVES, reason="this liminal-libs has no App.present (1.66.0 has)")
def test_each_is_refused_when_the_login_says_you_are_not_there_and_nothing_is_done():
    app, distro, kept, shells, lines = _platform()
    kept["DISTRO_DDNS_HOSTS"] = "home.example.com"
    asked, seen = [], []
    app.cancel_job = lambda *args: asked.append(("cancel_job", args))
    app.instances_asked = lambda body: asked.append(("instances_asked", body))
    try:
        app.present = lambda handler: True  # a terminal opened while you were there: one to read, type into and close
        assert _answer(app, "POST", "/api/machines/distro/terminal", {})[0] == 200 and len(shells) == 1
        shell, reads = shells[0], shells[0].reads
        lines.clear()
        app.present = lambda handler: seen.append(handler) or False
        for method, path, body, what in GATED:
            assert _answer(app, method, path, body) == (401, {"error": what + WORDS}), (method, path, body)
        assert seen == [REQUEST] * len(GATED)  # the login was shown each request, once
        assert kept == {"DISTRO_DDNS_HOSTS": "home.example.com"} and distro.changed == 0  # kept as it was, the plugin not told
        assert app.enabled("distro") and "distro" not in app.hidden()  # switched neither off nor out of the dock
        assert distro.setups == [] and distro.updates == 0 and "distro" not in app._setups  # no job begun
        assert distro.terminals == 1 and len(shells) == 1  # the plugin asked for no terminal, none made
        assert (shell.typed, shell.reads, shell.closed) == ("", reads, False)  # yours neither typed into, read nor closed
        assert asked == [] and lines == []  # no job asked to stop, no form passed on, nothing logged

        def fails(handler):
            raise RuntimeError("the proof could not be read")

        app.present = fails  # a proof that fails proves nothing
        assert _answer(app, "POST", "/api/machines/distro/terminal/input", {"data": "id\r"})[0] == 401
        assert shell.typed == ""
    finally:
        app.stop()


@pytest.mark.parametrize("there", [True, None], ids=["the login says you are there", "the platform holds no login"])
def test_each_is_answered_as_before_when_you_are_there_or_the_platform_holds_no_login(there):
    app, distro, kept, shells, lines = _platform()
    asked: list = []
    app.instances_asked = lambda body: asked.append(body["action"]) or {"ok": True}
    if there is not None:  # else the tests' platform, which holds no login (LIMINAL_PLATFORM_LOGIN_URL none): None
        app.present = lambda handler: there
    try:
        hosts = {"values": {"DISTRO_DDNS_HOSTS": "new.example.com"}}
        assert _answer(app, "POST", "/api/plugins/distro/settings", hosts)[0] == 200
        assert kept == {"DISTRO_DDNS_HOSTS": "new.example.com"} and distro.changed == 1
        assert _answer(app, "POST", "/api/plugins/distro/settings", {"forget": ["DISTRO_DDNS_HOSTS"]})[0] == 200
        assert "DISTRO_DDNS_HOSTS" not in kept and distro.changed == 2
        assert _answer(app, "POST", "/api/machines/distro/setup", {"steps": ["wsl"]})[0] == 202
        _ended(app, "distro")
        assert _answer(app, "POST", "/api/machines/distro/job", {"action": "install"})[0] == 202
        _ended(app, "distro")
        assert _answer(app, "POST", "/api/machines/distro/job", {"action": "update"})[0] == 202
        _ended(app, "distro")
        assert distro.setups == [("wsl",), None] and distro.updates == 1
        assert _answer(app, "POST", "/api/machines/distro/job/cancel", {})[0] == 409  # past the login: no job runs now
        assert _answer(app, "POST", "/api/machines/distro/terminal", {})[0] == 200 and len(shells) == 1
        assert _answer(app, "GET", "/api/machines/distro/terminal")[0] == 200
        assert _answer(app, "POST", "/api/machines/distro/terminal/input", {"data": "id\r"}) == (200, {"sent": 3})
        assert shells[0].typed == "id\r"
        assert _answer(app, "POST", "/api/machines/distro/terminal/close", {}) == (200, {"closed": True})
        assert shells[0].closed
        for action in CHANGES:
            assert _answer(app, "POST", "/api/databases/instances", _form(action))[0] == 200, action
        assert asked == list(CHANGES)  # each form passed on to the section
        assert _answer(app, "POST", "/api/plugins/distro/hidden", {"on": True})[1]["hidden"] is True
        assert "distro" in app.hidden()
        assert _answer(app, "POST", "/api/plugins/distro/enabled", {"on": False})[0] == 200 and not app.enabled("distro")
        assert _answer(app, "POST", "/api/machines/distro/enabled", {"on": True})[0] == 200 and app.enabled("distro")
    finally:
        app.stop()


def test_the_reads_beside_them_are_answered_as_before_and_the_login_is_asked_nothing():
    app, distro, kept, shells, lines = _platform()
    asked, seen = [], []
    app.present = lambda handler: seen.append(handler) or False
    app.instances_asked = lambda body: asked.append(body["action"]) or {"ok": True}
    try:
        assert _answer(app, "GET", "/api/machines/distro")[0] == 200  # its status, as its page draws it
        assert _answer(app, "GET", "/api/machines/distro/job")[0] == 200  # a job's lines
        assert _answer(app, "GET", "/api/machines/distro/setup")[0] == 200
        assert _answer(app, "POST", "/api/machines/distro/ask", {"hook": "status", "args": []})[0] == 200  # in neither word
        test = {"plugin": "duck", "action": "test", "name": "main"}
        assert _answer(app, "POST", "/api/databases/instances", test)[0] == 200
        assert asked == ["test"]  # an instance's test is a read: passed on to the section
        assert seen == []  # the login was asked nothing for any of them
    finally:
        app.stop()


def test_the_routes_table_says_it_of_each_and_of_no_other():
    """routes.py's rows are what the platform's Internal API tab lists: each route above says there that it is refused
    when the login says you are not at the page (the second switch route as the first one's row), and no other does."""
    assert AT_THE_PAGE == "; " + SAID
    said = {(method, path) for method, path, words, *_ in ROUTES if SAID in words or words.endswith("refused as it is")}
    here = {(method, path.replace("/api/machines/distro", MACHINE).replace("/api/plugins/distro", "/api/plugins/{name}"))
            for method, path, *_ in GATED}
    assert said == here
