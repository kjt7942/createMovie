#!/usr/bin/env node
/**
 * smoke.mjs — run a project headlessly in jsdom and report what is on screen over time.
 *
 *   node smoke.mjs <projectDir> [--step 0.5]
 *
 * You can't watch the video, so this is how you see it: it boots the real player + scenes.js,
 * surfaces runtime errors (ReferenceError, missing targets, GSAP warnings), then seeks through
 * the timeline and prints which scenes are visible and what text they show at each cue — and
 * flags empty frames and scenes that never appear.
 *
 * jsdom has no layout engine: positions, sizes, masks and canvas pixels are NOT checked.
 * First run needs: npm install --prefix <skill>/scripts   (installs jsdom)
 */
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

let JSDOM, VirtualConsole;
try {
  ({ JSDOM, VirtualConsole } = await import('jsdom'));
} catch {
  const here = path.dirname(fileURLToPath(import.meta.url));
  console.error(`jsdom is not installed. Run once:\n  npm install --prefix ${here}`);
  process.exit(3);
}

const argv = process.argv.slice(2);
const dir = path.resolve(argv.find((a) => !a.startsWith('--')) || '.');
const stepArg = argv.indexOf('--step');
const step = stepArg >= 0 ? Number(argv[stepArg + 1]) : 0.5;
if (!fs.existsSync(path.join(dir, 'index.html'))) {
  console.error(`no index.html in ${dir}`);
  process.exit(2);
}

const indexHtml = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
const uses3D = indexHtml.includes('vendor/three/stage3d.js') || indexHtml.includes('vendor/three/stagefx.js');
// jsdom has no WebGL: a 3D layer is replaced by an inert stand-in that absorbs every call.
// Check the 3D picture itself with snapshot.mjs (real Chromium).
const inert = new Proxy(function () {}, {
  get: (_, k) => (k === 'then' ? undefined : k === Symbol.toPrimitive ? () => 0 : k === Symbol.iterator ? [][Symbol.iterator].bind([]) : inert),
  apply: () => inert,
  construct: () => inert,
  set: () => true,
});
const problems = [];
const vc = new VirtualConsole();
const note = (kind) => (...a) => problems.push(`${kind}: ${a.map((x) => (x && x.stack) || String(x)).join(' ')}`);
vc.on('error', note('console.error'));
vc.on('warn', note('console.warn'));
vc.on('jsdomError', (e) => {
  if (/Could not parse CSS stylesheet|Not implemented: HTMLCanvasElement/.test(e.message)) return;
  problems.push(`runtime error: ${e.message}${e.detail ? ' — ' + (e.detail.stack || e.detail) : ''}`);
});

