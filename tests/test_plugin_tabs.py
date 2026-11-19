"""0.27.0 (the user, 2026-11-14: "so for the firewall's both are going to get a 'world wide web view' that shows the globe
and the routes incoming all traffic, as well as monitoring port traffic stats"; "on top of the monitoring there needs to be
a way to 'filter' (another tab) that allows you to monitor send and receive traffic, especially traffic that is out of the
ordinary"): a machine plugin declares tabs of its own (liminal-libs apps/tabs.py's Tab, in its TABS); its status carries
them after Main and API, and each one's hook is one the page may ask. The page asks it every `every` seconds while its tab
is shown and the page is visible (framed by the charts app: while its frame is drawn), and draws the page it answers (a
globe, charts, connections with their filters, tables, forms and actions); the platform asks it as a read, noted as one in
who talks to whom and never logged. Stand-in plugins on a free port and the page's script as it is served: nothing of this
machine is asked, nothing captured, no address reached."""
from __future__ import annotations

import re
import time

import pytest

from liminal_libs.apps.tabs import Tab
from liminal_libs.machines import MachinePlugin

from conftest import Wall, _port, page_script, sock
from test_app import _call

from liminal_platform.app import MAX_TAB_TITLE, MAX_TABS, NOT_ASKED, READS, PlatformApp, tab_hooks, tabs_of

AWAY = "a peer never seen before (unusual for this machine while Liminal was watching)"


class Walled(MachinePlugin):
    """A stand-in with tabs of its own: who reaches it, on a globe and in a table; what it sends and receives, filtered.
    Its addresses are the documentation ranges', its names .invalid ones."""

    name, title, about, api, order = "walled", "Walled", "a stand-in with tabs of its own", "2.2", 910
    HOOKS = (*MachinePlugin.HOOKS, "world", "filter", "poke")
    TABS = (Tab("world", "World Wide Web", "world", 2.0), Tab("filter", "Filter", "filter", 2.0),
            Tab("API", "Not the API's", "world"),  # Main's and API's places are the page's own, in any case
            Tab("World", "Twice", "world"),  # a tab's id once
            Tab("setup", "Its setup", "setup"),  # asked through its own route, never every few seconds
            Tab("scope", "Scope", "scope", 3))  # declared, its hook not among those it answers

    def __init__(self):
        self.asked: list[str] = []
        self.pokes = 0

    def present(self):
        return True

    def status(self):
        return {"present": True, "summary": "walled in"}

    def world(self):
        self.asked.append("world")
        return {"title": "Who reaches this machine",
                "globe": {"home": {"lat": 52.37, "lon": 4.9, "label": "here"}, "local": {"count": 2, "bytes": 512},
                          "origins": [{"id": "198.51.100.0/24", "lat": 40.7, "lon": -74.0, "label": "New York", "count": 3,
                                       "bytes": 4096, "kind": "allowed", "ports": [443]}], "attribution": None},
                "tables": [{"title": "Ports", "columns": [{"title": "Port", "num": True}, {"title": "In"}], "rows": [[443, "4 KB"]]}]}

    def filter(self):
        self.asked.append("filter")
        return {"flows": {"rows": [{"id": "1", "dir": "out", "proto": "tcp", "remote": "203.0.113.9:443", "name": "tracker.invalid",
                                    "labels": [{"kind": "tracking", "source": "EasyPrivacy"}],
                                    "flags": [{"id": "new-peer", "words": AWAY}]}],
                          "filters": {"dir": ["in", "out"], "flagged": False, "labels": ["tracking"], "search": ""}}}

    def poke(self):
        self.pokes += 1
        return {"poked": self.pokes}


def test_a_plugin_says_its_own_tabs_after_main_and_api():
    w = Walled()
    assert tabs_of(w) == [{"id": "world", "title": "World Wide Web", "hook": "world", "every": 2.0},
                          {"id": "filter", "title": "Filter", "hook": "filter", "every": 2.0},
                          {"id": "scope", "title": "Scope", "hook": "scope", "every": 3.0}]
    assert tab_hooks(w) == ["world", "filter", "scope"]
    assert tabs_of(MachinePlugin()) == [] and tabs_of(object()) == []  # none declared; an older library's plugin, none at all
    # the page may ask each tab's hook; the platform asks it as a read, as it asks a status
    asks = PlatformApp.asks(w)
    assert {"world", "filter", "scope", "poke"} <= set(asks) and not set(NOT_ASKED) & set(asks)
    assert PlatformApp.reads_of(w) == (*READS, "world", "filter", "scope") and "poke" not in PlatformApp.reads_of(w)
    assert PlatformApp.reads_of(MachinePlugin()) == READS


