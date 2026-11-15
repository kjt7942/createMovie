# render.py — the MP4 and contact-sheet maker

`render.py` films a project frame by frame in a headless Chrome and writes either an **MP4** (default) or **contact
sheets** (`--screenshot`). It is one portable Python file: a copy sits at the root of every project (new_project.mjs puts
it there), and it runs from anywhere with the project folder (or its `index.html`) as the argument. The user runs it; you
don't render videos yourself unless asked (collaboration.md §4). `python3 render.py --help` lists every option.

## Contents
1. How it films a page
2. MP4 mode (short)
3. Contact sheets (`--screenshot`)
4. Reading a sheet in a review
5. Resume, stale chunks, fonts, footage
6. What it needs

## 1. How it films a page
- A local web server serves the project; Chrome opens `index.html?render&captions…` — the player hides its UI
  (`body.vp-render`), and the page reports `Video.renderReady` once built (player-api.md §6).
- For every frame n it seeks to t = n / fps, waits while `Video.renderBusy()` is true (everything registered with
  `busy(fn)` — e.g. footage frames still decoding), seeks again, waits two animation frames, then captures; by default it
  captures until two shots agree (`--fast`: one shot). Nothing plays in real time, so a slow machine only takes longer.
- Anything that finishes drawing after a seek must be registered with `busy(fn)` (SKILL.md, player-api.md §4), or the
  capture can catch it half-drawn.
- CSS `@keyframes` / WAAPI animations in the stage are captured as the player sets them (paused, seeked to t — player-api.md
  §5 "Ambient CSS loop"); the capture never freezes or finishes them on its own.
- Stage size comes from `#stage data-width/data-height`; `--res` draws the same layout with fewer or more pixels
  (device pixel ratio 4/9, 2/3, 1, 2 → 480p, 720p, 1080p, 4K).

## 2. MP4 mode (short)
**HTML only.** An agent (Claude Code: `CLAUDECODE` set in its shell) runs this mode only for an MP4 the user just asked for, with `SUMO_RENDER_OK=1` in front of the command; without it `render.py` stops with a message. `--screenshot` is never blocked.

`python3 render.py <dir> [--from s] [--to s] [--res 480p|720p|1080p|4k] [--quality high|max|ultra] [--fps 60] [--fast] [--jobs N] [--out file]`
→ `<dir>/movie_<YYYYMMDD-HHMMSS>_<res>.mp4` (the time the command started and `--res`, e.g. `movie_20261106-213045_4k.mp4`, so a
new render never overwrites an earlier one) with captions burned in and the narration of the stretch (plus the sound of clips with
`audio: true`, mixed as the player plays them). render.py always puts narration and clip sound in at 1× — the original
audio files, never sped up or slowed down — whatever review speed the player was set to (Shift+> / Shift+<).
`--out` must be a `.mp4` or `.mov` file name (its folder is made if missing); that is checked before the first frame, not
at the end. Chunks of `--chunk` seconds render in parallel (`--jobs`) and resume after
Ctrl+C. `--quality ultra` compresses losslessly: JPEG 100 captures (PNG with `--png`, slower) decoded to RGB, then
BT.709 YUV 4:4:4 with no resize and no colour halving, libx264 at qp 0 (High 4:4:4 Predictive) — only the 8-bit RGB → YUV
rounding and JPEG 100 itself lose anything. Not H.264 RGB: players that ignore its GBR tag show it green and pink. Files
are very large and some players (QuickTime) do not play 4:4:4 H.264; the sound is the same as with high/max.
On a Mac: Metal drawing and VideoToolbox encoding. README 「MP4로 굽기」 has the user-facing details.

## 3. Contact sheets (`--screenshot`)
Every `--gapframe`-th frame of the range (or every `--at` time) is captured at **480p** (or `--res`, `--crop`) and laid
out on a grid, one image per sheet. **It is the only way the picture is looked at** (SKILL.md → Looking at the picture):
every need has an option below, so nothing else ever takes or opens a picture. The user's
guide (Korean, step by step, recipes, troubleshooting) is `docs/screenshot.md` — point the user there.

