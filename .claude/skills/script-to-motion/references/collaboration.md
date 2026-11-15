# Working with the user

How this user works, learned over the Kling video (dozens of review rounds). These rules come first; they decide how
every other reference is applied.

## The rules

1. **A question gets an answer, not a work session.** "속도가 1.15야??" is a question: answer it with the facts and stop.
   If something should change, say in one line what you would do and wait. Starting a long job instead ("너는 지금
   뭘하는거야? 나는 질문을 했는데 너는 답을 안하고 작업을 시작해?") overwrote a delivered file and broke a rule.
2. **Report numbers completely.** Every factor that changed the result (re-takes, offsets, level changes), every
   item that is not done. A partial number that sounds reassuring is a wrong report.
3. **A fix the user asks for: implement it, don't measure it.** "실측보다는 코드로 바로 구현한다. 확인은 사용자가 하고
   피드백을 줄것이다."
   - When the user asks for a change, don't shoot sheets or measure the result.
   - Write the change and run the cheap gates (`check.mjs`, `errscan.mjs`, plus reading `wave.mjs` / `check_fonts.mjs` when
     sound or text changed).
   - Say what changed and where (time + cue id), and stop.
   - Use layouts that align by construction (flex, shared variables) so you don't need to measure.

   **Work you do on your own is different.** This is the first build, an improvement you decide on, or a redesign you
   carry out. Look at it with `render.py --screenshot` and keep improving until it is right (references/visual-review.md).
   render.py sheets are the one way you look at the picture, including a clip the user gave you
   (`render.py <clip> --screenshot`). When the user asks you to look, or pastes the player's A command, run it and open
   the sheets. Name fixes by the frame · time · cue under each tile.
4. **The user makes the MP4.** Deliver the HTML project. The user screen-records it or runs the project's `render.py`
   (frame by frame, README 「MP4로 굽기」, references/render.md). Don't render MP4s yourself unless asked (contact sheets with
   `--screenshot` are how you look, rule 3), don't
   remind that a file is stale.
5. **Feedback arrives with its moment.** The S key copies `time / total [cue] line`; the user pastes it above a note.
   Find that moment, fix that, and answer with the same time and cue id.
6. **Re-create, don't decorate.** "표현력을 개선해줘" / "디자인을 더 멋지게" means rebuilding the scene or chapter from a
   concept (one object, numbers and words as its states, a match cut out), not adding effects to the old frame. If it's
   too big for one pass, say so and go chapter by chapter, reporting after each. Never shrink the scope silently.
7. **The user's words are final.** When they dictate a line ("…정도로 담백하게"), use it as given (spoken forms only in
   `say`). When they reject a phrase, find the same pattern everywhere.
8. **Reply in the user's language** — every line they read, including the short progress notes between steps.
9. **Plain, natural Korean**, no translationese, no inflated claims, no AI-style phrasing (anything that sounds
   polished but has to be decoded; say literally who did what — script-writing.md §5b) — in the video and in your
   replies; when a line sounds wrong ("말이 자연스럽지가
   못하지?"), rewrite it simply.
10. **Secrets**: the user's keys (Fish Audio) live in the skill's `.env`, which git ignores — the scripts read them
    from there. Never write a key into a tracked file (this repository is public), a project, output, a URL,
    a log or memory. Read-only use of the user's services unless they ask for a specific change.
11. **Outward-facing actions** (publishing, pushing, posting) only when asked, and say exactly what was published.
12. **Keep a progress file** (`진행상황.md`): decisions with their reasons, the file index, what's left. Log every
    change in one line.
13. **Finish everything; only the recording waits.** Given a script, a topic or a planning doc, do the whole job yourself:
    research, plan, script, scenes, verification and hand-off. Don't stop to show the lines or ask for approval along
    the way. Recording the user's voice is the one step you don't take on your own, because it is their voice and their
    credits. The finished video plays with silent placeholder narration. The user reviews it and decides whether to
    record (`tts.mjs --approved`).
14. **Rich expression by default**: every beat shows its content as picture, diagram, motion or acting type; how each
    effect is built comes from the skill's technique library (references/cokacmotion.md — technique only, never a demo's
    scene). Rich in ideas, calm in effects.

## The user's taste (defaults unless they say otherwise)

- **Never PPT or document design (absolute)**: no boxes, cards, bullet lists or tables holding text; the content
  itself is the picture on the open stage (SKILL.md → No slides, no boxes).
- **A script is speech for a listener who hears it once**: understood on first hearing; accuracy before convenience
  (exact names, every technical term explained); spoken, not written Korean (endings about 75 % ~니다 and 25 % ~요,
  filler words only where they do a job, never by quota; never 솔직히) — references/script-writing.md. The user's own
  script is used exactly as given, with no rewrites offered.
- No zoom into screen recordings — dim the rest, pin a callout (references/footage.md).
- No dead air ≥ 0.4 s (references/sound.md).
- Calm effects: no expanding rings or blinking circles, soft flashes, **no punch zoom**, no horizon line across the
  frame. Depth from light and material, not from noise. Grain and the rest of the finish are chosen per film by what
  suits it (references/cinematic-look.md §3).
- Handwriting: **East Sea Dokdo** (Google Fonts, OFL) via `--hand`; draw symbols it lacks as SVG.
- Numbers in Pretendard with tabular digits; D2Coding only for code (its slashed zero made prices read like code), never
  for Hangul.
- Analog touches over flat UI: a price on a taped memo sheet, a callout pinned up slightly crooked, pen loops and lines.
- Captions on by default, Noto Sans KR Bold, one line.
