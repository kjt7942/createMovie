# Motion design guide — from script to screen

> The user's own taste and the lessons from the Kling video are in **references/craft-notes.md**
> (calm impacts, no punch zoom, the studio look, the critique checklist) and **references/collaboration.md**.
> Where they differ from this guide, they win.

The difference between "text flying around" and a video people remember is decided before any code:
a concept, a consistent visual system, and one clear idea per beat. Read this before writing
`storyboard.md`.

## Contents
1. Find the concept
2. Art direction (palette, type, shape, motion personality)
3. Storyboarding: a shot list, one beat per cue
4. What goes on screen
5. Motion language
6. Transitions and continuity
7. Composition
8. Shot variety and the camera — the cure for monotony
8b. Film grammar — structure, camera, cuts
9. Visual devices (with snippets)
10. Anti-patterns
11. Pre-delivery checklist
12. Creative craft — what makes it motion *design*

---

## 1. Find the concept

Read the whole script first. Answer in one line each:
- **Message** — what should the viewer remember? (one sentence)
- **Audience & tone** — who is watching; how should it feel? (e.g. 신뢰감 있는 / 발랄한 / 긴박한 / 서정적인)
- **Key words** — the 3–6 words or numbers that carry the message. These become the biggest things on screen.
- **Structure** — hook → problem → idea → proof → close? a list? a timeline? a comparison?
- **World** — the designed world the film happens in (physical, illustrated, graphic, typographic or the product's own
  set), each chapter or section a place or an object in it, with its light and materials, for every kind of video
  (references/cinematic-look.md §2). Decide it first; the visual idea below lives inside it.
- **Visual idea** — one organising metaphor or system that runs through the piece. Examples:
  - a single line that travels through every scene and becomes a chart, a road, an underline
  - a grid of cells that fills, reorganises, and highlights as the story moves
  - a "document" that is typed, redacted, annotated
  - concentric circles / orbits for ecosystems; stacked blocks for layers of technology
  - a camera flying over one giant canvas where each scene is a region of it

A visual idea is what makes the piece feel designed instead of assembled. Pick one and let it recur.

## 2. Art direction

Choose once, write it at the top of `storyboard.md`, put it in `style.css` as tokens, and don't drift. It starts from
the **world bible** (references/cinematic-look.md §2): the world, one key light per chapter, materials, depth plan, type
as material, camera language. The tone table below gives palettes and type, not a substitute for a world: a palette and
a line style are starting tokens, never a finished look.

