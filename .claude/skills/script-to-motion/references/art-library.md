# Illustration library — js/art modules

Read this when a piece needs more than a few shapes: characters, creatures, vehicles, machines, maps,
landscapes — anything you would otherwise inline as long SVG in `index.html` and animate from `scenes.js`.
Every module is drawn from scratch for this video: no traced, downloaded or imported artwork, icons or map data,
and no imitation of existing characters or a recognisable artist's style (SKILL.md → Originality).
Splitting each illustration into a module keeps `scenes.js` about *when and where* (the timeline) and the
module about *what it looks like and how it moves inside itself*. It also lets several workers draw in
parallel without touching the same file.

## Contents
1. Layout and loading
2. The module contract
3. Determinism and cost
4. Integrating a module into the timeline
5. Previewing a module on its own
6. Delegating illustrations to parallel workers
7. Pitfalls that were actually hit

---

## 1. Layout and loading

```
js/art/core.js        shared helpers (in every new project): ART.rand, ART.defs, ART.smooth, ART.f, ART.clamp, ART.lerp, ART.palette
js/art/<group>.js     one file per group of illustrations (vehicles.js, creatures.js, people.js, scenery.js …)
```
Load them with plain script tags **before** `js/scenes.js` (file:// — no modules):
```html
<script src="js/art/core.js"></script>
<script src="js/art/creatures.js"></script>
<script src="js/scenes.js"></script>
```

## 2. The module contract

```js
ART.whale = {
  build(el, opts = {}) {            // el: an existing <svg viewBox="…"> or <g> from index.html
    el.innerHTML = `…`;             // all markup; gradients/filters/symbols via ART.defs('prefix-id', markup)
    const tail = el.querySelector('.tail');
    return {
      animate(t, state = {}) {      // pure function of t (+ state): only sets attributes/styles of its own nodes
        tail.setAttribute('transform', `rotate(${ART.f(8 * Math.sin(t * 2.1))} 760 130)`);
      },
    };
  },
};
ART.fishSymbol = () => ART.defs('crB-fish', '<symbol id="crB-fish" viewBox="-24 -10 48 20">…</symbol>');   // for swarms via <use>
```
- **Coordinate contract.** The container (its `viewBox`, or the `<g>` origin) is fixed by the timeline. Write
  down the anchors the timeline relies on — e.g. "lamp lens at (−178, 29)", "skid bottom y = 72", "finger nail
  top y = 690" — and keep them. Classes the timeline tweens (`.rays`, `.cracks`, `.merc`, `.dlines`) are part of
  the contract too: keep them, with the same element types (DrawSVG needs stroked paths; no dasharray).
- **Ids** are global in the document: prefix every id per file (`vehA-`, `crB-`, …) and register shared defs
  once with `ART.defs(id, markup)` (it creates a hidden `<svg id="art-defs">`).
- **Outer vs inner motion.** The timeline owns the container's position/scale/opacity (its `transform`,
  `autoAlpha`); the module owns everything inside. Never both on the same node.
- **Canvas helpers** for crowds (hundreds of items per frame) are plain functions:
  `ART.drawPerson(ctx, x, y, h, color, variant)`, `ART.drawBubble(ctx, x, y, r, a)` — ≤ 4 path ops each.

## 3. Determinism and cost

- `animate(t, state)` must give the same DOM for the same `t` and `state`, whatever was called before:
  no `Math.random`/`Date`/timers, no values accumulated across calls, no "write only if it changed" cache that
  can skip a needed write after a seek. Procedural detail (rocks, rivets, spots) comes from `ART.rand(seed)` in
  `build()`. `preview_art.mjs` checks this.
- Budget: ≤ ~40 attribute writes per module per frame; path re-computation of a few small paths is fine.
- No SVG blur filters on anything that changes per frame (repaint cost); glows are radial gradients whose
  radius/opacity you animate. Static filters on static parts are acceptable.
- Text inside art: catalogue fonts only (`font-family="Pretendard"` etc. — SKILL.md → Fonts).
- Keep each module under ~400 nodes.