const dom = await JSDOM.fromFile(path.join(dir, 'index.html'), {
  runScripts: 'dangerously',
  resources: 'usable',
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(w) {
    const M = w.HTMLMediaElement.prototype;
    M.play = () => Promise.resolve();
    M.pause = () => {};
    M.load = () => {};
    Object.defineProperty(M, 'readyState', { get: () => 4 });
    const noop = () => {};
    // a 2D context that accepts every call; methods that return objects return inert ones, so code that is
    // valid in a browser (gradients, patterns, ImageData, transforms) never fails here
    const gradient = () => ({ addColorStop: noop });
    const imageData = (a, b) => {
      const wd = typeof a === 'object' && a ? a.width : Math.max(1, a | 0), ht = typeof a === 'object' && a ? a.height : Math.max(1, b | 0);
      return { width: wd, height: ht, data: new Uint8ClampedArray(wd * ht * 4) };
    };
    const returns = {
      measureText: () => ({ width: 0, actualBoundingBoxAscent: 0, actualBoundingBoxDescent: 0 }),
      createLinearGradient: gradient, createRadialGradient: gradient, createConicGradient: gradient,
      createPattern: () => ({ setTransform: noop }),
      createImageData: imageData, getImageData: (x, y, wd, ht) => imageData(wd, ht),
      getTransform: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0, invertSelf() { return this; } }),
      isPointInPath: () => false, isPointInStroke: () => false, getLineDash: () => [],
    };
    const ctx2d = new Proxy({}, {
      get: (_, k) => (k in returns ? returns[k] : k === 'canvas' ? w.document.createElement('canvas') : noop),
      set: () => true,
    });
    w.HTMLCanvasElement.prototype.getContext = () => ctx2d;
    // canvas companions jsdom lacks: Path2D, ImageData, OffscreenCanvas, createImageBitmap
    if (!w.Path2D) {
      w.Path2D = function Path2D() {};
      for (const m of ['addPath', 'closePath', 'moveTo', 'lineTo', 'bezierCurveTo', 'quadraticCurveTo', 'arc', 'arcTo', 'ellipse', 'rect', 'roundRect']) w.Path2D.prototype[m] = noop;
    }
    if (!w.ImageData) w.ImageData = function ImageData(a, b, c) { const d = imageData(a && a.length ? b : a, a && a.length ? c : b); if (a && a.length) d.data = a; return d; };
    if (!w.OffscreenCanvas) w.OffscreenCanvas = function OffscreenCanvas(wd, ht) { this.width = wd; this.height = ht; this.getContext = () => ctx2d; };
    if (!w.createImageBitmap) w.createImageBitmap = () => Promise.resolve({ width: 1, height: 1, close: noop });
    Object.defineProperty(w.document, 'fonts', { value: { ready: Promise.resolve(), load: () => Promise.resolve([]) } });
    if (uses3D) {
      const stub = { create: () => inert, loadGLB: () => Promise.resolve(inert), mixer: () => inert, byName: () => inert };
      const fxStub = { ...stub, create: () => Promise.resolve(inert) };   // StageFX.create is async
      Object.defineProperty(w, 'THREE', { get: () => inert, set: () => {} });
      Object.defineProperty(w, 'Stage3D', { get: () => stub, set: () => {} });
      Object.defineProperty(w, 'StageFX', { get: () => fxStub, set: () => {} });
    }
    // jsdom has no SVG geometry; plausible stubs let DrawSVG/MorphSVG/MotionPath initialise
    const matrix = () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0, multiply() { return this; }, inverse() { return this; },
      translate() { return this; }, scale() { return this; } });
    const point = () => ({ x: 0, y: 0, matrixTransform() { return this; } });
    const SVG = w.SVGElement.prototype;
    SVG.getBBox = () => ({ x: 0, y: 0, width: 100, height: 100 });
    SVG.getCTM = matrix;
    SVG.getScreenCTM = matrix;
    SVG.getTotalLength = () => 1000;
    SVG.getPointAtLength = point;
    SVG.createSVGMatrix = matrix;
    SVG.createSVGPoint = point;
    SVG.createSVGTransform = () => ({ setMatrix() {}, matrix: matrix() });
    // GSAP reads transform.baseVal.consolidate().matrix whenever an SVG element has a transform attribute
    const parseTransform = (str) => {
      const m = matrix();
      const nums = (str || '').match(/-?[\d.]+(?:e-?\d+)?/gi)?.map(Number) || [];
      if (/^\s*matrix\(/.test(str || '') && nums.length >= 6) [m.a, m.b, m.c, m.d, m.e, m.f] = nums;
      else if (/^\s*translate\(/.test(str || '')) [m.e, m.f] = [nums[0] || 0, nums[1] || 0];
      return m;
    };
    Object.defineProperty(SVG, 'transform', {
      get() {
        const el = this;
        return { baseVal: { get numberOfItems() { return el.getAttribute('transform') ? 1 : 0; },
          consolidate: () => (el.getAttribute('transform') ? { matrix: parseTransform(el.getAttribute('transform')) } : null),
          initialize: () => {}, appendItem: () => {} } };
      },
    });
  },
});
const w = dom.window;
const doc = w.document;

// wait for the player to boot (or fail)
const t0 = Date.now();
while (!doc.body.classList.contains('vp-ready') && !doc.querySelector('.vp-error') && Date.now() - t0 < 15000) {
  await new Promise((r) => setTimeout(r, 50));
}
const bootError = doc.querySelector('.vp-error');
if (bootError || !w.__video || !doc.body.classList.contains('vp-ready')) {
  console.log('✖ player did not boot' + (bootError ? `: ${bootError.textContent}` : ' (timeout)'));
  for (const p of problems) console.log('  ' + p);
  process.exit(1);
}

const v = w.__video;
const data = w.VIDEO_DATA;
const seekErrors = new Map();
function seekTo(t) {
  try {
    v.seek(t);
  } catch (e) {
    const key = e.message;
    if (!seekErrors.has(key)) seekErrors.set(key, { t, stack: String(e.stack || e).split('\n').slice(0, 3).join(' ⟵ ') });
  }
}
const stage = doc.getElementById('stage');
const scenes = [...stage.querySelectorAll(':scope > .scene')];

