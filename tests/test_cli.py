"""The command line: status, one machine's status, setup and a command, through a stand-in registry."""
from __future__ import annotations

from liminal_platform import cli
from liminal_platform.app import PlatformApp

from conftest import Box


def test_status_and_a_machine_from_the_command_line(monkeypatch, capsys):
    box = Box()
    monkeypatch.setattr(cli, "_app", lambda log=print: PlatformApp(log=lambda m: None, machines={"box": box}))
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "cpus" in out and "box: A box; present; Docker inside running (28.1.1)" in out and "instance box: the box (box docker)" in out
    assert cli.main(["machine", "box", "status"]) == 0 and '"present": true' in capsys.readouterr().out
    assert cli.main(["machine", "box", "setup", "docker", "engine"]) == 0 and box.setups[-1] == ["docker", "engine"]
    assert "box: docker: ok" in capsys.readouterr().out
    assert cli.main(["machine", "box", "run", "--", "ls", "/"]) == 0 and capsys.readouterr().out == "ran ls /\n"
    assert cli.main(["machine", "box", "run"]) == 2
    assert cli.main(["machine", "box", "instances"]) == 0 and '"name": "box"' in capsys.readouterr().out
    assert cli.main(["machine", "nothing", "status"]) == 2 and "no machine plugin named" in capsys.readouterr().err


def test_a_machine_disabled_and_enabled_from_the_command_line(monkeypatch, capsys):
    box = Box()
    monkeypatch.setattr(cli, "_app", lambda log=print: PlatformApp(log=lambda m: None, machines={"box": box}))
    assert cli.main(["machine", "box", "disable"]) == 0 and capsys.readouterr().out == "box: disabled\n"
    assert cli.main(["status"]) == 0 and "box: A box; disabled" in capsys.readouterr().out
    assert cli.main(["machine", "box", "setup"]) == 2 and "box is disabled" in capsys.readouterr().err and box.setups == []
    assert cli.main(["machine", "box", "enable"]) == 0 and capsys.readouterr().out == "box: enabled\n"
    assert cli.main(["status"]) == 0 and "box: A box; present" in capsys.readouterr().out
