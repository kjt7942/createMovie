# Expressive typography — TypeFX

Read this when a line deserves more than a fade or a slide: the hero number, the title, the word the story turns
on. Type that cracks, melts, ripples, jiggles, falls apart and re-forms, glows, or turns solid is one of the most
noticed parts of motion design. Users of this skill treat it as essential.

TypeFX (`js/typefx.js`, in every new project) is a small open system, not a menu. Its named effects are examples
written with the same public parts you have. When the story needs something the presets don't do, compose it
(§4). Don't settle for the nearest preset.

## Contents
1. The idea: representations × effects
2. Which representation
3. Setup
4. Units, channels, effects — writing your own
5. Time and space helpers
6. Presets (examples) and what they say
7. Copies: shards, bands, layers
8. Glyph outlines: text_to_paths.mjs, pieces, deformers
9. Raster type: pixels, tiles, warps
10. With the timeline, FXKit and 3D
11. Craft rules
12. Determinism, cost, verification
13. Pitfalls that were actually hit

---

## 1. The idea: representations × effects

The same words can be materialised in different ways. Each way makes different motion possible:

| representation | call | units | what it can do that the others can't |
|---|---|---|---|
| **split** — real DOM text | `TX.split(el, { by })` | chars / words / lines | stays real text (sharp, searchable, checked by `check_fonts`), variable-font weight (`w`), CSS 3D |
| **copies** — exact overlays of an element | `TX.copies(el, …)`, `TX.shatter`, `TX.glitch`, `TX.extrude` | clipped/tinted clones | cut the text anywhere (glass shards, glitch bands), stack it (solid block letters, true Z depth) |
| **glyph pieces** — outlines from the font | `TX.glyphs(el, key)` | pieces (a jamo, a stroke, the dot of an i) or glyphs | Hangul splitting into its jamo, bending the letter shapes (liquid, melt, shock waves), drawing them on, morphs, 3D extrusion |
| **raster tiles** — the text as pixels | `await TX.raster(text)` → `TX.tiles(R)` | tiles (2–14 px) | dust, sand and particles that keep the exact look of the letters; per-row/column pixel warps (ripple, heat haze) |

Every unit, in every representation, has the same **channels**, and every effect writes to them. So one effect
function works on chars, shards, jamo and pixel tiles alike. `TX.scatter` is a letter explosion, a glass burst,
Hangul coming apart, or text blowing away as dust, depending on what you hand it.

## 2. Which representation

- Default to **split**. Most kinetic type is per-letter motion of real text.
- The text must **break where letters don't**: glass, cracks, slices → **copies** (`shatter`, `glitch`, your own cells).
- **Solid** letters → **copies** (`extrude`). Use `mode: 'offset'` for poster block type, or `'z'` for real depth while
  the element turns in 3D. For lit, bevelled 3D, extrude the glyph outlines in three.js (threejs-3d.md).
- The **letter shapes themselves** must move: jamo flying in, strokes bending, melting, wobbling like jelly, a
  word morphing into another or into a shape → **glyph pieces**.
- The text becomes **matter** (dust, sand, smoke, a swarm), or the whole line must **ripple** like water or heat →
  **raster tiles**.
- Light as the subject (bloom, rays, refraction) → the FX build with `fx.textTexture` or extruded glyphs
  (shader-fx.md).

You can mix them in one beat. The DOM word holds the reading moment, glyph pieces take over for the break, and
dust carries it off. Swap them at a moment of motion or behind a flash, not while everything is still.

## 3. Setup

New projects already link `css/typefx.css` and `js/typefx.js` (after FXKit, before scenes.js). Older projects:
copy both files from `<skill>/assets/template` and add the two tags.

```js
Video.define(async (ctx) => {            // async only if you use TX.raster (it awaits the font)
  const { tl, cue } = ctx;
  const K = FXKit.install(ctx);           // optional: flash, burst, shake to sell impacts
  const TX = TypeFX.install(ctx);
  const g = TX.split('#s03 .title');
  tl.from(g.outer, { yPercent: 100, autoAlpha: 0, stagger: 0.03, duration: 0.6, ease: 'expo.out' }, 'c03');  // timeline: outer
  TX.jelly(g, cue('c03').when('말랑'));                                                                   // TypeFX: inner
});
```

