# The cinematic look — a crafted world from the first build

A video can be correctly timed, free of defects and even "elevated" once, and still be unattractive in itself. When
it is, the cause is almost always the same: the picture was built as diagrams on a stage instead of as a place, and
the elevation judged each frame against the frame before it, so it added layers to the same compositions and changed
nothing a viewer can see. Rebuilding the same content as a lit, material world makes the difference obvious at a glance.
This file describes how to build that way **from the first build**, so the first version is already the film and the
elevation pass refines it instead of rescuing it.

**It applies to every kind of video the skill makes** — explainers and documentaries, promotional and brand films,
intros and title sequences, shorts, kinetic typography, product and software demos built on recordings, sponsored
briefs, data stories, lectures. Their content and tone differ; the bar does not. What changes from one kind to another
is what the world is made of (§2), never whether there is one.

## Contents
1. The bar, and the look it replaces
2. Start from a world (the world bible)
3. Material, light, depth, camera, type — how each is made
4. Look development: hero frames before the whole build
5. Building it: chapters, builders, join contracts
6. Failure modes to guard against
7. Never the same film twice
8. Calm, not busy

## 1. The bar, and the look it replaces

**The bar:** every frame could stand as a still in a motion studio's reel. Put any frame next to the obvious, literal
version of the same line, both shrunk to about 850 px wide: they must differ in three ways at once —
- **background**: a designed space with surfaces, light and depth — whether it is a real place, a painted one or an
  abstract graphic one — not a flat dark gradient;
- **hero size**: the thing the line is about dominates the frame when it is the subject, instead of a small figure in
  the middle;
- **composition**: perspective, depth and a diagonal led by the light, instead of a centred figure with text beside it.

**The infographic look** is what a build drifts into when nobody holds this bar, and it counts as a failure, not as a
style: thin vector lines and outlined shapes floating on a dark gradient; a small diagram in the centre with a number
or labels next to it; the same two-part layout repeated chapter after chapter. Adding particles, glints, trails or more
labels to such a frame does not change what it is. A frame with the infographic look is redesigned from the world
(§2), never decorated. When the content is data, the data is still shown — as an object in the world, with material,
light and depth, made of what the story is about — never as thin lines on an empty stage.

## 2. Start from a world (the world bible)

Before the shot list, decide **one world** in which the whole film takes place, and write it at the top of
`storyboard.md` as the **world bible**. The camera travels through this world; each chapter or section is a place in
it or an object in it, so moving from one idea to the next is moving through the world rather than replacing one layout
with another.

A world is any coherent, designed space with its own surfaces, light, depth and camera. It can be:
- **physical** — the place where the subject happens or the objects it is made of, shown as things that exist, lit and
  seen through a lens;
- **illustrated** — a painted or drawn universe with its own consistent hand, materials and light;
- **graphic** — an abstract space of designed forms that still have surface, light, depth and scale relations, never
  flat shapes on an empty stage;
- **typographic** — letters and words as the architecture and the material of the space;
- **the product's own environment** — for demos and sponsored pieces, a set in which the screens, recordings and
  devices sit as lit objects (RecKit's browser window, a phone, a monitor) rather than flat rectangles.

Choose it from the content and its purpose: what the subject is and where it happens, what the viewer should feel and
remember, the brand or the user's material when there is one, and where the video will be watched (its aspect and
length). Whatever kind it is, the rest of this file applies to it: material, one motivated light, depth, a camera
language, type that belongs to the space, and a recurring object.

The world bible states, concretely:
- **the world and, per chapter or section, its place or object**: what is there and what it is made of;
- **one key light per chapter**: its direction, its colour, the thing in the world that emits it, and how it changes as
  the story moves;
- **the materials** and how each is made (§3);
- **the depth plan**: which planes each scene has — an out-of-focus foreground, the sharp hero, a hazy background;
- **the palette, with one job per colour**: one colour always means the current hero or "now", others mean specific
  roles in the story (evidence, energy, life …), so colour carries meaning instead of decoration;
- **type as material**: what the hero words and numbers are made of in this world and how it would make them, so they
  belong to the scene instead of floating over it;
- **the recurring object's form**: the concept object has material and weight in this world, and a role in each
  chapter or section;
- **the camera language**: the default angle and what each kind of move means, and **the signature transition**,
  built from something in the world;
- the owner's standing taste (calm; one impact per peak; no shake or punch zoom unless asked).

The concept (motion-design.md §1) is chosen as a world first. An abstract organising system — a line that travels, a
grid that fills — is a device used inside the world, not a replacement for it.

## 3. Material, light, depth, camera, type — how each is made

Everything below runs in the browser and is a pure function of `t` (player-api.md §4); anything expensive is drawn once
into textures at build time. Find each technique in cokacmotion (step 5) and rebuild it for the subject.

**Material** — no object that matters is a flat fill. Each surface is built from three parts: a base texture baked from
noise at build time; shading computed from the key light's direction (a height field turned into normals and lit), so
the surface shows relief; and the surface's own response to light — rough surfaces scatter it, metals carry a highlight
that slides as the camera moves, transparent surfaces show a bright rim and bend what is behind them, liquids mirror
the world above them in broken bands. Living surfaces get three tones (shadow, middle, light), a rim on the light side
and a contact shadow; repeated creatures or plants vary in size, pose and colour instead of being stamped copies.
Regular, evenly spaced lines on a natural surface read as manufactured (planks, tiles) — break them.

