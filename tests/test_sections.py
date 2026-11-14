"""0.25.0 (the user, 2026-11-14: "classify the cloud plugins under the 'cloud plugins' section which should be on the far
left"): each machine plugin's overview row and status say its section, "cloud" for a cloud provider's account (liminal-libs
1.51.0's MachinePlugin.SECTION) and "machine" otherwise. The page's list and the machine's own page draw a Cloud plugins
section from it, and a server that sends no section draws every plugin under Machine plugins. Stand-in plugins on a free
port: nothing of this machine is asked."""
from __future__ import annotations

from conftest import Box, Wall, _port
from test_app import Bot, _call

from liminal_platform.app import PlatformApp, section_of


class Cloudy(Box):
    """A stand-in cloud provider's account."""

    name = "cloudy"
    title = "A cloud account"
    ICON = "digitalocean"
    SECTION = "cloud"


class Odd(Box):
    """A plugin naming a section the platform does not draw."""

    name = "odd"
    title = "An odd box"
    SECTION = "elsewhere"


def test_a_plugin_says_its_section_and_anything_else_is_a_machine_plugin():
    assert (section_of(Cloudy()), section_of(Box()), section_of(Wall()), section_of(Odd())) == ("cloud", "machine", "machine", "machine")
    assert section_of(object()) == "machine"  # an older library's plugin, with no SECTION at all


def test_the_overview_and_each_status_carry_the_section():
    app = PlatformApp(log=lambda m: None, machines={"box": Box(), "cloudy": Cloudy(), "wall": Wall()}, assistants={"bot": Bot()},
                      settings=lambda: object())
    port = _port(app.start(0))
    try:
        ov = _call(port, "GET", "/api/overview")[1]
        assert [(p["name"], p["kind"], p["section"]) for p in ov["plugins"]] == [
            ("box", "machine", "machine"), ("cloudy", "machine", "cloud"), ("wall", "machine", "machine"), ("bot", "assistant", "assistant")]
        assert _call(port, "GET", "/api/machines/cloudy")[1]["section"] == "cloud"
        assert _call(port, "GET", "/api/machines/box")[1]["section"] == "machine"
        assert {m["name"]: m["section"] for m in _call(port, "GET", "/api/status")[1]["machines"].values()} == {
            "box": "machine", "cloudy": "cloud", "wall": "machine"}
    finally:
        app.stop()


def test_the_page_draws_a_cloud_section_and_falls_back_without_one(served):
    app, port, lines, box = served
    js = _call(port, "GET", "/platform.js")[1]
    for part in (b"const isCloud = (m) => m.section === 'cloud';", b"<h4>Cloud plugins</h4>", b"section: p.section",
                 b"machines = all.filter((m) => !isCloud(m)), clouds = all.filter(isCloud)"):
        assert part in js, part
    # the order on the left: this machine, the machine plugins, the cloud plugins, the AI assistants
    draw = js[js.index(b"function drawList()"):]
    assert draw.index(b"<h4>Machine plugins</h4>") < draw.index(b"<h4>Cloud plugins</h4>") < draw.index(b"<h4>AI assistants</h4>")
