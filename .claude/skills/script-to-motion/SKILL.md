---
name: script-to-motion
description: Turns a narration script (대본, 원고, 스크립트, 나레이션) — or just a topic, an article or a planning doc (기획서), which it researches, plans and writes into a script — into a narrated motion-graphics video that plays in the browser: HTML/CSS/JS scenes on a seekable GSAP timeline, synced to Fish Audio TTS in the user's own voice, delivered as a folder the user screen-records or films into an MP4 with the bundled render.py. Use it whenever someone wants a video, 영상, 모션그래픽, 설명 영상, 홍보 영상, 인트로, 유튜브/쇼츠 영상, an explainer or kinetic/expressive typography (글자가 깨지고·녹고·빛나는 타이포), even if they never mention HTML, GSAP or TTS. Also for revising such a project (script edits, re-timing, new takes, redesigns, review notes with a time and cue id); videos built on the user's screen recordings or generated clips (demos, AI-tool reviews, sponsored briefs); 6–10 minute videos in chapters; and beats that need real 3D (Blender MCP) or shader FX.
hooks:
  PreToolUse:
    - matcher: "Read|Bash|Write|Edit|MultiEdit|NotebookEdit"
      hooks:
        - type: command
          command: 'for d in "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_SKILL_DIR" "$CLAUDE_PROJECT_DIR/.claude/skills/script-to-motion" "$HOME/.claude/skills/script-to-motion"; do if [ -n "$d" ] && [ -f "$d/scripts/hooks/look_guard.py" ]; then exec python3 "$d/scripts/hooks/look_guard.py"; fi; done; exit 0'
---

# Script → Motion Video

Turn a script into a motion-design video whose runtime is the browser: the page *is* the video.
Narration is synthesized with Fish Audio, cue by cue — only when the user provides their Fish Audio API key and
voice id; otherwise the video is made without narration (step 4). The measured length of each spoken cue (or its
estimated reading time) becomes the timeline, and every animation is anchored to those cues. The user opens `index.html`, presses
play, and screen-records — or runs `python3 render.py <project>` (a single portable file; a copy sits in every project,
where it runs without the argument), which films the page frame by frame into an MP4 (no dropped frames, 480p, 720p, 1080p or 4K). Either way the deliverable is source code + audio, not a video file: don't render
the MP4 yourself or build another capture pipeline unless the user asks.

> **HTML only — the MP4 waits for the user (absolute, enforced in code).** Making a video means writing and checking the
> HTML project (`index.html`, `js/`, `css/`, `script.json`, the audio) and looking at it with `render.py --screenshot`
> sheets. **Never make an MP4** — not as a last step, not to "check" it, not because everything else is done — until the
> user explicitly asks for it ("MP4 만들어", "렌더링해 줘"). `render.py` refuses an MP4 run from an agent shell
> (`CLAUDECODE` set) unless the command carries `SUMO_RENDER_OK=1`: add that **only** for a request the user just made
> (`SUMO_RENDER_OK=1 python render.py <dir> --res 720p`; PowerShell: `$env:SUMO_RENDER_OK='1'; python render.py <dir> …`).
> At the end of the work say the HTML is ready, give its `file:///…/index.html` link, and offer the MP4 in one line.

Why this shape: in a browser the text stays real text (sharp at any resolution, including 4K
fullscreen), timing can be regenerated when the script changes, and the whole thing is editable code.

> **STOP before you write or change a single word of narration or on-screen copy. (absolute — no exceptions)**
>
> **A viewer hears each line once, in order, at speaking pace, and knows NOTHING you know**: not the docs, not the
> files, not `진행상황.md`, not the session, not the cue ids, not your labels, not the chat. Everything you hold in
> context is invisible to them. This is the mistake you make most naturally and the one the user has had to correct
> most often, because **to you every gap already looks filled**. Your own re-reading never finds it.
>
> So, for **every** line — first draft, one-word fix, batch edit, a line you think is obvious — before it is recorded
> or handed off:
> 1. Is **who / what / when / which** inside the line, not left for the listener to guess or to look back for?
> 2. Was the viewer **told every name and term** in it? No name that exists only in the production, no term used
>    before it is explained.
> 3. Does every **connective and back-reference** still point at the line right before it?
> 4. Does it **stand on sound alone**, with no picture?
> 5. Is every claim **in the record** (session, logs, files), not just what usually happens?
>
> **And wherever the topic changes — every seam — the cushion. A new topic NEVER starts cold.** Before the first line of
> a new topic, the listener must hear the old topic **closed**, a **turn** with a breath, and **where the talk goes next
> and why**, the reason grown out of what was just finished. A word that only marks a boundary is not a cushion. A seam
> can pass all five questions above, every word clear, and still land as sudden and out of nowhere (갑작스럽다,
> 뜬금없다) — the user has had to point this out again and again. **Every topic change gets a cushion** (below).
>
> Then the neighbours, the **seam pass**, the internal-name list and the **cold-listener review** by a subagent that
> has never seen the project. The full rule, the kinds of failure and the brief: **Every line is for a first-time
> listener** and **Every topic change gets a cushion** (below), and `references/script-writing.md` §0b. **Never skip
> them. Never trust your own reading of your own line, or your own sense that a seam "flows".**
>
> **There is no target length — not for the video, not for a chapter, not for a line. Saying what needs saying,
> correctly and completely, comes before any time.** Nothing the viewer needs (an explanation, a cushion, a step, a
> reason) is ever left out, shortened or squeezed because the video is getting long. **Content first, never time**
> (below).

> **And the picture: a crafted world from the first build. (absolute)**
>
> Correct timing and zero defects do not make a video attractive. A picture built as small diagrams and thin lines on a
> dark stage, with text beside them and the same layout chapter after chapter, stays unattractive however much it is
> polished afterwards, because polishing adds layers to the same compositions. So the quality is decided before the
> first frame is built: **the first build is already cinematic** — for every kind of video the skill makes: one designed
**world** the camera travels through, real **material**,
> one motivated **key light** per scene, **depth** in planes, a **camera language chosen for this world** that moves for
> a reason, **type made of the world's material** — and **a world, palette, light and camera chosen for this subject**,
> never the same choices as the last film. Write the **world bible** before the shot list, prove it with **look-dev hero frames**, then
> build. Never accept the infographic look, and never try to repair it by decorating. **A crafted world from the first build**
> (below) and `references/cinematic-look.md`.

`<skill>` below means this skill's directory.

## What you deliver

```
<project>/
  index.html            scenes (you write)
  css/style.css         art direction tokens + styles (you write)
  js/scenes.js          the timeline (you write)
  js/art/*.js           illustration modules (optional; core.js comes with the template — references/art-library.md)
  js/fxkit.js, css/fxkit.css   seekable effects kit (from the template; FXKit.install(ctx) — references/fx-kit.md)
  js/typefx.js, css/typefx.css expressive typography system (from the template; TypeFX.install(ctx) — references/type-fx.md)
  glyphs.json + js/glyphs.js   glyph outlines of display lines (optional; text_to_paths.mjs, from catalogue OFL fonts)
  js/cues.js            cue timings (generated)
  js/sync.js            phrase times per cue (generated by sync.mjs from the times you set in script.json "at"; cue(id).when() uses them)
  js/player.js, css/player.css   runtime (from the template)
  render.py             MP4 / contact-sheet maker the user runs (from the template; one portable file — `python3 render.py
                        [<project dir | index.html>]`; Python 3 + ffmpeg, its own venv) — references/render.md
  js/media-src.js + js/media.js  footage on the master clock: the user's recordings / generated clips (references/footage.md)
  js/reckit.js, css/reckit.css   screen recordings without zooming: browser window, dim-the-rest spot, pinned callout
  css/look.css          opt-in studio finish: key light + floor, grade, vignette, glass monitors (craft-notes.md §4)
  js/seg/<id>.js        (long videos) one builder per chapter, called from scenes.js (references/long-form.md)
  vendor/gsap/          GSAP 3.15.0 — not stored in the skill: new_project.mjs downloads it from the npm registry
                        (integrity + sha256 checked, unmodified, notices intact; GSAP Standard "no charge" License)
  fonts/                core SIL OFL 1.1 fonts — Pretendard, D2Coding, Noto Sans KR — downloaded from their official
                        sources by new_project.mjs, sha256-verified, unmodified, with their OFL licence files
  (extra fonts) css/fonts.css + fonts/<id>/ (+ fonts/fonts.lock.json for Google Fonts families)   add_font.mjs —
                        SIL OFL 1.1 only: the catalogue or google/fonts ofl/, downloaded, verified, unmodified
  audio/narration.mp3   full narration used by the player (+ narration.wav, cues/<id>.wav)
  script.json           cues: what is said / shown (+ "chapters": the chapters' question titles)
  script.txt            the script as plain text — each cue's text on its own line, no ids or times (generated by tts.mjs)
  storyboard.md         the plan (audience, message, spine; a planning doc's requirement table), the world bible
                        (world, light, materials, depth, type as material, camera — references/cinematic-look.md),
                        art direction, beat per cue
  research.md           (when you researched) sources per fact, what you added, what disagreed (script-writing.md §0)
  (user assets) assets/user/ + provenance.json   only files the user provided — everything else is drawn here
  generated.json        the files the skill's tools wrote (narration, takes, stills, sheets, movies, models, three.js)
                        with its sha256 — written by the tools only (lib/generated.mjs, render.py)
  (optional) licenses/cokacmotion-LICENSE.txt   when a block of code is substantially a cokacmotion demo's (MIT)
  (footage) media/master/ (full-quality sources, may be a symlink) · media/stills/ (review frames, stills.mjs)
  (3D only) vendor/three/ (classic Stage3D or FX StageFX build), models/<name>.glb.js, assets3d/<name>.py|.blend|.glb|mcp-calls.jsonl
```

It plays offline from `file://` — no server, no CDN.

## Working with the user (read first: references/collaboration.md)

- **Every line you write or change is for a first-time listener** (the box above; **Every line is for a first-time
  listener**, absolute). That includes a line the user asks you to fix, a reply you draft for them, and every word of
  on-screen copy. Your context is not theirs. **And every topic change gets a cushion** (absolute): no new topic, group,
  example or chapter ever starts cold.
- **A question gets an answer, not a work session.** Answer with the facts and stop; propose a change in one line and
  wait for the go-ahead.
