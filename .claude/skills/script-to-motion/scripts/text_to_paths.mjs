#!/usr/bin/env node
/**
 * text_to_paths.mjs — glyph outlines of display lines, for TypeFX effects that work on the letter shapes
 * (shatter by stroke, Hangul jamo flying apart, liquid/melting outlines, draw-on, morphs, 3D extrusion).
 *
 *   node text_to_paths.mjs <dir>                          build js/glyphs.js from <dir>/glyphs.json
 *   node text_to_paths.mjs <dir> --add <key> --text "심해" --font pretendard [--size 220] [--weight 800]
 *                         [--tracking 0] [--line-height 1.15] [--align left|center|right] [--step 3] [--strokes]
 *   node text_to_paths.mjs <dir> --remove <key>
 *   node text_to_paths.mjs <dir> --list
 *
 * Fonts: only the skill's catalogue fonts (SIL OFL 1.1) that are installed in the project, read from the project's
 * own unmodified files (sha256 checked against the catalogue). A character the font lacks is an error — there is
 * no fallback font. Variable fonts (Pretendard) are instanced at --weight. Each entry records its font, file,
 * sha256 and licence; check.mjs verifies them.
 * Licence note (OFL FAQ 1.1/1.1.1): using a font's outlines for graphics, video titling or 3D shapes is design use;
 * the artwork is not covered by the OFL. Outline only the lines the video shows — never a whole character set.
 *
 * Overlapping contours of a glyph are merged by default (variable fonts like Pretendard keep strokes as overlapping
 * outlines: unmerged they show as inner lines in draw-on, darker patches when pieces fade, seams on bevelled 3D).
 * Merged outlines are computed at 1 px and resampled to --step for deformers. --strokes keeps the overlapping
 * strokes as separate pieces (letters coming apart stroke by stroke) at the cost of those artefacts.
 *
 * Output per key: { text, font, size, w, h, glyphs: [{ ch, line, word, x, adv, pieces: [{ d, c, b, rings }] }] }
 *   d      exact outline (M/L/Q/C/Z) of one piece: an outer contour with its holes (a jamo, a stroke, the dot of i)
 *   rings  the same contours resampled every --step px (for deformers), flat [x, y, x, y, …], original winding
 *   c, b   centroid and bbox; coordinates are px in the text block, origin top-left, y down
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadCatalog, sha256, allowedFonts } from './lib/fonts.mjs';
import { REQUIRED_LICENSE } from './lib/fontfetch.mjs';

let fontkit, wawoff, polyclip;
try { fontkit = await import('fontkit'); wawoff = (await import('wawoff2')).default; polyclip = (await import('polygon-clipping')).default; } catch {
  console.error('fontkit/wawoff2/polygon-clipping are not installed. Run once:  npm install --prefix ' + path.dirname(fileURLToPath(import.meta.url)));
  process.exit(4);
}

const argv = process.argv.slice(2);
const opt = { _: [] };
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith('--')) opt[argv[i].slice(2)] = argv[i + 1] != null && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  else opt._.push(argv[i]);
}
const dir = path.resolve(opt._[0] || '.');
if (!fs.existsSync(path.join(dir, 'index.html'))) { console.error(`no index.html in ${dir}`); process.exit(2); }
const specFile = path.join(dir, 'glyphs.json');
const spec = fs.existsSync(specFile) ? JSON.parse(fs.readFileSync(specFile, 'utf8')) : {};
const catalog = loadCatalog();

if (opt.list) {
  const keys = Object.keys(spec);
  if (!keys.length) console.log('glyphs.json is empty — add a line with --add <key> --text "…" --font <id>');
  for (const k of keys) console.log(`${k.padEnd(16)} ${JSON.stringify(spec[k].text)}  ${spec[k].font} ${spec[k].size || 200}px w${spec[k].weight || ''}`);
  process.exit(0);
}
if (typeof opt.remove === 'string') { delete spec[opt.remove]; }
if (typeof opt.add === 'string') {
  if (typeof opt.text !== 'string' || typeof opt.font !== 'string') { console.error('--add needs --text "…" and --font <catalogue id>'); process.exit(2); }
  spec[opt.add] = Object.fromEntries(Object.entries({
    text: opt.text.replace(/\\n/g, '\n'), font: opt.font, size: num(opt.size, 200), weight: opt.weight != null ? num(opt.weight) : undefined,
    tracking: num(opt.tracking, 0), lineHeight: num(opt['line-height'], 1.15), align: opt.align || 'left', step: num(opt.step, 3),
    merge: opt.strokes ? false : undefined,
  }).filter(([, v]) => v !== undefined));
}
function num(v, d) { return v == null || v === true ? d : Number(v); }

// ---------- fonts: catalogue entry → verified project files → fontkit faces ----------
const faceCache = new Map();
async function faces(id, weight) {
  const ALLOWED = allowedFonts(dir, catalog).fonts;
  const font = ALLOWED.find((f) => f.id === id) || ALLOWED.find((f) => f.family.toLowerCase() === String(id).toLowerCase());
  if (!font) throw new Error(`font "${id}" is not installed in the project — a catalogue id or a Google Fonts family installed with add_font.mjs (fonts/fonts.lock.json)`);
  if (font.license !== REQUIRED_LICENSE) throw new Error(`${id}: licence ${font.license} — SIL OFL 1.1 fonts only`);
  if (!fs.existsSync(path.join(dir, font.licenseFile.dest))) throw new Error(`${id}: licence file ${font.licenseFile.dest} missing — install with add_font.mjs ${dir} ${id}`);
  const W0 = weight == null ? 400 : weight;
  const ranges = font.files.map((file) => {
    const [lo, hi = lo] = String(file.weight || '400').split(/\s+/).map(Number);
    return { file, lo, hi, dist: W0 < lo ? lo - W0 : W0 > hi ? W0 - hi : 0 };
  });
  const best = Math.min(...ranges.map((r) => r.dist));
  if (best > 0) console.log(`  ⚠ ${id} has no weight ${W0}; using the nearest (${ranges.find((r) => r.dist === best).lo})`);
  const out = [];
  for (const { file, lo, hi } of ranges.filter((r) => r.dist === best)) {
    const abs = path.join(dir, file.dest);
    if (!fs.existsSync(abs)) throw new Error(`${id}: ${file.dest} is not installed in the project — node add_font.mjs ${dir} ${id}`);
    const w = Math.max(lo, Math.min(hi, W0));
    const key = abs + '@' + w;
    if (!faceCache.has(key)) {
      const hash = sha256(abs);
      if (hash !== file.sha256) throw new Error(`${file.dest}: sha256 differs from the ${font.fromLock ? 'pinned fonts.lock.json' : 'catalogue'} — the font file was modified; reinstall it (add_font.mjs)`);
      let buf = fs.readFileSync(abs);
      if (buf.slice(0, 4).toString('latin1') === 'wOF2') buf = Buffer.from(await wawoff.decompress(buf));
      let face = fontkit.create(buf);
      if (face.variationAxes && face.variationAxes.wght && lo !== hi) face = face.getVariation({ wght: w });
      faceCache.set(key, { face, file, font, weight: w, hash });
    }
    out.push(faceCache.get(key));
  }
  if (!out.length) throw new Error(`${id}: no file for weight ${weight} (files: ${font.files.map((f) => f.weight).join(', ')})`);
  return out;
}

// ---------- geometry ----------
const r1 = (v) => Math.round(v * 10) / 10;
function flattenAndPaths(cmds, X, Y, step) {
  // returns contours: [{ d, pts: [x,y,…] }]
  const contours = [];
  let cur = null, px = 0, py = 0, sx = 0, sy = 0;
  const add = (x, y) => { cur.pts.push(r1(x), r1(y)); };
  const close = () => { if (cur && cur.pts.length >= 6) { cur.d += 'Z'; contours.push(cur); } cur = null; };
  for (const { command, args } of cmds) {
    if (command === 'moveTo') {
      close();
      px = sx = X(args[0]); py = sy = Y(args[1]);
      cur = { d: `M${r1(px)} ${r1(py)}`, pts: [] };
      add(px, py);
    } else if (command === 'lineTo') {
      const x = X(args[0]), y = Y(args[1]);
      const n = Math.max(1, Math.ceil(Math.hypot(x - px, y - py) / step));
      for (let i = 1; i <= n; i++) add(px + (x - px) * i / n, py + (y - py) * i / n);
      cur.d += `L${r1(x)} ${r1(y)}`;
      px = x; py = y;
    } else if (command === 'quadraticCurveTo') {
      const cx = X(args[0]), cy = Y(args[1]), x = X(args[2]), y = Y(args[3]);
      const len = Math.hypot(cx - px, cy - py) + Math.hypot(x - cx, y - cy);
      const n = Math.max(2, Math.ceil(len / step));
      for (let i = 1; i <= n; i++) { const t = i / n, a = (1 - t) * (1 - t), b = 2 * (1 - t) * t, c = t * t; add(a * px + b * cx + c * x, a * py + b * cy + c * y); }
      cur.d += `Q${r1(cx)} ${r1(cy)} ${r1(x)} ${r1(y)}`;
      px = x; py = y;
    } else if (command === 'bezierCurveTo') {
      const c1x = X(args[0]), c1y = Y(args[1]), c2x = X(args[2]), c2y = Y(args[3]), x = X(args[4]), y = Y(args[5]);
      const len = Math.hypot(c1x - px, c1y - py) + Math.hypot(c2x - c1x, c2y - c1y) + Math.hypot(x - c2x, y - c2y);
      const n = Math.max(2, Math.ceil(len / step));
      for (let i = 1; i <= n; i++) {
        const t = i / n, a = (1 - t) ** 3, b = 3 * (1 - t) ** 2 * t, c = 3 * (1 - t) * t * t, e = t ** 3;
        add(a * px + b * c1x + c * c2x + e * x, a * py + b * c1y + c * c2y + e * y);
      }
      cur.d += `C${r1(c1x)} ${r1(c1y)} ${r1(c2x)} ${r1(c2y)} ${r1(x)} ${r1(y)}`;
      px = x; py = y;
    } else if (command === 'closePath') {
      if (cur && (px !== sx || py !== sy)) {
        const n = Math.max(1, Math.ceil(Math.hypot(sx - px, sy - py) / step));
        for (let i = 1; i < n; i++) add(px + (sx - px) * i / n, py + (sy - py) * i / n);
      }
      close();
    }
  }
  close();
  // drop a duplicated closing point
  for (const c of contours) {
    const p = c.pts, n = p.length;
    if (n >= 4 && Math.abs(p[0] - p[n - 2]) < 0.05 && Math.abs(p[1] - p[n - 1]) < 0.05) p.splice(n - 2, 2);
  }
  return contours;
}
const area = (p) => { let a = 0; for (let i = 0, n = p.length; i < n; i += 2) { const j = (i + 2) % n; a += p[i] * p[j + 1] - p[j] * p[i + 1]; } return a / 2; };
function inside(p, x, y) {
  let c = false;
  for (let i = 0, j = p.length - 2; i < p.length; j = i, i += 2) {
    const xi = p[i], yi = p[i + 1], xj = p[j], yj = p[j + 1];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c;
  }
  return c;
}
function bbox(pts) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < pts.length; i += 2) { x0 = Math.min(x0, pts[i]); x1 = Math.max(x1, pts[i]); y0 = Math.min(y0, pts[i + 1]); y1 = Math.max(y1, pts[i + 1]); }
  return [r1(x0), r1(y0), r1(x1), r1(y1)];
}
/** group contours into pieces: an outer contour (even nesting depth) with the holes directly inside it */
function pieces(contours) {
  const C = contours.map((c) => ({ ...c, a: area(c.pts), depth: 0, parent: -1 }));
  const contains = (B, A) => {
    if (Math.abs(A.a) >= Math.abs(B.a)) return false;
    const n = A.pts.length / 2, k = Math.max(1, Math.floor(n / 7));
    let hit = 0, tot = 0;
    for (let i = 0; i < n; i += k) { tot++; if (inside(B.pts, A.pts[2 * i], A.pts[2 * i + 1])) hit++; }
    return hit >= tot * 0.85;
  };
  C.forEach((A, i) => {
    let best = -1;
    C.forEach((B, j) => {
      if (i !== j && contains(B, A)) { A.depth++; if (best < 0 || Math.abs(B.a) < Math.abs(C[best].a)) best = j; }
    });
    A.parent = best;
  });
  const out = [];
  C.forEach((A, i) => {
    if (A.depth % 2) return;
    const holes = C.filter((H) => H.depth % 2 === 1 && H.parent === i);
    out.push(piece([A, ...holes].map((r) => r.pts), [A, ...holes].map((r) => r.d).join('')));
  });
  return out;
}
/** a piece from its rings (outer first): exact d if known, else the polyline; area-weighted centroid; bbox */
function piece(rings, d) {
  // area-weighted centroid; holes count negative whatever their winding
  const s0 = Math.sign(area(rings[0])) || 1;
  let sx = 0, sy = 0, sa = 0;
  rings.forEach((p, ri) => {
    const a = area(p);
    let x = 0, y = 0;
    for (let k = 0, n = p.length; k < n; k += 2) { const j = (k + 2) % n, cr = p[k] * p[j + 1] - p[j] * p[k + 1]; x += (p[k] + p[j]) * cr; y += (p[k + 1] + p[j + 1]) * cr; }
    const f = ri === 0 ? 1 : (Math.sign(a) === s0 ? -1 : 1);
    sx += f * x / 6; sy += f * y / 6; sa += f * a;
  });
  const b = bbox(rings.flat());
  const c = Math.abs(sa) > 1e-3 ? [r1(sx / sa), r1(sy / sa)] : [r1((b[0] + b[2]) / 2), r1((b[1] + b[3]) / 2)];
  const dd = d || rings.map((r) => { let s = ''; for (let k = 0; k < r.length; k += 2) s += (k ? 'L' : 'M') + r[k] + ' ' + r[k + 1]; return s + 'Z'; }).join('');
  return { d: dd, c, b, rings };
}
/** union the overlapping contours of one glyph's pieces; d from the fine polygon, rings resampled every `step` px */
function mergePieces(pcs, step) {
  const toPoly = (rings) => rings.map((r) => { const pts = []; for (let k = 0; k < r.length; k += 2) pts.push([r[k], r[k + 1]]); pts.push(pts[0]); return pts; });
  const merged = pcs.length > 1 ? polyclip.union(...pcs.map((p) => toPoly(p.rings))) : pcs.map((p) => toPoly(p.rings));
  return merged.map((poly) => {
    const fine = poly.map((ring) => simplify(ring.slice(0, -1), 0.2).flat().map(r1));
    const pc = piece(fine);
    pc.rings = fine.map((r) => resample(r, step));
    return pc;
  });
}
/** Ramer–Douglas–Peucker on a closed ring of [x, y] (tolerance px): fewer points, same outline at any size */
function simplify(pts, tol) {
  if (pts.length < 8) return pts;
  const keep = new Uint8Array(pts.length);
  const rdp = (a, b) => {
    let md = 0, mi = -1;
    const [ax, ay] = pts[a], [bx, by] = pts[b], dx = bx - ax, dy = by - ay, L = Math.hypot(dx, dy) || 1e-9;
    for (let i = a + 1; i < b; i++) { const d = Math.abs((pts[i][0] - ax) * dy - (pts[i][1] - ay) * dx) / L; if (d > md) { md = d; mi = i; } }
    if (md > tol && mi > 0) { keep[mi] = 1; rdp(a, mi); rdp(mi, b); }
  };
  const half = Math.floor(pts.length / 2);
  keep[0] = keep[half] = 1;
  rdp(0, half); rdp(half, pts.length - 1); keep[pts.length - 1] = 1;
  return pts.filter((_, i) => keep[i]);
}
/** points every `step` px along a closed ring (keeps winding) */
function resample(r, step) {
  const n = r.length / 2;
  if (n < 3) return r;
  let per = 0;
  for (let i = 0; i < n; i++) { const j = (i + 1) % n; per += Math.hypot(r[2 * j] - r[2 * i], r[2 * j + 1] - r[2 * i + 1]); }
  const m = Math.max(6, Math.round(per / step)), seg = per / m, out = [];
  let i = 0, acc = 0, need = 0;
  let ax = r[0], ay = r[1];
  while (out.length < m * 2) {
    const j = (i + 1) % n, bx = r[2 * j], by = r[2 * j + 1], L = Math.hypot(bx - ax, by - ay);
    if (acc + L >= need) {
      const k = L ? (need - acc) / L : 0;
      out.push(r1(ax + (bx - ax) * k), r1(ay + (by - ay) * k));
      need += seg;
      continue;
    }
    acc += L; ax = bx; ay = by; i = j;
    if (i === 0 && acc > per + seg) break;
  }
  return out;
}

