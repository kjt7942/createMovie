/*
 * reckit.js — showing a screen recording (a web app, a demo) without zooming into it. references/footage.md.
 *
 *   const R = RecKit.install(ctx);
 *   const B = R.browser(parentEl, { x: 40, y: 58, w: 1840, src: [3840, 1750], url: 'example.com' })
 *        → { el, view, world, vw, vh, x, y, k, bar }   a browser window; `world` holds the recording (a MEDIA clip of
 *          src px scaled by k = vw / src[0]). The whole page always stays in view.
 *   const sp = R.spot(B)          the highlight: everything outside a hole over [sx, sy, sw, sh] (source px) is dimmed and one
 *                                 hand-drawn pen loop goes round it once. sp.on(at, rect) · sp.go(at, rect, dur) glides it
 *                                 (never redrawn) · sp.off(at) · sp.pt(rect, 'r'|'l'|'t'|'b') a stage point just outside
 *                                 the loop, where an arrow can end without touching it
 *   R.callout(parentEl, { x, y, w, html, at, out, from: sp.pt(rect) })   a paper label pinned up by hand in the dimmed
 *                                 area (.k kicker, .v value with a highlighter swept under it, .s small line) and a hand-drawn
 *                                 line from the spot to its near edge. Take `from` on the side facing the callout
 *                                 (sp.pt(rect, 'l') when the callout is left of the spot). Readability comes from the
 *                                 callout's large type, not a zoom.
 *   R.leader(parentEl, [[x0, y0], …, [x1, y1]], at, outAt)   the bowed felt-pen line + arrowhead alone (x0,y0 = the thing)
 *   R.link(parentEl, from, [x, y], at, outAt, edge)          the same line, elbowed, to an existing box's 'left' (default)
 *                                 or 'right' edge at stage (x, y)
 *   R.track(state) → to(at, dur, vals, ease)   keyframes on a plain object whose segments never overlap (a late keyframe
 *                                 starts when the previous one ends) — tween meaningful numbers, draw them in onFrame
 *   R.camera(worldEl, { x, y, s }, vw, vh) → { st, to }   a camera over a world div: st.x/st.y = world point at the centre of
 *                                 the vw × vh frame (default the stage, W × H); st.s = scale. Tween with to(at, dur, vals)
 *
 * Times (`at`, `out`, `outAt`) are seconds or cue labels ('fr07', 'fr07+=0.2', 'fr07_end-=0.4').
 * Every call schedules on ctx.tl and draws in onFrame from tweened state only (seek-safe). Wobble comes from
 * ctx.rand(seed) once per element, so every playback draws the same line. Styles: css/reckit.css.
 */
