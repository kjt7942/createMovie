# Sound — no dead air, timing to the word

What the viewer hears is the narration plus the footage's own sound. This file covers the rules for that mix: dead air
and timing to the word. In both, **no code decides where silence, a pause or a word is** — the tools only prepare the
level data (`wave.mjs`); you read it and decide, and the tools apply exactly what you wrote.

## Contents
1. No dead air (the user's rule)
2. Timing visuals to the word: phrase times you set (`sync.mjs`)
3. Gaps, chapter windows and re-timing
4. Loudness
5. Reporting numbers

## 1. No dead air (the user's rule)

**No silence of 0.4 s or longer anywhere in the finished sound** — narration and footage together; room tone too quiet
to hear counts as silence. The user trims every such gap when editing by hand and called a 9 s pause after an episode
"너무한다".

- The one exception: pauses **inside** footage the video shows whole (a generated clip's own beats between lines). Never
  cut inside it. Where a clip ends on a silent hold, start the next line over the hold while the picture plays out.
- **The end hold** — from the last sound to the video's end (`tail`, the last frame holding) — is not dead air.

**You judge it; no script does.** Deciding by a fixed level or length in code makes mistakes, so nothing in the skill
says "this is silence" — not at a take's edges, not inside it, not in the footage. Every take is kept exactly as Fish
Audio returned it, the silence before its first word and after its last included, until your cut says otherwise.
`wave.mjs` only measures and prints the sound as numbers, and you read them:

```bash
node <skill>/scripts/wave.mjs <dir>                    # the finished sound: one line per second, the level of every 50 ms
node <skill>/scripts/wave.mjs <dir> --from 60 --to 120  # a stretch of it
node <skill>/scripts/wave.mjs <dir> --cue c05[,c06]     # takes as recorded, in seconds of the take (for a cut, an "at")
node <skill>/scripts/wave.mjs <dir> --unreviewed        # every take not read yet (after recording)
node <skill>/scripts/wave.mjs <dir> --no-narration      # the footage's own sound alone (a dub's rooms, dub.mjs)
```

- **What it prints.** Each number is the level (RMS, dBFS, rounded) of 50 ms of what the viewer hears: the narration plus
  every clip playing its own sound, at its placement and volume. `-inf` is digital silence. Marks sit before the window
  they fall in: `|c05` a cue starts, `c05|` it ends, `|c05(placeholder)` a cue not recorded yet (silent), `[clip:key …
  clip:key]` a clip with sound, `✂` where a cut take was joined, `END` the video's end. 20 numbers are one second, so 14
  in a row are 0.4 s.
- **Zero-crossing rate.** A take (`--cue`, `--unreviewed`) prints every window as `level/zcr`, e.g. `-27/7.6`; the whole
  sound does with `--zcr`. zcr is how many times the waveform changes sign per millisecond — how fast it swings. It is
  measured, never judged: the tool says nothing about what the window is.
- **How to read it.** Compare every stretch with the voice right before and after it. Silence is what a listener hears
  as nothing said and nothing sounding: digital silence, the floor of a take, room tone too quiet to hear, and a lone
  breath in a pause (the listener is still waiting). A soft syllable or a word's fading end is voice, not silence — tell
  them apart by reading the stretch's level and zcr against the voice around it and the words of `say` you expect
  there. Count the windows of each silence; 8 or more (0.4 s) is dead air,
  unless it is the exception or the end hold above.
- **Reading zcr with the level.** The level says how loud a window is; the zcr says how fast its waveform swings. What
  they mean physically: voiced sound (vowels, a hum) is periodic with its energy low in frequency, so it swings
  comparatively slowly; noise-like sound (breath, hiss, the friction of ㅅ ㅈ ㅊ ㅎ, a take's floor) carries more high
  frequencies and swings faster; digital silence does not swing (`0.0`). There is no number that makes a window one or
  the other: read each window against the windows around it in the same take, and against the words of `say` you
  expect there — whether a quiet, fast-swinging stretch is a word's first consonant, a breath or the floor is your
  reading. A worked reading of the user's take op01 ("자 이전…", `--step 0.01`, from 0 s): `-63/2.7 -64/5.6 -59/5.7
  -54/8.6 -41/11.0 -30/12.2 -34/11.2 -39/5.9 -33/1.9 -30/0.8 -21/1.2`. The windows from 0.03 s swing much faster than
  the vowel windows that follow and lead straight into them, and the line begins with 자 — so they were read as its ㅈ,
  and the word as starting at 0.03 s, not where the level jumps.
- **After recording, every new take** (`--unreviewed` lists them; js/cues.js marks them `unreviewed: true`): decide
  what comes out of it — the silence before the first word, after the last, and any pause inside that is dead air — and
  write the cue's `cut` (below), `"ranges": []` when nothing goes. `tts.mjs` applies it; `check.mjs` refuses the hand-off
  while any take is unread, and `dub.mjs` refuses a dub track. Takes cached before 2026-11-09 had their edges cut by the
  old tts.mjs (`--cue` says so): read them like the others; what was cut from them is gone.
- **When.** After recording and every re-take, after any re-timing (`gapAfter`, `leadIn`, `tail`, chapter windows), after
  a clip is placed or moved — and over the whole video before the hand-off whenever it has recorded takes or clip sound.
  While cues are placeholders their stretches are silent by design; the gaps between them are exactly their `gapAfter`
  (§3), so read again once they are recorded.
- **Fix it by where it is** (the marks tell you):
  - **at a take's start or end** (from `|c05` to its first voice, or from its last voice to `c05|`): read the take with
    `--cue c05`, choose where the voice begins and ends — keep the breath into the first word and the fading end of the
    last; cut only in the silence, never into the voice — and cut `[0, a]` and/or `[b, <the take's length as --cue
    prints it>]`; nothing of an edge stretch is kept (no crossfade there);
  - **between two lines** (the silence spans `c04| … |c05`): first the edges of both takes (above), then shorten `gapAfter` of the earlier cue (`leadIn` before the
    first line), run `tts.mjs`, read again;
  - **inside a take** (between `|c05` and `c05|`, with no cue mark inside it): read the take with `--cue c05`, choose the
    stretch to take out — inside the silent run only, never into the voice, leaving enough of the silence on each side that it
    still sounds like a pause between those words (how much is your reading of the pause and the words around it) — and write it as the cue's `cut` in script.json, with the take id that `--cue` printed:
    ```json
    { "id": "c05", "say": "…", "cut": { "take": "d525479975b02b635b5afc45", "ranges": [[1.35, 2.05]] } }
    ```
    `tts.mjs` takes exactly those stretches out (a 10 ms crossfade at each join) and moves the later cues up; then
    `sync.mjs`, and read again. A cut belongs to its take: after a re-take `tts.mjs` says the cut was not applied —
    read the new take and set it again. Another way is a re-take with a reworded `say`, which costs credits: only
    when the user decides;
  - **at a clip's silent tail**: start the next line over it;
  - never by inserting sound effects, never by speeding anything up.

## 2. Timing visuals to the word: phrase times you set (`sync.mjs`)

Only what must land on a spoken word uses `when()` — a number as it is said, a highlight on the word, an item as it is
named; what only follows the line uses a cue label, `at(f)` or `about('phrase')` (references/player-api.md), and needs no
time. Read only the stretch around a phrase: `--from` / `--to` (seconds in the take).

`cue(id).when('phrase')` estimates by character position until you set the phrase's time. No code looks for words or
pauses in a take: you read the take and say where the phrase starts.

1. **Read the take** at 10 ms: `node <skill>/scripts/wave.mjs <dir> --cue c05 --step 0.01 [--from 1 --to 2.5]` — seconds in the take as
   recorded, the clock a `cut` uses. Find where the phrase's first syllable starts: where the voice rises after the pause
   before it, or, inside a run of voice, by counting the syllables of `say` across it against the pauses you see. Read the
   zcr with the level (§1) where the level alone does not show where a syllable begins — compare each window with the
   ones around it and with the sound the phrase begins with in `say`; where it starts is your reading. Then check the
   reading against the words: the syllables of `say` between two points you are sure of (a pause, a clear consonant)
   must fit the time between them at the pace the rest of the take is spoken — a phrase placed so that its syllables
   would have to be said far faster or slower than their neighbours is misplaced (a closure read as a nasal, a dip read
   as a boundary): read it again.
2. **Write it** in script.json, with the take id `--cue` printed and the phrase exactly as it is in the cue's `text`
   (what `when()` looks up):
   ```json
   { "id": "c05", "say": "…", "at": { "take": "d525479975b02b635b5afc45", "phrases": { "천억": 1.35, "영상 그 자체": 3.02 } } }
   ```
3. **`node <skill>/scripts/sync.mjs <dir>`** writes `js/sync.js`: each time moved back by the stretches the cue's cut
   takes out before it. It refuses a phrase that isn't in the text, a time inside a cut or past the take's end.

From then on `when()` returns that moment — numbers land on the word that says them, a highlighter sweeps under the
spoken word. Set a time for every phrase the scenes anchor with `when()` on a recorded cue: for any other the player
uses the estimate and warns once (errscan.mjs lists them); check.mjs warns when `js/sync.js` doesn't say what
script.json sets. An `at` belongs to its take, like a cut: after a re-take sync.mjs reports it unused — read the new
take and set it again. A changed cut needs `tts.mjs` then `sync.mjs` (the times stay: they are on the take's own clock).
Placeholder cues have no take; their `when()` keeps the estimate until they are recorded.

## 3. Gaps, chapter windows and re-timing

- Defaults (`new_project.mjs`, `tts.mjs`): `leadIn` 0.3 s, `gap` 0.25 s between lines, `tail` 1.5 s — the end hold,
  where the last frame holds after the last line (not dead air, §1).
- **The silence you hear is longer than the gap.** Between two lines it is the silence the earlier take keeps after its
  last word + `gapAfter` + the silence the next take keeps before its first word — the takes' edges as your cuts left
  them (§1). Don't add it up: read it with `wave.mjs`, counting the windows from the last voice of one line to the first
  voice of the next. (Takes cached before 2026-11-09 were cut by the old tts.mjs itself, to 0.04 s before the
  first sample above −38 dBFS and 0.12 s after the last.)
- `gapAfter` gives a scene change or a question a breath, longer than the beat inside a thought. Choose it by reading
  the result: with the edges around it the whole silence stays under 0.4 s (§1) unless something sounds in it.
- Changing gaps re-times without new API calls: edit script.json, run `tts.mjs` (unchanged takes come from the cache),
  then `sync.mjs`, `check.mjs`, and read the sound with `wave.mjs` (§1).
- Chapter transitions (long-form.md) start `lead` s before the chapter's first line but never more than 0.25 s before the
  previous line ends — the transition plays under the end of the last sentence, not in a silent gap.
- A hook that plays an output (an episode, a demo) starts it right after the line that introduces it
  ("먼저 보시죠" → the clip starts as that line's last word ends — read where with `wave.mjs`) and the next line starts as soon as the clip's sound ends.

## 4. Loudness

- Fish takes come out around −22 LUFS integrated; that is the reference (`MEDIA_SRC.level`). Footage is level-matched
  to it per clip (`lufs`), then shaped by its envelope (references/footage.md §7).

## 5. Reporting numbers

When you hand over audio, report **every** factor that changes it: early starts, level changes, re-takes and why. There is
never a speed factor to report — no TTS speed, no time-stretch, no playback rate on anything with sound. Say what the user should listen to first (the lines with the largest change, numbers and
names, tags).
