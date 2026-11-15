# Choosing fonts

Read this when picking type for a piece. Every font must be SIL OFL 1.1 (SKILL.md → Fonts). Within that rule you
can use the seven catalogue fonts and **any family in the Google Fonts repository's `ofl/` directory**. This page
recommends; it is not a whitelist. Choose what the piece needs, look at it rendered, and verify it.

```bash
node <skill>/scripts/add_font.mjs <dir> --list                          # the catalogue
node <skill>/scripts/add_font.mjs <dir> "Do Hyeon" "Anybody"            # Google Fonts families by name (ofl/ only)
node <skill>/scripts/add_font.mjs <dir> "Gothic A1" --weights 400,800   # static families: only the weights you use
node <skill>/scripts/add_font.mjs <dir> "Hahmlet" --token --serif       # also set a CSS token in :root
```

Google families are pinned in `fonts/fonts.lock.json`: the google/fonts commit and the sha256 of every file.
`check.mjs` and `check_fonts.mjs` verify them. Apache- or UFL-licensed Google families are refused, by design.
Re-running `add_font.mjs` for a family rewrites its `@font-face` rules in `css/fonts.css`; with other `--weights` it
replaces the installed set (files of weights no longer listed are removed). `--token` takes the custom property's
name with its dashes (`--token --serif`, or `--token=--serif`); for a catalogue font a bare `--token` uses the
catalogue's own token.

`check_fonts.mjs` seeks through the video every 0.5 s (plus each cue's middle and end; `--step N` to change it,
`--step 0` for the cue moments only) and after every seek asks Chromium which font drew every visible text — own text,
`::before`/`::after` content, list markers and form values, including elements created later. Every web font the page
has must be an installed, unmodified file of its own family: `local()`, remote or `data:` URLs and any other file
(even one loaded with `new FontFace(…)` from a renamed `.bin`) fail, and so does a font stack that starts with a
generic family (`48px sans-serif, 'Pretendard'` is drawn by a system font).

## Contents
1. How to choose
2. Korean families (all in google/fonts `ofl/`)
3. Latin display
4. Variable fonts with expressive axes (for TypeFX)
5. Practical notes

---

## 1. How to choose

- **One workhorse plus at most one or two character fonts** per piece. Pretendard stays the default for
  body, numbers and UI; a character font carries the titles and the hero lines.
- **Pick by what the piece says** (motion-design.md §2): calm and editorial → a serif; urgent → heavy
  sans; playful → rounded; personal → handwriting; tech → mono or geometric.
