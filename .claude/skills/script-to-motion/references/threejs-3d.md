# three.js 3D layer — real 3D inside the video

A WebGL canvas in a scene, rendered from the playhead `t` like everything else. Assets usually come from
Blender (blender-mcp.md) as GLB; simple shapes can be made directly with three.js.

**Two builds, one per project.** This page is the classic build (`Stage3D`: WebGLRenderer, RoomEnvironment,
OutlineEffect). When the beat needs light as meaning — glow, light rays, focus pulls, flares, reflections,
shaped 3D transitions, GPU particle formations — use the **FX build** instead: `enable_3d.mjs <dir> --fx`,
`await StageFX.create(...)`, and read `shader-fx.md`. Loading GLBs, `mixer.setTime(t)`, `byName` and the
camera-from-`tl` pattern below work the same in both.

## Contents
1. Enable it
2. The layer and the Stage3D helper
3. Driving 3D from the timeline
4. Recipes
5. Look & performance
6. Verify
7. Text in 3D from glyph outlines (TypeFX)

---

## 1. Enable it

```bash
node <skill>/scripts/new_project.mjs <dir> --title "…" --3d      # new project with three.js
node <skill>/scripts/enable_3d.mjs <dir>                          # or add it to an existing one
node <skill>/scripts/embed_glb.mjs assets3d/cup.glb <dir>         # each GLB → models/cup.glb.js (+ script tag)
```

`vendor/three/three.bundle.min.js` is a classic-script build of three.js (r186) exposing `window.THREE`
with `GLTFLoader`, `RoomEnvironment` and `OutlineEffect`. It exists because Chrome refuses ES modules and
`fetch()` on `file://` — the video must open by double-click — which is also why GLBs are embedded as
base64 scripts. (Rebuild it from `assets/three/three.bundle.entry.js` with esbuild if you need other addons.)

## 2. The layer and the Stage3D helper

```html
<section class="scene" id="s04">
  <canvas id="gl"></canvas>              <!-- CSS: #gl { position: absolute; inset: 0; } -->
  <h2 class="title">…</h2>              <!-- DOM text on top of the 3D stays crisp and animatable -->
</section>
```

```js
Video.define(async ({ tl, cue, scene, onFrame, W, H }) => {       // async: GLB parsing is async
  const s3d = Stage3D.create(document.getElementById('gl'), { W, H, fov: 30 });
  // options: background: '#hex' (default transparent → DOM background shows), environment: true (soft studio
  // light via RoomEnvironment), exposure: 1, outline: false (comic ink outlines), outlineThickness: 0.004
  const T = s3d.THREE;
  const gltf = await Stage3D.loadGLB('cup');
  s3d.scene.add(gltf.scene);
  const key = new T.DirectionalLight(0xffffff, 2.0); key.position.set(3, 5, 4); s3d.scene.add(key);
  const mixer = Stage3D.mixer(gltf);                              // null when the GLB has no animation
  const handle = Stage3D.byName(gltf, 'Handle');                  // nodes keep Blender object names
  …
});
```

`s3d.render()` renders at the stage's on-screen resolution (sharp in fullscreen/4K; capped at 3×).

## 3. Driving 3D from the timeline

Same rule as everything else: **state is a function of t**. Tween plain objects on `tl`, then copy them
into the 3D scene in `onFrame`:

```js
const cam = { a: -0.5, h: 1.3, d: 4.4 };                          // orbit angle, height, distance
tl.to(cam, { a: 0.7, d: 3.4, duration: 4, ease: 'power2.inOut' }, 'c02');
tl.to(cam, { h: 3.4, d: 1.6, duration: 1.4, ease: 'power3.inOut' }, cue('c03').when('내려다보면') - 0.2);
const cupPose = { spin: 0, lift: 0 };
tl.to(cupPose, { lift: 0.2, duration: 0.6, ease: 'back.out(2)' }, 'c04');

onFrame((t) => {
  if (mixer) mixer.setTime(t);                                   // glTF clips sampled at t (seekable)
  gltf.scene.position.y = cupPose.lift;
  s3d.camera.position.set(Math.sin(cam.a) * cam.d, cam.h, Math.cos(cam.a) * cam.d);
  s3d.camera.lookAt(0, 0.42, 0);
  s3d.render();
});
```

