#!/usr/bin/env node
/**
 * snapshot.mjs — automatic checks on the real page in headless Chromium: layout warnings, seek determinism, unsafe
 * margins, playback cost. It MEASURES; it writes no picture of the video. The picture is looked at only through
 * `python3 <dir>/render.py <dir> --screenshot …` — for every warning it prints the render.py command for that moment.
 *
 *   node snapshot.mjs <projectDir> [what] [options]
 *
 * what (default: t≈0.3, one frame 65% into every cue, the last frame)
 *   --times 3.2,7.6,…     exact times (seconds)
 *   --cues c03,c08        start / middle / end of these cues
 *   --range 7.0:8.4       a filmstrip of consecutive frames (with --step, default 0.1 s) — for motion
 *   --overview            the whole video, one thumbnail every --every seconds (default 2) — rhythm, variety
 * options
 *   --crop x,y,w,h        compare only this stage rectangle (stage px) in --seekcheck
 *   --scale 2             device scale for the --seekcheck comparison
 *   --out dir             where report.json goes (default <project>/.snapshots); images an older version left there are
 *                         deleted (it no longer writes any)
 *   --perf               JavaScript time per frame during playback (sequential 1/30 s steps around each shot —
 *                         what the recording sees; keep it well under ~8 ms) plus random-seek cost (informational)
 *   --captions            shoot with the player's captions on (one-line segments)
 *   --safezone            draw the project's unsafe margins on the frames (css/style.css --safe-top/-bottom/-right/--safe;
 *                         in 9:16 the areas Shorts / Reels / TikTok cover with their UI) and warn on text inside them
 *   --seekcheck           determinism: after shooting forward, seek to every shot again — in reverse order, then in a
 *                         fixed shuffled order (seeded: --seed 1) — and compare the picture (a hash of the screenshot)
 *                         plus the stage's computed state for the explanation (DOM properties, every canvas's
 *                         pixels) — anything that depends on what was played before or on the seek path
 *                         (accumulated state, Math.random, caches) shows up as a mismatch
 *
 * Writes report.json (every checked time with its cue, the words being spoken then, its warnings) and prints the
 * console errors and layout problems measured by the browser (text overlapping text, text clipped by a container or
 * the edge, and glows clipped into boxes: a text-shadow cut by a SplitText mask / overflow / clip-path / mask
 * ancestor, which shows as faint rectangles behind the letters — player-api.md §4), each with the render.py command
 * that shows that moment. --seekcheck prints, for every frame that differs, the render.py --via command that films it
 * both ways with the difference marked.
 *
 * Needs a browser: run setup_browser.mjs once (it records ~/.cache/motion-video-deps/browser.json).
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { pathToFileURL, fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
let chromium;
try {
  ({ chromium } = await import('playwright-core'));
} catch {
  console.error(`playwright-core is not installed. Run once:\n  node ${path.join(here, 'setup_browser.mjs')}`);
  process.exit(3);
}

// ---------- args ----------
const argv = process.argv.slice(2);
const opt = { _: [] };
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith('--')) opt[argv[i].slice(2)] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  else opt._.push(argv[i]);
}
const dir = path.resolve(opt._[0] || '.');
const indexHtml = path.join(dir, 'index.html');
if (!fs.existsSync(indexHtml)) { console.error(`no index.html in ${dir}`); process.exit(2); }
const outDir = path.resolve(opt.out || path.join(dir, '.snapshots'));
fs.mkdirSync(outDir, { recursive: true });
// pictures an older version (or preview_art.mjs) left here are removed: the picture is looked at only on render.py sheets
for (const f of fs.readdirSync(outDir)) {
  if (/^(t-.*\.png|sheet-.*\.png|compare-.*\.png|review\.html|report\.json)$/.test(f)) fs.unlinkSync(path.join(outDir, f));
  else if (/^art-/.test(f) && fs.statSync(path.join(outDir, f)).isDirectory()) fs.rmSync(path.join(outDir, f), { recursive: true, force: true });
}

const html = fs.readFileSync(indexHtml, 'utf8');
const W = Number((html.match(/data-width="(\d+)"/) || [])[1] || 1920);
const H = Number((html.match(/data-height="(\d+)"/) || [])[1] || 1080);
const crop = typeof opt.crop === 'string' ? opt.crop.split(',').map(Number) : null;
const scale = Number(opt.scale || (crop ? 2 : 1));

// ---------- launch ----------
function browserConfig() {
  const f = path.join(os.homedir(), '.cache', 'motion-video-deps', 'browser.json');
  try {
    const c = JSON.parse(fs.readFileSync(f, 'utf8'));
    if (c.executablePath && fs.existsSync(c.executablePath)) return c;
  } catch { /* none yet */ }
  return null;
}
async function launch() {
  const cfg = browserConfig();
  const env = { ...process.env };
  const libs = cfg ? cfg.libDirs || [] : [];
  if (libs.length) env.LD_LIBRARY_PATH = [...libs, env.LD_LIBRARY_PATH].filter(Boolean).join(':');
  try {
    return await chromium.launch({ env, ...(cfg ? { executablePath: cfg.executablePath } : {}) });
  } catch (err) {
    console.error('✖ no working browser yet. Run once (it diagnoses and fixes the environment):\n  node ' + path.join(here, 'setup_browser.mjs'));
    console.error('  ' + String(err.message || err).split('\n')[0]);
    process.exit(4);
  }
}
const browser = await launch();
const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: scale });
const page = await context.newPage();
const logs = [];
// software WebGL (SwiftShader) reports harmless "GPU stall due to ReadPixels" performance notes when screenshotting
const noise = /GL Driver Message .*(GPU stall due to ReadPixels|Performance)/;
page.on('console', (m) => { if ((m.type() === 'error' || m.type() === 'warning') && !noise.test(m.text())) logs.push(`console.${m.type()}: ${m.text()}`); });
page.on('pageerror', (e) => logs.push(`page error: ${e.message}`));

