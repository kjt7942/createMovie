/* media-src.js — the footage this video shows (js/media.js, references/footage.md). Only files the user provided:
   each one is also listed in provenance.json. Leave `clips` empty when the video shows no footage. */
window.MEDIA_SRC = {
  level: -22,   // the narration's integrated loudness (LUFS); clips with `lufs` are level-matched to it
  clips: {
    // rec_demo: { file: 'assets/user/vid/rec_demo.mp4', master: 'media/master/rec_demo.mp4', w: 3840, h: 1750, dur: 42.0 },
  },
};
