"""`liminal-platform serve [--port] [--no-browser] [--until-quiet]`: the platform's page at its port (8775,
LIMINAL_PLATFORM_PORT); `status`: the machine and the machine plugins; `machine NAME status | setup [STEP
...] | run -- COMMAND | instances | enable | disable`: one machine plugin from the command line."""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from collections.abc import Callable

from liminal_libs import docker as docker_mod
from liminal_libs.logs import Logger

from . import __version__
from .app import PlatformApp, facts, platform_dir

QUIET_SECONDS = 600.0
# 0.31.0: on POSIX (the Linux platform, WSL's among them) these end the serve as Ctrl+C does, so the platform stops
# and its plugins stop what they started (a model server started by a click), and the children's atexit net runs.
# Left to Python, either ends the process at once and runs nothing of it (atexit runs for no signal Python does not
# handle): SIGTERM (kill, a service's stop) and SIGHUP (its terminal closed: the WSL suite's apps run in terminal tabs)
ENDING_SIGNALS = ("SIGTERM", "SIGHUP")
WHY = {"SIGTERM": "asked to end", "SIGHUP": "its terminal closed: nothing more is printed, its log keeps the rest"}


class Ending:
    """The serve loop's stop (the frame's App.serve waits on it in its loop and sets it at its end) that a signal can
    set (0.31.0). A signal's handler runs in the main thread, the one that waits here, wherever that thread is at that
    moment, so it only sets a flag: it takes no lock (a threading.Event's set takes the one its wait holds for an
    instant in that same thread: a signal landing then would hang the platform), raises nothing (a SystemExit could
    land in the middle of a stop) and prints nothing. The loop sees the flag within one STEP of waiting and stops the
    platform as after Ctrl+C; a signal while it stops changes nothing. Always true as an object (App.serve takes
    `stop or threading.Event()`). `log`: told once, from the waiting thread, which signal ended the serve."""

    STEP = 0.5  # seconds slept at a time while waiting: a flag set by a signal is seen within it

    def __init__(self, log: Callable[[str], None] | None = None, name: str = "platform", *,
                 sleep: Callable[[float], None] | None = None, clock: Callable[[], float] | None = None):
        self.by = ""  # the signal that ended the serve ("SIGTERM", "SIGHUP"), the first one; "" while none has
        self.quieted = False  # its output let go (after SIGHUP): nothing is printed from then on
        self._set = False
        self._said = False
        self._log, self._name = log, name
        self._sleep, self._clock = sleep, clock  # a test's; else time.sleep and time.monotonic, looked up when used

    def set(self) -> None:
        self._set = True

    def is_set(self) -> bool:
        return self._set

    def wait(self, timeout: float | None = None) -> bool:
        """Until it is set or `timeout` seconds pass (None: until it is set): whether it is. The first time it is found
        set by a signal, the log is told which."""
        sleep, clock = self._sleep or time.sleep, self._clock or time.monotonic
        end = None if timeout is None else clock() + max(0.0, float(timeout))
        while not self._set:
            left = self.STEP if end is None else min(self.STEP, end - clock())
            if left <= 0:
                break
            sleep(left)
        if self._set and self.by and not self._said:
            self._said = True
            self._say()
        return self._set

    def _say(self) -> None:
        if self._log is None:
            return
        try:
            self._log(f"{self._name}: {self.by} came ({WHY.get(self.by, 'asked to end')}): the server ends")
        except Exception:  # noqa: BLE001 - a line that cannot be written stops nothing
            pass

    def end(self, name: str, quiet: Callable[[], None] | None = None) -> None:
        """A signal's work, done by its handler: `quiet` first, once (SIGHUP: the terminal is gone), then the serve
        loop told to end. Raises nothing, takes no lock, prints nothing; the signal that came first is the one said."""
        if quiet is not None and not self.quieted:
            self.quieted = True
            try:
                quiet()
            except Exception:  # noqa: BLE001 - its output stays where it was
                pass
        if not self.by:
            self.by = name
        self._set = True


def silence(fds: tuple[int, ...] = (1, 2)) -> None:
    """Each of `fds` (this process's output and its errors) sent to the null device from now on (0.31.0, after SIGHUP):
    its terminal is gone, and every write to it fails (EIO), which would cut short whatever was writing, the stop's
    own lines among them (the log prints each line before it writes it to its file). What is logged still reaches the
    log's file."""
    null = os.open(os.devnull, os.O_WRONLY)
    try:
        for fd in fds:
            os.dup2(null, fd)
    finally:
        os.close(null)


def end_on_signals(ending: Ending, *, signals=None, posix: bool | None = None,
                   quiet: Callable[[], None] | None = None) -> tuple[str, ...]:
    """SIGTERM and SIGHUP made to end the serve as Ctrl+C does (0.31.0): `ending` set, after SIGHUP the output let go
    first (`quiet`; none given: silence's). Only on POSIX and from the main thread, the one a handler can be set from
    and runs in; a signal the platform was started with ignored (nohup's SIGHUP) or handled already is left as it was.
    The handlers stay until the process ends, so a signal while the platform stops, or while atexit stops the
    children, changes nothing. The names of the signals set: none on Windows, where none of them comes from outside
    (a plugin's children end with the platform's job object), and none off the main thread. `signals`: the signal
    module (a test's stand-in); `posix`: whether this is POSIX (None: os.name says)."""
    signals = signal if signals is None else signals
    posix = os.name == "posix" if posix is None else bool(posix)
    if not posix or threading.current_thread() is not threading.main_thread():
        return ()
    quiet = silence if quiet is None else quiet
    names: dict[int, str] = {}
    for name in ENDING_SIGNALS:
        number = getattr(signals, name, None)
        if number is None:
            continue
        try:
            if signals.getsignal(number) != signals.SIG_DFL:  # ignored (nohup), or someone's handler: left as it is
                continue
        except (OSError, ValueError, TypeError):
            continue
        names[number] = name

    def handler(number, frame=None) -> None:
        name = names.get(number) or f"signal {number}"
        ending.end(name, quiet if name == "SIGHUP" else None)

    done = []
    for number, name in names.items():
        try:
            signals.signal(number, handler)
        except (OSError, ValueError, RuntimeError):
            continue
        done.append(name)
    return tuple(done)


