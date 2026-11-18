"""What the platform itself associates with, for its own External API (liminal-libs 1.63.0's App.apis; the user,
2026-11-16: "the external should be all the SDKs/APIs the plugin associates with"; "for all apps, and all plugins").

What the platform's own code calls that Liminal does not make, and nothing of its plugins' (each says its own on its
page): the docker command (the Docker row of its status, its instances), WSL's command line (asked by the Docker row on
Windows when no docker command is there), the version control tools its Codebase reads the workspace with (git, and
Subversion or Mercurial for a working copy of theirs), and how it reads this machine's facts (Python's platform and os
modules; Windows' GlobalMemoryStatusEx through ctypes). Imported only when the platform's own External API is asked
(PlatformApp.apis), so the platform's start loads nothing more for it.

Every address is a page of the maker's own, for people to read, read on 2026-11-17: the platform never fetches any of
them (liminal_libs' dead_links is asked only by a check run by hand, LIMINAL_VENDOR_PAGES=1). This is the one .py of the
platform that names an outside host (the user, 2026-10-31: the app's code names no provider's host, links for people
excepted): tests/test_own_apis.py holds every other to that."""
from __future__ import annotations

try:  # liminal-libs 1.63.0: the cards' own module, which loads neither the registry nor pandas
    from liminal_libs.apis import Api, Area, Call, Link
except ImportError:  # an older library: the same classes where they were (sources/apis.py, since 1.49.0)
    from liminal_libs.sources.apis import Api, Area, Call, Link

VERIFIED = "2026-11-17"

_DOCKER_REF = "https://docs.docker.com/reference/cli/docker/"
_GIT = "https://git-scm.com/docs/"
_SVN = "https://svnbook.red-bean.com/en/1.7/"
_HG = "https://www.mercurial-scm.org/doc/hg.1.html"
_WIN_MEMORY = "https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/"
_PY = "https://docs.python.org/3/library/"

DOCKER = Api(
    name="Docker's command line", maker="Docker, Inc.", kind="command",
    about=("The docker command and the engine it reaches: the platform asks it only what Docker there is, for the "
           "Docker row of its status (GET /api/docker, /api/status) and for the Docker instances (GET /api/instances): "
           "this machine's engine, each of the command's contexts, a host named by LIMINAL_DOCKER_HOST, and those its "
           "machine plugins run. What runs in an engine (containers, images, volumes) is the Docker plugin's, on its "
           "own page."),
    base="docker (LIMINAL_DOCKER_COMMAND names another: nerdctl, podman; -H LIMINAL_DOCKER_HOST for a host)",
    version="the command's JSON (--format '{{json .}}')",
    auth=("none of its own: the engine's socket's permissions (the docker group on Linux, docker-users on Windows), a "
          "context's SSH key or TLS certificates"),
    limits="none: the engine is asked twice at the most for a status, each ask with a time limit (30 s)",
    costs="the docker command and Docker Engine are free (Apache 2.0); the platform only reads",
    links=(
        Link("Docker Engine", "https://docs.docker.com/engine/", "docs"),
        Link("docker CLI reference", _DOCKER_REF, "reference"),
        Link("docker version", _DOCKER_REF + "version/", "reference"),
        Link("docker context ls", _DOCKER_REF + "context/ls/", "reference"),
        Link("Docker contexts", "https://docs.docker.com/engine/manage-resources/contexts/", "guide"),
        Link("docker/cli", "https://github.com/docker/cli", "source"),
    ),
    areas=(
        Area("System", "docker version: the client's and the engine's versions, and whether an engine answers",
             _DOCKER_REF + "version/", covered="the Docker row: the command, its engine's version, its system and "
                                               "architecture, or why none answers"),
        Area("Contexts", "docker context: the engines the command knows besides this machine's (a VPS over SSH)",
             _DOCKER_REF + "context/", covered="each context but the default is a Docker instance"),
        Area("Containers, images, volumes and networks", "what an engine runs and keeps", _DOCKER_REF,
             covered=""),
    ),
    calls=(
        Call("docker version --format '{{json .}}'", "the client's and the engine's versions, as JSON (GET /version)",
             "System", used="GET /api/docker and the Docker row of GET /api/status", docs=_DOCKER_REF + "version/"),
        Call("docker context ls --format '{{json .}}'", "the command's contexts, as JSON (its own store: no engine "
             "asked)", "Contexts", used="GET /api/instances: a context's instance", docs=_DOCKER_REF + "context/ls/"),
        Call("docker ps -a", "every container, stopped ones too", "Containers, images, volumes and networks",
             docs=_DOCKER_REF + "container/ls/"),
    ),
    verified=VERIFIED)