Glyph outlines need `js/glyphs.js`: `node <skill>/scripts/text_to_paths.mjs <dir> --add <key> --text "…" --font <id> …`
(§8). The tool adds the `<script>` tag.

## 4. Units, channels, effects — writing your own

**Units** (`G.units`) carry their rest geometry and identity:

| field | meaning |
|---|---|
| `x, y` | centre relative to the group centre (px) — `nx, ny` the same in −1…1 |
| `w, h` | size of the unit |
| `i, n, k` | index, count, `i/(n−1)` |
| `ch, word, line` | the character, word index, line index (split and glyphs) |
| `r(salt)` | a stable hash 0…1 for this unit (use different salts for independent "random" values) |
| `el` | the element TypeFX writes to (split: the inner `.tx-i`; copies: the clone; glyphs: the path/g) |

**Channels** (`c`), reset every frame. Add to them; multiply the scales and the opacity:

`x y z` (px) · `r` (deg) · `rx ry` (deg, 3D; perspective per unit) · `sx sy` (×) · `kx ky` (skew deg) · `o` (×) ·
`w` (font-weight delta, split only) · `vary` ({ axis: value } for variable-font axes — wdth, slnt, XROT, MORF …; split
and copies; fonts.md §4) · `blur` (px, costly) · `color` (string) · `css` ({ prop: value }, escape hatch)

**An effect** is a window on the timeline and a pure function:

```js
TX.fx(G, { from, to, fill, live }, (u, s, c, G) => { … }, (s, gc, G) => { … /* optional, group level */ });
// s = { t, lt (seconds since from), dur, p (lt/dur), inside }
// fill: 'none' (only inside) · 'forwards' (hold the end: things that leave) · 'backwards' (hold the start: things
//       that arrive) · 'both'.    { static: true } = always on (re-evaluated when G.state changes).
// live: true = the function reads s.t while held by fill — rendered every frame it applies (see the rule below)
// gc (group level): gc.copies = show the copies · gc.hideOrig = hide the original under them · gc.filter = CSS filter on the root
```

**What a held effect may read.** A group renders every frame while `t` is inside one of its windows; outside them
(held by `fill`) it renders only when the playhead crosses a window edge. So a held value must come from `s.lt` / `s.p`
(clamped to the window) or constants — never from `s.t`, or it freezes at whatever frame happened to render last and
differs with the seek path (a plain forward-then-reverse `--seekcheck` can miss it: the playhead has to leave
the window backwards and come back). Something that keeps moving after its window — a hum, a flicker
that never ends — either keeps its window open (`to: Infinity`, or the scene's end) or says `live: true` (rendered every
frame where it applies, including the held sides). `neon` does the first: its hum runs until `to` (default the end of the
video), then holds.

Examples of effects that are not presets, each a few lines:

```js
// pressure crushes the letters (each buckles its own way), then they hold
TX.fx(g, { from: at, to: at + 0.9, fill: 'forwards' }, (u, s, c) => {
  const k = TX.m.spring(s.lt - u.r(1) * 0.12, 2.2, 7);
  c.sy *= 1 - 0.45 * k; c.sx *= 1 + 0.18 * k; c.kx += (u.r(2) - 0.5) * 16 * k;
});

// sinking: letters fall slowly with drag and sway, the deeper the slower (a word dropped into the sea)
TX.fx(g, { from: at, to: at + 3, fill: 'forwards' }, (u, s, c) => {
  const lt = s.lt - u.r(3) * 0.4;
  c.y += TX.m.drift(lt, 260, 0.9);                     // terminal-velocity fall, exact
  c.x += 14 * Math.sin(lt * 2.2 + u.i) * Math.min(1, lt);
  c.r += 9 * Math.sin(lt * 1.7 + u.r(4) * 6);
  c.o *= 1 - TX.m.smooth((lt - 1.8) / 1.2);
});

// sonar reveal: letters pop in as a ring passes them (order by distance from a point)
const ord = TX.order(g, [-300, 0]);
TX.fx(g, { from: at, to: at + 1.2, fill: 'backwards' }, (u, s, c) => {
  const k = TX.m.spring(s.lt - ord[u.i] * 0.6, 2, 8);
  c.sx *= k; c.sy *= k; c.o *= Math.min(1, Math.max(0, (s.lt - ord[u.i] * 0.6) * 10));
});

// glyph outlines breathe: each piece swells from its own centre (deformers get the piece)
TX.deform(gp, { from: a, to: b }, (x, y, s, piece) => {
  const k = 0.06 * Math.sin(s.t * 3) * TX.m.smooth(s.lt / 0.4);
  return [(x - piece.c[0]) * k, (y - piece.c[1]) * k];
});

// heat haze on raster type: rows shimmer with noise
TX.warp(gr, { from: a, to: b, axis: 'x' }, (v, s) => 4 * TX.m.noise(v * 0.04, s.t * 3));
```

