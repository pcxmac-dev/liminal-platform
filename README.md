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
(the user, 2026-11-16: "they will be classified as AI plugins"). Under AI plugins are three groups: Proprietary
services (the AI assistants, a vendor's service each: "the other plugins are strictly proprietary service plugins"),
Inference (the machine plugins that serve local models: llama.cpp, Ollama, vLLM) and Harnesses (those that set up a
coding harness to work with a model server: OpenCode, Aider, Continue). A machine plugin is drawn in one of the last
two when its `SECTION` is `"ai"` and its `GROUP` is `"inference"` or `"harness"`; one that names another group, like
one that names a section the platform does not draw, is listed under Machine plugins. In the tray the machine plugins
come first, then the assistants, then the inference plugins and the harnesses, so the AI plugins' icons sit together.

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

`GET /api/status`, `GET /api/overview` (what the page draws at once: no plugin asked), `GET /api/assistants`,
`GET /api/docker`, `GET /api/machines`, `GET /api/machines/<name>` (a plugin's status; it and the plugin's row in
the overview say its `section` and its `group`, the group empty outside AI plugins), `POST /api/machines/<name>/setup`
(`{"steps": [...]}`, 202; `GET` the same path for the lines and the result), `POST /api/machines/<name>/run`
(`{"command": [...]}`), `POST /api/machines/<name>/ask` (`{"hook": ..., "args": [...]}`: one of a plugin's hooks by
name; a refusal answers 400 and a failure 502, with the plugin's own `words` and, for a refusal that names the argument
accepting it, `accept`), `POST /api/machines/<name>/job` (`{"action": "hook", "hook": ..., "args": [...]}`: one of
the hooks the plugin names in its `JOB_HOOKS`, run as a job, 202; `{"action": "install"}` or `"update"` for a plugin
that installs a system; `GET` the same path with `since` and `wait` for the job's lines as they come and its end),
`POST /api/machines/<name>/job/cancel` (the job under way asked to stop, 202 with its state: only a job whose hook
the plugin names in its `CANCEL_HOOKS`, which looks at the request between its steps and ends by itself;
`{"startedAt": ...}`, optional, names the job meant by its state's own `startedAt`, a number; 409 when the plugin runs
no job, when the job named has ended and another runs, and when the job's work ends as it is asked; 400 for a job that
runs to its end, with a liminal-libs older than 1.62.0, and for a `startedAt` that is no number), `GET /api/instances`,
and the frame's `/api/tray`, `/api/app`, `/api/plugins`, `/api/interface`. Writes carry the write header, as in every
Liminal app; only this machine's pages are answered.

A job's state says `startedAt`, `cancels` (it can be asked to stop), `cancelling` (it was asked) and `cancelled` (it
had been asked when its work ended, and it has ended). The page shows a Cancel button in the job's panel while a job
that `cancels` runs: one click, no dialog, the job named by its `startedAt`, so a Cancel from a page not told yet that
its job has ended never stops the next one; what the job had done so far is its plugin's to keep for the next try. A
job begun at another time than the one a panel follows (that one ended, then another began) gets a panel of its own.

An ask is logged by the hook's name and how many arguments it was given, never their values; a plugin's reads are not
logged at all (`present`, `status`, `view`, `charts`, `instances`, `wanted`, `services`, `startups`, `processes`, its
tabs' hooks, and from 0.31.0 `serving`: what a model server offers the other AI plugins). A plugin asking another
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
explicit confirmation with the field's words and sends the same arguments with it true.

A field of type password (a Linux plugin's sudo password; a key) is typed hidden and never shown (0.31.0): the
confirmation lists it as "(given)", also while what was sent is answered; it is never put back in its field when the
form is drawn again (Back, Change it); and the page lets go of it once it is asked or the dialog closes. So a second
confirmation has it typed again, and the hook is given it anew with its accept argument. It is sent as typed, its
leading and trailing spaces kept (sudo is handed the line as it is); spaces alone are none. A key typed in one is
trimmed where it is kept (the settings' route; the library's `keys.clean`). The platform keeps nothing of a hook's
arguments once its job has run.
