"""Each plugin's status says what the plugin shares with the platform, for its Internal API tab (liminal-libs 1.63.0's
internal.py; the user, 2026-11-16: "the internal api is for interfaces the plugin shares with the rest of the app";
2026-11-17: "describe the internal API like structure that the app code can work with", "all plugins are middleware",
"even for other plugins", "and then the app object code"). The library makes it from the plugin object; the platform
says what its own code calls on a plugin of each kind (CALLS, ATTRIBUTES: held here to its source), what it asks by
name (askable), how it is asked (call_words), which plugins there are (known_plugins), its tabs as it keeps them, and
which hooks a status names for its page to ask (pageAsks). A hook a plugin says only reads is asked as one.

Stand-in plugins, the platform's routes called in this process: nothing is served, started or reached. Where the
library is older than 1.63.0, internal.py and the frame's plugin_internal are stood in to test the platform's part,
and the tests of what the library makes of a plugin are skipped."""
from __future__ import annotations

import ast
import inspect
import json
import types

import pytest

from liminal_libs.apps import App, EnvironmentLogin
from liminal_libs.apps.tabs import Tab
from liminal_libs.machines import MachinePlugin
from liminal_libs.sources.keys import KeyVar
from liminal_libs.sources.plugin import PlatformPlugin
from liminal_libs.web import WRITE_HEADER

import liminal_platform.app as app_mod
from liminal_platform.app import (ASK_TERMS, ATTRIBUTES, CALLS, MAX_PAGE_ASKS, NOT_ASKED, OWN_TABS, PAGE_ASKS_DEPTH,
                                  PAGE_ASKS_EACH, PAGE_ASKS_NODES, READS, PlatformApp, page_asks, tabs_of)

pytestmark = pytest.mark.usefixtures("no_outside")  # nothing started, served or reached (tests/conftest.py)


class Shared(MachinePlugin):
    """A stand-in sharing a hook of every kind: a read it says only reads, changes (one asked twice), a job, a tab's
    page, a service other plugins ask (and its status, which the platform reads too), its check; a key, what it keeps
    through the login beside it, what it asks of other plugins. Each hook it answers notes that it was asked."""

    name, title, about, api, order = "shared", "Shared", "a stand-in sharing every kind of hook", "2.2", 920
    HOOKS = (*MachinePlugin.HOOKS, "refresh", "poke", "risky", "fetch", "page", "serve_others", "check")
    READ_HOOKS = ("refresh",)
    SERVICE_HOOKS = ("serve_others", "status")
    JOB_HOOKS = ("fetch",)
    TABS = (Tab("page", "Its page", "page", 3.0), Tab("external", "Not External API", "page"),
            Tab("Internal", "Not Internal API", "page"), Tab("API", "Not the old API's", "page"),
            Tab("MAIN", "Not Main", "page"))
    keys = (KeyVar("SHARED_API_KEY", "Its key"),)
    ASKS = (("asker", "lend", "what it lends"), ("", "serving"))
    KEEPS = (("SHARED_GROUPS", "the groups of its rules"),)

    def __init__(self):
        self.asked: list[str] = []

    def present(self):
        self.asked.append("present")
        return True

    def status(self):
        """What it is, its forms, actions and tables naming the hooks its page asks."""
        self.asked.append("status")
        return {"present": True, "summary": "shared", "forms": [{"id": "poke", "hook": "poke", "fields": []}],
                "actions": [{"id": "again", "title": "Read again", "hook": "refresh"}],
                "tables": [{"title": "Rules", "move": {"hook": "risky", "groups": ["a"]}, "rows": [[1, "x"]]}]}

    def refresh(self):
        """Its state read again now: nothing changes."""
        self.asked.append("refresh")
        return {"fresh": True}

    def poke(self):
        """Something changed on this machine."""
        self.asked.append("poke")
        return {"poked": True}

    def risky(self, what, accept_risk=False):
        """A risky change, refused once: accept_risk accepts the refusal."""
        self.asked.append("risky")
        return {"risked": what}

    def fetch(self, log=None):
        """A long download, run as a job."""
        self.asked.append("fetch")
        return {"ok": True}

    def page(self):
        """Its tab's page, asked every three seconds while the tab is shown."""
        self.asked.append("page")
        return {"title": "its page"}

    def serve_others(self, what):
        """A service the other plugins ask through the platform."""
        self.asked.append("serve_others")
        return {"served": what}

    def check(self):
        """Its check of this machine for what it installs."""
        self.asked.append("check")
        return {"ready": True, "installed": True}


