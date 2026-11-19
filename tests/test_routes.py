"""The platform's own routes as its Internal API lists them (routes.py; liminal-libs 1.63.0's internal.py; the user,
2026-11-17: "describe the internal API like structure that the app code can work with"): one row for each route
PlatformApp.api answers, held here to the code itself. The chain is read from its source with ast and each row's class
is asked of classify: nothing is started, nothing is served, no plugin is asked."""
from __future__ import annotations

import ast
import inspect
import re
import textwrap
from importlib import resources

import pytest

from liminal_libs.apps import App
from liminal_libs.apps.traffic import CLASSES

from liminal_platform.app import RPC_METHODS, PlatformApp
from liminal_platform.routes import MACHINE, ROUTES

pytestmark = pytest.mark.usefixtures("no_outside")  # nothing started, served or reached (tests/conftest.py)

METHODS = ("GET", "POST", "PUT", "DELETE")
WHO = ("page", "client", "plugin", "app", "login")  # who asks a route (internal.py's words)


def _parts(node: ast.If) -> list:
    """An if's test, split at its `and`s."""
    test = node.test
    return list(test.values) if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And) else [test]


def _compared(part, name: str) -> list:
    """What `name` is compared with in one part of a test: `name == "x"` -> ["x"], `name in ("x", "y")` -> both,
    `not name` -> [""] (the empty action: the plugin itself)."""
    if isinstance(part, ast.UnaryOp) and isinstance(part.op, ast.Not):
        return [""] if isinstance(part.operand, ast.Name) and part.operand.id == name else []
    if not (isinstance(part, ast.Compare) and isinstance(part.left, ast.Name) and part.left.id == name):
        return []
    op, right = part.ops[0], part.comparators[0]
    if isinstance(op, ast.Eq) and isinstance(right, ast.Constant):
        return [right.value]
    if isinstance(op, ast.In) and isinstance(right, (ast.Tuple, ast.List, ast.Set)):
        return [e.value for e in right.elts if isinstance(e, ast.Constant)]
    return []


def _called(part, name: str, method: str):
    """The constant of `name.method("...")` in one part of a test, else None."""
    func = getattr(part, "func", None)
    if isinstance(part, ast.Call) and isinstance(func, ast.Attribute) and func.attr == method \
            and isinstance(func.value, ast.Name) and func.value.id == name and part.args \
            and isinstance(part.args[0], ast.Constant):
        return part.args[0].value
    return None


def chain_routes() -> set[tuple[str, str]]:
    """Every (method, path) PlatformApp.api's chain answers before the frame's, read from its source: a path compared
    whole, a prefix and a suffix around a plugin's name (/api/plugins/{name}/settings), and inside the block of one
    machine plugin's routes each action it compares with (`action == "ask"`, `action in ("setup", "job")`, `not
    action`), under MACHINE."""
    fn = ast.parse(textwrap.dedent(inspect.getsource(PlatformApp.api))).body[0]
    out: set[tuple[str, str]] = set()
    for stmt in fn.body:
        if not isinstance(stmt, ast.If):
            continue
        parts = _parts(stmt)
        methods = [m for p in parts for m in _compared(p, "method")]
        paths = [x for p in parts for x in _compared(p, "path")]
        start = next((c for p in parts if (c := _called(p, "path", "startswith")) is not None), None)
        end = next((c for p in parts if (c := _called(p, "path", "endswith")) is not None), None)
        if start == "/api/machines/" and not methods:  # one machine plugin's routes, told apart by their action
            for inner in (s for s in stmt.body if isinstance(s, ast.If)):
                there = _parts(inner)
                for method in (m for p in there for m in _compared(p, "method")):
                    out |= {(method, MACHINE + (f"/{a}" if a else "")) for p in there for a in _compared(p, "action")}
        elif paths:
            out |= {(m, p) for m in methods for p in paths}
        elif start is not None and end is not None:
            out |= {(m, start + "{name}" + end) for m in methods}
    return out