async function openPlayer(p) {
  await p.goto(pathToFileURL(indexHtml).href + (opt.captions ? '?captions' : ''));
  await p.addStyleTag({ content: '.vp-start, .vp-debug { display: none !important; } body { cursor: none !important; }' });
  await p.waitForFunction(() => document.body.classList.contains('vp-ready') || document.querySelector('.vp-error'), null, { timeout: 30000 })
    .catch(() => console.error('✖ the player did not become ready within 30 s'));
  return p.evaluate(() => (document.querySelector('.vp-error') || {}).textContent || '');
}
const bootError = await openPlayer(page);
// --safezone: tinted bands where text would sit too close to the edge (or under a platform's UI in 9:16)
if (opt.safezone && !bootError) {
  await page.evaluate(() => {
    const st = document.getElementById('stage');
    const cs = getComputedStyle(document.documentElement);
    const px = (n, d) => parseFloat(cs.getPropertyValue(n)) || d;
    const safe = px('--safe', 64), z = { top: px('--safe-top', safe), bottom: px('--safe-bottom', safe), right: px('--safe-right', safe), left: safe };
    const box = document.createElement('div');
    box.className = 'snap-safezone';
    box.dataset.zones = JSON.stringify(z);
    box.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:2147483000';
    const band = (css) => { const d = document.createElement('div'); d.style.cssText = 'position:absolute;background:rgba(255,40,80,.16);outline:1px dashed rgba(255,80,110,.8);' + css; box.appendChild(d); };
    band(`left:0;right:0;top:0;height:${z.top}px`);
    band(`left:0;right:0;bottom:0;height:${z.bottom}px`);
    band(`right:0;top:${z.top}px;bottom:${z.bottom}px;width:${z.right}px`);
    band(`left:0;top:${z.top}px;bottom:${z.bottom}px;width:${z.left}px`);
    st.appendChild(box);
  });
}
if (bootError) {
  console.log('✖ player error: ' + bootError);
  for (const l of logs) console.log('  ' + l);
  await browser.close();
  process.exit(1);
}
const data = await page.evaluate(() => ({ duration: window.__video.duration, cues: window.VIDEO_DATA.cues, audioDuration: window.VIDEO_DATA.audioDuration, leadIn: window.VIDEO_DATA.leadIn }));
const cues = data.cues;

// ---------- which times ----------
const clampT = (t) => Math.max(0, Math.min(data.duration - 0.02, t));
let shots = [];
let mode = 'default';
if (typeof opt.times === 'string') {
  mode = 'times';
  shots = opt.times.split(',').map(Number).filter((n) => !Number.isNaN(n)).map((t) => ({ t: clampT(t) }));
} else if (typeof opt.cues === 'string') {
  mode = 'cues';
  for (const id of opt.cues.split(',')) {
    const c = cues.find((x) => x.id === id.trim());
    if (!c) { console.error(`unknown cue ${id}`); continue; }
    shots.push({ t: clampT(c.start + 0.15), tag: 'start' }, { t: clampT(c.start + c.duration / 2), tag: 'mid' }, { t: clampT(c.end - 0.1), tag: 'end' });
  }
} else if (typeof opt.range === 'string') {
  mode = 'range';
  const [a, b] = opt.range.split(':').map(Number);
  const step = Number(opt.step || 0.1);
  for (let t = a; t <= b + 1e-6; t += step) shots.push({ t: clampT(Math.round(t * 1000) / 1000) });
} else if (opt.overview) {
  mode = 'overview';
  const every = Number(opt.every || 2);
  for (let t = 0.3; t < data.duration; t += every) shots.push({ t: clampT(t) });
  shots.push({ t: clampT(data.duration - 0.05) });
} else {
  shots = [{ t: 0.3, tag: 'start' }];
  for (const c of cues) shots.push({ t: Math.min(c.end, c.start + Math.max(0.6, c.duration * 0.65)) });
  shots.push({ t: clampT(data.duration - 0.05), tag: 'end' });
}

