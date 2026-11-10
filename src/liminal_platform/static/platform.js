// The platform's page (the user, 2026-11-07: "the specifics are on the right hand side before the icons on the very
// right, and the larger window from the left to right is used to describe or display data"; "plugins are better
// described as a list of details w/ the specifics in the right hand column, just like the charts had a right hand
// column"; "active plugins, will be part of the tray on the very right side"; "use the black boundary (around the
// icon) to serve as the tray border, it can stretch vertically to include more icons or plugins"):
//   the list (this machine, its machine plugins, the AI assistants) | the selected one's data | its specifics | the tray
// The tray is the platform's chip, a divider, then an icon per active plugin, all in the one dark box. A right click
// on a plugin's icon offers to disable it ("allow me to right click on the icons to disable them on the right icon
// menu"); the switch at the head of a plugin's page enables or disables it ("enable disable switch (left to right) on
// the plugin description when selected in the left menu"). A plugin's own figures are drawn in the middle: its
// status's `charts` (the library's charts.js, asked again at the plugin's interval while shown), `tables`,
// `options` (choices it is asked to make: the Preferences plugin's themes, applied to this page at once), `actions`
// (buttons asking one of its hooks by name: the Namecheap plugin's Refresh and Update DNS now) and `forms` (one of
// its hooks asked with what the user fills in, once the user has confirmed the exact change: the Namecheap plugin's
// records set and removed). The selection is the address's #name (#wsl-ubuntu), so a reload or a link keeps it. API
// paths are relative, so the page works under a super app's prefix too.
// 0.17.0 (the user, 2026-11-10: "let's do an update. I want to support touch as well as mouse clicking on the interface
// ... We'll make sure it works across all apps"; "Support for virtual keyboard on tablets and phones"): a finger, a pen and
// the on-screen keyboard through the library's touch.js (LiminalTouch): the tray's menu by a long press (menu.js), words a
// finger needs shown on a touch screen, every field's keyboard, no keyboard called up before a field is tapped, the
// login terminal kept alive across redraws with a row of the keys a phone's keyboard lacks. A mouse and a hardware
// keyboard work as they did.
(() => {
  'use strict';

  const WRITE = { 'Content-Type': 'application/json', 'X-Liminal-Charts': '1' };
  const $ = (id) => document.getElementById(id);
  const esc = window.LiminalIcons.esc;
  const icon = window.LiminalIcons.icon;
  const Charts = window.LiminalCharts;
  const list = $('list'), data = $('data'), side = $('side'), rail = $('rail');
  if (new URLSearchParams(location.search).get('embedded') === '1') document.body.classList.add('embedded');
  let st = null;  // the last GET api/status
  let tray = null;  // the last GET api/tray
  let span = 'recent';  // the charts' range: the last ten minutes, or the last day
  const day = {};  // a plugin's charts of the last day, by name (asked apart: they move every 30 s)
  let live = null;  // the timer asking the shown plugin again
  let gen = 0;  // bumped by every change of what the page holds: an answer asked before it is dropped
  const checks = {};  // a plugin's check of this PC, by name: {at, data} | {at, loading} | {at, error}
  const jobs = {};  // a plugin's job panel (an install, an update), by name: {term, offset, open, action, running, ok, timer}
  const shells = {};  // a plugin's login terminal, by name: {term, offset, alive, title, queue, timer, sending}
  const PREPARING = ['wsl', 'update', 'version'];  // setup steps that prepare this PC: never locked by its check
  const enc = encodeURIComponent;
  const hasHook = (m, h) => (m.hooks || []).includes(h);
  const selected = () => decodeURIComponent(location.hash.slice(1)) || 'machine';
  const label = (k) => k.replace(/([A-Z])/g, ' $1').toLowerCase();
  // a finger, a pen and the on-screen keyboard (0.17.0, liminal-libs 1.42.0's touch.js, loaded before this file); without
  // it, the page as a mouse and a keyboard have it
  const T = window.LiminalTouch || null;
  const fingered = () => !!T && (T.lastInput === 'touch' || T.lastInput === 'pen');  // the user's last move was a finger's
  const mayFocus = () => !T || T.mayFocus();  // a field focused by code calls up no keyboard unasked
  const autofocus = (el, options) => { if (!el) return false; if (T) return T.autofocus(el, options); el.focus(options); return true; };
  const kb = (kind, more) => (T ? T.keyboard(kind, more) : 'autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false"');  // a field's keyboard

  async function api(method, path, body) {
    let r;
    try { r = await fetch(path, { method, headers: method === 'GET' ? {} : WRITE, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin' }); }
    catch (e) { throw new Error(`The platform is not answering at ${location.host}: it may have stopped. Start it again, then reload this page.`); }
    let out = null;
    try { out = await r.json(); } catch (e) { out = null; }
    if (!r.ok) {  // the answer kept: a hook's refusal holds the plugin's words and what accepts it (a form's)
      const e = new Error((out && out.error) || `the platform answered ${r.status}`);
      e.status = r.status;
      e.answer = out;
      throw e;
    }
    return out;
  }

  // a plugin's state (the user: "if a plugin is not in a valid state it has to be disabled, and thus shaded out on the left
  // side"): disabled by the user (the switch, the tray's right click), or not valid (set up for Liminal: its own word, why),
  // disabled until it is; both shaded in the list and out of the tray
  const userOff = (m) => m.enabled === false;
  const invalid = (m) => !userOff(m) && (m.state === 'invalid' || m.valid === false);
  const off = (m) => userOff(m) || invalid(m);
  const whyOf = (m) => m.why || 'not valid';
  const notHere = (m) => invalid(m) && !!(m.status && m.status.applies === false);  // not for this machine at all: no setup offered
  const chipOf = (m) => (off(m) ? '<span class="chip">disabled</span>' : '<span class="chip up">active</span>');
  const stateLine = (m) => (userOff(m) ? 'disabled' : notHere(m) ? `not for this machine: ${whyOf(m)}` : invalid(m) ? `disabled: ${whyOf(m)}` : (m.status && m.status.summary) || 'active');
  function say(name, text) {  // a plugin's trouble, at the head of its page
    const el = $(`err-${name}`);
    if (el) el.textContent = text || '';
  }

  // -- the tray: the chip, a divider, an icon per active plugin, in the one dark box ------------------------
  function drawRail() {  // the active plugins, none hidden (0.10.2: the machine plugins, then the AI assistants)
    const sel = selected();
    const items = ((tray && tray.items) || []).filter((i) => { const p = i.kind === 'plugin' && st ? pluginOf(i.id) : null; return i.kind === 'plugin' && !(p && (off(p) || p.hidden)); });
    // a plugin's icon: its name and the right click in its tooltip; a long press (menu.js, 0.17.0) opens the same menu,
    // headed by its name alone (its data-tip)
    rail.innerHTML = `<button type="button" id="railChip" class="master${sel === 'machine' ? ' active' : ''}" data-select="machine" title="${esc((tray && tray.title) || 'Platform')}: this machine">${icon('chip', 30)}</button>`
      + (items.length ? '<hr>' + items.map((i) => `<button type="button" class="${sel === i.id ? 'active' : ''}" data-select="${esc(i.id)}" title="${esc(i.title)} (right click: hide or disable)" data-tip="${esc(i.title)}">${icon(i.icon || 'chip', 24)}</button>`).join('') : '');
  }

  // the tray as the platform will say it once it answers: the active plugins not hidden, machines then assistants
  function trayFollows(name, present) {
    if (!tray || !st) return;
    const p = pluginOf(name);
    const order = [...Object.keys(st.machines), ...(st.assistants || []).map((a) => a.name)];
    const own = tray.items.filter((i) => i.kind !== 'plugin');
    const plugins = tray.items.filter((i) => i.kind === 'plugin' && i.id !== name);
    if (present && p && !p.hidden) plugins.push({ id: name, icon: p.icon || 'chip', title: p.title, kind: 'plugin', app: tray.app });
    plugins.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
    tray = { ...tray, items: [...own, ...plugins] };
  }

  // -- the list: this machine, its machine plugins, the AI assistants -----------------------------------
  function drawList() {
    const sel = selected();
    const item = (id, ic, title, sub, cls = '') => `<button type="button" class="item${sel === id ? ' active' : ''}${cls}" data-select="${esc(id)}">${icon(ic, 20)}
      <span class="what"><span>${esc(title)}</span><span class="sub">${esc(sub)}</span></span></button>`;
    const f = st.machine;
    const machines = Object.values(st.machines);
    list.innerHTML = `<h2>Platform</h2><div class="muted small">the software and hardware under the framework</div>`
      + `<h4>This machine</h4>${item('machine', 'chip', f.host, `${f.system} ${f.release} · ${f.cpus} cpus`)}`
      + item(CONNECTIONS, 'plug', 'Connections', 'who talks to whom, as it happens')
      + `<h4>Machine plugins</h4>` + (machines.length ? machines.map((m) => item(m.name, m.icon || 'chip', m.title, stateLine(m), off(m) ? ' off' : '')).join('')
        : '<div class="muted small">None installed: WSL, firewall and admin plugins set this machine up.</div>')
      + ((st.assistants || []).length ? `<h4>AI assistants</h4>` + st.assistants.map((a) => item(a.name, a.icon || 'analysis', a.title, off(a) ? stateLine(a) : (a.vendor || a.about), off(a) ? ' off' : '')).join('') : '');
  }

  // -- the middle: the selected one's data ------------------------------------------------------------
  function instancesTable() {
    if (!st.instances.length) return `<h4>Docker instances</h4><div class="muted small">None yet: Docker here, a context, or a machine plugin with Docker inside.</div>`;
    return `<h4>Docker instances</h4><table class="list"><thead><tr><th>Name</th><th>Where</th><th>Command</th><th>From</th></tr></thead><tbody>`
      + st.instances.map((i) => `<tr><td class="mono">${esc(i.name)}</td><td>${esc(i.where)}</td><td class="mono">${esc(i.command)}</td><td>${esc(i.source)}</td></tr>`).join('') + `</tbody></table>`;
  }

  function machineData() {
    const rows = Object.values(st.machines).map((m) => `<tr class="pick" data-select="${esc(m.name)}"><td>${icon(m.icon || 'chip', 18)}</td>
      <td>${esc(m.title)}</td><td class="muted">${esc(m.version || '')}</td><td>${chipOf(m)}</td><td>${esc(stateLine(m))}</td></tr>`).join('');
    return `<h2>${esc(st.machine.host)}</h2><div class="muted small">this machine, and the plugins that set it up for the framework</div>
      <h4>Machine plugins</h4>${rows ? `<table class="list"><thead><tr><th></th><th>Plugin</th><th>Version</th><th>State</th><th>What it says</th></tr></thead><tbody>${rows}</tbody></table>`
        : '<div class="muted small">None installed.</div>'}
      ${instancesTable()}`;
  }

  function tables(m) {
    // what a plugin's status lists: Liminal's rules (a firewall), services, startups, processes (the admin)
    const s = m.status || {}, can = new Set(m.asks || []), out = [];
    const btn = (hook, args, text) => (can.has(hook) ? `<button type="button" class="ask" data-machine="${esc(m.name)}" data-hook="${esc(hook)}" data-args='${esc(JSON.stringify(args))}'>${esc(text)}</button>` : '');
    if (Array.isArray(s.rules)) {
      out.push(`<h4>Liminal's rules</h4>` + (s.rules.length ? `<table class="list"><thead><tr><th>Rule</th><th>Ports</th><th>Direction</th><th>From</th><th></th></tr></thead><tbody>` + s.rules.map((r) =>
        `<tr><td>${esc(r.label)}</td><td class="mono">${esc((r.ports || []).join(', ') || 'every')}/${esc(r.protocol)}</td><td>${esc(r.direction)} ${esc(r.action)}</td><td>${esc(r.remote)}</td>`
        + `<td>${r.owned ? btn('remove', [r.name], 'Remove') : ''}</td></tr>`).join('') + `</tbody></table>` : '<div class="muted small">None: its setup adds what the framework\'s services need.</div>'));
    }
    if (Array.isArray(s.services) && s.services.length) {
      out.push(`<h4>Services</h4><table class="list"><thead><tr><th>Service</th><th>State</th><th>Start</th><th>For</th><th></th></tr></thead><tbody>` + s.services.map((v) =>
        `<tr><td class="mono">${esc(v.name)}</td><td>${esc(v.state)}</td><td>${esc(v.startup)}</td><td class="muted">${esc(v.usedFor)}</td><td>`
        + (v.state === 'absent' ? '' : v.state === 'running' ? btn('service', [v.name, 'restart'], 'Restart') + btn('service', [v.name, 'stop'], 'Stop') : btn('service', [v.name, 'start'], 'Start'))
        + `</td></tr>`).join('') + `</tbody></table>`);
    }
    if (Array.isArray(s.startups) && s.startups.length) {
      out.push(`<h4>Startups</h4><table class="list"><thead><tr><th>App</th><th>Startup</th><th>State</th><th></th></tr></thead><tbody>` + s.startups.map((v) =>
        `<tr><td>${esc(v.app)}</td><td class="mono">${esc(v.name)}</td><td>${esc(v.state)}</td><td>`
        + (v.state === 'absent' ? btn('register', [v.app], 'Start at logon') : btn('startup', [v.app, 'run'], 'Run') + btn('startup', [v.app, 'end'], 'End') + btn('unregister', [v.app], 'Remove'))
        + `</td></tr>`).join('') + `</tbody></table>`);
    }
    if (Array.isArray(s.processes)) {
      out.push(`<h4>The framework's processes</h4>` + (s.processes.length ? `<table class="list"><thead><tr><th>Process</th><th>App</th><th>Memory</th><th>Command</th></tr></thead><tbody>` + s.processes.map((p) =>
        `<tr><td class="mono">${esc(p.pid)}</td><td>${esc(p.app)}</td><td>${esc(p.memoryMb)} MB</td><td class="mono muted small">${esc(p.command)}</td></tr>`).join('') + `</tbody></table>` : '<div class="muted small">None running.</div>'));
    }
    return out.join('');
  }

  // a plugin's own tables (status.tables: a title, the columns, the rows; a cell its text or {text, sub}, or a button
  // opening one of its forms, {form, title, values, label}). Under a table, its `actions`: buttons opening forms
  // ({form, title, values}) or asking a hook by name ({hook, args, title, note}: the hw-stats plugin's Refresh); above
  // its rows, its own `options` (a choice group, as status.options: the hw-stats plugin's ports listed) (0.7.0)
  const cellHtml = (c, m, forms) => (c && typeof c === 'object' ? (c.form ? formButton(m, c, forms)
    : `${esc(c.text)}${c.sub ? `<div class="sub">${esc(c.sub)}</div>` : ''}`) : esc(c));
  const longWord = (c) => String(c && typeof c === 'object' ? c.text ?? '' : c ?? '').split(/\s+/).some((w) => w.length > 16);  // may break

  // -- a table in groups (0.11.0: a firewall's rules, liminal-libs 1.35.0's rulegroups; the user: "for both firewalls, i
  // need to have groups, like system or application and then unassociated rules not tied to a specific application or
  // system process can be in an other, i can create labels, like system or application, as well and move the rules in to
  // that"; "just use basic expansion like a (+) to open and close labels"). t.groups: [{id, title, kind (auto | label),
  // count, listed, note, actions}]; each row {cells, key, group, own, why, moved}; t.move: {hook, title, choices}. Each
  // group a heading with (+) to open it and (−) to close it (closed at first; kept while the page lives, and in this
  // browser), a box to choose each rule (the heading's box choosing every rule the group lists), and under the table
  // Move to: the hook asked with the keys chosen and the group picked.
  // 0.16.0 (liminal-libs 1.41.0; the user: "lets group by application under apps or system"; "try to group the system by
  // 'services'"; "also rules that are turned off should be shown as well"): a group may hold `children` [{id, title,
  // count, listed, note}], one per name (a service in System, an application in Application), each drawn under the open
  // group as a heading of its own, indented and on a lighter band, with its (+) and (−) (kept open as a group is, under
  // its own id; closed at first, but open at first while its group lists FEW rules or fewer, as after a Find, until the
  // user closes it) and its box (choosing the rules whose `sub` is its id); its rules under it once open, indented as
  // it is; then the group's rules with no name, flush with the group and set apart by a line. A group with no children
  // is drawn as before. A row with `off` (a rule turned off) is dimmed and says so in words (over its name, to a screen
  // reader, by its box), chosen and moved as any. Rules moved into System or Application open the headings they went under.
  const OPEN_KEY = 'liminal-platform-open-groups', SHUT_KEY = 'liminal-platform-closed-headings';
  const openGroups = (() => { try { return new Set(JSON.parse(localStorage.getItem(OPEN_KEY) || '[]')); } catch (e) { return new Set(); } })();
  // closed by the user (0.16.0), `${plugin}|${table}|${id}`: a heading open at first (FEW) stays closed, in this browser too
  const shut = (() => { try { return new Set(JSON.parse(localStorage.getItem(SHUT_KEY) || '[]')); } catch (e) { return new Set(); } })();
  const keepOpen = () => {
    try { localStorage.setItem(OPEN_KEY, JSON.stringify([...openGroups].slice(-2000))); localStorage.setItem(SHUT_KEY, JSON.stringify([...shut].slice(-2000))); }
    catch (e) { /* this page only */ }
  };
  const FEW = 30;  // a group listing this many rules or fewer (a Find's, a narrow choice's): its headings open at first (0.16.0)
  const went = {};  // `${plugin}|${table}` -> {keys, to}: rules just moved into a group, until drawn there (0.16.0)
  const chosenRows = {};  // `${plugin}|${table}` -> the keys of the rules chosen
  const moveTargets = {};  // `${plugin}|${table}` -> the group last picked in Move to
  const tableKey = (name, title) => `${name}|${title}`;
  const chosenOf = (name, title) => chosenRows[tableKey(name, title)] || (chosenRows[tableKey(name, title)] = new Set());
  const textOf = (c) => String(c && typeof c === 'object' ? c.text ?? c.title ?? '' : c ?? '');
  const tableOf = (name, title) => { const p = pluginOf(name); return ((p && p.status && p.status.tables) || []).find((t) => t && t.title === title); };
  const rowsOf = (t) => (Array.isArray(t.rows) ? t.rows.filter((r) => r && typeof r === 'object' && Array.isArray(r.cells)) : []);
  function groupedTable(m, t, forms, can) {
    const rows = rowsOf(t), chosen = chosenOf(m.name, t.title), listed = new Set(rows.map((r) => r.key));
    [...chosen].forEach((k) => { if (!listed.has(k)) chosen.delete(k); });  // a rule no longer listed is no longer chosen
    const movable = !!(t.move && can.has(t.move.hook) && Array.isArray(t.move.choices));
    const at = (extra) => `data-machine="${esc(m.name)}" data-table="${esc(t.title)}"${extra || ''}`;
    const titles = Object.fromEntries(t.groups.filter(Boolean).map((g) => [g.id, g.title]));
    const span = t.columns.length;
    const came = went[tableKey(m.name, t.title)];  // rules just moved into a group: the headings they went under, open (0.16.0)
    if (came) { rows.forEach((r) => { if (came.keys.has(r.key) && r.sub && r.group === came.to) openGroups.add(`${tableKey(m.name, t.title)}|${r.sub}`); }); keepOpen(); }
    const isOpen = (id) => openGroups.has(`${tableKey(m.name, t.title)}|${id}`);
    const heading = (g, mine, open, cls, tail) => {  // a group's heading, or a name's under it (0.16.0): its box, (+) or (−), title, count, note
      const all = mine.length > 0 && mine.every((r) => chosen.has(r.key)), some = !all && mine.some((r) => chosen.has(r.key));
      const box = movable ? `<td class="pick"><input type="checkbox" class="pick-group" ${at(` data-group="${esc(g.id)}"`)}${all ? ' checked' : ''}`
        + `${some ? ' data-some="1"' : ''}${mine.length ? '' : ' disabled'} aria-label="Choose every rule ${esc(g.title)} lists"></td>` : '';
      return `<tr class="${cls}">${box}<td colspan="${span}"><div class="group-line">`
        + `<button type="button" class="expander" ${at(` data-group="${esc(g.id)}"`)} aria-expanded="${open}" aria-label="${open ? 'Close' : 'Open'} ${esc(g.title)}" title="${open ? 'Close' : 'Open'}">${open ? '−' : '+'}</button>`
        + `<span class="group-title">${esc(g.title)}</span><span class="muted small">${esc(String(g.count ?? mine.length))} rule${(g.count ?? mine.length) === 1 ? '' : 's'}</span>`
        + (g.note ? `<span class="muted small group-note">${esc(g.note)}</span>` : '') + (tail || '') + '</div></td></tr>';
    };
    const ruleLine = (r, place) => {  // place (0.16.0): 'under' a heading, indented as it is; 'first-own', a group's first rule after its headings
      const turned = r.off ? ' (turned off)' : '';  // a rule turned off: dimmed, and said so over its name, to a screen reader and by its box (0.16.0)
      const pick = movable ? `<td class="pick"><input type="checkbox" class="pick-row" ${at(` data-key="${esc(r.key)}"`)}${chosen.has(r.key) ? ' checked' : ''} aria-label="Choose ${esc(textOf(r.cells[0]) + turned)}"></td>` : '';
      const moved = r.moved ? `<div class="sub moved-note">moved here · its own group: ${esc(titles[r.own] || r.own || '')}</div>` : '';
      const why = [r.why, r.off && 'turned off'].filter(Boolean).join(' · ');
      // why it is in its group, in words under its name on a touch screen (0.17.0: no finger hovers the tooltip over it)
      const said = why ? `<div class="sub why-here touch-only" aria-hidden="true">${esc(why)}</div>` : '';
      const cls = [place, r.moved && 'moved', r.off && 'off'].filter(Boolean).join(' ');
      return `<tr${cls ? ` class="${cls}"` : ''}>${pick}` + r.cells.map((c, i) => `<td${t.columns[i] && t.columns[i].num ? ' class="num"' : longWord(c) ? ' class="long"' : ''}`
        + `${i === 0 && why ? ` title="${esc(why)}"` : ''}>${cellHtml(c, m, forms)}${i === 0 ? (turned ? '<span class="sr-only">turned off</span>' : '') + moved + said : ''}</td>`).join('') + '</tr>';
    };
    const body = t.groups.filter(Boolean).map((g) => {
      const open = isOpen(g.id), mine = rows.filter((r) => r.group === g.id);
      const buttons = (Array.isArray(g.actions) ? g.actions : []).map((a) => formButton(m, a, forms)).join('');
      const head = heading(g, mine, open, `group-head${g.kind === 'label' ? ' label' : ''}`, buttons ? `<span class="group-actions">${buttons}</span>` : '');
      const kids = Array.isArray(g.children) ? g.children.filter((c) => c && c.id) : [], ids = new Set(kids.map((c) => c.id));
      const few = mine.length <= FEW;  // few listed (a Find's): its headings open at first, until closed
      const lines = open ? kids.map((c) => {  // its names first, each a heading of its own, its rules under it once open
        const theirs = mine.filter((r) => r.sub === c.id), on = isOpen(c.id) || (few && !shut.has(`${tableKey(m.name, t.title)}|${c.id}`));
        return heading(c, theirs, on, 'sub-head') + (on ? theirs.map((r) => ruleLine(r, 'under')).join('') : '');
      }).join('') + mine.filter((r) => !ids.has(r.sub)).map((r, i) => ruleLine(r, kids.length && !i ? 'first-own' : '')).join('') : '';  // then those with no name, set apart
      return `<tbody class="group" data-group="${esc(g.id)}">${head}${lines}</tbody>`;
    }).join('');
    const thead = `<thead><tr>${movable ? '<th class="pick"></th>' : ''}${t.columns.map((c) => `<th${c.num ? ' class="num"' : ''}>${esc(c.title)}</th>`).join('')}</tr></thead>`;
    const target = moveTargets[tableKey(m.name, t.title)];
    const options = movable ? t.move.choices.filter(Boolean).map((c) => `<option value="${esc(c.value)}"${c.value === target ? ' selected' : ''}${c.note ? ` title="${esc(c.note)}"` : ''}>${esc(c.title)}</option>`).join('') : '';
    // the note of the group picked, in words beside it on a touch screen (0.17.0: a phone's picker never shows an option's
    // tooltip), kept as the pick changes
    const picked = movable ? t.move.choices.filter(Boolean).find((c) => c.value === target) || t.move.choices.filter(Boolean)[0] : null;
    const bar = movable ? `<div class="row move-bar"><span class="muted small" role="status">${chosen.size ? `${chosen.size} rule${chosen.size === 1 ? '' : 's'} chosen` : 'Choose rules by their boxes to move them'}</span>`
      + `<label class="small">${esc(t.move.title || 'Move to')} <select class="move-to" ${at()}>${options}</select></label>`
      + `<span class="muted small move-note touch-only">${esc((picked && picked.note) || '')}</span>`
      + `<button type="button" class="move-go" ${at()}${chosen.size ? '' : ' disabled'}>Move</button>`
      + (chosen.size ? `<button type="button" class="move-clear" ${at()}>Clear the choice</button>` : '') + '</div>' : '';
    return `<table class="list stats grouped">${thead}${body}</table>${rows.length ? '' : `<div class="muted small">${esc(t.empty || 'None.')}</div>`}${bar}`;
  }
  // -- a table chosen from by a click on a row (0.13.0: a WSL plugin's installs; the user: "instead of chosen, put task and
  // for the tasks lets do terminal, start, pause, stop, allow selection of the linux install by clicking on the list";
  // "tasks also include uninstall"). t.select {hook, value, title}: each row {cells, key}; the row whose key is the value
  // is the one chosen, a click on another (or its name, a button for the keyboard) asks the hook with its key. t.tasks
  // {title, subject, actions}: the chosen one's buttons above the table ("Task  Ubuntu  Terminal Start Pause Stop…
  // Uninstall…"), one whose task does not apply now `disabled`.
  function tasksBar(m, t, forms, can) {
    const k = t.tasks;
    if (!k || !Array.isArray(k.actions)) return '';
    const buttons = k.actions.map((b) => (b && b.form ? formButton(m, b, forms) : b && b.terminal ? shellButton(m, b.title, b)
      : b && b.job === 'update' ? updateButton(m, b) : askButton(m, b, can))).join('');
    return `<div class="row tasks" role="group" aria-label="${esc(`${k.title || 'Task'} ${k.subject || ''}`.trim())}"><span class="tasks-title">${esc(k.title || 'Task')}</span>`
      + `${k.subject ? `<span class="tasks-subject">${esc(k.subject)}</span>` : ''}${buttons}</div>`;
  }
  function updateButton(m, b) {  // the packages' update of the install chosen: a job, its output in the terminal panel (0.14.0)
    if (!hasHook(m, 'update_packages')) return '';
    const busy = !!(jobs[m.name] && jobs[m.name].running) || !!(m.setup && m.setup.running);
    return `<button type="button" class="update" data-machine="${esc(m.name)}"${busy || (b && b.disabled) ? ' disabled' : ''}${b && b.note ? ` title="${esc(b.note)}"` : ''}>`
      + `${esc((b && b.title) || 'Update packages')}</button>${offWhy(b)}`;
  }
  // why a button is disabled (its note), in words beside it on a touch screen (0.17.0): no finger hovers its tooltip, and a
  // disabled button answers no press
  const offWhy = (b) => (b && b.disabled && b.note ? `<span class="muted small off-why touch-only">${esc(b.note)}</span>` : '');
  function selectTable(m, t, forms, can) {
    const rows = rowsOf(t), s = t.select, pick = can.has(s.hook);
    const at = (r) => `data-machine="${esc(m.name)}" data-hook="${esc(s.hook)}" data-key="${esc(r.key)}"`;
    const first = (r, on) => {
      const c = r.cells[0], text = c && typeof c === 'object' ? c.text : c, sub = c && typeof c === 'object' ? c.sub : '';
      const inner = `<span class="row-name">${esc(text)}</span>${sub ? `<span class="sub">${esc(sub)}</span>` : ''}`;
      return pick ? `<button type="button" class="row-pick" ${at(r)} aria-pressed="${on}" title="${esc(s.title || 'Choose it')}">${inner}</button>` : inner;
    };
    const body = rows.map((r) => {
      const on = r.key === s.value;
      return `<tr class="pickable${on ? ' picked' : ''}"${pick ? ` data-pick-row ${at(r)}` : ''}>` + r.cells.map((c, i) => `<td${t.columns[i] && t.columns[i].num ? ' class="num"'
        : longWord(c) ? ' class="long"' : ''}>${i === 0 ? first(r, on) : cellHtml(c, m, forms)}</td>`).join('') + '</tr>';
    }).join('');
    // what a row's tap does, in words above the rows on a touch screen (0.17.0: its name's tooltip says it to a mouse)
    const how = pick && s.title && rows.length ? `<div class="muted small touch-only">${esc(s.title)}</div>` : '';
    return tasksBar(m, t, forms, can) + how + (rows.length ? `<table class="list stats selectable"><thead><tr>${t.columns.map((c) => `<th${c.num ? ' class="num"' : ''}>${esc(c.title)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>`
      : `<div class="muted small">${esc(t.empty || 'None.')}</div>`);
  }
  async function pickRow(el) {  // the row chosen at once on the page, then the plugin asked and drawn again
    const name = el.dataset.machine, hook = el.dataset.hook, key = el.dataset.key;
    const table = el.closest('table');
    if (table) table.querySelectorAll('tr.pickable').forEach((tr) => {
      const on = tr.dataset.key === key;
      tr.classList.toggle('picked', on);
      const b = tr.querySelector('button.row-pick');
      if (b) b.setAttribute('aria-pressed', String(on));
    });
    try { await api('POST', `api/machines/${encodeURIComponent(name)}/ask`, { hook, args: [key] }); say(name, ''); }
    catch (err) { say(name, err.message); }
    await refresh(name);
    const again = data.querySelector(`button.row-pick[data-machine="${CSS.escape(name)}"][data-key="${CSS.escape(key)}"]`);
    if (again && el.matches('button')) again.focus({ preventScroll: true });
  }

  function redrawTables(name, focus) {  // a plugin's tables drawn again (a group opened or closed, rules chosen), the focus kept
    const m = pluginOf(name), box = $(`tables-${name}`);
    if (!m || !box) return;
    box.innerHTML = tables(m) + statTables(m);
    const again = focus ? box.querySelector(focus) : null;
    if (again) again.focus({ preventScroll: true });
  }
  const pickSel = (cls, el, extra) => `${cls}[data-table="${CSS.escape(el.dataset.table)}"]${extra || ''}`;
  function toggleGroup(el) {  // as drawn: an open one closed, a closed one opened (a heading open at first, closed: kept closed)
    const k = `${tableKey(el.dataset.machine, el.dataset.table)}|${el.dataset.group}`;
    if (el.getAttribute('aria-expanded') === 'true') { openGroups.delete(k); shut.add(k); } else { openGroups.add(k); shut.delete(k); }
    keepOpen();
    redrawTables(el.dataset.machine, pickSel('button.expander', el, `[data-group="${CSS.escape(el.dataset.group)}"]`));
  }
  function pickRows(el, keys, on, focus) {
    const chosen = chosenOf(el.dataset.machine, el.dataset.table);
    keys.forEach((k) => (on ? chosen.add(k) : chosen.delete(k)));
    redrawTables(el.dataset.machine, focus);
  }
  async function moveChosen(el) {
    const name = el.dataset.machine, t = tableOf(name, el.dataset.table), chosen = chosenOf(name, el.dataset.table);
    const box = $(`tables-${name}`), pick = box && box.querySelector(pickSel('select.move-to', el));
    if (!t || !t.move || !chosen.size || !pick) return;
    const keys = [...chosen], to = pick.value;
    moveTargets[tableKey(name, t.title)] = to;
    chosen.clear();
    if (to !== 'own') { openGroups.add(`${tableKey(name, t.title)}|${to}`); keepOpen(); }  // where they went, open
    el.disabled = true;
    try { await api('POST', `api/machines/${encodeURIComponent(name)}/ask`, { hook: t.move.hook, args: [keys, to] }); say(name, ''); }
    catch (e) {  // refused: chosen as they were, the plugin's words at the head of its page
      keys.forEach((k) => chosen.add(k));
      say(name, e.message);
      redrawTables(name, pickSel('button.move-go', el));
      return;
    }
    if (to !== 'own') went[tableKey(name, t.title)] = { keys: new Set(keys), to };  // and the headings they go under, once drawn there
    await refresh(name);  // this plugin alone asked again: the rules where they went at once
    delete went[tableKey(name, t.title)];
  }
  // a group's box half chosen: shown as such once drawn
  new MutationObserver(() => document.querySelectorAll('input.pick-group[data-some]').forEach((x) => { x.indeterminate = true; }))
    .observe(document.body, { childList: true, subtree: true });
  document.addEventListener('change', (e) => {
    const s = e.target.closest && e.target.closest('select.move-to[data-table]');
    if (!s) return;
    moveTargets[tableKey(s.dataset.machine, s.dataset.table)] = s.value;
    const note = s.closest('.move-bar') && s.closest('.move-bar').querySelector('.move-note');  // its note in words (0.17.0)
    const o = s.options[s.selectedIndex];
    if (note) note.textContent = (o && o.getAttribute('title')) || '';
  });
  function statTables(m) {
    const forms = formsOf(m), can = new Set(m.asks || []);
    const under = (t) => {
      const buttons = (Array.isArray(t.actions) ? t.actions : []).map((b) => (b && b.form ? formButton(m, b, forms)
        : b && b.terminal ? shellButton(m, b.title, b) : askButton(m, b, can))).join('');  // {terminal, title}: its terminal (0.12.0)
      return buttons ? `<div class="row table-actions">${buttons}</div>` : '';
    };
    const picks = (t) => groupsOf(t.options, can).map((o) => choicesHtml(m, o, `<div class="muted small choices-title">${esc(o.title)}</div>`)).join('');
    return ((m.status && m.status.tables) || []).map((t) => `<h4>${esc(t.title)}</h4>${t.note ? `<div class="muted small mono note">${esc(t.note)}</div>` : ''}${picks(t)}`
      + (Array.isArray(t.groups) && Array.isArray(t.columns) ? groupedTable(m, t, forms, can)
        : t.select && Array.isArray(t.columns) ? selectTable(m, t, forms, can) : (t.rows || []).length ? `<table class="list stats"><thead><tr>${t.columns.map((c) => `<th${c.num ? ' class="num"' : ''}>${esc(c.title)}</th>`).join('')}</tr></thead><tbody>`
        + t.rows.map((r) => `<tr>${r.map((c, i) => `<td${t.columns[i] && t.columns[i].num ? ' class="num"' : longWord(c) ? ' class="long"' : ''}>${cellHtml(c, m, forms)}</td>`).join('')}</tr>`).join('') + '</tbody></table>'
        : `<div class="muted small">${esc(t.empty || 'None.')}</div>`) + under(t)).join('');
  }

  // -- a plugin's paths (0.8.0, status.paths: the hw-stats plugin's way in to a port): its hops in a row and the links
  // between them ({id, title, running, said, lines, at, nodes: [{id, title, sub, state}], links: [{from, to, state,
  // title}]}), each in its state: idle, checking, done, ok, warn, fail, unknown. Traffic moves along a link being
  // checked (and, slower, one it got through); a link that stopped it is crossed. Drawn again only when it changed, so
  // the moving traffic is not restarted by every refresh; asked again every second while a path is checked.
  const PATH_STATES = new Set(['idle', 'checking', 'done', 'ok', 'warn', 'fail', 'unknown']);
  const PATH_WORDS = { idle: 'not checked yet', checking: 'being checked', done: 'checked', ok: 'passes', warn: 'in doubt',
    fail: 'stops it', unknown: 'not known' };
  const pathState = (s) => (PATH_STATES.has(s) ? s : 'unknown');
  const drawnPaths = {};  // the paths drawn last, by plugin
  const pathsOf = (m) => (m.status && Array.isArray(m.status.paths) ? m.status.paths : []).filter((p) => p && Array.isArray(p.nodes) && p.nodes.length);
  const pathRunning = (m) => pathsOf(m).some((p) => p.running);
  function hopGlyph(id, x, y) {  // the internet a globe, a router a box with its antennas, anything else a screen
    if (id === 'internet') {
      return `<circle cx="${x}" cy="${y}" r="20" class="glyph"/><ellipse cx="${x}" cy="${y}" rx="8" ry="20" class="glyph"/>`
        + `<line x1="${x - 20}" y1="${y}" x2="${x + 20}" y2="${y}" class="glyph"/>`;
    }
    if (id === 'router') {
      return `<rect x="${x - 22}" y="${y - 6}" width="44" height="18" rx="4" class="glyph"/><line x1="${x - 12}" y1="${y - 6}" x2="${x - 17}" y2="${y - 21}" class="glyph"/>`
        + `<line x1="${x + 12}" y1="${y - 6}" x2="${x + 17}" y2="${y - 21}" class="glyph"/><circle cx="${x - 9}" cy="${y + 3}" r="2" class="led"/><circle cx="${x}" cy="${y + 3}" r="2" class="led"/>`;
    }
    return `<rect x="${x - 22}" y="${y - 18}" width="44" height="28" rx="3" class="glyph"/><line x1="${x}" y1="${y + 10}" x2="${x}" y2="${y + 17}" class="glyph"/>`
      + `<line x1="${x - 12}" y1="${y + 18}" x2="${x + 12}" y2="${y + 18}" class="glyph"/>`;
  }
  function pathHtml(p) {
    const W = 640, Y = 34, xs = p.nodes.map((_, i) => Math.round(80 + i * ((W - 160) / Math.max(1, p.nodes.length - 1))));
    const at = {};
    p.nodes.forEach((n, i) => { if (n && typeof n.id === 'string') at[n.id] = xs[i]; });
    const links = (Array.isArray(p.links) ? p.links : []).filter((l) => l && at[l.from] !== undefined && at[l.to] !== undefined).map((l) => {
      const s = pathState(l.state), x1 = at[l.from] + 34, x2 = at[l.to] - 34, mid = (x1 + x2) / 2;
      return `<g class="link ${s}"><title>${esc(l.title || '')}: ${esc(PATH_WORDS[s])}</title><line x1="${x1}" y1="${Y}" x2="${x2}" y2="${Y}" class="wire"/>`
        + (s === 'checking' || s === 'ok' ? `<line x1="${x1}" y1="${Y}" x2="${x2}" y2="${Y}" class="traffic"/>` : '')
        + (s === 'fail' ? `<path d="M${mid - 7} ${Y - 7} L${mid + 7} ${Y + 7} M${mid + 7} ${Y - 7} L${mid - 7} ${Y + 7}" class="cross"/>` : '')
        + `<path d="M${x2 - 8} ${Y - 5} L${x2} ${Y} L${x2 - 8} ${Y + 5}" class="arrow"/></g>`;
    }).join('');
    const hops = p.nodes.map((n, i) => `<g class="hop ${pathState(n.state)}"><title>${esc(n.title)}: ${esc(PATH_WORDS[pathState(n.state)])}</title>${hopGlyph(n.id, xs[i], Y)}</g>`).join('');
    const labels = p.nodes.map((n, i) => `<div class="hop-label ${pathState(n.state)}" style="left:${(xs[i] / W * 100).toFixed(2)}%"><strong>${esc(n.title)}</strong>`
      + `<span class="state">${esc(PATH_WORDS[pathState(n.state)])}</span>${n.sub ? `<span class="sub">${esc(n.sub)}</span>` : ''}</div>`).join('');
    const lines = (Array.isArray(p.lines) ? p.lines : []).filter((l) => typeof l === 'string' && l);
    return `<section class="path${p.running ? ' running' : ''}"><h4>${esc(p.title || 'A path')}</h4>`
      + `<div class="path-picture"><svg viewBox="0 0 ${W} ${Y * 2}" role="img" aria-label="${esc(p.said || p.title || '')}">${links}${hops}</svg>`
      + `<div class="hop-labels">${labels}</div></div>`
      + (p.said ? `<p class="said${p.running ? ' muted' : ''}" role="status">${esc(cap(String(p.said)))}</p>` : '')
      + (lines.length ? `<details open><summary class="muted small">What each hop showed${p.at ? ` · ${esc(p.at)}` : ''}</summary><ul class="lines">${lines.map((l) => `<li>${esc(l)}</li>`).join('')}</ul></details>` : '')
      + '</section>';
  }
  const pathsHtml = (m) => pathsOf(m).map(pathHtml).join('');

  // a choice group: a hook asked with the value chosen ({title, hook, value, choices: [{value, title, note, swatch}]}),
  // those the platform may ask of the plugin now; drawn under `head`
  const groupsOf = (groups, can) => (Array.isArray(groups) ? groups : []).filter((o) => o && can.has(o.hook) && Array.isArray(o.choices));
  function choicesHtml(m, o, head) {
    return head + `<div class="choices" role="radiogroup" aria-label="${esc(o.title)}">${o.choices.filter(Boolean).map((c) => `<button type="button" class="choice${c.value === o.value ? ' active' : ''}" role="radio"
          aria-checked="${c.value === o.value}" aria-label="${esc(c.title)}${c.note ? `, ${esc(c.note)}` : ''}" tabindex="${c.value === o.value ? 0 : -1}" data-machine="${esc(m.name)}" data-hook="${esc(o.hook)}" data-value="${esc(c.value)}">`
        + `<span class="swatch" aria-hidden="true">${(c.swatch || []).map((s) => `<span style="background:${/^#[0-9a-fA-F]{3,8}$/.test(s) ? s : 'transparent'}"></span>`).join('')}</span>`
        + `<span class="what"><span>${esc(c.title)}</span>${c.note ? `<span class="sub">${esc(c.note)}</span>` : ''}</span></button>`).join('')}</div>`;
  }

  // a plugin's choices (status.options: the Preferences plugin's themes)
  function optionsHtml(m) {
    return groupsOf(m.status && m.status.options, new Set(m.asks || [])).map((o) => choicesHtml(m, o, `<h4>${esc(o.title)}</h4>`)).join('');
  }

  // a button asking one of a plugin's hooks by name ({hook, args, title, note}), when the platform may ask it now
  function askButton(m, a, can) {
    return a && can.has(a.hook) && Array.isArray(a.args || []) ? `<button type="button" class="ask" data-machine="${esc(m.name)}" `
      + `data-hook="${esc(a.hook)}" data-args='${esc(JSON.stringify(a.args || []))}'${a.note ? ` title="${esc(a.note)}"` : ''}${a.disabled ? ' disabled' : ''}>${esc(a.title || a.hook)}</button>${offWhy(a)}` : '';
  }

  // a plugin's actions (status.actions: {hook, args, title, note}: one of its hooks asked by name from a button, the
  // Namecheap plugin's Refresh and Update DNS now; {form, title, values}: a button opening one of its forms): those the
  // platform may ask of it now, the rest left out
  function actionsHtml(m) {
    const can = new Set(m.asks || []), forms = formsOf(m);
    const items = ((m.status && m.status.actions) || []).map((a) => (a && a.form ? formButton(m, a, forms) : askButton(m, a, can))).filter(Boolean);
    return items.length ? `<div class="row actions">${items.join('')}</div>` : '';
  }

  // -- a plugin's forms (0.6.0, status.forms): one of its hooks asked with what the user fills in, once the user has
  // confirmed the exact change; its answer said in words. A form: {id, hook, title, note, fields, submit, confirm: {title,
  // words, yes, danger}}; a field: {name, label, type: text | number | choice | fixed | accept, value, choices: [{value,
  // title, note}], placeholder, note, required, min, max, empty, when: {field: [values]}, keyboard (0.17.0, optional: the
  // on-screen keyboard it calls up, one of the library's kinds its type takes: see keyboardOf)}, the fields in the order of the
  // hook's arguments (a field whose `when` is unmet, or left empty, is sent as null: the hook's default). A button names
  // a form: an action ({form, title, values}), a table's `actions` under it, a cell ({form, title, values, label}); its
  // `values` fill the fields by name, and a form with nothing to fill goes straight to its confirmation, where `{name}` in
  // the words is that field's value. A refusal naming a field of type accept (the error answer's `accept`) is offered as
  // a second, explicit confirmation (the field's title, words and yes) that sends the same arguments with that field
  // true (the Namecheap plugin's accept_ddns_reset); never before it. The page's one <dialog> holds the form, its
  // confirmation and the answer, outside what is drawn again, so the tables asked again leave it as it is. A form
  // whose `confirm` is false changes nothing on the machine (the ports a table lists): it is asked once filled (0.7.0).
  const EDITABLE = ['text', 'number', 'choice', 'password'];
  // a plugin's settings (0.9.0: its keys, from the platform: m.settings), entered in the same dialog and kept through
  // the platform's login: a secret typed hidden, a value never shown back, a field left empty keeping its value
  const SETTINGS = '__settings', FORGET = '__forget';
  function settingsForm(m, only) {  // every setting, or `only` the one named (0.15.0: an entry's Enter… or Change…)
    const all = m.settings || [], set = all.filter((s) => s.set).length;
    const shown = only ? all.filter((s) => s.variable === only) : all;
    if (!shown.length) return null;
    return { id: only ? `${SETTINGS}:${only}` : SETTINGS, hook: '', route: 'settings', confirm: false,
      title: only ? `${m.title}: ${shown[0].label || shown[0].variable}` : `${m.title}: settings`, submit: only ? 'Keep it' : 'Keep them',
      note: (only ? '' : `${set} of ${all.length} set. `) + 'Kept with you: your user environment variables today, the login app once it holds them. '
        + (only ? 'Left empty, it keeps its value; a key is never shown back.' : 'A field left empty keeps its value; a key is never shown back.'),
      fields: shown.map((s) => ({ name: s.variable, label: s.label || s.variable, type: s.secret ? 'password' : 'text',
        required: Boolean(only) && !s.set && !optionalSetting(s),  // one needed and not set yet: typed, or the dialog cancelled
        placeholder: s.set ? 'set: type to replace it' : 'not set', note: [s.variable, s.hint].filter(Boolean).join(' · ') })) };
  }
  function forgetForm(m, variable) {  // one setting forgotten: kept nowhere any more, once confirmed
    const s = (m.settings || []).find((x) => x.variable === variable && x.set);
    if (!s) return null;
    return { id: `${FORGET}:${variable}`, hook: '', route: 'settings-forget', title: `Forget ${s.label || s.variable}`,
      fields: [{ name: 'variable', label: 'Variable', type: 'fixed' }, { name: 'label', label: 'Setting', type: 'fixed' }],
      confirm: { title: `Forget ${s.label || s.variable}?`, words: `${s.variable} is removed from where it is kept (your user environment variables); `
        + `${m.title} no longer has it until it is entered again.`, yes: 'Forget it', danger: true } };
  }
  // a plugin's settings as entries on its page (0.15.0; the user: "the namecheap plugin is very sparse, it should have
  // entries for login credentials api key etc.."): each it declares with its variable, set or not (never its value),
  // optional or needed, where to get it (its hint), Enter… or Change… (that one field) and Forget… for one set; All
  // settings… for every one at once
  const optionalSetting = (s) => /^optional\b/i.test(s.hint || '');
  function settingsButton(m) {
    const all = m.settings || [];
    if (!all.length) return '';
    const set = all.filter((s) => s.set).length;
    const rows = all.map((s) => {
      const state = s.set ? '<span class="setting-set">✓ set</span>' : optionalSetting(s) ? '<span class="muted">optional</span>' : '<span class="setting-unset">not set</span>';
      return `<tr><td><span class="setting-name">${esc(s.label || s.variable)}</span><div class="sub mono">${esc(s.variable)}${s.secret ? ' · hidden' : ''}</div></td>`
        + `<td>${state}</td><td class="muted small setting-hint">${esc(String(s.hint || '').replace(/^optional:\s*/i, ''))}</td>`
        + `<td class="setting-buttons"><button type="button" class="settings-open" data-machine="${esc(m.name)}" data-variable="${esc(s.variable)}">${s.set ? 'Change…' : 'Enter…'}</button>`
        + (s.set ? `<button type="button" class="settings-forget" data-machine="${esc(m.name)}" data-variable="${esc(s.variable)}" data-label="${esc(s.label || s.variable)}">Forget…</button>` : '')
        + '</td></tr>';
    }).join('');
    return `<h4>Settings</h4><div class="muted small note">${set} of ${all.length} set. Kept with you through the platform's login: your user environment `
      + `variables today, the login app once it holds them. A value is never shown back.</div>`
      + `<table class="list settings-table"><thead><tr><th>Setting</th><th>State</th><th>Where to get it</th><th></th></tr></thead><tbody>${rows}</tbody></table>`
      + `<div class="row actions"><button type="button" class="settings-open" data-machine="${esc(m.name)}">All settings…</button></div>`;
  }
  const pluginOf = (name) => st && (st.machines[name] || (st.assistants || []).find((a) => a.name === name));
  let dlg = null;  // the form open: {name, plugin, form, values, step, busy, accepted, accept, answer, words, opener, key}

  function formsOf(m) {  // a plugin's forms by id: those whose hook the platform may ask of it now
    const can = new Set(m.asks || []), out = {};
    ((m.status && m.status.forms) || []).forEach((f) => {
      if (f && typeof f.id === 'string' && typeof f.hook === 'string' && can.has(f.hook) && Array.isArray(f.fields)) out[f.id] = f;
    });
    return out;
  }
  function formButton(m, b, forms) {  // a button opening one of its forms, with the values it fills in
    const f = b && typeof b.form === 'string' && (forms || formsOf(m))[b.form];
    if (!f) return '';
    return `<button type="button" class="form-open" data-machine="${esc(m.name)}" data-form="${esc(b.form)}" data-values='${esc(JSON.stringify(b.values || {}))}'`
      + `${b.label ? ` aria-label="${esc(b.label)}"` : ''}${b.note ? ` title="${esc(b.note)}"` : ''}${b.disabled ? ' disabled' : ''}>${esc(b.title || f.title || f.hook)}</button>${offWhy(b)}`;
  }

  const given = (v) => v !== undefined && v !== null && v !== '';
  const editableOf = (f) => f.fields.some((x) => x && EDITABLE.includes(x.type));
  const whenMet = (values, x) => !x.when || typeof x.when !== 'object'
    || Object.entries(x.when).every(([k, vs]) => (Array.isArray(vs) ? vs : [vs]).map(String).includes(String(values[k] ?? '')));
  const choiceOf = (x, v) => (Array.isArray(x.choices) ? x.choices.find((c) => c && String(c.value) === String(v)) : null) || null;
  function shownValue(x, v) {  // a field's value in words: a choice by its title, nothing by the field's `empty`
    if (!given(v)) return x.empty || '–';
    const c = choiceOf(x, v);
    return String(c && c.title !== undefined ? c.title : v);
  }
  function filled(text, f, values) {  // `{name}` in a form's words: that field's value as shown (one pass: a value is never read again)
    const by = {};
    f.fields.forEach((x) => { if (x && typeof x.name === 'string') by[x.name] = shownValue(x, values[x.name]); });
    return String(text || '').replace(/\{(\w+)\}/g, (all, k) => (Object.prototype.hasOwnProperty.call(by, k) ? by[k] : all));
  }
  function argsOf(f, values, accepted) {  // the hook's arguments, the fields' values in order
    return f.fields.map((x) => {
      if (!x) return null;
      if (x.type === 'accept') return accepted.includes(x.name);  // true only through its own confirmation
      if (!whenMet(values, x) || !given(values[x.name])) return null;  // not shown, or left empty: the hook's default
      return x.type === 'number' ? Number(values[x.name]) : values[x.name];
    });
  }

  function openForm(name, id, values, opener) {
    const m = pluginOf(name), f = m && (id === SETTINGS ? settingsForm(m) : id.startsWith(`${SETTINGS}:`) ? settingsForm(m, id.slice(SETTINGS.length + 1))
      : id.startsWith(`${FORGET}:`) ? forgetForm(m, id.slice(FORGET.length + 1)) : formsOf(m)[id]);
    if (!f) return;
    const start = {};
    f.fields.forEach((x) => {
      if (!x || typeof x.name !== 'string') return;
      const v = values && Object.prototype.hasOwnProperty.call(values, x.name) ? values[x.name] : x.value;
      start[x.name] = v !== undefined ? v : x.type === 'choice' && Array.isArray(x.choices) && x.choices[0] ? x.choices[0].value : null;
    });
    dlg = { name, plugin: m.title, form: f, values: start, step: editableOf(f) ? 'fill' : 'confirm', busy: false, accepted: [],
      accept: null, answer: null, words: '', opener, key: opener ? `${opener.dataset.form}|${opener.dataset.values}` : '' };
    const el = dialogEl();
    drawDialog();
    if (!el.open) {
      // opened by a finger (0.17.0): on its heading, so no keyboard covers the dialog before a field is tapped (the
      // browser's own opening focuses the first field it can reach by Tab: the heading is that one meanwhile)
      const head = mayFocus() ? null : $('formDialogTitle');
      if (head) { head.tabIndex = 0; head.setAttribute('autofocus', ''); }
      el.showModal();
      if (head) { head.tabIndex = -1; head.removeAttribute('autofocus'); }
    }
    focusStep();
  }

  function dialogEl() {
    let el = $('formDialog');
    if (el) return el;
    el = document.createElement('dialog');
    el.id = 'formDialog';
    el.className = 'form-dialog';
    el.setAttribute('aria-labelledby', 'formDialogTitle');
    el.addEventListener('cancel', (e) => { if (dlg && dlg.busy) e.preventDefault(); });  // Escape: not while it is asked
    el.addEventListener('close', closed);
    el.addEventListener('submit', (e) => { e.preventDefault(); review(); });
    el.addEventListener('change', (e) => { if (e.target.matches('select, input')) syncFill(); });
    el.addEventListener('input', (e) => {  // a field changed: its complaint goes
      if (!e.target.matches('input')) return;
      e.target.removeAttribute('aria-invalid');
      const bad = $(`${e.target.id}-bad`);
      if (bad) bad.textContent = '';
    });
    // an on-screen keyboard's Next (0.17.0): the next field shown, the form not sent yet (Safari sends it otherwise); a
    // hardware keyboard's Enter sends it from any field, as before
    el.addEventListener('keydown', (e) => {
      const c = e.target;
      if (e.key !== 'Enter' || e.isComposing || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey || !fingered()) return;
      if (!c.matches || !c.matches('form input') || c.getAttribute('enterkeyhint') !== 'next') return;
      const shown = shownControls(el), next = shown[shown.indexOf(c) + 1];
      if (!next) return;
      e.preventDefault();
      next.focus({ preventScroll: true });  // touch.js brings it into view above the keyboard
    });
    el.addEventListener('click', (e) => {
      const b = e.target.closest('button[data-do]');
      if (!b || b.disabled || !dlg) return;
      const what = b.dataset.do;
      if (what === 'close') el.close();
      else if (what === 'back') { dlg.step = 'fill'; dlg.accepted = []; drawDialog(); focusStep(); }  // a changed change: accepted again
      else if (what === 'yes') send();
      else if (what === 'accept') { dlg.accepted.push(dlg.accept); send(); }
    });
    document.body.appendChild(el);
    return el;
  }

  // the keyboard a field calls up on a phone or a tablet (0.17.0, the library's kinds): the one its plugin names in
  // `keyboard` when its type takes it (a host name's url, an address's email), else its type's own: a number the digits
  // pad (the keyboard with a minus where it may be below 0), a secret kept out of password managers (not a new password),
  // a text typed as it is (no capitals, no corrections). Signed is a number's alone: its minus is type=number's keyboard's
  const KEYBOARDS_OF = { text: ['plain', 'text', 'name', 'search', 'email', 'url', 'number', 'decimal', 'ticker', 'username', 'code'],
    number: ['number', 'signed'], password: ['secret', 'key', 'password'] };
  function keyboardOf(x) {
    if (typeof x.keyboard === 'string' && (KEYBOARDS_OF[x.type] || []).includes(x.keyboard)) return x.keyboard;
    if (x.type === 'number') return given(x.min) && Number(x.min) >= 0 ? 'number' : 'signed';
    return x.type === 'password' ? 'secret' : 'plain';
  }
  function fieldHtml(x, i, values) {
    if (!x || !EDITABLE.includes(x.type) || typeof x.name !== 'string') return '';
    const id = `fd-${i}`, v = values[x.name], c = x.type === 'choice' ? choiceOf(x, v) : null;
    const attrs = `id="${id}" name="${esc(x.name)}" aria-describedby="${id}-note ${id}-bad"${x.required ? ' aria-required="true"' : ''}`;
    const hint = x.placeholder ? ` placeholder="${esc(x.placeholder)}"` : '';
    const keys = x.type === 'choice' ? '' : kb(keyboardOf(x));  // its Enter's word is set by its place (syncFill)
    const control = x.type === 'choice'
      ? `<select ${attrs}>${(x.choices || []).filter(Boolean).map((o) => `<option value="${esc(o.value)}"${String(o.value) === String(v) ? ' selected' : ''}>${esc(o.title !== undefined ? o.title : o.value)}</option>`).join('')}</select>`
      : x.type === 'number'
        ? `<input type="number" step="1" ${keys} ${attrs}${x.min !== undefined ? ` min="${esc(x.min)}"` : ''}${x.max !== undefined ? ` max="${esc(x.max)}"` : ''} value="${given(v) ? esc(v) : ''}"${hint}>`
        : x.type === 'password'
          ? `<input type="password" ${keys} ${attrs} value="${given(v) ? esc(v) : ''}"${hint}>`
          : `<input type="text" ${keys} ${attrs} value="${given(v) ? esc(v) : ''}"${hint}>`;
    const optional = !x.required && x.type !== 'choice' ? ' <span class="muted">(optional)</span>' : '';
    return `<div class="field" data-field="${esc(x.name)}"><label for="${id}">${esc(x.label || x.name)}${optional}</label>${control}`
      + `<span class="sub" id="${id}-note">${esc((c && c.note) || x.note || '')}</span><span class="bad" id="${id}-bad"></span></div>`;
  }
  function valuesList(f, values) {  // the change asked: each field shown or fixed, by its label (a choice with its note)
    const rows = f.fields.filter((x) => x && (x.type === 'fixed' || EDITABLE.includes(x.type)) && whenMet(values, x)).map((x) => {
      const c = choiceOf(x, values[x.name]);
      return `<dt>${esc(x.label || x.name)}</dt><dd>${esc(shownValue(x, values[x.name]))}${c && c.note ? `<span class="sub">${esc(c.note)}</span>` : ''}</dd>`;
    });
    return rows.length ? `<dl class="facts change">${rows.join('')}</dl>` : '';
  }
  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '');
  function answerHtml(a) {  // a hook's answer in words: its `said` and `lines` (a fault when `ok` is false), else what it holds
    if (a && typeof a === 'object' && !Array.isArray(a) && (a.said || Array.isArray(a.lines))) {
      const lines = (Array.isArray(a.lines) ? a.lines : []).filter((l) => typeof l === 'string' && l);
      return (a.said ? `<p class="said${a.ok === false ? ' fault' : ''}">${esc(cap(String(a.said)))}</p>` : '')
        + (lines.length ? `<ul class="lines">${lines.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>` : '');
    }
    if (typeof a === 'string' && a) return `<p class="said">${esc(a)}</p>`;
    return (a && typeof a === 'object' && !Array.isArray(a) && facts(a)) || '<p class="said">Done.</p>';
  }

  function drawDialog() {
    const el = $('formDialog');
    if (!el || !dlg) return;
    const { form: f, values, step } = dlg, c = f.confirm || {};
    const head = (title) => `<h3 id="formDialogTitle" tabindex="-1">${esc(title)}</h3><div class="muted small">${esc(dlg.plugin)}</div>`;
    const btn = (what, text, cls = '') => `<button type="button" data-do="${what}"${cls ? ` class="${cls}"` : ''}>${esc(text)}</button>`;
    const back = editableOf(f) ? btn('back', 'Back') : '';
    const asking = `<p class="muted small" role="status">${dlg.busy ? `Asked: waiting for ${esc(dlg.plugin)}…` : ''}</p>`;
    const refusal = `<p>${esc(dlg.plugin)} refused it:</p><blockquote class="words">${esc(dlg.words)}</blockquote>`;
    let html;
    if (step === 'fill') {
      html = `<form novalidate>${head(f.title || f.hook)}${f.note ? `<p class="muted small note">${esc(f.note)}</p>` : ''}`
        + valuesList({ fields: f.fields.filter((x) => x && x.type === 'fixed') }, values) + f.fields.map((x, i) => fieldHtml(x, i, values)).join('')
        + `<div class="row end buttons">${btn('close', 'Cancel')}<button type="submit" class="accent">${esc(f.submit || 'Review')}</button></div></form>`;
    } else if (step === 'confirm') {
      html = head(filled(c.title || f.title || f.hook, f, values)) + (c.words ? `<p class="words">${esc(filled(c.words, f, values))}</p>` : '') + valuesList(f, values)
        + asking + `<div class="row end buttons">${btn('close', 'Cancel')}${back}${btn('yes', c.yes || 'Yes', c.danger ? 'danger' : 'accent')}</div>`;
    } else if (step === 'accept') {  // the second confirmation: the plugin's refusal, then what accepting it means
      const x = f.fields.find((y) => y && y.name === dlg.accept) || {};
      html = head(x.title || 'Go on anyway?') + refusal + (x.words ? `<p class="words">${esc(filled(x.words, f, values))}</p>` : '') + valuesList(f, values)
        + asking + `<div class="row end buttons">${btn('close', 'Cancel')}${back}${btn('accept', x.yes || 'Go on anyway', 'danger')}</div>`;
    } else if (step === 'done') {
      const fault = !!(dlg.answer && typeof dlg.answer === 'object' && dlg.answer.ok === false);
      html = head(fault ? 'Done, with a fault' : 'Done') + answerHtml(dlg.answer) + `<div class="row end buttons">${btn('close', 'Done', 'accent')}</div>`;
    } else if (step === 'refused') {
      html = head('Refused') + refusal + `<div class="row end buttons">${btn('close', 'Close')}${editableOf(f) ? btn('back', 'Change it', 'accent') : ''}</div>`;
    } else {  // failed: the plugin's words (it may have done part of it: the page is drawn again)
      html = head('It failed') + `<p>${esc(dlg.plugin)} could not do it:</p><blockquote class="words">${esc(dlg.words)}</blockquote>`
        + `<div class="row end buttons">${btn('close', 'Close', 'accent')}</div>`;
    }
    el.innerHTML = html;
    if (dlg.busy) el.querySelectorAll('button').forEach((b) => { b.disabled = true; });
    el.setAttribute('aria-busy', String(!!dlg.busy));
    if (step === 'fill') syncFill();
  }

  function focusStep() {  // the fill's first field; else the step's heading, so Enter confirms nothing by itself (after a
    // finger's tap, the heading too: the keyboard comes up when a field is tapped, 0.17.0)
    const el = $('formDialog');
    if (!el || !dlg) return;
    const target = (dlg.step === 'fill' && mayFocus() && el.querySelector('form input, form select')) || $('formDialogTitle');
    if (target) target.focus({ preventScroll: true });
  }

  // the form's fields shown (a field whose `when` is unmet is not), in order
  const shownControls = (el) => [...el.querySelectorAll('form .field[data-field]')].filter((d) => !d.hidden)
    .map((d) => d.querySelector('input, select')).filter(Boolean);
  function syncFill() {  // what the form holds kept; a field whose `when` is unmet hidden; a choice's note under it
    const el = $('formDialog');
    if (!el || !dlg || dlg.step !== 'fill') return;
    el.querySelectorAll('form [name]').forEach((c) => { dlg.values[c.name] = c.value; });
    el.querySelectorAll('.field[data-field]').forEach((div) => {
      const x = dlg.form.fields.find((y) => y && y.name === div.dataset.field);
      if (!x) return;
      div.hidden = !whenMet(dlg.values, x);
      const note = div.querySelector('.sub');
      if (x.type === 'choice' && note) note.textContent = ((choiceOf(x, dlg.values[x.name]) || {}).note) || x.note || '';
    });
    // the on-screen keyboard's Enter (0.17.0): Next on every field shown but the last, the last its kind's own word
    const shown = shownControls(el);
    shown.forEach((c, i) => {
      if (c.localName !== 'input') return;
      const own = ((T && T.KEYBOARDS[c.dataset.keyboard]) || {}).enterkeyhint || 'done';
      c.setAttribute('enterkeyhint', i < shown.length - 1 ? 'next' : own === 'next' ? 'done' : own);
    });
  }

  function review() {  // the fill checked as its fields say (the plugin checks again), then the confirmation
    if (!dlg || dlg.step !== 'fill') return;
    syncFill();
    let first = null;
    dlg.form.fields.forEach((x, i) => {
      const c = $(`fd-${i}`), bad = $(`fd-${i}-bad`);
      if (!x || !c || !EDITABLE.includes(x.type) || !whenMet(dlg.values, x)) return;
      const v = String(dlg.values[x.name] ?? '').trim();
      const range = x.min !== undefined && x.max !== undefined ? `a whole number, ${x.min} to ${x.max}` : 'a whole number';
      let why = '';
      if (x.type === 'number' && c.validity && c.validity.badInput) why = range;
      else if (!v) why = x.required ? `${x.label || x.name} is needed` : '';
      else if (x.type === 'number') {
        const n = Number(v);
        if (!Number.isInteger(n) || (x.min !== undefined && n < x.min) || (x.max !== undefined && n > x.max)) why = range;
      } else if (x.type === 'choice' && !choiceOf(x, v)) why = 'one of its choices';
      dlg.values[x.name] = v;
      if (why) c.setAttribute('aria-invalid', 'true'); else c.removeAttribute('aria-invalid');
      if (bad) bad.textContent = why;
      if (why && !first) first = c;
    });
    // the first field to change: focused, or after a finger's tap brought into view with its complaint (0.17.0: no keyboard
    // called up before it is tapped)
    if (first) { if (!autofocus(first)) (first.closest('.field') || first).scrollIntoView({ block: 'nearest' }); return; }
    if (dlg.form.confirm === false) { send(); return; }  // a choice changing nothing on the machine (0.7.0): asked at once
    dlg.step = 'confirm';
    drawDialog();
    focusStep();
  }

  async function send() {  // the hook asked with the fields' values; its answer, refusal or failure said in words
    const d = dlg;
    if (!d || d.busy) return;
    d.busy = true;
    drawDialog();
    focusStep();
    let out = null, err = null;
    try {
      out = d.form.route === 'settings'  // a plugin's settings: kept by the platform, the values typed only
        ? { answer: await api('POST', `api/plugins/${enc(d.name)}/settings`, { values: Object.fromEntries(Object.entries(d.values).filter(([, v]) => given(v))) }) }
        : d.form.route === 'settings-forget'  // one setting forgotten (0.15.0)
          ? { answer: await api('POST', `api/plugins/${enc(d.name)}/settings`, { values: {}, forget: [d.values.variable] }) }
          : await api('POST', `api/machines/${enc(d.name)}/ask`, { hook: d.form.hook, args: argsOf(d.form, d.values, d.accepted) });
    }
    catch (e) { err = e; }
    d.busy = false;
    if (dlg !== d) return;
    if (!err) {
      d.step = 'done';
      d.answer = out && out.answer;
    } else {
      const a = err.answer || {}, refused = err.status >= 400 && err.status < 500;
      d.words = a.words || err.message;
      if (refused && typeof a.accept === 'string' && !d.accepted.includes(a.accept)
          && d.form.fields.some((x) => x && x.type === 'accept' && x.name === a.accept)) {
        d.step = 'accept';
        d.accept = a.accept;
      } else d.step = refused ? 'refused' : 'failed';
    }
    drawDialog();
    focusStep();
    if (d.step === 'done' || d.step === 'failed') render();  // what the plugin holds now: its tables drawn again
  }

  function closed() {  // the focus back on the button that opened it, or the same one drawn again
    const d = dlg;
    dlg = null;
    const el = $('formDialog');
    if (el) el.innerHTML = '';
    if (!d) return;
    const back = (d.opener && d.opener.isConnected && d.opener)
      || [...data.querySelectorAll('button.form-open')].find((b) => `${b.dataset.form}|${b.dataset.values}` === d.key);
    if (back) back.focus({ preventScroll: true });
  }

  const chartsOf = (m) => (span === 'day' && day[m.name]) || (m.status && m.status.charts);
  function chartsBlock(m) {
    if (!m.status || !m.status.charts) return '';
    const btn = (v, text) => `<button type="button" data-span="${v}" aria-pressed="${span === v}">${text}</button>`;
    const drawn = Charts.cards(chartsOf(m), { id: m.name });
    return `<div class="stats-head"><div class="spans" role="group" aria-label="The charts' range">${btn('recent', 'Last 10 minutes')}${btn('day', 'Last day')}</div></div>`
      + `<div class="charts${span === 'day' && !day[m.name] ? ' loading' : ''}" id="charts-${esc(m.name)}">${drawn || '<div class="muted small">The charts begin with the second sample.</div>'}</div>`;
  }

  function switchRow(m) {
    const on = !off(m), held = invalid(m);  // not valid: off until it is, whatever the switch says
    const enable = `<label class="switch-row"${held ? ` title="${esc(notHere(m) ? `Not for this machine: ${whyOf(m)}` : `Disabled while not valid: ${whyOf(m)}`)}"` : ''}><button type="button" class="switch" role="switch" aria-checked="${on}" aria-label="${esc(m.title)}" data-toggle="${esc(m.name)}"${held ? ' disabled' : ''}></button>${on ? 'Enabled' : held ? (notHere(m) ? 'Disabled: not for this machine' : 'Disabled: not valid') : 'Disabled'}</label>`;
    // 0.10.2 (the user: "all plugins need a hide switch next to enable for the dock on the right"); 0.10.3 (the user: "the
    // dock hidden visible switch literally needs to say hidden (not lit) and visible (lit)"; "just hidden / visible"): lit,
    // its icon is on the right once the plugin is active; not lit, hidden while the plugin is as it was
    const hide = `<label class="switch-row" title="Hidden: its icon is not on the right, the plugin still works as before"><button type="button" class="switch" role="switch" aria-checked="${!m.hidden}" aria-label="${m.hidden ? 'Hidden' : 'Visible'}" data-hide="${esc(m.name)}"></button>${m.hidden ? 'Hidden' : 'Visible'}</label>`;
    return `<span class="switches">${enable}${hide}</span>`;
  }

  // a job's terminal panel: what an install or an update prints, as it comes (the user: "after the install is run a
  // terminal pops up in the plugin and shows the install progress")
  function jobState(j) {
    return j.running ? 'running…' : j.ok ? 'done' : j.ok === false ? 'ended with a failure' : '';
  }
  function jobTitle(m, j) {
    const what = (j.action === 'update' && j.what) || (checks[m.name] && checks[m.name].data && checks[m.name].data.distribution) || m.title;
    return j.action === 'update' ? `Updating ${what}'s packages` : PREPARING.includes((j.steps || [])[0]) && j.steps.length === 1
      ? `${m.title}: ${j.steps[0]}` : `Installing ${what}`;
  }
  function setupLog(m) {
    const j = jobs[m.name];
    if (j && j.open) {
      return `<div class="term-panel" data-panel="job-${esc(m.name)}"><div class="term-head"><span>${esc(jobTitle(m, j))}</span>`
        + `<span class="muted small state">${esc(jobState(j))}</span><button type="button" class="term-hide" data-machine="${esc(m.name)}" `
        + `aria-label="Hide the panel (the job goes on)">×</button></div><pre class="term" id="job-term-${esc(m.name)}" tabindex="0"></pre></div>`;
    }
    return (m.steps || []).length ? '<h4>Setup log</h4><div class="muted small">Nothing run here yet: a step\'s output shows in a terminal panel as it runs.</div>' : '';
  }

  // a plugin's check of this PC for what it installs, its Install (locked until every criterion is met), its packages'
  // update and its login terminal once installed
  function installHtml(m) {
    if (!hasHook(m, 'check')) return '';
    const c = checks[m.name], busy = m.setup && m.setup.running || (jobs[m.name] && jobs[m.name].running);
    const what = m.title.replace(/^WSL /, '');
    const again = `<button type="button" class="recheck" data-machine="${esc(m.name)}">Check again</button>`;
    // a terminal open stays while the check is asked again (0.17.0: the keyboard typing into it stays up)
    if (!c || c.loading) return `<h4>This PC for ${esc(what)}</h4><div class="muted small">Checking this PC…</div>${shellPanel(m)}`;
    if (c.error) return `<h4>This PC for ${esc(what)}</h4><p class="error">${esc(c.error)}</p>${again}${shellPanel(m)}`;
    const d = c.data;
    const items = d.criteria.map((x) => `<li class="${x.ok ? 'met' : 'unmet'}"><span class="mark" aria-hidden="true">${x.ok ? '✓' : '✗'}</span>`
      + `<span class="what"><span>${esc(x.title)}<span class="sr-only">: ${x.ok ? 'met' : 'not met'}</span></span><span class="sub">${esc(x.detail)}</span></span></li>`).join('');
    const install = d.installed ? '' : `<button type="button" class="install accent" data-machine="${esc(m.name)}" ${d.ready && !busy ? '' : 'disabled'}>Install ${esc(d.distribution || what)}</button>`;
    // a plugin with installs to choose from: its Terminal (0.13.0) and Update packages (0.14.0) are tasks of the one chosen
    const tools = !d.installed || shellInto(m) ? '' : `<button type="button" class="update" data-machine="${esc(m.name)}" ${busy ? 'disabled' : ''}>Update packages</button>`
      + shellButton(m);
    const said = d.installed ? `${d.distribution} is installed` : d.ready ? (busy ? 'Installing…' : 'Every criterion is met: the install is unlocked.') : `Locked: ${d.why}`;
    return `<h4>This PC for ${esc(what)}</h4><ul class="criteria">${items}</ul>`
      + `<div class="row install-row">${install}${tools}${again}<span class="muted small">${esc(said)}</span></div>${shellPanel(m)}`;
  }

  // the terminal's button: into the install chosen (0.12.0, status.terminalInto: the user, "select which one to terminal
  // in to"; "basically a selector for different installs"), Show when the one open is into it already
  const shellInto = (m) => (m.status && m.status.terminalInto) || '';
  function shellButton(m, title, b) {
    if (!hasHook(m, 'terminal')) return '';
    const into = shellInto(m), sh = shells[m.name], same = sh && (!into || !sh.into || sh.into === into);
    return `<button type="button" class="shell-open" data-machine="${esc(m.name)}"${b && b.disabled ? ' disabled' : ''}${b && b.note ? ` title="${esc(b.note)}"` : ''}>`
      + `${esc(same ? 'Show the terminal' : title || (into ? `Open a terminal in ${into}` : 'Open a terminal'))}</button>${offWhy(b)}`;
  }

  // A login terminal's panel (0.17.0): one element per terminal, kept alive across the page's redraws (the page draws a slot
  // where it goes, and drawData draws the pane anew around it), so a redraw never closes the on-screen keyboard nor drops a
  // word being typed. Under its lines, on a touch screen, the keys a phone's keyboard lacks: Esc, Tab, Ctrl (held for the
  // next key), the arrows, ^C, ^D and Paste.
  const shellPanel = (m) => (shells[m.name] ? `<div class="term-slot" data-shell-slot="${esc(m.name)}"></div>` : '');
  // how to type into it: a mouse's words as before, a finger's added on a touch screen, a phone's or a tablet's alone where
  // a finger is the only pointer (platform.css: a computer with a touch screen beside its mouse shows both)
  const HOW_TO_TYPE = '<span class="how-mouse">click, then type; Ctrl+Shift+C copies</span><span class="how-touch touch-only">tap, then type; press and hold to copy</span>';
  const TERM_KEYS = [['Escape', 'Esc', 'Escape'], ['Tab', 'Tab', 'Tab'], ['Ctrl', 'Ctrl', 'Control, held for the next key'],
    ['ArrowUp', '↑', 'Up'], ['ArrowDown', '↓', 'Down'], ['ArrowLeft', '←', 'Left'], ['ArrowRight', '→', 'Right'],
    ['^C', '^C', 'Control C: interrupt'], ['^D', '^D', 'Control D: end of input'], ['Paste', 'Paste', 'Paste what is copied']];
  function shellPanelEl(name) {  // made once, its words kept current
    const sh = shells[name];
    if (!sh) return null;
    if (!sh.panel) {
      const n = esc(name), wrap = document.createElement('div');
      wrap.innerHTML = `<div class="term-panel shell" data-panel="shell-${n}" data-touch-own><div class="term-head"><span class="term-title"></span>`
        + `<span class="muted small state"></span><button type="button" class="shell-close" data-machine="${n}" aria-label="Close the terminal">×</button></div>`
        + `<pre class="term interactive" id="shell-term-${n}" data-machine="${n}" aria-hidden="true"></pre>`
        + `<div class="term-keys touch-only" role="toolbar" aria-label="Keys a phone's keyboard lacks">`
        + TERM_KEYS.map(([k, text, words]) => `<button type="button" tabindex="-1" data-term-key="${k}" data-machine="${n}" aria-label="${words}"`
          + `${k === 'Ctrl' ? ' aria-pressed="false"' : ''}>${text}</button>`).join('')
        + '<span class="term-said" role="status"></span></div>'
        + `<textarea class="term-input" id="shell-in-${n}" data-machine="${n}" rows="1" ${kb('terminal')}></textarea>`
        + '<span class="term-composing" aria-hidden="true" hidden></span></div>';
      sh.panel = wrap.firstElementChild;
      keepBox(sh.panel.querySelector('textarea.term-input'));
      sh.panel.querySelector('pre.term').addEventListener('click', tapTerminal);  // on the lines themselves: Safari makes a click of a tap there only so
    }
    syncShellPanel(name);
    return sh.panel;
  }
  function syncShellPanel(name) {  // its words as the terminal is now: its title, how to type into it, or that it ended
    const sh = shells[name], p = sh && sh.panel;
    if (!p) return;
    p.querySelector('.term-title').textContent = sh.title || 'Terminal';
    const state = p.querySelector('.term-head .state'), alive = String(!!sh.alive);
    if (state.dataset.alive !== alive) { state.dataset.alive = alive; state.innerHTML = sh.alive ? HOW_TO_TYPE : 'ended'; }
    p.querySelector('textarea.term-input').setAttribute('aria-label', `Type into ${sh.title || 'the terminal'}`);
    p.querySelector('.term-keys').hidden = !sh.alive;
  }

  function pluginData(m) {
    const head = `<div class="data-head"><h2>${esc(m.title)}</h2>${switchRow(m)}</div><div class="muted small">${esc(m.about)}</div><p class="error" id="err-${esc(m.name)}"></p>`;
    if (userOff(m)) return `${head}${settingsButton(m)}<p class="muted">Disabled: the platform asks it nothing, it runs nothing here, and its icon is out of the tray. The switch enables it again.</p>`;
    const logged = (m.steps || []).length || m.setup;
    if (notHere(m)) {
      return `${head}<p class="muted">Not for this machine: ${esc(whyOf(m))}. It stays disabled here; no setup is offered, since none can make it valid on this machine.</p>`
        + (m.setup || jobs[m.name] ? setupLog(m) : '');
    }
    if (invalid(m)) {
      return `${head}${settingsButton(m)}<p class="muted">Disabled while it is not valid: ${esc(whyOf(m))}. ${(m.settings || []).length ? 'Its settings, above, can make it valid. '
        : hasHook(m, 'check') ? 'Its install, below, can make it valid. '
        : (m.steps || []).length ? 'Its setup, on the right, can make it valid. ' : ''}It is enabled again by itself once it is valid.</p>`
        + installHtml(m) + (logged || jobs[m.name] ? setupLog(m) : '');
    }
    drawnPaths[m.name] = pathsHtml(m);
    return head + settingsButton(m) + actionsHtml(m) + optionsHtml(m) + chartsBlock(m) + installHtml(m) + `<div id="paths-${esc(m.name)}">${drawnPaths[m.name]}</div>`
      + `<div id="tables-${esc(m.name)}">${tables(m)}${statTables(m)}</div>` + (logged || jobs[m.name] ? setupLog(m) : '');
  }

  function assistantData(a) {
    const head = `<div class="data-head"><h2>${esc(a.title)}</h2>${switchRow(a)}</div><div class="muted small">${esc(a.about)}</div><p class="error" id="err-${esc(a.name)}"></p>`;
    const said = userOff(a) ? '<p class="muted">Disabled: the platform does not host it. The switch enables it again.</p>'
      : invalid(a) ? `<p class="muted">Disabled while it is not valid: ${esc(whyOf(a))}. It is enabled again by itself once it is valid.</p>` : '';
    return `${head}${settingsButton(a)}${said}<h4>Where it is set up</h4><div class="small">Its key and account are its settings, above; its plan and model are set on the charts app's Plugins view. The platform hosts it.</div>`;
  }

  // -- Connections (0.10.0; the user, 2026-11-08: "the root plugin (platform) will need to visually illustrate how
  // plugins are connected to each other or to the main app/plugin/icon via IPC, all requests and interactions should be
  // classified and give the user a way to understand how the app and it's plugins communicate, visually"): who asks the
  // platform on the left (this page, a program), the platform and its login in the middle, its plugins, then what they
  // reach on the right (programs, hosts, the framework's other apps). A line per link and class: its colour the class,
  // its width how often, moving while it carried something in the last seconds, a dot running along it for each new
  // interaction. A box picked shows its own links and rows; a class switched off leaves the picture and the table.
  const CONNECTIONS = 'connections';
  const CLASS_ORDER = ['read', 'change', 'ask', 'stream', 'attach', 'login', 'process', 'network'];
  const COLS = { caller: [64, 112], app: [236, 150], plugin: [478, 180], outside: [704, 176] };  // x and width, of 800
  let traffic = null;  // the last GET api/traffic
  let trafficTimer = null;
  let trafficGen = 0;  // the latest ask of it: an older one's answer is dropped
  let trafficPaused = false;
  let trafficSeq = -1;  // the newest interaction drawn: newer ones run along their line
  let connShape = '';  // the parts and links drawn: the picture is built again only when they change
  let focusNode = null;  // a box picked: its own links and rows alone
  const kindsOff = new Set();  // classes switched off in the legend
  const still = () => !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const ago = (s) => (s < 1.5 ? 'just now' : s < 90 ? `${Math.round(s)} s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`);
  const clockOf = (t) => new Date(t * 1000).toLocaleTimeString();
  const cut = (s, n) => (s.length > n ? `${s.slice(0, Math.max(1, n - 1))}…` : s);
  const linkKey = (l) => `${l.from}|${l.to}|${l.kind}`;
  const nodeTitle = (t, id) => { const n = ((t && t.nodes) || []).find((x) => x.id === id); return n ? n.title : id; };
  const nodeTip = (n) => `${n.title}${n.sub ? ` (${n.sub})` : ''}${n.role === 'plugin' && n.state ? `: ${n.state}` : ''}`;
  const linkTip = (t, l) => `${nodeTitle(t, l.from)} → ${nodeTitle(t, l.to)}: ${l.kind}, ${l.count} time${l.count === 1 ? '' : 's'}`
    + `${l.failed ? ` (${l.failed} failed)` : ''}${l.ms ? `, ${l.ms} ms on average` : ''}; the last ${ago(t.now - l.last)}: ${l.what}`;

  function connectionsModel(t) {  // the parts in their columns, the links between parts drawn
    const nodes = (t.nodes || []).map((n) => ({ ...n, title: String(n.title || n.id) }));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const links = (t.links || []).filter((l) => !kindsOff.has(l.kind) && byId.has(l.from) && byId.has(l.to));
    const lastOf = new Map();
    links.forEach((l) => [l.from, l.to].forEach((id) => lastOf.set(id, Math.max(lastOf.get(id) || 0, l.last))));
    let outside = nodes.filter((n) => n.role === 'outside');
    const more = Math.max(0, outside.length - 16);  // the 16 reached last are drawn; the table names every one
    if (more) {
      const keep = new Set([...outside].sort((a, b) => (lastOf.get(b.id) || 0) - (lastOf.get(a.id) || 0)).slice(0, 16).map((n) => n.id));
      outside = outside.filter((n) => keep.has(n.id));
    }
    const KIND = { app: 0, process: 1, host: 2 }, STATE = { active: 0, attached: 0, unknown: 1, invalid: 2, disabled: 3 };
    outside.sort((a, b) => (KIND[a.kind] ?? 3) - (KIND[b.kind] ?? 3) || a.title.localeCompare(b.title));
    const plugins = nodes.filter((n) => n.role === 'plugin').sort((a, b) => (STATE[a.state] ?? 1) - (STATE[b.state] ?? 1) || a.title.localeCompare(b.title));
    const callers = nodes.filter((n) => n.role === 'caller').sort((a, b) => (a.id === 'page' ? -1 : b.id === 'page' ? 1 : a.title.localeCompare(b.title)));
    const app = nodes.find((n) => n.role === 'app'), login = nodes.find((n) => n.role === 'login');
    const ROW = 34, TOP = 30;
    const rows = Math.max(plugins.length, outside.length, callers.length, 4);
    const mid = TOP + (rows * ROW) / 2;
    const column = (list, role, c) => list.forEach((n, i) => Object.assign(n, { x: COLS[role][0], w: COLS[role][1], col: c, y: mid + (i - (list.length - 1) / 2) * ROW }));
    column(callers, 'caller', 0);
    column(plugins, 'plugin', 2);
    column(outside, 'outside', 3);
    if (app) Object.assign(app, { x: COLS.app[0], w: COLS.app[1], col: 1, y: login ? mid - 34 : mid });
    if (login) Object.assign(login, { x: COLS.app[0], w: COLS.app[1], col: 1, y: mid + 34 });
    const drawn = [...callers, ...(app ? [app] : []), ...(login ? [login] : []), ...plugins, ...outside];
    const ids = new Set(drawn.map((n) => n.id));
    return { nodes: drawn, byId, links: links.filter((l) => ids.has(l.from) && ids.has(l.to)), H: TOP + rows * ROW + 10, more };
  }
  const shapeOf = (m) => `${m.nodes.map((n) => `${n.id}:${n.state || ''}`).join(',')}/${m.links.map(linkKey).sort().join(',')}`;

  function edgeD(a, b, off) {  // a line from a to b; `off` sets apart several classes between the same two parts
    if (a.col === 1 && b.col === 1) {  // the platform and its login, one above the other
      const down = b.y > a.y;
      return `M${a.x + off} ${a.y + (down ? 13 : -13)}L${b.x + off} ${b.y + (down ? -13 : 13)}`;
    }
    if (a.col === b.col) {  // one plugin asking another: an arc on their right
      const x1 = a.x + a.w / 2, x2 = b.x + b.w / 2, r = 26 + Math.abs(a.y - b.y) / 3;
      return `M${x1} ${a.y + off}C${x1 + r} ${a.y + off} ${x2 + r} ${b.y + off} ${x2} ${b.y + off}`;
    }
    const fwd = b.x > a.x;
    const sx = fwd ? a.x + a.w / 2 : a.x - a.w / 2, tx = fwd ? b.x - b.w / 2 : b.x + b.w / 2, dx = (tx - sx) / 2;
    return `M${sx} ${a.y + off}C${sx + dx} ${a.y + off} ${tx - dx} ${b.y + off} ${tx} ${b.y + off}`;
  }

  function nodeSvg(n) {
    const w = n.w, ic = icon(n.icon || 'plug', 15).replace('<svg ', `<svg x="${-w / 2 + 8}" y="-7.5" `);
    const dot = n.role === 'plugin' ? `<circle class="dot" cx="${w / 2 - 10}" cy="0" r="3.5"/>` : '';
    // its row's whole height (34) a finger's to pick on a touch screen (0.17.0: rect.hit, unseen), the box drawn 26 high
    return `<g class="node role-${esc(n.role)} state-${esc(n.state || 'none')}" data-node="${esc(n.id)}" transform="translate(${n.x} ${n.y})"`
      + ` tabindex="0" role="button" aria-pressed="false" aria-label="${esc(nodeTip(n))}"><title>${esc(nodeTip(n))}</title>`
      + `<rect class="hit" x="${-w / 2}" y="-17" width="${w}" height="34" rx="7"/>`
      + `<rect x="${-w / 2}" y="-13" width="${w}" height="26" rx="7"/>${ic}<text x="${-w / 2 + 29}" y="4" data-room="${w - 29 - (dot ? 20 : 8)}">${esc(n.title)}</text>${dot}</g>`;
  }

  function fitLabels(svg) {  // a label longer than its box cut to fit as drawn (its whole name in the box's tooltip)
    svg.querySelectorAll('g.node text[data-room]').forEach((t) => {
      const room = Number(t.dataset.room), full = t.textContent;
      if (!room || t.getComputedTextLength() <= room) return;
      let lo = 1, hi = full.length - 1;
      while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        t.textContent = cut(full, mid + 1);
        if (t.getComputedTextLength() <= room) lo = mid; else hi = mid - 1;
      }
      t.textContent = cut(full, lo + 1);
    });
  }

  function connectionsSvg(m) {
    const pairs = new Map();
    m.links.forEach((l) => { const k = `${l.from}|${l.to}`; if (!pairs.has(k)) pairs.set(k, []); pairs.get(k).push(l.kind); });
    pairs.forEach((kinds) => kinds.sort((a, b) => CLASS_ORDER.indexOf(a) - CLASS_ORDER.indexOf(b)));
    const edges = m.links.map((l) => {
      const kinds = pairs.get(`${l.from}|${l.to}`), off = (kinds.indexOf(l.kind) - (kinds.length - 1) / 2) * 3.2;
      return `<path class="edge k-${esc(l.kind)}" data-link="${esc(linkKey(l))}" d="${edgeD(m.byId.get(l.from), m.byId.get(l.to), off)}"><title></title></path>`;
    }).join('');
    const heads = [['Asking', COLS.caller[0]], ['The platform', COLS.app[0]], ['Plugins', COLS.plugin[0]], ['Reached', COLS.outside[0]]]
      .map(([s, x]) => `<text class="col-head" x="${x}" y="14" text-anchor="middle">${s}</text>`).join('');
    return `<svg id="conn-svg" viewBox="0 0 800 ${m.H}" role="group" aria-label="Who talks to whom: ${m.nodes.length} parts, ${m.links.length} links">`
      + `${heads}<g class="edges">${edges}</g><g class="pulses" id="conn-pulses"></g><g class="nodes">${m.nodes.map(nodeSvg).join('')}</g></svg>`;
  }

  function paintLinks(t) {  // each line's width, whether it moves, its words; the box picked and what it talks to
    const svg = $('conn-svg');
    if (!svg) return;
    const byKey = new Map((t.links || []).map((l) => [linkKey(l), l]));
    const near = new Set();
    (t.links || []).forEach((l) => { if (l.from === focusNode) near.add(l.to); if (l.to === focusNode) near.add(l.from); });
    svg.querySelectorAll('path.edge').forEach((p) => {
      const l = byKey.get(p.dataset.link);
      if (!l) return;
      p.setAttribute('stroke-width', (1.2 + Math.min(3.6, Math.log10(l.count + 1) * 1.3)).toFixed(2));
      p.classList.toggle('busy', t.now - l.last < 4);
      p.classList.toggle('on', !!focusNode && (l.from === focusNode || l.to === focusNode));
      p.firstElementChild.textContent = linkTip(t, l);
    });
    svg.classList.toggle('focused', !!focusNode);
    svg.querySelectorAll('g.node').forEach((g) => {
      const id = g.dataset.node;
      g.classList.toggle('on', near.has(id));
      g.classList.toggle('picked', id === focusNode);
      g.setAttribute('aria-pressed', String(id === focusNode));
    });
  }

  function pulses(t, since) {  // a dot along its line for each interaction newer than the last drawn
    const g = $('conn-pulses');
    if (!g || since < 0 || still()) return;
    (t.recent || []).filter((r) => r.seq > since && !kindsOff.has(r.kind)).slice(0, 24).forEach((r, i) => {
      const p = document.querySelector(`#conn-svg path.edge[data-link="${CSS.escape(linkKey(r))}"]`);
      if (!p) return;
      setTimeout(() => {
        if (!p.isConnected) return;
        g.insertAdjacentHTML('beforeend', `<circle class="pulse k-${esc(r.kind)}" r="3.4"><animateMotion dur="0.9s" fill="freeze" begin="indefinite" path="${p.getAttribute('d')}"/></circle>`);
        const c = g.lastElementChild, a = c && c.firstElementChild;
        if (a && a.beginElement) a.beginElement();
        setTimeout(() => { if (c) c.remove(); }, 1000);
      }, i * 70);
    });
  }

  function summaryOf(t) {
    const total = (t.links || []).reduce((s, l) => s + l.count, 0), failed = (t.links || []).reduce((s, l) => s + l.failed, 0);
    return `since ${clockOf(t.since)} · ${total} interaction${total === 1 ? '' : 's'} on ${(t.links || []).length} link${(t.links || []).length === 1 ? '' : 's'}`
      + ` · ${failed} failed · ${trafficPaused ? 'paused' : 'asked every 2 s'}`;
  }

  function rowsHtml(t, since) {
    const rows = (t.recent || []).filter((r) => !kindsOff.has(r.kind) && (!focusNode || r.from === focusNode || r.to === focusNode)).slice(0, 60);
    if (!rows.length) return `<tr><td colspan="6" class="muted">${focusNode ? 'Nothing said to it or by it yet.' : 'Nothing yet.'}</td></tr>`;
    return rows.map((r) => `<tr class="${since >= 0 && r.seq > since ? 'new' : ''}${r.ok ? '' : ' failed'}"><td class="mono small">${esc(clockOf(r.at))}</td>`
      + `<td>${esc(nodeTitle(t, r.from))} → ${esc(nodeTitle(t, r.to))}</td><td><span class="kind k-${esc(r.kind)}">${esc(r.kind)}</span></td>`
      + `<td class="mono small what">${esc(r.what)}</td><td class="num">${r.times > 1 ? `×${r.times}` : ''}</td>`
      + `<td class="num">${r.ms ? `${r.ms} ms` : ''}${r.failed ? ` <span class="bad">${r.failed} failed</span>` : ''}</td></tr>`).join('');
  }

  function connectionsData() {
    return `<div class="data-head"><h2>Connections</h2><button type="button" class="conn-pause" aria-pressed="${trafficPaused}">${trafficPaused ? 'Resume' : 'Pause'}</button></div>
      <div class="muted small">who talks to whom on this platform, as it happens: a line for each kind of interaction between two parts</div>
      <p class="error" id="err-connections"></p>
      <div class="muted small" id="conn-summary" aria-live="off">${traffic ? esc(summaryOf(traffic)) : 'Asking the platform…'}</div>
      <div class="conn-picture" id="conn-graph" aria-live="off"></div>
      <div class="muted small" id="conn-note" aria-live="off"></div>
      <h4>Latest</h4><div class="muted small">the newest first; the same thing said again within 30 s is one row, counted</div>
      <table class="list conn-rows"><thead><tr><th>At</th><th>From → to</th><th>Class</th><th>What</th><th class="num">Times</th><th class="num">Took</th></tr></thead>
      <tbody id="conn-rows" aria-live="off"></tbody></table>`;
  }

  function connectionsSide(t) {
    const counts = {}, classes = (t && t.classes) || {};
    ((t && t.links) || []).forEach((l) => { counts[l.kind] = (counts[l.kind] || 0) + l.count; });
    const legend = CLASS_ORDER.filter((k) => classes[k]).map((k) => `<button type="button" class="legend-item k-${k}" data-kind="${k}" aria-pressed="${!kindsOff.has(k)}">`
      + `<span class="swatch-line" aria-hidden="true"></span><span class="what"><span>${k} <span class="muted">${counts[k] || 0}</span></span><span class="sub">${esc(classes[k])}</span></span></button>`).join('');
    const n = focusNode && t ? (t.nodes || []).find((x) => x.id === focusNode) : null;
    let picked = '';
    if (n) {
      const mine = (t.links || []).filter((l) => l.from === n.id || l.to === n.id);
      const rows = mine.map((l) => `<tr><td>${l.from === n.id ? `→ ${esc(nodeTitle(t, l.to))}` : `← ${esc(nodeTitle(t, l.from))}`}</td><td><span class="kind k-${esc(l.kind)}">${esc(l.kind)}</span></td>`
        + `<td class="num">${l.count}${l.failed ? ` <span class="bad">(${l.failed} failed)</span>` : ''}</td><td class="num">${l.ms ? `${l.ms} ms` : ''}</td></tr>`).join('');
      picked = `<h4>${esc(n.title)}</h4><div class="muted small">${esc(n.sub || n.role)}${n.role === 'plugin' && n.state ? ` · ${esc(n.state)}` : ''}</div>
        <div class="row">${n.role === 'plugin' && pluginOf(n.id) ? `<button type="button" data-select="${esc(n.id)}">Its page</button> ` : ''}<button type="button" class="conn-unpick">Every part</button></div>
        ${rows ? `<table class="list conn-links"><thead><tr><th>With</th><th>Class</th><th class="num">Times</th><th class="num">Mean</th></tr></thead><tbody>${rows}</tbody></table>` : '<div class="small muted">Nothing said to it or by it yet.</div>'}`;
    }
    return `<h3>${icon('plug', 20)} Connections</h3><div class="muted small">the platform, its page, its login, its plugins and what they reach</div>${picked}
      <h4>Classes</h4><div class="legend">${legend}</div><div class="muted small">A class switched off leaves the picture and the table.</div>
      <h4>Reading it</h4><p class="small">Who asks is on the left: this page, or a program. The platform asks its plugins; the platform and its plugins
      read and keep their settings through the login, under the platform; on the right, what they reach: programs, hosts, the framework's
      other apps. A line's colour is its class and its width how often; it moves while it carried something in the last seconds, and a dot
      runs along it for each new interaction. Pick a box to see its own links.</p>`;
  }

  function drawConnectionsSide() {  // drawn again with every answer; the legend's button that had the focus keeps it
    const a = document.activeElement, kind = a && side.contains(a) ? a.dataset.kind || (a.classList.contains('conn-unpick') ? '*' : '') : '';
    side.innerHTML = connectionsSide(traffic);
    const again = kind === '*' ? side.querySelector('.conn-unpick') : kind ? side.querySelector(`[data-kind="${kind}"]`) : null;
    if (again) again.focus({ preventScroll: true });
  }

  function updateConnections(rebuild) {
    const t = traffic, graph = $('conn-graph');
    if (!t || !graph || selected() !== CONNECTIONS) return;
    const m = connectionsModel(t), shape = shapeOf(m);
    if (rebuild || shape !== connShape || !$('conn-svg')) {
      graph.innerHTML = connectionsSvg(m);
      fitLabels($('conn-svg'));
      connShape = shape;
    }
    paintLinks(t);
    const since = trafficSeq;
    pulses(t, since);
    $('conn-summary').textContent = summaryOf(t);
    $('conn-note').textContent = (m.more ? `${m.more} more reached are not drawn (the table names them). ` : '')
      + ((t.hidden || []).length ? `Not drawn: ${t.hidden.join(', ')} (disabled or not valid, and nothing said to them).` : '');
    $('conn-rows').innerHTML = rowsHtml(t, since);
    trafficSeq = t.seq;
    drawConnectionsSide();
  }

  async function loadTraffic() {  // asked every 2 s while Connections is shown (one ask at a time)
    clearTimeout(trafficTimer);
    const g = ++trafficGen;
    if (selected() !== CONNECTIONS || trafficPaused || document.hidden) return;
    try {
      const t = await api('GET', 'api/traffic?last=200');
      if (g !== trafficGen || selected() !== CONNECTIONS) return;
      traffic = t;
      const err = $('err-connections');
      if (err) err.textContent = '';
      updateConnections(false);
    } catch (e) {
      if (g !== trafficGen) return;
      const err = $('err-connections');
      if (err) err.textContent = e.message;
    }
    if (g === trafficGen && selected() === CONNECTIONS && !trafficPaused && !document.hidden) trafficTimer = setTimeout(loadTraffic, 2000);
  }

  function pickNode(id) {
    focusNode = focusNode === id ? null : id;
    updateConnections(false);
  }

  function drawData() {
    const sel = selected();
    const m = st.machines[sel], a = (st.assistants || []).find((x) => x.name === sel);
    const scrolled = data.scrollTop;
    if (m && hasHook(m, 'check') && !userOff(m)) {  // its check of this PC: asked when shown, again after a minute
      const c = checks[m.name];
      if (!c || (!c.loading && Date.now() - c.at > 60000)) setTimeout(() => loadCheck(m.name), 0);
    }
    const html = sel === 'machine' ? machineData() : sel === CONNECTIONS ? connectionsData() : m ? pluginData(m) : a ? assistantData(a)
      : `<p class="muted">Nothing named ${esc(sel)} here.</p>`;
    // a terminal's panel shown stays where it is, the pane drawn anew around it (0.17.0): its box keeps the focus, the
    // on-screen keyboard stays up and a word being composed goes on; else the pane drawn anew and the panel put in its slot
    const panel = m && shells[m.name] ? shells[m.name].panel : null;
    if (!(panel && panel.parentNode === data && drawAround(panel, html, m.name))) {
      const typing = !!panel && panel.contains(document.activeElement);
      data.innerHTML = html;
      placeShells(typing);
    }
    if (sel === CONNECTIONS) updateConnections(true);
    Charts.draw(data);
    Object.entries(jobs).forEach(([name, j]) => { if (j.open) j.term.attach($(`job-term-${name}`)); });
    Object.values(shells).forEach((sh) => { if (sh.panel && !sh.panel.isConnected) sh.term.attach(null); });  // not shown: not drawn
    data.scrollTop = scrolled;
  }
  function drawAround(panel, html, name) {  // the pane's other parts replaced, the panel never taken out (false: no slot for it)
    const t = document.createElement('template');
    t.innerHTML = html;
    const parts = [...t.content.childNodes], at = parts.findIndex((n) => n.nodeType === 1 && n.getAttribute('data-shell-slot') === name);
    if (at < 0) return false;
    [...data.childNodes].forEach((n) => { if (n !== panel) n.remove(); });
    panel.before(...parts.slice(0, at));
    panel.after(...parts.slice(at + 1));
    syncShellPanel(name);
    return true;
  }
  function placeShells(refocus) {  // each terminal's panel in its slot (made, or put back after another view), drawn at its end
    data.querySelectorAll('[data-shell-slot]').forEach((slot) => {
      const name = slot.getAttribute('data-shell-slot'), panel = shellPanelEl(name);
      if (!panel) { slot.remove(); return; }
      slot.replaceWith(panel);
      shells[name].term.attach(panel.querySelector('pre.term'));
      if (refocus) panel.querySelector('textarea.term-input').focus({ preventScroll: true });  // typed in before: typed in still
    });
  }

  // -- the right: the selected one's specifics ----------------------------------------------------------
  function facts(s) {
    // a status's own facts: neither its lists, its charts, its choices nor its summary
    const skip = new Set(['rules', 'services', 'startups', 'processes', 'tables', 'charts', 'options', 'actions', 'forms', 'paths', 'summary', 'present', 'problem', 'valid', 'why']);
    const flat = Object.entries(s || {}).filter(([k, v]) => !skip.has(k) && v !== '' && v !== null && typeof v !== 'object');
    const nested = Object.entries(s || {}).filter(([k, v]) => !skip.has(k) && v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length);
    const show = (v) => (v === true ? 'yes' : v === false ? 'no' : typeof v === 'object' ? Object.entries(v).map(([a, b]) => `${a} ${b}`).join(', ') : v);
    const rows = [...flat, ...nested].map(([k, v]) => `<dt>${esc(label(k))}</dt><dd>${esc(typeof v === 'object' ? Object.entries(v).map(([a, b]) => `${a}: ${show(b)}`).join('; ') : show(v))}</dd>`);
    return rows.length ? `<dl class="facts">${rows.join('')}</dl>` : '';
  }

  function machineSide() {
    const f = st.machine, d = st.docker;
    return `<h3>${icon('chip', 20)} ${esc(f.host)}</h3><div class="muted small">this machine</div>
      <dl class="facts">
        <dt>System</dt><dd>${esc(f.system)} ${esc(f.release)} on ${esc(f.machine)}</dd>
        <dt>Processor</dt><dd>${esc(f.cpus)} cpus${f.processor ? ` · ${esc(f.processor)}` : ''}</dd>
        <dt>Memory</dt><dd>${esc(f.memoryMb)} MB</dd>
        <dt>Python</dt><dd>${esc(f.python)}</dd>
        <dt>Docker here</dt><dd>${d.available ? `engine ${esc(d.engine)} (${esc(d.command)})` : esc(d.problem || 'not installed')}${d.wsl ? ` · WSL 2 ${d.wsl.present ? 'present' : 'absent'}` : ''}</dd>
      </dl>
      <h4>Active plugins</h4><div class="small">${(st.active || []).length ? st.active.map(esc).join(', ') : 'none'}</div>
      ${(st.disabled || []).length ? `<h4>Disabled</h4><div class="small">${st.disabled.map(esc).join(', ')}</div>` : ''}
      <h4>Platform</h4><div class="small">${esc(st.app.title)} ${esc(st.app.api ? 'API ' + st.app.api : '')} at ${esc(st.app.url)}</div>`;
  }

  function pluginSide(m) {
    const head = `<h3>${icon(m.icon || 'chip', 20)} ${esc(m.title)} ${chipOf(m)}</h3><div class="muted small">${esc(m.name)}${m.version ? ` · ${esc(m.version)}` : ''}</div>`;
    if (userOff(m)) return `${head}<p class="summary">Disabled: enable it with the switch on its page.</p>`;
    const running = m.setup && m.setup.running;
    const steps = notHere(m) ? [] : m.steps || [];  // not for this machine: nothing to set up
    const said = notHere(m) ? `Not for this machine: ${whyOf(m)}` : invalid(m) ? `Disabled while not valid: ${whyOf(m)}` : stateLine(m);
    const c = hasHook(m, 'check') ? checks[m.name] : null;  // a plugin that checks this PC: its install locked until it passes
    const locked = c !== null && !(c && c.data && (c.data.ready || c.data.installed));
    const off_ = (s) => running || (locked && !PREPARING.includes(s));
    return `${head}<p class="summary">${esc(said)}</p>${m.status && m.status.problem && !invalid(m) ? `<p class="error">${esc(m.status.problem)}</p>` : ''}
      ${notHere(m) ? '' : facts(m.status)}
      ${steps.length ? `<h4>Set up</h4><div class="steps"><button type="button" class="setup accent" data-machine="${esc(m.name)}" ${off_('everything') ? 'disabled' : ''}>Everything</button>
        ${steps.map((s) => `<button type="button" class="step" data-machine="${esc(m.name)}" data-step="${esc(s)}" ${off_(s) ? 'disabled' : ''}>${esc(s)}</button>`).join('')}</div>
        <div class="muted small">${running ? 'Running: its output is in the middle.' : locked ? `The install is locked until this PC meets what it needs (${PREPARING.join(', ')} prepare it).` : 'Each step\'s output shows in the middle as it runs.'}</div>` : ''}`;
  }

  function assistantSide(a) {
    return `<h3>${icon(a.icon || 'analysis', 20)} ${esc(a.title)} ${chipOf(a)}</h3><div class="muted small">${esc(a.name)}${a.version ? ` · ${esc(a.version)}` : ''}</div>
      <p class="summary">${esc(userOff(a) ? 'Disabled: enable it with the switch on its page.' : invalid(a) ? `Disabled while not valid: ${whyOf(a)}` : 'active')}</p>
      <dl class="facts"><dt>vendor</dt><dd>${esc(a.vendor || '')}</dd><dt>model</dt><dd>${esc(a.model || '')}</dd></dl>`;
  }

  function drawSide() {
    const sel = selected();
    const m = st.machines[sel], a = (st.assistants || []).find((x) => x.name === sel);
    if (sel === CONNECTIONS) { drawConnectionsSide(); return; }
    side.innerHTML = sel === 'machine' ? machineSide() : m ? pluginSide(m) : a ? assistantSide(a) : '';
  }

  function draw() {
    if (!st) return;
    drawRail();
    drawList();
    drawData();
    drawSide();
    schedule();
    if (selected() === CONNECTIONS) loadTraffic();
    else { clearTimeout(trafficTimer); trafficGen += 1; }
  }

  async function render() {
    const g = ++gen;
    let fresh;
    try { fresh = await Promise.all([api('GET', 'api/status'), api('GET', 'api/tray')]); }
    catch (e) {
      if (g !== gen) return;
      // a terminal on the page stays where it is, typed into still (0.17.0: a view never replaces the field typed in): the
      // trouble said at the head of its plugin's page, the next answer drawing it all again; else the pane says it, as before
      const line = st && data.querySelector('.term-panel.shell') ? $(`err-${selected()}`) : null;
      if (line) line.textContent = e.message; else data.innerHTML = `<p class="error">${esc(e.message)}</p>`;
      return;
    }
    if (g !== gen) return;  // something changed meanwhile: a newer answer is on its way
    [st, tray] = fresh;
    draw();
    Object.values(st.machines).forEach((m) => { if (m.setup && m.setup.running && !(jobs[m.name] && jobs[m.name].running)) follow(m.name, m.setup.action, m.setup.steps); });
  }

  // -- the shown plugin asked again while it is on the page, drawn in place: its figures at their interval (the day's
  // every 30 s), its tables every TABLES_EVERY s (a WSL distribution's services, also while it is stopped, so they show once
  // it runs; an admin's services and startups; a firewall's rules) -------------------------------------------------------
  const TABLES_EVERY = 30;
  const tabled = (m) => {
    const s = m.status || {};
    return (s.tables || []).length > 0 || ['rules', 'services', 'startups', 'processes'].some((k) => s[k] && typeof s[k] === 'object');
  };
  function shown() {
    const m = st && st.machines[selected()];
    return m && !off(m) && m.status && (m.status.charts || tabled(m) || pathsOf(m).length) ? m : null;
  }
  function schedule() {
    clearTimeout(live);
    const m = shown();
    if (!m || document.hidden) return;
    const every = pathRunning(m) ? 1 : !m.status.charts ? TABLES_EVERY : span === 'day' ? 30 : Math.max(1, Number(m.status.charts.interval) || 2);
    live = setTimeout(() => refresh(m.name), every * 1000);
  }
  async function refresh(name) {
    clearTimeout(live);
    if (selected() !== name) return;
    const g = gen;
    try {
      const was = st.machines[name], charted = !!(was && was.status && was.status.charts);  // the day's figures: a charted plugin's
      const [m, d] = await Promise.all([api('GET', `api/machines/${encodeURIComponent(name)}`),
        span === 'day' && charted ? api('POST', `api/machines/${encodeURIComponent(name)}/ask`, { hook: 'charts', args: ['day'] }) : null]);
      if (g === gen) {  // nothing changed meanwhile (a plugin disabled or enabled, the page asked again)
        if (d) day[name] = d.answer;
        st.machines[name] = m;
        if (selected() === name) redrawShown(m);
      }
    } catch (e) { if (g === gen) say(name, e.message); }
    schedule();
  }
  // a button or a box focused in what is drawn again (a row's Remove, a service's Start; a group's or a heading's (+) or
  // (−), a rule's box, Move to: by its table, group and key, 0.16.0) is focused again after: the same one
  const FOCUSED = 'button[data-machine], input[data-machine], select[data-machine]';
  const keyOf = (b) => [b.className, b.dataset.machine, b.dataset.form || b.dataset.hook || '', b.dataset.values || b.dataset.args || '',
    b.dataset.table, b.dataset.group, b.dataset.key].join('|');
  function keepFocus(draw) {
    const a = document.activeElement;
    const key = a && data.contains(a) && a.matches && a.matches(FOCUSED) ? keyOf(a) : null;
    draw();
    if (!key || data.contains(a)) return;
    const again = [...data.querySelectorAll(FOCUSED)].find((b) => keyOf(b) === key);
    if (again) again.focus({ preventScroll: true });
  }
  function redrawShown(m) {
    const box = $(`charts-${m.name}`), t = $(`tables-${m.name}`), pz = $(`paths-${m.name}`);
    if (pz && !off(m)) {  // its paths drawn again only when they changed: the moving traffic goes on
      const html = pathsHtml(m);
      if (html !== drawnPaths[m.name]) { pz.innerHTML = html; drawnPaths[m.name] = html; }
    }
    keepFocus(() => {
      if (!off(m) && !m.status.charts && t) {
        t.innerHTML = tables(m) + statTables(m);  // its tables alone: a terminal or a job's panel beside them stays as it is
      } else if (off(m) || !box || !Charts.update(box, chartsOf(m), { id: m.name })) { drawData(); }  // other charts: drawn anew
      else {
        box.classList.remove('loading');
        if (t) t.innerHTML = tables(m) + statTables(m);
      }
    });
    drawSide();
    const sub = list.querySelector(`.item[data-select="${CSS.escape(m.name)}"] .sub`);
    if (sub) sub.textContent = stateLine(m);
  }
  function setSpan(v) {
    if (v === span) return;
    span = v;
    drawData();  // the frame kept, faded while the day is asked
    const m = shown();
    if (m) refresh(m.name);
  }

  // -- what the page asks -------------------------------------------------------------------------------
  async function ask(name, hook, args) {
    try { await api('POST', `api/machines/${encodeURIComponent(name)}/ask`, { hook, args }); }
    catch (e) { say(name, e.message); return false; }
    await render();
    return true;
  }

  async function choose(name, hook, value) {
    // the choice shows at once, and a UI preference (the theme) is applied to this page as soon as the plugin has
    // it; the rest (its facts, the list) follows once the platform has asked every plugin again (a few seconds)
    const had = document.activeElement && document.activeElement.matches && document.activeElement.matches('button.choice');
    data.querySelectorAll(`button.choice[data-hook="${CSS.escape(hook)}"]`).forEach((b) => {
      const on = b.dataset.value === value;
      b.setAttribute('aria-checked', String(on));
      b.classList.toggle('active', on);
      b.tabIndex = on ? 0 : -1;
    });
    try { await api('POST', `api/machines/${encodeURIComponent(name)}/ask`, { hook, args: [value] }); }
    catch (e) { say(name, e.message); return; }
    say(name, '');
    if (window.LiminalTheme) await window.LiminalTheme.load();
    await render();
    const again = data.querySelector(`button.choice[data-hook="${CSS.escape(hook)}"][data-value="${CSS.escape(value)}"]`);
    if (again && had) again.focus({ preventScroll: true });
  }

  // a plugin's state in what the page holds (this machine's table, the list, its page and switch, the tray): `answer`
  // is the platform's word on it; without one, the state expected until the platform answers
  function mark(name, on, answer) {
    if (!st.machines[name]) {  // an AI assistant: its row in the list, its icon in the dock (0.10.2)
      st.assistants = (st.assistants || []).map((a) => (a.name !== name ? a : answer
        || { ...a, enabled: on, valid: on ? a.valid : null, why: on ? a.why : '', state: on ? (a.valid === false ? 'invalid' : 'active') : 'disabled' }));
      const a = pluginOf(name);
      trayFollows(name, !!a && !off(a));
      return;
    }
    const m = st.machines[name];
    st.machines[name] = answer || { ...m, enabled: on, valid: on ? true : null, why: '', state: on ? 'active' : 'disabled', asks: on ? m.asks : [],
      status: on ? { ...(m.status || {}), present: true, summary: 'enabling…' } : { present: null, summary: 'disabled: the platform asks it nothing' } };
    const order = Object.keys(st.machines);
    const present = !off(st.machines[name]);
    st.disabled = order.filter((n) => (n === name ? !on : (st.disabled || []).includes(n)));
    st.active = order.filter((n) => (n === name ? present : (st.active || []).includes(n)));
    trayFollows(name, present);
  }

  // a plugin hidden, or visible again: at once on the page, then the platform's tray (0.10.2)
  async function setHidden(name, on, refocus) {
    const p = st && pluginOf(name);
    if (!p) return;
    const was = !!p.hidden;
    const focusHide = () => { const b = data.querySelector(`button.switch[data-hide="${CSS.escape(name)}"]`); if (b) b.focus({ preventScroll: true }); };
    p.hidden = on;
    trayFollows(name, !off(p));
    gen++;
    draw();
    if (refocus) focusHide();
    try {
      const answer = await api('POST', `api/plugins/${encodeURIComponent(name)}/hidden`, { on });
      if (answer && answer.tray) tray = answer.tray;
    } catch (e) {  // put back as it was
      p.hidden = was;
      trayFollows(name, !off(p));
      gen++;
      draw();
      say(name, e.message);
      return;
    }
    gen++;
    const focused = refocus || (document.activeElement && document.activeElement.matches && document.activeElement.matches('button.switch[data-hide]'));
    draw();
    if (focused) focusHide();
  }

  function focusSwitch(name) {
    const again = data.querySelector(`button.switch[data-toggle="${CSS.escape(name)}"]`);
    if (again) again.focus({ preventScroll: true });
  }

  async function setEnabled(name, on, refocus) {
    // every view shows it at once (the tray, this machine's table, the list, the plugin's page and switch), then
    // the platform's answer for the plugin; the rest (the Docker instances a machine runs) once the platform has
    // asked every plugin again, which takes a few seconds with the WSL plugins
    if (!st || !(st.machines[name] || (st.assistants || []).some((a) => a.name === name))) return;
    const before = { machine: st.machines[name], assistants: st.assistants, active: st.active, disabled: st.disabled, tray };
    gen++;
    mark(name, on);
    delete day[name];
    draw();
    if (refocus) focusSwitch(name);
    let answer;
    try { answer = await api('POST', `api/plugins/${encodeURIComponent(name)}/enabled`, { on }); }
    catch (e) {  // put back as it was
      gen++;
      if (before.machine) st.machines[name] = before.machine;
      st.assistants = before.assistants;
      st.active = before.active;
      st.disabled = before.disabled;
      tray = before.tray;
      draw();
      say(name, e.message);
      return;
    }
    gen++;
    mark(name, on, answer);
    const focused = refocus || (document.activeElement && document.activeElement.matches && document.activeElement.matches('button.switch'));
    draw();
    if (focused) focusSwitch(name);
    render();
  }

  // -- jobs: a setup (its steps, everything, the install) or the packages' update, followed in a terminal panel ------------
  async function setup(name, steps) {
    try { await api('POST', `api/machines/${enc(name)}/setup`, steps ? { steps } : {}); }
    catch (e) { say(name, e.message); return; }
    follow(name, 'setup', steps || []);
  }

  async function runJob(name, action) {  // the Install (everything) or the packages' update
    const what = action === 'update' ? shellInto(pluginOf(name) || {}) : '';  // the install chosen, which it updates (0.14.0)
    try { await api('POST', `api/machines/${enc(name)}/job`, { action }); }
    catch (e) { say(name, e.message); return; }
    follow(name, action === 'update' ? 'update' : 'setup', [], what);
  }

  function follow(name, action, steps, what) {  // the panel pops up and follows the job from its start
    const was = jobs[name];
    if (was) { clearTimeout(was.timer); was.term.attach(null); }  // the last job's lines no longer followed (0.17.0)
    jobs[name] = { term: LiminalTerminal.create(null), offset: 0, open: true, action, steps: steps || [], running: true, ok: null, timer: null, what: what || '' };
    say(name, '');
    if (st.machines[name]) st.machines[name].setup = { running: true, action };
    if (selected() === name) { drawData(); drawSide(); }
    pollJob(name);
  }

  const pause = (ms) => new Promise((r) => setTimeout(r, ms));
  // what came after `offset`, never what was drawn already (two answers can overlap): the text to draw, the new offset
  function fresh(offset, got) {
    const skip = Math.max(0, offset - (got.from ?? offset));
    return [got.text && got.text.length > skip ? got.text.slice(skip) : '', Math.max(offset, got.offset ?? offset)];
  }

  async function pollJob(name) {  // one read at a time, held by the platform until the job prints more (or 2 s)
    const j = jobs[name];
    if (!j || j.reading) return;
    j.reading = true;
    while (jobs[name] === j) {
      try {
        const got = await api('GET', `api/machines/${enc(name)}/job?since=${j.offset}&wait=2`);
        const [text, offset] = fresh(j.offset, got);
        j.term.write(text);
        j.offset = offset;
        j.running = !!got.running;
        j.ok = got.ok;
        if (!j.running && got.error) j.term.write(`\n${got.error}\n`);
      } catch (e) {
        j.term.write(`\n${e.message}\n`);
        j.running = false;
      }
      const state = document.querySelector(`[data-panel="job-${CSS.escape(name)}"] .state`);
      if (state) state.textContent = jobState(j);
      if (!j.running) break;
      if (document.hidden) await pause(1000);
    }
    j.reading = false;
    if (jobs[name] !== j) return;
    delete checks[name];  // installed now, perhaps: asked again
    await render();
  }

  async function loadCheck(name, fresh) {
    const c = checks[name];
    if (c && (c.loading || (!fresh && Date.now() - c.at < 60000))) return;
    checks[name] = { loading: true, at: Date.now() };
    try { checks[name] = { data: await api('GET', `api/machines/${enc(name)}/check`), at: Date.now() }; }
    catch (e) { checks[name] = { error: e.message, at: Date.now() }; }
    if (selected() === name) { drawData(); drawSide(); }
  }

  // -- a login terminal (the user: "the plugin also allows for a user to login through a terminal in to the environment")
  async function openShell(name) {
    const into = shellInto(pluginOf(name) || {});
    if (shells[name] && (!into || !shells[name].into || shells[name].into === into)) { showShell(name); return; }
    if (shells[name]) await closeShell(name);  // another install chosen: its terminal instead
    let got;
    try { got = await api('POST', `api/machines/${enc(name)}/terminal`, {}); }
    catch (e) { say(name, e.message); return; }
    // its panel made once and kept (0.17.0), the cursor followed sideways on a touch screen; a Ctrl held from its key row
    const sh = { term: LiminalTerminal.create(null, { cursor: true, followCursor: () => !!(T && T.touch) }), offset: got.offset, alive: got.alive,
      title: got.title, into, queue: '', sending: null, reading: false, panel: null, ctrl: false };
    shells[name] = sh;
    sh.term.write(got.text);
    drawData();
    showShell(name);
    readShell(name);
  }
  function showShell(name) {  // typed into at once with a mouse or a keyboard; after a finger's tap only brought into view,
    // its keyboard called up by a tap on its lines (0.17.0: none unasked)
    const el = $(`shell-in-${name}`);
    if (el && !autofocus(el)) el.closest('.term-panel').scrollIntoView({ block: 'nearest' });
  }

  // one read at a time, held open by the platform until the shell prints (its echo at once), nothing drawn twice
  async function readShell(name) {
    const sh = shells[name];
    if (!sh || sh.reading) return;
    sh.reading = true;
    while (shells[name] === sh && sh.alive) {
      try {
        const got = await api('GET', `api/machines/${enc(name)}/terminal?since=${sh.offset}&wait=2`);
        const [text, offset] = fresh(sh.offset, got);
        sh.term.write(text);
        sh.offset = offset;
        if (!got.alive) sh.alive = false;
      } catch (e) {
        sh.alive = false;
      }
      if (document.hidden) await pause(1000);
    }
    sh.reading = false;
    if (shells[name] === sh) syncShellPanel(name);  // ended: said so, its key row put away
  }

  function type(name, keys) {  // the keys typed, sent in small batches; the echo comes back through the read held open
    const sh = shells[name];
    if (!sh || !sh.alive || !keys) return;
    sh.queue += keys;
    if (sh.sending) return;
    sh.sending = setTimeout(async () => {
      const out = sh.queue;
      sh.queue = '';
      sh.sending = null;
      try { await api('POST', `api/machines/${enc(name)}/terminal/input`, { data: out }); }
      catch (e) { sh.term.write(`\r\n${e.message}\r\n`); }
    }, 8);
  }

  async function closeShell(name) {
    const sh = shells[name];
    if (!sh) return;
    delete shells[name];  // its read ends with it
    sh.term.attach(null);  // its lines' scrolls and size no longer followed (0.17.0)
    try { await api('POST', `api/machines/${enc(name)}/terminal/close`, {}); } catch (e) { /* gone already */ }
    drawData();
  }

  document.addEventListener('click', (e) => {
    const pz = e.target.closest('button.conn-pause');  // Connections: pause or resume the asking
    if (pz) {
      trafficPaused = !trafficPaused;
      pz.setAttribute('aria-pressed', String(trafficPaused));
      pz.textContent = trafficPaused ? 'Resume' : 'Pause';
      if (traffic) $('conn-summary').textContent = summaryOf(traffic);
      if (trafficPaused) { clearTimeout(trafficTimer); trafficGen += 1; } else loadTraffic();
      return;
    }
    const lg = e.target.closest('button.legend-item[data-kind]');  // a class switched off or on
    if (lg) { const k = lg.dataset.kind; if (kindsOff.has(k)) kindsOff.delete(k); else kindsOff.add(k); updateConnections(true); return; }
    if (e.target.closest('button.conn-unpick')) { focusNode = null; updateConnections(false); return; }
    const nd = e.target.closest('#conn-svg [data-node]');  // a box picked, or picked again to let it go
    if (nd) { pickNode(nd.dataset.node); return; }
    if (e.target.closest('#conn-svg')) { if (focusNode) { focusNode = null; updateConnections(false); } return; }
    const sw = e.target.closest('button.switch[data-toggle]');
    if (sw) { setEnabled(sw.dataset.toggle, sw.getAttribute('aria-checked') !== 'true', document.activeElement === sw || e.detail === 0); return; }
    const hs = e.target.closest('button.switch[data-hide]');  // lit: visible, so a click hides it; not lit: shown again
    if (hs) { setHidden(hs.dataset.hide, hs.getAttribute('aria-checked') === 'true', document.activeElement === hs || e.detail === 0); return; }
    const tk = e.target.closest('button[data-term-key]');  // a key of a terminal's key row (0.17.0)
    if (tk) { termKey(tk); return; }
    const cell = fingered() && e.target.matches('table.grouped td.pick') ? e.target : null;  // a finger's tap beside a rule's box: the box's (0.17.0)
    if (cell) { const x = cell.querySelector('input[type="checkbox"]'); if (x && !x.disabled) x.click(); return; }
    const rp = e.target.closest('button.row-pick[data-key], tr[data-pick-row]');  // an install chosen by a click on its row (0.13.0)
    if (rp && (e.target.closest('button.row-pick') || !e.target.closest('button, a, input, select, label'))) { pickRow(rp); return; }
    const ex = e.target.closest('button.expander[data-group]');  // a group opened (+) or closed (−), or a name under it
    if (ex) { toggleGroup(ex); return; }
    const pr = e.target.closest('input.pick-row[data-key]');  // a rule chosen, or not
    if (pr) { pickRows(pr, [pr.dataset.key], pr.checked, pickSel('input.pick-row', pr, `[data-key="${CSS.escape(pr.dataset.key)}"]`)); return; }
    const pg = e.target.closest('input.pick-group[data-group]');  // every rule a group lists chosen, or none; a name's box: its own (0.16.0)
    if (pg) {
      const t = tableOf(pg.dataset.machine, pg.dataset.table), id = pg.dataset.group;
      pickRows(pg, t ? rowsOf(t).filter((r) => r.group === id || r.sub === id).map((r) => r.key) : [], pg.checked,
        pickSel('input.pick-group', pg, `[data-group="${CSS.escape(id)}"]`));
      return;
    }
    const mg = e.target.closest('button.move-go[data-table]');
    if (mg) { if (!mg.disabled) moveChosen(mg); return; }
    const mc = e.target.closest('button.move-clear[data-table]');
    if (mc) { chosenOf(mc.dataset.machine, mc.dataset.table).clear(); redrawTables(mc.dataset.machine, pickSel('select.move-to', mc)); return; }
    const pick = e.target.closest('[data-select]');
    if (pick) { location.hash = pick.dataset.select === 'machine' ? '' : pick.dataset.select; return; }
    const sp = e.target.closest('button[data-span]');
    if (sp) { setSpan(sp.dataset.span); return; }
    const c = e.target.closest('button.choice[data-hook]');
    if (c) { if (c.getAttribute('aria-checked') !== 'true') choose(c.dataset.machine, c.dataset.hook, c.dataset.value); return; }
    const ins = e.target.closest('button.install[data-machine]');
    if (ins) { runJob(ins.dataset.machine, 'install'); return; }
    const upd = e.target.closest('button.update[data-machine]');
    if (upd) { runJob(upd.dataset.machine, 'update'); return; }
    const rc = e.target.closest('button.recheck[data-machine]');
    if (rc) { loadCheck(rc.dataset.machine, true); return; }
    const hide = e.target.closest('button.term-hide[data-machine]');
    if (hide) { const j = jobs[hide.dataset.machine]; if (j) j.open = false; drawData(); return; }
    const so = e.target.closest('button.shell-open[data-machine]');
    if (so) { openShell(so.dataset.machine); return; }
    const sc = e.target.closest('button.shell-close[data-machine]');
    if (sc) { closeShell(sc.dataset.machine); return; }
    const go = e.target.closest('button.setup, button.step');
    if (go) { setup(go.dataset.machine, go.dataset.step ? [go.dataset.step] : null); return; }
    const se = e.target.closest('button.settings-open[data-machine]');  // every setting, or the one an entry names (0.15.0)
    if (se) { openForm(se.dataset.machine, se.dataset.variable ? `${SETTINGS}:${se.dataset.variable}` : SETTINGS, {}, se); return; }
    const sf = e.target.closest('button.settings-forget[data-machine]');
    if (sf) { openForm(sf.dataset.machine, `${FORGET}:${sf.dataset.variable}`, { variable: sf.dataset.variable, label: sf.dataset.label }, sf); return; }
    const fo = e.target.closest('button.form-open[data-form]');
    if (fo) {  // one of a plugin's forms, filled with the button's values: asked only once confirmed
      let values = {};
      try { values = JSON.parse(fo.dataset.values || '{}') || {}; } catch (err) { values = {}; }
      openForm(fo.dataset.machine, fo.dataset.form, values, fo);
      return;
    }
    const a = e.target.closest('button.ask');
    if (a && !a.disabled) {  // busy while it is asked (an action may take seconds); the page is drawn again once answered
      a.disabled = true;
      a.setAttribute('aria-busy', 'true');
      ask(a.dataset.machine, a.dataset.hook, JSON.parse(a.dataset.args)).then((ok) => { if (!ok) { a.disabled = false; a.removeAttribute('aria-busy'); } });
    }
  });

  // a right click on a plugin's icon in the tray: hide it, or disable it (the platform's own icon keeps the
  // browser's menu); an AI assistant's too (0.10.2)
  rail.addEventListener('contextmenu', (e) => {
    const b = e.target.closest('button[data-select]');
    const m = b && st && b.dataset.select !== 'machine' ? pluginOf(b.dataset.select) : null;
    if (!m || !window.LiminalMenu) return;
    e.preventDefault();
    const r = b.getBoundingClientRect();
    const keyboard = e.clientX === 0 && e.clientY === 0;  // the menu key, or Shift+F10: beside the icon
    window.LiminalMenu.open({ x: keyboard ? r.left - 170 : e.clientX, y: keyboard ? r.top : e.clientY, title: m.title,
      items: [{ label: 'Hide', run: () => setHidden(m.name, true, false) }, { label: 'Disable', run: () => setEnabled(m.name, false, false) }], from: b });
  });

  // typing into a login terminal, through its hidden text box (as web terminals do): the keys a terminal sends for
  // Enter, the arrows, Tab, Backspace and Ctrl+letter at keydown; text from the box's input, so composed characters
  // (dead keys, other layouts) and a paste arrive whole (Ctrl+Shift+C copies, Ctrl+Shift+V pastes).
  // 0.17.0, a phone's or a tablet's keyboard too: the box keeps one unseen character (KEEP), so a Backspace always has
  // something to delete and reaches the shell (Gboard and others send it as a deletion, not as a key); the word such a
  // keyboard composes is shown at the cursor until it is done, then sent; a Ctrl held from the key row makes the next
  // character typed its control code
  const KEEP = String.fromCharCode(0x200b);  // a zero-width space: unseen, yet a character to delete
  const termBox = (t) => (t && t.closest ? t.closest('.term-input[data-machine]') : null);
  const typedIn = (box) => box.value.split(KEEP).join('');  // what a keyboard put in the box
  function keepBox(box) {  // back to its one character, the caret after it
    if (!box) return;
    if (box.value !== KEEP) box.value = KEEP;
    try { box.setSelectionRange(KEEP.length, KEEP.length); } catch (e) { /* not on the page yet */ }
  }
  function setCtrl(name, on) {  // the key row's Ctrl, held for the next key or let go
    const sh = shells[name];
    if (!sh) return;
    sh.ctrl = on;
    const b = sh.panel && sh.panel.querySelector('[data-term-key="Ctrl"]');
    if (b) b.setAttribute('aria-pressed', String(on));
  }
  function typeKey(name, keys) {  // a key that is not text; under a held Ctrl, an arrow is a word over (as xterm sends it)
    const sh = shells[name];
    if (sh && sh.ctrl) {
      setCtrl(name, false);
      const arrow = /^\x1b\[([ABCD])$/.exec(keys);
      if (arrow) keys = `\x1b[1;5${arrow[1]}`;
    }
    type(name, keys);
  }
  function typeText(name, text) {  // text a keyboard typed; under a held Ctrl, its first character as its control code
    const sh = shells[name];
    if (!sh || !text) return;
    if (sh.ctrl) {
      setCtrl(name, false);
      const code = LiminalTerminal.ctrl(text[0]);
      if (code) text = code + text.slice(1);
    }
    type(name, text.replace(/\r?\n/g, '\r'));
  }
  function composing(box, on) {  // the word a phone's keyboard composes, shown at the terminal's cursor until it is sent
    // (a hardware keyboard's own composing, an IME's or a dead key's, shows nothing new: as before)
    const p = box.closest('.term-panel'), w = p && p.querySelector('.term-composing'), pre = p && p.querySelector('pre.term');
    const text = on && fingered() ? typedIn(box) : '';
    if (!w || !pre) return;
    w.hidden = !text;
    if (!text) return;
    w.textContent = text;
    const c = pre.querySelector('.t-cursor'), panel = p.getBoundingClientRect(), view = pre.getBoundingClientRect();
    const at = c ? c.getBoundingClientRect() : { left: view.left + 10, top: view.bottom - 24 };
    w.style.left = `${Math.round(Math.max(view.left, Math.min(at.left, view.right - w.offsetWidth)) - panel.left)}px`;
    w.style.top = `${Math.round(Math.max(view.top, Math.min(at.top, view.bottom - w.offsetHeight)) - panel.top)}px`;
  }
  data.addEventListener('keydown', (e) => {
    const box = termBox(e.target);
    if (!box || e.isComposing) return;
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) return;  // a character: the input brings it
    if (e.ctrlKey && e.shiftKey && (e.key === 'C' || e.key === 'V' || e.key === 'c' || e.key === 'v')) return;  // copy, paste
    const keys = LiminalTerminal.keys(e);
    if (keys) { e.preventDefault(); typeKey(box.dataset.machine, keys); }
  });
  data.addEventListener('beforeinput', (e) => {  // a keyboard's Backspace as a deletion (0.17.0): sent, the box kept as it is
    const box = termBox(e.target);
    if (!box || e.isComposing || !e.cancelable || !/^delete.*Backward$/.test(e.inputType || '')) return;
    e.preventDefault();
    typeKey(box.dataset.machine, '\x7f');
  });
  data.addEventListener('input', (e) => {
    const box = termBox(e.target);
    if (!box) return;
    const name = box.dataset.machine, sh = shells[name];
    // a word being composed: shown, sent once done; under a held Ctrl, sent at once, its first character the control code
    // (the key row's Ctrl sent the word composed before it, so this one began after it)
    if (e.isComposing) {
      const text = typedIn(box);
      if (sh && sh.ctrl && text) { keepBox(box); composing(box, false); typeText(name, text); return; }
      composing(box, true);
      return;
    }
    const text = typedIn(box), gone = !text && !box.value.includes(KEEP);  // the kept character deleted: a Backspace
    keepBox(box);
    if (text) typeText(name, text);
    else if (gone) typeKey(name, '\x7f');
  });
  data.addEventListener('compositionend', (e) => {
    const box = termBox(e.target);
    if (!box) return;
    composing(box, false);
    const text = typedIn(box);
    keepBox(box);
    if (text) typeText(box.dataset.machine, text);
  });
  data.addEventListener('focusin', (e) => keepBox(termBox(e.target)));
  data.addEventListener('focusout', (e) => { const box = termBox(e.target); if (box) composing(box, false); });
  data.addEventListener('mouseup', (e) => {  // a click in the terminal types into it (a selection made is left to copy)
    if (fingered()) return;  // a finger's tap: tapTerminal, at its click (0.17.0)
    const t = e.target.closest && e.target.closest('.term.interactive[data-machine]');
    if (!t || String(window.getSelection() || '')) return;
    const box = $(`shell-in-${t.dataset.machine}`);
    if (box) box.focus({ preventScroll: true });
  });
  // the window's height with no on-screen keyboard up (0.17.0): as it is while no field is typed in, the tallest since one
  // is (at the same width). Chrome on Android makes the page itself shorter above its keyboard (resizes-content), which
  // LiminalTouch.keyboardOpen does not count
  let roomy = { w: innerWidth, h: innerHeight };
  window.addEventListener('resize', () => {
    if (innerWidth !== roomy.w || !(T && T.isTextField(document.activeElement))) roomy = { w: innerWidth, h: innerHeight };
    else if (innerHeight > roomy.h) roomy.h = innerHeight;
  });
  const keyboardUp = () => !!T && (T.keyboardOpen || innerHeight < roomy.h - 120);
  // a finger's tap on a terminal's lines (0.17.0): its keyboard comes up, even when it was put away with the box still
  // focused (Android's back gesture), and is left as it is when it is up (a word being composed goes on). A word a
  // finger pressed and held there to copy is let go by the next tap (its press keeps the focus in the box, so it
  // collapses nothing); a pen's drag selects to copy as a mouse's does, and is left to copy
  function tapTerminal(e) {
    if (!fingered()) return;
    const t = e.currentTarget, sh = shells[t.dataset.machine], s = window.getSelection();
    if (!sh || !sh.alive) return;
    if (s && !s.isCollapsed && t.contains(s.anchorNode)) {
      if (T.lastInput !== 'touch') return;
      s.removeAllRanges();
    }
    const box = $(`shell-in-${t.dataset.machine}`);
    if (box && !(document.activeElement === box && keyboardUp())) T.raiseKeyboard(box, { preventScroll: true });
  }
  // the key row under a terminal (0.17.0): a key sent as the terminal's. A press on it, or a finger's tap on the lines,
  // leaves the focus in the box (the tap's mouse press would take it to the page), so the keyboard stays up; a pen's
  // press on the lines is a mouse's (it selects to copy)
  data.addEventListener('mousedown', (e) => {
    const t = e.target.closest ? e.target : null;
    if (t && (t.closest('.term-keys button') || (T && T.lastInput === 'touch' && t.closest('.term.interactive[data-machine]')))) e.preventDefault();
  });
  // the word a phone's keyboard is still composing in the box, sent as typed before a key of the key row (0.17.0): Tab
  // completes it, an arrow or ^C comes after it, Ctrl applies to the next character typed and not to it
  function flushBox(name) {
    const sh = shells[name], box = sh && sh.panel && sh.panel.querySelector('textarea.term-input');
    const word = box ? typedIn(box) : '';
    if (!word) return;
    keepBox(box);
    composing(box, false);
    type(name, word.replace(/\r?\n/g, '\r'));
  }
  function termKey(b) {
    const name = b.dataset.machine, sh = shells[name], k = b.dataset.termKey;
    if (!sh || !sh.alive) return;
    flushBox(name);
    if (k === 'Ctrl') { setCtrl(name, !sh.ctrl); return; }
    if (k === 'Paste') { pasteInto(name); return; }
    typeKey(name, k === '^C' ? '\x03' : k === '^D' ? '\x04' : LiminalTerminal.seq(k));
  }
  async function pasteInto(name) {  // what is copied, typed into the shell (this page is on localhost: the browser may let it read it)
    setCtrl(name, false);
    let text = '';
    try { text = await navigator.clipboard.readText(); }
    catch (e) { termSaid(name, 'Paste: the browser did not let this page read what is copied.'); return; }
    if (text) type(name, text.replace(/\r?\n/g, '\r'));
  }
  function termSaid(name, words) {  // a word beside the key row, for a while
    const sh = shells[name], el = sh && sh.panel && sh.panel.querySelector('.term-said');
    if (!el) return;
    el.textContent = words;
    clearTimeout(sh.saidTimer);
    sh.saidTimer = setTimeout(() => { el.textContent = ''; }, 6000);
  }

  // the radio group's arrow keys move the choice, as a radio group's do
  data.addEventListener('keydown', (e) => {
    const c = e.target.closest && e.target.closest('button.choice[data-hook]');
    if (!c || !['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp'].includes(e.key)) return;
    const all = [...c.parentElement.querySelectorAll('button.choice')];
    const next = all[(all.indexOf(c) + (e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : -1) + all.length) % all.length];
    e.preventDefault();
    next.focus();
    choose(next.dataset.machine, next.dataset.hook, next.dataset.value);
  });

  // Connections: a box picked with Enter or Space too
  data.addEventListener('keydown', (e) => {
    const nd = e.target.closest && e.target.closest('#conn-svg [data-node]');
    if (!nd || (e.key !== 'Enter' && e.key !== ' ')) return;
    e.preventDefault();
    pickNode(nd.dataset.node);
  });

  window.addEventListener('hashchange', draw);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { clearTimeout(live); clearTimeout(trafficTimer); return; }
    const m = shown();
    if (m) refresh(m.name);
    if (selected() === CONNECTIONS) loadTraffic();
  });

  render();
})();