def test_what_a_plugin_declares_is_kept_to_what_the_page_can_ask():
    class Odd(MachinePlugin):
        name = "odd"
        JOB_HOOKS = ("pull",)
        TABS = ({"id": "slow", "title": "  Slow  ", "hook": "slow", "every": 1e9},  # a dict in a Tab's shape: taken as one
                {"id": "fast", "title": "", "hook": "fast", "every": 0.2},  # no title: its id; asked once a second at the most
                {"id": "bad id", "hook": "x"}, {"id": "x" * 41, "hook": "x"}, {"id": "nan", "hook": "x", "every": float("nan")},
                {"id": "yes", "hook": "x", "every": True}, {"id": "job", "hook": "pull"}, {"id": "cmd", "hook": "run"},
                {"id": "call", "hook": "not a name"}, {"id": "long", "title": "t" * 200, "hook": "long"}, "world", 7, None)

    assert tabs_of(Odd()) == [{"id": "slow", "title": "Slow", "hook": "slow", "every": 3600.0},
                              {"id": "fast", "title": "fast", "hook": "fast", "every": 1.0},
                              {"id": "long", "title": "t" * MAX_TAB_TITLE, "hook": "long", "every": 5.0}]

    class Many(MachinePlugin):
        name = "many"
        TABS = tuple(Tab(f"t{i}", f"Tab {i}", f"h{i}") for i in range(20))

    assert [t["id"] for t in tabs_of(Many())] == [f"t{i}" for i in range(MAX_TABS)]

    class Broken(MachinePlugin):
        name = "broken"

        @property
        def TABS(self):  # noqa: N802 - the declaration's own name
            raise RuntimeError("it cannot say")

    class Unsaid(MachinePlugin):
        name = "unsaid"

        class Bad:
            def as_dict(self):
                raise ValueError("no")

        TABS = (Bad(), Tab("ok", "OK", "ok"))

    assert tabs_of(Broken()) == [] and tabs_of(Unsaid()) == [{"id": "ok", "title": "OK", "hook": "ok", "every": 5.0}]


def test_the_status_carries_the_tabs_and_their_hooks_are_asked_as_reads(tmp_path):
    w, lines = Walled(), []
    app = PlatformApp(log=lines.append, machines={"walled": w}, assistants={}, state=tmp_path)
    port = _port(app.start(0))
    try:
        m = _call(port, "GET", "/api/machines/walled")[1]
        assert m["tabs"] == tabs_of(w) and {"world", "filter", "scope"} <= set(m["asks"])
        assert _call(port, "GET", "/api/status")[1]["machines"]["walled"]["tabs"] == m["tabs"]
        # a tab's hook asked as the page asks it: no arguments, its page the answer
        status, out = _call(port, "POST", "/api/machines/walled/ask", {"hook": "world", "args": []})
        assert status == 200 and out["answer"]["title"] == "Who reaches this machine"
        assert out["answer"]["globe"]["origins"][0]["kind"] == "allowed" and out["answer"]["tables"][0]["rows"] == [[443, "4 KB"]]
        flows = _call(port, "POST", "/api/machines/walled/ask", {"hook": "filter", "args": []})[1]["answer"]["flows"]
        assert flows["rows"][0]["flags"] == [{"id": "new-peer", "words": AWAY}] and flows["rows"][0]["labels"][0]["kind"] == "tracking"
        assert w.asked == ["world", "filter"]
        assert not any("asked world" in x or "asked filter" in x for x in lines)  # a read: never in the platform's log
        assert _call(port, "POST", "/api/machines/walled/ask", {"hook": "poke", "args": []})[1] == {"answer": {"poked": 1}}
        assert any("walled asked poke" in x for x in lines)  # a hook asked by name otherwise: logged, as ever
        # declared, its hook not among those it answers: its own words, which the tab shows
        status, out = _call(port, "POST", "/api/machines/walled/ask", {"hook": "scope", "args": []})
        assert status == 400 and "offers no 'scope'" in out["words"]
        assert _call(port, "POST", "/api/machines/walled/ask", {"hook": "setup", "args": []})[0] == 400  # never a tab's
        snap = _call(port, "GET", "/api/traffic")[1]
        # disabled: still its tabs (the page says the platform asks it nothing), and nothing asked
        assert _call(port, "POST", "/api/machines/walled/enabled", {"on": False})[0] == 200
        off = _call(port, "GET", "/api/machines/walled")[1]
        assert off["tabs"] == m["tabs"] and off["asks"] == []
        assert _call(port, "POST", "/api/machines/walled/ask", {"hook": "world", "args": []})[0] == 409 and w.asked == ["world", "filter"]
    finally:
        app.stop()
    kinds = {(r["what"], r["kind"]) for r in snap["recent"] if r["from"] == "platform" and r["to"] == "walled"}
    assert {("world", "read"), ("filter", "read"), ("scope", "read"), ("poke", "ask")} <= kinds  # classed: reads, never changes
    assert not {("world", "ask"), ("filter", "ask"), ("world", "change"), ("filter", "change")} & kinds


def _page(port) -> str:
    return _call(port, "GET", "/platform.js")[1].decode("utf-8")


def _charts(port) -> str:  # the library's charts.js, as the platform serves it beside its page
    return _call(port, "GET", "/charts.js")[1].decode("utf-8")


