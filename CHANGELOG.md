# Changelog

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
