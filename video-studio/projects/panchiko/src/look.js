/*
 * look.js — the film look for "Found": HDR scene → low-res bloom → ACES filmic →
 * split-tone grade → vignette, subtle grain, FXAA (the pipeline lives in eng.js).
 *
 *   import { createLook } from './look.js';
 *   const look = createLook(renderer, 1080, 1350);
 *   look.render(scene, camera, { grade: { street, store, field }, exposure }, t);
 *
 * grade weights (0..1, they blend) come from camera.js gradeAt(t) plus the field
 * weight once the film reaches the landscape. Grades follow the cinematographer:
 *   street — orange sodium lamps over wet blue-black; store — cold green-cyan
 *   fluorescent; field — clean daylight, the only neutral scene in the film.
 */
import * as THREE from 'three';
import { createPost } from './eng.js';

// shadow / high are colour *shifts* that eng.js adds into the shadows and highlights.
const GRADES = {
  street: { shadow: [-0.10, 0.05, 0.35], high: [0.35, 0.12, -0.25], sat: 0.92, bloom: 0.16, vig: 0.42, grain: 0.030 },
  store: { shadow: [-0.15, 0.10, 0.20], high: [-0.05, 0.12, 0.05], sat: 0.90, bloom: 0.10, vig: 0.32, grain: 0.024 },
  field: { shadow: [-0.05, 0.00, 0.10], high: [0.05, 0.03, -0.02], sat: 1.04, bloom: 0.06, vig: 0.18, grain: 0.016 },
};

export function createLook(renderer, W, H, opts = {}) {
  const post = createPost(renderer, W, H, { msaa: 0, fxaa: true, ...opts });
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

  return {
    post,
    render(scene, camera, p = {}, t = 0) {
      const weights = p.grade || { store: 1 };
      shadow.fromArray(mix(weights, 'shadow'));
      high.fromArray(mix(weights, 'high'));
      for (const m of [post.out, post.outCA]) {
        m.uniforms.uShadowTint.value.copy(shadow);
        m.uniforms.uHighTint.value.copy(high);
      }
      post.render(scene, camera, {
        exp: p.exposure ?? 1,
        sat: mix(weights, 'sat'),
        bloom: p.bloom ?? mix(weights, 'bloom'),
        vig: mix(weights, 'vig'),
        grain: mix(weights, 'grain'),
        ca: p.ca ?? 0.35,
        fade: p.fade ?? 0,
        threshold: p.threshold ?? 1.0,
      }, t);
    },
  };
}