(function () {
  'use strict';
  const LOCK = '<svg viewBox="0 0 16 16"><rect x="3" y="7" width="10" height="7" rx="1.6"/><path d="M5.2 7V5.2a2.8 2.8 0 0 1 5.6 0V7"/></svg>';
  const LOOP_MX = 18, LOOP_MY = 16;   // the loop's margin round the hole (px) — matches .spot .loop in reckit.css
  const GAP = 16;                     // between the loop and an arrowhead pointing at it

  function install(ctx, { seed = 400 } = {}) {
    const { tl, onFrame, rand, stage } = ctx;
    let handSeed = seed;
    const px = (v) => (typeof v === 'number' ? v + 'px' : v);
    const el = (tag, cls, parent, style, html) => {
      const e = document.createElement(tag);
      if (cls) e.className = cls;
      if (style) Object.assign(e.style, style);
      if (html != null) e.innerHTML = html;
      if (parent) parent.appendChild(e);
      return e;
    };
    // a time: seconds or a cue label → seconds (offsets are added to it: 'fr07' + 0.3 would be an unknown label at the end)
    const T = (p) => {
      if (typeof p === 'number' || p == null) return p;
      const m = String(p).match(/^([\w-]+?)(?:([+-])=([\d.]+))?$/);
      if (!m || tl.labels[m[1]] == null) throw new Error(`RecKit: can't resolve time "${p}" — use seconds or a cue label`);
      return tl.labels[m[1]] + (m[2] ? (m[2] === '-' ? -1 : 1) * Number(m[3]) : 0);
    };
    const draw = (sel, pos, dur = 0.9, o = {}) =>
      tl.fromTo(sel, { drawSVG: '0%' }, Object.assign({ drawSVG: '100%', duration: dur, ease: 'power2.inOut', immediateRender: false }, o), pos);

    // the pen's roughness, shared by the loop, the leader lines and the highlighter
    const ROUGH = '<filter id="hand-rough" filterUnits="userSpaceOnUse" x="-400" y="-400" width="3000" height="2200">' +
      '<feTurbulence type="fractalNoise" baseFrequency="0.045" numOctaves="2" seed="7" result="n"/>' +
      '<feDisplacementMap in="SourceGraphic" in2="n" scale="5" xChannelSelector="R" yChannelSelector="G"/></filter>';
    if (window.ART && ART.defs) ART.defs('hand-rough', ROUGH);
    else if (!document.getElementById('hand-rough')) {
      const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      s.setAttribute('width', '0'); s.setAttribute('height', '0'); s.style.position = 'absolute';
      s.innerHTML = '<defs>' + ROUGH + '</defs>';
      (stage || document.body).appendChild(s);
    }

    function track(state) {
      let last = Object.assign({}, state), lastEnd = -1e9;
      return function to(at, dur, vals, ease = 'power2.inOut') {
        at = T(at);
        if (!(dur > 0)) return;
        const st = Math.max(at, lastEnd), du = Math.max(Math.min(dur, Math.max(0.35, dur * 0.75)), at + dur - st);
        const from = Object.assign({}, last), target = Object.assign({}, last, vals);
        tl.fromTo(state, from, Object.assign({}, target, { duration: du, ease, immediateRender: false }), st);
        last = target; lastEnd = st + du;
      };
    }

    function camera(worldEl, init = {}, vw = ctx.W || 1920, vh = ctx.H || 1080) {   // the frame: the stage (any aspect)
      const st = Object.assign({ x: vw / 2, y: vh / 2, s: 1 }, init);
      const to = track(st);
      worldEl.style.transformOrigin = '0 0';
      let last = '';
      onFrame(() => {
        const v = `translate(${vw / 2}px, ${vh / 2}px) scale(${st.s.toFixed(4)}) translate(${(-st.x).toFixed(2)}px, ${(-st.y).toFixed(2)}px)`;
        if (v !== last) { worldEl.style.transform = v; last = v; }
      });
      return { st, to };
    }

    function browser(parent, { x = 40, y = 58, w = 1840, src = [3840, 1750], url = '', bar = 50 } = {}) {
      const vw = w, vh = Math.round(w * src[1] / src[0]);
      const b = el('div', 'bw', parent, { left: px(x), top: px(y), width: px(vw), height: px(vh + bar) });
      const barEl = el('div', 'bw-bar', b, { height: px(bar) }, `<div class="bw-dots"><i></i><i></i><i></i></div>${url ? `<div class="bw-url">${LOCK}<span>${url}</span></div>` : ''}`);
      const view = el('div', 'bw-view', b, { top: px(bar), height: px(vh) });
      const world = el('div', 'bw-world', view, { width: px(vw), height: px(vh) });
      return { el: b, bar: bar, barEl, view, world, vw, vh, x, y, k: vw / src[0] };
    }

    // the loop: one closed pen line, a squircle with soft, slightly bowed sides; its wobble from rand once, the path rebuilt
    // in pixels from the hole's size every frame (the stroke never stretches)
    function loopShape() {
      const r = rand(++handSeed), j = (a) => (r() - 0.5) * 2 * a;
      const a0 = -Math.PI * 0.62 + j(0.2), K = 14;
      const pts = Array.from({ length: K }, (_, i) => {
        const th = a0 + (Math.PI * 2 * i) / K, c = Math.cos(th), sn = Math.sin(th), q = 0.62;
        return [0.5 + 0.5 * Math.sign(c) * Math.pow(Math.abs(c), q) * (1 + j(0.03)), 0.5 + 0.5 * Math.sign(sn) * Math.pow(Math.abs(sn), q) * (1 + j(0.04))];
      });
      return (W, H) => {
        const P = pts.map(([u, v]) => [u * W, v * H]), m = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2], f = (v) => v.toFixed(1);
        const s0 = m(P[K - 1], P[0]);
        let d = `M${f(s0[0])} ${f(s0[1])}`;
        for (let i = 0; i < K; i++) { const e = m(P[i], P[(i + 1) % K]); d += ` Q${f(P[i][0])} ${f(P[i][1])} ${f(e[0])} ${f(e[1])}`; }
        return d + 'Z';
      };
    }

    function spot(B, { pad = 12 } = {}) {
      const hole = el('div', 'spot', B.view, null, '<svg class="loop"><path/></svg>');
      const loop = hole.querySelector('.loop path'), shape = loopShape();
      const lp = { v: 0 }, lpTo = track(lp);
      const st = { x: B.vw / 2, y: B.vh / 2, w: 10, h: 10, o: 0 };
      const to = track(st);
      const R = ([sx, sy, sw, sh]) => ({ x: sx * B.k - pad, y: sy * B.k - pad, w: sw * B.k + 2 * pad, h: sh * B.k + 2 * pad });
      let last = '', lastD = '', len = 0, lastDash = '';
      onFrame(() => {
        const v = `${st.x.toFixed(1)}|${st.y.toFixed(1)}|${st.w.toFixed(1)}|${st.h.toFixed(1)}|${st.o.toFixed(3)}`;
        if (v !== last) {
          last = v;
          Object.assign(hole.style, { left: st.x.toFixed(1) + 'px', top: st.y.toFixed(1) + 'px', width: st.w.toFixed(1) + 'px', height: st.h.toFixed(1) + 'px',
            visibility: st.o > 0.002 ? 'inherit' : 'hidden' });
          hole.style.setProperty('--o', st.o.toFixed(3));
        }
        if (st.o <= 0.002) return;
        const d = shape(st.w + 2 * LOOP_MX, st.h + 2 * LOOP_MY);
        if (d !== lastD) { loop.setAttribute('d', d); lastD = d; len = loop.getTotalLength ? loop.getTotalLength() : 0; }
        const dash = lp.v >= 0.999 || !len ? 'none' : `${(len * lp.v).toFixed(1)} ${(len + 1).toFixed(1)}`;
        if (dash !== lastDash) { loop.style.strokeDasharray = dash; lastDash = dash; }
      });
      return {
        el: hole,
        on(at, rect, dur = 0.5) {
          at = T(at);
          to(at - 0.02, 0.01, R(rect)); to(at, dur, { o: 1 }, 'power2.out');
          lpTo(at + 0.05, 0.01, { v: 0 }, 'none'); lpTo(at + 0.06, 0.5, { v: 1 }, 'power2.inOut');
        },
        go(at, rect, dur = 0.6, ease = 'power3.inOut') { to(at, dur, R(rect), ease); },
        off(at, dur = 0.4) { to(at, dur, { o: 0 }, 'power2.in'); },
        pt(rect, side = 'r') {
          const r = R(rect), ox = B.x + r.x, oy = B.y + B.bar + r.y, gx = LOOP_MX + GAP, gy = LOOP_MY + GAP;
          return { r: [ox + r.w + gx, oy + r.h / 2], l: [ox - gx, oy + r.h / 2], t: [ox + r.w / 2, oy - gy], b: [ox + r.w / 2, oy + r.h + gy] }[side];
        },
      };
    }

    // a hand-drawn line from the callout to the thing: bowed, unsteady, one felt-pen line, a chunky arrowhead
    function leader(parent, pts, at, outAt, { cls = '' } = {}) {
      at = T(at); outAt = T(outAt);
      const [x0, y0] = pts[0], [x1, y1] = pts[pts.length - 1];
      const r = rand(++handSeed), dx = x0 - x1, dy = y0 - y1, len = Math.hypot(dx, dy) || 1, nx = -dy / len, ny = dx / len;
      const bow = (r() < 0.5 ? -1 : 1) * Math.min(80, len * 0.14);
      const N = 24, Q = [], ph = r() * 6, amp = 3.2;
      for (let i = 0; i <= N; i++) {
        const u = i / N, b = 4 * u * (1 - u) * bow, edge = Math.min(1, u * 6, (1 - u) * 6);
        const wob = (Math.sin(u * 7 + ph) * amp + Math.sin(u * 19 + ph * 2.3) * amp * 0.45) * edge;
        Q.push([x1 + dx * u + nx * (b + wob), y1 + dy * u + ny * (b + wob)]);
      }
      let d = `M${Q[0][0].toFixed(1)} ${Q[0][1].toFixed(1)}`;
      for (let i = 1; i < N; i++) {
        const mx = (Q[i][0] + Q[i + 1][0]) / 2, my = (Q[i][1] + Q[i + 1][1]) / 2;
        d += ` Q${Q[i][0].toFixed(1)} ${Q[i][1].toFixed(1)} ${mx.toFixed(1)} ${my.toFixed(1)}`;
      }
      d += ` L${Q[N][0].toFixed(1)} ${Q[N][1].toFixed(1)}`;
      const ang = Math.atan2(y0 - Q[21][1], x0 - Q[21][0]);
      const barb = (s1, l) => `${(x0 - l * Math.cos(ang + s1)).toFixed(1)} ${(y0 - l * Math.sin(ang + s1)).toFixed(1)}`;
      const head = `M${barb(-0.55 - r() * 0.12, 30 + r() * 6)} Q${(x0 - 6 * Math.cos(ang)).toFixed(1)} ${(y0 - 6 * Math.sin(ang)).toFixed(1)} ${x0.toFixed(1)} ${y0.toFixed(1)} L${barb(0.5 + r() * 0.12, 27 + r() * 6)}`;
      const W = ctx.W || 1920, H = ctx.H || 1080;
      const wrap = el('div', 'leader ' + cls, parent, { width: px(W), height: px(H) },
        `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}"><path class="ln" d="${d}"/><path class="hd" d="${head}"/></svg>`);
      const ln = wrap.querySelector('.ln'), hd = wrap.querySelector('.hd');
      gsap.set([ln, hd], { drawSVG: '0%' });
      draw(ln, at + 0.05, 0.45, { ease: 'power2.inOut' });
      draw(hd, at + 0.5, 0.18, { ease: 'power1.out' });
      if (outAt != null) tl.fromTo(wrap, { autoAlpha: 1 }, { autoAlpha: 0, duration: 0.3, ease: 'power2.in', immediateRender: false }, outAt);
      return wrap;
    }
    // edge: 'left' — the line arrives at a box edge from the left (the box is right of `from`), 'right' — from the right
    function link(parent, from, [x, y], at, outAt, edge = 'left') {
      const ex = edge === 'left' ? x - 4 : x + 4, dir = Math.sign(ex - from[0]) || 1;
      const mx = from[0] + dir * Math.max(40, Math.abs(ex - from[0]) * 0.45);
      return leader(parent, Math.abs(y - from[1]) < 2 ? [from, [ex, y]] : [from, [mx, from[1]], [mx, y], [ex, y]], at, outAt);
    }
    function callout(parent, { x, y, w, html, cls = '', at, out: outAt, from, ay = 46 }) {
      at = T(at); outAt = T(outAt);
      const c = el('div', 'co ' + cls, parent, { left: px(x), top: px(y) }, html);
      if (w) c.style.width = px(w);
      const rr = rand(++handSeed), rot = (rr() < 0.5 ? -1 : 1) * (0.8 + rr() * 0.9);   // pinned up by hand: never quite straight
      gsap.set(c, { autoAlpha: 0, rotation: rot });
      // the line ends on the callout's near edge: its left edge when the callout is right of the spot, else its right edge
      if (from) {
        const cwid = c.offsetWidth || w || 0;
        if (from[0] <= x + cwid / 2) link(parent, from, [x, y + ay], at, outAt, 'left');
        else link(parent, from, [x + cwid, y + ay], at, outAt, 'right');
      }
      tl.fromTo(c, { autoAlpha: 0, x: -24 }, { autoAlpha: 1, x: 0, duration: 0.55, ease: 'power3.out', immediateRender: false }, at + 0.3);
      const v = c.querySelector('.v');
      if (v) {
        el('i', 'hl', v);
        tl.fromTo(v, { '--hl': 0 }, { '--hl': 1, duration: 0.4, ease: 'power2.inOut', immediateRender: false }, at + 0.75);
      }
      if (outAt != null) tl.fromTo(c, { autoAlpha: 1, x: 0 }, { autoAlpha: 0, x: 16, duration: 0.3, ease: 'power2.in', immediateRender: false }, outAt);
      return c;
    }

    return { track, camera, browser, spot, leader, link, callout, el, px, at: T };
  }

  window.RecKit = { install };
})();
