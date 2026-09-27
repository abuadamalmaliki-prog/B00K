/*
 * look.js — the film look for "Found": footage that was filmed on a phone in 2016.
 *
 * Two stages:
 *   1. eng.js post: HDR scene → low-res bloom → ACES → split-tone grade → vignette → FXAA.
 *   2. phone pass: the in-phone processing that makes real POV footage read as real —
 *      oversharpening (unsharp mask), motion smear (the previous frame bleeds in, more
 *      when the camera moves), and sensor noise that grows in the shadows, with chroma.
 *
 *   import { createLook } from './look.js';
 *   const look = createLook(renderer, 1080, 1350);
 *   look.render(scene, camera, { grade: { street, store, field }, exposure, motion }, t);
 *
 * Smear depends on history, so frames must be rendered in order. When t jumps (the first
 * frame of a parallel chunk, a still), look.continuous(t) is false and the caller renders
 * the two frames before t first (index.html does this) so the trail is already there.
 */
import * as THREE from 'three';
import { createPost } from './eng.js';

// shadow / high are colour *shifts* that eng.js adds into the shadows and highlights.
const GRADES = {
  street: { shadow: [-0.10, 0.05, 0.35], high: [0.35, 0.12, -0.25], sat: 0.95, bloom: 0.22, vig: 0.30, grain: 0.004 },
  store: { shadow: [-0.12, 0.08, 0.14], high: [0.06, 0.10, 0.02], sat: 0.92, bloom: 0.14, vig: 0.26, grain: 0.004 },
  field: { shadow: [-0.05, 0.00, 0.10], high: [0.05, 0.03, -0.02], sat: 1.04, bloom: 0.08, vig: 0.16, grain: 0.003 },
};

const PHONE = /* glsl */`
  uniform sampler2D tCur, tHist; uniform vec2 tx; uniform float uSmear, uNoise, uSharp, uSeed, uHist;
  varying vec2 vUv;
  float hash(vec2 p){ vec3 p3 = fract(vec3(p.xyx)*0.1031); p3 += dot(p3,p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }
  void main(){
    vec3 c = texture2D(tCur, vUv).rgb;
    // Phone oversharpening: a 5-tap unsharp mask (the faint halos on edges are the point).
    vec3 n = texture2D(tCur, vUv + vec2(0., tx.y)).rgb + texture2D(tCur, vUv - vec2(0., tx.y)).rgb
           + texture2D(tCur, vUv + vec2(tx.x, 0.)).rgb + texture2D(tCur, vUv - vec2(tx.x, 0.)).rgb;
    c += (c - n * 0.25) * uSharp;
    // Motion smear: a slow sensor in low light keeps a trace of the last frame.
    if (uHist > 0.5) c = mix(c, texture2D(tHist, vUv).rgb, uSmear);
    // Sensor noise: luma + a little chroma, strongest in the shadows.
    float l = dot(c, vec3(.2126, .7152, .0722));
    float amt = uNoise * (0.3 + 0.7 * (1. - smoothstep(0.04, 0.7, l)));
    float g = hash(gl_FragCoord.xy + uSeed * 917.) + hash(gl_FragCoord.xy * 1.37 + uSeed * 331.) - 1.;
    vec3 ch = vec3(hash(gl_FragCoord.xy * 1.31 + uSeed * 211.), hash(gl_FragCoord.xy * 0.71 + uSeed * 503.),
                   hash(gl_FragCoord.xy * 1.93 + uSeed * 97.)) - 0.5;
    c += g * amt + ch * amt * 0.7;
    gl_FragColor = vec4(clamp(c, 0., 1.), 1.);
  }`;

const COPY = /* glsl */`uniform sampler2D tIn; varying vec2 vUv; void main(){ gl_FragColor = texture2D(tIn, vUv); }`;
const VERT = /* glsl */`varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

export function createLook(renderer, W, H, opts = {}) {
  const post = createPost(renderer, W, H, { msaa: 0, fxaa: true, ...opts });
  const PW = post.W, PH = post.H;
  const rt = () => new THREE.WebGLRenderTarget(PW, PH, { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false });
  const cur = rt();
  let hist = rt(), next = rt();

  const quadScene = new THREE.Scene(), quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2));
  quadScene.add(quad);
  const mat = (fs, uniforms) => new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: fs, uniforms, depthTest: false, depthWrite: false });
  const phone = mat(PHONE, {
    tCur: { value: cur.texture }, tHist: { value: null }, tx: { value: new THREE.Vector2(1 / PW, 1 / PH) },
    uSmear: { value: 0.2 }, uNoise: { value: 0.035 }, uSharp: { value: 0.55 }, uSeed: { value: 0 }, uHist: { value: 0 },
  });
  const copy = mat(COPY, { tIn: { value: null } });
  const pass = (m, target) => { quad.material = m; renderer.setRenderTarget(target); renderer.render(quadScene, quadCam); };

  const shadow = new THREE.Vector3(), high = new THREE.Vector3();
  function mix(weights, key) {
    let sum = 0, acc = null;
    for (const [name, w] of Object.entries(weights)) {
      if (!w || !GRADES[name]) continue;
      const v = GRADES[name][key];
      if (Array.isArray(v)) { acc = acc || [0, 0, 0]; v.forEach((x, i) => { acc[i] += x * w; }); } else acc = (acc ?? 0) + v * w;
      sum += w;
    }
    if (!sum) return mix({ store: 1 }, key);
    return Array.isArray(acc) ? acc.map((x) => x / sum) : acc / sum;
  }

  let lastT = null;
  const FRAME = 1 / 60;

  return {
    post,
    /** True when t follows the last rendered frame, so the smear trail is valid. */
    continuous(t) { return lastT !== null && Math.abs(t - lastT - FRAME) < 1e-4; },
    render(scene, camera, p = {}, t = 0) {
      const weights = p.grade || { store: 1 };
      shadow.fromArray(mix(weights, 'shadow'));
      high.fromArray(mix(weights, 'high'));
      for (const m of [post.out, post.outCA]) {
        m.uniforms.uShadowTint.value.copy(shadow);
        m.uniforms.uHighTint.value.copy(high);
      }
      post.render(scene, camera, {
        exp: p.exposure ?? 1, sat: mix(weights, 'sat'), bloom: p.bloom ?? mix(weights, 'bloom'),
        vig: mix(weights, 'vig'), grain: mix(weights, 'grain'), ca: p.ca ?? 0.5, fade: p.fade ?? 0,
        threshold: p.threshold ?? 0.9, target: cur,
      }, t);

      const u = phone.uniforms;
      u.uHist.value = this.continuous(t) ? 1 : 0;
      u.tHist.value = hist.texture;
      // More smear when the camera moves (motion: rad/s of head rotation + m/s of travel).
      u.uSmear.value = Math.min(0.3, 0.1 + 0.12 * (p.motion ?? 0));
      u.uNoise.value = p.noise ?? 0.035;
      u.uSeed.value = (Math.floor(t * 60) % 997) / 997;
      pass(phone, next);
      copy.uniforms.tIn.value = next.texture;
      pass(copy, null);
      [hist, next] = [next, hist];
      lastT = t;
    },
  };
}
