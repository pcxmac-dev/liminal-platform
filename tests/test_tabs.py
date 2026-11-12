"""0.22.0 (the user, 2026-11-11: "now i need tabs for the main page of each plugin, each plugin has a tab for the API, and
on the APIs organize each API description so that they can expand and contract so they take up less space, kind of
like the firewall"): a plugin's page has tabs beside its title, Main and API; the API tab holds what it attaches to,
each API a line that opens. The page's script and styles, on stand-in plugins: nothing of this machine is asked."""
from __future__ import annotations

from test_app import _call


def test_a_plugins_page_has_tabs_and_its_apis_a_tab_of_their_own(served):
    app, port, lines, box = served
    js, css = _call(port, "GET", "/platform.js")[1], _call(port, "GET", "/platform.css")[1]
    # the tabs, a list the next one is added to; "APIs" when a plugin attaches to several
    # 0.24.1 (the user: "tabs should look more like this \"Windows Firewall___/: API___/: MISC\""): the plugin's name is the
    # first tab, the page's heading still; one known by its name alone has its name as a plain heading
    assert b"const TABS = [{ id: 'main', title: (p) => p.title }, { id: 'api', title: () => 'API' }];" in js
    assert b'<nav class="tabs" role="tablist"' in js and b'role="tab" class="tab${i ? \'\' : \' title\'}" aria-selected="${tabOf(p) === t.id}" data-tab="${t.id}"' in js
    assert b"const titleRow = (p) => (!hasTabs(p) ? `<h2>${esc(p.title)}</h2>`" in js
    # 0.24.2 (the user: "the tabs for the plugins should mirror the format of a URI address [plugin] : /  / module1 /
    # module2 / module3"): the name, a colon and two strokes, then the modules with a stroke between two
    assert b"return i ? (i > 1 ? stroke('/') : '') + tab : `<h2>${tab}</h2>${stroke(':')}${stroke('/')}${stroke('/')}`;" in js
    assert b'const stroke = (s) => `<span class="sep" aria-hidden="true">${s}</span>`;' in js
    # before the switches, on a machine plugin's page and an AI assistant's
    assert b'<div class="data-head">${titleRow(m)}${switchRow(m)}</div>' in js and b'<div class="data-head">${titleRow(a)}${switchRow(a)}</div>' in js
    # the tab is in the address after the plugin's name: a reload or a link keeps it; Main is the plugin's own address
    assert b"const hashParts = () => decodeURIComponent(location.hash.slice(1)).split('/');" in js
    assert b"const selected = () => hashParts()[0] || 'machine';" in js
    assert b"location.hash = tb.dataset.tab === 'main' ? tb.dataset.machine : `${tb.dataset.machine}/${tb.dataset.tab}`;" in js
    assert js.index(b"e.target.closest('button.tab[data-tab]')") < js.index(b"const pick = e.target.closest('[data-select]');")
    # no tabs for one known by its name alone, nor from a platform that sends no apis (before 0.20.0)
    assert b"const hasTabs = (p) => !!p && !pending(p) && !!window.LiminalApis && Array.isArray(p.apis);" in js
    # the API tab: the cards alone, folded (liminal-libs 1.50.0); Main: no cards
    assert b"if (tabOf(m) === 'api') return head + apiCard(m);" in js and b"fold: true });" in js
    main = js[js.index(b"function pluginData(m)"):js.index(b"function assistantData(a)")]
    assert main.count(b"apiCard(m)") == 1
    # shown, a refresh draws only its cards again when they changed, what had the focus keeping it
    assert b"const onApi = tabOf(m) === 'api' && !!$(`api-${m.name}`);" in js and b"if (!onApi) keepFocus(() => {" in js
    assert b"if (at >= 0 && parts(ac)[at]) parts(ac)[at].focus({ preventScroll: true });" in js
    # the tab picked keeps the focus once the page is drawn again
    assert b"const on = data.querySelector('button.tab[aria-selected=\"true\"]');" in js
    # the strokes are the address's own, said to no screen reader; the one shown is in the accent, on a line of it
    for part in (b".data-head .tabs {", b"margin-right: auto;", b".tabs .sep { padding: 0 5px; color: var(--muted);",
                 b"border-bottom: 2px solid transparent;", b".tabs .tab.title { padding-left: 0; font: inherit;",
                 b'.tabs .tab[aria-selected="true"] { color: var(--accent); border-bottom-color: var(--accent); background: none; }'):
        assert part in css, part
    assert b"skewX(" not in css and b'.tabs .tab:not(.title)::before' not in css  # 0.24.1's strokes and colons are gone


def test_the_machines_carry_what_the_api_tab_draws(served):
    app, port, lines, box = served
    m = _call(port, "GET", "/api/machines/box")[1]
    assert isinstance(m["apis"], list) and "apiFacts" in m and "pluginApi" in m  # the tab is there for every plugin
    whole = _call(port, "GET", "/api/status")[1]["machines"]["box"]
    assert whole["apis"] == m["apis"]