// what is being said at t (by character position inside the cue)
function spokenAt(t) {
  const c = cues.find((x) => t >= x.start && t <= x.end);
  if (!c) {
    const next = cues.find((x) => x.start > t);
    // (between lines by the cue times — whether anything sounds there, a clip or room tone, is not known here)
    return { cue: '', words: next ? `(between lines — ${next.id} starts in ${(next.start - t).toFixed(1)}s)` : '(after the last line)' };
  }
  const chars = [...c.text.replace(/\s+/g, ' ')];
  const weight = chars.map((ch) => (/[\s.,!?·…"'“”‘’()[\]-]/.test(ch) ? 0 : 1));
  const total = weight.reduce((a, b) => a + b, 0) || 1;
  const target = ((t - c.start) / c.duration) * total;
  let acc = 0;
  let i = 0;
  for (; i < chars.length - 1; i++) { acc += weight[i]; if (acc >= target) break; }
  const a = Math.max(0, i - 9);
  const b = Math.min(chars.length, i + 9);
  return { cue: c.id, words: `${a > 0 ? '…' : ''}${chars.slice(a, i).join('')}▸${chars.slice(i, b).join('')}${b < chars.length ? '…' : ''}` };
}

// ---------- layout probe (runs in the page) ----------
// Works on what is actually visible: each text box is intersected with its clipping ancestors, so text
// hidden on purpose (SplitText masks before a reveal, a digit strip in a window) is ignored.
function probe() {
  const stage = document.getElementById('stage');
  const sr = stage.getBoundingClientRect();
  const R = (r) => ({ left: r.left, top: r.top, right: r.right, bottom: r.bottom });
  const cut = (a, b) => ({ left: Math.max(a.left, b.left), top: Math.max(a.top, b.top), right: Math.min(a.right, b.right), bottom: Math.min(a.bottom, b.bottom) });
  const area = (r) => Math.max(0, r.right - r.left) * Math.max(0, r.bottom - r.top);
  const cls = (n) => (typeof n.className === 'string' ? n.className : (n.className && n.className.baseVal) || '');
  const eff = (el) => {
    let o = 1;
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.visibility === 'hidden' || cs.display === 'none') return 0;
      o *= parseFloat(cs.opacity);
    }
    return o;
  };
  const warn = [];
  const boxes = [];
  const walker = document.createTreeWalker(stage, NodeFilter.SHOW_ELEMENT);
  for (let el = walker.currentNode; el; el = walker.nextNode()) {
    if (el.closest('.vp-measure') || el.closest('.snap-safezone') || (el.closest('.vp-captions') && !el.closest('.vp-on'))) continue; // shown captions count
    // decorative copies (TypeFX shards/bands/extrusion layers/ghosts, FXKit glints) stand in for real text on purpose
    if (el.closest('[data-fx-copy]')) continue;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own || eff(el) < 0.5) continue;
    const raw = R(el.getBoundingClientRect());
    if (area(raw) < 4) continue;
    let vis = raw;
    let clipper = null;
    for (let n = el.parentElement; n && n !== stage; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (!/(hidden|clip)/.test(cs.overflow + cs.overflowX + cs.overflowY)) continue;
      const before = area(vis);
      vis = cut(vis, R(n.getBoundingClientRect()));
      if (!clipper && area(vis) < before - 1) clipper = n;
    }
    const shown = area(vis) / area(raw);
    if (shown < 0.05) continue; // hidden on purpose
    const text = el.textContent.trim().replace(/\s+/g, ' ').slice(0, 28);
    // a TypeFX unit that an effect is moving (scatter, swirl, drop…) leaves its box on purpose
    const moving = !!el.closest('.tx-i[style*="transform"]');
    // masks (SplitText) and rolling-digit windows (odometers: .od / .fxkit-od / .odo…) clip on purpose
    if (shown < 0.97 && clipper && !/mask|(^|[\s-])odo?(\s|$|-)|digit|roll/i.test(cls(clipper))) warn.push(`text clipped by its container (${Math.round(shown * 100)}% visible): "${text}"`);
    const onScreen = area(cut(vis, R(sr))) / area(vis);
    if (onScreen === 0) continue;
    if (onScreen < 0.98 && onScreen > 0.3 && !moving) warn.push(`text cut by screen edge (${Math.round(onScreen * 100)}% visible): "${text}"`);
    boxes.push({ el, r: cut(vis, R(sr)), text, tx: el.closest('[data-tx]') });
    const zoneBox = document.querySelector('.snap-safezone');
    if (zoneBox && !moving) {
      const z = JSON.parse(zoneBox.dataset.zones), k = sr.width / (stage.offsetWidth || sr.width), v = cut(vis, R(sr));
      const hit = [v.top < sr.top + z.top * k && 'top', v.bottom > sr.bottom - z.bottom * k && 'bottom', v.right > sr.right - z.right * k && 'right', v.left < sr.left + z.left * k && 'left'].filter(Boolean);
      if (hit.length && area(v) > 4) warn.push(`text in the unsafe ${hit.join('/')} margin${hit.length > 1 ? 's' : ''} (--safe-*; in 9:16 covered by Shorts/Reels/TikTok UI): "${text}"`);
    }
  }
  // glows clipped into boxes: a light text-shadow on text inside a clipping ancestor (SplitText mask, digit
  // columns, overflow hidden, clip-path, mask-image) is cut at that box -> faint rectangles behind the letters
  const parseShadows = (v) => {
    if (!v || v === 'none') return [];
    return v.split(/,(?![^(]*\))/).map((sh) => {
      const c = (sh.match(/rgba?\(([^)]+)\)/) || [])[1];
      const [r, g, b, a = 1] = c ? c.split(',').map(Number) : [0, 0, 0, 1];
      const px = (sh.replace(/rgba?\([^)]*\)/, '').match(/-?[\d.]+px/g) || []).map(parseFloat);
      const [x = 0, y = 0, blur = 0] = px;
      const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
      return { reach: Math.max(Math.abs(x), Math.abs(y)) + blur, glow: a >= 0.15 && lum >= 0.2 };
    }).filter((x) => x.glow && x.reach > 2);
  };
  const clipRect = (n, cs) => {
    const box = R(n.getBoundingClientRect());
    if (/(hidden|clip)/.test(cs.overflow + cs.overflowX + cs.overflowY)) return box;
    if ((cs.maskImage && cs.maskImage !== 'none') || (cs.webkitMaskImage && cs.webkitMaskImage !== 'none')) return box;
    const cp = cs.clipPath;
    if (!cp || cp === 'none') return null;
    const w = box.right - box.left, h = box.bottom - box.top;
    const m = cp.match(/^inset\(([^)]*)\)/);
    if (m) {
      const v = m[1].split(/\s+round\s+/)[0].trim().split(/\s+/).map((x, i) => (x.endsWith('%') ? parseFloat(x) / 100 * (i % 2 ? w : h) : parseFloat(x) || 0));
      const [t, rr = t, bb = t, l = rr] = v;
      return { left: box.left + l, top: box.top + t, right: box.right - rr, bottom: box.bottom - bb };
    }
    const c = cp.match(/^circle\(\s*([\d.]+)(px|%)/);
    if (c && parseFloat(c[1]) * (c[2] === '%' ? Math.hypot(w, h) / 100 : 1) > Math.hypot(sr.width, sr.height)) return null;
    return box;
  };
  const glowWarned = new Set();
  for (const b of boxes) {
    const cs = getComputedStyle(b.el);
    const sh = parseShadows(cs.textShadow);
    if (!sh.length) continue;
    const reach = Math.max(...sh.map((x) => x.reach));
    const tr = R(b.el.getBoundingClientRect());
    const need = { left: tr.left - reach, top: tr.top - reach, right: tr.right + reach, bottom: tr.bottom + reach };
    for (let n = b.el; n && n !== stage; n = n.parentElement) {   // the element itself clips its own text too
      const cr = clipRect(n, getComputedStyle(n));
      if (!cr) continue;
      if (need.left < cr.left - 1 || need.top < cr.top - 1 || need.right > cr.right + 1 || need.bottom > cr.bottom + 1) {
        let src = b.el;   // where the shadow is declared (it is inherited)
        while (src.parentElement && src.parentElement !== stage && getComputedStyle(src.parentElement).textShadow === cs.textShadow) src = src.parentElement;
        let label = src.textContent.trim().replace(/\s+/g, ' ');
        if (/0123456789/.test(label)) label = `rolling digits ${src.tagName.toLowerCase()}${cls(src) ? '.' + cls(src).trim().split(/\s+/).join('.') : ''}`;
        label = label.slice(0, 40);
        if (!glowWarned.has(src)) {
          glowWarned.add(src);
          warn.push(`glow clipped into a box: text-shadow on "${label}" is cut by ${n.tagName.toLowerCase()}${cls(n) ? '.' + cls(n).trim().split(/\s+/)[0] : ''} (mask/overflow/clip) — faint rectangles behind the letters; use filter: drop-shadow() on an element outside the clip (player-api.md §4)`);
        }
        break;
      }
    }
  }
  const blocks = boxes.filter((b) => !boxes.some((o) => o !== b && o.el.contains(b.el)));
  for (let i = 0; i < blocks.length; i++) {
    for (let j = i + 1; j < blocks.length; j++) {
      const a = blocks[i];
      const b = blocks[j];
      if (a.el.parentElement === b.el.parentElement && a.el.parentElement.children.length > 3) continue; // split chars/words of one line
      if (a.tx && a.tx === b.tx) continue;   // units of one TypeFX group crossing each other (jelly, wave, swirl)
      const small = Math.min(area(a.r), area(b.r));
      if (area(cut(a.r, b.r)) > small * 0.15) warn.push(`text overlaps text: "${a.text}" × "${b.text}"`);
    }
  }
  return [...new Set(warn)];
}