- **Report numbers completely** — every factor that changed a result, everything that is not done.
- **A fix the user asks for: implement it, don't measure it.** Change the code and run the cheap gates (`check.mjs`,
  `errscan.mjs`; read `wave.mjs` for dead air when sound or timing changed, `check_fonts.mjs` when text changed). Don't shoot or measure the result. Say
  what changed at which time and cue id. Notes arrive as `0:55.12 / 9:13.99 [op05] 대사…` (the player's S key).
- **Work you do on your own: look at it with `render.py --screenshot`, and improve it until it is right.** This covers
  the first build, anything you decide to improve, and a redesign you carry out.
  - The command is `python3 <dir>/render.py <dir> --screenshot --from A --to B --gapframe N`. It films 480p frames,
    every N-th, the same way it films the MP4, into grids with frame · time · cue under each in `<dir>/screenshots/`,
    and prints the sheets' full paths: open them. Sheets pile up there (each name holds its run time and what it
    shows; nothing is removed), so open the paths this run printed. `--clear` removes earlier sheets: never pass it
    unless the user asks for it.
  - A clip the user gave you is looked at the same way: `render.py <clip file> --screenshot`.
  - It is the only way you look at the picture — absolute, every situation, every agent (next section).
  - The player's **A** key copies such a command for the moment on screen. When the user pastes it, they are asking
    you to look.
- **The user makes the MP4** — by screen recording or with the project's `render.py`. Don't render an MP4 yourself
  unless asked (HTML only, above), and don't remind that a file is stale. When the user does ask: `SUMO_RENDER_OK=1`
  before `python render.py <dir> …` (the guard in `render.py` refuses an agent's MP4 run without it).
- **Re-create, don't decorate**: a design request rebuilds the scene from a concept; big jobs go chapter by chapter.
- **A crafted world from the first build** (absolute, below): a lit, material, deep world with a moving camera — never
  the infographic look of thin lines and small diagrams on a dark stage. Each technique is drawn from the user's
  technique library (cokacmotion) — step 5.
- **Finish everything; only the recording waits.** From a script, a topic or a planning doc, research, plan, write,
  build, verify **and elevate** the whole video on your own (step 7b: an art director scores direction, graphic design
  and motion on render.py sheets, and you rebuild until it is designed, not just defect-free). Don't stop to ask, and
  don't wait for the lines to be approved. The one
  thing you never do on your own is record the user's voice, because it is their voice and their credits. The finished
  video plays with silent placeholder narration and captions. The user reviews it and decides whether to record; then
  run `tts.mjs --approved` (step 4).
- **The narration (the TTS takes) and every clip with sound are always at 1×.** This holds everywhere: when they are
  generated, in the code you write, when they play for a recording, and in `render.py`.
  - No take or narration file uses a TTS speed, a speed tag (`<fast>`/`<slow>`) or a time-stretch.
  - The project's code never sets a playback rate (`playbackRate`, `defaultPlaybackRate`; `check.mjs` errors on it).
  - A clip with sound needs `rate` 1, and `media.js` refuses anything else.
  - A *silent* clip may run faster or slower through `M.clip(…, { rate })` (references/footage.md).
  - `render.py` puts the original audio into the MP4 at 1×, and **R** (restart, pressed to start a screen recording)
    resets the player to 1×.
  - The player's Shift+>/< keys only speed up *viewing* while the user reviews, and that is fine.
  - A rushed take gets pauses in its `say` (`,` or `...`) or a fresh take (references/fish-audio.md).
- **Keys** (Fish Audio) live in the skill's git-ignored `.env`; never in a tracked file, output or memory.
- Reply in the user's language, every line including progress notes. Keep `진행상황.md` (decisions, files, what's left).
- **Never PPT or document design**: no boxes, cards, bullet lists or tables holding text (the next section).

## Looking at the picture: only `render.py --screenshot` (absolute)

**Whenever you look at the video, or at anything it draws, you look at a render.py sheet: nothing else, ever.**
`python3 <dir>/render.py <dir> --screenshot …` films the page exactly the way the MP4 is filmed and prints the sheets'
full paths; open those images and no other. There is no exception for speed, size, debugging, "just one frame" or
"just to check a pixel": every need has its option.

| to see | command (`python3 <dir>/render.py <dir> --screenshot` + …) |
|---|---|
| the whole video · one beat · a transition frame by frame | `--gapframe 120` · `--from A --to B --gapframe 30` · `--from A --to B --gapframe 1–3` |
| exact moments (a warning's time, the frame the user named) | `--at 11.5,23` |
| small type, a glyph, a thin line, 4K sharpness | `--at T --res 1080p` (one stage-size tile per image) · `--at T --crop X,Y,W,H --res 4k` (a stage rectangle, 2×) |
| a frame that differs when reached another way (`snapshot.mjs --seekcheck` prints this command) | `--at T --via SEC`: [in order \| from SEC \| difference], the differing pixels marked and counted |
| one illustration module (`js/art/*.js`) on its own | `--art NAME --viewbox "X Y W H" --at 0,0.6,1.2 [--state JSON] [--opts JSON] [--group]` |
| a clip the user gave you, a screen recording, a rendered MP4 | `python3 <dir>/render.py <clip file> --screenshot …` — the same `--from/--to/--gapframe`, `--at`, and for detail `--res 1080p` or `--crop X,Y,W,H` in the file's own pixels (1:1) |
| before / after a change | the same command twice, `--out <dir>/screenshots/before` and `--out <dir>/screenshots/after` |

A project made before these options has an older `render.py` that does not know them: copy the skill's over it
(`cp <skill>/assets/template/render.py <dir>/render.py` — one portable tool, the same for every project; `check.mjs` warns
when the copy differs). An unknown option is never a reason to look another way.

**Never** — in the main session or in any subagent:
- write or run code that takes a picture: Playwright/Puppeteer `page.screenshot` / `locator.screenshot`, a CDP
  `Page.captureScreenshot` or screencast, `chrome --screenshot`, html2canvas, a canvas dumped to a file — not in a
  scratch folder, not to debug, not "once";
- grab frames from the MP4, a render or a clip with ffmpeg (or anything else) to look at them;
- open an image that no render.py --screenshot run printed: probe PNGs, preview folders, `.snapshots/` leftovers, diff
  images you made.

The skill's other tools measure and write no picture: `snapshot.mjs` (layout warnings, `--seekcheck`, `--safezone`,
`--perf`), `preview_art.mjs` (a module's determinism and console errors), `errscan.mjs`, `check_fonts.mjs`. Each prints
the render.py command for the moment it reports; run it and open the sheet. `scripts/lib/browser.mjs` refuses to take a
picture for any script but the skill's own tools. A guard (`scripts/hooks/look_guard.py`) blocks opening a non-sheet
image of a video project or a scratch folder and running or writing screenshot code: SKILL.md's own hook registers it
for this session once the skill is invoked, and `new_project.mjs` puts it into the Claude Code project's
`.claude/settings.local.json` (`scripts/hooks/install_guard.mjs`; local, not committed), the only place it also reaches
subagents. Working on a project that was made without it, run `node <skill>/scripts/hooks/install_guard.mjs` once and
say so in one line. If render.py cannot show something you need to see, tell the user what is missing; never build a
way of your own. **Every brief you give a subagent** (an illustration worker, a chapter builder, a reviewer) still
carries this section word for word.

## No slides, no boxes: motion design, never a document (absolute)

**Never build the video as PPT or document design, with the content laid out in boxes.** The user rejects this outright,
however well it is timed and however clean it looks. It is banned in every scene, aspect, tone and length:
- a title bar with content under it;
- rounded cards or panels holding text, alone or in rows, 2×2 or 3-column grids;
- icon + heading + description cards, KPI/stat tiles, callout boxes, text boxes — any bordered or filled container
  whose job is to hold text;
- bullet lists and numbered lists set as text, tables, box-and-arrow flowcharts and org charts, timelines made of
  boxes, agenda or table-of-contents slides;
- scenes that behave like slides: a layout appears, its boxes fade or slide in one by one, then the next layout
  replaces it.

**Instead, the content itself is the picture, on the open stage:**

| instead of … | show … |
|---|---|
| a heading in a bar, text in a box | the key word or number set large, directly on the stage. Hierarchy comes from scale, weight, colour, space and depth, never from a border or a fill |
| a bullet list | items that arrive as they are spoken, as objects or acting type; earlier ones change state |
| two cards side by side | the two things themselves in space: sizes compared, a scale tipping, one turning into the other |
| boxes and arrows | one object travelling a path and changing state at each step |
| stat tiles, a table | the numbers as hero type or as material (stacks, fills, pours) with a one-line takeaway |
| slide after slide | one continuous world: camera moves, match cuts, the recurring visual idea |

**The only boxes allowed are objects in the story.** Examples: a browser window showing the user's recording
(RecKit), a phone or a monitor, a sheet of paper, a memo, a sign, a ticket. Each is drawn as a thing with material,
light and shadow, sitting in the world. None is ever a container for laying out text.

**Test every frame:** take the motion away. If the frame would pass as a slide or a document page, redesign the
scene. Check this in the storyboard (step 5) and again in the review (step 7). See references/motion-design.md §10.

## A crafted world from the first build: the cinematic look (absolute)

**The first build is the film, not a draft to be rescued later.** Every frame aims at a still a motion studio would put
in its reel. Correct timing and zero defects are the floor; they never make a frame good. A build that starts as
diagrams on a stage cannot be polished into a film later: an elevation pass that adds layers to the same compositions
changes nothing a viewer can see, so the look has to be right from the start.

**The infographic look is a failure, not a style** — redesign any frame that shows it:
- thin vector lines, outlined circles and small icons floating on a flat dark gradient;
- a small diagram in the centre with a number or labels beside it, the same two-column layout chapter after chapter;
- the subject drawn at 30 % of the frame when it is what the line is about;
- trying to improve such a frame by adding small effects or more labels to the same composition.

**What every scene has instead** (how each is made: `references/cinematic-look.md` §3):
- **a world**: the film happens in one designed world — physical, illustrated, graphic, typographic or the product's
  own set (cinematic-look.md §2) — chosen from the content and its purpose, each chapter or section a place or an
  object in it, never a backdrop behind a diagram. This holds for every kind of video: explainers, promos and brand
  films, intros, shorts, kinetic typography, demos built on recordings, sponsored briefs, data stories;
- **material** on everything that matters: a baked texture, relief shaded by the key light and the surface's own
  response to light — never a flat fill;
- **one key light per scene**, motivated by something in the world, giving rims and contact shadows; the focal object
  is the brightest thing; one finish for the whole film, chosen for its world (a grade, a vignette, bloom on the
  brightest parts, grain — or none; whatever suits this world);
- **depth** in several planes with focus and haze; attention moves by a focus pull or the camera, not by crossfading
  layouts;
- **a camera language chosen for the world** — angle, lens, distance and how it moves — that shows space rather than a
  flat diagram plane and moves for a reason in the words; the subject dominates the frame when the line is about it;
- **type made of the world's material** — hero words and numbers built the way that world would make them and lit by
  its key light, large for heroes (motion-design.md §2), sitting inside the scene rather than floating over it.

**The order of work:** the **world bible** at the top of `storyboard.md` (step 5) → **look development**: one hero frame
per chapter built to the bar and passed by the art director at 1080p → the whole build (long films: one builder per
chapter with **join contracts**) → the elevation pass against the same absolute bar (step 7b).

**Test every frame twice:** take the motion away — it must not read as a slide (**No slides, no boxes**); shrink it to
850 px next to the obvious, literal version of the same line — background, hero size and composition must all be
visibly different.

**Never the same film twice:** the bar is raised by the standard and the process, never by a fixed look. The world,
palette, key light, finish, camera language, materials and signature transition are chosen anew from each subject.
Choices that tend to carry over from one film to the next (the same background tone, accent colour, finish, camera
angle and lens, kind of material, transition) are named in the world bible and changed unless this subject itself calls
for them; the art director flags a film that repeats earlier ones (references/elevate.md). Nothing in the template
imposes a look.

**Calm, not busy:** production value comes from the world — material, light, depth, camera, type — never from more
effects; the owner's taste for one clear idea, one impact per peak and no shake still holds (craft-notes.md).

## Every line is for a first-time listener: never the producer's shorthand (absolute)

**A viewer hears each line once, at speaking pace, in order, and knows nothing you know.** They have not read the
skill's docs, the project's files, `진행상황.md`, the storyboard, the session, the cue ids, your working labels or the
chat with the user. **Every line of narration and every word of on-screen copy must make complete sense to that person,
on its own, by sound alone.** This is the user's most repeated correction, and it is the agent's most natural mistake:
you hold all the context, so to you every gap looks filled, and re-reading your own line with the same context never
shows the gap. **Never trust your own reading of your own line.** Run the gates below, every time. There is no
exception for a short line, a one-word fix, a batch edit, "the screen shows it", a line that "everyone knows", or
time pressure.

**Never write any of these** (script-writing.md §0b explains why each one happens and how to catch it):
1. **A line whose subject, object or occasion is left outside it.** Korean lets a sentence drop who acts, on what, and
   when. A reader looks back and fills the gap; a listener cannot. A line that leans on something the listener never
   heard, or heard long before about something else, cannot be understood. When an earlier part of the video spoke
   about something similar, the listener hears the unanchored line as being about that earlier thing.
2. **A name that exists only inside the production.** The names you and the user use while working (cue ids, nicknames
   for demos and trials, file and folder names, variable names, labels from your notes) mean nothing to a viewer. They
   never appear in narration or on screen unless the narration first said what they are.
3. **A term used before it is explained.** Any word the viewer needs in order to follow the line (a technical term, a
   program or file they will have to use, an element on screen being pointed at) is explained in plain words the first
   time it is heard (script-writing.md §3).
4. **A connective or back-reference that no longer points where it should.** Words that answer the line before (meaning
   "instead", "so", "then", "this way", "as said earlier", "also") are tied to that line. Changing a line can leave the
   next one answering something that is no longer there. Two neighbouring lines that open with the same connective
   sound like a stutter.
5. **A heading read aloud.** A step announced, or a thing named, with a bare "noun + is" sentence, the shape of a slide
   title or a menu label. The listener hears a label instead of an explanation. Say what happens: the action and its
   result.
6. **A line cut down to keep it short.** No line has a length it must fit. Removing the words that carry the meaning
   to keep a line or the video short trades understanding for nothing. A long sentence is split into cues, never cut
   (**Content first, never time**).
7. **A line that only works with the picture.** You design the line and the screen together, so you read them as one.
   The viewer may not read a label while listening. The screen may show the example; the sentence must carry its
   meaning by sound alone.
8. **A sentence carried over from a document.** A sentence taken or translated from the skill's docs, a tool's help or
   a source keeps its words but loses the paragraph that said what it was about. Write from the question the viewer
   has at that moment, not from the source's sentence.
9. **A claim about the process that the record doesn't show.** This means describing what the agent or the user did
   from what usually happens in such a flow, instead of from what the session, the logs and the files show. A plausible
   step that did not happen is a false line.
10. **The agent's register instead of the narrator's.** The agent's default explainer voice (short announced steps,
    labels, a past-tense anecdote of one run) is not the narrator's voice. When the user has written or dictated lines,
    their sentence shape, endings and tense are the model (script-writing.md §5b). A tutorial explains how the tool
    works, in the present; the run you show is the example on screen, not the story.
