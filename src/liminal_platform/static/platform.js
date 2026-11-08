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
// status's `charts` (the library's charts.js, asked again at the plugin's interval while shown), `tables`, and
// `options` (choices it is asked to make: the Preferences plugin's themes, applied to this page at once). The
// selection is the address's #name (#wsl-ubuntu), so a reload or a link keeps it. API paths are relative, so the
// page works under a super app's prefix too.
(() => {
  'use strict';

  const WRITE = { 'Content-Type': 'application/json', 'X-Liminal-Charts': '1' };
  const $ = (id) => document.getElementById(id);
  const esc = window.LiminalIcons.esc;
  const icon = window.LiminalIcons.icon;
  const Charts = window.LiminalCharts;
  const list = $('list'), data = $('data'), side = $('side'), rail = $('rail');
  if (new URLSearchParams(location.search).get('embedded') === '1') document.body.classList.add('embedded');
  const polls = {};
  let st = null;  // the last GET api/status
  let tray = null;  // the last GET api/tray
  let span = 'recent';  // the charts' range: the last ten minutes, or the last day
  const day = {};  // a plugin's charts of the last day, by name (asked apart: they move every 30 s)
  let live = null;  // the timer asking the shown plugin again
  let gen = 0;  // bumped by every change of what the page holds: an answer asked before it is dropped
  const selected = () => decodeURIComponent(location.hash.slice(1)) || 'machine';
  const label = (k) => k.replace(/([A-Z])/g, ' $1').toLowerCase();

  async function api(method, path, body) {
    let r;
    try { r = await fetch(path, { method, headers: method === 'GET' ? {} : WRITE, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin' }); }
    catch (e) { throw new Error(`The platform is not answering at ${location.host}: it may have stopped. Start it again, then reload this page.`); }
    let out = null;
    try { out = await r.json(); } catch (e) { out = null; }
    if (!r.ok) throw new Error((out && out.error) || `the platform answered ${r.status}`);
    return out;
  }

  const off = (m) => m.enabled === false;
  const chipOf = (m) => (off(m) ? '<span class="chip">disabled</span>' : m.status && m.status.present ? '<span class="chip up">active</span>' : '<span class="chip">not present</span>');
  const stateLine = (m) => (off(m) ? 'disabled' : (m.status && m.status.summary) || (m.status && m.status.present ? 'present' : 'not present'));
  function say(name, text) {  // a plugin's trouble, at the head of its page
    const el = $(`err-${name}`);
    if (el) el.textContent = text || '';
  }

  // -- the tray: the chip, a divider, an icon per active plugin, in the one dark box ------------------------
  function drawRail() {
    const sel = selected();
    const items = ((tray && tray.items) || []).filter((i) => i.kind === 'plugin');
    rail.innerHTML = `<button type="button" id="railChip" class="master${sel === 'machine' ? ' active' : ''}" data-select="machine" title="${esc((tray && tray.title) || 'Platform')}: this machine">${icon('chip', 30)}</button>`
      + (items.length ? '<hr>' + items.map((i) => `<button type="button" class="${sel === i.id ? 'active' : ''}" data-select="${esc(i.id)}" title="${esc(i.title)} (right click: disable)">${icon(i.icon || 'chip', 24)}</button>`).join('') : '');
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
      + `<h4>Machine plugins</h4>` + (machines.length ? machines.map((m) => item(m.name, m.icon || 'chip', m.title, stateLine(m), off(m) ? ' off' : '')).join('')
        : '<div class="muted small">None installed: WSL, firewall and admin plugins set this machine up.</div>')
      + ((st.assistants || []).length ? `<h4>AI assistants</h4>` + st.assistants.map((a) => item(a.name, 'analysis', a.title, a.vendor || a.about)).join('') : '');
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

  // a plugin's own tables (status.tables: a title, the columns, the rows; a cell its text or {text, sub})
  const cellHtml = (c) => (c && typeof c === 'object' ? `${esc(c.text)}${c.sub ? `<div class="sub">${esc(c.sub)}</div>` : ''}` : esc(c));
  function statTables(items) {
    return (items || []).map((t) => `<h4>${esc(t.title)}</h4>${t.note ? `<div class="muted small mono note">${esc(t.note)}</div>` : ''}`
      + ((t.rows || []).length ? `<table class="list stats"><thead><tr>${t.columns.map((c) => `<th${c.num ? ' class="num"' : ''}>${esc(c.title)}</th>`).join('')}</tr></thead><tbody>`
        + t.rows.map((r) => `<tr>${r.map((c, i) => `<td${t.columns[i] && t.columns[i].num ? ' class="num"' : ''}>${cellHtml(c)}</td>`).join('')}</tr>`).join('') + '</tbody></table>'
        : `<div class="muted small">${esc(t.empty || 'None.')}</div>`)).join('');
  }

  // a plugin's choices (status.options: a hook asked with the value chosen; the Preferences plugin's themes)
  function optionsHtml(m) {
    const can = new Set(m.asks || []);
    return ((m.status && m.status.options) || []).filter((o) => can.has(o.hook)).map((o) => `<h4>${esc(o.title)}</h4>`
      + `<div class="choices" role="radiogroup" aria-label="${esc(o.title)}">${o.choices.map((c) => `<button type="button" class="choice${c.value === o.value ? ' active' : ''}" role="radio"
          aria-checked="${c.value === o.value}" aria-label="${esc(c.title)}${c.note ? `, ${esc(c.note)}` : ''}" tabindex="${c.value === o.value ? 0 : -1}" data-machine="${esc(m.name)}" data-hook="${esc(o.hook)}" data-value="${esc(c.value)}">`
        + `<span class="swatch" aria-hidden="true">${(c.swatch || []).map((s) => `<span style="background:${/^#[0-9a-fA-F]{3,8}$/.test(s) ? s : 'transparent'}"></span>`).join('')}</span>`
        + `<span class="what"><span>${esc(c.title)}</span>${c.note ? `<span class="sub">${esc(c.note)}</span>` : ''}</span></button>`).join('')}</div>`).join('');
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
    const on = !off(m);
    return `<label class="switch-row"><button type="button" class="switch" role="switch" aria-checked="${on}" aria-label="${esc(m.title)}" data-toggle="${esc(m.name)}"></button>${on ? 'Enabled' : 'Disabled'}</label>`;
  }

  function pluginData(m) {
    const head = `<div class="data-head"><h2>${esc(m.title)}</h2>${switchRow(m)}</div><div class="muted small">${esc(m.about)}</div><p class="error" id="err-${esc(m.name)}"></p>`;
    if (off(m)) return `${head}<p class="muted">Disabled: the platform asks it nothing, it runs nothing here, and its icon is out of the tray. The switch enables it again.</p>`;
    const logged = (m.steps || []).length || m.setup;
    return head + optionsHtml(m) + chartsBlock(m) + `<div id="tables-${esc(m.name)}">${tables(m)}${statTables(m.status && m.status.tables)}</div>`
      + (logged ? `<h4>Setup log</h4><pre class="setup-log" id="log-${esc(m.name)}">${m.setup ? esc(m.setup.lines.join('\n')) : 'Nothing run yet: the steps are on the right.'}</pre>` : '');
  }

  function assistantData(a) {
    return `<h2>${esc(a.title)}</h2><div class="muted small">${esc(a.about)}</div>
      <h4>Where it is set up</h4><div class="small">Its key, plan and model are set on the charts app's Plugins view; the platform hosts it.</div>`;
  }

  function drawData() {
    const sel = selected();
    const m = st.machines[sel], a = (st.assistants || []).find((x) => x.name === sel);
    const scrolled = data.scrollTop;
    data.innerHTML = sel === 'machine' ? machineData() : m ? pluginData(m) : a ? assistantData(a) : `<p class="muted">Nothing named ${esc(sel)} here.</p>`;
    Charts.draw(data);
    data.scrollTop = scrolled;
  }

  // -- the right: the selected one's specifics ----------------------------------------------------------
  function facts(s) {
    // a status's own facts: neither its lists, its charts, its choices nor its summary
    const skip = new Set(['rules', 'services', 'startups', 'processes', 'tables', 'charts', 'options', 'summary', 'present', 'problem']);
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
    if (off(m)) return `${head}<p class="summary">Disabled: enable it with the switch on its page.</p>`;
    const running = m.setup && m.setup.running;
    const steps = m.steps || [];
    return `${head}<p class="summary">${esc(stateLine(m))}</p>${m.status.problem ? `<p class="error">${esc(m.status.problem)}</p>` : ''}
      ${facts(m.status)}
      ${steps.length ? `<h4>Set up</h4><div class="steps"><button type="button" class="setup accent" data-machine="${esc(m.name)}" ${running ? 'disabled' : ''}>Everything</button>
        ${steps.map((s) => `<button type="button" class="step" data-machine="${esc(m.name)}" data-step="${esc(s)}" ${running ? 'disabled' : ''}>${esc(s)}</button>`).join('')}</div>
        <div class="muted small">${running ? 'Setting up: the log is in the middle.' : 'Each step reports what it did in the setup log.'}</div>` : ''}`;
  }

  function assistantSide(a) {
    return `<h3>${icon('analysis', 20)} ${esc(a.title)}</h3><div class="muted small">${esc(a.name)}${a.version ? ` · ${esc(a.version)}` : ''}</div>
      <dl class="facts"><dt>vendor</dt><dd>${esc(a.vendor || '')}</dd><dt>model</dt><dd>${esc(a.model || '')}</dd></dl>`;
  }

  function drawSide() {
    const sel = selected();
    const m = st.machines[sel], a = (st.assistants || []).find((x) => x.name === sel);
    side.innerHTML = sel === 'machine' ? machineSide() : m ? pluginSide(m) : a ? assistantSide(a) : '';
  }

  function draw() {
    if (!st) return;
    drawRail();
    drawList();
    drawData();
    drawSide();
    schedule();
  }

  async function render() {
    const g = ++gen;
    let fresh;
    try { fresh = await Promise.all([api('GET', 'api/status'), api('GET', 'api/tray')]); }
    catch (e) { if (g === gen) data.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
    if (g !== gen) return;  // something changed meanwhile: a newer answer is on its way
    [st, tray] = fresh;
    draw();
    Object.values(st.machines).forEach((m) => { if (m.setup && m.setup.running) watch(m.name); });
  }

  // -- the shown plugin's figures, asked again at its interval (the day's every 30 s), drawn in place ------------
  function shown() {
    const m = st && st.machines[selected()];
    return m && !off(m) && m.status && m.status.charts ? m : null;
  }
  function schedule() {
    clearTimeout(live);
    const m = shown();
    if (!m || document.hidden) return;
    const every = span === 'day' ? 30 : Math.max(1, Number(m.status.charts.interval) || 2);
    live = setTimeout(() => refresh(m.name), every * 1000);
  }
  async function refresh(name) {
    clearTimeout(live);
    if (selected() !== name) return;
    const g = gen;
    try {
      const [m, d] = await Promise.all([api('GET', `api/machines/${encodeURIComponent(name)}`),
        span === 'day' ? api('POST', `api/machines/${encodeURIComponent(name)}/ask`, { hook: 'charts', args: ['day'] }) : null]);
      if (g === gen) {  // nothing changed meanwhile (a plugin disabled or enabled, the page asked again)
        if (d) day[name] = d.answer;
        st.machines[name] = m;
        if (selected() === name) redrawShown(m);
      }
    } catch (e) { if (g === gen) say(name, e.message); }
    schedule();
  }
  function redrawShown(m) {
    const box = $(`charts-${m.name}`);
    if (off(m) || !box || !Charts.update(box, chartsOf(m), { id: m.name })) { drawData(); }  // other charts: drawn anew
    else {
      box.classList.remove('loading');
      const t = $(`tables-${m.name}`);
      if (t) t.innerHTML = tables(m) + statTables(m.status.tables);
    }
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
    catch (e) { const log = $(`log-${name}`); if (log) log.textContent = e.message; else say(name, e.message); return false; }
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
    const m = st.machines[name];
    st.machines[name] = answer || { ...m, enabled: on, asks: on ? m.asks : [],
      status: on ? { ...(m.status || {}), present: true, summary: 'enabling…' } : { present: null, summary: 'disabled: the platform asks it nothing' } };
    const order = Object.keys(st.machines);
    const present = on && !!(st.machines[name].status && st.machines[name].status.present);
    st.disabled = order.filter((n) => (n === name ? !on : (st.disabled || []).includes(n)));
    st.active = order.filter((n) => (n === name ? present : (st.active || []).includes(n)));
    if (tray) {
      const own = tray.items.filter((i) => i.kind !== 'plugin');
      const plugins = tray.items.filter((i) => i.kind === 'plugin' && i.id !== name);
      if (present) plugins.push({ id: name, icon: st.machines[name].icon || 'chip', title: st.machines[name].title, kind: 'plugin', app: tray.app });
      plugins.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
      tray = { ...tray, items: [...own, ...plugins] };
    }
  }

  function focusSwitch(name) {
    const again = data.querySelector(`button.switch[data-toggle="${CSS.escape(name)}"]`);
    if (again) again.focus({ preventScroll: true });
  }

  async function setEnabled(name, on, refocus) {
    // every view shows it at once (the tray, this machine's table, the list, the plugin's page and switch), then
    // the platform's answer for the plugin; the rest (the Docker instances a machine runs) once the platform has
    // asked every plugin again, which takes a few seconds with the WSL plugins
    if (!st || !st.machines[name]) return;
    const before = { machine: st.machines[name], active: st.active, disabled: st.disabled, tray };
    gen++;
    mark(name, on);
    delete day[name];
    draw();
    if (refocus) focusSwitch(name);
    let answer;
    try { answer = await api('POST', `api/machines/${encodeURIComponent(name)}/enabled`, { on }); }
    catch (e) {  // put back as it was
      gen++;
      st.machines[name] = before.machine;
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

  async function setup(name, steps) {
    try { await api('POST', `api/machines/${encodeURIComponent(name)}/setup`, steps ? { steps } : {}); await render(); watch(name); }
    catch (e) { const log = $(`log-${name}`); if (log) log.textContent = e.message; else say(name, e.message); }
  }

  function watch(name) {
    if (polls[name]) return;
    polls[name] = setInterval(async () => {
      try {
        const s = await api('GET', `api/machines/${encodeURIComponent(name)}/setup`);
        const log = $(`log-${name}`);
        if (log) log.textContent = s.lines.join('\n') + (s.error ? `\n${s.error}` : '') + (s.running ? '' : s.ok ? '\n— done' : '\n— ended with a failure');
        if (!s.running) { clearInterval(polls[name]); delete polls[name]; render(); }
      } catch (e) { clearInterval(polls[name]); delete polls[name]; }
    }, 2000);
  }

  document.addEventListener('click', (e) => {
    const sw = e.target.closest('button.switch[data-toggle]');
    if (sw) { setEnabled(sw.dataset.toggle, sw.getAttribute('aria-checked') !== 'true', document.activeElement === sw || e.detail === 0); return; }
    const pick = e.target.closest('[data-select]');
    if (pick) { location.hash = pick.dataset.select === 'machine' ? '' : pick.dataset.select; return; }
    const sp = e.target.closest('button[data-span]');
    if (sp) { setSpan(sp.dataset.span); return; }
    const c = e.target.closest('button.choice[data-hook]');
    if (c) { if (c.getAttribute('aria-checked') !== 'true') choose(c.dataset.machine, c.dataset.hook, c.dataset.value); return; }
    const go = e.target.closest('button.setup, button.step');
    if (go) { setup(go.dataset.machine, go.dataset.step ? [go.dataset.step] : null); return; }
    const a = e.target.closest('button.ask');
    if (a) ask(a.dataset.machine, a.dataset.hook, JSON.parse(a.dataset.args));
  });

  // a right click on a plugin's icon in the tray: disable it (the platform's own icon keeps the browser's menu)
  rail.addEventListener('contextmenu', (e) => {
    const b = e.target.closest('button[data-select]');
    const m = b && st && st.machines[b.dataset.select];
    if (!m || b.dataset.select === 'machine' || !window.LiminalMenu) return;
    e.preventDefault();
    const r = b.getBoundingClientRect();
    const keyboard = e.clientX === 0 && e.clientY === 0;  // the menu key, or Shift+F10: beside the icon
    window.LiminalMenu.open({ x: keyboard ? r.left - 170 : e.clientX, y: keyboard ? r.top : e.clientY, title: m.title,
      items: [{ label: 'Disable', run: () => setEnabled(m.name, false, false) }], from: b });
  });

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

  window.addEventListener('hashchange', draw);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { clearTimeout(live); return; }
    const m = shown();
    if (m) refresh(m.name);
  });

  render();
})();
