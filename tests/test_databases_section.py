"""0.36.0: the platform's Databases section (Monday list item 30, step 2; the user, 2026-11-24: "inheritance bro",
"through the rust interface"; 2026-11-25: the instance forms move to the platform's Databases section, the platform the
only writer of instance settings). PlatformApp is built on liminal-libs 1.90.0's platform core (Platform): it attaches
the database plugins, answers the section's two routes through liminal_libs.apps.databases, makes a change only once
it is confirmed (a server off this machine only once confirmed twice), keeps what you add through its login alone, says
each plugin's External and Internal API, and serves the section as its liminal-net node once it is served.

Two stand-in engines, a file's and a server's, found by a stand-in registry; a data folder of the test's own; liminal-
net stood in for (nothing listens, nothing is started, nothing is sent); the page's script tested by its text."""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace

import pytest

from liminal_libs.apps import EnvironmentLogin
from liminal_libs.apps import platform as core
from liminal_libs.apps.platform import Platform
from liminal_libs.sources import registry
from liminal_libs.sources.apis import Api, Link
from liminal_libs.storage import databases as contract
from liminal_libs.storage.databases import DatabasePlugin, Instance

from conftest import Box, api_answer, page_script, script_part

import liminal_platform.app as app_mod
from liminal_platform import cli
from liminal_platform.app import DATABASE_TERMS, DATABASES_SECTION, PlatformApp
from liminal_platform.routes import ROUTES

pytestmark = pytest.mark.usefixtures("no_outside")  # nothing started, served or reached (tests/conftest.py)


def docs(name: str) -> tuple:
    return (Api(name=name, maker="the tests", about="a stand-in engine", kind="file",
                links=(Link("Its documentation", "https://www.sqlite.org/docs.html", "docs"),), verified="2026-11-25"),)


