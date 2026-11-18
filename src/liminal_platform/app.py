"""The platform app: the frame's App with the chip icon; its routes serve the machine's facts, the machine
plugins (their status, a setup run in a thread with its lines kept, a command, disabled or enabled), the Docker
instances and the plugins attached. 0.32.0: each plugin's status also says what the plugin shares with the platform
(its Internal API: `internal`, liminal-libs 1.63.0's internal.py), and the platform says its own two (GET
/api/app/apis, the frame's): its routes (routes.py) and what it calls on its plugins (CALLS), and what it associates
with (apis.py)."""
from __future__ import annotations

import contextlib
import itertools
import json
import math
import os
import platform as py_platform
import re
import sys
import threading
import time
from http import HTTPStatus
from pathlib import Path

from liminal_libs import docker as docker_mod
from liminal_libs import layout
from liminal_libs.apps import App, EnvironmentLogin, Refused, TrayItem, Unauthorized, program_name, saved_variables
from liminal_libs.machines.terminal import Output, Terminal
from liminal_libs.web import WRITE_HEADER

from .routes import ROUTES  # its own routes, as its Internal API lists them: plain rows, nothing imported with them

try:  # a declared tab's id (url-safe) and the fewest seconds between its asks, as liminal-libs apps/tabs.py says them
    from liminal_libs.apps.tabs import ID as TAB_ID, MIN_EVERY as TAB_MIN_EVERY
except ImportError:  # a library from before its tabs: no plugin of it declares one, and a tab is what apps/tabs.py makes
    TAB_ID, TAB_MIN_EVERY = re.compile(r"[A-Za-z0-9_-]{1,40}"), 1.0

try:  # what a plugin shares with its app, read from the plugin itself (liminal-libs 1.63.0's internal.py)
    from liminal_libs import internal as internal_mod
except ImportError:  # an older library: no status carries `internal` (the page says so), its reads are the platform's
    internal_mod = None

PORT = 8775
NOT_ASKED = ("setup", "settings", "scan", "run")  # a machine's hooks the page asks through its own routes, or not at all
READS = ("present", "status", "view", "charts", "instances", "wanted", "services", "startups", "processes",
         "serving")  # asks not logged
# (and a plugin's tab hooks: PlatformApp.reads_of). `serving` (0.31.0): what a model server offers the other AI plugins
# (liminal-libs 1.62.0's ModelServer.serving: its instances as it holds them, no network and no process), asked through
# the platform by a harness for its page and by a model server looking for another's hold on a port
DIR_VAR = "LIMINAL_PLATFORM_DIR"  # the platform's own folder: its log, which plugins are disabled
LOGIN_VAR = "LIMINAL_PLATFORM_LOGIN"  # memory: a scratch preview's login, nothing it saves leaving the process
PLUGINS_FILE = "plugins.json"
TERMINAL_IDLE_S = 120.0  # a terminal no page has read for this long is closed
PREPARING = ("wsl", "update", "version")  # setup steps that prepare this PC: never locked by a plugin's check
MAX_INPUT = 8192  # characters of keys a page sends at once
MAX_SETTING = 4096  # characters of one setting entered on a plugin's page
MAX_WAIT = 5.0  # seconds a page's read may be held until there is output (the echo at once, one read at a time)
KEPT_SHOWN = 4000  # characters of a terminal open already a page is shown when it comes back to it
# a hook asked as a job that refuses before its first line, naming the argument that accepts the refusal (a licence to
# accept: liminal-libs 1.55.0's GeoIP install), is waited for this long at most, and refused as an ask's refusal is
JOB_REFUSAL_S = 1.0
# 0.31.0: as the platform stops, the asks of its plugins still under way (a Start clicked as it stops) and the jobs it
# asked to stop are waited for this long at most in all, before each plugin is told that it stops
STOP_WAIT_S = 5.0
STOPPING = "the platform is stopping: its plugins are asked nothing new"  # an ask or a job refused meanwhile (503)


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


def interface_of(p) -> dict:
    """The library's interface a plugin is built on (0.23.0, Connections' middle periphery): the nearest class of its
    line that liminal-libs defines (a firewall plugin's Firewall, a WSL plugin's WslDistribution, else MachinePlugin or
    AssistantPlugin), by its name and the first line of what it says of itself."""
    for c in type(p).__mro__[1:]:
        if (getattr(c, "__module__", "") or "").startswith("liminal_libs."):
            said = (c.__doc__ or "").strip().split("\n", 1)[0].strip()
            return {"id": f"interface:{c.__name__}", "title": c.__name__, "sub": said[:200], "module": c.__module__}
    return {"id": "interface:Plugin", "title": "Plugin", "sub": "", "module": ""}


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


SECTIONS = ("machine", "virtualization", "os", "cloud")  # the list's sections for machine plugins, in its order (0.25.0, 0.26.0)
# 0.31.0 (the user, 2026-11-16: "i need 3 plugins for inference serving local models on the platform, :: lama.cpp,
# ollama and vLLM, i also need 3 harness plugins for the platform :: OpenCode, Aider, and Continue"; "they will be
# classified as AI plugins"; "the other plugins are strictly proprietary service plugins"): the list's AI section. The
# AI assistants (a vendor's service each) are its proprietary services; after them come the machine plugins whose
# SECTION is "ai", each in the group it names. SECTIONS stays the four a machine plugin is otherwise drawn under
AI_SECTION = "ai"
AI_GROUPS = ("inference", "harness")  # a machine plugin's groups under AI, in the list's order and the tray's


def group_of(plugin) -> str:
    """The group of the AI section a machine plugin is drawn in (0.31.0): its own word, liminal-libs 1.62.0's
    `AiPlugin.GROUP`, when its SECTION is "ai": "inference" for a model server's (llama.cpp, Ollama, vLLM), "harness"
    for a coding harness's (OpenCode, Aider, Continue). "" for every other plugin: one of another section, one naming a
    group the platform does not draw, one from an older library with no GROUP at all."""
    group = getattr(plugin, "GROUP", "")
    ai = getattr(plugin, "SECTION", "") == AI_SECTION
    return group if ai and isinstance(group, str) and group in AI_GROUPS else ""


