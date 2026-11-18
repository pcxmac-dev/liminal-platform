"""The suite's shared guard (tests/conftest.py, `no_outside`, as liminal-libs' own): a test that asks for it fails if
the code under test starts a process, opens, binds or listens on a socket, or resolves a name for real, and that code
cannot silence it. A file whose tests must reach nothing asks for it for all of them:
`pytestmark = pytest.mark.usefixtures("no_outside")`."""
from __future__ import annotations

import os
import socket
import subprocess

import pytest

from conftest import Reached

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
