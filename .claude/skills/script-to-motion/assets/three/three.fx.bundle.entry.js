// Classic-script build of three.js r186 for SHADER FX on file:// playback (ES modules are blocked on file:// in Chrome).
// window.THREE = the WebGPU build (WebGPURenderer, RenderPipeline, node materials) + THREE.TSL + THREE.FX (post nodes)
// + GLTFLoader / RoomEnvironment. StageFX (stagefx.js) runs it on the WebGL2 backend — see references/shader-fx.md.
// Rebuild (three 0.186.1, esbuild API): bundle this file as format 'iife', minify, legalComments 'eof', target es2020,
// with a plugin that resolves ONLY the bare specifier "three" to "three/webgpu" (addons import "three"; an --alias
// would also rewrite "three/tsl"):  onResolve({ filter: /^three$/ }, a => build.resolve('three/webgpu', {...}))
// One three instance results (three.core + three.webgpu + three.tsl). See references/shader-fx.md §8.
// TSL `film` (noise on the built-in time clock) is deliberately left out: use the uTime grain recipe instead.
import * as THREE_NS from 'three/webgpu';
import * as TSL from 'three/tsl';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { bloom } from 'three/addons/tsl/display/BloomNode.js';
import { chromaticAberration } from 'three/addons/tsl/display/ChromaticAberrationNode.js';
import { rgbShift } from 'three/addons/tsl/display/RGBShiftNode.js';
import { gaussianBlur } from 'three/addons/tsl/display/GaussianBlurNode.js';
import { hashBlur } from 'three/addons/tsl/display/hashBlur.js';
import { radialBlur } from 'three/addons/tsl/display/radialBlur.js';
import { bilateralBlur } from 'three/addons/tsl/display/BilateralBlurNode.js';
import { dof } from 'three/addons/tsl/display/DepthOfFieldNode.js';
import { transition } from 'three/addons/tsl/display/TransitionNode.js';
import { lensflare } from 'three/addons/tsl/display/LensflareNode.js';
import { outline } from 'three/addons/tsl/display/OutlineNode.js';
import { godrays } from 'three/addons/tsl/display/GodraysNode.js';
import { depthAwareBlend } from 'three/addons/tsl/display/depthAwareBlend.js';
import { ssr } from 'three/addons/tsl/display/SSRNode.js';
import { ao } from 'three/addons/tsl/display/GTAONode.js';
import { sobel } from 'three/addons/tsl/display/SobelOperatorNode.js';
import { pixelationPass } from 'three/addons/tsl/display/PixelationPassNode.js';
import { dotScreen } from 'three/addons/tsl/display/DotScreenNode.js';
import { sepia } from 'three/addons/tsl/display/Sepia.js';
import { scanlines, vignette } from 'three/addons/tsl/display/CRT.js';
import { sharpen } from 'three/addons/tsl/display/SharpenNode.js';
import { fxaa } from 'three/addons/tsl/display/FXAANode.js';
import { smaa } from 'three/addons/tsl/display/SMAANode.js';
import { motionBlur } from 'three/addons/tsl/display/MotionBlur.js';
import { afterImage } from 'three/addons/tsl/display/AfterImageNode.js';
import { traa } from 'three/addons/tsl/display/TRAANode.js';

const FX = {
  bloom, chromaticAberration, rgbShift, gaussianBlur, hashBlur, radialBlur, bilateralBlur, dof, transition, lensflare,
  outline, godrays, depthAwareBlend, ssr, ao, sobel, pixelationPass, dotScreen, sepia, scanlines, vignette, sharpen,
  fxaa, smaa, motionBlur, afterImage, traa,
};
window.THREE = Object.assign({}, THREE_NS, { TSL, FX, GLTFLoader, RoomEnvironment, FX_BUILD: 'r186-webgpu-tsl' });