def section_of(plugin) -> str:
    """The section of the list a machine plugin is drawn under (0.25.0; the user, 2026-11-14: "classify the cloud plugins
    under the 'cloud plugins' section which should be on the far left"; 0.26.0, 2026-11-15: "platform needs a
    virtualization plugins section"; "just like cloud plugins"; "then OS plugins"). The plugin's own word, liminal-libs
    1.51.0's `MachinePlugin.SECTION`: "virtualization" for a hypervisor's or a container engine's (Hyper-V, libvirt, LXD,
    Docker, Kubernetes, Windows containers), "os" for an operating system's (WSL's distributions, the Windows and Linux
    administration and firewalls), "cloud" for a cloud provider's account. 0.31.0 (2026-11-16: "they will be classified
    as AI plugins"): "ai" for a model server's or a harness's, which says its group beside it (group_of). Anything else
    ("ai" with no group the platform draws too), or none from an older library or plugin, is "machine"."""
    if group_of(plugin):
        return AI_SECTION
    section = getattr(plugin, "SECTION", "")
    return section if section in SECTIONS else "machine"


# the page's own tabs on every plugin's page, whose ids a declared tab never takes (in any case): Main, External API and
# Internal API (0.32.0, liminal-libs 1.63.0; the user, 2026-11-16: "there should be an external api tab, and an
# internal api tab"), and "api", the address of the API tab before them, which the page opens as External API
OWN_TABS = ("main", "api", "external", "internal")
TAB_MAX_EVERY = 3600.0  # the most seconds between a tab's asks
MAX_TABS = 8  # declared tabs drawn on one plugin's page
MAX_TAB_TITLE = 60  # characters of a tab's title


def _tab_said(t) -> dict | None:
    """One declared tab as it says itself: a Tab's as_dict(), or a dict in that shape; None for anything else."""
    try:
        d = t.as_dict() if callable(getattr(t, "as_dict", None)) else t
    except Exception:  # noqa: BLE001 - not a tab
        return None
    return d if isinstance(d, dict) else None


def tabs_of(plugin) -> list[dict]:
    """The tabs a machine plugin declares after Main, External API and Internal API (the user, 2026-11-14: "so for the
    firewall's both are going to get a 'world wide web view'"; "there needs to be a way to 'filter' (another tab)"):
    liminal-libs apps/tabs.py's `Tab`s in its `TABS`, each as its `as_dict()` says it, {id, title, hook, every}; none
    from an older library or plugin. The page asks a tab's hook every `every` seconds while the tab is shown, and the
    platform asks it as a read: noted as one in who talks to whom, never logged, never a change. So a tab is left out
    when its hook is the setup, a command, the settings or the scan (asked through their own routes, or not at all) or
    one of its jobs; so is one whose id is one of the page's own (OWN_TABS: Main's, External API's, Internal API's, and
    "api", the old address of External API) or an earlier tab's, in any case, and one that cannot say itself. Its every
    is kept between TAB_MIN_EVERY and TAB_MAX_EVERY seconds, its title to MAX_TAB_TITLE characters (its id when it has
    none); MAX_TABS at the most."""
    try:
        declared = list(itertools.islice(iter(getattr(plugin, "TABS", ()) or ()), 4 * MAX_TABS))
        jobs = {h for h in (getattr(plugin, "JOB_HOOKS", ()) or ()) if isinstance(h, str)}
    except Exception:  # noqa: BLE001 - a declaration that cannot be read: no tabs
        return []
    out: list[dict] = []
    seen = set(OWN_TABS)
    for t in declared:
        d = _tab_said(t)
        if d is None:
            continue
        tid, title, hook, every = d.get("id"), d.get("title"), d.get("hook"), d.get("every", 5.0)
        if not isinstance(tid, str) or not TAB_ID.fullmatch(tid) or tid.lower() in seen:
            continue
        if not isinstance(hook, str) or not hook.isidentifier() or hook in NOT_ASKED or hook in jobs:
            continue
        if isinstance(every, bool) or not isinstance(every, (int, float)) or not math.isfinite(every):
            continue
        seen.add(tid.lower())
        words = title.strip()[:MAX_TAB_TITLE] if isinstance(title, str) and title.strip() else tid
        out.append({"id": tid, "title": words, "hook": hook, "every": min(max(float(every), TAB_MIN_EVERY), TAB_MAX_EVERY)})
        if len(out) == MAX_TABS:
            break
    return out


def tab_hooks(plugin) -> list[str]:
    """The hooks of the tabs a machine plugin declares (tabs_of), each once: reads the page asks while a tab is shown."""
    return list(dict.fromkeys(t["hook"] for t in tabs_of(plugin)))


def cancel_hooks(plugin) -> tuple[str, ...]:
    """The hooks of a machine plugin whose job can be asked to stop (0.31.0): those it names in its `CANCEL_HOOKS`
    (liminal-libs 1.62.0's AiPlugin: its install; a model server's download of a model). Such a hook looks at the job's
    output between its steps (`log.cancelled`) and ends by itself. None from an older library or plugin, or from a
    declaration that cannot be read."""
    try:
        return tuple(h for h in (getattr(plugin, "CANCEL_HOOKS", ()) or ()) if isinstance(h, str))
    except Exception:  # noqa: BLE001 - a declaration that cannot be read: none of its jobs is cancelled
        return ()


