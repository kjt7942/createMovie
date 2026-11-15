#!/usr/bin/env node
/**
 * new_project.mjs — create a video project folder from the template.
 *
 *   node new_project.mjs <dir> --title "제목" [--lang ko] [--aspect 16:9|9:16|1:1|4:5|4:3|3:4|21:9|<W>x<H>] [--3d | --fx] [--force]
 *   (--3d adds the classic three.js build, --fx the shader-FX build — see enable_3d.mjs, references/shader-fx.md)
 *
 * Writes index.html (stage size + title), the runtime (player, GSAP, fonts), a starter style.css /
 * scenes.js, and a script.json skeleton holding the narration defaults (voice, model, gaps).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const template = path.join(here, '..', 'assets', 'template');

const argv = process.argv.slice(2);
const opt = { _: [] };
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a.startsWith('--')) {
    const k = a.slice(2);
    const v = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
    opt[k] = v;
  } else opt._.push(a);
}

if (!opt._[0] && typeof opt.title !== 'string') {
  console.error('usage: node new_project.mjs [<dir>] --title "Title" [--lang ko] [--aspect 16:9] [--3d | --fx] [--force] [--no-guard]\n' +
    '  without <dir> the project is made in projects/<YYYYMMDDHHMMSS>_<title>/ (under $SUMO_PROJECTS_DIR, or ./projects)');
  process.exit(2);
}

// stage sizes in logical px (the player scales the stage to any window/screen; text and vectors stay sharp)
const SIZES = {
  '16:9': [1920, 1080], '9:16': [1080, 1920], '1:1': [1080, 1080], '4:5': [1080, 1350],
  '4:3': [1440, 1080], '3:4': [1080, 1440], '21:9': [2520, 1080],
};
const aspect = typeof opt.aspect === 'string' ? opt.aspect : '16:9';
const custom = aspect.match(/^(\d{3,4})x(\d{3,4})$/);
if (!SIZES[aspect] && !custom) {
  console.error(`unknown --aspect ${aspect}; use one of ${Object.keys(SIZES).join(', ')} or a size like 2048x858`);
  process.exit(2);
}
const [W, H] = SIZES[aspect] || [Number(custom[1]), Number(custom[2])];
if (Math.min(W, H) < 360 || Math.max(W, H) > 4096) { console.error(`stage ${W}×${H}: keep each side between 360 and 4096 px`); process.exit(2); }
const title = typeof opt.title === 'string' ? opt.title : 'Untitled';
const lang = typeof opt.lang === 'string' ? opt.lang : 'ko';
// No <dir>: one folder for every project, named "<date and time>_<project name>" (e.g. projects/20261115101135_가족캠프)
const slug = (s) => String(s || '').replace(/[\\/:*?"<>|\u0000-\u001f]/g, '').trim().replace(/\s+/g, '_').replace(/^[._-]+/, '').slice(0, 40).replace(/[._-]+$/, '') || '영상';
const stamp = () => { const d = new Date(), p = (n) => String(n).padStart(2, '0'); return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`; };
let dir;
if (opt._[0]) dir = path.resolve(opt._[0]);
else {
  const base = path.resolve(process.env.SUMO_PROJECTS_DIR || 'projects', `${stamp()}_${slug(title)}`);
  dir = base;
  for (let n = 2; fs.existsSync(dir); n++) dir = `${base}_${n}`;   // same second, same name: never overwrite
}

if (fs.existsSync(dir) && !fs.statSync(dir).isDirectory()) {
  console.error(`${dir} exists and is not a folder.`);
  process.exit(1);
}
if (fs.existsSync(dir) && fs.readdirSync(dir).length && !opt.force) {
  console.error(`${dir} already exists and is not empty (use --force to copy the template over it).`);
  process.exit(1);
}

// The whole project is built in a temp folder next to <dir> and moved into place only when everything worked: a failed
// font or GSAP download (or Ctrl+C) leaves nothing half-made behind — no index.html with {{TITLE}} — and <dir> as it
// was. Only what this run created is removed; a folder that existed before is never deleted.
const parent = path.dirname(dir);
const existed = fs.existsSync(dir);
let work = null, madeParent, finished = false;
process.on('exit', () => {
  if (finished) return;
  if (work) fs.rmSync(work, { recursive: true, force: true });
  if (madeParent) fs.rmSync(madeParent, { recursive: true, force: true });
});
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(sig, () => process.exit(130));
if (!existed) madeParent = fs.mkdirSync(parent, { recursive: true });   // the first folder created, if any
try {
  work = fs.mkdtempSync(path.join(parent, `.${path.basename(dir)}.new-`));
} catch (e) {
  if (!existed) throw e;
  work = fs.mkdtempSync(path.join(dir, '.new-project-'));              // parent not writable: build inside the folder
}

// Plain per-file copy: fs.cpSync's native fast path fails on some mounts (e.g. virtiofs) with EACCES.
function copyTree(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, e.name);
    const to = path.join(dest, e.name);
    if (e.isDirectory()) copyTree(from, to);
    else fs.copyFileSync(from, to);
  }
}
// move the finished project into <dir>: files replace files of the same name (--force), folders are merged, anything
// else already in <dir> stays
function moveTree(src, dest) {
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, e.name);
    const to = path.join(dest, e.name);
    if (e.isDirectory() && fs.existsSync(to) && fs.statSync(to).isDirectory()) moveTree(from, to);
    else fs.renameSync(from, to);                                       // (replaces a file of that name)
  }
}
copyTree(template, work);

// core fonts (Pretendard, D2Coding, Noto Sans KR): the skill ships no font files — download them from their
// official sources (cached after the first project), verify sha256 + the SIL OFL 1.1 licence, copy unmodified
{
  const { loadCatalog } = await import('./lib/fonts.mjs');
  const { installFonts } = await import('./lib/fontfetch.mjs');
  try {
    await installFonts(work, loadCatalog().fonts.filter((f) => f.core));
  } catch (e) {
    console.error(`✖ core fonts: ${e.message}`);
    console.error(`  nothing was created — ${dir} is as it was; run the same command again`);
    process.exit(1);
  }
}

// third-party runtime (GSAP): not stored in the skill either — downloaded from the official npm registry (cached),
// integrity + sha256 verified, copied unmodified with its licence notices (assets/vendor/catalog.json)
{
  const { installVendor } = await import('./lib/vendorfetch.mjs');
  try {
    await installVendor(work);
  } catch (e) {
    console.error(`✖ vendor libraries: ${e.message}`);
    console.error(`  nothing was created — ${dir} is as it was; run the same command again`);
    process.exit(1);
  }
}

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
const indexPath = path.join(work, 'index.html');
fs.writeFileSync(
  indexPath,
  fs.readFileSync(indexPath, 'utf8')
    .replaceAll('{{TITLE}}', esc(title))
    .replaceAll('{{LANG}}', esc(lang))
    .replaceAll('{{W}}', String(W))
    .replaceAll('{{H}}', String(H)),
);

if (!fs.existsSync(path.join(dir, 'script.json')) || opt.force) {
  const skeleton = {
    title,
    lang,
    voice: '',            // the user's Fish Audio voice model id (required for real narration; tts.mjs)
    model: 'drama-3',
    temperature: 0.7,
    leadIn: 0.3,
    gap: 0.25,
    tail: 1.5,
    cues: [],
  };
  fs.writeFileSync(path.join(work, 'script.json'), JSON.stringify(skeleton, null, 2) + '\n');
}
// layout tokens for this aspect (SKILL.md → Aspect ratio): text margin, and for 9:16 the zones that Shorts / Reels /
// TikTok cover with their own UI, plus captions lifted above them
{
  const vertical = H / W >= 1.6, portrait = H > W, wide = W / H >= 2;
  const t = vertical
    ? { safe: 64, top: 240, bottom: 480, right: 180, caption: 500 }
    : portrait || W === H ? { safe: 64, top: 64, bottom: 64, right: 64, caption: 40 }
      : { safe: wide ? 120 : 96, top: wide ? 120 : 96, bottom: wide ? 120 : 96, right: wide ? 120 : 96, caption: 20 };
  const stylePath = path.join(work, 'css', 'style.css');
  fs.appendFileSync(stylePath, `
/* aspect ${aspect} · stage ${W}×${H} — layout tokens written by new_project.mjs (SKILL.md → Aspect ratio).
   --safe: minimum text margin. --safe-top/-bottom/-right: keep text and key visuals inside them${vertical ? `;
   in 9:16 they clear the UI that Shorts / Reels / TikTok draw over the video (approximate, conservative)` : ''}. */
