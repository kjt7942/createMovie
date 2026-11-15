# Visual review — looking at the video with render.py

You can't watch the video, but `render.py --screenshot` films any stretch of it frame by frame, the same way it films
the MP4 the user will get, and lays the frames out as contact sheets you open as images. What you see on a sheet is
what ends up in the video file. This is the loop that turns "it should look right" into "I looked, and it does".

> **When to look, and when not.**
> - **Work you do on your own:** the first build, anything you decide to improve, a redesign you carry out. Look at it
>   with `render.py --screenshot` and keep improving until a pass finds nothing. Don't hand off what you haven't seen.
> - **A fix the user asks for:** implement it in code straight away. Don't shoot or measure it
>   ("실측보다는 코드로 바로 구현한다. 확인은 사용자가 하고 피드백을 줄것이다"). Run the cheap gates (`check.mjs`,
>   `errscan.mjs`; read `wave.mjs` when sound or timing changed, `check_fonts.mjs` when text changed), say what changed at which time and
>   cue id, and hand over (references/collaboration.md).
> - **When the user asks you to look** (or pastes the player's **A** command), run it and open the sheets.
>
> **render.py --screenshot is the only way you look at the picture — absolute** (SKILL.md → Looking at the picture).
> No screenshot code of your own, no ffmpeg frame grabs, no image any other tool left behind. `snapshot.mjs` and
> `preview_art.mjs` measure and write no picture (§4); every finding they print comes with the render.py command that
> shows it.

## Contents
1. Tools at a glance
2. The review loop
3. What to look at in every frame
4. The automatic checks (snapshot.mjs)
5. Checking sync
6. Iterating: before / after (6b. Shader FX beats)
7. Footage: looking at the user's clips
8. What a sheet can't tell you

---

## 1. Tools at a glance

Run render.py from the project (`<dir>/render.py`, a copy sits in every project). Without `--progress` it prints only
the full paths of the sheets: open those images. Full reference: render.md §3–4.

```bash
python3 <dir>/render.py <dir> --screenshot --gapframe 120            # the whole video, one tile every 2 s (60 fps)
python3 <dir>/render.py <dir> --screenshot --from 12 --to 20 --gapframe 30   # how one beat enters, holds, leaves
python3 <dir>/render.py <dir> --screenshot --from 7.0 --to 8.4 --gapframe 3  # a transition, a jump, a flash, frame by frame
python3 <dir>/render.py <dir> --screenshot --from 7 --to 9 --gapframe 6 --out <dir>/screenshots/before   # keep a set
python3 <dir>/render.py <dir> --screenshot --at 11.5,23                      # exactly these moments
python3 <dir>/render.py <dir> --screenshot --at 23 --res 1080p               # one moment at stage size: small type, detail
python3 <dir>/render.py <dir> --screenshot --at 23 --crop 1200,600,640,360 --res 4k   # a stage rectangle at twice the pixels
python3 <dir>/render.py <dir> --screenshot --at 66.3 --via 74.3              # a seekcheck difference, both ways + diff
python3 <dir>/render.py <dir> --screenshot --art whale --viewbox "-200 -130 400 260" --at 0,0.6,1.2   # one js/art module
```

| to see | gap at 60 fps |
|---|---|
| a transition, a flash, a one-frame jump, text colliding | 1–6 over 1–3 s |
| how one beat enters, holds and leaves | 15–30 over the beat |
| the build of a chapter | 60–120 |
| the whole video at a glance | 120–300 |

Each tile is 480p (or what `--res` / `--crop` ask for) and labelled `frame  m:ss.ff  [cue]`: the same time and cue id
the player's **S** key copies, so you and the user name the same moment. A tile of 1000 px or more gets an image of its
own, because an image viewer shrinks a wide sheet and the detail would be lost again.

**Debugging is looking too.** Something missing, a wrong colour, a glitch you can't explain: shoot the moment
(`--at T --res 1080p`, then `--crop` on the spot), read `errscan.mjs` for errors and missing files, and measure with the
checks. A probe script that takes a screenshot is never the way, however quick it seems. The captions are on, as in the MP4.

**Footage first.** When the video places clips, cut their render frames once before the first sheet:
`node <skill>/scripts/stills.mjs <dir> --out media/render-stills --fps 60 --scale 0.4444` (render.md §5; render.py
stops with this command if they are missing).

No browser yet? See browser-setup.md (`node <skill>/scripts/setup_browser.mjs`); render.py sets up its own the first time.

## 2. The review loop

1. **Whole video** — `--gapframe 120`. On the sheets the whole piece is one picture: is there variety of framing,
   scale and colour, or the same layout over and over? Does the colour or the camera escalate with the story? Find
   the frozen stretches yourself: where the narrator keeps talking but nothing on screen follows the words, fix it;
   stillness that means something (a line landing, a held beat) stays.
2. **Beat by beat** — each chapter at `--gapframe 30`. Read the tiles against storyboard.md, cue by cue.
3. **Key moments** — for every beat the story depends on (an encounter, a reveal, a push-in, the payoff), shoot the
   stretch around it at `--gapframe 6` and check that the moment happens **on screen, while it is being said** (§5).
4. **Transitions, frame by frame** — every cut, camera move and scale change at `--gapframe 1–3`. Look for one-frame
   jumps (a changed `transform-origin`), elements flashing their default state before their entrance, two scenes
   muddily overlapping, and dim or highlight states you couldn't explain in a sentence. The user scrubs in
   0.5-second steps and will see all of these.
5. **Fix, then shoot the same stretch again** (§6). Repeat until a pass finds nothing.
6. **The automatic checks** (§4) before the hand-off.
7. **Hand off** with the paths of the latest sheets, so the user can look at the same frames.

## 3. What to look at in every frame

- **Not a slide**: strip the motion away. Would this frame pass as a PPT slide or a document page (a title bar,
  cards or panels of text, bullets, a table, boxes with arrows)? Then the scene is rebuilt, not polished
  (SKILL.md → No slides, no boxes).
- **Story**: does the frame show what the storyboard promises for this cue? Is the key word/number the
  biggest thing on screen *now*?
- **The shot** (motion-design.md §8b): the shot size, angle and camera move the shot list planned; screen direction
  kept; the camera moving only where the words give it a reason.
- **Focus**: one clear focal point; nothing important under the HUD, off the edge, or behind another element.
- **Text**: large enough, readable contrast, not overlapping, not cut, sensible line breaks (Korean words
  not split), no orphaned single syllable.
- **Attached things stay attached**: in every camera/parent move, a light's glow and flare stay on the
  light, a weight on its rope, a label on its object (`--gapframe 6` across the move).
- **Effects that are physically right**: lens flares only on lights a camera would see (none on a light
  seen from under water — there it's a soft diffuse glow); bubbles rise, dust settles, shadows fall away
  from the light.
- **Procedural shapes look natural**: clouds, rocks, smoke, splashes and other generated detail. Uniform domes, flat
  cut-off bases, outline strokes on soft things and detached blobs read as mistakes (a pressure bulge beside a finger
  read as ears).
- **Decorative type counts as text**: giant outline/ghost words behind labels are text for the overlap warning — a
  label on top of their strokes needs its own backing or another place.
- **Clipped glows**: faint coloured rectangles behind individual characters or digits mean a `text-shadow` is being
  cut by a SplitText mask or an `overflow: hidden` digit box (player-api.md §4). Subtle at 480p: rely on the automatic
  "glow clipped into a box" warning (§4) as well.
- **Expressive type** (type-fx.md): the line is readable and still while it is spoken; the break, melt or
  dissolve lands on the stressed word, not after it; the swap from text to its copies/outlines/pixels is
  invisible (`--gapframe 1–3` across it); pieces and dust leave the frame or fade, so no debris is left in the next
  shot; the effect fits the line's meaning and the piece's material.
- **Acting**: gaze direction, brows and mouth read at this size; characters face the right way.
- **Composition**: balanced, safe margins, intentional empty space vs accidental emptiness.
- **Continuity**: persistent elements (HUD, counters, colours) show the right state for this point.
- **Transitions**: no ugly mid-states, no flash of the wrong layout, no element popping in late or lingering after
  its exit.
- **First and last frame**: both intentional — the first shows while fullscreen settles, the last holds.

## 4. The automatic checks (snapshot.mjs)

These measure and write no picture. Read what they report; every warning ends with a `look:` line, the render.py
command for those moments: run it and open the sheet.

```bash
S=<skill>/scripts
node $S/snapshot.mjs <dir>                          # layout warnings at every cue (overlaps, clipping, clipped glows)
node $S/snapshot.mjs <dir> --overview --seekcheck   # determinism: each shot again (reverse, then shuffled order) must match
node $S/snapshot.mjs <dir> --safezone               # text inside the unsafe margins (9:16: the platform UI)
node $S/snapshot.mjs <dir> --captions               # layout warnings with the captions on
node $S/snapshot.mjs <dir> --perf                   # JS cost per frame during playback
```

Layout warnings, measured by the browser on what is actually visible (clipping and masks taken into account):

| warning | usually means | intentional when |
|---|---|---|
| text overlaps text | two labels collide | a caption deliberately placed over a balloon (rare) |
| text clipped by its container | text touching a border, box too small | never at rest — fix it |
| text cut by screen edge | layout past the safe area | a previous shot moving away, a deliberately cropped close-up, mid-transition |
| text in the unsafe … margin | text inside `--safe*` (in 9:16: under the Shorts/Reels/TikTok UI) | a full-bleed background word that is decoration, not reading |
| glow clipped into a box | a light `text-shadow` cut by a SplitText mask, digit column, `overflow`, `clip-path` or mask: faint rectangles behind the letters | never — move the glow to `filter: drop-shadow()` outside the clip (player-api.md §4) |

Decorative copies (`[data-fx-copy]`: TypeFX shards, glitch bands, extrusion layers, motion-blur ghosts, FXKit
glints), units of one TypeFX group crossing each other, and units an effect is moving are not reported. When a warning
is reported, look at that moment on a render.py sheet.

`--seekcheck` reaches every shot again, in reverse order and then in a fixed shuffled order (`--seed N`, default 1),
and compares the picture: a hash of the screenshot, then the pixels (it reports how many differ and where). The
element and property that changed are listed when the computed styles show it; "no listed property explains it" means
something outside that list (an SVG attribute like `cx`, a `box-shadow`, a background). Each difference is printed with
the time it was reached from and its `look:` command, `render.py --screenshot --at T --via FROM`: a row of
[in order | from FROM | difference], the differing pixels in magenta inside a yellow box, counted and placed in stage
pixels. Add `--crop` around the box and `--res 4k` to see it closer.
A difference means something depends on what was played before or on the path of seeks: accumulated state,
`Math.random` or `Date`, a cache that skips a needed write, or a timeline callback. Never ship with one.

Also read the console errors — a page error means some animation never ran. `errscan.mjs` also lists every file the
page asked for and didn't get (a missing `js/art/*.js`, `<img>`, stylesheet) and footage whose stills haven't been cut
(run `stills.mjs`).

## 5. Checking sync

A visual should land **with or slightly before** the words it illustrates. Find the moment the words are spoken:
`cue(id).when('phrase')` is the time you set from the take (`at` → `sync.mjs` → `js/sync.js`), estimated before. Shoot that moment at
`--gapframe 3`, from about half a second before to half a second after, and find the first tile where the element is
readable. It should be at or before the tile at that time.

## 6. Iterating: before / after

```bash
python3 <dir>/render.py <dir> --screenshot --from 7 --to 9 --gapframe 6 --out <dir>/screenshots/before
# … fix …
python3 <dir>/render.py <dir> --screenshot --from 7 --to 9 --gapframe 6 --out <dir>/screenshots/after
```
A folder given with `--out` keeps other files; open the two sheets side by side. (Nothing is removed unless `--clear` is
given, and every sheet's name holds its run time, so later runs never overwrite these.)

## 6b. Shader FX beats

- Shoot every FX peak (glow, slam, rays, focus pull, shaped transition) at `--gapframe 3`: the effect must land on the
  word, then settle; an effect that is still rising after the word reads as late.
- A tile that is one flat colour, or two different times that look identical, means the FX canvas isn't rendering or
  isn't receiving `t` — check `fx.render(t)` in `onFrame` and the console.
- Class-C effects (afterImage, motionBlur, traa) depend on the frames before; judge them in consecutive tiles
  (`--gapframe 1`), and say so in the hand-off if the trail matters.
- Text drawn into 3D (`textTexture`) must show every syllable — a ☐ means the glyphs weren't loaded.
- GPU cost isn't visible here (software rendering). Name the heavy FX beats in the hand-off and mention `?fxq=0.75`.

## 7. Footage: looking at the user's clips

render.py makes the same sheets from a video file, so you can see what a clip the user gave you contains: where the
action is, when the result appears, where the button is, how long the waiting lasts.

```bash
python3 <dir>/render.py <dir>/media/master/<file>.mp4 --screenshot --gapframe 60 --out <dir>/screenshots/clips/<key>
```

- The frame numbers on a clip's sheet count in the clip's own fps (`--gapframe 60` at 30 fps is a tile every 2 s).
  Pick the gap from its length: the whole clip at a glance first, then the stretch you will use at a smaller gap.
- Always pass `--out` under `<dir>/screenshots/`. Without it the sheets land beside the video file, mixed in with the
  project's footage (render.py records them in generated.json either way).
- **Detail in a clip** (a small button in a screen recording, the text of a generated result): the same command with
  `--at T` and `--res 1080p`, or `--crop X,Y,W,H` in the clip's own pixels (shown 1:1). A rendered MP4 is looked at the
  same way. Never grab a frame with ffmpeg yourself.

```bash
python3 <dir>/render.py <dir>/media/master/<file>.mp4 --screenshot --at 14.2 --res 1080p --out <dir>/screenshots/clips/<key>
python3 <dir>/render.py <dir>/media/master/<file>.mp4 --screenshot --at 14.2 --crop 2400,80,960,540 --out <dir>/screenshots/clips/<key>
```
- Use what you see to place the clip (`in`, `dur`), the spot and the callout (footage.md).

## 8. What a sheet can't tell you

- **Fine detail** is not a limit: a default tile is 480p, so shoot small type, a glyph's shape or 4K sharpness with
  `--at T --res 1080p` or `--at T --crop X,Y,W,H --res 4k`.
- **Smoothness**: headless machines usually have no GPU. `snapshot.mjs --perf` shows JS cost per frame during
  playback (sequential 1/30 s steps — keep p95 well under ~8 ms) and, separately, random-seek cost (scrubbing; often
  several times higher and not what the recording sees). Compositing/GPU cost is only visible on the user's machine.
- **Audio**: you can't hear takes; you read them as numbers (`wave.mjs`). Word times are estimates until you set them (`at`).
- **Safari/Firefox** differences (clip-path, text stroke, fonts).

Say these limits in the hand-off, and ask the user to watch the moments that depend on them (D shows the
debug bar with time and cue, so they can point at an exact moment).
