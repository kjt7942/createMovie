/**
 * fonts.mjs — the skill's font catalogue (assets/fonts/catalog.json) and the checks built on it.
 *
 * Policy: text fonts are SIL Open Font License 1.1 ONLY. A video may only use the catalogued fonts — all
 * SIL OFL 1.1 — downloaded from their official sources and copied unmodified (sha256 in the catalogue) with
 * their OFL 1.1 licence files. The skill itself ships no font files (lib/fontfetch.mjs downloads them).
 * Used by check.mjs (static), check_fonts.mjs and thumbnail.mjs (static + real Chromium), add_font.mjs and
 * new_project.mjs.
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { isOfl11, REQUIRED_LICENSE } from './fontfetch.mjs';
import { readLock } from './gfonts.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
export const SKILL_DIR = path.resolve(here, '..', '..');
export const CATALOG_PATH = path.join(SKILL_DIR, 'assets', 'fonts', 'catalog.json');
export const GENERIC = /^(serif|sans-serif|monospace|cursive|fantasy|math|emoji|fangsong|inherit|initial|unset|revert|revert-layer)$/i;
// the generic families themselves: whatever the machine maps them to draws the text (a system font)
export const GENERIC_FAMILY = /^(serif|sans-serif|monospace|cursive|fantasy|math|emoji|fangsong|system-ui|ui-serif|ui-sans-serif|ui-monospace|ui-rounded)$/i;
// `font: menu` etc. — the shorthand set to the operating system's own UI font
const SYSTEM_FONT_KEYWORD = /^(caption|icon|menu|message-box|small-caption|status-bar)$/i;

export function loadCatalog() {
  return JSON.parse(fs.readFileSync(CATALOG_PATH, 'utf8'));
}
const shaCache = new Map();
export const sha256 = (p) => {
  const st = fs.statSync(p);
  const k = `${p}\0${st.size}\0${st.mtimeMs}`;
  if (!shaCache.has(k)) shaCache.set(k, crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'));
  return shaCache.get(k);
};
// comments out, every other character (and so every line number and offset) kept
const blank = (m) => m.replace(/[^\n]/g, ' ');
const strip = (t) => t.replace(/\/\*[\s\S]*?\*\//g, blank);
const stripJs = (t) => t.replace(/\/\*[\s\S]*?\*\//g, blank).replace(/(^|[^:'"`\\])\/\/.*$/gm, (m, a) => a + blank(m.slice(a.length)));
const stripHtml = (t) => t.replace(/<!--[\s\S]*?-->/g, blank);
const lineAt = (text, i) => text.slice(0, i).split('\n').length;

/** every .css in <dir>/css and <dir>/fonts (recursively) */
export function projectCss(dir) {
  const out = [];
  const walk = (rel) => {
    const abs = path.join(dir, rel);
    if (!fs.existsSync(abs)) return;
    for (const e of fs.readdirSync(abs, { withFileTypes: true })) {
      const r = path.posix.join(rel, e.name);
      if (e.isDirectory()) walk(r); else if (e.name.endsWith('.css')) out.push(r);
    }
  };
  walk('css'); walk('fonts');
  return out;
}

/**
 * the project's own files whose name matches `re`, recursively (posix paths relative to dir): never .git,
 * node_modules, .snapshots or .tts-cache; at the project root also not `skipRoot` (default: vendor/ and fonts/ — the
 * skill's verified copies).
 */
export function projectFiles(dir, re, { skipRoot = ['vendor', 'fonts'] } = {}) {
  const SKIP = new Set(['.git', 'node_modules', '.snapshots', '.tts-cache']);
  const out = [];
  const walk = (rel) => {
    let ents;
    try { ents = fs.readdirSync(path.join(dir, rel), { withFileTypes: true }); } catch { return; }
    for (const e of ents) {
      const r = rel ? `${rel}/${e.name}` : e.name;
      if (e.isDirectory()) { if (!SKIP.has(e.name) && !(rel === '' && skipRoot.includes(e.name))) walk(r); } else if (re.test(e.name)) out.push(r);
    }
  };
  walk('');
  return out.sort();
}

/**
 * the font format of a file's first bytes (WOFF, WOFF2, OpenType/TrueType, a collection) or null — font files are
 * recognised by content, not by their extension (a renamed .bin is still a font).
 */
