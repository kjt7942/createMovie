#!/usr/bin/env node
/**
 * wave.mjs — the sound as numbers, for the agent to read. It prepares the level data and nothing more: where there is
 * silence, which silence is dead air, what to cut and when a phrase starts are decided by the agent reading these numbers
 * (references/sound.md §1, §2). No code in the skill decides where silence is.
 *
 *   node wave.mjs <dir> [--from 0] [--to end] [--step 0.05] [--no-narration] [--zcr]
 *       the finished sound — audio/narration.wav plus every clip that plays its own sound, at its placement and volume
 *       (envelope × level match, held within 0–1 as the player plays it; js/media.js) — one line per second, each number
 *       the level (RMS, dBFS, rounded) of one --step window, the cues, clips, joins of cut takes and the end marked where
 *       they fall. --no-narration: the clips' own sound alone (what a dub track's lines are placed around, dub.mjs).
 *       --zcr: each window's zero-crossing rate too, as with takes
 *   node wave.mjs <dir> --cue c05[,c06,…] [--from s] [--to s] [--step 0.05]      (also <dir>/dub/<lang>)
 *   node wave.mjs <dir> --unreviewed                          every take not read yet (unreviewed: true in js/cues.js)
 *       each take on its own clock (.tts-cache/<take>.pcm) — exactly as Fish Audio returned it, or, for a take cached
 *       before 2026-11-09, as the old tts.mjs stored it after cutting its edges — with the stretches its script.json
 *       "cut" takes out marked: read the times for a cut, and for a phrase's start ("at"), here. --step 0.01 for 10 ms;
 *       --from / --to: only that stretch of each take (seconds in the take) — the part around a phrase.
 *       Every window of a take is printed as level/zero-crossing rate
 *
 * The numbers: level = RMS of the window in dBFS, rounded (−inf: every sample 0). Zero-crossing rate = how many times the
 * waveform changes sign in the window (a sample below 0 next to one at or above 0), per millisecond, one decimal. Both
 * are only measured; what a window is — voice, breath, room tone, silence — is the agent's reading (references/sound.md §1).
 *
 * Marks, placed before the window they fall in:  |c05 a cue starts · c05| it ends · |c05(placeholder) a cue not recorded
 * yet (silent) · [clip:key … clip:key] a clip playing its own sound · ✂ a cut take joined · END the video's end ·
 * --cue: ✂[ … ]✂ a stretch the cut removes. −inf = digital silence (every sample 0).
 * Needs ffmpeg (the narration and the clips' sound are decoded with it).
 */
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import vm from 'node:vm';
import { launch, openPage, parseArgs } from './lib/browser.mjs';

