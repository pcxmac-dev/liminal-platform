"""0.34.0 (the user, 2026-11-18: "now i need an MCP plugin for platform, basically a protocol plugin that mediates MCP
connections to resources by local AI agents"): POST, GET and DELETE /api/machines/{name}/rpc, the platform's own port
for an agent's requests. A plugin whose RPC_HOOK names one of its hooks (liminal-libs 1.66.0's ProtocolPlugin: rpc) is
handed each request whole: its method, the headers of the route's allow-list (named in lowercase; no other header, a
cookie or the write header among them, is handed over), its JSON body and gone(), whether the agent has closed its
connection, read without waiting. Its answer is sent as it is: a status from 200 to 599, a JSON object or nothing, and
the headers of the answer's allow-list alone. Refused: 404 for a plugin with no such hook, 409 while it is disabled,
503 while the platform stops, 431 past the headers' bounds, 502 for a hook that fails or answers what cannot be sent.
The hook is never asked by name, never offered to the page, and asked as no one's ask. The route is not counted as
under way (a call it holds must not hold up the stop: the plugin's app_stopping ends it), and leaves no line in the
platform's log per request.

Stand-ins: the plugins, a request's headers and its connection (no socket is made), and the select module where a
connection is looked at. The app is asked directly, as its server asks it: nothing is served, no port is opened, no
process is started (conftest's no_outside fails a test that does). One test runs the library's own ProtocolPlugin
through the platform's routes, where the library has it."""
from __future__ import annotations

import io
import json
import socket
import threading
from email.message import Message

import pytest

from liminal_libs.apps import EnvironmentLogin, Refused
from liminal_libs.apps.app import make_handler
from liminal_libs.machines import MachinePlugin

from conftest import Box
from conftest import api_answer as _api

import liminal_platform.app as app_module
from liminal_platform.app import (RPC_ANSWER_HEADERS, RPC_HEADER_CHARS, RPC_HEADERS, RPC_METHODS, RPC_PARAMS,
                                  STOPPING, PlatformApp, gone_of, rpc_answer, rpc_headers)

pytestmark = pytest.mark.usefixtures("no_outside")

try:  # who asks, as liminal-libs 1.66.0 hands it over (the route names no one)
    from liminal_libs.apps import asking
except ImportError:  # an older library hands no one over
    asking = None

PATH = "/api/machines/gate/rpc"
CALL = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}


def _asker():
    return asking.asker() if asking is not None else "no asker handed over here"


class Gate(MachinePlugin):
    """A stand-in protocol plugin: its route's hook notes what it is handed and who was asking then, and answers what
    the test sets; a request can be held inside it until the test lets it go, or until the platform tells the plugin
    that it stops (as liminal-libs 1.66.0's ProtocolPlugin ends the calls it holds)."""

    name, title, about, api, order = "gate", "A gate", "a stand-in protocol plugin", "2.2", 930
    SECTION, GROUP = "ai", "protocol"
    RPC_HOOK = "rpc"
    HOOKS = (*MachinePlugin.HOOKS, "rpc", "clients", "poke")
    READ_HOOKS = ("clients",)

    def __init__(self):
        self.handed: list[tuple] = []
        self.askers: list = []
        self.answer = (200, {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}, {"Mcp-Session-Id": "s1"})
        self.fails: BaseException | None = None
        self.hold = False
        self.inside, self.go = threading.Event(), threading.Event()
        self.told: list[str] = []

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "a gate", "why": ""}

    def rpc(self, method, headers=None, body=None, gone=None):
        """One request of an agent, handed whole by the platform's route."""
        self.handed.append((method, headers, body, gone))
        self.askers.append(_asker())
        if self.hold:
            self.inside.set()
            assert self.go.wait(20), "the request was never let go"
        if self.fails is not None:
            raise self.fails
        return self.answer

    def clients(self):
        """Its agents, as its page reads them."""
        return []

    def poke(self):
        """A change its page asks by name."""
        return {"said": "poked", "ok": True}

    def app_stopping(self):
        self.told.append("told")
        self.go.set()  # (the base ends every call it holds: here, the one the test holds)


class Handler:
    """A request as the platform's server hands it over (no server runs): its headers as http.server parses them (an
    email Message: a header sent twice is there twice), and its connection, a stand-in (no socket is made)."""

    def __init__(self, headers=(), connection=None):
        self.headers = Message()
        for name, value in headers:
            self.headers[name] = value
        self.connection = connection


