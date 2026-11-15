/**
 * fontfetch.mjs — download catalogue fonts on demand (the skill ships no font files).
 *
 * Every file in assets/fonts/catalog.json carries its official source (`fetch.url`, or a member of a pinned
 * release archive) and its sha256. installFonts() downloads what is missing into a local cache
 * (~/.cache/motion-video-fonts, or $MOTION_VIDEO_FONT_CACHE), verifies every hash, verifies that the licence
 * file is the SIL Open Font License 1.1, and copies the unmodified files into the project.
 *
 * Hard rules (no flags to bypass them):
 *   - a catalogue font whose `license` is not exactly "SIL OFL 1.1" is refused;
 *   - a downloaded file whose sha256 differs from the catalogue is refused (never "close enough");
 *   - a licence file that is not the SIL OFL 1.1 text is refused;
 *   - there is no fallback to another font or source. A failed download is an error.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';

export const REQUIRED_LICENSE = 'SIL OFL 1.1';
export const CACHE_DIR = process.env.MOTION_VIDEO_FONT_CACHE || path.join(os.homedir(), '.cache', 'motion-video-fonts');

const shaBuf = (b) => crypto.createHash('sha256').update(b).digest('hex');
const shaFile = (p) => shaBuf(fs.readFileSync(p));

/** true when the text is the SIL Open Font License, version 1.1 */
export function isOfl11(text) {
  const t = String(text).replace(/\s+/g, ' ');
  return /SIL OPEN FONT LICENSE/i.test(t) && /Version 1\.1/i.test(t) && /PERMISSION & CONDITIONS/i.test(t);
}

/** refuse any catalogue entry that is not SIL OFL 1.1 or lacks what verification needs */
export function assertOflEntry(font) {
  if (font.license !== REQUIRED_LICENSE) {
    throw new Error(`${font.id}: licence "${font.license}" is not allowed — this skill uses SIL OFL 1.1 fonts only`);
  }
  for (const f of [...font.files, font.licenseFile]) {
    if (!f || !f.dest || !/^[0-9a-f]{64}$/.test(f.sha256 || '') || !f.fetch) {
      throw new Error(`${font.id}: catalogue entry ${f && f.dest} needs dest, sha256 and fetch (official source)`);
    }
  }
}