class Asker(MachinePlugin):
    """A stand-in that asks Shared for its service and offers one of its own."""

    name, title, about, api, order = "asker", "Asker", "a stand-in asking another plugin", "2.2", 921
    HOOKS = (*MachinePlugin.HOOKS, "lend")
    SERVICE_HOOKS = ("lend",)
    ASKS = (("shared", "serve_others", "what it serves"),)

    def present(self):
        return True

    def status(self):
        return {"present": True, "summary": "asks"}

    def lend(self):
        """What it lends the other plugins."""
        return {}


class Bot(PlatformPlugin):
    """A stand-in AI assistant, its key set and its plan serving: the platform asks it nothing by name."""

    KIND = "assistant"
    name, title, about, api = "bot", "A bot", "a stand-in assistant", "2.2"
    vendor, ICON, default_model, key_names = "Bots", "copilot", "bot-1", ("BOT_API_KEY",)

    def keys_set(self, settings):
        """Whether its key is set."""
        return True

    def served(self, settings):
        """Whether its key and its plan serve."""
        return True

    def free_note(self, settings):
        """Why its plan has no API access."""
        return ""


def _app(lines=None, **plugins) -> PlatformApp:
    machines = {n: p for n, p in plugins.items() if getattr(p, "KIND", "") == "machine"}
    assistants = {n: p for n, p in plugins.items() if getattr(p, "KIND", "") == "assistant"}
    log = lines.append if lines is not None else (lambda m: None)
    return PlatformApp(log=log, login=EnvironmentLogin(env={}), machines=machines, assistants=assistants,
                       settings=lambda: object())


def _get(app, path):
    return app.api(None, "GET", path, {}, None)[:2]


def _ask(app, name, hook, args=()):
    return app.api(None, "POST", f"/api/machines/{name}/ask", {}, {"hook": hook, "args": list(args)})[:2]


def _traffic(app, name) -> set[tuple[str, str]]:
    recent = app.connections(200)["recent"]
    return {(r["what"], r["kind"]) for r in recent if r["from"] == "platform" and r["to"] == name}


def _library_says() -> bool:
    """Whether this liminal-libs makes a plugin's Internal API (1.63.0: internal.py and the frame's plugin_internal)."""
    return app_mod.internal_mod is not None and callable(getattr(App, "plugin_internal", None)) \
        and callable(getattr(app_mod.internal_mod, "internal_of", None))


LIBRARY = pytest.mark.skipif(not _library_says(), reason="liminal-libs before 1.63.0: it makes no Internal API")


def _stand_in(monkeypatch, answer: dict | None = None, raises: Exception | None = None) -> list:
    """internal.py and the frame's plugin_internal stood in (a library before them, or theirs replaced for this test):
    what the platform hands them is noted; plugin_internal answers `answer` (one kept dict, as the frame keeps it)."""
    handed: list = []

    def reads_of(plugin, reads=(), tabs=None):
        handed.append(("reads_of", plugin.name, tuple(reads), tabs))
        said = tuple(h for h in getattr(type(plugin), "READ_HOOKS", ()) if h not in reads)
        return (*reads, *(t["hook"] for t in tabs or () if t["hook"] not in reads), *said)

    def plugin_internal(self, plugin, tabs=None):
        handed.append(("plugin_internal", plugin.name, tabs, self.askable(plugin), self.call_words(plugin),
                       [p.name for p in self.known_plugins()]))
        if raises is not None:
            raise raises
        return answer if answer is not None else {"v": 1, "name": plugin.name}

    monkeypatch.setattr(app_mod, "internal_mod", types.SimpleNamespace(reads_of=reads_of))
    monkeypatch.setattr(App, "plugin_internal", plugin_internal, raising=False)
    return handed