class Connection:
    """A request's connection, stood in: what a peek at it finds (b"" once its agent has closed it) or raises, each
    peek noted with its flags. Nothing is ever read off it."""

    def __init__(self, waiting: bytes = b"", fails: BaseException | None = None):
        self.waiting, self.fails, self.peeks = waiting, fails, []

    def fileno(self):
        return 3

    def recv(self, size, flags=0):
        self.peeks.append((size, flags))
        if self.fails is not None:
            raise self.fails
        return self.waiting[:size]


class Select:
    """The select module stood in (app_module.select): whether a connection is readable now, as the test says, each
    look noted with its timeout. `poll`: the poll a POSIX system has; else select's alone, as on Windows."""

    POLLIN, POLLPRI = 1, 2

    def __init__(self, readable=False, *, poll=False, fails: BaseException | None = None):
        self.readable, self.fails, self.looks = readable, fails, []
        if poll:
            self.poll = self._poll

    def select(self, rlist, wlist, xlist, timeout):
        self.looks.append(("select", len(rlist), timeout))
        if self.fails is not None:
            raise self.fails
        return (list(rlist) if self.readable else [], [], [])

    def _poll(self):
        outer, watched = self, []

        class Poll:
            def register(self, fd, mask):
                watched.append((fd, mask))

            def poll(self, timeout):
                outer.looks.append(("poll", len(watched), timeout))
                if outer.fails is not None:
                    raise outer.fails
                return [(fd, outer.POLLIN) for fd, _ in watched] if outer.readable else []

        return Poll()


def _app(*plugins, lines=None, login=None) -> PlatformApp:
    log = lines.append if lines is not None else (lambda m: None)
    return PlatformApp(log=log, login=login, machines={p.name: p for p in plugins}, assistants={})


def _rpc(app, method="POST", handler=None, body=None, path=PATH):
    """The route asked as the platform's server asks it: (status, body, headers); a refusal as its status, its words
    and no headers."""
    try:
        status, data, *rest = app.api(handler, method, path, {}, None if method == "GET" else (body or {}))
    except Refused as e:
        return e.status, {"error": e.reason}, {}
    return status, data, (rest[0] if rest else {})


# -- the request handed over whole ------------------------------------------------------------------------------------
def test_each_method_is_handed_to_the_hook_whole_and_its_answer_sent_as_it_is():
    gate = Gate()
    app = _app(gate)
    try:
        assert RPC_METHODS == ("POST", "GET", "DELETE")
        sent = _rpc(app, "POST", Handler([("Mcp-Method", "tools/list")]), CALL)
        assert sent == (200, {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}, {"Mcp-Session-Id": "s1"})
        gate.answer = (405, None, {"Allow": "POST, DELETE"})  # MCP's GET, as the plugin answers it
        assert _rpc(app, "GET", Handler()) == (405, None, {"Allow": "POST, DELETE"})
        gate.answer = (202, None, {})  # a notification or a response: 202, with no body (liminal-libs 1.66.0)
        assert _rpc(app, "DELETE", Handler([("Mcp-Session-Id", "s1")])) == (202, None, {})
        methods = [(m, h, b) for m, h, b, _ in gate.handed]
        assert methods == [("POST", {"mcp-method": "tools/list"}, CALL), ("GET", {}, None),
                           ("DELETE", {"mcp-session-id": "s1"}, {})]  # a GET has no body; an empty write's is {}
        assert all(callable(g) for *_, g in gate.handed)
        # asked directly, as the tests ask the app: no headers, and no connection to have gone
        assert _rpc(app, "POST", None, CALL)[0] == 202 and gate.handed[-1][1] == {} and gate.handed[-1][3]() is False
        assert _rpc(app, "PUT", Handler(), CALL)[0] == 404  # no other method is the route's
    finally:
        app.stop()


