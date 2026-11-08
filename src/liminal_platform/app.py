"""The platform app: the frame's App with the chip icon; its routes serve the machine's facts, the machine
plugins (their status, a setup run in a thread with its lines kept, a command, disabled or enabled), the Docker
instances and the plugins attached."""
from __future__ import annotations

import json
import os
import platform as py_platform
import threading
import time
from http import HTTPStatus
from pathlib import Path

from liminal_libs import docker as docker_mod
from liminal_libs import layout
from liminal_libs.apps import App, EnvironmentLogin, Refused, TrayItem
from liminal_libs.machines.terminal import Output, Terminal

PORT = 8775
NOT_ASKED = ("setup", "settings", "scan", "run")  # a machine's hooks the page asks through its own routes, or not at all
READS = ("present", "status", "view", "charts", "instances", "wanted", "services", "startups", "processes")  # asks not logged
DIR_VAR = "LIMINAL_PLATFORM_DIR"  # the platform's own folder: its log, which plugins are disabled
PLUGINS_FILE = "plugins.json"
TERMINAL_IDLE_S = 120.0  # a terminal no page has read for this long is closed
PREPARING = ("wsl", "update", "version")  # setup steps that prepare this PC: never locked by a plugin's check
MAX_INPUT = 8192  # characters of keys a page sends at once


def platform_dir() -> Path:
    """The platform's own folder: LIMINAL_PLATFORM_DIR, else the data folder's platform/."""
    named = (os.environ.get(DIR_VAR) or "").strip()
    return Path(named).expanduser() if named else layout.data_dir() / "platform"


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
    """A machine plugin's job under way, in a thread: its setup, or its packages' update (`action`); what it prints as it
    comes (`output`, read from an offset by the page's terminal panel), its steps when done."""

    def __init__(self, machine, steps, action: str = "setup"):
        self.machine = machine
        self.action = action
        self.steps = tuple(steps) if steps else None
        self.output = Output()
        self.done: list[dict] | None = None
        self.error: str | None = None
        self.started = time.time()
        self.thread = threading.Thread(target=self._run, name=f"setup-{machine.name}", daemon=True)

    def _run(self) -> None:
        try:
            if self.action == "update":
                self.done = self.machine.update_packages(log=self.output)
            else:
                self.done = self.machine.setup(log=self.output, steps=self.steps)
        except Exception as e:  # noqa: BLE001 - the page gets the words
            self.error = f"{type(e).__name__}: {e}"
            self.done = []

    @property
    def running(self) -> bool:
        return self.thread.is_alive()

    @property
    def lines(self) -> list[str]:
        return self.output.text.splitlines()

    def describe(self, since: int | None = None, last: int | None = None) -> dict:
        """Its state; with `since`, the text printed after that offset (the panel's next part); `last`: only so many lines."""
        out = {"machine": self.machine.name, "action": self.action, "steps": list(self.steps or ()), "running": self.running,
               "lines": self.lines[-last:] if last else self.lines, "done": self.done, "error": self.error, "startedAt": self.started,
               "ok": None if self.done is None else (self.error is None and all(d["ok"] is not False for d in self.done))}
        if since is not None:
            out["text"], out["from"], out["offset"] = self.output.read(since)
        return out


