"""0.42.0, closed by default (liminal-libs 1.107.0; the user, 2026-11-26: "Yes, closed by default"). A security sweep
found that a plugin's change hooks were open to any program on the machine: the platform hands an ask over HTTP to a
hook as its page, and asked its login only for a hook the plugin named in PAGE_ONLY_HOOKS. Now a hook a plugin answers
and declares for no one is its page's alone, as if that word named it: refused to another plugin (403), and over HTTP
asked only when the login says a person is there (401 otherwise). Over HTTP the login is asked for every hook but one
the plugin declares a read (its READ_HOOKS, a tab of its own): a service other plugins ask, asked here by name, is a
person's too. A plugin written before the words keeps its page, which asks as the page.

Stand-in plugins; the app asked directly, as its server asks it: nothing is served, no port is opened, no process is
started (conftest's no_outside fails a test that does)."""
from __future__ import annotations

import pytest

from liminal_libs.apps import Refused
from liminal_libs.machines import MachinePlugin

from conftest import api_answer as _api

import liminal_platform.app as app_module
from liminal_platform.app import PlatformApp, person_alone

pytestmark = pytest.mark.usefixtures("no_outside")

try:
    from liminal_libs import internal
    from liminal_libs.apps import asking
except ImportError:  # an older library
    internal = asking = None
CLOSED = callable(getattr(internal, "audience", None))  # liminal-libs 1.107.0: the closed default
needs_closed = pytest.mark.skipif(not CLOSED, reason="this liminal-libs has no closed default (1.107.0 has)")


class Old(MachinePlugin):
    """A plugin written before the words: `apply` changes something, `view` is what its page draws; it declares
    neither. `look` is a read it declares, `lend` a service other plugins ask."""

    name, title, about, api, order = "old", "An old plugin", "a stand-in that declares little", "2.2", 950
    HOOKS = (*MachinePlugin.HOOKS, "apply", "view", "look", "lend")
    READ_HOOKS = ("look",)
    SERVICE_HOOKS = ("lend",)

    def __init__(self):
        self.asked: list[tuple] = []

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def _note(self, hook):
        self.asked.append((hook, asking.asker() if asking is not None else None))

    def apply(self, what):
        """A change it never declared."""
        self._note("apply")
        return {"said": f"{what} applied", "ok": True}

    def view(self):
        """What its page draws, never declared either."""
        self._note("view")
        return {"rows": []}

    def look(self):
        """A read it declares."""
        self._note("look")
        return {"seen": True}

    def lend(self, what):
        """A service other plugins ask."""
        self._note("lend")
        return {"lent": what}


class Other(MachinePlugin):
    """Another plugin asking Old's hooks through the platform."""

    name, title, about, api, order = "other", "Another plugin", "a stand-in asking another", "2.2", 951
    HOOKS = (*MachinePlugin.HOOKS, "wants")
    READ_HOOKS = ("wants",)

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def wants(self, hook, *args):
        """One of Old's hooks, asked through the platform."""
        try:
            return {"answer": self.app.ask("old", hook, list(args))}
        except Refused as e:
            return {"refused": int(e.status), "words": getattr(e, "words", e.reason)}


def _app(*plugins, lines=None):
    app = PlatformApp(log=lines.append if lines is not None else (lambda m: None),
                      machines={p.name: p for p in plugins}, assistants={})
    for p in plugins:
        app.attach(p)
    return app


@needs_closed
def test_over_http_an_undeclared_hook_waits_for_the_logins_word_that_you_are_there():
    old, lines = Old(), []
    app = _app(old, lines=lines)
    lines.clear()
    seen: list = []
    request = object()
    app.present = lambda handler: seen.append(handler) or False
    try:
        for hook, args in (("apply", ["x"]), ("view", [])):
            status, said, *_ = app.api(request, "POST", "/api/machines/old/ask", {}, {"hook": hook, "args": args})
            assert status == 401 and said["words"] == (
                f"An old plugin's {hook} is asked only from its page, and the platform's login does not show that you "
                "are there: sign in on the platform's page, then ask again."), hook
        assert old.asked == [] and lines == [] and seen == [request, request]  # nothing asked, nothing logged
        app.present = lambda handler: True  # a person shown to be there: its page works as it did
        assert _api(app, "POST", "/api/machines/old/ask", {"hook": "apply", "args": ["x"]}) == (
            200, {"answer": {"said": "x applied", "ok": True}})
        assert _api(app, "POST", "/api/machines/old/ask", {"hook": "view", "args": []}) == (200, {"answer": {"rows": []}})
        app.present = lambda handler: None  # a platform that holds no login asks as before
        assert _api(app, "POST", "/api/machines/old/ask", {"hook": "apply", "args": ["y"]})[0] == 200
        assert old.asked == [("apply", "page"), ("view", "page"), ("apply", "page")]
        assert {"apply", "view", "look", "lend"} <= set(PlatformApp.asks(old))  # its page is offered them all
    finally:
        app.stop()


@needs_closed
def test_a_read_it_declares_is_asked_without_the_login_and_a_service_asked_by_name_is_a_persons():
    old = Old()
    app = _app(old)
    seen: list = []
    app.present = lambda handler: seen.append(handler) or False
    try:
        assert _api(app, "POST", "/api/machines/old/ask", {"hook": "look", "args": []}) == (200, {"answer": {"seen": True}})
        assert _api(app, "POST", "/api/machines/old/ask", {"hook": "status", "args": []})[0] == 200
        assert seen == []  # reads: the login is asked nothing
        status, said = _api(app, "POST", "/api/machines/old/ask", {"hook": "lend", "args": ["x"]})
        assert status == 401 and said["words"].startswith("An old plugin's lend is asked only from its page")
        assert len(seen) == 1 and old.asked == [("look", "page")]
        assert (person_alone(old, "look"), person_alone(old, "status"), person_alone(old, "lend"),
                person_alone(old, "apply"), person_alone(old, "view")) == (False, False, True, True, True)
    finally:
        app.stop()


