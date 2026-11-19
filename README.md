# liminal-platform

The Liminal platform app: the interface to the software and hardware under the framework (the user,
2026-11-07: "basically the platform is the interface for the software/hardware which facilitates the liminal
framework"; "it also has an icon just like the chart/login and integrator"). An app of the frame
(`liminal_libs.apps.App`) with the chip icon at port 8775 (`LIMINAL_PLATFORM_PORT`).

## What its page shows

- The machine: system, processor, memory, Python, and Docker on this machine (or why not, and whether WSL 2 is
  there).
- The machine plugins (`liminal_libs.machines.MachinePlugin`: plugin-platform-wsl-ubuntu, -fedora, -gentoo),
  each with its status, Docker inside, and buttons to set it up, everything or one step, the setup's lines
  arriving as it runs.
- The Docker instances the framework may use (`liminal_libs.docker.instances`): this machine's, its contexts,
  the machine plugins' engines.
- The platform plugins attached (the machines and the AI assistants).

The list on the left has a heading for each kind of plugin, in this order: Machine plugins, Virtualization plugins,
OS plugins and Cloud plugins (a machine plugin's own `SECTION`; each is drawn when it has plugins), then AI plugins
(the user, 2026-11-16: "they will be classified as AI plugins"). Under AI plugins are four groups: Proprietary
services (the AI assistants, a vendor's service each: "the other plugins are strictly proprietary service plugins"),
Inference (the machine plugins that serve local models: llama.cpp, Ollama, vLLM), Harnesses (those that set up a
coding harness to work with a model server: OpenCode, Aider, Continue) and, from 0.34.0, Protocols (the user,
2026-11-18: "basically a protocol plugin that mediates MCP connections to resources by local AI agents": MCP's
first). A machine plugin is drawn in one of the last three when its `SECTION` is `"ai"` and its `GROUP` is
`"inference"`, `"harness"` or `"protocol"`; one that names another group, like one that names a section the platform
does not draw, is listed under Machine plugins. In the tray the machine plugins come first, then the assistants, then
the inference plugins, the harnesses and the protocols, so the AI plugins' icons sit together.

Plugins can be disabled: a right click on a plugin's icon in the tray offers Disable, and the switch at the head
of a plugin's page enables or disables it (disabled: asked nothing, out of the tray, detached; kept in the
platform's folder, `plugins.json`). A plugin that installs a system (the WSL plugins) shows its check of this PC; its Install unlocks only when every
criterion is met, and the install's output shows in a terminal panel as it runs. Once installed, the plugin updates its
packages and opens a login terminal into it, on the page.

A plugin not in a valid state (set up for Liminal: a WSL plugin with its own Liminal-named distribution, a firewall
with Liminal's rules, an admin with the rights; an AI assistant with a key and a plan with API access) is disabled
until it is: shaded, out of the tray, its switch held off with the reason, its setup still there. A plugin's own
charts, tables and choices are drawn in the middle (the
hardware stats' charts and tables; the Preferences plugin's themes), and every page is painted in the UI's
theme (the library's `theme.js`, the data folder's `ui.json`).

## A plugin's page and its tabs

Beside a plugin's title, its tabs (the user, 2026-11-16: "for all apps, and all plugins, there should be an external
api tab, and an internal api tab, the internal api is for interfaces the plugin shares with the rest of the app, the
external should be all the SDKs/APIs the plugin associates with"):

- **Main**: what it shows: its settings, actions, choices, charts, tables, forms and setup.
- **External API**: the SDKs and APIs it associates with, what it sits on (its `apis`: the plugin API 2.2 cards), each
  a line that opens to its description, drawn by the library's `apis.js`. It was the API tab.
- **Internal API**: what it shares with the rest of the app, made by the library from the plugin itself
  (`liminal_libs.internal`) and drawn by the library's `internal.js`: the kind of middleware it is (the library base it
  is built on, and so the standard interface it implements), the standard hooks it answers and those it leaves to the
  contract's defaults, then its own, each with its arguments, its line, whether it only reads and who uses it (the
  platform's code, other plugins, its page); how the platform asks it; the settings it reads through the login; and
  what it asks of other plugins. What it says to whom as it happens is Connections'.
- Then its own tabs (its `TABS`: a firewall's World Wide Web and Netstat, eBPF's Compare and Functions), each asked
  every few seconds while it is shown. A firewall's globe draws its internet infrastructure layers (0.33.0, with
  liminal-libs 1.65.0): the page asks the plugin the hook the globe names (`world_layer`) with a layer's id, once a
  layer's version, and remembers the layers' switches in this browser under the plugin's name and the tab's. A table
  of connections (Netstat's) draws Since as the plugin sends it, and Flagged only only where its filters name it.

The tab is in the address after the plugin's name, so a reload or a link keeps it: `#name` (Main), `#name/external`,
`#name/internal`, `#name/<id>`. An address that names the old API tab (`#name/api`) opens External API and is written
again as `#name/external`; no plugin's own tab takes these ids, nor `api`.

The platform's own two views are an entry under This machine, beside Connections and Codebase: External API (`#app`),
what the platform's own code calls that Liminal does not make (the commands it runs, the system interfaces it reads and
the signals `serve` takes, declared in `apis.py`), and Internal API (`#app/internal`), what its code calls on its
plugins and what it offers them and other apps, its routes, the login it includes, its plugins and what a job's hook is
handed. Both come from `GET /api/app/apis`, asked while the entry is shown.

The page is read from the checkout at each request, so it draws with what a running platform has: with a liminal-libs
that has no `internal.js`, Main and External API and no entry of its own; with a platform process started before these
views (no `internal` in its statuses, no `GET /api/app/apis`), the Internal API tab and the entry say to restart it.
A platform whose liminal-libs cannot read one plugin says so on that plugin's Internal API tab instead (its status's
`internalError`; why is in the platform's log), since a restart would not mend it.

## Run

```
pip install -e .
liminal-platform                          # the page at http://127.0.0.1:8775/
liminal-platform serve --no-browser --until-quiet
liminal-platform status
liminal-platform machine wsl-ubuntu status
liminal-platform machine wsl-ubuntu setup            # everything; or: setup docker engine user
liminal-platform machine wsl-ubuntu run -- docker ps
```

## The API

Its own routes, each listed with what it is in `routes.py` (`ROUTES`, held to the code by `tests/test_routes.py`) and
shown on its own Internal API view:

- `GET /api/status` (everything at once, for a client: every plugin asked, one after another), `GET /api/overview`
  (what the page draws at once: no plugin asked), `GET /api/assistants`, `GET /api/docker`, `GET /api/machines`,
  `GET /api/instances`.
- `POST /api/plugins/<name>/settings` (its settings kept through the login), `/enabled` and `/hidden` (`{"on": ...}`).
- `GET /api/machines/<name>` (its status; it and the plugin's row in the overview say its `section` and its `group`,
  the group empty outside AI plugins), `GET /api/machines/<name>/check` (its check of this machine).
- `POST /api/machines/<name>/setup` (`{"steps": [...]}`, 202; `GET` the same path for the lines and the result) and
  `POST /api/machines/<name>/job` (`{"action": "hook", "hook": ..., "args": [...]}`: one of the hooks the plugin
  names in its `JOB_HOOKS`, run as a job, 202; `{"action": "install"}` or `"update"` for a plugin that installs a
  system; `GET` the same path with `?since=&wait=` for the job's lines as they come and its end).
- `POST /api/machines/<name>/job/cancel` (the job under way asked to stop, 202 with its state: only a job whose hook
  the plugin names in its `CANCEL_HOOKS`, which looks at the request between its steps and ends by itself;
  `{"startedAt": ...}`, optional, names the job meant by its state's own `startedAt`, a number; 409 when the plugin
  runs no job, when the job named has ended and another runs, and when the job's work ends as it is asked; 400 for a
  job that runs to its end, with a liminal-libs older than 1.62.0, and for a `startedAt` that is no number).
- `POST /api/machines/<name>/ask` (`{"hook": ..., "args": [...]}`: one of a plugin's hooks by name, its arguments by
  position; a refusal answers 400 and a failure 502, with the plugin's own `words` and, for a refusal that names the
  argument accepting it, `accept`), `POST /api/machines/<name>/enabled`, `POST /api/machines/<name>/run`
  (`{"command": [...]}`: a client's, never the page's).
- `POST /api/machines/<name>/terminal`, `GET` the same path (its output), `POST .../terminal/input` and
  `.../terminal/close`: its login terminal.
- `POST`, `GET` and `DELETE /api/machines/<name>/rpc` (0.34.0): an agent's request, on the platform's own port, for a
  plugin whose `RPC_HOOK` names one of the hooks it answers (liminal-libs 1.66.0's `ProtocolPlugin`: `rpc`; the MCP
  plugin's endpoint is `/api/machines/mcp/rpc`). The hook is handed the request whole: its method; the headers of the
  route's allow-list, named in lowercase (`authorization`, `mcp-session-id`, `mcp-protocol-version`, `mcp-method`,
  `mcp-name`, `accept`, `content-type`, `user-agent`, `last-event-id`, and up to 16 `mcp-param-*`), each at most 4,096
  characters, a header sent twice as its values joined by `, `; its JSON body (none for a GET, `{}` for a write that
  sends none); and `gone()`, whether the agent has closed its connection, read without waiting (a select, poll where
  the system has it, then a one-byte peek). No other header is handed over: not the cookie, not the write header. Its
  answer is sent as it is: a status
  from 200 to 599, a JSON object or nothing (a 202 or a 204 with no body at all), and of its headers `Mcp-Session-Id`,
  `MCP-Protocol-Version`, `WWW-Authenticate`, `Allow` and `Retry-After` alone, each one line of plain text. Refused:
  404 for a plugin with no such hook, 409 while it is disabled, 503 while the platform stops, 431 past the headers'
  bounds, 400 for a body holding NaN or Infinity (Python's reader takes them, JSON has neither, and an answer echoing
  the request's id would hold them), 502 for a hook that fails or answers what cannot be sent (its words kept out: a
  request's may hold its token). What cannot be sent: a body that is not JSON, a 204 with a body, a 205 or a 304. The
  agent always reads an answer: such a body once left it none, the frame's send failing after the route returned.
  The frame's checks come first, as for every route: this machine only, no other site's page, the write header
  on a POST and a DELETE, a JSON object of at most 5 MB. The hook is never asked by name and never offered to the page.
  The request is no one's ask (neither the page's nor a plugin's): the plugin finds the agent by its token. It is not
  counted as under way, so a call it holds for your answer never holds up the stop (the plugin's `app_stopping` ends
  it), and it leaves no line in the platform's log: the plugin notes each request itself. The frame notes it in
  Connections as a program's request to the platform, and the plugin as its agent's.

Who may ask a hook (0.34.0, liminal-libs 1.66.0's `PLUGIN_ONLY_HOOKS`, `PAGE_ONLY_HOOKS` and `apps/asking.py`). The
asker is handed over in so many words, never taken from what a thread inherits: the page, for `POST .../ask` and
`.../job` (inside the job's own thread too, as the job records it where it is started); the plugin that asks, for its
`app.ask` through the platform, as the platform names it (never an argument; one that took the name `page` asks as no
one); no one otherwise.

- A hook a plugin's `PLUGIN_ONLY_HOOKS` names (the MCP plugin's: an agent for a harness, a token for its window) is
  asked only by another plugin: over HTTP it is refused (403), and its page is never offered it (it is left out of the
  status's `asks`, as the setup and the command are). Its own plugin asking it is refused too. The word only narrows
  who asks: a hook the platform asks by no name (its setup, its settings, a scan, a command, the route's hook) stays
  refused to every plugin, even when the word names it.
- A hook its `PAGE_ONLY_HOOKS` names (the MCP plugin's decisions) is asked only from its page: a plugin's ask of it is
  refused (403), and noted in Connections as an ask that failed. Over HTTP it is asked when the login says you are
  there (`App.present`: today, a browser signed in to the platform's login), refused (401) when it says you are not,
  and asked when the platform holds no login. A signed-in session can be opened by any program that signs in as the
  passwordless user: it is a speed bump, not a proof. The proof the user picks later takes its place there.
- A plugin whose words cannot be read is asked nothing by name. A plugin that says neither word is asked as before, and
  the login is asked nothing for it.
- With a liminal-libs before 1.66.0 the platform reads the two words from the plugin itself and holds them the same;
  there is no proof to ask, and no asker is handed to a plugin's hook.

Each machine plugin's and AI assistant's status carries its External API (`pluginApi`, `apis`, `apiFacts`) and its
Internal API (`internal`; `null`, with `internalError` in words, when the library could not read it). Beside these,
the frame's: `/api/tray`, `/api/app`, `/api/plugins`, `/api/interface`, `/api/login/pairs`, `/api/traffic`,
`/api/codebase`, `/api/ui`, and `GET /api/app/apis`: the platform's own External and Internal API (`{"app",
"internal", "apis", "apiFacts"}`), or with `?plugin=<name>` an attached plugin's (`{"name", "internal", "apis",
"apiFacts"}`). Writes carry the write header (`X-Liminal-Charts: 1`), as in every Liminal app; only this machine is
answered (the platform listens on 127.0.0.1), and of web pages only its own.

A job's state says `startedAt`, `cancels` (it can be asked to stop), `cancelling` (it was asked) and `cancelled` (it
had been asked when its work ended, and it has ended). The page shows a Cancel button in the job's panel while a job
that `cancels` runs: one click, no dialog, the job named by its `startedAt`, so a Cancel from a page not told yet that
its job has ended never stops the next one; what the job had done so far is its plugin's to keep for the next try. A
job begun at another time than the one a panel follows (that one ended, then another began) gets a panel of its own.

An ask is logged by the hook's name and how many arguments it was given, never their values; a plugin's reads are not
logged at all (`present`, `status`, `view`, `charts`, `instances`, `wanted`, `services`, `startups`, `processes`, its
tabs' hooks, from 0.31.0 `serving`: what a model server offers the other AI plugins, and from 0.33.0 `world_layer`:
one infrastructure layer of a firewall's globe, read back from this machine's files). From 0.32.0, with
liminal-libs 1.63.0, so are the hooks a plugin names in its `READ_HOOKS` that it answers itself and that are not
its jobs: noted as reads in Connections, and drawn as reads on its Internal API tab. A plugin asking another
through the platform (`app.ask`) is noted in Connections as the one asking.

## When the platform stops

It stops at Ctrl+C, when `--until-quiet` finds no page in touch for ten minutes, and (0.31.0) on POSIX at SIGTERM (a
service's stop, `kill`) and SIGHUP (its terminal closed: its output is let go first, its log keeps the rest), which
`serve` takes as Ctrl+C; a signal it was started with ignored (nohup) is left as it was. From then on nothing new is
begun: an ask, a job, a login terminal and a command answer 503 ("the platform is stopping"). A job that `cancels` is
asked to stop, and those jobs and what was under way (an ask: a Start clicked as it stops; a login terminal being
opened, which is closed once made; a command) are waited for, 5 s (`STOP_WAIT_S`) at most in all. Then each machine
plugin that has an `app_stopping()` is told, one after another in the registry's order, enabled or not, attached or
not; one that raises is logged and the rest are still told (liminal-libs 1.62.0's AI plugins stop there the servers a
click started). An ordinary end stops twice (the serve's own stop, then the command's), so the hook bears a second
call. Disabling a plugin detaches it, as before; it is told at the platform's stop all the same.

## What a plugin's status may hold for the page

Beside its summary and facts: `tables` (a title, the columns, the rows), `charts`, `options` (choices), `actions`
(buttons asking a hook by name) and `forms` (0.6.0): a hook asked with what the user fills in, once the user has
confirmed the exact change.

```
{"id": "set:example.com", "hook": "set_record", "title": "Set a record in example.com",
 "fields": [{"name": "domain", "label": "Domain", "type": "fixed", "value": "example.com"},
            {"name": "host", "label": "Host", "type": "text", "required": true, "placeholder": "@, www, home"},
            {"name": "rtype", "label": "Type", "type": "choice", "value": "A",
             "choices": [{"value": "A", "title": "A", "note": "an IPv4 address"}]},
            {"name": "ttl", "label": "TTL", "type": "number", "min": 60, "max": 60000, "empty": "1800"},
            {"name": "mx", "label": "MX preference", "type": "number", "when": {"rtype": ["MX"]}},
            {"name": "accept_ddns_reset", "type": "accept", "title": "Write anyway?", "words": "...", "yes": "Write anyway"}],
 "confirm": {"title": "Set this record?", "words": "{host} {rtype} is set in {domain}; a backup first", "yes": "Set it"}}
```

The fields are the hook's arguments in order (one whose `when` is unmet, or left empty, is sent as null: the hook's
default). A button names a form: an action `{"form": id, "title": ...}`, a table's `actions` (buttons under it), or a
cell `{"form": id, "title": "Remove", "values": {...}, "label": ...}` whose values fill the fields by name. A form with
nothing to fill goes straight to its confirmation. The answer is said by its `said` and `lines` (a fault when `ok` is
false). A field of type accept is false unless the hook refuses naming it (`accept`), when the page asks a second,
explicit confirmation with the field's words and sends the same arguments with it true. What a plugin says is drawn
as text, never as markup; from 0.34.0 an answer's lines and a refusal's words keep every space and line they have, so
a call waiting for your answer shows its arguments exactly (the MCP plugin's Open…, its waiting_call), and so does the
second confirmation of a call whose rule asks twice.

A field of type password (a Linux plugin's sudo password; a key) is typed hidden and never shown (0.31.0): the
confirmation lists it as "(given)", also while what was sent is answered; it is never put back in its field when the
form is drawn again (Back, Change it); and the page lets go of it once it is asked or the dialog closes. So a second
confirmation has it typed again, and the hook is given it anew with its accept argument. It is sent as typed, its
leading and trailing spaces kept (sudo is handed the line as it is); spaces alone are none. A key typed in one is
trimmed where it is kept (the settings' route; the library's `keys.clean`). The platform keeps nothing of a hook's
arguments once its job has run.
