"""0.31.0 (DECISIONS A.5: a server a plugin started by a click stops when the platform stops): on POSIX, SIGTERM (kill,
a service's stop) and SIGHUP (its terminal closed: the WSL suite's apps run in terminal tabs) end the serve as Ctrl+C
does, so the platform stops, tells its plugins, and the children's atexit net runs; left to Python, either ends the
process at once and runs nothing of it. The handlers are set from the main thread on POSIX alone, and only set the
serve loop's stop (cli.Ending: a flag, no lock taken, nothing raised, nothing printed); a signal ignored when the
platform started (nohup's SIGHUP) is left ignored; they stay until the process ends, so a further signal while it
stops cuts nothing short. After SIGHUP nothing more is printed: its terminal is gone.

A stand-in signal module throughout: no handler of this process's is set and no signal is sent; nothing is served, no
process is started and no port is opened (conftest's no_outside and the guard below fail a test that does)."""
from __future__ import annotations

import functools
import os
import signal
import threading

import pytest

from conftest import Other, Reached, Served

import liminal_platform.cli as cli
from liminal_platform.app import PlatformApp

SILENCE = cli.silence  # the real one, kept before the guard puts a refusing one in its place
OURS = {getattr(signal, n) for n in ("SIGTERM", "SIGHUP", "SIGINT") if hasattr(signal, n)}


@pytest.fixture(autouse=True)
def no_signal_of_its_own(monkeypatch, no_outside):
    """Besides conftest's no_outside: a test here that sends a signal, sets one of this process's own handlers or lets
    go of its own output fails, each reach noted with the guard's (which fails the test at its end)."""
    def refuse(what):
        def stand_in(*a, **k):
            no_outside.append(what)
            raise Reached(f"a test reached {what} for real")
        return stand_in

    for name in ("kill", "killpg"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, refuse(f"os.{name}"))
    real = signal.signal

    def guarded(number, handler):
        if number in OURS:  # this process's own Ctrl+C, SIGTERM or SIGHUP: never a test's to set
            no_outside.append(f"signal.signal({number})")
            raise Reached(f"a test set this process's handler of signal {number}")
        return real(number, handler)

    monkeypatch.setattr(signal, "signal", guarded)
    monkeypatch.setattr(cli, "silence", refuse("cli.silence (this process's own output)"))


class Signals:
    """A stand-in signal module: its numbers, what each is set to, and a signal sent (`send`), whose handler is run as
    the interpreter runs one: in the main thread, between two steps of whatever it does."""

    SIGHUP, SIGINT, SIGTERM = 1, 2, 15
    SIG_DFL, SIG_IGN = "default", "ignored"

    def __init__(self, **set_to):
        self.handlers = {self.SIGHUP: self.SIG_DFL, self.SIGINT: "python's own", self.SIGTERM: self.SIG_DFL}
        for name, how in set_to.items():
            self.handlers[getattr(self, name)] = how
        self.set: list[int] = []  # the numbers set, in order

    def getsignal(self, number):
        return self.handlers.get(number, self.SIG_DFL)

    def signal(self, number, handler):
        before = self.handlers.get(number, self.SIG_DFL)
        self.handlers[number] = handler
        self.set.append(number)
        return before

    def send(self, number):
        handler = self.handlers[number]
        assert callable(handler), f"signal {number} has no handler of the platform's: {handler!r}"
        handler(number, None)


class Quiet:
    """What lets go of the terminal after SIGHUP (cli.silence), counted; `fails`: it cannot."""

    def __init__(self, fails=False):
        self.calls, self.fails = 0, fails

    def __call__(self):
        self.calls += 1
        if self.fails:
            raise OSError("the output could not be let go")


class Clock:
    """Time that passes only as the waiting thread sleeps; `during`: what lands in its nth sleep (a signal)."""

    def __init__(self, during=None):
        self.now, self.slept, self.during = 100.0, [], dict(during or {})

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(round(seconds, 6))
        self.now += seconds
        landed = self.during.get(len(self.slept))
        if landed is not None:
            landed()