export function fontSignature(b) {
  if (!b || b.length < 16) return null;
  const tag = b.toString('latin1', 0, 4);
  if (tag === 'wOFF' || tag === 'wOF2') return tag;
  if (tag === 'ttcf') return [1, 2].includes(b.readUInt16BE(4)) && b.readUInt16BE(6) === 0 ? tag : null;
  if (tag === 'OTTO' || tag === 'true' || tag === 'typ1' || b.readUInt32BE(0) === 0x00010000) {
    const n = b.readUInt16BE(4);
    return n >= 1 && n <= 512 && /^[\x20-\x7e]{4}$/.test(b.toString('latin1', 12, 16)) ? 'sfnt' : null;
  }
  return null;
}
function headOf(file) {
  const b = Buffer.alloc(16);
  let n = 0;
  try { const fd = fs.openSync(file, 'r'); n = fs.readSync(fd, b, 0, 16, 0); fs.closeSync(fd); } catch { return null; }
  return b.subarray(0, n);
}
// base64 of a font file's first bytes (wOF2, wOFF, OTTO, 00010000, true, ttcf) followed by a long run of base64
const B64_FONT = /(?:d09GMg|d09GRg|T1RUTw|AAEAAA|dHJ1ZQ|dHRjZg)[A-Za-z0-9+/]{1000,}/;

/**
 * every font this project may use: the skill's catalogue (pinned, recommended) + the families installed from Google
 * Fonts' ofl/ directory, recorded with their commit and sha256 in fonts/fonts.lock.json (add_font.mjs).
 * Lock entries that are not ofl/ + SIL OFL 1.1 are returned in `bad`.
 */
export function allowedFonts(dir, catalog = loadCatalog()) {
  const fonts = catalog.fonts.filter((f) => f.license === REQUIRED_LICENSE);
  const bad = [];
  let lock = { fonts: [] };
  try { lock = readLock(dir); } catch (e) { bad.push(`fonts/fonts.lock.json is not valid JSON (${e.message}) — reinstall the fonts with add_font.mjs`); }
  for (const f of lock.fonts || []) {
    if (f.source !== 'google/fonts' || !String(f.path || '').startsWith('ofl/') || f.license !== REQUIRED_LICENSE || !/^[0-9a-f]{40}$/.test(f.commit || '')) {
      bad.push(`fonts.lock.json: "${f.family}" is not an SIL OFL 1.1 family from google/fonts ofl/ at a pinned commit — remove it`);
      continue;
    }
    if (fonts.some((c) => c.family.toLowerCase() === f.family.toLowerCase())) continue;   // the catalogue entry wins
    fonts.push(Object.assign({ fromLock: true }, f));
  }
  return { fonts, bad };
}

