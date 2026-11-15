/*
 * media.js — footage on the master clock: screen recordings, generated clips, any video the user provided
 * (references/footage.md). Still images are plain <img>.
 *
 * The clips are declared in js/media-src.js (the project's file, loaded before this one):
 *   window.MEDIA_SRC = { level: -22, clips: {
 *     rec_demo: { file: 'assets/user/vid/rec_demo.mp4', master: 'media/master/rec_demo.mp4', w: 3840, h: 1750 },
 *     clip_a:   { file: 'assets/user/vid/clip_a.mp4', master: 'media/master/clip_a.mp4', w: 1080, h: 1920, dur: 30.04, lufs: -12.5 },
 *   } };
 *   file    the playback copy the browser plays (light: H.264, ~8 Mbit/s, faststart)
 *   master  the full-quality source the stills are cut from (may live outside the project; a symlink is fine)
 *   w, h    the master's pixel size (crops and spot rects are in these pixels) · dur its length (s)
 *   lufs    the clip's own integrated loudness (ffmpeg ebur128): every clip with sound is level-matched to `level`
 *           (the narration's loudness) before its volume envelope applies
 *
 * Two ways to show a clip, same placement, same timing:
 *   live    (a normal browser)  <video> elements follow the player clock: playing while the video plays, seeked when
 *           paused/scrubbed. Clips with `audio` play their own sound with the volume envelope below. At a review speed
 *           (the player's Shift+> / Shift+<) they play at that speed too; recordings (R resets it) and renders are 1×.
 *   stills  (headless review: snapshots, ?stills, ?render)  pre-extracted JPEG frames — scripts/stills.mjs writes them to
 *           <frames>/<placement id>/00001.jpg… at <mfps> (defaults: media/stills at 10 fps). Headless Chromium has no
 *           H.264 decoder, so this is how the review tools see footage.
 * Every placement is a pure function of t: nothing is accumulated, so seeking anywhere shows the same frame.
 *
 *   const M = MEDIA.install(ctx);
 *   const box = M.clip(parentEl, 'clip_a', { x, y, w, h, start, dur, in: 0, rate: 1, crop: [sx, sy, sw, sh],
 *                                            fit: 'cover', zoom: 1, show: [t0, t1], audio: true, vol: 0.9 | [[lt, v], …] })
 *   M.duck(start, dur, hi, lo) → envelope [[lt, v], …]: lo while the narration speaks, hi in its gaps
 *   window.__media.list() / .audio() / .settle()   for scripts/stills.mjs, wave.mjs and dub.mjs
 */
