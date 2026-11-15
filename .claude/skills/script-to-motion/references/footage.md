# Footage — screen recordings and generated clips in the video

Some videos are about a product: the user records its website or app, or a tool generates clips that the video must
show and judge. This file covers putting that footage on the master clock, pointing at things in a recording without
zooming in, and the rules that keep footage honest.

## Contents
1. What counts as footage, and provenance
2. Preparing files: masters, playback copies, privacy
3. `media.js`: clips on the master clock
4. Review mode: stills for headless Chromium
5. Recordings: never zoom in — dim the rest and pin a callout (`reckit.js`)
6. Generated outputs: play them whole, compare plan and result
7. Clip sound: level, ducking, silent tails
8. Checklist

## 1. What counts as footage, and provenance

Footage is never made by you and never taken from the web: it is what the **user provides** (their screen recordings,
the clips their tool generated, a sponsor's official media kit they hand you). Every file goes in `assets/user/` (or a
master folder outside the project) and gets a `provenance.json` entry with `source: "user"` and a note saying what it is
("Higgsfield official Media Kit, Comparisons/02, given 2026-10-28"). `check.mjs` refuses unlisted media. The frames
`stills.mjs` cuts are recorded in `generated.json` (it keeps a cut only while every frame is recorded unchanged).

Name the official asset as what it is on screen only when the user/sponsor wants it; otherwise keep labels generic.

## 2. Preparing files: masters, playback copies, privacy