# -- the platform's own part, whatever the library ---------------------------------------------------------------

def test_a_plugin_never_takes_the_pages_own_tabs():
    """Main, External API and Internal API are the page's own, and "api" (the old address of External API) stays
    kept, so an address written before them never opens a plugin's own tab."""
    assert OWN_TABS == ("main", "api", "external", "internal")
    assert tabs_of(Shared()) == [{"id": "page", "title": "Its page", "hook": "page", "every": 3.0}]


def test_how_the_platform_is_asked_a_plugins_hooks():
    shared, asker, bot = Shared(), Asker(), Bot()
    app = _app(shared=shared, asker=asker, bot=bot)
    askable = app.askable(shared)
    assert askable == set(PlatformApp.asks(shared)) and {"refresh", "poke", "page", "serve_others", "status"} <= askable
    assert not askable & set(NOT_ASKED) and app.askable(bot) == set()  # an assistant is asked nothing by name
    assert app.known_plugins() == [shared, asker, bot]  # attached or not (none is, here)
    words = app.call_words(shared)
    # over HTTP, as the frame takes a write: from this machine, with the write header (else 403)
    header = f"with the header {WRITE_HEADER}: 1, from this machine"
    assert words == {"plugins": "self.app.ask('shared', hook, [arguments])",
                     "clients": f'POST /api/machines/shared/ask {{"hook": hook, "args": [arguments]}} {header}',
                     "jobs": 'POST /api/machines/shared/job {"action": "hook", "hook": hook, "args": [arguments]} '
                             f"{header}: one of its JOB_HOOKS, its lines then read from GET "
                             "/api/machines/shared/job?since=",
                     "terms": ASK_TERMS}
    assert "none of setup, settings, scan and run" in ASK_TERMS and "by position, in one list" in ASK_TERMS
    assert app.call_words(bot) == {"terms": "the platform asks an AI assistant nothing by name"}
    assert shared.asked == [] and json.dumps(words)  # nothing asked of it; words as JSON says them


def test_the_hooks_a_status_names_for_its_page_to_ask():
    status = Shared().status()
    before = json.dumps(status, sort_keys=True)
    assert page_asks(status) == ["poke", "refresh", "risky"]  # shallowest first: forms, actions, a table's move
    assert json.dumps(status, sort_keys=True) == before  # the status is not changed
    assert page_asks(None) == [] and page_asks([{"hook": "x"}]) == [] and page_asks("hook") == []
    assert (PAGE_ASKS_DEPTH, PAGE_ASKS_NODES) == (6, 2000)  # the bounds C-critique S3 gives the walk
    # the deepest the page reads one: a table's tasks' buttons (tables[0].tasks.actions[0].hook, five down)
    tasks = {"tables": [{"rows": [], "tasks": {"title": "Task", "actions": [{"hook": "start"}]}}]}
    assert page_asks(tasks) == ["start"]
    assert page_asks({"hook": "not a name", "forms": [{"hook": 7}, {"hook": "ok"}, {"hook": "ok"}]}) == ["ok"]
    deep: dict = {"hook": "d0"}
    at = deep
    for i in range(1, PAGE_ASKS_DEPTH + 3):  # dicts in dicts, each naming a hook
        at["more"] = {"hook": f"d{i}"}
        at = at["more"]
    assert page_asks(deep) == [f"d{i}" for i in range(PAGE_ASKS_DEPTH + 1)]  # PAGE_ASKS_DEPTH deep at the most
    many = {"rows": [{"hook": f"h{i}"} for i in range(5 * PAGE_ASKS_NODES)]}
    assert page_asks(many) == [f"h{i}" for i in range(PAGE_ASKS_EACH)]  # the first of a long list: more of the same
    wide = {"cells": list(range(100 * PAGE_ASKS_NODES)), "rows": [[{"x": 1}] * 50] * 500, "forms": [{"hook": "late"}]}
    assert page_asks(wide) == ["late"]  # a long table before them hides no form
    huge = {f"k{i}": [{"a": [{"b": [1]}]} for _ in range(PAGE_ASKS_EACH)] for i in range(PAGE_ASKS_EACH)}
    huge["forms"] = [{"hook": "beyond"}]  # past the first PAGE_ASKS_EACH values of the status itself
    assert page_asks(huge) == []  # and the walk ends, its dicts and lists PAGE_ASKS_NODES at the most
    lots = {k: [{"hook": f"{k}{i}"} for i in range(PAGE_ASKS_EACH)] for k in "abc"}
    assert len(page_asks(lots)) == MAX_PAGE_ASKS


