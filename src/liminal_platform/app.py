"""The platform app: the frame's App with the chip icon; its routes serve the machine's facts, the machine
plugins (their status, a setup run in a thread with its lines kept, a command), the Docker instances and
the plugins attached."""
from __future__ import annotations

import os
import platform as py_platform
import threading
import time
from http import HTTPStatus
from pathlib import Path

from liminal_libs import docker as docker_mod
from liminal_libs.apps import App, EnvironmentLogin, Refused, TrayItem, attach_registry

PORT = 8775
NOT_ASKED = ("setup", "settings", "scan", "run")  # a machine's hooks the page asks through its own routes, or not at all


def facts() -> dict:
    """What this machine is: the system, the processor, the memory, the Python, the host name."""
    return {"system": py_platform.system(), "release": py_platform.release(), "version": py_platform.version(),
            "machine": py_platform.machine(), "processor": py_platform.processor(), "cpus": os.cpu_count() or 0,
            "memoryMb": memory_mb(), "python": py_platform.python_version(), "host": py_platform.node()}


def memory_mb() -> int:
    """The machine's memory in MB (0 when it cannot be read)."""
    try:
        if os.name == "nt":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32), ("ullTotalPhys", ctypes.c_uint64),
                            ("ullAvailPhys", ctypes.c_uint64), ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
                            ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64), ("ullAvailExtendedVirtual", ctypes.c_uint64)]
            s = Status()
            s.dwLength = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            return int(s.ullTotalPhys // (1024 * 1024))
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024))
    except Exception:  # noqa: BLE001 - a fact that cannot be read is 0
        return 0


