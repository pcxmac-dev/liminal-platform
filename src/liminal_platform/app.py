"""The platform app: the frame's App with the chip icon; its routes serve the machine's facts, the machine
plugins (their status, a setup run in a thread with its lines kept, a command, disabled or enabled), the Docker
instances and the plugins attached. 0.32.0: each plugin's status also says what the plugin shares with the platform
(its Internal API: `internal`, liminal-libs 1.63.0's internal.py), and the platform says its own two (GET
/api/app/apis, the frame's): its routes (routes.py) and what it calls on its plugins (CALLS), and what it associates
with (apis.py). 0.33.0: a firewall's globe loads its internet infrastructure layers through the platform's ask, as
reads (READS: world_layer). 0.34.0: the AI plugins' fourth group, Protocols; the route a protocol plugin answers an
agent's request on (POST, GET and DELETE /api/machines/{name}/rpc); and who may ask a hook: one only another plugin
asks (PLUGIN_ONLY_HOOKS) is never asked over HTTP, one only its page asks (PAGE_ONLY_HOOKS) never by a plugin.
0.36.0 (Monday list item 30, step 2; the user, 2026-11-24: "inheritance bro", "through the rust interface";
2026-11-25: the instance forms move to the platform's Databases section, the platform the only writer of instance
settings): PlatformApp is built on liminal-libs 1.90.0's platform core (apps/platform.py: Platform), which the charts
and the integrator inherit too. It attaches the database plugins (PLATFORM_NEEDS), it is the one writer of their
instance settings (PLATFORM_WRITER), it answers the Databases section's two routes (GET /api/databases/plugins, POST
/api/databases/instances: liminal_libs.apps.databases) and, once served, serves the section as the liminal-net node
platform-databases (cli.cmd_serve: serve_databases), which the other apps reach for a change.
0.40.0 (Monday list item 19, part two, release 1; the user, 2026-11-18: every plugin has a "needs" requirement, and a
plugin whose needs this machine cannot meet is not shown in the left-most list): each plugin's needs (its NEEDS, judged
by liminal-libs 1.103.0's needs.py against this machine's facts, read by its facts.py without sending anything) come
before its status. One whose required needs are unmet is in the state "unmet": out of the list and the tray, asked
nothing new (409), never attached while unmet, held (not let go) while the internet alone is missing, and let go only
once no job of it runs and nothing it started is in the ledger. GET /api/needs (the frame's route) answers every plugin
with its judgement; POST /api/needs/internet sets the internet switch. The kinds it attaches are PLATFORM_KINDS (the
user's "Rename it")."""
from __future__ import annotations

import contextlib
import itertools
import json
import math
import os
import platform as py_platform
import re
import select
import socket
import sys
import threading
import time
from collections.abc import Callable, Mapping
from http import HTTPStatus
from pathlib import Path

from liminal_libs import docker as docker_mod
from liminal_libs import layout, lifecycle
from liminal_libs import facts as facts_mod  # this machine's facts, read without sending anything (liminal-libs 1.103.0)
from liminal_libs import needs as needs_mod  # what a plugin needs of the machine, and its judgement (1.103.0)
from liminal_libs import proc as proc_mod  # whether a process of the ledger still runs (_busy)
from liminal_libs.apps import App, EnvironmentLogin, Refused, TrayItem, Unauthorized, program_name, saved_variables
from liminal_libs.apps import databases as db_section  # the Databases section's overview and forms (liminal-libs 1.90.0)
from liminal_libs.apps.platform import Platform  # the platform's core, the base the apps inherit (liminal-libs 1.90.0)
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

try:  # who asks a hook, handed over in so many words (liminal-libs 1.66.0's apps/asking.py): the page, or a plugin
    from liminal_libs.apps import asking as asking_mod
except ImportError:  # an older library hands no asker over: the platform's own gates read the two words themselves
    asking_mod = None
PAGE = getattr(asking_mod, "PAGE", "page")  # the asker of a request from the page, and of a job it started
try:  # a preference read and kept through the login, the file the fallback (liminal-libs 1.88.0; Monday list item 21)
    from liminal_libs.apps.authorization import keep as keep_setting, keeps as keeps_settings, recall as recall_setting
except ImportError:  # an older library: plugins.json alone, as before
    keep_setting = keeps_settings = recall_setting = None
PLUGINS_PAIR = "platform-plugins"  # the plugins switched off and hidden, as a preference pair of the user's login store
# 0.40.0: the internet switch (the user's answer 3, 2026-11-25: "A switch at the Plugins tab's head, kept in the user's own
# login store"): its rule held in memory, each judgement reading it from there; kept as this preference pair of the
# signed-in person's own store, and brought back from it once, when a signed-in page first asks GET /api/needs
INTERNET_PAIR = "platform-internet"
INTERNET_RULES = ("system", "there")  # as this system judges it (NCSI, NetworkManager), or taken as there
NEEDS_PATH = "/api/needs"  # the frame's route (liminal-libs 1.103.0), the platform's report (PlatformApp.needs_report)

PORT = 8775
NOT_ASKED = ("setup", "settings", "scan", "run")  # a machine's hooks the page asks through its own routes, or not at all
READS = ("present", "status", "view", "charts", "instances", "wanted", "services", "startups", "processes",
         "serving", "world_layer")  # asks not logged
# (and a plugin's tab hooks: PlatformApp.reads_of). `serving` (0.31.0): what a model server offers the other AI plugins
# (liminal-libs 1.62.0's ModelServer.serving: its instances as it holds them, no network and no process), asked through
# the platform by a harness for its page and by a model server looking for another's hold on a port. `world_layer`
# (0.33.0), beside "wanted", the Firewall base's other read: one internet infrastructure layer's geometry for a
# firewall's globe (liminal-libs 1.65.0's Firewall.world_layer: a file on this machine read back, nothing downloaded),
# asked by its page with the layer's id once a layer's version is shown; noted as a read, never logged, whatever the
# library says of it
DIR_VAR = "LIMINAL_PLATFORM_DIR"  # the platform's own folder: its log, which plugins are disabled
LOGIN_VAR = "LIMINAL_PLATFORM_LOGIN"  # memory: a scratch preview's login, nothing it saves leaving the process
PLUGINS_FILE = "plugins.json"
TERMINAL_IDLE_S = 120.0  # a terminal no page has read for this long is closed
# 0.34.2 (the review of 2026-11-21, item 26): how often the platform looks for such terminals by itself, so one whose
# tab was closed is closed without waiting for another terminal request
TERMINAL_SWEEP_S = 15.0
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
# 0.35.0 (Monday list item 38; the shutdown audit of 2026-11-24: told one after another, its plugins took about 54 s
# and more): its plugins are told together, under one deadline of this long at the most, and the library's grace
# (App.STOP_GRACE_S) more; one still at it then is late, and what was started for it is killed with its trees
PLUGINS_DEADLINE_S = lifecycle.PLUGINS_DEADLINE_S
STOPPING = "the platform is stopping: its plugins are asked nothing new"  # an ask or a job refused meanwhile (503)
# 0.34.0 (the user, 2026-11-18: "now i need an MCP plugin for platform, basically a protocol plugin that mediates MCP
# connections to resources by local AI agents"): POST, GET and DELETE /api/machines/{name}/rpc, the platform's own port
# for an agent's requests, for a plugin whose RPC_HOOK names one of its hooks (liminal-libs 1.66.0's ProtocolPlugin:
# rpc). The hook is handed each request whole: its method, the headers of this list (named in lowercase), its JSON body
# and gone(). Its answer is sent as it is, with the headers of RPC_ANSWER_HEADERS alone
RPC_METHODS = ("POST", "GET", "DELETE")
RPC_HEADERS = ("authorization", "mcp-session-id", "mcp-protocol-version", "mcp-method", "mcp-name", "accept",
               "content-type", "user-agent", "last-event-id")
RPC_PARAM = "mcp-param-"  # and up to RPC_PARAMS of these, passed on unread (MCP 2026-07-28 mirrors a tool's values)
RPC_PARAMS = 16
RPC_HEADER_CHARS = 4096  # characters of one header's value at the most, either way
RPC_ANSWER_HEADERS = ("Mcp-Session-Id", "MCP-Protocol-Version", "WWW-Authenticate", "Allow", "Retry-After")
_PLAIN = re.compile(r"[\t\x20-\x7e]*")  # a header's value the route sends: one line of plain text
# answers that never have a body (RFC 9110 15.3.5, 15.3.6, 15.4.5). The frame sends a 204 with nothing when its body is
# None; it would send "null" with a 205 or a 304, so the route sends neither
RPC_BODILESS = (HTTPStatus.NO_CONTENT, HTTPStatus.RESET_CONTENT, HTTPStatus.NOT_MODIFIED)


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
    """What this machine is: the system, the processor, the memory, the Python, the host name. 0.40.0: the processor's
    architecture (`machine`, in the needs reader's words: x86-64, arm64) and the memory (`memoryMb` usable,
    `memoryInstalledMb` installed) from liminal-libs' one reading of this machine (liminal_libs.facts, which the plugins'
    needs are judged against), when it reads them; else as before."""
    out = {"system": py_platform.system(), "release": py_platform.release(), "version": py_platform.version(),
           "machine": py_platform.machine(), "processor": py_platform.processor(), "cpus": os.cpu_count() or 0,
           "memoryMb": memory_mb(), "python": py_platform.python_version(), "host": py_platform.node()}
    try:
        read = facts_mod.reader().read({"architecture", "memory"})
    except Exception:  # noqa: BLE001 - a reading that fails: the facts as before
        return out
    if isinstance(read.get("architecture"), str) and read["architecture"]:
        out["machine"] = read["architecture"]
    memory = read.get("memory") if isinstance(read.get("memory"), dict) else {}
    usable, installed = memory.get("usable"), memory.get("installed")
    if isinstance(usable, int) and not isinstance(usable, bool) and usable > 0:
        out["memoryMb"] = usable // (1024 * 1024)
    if isinstance(installed, int) and not isinstance(installed, bool) and installed > 0:
        out["memoryInstalledMb"] = installed // (1024 * 1024)
    return out


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


# the list's sections for machine plugins, in its order (0.25.0, 0.26.0); 0.38.0 (Monday list item 34; the user,
# 2026-11-22: "we will classify them as continuous integration"): "ci" after Cloud, Jenkins, GoCD and Buildbot's;
# 0.39.0 (Monday list item 35; the user, 2026-11-22: "another class of plugins for platform, classified source
# control"): "scm" after it, Git, GitHub, GitLab, Subversion and Mercurial's
SECTIONS = ("machine", "virtualization", "os", "cloud", "ci", "scm")
# 0.31.0 (the user, 2026-11-16: "i need 3 plugins for inference serving local models on the platform, :: lama.cpp,
# ollama and vLLM, i also need 3 harness plugins for the platform :: OpenCode, Aider, and Continue"; "they will be
# classified as AI plugins"; "the other plugins are strictly proprietary service plugins"): the list's AI section. The
# AI assistants (a vendor's service each) are its proprietary services; after them come the machine plugins whose
# SECTION is "ai", each in the group it names. SECTIONS stays the four a machine plugin is otherwise drawn under.
# 0.34.0 (2026-11-18: "basically a protocol plugin that mediates MCP connections to resources by local AI agents"): a
# fourth group, after the harnesses: the protocol plugins (liminal-libs 1.66.0's ProtocolPlugin; MCP's first)
AI_SECTION = "ai"
AI_GROUPS = ("inference", "harness", "protocol")
# 0.36.0 (Monday list item 30, step 2; the user, 2026-11-25: the instance forms move to the platform's Databases
# section): the list's Databases section, its plugins the database plugins (liminal-libs 1.90.0's DatabasePlugin: KIND
# "database", SECTION "databases"), held by the library's platform core and drawn beside the four sections and AI
DATABASES_SECTION = "databases"
DATABASE_TERMS = ("the forms of its page, one at a time: test, new, connect, share, port, credentials and forget "
                  "(liminal_libs.apps.databases.ask); a change made only once confirmed on the page (confirm: true), "
                  "a server off this machine only once confirmed a second time (the argument its refusal names as "
                  "accepting it); a password never logged or echoed. The platform is the one writer of instance "
                  "settings: the other apps ask it for a change through its node, platform-databases")  # a machine plugin's groups under AI, in the list's and tray's order


