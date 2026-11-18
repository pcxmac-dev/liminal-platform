from __future__ import annotations

import os
import socket
import subprocess

import pytest

from liminal_libs import docker as docker_mod
from liminal_libs.apps import Refused
from liminal_libs.docker import Instance
from liminal_libs.machines import MachinePlugin
from liminal_libs.machines.terminal import Output

import liminal_platform.app as app_module
from liminal_platform.app import PlatformApp


class Reached(BaseException):
    """A test reached for real what it must stand in for."""


@pytest.fixture
def no_outside(monkeypatch):
    """No process started, no socket opened, bound or listened on, no name resolved for real (liminal-libs' shared
    guard, for the platform's own tests): a reach raises Reached, a BaseException that no `except Exception` of the code
    under test swallows, and is noted, so it fails the test at its end even if something caught that. A file whose tests
    must reach nothing asks for it for all of them: `pytestmark = pytest.mark.usefixtures("no_outside")`; one that
    serves the page (`served` below: a listener on 127.0.0.1) cannot. It bites where the code looks the names up when it
    runs (`subprocess.Popen`, `socket.create_connection`), not where a module bound one when it was imported."""
    reached: list[str] = []

    def refuse(what):
        def stand_in(*args, **kwargs):
            reached.append(f"{what} {args[:2]!r}"[:300])
            raise Reached(f"the test reached {what} for real: give the code a stand-in")
        return stand_in

    for name in ("Popen", "run", "call", "check_call", "check_output", "getoutput", "getstatusoutput"):
        monkeypatch.setattr(subprocess, name, refuse(f"subprocess.{name}"))
    for name in ("system", "startfile", "posix_spawn", "posix_spawnp", "spawnv", "spawnve", "spawnvp", "spawnvpe"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, refuse(f"os.{name}"))
    for name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex"):
        monkeypatch.setattr(socket, name, refuse(f"socket.{name}"))
    for name in ("connect", "connect_ex", "sendto", "bind", "listen"):
        monkeypatch.setattr(socket.socket, name, refuse(f"socket.socket.{name}"))
    yield reached
    assert not reached, f"the test reached the outside for real: {reached}"


class Box(MachinePlugin):
    name = "box"
    title = "A box"
    about = "a stand-in machine with Docker inside"
    api = "2.1"
    order = 900

    def __init__(self):
        self.ran: list = []
        self.setups: list = []

    def present(self) -> bool:
        return True

    def status(self) -> dict:
        return {"present": True, "state": "Running", "version": "2", "engine": {"installed": True, "version": "28.1.1", "running": True}}

    def setup(self, log=print, steps=None):
        self.setups.append(steps)
        for s in (steps or ("docker", "engine")):
            log(f"box: {s}: ok")
        return [{"step": s, "ok": True, "detail": "done"} for s in (steps or ("docker", "engine"))]

    def run(self, *command, **options):
        self.ran.append(command)
        if command[0] == "false":
            raise RuntimeError("it failed")
        return "ran " + " ".join(command) + "\n"

    def instances(self):
        return (Instance("box", "the box", command="box docker", source="box"),)


from liminal_libs.machines.firewall import Firewall, Rule  # noqa: E402


class Wall(Firewall):
    """A stand-in firewall: its rules in memory."""

    name = "wall"
    title = "A wall"
    about = "a stand-in firewall"
    api = "2.1"
    order = 901

    def __init__(self):
        self.rules = {"base": Rule("base", ports=(9000,), detail="a rule of Liminal's: the wall is valid")}

    def present(self):
        return True

    def backend(self):
        return "the wall"

    def state(self):
        return {"enabled": True, "profiles": {"all": True}}

    def list_rules(self, owned_only=True):
        return list(self.rules.values())

    def add_rule(self, rule):
        self.rules[rule.name] = rule

    def delete_rule(self, name):
        return self.rules.pop(name, None) is not None

    def enable(self):
        pass

    def exposing(self, ports):
        return []

    def wanted(self):
        return []


@pytest.fixture(autouse=True)
def _no_docker_or_wsl_here(monkeypatch):
    """The tests never ask this machine's Docker or WSL: GitHub's runners have Docker installed, this PC
    has WSL; the instances and the description then hold only what a test puts there."""
    monkeypatch.setattr(docker_mod.shutil, "which", lambda name: None)
    monkeypatch.setattr(docker_mod, "wsl", lambda: None)


@pytest.fixture(autouse=True)
def _folders_of_the_tests_own(monkeypatch, tmp_path):
    """The platform's folder (which plugins are disabled) and the UI's preferences: the test's own, never this
    machine's."""
    monkeypatch.setenv("LIMINAL_PLATFORM_DIR", str(tmp_path / "platform"))
    monkeypatch.setenv("LIMINAL_UI_FILE", str(tmp_path / "ui.json"))
    monkeypatch.setenv("LIMINAL_PLATFORM_LOGIN_URL", "none")  # no login app reached or started (a test sets a stand-in)


def _port(url: str) -> int:
    return int(url.split("127.0.0.1:", 1)[1].split("/", 1)[0])


@pytest.fixture
def served():
    lines: list[str] = []
    box = Box()
    app = PlatformApp(log=lines.append, machines={"box": box, "wall": Wall()}, assistants={})  # none of this PC's
    url = app.start(0)
    yield app, _port(url), lines, box
    app.stop()


def api_answer(app, method: str, path: str, body=None, query=None):
    """The app asked as its server asks it (no server runs): its status and answer; a Refused raised is its status with
    {"error": its reason}."""
    try:
        status, data, *_ = app.api(None, method, path, query or {}, None if method == "GET" else (body or {}))
    except Refused as e:
        return e.status, {"error": e.reason}
    return status, data


class Cancellable(Output):
    """A job's output that takes a cancel as liminal-libs 1.62.0's does (`cancel()` sets the flag the work looks at,
    `cancelled`), for a run on an older library, whose own takes none."""

    asked = False

    def cancel(self):
        self.asked = True

    @property
    def cancelled(self):
        return self.asked


@pytest.fixture
def an_output_that_takes_a_cancel(monkeypatch):
    """The library's own Output from 1.62.0 on; before it, Cancellable in its place, so what the platform does with a
    job's cancel is tested on every library it runs on."""
    if not callable(getattr(Output, "cancel", None)):
        monkeypatch.setattr(app_module, "Output", Cancellable)


class Served(MachinePlugin):
    """A stand-in that runs a server of its own: told that the platform stops, it ends it (here: it notes that it was
    told), as often as it is told. `signals` (test_signals' stand-in signal module): a signal sent to the platform again
    while it is told (another SIGTERM, its terminal closing)."""

    name, title, about, api, order = "served", "Served", "a stand-in with a server to end", "2.2", 914

    def __init__(self, told: list, signals=None):
        self.told, self.signals = told, signals

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "serving", "why": ""}

    def app_stopping(self):
        if self.signals is not None:
            self.signals.send(15)
            self.signals.send(1)
        self.told.append(self.name)


class Other(Served):
    name, title = "other", "Another"


def page_script() -> str:
    """The page's script, read from the folder the platform serves it from (no port is opened for its text)."""
    return (PlatformApp.STATIC / "platform.js").read_text(encoding="utf-8")


def script_part(script: str, start: str, end: str = "\n  }") -> str:
    """The script from `start` up to the next `end`: one function's own lines (the page's functions close at two
    spaces)."""
    at = script.index(start)
    return script[at:script.index(end, at)]