**Tone → starting points** (adapt; don't copy):

| tone | background / palette | type | shapes | motion |
|---|---|---|---|---|
| tech, product launch | near-black, one electric accent (#3D7BFF, #7CFFB2, #FF5A36) | 800–900 display, tight tracking | grids, thin lines, glows | snappy `expo.out`, precise |
| corporate, trust | off-white or deep navy, 1 accent + neutrals | 600–700, generous spacing | rules, hairlines, data drawn as objects | calm `power2/3`, no bounce |
| education, friendly | warm light (#F6F1E7), 2–3 soft saturated colours | 700–800, rounded feel | circles, pills, icons | `back.out(1.4)` pops, playful stagger |
| emotional, brand story | dark or photographic-feeling gradients, muted | light 200–300 huge + 600 small | few, large, slow | long `sine.inOut`, slow push-ins |
| urgent, news, warning | black/white + red/yellow | 900 condensed-feeling, all caps Latin | bars, tickers, stamps | hard cuts, fast in, `CustomWiggle` shakes |

**Palette**: `--bg`, `--surface`, `--fg`, `--muted`, `--accent` (+ at most one `--accent-2`). The accent
marks what matters *right now* — if everything is accented nothing is. Keep text contrast ≥ 4.5:1.

**Type — SIL OFL 1.1 fonts only** (SKILL.md → Fonts): the catalogue or any Google Fonts `ofl/` family; the
recommendations by tone, Korean and Latin, and variable fonts with animatable axes are in `fonts.md`. Pretendard
(variable 45–920) is the workhorse; add one or two character fonts per piece, matched to the tone. Starting points:

| tone | headline / accent font (`add_font.mjs`) | body |
|---|---|---|
| tech, product launch, developer | Pretendard 800–900 + D2Coding for code/ids | Pretendard |
| corporate, trust | Pretendard only | Pretendard |
| news, urgent, promo, sports | Black Han Sans (`--display`) for slams and flashes | Pretendard |
| education, friendly, kids | Jua (`--display`) for titles and labels; Nanum Pen Script (`--hand`) for notes | Pretendard |
| emotional, editorial, story, quotes | Gowun Batang (`--serif`) for titles, quotes, and body where a quiet reading voice fits | Pretendard / Gowun Batang |

Never a system font. Sizes for a 1920×1080 stage:

| role | size | weight | tracking | line-height |
|---|---|---|---|---|
| hero word / number | 180–320px | 800–900 | -0.04em | 1.0 |
| headline | 96–140px | 700–850 | -0.03em | 1.1 |
| subhead | 52–72px | 500–650 | -0.02em | 1.25 |
| body / list item | 40–48px | 450–550 | -0.01em | 1.4 |
| label / caption | 26–32px | 500–600 | 0 (or +0.08em caps) | 1.3 |

Nothing under 26px — it won't survive video compression or a phone screen. Other aspects keep the same px
sizes for body text (the stage is 1080 px on its short side in every preset); scale headlines to the line width:
~70–85% for 9:16 and 3:4, ~80–90% for 1:1 and 4:5. In 21:9 keep 16:9 sizes and shorter lines.

Korean specifics: `word-break: keep-all` is already on the stage (lines break between words). Add
`text-wrap: balance` to headings so two-line titles split evenly. Avoid a single short word alone on
the last line — adjust `max-width` or insert a `<br>` at a meaningful break. Mixed Hangul/Latin: Latin
in Pretendard is slightly smaller-looking; bump English-only display words ~5%.

**Shape language**: pick one family (sharp rectangles, pills, circles, hairlines, blobs) and use it
everywhere: highlights, marks, masks, dividers, transitions. Shapes are marks and objects, **never boxes that hold
text** (SKILL.md → No slides, no boxes).

**Motion personality**: one easing family + one speed. See §5.

## 3. Storyboarding: a shot list, one beat per cue

A cue is one sentence of narration and the unit of sync. Every cue gets at least one *meaningful*
visual change timed to it (new element, emphasis, transformation, camera move). Long cues (> 5 s) get
2–3 sub-beats using `cue(id).when('…')`.

Group cues into scenes (usually 1–3 cues per scene, one idea per scene).

`storyboard.md` is a **shot list**, the way a film is planned. Each row says what the camera shows, how, and why:

```markdown
# <title>
- Message: …
- Visual idea: …
- Structure: chapters and their worlds (§8b); where the cuts and the signature transition fall
- Colour script: the colour of each chapter along the story's arc
- Palette: bg #…, fg #…, accent #… · Type: … · Shapes: … · Motion: … · Screen direction: progress runs →

| cue | narration (short) | shot size · angle | camera (and why) | blocking · light | in / out | colour |
|---|---|---|---|---|---|---|
| c04 | 회의 시간의 절반은 결론 없이 끝납니다 | close-up, eye level | push in — this is the point | the clock right third, key light on it | J-cut (line first); match cut dot → clock | warm → hot |
| …
```

Every camera move names its reason. A row that can't say why the camera moves keeps the camera still. This is
short on purpose: it's the plan you implement and the thing the user can skim.

## 4. What goes on screen

The narration already says the sentence — the screen should *add*, not duplicate.

**Never a slide, never a document (absolute).** No title bars, no cards or panels holding text, no bullet lists, no
tables, no box-and-arrow diagrams, no grids of tiles, and no scenes that swap like slides. The content itself is the
picture, on the open stage. Boxes appear only as objects in the story (a window, a phone, a sheet of paper), drawn
with material and light. Full rule and replacements: SKILL.md → No slides, no boxes.

- **Key phrase, not transcript.** 2–8 words from the cue, or the one number. Full sentences only for a
  quote or a thesis statement that deserves reading.
- **Numbers become heroes.** `1,280,000` huge with a count-up, label small underneath.
- **Lists become sequences — never a bullet list.** Each item is an object or acting word that enters *as it is
  spoken* (`when()`), and earlier ones change state (dim, move aside, become part of the picture).
- **Comparisons become space.** Split screen, before/after, two columns, a scale tipping.
- **Processes become flows.** Nodes + connectors drawn in order (DrawSVG), a dot travelling the path.
- **Abstract ideas become metaphors.** Growth → rising bars/stairs; connection → lines between nodes;
  complexity → tangled lines straightening; speed → streaks, motion-blur stretch (scaleX + blur).
- **Questions** get a pause: let the question sit alone on screen before the answer appears (use a
  longer `gapAfter`).
- **Captions are not the design.** The player has optional captions (C); don't build subtitle bars.

## 5. Motion language

**Easing** (GSAP names):
- entrances: `expo.out`, `power4.out` (confident), `back.out(1.4)` (playful)
- exits: `power2.in`, `expo.in` — faster than entrances
- moves between states: `power3.inOut`, `expo.inOut`
- ambient/camera: `sine.inOut`, or `none` for constant drift
- avoid `linear` on anything that starts and stops; avoid `bounce` unless the tone is childlike

**Durations**: micro (highlight, colour) 0.2–0.35 s · standard entrance 0.6–0.9 s · big moves/transitions
0.9–1.4 s · ambient 6–20 s. Exits ≈ 60% of entrances.

**Stagger**: chars 0.02–0.04 · words 0.06–0.1 · list items/objects 0.1–0.18. Total stagger of a group ≤ 0.8 s.

**Timing to speech**: a visual should land with (or up to 0.2 s before) the words that describe it —
position with `'cXX'`, `'cXX+=0.1'` or `cue(id).when('단어') - 0.15`. Visuals that arrive after the
words feel laggy.

**Overlap, always.** The next element starts before the previous finishes (`'<0.15'`, `'-=0.3'`). The
exit of scene A overlaps the entrance of scene B by 0.2–0.4 s. Sequential "one thing, then wait, then the
next" feels like PowerPoint.

**The picture follows the words.** While the narrator talks, what is said moves: each phrase that names something
gives that thing a reason to arrive, change or be pointed at. A still frame is right when the stillness means
something (a line landing, a held beat before a reveal, the end hold). A frame frozen only because nothing was
planned for those words is dead air. Motion with no reason, such as a habitual slow zoom or a drift on every scene,
is not the cure: it is decoration.

**Hierarchy in time.** One focal element moves first and most; supporting elements follow smaller and
later. Never animate everything at once with the same tween.

## 6. Transitions and continuity

Pick 2–3 transition types that fit the concept and reuse them; random variety reads as noise.

- **Mask wipe** — incoming scene revealed by `clip-path: inset(0 100% 0 0)` → `inset(0 0% 0 0)`.
- **Panel wipe** — an accent-coloured panel sweeps across, the scene swaps underneath, the panel exits.
- **Push** — outgoing moves out (`xPercent: -30, autoAlpha: 0`), incoming arrives from the other side.
- **Zoom through** — scale up into an element (a dot, a letter, a window) that becomes the next background.
- **Match cut / morph** — an element survives the cut and transforms (circle → chart dot, word → headline,
  shape → shape with MorphSVG). The most "designed" feeling; use it at the 1–2 key moments.
- **Hard cut on a beat** — for energetic pieces; cut exactly at the cue start.

Persistent elements (a logo mark in a corner, a progress line, a background grid, the travelling line
of your visual idea) live directly in `#stage` outside scenes and tie the piece together.

Mask wipe snippet:
```js
tl.fromTo('#s04', { clipPath: 'inset(0% 100% 0% 0%)' }, { clipPath: 'inset(0% 0% 0% 0%)', duration: 0.9, ease: 'expo.inOut' }, 'c05-=0.35');
```
Panel wipe snippet (`.wipe` is a persistent full-stage div with `background: var(--accent); transform: scaleX(0)`):
```js
tl.fromTo('.wipe', { scaleX: 0, transformOrigin: 'left' }, { scaleX: 1, duration: 0.45, ease: 'expo.in' }, 'c06-=0.5')
  .set('.wipe', { transformOrigin: 'right' })
  .to('.wipe', { scaleX: 0, duration: 0.55, ease: 'expo.out' });
```
(Schedule the scene swap — `scene()` boundaries — at the moment the panel fully covers the stage.)

## 7. Composition

- **Safe area**: keep text inside the `--safe*` tokens new_project.mjs wrote for the aspect (96px in 16:9, 64px in
  the square/portrait formats; in 9:16 also 240px top, 480px bottom, 180px right for the platform UI). Background
  shapes can bleed. Check with `snapshot.mjs --safezone`.
- **Composition by aspect** (re-lay out each aspect; don't crop one into another):
  - **16:9** — grids, left/right splits, a visual beside its text, lateral camera moves.
  - **9:16** — stack vertically: one idea per screen, the headline in the upper-middle (≈ y 300–900), the visual
    below or behind it; few, very large words; side-by-side layouts don't fit. Vertical motion (rise, drop,
    scroll) reads naturally; keep everything inside the UI-free zone.
  - **4:5 · 1:1** — feed formats, often watched muted while scrolling: centred, bold compositions that read at
    thumbnail size; a frame that works as a still in the first second; key words on screen, not only in the
    voice.
  - **21:9** — cinematic: wide establishing shots, lateral pans, generous negative space; keep text near the
    centre so it survives if the sides are cropped.
  - **4:3 · 3:4** — the screens slides are shown on, but never slide design: one hero word or number with one
    picture, calm moves, no text boxes.
- **Grid**: 12 columns with 120px margins; align text blocks to shared left edges across scenes.
- **Scale contrast**: one very large thing + small supporting labels beats several medium things.
- **Asymmetry**: left-aligned blocks with a large visual on the right read more editorial than
  everything centred. Centre only for single hero words/numbers.
- **Depth**: background (colour, gradient, grain) → mid (shapes, graphics) → content (type) → foreground
  accents (a line, particles). Parallax the layers at different speeds during camera moves.
- **Density**: at most ~12 words readable on screen at once; at most 3 visual groups.

**Layout safety without a browser** (you can't see the render):
- Give every text container an explicit `width`/`max-width` and position it with flex/grid or explicit
  `left/top` inside the safe area; never rely on text happening to fit.
- Estimate widths: Hangul ≈ 0.95em per syllable, Latin ≈ 0.55em per character, digits ≈ 0.6em (tabular).
  A 120px headline fits ~15 Hangul syllables per 1728px line (1920 − 2×96). If it doesn't fit, lower the
  size, shorten the phrase, or break into two balanced lines.
- Absolutely positioned elements stacked in one scene: make sure their boxes don't overlap at the
  moment both are visible.

## 8. Shot variety and the camera — the cure for monotony

A real failure from this skill's first run: every scene used the same slot (title top-centre, figures
centred below), the camera never moved, the background never changed, and the gags — tiny gestures
like a mouth corner rising — were drawn a few pixels big. The user's verdict: "too monotonous". Fix it
by thinking in **shots**, like a film or a comic:

- **Vary the framing beat to beat**: long shot (place, both characters) → medium (bust) → close-up
  (one face) → extreme close-up (eyes only, the mouth corner) → insert (the phone, the notice board)
  → split panel (two options) → full-bleed type. Don't reuse the same layout slot more than twice in a row.
- **Make the small things big.** If the script is about a gesture, give that gesture the whole screen
  (a 2× punch-in on an ECU panel) at the moment it's spoken.
- **Give the camera a job.** A world larger than the screen (a comic strip, a floor plan, a long
  corridor) plus camera moves between regions gives continuous motion and natural transitions. Keep
  every region's coordinates in one layout table and compute camera frames from it (see below).
- **Let colour carry the arc.** Tie background/page colour to the story's tension (calm → warm → hot →
  dark at the climax) so the whole frame changes as the story escalates, not just the text.
- **Characters must be able to act.** Minimum face kit: whites of the eyes + pupils (gaze reads at any
  size), eyebrows (most of the emotion), mouth, blush, sweat. Parametric drawing functions make every
  shot size consistent.
- **Comic grammar is cheap richness**: narration boxes, speech/thought balloons, onomatopoeia (흠칫,
  휙!, 끄덕, 삐걱) with a thick outline, focus lines, screentone. Use SFX sparingly — they're emphasis.
- **Put persistent UI where the camera isn't going.** When the camera travels down, the bottom of the
  screen is the not-yet-revealed page; a HUD in the bottom corners stays out of the way. Hide it during
  punch-ins and at the final frame.

**Camera on a large world** (explicit coordinates → verifiable framing):
```js
// window.LAYOUT = { W: 1920, H: 11100, panels: { p3: [100, 1260, 1720, 520], ... } }  (js/layout.js)
function frame([x, y, w, h], maxS = 1) {           // fit a rect into the free area above a bottom HUD
  const s = Math.max(1, Math.min(maxS, 1800 / w, 860 / h));
  const tx = Math.min(0, Math.max(1920 - s * 1920, 960 - s * (x + w / 2)));    // never show past the edges
  const ty = Math.min(0, Math.max(1080 - s * H, 470 - s * (y + h / 2)));
  return { x: tx, y: ty, scale: s };
}
gsap.set('#world', { transformOrigin: '0 0' });
tl.to('#world', { ...frame(P.p13, 2), duration: 0.5, ease: 'power4.inOut' }, cue('c08').when('입꼬리를') - 0.35);
```
Because every panel and frame is plain numbers, you can reason about what the camera shows at each
cue — and then confirm it with `render.py --screenshot`, which films the real page frame by frame at the
times you choose, the way the MP4 is made.

## 8b. Film grammar — structure, camera, cuts

The video is planned and shot like a film, not laid out like pages. The narrator plays the director: the words decide
where the eye goes, and the picture follows them.

**Structure: one world per chapter, cuts between chapters.**
- Inside a chapter, the scenes live in **one continuous world**, and the camera travels between its regions. Moving
  from A to B says that A and B belong together: a cause and its effect, a step and the next, a part and the whole.
- Between chapters, and wherever the topic, time or place changes, **cut**. The cut shows that something else begins;
  it never replaces the spoken cushion that closes the old topic and turns to the new one (SKILL.md → Every topic
  change gets a cushion).
  The signature transition (§12) carries the chapter changes.
- A contrast or a reversal can also be a hard cut (a smash cut), inside a chapter too.

**The camera moves only for a reason.**
- push in: this is the point, look closer ("여기 보시면");
- pull out: here is the whole, the context, the reveal;
- pan or tilt: follow something that moves, or uncover what was off screen;
- track: travel alongside a moving thing;
- focus pull: the narration names one thing, so only it is sharp.

A move with no reason in that moment's words is decoration; the camera stays still instead.

**Making a camera in 2D.** A move is a transform on the world, and depth comes from parallax: near layers move more
than far ones, so a push-in feels like going closer, not like scaling a picture. A wide feel (strong perspective,
energetic) or a long-lens feel (compressed, calm) follows the scene's character. Focus can guide the eye where a box
or an arrow would have.

**Shot size and angle carry meaning.**
- Sizes: long (context), medium (relations), close-up (the point, the feeling), extreme close-up (the detail), insert
  (an object).
- Angles: looking up makes a thing big or imposing. Looking down shows the whole and makes things small. A top-down
  view reads as a map or a plan.
- Framing: leave room on the side a thing faces or moves towards (lead room).

**Continuity.**
- Keep screen direction through the whole video: progress, the future and growth run the same way every time (→,
  and up for more). Crossing it on purpose means going back or turning around.
- Connect shots by what survives the cut:
  - a match cut by shape;
  - a cut on an action, in the middle of a movement;
  - an eyeline cut, to what someone looks at.
- Start each chapter by establishing the world (wide), go in to the details, and come back out at the end of the
  chapter.

**Cuts and the voice.**
- Cut at a phrase boundary of the narration, never inside a word.
- Make the J-cut the default joint between scenes: the next line starts and the picture follows it. An L-cut, where
  the picture changes while the last words finish, lets a feeling linger.
- Shot length follows information. Shots get shorter towards the climax, and a shot to breathe follows the peak.

**A list is a montage, not a column.** Several items become short shots with the same framing and the same move,
cut to the rhythm of the words. It is never a stack of bullets (SKILL.md → No slides, no boxes).

**Withhold, then reveal.**
- Keep the result off screen, covered or out of focus until the words name it.
- Plant early what pays off later: an object glimpsed at the start that means something at the end.
- A last shot that answers the first one closes the piece.

**Mise-en-scène.**
- Blocking: where each thing stands and moves in the frame.
- Staging in depth: foreground, middle and background.
- Light as attention: a key light on the hero, the rest in shadow.
- A colour script: the colour of each chapter along the arc, planned in the storyboard.

## 9. Visual devices (snippets)

**Film grain** (static, cheap — put once in `#stage` as a persistent layer; use it when it suits the film's world and keep it fine, references/cinematic-look.md §3):
```html
<svg class="grain" width="1920" height="1080" aria-hidden="true"><filter id="grainF"><feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.06 0"/></filter><rect width="100%" height="100%" filter="url(#grainF)"/></svg>
```
```css
.grain { position: absolute; inset: 0; pointer-events: none; mix-blend-mode: overlay; z-index: 50; }
```

**Soft gradient blobs** (blur is static; only transform animates):
```css
.blob { position: absolute; width: 900px; height: 900px; border-radius: 50%; filter: blur(140px); opacity: .45; }
```
```js
tl.to('.blob.b1', { x: 260, y: 120, duration: data.duration, ease: 'sine.inOut' }, 0);
```

**Dot / line grid background**:
```css
.grid { position: absolute; inset: 0; background-image: radial-gradient(rgba(255,255,255,.12) 1.5px, transparent 1.5px); background-size: 48px 48px; }
```

**Underline draw / strike-through** — a `<span>` with an absolutely positioned `::after` bar tweened
via a CSS variable (see the highlight recipe in player-api.md), or an inline SVG path with DrawSVG.

**Icons** — draw simple stroke icons as inline SVG (24–48 viewBox, 2–3px strokes, round caps) in the
shape language of the piece; animate with DrawSVG. Don't use emoji (renders differently per OS) or
remote icon fonts.

**Screens and UI mockups — only when the story shows a screen** (the product, a phone, the user's browser). Draw the
device as an object: a rim, a reflection across a corner, light spilling below, a ground shadow (look.css `.mon`),
`box-shadow` set once (don't animate shadows). 3D flip: parent `perspective: 1400px`, tween `rotationY`. Never use
card styling to box the video's own text (SKILL.md → No slides, no boxes).

**Scramble / typing** for tech tones:
```js
K.kick('#s02 .code', 'c02', { dur: 1.2, chars: '01<>/{}' });   // FXKit (fx-kit.md): deterministic scramble
// not tl.to(…, { scrambleText }) — GSAP's ScrambleTextPlugin uses Math.random: different letters after every seek
tl.to('#s03 .typed', { duration: 1.5, text: { value: '코드로 만드는 영상' }, ease: 'none' }, 'c03');
```

**Speed/impact** — a quick `scaleX: 1.15, skewX: -8` squash on arrival, then settle; a flash (a full
white div from `opacity .6 → 0` in 0.25 s) on a big reveal. Use once or twice, not every scene.

## 10. Anti-patterns

- **The infographic look** — thin lines, outlined circles and small icons floating on a flat dark gradient, a small
  diagram in the centre and labels beside it, the same layout chapter after chapter. Clean is not designed: rebuild it
  as a lit, material world (references/cinematic-look.md); never decorate it with particles or more labels.
- **PPT or document design — the worst one.** Title bar + content, rounded cards or panels of text, icon-heading-
  description tiles, bullet lists, tables, boxes with arrows, grids of tiles, scenes that swap like slides. However
  neat, the user rejects it outright. Rebuild the scene so the content itself is the picture (SKILL.md → No slides,
  no boxes).
- Transcribing the narration onto the screen, sentence after sentence.
- Every element fading in the same way; every scene centred at the same size; the same layout slot
  scene after scene with a static camera and an unchanging background.
- Drawing the punch line small: a gesture the script is about, rendered as a few pixels in a wide shot.
- Rainbow palettes, gradients on text everywhere, drop shadows on everything.
- Tiny text, text touching edges, orphaned one-syllable last lines.
- Dead air: a frozen layout while the narrator speaks for 4 seconds.
- Motion that ignores the words (the number appears after it was said).
- Random transitions — six different wipes in a 40-second piece.
- Anything not made here: stock photos, icon sets, clip art, downloaded models or textures, a look borrowed from
  another video, characters or logos the user didn't provide. Every visual is drawn originally from type, shape,
  colour, SVG, canvas and your own 3D scripts (SKILL.md → Originality); only files the user gives you are used as
  given.
- Ending abruptly: the last narration word followed by an instant stop. End with a resolved final frame
  (title/logo/key line) that holds for the `tail`.
- **Emphasis without a reason.** Groups that dim and brighten by a rule the viewer can't see, such as
  a table of contents half-lit by an arbitrary split, read as a mess ("기준이 뭐야?"). Every state change
  must be explainable in one sentence. Otherwise use the simple version (items arrive in order at one
  brightness).
- **Double moves.** An element that shows its CSS default (a full bar), resets to 0, grows, then
  shrinks. Give each element one clean move from a start state set at build time (player-api.md §4).
- **Jolts.** A one-frame jump when `transform-origin` changes on an element that is already scaled. Use
  one origin for every scale tween on that element.
- **Style collisions.** Generic class names (`.tag`, `.card`) reused in another scene inherit that
  scene's layout. Scope styles by scene (`#s05 .tag`) or use distinct names.
- **Detached companions.** A glow, flare, label or rope that computes its own position drifts off its
  object when the camera moves. One source of truth per object (player-api.md §4).
- **Wrong-world effects.** A camera lens flare under water, bubbles that sink, a shadow towards the light.
  Effects must belong to the world the shot is in.
- **Type effects that fight the words.** A glitch on a calm line, jelly on a tragedy, a word shattering
  before anyone could read it, or a different type effect on every line. Pick the effect for what the line
  means (type-fx.md §6, §11) and save breaks for the peaks.
- **Clipped glows.** A `text-shadow` glow on masked kinetic type or rolling digits is cut at each
  character's box and leaves faint rectangles behind the letters. Glow the parent with
  `filter: drop-shadow()` instead (player-api.md §4).
- **One flat wipe for every section change.** It is consistent, but it is not designed. See §12.

## 11. Pre-delivery checklist

- [ ] **No frame would pass as a slide or a document page**: no boxes, cards, panels, bullet lists, tables or
      box-and-arrow diagrams holding text. Boxes appear only as story objects drawn with material and light.
- [ ] The visual idea recurs across the piece; palette and type follow the tokens.
- [ ] Shot sizes vary (long / medium / close-up / ECU / insert); no layout slot three times in a row;
      the key gesture of each beat gets a close-up; colour or camera changes as the story escalates.
- [ ] Every cue has a meaningful visual change, landing with (not after) its words.
- [ ] Key words/numbers are the largest elements on screen when spoken.
- [ ] No text under 26px; all text inside the safe area; widths estimated for the longest phrases.
- [ ] Transitions overlap; no stretch is frozen for lack of a plan while the narrator talks (a held beat with a
      reason is fine).
- [ ] `check.mjs` passes; `smoke.mjs` shows the expected scene and text for every cue and no scene-less gaps.
- [ ] `check_fonts.mjs` passes: every glyph on screen (captions included) comes from an SIL OFL 1.1 catalogue font installed in `fonts/` with its licence file.
- [ ] You looked at render.py sheets (the whole video, each chapter, every key moment) and re-shot what you fixed;
      snapshot.mjs reports no unintended layout warnings.
- [ ] Opening frame (t=0) is intentional (it's what shows while fullscreen settles), and the last frame
      is a clean, resolved composition.
- [ ] Every emphasis/dim state has a one-sentence reason; no element flashes its default state before
      its entrance; no one-frame jumps (render.py sheets at `--gapframe 1–3` across every transition).
- [ ] Data beats carry an on-screen takeaway, not only the numbers (script-writing.md §2).
- [ ] Every camera move, cut, match cut and impact has a reason in that moment's words or story (§8b, §12); a
      signature transition carries the chapter changes; no effect is there to fill a count.
- [ ] The hero lines have typography that does something meaningful (type-fx.md): each one's treatment
      says what the line says, stays readable while spoken, and leaves a clean frame behind.
- [ ] `snapshot.mjs --seekcheck` passes: every frame looks the same when reached again (no accumulated state).
- [ ] The elevation pass ran (references/elevate.md): an art director scored every chapter on 연출, 그래픽 디자인 and
      모션; every chapter reached 4 on all three (or what is left is in the hand-off), with before/after sheets.

## 12. Creative craft — what makes it motion *design*

Correct timing and clean layout are the floor, not the goal. Users expect the piece to look *designed*
("모션디자인의 정수", "크리에이티브한 모션디자인"), whatever the subject. Plan these in the storyboard,
not as decoration added at the end:

- **A signature transition that comes from the concept.** Build section changes from the piece's own
  shapes: the brand's or logo's forms as staggered bars, the recurring line that sweeps and becomes
  the next layout, a number that grows to fill the frame. Pair it with a chapter card (big number and
  title) so every section change is a small title sequence rather than a flat panel.
- **Match cuts and morphs as the default connective.** Something should survive each cut: a wordmark
  shrinks into a slot, a bar becomes a dial arc, a dot becomes the next scene's background, a word
  becomes a headline. Use one wherever two moments are really connected; there is no quota.
- **Kinetic typography with rhythm.** Split to chars or words behind a mask, stagger to the speech,
  contrast scale and weight inside one line, and let a keyword swell, change colour, or get struck
  through as it is spoken. Headlines should rarely just fade in.
- **Type as material — expressive typography.** Beyond moving letters around, let the type *become* what the
  line says: a record shatters like glass, a word sinks and sways, pressure crushes the letters, Hangul
  assembles from its jamo, a name dissolves into dust, the outline ripples like water or melts in heat, a sign
  flickers on, a title turns into a solid block. TypeFX (`type-fx.md`) gives the representations (DOM units,
  copies, glyph outlines, pixel tiles) and one channel system to write any such effect; its presets are
  examples, not a menu. Keep the reading moment: the line holds still and legible while it is spoken, and the
  effect happens around it.
- **Anticipation, overshoot, follow-through.** A small pull-back before a big reveal, an overshoot on
  arrival (`back.out`, `elastic` on physical objects), settling secondary motion (a bell that rings,
  a scale that wobbles before it tips).
- **An impact kit for the moments that truly peak.** Which moments those are comes from the story, not from a
  count. Use a light-glint sweep across a hero number, a
  shockwave ring, a particle burst, a 2–4 px camera shake, a brief flash, and an RGB-split
  (chromatic) slam for a warning word. Used everywhere it is noise; at the peaks it is the moment
  people remember.
- **Data as motion.** Bars with a bright leading edge and a trail, counters whose digits roll or
  blur-in, needles with ghost trails, lines drawn at the speed of the sentence, and cells or particles
  that pour, fill, or explode to show quantity.
- **Depth.** Separate background, mid-ground and type layers that move at different speeds with the
  camera. Add light perspective (a tilted grid, `rotationX/Y` on cards) and soft glows behind heroes.
- **Colour as story.** Shift the whole frame's temperature with the arc: calm, then hot at the peak,
  then red at the risk, then resolved at the end.

- **Light and focus on the GPU (shader FX).** When the meaning is light, energy, focus or emergence, go past
  CSS glows: a selectively blooming hero, light rays that carry the cut, a depth-of-field pull to the object
  the narration names, a dissolve shaped like the next scene, a lens flare on the hero shot, tens of thousands
  of particles gathering into a structure. Recipes and costs in `shader-fx.md` (FX build, `StageFX`).
- **One primary effect per beat.** Each beat gets one main effect (plus one or two supporting) chosen because it
  says what the line says; heavy GPU effects at most one per beat. A different effect on every beat is noise,
  the same effect everywhere is wallpaper — vary the treatment with the story's density: sparse → gather →
  peak → resolve → still.

All of these must stay deterministic and seekable: canvas effects as pure functions of `t`, shaders on
`fx.uTime` (never TSL `time`), and flashes, shakes and glints as tweens on `tl` (player-api.md §4). Verify each
on render.py sheets (`--gapframe 1–3`). An impact effect that lands after the word is worse than none.