def _between(text: str, start: str, end: str) -> str:
    """The part of a script from `start` to the first `end` after it."""
    at = text.index(start)
    return text[at:text.index(end, at + len(start))]


def test_the_page_draws_a_plugins_own_tabs_and_asks_them_only_while_shown(served):
    app, port, lines, box = served
    js = _page(port)
    # Main and API, then the plugin's own (url-safe ids, Main's and API's places kept, eight at the most); a server that
    # sends no tabs: Main and API as before
    assert "const OWN_TABS = [{ id: 'main', title: () => 'Main' }," in js and "const tabsOf = (p) => [...OWN_TABS, ...declaredTabs(p)];" in js
    assert "const TAB_ID = /^[A-Za-z0-9_-]{1,40}$/;" in js and "const MAX_TABS = 8;" in js
    assert "(Array.isArray(p && p.tabs) ? p.tabs : []).forEach((t) => {" in js and "seen.has(t.id.toLowerCase())" in js
    assert "Math.min(3600, Math.max(1, Number(t.every) || 5))" in js
    assert "hasTabs(p) && tabsOf(p).some((x) => x.id === t) ? t : 'main'" in js and "tabsOf(p).map((t) => `<button type=\"button\" role=\"tab\"" in js
    # its tab drawn in the plugin's page, its place said while it is not asked
    assert "const own = ownTabOf(m);" in js and "if (own) return head + tabFrame(m, own);" in js
    frame = js[js.index("function tabFrame(m, t) {"):js.index("function partOf(m, t, v, part) {")]
    for said in ("Disabled: the platform asks it nothing", "Not for this machine:", "Disabled while it is not valid:",
                 'role="status"', 'aria-label="${title}"'):
        assert said in frame, said
    # its hook asked with no arguments, one ask at a time, every `every` seconds; nothing while the page is hidden (its frame
    # too: test_a_tab_is_asked_only_while_its_frame_is_drawn) or your account covers it, nothing once it is left (its timer
    # cleared, its globe destroyed, its page dropped)
    asked = _between(js, "function askOf(v) {", "async function askTab() {")
    assert "api('POST', `api/machines/${enc(v.name)}/ask`, { hook: v.hook, args: [] })" in asked
    ask = _between(js, "async function askTab() {", "function askTabNow(name) {")
    assert "if (!v || v.asking) return;" in ask and "if (tabView !== v) return;" in ask
    assert "if (!under && !askable()) { waitShown(); return; }" in ask
    assert "v.timer = setTimeout(askTab, v.again ? 0 : (error ? Math.max(v.every, 5) : v.every) * 1000);" in ask
    assert "const askable = () => pageShown() && !loginOpen;" in js
    assert "if (document.hidden) { clearTimeout(live); clearTimeout(trafficTimer); pauseTab(); return; }" in js
    leave = js[js.index("function leaveTab() {"):js.index("async function askTab() {")]
    assert "clearTimeout(v.timer);" in leave and "dropGlobe(v);" in leave and "v.page = null;" in leave
    sync = js[js.index("function syncTab() {"):js.index("function pauseTab() {")]
    assert "if (tabView && tabView.key !== want) leaveTab();" in sync and "if (!tabView.asking && !tabView.timer) askTab();" in sync
    draw = js[js.index("function drawData() {"):js.index("function drawAround(panel, html, name) {")]
    assert "syncTab();" in draw and "if (own) keepFocus(put); else put();" in draw
    assert "syncTab();  // 0.27.0: a plugin's own tab under your account is not asked meanwhile" in js
    # its status asked only now and then meanwhile, the tab's page left as it is unless what frames it changed
    assert "const every = ownTabOf(m) ? TABLES_EVERY : pathRunning(m) ? 1" in js
    assert "if (ownTabOf(m)) { redrawTabFrame(m); return; }" in js and "if (!t || frameKey(m, t) !== tabFramed) drawData();" in js