**Light** — one key light per scene, motivated by something in the world. Every object it touches gets a rim on the lit
side and a shadow on the other; the focal object is the brightest thing in the frame and the only one that blooms;
hero type takes the same light. The light changes with the story: the colour temperature shifts between chapters, and a
light that turns on or swings can be the beat itself. One finish is chosen for the whole film from its world — a colour
grade, a vignette, bloom on the brightest parts, or nothing at all — and applied once for all chapters, not per chapter.
Grain, like every part of the finish, is used when it suits this film and left out when it does not; when used it is
kept fine, because heavy per-frame grain costs bitrate and breaks up in compressed video.

**Depth** — as many planes as the world needs, usually several: an out-of-focus foreground that moves fastest with the camera, the sharp
hero, and a background softened by haze, with distant things lighter, cooler and lower in contrast (atmospheric
perspective). Attention moves from one thing to another by a focus pull or a camera move, not by fading one layout
into another.

**Camera** — a camera language chosen for the world in the bible: its angle, lens, distance and the way it moves.
Whatever it is, it shows space — perspective, overlap, parallax — rather than the flat plane of a diagram, and each
kind of move keeps one meaning through the film (moving closer to look at something named, moving back for the whole,
a fast move for a change of subject, a journey across scales in log space). The same composition does not hold for more than about two
seconds while the narration continues, and every move has a reason in the words.

**Type as material** — hero words and numbers are large (motion-design.md §2 sizes), made of the world's material as the
world bible says, lit by the key light and placed inside the scene so that objects can pass in front of them. Support
text is at least 34 px, at most two blocks on screen, placed next to what it names; nothing under 26 px.

**Tools** — Canvas 2D for painted planes and baked textures; small hand-written WebGL where light and material need
real computation (a lit sphere, relief from a height field, depth of field, bloom) — a normal tool, not an exception;
the DOM for text that must stay text; the StageFX/three.js stacks (shader-fx.md, threejs-3d.md) for beats that need
real 3D or shader effects.

## 4. Look development: hero frames before the whole build

Before building every beat, build **one hero frame per chapter** (three to five for a short film) to the bar, with the
real materials, light, depth and type, and look at them at `--res 1080p`. The art director (elevate.md) scores these
frames against §1, and the rest is built only when they reach 4 on graphic design. A world that does not hold up in a
single still will not hold up in motion, and fixing it here costs a fraction of fixing it after the whole build.

## 5. Building it: chapters, builders, join contracts

- A film with chapters is built **one builder per chapter** (a subagent, or you chapter by chapter), every builder
  reading the same world bible. One owner holds the shared look layer, the shared art modules and the signature
  transition; nobody else edits them, so the film keeps one look.
- Parallel builders work in separate copies (detached git worktrees) and the integrator merges them; each builder edits
  only its own chapter's code and files.
- Every brief carries **join contracts**: the exact last frame of one chapter and the first frame of the next — the
  position, size and angle of anything that continues across the cut, the light, which side is which — and who draws
  what at the seam. After merging, the integrator looks at every seam frame by frame, because two builders who each
  look right on their own can still disagree at the cut.
- A chapter at this level needs several rounds of building and looking; plan the time for it rather than a single pass.

## 6. Failure modes to guard against

- **Canvas memory:** every baked texture and offscreen canvas counts against the browser's canvas memory. When the total
  is too large, textures are silently dropped and draw nothing. Keep a pixel budget per chapter (roughly 30–40 million
  pixels), bake at reduced size anything that will be blurred, share one compositing canvas, and release GPU textures
  once they have been baked.
- **A single error removes a whole file:** a syntax error anywhere in one script stops the whole file from loading, and
  everything it draws disappears. Look at every chapter's sheet after every change or merge,
  not only the chapter you edited.
- **Two tweens writing one property:** when a new tween starts before an older one on the same property has finished,
  whichever finishes last wins, and the result can differ between playing and seeking. Make the later tween the last
  writer — `fromTo`, durations that end before the next one begins.
- **State that depends on how a frame was reached:** anything forced on a layer outside the player's scene windows
  (visibility, a position kept from a previous frame) can leak into other chapters only after a jump. Let `scene()` own
  visibility, write positions from closed forms of `t`, and check with `--via`.
- **Seams between builders:** a shared object can change shape, lose a part or double up across a cut when its two halves
  were drawn separately. Join contracts and a frame-by-frame look at every seam catch it.
- **Rendering cost:** without a GPU, lit scenes and shaders render slowly frame by frame, and every render.py command
  first builds the whole page — every texture, shader and baked plane of the film — which is often most of a short
  command's time. Decide which looks are needed before shooting sheets, put the moments one look needs into one command
  (render.md → Size and time), and shoot the commands one at a time.

## 7. Never the same film twice

The bar is raised by the standard and the process in this file, never by a fixed look. A look that is applied to every
film — the same dark stage, the same accent colour, the same finish, the same camera angle and lens, the same kind of
material, the same transition — makes different subjects look alike, which is its own kind of failure. So:
- the world bible chooses the world, palette, key light, finish, camera language, materials and signature transition
  from this subject; it also names the choices that would simply carry over from earlier films and says what replaces
  them, unless this subject itself calls for them;
- nothing in the template or in a shared module decides the look; techniques are looked up and rebuilt for each film;
- the art director compares the film with earlier films made with this skill when they are available and flags what
  repeats without a reason in the subject (elevate.md).

## 8. Calm, not busy

The owner's taste still holds (craft-notes.md): the strongest videos rest on one clear idea, and scattered rings, pings
and bursts are noise. The cinematic look is the **production value of the world** — material, light, depth, camera and
type — not a larger number of effects. One impact per peak, no shake or punch zoom unless asked, and stillness when it
means something.