def test_a_status_carries_what_the_library_makes_of_the_plugin(monkeypatch):
    """The platform's part with internal.py and the frame's plugin_internal stood in: it hands them its tabs as it keeps
    them, the hooks it asks by name, how it is asked and every plugin there is; the status gets a copy of the kept
    answer with the hooks its page asks, for a plugin disabled too; an assistant's names none."""
    kept = {"v": 1, "name": "shared", "hooks": [{"name": "poke"}]}
    handed = _stand_in(monkeypatch, kept)
    monkeypatch.setattr(app_mod, "facts", lambda: {"system": "a stand-in"})  # (Python's processor() may start uname)
    shared, asker, bot = Shared(), Asker(), Bot()
    app = _app(shared=shared, asker=asker, bot=bot)
    status, m = _get(app, "/api/machines/shared")
    assert status == 200 and m["internal"] == {**kept, "pageAsks": ["poke", "refresh", "risky"]}
    assert "pageAsks" not in kept  # the kept answer itself is never changed
    (_, name, tabs, askable, words, known) = next(h for h in handed if h[0] == "plugin_internal")
    assert (name, tabs, askable, words["plugins"], known) == ("shared", tabs_of(shared), set(PlatformApp.asks(shared)),
                                                              "self.app.ask('shared', hook, [arguments])",
                                                              ["shared", "asker", "bot"])
    a = app.assistant_status(bot)
    last = next(h for h in reversed(handed) if h[0] == "plugin_internal")
    assert a["internal"]["pageAsks"] == [] and last[1] == "bot" and last[3] == set()
    # disabled: its Internal API all the same, no status read, so no hook named for its page
    shared.asked.clear()
    assert app.set_enabled("shared", False)["internal"] == {**kept, "pageAsks": []} and shared.asked == []
    every = _get(app, "/api/status")[1]
    assert every["machines"]["shared"]["internal"]["name"] == "shared" and every["assistants"][0]["internal"]


def test_a_library_that_cannot_read_one_plugin_says_so_in_its_status(monkeypatch):
    """The library is there but fails on one plugin (its registry cannot say, a shape it does not know): its status says
    so (`internal` None, `internalError` in words: only a platform that has the library sends it, so its tab never
    tells it to restart), the rest of its status as it was; the trouble is logged once, never sent."""
    lines: list[str] = []
    _stand_in(monkeypatch, raises=RuntimeError("it cannot say"))
    shared, bot = Shared(), Bot()
    app = _app(lines, shared=shared, bot=bot)
    for _ in range(3):
        m = _get(app, "/api/machines/shared")[1]
        assert m["internal"] is None and m["apis"] == [] and m["tabs"] == tabs_of(Shared())
        assert m["internalError"] == ("What Shared shares with the platform could not be read: the platform's log "
                                      "says why.")
        assert "it cannot say" not in json.dumps(m) and "RuntimeError" not in json.dumps(m)  # the log's, not the page's
    said = [x for x in lines if "what shared shares could not be read" in x]
    assert said == ["platform: what shared shares could not be read: RuntimeError: it cannot say"]  # once
    a = app.assistant_status(bot)
    assert a["internal"] is None and a["internalError"].startswith("What A bot shares with the platform could not")
    # an answer that is not a plugin's Internal API is one the platform cannot say either
    _stand_in(monkeypatch, answer=["not", "a", "dict"])
    m = _get(app, "/api/machines/shared")[1]
    assert m["internal"] is None and m["internalError"].startswith("What Shared shares")