def test_the_page_draws_what_a_tab_answers_with_the_drawers_it_has(served):
    app, port, lines, box = served
    js = _page(port)
    # the globe: the library's, made once in an element kept across redraws, given each answer, destroyed when left
    # (0.33.0: with the key its layers' switches are remembered under and the way to their geometry)
    assert "window.LiminalGlobe.draw(v.globeEl, spec, { theme: themeNow(), key: `${m.name}/${v.id}`, load });" in js
    assert "v.globe.update(spec);" in js
    assert "v.globe.destroy();" in js and 'data-globe-slot="${esc(m.name)}"' in js and "slot.replaceWith(v.globeEl);" in js
    # charts: LiminalCharts cards whose ids are the tab's, in place when they are the same charts
    assert "const chartsId = (m, t, i) => `${t.id}-${m.name}-${i}`;" in js and "Charts.cards(s, { id: chartsId(m, t, i) })" in js
    assert "Charts.update(groups[i], s, { id: chartsId(m, t, i) })" in js
    # tables, forms and actions: the Main tab's own drawers, given the page as the plugin's status
    assert "statTables(pagePlugin(m, p))" in js and "actionsHtml(pagePlugin(m, p))" in js
    assert "[...listOf(m.status && m.status.forms), ...(page ? listOf(page.forms) : [])]" in js  # a tab's forms open too
    assert "return on ? pageTables(pageOf(on.v) || {}) : (p && p.status && p.status.tables) || [];" in js  # its groups open and close
    for after in ("askTabNow(name);  // 0.27.0: asked from one of its own tabs", "askTabNow(d.name);  // 0.27.0: a form of one",
                  "askTabNow(name);  // 0.27.0: the row of one of its own tabs", "askTabNow(name);  // 0.27.0: a search on one"):
        assert after in js, after  # a change asked through the tab: its page asked again at once
    # each part drawn again only when it changed, the focus kept
    tab = js[js.index("function drawTab(name) {"):js.index("function syncTab() {")]
    assert "keepFocus(() => TAB_PARTS.forEach((part) => {" in tab and "if (v.drawn[part] !== html) box.innerHTML = html;" in tab
    assert "const TAB_PARTS = ['head', 'actions', 'globe', 'charts', 'flows', 'tables'];" in js


def test_the_page_draws_connections_with_their_filters_and_chips(served):
    app, port, lines, box = served
    js = _page(port)
    flows = js[js.index("const FLOW_COLUMNS = {"):js.index("function drawTab(name) {")]
    # the filters: the direction, flagged only, the labels' kinds, a search; each labelled, each kept per tab
    for control in ('<select class="flow-dir" ${at}>', '<input type="checkbox" class="flow-flagged" ${at}',
                    'class="flow-kind" ${at} data-key="${esc(k)}" aria-pressed="${x.kinds.has(k)}"',
                    '<input type="search" id="${esc(id)}" class="flow-search" ${at}', "${kb('search')}",
                    '<label class="sr-only" for="${esc(id)}">Search the', '<label>Direction ', '> Flagged only</label>',
                    'role="group" aria-label="Only these labels"', '<span class="muted small flow-count" role="status">'):
        assert control in flows, control
    assert "const flowFilters = {};" in flows and "filterOf(on.v.key, f)" in flows
    # the flagged rows first, each in the plugin's order; a search's every word matched
    assert "return [...kept.filter((r) => flagsOf(r).length), ...kept.filter((r) => !flagsOf(r).length)];" in flows
    assert "words.every((w) => flowText(r).includes(w))" in flows
    # a flag's chip with its words (its tooltip, a screen reader's, a finger's); a label's with its kind, company and list
    assert '<span class="chip flow-flag" title="${esc(g.words || \'\')}">' in flows and '<span class="sr-only">: ${esc(g.words)}.</span>' in flows
    assert 'class="sub flow-words touch-only" aria-hidden="true"' in flows and '<span class="chip flow-label" title="${esc(from)}">' in flows
    assert "`listed in ${l.source}`" in flows and "<tr${marked ? ' class=\"flagged\"' : ''}>" in flows
    # drawn in place: the bar made once, so a search being typed goes on (made again only when it offers "Flagged only"
    # now and not then, or the other way: 0.33.0); a choice draws the rows again, asking nothing
    assert "if (!f || !bar || !bar.querySelector('input.flow-flagged') !== !flaggable(f)) {" in flows
    assert "put('.flow-rows', 'flowRows', p.rows);" in flows
    assert "keepFocus(() => drawFlows(on, box));" in flows
    assert "data.addEventListener('input', (e) => { const el = e.target.closest && e.target.closest('input.flow-search[data-tab]');" in flows
    assert "const fk = e.target.closest('button.flow-kind[data-tab]');" in js
    # bounded: so many rows read, fewer drawn, the count saying so
    assert "const MAX_FLOWS = 400;" in flows and "const MAX_FLOWS_READ = 5000;" in flows and ", the first ${n(shown.length)} shown" in flows


def test_the_tabs_are_a_tab_lists_by_the_keyboard_and_the_globe_is_served(served):
    app, port, lines, box = served
    js = _page(port)
    keys = js[js.index("// a plugin's tabs (0.27.0: Main, API and its own)"):js.index("// the radio group's arrow keys")]
    assert "['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(e.key)" in keys and "next.click();" in keys and "e.preventDefault();" in keys
    # the tabs' styles: on the themes' variables, a mouse's hover nowhere
    style = js[js.index("const TAB_STYLE = `"):js.index("// -- Connections (0.10.0;")]
    assert "var(--accent)" in style and ":hover" not in style and "platform-tabs-style" in style
    # the library's globe, loaded before the page's script, served beside it with its map
    body = _call(port, "GET", "/")[1]
    assert body.index(b'src="charts.js"') < body.index(b'src="liminal-globe.js"') < body.index(b'src="platform.js"')
    status, globe = _call(port, "GET", "/liminal-globe.js")
    assert status == 200 and b"window.LiminalGlobe" in globe
    assert re.search(rb"countries-110m\.json", globe)


