#!/usr/bin/env node
/**
 * subs.mjs — subtitle files (SRT) for uploading: one per language, timed by the cues (js/cues.js).
 *
 *   node subs.mjs <projectDir> [--out <folder>] [--name <base>]      → <out>/<base>.<lang>.srt   (default subs/video.*.srt)
 *
 * The base language is the cue text as shown on screen. Other languages and lines that aren't narration (dialogue inside
 * a clip, a sign) come from <project>/subs.json:
 *   { "lang": "ko",
 *     "translations": { "en": { "c01": "…", "c02": "…" } },          // every cue, or the language is refused
 *     "extra": [ { "after": "c02", "offset": 0.15,                     // relative to that cue's end (re-timing moves them)
 *                  "lines": [[4.1, 6.75, { "ko": "…", "en": "…" }]] } ] }   // [from, to] seconds after that point
 * Each subtitle stays up 0.15 s after its line ends (never into the next one); long lines are split at punctuation into at
 * most two lines (28 characters for Korean/Japanese/Chinese, 46 otherwise).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { parseArgs } from './lib/browser.mjs';

const opt = parseArgs();
const dir = path.resolve(opt._[0] || '.');
const out = path.resolve(dir, opt.out || 'subs');
const name = opt.name || 'video';
const box = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(dir, 'js/cues.js'), 'utf8'), box);
const data = box.window.VIDEO_DATA;
const byId = new Map(data.cues.map((c) => [c.id, c]));
if (data.placeholder) console.warn('⚠ some cues are placeholders (estimated timing): the subtitle times move once the narration is recorded — run subs.mjs again then');
const cfgPath = path.join(dir, 'subs.json');
const cfg = fs.existsSync(cfgPath) ? JSON.parse(fs.readFileSync(cfgPath, 'utf8')) : {};
const base = cfg.lang || (fs.readFileSync(path.join(dir, 'index.html'), 'utf8').match(/<html lang="([\w-]+)"/) || [])[1] || 'ko';
const langs = [base, ...Object.keys(cfg.translations || {})];

const ts = (s) => {
  const ms = Math.max(0, Math.round(s * 1000)), h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000), sec = Math.floor((ms % 60000) / 1000);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
};
function wrap(text, max) {
  if (text.length <= max) return text;
  const mid = text.length / 2, near = (i) => Math.abs(i - mid);
  const punct = [], spaces = [];
  for (let i = 1; i < text.length - 1; i++) {
    if (text[i] !== ' ') continue;
    (/[,.?!…:;]/.test(text[i - 1]) ? punct : spaces).push(i);
  }
  const good = punct.filter((i) => i > text.length * 0.3 && i < text.length * 0.7);
  const pick = (good.length ? good : spaces).sort((p, q) => near(p) - near(q))[0];
  return pick == null ? text : text.slice(0, pick).trim() + '\n' + text.slice(pick).trim();
}

let bad = 0;
fs.mkdirSync(out, { recursive: true });
for (const lang of langs) {
  const tr = lang === base ? null : cfg.translations[lang];
  const missing = tr ? data.cues.filter((c) => !tr[c.id]).map((c) => c.id) : [];
  if (missing.length) { console.error(`✖ ${lang}: no translation for ${missing.join(', ')}`); bad++; continue; }
  const rows = data.cues.map((c) => [c.start, c.end + 0.15, tr ? tr[c.id] : c.text]);
  for (const g of cfg.extra || []) {
    const c = byId.get(g.after);
    if (!c) { console.error(`✖ subs.json extra: no cue ${g.after}`); bad++; continue; }
    const o = c.end + (g.offset || 0);
    for (const [a, b, t] of g.lines) {
      const text = typeof t === 'string' ? (lang === base ? t : null) : t[lang];
      if (text == null) { console.error(`✖ ${lang}: an extra line at ${g.after}+${a}s has no ${lang} text`); bad++; continue; }
      rows.push([o + a, o + b, text]);
    }
  }
  rows.sort((p, q) => p[0] - q[0]);
  const max = /^(ko|ja|zh)/.test(lang) ? 28 : 46;
  const srt = rows.map(([a, b, t], i) => `${i + 1}\n${ts(a)} --> ${ts(Math.min(b, rows[i + 1] ? rows[i + 1][0] - 0.02 : b))}\n${wrap(String(t), max)}\n`).join('\n');
  const f = path.join(out, `${name}.${lang}.srt`);
  fs.writeFileSync(f, srt);
  console.log(`${path.relative(process.cwd(), f)}: ${rows.length} subtitles`);
}
process.exit(bad ? 1 : 0);
