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
from liminal_libs.apps import App, EnvironmentLogin, Refused, TrayItem, Unauthorized, program_name, saved_variables
from liminal_libs.machines.terminal import Output, Terminal

PORT = 8775
NOT_ASKED = ("setup", "settings", "scan", "run")  # a machine's hooks the page asks through its own routes, or not at all
READS = ("present", "status", "view", "charts", "instances", "wanted", "services", "startups", "processes")  # asks not logged
DIR_VAR = "LIMINAL_PLATFORM_DIR"  # the platform's own folder: its log, which plugins are disabled
LOGIN_VAR = "LIMINAL_PLATFORM_LOGIN"  # memory: a scratch preview's login, nothing it saves leaving the process
PLUGINS_FILE = "plugins.json"
TERMINAL_IDLE_S = 120.0  # a terminal no page has read for this long is closed
PREPARING = ("wsl", "update", "version")  # setup steps that prepare this PC: never locked by a plugin's check
MAX_INPUT = 8192  # characters of keys a page sends at once
MAX_SETTING = 4096  # characters of one setting entered on a plugin's page
MAX_WAIT = 5.0  # seconds a page's read may be held until there is output (the echo at once, one read at a time)
KEPT_SHOWN = 4000  # characters of a terminal open already a page is shown when it comes back to it


def _wait(query: dict) -> float:
    try:
        return min(max(float(query.get("wait") or 0), 0.0), MAX_WAIT)
    except ValueError:
        return 0.0


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


class HookRefused(Refused):
    """A plugin's hook refusing what it was asked (400) or failing (502), its own words beside the frame's reason (0.6.0:
    a form's answer said in words on the page). `accept`: a refusal naming the argument that accepts it (the Namecheap
    plugin's accept_ddns_reset), which the page offers as a second, explicit confirmation."""

    def __init__(self, status: int, reason: str, words: str, accept: str | None = None):
        super().__init__(status, reason)
        self.words, self.accept = words, accept

    def answer(self) -> dict:
        out = {"error": self.reason, "words": self.words}
        if self.accept:
            out["accept"] = self.accept
        return out


def _accepting(e: Exception) -> str | None:
    """The argument a refusal names as accepting it (its `accept`), when it is a plain name."""
    name = getattr(e, "accept", None)
    return name if isinstance(name, str) and name.isidentifier() else None


