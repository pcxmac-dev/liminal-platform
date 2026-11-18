"""The platform's own two views (liminal-libs 1.63.0's App, GET /api/app/apis; the user, 2026-11-16: "for all apps, and
all plugins, there should be an external api tab, and an internal api tab"): what it associates with (apis.py, its
External API: the docker command, WSL's command, the version control tools its Codebase reads, how it reads this
machine's facts, the signals its serve takes) and what it offers its plugins and other apps (its Internal API: its
routes beside the frame's, what it calls on its plugins, what a job's hook is handed). Answered by calling the app's
routes in this process: nothing is served or started, and the links are read only as text (the platform never fetches
them)."""
from __future__ import annotations

import ast
import inspect
import re
import threading
from pathlib import Path

import pytest

from liminal_libs.apps import App, EnvironmentLogin, Refused
from liminal_libs.machines import MachinePlugin
from liminal_libs.sources.apis import Api, problems

from conftest import api_answer as _api

import liminal_platform.app as app_mod
import liminal_platform.cli as cli
from liminal_platform.apis import APIS
from liminal_platform.app import CALLS, PlatformApp
from liminal_platform.routes import ROUTES

pytestmark = pytest.mark.usefixtures("no_outside")  # nothing started, served or reached (tests/conftest.py)

URL = re.compile(r"\b(?:https?|wss?|ftp)://([A-Za-z0-9.-]+)")  # a scheme://host literal, as the charts' boundary test
THIS_MACHINE = {("app.py", "127.0.0.1")}  # PlatformApp.LOGIN_URL: 1.46-1.51's declaration of its login, on this machine
SIGNALS = "Python's signal module"  # the card of the signals its serve takes (0.32.0)


class Kept(MachinePlugin):
    """A stand-in machine plugin, attached to the platform."""

    name, title, about, api, order = "kept", "Kept", "a stand-in attached to the platform", "2.2", 930

    def present(self):
        return True

    def status(self):
        return {"present": True, "summary": "kept"}


def _app(**kw) -> PlatformApp:
    return PlatformApp(log=lambda m: None, login=EnvironmentLogin(env={}), assistants={}, settings=lambda: object(),
                       **{"machines": {}, **kw})


def _frame_says() -> bool:
    """Whether the frame answers an app's own two views (liminal-libs 1.63.0: App.own_apis, GET /api/app/apis)."""
    return callable(getattr(App, "own_apis", None)) and app_mod.internal_mod is not None


FRAME = pytest.mark.skipif(not _frame_says(), reason="liminal-libs before 1.63.0: no GET /api/app/apis in its frame")


def test_what_the_platform_associates_with_is_sound_and_its_own():
    app = _app()
    assert app.apis is APIS and isinstance(APIS, tuple) and problems(APIS) == []
    assert [a.name for a in APIS] == ["Docker's command line", "WSL's command line", "git", "Subversion (svn)",
                                      "Mercurial (hg)", "Python's platform and os modules",
                                      "Windows' GlobalMemoryStatusEx", "Python's signal module"]
    for api in APIS:
        assert isinstance(api, Api) and api.docs.startswith("https://"), api.name
        assert any(c.used for c in api.calls), f"{api.name}: no call the platform makes"  # each is one it makes
        assert api.verified == ("2026-11-18" if api.name == SIGNALS else "2026-11-17")  # the day its pages were read
    # nothing of a plugin's own: the Docker plugin's engine API, a cloud's REST API, the globe's map (the library's)
    assert not {"Docker Engine API", "Docker Hub API", "world-atlas"} & {a.name for a in APIS}
    # what the platform's code calls is what the cards say it calls (the docker command's two reads)
    docker = {c.name for c in APIS[0].calls if c.used}
    assert docker == {"docker version --format '{{json .}}'", "docker context ls --format '{{json .}}'"}


