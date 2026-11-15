#!/usr/bin/env node
/**
 * install_vendor.mjs — put the third-party runtime libraries (GSAP) into a project, or repair them.
 *
 *   node install_vendor.mjs <projectDir>        download (once, cached) from the official registry, verify, copy
 *   node install_vendor.mjs --list              what is installed and under which licence
 *
 * new_project.mjs runs this for every new project. The skill repository itself does not contain these files
 * (assets/vendor/catalog.json pins their official source and hashes).
 */
import path from 'node:path';
import fs from 'node:fs';
import { installVendor, loadVendorCatalog } from './lib/vendorfetch.mjs';

const arg = process.argv[2];
if (!arg || arg === '--list') {
  for (const l of loadVendorCatalog().libs) {
    console.log(`${l.name} ${l.version} — ${l.license} (${l.licenseUrl})\n  source: ${l.archive.url}\n  ${l.licenseNote}\n  files: ${l.files.map((f) => f.dest).join(', ')}`);
  }
  if (!arg) console.log('\nusage: node install_vendor.mjs <projectDir>');
  process.exit(0);
}
const dir = path.resolve(arg);
if (!fs.existsSync(path.join(dir, 'index.html'))) { console.error(`no index.html in ${dir}`); process.exit(2); }
// a folder an older new_project.mjs left half-made (a download failed after the template was copied): GSAP alone does
// not make it a project — the title, stage size, script.json and layout tokens are missing too
const left = fs.readFileSync(path.join(dir, 'index.html'), 'utf8').match(/\{\{(TITLE|LANG|W|H)\}\}/g);
if (left) {
  console.error(`✖ ${dir} is an unfinished project (index.html still has ${[...new Set(left)].join(' ')}) — new_project.mjs stopped before the end.\n` +
    `  Make it again: node ${path.join(path.dirname(process.argv[1]), 'new_project.mjs')} ${dir} --title "…" [--aspect …] --force`);
  process.exit(1);
}
try {
  await installVendor(dir);
  console.log(`✓ vendor libraries installed in ${dir} (unmodified, sha256-verified)`);
} catch (e) {
  console.error('✖ ' + e.message);
  process.exit(1);
}