WSL = Api(
    name="WSL's command line", maker="Microsoft", kind="command",
    about=("wsl.exe, the Windows Subsystem for Linux's command: on Windows, when no docker command is found and no "
           "context or host names another engine, the Docker row says whether WSL 2 is there, which is what Docker "
           "Desktop and Rancher Desktop run their engine in. Installing and running WSL distributions is the WSL "
           "plugins', on their own pages."),
    base="wsl.exe (Windows only)",
    version="its --status lines: the default version and the default distribution",
    auth="none: this user's own WSL",
    limits="one ask for a status, 15 s at the most",
    costs="free (MIT, open source since 2025)",
    links=(
        Link("Windows Subsystem for Linux Documentation", "https://learn.microsoft.com/en-us/windows/wsl/", "docs"),
        Link("Basic commands for WSL", "https://learn.microsoft.com/en-us/windows/wsl/basic-commands", "reference"),
        Link("microsoft/WSL", "https://github.com/microsoft/WSL", "source"),
    ),
    calls=(
        Call("wsl --status", "WSL's configuration: its default distribution's type, the default distribution, the "
             "kernel's version", used="the Docker row on Windows without a docker command: whether WSL 2 is there",
             docs="https://learn.microsoft.com/en-us/windows/wsl/basic-commands#check-wsl-status"),
        Call("wsl --list --verbose", "the distributions installed, their state and WSL version",
             docs="https://learn.microsoft.com/en-us/windows/wsl/basic-commands#list-installed-linux-distributions"),
    ),
    verified=VERIFIED)

GIT = Api(
    name="git", maker="The Git project", kind="command",
    about=("The version control command its Codebase reads the workspace's git working copies with (the frame's "
           "Codebase, under This machine; GET /api/codebase): each one's branch, the commit checked out, its remote, "
           "what is changed and not committed, how far ahead and behind its upstream as of its last fetch, and its "
           "tracked files, counted by language. git is told to take no lock (GIT_OPTIONAL_LOCKS=0) and to ask nothing "
           "at a terminal (GIT_TERMINAL_PROMPT=0); no remote is asked but on the user's Fetch."),
    base="git, in each working copy of the workspace",
    version="git status's porcelain v2",
    auth="none of its own: a remote's credentials are git's and the user's (asked at no terminal: a fetch that needs "
         "them fails in words)",
    limits="20 s for each command, 90 s for a fetch; read at most once in 10 minutes unless asked fresh",
    costs="free (GPL 2)",
    links=(
        Link("Git reference", _GIT, "reference"),
        Link("git (its environment variables)", _GIT + "git", "reference"),
        Link("git status", _GIT + "git-status", "reference"),
        Link("git log", _GIT + "git-log", "reference"),
        Link("git config", _GIT + "git-config", "reference"),
        Link("git ls-files", _GIT + "git-ls-files", "reference"),
        Link("git fetch", _GIT + "git-fetch", "reference"),
        Link("Install Git", "https://git-scm.com/install/", "tool"),
        Link("git/git", "https://github.com/git/git", "source"),
    ),
    areas=(
        Area("The working copy", "status: the branch, its upstream, ahead and behind, what is changed",
             _GIT + "git-status", covered="each repository's branch, changes and distance from its upstream"),
        Area("History", "log: the commits", _GIT + "git-log",
             covered="the commit checked out: its hash, date and subject"),
        Area("Configuration", "config: the repository's settings", _GIT + "git-config",
             covered="its remote's address (shown with no name or token in it)"),
        Area("The index", "ls-files: the files git tracks", _GIT + "git-ls-files",
             covered="the code counted: the tracked files"),
        Area("Remotes", "fetch: what a remote has", _GIT + "git-fetch",
             covered="Fetch, on the user's click: the remote-tracking branches move, nothing checked out does"),
        Area("Commits, branches and merges", "commit, branch, merge, rebase, push: the repository changed",
             _GIT, covered=""),
    ),
    calls=(
        Call("git status --porcelain=v2 --branch", "the working copy's state and its branch's headers",
             "The working copy", used="Codebase: the branch, ahead and behind, the changes", docs=_GIT + "git-status"),
        Call("git log -1 --format=%h%x1f%cI%x1f%s", "the last commit: its short hash, its date, its subject", "History",
             used="Codebase: the commit checked out", docs=_GIT + "git-log"),
        Call("git config --get remote.NAME.url", "the address of the remote its branch follows (git config's older "
             "mode)", "Configuration", used="Codebase: its remote", docs=_GIT + "git-config"),
        Call("git ls-files -z", "the files git tracks, each ended by a NUL", "The index",
             used="Codebase: the files counted by language", docs=_GIT + "git-ls-files"),
        Call("git config --get-regexp ^remote\\..*\\.url$", "whether the working copy has any remote", "Configuration",
             used="before a fetch: a working copy with no remote is not asked", docs=_GIT + "git-config"),
        Call("git fetch --quiet", "what the remote has (its remote-tracking branches move)", "Remotes",
             used="Fetch, on the user's click (POST /api/codebase/fetch)", docs=_GIT + "git-fetch", writes=True),
        Call("git push", "commits sent to a remote", "Commits, branches and merges", docs=_GIT + "git-push",
             writes=True),
    ),
    verified=VERIFIED)

