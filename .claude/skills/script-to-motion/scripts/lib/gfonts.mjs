/**
 * gfonts.mjs — any SIL OFL 1.1 family from the Google Fonts repository (github.com/google/fonts), on demand.
 *
 * The repository sorts families by licence: ofl/<dir> (SIL Open Font License), apache/<dir>, ufl/<dir>. Only ofl/ is
 * accepted, and on top of that METADATA.pb must say license "OFL" and the family's OFL.txt must be the SIL OFL 1.1 text.
 * Everything is pinned: the google/fonts commit, and the sha256 of every installed file, recorded in the project's
 * fonts/fonts.lock.json. The files are copied unmodified with OFL.txt into fonts/<slug>/. check.mjs and check_fonts.mjs
 * accept exactly these files; a re-install reproduces them from the pinned commit.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { download, isOfl11, CACHE_DIR, REQUIRED_LICENSE } from './fontfetch.mjs';

const RAW = 'https://raw.githubusercontent.com/google/fonts';
export const gfDir = (family) => String(family).toLowerCase().replace(/[^a-z0-9]/g, '');
export const slug = (family) => String(family).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const sha256 = (b) => crypto.createHash('sha256').update(b).digest('hex');
export const lockPath = (dir) => path.join(dir, 'fonts', 'fonts.lock.json');

export function readLock(dir) {
  const p = lockPath(dir);
  if (!fs.existsSync(p)) return { schema: 1, note: 'fonts installed from Google Fonts (ofl/ only) by add_font.mjs — pinned commit + sha256 of every file. Generated; do not edit.', fonts: [] };
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}
export function writeLock(dir, lock) {
  fs.mkdirSync(path.dirname(lockPath(dir)), { recursive: true });
  fs.writeFileSync(lockPath(dir), JSON.stringify(lock, null, 2) + '\n');
}

/** the current commit of google/fonts main (git ls-remote — no API rate limit; API as a fallback) */
export async function currentCommit() {
  const r = spawnSync('git', ['ls-remote', 'https://github.com/google/fonts', 'refs/heads/main'], { encoding: 'utf8', timeout: 60000 });
  const m = !r.error && r.status === 0 && r.stdout.match(/^([0-9a-f]{40})/);
  if (m) return m[1];
  const j = JSON.parse((await download('https://api.github.com/repos/google/fonts/commits/main')).toString('utf8'));
  if (!/^[0-9a-f]{40}$/.test(j.sha || '')) throw new Error('could not resolve the google/fonts commit (network?)');
  return j.sha;
}

async function tryText(url) {
  try { return (await download(url, 1)).toString('utf8'); } catch { return null; }
}

/** METADATA.pb (text proto) → { name, license, category, fonts: [{ style, weight, filename, copyright }], axes, subsets } */
export function parseMetadata(txt) {
  const one = (re, s = txt) => (s.match(re) || [])[1];
  const fonts = [...txt.matchAll(/^fonts\s*{([^}]*)}/gm)].map(([, b]) => ({
    style: one(/style:\s*"([^"]+)"/, b) || 'normal', weight: Number(one(/weight:\s*(\d+)/, b) || 400),
    filename: one(/filename:\s*"([^"]+)"/, b), copyright: one(/copyright:\s*"([^"]*)"/, b) || '',
  }));
  const axes = [...txt.matchAll(/^axes\s*{([^}]*)}/gm)].map(([, b]) => ({
    tag: one(/tag:\s*"([^"]+)"/, b), min: Number(one(/min_value:\s*(-?[\d.]+)/, b)), max: Number(one(/max_value:\s*(-?[\d.]+)/, b)),
  }));
  return {
    name: one(/^name:\s*"([^"]+)"/m), license: one(/^license:\s*"([^"]+)"/m), category: [...txt.matchAll(/^category:\s*"([^"]+)"/gm)].map((m) => m[1]),
    fonts, axes, subsets: [...txt.matchAll(/^subsets:\s*"([^"]+)"/gm)].map((m) => m[1]),
  };
}

/** find the family in google/fonts at `commit`; refuse anything that is not OFL */
export async function resolveFamily(family, commit) {
  const dir = gfDir(family);
  const meta = await tryText(`${RAW}/${commit}/ofl/${dir}/METADATA.pb`);
  if (!meta) {
    for (const other of ['apache', 'ufl']) {
      if (await tryText(`${RAW}/${commit}/${other}/${dir}/METADATA.pb`)) {
        throw new Error(`"${family}" is in Google Fonts under ${other}/ (${other === 'apache' ? 'Apache License 2.0' : 'Ubuntu Font Licence'}) — not SIL OFL 1.1, so it can't be used; pick an OFL family (references/fonts.md)`);
      }
    }
    throw new Error(`"${family}" was not found in Google Fonts (looked for ofl/${dir}) — use the exact family name as on fonts.google.com`);
  }
  const m = parseMetadata(meta);
  if (m.license !== 'OFL') throw new Error(`"${family}": METADATA.pb says license "${m.license}" — SIL OFL 1.1 only`);
  if (!m.fonts.length) throw new Error(`"${family}": METADATA.pb lists no font files`);
  return { dir, meta: m };
}

