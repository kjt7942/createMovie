# cokacmotion — the technique library for expression

cokacmotion (https://github.com/kstost/cokacmotion, the `aimotion` skill, MIT) is a library of **166 short
web-graphics demos, one technique each**, in 12 groups. Each demo has implementation notes, full source and stills.
The groups are web graphics, analogue looks, web platform tech, nature/optics/maths, experimental typography, GSAP,
well-known libraries, native web animation, expressive video craft, typographic motion graphics, motion-graphics design
and 3D scenes.
It is the place this skill learns **how an effect is built**. Use it:

- in **step 5** (storyboard), for every beat's primary effect, every hero line's type treatment, the signature transition
  and the impact beats: find the technique before inventing one;
- in **step 6** (build), before writing an effect that FXKit and TypeFX don't already give you;
- whenever the user asks for 더 풍부한 표현, 표현력 업그레이드, 그래픽 업그레이드, or a named look (잉크, 수채, 판화, 필름,
  네온, 유리, 유체, 입자 …).

## Contents
1. The rule: take the technique, never the content
2. The tool: `cokacmotion.mjs`
3. Finding and reading a technique
4. Porting into this skill
5. What carries over from the code
6. Notes in the project and the hand-off

## 1. The rule: take the technique, never the content

**Borrow only how an effect is built. Never reuse what a demo depicts.** This rule comes before everything else in this file.
- **Leave out:** the demo's subject (objects, creatures, people, mascots, logos, places, data), scene and background,
  story and staging order, composition and camera path, layout, copy and captions, colours and palette, and the
  demo-only shapes.
- **Leave out the frame too:** every demo uses the same 9:16 1080×1920, 8–10 s, bottom-caption format. The video's own
  aspect, stage, safe area, captions and length apply.
- **Start from the script.** Decide the beat's content and its one primary effect in the storyboard first, then search
  for a technique that fits. Never pick a demo you like and bend the script to fit it.
- **Write the technique in one sentence without the demo's subject.** Example, from 03 (a coral in the sea): "bake a
  space-colonization growth toward attractor points once, then draw the nodes born before G(t); thickness from the
  number of descendants." If the script talks about a network spreading, the network grows. If you draw coral, sea
  or polyps, you have copied the demo.
- **Final check:** someone who has seen the demo must not recognise its scene in the video. If they would, start again
  from the script.
- **Richness comes from meaning, not from more effects.** Each beat still gets one primary effect that says what its line
  says (motion-design.md §12, craft-notes.md). cokacmotion tells you how to build it. It is not a reason to add effects.

## 2. The tool: `cokacmotion.mjs`

```bash
S=<skill>/scripts
node $S/cokacmotion.mjs search 잉크 번짐            # ranked by title, technique, key points, libraries, group (ko/en words)
node $S/cokacmotion.mjs search particles 글자 --limit 5
node $S/cokacmotion.mjs list                       # every demo, by group
node $S/cokacmotion.mjs show 12 --notes            # NOTES.md (--code: the source files; neither: both)
node $S/cokacmotion.mjs path 12                    # folder and files, incl. out/poster.jpg (and out/sheet.jpg where present)
node $S/cokacmotion.mjs common                     # shared demo runtime: _lib/stage.js (clock, rand, track, ease, replay), type.js
node $S/cokacmotion.mjs where                      # local copy, commit, fetch time (note the commit in the storyboard)
node $S/cokacmotion.mjs update                     # refresh now
```

- **First use downloads the repository** (about 70 MB) into `~/.cache/motion-video-cokacmotion` (set
  `$MOTION_VIDEO_COKACMOTION_CACHE` to change it). It uses git, or the GitHub tarball when git is missing. Tell the user
  in one line before the first download.
- After that the copy refreshes at most once a day. Offline, the cached copy is used. `COKACMOTION_DIR=<checkout>` uses an
  existing checkout instead.
- **The video never loads these files.** You read them, then write the technique into the project yourself.
- Some search results carry the library's own cautions, e.g. "CPU 검증 프레임당 3.2s — … MP4 내보내기가 매우 느리다".
  In this skill the user screen-records real-time playback, so read that as **too heavy to play in real time** (§4,
  Weight). Never mention MP4 to the user.

## 3. Finding and reading a technique

1. **Find.** Search with the words for the effect the beat needs, in Korean or English. You can also use `list`, or open
   the library's `INDEX.md` (in the folder `where` prints): by group, each entry lists the demo scene, what to learn, the
   libraries and video cautions. The "데모 장면" text is an example of the technique, not a scene to use.
2. **Look.** Open `out/poster.jpg` (the peak frame), and `out/sheet.jpg` (one frame per second) where it exists. Not every
   demo has a sheet: `path` lists what is there. Look to see how the technique reads on screen. Don't model your
   composition, colours or scene on it.
3. **Principle.** Read `NOTES.md` to the end. Its section "기법과 원리" points to the key ideas as `main.js:line`: read
   every line it points to. The first section ("화면") only says what the demo drew.
4. **Source.** Read the demo's files, and `common` for the shared runtime. One demo can be tens of thousands of
   characters, so let the notes guide you. Read until you can explain why it is built that way and could rebuild it for a
   completely different subject.
5. **Write the technique** in one sentence without the demo's subject (§1).
6. **Port it** (§4) to the beat's own subject from the storyboard.
7. **Check** (§1): the demo's scene must not be recognisable.

## 4. Porting into this skill

**The player is this skill's own** (`js/player.js`, `Video.define`). The demo runtime (`_lib/stage.js`) never comes into
a project: not its playback clock, not its keyboard controls, not its HUD, not its renderer hook `window.__video`. Only
the technique comes over, wired to the player as below.

Demos and this skill share the core idea: **every frame is a pure function of t.** The wiring differs:

| demo (cokacmotion) | this skill |
|---|---|
| `defineDemo({ setup, frame, duration })` | code inside `Video.define(async (ctx) => …)` in `js/scenes.js`, a `js/art/<group>.js` module or a `js/<name>.js` helper |
| `setup(api)`: bake geometry, compile shaders, precompute | at build time inside `define` (it may be `async`; nothing wall-clock) |
| `frame(t)`, t from 0 to the demo's duration | `onFrame((t) => { const u = t - cue('c07').start; … })`: local time from the cue the effect belongs to; draw only while its scene is on |
| `rand(seed)` (mulberry32) | `ctx.rand(seed)` |
| `track` / `ease` / `ramp` keyframes | tweens on `tl` at cue labels and `cue(id).when('구절')`, or a proxy object tweened on `tl` and read in `onFrame` |
| `replay` (stateful simulation from checkpoints) | the same pattern in project code with a fixed dt, or bake every frame's state at build time |
| `W = 1080, H = 1920` | `ctx.W`, `ctx.H` (the project's stage). Recompute coordinates and sizes, and lay portrait layouts out again for the video's aspect and safe area |
| canvas sizing in `_lib/stage.js` | `fitCanvas(canvas, W, H, 2)` |
| `import … from '../_lib/stage.js'`, ES modules | classic scripts loaded with `<script>` before `js/scenes.js`: Chrome refuses ES modules on `file://` (player-api.md §1) |
| fonts from `@fontsource` / `_lib/fonts.css`; `type.js` (opentype.js outlines, distance fields) | `add_font.mjs` (catalogue or Google Fonts `ofl/`; most demo families such as "Bebas Neue" or "Black Han Sans" are there). Glyph outlines from `text_to_paths.mjs` / TypeFX, raster type from `TX.raster`. Never a font file from the demo folder, never fontsource |
| `?t=` and the demo HUD | the player's own controls |

**Libraries.**
- This skill's runtime has two libraries:
  - **GSAP 3.15** with SplitText, CustomEase, CustomBounce, CustomWiggle, DrawSVG, MorphSVG, MotionPath and Text.
    ScrambleText is installed too, but `check.mjs` rejects it (it uses `Math.random`).
  - **three.js** via `enable_3d.mjs`: the classic Stage3D build or the FX StageFX build.
- A demo built on another library takes the principle only, rewritten in Canvas 2D, SVG, CSS, GSAP or three.js. The
  other libraries are PixiJS, p5, Babylon, Matter, Rapier, Tone, Lottie, D3, rough.js, perfect-freehand, anime.js,
  Motion, mo.js, Paper, Zdog, opentype.js and GSAP Flip.
- Physics is baked at build time with a fixed dt, and each frame reads the result by t.
- Adding a library to `assets/vendor/catalog.json` is a deliberate change to the skill. It needs the user's approval and
  the same process as fonts (official source, pinned, hashed, licence intact). Propose it in one line; never do it on
  your own.

**Hand-written shaders** (WebGL2 GLSL demos) go on the project's WebGL layer, and one build per project still holds:
- **classic build:** a full-screen quad with `THREE.ShaderMaterial` or `RawShaderMaterial`. GLSL ports nearly line for
  line; set the time uniform from `t` in `onFrame`.
- **FX build:** rewrite the shader in TSL and read only `fx.uTime` (shader-fx.md).
- The library's shader pitfalls apply too: `pow` on a negative base is NaN on real GPUs, and one NaN pixel spreads
  through bloom or blur as flicker. The library's own `SKILL.md` lists them in its section "영상에 옮길 때" (the folder
  is printed by `cokacmotion.mjs where`).

**Sound.** Some demos synthesise sound (Tone.js, WebAudio). Their visual technique can carry over, driven by `tl`, cue
times or `sync.mjs` phrase times. The project's sound stays what sound.md describes: narration plus footage sound. Ask
the user before adding any other sound.

**Data.** Demos that use real map data (world-atlas, topojson) carry over as technique only. Draw a stylised map yourself
(SKILL.md → Originality).

**Weight.** The video plays live while the user records it, so every frame must render in real time: `snapshot.mjs --perf`,
with p95 well under 8 ms of JS per frame. The library's "CPU 검증 프레임당" figure is a software-rendering time. A
technique listed at hundreds of ms or more per frame must be made lighter before it goes in:
- bake textures and sprites at build time and composite them per frame (player-api.md §4 Performance);
- lower the simulation or shader resolution;
- use fewer elements.

**Determinism** is checked as for any project code: `check.mjs` (no `Math.random`, `Date`, `performance.now`, timers in
`js/*.js`) and `snapshot.mjs --overview --seekcheck`. `check.mjs` also fails on demo code pasted without porting
(`defineDemo`, `_lib/stage.js`, `node_modules/`, `@fontsource`).

## 5. What carries over from the code

- **The code that implements the technique** may be adapted: the algorithm, the shader, the bake, the easing structure,
  the performance tricks. It is MIT-licensed and the skill names it as its technique reference (SKILL.md → Originality).
  - Put a one-line comment above the ported block, e.g.
    `// technique: cokacmotion 12-stable-fluids (MIT, github.com/kstost/cokacmotion)`.
  - When a block is substantially the demo's code rather than a rewrite, also copy the repository's `LICENSE` into the
    project once, as `licenses/cokacmotion-LICENSE.txt`.
- **The code that builds the demo's scene** does not carry over: the shapes of its subject, its copy, colour values,
  layout coordinates, staging order. Write those from the storyboard.
- **The demo's images** (`poster.jpg`, `sheet.jpg`) are for looking only. They never go into the project (provenance:
  `check.mjs` fails on unlisted media).

## 6. Notes in the project and the hand-off

- `storyboard.md` → **References**: for each beat that uses a technique, give the demo id, the technique in one sentence,
  and what this video draws with it instead. Add the commit from `cokacmotion.mjs where`.
- `진행상황.md`: one line per technique ported (demo id → file).
- Hand-off, originality line: all visuals were made for this video. Name the cokacmotion techniques re-implemented, by demo
  id and technique name.