SUBVERSION = Api(
    name="Subversion (svn)", maker="The Apache Software Foundation", kind="command",
    about=("Subversion's command, asked by the Codebase for a Subversion working copy in the workspace (if there is "
           "one): its address, its revision, its last change and what is changed. Its server is never asked."),
    base="svn, in a Subversion working copy", version="svn info's and svn status's lines",
    auth="none: the working copy only", limits="20 s for each command", costs="free (Apache 2.0)",
    links=(
        Link("Apache Subversion Documentation", "https://subversion.apache.org/docs/", "docs"),
        Link("svn info", _SVN + "svn.ref.svn.c.info.html", "reference"),
        Link("svn status", _SVN + "svn.ref.svn.c.status.html", "reference"),
        Link("Apache Subversion", "https://subversion.apache.org/", "tool"),
    ),
    calls=(
        Call("svn info", "the working copy's URL, revision and last change", used="Codebase: its remote and revision",
             docs=_SVN + "svn.ref.svn.c.info.html"),
        Call("svn status -q", "the items changed locally", used="Codebase: how many are changed",
             docs=_SVN + "svn.ref.svn.c.status.html"),
    ),
    verified=VERIFIED)

MERCURIAL = Api(
    name="Mercurial (hg)", maker="The Mercurial project", kind="command",
    about=("Mercurial's command, asked by the Codebase for a Mercurial working copy in the workspace (if there is "
           "one): its revision, its branch, whether it is changed, and its default path. Its remote is never asked."),
    base="hg, in a Mercurial working copy", version="hg id's and hg paths' lines",
    auth="none: the working copy only", limits="20 s for each command", costs="free (GPL 2 or later)",
    links=(
        Link("hg's manual", _HG, "reference"),
        Link("Mercurial", "https://www.mercurial-scm.org/", "tool"),
    ),
    calls=(
        Call("hg id -i -b", "the working directory's revision (a + when changed) and its branch",
             used="Codebase: the commit, the branch, whether it is changed", docs=_HG),
        Call("hg paths default", "the default remote's address", used="Codebase: its remote", docs=_HG),
    ),
    verified=VERIFIED)

PYTHON = Api(
    name="Python's platform and os modules", maker="Python Software Foundation", kind="sdk",
    about=("How the platform reads this machine's facts (This machine; GET /api/status, /api/overview): the system, "
           "its release and version, the machine's type, the processor, the host's name and the Python it runs, "
           "through Python's platform module; the logical processors through os.cpu_count; on Linux the memory "
           "through os.sysconf, the system's sysconf(3)."),
    base="the Python the platform runs on", version="Python 3.12 to 3.15",
    auth="none", limits="none: read with each status", costs="free (the PSF licence)",
    links=(
        Link("platform: the underlying platform's identifying data", _PY + "platform.html", "docs"),
        Link("os: miscellaneous system information", _PY + "os.html#miscellaneous-system-information", "reference"),
        Link("sysconf(3)", "https://man7.org/linux/man-pages/man3/sysconf.3.html", "reference"),
    ),
    calls=(
        Call("platform.system(), release(), version(), machine(), processor(), node()",
             "the system's name, release and version, the machine type, the processor, the network name",
             used="This machine: what it is", docs=_PY + "platform.html"),
        Call("platform.python_version()", "the Python version", used="This machine: its Python",
             docs=_PY + "platform.html#platform.python_version"),
        Call("os.cpu_count()", "the system's logical processors", used="This machine: its processors",
             docs=_PY + "os.html#os.cpu_count"),
        Call("os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')", "the page size and the pages of physical "
             "memory (Unix)", used="This machine: its memory, on Linux", docs=_PY + "os.html#os.sysconf"),
    ),
    verified=VERIFIED)

WINDOWS_MEMORY = Api(
    name="Windows' GlobalMemoryStatusEx", maker="Microsoft", kind="system",
    about=("The Win32 call that fills a MEMORYSTATUSEX with the system's physical and virtual memory, asked through "
           "Python's ctypes from kernel32.dll: on Windows, the machine's memory for This machine (its total physical "
           "memory, in MB)."),
    base="kernel32.dll (sysinfoapi.h), through ctypes", version="Windows XP and later",
    auth="none", limits="none: read with each status", costs="part of Windows",
    links=(
        Link("GlobalMemoryStatusEx function", _WIN_MEMORY + "nf-sysinfoapi-globalmemorystatusex", "reference"),
        Link("MEMORYSTATUSEX structure", _WIN_MEMORY + "ns-sysinfoapi-memorystatusex", "reference"),
        Link("ctypes: a foreign function library for Python", _PY + "ctypes.html", "sdk"),
    ),
    calls=(
        Call("GlobalMemoryStatusEx(&MEMORYSTATUSEX)", "the system's memory now: ullTotalPhys, the physical memory in "
             "bytes, among the rest", used="This machine: its memory, on Windows",
             docs=_WIN_MEMORY + "nf-sysinfoapi-globalmemorystatusex"),
    ),
    verified=VERIFIED)

APIS = (DOCKER, WSL, GIT, SUBVERSION, MERCURIAL, PYTHON, WINDOWS_MEMORY)