class Setup:
    """A machine plugin's job under way, in a thread: its setup, its packages' update, or one of its hooks (`action`:
    the hook's name; 0.19.0, `call`: the hook asked with the job's output as its `log`); what it prints as it comes
    (`output`, read from an offset by the page's terminal panel), its steps (a hook's answer) when done. 0.31.0 (a
    model's download runs for a long time): a hook's job can be asked to stop when the plugin names that hook in its
    CANCEL_HOOKS (`cancels`, `cancel`); a setup, a packages' update and every other hook run to their end."""

    def __init__(self, machine, steps, action: str = "setup", traffic=None, by: str = "platform", call=None):
        self.machine = machine
        self.action = action
        self.steps = tuple(steps) if steps else None
        self.call = call  # (log) -> the hook's answer, for a hook asked as a job; let go once it has run (below)
        self.hooked = call is not None  # a hook asked as a job, said after its call is let go
        self.answer = None  # that answer, once it is in
        self.refused: HookRefused | None = None  # its refusal before its first line, naming what accepts it (an ask's)
        self.output = Output()
        self.done: list[dict] | None = None
        self.error: str | None = None
        self.started = time.time()
        self.traffic, self.by = traffic, by  # who asked it, noted when it ends (apps.traffic)
        self.thread = threading.Thread(target=self._run, name=f"setup-{machine.name}", daemon=True)
        # 0.31.0: its work's end and a cancel, taken one after the other, so a cancel that comes as the work ends is
        # either seen by it or refused, and whether it was cancelled is decided once, as the work ended
        self._ending = threading.Lock()
        self.ended = False  # its work has returned or raised: a cancel from then on changes nothing
        self.stopped = False  # a cancel had been asked when its work ended: it was cancelled

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
            accept = _accepting(e) if self.call is not None and isinstance(e, (TypeError, ValueError, LookupError)) else None
            if accept and not self.output.end:  # before its first line: the page offers it as a second confirmation
                self.refused = HookRefused(HTTPStatus.BAD_REQUEST, self.error, str(e), accept)
        # The call holds the hook's arguments, a sudo password typed into its form among them: let go of it as soon as
        # it has run, so the job kept for its panel keeps nothing the form was given.
        self.call = None
        with self._ending:  # from here on a cancel is refused (cancel): it was cancelled when one had been asked
            self.ended = True
            self.stopped = self.cancelling
        if self.traffic is not None:
            ok = self.error is None and all(d.get("ok") is not False for d in self.done or [] if isinstance(d, dict))
            how = "" if ok else ": cancelled" if self.stopped else ": it failed"
            self.traffic.record(self.by, self.machine.name, "change", f"{self.action} ended{how}",
                                (time.perf_counter() - began) * 1000, ok or self.stopped)  # asked to stop: no failure
        self.output.finish()  # its end told to whoever waits on its lines (start_hook_job, the panel's next read)

    @property
    def running(self) -> bool:
        return self.thread.is_alive()

    @property
    def lines(self) -> list[str]:
        return self.output.text.splitlines()

    @property
    def cancels(self) -> bool:
        """Whether it can be asked to stop (0.31.0): a hook's job, the hook one the plugin names in its CANCEL_HOOKS,
        its output one that takes a cancel (liminal-libs 1.62.0's Output; an older library's takes none)."""
        can = callable(getattr(self.output, "cancel", None))
        return can and self.hooked and self.action in cancel_hooks(self.machine)

    @property
    def cancelling(self) -> bool:
        """Whether it was asked to stop: its output's flag (never set with a library before 1.62.0)."""
        return bool(getattr(self.output, "cancelled", False))

    def cancel(self) -> bool:
        """Its work asked to stop: the flag of its output set (liminal-libs 1.62.0's Output.cancel) for the hook to see
        between its steps, and whoever waits on it told; asked twice, nothing changes. False when nothing was asked: an
        older library's output takes no cancel, or its work has ended already (a cancel that comes as it ends is too
        late, and the job is said as it ended, never as cancelled)."""
        cancel = getattr(self.output, "cancel", None)
        if not callable(cancel):
            return False
        with self._ending:
            if self.ended or getattr(self.output, "finished", False):
                return False
            cancel()
        return True

    def describe(self, since: int | None = None, last: int | None = None) -> dict:
        """Its state; with `since`, the text printed after that offset (the panel's next part); `last`: only so many
        lines. 0.31.0: `cancels` (it can be asked to stop: the page offers Cancel while it runs), `cancelling` (it was
        asked) and `cancelled` (it had been asked when its work ended, and it has ended)."""
        running, cancelling = self.running, self.cancelling
        ok = None if self.done is None else (self.error is None and all(d["ok"] is not False for d in self.done))
        out = {"machine": self.machine.name, "action": self.action, "steps": list(self.steps or ()), "running": running,
               "lines": self.lines[-last:] if last else self.lines, "done": self.done, "error": self.error,
               "startedAt": self.started, "ok": ok,
               "cancels": self.cancels, "cancelling": cancelling, "cancelled": self.stopped and not running}
        if self.hooked:
            out["hook"], out["answer"] = True, self.answer
        if since is not None:
            out["text"], out["from"], out["offset"] = self.output.read(since)
        return out


# What the platform's own code calls and reads on a plugin of each kind (0.32.0; liminal-libs 1.63.0's internal.py: a
# plugin's Internal API says, for each hook, whether the app's object code uses it and how; the user, 2026-11-17: "all
# plugins are middleware", "even for other plugins", "and then the app object code"). Each `how` is in the code's
# words; the platform's own Internal API lists both by kind. tests/test_internal_tab.py holds them to this module's
# source: every name its code reads or calls on a plugin is here, and every name here is one it does (but `instances`,
# asked through liminal_libs.docker; `api_facts`, through facts_of; `attach` and `detach`, which the frame calls).
CALLS = {
    "machine": {
        "present": "whether it is there: for the tray, at most once a minute",
        "status": "its state: each GET /api/machines/{name}, /api/machines and /api/status, while it is enabled",
        "instances": ("its Docker instances: GET /api/instances and /api/status, while it is enabled "
                      "(liminal_libs.docker.instances)"),
        "interface": "the hooks it answers: with each status and each ask",
        "setup": "POST /api/machines/{name}/setup and /job {action: install}: its steps, as a job",
        "update_packages": "POST /api/machines/{name}/job {action: update}, as a job",
        "check": "GET /api/machines/{name}/check: while its page is shown, and before an install or an update",
        "terminal": "POST /api/machines/{name}/terminal: the command its login terminal runs",
        "terminal_title": "its terminal's title (else its user and distribution_name)",
        "run": "POST /api/machines/{name}/run: a client's command, never the page's",
        "settings_changed": "after POST /api/plugins/{name}/settings kept them",
        "api_facts": "what it learned of its APIs: with each status while it is enabled",
        "attach": "while it is enabled and valid: the platform and a login that notes what it reads and keeps",
        "detach": "when it is disabled or not valid",
        "app_stopping": ("when the platform stops, once the asks and the jobs that take a cancel under way are "
                         "waited for (STOP_WAIT_S at the most): each machine plugin that has it, enabled or "
                         "not, attached or not"),
        "ask": ("any other hook by name: POST /api/machines/{name}/ask, and /job {action: hook} for one of its "
                "JOB_HOOKS")},
    "assistant": {
        "served": "whether its key and its plan serve: with each status",
        "keys_set": "whether its key is set, when it does not serve",
        "free_note": "why its plan has no API access",
        "settings_changed": "after POST /api/plugins/{name}/settings kept them",
        "interface": "the hooks it answers: in GET /api/status's plugins while it is attached (the frame's plugins())",
        "api_facts": "what it learned of its APIs: with each status while it is enabled",
        "attach": "while it is enabled and valid", "detach": "when it is disabled or not valid"}}