| option | meaning (default) |
|---|---|
| `--screenshot` | sheets instead of an MP4 |
| `--gapframe N` | one tile every N frames (30). At 60 fps: 1 = every frame, 6 = 0.1 s, 30 = 0.5 s, 60 = 1 s, 300 = 5 s |
| `--from` / `--to` | the range in seconds (whole video) |
| `--at T,T,…` | exactly these moments, one tile each (instead of the range and the gap) |
| `--res 720p\|1080p\|4k` | the tiles' resolution (480p); a tile of 1000 px or more gets an image of its own |
| `--crop X,Y,W,H` | only this stage rectangle (stage px), at the `--res` density: `--crop 1200,600,640,360 --res 4k` → 1280×720 tiles |
| `--via SEC` | each tile again after a detour to SEC: a row of [in order \| from SEC \| difference], the differing pixels marked, counted and boxed in stage pixels — for what `snapshot.mjs --seekcheck` reports (it prints this command) |
| `--art NAME --viewbox "X Y W H"` | one `js/art` module alone (a page render.py builds in memory: core.js + every module, the fonts), posed by `animate(t, state)` at each `--at` time (0, 0.5, 1, 1.5); `--state`, `--opts` (JSON), `--group`, `--bg`, `--size` as in preview_art.mjs; tiles 800 wide at the default `--res 1080p` |
| `--cols` / `--rows` | tiles per sheet (landscape 4 × 6, portrait 8 × 3); more tiles → more sheets |
| `--fps` | the frame rate frame numbers and the gap count in (60) |
| `--out DIR` | where the sheets go (`<dir>/screenshots/`) |
| `--png` | lossless (JPEG quality 90) |
| `--no-captions` | captions off (on) |
| `--jobs`, `--fast`, `--no-gpu`, `--no-font-check`, `--fresh` | as in MP4 mode |
| `--clear` | remove earlier sheets once this run's are made (off: nothing is ever removed) — the project's `screenshots/` is emptied; any other folder loses only the sheets render.py recorded there (`.render-sheets.json`) and that are still as written |
| `--progress` | show progress while it works (off: stdout carries only the finished sheets' full paths, one per line; errors and warnings go to stderr) |

**A video file** (`render.py clip.mov --screenshot …` — mp4, mov, m4v, mkv, webm, avi): the same sheets from the file's
own frames, cut with ffmpeg (no project, no browser drawing): frame numbers and `--gapframe` in the file's fps (`--fps`
overrides), tiles 480 px high in the file's own shape (landscape 4 × 6, portrait 8 × 3) — `--res 720p|1080p|4k` for
720/1080/2160 px high (never above the file's own pixels), `--crop X,Y,W,H` for one rectangle in the file's own pixels
(1:1 unless `--res`), `--at T,T` for exactly those moments (snapped to its frames) — labels frame · time (no cue),
sheets in `screenshots/` next to the file as `<file name>_<run time>_<from>-to-<to>_every-<gap>-frames-at-<fps>fps_sheet-<k>-of-<n>.jpg`
(with `--clear`, only that file's earlier sheets are removed). Sheets only — a video file can't be made into an MP4 here.

**A page that is not a video** (`render.py <dir>/<page>.html --screenshot` — any `.html` other than `index.html`): the
page as the browser draws it once its fonts and images are ready, one tile at `--size` (1280×720) and `--res`
(1080p = 1×), `--crop X,Y,W,H` in page pixels; served from the video project above it, so its fonts load; the sheet
goes to `screenshots/` beside the page as `<project>_<run time>_page-<name>_<w>x<h>_sheet-1-of-1.jpg`.

Not used in this mode: `--codec`, `--quality`, `--encoder`, `--no-audio`, `--chunk` (each job launches one browser,
builds the page once and films the tiles of all its sheets in order, seeking from one to the next as a movie chunk does;
the sheets are split between the `--jobs` workers as neighbouring runs). A video
file's sheets take the range and the gap, `--at`, `--res` and `--crop` (not `--via` or `--art`). No ffmpeg is needed for a project's sheets (a video file's sheets need it).

**A sheet:** a header line (project · first–last tile time · gap · sheet k/N), then the tiles left to right, top to
bottom. Tiles are 854×480 (landscape) or 480×854 (portrait), outlined on a mid-grey ground; a landscape 4×6 sheet is about
3500×3250 px, a portrait 8×3 sheet about 4000×2800 px. Under each tile: `frame  m:ss.ff  [cue]` — the frame number from
the start of the video (at `--fps`, from 0), the time in the same form the player's `S` key copies, and the id of the cue
being spoken at that time (the last cue that started). Labels are set in the project's own installed fonts (D2Coding,
Pretendard) — the sheet page loads the project's `@font-face` rules.

**Files:** `screenshots/<project>_<run time>_<what>[_…]_sheet-<k>-of-<n>.jpg` — the run time is when the command started
(`YYYYMMDD-HHMMSS`, as in the movie's name). `<what>`: a range `0m08.00s-to-0m15.00s_every-5-frames-at-60fps`; `--at`
`moment-0m23.00s` or `2-moments-0m11.50s-to-0m23.00s`; `--art` `art-dino_3-poses-0m00.00s-to-0m01.20s`; then `_res-1080p`,
`_crop-640x360-at-x1200-y600`, `_seek-check-from-1m14.30s` say what else was asked, e.g.
`intro_20261109-101201_2-moments-0m11.50s-to-0m23.00s_res-1080p_sheet-1-of-1.jpg`. **Nothing is removed unless `--clear`
is given**, so the folder keeps every run's sheets; open the paths the run printed. `--clear` empties `screenshots/` once
this run's sheets are made (a stopped or failed run leaves the earlier ones); in a folder given with `--out` it removes only
the sheets render.py recorded there (`.render-sheets.json`, name and sha256) that are still as written. **Never pass
`--clear` unless the user asks for it** — keeping or removing their sheets is their call. `check.mjs` looks at
`screenshots/` like every other folder: the sheets pass because render.py records them in `generated.json`
(`.render-sheets.json` is plain text);
new_project.mjs puts it in the project's `.gitignore` (add it by hand in projects made before).

**Size and time:** tiles = range (s) × fps ÷ gap; sheets = tiles ÷ (cols × rows), rounded up. Time grows with the tiles,
plus one page load per job (not per sheet). Building the page is often most of a short run's time: every scene's
textures, shaders and art are baked at load, and without a GPU all of it is drawn by the CPU — so `--jobs 1` builds it
once per command, and many `--res 1080p` moments (one tile per sheet) cost one build plus each tile's own seek and
capture. So the moments one look needs go into one command (one `--at` list, one range), not one command each. A 41-minute video at `--gapframe 300` is about 490 tiles, 21 sheets.

**Choosing the gap**

| to see | gap at 60 fps |
|---|---|
| a transition, a flash, a one-frame jump, text colliding | 1–6 over 1–3 s |
| how one beat enters, holds and leaves | 15–30 over the beat |
| the build of a chapter | 60–120 |
| the whole video at a glance | 120–300 |

## 4. Sheets are how the agent looks
- **Work you do on your own** (the first build, an improvement you decide on, a redesign): make sheets yourself and look
  at them. Use the whole video, then each chapter, then the key moments and transitions (references/visual-review.md),
  and keep improving until a pass finds nothing. It is the one way you look at the picture — absolute: no screenshot code
  of your own, no ffmpeg frame grabs, no image another tool left. A clip the user gave you is looked at the same way:
  `render.py <clip> --screenshot --out <dir>/screenshots/clips/<key>`.
- **A fix the user asks for:** implement it, and don't shoot it (collaboration.md §3).
- **When the user wants to look at a stretch together** (or asks you to look): run the command for the range around
  their note with a gap from the table, or open the sheet images they made (ordinary image files; the shared folder
  makes them readable here).
- The player's **A** key copies that command for the moment on screen: `--screenshot --from t−1 --to t+1 --gapframe 10
  --fast --jobs 1 (check it with render.py from the script-to-motion skill)` (clamped to the video; no project name). The
  note in parentheses is for an agent it is pasted to: run `python3 render.py <dir>` with the options before it (in a
  terminal the user pastes it after `python3 render.py ` in the project folder, without the parenthesis). Without
  `--progress` the run prints only the sheets' full paths — open those images.
- Refer to tiles by the label under them (`485 0:08.08 [op02]`): that time and cue id are what the user pastes from the
  player, so a fix can be named exactly.
- A default tile is 480p: judge composition, timing, overlaps and flashes from it. Small type, a glyph, a thin line:
  the same command with `--at T --res 1080p`, or `--crop X,Y,W,H --res 4k` around it — never a frame of an MP4 or a
  browser screenshot.

## 5. Resume, stale chunks, fonts, footage
- Work goes to a temp folder per project + options. Ctrl+C (or `kill`) on a movie: each worker finishes its frame and
  closes its file, and the part made so far without a gap (finished chunks from the start + the next chunk as far as it
  got) is saved as `<name>_partial.mp4`; a second Ctrl+C stops at once without it. The same command then skips finished chunks /
  sheets; if the project's files changed in between (index.html, css, js, assets …), the old ones are dropped
  (`<dir>/screenshots/`, its own sheets, does not count as a change).
  `--fresh` drops them anyway and starts over (only the work folder of this command: the same project and options);
  a stopped `--fresh` run goes on with the same command minus `--fresh` (the stop message says so).
- Font check (default on): the DOM's visible text is asked which font files drew it (every 5 s of video in MP4 mode, every
  12th tile on a sheet) and every canvas `fillText`/`strokeText` is recorded with its font; a system font is reported as a
  warning under the chunk / sheet. `--no-font-check` turns it off.
- Footage (js/media-src.js) is filmed from frames cut beforehand: `node <skill>/scripts/stills.mjs <dir> --out
  media/render-stills --fps 60 --scale <s>` with s = 1 (1080p), 2 (4K), 0.6667 (720p) or 0.4444 (480p and sheets).
  Once the page is loaded, each worker checks the frames of every clip the page places (`__media.list()`) against this
  render before drawing: exactly the count at its fps, at least the width at its resolution. A clip declared in
  `media-src.js` but never placed needs no frames. Missing, smaller (scaled up → a blurry clip) or another count
  stops the run with the list and the command for this render; re-run, stills.mjs keeps what fits (larger cuts too — 4K
  frames serve 1080p and sheets) and cuts the rest again.

## 6. What it needs
Python 3 and ffmpeg (for MP4s and a video file's sheets, not a project's sheets; Mac: `brew install ffmpeg`); on
Debian/Ubuntu also `python3-venv` (without it `python3 -m venv` makes an environment with no pip — render.py makes it
again once, then stops with `sudo apt install python3-venv`). On the first
run it makes its own virtual environment in `~/.cache/motion-render-venv` (`MOTION_RENDER_VENV` to put it elsewhere;
Playwright + Chromium inside it) and runs itself from there; nothing goes into the system Python or the project.
`--no-venv` uses the current Python (Playwright must be installed there).