Forbidden (check.mjs flags them): `THREE.Clock`, `getDelta()`, `getElapsedTime()`, `renderer.setAnimationLoop`,
`mixer.update(delta)`, physics stepping, `Math.random()` for placement (use `rand(seed)`).
To start a clip at a cue instead of t=0: `mixer.setTime(Math.max(0, t - cue('c05').start))`.

## 4. Recipes

- **Turntable reveal**: object scale 0 → 1 with `back.out` at the cue, slow orbit (`a` over the whole scene).
- **Dolly to a detail**: tween `d` and `lookAt` target (tween a `{x,y,z}` target object too) to the part the
  narration names, 0.2 s before the word (`cue(id).when('…')`).
- **Exploded view**: tween each part's position outward from the root (parts found with `byName`).
- **3D + 2D**: keep headlines as DOM over the canvas; let a 3D object "hold" a DOM label by projecting a
  point: `const p = obj.getWorldPosition(new T.Vector3()).project(s3d.camera); label.style.transform =
  \`translate(${(p.x + 1) / 2 * W}px, ${(1 - p.y) / 2 * H}px)\`` inside `onFrame`.
- **Comic look**: `Stage3D.create(canvas, { outline: true })` + flat colours (roughness 0.6–0.9); optionally
  swap materials for `MeshToonMaterial` with the same colour.
- **Primitives without Blender**: `new T.Mesh(new T.BoxGeometry(1, 1, 1), new T.MeshStandardMaterial({ color: 0xf2604c, roughness: 0.4 }))`.

## 5. Look & performance

- The default lighting (RoomEnvironment + one directional key) flatters PBR materials; add a rim light
  from behind for silhouettes; keep backgrounds in the DOM so colour escalation still works.
- Transparent canvas (`background` unset) → the page colour and grain show through.
- Keep triangles ≲100k on screen, one canvas per scene at most, and hide scenes you're not using (scene()
  visibility stops the browser compositing them; also skip `s3d.render()` when the scene is hidden if it's heavy).
- `snapshot.mjs --perf` reports JS time per frame; GPU cost isn't measurable on machines without a GPU
  (screenshots use software rendering) — ask the user to watch 3D moves for smoothness.

## 6. Verify

