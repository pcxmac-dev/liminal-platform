"""The page's part of the plugins' needs (0.40.0; Monday list item 19, part two, release 1; the needs plan's revision 2,
3.7 and 3.12): the list's filter and its Not listed line, Connections' two tabs and its Plugins tab with its right
column, the Needs list, This machine's facts, the asks of GET api/needs, and the three older mixes. Read from the files
the platform serves, as text: nothing is served, nothing started."""
from __future__ import annotations

import pytest

from conftest import page_script, script_part

from liminal_platform.app import PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside")


@pytest.fixture(scope="module")
def js() -> str:
    return page_script()


def _between(js: str, start: str, end: str) -> str:
    at = js.index(start)
    return js[at:js.index(end, at)]


def test_needs_js_is_loaded_after_internal_js_and_before_the_page():
    html = (PlatformApp.STATIC / "index.html").read_text(encoding="utf-8")
    assert html.index('src="internal.js"') < html.index('src="needs.js"') < html.index('src="platform.js"')


def test_the_list_leaves_out_what_cannot_run_here(js):
    """The list, the tray and This machine's tables leave out every plugin whose needs say met: false, and (from an older
    server) every one its status says is not for this machine; a section left empty is not drawn; the line under the
    sections says how many and where they all are; one shown by its address is drawn at the foot, dimmed."""
    assert "const unlisted = (m) => !!m && (unmetMachine(m) || unmetNow(m) || notHere(m));" in js
    draw = script_part(js, "  function drawList() {")
    assert "all = everyone.filter((m) => !unlisted(m))" in draw and "(st.assistants || []).filter((a) => !unlisted(a))" in draw
    assert "return mine.length ? `<h4>${title}</h4>` + mine.map(drawn).join('') : '';" in draw  # an empty section: nothing
    assert "+ notListed(item);" in draw
    line = _between(js, "  function notListed(item) {", "\n  }\n")
    assert "Not listed: ${parts.join(', ')}." in line and "Connections, Plugins</button> lists them all." in line
    assert "`${cannot} not for this machine`" in line and "`${now} not met now`" in line
    assert "data-select=\"${CONNECTIONS}/plugins\"" in line and "' off unlisted'" in line
    assert "p.hidden || unlisted(p)" in script_part(js, "  function drawRail() {")
    assert "Object.values(st.machines).filter((m) => !unlisted(m));  // 0.40.0: what the list lists" in js


def test_the_three_older_mixes_are_said(js):
    """M30: a page from before draws the new state as not valid (the server's valid: false, applies: false: the
    platform's tests); this page with an older server and library (404: notHere filters, the words, no more asks); this
    page and library with an older platform process (held: false, no switch, its words; the switch's 404 said)."""
    assert "was started before it judged its plugins’ needs: start it again to see them." in js
    assert "judges its plugins’ needs but does not hold them by them yet: start it again." in js
    assert "does not take the internet switch yet: start it again." in js
    load = _between(js, "  async function loadNeeds(fresh) {", "\n  function needsChanged(before) {")
    assert "if (e.status === 404) { needsGone = true; needsAnswer = null; }" in load
    assert "if (needsGone) return;" in load and "if (!needsGone) needsTimer = setTimeout(" in load  # stopped until a reload
    assert "const sw = needsAnswer.switch ?" in js  # the switch only where the route says it takes one
    assert "needsAnswer.held === false ? NEEDS_UNHELD" in js
    # a status without `needs` (an older platform process): the route's answer is read in its place
    assert "m && m.needs && typeof m.needs === 'object' ? m.needs : ((m && needsRow(m.name)) || {}).needs" in js


def test_without_needs_js_the_list_still_filters_and_rows_are_plain(js):
    assert "const ND = () => window.LiminalNeeds || null;" in js
    assert "if (ND()) return ND().line(n);" in js and "if (ND()) return `<div class=\"plugin-needs\">${ND().table(n)}</div>`;" in js
    assert "LiminalNeeds" not in script_part(js, "  function drawList() {")


def test_the_asks_follow_the_page_and_the_tab(js):
    """M5: every 30 s while the page is shown, 15 s while the Plugins tab is, one at a time; the 2-s traffic ask paused
    while the Plugins tab is shown; a plugin whose needs changed asked its status at once."""
    assert "const NEEDS_EVERY = 30, NEEDS_TAB_EVERY = 15;" in js
    load = _between(js, "  async function loadNeeds(fresh) {", "\n  function needsChanged(before) {")
    assert "if (!fresh && !pageShown()) { again(); return; }" in load and "if (needsAsking) return;" in load
    assert "(onPluginsTab() ? NEEDS_TAB_EVERY : NEEDS_EVERY) * 1000" in load
    assert "api('GET', `api/needs${fresh ? '?fresh=1' : ''}`)" in load
    traffic = _between(js, "  async function loadTraffic() {", "\n  function pickNode(id) {")
    assert traffic.count("onPluginsTab()") == 2  # neither asked nor asked again while Plugins is shown
    changed = _between(js, "  function needsChanged(before) {", "\n  async function setInternet(rule) {")
    assert "api('GET', `api/machines/${enc(p.name)}`)" in changed and "api('GET', 'api/assistants')" in changed


def test_the_check_is_not_asked_while_its_needs_are_unmet(js):
    """M23: a plugin's check, asked when its page is shown and each minute, only while its needs are not unmet and it is
    not for elsewhere: a WSL plugin's page on the Linux platform asks nothing, so no 409 comes back each minute."""
    data = script_part(js, "  function drawData() {")
    assert "if (m && hasHook(m, 'check') && !userOff(m) && !unlisted(m) && !own) {" in data


