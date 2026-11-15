#!/usr/bin/env node
/**
 * check.mjs — static checks for a script-to-motion project (no browser needed).
 *
 *   node check.mjs <projectDir>
 *
 * Catches the mistakes that are invisible without watching the page: syntax errors, cue ids or
 * #ids that don't exist, unused cues, stale timings, and code that breaks seek/determinism.
 * Exit code 1 when there are errors (warnings don't fail).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import { auditFonts, allowedFonts, stackProblems, genericOnlyStacks, genericFirstStacks } from './lib/fonts.mjs';
import { auditGlyphs } from './lib/glyphs.mjs';
import { auditVendor, loadVendorCatalog } from './lib/vendorfetch.mjs';
import { readRecord } from './lib/generated.mjs';
import { allSettings, FISH_KEY_NAMES } from './lib/env.mjs';
import { scriptSignature } from './lib/scriptsig.mjs';
import { phraseTimes } from './lib/phrases.mjs';

const dir = path.resolve(process.argv[2] || '.');
let data;
const errors = [];
const warnings = [];
const err = (m) => errors.push(m);
const warn = (m) => warnings.push(m);
const read = (p) => fs.readFileSync(path.join(dir, p), 'utf8');
const exists = (p) => fs.existsSync(path.join(dir, p));

// ---------- files ----------
const required = [
  'index.html', 'script.json', 'css/player.css', 'css/style.css', 'js/player.js', 'js/scenes.js',
  'fonts/PretendardVariable.woff2',
];
for (const f of required) if (!exists(f)) err(`missing ${f}`);
// third-party runtime (GSAP): present and exactly as published — licence notices intact (assets/vendor/catalog.json)
for (const e of auditVendor(dir)) err(e);
if (!exists('js/cues.js')) err('missing js/cues.js — run scripts/tts.mjs');
if (errors.length) finish();

// ---------- render.py: the project's copy of the skill's (the only way the picture is looked at) ----------
{
  const skillPy = path.join(path.dirname(new URL(import.meta.url).pathname), '..', 'assets', 'template', 'render.py');
  const ownPy = path.join(dir, 'render.py');
  if (!fs.existsSync(ownPy)) warn(`no render.py in the project — copy the skill's: cp ${skillPy} ${ownPy}`);
  else if (fs.existsSync(skillPy) && fs.readFileSync(ownPy, 'utf8') !== fs.readFileSync(skillPy, 'utf8'))
    warn(`render.py differs from the skill's (an older copy may not know --at/--res/--crop/--via/--art) — update it: cp ${skillPy} ${ownPy}`);
}

// ---------- cues ----------
try {
  const ctx = { window: {} };
  vm.runInNewContext(read('js/cues.js'), ctx, { filename: 'cues.js' });
  data = ctx.window.VIDEO_DATA;
} catch (e) {
  err(`js/cues.js does not evaluate: ${e.message}`);
  finish();
}
if (!data || !Array.isArray(data.cues) || !data.cues.length) {
  err('js/cues.js has no cues');
  finish();
}
const cueIds = new Set(data.cues.map((c) => c.id));
let prevEnd = 0;
for (const c of data.cues) {
  if (!(c.duration > 0)) err(`cue ${c.id}: duration ${c.duration}`);
  if (c.start < prevEnd - 1e-6) err(`cue ${c.id} starts before the previous cue ends`);
  prevEnd = c.end;
}
if (!exists(data.audio)) err(`narration file ${data.audio} is missing`);
// cues not recorded yet: silent placeholders with estimated timing (per cue; a js/cues.js from before the per-cue flag
// marks only the whole file)
const placeholderIds = data.cues.filter((c) => c.placeholder || (data.placeholder && !data.cues.some((x) => 'placeholder' in x))).map((c) => c.id);
// a take kept exactly as recorded with no "cut" for it yet: nobody has read it — where its silence is and what comes out is
// the agent's call (references/sound.md §1), so it must be made before the hand-off
const unreviewedIds = data.cues.filter((c) => c.unreviewed).map((c) => c.id);
if (unreviewedIds.length) err(`${unreviewedIds.length} take(s) not read yet (${unreviewedIds.join(', ')}): kept exactly as recorded, edges included — read them (node wave.mjs <dir> --unreviewed), set each cue's "cut" in script.json ("ranges": [] when nothing goes), run tts.mjs again`);
if (placeholderIds.length) warn(`narration not recorded yet for ${placeholderIds.length} of ${data.cues.length} cue(s) (${placeholderIds.join(', ')}): silent placeholders with estimated timing — expected until the user has reviewed the finished video and decides to record (then tts.mjs --approved; the scenes follow the new timings), or make it a video without narration ("narration": false in script.json)`);

try {
  const script = JSON.parse(read('script.json'));
  if (data.scriptSig) {
    // everything js/cues.js is built from (lines, spoken forms, gaps, leadIn/gap/tail, voice …) — lib/scriptsig.mjs
    if (data.scriptSig !== scriptSignature(script)) warn('script.json changed since js/cues.js was generated — re-run tts.mjs');
  } else {   // js/cues.js from before scriptSig: compare what it carries
    const a = JSON.stringify((script.cues || []).map((c) => [c.id, c.say, c.gapAfter ?? null, c.captions || null]));
    const b = JSON.stringify(data.cues.map((c, i) => [c.id, c.say, (script.cues[i] || {}).gapAfter ?? null, c.captions || null]));
    if (a !== b) warn('script.json changed since js/cues.js was generated — re-run tts.mjs');
  }
  if ((script.narration === false) !== (data.narration === false)) warn(`script.json says narration ${script.narration === false ? 'off' : 'on'} but js/cues.js was made ${data.narration === false ? 'without' : 'with'} it — re-run tts.mjs`);
} catch (e) {
  err(`script.json: ${e.message}`);
}

// ---------- scenes.js ----------
const scenesSrc = read('js/scenes.js');
for (const f of ['js/player.js', 'js/scenes.js']) {
  try {
    new vm.Script(read(f), { filename: f });
  } catch (e) {
    err(`${f}: syntax error — ${e.message}`);
  }
}

// long videos: one builder per chapter in js/seg/*.js (references/long-form.md) — checked like scenes.js
const segFiles = fs.existsSync(path.join(dir, 'js', 'seg')) ? fs.readdirSync(path.join(dir, 'js', 'seg')).filter((f) => f.endsWith('.js')).map((f) => `js/seg/${f}`) : [];
for (const f of segFiles) {
  try { new vm.Script(read(f), { filename: f }); } catch (e) { err(`${f}: syntax error — ${e.message}`); }
}
// comments stripped (roughly) so commented-out examples don't trigger checks
const stripComments = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
const code = [scenesSrc, ...segFiles.map(read)].map(stripComments).join('\n');
const html = read('index.html').replace(/<!--[\s\S]*?-->/g, '');
const css = read('css/style.css');

if (!/Video\.define\s*\(/.test(stripComments(scenesSrc))) err('js/scenes.js never calls Video.define(...)');

// cue ids referenced in cue('..') calls and label positions ('c03', 'c03+=0.2', 'c03_end-=0.4'). GSAP puts a position
// that names an unknown label at the END of the timeline without a word, so every label-like position must be a cue
// label (or one the scenes add themselves with tl.addLabel / tl.add('name')).
for (const m of code.matchAll(/cue\(\s*['"`]([^'"`]+)['"`]\s*\)/g)) {
  if (!cueIds.has(m[1])) err(`scenes.js: cue('${m[1]}') — no such cue`);
}
{
  const labels = new Set([...cueIds].flatMap((id) => [id, id + '_end']));
  for (const m of code.matchAll(/(?<!classList\s*)\.(?:addLabel|add)\(\s*(['"`])([A-Za-z_][\w-]*)\1/g)) labels.add(m[2]);
  // the project's cue-id pattern (c01 → c\d+): a string shaped like a cue id is meant as one
  const shapes = new RegExp(`^(?:${[...cueIds].map((id) => id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\d+/g, '\\d+')).join('|')})(?:_end)?$`);
  const LABELISH = /^([A-Za-z][\w-]*?)(?:([+-]=)[\d.]+)?$/;
  // which argument of a timeline method is its position: tl.to(target, vars, POS) … scene(target, FROM, TO)
  const POS = { to: [2], from: [2], set: [2], fromTo: [3], call: [2], add: [1], addLabel: [1], addPause: [0], tweenTo: [0], tweenFromTo: [0, 1], scene: [1, 2] };
  const TL = /^(?:\w*(?:tl|Tl|TL|timeline|Timeline)|\(chain\))$/;
  const DOMISH = /(?:^|\.)(?:classList\.\w+|setAttribute|getAttribute|removeAttribute|querySelector(?:All)?|getElementById|getElementsBy\w+|createElement(?:NS)?|closest|matches|addEventListener|removeEventListener|dispatchEvent|postMessage|log|warn|error|info|has|get|delete)$/;
  const told = new Set();
  for (const [f, src] of [['js/scenes.js', stripComments(scenesSrc)], ...segFiles.map((g) => [g, stripComments(read(g))])]) {
    for (const a of callArgs(src)) {
      const m = a.value.match(LABELISH);
      if (!m) continue;
      const label = m[1];
      if (labels.has(label)) continue;
      const [recv, name] = a.callee.includes('.') ? [a.callee.slice(0, a.callee.lastIndexOf('.')), a.callee.slice(a.callee.lastIndexOf('.') + 1)] : ['', a.callee];
      const atPos = Object.hasOwn(POS, name) && POS[name].includes(a.index) && (name === 'scene' ? !recv : ['add', 'call', 'addPause', 'tweenTo', 'tweenFromTo'].includes(name) ? TL.test(recv) : recv !== 'gsap');
      // anything else: only strings shaped like this project's cue ids (or with an offset), never DOM / Map / console calls
      if (!atPos && (DOMISH.test(a.callee) || !(shapes.test(label) || m[2]))) continue;
      const key = `${f}|${a.value}`;
      if (told.has(key)) continue;
      told.add(key);
      err(`${f}: position '${a.value}' (in ${a.callee}${a.index < 0 ? '' : '(…)'}) refers to unknown label ${label} — GSAP would silently put it at the END of the timeline; cue labels: ${[...cueIds].slice(0, 3).join(', ')}${cueIds.size > 3 ? ' …' : ''} and <id>_end`);
    }
  }
  // offsets inside any string ('intro_1+=0.2'), wherever they are passed
  for (const m of code.matchAll(/(['"`])([A-Za-z][\w-]*?)([+-]=[\d.]+)\1/g)) {
    if (labels.has(m[2]) || [...told].some((k) => k.endsWith(`|${m[2]}${m[3]}`))) continue;
    err(`scenes.js: position '${m[2]}${m[3]}' refers to unknown label ${m[2]} (GSAP would silently append it at the end)`);
  }
}
const referenced = (id) => new RegExp(`['"\`]${id}(_end)?([+-]=|['"\`])|cue\\(\\s*['"\`]${id}['"\`]`).test(code);
const unused = data.cues.filter((c) => !referenced(c.id)).map((c) => c.id);
if (unused.length && !/\bcues\s*(\.\s*(forEach|map|filter|find|slice|at)\b|\[)|\bfor\s*\(\s*const\s+\w+\s+of\s+cues\b|=\s*cues\b/.test(code)) {
  warn(`cues never referenced in scenes.js: ${unused.join(', ')} — every narration beat should drive something on screen`);
}

// determinism / seekability
const rules = [
  [/Math\.random\s*\(/, 'error', 'Math.random() — use rand(seed) so every playback and seek looks identical'],
  [/\bDate\.now\s*\(|new\s+Date\s*\(/, 'error', 'Date — visuals must depend only on the playhead t'],
  [/performance\.now\s*\(/, 'error', 'performance.now() — use the t passed to onFrame'],
  [/\b(setTimeout|setInterval|requestAnimationFrame)\s*\(/, 'error', 'timers/rAF — the player drives every frame; use tl or onFrame(t)'],
  [/\bgsap\s*\.\s*(to|from|fromTo)\s*\(/, 'error', 'standalone gsap.to/from/fromTo plays on wall-clock time — put tweens on tl (gsap.set is fine)'],
  [/repeat\s*:\s*-1/, 'error', 'repeat: -1 inside the master timeline makes its duration infinite — use a finite repeat, a CSS @keyframes loop, or onFrame(t)'],
  [/\.call\s*\(|on(Complete|Start|Repeat|ReverseComplete)\s*:/, 'warn', 'timeline callbacks fire unreliably when seeking — prefer tweened properties or onFrame(t)'],
  [/\.play\s*\(\s*\)|\.restart\s*\(/, 'warn', 'play()/restart() on a tween/timeline — the player owns playback'],
  [/\.style\.display\s*=|display\s*:\s*['"]none/, 'warn', 'toggling display restarts CSS animations and breaks layout measurement — use scene() / autoAlpha'],
  [/new\s+THREE\.Clock|\.getDelta\s*\(|\.getElapsedTime\s*\(|setAnimationLoop\s*\(/, 'error', 'three.js clock/animation loop — render from onFrame(t) only'],
  [/mixer\w*\.update\s*\(/i, 'error', 'AnimationMixer.update(delta) accumulates time — use mixer.setTime(t) in onFrame'],
  [/\bscrambleText\s*:/, 'error', 'scrambleText (GSAP ScrambleTextPlugin) picks its characters with Math.random — the same t shows different letters after a seek; use FXKit kick() (references/fx-kit.md) or a scramble hashed from (char index, frame)'],
];
for (const [re, level, msg] of rules) if (re.test(code)) (level === 'error' ? err : warn)(`scenes.js: ${msg}`);

// the same determinism rules for every other script the page runs that the author (or a worker) wrote:
// illustration modules (js/art/*.js, references/art-library.md) and any extra js/*.js
{
  const own = [];
  const jsDir = path.join(dir, 'js');
  for (const f of fs.existsSync(jsDir) ? fs.readdirSync(jsDir) : []) if (f.endsWith('.js') && !['scenes.js', 'player.js', 'cues.js'].includes(f)) own.push(`js/${f}`);
  const artDir = path.join(dir, 'js', 'art');
  for (const f of fs.existsSync(artDir) ? fs.readdirSync(artDir) : []) if (f.endsWith('.js')) own.push(`js/art/${f}`);
  const strip = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
  for (const f of own) {
    const src = strip(read(f));
    try { new vm.Script(src, { filename: f }); } catch (e) { err(`${f}: syntax error — ${e.message}`); continue; }
    for (const [re, level, msg] of rules.slice(0, 4).concat(rules.slice(-1))) if (re.test(src)) (level === 'error' ? err : warn)(`${f}: ${msg}`);
  }
  // speed: the narration (the TTS takes) and every clip with sound always play at 1× — in the code you write too. Only the
  // player's review keys change the speed (player.js, which media.js follows while reviewing). A silent clip may get its
  // own speed, but only through M.clip({ rate }) — never by setting a media element's or an audio node's playback rate.
  {
    const RATE = /\b(?:playbackRate|defaultPlaybackRate)\b/;
    const inline = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map((m) => m[1]).join('\n');
    const mine = [['js/scenes.js', code], ['index.html', inline], ...own.filter((f) => f !== 'js/media.js').map((f) => [f, strip(read(f))])];
    for (const [f, src] of mine) {
      if (RATE.test(src)) err(`${f}: sets a playback rate — the narration and clips with sound always play at 1× (SKILL.md → Working with the user); a silent clip's speed goes through M.clip(…, { rate }) (references/footage.md)`);
    }
  }
  // late drawing: something that is still loading or drawing after a seek needs busy(fn) (or an awaited decode() at build
  // time), else a frame-by-frame render (render.py) can capture it half-drawn (player-api.md §4). media.js does it itself.
  {
    const LATE = /\bnew\s+Worker\s*\(|createElement\(\s*['"`]iframe|<iframe\b|\bcreateImageBitmap\s*\(|\bnew\s+Image\s*\(|\.src\s*=(?!=)/;
    const segDir = path.join(dir, 'js', 'seg');
    const seg = fs.existsSync(segDir) ? fs.readdirSync(segDir).filter((f) => f.endsWith('.js')).map((f) => `js/seg/${f}`) : [];
    const all = [['js/scenes.js', strip(code)], ...[...own, ...seg].filter((f) => f !== 'js/media.js').map((f) => [f, strip(read(f))])];
    const busyAnywhere = all.some(([, src]) => /\bbusy\s*\(|\.renderBusy\s*=/.test(src));   // (or a page that defines renderBusy itself)
    for (const [f, src] of all) {
      if (!LATE.test(src) || busyAnywhere || /await\s[^;\n]*\.decode\s*\(/.test(src)) continue;
      warn(`${f}: loads or draws after a seek (img.src / new Image / iframe / Worker / createImageBitmap) and nothing registers busy(fn) — a frame-by-frame render (render.py) may capture it half-drawn: await img.decode() inside define for what is set once, busy(() => !img.complete) for what changes with t (player-api.md §4)`);
    }
  }
  // cokacmotion demo code pasted without porting: its runtime, modules and fonts don't exist here (references/cokacmotion.md §4)
  const PASTED = /\bdefineDemo\s*\(|_lib\/(?:stage|type)\.js|node_modules\/|@fontsource/;
  for (const [f, src] of [['index.html', html], ['js/scenes.js', code], ...own.map((f) => [f, strip(read(f))])]) {
    if (PASTED.test(src)) err(`${f}: cokacmotion demo code pasted as is (defineDemo, _lib/stage.js, node_modules/ or @fontsource) — port the technique into project code (references/cokacmotion.md §4)`);
  }
}

// shader FX build (StageFX): one clock, no internal-time nodes, effect chain intact (references/shader-fx.md §3)
const usesFX = html.includes('vendor/three/stagefx.js');
if (usesFX && html.includes('vendor/three/stage3d.js')) err('index.html loads both three.js builds — keep one (enable_3d.mjs switches)');
if (usesFX) {
  const fxRules = [
    [/\bTSL\s*\.\s*(time|deltaTime|frameId)\b|\{[^}]*\b(time|deltaTime|frameId)\b[^}]*\}\s*=\s*[\w.]*TSL\b/, 'error', 'TSL time/deltaTime/frameId run on performance.now(), not the playhead — use fx.uTime'],
    [/\bfilm\s*\(/, 'error', 'film() noise runs on TSL time (and is not in the FX build) — use the uTime grain recipe (shader-fx.md §4)'],
    [/\bStage3D\.create\s*\(/, 'error', 'this project uses the FX build — Stage3D.create → await StageFX.create'],
    [/(?<!await\s{0,4})\bStageFX\.create\s*\(/, 'error', 'StageFX.create is async — `const fx = await StageFX.create(...)` inside an async define'],
    [/(?<!await\s{1,4}[\w$.]*)\.textTexture\s*\(/, 'error', 'fx.textTexture is async (it loads the glyphs first) — await it'],
    [/\brenderer\s*\.\s*render\s*\(/, 'warn', 'renderer.render() bypasses the effect chain — call fx.render(t) in onFrame'],
    [/\brenderer\s*\.\s*compute\s*\(/, 'warn', 'renderer.compute() directly — register with fx.addCompute(node) (runs twice per frame: WebGL2 shows compute one frame late)'],
    [/\b(afterImage|motionBlur|traa)\s*\(/, 'warn', 'class-C effect (frame history): exact in continuous playback/recording, approximate after a seek and in snapshot stills'],
  ];
  for (const [re, level, msg] of fxRules) if (re.test(code)) (level === 'error' ? err : warn)(`scenes.js: ${msg}`);
  if (!/\bfx\w*\s*\.\s*render\s*\(\s*t\b|\.render\s*\(\s*t\s*\)/.test(code)) warn('scenes.js: no fx.render(t) found — shaders must receive the playhead (fx.render(t) in onFrame sets fx.uTime)');
}

// #ids used in scenes.js must exist in index.html (or be created in scenes.js)
const htmlIds = new Set([...html.matchAll(/\bid\s*=\s*["']([^"']+)["']/g)].map((m) => m[1]));
const madeIds = new Set([...code.matchAll(/\bid\s*=\s*['"`]([\w-]+)['"`]|\.id\s*=\s*['"`]([\w-]+)['"`]/g)].map((m) => m[1] || m[2]));
const missingIds = new Set();
for (const s of code.matchAll(/(['"`])((?:(?!\1)[^\\\n]|\\.)*)\1/g)) {
  for (const m of s[2].matchAll(/#([A-Za-z][\w-]*)/g)) {
    if (/^[0-9a-fA-F]{3,8}$/.test(m[1])) continue; // colour
    if (!htmlIds.has(m[1]) && !madeIds.has(m[1])) missingIds.add(m[1]);
  }
}
if (missingIds.size) err(`scenes.js targets #ids not found in index.html: ${[...missingIds].map((i) => '#' + i).join(', ')}`);

// every scene section should be scheduled
for (const m of html.matchAll(/<section[^>]*class=["'][^"']*\bscene\b[^"']*["'][^>]*>/g)) {
  const id = (m[0].match(/\bid=["']([^"']+)["']/) || [])[1];
  if (!id) warn('a <section class="scene"> has no id');
  else if (!new RegExp(`#${id}\\b`).test(code)) warn(`scene #${id} is never referenced in scenes.js (it would never show)`);
}

// styles
if (/(^|[;{\s])transition\s*:/m.test(css)) warn('style.css uses CSS transitions — they run on wall-clock time and ignore seeking; animate on tl instead');
if (/will-change/.test(css)) warn('style.css uses will-change — layers may stay blurry when the stage is scaled up (fullscreen/4K)');
// offline: what the page loads from the network is seen where the page really runs — errscan.mjs (lib/browser.mjs) and
// render.py report every request that is not to the project's own files; reading code can't tell (an address can be built)
// files index.html loads must exist (a missing script, stylesheet or image fails silently in the browser)
for (const m of html.matchAll(/<(script|link|img|source|video|audio|iframe|image|use|track|embed)\b[^>]*?\s(src|href|xlink:href|poster)\s*=\s*(?:"([^"]*)"|'([^']*)')/gi)) {
  const v = (m[3] ?? m[4] ?? '').trim();
  if (!v || /^(#|data:|blob:|about:|javascript:|mailto:|https?:|\/\/)/i.test(v) || /\$\{|\{\{/.test(v)) continue;
  let rel = v.split(/[?#]/)[0];
  try { rel = decodeURIComponent(rel); } catch { /* as written */ }
  if (rel && !fs.existsSync(path.resolve(dir, rel))) err(`index.html: <${m[1]} ${m[2]}="${v}"> — ${rel} does not exist`);
}