def _json_of(value):
    """A plugin's answer as JSON: what can describe itself, described; lists and dicts through."""
    if hasattr(value, "describe"):
        return value.describe()
    if isinstance(value, (list, tuple)):
        return [_json_of(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_of(v) for k, v in value.items()}
    return value


class Setup:
    """A machine plugin's setup under way, in a thread: its lines as they come, its steps when done."""

    def __init__(self, machine, steps):
        self.machine = machine
        self.steps = tuple(steps) if steps else None
        self.lines: list[str] = []
        self.done: list[dict] | None = None
        self.error: str | None = None
        self.started = time.time()
        self.thread = threading.Thread(target=self._run, name=f"setup-{machine.name}", daemon=True)

    def _run(self) -> None:
        try:
            self.done = self.machine.setup(log=self.lines.append, steps=self.steps)
        except Exception as e:  # noqa: BLE001 - the page gets the words
            self.error = f"{type(e).__name__}: {e}"
            self.done = []

    @property
    def running(self) -> bool:
        return self.thread.is_alive()

    def describe(self) -> dict:
        return {"machine": self.machine.name, "steps": list(self.steps or ()), "running": self.running, "lines": list(self.lines),
                "done": self.done, "error": self.error, "startedAt": self.started,
                "ok": None if self.done is None else (self.error is None and all(d["ok"] is not False for d in self.done))}


class PlatformApp(App):
    NAME = "platform"
    TITLE = "Liminal Platform"
    ICON = "chip"  # the hardware (icons.js)
    PORT = PORT
    PORT_VAR = "LIMINAL_PLATFORM_PORT"
    STATIC = Path(__file__).parent / "static"

    ACTIVE_SECONDS = 60.0  # which plugins are active is asked again after this long (some ask WSL)

    def __init__(self, log=print, login=None, machines: dict | None = None):
        super().__init__(log, login if login is not None else EnvironmentLogin())
        self._machines = machines  # by name; None: the registry's
        self._setups: dict[str, Setup] = {}
        self._lock = threading.Lock()
        self._active: tuple[float, list[str]] | None = None

    # -- the tray: the chip, then an icon per active plugin (the user, 2026-11-07: "active plugins, will be part
    # of the tray on the very right side") ------------------------------------------------------------------
    def active(self, fresh: bool = False) -> list[str]:
        """The machine plugins present, by name (asked at most once a minute unless `fresh`)."""
        now = time.monotonic()
        with self._lock:
            cached = self._active
        if cached is not None and not fresh and now - cached[0] < self.ACTIVE_SECONDS:
            return list(cached[1])
        names = []
        for name, m in self.machines().items():
            try:
                if m.present():
                    names.append(name)
            except Exception:  # noqa: BLE001 - a plugin that cannot say is not active
                continue
        with self._lock:
            self._active = (now, names)
        return names

    def items(self) -> tuple[TrayItem, ...]:
        """An icon per active machine plugin, after the platform's own (the frame's tray puts the chip first)."""
        machines = self.machines()
        return tuple(TrayItem(name, getattr(machines[name], "ICON", "") or "chip", machines[name].title, "plugin", self.NAME)
                     for name in self.active() if name in machines)

    def assistants(self) -> list[dict]:
        """The AI assistants attached here: who they are (their keys and plans are set on the charts app's view)."""
        return [{"name": p.name, "title": p.title, "about": p.about, "version": p.version, "vendor": str(getattr(p, "vendor", "") or ""),
                 "model": str(getattr(p, "default_model", "") or "")}
                for p in self._plugins.values() if getattr(p, "KIND", "") == "assistant"]

    def machines(self) -> dict:
        if self._machines is not None:
            return dict(self._machines)
        from liminal_libs.sources.registry import machines

        return machines()

    def machine(self, name: str):
        m = self.machines().get(name)
        if m is None:
            raise Refused(HTTPStatus.NOT_FOUND, f"no machine plugin named {name!r}")
        return m

    def attach_plugins(self) -> list[str]:
        """Every platform plugin the registry loaded (the machines, the AI assistants), attached here."""
        return attach_registry(self, only="platform")

    def instances(self) -> list[dict]:
        return [i.describe() for i in docker_mod.instances(machines=self.machines().values())]

    def status(self) -> dict:
        machines = {n: self.machine_status(m) for n, m in self.machines().items()}
        with self._lock:  # the presence just read is the freshest: the tray follows it
            self._active = (time.monotonic(), [n for n, m in machines.items() if m["status"].get("present")])
        return {"app": self.describe(), "machine": facts(), "docker": docker_mod.Docker(env={}).describe(),
                "machines": machines, "active": self.active(), "assistants": self.assistants(),
                "instances": self.instances(), "plugins": self.plugins()}

    def machine_status(self, m) -> dict:
        try:
            status = m.status()
        except Exception as e:  # noqa: BLE001 - a plugin's trouble is shown, not raised
            status = {"present": False, "problem": f"{type(e).__name__}: {e}"}
        with self._lock:
            setup = self._setups.get(m.name)
        return {"name": m.name, "title": m.title, "about": m.about, "version": m.version, "status": status,
                "icon": getattr(m, "ICON", "") or "chip",
                "steps": list(getattr(m, "STEPS", ()) or ()), "asks": self.asks(m),
                "setup": setup.describe() if setup else None}

    @staticmethod
    def asks(m) -> list[str]:
        """What the page may ask a machine plugin by name: its hooks (Plugin.interface) but the setup, the
        settings, the scan and a command, which have routes of their own or none."""
        try:
            return [h for h in m.interface()["hooks"] if h not in NOT_ASKED]
        except Exception:  # noqa: BLE001 - a plugin that cannot say: nothing to ask
            return []

    def ask(self, name: str, hook: str, args: list):
        """One of a machine plugin's hooks by name (asks), its answer as JSON (a rule, a startup: described)."""
        m = self.machine(name)
        if hook not in self.asks(m):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} is not asked {hook!r} here: {', '.join(self.asks(m)) or 'nothing'}")
        self.log(f"platform: {name} asked {hook}" + (f" {' '.join(map(str, args))}" if args else ""))
        try:
            answer = m.ask(hook, *args)
        except (TypeError, ValueError, LookupError) as e:
            raise Refused(HTTPStatus.BAD_REQUEST, f"{type(e).__name__}: {e}") from None
        except Exception as e:  # noqa: BLE001 - the plugin's own words
            raise Refused(HTTPStatus.BAD_GATEWAY, f"{type(e).__name__}: {e}") from None
        return _json_of(answer)

    def start_setup(self, name: str, steps=None) -> Setup:
        m = self.machine(name)
        with self._lock:
            current = self._setups.get(name)
            if current is not None and current.running:
                raise Refused(HTTPStatus.CONFLICT, f"{name} is being set up already")
            setup = Setup(m, steps)
            self._setups[name] = setup
        self.log(f"platform: setting up {name}" + (f" ({', '.join(setup.steps)})" if setup.steps else ""))
        setup.thread.start()
        return setup

    def api(self, handler, method: str, path: str, query: dict, body: dict | None):
        body = body or {}
        if method == "GET" and path == "/api/status":
            return 200, self.status()
        if method == "GET" and path == "/api/machines":
            return 200, {"machines": [self.machine_status(m) for m in self.machines().values()]}
        if method == "GET" and path == "/api/instances":
            return 200, {"instances": self.instances()}
        if path.startswith("/api/machines/"):
            rest = path[len("/api/machines/"):]
            name, _, action = rest.partition("/")
            m = self.machine(name)
            if method == "GET" and not action:
                return 200, self.machine_status(m)
            if method == "GET" and action == "setup":
                with self._lock:
                    setup = self._setups.get(name)
                return 200, (setup.describe() if setup else {"machine": name, "running": False, "lines": [], "done": None})
            if method == "POST" and action == "setup":
                steps = body.get("steps") or None
                if steps is not None and (not isinstance(steps, list) or not all(isinstance(s, str) for s in steps)):
                    raise Refused(HTTPStatus.BAD_REQUEST, "steps is a list of step names")
                return 202, self.start_setup(name, steps).describe()
            if method == "POST" and action == "ask":
                hook, args = body.get("hook"), body.get("args") or []
                if not isinstance(hook, str) or not isinstance(args, list):
                    raise Refused(HTTPStatus.BAD_REQUEST, "hook is a hook's name, args a list")
                return 200, {"answer": self.ask(name, hook, args)}
            if method == "POST" and action == "run":
                command = body.get("command")
                if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
                    raise Refused(HTTPStatus.BAD_REQUEST, "command is a list of words")
                try:
                    return 200, {"output": m.run(*command)}
                except Exception as e:  # noqa: BLE001 - the plugin's words
                    raise Refused(HTTPStatus.BAD_GATEWAY, f"{type(e).__name__}: {e}") from None
        return super().api(handler, method, path, query, body)