/**
 * Install a Google Fonts OFL family into <projectDir>/fonts/<slug>/ and record it in fonts.lock.json.
 * weights: optional list of static weights to keep (variable files are always kept — they hold every weight).
 * A family already in the lock is reproduced from its pinned commit and hashes.
 */
export async function installGoogleFont(projectDir, family, { weights = null, log = console.log } = {}) {
  const lock = readLock(projectDir);
  const prev = lock.fonts.find((f) => f.family.toLowerCase() === String(family).toLowerCase());
  const commit = prev ? prev.commit : await currentCommit();
  const { dir, meta } = await resolveFamily(prev ? prev.family : family, commit);
  const id = slug(meta.name);
  const cacheDir = path.join(CACHE_DIR, `gf-${dir}@${commit.slice(0, 12)}`);
  const get = async (name) => {
    const c = path.join(cacheDir, name);
    if (fs.existsSync(c)) return fs.readFileSync(c);
    const url = `${RAW}/${commit}/ofl/${dir}/${encodeURIComponent(name)}`;
    log(`  ↓ ${url}`);
    const b = await download(url);
    fs.mkdirSync(cacheDir, { recursive: true });
    fs.writeFileSync(c + '.part', b);
    fs.renameSync(c + '.part', c);
    return b;
  };
  // licence first: the family's OFL.txt must be the SIL Open Font License 1.1
  const lic = await get('OFL.txt');
  if (!isOfl11(lic.toString('utf8'))) throw new Error(`"${meta.name}": OFL.txt is not the SIL Open Font License 1.1 text — refused`);
  const wAxis = meta.axes.find((a) => a.tag === 'wght');
  let picks = meta.fonts;
  if (weights && weights.length) picks = picks.filter((f) => /\[/.test(f.filename) || weights.includes(f.weight));
  if (!picks.length) throw new Error(`"${meta.name}": no file for weights ${weights.join(', ')} (available: ${[...new Set(meta.fonts.map((f) => f.weight))].join(', ')})`);
  const files = [];
  for (const f of picks) {
    const b = await get(f.filename);
    const want = prev && prev.files.find((x) => x.dest.endsWith('/' + f.filename));
    if (want && want.sha256 !== sha256(b)) throw new Error(`"${meta.name}": ${f.filename} differs from the sha256 pinned in fonts.lock.json — refused`);
    const dest = `fonts/${id}/${f.filename}`;
    fs.mkdirSync(path.join(projectDir, 'fonts', id), { recursive: true });
    fs.writeFileSync(path.join(projectDir, dest), b);
    files.push({ dest, sha256: sha256(b), bytes: b.length, style: f.style, weight: /\[/.test(f.filename) && wAxis ? `${wAxis.min} ${wAxis.max}` : String(f.weight) });
  }
  // a re-install with other weights replaces the set: font files of this family that are no longer pinned would be
  // stray font files (check.mjs) and stale @font-face targets
  const keep = new Set(files.map((f) => path.basename(f.dest)));
  for (const f of fs.readdirSync(path.join(projectDir, 'fonts', id))) {
    if (/\.(ttf|otf|woff2?|ttc|otc)$/i.test(f) && !keep.has(f)) { fs.rmSync(path.join(projectDir, 'fonts', id, f)); log(`  removed fonts/${id}/${f} (not among the weights installed now)`); }
  }
  const licDest = `fonts/${id}/OFL.txt`;
  fs.writeFileSync(path.join(projectDir, licDest), lic);
  const entry = {
    id, family: meta.name, source: 'google/fonts', path: `ofl/${dir}`, commit, license: REQUIRED_LICENSE,
    copyright: (meta.fonts[0] && meta.fonts[0].copyright) || '', category: meta.category.join(', '),
    axes: meta.axes, subsets: meta.subsets, files,
    licenseFile: { dest: licDest, sha256: sha256(lic), bytes: lic.length },
  };
  lock.fonts = lock.fonts.filter((f) => f.id !== id).concat(entry);
  writeLock(projectDir, lock);
  return entry;
}
