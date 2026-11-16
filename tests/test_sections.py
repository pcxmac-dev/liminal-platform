"""0.25.0 (the user, 2026-11-14: "classify the cloud plugins under the 'cloud plugins' section which should be on the far
left") and 0.26.0 (2026-11-15: "platform needs a virtualization plugins section"; "just like cloud plugins"; "then OS
plugins"): each machine plugin's overview row and status say its section (liminal-libs 1.51.0's MachinePlugin.SECTION):
"virtualization" for a hypervisor's or a container engine's, "os" for an operating system's, "cloud" for a cloud provider's
account, and "machine" otherwise. The page's list and the machine's own page draw a section of each, in that order, and a
server that sends no section draws every plugin under Machine plugins. Stand-in plugins on a free port: nothing of this
machine is asked."""
from __future__ import annotations

from conftest import Box, Wall, _port
from test_app import Bot, _call

from liminal_platform.app import SECTIONS, PlatformApp, section_of


class Cloudy(Box):
    """A stand-in cloud provider's account."""

    name = "cloudy"
    title = "A cloud account"
    ICON = "digitalocean"
    SECTION = "cloud"


class Hyper(Box):
    """A stand-in hypervisor."""

    name = "hyper"
    title = "A hypervisor"
    ICON = "hyperv"
    SECTION = "virtualization"


class Distro(Box):
    """A stand-in operating system's plugin."""

    name = "distro"
    title = "An operating system"
    ICON = "ubuntu"
    SECTION = "os"


class Odd(Box):
    """A plugin naming a section the platform does not draw."""

    name = "odd"
    title = "An odd box"
    SECTION = "elsewhere"


def test_a_plugin_says_its_section_and_anything_else_is_a_machine_plugin():
    assert SECTIONS == ("machine", "virtualization", "os", "cloud")
    assert ([section_of(p) for p in (Cloudy(), Hyper(), Distro(), Box(), Wall(), Odd())]
            == ["cloud", "virtualization", "os", "machine", "machine", "machine"])
    assert section_of(object()) == "machine"  # an older library's plugin, with no SECTION at all


def test_the_overview_and_each_status_carry_the_section():
    app = PlatformApp(log=lambda m: None, machines={"box": Box(), "cloudy": Cloudy(), "distro": Distro(), "hyper": Hyper(),
                                                    "wall": Wall()},
                      assistants={"bot": Bot()}, settings=lambda: object())
    port = _port(app.start(0))
    try:
        ov = _call(port, "GET", "/api/overview")[1]
        assert [(p["name"], p["kind"], p["section"]) for p in ov["plugins"]] == [
            ("box", "machine", "machine"), ("cloudy", "machine", "cloud"), ("distro", "machine", "os"),
            ("hyper", "machine", "virtualization"), ("wall", "machine", "machine"), ("bot", "assistant", "assistant")]
        assert _call(port, "GET", "/api/machines/cloudy")[1]["section"] == "cloud"
        assert _call(port, "GET", "/api/machines/hyper")[1]["section"] == "virtualization"
        assert _call(port, "GET", "/api/machines/distro")[1]["section"] == "os"
        assert _call(port, "GET", "/api/machines/box")[1]["section"] == "machine"
        assert {m["name"]: m["section"] for m in _call(port, "GET", "/api/status")[1]["machines"].values()} == {
            "box": "machine", "cloudy": "cloud", "distro": "os", "hyper": "virtualization", "wall": "machine"}
    finally:
        app.stop()


def test_the_page_draws_each_section_in_order_and_falls_back_without_one(served):
    app, port, lines, box = served
    js = _call(port, "GET", "/platform.js")[1]
    # the sections, in the list's order: the machine's own, virtualization, OS, cloud (then the AI assistants)
    assert (b"const SECTIONS = [['machine', 'Machine plugins'], ['virtualization', 'Virtualization plugins'], "
            b"['os', 'OS plugins'], ['cloud', 'Cloud plugins']];") in js
    # a section the page does not know, or none from an older server: Machine plugins
    assert b"const sectionOf = (m) => (SECTIONS.some(([s]) => s === m.section) ? m.section : 'machine');" in js
    assert b"section: p.section" in js  # a plugin not answered yet keeps its section
    draw = js[js.index(b"function drawList()"):js.index(b"function instancesTable()")]
    assert draw.index(b"SECTIONS.map(") < draw.index(b"<h4>AI assistants</h4>")
    assert b"None installed: WSL, firewall and admin plugins set this machine up." in draw  # no plugin at all
    page = js[js.index(b"function machineData()"):js.index(b"function tables(m)")]
    assert b"SECTIONS.map(" in page and b"None installed." in page and page.index(b"SECTIONS.map(") < page.index(b"instancesTable()")
    for note in (b"the hypervisors and container engines", b"the operating systems: WSL's distributions",
                 b"the cloud accounts the platform reads"):
        assert note in page, note
    assert b"isCloud" not in js  # the one section of 0.25.0 is one of four now
