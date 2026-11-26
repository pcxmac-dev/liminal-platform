"""The suite's shared guard (tests/conftest.py, `no_outside`, as liminal-libs' own): a test that asks for it fails if
the code under test starts a process, opens, binds or listens on a socket, or resolves a name for real, and that code
cannot silence it. A file whose tests must reach nothing asks for it for all of them:
`pytestmark = pytest.mark.usefixtures("no_outside")`. The hosts' guard beside it (`no_real_hosts`, every test's, 0.33.0)
keeps a firewall the platform attaches from recording this machine's sockets by the user's own setting and from
placing a host by this machine's GeoIP files, and a third (`_none_of_this_users_saved_variables`, every test's, 0.33.0)
keeps an app built with no login from reading this user's saved variables (on Windows, the registry)."""
from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

from conftest import HOSTS_VARIABLE, Reached, Wall, sock

from liminal_platform.app import PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside")


def test_a_process_started_for_real_is_refused_and_cannot_be_swallowed(no_outside):
    def code_under_test():
        try:
            subprocess.Popen(["anything"])
        except Exception:  # noqa: BLE001 - the code's own handling, as in the platform
            return "swallowed"
        return "started"

    with pytest.raises(Reached):
        code_under_test()
    for reach in (lambda: subprocess.run(["anything"]), lambda: subprocess.check_output(["anything"])):
        with pytest.raises(Reached):
            reach()
    assert [r.split(" ")[0] for r in no_outside] == ["subprocess.Popen", "subprocess.run", "subprocess.check_output"]
    no_outside.clear()  # (this test reached them on purpose: the guard's own check at its end stays quiet)
    # the shell's ways are stood in too; not asked here, where a guard gone wrong would start a shell for real
    assert all(getattr(getattr(os, n), "__name__", "") == "stand_in" for n in ("system", "spawnv") if hasattr(os, n))


def _on_a_socket(method: str, *args):
    """What `s.<method>(...)` runs on any socket `s`, asked with no socket made at all."""
    getattr(socket.socket, method)(None, *args)


def test_a_connection_a_listener_or_a_lookup_for_real_is_refused(no_outside):
    for reach in (lambda: socket.create_connection(("127.0.0.1", 9)), lambda: socket.getaddrinfo("example.test", 443),
                  lambda: _on_a_socket("connect", ("127.0.0.1", 9)), lambda: _on_a_socket("bind", ("127.0.0.1", 0)),
                  lambda: _on_a_socket("listen")):
        with pytest.raises(Reached):
            reach()
    assert [r.split(" ")[0] for r in no_outside] == ["socket.create_connection", "socket.getaddrinfo",
                                                     "socket.socket.connect", "socket.socket.bind",
                                                     "socket.socket.listen"]
    no_outside.clear()


def test_a_stand_in_handed_to_the_code_is_untouched():
    calls = []
    run = lambda argv, **kw: calls.append(argv) or 0  # noqa: E731 - a stand-in, as the platform's tests hand them
    assert run(["x"]) == 0 and calls == [["x"]]


def test_a_firewall_the_platform_attaches_under_a_login_that_says_always_starts_nothing_real(no_real_hosts, tmp_path):
    """0.33.0 (B-critique B1): the suite builds its apps with no login given, so with the platform's own (reading the
    process's variables, and the user's saved ones but in a test), and attaches its stand-in Wall, a Firewall, which
    from liminal-libs 1.65.0 reads its hosts' recording setting through the login the platform lends it. Here the
    user's saved variables say LIMINAL_HOSTS_RECORDING=always (what the Recording form keeps on Windows): the guard's
    "shown" in the test's process wins (the process's own variable over a saved one), so nothing records; the socket
    table its view would read is the guard's refusal, and the hosts database, the GeoIP files and the layers are in
    the test's own folder. Asked of the app directly: nothing served, no port opened."""
    hostbook = pytest.importorskip("liminal_libs.hostbook", reason="a library before 1.65.0 records no hosts")
    from liminal_libs import geo, sockets
    from liminal_libs.apps import EnvironmentLogin
    from liminal_libs.machines import infrastructure
    from liminal_libs.machines.firewall import Firewall

    class Bare(Wall):  # its Netstat as the Firewall base makes it: this machine's socket table, the data folder's book
        make_netstat_view = Firewall.make_netstat_view

    assert hostbook.VARIABLE == HOSTS_VARIABLE and os.environ[HOSTS_VARIABLE] == "shown"
    saved = {HOSTS_VARIABLE: "always"}
    login = EnvironmentLogin(saved=lambda: dict(saved))  # the platform's own login, as it reads this user's variables
    assert EnvironmentLogin(env=dict(saved)).variables([HOSTS_VARIABLE]) == saved  # unguarded, it would say always
    wall = Bare()
    app = PlatformApp(log=lambda m: None, login=login, machines={"wall": wall}, assistants={})
    try:
        assert app.attach_plugins([wall]) == ["wall"] and wall.app is app
        view = wall.netstat_view(make=False)  # made as the Wall was attached, its recording following its setting
        assert view is not None and view.mode() == "shown" and not view.recording()
        assert not [t for t in threading.enumerate() if t.name.endswith("-hosts")]
        with pytest.raises(Reached, match="socket table for real"):
            view.touch()  # the reader the Firewall base makes its view with: the guard's
        assert no_real_hosts == ["sockets.read ()"]
        no_real_hosts.clear()  # (read on purpose: the guard's own check at the end stays quiet)
        assert hostbook.path().is_relative_to(tmp_path) and infrastructure.folder().is_relative_to(tmp_path)
        assert view.book.path.is_relative_to(tmp_path) and view.index.folder.is_relative_to(tmp_path)
        assert geo.data_folder().is_relative_to(tmp_path) and (wall.world_view(make=False) is None  # 1.105.0: no view
                                                                    or wall.world_view().folder.is_relative_to(tmp_path))
        assert not hostbook.path().exists()  # nothing was kept
    finally:
        app.detach("wall")
        app.stop()
    assert view.closed and not view.recording()
    with pytest.raises(Reached):
        sockets.read("windows")  # whichever system it is asked for
    no_real_hosts.clear()


