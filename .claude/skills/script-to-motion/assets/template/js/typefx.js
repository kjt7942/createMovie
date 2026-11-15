/*
 * typefx.js — expressive typography for script-to-motion projects.
 * Text that shatters, melts, ripples, jiggles, splits and re-forms, glows, turns solid — and whatever else you
 * compose from the same parts. The named effects below are examples built on a small open system, not a menu.
 *
 * Classic script (file:// safe). In index.html, after player.js (and fxkit.js), before scenes.js:
 *   <link rel="stylesheet" href="css/typefx.css">
 *   <script src="js/glyphs.js"></script>   (optional: glyph outlines made by scripts/text_to_paths.mjs)
 *   <script src="js/typefx.js"></script>
 * In Video.define:   const TX = TypeFX.install(ctx);
 *
 * The system (references/type-fx.md):
 *   1. representations — the same words as
 *        split units   TX.split(el)              real DOM text, per char / word / line
 *        copies        TX.copies(el, …)          exact overlays of an element, each clipped/tinted/moved (shards, bands, layers)
 *        glyph pieces  TX.glyphs(el, key)        SVG outlines from the font (strokes, jamo, points you can bend)
 *        raster tiles  await TX.raster(…) → TX.tiles(R, …)   canvas pixels (dust, particles, waves)
 *   2. units + channels — every unit has a rest place (x, y from the group centre, w, h, index, hashes) and, each
 *      frame, channels:  x y z  r rx ry  sx sy  kx ky  o  w (font weight delta)  vary{axis: value}  blur  color  css{}
 *   3. effects — TX.fx(group, { from, to, fill }, (u, s, c) => { c.y += … })  add into channels; deformers bend
 *      outlines (TX.deform), warps bend pixels (TX.warp). Every preset is one of these.
 * Everything is a pure function of the playhead t: no state carries between frames, randomness is hashed from
 * (group seed, unit, salt), physics is closed form. Seeking anywhere gives the same picture.
 */
