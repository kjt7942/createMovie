#!/usr/bin/env node
/**
 * check_fonts.mjs — prove that every glyph on screen is drawn with an installed SIL OFL 1.1 catalogue font.
 *
 *   node check_fonts.mjs <projectDir> [--step 0.5]   (default: every 0.5 s plus each cue's middle and end;
 *                                                     --step 0: only each cue's middle and end — quick, misses short beats)
 *
 * Why: a system font (system-ui, Menlo, SF Mono, Consolas, Apple SD Gothic Neo, Malgun Gothic…) renders
 * differently on the recording machine than in the verification, and some system fonts carry
 * licences that don't cover a published video. The rule in this skill: only fonts shipped in
 * <project>/fonts/ with their licence files (SIL OFL 1.1, unmodified).
 *
 * 1. Static: every @font-face is a family from the skill's font catalogue (assets/fonts/catalog.json) or
 *    fonts/fonts.lock.json, its file is the unmodified file (sha256), its licence file is present, no other font file
 *    is in the project (recognised by content, not extension), and no CSS / HTML / JS font declaration names anything
 *    but installed families + CSS generics, or puts a generic family first.
 * 2. Runtime (headless Chromium, the same browser as snapshot.mjs): the page must build without an error; seek
 *    through the video with captions on, and after every seek ask the engine (CDP CSS.getPlatformFontsForNode) which
 *    font files rendered each visible text — own text, ::before/::after content, list markers, form values — including
 *    elements created later. Any non-web ("platform") font fails, with the text and the time. Every web font the page
 *    has (each @font-face of every stylesheet, each FontFace a script made) must come from an installed, unmodified
 *    file of its own family: local(), remote URLs, data: URLs and any other file fail.
 * 3. Type that is not DOM text (TypeFX): glyph outlines in js/glyphs.js must come from installed catalogue font
 *    files (sha256), and every text drawn on a canvas (ctx.font, TX.raster) must name an installed family FIRST that
 *    covers every character (no glyph may fall back to a system font).
 *
 * Exit code 1 on any failure. Needs a browser: node setup_browser.mjs (same as snapshot.mjs).
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { auditFonts, stackProblems, genericFirstStacks, fontHooks, webFontSources, verifyWebFonts, domFontsNow } from './lib/fonts.mjs';
import { auditGlyphs, familiesOf, uncovered, canvasTextProblems } from './lib/glyphs.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = { _: [] };
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith('--')) opt[argv[i].slice(2)] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  else opt._.push(argv[i]);
}
const dir = path.resolve(opt._[0] || '.');
if (!fs.existsSync(path.join(dir, 'index.html'))) { console.error(`no index.html in ${dir}`); process.exit(2); }

const fails = [];
const notes = [];
const read = (p) => fs.readFileSync(path.join(dir, p), 'utf8');

// ---------- 1. static (catalogue: family allowed, file unmodified, licence present, no stray names) ----------
const fa = auditFonts(dir);
fails.push(...fa.errors);
for (const b of stackProblems(dir, fa.families)) fails.push(`${b} is not an installed catalogue font — use a catalogued font (add_font.mjs --list) + a generic fallback`);
for (const g of genericFirstStacks(dir)) fails.push(`${g} — a generic family first always matches, so a system font draws the text: put the installed family first ('Pretendard', sans-serif)`);
notes.push(`SIL OFL 1.1 fonts installed in this project (catalogue + fonts.lock.json): ${[...fa.used].join(', ') || '(none)'}`);

// ---------- 2. runtime ----------
let chromium;
try { ({ chromium } = await import('playwright-core')); } catch {
  console.error(`playwright-core is not installed. Run once:\n  node ${path.join(here, 'setup_browser.mjs')}`); process.exit(3);
}
function browserConfig() {
  try {
    const c = JSON.parse(fs.readFileSync(path.join(os.homedir(), '.cache', 'motion-video-deps', 'browser.json'), 'utf8'));
    if (c.executablePath && fs.existsSync(c.executablePath)) return c;
  } catch { /* none yet */ }
  return null;
}
const cfg = browserConfig();
const env = { ...process.env };
if (cfg && cfg.libDirs && cfg.libDirs.length) env.LD_LIBRARY_PATH = [...cfg.libDirs, env.LD_LIBRARY_PATH].filter(Boolean).join(':');
let browser;
try { browser = await chromium.launch({ env, ...(cfg ? { executablePath: cfg.executablePath } : {}) }); } catch (e) {
  console.error('✖ no working browser yet. Run once: node ' + path.join(here, 'setup_browser.mjs')); process.exit(4);
}
const W = Number((read('index.html').match(/data-width="(\d+)"/) || [])[1] || 1920);
const H = Number((read('index.html').match(/data-height="(\d+)"/) || [])[1] || 1080);
const page = await (await browser.newContext({ viewport: { width: W, height: H } })).newPage();
const logs = [];
page.on('pageerror', (e) => logs.push(`page error: ${e.message}`));
// every FontFace a script makes (with its source) and every text any canvas draws, with its font
await page.addInitScript(fontHooks);
await page.goto(pathToFileURL(path.join(dir, 'index.html')).href + '?captions');
await page.addStyleTag({ content: '.vp-start { display: none !important; }' });
await page.waitForFunction(() => document.body.classList.contains('vp-ready') || document.querySelector('.vp-error'), null, { timeout: 30000 })
  .catch(() => {});