/** the sources of one @font-face `src` (or a FontFace source string): [{ url } | { local }] */
export function parseFontSrc(src) {
  const out = [];
  for (const m of String(src || '').matchAll(/(url|local)\(\s*(?:"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'|([^)]*?))\s*\)/gi)) {
    const v = (m[2] ?? m[3] ?? m[4] ?? '').trim();
    out.push(m[1].toLowerCase() === 'local' ? { local: v } : { url: v });
  }
  return out;
}

/** @font-face rules in the project (css/, fonts/, <style> in index.html): [{ css, family, url, remote, data, local, file }] */
export function fontFaces(dir) {
  const faces = [];
  const sources = projectCss(dir).map((css) => [css, path.dirname(path.join(dir, css)), strip(fs.readFileSync(path.join(dir, css), 'utf8'))]);
  const html = path.join(dir, 'index.html');
  if (fs.existsSync(html)) for (const m of stripHtml(fs.readFileSync(html, 'utf8')).matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)) sources.push(['index.html', dir, strip(m[1])]);
  for (const [css, base, text] of sources) {
    for (const block of text.match(/@font-face\s*{[^}]*}/g) || []) {
      const family = ((block.match(/font-family\s*:\s*['"]?([^;'"]+)['"]?/) || [])[1] || '').trim();
      const src = parseFontSrc((block.match(/(?:^|[;{\s])src\s*:\s*([^;}]+)/) || [])[1] || '');
      for (const s of src.length ? src : [{ url: null }]) {
        if (s.local != null) { faces.push({ css, family, local: s.local }); continue; }
        const url = s.url;
        const remote = !!url && /^(https?:)?\/\//i.test(url);
        const data = !!url && /^data:/i.test(url);
        let file = null;
        if (url && !remote && !data) { try { file = path.resolve(base, decodeURIComponent(url.split(/[?#]/)[0])); } catch { file = path.resolve(base, url.split(/[?#]/)[0]); } }
        faces.push({ css, family, url, remote, data, file });
      }
    }
  }
  return faces;
}

const inside = (dir, file) => { const r = path.relative(dir, file); return !!r && !r.startsWith('..') && !path.isAbsolute(r); };

/**
 * Audit the project's fonts against the catalogue.
 * Returns { errors, warnings, families: Set<lowercase family declared & allowed>, used: Set<catalog id> }.
 */
export function auditFonts(dir, catalog = loadCatalog()) {
  const errors = [];
  const warnings = [];
  for (const f of catalog.fonts) {
    if (f.license !== REQUIRED_LICENSE) errors.push(`catalogue: ${f.id} is licensed "${f.license}" — only ${REQUIRED_LICENSE} fonts are allowed; remove it from assets/fonts/catalog.json`);
  }
  const { fonts: ALLOWED, bad } = allowedFonts(dir, catalog);
  errors.push(...bad);
  const byFamily = new Map(ALLOWED.map((f) => [f.family.toLowerCase(), f]));
  const hashes = new Map();
  for (const f of ALLOWED) for (const file of f.files) hashes.set(file.sha256, f.id);
  const families = new Set();
  const used = new Set();
  for (const face of fontFaces(dir)) {
    const cat = byFamily.get(face.family.toLowerCase());
    if (!cat) { errors.push(`${face.css}: @font-face "${face.family}" is neither a catalogue font nor a Google Fonts OFL family in fonts/fonts.lock.json — install it with add_font.mjs (catalogue id or Google Fonts family name)`); continue; }
    families.add(face.family.toLowerCase());
    used.add(cat.id);
    if (face.local != null) { errors.push(`${face.css}: @font-face "${face.family}" uses local("${face.local}") — that draws with a font installed on this machine (a system font), not the project's file: use url() of the installed file (add_font.mjs)`); continue; }
    if (!face.url) continue;
    if (face.remote) { errors.push(`${face.css}: "${face.family}" loads a remote font (${face.url}) — install it from the catalogue (add_font.mjs)`); continue; }
    if (face.data) { errors.push(`${face.css}: "${face.family}" embeds font data (a data: URL) — use the installed, unmodified file in fonts/ (add_font.mjs)`); continue; }
    if (!inside(dir, face.file)) { errors.push(`${face.css}: "${face.family}" loads ${face.url} from outside the project — the project must contain its fonts (add_font.mjs ${dir} ${cat.id})`); continue; }
    if (!fs.existsSync(face.file)) { errors.push(`${face.css}: "${face.family}" → missing ${path.relative(dir, face.file)} (add_font.mjs ${dir} ${cat.id})`); continue; }
    const owner = hashes.get(sha256(face.file));
    if (owner !== cat.id) errors.push(`${path.relative(dir, face.file)}: not the ${cat.fromLock ? 'pinned (fonts.lock.json)' : "catalogue's"} unmodified file for "${face.family}" (sha256 mismatch) — reinstall with add_font.mjs`);
  }
  for (const id of used) {
    const cat = ALLOWED.find((f) => f.id === id);
    const lic = path.join(dir, cat.licenseFile.dest);
    if (!fs.existsSync(lic)) errors.push(`${cat.licenseFile.dest}: licence file for ${cat.family} is missing (add_font.mjs ${dir} ${id})`);
    else if (!isOfl11(fs.readFileSync(lic, 'utf8'))) errors.push(`${cat.licenseFile.dest}: not the SIL Open Font License 1.1 text — only ${REQUIRED_LICENSE} fonts may be used (reinstall with add_font.mjs)`);
  }
  // no font file in the project may be anything but an unmodified catalogue / locked Google Fonts OFL file — a font is
  // recognised by its extension or by its first bytes (data/glyphdata.bin holding a TrueType font is a font file)
  const known = new Set(ALLOWED.flatMap((f) => f.files.map((x) => x.sha256)));
  const FONT_EXT = /\.(ttf|otf|woff2?|ttc|otc|eot|pfb|pfa|dfont)$/i;
  for (const r of projectFiles(dir, /./, { skipRoot: [] })) {
    const abs = path.join(dir, r);
    if (!FONT_EXT.test(r) && !fontSignature(headOf(abs))) continue;
    if (!known.has(sha256(abs))) errors.push(`${r}: font file that is neither an unmodified catalogue font nor a pinned Google Fonts OFL file (fonts.lock.json) — only ${REQUIRED_LICENSE} fonts installed with add_font.mjs may be in the project; delete it`);
  }
  // nor font data pasted into code (base64 of a font file, e.g. for new FontFace(…) or a data: URL)
  for (const r of projectFiles(dir, /\.(m?js|css|html?|json|svg)$/i)) {
    const abs = path.join(dir, r);
    if (fs.statSync(abs).size > 64e6) continue;
    if (B64_FONT.test(fs.readFileSync(abs, 'utf8'))) errors.push(`${r}: holds font data encoded in the file (base64 of a font) — fonts are loaded only from the installed, unmodified files in fonts/ (add_font.mjs); an embedded copy is neither verified nor licensed`);
  }
  return { errors, warnings, families, used };
}

// ---------- font names: every place a family can be named ----------

/** split at top-level commas (not inside quotes or parentheses) */
function splitTop(s) {
  const out = [];
  let depth = 0, q = null, cur = '';
  for (const ch of s) {
    if (q) { if (ch === q) q = null; cur += ch; continue; }
    if (ch === '"' || ch === "'") q = ch;
    else if (ch === '(') depth++;
    else if (ch === ')') depth = Math.max(0, depth - 1);
    else if (ch === ',' && !depth) { out.push(cur); cur = ''; continue; }
    cur += ch;
  }
  out.push(cur);
  return out;
}

/** a font-family list → [{ name, generic, quoted } | { varName, fallback: [...] } | { unknown }] */
export function parseStack(value) {
  const out = [];
  for (let item of splitTop(String(value).replace(/!\s*important\s*$/i, ''))) {
    item = item.trim();
    if (!item) continue;
    const v = item.match(/^var\(\s*(--[\w-]+)\s*(?:,([\s\S]*))?\)$/);
    if (v) { out.push({ varName: v[1], fallback: v[2] != null ? parseStack(v[2]) : [] }); continue; }
    if (/\w\(/.test(item)) { out.push({ unknown: true }); continue; }   // var() among other words, env(), attr() …
    const quoted = /^(['"])[\s\S]*\1$/.test(item);
    const name = (quoted ? item.slice(1, -1) : item).replace(/\s+/g, ' ').trim();
    if (name) out.push({ name, quoted, generic: !quoted && GENERIC.test(name) });
  }
  return out;
}

// the size in a `font` shorthand (the families follow it): 48px, 4vw, 1.2em/1.4, large, calc(…), var(--size)
const SIZE = /(?:^|\s)(?:-?[\d.]+(?:px|r?em|%|pt|pc|[sld]?v(?:w|h|i|b|min|max)|cq(?:w|h|i|b|min|max)|ch|ex|r?cap|r?ic|r?lh|q|cm|mm|in)|xxx-large|xx-large|x-large|xx-small|x-small|small|medium|large|smaller|larger|(?:calc|clamp|min|max|var)\((?:[^()]|\([^()]*\))*\))(?:\s*\/\s*[^\s,'"]+)?\s+(?=\S)/i;
/** `font` shorthand → { families } (the list after the size), { system: keyword }, or null (no family part) */
export function shorthandFamilies(value) {
  const s = String(value).trim().replace(/!\s*important\s*$/i, '');
  if (SYSTEM_FONT_KEYWORD.test(s)) return { system: s };
  const m = SIZE.exec(s);
  return m ? { families: s.slice(m.index + m[0].length) } : null;
}
// a custom property's value as a family list (null: a size, a number, a colour …); a shorthand gives its families
function stackOf(value) {
  const v = String(value).trim();
  if (!v) return null;
  if (/^(-?[\d.]|#)/.test(v) || (/^[\w-]+\(/.test(v) && !/^var\(/.test(v))) { const sh = shorthandFamilies(v); return sh && sh.families != null ? sh.families : null; }
  return v;
}
// custom properties that hold a font stack by name (the catalogue's tokens and anything *font*)
const FONT_PROP = /^--(?:[\w-]*font[\w-]*|mono|serif|display|hand)$/i;

const scanCache = new Map();
/**
 * every place the project names a font, statically: CSS files (css/), <style> blocks, style="…" attributes and SVG
 * font-family="…" attributes in the project's HTML pages, inline <script>s and js/**: fontFamily, ctx.font / style.font,
 * setAttribute('font-family', …), style.setProperty('font…', …) and CSS or markup inside JS strings (cssText,
 * innerHTML). Returns { decls: [where, families, dynamic], props: Map<--name, [where, value]>, system: [where] }.
 */
function scanFonts(dir) {
  if (scanCache.has(dir)) return scanCache.get(dir);
  const decls = [], system = [];
  const props = new Map();
  const STR = /(['"])((?:\\.|(?!\1)[^\\\n])*)\1|(`)((?:\\[\s\S]|[^\\`])*)`/g;   // '…' "…" on one line, `…` across lines
  const css = (text, where, base = 0, full = text) => {
    text = text.replace(/@font-face\s*{[^}]*}/g, blank);
    for (const m of text.matchAll(/(?:^|[;{\s"'`])(font-family|font|--[\w-]+)\s*:\s*([^;{}]+)/gi)) {
      const at = `${where}:${lineAt(full, base + m.index + m[0].indexOf(m[1]))}`;
      const prop = m[1].toLowerCase(), v = m[2].trim();
      if (prop.startsWith('--')) {
        if (!props.has(m[1])) props.set(m[1], []);
        props.get(m[1]).push([at, v]);
        if (FONT_PROP.test(m[1])) { const st = stackOf(v); if (st != null) decls.push([at, st, false]); }
      } else if (prop === 'font-family') decls.push([at, v, false]);
      else {
        const sh = shorthandFamilies(v);
        if (sh && sh.system) system.push(`${at}: font: ${sh.system}`);
        else if (sh) decls.push([at, sh.families, false]);
      }
    }
  };
  const markup = (text, where, base = 0, full = text) => {
    for (const m of text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)) css(strip(m[1]), where, base + m.index + m[0].indexOf(m[1]), full);
    for (const m of text.matchAll(/\sstyle\s*=\s*(?:"([^"]*)"|'([^']*)')/gi)) css(m[1] ?? m[2], where, base + m.index, full);
    for (const m of text.matchAll(/\sfont-family\s*=\s*(?:"([^"]*)"|'([^']*)')/gi)) decls.push([`${where}:${lineAt(full, base + m.index + 1)}`, m[1] ?? m[2], false]);
  };
  const js = (text, where, base = 0, full = text) => {
    const at = (i) => `${where}:${lineAt(full, base + i)}`;
    const val = (q, s) => ({ v: q === '`' ? s.replace(/\$\{[^}]*\}/g, ' ') : s, dynamic: q === '`' && /\$\{/.test(s) });
    for (const m of text.matchAll(/(fontFamily|\.font)\s*[:=]\s*(['"`])((?:\\[\s\S]|(?!\2)[^\\])*)\2/g)) {
      const { v, dynamic } = val(m[2], m[3]);
      if (m[1] === 'fontFamily') { decls.push([at(m.index), v, dynamic]); continue; }
      const sh = shorthandFamilies(v);
      if (sh && sh.system) system.push(`${at(m.index)}: font = '${sh.system}'`);
      else decls.push([at(m.index), sh ? sh.families : v.replace(/^(?:italic|oblique|normal|bold|\d{3}|\s)+/i, ''), dynamic]);
    }
    for (const m of text.matchAll(/\.(?:setAttribute|setProperty)\(\s*(['"])(font-family|font|--[\w-]+)\1\s*,\s*(['"`])((?:\\[\s\S]|(?!\3)[^\\])*)\3/g)) {
      const { v, dynamic } = val(m[3], m[4]);
      if (m[2].startsWith('--')) { if (FONT_PROP.test(m[2])) { const st = stackOf(v); if (st != null) decls.push([at(m.index), st, dynamic]); } continue; }
      const sh = m[2] === 'font' ? shorthandFamilies(v) : { families: v };
      if (sh && sh.system) system.push(`${at(m.index)}: font: ${sh.system}`);
      else if (sh) decls.push([at(m.index), sh.families, dynamic]);
    }
    // CSS or markup written inside a string (el.style.cssText = 'font-family: …', innerHTML = '<text font-family="…">')
    for (const m of text.matchAll(STR)) {
      const body = m[2] ?? m[4];
      if (!/font(?:-family)?\s*[:=]/i.test(body)) continue;
      const s = m[3] ? body.replace(/\$\{[^}]*\}/g, (x) => ' '.repeat(x.length)) : body;
      const off = base + m.index + 1;
      markup(s, where, off, full);
      if (!/<[a-z]/i.test(s)) css(s, where, off, full);
    }
  };
  for (const f of projectCss(dir).filter((c) => c.startsWith('css/'))) css(strip(fs.readFileSync(path.join(dir, f), 'utf8')), f);
  for (const f of projectFiles(dir, /\.html?$/i)) {
    const text = stripHtml(fs.readFileSync(path.join(dir, f), 'utf8'));
    markup(text, f);
    for (const m of text.matchAll(/<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)) js(stripJs(m[1]), f, m.index + m[0].indexOf(m[1]), text);
  }
  for (const f of projectFiles(dir, /\.m?js$/i).filter((r) => r.startsWith('js/') && !/^js\/(player|cues|glyphs|sync)\.js$/.test(r))) {
    js(stripJs(fs.readFileSync(path.join(dir, f), 'utf8')), f);
  }
  const out = { decls, props, system };
  scanCache.set(dir, out);
  return out;
}

/** font names in stacks (CSS declarations, shorthand, inline styles, SVG attributes, JS, var() fallbacks and the custom
 *  properties those var()s read) that aren't declared catalogue families */
export function stackProblems(dir, families) {
  const { decls, props, system } = scanFonts(dir);
  const bad = new Set();
  const readVars = new Set();
  const visit = (where, items) => {
    for (const it of items) {
      if (it.unknown) continue;
      if (it.varName) {
        visit(where, it.fallback);
        if (!readVars.has(it.varName)) {
          readVars.add(it.varName);
          for (const [w, v] of props.get(it.varName) || []) { const st = stackOf(v); if (st != null) visit(w, parseStack(st)); }
        }
        continue;
      }
      if (it.generic || families.has(it.name.toLowerCase())) continue;
      bad.add(`${where}: "${it.name}"`);
    }
  };
  for (const [where, value] of decls) visit(where, parseStack(value));
  for (const s of system) bad.add(`${s} (the operating system's UI font)`);
  return [...bad];
}

/** font declarations that name no font at all — only generic families (sans-serif, monospace …) or a reset to the
 *  browser default (initial, revert): the text is then drawn by whatever system font the machine has */
export function genericOnlyStacks(dir) {
  const out = [];
  for (const [where, value, dynamic] of scanFonts(dir).decls) {
    if (dynamic) continue;                                               // a template string: its family is a variable
    const items = parseStack(value);
    if (!items.length || items.some((x) => x.varName || x.unknown || /^(inherit|unset)$/i.test(x.name))) continue;   // var(--font), or inherited
    if (items.every((x) => x.generic)) out.push(`${where}: ${value.trim()}`);
  }
  return [...new Set(out)];
}

/** stacks whose FIRST family is a generic one (sans-serif, 'Pretendard' / system-ui, …): the generic always matches, so
 *  the installed font after it never draws anything */
export function genericFirstStacks(dir) {
  const out = [];
  for (const [where, value] of scanFonts(dir).decls) {
    const items = parseStack(value);
    if (items.length > 1 && items[0].name && !items[0].quoted && GENERIC_FAMILY.test(items[0].name)) out.push(`${where}: ${value.trim()}`);
  }
  return [...new Set(out)];
}

/** a CSS @font-face block for one catalogue file, relative to css/ */
export function faceCss(font, file) {
  const ext = path.extname(file.dest).slice(1).toLowerCase();
  const format = { woff2: 'woff2', woff: 'woff', ttf: 'truetype', otf: 'opentype' }[ext] || ext;
  return `@font-face {\n  font-family: '${font.family}';   /* ${font.license} · ${font.copyright} · ${font.licenseFile.dest} */\n` +
    `  src: url('../${file.dest}') format('${format}');\n  font-weight: ${file.weight || 400};\n  font-style: ${file.style || 'normal'};\n  font-display: block;\n}\n`;
}

// ---------- runtime (a real browser page): which fonts actually drew the text, and where web fonts came from ----------

/**
 * page.addInitScript(fontHooks) — runs before the page's own scripts: records every FontFace a script constructs (its
 * family and source; binary sources are hashed, sha256) in window.__fontFaces, and every text drawn on a 2D canvas
 * with the font it was drawn in (window.__canvasText) — the DOM check can't see inside a canvas.
 */
export function fontHooks() {
  const faces = [];
  window.__fontFaces = faces;
  const Native = window.FontFace;
  if (Native) {
    const hex = (d) => [...new Uint8Array(d)].map((x) => x.toString(16).padStart(2, '0')).join('');
    window.FontFace = class FontFace extends Native {
      constructor(family, source, descriptors) {
        super(family, source, descriptors);
        const e = { family: String(family), base: document.baseURI };
        if (typeof source === 'string') e.src = source;
        else {
          let u8 = null;
          try {
            u8 = source instanceof ArrayBuffer ? new Uint8Array(source.slice(0))
              : ArrayBuffer.isView(source) ? new Uint8Array(source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength)) : null;
          } catch (err) { u8 = null; }
          e.bytes = u8 ? u8.length : 0;
          e.hash = u8 && window.crypto && crypto.subtle ? crypto.subtle.digest('SHA-256', u8).then(hex, () => null) : null;
        }
        faces.push(e);
      }
    };
  }
  const seen = new Map();
  window.__canvasText = seen;
  for (const C of [window.CanvasRenderingContext2D, window.OffscreenCanvasRenderingContext2D]) {
    if (!C) continue;
    for (const m of ['fillText', 'strokeText']) {
      const orig = C.prototype[m];
      C.prototype[m] = function (text, ...rest) {
        const f = String(this.font), k = f + '\u0000' + text;
        if (seen.size < 20000 && !seen.has(k)) seen.set(k, { font: f, text: String(text) });
        return orig.call(this, text, ...rest);
      };
    }
  }
}

/** every web font source the page has: @font-face rules of every stylesheet (linked, @import-ed, <style>, constructed)
 *  and every FontFace a script made (needs fontHooks) */
export function webFontSources(page) {
  return page.evaluate(async () => {
    const out = [];
    const walk = (list, base, where) => {
      for (const r of list) {
        if (r.type === 5) out.push({ kind: 'css', family: r.style.getPropertyValue('font-family'), src: r.style.getPropertyValue('src'), base, where });
        else if (r.type === 3) {
          const s = r.styleSheet;
          if (!s) { out.push({ kind: 'css', unreadable: r.href, where }); continue; }
          try { walk(s.cssRules, s.href || base, s.href || where); } catch (e) { out.push({ kind: 'sheet', href: s.href || r.href, where }); }
        } else if (r.cssRules) walk(r.cssRules, base, where);
      }
    };
    for (const s of [...document.styleSheets, ...(document.adoptedStyleSheets || [])]) {
      const where = s.href || (s.ownerNode ? `a <${s.ownerNode.localName}> in the page` : 'a stylesheet made by a script');
      // a file:// stylesheet's rules can't be read from the page without --allow-file-access-from-files: read the file
      try { walk(s.cssRules, s.href || document.baseURI, where); } catch (e) { out.push({ kind: 'sheet', href: s.href, where }); }
    }
    for (const f of window.__fontFaces || []) out.push({ kind: 'js', family: f.family, src: f.src, base: f.base, bytes: f.bytes, hash: f.hash ? await f.hash : null });
    return out;
  });
}

/**
 * every web font must come from an installed, unmodified file of its own family (catalogue or fonts.lock.json) inside
 * the project — not local() (a system font), a remote URL, a data: URL, or another file. Returns { errors, families }.
 */
export function verifyWebFonts(dir, sources, catalog = loadCatalog()) {
  const { fonts } = allowedFonts(dir, catalog);
  const byFamily = new Map(fonts.map((f) => [f.family.toLowerCase(), f]));
  const errors = [], families = new Set();
  const short = (u) => { try { const p = fileURLToPath(u); return inside(dir, p) ? path.relative(dir, p) : p; } catch { return String(u).slice(0, 120); } };
  // stylesheets the page could not read itself: their @font-face rules (and @import-ed sheets) from the files
  const list = [];
  const seenSheets = new Set();
  const fromSheet = (href, where) => {
    if (!href || seenSheets.has(href)) { if (!href) list.push({ unreadable: null, where }); return; }
    seenSheets.add(href);
    let file;
    try { file = new URL(href).protocol === 'file:' ? fileURLToPath(href) : null; } catch { file = null; }
    if (!file) { list.push({ unreadable: href, where }); return; }
    if (!fs.existsSync(file)) return;                     // a missing stylesheet declares nothing
    const text = strip(fs.readFileSync(file, 'utf8'));
    for (const block of text.match(/@font-face\s*{[^}]*}/g) || []) {
      list.push({ kind: 'css', family: ((block.match(/font-family\s*:\s*([^;}]+)/) || [])[1] || '').trim(), src: (block.match(/(?:^|[;{\s])src\s*:\s*([^;}]+)/) || [])[1] || '', base: href, where: href });
    }
    for (const m of text.matchAll(/@import\s+(?:url\(\s*)?(?:"([^"]*)"|'([^']*)'|([^\s;)'"]+))/g)) {
      let u;
      try { u = new URL(m[1] ?? m[2] ?? m[3], href).href; } catch { continue; }
      fromSheet(u, href);
    }
  };
  for (const s of sources) if (s.kind === 'sheet') fromSheet(s.href, s.where); else list.push(s);
  for (const s of list) {
    if (s.unreadable !== undefined) { errors.push(`stylesheet ${s.unreadable ? short(s.unreadable) : '(unknown)'} (from ${short(s.where)}) could not be read — remote or blocked; the project must contain its CSS and fonts`); continue; }
    const fam = String(s.family || '').trim().replace(/^(['"])([\s\S]*)\1$/, '$2');
    const cat = byFamily.get(fam.toLowerCase());
    const what = s.kind === 'js' ? `FontFace("${fam}") made by a script` : `@font-face "${fam}" in ${short(s.where)}`;
    const hashes = new Set(cat ? cat.files.map((x) => x.sha256) : []);
    const fix = 'only fonts installed with add_font.mjs (catalogue or Google Fonts ofl/, unmodified) may draw text';
    if (s.src == null) {
      if (!s.hash) errors.push(`${what}: font data from memory (${s.bytes || 0} bytes) that could not be verified — ${fix}`);
      else if (!hashes.has(s.hash)) errors.push(`${what}: font data from memory (${s.bytes} bytes, sha256 ${s.hash.slice(0, 12)}…) is not ${cat ? `an installed file of ${cat.family}` : 'an installed font'} — ${fix}`);
      else families.add(cat.family);
      continue;
    }
    const items = parseFontSrc(s.src);
    if (!items.length) errors.push(`${what}: no url() source — ${fix}`);
    for (const it of items) {
      if (it.local != null) { errors.push(`${what}: local("${it.local}") draws with a font installed on this machine (a system font) — use url() of the installed file`); continue; }
      let u;
      try { u = new URL(it.url, s.base); } catch { errors.push(`${what}: unreadable source url(${it.url})`); continue; }
      if (u.protocol === 'data:') { errors.push(`${what}: embedded font data (data: URL) — ${fix}`); continue; }
      if (u.protocol !== 'file:') { errors.push(`${what}: remote font ${u.href.slice(0, 120)} — the project must contain its fonts; ${fix}`); continue; }
      const file = fileURLToPath(u);
      if (!inside(dir, file)) { errors.push(`${what}: ${file} is outside the project — the project must contain its fonts; ${fix}`); continue; }
      const rel = path.relative(dir, file);
      if (!fs.existsSync(file)) { errors.push(`${what}: ${rel} does not exist`); continue; }
      if (!cat) errors.push(`${what}: "${fam}" is not an installed family (catalogue or fonts/fonts.lock.json) — ${rel}; ${fix}`);
      else if (!hashes.has(sha256(file))) errors.push(`${what}: ${rel} is not an installed, unmodified file of ${cat.family} (its sha256 is not in the ${cat.fromLock ? 'fonts.lock.json pins' : 'catalogue'}) — ${fix}`);
      else families.add(cat.family);
    }
  }
  return { errors: [...new Set(errors)], families };
}

// runs in the page: the visible elements under `scope` that show text — own text nodes, ::before/::after/::marker
// content, form control values — and whose (text, font settings) were not checked before; their texts in __fcTexts
async function fontCandidates(scope) {
  const root = document.querySelector(scope) || document.body;
  void root.offsetWidth;                                   // lay out first: that starts the web font loads the frame needs
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  void root.offsetWidth;
  const seen = window.__fcSeen || (window.__fcSeen = new Set());
  const els = [], texts = [];
  const pseudoOf = (el, p) => {
    const ps = getComputedStyle(el, p);
    const c = ps.content;
    if (!c || c === 'none' || c === 'normal' || c === '""' || c === "''") return '';
    return `${p} ${c} ${ps.fontFamily} ${ps.fontWeight} ${ps.fontStyle} ${ps.fontStretch} ${ps.fontVariationSettings}`;
  };
  for (const el of [root, ...root.querySelectorAll('*')]) {
    let own = '';
    for (const n of el.childNodes) if (n.nodeType === 3) own += n.textContent;
    own = own.trim();
    const cs = getComputedStyle(el);
    let extra = pseudoOf(el, '::before') + pseudoOf(el, '::after');
    if (cs.display === 'list-item' && cs.listStyleType !== 'none') extra += ` ::marker ${cs.listStyleType}`;
    if ((el.localName === 'input' || el.localName === 'textarea') && (el.value || el.placeholder)) extra += ` value ${el.value || el.placeholder}`;
    else if (el.localName === 'select' && el.selectedOptions && el.selectedOptions[0]) extra += ` value ${el.selectedOptions[0].textContent}`;
    if (!own && !extra) continue;
    if (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
    const sig = [own, extra, cs.fontFamily, cs.fontWeight, cs.fontStyle, cs.fontStretch, cs.fontVariationSettings, cs.fontSynthesis, el.lang || document.documentElement.lang].join('\u0001');
    if (seen.has(sig)) continue;
    seen.add(sig);
    els.push(el);
    const label = own || (extra.match(/::(?:before|after) ("(?:[^"\\]|\\.)*"|\S+)/) || [])[0] || extra.trim();
    texts.push(label.replace(/\s+/g, ' ').slice(0, 40));
  }
  window.__fcTexts = texts;
  return els;
}

/**
 * The fonts Chromium used (CDP CSS.getPlatformFontsForNode) for every visible text element under `scope` that was not
 * checked before with the same text and font settings — call after each seek. `cdp` is a CDPSession on the page with
 * DOM and CSS enabled and DOM.getDocument called once. Returns [{ text, fonts: [{ familyName, isCustomFont, glyphCount }] }].
 */
export async function domFontsNow(cdp, scope = '#stage') {
  const { result, exceptionDetails } = await cdp.send('Runtime.evaluate', { expression: `(${fontCandidates.toString()})(${JSON.stringify(scope)})`, objectGroup: 'fontcheck', awaitPromise: true });
  if (exceptionDetails || !result.objectId) return [];
  const texts = (await cdp.send('Runtime.evaluate', { expression: 'window.__fcTexts', returnByValue: true })).result.value || [];
  const { result: props } = await cdp.send('Runtime.getProperties', { objectId: result.objectId, ownProperties: true });
  const out = [];
  for (const p of props) {
    if (!/^\d+$/.test(p.name) || !p.value || !p.value.objectId) continue;
    try {
      const { nodeId } = await cdp.send('DOM.requestNode', { objectId: p.value.objectId });
      const res = await cdp.send('CSS.getPlatformFontsForNode', { nodeId });
      out.push({ text: texts[+p.name] || '', fonts: res.fonts || [] });
    } catch { /* gone or not laid out */ }
  }
  await cdp.send('Runtime.releaseObjectGroup', { objectGroup: 'fontcheck' });
  return out;
}