// the visible state of the stage: for every element that can be seen (on stage, effective opacity > 0, not hidden),
// the computed values that change the picture (GSAP's lazy inline styles that compute to the same value don't
// count), plus a hash of every visible canvas's pixels
const stageState = (p, t) => p.evaluate((tt) => {
  // re-render this frame inside the same task, so WebGL canvases still hold their drawing buffer when read
  window.__video.seek(tt);
  const st = document.getElementById('stage');
  const SR = st.getBoundingClientRect();
  const h = (s) => { let x = 2166136261; for (let i = 0; i < s.length; i++) { x ^= s.charCodeAt(i); x = Math.imul(x, 16777619); } return (x >>> 0).toString(16); };
  const PROPS = ['transform', 'translate', 'rotate', 'scale', 'opacity', 'clip-path', 'filter', 'color', 'background-color', 'width', 'height',
    'left', 'top', 'font-weight', 'fill', 'fill-opacity', 'stroke', 'stroke-opacity', 'stroke-dasharray', 'stroke-dashoffset', 'd', 'letter-spacing'];
  // values that draw the same picture compare equal (GSAP's lazy inline styles, identity transforms)
  const IDENT = { transform: /^matrix\(1, 0, 0, 1, 0, 0\)$/, translate: /^0(px)?( 0(px)?)?$/, rotate: /^0(deg)?$/, scale: /^1( 1)?$/ };
  const norm = (k, v) => {
    let s = String(v).replace(/-?\d*\.?\d+(e[-+]?\d+)?/gi, (n) => { const x = +(+n).toFixed(2); return String(Object.is(x, -0) ? 0 : x); });
    if (IDENT[k] && IDENT[k].test(s)) s = 'none';
    return s;
  };
  const onStage = (r) => r.right > SR.left && r.left < SR.right && r.bottom > SR.top && r.top < SR.bottom && (r.width > 0 || r.height > 0);
  const rows = [], canvases = [], gl = [];
  const walk = (el, op, path) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    const o = op * parseFloat(cs.opacity || 1);
    if (o < 0.002) return;
    const r = el.getBoundingClientRect();
    if (onStage(r)) {               // off-screen elements can differ without changing the picture
      let own = '';
      for (const n of el.childNodes) if (n.nodeType === 3 && n.textContent.trim()) own += n.textContent;
      rows.push(path + '|' + PROPS.map((k) => norm(k, cs.getPropertyValue(k))).join(';') + (own ? '|' + own : ''));
      if (el.tagName === 'CANVAS') {
        // 2D canvases are read directly; WebGL ones (getContext('2d') → null) render asynchronously, so they are
        // compared from a screenshot of their box (taken in Node after the frame is presented)
        let c2 = null;
        try { c2 = el.getContext('2d'); } catch (e) { c2 = null; }
        if (c2) { try { canvases.push(path + ':' + h(el.toDataURL())); } catch (e) { canvases.push(path + ':unreadable'); } }
        else gl.push({ path, x: Math.max(r.left, SR.left), y: Math.max(r.top, SR.top), w: Math.min(r.right, SR.right) - Math.max(r.left, SR.left), h: Math.min(r.bottom, SR.bottom) - Math.max(r.top, SR.top) });
      }
    }
    let i = 0;
    for (const c of el.children) walk(c, o, path + '>' + c.tagName.toLowerCase() + (c.classList && c.classList.length ? '.' + c.classList[0] : '') + ':' + i++);
  };
  for (const c of st.children) walk(c, 1, c.tagName.toLowerCase() + (c.id ? '#' + c.id : ''));
  return { rows, domHash: h(rows.join('\n')), canvases, gl };
}, t);
async function captureState(p, t) {
  const st = await stageState(p, t);
  if (st.gl.length) {
    await settle(p);
    for (const g of st.gl) {
      if (g.w < 1 || g.h < 1) continue;
      const png = await p.screenshot({ clip: { x: g.x, y: g.y, width: g.w, height: g.h } });
      st.canvases.push(g.path + ':' + crypto.createHash('sha1').update(png).digest('hex').slice(0, 16));
    }
  }
  delete st.gl;
  return st;
}
// fonts, footage stills (js/media.js decodes the frame each clip shows at t) and two frames for layout
const settle = (p) => p.evaluate(() => document.fonts.ready
  .then(() => (window.__media && window.__media.settle ? window.__media.settle() : null))
  .then(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))));