const opt = parseArgs();
const dir = path.resolve(opt._[0] || '.');
const STEP = +(opt.step || 0.05);
if (!(STEP > 0)) { console.error('✖ --step must be a positive number of seconds'); process.exit(2); }
const die = (m, code = 2) => { console.error('✖ ' + m); process.exit(code); };
const fmt = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, '0')}`;   // a line's true start, to 0.01 s (--from 2.15 starts at 0:02.15)
const db = (sum, n) => (sum > 0 ? String(Math.round(10 * Math.log10(sum / n))) : '-inf');

/** one line per second: [time, tokens] — the level of every STEP window (with zcr: level/zero-crossing rate), with marks
 *  before the window they fall in */
function lines(x, sr, t0, marks, zcr = false) {
  const w = Math.round(STEP * sr), perLine = Math.max(1, Math.round(1 / STEP));
  const ms = [...marks].sort((a, b) => a.t - b.t || a.o - b.o);
  const out = [];
  let m = 0, line = null;
  for (let k = 0; k * w < x.length; k++) {
    const a = t0 + k * STEP;
    if (k % perLine === 0) { line = [fmt(a)]; out.push(line); }
    while (m < ms.length && ms[m].t < a + STEP - 1e-9) line.push(ms[m++].s);
    let s = 0, z = 0;
    const i0 = k * w, n = Math.min(w, x.length - i0);
    for (let j = 0; j < n; j++) {
      const v = x[i0 + j];
      s += v * v;
      if (i0 + j > 0 && (v < 0) !== (x[i0 + j - 1] < 0)) z++;   // a sign change from the sample before (across windows too)
    }
    line.push(zcr ? `${db(s, n)}/${(z / (n / sr * 1000)).toFixed(1)}` : db(s, n));
  }
  while (m < ms.length) line.push(ms[m++].s);   // marks at the very end (END)
  return out.map((l) => l[0] + '  ' + l.slice(1).join(' '));
}

// takes: read from js/cues.js and .tts-cache alone (no page, no ffmpeg) — so a dub folder (dub/<lang>) reads the same way
if (opt.cue || opt.unreviewed) {
  const cuesFile = path.join(dir, 'js', 'cues.js');
  if (!fs.existsSync(cuesFile)) die(`no js/cues.js in ${dir} — run tts.mjs first`);
  const box = { window: {} };
  vm.runInNewContext(fs.readFileSync(cuesFile, 'utf8'), box);
  const all = box.window.VIDEO_DATA.cues;
  let pick;
  if (opt.unreviewed) {
    pick = all.filter((c) => c.unreviewed);
    if (!pick.length) { console.log('no take is waiting to be read (no unreviewed: true in js/cues.js)'); process.exit(0); }
  } else {
    pick = String(opt.cue).split(',').map((s) => s.trim()).filter(Boolean).map((id) => all.find((x) => x.id === id) || die(`--cue ${id}: no such cue in js/cues.js`));
  }
  console.log(`each window of ${Math.round(STEP * 1000)} ms: level (RMS dBFS) / zero-crossing rate (sign changes per ms) · one line = 1 s of the take · times are seconds in the take (what a "cut" range and an "at" time use)`);
  for (const c of pick) {
    if (!c.take) die(`--cue ${c.id}: no recorded take (a placeholder, or a js/cues.js from before takes had ids — run tts.mjs again)`);
    const file = path.join(dir, '.tts-cache', `${c.take}.pcm`);
    if (!fs.existsSync(file)) die(`${path.relative(dir, file)} is missing — the take itself is needed to read it`);
    const b = fs.readFileSync(file), SR = 44100;   // (tts.mjs keeps its takes as 16-bit mono at 44.1 kHz)
    const x = new Float32Array(b.length >> 1);
    for (let i = 0; i < x.length; i++) x[i] = b.readInt16LE(2 * i) / 32768;
    const len = x.length / SR;
    const a0 = opt.from != null ? Math.max(0, Math.min(len, +opt.from)) : 0, b0 = opt.to != null ? Math.max(a0, Math.min(len, +opt.to)) : len;
    const part = x.subarray(Math.round(a0 * SR), Math.round(b0 * SR));
    const marks = (c.cut || []).flatMap(([a, e]) => [{ t: a, o: 1, s: '✂[' }, { t: e, o: 0, s: ']✂' }]).filter((m) => m.t >= a0 - 1e-9 && m.t <= b0 + 1e-9);
    console.log('');
    console.log(`${c.id} · take ${c.take} · ${len.toFixed(3)} s${a0 > 0 || b0 < len ? ` · showing ${a0.toFixed(2)}–${b0.toFixed(2)} s` : ''} · ` +
      (c.asRecorded ? 'exactly as recorded' : 'cached before 2026-11-09: its edges were cut by the old tts.mjs before it was stored (what was cut is gone)') +
      ` · ${c.cut ? `cut: ${JSON.stringify(c.cut)} (✂[ … ]✂)` : c.unreviewed ? 'not read yet — no cut set' : 'no cut'} · "${c.text}"`);
    for (const l of lines(part, SR, a0, marks, true)) console.log(l);
  }
  process.exit(0);
}

if (spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' }).error) die('ffmpeg not found — wave.mjs decodes the narration and the clips\' sound with it (Mac: brew install ffmpeg). Nothing was measured.');
const browser = await launch();
const page = await openPage(browser, dir);
const info = await page.evaluate(() => ({ dur: window.__video.duration, audio: window.__media ? window.__media.audio() : [],
  cues: window.VIDEO_DATA.cues, audioFile: window.VIDEO_DATA.audio, narration: window.VIDEO_DATA.narration !== false }));
await browser.close();

// the finished sound of [from, to)
const from = Math.max(0, +(opt.from || 0)), to = Math.min(info.dur, opt.to != null ? +opt.to : info.dur);
if (!(to > from)) die(`the range is empty (the video is ${info.dur.toFixed(2)} s)`);
const SR = 16000, n = Math.round((to - from) * SR), mix = new Float32Array(n);
const decode = (file, ss, dur) => {
  const a = ['-v', 'error', '-ss', String(ss), '-i', file, '-t', String(dur), '-f', 'f32le', '-ac', '1', '-ar', String(SR), '-'];
  let buf;
  try { buf = execFileSync('ffmpeg', a, { maxBuffer: 1 << 30, stdio: ['ignore', 'pipe', 'pipe'] }); } catch (err) {
    die(`ffmpeg could not decode ${path.relative(dir, file) || file}: ${String(err.stderr || err.message).trim().split('\n').pop()} — nothing was measured`);
  }
  return new Float32Array(buf.buffer, buf.byteOffset, buf.length / 4);
};
const volAt = (v, lt) => {
  if (typeof v === 'number') return v;
  if (lt <= v[0][0]) return v[0][1];
  for (let i = 1; i < v.length; i++) if (lt <= v[i][0]) { const [x0, a] = v[i - 1], [x1, b] = v[i]; return a + ((b - a) * (lt - x0)) / Math.max(1e-6, x1 - x0); }
  return v[v.length - 1][1];
};
const narrationFile = path.join(dir, 'audio/narration.wav');
const withNarration = !opt['no-narration'];
if (withNarration && fs.existsSync(narrationFile)) {
  const s = decode(narrationFile, from, to - from);
  for (let i = 0; i < Math.min(n, s.length); i++) mix[i] += s[i];
}
const clips = [];
for (const c of info.audio) {
  const a = Math.max(from, c.start), b = Math.min(to, c.start + c.dur);
  if (b <= a) continue;
  clips.push(c);
  const s = decode(path.resolve(dir, c.file), c.in + (a - c.start) * c.rate, (b - a) * c.rate);
  const o = Math.round((a - from) * SR);
  for (let i = 0; i < s.length && o + i < n; i++) mix[o + i] += s[i] * Math.min(1, Math.max(0, volAt(c.vol, a - c.start + i / SR)));
}
const marks = [];
for (const c of info.cues) {
  marks.push({ t: c.start, o: 1, s: `|${c.id}${c.placeholder ? '(placeholder)' : ''}` }, { t: c.end, o: 0, s: `${c.id}|` });
  let gone = 0;
  for (const [a, b] of c.cut || []) { marks.push({ t: c.start + a - gone, o: 0.5, s: '✂' }); gone += b - a; }
}
for (const c of info.audio) marks.push({ t: c.start, o: 1, s: `[clip:${c.key}` }, { t: c.start + c.dur, o: 0, s: `clip:${c.key}]` });
marks.push({ t: info.dur, o: 2, s: 'END' });
const inRange = marks.filter((m) => m.t >= from - 1e-9 && m.t <= to + 1e-9);
const ph = info.cues.filter((c) => c.placeholder).length;
console.log(`sound ${fmt(from)} – ${fmt(to)} of ${fmt(info.dur)} · ${!withNarration ? 'the narration left out (--no-narration): the clips\' own sound alone' : info.narration ? 'audio/narration.wav' : 'no narration ("narration": false)'}${clips.length ? ` + ${clips.length} clip(s) with sound: ${[...new Set(clips.map((c) => c.key))].join(', ')}` : ''}${ph ? ` · ${ph} cue(s) not recorded yet (silent)` : ''}`);
console.log(`each ${opt.zcr ? 'window' : 'number'} of ${Math.round(STEP * 1000)} ms: level (RMS dBFS)${opt.zcr ? ' / zero-crossing rate (sign changes per ms)' : ''} · one line = 1 s · |id cue starts, id| ends · [clip:key … clip:key] · ✂ cut take joined · END`);
for (const l of lines(mix, SR, from, inRange, !!opt.zcr)) console.log(l);
