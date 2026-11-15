#!/usr/bin/env node
/**
 * add_font.mjs — install a font into a project. SIL OFL 1.1 fonts only, from two sources:
 *
 *   node add_font.mjs <projectDir> <id> [<id> …]                  catalogue fonts (pinned, recommended): gowun-batang …
 *   node add_font.mjs <projectDir> "Do Hyeon" "Anybody" …          any Google Fonts family in its ofl/ directory
 *   node add_font.mjs <projectDir> "Gothic A1" --weights 400,800   static families: only these weights (a re-run with
 *                                                                  other weights replaces the set)
 *   node add_font.mjs <projectDir> "Tilt Warp" --token --tilt      also add a CSS token (custom property) to :root
 *   node add_font.mjs --list                                       the catalogue + where to find more (references/fonts.md)
 *
 * Catalogue fonts: assets/fonts/catalog.json pins each file's official URL and sha256.
 * Google Fonts: the family must live in google/fonts ofl/ (Apache/UFL families are refused), METADATA.pb must say OFL,
 * and its OFL.txt must be the SIL OFL 1.1 text. The google/fonts commit and the sha256 of every installed file are
 * recorded in fonts/fonts.lock.json, so the project can be checked and reproduced.
 * Either way the files are downloaded on demand (cached in ~/.cache/motion-video-fonts), copied unmodified with the
 * licence into fonts/<id>/, and @font-face rules are written to css/fonts.css (linked from index.html) — the family's
 * rules are rewritten from its catalogue / fonts.lock.json entry on every run.
 */
import fs from 'node:fs';
import path from 'node:path';
import { loadCatalog, faceCss, fontFaces } from './lib/fonts.mjs';
import { installFonts, REQUIRED_LICENSE } from './lib/fontfetch.mjs';
import { installGoogleFont } from './lib/gfonts.mjs';

const catalog = loadCatalog();
const argv = process.argv.slice(2);
const opt = { _: [] };
const OPTIONS = ['weights', 'token', 'list'];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '-l') { opt.list = true; continue; }
  if (!a.startsWith('--')) { opt._.push(a); continue; }
  const [k, inline] = a.slice(2).split(/=(.*)/s);
  const next = argv[i + 1];
  if (inline !== undefined) opt[k] = inline;
  // --token takes a CSS custom property name, which itself starts with -- (--token --serif)
  else if (k === 'token') opt[k] = next != null && !OPTIONS.includes(next.replace(/^--/, '')) ? argv[++i] : true;
  else opt[k] = next != null && !next.startsWith('--') ? argv[++i] : true;
}
const TOKEN_USAGE = '--token needs a CSS custom property name: --token --serif (then font-family: var(--serif))';
if (typeof opt.token === 'string') {
  if (/^[a-z]/i.test(opt.token)) opt.token = '--' + opt.token;   // --token serif → --serif
  if (!/^--[a-z][\w-]*$/i.test(opt.token)) { console.error(`✖ ${TOKEN_USAGE}`); process.exit(2); }
}

if (!opt._.length || opt.list || opt.l) {
  console.log(`Fonts — ${REQUIRED_LICENSE} only. Two sources: this catalogue (pinned, recommended), and any Google Fonts family`);
  console.log('in its ofl/ directory (add it by its family name). Choosing by tone: references/fonts.md.\n');
  for (const f of catalog.fonts) {
    console.log(`${f.core ? '●' : '○'} ${f.id.padEnd(17)} ${`'${f.family}'`.padEnd(20)} ${f.category.padEnd(11)} Hangul ${String(f.hangul).padStart(5)} · ${f.license}`);
    console.log(`  ${f.role}`);
    console.log(`  stack: ${f.token}: ${f.stack};   tones: ${f.tones.join(', ')}\n`);
  }
  console.log('● core (in every project)   ○ node add_font.mjs <projectDir> <id>');
  console.log('Google Fonts: node add_font.mjs <projectDir> "Family Name" [--weights 400,700] [--token --name]');
  process.exit(0);
}

const dir = path.resolve(opt._[0]);
if (!fs.existsSync(path.join(dir, 'index.html'))) { console.error(`no index.html in ${dir}`); process.exit(2); }
const names = opt._.slice(1);
if (!names.length) { console.error('usage: node add_font.mjs <projectDir> <catalogue id | "Google Fonts family"> …   (see --list)'); process.exit(2); }
const weights = typeof opt.weights === 'string' ? opt.weights.split(',').map(Number).filter(Boolean) : null;
// a bare --token means the catalogue's own token (--serif, --display …); a Google Fonts family needs a name
if (opt.token === true && names.some((n) => !catalog.fonts.some((f) => f.id === n || f.family.toLowerCase() === n.toLowerCase()))) { console.error(`✖ ${TOKEN_USAGE}`); process.exit(2); }

