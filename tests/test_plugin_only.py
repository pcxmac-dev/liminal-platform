"""0.34.0 (liminal-libs 1.66.0's PLUGIN_ONLY_HOOKS and apps/asking.py; the user, 2026-11-18: "now i need an MCP plugin
for platform, basically a protocol plugin that mediates MCP connections to resources by local AI agents"): a hook a
plugin says only another plugin asks (the MCP plugin's: an agent for a harness, a token for the harness's window) is
never asked over HTTP. POST /api/machines/{name}/ask and /job refuse it (403) whatever the login says, and its page is
never offered it: the platform's asks, its Internal API's askable and a status's asks leave it out, a tab's hook among
them. Another plugin asks it through the platform (self.app.ask), and the platform names that plugin as the call's
asker, which the hook reads (never an argument), from the page's ask of that plugin too. Its own plugin asking it is
refused, and so is a plugin that took the page's name (it asks as no one). A plugin that says neither word is asked as
before.

Stand-in plugins; the app asked directly, as its server asks it: nothing is served, no port is opened, no process is
started (conftest's no_outside fails a test that does)."""
from __future__ import annotations

import pytest

from liminal_libs.apps import Refused
from liminal_libs.apps.tabs import Tab
from liminal_libs.machines import MachinePlugin

from conftest import Box
from conftest import api_answer as _api

from liminal_platform.app import PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside")

try:  # who asks, as liminal-libs 1.66.0 hands it over
    from liminal_libs.apps import asking
except ImportError:  # an older library hands no one over: the platform's gates hold all the same
    asking = None

UNSAID = "no asker handed over here"


def _asker():
    return asking.asker() if asking is not None else UNSAID


def _named(plugin: str) -> str:
    """Who a hook sees asking when `plugin` asks it through the platform."""
    return plugin if asking is not None else UNSAID


class Minter(MachinePlugin):
    """A stand-in whose `mint` and `batch` (a job) only other plugins ask, as the MCP plugin's launch tokens; `look` is
    in neither word."""

    name, title, about, api, order = "minter", "A minter", "a stand-in handing out tokens", "2.2", 950
    HOOKS = (*MachinePlugin.HOOKS, "mint", "batch", "look", "mint_my_own")
    JOB_HOOKS = ("batch",)
    PLUGIN_ONLY_HOOKS = ("mint", "batch")

    def __init__(self):
        self.asked: list[tuple] = []

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def mint(self):
        """A token for the asking plugin's window."""
        self.asked.append(("mint", _asker()))
        return {"token": "made", "for": _asker()}

    def batch(self, log=None):
        """Tokens made as a job."""
        self.asked.append(("batch", _asker()))
        return {"said": "made", "ok": True}

    def look(self):
        """A read in neither word."""
        self.asked.append(("look", _asker()))
        return {"seen": True}

    def mint_my_own(self):
        """Its own plugin-only hook, asked of itself through the platform: refused."""
        return self.app.ask("minter", "mint", [])


class Harness(MachinePlugin):
    """A stand-in harness: a token for its window, asked of the minter through the platform."""

    name, title, about, api, order = "harness", "A harness", "a stand-in harness", "2.2", 951
    HOOKS = (*MachinePlugin.HOOKS, "open_window")

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def open_window(self):
        """A window opened, with a token of its own."""
        return self.app.ask("minter", "mint", [])


class Paged(Harness):
    """A plugin that took the page's name: it asks as no one."""

    name, title = "page", "Not the page"


class Tabbed(Minter):
    """One whose tab names a hook only other plugins ask (internal.problems says so): its page never asks it all the
    same."""

    name = "tabbed"
    TABS = (Tab("minted", "Minted", "mint", 5.0),)


def _apps(*plugins, lines=None):
    log = lines.append if lines is not None else (lambda m: None)
    app = PlatformApp(log=log, machines={p.name: p for p in plugins}, assistants={})
    for p in plugins:
        app.attach(p)  # each plugin's code is its own: a plugin that asks is named (traffic.actor)
    return app


def test_over_http_it_is_refused_whatever_the_login_says():
    minter = Minter()
    app = _apps(minter)
    seen: list = []
    app.present = lambda handler: seen.append(handler) or True  # you are there: it is refused all the same
    words = "minter's mint is asked only by another plugin, never from a page or by a program."
    try:
        status, said = _api(app, "POST", "/api/machines/minter/ask", {"hook": "mint", "args": []})
        assert status == 403 and said["words"].startswith("minter's mint is asked only by another plugin")
        if asking is not None:
            assert said == {"error": words, "words": words}
        status, said = _api(app, "POST", "/api/machines/minter/job", {"action": "hook", "hook": "batch", "args": []})
        assert status == 403 and said["words"].startswith("minter's batch is asked only by another plugin")
        assert minter.asked == [] and "minter" not in app._setups and seen == []  # nothing asked, the login neither
        assert _api(app, "POST", "/api/machines/minter/ask", {"hook": "look", "args": []}) == (
            200, {"answer": {"seen": True}})  # a hook in neither word: asked as ever
    finally:
        app.stop()