def test_sigterm_and_sighup_are_set_to_end_the_serve_and_later_ones_change_nothing():
    signals, quiet, ending = Signals(), Quiet(), cli.Ending()
    assert cli.end_on_signals(ending, signals=signals, posix=True, quiet=quiet) == ("SIGTERM", "SIGHUP")
    assert signals.set == [15, 1] and signals.handlers[2] == "python's own"  # Ctrl+C stays Python's own
    assert not ending.is_set() and ending.by == "" and not ending.quieted
    signals.send(15)
    assert ending.is_set() and ending.by == "SIGTERM" and quiet.calls == 0  # its terminal is there: still printed to
    signals.send(15)  # another while it stops: nothing raised, nothing changed
    signals.send(1)  # its terminal closed meanwhile: let go, the first signal still the one said
    signals.send(1)
    assert ending.by == "SIGTERM" and quiet.calls == 1 and ending.quieted
    assert callable(signals.handlers[15]) and callable(signals.handlers[1])  # kept: never set back


def test_after_sighup_its_terminal_is_let_go_once_first():
    signals, quiet, ending = Signals(), Quiet(), cli.Ending()
    cli.end_on_signals(ending, signals=signals, posix=True, quiet=quiet)
    signals.send(1)
    assert ending.is_set() and ending.by == "SIGHUP" and quiet.calls == 1
    signals.send(1)
    signals.send(15)
    assert quiet.calls == 1 and ending.by == "SIGHUP"
    failing, again = Quiet(fails=True), cli.Ending()  # output that cannot be let go: the serve ends all the same
    cli.end_on_signals(again, signals=Signals(), posix=True, quiet=failing)
    again.end("SIGHUP", failing)
    assert again.is_set() and failing.calls == 1 and again.quieted


def test_a_signal_ignored_at_the_start_or_handled_already_is_left_as_it_was():
    nohup, ending = Signals(SIGHUP="ignored"), cli.Ending()  # nohup: a closed terminal is not to end it
    assert cli.end_on_signals(ending, signals=nohup, posix=True, quiet=Quiet()) == ("SIGTERM",)
    assert nohup.handlers[1] == "ignored" and nohup.set == [15]

    def theirs(number, frame):
        """Someone's own handler of SIGTERM."""

    handled = Signals(SIGTERM=theirs)
    assert cli.end_on_signals(cli.Ending(), signals=handled, posix=True, quiet=Quiet()) == ("SIGHUP",)
    assert handled.handlers[15] is theirs


def test_nothing_is_set_off_posix_or_off_the_main_thread():
    signals, quiet, ending = Signals(), Quiet(), cli.Ending()
    assert cli.end_on_signals(ending, signals=signals, posix=False, quiet=quiet) == () and signals.set == []
    got: list = []
    other = threading.Thread(target=lambda: got.append(cli.end_on_signals(ending, signals=signals, posix=True,
                                                                          quiet=quiet)))
    other.start()
    other.join(5)
    assert got == [()] and signals.set == []  # a handler is set from the main thread alone


@pytest.mark.skipif(os.name != "posix", reason="POSIX alone: on Windows none of these signals comes from outside")
def test_on_posix_the_system_itself_says_they_are_set():
    signals, ending = Signals(), cli.Ending()
    assert cli.end_on_signals(ending, signals=signals, quiet=Quiet()) == ("SIGTERM", "SIGHUP")
    signals.send(signal.SIGTERM)  # the real number, as the interpreter passes it
    assert ending.is_set() and ending.by == "SIGTERM"


@pytest.mark.skipif(os.name == "posix", reason="Windows alone: its plugins' children end with its job object")
def test_on_windows_none_is_set():
    signals = Signals()
    assert cli.end_on_signals(cli.Ending(), signals=signals, quiet=Quiet()) == () and signals.set == []


def test_the_stop_waits_in_steps_and_says_once_which_signal_ended_the_serve():
    lines: list[str] = []
    clock = Clock()
    ending = cli.Ending(log=lines.append, sleep=clock.sleep, clock=clock)
    assert bool(ending) is True  # App.serve takes `stop or threading.Event()`: never another stop in its place
    assert ending.wait(0.5) is False and clock.slept == [0.5]
    assert ending.wait(1.25) is False and clock.slept == [0.5, 0.5, 0.5, 0.25]  # in steps of STEP at most
    assert ending.wait(0) is False and ending.wait(-1) is False and len(clock.slept) == 4
    clock.during[6] = lambda: ending.end("SIGTERM")  # lands in its second sleep of the next wait
    assert ending.wait(None) is True and len(clock.slept) == 6
    assert lines == ["platform: SIGTERM came (asked to end): the server ends"]
    assert ending.wait(10) is True and len(clock.slept) == 6 and len(lines) == 1  # said once, no more sleeping
    plain = cli.Ending(log=lines.append, sleep=clock.sleep, clock=clock)
    plain.set()  # set by App.serve itself at its end, no signal: nothing to say
    assert plain.wait(0.5) is True and len(lines) == 1

    def broken(line):
        raise OSError("the log cannot be written")

    worded = cli.Ending(log=broken, name="platform", sleep=clock.sleep, clock=clock)
    worded.end("SIGHUP")
    assert worded.wait(0.5) is True  # a line that cannot be written stops nothing