class Setup:
    """A machine plugin's job under way, in a thread: its setup, its packages' update, or one of its hooks (`action`:
    the hook's name; 0.19.0, `call`: the hook asked with the job's output as its `log`); what it prints as it comes
    (`output`, read from an offset by the page's terminal panel), its steps (a hook's answer) when done."""

    def __init__(self, machine, steps, action: str = "setup", traffic=None, by: str = "platform", call=None):
        self.machine = machine
        self.action = action
        self.steps = tuple(steps) if steps else None
        self.call = call  # (log) -> the hook's answer, for a hook asked as a job
        self.answer = None  # that answer, once it is in
        self.output = Output()
        self.done: list[dict] | None = None
        self.error: str | None = None
        self.started = time.time()
        self.traffic, self.by = traffic, by  # who asked it, noted when it ends (apps.traffic)
        self.thread = threading.Thread(target=self._run, name=f"setup-{machine.name}", daemon=True)

    def _run(self) -> None:
        began = time.perf_counter()
        try:
            if self.call is not None:  # kept as JSON can say it (it is shown with the plugin's status): never a value it cannot
                self.answer = json.loads(json.dumps(_json_of(self.call(self.output)), default=str))
                said = self.answer.get("said", "") if isinstance(self.answer, dict) else str(self.answer or "")
                ok = not (isinstance(self.answer, dict) and self.answer.get("ok") is False)
                self.done = [{"step": self.action, "ok": ok, "said": said}]
            elif self.action == "update":
                self.done = self.machine.update_packages(log=self.output)
            else:
                self.done = self.machine.setup(log=self.output, steps=self.steps)
        except Exception as e:  # noqa: BLE001 - the page gets the words
            self.error = f"{type(e).__name__}: {e}"
            self.done = []
        if self.traffic is not None:
            ok = self.error is None and all(d.get("ok") is not False for d in self.done or [] if isinstance(d, dict))
            self.traffic.record(self.by, self.machine.name, "change", f"{self.action} ended" + ("" if ok else ": it failed"),
                                (time.perf_counter() - began) * 1000, ok)

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
        if self.call is not None:
            out["hook"], out["answer"] = True, self.answer
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
    # the login app it inherits (0.18.0; the user, 2026-11-10: "make sure that the platform inherits the login app so we
    # can login to platform"; "using secret user"): its own login, its users apart from the charts app's (liminal-libs
    # 1.46.0: started for it when nothing answers, its page the sign-in until the browser is signed in)
    LOGIN_URL_VAR = "LIMINAL_PLATFORM_LOGIN_URL"
    LOGIN_URL = "http://127.0.0.1:8796"

    ACTIVE_SECONDS = 60.0  # which plugins are active is asked again after this long (some ask WSL)

    SETTINGS_SECONDS = 30.0  # the app's settings (the assistants' keys and plans) are read again after this long

    # who talks to whom, drawn on the page's Connections (the user, 2026-11-08: "the root plugin (platform) will need to
    # visually illustrate how plugins are connected to each other or to the main app/plugin/icon via IPC, all requests
    # and interactions should be classified"): each plugin lent a login noting what it reads and keeps, and the programs
    # and hosts the platform and its plugins reach noted once it serves (apps.traffic)
    TRACE_LOGIN = True
    WATCH_OUTSIDE = True
    READ_HOOKS = READS

    def __init__(self, log=print, login=None, machines: dict | None = None, state: Path | None = None,
                 assistants: dict | None = None, settings=None, terminal=None):
        # its login: the user's environment variables, those saved after it started too (a setting entered on a page
        # holds across a restart), until the login app holds them (Login.save keeps one); a scratch preview's
        # (LIMINAL_PLATFORM_LOGIN=memory, 0.11.0): a copy of this process's, what the page saves kept in it alone
        if login is None:
            memory = os.environ.get(LOGIN_VAR, "").strip().lower() == "memory"
            login = EnvironmentLogin(env=dict(os.environ)) if memory else EnvironmentLogin(saved=saved_variables)
        super().__init__(log, login)
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
        self._hidden: set[str] | None = None  # the plugins hidden from the dock, read with them
        self._attaching = False  # set once attach_plugins ran: an enabled plugin is attached again
        self._setups: dict[str, Setup] = {}
        self._lock = threading.Lock()
        self._active: tuple[float, list[str]] | None = None
        self._states: dict[str, str] = {}  # each plugin's state when last asked: active | disabled | invalid (Connections)

    # -- who talks to whom (apps.traffic; the page's Connections) -------------------------------------------------
    def classify(self, method: str, path: str) -> str:
        """A page's request in its class: a terminal's keys and output and a job's output read are streams, a hook
        asked by name an ask; the rest as the frame says (a GET reads, anything else asks for a change)."""
        if "/terminal" in path or (method == "GET" and path.endswith(("/job", "/setup"))):
            return "stream"
        if path.endswith("/ask"):
            return "ask"
        return super().classify(method, path)

    def known_ports(self) -> dict[int, str]:
        """The framework's apps' ports on this machine (their variables moving them): a link to one is drawn as it."""
        from liminal_libs.machines.firewall import app_ports

        try:
            return {port: app for app, port in app_ports().items()}
        except Exception:  # noqa: BLE001 - none known
            return {}

    def connections(self, last: int = 200) -> dict:
        """The frame's picture with every platform plugin in it, attached or not, in its state (active, disabled, not
        valid); one disabled or not valid that nothing was said to is left out, named in `hidden`."""
        out = super().connections(last)
        nodes = {n["id"]: n for n in out["nodes"]}
        linked = {end for link in out["links"] for end in (link["from"], link["to"])}
        assistants, hidden = self.assistant_plugins(), []
        for name, p in {**self.machines(), **assistants}.items():
            state = self._states.get(name) or ("disabled" if not self.enabled(name) else "unknown")
            attached = self.plugin(name) is p
            if state != "active" and not attached and name not in linked:
                hidden.append(name)
                nodes.pop(name, None)
                continue
            nodes[name] = {"id": name, "role": "plugin", "title": p.title, "attached": attached, "state": state,
                           "icon": getattr(p, "ICON", "") or ("analysis" if name in assistants else "chip"),
                           "kind": "assistant" if name in assistants else "machine"}
        out["nodes"], out["hidden"] = list(nodes.values()), sorted(hidden)
        return out

    # -- disabled plugins (the user, 2026-11-07: "allow me to right click on the icons to disable them on the right
    # icon menu, also allow for enable disable switch (left to right) on the plugin description") -------------------
    @property
    def state_dir(self) -> Path:
        return self._state if self._state is not None else platform_dir()

    def _saved(self) -> None:
        """The folder's plugins.json, read once (the lock held): the plugins disabled, and those hidden from the dock."""
        if self._disabled is None:
            try:
                saved = json.loads((self.state_dir / PLUGINS_FILE).read_text(encoding="utf-8"))
                self._disabled = {n for n in saved.get("disabled", []) if isinstance(n, str)}
                self._hidden = {n for n in saved.get("hidden", []) if isinstance(n, str)}
            except (OSError, ValueError, AttributeError):
                self._disabled, self._hidden = set(), set()

    def disabled(self) -> set[str]:
        """The plugins disabled here, by name (the folder's plugins.json, kept across restarts)."""
        with self._lock:
            self._saved()
            return set(self._disabled)

    def hidden(self) -> set[str]:
        """The plugins hidden from the dock here, by name (kept beside the disabled ones): enabled or not, their icon is
        never in the tray."""
        with self._lock:
            self._saved()
            return set(self._hidden or ())

    def _keep(self, disabled: set[str], hidden: set[str]) -> None:
        """plugins.json written whole (a part file renamed): the plugins disabled, and those hidden from the dock."""
        folder = self.state_dir
        folder.mkdir(parents=True, exist_ok=True)
        part = folder / (PLUGINS_FILE + ".part")
        part.write_text(json.dumps({"disabled": sorted(disabled), "hidden": sorted(hidden)}, indent=1), encoding="utf-8")
        os.replace(part, folder / PLUGINS_FILE)
        with self._lock:
            self._disabled, self._hidden = set(disabled), set(hidden)

    def enabled(self, name: str) -> bool:
        return name not in self.disabled()

    def set_hidden(self, name: str, on: bool) -> dict:
        """A plugin hidden from the dock on the right, or shown there again (the user, 2026-11-08: "all plugins need a
        hide switch next to enable for the dock on the right"). Hidden, its icon leaves the tray while it stays as it
        was: enabled or not, attached, asked; its row in the list, its page and Connections keep it. Kept across
        restarts. The answer: hidden or not, and the tray as it is now."""
        self.platform_plugin(name)
        names = self.hidden()
        (names.add if on else names.discard)(name)
        self._keep(self.disabled(), names)
        self.log(f"platform: {name} {'hidden' if on else 'visible'}")
        return {"name": name, "hidden": on, "tray": self.tray().as_dict()}

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
        self._keep(names, self.hidden())
        with self._lock:
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
            self.traffic.own(m, name)
            try:
                with self.traffic.timed(self.NAME, name, "read", "present"):
                    present = m.present()
                if present:
                    names.append(name)
            except Exception:  # noqa: BLE001 - a plugin that cannot say is not active
                continue
        with self._lock:
            self._active = (now, names)
        return names

    def items(self) -> tuple[TrayItem, ...]:
        """An icon per active plugin, the machine plugins then the AI assistants, after the platform's own (the frame's
        tray puts the chip first); none the user hid from the dock."""
        machines, hidden = self.machines(), self.hidden()
        out = [TrayItem(name, getattr(machines[name], "ICON", "") or "chip", machines[name].title, "plugin", self.NAME)
               for name in self.active() if name in machines and name not in hidden]
        off = self.disabled()
        for name, p in self.assistant_plugins().items():
            if name in hidden or name in off:
                continue
            state = self._states.get(name)
            if state is None:  # not asked yet: whether its key and its plan serve
                state = "active" if self.assistant_validity(p)[0] else "invalid"
            if state == "active":
                out.append(TrayItem(name, getattr(p, "ICON", "") or "analysis", p.title, "plugin", self.NAME))
        return tuple(out)

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

        settings = load_settings(login=self.login_for(self.NAME))
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
                return False, f"no key: {names[0] if names else 'its key'} is not set (its Settings, on its page, set it)"
            return False, p.free_note(settings) or "its plan has no API access"
        except Exception as e:  # noqa: BLE001 - one that cannot say is not valid
            return False, f"cannot be read: {type(e).__name__}: {e}"

    def assistant_status(self, p) -> dict:
        """An AI assistant as the page shows it: who it is, enabled (the user's), valid (a key and a plan with API
        access) and why not; attached while both (its keys and plans are set on the charts app's Plugins view)."""
        on = self.enabled(p.name)
        self.traffic.own(p, p.name)
        if on:
            with self.traffic.timed(self.NAME, p.name, "read", "valid? (its key, its plan)"):
                valid, why = self.assistant_validity(p)
        else:
            valid, why = None, ""
        state = "active" if on and valid else "disabled" if not on else "invalid"
        with self._lock:
            self._states[p.name] = state
        self._settle(p, state == "active")
        return {"name": p.name, "title": p.title, "about": p.about, "version": p.version, "vendor": str(getattr(p, "vendor", "") or ""),
                "icon": getattr(p, "ICON", "") or "analysis",  # its maker's mark (0.10.1), else the chart
                "model": str(getattr(p, "default_model", "") or ""), "enabled": on, "valid": valid, "why": why, "state": state,
                "hidden": p.name in self.hidden(), "settings": self.settings_of(p), **self.api_card(p, on)}

    # -- a plugin's settings, entered on its page (the user, 2026-11-08: "i need a way to put my credentials in to the
    # namecheap plugin and allow it to function"): its keys (KeyVar), kept through the platform's login (Login.save:
    # the user's environment variables until the login app holds them); a value never shown back, never logged ----------
    def settings_of(self, p) -> list[dict]:
        """A plugin's settings as its page shows them: each key it declares, set or not (never its value)."""
        keys = [k for k in (getattr(p, "keys", None) or ()) if getattr(k, "name", "")]
        if not keys:
            return []
        try:
            have = set(self.login_for(self.NAME).variables([n for k in keys for n in k.names]))
        except Exception:  # noqa: BLE001 - a login that cannot say: none is said set
            have = set()
        return [{"variable": k.name, "label": k.label, "secret": bool(k.secret), "hint": k.hint or "",
                 "set": any(n in have for n in k.names)} for k in keys]

    def save_settings(self, name: str, body: dict) -> dict:
        """A plugin's settings kept: only its own keys; a value left empty keeps it as it is; `forget` drops one.
        The plugin reads them anew (its settings_changed, when it has one) and the platform's settings too."""
        p = self.machines().get(name) or self.assistant_plugins().get(name)
        if p is None:
            raise Refused(HTTPStatus.NOT_FOUND, f"no plugin named {name!r}")
        values, forget = body.get("values") or {}, body.get("forget") or []
        if not isinstance(values, dict) or not isinstance(forget, list):
            raise Refused(HTTPStatus.BAD_REQUEST, "values is {variable: value}, forget a list of variables")
        allowed = {k.name for k in (getattr(p, "keys", None) or ()) if getattr(k, "name", "")}
        unknown = [str(v) for v in [*values, *forget] if v not in allowed]
        if unknown:
            raise Refused(HTTPStatus.BAD_REQUEST, f"not {p.title}'s settings: {', '.join(unknown)}")
        changes = []
        for variable, value in values.items():
            if value is None:
                continue
            if not isinstance(value, str) or len(value) > MAX_SETTING:
                raise Refused(HTTPStatus.BAD_REQUEST, f"{variable} is text, at most {MAX_SETTING} characters")
            if value.strip():
                changes.append((variable, value.strip()))
        changes += [(v, None) for v in forget]
        if not changes:
            raise Refused(HTTPStatus.BAD_REQUEST, "nothing to keep: every field was left empty (an empty field keeps its value)")
        where, login = "", self.login_for(self.NAME)
        for variable, value in changes:
            try:
                where = login.save(variable, value)
            except Unauthorized as e:
                raise Refused(HTTPStatus(e.status) if 400 <= e.status < 600 else HTTPStatus.INTERNAL_SERVER_ERROR, e.reason) from None
        with self._lock:
            self._settings_cache = None
        changed = getattr(p, "settings_changed", None)
        if callable(changed):
            try:
                with self.traffic.timed(self.NAME, name, "change", "its settings changed"):
                    changed()
            except Exception:  # noqa: BLE001 - the plugin reads them on its own then
                pass
        kept, dropped = [v for v, x in changes if x is not None], [v for v, x in changes if x is None]
        self.log(f"platform: {name} settings kept: {', '.join(kept) or '-'}; forgotten: {', '.join(dropped) or '-'}")  # names only
        lines = ([f"kept: {', '.join(kept)}"] if kept else []) + ([f"forgotten: {', '.join(dropped)}"] if dropped else [])
        return {"said": f"{p.title}'s settings kept in {where}", "lines": lines + [f"{p.title} reads them now"], "ok": True,
                "kept": kept, "forgotten": dropped}

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
            self.traffic.own(m, m.name)
            if getattr(m, "login", None) is None:  # the platform's login lent, attached or not: its settings read through it
                m.login = self.login_for(m.name)
            try:
                with self.traffic.timed(self.NAME, m.name, "read", "status"):
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
            self._states[m.name] = state
        self._settle(m, state == "active")
        with self._lock:
            setup = self._setups.get(m.name)
        return {"name": m.name, "title": m.title, "about": m.about, "version": m.version, "status": status,
                "icon": getattr(m, "ICON", "") or "chip", "enabled": on, "valid": valid, "why": why, "state": state,
                "hidden": m.name in self.hidden(), "steps": list(getattr(m, "STEPS", ()) or ()), "asks": self.asks(m) if state == "active" else [],
                "hooks": self.hooks(m), "setup": setup.describe(last=200) if setup else None,
                "terminal": {"open": self.terminal_of(m.name) is not None}, "settings": self.settings_of(m), **self.api_card(m, on)}

    @staticmethod
    def api_card(p, live: bool = True) -> dict:
        """What a plugin attaches to (0.20.0, plugin API 2.2: liminal-libs sources/apis.py; the user, 2026-11-11: "each
        plugin should reflect the the API its attached to, and present links that provide documentation ... it should
        also expose more of what the API is about"): its declarations and what it learned of them while it ran, asking
        nothing of it (api_facts says what it already holds; a disabled plugin is not asked even that: `live`, 0.20.1);
        the page draws them with the library's apis.js."""
        from liminal_libs.sources import apis as apis_mod

        try:
            declared = apis_mod.as_dicts(getattr(p, "apis", ()) or ())
        except Exception:  # noqa: BLE001 - a declaration that cannot be read: the page says it declares none
            declared = []
        return {"pluginApi": str(getattr(p, "api", "") or ""), "apis": declared, "apiFacts": apis_mod.facts_of(p) if declared and live else {}}

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
        """One of a machine plugin's hooks by name (asks), its answer as JSON (a rule, a startup: described). Its refusal
        (400) or failure (502) is a HookRefused: the plugin's own words, and the argument accepting a refusal that names one."""
        m = self.machine(name)
        self._refuse_disabled(name)
        if hook not in self.asks(m):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} is not asked {hook!r} here: {', '.join(self.asks(m)) or 'nothing'}")
        if hook not in READS:  # its name and how many arguments, never their values: a key pasted into a form (0.20.1)
            self.log(f"platform: {name} asked {hook}" + (f" ({len(args)} argument{'' if len(args) == 1 else 's'})" if args else ""))
        try:
            with self.traffic.timed(self.NAME, name, "read" if hook in READS else "ask", hook):
                answer = m.ask(hook, *args)
        except (TypeError, ValueError, LookupError) as e:
            raise HookRefused(HTTPStatus.BAD_REQUEST, f"{type(e).__name__}: {e}", str(e), _accepting(e)) from None
        except Exception as e:  # noqa: BLE001 - the plugin's own words
            raise HookRefused(HTTPStatus.BAD_GATEWAY, f"{type(e).__name__}: {e}", str(e)) from None
        return _json_of(answer)

    def check(self, name: str) -> dict:
        """A plugin's check of this PC for what it installs (the user: \"each plugin should have a scheme for checking the
        environment to see if it supports installing the operating system it has in its name\")."""
        m = self.machine(name)
        self._refuse_disabled(name)
        if "check" not in self.hooks(m):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} checks nothing")
        try:
            with self.traffic.timed(self.NAME, name, "read", "check"):
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
            # a plugin with installs to choose from updates the one chosen and says itself when it is not there (0.14.0)
            if "check" in hooks and not callable(getattr(m, "chosen", None)) and not self.check(name).get("installed"):
                raise Refused(HTTPStatus.CONFLICT, f"{name} is not installed: install it first")
        elif "check" in hooks and not (steps and set(steps) <= set(PREPARING)):
            c = self.check(name)
            if not (c.get("ready") or c.get("installed")):
                raise Refused(HTTPStatus.CONFLICT, f"the install is locked: {c.get('why') or 'this PC does not meet what it needs'}")
        with self._lock:
            current = self._setups.get(name)
            if current is not None and current.running:
                raise Refused(HTTPStatus.CONFLICT, f"{name} is busy already ({current.action})")
            setup = Setup(m, steps, action, self.traffic, self.NAME)
            self._setups[name] = setup
            self.traffic.own(m, name)
            setup.thread.start()  # running before the lock goes: a second ask sees it busy (0.19.0)
        self.log(f"platform: {'updating the packages of' if action == 'update' else 'setting up'} {name}"
                 + (f" ({', '.join(setup.steps)})" if setup.steps else ""))
        self.traffic.record(self.NAME, name, "change", f"{action} started" + (f": {', '.join(setup.steps)}" if setup.steps else ""))
        return setup

    def start_hook_job(self, name: str, hook: str, args: list) -> Setup:
        """One of a plugin's hooks asked as a job (0.19.0; the Docker plugin's pull: a large image takes minutes): only one
        the page may ask and the plugin names in its JOB_HOOKS, run in a thread with the job's output as its `log`, each
        line followed on the page as it comes; its answer (or its refusal, in its own words) at the end."""
        m = self.machine(name)
        self._refuse_disabled(name)
        if hook not in self.asks(m) or hook not in tuple(getattr(m, "JOB_HOOKS", ()) or ()):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} runs no {hook!r} as a job")
        if not isinstance(args, list) or len(args) > 16:
            raise Refused(HTTPStatus.BAD_REQUEST, "args is a list of the hook's arguments")
        with self._lock:
            current = self._setups.get(name)
            if current is not None and current.running:
                raise Refused(HTTPStatus.CONFLICT, f"{name} is busy already ({current.action})")
            job = Setup(m, None, hook, self.traffic, self.NAME, call=lambda log: m.ask(hook, *args, log=log))
            self._setups[name] = job
            self.traffic.own(m, name)
            job.thread.start()  # running before the lock goes: a second ask sees it busy
        # its name and how many arguments, never their values (0.20.1, as an ask's)
        self.log(f"platform: {name} asked {hook} as a job" + (f" ({len(args)} argument{'' if len(args) == 1 else 's'})" if args else ""))
        self.traffic.record(self.NAME, name, "change", f"{hook} started")
        return job

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
        try:
            with self.traffic.timed(self.NAME, name, "ask", "terminal"):
                argv = m.terminal()
        except Exception as e:  # noqa: BLE001 - not installed: its words
            raise Refused(HTTPStatus.CONFLICT, str(e)) from None
        current = self.terminal_of(name)
        if current is not None and current.alive:
            if list(getattr(current, "argv", None) or argv) == list(argv):
                return current.read(max(0, current.output.end - KEPT_SHOWN))  # where it was: its last lines
            self.close_terminal(name)  # another install chosen meanwhile (0.12.0): that one's terminal instead
        made = getattr(m, "terminal_title", None)
        title = made() if callable(made) else f"{getattr(m, 'user', '') or 'you'} in {getattr(m, 'distribution_name', '') or m.title}"
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
        self.traffic.record(self.NAME, self._terminal_program(term), "stream", "closed")
        self.log(f"platform: the terminal into {name} closed")
        return True

    @staticmethod
    def _terminal_program(term) -> str:
        """The program a login terminal runs, as a link's end (process:wsl)."""
        return f"process:{program_name(None, list(getattr(term, 'argv', None) or [])) or 'terminal'}"

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
        if method == "POST" and path.startswith("/api/plugins/") and path.endswith("/settings"):
            return 200, self.save_settings(path[len("/api/plugins/"):-len("/settings")], body)
        if method == "POST" and path.startswith("/api/plugins/") and path.endswith("/enabled"):
            on = body.get("on")
            if not isinstance(on, bool):
                raise Refused(HTTPStatus.BAD_REQUEST, "on is true or false")
            return 200, self.set_enabled(path[len("/api/plugins/"):-len("/enabled")], on)
        if method == "POST" and path.startswith("/api/plugins/") and path.endswith("/hidden"):
            on = body.get("on")
            if not isinstance(on, bool):
                raise Refused(HTTPStatus.BAD_REQUEST, "on is true or false")
            return 200, self.set_hidden(path[len("/api/plugins/"):-len("/hidden")], on)
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
                if setup is not None and since is not None and setup.running and _wait(query):
                    setup.output.wait(since, _wait(query))  # held until it prints more, or ends
                return 200, (setup.describe(since=since) if setup else {"machine": name, "running": False, "lines": [], "done": None,
                                                                       "text": "", "from": 0, "offset": 0})
            if method == "GET" and action == "check":
                return 200, self.check(name)
            if method == "POST" and action == "job":
                what = body.get("action")
                if what == "hook":  # one of its hooks as a job (0.19.0)
                    hook, args = body.get("hook"), body.get("args") or []
                    if not isinstance(hook, str):
                        raise Refused(HTTPStatus.BAD_REQUEST, "hook is a hook's name")
                    return 202, self.start_hook_job(name, hook, args).describe(since=0)
                if what not in ("install", "update"):
                    raise Refused(HTTPStatus.BAD_REQUEST, "action is install, update or hook")
                job = self.start_setup(name, None, "update" if what == "update" else "setup")
                return 202, job.describe(since=0)
            if action == "terminal" and method == "POST":
                return 200, self.open_terminal(name)
            if action == "terminal" and method == "GET":
                term = self.terminal_of(name)
                if term is None:
                    raise Refused(HTTPStatus.NOT_FOUND, f"no terminal is open into {name}")
                got = term.read(int(query.get("since") or 0), _wait(query))
                self._close_idle()
                return 200, got
            if action == "terminal/input" and method == "POST":
                data, term = body.get("data"), self.terminal_of(name)
                if not isinstance(data, str) or len(data) > MAX_INPUT:
                    raise Refused(HTTPStatus.BAD_REQUEST, f"data is the keys typed, at most {MAX_INPUT} characters")
                if term is None or not term.alive:
                    raise Refused(HTTPStatus.CONFLICT, f"no terminal is open into {name}")
                term.write(data)
                self.traffic.record(self.NAME, self._terminal_program(term), "stream", "keys typed")  # never the keys
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
                try:
                    return 200, {"answer": self.ask(name, hook, args)}
                except HookRefused as e:  # the plugin's words, and what accepts a refusal (a form's second confirmation)
                    return e.status, e.answer()
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
                    with self.traffic.timed(self.NAME, name, "ask", f"run {program_name(None, command) or 'a command'}"):
                        return 200, {"output": m.run(*command)}
                except Exception as e:  # noqa: BLE001 - the plugin's words
                    raise Refused(HTTPStatus.BAD_GATEWAY, f"{type(e).__name__}: {e}") from None
        return super().api(handler, method, path, query, body)