- `smoke.mjs` stubs the 3D layer (jsdom has no WebGL) — it checks the rest of the page.
- `render.py --screenshot` renders real WebGL (software SwiftShader when there's no GPU — slower, same picture).
  Shoot each camera move and animation at `--gapframe 3`, check framing, lighting, that the object is where
  the narration says, and that DOM text doesn't collide with it. SwiftShader "GPU stall" console notes are
  filtered out as noise.

## 7. Text in 3D from glyph outlines (TypeFX)

Solid letters with sides, bevels and real light, from the same SIL OFL 1.1 catalogue fonts: list the line in
`glyphs.json` and run `text_to_paths.mjs` (type-fx.md), then `TX.shapes(key)` gives polygons centred on the line,
y up: `[{ outer: [[x, y]…], holes: [[[x, y]…]…], glyph, ch }]` in glyph px. Tested with "심해 10,935m"
(Pretendard 900) and "HADAL" (Black Han Sans) in the classic build, and in the FX build (shader-fx.md §11).

```js
Video.define(async (ctx) => {                                   // keep ctx whole: TypeFX.install(ctx) needs it
  const { tl, cue, onFrame, W, H } = ctx;
  const TX = TypeFX.install(ctx);                               // works in the async define like everything else
  const s3d = Stage3D.create(document.getElementById('gl'), { W, H, fov: 30 });
  const T = s3d.THREE, PX = 1 / 100;                            // glyph px → world units (200 px type ≈ 2 units)
  const toShape = (p, cx = 0, cy = 0) => {
    const s = new T.Shape(p.outer.map(([x, y]) => new T.Vector2((x - cx) * PX, (y - cy) * PX)));
    for (const h of p.holes) s.holes.push(new T.Path(h.map(([x, y]) => new T.Vector2((x - cx) * PX, (y - cy) * PX))));
    return s;
  };
  const EXT = { depth: 0.42, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.03, bevelSegments: 3, curveSegments: 1 };
  const face = new T.MeshStandardMaterial({ color: 0x59f3e0, roughness: 0.32, metalness: 0.1 });
  const side = new T.MeshStandardMaterial({ color: 0x0c5f6b, roughness: 0.45, metalness: 0.35 });
  const geo = new T.ExtrudeGeometry(TX.shapes('deep').map((p) => toShape(p)), EXT);
  geo.translate(0, 0, -EXT.depth / 2);                          // pivot in the middle of the depth
  const word = new T.Mesh(geo, [face, side]);                    // ExtrudeGeometry groups: 0 = caps (face), 1 = sides
  s3d.scene.add(word);
  // key light + a cool rim light from behind; camera from tl values, s3d.render() in onFrame (§3)
});
```

**Strokes and jamo flying apart in 3D.** One mesh per piece (an outline with its holes: a jamo, a stroke, a digit),
its geometry centred on the piece so it spins in place; motion is closed-form in `t`, so seeking is exact:

```js
const easeOut = (k) => 1 - Math.pow(1 - Math.min(1, Math.max(0, k)), 3);
const parts = TX.shapes('deep').map((p, i) => {
  const xs = p.outer.map((q) => q[0]), ys = p.outer.map((q) => q[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const g = new T.ExtrudeGeometry(toShape(p, cx, cy), EXT); g.translate(0, 0, -EXT.depth / 2);
  const m = new T.Mesh(g, [face, side]); bits.add(m);           // bits = a THREE.Group shown while the word is in pieces
  const h = (k) => TX.m.hash(i * 31 + 7, k, 5);                 // per-piece random, the same on every seek
  return { m, home: new T.Vector3(cx * PX, cy * PX, 0), delay: h(7) * 0.35,
    v: new T.Vector3((h(1) - 0.5) * 4 + cx * PX * 0.9, (h(2) - 0.5) * 4, 1 + h(3) * 5),     // outward and toward camera
    spin: new T.Vector3((h(4) - 0.5) * 9, (h(5) - 0.5) * 9, (h(6) - 0.5) * 6) };
});
const fly = (tau) => (tau <= 0 ? 0 : (1 - Math.exp(-1.4 * tau)) / 1.4);   // burst, then drift (drag)
onFrame((t) => {
  word.visible = t < tSplit; bits.visible = !word.visible;
  for (const P of parts) {
    const max = tBack - tSplit - P.delay;                        // out at tSplit, then the same path backwards at tBack
    const tau = Math.max(0, t < tBack ? t - tSplit - P.delay : max * (1 - easeOut((t - tBack - P.delay * 0.6) / 1.4)));
    P.m.position.copy(P.home).addScaledVector(P.v, fly(tau));
    P.m.rotation.set(P.spin.x * tau * 0.18, P.spin.y * tau * 0.18, P.spin.z * tau * 0.18);
  }
  s3d.render();
});
```

- **Size the camera to the line.** A 1262 px line is 12.6 units wide; at `fov: 30` on 16:9 the visible width is
  ≈ 0.95 × distance, so a distance of ~22 frames it with margin (at 15 it ran off both edges).
- **Cost** is set by the outline resampling (`"step"` in glyphs.json, px between points): at step 4, "심해 10,935m" is
  7.8k triangles flat-sided, 31.5k with a 3-segment bevel. Use step 4–6 for 3D; JS per frame stayed ≤ 0.4 ms.
- **Readable copy stays DOM** above the canvas (a TX.split subtitle worked unchanged over the WebGL layer).
- Verify with `snapshot.mjs --seekcheck` (it compares WebGL canvases from screenshots of their box — `toDataURL()`
  alone returns a blank buffer once the frame is composited) and look at the moves on render.py sheets: shooting the same times
  in two different orders gave byte-identical PNGs here.

| symptom | cause | fix |
|---|---|---|
| hairline seams inside Pretendard letters (ㅅ, ㅎ, ㅐ) | the variable font keeps overlapping contours (4 overlapping piece pairs in "심해 10,935m", 9 in "깊은 바다"); each piece's bevel ridge shows through the other | text_to_paths.mjs now merges overlapping contours by default — don't use `--strokes` for bevelled 3D (or turn the bevel off) |
| the line ran off both edges | world width = glyph px × PX | camera distance from the width (above) |
