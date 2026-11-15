# FX kit — reusable, seekable effects (js/fxkit.js)

A small library of the effects that carried a full production (the deep-sea explainer): particle bursts,
lens flares, sonar pings and the ping wipe, SFX words, light leaks, punch zooms, rolling-digit odometers,
glints, scramble kickers, write-on labels. Every effect is scheduled on `tl` or drawn in `onFrame(t)` from
closed-form formulas, so seeking, scrubbing and repeated recordings always show the same frame.

## Contents
1. Enable it
2. Craft rules: when to use what
3. API
4. Determinism contract
5. Pitfalls that were actually hit

---

## 1. Enable it

New projects already contain `js/fxkit.js` and `css/fxkit.css` (template). Link them in `index.html`:

```html
<link rel="stylesheet" href="css/fxkit.css">     <!-- after css/player.css -->
<script src="js/fxkit.js"></script>               <!-- after js/player.js, before js/scenes.js -->
```

```js
Video.define((ctx) => {
  const { tl, cue, scene } = ctx;
  const K = FXKit.install(ctx, { accent: '89,243,224' });   // creates its canvas + layers inside #stage
  K.burst(960, 540, cue('c03').when('폭발'), { n: 40, speed: 500 });
});
```

`install(ctx, opts)` options: `accent` (rgb triplet `'r,g,b'`, default `'89,243,224'` cyan — sparks, flare ghosts, the
ping wipe's sparks and the rings' default colour), `zRings` 31, `zCanvas` 32, `zOver` 34 (SFX + leaks), `zFlash` 60.
Give your persistent HUD layers a z-index above these if they must stay on top.

Colours: FXKit does **not** read your `--accent` token — pass it in yourself if the effects should match the palette:

```js
const hex = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();     // '#ff5a36' (6-digit hex)
const K = FXKit.install(ctx, { accent: [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(',') });   // '255,90,54'
```

(`accent` must be an `r,g,b` triplet.) Without it the effects stay cyan whatever the palette. Per call: `burst(…, { color:
'r,g,b' })`, `ring(…, { color })`, `pingWipe(…, { color, rgb })`. Per element (CSS): `--fxkit-ring` (ring border),
`--fxkit-sfx` (SFX word colour; falls back to `--accent-2`, then orange), `--fxkit-odo-glow` (odometer filter).

## 2. Craft rules: when to use what

One **primary** effect per beat, chosen because it says what the line says (motion-design.md §12). The impact
kit (burst + flash + shake + punch) belongs only on the moments that truly peak in the story, not everywhere and not to fill a count. This user prefers it
calm: no expanding rings, flashes ≤ 0.08 peak over ≥ 0.7 s, and no punch zoom at all (references/craft-notes.md) — the
Kling video overrode `K.flash` and `K.ring` at install for that.

| effect | use it for | avoid |
|---|---|---|
| `burst` spark / ember | a reveal, an arrival, a number landing; embers for heat, volcanoes, danger | every entrance (noise) |
| `burst` bubble / dust / debris | underwater moves, landings on a floor, impacts on a surface | dust in mid-water with no floor |
| `burst` converge | light gathering into a logo, a dot, a final symbol | — |
| `burst` warp | zoom-through transitions, sudden speed | static holds |
| `ping` / `pingWipe` | the signature section change (sonar, radar, ripples, detection) | more than one transition family per piece |
| `flare` / `flareSource` | a light source **a lens would see**: the sun in the sky, a lamp facing camera, a hero glow | underwater or "inside" a scene with no camera logic (reads as a cross on nothing) |
| `leak` | a soft scene change, a warm/cool mood turn | over text that must be read |
| `sfx` | a comic beat: 쿵!, 콩!, 휙! at a physical impact | serious/sad lines |
| `punch` (0.02–0.05) | the single hit of a big beat | more than ~10 per 3 minutes |
| `shake` (6–12 px) | an impact on that element / scene | text that must stay readable for long |
| `odometer` / `rollTo` | hero numbers that count (depth, money, years) | numbers that don't change |
| `glintOver` | the moment a hero number or title settles | moving text |
| `kick` | mono kickers / codes / coordinates (deterministic scramble) | Korean body text |
| `wipe` | labels and captions-as-design that write on | headlines (use `chars`) |
| `chars` | kinetic headlines (SplitText, masked rise) | long body text (> ~250 chars) |

