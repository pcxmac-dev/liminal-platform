"""0.34.0 (liminal-libs 1.66.0's PAGE_ONLY_HOOKS and apps/asking.py; the user, 2026-11-18: "now i need an MCP plugin
for platform, basically a protocol plugin that mediates MCP connections to resources by local AI agents"): a hook a
plugin says only its page asks (the MCP plugin's decisions: a call allowed, a grant, a token shown once) is never asked
by another plugin. A plugin's ask of it through the platform is refused (403), in the library's words, and noted as an
ask that failed. Over HTTP (POST /api/machines/{name}/ask, and /job for one of its JOB_HOOKS) it is asked when the
login says the person at the browser is there (App.present True) or when the platform holds no login (None), and
refused (401) when it says they are not (False). The page is then its asker, for the hook and inside the job's own
thread. A thread that was handed no asker is refused it, and so is every hook of a plugin whose words cannot be read. A
plugin that says neither word is asked as before, and the login is asked nothing for it.

Stand-in plugins; the app asked directly, as its server asks it: nothing is served, no port is opened, no process is
started (conftest's no_outside fails a test that does). Each thread is joined; none is left to luck."""
from __future__ import annotations

import threading

import pytest

from liminal_libs.apps import App, Refused
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
PAGE = asking.PAGE if asking is not None else UNSAID  # who a hook sees asking when the page asks it
PROVES = callable(getattr(App, "present", None))  # liminal-libs 1.66.0: the login says whether you are there


def _asker():
    return asking.asker() if asking is not None else UNSAID


class Decider(MachinePlugin):
    """A stand-in whose decisions only its page asks: `decide` by name, `approve` as a job; `look` is in neither word:
    a read it declares (0.42.0: a hook declared for no one is its page's alone, closed by default: test_closed_default).
    Each notes who was asking when it ran, and in which thread."""

    name, title, about, api, order = "decider", "A decider", "a stand-in with decisions", "2.2", 940
    HOOKS = (*MachinePlugin.HOOKS, "decide", "approve", "look")
    READ_HOOKS = ("look",)
    JOB_HOOKS = ("approve",)
    PAGE_ONLY_HOOKS = ("decide", "approve")

    def __init__(self):
        self.asked: list[tuple] = []

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def _note(self, hook):
        self.asked.append((hook, _asker(), threading.current_thread().name))

    def decide(self, ticket, answer="once"):
        """A call waiting for you answered."""
        self._note("decide")
        return {"said": f"{ticket}: {answer}", "ok": True}

    def approve(self, what, log=None):
        """An approval, run as a job."""
        self._note("approve")
        if log is not None:
            log(f"approving {what}")
        return {"said": f"{what} approved", "ok": True}

    def look(self):
        """A read in neither word."""
        self._note("look")
        return {"seen": True}


class Agent(MachinePlugin):
    """A stand-in plugin asking the decider's decision through the platform, as its page asked it to or from a job of
    its own: refused either way, its refusal handed back as it came."""

    name, title, about, api, order = "agent", "An agent's plugin", "a stand-in asking another", "2.2", 941
    HOOKS = (*MachinePlugin.HOOKS, "decide_for_me", "relay")
    JOB_HOOKS = ("relay",)

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def decide_for_me(self):
        """The decider's decision, asked through the platform."""
        try:
            return {"answer": self.app.ask("decider", "decide", ["t1", "once"])}
        except Refused as e:
            return {"refused": int(e.status), "words": getattr(e, "words", e.reason)}

    def relay(self, log=None):
        """The same, asked from inside a job of its own, which its page started."""
        return self.decide_for_me()


def _apps(*plugins, lines=None):
    log = lines.append if lines is not None else (lambda m: None)
    app = PlatformApp(log=log, machines={p.name: p for p in plugins}, assistants={})
    for p in plugins:
        app.attach(p)  # each plugin's code is its own: a plugin that asks is named (traffic.actor)
    return app


def _ended(app, name: str) -> dict:
    """The job just started for `name`, waited for: its state as its panel reads it."""
    job = app._setups[name]
    job.thread.join(10)
    assert not job.thread.is_alive(), "the job never ended"
    return job.describe()