// ---------- layout one entry ----------
async function build(key, e) {
  const size = e.size || 200, lhK = e.lineHeight || 1.15, track = e.tracking || 0, step = e.step || 3;
  const F = await faces(e.font, e.weight);
  const main = F[0];
  const upm = main.face.unitsPerEm, k = size / upm;
  const asc = main.face.ascent * k, desc = Math.abs(main.face.descent) * k, LH = lhK * size;
  const lines = String(e.text).split('\n');
  const missing = new Set();
  const laid = lines.map((line, li) => {
    const items = [];
    let x = 0;
    if (F.length === 1) {
      const run = main.face.layout(line);
      const chars = [...line];
      run.glyphs.forEach((g, gi) => {
        const pos = run.positions[gi];
        const ch = g.codePoints && g.codePoints.length ? String.fromCodePoint(...g.codePoints) : chars[gi] || '';
        if (g.id === 0 && ch.trim()) missing.add(ch);
        items.push({ ch, g, face: main.face, x: x + pos.xOffset * k, y: pos.yOffset * k, adv: pos.xAdvance * k });
        x += pos.xAdvance * k + track;
      });
    } else {
      for (const ch of line) {
        const cp = ch.codePointAt(0);
        const hit = F.find((ff) => ff.face.hasGlyphForCodePoint(cp));
        if (!hit) { if (ch.trim()) missing.add(ch); continue; }
        const g = hit.face.glyphForCodePoint(cp);
        const kk = size / hit.face.unitsPerEm;
        items.push({ ch, g, face: hit.face, x, y: 0, adv: g.advanceWidth * kk, kk });
        x += g.advanceWidth * kk + track;
      }
    }
    return { items, width: Math.max(0, x - track), li };
  });
  if (missing.size) throw new Error(`${key}: ${e.font} has no glyph for ${[...missing].map((c) => JSON.stringify(c)).join(' ')} — change the text or use a catalogue font that covers it (no fallback fonts)`);
  const w = Math.ceil(Math.max(1, ...laid.map((l) => l.width)));
  const h = Math.ceil(LH * lines.length);
  const glyphs = [];
  let word = 0;
  for (const L of laid) {
    const x0 = e.align === 'center' ? (w - L.width) / 2 : e.align === 'right' ? w - L.width : 0;
    const base = L.li * LH + (LH - (asc + desc)) / 2 + asc;
    for (const it of L.items) {
      if (!it.ch.trim()) { word++; continue; }
      const kk = it.kk || k;
      const X = (v) => x0 + it.x + v * kk, Y = (v) => base - it.y - v * kk;
      let pcs;
      if (e.merge === false) pcs = pieces(flattenAndPaths(it.g.path.commands, X, Y, step));
      else pcs = mergePieces(pieces(flattenAndPaths(it.g.path.commands, X, Y, Math.min(step, 1))), step);
      glyphs.push({ ch: it.ch, line: L.li, word, x: r1(x0 + it.x), adv: r1(it.adv), pieces: pcs });
    }
    word++;
  }
  const fileRec = main.file;
  return {
    v: 1, key, text: e.text, size, weight: main.weight, tracking: track, lineHeight: lhK, align: e.align || 'left', step, merge: e.merge !== false, w, h,
    font: { id: main.font.id, family: main.font.family, file: fileRec.dest, sha256: fileRec.sha256, version: main.font.version, license: main.font.license },
    files: F.map((ff) => ({ file: ff.file.dest, sha256: ff.hash })),
    glyphs,
  };
}