def test_the_headers_handed_over_are_the_routes_allow_list_alone():
    gate = Gate()
    app = _app(gate)
    sent = [("Host", "127.0.0.1:8775"), ("Authorization", "Bearer t0k3n"), ("Cookie", "liminal_session=abc"),
            ("X-Liminal-Charts", "1"), ("Mcp-Session-Id", "s1"), ("MCP-Protocol-Version", "2025-11-25"),
            ("Mcp-Method", "tools/call"), ("Mcp-Name", "git__status"), ("Accept", "application/json"),
            ("Content-Type", "application/json"), ("User-Agent", "an agent"), ("Last-Event-ID", "7"),
            ("Mcp-Param-Region", "eu"), ("X-Forwarded-For", "203.0.113.9"), ("Origin", "null"),
            ("accept", "text/event-stream")]  # Accept sent twice: its values joined, as RFC 9110 joins them
    try:
        assert _rpc(app, "POST", Handler(sent), CALL)[0] == 200
        heard = gate.handed[0][1]
        assert heard == {"authorization": "Bearer t0k3n", "mcp-session-id": "s1", "mcp-protocol-version": "2025-11-25",
                         "mcp-method": "tools/call", "mcp-name": "git__status",
                         "accept": "application/json, text/event-stream", "content-type": "application/json",
                         "user-agent": "an agent", "last-event-id": "7", "mcp-param-region": "eu"}
        assert set(heard) - {"mcp-param-region"} == set(RPC_HEADERS)
        assert rpc_headers(Handler([("Cookie", "x"), ("Host", "localhost")])) == {} and rpc_headers(None) == {}
    finally:
        app.stop()


def test_past_the_headers_bounds_a_request_is_refused_before_the_plugin_is_asked():
    gate = Gate()
    app = _app(gate)
    try:
        params = [(f"Mcp-Param-P{i}", str(i)) for i in range(RPC_PARAMS)]
        assert _rpc(app, "POST", Handler(params), CALL)[0] == 200 and len(gate.handed[0][1]) == RPC_PARAMS
        gate.handed.clear()
        status, said, _ = _rpc(app, "POST", Handler([*params, ("Mcp-Param-One-More", "x")]), CALL)
        assert status == 431 and said == {"error": f"a request here carries {RPC_PARAMS} mcp-param-* headers at the "
                                                   "most"}
        assert _rpc(app, "POST", Handler([("Mcp-Name", "x" * RPC_HEADER_CHARS)]), CALL)[0] == 200
        gate.handed.clear()
        status, said, _ = _rpc(app, "POST", Handler([("Mcp-Name", "x" * (RPC_HEADER_CHARS + 1))]), CALL)
        assert status == 431 and said["error"] == ("a header's value here is 4,096 characters at the most: mcp-name's "
                                                   "is longer")
        twice = [("Accept", "a" * 2048), ("Accept", "b" * 2048)]  # joined, the two are past it: refused too
        assert _rpc(app, "POST", Handler(twice), CALL)[0] == 431
        long_cookie = [("Cookie", "c" * (RPC_HEADER_CHARS * 2))]  # not handed over, so not held to the bound
        assert _rpc(app, "POST", Handler(long_cookie), CALL)[0] == 200
        assert len(gate.handed) == 1  # none of those refused reached the plugin
    finally:
        app.stop()


# -- gone() ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("poll", [False, True], ids=["select", "poll"])
def test_gone_says_whether_the_agent_has_closed_its_connection_and_never_waits(monkeypatch, poll):
    cases = [  # (readable, what a peek finds or raises, gone)
        (False, b"", False),  # nothing to read: open, and nothing peeked at
        (True, b"", True),  # readable at its end: closed
        (True, b"{", False),  # readable with a byte waiting (a client that sent more): open, the byte left there
        (True, ConnectionResetError(10054, "reset"), True),
        (True, OSError(9, "closed here"), True),
        (True, BlockingIOError(), False),
        (True, TimeoutError(), False),
    ]
    for readable, found, gone in cases:
        looks = Select(readable, poll=poll)
        monkeypatch.setattr(app_module, "select", looks)
        connection = Connection(found if isinstance(found, bytes) else b"",
                                None if isinstance(found, bytes) else found)
        assert gone_of(Handler(connection=connection))() is gone, (readable, found)
        assert looks.looks == [("poll" if poll else "select", 1, 0)]  # looked at once, waiting for nothing
        assert connection.peeks == ([(1, socket.MSG_PEEK)] if readable else [])  # one byte, peeked at alone
    broken = Select(fails=ValueError("file descriptor cannot be a negative integer"), poll=poll)
    monkeypatch.setattr(app_module, "select", broken)
    assert gone_of(Handler(connection=Connection()))() is True  # a connection that cannot be looked at any more
    assert gone_of(Handler())() is False and gone_of(None)() is False  # no connection: nothing has gone