:root { --safe: ${t.safe}px; --safe-top: ${t.top}px; --safe-bottom: ${t.bottom}px; --safe-right: ${t.right}px; }
#stage { --caption-bottom: ${t.caption}px;${vertical ? ` --caption-max: ${W - 2 * t.right}px;` : ''} }
`);
}
fs.mkdirSync(path.join(work, 'audio'), { recursive: true });
// screenshots/: render.py --screenshot sheets (review output, rebuilt any time)
fs.writeFileSync(path.join(work, '.gitignore'), '.tts-cache/\n.snapshots/\nscreenshots/\n.env\n');
if (opt['3d'] || opt.fx) {
  const r = (await import('node:child_process')).spawnSync(process.execPath, [path.join(here, 'enable_3d.mjs'), '.', ...(opt.fx ? ['--fx'] : [])], { stdio: 'inherit', cwd: work });
  if (r.status !== 0) {
    console.error(`  nothing was created — ${dir} is as it was`);
    process.exit(r.status || 1);
  }
}

// into place: a new folder in one rename; an existing (empty, or --force) folder gets the files moved in
if (!existed) fs.renameSync(work, dir);
else { moveTree(work, dir); fs.rmSync(work, { recursive: true, force: true }); }
finished = true;

console.log(`created ${dir}  (${aspect}, stage ${W}×${H}, lang ${lang})`);
// the looking guard in the Claude Code project's local settings: the picture is looked at only on render.py sheets —
// by this agent and by every subagent it briefs (SKILL.md's own hook does not reach subagents). --no-guard skips it.
if (!opt['no-guard']) {
  const g = (await import('node:child_process')).spawnSync(process.execPath, [path.join(here, 'hooks', 'install_guard.mjs')], { encoding: 'utf8' });
  console.log((g.stdout || g.stderr || '').trim() || 'looking guard: not installed (install_guard.mjs gave no answer)');
}
console.log('next: fill script.json cues, then run tts.mjs');
