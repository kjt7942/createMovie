#!/usr/bin/env node
/**
 * install_guard.mjs — put script-to-motion's looking guard (look_guard.py) into the Claude Code project's local settings,
 * so it covers every agent of the project, subagents included.
 *
 *   node <skill>/scripts/hooks/install_guard.mjs [<claude project dir>] [--remove] [--check]
 *
 * Why: SKILL.md's frontmatter hook starts only once the skill is invoked and does not reach subagents (tested with
 * Claude Code 2.1.319: a general-purpose subagent opened the image the main session was refused). A PreToolUse hook in
 * `.claude/settings.local.json` reaches them, and Claude Code picks it up at once, mid-session.
 *
 * The project folder: the argument, else the nearest folder above the current one that has `.claude/` (then `.git`),
 * else the current folder. The file is the user's local settings (git-ignored by Claude Code) — nothing is committed.
 * The entry points at this skill's look_guard.py by its absolute path and does nothing when that file is gone (it never
 * blocks a call because the skill moved). Running it again updates the path; --remove takes it out; --check only says
 * whether it is there. It prints one line saying what it did.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const guard = path.join(here, 'look_guard.py');
const args = process.argv.slice(2);
const flag = (k) => args.includes(k);
const pos = args.filter((a) => !a.startsWith('--'));

function projectRoot(start) {
  for (const mark of ['.claude', '.git']) {
    for (let d = path.resolve(start); ; d = path.dirname(d)) {
      if (fs.existsSync(path.join(d, mark)) && !(mark === '.claude' && d === path.resolve(process.env.HOME || '~'))) return d;
      if (path.dirname(d) === d) break;
    }
  }
  return path.resolve(start);
}
const root = pos[0] ? path.resolve(pos[0]) : (process.env.CLAUDE_PROJECT_DIR || projectRoot(process.cwd()));
const file = path.join(root, '.claude', 'settings.local.json');
const sq = (s) => `'${s.replace(/'/g, `'\\''`)}'`;
const command = `f=${sq(guard)}; [ -f "$f" ] && exec python3 "$f"; exit 0`;
const MATCHER = 'Read|Bash|Write|Edit|MultiEdit|NotebookEdit';

let cfg = {};
if (fs.existsSync(file)) {
  try { cfg = JSON.parse(fs.readFileSync(file, 'utf8')); } catch (e) {
    console.error(`✖ ${file} is not valid JSON — not touched (${e.message})`); process.exit(1);
  }
}
const pre = ((cfg.hooks || {}).PreToolUse || []);
const ours = (h) => /look_guard\.py/.test(h.command || '');
const has = pre.some((g) => (g.hooks || []).some(ours));

if (flag('--check')) {
  console.log(has ? `✓ looking guard is in ${file}` : `✖ no looking guard in ${file} — run: node ${path.relative(process.cwd(), fileURLToPath(import.meta.url)) || 'install_guard.mjs'}`);
  process.exit(has ? 0 : 1);
}

// drop our old entries (any path), keep everything else of the user's
const kept = pre.map((g) => ({ ...g, hooks: (g.hooks || []).filter((h) => !ours(h)) })).filter((g) => g.hooks.length);
if (flag('--remove')) {
  if (!has) { console.log(`looking guard: not in ${file} — nothing to remove`); process.exit(0); }
  cfg.hooks = { ...(cfg.hooks || {}), PreToolUse: kept };
  if (!cfg.hooks.PreToolUse.length) delete cfg.hooks.PreToolUse;
  if (!Object.keys(cfg.hooks).length) delete cfg.hooks;
} else {
  cfg.hooks = { ...(cfg.hooks || {}), PreToolUse: [...kept, { matcher: MATCHER, hooks: [{ type: 'command', command }] }] };
}
fs.mkdirSync(path.dirname(file), { recursive: true });
const tmp = `${file}.${process.pid}.tmp`;
fs.writeFileSync(tmp, JSON.stringify(cfg, null, 2) + '\n');
fs.renameSync(tmp, file);
console.log(flag('--remove') ? `looking guard removed from ${file}`
  : `looking guard ${has ? 'updated' : 'installed'} in ${file} (local settings, not committed): every agent of this project, subagents too, sees the video only on render.py sheets`);
