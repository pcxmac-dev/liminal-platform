"""The platform app on a free port: its page and icon, the machine's facts, the machine plugins and their
setup from the page (a thread, its lines), a command on one, the Docker instances, what is refused."""
from __future__ import annotations

import json
import time
from http.client import HTTPConnection

from liminal_libs.web import WRITE_HEADER

from liminal_platform.app import PlatformApp, facts, memory_mb


def _call(port, method, path, body=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    h = {}
    if body is not None:
        h["Content-Type"] = "application/json"
    if method != "GET":
        h.setdefault(WRITE_HEADER, "1")
    conn.request(method, path, body=None if body is None else json.dumps(body).encode(), headers=h)
    r = conn.getresponse()
    raw = r.read()
    try:
        data = json.loads(raw)
    except ValueError:
        data = raw
    return r.status, data


def test_the_page_its_icon_and_the_machine(served):
    app, port, lines, box = served
    status, body = _call(port, "GET", "/")
    assert status == 200 and b'id="railChip"' in body and b"<title>Liminal Platform</title>" in body
    # the list, the selected one's data, its specifics before the tray (the user's layout)
    for part in (b'class="app-main cols"', b'class="app-list" id="list"', b'class="app-data" id="data"', b'class="app-side" id="side"'):
        assert part in body
    assert b"window.LiminalIcons" in _call(port, "GET", "/icons.js")[1] and _call(port, "GET", "/platform.js")[0] == 200
    # the library's charts, menu and theme beside it; the theme first in the body, so the page is painted in it at once
    assert b"window.LiminalCharts" in _call(port, "GET", "/charts.js")[1] and b"window.LiminalMenu" in _call(port, "GET", "/menu.js")[1]
    assert b"window.LiminalTheme" in _call(port, "GET", "/theme.js")[1] and body.index(b'src="theme.js"') < body.index(b'id="main"')
    assert body.index(b'src="charts.js"') < body.index(b'src="platform.js"') and body.index(b'src="menu.js"') < body.index(b'src="platform.js"')
    status, look = _call(port, "GET", "/api/ui")
    assert status == 200 and look["theme"] == "dark" and len(look["themes"]) == 5  # the UI's preferences, the frame's
    status, tray = _call(port, "GET", "/api/tray")
    assert tray["app"] == "platform" and tray["icon"] == "chip" and tray["items"][0]["kind"] == "app"
    # the active plugins after the chip, each with its icon
    assert [(i["id"], i["icon"], i["kind"], i["app"]) for i in tray["items"][1:]] == [("box", "chip", "plugin", "platform"),
                                                                                   ("wall", "shield", "plugin", "platform")]
    assert _call(port, "GET", "/api/app")[1]["port"] == 8775 and app.port() == 8775
    f = facts()
    assert f["cpus"] >= 1 and f["python"] and f["host"] and memory_mb() >= 0
    status, st = _call(port, "GET", "/api/status")
    assert status == 200 and st["machine"]["cpus"] == f["cpus"] and st["app"]["icon"] == "chip"
    assert st["docker"]["installed"] is False and st["docker"]["available"] is False  # no Docker here, as the fixture says
    assert st["machines"]["box"]["status"]["engine"]["running"] and st["machines"]["box"]["setup"] is None and "wall" in st["machines"]
    assert st["active"] == ["box", "wall"] and st["machines"]["wall"]["icon"] == "shield" and st["assistants"] == []
    assert st["instances"] == [{"name": "box", "where": "the box", "command": "box docker", "context": "", "host": "", "source": "box"}]
    assert any("its page at" in m for m in lines)


def test_a_machine_is_set_up_from_the_page_and_runs_a_command(served):
    app, port, lines, box = served
    status, m = _call(port, "GET", "/api/machines/box")
    assert status == 200 and m["title"] == "A box" and m["status"]["present"]
    assert _call(port, "GET", "/api/machines/nothing")[0] == 404
    status, started = _call(port, "POST", "/api/machines/box/setup", {"steps": ["docker"]})
    assert status == 202 and started["machine"] == "box" and started["steps"] == ["docker"]
    for _ in range(50):
        status, s = _call(port, "GET", "/api/machines/box/setup")
        if not s["running"]:
            break
        time.sleep(0.05)
    assert s["ok"] is True and s["lines"] == ["box: docker: ok"] and s["done"] == [{"step": "docker", "ok": True, "detail": "done"}] and box.setups == [("docker",)]
    assert _call(port, "POST", "/api/machines/box/setup", {"steps": "docker"})[0] == 400
    status, out = _call(port, "POST", "/api/machines/box/run", {"command": ["ls", "/"]})
    assert status == 200 and out["output"] == "ran ls /\n" and box.ran[-1] == ("ls", "/")
    assert _call(port, "POST", "/api/machines/box/run", {"command": ["false"]})[0] == 502
    assert _call(port, "POST", "/api/machines/box/run", {"command": []})[0] == 400
    assert [m["name"] for m in _call(port, "GET", "/api/machines")[1]["machines"]] == ["box", "wall"]
    assert _call(port, "GET", "/api/instances")[1]["instances"][0]["name"] == "box"
    # a write without the header is refused by the frame
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", "/api/machines/box/run", body=b"{}", headers={"Content-Type": "application/json"})
    assert conn.getresponse().status == 403


def test_a_plugins_steps_summary_and_asks_by_name(served):
    app, port, lines, box = served
    status, wall = _call(port, "GET", "/api/machines/wall")
    assert status == 200 and wall["steps"] == ["enable", "exposure", "rules"] and wall["status"]["summary"] == "the wall: on (all on); 0 Liminal rule(s)"
    assert {"allow", "remove", "wanted", "status", "present"} <= set(wall["asks"]) and "setup" not in wall["asks"] and "run" not in wall["asks"]
    assert wall["enabled"] is True
    status, out = _call(port, "POST", "/api/machines/wall/ask", {"hook": "allow", "args": ["web", [8443]]})
    assert status == 200 and out["answer"]["label"] == "Liminal: web" and out["answer"]["ports"] == [8443]
    assert _call(port, "GET", "/api/machines/wall")[1]["status"]["rules"][0]["name"] == "web"
    assert _call(port, "POST", "/api/machines/wall/ask", {"hook": "remove", "args": ["web"]})[1] == {"answer": True}
    assert _call(port, "POST", "/api/machines/wall/ask", {"hook": "setup", "args": []})[0] == 400  # its own route
    assert _call(port, "POST", "/api/machines/wall/ask", {"hook": "allow", "args": ["Bad Name", [1]]})[0] == 400
    assert _call(port, "POST", "/api/machines/wall/ask", {"hook": "allow", "args": "x"})[0] == 400
    assert any("wall asked allow web" in m for m in lines)
    assert _call(port, "POST", "/api/machines/wall/ask", {"hook": "wanted", "args": []})[0] == 200
    assert not any("asked wanted" in m for m in lines)  # what only reads is not logged
    assert _call(port, "GET", "/api/machines/box")[1]["steps"] == []  # a plugin without steps offers none


def test_a_plugin_not_present_stays_out_of_the_tray(served):
    app, port, lines, box = served
    box.present = lambda: False
    assert app.active(fresh=True) == ["wall"] and [i.id for i in app.items()] == ["wall"]
    assert [i["id"] for i in _call(port, "GET", "/api/tray")[1]["items"]] == ["platform", "wall"]


def test_the_registry_is_asked_when_no_machines_are_given():
    app = PlatformApp(log=lambda m: None)
    assert isinstance(app.machines(), dict) and isinstance(app.instances(), list)


def test_a_plugin_disabled_and_enabled_again(served):
    """The tray's right click and the switch on a plugin's page: disabled, the platform asks it nothing, its icon
    leaves the tray, it is detached; kept across restarts; enabled, attached again."""
    app, port, lines, box = served
    asked: list = []
    real = box.status
    box.status = lambda: asked.append(1) or real()
    assert app.attach_plugins([box]) == ["box"] and box.app is app
    status, m = _call(port, "POST", "/api/machines/box/enabled", {"on": False})
    assert status == 200 and m["enabled"] is False and m["status"]["present"] is None and m["asks"] == [] and m["name"] == "box"
    assert box.app is None and app.plugin("box") is None  # detached: a plugin that samples stops
    asked.clear()
    st = _call(port, "GET", "/api/status")[1]
    assert st["disabled"] == ["box"] and st["machines"]["box"]["enabled"] is False and asked == [] and st["active"] == ["wall"]
    assert [i["id"] for i in _call(port, "GET", "/api/tray")[1]["items"]] == ["platform", "wall"] and st["instances"] == []
    assert _call(port, "POST", "/api/machines/box/ask", {"hook": "present", "args": []})[0] == 409
    assert _call(port, "POST", "/api/machines/box/setup", {})[0] == 409
    assert _call(port, "POST", "/api/machines/box/run", {"command": ["ls"]})[0] == 409
    assert _call(port, "POST", "/api/machines/box/enabled", {"on": "no"})[0] == 400
    assert _call(port, "POST", "/api/machines/nothing/enabled", {"on": True})[0] == 404
    # kept in the platform's own folder: a restarted platform leaves it detached
    assert json.loads((app.state_dir / "plugins.json").read_text(encoding="utf-8")) == {"disabled": ["box"]}
    again = PlatformApp(log=lambda m: None, machines={"box": box})
    assert again.disabled() == {"box"} and again.attach_plugins([box]) == [] and box.app is None
    status, m = _call(port, "POST", "/api/machines/box/enabled", {"on": True})
    assert status == 200 and m["enabled"] is True and m["status"]["present"] and box.app is app and asked
    assert [i["id"] for i in _call(port, "GET", "/api/tray")[1]["items"]] == ["platform", "box", "wall"]
    assert any("box disabled" in x for x in lines) and any("box enabled" in x for x in lines)
