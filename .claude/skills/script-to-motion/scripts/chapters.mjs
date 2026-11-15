#!/usr/bin/env node
/**
 * chapters.mjs — YouTube chapters (description timestamps) from the cues, with the same chapter windows the scenes use.
 *
 *   node chapters.mjs <projectDir> [--lang en] [--lead 1.05] [--overlap 0.25]
 *
 * Chapters are declared in script.json:
 *   "chapters": [ { "from": "op01", "title": "AI가 만든 60초 드라마, 배우 없이 어떻게 찍었을까?" },
 *                 { "from": "tr01", "title": { "ko": "…", "en": "Why are AI short dramas suddenly everywhere?" } }, … ]
 * A chapter starts where its transition starts: `lead` s before its first line, but never more than `overlap` s before the
 * previous line ends (no dead air between chapters). Keep the scenes' chapter windows on the same rule
 * (references/long-form.md). The first chapter starts at 0:00.
 * Checks YouTube's rules (at least 3 chapters, 0:00 first, each ≥ 10 s) and warns on a title that isn't a question.
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { parseArgs } from './lib/browser.mjs';

const opt = parseArgs();
const dir = path.resolve(opt._[0] || '.');
const LEAD = +(opt.lead ?? 1.05), OVER = +(opt.overlap ?? 0.25), lang = opt.lang || null;
const script = JSON.parse(fs.readFileSync(path.join(dir, 'script.json'), 'utf8'));
const box = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(dir, 'js/cues.js'), 'utf8'), box);
const cues = box.window.VIDEO_DATA.cues;
if (box.window.VIDEO_DATA.placeholder) console.warn('⚠ some cues are placeholders (estimated timing): these timestamps move once the narration is recorded — run chapters.mjs again then');
const chs = script.chapters || [];
if (!chs.length) {
  console.error('✖ no "chapters" in script.json — add [{ "from": "<first cue id>", "title": "<a question>" }, …]');
  process.exit(2);
}
const fmt = (s) => { s = Math.floor(s + 1e-6); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}` : `${m}:${String(x).padStart(2, '0')}`; };
const problems = [];
const starts = chs.map((ch, i) => {
  const k = cues.findIndex((c) => c.id === ch.from);
  if (k < 0) { problems.push(`chapter ${i + 1}: no cue ${ch.from}`); return 0; }
  if (i === 0) return 0;
  const prev = cues[k - 1];
  return Math.max(cues[k].start - LEAD, prev ? prev.end - OVER : 0);
});
const total = box.window.VIDEO_DATA.duration;
const lines = chs.map((ch, i) => {
  const t = typeof ch.title === 'string' ? ch.title : (ch.title || {})[lang || Object.keys(ch.title || {})[0]];
  if (!t) problems.push(`chapter ${i + 1}: no title${lang ? ` in ${lang}` : ''}`);
  else if (!/[?？]\s*$/.test(t)) console.warn(`⚠ chapter ${i + 1} is not a question: "${t}"`);
  const len = (i + 1 < chs.length ? starts[i + 1] : total) - starts[i];
  if (len < 10) problems.push(`chapter ${i + 1} lasts ${len.toFixed(1)} s — YouTube needs ≥ 10 s`);
  return `${fmt(starts[i])} ${t || ''}`;
});
if (chs.length < 3) problems.push('YouTube shows chapters only with at least 3');
console.log(lines.join('\n'));
for (const p of problems) console.error('✖ ' + p);
process.exit(problems.length ? 1 : 0);
