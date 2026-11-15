/*
 * fxkit.js — reusable, seekable motion-graphics effects for script-to-motion projects.
 * Classic script (file:// safe). Enable it by adding, in index.html:
 *   <link rel="stylesheet" href="css/fxkit.css">           (after player.css)
 *   <script src="js/fxkit.js"></script>                    (after player.js, before scenes.js)
 * then inside Video.define:   const K = FXKit.install(ctx);   (ctx = the object Video.define passes)
 *
 * Everything is a function of the playhead: tweens go on ctx.tl, drawing happens in ctx.onFrame(t) from
 * closed-form formulas, randomness comes from ctx.rand(seed). No Math.random / Date / timers / rAF /
 * CSS transitions / display toggling. Transient effects are to→to pairs or fromTo(immediateRender:false),
 * which restore correctly when seeking in either direction. See references/fx-kit.md.
 */
(function () {
  'use strict';

  const TAU = Math.PI * 2;

  function install(ctx, opts) {
    const { tl, onFrame, rand, fitCanvas, stage, W, H } = ctx;
    const gs = ctx.gsap || window.gsap;
    const o = Object.assign({ zRings: 31, zCanvas: 32, zOver: 34, zFlash: 60, accent: '89,243,224' }, opts || {});
    const $ = (s) => (typeof s === 'string' ? stage.querySelector(s) || document.querySelector(s) : s);
    const $$ = (s) => (typeof s === 'string' ? Array.from(document.querySelectorAll(s)) : Array.isArray(s) ? s : [s]);
    const el = (tag, cls, parent, z) => {
      const d = document.createElement(tag);
      if (cls) d.className = cls;
      if (z != null) d.style.zIndex = z;
      if (parent) parent.appendChild(d);
      return d;
    };

    // ---------- layers (persistent, appended to #stage above the scenes) ----------
    const ringsBox = el('div', 'fxkit-layer', stage, o.zRings);
    const canvas = el('canvas', 'fxkit-canvas', stage, o.zCanvas);
    canvas.id = 'fxkit-canvas';
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    const overBox = el('div', 'fxkit-layer', stage, o.zOver);
    const fctx = fitCanvas(canvas);
    stage.style.setProperty('--fxkit-accent-rgb', o.accent);   // rings and sparks share one accent

    // ---------- sprites (pre-rendered once; null where the canvas can't, e.g. jsdom) ----------
    function sprite(rgb, size = 128) {
      const cv = document.createElement('canvas');
      cv.width = cv.height = size;
      const c = cv.getContext && cv.getContext('2d');
      if (!c || typeof c.createRadialGradient !== 'function') return null;
      const g = c.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
      if (!g || typeof g.addColorStop !== 'function') return null;
      g.addColorStop(0, `rgba(${rgb},1)`); g.addColorStop(0.55, `rgba(${rgb},.55)`); g.addColorStop(1, `rgba(${rgb},0)`);
      c.fillStyle = g;
      c.fillRect(0, 0, size, size);
      return cv;
    }
    const SP = { white: sprite('235,248,255'), accent: sprite(o.accent), orange: sprite('255,170,120'), dust: sprite('205,228,242') };

    // =====================================================================
    // DOM helpers
    // =====================================================================
    const NEUTRAL = { x: 0, y: 0, xPercent: 0, yPercent: 0, rotation: 0, scale: 1, scaleX: 1, scaleY: 1 };
    /** fade + move in from `from` to neutral */
    function inn(target, pos, from = { y: 40 }, dur = 0.8, ez = 'expo.out') {
      const to = { autoAlpha: 1, duration: dur, ease: ez };
      for (const k of Object.keys(from)) if (k in NEUTRAL) to[k] = NEUTRAL[k];
      return tl.fromTo(target, Object.assign({ autoAlpha: 0 }, from), to, pos);
    }
    /** fade + move out (faster than the entrance) */
    function out(target, pos, to = { y: -30 }, dur = 0.45, ez = 'power2.in') {
      return tl.to(target, Object.assign({ autoAlpha: 0 }, to, { duration: dur, ease: ez }), pos);
    }
    // a glow drawn with text-shadow is clipped per character by SplitText masks / overflow boxes and shows as
    // faint rectangles: move it to a filter: drop-shadow on the element (the filter shadows the clipped glyphs)
    function fixClippedGlow(node) {
      if (!node || !window.getComputedStyle) return;
      const ts = getComputedStyle(node).textShadow;
      if (!ts || ts === 'none') return;
      const m = ts.match(/(rgba?\([^)]*\)|#[0-9a-f]{3,8}|[a-z]+)\s+(-?[\d.]+)px\s+(-?[\d.]+)px\s+([\d.]+)px/i)
        || ts.match(/(-?[\d.]+)px\s+(-?[\d.]+)px\s+([\d.]+)px\s+(rgba?\([^)]*\)|#[0-9a-f]{3,8}|[a-z]+)/i);
      node.style.textShadow = 'none';
      if (!m) return;
      const colorFirst = /[a-z#(]/i.test(m[1]);
      const [c, x, y, b] = colorFirst ? [m[1], m[2], m[3], m[4]] : [m[4], m[1], m[2], m[3]];
      const prev = getComputedStyle(node).filter;
      node.style.filter = `${prev && prev !== 'none' ? prev + ' ' : ''}drop-shadow(${x}px ${y}px ${(+b * 0.4).toFixed(1)}px ${c})`;
    }
    /** kinetic type: split into chars behind a mask and rise in (glow is moved to drop-shadow automatically) */
    function chars(sel, pos, { stagger = 0.035, dur = 0.85, from = { yPercent: 115 }, mask = 'chars', type = 'words,chars' } = {}) {
      $$(sel).forEach((n) => { if (mask) fixClippedGlow(n); });
      const st = window.SplitText.create(sel, { type, mask: mask || undefined });
      tl.from(st.chars || st.words || st.lines, Object.assign({}, from, { duration: dur, ease: 'expo.out', stagger }), pos);
      return st;
    }
    /** full-frame flash (white by default) — keep peaks ≤ 0.35 and use it on 1–3 beats per minute */
    function flash(pos, { peak = 0.3, dur = 0.45, color = '#ffffff' } = {}) {
      pos = at(pos);
      const f = el('div', 'fxkit-flash', stage, o.zFlash);
      f.style.background = color;
      gs.set(f, { opacity: 0 });
      tl.to(f, { opacity: peak, duration: 0.05, ease: 'none' }, pos);
      tl.to(f, { opacity: 0, duration: dur, ease: 'power2.out' }, pos + 0.05);
      return f;
    }
    // ---------- offsets on the CSS `translate` property (independent of GSAP's x/y transforms) ----------
    // shakes and handheld drift are closed-form functions of t added here and written once per frame, so they
    // compose with any tween of x/y on the same element and look the same however the playhead got there.
    // (A relative tween `x: '+=10'` reads its base when first rendered — after a seek that base can be a different
    // moment of a moving camera, leaving the frame a few px off: snapshot.mjs --seekcheck finds it.)
    const OFFS = new Map();
    function addOffset(node, fn) {
      if (!OFFS.has(node)) OFFS.set(node, { fns: [], last: null });
      OFFS.get(node).fns.push(fn);
    }
    onFrame((t) => {
      for (const [node, rec] of OFFS) {
        let x = 0, y = 0;
        for (const fn of rec.fns) { const v = fn(t); if (v) { x += v[0]; y += v[1]; } }
        const s = Math.abs(x) < 0.01 && Math.abs(y) < 0.01 ? '' : `${x.toFixed(2)}px ${y.toFixed(2)}px`;
        if (s !== rec.last) { node.style.translate = s; rec.last = s; }
      }
    });
    /** timeline position (number, 'c03', 'c03+=0.2', 'c03_end-=0.4') → seconds. Every effect that adds offsets to its
     *  position resolves it first: 'c03' + 0.05 would be the string 'c030.05', an unknown label GSAP puts at the end */
    function at(pos) {
      if (typeof pos === 'number') return pos;
      const m = String(pos).match(/^([\w-]+?)(?:([+-])=([\d.]+))?$/);
      if (!m || tl.labels[m[1]] == null) throw new Error(`FXKit: can't resolve position "${pos}" — use seconds or a cue label`);
      return tl.labels[m[1]] + (m[2] ? (m[2] === '-' ? -1 : 1) * Number(m[3]) : 0);
    }
    let shakeSeed = 0;
    /** camera shake: a decaying wiggle on the CSS translate property — composes with any x/y tween, seek-exact */
    function shake(target, pos, { amp = 10, dur = 0.55, wiggles = 7, ratio = 0.6 } = {}) {
      const t0 = at(pos), seedK = ++shakeSeed;
      const ph1 = rand(911 + seedK)() * TAU, ph2 = rand(1733 + seedK)() * TAU;
      $$(target).forEach((node) => addOffset(node, (t) => {
        const p = (t - t0) / dur;
        if (p <= 0 || p >= 1) return null;
        const env = (1 - p) * (1 - p);
        return [amp * env * Math.sin(TAU * wiggles * p + ph1), amp * ratio * env * Math.sin(TAU * wiggles * 1.13 * p + ph2)];
      }));
    }
    /** slow push-in that keeps a hold alive */
    function drift(sel, from, to, s = 1.035) {
      from = at(from); to = at(to);
      return tl.fromTo(sel, { scale: 1 }, { scale: s, duration: Math.max(0.01, to - from), ease: 'none', immediateRender: false }, from);
    }
    /** text that updates every frame from obj[key] (only when the string changes) */
    function counter(node, obj, key, format = (v) => Math.round(v).toLocaleString('en-US')) {
      const n = $(node);
      let last = null;
      onFrame(() => { const s = format(obj[key]); if (s !== last) { n.textContent = s; last = s; } });
    }
    /**
     * mono kicker decodes in. Deterministic: GSAP's ScrambleText picks its random characters with Math.random,
     * so the same t shows different letters after each seek — this scramble is a pure function of t instead.
     */
    function kick(sel, pos, { dur = 0.75, chars: cs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', fps = 20 } = {}) {
      $$(sel).forEach((n, idx) => {
        const txt = n.textContent, len = txt.length, st = { p: 0 };
        tl.fromTo(n, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.12 }, pos);
        tl.fromTo(st, { p: 0 }, { p: 1, duration: dur, ease: 'none', immediateRender: false }, pos);
        let last = null;
        onFrame((t) => {
          let s;
          if (st.p >= 1) s = txt;
          else if (st.p <= 0) s = '';
          else {
            const shown = Math.min(len, Math.ceil(st.p * 1.6 * len));          // scrambled tail grows in…
            const fixed = Math.floor(Math.max(0, st.p - 0.15) / 0.85 * len);  // …and resolves left to right
            const frame = Math.floor(t * fps);
            s = '';
            for (let i = 0; i < shown; i++) {
              const ch = txt[i];
              if (i < fixed || ch === ' ' || ch === '·') { s += ch; continue; }
              let h = Math.imul(i + 1, 0x9e3779b1) ^ Math.imul(frame + 7 * idx + 1, 0x85ebca6b);
              h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d); h ^= h >>> 13;
              s += cs[(h >>> 0) % cs.length];
            }
          }
          if (s !== last) { n.textContent = s; last = s; }
        });
      });
    }
    /** label writes on left → right */
    function wipe(sel, pos, { dur = 0.65 } = {}) {
      return tl.fromTo(sel, { autoAlpha: 0, clipPath: 'inset(-30% 110% -30% -10%)' },
        { autoAlpha: 1, clipPath: 'inset(-30% -10% -30% -10%)', duration: dur, ease: 'power3.inOut' }, pos);
    }

    // =====================================================================
    // odometer: rolling digit columns. Glow → filter: drop-shadow on the wrapper (fxkit.css), never text-shadow.
    // =====================================================================
    function odometer(node, sample, { decimals = 0, mono = false } = {}) {
      const host = $(node);
      host.textContent = '';
      host.classList.add('fxkit-odo');
      if (mono) host.classList.add('fxkit-odo-mono');
      const cols = [], seps = [];
      let j = sample.replace(/\D/g, '').length - 1;
      for (const ch of sample) {
        if (/\d/.test(ch)) {
          const wrap = el('span', 'fxkit-od', host);
          const strip = el('span', 'fxkit-ods', wrap);
          strip.innerHTML = '01234567890'.split('').map((d) => `<i>${d}</i>`).join('');
          cols.push({ wrap, strip, j: j--, last: '', shown: null });
        } else {
          const s = el('span', 'fxkit-odsep', host);
          s.textContent = ch;
          seps.push({ s, left: cols[cols.length - 1], shown: null });
        }
      }
      const show = (n, on) => { n.style.width = on ? '' : '0px'; n.style.opacity = on ? '' : '0'; };
      return (v) => {
        const q = Math.round(Math.max(0, v) * Math.pow(10, decimals) * 1e4) / 1e4;
        const nd = Math.max(1 + decimals, Math.floor(Math.log10(Math.max(1, q))) + 1);
        for (const c of cols) {
          const P = Math.pow(10, c.j);
          let p;
          if (c.j === 0) p = q % 10;
          else {
            const rem = q % P, k = rem > P - 1 ? Math.min(1, rem - (P - 1)) : 0;   // carry only while all lower digits pass 9
            p = (Math.floor(q / P) % 10) + k * k * (3 - 2 * k);
          }
          const tr = `translateY(${(-p).toFixed(4)}em)`;
          if (tr !== c.last) { c.strip.style.transform = tr; c.last = tr; }
          const on = c.j < nd;
          if (on !== c.shown) { show(c.wrap, on); c.shown = on; }
        }
        for (const s of seps) {
          const on = !s.left || s.left.shown;
          if (on !== s.shown) { show(s.s, on); s.shown = on; }
        }
      };
    }
    /** odometer + tween: rolls `node` from `from` to `to` starting at pos */
    function rollTo(node, pos, { from = 0, to, dur = 1.2, ez = 'power3.out', sample, decimals = 0, mono = false } = {}) {
      const set = odometer(node, sample || to.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }), { decimals, mono });
      const v = { v: from };
      tl.fromTo(v, { v: from }, { v: to, duration: dur, ease: ez, immediateRender: false }, pos);
      onFrame(() => set(v.v));
      return v;
    }
    /** a light sweep across text: an overlay copy of the final text shows only inside a moving band */
    function glintOver(node, pos, { text, html, dur = 1.0 } = {}) {
      const host = $(node);
      if (!host) return null;
      pos = at(pos);
      if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
      const g = el('span', 'fxkit-glo', host);
      g.setAttribute('aria-hidden', 'true');
      g.setAttribute('data-fx-copy', '');   // a decorative copy of the text: snapshot.mjs doesn't count it as overlapping
      if (html != null) g.innerHTML = html; else g.textContent = text != null ? text : host.textContent;
      gs.set(g, { '--gx': '100%', opacity: 0 });
      tl.to(g, { opacity: 1, duration: 0.05 }, pos);
      tl.fromTo(g, { '--gx': '100%' }, { '--gx': '-30%', duration: dur, ease: 'power2.inOut', immediateRender: false }, pos);
      tl.to(g, { opacity: 0, duration: 0.05 }, pos + dur);
      return g;
    }

    // =====================================================================
    // rings, pings, the ping wipe
    // =====================================================================
    function ring(x, y, pos, { size = 6, dur = 1.1, color, width = 3, ez = 'expo.out', peak = 0.95, flat = false } = {}) {
      const r = el('div', 'fxkit-ring', ringsBox);
      r.style.borderWidth = width + 'px';
      if (color) r.style.borderColor = color;
      const sy = flat ? 0.28 : 1;
      gs.set(r, { x, y, scaleX: 0.05, scaleY: 0.05 * sy, opacity: 0 });
      tl.fromTo(r, { scaleX: 0.05, scaleY: 0.05 * sy, opacity: peak },
        { scaleX: size, scaleY: size * sy, opacity: 0, duration: dur, ease: ez, immediateRender: false }, pos);
      return r;
    }
    function ping(x, y, pos, opt = {}) {
      const n = opt.n || 2, gap = opt.gap || 0.2;
      pos = at(pos);
      for (let i = 0; i < n; i++) ring(x, y, pos + i * gap, opt);
    }
    /** reveal `sel` (a scene) through an expanding sonar circle; schedule scene(sel, pos, …) with the same pos */
    function pingWipe(sel, x, y, pos, { dur = 0.95, color, sparks = true, rgb } = {}) {
      const R = Math.hypot(Math.max(x, W - x), Math.max(y, H - y)) + 40;
      pos = at(pos);
      tl.fromTo(sel, { clipPath: `circle(0px at ${x}px ${y}px)` },
        { clipPath: `circle(${R.toFixed(0)}px at ${x}px ${y}px)`, duration: dur, ease: 'power2.inOut', immediateRender: false }, pos);
      tl.set(sel, { clipPath: 'none' }, pos + dur + 0.01);
      ring(x, y, pos, { size: R / 100, dur, ez: 'power2.inOut', width: 5, color, peak: 1 });
      ring(x, y, pos + 0.12, { size: R / 100, dur, ez: 'power2.inOut', width: 2, color, peak: 0.6 });
      if (sparks) {
        const c = rgb || o.accent;
        burst(x, y, pos + 0.05, { n: 80, speed: R * 1.15, drag: 1.4, life: 0.85, size: 2.6, color: c });
        burst(x, y, pos + 0.02, { kind: 'warp', n: 36, speed: R * 0.8, drag: 1.2, life: 0.6, size: 2, color: c });
      }
    }

    // =====================================================================
    // particle bursts (closed form: position = f(t − t0), so any seek is exact)
    // =====================================================================
    const BURSTS = [];
    let seed = 7919;
    /**
     * kind: 'spark' (default) | 'ember' (flickering, light) | 'bubble' | 'dust' (soft clouds) | 'debris' (spinning chips)
     *       | 'converge' (gathers into x,y) | 'warp' (radial speed lines)
     */
    function burst(x, y, t0, b = {}) {
      t0 = at(t0);   // drawn in closed form of t − t0: a label must become seconds
      const n = b.n || 20, life = b.life || 1.0, r = rand(b.seed || (seed += 7));
      const dir = b.dir == null ? -Math.PI / 2 : b.dir, spread = b.spread == null ? TAU : b.spread;
      const speed = b.speed == null ? 260 : b.speed, area = b.area || 0, areaY = b.areaY == null ? area : b.areaY;
      const ps = [];
      for (let i = 0; i < n; i++) {
        const a = dir + (r() - 0.5) * spread, sp = speed * (0.35 + r() * 0.65);
        ps.push({ vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: life * (0.55 + r() * 0.45), sz: (b.size || 3) * (0.5 + r()), ph: r() * TAU,
          dx: (r() - 0.5) * area, dy: (r() - 0.5) * areaY, d: (b.delay || 0) * r() });
      }
      const rec = { x, y, t0, kind: b.kind || 'spark', ps, g: b.g || 0, drag: b.drag == null ? 2.2 : b.drag, color: b.color || o.accent,
        end: t0 + life + (b.delay || 0) + 0.05 };
      BURSTS.push(rec);
      return rec;
    }

    // =====================================================================
    // lens flares — only for light sources a camera lens would see (sun in the sky, a lamp facing camera)
    // =====================================================================
    const FLARES = [];
    /** returns { k } — tween k (0..1) on tl; x/y may be numbers or functions of t */
    function flareSource({ x, y, len = 1000, tint = 'accent' } = {}) {
      const f = { k: 0, x, y, len, tint };
      FLARES.push(f);
      return f;
    }
    /** one-shot flare at a fixed point: rises to `peak`, holds, fades */
    function flare(x, y, pos, { peak = 0.9, hold = 0.4, dur = 0.8, len = 1000 } = {}) {
      pos = at(pos);
      const f = flareSource({ x, y, len });
      tl.to(f, { k: peak, duration: 0.15, ease: 'power2.out' }, pos);
      tl.to(f, { k: 0, duration: dur, ease: 'power2.in' }, pos + 0.15 + hold);
      return f;
    }
    function drawFlare(x, y, a, len, tint) {
      const main = SP.white, ghost = SP[tint] || SP.accent;
      if (a < 0.01 || !main) return;
      fctx.globalCompositeOperation = 'lighter';
      fctx.globalAlpha = Math.min(1, 0.6 * a); fctx.drawImage(main, x - 90, y - 90, 180, 180);
      fctx.globalAlpha = Math.min(1, 0.5 * a); fctx.drawImage(main, x - len / 2, y - 7, len, 14);
      fctx.globalAlpha = Math.min(1, 0.25 * a); fctx.drawImage(main, x - 8, y - 160, 16, 320);
      const vx = W / 2 - x, vy = H / 2 - y;
      [[0.45, 22, ghost], [0.8, 12, main], [1.25, 46, ghost], [1.6, 18, SP.orange], [1.9, 30, main]].forEach(([k, r, g]) => {
        if (!g) return;
        fctx.globalAlpha = Math.min(1, 0.13 * a);
        fctx.drawImage(g, x + vx * k - r, y + vy * k - r, r * 2, r * 2);
      });
      fctx.globalAlpha = 1;
      fctx.globalCompositeOperation = 'source-over';
    }

    // ---------- the renderer: clears only when something was drawn, skips idle frames ----------
    let dirty = false;
    onFrame((t) => {
      const active = BURSTS.filter((b) => t >= b.t0 && t <= b.end);
      const lit = FLARES.filter((f) => f.k > 0.01);
      if (!active.length && !lit.length) {
        if (dirty) { fctx.clearRect(0, 0, W, H); dirty = false; }
        return;
      }
      dirty = true;
      fctx.clearRect(0, 0, W, H);
      for (const b of active) drawBurst(b, t);
      fctx.globalCompositeOperation = 'source-over';
      fctx.globalAlpha = 1;
      for (const f of lit) {
        const x = typeof f.x === 'function' ? f.x(t) : f.x, y = typeof f.y === 'function' ? f.y(t) : f.y;
        drawFlare(x, y, f.k, f.len, f.tint);
      }
    });
    function drawBurst(b, t) {
      for (const p of b.ps) {
        const a = t - b.t0 - p.d;
        if (a < 0 || a > p.life) continue;
        const u = a / p.life, k = b.drag;
        const f = k ? (1 - Math.exp(-k * a)) / k : a;
        let x = b.x + p.dx + p.vx * f, y = b.y + p.dy + p.vy * f + 0.5 * b.g * a * a;
        if (b.kind === 'spark' || b.kind === 'ember') {
          fctx.globalCompositeOperation = 'lighter';
          const fl = b.kind === 'ember' ? 0.6 + 0.4 * Math.sin(a * 22 + p.ph) : 1;
          const al = Math.pow(1 - u, 1.4) * fl;
          fctx.strokeStyle = fctx.fillStyle = `rgba(${b.color},${al.toFixed(3)})`;
          const e = Math.exp(-k * a), ivx = p.vx * e, ivy = p.vy * e + b.g * a;
          fctx.lineWidth = Math.max(1, p.sz * 0.7);
          fctx.beginPath(); fctx.moveTo(x, y); fctx.lineTo(x - ivx * 0.035, y - ivy * 0.035); fctx.stroke();
          const rr = p.sz * (1 - u * 0.6);
          fctx.fillRect(x - rr, y - rr, rr * 2, rr * 2);
        } else if (b.kind === 'bubble') {
          fctx.globalCompositeOperation = 'source-over';
          x += 5 * Math.sin(a * 7 + p.ph);
          const al = Math.min(1, u * 6) * Math.pow(1 - u, 0.7) * 0.9, rr = p.sz * (1 + 0.25 * u);
          if (window.ART && window.ART.drawBubble) window.ART.drawBubble(fctx, x, y, rr, al);
          else {
            fctx.strokeStyle = `rgba(225,248,255,${al.toFixed(3)})`; fctx.lineWidth = 1.6;
            fctx.beginPath(); fctx.arc(x, y, rr, 0, TAU); fctx.stroke();
            fctx.fillStyle = `rgba(255,255,255,${(al * 0.8).toFixed(3)})`;
            fctx.beginPath(); fctx.arc(x - rr * 0.35, y - rr * 0.35, rr * 0.28, 0, TAU); fctx.fill();
          }
        } else if (b.kind === 'dust') {
          if (!SP.dust) continue;
          fctx.globalCompositeOperation = 'source-over';
          const rr = p.sz * (1 + 2.5 * u);
          fctx.globalAlpha = 0.42 * (1 - u) * Math.min(1, u * 5);
          fctx.drawImage(SP.dust, x - rr, y - rr, rr * 2, rr * 2);
          fctx.globalAlpha = 1;
        } else if (b.kind === 'debris') {
          fctx.globalCompositeOperation = 'source-over';
          fctx.fillStyle = `rgba(${b.color},${(1 - Math.pow(u, 3)).toFixed(3)})`;
          fctx.save(); fctx.translate(x, y); fctx.rotate(p.ph + a * 7);
          fctx.fillRect(-p.sz, -p.sz * 0.6, p.sz * 2, p.sz * 1.2); fctx.restore();
        } else if (b.kind === 'warp') {
          fctx.globalCompositeOperation = 'lighter';
          const ang = Math.atan2(p.vy, p.vx), sp = Math.hypot(p.vx, p.vy), rr = 40 + sp * f, L = 50 + rr * 0.28;
          const al = Math.pow(1 - u, 1.2) * Math.min(1, u * 8);
          fctx.strokeStyle = `rgba(${b.color},${al.toFixed(3)})`;
          fctx.lineWidth = p.sz;
          const cx = Math.cos(ang), cy = Math.sin(ang);
          fctx.beginPath(); fctx.moveTo(b.x + cx * (rr - L), b.y + cy * (rr - L)); fctx.lineTo(b.x + cx * rr, b.y + cy * rr); fctx.stroke();
        } else if (b.kind === 'converge') {
          fctx.globalCompositeOperation = 'lighter';
          const e = u * u * (3 - 2 * u);
          x = b.x + p.dx * (1 - e); y = b.y + p.dy * (1 - e);
          const al = Math.min(1, u * 4) * (1 - Math.pow(u, 6));
          fctx.strokeStyle = fctx.fillStyle = `rgba(${b.color},${al.toFixed(3)})`;
          fctx.lineWidth = Math.max(1, p.sz * 0.6);
          fctx.beginPath(); fctx.moveTo(x, y); fctx.lineTo(x + p.dx * 0.06 * (1 - u), y + p.dy * 0.06 * (1 - u)); fctx.stroke();
          fctx.fillRect(x - p.sz / 2, y - p.sz / 2, p.sz, p.sz);
        }
      }
    }

    // =====================================================================
    // SFX words, light leaks, punch zoom, handheld drift
    // =====================================================================
    /** outlined comic word (쿵!, 콩!) popping at x,y */
    function sfx(text, x, y, pos, { rot = -8, color, size = 0, dur = 0.9 } = {}) {
      pos = at(pos);
      const w = el('div', 'fxkit-sfx', overBox);
      w.textContent = text;
      if (color) w.style.color = color;
      if (size) w.style.fontSize = size + 'px';
      gs.set(w, { x, y, xPercent: -50, yPercent: -50, rotation: rot, autoAlpha: 0, scale: 0.3 });
      tl.to(w, { autoAlpha: 1, scale: 1.18, duration: 0.12, ease: 'power2.out' }, pos);
      tl.to(w, { scale: 1, duration: 0.3, ease: 'back.out(3)' }, pos + 0.12);
      tl.to(w, { autoAlpha: 0, y: y - 50, duration: 0.35, ease: 'power2.in' }, pos + dur);
      return w;
    }
    /** a soft light leak sweeping across the frame (scene changes, reveals) */
    function leak(pos, { warm = false, from = -900, to = 900, y = 0, dur = 1.1, peak = 0.6 } = {}) {
      pos = at(pos);
      const l = el('div', 'fxkit-leak' + (warm ? ' warm' : ''), overBox);
      gs.set(l, { x: from, y, opacity: 0 });
      tl.to(l, { x: to, duration: dur, ease: 'power1.inOut' }, pos);
      tl.to(l, { opacity: peak, duration: dur * 0.4, ease: 'power2.out' }, pos);
      tl.to(l, { opacity: 0, duration: dur * 0.6, ease: 'power2.in' }, pos + dur * 0.4);
      return l;
    }
    // punch-zoom scales every scene through the CSS `scale` property (independent of GSAP transforms)
    const PUNCH = { v: 0 };
    const scenes = () => Array.from(stage.querySelectorAll(':scope > .scene'));
    let lastPunch = '', punchUsed = false;
    function punch(pos, amt = 0.035) {
      pos = at(pos);
      if (!punchUsed) {
        punchUsed = true;
        const list = scenes();
        onFrame(() => {
          const s = (1 + PUNCH.v).toFixed(4);
          if (s === lastPunch) return;
          lastPunch = s;
          list.forEach((n) => { n.style.scale = s; });
        });
      }
      tl.to(PUNCH, { v: amt, duration: 0.07, ease: 'power2.out' }, pos);
      tl.to(PUNCH, { v: 0, duration: 0.5, ease: 'power3.out' }, pos + 0.07);
    }
    /** gentle handheld drift on every scene (CSS `translate`, independent of GSAP transforms; adds to shakes) */
    function handheld({ amp = 4, skip = [] } = {}) {
      scenes().filter((n) => !skip.includes('#' + n.id)).forEach((n, i) => addOffset(n, (t) =>
        [amp * Math.sin(t * 0.5 + i), amp * 0.75 * Math.sin(t * 0.7 + i * 2)]));
    }

    return { inn, out, chars, flash, shake, addOffset, at, drift, counter, kick, wipe, odometer, rollTo, glintOver, fixClippedGlow,
      ring, ping, pingWipe, burst, flareSource, flare, sfx, leak, punch, handheld, sprite, canvas };
  }

  window.FXKit = { install, version: '1.0.0' };
})();