11. **A new topic with no cushion.** The talk moves to another topic, group, example or kind of thing and the next
    line simply starts it: nothing closed what came before, nothing marked the turn, nothing said why this comes now.
    Every word can be clear and the seam still lands as a jump. This has its own section and its own gate: **Every
    topic change gets a cushion** (below).

**The gates — before any line is recorded, and before every hand-off:**
1. **Per line, by you:** the five questions of script-writing.md §0b. Who/what/when is inside the line? Any name or
   term the viewer was never told? Does each connective still point at the line before? Does it stand on sound alone?
   Is every claim in the record?
2. **After any edit:** read the changed line together with the line before and the line after it, as a stranger.
   **The seam pass** (**Every topic change gets a cushion**, below) on every seam of the script, and again on every
   seam an edit touched.
3. **The internal-name list:** write down by hand every name that exists only inside the project (cue ids, trial and
   episode nicknames, file and folder names, labels from `진행상황.md`, `storyboard.md` and code comments), then find
   each one in the narration and every on-screen string and read it in its line (script-writing.md §0b). No pattern
   matcher does this for you: only you know which names are yours.
4. **The cold-listener review:** a separate subagent that has never seen the project gets only `script.txt` (the lines
   in order, nothing else) and the brief in script-writing.md §0b, word for word. It reads it once, top to bottom, and
   returns every line where it cannot tell what, which, when, who or why, and every place where the talk jumps to a
   new topic without a cushion.
   - Fix every flagged line you wrote, then run the review again on the stretch you changed.
   - A flagged line the user wrote or dictated is not reworded: tell the user in one line and propose a fix.
   - Run it on the first draft, and again on every stretch you rewrite, before recording it.
   - When no subagent can be started, do it yourself as a separate written step from `script.txt` alone, reading as a
     stranger, and say so in the hand-off.

Every brief you give a subagent that writes or edits narration or on-screen copy carries this section word for word.

## Every topic change gets a cushion: no new topic out of nowhere (absolute)

**The listener follows the talk in time. Letting go of one topic and taking up the next takes a moment of speech, and
only the narration can give it.** When the next line simply starts a new topic, the listener is dropped into it: the
user hears it as sudden, abrupt, out of nowhere (갑작스럽다, 뜬금없다), even when every word is clear. In one video the
user had to point this out again and again: a new group of player keys started right after a side remark about
recording; a live demonstration started right after the explanation of how it works; a chapter opened by naming the
next method without closing the one before; a bridge hooked onto a clip heard minutes earlier instead of the chapter
that had just ended; a fix clarified a vague word at a seam and left the seam as sudden as before. **A new topic never
starts cold. There is no exception** for a chapter card on screen, a short video, a line the user "only" asked to
reword, a batch edit, or a seam that looks smooth in the script.

**Why you miss it (read this; it is how you catch yourself):**
- **You think in an outline.** In your plan and in `storyboard.md` the topics are separated by headings, numbers and
  white space, and those carry the reader across. Speech has none of them: nothing carries the listener unless a
  sentence does. Turning a heading into a word that only marks where a section begins feels like a transition to you;
  to the listener it is a jump.
- **You judge a bridge by its information.** A cushion says nothing new, so to you it looks like filler, and you cut
  it, shorten it or squeeze it into the first sentence of the new topic. Never. A cushion does a job no other line can
  do: it lets the listener close one topic and open the next. This skill once taught you to cut lines that lead into
  what comes next and to fold bridges into the first content sentence; that teaching was wrong and has been removed.
  If you remember it, or meet it in an older copy of this skill, ignore it.
- **You read the whole script at once.** A purpose stated minutes earlier sits right beside the new topic in your view,
  so the link looks obvious. The listener heard it long ago, with many other things in between; for them the link is
  gone unless the narration renews it.
- **You edit locally.** Inserting a line in front of a seam (a caveat, an aside, a promise to come back to something
  later) or deleting the line that closed a topic moves or breaks the seam. You check the line you touched; nobody
  checks the seam unless you do.
- **You check meaning, not movement.** The per-line checks look for missing information. A seam can be complete in
  meaning and still sudden. **When the user says a line is abrupt or comes out of nowhere, it is about how the talk
  moves, not about a missing word: clearer wording does not fix it, a cushion does.** Don't answer that note by
  explaining what the line means.
- **You treat the narrator's turn word as style.** In the user's own lines, their turn word (the word they open a new
  beat with) sits exactly where the topic changes, after a breath. It is the device that turns the talk, not a habit
  to sprinkle or to drop.

**Where the seams are — each of these is a seam, and each one gets its cushion:**
- the start of every chapter, including where a chapter card shows the title: the card shows the question, the voice
  still has to close the last chapter and turn;
- inside a chapter: a move to another group or kind of thing (another set of features, keys or steps with a different
  purpose), from explaining something to demonstrating it, from a demonstration to its lesson or tips, from one
  example to another (one demo to the next; a demo to the very video the viewer is watching);
- right after a side remark, a caveat or a promise to cover something later: the next line must not sound like the
  promised thing unless it is;
- the return from a side remark to the main line;
- where another clip starts, where it ends, and where the narrator hands over to a clip's own sound;
- before the closing.

**What a cushion is made of** (in the narrator's voice; one sentence or two cues; never squeezed to fit a length):
1. **Close** what was just covered, as a whole, under a name the viewer can recognise from what they heard (never a
   label from your outline or notes).
2. **Turn:** the narrator's own turn word where they have one, with a breath before it (the gap after the previous
   line longer than inside a thought, the whole silence still under the dead-air limit — step 3).
3. **Open:** where the talk goes now **and why now**. The reason grows out of the topic just finished: what it leads
   to, what is still missing, what has to happen before the next step. Reach back to a purpose stated earlier only
   when that purpose is the reason, and then say the purpose again.
4. Then the first line of the new topic.
- **A boundary word alone is never a cushion.** A word that only says "from this point", "next" or "now" is a
  document's section mark spoken aloud. It never stands in for the close, the turn and the open.
- **A cushion is never cut, shortened, merged into the next line or squeezed into the first content sentence of the
  new topic.** Nothing in this skill asks you to remove a line because it leads into what comes next.
- **When the first line of the new topic is the user's own,** the cushion goes in front of it as a line of your own
  in their voice; their line stays as written. If you are unsure, propose the cushion to the user in one line.
- **The picture turns too.** What belonged to the old topic leaves or steps back (gathers, dims, is set aside) before
  the new topic's first element arrives, and nothing of the old topic lingers on screen as an unexplained leftover.

**The seam pass — a gate, as mandatory as the first-time-listener gates, before any line is recorded and before every
hand-off:**
1. From `script.txt`, write down every seam in order, by the kinds listed above. Do this by reading, not by searching
   for words: only reading tells you where the topic changes.