def test_an_app_built_with_no_login_reads_none_of_this_users_saved_variables(monkeypatch):
    """0.33.0: an app a test builds with no login of its own makes the platform's, an EnvironmentLogin that reads the
    user's saved variables under the process's (on Windows their Environment key in the registry, secrets included),
    and a firewall attached to it asks that login for its hosts' recording. In a test it reads the process's alone
    (the guard, _none_of_this_users_saved_variables). The registry's way in is stood in here by one that notes each
    key opened and refuses it, so nothing of the registry is read either way; off Windows there is none to read.
    Asked of the app directly: nothing served, no port opened."""
    opened: list[str] = []
    if os.name == "nt":
        import winreg

        def refuse(key, sub_key, *args, **kwargs):
            opened.append(str(sub_key))
            raise OSError("the test opened this user's registry for real")
        monkeypatch.setattr(winreg, "OpenKey", refuse)
    app = PlatformApp(log=lambda m: None, machines={}, assistants={})  # no login given: the platform's own
    try:
        assert app.login.variables([HOSTS_VARIABLE]) == {HOSTS_VARIABLE: "shown"}  # the process's: the hosts' guard's
        assert "liminal-hosts-recording" in app.login.names()  # (its pair's name)
    finally:
        app.stop()
    assert opened == []


def test_a_host_on_the_internet_is_placed_by_the_tests_own_geoip_folder_alone(monkeypatch, tmp_path):
    """0.33.0: a connection to a host on the internet sends the Netstat tab to the plugin's GeoIP file for its place
    (WorldView.geoip: the data folder's geoip/ unless the plugin names a folder of its own); in a test that folder is
    the test's own (the hosts' guard, no_real_hosts), never this machine's. The file is looked for by a stand-in that
    notes where and finds none, so no GeoIP file is opened either way. The address is MaxMind's own test address; no
    name is looked up and nothing is reached. Asked of the app directly: nothing served, no port opened, no socket
    table read but the stand-in."""
    pytest.importorskip("liminal_libs.machines.netstat", reason="a library before 1.65.0 has no Netstat tab")
    from liminal_libs import geo

    looked: list = []
    monkeypatch.setattr(geo.GeoIP, "find", classmethod(lambda cls, folder=None, *args, **kw: looked.append(folder)))
    from liminal_libs.machines.firewall import Firewall

    wall = Wall()
    wall.sockets = [sock(remote="81.2.69.142", remote_port=443, started=time.time() - 60)]
    machines = {"wall": wall}
    if not callable(getattr(Firewall, "world", None)):  # 0.39.2, liminal-libs 1.105.0: the places are the World Wide
        from test_worldwideweb import Web  # Web plugin's, its GeoIP folder the data folder's (the guard's)
        machines["worldwideweb"] = Web(None)
    app = PlatformApp(log=lambda m: None, machines=machines, assistants={}, state=tmp_path / "platform")
    app.attach_plugins(list(machines.values()))
    try:
        status, out = app.api(None, "POST", "/api/machines/wall/ask", {}, {"hook": "netstat", "args": []})
    finally:
        app.stop()
    assert status == 200 and len(out["answer"]["flows"]["rows"]) == 1
    assert looked and all(Path(folder).is_relative_to(tmp_path) for folder in looked), looked
