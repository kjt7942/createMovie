# Shader FX — light, focus, particles and transitions on the GPU

The FX build turns a scene's WebGL canvas into a post-processed picture: glowing heroes, light rays on the
peak word, a focus pull to the object the narration names, a dissolve shaped like the next scene, tens of
thousands of particles forming a structure. Same player, same clock: everything is a function of the playhead `t`.

Ported from the `script-to-motion-graphics` skill, where every effect below was rendered and pixel-checked
(three r186, WebGL2 backend, headless Chromium, SwiftShader). Here they were re-checked through the classic
FX bundle from `file://`: 21/21 render, determinism exactly as classed in §3.

## Contents
1. When to use it
2. Enable, StageFX API
3. One clock — determinism classes A / A* / B / C
4. Effect catalog
5. Recipes for the craft beats (motion-design.md §12)
6. GPU particles
7. Type, layers, transparency
8. Cost and recording
9. Pitfalls that were actually hit
10. Rebuilding the bundle
11. Glowing / dissolving type

---

## 1. When to use it

| the beat needs | use |
|---|---|
| headlines, labels, charts, SVG, kinetic type | DOM/SVG + GSAP (player-api.md) — always the type layer |
| a modelled object that turns/opens/assembles | classic 3D: `Stage3D` (threejs-3d.md) — or FX if it should also glow, blur, ray |
| light as meaning: glow, rays, flare, focus, reflections; particle formations; shaped 3D transitions | **FX build: `StageFX`** |
| a few hundred dots/lines | canvas 2D in `onFrame` (player-api.md §5) — cheaper than FX |

A project uses one three.js build. `enable_3d.mjs <dir> --fx` (or `new_project.mjs … --fx`) installs the FX build;
`--fx` on a classic project switches it (Stage3D code must move to `await StageFX.create`). Without `--fx`,
`enable_3d.mjs` leaves an FX project as it is (switching back takes `--classic`); `embed_glb.mjs` works with either build.

## 2. Enable, StageFX API

```html
<canvas id="gl"></canvas>        <!-- persistent layer in #stage, or inside a scene; CSS: #gl { position:absolute; inset:0 } -->
```

```js
Video.define(async ({ tl, cue, scene, onFrame, W, H }) => {            // async: the renderer initialises first
  const fx = await StageFX.create(document.getElementById('gl'), {
    W, H, fov: 35,
    background: '#05070c',      // a colour (default '#000000'): effects need an opaque canvas — see §7
    environment: true,          // RoomEnvironment light for PBR / GLB materials
    mrt: ['emissive'],          // extra attachments the chosen effects need: 'emissive' 'normal' 'metalrough' 'velocity'
    shadows: false,             // true for godrays (castShadow light)
  });
  const { THREE: T, TSL, FX } = fx;    // THREE = WebGPU build (node materials), TSL nodes, FX = post-processing nodes
  // fx.scene, fx.camera, fx.renderer, fx.pipeline, fx.uTime (= playhead in shaders)
  // fx.beauty, fx.depth, fx.viewZ, fx.emissive / fx.normal / fx.metalrough / fx.velocity (when requested in mrt)
  fx.output = FX.smaa(fx.beauty.add(FX.bloom(fx.emissive, 1.2, 0.4, 0)));   // the effect chain (default: smaa(beauty))
  onFrame((t) => { /* copy tweened values into the scene */ fx.render(t); });
});
```

| member | |
|---|---|
| `fx.render(t)` | fits the canvas resolution, sets `fx.uTime = t`, runs registered computes (twice), renders the chain |
| `fx.output = node` | the final node. Wrap your chain in `FX.smaa(…)` yourself (renderer antialias is off) |
| `fx.addCompute(node)` | a stateless compute `f(index, uTime)`; runs twice per frame (WebGL2 shows compute one frame late) |
| `await fx.textTexture(text, { font, color })` | `{ texture, aspect }` — text in 3D; loads the glyphs first (§7) |
| `fx.backend` | `'WebGL2'` (verified) or `'WebGPU'` (`?fxbackend=webgpu`, not verified) |
| `StageFX.loadGLB(name)`, `.mixer(gltf)`, `.byName(gltf, name)` | as Stage3D (GLBs embedded by embed_glb.mjs; `mixer.setTime(t)`) |

Materials are node materials: `MeshStandardNodeMaterial`, `MeshPhysicalNodeMaterial`, `MeshBasicNodeMaterial`,
`SpriteNodeMaterial` with `colorNode`, `emissiveNode`, `positionNode`, `opacityNode`, `scaleNode`. GLB materials
are converted automatically. Plain `MeshStandardMaterial` also renders.