- **Master**: the full-quality source (4K recording, the generator's original file). Stills for review are cut from it.
  Large masters can live outside the project (`media/master` → a symlink); keep a script that rebuilds them
  (`tools/prep_media.sh` in the project) so a cleared `/tmp` is no problem.
- **Playback copy**: what the browser streams — H.264, CRF ~20, AAC 160k, `+faststart`. `media_info.mjs <dir> <key>
  <master> --copy` writes it and prints the `js/media-src.js` entry (pixel size, length, loudness).
- **Cut, don't speed up, the waiting.** In a long recording, trim dead stretches (loading, typing a long prompt) in the
  master with ffmpeg, or show them silent at a `rate` > 1 with a visible "×4" label — never pass a waiting screen off as
  real time, and never speed up a clip's sound. The speed of a silent clip goes only through `M.clip(…, { rate })`; never
  set a media element's `playbackRate` in your own code (`check.mjs` errors on it).
- **Privacy — blur before anything else.** Personal libraries, file pickers, OS dialogs, e-mail addresses, account
  names, other users' content (a community feed), phone numbers. Blur in the master, not with an overlay: an overlay can
  slip when the placement changes. Use a **moderate** blur (`boxblur=20:2` on a 4K recording) that hides details but
  still reads as "a page section", and **feather its edge** (an alpha-faded mask over ~200 px) — a hard-edged block
  looks like damage and draws the eye ("이정도로 가려버리지는 말고 그냥 적당한 블러정도로").
- **Single frames** as content of the video (a card, a comparison still): `ffmpeg -ss <t> -i master -frames:v 1 -q:v 2
  assets/user/<name>.jpg`, listed in provenance like the clip. Only into `assets/user/`, only for the video — never a
  frame cut to look at (that is `render.py <clip> --screenshot --at T`; the guard blocks every other ffmpeg frame grab).

## 3. `media.js`: clips on the master clock

Declare the clips once in `js/media-src.js`:

```js
window.MEDIA_SRC = { level: -22, clips: {
  rec_frames: { file: 'assets/user/vid/rec_frames.mp4', master: 'media/master/rec_frames.mp4', w: 3840, h: 1750 },
  clip_s1:    { file: 'assets/user/vid/clip_s1.mp4', master: 'media/master/clip_s1.mp4', w: 1076, h: 1924, dur: 30.04, lufs: -12.5 },
} };
```

Place them in scenes:

```js
const M = MEDIA.install(ctx);
M.clip(monitorScreenEl, 'clip_s1', { x: 0, y: 0, w: 540, h: 960, start: cue('op02').end + 0.15, dur: 30.04, audio: true, vol: 1 });
M.clip(B.world, 'rec_frames', { x: 0, y: 0, w: B.vw, h: B.vh, start: cue('fr01').start - 0.4, in: 12.0, dur: 26, rate: 1 });
```

- `start` = video time the clip's `in` point plays; `dur` = how long (video seconds); `rate` plays it faster/slower —
  only a silent clip: sound is never slowed down or sped up, so `audio: true` needs `rate` 1 (media.js refuses otherwise).
- `crop: [sx, sy, sw, sh]` in master pixels; `fit: 'cover' | 'contain'`; `show: [t0, t1]` to keep the last frame up
  longer than it plays (a hold); `zoom` tells review mode how large the box gets on screen (still resolution).
- Every placement is a pure function of t: seeking anywhere shows the same frame. In a normal browser the `<video>`
  plays while the player plays and is seeked when paused or scrubbed. At a review speed (the player's Shift+> / Shift+<)
  the clips play at that speed too — review only: R resets the player to 1× before a recording, and `render.py` films
  the stills and mixes the clips' sound at 1×.

## 4. Review mode: stills for headless Chromium

Headless Chromium can't decode H.264. With `?stills` (and in every review tool: snapshot.mjs, check_fonts.mjs,
errscan.mjs) `media.js` shows JPEG frames instead. Cut them after adding or moving a placement:

```bash
node <skill>/scripts/stills.mjs <dir>            # media/stills/<placement id>/00001.jpg … at 10 fps, half size
```

Add `media/stills/` to the project's ignore list when it's a repo; it is rebuilt anytime.

**Looking at clips.** To see what a clip contains (where the action is, when the result appears, where a button is,
how long the waiting lasts), make sheets from the video file itself with render.py, and keep them under the project's
`screenshots/`:
`python3 <dir>/render.py <dir>/media/master/<file> --screenshot --gapframe 60 --out <dir>/screenshots/clips/<key>`
(the gap counts in the clip's own fps); for a detail (a small button, a line of text) add `--at T` with `--res 1080p`
or `--crop X,Y,W,H` in the clip's own pixels — never an ffmpeg frame grab of your own. To see the clips placed in the
video, shoot the project
(visual-review.md); render.py films them from `media/render-stills`, which `stills.mjs <dir> --out media/render-stills
--fps 60 --scale 0.4444` cuts for sheets.

`errscan.mjs` and `check.mjs` fail while a placed clip has no stills, or when any file the page loads is missing.
Cut the stills before running them. Only the clips' own playback copies, which review mode leaves unloaded on purpose,
are ignored.

For an MP4 made with `render.py`, the clips are filmed from frames at the render's own rate and full size — cut them
into a folder of their own first (render.py stops and prints this command when they are missing, smaller than its
resolution needs — a 480p cut in a 4K render would be a blurry clip — or cut at another fps; re-running stills.mjs keeps
what fits, larger cuts included, and cuts the rest again):

```bash
node <skill>/scripts/stills.mjs <dir> --out media/render-stills --fps 60 --scale 1   # --scale 2 for render.py --res 4k, 0.6667 for --res 720p, 0.4444 for --res 480p
```

The clips' own sound (`audio: true`) is mixed into that MP4 with the narration as the player plays it — placement, `in`,
`vol` envelope × the `lufs` level match, capped at 1 — taken from each clip's master, always at 1×.

## 5. Recordings: never zoom in — dim the rest and pin a callout (`reckit.js`)

The user's rule for demos: the whole page stays in view. A camera push into one corner of a recording loses where we
are on the page and looks like a cheap edit ("시연 영상 화면이 너무 확대되어 특정 영역만 보이게 하는걸 지양").

```js
const R = RecKit.install(ctx);
const B = R.browser(sceneEl, { x: 40, y: 58, w: 1840, src: [3840, 1750], url: 'higgsfield.ai' });
M.clip(B.world, 'rec_frames', { x: 0, y: 0, w: B.vw, h: B.vh, start: t0, in: 3.2, dur: 20 });
const sp = R.spot(B);
const BTN = [3120, 1490, 560, 170];                         // master px, measured on a frame of the master
sp.on(cue('fr07').when('버튼'), BTN);                              // hole + one pen loop drawn round it, everything else dims
R.callout(sceneEl, { x: 1180, y: 690, at: cue('fr07').when('원래'), out: cue('fr09').start, from: sp.pt(BTN, 'l'),
  html: '<div class="k">생성 버튼</div><div class="v">30 크레딧</div><div class="s">촬영 시점 · 바뀔 수 있음</div>' });
sp.go(cue('fr08').start, PROMPT, 0.6);                               // the hole glides to the next thing — never redrawn
sp.off(cue('fr09').start);
```

- **The highlight** (`spot`): a hole over the target, everything around it dimmed to ~66 %, one hand-drawn loop round it,
  drawn on once. When the subject moves to the next control, the hole **glides** there; the loop is not drawn again on
  every tab switch (it read as nervous). One line only — never two loops or a loop and a box.
- **The text** goes in a **callout** in the dimmed area: a paper label with a kicker, a large value (58 px+), a small
  line. Readability comes from the callout's type size, not from enlarging the recording. The leader line ends just
  outside the loop (`sp.pt(rect, side)`), never on top of it or crossing the hole.
- Measure target rects on the master (crop a frame, read pixel positions); they don't change between placements.
- Keep particles, grain, light leaks and "breathing" scale off recordings and clips — atmosphere goes around the window.
- A browser frame with a drawn address bar keeps the viewer oriented. Show the product's real URL only.
- The rest of RecKit (`js/reckit.js` header): `R.leader(parent, pts, at, outAt)` / `R.link(parent, from, [x, y], at,
  outAt, edge)` — the hand-drawn line alone; `R.track(state)` → `to(at, dur, vals, ease)` — keyframes on a plain object
  that never overlap; `R.camera(worldEl, { x, y, s }, vw = W, vh = H)` → `{ st, to }` — a camera over a world div:
  `st.x/st.y` is the world point at the centre of the `vw × vh` frame (default the stage, so it is centred on 9:16 and
  other aspects too; pass the view's size for a camera inside a smaller box), `st.s` the scale; move it with
  `to(at, dur, { x, y, s })`. Not for zooming into a recording (above). Every RecKit time (`at`, `out`, `outAt`) is
  seconds or a cue label (`'fr07'`, `'fr07+=0.3'`).

## 6. Generated outputs: play them whole, compare plan and result

- **Play every finished output in full**, once, uncut, without overlays fighting it (no fast montage that hides
  continuity). Narration may run over its silent stretches. Never trim inside a generated clip — its own pauses stay.
- **Plan next to result**: put the planned keyframes beside the matching moments (a tracing-paper overlay, an A/B pair
  with the same scan line, a ruler of planned vs actual cut times); for a reference/edit mode, show source, reference and
  result side by side so viewers see what carried over and what changed.
- **Grade honestly but briefly**: mint ✓ for what held, a calm red mark for what slipped, one sentence each. In a
  sponsored video the verdict is short and constructive (references/sponsored.md).
- **Dashed = plan, solid = footage** is a strong visual grammar: a dashed card that turns solid when the output fills it.

## 7. Clip sound: level, ducking, silent tails

- Generators deliver audio ~10 dB hotter than narration. `lufs` per clip + `level` (the narration's integrated
  loudness, ≈ −22 LUFS for Fish takes) level-match every clip before its envelope applies.
- Under narration, duck: `vol: M.duck(start, dur, 0.85, 0.18)` — low while a cue is spoken, back up in the gaps.
- A clip that ends on a silent hold: start the next narration **over the hold** while the picture plays to its end —
  never wait it out (dead air, references/sound.md).
- In `wave.mjs` a clip with sound is marked `[clip:key … clip:key]`; silences inside a clip shown whole are the clip's own and stay.

## 8. Checklist

- [ ] every footage file in provenance.json; privacy blurred in the masters (moderate, feathered)
- [ ] no zoom into recordings; spots glide, one line; callouts carry the text
- [ ] every output played whole once; plan beside result; nothing trimmed inside an output
- [ ] clips level-matched (`lufs`), ducked under narration, no dead air at clip tails (read with `wave.mjs`)
- [ ] `stills.mjs` run after placement changes so the review tools see the footage
