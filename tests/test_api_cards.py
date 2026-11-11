"""Each plugin's page shows the API it attaches to (0.20.0; liminal-libs 1.49.0, plugin API 2.2; the user, 2026-11-11:
"each plugin should reflect the the API its attached to, and present links that provide documentation ... it should also
expose more of what the API is about")."""
from __future__ import annotations

from liminal_libs.machines import MachinePlugin as Machine
from liminal_libs.sources.apis import Api, Area, Call, Link

from conftest import _port
from liminal_platform.app import PlatformApp
from test_app import _call

API = Api(name="Stand-in API", maker="Stand-in", about="What the stand-in cloud offers, over HTTPS.", kind="rest",
          base="https://api.example.org/v1", version="v1", auth="a bearer token", limits="100 a minute",
          links=(Link("Reference", "https://docs.example.org/api", "reference"),),
          areas=(Area("Servers", "the account's servers", covered="read"), Area("Billing", "the invoices")),
          calls=(Call("GET /v1/servers", "lists the servers", "Servers", used="the Servers table"),
                 Call("POST /v1/servers", "makes a server", "Servers", writes=True, costs=True)),
          verified="2026-11-11")


class Cloudy(Machine):
    name, title, about, api, order = "cloudy", "Cloudy", "a stand-in cloud", "2.2", 903
    apis = (API,)

    def present(self):
        return True

    def status(self):
        return {"present": True, "summary": "two servers"}

    def api_facts(self):
        return {"Stand-in API": {"Requests": "3 made", "Left this minute": 97}}


class Older(Machine):
    name, title, about, api, order = "older", "Older", "written for 2.1", "2.1", 904

    def present(self):
        return True

    def status(self):
        return {"present": True, "summary": "fine"}


def test_a_plugins_api_reaches_its_page_with_what_it_learned():
    app = PlatformApp(log=lambda m: None, machines={"cloudy": Cloudy(), "older": Older()}, assistants={})
    port = _port(app.start(0))
    try:
        m = _call(port, "GET", "/api/machines/cloudy")[1]
        assert m["pluginApi"] == "2.2" and [a["name"] for a in m["apis"]] == ["Stand-in API"]
        card = m["apis"][0]
        assert card["docs"] == "https://docs.example.org/api" and card["counts"] == {"areas": 2, "covered": 1, "calls": 2, "used": 1}
        assert m["apiFacts"] == {"Stand-in API": {"Requests": "3 made", "Left this minute": "97"}}
        old = _call(port, "GET", "/api/machines/older")[1]
        assert old["pluginApi"] == "2.1" and old["apis"] == [] and old["apiFacts"] == {}
        page = _call(port, "GET", "/")[1]
        assert page.index(b'src="charts.js"') < page.index(b'src="apis.js"') < page.index(b'src="platform.js"')
        js = _call(port, "GET", "/platform.js")[1]
        assert b"function apiCard(p)" in js and b"window.LiminalApis.html(p.apis, p.apiFacts" in js
        assert b"setupLog(m) : '') + apiCard(m);" in js and b"${apiCard(a)}" in js  # after what it already shows
        assert b"if (html !== drawnApis[m.name])" in js  # a refresh draws it again only when it changed
        lib = _call(port, "GET", "/apis.js")[1]
        assert b"window.LiminalApis" in lib  # the library's, served beside the platform's own files
    finally:
        app.stop()


def test_a_change_is_logged_without_what_was_filled_in():
    """0.20.1: the audit before any cloud key went in found a private key pasted into an SSH-key form written to
    platform.log; a change asked of a plugin is logged by its name and how many arguments it had, never their values."""
    said = []

    class Keyed(Machine):
        name, title, about, api, order = "keyed", "Keyed", "a stand-in with a key form", "2.2", 905
        apis = (API,)
        HOOKS = (*Machine.HOOKS, "add_key")

        def present(self):
            return True

        def status(self):
            return {"present": True, "summary": "ready"}

        def add_key(self, name, key):
            return {"added": name}

    app = PlatformApp(log=said.append, machines={"keyed": Keyed()}, assistants={})
    port = _port(app.start(0))
    try:
        secret = "-----BEGIN OPENSSH PRIVATE KEY----- AAAAsecretbody"
        status, out = _call(port, "POST", "/api/machines/keyed/ask", {"hook": "add_key", "args": ["laptop", secret]})
        assert status == 200 and out == {"answer": {"added": "laptop"}}
        assert "platform: keyed asked add_key (2 arguments)" in said and not any("secretbody" in s or "laptop" in s for s in said)
    finally:
        app.stop()


def test_the_command_lines_app_is_a_one_shot_and_serves_is_not(monkeypatch):
    """0.20.1: the command line's status and machine commands make a one-shot app, whose plugins start no background
    work (a cloud's account reads, a Dynamic DNS pass); serve's app is not one."""
    from liminal_platform import cli

    made = []
    monkeypatch.setattr(cli.PlatformApp, "attach_plugins", lambda self, plugins=None: made.append(self) or [])
    assert cli._app(lambda m: None).once is True and made[-1].once is True
    assert cli._app(lambda m: None, once=False).once is False
    assert PlatformApp(log=lambda m: None, machines={}, assistants={}).once is False
