/**
 * env.mjs — the user's settings as tts.mjs finds them: the environment, a .env file in the project folder or any folder
 * above it, the skill's own .env (git-ignored, where the user's keys live).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const SKILL_ENV = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '.env');   // fileURLToPath: spaces, Hangul
export const FISH_KEY_NAMES = ['FISH_API_KEY', 'FISH_AUDIO_API_KEY'];

/** the value of the first of `names` set in a .env file (NAME=value, optionally quoted or after `export`), or null */
export function fromEnvFile(f, names) {
  if (!fs.existsSync(f)) return null;
  const txt = fs.readFileSync(f, 'utf8');
  for (const n of names) {
    const m = txt.match(new RegExp(`^[ \\t]*(?:export[ \\t]+)?${n}[ \\t]*=[ \\t]*["']?([^"'\\s#]+)`, 'm'));
    if (m) return m[1];
  }
  return null;
}

/** every value of `names` in every place tts.mjs looks (not only the first it would use): [{ value, where }] */
export function allSettings(dir, names) {
  const out = [];
  for (const n of names) if (process.env[n] && process.env[n].trim()) out.push({ value: process.env[n].trim(), where: `the environment (${n})` });
  for (let d = path.resolve(dir); ; d = path.dirname(d)) {
    for (const n of names) { const v = fromEnvFile(path.join(d, '.env'), [n]); if (v) out.push({ value: v, where: path.join(d, '.env') }); }
    if (path.dirname(d) === d) break;
  }
  for (const n of names) { const v = fromEnvFile(SKILL_ENV, [n]); if (v) out.push({ value: v, where: SKILL_ENV }); }
  return [...new Map(out.map((x) => [x.value, x])).values()];
}