def _app(log=print, once: bool = True) -> PlatformApp:
    """The platform app with its plugins attached; `once` (every command but serve): answering and ending, so a plugin
    starts no background work of its own (0.20.1: a status had started each cloud plugin's reads and a Dynamic DNS pass)."""
    app = PlatformApp(log=log, once=once)
    app.attach_plugins()
    return app


def cmd_serve(args) -> int:
    """The page served until Ctrl+C (or, 0.31.0, SIGTERM or SIGHUP on POSIX: end_on_signals), or until no page has
    been in touch for QUIET_SECONDS with --until-quiet; then the platform stopped, its plugins told."""
    folder = platform_dir()
    app = _app(Logger(folder / "logs" / "platform.log"), once=False)
    port = args.port if args.port is not None else app.port()
    ending = Ending(log=app.log, name="platform")
    end_on_signals(ending)  # kept until the process ends: a signal while it stops changes nothing
    print(f"platform: its page at {app.url(port)} (Ctrl+C to stop)", flush=True)
    try:
        app.serve(port, open_browser=not args.no_browser, until_quiet=QUIET_SECONDS if args.until_quiet else None,
                  stop=ending)
    finally:
        if not app.stopping:  # 0.35.0: serve's own end stopped it already (once): only a serve that never began
            app.stop()
    return 0


def cmd_status(args) -> int:
    app = _app(lambda m: None)
    f = facts()
    print(f"{f['host']}: {f['system']} {f['release']} on {f['machine']}, {f['cpus']} cpus, {f['memoryMb']} MB, Python {f['python']}")
    d = docker_mod.Docker(env={}).describe()
    print("docker on this machine: " + (f"engine {d['engine']}" if d["available"] else d.get("problem", "not installed")))
    for name, m in app.machines().items():
        if not app.enabled(name):
            print(f"{name}: {m.title}; disabled")
            continue
        st = app.machine_status(m)["status"]
        engine = st.get("engine") or {}
        print(f"{name}: {m.title}; " + ("present" if st.get("present") else "not present")
              + (f"; Docker inside {'running' if engine.get('running') else 'installed, not running'} ({engine.get('version')})" if engine.get("installed") else "; no Docker inside")
              + (f"; {st['problem']}" if st.get("problem") else ""))
    for i in app.instances():
        print(f"instance {i['name']}: {i['where']} ({i['command']})")
    return 0


def cmd_machine(args) -> int:
    app = _app(print)
    try:
        m = app.machine(args.name)
    except Exception as e:  # noqa: BLE001 - said
        print(str(e), file=sys.stderr)
        return 2
    if args.action in ("enable", "disable"):
        app.set_enabled(m.name, args.action == "enable")
        print(f"{m.name}: {args.action}d")
        return 0
    if args.action == "status":
        print(json.dumps(app.machine_status(m)["status"], indent=1))
        return 0
    if not app.enabled(m.name):
        print(f"{m.name} is disabled: liminal-platform machine {m.name} enable", file=sys.stderr)
        return 2
    if args.action == "setup":
        done = m.setup(log=print, steps=args.rest or None)
        return 0 if all(d["ok"] is not False for d in done) else 1
    if args.action == "run":
        command = args.rest[1:] if args.rest[:1] == ["--"] else args.rest
        if not command:
            print("a command is needed: liminal-platform machine NAME run -- ls /", file=sys.stderr)
            return 2
        print(m.run(*command), end="")
        return 0
    if args.action == "instances":
        print(json.dumps([i.describe() for i in m.instances()], indent=1))
        return 0
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="liminal-platform", description="The Liminal platform: the software and hardware under the framework.")
    p.add_argument("--version", action="version", version=f"liminal-platform {__version__}")
    sub = p.add_subparsers(dest="command")
    s = sub.add_parser("serve", help="keep the platform's page at its port until Ctrl+C")
    s.add_argument("--port", type=int, default=None, help="the page's port (LIMINAL_PLATFORM_PORT, 8775)")
    s.add_argument("--no-browser", action="store_true")
    s.add_argument("--until-quiet", action="store_true", help=f"end once no page has been in touch for {QUIET_SECONDS:g} s")
    s.set_defaults(func=cmd_serve)
    st = sub.add_parser("status", help="the machine, Docker, the machine plugins and the Docker instances")
    st.set_defaults(func=cmd_status)
    m = sub.add_parser("machine", help="one machine plugin: status | setup [STEP ...] | run -- COMMAND | instances | enable | disable")
    m.add_argument("name")
    m.add_argument("action", choices=("status", "setup", "run", "instances", "enable", "disable"))
    m.add_argument("rest", nargs="*")
    m.set_defaults(func=cmd_machine)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version")):
        argv = ["serve", *argv]
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        build_parser().print_help()
        return 2
    return args.func(args)