- **Look before you commit.** Install two or three candidates in the project, set them on the actual hero
  lines, and look at them on a render.py sheet (`--screenshot` over the line's moment, then `--at T --res 1080p` or
  `--crop X,Y,W,H --res 4k` on the line for the glyphs' detail). Many display fonts have
  quirks (missing syllables, odd numerals) that only show on the real words.
- **Hangul coverage.** Many Korean display and handwriting fonts carry only the 2,350 common syllables
  (KS X 1001). A rare syllable then falls back to Pretendard mid-word. `check_fonts.mjs` reports which font
  drew each glyph; rephrase the line or choose another font if a fallback shows.
- **Latin-only fonts** draw Hangul with the fallback (Pretendard). Use them for English words, numbers and
  labels, not for Korean lines.

## 2. Korean families (all in google/fonts `ofl/`)

Notes describe use, not quality. Check the look on your own words.

| tone | families |
|---|---|
| clean sans (body, UI, data) | Noto Sans KR (variable 100–900) · Gothic A1 (9 weights) · IBM Plex Sans KR (corporate, technical) · Nanum Gothic · Asta Sans (variable 300–800) · Gowun Dodum (soft) · Sunflower · Stylish |
| serif / 명조 (editorial, story, history, quotes) | Noto Serif KR (variable 200–900) · Hahmlet (variable 100–900) · Nanum Myeongjo · Gowun Batang *(catalogue)* · Song Myung (traditional, brush-like) · Diphylleia · Grandiflora One |
| heavy display (headlines, promos, warnings) | Black Han Sans *(catalogue)* · Do Hyeon (bold, signage-like) · Gasoek One · Bagel Fat One (fat, bubbly) |
| friendly / rounded (education, kids, casual) | Jua *(catalogue)* · Dongle · Cute Font · Poor Story |
| retro / decorative (titles with character) | Black And White Picture · Yeon Sung · Gugi · Kirang Haerang · Moirai One · Single Day · Orbit |
| handwriting / brush (notes, asides, emotion) | **East Sea Dokdo** (the user's choice for every handwritten touch: memos, pen notes, chapter numbers — `add_font.mjs <dir> "East Sea Dokdo"`, used as `--hand`) · Nanum Pen Script *(catalogue)* · Nanum Brush Script · Dokdo (rough brush) · Gaegu · Gamja Flower · Hi Melody |
| code / mono | D2Coding *(catalogue, core)* · Nanum Gothic Coding — code only: never for Hangul display text (it spaces it out), and not for prices (its slashed zero reads like code); numbers use Pretendard with `font-variant-numeric: tabular-nums` |

Korean static fonts are large (Gothic A1 400 + 800 ≈ 4.4 MB). Install only the weights you use.

## 3. Latin display

All in google/fonts `ofl/`. Use them for English titles, numbers and labels.

| feel | families |
|---|---|
| condensed impact, posters, sports | Bebas Neue · Anton · Oswald (variable) · Big Shoulders (variable, see §4) |
| wide / geometric headline | Unbounded (variable) · Syne (variable) · Righteous · Bungee |
| elegant serif display | Playfair Display (variable) · DM Serif Display · Instrument Serif · Fraunces (see §4) |
| neon / lines / retro | Monoton (multi-line neon) · Shrikhand · Major Mono Display |
| glitch / digital | Rubik Glitch · Bitcount, Sixtyfour, Workbench (see §4) |
| neutral modern sans | Inter (variable) · Space Grotesk (variable) · Montserrat (variable) · Rubik (variable) · Archivo (see §4) |

## 4. Variable fonts with expressive axes (for TypeFX)

A variable font's axes can be animated per letter, as a pure function of time. This is type that changes its own
shape, not just its position. TypeFX writes them through the `vary` channel (type-fx.md):

```js
const g = TX.split('#s03 .title');
TX.breathe(g, a, b, { axis: 'wdth', min: 50, max: 150, rest: 100 });        // letters stretch and squeeze in a wave
TX.fx(g, { from: a, to: b }, (u, s, c) => {                                  // or any axis, any shape
  c.vary = Object.assign(c.vary || {}, { XROT: 40 * Math.sin(s.t * 2 + u.i * 0.6) });
});
```

| family | axes (range) | what it can say |
|---|---|---|
| Anybody | wdth 50–150, wght 100–900 | stretch, squeeze, pressure, breath |
| Roboto Flex | wdth 25–151, wght 100–1000, slnt, opsz, GRAD, XTRA … | precise width/weight/slant control on a neutral sans |
| Bricolage Grotesque | opsz, wdth 75–100, wght 200–800 | lively editorial sans |
| Archivo | wdth 62–125, wght 100–900 | condensed ↔ wide data headlines |
| Big Shoulders | opsz, wght 100–900 | industrial condensed, signage |
| Recursive | CASL 0–1, CRSV 0–1, MONO 0–1, slnt, wght 300–1000 | code that relaxes into casual handwriting |
| Fraunces | SOFT 0–100, WONK 0–1, opsz, wght | a serif that softens, wobbles, gets heavier |
| Tilt Warp · Tilt Neon | XROT −45–45, YROT −45–45 | letters tilting in 3D on their own, signage |
| Kablammo | MORF 0–60 | cartoon letters that wobble and morph |
| Honk | MORF 0–45, SHLN 0–100 | inflated 3D colour letters, shine |
| Nabla | EDPT 0–200, EHLT 0–24 | isometric 3D colour letters whose depth can grow |
| Climate Crisis | YEAR 1979–2050 | letters that melt away with a year: data as type |
| Handjet | ELGR, ELSH, wght | letters built from elements (dots, shapes) |
| Bitcount | ELSH, ELXP, CRSV, slnt, wght | pixel/LED type |
| Sixtyfour · Workbench | BLED 0–100, SCAN −53–100 | CRT scanlines and bleed |

These are Latin-only. Use them on English or number lines. Honk and Nabla are colour (COLRv1) fonts: they work
as DOM text, but `text_to_paths.mjs` outlines don't carry their colour layers.

## 5. Practical notes

- `css/fonts.css` gets one `@font-face` per installed file. A variable file declares its weight range;
  other axes need no CSS — set them with `font-variation-settings` or TypeFX `vary`.
- Glyph outlines (`text_to_paths.mjs`) and canvas text (`TX.raster`) accept any installed font by catalogue id or
  family name (`"font": "Do Hyeon"` in glyphs.json; `family: "'Do Hyeon'"` in TX.raster).
- Reproducibility: copying the project keeps `fonts/` and `fonts.lock.json`. Re-running `add_font.mjs` for a
  locked family fetches the same commit and refuses a file whose hash changed.
- Fonts must stay unmodified: no subsetting, renaming or conversion. Each family's `OFL.txt` travels with it.
- **East Sea Dokdo has only ~1,300 glyphs**: common Hangul and Latin, few symbols. Keep `'East Sea Dokdo', 'Pretendard',
  cursive` as the stack, run `check_fonts.mjs` after adding handwritten text, and draw symbols (✦, ✓, arrows) as SVG.
- Weights above 800 look crude on screen at this size and were rejected by the user; keep display weights ≤ 800.
