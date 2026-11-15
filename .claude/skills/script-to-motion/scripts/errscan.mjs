#!/usr/bin/env node
/**
 * errscan.mjs — the cheap runtime gate in a real browser, with no screenshots: loads the page in review mode, seeks through
 * the whole video (or a range) and lists page errors and console errors/warnings — a segment that threw, a phrase that
 * when() couldn't find, a stale js/sync.js, a missing scene element. Use it after every change while the user reviews the
 * picture themselves (references/collaboration.md); snapshot.mjs is for when you need to see frames.
 *
 *   node errscan.mjs <projectDir> [--from 0] [--to end] [--step 0.5]
 *
 * Exit code 1 when anything was reported.
 */
import path from 'node:path';
import { launch, openPage, parseArgs } from './lib/browser.mjs';

const opt = parseArgs();
const dir = path.resolve(opt._[0] || '.');
const errors = [];
const browser = await launch();
let page;
try { page = await openPage(browser, dir, { errors }); } catch (e) {
  // the build threw: the page shows only its error screen
  await browser.close();
  for (const x of new Set([String(e.message || e), ...errors])) console.log('✖ ' + x);
  console.log('the video did not build — nothing was seeked');
  process.exit(1);
}
const r = await page.evaluate(async ([a, z, s]) => {
  const V = window.__video, end = Math.min(z, V.duration);
  let n = 0;
  for (let t = a; t <= end + 1e-9; t += s) { V.seek(t); n++; if (n % 20 === 0) await new Promise((ok) => requestAnimationFrame(ok)); }
  V.seek(end);
  return { n, end };
}, [+(opt.from || 0), opt.to != null ? +opt.to : 1e9, +(opt.step || 0.5)]);
await browser.close();
const uniq = [...new Set(errors)];
for (const e of uniq) console.log('✖ ' + e);
console.log(`${uniq.length ? uniq.length + ' problem(s)' : 'no errors or warnings'} · ${r.n} seeks to ${r.end.toFixed(2)} s`);
process.exit(uniq.length ? 1 : 0);