(function () {
  'use strict';
  const Q = new URLSearchParams(location.search);
  const RENDER = Q.has('render');
  const STILLS = RENDER || Q.has('stills') || navigator.webdriver === true;
  const FRAMES = (Q.get('frames') || 'media/stills').replace(/\/$/, '');
  const MFPS = +(Q.get('mfps') || 10);
  if (RENDER) document.documentElement.classList.add('render');

  const CFG = window.MEDIA_SRC || {};
  const LEVEL = CFG.level != null ? CFG.level : -22;
  const SRC = CFG.clips || {};

  const LIST = [];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const r3 = (v) => Math.round(v * 1000) / 1000;
  const gainOf = (key) => (SRC[key].lufs == null ? 1 : Math.pow(10, (LEVEL - SRC[key].lufs) / 20));
  let muted = false;

  function volAt(v, lt) {
    if (typeof v === 'number') return v;
    if (lt <= v[0][0]) return v[0][1];
    for (let i = 1; i < v.length; i++) if (lt <= v[i][0]) {
      const [t0, a] = v[i - 1], [t1, b] = v[i];
      return a + (b - a) * (lt - t0) / Math.max(1e-6, t1 - t0);
    }
    return v[v.length - 1][1];
  }

  function install(ctx) {
    const { onFrame, data } = ctx;
    const cues = data.cues || [];
    // a frame-by-frame render (?render) waits while a visible clip's frame image is still loading or decoding
    if (ctx.busy) ctx.busy(() => STILLS && LIST.some((m) => m.vis && m.el.src && !m.el.complete));

    function clip(parent, key, o) {
      const s = SRC[key];
      if (!s) throw new Error('[media] unknown clip ' + key);
      const crop = o.crop || [0, 0, s.w, s.h];
      const w = o.w, h = o.h, rate = o.rate || 1, inn = o.in || 0;
      // a clip's sound is never slowed down or sped up: a clip with audio plays at rate 1 (a faster or slower clip is silent)
      if (o.audio && rate !== 1) throw new Error(`[media] clip ${key}: audio: true needs rate 1 (got ${rate}) — sound is never slowed down or sped up`);
      const dur = o.dur != null ? o.dur : ((s.dur || 0) - inn) / rate;
      const box = document.createElement('div');
      box.className = 'media' + (o.cls ? ' ' + o.cls : '');
      Object.assign(box.style, { position: 'absolute', left: (o.x || 0) + 'px', top: (o.y || 0) + 'px', width: w + 'px', height: h + 'px', overflow: 'hidden', visibility: 'hidden' });
      if (o.radius) box.style.borderRadius = o.radius + 'px';
      parent.appendChild(box);
      // cover (default) or contain-fit the crop region into the box
      const sc = (o.fit === 'contain' ? Math.min : Math.max)(w / crop[2], h / crop[3]);
      const ox = (w - crop[2] * sc) / 2, oy = (h - crop[3] * sc) / 2;
      // still resolution: enough source pixels for the box at its biggest on screen (camera zoom), never more than the crop
      const res = Math.round(Math.min(crop[2], Math.max(64, crop[2] * sc * (o.zoom || 1))));
      const m = { key, start: o.start, dur, in: inn, rate, crop, res, box, w, h, audio: !!o.audio, vol: o.vol == null ? 1 : o.vol,
        show: o.show || [o.start, o.start + dur], vis: null, el: null, f: 0, loaded: false };
      m.n = Math.max(1, Math.ceil(dur * MFPS - 1e-6));
      m.id = [key, r3(inn), r3(rate), r3(dur), crop.join('_'), res].join('-').replace(/\./g, 'p');
      if (STILLS) {
        const im = document.createElement('img');
        im.decoding = 'sync';
        Object.assign(im.style, { position: 'absolute', width: crop[2] * sc + 'px', height: crop[3] * sc + 'px', left: ox + 'px', top: oy + 'px' });
        box.appendChild(im);
        m.el = im;
      } else {
        const v = document.createElement('video');
        v.muted = true; v.playsInline = true; v.preload = 'none'; v.preservesPitch = true;
        // a seek while the clip was still unloaded (readyState 0) could not be applied: show the right frame once it can
        v.addEventListener('loadedmetadata', () => { if (m.target != null && Math.abs(v.currentTime - m.target) > 0.04) v.currentTime = m.target; });
        Object.assign(v.style, { position: 'absolute', width: s.w * sc + 'px', height: s.h * sc + 'px', left: ox - crop[0] * sc + 'px', top: oy - crop[1] * sc + 'px' });
        box.appendChild(v);
        m.el = v;
      }
      LIST.push(m);
      return box;
    }

    // envelope for a clip that plays under narration: lo while a cue is spoken (with short ramps), hi in the gaps
    function duck(start, dur, hi = 0.85, lo = 0.18, ramp = 0.18) {
      const pts = [[0, hi]];
      for (const c of cues) {
        const a = c.start - start - ramp, b = c.end - start + ramp;
        if (b < 0 || a > dur) continue;
        pts.push([Math.max(0, a), hi], [Math.max(0, a + ramp), lo], [Math.min(dur, b - ramp), lo], [Math.min(dur, b), hi]);
      }
      pts.push([dur, hi]);
      pts.sort((p, q) => p[0] - q[0]);
      return pts;
    }

    onFrame((t) => {
      const playing = document.body.classList.contains('vp-playing');
      // the player's review speed (Shift+> / Shift+<): clips being watched follow it instead of being hard-seeked to keep up
      const speed = (window.Video && window.Video.rate) || 1;
      for (const m of LIST) {
        const lt = t - m.start;
        const vis = t >= m.show[0] && t < m.show[1];
        if (m.vis !== vis) { m.box.style.visibility = vis ? 'inherit' : 'hidden'; m.vis = vis; }
        if (STILLS) {
          if (!vis) continue;
          const f = clamp(Math.floor(clamp(lt, 0, m.dur) * MFPS + 1e-6) + 1, 1, m.n);
          if (m.f !== f) { m.f = f; m.el.src = `${FRAMES}/${m.id}/${String(f).padStart(5, '0')}.jpg`; }
          continue;
        }
        const v = m.el, s = SRC[m.key];
        const near = t > m.show[0] - 3 && t < m.show[1] + 1;
        if (near && !m.loaded) { v.src = s.file; v.preload = 'auto'; m.loaded = true; }
        if (!near) { if (m.loaded) { v.pause(); v.removeAttribute('src'); v.load(); m.loaded = false; } continue; }
        const active = lt >= 0 && lt < m.dur;
        const target = m.in + clamp(lt, 0, m.dur) * m.rate;
        m.target = target;
        const vr = m.rate * speed;
        const native = vr >= 0.0625 && vr <= 16;   // browsers play only this range; slower clips are scrubbed
        if (active && playing && vis && native) {
          if (v.playbackRate !== vr) v.playbackRate = vr;
          if (v.paused) v.play().catch(() => {});
          if (v.readyState > 0 && Math.abs(v.currentTime - target) > 0.25 * Math.max(1, speed)) v.currentTime = target;
        } else {
          if (!v.paused) v.pause();
          if (v.readyState > 0 && Math.abs(v.currentTime - target) > 0.04) v.currentTime = target;
        }
        if (m.audio) {
          v.muted = muted || !active || !playing;
          v.volume = clamp(volAt(m.vol, clamp(lt, 0, m.dur)) * gainOf(m.key), 0, 1);
        }
      }
    });

    return { clip, duck, SRC, STILLS };
  }

  window.MEDIA = { install, SRC, STILLS, setMuted: (b) => { muted = b; } };
  window.__media = {
    mfps: MFPS,
    list: () => LIST.map((m) => ({ id: m.id, key: m.key, master: SRC[m.key].master, in: m.in, rate: m.rate, dur: m.dur, crop: m.crop, res: m.res, start: m.start })),
    audio: () => LIST.filter((m) => m.audio).map((m) => ({ key: m.key, file: SRC[m.key].master, in: m.in, rate: m.rate, start: m.start, dur: m.dur,
      vol: typeof m.vol === 'number' ? m.vol * gainOf(m.key) : m.vol.map((p) => [p[0], p[1] * gainOf(m.key)]) })),
    // resolves when every visible still has decoded (render / snapshots wait on it)
    settle: () => Promise.all(LIST.filter((m) => m.vis && STILLS && m.el.src).map((m) => (m.el.complete ? Promise.resolve() : m.el.decode().catch(() => {})))),
  };
})();
