"""The right-hand menu by the library's page standard (0.39.2; Monday list item 31; liminal-libs docs/PAGES.md): the
tool picked on the left at its top, the row, the globe's item or the Connections part picked in the middle told in full
under it, through the library's side.js. Text assertions on the page's files, as the platform's other page tests; the
script itself is run in headless Edge on stand-ins."""
from __future__ import annotations

import json
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "liminal_platform" / "static"
JS = (STATIC / "platform.js").read_text(encoding="utf-8")
HTML = (STATIC / "index.html").read_text(encoding="utf-8")


def body(head: str) -> str:
    at = JS.index(head)
    depth, i = 0, JS.index("{", at)
    for j in range(i, len(JS)):
        depth += {"{": 1, "}": -1}.get(JS[j], 0)
        if depth == 0:
            return JS[at:j + 1]
    raise AssertionError(head)


def test_side_js_is_loaded_after_the_icons_and_before_the_page():
    order = [HTML.index(s) for s in ('src="icons.js"', 'src="side.js"', 'src="platform.js"')]
    assert order == sorted(order)


def test_without_side_js_the_side_is_drawn_whole_as_before():
    assert "const Side = window.LiminalSide || null;" in JS
    assert "const sidePanel = Side ? Side.panel(side, { app: 'platform', onPick: (p) => sidePicked(p) }) : null;" in JS
    set_side = body("function setSide(scope, html) {")
    assert "if (sidePanel) sidePanel.tool(scope, html);" in set_side and "else side.innerHTML = html;" in set_side
    assert JS.count("side.innerHTML = ") == 1  # only setSide's fallback draws the side whole
    assert "if (!sidePanel || t.pick === false) return '';" in JS  # no panel, or a table of buttons: no row picks
    assert "const mainPick = (key) => (sidePanel ? ` data-pick=" in JS


def test_the_scopes_are_the_standards_platform_tools():
    """The scope's first word is one of standard.json's platform tools: a new tool or a new tab lets the pick go."""
    from liminal_libs.ui import standard

    tools = next(g for g in standard.groups("platform") if g["id"] == "tool")["tools"]
    scope = body("function sideScope() {")
    said = set(re.findall(r"return `?'?([a-z]+)[:'`]", scope))
    assert said == set(tools), said
    assert "setSide('connections', connectionsSide(traffic));" in JS


def test_a_tab_pages_rows_carry_their_keys_and_details():
    st = body("function statTables(m) {")
    assert "pickSpecs.clear();" in st and "if (d && typeof d === 'object') pickSpecs.set(key, d);" in st
    assert "t.rows.map((r, ri) => `<tr${pickAttr(t, r, ri)}>" in st
    key = body("function rowKey(t, r, i) {")
    assert "if (d && typeof d === 'object' && d.key) return" in key and "wordsShared(t).has(w) ? r.map(cellWords)" in key
    assert "!(t.columns[j] && t.columns[j].num)" in JS
    tables = body("function pageTables(p) {")
    assert "details: kept.map(([, d]) => d)" in tables  # a row left out takes its details with it


def test_the_pick_is_told_anew_after_every_answer_and_every_draw():
    rows = body("function sideRows() {")
    assert "Side.rows(data, { selector: 'tr[data-pick]', panel: sidePanel," in rows and "sidePanel.refresh(pickFind);" in rows
    assert "sideRows();  // 0.39.2: the pick told anew from this answer" in body("function drawTab(name) {")
    assert "sideRows();  // 0.39.2" in body("function drawData() {")
    find = body("function pickFind(key) {")
    assert "v.globe.describe(key)" in find and "nodePick(t, n)" in find and "Side.fromRow(tr)" in find


def test_the_globe_and_the_rows_share_the_one_pick():
    assert "onPick: (item) => globePicked(item) });" in JS
    g = body("function globePicked(item) {")
    assert "sidePanel.pick(" in g and "startsWith('globe:')) sidePanel.unpick();" in g
    p = body("function sidePicked(p) {")
    assert "tabView.globe.unpick();" in p and "!key.startsWith('globe:')" in p


def test_connections_part_is_told_under_the_tool():
    side = body("function connectionsSide(t) {")
    assert "if (n && !sidePanel) {" in side  # with the panel, the part is not in the tool's slot
    node = body("function nodePick(t, n) {")
    assert "key: `node:${n.id}`" in node and "'Its links'" in node
    draw = body("function drawConnectionsSide() {")
    assert "sidePanel.pick(nodePick(t, n));" in draw and "else if (sidePanel.picked) sidePanel.unpick();" in draw
    assert "if (!p && focusNode && selected() === CONNECTIONS) { focusNode = null; updateConnections(false); }" in JS


def test_codebase_is_mounted_with_the_panel():
    assert "panel: sidePanel, scope: 'codebase' });" in JS


def test_rows_alike_in_their_words_are_told_apart_by_every_cell():
    """Two programs listening on one address (tcp 135 and tcp 5040, both svchost.exe): their first words are alike,
    so each is keyed by all its cells, the ports with them; a row alone in its words keeps the key a count cannot move."""
    shared = body("function wordsShared(t) {")
    assert "if (seen.has(w)) s.add(w); seen.add(w);" in shared and "sharedWords.set(t, s);" in shared


def test_the_tables_redrawn_by_an_answer_or_a_group_are_marked_again():
    """A status answer redraws a Main tab's tables (redrawShown) and a group opened or closed redraws them too
    (redrawTables): the new rows are marked (tabindex, .picked) and the pick told anew from them."""
    assert "sideRows();  // 0.39.2: the tables drawn again from this answer" in body("function redrawShown(m) {")
    assert "sideRows();  // 0.39.2: the rows drawn again marked" in body("function redrawTables(name, focus) {")
