# Changelog

## 0.34.1 (2026-11-24)

The review of 2026-11-21 (Monday list item 26), a P1: `POST /api/machines/<name>/run` is gone. It handed any list of
words to the plugin's `run` (as root in the Linux firewall's, into PowerShell unquoted in the Windows admin's and
firewall's), checked only that the request came from this machine with the write header, and asked for no sign-in
and no confirmation: any program or account on this PC could empty the firewall or read the platform's environment.
No page and no app used it. The command line keeps `liminal-platform machine NAME run`, in its own process. The
route now answers 404 and says so.

## 0.34.0 (2026-11-19)

The platform's side of the MCP plugin, and a fourth group of AI plugins. The user, 2026-11-18: "now i need an MCP
plugin for platform, basically a protocol plugin that mediates MCP connections to resources by local AI agents"; "top
4 inference engines, top 4 agentic harnesses (open source)"; "all platform"; "both linux and windows compatibility".
The protocol plugin's base, the two words of who may ask a hook, the asker and the proof that you are there are
liminal-libs 1.66.0's (`machines/protocol.py`, `internal.py`, `apps/asking.py`, `App.present`). The plugins are built
on this release.

- **Protocols**, after Harnesses under AI plugins: a machine plugin whose `SECTION` is "ai" and whose `GROUP` is
  "protocol" (liminal-libs 1.66.0's `ProtocolPlugin`, MCP's first). The list, the overview, each status and the tray
  follow `AI_GROUPS`; in the tray the protocols come after the harnesses.