## 3. One clock — determinism classes

The player sets `t` every frame; snapshots seek. Shaders must therefore read **`fx.uTime`** only. TSL's built-in
`time` / `deltaTime` / `frameId` run on `performance.now()` and keep moving while paused or seeking.

| class | meaning | measured (seek t=1→3→1 / two fresh sequential runs) | rule |
|---|---|---|---|
| **A** | pure function of t | identical / identical | use freely |
| **A\*** | A under a condition | identical / identical | keep the condition (catalog) |
| **B** | reads an internal clock | **differs / differs** | **forbidden** — `film()` is not even in the build; use the grain recipe |
| **C** | keeps frame history | **differs** / identical | fine in the recording (continuous playback from the start); snapshot stills and debug scrubbing show it approximately |

C detail: `afterImage`, `motionBlur`, `traa` did not become bit-exact after a seek even with 1–90 warm-up frames
(history render targets have no reset; velocity's previous matrices follow `frameId`). Two fresh runs played
in order were identical. Use C effects where the trail/blur reads as motion, and judge them on render.py sheets at `--gapframe 1`
(frames filmed in order), not from single seeks.

Also replace, when porting official examples: `oscSine(time)`, `Math.random()`, `scanlines(…, speed > 0)`.
`check.mjs` flags TSL `time`, `film(`, non-awaited `StageFX.create` / `textTexture`, `renderer.render`,
direct `renderer.compute`, class-C nodes, and a missing `fx.render(t)`.

## 4. Effect catalog

`ms` = relative cost at 960×540 on the software renderer, frame presented (from motion-graphics' probe). GPU is
far faster; the ratios hold. 1080p costs ~2–3.5×.

| effect | class | ms | call (`FX.…`, inputs) | notes |
|---|---|---:|---|---|
| base | A | 60 | `fx.beauty` | |
| bloom | A | 71 | `fx.beauty.add(FX.bloom(fx.emissive, strength, radius, threshold))` | selective via emissive MRT; `FX.bloom(fx.beauty, .8, .3, .9)` for HDR highlights. Half-res internally |
| chromaticAberration | A | 55 | `FX.chromaticAberration(n, strengthU, TSL.vec2(.5,.5), 1.1)` | subtle at 1.0 — spike it on a word |
| rgbShift | A | 55 | `FX.rgbShift(n, 0.006, angle)` | |
| gaussianBlur | A | 116 | `FX.gaussianBlur(n, radius, sigma, { resolutionScale })` | |
| hashBlur | A | 118 | `FX.hashBlur(n, TSL.float(0.02))` | |
| radialBlur | A | 88 | `FX.radialBlur(TSL.convertToTexture(n), { count: TSL.int(32), exposure: TSL.float(1) })` | light rays; default exposure 5 blows out |
| dof | A | 195 | `FX.dof(n, fx.viewZ, focusU, focalLength, bokehU)` | world units; uniforms → focus pulls on `tl` |
| transition | A | 67 | `FX.transition(fx.beauty, TSL.pass(sceneB, cam), TSL.texture(mask), mixU, threshold, 1)` | **mix 1 = A, 0 = B**; both scenes render that frame |
| lensflare | A | 202 | `FX.lensflare(bloomNode, { threshold })` → `FX.gaussianBlur(flare, 8)` | input is the bloom result |
| outline | A | 63 | `FX.outline(fx.scene, fx.camera, { selectedObjects, edgeThickness })` | add `visibleEdge × colour` to beauty; the official pulse uses `time` → use `fx.uTime` |
| godrays | A | 75 | `FX.depthAwareBlend(b, FX.godrays(fx.depth, cam, light).getTextureNode(), fx.depth, cam, {…})` | `shadows: true`, light `castShadow`; needs occluders |
| ssr | A | 138 | `b.add(FX.ssr(b, fx.depth, fx.normal, { metalnessNode: fx.metalrough.r, roughnessNode: fx.metalrough.g }).rgb)` | mrt `normal`, `metalrough` |
| ao (GTAO) | A | 87 | `FX.ao(fx.depth, fx.normal, fx.camera)` | subtle contact shadow on lit surfaces |
| sobel · sepia · sharpen · dotScreen | A | 41–56 | `FX.sobel(n)` … | dotScreen turns dark scenes white |
| pixelationPass | A | 29 | `FX.pixelationPass(scene, cam, 6, .3, .4)` | its own pass |
| scanlines + vignette | A* | 59 | `FX.vignette(FX.scanlines(n.rgb, .3, count, TSL.float(0)), .5)` | speed 0 |
| fxaa | A | 60 | `fx.pipeline.outputColorTransform = false; FX.fxaa(TSL.renderOutput(n))` | sRGB input |
| smaa | A | 71 | `FX.smaa(n)` | the default AA |
| grain | A | 48 | §5 | replaces film() |
| particles (TSL) | A | 495 | `SpriteNodeMaterial.positionNode = f(instanceIndex, fx.uTime)` | 20k additive sprites; overdraw is the cost |
| particles (compute) | A* | 617 | `fx.addCompute(Fn(…)().compute(N))` | runs twice per frame |
| text in 3D | A | 49 | `await fx.textTexture('…')` | |
| motionBlur | **C** | 162 | `FX.motionBlur(b, fx.velocity)` | mrt `velocity`; real per-pixel motion blur |
| afterImage | **C** | 53 | `FX.afterImage(n, damp)` | trails, not motion blur |
| traa | **C** | 66 | `FX.traa(b, fx.depth, fx.velocity, cam)` | temporal AA |

## 5. Recipes for the craft beats (motion-design.md §12)

Plan **one primary effect per beat** (plus one or two supporting); the effect must say something the narration says.

```js
const { uniform, float, vec4, rand, fract, floor, uv, mix, convertToTexture, int } = TSL;
const k = { glow: 0, slam: 0, rays: 0, bokeh: 0, grain: 0 };          // tweened on tl, copied in onFrame
const uGlow = uniform(0), uSlam = uniform(0), uRays = uniform(0), uBokeh = uniform(0), uGrain = uniform(0);
const focused = FX.dof(fx.beauty, fx.viewZ, uniform(4), float(3), uBokeh);
const lit = convertToTexture(focused.add(FX.bloom(fx.emissive, uGlow, 0.4, 0)));
const rays = mix(lit, FX.radialBlur(lit, { count: int(32), exposure: float(1) }), uRays);
const slam = FX.chromaticAberration(rays, uSlam, TSL.vec2(0.5, 0.5), float(1.1));
const n = rand(fract(uv().add(floor(fx.uTime.mul(60)).mul(0.1271))));        // grain locked to the frame number
fx.output = FX.smaa(vec4(slam.rgb.add(n.sub(0.5).mul(uGrain)), 1));
onFrame((t) => { uGlow.value = k.glow; uSlam.value = k.slam; uRays.value = k.rays; uBokeh.value = k.bokeh; uGrain.value = k.grain; fx.render(t); });
```

- **Glow on the hero word/object** — `emissiveNode` on the hero only + `bloom(fx.emissive)`; tween `k.glow` 0 → 1.4 →
  0.6 at `cue(id).when('…') - 0.1`. Background stays clean (selective bloom).
- **Impact slam** (warning word, big number) — `k.slam` 0 → 3 → 0 in ~0.35 s on the word, plus a 2–4 px DOM camera shake.
  One or two per video; never full-frame flashes (W3C flash thresholds).
- **Light rays as a transition** — `k.rays` up to 0.5 over 0.5 s before the cut, down after: the bright centre becomes
  the next scene's focal point (a position match cut).
- **Focus pull to what is named** — `uniform` focus distance tweened to the named object's distance; `k.bokeh` 0 → 2.5.
  Keep DOM headlines out of it (they sit above the canvas, always sharp).
- **Shape-mask transition between two 3D scenes** — `FX.transition(fx.beauty, TSL.pass(sceneB, cam), TSL.texture(mask), uMix, 0.15, 1)`
  with `mask` = a CanvasTexture of the shape that links the scenes (a circle, the logo, a word); tween `uMix` 1 → 0.
- **Lens character** — `lensflare(bloom)` on one hero shot; `vignette` + `grain` as a quiet finish.
- **Data as light** — counters/bars stay DOM; the GPU adds a glint: a bright emissive bar edge + bloom.

## 6. GPU particles

Formation model (seekable): per particle `A` (start), `B` (target), delay `d` from `hash(instanceIndex + k)`;
`q = smoothstep(clamp((uTime − tStart − d) / dur))`; `pos = mix(A, B, q) + wobble(uTime) · (1 − q)`.
Feed cue times as uniforms (`uniform(cue('c02').start)`) so a narration re-take re-times the particles too.

```js
const { instanceIndex, hash, float, vec3, cos, sin, clamp, mix, smoothstep, shapeCircle, uniform, color } = TSL;
const N = 20000, h = (k) => hash(instanceIndex.add(k)), tGather = uniform(cue('c02').start);
const A = vec3(h(1), h(2), h(3)).sub(0.5).mul(14);
const ang = h(4).mul(6.283), B = vec3(cos(ang).mul(2.4), sin(ang).mul(2.4), 0);          // ring; or points sampled from a logo
const q = smoothstep(0, 1, clamp(fx.uTime.sub(tGather).sub(h(5).mul(1.2)).div(2.2), 0, 1));
const m = new T.SpriteNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending });
m.positionNode = mix(A, B, q); m.colorNode = color(0x7fc8ff); m.opacityNode = shapeCircle().mul(0.8); m.scaleNode = float(0.05);
const pts = new T.Sprite(m); pts.count = N; pts.frustumCulled = false; fx.scene.add(pts);
```

Targets from a shape: sample points from an SVG path/logo or rasterised text at build time into a
`TSL.instancedArray`/`attributeArray`. Accumulating simulations (reading last frame's velocity) are class C.

## 7. Type, layers, transparency

- **Readable text stays DOM above the canvas** (SplitText, highlights, captions) — sharp at 4K, untouched by blur/CA.
- **Effects need an opaque canvas.** SMAA and the post nodes write alpha 1, and glow cannot blend correctly over DOM
  (measured: with `background: null` the DOM shows through only for the raw beauty pass). So give `StageFX` the
  scene's background colour and put the art-direction background in the WebGL scene (colour, gradient plane,
  particles). `background: null` → transparent canvas, output = raw `fx.beauty` (no post).
- **Text in 3D**: `await fx.textTexture('질서의 탄생', { font: '700 120px Pretendard' })`. The await matters: web fonts
  split by unicode-range load only glyphs the page has used — without it the canvas drew tofu boxes (measured).

## 8. Cost and recording

The user records the screen in real time, so a dropped frame is in the video. Budget for the recording machine:

- One heavy effect per beat (dof, lensflare, ssr, godrays, ≥20k particles). Lower internal resolution first
  (`bloom` is half-res by default; `gaussianBlur({ resolutionScale })`; `fx.pass.setResolutionScale()`).
- The canvas renders at the on-screen resolution × DPR, capped at 2× for FX (`maxPixelRatio`). For a slow machine:
  record with `?fxq=0.75` (or 0.5) — a lower canvas resolution, same picture otherwise. Never change quality mid-take.
- Hide FX scenes you're not in (`scene()` visibility) and skip `fx.render` when the canvas is hidden for long stretches.
- `snapshot.mjs --perf` shows JS time per seek; GPU time can't be measured without a GPU — ask the user to play the
  FX beats once at full screen before recording, and mention `?fxq` in the hand-off.

## 9. Pitfalls that were actually hit

| symptom | cause | fix |
|---|---|---|
| WebGPU "initialised" but black, hashes identical | software WebGPU adapter → device lost | FX forces WebGL2; `?fxbackend=webgpu` is experimental |
| canvas text shows ☐ for some syllables | glyph subsets not loaded | `await fx.textTexture` (it calls `document.fonts.load`) |
| DOM background doesn't show through the FX canvas | post nodes write alpha 1 | opaque `background`, backdrop inside WebGL |
| compute particles one frame behind | WebGL2 transform-feedback ping-pong | `fx.addCompute` (runs twice) |
| transition never shows scene B | mixRatio 1 = A | tween 1 → 0 |
| grain/pulse moves while paused | TSL `time` | `fx.uTime` |
| godrays fog the whole frame | no occluders / shadows off | `shadows: true`, light `castShadow`, objects between light and camera |
| GTAO "does nothing" | multiplied onto a dark scene | lit surfaces; or feed lighting via `TSL.builtinAOContext` |
| radialBlur white-out | default exposure 5 | `exposure: TSL.float(1)` |
| `const color = …` TDZ error | shadowing a TSL import | keep TSL names and locals apart |

## 10. Rebuilding the bundle

`assets/three/three.fx.bundle.min.js` is built from `three.fx.bundle.entry.js` (three 0.186.1) with esbuild: format
`iife`, minify, `legalComments: 'eof'`, target es2020, and a plugin that resolves only the bare `three` to
`three/webgpu` (addons import `three`; an alias would also rewrite `three/tsl`). Add an addon by importing it in
the entry and putting it on `FX`. After a rebuild, re-check every effect you rely on with `render.py --screenshot`.

## 11. Glowing / dissolving type

Two recipes tested in the FX build (WebGL2, SwiftShader): extruded glyph outlines with an emissive light band,
and a text texture that ripples and then burns away. Both are class A (uniforms copied from `tl` values + `fx.uTime`);
stills shot in two different seek orders were byte-identical.

**(a) Glowing solid letters with a light sweep.** Outlines from `TX.shapes(key)` (threejs-3d.md §7 has `toShape`),
node materials whose emissive feeds selective bloom:

```js
const { uniform, float, color, abs, smoothstep, positionLocal } = TSL;
const geo = new T.ExtrudeGeometry(TX.shapes('hadal').map(toShape),
  { depth: 0.5, bevelEnabled: true, bevelThickness: 0.06, bevelSize: 0.035, bevelSegments: 3, curveSegments: 1 });
geo.translate(0, 0, -0.25);
const uGlow = uniform(0), uSweep = uniform(-6), uBloom = uniform(0.5);
const band = smoothstep(float(0.9), float(0), abs(positionLocal.x.sub(uSweep)));      // 1 at the band centre (world units)
const faceM = new T.MeshStandardNodeMaterial({ color: 0x0b2c44, roughness: 0.35, metalness: 0.4 });
faceM.emissiveNode = color(0x59f3e0).mul(uGlow.add(band.mul(2)));
const sideM = new T.MeshStandardNodeMaterial({ color: 0x061a2a, roughness: 0.5, metalness: 0.6 });
sideM.emissiveNode = color(0x59f3e0).mul(band.mul(0.6));
fx.scene.add(new T.Mesh(geo, [faceM, sideM]));                                       // groups: 0 caps, 1 sides
fx.output = FX.smaa(fx.beauty.add(FX.bloom(fx.emissive, uBloom, 0.45, 0)));
const k = { glow: 0, sweep: -6, bloom: 0.5 };
const T0 = cue('c01').start;
tl.to(k, { glow: 0.35, bloom: 0.9, duration: 0.6, ease: 'power2.out' }, T0 + 0.3);
tl.fromTo(k, { sweep: -6 }, { sweep: 6, duration: 1.6, ease: 'power1.inOut', immediateRender: false }, T0 + 1);
onFrame((t) => { uGlow.value = k.glow; uSweep.value = k.sweep; uBloom.value = k.bloom; fx.render(t); });
```

**(b) Text that ripples, then burns away** (a hot edge eats the letters along a fixed noise field):

```js
const { vec2, vec3, uv, texture, sin, step, mx_noise_float } = TSL;
const { texture: tex, aspect } = await fx.textTexture('심해의 빛', { font: '900 170px Pretendard', color: '#ffffff' });
const uRip = uniform(0), uDis = uniform(0);
const p = uv();
const wob = vec2(sin(p.y.mul(26).add(fx.uTime.mul(3.2))).mul(0.012), sin(p.x.mul(17).add(fx.uTime.mul(2.1))).mul(0.008)).mul(uRip);
const tc = texture(tex, p.add(wob));                                                   // under-water ripple
const n = mx_noise_float(vec3(p.x.mul(aspect * 5), p.y.mul(5), float(1.7))).mul(0.5).add(0.5);   // 0…1, fixed
const keep = step(uDis, n);                                                            // uDis 0 → 1 burns it away
const edge = smoothstep(uDis.add(0.07), uDis, n).mul(keep).mul(step(0.001, uDis));
const m = new T.MeshStandardNodeMaterial({ transparent: true, depthWrite: false, roughness: 1, metalness: 0 });
m.colorNode = vec3(0);                                                                 // self-lit: all light is emissive
m.emissiveNode = tc.rgb.mul(0.85).add(color(0xff8a4c).mul(edge).mul(4)).mul(tc.a).mul(keep);
m.opacityNode = tc.a.mul(keep);
fx.scene.add(new T.Mesh(new T.PlaneGeometry(aspect * 2.4, 2.4), m));
// tl: uRip 0 → 1 on the line about water; uDis 0 → 1 (power1.in, ~1.8 s) when it vanishes; 1 → 0 materialises it
```

- Glyph outlines (vector, `TX.shapes`) for anything with depth; `fx.textTexture` (raster) for effects on flat text.
  The texture's sharpness is its font size: 170 px on a 2.4-unit plane held up at 1080p.
- Keep a base glow low (~0.35) so a sweep still reads; save strong bloom for the one glow beat.
- Readable copy stays DOM above the canvas (§7); these are for the hero line.

| symptom | cause | fix |
|---|---|---|
| dissolved text still glowed as a blurry ghost of the whole line | the `emissive` MRT attachment ignores opacity; bloom read the full text | multiply `emissiveNode` by the same mask as `opacityNode` |
| text plane unreadable, letters lost in their own halo | white emissive 1.0 + bloom strength 1.1 with threshold 0 | emissive ≈ 0.85 and bloom ≈ 0.45 for text |
| the light sweep didn't read | base glow 0.9 already saturated the face under bloom | base glow ≈ 0.35, band × 2 on top |