def test_the_hook_is_handed_the_requests_own_gone(monkeypatch):
    gate = Gate()
    app = _app(gate)
    looks = Select(readable=True)
    monkeypatch.setattr(app_module, "select", looks)
    try:
        closed, open_ = Connection(b""), Connection(b"x")
        assert _rpc(app, "POST", Handler(connection=closed), CALL)[0] == 200
        assert _rpc(app, "POST", Handler(connection=open_), CALL)[0] == 200
        assert looks.looks == []  # handed over, not asked: the plugin asks it while it holds a call
        assert [g() for *_, g in gate.handed] == [True, False]
    finally:
        app.stop()


# -- the answer ------------------------------------------------------------------------------------------------------
def test_the_answers_headers_are_the_allow_list_alone_each_one_line_of_text():
    gate = Gate()
    app = _app(gate)
    try:
        gate.answer = (401, {"error": "no bearer token"}, {
            "www-authenticate": "Bearer", "MCP-PROTOCOL-VERSION": "2025-11-25", "Retry-After": 12,
            "Set-Cookie": "liminal_session=stolen", "Content-Type": "text/html", "Location": "/elsewhere",
            "Allow": "POST\r\nSet-Cookie: x=1", "Mcp-Session-Id": "s" * (RPC_HEADER_CHARS + 1)})
        status, data, headers = _rpc(app, "POST", Handler(), CALL)
        assert (status, data) == (401, {"error": "no bearer token"})
        assert headers == {"WWW-Authenticate": "Bearer", "MCP-Protocol-Version": "2025-11-25", "Retry-After": "12"}
        assert set(headers) <= set(RPC_ANSWER_HEADERS)  # spelled as the route spells them
        assert rpc_answer((204, None), "A gate", "rpc") == (204, None, {})  # a pair: no headers
        assert rpc_answer((200, {}, {"Allow": True, 7: "x", "Allow ": "GET"}), "A gate", "rpc") == (200, {}, {
            "Allow": "GET"})  # a word that is no text, a name that is not one: left out
    finally:
        app.stop()


def test_an_answer_that_cannot_be_sent_or_a_hook_that_fails_is_refused_in_words():
    gate = Gate()
    app = _app(gate)
    words = ("A gate's rpc answered what the route cannot send: (a status from 200 to 599, a JSON object or nothing, "
             "its headers)")
    try:
        for answer in ((199, {}, {}), (600, {}, {}), ("200", {}, {}), (True, {}, {}), (200, [1, 2], {}),
                       (200, "text", {}), (200, {}, [("Allow", "POST")]), (200,), [200, {}, {}], None, "ok"):
            gate.answer = answer
            assert _rpc(app, "POST", Handler(), CALL) == (502, {"error": words}, {}), answer
        gate.fails = RuntimeError("the agent's token was t0k3n-secret")
        status, said, _ = _rpc(app, "POST", Handler(), CALL)
        assert (status, said) == (502, {"error": "A gate could not answer: its rpc failed (RuntimeError)"})
        assert "t0k3n" not in json.dumps(said)  # its own words are kept out: a request's may hold its token
    finally:
        app.stop()


# -- what the agent reads: the frame's own handler, driven in memory ------------------------------------------------
class Wire:
    """A request's connection as the frame's handler reads and writes it, in memory: the request's bytes read from a
    buffer, the answer's bytes kept. No socket is made: nothing is served, no port is used."""

    def __init__(self, raw: bytes):
        self.raw, self.sent = raw, bytearray()

    def makefile(self, mode, buffering=-1):
        return io.BufferedReader(io.BytesIO(self.raw))

    def sendall(self, data):
        self.sent += bytes(data)

    def fileno(self):
        return -1


def _wire(app, method="POST", body=b"", path=PATH):
    """What an agent reads for one request, the frame's real handler answering it (make_handler: the frame's checks,
    the route, web.send_json): (its status, its headers by lowercase name, its body's bytes, what the handler raised).
    The server would only print what the handler raised: the agent then reads nothing at all."""
    lines = [f"{method} {path} HTTP/1.1", "Host: 127.0.0.1:8775", "X-Liminal-Charts: 1",
             "Content-Type: application/json", *([f"Content-Length: {len(body)}"] if method != "GET" else [])]
    wire = Wire(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body)
    raised = None
    try:
        make_handler(app)(wire, ("127.0.0.1", 50123), None)
    except Exception as e:  # noqa: BLE001 - what the server's thread would see
        raised = e
    head, _, rest = bytes(wire.sent).partition(b"\r\n\r\n")
    first, *fields = head.decode("latin-1").split("\r\n")
    named = {k.strip().lower(): v.strip() for k, _, v in (f.partition(":") for f in fields)}
    return (int(first.split()[1]) if first else None), named, rest, raised