ATTRIBUTES = {  # read or looked up, never called (KIND: which of CALLS' kinds it is; chosen: whether it has installs to
    # choose from, looked up before an update, which it then checks itself)
    "machine": ("KIND", "name", "title", "about", "version", "SYSTEM", "ICON", "SECTION", "STEPS", "TABS", "JOB_HOOKS",
                "keys", "apis", "api", "app", "login", "user", "distribution_name", "chosen", "GROUP",
                "CANCEL_HOOKS"),
    "assistant": ("KIND", "name", "title", "about", "version", "SYSTEM", "ICON", "vendor", "default_model", "key_names",
                  "keys", "apis", "api", "app")}
# the terms of the platform's ask (PlatformApp.ask; POST /api/machines/{name}/ask), as a plugin's Internal API says them
ASK_TERMS = (f"the hooks a machine plugin answers (its tabs' too), while it is enabled, none of "
             f"{', '.join(NOT_ASKED[:-1])} and {NOT_ASKED[-1]} (routes of their own, or none); the arguments by "
             "position, in one list; its answer as JSON; a refusal is a HookRefused: 400 with the plugin's own words "
             "and the argument that accepts it, a failure 502; none begun while the platform stops (503)")
PAGE_ASKS_DEPTH = 6  # how deep a plugin's status is walked for the hooks its page asks (page_asks)
PAGE_ASKS_NODES = 2000  # and how many of its dicts and lists at the most
PAGE_ASKS_EACH = 100  # values of each looked at: a table's rows past its first hundred are more of the same
MAX_PAGE_ASKS = 200  # hooks' names taken from it at the most