def test_the_signals_its_serve_takes_are_named():
    """0.31.0's serve ends on SIGTERM and SIGHUP on POSIX as on Ctrl+C (cli.end_on_signals): a system interface the
    platform's own code calls, so its External API names it, with Python's page for the signal module: each signal the
    serve takes (cli.ENDING_SIGNALS), and as its calls those cli.py makes of that module, held to its source."""
    card = next((a for a in APIS if a.name == SIGNALS), None)
    assert card is not None, f"no card of {SIGNALS} among {[a.name for a in APIS]}"
    assert card.kind == "system" and "POSIX" in card.base
    assert card.docs == "https://docs.python.org/3/library/signal.html"
    used = [c.name for c in card.used]
    assert cli.ENDING_SIGNALS == ("SIGTERM", "SIGHUP") and all(s in card.about for s in cli.ENDING_SIGNALS)
    assert all(s in name for name in used for s in cli.ENDING_SIGNALS), used  # each call, of both
    # what end_on_signals calls of its `signals` (the signal module, or a test's stand-in) is what the card says
    tree = ast.parse(inspect.getsource(cli.end_on_signals))
    made = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "signals"}
    assert made == {"getsignal", "signal"}
    assert sorted(name.split("(", 1)[0] for name in used) == sorted(f"signal.{m}" for m in made)
    taken = next(c for c in card.used if c.name.startswith("signal.getsignal("))
    assert "SIG_DFL" in taken.used and "signals.SIG_DFL" in inspect.getsource(cli.end_on_signals)  # a default only