def group_of(plugin) -> str:
    """The group of the AI section a machine plugin is drawn in (0.31.0): its own word, liminal-libs 1.62.0's
    `AiPlugin.GROUP`, when its SECTION is "ai": "inference" for a model server's (llama.cpp, Ollama, vLLM), "harness"
    for a coding harness's (OpenCode, Aider, Continue), and from 0.34.0 "protocol" for a protocol plugin's (MCP's:
    liminal-libs 1.66.0's ProtocolPlugin). "" for every other plugin: one of another section, one naming a group the
    platform does not draw, one from an older library with no GROUP at all."""
    group = getattr(plugin, "GROUP", "")
    ai = getattr(plugin, "SECTION", "") == AI_SECTION
    return group if ai and isinstance(group, str) and group in AI_GROUPS else ""


def section_of(plugin) -> str:
    """The section of the list a machine plugin is drawn under (0.25.0; the user, 2026-11-14: "classify the cloud plugins
    under the 'cloud plugins' section which should be on the far left"; 0.26.0, 2026-11-15: "platform needs a
    virtualization plugins section"; "just like cloud plugins"; "then OS plugins"). The plugin's own word, liminal-libs
    1.51.0's `MachinePlugin.SECTION`: "virtualization" for a hypervisor's or a container engine's (Hyper-V, libvirt, LXD,
    Docker, Kubernetes, Windows containers), "os" for an operating system's (WSL's distributions, the Windows and Linux
    administration and firewalls), "cloud" for a cloud provider's account, and from 0.38.0 "ci" for a Continuous
    Integration server's (Jenkins, GoCD, Buildbot: liminal-libs 1.94.0's ContainedService), and from 0.39.0 "scm" for
    a source control system's (Git, GitHub, GitLab, Subversion, Mercurial). 0.31.0 (2026-11-16: "they will be classified
    as AI plugins"): "ai" for a model server's, a harness's or (0.34.0) a protocol plugin's, which says its group beside
    it (group_of). Anything else ("ai" with no group the platform draws too), or none from an older library or plugin,
    is "machine"."""
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


class _Part:
    """One of the platform's parts (PlatformApp.parts, 0.35.0): told a signal by the frame's terminate before its
    plugins, its work done within the deadline given."""

    def __init__(self, name: str, work: Callable):
        self.name, self._work = name, work

    def signal(self, sig, deadline: float, sender=None) -> dict:  # noqa: ARG002 - the lifecycle's signature
        self._work(sig, deadline)
        return {"name": self.name, "signal": lifecycle.Signal.of(sig).value}


class _Told:
    """A plugin not attached here, told that the platform stops by its `app_stopping` alone (lifecycle.deliver's way
    for an object with no signal of its own): it answers its own app's signal only, and this is not its app."""

    def __init__(self, name: str, stopping: Callable[[], object]):
        self.name, self._stopping = name, stopping

    def app_stopping(self) -> None:
        self._stopping()


def cancel_hooks(plugin) -> tuple[str, ...]:
    """The hooks of a machine plugin whose job can be asked to stop (0.31.0): those it names in its `CANCEL_HOOKS`
    (liminal-libs 1.62.0's AiPlugin: its install; a model server's download of a model). Such a hook looks at the job's
    output between its steps (`log.cancelled`) and ends by itself. None from an older library or plugin, or from a
    declaration that cannot be read."""
    try:
        return tuple(h for h in (getattr(plugin, "CANCEL_HOOKS", ()) or ()) if isinstance(h, str))
    except Exception:  # noqa: BLE001 - a declaration that cannot be read: none of its jobs is cancelled
        return ()


# -- who may ask a hook, and a protocol plugin's route (0.34.0; liminal-libs 1.66.0's apps/asking.py, internal.py's
# PLUGIN_ONLY_HOOKS and PAGE_ONLY_HOOKS, machines/protocol.py's RPC_HOOK) ---------------------------------------------
def rpc_hook(plugin) -> str:
    """The hook a machine plugin's route hands an agent's requests to (0.34.0): the name its RPC_HOOK gives
    (liminal-libs 1.66.0's ProtocolPlugin: rpc). "" for none: a plugin that names none, or names it in anything but a
    hook's name. Whether the plugin answers that hook is the route's to look at."""
    try:
        hook = getattr(plugin, "RPC_HOOK", "")
    except Exception:  # noqa: BLE001 - a word that cannot be read names nothing
        return ""
    return hook if isinstance(hook, str) and hook.isidentifier() else ""


def _words_of(word: str, value) -> tuple[str, ...]:
    """One of the two words as a plugin says it, read here for a library before 1.66.0: a tuple (or a list) of hooks'
    names; a ValueError for anything else, so a gate that asks it refuses."""
    if isinstance(value, (tuple, list)) and all(isinstance(h, str) for h in value):
        return tuple(value)
    raise ValueError(f"{word} must be a tuple of str")


def gated(plugin) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(the hooks a plugin says only another plugin asks: its PLUGIN_ONLY_HOOKS; those it says only its page asks: its
    PAGE_ONLY_HOOKS), 0.34.0. As liminal-libs 1.66.0 reads them (internal.plugin_only and page_only: a base's names stay
    its subclasses'); with an older library, as the plugin's own attributes say them. Each () when it says none. A
    ValueError when either cannot be read, or is not a tuple of words: a gate that asks it refuses."""
    plugin_only = getattr(internal_mod, "plugin_only", None) if internal_mod is not None else None
    page_only = getattr(internal_mod, "page_only", None) if internal_mod is not None else None
    try:
        if callable(plugin_only) and callable(page_only):
            return tuple(plugin_only(plugin)), tuple(page_only(plugin))
        return (_words_of("PLUGIN_ONLY_HOOKS", getattr(plugin, "PLUGIN_ONLY_HOOKS", ())),
                _words_of("PAGE_ONLY_HOOKS", getattr(plugin, "PAGE_ONLY_HOOKS", ())))
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001 - a word that cannot be read is one the gates refuse on
        raise ValueError(f"who may ask its hooks cannot be read ({type(e).__name__}: {e})") from None


def refusal(plugin, hook: str, who) -> str:
    """Why `who` may not ask a plugin's `hook`, in words; "" when it may (0.34.0). `who` is PAGE (its page, or a job its
    page started), another plugin's name, or None (an ask that names no one). liminal-libs 1.66.0's own rule
    (asking.refusal); with an older library the same rule here, on the words as gated() reads them: a hook in neither
    word is never refused; one only other plugins ask is refused to the page, to no one and to its own plugin; one only
    its page asks is refused to anyone else; and when the words cannot be read, every hook of that plugin."""
    if asking_mod is not None:
        return asking_mod.refusal(plugin, hook, who)
    name = str(getattr(plugin, "name", "") or "a plugin")
    try:
        by_plugins, by_page = gated(plugin)
    except ValueError as e:
        return f"{name}: who may ask its hooks cannot be read ({e}), so it is asked nothing"
    said = f"{name}'s {hook}"
    if hook in by_plugins and hook in by_page:
        return f"{said} is said to be asked only by other plugins and only from its page, so no one can ask it."
    if hook in by_page and who != PAGE:
        return f"{said} is asked only from its page, never by another plugin: {who or 'no one'} asked it."
    if hook in by_plugins and who in (None, PAGE, name):
        return f"{said} is asked only by another plugin, never from a page, by a program or by {name} itself."
    return ""


def not_by_name(plugin) -> set[str]:
    """The hooks of a machine plugin that its page and a program never ask by name (0.34.0): the one its RPC_HOOK names
    (the route's alone) and those its PLUGIN_ONLY_HOOKS name (another plugin's alone). None for a plugin that says
    neither; its RPC hook alone when its words cannot be read (every ask of it is refused then)."""
    out = {rpc_hook(plugin)} - {""}
    return out | set(_plugin_only(plugin))


def _plugin_only(plugin) -> tuple[str, ...]:
    """Its PLUGIN_ONLY_HOOKS as gated() reads them; none when they cannot be read (every gate refuses it then)."""
    try:
        return gated(plugin)[0]
    except ValueError:
        return ()


def _page_only(plugin) -> tuple[str, ...]:
    """Its PAGE_ONLY_HOOKS as gated() reads them; none when they cannot be read (every gate refuses it then)."""
    try:
        return gated(plugin)[1]
    except ValueError:
        return ()


def _asker() -> str | None:
    """Who asks now, as the library hands it over (asking.asker): PAGE, a plugin's name, or None. None with a library
    before 1.66.0, which hands no one over."""
    return asking_mod.asker() if asking_mod is not None else None


def _asked_by(who):
    """The asker for a block, in this thread alone (asking.asking): PAGE, a plugin's name, or None for no one; the
    one before put back after it. Nothing with an older library."""
    return asking_mod.asking(who) if asking_mod is not None else contextlib.nullcontext()


def _handed(target):
    """`target` carrying the asker of this moment into the thread that runs it (asking.handed: a job's hand-over, read
    where the job is started, set in its own thread); `target` itself with an older library. The asking person's login
    goes with it too (item 21, liminal-libs 1.88.0: it is each thread's own, so a job's thread would otherwise keep, or
    record a licence accepted in its hook as, the platform's own login, not the person who started it)."""
    handed = asking_mod.handed(target) if asking_mod is not None else target
    try:
        from liminal_libs.apps import as_user, asking_login
    except ImportError:  # a library before 1.88.0: nothing per person to carry
        return handed
    login = asking_login()
    if login is None:
        return handed

    def run(*args, **kwargs):
        with as_user(login):
            return handed(*args, **kwargs)

    return run


def rpc_headers(handler) -> dict[str, str]:
    """A request's headers as the route hands them to its plugin (0.34.0): those RPC_HEADERS names and up to RPC_PARAMS
    whose names begin with RPC_PARAM, named in lowercase; one sent twice is its values joined by ", " (RFC 9110 5.3).
    No other header is handed over. Refused (431) past either bound: a value longer than RPC_HEADER_CHARS, or more
    than RPC_PARAMS mcp-param- headers. Nothing for a request that has no headers (the app asked directly)."""
    raw = getattr(handler, "headers", None)
    try:
        items = list(raw.items()) if raw is not None else []
    except Exception:  # noqa: BLE001 - headers that cannot be read: none handed over
        items = []
    out: dict[str, str] = {}
    for name, value in items:
        key = str(name).strip().lower()
        param = key.startswith(RPC_PARAM) and len(key) > len(RPC_PARAM)
        if key not in RPC_HEADERS and not param:
            continue
        if param and key not in out and sum(k.startswith(RPC_PARAM) for k in out) >= RPC_PARAMS:
            raise Refused(HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE,
                          f"a request here carries {RPC_PARAMS} {RPC_PARAM}* headers at the most")
        text = f"{out[key]}, {value}" if key in out else str(value)
        if len(text) > RPC_HEADER_CHARS:
            raise Refused(HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE,
                          f"a header's value here is {RPC_HEADER_CHARS:,} characters at the most: {key}'s is longer")
        out[key] = text
    return out


def gone_of(handler) -> Callable[[], bool]:
    """gone() for a request (0.34.0): whether its agent has closed the connection it asked on, read without waiting and
    taking nothing off it: a select (poll where the system has it, as select takes no socket numbered past 1023 on
    Linux), then a peek at one byte (MSG_PEEK). A connection that can no longer be looked at is gone; a request with no
    connection (the app asked directly) never is."""
    connection = getattr(handler, "connection", None)

    def gone() -> bool:
        return connection is not None and _closed(connection)

    return gone


def _closed(connection) -> bool:
    """Whether the other end has closed `connection`: it is readable and a peek finds its end (b""), or it cannot be
    looked at (reset; closed here). Readable with a byte waiting, or not readable: it is open."""
    try:
        poll = getattr(select, "poll", None)
        if callable(poll):
            watch = poll()
            watch.register(connection, select.POLLIN | select.POLLPRI)
            ready = bool(watch.poll(0))
        else:
            readable, _, broken = select.select([connection], [], [connection], 0)
            ready = bool(readable or broken)
        return ready and connection.recv(1, socket.MSG_PEEK) == b""
    except (BlockingIOError, InterruptedError, TimeoutError):
        return False
    except (OSError, ValueError):
        return True


def rpc_answer(answer, title: str, hook: str) -> tuple[int, dict | None, dict[str, str]]:
    """What a plugin's RPC hook answered, as the route sends it (0.34.0): its status (200 to 599), its body (a dict, or
    None: a 202 or a 204 then has no body at all, liminal-libs 1.66.0's send_json) and, of its headers, those
    RPC_ANSWER_HEADERS names, in their own spelling, whose value is one line of plain text of RPC_HEADER_CHARS at the
    most; any other is left out. Anything but (status, body[, headers]) is refused (502) in words.

    The agent always gets an answer. A body the frame cannot send as JSON (NaN or Infinity in it, a set, bytes, a
    loop) would leave it none: the frame's send fails after the route returns, and the connection just closes. So that
    body is refused here (502). So is a body on a 204, and a 205 or a 304 (RPC_BODILESS), which never have one."""
    if isinstance(answer, tuple) and len(answer) in (2, 3):
        status, data = answer[0], answer[1]
        headers = answer[2] if len(answer) == 3 else None
        if (isinstance(status, int) and not isinstance(status, bool) and 200 <= status <= 599
                and (data is None or isinstance(data, dict)) and (headers is None or isinstance(headers, Mapping))):
            if status == HTTPStatus.NO_CONTENT and data is not None:
                raise Refused(HTTPStatus.BAD_GATEWAY, f"{title}'s {hook} answered a 204 with a body: a 204 has none")
            if status in RPC_BODILESS and status != HTTPStatus.NO_CONTENT:
                raise Refused(HTTPStatus.BAD_GATEWAY, f"{title}'s {hook} answered a {int(status)}: the route sends no "
                                                      f"{int(status)}, as it cannot send one without a body")
            try:  # as the frame sends it (web.send_json): strict JSON
                json.dumps(data, allow_nan=False)
            except Exception as e:  # noqa: BLE001 - whatever would stop the frame's own send, said by its type alone
                raise Refused(HTTPStatus.BAD_GATEWAY, f"{title}'s {hook} answered a body that is not JSON "
                                                      f"({type(e).__name__}): nothing of it was sent") from None
            spelled = {h.lower(): h for h in RPC_ANSWER_HEADERS}
            out: dict[str, str] = {}
            for name, value in (headers or {}).items():
                known = spelled.get(name.strip().lower()) if isinstance(name, str) else None
                text = str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) else None
                if known and text is not None and len(text) <= RPC_HEADER_CHARS and _PLAIN.fullmatch(text):
                    out[known] = text
            return status, data, out
    raise Refused(HTTPStatus.BAD_GATEWAY, f"{title}'s {hook} answered what the route cannot send: (a status from 200 "
                                          "to 599, a JSON object or nothing, its headers)")


