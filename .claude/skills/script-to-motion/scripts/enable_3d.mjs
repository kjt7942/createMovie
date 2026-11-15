#!/usr/bin/env node
/**
 * enable_3d.mjs — add three.js to a video project (idempotent).
 *
 *   node enable_3d.mjs <projectDir>          classic build: WebGLRenderer + Stage3D (GLB, RoomEnvironment, OutlineEffect)
 *                                            (--classic: also switch an FX project back to it)
 *   node enable_3d.mjs <projectDir> --fx     FX build: WebGPURenderer on WebGL2 + TSL + post-processing nodes + StageFX
 *                                            (bloom, light rays, depth of field, mask transitions, GPU particles…)
 *
 * Both are classic-script builds exposing window.THREE, because Chrome blocks ES modules on file://. A project uses one
 * of them: --fx switches a classic project to the FX build (Stage3D code must then move to `await StageFX.create`).
 * An FX project stays FX when this runs without --fx (nothing changes); `--classic` switches it back explicitly.
 * See references/threejs-3d.md (classic) and references/shader-fx.md (FX).
 * The copied files are recorded in the project's generated.json (lib/generated.mjs).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { recordGenerated } from './lib/generated.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(here, '..', 'assets', 'three');
const args = process.argv.slice(2);
const fxMode = args.includes('--fx');
const dir = path.resolve(args.find((a) => !a.startsWith('--')) || '.');
const indexPath = path.join(dir, 'index.html');
if (!fs.existsSync(indexPath)) { console.error(`no index.html in ${dir}`); process.exit(2); }
if (fxMode && args.includes('--classic')) { console.error('--fx or --classic, not both'); process.exit(2); }
// an FX project is never switched back to the classic build by accident (that deletes the FX build): only with --classic
if (!fxMode && !args.includes('--classic') && fs.readFileSync(indexPath, 'utf8').includes('vendor/three/stagefx.js')) {
  console.log(`• ${path.relative(process.cwd(), dir) || '.'} uses the FX build (vendor/three/stagefx.js) — nothing changed. Its StageFX loads GLBs too` +
    ' (StageFX.loadGLB). Refresh it with --fx; switch back to the classic build only on purpose with --classic.');
  process.exit(0);
}

const dest = path.join(dir, 'vendor', 'three');
fs.mkdirSync(dest, { recursive: true });
const files = fxMode ? ['three.fx.bundle.min.js', 'stagefx.js', 'three.LICENSE'] : ['three.bundle.min.js', 'stage3d.js', 'three.LICENSE'];
for (const f of files) fs.copyFileSync(path.join(src, f), path.join(dest, f));

const CLASSIC = '<script src="vendor/three/three.bundle.min.js"></script>\n  <script src="vendor/three/stage3d.js"></script>';
const FX = '<script src="vendor/three/three.fx.bundle.min.js"></script>\n  <script src="vendor/three/stagefx.js"></script>';
let html = fs.readFileSync(indexPath, 'utf8');
const want = fxMode ? FX : CLASSIC, other = fxMode ? CLASSIC : FX;
if (html.includes(other)) {
  html = html.replace(other, want);
  for (const f of fxMode ? ['three.bundle.min.js', 'stage3d.js'] : ['three.fx.bundle.min.js', 'stagefx.js']) fs.rmSync(path.join(dest, f), { force: true });
  console.log(`• switched ${fxMode ? 'classic → FX' : 'FX → classic'} build — update js/scenes.js (${fxMode ? 'Stage3D.create → await StageFX.create' : 'StageFX → Stage3D'})`);
} else if (!html.includes(want)) {
  const anchor = '<script src="js/cues.js"></script>';
  if (!html.includes(anchor)) { console.error('✖ index.html has no <script src="js/cues.js"> to insert before'); process.exit(1); }
  html = html.replace(anchor, `${want}\n  ${anchor}`);
}
fs.writeFileSync(indexPath, html);
// generated.json: the build is the skill's own copy, byte for byte (check.mjs verifies it by sha256 — the FX bundle
// carries three.js's own small data: textures); recorded after a switch removed the other build's files
recordGenerated(files.map((f) => path.join(dest, f)), 'enable_3d.mjs');
const bundle = files[0];
console.log(`✓ three.js ${fxMode ? 'FX build' : 'classic build'} enabled in ${path.relative(process.cwd(), dir) || '.'} (vendor/three/${bundle}, ${(fs.statSync(path.join(dest, bundle)).size / 1024).toFixed(0)} KB)`);
console.log(fxMode
  ? '  next: <canvas id="gl"> in a scene, `const fx = await StageFX.create(canvas, { W, H, background })` in scenes.js — references/shader-fx.md'
  : '  next: a <canvas id="gl"> in a scene, Stage3D.create(...) in scenes.js — references/threejs-3d.md');
