#!/usr/bin/env node
/**
 * cokacmotion.mjs — the cokacmotion technique library for this skill: 166 short web-graphics demos (the `aimotion`
 * skill), one technique each, with implementation notes, full source and stills. Find the technique a beat needs, read
 * how it is built, then re-implement it in the project (references/cokacmotion.md). Read-only reference: a project never
 * loads its files.
 *
 *   node cokacmotion.mjs search <words…> [--limit N]    demos ranked by title, technique, key points, libraries, group
 *   node cokacmotion.mjs list                           every demo, by group
 *   node cokacmotion.mjs show <id> [--notes | --code]   the demo's NOTES.md and source (or one of the two)
 *   node cokacmotion.mjs path <id>                      its folder and files (open out/poster.jpg, out/sheet.jpg as images)
 *   node cokacmotion.mjs common                         the shared demo runtime (_lib: stage.js clock, type.js)
 *   node cokacmotion.mjs where                          the local copy: folder, commit, when it was fetched
 *   node cokacmotion.mjs update                         refresh the local copy now
 *
 * <id> is the demo folder (03-coral-growth) or its number (3). search/list/show/path/common run the library's own
 * scripts/aimotion.mjs (no dependencies, no network, reads only its own files).
 *
 * Source: https://github.com/kstost/cokacmotion (MIT), this skill's technique reference.
 * Downloaded on first use into ~/.cache/motion-video-cokacmotion ($MOTION_VIDEO_COKACMOTION_CACHE) with git (or the
 * GitHub tarball when git is missing), refreshed at most once a day; offline, the cached copy is used.
 * COKACMOTION_DIR=<checkout> uses an existing checkout instead (no download, no refresh).
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { download } from './lib/fontfetch.mjs';

const REPO = 'https://github.com/kstost/cokacmotion';
const TARBALL = 'https://codeload.github.com/kstost/cokacmotion/tar.gz/refs/heads/main';
const SKILL_SUB = path.join('skills', 'aimotion');
const TOOL_SUB = path.join('scripts', 'aimotion.mjs');
const DAY = 24 * 3600 * 1000;

const args = process.argv.slice(2);
const cmd = args[0];

function die(msg, code = 1) {
  console.error(`✖ ${msg}`);
  process.exit(code);
}
const note = (msg) => console.error(`· ${msg}`);

function usage() {
  const src = fs.readFileSync(new URL(import.meta.url), 'utf8');
  const doc = src.slice(src.indexOf('/**') + 3, src.indexOf('*/')).split('\n').map((l) => l.replace(/^\s*\* ?/, ''));
  console.log(doc.join('\n').trim());
}

if (!cmd || cmd === '--help' || cmd === '-h' || cmd === 'help') {
  usage();
  process.exit(cmd ? 0 : 1);
}

const run = (bin, argv, opts = {}) => spawnSync(bin, argv, { encoding: 'utf8', timeout: 180000, ...opts });
const hasGit = !run('git', ['--version']).error;

/** A folder that holds the aimotion skill: the repository root or the skill folder itself. */
function skillDirOf(dir) {
  if (fs.existsSync(path.join(dir, SKILL_SUB, TOOL_SUB))) return path.join(dir, SKILL_SUB);
  if (fs.existsSync(path.join(dir, TOOL_SUB))) return dir;
  return null;
}

// ---------- an existing checkout given by the user ----------
const given = process.env.COKACMOTION_DIR && path.resolve(process.env.COKACMOTION_DIR);
if (given && !skillDirOf(given)) die(`COKACMOTION_DIR=${given} holds no aimotion skill (expected ${path.join(SKILL_SUB, TOOL_SUB)})`);

// ---------- the cache ----------
const cache = path.resolve(process.env.MOTION_VIDEO_COKACMOTION_CACHE || path.join(os.homedir(), '.cache', 'motion-video-cokacmotion'));
const repoDir = path.join(cache, 'repo');
const stamp = path.join(cache, 'fetched-at');

const fetchedAt = () => {
  try {
    return fs.statSync(stamp).mtimeMs;
  } catch {
    return 0;
  }
};
const touch = () => fs.writeFileSync(stamp, new Date().toISOString() + '\n');

