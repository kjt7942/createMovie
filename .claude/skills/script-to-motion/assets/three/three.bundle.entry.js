// Classic-script build of three.js for file:// playback (ES modules are blocked on file:// in Chrome).
import * as THREE_NS from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { OutlineEffect } from 'three/examples/jsm/effects/OutlineEffect.js';
window.THREE = Object.assign({}, THREE_NS, { GLTFLoader, RoomEnvironment, OutlineEffect });