@needs_closed
def test_another_plugin_is_refused_an_undeclared_hook_and_still_asks_a_service_and_a_read():
    old, other = Old(), Other()
    app = _app(old, other)
    try:
        said = other.wants("apply", "x")
        assert said["refused"] == 403 and said["words"].startswith(
            "old's apply is asked only from its page: old declares it for no one else.")
        assert said["words"].endswith("other asked it.") and "SERVICE_HOOKS" in said["words"]
        assert other.wants("view")["refused"] == 403
        assert other.wants("lend", "x") == {"answer": {"lent": "x"}} and other.wants("look") == {"answer": {"seen": True}}
        assert old.asked == [("lend", "other"), ("look", "other")]
        failed = [r for r in app.traffic.recent() if r["from"] == "other" and r["to"] == "old" and not r["ok"]]
        assert {r["what"] for r in failed} == {"apply: refused", "view: refused"}  # noted as asks that failed
        # asked from the page for the other plugin, the asker is still that plugin: refused all the same
        status, out = _api(app, "POST", "/api/machines/other/ask", {"hook": "wants", "args": ["apply", "x"]})
        assert status == 200 and out["answer"]["refused"] == 403
        # the platform's own code, handed no asker, is refused it too
        with pytest.raises(Refused) as refused:
            app.ask("old", "apply", ["z"])
        assert refused.value.status == 403 and "names no asker" in refused.value.words
        assert [a for a in old.asked if a[0] == "apply"] == []
    finally:
        app.stop()


@needs_closed
def test_a_job_of_an_undeclared_hook_is_started_only_by_a_person_at_the_page():
    class Jobs(Old):
        name, title = "jobs", "A plugin with a job"
        JOB_HOOKS = ("apply",)

        def apply(self, what, log=None):
            """A job it never declared for anyone."""
            self._note("apply")
            return {"said": f"{what} applied", "ok": True}

    jobs = Jobs()
    app = _app(jobs)
    body = {"action": "hook", "hook": "apply", "args": ["x"]}
    try:
        app.present = lambda handler: False
        status, said = _api(app, "POST", "/api/machines/jobs/job", body)
        assert status == 401 and "jobs" not in app._setups and jobs.asked == []
        app.present = lambda handler: True
        assert _api(app, "POST", "/api/machines/jobs/job", body)[0] == 202
        job = app._setups["jobs"]
        job.thread.join(10)
        assert not job.thread.is_alive() and jobs.asked == [("apply", "page")]  # the page, in the job's own thread
    finally:
        app.stop()


@needs_closed
def test_its_internal_api_tab_is_handed_each_hooks_audience():
    """The follow-up: the tab drew an undeclared hook as a plain change anyone may ask by name. The platform's status
    carries what the library reads of each hook (internal_of's `audience` and `declared`), which the library's
    internal.js draws: read, plugins, page, and page by default."""
    old = Old()
    app = _app(old)
    try:
        status, got = _api(app, "GET", "/api/machines/old")
        assert status == 200
        rows = {h["name"]: (h["audience"], h["declared"]) for h in got["internal"]["hooks"]}
        assert rows["apply"] == ("page", False) and rows["view"] == ("page", False)  # closed by default
        assert rows["look"] == ("read", True) and rows["status"] == ("read", True) and rows["lend"] == ("plugin", True)
        page = (PlatformApp.STATIC / "platform.js").read_text(encoding="utf-8")
        assert "window.LiminalInternal" in page  # drawn by the library's internal.js, which says the audience
        from pathlib import Path

        js = (Path(internal.__file__).parent / "ui" / "static" / "internal.js").read_text(encoding="utf-8")
        for words in ("asked by anyone here", "asked by other plugins and its page",
                      "asked only from its page: declared for no one"):
            assert words in js, words
    finally:
        app.stop()


def test_with_a_library_before_the_closed_default_the_login_is_asked_for_page_only_hooks_alone(monkeypatch):
    """liminal-libs before 1.107.0 has no internal.audience: the platform asks its login as it did (0.34.0)."""
    class Before:
        plugin_only = staticmethod(lambda plugin: tuple(getattr(plugin, "PLUGIN_ONLY_HOOKS", ())))
        page_only = staticmethod(lambda plugin: tuple(getattr(plugin, "PAGE_ONLY_HOOKS", ())))

    class Paged(Old):
        name = "paged"
        PAGE_ONLY_HOOKS = ("apply",)

    monkeypatch.setattr(app_module, "internal_mod", Before)
    assert (person_alone(Paged(), "apply"), person_alone(Paged(), "view"), person_alone(Paged(), "lend"),
            person_alone(Paged(), "look")) == (True, False, False, False)
    monkeypatch.setattr(app_module, "internal_mod", None)
    assert person_alone(Paged(), "apply") is True and person_alone(Paged(), "view") is False


@needs_closed
def test_words_that_cannot_be_read_open_nothing():
    class Unreadable(Old):
        name = "unreadable"
        READ_HOOKS = "look"

    assert person_alone(Unreadable(), "look") is True and person_alone(Unreadable(), "apply") is True