def test_without_the_librarys_internal_api_no_status_says_one(monkeypatch):
    """A liminal-libs before 1.63.0 (no internal.py; or a frame without plugin_internal): no status has `internal`,
    which the page reads as a platform that cannot say it yet, and the reads are the platform's own."""
    lines: list[str] = []
    shared, bot = Shared(), Bot()
    monkeypatch.setattr(app_mod, "internal_mod", None)
    app = _app(lines, shared=shared, bot=bot)
    assert "internal" not in _get(app, "/api/machines/shared")[1] and "internal" not in app.assistant_status(bot)
    assert PlatformApp.reads_of(shared) == (*READS, "page")
    assert _ask(app, "shared", "refresh") == (200, {"answer": {"fresh": True}})
    assert "platform: shared asked refresh" in lines  # said to only read, but no library to say so: logged as ever
    monkeypatch.setattr(app_mod, "internal_mod", types.SimpleNamespace(reads_of=lambda *a: ("present",)))
    monkeypatch.delattr(App, "plugin_internal", raising=False)  # internal.py, but a frame without plugin_internal
    assert "internal" not in _get(app, "/api/machines/shared")[1]
    assert not any("could not be read" in x for x in lines)  # a library before it is no trouble: nothing to log


def test_a_hook_said_to_only_read_is_asked_as_one(monkeypatch):
    """READ_HOOKS through the library's reads_of (stood in here): asked without a line in the platform's log and noted
    as a read in who talks to whom, as a tab's hook is; anything else asked by name is logged and noted as an ask. A
    reads_of that cannot say leaves the platform's own reads."""
    lines: list[str] = []
    handed = _stand_in(monkeypatch)
    shared = Shared()
    app = _app(lines, shared=shared)
    assert PlatformApp.reads_of(shared) == (*READS, "page", "refresh")
    assert ("reads_of", "shared", READS, tabs_of(shared)) in handed  # its reads, and the tabs as it keeps them
    assert _ask(app, "shared", "refresh") == (200, {"answer": {"fresh": True}})
    assert _ask(app, "shared", "poke") == (200, {"answer": {"poked": True}})
    assert not any("asked refresh" in x for x in lines) and "platform: shared asked poke" in lines
    assert {("refresh", "read"), ("poke", "ask")} <= _traffic(app, "shared")

    def cannot(*args):
        raise RuntimeError("no")

    monkeypatch.setattr(app_mod, "internal_mod", types.SimpleNamespace(reads_of=cannot))
    assert PlatformApp.reads_of(shared) == (*READS, "page")
    monkeypatch.setattr(app_mod, "internal_mod", types.SimpleNamespace(reads_of=lambda *a: ["present"]))
    assert PlatformApp.reads_of(shared) == (*READS, "page")  # not a tuple of names: the platform's own


# -- CALLS and ATTRIBUTES are what the platform's code does -------------------------------------------------------

PLUGIN_NAMES = {"m", "p", "a", "machine", "plugin"}  # the names the platform's code gives a plugin object
INDIRECT = {"instances": "liminal_libs.docker.instances asks each machine plugin", "api_facts": "sources.apis.facts_of",
            "attach": "the frame's attach", "detach": "the frame's detach",
            "rpc": "0.34.0's route: the plugin's own ask, by the name its RPC_HOOK gives",
            "signal": "0.35.0's stop: liminal_libs.lifecycle.deliver_all tells each plugin attached here"}