def test_the_cards_are_loaded_only_when_asked():
    """app.py imports neither apis.py nor anything of liminal_libs.sources (which loads the registry and pandas) when it
    is imported: PlatformApp.apis imports its cards when they are first asked for."""
    tree = ast.parse(Path(app_mod.__file__).read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    top += [n for t in tree.body if isinstance(t, ast.Try) for n in t.body
            if isinstance(n, (ast.Import, ast.ImportFrom))]
    modules = {("." * n.level) + (n.module or "") for n in top if isinstance(n, ast.ImportFrom)}
    modules |= {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    assert ".apis" not in modules and not any(m.startswith("liminal_libs.sources") for m in modules), modules
    assert ".routes" in modules  # plain rows, nothing imported with them
    assert isinstance(PlatformApp.__dict__["apis"], property)


def test_no_other_py_of_the_platform_names_an_outside_host():
    """The user's rule of 2026-10-31 (the app's code names no provider's host; links for people excepted): the
    platform's outside addresses are its cards' links, in apis.py alone; every other module names this machine at
    most."""
    root = Path(app_mod.__file__).parent
    found = {(p.relative_to(root).as_posix(), h.lower().rstrip("."))
             for p in root.rglob("*.py") for h in URL.findall(p.read_text(encoding="utf-8"))}
    assert {(f, h) for f, h in found if f != "apis.py"} <= THIS_MACHINE
    hosts = {h for f, h in found if f == "apis.py"}
    assert {"docs.docker.com", "learn.microsoft.com", "git-scm.com", "docs.python.org"} <= hosts


class Handed(MachinePlugin):
    """A stand-in whose pull is a job that takes a cancel: it notes what it is handed, gives its log a line, and waits
    until its log is cancelled or the test lets it go (20 s at the most, so no test hangs on it)."""

    name, title, about, api, order = "handed", "Handed", "a stand-in noting what its job is handed", "2.2", 931
    HOOKS = (*MachinePlugin.HOOKS, "pull")
    JOB_HOOKS = ("pull",)
    CANCEL_HOOKS = ("pull",)

    def __init__(self):
        self.handed: dict = {}
        self.began, self.go = threading.Event(), threading.Event()

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "here", "why": ""}

    def pull(self, what, log=None):
        """A long pull, run as a job: it ends by itself once its log is cancelled."""
        self.handed.update(what=what, log=log)
        log(f"pulling {what}")
        self.began.set()
        for _ in range(2000):
            if getattr(log, "cancelled", False):
                return {"said": f"cancelled: {what} is not pulled", "ok": False}
            if self.go.wait(0.01):
                break
        return {"said": f"{what} is pulled", "ok": True}


def test_its_internal_api_says_what_a_jobs_hook_is_handed(an_output_that_takes_a_cancel):
    """Its own notes (INTERNAL_NOTES, which liminal-libs 1.63.0's internal.app_internal reads whole: each line at most
    NOTE_CHARS characters, MAX_WORDS lines at the most) say what a hook asked as a job is handed beside its arguments,
    which neither CALLS nor its routes say; and a job asked through the platform's own routes does what they say (on a
    library before 1.62.0, with conftest's output that takes a cancel)."""
    notes = PlatformApp.__dict__.get("INTERNAL_NOTES")  # its own, not the frame's (() since liminal-libs 1.63.0)
    chars = getattr(app_mod.internal_mod, "NOTE_CHARS", 400)
    most = getattr(app_mod.internal_mod, "MAX_WORDS", 40)
    assert isinstance(notes, tuple) and 0 < len(notes) <= most
    assert all(isinstance(n, str) and n == n.strip() and 0 < len(n) <= chars for n in notes), [len(n) for n in notes]
    said = " ".join(notes)
    for words in ("JOB_HOOKS", "POST /api/machines/{name}/job {action: hook", "log=, the job's output",
                  "shown in the job's panel", "log.cancelled is set by the page's Cancel", "CANCEL_HOOKS",
                  "lets go of its arguments once the hook has run"):
        assert words in said, words
    handed = Handed()
    app = _app(machines={"handed": handed})
    try:
        status, job = _api(app, "POST", "/api/machines/handed/job", {"action": "hook", "hook": "pull", "args": ["it"]})
        assert status == 202 and job["hook"] is True and job["cancels"] is True and handed.began.wait(5)
        running = app._setups["handed"]
        assert handed.handed["what"] == "it" and handed.handed["log"] is running.output  # log=, the job's output
        panel = _api(app, "GET", "/api/machines/handed/job", query={"since": "0"})[1]
        assert panel["text"].startswith("pulling it\n")  # what it gave log, in the job's panel as it comes
        assert _api(app, "POST", "/api/machines/handed/job/cancel")[0] == 202  # the page's Cancel
        assert handed.handed["log"].cancelled is True  # seen by the hook, which ends by itself
        running.thread.join(5)
        assert not running.running and running.describe()["cancelled"] is True
        assert running.call is None and running.hooked  # once it has run, it lets go of the call with its arguments
    finally:
        handed.go.set()
        app.stop()


@FRAME
def test_the_platform_answers_its_own_two_views():
    kept = Kept()
    app = _app(machines={"kept": kept})
    assert app.attach_plugins([kept]) == ["kept"]
    status, own = app.api(None, "GET", "/api/app/apis", {}, None)[:2]
    assert status == 200 and {"app", "internal", "apis", "apiFacts"} <= set(own)
    assert own["app"]["app"] == "platform" and [a["name"] for a in own["apis"]] == [a.name for a in APIS]
    assert own["apis"][0]["calls"][0]["used"]  # the cards as a plugin's are drawn (as_dicts)
    internal = own["internal"]
    assert internal["of"] == "app" and internal["name"] == "platform"
    # its routes, its own marked so, beside the frame's
    mine = {(r["method"], r["path"]) for r in internal["routes"] if r.get("own")}
    assert mine == {(r[0], r[1]) for r in ROUTES}
    assert {("GET", "/api/app/apis"), ("GET", "/api/traffic")} <= {(r["method"], r["path"]) for r in internal["routes"]}
    # what it calls on a plugin of each kind, in its code's words
    calls = internal["calls"]
    assert calls["machine"]["status"] == CALLS["machine"]["status"] and set(calls) == set(CALLS)
    # what a job's hook is handed: its notes, whole (none cut or left out)
    assert internal["notes"] == list(PlatformApp.INTERNAL_NOTES) and internal["notes"]
    # the plugins it holds
    assert [p["name"] for p in internal["plugins"]] == ["kept"]


@FRAME
def test_a_plugins_shared_structure_is_given_to_code_by_its_name():
    kept = Kept()
    app = _app(machines={"kept": kept})
    app.attach_plugins([kept])
    status, got = app.api(None, "GET", "/api/app/apis", {"plugin": "kept"}, None)[:2]
    assert status == 200 and got["name"] == "kept" and {"internal", "apis", "apiFacts"} <= set(got)
    assert got["internal"]["name"] == "kept" and got["internal"]["calls"]["plugins"] == \
        "self.app.ask('kept', hook, [arguments])"
    try:  # refused, as the frame refuses (Refused), or answered so
        missing = app.api(None, "GET", "/api/app/apis", {"plugin": "nobody"}, None)[0]
    except Refused as e:
        missing = e.status
    assert missing == 404