// originality (SKILL.md → Originality): every file in the project is accounted for — nothing passes by its name or its
// folder. A file passes when it is
//   · declared in provenance.json as the user's (source: "user");
//   · written by one of the skill's tools and recorded in generated.json with the same sha256 (lib/generated.mjs);
//   · one of the installed, unmodified font files (fonts/fonts.lock.json, the font catalogue) or vendor files (the vendor
//     catalogue) — pinned by sha256;
//   · empty;
//   · plain text of a kind the project is written in (TEXT_EXT, TEXT_NAME), valid UTF-8 — and then a .json that is a
//     Lottie animation (the Lottie spec's required w, h, fr, ip, op, layers) and media written into .html / .css / .js
//     (a data: URL of an image, video or audio; an SVG data: URL whose literal is not readable markup) are refused;
//   · a file the operating system keeps beside others, known by its format: .DS_Store, AppleDouble ._*, Thumbs.db, and
//     Python's cache of a .py beside its __pycache__/.
// Everything else is refused. Only .git/ is not looked into (version-control data, never part of the video). Links are
// followed (a master folder linked into the project is part of it).
// secrets, in the same pass: every file but a .env is searched for the user's Fish Audio API key itself — each value
// found where tts.mjs looks for it (the environment, the .env files from the project up, the skill's .env).
{
  const TEXT_EXT = new Set(['html', 'htm', 'css', 'js', 'mjs', 'cjs', 'json', 'jsonl', 'md', 'txt', 'srt', 'vtt', 'py', 'sh', 'csv', 'license']);
  const TEXT_NAME = new Set(['.gitignore', '.env', 'LICENSE', 'generated.json.lock']);
  const CODE_EXT = new Set(['html', 'htm', 'css', 'js', 'mjs', 'cjs']);
  const posixRel = (p) => path.posix.normalize(String(p).split('\\').join('/')).replace(/^\.\//, '');
  // provenance.json: the user's files
  let prov = { assets: [] };
  if (exists('provenance.json')) {
    try { prov = JSON.parse(read('provenance.json')); } catch (e) { err(`provenance.json is not valid JSON: ${e.message}`); }
  }
  const declared = new Set();
  for (const a of prov.assets || []) {
    if (!a || !a.file) { err('provenance.json: every entry needs "file"'); continue; }
    if (a.source !== 'user') err(`provenance.json: ${a.file} — only files the user provided belong here (source: "user"); everything else must be drawn in this project`);
    else if (!exists(a.file)) warn(`provenance.json lists ${a.file}, which is not in the project`);
    else declared.add(posixRel(a.file));
  }
  // generated.json: what the skill's tools wrote
  let made = { files: {} };
  try { made = readRecord(dir); } catch (e) { err(`generated.json is not valid JSON: ${e.message} — the skill's tools write it; run the tools that made the project's files again`); }
  // pinned bytes: installed fonts (auditFonts reports a broken lock) and vendor files (auditVendor reports a changed one)
  const pinnedFont = new Map(), pinnedVendor = new Map();
  for (const f of allowedFonts(dir).fonts) for (const x of f.files || []) pinnedFont.set(posixRel(x.dest), x.sha256);
  for (const lib of loadVendorCatalog().libs) for (const x of lib.files) pinnedVendor.set(posixRel(x.dest), x.sha256);
  // the user's API key, as tts.mjs finds it
  const keys = allSettings(dir, FISH_KEY_NAMES).map((k) => ({ ...k, buf: Buffer.from(k.value) }));
  const keep = Math.max(1, ...keys.map((k) => k.buf.length)) - 1;
  const hasKey = new Map();   // file → where its key came from
  const CHUNK = 1 << 24, piece = Buffer.allocUnsafe(CHUNK);
  // one read of a file: its sha256 when asked, and the keys in it (a key split across two pieces is found too)
  const pass = (abs, rel, wantHash) => {
    const h = wantHash ? crypto.createHash('sha256') : null;
    const scan = keys.length && path.posix.basename(rel) !== '.env';
    let tail = Buffer.alloc(0);
    const fd = fs.openSync(abs, 'r');
    try {
      for (let n; (n = fs.readSync(fd, piece, 0, CHUNK, null)) > 0;) {
        const b = piece.subarray(0, n);
        if (h) h.update(b);
        if (scan) {
          const win = tail.length ? Buffer.concat([tail, b]) : b;
          for (const k of keys) if (win.indexOf(k.buf) >= 0) hasKey.set(rel, k.where);
          tail = Buffer.from(win.subarray(Math.max(0, win.length - keep)));
        }
      }
    } finally { fs.closeSync(fd); }
    return h && h.digest('hex');
  };
  const startsWith = (abs, bytes, at = 0) => {
    const b = Buffer.alloc(bytes.length);
    const fd = fs.openSync(abs, 'r');
    try { fs.readSync(fd, b, 0, b.length, at); } finally { fs.closeSync(fd); }
    return b.equals(Buffer.from(bytes));
  };
  // a Lottie animation: an object with the spec's required members (lottie-spec schema: composition/animation.json
  // requires w, h (integer ≥ 0), fr (number > 0), op, ip (number); composition.json requires layers (array))
  const isLottie = (t) => {
    let j;
    try { j = JSON.parse(t); } catch { return false; }
    return !!j && typeof j === 'object' && !Array.isArray(j) && Number.isInteger(j.w) && j.w >= 0 && Number.isInteger(j.h) && j.h >= 0
      && typeof j.fr === 'number' && j.fr > 0 && typeof j.ip === 'number' && typeof j.op === 'number' && Array.isArray(j.layers);
  };
  // data: URLs written into code (RFC 2397: data:[<type>/<subtype>][;<parameter>…][;base64],<data>)
  const DATA = /(?<![\w-])data:([a-z0-9!#$&^_.+-]+)\/([a-z0-9!#$&^_.+-]+)((?:;[^,;"'`()\s]*)*),/gi;
  // the literal a data: URL is written in, from after its comma: to the closing quote of the string it starts (a template
  // literal also ends at its first ${), to ")" in an unquoted CSS url(…), else to whitespace, a quote or ">"
  const literalAfter = (t, start, from) => {
    const q = t[start - 1];
    let i = from;
    if (q === '"' || q === "'" || q === '`') {
      for (; i < t.length && t[i] !== q; i++) {
        if (t[i] === '\\') i++;
        else if (q === '`' && t[i] === '$' && t[i + 1] === '{') break;
      }
    } else if (q === '(') { while (i < t.length && t[i] !== ')') i++; }
    else { while (i < t.length && !/[\s"'`>]/.test(t[i])) i++; }
    return t.slice(from, i);
  };
  const embedded = (rel, t) => {
    const said = new Set();
    const once = (m) => { if (!said.has(m)) { said.add(m); err(m); } };
    for (const m of t.matchAll(DATA)) {
      const type = m[1].toLowerCase(), sub = m[2].toLowerCase();
      if (!['image', 'video', 'audio'].includes(type)) continue;   // fonts: check_fonts.mjs; text and data types are not media
      const line = t.slice(0, m.index).split('\n').length;
      const base64 = m[3].toLowerCase().split(';').includes('base64');
      if (type !== 'image' || sub !== 'svg+xml' || base64) {
        once(`${rel}:${line} embedded media (a data:${type}/${sub}${base64 ? ';base64' : ''} URL) — draw it in code; a user-provided file goes in assets/user/ with a provenance.json entry`);
        continue;
      }
      // an SVG written into the code must be readable: its literal is empty (the code builds the markup at run time) or
      // markup starting with "<" whose only percent-escape is %23 (#, which a URL needs escaped)
      const lit = literalAfter(t, m.index, m.index + m[0].length);
      if (lit.trim() && (!lit.trimStart().startsWith('<') || /%(?!23)[0-9a-f]{2}/i.test(lit))) {
        once(`${rel}:${line} an SVG pasted as an encoded data: URL (data:image/svg+xml,%3Csvg…) — its origin can't be read: draw it as inline <svg>, in js/art or as a readable data:image/svg+xml;utf8,<svg …> you wrote (escape only # as %23); a user-provided file goes in assets/user/ with a provenance.json entry`);
      }
    }
  };
  const UTF8 = new TextDecoder('utf-8', { fatal: true });
  const unaccounted = [], changed = [];
  const look = (rel, abs, size) => {
    const name = path.posix.basename(rel);
    const ext = name.includes('.') ? name.slice(name.lastIndexOf('.') + 1).toLowerCase() : '';
    if (declared.has(rel)) { pass(abs, rel, false); return; }
    const g = made.files[rel];
    if (g) { if (pass(abs, rel, true) !== g.sha256) changed.push(`${rel} (${g.by})`); return; }
    if (pinnedFont.has(rel)) { if (pass(abs, rel, true) !== pinnedFont.get(rel)) err(`${rel}: not the installed font file (sha256 differs from fonts.lock.json / the catalogue) — reinstall with add_font.mjs; never edit a font file`); return; }
    if (pinnedVendor.has(rel)) { pass(abs, rel, false); return; }
    if (size === 0) return;
    if (TEXT_EXT.has(ext) || TEXT_NAME.has(name)) {
      const b = fs.readFileSync(abs);
      if (name !== '.env') for (const k of keys) if (b.indexOf(k.buf) >= 0) hasKey.set(rel, k.where);
      let t;
      try { t = UTF8.decode(b); } catch { err(`${rel}: named as text (${ext ? '.' + ext : name}) but not UTF-8 text — a picture, sound or other data under a text name; draw it in code, or declare the user's file in provenance.json`); return; }
      if (ext === 'json' && isLottie(t)) err(`${rel}: a Lottie animation (the Lottie spec's w, h, fr, ip, op and layers) — animations are made here with GSAP; a Lottie file the user gave goes in assets/user/ with a provenance.json entry`);
      if (CODE_EXT.has(ext)) embedded(rel, t);
      return;
    }
    if ((name === '.DS_Store' && startsWith(abs, [0, 0, 0, 1, 0x42, 0x75, 0x64, 0x31]))           // Finder: \0\0\0\1Bud1
      || (name.startsWith('._') && startsWith(abs, [0, 5, 0x16, 7]))                                 // AppleDouble
      || (name === 'Thumbs.db' && startsWith(abs, [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]))  // Windows: OLE file
      || (ext === 'pyc' && path.posix.basename(path.posix.dirname(rel)) === '__pycache__' && startsWith(abs, [0x0d, 0x0a], 2)
        && exists(path.posix.join(path.posix.dirname(path.posix.dirname(rel)), name.split('.')[0] + '.py')))) return;
    pass(abs, rel, false);
    unaccounted.push(rel);
  };
  const walk = (rel, ancestors) => {
    const at = rel ? path.join(dir, rel) : dir;
    let real;
    try { real = fs.realpathSync(at); } catch { return; }
    if (ancestors.has(real)) return;                        // a link back up its own path
    const anc = new Set(ancestors).add(real);
    let ents;
    try { ents = fs.readdirSync(at, { withFileTypes: true }); } catch { return; }
    for (const e of ents.sort((x, y) => (x.name < y.name ? -1 : 1))) {
      const r = rel ? `${rel}/${e.name}` : e.name;
      let st;
      try { st = fs.statSync(path.join(dir, r)); } catch { continue; }   // a broken link: nothing to look at
      if (st.isDirectory()) { if (e.name !== '.git') walk(r, anc); } else if (st.isFile()) look(r, path.join(dir, r), st.size);
    }
  };
  walk('', new Set());
  // one line per folder (an old project can have thousands of unrecorded frames in one)
  const byFolder = (list) => {
    const m = new Map();
    for (const f of list) { const d = path.posix.dirname(f.split(' (')[0]); if (!m.has(d)) m.set(d, []); m.get(d).push(f); }
    return [...m].map(([d, fs_]) => (fs_.length === 1 ? fs_[0] : `${d === '.' ? './' : d + '/'} (${fs_.length} files: ${fs_.slice(0, 3).map((f) => path.posix.basename(f)).join(', ')}${fs_.length > 3 ? ' …' : ''})`));
  };
  for (const x of byFolder(unaccounted)) err(`${x} — not accounted for: not plain text, not recorded in generated.json by the skill's tools, not declared in provenance.json`);
  if (unaccounted.length) err('every file of the video is drawn here in code (SVG/CSS/canvas/js/art, Blender scripts) or given by the user: a user\'s file goes in assets/user/ with a provenance.json entry (source: "user"); a file a tool of the skill wrote before the tools kept generated.json — run that tool again (tts.mjs for audio/, tts.mjs --record-cache for cached takes with the user\'s OK; stills.mjs; thumbnail.mjs; enable_3d.mjs; blender_mcp.mjs run + embed_glb.mjs; render.py; snapshot.mjs clears old images from .snapshots/) or move it out of the project');
  for (const x of byFolder(changed)) err(`${x} — changed since the skill's tool wrote it (sha256 differs from generated.json) — run that tool again; never edit or replace a generated file`);
  for (const [f, where] of hasKey) err(`${f}: contains the user's Fish Audio API key (the one in ${where}) — remove it; keys belong only in the skill's .env (never in a project or a tracked file)`);
}

// footage (references/footage.md): every clip in js/media-src.js has its playback copy; a missing master only means the
// review tools can't cut its stills
if (exists('js/media-src.js') && /js\/media\.js/.test(html)) {
  try {
    const box = { window: {} };
    vm.runInNewContext(read('js/media-src.js'), box, { filename: 'media-src.js' });
    const clips = ((box.window.MEDIA_SRC || {}).clips) || {};
    for (const [k, c] of Object.entries(clips)) {
      if (!c.file || !exists(c.file)) err(`js/media-src.js: clip ${k} — playback file ${c.file} is missing`);
      if (!(c.w > 0 && c.h > 0)) err(`js/media-src.js: clip ${k} needs w and h (the master's pixel size)`);
      if (c.master && !fs.existsSync(path.resolve(dir, c.master))) warn(`js/media-src.js: clip ${k} — master ${c.master} not found (stills.mjs can't cut its review frames)`);
    }
  } catch (e) { err(`js/media-src.js does not evaluate: ${e.message}`); }
}
// phrase times (script.json "at" → sync.mjs → js/sync.js): js/sync.js must say exactly what the agent set, for the takes
// there are now (lib/phrases.mjs, the same conversion sync.mjs makes)
{
  let script = null;
  try { script = JSON.parse(read('script.json')); } catch { /* reported above */ }
  const set = script ? (script.cues || []).filter((c) => c.at != null) : [];
  let S = null;
  if (exists('js/sync.js')) {
    try {
      const box = { window: {} };
      vm.runInNewContext(read('js/sync.js'), box, { filename: 'sync.js' });
      S = box.window.SYNC || {};
    } catch (e) { err(`js/sync.js does not evaluate: ${e.message}`); }
  }
  if (set.length) {
    const byId = new Map(data.cues.map((c) => [c.id, c]));
    const want = {}, bad = [], stale = [];
    for (const sc of set) {
      const c = byId.get(sc.id);
      const pcm = c && c.take ? path.join(dir, '.tts-cache', `${c.take}.pcm`) : null;
      const r = phraseTimes(sc, c, pcm && fs.existsSync(pcm) ? fs.statSync(pcm).size / 2 / 44100 : null);
      if (r.problems) bad.push(...r.problems.map((x) => `${sc.id}: ${x}`));
      else if (r.stale) stale.push(`${sc.id} (${r.stale})`);
      else want[sc.id] = { take: c.take, d: c.duration, phrases: r.phrases };
    }
    for (const b of bad) err(`script.json "at" — ${b}`);
    if (stale.length) warn(`script.json "at" set on another take, not used: ${stale.join(', ')} — read the take now (wave.mjs --cue <id>) and set it again`);
    if (!bad.length && JSON.stringify(S || {}) !== JSON.stringify(want)) warn('js/sync.js does not say what script.json "at" sets for the takes now — run sync.mjs');
  } else if (S && Object.keys(S).length) {
    warn('js/sync.js has phrase times but script.json sets none ("at") — run sync.mjs (an older js/sync.js was measured by code; phrase times are now the agent\'s, references/sound.md §2)');
  }
}
// chapters (chapters.mjs) and subtitles (subs.mjs)
try {
  const script = JSON.parse(read('script.json'));
  for (const ch of script.chapters || []) if (!cueIds.has(ch.from)) err(`script.json chapters: no cue ${ch.from}`);
} catch { /* reported above */ }
if (exists('subs.json')) {
  try {
    const subs = JSON.parse(read('subs.json'));
    for (const [lang, tr] of Object.entries(subs.translations || {})) {
      const miss = data.cues.filter((c) => !tr[c.id]).map((c) => c.id);
      if (miss.length) warn(`subs.json: ${lang} has no translation for ${miss.slice(0, 6).join(', ')}${miss.length > 6 ? ' …' : ''}`);
    }
    for (const g of subs.extra || []) if (!cueIds.has(g.after)) err(`subs.json extra: no cue ${g.after}`);
  } catch (e) { err(`subs.json: ${e.message}`); }
}

// fonts — only the skill's catalogue fonts, unmodified, with licence files (SKILL.md → Fonts)
{
  const fa = auditFonts(dir);
  for (const e of fa.errors) err(e);
  for (const w of fa.warnings) warn(w);
  const bad = stackProblems(dir, fa.families);
  // glyph outlines (TypeFX, text_to_paths.mjs): made from installed catalogue OFL fonts, in sync with glyphs.json
  const ga = auditGlyphs(dir);
  for (const e of ga.errors) err(e);
  for (const w of ga.warnings) warn(w);
  if (bad.length) err(`font names outside the installed catalogue fonts (system/remote fonts vary per machine and may not be licensed for a published video): ${bad.join(', ')} — use ${[...fa.families].map((f) => `'${f}'`).join(', ')} + a generic fallback, or install one with add_font.mjs`);
  // a stack that names no installed font (only sans-serif, monospace … or a reset to the browser default) is drawn by a system font
  const gen = genericOnlyStacks(dir);
  if (gen.length) err(`font declarations with no installed font, only a generic family — the text would be drawn by a system font: ${gen.join(' · ')} — put an installed SIL OFL 1.1 family first ('Pretendard', sans-serif)`);
  // a generic family FIRST always matches: the installed family after it never draws anything
  const first = genericFirstStacks(dir);
  if (first.length) err(`font stacks that start with a generic family — it always matches, so a system font draws the text: ${first.join(' · ')} — put the installed family first ('Pretendard', sans-serif)`);
  // canvas text without ctx.font is drawn in the browser's default "10px sans-serif" — a system font
  const jsFiles = ['js/scenes.js', ...(fs.existsSync(path.join(dir, 'js')) ? fs.readdirSync(path.join(dir, 'js')).filter((f) => f.endsWith('.js') && !['scenes.js', 'player.js', 'cues.js', 'glyphs.js', 'sync.js'].includes(f)).map((f) => `js/${f}`) : []),
    ...['js/seg', 'js/art'].flatMap((d) => (fs.existsSync(path.join(dir, d)) ? fs.readdirSync(path.join(dir, d)).filter((f) => f.endsWith('.js')).map((f) => `${d}/${f}`) : []))];
  for (const f of jsFiles) {
    if (!fs.existsSync(path.join(dir, f))) continue;
    // comments and string contents out (a file of code shown on screen holds "fillText" as text, not as a call)
    const src = read(f).replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1')
      .replace(/'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\.|[^`\\])*`/g, '""');
    if (/\.(fillText|strokeText)\s*\(/.test(src) && !/\.font\s*=/.test(src)) warn(`${f}: draws canvas text (fillText/strokeText) but never sets ctx.font — the canvas default is "10px sans-serif", a system font: set ctx.font = "<size>px 'Pretendard', sans-serif" (an installed family first) before drawing`);
  }
}

finish();

/** the string literals passed directly as call arguments: [{ callee: 'tl.to' | '(chain).to' | 'scene', index, value }] —
 *  a small scanner (comments already stripped): brackets are tracked, other strings and template parts skipped */
function callArgs(src) {
  const out = [];
  const stack = [];
  let prev = '';                                   // the last significant character before the current one
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (ch === '"' || ch === "'" || ch === '`') {
      let j = i + 1;
      while (j < src.length && src[j] !== ch && (ch === '`' || src[j] !== '\n')) j += src[j] === '\\' ? 2 : 1;
      const value = src.slice(i + 1, j);
      let k = j + 1;
      while (k < src.length && /\s/.test(src[k])) k++;
      const top = stack[stack.length - 1];
      const plain = !(ch === '`' && value.includes('${'));
      if (top && top.callee && (prev === '(' || prev === ',') && (src[k] === ',' || src[k] === ')') && plain) {
        out.push({ callee: top.callee, index: top.index, value });
      } else if (top && top.ch === '{' && prev === ':' && (src[k] === ',' || src[k] === '}') && plain) {
        // an option that takes a time: TX.neon(el, t, { to: 'c04_end' }), K.x(…, { at: 'c05' })
        const key = (src.slice(Math.max(0, i - 40), i).match(/([A-Za-z_$][\w$]*)['"]?\s*:\s*$/) || [])[1];
        if (/^(from|to|at|start|end|pos|position|until|label|when)$/.test(key || '')) out.push({ callee: `{ ${key}: … }`, index: -1, value });
      }
      i = j;
      prev = ch;
      continue;
    }
    if (ch === '(') {
      const m = src.slice(Math.max(0, i - 120), i).match(/(\)\s*\.\s*)?([A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*)\s*$/);
      const callee = m && !/^(if|for|while|switch|catch|function|return|typeof)$/.test(m[2]) ? (m[1] ? '(chain).' : '') + m[2].replace(/\s+/g, '') : null;
      stack.push({ ch, callee, index: 0 });
    } else if (ch === '[' || ch === '{') stack.push({ ch, callee: null, index: 0 });
    else if (ch === ')' || ch === ']' || ch === '}') stack.pop();
    else if (ch === ',' && stack.length) stack[stack.length - 1].index++;
    if (!/\s/.test(ch)) prev = ch;
  }
  return out;
}

function finish() {
  const r = path.relative(process.cwd(), dir);
  const rel = !r ? '.' : r.startsWith('..') ? dir : r;
  for (const e of errors) console.log('✖ ' + e);
  for (const w of warnings) console.log('⚠ ' + w);
  if (!errors.length && !warnings.length) console.log(`✓ ${rel}: no problems found`);
  else console.log(`\n${rel}: ${errors.length} error(s), ${warnings.length} warning(s)`);
  if (data && data.cues) {
    console.log(`  ${data.cues.length} cues · narration ${data.audioDuration}s · video ${data.duration}s`);
  }
  process.exit(errors.length ? 1 : 0);
}