For type that does more than rise in — shatters, melts, ripples, jiggles, assembles from jamo, dissolves, glows,
turns solid — use TypeFX (`type-fx.md`); FXKit's flash, burst and shake sell its impacts.

## 3. API

Every position (`pos`, `t0`, `drift`'s `from`/`to`) may be timeline seconds or a cue label — `'c03'`, `'c03+=0.2'`,
`'c03_end-=0.4'` (resolved to seconds first, so effects that add their own offsets land on the cue, not at the end of
the timeline). Anchor them to cues (`'c04'`, `cue('c04').when('단어') - 0.1`). Relative GSAP positions (`'<'`, `'+=1'`)
have no fixed time: the effects that add offsets refuse them with an error. Coordinates are stage px.

| call | does |
|---|---|
| `inn(target, pos, from = {y:40}, dur = .8, ease)` / `out(target, pos, to = {y:-30}, dur = .45)` | fromTo entrance to neutral / exit to hidden |
| `chars(sel, pos, { stagger, dur, from, mask = 'chars' })` | SplitText rise; **moves any text-shadow to a drop-shadow filter first** (§5) |
| `flash(pos, { peak = .3, dur = .45, color })` | full-frame flash (to→to pair) |
| `shake(target, pos, { amp = 10, dur = .55, wiggles = 7 })` | decaying wiggle written to the CSS `translate` property (closed form of t): composes with any x/y tween of the same element and is exact after any seek |
| `addOffset(el, t => [dx, dy] \| null)` | add your own closed-form offset to that `translate` channel (shakes and `handheld` share it) |
| `at(pos)` | a position (seconds or cue label) → seconds, as every FXKit call resolves it |
| `drift(sel, from, to, s = 1.035)` | slow push-in that keeps a hold alive |
| `counter(node, obj, key, format)` | writes `format(obj[key])` each frame (only on change) |
| `kick(sel, pos, { dur, chars, fps })` / `wipe(sel, pos, { dur })` | scramble-decode (pure function of t, no plugin) / clip-path write-on |
| `odometer(node, sample, { decimals, mono })` → `set(v)` | builds rolling digit columns from `sample` (e.g. `'10,935'`); call `set(v)` in onFrame |
| `rollTo(node, pos, { from, to, dur, ez, sample, decimals })` → `{v}` | odometer + tween in one call |
| `glintOver(node, pos, { text, html, dur })` | light sweep over a settled number/title (pass the **final** text for odometers) |
| `ring(x, y, pos, { size, dur, color, width, flat })` / `ping(x, y, pos, { n, gap, … })` | expanding circle(s); `flat` = surface ripple |
| `pingWipe(sel, x, y, pos, { dur, color, rgb, sparks })` | reveals scene `sel` through an expanding circle + rings + spark ring + warp lines; schedule `scene(sel, pos, …)` with the same `pos` |
| `burst(x, y, t0, { kind, n, speed, dir, spread, life, size, g, drag, color, area, areaY, delay, seed })` | particles: `spark` `ember` `bubble` `dust` `debris` `converge` `warp` |
| `flareSource({ x, y, len, tint })` → `{k}` | a controllable lens flare; x/y may be functions of t; tween `k` 0..1 on tl |
| `flare(x, y, pos, { peak, hold, dur, len })` | one-shot flare |
| `sfx(text, x, y, pos, { rot, color, size, dur })` | outlined comic word pop |
| `leak(pos, { warm, from, to, y, dur, peak })` | light leak sweep |
| `punch(pos, amt = .035)` | zoom kick on every scene (CSS `scale`) |
| `handheld({ amp = 4, skip: ['#s07'] })` | gentle handheld drift on every scene (CSS `translate`) |
| `sprite(rgb)` | a soft round 128px glow sprite (canvas) for your own drawing |

```js
const K = FXKit.install(ctx);
scene('#s03', cue('c04').start - 0.4, cue('c07').start);
K.pingWipe('#s03', 960, 540, cue('c04').start - 0.4);                 // signature transition
const hit = cue('c09').when('1만m');
K.burst(1250, 800, hit, { n: 50, speed: 620 });                        // impact kit, on a moment that truly peaks
K.flash(hit, { peak: 0.15 }); K.punch(hit, 0.04); K.shake('#s04 .chart', hit, { amp: 8 });
K.rollTo('#s04 .num .v', hit - 0.6, { to: 10935, dur: 1.3 });
K.glintOver('#s04 .num', hit + 0.6, { html: '10,935<span class="u">m</span>' });
const sun = K.flareSource({ x: (t) => 1180 - 20 * t, y: 300 });         // follows the sun disc's own formula
tl.fromTo(sun, { k: 0.85 }, { k: 0, duration: 1.2 }, cue('c01').end);
```

## 4. Determinism contract

- Particles are closed-form: `pos = origin + v·(1 − e^(−drag·a))/drag + ½·g·a²` with `a = t − t0`. Nothing
  accumulates between frames, so any seek is exact. Seeds come from `ctx.rand` (a per-call counter, or `seed`).
- Transient DOM effects are to→to pairs or `fromTo(…, { immediateRender: false })` — both restore their start
  state when the playhead moves back before them (verified in both directions).
- No `Math.random`, `Date`, timers, `requestAnimationFrame`, CSS transitions, or `display` toggling (the
  odometer hides unused digits with width/opacity).
- Verified pixel-identical: the same t rendered after a forward seek and after seeking back from the end
  (0 differing pixels across bursts, flares, ping wipe, odometer, scramble, SFX, leaks).
- The canvas clears only when something was drawn and skips idle frames; sprites are pre-rendered once.
- jsdom (smoke.mjs) has no real canvas: sprite creation returns `null` there and drawing is skipped.

## 5. Pitfalls that were actually hit

| symptom | cause | rule |
|---|---|---|
| faint coloured rectangles behind each character/digit | `text-shadow` on text inside a clipping box (SplitText `mask`, odometer columns) is cut per box | glow = `filter: drop-shadow()` on the wrapper; `chars()` and `.fxkit-odo` do this; drop-shadow blur ≈ 0.4 × the text-shadow blur |
| a number shows a half-rolled digit at rest (10,935 with a 0/1 between) | carry started before the lower digits reached 9 | the odometer carries a column only while every lower digit passes 9 |
| the screen jumps to another station during a shake | absolute shake values on an element whose `y` is also tweened | shake on a separate channel (CSS `translate`), never on the tweened x/y |
| after scrubbing, the world sat 3–5 px off its place | relative `x: '+=10'` shakes read their base when first rendered; after a seek that base is another moment of the moving camera (`--seekcheck` found it) | `shake()` is now a closed-form offset on `translate`; don't tween relative values on moving elements |
| a cross-shaped light where the sun "was" underwater | a lens flare drawn where no lens sees a light | flares only for visible light sources; underwater use a soft glow sprite instead |
| halo and flare drift away from the sun during a camera move | each element computed its own position formula | attach the flare to the source's own formula (`x/y` functions) or put it in the same group |
| punch zoom fighting a scene's own transform | both written to `transform` | `punch`/`handheld` use the separate CSS `scale`/`translate` properties |
| a flash on `'c03'` lit up at c03 and never faded; the fade landed at the very end of the video | `'c03' + 0.05` is the string `'c030.05'`, an unknown label GSAP places at the end of the timeline | every FXKit call resolves its position with `at()` before adding offsets; do the same in your own helpers (`K.at(pos) + 0.2`) |
| a kicker shows different letters at the same t after each seek | GSAP's ScrambleTextPlugin picks its random characters with `Math.random` | `kick()` scrambles from a hash of (char index, frame) — a pure function of t; avoid `scrambleText` on `tl` |
