"""The platform app on a free port: its page and icon, the machine's facts, the machine plugins and their
setup from the page (a thread, its lines), a command on one, the Docker instances, what is refused."""
from __future__ import annotations

import json
import time
from http.client import HTTPConnection

from liminal_libs.web import WRITE_HEADER

from liminal_libs.sources.plugin import PlatformPlugin

from conftest import _port
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
    assert status == 200 and wall["steps"] == ["enable", "exposure", "rules"] and wall["status"]["summary"] == "the wall: on (all on); 1 Liminal rule(s)"
    assert {"allow", "remove", "wanted", "status", "present"} <= set(wall["asks"]) and "setup" not in wall["asks"] and "run" not in wall["asks"]
    assert wall["enabled"] is True
    status, out = _call(port, "POST", "/api/machines/wall/ask", {"hook": "allow", "args": ["web", [8443]]})
    assert status == 200 and out["answer"]["label"] == "Liminal: web" and out["answer"]["ports"] == [8443]
    assert "web" in [r["name"] for r in _call(port, "GET", "/api/machines/wall")[1]["status"]["rules"]]
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
    asked_tray: list = []
    real_present = box.present
    box.present = lambda: asked_tray.append(1) or real_present()
    wall_asked: list = []
    wall = app.machines()["wall"]
    wall.present = lambda: wall_asked.append(1) or True
    status, m = _call(port, "POST", "/api/machines/box/enabled", {"on": True})
    assert status == 200 and m["enabled"] is True and m["status"]["present"] and box.app is app and asked
    assert app.active() == ["box", "wall"] and wall_asked == []  # the tray's list followed: no other plugin asked again
    assert [i["id"] for i in _call(port, "GET", "/api/tray")[1]["items"]] == ["platform", "box", "wall"]
    assert any("box disabled" in x for x in lines) and any("box enabled" in x for x in lines)


def test_a_plugin_not_valid_is_disabled_until_it_is(served):
    """The user: "if a plugin is not in a valid state it has to be disabled, and thus shaded out on the left side". Not
    valid (its own word, else not present), it is shown disabled with why, asked nothing it cannot answer, out of the
    tray, detached; its setup stays, being what makes it valid; valid again, it is active and attached."""
    app, port, lines, box = served
    assert app.attach_plugins([box]) == ["box"] and box.app is app
    box.present = lambda: False
    box.status = lambda: {"present": False, "summary": "not installed", "valid": False, "why": "no Liminal install: its setup installs it"}
    st = _call(port, "GET", "/api/status")[1]
    m = st["machines"]["box"]
    assert (m["enabled"], m["valid"], m["state"], m["why"], m["asks"]) == (True, False, "invalid", "no Liminal install: its setup installs it", [])
    assert box.app is None and st["active"] == ["wall"] and [i["id"] for i in _call(port, "GET", "/api/tray")[1]["items"]] == ["platform", "wall"]
    assert _call(port, "POST", "/api/machines/box/setup", {"steps": ["docker"]})[0] == 202  # its setup is what makes it valid
    for _ in range(50):
        if not _call(port, "GET", "/api/machines/box/setup")[1]["running"]:
            break
        time.sleep(0.05)
    box.present = lambda: True
    box.status = lambda: {"present": True, "summary": "installed"}
    m = _call(port, "GET", "/api/machines/box")[1]
    assert (m["valid"], m["state"], m["why"]) == (True, "active", "") and box.app is app and m["asks"]
    box.status = lambda: {"present": False, "summary": "not present"}  # without its own word: present or not
    m = _call(port, "GET", "/api/machines/box")[1]
    assert (m["state"], m["why"]) == ("invalid", "not present") and box.app is None


class Bot(PlatformPlugin):
    """A stand-in AI assistant: its key set or not, its plan with API access or not."""

    KIND = "assistant"
    name = "bot"
    title = "A bot"
    about = "a stand-in assistant"
    api = "2.1"
    vendor = "Bots"
    default_model = "bot-1"
    key_names = ("BOT_API_KEY", "BOT_ACCOUNT")

    def __init__(self):
        self.key, self.access = False, True

    def keys_set(self, settings):
        return self.key

    def served(self, settings):
        return self.key and self.access

    def free_note(self, settings):
        return "" if self.access else "the free plan has no API access"


