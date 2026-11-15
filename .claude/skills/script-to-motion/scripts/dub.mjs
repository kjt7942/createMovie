#!/usr/bin/env node
/**
 * dub.mjs — a dubbed audio track in another language, the same length as the video, for YouTube's audio tracks.
 * The other language's narration is recorded with the same voice, each line is placed where
 * the original line starts, and the footage's own sound is mixed in exactly as the player plays it.
 *
 *   node dub.mjs <projectDir> --lang en --init         dub/en/script.json from subs.json's translations (voice, model and
 *                                                       settings copied; say = text): then write the spoken forms in `say`
 *   node tts.mjs <projectDir>/dub/en                    silent placeholders with estimated timing, no API call: --report
 *                                                       then shows the estimated fit before anything is recorded
 *   node tts.mjs <projectDir>/dub/en --approved         record the takes, once the user decided to record the dub (their
 *                                                       key and voice from the skill's .env, model drama-3)
 *   node dub.mjs <projectDir> --lang en --report        how each take fits its room; writes nothing (--json: every line)
 *   node dub.mjs <projectDir> --lang en [--out file.wav]   → dub/en/<name>.en.wav (48 kHz stereo) — recorded takes only:
 *                                                       refused while a line is a placeholder or its take is stale
 *
 * No code here decides where the footage's sound is up or where there is silence — that is the agent's call, read from
 * numbers (references/sound.md §1). A line's room: from its original start to the next line's start (−0.12 s), plain
 * arithmetic on the cue times — unless a clip that plays its own sound is placed in that stretch (known exactly from the
 * clips' placements on the timeline, not from any level). Such a line needs the agent's own room, read off
 *   node wave.mjs <dir> --no-narration --from … --to …      (the footage's sound alone, as numbers)
 * and written in dub/<lang>/script.json as the cue's "room": [start, end] (seconds of the video): the take starts at
 * start and must end by end. Every take plays exactly as it was recorded — the voice is never slowed down or sped up (no
 * time-stretch here, no TTS speed in tts.mjs): a take longer than its room is refused, reword it shorter. --report prints
 * every line's room, take, what is left and the air to the next line as numbers; whether that air is dead air is the
 * agent's call. The dub's takes are read and cut like the original's (tts.mjs "cut", wave.mjs <dir>/dub/<lang> --cue).
 * The narration is level-matched to the original narration, then compressed, normalised to −16 LUFS and limited at −2 dBFS.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { execFileSync, spawnSync } from 'node:child_process';
import { launch, openPage, parseArgs } from './lib/browser.mjs';
import { recordGenerated } from './lib/generated.mjs';

const opt = parseArgs();
const dir = path.resolve(opt._[0] || '.');
const lang = opt.lang;
if (!lang) { console.error('✖ --lang <code> is required (e.g. --lang en)'); process.exit(2); }
if (opt.max != null || opt.min != null) { console.error('✖ --max / --min are gone: the voice is never slowed down or sped up — reword a line that does not fit its room (--report lists them)'); process.exit(2); }
const DUB = path.join(dir, 'dub', lang);

if (opt.init) {
  const src = JSON.parse(fs.readFileSync(path.join(dir, 'script.json'), 'utf8'));
  const subs = fs.existsSync(path.join(dir, 'subs.json')) ? JSON.parse(fs.readFileSync(path.join(dir, 'subs.json'), 'utf8')) : {};
  const tr = (subs.translations || {})[lang];
  if (!tr) { console.error(`✖ no translations.${lang} in subs.json — write the translation there first (subs.mjs uses it too)`); process.exit(2); }
  const missing = src.cues.filter((c) => !tr[c.id]).map((c) => c.id);
  if (missing.length) { console.error(`✖ ${lang}: no translation for ${missing.join(', ')}`); process.exit(2); }
  if (fs.existsSync(path.join(DUB, 'script.json')) && !opt.force) { console.error(`✖ ${path.relative(process.cwd(), DUB)}/script.json exists (--force to overwrite)`); process.exit(2); }
  const keep = ['voice', 'model', 'temperature', 'top_p', 'leadIn', 'gap', 'tail'];   // same voice and model (drama-3)
  const out = { title: `${src.title || ''} (${lang} dub)`, lang, narration: true };
  for (const k of keep) if (src[k] != null) out[k] = src[k];
  out.cues = src.cues.map((c) => ({ id: c.id, text: tr[c.id], say: tr[c.id] }));
  fs.mkdirSync(DUB, { recursive: true });
  fs.writeFileSync(path.join(DUB, 'script.json'), JSON.stringify(out, null, 1));
  const rel = path.relative(process.cwd(), DUB);
  console.log(`${rel}/script.json: ${out.cues.length} cues. Write numbers, symbols and names as they are spoken in "say" (Kling 4.0 → "Kling four point oh", 1080p → "ten-eighty p"), keep tags sparse. Then node tts.mjs ${rel} (silent placeholders, no API call) and dub.mjs --lang ${lang} --report for the estimated fit; the takes are recorded only when the user decides to: node tts.mjs ${rel} --approved`);
  process.exit(0);
}

const noTool = ['ffmpeg', 'ffprobe'].filter((t) => spawnSync(t, ['-version'], { stdio: 'ignore' }).error);
if (noTool.length) { console.error(`✖ ${noTool.join(' and ')} not found — dub.mjs measures and mixes the takes with ${noTool.length > 1 ? 'them' : 'it'}. Install ffmpeg (Mac: brew install ffmpeg; ffprobe comes with it), then run it again. Nothing was written.`); process.exit(2); }

const dubScript = JSON.parse(fs.readFileSync(path.join(DUB, 'script.json'), 'utf8'));
const rel = path.relative(process.cwd(), DUB);
// only recorded, current takes make a track: a placeholder is silence, a stale take says the old wording
if (!fs.existsSync(path.join(DUB, 'js', 'cues.js'))) { console.error(`✖ no ${lang} takes yet — run tts.mjs ${rel} (placeholders for --report), and record with --approved once the user decided to record the dub`); process.exit(1); }
const dubBox = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(DUB, 'js', 'cues.js'), 'utf8'), dubBox);
const dubData = dubBox.window.VIDEO_DATA;
if (dubData.narration === false || dubScript.narration === false) { console.error(`✖ ${rel} is "narration": false — a dub track is recorded narration: set "narration": true in its script.json, run tts.mjs ${rel}, and record with --approved once the user decided to`); process.exit(1); }
const said = new Map(dubData.cues.map((c) => [c.id, c.say]));
const stale = [...dubScript.cues.filter((c) => said.get(c.id) !== c.say).map((c) => c.id),
  ...dubData.cues.filter((c) => !dubScript.cues.some((d) => d.id === c.id)).map((c) => c.id)];
if (stale.length) { console.error(`✖ the ${lang} takes are stale: "say" in ${rel}/script.json changed since tts.mjs ran (${stale.join(', ')}) — run tts.mjs ${rel} again (unchanged lines come from the cache; changed lines are recorded with --approved once the user decided to)`); process.exit(1); }
const ph = dubData.cues.filter((c) => c.placeholder || (dubData.placeholder && !dubData.cues.some((d) => 'placeholder' in d))).map((c) => c.id);
if (ph.length && !opt.report) { console.error(`✖ ${ph.length} ${lang} line(s) are silent placeholders, not recorded (${ph.join(', ')}) — the track would be silent there. Record them once the user decided to record the dub: node tts.mjs ${rel} --approved`); process.exit(1); }
const GAP = 0.12;
const LUFS = -16, LIMIT = 0.79;

const browser = await launch();
const page = await openPage(browser, dir);
const info = await page.evaluate(() => ({ dur: window.__video.duration, audio: window.__media ? window.__media.audio() : [],
  cues: window.VIDEO_DATA.cues.map((c) => ({ id: c.id, start: c.start, end: c.end })) }));
await browser.close();

const decode = (file, sr, ch, ss, dur, af) => {
  const a = ['-v', 'error'];
  if (ss) a.push('-ss', String(ss));
  a.push('-i', file);
  if (dur) a.push('-t', String(dur));
  if (af) a.push('-af', af);
  a.push('-f', 'f32le', '-ac', String(ch), '-ar', String(sr), '-');
  const buf = execFileSync('ffmpeg', a, { maxBuffer: 1 << 30 });
  return new Float32Array(buf.buffer, buf.byteOffset, buf.length / 4);
};
const volAt = (v, lt) => {
  if (typeof v === 'number') return v;
  if (lt <= v[0][0]) return v[0][1];
  for (let i = 1; i < v.length; i++) if (lt <= v[i][0]) { const [x0, a] = v[i - 1], [x1, b] = v[i]; return a + ((b - a) * (lt - x0)) / Math.max(1e-6, x1 - x0); }
  return v[v.length - 1][1];
};
const mixInto = (mix, ch, sr, pcm, at, gain) => {
  const o = Math.round(at * sr) * ch;
  for (let i = 0; i < pcm.length && o + i < mix.length; i++) if (o + i >= 0) mix[o + i] += pcm[i] * (typeof gain === 'function' ? gain(Math.floor(i / ch) / sr) : gain);
};
const clipsInto = (mix, ch, sr) => {
  for (const c of info.audio) {
    const pcm = decode(path.resolve(dir, c.file), sr, ch, c.in, c.dur).subarray(0, Math.round(c.dur * sr) * ch);   // clips with sound play at rate 1 (media.js)
    mixInto(mix, ch, sr, pcm, c.start, (lt) => volAt(c.vol, lt));
  }
};

const durOf = (f) => +execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], { encoding: 'utf8' });
const missing = info.cues.filter((c) => !fs.existsSync(path.join(DUB, 'audio', 'cues', `${c.id}.wav`))).map((c) => c.id);
if (missing.length) { console.error(`✖ no ${lang} take for ${missing.join(', ')} — add the line to ${rel}/script.json and run tts.mjs ${rel} (--approved once the user decided to record the dub)`); process.exit(1); }
const unread = dubData.cues.filter((c) => c.unreviewed).map((c) => c.id);
if (unread.length && !opt.report) { console.error(`✖ ${unread.length} ${lang} take(s) not read yet (${unread.join(', ')}) — read them (node wave.mjs ${rel} --unreviewed), set each cue's "cut" in ${rel}/script.json ("ranges": [] when nothing goes), run tts.mjs ${rel} again`); process.exit(1); }

// each line's room — arithmetic on the cue times, or the agent's "room" where a clip with sound is placed in the stretch
const scById = new Map(dubScript.cues.map((c) => [c.id, c]));
const fmtT = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, '0')}`;
const problems = [];
let prevEnd = 0;
const plan = info.cues.map((c, i) => {
  const next = i + 1 < info.cues.length ? info.cues[i + 1].start : info.dur;
  const file = path.join(DUB, 'audio', 'cues', `${c.id}.wav`);
  const d = durOf(file);
  let start = c.start, end = next - GAP, set = false;
  const room = (scById.get(c.id) || {}).room;
  if (room != null) {
    if (!Array.isArray(room) || room.length !== 2 || !room.every((x) => typeof x === 'number' && Number.isFinite(x)) || !(room[0] >= 0 && room[1] > room[0] && room[1] <= info.dur + 1e-6)) {
      problems.push(`${c.id}: "room" must be [start, end] in seconds of the video (0 ≤ start < end ≤ ${info.dur.toFixed(3)})`);
    } else { [start, end] = room; set = true; }
  }
  // clips that play their own sound placed in this stretch (their placements on the timeline — nothing is measured)
  const clips = [...new Set(info.audio.filter((a) => a.start < end && a.start + a.dur > start).map((a) => a.key))];
  const overlap = start < prevEnd - 1e-6 ? prevEnd : null;   // starts before the line before it has ended
  prevEnd = start + d;
  return { id: c.id, file, start, end, room: end - start, d, over: d - (end - start), set, clips, overlap, from: c.start, next };
});
// air: from a take's end to the next line's start — arithmetic; whether it is dead air is the agent's call (sound.md §1)
plan.forEach((p, i) => { p.air = i + 1 < plan.length ? plan[i + 1].start - (p.start + p.d) : null; });
const open = plan.filter((p) => p.clips.length && !p.set);   // footage sound placed in its stretch, no room set by the agent
const long = plan.filter((p) => p.over > 0.0005);
const overl = plan.filter((p) => p.overlap != null);
const look = (p) => `node wave.mjs ${path.relative(process.cwd(), dir) || '.'} --no-narration --from ${Math.max(0, p.from - 1).toFixed(2)} --to ${Math.min(info.dur, p.next + 0.5).toFixed(2)}`;
if (opt.report) {
  if (opt.json) { console.log(JSON.stringify(plan.map(({ id, start, end, room, d, over, air, set, clips }) => ({ id, start, end, room, d, over, air, roomSet: set, clips, ...(ph.includes(id) ? { placeholder: true } : {}), ...(unread.includes(id) ? { unreviewed: true } : {}) })))); process.exit(0); }
  for (const p of plan) {
    console.log(`${p.id.padEnd(8)} ${fmtT(p.start)}–${fmtT(p.end)} room ${p.room.toFixed(2)} s${p.set ? ' (set)' : ''} · take ${p.d.toFixed(2)} s` +
      (p.over > 0.0005 ? ` → ${p.over.toFixed(2)} s too long ✖ reword shorter` : ` · ${(-p.over).toFixed(2)} s left`) +
      (p.air != null ? ` · air to the next line ${p.air.toFixed(2)} s` : '') +
      (p.clips.length ? ` · footage sound placed here: ${p.clips.join(', ')}${p.set ? '' : ' — set "room" (read: ' + look(p) + ')'}` : '') +
      (p.overlap != null ? ` · ✖ starts before the line before it ends (${fmtT(p.overlap)})` : '') +
      (ph.includes(p.id) ? ' · placeholder (estimated length)' : '') + (unread.includes(p.id) ? ' · take not read yet' : ''));
  }
  for (const x of problems) console.log(`✖ ${x} — this line was shown with its default room`);
  console.log(`${long.length} of ${plan.length} lines too long for their room · ${open.length} need a room you set (footage sound placed in their stretch)` +
    (overl.length ? ` · ${overl.length} start before the line before them ends` : '') + ' · the air after each line is yours to judge (references/sound.md §1)');
  if (ph.length) console.log(`⏸ ${ph.length} line(s) are placeholders, not recorded — their lengths are estimates: ${ph.join(', ')}`);
  process.exit(0);
}
if (problems.length) { console.error(`✖ ${rel}/script.json:\n  ${problems.join('\n  ')}`); process.exit(1); }
if (open.length) { console.error(`✖ footage sound is placed in the stretch of ${open.map((p) => p.id).join(', ')} and no "room" is set — where that sound is up is your call: read it (--report prints the wave.mjs command for each), then set "room": [start, end] for the line in ${rel}/script.json`); process.exit(1); }
if (overl.length) { console.error(`✖ ${overl.map((p) => p.id).join(', ')} would start before the line before it has ended — move its "room" start (or reword the line before shorter)`); process.exit(1); }
if (long.length) { console.error(`✖ too long for their room: ${long.map((p) => `${p.id} +${p.over.toFixed(2)} s`).join(', ')} — reword them shorter in ${path.relative(process.cwd(), DUB)}/script.json (the voice is never sped up)`); process.exit(1); }

// narration level-matched to the original narration, then the footage, then mastering
const SR = 48000, CH = 2;
const narr = new Float32Array(Math.ceil(info.dur * SR) * CH);
for (const p of plan) mixInto(narr, CH, SR, decode(p.file, SR, CH, 0, 0), p.start, 1);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'dub-'));
const narrFile = path.join(tmp, 'narr.f32');
fs.writeFileSync(narrFile, Buffer.from(narr.buffer));
const loudness = (inArgs, af = '') => {
  const e = spawnSync('ffmpeg', ['-hide_banner', '-nostats', ...inArgs, '-af', `${af}ebur128`, '-f', 'null', '-'], { encoding: 'utf8', maxBuffer: 1 << 26 }).stderr;
  return +/I:\s+(-?[\d.]+) LUFS/.exec(e.slice(e.lastIndexOf('Summary')))[1];
};
const origI = loudness(['-i', path.join(dir, 'audio/narration.wav')]);
const dubI = loudness(['-f', 'f32le', '-ar', String(SR), '-ac', String(CH), '-i', narrFile]);
const g = 10 ** ((origI - dubI) / 20);
const mix = new Float32Array(narr.length);
for (let i = 0; i < mix.length; i++) mix[i] = narr[i] * g;
clipsInto(mix, CH, SR);
const mixFile = path.join(tmp, 'mix.f32');
fs.writeFileSync(mixFile, Buffer.from(mix.buffer));
const raw = ['-f', 'f32le', '-ar', String(SR), '-ac', String(CH), '-i', mixFile];
const COMP = 'acompressor=threshold=0.1:ratio=3:attack=5:release=150:knee=4';
const measI = loudness(raw, `${COMP},`);
const MASTER = `${COMP},volume=${(LUFS - measI).toFixed(2)}dB,alimiter=limit=${LIMIT}:attack=5:release=80:level=false`;
const OUT = path.resolve(dir, opt.out || path.join('dub', lang, `${opt.name || 'video'}.${lang}.wav`));
fs.mkdirSync(path.dirname(OUT), { recursive: true });
execFileSync('ffmpeg', ['-v', 'error', '-y', ...raw, '-af', MASTER, '-t', info.dur.toFixed(3), '-c:a', 'pcm_s16le', '-ar', String(SR), OUT]);
fs.rmSync(tmp, { recursive: true, force: true });
recordGenerated([OUT], 'dub.mjs');   // generated.json: check.mjs accepts the track as the skill's own
console.log(`${lang} narration ${dubI.toFixed(1)} → ${origI.toFixed(1)} LUFS (the original narration's level) · every line at its recorded speed`);
console.log(`→ ${path.relative(process.cwd(), OUT)} · ${info.dur.toFixed(3)} s · 48 kHz stereo 16-bit · ${LUFS} LUFS`);