class Setup:
    """A machine plugin's job under way, in a thread: its setup, its packages' update, or one of its hooks (`action`:
    the hook's name; 0.19.0, `call`: the hook asked with the job's output as its `log`); what it prints as it comes
    (`output`, read from an offset by the page's terminal panel), its steps (a hook's answer) when done. 0.31.0 (a
    model's download runs for a long time): a hook's job can be asked to stop when the plugin names that hook in its
    CANCEL_HOOKS (`cancels`, `cancel`); a setup, a packages' update and every other hook run to their end. 0.34.0
    (liminal-libs 1.66.0's apps/asking.py): it is made where it is asked, and the asker of that moment (the page, for
    the page's routes) is read there and set in its own thread, so its hook is asked as it was asked to run: never
    from what the thread happens to inherit."""

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
        self.asker = _asker()  # who asked it to run (0.34.0): PAGE from the page's routes; set in its thread (_handed)
        self.thread = threading.Thread(target=_handed(self._run), name=f"setup-{machine.name}", daemon=True)
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
        "not_for_here": ("why it is not for this machine, in its own words (0.40.0): asked before its status, by the "
                         "overview and by GET /api/needs, one more unmet need of the machine when it gives words; by "
                         "contract it asks nothing"),
        "present": "whether it is there: for the tray, at most once a minute, while it is enabled and its needs are met",
        "status": ("its state: each GET /api/machines/{name}, /api/machines and /api/status, while it is enabled and "
                   "its needs are met (and, not for this machine, while its not_for_here() gives words: its tables of "
                   "elsewhere)"),
        "instances": ("its Docker instances: GET /api/instances and /api/status, while it is enabled and its needs are "
                      "met (liminal_libs.docker.instances)"),
        "interface": "the hooks it answers: with each status and each ask",
        "setup": "POST /api/machines/{name}/setup and /job {action: install}: its steps, as a job",
        "update_packages": "POST /api/machines/{name}/job {action: update}, as a job",
        "check": "GET /api/machines/{name}/check: while its page is shown, and before an install or an update",
        "terminal": "POST /api/machines/{name}/terminal: the command its login terminal runs",
        "terminal_title": "its terminal's title (else its user and distribution_name)",
        "settings_changed": "after POST /api/plugins/{name}/settings kept them",
        "api_facts": "what it learned of its APIs: with each status while it is enabled and its needs are met",
        "attach": ("while it is enabled, its needs met and valid: the platform and a login that notes what it reads "
                   "and keeps"),
        "detach": ("when it is disabled, or not valid or its needs unmet once no job of it runs and nothing it started "
                   "is in the ledger (never for the internet alone: it is held)"),
        "app_stopping": ("when the platform stops, once the asks and the jobs that take a cancel under way are "
                         "waited for (STOP_WAIT_S at the most): each machine plugin that has it, enabled or "
                         "not, not attached here; all told together (0.35.0), PLUGINS_DEADLINE_S at the most"),
        "signal": ("when the platform stops (0.35.0), each machine plugin attached here: TERM, its app_stopping "
                   "then what was started for it; all told together (liminal_libs.lifecycle.deliver_all)"),
        "ask": ("any other hook by name: POST /api/machines/{name}/ask, and /job {action: hook} for one of its "
                "JOB_HOOKS"),
        "rpc": ("POST, GET and DELETE /api/machines/{name}/rpc (0.34.0): the hook its RPC_HOOK names, through its "
                "ask, handed an agent's request whole (method, the allow-listed headers, body, gone); never by name")},
    "assistant": {
        "not_for_here": ("why it is not for this machine, in its own words (0.40.0): asked before its status; by "
                         "contract it asks nothing"),
        "served": "whether its key and its plan serve: with each status, while its needs are met",
        "keys_set": "whether its key is set, when it does not serve",
        "free_note": "why its plan has no API access",
        "settings_changed": "after POST /api/plugins/{name}/settings kept them",
        "interface": "the hooks it answers: in GET /api/status's plugins while it is attached (the frame's plugins())",
        "api_facts": "what it learned of its APIs: with each status while it is enabled and its needs are met",
        "attach": "while it is enabled, its needs met and valid",
        "detach": "when it is disabled, not valid, or its needs unmet (never for the internet alone: it is held)"},
    # 0.36.0: a database plugin, through the library's Databases section (liminal_libs.apps.databases)
    "database": {
        "status": "its instances as its page draws them: GET /api/databases/plugins (databases.overview)",
        "interface": "the hooks it answers: with each GET /api/databases/plugins",
        "test": "POST /api/databases/instances {action: test}: an instance opened for reading and asked what it is",
        "new_database": "POST /api/databases/instances {action: new, confirm: true}: a database made",
        "connect_to": "POST /api/databases/instances {action: connect, confirm: true}: one that exists, kept",
        "share": "POST /api/databases/instances {action: share, confirm: true}: who else may attach to it",
        "set_port": "POST /api/databases/instances {action: port, confirm: true}: its port",
        "set_credentials": "POST /api/databases/instances {action: credentials, confirm: true}: its sign-in",
        "forget": "POST /api/databases/instances {action: forget, confirm: true}: forgotten, what it holds kept",
        "api_facts": "what it learned of its APIs: with each GET /api/databases/plugins",
        "attach": ("as the platform attaches its plugins, or at the section's first ask: the platform's login, "
                   "through which the instances you add are kept")}}
ATTRIBUTES = {  # read or looked up, never called (KIND: which of CALLS' kinds it is; chosen: whether it has installs to
    # choose from, looked up before an update, which it then checks itself; 0.34.0: RPC_HOOK, the hook its route's
    # requests are handed to, and the two words of who may ask a hook)
    "machine": ("KIND", "name", "title", "about", "version", "SYSTEM", "ICON", "SECTION", "STEPS", "TABS", "JOB_HOOKS",
                "keys", "apis", "api", "app", "login", "user", "distribution_name", "chosen", "GROUP",
                "CANCEL_HOOKS", "RPC_HOOK", "PLUGIN_ONLY_HOOKS", "PAGE_ONLY_HOOKS", "NEEDS"),
    "assistant": ("KIND", "name", "title", "about", "version", "SYSTEM", "ICON", "vendor", "default_model", "key_names",
                  "keys", "apis", "api", "app", "NEEDS"),
    "database": ("KIND", "name", "title", "about", "version", "SYSTEM", "ICON", "SECTION", "ENGINE", "SERVER", "TABS",
                 "JOB_HOOKS", "apis", "api", "app", "login", "NEEDS")}
# the terms of the platform's ask (PlatformApp.ask; POST /api/machines/{name}/ask), as a plugin's Internal API says them
ASK_TERMS = (f"the hooks a machine plugin answers (its tabs' too), while it is enabled, none of "
             f"{', '.join(NOT_ASKED[:-1])} and {NOT_ASKED[-1]} (routes of their own, or none); the arguments by "
             "position, in one list; its answer as JSON; a refusal is a HookRefused: 400 with the plugin's own words "
             "and the argument that accepts it, a failure 502; none begun while the platform stops (503). From 0.34.0 "
             "a hook its PLUGIN_ONLY_HOOKS names is asked by another plugin alone (403 over HTTP), one its "
             "PAGE_ONLY_HOOKS names from its page alone (403 to a plugin; 401 over HTTP without the login's word that "
             "you are there), and the hook its RPC_HOOK names through its route alone")
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