def test_the_ai_assistants_are_valid_with_a_key_and_enabled_or_disabled():
    """The user: "theres also no disable or enable on the AI assistants": an assistant has the switch too, and is valid
    with its key set and a plan with API access; attached while both."""
    bot = Bot()
    app = PlatformApp(log=lambda m: None, machines={}, assistants={"bot": bot}, settings=lambda: object())
    port = _port(app.start(0))
    try:
        assert app.attach_plugins([bot]) == ["bot"]
        (a,) = _call(port, "GET", "/api/status")[1]["assistants"]
        assert (a["enabled"], a["valid"], a["state"], a["vendor"]) == (True, False, "invalid", "Bots")
        assert a["why"] == "no key: BOT_API_KEY is not set (the charts app's Plugins view sets it)" and bot.app is None
        bot.key = True
        (a,) = _call(port, "GET", "/api/status")[1]["assistants"]
        assert a["state"] == "active" and a["why"] == "" and bot.app is app
        bot.access = False
        assert app.assistant_status(bot)["why"] == "the free plan has no API access" and bot.app is None
        bot.access = True
        status, a = _call(port, "POST", "/api/plugins/bot/enabled", {"on": False})
        assert status == 200 and (a["state"], a["enabled"], a["valid"]) == ("disabled", False, None) and bot.app is None
        status, a = _call(port, "POST", "/api/plugins/bot/enabled", {"on": True})
        assert status == 200 and a["state"] == "active" and bot.app is app
        assert _call(port, "POST", "/api/plugins/nobody/enabled", {"on": True})[0] == 404
        assert _call(port, "POST", "/api/plugins/bot/enabled", {"on": 1})[0] == 400
    finally:
        app.stop()


from liminal_libs.machines import MachinePlugin  # noqa: E402
from liminal_libs.machines.terminal import Output  # noqa: E402


class Distro(MachinePlugin):
    """A stand-in WSL plugin: its check of this PC, its install streamed, its packages' update, its terminal."""

    name = "distro"
    title = "A distro"
    about = "a stand-in system"
    api = "2.1"
    order = 950
    STEPS = ("wsl", "distribution")
    HOOKS = (*MachinePlugin.HOOKS, "check", "update_packages", "terminal")

    def __init__(self):
        self.ready, self.installed, self.updates = False, False, 0

    def present(self):
        return self.installed

    def status(self):
        return {"present": self.installed, "summary": "installed" if self.installed else "not installed",
                "valid": self.installed, "why": "" if self.installed else "no Liminal install: its setup installs it"}

    def check(self):
        return {"ready": self.ready and not self.installed, "installed": self.installed, "distribution": "Liminal-Distro",
                "criteria": [{"name": "space", "title": "Room for it", "ok": self.ready, "detail": "plenty" if self.ready else "too little"}],
                "why": "" if self.ready else "Room for it: too little"}

    def setup(self, log=print, steps=None):
        for step in steps or self.STEPS:
            log.write(f"{step}: 50%\r{step}: 100%\n")  # what its commands print, as it comes
            log(f"distro: {step}: ok")
        if not steps or "distribution" in steps:
            self.installed = True
        return [{"step": step, "ok": True, "detail": "done"} for step in steps or self.STEPS]

    def update_packages(self, log=print):
        self.updates += 1
        log.write("Reading package lists... Done\n")
        log("distro: packages: ok")
        return [{"step": "packages", "ok": True, "detail": "up to date"}]

    def terminal(self, user=None):
        if not self.installed:
            raise RuntimeError("Liminal-Distro is not installed: install it first")
        return ["wsl", "-d", "Liminal-Distro"]


class FakeTerminal:
    """A login shell's stand-in: what it prints, the keys typed (echoed as a terminal does)."""

    def __init__(self, argv, title):
        self.argv, self.title, self.typed, self.closed = argv, title, "", False
        self.output = Output()
        self.output.write("liminal@pc:~$ ")
        self.seen = time.monotonic()

    @property
    def alive(self):
        return not self.closed

    def read(self, since=0, wait=0.0):
        self.waited = wait
        self.seen = time.monotonic()
        text, start, end = self.output.read(since)
        return {"text": text, "from": start, "offset": end, "alive": self.alive, "title": self.title}

    def write(self, data):
        self.typed += data
        self.output.write(data.replace("\r", "\r\n"))

    def close(self):
        self.closed = True


def _wait_job(port, name):
    for _ in range(100):
        got = _call(port, "GET", f"/api/machines/{name}/job?since=0")[1]
        if not got["running"]:
            return got
        time.sleep(0.02)
    raise AssertionError("the job did not end")