class PlatformApp(App):
    NAME = "platform"
    TITLE = "Liminal Platform"
    ICON = "chip"  # the hardware (icons.js)
    PORT = PORT
    PORT_VAR = "LIMINAL_PLATFORM_PORT"
    STATIC = Path(__file__).parent / "static"

    ACTIVE_SECONDS = 60.0  # which plugins are active is asked again after this long (some ask WSL)

    SETTINGS_SECONDS = 30.0  # the app's settings (the assistants' keys and plans) are read again after this long

    def __init__(self, log=print, login=None, machines: dict | None = None, state: Path | None = None,
                 assistants: dict | None = None, settings=None, terminal=None):
        super().__init__(log, login if login is not None else EnvironmentLogin())
        self._machines = machines  # by name; None: the registry's
        self._assistants = assistants  # by name; None: the registry's
        self._settings_of = settings  # () -> Settings: a test's; else the app's, read with its login
        self._settings_cache: tuple[float, object] | None = None
        self._invalid: set[str] = set()  # the plugins found not valid by the last status: out of the tray
        self._terminals: dict[str, Terminal] = {}  # a login terminal per plugin (the page's terminal panel)
        self._terminal_of = terminal  # (argv, title) -> Terminal: a test's
        self._settling = threading.Lock()
        self._state = Path(state) if state is not None else None  # the platform's folder; platform_dir() unless given
        self._disabled: set[str] | None = None  # read from the folder's plugins.json when first wanted
        self._attaching = False  # set once attach_plugins ran: an enabled plugin is attached again
        self._setups: dict[str, Setup] = {}
        self._lock = threading.Lock()
        self._active: tuple[float, list[str]] | None = None

    # -- disabled plugins (the user, 2026-11-07: "allow me to right click on the icons to disable them on the right
    # icon menu, also allow for enable disable switch (left to right) on the plugin description") -------------------
    @property
    def state_dir(self) -> Path:
        return self._state if self._state is not None else platform_dir()

    def disabled(self) -> set[str]:
        """The plugins disabled here, by name (the folder's plugins.json, kept across restarts)."""
        with self._lock:
            if self._disabled is None:
                try:
                    saved = json.loads((self.state_dir / PLUGINS_FILE).read_text(encoding="utf-8"))
                    self._disabled = {n for n in saved.get("disabled", []) if isinstance(n, str)}
                except (OSError, ValueError, AttributeError):
                    self._disabled = set()
            return set(self._disabled)

    def enabled(self, name: str) -> bool:
        return name not in self.disabled()

    def set_enabled(self, name: str, on: bool) -> dict:
        """A machine plugin enabled or disabled (the tray's right click, the switch on its page). Disabled, the
        platform asks it nothing, its icon leaves the tray and it is detached (a plugin that samples stops);
        enabled, it is attached again when the platform attaches its plugins. Kept across restarts."""
        m = self.platform_plugin(name)
        names = self.disabled()
        if on:
            names.discard(name)
        else:
            names.add(name)
        folder = self.state_dir
        folder.mkdir(parents=True, exist_ok=True)
        part = folder / (PLUGINS_FILE + ".part")
        part.write_text(json.dumps({"disabled": sorted(names)}, indent=1), encoding="utf-8")
        os.replace(part, folder / PLUGINS_FILE)
        with self._lock:
            self._disabled = names
            if self._active is not None:  # the tray follows without asking every plugin again
                self._active = (self._active[0], [n for n in self._active[1] if n != name])
        if not on and self.plugin(name) is not None:
            self.detach(name)
        self.log(f"platform: {name} {'enabled' if on else 'disabled'}")
        if name not in self.machines():  # an AI assistant
            return self.assistant_status(m)
        answer = self.machine_status(m)  # attached again when it is valid (_settle)
        if answer["state"] == "active":
            order = list(self.machines())
            with self._lock:
                if self._active is not None:
                    names_active = {*self._active[1], name}
                    self._active = (self._active[0], [n for n in order if n in names_active])
        return answer

    def _settle(self, p, active: bool) -> None:
        """A plugin attached while it is active (enabled and valid) and detached otherwise, once the platform
        attaches its plugins (the user: "if a plugin is not in a valid state it has to be disabled")."""
        if not self._attaching:
            return
        with self._settling:
            attached = self.plugin(p.name) is not None
            if active and not attached and getattr(p, "app", None) is None:
                self.attach(p)
            elif not active and attached:
                self.detach(p.name)

    def platform_plugin(self, name: str):
        """A machine plugin or an AI assistant of the platform, by name."""
        p = self.machines().get(name) or self.assistant_plugins().get(name)
        if p is None:
            raise Refused(HTTPStatus.NOT_FOUND, f"no plugin named {name!r} here")
        return p

    def _refuse_disabled(self, name: str) -> None:
        if not self.enabled(name):
            raise Refused(HTTPStatus.CONFLICT, f"{name} is disabled: enable it first")

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
        off = self.disabled() | set(self._invalid)
        for name, m in self.machines().items():
            if name in off:
                continue
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

    def assistant_plugins(self) -> dict:
        """The AI assistants, by name: given, else every one the registry loaded (attached or not)."""
        if self._assistants is not None:
            return dict(self._assistants)
        from liminal_libs.sources.registry import assistants

        return assistants()

    def settings_now(self):
        """The app's settings (the assistants' keys and plans), read with the platform's login; kept SETTINGS_SECONDS."""
        if self._settings_of is not None:
            return self._settings_of()
        now = time.monotonic()
        with self._lock:
            cached = self._settings_cache
        if cached is not None and now - cached[0] < self.SETTINGS_SECONDS:
            return cached[1]
        from liminal_libs.config import load_settings

        settings = load_settings(login=self.login)
        with self._lock:
            self._settings_cache = (now, settings)
        return settings

    def assistant_validity(self, p) -> tuple[bool, str]:
        """An assistant is valid with its key set and its plan offering API access; else why not."""
        try:
            settings = self.settings_now()
            if p.served(settings):
                return True, ""
            if not p.keys_set(settings):
                names = [n for n in (getattr(p, "key_names", ()) or ()) if n.endswith("_API_KEY")] or list(getattr(p, "key_names", ()) or ())
                return False, f"no key: {names[0] if names else 'its key'} is not set (the charts app's Plugins view sets it)"
            return False, p.free_note(settings) or "its plan has no API access"
        except Exception as e:  # noqa: BLE001 - one that cannot say is not valid
            return False, f"cannot be read: {type(e).__name__}: {e}"

    def assistant_status(self, p) -> dict:
        """An AI assistant as the page shows it: who it is, enabled (the user's), valid (a key and a plan with API
        access) and why not; attached while both (its keys and plans are set on the charts app's Plugins view)."""
        on = self.enabled(p.name)
        valid, why = self.assistant_validity(p) if on else (None, "")
        state = "active" if on and valid else "disabled" if not on else "invalid"
        self._settle(p, state == "active")
        return {"name": p.name, "title": p.title, "about": p.about, "version": p.version, "vendor": str(getattr(p, "vendor", "") or ""),
                "model": str(getattr(p, "default_model", "") or ""), "enabled": on, "valid": valid, "why": why, "state": state}

    def assistants(self) -> list[dict]:
        """The AI assistants and their state."""
        return [self.assistant_status(p) for p in self.assistant_plugins().values()]

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

    def attach_plugins(self, plugins=None) -> list[str]:
        """Every platform plugin the registry loaded (the machines, the AI assistants; or `plugins`), attached
        here but those disabled and those another app holds; returns the names attached."""
        self._attaching = True
        if plugins is None:
            from liminal_libs.sources.registry import assistants, machines

            plugins = [*assistants().values(), *machines().values()]
        off, out = self.disabled(), []
        for p in plugins:
            if p.SYSTEM != "platform" or p.name in off or (p.app is not None and p.app is not self):
                continue
            self.attach(p)
            out.append(p.name)
        return out

    def instances(self) -> list[dict]:
        off = self.disabled()
        return [i.describe() for i in docker_mod.instances(machines=[m for n, m in self.machines().items() if n not in off])]

    def status(self) -> dict:
        machines = {n: self.machine_status(m) for n, m in self.machines().items()}
        with self._lock:  # the presence just read is the freshest: the tray follows it
            self._active = (time.monotonic(), [n for n, m in machines.items() if m["state"] == "active"])
        return {"app": self.describe(), "machine": facts(), "docker": docker_mod.Docker(env={}).describe(),
                "machines": machines, "active": self.active(), "disabled": sorted(self.disabled()), "assistants": self.assistants(),
                "instances": self.instances(), "plugins": self.plugins()}

    def machine_status(self, m) -> dict:
        on = self.enabled(m.name)
        if not on:  # asked nothing
            status = {"present": None, "summary": "disabled: the platform asks it nothing"}
        else:
            try:
                status = m.status()
            except Exception as e:  # noqa: BLE001 - a plugin's trouble is shown, not raised
                status = {"present": False, "problem": f"{type(e).__name__}: {e}"}
        valid, why = None, ""
        if on:  # its own word when it says (liminal-libs 1.24.0), else present without a problem
            valid = bool(status["valid"]) if "valid" in status else bool(status.get("present")) and not status.get("problem")
            why = "" if valid else str(status.get("why") or status.get("problem") or status.get("summary") or "not present")
        state = "active" if on and valid else "disabled" if not on else "invalid"
        with self._lock:
            (self._invalid.add if state == "invalid" else self._invalid.discard)(m.name)
        self._settle(m, state == "active")
        with self._lock:
            setup = self._setups.get(m.name)
        return {"name": m.name, "title": m.title, "about": m.about, "version": m.version, "status": status,
                "icon": getattr(m, "ICON", "") or "chip", "enabled": on, "valid": valid, "why": why, "state": state,
                "steps": list(getattr(m, "STEPS", ()) or ()), "asks": self.asks(m) if state == "active" else [],
                "hooks": self.hooks(m), "setup": setup.describe(last=200) if setup else None,
                "terminal": {"open": self.terminal_of(m.name) is not None}}

    @staticmethod
    def hooks(m) -> list[str]:
        """The hooks a machine plugin offers, whether it is valid now or not (its check, its update, its terminal)."""
        try:
            return list(m.interface()["hooks"])
        except Exception:  # noqa: BLE001 - one that cannot say offers nothing
            return []

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
        self._refuse_disabled(name)
        if hook not in self.asks(m):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} is not asked {hook!r} here: {', '.join(self.asks(m)) or 'nothing'}")
        if hook not in READS:
            self.log(f"platform: {name} asked {hook}" + (f" {' '.join(map(str, args))}" if args else ""))
        try:
            answer = m.ask(hook, *args)
        except (TypeError, ValueError, LookupError) as e:
            raise Refused(HTTPStatus.BAD_REQUEST, f"{type(e).__name__}: {e}") from None
        except Exception as e:  # noqa: BLE001 - the plugin's own words
            raise Refused(HTTPStatus.BAD_GATEWAY, f"{type(e).__name__}: {e}") from None
        return _json_of(answer)

    def check(self, name: str) -> dict:
        """A plugin's check of this PC for what it installs (the user: \"each plugin should have a scheme for checking the
        environment to see if it supports installing the operating system it has in its name\")."""
        m = self.machine(name)
        self._refuse_disabled(name)
        if "check" not in self.hooks(m):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} checks nothing")
        try:
            return m.check()
        except Exception as e:  # noqa: BLE001 - the plugin's words
            raise Refused(HTTPStatus.BAD_GATEWAY, f"{type(e).__name__}: {e}") from None

    def start_setup(self, name: str, steps=None, action: str = "setup") -> Setup:
        """A plugin's setup (or its packages' update) started in a thread. A plugin that checks this PC is installed only
        once the check passes (\"if the criteria are met according to the O/S, then the install method should be not
        locked out\"); the steps that prepare this PC (WSL itself) are never locked; an update needs it installed."""
        m = self.machine(name)
        self._refuse_disabled(name)
        hooks = self.hooks(m)
        if action == "update":
            if "update_packages" not in hooks:
                raise Refused(HTTPStatus.BAD_REQUEST, f"{name} updates no packages")
            if "check" in hooks and not self.check(name).get("installed"):
                raise Refused(HTTPStatus.CONFLICT, f"{name} is not installed: install it first")
        elif "check" in hooks and not (steps and set(steps) <= set(PREPARING)):
            c = self.check(name)
            if not (c.get("ready") or c.get("installed")):
                raise Refused(HTTPStatus.CONFLICT, f"the install is locked: {c.get('why') or 'this PC does not meet what it needs'}")
        with self._lock:
            current = self._setups.get(name)
            if current is not None and current.running:
                raise Refused(HTTPStatus.CONFLICT, f"{name} is busy already ({current.action})")
            setup = Setup(m, steps, action)
            self._setups[name] = setup
        self.log(f"platform: {'updating the packages of' if action == 'update' else 'setting up'} {name}"
                 + (f" ({', '.join(setup.steps)})" if setup.steps else ""))
        setup.thread.start()
        return setup

    # -- login terminals (the user: "the plugin also allows for a user to login through a terminal in to the environment")
    def terminal_of(self, name: str) -> Terminal | None:
        with self._lock:
            return self._terminals.get(name)

    def _close_idle(self) -> None:
        """Terminals no page has read for TERMINAL_IDLE_S, or that ended, closed."""
        now = time.monotonic()
        with self._lock:
            gone = [(n, t) for n, t in self._terminals.items() if not t.alive or now - t.seen > TERMINAL_IDLE_S]
            for n, _ in gone:
                del self._terminals[n]
        for _, t in gone:
            t.close()

    def open_terminal(self, name: str) -> dict:
        m = self.machine(name)
        self._refuse_disabled(name)
        if "terminal" not in self.hooks(m):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} offers no terminal")
        self._close_idle()
        current = self.terminal_of(name)
        if current is not None and current.alive:
            return current.read(current.output.end)
        try:
            argv = m.terminal()
        except Exception as e:  # noqa: BLE001 - not installed: its words
            raise Refused(HTTPStatus.CONFLICT, str(e)) from None
        title = f"{getattr(m, 'user', '') or 'you'} in {getattr(m, 'distribution_name', '') or m.title}"
        term = (self._terminal_of or (lambda a, t: Terminal(a, title=t)))(argv, title)
        with self._lock:
            self._terminals[name] = term
        self.log(f"platform: a terminal opened into {name}")
        return term.read(0)

    def close_terminal(self, name: str) -> bool:
        with self._lock:
            term = self._terminals.pop(name, None)
        if term is None:
            return False
        term.close()
        self.log(f"platform: the terminal into {name} closed")
        return True

    def stop(self) -> None:
        with self._lock:
            terms, self._terminals = list(self._terminals.values()), {}
        for t in terms:
            t.close()
        super().stop()

    def api(self, handler, method: str, path: str, query: dict, body: dict | None):
        body = body or {}
        if method == "GET" and path == "/api/status":
            return 200, self.status()
        if method == "GET" and path == "/api/machines":
            return 200, {"machines": [self.machine_status(m) for m in self.machines().values()]}
        if method == "GET" and path == "/api/instances":
            return 200, {"instances": self.instances()}
        if method == "POST" and path.startswith("/api/plugins/") and path.endswith("/enabled"):
            on = body.get("on")
            if not isinstance(on, bool):
                raise Refused(HTTPStatus.BAD_REQUEST, "on is true or false")
            return 200, self.set_enabled(path[len("/api/plugins/"):-len("/enabled")], on)
        if path.startswith("/api/machines/"):
            rest = path[len("/api/machines/"):]
            name, _, action = rest.partition("/")
            m = self.machine(name)
            if method == "GET" and not action:
                return 200, self.machine_status(m)
            if method == "GET" and action in ("setup", "job"):
                with self._lock:
                    setup = self._setups.get(name)
                since = int(query.get("since") or 0) if action == "job" else None
                return 200, (setup.describe(since=since) if setup else {"machine": name, "running": False, "lines": [], "done": None,
                                                                       "text": "", "from": 0, "offset": 0})
            if method == "GET" and action == "check":
                return 200, self.check(name)
            if method == "POST" and action == "job":
                what = body.get("action")
                if what not in ("install", "update"):
                    raise Refused(HTTPStatus.BAD_REQUEST, "action is install or update")
                job = self.start_setup(name, None, "update" if what == "update" else "setup")
                return 202, job.describe(since=0)
            if action == "terminal" and method == "POST":
                return 200, self.open_terminal(name)
            if action == "terminal" and method == "GET":
                term = self.terminal_of(name)
                if term is None:
                    raise Refused(HTTPStatus.NOT_FOUND, f"no terminal is open into {name}")
                got = term.read(int(query.get("since") or 0))
                self._close_idle()
                return 200, got
            if action == "terminal/input" and method == "POST":
                data, term = body.get("data"), self.terminal_of(name)
                if not isinstance(data, str) or len(data) > MAX_INPUT:
                    raise Refused(HTTPStatus.BAD_REQUEST, f"data is the keys typed, at most {MAX_INPUT} characters")
                if term is None or not term.alive:
                    raise Refused(HTTPStatus.CONFLICT, f"no terminal is open into {name}")
                term.write(data)
                return 200, {"sent": len(data)}
            if action == "terminal/close" and method == "POST":
                return 200, {"closed": self.close_terminal(name)}
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
            if method == "POST" and action == "enabled":
                on = body.get("on")
                if not isinstance(on, bool):
                    raise Refused(HTTPStatus.BAD_REQUEST, "on is true or false")
                return 200, self.set_enabled(name, on)
            if method == "POST" and action == "run":
                self._refuse_disabled(name)
                command = body.get("command")
                if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
                    raise Refused(HTTPStatus.BAD_REQUEST, "command is a list of words")
                try:
                    return 200, {"output": m.run(*command)}
                except Exception as e:  # noqa: BLE001 - the plugin's words
                    raise Refused(HTTPStatus.BAD_GATEWAY, f"{type(e).__name__}: {e}") from None
        return super().api(handler, method, path, query, body)
