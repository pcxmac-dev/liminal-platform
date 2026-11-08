# Changelog

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