class Unsayable(dict):
    """A body that cannot even say its items: JSON's writer raises what it raises."""

    def items(self):
        raise RuntimeError("cannot say")


class Echo(Gate):
    """A stand-in whose answer echoes the request's id, as every JSON-RPC answer does."""

    name = "echo"

    def rpc(self, method, headers=None, body=None, gone=None):
        """One request, its id echoed."""
        self.handed.append((method, headers, body, gone))
        return 200, {"jsonrpc": "2.0", "id": (body or {}).get("id"), "result": {}}, {}


def test_an_answer_whose_body_is_not_json_is_refused_and_the_agent_still_reads_an_answer():
    """The reviewer's finding (2026-11-19): a body the frame cannot send as JSON (NaN or Infinity in it, a set, bytes,
    a loop) left the agent with no answer at all. The frame's send failed after the route returned, and the
    connection just closed. It is refused in words (502), and the agent reads that."""
    gate = Gate()
    app = _app(gate)
    loop: dict = {}
    loop["again"] = loop
    try:
        for body in ({"result": float("nan")}, {"result": float("-inf")}, {"result": {"a set"}}, {"result": b"x"},
                     loop, Unsayable(result=1)):
            gate.answer = (200, body, {"Mcp-Session-Id": "s1"})
            status, said, headers = _rpc(app, "POST", Handler(), CALL)
            assert status == 502 and headers == {}, body
            assert said["error"].startswith("A gate's rpc answered a body that is not JSON ("), body
        gate.answer = (200, {"jsonrpc": "2.0", "id": 1, "result": {"x": float("nan")}}, {"Mcp-Session-Id": "s1"})
        status, headers, sent, raised = _wire(app, body=json.dumps(CALL).encode())
        assert raised is None and status == 502 and headers["content-type"] == "application/json"
        assert json.loads(sent) == {"error": "A gate's rpc answered a body that is not JSON (ValueError): nothing of "
                                             "it was sent"}
        gate.answer = (200, {"jsonrpc": "2.0", "id": 1, "result": {}}, {"Mcp-Session-Id": "s1"})
        status, headers, sent, raised = _wire(app, body=json.dumps(CALL).encode())  # a JSON one: sent as ever
        assert (status, headers["mcp-session-id"], json.loads(sent), raised) == (200, "s1", gate.answer[1], None)
    finally:
        app.stop()


def test_a_request_body_holding_nan_or_infinity_is_refused_before_the_plugin_is_asked():
    """The reviewer's finding (2026-11-19): the frame's JSON reader takes NaN and Infinity, which JSON does not have.
    A JSON-RPC answer echoes the request's id, so a request whose id was NaN got no answer at all. Such a body is
    refused (400) before the plugin is asked, in words the agent reads."""
    echo = Echo()
    app = _app(echo)
    words = "the body is not JSON: NaN and Infinity are not JSON numbers"
    try:
        for value in (float("nan"), float("inf"), float("-inf")):
            assert _rpc(app, "POST", Handler(), {**CALL, "id": value}, path="/api/machines/echo/rpc") == (
                400, {"error": words}, {})
        assert echo.handed == []
        for raw in (b'{"jsonrpc": "2.0", "id": NaN, "method": "ping"}', b'{"id": 1, "params": {"x": [-Infinity]}}'):
            status, _, sent, raised = _wire(app, body=raw, path="/api/machines/echo/rpc")
            assert (status, json.loads(sent), raised) == (400, {"error": words}, None), raw
        assert echo.handed == []
        status, _, sent, raised = _wire(app, body=b'{"jsonrpc": "2.0", "id": 7, "method": "ping"}',
                                        path="/api/machines/echo/rpc")
        assert (status, json.loads(sent)["id"], raised) == (200, 7, None) and len(echo.handed) == 1
    finally:
        app.stop()