def test_the_install_is_locked_until_the_check_passes_and_streams_its_progress():
    """The user: "if the criteria are met according to the O/S, then the install method should be not locked out, after the
    install is run a terminal pops up in the plugin and shows the install progress, after the install is complete, the user
    can use the plugin to update the environment's packages"."""
    d = Distro()
    app = PlatformApp(log=lambda m: None, machines={"distro": d}, assistants={})
    port = _port(app.start(0))
    try:
        m = _call(port, "GET", "/api/machines/distro")[1]
        assert {"check", "update_packages", "terminal"} <= set(m["hooks"]) and m["state"] == "invalid" and m["terminal"] == {"open": False}
        c = _call(port, "GET", "/api/machines/distro/check")[1]
        assert (c["ready"], c["installed"], c["why"]) == (False, False, "Room for it: too little")
        status, refused = _call(port, "POST", "/api/machines/distro/job", {"action": "install"})
        assert status == 409 and "the install is locked: Room for it: too little" in refused["error"]
        assert _call(port, "POST", "/api/machines/distro/setup", {})[0] == 409  # everything is the install too
        assert _call(port, "POST", "/api/machines/distro/setup", {"steps": ["wsl"]})[0] == 202  # preparing this PC: never locked
        _wait_job(port, "distro")
        assert _call(port, "POST", "/api/machines/distro/job", {"action": "update"})[0] == 409  # not installed yet
        d.ready = True
        status, job = _call(port, "POST", "/api/machines/distro/job", {"action": "install"})
        assert status == 202 and job["action"] == "setup"
        done = _wait_job(port, "distro")
        assert done["ok"] is True and "distribution: 50%\rdistribution: 100%\n" in done["text"] and done["offset"] == len(done["text"])
        assert _call(port, "GET", f"/api/machines/distro/job?since={done['offset'] - 4}")[1]["text"] == done["text"][-4:]  # read on from an offset
        assert d.installed and _call(port, "GET", "/api/machines/distro/check")[1]["installed"] is True
        status, job = _call(port, "POST", "/api/machines/distro/job", {"action": "update"})
        assert status == 202 and job["action"] == "update"
        upd = _wait_job(port, "distro")
        assert upd["ok"] is True and upd["text"].startswith("Reading package lists... Done\n") and d.updates == 1
        assert _call(port, "POST", "/api/machines/distro/job", {"action": "reboot"})[0] == 400
    finally:
        app.stop()


def test_a_login_terminal_into_the_environment():
    """The user: "the plugin also allows for a user to login through a terminal in to the environment"."""
    d = Distro()
    made: list = []

    def terminal(argv, title):
        made.append(FakeTerminal(argv, title))
        return made[-1]
    app = PlatformApp(log=lambda m: None, machines={"distro": d}, assistants={}, terminal=terminal)
    port = _port(app.start(0))
    try:
        status, refused = _call(port, "POST", "/api/machines/distro/terminal", {})
        assert status == 409 and "not installed" in refused["error"] and made == []
        d.installed = True
        status, opened = _call(port, "POST", "/api/machines/distro/terminal", {})
        assert status == 200 and opened["text"] == "liminal@pc:~$ " and opened["alive"] and made[0].argv == ["wsl", "-d", "Liminal-Distro"]
        assert _call(port, "GET", "/api/machines/distro")[1]["terminal"] == {"open": True}
        assert _call(port, "POST", "/api/machines/distro/terminal/input", {"data": "ls\r"})[1] == {"sent": 3}
        got = _call(port, "GET", f"/api/machines/distro/terminal?since={opened['offset']}&wait=9")[1]
        assert got["text"] == "ls\r\n" and made[0].typed == "ls\r" and made[0].waited == 5.0  # held at most five seconds
        again = _call(port, "POST", "/api/machines/distro/terminal", {})[1]
        assert again["from"] == 0 and again["text"].endswith("ls\r\n")  # come back to: its last lines shown
        assert len(made) == 1  # the one open, kept
        assert _call(port, "POST", "/api/machines/distro/terminal/input", {"data": 5})[0] == 400
        assert _call(port, "POST", "/api/machines/distro/terminal/close", {})[1] == {"closed": True} and made[0].closed
        assert _call(port, "GET", "/api/machines/distro/terminal")[0] == 404
        assert _call(port, "POST", "/api/machines/distro/terminal/input", {"data": "x"})[0] == 409
    finally:
        app.stop()
