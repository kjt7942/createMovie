/*
 * stage3d.js — three.js inside the video player: a WebGL layer that renders the playhead t.
 * Load after vendor/three/three.bundle.min.js (enable_3d.mjs wires both). In js/scenes.js:
 *
 *   Video.define(async ({ tl, cue, onFrame, W, H }) => {
 *     const s3d = Stage3D.create(document.getElementById('gl'), { W, H, fov: 35 });
 *     const gltf = await Stage3D.loadGLB('mug');          // models/mug.glb.js (embed_glb.mjs)
 *     s3d.scene.add(gltf.scene);
 *     const mixer = Stage3D.mixer(gltf);                  // glTF animations, seekable
 *     const cam = { angle: 0 };
 *     tl.to(cam, { angle: 1.2, duration: 4, ease: 'power2.inOut' }, 'c02');
 *     onFrame((t) => {
 *       if (mixer) mixer.setTime(t);                      // never mixer.update(delta)
 *       s3d.camera.position.set(Math.sin(cam.angle) * 3, 1.2, Math.cos(cam.angle) * 3);
 *       s3d.camera.lookAt(0, 0.5, 0);
 *       s3d.render();
 *     });
 *   });
 *
 * Everything is a function of t: no THREE.Clock, no setAnimationLoop, no physics stepping.
 * The canvas renders at the stage's on-screen resolution (crisp in fullscreen/4K).
 */
(function () {
  'use strict';
  const T = window.THREE;
  if (!T) { console.error('[stage3d] THREE is missing — load vendor/three/three.bundle.min.js first'); return; }

  function create(canvas, o = {}) {
    const { W = 1920, H = 1080, fov = 35, near = 0.05, far = 200, background = null, environment = true,
      exposure = 1.0, outline = false, outlineThickness = 0.004 } = o;
    const renderer = new T.WebGLRenderer({ canvas, antialias: true, alpha: background === null });
    renderer.outputColorSpace = T.SRGBColorSpace;
    renderer.toneMapping = T.ACESFilmicToneMapping;
    renderer.toneMappingExposure = exposure;
    const scene = new T.Scene();
    if (background) scene.background = new T.Color(background);
    if (environment) {
      const pmrem = new T.PMREMGenerator(renderer);
      scene.environment = pmrem.fromScene(new T.RoomEnvironment(), 0.04).texture;
    }
    const camera = new T.PerspectiveCamera(fov, W / H, near, far);
    const effect = outline ? new T.OutlineEffect(renderer, { defaultThickness: outlineThickness }) : null;
    let ratio = 0;
    function fit() {
      const r = canvas.getBoundingClientRect(); // on-screen size of the (scaled) stage canvas
      const want = Math.min(3, Math.max(1, (r.width / W || 1) * (window.devicePixelRatio || 1)));
      if (Math.abs(want - ratio) > 0.01) {
        ratio = want;
        renderer.setPixelRatio(ratio);
        renderer.setSize(W, H, false);
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
      }
    }
    fit();
    return {
      THREE: T, renderer, scene, camera, fit,
      render() { fit(); (effect || renderer).render(scene, camera); },
    };
  }

  function b64ToArrayBuffer(b64) {
    const bin = atob(b64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return u8.buffer;
  }

  /** a GLB embedded by embed_glb.mjs (window.GLB_ASSETS[name]) — works from file:// */
  function loadGLB(name) {
    const b64 = (window.GLB_ASSETS || {})[name];
    if (!b64) return Promise.reject(new Error(`[stage3d] GLB "${name}" is not embedded — run embed_glb.mjs (models/${name}.glb.js)`));
    return new Promise((resolve, reject) => new T.GLTFLoader().parse(b64ToArrayBuffer(b64), '', resolve, reject));
  }

  /** AnimationMixer with every clip playing; drive it with mixer.setTime(seconds) in onFrame */
  function mixer(gltf, root) {
    if (!gltf.animations || !gltf.animations.length) return null;
    const m = new T.AnimationMixer(root || gltf.scene);
    for (const clip of gltf.animations) m.clipAction(clip).play();
    return m;
  }

  /** find a node by name (glTF node names = Blender object names) */
  const byName = (gltf, name) => gltf.scene.getObjectByName(name);

  window.Stage3D = { create, loadGLB, mixer, byName };
})();