// families whose @font-face live elsewhere (the core fonts: css/player.css, fonts/noto-sans-kr/…) are not written here
const declaredElsewhere = new Set(fontFaces(dir).filter((f) => f.css !== 'css/fonts.css').map((f) => f.family.toLowerCase()));
const fontsCss = path.join(dir, 'css', 'fonts.css');
let css = fs.existsSync(fontsCss) ? fs.readFileSync(fontsCss, 'utf8')
  : '/* fonts.css — @font-face for fonts added with scripts/add_font.mjs (catalogue or Google Fonts OFL). Generated; don\'t add other fonts by hand. */\n';
let styleCss = fs.readFileSync(path.join(dir, 'css', 'style.css'), 'utf8');
const addToken = (token, stack, family, why) => {
  if (!new RegExp(`${token}\\s*:`).test(styleCss)) {
    styleCss = styleCss.replace(/:root\s*{/, (m) => `${m}\n  ${token}: ${stack};   /* ${family} — ${why} (add_font.mjs) */`);
  } else if (!styleCss.includes(stack)) console.log(`  note: ${token} already exists in style.css — to use ${family} set it to: ${stack}`);
};
// a family's part of css/fonts.css — its header comment and every @font-face of the family — rewritten from its
// catalogue / fonts.lock.json entry on every run, so a re-install (other --weights) never leaves a stale rule behind
const esc = (x) => String(x).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const setFamilyCss = (id, family, header, block) => {
  css = css.replace(new RegExp(`\\n?/\\* ${esc(id)} — [^\\n]*\\*/[ \\t]*(?=\\n|$)`, 'g'), '')
    .replace(new RegExp(`@font-face\\s*\\{[^}]*font-family:\\s*['"]?${esc(family)}['"]?\\s*;[^}]*\\}\\n?`, 'gi'), '')
    .replace(/\n{3,}/g, '\n\n').replace(/\s*$/, '\n');
  css += `\n/* ${id} — ${header} */\n${block}`;
};
const generic = (cat) => (/serif/i.test(cat) && !/sans/i.test(cat) ? 'serif' : /mono/i.test(cat) ? 'monospace' : /hand/i.test(cat) ? 'cursive' : 'sans-serif');

for (const name of names) {
  const font = catalog.fonts.find((f) => f.id === name) || catalog.fonts.find((f) => f.family.toLowerCase() === name.toLowerCase());
  try {
    if (font) {
      await installFonts(dir, [font]);
      if (!declaredElsewhere.has(font.family.toLowerCase())) setFamilyCss(font.id, font.family, font.role, font.files.filter((f) => !f.dest.endsWith('.css')).map((f) => faceCss(font, f)).join(''));
      addToken(typeof opt.token === 'string' ? opt.token : font.token, font.stack, font.family, font.license);
      console.log(`✓ ${font.family} (${font.id}, catalogue) → fonts/${font.id}/ · ${font.license} · use var(${typeof opt.token === 'string' ? opt.token : font.token})`);
    } else {
      const e = await installGoogleFont(dir, name, { weights });
      if (!declaredElsewhere.has(e.family.toLowerCase())) setFamilyCss(e.id, e.family, `Google Fonts ${e.path} @ ${e.commit.slice(0, 12)} · ${e.category}`, e.files.map((f) => faceCss(e, f)).join(''));
      const stack = `'${e.family}', 'Pretendard', ${generic(e.category)}`;
      if (typeof opt.token === 'string') addToken(opt.token, stack, e.family, e.license);
      const axes = e.axes.length ? ` · axes ${e.axes.map((a) => `${a.tag} ${a.min}–${a.max}`).join(', ')}` : '';
      const ko = e.subsets.includes('korean') ? ' · Hangul' : ' · no Hangul (Pretendard draws Korean)';
      const mb = (e.files.reduce((s, f) => s + f.bytes, 0) / 1048576).toFixed(1);
      console.log(`✓ ${e.family} (Google Fonts ${e.path}) → fonts/${e.id}/ · ${e.license} · ${e.files.length} file(s), ${mb} MB${axes}${ko}`);
      console.log(`  stack: ${stack}${typeof opt.token === 'string' ? `  → var(${opt.token})` : ''}`);
    }
  } catch (err) {
    console.error(`✖ ${err.message}`);
    process.exit(1);
  }
}
fs.writeFileSync(fontsCss, css);
fs.writeFileSync(path.join(dir, 'css', 'style.css'), styleCss);

// link css/fonts.css before style.css so tokens can use the families
const indexPath = path.join(dir, 'index.html');
let html = fs.readFileSync(indexPath, 'utf8');
if (!/href=["']css\/fonts\.css["']/.test(html)) {
  html = html.replace(/(\s*)<link rel="stylesheet" href="css\/style\.css">/, '$1<link rel="stylesheet" href="css/fonts.css">$1<link rel="stylesheet" href="css/style.css">');
  fs.writeFileSync(indexPath, html);
}
console.log('\nNext: use the family in style.css, then node check_fonts.mjs <projectDir> to prove every glyph is covered.');