export async function download(url, attempts = 3) {
  let last;
  for (let i = 1; i <= attempts; i++) {
    try {
      const res = await fetch(url, { redirect: 'follow', signal: AbortSignal.timeout(180000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return Buffer.from(await res.arrayBuffer());
    } catch (e) {
      last = e;
      if (i < attempts) await new Promise((r) => setTimeout(r, 1500 * i));
    }
  }
  throw new Error(`download failed: ${url} (${last && last.message}) — check the network/proxy and run again; fonts are never substituted`);
}

const cacheFile = (font, dest) => path.join(CACHE_DIR, `${font.id}@${String(font.version).replace(/[^\w.-]+/g, '-')}`, dest.replace(/^fonts\//, ''));

/** download an archive once (cached by URL) and extract the requested members into a temp dir */
async function fromArchive(font, key, members, log) {
  const spec = (font.archives || {})[key];
  if (!spec) throw new Error(`${font.id}: archive "${key}" is not declared in the catalogue`);
  const archDir = path.join(CACHE_DIR, '_archives');
  fs.mkdirSync(archDir, { recursive: true });
  const arch = path.join(archDir, `${shaBuf(Buffer.from(spec.url)).slice(0, 16)}.${spec.type}`);
  if (!fs.existsSync(arch)) {
    log(`  ↓ ${spec.url}`);
    const buf = await download(spec.url);
    fs.writeFileSync(arch + '.part', buf);
    fs.renameSync(arch + '.part', arch);
  }
  const tmp = extract(arch, spec.type, members, `${font.id}: could not extract from ${path.basename(spec.url)}`);
  return {
    get: (m) => fs.readFileSync(path.join(tmp, m)),
    // the extracted files are cached individually; the archive itself is not kept
    done: (ok) => { fs.rmSync(tmp, { recursive: true, force: true }); if (ok) fs.rmSync(arch, { force: true }); },
  };
}

/**
 * Extract `members` of a zip/tgz archive into a new temp dir (returned). Tries the usual tools in order: Windows has
 * bsdtar (reads zip) but no unzip; some minimal Linux images lack both, python's zipfile/tarfile is the last resort.
 */
export function extract(arch, type, members, what = 'archive') {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'mvfetch-'));
  const py = `import sys,zipfile,tarfile\na,d,*m=sys.argv[1:]\nz=zipfile.ZipFile(a) if a.endswith('.zip') else tarfile.open(a)\n[z.extract(z.getmember(x) if hasattr(z,'getmember') else x, d) for x in m]`;
  const tries = type === 'zip'
    ? [['unzip', ['-o', '-q', arch, ...members, '-d', tmp]], ['tar', ['-xf', arch, '-C', tmp, ...members]], ['python3', ['-c', py, arch, tmp, ...members]], ['python', ['-c', py, arch, tmp, ...members]]]
    : [['tar', ['-xzf', arch, '-C', tmp, ...members]], ['python3', ['-c', py, arch, tmp, ...members]], ['python', ['-c', py, arch, tmp, ...members]]];
  const errs = [];
  for (const [cmd, args] of tries) {
    const r = spawnSync(cmd, args, { encoding: 'utf8' });
    if (!r.error && r.status === 0 && members.every((m) => fs.existsSync(path.join(tmp, m)))) return tmp;
    errs.push(`${cmd}: ${r.error ? r.error.code || r.error.message : (r.stderr || '').trim().split('\n')[0] || 'exit ' + r.status}`);
  }
  fs.rmSync(tmp, { recursive: true, force: true });
  throw new Error(`${what} (${errs.join('; ')}) — install unzip/tar or python3`);
}

/**
 * Make sure every file of `font` (and its licence) is in the cache, verified. Returns [{ entry, cached }].
 * Downloads only what is missing or doesn't match; works offline once cached.
 */
export async function ensureFont(font, { log = () => {} } = {}) {
  assertOflEntry(font);
  const all = [...font.files, font.licenseFile];
  const out = [];
  const missing = [];
  for (const entry of all) {
    const c = cacheFile(font, entry.dest);
    if (fs.existsSync(c) && shaFile(c) === entry.sha256) out.push({ entry, cached: c });
    else missing.push(entry);
  }
  if (missing.length) log(`  fetching ${font.family} ${font.version} (${missing.length} file${missing.length > 1 ? 's' : ''}) from the official source`);
  const byArchive = new Map();
  for (const entry of missing) {
    if (entry.fetch.archive) {
      if (!byArchive.has(entry.fetch.archive)) byArchive.set(entry.fetch.archive, []);
      byArchive.get(entry.fetch.archive).push(entry);
    }
  }
  const store = (entry, buf, from) => {
    const got = shaBuf(buf);
    if (got !== entry.sha256) {
      throw new Error(`${font.id}: ${entry.dest} from ${from} has sha256 ${got.slice(0, 12)}…, the catalogue expects ${entry.sha256.slice(0, 12)}… — refused (the official file changed or the download is corrupt; never use a modified file)`);
    }
    const c = cacheFile(font, entry.dest);
    fs.mkdirSync(path.dirname(c), { recursive: true });
    fs.writeFileSync(c + '.part', buf);
    fs.renameSync(c + '.part', c);
    out.push({ entry, cached: c });
  };
  for (const entry of missing.filter((e) => e.fetch.url)) {
    log(`  ↓ ${entry.fetch.url}`);
    store(entry, await download(entry.fetch.url), entry.fetch.url);
  }
  for (const [key, entries] of byArchive) {
    const a = await fromArchive(font, key, entries.map((e) => e.fetch.member), log);
    let ok = false;
    try { for (const e of entries) store(e, a.get(e.fetch.member), `${key}:${e.fetch.member}`); ok = true; } finally { a.done(ok); }
  }
  const lic = out.find((o) => o.entry === font.licenseFile);
  if (!isOfl11(fs.readFileSync(lic.cached, 'utf8'))) {
    throw new Error(`${font.id}: licence file ${font.licenseFile.dest} is not the SIL Open Font License 1.1 text — refused`);
  }
  return out;
}

/** download (if needed) and copy fonts into <projectDir>/<dest>, unmodified */
export async function installFonts(projectDir, fonts, { log = console.log } = {}) {
  for (const font of fonts) {
    const files = await ensureFont(font, { log });
    for (const { entry, cached } of files) {
      const dest = path.join(projectDir, entry.dest);
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.copyFileSync(cached, dest);
      if (shaFile(dest) !== entry.sha256) throw new Error(`${entry.dest}: hash mismatch after copy`);
    }
  }
}
