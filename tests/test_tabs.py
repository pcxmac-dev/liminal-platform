"""0.22.0 (the user, 2026-11-11: "now i need tabs for the main page of each plugin, each plugin has a tab for the API, and
on the APIs organize each API description so that they can expand and contract so they take up less space, kind of
like the firewall"): a plugin's page has tabs beside its title, Main and API; the API tab holds what it attaches to,
each API a line that opens. The page's script and styles, on stand-in plugins: nothing of this machine is asked.
0.32.0 (the user, 2026-11-16: "for all apps, and all plugins, there should be an external api tab, and an internal
api tab"): the API tab is External API, Internal API beside it (tests/test_internal_page.py). The page's files are
read as text from the package and the statuses asked of the app in this process: nothing is served, started or
reached."""
from __future__ import annotations

import json
from importlib import resources

import pytest

from conftest import Box, Wall

import liminal_platform.app as app_mod
from liminal_platform.app import PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside")  # nothing started, served or reached (tests/conftest.py)

STATIC = resources.files("liminal_platform") / "static"  # what the platform serves its page from


def test_a_plugins_page_has_tabs_and_its_apis_a_tab_of_their_own():
    js, css = (STATIC / "platform.js").read_bytes(), (STATIC / "platform.css").read_bytes()
    # the tabs: Main, External API (what was the API tab: its cards) and Internal API, then the plugin's own
    # (test_plugin_tabs.py); Internal API only where the library has internal.js (test_internal_page.py)
    tabs = b"const OWN_TABS = [{ id: 'main', title: () => 'Main' }, { id: 'external', title: () => 'External API' },"
    assert tabs in js and b"{ id: 'internal', title: () => 'Internal API' }];" in js
    assert b"const tabsOf = (p) => [...OWN_TABS, ...declaredTabs(p)];" in js and b"const TABS = " not in js
    assert b'<nav class="tabs" role="tablist"' in js and b'role="tab" class="tab" aria-selected="${tabOf(p) === t.id}" data-tab="${t.id}"' in js
    # beside the title, before the switches, on a machine plugin's page and an AI assistant's
    assert b"<h2>${esc(m.title)}</h2>${tabsRow(m)}${switchRow(m)}</div>" in js and b"<h2>${esc(a.title)}</h2>${tabsRow(a)}${switchRow(a)}</div>" in js
    # the tab is in the address after the plugin's name: a reload or a link keeps it; Main is the plugin's own address
    assert b"const hashParts = () => decodeURIComponent(location.hash.slice(1)).split('/');" in js
    assert b"const selected = () => hashParts()[0] || 'machine';" in js
    assert b"location.hash = tb.dataset.tab === 'main' ? tb.dataset.machine : `${tb.dataset.machine}/${tb.dataset.tab}`;" in js
    assert js.index(b"e.target.closest('button.tab[data-tab]')") < js.index(b"const pick = e.target.closest('[data-select]');")
    # no tabs for one known by its name alone, nor from a platform that sends no apis (before 0.20.0)
    assert b"const hasTabs = (p) => !!p && !pending(p) && !!window.LiminalApis && Array.isArray(p.apis);" in js
    # the External API tab: the cards alone, folded (liminal-libs 1.50.0); Main: no cards
    assert b"if (tabOf(m) === 'external') return head + apiCard(m);" in js and b"fold: true });" in js
    main = js[js.index(b"function pluginData(m)"):js.index(b"function assistantData(a)")]
    assert main.count(b"apiCard(m)") == 1
    # shown, a refresh draws only its cards (on Internal API: its box) again when they changed, the focus kept
    assert b"const onApi = (tabOf(m) === 'external' && !!$(`api-${m.name}`))" in js
    assert b"|| (tabOf(m) === 'internal' && !!$(`internal-${m.name}`));" in js
    assert b"if (!onApi) keepFocus(() => {" in js
    assert b"if (ac) redrawKept(ac, apiInner(m), drawnApis, m.name);" in js
    assert b"if (at >= 0 && parts()[at]) parts()[at].focus({ preventScroll: true });" in js
    # the tab picked keeps the focus once the page is drawn again
    assert b"const on = data.querySelector('button.tab[aria-selected=\"true\"]');" in js
    for part in (b".data-head .tabs {", b"margin-right: auto;", b'.tabs .tab[aria-selected="true"] { color: var(--accent); border-bottom-color: var(--accent); }'):
        assert part in css, part


def test_the_machines_carry_what_the_api_tab_draws(monkeypatch):
    monkeypatch.setattr(app_mod, "facts", lambda: {"system": "a stand-in"})  # (Python's processor() may start uname)
    app = PlatformApp(log=lambda m: None, machines={"box": Box(), "wall": Wall()}, assistants={})  # none of this PC's
    status, m = app.api(None, "GET", "/api/machines/box", {}, None)[:2]
    assert status == 200 and json.dumps(m)  # as it is sent
    assert isinstance(m["apis"], list) and "apiFacts" in m and "pluginApi" in m  # the tab is there for every plugin
    whole = app.api(None, "GET", "/api/status", {}, None)[1]["machines"]["box"]
    assert whole["apis"] == m["apis"]
