/*
 * stagefx.js — shader FX inside the video player: three.js WebGPURenderer + TSL + RenderPipeline on the WebGL2
 * backend, rendered from the playhead t. Load after vendor/three/three.fx.bundle.min.js (enable_3d.mjs --fx).
 * The FX build replaces the classic one in a project (one window.THREE). See references/shader-fx.md.
 *
 *   Video.define(async ({ tl, cue, onFrame, W, H }) => {
 *     const fx = await StageFX.create(document.getElementById('gl'), { W, H, background: '#05070c', mrt: ['emissive'] });
 *     const { TSL, FX } = fx;                                    // TSL nodes, post-processing nodes
 *     const hero = new fx.THREE.Mesh(geo, new fx.THREE.MeshStandardNodeMaterial({ color: 0x3355ff }));
 *     hero.material.emissiveNode = TSL.color(0xff2d6f).mul(fx.uTime.mul(2).sin().mul(0.5).add(0.5));
 *     fx.scene.add(hero);
 *     const glow = { k: 0 };  tl.to(glow, { k: 1.2, duration: 0.6 }, cue('c03').when('핵심') - 0.1);
 *     const kBloom = TSL.uniform(0);
 *     fx.output = FX.smaa(fx.beauty.add(FX.bloom(fx.emissive, kBloom, 0.4, 0)));
 *     onFrame((t) => { kBloom.value = glow.k; hero.rotation.y = t * 0.6; fx.render(t); });
 *   });
 *
 * Rules (shader-fx.md §3): shaders read fx.uTime (= the playhead), never TSL `time`; no Math.random, no clocks,
 * no setAnimationLoop; class-C effects (afterImage, motionBlur, traa) are exact only in continuous playback.
 * URL: ?fxq=0.75 lowers the canvas resolution (slow machines while recording) · ?fxbackend=webgpu tries WebGPU (untested).
 */
