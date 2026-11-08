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

`GET /api/status`, `GET /api/machines`, `GET /api/machines/<name>`, `POST /api/machines/<name>/setup`
(`{"steps": [...]}`, 202; `GET` the same path for the lines and the result), `POST /api/machines/<name>/run`
(`{"command": [...]}`), `POST /api/machines/<name>/ask` (`{"hook": ..., "args": [...]}`: one of a plugin's hooks by
name; a refusal answers 400 and a failure 502, with the plugin's own `words` and, for a refusal that names the argument
accepting it, `accept`), `GET /api/instances`, and the frame's `/api/tray`, `/api/app`, `/api/plugins`,
`/api/interface`. Writes carry the write header, as in every Liminal app; only this machine's pages are
answered.

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
