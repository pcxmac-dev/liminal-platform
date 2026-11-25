"""0.35.0 (Monday list item 38; the shutdown audit of 2026-11-24: told one after another, the platform's plugins took
about 54 s and more): the platform's stop tells its plugins together, under one deadline (PLUGINS_DEADLINE_S, about
10 s) and a short grace, through the library's App.terminate with the platform's parts (its job runner, then its
plugins); the whole stop ends within its deadline, and a plugin that ignores the stop is late at it and what was
started for it is killed with its trees.

Stand-in plugins and processes only (lifecycle.standins: a table of stand-ins that is its own killer, a ledger in
memory): nothing is served, started or signalled."""
from __future__ import annotations

import os
import threading
import time

import pytest

from liminal_libs import lifecycle
from liminal_libs.lifecycle import FakeTable, MemoryLedger, Proc, Row
from liminal_libs.machines import MachinePlugin

import liminal_platform.app as app_module
from liminal_platform.app import PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside")


class Together(MachinePlugin):
    """A stand-in whose stop waits for the other one's at the same time: told one after another, they never meet."""

    api, order = "2.2", 930

    def __init__(self, name: str, met: threading.Barrier, told: list):
        self.name, self.title, self.about = name, name.title(), "a stand-in told with another"
        self.met, self.told = met, told

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "", "why": ""}

    def app_stopping(self):
        self.met.wait()  # BrokenBarrierError when the other is not being told meanwhile
        self.told.append(self.name)


class Stubborn(Together):
    """A stand-in that ignores the stop: its app_stopping does not return until the test lets it."""

    def __init__(self, released: threading.Event):
        super().__init__("stubborn", threading.Barrier(1), [])
        self.released = released

    def app_stopping(self):
        self.released.wait(30)


def test_the_plugins_are_told_together_and_one_that_ignores_the_stop_is_killed_at_its_deadline(monkeypatch):
    monkeypatch.setattr(app_module, "PLUGINS_DEADLINE_S", 0.5)
    met, told, lines = threading.Barrier(2, timeout=5), [], []
    released = threading.Event()
    machines = {"first": Together("first", met, told), "second": Together("second", met, told),
                "stubborn": Stubborn(released)}
    app = PlatformApp(log=lines.append, machines=machines, assistants={})
    app.STOP_GRACE_S = 0.1
    app.stop_timeout = 2.0
    assert app.attach_plugins([machines["first"]]) == ["first"]  # one told through its own signal, the rest not attached
    # what was started for the stubborn one (lifecycle.spawn's row): a process that ignores TERM
    pid = 990_001
    table, ledger = FakeTable([Proc(pid, os.getpid(), "model-server", "model-server --serve", 77)], ignores=[pid]), \
        MemoryLedger()
    stopper = threading.Thread(target=app.stop, daemon=True)
    with lifecycle.standins(table=table, killer=table, ledger=ledger):
        lifecycle.note(Row(pid=pid, started=77, owner="stubborn", owner_pid=os.getpid(), owner_started=1,
                           kind="model server", command=["model-server", "--serve"]), ledger)
        began = time.monotonic()
        try:
            stopper.start()
            stopper.join(10)
            took = time.monotonic() - began
            assert not stopper.is_alive(), "the stop waited on a plugin that ignores it"
        finally:
            released.set()
            stopper.join(10)
    assert sorted(told) == ["first", "second"]  # together: each met the other while being told
    assert took < app.stop_timeout + 1.0  # within the whole stop's deadline (and a test's margin)
    assert (pid, "KILL") in table.sent and pid not in table.rows  # killed at its deadline
    assert any(line.startswith("platform: stubborn did not stop within 0.5 s and its grace") for line in lines)
    assert not any("did not stop" in line and ("first" in line or "second" in line) for line in lines)  # ended cleanly


def test_a_second_stop_tells_nobody_again_and_returns_at_once():
    met, told = threading.Barrier(1), []
    app = PlatformApp(log=lambda m: None, machines={"first": Together("first", met, told)}, assistants={})
    app.stop()
    began = time.monotonic()
    app.stop()
    assert told == ["first"] and time.monotonic() - began < 1.0
