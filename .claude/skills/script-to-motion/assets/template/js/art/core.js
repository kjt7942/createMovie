/*
 * art/core.js — shared helpers for the illustration library (window.ART).
 * Every art module is deterministic: no Math.random, Date, timers. Procedural detail uses ART.rand(seed).
 * Modules register on window.ART and are built from js/scenes.js at define time.
 *
 * Module contract:
 *   ART.<name> = { build(el, opts) -> { animate(t, state) } }   // el: an existing <svg> or <g>; build fills it
 *   ART.<name>Symbol() -> id                                     // registers a <symbol> once (for <use href="#id">)
 * animate(t, state) must be a pure function of t (+ the state passed in): it may only set attributes/styles.
 */
(function () {
  const ART = (window.ART = window.ART || {});
  const NS = 'http://www.w3.org/2000/svg';
  ART.NS = NS;

  // deterministic PRNG (mulberry32) — same as the player's rand()
  ART.rand = function (seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let r = Math.imul(a ^ (a >>> 15), 1 | a);
      r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  };

  // shared <defs> host: gradients, filters and symbols are registered once per document
  ART.defs = function (id, markup) {
    let host = document.getElementById('art-defs');
    if (!host) {
      host = document.createElementNS(NS, 'svg');
      host.setAttribute('id', 'art-defs');
      host.setAttribute('width', '0');
      host.setAttribute('height', '0');
      host.setAttribute('aria-hidden', 'true');
      host.style.position = 'absolute';
      host.style.left = '0';
      host.style.top = '0';
      host.innerHTML = '<defs></defs>';
      document.body.insertBefore(host, document.body.firstChild);
    }
    if (!document.getElementById(id)) host.querySelector('defs').insertAdjacentHTML('beforeend', markup);
    return id;
  };

  ART.q = (root, sel) => root.querySelector(sel);
  ART.qa = (root, sel) => Array.from(root.querySelectorAll(sel));
  ART.f = (n, d = 1) => Number(n).toFixed(d);
  ART.clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  ART.lerp = (a, b, k) => a + (b - a) * k;
  // polyline → smooth closed/open path through points (Catmull-Rom → cubic Bézier)
  ART.smooth = function (pts, closed = false) {
    const n = pts.length;
    if (n < 2) return '';
    const P = (i) => pts[closed ? (i + n) % n : Math.max(0, Math.min(n - 1, i))];
    let d = `M${ART.f(pts[0][0])} ${ART.f(pts[0][1])}`;
    const last = closed ? n : n - 1;
    for (let i = 0; i < last; i++) {
      const p0 = P(i - 1), p1 = P(i), p2 = P(i + 1), p3 = P(i + 2);
      const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      d += ` C${ART.f(c1[0])} ${ART.f(c1[1])} ${ART.f(c2[0])} ${ART.f(c2[1])} ${ART.f(p2[0])} ${ART.f(p2[1])}`;
    }
    return d + (closed ? ' Z' : '');
  };
  ART.palette = { fg: '#eaf7ff', muted: '#8db2cf', accent: '#59f3e0', coral: '#ff7a45', sand: '#e8d6a8', abyss: '#01040c' };
})();