def test_connections_has_two_tabs_at_their_addresses(js):
    """The user's answer 8: "Two tabs": Who talks to whom (#connections) and Plugins (#connections/plugins)."""
    assert "const connTab = () => (selected() === CONNECTIONS && hashParts()[1] === 'plugins' ? 'plugins' : 'who');" in js
    assert "['who', 'Who talks to whom', CONNECTIONS], ['plugins', 'Plugins', `${CONNECTIONS}/plugins`]" in js
    assert "if (connTab() === 'plugins') return pluginsTab();" in js
    assert "<h2>Connections</h2>${connTabs()}<span class=\"conn-tools\">" in js
    # 0.41.0: drawn as the right-hand panel's top (setSide), in its own scope: connections/plugins
    assert "if (sel === CONNECTIONS) { if (onPluginsTab()) setSide(sideScope(), pluginsSide()); else drawConnectionsSide(); return; }" in js
    assert "if (sel === CONNECTIONS && onPluginsTab()) return 'connections/plugins';" in js


def test_the_plugins_tab_shades_only_what_cannot_run_here(js):
    """S10: shading means not for this machine alone, red not met now (and said in words); disabled and not valid are
    at full strength, their chip muted."""
    tab = _between(js, "  function pluginsTab() {", "\n  function pluginsSide() {")
    assert "cls = n.met === false ? (n.sort === 'machine' ? 'nd-cannot' : 'nd-now') : ''" in tab
    assert "nd-cannot" not in tab.replace("(n.sort === 'machine' ? 'nd-cannot'", "")  # no other row is shaded
    words = _between(js, "  function needsStateWords(p) {", "\n  }\n")
    assert "'not for this machine' : 'not met now'" in words and "not valid" in words and "'disabled'" in words
    assert "Read again</button>" in tab and "data-needs=\"system\"" in tab and "data-needs=\"there\"" in tab
    assert "Read on this machine, nothing sent: the internet" in tab and "is not known here" in tab
    assert "${c.listed} listed · ${c.now} not met now · ${c.cannot} not for this machine" in tab
    css = (PlatformApp.STATIC / "platform.css").read_text(encoding="utf-8")
    assert ".nd-cannot { opacity: .45; }" in css and "var(--down)" in css
    assert ".needs-row.nd-invalid" not in css and "opacity" not in css[css.index("table.needs-table"):]


def test_the_plugins_tabs_right_column_is_the_picked_ones_needs(js):
    """M28: a row picked fills the right column with that plugin's Needs list, its page one click away; with none picked,
    the counts and what red and shading mean."""
    side = _between(js, "  function pluginsSide() {", "\n  function connectionsSide(t) {")
    assert "needsList({ name: p.name, needs: p.needs })" in side and "data-select=\"${esc(p.name)}\">Its page</button>" in side
    assert "Not met now</dt>" in side and "Not for this machine</dt>" in side and "“not known here”" in side
    assert "const needsPick = e.target.closest('button[data-needs-pick]');" in js


def test_a_plugins_page_and_its_right_column_say_its_needs(js):
    data = script_part(js, "  function pluginData(m) {")
    assert "needsTable(m) + `<div id=\"tables-${esc(m.name)}\">${statTables(m)}</div>`" in data  # not for this machine
    assert "Not met now: ${esc(whyOf(m))}. It is asked again once its needs are met." in data
    listing = _between(js, "  function needsList(m) {", "\n  function assistantData(a) {")
    for said in ("group('It needs', 'required')", "group('For its parts', 'part')", "group('It prefers', 'preferred')",
                 "It has not said what it needs yet", "It needs nothing of this machine", "'✓', 'met'", "'✗'", "'?'"):
        assert said in listing, said
    assert "${needsList(m)}" in script_part(js, "  function pluginSide(m) {")
    switch = script_part(js, "  function switchRow(m) {")
    assert "held = invalid(m) || unlisted(m)" in switch and "'Disabled: not met now'" in switch


def test_both_state_orders_know_unmet(js):
    assert js.count("STATE = { active: 0, attached: 0, unknown: 1, invalid: 2, unmet: 3, disabled: 4 }") == 2


def test_this_machine_says_what_the_needs_are_read_against(js):
    facts = _between(js, "  function needsFacts() {", "\n  }\n")
    assert "What the plugins’ needs are read against" in facts and "data-needs=\"again\">Read again</button>" in facts
    assert "${needsFacts()}" in script_part(js, "  function machineData() {")


def test_every_word_the_needs_draw_is_escaped(js):
    """No word of a plugin's, of its needs' or of the facts reaches the page but through esc."""
    import re

    fields = r"(r\.said|r\.words|r\.how|p\.title|p\.name|p\.why|n\.why)"  # (the internet's words make `how`, drawn through esc)
    words = re.compile(r"\$\{\s*\(?\s*" + fields + r"\s*(\|\|[^{}]*)?\)?\s*\}")  # a field drawn as it is
    for start, end in (("  function needsTable(m) {", "\n  function needsList(m) {"),
                       ("  function needsList(m) {", "\n  function assistantData(a) {"),
                       ("  function pluginsTab() {", "\n  function pluginsSide() {"),
                       ("  function pluginsSide() {", "\n  function connectionsSide(t) {"),
                       ("  function notListed(item) {", "\n  }\n")):
        part = _between(js, start, end)
        assert not words.findall(part), f"{start.strip()}: {words.findall(part)}"
    facts = _between(js, "  function needsFacts() {", "\n  }\n")
    assert "`<dt>${esc(n)}</dt><dd>${esc(x)}</dd>`" in facts
    assert "`<dt>${esc(n)}</dt><dd class=\"muted\">${esc(why)}</dd>`" in facts