def test_its_page_is_never_offered_it():
    minter, tabbed = Minter(), Tabbed()
    app = _apps(minter, tabbed)
    try:
        asks = PlatformApp.asks(minter)
        assert "look" in asks and not {"mint", "batch"} & set(asks)
        assert app.askable(minter) == set(asks)
        assert not {"mint", "batch"} & set(_api(app, "GET", "/api/machines/minter")[1]["asks"])
        assert {"mint", "batch"} <= set(PlatformApp.hooks(minter))  # it answers them: to other plugins
        assert "mint" not in PlatformApp.asks(tabbed)  # a tab's hook too, when it is one only other plugins ask
        assert _api(app, "POST", "/api/machines/tabbed/ask", {"hook": "mint", "args": []})[0] == 403
        assert tabbed.asked == []
    finally:
        app.stop()


def test_another_plugin_asks_it_through_the_platform_and_is_named_its_asker():
    minter, harness, lines = Minter(), Harness(), []
    app = _apps(minter, harness, lines=lines)
    try:
        assert harness.open_window() == {"token": "made", "for": _named("harness")}  # of its own accord
        status, out = _api(app, "POST", "/api/machines/harness/ask", {"hook": "open_window", "args": []})
        assert (status, out) == (200, {"answer": {"token": "made", "for": _named("harness")}})  # its page asked it to
        assert minter.asked == [("mint", _named("harness"))] * 2  # never the page: the plugin that asked
        said = {(r["from"], r["to"], r["kind"], r["what"], r["ok"]) for r in app.traffic.recent()}
        assert ("harness", "minter", "ask", "mint", True) in said
        assert "platform: minter asked mint" in lines  # an ask, logged by its name as ever; never its token
    finally:
        app.stop()


def test_its_own_plugin_and_one_that_took_the_pages_name_are_refused():
    minter, paged = Minter(), Paged()
    app = _apps(minter, paged)
    try:
        with pytest.raises(Refused) as own:
            minter.mint_my_own()
        assert own.value.status == 403 and "minter itself" in own.value.words
        with pytest.raises(Refused) as page:
            paged.open_window()
        assert page.value.status == 403 and page.value.words.startswith("minter's mint is asked only by another plugin")
        assert minter.asked == []
    finally:
        app.stop()


def test_a_plugin_that_says_neither_word_is_asked_as_before():
    box, harness = Box(), Harness()
    app = _apps(box, harness)
    try:
        assert _api(app, "POST", "/api/machines/box/ask", {"hook": "status", "args": []})[0] == 200
        assert app.ask("box", "status", [])["present"] is True  # the platform's own code, naming no one: as before
        assert PlatformApp.asks(box) == ["present", "status", "instances"]
    finally:
        app.stop()


class Wide(Minter):
    """One whose PLUGIN_ONLY_HOOKS also names hooks the platform asks by no name: its route's hook and two of
    NOT_ASKED (a command; its setup)."""

    name = "wide"
    RPC_HOOK = "rpc"
    HOOKS = (*Minter.HOOKS, "rpc")
    PLUGIN_ONLY_HOOKS = ("mint", "rpc", "run", "setup")

    def rpc(self, method, headers=None, body=None, gone=None):
        """An agent's request, its route's alone."""
        self.asked.append(("rpc", _asker()))
        return 200, {}, {}

    def run(self, *command, **options):
        """A command, a client's alone (POST .../run)."""
        self.asked.append(("run", command))
        return "ran"

    def setup(self, log=print, steps=None):
        """Its setup, its route's alone (POST .../setup)."""
        self.asked.append(("setup", steps))
        return []


class Reacher(Harness):
    """A stand-in plugin asking the wide plugin's hooks by name through the platform."""

    name = "reacher"

    def reach(self, hook, args):
        """One of the wide plugin's hooks, asked through the platform."""
        return self.app.ask("wide", hook, args)


def test_the_word_never_opens_a_hook_the_platform_asks_by_no_name():
    """The reviewer's finding (2026-11-19): PLUGIN_ONLY_HOOKS narrows who asks a hook, yet naming in it the hook a
    plugin's route hands requests to (RPC_HOOK), or one of NOT_ASKED (a command, its setup, its settings, a scan),
    let every other plugin ask it by name, as no plugin could before. Those stay refused (400); a hook the platform
    asks by name stays another plugin's to ask."""
    wide, reacher = Wide(), Reacher()
    app = _apps(wide, reacher)
    try:
        for hook, args in (("rpc", ["POST", {}, {}, None]), ("run", ["echo", "hi"]), ("setup", [])):
            with pytest.raises(Refused) as refused:
                reacher.reach(hook, args)
            assert refused.value.status == 400 and refused.value.reason.startswith(f"wide is not asked {hook!r} here")
        assert wide.asked == []
        assert reacher.reach("mint", []) == {"token": "made", "for": _named("reacher")}
        assert wide.asked == [("mint", _named("reacher"))]
    finally:
        app.stop()