To make a reusable effect, write a function that takes a group and options and calls `TX.fx` / `TX.deform` /
`TX.warp`. The presets in `typefx.js` are written this way: copy one and change it.

## 5. Time and space helpers

`TX.m` holds pure helpers. Nothing in them depends on frames already played:

| helper | use |
|---|---|
| `spring(t, freq, decay)` | 0 → 1 with overshoot: arrivals, pops, squash that settles |
| `wobble(t, freq, decay)` | 0 → ±1 → 0: a hit, a jiggle, a ringing bell |
| `drift(t, v, drag)` | distance travelled with drag: pieces that slow down, sinking |
| `bounce(t, h, g, e)` | height of something dropped from `h`, bouncing with restitution `e` |
| `noise(x, y, z)`, `fbm(…)` | smooth deterministic noise −1…1: floating, liquid, wind |
| `hash(a, b, c)` | stable 0…1 from integers: flicker per frame (`Math.floor(t * 24)`), glitch beats |
| `smooth`, `smoother`, `clamp`, `lerp` | shaping |
| `TX.ease('expo.out')` | any GSAP ease as a function 0…1 → 0…1 |
| `TX.order(G, mode)` | 0…1 per unit for staggers: `'index' 'reverse' 'center' 'edges' 'random' 'x' 'y' 'line' 'word'`, `[x, y]` (distance from a point), or `u => value` |
| `TX.stageXY(el, fx, fy)` | stage coordinates of a point in an element (aim FXKit bursts at the impact point) |
| `TX.shardCells(w, h, o)`, `TX.bandCells`, `TX.voronoi` | cut shapes for copies |

Physics is written as closed forms of time (`drift`, `bounce`, `x = v·t + ½·g·t²`). It is never stepped frame by
frame, so any frame can be computed on its own.

## 6. Presets (examples) and what they say

Pick by meaning, not by novelty. An effect that contradicts the line is worse than none.

