#!/usr/bin/env node
/**
 * media_info.mjs — the js/media-src.js entry for a clip: pixel size, length and integrated loudness of the master, and
 * (with --copy) a light playback copy for the browser. Paste the printed line into window.MEDIA_SRC.clips and list the
 * file in provenance.json (source: "user"). references/footage.md.
 *
 *   node media_info.mjs <projectDir> <key> <master.mp4> [--copy]     --copy: assets/user/vid/<key>.mp4 (H.264 CRF 20,
 *                                                                     AAC 160k, faststart — what the player streams)
 */
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { parseArgs } from './lib/browser.mjs';

const opt = parseArgs();
const [d, key, master] = opt._;
if (!d || !key || !master) { console.error('usage: node media_info.mjs <projectDir> <key> <master.mp4> [--copy]'); process.exit(2); }
const dir = path.resolve(d), src = path.resolve(master);
const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries',
  'stream=codec_type,width,height:stream_tags=rotate:stream_side_data=rotation:format=duration', '-of', 'json', src], { encoding: 'utf8' }));
const v = probe.streams.find((s) => s.codec_type === 'video'), hasAudio = probe.streams.some((s) => s.codec_type === 'audio');
if (!v) { console.error(`✖ ${master}: no video stream`); process.exit(1); }
// a phone video stored sideways (display-matrix rotation, or the older `rotate` tag): ffmpeg (stills.mjs, the playback
// copy) and the browser show it upright, so the entry carries the upright size — as render.py's probe() does
const rot = Number((v.side_data_list || []).find((x) => x.rotation != null)?.rotation ?? v.tags?.rotate ?? 0);
const [vw, vh] = Math.round(Math.abs(rot)) % 180 === 90 ? [v.height, v.width] : [v.width, v.height];
const dur = +(+probe.format.duration).toFixed(2);
let lufs = null;
if (hasAudio) {
  const e = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', src, '-af', 'ebur128', '-f', 'null', '-'], { encoding: 'utf8', maxBuffer: 1 << 26 }).stderr;
  lufs = +/I:\s+(-?[\d.]+) LUFS/.exec(e.slice(e.lastIndexOf('Summary')))[1];
}
const file = `assets/user/vid/${key}.mp4`;
if (opt.copy) {
  fs.mkdirSync(path.join(dir, 'assets/user/vid'), { recursive: true });
  // even width and height (yuv420p needs them: a 1281×721 master would make libx264 fail); written to a temp name and
  // moved into place only when ffmpeg succeeded, so a failure leaves no empty or half-written copy behind
  const out = path.join(dir, file), part = `${out}.part`;
  try {
    execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', src, '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-crf', '20',
      '-preset', 'medium', '-pix_fmt', 'yuv420p', ...(hasAudio ? ['-c:a', 'aac', '-b:a', '160k'] : ['-an']), '-movflags', '+faststart',
      '-f', 'mp4', part], { stdio: ['ignore', 'inherit', 'inherit'] });
    fs.renameSync(part, out);
  } catch (e) {
    fs.rmSync(part, { recursive: true, force: true });
    console.error(`✖ the playback copy failed (ffmpeg, see above) — ${file} not written`);
    process.exit(1);
  }
}
const rel = path.relative(dir, src);
const entry = { file, master: rel.startsWith('..') ? src : rel, w: vw, h: vh, dur, ...(lufs != null ? { lufs } : {}) };
console.log(`    ${key}: ${JSON.stringify(entry).replace(/"(\w+)":/g, '$1: ').replace(/,(?=\w)/g, ', ')},`);
if (!opt.copy) console.log(`(no playback copy yet: add --copy to write ${file})`);
