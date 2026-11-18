"""The platform's own two views (liminal-libs 1.63.0's App, GET /api/app/apis; the user, 2026-11-16: "for all apps, and
all plugins, there should be an external api tab, and an internal api tab"): what it associates with (apis.py, its
External API: the docker command, WSL's command, the version control tools its Codebase reads, how it reads this
machine's facts) and what it offers its plugins and other apps (its Internal API: its routes beside the frame's, what
it calls on its plugins). Answered by calling the app's routes in this process: nothing is served or started, and the
links are read only as text (the platform never fetches them)."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from liminal_libs.apps import App, EnvironmentLogin, Refused
from liminal_libs.machines import MachinePlugin
from liminal_libs.sources.apis import Api, problems

import liminal_platform.app as app_mod
from liminal_platform.apis import APIS
from liminal_platform.app import CALLS, PlatformApp
from liminal_platform.routes import ROUTES

pytestmark = pytest.mark.usefixtures("no_outside")  # nothing started, served or reached (tests/conftest.py)

URL = re.compile(r"\b(?:https?|wss?|ftp)://([A-Za-z0-9.-]+)")  # a scheme://host literal, as the charts' boundary test
THIS_MACHINE = {("app.py", "127.0.0.1")}  # PlatformApp.LOGIN_URL: 1.46-1.51's declaration of its login, on this machine


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
                                      "Windows' GlobalMemoryStatusEx"]
    for api in APIS:
        assert isinstance(api, Api) and api.docs.startswith("https://"), api.name
        assert any(c.used for c in api.calls), f"{api.name}: no call the platform makes"  # each is one it makes
        assert api.verified == "2026-11-17"
    # nothing of a plugin's own: the Docker plugin's engine API, a cloud's REST API, the globe's map (the library's)
    assert not {"Docker Engine API", "Docker Hub API", "world-atlas"} & {a.name for a in APIS}
    # what the platform's code calls is what the cards say it calls (the docker command's two reads)
    docker = {c.name for c in APIS[0].calls if c.used}
    assert docker == {"docker version --format '{{json .}}'", "docker context ls --format '{{json .}}'"}


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
