#!/usr/bin/env node
/**
 * stills.mjs — the footage frames the review tools see. Headless Chromium has no H.264 decoder, so in review mode
 * (?stills — snapshot.mjs, check_fonts.mjs, errscan.mjs) js/media.js shows pre-extracted JPEG frames instead of <video>.
 * This cuts them: for every clip placement (MEDIA.clip), <out>/<placement id>/00001.jpg … at <fps>, cropped and scaled
 * like the placement, from the clip's master (js/media-src.js). A placement already cut is kept when it has this fps's
 * frame count at this size or larger (frames cut for a 4K render serve 1080p and sheets as they are); a smaller cut or
 * another fps is cut again — render.py stops on frames smaller than its resolution needs and prints this command.
 * Every frame is recorded in the project's generated.json with its sha256 (lib/generated.mjs); a placement is kept only
 * when all its frames are recorded there unchanged — frames without a record (cut before the tools kept it) are cut again.
 *
 *   node stills.mjs <projectDir> [--out media/stills] [--fps 10] [--scale 0.5] [--jobs 6]
 *
 * Re-run after adding or moving a placement. Needs ffmpeg. references/footage.md.
 */
import fs from 'node:fs';
import path from 'node:path';
import { launch, openPage, run, pool, parseArgs } from './lib/browser.mjs';
import { projectOf, readRecord, recordGenerated, sha256File } from './lib/generated.mjs';

const opt = parseArgs();
const dir = path.resolve(opt._[0] || '.');
const OUT = path.resolve(dir, opt.out || 'media/stills');
const FPS = +(opt.fps || 10), SCALE = +(opt.scale || 0.5), JOBS = +(opt.jobs || 6);

// a JPEG's width in pixels, read from its frame header (0 when it can't be read)
function jpegWidth(f) {
  const b = Buffer.alloc(65536);
  let len = 0;
  try { const fd = fs.openSync(f, 'r'); len = fs.readSync(fd, b, 0, b.length, 0); fs.closeSync(fd); } catch { return 0; }
  if (b[0] !== 0xff || b[1] !== 0xd8) return 0;
  for (let i = 2; i + 9 <= len;) {
    if (b[i] !== 0xff) return 0;
    const m = b[i + 1];
    if (m === 0xff) i += 1;                                            // a fill byte
    else if ((m >= 0xd0 && m <= 0xd8) || m === 0x01) i += 2;           // markers without a length
    else if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) return b.readUInt16BE(i + 7);   // frame header
    else i += 2 + b.readUInt16BE(i + 2);
  }
  return 0;
}

const browser = await launch();
const page = await openPage(browser, dir);
const list = await page.evaluate(() => (window.__media ? window.__media.list() : []));
await browser.close();
const uniq = [...new Map(list.map((m) => [m.id, m])).values()];
if (!uniq.length) { console.log('no clip placements (js/media.js) — nothing to cut'); process.exit(0); }
console.log(`${uniq.length} placements → ${path.relative(process.cwd(), OUT) || '.'} (${FPS} fps, scale ${SCALE})`);
fs.mkdirSync(OUT, { recursive: true });
let done = 0, kept = 0, cut = 0;
const missing = new Set();
const ROOT = projectOf(dir) || dir;
const rec = readRecord(ROOT);
const recorded = (f) => { const e = rec.files[path.relative(ROOT, f).split(path.sep).join('/')]; return !!e && e.sha256 === sha256File(f); };
const cutDirs = [];
await pool(uniq, JOBS, async (m) => {
  const d = path.join(OUT, m.id), n = Math.max(1, Math.ceil(m.dur * FPS - 1e-6));
  const wpx = Math.max(64, Math.round((m.res * SCALE) / 2) * 2);
  // kept: exactly this fps's frame count, at least this wide (2 px: one rounding step of a scale typed as 0.4444 for 4/9)
  const have = fs.existsSync(d) ? fs.readdirSync(d).filter((f) => /^\d{5}\.jpg$/.test(f)) : [];
  if (have.length === n && jpegWidth(path.join(d, '00001.jpg')) >= wpx - 2 && have.every((f) => recorded(path.join(d, f)))) { kept++; done++; return; }
  const master = path.resolve(dir, m.master);
  if (!fs.existsSync(master)) { missing.add(m.master); done++; return; }   // (frames already there are left as they are)
  for (const f of have) fs.unlinkSync(path.join(d, f));                     // an earlier cut at another size or fps
  fs.mkdirSync(d, { recursive: true });
  const [cx, cy, cw, ch] = m.crop.map((v) => Math.round(v));
  await run('ffmpeg', ['-v', 'error', '-y', '-ss', String(m.in), '-i', master, '-vf',
    `crop=${cw}:${ch}:${cx}:${cy},scale=${wpx}:-2:flags=lanczos,setpts=(PTS-STARTPTS)/${m.rate},fps=${FPS},tpad=stop_mode=clone:stop=${n}`,
    '-frames:v', String(n), '-q:v', '3', path.join(d, '%05d.jpg')]);
  cutDirs.push(d);
  cut++; done++;
  if (done % 5 === 0 || done === uniq.length) console.log(`  ${done}/${uniq.length}`);
});
recordGenerated(cutDirs.flatMap((d) => fs.readdirSync(d).filter((f) => /^\d{5}\.jpg$/.test(f)).map((f) => path.join(d, f))), 'stills.mjs');
if (missing.size) console.log(`⚠ skipped — master not found: ${[...missing].join(', ')}`);
console.log(`stills ready — ${cut} cut, ${kept} kept (already this fps, this size or larger)`);
