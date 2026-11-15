# Craft notes — what the user's best videos have in common, and the Kling video's lessons

Two sources: the user's own finished videos and the revision requests they made on them, and the review rounds of the
9-minute Kling 4.0 campaign video. Read with motion-design.md; where they differ, these notes are
the user's own taste.

## Contents
1. The owner's quality floor
2. What the strong videos share
3. Techniques: showing, rhythm, emphasis, depth
4. The look (css/look.css)
5. Devices that worked
6. The user's design critiques — check these before handing over
7. Code habits

## 1. The owner's quality floor

The user asks for the same "한 차원 업그레이드" again and again — and judged videos that passed every check with "연출에
대한 아쉬움, 더 섬세한 그래픽 디자인 모션의 표현 등등 전체적으로 미적인 부분에서 큰 아쉬움들이 있어". The elevation pass
(references/elevate.md) exists for that. This is the floor, not a bonus:
- **never PPT or document design**: no boxes, cards, panels, bullet lists or tables holding text, and no slide-like
  scene swaps. The content itself is the picture (SKILL.md → No slides, no boxes);
- a scene of only text and simple shapes becomes an **illustration, diagram or motion that shows the content**;
- entrances, exits and transitions **overlap with eased rhythm**;
- key words and numbers get **one emphasis effect** each (FXKit, TypeFX);
- the background has **depth and material** (layers, light, particles) — no empty screen;
- the film is **a crafted world from the first build** — a lit, material place the camera travels through, never the
  infographic look of thin lines and small diagrams on a dark gradient (SKILL.md → A crafted world from the first
  build, references/cinematic-look.md); a pass that only adds layers to such a picture changes nothing a viewer can
  see;
- colour and type are **one system** through the whole video.
Also from the edit histories: no "follow along" call to action, hide anything that could be personal data, never
apologise at the end, write 5+ titles and pick the most curious one.

## 2. What the strong videos share

1. **One object travels through the video and turns into the explanation** (an apple's fall becomes the moon's orbit; a
   light cone becomes a "guess" bar; the signature transition is done by that object — a yawning mouth swallows the
   frame, a mosquito's compound eye becomes the iris).
2. **More effects did not make a video do better.** The most decorated pieces did worst with viewers; the plainest, built on one
   clear idea, did best. Depth and texture are the floor; rings, pings and bursts scattered without a budget are noise.
3. **The first frame is already a moving question, and it is about the viewer** ("참아 보세요", "왜 하필 너를").
4. **A progress device stays on screen the whole time** (a holding-on timer, an island clock, a depth rail) and is pulled
   to the centre, large, at the punchline.

## 3. Techniques

**Showing**
- Charts made of the story's own material: stack or stretch the things the story is about (hair on a tape measure, 100
  dots in a glass column, one taxi drawing = 100 taxis). Write the legend on screen.
- Tween one **count** and let N objects land one by one (coins, money bundles) — what melts and what stays can differ.
- **Fraction objects**: 5.37× as five blocks and a sliver. **A big number = one everyday object** (1.9 cm = a coin).
- **A/B setup**: the two things themselves at the same size side by side (two pictures, two screens, two objects —
  never two text cards), the same scan line passing both, chips where they differ; or overlay
  and wipe. **Dashed = hypothesis/plan, solid = confirmed/real.**
- Typographic numbers can carry a scene: "1/10" as a heavy filled 1, a slash, an outlined 10, set diagonally.

**Rhythm and transitions**
- Exits leave staggered 0.03–0.08 s with `power2/3.in`; headlines leave per character upward.
- Entering scenes settle 1.05–1.12 → 1 with `expo.out`; leaving scenes step back to 0.96 and darken.
- Three tiers: between chapters the signature transition (at each chapter change, never between every scene); chapter card → first scene an iris from a focus
  point in the picture; within a chapter a staggered push.
- Match cuts by continuing geometry, not dissolves: the same object changes role (a bar becomes a light cone).
- The picture follows the words: what is said moves when it is said. Stillness is fine when it means something; no
  habitual zoom or drift added just to keep things moving.

**Emphasis**
- Words move the way they mean ("세게" squashes, "바뀜" flips like a card, "사라졌어요" scatters, "그대로" drops and sticks).
- One effect per line, one emphasis per scene, and big impacts only on the moments that truly peak (no count). **Anti-impact**: the biggest moment
  can be the stillest (no flash, a held frame, sepia).
