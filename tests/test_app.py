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
    assert b"window.LiminalIcons" in _call(port, "GET", "/icons.js")[1] and _call(port, "GET", "/platform.js")[0] == 200
    status, tray = _call(port, "GET", "/api/tray")
    assert tray["app"] == "platform" and tray["icon"] == "chip" and tray["items"][0]["kind"] == "app"
    assert _call(port, "GET", "/api/app")[1]["port"] == 8775 and app.port() == 8775
    f = facts()
    assert f["cpus"] >= 1 and f["python"] and f["host"] and memory_mb() >= 0
    status, st = _call(port, "GET", "/api/status")
    assert status == 200 and st["machine"]["cpus"] == f["cpus"] and "docker" in st and st["app"]["icon"] == "chip"
    assert st["machines"]["box"]["status"]["engine"]["running"] and st["machines"]["box"]["setup"] is None
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
    assert _call(port, "GET", "/api/machines")[1]["machines"][0]["name"] == "box"
    assert _call(port, "GET", "/api/instances")[1]["instances"][0]["name"] == "box"
    # a write without the header is refused by the frame
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", "/api/machines/box/run", body=b"{}", headers={"Content-Type": "application/json"})
    assert conn.getresponse().status == 403


def test_the_registry_is_asked_when_no_machines_are_given():
    app = PlatformApp(log=lambda m: None)
    assert isinstance(app.machines(), dict) and isinstance(app.instances(), list)