// ---------- build all, write js/glyphs.js, wire index.html ----------
const out = {};
let chars = 0, pts = 0;
try {
  for (const [key, e] of Object.entries(spec)) {
    if (!/^[A-Za-z_$][\w$-]*$/.test(key)) throw new Error(`key "${key}": use letters, digits, _ or -`);
    out[key] = await build(key, e);
    chars += [...String(e.text)].filter((c) => c.trim()).length;
    for (const g of out[key].glyphs) for (const p of g.pieces) for (const r of p.rings) pts += r.length / 2;
  }
} catch (err) {
  console.error('✖ ' + err.message);
  process.exit(1);
}
fs.writeFileSync(specFile, JSON.stringify(spec, null, 2) + '\n');
const header = `/* generated by text_to_paths.mjs from glyphs.json — do not edit.
   Glyph outlines of the display lines this video animates, from SIL OFL 1.1 catalogue fonts (the project's
   unmodified font files, sha256 below). OFL FAQ 1.1/1.1.1: outlines used for graphics/video titling are design use. */\n`;
fs.mkdirSync(path.join(dir, 'js'), { recursive: true });
fs.writeFileSync(path.join(dir, 'js', 'glyphs.js'), header + 'window.GLYPHS = Object.assign(window.GLYPHS || {}, ' + JSON.stringify(out) + ');\n');
const idx = path.join(dir, 'index.html');
let html = fs.readFileSync(idx, 'utf8');
if (!/src=["']js\/glyphs\.js["']/.test(html)) {
  const tag = '<script src="js/glyphs.js"></script>     <!-- glyph outlines: scripts/text_to_paths.mjs -->\n  ';
  const at = html.search(/<script src=["']js\/typefx\.js["']/) >= 0 ? html.search(/<script src=["']js\/typefx\.js["']/) : html.search(/<script src=["']js\/scenes\.js["']/);
  if (at >= 0) { html = html.slice(0, at) + tag + html.slice(at); fs.writeFileSync(idx, html); console.log('  index.html: added <script src="js/glyphs.js">'); }
  else console.log('  ⚠ add <script src="js/glyphs.js"></script> to index.html before js/scenes.js');
}
const kb = (fs.statSync(path.join(dir, 'js', 'glyphs.js')).size / 1024).toFixed(0);
console.log(`✓ js/glyphs.js: ${Object.keys(out).length} line(s), ${chars} glyphs, ${pts} outline points, ${kb} KB`);
for (const [k, v] of Object.entries(out)) {
  const np = v.glyphs.reduce((s, g) => s + g.pieces.length, 0);
  console.log(`  ${k.padEnd(16)} ${JSON.stringify(v.text)} · ${v.font.family} ${v.weight} · ${v.size}px · ${v.w}×${v.h} · ${v.glyphs.length} glyphs, ${np} pieces`);
}
if (chars > 300) console.log('  ⚠ more than 300 glyphs: outlines are for display lines (titles, key words), not paragraphs — keep body text as real text');
