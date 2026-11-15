/**
 * vendorfetch.mjs — third-party runtime libraries (GSAP) on demand. The skill repository does not redistribute them:
 * assets/vendor/catalog.json pins the official archive (npm tarball + its sha512 integrity) and the sha256 of every
 * file a project needs. installVendor() downloads the archive once into a cache (~/.cache/motion-video-vendor, or
 * $MOTION_VIDEO_VENDOR_CACHE), verifies it, and copies the files unmodified — licence notices intact — into the project.
 * A mismatch is an error; there is no other source and no fallback.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { download, extract } from './fontfetch.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
export const VENDOR_CATALOG = path.resolve(here, '..', '..', 'assets', 'vendor', 'catalog.json');
export const VENDOR_CACHE = process.env.MOTION_VIDEO_VENDOR_CACHE || path.join(os.homedir(), '.cache', 'motion-video-vendor');

export const loadVendorCatalog = () => JSON.parse(fs.readFileSync(VENDOR_CATALOG, 'utf8'));
const sha256 = (b) => crypto.createHash('sha256').update(b).digest('hex');
const cached = (lib, f) => path.join(VENDOR_CACHE, `${lib.id}@${lib.version}`, f.member);

/** make sure every file of `lib` is in the cache, verified; returns [{ file, path }] */
export async function ensureVendor(lib, { log = () => {} } = {}) {
  const missing = lib.files.filter((f) => !(fs.existsSync(cached(lib, f)) && sha256(fs.readFileSync(cached(lib, f))) === f.sha256));
  if (missing.length) {
    const a = lib.archive;
    log(`  fetching ${lib.name} ${lib.version} from the official registry (${lib.license})`);
    log(`  ↓ ${a.url}`);
    const buf = await download(a.url);
    const [algo, want] = a.integrity.split('-');
    const got = crypto.createHash(algo).update(buf).digest('base64');
    if (got !== want) throw new Error(`${lib.id}: ${a.url} failed its ${algo} integrity check — refused (corrupt download or the published file changed)`);
    fs.mkdirSync(VENDOR_CACHE, { recursive: true });
    const arch = path.join(VENDOR_CACHE, `${lib.id}-${lib.version}.${a.type}`);
    fs.writeFileSync(arch, buf);
    let tmp;
    try {
      tmp = extract(arch, a.type, missing.map((f) => f.member), `${lib.id}: could not extract ${path.basename(a.url)}`);
      for (const f of missing) {
        const b = fs.readFileSync(path.join(tmp, f.member));
        if (sha256(b) !== f.sha256) throw new Error(`${lib.id}: ${f.member} has sha256 ${sha256(b).slice(0, 12)}…, the catalogue expects ${f.sha256.slice(0, 12)}… — refused`);
        fs.mkdirSync(path.dirname(cached(lib, f)), { recursive: true });
        fs.writeFileSync(cached(lib, f), b);
      }
    } finally {
      if (tmp) fs.rmSync(tmp, { recursive: true, force: true });
      fs.rmSync(arch, { force: true });
    }
  }
  return lib.files.map((f) => ({ file: f, path: cached(lib, f) }));
}

/** download (if needed) and copy the catalogue libraries into <projectDir>, unmodified */
export async function installVendor(projectDir, ids = null, { log = console.log } = {}) {
  const cat = loadVendorCatalog();
  for (const lib of cat.libs.filter((l) => !ids || ids.includes(l.id))) {
    for (const { file, path: src } of await ensureVendor(lib, { log })) {
      const dest = path.join(projectDir, file.dest);
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.copyFileSync(src, dest);
      if (sha256(fs.readFileSync(dest)) !== file.sha256) throw new Error(`${file.dest}: hash mismatch after copy`);
    }
  }
}

/** problems with the vendor files of a project: missing or modified (for check.mjs) */
export function auditVendor(projectDir) {
  const errors = [];
  for (const lib of loadVendorCatalog().libs) {
    for (const f of lib.files) {
      const p = path.join(projectDir, f.dest);
      if (!fs.existsSync(p)) errors.push(`${f.dest} is missing — node <skill>/scripts/install_vendor.mjs ${projectDir}`);
      else if (sha256(fs.readFileSync(p)) !== f.sha256) errors.push(`${f.dest} differs from ${lib.name} ${lib.version} as published — never edit vendor files (their licence notices must stay intact); restore with install_vendor.mjs`);
    }
  }
  return errors;
}