def test_the_frames_serve_loop_ends_by_sigterm_and_the_platform_stops_as_after_ctrl_c(monkeypatch):
    told, lines = [], []
    signals, quiet = Signals(), Quiet()
    app = PlatformApp(log=lines.append, machines={"served": Served(told, signals), "other": Other(told)},
                      assistants={})
    monkeypatch.setattr(app, "start", lambda port=None, open_browser=False: "its page")  # nothing is served
    clock = Clock(during={2: lambda: signals.send(15)})  # SIGTERM lands in the loop's second wait
    ending = cli.Ending(log=app.log, sleep=clock.sleep, clock=clock)
    assert cli.end_on_signals(ending, signals=signals, posix=True, quiet=quiet) == ("SIGTERM", "SIGHUP")
    assert app.serve(None, stop=ending) == "its page"  # the library's own loop, waiting on the stop it is given
    assert clock.slept == [0.5, 0.5] and ending.by == "SIGTERM"
    # stopped as after Ctrl+C: each plugin told, the second too, though another SIGTERM and a SIGHUP came meanwhile
    assert told == ["served", "other"] and quiet.calls == 1
    assert lines == ["platform: SIGTERM came (asked to end): the server ends"]


class Platform:
    """A stand-in for the app the command serves: its serve waits as the frame's does, and the signal a test names
    comes while it serves; its stops are counted."""

    NAME = "platform"

    def __init__(self, signals: Signals, number: int):
        self.signals, self.number = signals, number
        self.lines: list[str] = []
        self.stops, self.served = 0, None

    def log(self, line):
        self.lines.append(line)

    def port(self):
        return 8775

    def url(self, port):
        return f"port {port}"

    def serve(self, port, open_browser=False, stop=None, until_quiet=None):
        self.served = (port, open_browser, until_quiet, stop)
        self.signals.send(self.number)
        try:
            while not stop.wait(0.5):
                pass
        finally:
            stop.set()
            self.stop()
        return "served"

    def stop(self):
        self.stops += 1


@pytest.mark.parametrize("number, said", [
    (15, "platform: SIGTERM came (asked to end): the server ends"),
    (1, "platform: SIGHUP came (its terminal closed: nothing more is printed, its log keeps the rest): "
        "the server ends"),
])
def test_the_serve_command_ends_by_a_signal_and_stops_the_platform(monkeypatch, capsys, number, said):
    signals, quiet = Signals(), Quiet()
    platform = Platform(signals, number)
    monkeypatch.setattr(cli, "_app", lambda log=print, once=True: platform)
    monkeypatch.setattr(cli, "end_on_signals", functools.partial(cli.end_on_signals, signals=signals, posix=True,
                                                                 quiet=quiet))
    assert cli.main(["serve", "--no-browser"]) == 0
    port, browser, until_quiet, stop = platform.served
    assert (port, browser, until_quiet) == (8775, False, None) and isinstance(stop, cli.Ending)
    assert platform.stops == 2  # the serve's own stop, then the command's
    assert platform.lines == [said]
    assert quiet.calls == (1 if number == 1 else 0)
    # printed: only what came before the signal (after SIGHUP its terminal is gone)
    assert capsys.readouterr().out == "platform: its page at port 8775 (Ctrl+C to stop)\n"
    assert callable(signals.handlers[15]) and callable(signals.handlers[1])  # kept until the process ends
    signals.send(15)  # one more as the process ends (atexit stopping the children): nothing raised
    assert stop.by == ("SIGTERM" if number == 15 else "SIGHUP")


def test_silence_sends_what_is_written_to_a_stream_nowhere(tmp_path):
    path = tmp_path / "terminal.txt"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0))
    try:
        os.write(fd, b"before\n")
        SILENCE((fd,))
        assert os.write(fd, b"after\n") == 6  # written without a failure: to the null device
    finally:
        os.close(fd)
    assert path.read_bytes() == b"before\n"