## 4. Integrating a module into the timeline

```js
// scenes.js — build before any tween targets the module's parts
const A = {};
A.whale = ART.whale.build(document.querySelector('#s07 .whale'));
A.sub = ART.sub.build(document.querySelector('#s07 .subm svg'));
onFrame((t) => {                                   // animate only while the scene is on screen
  if (t >= cue('c18').start - 2 && t <= cue('c19').end) A.whale.animate(t);
  A.sub.animate(t, { lamp: S.beam, streak: S.streak });
});
tl.fromTo('#s07 .whale', { x: 1500 }, { x: -60, duration: 4.4, ease: 'none' }, 'c18-=0.6');   // outer motion
```
- Guard per-scene `animate` calls with time ranges; dozens of modules animating off-screen add up.
- Feature-detect when a module is optional (`if (ART.whale) …`) so a missing file fails soft in smoke tests.

## 5. Looking at a module on its own

Look with render.py — the only way any picture is looked at (SKILL.md → Looking at the picture):
```bash
python3 <dir>/render.py <dir> --screenshot --art sub --viewbox "-200 -130 400 260" --state '{"lamp":1}' --at 0,0.6,1.2
python3 <dir>/render.py <dir> --screenshot --art bag --viewbox "-160 -190 320 400" --group --at 0,1   # container is a <g>
python3 <dir>/render.py <dir> --screenshot --art sub --viewbox "-200 -130 400 260" --at 0.6 --res 4k  # detail: 1600 px wide
```
render.py builds the page in memory (the project's `js/art/core.js` + every module, its fonts, a plain `--bg`), builds the
module, poses it with `animate(t, state)` at each `--at` time and films it the way it films the video. Open the sheet;
look at two or three `t` values and each state (lamp off/on).

Check it with preview_art.mjs — console errors and determinism (the DOM state after returning to the first `t`); it
writes no picture and prints the render.py command above for the same module:
```bash
node <skill>/scripts/preview_art.mjs <dir> ART.sub --viewbox "-200 -130 400 260" --state '{"lamp":1}' --t 0,0.6,1.2
```
Never write a page or a script of your own to photograph a module.

## 6. Delegating illustrations to parallel workers

Several workers can draw at once when each owns **one file** (`js/art/<group>.js`) and nobody else edits it.
Give every worker a brief with:
1. scope — the one file it may write, the files it must not touch, a scratch folder for tests;
2. the contract per element — container + viewBox, anchors, classes to keep, `animate` state keys;
3. style — palette, light direction, level of detail, "readable at 1080p, not noisy";
4. the rules of §3 and the id prefix;
5. the verification commands — `preview_art.mjs …` (errors, determinism) and `render.py --screenshot --art …` (the one
   way to look) — with "open the sheet, iterate", and SKILL.md's "Looking at the picture" section word for word: no
   screenshot code, no other images (a worker may not inherit the skill's hook);
6. the report format — API per element, contracts kept, anything the integrator must change.
Integrate after all reports: replace inline art with empty containers, `build()` before tweens, delete the
old per-element motion code the modules now own, then `check` / `smoke` / `snapshot`.

## 7. Pitfalls that were actually hit

| symptom | cause | fix |
|---|---|---|
| a weight drifted 4 px off its rope after scaling | GSAP scaled an SVG `<g>` around its bbox top-left | bake scale into the markup or set `svgOrigin` (player-api.md §4) |
| a pressure "bulge" beside a finger read as ears | procedural detail detached from the silhouette | effects must hug the shape; look closer with `--res 4k` (`--crop` on the spot) |
| cartoon clouds with outline arcs and flat bases | hand-drawn outline shapes for something soft | soft puffs (radial gradients) piled irregularly, no outlines |
| pixel-diff "non-determinism" with identical DOM | Chromium repaints only changed regions | compare DOM state, not pixels (`preview_art.mjs` does) |
| `addColorStop of undefined` only in smoke tests | old jsdom canvas stub | fixed in smoke.mjs; keep `if (!g)` guards cheap |
