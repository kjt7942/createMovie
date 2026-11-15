/*
 * scenes.js — the video itself. Everything is placed on the master timeline `tl`
 * at times derived from narration cues, so re-generated narration re-times the visuals.
 *
 * Position shorthands: every cue id is a timeline label, plus `<id>_end`.
 *   tl.from('#s01 .title', { yPercent: 110, duration: 0.9, ease: 'expo.out' }, 'c01+=0.1');
 *   tl.to('#s01', { autoAlpha: 0, duration: 0.4 }, 'c02-=0.3');
 *   cue('c03').when('핵심 단어')   → the time that phrase is spoken (measured from the take once scripts/sync.mjs has run,
 *                                   estimated by character position until then)
 *
 * Rules: no Math.random / Date / setTimeout / standalone gsap.to() — see references/player-api.md.
 * Kits (optional, already linked in index.html): const K = FXKit.install(ctx) — impacts, counters, particles
 * (references/fx-kit.md); const TX = TypeFX.install(ctx) — expressive typography (references/type-fx.md).
 * Footage (references/footage.md): const M = MEDIA.install(ctx) — clips on the master clock (declared in js/media-src.js);
 * const R = RecKit.install(ctx) — a recording window, dim-the-rest highlights and pinned-up callouts (never zoom in).
 * Long videos (references/long-form.md): one builder per chapter in js/seg/<id>.js, called from here with its window.
 */
Video.define(({ tl, cue, cues, scene, onFrame, rand, fitCanvas, stage, W, H }) => {
  // Replace with the real storyboard implementation.
});