// pushed fully out of a clipping parent (SplitText masks: yPercent ±110 inside overflow:clip)
function maskedOut(n) {
  const m = /translate(?:3d)?\(\s*([-\d.]+)(%|px)?\s*,\s*([-\d.]+)%/.exec(n.style.transform || '');
  if (!m) return false;
  const p = n.parentElement;
  const ov = p && (p.style.overflow || w.getComputedStyle(p).overflow);
  return /clip|hidden/.test(ov || '') && (Math.abs(parseFloat(m[3])) >= 99 || (m[2] === '%' && Math.abs(parseFloat(m[1])) >= 99));
}
function shown(el) {
  for (let n = el; n && n !== stage; n = n.parentElement) {
    const cs = w.getComputedStyle(n);
    if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    const op = parseFloat(n.style.opacity !== '' ? n.style.opacity : cs.opacity);
    if (!Number.isNaN(op) && op < 0.02) return false;
    if (maskedOut(n)) return false;
  }
  return true;
}
function visibleText(root) {
  const out = [];
  const walk = (n) => {
    if (n.nodeType === 3) {
      out.push(n.textContent.replace(/\s+/g, ' '));
      return;
    }
    if (n.nodeType !== 1 || !shown(n)) return;
    if (n.tagName === 'BR') return out.push(' ');
    const inline = /^inline/.test(n.style.display) || /^(SPAN|EM|STRONG|B|I|SUP|SUB|MARK|SMALL|A)$/.test(n.tagName);
    for (const c of n.childNodes) walk(c);
    if (!inline) out.push(' ');
  };
  walk(root);
  return out.join('').replace(/\s+/g, ' ').trim();
}
const clip = (s, n = 70) => (s.length > n ? s.slice(0, n - 1) + '…' : s);

console.log(`✓ booted · video ${v.duration.toFixed(2)}s · ${data.cues.length} cues · ${scenes.length} scenes${data.placeholder ? ' · PLACEHOLDER narration' : ''}`);
if (uses3D) console.log('  (3D layer stubbed — jsdom has no WebGL; check the 3D picture with snapshot.mjs)');
console.log('');

// what is on screen at the heart of every cue
const everShown = new Set();
for (const c of data.cues) {
  const at = Math.min(c.end, c.start + Math.max(0.6, c.duration * 0.6));
  seekTo(at);
  const vis = scenes.filter(shown);
  vis.forEach((s) => everShown.add(s));
  const label = vis.length ? vis.map((s) => '#' + (s.id || '?')).join(' + ') : '(no scene)';
  const text = vis.map(visibleText).filter(Boolean).join(' | ');
  console.log(`${c.id.padEnd(6)} t=${at.toFixed(2).padStart(6)}  ${label.padEnd(14)} ${clip(text || '—')}`);
  console.log(`${''.padEnd(6)} ${''.padStart(8)}  🎙 ${clip(c.text)}`);
}

// sweep the whole timeline for empty frames
const empty = [];
for (let t = 0; t <= v.duration + 1e-6; t += step) {
  seekTo(t);
  const vis = scenes.filter(shown);
  vis.forEach((s) => everShown.add(s));
  if (!vis.length) empty.push(t);
}
console.log('');
if (empty.length) {
  const ranges = [];
  for (const t of empty) {
    const last = ranges[ranges.length - 1];
    if (last && t - last[1] <= step + 1e-6) last[1] = t;
    else ranges.push([t, t]);
  }
  const long = ranges.filter(([a, b]) => b - a >= 0.75 || (a === 0 && b === 0));
  if (long.length) {
    console.log(`⚠ no scene visible (only persistent layers, if any) at: ${long.map(([a, b]) => (a === b ? `${a.toFixed(1)}s` : `${a.toFixed(1)}–${b.toFixed(1)}s`)).join(', ')}`);
  }
}
const never = scenes.filter((s) => !everShown.has(s));
if (never.length) console.log(`⚠ scenes never visible: ${never.map((s) => '#' + s.id).join(', ')}`);

for (const [msg, { t, stack }] of seekErrors) problems.push(`runtime error while rendering t=${t.toFixed(2)}: ${msg} (${stack})`);
const seen = new Set();
const unique = problems.filter((p) => (seen.has(p) ? false : seen.add(p)));
for (const p of unique) console.log('✖ ' + clip(p, 400));
if (!never.length && !unique.length) console.log('✓ no runtime errors, every scene appears');
w.close();
process.exit(unique.some((p) => p.startsWith('runtime error') || p.startsWith('console.error')) ? 1 : 0);
