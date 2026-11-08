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
platform's folder, `plugins.json`). A plugin not in a valid state (set up for Liminal: a WSL plugin with its own Liminal-named distribution, a firewall
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
(`{"command": [...]}`), `GET /api/instances`, and the frame's `/api/tray`, `/api/app`, `/api/plugins`,
`/api/interface`. Writes carry the write header, as in every Liminal app; only this machine's pages are
answered.