2. At each seam, read the last line of the old topic and the first two lines of the new one as a stranger hearing them
   in time. Check that all three parts are there: closed, turned, opened with a reason from what just finished. A
   missing part is a failure even when every word is clear.
3. After any insert or delete, find the seams it touched (the seam it now sits in front of, the seam whose closing line
   it removed, the seam it created) and pass them again.
4. The cold-listener review (script-writing.md §0b) also reports abrupt topic changes. Fix a flagged seam with a
   cushion, never by clarifying the words around it, and run the review again on that stretch.
5. A seam the user flags is a rule for the whole script: pass every seam again, not only that one, before you answer.

Every brief you give a subagent that writes or edits narration carries this section word for word.

## Content first, never time (absolute)

**This skill sets no length for anything: not for the video, not for a chapter, not for a line.** The length is
whatever it takes to say what the viewer needs, correctly and completely, for someone hearing it once: every term
explained, every topic change cushioned, every step and every reason the viewer needs to follow. **Time never decides
what is said.**
- **Never leave out, shorten, merge or skip** an explanation, a cushion, a step, a reason or an example because the
  video, a chapter or a line is getting long. Not to meet a number in your own plan, not to stay near an earlier
  version's length, not because a cue feels long, not to keep a stretch brisk.
- **Never plan to a length.** Don't put a target length in `storyboard.md`, and don't size the script by cues per
  minute or syllables per second. Plan what has to be said; the length is the result.
- **A long sentence is split into cues, never cut.** A line that is long because it carries what it must carry stays
  whole in meaning.
- **When the user named a length** (in the request or a planning doc) and saying it properly takes more, keep the
  content and tell the user how long it came out and why. Never cut silently to fit. If the user then asks for a
  shorter video, decide with them what goes, topic by topic; never by thinning every line.
- **The pacing rules are about how the words sound, not how many there are.** The breath between lines and the limit
  on dead air (step 3, references/sound.md) never justify removing words.
- **If you remember a default length, a cue length in seconds or a words-per-minute budget from an older copy of this
  skill, ignore it.** They were removed because they made lines and bridges disappear.

Every brief you give a subagent that writes or edits narration carries this section word for word.

## Originality: every resource is made here, 100% original (absolute)

**Everything that makes up the content is created by you, from scratch, for this video — unless the user
explicitly names or provides it.** No exceptions for convenience, speed or "it's only small". This covers every
illustration, character, creature, vehicle, icon, logo mark, background, texture, pattern, map, diagram, chart,
3D model and material, animation and effect, layout and visual concept, the narration you write, titles and
on-screen copy, and any sound.

**What you may use**
1. **What the user explicitly provides or names** — their files (logo, photos, product shots, brand guide, data,
   script) or a specific source they tell you to use. Use it as given and only for what they asked. Put the files
   in `assets/user/` and record each one in `provenance.json` (below).
2. **Tools, which are not content** — the SIL OFL 1.1 fonts (Fonts below), GSAP and three.js, Blender. They render
   your original work.
3. **Techniques from the cokacmotion library**, this skill's technique reference (references/cokacmotion.md):
   - **carries over:** how an effect is built — the algorithm, the shader, the bake, the easing structure. Its MIT code
     may be adapted, with a source comment;
   - **never carries over:** what a demo depicts — subject, scene, composition, copy, colours, the 9:16 frame.
4. **Facts and data from research** — facts are no one's expression, but the wording, structure and
   visualisation are yours. Note your sources in the project's `research.md` (script-writing.md §0); never copy sentences from them
   (a short quote only when the user wants it, with attribution).

**What you never use unless the user explicitly asks for that specific thing**
- images, photos, illustrations, icons or icon sets (Font Awesome, Material Icons …), clip art, emoji art, stock
  footage, GIFs, Lottie files, music or sound effects — from the web or anywhere else;
- 3D models, HDRIs, textures or materials from asset libraries (Sketchfab, Poly Haven, TurboSquid …) — build them
  in Blender with your own scripts or in code;