def test_an_answer_with_no_body_is_a_204_never_a_205_or_a_304_and_a_204_never_has_one():
    """The reviewer's finding (2026-11-19): a 204, a 205 and a 304 never have a body (RFC 9110). A 204 with a body went
    out with its JSON after it, and a 205 or a 304 with "null". Each is refused in words (502); a 204 with nothing is
    sent as it is."""
    gate = Gate()
    app = _app(gate)
    try:
        gate.answer = (204, {"result": "x"}, {})
        assert _rpc(app, "POST", Handler(), CALL) == (502, {"error": "A gate's rpc answered a 204 with a body: a 204 "
                                                                     "has none"}, {})
        for status in (205, 304):
            gate.answer = (status, None, {"Allow": "POST"})
            assert _rpc(app, "POST", Handler(), CALL) == (502, {"error": f"A gate's rpc answered a {status}: the route "
                                                                         f"sends no {status}, as it cannot send one "
                                                                         "without a body"}, {}), status
        assert rpc_answer((204, None, {"Allow": "POST"}), "A gate", "rpc") == (204, None, {"Allow": "POST"})
        gate.answer = (204, {"result": "x"}, {})
        status, _, sent, raised = _wire(app, body=json.dumps(CALL).encode())
        assert (status, raised) == (502, None) and json.loads(sent)["error"].startswith("A gate's rpc answered a 204")
    finally:
        app.stop()


# -- refused before the plugin is asked ---------------------------------------------------------------------------
class Plain(Box):
    """A machine plugin with no RPC hook at all (any plugin today)."""

    name = "plain"


class Misnamed(Gate):
    """One whose RPC_HOOK names a hook it does not answer."""

    name = "misnamed"
    RPC_HOOK = "serve_agents"


class Worded(Gate):
    """One whose RPC_HOOK is not a hook's name."""

    name = "worded"
    RPC_HOOK = ("rpc",)


def test_a_plugin_with_no_such_hook_while_disabled_or_while_the_platform_stops_is_refused():
    gate, plain, misnamed, worded = Gate(), Plain(), Misnamed(), Worded()
    app = _app(gate, plain, misnamed, worded)
    try:
        for name in ("plain", "misnamed", "worded"):
            status, said, _ = _rpc(app, "POST", Handler(), CALL, path=f"/api/machines/{name}/rpc")
            assert (status, said) == (404, {"error": f"{name} takes no requests here: it names none of its hooks for "
                                                     "them (RPC_HOOK)"}), name
        assert _rpc(app, "POST", Handler(), CALL, path="/api/machines/nobody/rpc")[0] == 404
        assert misnamed.handed == [] and worded.handed == []
        assert app.set_enabled("gate", False)["state"] == "disabled"
        assert _rpc(app, "POST", Handler(), CALL) == (409, {"error": "gate is disabled: enable it first"}, {})
        assert app.set_enabled("gate", True)["state"] == "active"
        assert _rpc(app, "POST", Handler(), CALL)[0] == 200
        app.stop()
        assert _rpc(app, "POST", Handler(), CALL) == (503, {"error": STOPPING}, {})
        assert len(gate.handed) == 1
    finally:
        app.stop()


def test_the_hook_is_never_asked_by_name_nor_offered_to_the_page():
    gate = Gate()

    class Caller(MachinePlugin):
        """A stand-in asking the gate's rpc by name through the platform."""

        name, title, about, api, order = "caller", "A caller", "a stand-in", "2.2", 931
        HOOKS = (*MachinePlugin.HOOKS, "call")

        def present(self):
            return True

        def status(self):
            return {"present": True, "valid": True, "summary": "", "why": ""}

        def call(self):
            """The gate's rpc asked by name."""
            return self.app.ask("gate", "rpc", ["POST", {}, CALL, None])

    caller = Caller()
    app = _app(gate, caller)
    try:
        app.attach(gate)
        app.attach(caller)
        assert "rpc" in PlatformApp.hooks(gate) and "rpc" not in PlatformApp.asks(gate)
        assert "rpc" not in app.askable(gate) and "clients" in PlatformApp.asks(gate)
        assert "rpc" not in _api(app, "GET", "/api/machines/gate")[1]["asks"]
        status, said = _api(app, "POST", "/api/machines/gate/ask", {"hook": "rpc", "args": ["POST", {}, CALL, None]})
        assert status == 400 and said["error"].startswith("gate is not asked 'rpc' here: ")
        with pytest.raises(Refused, match="gate is not asked 'rpc' here"):
            caller.call()
        assert gate.handed == []
    finally:
        app.stop()


