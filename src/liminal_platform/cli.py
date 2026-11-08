"""`liminal-platform serve [--port] [--no-browser] [--until-quiet]`: the platform's page at its port (8775,
LIMINAL_PLATFORM_PORT); `status`: the machine and the machine plugins; `machine NAME status | setup [STEP
...] | run -- COMMAND | instances`: one machine plugin from the command line."""
from __future__ import annotations

import argparse
import json
import sys

from liminal_libs import docker as docker_mod
from liminal_libs.logs import Logger

from . import __version__
from .app import PlatformApp, facts

QUIET_SECONDS = 600.0


def _app(log=print) -> PlatformApp:
    app = PlatformApp(log=log)
    app.attach_plugins()
    return app


def cmd_serve(args) -> int:
    from liminal_libs.layout import data_dir

    folder = data_dir() / "platform"
    app = _app(Logger(folder / "logs" / "platform.log"))
    port = args.port if args.port is not None else app.port()
    print(f"platform: its page at {app.url(port)} (Ctrl+C to stop)", flush=True)
    try:
        app.serve(port, open_browser=not args.no_browser, until_quiet=QUIET_SECONDS if args.until_quiet else None)
    finally:
        app.stop()
    return 0


def cmd_status(args) -> int:
    app = _app(lambda m: None)
    f = facts()
    print(f"{f['host']}: {f['system']} {f['release']} on {f['machine']}, {f['cpus']} cpus, {f['memoryMb']} MB, Python {f['python']}")
    d = docker_mod.Docker(env={}).describe()
    print("docker on this machine: " + (f"engine {d['engine']}" if d["available"] else d.get("problem", "not installed")))
    for name, m in app.machines().items():
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
    if args.action == "status":
        print(json.dumps(app.machine_status(m)["status"], indent=1))
        return 0
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
    m = sub.add_parser("machine", help="one machine plugin: status | setup [STEP ...] | run -- COMMAND | instances")
    m.add_argument("name")
    m.add_argument("action", choices=("status", "setup", "run", "instances"))
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