- output of external generative services (image, video, music, voice other than the user's Fish Audio voice, 3D):
  it is not made here;
- tracing, copying or closely imitating someone else's artwork or a specific video's look, or reproducing
  characters, mascots, logos or trademarks the user didn't provide — even redrawn by hand. If the story names a
  brand, a product or a person, use only what the user gave you, otherwise a neutral stand-in or a typographic
  treatment of the name, and ask for the official asset if it matters;
- map shapes, vector data or diagrams copied from elsewhere: draw maps and diagrams yourself, stylised to what the
  piece needs;
- text copied from websites, articles or encyclopedias: write it in your own words.

When unsure whether something counts as original, make it yourself or ask the user. Everything you draw lives in
code (inline SVG, CSS, canvas, `js/art/*.js`, Blender scripts in `assets3d/`), so its origin is visible.

**Provenance is checked — every file, by what it is, never by its name or folder.** `check.mjs` accepts a file in the
project (all of it but `.git/`, links followed) only when it is one of these:

- **the user's**, listed in `provenance.json`:
  ```json
  { "assets": [ { "file": "assets/user/logo.svg", "source": "user", "note": "client logo, given in chat on 2026-10-03" } ] }
  ```
- **written by a tool of the skill**, recorded in `generated.json` with the same sha256. The tools record what they
  write: `tts.mjs` (takes in `.tts-cache/`, `audio/`), `stills.mjs`, `enable_3d.mjs` (the
  three.js build in `vendor/three/`), `embed_glb.mjs`, `blender_mcp.mjs run` (what Blender wrote into `assets3d/`
  during the run) and `render.py` (movies, sheets). Never
  write or edit `generated.json` yourself, and never replace a recorded file: run the tool again.
- an installed **font** or **vendor** file, unmodified (sha256 pinned in `fonts/fonts.lock.json`, the catalogues);
- **plain text** the project is written in (.html .css .js .json .md .txt .srt .py …, valid UTF-8). In it, these are
  refused: a `.json` that is a Lottie animation (the Lottie spec's `w h fr ip op layers`), and in .html/.css/.js a
  `data:` URL of an image, video or audio — except an SVG written readably (`data:image/svg+xml;utf8,<svg …>`, only
  `#` escaped as `%23`, or an empty literal the code fills at run time);
- an empty file, or a file the operating system keeps (`.DS_Store`, `._*`, `Thumbs.db`, Python's `__pycache__`),
  recognised by its format.

Everything else fails. A tool's output from before the tools kept `generated.json` fails too: run that tool again
(`stills.mjs`, `render.py`, `tts.mjs` for `audio/`); cached takes in `.tts-cache/` cost credits to
record again, so ask the user and, with their OK, run `tts.mjs <dir> --record-cache` once (it records only the cached
takes of the script's own cues). `embed_glb.mjs` takes only a `.glb` recorded from a Blender run or declared as the
user's. What the page loads from the network is seen where it really runs: `errscan.mjs` reports every request that
isn't to the project's files, and `render.py` stops on one. In the hand-off, say that all visuals were made for this
video and list the user-provided assets.

What no check can see: someone else's artwork copied into code (SVG path data pasted inline, an image turned into a
pixel array in a script). That stays your rule to keep: draw it yourself.

## Fonts: SIL OFL 1.1 only, downloaded on demand (important)

### The licence rule — absolute

**Every font that draws text in a video must be licensed under the SIL Open Font License 1.1 (OFL 1.1).
No other licence is acceptable, ever.** This covers every glyph the viewer can see: headlines, body,
numbers, labels, captions, HUD text, SVG `<text>`, canvas `ctx.font`, text textures in 3D/FX scenes, glyph
outlines (TypeFX shards, jamo, melted or extruded letters) and text drawn as pixels (TypeFX raster type).

- **Not allowed**, whatever the reason: Apache 2.0, Ubuntu Font Licence, GPL/LGPL (with or without font
  exception), CC licences, public-domain claims, "free for commercial use" freeware with its own terms
  (most Korean 무료 폰트 sites, 눈누-listed fonts with custom licences, 상업용 무료 폰트), fonts bundled
  with an OS or an app (system fonts), hosted web-font CSS/CDNs (Google Fonts/Adobe Fonts links), and
  fonts whose licence merely resembles the OFL. If the licence file of a font is not the SIL OFL 1.1
  text, the font does not exist for this skill.
- **No exceptions on request.** If someone asks for a specific non-OFL font, explain the rule, name the
  closest OFL 1.1 font (catalogue or Google Fonts `ofl/`, references/fonts.md), and do not install it.
- **Unmodified only.** OFL fonts are used exactly as published by their official source: no subsetting,
  renaming, re-hinting or format conversion (Reserved Font Names forbid it). Integrity is proved by sha256.
- **Drawing with the font is use, not modification.** Outlines read from the installed, unmodified file to
  draw the video's own lines (`text_to_paths.mjs`) and text rasterised on a canvas (`TX.raster`) are artwork
  made with the font (OFL FAQ 1.1/1.1.1: graphics, video titling, 3D shapes). Only through those tools, only from
  installed OFL fonts, only the lines the video shows — never a converted character set or font file.
- **With the licence.** Every font travels into the project with its OFL 1.1 licence file; if the project
  folder is shared, the licence files stay with it.

The tooling enforces this and has no override: a catalogue entry whose `license` is not `SIL OFL 1.1` is
refused; a Google Fonts family outside the repository's `ofl/` directory (Apache, UFL), or whose METADATA or
OFL.txt is not the OFL, is refused; a licence file that is not the OFL 1.1 text is refused; `check.mjs` fails on any
font file in the project that is not an unmodified catalogue file or a file pinned in `fonts/fonts.lock.json`, on
any licence file that is not OFL 1.1, and on any font name that isn't an installed family.

### Where the fonts come from — two sources, both on demand

**The skill ships no font files.** A project gets its fonts from:

1. **The catalogue** (`assets/fonts/catalog.json`): seven curated families with the pinned official source and
   sha256 of every file — including the three **core** fonts every project gets. Install extras by id.
2. **Google Fonts, `ofl/` only**: any family in the google/fonts repository's `ofl/` directory, by its name —
   `add_font.mjs <dir> "Do Hyeon"`. METADATA.pb must say OFL and the family's OFL.txt must be the OFL 1.1 text.
   The google/fonts commit and every installed file's sha256 are written to `<project>/fonts/fonts.lock.json`,
   so the check tools can verify the files and a re-install reproduces them exactly.

Both download only when needed, verify, cache in `~/.cache/motion-video-fonts/` (override with
`MOTION_VIDEO_FONT_CACHE`), and copy the files **unmodified** with their licence into `<project>/fonts/<id>/`,
writing the `@font-face` rules to `css/fonts.css`. Later projects reuse the cache. With no network and an empty
cache the scripts stop with an error — **never** substitute another font, a system font or a "similar" file. A
hash mismatch means the official file changed or the download is corrupt: stop and report it. The project must
contain its fonts (it plays from `file://`); no CDN or web-font links.

**Choosing a font: `references/fonts.md`** is the guide — recommendations by tone (Korean sans, serif, display,
handwriting; Latin display; variable fonts whose axes TypeFX can animate: width, slant, 3D tilt, morph). It
recommends; it is not a whitelist. Pick what the piece needs.

| catalogue id | CSS family | use it for | Hangul | in projects |
|---|---|---|---|---|
| `pretendard` | `'Pretendard'` | default: headlines, body, numbers, UI (variable 45–920) | 11,172 | always (core) |
| `d2coding` | `'D2Coding'` | code, ids, commands, terminal looks (`var(--mono)`) | 11,172 | always (core) |
| `noto-sans-kr` | `'Noto Sans KR'` | the player's captions (700) | 11,172 | always (core) |
| `gowun-batang` | `'Gowun Batang'` | serif 바탕/명조: emotional, editorial, story, quotes (400/700) | 11,172 | `add_font.mjs` |
| `black-han-sans` | `'Black Han Sans'` | ultra-heavy display 검은고딕: news flashes, warnings, promo slams | ~2,580 | `add_font.mjs` |
| `jua` | `'Jua'` | rounded friendly display 주아: education, kids, casual | ~2,370 | `add_font.mjs` |
| `nanum-pen-script` | `'Nanum Pen Script'` | handwriting 나눔손글씨 펜: annotations, notes, asides | 11,172 | `add_font.mjs` |

- **Install:** `node <skill>/scripts/add_font.mjs <dir> <catalogue id | "Google Fonts family"> … [--weights 400,800]
  [--token --name]`. Korean static families can be several MB per weight: install only the weights you use.
  `add_font.mjs --list` shows the catalogue.
- **Fallback:** every stack is `'<font>', 'Pretendard', <generic>`, so glyphs a display font lacks (many Korean
  display fonts carry only the 2,350 common syllables; Latin-only fonts have no Hangul) are still drawn by an
  installed OFL font. Use display and handwriting fonts for headlines, labels and short phrases, not body text.
- **Never** name a system font (`system-ui`, `-apple-system`, `ui-monospace`, SF Mono/SF Pro, Menlo,
  Consolas, Arial, Helvetica, Apple SD Gothic Neo, Malgun Gothic…), a remote font, or a font that isn't
  installed in the project, anywhere: CSS, inline styles, canvas `ctx.font`, or SVG `<text>`. System
  fonts differ per machine (the recording won't match the verification) and are not OFL. Use no emoji
  (emoji fonts are not OFL-licensed here): draw icons as SVG.
- **No text is ever left without an installed font** — a system font must never show up just because no font was set:
  - DOM text inherits `var(--font)` from `#stage`; the template makes form controls (`button`, `input`, `select`,
    `textarea`) inherit it too — browsers otherwise give them the system font.
  - Every canvas sets `ctx.font` with an installed family first (`"700 48px 'Pretendard', sans-serif"`) before
    `fillText`/`strokeText`: the canvas default, `10px sans-serif`, is a system font. The same for text drawn into
    textures (3D/FX) and offscreen canvases.
  - No stack is generic-only (`sans-serif`, `monospace`) or a reset to the browser default (`initial`, `revert`).
  - SVG text only inline in the page (an SVG loaded as `<img>`/background doesn't see the page's fonts) — or as
    outlines (`text_to_paths.mjs`).
  - The generic family at the end of a stack is only the last resort; if it ever draws a glyph, that is a failure.
  `check.mjs` errors on generic-only stacks and on stacks that start with a generic family (a canvas draws with the
  first family), and warns on canvas text with no `ctx.font`; `check_fonts.mjs` checks every
  DOM glyph and every canvas text, character by character; `render.py` repeats the DOM and canvas check while it renders.
- **Fonts outside both sources** (an OFL font published only on a foundry's own site or repository) need a
  catalogue entry — a deliberate change to the skill that needs the user's approval: (1) read the licence file
  itself and confirm the SIL OFL 1.1 text; (2) take the files from the official source pinned to an immutable URL
  (commit SHA, release asset, npm tarball); (3) add the entry to `catalog.json` (role, tones, stack, token,
  `license: "SIL OFL 1.1"`, source, version, Hangul coverage, and `dest`/`sha256`/`bytes`/`fetch` for every file
  and the licence); (4) never put the font files in the skill; prove it with `add_font.mjs` and `check_fonts.mjs`
  on a test project.
- **Prove it.** `check.mjs` rejects uninstalled families, modified files (hash), non-OFL or missing licence
  files, stray font files (recognised by content, not only by extension), `local()` and `data:` fonts, and stray font
  names. `check_fonts.mjs` asks Chromium which font file drew every
  visible glyph across the video (every 0.5 s and at each cue, elements created later and `::before`/`::after` text
  included; captions on) and fails on any system font or on any web font whose source isn't an installed file; it also
  checks that glyph outlines
  came from installed font files and that every canvas text's family covers each of its characters. Run both
  before hand-off.

## Workflow

Tell the user briefly what you're doing at each stage; a full build takes a while.

### 1. Read the input, set the brief

Infer rather than ask: language, aspect ratio (below), tone, audience. The length is not chosen in advance: it is
whatever saying the content correctly and completely takes (**Content first, never time**).

What the user gave decides where the words come from:
- **A finished script.** Keep their words (step 3).
- **Only a topic** (a sentence or two), **or material** (an article, notes, a report). You research, plan and write the
  narration yourself: references/script-writing.md §0. Search the web, keep `research.md`, and put the plan at the top of
  `storyboard.md`.
- **A planning doc (기획서).** It is the user's brief. Turn it into a requirement table at the top of `storyboard.md`.
  What it fixes is kept: dictated lines verbatim, audience, must-show items, scene directions. A length it names is the
  user's wish and never a reason to leave something out: when what must be said needs more, keep all of it and tell the
  user how long it came out and why (**Content first, never time**). What it leaves open is yours to decide, researched
  like a topic.

Then read what applies:
- a **sponsor's brief** → references/sponsored.md (turn it into a requirement table first);
- **the user's recordings or generated clips** → references/footage.md;
- **a long video with many topics** → references/long-form.md (chapters as questions, one module per chapter).

Narration is recorded in the user's Fish Audio voice (key and voice in the skill's `.env`) only once they have reviewed
the finished video and decide to record. Until then every cue is a silent placeholder. Without a key or voice, plan a
video without narration (step 4).

Ask only when something truly blocks you, which is rare once a topic counts as enough. State the defaults you chose in
the final summary.

**Aspect ratio** — from where the video will be watched:

| aspect | stage | for | cues in the request |
|---|---|---|---|
| 16:9 (default) | 1920×1080 | YouTube, presentations, lectures, web, TV | 유튜브, 발표, 강의, 홈페이지 — or nothing said |
| 9:16 | 1080×1920 | Shorts, Reels, TikTok, stories | 쇼츠, 릴스, 틱톡, 스토리, 세로, 모바일 전체화면 |
| 4:5 | 1080×1350 | Instagram / Facebook feed posts and feed ads | 인스타 피드, 피드 게시물, 피드 광고 |
| 1:1 | 1080×1080 | square feeds, LinkedIn, messenger shares | 정사각, 정방형 |
| 4:3 · 3:4 | 1440×1080 · 1080×1440 | classic slides, tablets, some displays | 4:3, 3:4 |
| 21:9 | 2520×1080 | cinematic wide, signage, ultra-wide screens | 시네마틱, 와이드, 21:9 |
| custom | `--aspect 2048x858` | a screen or slot with exact pixels | a resolution |

- "인스타" for a video means Reels (9:16) unless they say feed/게시물 (4:5).
- **Another aspect is a re-layout, not a crop.** Compose each aspect on its own stage; never letterbox or crop a
  16:9 design into 9:16. For two destinations, make two projects: they can share the storyboard beats and the
  narration (copy `script.json`, `audio/` and `js/cues.js`), but the scenes are laid out again.
- `new_project.mjs` writes the aspect's layout tokens into `style.css`: `--safe` (text margin) and, in 9:16,
  `--safe-top` 240 / `--safe-bottom` 480 / `--safe-right` 180 px — where Shorts, Reels and TikTok draw titles,
  buttons and descriptions over the video (approximate and conservative; platforms change their UI). It also lifts
  and narrows the player's captions to clear them. Keep text and key visuals inside; check with
  `snapshot.mjs --safezone`. Composition by aspect: motion-design.md §7.

### 2. Create the project

```bash
node <skill>/scripts/new_project.mjs [<dir>] --title "<title>" [--lang ko] [--aspect 16:9|9:16|4:5|1:1|4:3|3:4|21:9|WxH]
```

`<dir>`: only when the user named a folder. **Otherwise leave it out**: every project is then made in one folder, as
`projects/<YYYYMMDDHHMMSS>_<project name>/` (under `$SUMO_PROJECTS_DIR`, or `./projects` of the current folder; the
date and time are the moment of creation, the project name comes from `--title`, Korean is fine). The tool prints the
folder it made: use that path for everything after (check, render, links to the user).
This copies the runtime, downloads the core SIL OFL 1.1 fonts into `fonts/` and GSAP into `vendor/gsap/` (first
run needs the network; later runs use the verified caches — see Fonts; `install_vendor.mjs <dir>` restores GSAP),
installs the looking guard into the Claude Code project's local settings (one line says where; Looking at the picture),
and writes a `script.json` skeleton with the narration
defaults. Its `voice` is empty on purpose: the voice is the user's to give (step 4).

### 3. Write the cues into script.json

Read `references/fish-audio.md` first. **If the user gave you a topic or material rather than a finished script**
(a sentence or two, an article, notes, a planning doc, "이 내용으로 영상 만들어줘"), you write the narration.
Read `references/script-writing.md` before drafting, starting with §0: research and the plan. Interpret the numbers
instead of reading them out, explain jargon for newcomers, give every topic change its cushion (close, turn, open with
the reason — **Every topic change gets a cushion**; a cushion is never filler), and use the creator's own sign-off.
Don't show the draft and wait; carry on to the finished video. The essentials:
- **Keep the user's words** when they gave a script, and any wording they dictate later. Split it into
  cues and don't rewrite the content. You only change *how it's
  pronounced* in `say` (numbers, units and English terms in spoken Hangul; sparse expression tags;
  `[break]` pauses). `text` keeps the original spelling for display.
- **The user's own script is used exactly as given.** Don't reword it, and don't offer rewrites. Only `say` gets
  spoken forms.
- **A script you write is speech for a listener who hears it once** (script-writing.md). The first rule is that the
  listener understands it the first time they hear it, and accuracy always comes before convenience:
  - **Order:** conclusion and count first, a one-line recap at the end of a section.
  - **Sentences:** one idea per sentence, no stacked modifiers or noun chains, one number per sentence, and the screen
    showing what is being said (§5).
  - **Terms:** every technical term is said exactly and explained in plain words when it is first heard (§3).
  - **Names:** one thing, one exact official name, with no convenient shortening and no coined term presented as
    established (§3b).
  - **Spoken Korean, not written** (§5b):
    - sentence endings about **75 % ~니다 · 25 % ~요**;
    - no words or endings that only belong on paper (formal Sino-Korean, paper connectives, 해라체 and report endings,
      passives);
    - no symbols or brackets in `say`;
    - **filler words only where they do a job** (자, = a new beat, 사실 = a truth against expectation, 그러니까 =
      a summary …), never as a quota;
    - never a word the user doesn't say (솔직히);
    - **no AI-style phrasing** in narration or on-screen copy: nothing that sounds polished but makes the listener
      stop and work out what it means. Say literally who did what, what changed and by how much (§5b).
  - You judge all of this yourself, line by line. No script scores wording.
  - **Before a single line is recorded or handed off, it passes the first-time-listener gates** (SKILL.md → Every line
    is for a first-time listener; script-writing.md §0b): the five questions, the neighbours, the seam pass (**Every
    topic change gets a cushion**), the internal-name list and the cold-listener review. No line skips them. That
    includes a line you fix later and every line of a batch edit.
- One cue ≈ one sentence: the unit of visual sync. A long sentence is split at a clause boundary into two cues, never
  shortened.
- Use `gapAfter` to give scene changes and questions a breath, longer than the beat inside a thought. The silence you
  hear is the gap plus the edges the two takes keep after your cuts, so choose it by reading the result with `wave.mjs`,
  not by a number: 0.4 s or more is dead air unless something sounds in it (a clip, a transition sound) — the user's
  rule. The user trims every such gap (references/sound.md §3).
- Stage directions in the script ("[장면 1]", "(화면: …)") are for your storyboard, not for `say`.

### 4. Narration (Fish Audio, drama-3) — recorded only when the user decides, after reviewing the finished video

```bash
node <skill>/scripts/tts.mjs <dir>              # until the user decides: every new cue is a silent placeholder, no API call
node <skill>/scripts/tts.mjs <dir> --approved   # the user reviewed the finished video and said to record: records the takes
```

Every run of `tts.mjs` also writes `script.txt`: the script as plain text, one cue per line, with no ids or times.

**Before `--approved`, every line about to be recorded has passed the first-time-listener gates** (the box at the top;
**Every line is for a first-time listener**). A take costs the user's credits, and a line that only you understand
gets recorded, timed, animated and has to be done again. Never run `--approved` on a line you have not put through the
five questions, its neighbours, the seam pass, the internal-name list and the cold-listener review.

Narration is made with **Fish Audio**, model **`drama-3`** (the user's choice; directed in plain language — read
references/fish-audio.md and https://docs.fish.audio/features/text-to-speech, …/text-to-speech/drama-3), in the
**user's own voice**. Never pick, guess or borrow another voice, and never use another TTS.

- **Keys.** The user's `FISH_API_KEY` and `FISH_VOICE` are kept in the skill's own `.env` (git-ignored — never in a
  tracked file, a project, output or memory); `tts.mjs` reads them from there (after the environment and any `.env` in
  the project or its parents). Put the voice id in `script.json` `"voice"` too. If the user gives a new key, replace it
  in that `.env` only.
- **The recording waits for the user (default).** Never generate narration on your own: it is their voice and their
  credits. Don't stop earlier to get the lines approved, either.
  - Build and verify the whole video on silent placeholders: `tts.mjs <dir>` without a flag gives each cue an estimated
    timing, and the captions show the lines.
  - Hand it off with the script (`script.txt`) and ask whether to record it in their voice now.
  - When the user says to record ("녹음해", "승인"), run `--approved`, then the after-recording pass (below).
  - Some requests count as the decision for those cues (`--approved --only <ids>`): "이 줄 다시 녹음해줘", or a line
    they dictate in an already recorded video.
  - A re-take or rewording you propose needs their OK first.
- **Whether a key and voice are available is what `tts.mjs` says** — its `🔑` line on every run names where it found
  them (the environment, a `.env` in the project or any parent folder, the skill's `.env`) or everywhere it looked. Run
  `tts.mjs <dir>` before deciding; never conclude "no key" from one `.env` file (a key in a parent folder's `.env` counts).
- **No key or voice available** (the `🔑` line says not found) → make the video **without narration**: set `"narration": false` in `script.json` and run
  `tts.mjs`. It writes silent audio and times each cue by its estimated reading time; the cues still drive every
  scene. Plan for it: the message must be readable on screen (key lines as on-screen text, or captions on), with
  enough hold time to read. In the hand-off, say the video has no narration and that it can be voiced later.

`tts.mjs` enforces both: without key and voice it never calls Fish Audio, and without `--approved` it records nothing new.

**No code decides where silence, a pause or a word is** — the user's rule, without exceptions. The tools only prepare the
level data (`wave.mjs` prints it as numbers); you read it and decide; the tools apply exactly what you wrote in
script.json. Every take is kept exactly as Fish Audio returned it, its edges included:
- **What comes out of a take** (the silence before the first word and after the last, a pause that is dead air) is its
  `cut`, read off `wave.mjs <dir> --unreviewed` / `--cue <id>` — `"ranges": []` when nothing goes (references/sound.md §1).
  A new take without a cut is `unreviewed: true` in js/cues.js, and check.mjs refuses the hand-off until it has one.
- **When a phrase is spoken**, for every phrase the scenes anchor with `cue(id).when('phrase')`, is the second you read off
  the take and write as the cue's `at`; `sync.mjs` turns it into `js/sync.js` (references/sound.md §2). Until then
  `when()` estimates by character position (the player warns for a recorded cue). Never transcribe a take.
- **No dead air**: no silence ≥ 0.4 s anywhere in the finished sound except pauses inside footage shown whole — keep
  `gapAfter` short, and judge the sound yourself by reading it as numbers with `wave.mjs` (references/sound.md §1).

**After-recording pass.** Once the takes are recorded, the cues move to the takes' real lengths and the scenes follow
their labels. Then:
1. Read every new take (`wave.mjs <dir> --unreviewed`), set each one's `cut` (edges included; `"ranges": []` when nothing
   goes) and the `at` times of the phrases `when()` uses, then `tts.mjs`, `sync.mjs`, `check.mjs`, `smoke.mjs` (re-anchor
   any `when()` phrase it reports), then read the whole sound with `wave.mjs` and fix every dead air you find
   (references/sound.md §1: a `cut`, or `gapAfter`).
2. Tell the user the new length and which takes to listen to first.

You can't hear the audio, and you must **never transcribe it** (no Fish ASR, no speech-to-text of any
kind) — it costs API credits, and judging takes is the user's job, not yours. Lines with expression tags, numbers,
English terms or names are what you ask the user to listen to first. When they report a bad
line, respell `say` or take again with `--approved --only <ids>`. Then search every cue for the same pattern (a
missing pause after a connective, a name run into its version, a verbless list) and fix those too
(fish-audio.md §3). Re-running is cheap: unchanged cues come from the cache.

### 5. Storyboard — rich expression

**Every word on screen obeys the first-time-listener rule too** (the box at the top): no cue ids, trial nicknames,
file names or working labels in titles, notes, kickers or captions unless the viewer was told what they are. A title
that names a thing by your working label is your name for it, not the viewer's.

**Start with the world bible** (references/cinematic-look.md §2) — before the shot list, at the top of `storyboard.md`:
the world (physical, illustrated, graphic, typographic or the product's own set) and each chapter's place or object
in it, one key light per chapter and how it changes, the
materials and how each is made, the depth plan, the palette with a job per colour, type as the world's material, the
recurring object's form and material, the camera language and the signature transition built from the world. An abstract
organising system is a device used inside the world, not a replacement for it.

**Then look development** (cinematic-look.md §4): build one hero frame per chapter (3–5 for a short film) to the bar,
look at them with `render.py --screenshot --at … --res 1080p`, and have the art director (elevate.md) score them.
Build the rest only when they reach 4 on graphic design.

**Aim for the richest expression the content supports.** Every beat shows its content as a picture in the world, an
object that moves or type that acts out its meaning — not words or a diagram on a background. Layered depth, a concept object
that travels through the piece, match cuts, expressive type for the hero lines, a signature transition. Richness comes
from meaning (one idea per beat, each idea visual), not from scattering effects; the user's calm taste still holds
(references/craft-notes.md).

**Find each technique in cokacmotion.** The skill's technique library has 166 web-graphics demos, one technique each,
with implementation notes, source and stills. Use it for every beat's primary effect, every hero line's type, the
signature transition and the impact beats:
1. Decide the beat's content and effect from the script.
2. `cokacmotion.mjs search <words>` to find the technique.
3. Read the demo's NOTES.md and the `main.js` lines it points to until you understand the principle.
4. Rebuild the technique for this video's own subject.

Take the technique, never the demo's scene, subject, colours or 9:16 frame. Someone who knows the demo must not recognise
it (references/cokacmotion.md). Note the demo id per beat in the storyboard's References.

Read `references/motion-design.md`, then write `storyboard.md`: message, the visual idea that recurs
through the piece, palette/type/shape/motion choices, and a table with one row per cue (what's on
screen, what moves, where the emphasis lands, how the scene exits). This is where the quality is
decided — a concept and a consistent system, one idea per beat, key words and numbers as the heroes,
never the transcript pasted on screen, and **never a slide or document layout** (no boxes, cards, bullet lists or
tables holding text; see "No slides, no boxes" above).

Plan it **like a film** (motion-design.md §8, §8b). `storyboard.md` is a shot list: for every cue the shot size and
angle, the camera move **and its reason**, blocking and light, the cut in and out, and the colour.
- **Structure:** inside a chapter, one continuous world the camera travels through (moving says "these belong
  together"). Between chapters, and wherever topic, time or place changes, cut, with the signature transition at the
  chapter changes. At every one of these seams the narration carries its cushion (close, turn, open with the reason —
  **Every topic change gets a cushion**), and the picture turns with it: the old topic's elements leave or step back
  before the new one's arrive.
- **The words direct the camera:** a push-in when the line points at something, a pull-out for the whole. A move with
  no reason is decoration, so the camera stays still.
- **Cuts and the voice:** cut at phrase boundaries, J-cuts (the next line first) as the default joint.
- **Continuity:** one screen direction for progress through the whole video.
- **Lists:** a list is a montage of shots, not a column.
- **Reveals:** withhold, then reveal on the word.
- **Variety:** vary the framing from beat to beat, give each key gesture a close-up, and let colour or the camera
  change as the story escalates.

Plan the **craft** here too (motion-design.md §12): a signature transition built from the concept, match cuts where
two moments really connect, kinetic type for the key lines, and impact treatment only for the moments that truly
peak. All of these are chosen by reason, never by count.
Plan the **typography** as carefully as the pictures (references/type-fx.md): for every hero line, decide what the
type itself does and why — it can shatter, melt, ripple, sink, jiggle, assemble from its jamo, blow away as dust,
glow, turn solid — and in which representation. The named effects are examples; compose new ones when the
line calls for it. Sensuous typography is something users notice and expect.
Users judge the piece as motion *design*, not as correctly timed slides. Give each beat **one primary
effect** that says what the line says (motion-design.md §12). Decide here whether any beat needs **real 3D**
(an object the viewer should see turn, open, assemble — see blender-mcp.md §1) or **shader FX** — light as
meaning: a glowing hero, light rays that carry a cut, a focus pull to the named object, a dissolve shaped like
the next scene, particles gathering into a structure (shader-fx.md §1, §5). Light, material and depth themselves are
not optional: they are the world (cinematic-look.md §3), drawn with baked Canvas textures and small hand-written WebGL
where needed; the StageFX/three.js stacks are for the beats that need them.

### 6. Build

Read `references/player-api.md` (API, timeline rules, tested recipes). Then:
- fonts: SIL OFL 1.1 catalogue fonts only (Fonts above); install extras with `add_font.mjs` before styling.
- `style.css`: palette and type tokens from the storyboard, scene layouts in stage pixels
  (1920×1080 for 16:9), every text box with an explicit width inside the safe area.
- `index.html`: persistent layers in `#stage`, one `<section class="scene" id="sNN">` per scene.
- `js/scenes.js`: `Video.define(({ tl, cue, scene, onFrame, rand, ... }) => { ... })`, every tween
  on `tl`, positioned by cue labels (`'c03'`, `'c03+=0.2'`, `cue('c03').about('단어')`, `cue('c03').when('단어')`).
  **`when()` only where the picture must land on a spoken word** — a number that appears as it is said, a highlight on the
  word, an item shown as it is named. Each `when()` phrase on a recorded cue is a time you read off the take and set
  (references/sound.md §2). Whatever only follows the line — a scene change, a camera move, a panel entering while the
  line runs — anchors on the cue's start or end (labels), a fraction (`cue(id).at(f)`), or `cue(id).about('구절')`
  (where the phrase falls by its characters; no time to set, no warning).
- effects: `const K = FXKit.install(ctx)` gives tested, seekable bursts, flares, ping wipes, punch zooms,
  odometers, glints, scramble kickers and write-ons — read `references/fx-kit.md` before building your own.
- techniques from cokacmotion (step 5): port them into project code — classic scripts, `onFrame(t)` with local time from
  the cue, `rand(seed)`, the stage's `W`×`H`, the libraries and fonts this skill installs. Bake anything heavy so it plays in
  real time. Never load the demo's files or modules (references/cokacmotion.md §4).
- expressive type: `const TX = TypeFX.install(ctx)` — the same words as split DOM units, copies (shards,
  glitch bands, solid layers), glyph outlines (`text_to_paths.mjs`) or raster tiles, all moved by one channel
  system (`TX.fx`, `TX.deform`, `TX.warp`) with presets as examples — read `references/type-fx.md`.
- illustrations beyond a few shapes (creatures, vehicles, maps, landscapes): one module per group in
  `js/art/<group>.js` with `build(el) → { animate(t) }`, looked at alone with `render.py --screenshot --art <name>`
  (`preview_art.mjs` checks its determinism and errors, and draws no picture) — read `references/art-library.md` (also
  how to hand groups to parallel workers: their brief carries the looking rule above).
- footage (the user's recordings, generated clips): declare them in `js/media-src.js`, place them with
  `MEDIA.install(ctx).clip(...)`; show recordings in `RecKit.browser(...)` and point with `spot` + `callout` — **never
  zoom into a recording**; play generated outputs whole; level-match and duck clip sound (references/footage.md).
- long videos: `js/seg/<id>.js` per chapter, chapter windows that never leave dead air, shared devices in one helper
  object (references/long-form.md). The user's taste and critique checklist: references/craft-notes.md.
- performance: hundreds of moving things on a canvas are pre-drawn sprites placed with drawImage, `fitCanvas(c, W, H, 2)`
  (player-api.md §4 Performance).
- division of labour: GSAP = time and values; DOM/SVG = the few meaningful elements (all text, vector art);
  Canvas 2D in `onFrame(t)` = quantity (hundreds of particles), painted planes and generated pixels (baked textures,
  light); small hand-written WebGL = lit material, relief, spheres, depth of field and bloom where the world needs them
  (cinematic-look.md §3), the StageFX/three.js stacks for real 3D and shader FX.
- the world is built to the world bible by **one builder per chapter** for anything with chapters, reading the same bible,
  each with **join contracts** for its seams (the exact frame on both sides) and one owner for the shared look layer, art
  modules and signature transition (cinematic-look.md §5). Keep a canvas pixel budget per chapter (≈30–40 M px) and
  look at every chapter after every merge — the failure modes to guard against are in cinematic-look.md §6.

The rules that matter most (the player sets the timeline to `t` every frame, so anything not derived
from `t` breaks seeking and makes takes differ): no standalone `gsap.to`, no `repeat: -1` on `tl`, no
`Math.random`/`Date`/timers, no CSS transitions or class toggling during playback, no network assets.
Anything that finishes drawing **after** a seek — an image whose `src` changes with t, `new Image()`, an iframe, a
Worker, `createImageBitmap` — is loaded once inside the async `define` (`await img.decode()`) or registered with
`busy(() => …)` while it is still drawing, so a frame-by-frame render (`render.py`) waits for it (player-api.md §4).
Never put `text-shadow` (glow) on text that sits inside a clipping box (SplitText `mask`, rolling-digit
columns, any `overflow: hidden`/`clip-path`/`mask-image` ancestor): every char's glow is cut at its box and
shows as **faint coloured rectangles behind the letters**. Glow with `filter: drop-shadow()` on an element
outside the clip instead (player-api.md §4, "Glows on clipped text").

### 6b. 3D and shader-FX beats (optional): Blender MCP → glTF → three.js

Only when the storyboard calls for it. Read `references/blender-mcp.md` (preparing and driving Blender
through the official Blender Lab MCP server) and `references/threejs-3d.md` (the WebGL layer). For glow,
light rays, depth of field, shaped transitions, lens flares, reflections and GPU particles use the **FX
build** — `enable_3d.mjs <dir> --fx` (or `new_project.mjs … --fx`), `const fx = await StageFX.create(...)`,
`fx.render(t)` in `onFrame` — and read `references/shader-fx.md` (effect catalog with determinism classes and
relative cost, recipes for the craft beats, particles, pitfalls). One build per project.

```bash
S=<skill>/scripts
node $S/setup_blender.mjs --check && node $S/setup_blender.mjs   # once per machine (~400 MB, no sudo; self-test; Python ≥ 3.10, --python <exe>)
node $S/enable_3d.mjs <dir> [--fx | --classic]                   # three.js into the project (--fx: shader FX build; --classic switches back)
node $S/blender_mcp.mjs start                                    # background Blender + official add-on
node $S/blender_mcp.mjs run <dir>/assets3d/cup.py --prelude --log <dir>/assets3d/mcp-calls.jsonl
node $S/blender_mcp.mjs call get_objects_summary                 # inspect; iterate on the script
node $S/embed_glb.mjs <dir>/assets3d/cup.glb <dir>               # → models/cup.glb.js
node $S/blender_mcp.mjs stop
```

- Blender only makes assets; the video renders them with three.js on the player clock
  (`mixer.setTime(t)`, camera from values tweened on `tl`, `s3d.render()` in `onFrame`).
- On ARM Linux (Docker on Apple silicon) the official x86_64 Blender runs through Rosetta with a
  user-space runtime — setup handles it.
- Asset scripts are idempotent, return `result` (use `stats()`), export with `export_glb()`; keep
  `.py`, `.blend`, `.glb` in `assets3d/`. Tell the user in one line before the first Blender download.
- Verify the 3D on render.py sheets: `--screenshot --from a --to b --gapframe 3` across every 3D move and every FX
  peak. Shaders read `fx.uTime` only; `check.mjs` flags TSL `time`, `film()`, a missing `fx.render(t)`.
- FX scenes keep an opaque canvas (post effects write alpha) with DOM type above it; mention `?fxq=0.75` in the
  hand-off for recording on a slow machine (shader-fx.md §7–8).
- Optional: `blender_mcp.mjs mcp-json` prints an `.mcp.json` entry so later sessions get the Blender tools
  natively (ask before changing their config).

### 7. Verify — look at the real render

**Verify the words as well as the picture:** the whole script goes through the first-time-listener gates here, before
the hand-off — the seam pass over every topic change (**Every topic change gets a cushion**), the cold-listener review
on `script.txt`, and the internal-name list over the narration and every on-screen string (**Every line is for a
first-time listener**; script-writing.md §0b).

What the viewer gets is what `render.py` films, so you look at the video with `render.py --screenshot`: frame by frame,
the same way the MP4 is made. Read `references/visual-review.md` (the review loop) the first time; the short version:

```bash
# looking — render.py sheets (open the images whose paths it prints)
python3 <dir>/render.py <dir> --screenshot --gapframe 120                      # the whole video, a tile every 2 s
python3 <dir>/render.py <dir> --screenshot --from 12 --to 20 --gapframe 30     # one beat: enter, hold, leave
python3 <dir>/render.py <dir> --screenshot --from 7.0 --to 8.4 --gapframe 3    # a transition or camera move, frame by frame
python3 <dir>/render.py <dir> --screenshot --at 23 --res 1080p                  # one moment at stage size (small type, detail)
python3 <dir>/render.py <dir> --screenshot --at 23 --crop 1200,600,640,360 --res 4k   # a stage rectangle, twice the pixels
python3 <dir>/render.py <dir> --screenshot --at 66.3 --via 74.3                 # a seekcheck difference: both ways + the diff
python3 <dir>/render.py <dir> --screenshot --art dino --viewbox "-200 -130 400 260" --at 0,0.6,1.2   # one js/art module
python3 <dir>/render.py <clip file> --screenshot --gapframe 60 --out <dir>/screenshots/clips/<key>   # what a user's clip shows
node <skill>/scripts/stills.mjs <dir> --out media/render-stills --fps 60 --scale 0.4444   # once, when the video places clips

# automatic checks — they measure and draw no picture; each prints the render.py command for the moment it reports
node <skill>/scripts/check.mjs <dir>                       # static: syntax, cues/#ids, determinism, every file accounted for, font names
node <skill>/scripts/check_fonts.mjs <dir>                 # real Chromium: every glyph drawn by a catalogue font
node <skill>/scripts/smoke.mjs <dir>                       # jsdom: runtime errors, visible scene/text per cue
node <skill>/scripts/errscan.mjs <dir>                     # real Chromium: runtime errors, missing files, network requests, across the timeline
node <skill>/scripts/snapshot.mjs <dir>                    # layout warnings at every cue (overlaps, clipping, clipped glows)
node <skill>/scripts/snapshot.mjs <dir> --overview --seekcheck   # determinism: every shot again in reverse and in shuffled order must match (pixels)
node <skill>/scripts/snapshot.mjs <dir> --safezone         # text inside the unsafe margins (9:16: platform UI)
node <skill>/scripts/snapshot.mjs <dir> --perf             # JS per frame during playback (p95 well under 8 ms)
node <skill>/scripts/preview_art.mjs <dir> ART.sub --viewbox "…"  # one illustration module: determinism + errors (look: --art)
node <skill>/scripts/wave.mjs <dir>                        # the sound as numbers (level per 50 ms, cues/clips marked) — you judge dead air
node <skill>/scripts/wave.mjs <dir> --cue <id>             # one take as recorded, in seconds of the take — for a "cut"
```

For a fix the user asked for, the gate is `check.mjs` + `errscan.mjs` (+ reading `wave.mjs`, `check_fonts.mjs` when
relevant), with no sheets. The loop below is for work you do on your own and for moments the user asks you to look at.

- **render.py sheets are how you see the video.** Open every sheet and look properly: story, the shot, focus, text,
  acting, composition, and **no frame that would pass as a slide** (boxes, cards, bullets, tables) (visual-review.md
  §3). Start with the whole video, then each chapter, then every key moment, and check that each happens on screen
  while it is said (visual-review.md §5).
- Shoot every transition and camera move at `--gapframe 1–3` to catch one-frame jolts, default-state flashes, and
  unexplained dim/bright states. Look for stretches where nothing follows the words and fix them, unless a stillness is
  a deliberate beat. Keep improving and re-shooting the same stretch until a pass finds nothing.
- Layout warnings and the seekcheck come from snapshot.mjs (§4 of visual-review.md). Each comes with its render.py
  command (`--at`, and `--via` for a seekcheck difference): run it, look, fix the real ones, look again.
- **No browser yet?** `node <skill>/scripts/setup_browser.mjs --check`, then without `--check`. It
  finds or downloads a headless Chromium and, on Linux, fetches missing libraries into
  ~/.cache/motion-video-deps (SHA256-verified, no sudo). Tell the user in one line before the first
  download. Details, other platforms and troubleshooting: `references/browser-setup.md`. If no browser
  can run at all, do a layout pass by hand (motion-design.md §7), say the render wasn't seen, and ask
  the user for screenshots.
- Headless Chromium can't judge smoothness (usually no GPU), audio by ear, or Safari — say so when you
  hand off. Finish with the checklist in motion-design.md §11.

### 7b. Elevate — the aesthetic pass (고도화, always)

**A video that passes every check can still disappoint.** The user's words about such videos: "연출에 대한 아쉬움, 더
섬세한 그래픽 디자인 모션의 표현 등등 전체적으로 미적인 부분에서 큰 아쉬움들이 있어." Step 7 finds what is *wrong*;
this step makes it *good*. The director scores against the **absolute bar** of **A crafted world from the first build**
(a reel-worthy still; the infographic look scores 2 at best) — never against the previous round. Read
`references/elevate.md` and run it after the first complete build, without asking:
1. Shoot fresh sheets of the whole video, every chapter, every transition and the hero frames.
2. An **art director** — a separate subagent with no stake in the code, briefed with "Looking at the picture" word for
   word — scores every chapter 1–5 on **연출** (shots, camera with a reason, staging and reveals, rhythm, joins),
   **그래픽 디자인** (composition, hierarchy, typography, colour and light, material and depth, detail) and **모션**
   (easing, choreography, anticipation and follow-through, continuity, life), lists the floor violations and ranks
   6–10 concrete upgrades.
3. You rebuild — re-create the weak beats from the world bible with techniques from cokacmotion, never decorate (a round
   that only adds layers to the same frames does not count) — and re-shoot before/after.
4. Repeat until every chapter scores at least 4 on all three, or three rounds; report the scores before → after.

### 8. Hand off

Reply in the user's language with:
- that the script passed the first-time-listener gates (the cold-listener review answered "clear" after your fixes), and
  every line the user wrote or dictated that the review flagged, with a proposed fix for them to decide;
- the folder path and the two ways to a video file: `python3 render.py <folder>` (or without the argument inside the folder; an MP4 frame by frame, captions
  on, `--res 480p` / `720p` / `4k` for 480p / 720p / 4K — the first run sets itself up), or play and screen-record: open `index.html` in Chrome (double-click works) —
  a black screen with one loading bar, then it plays at once; press **F** for fullscreen, start the screen recorder,
  then **R** (from the start). `index.html?warm` warms up first (paints the whole video once, on the second half of the
  bar) so even the first play doesn't drop frames. If the browser blocks sound without a click, a play mark shows in the
  middle (click / Space). UI and cursor stay hidden while playing; the last frame holds at the end. To find stutter
  before recording: `?watch` warms up and stops on every dropped frame with a red screen for a second (not for the
  recording itself).
- recording tips: use a recorder that captures system audio (e.g. OBS), or record video only and lay
  `audio/narration.wav` under it in an editor — its 0 s is the moment motion starts from the beginning (R). When clips play
  their own sound (footage with `audio`), narration.wav alone lacks it: record system audio.
  For 4K, record fullscreen on a 4K display or set the recorder canvas to 3840×2160; text and vector
  shapes stay sharp.
- other aspects: the player scales the stage to the screen and fills the rest with black, so a 9:16 video on a
  landscape monitor has black sides. Tell the user to record only the video area — e.g. OBS with a crop filter on
  the capture and the canvas set to the stage size (1080×1920, or 2160×3840 for 4K) — or to crop afterwards in the
  editor; a portrait monitor or a tall browser window works too. For 9:16, remind them that the platform's UI
  covers the margins the layout kept clear.
- hover chrome: moving the mouse over the page shows a thin progress bar along the bottom (click or drag to seek) and the
  shortcut list on the right, hidden again 2.5 s after the last movement while playing (never in a recording, a render or a sheet).
- a click on the picture toggles play / pause (a round mark in the middle: pause while playing, play while paused, shown with the hover chrome).
- keys: Space play/pause · ←/→ ±0.5 s (Shift ±5 s) · Shift+> / Shift+< speed (0.25–3×, for review only) · R restart at 1× ·
  C captions · **S copies the time, cue id and line** (paste it above a review note) · D debug bar (mouse scrubbing).
  A reload resumes where it was. Captions (on by default; C toggles and is remembered) are Noto Sans KR Bold, one line
  at a time, at the very bottom with a 20px margin.
  If the design has UI along the bottom, keep captions clear of it with `--caption-max`/`--caption-bottom`
  on `#stage` (player-api.md §6) and check them on render.py sheets (captions are on there) and with
  `snapshot.mjs --captions` (layout warnings).
- the defaults you chose, the length, and anything unresolved (placeholder audio, takes the user reported).
- the elevation (step 7b): rounds, the director's scores before → after on 연출 · 디자인 · 모션, the most visible
  changes with their before/after sheet paths, and what the director still wanted that was not done.
- what to read: `script.txt` (the script as plain text) and `storyboard.md` (the plan). When you researched, also point
  to `research.md` (sources) and list the facts you added beyond what the user gave you.
- originality: all visuals, illustrations, effects and copy were made for this video; list any user-provided
  assets (provenance.json) and the cokacmotion techniques re-implemented (demo id and technique).
- fonts: which catalogue fonts are used and their licences (all SIL OFL 1.1), confirmed by `check_fonts.mjs`.
  If the project folder itself is shared, the licence files in `fonts/` must stay with it.
- how you verified it (render.py sheets you looked at) and what you could not check (smoothness, audio sync by ear,
  Safari), plus the paths of the latest render.py sheets so the user can see the same frames.
- narration:
  - **Not recorded yet** (the default when a key and voice exist): say so plainly. The video plays with silent
    placeholder narration at estimated timing. Ask whether to record it in their voice now. Recording re-times the
    video to the real takes, and then you run the after-recording pass (step 4).
  - **Voiced**: say which audio to listen to first — `audio/narration.mp3`, plus the specific `audio/cues/<id>.wav` files
    with expression tags, numbers, English terms or names (you couldn't hear them).
  - **Made without narration**: say so, and that giving their Fish Audio API key and voice id adds it later.

## Revisions

- Review notes come as `time / total [cue] line` (the S key) + a remark: go to that moment, fix it, answer with the same
  time and cue id. A question in a note is answered first (references/collaboration.md).
- Script text changed → edit `script.json` and run `tts.mjs` (it rewrites `script.txt` too).
  - In a recorded video the changed cues become silent placeholders until the user decides to record them. A line they
    dictated, or one they asked to re-record, is that decision: `--approved --only <ids>`.
  - Later cues shift and the visuals follow their labels.
  - Then, for a new take, read it and set its `cut` and `at` (references/sound.md §1–2), run `tts.mjs` and `sync.mjs`,
  `check.mjs` + `smoke.mjs`, and read the changed stretch with `wave.mjs`. If `smoke.mjs` warns
  `phrase not found`, a `when()` anchor lost its words: re-anchor it in `scenes.js`. If a line was
  inserted or deleted, pass the seams it touched again (**Every topic change gets a cushion**).
- A correction to one line is usually a rule. Apply it to every cue with the same pattern, and add it to
  the storyboard's notes so later edits keep it.
- **Every changed line, every time** (a dictated line, a rewording of yours, a batch of style fixes) → the
  first-time-listener gates before it is recorded (SKILL.md → Every line is for a first-time listener):
  - Read it with the line before and the line after it. A changed line can leave the next line's connective or
    back-reference pointing at nothing.
  - Find the seams around it and pass them again: an inserted aside can strand the next topic, a deleted closing line
    can leave a topic open. A note that a line is abrupt is answered with a cushion, and every other seam is passed
    again before you reply (**Every topic change gets a cushion**).
  - Check it against your internal-name list.
  - Send the changed stretch to the cold-listener review.
  - A batch edit that changes only endings or register still gets read for meaning, line by line: a rule that rewrites
    the form carries the old ambiguity along unchanged.
- "This line sounds wrong" → respell `say` and/or take it again: `tts.mjs <dir> --approved --only <id>` (their report
  is the decision for that line).
- Pacing → `gapAfter`, `leadIn`, `tail` in `script.json` (never a speed: the voice is never slowed down or sped up — a
  rushed take gets pauses in `say`, references/fish-audio.md), then `tts.mjs` (cached takes: no API calls),
  `sync.mjs`, then read the sound with `wave.mjs`.
- Visual changes → `scenes.js` / `style.css` / `index.html`, then verify again.
- A stretch the user finds flat or ugly ("밋밋해", "아쉬워", "연출이 약해", "디자인이 별로야") → an elevation round on that
  stretch (references/elevate.md): rebuild it from its concept, not a polish of the same frame.
- 3D asset changes → edit `assets3d/<name>.py`, `blender_mcp.mjs run` it, `embed_glb.mjs` again, re-shoot.