- Numbers: odometer → glint 0.5–1.3 s later → one pop, landing **on the word that says it** (the phrase time you set from the take, `at` → `sync.mjs`).
  Don't roll a labelled value — the in-between numbers read as false statements.
- Honesty tags in the frame: an "추정" stamp, "내 계정 기준", "개념도".

**Depth and material**
- Layer order: gradient → 2–3 wandering lights → the scene's own mid-ground picture → particles at three depths →
  content → vignette. Particles show only inside a light (mask by the light cone) and take the colour of the meaning in play.
- **Grain only when it suits the film**, and kept fine — heavy per-frame grain costs bitrate and breaks up in the
  encode. Nothing on top of recordings or
  generated footage — atmosphere goes around the window.

**Long videos**: references/long-form.md.

## 4. The look (css/look.css)

What made the Kling video read as "filmed" without effects on the content:
- **A studio set per backdrop**: a soft key light from above, a floor that catches it and fades in from nothing (no edge,
  no horizon line — "가로로 만들어진 선은 무슨 의미야?"), one light wandering slowly (closed form of t).
- **A film finish** above everything: a very light soft-light grade (warm highlights, cool shadows) and a vignette.
- **Glass and rim on screens**: monitors and browser windows get a reflection across a top corner, a lit rim, light
  spilling below them, a ground shadow.
- Warm/cool sets per chapter carry the story's colours (amber = plan, cyan = footage) without painting the content.

## 5. Devices that worked

- **Spot + callout** on recordings (reckit.js) — the hole glides between controls; the loop is drawn once.
- **Plan card** (dashed amber) → **footage** (solid cyan rim) when the output fills it; mint ✓ / red mark grades.
- **A price on a taped memo sheet**: header in pencil, the number in ink, values rubbed out and rewritten when the button
  changes, a dated "촬영 시점 · 바뀔 수 있음" note in small pencil — analog, honest, readable.
- **Chapter card**: handwritten chapter number, the question with the keyword largest (the keyword filled with the
  chapter's picture), the other chapters receding on both sides.
- **Money as material**: banded bundles in an isometric heap that grows by count, notes tumbling with depth blur, a
  scan band turning yuan into won — drawn as **sprites** (each note drawn once, placed with drawImage), so hundreds of
  notes run without frame drops.
- **A closing gag** in the user's voice that comes back to the story's premise (the hoodie), with the polaroid of the
  shot and a handwritten question.

## 6. The user's design critiques — check these before handing over

From the review rounds (each was a fix request):
- **Looks like a slide or a document** (boxes, cards, bullets, tables, a title bar): rebuild the scene as a picture.
  This is never a polish note.
- Nothing overlaps: bars, labels, card tags, arrows over a selection box, a leader line over the loop.
- One line per mark: no duplicated outlines, no loop redrawn on every tab switch.
- No flicker: an element shown and hidden by two overlapping schedules blinks — show it once for its whole span.
- No jumps: a background fade must start before the element hides, not after.
- Balance after motion: when things move away (photos flying into a card), the space they left must not go empty —
  keep or refill it.
- Not top-heavy: centre the composition vertically; check every chapter's first frame.
- Underlines and highlights don't break across lines; labels don't intrude into pictures.
- Readable at phone size: nothing under 26 px; heroes 120–220 px; weights ≤ 800.
- Handwriting font only for handwritten things; mono font only for code; Hangul never in D2Coding display.
- Remove what means nothing (a line across the frame, a source chip the user didn't ask for, a stray badge).

## 7. Code habits

- **Set word times** for anything that must hit a word (read off the take, script.json `at` → `sync.mjs`, `cue(id).when`).
- Art modules: `ART.x = { build(el, opts) → { animate(t, state) } }`; the header comment lists viewBox, anchors, classes
  safe to tween, state keys. The timeline tweens meaningful numbers (state); the module only moves its own insides; it
  exports points (`hand()`, `toStage()`) for effects to attach to.
- Keyframes in `onFrame` with an interpolator; zoom interpolated in log space.
- A `track()`/`mover()` that remembers the last value and never overlaps segments (RecKit.track).
- Cache DOM writes (compare with the last value), skip work outside a scene's window, squeeze factor
  `k = min(1, available / natural)` for layouts that must fit.
- `fromTo(..., { immediateRender: false })` for anything that is set before its tween; seeded `rand` only.
