// The platform's page (the user, 2026-11-07: "the specifics are on the right hand side before the icons on the very
// right, and the larger window from the left to right is used to describe or display data"; "plugins are better
// described as a list of details w/ the specifics in the right hand column, just like the charts had a right hand
// column"; "active plugins, will be part of the tray on the very right side"; "use the black boundary (around the
// icon) to serve as the tray border, it can stretch vertically to include more icons or plugins"):
//   the list (this machine, its machine plugins, the AI assistants) | the selected one's data | its specifics | the tray
// The tray is the platform's chip, a divider, then an icon per active plugin, all in the one dark box. The
// selection is the address's #name (#wsl-ubuntu), so a reload or a link keeps it. API paths are relative, so the
// page works under a super app's prefix too.
(() => {
  'use strict';

  const WRITE = { 'Content-Type': 'application/json', 'X-Liminal-Charts': '1' };
  const $ = (id) => document.getElementById(id);
  const esc = window.LiminalIcons.esc;
  const icon = window.LiminalIcons.icon;
  const list = $('list'), data = $('data'), side = $('side'), rail = $('rail');
  if (new URLSearchParams(location.search).get('embedded') === '1') document.body.classList.add('embedded');
  const polls = {};
  let st = null;  // the last GET api/status
  let tray = null;  // the last GET api/tray
  const selected = () => decodeURIComponent(location.hash.slice(1)) || 'machine';
  const label = (k) => k.replace(/([A-Z])/g, ' $1').toLowerCase();

  async function api(method, path, body) {
    const r = await fetch(path, { method, headers: method === 'GET' ? {} : WRITE, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin' });
    let out = null;
    try { out = await r.json(); } catch (e) { out = null; }
    if (!r.ok) throw new Error((out && out.error) || `the platform answered ${r.status}`);
    return out;
  }

  const chipOf = (m) => (m.status && m.status.present ? '<span class="chip up">active</span>' : '<span class="chip">not present</span>');
  const stateLine = (m) => (m.status && m.status.summary) || (m.status && m.status.present ? 'present' : 'not present');

  // -- the tray: the chip, a divider, an icon per active plugin, in the one dark box ------------------------
  function drawRail() {
    const sel = selected();
    const items = ((tray && tray.items) || []).filter((i) => i.kind === 'plugin');
    rail.innerHTML = `<button type="button" id="railChip" class="master${sel === 'machine' ? ' active' : ''}" data-select="machine" title="${esc((tray && tray.title) || 'Platform')}: this machine">${icon('chip', 30)}</button>`
      + (items.length ? '<hr>' + items.map((i) => `<button type="button" class="${sel === i.id ? 'active' : ''}" data-select="${esc(i.id)}" title="${esc(i.title)}">${icon(i.icon || 'chip', 24)}</button>`).join('') : '');
  }

  // -- the list: this machine, its machine plugins, the AI assistants -----------------------------------
  function drawList() {
    const sel = selected();
    const item = (id, ic, title, sub) => `<button type="button" class="item${sel === id ? ' active' : ''}" data-select="${esc(id)}">${icon(ic, 20)}
      <span class="what"><span>${esc(title)}</span><span class="sub">${esc(sub)}</span></span></button>`;
    const f = st.machine;
    const machines = Object.values(st.machines);
    list.innerHTML = `<h2>Platform</h2><div class="muted small">the software and hardware under the framework</div>`
      + `<h4>This machine</h4>${item('machine', 'chip', f.host, `${f.system} ${f.release} · ${f.cpus} cpus`)}`
      + `<h4>Machine plugins</h4>` + (machines.length ? machines.map((m) => item(m.name, m.icon || 'chip', m.title, stateLine(m))).join('')
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

  function pluginData(m) {
    return `<h2>${esc(m.title)}</h2><div class="muted small">${esc(m.about)}</div>${tables(m)}
      <h4>Setup log</h4><pre class="setup-log" id="log-${esc(m.name)}">${m.setup ? esc(m.setup.lines.join('\n')) : 'Nothing run yet: the steps are on the right.'}</pre>`;
  }

  function assistantData(a) {
    return `<h2>${esc(a.title)}</h2><div class="muted small">${esc(a.about)}</div>
      <h4>Where it is set up</h4><div class="small">Its key, plan and model are set on the charts app's Plugins view; the platform hosts it.</div>`;
  }

  function drawData() {
    const sel = selected();
    const m = st.machines[sel], a = (st.assistants || []).find((x) => x.name === sel);
    data.innerHTML = sel === 'machine' ? machineData() : m ? pluginData(m) : a ? assistantData(a) : `<p class="muted">Nothing named ${esc(sel)} here.</p>`;
  }

  // -- the right: the selected one's specifics ----------------------------------------------------------
  function facts(s) {
    // a status's own facts: neither its lists nor its summary
    const skip = new Set(['rules', 'services', 'startups', 'processes', 'summary', 'present', 'problem']);
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
      <h4>Platform</h4><div class="small">${esc(st.app.title)} ${esc(st.app.api ? 'API ' + st.app.api : '')} at ${esc(st.app.url)}</div>`;
  }

  function pluginSide(m) {
    const running = m.setup && m.setup.running;
    const steps = m.steps || [];
    return `<h3>${icon(m.icon || 'chip', 20)} ${esc(m.title)} ${chipOf(m)}</h3><div class="muted small">${esc(m.name)}${m.version ? ` · ${esc(m.version)}` : ''}</div>
      <p class="summary">${esc(stateLine(m))}</p>${m.status.problem ? `<p class="error">${esc(m.status.problem)}</p>` : ''}
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
  }

  async function render() {
    try { [st, tray] = await Promise.all([api('GET', 'api/status'), api('GET', 'api/tray')]); }
    catch (e) { data.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
    draw();
    Object.values(st.machines).forEach((m) => { if (m.setup && m.setup.running) watch(m.name); });
  }

  async function ask(name, hook, args) {
    try { await api('POST', `api/machines/${encodeURIComponent(name)}/ask`, { hook, args }); render(); }
    catch (e) { const log = $(`log-${name}`); if (log) log.textContent = e.message; }
  }

  async function setup(name, steps) {
    try { await api('POST', `api/machines/${encodeURIComponent(name)}/setup`, steps ? { steps } : {}); await render(); watch(name); }
    catch (e) { const log = $(`log-${name}`); if (log) log.textContent = e.message; }
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
    const pick = e.target.closest('[data-select]');
    if (pick) { location.hash = pick.dataset.select === 'machine' ? '' : pick.dataset.select; return; }
    const go = e.target.closest('button.setup, button.step');
    if (go) { setup(go.dataset.machine, go.dataset.step ? [go.dataset.step] : null); return; }
    const a = e.target.closest('button.ask');
    if (a) ask(a.dataset.machine, a.dataset.hook, JSON.parse(a.dataset.args));
  });
  window.addEventListener('hashchange', draw);

  render();
})();
