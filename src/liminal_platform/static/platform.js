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
        <p class="engine">${engineText(m.status)}${m.status.problem ? ` · <span class="error">${esc(m.status.problem)}</span>` : ''}</p>
        <div class="steps"><button type="button" class="setup accent" ${m.setup && m.setup.running ? 'disabled' : ''}>Set up everything</button>
          ${['distribution', 'docker', 'engine', 'user'].map((s) => `<button type="button" class="step" data-step="${s}" ${m.setup && m.setup.running ? 'disabled' : ''}>${s}</button>`).join('')}</div>
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
    });
    list.forEach((m) => { if (m.setup && m.setup.running) watch(m.name); });
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
