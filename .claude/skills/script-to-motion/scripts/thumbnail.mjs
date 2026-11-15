#!/usr/bin/env node
/**
 * thumbnail.mjs — a still image from an HTML page you designed (the video's thumbnail, a cover, a card): the same OFL
 * fonts and drawing code as the video, rendered in headless Chromium after the fonts and images are ready.
 *
 *   node thumbnail.mjs <page.html> [--out thumbnail.png] [--size 1280x720] [--project <dir>]
 *
 * Reports page errors, fonts that didn't load and images that failed, and checks the fonts like check_fonts.mjs: every
 * glyph on the page must be drawn by an installed SIL OFL 1.1 font of the project (the folder above the page that has
 * index.html, or --project), every web font must be one of its installed, unmodified files, and canvas text must name an
 * installed family first. Exit code 1 on any problem.
 */
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { launch, parseArgs } from './lib/browser.mjs';
import { auditFonts, fontHooks, webFontSources, verifyWebFonts, domFontsNow } from './lib/fonts.mjs';
import { canvasTextProblems } from './lib/glyphs.mjs';
import { recordGenerated } from './lib/generated.mjs';

const opt = parseArgs();
const file = path.resolve(opt._[0] || 'thumbnail.html');
if (!fs.existsSync(file)) { console.error(`✖ no ${file}`); process.exit(2); }
const [w, h] = String(opt.size || '1280x720').split('x').map(Number);
const out = path.resolve(opt.out || path.join(path.dirname(file), 'thumbnail.png'));
// the video project whose installed fonts the page may use: --project, else the nearest folder above with index.html + fonts/
let project = typeof opt.project === 'string' ? path.resolve(opt.project) : null;
for (let d = path.dirname(file); !project; d = path.dirname(d)) {
  if (fs.existsSync(path.join(d, 'index.html')) && fs.existsSync(path.join(d, 'fonts'))) project = d;
  if (path.dirname(d) === d) break;
}
const errors = [];
const browser = await launch();
const page = await browser.newPage({ viewport: { width: w, height: h } });
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
// a thumbnail is made from the project's own files: every request the page sends to the network is a problem
page.on('request', (r) => { if (!/^(file|data|blob|about):/i.test(r.url())) errors.push(`network request: ${r.url().slice(0, 160)} — use the project's own files (fonts via add_font.mjs, pictures drawn in code or the user's in assets/user/)`); });
await page.addInitScript(fontHooks);
await page.goto(pathToFileURL(file).href);
await page.evaluate(() => document.fonts.ready);
const st = await page.evaluate(async () => {
  await Promise.all([...document.images].map((i) => (i.complete ? null : i.decode().catch(() => null))));
  return { fonts: [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family.replace(/["']/g, '')),
    failedFonts: [...document.fonts].filter((f) => f.status === 'error').map((f) => f.family),
    badImages: [...document.images].filter((i) => !i.naturalWidth).map((i) => i.getAttribute('src')) };
});
await page.waitForTimeout(200);
fs.mkdirSync(path.dirname(out), { recursive: true });
await page.screenshot({ path: out });
recordGenerated([out], 'thumbnail.mjs');   // generated.json: check.mjs accepts the image as the skill's own
// fonts: which font files drew every visible text (CDP), where every web font came from, what canvases drew text in
const fontFails = [];
const drawnBy = new Map();
{
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
  await cdp.send('DOM.getDocument', { depth: 0 });
  for (const { text, fonts } of await domFontsNow(cdp, 'body')) {
    for (const f of fonts) {
      drawnBy.set(f.familyName, f.isCustomFont);
      if (!f.isCustomFont) fontFails.push(`platform font "${f.familyName}" drew "${text}" — a system font: name an installed OFL family first, or install one that covers these glyphs (add_font.mjs)`);
    }
  }
  if (!project) fontFails.push(`no video project above ${path.dirname(file)} (a folder with index.html and fonts/) — pass --project <dir> so the page's fonts can be checked against its installed fonts`);
  else {
    const fa = auditFonts(project);
    fontFails.push(...verifyWebFonts(project, await webFontSources(page)).errors);
    const canvasText = await page.evaluate(() => (window.__canvasText ? [...window.__canvasText.values()] : []));
    fontFails.push(...(await canvasTextProblems(project, canvasText, fa.families)).fails);
  }
}
await browser.close();
const problems = [...new Set(fontFails)];
for (const e of errors) console.log('✖ ' + e);
for (const f of st.failedFonts) console.log('✖ font failed to load: ' + f);
for (const i of st.badImages) console.log('✖ image failed: ' + i);
for (const f of problems) console.log('✖ ' + f);
console.log(`${path.relative(process.cwd(), out)} · ${w}×${h} · fonts: ${[...new Set(st.fonts)].join(', ') || 'none'} · drawn by: ${[...drawnBy].map(([n, c]) => `${n}${c ? '' : ' (SYSTEM)'}`).join(', ') || 'no text'}`);
process.exit(errors.length || st.failedFonts.length || st.badImages.length || problems.length ? 1 : 0);