def test_a_tab_is_asked_only_while_its_frame_is_drawn(served):
    """The charts app frames this page (its bound view, /platform/?embedded=1) and, once another view is picked, hides the
    frame with display:none without unloading it; a framed page's visibility is its top page's, so no visibilitychange comes
    and the World tab's asks went on every 2 s unseen, its capture never reaching its viewing timeout (the phase-1 review's
    hidden bound frame). A tab is asked only while the page is visible and has a size, its frame has boxes in the page round it
    (the same origin, through the charts front) and its pane is in sight (an IntersectionObserver's last word): looked at before
    every ask, again as the page resizes or the observer speaks, and every second while a tab waits for its frame, asking
    nothing meanwhile."""
    app, port, lines, box = served
    js = _page(port)
    assert "const askable = () => pageShown() && !loginOpen;" in js and "const pageShown = () => !document.hidden && frameShown();" in js
    shown = _between(js, "function frameShown() {", "const pageShown = ")
    for part in ("if (!(window.innerWidth > 0 && window.innerHeight > 0) || !paneSeen) return false;", "try { f = window.frameElement; }",
                 "if (!f.isConnected || !f.getClientRects().length) return false;", "return r.width > 0 && r.height > 0;"):
        assert part in shown, part
    # looked at again: as the page resizes, as the observer of its pane speaks, and every second while a tab waits on its frame
    assert "window.addEventListener('resize', seenAgain);" in js and "const seenAgain = () => { if (tabView) syncTab(); };" in js
    assert "new IntersectionObserver((entries) => { paneSeen = entries[entries.length - 1].isIntersecting; seenAgain(); }).observe(data);" in js
    wait = _between(js, "function waitShown() {", "const seenAgain = ")
    assert "if (!tabView || document.hidden || loginOpen || frameShown()) return;" in wait  # hidden or covered: their own events
    assert "unseen = setTimeout(() => { unseen = 0; if (frameShown()) syncTab(); else waitShown(); }, SEEN_AGAIN_MS);" in wait
    assert "const SEEN_AGAIN_MS = 1000;" in js
    # every ask behind the gate: the one place a tab's hook is asked, reached only past askable(); the next ask timed only while
    # it holds; paused, and looked at again, wherever it does not
    assert js.count("api('POST', `api/machines/${enc(v.name)}/ask`, { hook: v.hook, args: [] })") == 1
    assert js.count("askOf(") == 2 and js.count("setTimeout(askTab") == 1  # askOf defined and called once; askTab timed once
    ask = _between(js, "async function askTab() {", "function askTabNow(name) {")
    assert ask.index("if (!under && !askable()) { waitShown(); return; }") < ask.index("const ask = under || askOf(v);")
    assert "if (askable()) v.timer = setTimeout(askTab," in ask and "else waitShown();" in ask
    sync = _between(js, "function syncTab() {", "function pauseTab() {")
    assert "if (!askable()) { pauseTab(); waitShown(); return; }" in sync and "clearTimeout(unseen);" in sync
    assert "clearTimeout(unseen);" in _between(js, "function leaveTab() {", "const tabAsks = ")


def test_a_tabs_charts_are_let_go_once_they_are_not_drawn(served):
    """charts.js keeps every chart given to cards() (its samples) in a map that lives as long as the page, and a tab's charts may
    be keyed by what changes from answer to answer, a port or a peer: they piled up (the phase-1 review's tab charts). The library
    lets go of the charts whose id starts with a prefix (LiminalCharts.forget), and the page forgets a tab's own whenever it
    draws them whole and when the tab is left; a library without forget: kept, as before."""
    app, port, lines, box = served
    charts = _charts(port)
    forget = _between(charts, "function forget(prefix) {", "window.LiminalCharts = ")
    assert "if (typeof prefix !== 'string' || !prefix) return 0;" in forget  # an empty prefix lets go of nothing (the Main tab's)
    assert "if (key.startsWith(prefix)) { specs.delete(key); n++; }" in forget and "opened" not in forget  # tables opened stay so
    assert "window.LiminalCharts = { cards, draw, update, forget, format," in charts and charts.count("specs.delete(") == 1
    js = _page(port)
    assert "const forgetTabCharts = (name, id) => { if (Charts && typeof Charts.forget === 'function') Charts.forget(`${id}-${name}-`); };" in js
    whole = _between(js, "const tabChartsHtml = (m, t, p) => {", "function drawTabCharts(on, box) {")
    assert whole.index("forgetTabCharts(m.name, t.id);") < whole.index("Charts.cards(s, { id: chartsId(m, t, i) })")
    # drawn whole with other keys (through tabChartsHtml): those before let go first; the same charts: in place, kept
    redraw = _between(js, "function drawTabCharts(on, box) {", "// its connections (page.flows")
    assert "box.innerHTML = tabChartsHtml(m, t, p);" in redraw and "forget" not in redraw
    assert "forgetTabCharts(v.name, v.id);" in _between(js, "function leaveTab() {", "const tabAsks = ")