const bootError = await page.evaluate(() => (document.querySelector('.vp-error') || {}).textContent || (document.body.classList.contains('vp-ready') ? '' : 'the player did not become ready within 30 s'));
if (bootError) {
  // a page whose build threw shows only the error screen: nothing of the video was checked
  console.log(`fonts · ${path.basename(dir)}\n✖ player error: ${bootError}`);
  for (const l of logs) console.log('  ' + l);
  await browser.close();
  process.exit(1);
}
const cdp = await page.context().newCDPSession(page);
await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
await cdp.send('DOM.getDocument', { depth: 0 });
const info = await page.evaluate(() => ({ duration: window.__video.duration, cues: window.VIDEO_DATA.cues.map((c) => [c.start, c.end]) }));
const step = opt.step != null ? Number(opt.step) : 0.5;
const cueTimes = [0.2, ...info.cues.flatMap(([a, b]) => [(a + b) / 2, Math.max(a, b - 0.1)]), info.duration - 0.05];
const grid = step > 0 ? Array.from({ length: Math.floor(info.duration / step) + 1 }, (_, i) => i * step) : [];
const times = [...new Set([...grid, ...cueTimes].map((t) => +Math.max(0, Math.min(info.duration - 0.02, t)).toFixed(2)))].sort((a, b) => a - b);
const used = new Map();       // family → { custom, glyphs }
const platform = new Map();   // family → [{ t, text }]
for (const t of times) {
  await page.evaluate((tt) => window.__video.seek(tt), t);
  // the elements are found again after every seek (a label built later counts), each new text + font setting once
  for (const { text, fonts } of await domFontsNow(cdp, '#stage')) {
    for (const f of fonts) {
      const u = used.get(f.familyName) || { custom: f.isCustomFont, glyphs: 0 };
      u.glyphs += f.glyphCount; used.set(f.familyName, u);
      if (!f.isCustomFont) {
        const list = platform.get(f.familyName) || [];
        if (list.length < 5) list.push({ t, text });
        platform.set(f.familyName, list);
      }
    }
  }
}
// every web font the page has must be an installed file of its own family (not local(), remote, data: or another file)
const web = verifyWebFonts(dir, await webFontSources(page));
fails.push(...web.errors);
// ---------- 3. type that is not DOM text (TypeFX outlines and canvas text) ----------
const typefx = await page.evaluate(() => window.__typefx || { rasters: [], glyphs: [] });
const canvasText = await page.evaluate(() => (window.__canvasText ? [...window.__canvasText.values()] : []));
await browser.close();
const ga = auditGlyphs(dir);
fails.push(...ga.errors);
const gl = Object.values(ga.entries);
if (gl.length) notes.push(`glyph outlines: ${gl.map((e) => `"${e.text.replace(/\n/g, ' ').slice(0, 16)}" (${e.font.family} ${e.weight})`).join(', ')} — from the installed, unmodified font files`);
for (const r of typefx.rasters || []) {
  const fams = familiesOf(r.family || r.font);
  const first = fams[0];
  if (!first || !fa.families.has(first.toLowerCase())) { fails.push(`canvas text "${r.text.slice(0, 30)}" uses font "${r.family || r.font}" — name an installed catalogue family first (TX.raster({ family: "'Pretendard'" }))`); continue; }
  const cov = await uncovered(dir, fams, r.text);
  if (cov.skipped) { fails.push(`canvas text "${r.text.slice(0, 30)}" could not be checked (${cov.skipped}) — npm install in the skill's scripts folder`); continue; }
  if (cov.unknown && cov.unknown.length) fails.push(`canvas text "${r.text.slice(0, 30)}": ${cov.unknown.join(', ')} is not a catalogue font`);
  if (cov.missing.length) fails.push(`canvas text "${r.text.slice(0, 30)}": ${fams.join(', ')} has no glyph for ${cov.missing.map((c) => JSON.stringify(c)).join(' ')} — the canvas would draw them with a system font`);
  else notes.push(`canvas text "${r.text.replace(/\n/g, ' ').slice(0, 24)}" (${first} ${r.weight || ''}) — every character covered`);
}
// every canvas fillText/strokeText seen during the sweep: its font must name an installed family first that covers each character
{
  const ct = await canvasTextProblems(dir, canvasText, fa.families);
  fails.push(...ct.fails);
  notes.push(...ct.notes);
}
for (const [fam, list] of platform) {
  fails.push(`platform font "${fam}" rendered on screen — e.g. ${list.map((x) => `t=${x.t.toFixed(2)} "${x.text}"`).join(' · ')}. ` +
    'An installed catalogue font lacks these glyphs or a stack names a system font: change the text, or install an SIL OFL 1.1 catalogue font that covers them (add_font.mjs).');
}

// ---------- report ----------
console.log(`fonts · ${path.basename(dir)} · ${times.length} moments checked (${step > 0 ? `every ${step} s + ` : ''}each cue's middle and end)`);
for (const n of notes) console.log('  ' + n);
for (const [fam, u] of [...used].sort((a, b) => b[1].glyphs - a[1].glyphs)) {
  // a web font is "installed OFL" only when every web font source of the page was verified above
  const label = !u.custom ? '✖ SYSTEM       ' : web.errors.length ? '? web font     ' : '✓ installed OFL';
  console.log(`  ${label} ${fam}  (${u.glyphs} glyphs)`);
}
if (fails.length) {
  console.log(`\n✖ ${fails.length} font problem(s):`);
  for (const f of fails) console.log('  - ' + f);
  if (web.errors.length) console.log('  (? web font: drawn by a web font, but not every web font of the page is an installed file — see above)');
  process.exit(1);
}
console.log('\n✓ every glyph on screen is drawn with an installed SIL OFL 1.1 font (catalogue or pinned Google Fonts ofl/); every font has its OFL licence file');
