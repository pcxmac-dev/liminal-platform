"""0.32.0 (the user, 2026-11-16: "for all apps, and all plugins, there should be an external api tab, and an internal
api tab, the internal api is for interfaces the plugin shares with the rest of the app, the external should be all the
SDKs/APIs the plugin associates with"; 2026-11-17: "also, i asked for a second tab for all plugins which describe the
internal API like structure that the app code can work with", "i don't see it", "all plugins all apps"): every plugin's
page has Main, External API and Internal API beside its title, an address naming the old API tab opens External API,
and the platform's own two views are an entry under This machine. The page is served live from the checkout to a
platform already running, so it still draws with a server that sends no `internal` and has no GET api/app/apis, and with
a library that has no internal.js. The page's files are read as text from the package: nothing is served, started or
asked."""
from __future__ import annotations

import re
from importlib import resources

import pytest

pytestmark = pytest.mark.usefixtures("no_outside")  # nothing started, served or reached (tests/conftest.py)

STATIC = resources.files("liminal_platform") / "static"


def _text(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    """The part of a text from `start` to the first `end` after it."""
    at = text.index(start)
    return text[at:text.index(end, at + len(start))]


def test_every_plugins_page_has_main_external_api_and_internal_api():
    js = _text("platform.js")
    # beside the title (tabsRow), on a machine plugin's page and an AI assistant's alike
    tabs = "const OWN_TABS = [{ id: 'main', title: () => 'Main' }, { id: 'external', title: () => 'External API' },"
    assert tabs in js and "{ id: 'internal', title: () => 'Internal API' }];" in js
    # a library without internal.js: Main and External API (internal.js is a 404 there, so nothing defines it)
    pop = "if (!window.LiminalInternal) OWN_TABS.pop();"
    assert js.index(tabs) < js.index(pop) < js.index("function declaredTabs(p) {")
    # no plugin's tab takes the page's ids or the old API tab's, after the pop and from an older server's tabs_of too
    assert "const seen = new Set([...OWN_TABS.map((o) => o.id), 'api', 'external', 'internal']), out = [];" in js
    # each one's page, whatever the plugin's state, before its own tabs and its Main
    plugin = _between(js, "function pluginData(m) {", "function assistantData(a) {")
    assistant = _between(js, "function assistantData(a) {", "// -- a plugin's own tabs (0.27.0;")
    assert "if (tabOf(m) === 'external') return head + apiCard(m);" in plugin
    assert "if (tabOf(m) === 'internal') return head + internalCard(m);" in plugin
    assert plugin.count("apiCard(m)") == 1 and plugin.count("internalCard(m)") == 1
    assert plugin.index("internalCard(m)") < plugin.index("const own = ownTabOf(m);")
    assert "if (tabOf(a) === 'external') return head + apiCard(a);" in assistant
    assert "if (tabOf(a) === 'internal') return head + internalCard(a);" in assistant


def test_an_address_naming_the_old_api_tab_opens_external_api():
    js = _text("platform.js")
    tab_of = _between(js, "const tabOf = (p) => {", "const ownTabOf = ")
    assert "const h = hashParts()[1], t = h === 'api' ? 'external' : h;" in tab_of
    assert "return hasTabs(p) && tabsOf(p).some((x) => x.id === t) ? t : 'main';" in tab_of
    # written again in place, first in every draw: #name/api as #name/external; the platform's own #app/api and
    # #app/external as #app, its External API's address (C-critique S7). No hashchange, so no second draw
    old = _between(js, "function oldAddress() {", "function draw() {")
    assert "name && tab === 'api' ? `#${enc(name)}/external`" in old
    assert "mine && (tab === 'api' || tab === 'external') ? `#${OWN}`" in old
    assert "if (again) history.replaceState(null, '', again);" in old and "location.hash" not in old
    draw = _between(js, "function draw() {", "// the platform not answering, said:")
    assert draw.index("oldAddress();") < draw.index("if (!st) return;")


def test_the_internal_api_is_the_librarys_drawing_of_what_the_status_says():
    js = _text("platform.js")
    inner = _between(js, "function internalInner(p) {", "function internalCard(p) {")
    assert "if (!window.LiminalInternal) return '';" in inner
    assert "const opts = { owner: p.name, title: p.title, app, seen: '#connections', pick: pickOf };" in inner
    assert "return window.LiminalInternal.html(p.internal, opts);" in inner
    # what an ask finds here and who asks a service come in the data (C-critique S3), not from the page's other plugins
    assert "others" not in inner
    # a drawing that throws on a shape it does not know is said in its place: the rest of the page is drawn
    assert "Its Internal API could not be drawn: ${e.message}" in inner
    # its own box, drawn again on a refresh only when it changed, what had the focus in it keeping it
    card = _between(js, "function internalCard(p) {", "const icon = window.LiminalIcons.icon;")
    assert "drawnInternal[p.name] = internalInner(p);" in card and 'id="internal-${esc(p.name)}"' in card
    shown = _between(js, "function redrawShown(m) {", "function setSpan(v) {")
    assert "if (ic) redrawKept(ic, internalInner(m), drawnInternal, m.name);" in shown
    kept = _between(js, "function redrawKept(box, html, drawn, name) {", "function redrawShown(m) {")  # the cards' too
    assert "if (html === drawn[name]) return;" in kept and "drawn[name] = html;" in kept
    assert "if (at >= 0 && parts()[at]) parts()[at].focus({ preventScroll: true });" in kept
    # a plugin's name drawn by the library (an app's plugins, a plugin's asks) is a button to its page
    assert "const pickOf = (n) => `data-select=\"${esc(n)}\"`;" in js
    tab, pick = "e.target.closest('button.tab[data-tab]')", "const pick = e.target.closest('[data-select]');"
    assert js.index(tab) < js.index(pick)


def test_a_platform_that_sends_no_internal_is_said_in_words_with_no_number():
    """C-critique B2 and M6: a page served to a platform started before (or on an older liminal-libs) says so in the
    platform's words, its hooks' names after when its status has them; no release number in what the page says."""
    js = _text("platform.js")
    inner = _between(js, "function internalInner(p) {", "function internalCard(p) {")
    assert "if (!p.internal || typeof p.internal !== 'object') {" in inner
    first = "`This platform was started before it could say what ${p.title} shares with it, or runs on an older `"
    assert first in inner and "+ 'liminal-libs: restart the platform to see it.';" in inner
    assert "const hooks = Array.isArray(p.hooks) ? p.hooks.map(String) : [];" in inner
    assert "const named = hooks.length ? ` Its hooks, by name: ${hooks.join(', ')}.` : '';" in inner
    assert 'return `<p class="muted">${esc(older + named)}</p>`;' in inner  # every word of it escaped
    # the platform's own views on such a platform: GET api/app/apis is a 404 there
    assert "const OWN_OLDER = 'This platform was started before it could show its own APIs, or runs on an older " in js
    assert "+ 'restart the platform to see them.';" in js
    for words in (first, "liminal-libs: restart the platform to see it.", "Its hooks, by name:",
                  "This platform was started before it could show its own APIs, or runs on an older liminal-libs: ",
                  "restart the platform to see them.", "its own External and Internal API",
                  "the platform itself: what it attaches to, and what it offers its plugins and other apps",
                  "The APIs and SDKs it associates with", "It declares no outside API or SDK.",
                  "Its answer says nothing of what it offers its plugins and other apps."):
        assert words in js and not re.search(r"\d", words), words


def test_a_plugin_the_library_could_not_read_is_said_so_with_no_restart():
    """A platform that has the library but could not read one plugin sends `internalError` (app.py's internal_card),
    which only such a platform sends: its tab says those words, its hooks' names after, before the sentence for a
    platform started before, which would wrongly ask for a restart."""
    js = _text("platform.js")
    inner = _between(js, "function internalInner(p) {", "function internalCard(p) {")
    error = "if (typeof p.internalError === 'string' && p.internalError) {"
    assert error in inner and inner.index(error) < inner.index("if (!p.internal || typeof p.internal !== 'object') {")
    said = _between(inner, error, "\n    }")
    assert 'return `<p class="error">${esc(p.internalError.slice(0, 400) + named)}</p>`;' in said  # escaped, bounded
    assert inner.index("const named = ") < inner.index(error)


def test_the_platforms_own_two_views_are_an_entry_under_this_machine():
    js = _text("platform.js")
    assert "const OWN = 'app';" in js and "const ownShown = () => selected() === OWN && !!window.LiminalInternal;" in js
    listed = _between(js, "function drawList() {", "// -- the middle: the selected one's data")
    entry = "(window.LiminalInternal ? item(OWN, 'sort', st.app.title || 'Platform',"
    assert entry in listed and "'its own External and Internal API')" in listed
    assert listed.index("item(CODEBASE,") < listed.index(entry) < listed.index("SECTIONS.map(")
    # its two tabs beside its title: External API at the entry's own address (#app: the click writes the bare name for
    # "main"), Internal API at #app/internal (C-critique S7); the tabs' keys serve them as a plugin's
    own = _between(js, "function ownData() {", "function ownSide() {")
    assert "const tab = hashParts()[1] === 'internal' ? 'internal' : 'external';" in own
    both = "button('main', 'External API', tab === 'external') + button('internal', 'Internal API', tab === 'internal')"
    assert both in own and 'data-tab="${id}" data-machine="${OWN}"' in own and 'role="tablist"' in own
    assert "location.hash = tb.dataset.tab === 'main' ? tb.dataset.machine : `${tb.dataset.machine}/" in js
    keys = "const all = [...tb.parentElement.querySelectorAll('button.tab[data-tab]')], at = all.indexOf(tb);"
    assert keys in js
    # External: the library's cards, folded; Internal: the library's drawing of the app's own answer
    assert "window.LiminalApis.html(d.apis, d.apiFacts, { owner: 'app:platform', fold: true," in own
    assert "title: 'The APIs and SDKs it associates with', empty: 'It declares no outside API or SDK.' });" in own
    assert "const opts = { owner: 'app:platform', title, pick: pickOf, seen: '#connections' };" in own
    assert "? (inner ? window.LiminalInternal.html(inner, opts)" in own
    assert "if (!got.data) return `${head}<p class=\"muted\" role=\"status\">" in own  # not in yet: said
    assert "${esc(got.error || 'Asking the platform…')}</p>`;" in own
    # asked when the entry is shown and its answer is a minute old, never by a timer; an older platform said so
    load = _between(js, "async function loadOwn() {", "function ownData() {")
    assert "data = await api('GET', 'api/app/apis');" in load and "older = e.status === 404;" in load
    assert "if (was.asking || (was.at && Date.now() - was.at < OWN_AGAIN_MS)) return;" in load
    assert "const OWN_AGAIN_MS = 60000;" in js and "setTimeout" not in load and "setInterval" not in load
    assert "if (ownShown()) loadOwn();" in _between(js, "function draw() {", "// the platform not answering, said:")
    # tested before a plugin of its name in both panes: one named so is shadowed, as one named connections is
    data = _between(js, "function drawData() {", "function drawAround(panel, html, name) {")
    first = "const m = mine ? null : st.machines[sel], a = mine ? null : (st.assistants || []).find("
    assert "const mine = ownShown();" in data and first in data
    assert data.index("mine ? ownData()") < data.index("m ? pluginData(m)")
    side = _between(js, "function drawSide() {", "function oldAddress() {")
    assert side.index("if (ownShown()) { side.innerHTML = ownSide(); return; }") < side.index("m ? pluginSide(m)")


def test_the_own_entrys_side_counts_its_plugins_as_the_drawing_does():
    """Its side says how many plugins the platform knows and how many are attached now (a disabled or not valid one is
    known, not attached), as the library's drawing of the same answer does (internal.js's pluginsWords)."""
    js = _text("platform.js")
    side = _between(js, "function ownSide() {", "const CLASS_ORDER = ")
    assert "Plugins attached" not in side  # (it once counted every plugin it knows as attached)
    assert "const known = Array.isArray(i.plugins) ? i.plugins.filter((p) => p && typeof p.name === 'string'" in side
    assert "const attached = known ? known.filter((p) => p.attached !== false).length : 0;" in side
    assert "attached === known.length ? `${attached} attached`" in side
    assert ": `${known.length}, ${attached} attached`;" in side and "['Plugins', plugins]," in side


def test_the_librarys_drawing_is_loaded_in_its_place_and_the_tabs_wrap_on_a_phone():
    page = _text("index.html")
    names = ("apis.js", "internal.js", "codebase.js", "platform.js")
    order = [page.index(f'<script src="{name}"></script>') for name in names]
    assert order == sorted(order)
    # C-critique S6: Main, External API, Internal API and a plugin's own do not fit a phone's width on one line
    css = _text("platform.css")
    assert re.search(r"@media \(max-width: 700px\) \{\s*\.data-head \{ flex-wrap: wrap; \}\s*"
                     r"\.data-head \.tabs \{ flex-wrap: wrap; row-gap: 2px; \}", css)