/** Download a fresh copy into a temporary folder next to the cache, then swap it in. */
async function fetchFresh() {
  fs.mkdirSync(cache, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(cache, 'incoming-'));
  try {
    if (hasGit) {
      const r = run('git', ['clone', '--depth', '1', '--quiet', `${REPO}.git`, tmp]);
      if (r.error || r.status !== 0) throw new Error(`git clone: ${(r.stderr || r.error?.message || '').trim().split('\n').pop()}`);
    } else {
      const tgz = path.join(tmp, '..', `${path.basename(tmp)}.tar.gz`);
      fs.writeFileSync(tgz, await download(TARBALL));
      const r = run('tar', ['-xzf', tgz, '-C', tmp, '--strip-components=1']);
      fs.rmSync(tgz, { force: true });
      if (r.error || r.status !== 0) throw new Error(`tar: ${(r.stderr || r.error?.message || '').trim().split('\n').pop()}`);
    }
    if (!skillDirOf(tmp)) throw new Error(`the download holds no ${path.join(SKILL_SUB, TOOL_SUB)} — has the repository changed its layout?`);
    fs.rmSync(repoDir, { recursive: true, force: true });
    try {
      fs.renameSync(tmp, repoDir);
    } catch (e) {
      if (!skillDirOf(repoDir)) throw e; // a parallel run won the race: its copy is as fresh as ours
      fs.rmSync(tmp, { recursive: true, force: true });
    }
    touch();
  } catch (e) {
    fs.rmSync(tmp, { recursive: true, force: true });
    throw e;
  }
}

/** Bring the cached copy up to date (git fast path; otherwise a fresh download). */
async function refresh() {
  if (hasGit && fs.existsSync(path.join(repoDir, '.git'))) {
    const f = run('git', ['-C', repoDir, 'fetch', '--depth', '1', '--quiet', 'origin', 'main']);
    if (f.error || f.status !== 0) throw new Error(`git fetch: ${(f.stderr || f.error?.message || '').trim().split('\n').pop()}`);
    // the cache is this tool's own copy (nobody edits it), so it simply follows the remote
    const r = run('git', ['-C', repoDir, 'reset', '--hard', '--quiet', 'FETCH_HEAD']);
    if (r.error || r.status !== 0) throw new Error(`git reset: ${(r.stderr || '').trim()}`);
    touch();
  } else {
    await fetchFresh();
  }
}

function describe(dir) {
  const root = path.basename(dir) === 'aimotion' ? path.resolve(dir, '..', '..') : dir;
  if (hasGit && fs.existsSync(path.join(root, '.git'))) {
    const r = run('git', ['-C', root, 'log', '-1', '--format=%h %cs %s']);
    if (r.status === 0) return `commit ${r.stdout.trim()}`;
  }
  return 'commit unknown, downloaded as a tarball';
}

async function ensure({ force = false } = {}) {
  if (given) {
    if (force) note('COKACMOTION_DIR is set: update that checkout yourself (git pull) — nothing downloaded');
    return skillDirOf(given);
  }
  const have = skillDirOf(repoDir);
  if (!have) {
    note(`downloading the cokacmotion technique library from ${REPO} (first use) …`);
    try {
      await fetchFresh();
    } catch (e) {
      die(`could not download cokacmotion: ${e.message}\n  check the network and run again (or set COKACMOTION_DIR to an existing checkout)`);
    }
    note(`cached in ${repoDir} (${describe(repoDir)})`);
    return skillDirOf(repoDir);
  }
  if (force || Date.now() - fetchedAt() > DAY) {
    try {
      await refresh();
      if (force) note(`up to date: ${describe(repoDir)}`);
    } catch (e) {
      if (force) die(`update failed: ${e.message} — the cached copy is unchanged`);
      note(`could not refresh cokacmotion (${e.message}) — using the cached copy`);
    }
  }
  return skillDirOf(repoDir);
}

// ---------- commands ----------
if (cmd === 'update') {
  await ensure({ force: true });
  process.exit(0);
}

const dir = await ensure();

if (cmd === 'where') {
  const fetched = given ? 'given by COKACMOTION_DIR' : `fetched ${new Date(fetchedAt()).toISOString().slice(0, 16).replace('T', ' ')} UTC`;
  console.log(`cokacmotion (aimotion skill): ${dir}`);
  console.log(`  ${describe(given || repoDir)} · ${fetched}`);
  console.log(`  source ${REPO} · MIT`);
  process.exit(0);
}

const r = spawnSync(process.execPath, [path.join(dir, TOOL_SUB), ...args], { stdio: 'inherit' });
if (r.error) die(`could not run ${path.join(dir, TOOL_SUB)}: ${r.error.message}`);
process.exit(r.status ?? 1);