// the frame's PNG bytes, kept in memory for --seekcheck's comparison only — never written, never shown (render.py is
// how the picture is looked at)
const shoot = (p) => (crop ? p.screenshot({ clip: { x: crop[0], y: crop[1], width: crop[2], height: crop[3] } })
  : p.locator('#stage').screenshot());
const seekTimed = (p, t) => p.evaluate((tt) => { const a = performance.now(); window.__video.seek(tt); return performance.now() - a; }, t);
// the command that shows a moment — render.py's sheets are the only way to look at the picture
// (the project's own copy when it knows --at/--via; an older copy → the skill's, and say how to update the project's)
const skillPy = path.join(here, '..', 'assets', 'template', 'render.py'), ownPy = path.join(dir, 'render.py');
const ownKnows = fs.existsSync(ownPy) && /'--via'/.test(fs.readFileSync(ownPy, 'utf8'));
const renderPy = ownKnows ? ownPy : skillPy;
if (!ownKnows) console.log(`note: ${fs.existsSync(ownPy) ? "this project's render.py is older than the skill's (no --at/--crop/--via/--art)" : 'no render.py in the project'} — the commands below use the skill's; update the project's copy: cp ${skillPy} ${ownPy}`);
const q = (s) => (/^[\w./@%+=:,-]+$/.test(s) ? s : `'${s.replace(/'/g, `'\\''`)}'`);
const lookCmd = (times, extra = '') => `python3 ${q(renderPy)} ${q(dir)} --screenshot --at ${[...new Set(times.map((t) => +t.toFixed(2)))].join(',')}${extra}`;
// playback-like cost: from 0.5 s before t, step forward one 30 fps frame at a time (what a recording does)
const playTimed = (p, t) => p.evaluate((tt) => {
  const out = [];
  window.__video.seek(Math.max(0, tt - 0.5));
  for (let k = 1; k <= 15; k++) { const a = performance.now(); window.__video.seek(Math.max(0, tt - 0.5) + k / 30); out.push(performance.now() - a); }
  return out;
}, t);

// ---------- shoot ----------
const frames = [];
const perf = [];
const play = [];
for (const s of shots) {
  if (opt.perf) for (const ms of await playTimed(page, s.t)) play.push({ t: s.t, ms });
  perf.push({ t: s.t, ms: await seekTimed(page, s.t) });
  await settle(page);
  if (opt.seekcheck) {
    s.state = await captureState(page, s.t);
    s.png = await shoot(page);
    s.pix = crypto.createHash('sha1').update(s.png).digest('hex');
  }
  const said = spokenAt(s.t);
  const { png: _png, ...meta } = s;
  frames.push({ ...meta, cue: said.cue, words: said.words, warnings: await page.evaluate(probe) });
}

// ---------- seek determinism (--seekcheck) ----------
// the same picture whichever way a time is reached: every shot again in reverse order, then in a seeded shuffled order.
// The picture is compared (screenshot hash; when the hashes differ, the pixels — PNG encoding alone is not a change);
// the computed state says which element differs.
let seekcheck = null;
let diffPage = null;
async function pixelDiff(bufA, bufB) {
  diffPage = diffPage || await context.newPage();
  return diffPage.evaluate(async ([a, b]) => {
    const load = (src) => new Promise((ok, bad) => { const im = new Image(); im.onload = () => ok(im); im.onerror = bad; im.src = src; });
    const [A, B] = await Promise.all([load(a), load(b)]);
    if (A.width !== B.width || A.height !== B.height) return { n: A.width * A.height, box: [0, 0, A.width, A.height] };
    const px = (im) => { const c = document.createElement('canvas'); c.width = im.width; c.height = im.height; const x = c.getContext('2d'); x.drawImage(im, 0, 0); return x.getImageData(0, 0, c.width, c.height).data; };
    const pa = px(A), pb = px(B), w = A.width;
    let n = 0, x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
    for (let i = 0; i < pa.length; i += 4) {
      if (Math.abs(pa[i] - pb[i]) > 2 || Math.abs(pa[i + 1] - pb[i + 1]) > 2 || Math.abs(pa[i + 2] - pb[i + 2]) > 2 || Math.abs(pa[i + 3] - pb[i + 3]) > 2) {
        n++; const p = i / 4, x = p % w, y = (p - x) / w;
        if (x < x0) x0 = x; if (y < y0) y0 = y; if (x > x1) x1 = x; if (y > y1) y1 = y;
      }
    }
    return { n, box: [x0, y0, x1 - x0 + 1, y1 - y0 + 1] };
  }, [`data:image/png;base64,${bufA.toString('base64')}`, `data:image/png;base64,${bufB.toString('base64')}`]);
}
let lastT = shots.length ? shots[shots.length - 1].t : 0;   // where the page stands: the time each shot is reached from
async function recheck(order, label) {
  const out = [];
  for (const s of order) {
    const from = lastT;
    lastT = s.t;
    await page.evaluate((tt) => window.__video.seek(tt), s.t);
    await settle(page);
    const b = await captureState(page, s.t);
    const a = s.state;
    if (!a) continue;
    const png = await shoot(page, null);
    const diffs = [];
    if (a.domHash !== b.domHash) {
      const A = new Map(a.rows.map((r) => [r.split('|')[0], r])), B = new Map(b.rows.map((r) => [r.split('|')[0], r]));
      const keys = [...new Set([...A.keys(), ...B.keys()])].filter((k) => A.get(k) !== B.get(k));
      for (const k of keys.slice(0, 3)) {
        const ra = A.get(k), rb = B.get(k);
        if (!ra || !rb) { diffs.push(`${k.split('>').slice(-3).join('>')} ${ra ? 'visible only on the first pass' : 'visible only after re-seeking'}`); continue; }
        const pa = ra.split('|')[1].split(';'), pb = rb.split('|')[1].split(';');
        const what = pa.map((v, j) => (v !== pb[j] ? `${['transform', 'translate', 'rotate', 'scale', 'opacity', 'clip-path', 'filter', 'color', 'background-color', 'width', 'height', 'left', 'top', 'font-weight', 'fill', 'fill-opacity', 'stroke', 'stroke-opacity', 'stroke-dasharray', 'stroke-dashoffset', 'd', 'letter-spacing'][j]}: ${v.slice(0, 50)} → ${pb[j].slice(0, 50)}` : null)).filter(Boolean);
        if (ra.split('|')[2] !== rb.split('|')[2]) what.push(`text: "${(ra.split('|')[2] || '').slice(0, 30)}" → "${(rb.split('|')[2] || '').slice(0, 30)}"`);
        diffs.push(`${k.split('>').slice(-3).join('>')}: ${what.join(' · ')}`);
      }
      if (keys.length > 3) diffs.push(`… ${keys.length - 3} more element(s)`);
    }
    const bc = new Set(b.canvases);
    for (const c of a.canvases) if (!bc.has(c)) diffs.push(`canvas ${c.slice(0, c.lastIndexOf(':')).split('>').slice(-2).join('>')} pixels differ`);
    // the verdict is the picture itself (SVG attributes like cx, box-shadow, backgrounds — anything the property list
    // doesn't hold); the property and canvas differences above only say where to look
    const d = crypto.createHash('sha1').update(png).digest('hex') === s.pix ? { n: 0 } : await pixelDiff(s.png, png);
    if (!d.n) continue;
    diffs.unshift(`picture differs: ${d.n} px in ${d.box[2]}×${d.box[3]} at ${d.box[0]},${d.box[1]}${crop ? ' of the crop' : ''}${diffs.length ? '' : ' — no listed property explains it (an SVG attribute, box-shadow, background …): look at that area with the render.py --via command below'}`);
    if (diffs.length) out.push({ t: s.t, from, order: label, diffs });
  }
  return out;
}
if (opt.seekcheck) {
  // mulberry32, the player's rand(): the same --seed gives the same order every run
  let a = (Number(opt.seed) || 1) >>> 0;
  const rnd = () => { a = (a + 0x6d2b79f5) >>> 0; let r = Math.imul(a ^ (a >>> 15), 1 | a); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; };
  const shuffled = [...shots];
  for (let i = shuffled.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]; }
  seekcheck = [...await recheck([...shots].reverse(), 'reverse order'), ...await recheck(shuffled, `shuffled order (seed ${Number(opt.seed) || 1})`)];
  for (const s of [...shots, ...frames]) { delete s.state; delete s.pix; delete s.png; }
}

// (--motion was removed: guessing "static" or "least active" from a pixel-change threshold is a heuristic — rhythm and
// static stretches are judged by looking at render.py sheets of the whole video, visual-review.md)
if (opt.motion) console.warn(`--motion was removed — judge rhythm and static stretches on render.py sheets of the whole video: python3 ${q(renderPy)} ${q(dir)} --screenshot --gapframe 120`);
// (contact sheets, --compare and review.html were removed: snapshot.mjs writes no picture. Look with render.py --screenshot;
// a before/after is two render.py runs with --out <dir>/screenshots/before and …/after)
for (const k of ['grid', 'compare', 'keep']) if (opt[k] !== undefined) console.warn(`--${k} was removed — snapshot.mjs writes no images; look with render.py --screenshot (visual-review.md)`);
await browser.close();

// ---------- report.json ----------
const title = (f) => `t=${f.t.toFixed(2)}${f.cue ? ` · ${f.cue}` : ''}${f.tag ? ` · ${f.tag}` : ''}`;
const uniqLogs = [...new Set(logs)];
const perfSorted = [...perf].sort((a, b) => b.ms - a.ms);
const perfSummary = perf.length ? { avg: +(perf.reduce((a, b) => a + b.ms, 0) / perf.length).toFixed(2), max: +perfSorted[0].ms.toFixed(2), worst: perfSorted.slice(0, 3) } : null;
const playSorted = [...play].sort((a, b) => a.ms - b.ms);
const pct = (q) => (playSorted.length ? playSorted[Math.min(playSorted.length - 1, Math.floor(q * playSorted.length))] : null);
const playSummary = play.length ? { avg: +(play.reduce((a, b) => a + b.ms, 0) / play.length).toFixed(2), p95: +pct(0.95).ms.toFixed(2), max: +playSorted[playSorted.length - 1].ms.toFixed(2), worstAt: playSorted[playSorted.length - 1].t } : null;
fs.writeFileSync(path.join(outDir, 'report.json'), JSON.stringify({ project: dir, mode, size: [W * scale, H * scale], crop, frames, console: uniqLogs, perf: opt.perf ? { playback: playSummary, seek: perfSummary } : undefined, seekcheck: seekcheck || undefined }, null, 2));

// ---------- console report ----------
const rel = (p) => path.relative(process.cwd(), p) || '.';
console.log(`✓ checked ${frames.length} moment(s) (${mode}) → ${rel(path.join(outDir, 'report.json'))}  (no images: look with render.py --screenshot)`);
if (uniqLogs.length) {
  console.log(`\n✖ console (${uniqLogs.length}):`);
  for (const l of uniqLogs.slice(0, 20)) console.log('  ' + l.slice(0, 300));
}
const warned = frames.filter((f) => f.warnings.length);
if (warned.length) {
  console.log('\n⚠ layout warnings (some are intentional, e.g. mid-animation or a panel leaving — look at each moment on a render.py sheet):');
  for (const f of warned) {
    console.log(`  ${title(f)}`);
    for (const w of f.warnings.slice(0, 6)) console.log('    - ' + w);
  }
  console.log(`  look: ${lookCmd(warned.map((f) => f.t), crop ? ` --crop ${crop.join(',')} --res 1080p` : '')}`);
} else console.log('✓ no text overlaps or clipped text detected');
if (seekcheck) {
  if (!seekcheck.length) console.log(`\n✓ seekcheck: all ${frames.length} frames identical when reached again in reverse and in shuffled order (deterministic)`);
  else {
    const at = new Set(seekcheck.map((m) => m.t));
    console.log(`\n✖ seekcheck: ${at.size} of ${frames.length} frames differ when reached again — something depends on playback history or the seek path (accumulated state, Math.random/Date, a cache that skips a write, a callback):`);
    for (const m of seekcheck.slice(0, 8)) {
      console.log(`  t=${m.t.toFixed(2)} (${m.order}, reached from t=${m.from.toFixed(2)})`);
      for (const d of m.diffs.slice(0, 3)) console.log('    - ' + d);
      console.log(`    look: ${lookCmd([m.t], ` --via ${+m.from.toFixed(2)}${crop ? ` --crop ${crop.join(',')}` : ''}`)}`);
    }
    process.exitCode = 1;
  }
}
if (opt.perf && playSummary) {
  console.log(`\n~ JS per frame during playback (sequential 1/30 s steps, GSAP + onFrame): avg ${playSummary.avg} ms, p95 ${playSummary.p95} ms, max ${playSummary.max} ms near t=${playSummary.worstAt.toFixed(2)}${playSummary.p95 > 8 ? '  ⚠ heavy — may drop frames on slower machines' : ''}`);
  console.log(`  random seek (scrubbing / ?t= / snapshots — not what the recording sees): avg ${perfSummary.avg} ms, max ${perfSummary.max} ms`);
}