def test_a_rows_own_values_and_a_tab_that_is_slow_to_answer(served):
    """The phase-1 review's smaller ones. A direction is one of the page's own three (a Map: a row's "constructor" or "__proto__"
    as its direction threw and blanked the whole table), a row's and a column's values are their own, a title that is not a
    string is drawn. The tab's parts, drawn again with every answer, are out of the main area's polite announcements; its said
    line, its error and the connections' count speak. Leaving a tab and coming back while its ask is under way asks nothing
    again; an ask unanswered for long is said to be (never given up: the platform would run the hook again, a thread each
    time), and when an ask fails, what is shown is said to be from its last answer."""
    app, port, lines, box = served
    js = _page(port)
    flows = _between(js, "const FLOW_COLUMNS = {", "function drawTab(name) {")
    assert "const DIRS = new Map([['in', 'In'], ['out', 'Out'], ['local', 'Local']]);" in flows and "DIRS[" not in flows
    assert "const dirWord = (d) => (typeof d === 'string' ? DIRS.get(d) : undefined);" in flows and flows.count("dirWord(") == 4
    assert "Object.prototype.hasOwnProperty.call(o, k) ? o[k] : undefined" in flows
    assert "const v = ownOf(r, c.key)," in flows and "ownOf(FLOW_COLUMNS, c.key)" in flows and "FLOW_COLUMNS[" not in flows
    assert flows.count("String(f.title || 'connections').toLowerCase()") == 2
    assert "(f.title || 'connections').toLowerCase()" not in flows.replace("String(f.title || 'connections').toLowerCase()", "")
    frame = _between(js, "function tabFrame(m, t) {", "function partOf(m, t, v, part) {")
    assert '<div class="tab-part" id="tab-${part}-${n}" aria-live="off">' in frame
    assert 'class="muted small tab-said" id="tab-said-${n}" role="status"' in frame and '<span class="muted small flow-count" role="status">' in flows
    # one ask at a time for each tab, across leaving it and coming back: the answer of the one under way awaited
    assert "const tabAsks = new Map();" in js
    of = _between(js, "function askOf(v) {", "async function askTab() {")
    assert "if (was) return was;" in of and "tabAsks.set(v.key, under);" in of and "if (tabAsks.get(v.key) === under) tabAsks.delete(v.key);" in of
    ask = _between(js, "async function askTab() {", "function askTabNow(name) {")
    assert "const under = tabAsks.get(v.key);" in ask and "const ask = under || askOf(v);" in ask
    # late, and said so; what is shown said to be from its last answer when an ask fails
    assert "AbortController" not in of + ask and "const lateAfter = (v) => Math.max(10, 3 * v.every) * 1000;" in js
    assert "v.late = true;" in ask and "Math.max(0, lateAfter(v) - (Date.now() - ask.at))" in ask and "v.at = Date.now();" in ask
    said = _between(js, "function saidOf(m, t, v) {", "function tabFrame(m, t) {")
    assert "`Still asking ${what}: no answer in over ${lasted(lateAfter(v) / 1000)}`" in said
    assert "; what is shown is from ${clockAt(v.at)}" in said and "`What is shown is from ${clockAt(v.at)}, its last answer.`" in said
    leave = _between(js, "function leaveTab() {", "const tabAsks = ")
    assert "clearTimeout(v.slow);" in leave


class Layered(MachinePlugin):
    """A stand-in whose globe draws internet infrastructure layers, as liminal-libs 1.65.0's firewalls' does: its tab's
    page names the read hook a layer's geometry is asked through, and a filter's choice is a hook of its own. It says
    nothing of its reads (no READ_HOOKS): the platform's READS alone keep a layer's load out of the log."""

    name, title, about, api, order = "layered", "Layered", "a stand-in globe with layers", "2.2", 911
    HOOKS = (*MachinePlugin.HOOKS, "world", "world_layer", "world_pick")
    TABS = (Tab("world", "World Wide Web", "world", 2.0),)
    LAYER = {"id": "datacentres", "title": "Data centres", "kind": "points", "mark": "square", "slot": 4, "on": True,
             "names_from": 5.0, "count": 1, "version": "0123456789ab", "credits": [], "note": "a stand-in"}

    def __init__(self):
        self.asked: list = []

    def present(self):
        return True

    def status(self):
        return {"present": True, "valid": True, "summary": "layered", "why": ""}

    def world(self):
        self.asked.append(("world",))
        return {"globe": {"home": None, "origins": [], "layers": [dict(self.LAYER)], "layer_hook": "world_layer"}}

    def world_layer(self, layer):
        self.asked.append(("world_layer", layer))
        if layer != self.LAYER["id"]:
            raise LookupError(f"no layer {layer!r} is installed here")
        return {"id": layer, "version": self.LAYER["version"], "parts": []}

    def world_pick(self, choice):
        self.asked.append(("world_pick", choice))
        return {"said": "Hosts recorded · all of them", "ok": True}