def page_asks(status) -> list[str]:
    """The hooks a plugin's status names for its page to ask (its forms', actions' and options' `hook`; a table's
    `move`, `select`, options, actions and tasks): the value of every key named "hook" that is a hook's name, each once,
    the status walked through its dicts and lists, the shallowest first: PAGE_ASKS_DEPTH deep, PAGE_ASKS_NODES of them
    and PAGE_ASKS_EACH values of each at the most, so a long table cannot hide the forms after it. Nothing of the
    plugin is asked, and the status is not changed; a status that is not a dict names none. Its Internal API then says
    of those hooks that its page asks them, which tells one its page asks from one that only other plugins ask."""
    if not isinstance(status, dict):
        return []
    found: dict[str, None] = {}
    queue, at = [(status, 0)], 0
    try:
        while at < len(queue) and len(found) < MAX_PAGE_ASKS:
            node, depth = queue[at]
            at += 1
            if isinstance(node, dict):
                hook = node.get("hook")
                if isinstance(hook, str) and hook.isidentifier() and len(hook) <= 80:
                    found.setdefault(hook, None)
                values = node.values()
            else:
                values = node
            if depth >= PAGE_ASKS_DEPTH:
                continue
            for value in itertools.islice(values, PAGE_ASKS_EACH):
                if len(queue) >= PAGE_ASKS_NODES:
                    break
                if isinstance(value, (dict, list, tuple)):
                    queue.append((value, depth + 1))
    except Exception:  # noqa: BLE001 - a status that cannot be walked: what was found in it so far
        pass
    return list(found)


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
    # its own Internal API (liminal-libs 1.63.0's App, GET /api/app/apis): what its code calls and reads on its plugins
    # of each kind, and its routes beside the frame's; its External API is `apis` (apis.py, imported when asked)
    CALLS = CALLS
    ATTRIBUTES = ATTRIBUTES
    ROUTES = ROUTES
    # and what a hook asked as a job is handed beside its arguments, which neither CALLS nor ROUTES says (0.32.0):
    # lines internal.app_internal reads whole, each at most 400 characters (NOTE_CHARS), 40 at the most (MAX_WORDS)
    INTERNAL_NOTES = (
        "A hook asked as a job (one of its JOB_HOOKS: POST /api/machines/{name}/job {action: hook, hook, args}) is "
        "called with its arguments by position and log=, the job's output: each line it gives log (log(line)) is "
        "shown in the job's panel as it comes (GET /api/machines/{name}/job?since=), and its answer once it ends.",
        "log.cancelled is set by the page's Cancel (POST /api/machines/{name}/job/cancel) for a hook its "
        "CANCEL_HOOKS names (from liminal-libs 1.62.0): the hook looks at it between its steps and ends by itself. "
        "Any other job runs to its end.",
        "The job lets go of its arguments once the hook has run (a password typed into its form among them): what it "
        "keeps for its panel is the hook's lines, its answer and its state, nothing it was asked with.")

    def __init__(self, log=print, login=None, machines: dict | None = None, state: Path | None = None,
                 assistants: dict | None = None, settings=None, terminal=None, once: bool = False):
        # its login: the user's environment variables, those saved after it started too (a setting entered on a page
        # holds across a restart), until the login app holds them (Login.save keeps one); a scratch preview's
        # (LIMINAL_PLATFORM_LOGIN=memory, 0.11.0): a copy of this process's, what the page saves kept in it alone
        if login is None:
            memory = os.environ.get(LOGIN_VAR, "").strip().lower() == "memory"
            login = EnvironmentLogin(env=dict(os.environ)) if memory else EnvironmentLogin(saved=saved_variables)
        super().__init__(log, login)
        # a one-shot app (0.20.1): the command line's status and machine commands, answering and ending; a plugin it
        # attaches starts no background work of its own (a cloud's account reads, Dynamic DNS passes)
        self.once = bool(once)
        self._machines = machines  # by name; None: the registry's
        self._assistants = assistants  # by name; None: the registry's
        self._settings_of = settings  # () -> Settings: a test's; else the app's, read with its login
        self._settings_cache: tuple[float, object] | None = None
        self._invalid: set[str] = set()  # the plugins found not valid by the last status: out of the tray
        self._unsaid: set[str] = set()  # the plugins whose Internal API could not be read: said once in the log
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
        # 0.31.0: set while it stops (_refuse_stopping), and the asks under way counted for the stop (_under_way)
        self._stopping = False
        self._asking = 0
        self._asked = threading.Condition(self._lock)  # told as each ask ends

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
        # 0.23.0 (the sphere; the user, 2026-11-11: "treat the plugins like a peripheral interface, and have them on the
        # outer periphery, which is a sphere ... logic and intermediary interfaces (abstractions) are on the middle
        # periphery, which talk to the plugins and the primary application"): each plugin names the library's interface it
        # is built on (`interface`, listed in `interfaces`), and the ones left out of `nodes` are given in `quiet`, so
        # the whole periphery can be drawn
        quiet, interfaces = [], {}
        for name, p in {**self.machines(), **assistants}.items():
            state = self._states.get(name) or ("disabled" if not self.enabled(name) else "unknown")
            attached = self.plugin(name) is p
            face = interface_of(p)
            interfaces[face["id"]] = face
            node = {"id": name, "role": "plugin", "title": p.title, "attached": attached, "state": state,
                    "icon": getattr(p, "ICON", "") or ("analysis" if name in assistants else "chip"),
                    "kind": "assistant" if name in assistants else "machine", "interface": face["id"]}
            if state != "active" and not attached and name not in linked:
                hidden.append(name)
                quiet.append(node)
                nodes.pop(name, None)
                continue
            nodes[name] = node
        out["nodes"], out["hidden"] = list(nodes.values()), sorted(hidden)
        out["quiet"], out["interfaces"] = quiet, list(interfaces.values())
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
        tray puts the chip first); none the user hid from the dock. 0.31.0: the machine plugins of the AI section (the
        model servers, then the harnesses: AI_GROUPS' order, the registry's within a group) come after the assistants,
        so the AI plugins' icons sit together."""
        machines, hidden = self.machines(), self.hidden()
        shown = [name for name in self.active() if name in machines and name not in hidden]

        def icon(name: str) -> TrayItem:
            m = machines[name]
            return TrayItem(name, getattr(m, "ICON", "") or "chip", m.title, "plugin", self.NAME)

        out = [icon(name) for name in shown if not group_of(machines[name])]
        off = self.disabled()
        for name, p in self.assistant_plugins().items():
            if name in hidden or name in off:
                continue
            state = self._states.get(name)
            if state is None:  # not asked yet: whether its key and its plan serve
                state = "active" if self.assistant_validity(p)[0] else "invalid"
            if state == "active":
                out.append(TrayItem(name, getattr(p, "ICON", "") or "analysis", p.title, "plugin", self.NAME))
        for group in AI_GROUPS:
            out += [icon(name) for name in shown if group_of(machines[name]) == group]
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
                "hidden": p.name in self.hidden(), "settings": self.settings_of(p), **self.api_card(p, on),
                **self.internal_card(p)}

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

    def overview(self) -> dict:
        """What the page draws at once (0.21.0; the user, 2026-11-11: "when starting platform there is a long pause before
        anything is visible, there needs instead to be a way that all plugins pop in to existance after loading, and that
        perhaps the main icon/page should show loading status"): the app, this machine and every platform plugin by its
        name, title and icon, enabled or not, hidden or not, in the state it was last found in (None: not asked yet). No
        plugin is asked anything here: the page asks each for its status on its own (GET api/machines/NAME, GET
        api/assistants, api/docker, api/instances) and draws it as its answer comes, where the whole status (GET
        api/status) asks them one after another and answers once the slowest has."""
        off, hidden = self.disabled(), self.hidden()
        with self._lock:
            states = dict(self._states)

        def row(name: str, p, kind: str, icon: str) -> dict:
            machine = kind == "machine"  # an assistant's section is its kind, and it names no group under AI (0.31.0)
            return {"name": name, "title": p.title, "about": p.about, "version": p.version,
                    "icon": getattr(p, "ICON", "") or icon, "kind": kind, "section": section_of(p) if machine else kind,
                    "group": group_of(p) if machine else "", "enabled": name not in off, "hidden": name in hidden,
                    "state": "disabled" if name in off else states.get(name)}

        return {"app": self.describe(), "machine": facts(), "disabled": sorted(off),
                "plugins": [*(row(n, m, "machine", "chip") for n, m in self.machines().items()),
                            *(row(n, p, "assistant", "analysis") for n, p in self.assistant_plugins().items())]}

    def _tray_follows(self, name: str, active: bool) -> None:
        """The tray's active plugins kept in step with one plugin's state just read (0.21.0): the page asks each plugin on
        its own now, and the list is otherwise only asked again after ACTIVE_SECONDS (a whole status sets it anew)."""
        order = list(self.machines())
        with self._lock:
            if self._active is None or name not in order:
                return
            names = set(self._active[1])
            (names.add if active else names.discard)(name)
            self._active = (self._active[0], [n for n in order if n in names])

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
        self._tray_follows(m.name, state == "active")
        self._settle(m, state == "active")
        with self._lock:
            setup = self._setups.get(m.name)
        return {"name": m.name, "title": m.title, "about": m.about, "version": m.version, "status": status,
                "icon": getattr(m, "ICON", "") or "chip", "section": section_of(m),
                "group": group_of(m),  # 0.31.0: its group under AI ("inference", "harness"), "" in every other section
                "enabled": on, "valid": valid, "why": why, "state": state,
                "hidden": m.name in self.hidden(), "steps": list(getattr(m, "STEPS", ()) or ()), "asks": self.asks(m) if state == "active" else [],
                "tabs": tabs_of(m), "hooks": self.hooks(m), "setup": setup.describe(last=200) if setup else None,
                "terminal": {"open": self.terminal_of(m.name) is not None}, "settings": self.settings_of(m),
                **self.api_card(m, on), **self.internal_card(m, status if on else None)}

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

    # -- what a plugin shares with the platform, and what the platform shares itself (0.32.0; liminal-libs 1.63.0's
    # internal.py; the user, 2026-11-16: "the internal api is for interfaces the plugin shares with the rest of the
    # app"; 2026-11-17: "describe the internal API like structure that the app code can work with", "all plugins are
    # middleware") -----------------------------------------------------------------------------------------------------
    def internal_card(self, p, status=None) -> dict:
        """What a plugin shares with the platform, for its Internal API tab: {"internal": ...}, made from the plugin
        object itself by the library (internal.internal_of, through plugin_internal: its base and the standard interface
        it implements, its own hooks, who uses each and how it is called, its tabs, its settings, what it asks of other
        plugins), asking it nothing, so a disabled plugin has it too. That part is kept for the platform's life; the
        status gets a copy of it with `pageAsks`, the hooks its page asks as `status` (the status just read from it, or
        None) names them (page_asks). {} with a library before internal.py, whose frame has no plugin_internal: the
        page then says the platform was started before it could say it. When the library is there and cannot read
        this plugin (it raises, or makes something other than a plugin's Internal API of it): {"internal": None,
        "internalError": words}, which only a platform that has the library sends, so its tab says that it could not
        be read, not to restart the platform; why is in the platform's log, once, and never in the status."""
        if internal_mod is None or not callable(getattr(App, "plugin_internal", None)):
            return {}
        try:
            shared = self.plugin_internal(p)
            if not isinstance(shared, dict):
                raise TypeError(f"the library made a {type(shared).__name__} of it, not its Internal API")
        except Exception as e:  # noqa: BLE001 - its Internal API tab says it could not be read; why, logged once
            with self._lock:
                said = p.name in self._unsaid
                self._unsaid.add(p.name)
            if not said:
                self.log(f"platform: what {p.name} shares could not be read: {type(e).__name__}: {e}")
            title = str(getattr(p, "title", "") or p.name)
            return {"internal": None,
                    "internalError": f"What {title} shares with the platform could not be read: the platform's log "
                                     "says why."}
        return {"internal": {**shared, "pageAsks": page_asks(status)}}  # a copy: the part kept is never changed

    def plugin_internal(self, plugin, tabs=None) -> dict:
        """What a plugin shares with the platform (the frame's plugin_internal: kept for the app's life), with its tabs
        as the platform keeps them (tabs_of) when none are given."""
        return super().plugin_internal(plugin, tabs=tabs_of(plugin) if tabs is None else tabs)

    @staticmethod
    def _machine_kind(p) -> bool:
        return getattr(p, "KIND", "") == "machine"

    def askable(self, p) -> set[str]:
        """The hooks the platform asks a plugin by name, whoever wants them (its page, a client, another plugin): a
        machine plugin's `asks`, what POST /api/machines/{name}/ask and PlatformApp.ask take while it is enabled; none
        of an AI assistant's (ask takes machine plugins only)."""
        return set(self.asks(p)) if self._machine_kind(p) else set()

    def known_plugins(self) -> list:
        """Every plugin of the platform, attached or not (what a plugin asks of another, and who asks a plugin, are
        said from them): the machine plugins, then the AI assistants."""
        return [*self.machines().values(), *self.assistant_plugins().values()]

    def call_words(self, p) -> dict:
        """How the platform is asked one of a plugin's hooks, in words, for its Internal API's "How it is called": by
        another plugin (its app's ask, the arguments in one list), by a client over HTTP, as a job; then the terms
        (ASK_TERMS). Over HTTP as the frame takes a write: from this machine (the platform listens on 127.0.0.1 and
        answers only a request addressed to it), with the write header (WRITE_HEADER: 1; without it, 403). An AI
        assistant is asked nothing by name here."""
        if not self._machine_kind(p):
            return {"terms": "the platform asks an AI assistant nothing by name"}
        name, header = p.name, f"with the header {WRITE_HEADER}: 1, from this machine"
        return {"plugins": f"self.app.ask({name!r}, hook, [arguments])",
                "clients": f'POST /api/machines/{name}/ask {{"hook": hook, "args": [arguments]}} {header}',
                "jobs": (f'POST /api/machines/{name}/job {{"action": "hook", "hook": hook, "args": [arguments]}} '
                         f"{header}: one of its JOB_HOOKS, its lines then read from GET "
                         f"/api/machines/{name}/job?since="),
                "terms": ASK_TERMS}

    @property
    def apis(self) -> tuple:
        """What the platform itself associates with, for its own External API (apis.py): imported when first asked,
        so the platform's start loads nothing more for it."""
        from .apis import APIS

        return APIS

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
        settings, the scan and a command, which have routes of their own or none; and the hook of each tab it declares
        (tabs_of), which it answers once it lists it in its HOOKS (Plugin.ask refuses another, in its words)."""
        try:
            hooks = [h for h in m.interface()["hooks"] if h not in NOT_ASKED]
        except Exception:  # noqa: BLE001 - a plugin that cannot say: nothing to ask
            return []
        return hooks + [h for h in tab_hooks(m) if h not in hooks]

    @staticmethod
    def reads_of(m) -> tuple[str, ...]:
        """The hooks of a machine plugin that only read: READS, its tabs' hooks (the page asks them every few seconds
        while a tab is shown) and, with liminal-libs 1.63.0 (internal.reads_of), those it says only read (its
        READ_HOOKS) that it answers itself and are not its jobs: noted as reads in who talks to whom, and not logged,
        and drawn as reads on its Internal API tab. Without that library, or if it cannot say: READS and the tabs'."""
        if internal_mod is not None:
            try:
                said = internal_mod.reads_of(m, READS, tabs_of(m))
                if isinstance(said, tuple) and all(isinstance(h, str) for h in said):
                    return said
            except Exception:  # noqa: BLE001 - a plugin's declaration that cannot be read: the platform's own reads
                pass
        return (*READS, *(h for h in tab_hooks(m) if h not in READS))

    def _refuse_stopping(self) -> None:
        """Nothing new begun once the platform stops, until it starts again (0.31.0): refused (503). With _lock held."""
        if self._stopping:
            raise Refused(HTTPStatus.SERVICE_UNAVAILABLE, STOPPING)

    @contextlib.contextmanager
    def _under_way(self):
        """What a request asks of a plugin while it waits (0.31.0): one of its hooks (ask), a login terminal being
        opened, a command run. Refused (503) once the platform stops; else counted while it is under way, so the stop
        waits for it (STOP_WAIT_S at most) before it tells the plugins: what it starts is there to be stopped."""
        with self._lock:
            self._refuse_stopping()
            self._asking += 1
        try:
            yield
        finally:
            with self._lock:
                self._asking -= 1
                self._asked.notify_all()

    def ask(self, name: str, hook: str, args: list):
        """One of a machine plugin's hooks by name (asks), its answer as JSON (a rule, a startup: described). Its refusal
        (400) or failure (502) is a HookRefused: the plugin's own words, and the argument accepting a refusal that names
        one. Noted in who talks to whom as asked by whoever calls (0.31.0, as the frame's own ask notes it): a plugin
        asking another through the platform is the one asking (a harness asking a model server what it serves:
        Connections draws the harness to the server), anything else the platform. Under way as _under_way says."""
        caller = self.traffic.actor(sys._getframe(1)) or self.NAME
        m = self.machine(name)
        self._refuse_disabled(name)
        if hook not in self.asks(m):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} is not asked {hook!r} here: {', '.join(self.asks(m)) or 'nothing'}")
        reads = self.reads_of(m)
        with self._under_way():
            if hook not in reads:  # its name and how many arguments, never their values: a key put in a form (0.20.1)
                many = f" ({len(args)} argument{'' if len(args) == 1 else 's'})" if args else ""
                self.log(f"platform: {name} asked {hook}{many}")
            try:
                with self.traffic.timed(caller, name, "read" if hook in reads else "ask", hook):
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
            self._refuse_stopping()
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
        line followed on the page as it comes; its answer (or its refusal, in its own words) at the end.

        A refusal before the job's first line that names the argument accepting it (liminal-libs 1.55.0's GeoIP install:
        its licence) is a HookRefused, as an ask's is, so the page offers its second confirmation and asks the job again
        with that argument true; that job is forgotten (the one before it kept). It is waited for JOB_REFUSAL_S at most:
        a hook that prints its first line or ends sooner is not waited for longer."""
        m = self.machine(name)
        self._refuse_disabled(name)
        if hook not in self.asks(m) or hook not in tuple(getattr(m, "JOB_HOOKS", ()) or ()):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} runs no {hook!r} as a job")
        if not isinstance(args, list) or len(args) > 16:
            raise Refused(HTTPStatus.BAD_REQUEST, "args is a list of the hook's arguments")
        with self._lock:
            self._refuse_stopping()
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
        job.output.wait(0, JOB_REFUSAL_S)  # its first line, or its end
        if job.refused is not None:
            job.thread.join(JOB_REFUSAL_S)  # it has ended: a second ask, accepted, does not find it busy
            with self._lock:
                if self._setups.get(name) is job:
                    if current is None:
                        del self._setups[name]
                    else:
                        self._setups[name] = current
            raise job.refused
        return job

    def cancel_job(self, name: str, started_at: float | None = None) -> dict:
        """A plugin's job under way asked to stop (0.31.0; a model's download runs for a long time, and until now a job
        ran to its end whatever the page did): only a hook's job, the hook one the plugin names in its CANCEL_HOOKS
        (liminal-libs 1.62.0's AiPlugin: its install; a model server's download). Nothing is ended from here: the job's
        output is told (Output.cancel), the hook sees it between its steps and ends by itself, saying what it kept. The
        answer is the job as it is now (`cancelling`; `cancelled` once it has ended). `started_at`: the job meant, by
        its `startedAt` as the page was told it (none: the one under way). Refused: no job running (409); the job meant
        has ended and another runs (409: a Cancel from a page not told yet never stops the next job); a setup, a
        packages' update or a hook that runs to its end (400); a liminal-libs before 1.62.0, whose output takes no
        cancel (400); its work ending as it was asked (409: it is said as it ended). The plugin itself is asked
        nothing, so a job of one disabled meanwhile can still be stopped."""
        self.machine(name)
        with self._lock:
            job = self._setups.get(name)
        if job is None or not job.running:
            raise Refused(HTTPStatus.CONFLICT, f"{name} runs no job now")
        if started_at is not None and started_at != job.started:
            raise Refused(HTTPStatus.CONFLICT,
                          f"the job asked to stop has ended: {name} runs another now ({job.action})")
        if not job.hooked or job.action not in cancel_hooks(job.machine):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name}'s {job.action} cannot be cancelled: it runs to its end")
        if not callable(getattr(job.output, "cancel", None)):
            raise Refused(HTTPStatus.BAD_REQUEST, "this liminal-libs cannot cancel a job (1.62.0 can)")
        if not job.cancel():
            raise Refused(HTTPStatus.CONFLICT, f"{name}'s {job.action} has ended: there is nothing left to cancel")
        self.log(f"platform: {name} asked to cancel {job.action}")
        self.traffic.record(self.NAME, name, "change", f"{job.action} asked to stop")
        return job.describe()

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
        """A login terminal into the plugin's system, or the one open already where it was. 0.31.0: under way as
        _under_way says; one made after the stop closed the terminals is closed at once and refused, so none outlives
        the platform."""
        m = self.machine(name)
        self._refuse_disabled(name)
        if "terminal" not in self.hooks(m):
            raise Refused(HTTPStatus.BAD_REQUEST, f"{name} offers no terminal")
        self._close_idle()
        with self._under_way():
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
            title = (made() if callable(made)
                     else f"{getattr(m, 'user', '') or 'you'} in {getattr(m, 'distribution_name', '') or m.title}")
            term = (self._terminal_of or (lambda a, t: Terminal(a, title=t)))(argv, title)
            with self._lock:
                stopping = self._stopping  # the stop began meanwhile: it has closed the terminals it held already
                if not stopping:
                    self._terminals[name] = term
            if stopping:
                term.close()
                raise Refused(HTTPStatus.SERVICE_UNAVAILABLE, STOPPING)
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

    def start(self, *args, **kwargs) -> str:
        """The frame's start (its page served at its port); the asks and jobs a stop refused are taken again."""
        with self._lock:
            self._stopping = False
        return super().start(*args, **kwargs)

    def stop(self) -> None:
        """The terminals closed and the page ended (the frame's stop), then each machine plugin told that the platform
        stops (0.31.0; the user, 2026-11-16: "the plugins manage the services"; a server a plugin started by a click
        stops when the platform stops, unless it starts at boot): its `app_stopping()` when it has one (liminal-libs
        1.62.0's AiPlugin), one plugin after another, enabled or not, attached or not. One that raises is logged and
        the rest are still told; they are told when the frame's stop raises, too. An ordinary end stops twice
        (cli.cmd_serve: serve's own stop, then the command's), so the hook bears a second call. Before they are told,
        nothing new is begun (_refuse_stopping) and what is under way is wound down (_wind_down)."""
        with self._lock:
            self._stopping = True  # nothing new is begun from now on, until it starts again
            terms, self._terminals = list(self._terminals.values()), {}
        for t in terms:
            t.close()
        try:
            super().stop()
        finally:
            try:
                self._wind_down()
            finally:
                self._tell_stopping()

    def _wind_down(self) -> None:
        """What is under way as the platform stops (0.31.0), before each plugin is told: each job that takes a cancel
        asked to stop (an install's or a model's download, whose child would otherwise outlive the platform), then the
        asks under way (_under_way) and those jobs waited for, STOP_WAIT_S at the most in all. What is still under way
        then is logged, and the plugins are told all the same; a second stop finds nothing to wait for. A setup, a
        packages' update and a job that runs to its end are not waited for: they end with the platform's process, as
        before."""
        deadline = time.monotonic() + STOP_WAIT_S
        with self._lock:
            jobs = [(name, job) for name, job in self._setups.items() if job.running]
        asked = []
        for name, job in jobs:
            if not job.cancels:
                continue
            if not job.cancelling:  # one its page asked to stop already is waited for, not asked again
                if not job.cancel():
                    continue  # its work has just ended
                self.log(f"platform: {name}'s {job.action} asked to stop: the platform stops")
                self.traffic.record(self.NAME, name, "change", f"{job.action} asked to stop")
            asked.append((name, job))
        with self._lock:
            while self._asking and deadline - time.monotonic() > 0:
                self._asked.wait(deadline - time.monotonic())
            asking = self._asking
        if asking:
            self.log(f"platform: {asking} ask{'' if asking == 1 else 's'} of its plugins still under way after "
                     f"{STOP_WAIT_S:g} s: the plugins are told that it stops all the same")
        for name, job in asked:
            if job.thread is not threading.current_thread():  # (a job's own hook stopping the platform: not waited for)
                job.thread.join(max(0.0, deadline - time.monotonic()))
            if job.running:
                self.log(f"platform: {name}'s {job.action} has not ended {STOP_WAIT_S:g} s after it was asked to stop")

    def _tell_stopping(self) -> None:
        """Each machine plugin that has an `app_stopping` told that the platform stops, in the registry's order."""
        try:
            machines = self.machines()
        except Exception as e:  # noqa: BLE001 - a registry that cannot say: the platform ends all the same
            self.log(f"platform: its plugins could not be told that it stops: {type(e).__name__}: {e}")
            return
        for name, m in machines.items():
            try:
                stopping = getattr(m, "app_stopping", None)
                if callable(stopping):
                    stopping()
            except Exception as e:  # noqa: BLE001 - the rest are still told
                self.log(f"platform: {name} did not stop cleanly: {type(e).__name__}: {e}")

    def api(self, handler, method: str, path: str, query: dict, body: dict | None):
        body = body or {}
        if method == "GET" and path == "/api/status":
            return 200, self.status()
        if method == "GET" and path == "/api/overview":  # 0.21.0: at once, no plugin asked; then each part on its own
            return 200, self.overview()
        if method == "GET" and path == "/api/assistants":
            return 200, {"assistants": self.assistants()}
        if method == "GET" and path == "/api/docker":
            return 200, docker_mod.Docker(env={}).describe()
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
            if method == "POST" and action == "job/cancel":  # 0.31.0: the job under way asked to stop (its Cancel)
                started = body.get("startedAt")  # the job meant, as the page was told it (none: the one under way)
                if started is not None and (isinstance(started, bool) or not isinstance(started, (int, float))):
                    raise Refused(HTTPStatus.BAD_REQUEST, "startedAt is the job's own, a number as its state says it")
                return 202, self.cancel_job(name, started)
            if method == "POST" and action == "job":
                what = body.get("action")
                if what == "hook":  # one of its hooks as a job (0.19.0)
                    hook, args = body.get("hook"), body.get("args") or []
                    if not isinstance(hook, str):
                        raise Refused(HTTPStatus.BAD_REQUEST, "hook is a hook's name")
                    try:
                        return 202, self.start_hook_job(name, hook, args).describe(since=0)
                    except HookRefused as e:  # refused before it began, naming what accepts it: the plugin's words with it
                        return e.status, e.answer()
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
                what = f"run {program_name(None, command) or 'a command'}"
                with self._under_way():
                    try:
                        with self.traffic.timed(self.NAME, name, "ask", what):
                            return 200, {"output": m.run(*command)}
                    except Exception as e:  # noqa: BLE001 - the plugin's words
                        raise Refused(HTTPStatus.BAD_GATEWAY, f"{type(e).__name__}: {e}") from None
        return super().api(handler, method, path, query, body)
