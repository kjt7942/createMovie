#!/usr/bin/env node
/**
 * preview_art.mjs — CHECK one illustration module (js/art/*.js) on its own, in headless Chromium: console errors and
 * determinism. It writes no picture. To LOOK at the module, it prints the render.py command that films it the same way
 * the video is filmed:  python3 <dir>/render.py <dir> --screenshot --art <name> --viewbox "…" --at … [--state …]
 * (render.py --screenshot is the only way the picture is looked at — SKILL.md, visual-review.md).
 *
 *   node preview_art.mjs <projectDir> <ART.name> --viewbox "-200 -130 400 260" [options]
 *   node preview_art.mjs --page <file.html> [options]          # your own page with window.ART_PREVIEW(t) — check only
 *
 * module mode builds ART.<name> into an <svg viewBox="…"> (or a <g> inside one with --group), loading the project's
 * js/art/core.js and every other js/art/*.js, then poses it with animate(t, state) at each --t.
 *
 * options
 *   --t 0,0.7,1.4          times to pose (default 0,0.5,1.0,1.5)
 *   --state '{"lamp":1}'   state object passed to animate(t, state)   (JSON)
 *   --opts '{"hue":"…"}'   opts passed to build(el, opts)               (JSON)
 *   --group                build into a <g> at the viewBox origin (for modules whose container is a <g>)
 *   --size 800x520         logical size of the module's box (default: viewBox aspect, 800 wide)
 *   --bg '#04122e'         background (passed on to the render.py command)
 *
 * Prints console errors and checks determinism (exit code 1 on either): after posing every other t, posing the first t
 * again must reproduce exactly the same DOM state (every attribute animate() writes). (Pixels are not compared:
 * Chromium repaints only changed regions, so anti-aliasing can differ by a few pixels between identical states.) In
 * --page mode the page's own #stage/body markup is compared. Uses the browser configured by setup_browser.mjs.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { pathToFileURL, fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
let chromium;
try { ({ chromium } = await import('playwright-core')); } catch {
  console.error(`playwright-core is not installed. Run once:\n  node ${path.join(here, 'setup_browser.mjs')}`); process.exit(4);
}

const argv = process.argv.slice(2);
const opt = { _: [] };
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a.startsWith('--')) { const k = a.slice(2); opt[k] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true; } else opt._.push(a);
}
const json = (s, d) => { if (typeof s !== 'string') return d; try { return JSON.parse(s); } catch (e) { console.error(`✖ bad JSON: ${s}`); process.exit(2); } };
const times = (typeof opt.t === 'string' ? opt.t : '0,0.5,1,1.5').split(',').map(Number).filter((x) => Number.isFinite(x));
const state = json(opt.state, {});
const bopts = json(opt.opts, {});
const bg = typeof opt.bg === 'string' ? opt.bg : '#04122e';

let pageFile, cellW, cellH, name, look = '';
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'artprev-'));
if (typeof opt.page === 'string') {
  pageFile = path.resolve(opt.page);
  name = path.basename(pageFile, '.html');
  [cellW, cellH] = (typeof opt.size === 'string' ? opt.size : '1280x720').split('x').map(Number);
} else {
  const [dir0, mod] = opt._;
  if (!dir0 || !mod || typeof opt.viewbox !== 'string') {
    console.error('usage: node preview_art.mjs <projectDir> <ART.name> --viewbox "x y w h" [--t 0,1] [--state JSON] [--opts JSON] [--group]\n       node preview_art.mjs --page file.html [--t …]');
    process.exit(2);
  }
  const dir = path.resolve(dir0);
  const artDir = path.join(dir, 'js', 'art');
  if (!fs.existsSync(path.join(artDir, 'core.js'))) { console.error(`✖ ${artDir}/core.js not found`); process.exit(2); }
  name = mod.replace(/^ART\./, '');
  const vb = opt.viewbox.trim().split(/[\s,]+/).map(Number);
  cellW = 800;
  cellH = Math.round(800 * vb[3] / vb[2]);
  if (typeof opt.size === 'string') [cellW, cellH] = opt.size.split('x').map(Number);
  // the one way to look at it: render.py films the module the way it films the video (it builds the same page in memory)
  const own = path.join(dir, 'render.py'), skill = path.join(here, '..', 'assets', 'template', 'render.py');
  const rp = fs.existsSync(own) && /'--art'/.test(fs.readFileSync(own, 'utf8')) ? own : skill;   // an older project copy lacks --art
  if (rp === skill) console.log(`note: ${fs.existsSync(own) ? "this project's render.py is older than the skill's (no --art)" : 'no render.py in the project'} — update it: cp ${skill} ${own}`);
  const sq = (v) => (/^[\w./@%+=:,-]+$/.test(v) ? v : `'${String(v).replace(/'/g, `'\\''`)}'`);
  look = `python3 ${sq(rp)} ${sq(dir)} --screenshot --art ${sq(name)} --viewbox ${sq(vb.join(' '))} --at ${times.join(',')}` +
    (opt.group ? ' --group' : '') + (typeof opt.opts === 'string' ? ` --opts ${sq(opt.opts)}` : '') +
    (typeof opt.state === 'string' ? ` --state ${sq(opt.state)}` : '') + (typeof opt.bg === 'string' ? ` --bg ${sq(opt.bg)}` : '') +
    (typeof opt.size === 'string' ? ` --size ${opt.size}` : '');
  const scripts = ['core.js', ...fs.readdirSync(artDir).filter((f) => f.endsWith('.js') && f !== 'core.js').sort()]
    .map((f) => `<script src="${pathToFileURL(path.join(artDir, f)).href}"></script>`).join('\n');
  const fonts = ['css/player.css', 'css/fonts.css'].filter((f) => fs.existsSync(path.join(dir, f)))
    .map((f) => `<link rel="stylesheet" href="${pathToFileURL(path.join(dir, f)).href}">`).join('');
  pageFile = path.join(tmp, 'page.html');
  fs.writeFileSync(pageFile, `<!doctype html><meta charset="utf-8">${fonts}
<style>html,body{margin:0;background:${bg};overflow:hidden}svg{display:block;width:${cellW}px;height:${cellH}px}</style>
<svg id="host" viewBox="${vb.join(' ')}">${opt.group ? '<g id="el"></g>' : ''}</svg>
${scripts}
<script>
  const target = document.getElementById(${opt.group ? '"el"' : '"host"'});
  const mod = window.ART && window.ART[${JSON.stringify(name)}];
  if (!mod || typeof mod.build !== 'function') throw new Error('ART.' + ${JSON.stringify(name)} + ' has no build() — modules: ' + Object.keys(window.ART || {}).join(', '));
  const inst = mod.build(target, ${JSON.stringify(bopts)}) || {};
  window.ART_PREVIEW = (t) => { if (inst.animate) inst.animate(t, ${JSON.stringify(state)}); };
</script>`);
}

const cfgFile = path.join(os.homedir(), '.cache', 'motion-video-deps', 'browser.json');
const cfg = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : null;
const env = { ...process.env };
if (cfg && cfg.libDirs && cfg.libDirs.length) env.LD_LIBRARY_PATH = [...cfg.libDirs, env.LD_LIBRARY_PATH].filter(Boolean).join(':');
let browser;
try { browser = await chromium.launch({ env, ...(cfg ? { executablePath: cfg.executablePath } : {}) }); } catch (e) {
  console.error('✖ no working browser yet. Run once: node ' + path.join(here, 'setup_browser.mjs')); process.exit(4);
}
const page = await browser.newPage({ viewport: { width: cellW, height: cellH } });
const logs = [];
page.on('pageerror', (e) => logs.push(String(e.message || e)));
page.on('console', (m) => { if (m.type() === 'error') logs.push(m.text()); });
await page.goto(pathToFileURL(pageFile).href);
await page.evaluate(() => document.fonts.ready);
const hasHook = await page.evaluate(() => typeof window.ART_PREVIEW === 'function');
const domState = () => page.evaluate(() => {
  const host = document.getElementById('host') || document.getElementById('stage') || document.body;
  return host.innerHTML;
});
// pose at t and read the DOM state animate() left — no picture is taken (render.py is how the module is looked at)
const pose = async (t) => {
  if (hasHook) await page.evaluate((tt) => window.ART_PREVIEW(tt), t);
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  return crypto.createHash('sha1').update(await domState()).digest('hex');
};
const shots = [];
for (const t of times) shots.push({ t, hash: await pose(t) });
// determinism: pose the first time again after the others; the DOM state must match
let deterministic = null;
if (hasHook && times.length > 1) deterministic = (await pose(times[0])) === shots[0].hash;
await browser.close();
fs.rmSync(tmp, { recursive: true, force: true });

console.log(`✓ ${name}: posed ${shots.length} time(s) (${times.join(', ')}) — no picture written`);
if (!hasHook) console.log('  note: the page defines no window.ART_PREVIEW(t) — every pose is the same static frame');
if (deterministic === false) process.exitCode = 1;
if (deterministic === false) console.log(`✖ not deterministic: posing t=${times[0]} again after other times left a different DOM state — animate() must be a pure function of t + state: no Math.random/Date, no values accumulated across calls, no "write only if changed" caches that skip a write`);
else if (deterministic) console.log('✓ deterministic (same t → same DOM state)');
if (look) console.log(`  look: ${look}`);
else console.log('  look: a page of your own cannot be looked at — build the drawing as a js/art module and use render.py --screenshot --art (art-library.md §5)');
if (logs.length) { console.log(`✖ console (${logs.length}):`); for (const l of [...new Set(logs)].slice(0, 10)) console.log('  ' + l.slice(0, 300)); process.exitCode = 1; }