(function () {
  'use strict';
  const T = window.THREE;
  if (!T || !T.TSL || !T.FX) { console.error('[stagefx] the FX build of THREE is missing — load vendor/three/three.fx.bundle.min.js first'); return; }
  const { TSL, FX } = T;
  const params = new URLSearchParams(location.search);

  async function create(canvas, o = {}) {
    // background: a colour → opaque canvas (needed by post effects). null → transparent canvas, but then the output
    // must stay the raw beauty pass: SMAA, bloom and the other nodes write alpha 1 / glow that can't blend over the DOM.
    const { W = 1920, H = 1080, fov = 35, near = 0.05, far = 200, background = '#000000', environment = true,
      exposure = 1.0, mrt = ['emissive'], maxPixelRatio = 2, quality = Number(params.get('fxq')) || 1,
      antialias = background === null ? 'none' : 'smaa' } = o;
    const renderer = new T.WebGPURenderer({ canvas, antialias: false, alpha: background === null,
      forceWebGL: params.get('fxbackend') !== 'webgpu' });
    renderer.toneMapping = T.ACESFilmicToneMapping;
    renderer.toneMappingExposure = exposure;
    renderer.shadowMap.enabled = !!o.shadows;
    await renderer.init();
    const scene = new T.Scene();
    if (background) scene.background = new T.Color(background);
    if (environment) {
      const pmrem = new T.PMREMGenerator(renderer);
      scene.environment = pmrem.fromScene(new T.RoomEnvironment(), 0.04).texture;
    }
    const camera = new T.PerspectiveCamera(fov, W / H, near, far);
    const uTime = TSL.uniform(0);

    // scene pass with the attachments the chosen effects need (each one costs bandwidth)
    const pass = TSL.pass(scene, camera);
    const att = { output: TSL.output };
    if (mrt.includes('emissive')) att.emissive = TSL.emissive;
    if (mrt.includes('normal')) att.normal = TSL.packNormalToRGB(TSL.normalView);
    if (mrt.includes('metalrough')) att.metalrough = TSL.vec2(TSL.metalness, TSL.roughness);
    if (mrt.includes('velocity')) att.velocity = TSL.velocity;
    if (Object.keys(att).length > 1) pass.setMRT(TSL.mrt(att));
    const beauty = pass.getTextureNode('output');
    const pipeline = new T.RenderPipeline(renderer);
    pipeline.outputNode = antialias === 'smaa' ? FX.smaa(beauty) : beauty;
    const computes = [];

    let ratio = 0;
    function fit() {
      const r = canvas.getBoundingClientRect(); // on-screen size of the (scaled) stage canvas
      const want = Math.min(maxPixelRatio, Math.max(0.5, (r.width / W || 1) * (window.devicePixelRatio || 1))) * quality;
      if (Math.abs(want - ratio) > 0.01) {
        ratio = want;
        renderer.setPixelRatio(ratio);
        renderer.setSize(W, H, false);
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
      }
    }
    fit();

    const api = {
      THREE: T, TSL, FX, renderer, scene, camera, uTime, pass, pipeline, beauty, fit,
      get backend() { return renderer.backend.isWebGPUBackend ? 'WebGPU' : 'WebGL2'; },
      /** the final node; wrap your chain in FX.smaa(...) yourself when you set it */
      get output() { return pipeline.outputNode; },
      set output(node) { pipeline.outputNode = node; pipeline.needsUpdate = true; },
      /** register a stateless compute (f(index, uTime)); it runs twice per frame — WebGL2 shows compute one frame late */
      addCompute(node) { computes.push(node); return node; },
      /** draw the scene at playhead t through the effect chain */
      render(t) {
        fit();
        uTime.value = t;
        for (const c of computes) { renderer.compute(c); renderer.compute(c); }
        pipeline.render();
      },
      /** a CanvasTexture with text (Korean OK). Async: the glyphs are loaded first — unicode-range web fonts only
       *  fetch the subsets a page has used, and a canvas never triggers that by itself. Returns { texture, aspect } */
      async textTexture(text, { font = '700 120px Pretendard', color = '#fff', pad = 24 } = {}) {
        await document.fonts.load(font, text);
        const c = document.createElement('canvas'), g = c.getContext('2d');
        g.font = font;
        const m = g.measureText(text), size = parseFloat(font.match(/(\d+(?:\.\d+)?)px/)?.[1] || 120);
        c.width = Math.ceil(m.width + pad * 2); c.height = Math.ceil(size * 1.4 + pad * 2);
        g.font = font; g.fillStyle = color; g.textBaseline = 'middle'; g.fillText(text, pad, c.height / 2);
        const texture = new T.CanvasTexture(c); texture.colorSpace = T.SRGBColorSpace; texture.anisotropy = 4;
        return { texture, aspect: c.width / c.height };
      },
    };
    if (att.emissive) api.emissive = pass.getTextureNode('emissive');
    if (att.velocity) api.velocity = pass.getTextureNode('velocity');
    if (att.metalrough) api.metalrough = pass.getTextureNode('metalrough');
    if (att.normal) api.normal = TSL.sample((uv) => TSL.unpackRGBToNormal(pass.getTextureNode('normal').sample(uv)));
    api.depth = pass.getTextureNode('depth');
    api.viewZ = pass.getViewZNode();
    return api;
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
    if (!b64) return Promise.reject(new Error(`[stagefx] GLB "${name}" is not embedded — run embed_glb.mjs (models/${name}.glb.js)`));
    return new Promise((resolve, reject) => new T.GLTFLoader().parse(b64ToArrayBuffer(b64), '', resolve, reject));
  }
  /** AnimationMixer with every clip playing; drive it with mixer.setTime(seconds) in onFrame */
  function mixer(gltf, root) {
    if (!gltf.animations || !gltf.animations.length) return null;
    const m = new T.AnimationMixer(root || gltf.scene);
    for (const clip of gltf.animations) m.clipAction(clip).play();
    return m;
  }
  const byName = (gltf, name) => gltf.scene.getObjectByName(name);

  window.StageFX = { create, loadGLB, mixer, byName };
  window.Stage3D = window.Stage3D || { create() { throw new Error('[stagefx] this project uses the FX build: use StageFX.create (async)'); }, loadGLB, mixer, byName };
})();