def test_a_plugin_asking_it_through_the_platform_is_refused_and_noted_as_a_failed_ask():
    decider, agent = Decider(), Agent()
    app = _apps(decider, agent)
    words = "decider's decide is asked only from its page, never by another plugin: agent asked it."
    try:
        status, out = _api(app, "POST", "/api/machines/agent/ask", {"hook": "decide_for_me", "args": []})
        assert status == 200 and out["answer"] == {"refused": 403, "words": words}  # asked from the page: the agent's
        assert agent.decide_for_me() == {"refused": 403, "words": words}  # the plugin asking of its own accord
        assert _api(app, "POST", "/api/machines/agent/job", {"action": "hook", "hook": "relay", "args": []})[0] == 202
        assert _ended(app, "agent")["answer"] == {"refused": 403, "words": words}  # from a job its page started
        assert decider.asked == []  # never asked
        failed = [r for r in app.traffic.recent() if r["from"] == "agent" and r["to"] == "decider"]
        assert failed and {(r["kind"], r["what"], r["ok"]) for r in failed} == {("ask", "decide: refused", False)}
    finally:
        app.stop()


@pytest.mark.skipif(not PROVES, reason="this liminal-libs has no App.present (1.66.0 has)")
def test_over_http_it_is_refused_when_the_login_says_you_are_not_there():
    decider, lines = Decider(), []
    app = _apps(decider, lines=lines)
    lines.clear()  # (its attach, said)
    seen: list = []
    request = object()  # the request as the server hands it over: what the login is shown
    app.present = lambda handler: seen.append(handler) or False
    words = ("A decider's decide is asked only from its page, and the platform's login does not show that you are "
             "there: sign in on the platform's page, then ask again.")
    try:
        status, said, *_ = app.api(request, "POST", "/api/machines/decider/ask", {}, {"hook": "decide", "args": ["t"]})
        assert (status, said) == (401, {"error": words, "words": words}) and seen == [request]
        job = {"action": "hook", "hook": "approve", "args": ["x"]}
        status, said, *_ = app.api(request, "POST", "/api/machines/decider/job", {}, job)
        assert status == 401 and said["words"].startswith("A decider's approve is asked only from its page")
        assert decider.asked == [] and "decider" not in app._setups and lines == []  # no job begun, nothing logged

        def fails(handler):
            raise RuntimeError("the proof could not be read")

        app.present = fails  # a proof that fails proves nothing
        assert _api(app, "POST", "/api/machines/decider/ask", {"hook": "decide", "args": ["t"]})[0] == 401
        assert decider.asked == []
    finally:
        app.stop()


def test_over_http_it_is_asked_when_the_login_says_you_are_there_or_there_is_no_login():
    decider = Decider()
    app = _apps(decider)
    try:
        # the tests' platform holds no login (LIMINAL_PLATFORM_LOGIN_URL none): None, nothing to prove
        assert _api(app, "POST", "/api/machines/decider/ask", {"hook": "decide", "args": ["t1"]}) == (
            200, {"answer": {"said": "t1: once", "ok": True}})
        app.present = lambda handler: True
        assert _api(app, "POST", "/api/machines/decider/ask", {"hook": "decide", "args": ["t2", "deny"]})[0] == 200
        job = {"action": "hook", "hook": "approve", "args": ["x"]}
        assert _api(app, "POST", "/api/machines/decider/job", job)[0] == 202
        assert _ended(app, "decider")["answer"] == {"said": "x approved", "ok": True}
        main = threading.current_thread().name
        # the page is the asker, for the hook and inside the job's own thread, handed over where it was started
        assert decider.asked == [("decide", PAGE, main), ("decide", PAGE, main), ("approve", PAGE, "setup-decider")]
        assert app._setups["decider"].asker == (PAGE if asking is not None else None)
    finally:
        app.stop()


def test_the_login_is_asked_nothing_for_a_hook_in_neither_word_nor_for_a_plugin_that_says_neither():
    decider, box = Decider(), Box()
    app = _apps(decider, box)
    seen: list = []
    app.present = lambda handler: seen.append(handler) or False
    try:
        assert _api(app, "POST", "/api/machines/decider/ask", {"hook": "look", "args": []}) == (
            200, {"answer": {"seen": True}})
        assert _api(app, "POST", "/api/machines/box/ask", {"hook": "status", "args": []})[0] == 200
        assert seen == []  # asked as before: the login is not asked
        assert decider.asked == [("look", PAGE, threading.current_thread().name)]
        assert "decide" in PlatformApp.asks(decider) and "approve" in PlatformApp.asks(decider)  # its page asks them
    finally:
        app.stop()


