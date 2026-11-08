from __future__ import annotations

import pytest

from liminal_libs import docker as docker_mod
from liminal_libs.docker import Instance
from liminal_libs.machines import MachinePlugin

from liminal_platform.app import PlatformApp


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


@pytest.fixture(autouse=True)
def _no_docker_or_wsl_here(monkeypatch):
    """The tests never ask this machine's Docker or WSL: GitHub's runners have Docker installed, this PC
    has WSL; the instances and the description then hold only what a test puts there."""
    monkeypatch.setattr(docker_mod.shutil, "which", lambda name: None)
    monkeypatch.setattr(docker_mod, "wsl", lambda: None)


def _port(url: str) -> int:
    return int(url.split("127.0.0.1:", 1)[1].split("/", 1)[0])


@pytest.fixture
def served():
    lines: list[str] = []
    box = Box()
    app = PlatformApp(log=lines.append, machines={"box": box})
    url = app.start(0)
    yield app, _port(url), lines, box
    app.stop()