def test_the_table_lists_every_route_the_chain_answers_and_no_other():
    found = chain_routes()
    assert len(found) >= 20 and ("POST", MACHINE + "/ask") in found and ("GET", MACHINE) in found  # the reading reads
    assert ("POST", "/api/plugins/{name}/settings") in found and ("GET", MACHINE + "/job") in found
    assert ("POST", MACHINE + "/job/cancel") in found  # 0.31.0's Cancel, listed since 0.32.0
    # 0.34.0: an agent's request to a protocol plugin, on each of the three methods MCP's transport uses
    assert {(m, MACHINE + "/rpc") for m in RPC_METHODS} <= found and ("PUT", MACHINE + "/rpc") not in found
    listed = [(r[0], r[1]) for r in ROUTES]
    assert len(listed) == len(set(listed)), "a route listed twice"
    assert set(listed) - found == set(), "rows the chain does not answer"
    assert found - set(listed) == set(), "routes the chain answers that routes.py does not list"


def test_each_row_says_what_it_is_its_class_and_who_asks_it():
    app = PlatformApp(log=lambda m: None, machines={}, assistants={})
    for row in ROUTES:
        assert isinstance(row, tuple) and len(row) == 5 and all(isinstance(x, str) for x in row), row
        method, path, about, kind, who = row
        assert method in METHODS and path.startswith("/api/") and about.strip() and who in WHO, row
        assert kind in CLASSES and kind == app.classify(method, path.replace("{name}", "x")), row
        assert path.count("{") == path.count("}") <= 1 and ("{" not in path or "{name}" in path), row
    assert {r[3] for r in ROUTES} == {"read", "change", "ask", "stream"}  # the four classes a request of it is noted as
    # the command is a client's alone, and a change (classify), never the page's ask
    assert next(r for r in ROUTES if r[1] == MACHINE + "/run")[3:] == ("change", "client")
    # 0.34.0: an agent's request is a program's, and an ask whatever its method (classify: /rpc)
    assert [r[0] for r in ROUTES if r[1] == MACHINE + "/rpc"] == list(RPC_METHODS)
    assert {r[3:] for r in ROUTES if r[1] == MACHINE + "/rpc"} == {("ask", "client")}


def test_who_asks_the_whole_status_and_what_is_noted_of_a_terminals_keys():
    """GET /api/status is a client's: this page asks it only of a platform from before GET /api/overview (renderWhole,
    after a 404 there), which this one is not; no other Liminal app asks it. A terminal's keys: the request is noted in
    who talks to whom, as the frame notes every request (its path, never its body) and as the platform notes "keys
    typed"; the keys themselves are never noted or logged."""
    script = (resources.files("liminal_platform") / "static" / "platform.js").read_text(encoding="utf-8")
    whole = script.index("async function renderWhole(g) {")
    asked = [m.start() for m in re.finditer(re.escape("api('GET', 'api/status')"), script)]
    assert asked and all(whole < at < script.index("\n  }\n", whole) for at in asked)  # renderWhole alone asks it
    assert "if (e.status === 404) return renderWhole(g);" in script  # only when GET api/overview is not answered
    rows = {(r[0], r[1]): r for r in ROUTES}
    assert ("GET", "/api/overview") in rows and rows[("GET", "/api/status")][3:] == ("read", "client")
    keys = rows[("POST", MACHINE + "/terminal/input")][2]
    assert "noted" in keys and "keys typed" in keys and "the keys themselves never noted or logged" in keys
    assert "never noted, never logged" not in keys  # (the request is noted)
    assert '"stream", "keys typed")' in inspect.getsource(PlatformApp.api)  # what the platform notes of it


def test_the_app_gives_them_as_its_own_routes():
    assert PlatformApp.ROUTES is ROUTES
    if callable(getattr(App, "routes", None)):  # liminal-libs 1.63.0: the frame's routes(), the app's own rows
        assert PlatformApp(log=lambda m: None, machines={}, assistants={}).routes() == ROUTES


def test_the_librarys_own_reading_finds_the_table_and_the_code_alike():
    internal = pytest.importorskip("liminal_libs.internal")
    if not (callable(getattr(internal, "route_problems", None)) and callable(getattr(internal, "literals_in", None))):
        pytest.skip("this liminal-libs reads no route table")
    literals = internal.literals_in(inspect.getsource(PlatformApp.api))
    assert "/api/overview" in literals and "/api/machines/" in literals
    assert internal.route_problems(ROUTES, literals) == []
    # and it tells when they part: a row the code does not answer, a route the table does not list
    assert internal.route_problems((*ROUTES, ("GET", "/api/nowhere", "not answered", "read", "page")), literals)
    assert internal.route_problems(tuple(r for r in ROUTES if r[1] != "/api/overview"), literals)