@pytest.mark.skipif(asking is None, reason="this liminal-libs hands no asker over (1.66.0 does)")
def test_a_thread_handed_no_asker_is_refused_it():
    decider = Decider()
    app = _apps(decider)
    out: dict = {}

    def unhanded():  # a thread the platform's code starts without a hand-over: it has no asker
        try:
            app.ask("decider", "decide", ["t1"])
        except Refused as e:
            out["refused"] = (int(e.status), e.words)

    try:
        with asking.asking(asking.PAGE):  # the page asks in this thread: a thread started here does not inherit it
            thread = threading.Thread(target=unhanded)
            thread.start()
            thread.join(10)
        assert not thread.is_alive()
        assert out["refused"] == (403, "decider's decide is asked only from its page. This ask names no asker: neither "
                                       "the page nor a plugin.")
        assert decider.asked == []
    finally:
        app.stop()


class Paged(Agent):
    """A plugin that took the page's name: it asks as no one, never as the page."""

    name, title = "page", "Not the page"


def test_a_plugin_that_took_the_pages_name_is_refused_it_as_any_plugin_is():
    decider, paged = Decider(), Paged()
    app = _apps(decider, paged)
    try:
        said = paged.decide_for_me()
        assert said["refused"] == 403 and said["words"].startswith("decider's decide is asked only from its page")
        assert decider.asked == []
    finally:
        app.stop()


class Unreadable(Decider):
    """One whose word is no tuple of hooks' names: who may ask its hooks cannot be read."""

    name = "unreadable"
    PAGE_ONLY_HOOKS = "decide"


def test_every_hook_of_a_plugin_whose_words_cannot_be_read_is_refused():
    plugin = Unreadable()
    app = _apps(plugin)
    try:
        for hook, args in (("look", []), ("decide", ["t"])):
            status, said = _api(app, "POST", "/api/machines/unreadable/ask", {"hook": hook, "args": args})
            assert status == 403 and "who may ask its hooks cannot be read" in said["words"], hook
        assert plugin.asked == []
        assert _api(app, "GET", "/api/machines/unreadable")[0] == 200  # its status is read as ever: no ask by name
    finally:
        app.stop()


def test_on_a_library_before_the_two_words_the_platform_holds_them_itself(monkeypatch):
    """A liminal-libs before 1.66.0 has neither apps/asking.py, internal.py's reading of the two words nor App.present:
    the platform reads the words from the plugin itself and holds them all the same. Over HTTP a hook only other
    plugins ask is refused and one only its page asks is asked (there is no proof to ask); a plugin's ask of one only
    its page asks is refused, and of one only other plugins ask, asked; words it cannot read refuse every hook."""
    from test_plugin_only import Harness, Minter

    import liminal_platform.app as app_module

    monkeypatch.setattr(app_module, "asking_mod", None)
    monkeypatch.setattr(app_module, "internal_mod", None)
    monkeypatch.delattr(App, "present", raising=False)
    decider, agent, minter, harness, unreadable = Decider(), Agent(), Minter(), Harness(), Unreadable()
    app = _apps(decider, agent, minter, harness, unreadable)
    try:
        assert _api(app, "POST", "/api/machines/decider/ask", {"hook": "decide", "args": ["t1"]})[0] == 200
        said = agent.decide_for_me()
        assert said == {"refused": 403, "words": "decider's decide is asked only from its page, never by another "
                                                 "plugin: agent asked it."}
        assert [a[0] for a in decider.asked] == ["decide"]
        status, said = _api(app, "POST", "/api/machines/minter/ask", {"hook": "mint", "args": []})
        assert status == 403 and said["words"] == ("minter's mint is asked only by another plugin, never from a page, "
                                                   "by a program or by minter itself.")
        assert harness.open_window()["token"] == "made"
        with pytest.raises(Refused) as own:
            minter.mint_my_own()
        assert own.value.status == 403
        assert "mint" not in PlatformApp.asks(minter) and "decide" in PlatformApp.asks(decider)
        status, said = _api(app, "POST", "/api/machines/unreadable/ask", {"hook": "look", "args": []})
        assert status == 403 and said["words"] == ("unreadable: who may ask its hooks cannot be read (PAGE_ONLY_HOOKS "
                                                   "must be a tuple of str), so it is asked nothing")
    finally:
        app.stop()
