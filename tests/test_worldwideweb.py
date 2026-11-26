"""0.39.2 (Monday list item 33): the World Wide Web tab is a plugin of its own, plugin-platform-worldwideweb, on
liminal-libs 1.105.0's WorldWideWeb base, and the firewalls keep their Netstat tab. Through the platform, with nothing
of the platform's own code changed for it (its tabs are drawn as every plugin's): the plugin's tab is listed and asked
as a read; it asks the firewall's socket table of it through the platform's ask, the firewall chosen being the one that
answers; the globe's layer and pick are its hooks now, a layer a read, a pick an ask; the firewall's Netstat tab asks it
for its places. And the page writes an old address of a firewall's tab (#firewall-windows/world) as the plugin's, once
that plugin is listed and the firewall no longer declares the tab (checked in headless Edge on stand-ins too). A
stand-in capture, socket table and GeoIP folder: nothing of this machine is read or reached."""
from __future__ import annotations

import time
from collections import deque

import pytest

from conftest import Wall, page_script, sock

from liminal_platform.app import PlatformApp

worldweb = pytest.importorskip("liminal_libs.machines.worldweb", reason="a library before 1.105.0 has no such base")


class Feed:
    """A capture as a stand-in: opened, nothing to hand, closed."""

    address = "192.168.1.20"

    def __init__(self):
        self.packets = deque()

    def open(self):
        pass

    def next(self):
        return None

    def close(self):
        pass


class Web(worldweb.WorldWideWeb):
    """The World Wide Web plugin as a stand-in: its capture Feed's, its GeoIP folder the test's (none installed), its
    routes traced by nobody."""

    name, title, about, api, order = "worldwideweb", "World Wide Web", "a stand-in globe", "2.2", 712

    def __init__(self, folder):
        self.folder = folder

    def present(self):
        return True

    def make_world_view(self):
        from liminal_libs.machines.world import WorldView

        return WorldView(self.name, capture_factory=Feed, geo_folder=self.folder,
                         resolve=lambda version, servers: (None, "no name server answers in a test"))

    def make_world_routes(self):
        from liminal_libs.machines.routes import Routes

        return Routes(tracer=lambda address: None, start=lambda work: None, keep=self._keep_route, known=self._routed,
                      stored=self._stored_routes)


@pytest.fixture
def platform(tmp_path):
    lines, wall, web = [], Wall(), Web(tmp_path / "geoip")
    wall.sockets = [sock(local_port=51000, remote="81.2.69.142", remote_port=443, started=time.time() - 60)]
    app = PlatformApp(log=lines.append, machines={"wall": wall, "worldwideweb": web}, assistants={},
                      state=tmp_path / "platform")
    assert app.attach_plugins([wall, web]) == ["wall", "worldwideweb"]  # as the platform's start attaches them
    yield app, wall, web, lines
    app.stop()


def ask(app, name, hook, *args):
    return app.api(None, "POST", f"/api/machines/{name}/ask", {}, {"hook": hook, "args": list(args)})


def test_its_tab_is_listed_asked_as_a_read_and_asks_the_firewall_through_the_platform(platform):
    app, wall, web, lines = platform
    status, m = app.api(None, "GET", "/api/machines/worldwideweb", {}, None)
    assert status == 200 and [t["id"] for t in m["tabs"]] == ["world"]
    status, f = app.api(None, "GET", "/api/machines/wall", {}, None)
    assert "world" not in {t["id"] for t in f["tabs"]}  # the firewall keeps its Netstat tab alone
    assert "world" in PlatformApp.reads_of(web) and "world_layer" in PlatformApp.reads_of(web)
    status, out = ask(app, "worldwideweb", "world")
    assert status == 200 and out["answer"]["title"] == "World Wide Web" and web.firewall() == "wall"
    said = {(r["what"], r["kind"]) for r in app.traffic.recent() if r["to"] == "wall"}
    assert ("netstat_seen", "read") in said  # the plugin asked the firewall, as the platform notes every ask
    with pytest.raises(LookupError) as refused:  # no layer installed: the plugin's own refusal
        web.world_layer("datacentres")
    status, out = ask(app, "worldwideweb", "world_layer", "datacentres")
    assert status == 400 and out["words"] == str(refused.value)
    status, out = ask(app, "worldwideweb", "world_pick", "clear")
    assert status == 200 and [x for x in lines if " asked " in x] == ["platform: worldwideweb asked world_pick (1 argument)"]


def test_the_firewalls_netstat_asks_it_for_its_places(platform):
    app, wall, web, lines = platform
    status, out = ask(app, "wall", "netstat")
    assert status == 200 and "flows" in out["answer"]
    said = {(r["what"], r["to"]) for r in app.traffic.recent()}
    assert ("places", "worldwideweb") in said  # one ask a page; no GeoIP file here, so the note says why
    assert "No place is shown" in out["answer"]["note"]


def test_the_page_writes_a_firewalls_old_address_as_the_plugins():
    js = page_script()
    moved = js[js.index("function wwwMoved(name, tab) {"):js.index("function oldAddress() {")]
    assert "tab === 'world' && OLD_WWW.test(name || '') && !!fw && !!st.machines[WWW]" in moved
    assert "!declaredTabs(fw).some((t) => t.id === 'world')" in moved  # a firewall with the tab keeps its address
    old = js[js.index("function oldAddress() {"):js.index("function draw() {")]
    assert "wwwMoved(name, tab) ? `#${WWW}/world`" in old and "location.hash" not in old