(function () {
  'use strict';

  const TAU = Math.PI * 2;
  const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
  const lerp = (a, b, k) => a + (b - a) * k;
  const smooth = (k) => { k = clamp(k); return k * k * (3 - 2 * k); };
  const smoother = (k) => { k = clamp(k); return k * k * k * (k * (k * 6 - 15) + 10); };
  const f = (v, d = 2) => String(+v.toFixed(d));          // "-0.00" → "0"

  /** integer hash of up to three ints → [0, 1) */
  function hash(a, b = 0, c = 0) {
    let h = Math.imul(a | 0, 0x9e3779b1) ^ Math.imul((b | 0) + 0x632be5ab, 0x85ebca6b) ^ Math.imul((c | 0) + 0x5bd1e995, 0xc2b2ae35);
    h = Math.imul(h ^ (h >>> 16), 0x7feb352d);
    h = Math.imul(h ^ (h >>> 15), 0x846ca68b);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }
  /** smooth value noise in 1–3D → [-1, 1] */
  function noise(x, y = 0, z = 0) {
    const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
    const u = smoother(x - xi), v = smoother(y - yi), w = smoother(z - zi);
    const g = (i, j, k) => hash(xi + i, yi + j, zi + k) * 2 - 1;
    const x00 = lerp(g(0, 0, 0), g(1, 0, 0), u), x10 = lerp(g(0, 1, 0), g(1, 1, 0), u);
    const x01 = lerp(g(0, 0, 1), g(1, 0, 1), u), x11 = lerp(g(0, 1, 1), g(1, 1, 1), u);
    return lerp(lerp(x00, x10, v), lerp(x01, x11, v), w);
  }
  const fbm = (x, y = 0, z = 0, oct = 3) => { let s = 0, a = 0.5, q = 1; for (let i = 0; i < oct; i++) { s += a * noise(x * q, y * q, z * q + i * 17.3); a *= 0.5; q *= 2.03; } return s; };
  /** impulse response: 0 at t=0, swings ±1 and dies out (a hit, a jiggle) */
  const wobble = (t, freq = 3, decay = 5) => (t <= 0 ? 0 : Math.exp(-decay * t) * Math.sin(TAU * freq * t));
  /** step response: 0 → 1 with overshoot (a spring settling) */
  const spring = (t, freq = 1.6, decay = 6) => (t <= 0 ? 0 : 1 - Math.exp(-decay * t) * Math.cos(TAU * freq * t));
  /** displacement after t seconds at speed v with drag k (1/s) — exact integral, no stepping */
  const drift = (t, v, k = 0) => (t <= 0 ? 0 : k ? v * (1 - Math.exp(-k * t)) / k : v * t);
  /** height above the floor of something dropped from h with gravity g, bouncing with restitution e (≤ n bounces) */
  function bounce(t, h, g = 2400, e = 0.42, n = 4) {
    if (t <= 0) return h;
    let t0 = Math.sqrt(2 * h / g);
    if (t < t0) return h - 0.5 * g * t * t;
    let v = g * t0 * e, tt = t - t0;
    for (let i = 0; i < n; i++) {
      const d = 2 * v / g;
      if (tt < d) return v * tt - 0.5 * g * tt * tt;
      tt -= d; v *= e;
    }
    return 0;
  }
  const M = { TAU, clamp, lerp, smooth, smoother, hash, noise, fbm, wobble, spring, drift, bounce };

  function install(ctx, opts) {
    const { tl, onFrame, fitCanvas, stage, W, H } = ctx;
    const gs = ctx.gsap || window.gsap;
    const o0 = Object.assign({ perspective: 900 }, opts || {});
    const $ = (s) => (typeof s === 'string' ? stage.querySelector(s) || document.querySelector(s) : s);
    const ease = (e) => (typeof e === 'function' ? e : gs && gs.parseEase ? gs.parseEase(e || 'none') : (k) => k);
    const groups = [];
    let seedN = 101;
    // a time: seconds or a cue label ('c03', 'c03+=0.2', 'c03_end-=0.4') → seconds. Presets add offsets to their times
    // ('c03' + 0.9 would be the string 'c030.9'), and windows are compared with t, so labels are resolved first.
    function T(p) {
      if (typeof p === 'number' || p == null) return p;
      const m = String(p).match(/^([\w-]+?)(?:([+-])=([\d.]+))?$/);
      if (!m || !tl || !tl.labels || tl.labels[m[1]] == null) throw new Error(`TypeFX: can't resolve time "${p}" — use seconds or a cue label`);
      return tl.labels[m[1]] + (m[2] ? (m[2] === '-' ? -1 : 1) * Number(m[3]) : 0);
    }
    const reg = (window.__typefx = window.__typefx || { rasters: [], glyphs: [] });

    // ---------- small DOM helpers ----------
    const cs = (n) => (window.getComputedStyle ? getComputedStyle(n) : { position: 'static', display: 'block' });
    function positioned(n) { if (n && cs(n).position === 'static') n.style.position = 'relative'; }
    /** layout box of el relative to root (ignores transforms — safe while tweens are mid-flight at build time) */
    function relBox(el, root) {
      let x = 0, y = 0, n = el;
      while (n && n !== root && n !== document.body) { x += n.offsetLeft || 0; y += n.offsetTop || 0; n = n.offsetParent; }
      if (n !== root && el.getBoundingClientRect && root.getBoundingClientRect) {        // root not in the chain: measure
        const a = el.getBoundingClientRect(), b = root.getBoundingClientRect(), k = (root.offsetWidth || 1) / (b.width || 1);
        return { x: (a.left - b.left) * k, y: (a.top - b.top) * k, w: el.offsetWidth || a.width * k, h: el.offsetHeight || a.height * k };
      }
      return { x, y, w: el.offsetWidth || 0, h: el.offsetHeight || 0 };
    }
    /** stage coordinates (layout, no transforms) of a point inside an element: fx, fy are fractions of its box */
    function stageXY(target, fx = 0.5, fy = 0.5) {
      const el = $(target);
      const b = relBox(el, stage);
      return [b.x + fx * b.w, b.y + fy * b.h];
    }
    function parseRGB(s) {
      const m = String(s || '').match(/rgba?\(([^)]+)\)/);
      if (!m) return [255, 255, 255, 1];
      const p = m[1].split(/[,\s/]+/).filter(Boolean).map(Number);
      return [p[0], p[1], p[2], p[3] == null ? 1 : p[3]];
    }
    const rgba = (c, a = 1) => `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${f(clamp(a * (c[3] == null ? 1 : c[3])), 3)})`;
    const mix = (a, b, k) => [lerp(a[0], b[0], k), lerp(a[1], b[1], k), lerp(a[2], b[2], k), lerp(a[3] == null ? 1 : a[3], b[3] == null ? 1 : b[3], k)];
    // a light text-shadow on clipped text shows as faint boxes: move it to a drop-shadow on the root (player-api.md §4)
    function fixClippedGlow(node) {
      const ts = cs(node).textShadow;
      if (!ts || ts === 'none') return;
      const m = ts.match(/(rgba?\([^)]*\)|#[0-9a-f]{3,8})\s+(-?[\d.]+)px\s+(-?[\d.]+)px\s+([\d.]+)px/i);
      node.style.textShadow = 'none';
      if (!m) return;
      const prev = cs(node).filter;
      node.style.filter = `${prev && prev !== 'none' ? prev + ' ' : ''}drop-shadow(${m[2]}px ${m[3]}px ${(+m[4] * 0.4).toFixed(1)}px ${m[1]})`;
    }

    // ---------- groups, units, channels ----------
    function newChannels() { return { x: 0, y: 0, z: 0, r: 0, rx: 0, ry: 0, sx: 1, sy: 1, kx: 0, ky: 0, o: 1, w: 0, vary: null, blur: 0, color: null, css: null }; }
    function resetChannels(c) {
      c.x = c.y = c.z = c.r = c.rx = c.ry = c.kx = c.ky = c.w = c.blur = 0;
      c.sx = c.sy = c.o = 1; c.color = null; c.css = null; c.vary = null;
    }
    const C = newChannels(), C2 = newChannels();
    const isIdentity = (c) => Math.abs(c.x) < 0.05 && Math.abs(c.y) < 0.05 && Math.abs(c.z) < 0.05 && Math.abs(c.r) < 0.05 && Math.abs(c.rx) < 0.05 &&
      Math.abs(c.ry) < 0.05 && Math.abs(c.sx - 1) < 0.001 && Math.abs(c.sy - 1) < 0.001 && Math.abs(c.kx) < 0.05 && Math.abs(c.ky) < 0.05 && c.o > 0.999 && !c.color;

    /** finish a group: unit geometry (x, y from the group centre; nx, ny in −1…1), hashes, registration */
    function group(kind, root, units, extra) {
      const G = Object.assign({ kind, root, units, effects: [], deforms: [], warps: [], ghosts: null, state: null, seed: (seedN += 7919) },
        extra || {});
      if (G.w == null) {
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        for (const u of units) { x0 = Math.min(x0, u.bx); y0 = Math.min(y0, u.by); x1 = Math.max(x1, u.bx + u.w); y1 = Math.max(y1, u.by + u.h); }
        if (!units.length || !isFinite(x0)) { x0 = y0 = 0; x1 = (root && root.offsetWidth) || 0; y1 = (root && root.offsetHeight) || 0; }
        Object.assign(G, { bx: x0, by: y0, w: x1 - x0, h: y1 - y0 });
      }
      const cx = G.bx + G.w / 2, cy = G.by + G.h / 2;
      units.forEach((u, i) => {
        u.i = i; u.n = units.length; u.k = units.length > 1 ? i / (units.length - 1) : 0;
        u.x = u.bx + u.w / 2 - cx; u.y = u.by + u.h / 2 - cy;
        u.nx = G.w ? u.x / (G.w / 2) : 0; u.ny = G.h ? u.y / (G.h / 2) : 0;
        u.r = (salt = 0) => hash(G.seed + i * 31, salt, 977);
        u.last = {};
        // inline styles the representation set (a tint colour…) are the rest state the writers return to
        if (u.el && u.el.style) u.base = Object.assign({ w: 400 }, u.base, { color: u.el.style.color || '' });
      });
      G._ord = {};
      G._sig = null;
      G.gcLast = {};
      if (root && root.setAttribute) root.setAttribute('data-tx', kind);
      groups.push(G);
      return G;
    }

    /**
     * stagger orders: a number 0…1 per unit. mode: 'index' | 'reverse' | 'center' (middle first) | 'edges' |
     * 'random' | 'x' | 'y' | 'line' | 'word' | [x, y] (distance from a point, group coordinates) | function(u) → number
     */
    function order(G, mode = 'index') {
      const key = typeof mode === 'function' ? null : JSON.stringify(mode);
      if (key && G._ord[key]) return G._ord[key];
      const U = G.units;
      let v;
      if (typeof mode === 'function') v = U.map(mode);
      else if (Array.isArray(mode)) v = U.map((u) => Math.hypot(u.x - mode[0], u.y - mode[1]));
      else if (mode === 'reverse') v = U.map((u) => -u.i);
      else if (mode === 'center') v = U.map((u) => Math.abs(u.x) + Math.abs(u.y) * 0.5);
      else if (mode === 'edges') v = U.map((u) => -(Math.abs(u.x) + Math.abs(u.y) * 0.5));
      else if (mode === 'random') v = U.map((u) => u.r(91));
      else if (mode === 'x') v = U.map((u) => u.x);
      else if (mode === 'y') v = U.map((u) => u.y);
      else if (mode === 'line') v = U.map((u) => (u.line || 0) + u.k * 0.001);
      else if (mode === 'word') v = U.map((u) => (u.word || 0) + u.k * 0.001);
      else v = U.map((u) => u.i);
      let lo = Infinity, hi = -Infinity;
      for (const x of v) { lo = Math.min(lo, x); hi = Math.max(hi, x); }
      const out = v.map((x) => (hi > lo ? (x - lo) / (hi - lo) : 0));
      if (key) G._ord[key] = out;
      return out;
    }

    // ---------- effects ----------
    /**
     * Add an effect: fn(u, s, c) adds into the unit's channels c. s = { t, lt (seconds since from, clamped by fill),
     * dur, p (lt/dur), inside }. fill: 'none' (only inside [from, to]) | 'forwards' (hold the end) | 'backwards'
     * (hold the start before from) | 'both'. `group(s, gc)` (optional) sets group-level state:
     * gc.copies (show the copies), gc.hideOrig (hide the original under them), gc.filter (extra CSS filter on the root).
     * { static: true } = always on, evaluated once (re-evaluated when G.state changes).
     * Outside its window a filled effect is evaluated only when the side changes, so what it holds must depend on s.lt / s.p
     * (clamped), not on s.t. { live: true } = it reads s.t while held (a hum that never ends): rendered every frame it applies.
     */
    function fx(G, o, fn, groupFn) {
      const from = T(o.from), to = T(o.to);
      const e = { fn, group: groupFn || null, fill: o.fill || 'none', from: from == null ? 0 : from, to: to == null ? (from || 0) : to, s: {},
        live: !!o.live };
      if (o.static) { e.from = e.to = -1; e.fill = 'both'; }
      e.back = e.fill === 'both' || e.fill === 'backwards';
      e.fwd = e.fill === 'both' || e.fill === 'forwards';
      (o.list ? G[o.list] : G.effects).push(e);
      return e;
    }
    function local(e, t) {
      let lt;
      if (t < e.from) { if (!e.back) return null; lt = 0; } else if (t > e.to) { if (!e.fwd) return null; lt = e.to - e.from; } else lt = t - e.from;
      const s = e.s, dur = e.to - e.from;
      s.t = t; s.lt = lt; s.dur = dur; s.p = dur > 0 ? lt / dur : 1; s.inside = t >= e.from && t <= e.to;
      return s;
    }
    function evalUnit(G, u, t, c) {
      resetChannels(c);
      for (const e of G.effects) { const s = local(e, t); if (s) e.fn(u, s, c, G); }
      return c;
    }
    function groupState(G, t) {
      const gc = { copies: false, hideOrig: false, filter: '' };
      for (const e of G.effects) if (e.group) { const s = local(e, t); if (s) e.group(s, gc, G); }
      return gc;
    }
    /** does this frame need a render? (inside some window or a live effect applies, or the before/after pattern or state changed) */
    function needsRender(G, t) {
      const pad = G.ghosts ? G.ghosts.shutter : 0;
      let sig = '', inside = false;
      for (const list of [G.effects, G.deforms, G.warps]) {
        for (const e of list) {
          const side = t < e.from ? 0 : t > e.to + pad ? 2 : 1;
          if (side === 1 && e.from !== -1) inside = true;
          else if (e.live && (side === 1 || (side === 0 ? e.back : e.fwd))) inside = true;   // reads s.t while held
          sig += side;
        }
      }
      if (G.state) for (const k in G.state) sig += '|' + (+G.state[k]).toFixed(4);
      if (!inside && sig === G._sig) return false;
      G._sig = sig;
      return true;
    }

    // ---------- writers ----------
    function writeDom(G, el, c, last, base) {
      const has3 = Math.abs(c.z) > 0.01 || Math.abs(c.rx) > 0.01 || Math.abs(c.ry) > 0.01;
      let tr = '';
      if (has3) tr = `perspective(${G.perspective || o0.perspective}px) translate3d(${f(c.x)}px,${f(c.y)}px,${f(c.z)}px) rotateX(${f(c.rx, 1)}deg) rotateY(${f(c.ry, 1)}deg)`;
      else if (c.x || c.y) tr = `translate(${f(c.x)}px,${f(c.y)}px)`;
      if (c.r) tr += ` rotate(${f(c.r, 1)}deg)`;
      if (c.kx || c.ky) tr += ` skew(${f(c.kx, 1)}deg,${f(c.ky, 1)}deg)`;
      if (Math.abs(c.sx - 1) > 1e-4 || Math.abs(c.sy - 1) > 1e-4) tr += ` scale(${f(c.sx, 4)},${f(c.sy, 4)})`;
      tr = tr.trim();
      if (tr !== last.t) { el.style.transform = tr; last.t = tr; }
      const op = c.o >= 0.999 ? '' : f(clamp(c.o), 3);
      if (op !== last.o) { el.style.opacity = op; last.o = op; }
      const w = c.w ? String(Math.round(clamp((base && base.w || 400) + c.w, 1, 1000))) : '';
      if (w !== last.w) { el.style.fontWeight = w; last.w = w; }
      // variable-font axes (wdth, slnt, opsz, XROT, MORF …): absolute values, last writer per axis wins
      let fv = '';
      if (c.vary) for (const k in c.vary) fv += (fv ? ', ' : '') + `'${k}' ${f(c.vary[k], 1)}`;
      if (fv !== last.v) { el.style.fontVariationSettings = fv; last.v = fv; }
      const bl = c.blur > 0.05 ? `blur(${f(c.blur, 1)}px)` : '';
      if (bl !== last.f) { el.style.filter = bl; last.f = bl; }
      const col = c.color || (base && base.color) || '';
      if (col !== last.c) { el.style.color = col; last.c = col; }
      if (c.css || last.css) {
        const prev = last.css || {}, next = c.css || {};
        for (const k in prev) if (!(k in next)) el.style[k] = '';
        for (const k in next) if (prev[k] !== next[k]) el.style[k] = next[k];
        last.css = c.css ? Object.assign({}, c.css) : null;
      }
    }
    function applyGroupState(G, gc) {
      const L = G.gcLast;
      if (G.copyBox && gc.copies !== L.copies) { G.copyBox.style.visibility = gc.copies ? 'inherit' : 'hidden'; L.copies = gc.copies; }
      if (G.orig) {
        const r = G.root;
        r._txHide = r._txHide || {};
        r._txHide[G.seed] = gc.hideOrig;
        const hide = Object.values(r._txHide).some(Boolean);
        if (hide !== L.hide) { G.orig.style.visibility = hide ? 'hidden' : ''; L.hide = hide; }
      }
      if (gc.filter !== L.filter && G.root && G.root.style) {
        const r = G.root;
        r._txFilter = r._txFilter || {};
        r._txFilter[G.seed] = gc.filter;
        if (r._txBaseFilter == null) { const b = cs(r).filter; r._txBaseFilter = b && b !== 'none' ? b : ''; }
        r.style.filter = [r._txBaseFilter, ...Object.values(r._txFilter)].filter(Boolean).join(' ');
        L.filter = gc.filter;
      }
    }
    function renderDom(G, t) {
      applyGroupState(G, groupState(G, t));
      const gh = G.ghosts;
      for (const u of G.units) {
        evalUnit(G, u, t, C);
        writeDom(G, u.el, C, u.last, u.base);
        if (!gh) continue;
        for (let k = 0; k < gh.n; k++) {
          const tk = t - gh.shutter * (k + 1) / gh.n;
          evalUnit(G, u, tk, C2);
          const d = Math.hypot(C2.x - C.x, C2.y - C.y, C2.z - C.z) + Math.abs(C2.r - C.r) * Math.max(u.w, u.h) * 0.01;
          C2.o *= gh.alpha * (1 - k / (gh.n + 1)) * clamp((d - gh.threshold) / (gh.threshold * 4 + 1));
          writeDom(G, u.ghosts[k], C2, u.ghostLast[k], u.base);
        }
      }
    }

    // redraw: the player re-sized the canvases (window resize, fullscreen), which blanks raster groups — draw every group
    onFrame((t, redraw) => {
      for (const G of groups) if (needsRender(G, t) || redraw) G.render(t);
    });

    // =====================================================================
    // representation 1 — split: real DOM text per char / word / line
    // =====================================================================
    /**
     * TX.split(target, { by: 'chars'|'words'|'lines', mask: false|'chars'|'words'|'lines', origin: '50% 50%',
     *                    perspective, seed })
     * returns a group; G.outer are SplitText's elements (tween those on tl), each unit's inner .tx-i belongs to TypeFX.
     */
    function split(target, o = {}) {
      const root = $(target);
      if (!root) throw new Error(`TypeFX.split: target not found: ${target}`);
      if (!window.SplitText) throw new Error('TypeFX.split needs SplitText (vendor/gsap/SplitText.min.js)');
      positioned(root);
      if (o.mask) fixClippedGlow(root);
      const by = o.by || 'chars';
      const type = by === 'lines' ? 'lines' : by === 'words' ? 'words' : 'words,chars';
      const st = window.SplitText.create(root, Object.assign({ type, mask: o.mask || undefined }, o.split || {}));
      const outer = by === 'lines' ? st.lines : by === 'words' ? st.words : st.chars;
      const words = st.words || [];
      for (const w of words) positioned(w);
      const units = outer.map((el) => {
        positioned(el);
        const inner = document.createElement('span');
        inner.className = 'tx-i';
        while (el.firstChild) inner.appendChild(el.firstChild);
        el.appendChild(inner);
        inner.style.transformOrigin = o.origin || '50% 50%';
        const b = relBox(el, root);
        let word = 0;
        for (let i = 0; i < words.length; i++) if (words[i] === el || words[i].contains(el)) { word = i; break; }
        return { el: inner, outer: el, ch: el.textContent, word, bx: b.x, by: b.y, w: b.w, h: b.h, base: { w: parseFloat(cs(inner).fontWeight) || 400 } };
      });
      const ys = [...new Set(units.map((u) => Math.round(u.by / Math.max(1, u.h * 0.5))))].sort((a, b) => a - b);
      for (const u of units) u.line = ys.indexOf(Math.round(u.by / Math.max(1, u.h * 0.5)));
      const G = group('split', root, units, { split: st, outer, perspective: o.perspective, seed: o.seed || (seedN += 7919) });
      G.inner = units.map((u) => u.el);
      G.render = (t) => renderDom(G, t);
      return G;
    }

    // =====================================================================
    // representation 2 — copies: exact overlays of an element (shards, bands, extrusion layers…)
    // =====================================================================
    /**
     * TX.copies(target, { n, cells: [[x,y]…][] | null, clip(i, box) → CSS clip-path, style(i) → {…}, tint(i) → colour,
     *                     behind: false, depth3d: false, seed })
     * Each copy is a full clone of the element's content, clipped to its cell; together they rebuild the original
     * exactly, so swapping the original for its copies is invisible. Units are the copies (x, y = cell centroid).
     */
    function copies(target, o = {}) {
      const root = $(target);
      if (!root) throw new Error(`TypeFX.copies: target not found: ${target}`);
      positioned(root);
      const st = cs(root);
      let orig = null;
      for (const ch of root.children) if (ch.classList.contains('tx-o')) orig = ch;
      if (!orig) {
        orig = document.createElement('span');
        orig.className = 'tx-o';
        const keep = [...root.childNodes].filter((n) => !(n.classList && n.classList.contains('tx-copies')));
        for (const n of keep) orig.appendChild(n);
        root.insertBefore(orig, root.firstChild);
      }
      const bw = (parseFloat(st.borderLeftWidth) || 0) + (parseFloat(st.borderRightWidth) || 0);
      const bh = (parseFloat(st.borderTopWidth) || 0) + (parseFloat(st.borderBottomWidth) || 0);
      const box = { w: Math.max(0, (root.offsetWidth || 0) - bw), h: Math.max(0, (root.offsetHeight || 0) - bh) };
      const wrap = document.createElement('div');
      wrap.className = 'tx-copies';
      wrap.setAttribute('aria-hidden', 'true');
      wrap.setAttribute('data-fx-copy', '');
      Object.assign(wrap.style, { width: box.w + 'px', height: box.h + 'px' });
      if (o.behind) wrap.style.zIndex = '-1';
      if (o.depth3d) { wrap.style.transformStyle = 'preserve-3d'; root.style.transformStyle = 'preserve-3d'; }
      if (o.behind && !o.depth3d) root.style.isolation = 'isolate';
      const layout = {
        display: st.display === 'inline' ? 'block' : st.display, flexDirection: st.flexDirection, flexWrap: st.flexWrap,
        alignItems: st.alignItems, justifyContent: st.justifyContent, gap: st.gap,
        padding: `${st.paddingTop} ${st.paddingRight} ${st.paddingBottom} ${st.paddingLeft}`,
      };
      const html = o.html != null ? o.html : orig.innerHTML;   // copies are snapshots: pass { html } for content that changes (counters)
      const cells = o.cells || null;
      const n = cells ? cells.length : o.n || 1;
      const units = [];
      const els = [];
      for (let i = 0; i < n; i++) {
        const d = document.createElement('div');
        d.className = 'tx-copy' + (o.tint ? ' tx-tint' : '');
        Object.assign(d.style, layout);
        d.innerHTML = html;
        d.querySelectorAll('[id]').forEach((x) => x.removeAttribute('id'));
        let cx = box.w / 2, cy = box.h / 2, x0 = 0, y0 = 0, x1 = box.w, y1 = box.h;
        if (cells) {
          const P = cells[i];
          d.style.clipPath = `polygon(${P.map((p) => `${f(p[0], 1)}px ${f(p[1], 1)}px`).join(',')})`;
          const cc = centroid(P);
          cx = cc[0]; cy = cc[1];
          x0 = Math.min(...P.map((p) => p[0])); x1 = Math.max(...P.map((p) => p[0]));
          y0 = Math.min(...P.map((p) => p[1])); y1 = Math.max(...P.map((p) => p[1]));
        } else if (o.clip) d.style.clipPath = o.clip(i, box);
        d.style.transformOrigin = `${f(cx, 1)}px ${f(cy, 1)}px`;
        if (o.tint) d.style.color = o.tint(i);
        if (o.style) Object.assign(d.style, o.style(i) || {});
        els.push(d);
        units.push({ el: d, bx: cx - (x1 - x0) / 2, by: cy - (y1 - y0) / 2, w: x1 - x0, h: y1 - y0, cell: cells && cells[i] });
      }
      // paint order: o.order lets layers stack back-to-front
      (o.paintOrder ? o.paintOrder(els) : els).forEach((d) => wrap.appendChild(d));
      root.appendChild(wrap);
      const G = group('copies', root, units, { bx: 0, by: 0, w: box.w, h: box.h, box, copyBox: wrap, orig, perspective: o.perspective,
        seed: o.seed || (seedN += 7919) });
      G.render = (t) => renderDom(G, t);
      return G;
    }
    function centroid(P) {
      let a = 0, x = 0, y = 0;
      for (let i = 0; i < P.length; i++) {
        const [x0, y0] = P[i], [x1, y1] = P[(i + 1) % P.length], k = x0 * y1 - x1 * y0;
        a += k; x += (x0 + x1) * k; y += (y0 + y1) * k;
      }
      if (Math.abs(a) < 1e-6) return [P.reduce((s, p) => s + p[0], 0) / P.length, P.reduce((s, p) => s + p[1], 0) / P.length];
      return [x / (3 * a), y / (3 * a)];
    }
    /** Voronoi cells of `pts` inside the rectangle [x0, y0, x1, y1] (half-plane clipping; fine for ≤ 80 cells) */
    function voronoi(pts, [x0, y0, x1, y1]) {
      return pts.map((p, i) => {
        let poly = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
        for (let j = 0; j < pts.length && poly.length; j++) {
          if (j === i) continue;
          const q = pts[j], mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2, nx = q[0] - p[0], ny = q[1] - p[1];
          const side = (v) => (v[0] - mx) * nx + (v[1] - my) * ny;            // ≤ 0: on p's side
          const out = [];
          for (let k = 0; k < poly.length; k++) {
            const a = poly[k], b = poly[(k + 1) % poly.length], sa = side(a), sb = side(b);
            if (sa <= 0) out.push(a);
            if ((sa <= 0) !== (sb <= 0)) { const tt = sa / (sa - sb); out.push([a[0] + (b[0] - a[0]) * tt, a[1] + (b[1] - a[1]) * tt]); }
          }
          poly = out;
        }
        return poly;
      }).filter((P) => P.length >= 3);
    }
    /** shard cells for an element box: denser (smaller) near the impact point, like real glass */
    function shardCells(w, h, { pieces = 26, impact = [0.5, 0.5], margin, seed = 1, focus = 0.45 } = {}) {
      const m = margin == null ? Math.max(24, 0.3 * h) : margin;
      const ix = impact[0] * w, iy = impact[1] * h, R = Math.max(w, h);
      const pts = [];
      for (let k = 0; k < pieces; k++) {
        if (k < pieces * focus) {
          const a = hash(seed, k, 1) * TAU, rr = Math.pow(hash(seed, k, 2), 1.5) * 0.38 * R;
          pts.push([ix + Math.cos(a) * rr, iy + Math.sin(a) * rr * 0.75]);
        } else pts.push([-m + hash(seed, k, 3) * (w + 2 * m), -m + hash(seed, k, 4) * (h + 2 * m)]);
      }
      return voronoi(pts, [-m, -m, w + m, h + m]);
    }
    /** horizontal bands (glitch slices) covering the box, with a margin so glows are not cut */
    function bandCells(w, h, { bands = 7, margin, seed = 1 } = {}) {
      const m = margin == null ? Math.max(24, 0.3 * h) : margin;
      const ws = Array.from({ length: bands }, (_, i) => 0.35 + hash(seed, i, 5));
      const sum = ws.reduce((a, b) => a + b, 0);
      const cells = [];
      let y = -m;
      ws.forEach((wt, i) => {
        const y2 = i === bands - 1 ? h + m : y + (wt / sum) * (h + 2 * m);
        cells.push([[-m, y], [w + m, y], [w + m, y2], [-m, y2]]);
        y = y2;
      });
      return cells;
    }

    /** motion blur for DOM groups (split / copies): ghost copies of each unit, evaluated `shutter` seconds earlier */
    function motionBlur(G, { samples = 4, shutter = 0.04, alpha = 0.5, threshold = 1.5 } = {}) {
      G.ghosts = { n: samples, shutter, alpha, threshold };
      for (const u of G.units) {
        u.ghosts = []; u.ghostLast = [];
        for (let k = 0; k < samples; k++) {
          const g = u.el.cloneNode(true);
          g.classList.add('tx-ghost');
          g.setAttribute('aria-hidden', 'true');
          g.setAttribute('data-fx-copy', '');
          g.style.opacity = '0';
          u.el.parentNode.insertBefore(g, u.el);
          u.ghosts.push(g); u.ghostLast.push({ o: '0' });
        }
      }
      return G;
    }

    // =====================================================================
    // representation 3 — glyph outlines (js/glyphs.js, made by scripts/text_to_paths.mjs)
    // =====================================================================
    const SVGNS = 'http://www.w3.org/2000/svg';
    const svgEl = (tag, attrs, parent) => {
      const n = document.createElementNS(SVGNS, tag);
      for (const k in attrs || {}) n.setAttribute(k, attrs[k]);
      if (parent) parent.appendChild(n);
      return n;
    };
    function ringsToD(rings, disp) {
      let d = '';
      for (const R of rings) {
        for (let i = 0; i < R.length; i += 2) {
          let x = R[i], y = R[i + 1];
          if (disp) { const v = disp(x, y); x += v[0]; y += v[1]; }
          d += (i ? 'L' : 'M') + f(x, 1) + ' ' + f(y, 1);
        }
        d += 'Z';
      }
      return d;
    }
    /**
     * TX.glyphs(container, key, { by: 'piece'|'glyph', fill, stroke, strokeWidth, anchor: [ax, ay], x, y, seed })
     * container: an HTML element (an <svg> is created at its origin; anchor picks which point of the text block sits
     * there, default [0, 0] = top-left), or an <svg>/<g> (drawn at x, y). Units: pieces (each outline + its holes:
     * Hangul jamo, the dot of an i) or whole glyphs.
     */
    function glyphs(container, key, o = {}) {
      const data = (window.GLYPHS || {})[key];
      if (!data) throw new Error(`TypeFX.glyphs: no glyph data "${key}" — add it to glyphs.json and run scripts/text_to_paths.mjs`);
      const host = $(container);
      if (!host) throw new Error(`TypeFX.glyphs: container not found: ${container}`);
      const inSvg = typeof SVGElement !== 'undefined' && host instanceof SVGElement;
      const [ax, ay] = o.anchor || [0, 0];
      let svg = null, g;
      if (inSvg) g = svgEl('g', { transform: `translate(${f((o.x || 0) - ax * data.w)} ${f((o.y || 0) - ay * data.h)})` }, host);
      else {
        positioned(host);
        svg = svgEl('svg', { class: 'tx-svg', width: data.w, height: data.h, viewBox: `0 0 ${data.w} ${data.h}` }, host);
        svg.style.left = f((o.x || 0) - ax * data.w) + 'px';
        svg.style.top = f((o.y || 0) - ay * data.h) + 'px';
        g = svgEl('g', {}, svg);
      }
      g.setAttribute('fill', o.fill || 'currentColor');
      if (o.stroke) { g.setAttribute('stroke', o.stroke); g.setAttribute('stroke-width', o.strokeWidth || 2); g.setAttribute('stroke-linejoin', 'round'); }
      g.setAttribute('fill-rule', 'nonzero');
      const by = o.by || 'piece';
      const units = [], paths = [];
      data.glyphs.forEach((gl, gi) => {
        let parent = g, gEl = null;
        if (by === 'glyph') { gEl = svgEl('g', {}, g); parent = gEl; }
        const ps = gl.pieces.map((pc) => {
          const p = svgEl('path', { d: pc.d }, parent);
          const rec = { el: p, rings: pc.rings, d: pc.d, last: '' , c: pc.c, b: pc.b, glyph: gi };
          paths.push(rec);
          if (by === 'piece') units.push({ el: p, ch: gl.ch, glyph: gi, line: gl.line, word: gl.word || 0, bx: pc.b[0], by: pc.b[1], w: pc.b[2] - pc.b[0], h: pc.b[3] - pc.b[1], cx: pc.c[0], cy: pc.c[1], paths: [rec] });
          return rec;
        });
        if (by === 'glyph' && ps.length) {
          const x0 = Math.min(...gl.pieces.map((p) => p.b[0])), y0 = Math.min(...gl.pieces.map((p) => p.b[1]));
          const x1 = Math.max(...gl.pieces.map((p) => p.b[2])), y1 = Math.max(...gl.pieces.map((p) => p.b[3]));
          units.push({ el: gEl, ch: gl.ch, glyph: gi, line: gl.line, word: gl.word || 0, bx: x0, by: y0, w: x1 - x0, h: y1 - y0, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, paths: ps });
        }
      });
      const G = group('glyphs', svg || g, units, { bx: 0, by: 0, w: data.w, h: data.h, data, svg, g, paths, seed: o.seed || (seedN += 7919) });
      reg.glyphs.push({ key, text: data.text, font: data.font });
      G.render = (t) => renderGlyphs(G, t);
      return G;
    }
    function renderGlyphs(G, t) {
      // outlines: deformers bend the points (rings) of every piece
      const active = G.deforms.map((e) => [e, local(e, t)]).filter((x) => x[1]);
      if (active.length || G._deformed) {
        for (const p of G.paths) {
          let d;
          if (active.length) {
            const u = p.unit || null;
            d = ringsToD(p.rings, (x, y) => {
              let dx = 0, dy = 0;
              for (const [e, s] of active) { const v = e.fn(x, y, s, p, u); if (v) { dx += v[0]; dy += v[1]; } }
              return [dx, dy];
            });
          } else d = p.d;
          if (d !== p.last) { p.el.setAttribute('d', d); p.last = d; }
        }
        G._deformed = active.length > 0;
      }
      const gc = groupState(G, t);
      if (gc.filter !== G.gcLast.filter) { (G.svg || G.g).style.filter = gc.filter; G.gcLast.filter = gc.filter; }
      for (const u of G.units) {
        const c = evalUnit(G, u, t, C);
        const sx = c.sx * Math.cos(c.ry * Math.PI / 180), sy = c.sy * Math.cos(c.rx * Math.PI / 180);
        let tr = '';
        if (c.x || c.y || c.r || c.kx || Math.abs(sx - 1) > 1e-4 || Math.abs(sy - 1) > 1e-4) {
          tr = `translate(${f(u.cx + c.x)} ${f(u.cy + c.y)})`;
          if (c.r) tr += ` rotate(${f(c.r, 1)})`;
          if (c.kx) tr += ` skewX(${f(c.kx, 1)})`;
          if (Math.abs(sx - 1) > 1e-4 || Math.abs(sy - 1) > 1e-4) tr += ` scale(${f(sx, 4)} ${f(sy, 4)})`;
          tr += ` translate(${f(-u.cx)} ${f(-u.cy)})`;
        }
        const L = u.last;
        if (tr !== L.t) { if (tr) u.el.setAttribute('transform', tr); else u.el.removeAttribute('transform'); L.t = tr; }
        const op = c.o >= 0.999 ? '' : f(clamp(c.o), 3);
        if (op !== L.o) { if (op) u.el.setAttribute('opacity', op); else u.el.removeAttribute('opacity'); L.o = op; }
        const col = c.color || '';
        if (col !== L.c) { if (col) u.el.setAttribute('fill', col); else u.el.removeAttribute('fill'); L.c = col; }
        if (c.css || L.css) {
          const prev = L.css || {}, next = c.css || {};
          for (const k in prev) if (!(k in next)) u.el.style[k] = '';
          for (const k in next) if (prev[k] !== next[k]) u.el.style[k] = next[k];
          L.css = c.css ? Object.assign({}, c.css) : null;
        }
      }
    }
    /** bend outlines: fn(x, y, s, piece) → [dx, dy] (block coordinates, px). Same windows/fill as fx. */
    function deform(G, o, fn) {
      if (G.kind !== 'glyphs') throw new Error('TypeFX.deform works on glyph groups (TX.glyphs)');
      for (const u of G.units) for (const p of u.paths) p.unit = u;
      return fx(G, Object.assign({}, o, { list: 'deforms' }), fn);
    }
    /** outlines as plain polygons for three.js ExtrudeGeometry: [{ outer: [[x,y]…], holes: [[[x,y]…]…], glyph, ch }] */
    function shapes(key, { flipY = true, center = true } = {}) {
      const data = (window.GLYPHS || {})[key];
      if (!data) throw new Error(`TypeFX.shapes: no glyph data "${key}"`);
      const cx = center ? data.w / 2 : 0, cy = center ? data.h / 2 : 0;
      const out = [];
      const pt = (R, i) => [R[i] - cx, flipY ? cy - R[i + 1] : R[i + 1] - cy];
      const ring = (R) => { const a = []; for (let i = 0; i < R.length; i += 2) a.push(pt(R, i)); return a; };
      data.glyphs.forEach((gl, gi) => gl.pieces.forEach((pc) => {
        out.push({ outer: ring(pc.rings[0]), holes: pc.rings.slice(1).map(ring), glyph: gi, ch: gl.ch });
      }));
      return out;
    }

    // =====================================================================
    // representation 4 — raster tiles: the text as canvas pixels
    // =====================================================================
    /**
     * await TX.raster(text, { family: "'Pretendard'", weight: 800, size: 160, color: '#fff', stroke, strokeWidth,
     *                         gradient: [[0,'#fff'],[1,'#59f3e0']], tracking: 0, lineHeight: 1.15, align: 'center', pad: 24, scale: 2 })
     * Draws with a catalogue font (after loading exactly these glyphs) into an offscreen canvas. check_fonts.mjs
     * verifies the family and that it covers every character (window.__typefx.rasters).
     */
    async function raster(text, o = {}) {
      const size = o.size || 160, weight = o.weight || 800, family = o.family || "'Pretendard'";
      const font = `${o.italic ? 'italic ' : ''}${weight} ${size}px ${family}`;
      if (document.fonts && document.fonts.load) { try { await document.fonts.load(font, text); } catch (e) { /* reported by check_fonts */ } }
      const s = o.scale || 2, pad = o.pad == null ? Math.round(size * 0.18) : o.pad, lh = (o.lineHeight || 1.15) * size, tr = o.tracking || 0;
      const lines = String(text).split('\n');
      const meas = document.createElement('canvas').getContext('2d');
      const widthOf = (str) => {
        if (!meas || !meas.measureText) return str.length * size * 0.6;
        meas.font = font;
        return (meas.measureText(str).width || str.length * size * 0.6) + tr * Math.max(0, [...str].length - 1);
      };
      const ws = lines.map(widthOf);
      const w = Math.ceil(Math.max(...ws, 1) + pad * 2), h = Math.ceil(lh * lines.length + pad * 2);
      const cv = document.createElement('canvas');
      cv.width = Math.max(1, Math.round(w * s)); cv.height = Math.max(1, Math.round(h * s));
      const c = cv.getContext('2d', { willReadFrequently: true });   // read back below (getImageData): keep it on the CPU
      const R = { canvas: cv, w, h, s, text, font, data: null, ok: !!(c && c.fillText) };
      reg.rasters.push({ text, font, family, weight });
      if (!R.ok) return R;
      c.setTransform(s, 0, 0, s, 0, 0);
      c.font = font;
      c.textBaseline = 'alphabetic';
      let fill = o.color || '#ffffff';
      if (o.gradient && c.createLinearGradient) {
        const gr = c.createLinearGradient(0, pad, 0, h - pad);
        if (gr) { for (const [k, col] of o.gradient) gr.addColorStop(k, col); fill = gr; }
      }
      c.fillStyle = fill;
      lines.forEach((line, li) => {
        const lw = ws[li], al = o.align || 'center';
        let x = al === 'left' ? pad : al === 'right' ? w - pad - lw : (w - lw) / 2;
        const y = pad + li * lh + size * 0.86;
        const drawStr = (str, xx) => {
          if (o.stroke) { c.lineJoin = 'round'; c.lineWidth = o.strokeWidth || size * 0.05; c.strokeStyle = o.stroke; c.strokeText(str, xx, y); }
          c.fillText(str, xx, y);
        };
        if (!tr) drawStr(line, x);
        else for (const ch of line) { drawStr(ch, x); x += widthOf(ch) + tr; }
      });
      try { R.data = c.getImageData(0, 0, cv.width, cv.height); } catch (e) { R.data = null; }
      return R;
    }
    /**
     * TX.tiles(R, { into, x, y, anchor: [0.5, 0.5], size: 6, mode: 'image'|'dot', z, seed })
     * Cuts a raster into tiles (size in stage px; 2–4 reads as particles, 6–14 as fragments). The group draws on its own
     * canvas inside `into` (a scene, default the stage) at stage point (x, y). Untouched tiles draw as one image.
     */
    function tiles(R, o = {}) {
      const host = $(o.into) || stage;
      const cv = document.createElement('canvas');
      cv.className = 'tx-canvas';
      cv.setAttribute('aria-hidden', 'true');
      if (o.z != null) cv.style.zIndex = o.z;
      host.appendChild(cv);
      const g2 = fitCanvas(cv);
      // every tile with any visible pixel is a unit: a tile left out would stay behind when the others fly away
      const size = o.size || 6, th = o.threshold == null ? 0 : o.threshold;
      const [ax, ay] = o.anchor || [0.5, 0.5];
      const ox = (o.x == null ? W / 2 : o.x) - ax * R.w, oy = (o.y == null ? H / 2 : o.y) - ay * R.h;
      const units = [];
      const D = R.data;
      for (let ty = 0; ty < R.h; ty += size) {
        for (let tx = 0; tx < R.w; tx += size) {
          let a = 0, r = 0, gg = 0, b = 0, n = 0;
          if (D) {
            const x0 = Math.floor(tx * R.s), y0 = Math.floor(ty * R.s), x1 = Math.min(D.width, Math.floor((tx + size) * R.s)), y1 = Math.min(D.height, Math.floor((ty + size) * R.s));
            for (let yy = y0; yy < y1; yy++) for (let xx = x0; xx < x1; xx++) {
              const k = (yy * D.width + xx) * 4, al = D.data[k + 3] / 255;
              a += al; r += D.data[k] * al; gg += D.data[k + 1] * al; b += D.data[k + 2] * al; n++;
            }
          }
          if (!n || a * 255 < 0.5 || a / n < th) continue;
          units.push({ sx: tx, sy: ty, bx: tx, by: ty, w: Math.min(size, R.w - tx), h: Math.min(size, R.h - ty), a: a / n, rgb: [r / a, gg / a, b / a] });
        }
      }
      const scratch = document.createElement('canvas');
      scratch.width = R.canvas.width; scratch.height = R.canvas.height;
      const sc = scratch.getContext('2d');
      const G = group('tiles', cv, units, { bx: 0, by: 0, w: R.w, h: R.h, R, canvas: cv, g2, ox, oy, size, mode: o.mode || 'image', scratch, sc,
        seed: o.seed || (seedN += 7919) });
      G.render = (t) => renderTiles(G, t);
      return G;
    }
    function renderTiles(G, t) {
      const { g2, R, ox, oy, sc } = G;
      if (!g2 || !R.ok || !sc) return;
      g2.save(); g2.setTransform(1, 0, 0, 1, 0, 0); g2.clearRect(0, 0, G.canvas.width, G.canvas.height); g2.restore();
      const gc = groupState(G, t);
      if (gc.hideAll) return;
      const S = R.s, moved = [];
      for (const u of G.units) {
        const c = evalUnit(G, u, t, C);
        if (!isIdentity(c)) moved.push([u, Object.assign({}, c)]);
      }
      // base image minus the tiles that left home
      sc.setTransform(1, 0, 0, 1, 0, 0);
      sc.clearRect(0, 0, G.scratch.width, G.scratch.height);
      sc.globalCompositeOperation = 'source-over';
      sc.drawImage(R.canvas, 0, 0);
      if (moved.length) {
        sc.globalCompositeOperation = 'destination-out';
        sc.fillStyle = '#000';
        for (const [u] of moved) sc.fillRect(u.sx * S - 0.5, u.sy * S - 0.5, u.w * S + 1, u.h * S + 1);
        sc.globalCompositeOperation = 'source-over';
      }
      g2.globalAlpha = gc.alpha == null ? 1 : gc.alpha;
      const warps = G.warps.map((e) => [e, local(e, t)]).filter((x) => x[1]);
      if (!warps.length) g2.drawImage(G.scratch, 0, 0, G.scratch.width, G.scratch.height, ox, oy, R.w, R.h);
      else {
        // pixel warps: rows shift sideways (axis x) or columns shift vertically (axis y)
        const strip = G.warpStrip || 2;
        const xs = warps.filter(([e]) => e.axis !== 'y'), ys = warps.filter(([e]) => e.axis === 'y');
        const off = (list, v, other) => { let d = 0; for (const [e, s] of list) d += e.fn(v, s, other) || 0; return d; };
        if (!ys.length) {
          for (let y = 0; y < R.h; y += strip) {
            const dx = off(xs, y - R.h / 2, 0);
            g2.drawImage(G.scratch, 0, y * S, G.scratch.width, strip * S, ox + dx, oy + y, R.w, strip);
          }
        } else {
          for (let x = 0; x < R.w; x += strip) {
            const dy = off(ys, x - R.w / 2, 0), dx = xs.length ? off(xs, 0, x - R.w / 2) : 0;
            g2.drawImage(G.scratch, x * S, 0, strip * S, G.scratch.height, ox + x + dx, oy + dy, strip, R.h);
          }
        }
      }
      // tiles that moved
      for (const [u, c] of moved) {
        if (c.o <= 0.004) continue;
        g2.globalAlpha = clamp(c.o) * (gc.alpha == null ? 1 : gc.alpha);
        const cx = ox + u.bx + u.w / 2 + c.x, cy = oy + u.by + u.h / 2 + c.y;
        const sx = c.sx * Math.cos(c.ry * Math.PI / 180), sy = c.sy * Math.cos(c.rx * Math.PI / 180);
        if (G.mode === 'dot') {
          g2.fillStyle = c.color || `rgb(${u.rgb.map(Math.round).join(',')})`;
          const rw = u.w * Math.abs(sx) * Math.sqrt(u.a), rh = u.h * Math.abs(sy) * Math.sqrt(u.a);
          g2.fillRect(cx - rw / 2, cy - rh / 2, rw, rh);
        } else {
          g2.save();
          g2.translate(cx, cy);
          if (c.r) g2.rotate(c.r * Math.PI / 180);
          g2.scale(sx || 1e-4, sy || 1e-4);
          g2.drawImage(R.canvas, u.sx * S, u.sy * S, u.w * S, u.h * S, -u.w / 2, -u.h / 2, u.w, u.h);
          g2.restore();
        }
      }
      g2.globalAlpha = 1;
    }
    /** bend pixels: fn(v, s, other) → offset px. axis 'x': each row shifts sideways (v = row y from centre);
     *  axis 'y': each column shifts vertically (v = column x from centre). */
    function warp(G, o, fn) {
      if (G.kind !== 'tiles') throw new Error('TypeFX.warp works on raster groups (TX.tiles)');
      const e = fx(G, Object.assign({}, o, { list: 'warps' }), fn);
      e.axis = o.axis || 'x';
      if (o.strip) G.warpStrip = o.strip;
      return e;
    }

    // =====================================================================
    // presets — examples of the system, all written with fx / deform / warp. Copy one to make a new effect.
    // =====================================================================
    const E = (o, k, d) => (o[k] == null ? d : o[k]);

    /** a travelling wave through the units (sea, sound, breath) */
    function wave(G, from, to, o = {}) {
      const amp = E(o, 'amp', 18), len = E(o, 'length', 6), speed = E(o, 'speed', 1.1), rot = E(o, 'rot', 6), sc = E(o, 'scale', 0), fade = E(o, 'fade', 0.35);
      const ord = order(G, o.order || 'index');
      return fx(G, { from, to }, (u, s, c) => {
        const env = smooth(s.lt / fade) * smooth((s.dur - s.lt) / fade);
        const ph = TAU * (s.lt * speed - ord[u.i] * (G.units.length / len));
        const v = Math.sin(ph) * env;
        c.y += -amp * v;
        c.r += rot * Math.cos(ph) * env;
        if (sc) { c.sx *= 1 + sc * v; c.sy *= 1 + sc * v; }
      });
    }
    /** squash-and-stretch jiggle after a hit (jelly, rubber, a landing) — feet stay planted */
    function jelly(G, at, o = {}) {
      const amp = E(o, 'amp', 0.32), freq = E(o, 'freq', 3.2), decay = E(o, 'decay', 4.2), st = E(o, 'stagger', 0.035), dur = E(o, 'dur', 1.6), skew = E(o, 'skew', 10);
      const ord = order(G, o.order || 'center');
      return fx(G, { from: at, to: at + dur + st * G.units.length }, (u, s, c) => {
        const lt = s.lt - ord[u.i] * st * G.units.length;
        const v = wobble(lt, freq, decay);
        const sy = 1 - amp * v, sx = 1 + amp * 0.75 * v;
        c.sx *= sx; c.sy *= sy;
        c.y += (1 - sy) * u.h / 2;                      // keep the baseline on the floor
        c.kx += skew * wobble(lt - 0.04, freq * 0.5, decay) * (u.nx || 0.3);
      });
    }
    /** units fly apart from a point (group coordinates) and fade — explosion, scattering, letting go */
    function scatter(G, at, o = {}) {
      const dur = E(o, 'dur', 1.3), force = E(o, 'force', 900), grav = E(o, 'gravity', 900), drag = E(o, 'drag', 1.6), spin = E(o, 'spin', 360);
      const tumble = E(o, 'tumble', 0), lift = E(o, 'lift', 0.25), z = E(o, 'z', 0), spread = E(o, 'spread', 0.9), st = E(o, 'stagger', 0);
      const P = o.from || [0, 0], fadeAt = E(o, 'fadeAt', 0.5), reverse = !!o.reverse, ez = ease(o.ease || 'power3.out');
      const ord = order(G, o.order || P);
      const R = Math.max(G.w, G.h, 1);
      const total = dur + st;
      const move = (u, lt, c) => {
        if (lt <= 0) return;
        const dx = u.x - P[0], dy = u.y - P[1], d = Math.hypot(dx, dy) || 1;
        const ang = Math.atan2(dy, dx) + (u.r(2) - 0.5) * TAU * spread * 0.5;
        const sp = force * (0.45 + 0.9 * u.r(1)) / (1 + d / (0.7 * R));
        const vx = Math.cos(ang) * sp, vy = Math.sin(ang) * sp - force * lift * u.r(3);
        c.x += drift(lt, vx, drag); c.y += drift(lt, vy, drag) + 0.5 * grav * lt * lt;
        c.z += drift(lt, z * (u.r(6) - 0.3), drag);
        c.r += (u.r(4) - 0.5) * 2 * spin * lt;
        if (tumble) { c.rx += (u.r(7) - 0.5) * 2 * tumble * lt; c.ry += (u.r(8) - 0.5) * 2 * tumble * lt; }
        c.o *= 1 - smooth((lt - dur * fadeAt) / (dur * (1 - fadeAt)));
      };
      return fx(G, { from: at, to: at + total, fill: reverse ? 'backwards' : 'forwards' }, (u, s, c) => {
        if (!reverse) return move(u, s.lt - ord[u.i] * st, c);
        // assemble: play the flight backwards, eased so the pieces settle into place
        const lt = clamp(s.lt - ord[u.i] * st, 0, dur);
        move(u, dur * (1 - ez(lt / dur)), c);
      });
    }
    const assemble = (G, at, o = {}) => scatter(G, at, Object.assign({ fadeAt: 0.55 }, o, { reverse: true }));

    /**
     * glass break: the element cracks at an impact point, then bursts into shards (copies clipped to Voronoi cells).
     * { pieces, impact: [fx, fy] (fractions of the box), crack (s), gap (px), dur, force, gravity, spin, tumble, z,
     *   reverse (shards fly in and fuse), blur: true (motion blur) } — returns the copies group
     */
    function shatter(target, at, o = {}) {
      const root = $(target);
      const box = { w: root.offsetWidth, h: root.offsetHeight };
      const seed = o.seed || (seedN += 7919);
      const imp = o.impact || [0.5, 0.5];
      const G = copies(root, { cells: shardCells(box.w, box.h, { pieces: E(o, 'pieces', 26), impact: imp, seed, margin: o.margin }), seed, perspective: o.perspective, html: o.html });
      if (o.blur) motionBlur(G, typeof o.blur === 'object' ? o.blur : { samples: 3, shutter: 0.035 });
      const P = [(imp[0] - 0.5) * G.w, (imp[1] - 0.5) * G.h];
      const crack = E(o, 'crack', 0.22), gap = E(o, 'gap', 3), dur = E(o, 'dur', 1.6), rev = !!o.reverse;
      const R = Math.max(G.w, G.h, 1);
      const burst = { dur, force: E(o, 'force', 1100), gravity: E(o, 'gravity', 1500), drag: E(o, 'drag', 1.3), spin: E(o, 'spin', 300),
        tumble: E(o, 'tumble', 420), z: E(o, 'z', 260), lift: E(o, 'lift', 0.3), spread: E(o, 'spread', 0.5), from: P, fadeAt: 0.55 };
      const total = crack + dur;
      const t0 = at;
      const sc = scatter(G, t0 + (rev ? 0 : crack), Object.assign({}, burst, { reverse: rev, ease: o.ease || 'expo.out' }));
      // the crack: shards part by a hairline (the background shows through the cuts) and twist a little
      fx(G, { from: rev ? t0 + dur : t0, to: rev ? t0 + total : t0 + crack, fill: 'both' }, (u, s, c) => {
        const k = rev ? 1 - smooth(s.p) : smooth(s.p);
        const dx = u.x - P[0], dy = u.y - P[1], d = Math.hypot(dx, dy) || 1;
        const g = gap * k * (0.6 + 0.8 * u.r(11)) * (1.4 - 0.8 * Math.min(1, d / R));
        c.x += dx / d * g; c.y += dy / d * g;
        c.r += (u.r(12) - 0.5) * 2.4 * k;
      }, (s, gc) => {
        // forward: copies stand in from the impact on; reverse: until the pieces have fused
        if (!rev) { gc.copies = s.t >= t0; gc.hideOrig = s.t >= t0; }
        else { gc.copies = s.t < t0 + total; gc.hideOrig = s.t < t0 + total; }
      });
      G.effect = sc;
      G.impact = P;
      return G;
    }

    /** digital glitch: the element is sliced into bands that jump sideways, with an RGB split, on a hashed beat */
    function glitch(target, from, to, o = {}) {
      const root = $(target);
      const seed = o.seed || (seedN += 7919);
      const bands = E(o, 'bands', 7), amount = E(o, 'amount', 42), rate = E(o, 'rate', 24), density = E(o, 'density', 0.55), rgb = o.rgb !== false;
      const cells = bandCells(root.offsetWidth, root.offsetHeight, { bands, seed });
      const tints = rgb ? [o.c1 || 'rgb(255,48,96)', o.c2 || 'rgb(48,240,255)'] : [];
      const G = copies(root, { cells, seed, html: o.html });
      let T = null;
      if (rgb) {
        T = copies(root, { n: 2, tint: (i) => tints[i], style: () => ({ mixBlendMode: 'screen' }), seed: seed + 1, html: o.html });
        T.copyBox.style.zIndex = '-1';
        root.style.isolation = 'isolate';
      }
      const burstAt = (t) => {
        const q = Math.floor(t * rate);
        const env = smooth((t - from) / 0.08) * smooth((to - t) / 0.08);
        return hash(seed, q, 3) < density ? env * (0.35 + 0.65 * hash(seed, q, 4)) : 0;
      };
      fx(G, { from, to }, (u, s, c) => {
        const b = burstAt(s.t), q = Math.floor(s.t * rate);
        if (!b) return;
        const jump = hash(seed + u.i, q, 7) < 0.6 ? (hash(seed + u.i, q, 8) - 0.5) * 2 * amount * b : 0;
        c.x += jump;
        if (hash(seed + u.i, q, 9) < 0.15) c.kx += (hash(seed + u.i, q, 10) - 0.5) * 30 * b;
      }, (s, gc) => { gc.copies = true; gc.hideOrig = true; });
      if (T) fx(T, { from, to }, (u, s, c) => {
        const b = burstAt(s.t), q = Math.floor(s.t * rate);
        c.x += (u.i ? 1 : -1) * (4 + amount * 0.22 * b) * (0.6 + 0.4 * hash(seed, q, 11));
        c.y += (u.i ? -1 : 1) * 2 * b;
        c.o *= 0.25 + 0.75 * b;
      }, (s, gc) => { gc.copies = true; });
      G.rgb = T;
      return G;
    }

    /**
     * solid type: copies stacked behind the face. mode 'offset' (poster block letters, angle in degrees, 90 = down)
     * or 'z' (true depth for 3D rotations of the element: tween rotationY/rotationX with transformPerspective on tl).
     * G.state.depth / G.state.angle can be tweened on tl.
     */
    function extrude(target, o = {}) {
      const root = $(target);
      const layers = E(o, 'layers', 14), mode = o.mode || 'offset';
      const base = parseRGB(cs(root).color);
      const side = o.side ? parseRGB(o.side) : mix(base, [0, 0, 0, 1], 0.55);
      const end = o.shade ? parseRGB(o.shade) : mix(side, [0, 0, 0, 1], 0.55);
      const edge = o.edge ? parseRGB(o.edge) : null;
      const G = copies(root, {
        n: layers, behind: true, depth3d: mode === 'z', tint: (i) => rgba(edge && i === 0 ? edge : mix(side, end, i / Math.max(1, layers - 1))),
        paintOrder: (els) => els.slice().reverse(), html: o.html,
      });
      G.state = { depth: E(o, 'depth', 26), angle: E(o, 'angle', 125) };
      fx(G, { static: true }, (u, s, c) => {
        const k = (u.i + 1) / layers, d = G.state.depth * k;
        if (mode === 'z') c.z -= d;
        else { const a = G.state.angle * Math.PI / 180; c.x += Math.cos(a) * d; c.y += Math.sin(a) * d; }
      }, (s, gc) => { gc.copies = G.state.depth > 0.3; });
      return G;
    }

    /**
     * neon sign: ignites with a hashed flicker, then hums. Works on a split group (per-letter flicker) or an element.
     * The hum is a function of t, so the window stays open until `to` (default: the end of the video) and the group renders
     * every frame from `at`; after `to` it holds steady. On a long video pass the scene's end as `to`.
     */
    function neon(target, at, o = {}) {
      const isG = target && target.units;
      const G = isG ? target : group('root', $(target), [], {});
      if (!isG) G.render = (t) => applyGroupState(G, groupState(G, t));
      const col = parseRGB(o.color || cs(G.root).color), rad = E(o, 'radius', 22), ign = E(o, 'ignite', 0.9), hum = E(o, 'hum', 0.06), un = E(o, 'unlit', 0.12);
      const to = o.to == null ? Infinity : Math.max(at, T(o.to)), seed = G.seed;
      const glowAt = (k) => `drop-shadow(0 0 ${f(rad * 0.18)}px ${rgba(col, 0.95 * k)}) drop-shadow(0 0 ${f(rad)}px ${rgba(col, 0.75 * k)})`;
      const lit = (t, salt) => {
        t = Math.min(t, to);                                // after `to`: the value at `to`, whatever the seek path
        if (t < at) return 0;
        const lt = t - at;
        if (lt >= ign) return 1 - hum * (0.5 + 0.5 * noise(lt * 7, salt));
        const q = Math.floor(lt * 30), p = lt / ign;
        return hash(seed + salt, q, 21) < Math.pow(p, 0.7) * 0.9 + 0.08 ? 0.75 + 0.25 * hash(seed, q, 22) : 0.06;
      };
      fx(G, { from: at, to, fill: 'both' }, (u, s, c) => { c.o *= un + (1 - un) * lit(s.t, u.i + 1); },
        (s, gc) => { const k = lit(s.t, 0); gc.filter = `${glowAt(k)} brightness(${f(isG ? 1 : un + (1 - un) * k, 3)})`; });
      return G;
    }
    /**
     * a variable-font axis breathes along the text. Default the weight (Pretendard 45–920); any axis of the font with
     * { axis: 'wdth' | 'slnt' | 'opsz' | 'XROT' | 'MORF' …, min, max, rest } (Google Fonts families via add_font.mjs).
     */
    function breathe(G, from, to, o = {}) {
      const axis = o.axis || 'wght';
      const min = E(o, 'min', 250), max = E(o, 'max', 900), speed = E(o, 'speed', 0.8), len = E(o, 'length', 8), fade = E(o, 'fade', 0.4);
      const rest = E(o, 'rest', (min + max) / 2);
      const ord = order(G, o.order || 'index');
      return fx(G, { from, to }, (u, s, c) => {
        const env = smooth(s.lt / fade) * smooth((s.dur - s.lt) / fade);
        const v = lerp(min, max, 0.5 + 0.5 * Math.sin(TAU * (s.lt * speed - ord[u.i] * G.units.length / len)));
        if (axis === 'wght') c.w += (v - u.base.w) * env;
        else (c.vary || (c.vary = {}))[axis] = lerp(rest, v, env);
      });
    }
    /** drifting like something under water: slow noise in position and angle */
    function float(G, from, to, o = {}) {
      const amp = E(o, 'amp', 12), speed = E(o, 'speed', 0.35), rot = E(o, 'rot', 5), fade = E(o, 'fade', 0.6);
      return fx(G, { from, to }, (u, s, c) => {
        const env = smooth(s.lt / fade) * smooth((s.dur - s.lt) / fade), k = s.t * speed;
        c.x += amp * noise(k, u.i * 3.1, 1) * env; c.y += amp * noise(k, u.i * 3.1, 2) * env; c.r += rot * noise(k, u.i * 3.1, 3) * env;
      });
    }
    /** nervous trembling (fear, cold, pressure): hashed per frame, eased in and out */
    function tremble(G, from, to, o = {}) {
      const amp = E(o, 'amp', 3), rate = E(o, 'rate', 30), rot = E(o, 'rot', 1.5), fade = E(o, 'fade', 0.15);
      return fx(G, { from, to }, (u, s, c) => {
        const env = smooth(s.lt / fade) * smooth((s.dur - s.lt) / fade), q = Math.floor(s.t * rate);
        c.x += (hash(G.seed + u.i, q, 1) - 0.5) * 2 * amp * env; c.y += (hash(G.seed + u.i, q, 2) - 0.5) * 2 * amp * env;
        c.r += (hash(G.seed + u.i, q, 3) - 0.5) * 2 * rot * env;
      });
    }
    /** units pop in on a spring, staggered */
    function pop(G, at, o = {}) {
      const st = E(o, 'stagger', 0.045), freq = E(o, 'freq', 1.7), decay = E(o, 'decay', 7), rise = E(o, 'rise', 30);
      const ord = order(G, o.order || 'index'), dur = E(o, 'dur', 1.2);
      return fx(G, { from: at, to: at + dur + st * G.units.length, fill: 'backwards' }, (u, s, c) => {
        const lt = s.lt - ord[u.i] * st * G.units.length, k = spring(lt, freq, decay);
        c.sx *= Math.max(0, k); c.sy *= Math.max(0, k); c.y += rise * (1 - clamp(k)); c.o *= clamp(lt * 12);
      });
    }
    /** units drop in from above and bounce on the baseline */
    function drop(G, at, o = {}) {
      const h = E(o, 'height', 520), g = E(o, 'gravity', 3200), e = E(o, 'bounce', 0.38), st = E(o, 'stagger', 0.05), squash = E(o, 'squash', 0.25);
      const ord = order(G, o.order || 'random'), dur = E(o, 'dur', 1.4);
      return fx(G, { from: at, to: at + dur + st * G.units.length, fill: 'backwards' }, (u, s, c) => {
        const lt = s.lt - ord[u.i] * st * G.units.length;
        c.y -= bounce(lt, h, g, e);
        c.o *= clamp(lt * 20 + (lt > 0 ? 1 : 0));
        const t0 = Math.sqrt(2 * h / g), sq = squash * wobble(lt - t0, 4, 9);
        if (lt > t0) { c.sy *= 1 - sq; c.sx *= 1 + sq * 0.8; c.y += sq * u.h / 2; }
      });
    }
    /** a vortex: units spiral into a point (default the centre; radius > 0 leaves them on a ring), reverse: spiral out into place */
    function swirl(G, at, o = {}) {
      const dur = E(o, 'dur', 1.4), turns = E(o, 'turns', 1.2), rad = E(o, 'radius', 0), st = E(o, 'stagger', 0.3), rev = !!o.reverse, ez = ease(o.ease || 'power2.in');
      const ord = order(G, o.order || 'center');
      return fx(G, { from: at, to: at + dur + st, fill: rev ? 'backwards' : 'forwards' }, (u, s, c) => {
        let k = clamp((s.lt - ord[u.i] * st) / dur);
        k = rev ? 1 - ease('power3.out')(k) : ez(k);
        const a0 = Math.atan2(u.y, u.x), r0 = Math.hypot(u.x, u.y);
        const a = a0 + TAU * turns * k, r = lerp(r0, rad, k);
        c.x += Math.cos(a) * r - u.x; c.y += Math.sin(a) * r - u.y; c.r += 360 * turns * k; c.o *= 1 - smooth((k - 0.6) / 0.4);
        c.sx *= 1 - 0.5 * k; c.sy *= 1 - 0.5 * k;
      });
    }
    /** units are pulled toward a point (group coordinates) and swallowed — gravity well, drain, black hole */
    function magnet(G, at, o = {}) {
      const P = o.to || [0, 300], dur = E(o, 'dur', 1.2), st = E(o, 'stagger', 0.4), ez = ease(o.ease || 'power3.in'), shrink = E(o, 'shrink', 0.9);
      const ord = order(G, o.order || [-P[0], -P[1]]);
      return fx(G, { from: at, to: at + dur + st, fill: 'forwards' }, (u, s, c) => {
        const k = ez(clamp((s.lt - ord[u.i] * st) / dur));
        c.x += (P[0] - u.x) * k; c.y += (P[1] - u.y) * k; c.sx *= 1 - shrink * k; c.sy *= 1 - shrink * k;
        c.r += (u.r(5) - 0.5) * 180 * k; c.o *= 1 - smooth((k - 0.75) / 0.25);
      });
    }
    /** 3D flip of every unit around its own axis, staggered (axis 'x' = like a split-flap board) */
    function flip(G, at, o = {}) {
      const dur = E(o, 'dur', 0.7), st = E(o, 'stagger', 0.05), axis = o.axis || 'x', turns = E(o, 'turns', 1), ez = ease(o.ease || 'power3.inOut');
      const ord = order(G, o.order || 'index');
      return fx(G, { from: at, to: at + dur + st * G.units.length }, (u, s, c) => {
        const k = ez(clamp((s.lt - ord[u.i] * st * G.units.length) / dur)) * 360 * turns;
        if (axis === 'x') c.rx += k; else c.ry += k;
      });
    }

    // ---- glyph outline presets (TX.glyphs groups) ----
    /** outlines draw on as strokes, then fill (signature, blueprint, neon tube) */
    function drawOn(G, at, o = {}) {
      const dur = E(o, 'dur', 1.4), st = E(o, 'stagger', 0.06), fillDelay = E(o, 'fillDelay', dur * 0.75), fillDur = E(o, 'fillDur', 0.5);
      const els = G.paths.map((p) => p.el);
      els.forEach((p) => { p.setAttribute('stroke', o.stroke || 'currentColor'); p.setAttribute('stroke-width', o.width || 2.5); p.setAttribute('stroke-linejoin', 'round'); });
      tl.fromTo(els, { drawSVG: '0% 0%', fillOpacity: 0 }, { drawSVG: '0% 100%', duration: dur, ease: o.ease || 'power2.inOut', stagger: st }, at);
      tl.fromTo(els, { fillOpacity: 0 }, { fillOpacity: 1, duration: fillDur, ease: 'power1.out', stagger: st, immediateRender: false }, at + fillDelay);
      if (o.keepStroke !== true) tl.to(els, { strokeOpacity: 0, duration: fillDur, stagger: st }, at + fillDelay + fillDur * 0.5);
      return G;
    }
    /** liquid outlines: points flow on smooth noise (under water, heat, dream) */
    function liquid(G, from, to, o = {}) {
      const amp = E(o, 'amp', 7), sc = E(o, 'scale', 0.014), speed = E(o, 'speed', 0.7), fade = E(o, 'fade', 0.5);
      return deform(G, { from, to }, (x, y, s) => {
        const env = smooth(s.lt / fade) * smooth((s.dur - s.lt) / fade), z = s.t * speed;
        return [amp * env * noise(x * sc, y * sc, z), amp * env * noise(x * sc + 31.7, y * sc, z + 9.1)];
      });
    }
    /** a shock wave runs through the outlines from a point (jelly, impact, sonar) */
    function shockwave(G, at, o = {}) {
      const P = o.from || [G.w / 2, G.h], amp = E(o, 'amp', 14), speed = E(o, 'speed', 900), freq = E(o, 'freq', 6), decay = E(o, 'decay', 3.5), dur = E(o, 'dur', 1.6);
      return deform(G, { from: at, to: at + dur }, (x, y, s) => {
        const dx = x - P[0], dy = y - P[1], d = Math.hypot(dx, dy) || 1, v = amp * wobble(s.lt - d / speed, freq, decay);
        return [dx / d * v, dy / d * v];
      });
    }
    /** outlines sag and drip downward (heat, sadness, pressure); drips are uneven columns */
    function melt(G, at, o = {}) {
      const dur = E(o, 'dur', 2.2), drop = E(o, 'drop', 200), sc = E(o, 'scale', 0.018), ez = ease(o.ease || 'power1.in'), rev = !!o.reverse;
      return deform(G, { from: at, to: at + dur, fill: rev ? 'backwards' : 'forwards' }, (x, y, s) => {
        const k = rev ? 1 - ease('power3.out')(s.p) : ez(s.p);
        const low = clamp(y / G.h), col = 0.5 + 0.5 * noise(x * sc, 4.2), drip = 0.2 + 0.8 * col * col * col;
        return [noise(y * 0.03, x * 0.01, 7) * 5 * k, drop * k * drip * (0.15 + 0.85 * Math.pow(low, 1.6))];
      });
    }

    // ---- raster presets (TX.tiles groups) ----
    /** rows ripple sideways (under water, mirage, signal) */
    function ripple(G, from, to, o = {}) {
      const amp = E(o, 'amp', 10), len = E(o, 'length', 90), speed = E(o, 'speed', 1.4), fade = E(o, 'fade', 0.4);
      return warp(G, { from, to, axis: o.axis || 'x' }, (v, s) => {
        const env = smooth(s.lt / fade) * smooth((s.dur - s.lt) / fade);
        return amp * env * (Math.sin(TAU * (v / len - s.lt * speed)) + 0.35 * noise(v * 0.05, s.t * 2));
      });
    }
    /** the text crumbles into dust that drifts away (or gathers from dust: reverse) */
    function dissolve(G, at, o = {}) {
      const dur = E(o, 'dur', 1.6), sweep = E(o, 'sweep', 0.9), rise = E(o, 'rise', 120), wind = E(o, 'wind', 140), turb = E(o, 'turbulence', 50);
      const rev = !!o.reverse, ez = ease(o.ease || 'power2.in');
      const ord = order(G, o.order || 'x');
      return fx(G, { from: at, to: at + dur + sweep, fill: rev ? 'backwards' : 'forwards' }, (u, s, c) => {
        let k = clamp((s.lt - (ord[u.i] * 0.85 + u.r(1) * 0.15) * sweep) / dur);
        k = rev ? 1 - ease('power3.out')(k) : ez(k);
        if (k <= 0) return;
        c.x += wind * k * (0.5 + u.r(2)) + turb * noise(u.x * 0.02, u.y * 0.02, k * 3) * k;
        c.y += -rise * k * (0.4 + u.r(3)) + turb * noise(u.x * 0.02 + 9, u.y * 0.02, k * 3) * k;
        c.r += (u.r(4) - 0.5) * 240 * k;
        c.sx *= 1 - 0.6 * k; c.sy *= 1 - 0.6 * k;
        c.o *= 1 - smooth((k - 0.35) / 0.65);
      });
    }

    // the presets as called from scenes.js: their times (seconds or cue labels) resolved to seconds first
    const at1 = (fn) => (G, a, ...r) => fn(G, T(a), ...r);
    const at2 = (fn) => (G, a, b, ...r) => fn(G, T(a), T(b), ...r);
    return {
      // representations
      split, copies, glyphs, raster, tiles, motionBlur,
      // the open system: write your own effects with these
      fx, deform, warp, order, m: M, ease, stageXY, shardCells, bandCells, voronoi, shapes, at: T,
      // presets (examples)
      wave: at2(wave), jelly: at1(jelly), scatter: at1(scatter), assemble: at1(assemble), shatter: at1(shatter), glitch: at2(glitch),
      extrude, neon: at1(neon), breathe: at2(breathe), float: at2(float), tremble: at2(tremble), pop: at1(pop), drop: at1(drop),
      swirl: at1(swirl), magnet: at1(magnet), flip: at1(flip),
      drawOn: at1(drawOn), liquid: at2(liquid), shockwave: at1(shockwave), melt: at1(melt), ripple: at2(ripple), dissolve: at1(dissolve),
      groups,
    };
  }

  window.TypeFX = { install, m: M, version: '1.0.0' };
})();