Times (`at`, `a`, `b`, `TX.fx`'s `from`/`to`) are seconds or cue labels (`'c03'`, `'c03+=0.2'`, `'c03_end-=0.4'`);
TypeFX resolves a label to seconds before adding its own offsets (`TX.at(pos)` does the same for your code).

| preset | works on | says | key options |
|---|---|---|---|
| `wave(G, a, b)` | any | sea, sound, breath, crowd | `amp length speed rot scale` |
| `float(G, a, b)` | any | under water, weightless, dream | `amp speed rot` |
| `breathe(G, a, b)` | split (variable font) | alive, pulse, emphasis without moving; with `axis` any axis: stretch (`wdth`), 3D tilt (`XROT`), morph (`MORF`) | `axis min max rest speed length` |
| `jelly(G, at)` | any (origin bottom) | soft, playful, cute, a landing | `amp freq decay stagger order` |
| `pop(G, at)` | any | arrival, list items, friendly | `stagger freq decay rise` |
| `drop(G, at)` | any | weight, arrival with a thud | `height bounce squash order` |
| `tremble(G, a, b)` | any | fear, cold, pressure, urgency | `amp rate rot` |
| `flip(G, at)` | split/copies | change of state, split-flap board | `axis turns stagger` |
| `scatter(G, at)` / `assemble` | any | explosion, letting go / forming, solution | `from force gravity drag spin tumble z stagger order` |
| `swirl(G, at)` | any | pulled in, drain, black hole (reverse: emerging) | `turns radius stagger reverse` |
| `magnet(G, at)` | any | absorbed, sucked into a point (the trench, a logo) | `to dur stagger shrink` |
| `shatter(el, at)` | copies | impact, a record broken, failure, "the limit breaks" | `impact pieces crack gap force tumble z blur reverse html` |
| `glitch(el, a, b)` | copies | error, signal lost, hacked, uncertainty | `bands amount rate density rgb` |
| `extrude(el, o)` | copies | solid, monumental, weight (`G.state.depth` tweenable) | `mode depth layers angle side shade edge` |
| `neon(G or el, at)` | split / element | night, sign, retro, "turning on" | `color radius ignite hum unlit to` (the hum renders every frame until `to`, default the end of the video — on a long video pass the scene's end) |
| `drawOn(G, at)` | glyphs | handwriting, blueprint, signature | `dur stagger stroke width fillDelay keepStroke` |
| `liquid(G, a, b)` | glyphs | water, heat, dizziness | `amp scale speed` |
| `shockwave(G, at)` | glyphs | impact ringing through, sonar, jelly | `from amp speed freq decay` |
| `melt(G, at)` | glyphs | heat, sadness, pressure, collapse | `drop dur scale reverse` |
| `ripple(G, a, b)` | tiles | reflection, under water, signal | `amp length speed axis` |
| `dissolve(G, at)` / `{reverse}` | tiles | loss, memory, time / materialising | `dur sweep rise wind turbulence order` |
| `motionBlur(G)` | split / copies | speed. Add it to fast scatter, shatter and swirl | `samples shutter alpha` |

Combine them sparingly. `drop` then `jelly` on landing; `shatter` with `blur`, a FXKit `flash` + `burst` +
`shake` at the impact point; `liquid` with a `shockwave` on the stressed word.

## 7. Copies: shards, bands, layers

`TX.copies(el, { cells | n, clip, tint, style, behind, depth3d, html })` puts N full clones of the element's content
over it. Each clone is clipped to its cell or tinted, and together they rebuild the original exactly. While an
effect sets `gc.copies` and `gc.hideOrig`, the copies stand in for the original. Because they are identical at
rest, the swap is invisible.

- Your own cuts: polygons in the element's box (px). `TX.shardCells(w, h, { pieces, impact, seed })` gives glass
  (denser near the impact); `TX.bandCells` gives horizontal slices. Any polygons work: a grid for tiles, radial
  wedges for a pie burst, a single diagonal for a sword cut.
- **Copies are snapshots of the content at build time.** For content that changes (odometer, counter), pass
  `{ html: '10,935m' }` with the final text.
- The element must not sit inside an `overflow: hidden` box if pieces should fly out of it.
- Each copy is a full text layer: keep shards ≤ ~40. `motionBlur` multiplies that by its samples.

## 8. Glyph outlines: text_to_paths.mjs, pieces, deformers

```bash
node <skill>/scripts/text_to_paths.mjs <dir> --add hero --text "해연" --font pretendard --size 300 --weight 800 --align center
node <skill>/scripts/text_to_paths.mjs <dir>            # rebuild js/glyphs.js from glyphs.json (after edits)
node <skill>/scripts/text_to_paths.mjs <dir> --list
# options: --size --weight --tracking --line-height --align --step (px between ring points; 4–6 for 3D) --strokes
```

- Fonts: any installed SIL OFL 1.1 font, by catalogue id or family name (catalogue or Google Fonts `ofl/`, fonts.md),
  read from the project's own files (sha256 checked against the catalogue or `fonts.lock.json`).
  Variable Pretendard is instanced at `--weight`. A character the font lacks is an error; there is no fallback.
  Outline only the lines the video shows (OFL FAQ 1.1: outlines used for graphics and video titling are design
  use; never dump a character set). `check.mjs` and `check_fonts.mjs` verify provenance.
- `TX.glyphs(container, key, { by: 'piece'|'glyph', anchor: [0.5, 0.5], fill, stroke })`. An HTML container gets an
  SVG at its origin (`anchor` picks the point of the text block placed there). An `<svg>`/`<g>` is drawn into at
  `x, y`. The fill defaults to `currentColor`, so CSS `color` styles it.
- Pieces are an outer contour with its holes. Overlapping contours of a glyph are merged by default: Pretendard's
  variable outlines keep strokes as overlapping shapes, which would show as inner lines while drawing on,
  darker patches where fading pieces overlap, and seams on bevelled 3D. Merged, a Hangul piece is a jamo ("해연" →
  ㅎ ㅐ ㅇ ㅕ ㄴ), and assembling a syllable from its jamo is something only Korean type can do. `--strokes` keeps
  the overlapping strokes as separate pieces (finer debris) and accepts those artefacts. Look at the result with
  `--range`.
- `TX.deform(G, { from, to, fill }, (x, y, s, piece, unit) => [dx, dy])` bends every outline point (block coords;
  `piece.c` centroid, `piece.b` bbox). Unit channels (scatter, jelly…) still apply on top.
- `TX.shapes(key)` gives polygons (outer + holes, y up, centred) for three.js `ExtrudeGeometry`. Bevelled, lit
  3D type is in threejs-3d.md.
- `drawOn` uses DrawSVG; a morph between two outlines (`tl.to(path, { morphSVG: otherD })`) uses MorphSVG. Both
  are on `tl`, so they seek.
- fontkit's layout and the browser's can differ by about 1 px. Don't expect a glyph group to sit pixel-exact on
  DOM text; swap during motion or behind a flash.

## 9. Raster type: pixels, tiles, warps

```js
const R = await TX.raster('흩어지는 글자', { family: "'Pretendard'", weight: 800, size: 170, color: '#eaf7ff' });
const g = TX.tiles(R, { into: '#s13', x: 960, y: 520, size: 5 });   // own canvas in the scene, stage coords
TX.ripple(g, a, b);  TX.dissolve(g, at, { sweep: 0.8 });
```

- `raster` draws with an installed family (catalogue or Google Fonts `ofl/`, fonts.md) after loading exactly those
  glyphs. `check_fonts.mjs` fails if the family isn't installed or misses a character, because a canvas would
  silently use a system font. It also takes
  `gradient`, `stroke`, `tracking`, `lineHeight` and multi-line `\n`.
- Tiles at home are drawn as one image, so the text stays crisp until a tile moves. Moved tiles are drawn one by
  one (`mode: 'dot'` fills squares of the tile's colour, faster for 2–3 px particles).
- Cost grows with the number of moving tiles. In the gallery, size 5 over a full line had p95 ≈ 5 ms and dot tiles
  of size 3 peaked at 15 ms. Use size ≥ 4 for whole lines and measure with `--perf`.
- `TX.warp(g, { from, to, axis: 'x'|'y', strip: 2 }, (v, s) => offset)` shifts rows (axis x) or columns (axis y).

## 10. With the timeline, FXKit and 3D

- **Outer vs inner.** The timeline owns split's `G.outer` elements and the element itself. TypeFX owns the inner
  `.tx-i`, the clones and the paths. Never tween what TypeFX writes. Tweening the element (the group) moves
  everything together, copies included.
- Groups expose `G.state` for values to tween on `tl` (for example `extrude`'s `depth` and `angle`).
- Sell impacts with FXKit at the right place: `const [x, y] = TX.stageXY(el, 0.62, 0.55)` →
  `K.burst(x, y, at)`, `K.flash(at)`, `K.shake(row, at)`.
- Land effects on the stressed syllable (`cue('c03').when('산산조각')`). A break that lands after the word is
  wasted.
- 3D and light: bevelled, lit, extruded glyph outlines (threejs-3d.md); glowing or dissolving type with bloom and
  shaders (shader-fx.md).

## 11. Craft rules

- **Reading comes first.** The line must sit still and readable while it is spoken: hold ≥ 0.6–1 s before
  breaking it, or let it form first. Effects go around the reading moment, not in place of it.
- **One primary type effect per beat**, chosen because it says what the line says (§6). Keep breaks, shatters and
  dissolves for the moments that truly peak in the story. If everything breaks, nothing does.
- **Material consistency.** In a deep-sea piece, type sinks, floats, ripples, is crushed by pressure and lights
  up like bioluminescence. A neon sign or a glitch needs a reason.
- **Leftovers.** Shards and dust leave the frame or fade; don't leave a dirty frame for the next line.
- **Body text stays real text.** Use outlines and raster for display lines only.

## 12. Determinism, cost, verification

- Effects run in `onFrame` from closed forms of `t`. Randomness is `u.r(salt)` or `TX.m.hash`, never `Math.random`.
  Nothing carries between frames, and writers compare against what they last wrote (TypeFX owns those
  elements). A held effect reads `s.lt`/`s.p`, not `s.t`, unless it is `live` (§4).
- A group outside its windows is not redrawn — except after a window resize or fullscreen (F), when the player
  re-sizes the canvases (blanking raster tiles) and every group redraws at the current t.
- `snapshot.mjs --seekcheck` revisits every shot in reverse order and in a shuffled order and compares the picture
  (a screenshot hash, then the pixels; computed styles explain what changed). Run it on any piece with TypeFX or
  custom effects. It catches accumulated state; on the first real project it also found relative shakes leaving
  the camera a few px off after a seek.
- `render.py --screenshot --from a --to b --gapframe 3` across every break, swap and landing: one-frame pops (the
  swap from original to copies, a unit reset at a window edge) show up only there.
- `snapshot.mjs --perf`: JavaScript time per frame. Painting many large copies or blurred units also costs GPU
  time that headless Chromium doesn't measure, so watch the real playback once.
- `check.mjs` verifies `js/glyphs.js` provenance; `check_fonts.mjs` checks DOM glyphs, outline provenance and
  canvas-text coverage.
- Layout warnings ignore decorative copies (`[data-fx-copy]`), units of one group crossing each other, and units an
  effect is moving.

## 13. Pitfalls that were actually hit

| symptom | cause | fix |
|---|---|---|
| extrusion layers had the face's colour (blob letters) | the writer reset `color` to `''` after the first frame, wiping the tint | writers return to the inline rest state the representation set |
| shattered number showed "00,000m" | copies cloned the odometer's columns at build time | `shatter(el, at, { html: '10,935m' })` |
| `getVariation` crashed on Pretendard (WOFF2) in fontkit | fontkit's WOFF2 + variations path | text_to_paths decompresses WOFF2 (wawoff2) first |
| Pretendard outlines drew inner lines, fading pieces showed darker patches, bevels had seams | the variable font's overlapping contours | text_to_paths merges overlapping contours by default (1 px union, resampled rings); `--strokes` to opt out |
| `--seekcheck` passed a WebGL scene that wasn't deterministic | `toDataURL()` of a WebGL canvas reads a cleared buffer | WebGL canvases are compared from screenshots of their box |
| after scrubbing, a world/camera sat a few px off | relative `x: '+=10'` shakes read their base when first rendered | FXKit `shake()` is a closed-form offset on the CSS `translate` property |
| melt looked like nothing in a filmstrip | the ease puts most of the motion late in the window | shoot the whole window; `melt` now uses `power1.in` and uneven drips |
| swirl threw letters off-screen | radius grew outward | `radius` is the end radius (0 = centre) |
| `--seekcheck` flagged GSAP's lazy inline styles | raw DOM comparison | compare computed visible values (done in the tool) |
| fused text looked broken for half a second (reverse shatter) | slow `power3.out` settle | reverse uses `expo.out` |
| raster text vanished after resizing the window or pressing F, until its next effect | re-sizing a canvas blanks it, and a still group was never redrawn | the player passes `redraw` to `onFrame` after a refit; TypeFX redraws every group then |
| a neon sign stopped humming after it lit, and showed a different brightness at the same t depending on the seek path | the hum read `s.t` outside its window, where groups render only at window edges | neon keeps its window open (`to`); custom effects reading `s.t` while held use `live: true` |