def _plugin(node) -> bool:
    """Whether an expression is a plugin object as the platform's code names one: one of PLUGIN_NAMES, or
    `self.machine` (a job's plugin)."""
    return (isinstance(node, ast.Name) and node.id in PLUGIN_NAMES) or (
        isinstance(node, ast.Attribute) and node.attr == "machine" and isinstance(node.value, ast.Name)
        and node.value.id == "self")


def _looked_up(node) -> str | None:
    """The name of a getattr(<plugin>, "...") (with or without a default), else None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" \
            and len(node.args) > 1 and _plugin(node.args[0]) and isinstance(node.args[1], ast.Constant) \
            and isinstance(node.args[1].value, str):
        return node.args[1].value
    return None


def _taken() -> tuple[dict[str, set[int]], set[str]]:
    """What liminal_platform/app.py reads or calls on a plugin, by name, with the lines (an attribute of a plugin, and
    the name of a getattr of one), and the names among them it calls: `m.name(...)`, `getattr(m, "name")(...)`, or a
    name bound to `getattr(m, "name", None)` in a function and called there (`made = getattr(m, "terminal_title",
    None)`, then `made()`). A name only looked up (`callable(getattr(m, "chosen", None))`) is read, never called."""
    tree = ast.parse(inspect.getsource(app_mod))
    out: dict[str, set[int]] = {}
    called: set[str] = set()
    for node in ast.walk(tree):
        if (name := _looked_up(node)) is not None:
            out.setdefault(name, set()).add(node.lineno)
        if isinstance(node, ast.Attribute) and _plugin(node.value):
            out.setdefault(node.attr, set()).add(node.lineno)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and _plugin(func.value):
                called.add(func.attr)
            elif (name := _looked_up(func)) is not None:
                called.add(name)
    for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        bound = {t.id: name for n in ast.walk(fn) if isinstance(n, ast.Assign) and len(n.targets) == 1
                 for t in n.targets if isinstance(t, ast.Name) and (name := _looked_up(n.value)) is not None}
        called |= {bound[n.func.id] for n in ast.walk(fn)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in bound}
    return out, called


def test_calls_and_attributes_are_what_the_platforms_code_does():
    """B3 of the plan's critique: the platform's own Internal API says what its code calls and reads on its plugins, so
    the two are held to its source. Every name the code takes of a plugin is declared; every declared name is one the
    code takes, but the four it takes through another's code (INDIRECT); and each is declared as what it is: in CALLS
    a name its code calls, in ATTRIBUTES (read, never called) one it only reads or looks up."""
    assert set(CALLS) == set(ATTRIBUTES) == {"machine", "assistant"}
    calls = {n for kind in CALLS for n in CALLS[kind]}
    attributes = {n for kind in ATTRIBUTES for n in ATTRIBUTES[kind]}
    declared = calls | attributes
    taken, called = _taken()
    assert {"present", "status", "terminal_title", "SECTION", "TABS", "JOB_HOOKS", "served", "vendor"} <= set(taken)
    assert {"present", "status", "terminal_title", "settings_changed", "update_packages", "served"} <= called
    # 0.31.0's, declared since 0.32.0: the stop told to each machine plugin (a call, through a name bound to its
    # getattr), its AI group and the hooks whose job takes a cancel (reads)
    assert {"app_stopping", "GROUP", "CANCEL_HOOKS"} <= set(taken) and "app_stopping" in called
    assert "app_stopping" in CALLS["machine"] and {"GROUP", "CANCEL_HOOKS"} <= set(ATTRIBUTES["machine"])
    # 0.34.0's: the hook a route's requests are handed to and the two words of who may ask a hook (read, never called),
    # and that hook itself, asked through the plugin's own ask by the name RPC_HOOK gives (INDIRECT)
    words = {"RPC_HOOK", "PLUGIN_ONLY_HOOKS", "PAGE_ONLY_HOOKS"}
    assert words <= set(taken) and words <= set(ATTRIBUTES["machine"]) and not words & called
    assert "rpc" in CALLS["machine"] and "rpc" not in taken and "/rpc" in CALLS["machine"]["rpc"]
    missing = {n: sorted(lines) for n, lines in taken.items() if n not in declared}
    assert not missing, f"read or called on a plugin, not in CALLS or ATTRIBUTES: {missing}"
    assert declared - set(taken) == set(INDIRECT), "declared, but the platform's code never takes it"
    only_read = {n: sorted(taken[n]) for n in calls - set(INDIRECT) - called}
    assert not only_read, f"in CALLS, but the platform's code only reads or looks it up (ATTRIBUTES): {only_read}"
    also_called = {n: sorted(taken[n]) for n in attributes & called}
    assert not also_called, f"in ATTRIBUTES, but the platform's code calls it (CALLS): {also_called}"
    for kind in CALLS:
        assert not set(CALLS[kind]) & set(ATTRIBUTES[kind]), kind  # called, or only read: one or the other
        assert all(isinstance(how, str) and how.strip() for how in CALLS[kind].values()), kind
        assert len(set(ATTRIBUTES[kind])) == len(ATTRIBUTES[kind]), kind
    # an assistant is asked nothing by name; a machine plugin is asked any other hook through ask
    assert "ask" in CALLS["machine"] and "ask" not in CALLS["assistant"]
    assert PlatformApp.CALLS is CALLS and PlatformApp.ATTRIBUTES is ATTRIBUTES


# -- what the library makes of a plugin, through the platform (liminal-libs 1.63.0) -------------------------------

def _rows(internal: dict) -> dict[str, dict]:
    return {h["name"]: h for h in internal["hooks"]}


@LIBRARY
def test_the_status_says_what_the_plugin_shares_as_the_platform_uses_it():
    shared, asker = Shared(), Asker()
    app = _app(shared=shared, asker=asker)
    status, m = _get(app, "/api/machines/shared")
    assert status == 200 and json.dumps(m["internal"])
    d = m["internal"]
    assert d["name"] == "shared" and d["builtOn"]["class"] == "MachinePlugin"
    # the standard interface of its base first, layer by layer, then its own hooks
    assert [(s["class"], s["hooks"]) for s in d["standard"]] == [
        ("MachinePlugin", ["present", "status", "setup", "run", "instances"]), ("Plugin", ["scan", "settings"])]
    rows = _rows(d)
    assert [h["name"] for h in d["hooks"]] == [*MachinePlugin.HOOKS, "refresh", "poke", "risky", "fetch", "page",
                                               "serve_others", "check"]
    assert (rows["present"]["layer"], rows["scan"]["layer"], rows["poke"]["layer"]) == ("MachinePlugin", "Plugin", "")
    assert rows["present"]["answered"] == "itself" and rows["setup"]["answered"] == "" and d["left"] == \
        ["setup", "run", "instances", "scan", "settings"]
    assert (d["counts"]["standard"], d["counts"]["own"], d["counts"]["left"]) == (7, 7, 5)
    # who uses each, from what the platform's code calls (CALLS), its tabs, its services and what it asks by name
    users = {n: r["users"] for n, r in rows.items()}
    assert users == {"present": "app", "status": "both", "setup": "app", "run": "", "instances": "app", "scan": "",
                     "settings": "", "refresh": "named", "poke": "named", "risky": "named", "fetch": "named",
                     "page": "app", "serve_others": "plugins", "check": "app"}
    for name in ("present", "status", "setup", "check"):  # run: the command line's alone (0.34.1)
        assert rows[name]["how"] == CALLS["machine"][name], name
    assert {n for n, r in rows.items() if r["askable"]} == set(PlatformApp.asks(shared))
    # the kinds of call: a read it says it is, a change asked twice, a job, a tab's page, a service
    assert (rows["refresh"]["kind"], rows["refresh"]["reads"]) == ("read", True)
    assert (rows["poke"]["kind"], rows["poke"]["reads"]) == ("change", False)
    assert rows["risky"]["twice"] == ["accept_risk"] and rows["risky"]["args"] == "(what, accept_risk=False)"
    assert rows["fetch"]["job"] is True and rows["fetch"]["kind"] == "job"
    assert (rows["page"]["kind"], rows["page"]["tab"], rows["page"]["every"]) == ("tab", "page", 3.0)
    assert rows["serve_others"]["kind"] == "service" and rows["serve_others"]["askedBy"] == ["asker"]
    assert rows["poke"]["line"] == "Something changed on this machine."
    # how it is called, its settings and what it keeps, what it asks of others and whether they offer it here
    assert d["calls"] == app.call_words(shared)
    assert d["settings"][0]["variable"] == "SHARED_API_KEY" and d["settings"][0]["pair"] == "shared-api-key"
    assert [(k["variable"], k["about"]) for k in d["keeps"]] == [("SHARED_GROUPS", "the groups of its rules")]
    asks = {(a["plugin"], a["hook"]): a for a in d["asks"]}
    assert asks[("asker", "lend")]["here"] == "offered" and asks[("", "serving")]["here"] == "no plugin offers it here"
    assert [t["id"] for t in d["tabs"]] == ["page"]
    assert set(m["internal"]["pageAsks"]) == {"poke", "refresh", "risky"}
    # nothing of it was asked for that but its status; the other plugin's Internal API says who asks its service
    assert shared.asked == ["status"]
    lend = _rows(_get(app, "/api/machines/asker")[1]["internal"])["lend"]
    assert lend["users"] == "plugins" and lend["askedBy"] == ["shared"]


@LIBRARY
def test_disabled_it_still_says_what_it_shares_and_is_asked_nothing():
    shared = Shared()
    app = _app(shared=shared)
    on = _get(app, "/api/machines/shared")[1]["internal"]
    shared.asked.clear()
    off = app.set_enabled("shared", False)
    assert off["state"] == "disabled" and off["internal"]["pageAsks"] == [] and shared.asked == []
    assert {k: v for k, v in off["internal"].items() if k != "pageAsks"} == \
        {k: v for k, v in on.items() if k != "pageAsks"}  # the same, kept for the platform's life


@LIBRARY
def test_a_hook_said_to_only_read_is_asked_as_a_read():
    lines: list[str] = []
    shared = Shared()
    app = _app(lines, shared=shared)
    reads = PlatformApp.reads_of(shared)
    assert reads[:len(READS)] == READS and {"page", "refresh"} <= set(reads)
    assert "poke" not in PlatformApp.reads_of(shared) and "fetch" not in PlatformApp.reads_of(shared)
    assert _ask(app, "shared", "refresh") == (200, {"answer": {"fresh": True}})
    assert _ask(app, "shared", "poke") == (200, {"answer": {"poked": True}})
    assert not any("asked refresh" in x for x in lines) and "platform: shared asked poke" in lines
    assert {("refresh", "read"), ("poke", "ask")} <= _traffic(app, "shared")
    assert PlatformApp.reads_of(MachinePlugin()) == READS  # a plugin that says nothing of its own: as before


@LIBRARY
def test_an_ai_assistant_is_asked_nothing_by_name_here():
    bot = Bot()
    app = _app(bot=bot)
    d = app.assistant_status(bot)["internal"]
    assert d["calls"] == {"terms": "the platform asks an AI assistant nothing by name"} and d["pageAsks"] == []
    assert all(r["users"] == "" and not r["askable"] for r in d["hooks"])  # its hooks are not used here
    also = {r["name"]: r for r in d["also"]}
    assert also["served"]["how"] == CALLS["assistant"]["served"]
    assert also["keys_set"]["how"] == CALLS["assistant"]["keys_set"]