def test_an_agents_request_is_no_ones_ask_whoever_else_is_named_in_its_thread():
    """The route names no asker: an agent's request is neither its page's ask nor a plugin's (the plugin finds the
    agent by its token). Asked even from a thread that names the page, the hook is asked as no one's."""
    if asking is None:
        pytest.skip("this liminal-libs hands no asker over (1.66.0 does)")
    gate = Gate()
    app = _app(gate)
    try:
        with asking.asking(asking.PAGE):
            assert _rpc(app, "POST", Handler(), CALL)[0] == 200
            assert asking.asker() == asking.PAGE  # put back after it
        assert gate.askers == [None]
    finally:
        app.stop()


# -- nothing per request in the log, and the stop never waits for it -------------------------------------------------
def test_nothing_is_logged_per_request_and_it_is_noted_as_an_ask():
    gate, lines = Gate(), []
    app = _app(gate, lines=lines)
    try:
        for method in RPC_METHODS:
            assert _rpc(app, method, Handler(), CALL)[0] == 200
        assert lines == []  # the plugin notes its own (its audit), the platform's log nothing
        assert _api(app, "POST", "/api/machines/gate/ask", {"hook": "poke", "args": []})[0] == 200
        assert lines == ["platform: gate asked poke"]  # a change asked by name, as ever: logged by its name
        assert {app.classify(m, PATH) for m in RPC_METHODS} == {"ask"}
    finally:
        app.stop()


def test_a_request_held_by_its_plugin_does_not_hold_the_stop_and_the_plugin_ends_it(monkeypatch):
    monkeypatch.setattr(app_module, "STOP_WAIT_S", 30.0)  # a wait for it would show: the stop would wait half a minute
    gate, lines = Gate(), []
    gate.hold = True
    app = _app(gate, lines=lines)
    waited: list = []

    class Watched(threading.Condition):
        """The stop's wait for what is under way, noted if it waits at all."""

        def wait(self, timeout=None):
            waited.append(timeout)
            return super().wait(timeout)

    app._asked = Watched(app._lock)
    answers: list = []
    agent = threading.Thread(target=lambda: answers.append(_rpc(app, "POST", Handler(), CALL)))
    agent.start()
    try:
        assert gate.inside.wait(5)  # a call held for your answer, inside the plugin
        app.stop()
        assert waited == [] and gate.told == ["told"]  # nothing it counts was under way: told at once
        agent.join(10)
        assert not agent.is_alive() and answers == [(200, gate.answer[1], {"Mcp-Session-Id": "s1"})]
        assert not any("still under way" in line for line in lines)
        assert _rpc(app, "POST", Handler(), CALL) == (503, {"error": STOPPING}, {})  # and nothing new is begun
    finally:
        gate.go.set()
        agent.join(10)


