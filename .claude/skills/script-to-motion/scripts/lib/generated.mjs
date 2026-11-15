/**
 * generated.mjs — the record of the files the skill's own tools wrote into a video project.
 *
 * <project>/generated.json:  { "files": { "<path in the project>": { "sha256": "…", "by": "<tool>" }, … } }
 *
 * A tool that writes a file which is not plain text (audio, images, video, 3D) records it here right after writing it.
 * check.mjs accepts such a file only when it is listed here with the same sha256 (the skill made it, unchanged since)
 * or declared in provenance.json as the user's — there is no rule by file name or folder.
 * render.py is a standalone copy in every project and writes the same file the same way (record_generated there).
 *
 * Writers take generated.json.lock (created exclusively; it holds the writer's host and pid). A lock whose process is
 * gone on this host is removed; a lock held longer than 30 s by a live process (or one on another host) stops the tool
 * with the path to delete.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';

export const RECORD = 'generated.json';
const NOTE = 'files the skill\'s tools wrote into this project, with their sha256 — written by the tools; do not edit (check.mjs, SKILL.md → Originality)';

/** the video project a path is in: the nearest folder at or above it with index.html and script.json (null: none) */
export function projectOf(p) {
  let d = path.resolve(p);
  try { if (!fs.statSync(d).isDirectory()) d = path.dirname(d); } catch { d = path.dirname(d); }
  for (;;) {
    if (fs.existsSync(path.join(d, 'index.html')) && fs.existsSync(path.join(d, 'script.json'))) return d;
    const up = path.dirname(d);
    if (up === d) return null;
    d = up;
  }
}

/** sha256 of a file, read in 16 MB pieces (a movie of several GB never sits in memory whole) */
export function sha256File(abs) {
  const h = crypto.createHash('sha256');
  const buf = Buffer.allocUnsafe(1 << 24);
  const fd = fs.openSync(abs, 'r');
  try {
    for (let n; (n = fs.readSync(fd, buf, 0, buf.length, null)) > 0;) h.update(buf.subarray(0, n));
  } finally { fs.closeSync(fd); }
  return h.digest('hex');
}

/** generated.json of a project as { files } (empty when there is none; throws when it is not valid JSON) */
export function readRecord(root) {
  const p = path.join(root, RECORD);
  if (!fs.existsSync(p)) return { files: {} };
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  return { files: (j && typeof j.files === 'object' && j.files) || {} };
}

const posix = (root, abs) => path.relative(root, abs).split(path.sep).join('/');
const sleep = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch (e) { return e.code === 'EPERM'; } };

function withLock(root, fn) {
  const lock = path.join(root, RECORD + '.lock');
  const me = JSON.stringify({ host: os.hostname(), pid: process.pid });
  const t0 = Date.now();
  for (;;) {
    try { fs.writeFileSync(lock, me, { flag: 'wx' }); break; } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      let o = null;
      try { o = JSON.parse(fs.readFileSync(lock, 'utf8')); } catch { /* being written this moment, or gone */ }
      if (o && o.host === os.hostname() && Number.isInteger(o.pid) && !alive(o.pid)) { fs.rmSync(lock, { force: true }); continue; }
      if (Date.now() - t0 > 30000) {
        throw new Error(`${lock} is held by ${o ? `pid ${o.pid} on ${o.host}` : 'another process'} — if no tool of the skill is writing to this project, delete it`);
      }
      sleep(50);
    }
  }
  try { return fn(); } finally { fs.rmSync(lock, { force: true }); }
}

/**
 * record files a tool of the skill has just written (paths, absolute or relative to the working folder). Each file goes
 * into the generated.json of the video project it is in (a file in no project needs no record). Entries whose file no
 * longer exists are dropped in the same write. Returns the number of files recorded.
 */
export function recordGenerated(files, by) {
  const groups = new Map();
  for (const f of files) {
    const abs = path.resolve(f);
    const root = projectOf(abs);
    if (!root || !fs.statSync(abs).isFile()) continue;
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root).push(abs);
  }
  let n = 0;
  for (const [root, list] of groups) {
    const add = list.map((abs) => [posix(root, abs), { sha256: sha256File(abs), by }]);   // hashed before the lock is taken
    withLock(root, () => {
      const rec = readRecord(root);
      for (const [r, e] of add) rec.files[r] = e;
      for (const r of Object.keys(rec.files)) if (!fs.existsSync(path.join(root, r))) delete rec.files[r];
      const files = Object.fromEntries(Object.keys(rec.files).sort().map((k) => [k, rec.files[k]]));
      const tmp = path.join(root, `generated.${process.pid}.tmp.json`);
      fs.writeFileSync(tmp, JSON.stringify({ note: NOTE, files }, null, 1) + '\n');
      fs.renameSync(tmp, path.join(root, RECORD));
    });
    n += add.length;
  }
  return n;
}

/** every file under a folder (recursively, links not followed) as absolute paths — what a tool wrote there */
export function filesUnder(d) {
  const out = [];
  const walk = (x) => {
    let ents;
    try { ents = fs.readdirSync(x, { withFileTypes: true }); } catch { return; }
    for (const e of ents) {
      const p = path.join(x, e.name);
      if (e.isDirectory()) walk(p); else if (e.isFile()) out.push(p);
    }
  };
  walk(d);
  return out;
}