class Flat(DatabasePlugin):
    """A file engine's stand-in: a database is a text file that begins with the word flat."""

    name, title, about, api, order = "sqlite", "Flat", "a file engine's stand-in", "2.3", 940
    options = ("SQLITE_INSTANCES",)
    apis = docs("Flat files")
    ENGINE = "sqlite"
    METHODS = ("file",)
    HOLDS = ("main", "bars")

    def builtin(self, data_dir):
        return (Instance("data", "The data folder", where="./", holds=("main", "bars")),)

    def open(self, instance, part="", read_only=True, data_dir=None):
        return open(self.path_of(instance, data_dir), "r" if read_only else "a", encoding="utf-8")

    def probe(self, instance, data_dir):
        if instance.folder:
            return ["a folder"]
        with self.open(instance, data_dir=data_dir) as f:
            if f.readline().strip() != "flat":
                raise ValueError("not a flat file")
        return ["flat 1"]

    def make(self, instance, data_dir, **given):
        path = self.path_of(instance, data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("flat\n", encoding="utf-8", newline="\n")
        return [f"{path.name} made"]


class Served(DatabasePlugin):
    """A server engine's stand-in: nothing answers anywhere, and no server is ever asked here."""

    name, title, about, api, order = "postgres", "Served", "a server engine's stand-in", "2.3", 941
    options = ("POSTGRES_INSTANCES",)
    apis = docs("Served")
    ENGINE = "postgres"
    METHODS = ("tcp",)
    HOLDS = ("documents",)
    SERVER = True
    SHARED = "its server's roles decide who reaches it"

    def open(self, instance, part="", read_only=True, data_dir=None):
        raise ConnectionError(f"nothing answers at {instance.where}:{instance.port}")

    def probe(self, instance, data_dir):
        self.open(instance, data_dir=data_dir)

    def make(self, instance, data_dir, **given):
        self.open(instance, data_dir=data_dir)


@pytest.fixture
def found(tmp_path, monkeypatch):
    """The two stand-ins as the registry finds the packages, no machine plugin or assistant of this PC, a data folder
    of the test's own (LIMINAL_DB), and nothing that listens on this machine."""
    flat, served = Flat(), Served()
    monkeypatch.setattr(registry, "databases", lambda: {"sqlite": flat, "postgres": served})
    monkeypatch.setattr(registry, "machines", lambda: {})
    monkeypatch.setattr(registry, "assistants", lambda: {})
    monkeypatch.setattr(registry, "errors", lambda: [("plugin-platform-duckdb (plugin_platform_duckdb)",
                                                      "ModuleNotFoundError: No module named 'duckdb'")])
    monkeypatch.setattr(contract, "listening", lambda host, port, timeout=0.3: False)
    data = tmp_path / "data"
    data.mkdir()
    (data / "liminal.db").write_text("flat\n", encoding="utf-8", newline="\n")
    monkeypatch.setenv("LIMINAL_DB", str(data / "liminal.db"))
    env: dict = {}
    lines: list[str] = []
    app = PlatformApp(log=lines.append, login=EnvironmentLogin(env=env), machines={"box": Box()}, assistants={})
    yield SimpleNamespace(app=app, data=data, env=env, lines=lines, flat=flat, served=served, folder=tmp_path / "platform")
    for p in (flat, served):
        if p.app is app:
            app.detach(p.name)


def post(app, **form):
    return api_answer(app, "POST", "/api/databases/instances", form)


# -- the platform core under the platform app ----------------------------------------------------------------------------
def test_the_platform_app_is_the_platform_core_and_the_one_writer():
    assert issubclass(PlatformApp, Platform) and PlatformApp.PLATFORM_NEEDS == ("database",)
    assert PlatformApp.PLATFORM_WRITER is True and DATABASES_SECTION == "databases" == DatabasePlugin.SECTION
    app = PlatformApp(log=lambda m: None, login=EnvironmentLogin(env={}), machines={}, assistants={})
    assert app.is_platform and app.needs("database") and not app.needs("machine")  # its machines are its own, as before


def test_the_registrys_plugins_attach_the_database_plugins_too(found):
    app = found.app
    assert app.attach_plugins() == ["sqlite", "postgres"]  # (no machine plugin or assistant in the registry here)
    assert found.flat.app is app and found.served.app is app and found.flat.login is not None
    assert sorted(app.section(DATABASES_SECTION)) == ["postgres", "sqlite"]
    assert app.attach_plugins() == []  # attached once
    assert app.known_plugins()[-2:] == [found.flat, found.served]  # the Internal API knows them, the registry not asked


# -- the section's routes ---------------------------------------------------------------------------------------------------
def test_the_section_lists_each_database_plugin_with_what_its_tabs_draw(found):
    status, body = api_answer(found.app, "GET", "/api/databases/plugins")
    assert status == 200 and body["writer"] is True and body["dataFolder"] == str(found.data)
    assert body["suites"][0] == body["me"]
    assert body["errors"] == ["plugin-platform-duckdb (plugin_platform_duckdb): ModuleNotFoundError: No module named 'duckdb'"]
    rows = {p["name"]: p for p in body["plugins"]}
    assert list(rows) == ["sqlite", "postgres"]
    for row in rows.values():
        assert (row["kind"], row["section"], row["icon"], row["pluginApi"]) == ("database", "databases", "database", "2.3")
        assert row["apis"] and row["apis"][0]["name"] in ("Flat files", "Served")  # its External API tab
        assert "probe" in row["hooks"] and "make" in row["hooks"]
        if app_mod.internal_mod is not None:  # its Internal API tab, as every plugin's
            assert isinstance(row["internal"], dict) and row["internal"]["pageAsks"] == []
    flat = rows["sqlite"]
    assert flat["can"]["new"] is True and flat["can"]["why"] == ""  # changed here: the platform is the one writer
    assert [i["name"] for i in flat["instances"]] == ["data"] and rows["postgres"]["server"] is True
    # the plugins attached at the first ask, with the platform's login
    assert found.flat.app is found.app and found.served.app is found.app


def test_a_change_is_made_only_once_confirmed_and_kept_through_the_login_alone(found):
    app = found.app
    status, body = post(app, plugin="sqlite", action="new", name="archive", where="instances/archive.db")
    assert status == HTTPStatus.BAD_REQUEST and "confirmed on the page first" in body["error"]
    assert not (found.data / "instances").exists() and found.env == {}
    status, body = post(app, plugin="sqlite", action="new", name="archive", where="instances/archive.db", confirm=True)
    assert status == 200 and body["ok"]
    assert (found.data / "instances" / "archive.db").read_text(encoding="utf-8") == "flat\n"
    assert "archive" in found.env["SQLITE_INSTANCES"]  # through the login: no settings file
    assert not found.folder.exists() or not any(found.folder.rglob("*.json"))
    assert any(line.startswith("platform: sqlite: new archive: ") for line in found.lines)
    status, body = post(app, plugin="sqlite", action="test", name="archive")  # a test needs no confirmation
    assert status == 200 and body["ok"]
    listed = api_answer(app, "GET", "/api/databases/plugins")[1]
    assert "archive" in [i["name"] for i in next(p for p in listed["plugins"] if p["name"] == "sqlite")["instances"]]
    status, body = post(app, plugin="sqlite", action="forget", name="archive", confirm=True)
    assert status == 200 and (found.data / "instances" / "archive.db").exists()  # what it holds stays where it is
    for form, want in (({"plugin": "nope", "action": "test"}, 404), ({"plugin": "sqlite", "action": "drop"}, 400)):
        assert post(app, **form)[0] == want


def test_a_server_off_this_machine_is_asked_twice_and_kept_only_then(found):
    app = found.app
    form = {"plugin": "postgres", "action": "connect", "name": "far", "where": "203.0.113.5", "port": 5432,
            "database": "docs", "confirm": True}
    status, body = post(app, **form)
    # the refusal names what accepts it, for the page's second question (the frame alone would drop it)
    assert status == HTTPStatus.BAD_REQUEST and body["accept"] == "accept_remote" and "not this machine" in body["error"]
    assert found.env == {}
    status, body = post(app, **form, accept_remote=True)  # accepted, but neither TLS nor a sign-in: refused all the same
    assert status == HTTPStatus.BAD_REQUEST and "accept" not in body and found.env == {}


def test_the_routes_are_the_platforms_own_and_listed():
    rows = {(r[0], r[1]): r for r in ROUTES}
    assert rows[("GET", "/api/databases/plugins")][3:] == ("read", "page")
    assert rows[("POST", "/api/databases/instances")][3:] == ("change", "page")


# -- the Internal API, and the node -------------------------------------------------------------------------------------
def test_how_a_database_plugin_is_asked_in_words(found):
    found.app.attach_plugins()
    words = found.app.call_words(found.flat)
    assert words["terms"] == DATABASE_TERMS and "POST /api/databases/instances" in words["clients"]
    assert "'sqlite'" in words["clients"] and found.app.askable(found.flat) == set()  # never a hook by its name
    assert "database" in app_mod.CALLS and "new_database" in app_mod.CALLS["database"]


class StandInNode:
    """liminal_net.Node stood in for: started and stopped, nothing listens."""

    made: list = []

    def __init__(self, name, kind, scope, hillock, interface, ipc_dir=None, timing=None):
        self.name, self.kind, self.scope, self.hillock, self.interface = name, kind, scope, hillock, interface
        self.started, self.stopped = False, []
        StandInNode.made.append(self)

    def start(self):
        self.started = True

    def stop(self, why):
        self.stopped.append(why)


def test_the_section_is_served_as_its_node_and_ends_with_the_platform(found, monkeypatch, tmp_path):
    monkeypatch.setattr(StandInNode, "made", [])
    app = PlatformApp(log=found.lines.append, login=EnvironmentLogin(env={}), machines={}, assistants={},
                      node_factory=StandInNode)
    app.PLATFORM_SCOPE = tmp_path
    cli.serve_databases(app)
    node = app.databases_node
    assert node is StandInNode.made[0] and node.started and node.name == core.DATABASES_NODE == "platform-databases"
    assert set(node.interface["methods"]) == {"overview", "elsewhere", "test", "change"}
    assert node.hillock.request({"name": "app-charts-platform"}, "overview", [], {})["writer"] is True
    app.stop()
    assert node.stopped == ["the platform is ending"] and app.databases_node is None


def test_a_node_that_cannot_be_served_is_said_and_the_page_served_all_the_same(found):
    def refused(*args, **kwargs):
        raise ImportError("No module named 'liminal_net'")

    app = PlatformApp(log=found.lines.append, login=EnvironmentLogin(env={}), machines={}, assistants={},
                      node_factory=refused)
    cli.serve_databases(app)  # nothing raised
    assert app.databases_node is None
    assert found.lines[-1] == ("platform: its Databases section is not served as a node: ImportError: No module "
                               "named 'liminal_net'")


# -- the page ------------------------------------------------------------------------------------------------------------
def test_the_page_draws_the_section_beside_the_others_with_its_tabs():
    js = page_script()
    draw = script_part(js, "function drawList() {")
    assert draw.index("SECTIONS.map(") < draw.index("dbList(item,") < draw.index("<h4>AI plugins</h4>")
    listed = script_part(js, "function dbList(item, cls) {")
    assert "if (!d || d.absent) return '';" in listed and "<h4>Database plugins</h4>" in listed
    assert "${dbTable()}" in script_part(js, "function machineData() {")
    page = script_part(js, "function dbData(p) {")
    assert "${tabsRow(p)}" in page and "return head + apiCard(p);" in page and "return head + internalCard(p);" in page
    assert "return head + dbMain(p);" in page
    assert ": db ? dbData(db)" in script_part(js, "function drawData() {")
    assert ": db ? dbSide(db) :" in script_part(js, "function drawSide() {")
    assert "asks.push(loadDatabases());" in script_part(js, "async function render() {")
    load = script_part(js, "async function loadDatabases() {")
    assert "api('GET', 'api/databases/plugins')" in load and "e.status === 404 ? { absent: true }" in load
    assert "databases: was.databases || { pending: true }" in script_part(js, "function held(ov) {")
    # the forms: New database, Connect, Share, Port, Sign-in, Forget, Test
    main, row = script_part(js, "function dbMain(p) {"), script_part(js, "function dbRow(p, i) {")
    assert "New database…" in main and "Connect…" in main
    for words in ("'Test'", "'Share…'", "'Port…'", "'Sign-in…'", "'Forget'"):
        assert words in row, words
    forms = script_part(js, "function dbFormHtml(p) {")
    for kind in ("'new'", "'connect'", "'share'", "'port'", "'signin'"):
        assert f"dbForm.kind === {kind}" in forms, kind


def test_the_page_asks_before_every_change_and_twice_for_a_server_off_this_machine():
    js = page_script()
    sent = script_part(js, "function dbSubmit(f) {")
    assert "dbPending = { plugin: p.name, body, words: dbQuestion(body) };" in sent and "api(" not in sent  # asked, not sent
    act = script_part(js, "function dbDo(b) {")
    # only the yes sends a change, with confirm: true; a test needs none; Forget is asked first too
    assert "if (what === 'yes') { if (dbPending) dbAnswer(p, { ...dbPending.body, confirm: true }); return; }" in act
    assert act.count("dbAnswer(") == 2 and "action: 'test'" in act
    assert "dbPending = { plugin: p.name, body, words: dbQuestion(body) };" in act
    answer = script_part(js, "async function dbAnswer(p, body) {")
    assert "api('POST', 'api/databases/instances', body)" in answer
    assert ("} else if (dbPending && !dbPending.second && typeof accept === 'string' && /^[a-z_]+$/.test(accept)) {"
            in answer)
    assert "body: { ...body, [accept]: true }" in answer and "second: true" in answer
    assert "if (body.action !== 'test') { dbForm = null; await loadDatabases(); return; }" in answer
    assert "'Yes, all the same'" in script_part(js, "function dbAskHtml(p) {")
    assert "const dbSecret = (name) => `<input name=\"${name}\" type=\"password\" ${kb('secret'" in js  # never shown
    css = (PlatformApp.STATIC / "platform.css").read_text(encoding="utf-8")
    assert ".db-form {" in css and ".db-ask.second {" in css
