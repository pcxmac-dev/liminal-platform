// The platform's page: the machine, the machine plugins (set up from here, their log as it comes), the Docker
// instances, the plugins attached. The API paths are relative, so the page works under a super app's prefix.
(() => {
  'use strict';

  const WRITE = { 'Content-Type': 'application/json', 'X-Liminal-Charts': '1' };
  const $ = (id) => document.getElementById(id);
  const esc = window.LiminalIcons.esc;
  const icon = window.LiminalIcons.icon;
  const main = $('main');
  if (new URLSearchParams(location.search).get('embedded') === '1') document.body.classList.add('embedded');
  $('railChip').innerHTML = icon('chip', 30);
  const polls = {};

  async function api(method, path, body) {
    const r = await fetch(path, { method, headers: method === 'GET' ? {} : WRITE, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin' });
    let data = null;
    try { data = await r.json(); } catch (e) { data = null; }
    if (!r.ok) throw new Error((data && data.error) || `the platform answered ${r.status}`);
    return data;
  }

  function machineCard(f, d) {
    return `<h1>${icon('chip', 24)} ${esc(f.host)}</h1>
      <dl class="facts">
        <dt>System</dt><dd>${esc(f.system)} ${esc(f.release)} on ${esc(f.machine)}</dd>
        <dt>Processor</dt><dd>${esc(f.cpus)} cpus${f.processor ? ` (${esc(f.processor)})` : ''}</dd>
        <dt>Memory</dt><dd>${esc(f.memoryMb)} MB</dd>
        <dt>Python</dt><dd>${esc(f.python)}</dd>
        <dt>Docker here</dt><dd>${d.available ? `engine ${esc(d.engine)} (${esc(d.command)})` : esc(d.problem || 'not installed') + (d.wsl ? ` · WSL 2 ${d.wsl.present ? 'present' : 'absent'}` : '')}</dd>
      </dl>`;
  }

  function tables(m) {
    // what a plugin's status lists: Liminal's rules (a firewall), services, startups, processes (the admin)
    const st = m.status || {}, can = new Set(m.asks || []), out = [];
    const btn = (hook, args, label) => can.has(hook) ? `<button type="button" class="ask" data-hook="${esc(hook)}" data-args='${esc(JSON.stringify(args))}'>${esc(label)}</button>` : '';
    if (Array.isArray(st.rules) && st.rules.length) {
      out.push(`<table class="list"><thead><tr><th>Rule</th><th>Ports</th><th>Direction</th><th>From</th><th></th></tr></thead><tbody>` + st.rules.map((r) =>
        `<tr><td>${esc(r.label)}</td><td class="mono">${esc((r.ports || []).join(', ') || 'every')}/${esc(r.protocol)}</td><td>${esc(r.direction)} ${esc(r.action)}</td><td>${esc(r.remote)}</td>`
        + `<td>${r.owned ? btn('remove', [r.name], 'Remove') : ''}</td></tr>`).join('') + `</tbody></table>`);
    }
    if (Array.isArray(st.services) && st.services.length) {
      out.push(`<table class="list"><thead><tr><th>Service</th><th>State</th><th>Start</th><th>For</th><th></th></tr></thead><tbody>` + st.services.map((s) =>
        `<tr><td class="mono">${esc(s.name)}</td><td>${esc(s.state)}</td><td>${esc(s.startup)}</td><td class="muted">${esc(s.usedFor)}</td><td>`
        + (s.state === 'absent' ? '' : s.state === 'running' ? btn('service', [s.name, 'restart'], 'Restart') + btn('service', [s.name, 'stop'], 'Stop') : btn('service', [s.name, 'start'], 'Start'))
        + `</td></tr>`).join('') + `</tbody></table>`);
    }
    if (Array.isArray(st.startups) && st.startups.length) {
      out.push(`<table class="list"><thead><tr><th>App</th><th>Startup</th><th>State</th><th></th></tr></thead><tbody>` + st.startups.map((s) =>
        `<tr><td>${esc(s.app)}</td><td class="mono">${esc(s.name)}</td><td>${esc(s.state)}</td><td>`
        + (s.state === 'absent' ? btn('register', [s.app], 'Start at logon') : btn('startup', [s.app, 'run'], 'Run') + btn('startup', [s.app, 'end'], 'End') + btn('unregister', [s.app], 'Remove'))
        + `</td></tr>`).join('') + `</tbody></table>`);
    }
    if (Array.isArray(st.processes) && st.processes.length) {
      out.push(`<table class="list"><thead><tr><th>Process</th><th>App</th><th>Memory</th></tr></thead><tbody>` + st.processes.map((p) =>
        `<tr><td class="mono">${esc(p.pid)}</td><td>${esc(p.app)}</td><td>${esc(p.memoryMb)} MB</td></tr>`).join('') + `</tbody></table>`);
    }
    return out.join('');
  }

  function engineText(st) {
    const e = st.engine || {};
    if (!st.present) return 'not present';
    return `present (${esc(st.state || '')}, WSL ${esc(st.version || '')}) · Docker inside: ${e.installed ? (e.running ? 'running' : 'installed, not running') + ' ' + esc(e.version) : 'none'}`;
  }

  function machines(list) {
    if (!list.length) return `<h2>Machine plugins</h2><p class="muted">None installed: plugin-platform-wsl-ubuntu, -fedora or -gentoo set up WSL with Docker inside.</p>`;
    return `<h2>Machine plugins</h2>` + list.map((m) => `<div class="card machine" data-name="${esc(m.name)}">
        <h3>${esc(m.title)} <span class="muted">${esc(m.version || '')}</span></h3>
        <p class="muted">${esc(m.about)}</p>
        <p class="engine">${m.status.summary ? esc(m.status.summary) : engineText(m.status)}${m.status.problem ? ` · <span class="error">${esc(m.status.problem)}</span>` : ''}</p>
        ${tables(m)}
        <div class="steps"><button type="button" class="setup accent" ${m.setup && m.setup.running ? 'disabled' : ''}>Set up everything</button>
          ${(m.steps || []).map((s) => `<button type="button" class="step" data-step="${esc(s)}" ${m.setup && m.setup.running ? 'disabled' : ''}>${esc(s)}</button>`).join('')}</div>
        <pre class="setup-log" id="log-${esc(m.name)}">${m.setup ? esc(m.setup.lines.join('\n')) : ''}</pre></div>`).join('');
  }

  function instances(list) {
    if (!list.length) return `<h2>Docker instances</h2><p class="muted">None yet: Docker here, a context, or a machine plugin with Docker inside.</p>`;
    return `<h2>Docker instances</h2><table class="list"><thead><tr><th>Name</th><th>Where</th><th>Command</th><th>From</th></tr></thead><tbody>`
      + list.map((i) => `<tr><td class="mono">${esc(i.name)}</td><td>${esc(i.where)}</td><td class="mono">${esc(i.command)}</td><td>${esc(i.source)}</td></tr>`).join('') + `</tbody></table>`;
  }

  function plugins(attached) {
    const names = Object.keys(attached);
    return `<h2>Plugins attached</h2><p class="muted">${names.length ? names.map(esc).join(', ') : 'none'}</p>`;
  }

  async function render() {
    let st;
    try { st = await api('GET', 'api/status'); }
    catch (e) { main.innerHTML = `<p class="error">${esc(e.message)}</p>`; return; }
    const list = Object.values(st.machines);
    main.innerHTML = machineCard(st.machine, st.docker) + machines(list) + instances(st.instances) + plugins(st.plugins);
    main.querySelectorAll('.machine').forEach((card) => {
      const name = card.dataset.name;
      card.querySelector('.setup').addEventListener('click', () => setup(name, null));
      card.querySelectorAll('.step').forEach((b) => b.addEventListener('click', () => setup(name, [b.dataset.step])));
      card.querySelectorAll('.ask').forEach((b) => b.addEventListener('click', () => ask(name, b.dataset.hook, JSON.parse(b.dataset.args))));
    });
    list.forEach((m) => { if (m.setup && m.setup.running) watch(m.name); });
  }

  async function ask(name, hook, args) {
    try { await api('POST', `api/machines/${encodeURIComponent(name)}/ask`, { hook, args }); render(); }
    catch (e) { $(`log-${name}`).textContent = e.message; }
  }

  async function setup(name, steps) {
    try { await api('POST', `api/machines/${encodeURIComponent(name)}/setup`, steps ? { steps } : {}); watch(name); }
    catch (e) { $(`log-${name}`).textContent = e.message; }
  }

  function watch(name) {
    if (polls[name]) return;
    polls[name] = setInterval(async () => {
      try {
        const s = await api('GET', `api/machines/${encodeURIComponent(name)}/setup`);
        $(`log-${name}`).textContent = s.lines.join('\n') + (s.error ? `\n${s.error}` : '') + (s.running ? '' : s.ok ? '\n— done' : '\n— ended with a failure');
        if (!s.running) { clearInterval(polls[name]); delete polls[name]; render(); }
      } catch (e) { clearInterval(polls[name]); delete polls[name]; }
    }, 2000);
  }

  render();
})();