class PlatformApp(Platform):
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

    # 0.36.0 (Monday list item 30, step 2): the library's platform core (liminal_libs.apps.platform.Platform) under it.
    # It attaches the database plugins (the machine plugins and the AI assistants are its own, as before: attach_plugins),
    # and it is the running platform, the one writer of instance settings: a part of the platform included in another
    # app's process reads them and asks this one for a change, through its node (serve_databases). 0.40.0: the kinds it
    # attaches are PLATFORM_KINDS (liminal-libs 1.103.0; the user's "Rename it": "needs" is what a plugin needs of the
    # machine), the old PLATFORM_NEEDS left to the library, which reads it one release more for the apps that set it
    PLATFORM_KINDS = ("database",)
    PLATFORM_WRITER = True

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
        "keeps for its panel is the hook's lines, its answer and its state, nothing it was asked with.",
        "POST, GET and DELETE /api/machines/{name}/rpc (0.34.0) hand an agent's request whole to the hook its "
        "RPC_HOOK names: its method, the headers of the route's allow-list (named in lowercase), its JSON body and "
        "gone(), whether the agent has closed its connection. Its answer (status, body or None, headers) is sent as it "
        "is, with the allow-listed headers alone.",
        "That route is not counted as under way: a call it holds for your answer must not hold up the stop, and the "
        "plugin's app_stopping ends it. Nothing is logged per request: the plugin notes each one itself.",
        "A hook its PLUGIN_ONLY_HOOKS names is asked only by another plugin through the platform (self.app.ask), "
        "which names that plugin as its asker (liminal-libs 1.66.0's apps/asking.py): over HTTP it is refused (403), "
        "and its page is never offered it.",
        "A hook its PAGE_ONLY_HOOKS names is asked only from its page: a plugin's ask of it is refused (403); over "
        "HTTP it is asked when the login says you are there (App.present: today, a browser signed in to the "
        "platform), else refused (401), or when the platform holds no login. The page is its asker, in a job too.",
        "The Databases section (0.36.0) is liminal-libs' platform core: its plugins attached with the platform's login, "
        "their instances' forms answered by GET /api/databases/plugins and POST /api/databases/instances, a change "
        "only once confirmed. The platform is the one writer of instance settings, and serves the section as the "
        "node platform-databases, which the other apps ask for a change.")

    def __init__(self, log=print, login=None, machines: dict | None = None, state: Path | None = None,
                 assistants: dict | None = None, settings=None, terminal=None, once: bool = False, node_factory=None):
        # its login: the user's environment variables, those saved after it started too (a setting entered on a page
        # holds across a restart), until the login app holds them (Login.save keeps one); a scratch preview's
        # (LIMINAL_PLATFORM_LOGIN=memory, 0.11.0): a copy of this process's, what the page saves kept in it alone
        if login is None:
            memory = os.environ.get(LOGIN_VAR, "").strip().lower() == "memory"
            login = EnvironmentLogin(env=dict(os.environ)) if memory else EnvironmentLogin(saved=saved_variables)
        # (0.36.0: node_factory, liminal_net.Node unless a test's stand-in, for the Databases section's node)
        super().__init__(log, login, node_factory=node_factory)
        # a one-shot app (0.20.1): the command line's status and machine commands, answering and ending; a plugin it
        # attaches starts no background work of its own (a cloud's account reads, Dynamic DNS passes)
        self.once = bool(once)
        self._machines = machines  # by name; None: the registry's
        self._assistants = assistants  # by name; None: the registry's
        self._settings_of = settings  # () -> Settings: a test's; else the app's, read with its login
        self._settings_cache: tuple[float, object] | None = None
        self._invalid: set[str] = set()  # the plugins found not valid by the last status: out of the tray
        # 0.40.0: the plugins whose needs this machine does not meet now (out of the tray, asked nothing new), each
        # one's needs as last judged (Connections, the overview), the words of a status that said it is not for this
        # machine (applies: False), and the internet switch's rule, held in memory, with whether it was brought back
        # from a signed-in person's store and whether it is kept there
        self._unmet: set[str] = set()
        self._needs: dict[str, dict] = {}
        self._elsewhere: dict[str, str] = {}
        self._internet = "system"
        self._internet_recalled = False
        self._internet_kept = False
        self._unsaid: set[str] = set()  # the plugins whose Internal API could not be read: said once in the log
        self._terminals: dict[str, Terminal] = {}  # a login terminal per plugin (the page's terminal panel)
        self._terminal_of = terminal  # (argv, title) -> Terminal: a test's
        # 0.34.2: the clock a terminal's `seen` is read against (a test's moves), and the sweep that closes idle ones
        # while the platform is served (_start_sweep), with the event that ends it
        self._clock = time.monotonic
        self._sweeper: threading.Thread | None = None
        self._swept: threading.Event | None = None
        self._settling = threading.Lock()
        self._state = Path(state) if state is not None else None  # the platform's folder; platform_dir() unless given
        self._disabled: set[str] | None = None  # read from the folder's plugins.json when first wanted
        self._hidden: set[str] | None = None  # the plugins hidden from the dock, read with them
        self._attaching = False  # set once attach_plugins ran: an enabled plugin is attached again
        self._setups: dict[str, Setup] = {}
        self._lock = threading.Lock()
        self._active: tuple[float, list[str]] | None = None
        self._states: dict[str, str] = {}  # each plugin's state when last asked: active | disabled | invalid | unmet
        self._whys: dict[str, str] = {}  # why, when last asked (0.37.0: plugin_state)
        # 0.31.0: set while it stops (_refuse_stopping), and the asks under way counted for the stop (_under_way)
        self._stopping = False
        self._asking = 0
        self._asked = threading.Condition(self._lock)  # told as each ask ends

    # -- who talks to whom (apps.traffic; the page's Connections) -------------------------------------------------
    def classify(self, method: str, path: str) -> str:
        """A page's request in its class: a terminal's keys and output and a job's output read are streams, a hook
        asked by name an ask, and (0.34.0) an agent's request on a protocol plugin's route an ask, whatever its method;
        the rest as the frame says (a GET reads, anything else asks for a change)."""
        if "/terminal" in path or (method == "GET" and path.endswith(("/job", "/setup"))):
            return "stream"
        if path.endswith(("/ask", "/rpc")):
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
            if state == "unmet":  # 0.40.0: not for this machine ("machine") or not met now ("moment")
                with self._lock:
                    node["sort"] = str((self._needs.get(name) or {}).get("sort") or "moment")
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

    def _plugins_file(self) -> dict | None:
        """The folder's plugins.json as it is kept ({"disabled": [...], "hidden": [...]}), None when there is none or
        it cannot be read."""
        try:
            saved = json.loads((self.state_dir / PLUGINS_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return saved if isinstance(saved, dict) else None

    def _write_plugins_file(self, value: dict) -> None:
        folder = self.state_dir
        folder.mkdir(parents=True, exist_ok=True)
        part = folder / f"{PLUGINS_FILE}.{os.getpid()}.part"
        part.write_text(json.dumps(value, indent=1), encoding="utf-8")
        os.replace(part, folder / PLUGINS_FILE)

    def _saved(self) -> None:
        """The plugins disabled, and those hidden from the dock, read once (the lock held). 0.34.4 (Monday list item 21;
        the user, 2026-11-19: "preferences, keys, licenses all get stored in the individual's login db"): they are a
        preference of the platform's signed-in user, the pair PLUGINS_PAIR of their login's store, when its login keeps
        them; else, and with an EnvironmentLogin as today, the folder's plugins.json. A store holding none yet is given
        the file's, once (liminal-libs' recall), and the file is left as it was. They are the platform's login's, not a
        browser's: a plugin switched off is off for the whole process."""
        if self._disabled is None:
            if recall_setting is not None:
                saved = recall_setting(self.login_for(self.NAME), PLUGINS_PAIR, self._plugins_file,
                                       label="the platform's plugins switched off and hidden")
            else:
                saved = self._plugins_file()
            saved = saved if isinstance(saved, dict) else {}
            try:
                self._disabled = {n for n in saved.get("disabled", []) if isinstance(n, str)}
                self._hidden = {n for n in saved.get("hidden", []) if isinstance(n, str)}
            except TypeError:  # a list that is not one
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

    def _keep(self, change: Callable[[set[str], set[str]], None]) -> None:
        """plugins.json written whole (a part file renamed): the plugins disabled, and those hidden from the dock, as
        `change` leaves them (it changes the two sets in place). Until 0.34.3 the sets were read, changed and written
        outside the lock, through one shared plugins.json.part (the review of 2026-11-21, item 26): two switches at
        once could lose one's change, and the second rename found the part file gone. The whole read-change-write is
        now one step under the lock, through a part file of this process's own. 0.34.4: kept in the login's store when
        it keeps them (`_saved`), the file otherwise, or when the store refuses or cannot be reached."""
        with self._lock:
            self._saved()
            disabled, hidden = set(self._disabled), set(self._hidden or ())
            change(disabled, hidden)
            value = {"disabled": sorted(disabled), "hidden": sorted(hidden)}
            if keep_setting is not None:
                keep_setting(self.login_for(self.NAME), PLUGINS_PAIR, value, self._write_plugins_file,
                             label="the platform's plugins switched off and hidden")
            else:
                self._write_plugins_file(value)
            self._disabled, self._hidden = disabled, hidden

    def enabled(self, name: str) -> bool:
        return name not in self.disabled()

    def set_hidden(self, name: str, on: bool) -> dict:
        """A plugin hidden from the dock on the right, or shown there again (the user, 2026-11-08: "all plugins need a
        hide switch next to enable for the dock on the right"). Hidden, its icon leaves the tray while it stays as it
        was: enabled or not, attached, asked; its row in the list, its page and Connections keep it. Kept across
        restarts. The answer: hidden or not, and the tray as it is now."""
        self.platform_plugin(name)
        self._keep(lambda disabled, hidden: (hidden.add if on else hidden.discard)(name))
        self.log(f"platform: {name} {'hidden' if on else 'visible'}")
        return {"name": name, "hidden": on, "tray": self.tray().as_dict()}

    def set_enabled(self, name: str, on: bool) -> dict:
        """A machine plugin enabled or disabled (the tray's right click, the switch on its page). Disabled, the
        platform asks it nothing, its icon leaves the tray and it is detached (a plugin that samples stops);
        enabled, it is attached again when the platform attaches its plugins. Kept across restarts."""
        m = self.platform_plugin(name)
        self._keep(lambda disabled, hidden: (disabled.discard if on else disabled.add)(name))
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

    def _settle(self, p, active: bool, held: bool = False) -> None:
        """A plugin attached while it is active (enabled and valid) and detached otherwise, once the platform
        attaches its plugins (the user: "if a plugin is not in a valid state it has to be disabled"). 0.40.0 (the needs
        plan's S13, M15): one not active is let go only once no job of it runs and nothing it started is in this
        process's ledger (lifecycle.mine), at the first status read after both have ended, since a detach ends what it
        started; and never while `held` (its needs unmet by the internet alone: the user's answer 19, "Held"). The
        switch (set_enabled) and the platform's stop let go at once, as before."""
        if not self._attaching:
            return
        with self._settling:
            attached = self.plugin(p.name) is not None
            if active and not attached and getattr(p, "app", None) is None:
                self.attach(p)
            elif not active and attached and not held and not self._busy(p.name):
                self.detach(p.name)

    def _busy(self, name: str) -> bool:
        """Whether a job of the plugin runs, or a process it started is in this process's ledger and still runs (0.40.0).
        A row stays in the ledger after its process ended by itself (only end_owned takes rows out), so a row counts only
        while its process is alive and started when it started (never a reused id); else a plugin that ever started
        anything would never be let go."""
        with self._lock:
            setup = self._setups.get(name)
        if setup is not None and setup.running:
            return True
        try:
            return any(r.started is not None and proc_mod.pid_alive(r.pid) and proc_mod.started(r.pid) == r.started
                       for r in lifecycle.mine(name))
        except Exception:  # noqa: BLE001 - a ledger that cannot say holds nothing back
            return False

    def platform_plugin(self, name: str):
        """A machine plugin or an AI assistant of the platform, by name."""
        p = self.machines().get(name) or self.assistant_plugins().get(name)
        if p is None:
            raise Refused(HTTPStatus.NOT_FOUND, f"no plugin named {name!r} here")
        return p

    def _refuse_disabled(self, name: str) -> None:
        if not self.enabled(name):
            raise Refused(HTTPStatus.CONFLICT, f"{name} is disabled: enable it first")

    # -- what its plugins need of this machine (0.40.0; Monday list item 19, part two, release 1: liminal-libs 1.103.0's
    # needs.py and facts.py; the user, 2026-11-18: "a plugin whose needs this machine cannot meet is not shown in the
    # left-most list"; the Connections view's Plugins tab, "red for those that could but do not meet current
    # conditions, shaded for those that never can here") ---------------------------------------------------------
    def internet_rule(self) -> str:
        """How the internet is judged: "system", as this system judges it (Windows' NCSI, NetworkManager), or
        "there", the Plugins tab's switch. Held in memory and read from there at each judgement, never from a store."""
        with self._lock:
            return self._internet

    def offline(self) -> str | None:
        """The setting that makes the platform send nothing, from its own settings (the user's answer 5:
        LIMINAL_READONLY, LIMINAL_OFFLINE): every internet need unmet then, whatever the switch; None when neither is
        set or the settings cannot be read."""
        try:
            settings = self.settings_now()
        except Exception:  # noqa: BLE001 - settings that cannot be read set nothing
            return None
        if getattr(settings, "read_only", False) is True:
            return "LIMINAL_READONLY"
        return "LIMINAL_OFFLINE" if getattr(settings, "offline", False) is True else None

    def plugin_states(self) -> dict[str, str]:
        """Each plugin's state for a `plugin` need: "attached" while it is attached here, "cannot" for one not for this
        machine, else its state when last asked."""
        with self._lock:
            states, judged = dict(self._states), dict(self._needs)
        out = {}
        for p in self.known_plugins():
            name = str(getattr(p, "name", "") or "")
            last = judged.get(name) or {}
            if last.get("met") is False and last.get("sort") == "machine":
                out[name] = "cannot"
            elif self.plugin(name) is p:
                out[name] = "attached"
            else:
                out[name] = states.get(name, "")
        return out

    def _known(self, name: str):
        p = next((k for k in self.known_plugins() if getattr(k, "name", "") == name), None)
        if p is None:
            raise LookupError(f"no plugin {name!r} is known to the platform")
        return p

    def _judged(self, p, read: dict | None = None, fresh: bool = False, own: str | None = None) -> dict:
        """A plugin's needs judged (needs.judge) against the facts in hand (`read`, else this machine's kept facts of
        what its rows name), asking the plugin nothing but its not_for_here(), which by contract asks nothing; with the
        words of a status that said it is not for this machine (applies: False) as one more need of the machine. The
        settings are read for an internet row alone (offline), the plugins' states for a plugin row alone. Kept for
        Connections and the overview."""
        rows = needs_mod.declared(p)
        kinds = {str(r.get("attribute", "")).rpartition(":")[2] for r in rows}
        if read is None:
            attributes, names = facts_mod.wanted(rows)
            read = self.machine_facts(attributes, fresh=fresh, names=names)
        if own is None:
            with self._lock:
                elsewhere = self._elsewhere.get(p.name, "")
            own = "; ".join(w for w in (needs_mod.own_words(p), elsewhere) if w)
        answer = needs_mod.judge(rows, read, own=own, plugins=self.plugin_states() if "plugin" in kinds else None,
                                 internet=self.internet_rule(), offline=self.offline() if "internet" in kinds else None,
                                 declared=needs_mod.says(p))
        with self._lock:
            self._needs[p.name] = answer
        return answer

    def needs_of(self, plugin_or_name, fresh: bool = False) -> dict:
        """A plugin's needs judged against this machine: any plugin of the platform, attached or not (LookupError for
        one it does not have), asked nothing but its not_for_here()."""
        p = self._known(plugin_or_name) if isinstance(plugin_or_name, str) else plugin_or_name
        return self._judged(p, fresh=fresh)

    def _read_for(self, plugins, fresh: bool = False) -> dict:
        """One reading of this machine for every plugin given: what their rows name."""
        attributes, names = facts_mod.wanted([r for p in plugins for r in needs_mod.declared(p)])
        return self.machine_facts(attributes | {"kernel", "architecture"}, fresh=fresh, names=names)

    def _kind_of(self, p) -> tuple[str, str]:
        """A plugin's kind and section as the overview says them."""
        if self._machine_kind(p):
            return "machine", section_of(p)
        if getattr(p, "KIND", "") == "database":
            return "database", DATABASES_SECTION
        return "assistant", "assistant"

    def needs_report(self, fresh: bool = False, only: str | None = None) -> dict:
        """GET /api/needs, the platform's (the frame's route): this machine's facts and every plugin it has, attached
        or not, with its needs judged and its state here (`only`: one, by name; LookupError for one it does not have).
        `held` and `switch` are true: the platform holds its plugins by their needs and takes the internet switch;
        `internet` says the rule, how the system judges it, whether it is kept in the signed-in person's store, and the
        setting that makes it send nothing."""
        plugins = [self._known(only)] if only else self.known_plugins()
        read = self._read_for(plugins, fresh=fresh)
        off = self.disabled()
        with self._lock:
            states, whys = dict(self._states), dict(self._whys)
        out = []
        for p in plugins:
            kind, section = self._kind_of(p)
            answer = self._judged(p, read)
            state = states.get(p.name, "")
            if kind != "database" and p.name in off:
                state = "disabled"
            elif answer.get("met") is False:
                state = "unmet"
            elif state == "unmet":  # met again since it was last asked: its page asks its status at once
                state = ""
            out.append({"name": p.name, "title": str(getattr(p, "title", "") or p.name), "kind": kind,
                        "section": section, "group": group_of(p) if kind == "machine" else "",
                        "icon": getattr(p, "ICON", "") or ("analysis" if kind == "assistant" else "chip"),
                        "state": state, "why": whys.get(p.name, "") if state in ("invalid", "unmet") else "",
                        "needs": answer})
        internet = read.get("internet") if isinstance(read.get("internet"), dict) else {}
        with self._lock:
            rule, kept = self._internet, self._internet_kept
        return {"v": 1, "vocabulary": needs_mod.VOCABULARY, "facts": read,
                "internet": {"rule": rule, "by": str(internet.get("by") or ""), "state": internet.get("state"),
                             "switch": True, "kept": kept, "offline": self.offline()},
                "held": True, "switch": True, "plugins": out}

    def set_internet(self, rule: str, handler=None) -> dict:
        """The internet switch set (POST /api/needs/internet): "system" or "there". Held in memory for the whole
        platform at once, and kept as the preference pair INTERNET_PAIR in the store of the person signed in at
        `handler`'s browser when their login keeps settings (`kept`); with a login that keeps none it holds until the
        platform restarts. No file is written."""
        if rule not in INTERNET_RULES:
            raise Refused(HTTPStatus.BAD_REQUEST, f"rule is one of {', '.join(INTERNET_RULES)}")
        with self._lock:
            self._internet, self._internet_recalled = rule, True
        kept = False
        if keep_setting is not None:
            where = keep_setting(self.user_login(handler), INTERNET_PAIR, rule, lambda value: None,
                                 label="how the platform judges the internet for its plugins' needs")
            kept = where == "your login's store"
        with self._lock:
            self._internet_kept = kept
        self.log(f"platform: the internet {'taken as there' if rule == 'there' else 'as this system judges it'}"
                 f" ({'kept in your login' if kept else 'until the platform restarts'})")
        return {"rule": rule, "kept": kept}

    def _recall_internet(self, handler, method: str, path: str) -> None:
        """The internet switch brought back from the signed-in person's store, once, when their page first asks GET
        /api/needs after a start (a page with nobody signed in brings back nothing: asked again by the next)."""
        if method != "GET" or path != NEEDS_PATH or recall_setting is None or keeps_settings is None:
            return
        with self._lock:
            if self._internet_recalled:
                return
        login = self.user_login(handler)
        if not keeps_settings(login):
            return
        value = recall_setting(login, INTERNET_PAIR, lambda: None)
        with self._lock:
            if self._internet_recalled:  # set meanwhile: the switch just set wins
                return
            self._internet_recalled = True
            if value in INTERNET_RULES:
                self._internet, self._internet_kept = value, True

    def _refuse_unmet(self, p) -> None:
        """Nothing new asked of a plugin whose needs this machine does not meet (0.40.0): 409 in its needs' words. A
        job under way runs to its end; its settings may still be kept."""
        answer = self._judged(p)
        if answer.get("met") is False:
            title = str(getattr(p, "title", "") or p.name)
            if answer.get("sort") == "machine":
                raise Refused(HTTPStatus.CONFLICT, f"{title} is not for this machine: {answer.get('why')}")
            raise Refused(HTTPStatus.CONFLICT, f"{title}'s needs are not met now: {answer.get('why')}. It is asked "
                                               "again once they are")

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
        off = self.disabled() | set(self._invalid) | set(self._unmet)
        for name, m in self.machines().items():
            if name in off or self._judged(m).get("met") is False:  # 0.40.0: its needs first, asked nothing while unmet
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
            if state is None:  # not asked yet: its needs first (0.40.0), then whether its key and its plan serve
                state = ("unmet" if self._judged(p).get("met") is False
                         else "active" if self.assistant_validity(p)[0] else "invalid")
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
        answer = self._judged(p)  # 0.40.0: its needs first, from the facts in hand; asked nothing while unmet
        self.traffic.own(p, p.name)
        if on and answer.get("met") is False:
            valid, why = False, str(answer.get("why") or "its needs are not met here")
        elif on:
            with self.traffic.timed(self.NAME, p.name, "read", "valid? (its key, its plan)"):
                valid, why = self.assistant_validity(p)
        else:
            valid, why = None, ""
        state = needs_mod.state_of(on, answer, valid)
        with self._lock:
            self._states[p.name] = state
            (self._unmet.add if state == "unmet" else self._unmet.discard)(p.name)
            self._whys[p.name] = why if state in ("invalid", "unmet") else ""
        self._settle(p, state == "active", held=state == "unmet" and bool(answer.get("held")))
        return {"name": p.name, "title": p.title, "about": p.about, "version": p.version, "vendor": str(getattr(p, "vendor", "") or ""),
                "icon": getattr(p, "ICON", "") or "analysis",  # its maker's mark (0.10.1), else the chart
                "model": str(getattr(p, "default_model", "") or ""), "enabled": on, "valid": valid, "why": why, "state": state,
                "hidden": p.name in self.hidden(), "settings": self.settings_of(p), "needs": answer,
                **self.api_card(p, on and state != "unmet"), **self.internal_card(p)}

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
        here but those disabled and those another app holds; returns the names attached. 0.36.0: with the registry's,
        the database plugins too (Platform.attach_kinds, 0.40.0: the kinds it takes), which no switch disables: the
        other apps open their databases through them. 0.40.0: none whose required needs this machine does not meet
        (item 38: a plugin whose needs are unmet is never started). The Windows features the plugins' rows name are
        read first, in a thread of the reader's (the slow read, about 0.7 s): a plugin whose rows name one is attached
        once they are read, or after FEATURES_WAIT_S, its feature then unknown; the others meanwhile."""
        self._attaching = True
        registry = plugins is None
        if plugins is None:
            from liminal_libs.sources.registry import assistants, machines

            plugins = [*assistants().values(), *machines().values()]
        off, out = self.disabled(), []
        mine = [p for p in plugins
                if p.SYSTEM == "platform" and p.name not in off and (p.app is None or p.app is self)]
        rows = {p.name: needs_mod.declared(p) for p in mine}
        features = facts_mod.wanted([r for rs in rows.values() for r in rs])[1].get("windows.feature") or []
        reader = facts_mod.reader()
        if features:
            reader.begin_features(features)
        waits = [p for p in mine if features and any(str(r.get("attribute", "")).rpartition(":")[2] == "windows.feature"
                                                      for r in rows[p.name])]

        def take(p) -> None:
            if self._judged(p).get("met") is not False:
                self.attach(p)
                out.append(p.name)

        for p in mine:
            if p not in waits:
                take(p)
        if waits:  # once the features are read, or after FEATURES_WAIT_S (then unknown: never hidden for it)
            reader.features_ready(facts_mod.FEATURES_WAIT_S)
            for p in waits:
                take(p)
        if registry:
            out += [name for name in self.attach_kinds() if name not in out]
        return out

    def instances(self) -> list[dict]:
        off = self.disabled()
        return [i.describe() for i in docker_mod.instances(machines=[
            m for n, m in self.machines().items() if n not in off and self._judged(m).get("met") is not False])]

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
        # 0.40.0: each one's needs, judged from the facts in hand and its not_for_here() (it asks nothing): one not met
        # leaves the list at once, before its status comes (the needs plan's M20)
        read = self._read_for([*self.machines().values(), *self.assistant_plugins().values()])

        def row(name: str, p, kind: str, icon: str) -> dict:
            machine = kind == "machine"  # an assistant's section is its kind, and it names no group under AI (0.31.0)
            answer = self._judged(p, read)
            state = "disabled" if name in off else "unmet" if answer.get("met") is False else states.get(name)
            return {"name": name, "title": p.title, "about": p.about, "version": p.version,
                    "icon": getattr(p, "ICON", "") or icon, "kind": kind, "section": section_of(p) if machine else kind,
                    "group": group_of(p) if machine else "", "enabled": name not in off, "hidden": name in hidden,
                    "state": state,
                    "needs": answer}

        return {"app": self.describe(), "machine": facts(), "disabled": sorted(off),
                "plugins": [*(row(n, m, "machine", "chip") for n, m in self.machines().items()),
                            *(row(n, p, "assistant", "analysis") for n, p in self.assistant_plugins().items())]}

    def databases_overview(self) -> dict:
        """The Databases section as its page draws it (0.36.0): the library's overview (GET /api/databases/plugins:
        every database plugin with its instances, `writer` true here), each plugin's row with its kind and section, the
        plugin API it is written for, the hooks it answers and what it shares with the platform (its Internal API tab,
        as every plugin's: internal_card); its External API is the library's (apis, apiFacts)."""
        out = super().databases_overview()
        held = self.database_plugins()
        for row in out.get("plugins") or ():
            row.update({"kind": "database", "section": DATABASES_SECTION, "pluginApi": str(row.get("api") or "")})
            row.setdefault("icon", "database")
            p = held.get(row.get("name"))
            if p is not None and "error" not in row:
                row["hooks"] = self.hooks(p)
                row.update(self.internal_card(p, row))
        return out

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

    def _status_of(self, m) -> dict:
        """A machine plugin's own status, the platform's login lent, attached or not (its settings read through it)."""
        self.traffic.own(m, m.name)
        if getattr(m, "login", None) is None:
            m.login = self.login_for(m.name)
        try:
            with self.traffic.timed(self.NAME, m.name, "read", "status"):
                status = m.status()
        except Exception as e:  # noqa: BLE001 - a plugin's trouble is shown, not raised
            status = {"present": False, "problem": f"{type(e).__name__}: {e}"}
        return status if isinstance(status, dict) else {"present": False, "problem": "its status is not a mapping"}

    def machine_status(self, m) -> dict:
        """A machine plugin as its page draws it. 0.40.0: its needs judged first, from the facts in hand. Not for this
        machine: its status asked only when its not_for_here() gives words (the Admin and Firewall bases' tables of
        elsewhere) or when its own status said so before (asked again, so it stays unmet and can come back), else nothing
        asked; not met now: nothing asked. Met or unknown: its status as before, an `applies:
        False` in it one more need of the machine. Its state is needs.state_of's (disabled, unmet, invalid, active);
        unmet, it is `valid` False with its needs' why, and of the machine `status.applies` False, so a page from before
        draws it as it did."""
        on = self.enabled(m.name)
        answer = self._judged(m)
        unmet = answer.get("met") is False
        with self._lock:
            held_words = self._elsewhere.get(m.name, "")
        asked = False  # whether its own status was asked: only then can it change what its status said before
        if not on:  # asked nothing
            status = {"present": None, "summary": "disabled: the platform asks it nothing"}
        elif unmet and answer.get("sort") == "machine" and not (needs_mod.own_words(m) or held_words):
            status = {"present": None, "summary": f"not for this machine: {answer.get('why')}"}
        elif unmet and answer.get("sort") == "machine":  # its own words, or its status said so before: asked again
            status, asked = self._status_of(m), True
        elif unmet:
            status = {"present": None, "summary": f"not met now: {answer.get('why')}"}
        else:
            status, asked = self._status_of(m), True
        elsewhere = held_words
        if asked:
            elsewhere = ""
            if status.get("applies") is False and not needs_mod.own_words(m):
                elsewhere = str(status.get("why") or status.get("problem") or status.get("summary") or "not for this machine")
        with self._lock:
            changed = self._elsewhere.get(m.name, "") != elsewhere
            (self._elsewhere.__setitem__(m.name, elsewhere) if elsewhere else self._elsewhere.pop(m.name, None))
        if changed:
            answer = self._judged(m)
            unmet = answer.get("met") is False
        valid, why = None, ""
        if on and unmet:
            valid, why = False, str(answer.get("why") or "its needs are not met here")
        elif on:  # its own word when it says (liminal-libs 1.24.0), else present without a problem
            valid = bool(status["valid"]) if "valid" in status else bool(status.get("present")) and not status.get("problem")
            why = "" if valid else str(status.get("why") or status.get("problem") or status.get("summary") or "not present")
        state = needs_mod.state_of(on, answer, valid)
        if state == "unmet" and answer.get("sort") == "machine":
            status = {**status, "applies": False}
        with self._lock:
            (self._invalid.add if state == "invalid" else self._invalid.discard)(m.name)
            (self._unmet.add if state == "unmet" else self._unmet.discard)(m.name)
            self._states[m.name] = state
            self._whys[m.name] = (why if state in ("invalid", "unmet")
                                  else ("turned off on its page or in the tray" if not on else ""))
        self._tray_follows(m.name, state == "active")
        self._settle(m, state == "active", held=state == "unmet" and bool(answer.get("held")))
        with self._lock:
            setup = self._setups.get(m.name)
        return {"name": m.name, "title": m.title, "about": m.about, "version": m.version, "status": status,
                "icon": getattr(m, "ICON", "") or "chip", "section": section_of(m),
                "group": group_of(m),  # 0.31.0: its group under AI ("inference", "harness"), "" in every other section
                "enabled": on, "valid": valid, "why": why, "state": state,
                "hidden": m.name in self.hidden(), "steps": list(getattr(m, "STEPS", ()) or ()), "asks": self.asks(m) if state == "active" else [],
                "tabs": tabs_of(m), "hooks": self.hooks(m), "setup": setup.describe(last=200) if setup else None,
                "terminal": {"open": self.terminal_of(m.name) is not None}, "settings": self.settings_of(m),
                "needs": answer, **self.api_card(m, on and state != "unmet"),
                **self.internal_card(m, status if on and state != "unmet" else None)}

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

    def plugin_state(self, name: str) -> dict:
        """The platform's last word on a plugin (0.37.0; service-containers-design §3.10), asked nothing: its state
        (active, disabled, invalid; unknown before its first look; not installed) and why, and where its page is. A
        service plugin says with it why a container plugin it lists is not active. 0.40.0: "unmet", with its needs' why,
        for one whose needs this machine does not meet."""
        key = str(name or "")
        with self._lock:
            state, why = self._states.get(key), self._whys.get(key, "")
        known = key in self.machines()
        if state is None:
            state = ("disabled" if not self.enabled(key) else "unknown") if known else "not installed"
            why = why or ("turned off on its page or in the tray" if state == "disabled" else "")
        return {"name": key, "state": state, "why": why, "page": f"#{key}" if known else ""}

    def known_plugins(self) -> list:
        """Every plugin of the platform, attached or not (what a plugin asks of another, and who asks a plugin, are
        said from them): the machine plugins, then the AI assistants; then (0.36.0) the database plugins attached here
        (the registry is not asked for them here: they are attached as the platform attaches its plugins)."""
        return [*self.machines().values(), *self.assistant_plugins().values(), *self.section(DATABASES_SECTION).values()]

    def call_words(self, p) -> dict:
        """How the platform is asked one of a plugin's hooks, in words, for its Internal API's "How it is called": by
        another plugin (its app's ask, the arguments in one list), by a client over HTTP, as a job; then the terms
        (ASK_TERMS). Over HTTP as the frame takes a write: from this machine (the platform listens on 127.0.0.1 and
        answers only a request addressed to it), with the write header (WRITE_HEADER: 1; without it, 403). An AI
        assistant is asked nothing by name here."""
        header = f"with the header {WRITE_HEADER}: 1, from this machine"
        if getattr(p, "KIND", "") == "database":  # 0.36.0: through its page's forms, never by a hook's name
            return {"clients": (f'POST /api/databases/instances {{"plugin": {p.name!r}, "action": action, "name": '
                                f'instance, ..., "confirm": true}} {header}'), "terms": DATABASE_TERMS}
        if not self._machine_kind(p):
            return {"terms": "the platform asks an AI assistant nothing by name"}
        name = p.name
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
        (tabs_of), which it answers once it lists it in its HOOKS (Plugin.ask refuses another, in its words). 0.34.0:
        none that its page and a program never ask (not_by_name: the hook its RPC_HOOK names, the route's alone, and
        those its PLUGIN_ONLY_HOOKS name, another plugin's alone), as none of NOT_ASKED."""
        try:
            hooks = [h for h in m.interface()["hooks"] if h not in NOT_ASKED]
        except Exception:  # noqa: BLE001 - a plugin that cannot say: nothing to ask
            return []
        left = not_by_name(m)
        hooks = [h for h in hooks if h not in left]
        return hooks + [h for h in tab_hooks(m) if h not in hooks and h not in left]

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
        Connections draws the harness to the server), anything else the platform. Under way as _under_way says.

        0.34.0 (liminal-libs 1.66.0's apps/asking.py): a plugin that asks is that call's asker, as the platform names
        it, never an argument (one named "page" asks as no one). A hook only its page asks (PAGE_ONLY_HOOKS) is refused
        to it (403); one only other plugins ask (PLUGIN_ONLY_HOOKS), never offered to its page, is asked for it, but
        not for its own plugin. That word only narrows who asks: a hook the platform asks by no name (NOT_ASKED, the
        hook its RPC_HOOK names) stays refused to every plugin, as before. The platform's own code asks as the asker it
        was handed: the page in the page's routes (_from_page), no one otherwise, whom a gated hook refuses. A refusal
        is noted as an ask that failed; a plugin that says neither word is asked as before."""
        who = self.traffic.actor(sys._getframe(1))
        caller = who or self.NAME
        m = self.machine(name)
        self._refuse_disabled(name)
        self._refuse_unmet(m)  # 0.40.0: nothing new while its needs are unmet (409)
        plugin = who if who and who != self.NAME else None  # a plugin asking another through the platform
        named = None if plugin == PAGE else plugin
        with _asked_by(named) if plugin else contextlib.nullcontext():
            # the asker just named, or the one the platform's code was handed; with an older library a plugin alone
            # is checked here (the page's routes checked their own: _from_page)
            words = refusal(m, hook, _asker()) if asking_mod is not None else refusal(m, hook, named) if plugin else ""
            if words:
                self.traffic.record(caller, name, "ask", f"{hook}: refused", 0.0, False)
                raise HookRefused(HTTPStatus.FORBIDDEN, words, words)
            askable = self.asks(m)
            # a hook left out of asks only for being another plugin's; never one the platform asks by no name (its
            # setup, its settings, a scan, a command, the hook its route hands the requests to)
            for_plugins = (plugin and hook in _plugin_only(m) and hook in self.hooks(m) and hook not in NOT_ASKED
                           and hook != rpc_hook(m))
            if hook not in askable and not for_plugins:
                raise Refused(HTTPStatus.BAD_REQUEST, f"{name} is not asked {hook!r} here: "
                                                      f"{', '.join(askable) or 'nothing'}")
            reads = self.reads_of(m)
            with self._under_way():
                if hook not in reads:  # its name and how many arguments, never their values: a key in a form (0.20.1)
                    many = f" ({len(args)} argument{'' if len(args) == 1 else 's'})" if args else ""
                    self.log(f"platform: {name} asked {hook}{many}")
                try:
                    with self.traffic.timed(caller, name, "read" if hook in reads else "ask", hook):
                        answer = m.ask(hook, *args)
                except (TypeError, ValueError, LookupError) as e:
                    raise HookRefused(HTTPStatus.BAD_REQUEST, f"{type(e).__name__}: {e}", str(e),
                                      _accepting(e)) from None
                except Exception as e:  # noqa: BLE001 - the plugin's own words
                    raise HookRefused(HTTPStatus.BAD_GATEWAY, f"{type(e).__name__}: {e}", str(e)) from None
        return _json_of(answer)

    @contextlib.contextmanager
    def _from_page(self, handler, m, hook: str):
        """An ask of one of a plugin's hooks over HTTP (0.34.0): POST /api/machines/{name}/ask, and /job for one of its
        JOB_HOOKS. Its asker is the page (PAGE), for the hook and for a job's own thread (Setup), never a plugin. A hook
        the plugin says only another plugin asks (PLUGIN_ONLY_HOOKS) is refused (403). One it says only its page asks
        (PAGE_ONLY_HOOKS) is refused (401) when the login says the person at this browser is not shown to be there
        (App.present False: today, a browser not signed in to the platform), and asked when it says they are, or when
        the platform holds no login (None). A hook in neither word is asked as before."""
        words = refusal(m, hook, PAGE)
        if words:
            raise HookRefused(HTTPStatus.FORBIDDEN, words, words)
        if hook in _page_only(m) and self._present(handler) is False:
            title = str(getattr(m, "title", "") or m.name)
            words = (f"{title}'s {hook} is asked only from its page, and the platform's login does not show that you "
                     "are there: sign in on the platform's page, then ask again.")
            raise HookRefused(HTTPStatus.UNAUTHORIZED, words, words)
        with _asked_by(PAGE):
            yield

    def _at_the_page(self, handler, what: str) -> None:
        """One of the page's own routes that changes something, and a login terminal's four (0.39.1): a plugin's
        settings, its switches, its setup or its packages' update, a job's Cancel, a terminal opened, read, typed into
        or closed, a change in the Databases section. None asks a hook by name, so no plugin's PAGE_ONLY_HOOKS reaches
        them: the platform asks its login itself, as _from_page does for a hook only the page asks. Refused (401) when
        the login says the person at this browser is not shown to be there (App.present False: today, a browser not
        signed in to the platform); answered when it says they are, or when the platform holds no login (None), as
        before. Asked before the request is read any further, so nothing is looked up, changed or logged for a refusal.
        `what`: the route in words, the refusal's first ("A plugin's settings are kept")."""
        if self._present(handler) is False:
            raise Refused(HTTPStatus.UNAUTHORIZED, f"{what} only from the platform's page, and the platform's login "
                                                   "does not show that you are there: sign in on the platform's page, "
                                                   "then ask again.")

    def _present(self, handler) -> bool | None:
        """Whether the person at the browser of `handler` is shown to be there (liminal-libs 1.66.0's App.present: the
        login's own proof when it offers one, else a browser signed in to it; None when the platform holds no login).
        None with an older library, which has no such word; False when the frame cannot say."""
        present = getattr(App, "present", None)
        if not callable(present):
            return None
        try:
            said = self.present(handler)
        except Exception:  # noqa: BLE001 - a proof that fails proves nothing
            return False
        return said if said is None else said is True

    def rpc(self, handler, name: str, method: str, body) -> tuple:
        """One request of an agent, handed whole to a plugin (0.34.0; the user, 2026-11-18: "basically a protocol
        plugin that mediates MCP connections to resources by local AI agents"): POST, GET and DELETE
        /api/machines/{name}/rpc, on the platform's own port. The hook its RPC_HOOK names (liminal-libs 1.66.0's
        ProtocolPlugin: rpc) is asked through its own ask with (method, headers, body, gone): the headers of the
        route's allow-list (rpc_headers), the JSON object the frame read ({} for none; None for a GET) and gone(),
        whether the agent has closed its connection (gone_of). Its answer is sent as rpc_answer says: (status, body or
        None, headers).

        Its asker is no one: an agent's request is neither its page's ask nor a plugin's, and the plugin finds the
        agent by its token. Refused: 404 for a plugin whose RPC_HOOK names none of the hooks it answers, 409 while it
        is disabled, 503 while the platform stops, 431 past the headers' bounds, 400 for a body that is not JSON (the
        frame reads NaN and Infinity, which JSON does not have: an answer that echoes the request's id would hold them),
        502 for a hook that fails (its words kept out: a request's may hold its token) or answers what cannot be sent.
        Not counted as under way (_under_way): a call it holds for your answer must not hold up the stop, and the
        plugin's app_stopping ends it. Nothing is logged per request: the plugin notes its own."""
        m = self.machine(name)
        hook = rpc_hook(m)
        if not hook or hook not in self.hooks(m):
            raise Refused(HTTPStatus.NOT_FOUND, f"{name} takes no requests here: it names none of its hooks for them "
                                                "(RPC_HOOK)")
        self._refuse_disabled(name)
        self._refuse_unmet(m)
        with self._lock:
            self._refuse_stopping()
        heard, gone, title = rpc_headers(handler), gone_of(handler), str(getattr(m, "title", "") or name)
        if body is not None:  # strict JSON, as the answer is sent: none of NaN or Infinity reaches the plugin
            try:
                json.dumps(body, allow_nan=False)
            except (TypeError, ValueError, RecursionError):
                raise Refused(HTTPStatus.BAD_REQUEST, "the body is not JSON: NaN and Infinity are not JSON numbers") \
                    from None
        self.traffic.own(m, name)
        try:
            with _asked_by(None):
                answer = m.ask(hook, method, heard, body, gone)
        except Exception as e:  # noqa: BLE001 - said in words, its own kept out
            raise Refused(HTTPStatus.BAD_GATEWAY, f"{title} could not answer: its {hook} failed "
                                                  f"({type(e).__name__})") from None
        return rpc_answer(answer, title, hook)

    def check(self, name: str) -> dict:
        """A plugin's check of this PC for what it installs (the user: \"each plugin should have a scheme for checking the
        environment to see if it supports installing the operating system it has in its name\")."""
        m = self.machine(name)
        self._refuse_disabled(name)
        self._refuse_unmet(m)
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
        self._refuse_unmet(m)
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
        self._refuse_unmet(m)
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
        now = self._clock()
        with self._lock:
            gone = [(n, t) for n, t in self._terminals.items() if not t.alive or now - t.seen > TERMINAL_IDLE_S]
            for n, _ in gone:
                del self._terminals[n]
        for _, t in gone:
            t.close()

    def _start_sweep(self) -> None:
        """The sweep of idle terminals begun, once, while the platform is served (0.34.2; the review of 2026-11-21,
        item 26): a page whose tab was closed stops reading without closing its terminal, and its login shell ran on
        until another terminal request came, or the platform stopped. A one-shot app begins none."""
        if self.once:
            return
        with self._lock:
            if self._sweeper is not None and self._sweeper.is_alive():
                return
            done = self._swept = threading.Event()
            self._sweeper = threading.Thread(target=self._sweep, args=(done,), name="platform-terminal-sweep",
                                             daemon=True)
            sweeper = self._sweeper
        sweeper.start()

    def _sweep(self, done) -> None:
        """Every TERMINAL_SWEEP_S until `done` is set (stop): the idle terminals closed (_close_idle). One that cannot
        be closed is logged and the sweep goes on."""
        while not done.wait(TERMINAL_SWEEP_S):
            try:
                self._close_idle()
            except Exception as e:  # noqa: BLE001 - the next sweep tries again
                self.log(f"platform: idle terminals could not be closed: {type(e).__name__}: {e}")

    def _end_sweep(self) -> None:
        """The sweep ended and waited for (stop): nothing of it outlives the platform."""
        with self._lock:
            sweeper, done, self._sweeper, self._swept = self._sweeper, self._swept, None, None
        if done is not None:
            done.set()
        if sweeper is not None and sweeper is not threading.current_thread():
            sweeper.join(STOP_WAIT_S)

    def open_terminal(self, name: str) -> dict:
        """A login terminal into the plugin's system, or the one open already where it was. 0.31.0: under way as
        _under_way says; one made after the stop closed the terminals is closed at once and refused, so none outlives
        the platform."""
        m = self.machine(name)
        self._refuse_disabled(name)
        self._refuse_unmet(m)
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
        """The frame's start (its page served at its port); the asks and jobs a stop refused are taken again, and
        (0.34.2) idle terminals are swept while it is served."""
        with self._lock:
            self._stopping = False
        url = super().start(*args, **kwargs)
        self._start_sweep()
        return url

    def stop(self) -> None:
        """The terminals closed and the page ended, then the frame's end in good order (0.35.0: the library's
        App.terminate, once, within stop_timeout): the login it includes, then its parts (parts: the jobs wound down,
        then every machine plugin told that the platform stops, together), then what it started. Each plugin is told
        (0.31.0; the user, 2026-11-16: "the plugins manage the services"; a server a plugin started by a click stops
        when the platform stops, unless it starts at boot) through its `signal` when it is attached here (its
        `app_stopping()`, then what was started for it ended), else its `app_stopping()` when it has one (liminal-libs
        1.62.0's AiPlugin), enabled or not, attached or not. One that raises is logged and the rest are still told;
        they are told when the page does not end cleanly, too. Until 0.35.0 they were told one after another, and an
        ordinary end (cli.cmd_serve: serve's own stop, then the command's) told each twice; a second stop now finds
        the first's end. Before they are told, nothing new is begun (_refuse_stopping) and what is under way is wound
        down (_wind_down)."""
        with self._lock:
            self._stopping = True  # nothing new is begun from now on, until it starts again
            terms, self._terminals = list(self._terminals.values()), {}
        self._end_sweep()
        for t in terms:
            t.close()
        try:
            self._end_server()  # the page first, as before 0.35.0: nothing new comes while the rest ends
        finally:
            report = self.terminate(lifecycle.Signal.TERM, self.stop_timeout, plugins=False)
            for r in report.get("objects", ()):
                if r.get("how") == "failed" and r.get("name") in ("jobs", "plugins"):
                    self.log(f"platform: its {r['name']} could not be ended: {r.get('why')}")

    def parts(self) -> tuple:
        """What the platform includes besides its login and its plugins, told before them in the frame's terminate
        (0.35.0): its job runner (the jobs that take a cancel asked to stop and, with the asks under way, waited for:
        what they start is there to be stopped), then its plugins, told together (_tell_stopping)."""
        return (_Part("jobs", self._wind_down), _Part("plugins", self._tell_stopping))

    def _wind_down(self, sig=None, deadline: float | None = None) -> None:
        """What is under way as the platform stops (0.31.0), before each plugin is told: each job that takes a cancel
        asked to stop (an install's or a model's download, whose child would otherwise outlive the platform), then the
        asks under way (_under_way) and those jobs waited for, STOP_WAIT_S at the most in all. What is still under way
        then is logged, and the plugins are told all the same; a second stop finds nothing to wait for. A setup, a
        packages' update and a job that runs to its end are not waited for: their threads end with the platform's
        process, as before, and (0.34.2) each is named in the log as running on."""
        deadline = min(time.monotonic() + STOP_WAIT_S, deadline if deadline is not None else math.inf)
        with self._lock:
            jobs = [(name, job) for name, job in self._setups.items() if job.running]
        asked = []
        for name, job in jobs:
            if not job.cancels:
                # 0.34.2 (the review of 2026-11-21, item 26): said, not left unsaid. The programs it started (a
                # setup's or an update's behind wsl.exe or sudo) are not this process's children to end: they may
                # outlive the platform until the library's jobs take a cancel and end what they started
                self.log(f"platform: {name}'s {job.action} runs on as the platform stops: it takes no cancel, and "
                         "what it started may outlive the platform")
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

    def _tell_stopping(self, sig=lifecycle.Signal.TERM, deadline: float | None = None) -> list[dict]:
        """Each machine plugin told that the platform stops (0.35.0: together, lifecycle.deliver_all): one attached
        here through its `signal` (its `app_stopping`, then what the library started for it), any other through its
        `app_stopping` when it has one; all under one deadline, PLUGINS_DEADLINE_S at the most (and no later than
        `deadline`), and the library's grace more. One that raises is logged; one still at it then is logged as late
        and what was started for it killed with its trees. What each came to, in the registry's order."""
        try:
            machines = self.machines()
        except Exception as e:  # noqa: BLE001 - a registry that cannot say: the platform ends all the same
            self.log(f"platform: its plugins could not be told that it stops: {type(e).__name__}: {e}")
            return []
        sig = lifecycle.Signal.of(sig)
        items = []
        from liminal_libs.sources.plugin import Plugin

        for name, m in machines.items():
            try:
                if isinstance(m, Plugin) and getattr(m, "app", None) is self:
                    items.append((name, m))  # its own signal: its app_stopping, then what was started for it
                    continue
                stopping = getattr(m, "app_stopping", None)
                if callable(stopping):
                    items.append((name, _Told(name, lambda stopping=stopping: stopping())))
            except Exception as e:  # noqa: BLE001 - one that cannot even say: logged, the rest are still told
                self.log(f"platform: {name} did not stop cleanly: {type(e).__name__}: {e}")
        if not items:
            return []
        together = lifecycle.deadline_in(PLUGINS_DEADLINE_S)
        if deadline is not None:
            together = min(together, deadline)
        out = lifecycle.deliver_all(items, sig, together, sender=self,
                                    grace=0.0 if sig is lifecycle.Signal.KILL else self.STOP_GRACE_S)
        for r in out:
            if r.get("how") in ("failed", "refused"):
                self.log(f"platform: {r['name']} did not stop cleanly: {r.get('why')}")
            elif r.get("how") == "late":
                self.log(f"platform: {r['name']} did not stop within {PLUGINS_DEADLINE_S:g} s and its grace: "
                         f"{r.get('why')}")
        return out

    def api(self, handler, method: str, path: str, query: dict, body: dict | None):
        body = body or {}
        self._recall_internet(handler, method, path)  # 0.40.0: GET /api/needs (the frame's) brings the switch back once
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
        if method == "GET" and path == "/api/databases/plugins":  # 0.36.0: the Databases section (the library's)
            return 200, self.databases_overview()
        if method == "POST" and path == "/api/databases/instances":
            if db_section.text_of(body, "action") in db_section.CHANGES:  # 0.39.1: a change is the page's own
                self._at_the_page(handler, "A database's instance is changed")
            try:
                return 200, self.instances_asked(body)
            except db_section.Asked as e:  # the plugin's words, and what accepts its refusal (a second confirmation)
                return e.status, e.answer()
        if method == "POST" and path == "/api/needs/internet":  # 0.40.0: the internet switch {rule: system | there}
            self._at_the_page(handler, "The internet switch is set")
            return 200, self.set_internet(body.get("rule"), handler)
        if method == "POST" and path.startswith("/api/plugins/") and path.endswith("/settings"):
            self._at_the_page(handler, "A plugin's settings are kept")  # 0.39.1: the page's own routes ask the login
            return 200, self.save_settings(path[len("/api/plugins/"):-len("/settings")], body)
        if method == "POST" and path.startswith("/api/plugins/") and path.endswith("/enabled"):
            self._at_the_page(handler, "A plugin is enabled or disabled")
            on = body.get("on")
            if not isinstance(on, bool):
                raise Refused(HTTPStatus.BAD_REQUEST, "on is true or false")
            return 200, self.set_enabled(path[len("/api/plugins/"):-len("/enabled")], on)
        if method == "POST" and path.startswith("/api/plugins/") and path.endswith("/hidden"):
            self._at_the_page(handler, "A plugin's icon is hidden or shown")
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
                self._at_the_page(handler, "A job is asked to stop")
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
                    try:  # (0.34.0: asked as the page asks, in the job's own thread too: _from_page)
                        with self._from_page(handler, m, hook):
                            return 202, self.start_hook_job(name, hook, args).describe(since=0)
                    except HookRefused as e:  # refused before it began, naming what accepts it: the plugin's words with it
                        return e.status, e.answer()
                if what not in ("install", "update"):
                    raise Refused(HTTPStatus.BAD_REQUEST, "action is install, update or hook")
                # 0.39.1: its setup and its packages' update are called on the plugin itself (Setup._run), not asked by
                # name, so its PAGE_ONLY_HOOKS (the WSL base's update_packages) never held them here: the login is asked
                self._at_the_page(handler, "A plugin's install or its packages' update is started")
                job = self.start_setup(name, None, "update" if what == "update" else "setup")
                return 202, job.describe(since=0)
            # 0.39.1: a login terminal is the page's alone, whoever's word names it (the WSL base's PAGE_ONLY_HOOKS do:
            # these routes call terminal() themselves and never read them). Opened, read, typed into and closed
            if action == "terminal" and method == "POST":
                self._at_the_page(handler, "A terminal is opened")
                return 200, self.open_terminal(name)
            if action == "terminal" and method == "GET":
                self._at_the_page(handler, "A terminal is read")
                term = self.terminal_of(name)
                if term is None:
                    raise Refused(HTTPStatus.NOT_FOUND, f"no terminal is open into {name}")
                got = term.read(int(query.get("since") or 0), _wait(query))
                self._close_idle()
                return 200, got
            if action == "terminal/input" and method == "POST":
                self._at_the_page(handler, "A terminal is typed into")
                data, term = body.get("data"), self.terminal_of(name)
                if not isinstance(data, str) or len(data) > MAX_INPUT:
                    raise Refused(HTTPStatus.BAD_REQUEST, f"data is the keys typed, at most {MAX_INPUT} characters")
                if term is None or not term.alive:
                    raise Refused(HTTPStatus.CONFLICT, f"no terminal is open into {name}")
                term.write(data)
                self.traffic.record(self.NAME, self._terminal_program(term), "stream", "keys typed")  # never the keys
                return 200, {"sent": len(data)}
            if action == "terminal/close" and method == "POST":
                self._at_the_page(handler, "A terminal is closed")
                return 200, {"closed": self.close_terminal(name)}
            if method == "POST" and action == "setup":
                self._at_the_page(handler, "A plugin's setup is started")
                steps = body.get("steps") or None
                if steps is not None and (not isinstance(steps, list) or not all(isinstance(s, str) for s in steps)):
                    raise Refused(HTTPStatus.BAD_REQUEST, "steps is a list of step names")
                return 202, self.start_setup(name, steps).describe()
            if method == "POST" and action == "ask":
                hook, args = body.get("hook"), body.get("args") or []
                if not isinstance(hook, str) or not isinstance(args, list):
                    raise Refused(HTTPStatus.BAD_REQUEST, "hook is a hook's name, args a list")
                try:
                    with self._from_page(handler, m, hook):  # 0.34.0: asked as the page asks (who may ask a hook)
                        return 200, {"answer": self.ask(name, hook, args)}
                except HookRefused as e:  # the plugin's words, and what accepts a refusal (a form's second confirmation)
                    return e.status, e.answer()
            if action == "rpc" and method in ("POST", "GET", "DELETE"):  # 0.34.0: an agent's request, to its plugin
                return self.rpc(handler, name, method, None if method == "GET" else body)
            if method == "POST" and action == "enabled":
                self._at_the_page(handler, "A plugin is enabled or disabled")
                on = body.get("on")
                if not isinstance(on, bool):
                    raise Refused(HTTPStatus.BAD_REQUEST, "on is true or false")
                return 200, self.set_enabled(name, on)
            if action == "run":  # the review of 2026-11-21 (item 26): any program or account here could send it
                raise Refused(HTTPStatus.NOT_FOUND, 'no route runs a command on a machine (0.34.1): it ran any words given, as root or elevated, with no sign-in and no confirmation. On this machine: liminal-platform machine NAME run -- COMMAND')
        return super().api(handler, method, path, query, body)