# -- the library's own protocol plugin through the platform's routes ------------------------------------------------
def test_the_librarys_protocol_plugin_answers_through_the_platforms_routes(tmp_path):
    """liminal-libs 1.66.0's ProtocolPlugin, a stand-in subclass of it, attached to the platform: its decisions asked
    from the page (a token shown once, asked twice), an agent's request on the route found by its token and handed
    over without it, a harness's ask for its own agent and launch token through the platform, and each gate held:
    nothing a page or a program asks hands out a token, and nothing a plugin asks decides."""
    protocol = pytest.importorskip("liminal_libs.machines.protocol")
    from liminal_libs.machines.ai import Outside

    class Gateway(protocol.ProtocolPlugin):
        name, title, about, order, version = "gateway", "Gateway", "a stand-in protocol plugin", 530, "0.1.0"

        def serve(self, method, headers, body, client, gone):
            self.record(client, method, "tools/list", "answered", kind="read")
            return 200, {"agent": client, "method": method, "headers": dict(headers), "body": body}, {
                "Mcp-Session-Id": "s1"}

        def offer(self, client):
            return {"wires": ["http"], "endpoint": "/api/machines/gateway/rpc"}

        def grantable(self):
            return {}

    class Coder(MachinePlugin):
        """A stand-in harness: its agent and a launch token for its window, asked of the gateway through the
        platform."""

        name, title, about, api, order = "coder", "Coder", "a stand-in harness", "2.2", 932
        HOOKS = (*MachinePlugin.HOOKS, "wire", "decide_for_me")

        def present(self):
            return True

        def status(self):
            return {"present": True, "valid": True, "summary": "", "why": ""}

        def wire(self):
            """Its agent made, then a launch token for its next window."""
            made = self.app.ask("gateway", "ensure_client", ["Coder"])
            return made, self.app.ask("gateway", "launch_token", [])

        def decide_for_me(self):
            """An agent's harness trying to add an agent of its own: refused."""
            return self.app.ask("gateway", "add_client", ["eve", "Eve"])

    lines: list[str] = []
    gateway = Gateway(Outside(env={}, home=tmp_path / "gateway", clock=lambda: 1_800_000_000.0))
    coder = Coder()
    app = PlatformApp(log=lines.append, login=EnvironmentLogin(env={}), machines={"gateway": gateway, "coder": coder},
                      assistants={})
    try:
        assert app.attach_plugins([gateway, coder]) == ["gateway", "coder"]
        asks = PlatformApp.asks(gateway)
        assert not {"rpc", "ensure_client", "launch_token", "end_launch"} & set(asks)
        assert {"add_client", "token_once", "decide", "waiting_call", "client_offer"} <= set(asks)
        # the page decides (no login here: nothing to prove), the token shown once after its second confirmation
        added = _api(app, "POST", "/api/machines/gateway/ask", {"hook": "add_client", "args": ["alice", "Alice"]})
        assert added[0] == 200
        status, refused = _api(app, "POST", "/api/machines/gateway/ask", {"hook": "token_once", "args": ["alice", 30]})
        assert status == 400 and refused["accept"] == "accept_shown"
        status, shown = _api(app, "POST", "/api/machines/gateway/ask",
                             {"hook": "token_once", "args": ["alice", 30, True]})
        token = shown["answer"]["token"]
        assert status == 200 and len(token) >= 40
        # an agent's request: found by its token, handed over without it, answered with its session
        sent = [("Authorization", f"Bearer {token}"), ("Mcp-Method", "tools/list"), ("Cookie", "liminal_session=x")]
        status, data, headers = _rpc(app, "POST", Handler(sent), CALL, path="/api/machines/gateway/rpc")
        assert (status, data["agent"], data["headers"], data["body"]) == (200, "alice", {"mcp-method": "tools/list"},
                                                                          CALL)
        assert headers == {"Mcp-Session-Id": "s1"}
        status, data, headers = _rpc(app, "POST", Handler(), CALL, path="/api/machines/gateway/rpc")
        assert status == 401 and headers == {"WWW-Authenticate": "Bearer"} and "no bearer token" in data["error"]
        # a harness's agent and its launch token, asked through the platform: its own, named by the platform
        made, launch = coder.wire()
        assert made["agent"] == "coder" and launch["agent"] == "coder"
        status, data, _ = _rpc(app, "POST", Handler([("Authorization", f"Bearer {launch['token']}")]), CALL,
                               path="/api/machines/gateway/rpc")
        assert (status, data["agent"]) == (200, "coder")
        # the gates: a program never gets a token, and a plugin never decides
        status, said = _api(app, "POST", "/api/machines/gateway/ask", {"hook": "launch_token", "args": []})
        assert status == 403 and "asked only by another plugin" in said["words"] and "answer" not in said
        with pytest.raises(Refused) as refused_to_plugin:
            coder.decide_for_me()
        assert refused_to_plugin.value.status == 403 and "asked only from its page" in refused_to_plugin.value.words
        assert [c["name"] for c in gateway.clients()] == ["alice", "coder"]  # eve was never added
        # and over HTTP, a decision is asked only with the login's word that you are there
        app.present = lambda handler: False
        status, said = _api(app, "POST", "/api/machines/gateway/ask", {"hook": "revoke", "args": ["alice"]})
        assert status == 401 and "does not show that you are there" in said["words"]
        app.present = lambda handler: True
        assert _api(app, "POST", "/api/machines/gateway/ask", {"hook": "revoke", "args": ["alice"]})[0] == 200
        assert _rpc(app, "POST", Handler(sent), CALL, path="/api/machines/gateway/rpc")[0] == 401  # its token ended
        assert token not in "\n".join(lines) and launch["token"] not in "\n".join(lines)  # no token in the log
        assert not any("asked rpc" in line for line in lines)  # nor a line per request
    finally:
        app.stop()
