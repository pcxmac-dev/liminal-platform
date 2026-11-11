# Changelog

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
