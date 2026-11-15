# Elevate — the aesthetic pass (고도화)

**Defect-free is the floor, not the goal.** The user's verdict on videos that had passed every check: "연출에 대한 아쉬움,
더 섬세한 그래픽 디자인 모션의 표현 등등 전체적으로 미적인 부분에서 큰 아쉬움들이 있어." Their sheets showed why: dark
frames holding three thin lines, the same composition for nine seconds, small grey labels, diagrams on an empty stage.
The builders had stopped when a pass found nothing *wrong*. This pass keeps going until the piece is *designed*.

An elevation that judges each frame against the frame before it tends to add layers to the same compositions, and the
result can be unattractive in itself and barely distinguishable from the first build. So the director scores against
an **absolute bar** — a still a motion studio would put in its reel, built as a crafted world (SKILL.md → **A crafted world from the
first build**, references/cinematic-look.md) — never against the previous version, and a round that only decorates
does not count.

It is not optional and it does not wait for the user: it runs after the first complete build has passed the gates
(SKILL.md step 7), after a redesign you carry out, and on any stretch the user calls flat ("밋밋해", "아쉬워"). The
standards it applies are already written down — motion-design.md (§5 motion language, §7 composition, §8–8b shots and
film grammar, §12 craft), craft-notes.md (the owner's floor and critiques), type-fx.md. What was missing is someone who
holds the work to them.

## Contents
1. Two roles: the builder and the art director
2. What the director gets
3. The rubric: direction, graphic design, motion
4. What the director returns
5. What the builder does with it
6. Rounds, stopping, reporting

## 1. Two roles: the builder and the art director

You built the video, so you are the worst judge of it. The **art director** is a separate subagent (the Agent tool,
general-purpose) with no stake in the code: it looks at the pictures, scores them and asks for changes. It never edits
files, never runs anything but reading the sheets you give it, and never looks at the picture any other way — put
SKILL.md's "Looking at the picture" section in its brief **word for word**. When no subagent can be started, do the
director's job yourself in a separate, written step with the same rubric and the same output, and score as a stranger
would: a frame you can explain is not therefore a good frame.

## 2. What the director gets

Shoot fresh render.py sheets for the round (`--out <dir>/screenshots/elevate-<n>`) and give the director their full paths:
- the whole video at `--gapframe 120`;
- every chapter (or every 30–40 s) at `--gapframe 30`;
- every transition and camera move frame by frame (`--from A --to B --gapframe 3`);
- the hero frames at stage size (`--at T --res 1080p`), and small type at `--crop … --res 4k`.

Also `storyboard.md` (the world bible, art direction, shot list) and `script.txt`, so it judges the picture against
what the line says. Nothing else: no code, no logs. Before the whole build the director also scores the look-dev hero
frames (cinematic-look.md §4): one per chapter at 1080p. When an earlier version exists, give its sheets too, and the
director checks the 850 px side-by-side difference. When earlier films made with this skill are available, give a
whole-video sheet of one or two of them as well, so the director can see whether this film repeats them.

## 3. The rubric: direction, graphic design, motion

Score every chapter 1–5 on each axis (5 = a motion designer would put it in a reel), with the tile ids (`frame m:ss.ff
[cue]`) that justify the score. The look-fors are prompts, not a checklist to tick. **The scale is absolute**: 3 is competent
explainer graphics, 4 is a crafted world with material, light and depth that a viewer finds beautiful on its own, 5 is
reel-worthy. The infographic look (thin lines and small diagrams on a dark gradient, a label column
beside them) scores at most 2 on graphic design, however clean it is.

**A. 연출 — direction**
- The concept object/idea is present and keeps changing role; the chapter has a world, not a backdrop.
- Shots vary (wide · medium · close-up · insert); the key gesture of each beat gets its close-up; no layout slot three
  times in a row; nothing holds the same composition for more than ~2 s while words go on, unless the stillness means
  something.
- The camera moves for a reason in the words (push-in on what is named, pull-out for the whole) and stays still
  otherwise; no habitual drift.
- Staging: one focal point per moment; the eye is led — where it lands at a cut is where the next shot starts; reveals
  are withheld and land on the word.
- Rhythm: density follows the story (sparse → gather → peak → resolve → still); the peaks are visibly peaks.
- Joins: something survives the cut (match cut, morph, the travelling object); chapter changes carry the signature
  transition; no hard pop, no fade-swap of unrelated layouts.

**B. 그래픽 디자인 — the finish of the frame**
- Composition: a grid and balance you can name; negative space that is chosen, not left over; vertical centre of mass;
  alignment between elements that belong together.
- Scale and hierarchy: one hero, clearly the largest thing when its word is said (120–220 px); support legible
  (never under 26 px at 1080, more for long lines); a clear second and third level, not ten equal labels.
- Typography: weight and size contrast inside a line; tracking for display sizes; line breaks at phrase boundaries,
  no orphan syllable; hero lines with a treatment that says what they say (type-fx.md); numerals set as numerals.
- Colour and light: one palette, one or two accents with a job; value contrast that reads on a phone; a key light or
  glow that makes the focal point; temperature that changes with the story.
- World, material and depth: the frame is a place in one designed world (the world bible), not a backdrop behind a
  diagram; background, mid-ground and foreground layers with focus and haze; texture, falloff, rim and contact shadow;
  objects drawn with material — never thin lines floating on flat black; one motivated key light, the focal object the
  brightest thing; type made of the world's material.
- Detail: consistent stroke weights and caps, consistent icon language, things that touch actually touch, nothing
  meaningless on screen.

**C. 모션 — the expression of movement**
- Easing with intent: confident entrances (`expo.out`, `power4.out`), quicker exits, no linear start/stop.
- Choreography: hierarchy in time (the focal element first and most), overlaps of 0.2–0.4 s, staggers in the rhythm of
  the speech; never everything at once with one tween.
- Physicality: anticipation before big moves, overshoot and settle on arrival, follow-through and secondary motion
  (what is hit reacts, what hangs swings).
- Continuity: elements travel, transform and hand over rather than fade out and in.
- Life: while words go on, the thing they name moves; ambient life is subtle and never the only motion.
- Contrast of speed: fast against slow, accents on the stressed syllable, held beats before reveals.

**D. The floor — any hit is a must-fix, whatever the scores**
A frame that would pass as a slide or a document; the infographic look (thin lines, small diagrams, a label column on a
flat dark stage); text under 26 px; overlaps and clipping; a stretch frozen for lack of a plan; three tiles in a row
with the same layout; an effect landing after its word; dead air (references/sound.md); against an earlier version, a
stretch that looks the same at 850 px (background, hero size and composition unchanged).

## 4. What the director returns

```
## Round <n> — scores
| chapter | A 연출 | B 디자인 | C 모션 | why (tile ids) |

## World check
- does each chapter read as a place in one lit, material world (tile ids)? where it reads as an infographic instead
- does the film repeat earlier films made with this skill — world, palette, key light, finish, camera language,
  materials, transition — without the subject calling for it? what should change

## Must-fix (the floor)
- <tile id> — what is wrong

## The upgrades that matter most (ranked by impact, 6–10)
1. <cue / time span> — what the sheet shows now (tile ids) → what it should become, concretely: the shot, the layout,
   the move, the type treatment; a technique to look up (`cokacmotion.mjs search <words>`, or a demo id).
…

## Keep
- what already works and must survive the changes
```

Concrete means buildable: "c05–c07: the dial holds still for 9 s (tiles 1080–1620) → push in to the day half on
'여름엔', stretch the 12 day wedges as the line says 길고/짧았어요, cut to a close-up of one wedge with the hour length
as hero type" — not "make it more dynamic".

## 5. What the builder does with it

- Fix the floor first, then take the upgrades from the top.
- **Re-create, don't decorate**: a weak beat is redesigned from its concept and the world bible (a new shot, a new
  picture of the idea in the world, real material and light), not given small added effects or labels. A round that only
  adds layers to the same frames does not count as a round. When the world bible itself is the problem, rewrite it
  first (cinematic-look.md §2). Find each new technique in cokacmotion (SKILL.md step 5) and rebuild it for this video.
- Keep what the director said to keep. Keep the determinism rules (player-api.md §4).
- Re-shoot exactly the stretches you changed, before and after (`--out screenshots/before`, `…/after`), run the gates
  (`check.mjs`, `errscan.mjs`, `snapshot.mjs --seekcheck` when canvases or caches changed).
- You may disagree with an upgrade: say why in one line in the next round's brief; the director decides.

## 6. Rounds, stopping, reporting

- Up to three rounds by default. Stop earlier when every chapter scores at least 4 on A, B and C **on the absolute
  scale** and nothing is left on the floor; go on past three only when a round still raised scores and the user asked for the best possible.
- `진행상황.md` keeps each round: scores, the upgrades done, the paths of the sheets.
- The hand-off (SKILL.md step 8) reports the elevation: rounds, the scores before → after per axis, the most visible
  changes with their before/after sheet paths, and what the director still wanted that was not done (and why).
- Time: each round costs a fresh set of sheets and the rebuilds — on a machine without a GPU tens of minutes. Each
  render.py command builds the page once, so a round's moments go into as few commands as the looks allow. It is
  the part of the job the user notices most; spend it.
