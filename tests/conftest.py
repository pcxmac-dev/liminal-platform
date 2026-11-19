from __future__ import annotations

import os
import socket
import subprocess
import time

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


def sock(proto="tcp", local="192.168.1.20", local_port=51000, remote="", remote_port=0, *, state="established",
         pid=4321, program="msedge.exe", started=None, seen=None) -> dict:
    """One socket as liminal-libs 1.65.0's socket readers give it (sockets' row): a stand-in. The addresses are the
    local network's and this machine's (never placed, so no GeoIP file is opened for them)."""
    return {"proto": proto, "family": 6 if ":" in local else 4, "state": state, "local": local,
            "local_port": local_port, "remote": remote, "remote_port": remote_port, "pid": pid,
            "pids": [pid] if pid else [], "program": program, "path": "", "service": "", "service_title": "",
            "user": "", "started": started, "process_started": None, "count": 1, "inode": 0,
            "seen": seen if seen is not None else started, "unread": {}}


def socket_table(rows) -> dict:
    """This machine's socket table as liminal-libs 1.65.0's sockets.read answers it, of the rows given: a stand-in."""
    return {"system": "windows", "at": time.time(), "awake": time.monotonic(), "took": 0.004, "root": False,
            "starts": True, "read": ("tcp4", "tcp6", "udp4", "udp6"), "cut": False, "rows": [dict(r) for r in rows],
            "notes": []}


class Wall(Firewall):
    """A stand-in firewall: its rules in memory; from liminal-libs 1.65.0 its Netstat over a stand-in socket table."""

    name = "wall"
    title = "A wall"
    about = "a stand-in firewall"
    api = "2.1"
    order = 901

    def __init__(self):
        self.rules = {"base": Rule("base", ports=(9000,), detail="a rule of Liminal's: the wall is valid")}
        self.sockets: list[dict] = []  # the rows its Netstat reads (sock's), none by default

    def make_netstat_view(self):
        """liminal-libs 1.65.0: its Netstat tab and hosts recording over a stand-in socket table of `sockets` (the
        guard, no_real_hosts, refuses this machine's), no name looked up; the hosts database and the layers in the
        test's own folder (the same guard's). A library before it never asks."""
        from liminal_libs.machines.netstat import NetstatView

        return NetstatView(self.name, reader=lambda: socket_table(self.sockets), names={},
                           login_of=lambda: getattr(self, "login", None))

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


@pytest.fixture(autouse=True)
def _none_of_this_users_saved_variables(monkeypatch):
    """Every test (0.33.0): an app a test builds with no login of its own makes the platform's, an EnvironmentLogin that
    reads this user's saved variables under the process's (saved_variables: on Windows the user's Environment key in
    the registry, secrets included), and from liminal-libs 1.65.0 a firewall attached to it asks that login for its
    hosts' recording. In a test it reads none of them: the process's environment alone, as the library's tests and a
    plugin's own login read it."""
    monkeypatch.setattr(app_module, "saved_variables", lambda: {})


HOSTS_VARIABLE = "LIMINAL_HOSTS_RECORDING"  # liminal-libs 1.65.0's hostbook.VARIABLE, named here for older libraries


@pytest.fixture(autouse=True)
def no_real_hosts(monkeypatch, tmp_path):
    """Every test (0.33.0; B-critique B1), as liminal-libs' own suite has it: from liminal-libs 1.65.0 a firewall reads
    its hosts' recording setting through its login when it is attached, and an app a test builds with no login reads
    this user's own variables (EnvironmentLogin with the saved ones under the process's), so once the user chose
    "always" the stand-in Wall attached here would start a thread reading this machine's socket table into this
    machine's own hosts database, beside the user's running platform. So each test runs with LIMINAL_HOSTS_RECORDING
    "shown" in its process (which wins over a saved one), the socket reader refused (a Reached again, noted and failed
    at the test's end: sockets.read, looked up when the code reads), and the hosts database, the GeoIP files (which
    place an internet host on the Netstat tab and the globe) and the infrastructure layers in the test's own folder;
    each book handed out there is let go after the test. Yields the reads refused, so the guard's own test can clear
    the one it made on purpose. A library before 1.65.0 has neither the reader nor the two: the variable and the GeoIP
    folder alone are set."""
    from liminal_libs import geo  # (every library the platform runs on has it: the World tab's places)

    monkeypatch.setenv(HOSTS_VARIABLE, "shown")
    monkeypatch.setattr(geo, "data_folder", lambda: tmp_path / "liminal-data" / geo.FOLDER)
    try:
        from liminal_libs import hostbook, sockets
        from liminal_libs.machines import infrastructure
    except ImportError:  # a library before 1.65.0: no firewall records hosts
        yield []
        return
    refused: list[str] = []

    def read(*args, **kwargs):
        refused.append(f"sockets.read {args[:1]!r}"[:300])
        raise Reached("the test read this machine's socket table for real: give the code a reader of its own")

    monkeypatch.setenv(hostbook.VARIABLE, "shown")  # the library's own name for it (HOSTS_VARIABLE today)
    monkeypatch.setattr(sockets, "read", read)
    monkeypatch.setattr(hostbook, "path", lambda: tmp_path / "liminal-data" / hostbook.FOLDER / hostbook.FILE)
    monkeypatch.setattr(hostbook, "_BOOKS", {})
    monkeypatch.setattr(infrastructure, "folder", lambda: tmp_path / "liminal-data" / infrastructure.FOLDER)
    yield refused
    for book in list(hostbook._BOOKS.values()):  # the books handed out in the test: written and let go
        try:
            book.close()
        except Exception:  # noqa: BLE001 - a test's own book that it broke on purpose
            pass
    assert not refused, f"the test read this machine's socket table for real: {refused}"


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
