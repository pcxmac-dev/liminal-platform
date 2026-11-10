// A terminal in a page (the platform's panel: an install's progress, a login shell; the user, 2026-11-07: "after the install
// is run a terminal pops up in the plugin and shows the install progress"; "the plugin also allows for a user to login
// through a terminal in to the environment"): the text a shell prints, with its escape sequences (colours, the cursor moved
// and lines erased: readline's editing, a progress line rewritten after \r), drawn as lines; keys turned into what a
// terminal sends. Not a full emulator: full-screen programs (vim, top) are not drawn as they should be.
//
//   const t = LiminalTerminal.create(el, {cursor: true}); t.write(text); t.attach(other)   // drawn again elsewhere
//   LiminalTerminal.keys(keydownEvent) -> '\r', '\x1b[A', 'a', '\x03' ... ('' for none)
//   LiminalTerminal.seq('Escape') -> '\x1b'; LiminalTerminal.ctrl('c') -> '\x03'   // a key row's keys (0.17.0), as keys() sends them
// {followCursor: true, or a function saying so now}: the cursor kept in view sideways too while the end is followed (a
// phone's terminal is narrower than its 120 columns; 0.17.0)
// The end followed (0.17.0): while the lines are scrolled to their end they stay there, as lines come and as the box
// changes size (an on-screen keyboard coming up makes it shorter); a scroll up lets the end go, a scroll back to it
// takes it again.
(() => {
  'use strict';

  const esc = (s) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]);
  const MAX_LINES = 3000;
  const SCREEN = 32;  // the rows a cursor position counts from (the terminal is 120 x 32: LOGIN in liminal-libs' wsl.py)

  function create(el, { cursor = false, followCursor = false } = {}) {
    let lines = [[]], row = 0, col = 0, fg = 0, bold = false, pend = '', box = null;
    let stuck = true, top = 0;  // the end followed; where the box was scrolled to when last looked at
    const sideways = () => !!(typeof followCursor === 'function' ? followCursor() : followCursor);
    function note() {  // where the user left the lines: at the end (followed), scrolled up (let go), or as they were
      if (!box) return;
      if (box.scrollTop + box.clientHeight >= box.scrollHeight - 24) stuck = true;
      else if (box.scrollTop < top - 1) stuck = false;  // a box made shorter keeps its place: still followed
      top = box.scrollTop;
    }
    function toEnd() {  // the end in view, and the cursor's column too when asked (a long command typed on a phone stays seen)
      box.scrollTop = box.scrollHeight;
      top = box.scrollTop;
      if (!cursor || !sideways()) return;
      const c = box.querySelector('.t-cursor');
      if (!c) return;
      const b = box.getBoundingClientRect(), r = c.getBoundingClientRect(), x = r.left - b.left + box.scrollLeft, room = 24;
      if (x < box.scrollLeft + room) box.scrollLeft = Math.max(0, x - room);
      else if (x + r.width > box.scrollLeft + box.clientWidth - room) box.scrollLeft = x + r.width - box.clientWidth + room;
    }
    // a box that changes size (an on-screen keyboard's room, a window turned): its end kept in view while followed
    const sized = typeof ResizeObserver === 'function' ? new ResizeObserver(() => { note(); if (box && stuck) toEnd(); }) : null;
    function bind(next) {  // the box drawn into: its scrolls and its size followed, the last one's no longer
      if ((next || null) === box) return;
      if (box) { box.removeEventListener('scroll', note); if (sized) sized.unobserve(box); }
      box = next || null;
      top = 0;
      if (box) { box.addEventListener('scroll', note, { passive: true }); if (sized) sized.observe(box); }
    }
    const style = () => [fg ? `t-${fg}` : '', bold ? 't-b' : ''].filter(Boolean).join(' ');
    const line = () => lines[row] || (lines[row] = []);
    function down() {
      row++;
      while (lines.length <= row) lines.push([]);
      if (lines.length > MAX_LINES) { const cut = lines.length - MAX_LINES; lines.splice(0, cut); row -= cut; }
    }
    function put(ch) {
      const l = line();
      while (l.length < col) l.push([' ', '']);
      l[col] = [ch, style()];
      col++;
    }
    function sgr(params) {
      const codes = (params || '0').split(';').map((x) => parseInt(x || '0', 10));
      for (let i = 0; i < codes.length; i++) {
        const c = codes[i];
        if (c === 0) { fg = 0; bold = false; }
        else if (c === 1) bold = true;
        else if (c === 22) bold = false;
        else if (c >= 30 && c <= 37) fg = c - 29;
        else if (c >= 90 && c <= 97) fg = c - 81;
        else if (c === 39) fg = 0;
        else if (c === 38 || c === 48) i += codes[i + 1] === 5 ? 2 : codes[i + 1] === 2 ? 4 : 1;  // 256 and true colours: not drawn
      }
    }
    function csi(params, final) {
      const n = Math.max(1, parseInt(params || '1', 10) || 1);
      const m = parseInt(params || '0', 10) || 0;
      if (final === 'A') row = Math.max(0, row - n);
      else if (final === 'B') { for (let i = 0; i < n; i++) down(); }
      else if (final === 'C') col += n;
      else if (final === 'D') col = Math.max(0, col - n);
      else if (final === 'G') col = n - 1;
      else if (final === 'H' || final === 'f') {
        const [r, c] = (params || '').split(';').map((x) => parseInt(x || '1', 10) || 1);
        row = Math.max(0, lines.length - SCREEN) + (r || 1) - 1;
        while (lines.length <= row) lines.push([]);
        col = (c || 1) - 1;
      } else if (final === 'K') {
        const l = line();
        if (m === 0) l.length = Math.min(l.length, col);
        else if (m === 1) for (let i = 0; i <= col && i < l.length; i++) l[i] = [' ', ''];
        else lines[row] = [];
      } else if (final === 'J') {
        if (m === 2 || m === 3) { lines = [[]]; row = 0; col = 0; }
        else if (m === 0) { line().length = Math.min(line().length, col); lines.length = row + 1; }
      } else if (final === 'P') line().splice(col, n);
      else if (final === '@') line().splice(col, 0, ...Array.from({ length: n }, () => [' ', '']));
      else if (final === 'X') { const l = line(); for (let i = col; i < col + n && i < l.length; i++) l[i] = [' ', '']; }
      else if (final === 'm') sgr(params);
    }
    function feed(text) {
      const s = pend + text;
      pend = '';
      for (let i = 0; i < s.length; i++) {
        const c = s[i];
        if (c === '\x1b') {
          const rest = s.slice(i, i + 256);
          let mt = /^\x1b\[([0-9;?>=]*)([@-~])/.exec(rest);
          if (mt) { if (!/^[?>=]/.test(mt[1])) csi(mt[1], mt[2]); i += mt[0].length - 1; continue; }  // private modes: not drawn
          mt = /^\x1b\][^\x07\x1b]*(\x07|\x1b\\)/.exec(rest);  // a window title
          if (mt) { i += mt[0].length - 1; continue; }
          if (/^\x1b(\[[0-9;?>=]*|\][^\x07\x1b]*|[()])?$/.test(rest)) { pend = s.slice(i); break; }  // cut in two: the next part ends it
          mt = /^\x1b[()][0-9A-Za-z]/.exec(rest);
          i += mt ? mt[0].length - 1 : 1;  // a character set, or ESC and one character (=, >, 7, 8): not drawn
          continue;
        }
        if (c === '\r') col = 0;
        else if (c === '\n') { down(); col = 0; }
        else if (c === '\b') col = Math.max(0, col - 1);
        else if (c === '\t') col = (Math.floor(col / 8) + 1) * 8;
        else if (c >= ' ') put(c);
      }
    }
    function draw() {
      if (!box) return;
      note();  // a scroll up since the last look: let go at once, before its scroll event comes
      box.innerHTML = lines.map((l, r) => {
        let out = '', cur = null, buf = '';
        const cells = cursor && r === row ? [...l, ...Array.from({ length: Math.max(0, col + 1 - l.length) }, () => [' ', ''])] : l;
        cells.forEach(([ch, k], c) => {
          const kind = cursor && r === row && c === col ? `${k} t-cursor` : k;
          if (kind !== cur) { if (buf) out += cur ? `<span class="${cur}">${esc(buf)}</span>` : esc(buf); buf = ''; cur = kind; }
          buf += ch;
        });
        if (buf) out += cur ? `<span class="${cur}">${esc(buf)}</span>` : esc(buf);
        return out;
      }).join('\n');
      if (stuck) toEnd();
    }
    bind(el);
    return {
      write(text) { if (text) { feed(text); draw(); } },
      attach(next) { bind(next); stuck = true; draw(); },  // drawn again elsewhere, at its end
      clear() { lines = [[]]; row = 0; col = 0; draw(); },
      get text() { return lines.map((l) => l.map(([ch]) => ch).join('')).join('\n'); },
    };
  }

  const KEYS = { Enter: '\r', Backspace: '\x7f', Tab: '\t', Escape: '\x1b', ArrowUp: '\x1b[A', ArrowDown: '\x1b[B', ArrowRight: '\x1b[C',
    ArrowLeft: '\x1b[D', Home: '\x1b[H', End: '\x1b[F', Delete: '\x1b[3~', Insert: '\x1b[2~', PageUp: '\x1b[5~', PageDown: '\x1b[6~' };
  function ctrl(ch) {  // a character's control code (Ctrl+C: '\x03'), '' for one with none
    const k = String(ch || '').toUpperCase().charCodeAt(0);
    return k >= 64 && k <= 95 ? String.fromCharCode(k - 64) : '';
  }
  function keys(e) {
    if (e.ctrlKey && !e.altKey && !e.shiftKey && e.key.length === 1) return ctrl(e.key);  // Ctrl+C, Ctrl+D ... (Ctrl+Shift+C copies, as the browser does)
    if (KEYS[e.key]) return KEYS[e.key];
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) return e.altKey ? `\x1b${e.key}` : e.key;
    return '';
  }
  const seq = (name) => (Object.prototype.hasOwnProperty.call(KEYS, name) ? KEYS[name] : '');

  window.LiminalTerminal = { create, keys, seq, ctrl };
})();