def test_a_globes_layer_is_asked_as_a_read_and_leaves_no_line_in_the_log():
    """0.33.0 (B-firewall-plan 3): a firewall's globe asks one infrastructure layer's geometry at a time through the
    platform's ask, with the layer's id (the page's layerLoader). `world_layer`, beside "wanted", is one of the
    platform's reads: noted as a read in who talks to whom and never logged, whatever the plugin or its library says of
    it; its refusal is the plugin's own words (400). Picking a filter stays an ask, logged by its name and how many
    arguments, never their values. Asked of the app directly: nothing is served, no port is opened."""
    p, lines = Layered(), []
    app = PlatformApp(log=lines.append, machines={"layered": p}, assistants={})
    try:
        assert "world_layer" in READS and "world_layer" in PlatformApp.reads_of(p)
        assert "world_pick" not in PlatformApp.reads_of(p) and {"world_layer", "world_pick"} <= set(PlatformApp.asks(p))
        ask = lambda hook, *args: app.api(None, "POST", "/api/machines/layered/ask", {},  # noqa: E731
                                          {"hook": hook, "args": list(args)})
        status, out = ask("world_layer", "datacentres")
        assert status == 200 and out == {"answer": {"id": "datacentres", "version": "0123456789ab", "parts": []}}
        status, out = ask("world_layer", "cables")
        assert status == 400 and out["words"] == "no layer 'cables' is installed here"
        assert lines == []  # a read: never in the log, answered or refused
        status, out = ask("world_pick", "program=msedge.exe")
        assert status == 200 and out["answer"]["ok"] is True
        assert lines == ["platform: layered asked world_pick (1 argument)"]  # its name and how many: never the value
        assert p.asked == [("world_layer", "datacentres"), ("world_layer", "cables"),
                           ("world_pick", "program=msedge.exe")]
        said = [(r["from"], r["what"], r["kind"]) for r in app.traffic.recent() if r["to"] == "layered"]
        assert ("platform", "world_layer", "read") in said and ("platform", "world_pick", "ask") in said
        assert ("platform", "world_layer", "ask") not in said  # (its two asks, answered and refused: one row, a read)
    finally:
        app.stop()


def test_a_firewalls_netstat_and_its_globes_layers_through_the_platform(tmp_path):
    """0.33.0, on liminal-libs 1.65.0's Firewall (the suite's Wall, its Netstat over a stand-in socket table): the
    Netstat tab's hook is asked as a read. Its connections name no "flagged" among their filters, so the page draws no
    "Flagged only" that would only empty a table that flags nothing (B-critique M13); since when comes as words under a
    key of its own beside the row's time (the page draws the words as sent, the time in its tooltip), and each row's
    direction and kinds are among those its filters offer. A layer of its globe is asked as a read, its refusal carried
    in the plugin's own words; a filter's pick is an ask, logged. What is checked is the platform's side: the library's
    own words and shapes are the library's tests'. Asked of the app directly: nothing served, no port opened, no socket
    table read but the stand-in."""
    pytest.importorskip("liminal_libs.machines.netstat", reason="a library before 1.65.0 has no Netstat tab")
    now, lines, wall = time.time(), [], Wall()
    wall.sockets = [sock(local_port=51000, remote="192.168.1.50", remote_port=445, started=now - 3 * 86400),
                    sock(local="0.0.0.0", local_port=8775, state="listening", pid=901, program="python.exe",
                         started=now - 3600)]
    app = PlatformApp(log=lines.append, machines={"wall": wall}, assistants={}, state=tmp_path / "platform")
    ask = lambda hook, *args: app.api(None, "POST", "/api/machines/wall/ask", {},  # noqa: E731
                                      {"hook": hook, "args": list(args)})
    try:
        status, m = app.api(None, "GET", "/api/machines/wall", {}, None)
        assert status == 200 and {"world", "netstat"} <= {t["id"] for t in m["tabs"]}
        assert {"netstat", "world_layer", "world_pick"} <= set(m["asks"])
        reads = PlatformApp.reads_of(wall)
        assert {"world", "netstat", "world_layer"} <= set(reads) and "world_pick" not in reads
        status, out = ask("netstat")
        assert status == 200 and isinstance(out["answer"]["flows"], dict)
        flows = out["answer"]["flows"]
        assert "flagged" not in flows["filters"]  # so the page draws no "Flagged only" (flaggable)
        assert "since" in [c["key"] for c in flows["columns"]]
        [row] = [r for r in flows["rows"] if r.get("time") == pytest.approx(now - 3 * 86400)]  # the connection's
        assert isinstance(row["since"], str) and row["since"]  # words, drawn as sent
        assert row["dir"] in flows["filters"]["dir"]
        assert {label["kind"] for label in row["labels"]} <= set(flows["filters"]["labels"])
        with pytest.raises(LookupError) as refused:  # no layer installed: the plugin's own refusal
            wall.world_layer("datacentres")
        status, out = ask("world_layer", "datacentres")
        assert status == 400 and out["words"] == str(refused.value)
        status, out = ask("world_pick", "clear")
        assert status == 200 and "answer" in out  # (what the pick says is the plugin's)
        assert [x for x in lines if " asked " in x] == ["platform: wall asked world_pick (1 argument)"]
        said = {(r["what"], r["kind"]) for r in app.traffic.recent() if r["to"] == "wall"}
        assert {("netstat", "read"), ("world_layer", "read"), ("world_pick", "ask")} <= said
    finally:
        app.stop()