- **An agent's route**: `POST`, `GET` and `DELETE /api/machines/{name}/rpc`, on the platform's own port (no new one),
  for a plugin whose `RPC_HOOK` names one of the hooks it answers. The hook is handed the request whole, through the
  plugin's own ask: its method, the headers of an allow-list named in lowercase (the bearer token, MCP's session,
  version, method and name, `accept`, `content-type`, `user-agent`, `last-event-id`, and up to 16 `mcp-param-*`; each
  at most 4,096 characters), its JSON body and `gone()`, whether the agent has closed its connection, read without
  waiting (a select, poll where the system has it, then a one-byte peek). Its answer is sent as it is: a status from
  200 to 599, a JSON object or nothing, and five headers at the most (`Mcp-Session-Id`, `MCP-Protocol-Version`,
  `WWW-Authenticate`, `Allow`, `Retry-After`), each one line of plain text. Refused: 404, 409 while the plugin is
  disabled, 503 while the platform stops, 431 past the headers' bounds, 400 for a body holding NaN or Infinity (JSON
  has neither), 502 for a hook that fails (its words kept out) or answers what cannot be sent: a body that is not JSON,
  a 204 with a body, a 205 or a 304. So the agent always reads an answer (the review found that such a body left it
  none: the frame's send failed after the route returned). The request is no one's ask, the plugin finding the agent
  by its token; it is not counted as under way (a call held for your answer never holds up the stop: the plugin's
  `app_stopping` ends it), and it leaves no line in the platform's log. It is noted as an ask (`classify`), and listed
  in `routes.py`.
- **Who may ask a hook.** The page is the asker of `POST .../ask` and `.../job`, inside the job's own thread too (a job
  records its asker where it is started and sets it in its thread: never what the thread inherits). A plugin asking
  through the platform is that call's asker, named by the platform. A hook a plugin's `PLUGIN_ONLY_HOOKS` names is
  refused over HTTP (403) and never offered to its page (left out of `asks`, as the RPC hook is); another plugin asks
  it, its own plugin does not. The word only narrows who asks: one of `NOT_ASKED` (setup, settings, scan, run) or the
  RPC hook stays refused to every plugin even when the word names it (the review found that it let every plugin ask
  them by name). A hook its `PAGE_ONLY_HOOKS` names is refused to a plugin (403, noted in Connections as
  an ask that failed), and over HTTP asked when the login says you are there (`App.present`: today a browser signed in
  to the platform's login, which any program can open as the passwordless user: a speed bump), refused (401) when it
  says you are not, and asked when the platform holds no login. A plugin whose words cannot be read is asked nothing by
  name. A plugin that says neither word is asked exactly as before.
- **What a plugin says is drawn as text, every space and line kept**: an answer's lines and a refusal's words, so a
  call waiting for your answer shows its arguments exactly (the MCP plugin's Open…), and so does an ask-twice call's
  second confirmation.
- Its Internal API: `CALLS` says `rpc` (the route), `ATTRIBUTES` the three words it reads (`RPC_HOOK`,
  `PLUGIN_ONLY_HOOKS`, `PAGE_ONLY_HOOKS`), `ASK_TERMS` the gates, and four notes the route and the gates.
- With a liminal-libs before 1.66.0 the platform reads the two words from the plugin itself and holds them the same:
  there is no proof to ask, and no asker is handed over. The floor stays liminal-libs>=1.54.0: every new name is read
  with getattr.

Tests: test_rpc_route.py (each method handed over whole, both allow-lists, the bounds, gone() on a stand-in
connection with select and with poll, the answers, 404, 409, 503, never asked by name, no one's ask, nothing logged, a
held request that never holds the stop, and the library's own ProtocolPlugin through the routes: a token shown once,
an agent found by it, a harness's agent and launch token, each gate held); test_page_only.py and test_plugin_only.py
(refused to a plugin, over HTTP by the login's word or always, the asker named, a job's thread handed the page, a
thread handed nothing refused, words that cannot be read, a plugin named "page", an older library); the pinned groups,
the routes' rows, `rpc` and the three words in CALLS and ATTRIBUTES, and the page's text drawn as text. Each fix undone
on a scratch copy fails a test (31 of 31). The review's four (an answer that is not JSON, a request holding NaN or
Infinity, a body on a 204 and a 205 or a 304, held by tests that drive the frame's own handler in memory as an agent
reads it, no socket made; and PLUGIN_ONLY_HOOKS opening a hook asked by no name) each fail with their fix undone (7 of
7).

## 0.33.0 (2026-11-18)

The firewalls' globe loads its layers. The user, 2026-11-16: "the globe-firewall should allow filtering, so i can view
apps connected to hosts all across the globe, or ports talking to all hosts. The globe should have the same kind of
geography associated with the exchanges globe, but the firewall globe should instead of exchanges, have all the
backbones,ibones, major internet infrastructure, (as many as possible) datacenter locations." The Netstat tab, the
hosts database, the globe's filters and its internet infrastructure are liminal-libs 1.65.0's Firewall base's, and the
firewall plugins name the data sets (plugin-platform-firewall-windows 0.7.0, plugin-platform-firewall-linux 0.9.0):
the platform gives the globe its way to a layer and draws the Netstat tab's table.

- **A layer's geometry through the platform.** The globe asks its page for a layer once a version, while that layer
  is on and drawn. The page asks the plugin the hook the globe names (`layer_hook`: the firewalls' `world_layer`, a
  file on this machine read back, nothing downloaded) with the layer's id, `POST /api/machines/NAME/ask`, and hands
  the answer to the globe; a refusal is said in the plugin's own words. Where the globe names no hook, or the plugin
  offers none, its layers stay off and their switches say why.
- `world_layer` is asked as a read (`READS`, beside `wanted`): noted as one in Connections, never logged.
- **The layers' switches are remembered in this browser**, under the plugin's name and the tab's
  (`liminal-globe-layers:NAME/world`). A globe left open while the platform starts again on a library whose
  firewalls name a hook is given its loader then, drawn again in the same element; one whose way is gone is made anew
  without it.
- **The Netstat tab's table** (the library's flows): a **Since** column, drawn as the plugin sends it ("15 Nov
  21:01", "20:59:23") with the whole moment in its tooltip; **Up for** says the days past a day ("3 d 0 h", as the
  library does); and **Flagged only** is drawn only where a page's filters name it, so a table that flags nothing
  (Netstat) has no switch that would only empty it. What an ask that failed says is one expression for a tab's page
  and a globe's layer (`refusalWords`).
- With a liminal-libs before 1.65.0 nothing changes: the firewalls have neither the Netstat tab nor layers. The floor
  stays liminal-libs>=1.54.0.

Tests: tests/conftest.py's autouse `no_real_hosts` (as the library's: the recording setting `shown`, the socket
table's reader refused, the hosts database, the layers and the GeoIP folder in the test's own folder, and a stand-in
socket table for the test's firewall) and `_none_of_this_users_saved_variables` (an app built with no login reads
none of this user's saved variables, so no test opens the registry); test_no_outside.py tests both. test_plugin_tabs.py:
a layer asked as a read and never logged; the Netstat tab and the layers through the platform on 1.65.0, the
library's own refusal words; the page's loader, key, way, Flagged only and Since pinned. The page-pin test reads the
page's script and no longer serves.

## 0.32.0 (2026-11-18)

External API and Internal API on every plugin's page, and the platform's own two views. The user, 2026-11-16: "for all
apps, and all plugins, there should be an external api tab, and an internal api tab, the internal api is for
interfaces the plugin shares with the rest of the app, the external should be all the SDKs/APIs the plugin associates
with"; 2026-11-17: "all plugins are middleware". The Internal API is made and drawn by liminal-libs 1.63.0
(`internal.py`, `internal.js`, the frame's `GET /api/app/apis`). The platform is the first app to show both; the
charts, the integrator and the login follow.

- Every machine plugin's and AI assistant's page has **Main**, **External API** and **Internal API** beside its title,
  then its own tabs. External API is the old API tab's cards: `#name/api` opens it and is written again as
  `#name/external`. No plugin's own tab takes the ids main, api, external or internal.
- **Internal API** is made by the library from the plugin itself, asking it nothing: the base it is built on, and so
  the standard interface it implements; the standard hooks it answers, layer by layer, and those it leaves to the
  contract; then its own hooks, each with its call, its line, its whole docstring, read or change, and who uses it
  (the platform's code: `CALLS`; other plugins: `SERVICE_HOOKS`, with the plugins whose `ASKS` name it; its page: the
  hooks its status names, `pageAsks`; or anything asking it by name); how it is called (`self.app.ask(NAME, hook,
  [arguments])`, `POST /api/machines/NAME/ask` with the header `X-Liminal-Charts: 1` from this machine, or as a job);
  its settings through the login, and what it asks of other plugins.
- Every status carries `internal`. When the library cannot read a plugin, the status carries `internal: null` and
  `internalError` in words: its tab says so, not to restart the platform, and why is logged once.
- A hook a plugin lists in `READ_HOOKS` is asked as a read: noted as one in Connections and not logged, as a tab's hook
  is.
- **The platform's own entry**, under This machine after Codebase, has two views, both from `GET /api/app/apis` and
  asked only while shown. External API (`#app`): what its own code calls that Liminal does not make (Docker's and
  WSL's command lines, git, svn and hg, Python's platform and os modules, GlobalMemoryStatusEx), declared in `apis.py`
  as links for people, never fetched. Internal API (`#app/internal`): what it calls and reads on its plugins of each
  kind (`CALLS` and `ATTRIBUTES`, 0.31.0's `app_stopping`, `GROUP` and `CANCEL_HOOKS` among them), what it offers its
  plugins, its routes beside the frame's, the login it includes, and its plugins (those it knows, and how many are
  attached).
- `routes.py` lists the 23 routes of `api()`, 0.31.0's job/cancel among them, each with what it is, its class and who
  asks it; `GET /api/status` is a client's.
- The platform's Internal API says what a job's hook is handed (`INTERNAL_NOTES`): `log=` and `log.cancelled`.
- The platform's External API names the signals `serve` handles on POSIX: SIGTERM and SIGHUP (the `signal` module).
- On a phone's width the tabs wrap.
- With a liminal-libs before 1.63.0 the page shows Main and External API, and no entry of its own; with a platform
  process from before, the Internal API tab and the entry say to restart it. The floor stays liminal-libs>=1.54.0.

Tests: test_internal_tab.py (`CALLS` and `ATTRIBUTES` held to the platform's source by ast, calls told from reads),
test_internal_page.py, test_own_apis.py (no other `.py` of the platform names an outside host), test_routes.py (the
table held to the code) and test_no_outside.py (the shared guard in tests/conftest.py); test_tabs.py reads the page's
files from the package and no longer serves.

## 0.31.0 (2026-11-18)

The AI plugins' section, a job's Cancel, and a stop that ends what the plugins started. The user, 2026-11-16, asking
for llama.cpp, Ollama, vLLM, OpenCode, Aider and Continue: "they will be classified as AI plugins"; "the other
plugins are strictly proprietary service plugins".

- The list has one **AI plugins** heading with three groups: Proprietary services (the AI assistants, as before),
  Inference and Harnesses. A machine plugin goes there when its `SECTION` is "ai" and its `GROUP` "inference" or
  "harness"; another group falls under Machine plugins. The tray follows the same order. A server before 0.31.0 sends
  no group: its plugins are drawn as before.
- **Cancel**: `POST /api/machines/NAME/job/cancel` answers 202 with the job's state, for a hook the plugin names in
  its `CANCEL_HOOKS`, with liminal-libs 1.62.0's `Output.cancel`. An optional `{"startedAt"}` names the job meant, so a
  stale page never stops the next one. 409 when no job runs or the named one has ended; 400 for a hook that runs to
  its end, or a library that cannot cancel. A job's state says `cancels`, `cancelling` and `cancelled`; its panel has
  a Cancel button (one click). A cancel is counted as no failure.
- **Stopping**: once the platform stops, asks, jobs, login terminals and commands answer 503 ("the platform is
  stopping"); each plugin is told `app_stopping()` once per stop (a second stop is safe), jobs that cancel are asked
  to, and what was under way is waited for a few seconds. `serve` ends on SIGTERM and SIGHUP on POSIX as on Ctrl+C,
  so a closed terminal tab no longer leaves the servers a plugin started running.
- `serving` counts as a read and is not logged; a plugin asking another through the platform is noted in
  Connections as the one asking.
- **Passwords**: a password field's value is never shown ("(given)" in a confirmation), never put back in its field,
  let go of as soon as it is sent, and typed again at a second confirmation. A job lets go of its hook's arguments, a
  sudo password among them, as soon as it has run.
- The floor stays liminal-libs>=1.54.0: Cancel says what an older library lacks.

## 0.30.0 (2026-11-16)

Codebase, under This machine beside Connections (the user: "i want to add another functional class called codebase,
which has the associated repositories (git/svn/,,,) if there are, also the code base, and stats like how much is rust
%, javascript %, etc..."; "this class will be added to all the 'apps' just like connections"; "it will also say how
far it is behind the remote"). The class and its drawing are the library's (liminal-libs 1.59.0: `apps/codebase.py`,
answered by every app at `GET /api/codebase`; `ui/static/codebase.js`), so the platform's part is small.

- The list has **Codebase** under This machine. Its page shows the workspace's code by language as one bar (the share
  of each of the bytes of code and markup), the same for what the platform itself runs from, every repository (its
  kind, branch, commit, how far it is behind and ahead of its remote and when that remote was last asked, what is not
  committed, its lines) with filters for the ones behind, the ones with changes and the platform's own, and every
  language with its lines and files. A repository picked shows its details beside.
- **Read again** reads everything anew. **Ask the remotes** runs `git fetch` in every repository that has a remote,
  after a confirmation, and counts what is behind anew; nothing reaches a remote without that click.
- With a library from before 1.59.0 the entry is not listed.

## 0.29.0 (2026-11-16)

A plugin not valid yet shows what it needs. The user: "still need linux firewall". Inside WSL's Ubuntu the Linux firewall
could not be read (sudo asks for a password there, and no firewall tool is installed), and its page said only that.

- A plugin that is not valid yet now has its own tables drawn under the reason, as one not for this machine has them.
- They are read only: the server sends such a plugin no asks, so the page draws neither an ask's button nor a form's.
- The Linux firewall 0.8.1 puts "What the firewall needs here" there, and inside WSL its "Under WSL" table.

Tests: the branch, and that what it draws is read only.

## 0.28.0 (2026-11-16)

A job refused before it begins is offered as a second confirmation, as an ask's refusal is. liminal-libs 1.55.0's GeoIP
install (the firewalls' World Wide Web tab) runs as a job, a 60 MB download with its progress in the plugin's panel, and
refuses until its licence is accepted, naming the argument that accepts it (`accept_licence`).

- `start_hook_job` waits up to `JOB_REFUSAL_S` (1 s) for the job's first line or its end. A refusal before the first
  line that names an accepting argument comes back as an ask's refusal does: 400, with the plugin's words and `accept`.
  The page then offers its second confirmation and asks the job again with that argument true; platform.js needed no
  change, since its accept step resends the same job form. The refused job is forgotten, and the one before it kept.
- Every other refusal still ends as the job's error, in its panel, as before.
- A job's end now wakes a panel's read waiting on its lines (`Setup._run` ends with `output.finish()`).
- A job hook that prints nothing in its first second (Docker's pull, while it checks the engine) gets its 202 up to
  1 s later.

Tests: a job refused before its first line answers 400 with the plugin's words and what accepts it, leaving no job to
follow; asked again, accepted, it runs as a job, one at a time, its lines followed to its answer; refused once more,
the last job is what the page still shows.

## 0.27.0 (2026-11-15)

A plugin's own tabs. The user, 2026-11-14: "so for the firewall's both are going to get a 'world wide web view'"; "there
needs to be a way to 'filter' (another tab)".

The tabs a plugin declares (liminal-libs 1.54.0's `MachinePlugin.TABS`) come after Main and API, each at #name/<id>.

**When a tab is asked.** The page asks a tab's hook every `every` seconds: a POST to api/machines/NAME/ask, with no
arguments. It asks only while all of these hold:
- the tab is shown;
- the page is visible;
- when the charts app shows the platform in its bound frame, that frame is drawn.
So a capture behind a tab stops when nobody looks: the user's decision, "only while you look".

There is one ask at a time per tab, kept across leaving and coming back, and a late one is said.

**What the page draws.** Whatever the hook answers:
- a globe (liminal-globe.js);
- charts, forgotten once no longer drawn;
- connections with their filters (direction, flagged, labels, search), flagged rows first, read by own keys only;
- tables, forms and actions.
The parts are not announced again on every redraw.

**The server.**
- It sends each plugin's `tabs`: at most 8, and never Main or API, setup, settings, scan, run or a job hook.
- A tab's hook is a read: noted as such in Connections, and kept out of the log.
- A server before 0.27.0 sends no tabs, and the page then shows Main and API as before.

Needs liminal-libs 1.54.0.

## 0.26.0 (2026-11-15)

Two more sections in the list on the left, built the way Cloud plugins is (the user: "platform needs a virtualization
plugins section"; "just like cloud plugins"; "then OS plugins"). The list is now This machine, Machine plugins,
Virtualization plugins, OS plugins, Cloud plugins, AI assistants. Each plugin names its own section with liminal-libs
1.51.0's `MachinePlugin.SECTION`, and the server now knows two more words for it:
- "virtualization": a hypervisor's or a container engine's plugin (Hyper-V, libvirt, LXD, Docker, Kubernetes, Windows
  containers);
- "os": an operating system's plugin (WSL's distributions, and the Windows and Linux administration and firewalls).

The machine's own page draws a table for each section that has plugins, each with a line saying what it holds. A section
is drawn only when it has plugins, and with no plugin at all Machine plugins says so. A server older than 0.26.0 says
"machine" for these plugins, so they stay under Machine plugins there, as before.

## 0.25.0 (2026-11-14)

The cloud plugins have their own section in the list on the left (the user: "classify the cloud plugins under the 'cloud plugins' section which should be on the far left"). The list is now This machine, Machine plugins,
Cloud plugins, AI assistants. Each machine plugin's overview row and status carry its `section`, from liminal-libs
1.51.0's `MachinePlugin.SECTION`: "machine" unless the plugin says "cloud". The machine's own page lists the cloud plugins
in a Cloud plugins table of their own. A server older than 0.25.0 sends no section, and the page then draws every plugin
under Machine plugins, as before.

## 0.24.3 (2026-11-11)

A plugin's tabs are as they first were (the user, after three other looks: "lets go back to the original tab layout";
asked which, the first): the plugin's title, then Main and API (APIs for several) as two small words beside it, the one
shown in the accent on a line of it. 0.24.0's bordered buttons, 0.24.1's lines with a rising stroke and 0.24.2's
address are gone.

## 0.24.2 (2026-11-11)

A plugin's tabs read as an address (the user: "the tabs for the plugins should mirror the format of a URI address
[plugin] : /  / module1 / module2 / module3"): the plugin's name, a colon and two strokes, then its modules with a
stroke between two: `Windows Firewall : / / API`. The name is the main page and the page's heading still; the one shown
is in the accent, on a line of it. 0.24.1's line and rising stroke under each tab are gone. The strokes are drawn, not
read out: a screen reader hears the tabs alone.

## 0.24.1 (2026-11-11)

A plugin's tabs as the user drew them ("tabs should look more like this \"Windows Firewall___/: API___/: MISC\""): the
plugin's own name is the first tab, its main page (and the page's heading still); then the others, in capitals. Each
tab is a label on a line that ends in a rising stroke, with a colon before every tab but the first; the one shown has
its line and stroke in the accent. 0.24.0's bordered buttons and the tab called Main are gone; the API tab says API
whether a plugin attaches to one or to several.

## 0.24.0 (2026-11-11)

Connections' sphere comes nearer and goes farther (the user: "i need to be able to zoom in and out the connections").
The wheel over the sphere, about the pointer (what is under it stays under it); a pinch of two fingers; − and + at the
head, with the sphere's measure between them, which is the way back to the whole sphere; the keys + and −, and 0 for
the whole sphere, when the picture has the focus. From half its size to six times. Nearer, a drag still turns the
sphere and Shift and a drag moves the picture; the parts grow a little with it, so their names stay readable; a part
picked comes to the middle of what is shown. What is outside the picture is cut off, not drawn over the page. The
wheel scrolls the page as before anywhere but over the sphere. The page's files alone changed: a platform already
running serves them at its next reload.

A plugin's tabs look like tabs (the user, of 0.22.0's two small grey words with a thin line under one: "also i don't
see tabs"): each a button with its own border and ground beside the title, the one shown filled in the accent.

## 0.23.0 (2026-11-11)

Connections is a sphere (the user: "for the #connections, lets treat the plugins like a peripheral interface, and have
them on the outer periphery, which is a sphere, objects insantiated using the plugin, orbit the plugin on the
peripheral, the login/platform object is at the center, logic and intermediary interfaces (abstractions) are on the
middle periphery, which talk to the plugins and the primary application (platform/integrator/charts)"). Three shells
round one centre. At the centre the platform, with its login and who asks it (this page, a program) close by. On the
middle periphery the library's interfaces the plugins are built on (`Firewall`, `WslDistribution`, `Admin`,
`MachinePlugin`, `AssistantPlugin`): `GET /api/traffic` names each plugin's (`interface`, the nearest class of its line
that liminal-libs defines; listed in `interfaces`), and what the platform or the login and a plugin say to each other
is drawn through the plugin's interface. On the outer periphery, a sphere, every plugin, those of one interface
together; the ones nothing was said to are drawn too, dimmed (`quiet` in the answer). Round a plugin, in orbit, what
was made or reached with it: the programs it ran, the hosts and apps it reached, the Docker instances it gives (what
the platform itself reached orbits the centre).

The sphere turns slowly by itself and is turned by a drag, a finger moved sideways or the arrow keys; it rests under
the pointer and while a part is picked, which is brought to the front, beside the centre. An interface picked lights
its plugins and what goes through it. The far side is fainter and its names are left out. Nothing moves by itself for a
reader who asked for reduced motion. The lines' classes, widths, movement and dots, the legend, Pause and the table are
as they were, and **Columns**, beside **Sphere** at the head, draws the picture as it was (the choice is kept in this
browser). A platform started before this release names no interfaces: its plugins are grouped as machine plugins and
AI assistants.

## 0.22.0 (2026-11-11)

A plugin's page has tabs, and its APIs a tab of their own (the user: "now i need tabs for the main page of each plugin,
each plugin has a tab for the API, and on the APIs organize each API description so that they can expand and contract
so they take up less space, kind of like the firewall"). Beside a plugin's title: **Main**, what its page showed until
now but the APIs, and **API** ("APIs" when it attaches to several), what it attaches to. The switches stay at the
right. The tab is in the address after the plugin's name (`#wsl-gentoo/api`), so a reload or a link keeps it; another
plugin picked opens on its Main; the machine plugins and the AI assistants have them alike, whatever their state. On
the API tab each API is one line with a round (+), as the firewall's groups have: its maker, name, form and version
and how much of it is used here; opened, its description, and its parts and its calls as two more such lines (the
library's folded cards, liminal-libs 1.50.0; with an older library the cards are drawn whole). Closed at first, but a
plugin's only API; what was opened stays open across the page's refreshes and in this browser. While the API tab is
shown the plugin is still asked at its interval, and only its cards are drawn again when what it learned changed, the
line or link that had the focus keeping it. The tabs are a list in the page's script (`TABS`), for the next one.

## 0.21.0 (2026-11-11)

The page shows at once and the plugins pop in as each answers (the user: "when starting platform there is a long pause
before anything is visible, there needs instead to be a way that all plugins pop in to existance after loading, and that
perhaps the main icon/page should show loading status"). The pause was not the start (under a second) but the page's
first question: it asked the whole status, which asks every plugin one after another, and drew nothing until the last
had answered (nine seconds on the user's PC with 22 machine plugins, the Windows firewall alone almost five). Now the
page asks `GET /api/overview` first, which asks no plugin anything: the app, this machine and every plugin by its name,
title and icon, enabled or not, hidden or not. It draws from that at once, every plugin in its place in the list,
dimmed, "loading"; then it asks each plugin for its status on its own, all at the same time (`GET /api/machines/NAME`,
and the new `GET /api/assistants` and `GET /api/docker` beside `GET /api/instances`), and each comes alive as its answer
arrives: its row in the list, its line in this machine's table, its icon popping into the tray. A slow plugin holds no
other back, and one picked before its answer is in says it is being asked. The loading status: a ring round the chip
(the platform's own icon) filling with the answers, its tooltip counting them, and a line at the list's head ("Loading
plugins: 7 of 27") while the page fills for the first time. When everything is asked again later (a switch thrown, a
setup ended) what the page holds stays as it is until each new answer comes, the chip's ring alone showing it; that
takes as long as the slowest plugin now, not as long as all of them together. The tray follows a plugin asked on its
own at once (it followed only a whole status, else a minute later). A platform started before this release has no
overview: the page asks it the whole status, as before. `GET /api/status` is as it was (the command line's status).
Nothing moves for a reader who asked for reduced motion.

## 0.20.1 (2026-11-11)

What the audit before any cloud key went in found here: a change asked of a plugin is logged by its name and how many
arguments it had, never their values. A private key pasted into a cloud plugin's SSH-key form had reached platform.log
before the plugin refused it. A disabled plugin is no longer asked what it learned of its APIs (its card is still drawn). The command line's status
and machine commands make a one-shot app (`PlatformApp.once`): a plugin they attach starts no background work of its
own (a cloud's account reads, a Dynamic DNS pass); serve's app is not one.

## 0.20.0 (2026-11-11)

Each plugin's page shows the API it attaches to (the user: "each plugin should reflect the the API its attached to, and
present links that provide documentation, the plugin interface should more or less contain what it already has, BUT, it
should also expose more of what the API is about"; liminal-libs 1.49.0, plugin API 2.2). After what the page already
shows, a card for each API the plugin declares: its maker, its form and version, the maker's pages as links (each in a
tab of its own: the documentation, the reference, the limits, pricing, the status page, changes, the specification, the
console), what the API is about, where it is reached, how a caller proves who it is, its limits and what costs money,
the day those facts were read, what the plugin learned of it while it ran, then the API's parts and calls: the ones the
plugin uses first, the rest behind "more of the API". The machines' and the AI assistants' JSON carry `apis`,
`apiFacts` and `pluginApi`; a plugin written for an older plugin API says it does not say yet what it attaches to. A
refresh draws the card again only when it changed, so a box opened stays open.

## 0.19.1 (2026-11-11)

A plugin not for this machine shows what it would do where it applies (the user: "the administration plugins don't seem to
work right especially linux which doesn't say anything about startup"): beside its reason, its own tables (the Linux admin
plugin's sections and the unit it installs at boot, liminal-libs 1.48.0 and plugin-platform-admin-linux 0.6.0), read
only: it is asked nothing here, so no button is drawn.

## 0.19.0 (2026-11-11)

A plugin's hook asked as a job, and a table's search box (for the Docker plugin's image search; the user: "lets roll in a
way to import docker images (from various docker repos) with a search that can find things like nginx webserver or
postfix secure file server w/ all the anti-spam+++").
- A plugin names the hooks the page may run as a job (`JOB_HOOKS`); a form with `job` is posted as one (`POST
  api/machines/<name>/job {action: "hook", hook, args}`): the hook runs in a thread with the job's output as its `log`,
  each line in the job's panel as it comes, its answer (or its refusal, in its own words) said at the end; the dialog
  closes onto the panel. Only a hook the page may ask and the plugin names; one job at a time per plugin.
- A status table's `search` ({form, field, value, placeholder}): its form's text field drawn above the table as a search
  box, the form's choices beside it, asked at once on Enter or Search (such a form changes nothing: its confirm is false),
  the plugin's word beside it; what is typed kept while the table is drawn again, the caret where it was.
- A form with nothing to fill and nothing to confirm (a row's Details) is asked as it opens.
- Mended with it: a job's thread starts before the busy check's lock is let go (two asks at once could start two jobs,
  installs and updates too); a hook job's answer is kept as JSON can say it (it is shown with the plugin's status); its
  panel is brought into view and keeps its title after a reload; its end draws that plugin's tables alone, the focus kept;
  a plugin page's refresh asked while another is shown leaves that one's timer alone (a search answered after you moved
  on had stopped it); the search box gives the keyboard back after a search, its last word goes with Clear, and only a
  form whose confirm is false is drawn as one.

## 0.18.1 (2026-11-10)

The open page keeps its login in touch (the user, of being signed out after ten quiet minutes: "Yes, fix both"). The
login app started for the platform ends once no page has been in touch with it for ten minutes (LIMINAL_QUIET_SECONDS),
and the platform's page was in touch only as it opened, so a reload or your account after that found you signed out
while you were using the platform. While a page is open, shown or not, it asks the login every minute whether you are
still signed in (`login/api/status`, passed on with your cookie), which keeps the login in touch; the login ends ten
minutes after the platform's last page closes. Signed out meanwhile (in another page, or the session over), or a login
that ended anyway and was started again (every session lost): the sign-in again; coming back to the page asks at once;
no answer (the platform stopped, or its login could not be started): asked again a minute later, the page left as it is.
On liminal-libs 1.46.1, whose sign-in covers the page by its file's own name too (a page opened at /index.html while
signed out would otherwise reload into itself every minute).
- Your account takes a theme chosen after it opened: painted again in place (it kept the theme it first opened in, and
  with the login drawing no colour of its own round it, liminal-login 0.15.3, the old theme showed inside the new);
  one not loaded yet and out of sight is made again when next opened.
- With liminal-login 0.15.3 the sign-in, your account and the charts' bound view show no box of the login's own round
  it, in every theme.

## 0.18.0 (2026-11-10)

The platform inherits the login app (the user: "we need to shift over to platform, but make sure that the platform
inherits the login app so we can login to platform"; "using secret user"), on liminal-libs 1.46.0:
- Its own login at LIMINAL_PLATFORM_LOGIN_URL (http://127.0.0.1:8796; "none": none), started for it when nothing
  answers, as its superclass: the platform's users apart from the charts app's (the login's folder `platform/`), the
  pairs the platform's plugins ask for asked of the platform.
- The page opens on the sign-in (the login app's page; type secret and click the lambda) until the browser is signed in;
  then the platform.
- The login's lambda after a divider at the rail's end: your account (who you are, your keys, the pairs the platform's
  plugins ask for, sign out) over the main area; the rail's own icons take you back. Signing out there brings the
  sign-in again.
- The tests never reach or start a login app (LIMINAL_PLATFORM_LOGIN_URL=none; one test plays it).

## 0.17.0 (2026-11-10)

Touch screens and the on-screen keyboard (the user: "let's do an update. I want to support touch as well as mouse
clicking on the interface ... We'll make sure it works across all apps"; "Support for virtual keyboard on tablets and
phones"), on liminal-libs 1.42.0's touch.js, which the page loads right after theme.js, and the viewport's
`interactive-widget=resizes-content` (Chrome on Android makes room above its keyboard). A mouse and a hardware keyboard
work as before. A long press on a plugin's icon in the tray opens its menu (Hide, Disable) on every device, an iPad's
too, through the library's menu, headed by the plugin's name; a long press on anything with a tooltip shows its words in
a bubble. On a touch screen the words no finger can hover are on the page: why a rule is in its group, under its name;
the note of the group picked in Move to, beside it; a disabled button's reason, beside it; what a tap on a row of a
table chosen from does, above it. A tap beside a rule's box chooses it, a box in Connections is picked anywhere in its
row, targets are about 40 px (liminal.css) with room between a row's buttons, and no hover highlight sticks after a tap.

The login terminal is kept alive across the page's redraws: its panel stays where it is and the page is drawn around it,
so a redraw never closes the keyboard nor drops a word being typed (nor scrolls the terminal back to its end); it stays
while this PC's check is asked again, and when the platform does not answer a refresh for a moment, which is said at the
head of the plugin's page rather than in place of it. Its lines keep following their end while the keyboard makes them
shorter (and while a phone's bars come and go): a scroll up lets the end go, a scroll back to it takes it again. On a
touch screen a row of the keys a phone's keyboard lacks sits under its lines: Esc, Tab, Ctrl (held for the next key: a
letter typed then is its control code, an arrow a word over), the four arrows, ^C, ^D and Paste (what is copied, read
through the clipboard, which a page on localhost may read once the browser allows it). An Android keyboard's typing
reaches the shell: the word it composes shows at the cursor until it is done, then is sent, and a key of the row sends
it first, as typed (Tab completes it; Ctrl applies to the next character, not to it); its Backspace always arrives (the
box keeps one unseen character to delete). A hardware keyboard's own composing (an IME, a dead key) shows nothing new. A
tap on the terminal brings the keyboard back, even after it was put away, and leaves it as it is while it is up (a word
being composed goes on); it lets go of a word pressed and held to copy; a pen's drag selects to copy as a mouse's does.
Opening or showing a terminal by a tap brings it into view without calling up the keyboard; on a touch screen the cursor
is kept in view sideways, and the head says "tap, then type; press and hold to copy" (beside the mouse's words on a
computer whose touch screen sits beside its mouse, alone on a phone or a tablet).

A plugin's form, opened by a tap, shows its heading first, so no keyboard covers the dialog before a field is tapped (a
mouse or a keyboard still finds the first field focused), and a field to fix after Review is brought into view rather
than focused. The dialog fits what the keyboard leaves (at the top of what is seen where the keyboard lies over the page,
as on an iPhone), the field typed in is kept in view with its label and note, and its buttons are held at its foot on a
phone or while the keyboard is up. Each field calls up its keyboard: a number its digits (with a minus where it may be
below 0), a text typed as it is (no capitals, no corrections), a secret kept out of password managers (no longer offered
a new password). A form's field may name its own with `keyboard`, one of the library's kinds its type takes: plain,
text, name, search, email, url, number, decimal, ticker, username or code for a text; number or signed for a number
(signed is a number's alone: its minus is the number field's keyboard's); secret, key or password for a password. The
keyboard's Enter says Next on every field shown but the last and moves there; the last one's sends the form, as Enter
does.

Below 700 px wide the panes are one column (liminal.css); here a plugin's head wraps, Connections' picture scrolls
sideways at a size its words can be read, and a terminal is at most 45% of the height. The library at 1.42.0 or later.

## 0.16.0 (2026-11-09)

The firewalls' System and Application grouped again (the user: "lets group by application under apps or system, try
best to organize under system and applications. Like system has 'core networking' or WSD or UPnP or RA Server or Remote
Assistance or network discovery or ... applications has like starcraft or edge"; "try to group the system by
'services'"; "also rules that are turned off should be shown as well"): an open System shows a heading per service (Core
Networking, Network Discovery, Remote Assistance...) and an open Application a heading per application (StarCraft II,
Microsoft Edge...). Each heading is indented under its group on a paler band, its title smaller than the group's, with
its own (+) to open it and (−) to close it, a box choosing every rule it lists, how many rules it holds and, when not
every one is listed, how many are. A heading is closed at first and kept open in this browser as a group is; while its
group lists 30 rules or fewer (after a Find, or a narrow choice of the rules shown) it is open at first, and one closed
then is kept closed in this browser. An open heading lists its rules under it, indented as it is; the group's rules with
no service or application follow the headings, flush with the group, a line above them. Rules moved into System or
Application open the heading they go under. A group's box still chooses every rule it lists, those under its headings
too; Other and the labels stay single lists, and Move to is as it was. A rule turned off is listed dimmed and says so,
over its name and to a screen reader; it is chosen and moved as any other. While the tables are drawn again every 30 s,
the focus stays on the (+), (−), box or Move to it was on, and this browser keeps up to 2000 groups and headings open
(200 before). The headings come with liminal-libs 1.41.0's firewall tables; a table without them is drawn as before.

## 0.15.0 (2026-11-09)

A plugin's settings as entries on its page (the user: "the namecheap plugin is very sparse, it should have entries for
login credentials api key etc.."): every setting a plugin declares (its keys: the Namecheap plugin's API user, API key,
account acted on, whitelisted address, sandbox, Dynamic DNS password, hosts and minutes; an AI assistant's key and
account) is a row under "Settings": its label and variable, set (✓), not set or optional, where to get it (its hint),
Enter… or Change… opening the settings dialog with that one field, and Forget… for one set (confirmed; it is removed
from where it is kept). All settings… opens them all at once, as Settings… did. A value is never shown back.

## 0.14.0 (2026-11-09)

Update packages among the tasks (the user: "move the update packages on to the TASK"): a task `{job: "update"}` draws the
packages' update button in the Task bar (busy while a job runs), its terminal panel titled by the install it updates;
the row above the installs keeps neither Update packages nor the terminal for a plugin with installs to choose from. The
update job of such a plugin (one with `chosen`) is not held back by its own install's check: it updates the one chosen
and says itself when that is not there.

## 0.13.0 (2026-11-09)

A table chosen from by a click on a row, its tasks above it (the user: "instead of chosen, put task and for the tasks lets
do terminal, start, pause, stop, allow selection of the linux install by clicking on the list"; "tasks also include
uninstall"): a table with `select` {hook, value} (liminal-libs 1.37.0: a WSL plugin's installs) draws its rows to click,
the chosen one marked, its name a button for the keyboard; a click asks the hook with the row's key and draws the plugin
again. Its `tasks` {title, subject, actions} sit above it: "Task  Ubuntu  Terminal  Start  Pause  Stop…  Uninstall…". A
button (an ask, a form's, the terminal's) is drawn `disabled` where its task does not apply now (Pause while stopped).

## 0.12.0 (2026-11-08)

The terminal into the install chosen (the user: "for the WSL plugins, they need to list all the 'operating systems' that
are installed under the plugin's regime"; "also the ability to uninstall and select which one to terminal in to";
"basically a selector for different installs"): a WSL plugin's status says which install its terminal opens into
(`terminalInto`: liminal-libs 1.36.0's selector), so its button says "Open a terminal in Ubuntu", and a table's action
`{terminal, title}` draws that button under the installs. Open while a terminal into another install is open, the page
closes that one and opens the chosen one's; the platform does the same when the plugin's terminal command changed
(`open_terminal` asks the plugin first), and titles it with the plugin's `terminal_title()` when it has one.

## 0.11.0 (2026-11-08)

A plugin's table in groups (the user: "for both firewalls, i need to have groups, like system or application and then
unassociated rules not tied to a specific application or system process can be in an other, i can create labels, like
system or application, as well and move the rules in to that"; "just use basic expansion like a (+) to open and close
labels"): a table with `groups` (liminal-libs 1.35.0's rulegroups: the firewall plugins' Rules) is drawn as a heading per
group (its title, how many rules, what it holds, a label's Rename… and Remove…) with (+) to open it and (−) to close it,
closed at first and kept open in this browser; a box to choose each rule, the heading's box choosing every rule the group
lists; under the table, Move to with the groups and labels and Its own group, asking the plugin's move hook with the
keys chosen. A rule moved shows where it came from; why a rule is in its group shows over its name. The choice, the
groups open and the group picked last hold while the tables are asked again every 30 s.
`LIMINAL_PLATFORM_LOGIN=memory`: a scratch preview's login, a copy of the process's environment keeping what the page
saves (a setting, a label) in the process alone, never the user's environment.

## 0.10.3 (2026-11-08)

The dock switch says just Visible or Hidden (the user: "the dock hidden visible switch literally needs to say hidden (not
lit) and visible (lit)"; "don't say 'from the dock'"; "just hidden / visible"): lit, the plugin's icon is on the right
(once it is active); not lit, hidden. The tray's right click offers Hide beside Disable; the log says "hidden" or
"visible".

## 0.10.2 (2026-11-08)

A hide switch beside enable (the user: "all plugins need a hide switch next to enable for the dock on the right"): on
every plugin's page, machine plugin or AI assistant, a second switch hides its icon from the dock on the right while the
plugin stays as it was (enabled or not, attached, asked); off, the icon is back in its place once the plugin is active.
The tray's right click offers Hide from the dock beside Disable. Kept in the platform's plugins.json beside the disabled
ones (`hidden`); `POST /api/plugins/<name>/hidden {on}` answers with the tray as it is now; each status says `hidden`.
The dock now holds the active AI assistants too, after the machine plugins, each by its maker's mark.

## 0.10.1 (2026-11-08)

Each plugin by its maker's mark (the user: "for the AI icons, lets use the respective mascot/icon from the business,
logo, etc.."; and for the WSL distributions, the firewalls, Namecheap, Docker, Kubernetes, LXD and Hyper-V the same): the
AI assistants are drawn with their own icons (`icon` in their status, from the plugin's ICON; the chart when one has
none) in the list, on their page and in Connections, as the machine plugins were. The marks themselves are liminal-libs
1.33.0's icons. Needs liminal-libs>=1.33.0.

## 0.10.0 (2026-11-08)

Connections (the user: "the root plugin (platform) will need to visually illustrate how plugins are connected to each
other or to the main app/plugin/icon via IPC, all requests and interactions should be classified and give the user a
way to understand how the app and it's plugins communicate, visually"): a view of its own under This machine, drawing
who talks to whom as it happens. On the left who asks the platform (this page, a program); in the middle the platform
and its login; its plugins (each in its state); on the right what they reach (programs, hosts, the framework's other
apps on this machine). A line for each link and class (read, change, ask, stream, attach, login, process, network) in
the class's colour, its width how often; it moves while it carried something in the last seconds and a dot runs along
it for each new interaction (still, with reduced motion). A box picked shows its own links and rows (Its page opens a
plugin's); the legend's classes switch off and on; Pause holds the picture. The latest interactions under it, the same
one said again within 30 s one row, counted, with how long each took and whether it failed. Never a value: a setting by
its name, no hook's arguments, a program by its name alone, a host by its name and port.

- `GET /api/traffic` (liminal-libs 1.32.0's `App.connections`): every platform plugin in its state, attached or not;
  one disabled or not valid that nothing was said to is left out and named in `hidden`.
- Noted: the page's requests in their class (a terminal's and a job's output streams, a hook asked by name an ask), each
  plugin's presence, status, check, validity and hooks asked (the reads apart), a setup started and ended, a
  terminal opened, typed into and closed, a command run, what the platform and each plugin read and keep through the
  login (each plugin lent a login noting it: `TRACE_LOGIN`), the programs and hosts the platform and its plugins reach
  (`WATCH_OUTSIDE`: one audit hook, the calling code naming who).
- Needs liminal-libs>=1.32.0.

## 0.9.0 (2026-11-08)

A plugin's settings entered on its page (the user: "i need a way to put my credentials in to the namecheap plugin and
allow it to function"): **Settings…** on a plugin's page (a machine plugin, valid or not yet; an AI assistant) asks for
each key it declares (KeyVar), a secret typed hidden; a field left empty keeps its value and no value is ever shown
back or logged. `POST /api/plugins/<name>/settings {values, forget}` keeps them through the platform's login
(liminal-libs 1.31.0's `Login.save`: the user's environment variables until the login app holds them), only the
plugin's own keys, then tells the plugin (`settings_changed`, when it has one); `GET /api/machines/<name>` says each
setting set or not. The platform's login reads the variables saved after it started too (`EnvironmentLogin(saved=
saved_variables)`), and is lent to a plugin not yet attached, so its settings make it valid. An assistant's missing key
now points to its Settings.

## 0.8.0 (2026-11-08)

A plugin's paths (the user, on the hw-stats plugin's port checks: "the check needs to validate the computer, the
router/gateway to the computer, then the internet to the computer, and graphically show traffic moving between the
three different checks"): a plugin's status may hold `paths`, each its hops in a row (`nodes`: id, title, sub, state)
and the links between them (`links`: from, to, title, state), drawn as a picture: the internet a globe, a router a box
with its antennas, a computer a screen; each in its state (idle, checking, done, ok, warn, fail, unknown) in the
theme's colours. Traffic moves along a link being checked (and, slower, one it got through); a link that stopped it
is crossed; beneath, the conclusion (`said`) and what each hop showed (`lines`). A path is drawn again only when it
changed, so the moving traffic is not restarted by every refresh, and the plugin is asked again every second while a
path is checked (`running`). Moving traffic stays still for those who ask for reduced motion.
A confirmation's title fills its `{field}`s too ("Check the way in to port 8795?").

## 0.7.0 (2026-11-08)

A table's own choices and buttons (the user, on the hw-stats plugin's Ports table: "there needs to be a refresh button
and port selector for PORTS"): a plugin table's `options` (a choice group, as status.options: a hook asked with the
value chosen) are drawn above its rows, and its `actions` may ask a hook by name (`{hook, args, title, note}`, as
status.actions) beside the buttons opening forms. A form whose `confirm` is false changes nothing on the machine (the
ports a table lists): it is asked as soon as it is filled. One choice-group and one ask-button maker serve the plugin's
own options and actions and its tables'.

## 0.6.0 (2026-11-08)

A plugin's forms: its status's `forms` are drawn as forms for one of its hooks, so the page can change what a plugin
manages with a confirmation instead of the command line (the Namecheap plugin's records set and removed:
plugin-platform-namecheap 0.2.0). A form names the hook, its fields in the order of the hook's arguments (a label,
text, a number, a choice with its notes, a fixed value, a default, a field shown only for some choices) and the words of
its confirmation. A button opens it: one of the actions, a button under a table (a table's `actions`), or a button in a
row's cell (`{form, title, values}`, the values filling its fields: a row's Remove). The page's one dialog holds the
form, then the confirmation naming the exact change (the plugin's words with the values filled in, and each value by its
label), then the plugin's answer in words (`said`, `lines`, a fault when `ok` is false); a refusal or a failure is said
in the plugin's own words. A form with nothing to fill goes straight to its confirmation. The dialog sits outside what
is drawn again, so the tables asked every 30 s leave what is typed as it is; a table button focused is focused again
after they are drawn. A plugin table's long words (a DKIM record's host name, a long address) wrap in their cells, so a
row's buttons stay in the column instead of behind a sideways scroll.

A refusal can name the argument that accepts it (the exception's `accept`; the error answer of `POST
api/machines/<name>/ask` carries it, and the plugin's own `words`, since this release): when the form has that argument
as a field of type accept, the page offers it as a second, explicit confirmation (the field's own words) that sends the
same arguments with it true, never before (the Namecheap plugin's `accept_ddns_reset`, for zones with Dynamic DNS hosts).
An acceptance holds for the one change confirmed: a change made again (Back, Change it) is asked to be accepted again.

## 0.5.0 (2026-11-08)

A plugin's actions: its status's `actions` ({hook, args, title, note}) are drawn as buttons at the head of its page, each
asking one of its hooks by name with its arguments, as a table's buttons do (the Namecheap plugin's Refresh and Update DNS
now: plugin-platform-namecheap 0.1.0). Only the actions the platform may ask of it now are drawn. A button asked is busy
until the answer comes (a plugin's action may take seconds), then the page is drawn again; a refusal shows at the head
of the page and the button is free again.

## 0.4.3 (2026-11-08)

A shown plugin's tables are asked again every 30 s while it is on the page (the user: "Yes, do it" to the page
refreshing a WSL distribution's services table on its own): a WSL plugin's services (also while its distribution is
stopped, so the table shows once it runs), an admin's services and startups, a firewall's rules. Only the tables are
drawn again: a terminal or a job's panel beside them is left as it is. The day's figures are asked of a charted plugin
only. Nothing is asked while the page is hidden.

## 0.4.2 (2026-11-08)

A plugin not for this machine at all (its status says `applies` False: Linux administration on Windows or in WSL; the
user: "the scope of linux administration is only on native linux O/S") is shown as such: disabled, "Not for this
machine" and its reason on its page, in the list, in this machine's table and on its switch, and no setup offered,
since none can make it valid here. A plugin not valid yet keeps its setup or install as before.

## 0.4.1 (2026-11-08)

The terminal's typing (the user: "in the terminal, characters repeat"; "the character entry is not great for the term"):
the page keeps one read open, held by the platform until the shell prints (`?wait=`, at most five seconds), so the echo
shows at once and nothing is drawn twice (two reads at once had drawn the same output twice); the keys go through a
hidden text box, as web terminals do, so composed characters, other layouts and a paste arrive whole; a terminal open
again shows its last lines. A job's panel is read the same way.

## 0.4.0 (2026-11-07)

A plugin that installs a system shows its check of this PC and unlocks the install only when every criterion is met (the
user: "each plugin should have a scheme for checking the environment to see if it supports installing the operating system
it has in its name, if the criteria are met according to the O/S, then the install method should be not locked out"):
`GET /api/machines/<name>/check`, the page's list of criteria with Install and Check again; the setup's own install steps
locked the same way, the steps that prepare this PC (wsl, update, version) never. A job (the install, a step, the
packages' update) pops up a terminal panel that shows what it prints as it comes ("after the install is run a terminal
pops up in the plugin and shows the install progress"): `POST /api/machines/<name>/job {action: install|update}`, `GET
/api/machines/<name>/job?since=N`. Once installed, Update packages ("the user can use the plugin to update the
environment's packages") and Open a terminal ("the plugin also allows for a user to login through a terminal in to the
environment"): `POST /api/machines/<name>/terminal`, its `input` and `close`, `GET ...?since=N`; a terminal no page reads
for two minutes is closed. `terminal.js` draws a shell's output (colours, progress lines, readline's editing) and sends
the keys typed.

## 0.3.0 (2026-11-07)

A plugin not in a valid state is disabled until it is (the user: "if a plugin is not in a valid state it has to be
disabled, and thus shaded out on the left side"; "there are no WSL-liminally scoped installs, so all three WSL plugins
are invalid"; "only hardware stats and preferences seem valid atm"): its state is active, disabled (the user's) or
invalid, with why (the plugin's own word, liminal-libs 1.24.0, else not present); not valid, it is shaded in the list,
out of the tray, detached, offered no asks, its switch held off with the reason; its setup stays, being what makes it
valid, and it is active again by itself once valid. The AI assistants have the switch too ("theres also no disable or
enable on the AI assistants"): valid with a key set and a plan with API access, attached while active; `POST
/api/plugins/<name>/enabled` for any platform plugin.

## 0.2.2 (2026-11-07)

A plugin disabled or enabled shows at once in every view: the tray, this machine's table and its lists, the list on
the left, the plugin's page and switch (the user: "when i right click disable on icon menu it doesn't reflect in 'this
machine' state or plugin on/off": the page waited for every plugin's status, 5 to 8 s, and a refresh of the shown
plugin asked before the change could bring the old state back). The platform's answer for the plugin follows, then
the rest; answers asked before a change are dropped. The tray's list follows a change without asking every plugin
again. A disabled plugin is shaded darker in the list ("on the left hand side, shade darker the plugins that are not
enabled"), brighter while pointed at, focused or selected.

## 0.2.1 (2026-11-07)

A theme chosen is applied to the page at once (it waited for every plugin's status, 5 to 8 s with the WSL plugins);
the choice shows at once; each choice has its name for a screen reader. A platform that stopped answering is said in
words ("The platform is not answering ...") rather than the browser's "Failed to fetch" (the user, 2026-11-07:
"says failed to fetch when i click on a theme": the preview had been stopped under the open page).

## 0.2.0 (2026-11-07)

A plugin disabled and enabled (the user: "allow me to right click on the icons to disable them on the right icon
menu, also allow for enable disable switch (left to right) on the plugin description when selected in the left
menu"): a right click on a plugin's icon in the tray offers Disable (the library's menu.js), and a switch at the
head of its page enables or disables it. Disabled, the platform asks it nothing, runs nothing on it, leaves its
icon out of the tray and detaches it (a plugin that samples stops); kept in the platform's folder
(LIMINAL_PLATFORM_DIR, else the data folder's platform/, `plugins.json`) across restarts. `POST
/api/machines/<name>/enabled {on}`, `liminal-platform machine NAME enable|disable`. A plugin's own figures drawn
in the middle: its status's `charts` (the library's charts.js, asked again at its interval while shown, the last
ten minutes or the last day), `tables` and `options` (choices, such as the Preferences plugin's themes). Every
page painted in the UI's theme (the library's theme.js, `GET /api/ui`). Asks that only read are not logged.

## 0.1.2 (2026-11-07)

The page as the user laid it out: "the specifics are on the right hand side before the icons on the very
right, and the larger window from the left to right is used to describe or display data"; "plugins are
better described as a list of details w/ the specifics in the right hand column, just like the charts had a
right hand column"; "active plugins, will be part of the tray on the very right side"; "use the black
boundary (around the icon) to serve as the tray border, it can stretch vertically to include more icons or
plugins". The list (this machine, its machine plugins, the AI assistants) | the selected one's data (the
plugins table and the Docker instances; a plugin's rules, services, startups, processes and setup log) | its
specifics (its state, facts and setup steps) | the tray: the chip, a divider, an icon per active plugin, in
the one box (`items()`: the machine plugins present, asked once a minute; `/api/tray`). The selection is the
address's `#name`. `/api/status` adds `active`, `assistants` and each plugin's `icon`. liminal-libs 1.21.0
(the shared three-column layout, the shield, wrench and terminal icons).

## 0.1.1 (2026-11-07)

The page takes each machine plugin as it is (the firewall and admin plugins next to the WSL ones): its own
setup steps (`steps`) and one-line `summary`; its tables, Liminal's rules (a firewall), the services, the
startups and the processes (the admin), with buttons asking the plugin by name: remove a rule, start, stop
or restart a service, start an app at logon, run, end or remove its startup. `POST /api/machines/<name>/ask`
(`{"hook", "args"}`): one of the plugin's hooks (`asks`: what its interface lists but the setup, the
settings, the scan and a command), its answer as JSON. The library at 1.20.1 or later.

## 0.1.0 (2026-11-07)

The first release: the platform app of the frame (the chip icon, port 8775): the machine's facts, Docker on
this machine, the machine plugins with their status and their setup from the page (a thread, its lines as
they come) or the command line, a command on one, the Docker instances, the platform plugins attached.
The library at 1.19.0 or later.