@pytest.mark.usefixtures("no_outside")
def test_the_page_loads_a_globes_layers_through_the_platform_and_draws_flagged_only_where_it_is_named():
    """0.33.0: the page gives the globe its loader (layerLoader: the spec's layer_hook, asked through the platform with
    the layer's id, only where the platform may ask the plugin for it; the answer's geometry, a refusal's own words,
    worded as a tab's failed ask is: refusalWords) and a key its layers' switches are remembered under (the plugin's
    name and the tab's), and gives the loader again when the way to the layers changed (a platform started again on a
    newer library, the page left open); a globe whose way is gone is made anew with none, since the library's draw
    keeps the loader it has when given none. "Flagged only" is drawn only where the page's filters name it, and holds
    nothing where it is not drawn (B-critique M13); since when is drawn in the words the plugin sends, the row's own
    time in its tooltip; how long a connection is up says its days past a day, as the plugin's own tables do. The
    page's script read from its folder: no port opened, nothing served (the guard, no_outside)."""
    js = page_script()
    words = "(e.answer && e.answer.words) || e.message || 'it did not answer'"
    assert js.count(words) == 1  # one way for both: a tab's page and a globe's layer
    assert f"const refusalWords = (e) => String({words});" in js
    assert "(e) => ({ page: null, error: refusalWords(e) }))" in _between(js, "function askOf(v) {", "async function")
    loader = _between(js, "const layerLoader = (m, spec) => {", "\n  };")
    assert "const hook = typeof spec.layer_hook === 'string' ? spec.layer_hook : '', name = m.name;" in loader
    assert "return hook && (m.asks || []).includes(hook)" in loader and ": null;" in loader
    assert "(id) => api('POST', `api/machines/${enc(name)}/ask`, { hook, args: [String(id)] })" in loader
    assert ".then((out) => (out ? out.answer : null), (e) => { throw new Error(refusalWords(e)); })" in loader
    assert "m.status" not in loader  # what it keeps of the plugin: its name alone, never its status
    place = _between(js, "function placeGlobe(on) {", "function dropGlobe(v) {")
    assert "const load = layerLoader(m, spec), way = load ? spec.layer_hook : '';" in place
    gone = "if (v.globe && v.globeWay && !way) dropGlobe(v);"  # its way gone: made anew, with none
    assert gone in place and place.index(gone) < place.index("if (!v.globeEl) {") < place.index("const slot = ")
    assert "if (!v.globe || v.globeWay !== way) {" in place and "v.globeWay = way;" in place
    assert "} else if (v.globeSpec !== spec) v.globe.update(spec);" in place
    assert "v.globeWay = '';" in _between(js, "function dropGlobe(v) {", "// its charts (page.charts")
    assert "globeSpec: null, globeWay: '' };" in js
    flows = _between(js, "const FLOW_COLUMNS = {", "function drawTab(name) {")
    assert ("const flaggable = (f) => !!f.filters && typeof f.filters === 'object' && ownOf(f.filters, 'flagged') "
            "!== undefined;") in flows
    html = _between(flows, "function flowsHtml(m, t, v) {", "function drawFlows(on, box) {")
    assert "const flagged = !flaggable(f) ? ''" in html and "\n      + flagged\n" in html.replace("\r\n", "\n")
    assert html.count("flow-flagged") == 1  # drawn in one place alone, behind the condition
    assert "if (!flaggable(f)) flowFilters[key].flagged = false;" in _between(flows, "function filterOf(key, f) {",
                                                                               "function dirsOf(f, x) {")
    assert "if (c.key === 'since') return flowSince(r, v);" in flows and "since: 'Since'" in flows
    since = _between(flows, "function flowSince(r, v) {", "\n  }")
    assert "const d = words ? momentOf(ownOf(r, 'time')) : null;" in since and "if (!d) return esc(words);" in since
    assert '">${esc(words)}</time>`;' in since and "toLocaleTimeString" not in since  # the words as sent, not a time
    assert "const d = momentOf(v);" in _between(flows, "function flowTime(v) {", "\n  }")
    lasted = _between(flows, "function lasted(v) {", "\n  }")  # "Up for": three days are "3 d 0 h", not "72.0 h"
    days = "if (s >= 86400) return `${Math.floor(s / 86400).toLocaleString()} d ${Math.floor((s % 86400) / 3600)} h`;"
    assert days in lasted and lasted.index("return '–';") < lasted.index(days) < lasted.index("return s < 1 ?")
