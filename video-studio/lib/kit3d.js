/*
 * kit3d.js — "our own Blender": abstract Y2K chrome / liquid-glass 3D for video-studio.
 *
 * Original abstract geometry only (ribbons, tubes, rings, crystal shards, clouds, glass
 * panes). Every frame is a pure function of the time you pass in: no clocks, no
 * Math.random() (layouts come from a seeded PRNG), so renders are exact and repeatable.
 *
 * ── Usage (a composition page with the usual import map for 'three' + 'three/addons/') ──
 *
 *   import * as THREE from 'three';
 *   import { createKit } from '../../lib/kit3d.js';
 *   const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
 *   renderer.setPixelRatio(devicePixelRatio); renderer.setSize(1080, 1350);
 *   const kit = createKit(renderer, { width: 1080, height: 1350 });
 *   Studio.onFrame((t) => {
 *     kit.scenes.ribbons.update(t - seg.start, { tone: 'pearl' });
 *     kit.scenes.ribbons.render();             // → canvas; or .render(rt) → your RenderTarget
 *   });
 *
 * ── createKit(renderer, { width, height, msaa = 4, seed = 11 }) → kit ──────────────────
 *   kit.scenes.{ribbons, kaleido, shards, sky, orbit} — each one has
 *     .update(t, params)        state for time t (seconds, any origin; pass segment-local
 *                               time for repeatable starts, or one continuous clock across
 *                               adjacent segments of the same scene for seamless motion)
 *     .render(target = null, post = {})
 *                               scene → HDR target → post → target (null = canvas). Output is
 *                               display-referred sRGB (what you see); an RGBA8 RT works.
 *     .renderHDR(rt)            advanced: raw linear HDR scene into rt, no post.
 *     .defaults                 default params (incl. .post)
 *   kit.post.render(hdrTexture, target, postParams, t)
 *   kit.texture(el)             cached sRGB THREE.Texture for <img>/<video>/<canvas>, re-uploaded
 *                               on each call (e.g. kit.texture(Studio.footage('s12_0')))
 *   kit.envMap(tone)            PMREM of the same procedural studio (for your own
 *                               MeshStandard/Physical materials)
 *   kit.tones                   ['pearl', 'silver', 'electric', 'prism'] (+ 'sky')
 *   kit.hdr                     the shared HalfFloat MSAA target scenes draw into
 *
 * ── Common params (every scene) ─────────────────────────────────────────────────────────
 *   tone     'pearl'    white/pearl stage, light-blue & lilac glass, silver
 *            'silver'   monochrome chrome on black
 *            'electric' #1437FF electric blue on black, white-hot highlights
 *            'prism'    blown-out white, rainbow dispersion edges
 *   energy   0..1 beat envelope → brightness / ribbon swell only (never shakes or zooms)
 *   post     { bloom, threshold, disp (spectral dispersion), grain, vignette, exposure,
 *              flash (0..1 to white), fade (0..1 to black) } — grain/vignette default 0
 *
 * ── Footage inputs (params.footage, params.behind, kaleido params.source) ────────────────
 *   An element (<img> from Studio.footage(name), <video>, <canvas>), a THREE.Texture, or
 *   { src, rect, encoded, fx }:
 *     rect     [x, y, w, h] crop in flipY UV space (y = 0 is the image BOTTOM) — the v1 /
 *              CONTEXT convention: church → [0, .13, 1, .73], fireworks → [0, .1, 1, .9]
 *     encoded  true if the texture holds display sRGB values in a linear texture (e.g. an
 *              RT your 2D compositor drew the outgoing frame into). Elements: automatic.
 *     fx       horizontal focus 0..1 where a scene must crop to fill (default .5)
 *   Footage goes through the HDR pipeline colour-exact (inverse tone curve): an untouched
 *   footage pixel comes out equal to the source pixel.
 *
 * ── Scene params ─────────────────────────────────────────────────────────────────────────
 *   ribbons  { seed: 1, speed: 1, glass: .45 (share of glass ribbons), count: 1 (share
 *            shown), tubes: 1, unfurl: 0 (s; >0 = ribbons grow in from t = 0), dist: 8.5
 *            (camera distance; ~3 puts the camera inside the swirl), orbit: .12 (rad/s) }
 *   kaleido  { source: 'chrome' | footage, folds: 6, mode: 'radial' | 'kifs' (fractal,
 *            tiled mandalas), rotation: 0 (rad), spin: .15 (rad/s), zoom: 1, seed: 3, speed: 1 }
 *   shards   { mode: 'burst' | 'shatter', hits: [.5] (burst times, same clock as t), count: 1,
 *            // shatter — the given frame breaks into glass tiles that fly at the camera:
 *            footage (required), hit: .4 (impact time), duration: 1.1, impact: [.5, .5]
 *            (screen uv, y up), behind: 'burst' (default: a crystal burst in the same tone
 *            erupts behind the tiles) | footage | null (→ behindColor [r,g,b] 0..1) }
 *   sky      { footage (optional glass pane, drifts slowly, stays ≥ 85 % of frame width),
 *            pane: .88 (pane width / frame width), object: 'rings' | 'ribbon' | 'none'
 *            (a chrome object drifting across during `cross`), cross: [0, 5] (s),
 *            cover: .5 (clouds), wind: 1, pitch: .3 (rad, camera looks up) }
 *   orbit    with footage: a floating glass/chrome slab, camera orbiting slowly —
 *              { footage, fill: .9 (slab width / frame width, ≥ .8 while orbiting),
 *                yaw: .2 (rad), period: 9 (s), reflection: .5, ribbons: .6, sharpen: .35,
 *                gloss: 1, sweep: 1 }
 *            without footage: thin arcs & rings orbiting like an armillary sphere —
 *              { seed: 2, speed: 1, count: 1 }
 *
 * Performance (SwiftShader, 4 cores): no transmission — glass is faked with an analytic
 * studio environment (reflection + refraction + thin film); targets are shared; bloom
 * runs at 1/4..1/32 res; clouds at 1/2 res.
 */
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

const TAU = Math.PI * 2;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, x) => a + (b - a) * x;
const smooth = (a, b, x) => { const k = clamp((x - a) / (b - a), 0, 1); return k * k * (3 - 2 * k); };

/** Seeded PRNG — the same generator as Studio.random. */
export function rng(seed = 1) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

// ════════════════════════════════════════════════════════════════════════════════════════
// GLSL building blocks
// ════════════════════════════════════════════════════════════════════════════════════════

const NB = 6; // softboxes in the analytic studio

/* Analytic studio environment: gradient sky, sharp horizon line, rounded softboxes.
 * Sharper and cheaper than a cube map on a CPU rasteriser, and animatable (eRot). */
const ENV_GLSL = /* glsl */`
  uniform vec3 eTop, eMid, eHor, eGnd, eNadir;
  uniform float eHorGlow, eGain;
  uniform mat3 eRot;
  uniform vec3 eBoxDir[${NB}], eBoxRight[${NB}], eBoxUp[${NB}], eBoxCol[${NB}];
  uniform vec4 eBoxP[${NB}];   // half width, half height (tan units), intensity, softness
  vec3 envMap(vec3 d, float rough) {
    d = eRot * d;
    float y = d.y;
    float hw = 0.006 + rough * 0.25;
    vec3 sky = mix(eHor, eMid, smoothstep(0.0, 0.28, y));
    sky = mix(sky, eTop, smoothstep(0.28, 0.95, y));
    vec3 gnd = mix(eGnd, eNadir, smoothstep(0.0, -0.7, y));
    vec3 c = mix(gnd, sky, smoothstep(-hw, hw, y));
    c += eHor * eHorGlow * exp(-abs(y) * 60.0 / (1.0 + rough * 30.0));
    for (int i = 0; i < ${NB}; i++) {
      float t = max(dot(d, eBoxDir[i]), 1e-3);
      vec2 q = vec2(dot(d, eBoxRight[i]), dot(d, eBoxUp[i])) / t;
      vec2 e = abs(q) - eBoxP[i].xy;
      float sd = length(max(e, 0.0)) + min(max(e.x, e.y), 0.0);
      float s = eBoxP[i].w + rough * 0.6;
      c += eBoxCol[i] * (eBoxP[i].z * (1.0 - smoothstep(-s, s, sd)) * step(0.0, dot(d, eBoxDir[i])));
    }
    return c * eGain;
  }
  vec3 film(float x) { return 0.5 + 0.5 * cos(6.2831853 * (x + vec3(0.0, 0.33, 0.67))); }
`;

const COLOR_GLSL = /* glsl */`
  vec3 fromSRGB(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c)); }
  vec3 toSRGB(vec3 c) { c = clamp(c, 0.0, 1.0); return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
  // Post's tone curve is identity below 0.8 with a soft shoulder above; invTone() undoes it,
  // so footage sent through the HDR pipeline comes out exactly as the source.
  vec3 invTone(vec3 y) {
    y = clamp(y, 0.0, 0.996);
    vec3 x = 0.8 - 0.2 * log(1.0 - (y - 0.8) / 0.2);
    return mix(y, x, step(0.8, y));
  }
`;

/* Footage sampling with crop rect, optional sRGB decode and a 5-tap sharpen. */
const FOOTAGE_GLSL = /* glsl */`
  uniform sampler2D tFoot; uniform vec4 fRect; uniform vec2 fTexel; uniform float fEncoded, fSharp;
  vec3 footRaw(vec2 uv) {
    vec3 c = texture2D(tFoot, uv).rgb;
    return fEncoded > 0.5 ? fromSRGB(c) : c;
  }
  vec3 footage(vec2 uv01) {
    vec2 uv = fRect.xy + clamp(uv01, 0.0, 1.0) * fRect.zw;
    vec3 c = footRaw(uv);
    if (fSharp > 0.0) {
      vec3 n = footRaw(uv + vec2(fTexel.x, 0.0)) + footRaw(uv - vec2(fTexel.x, 0.0))
             + footRaw(uv + vec2(0.0, fTexel.y)) + footRaw(uv - vec2(0.0, fTexel.y));
      c = max(c + fSharp * (c - 0.25 * n), 0.0);
    }
    return invTone(c);
  }
`;

const FS_VERT = /* glsl */`
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

// Ribbon / tube / ring swept along an animated curve — geometry is computed on the GPU.
const RIBBON_VERT = /* glsl */`
  attribute vec3 aProf;          // stadium cross-section: side (-1/1), cap normal x, y
  uniform float uTime, uSwell, uGrow, uCamber;
  uniform vec4 uA;   // radius, arc (rad), theta0, flow (rad/s)
  uniform vec4 uB;   // wobble amp, wobble freq, height amp, height freq
  uniform vec4 uC;   // width, thickness ratio, twist turns, twist speed
  uniform vec4 uD;   // rise, phase1, phase2, taper (0 ring … 1 tapered ribbon)
  uniform mat3 uRot; uniform vec3 uOff;
  centroid varying vec3 vW; centroid varying vec3 vN; varying vec2 vUv; centroid varying float vEdge;
  vec3 curve(float s) {
    float th = uA.z + (s - 0.5) * uA.y * uGrow + uTime * uA.w;
    float r = uA.x * (1.0 + uB.x * sin(uB.y * th + uD.y));
    float y = uB.z * sin(uB.w * th + uD.z) + (s - 0.5) * uD.x * uGrow;
    return uRot * vec3(r * cos(th), y, r * sin(th)) + uOff;
  }
  void main() {
    float s = uv.x;
    vec3 P = curve(s);
    vec3 T = normalize(curve(s + 0.0015) - curve(s - 0.0015));
    vec3 B = normalize(cross(T, uRot[1]));
    vec3 N = cross(B, T);
    float psi = uC.z * 6.2831853 * s + uC.w * uTime + uD.y;
    vec3 Wd = cos(psi) * B + sin(psi) * N;
    vec3 Nr = cross(T, Wd);
    float taper = mix(1.0, pow(max(sin(3.14159265 * s), 0.0), 0.7), uD.w);
    float a = 0.5 * uC.x * taper * uSwell * min(1.0, uGrow * 1.4);
    float b = a * uC.y;
    vec3 off = Wd * (aProf.x * (a - b) + aProf.y * b) + Nr * (aProf.z * b);
    // camber: the flat faces bow outward, so a highlight line runs along each ribbon
    vN = normalize(Wd * (aProf.y + aProf.x * abs(aProf.z) * uCamber) + Nr * aProf.z);
    vEdge = abs(aProf.y);
    vW = P + off;
    vUv = uv;
    gl_Position = projectionMatrix * viewMatrix * vec4(vW, 1.0);
  }
`;

const MESH_VERT = /* glsl */`
  centroid varying vec3 vW; centroid varying vec3 vN; varying vec2 vUv; centroid varying float vEdge;
  void main() {
    vec4 w = modelMatrix * vec4(position, 1.0);
    vW = w.xyz; vN = normalize(mat3(modelMatrix) * normal); vUv = uv; vEdge = 0.5;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;

const CHROME_FRAG = /* glsl */`
  ${ENV_GLSL}
  uniform vec3 uTint; uniform float uRough, uFilm, uBright, uFilmShift, uPaint;
  centroid varying vec3 vW; centroid varying vec3 vN; varying vec2 vUv; centroid varying float vEdge;
  void main() {
    vec3 n = normalize(vN);
    vec3 v = normalize(cameraPosition - vW);
    float ndv = clamp(dot(n, v), 0.0, 1.0);
    vec3 r = reflect(-v, n);
    float rough = max(uRough, clamp(length(fwidth(vN)) * 0.7, 0.0, 0.6));   // specular AA
    vec3 e = envMap(r, rough);
    float F = pow(1.0 - ndv, 5.0);
    vec3 c = e * mix(uTint, vec3(1.0), 0.35 + 0.65 * F);
    c += film(ndv * 1.6 + uFilmShift + vUv.x * 0.7) * (vEdge * 0.7 + pow(1.0 - ndv, 4.0) * 0.3) * uFilm * (0.3 + dot(e, vec3(0.25)));
    vec3 paint = uTint * (0.62 + 0.45 * (0.5 + 0.5 * n.y)) + e * (0.03 + 0.45 * F);
    c = mix(c, paint, uPaint);
    gl_FragColor = vec4(min(c * uBright, vec3(14.0)), 1.0);
  }
`;

// Fake glass: premultiplied — reflection + refracted studio + thin-film edge, low alpha.
const GLASS_FRAG = /* glsl */`
  ${ENV_GLSL}
  uniform vec3 uTint; uniform float uRough, uFilm, uBright, uFilmShift, uAlpha;
  centroid varying vec3 vW; centroid varying vec3 vN; varying vec2 vUv; centroid varying float vEdge;
  void main() {
    vec3 n = normalize(vN);
    vec3 v = normalize(cameraPosition - vW);
    float ndv = clamp(dot(n, v), 0.0, 1.0);
    float F = 0.03 + 0.97 * pow(1.0 - ndv, 4.0);
    float rough = max(uRough, clamp(length(fwidth(vN)) * 0.7, 0.0, 0.6));   // specular AA
    vec3 refl = envMap(reflect(-v, n), rough);
    vec3 rd = refract(-v, n, 0.66);
    vec3 trans = envMap(rd, rough + 0.04) * uTint;
    vec3 c = refl * F + trans * (1.0 - F) * uAlpha;
    c += film(ndv * 2.2 + uFilmShift + vUv.x) * (vEdge * 0.9 + pow(1.0 - ndv, 4.0) * 0.2) * uFilm * 0.6;
    float a = clamp(uAlpha * (1.0 - F) + F * 0.9, 0.0, 1.0);
    gl_FragColor = vec4(min(c * uBright, vec3(14.0)), a);
  }
`;

// Crystal shard: faceted normals from derivatives, dispersion via 3 refraction IORs.
const SHARD_VERT = /* glsl */`
  attribute vec4 aSeed;
  varying vec3 vW; varying vec4 vSeed;
  void main() {
    vec4 w = modelMatrix * instanceMatrix * vec4(position, 1.0);
    vW = w.xyz; vSeed = aSeed;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;
const SHARD_FRAG = /* glsl */`
  ${ENV_GLSL}
  uniform vec3 uTint, uTint2; uniform float uBright, uFilm;
  varying vec3 vW; varying vec4 vSeed;
  void main() {
    vec3 n = normalize(cross(dFdx(vW), dFdy(vW)));
    vec3 v = normalize(cameraPosition - vW);
    if (dot(n, v) < 0.0) n = -n;
    float ndv = clamp(dot(n, v), 0.0, 1.0);
    float F = 0.08 + 0.92 * pow(1.0 - ndv, 3.0);
    vec3 refl = envMap(reflect(-v, n), 0.0);
    vec3 tr = vec3(envMap(refract(-v, n, 0.70), 0.02).r,
                   envMap(refract(-v, n, 0.66), 0.02).g,
                   envMap(refract(-v, n, 0.61), 0.02).b);
    vec3 tint = mix(uTint, uTint2, step(0.72, vSeed.x));
    vec3 c = refl * F + tr * tint * (1.0 - F);
    c += film(ndv * 2.0 + vSeed.y * 3.0) * pow(1.0 - ndv, 1.5) * uFilm;
    gl_FragColor = vec4(c * uBright * (0.75 + 0.5 * vSeed.z), 1.0);
  }
`;

// Shatter pieces: extruded glass tiles carrying screen-space pieces of the footage.
const PIECE_VERT = /* glsl */`
  attribute vec3 aCenter; attribute vec4 aRand; attribute vec3 aInfo; // edge, face, dist
  attribute vec2 aSuv;
  uniform float uTau, uDur, uSpread, uZoom;
  uniform vec2 uImpact;
  varying vec3 vW; varying vec3 vN; varying vec2 vSuv; varying vec3 vInfo; varying float vK;
  mat3 axisAngle(vec3 a, float g) {
    float c = cos(g), s = sin(g), t = 1.0 - c;
    return mat3(t*a.x*a.x + c, t*a.x*a.y + s*a.z, t*a.x*a.z - s*a.y,
                t*a.x*a.y - s*a.z, t*a.y*a.y + c, t*a.y*a.z + s*a.x,
                t*a.x*a.z + s*a.y, t*a.y*a.z - s*a.x, t*a.z*a.z + c);
  }
  void main() {
    float delay = aInfo.z * 0.25 * uDur;
    float tt = max(0.0, uTau - delay) / uDur;   // 0 → 1 over the duration
    float k = tt * 0.9 + tt * tt * 0.9;          // eased flight: slow separation, then away
    float pop = smoothstep(0.0, 0.03, uTau);     // hairline gaps open at impact
    vec3 axis = normalize(aRand.xyz * 2.0 - 1.0 + vec3(0.0, 0.0, 0.3));
    float ang = (aRand.w - 0.5) * 4.5 * k + (aRand.w - 0.5) * 0.05 * pop;
    mat3 R = axisAngle(axis, ang);
    vec2 away = aCenter.xy - uImpact;
    vec2 dir = away / max(length(away), 1e-3);
    vec3 move = vec3(dir * uSpread * (0.25 + aRand.x) * k,
                     uZoom * (0.25 + aRand.y) * (tt * 0.5 + tt * tt * 1.1));
    move.xy += dir * 0.01 * pop;
    vec3 p = aCenter + move + R * (position - aCenter);
    vN = normalize(R * normal);
    vW = p; vSuv = aSuv; vInfo = aInfo; vK = k;
    gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
  }
`;
const PIECE_FRAG = /* glsl */`
  ${COLOR_GLSL}
  ${ENV_GLSL}
  ${FOOTAGE_GLSL}
  uniform float uTau, uCrack;
  uniform vec3 uEdge;
  varying vec3 vW; varying vec3 vN; varying vec2 vSuv; varying vec3 vInfo; varying float vK;
  void main() {
    vec3 n = normalize(vN);
    vec3 v = normalize(cameraPosition - vW);
    if (dot(n, v) < 0.0) n = -n;
    float ndv = clamp(dot(n, v), 0.0, 1.0);
    vec3 refl = envMap(reflect(-v, n), 0.0);
    float face = vInfo.y;
    vec3 c;
    if (face < 0.5) {                       // front: the image
      c = footage(vSuv);
      float F = 0.02 + 0.98 * pow(1.0 - ndv, 5.0);
      c += refl * F * smoothstep(0.0, 0.15, vK);
      float e = vInfo.x;
      float line = 1.0 - smoothstep(0.0, fwidth(e) * 0.9, 1.0 - e);
      float reach = step(vInfo.z, uTau * 9.0 + 0.02);                 // cracks race out from the impact
      c += line * reach * uCrack * (uEdge + film(vSuv.x * 3.0 + vSuv.y * 2.0) * 1.2);
    } else if (face < 1.5) {                // back: dim glass
      c = footage(vSuv) * 0.35 + refl * 0.5;
    } else {                                // sides: bright prismatic glass edge
      c = refl * 1.2 + film(ndv * 2.5 + vSuv.x * 4.0) * 1.1 + uEdge * 0.5;
    }
    gl_FragColor = vec4(c, 1.0);
  }
`;

// ════════════════════════════════════════════════════════════════════════════════════════
// Tones (linear HDR). Box: [dirX, dirY, dirZ, halfW, halfH, intensity, soft, r, g, b, roll]
// ════════════════════════════════════════════════════════════════════════════════════════

const BOX_LAYOUT = [
  [-0.62, 0.42, 0.66, 0.55, 0.26, 1, 0.02, 0.2],  // key softbox
  [-1, 0.08, 0.08, 0.035, 1.6, 1, 0.004, 0],      // strip left
  [1, 0.05, -0.25, 0.03, 1.6, 1, 0.004, 0],       // strip right
  [0, 1, 0.12, 0.9, 0.5, 1, 0.05, 0],             // overhead
  [0.3, 0.22, -1, 1.1, 0.045, 1, 0.004, 0.1],     // back line
  [0.35, -0.12, 1, 0.8, 0.02, 1, 0.003, -0.15],   // low front line
];
const boxes = (spec) => BOX_LAYOUT.map((b, i) => [b[0], b[1], b[2], b[3], b[4], spec[i][0], b[6], ...spec[i][1], b[7]]);

const TONES = {
  silver: {
    top: [0.05, 0.052, 0.06], mid: [0.16, 0.165, 0.19], hor: [1.1, 1.12, 1.2], gnd: [0.012, 0.012, 0.016], nadir: [0, 0, 0],
    horGlow: 1.6,
    boxes: boxes([[5.5, [1, 1, 1.03]], [9, [1, 1, 1]], [8, [0.96, 0.98, 1.05]], [2.2, [0.95, 0.96, 1]], [7, [1, 1, 1]], [4, [0.9, 0.95, 1.1]]]),
    bg: [[0.018, 0.018, 0.024], [0, 0, 0]],
    chrome: [0.92, 0.94, 1.0], glass: [0.9, 0.95, 1.05], tubes: [[0.95, 0.97, 1.0], [0.8, 0.82, 0.9], [1, 1, 1]], film: 0.35,
    post: { bloom: 0.55, threshold: 1.1, disp: 0.12 },
  },
  electric: { // #1437FF accent: linear (0.007, 0.038, 1.0)
    top: [0.0, 0.002, 0.02], mid: [0.002, 0.012, 0.13], hor: [0.04, 0.13, 2.6], gnd: [0.0, 0.0, 0.01], nadir: [0, 0, 0],
    horGlow: 1.4,
    boxes: boxes([[7, [0.72, 0.8, 1.25]], [9, [0.05, 0.16, 1.6]], [7, [0.25, 0.55, 1.5]], [2.0, [0.03, 0.1, 1.0]], [8, [0.2, 0.16, 1.5]], [5, [0.1, 0.3, 1.6]]]),
    bg: [[0.002, 0.007, 0.055], [0, 0, 0.003]],
    chrome: [0.16, 0.34, 1.0], glass: [0.12, 0.3, 1.1], tubes: [[0.05, 0.16, 1.7], [0.25, 0.5, 1.8], [0.7, 0.8, 1.6]], film: 0.45,
    post: { bloom: 0.95, threshold: 0.75, disp: 0.2 },
  },
  pearl: {
    top: [1.0, 1.0, 1.05], mid: [0.8, 0.82, 0.93], hor: [0.62, 0.58, 0.85], gnd: [0.035, 0.037, 0.05], nadir: [0.012, 0.012, 0.018],
    horGlow: 0.9,
    boxes: boxes([[3.6, [1, 1, 1]], [4, [0.62, 0.84, 1.15]], [4, [0.8, 0.7, 1.1]], [1.4, [1, 1, 1]], [0.02, [0.2, 0.2, 0.26]], [2.5, [0.9, 0.95, 1.1]]]),
    bg: [[0.95, 0.955, 0.99], [0.78, 0.8, 0.9]],
    chrome: [0.88, 0.9, 0.98], glass: [0.78, 0.88, 1.08], tubes: [[0.2, 0.52, 1.0], [0.55, 0.45, 1.0], [0.06, 0.065, 0.08]],
    paint: [0.8, 0.8, 0], film: 0.7,
    post: { bloom: 0.25, threshold: 1.4, disp: 0 },
  },
  prism: {
    top: [1.1, 1.1, 1.15], mid: [0.7, 0.72, 0.78], hor: [2.2, 2.2, 2.3], gnd: [0.02, 0.02, 0.03], nadir: [0, 0, 0],
    horGlow: 1.2,
    boxes: boxes([[9, [1, 1, 1]], [10, [1, 1, 1]], [9, [1, 1, 1]], [3, [1, 1, 1]], [8, [1, 1, 1]], [6, [1, 1, 1]]]),
    bg: [[1.25, 1.25, 1.3], [0.7, 0.72, 0.8]],
    chrome: [1, 1, 1.02], glass: [1, 1, 1.05], tubes: [[1, 1, 1], [0.8, 0.9, 1.1], [0.9, 0.85, 1.1]], film: 1.0,
    post: { bloom: 1.1, threshold: 0.95, disp: 0.7 },
  },
  sky: {
    top: [0.2, 0.36, 0.78], mid: [0.48, 0.64, 0.92], hor: [0.95, 0.97, 1.0], gnd: [0.3, 0.34, 0.45], nadir: [0.1, 0.11, 0.16],
    horGlow: 0.5,
    boxes: [
      [0.4, 0.55, -0.7, 0.08, 0.08, 14, 0.03, 1, 0.97, 0.92, 0],
      [-0.7, 0.3, 0.6, 0.5, 0.18, 1.6, 0.15, 1, 1, 1, 0.1],
      [0.8, 0.25, 0.5, 0.45, 0.14, 1.3, 0.15, 1, 1, 1, -0.1],
      [0, 1, 0.1, 0.6, 0.6, 0.6, 0.2, 0.9, 0.95, 1, 0],
      [-0.2, 0.15, -1, 1.0, 0.1, 1.4, 0.12, 1, 1, 1, 0],
      [0.2, 0.4, 1, 0.3, 0.1, 1.5, 0.12, 1, 1, 1, 0],
    ],
    bg: [[0.56, 0.72, 0.95], [0.93, 0.95, 1.0]],
    chrome: [0.9, 0.95, 1.0], glass: [0.85, 0.93, 1.05], tubes: [[1.1, 1.12, 1.2], [0.8, 0.9, 1.1], [1, 1, 1]], film: 0.4,
    post: { bloom: 0.3, threshold: 1.3, disp: 0 },
  },
};
TONES.blue = TONES.electric; // aliases
TONES.night = TONES.electric;
TONES.white = TONES.pearl;
const toneOf = (p) => (TONES[p.tone] ? p.tone : TONES[p.palette] ? p.palette : null);
const T = (name) => TONES[name] || TONES.silver;

function envUniforms() {
  const v3 = () => Array.from({ length: NB }, () => new THREE.Vector3());
  return {
    eTop: { value: new THREE.Vector3() }, eMid: { value: new THREE.Vector3() }, eHor: { value: new THREE.Vector3() },
    eGnd: { value: new THREE.Vector3() }, eNadir: { value: new THREE.Vector3() },
    eHorGlow: { value: 1 }, eGain: { value: 1 }, eRot: { value: new THREE.Matrix3() },
    eBoxDir: { value: v3() }, eBoxRight: { value: v3() }, eBoxUp: { value: v3() }, eBoxCol: { value: v3() },
    eBoxP: { value: Array.from({ length: NB }, () => new THREE.Vector4()) },
  };
}

const _m4 = new THREE.Matrix4(), _eu = new THREE.Euler();
const _up = new THREE.Vector3(0, 1, 0), _z = new THREE.Vector3(0, 0, 1);
const _d = new THREE.Vector3(), _r = new THREE.Vector3(), _u = new THREE.Vector3();
function applyTone(u, name, yaw = 0, gain = 1, pitch = 0) {
  const p = T(name);
  u.eTop.value.fromArray(p.top); u.eMid.value.fromArray(p.mid); u.eHor.value.fromArray(p.hor);
  u.eGnd.value.fromArray(p.gnd); u.eNadir.value.fromArray(p.nadir);
  u.eHorGlow.value = p.horGlow; u.eGain.value = gain;
  u.eRot.value.setFromMatrix4(_m4.makeRotationFromEuler(_eu.set(pitch, yaw, 0, 'YXZ')));
  p.boxes.forEach((b, i) => {
    _d.set(b[0], b[1], b[2]).normalize();
    _r.crossVectors(Math.abs(_d.y) > 0.9 ? _z : _up, _d).normalize();
    _u.crossVectors(_d, _r).normalize();
    const c = Math.cos(b[10]), s = Math.sin(b[10]);
    u.eBoxDir.value[i].copy(_d);
    u.eBoxRight.value[i].copy(_r).multiplyScalar(c).addScaledVector(_u, s);
    u.eBoxUp.value[i].copy(_u).multiplyScalar(c).addScaledVector(_r, -s);
    u.eBoxP.value[i].set(b[3], b[4], b[5], b[6]);
    u.eBoxCol.value[i].set(b[7], b[8], b[9]);
  });
  return p;
}

// ════════════════════════════════════════════════════════════════════════════════════════
// Geometry helpers
// ════════════════════════════════════════════════════════════════════════════════════════

/* A strip of `seg` rings along s ∈ [0,1], each ring a closed stadium cross-section. */
function sweepGeometry(seg) {
  const c45 = Math.SQRT1_2;
  const prof = [
    [1, 0, 1], [-1, 0, 1], [-1, -c45, c45], [-1, -1, 0], [-1, -c45, -c45],
    [-1, 0, -1], [1, 0, -1], [1, c45, -c45], [1, 1, 0], [1, c45, c45],
  ];
  const P = prof.length;
  const uv = [], ap = [], pos = [], idx = [];
  for (let i = 0; i <= seg; i++) {
    for (let k = 0; k < P; k++) { uv.push(i / seg, k / P); ap.push(...prof[k]); pos.push(0, 0, 0); }
  }
  for (let i = 0; i < seg; i++) {
    for (let k = 0; k < P; k++) {
      const a = i * P + k, b = i * P + ((k + 1) % P), c = (i + 1) * P + ((k + 1) % P), d = (i + 1) * P + k;
      idx.push(a, b, d, b, c, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setAttribute('aProf', new THREE.Float32BufferAttribute(ap, 3));
  g.setIndex(idx);
  return g;
}

/* An irregular elongated crystal (bipyramid with a jittered waist), non-indexed. */
function crystalGeometry(rand, sides = 6) {
  const pts = [];
  const top = new THREE.Vector3((rand() - 0.5) * 0.2, 1, 0), bot = new THREE.Vector3((rand() - 0.5) * 0.15, -0.55, 0);
  const ring = [];
  for (let i = 0; i < sides; i++) {
    const a = (i / sides) * TAU + (rand() - 0.5) * 0.6;
    const r = 0.16 + rand() * 0.12;
    ring.push(new THREE.Vector3(Math.cos(a) * r, (rand() - 0.5) * 0.25, Math.sin(a) * r * 0.55));
  }
  for (let i = 0; i < sides; i++) {
    const a = ring[i], b = ring[(i + 1) % sides];
    pts.push(a, b, top, b, a, bot);
  }
  return new THREE.BufferGeometry().setFromPoints(pts);
}

/* Sutherland–Hodgman clip of a polygon against x·n <= c. */
function clipPoly(poly, nx, ny, c) {
  const out = [];
  for (let i = 0; i < poly.length; i++) {
    const [ax, ay] = poly[i], [bx, by] = poly[(i + 1) % poly.length];
    const da = ax * nx + ay * ny - c, db = bx * nx + by * ny - c;
    if (da <= 0) out.push([ax, ay]);
    if ((da <= 0) !== (db <= 0)) { const k = da / (da - db); out.push([ax + (bx - ax) * k, ay + (by - ay) * k]); }
  }
  return out;
}

/* Spider-web glass fracture of the rectangle [-hw,hw]×[-hh,hh] around (ix, iy). */
function fracture(rand, hw, hh, ix, iy) {
  const spokes = 17, rings = 8;
  const maxR = Math.hypot(hw + Math.abs(ix), hh + Math.abs(iy)) * 1.05;
  const ang = [];
  for (let i = 0; i < spokes; i++) ang.push(((i + (rand() - 0.5) * 0.7) / spokes) * TAU);
  const radii = [];
  for (let k = 0; k <= rings; k++) radii.push(maxR * Math.pow(k / rings, 1.55));
  const node = [];
  for (let k = 0; k <= rings; k++) {
    node.push(ang.map((a) => { const r = radii[k] * (k === 0 || k === rings ? 1 : 0.8 + rand() * 0.4); return [ix + Math.cos(a) * r, iy + Math.sin(a) * r]; }));
  }
  const polys = [];
  const clipRect = (p) => clipPoly(clipPoly(clipPoly(clipPoly(p, 1, 0, hw), -1, 0, hw), 0, 1, hh), 0, -1, hh);
  for (let k = 0; k < rings; k++) {
    for (let i = 0; i < spokes; i++) {
      const j = (i + 1) % spokes;
      const quad = k === 0 ? [node[0][i], node[1][i], node[1][j]] : [node[k][i], node[k + 1][i], node[k + 1][j], node[k][j]];
      const parts = [];
      if (k >= 3 && rand() < 0.75) { // split outer pieces along a random chord: less dartboard
        const cx = quad.reduce((s, q) => s + q[0], 0) / quad.length, cy = quad.reduce((s, q) => s + q[1], 0) / quad.length;
        const a = rand() * Math.PI, nx = Math.cos(a), ny = Math.sin(a), c = nx * cx + ny * cy;
        parts.push(clipPoly(quad, nx, ny, c), clipPoly(quad, -nx, -ny, -c));
      } else parts.push(quad);
      for (const p of parts) { const q = clipRect(p); if (q.length >= 3) polys.push(q); }
    }
  }
  return polys;
}

// ════════════════════════════════════════════════════════════════════════════════════════
// The kit
// ════════════════════════════════════════════════════════════════════════════════════════

export function createKit(renderer, opts = {}) {
  const { width = 1080, height = 1350, msaa = 4, seed = 11 } = opts;
  const pr = renderer.getPixelRatio();
  const W = Math.max(2, Math.round(width * pr)), H = Math.max(2, Math.round(height * pr));
  const ASPECT = width / height;

  const rt = (w, h, o = {}) => new THREE.WebGLRenderTarget(w, h, {
    type: THREE.HalfFloatType, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false, ...o,
  });
  const hdr = rt(W, H, { depthBuffer: true, samples: msaa });
  const aux = rt(W, H, { depthBuffer: true, samples: msaa }); // kaleido source
  const half = rt(Math.ceil(W / 2), Math.ceil(H / 2));        // sky
  const bloomRT = [4, 8, 16, 32].map((d) => rt(Math.max(1, Math.ceil(W / d)), Math.max(1, Math.ceil(H / d))));

  // ---- full-screen passes -------------------------------------------------------------
  const quadGeo = new THREE.BufferGeometry();
  quadGeo.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
  quadGeo.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
  const quad = new THREE.Mesh(quadGeo);
  quad.frustumCulled = false;
  const quadScene = new THREE.Scene().add(quad);
  const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const passMat = (fragmentShader, uniforms = {}, extra = {}) => new THREE.ShaderMaterial({
    vertexShader: FS_VERT, fragmentShader, uniforms, depthTest: false, depthWrite: false, ...extra,
  });
  function pass(material, target) {
    quad.material = material;
    renderer.setRenderTarget(target);
    renderer.render(quadScene, quadCam);
  }
  function clearTo(target) { renderer.setRenderTarget(target); renderer.setClearColor(0x000000, 1); renderer.clear(true, true, false); }

  function withState(fn) {
    const prevClear = renderer.autoClear, prevTarget = renderer.getRenderTarget();
    const prevColor = renderer.getClearColor(new THREE.Color()), prevAlpha = renderer.getClearAlpha();
    renderer.autoClear = false;
    try { fn(); } finally {
      renderer.autoClear = prevClear; renderer.setRenderTarget(prevTarget); renderer.setClearColor(prevColor, prevAlpha);
    }
  }

  // Gradient background (radial or vertical) drawn into an HDR target, clearing depth.
  const bgMat = passMat(/* glsl */`
    uniform vec3 c0, c1; uniform float uAspect, uLinear; uniform vec2 uCenter;
    varying vec2 vUv;
    void main() {
      vec2 p = (vUv - uCenter) * vec2(uAspect, 1.0);
      float k = uLinear > 0.5 ? smoothstep(-0.1, 1.05, 1.0 - vUv.y) : smoothstep(0.0, 0.95, length(p));
      gl_FragColor = vec4(mix(c0, c1, k), 1.0);
    }`, { c0: { value: new THREE.Vector3() }, c1: { value: new THREE.Vector3() }, uAspect: { value: ASPECT },
    uLinear: { value: 0 }, uCenter: { value: new THREE.Vector2(0.5, 0.5) } });
  function background(target, [c0, c1], linear = false, center = [0.5, 0.5]) {
    bgMat.uniforms.c0.value.fromArray(c0); bgMat.uniforms.c1.value.fromArray(c1);
    bgMat.uniforms.uLinear.value = linear ? 1 : 0; bgMat.uniforms.uCenter.value.fromArray(center);
    clearTo(target);
    pass(bgMat, target);
  }

  // ---- footage ----------------------------------------------------------------------------
  const texCache = new Map();
  function texture(el) {
    let t = texCache.get(el);
    if (!t) {
      t = new THREE.Texture(el);
      t.colorSpace = THREE.SRGBColorSpace;
      t.minFilter = THREE.LinearFilter; t.magFilter = THREE.LinearFilter; t.generateMipmaps = false;
      texCache.set(el, t);
    }
    t.needsUpdate = true;
    return t;
  }
  /** Normalise a footage param → { tex, rect, encoded, fx, aspect (px w/h of rect), texel }. */
  function source(x) {
    if (!x || typeof x === 'string') return null;
    const spec = (x.isTexture || (typeof Element !== 'undefined' && x instanceof Element)) ? { src: x } : x;
    const s = spec.src ?? spec.texture;
    if (!s) return null;
    const tex = s.isTexture ? s : texture(s);
    const r = spec.rect || [0, 0, 1, 1];
    const img = tex.image || {};
    const iw = img.videoWidth || img.naturalWidth || img.width || 1280;
    const ih = img.videoHeight || img.naturalHeight || img.height || 720;
    return { tex, rect: new THREE.Vector4(...r), encoded: !!spec.encoded, fx: spec.fx ?? 0.5,
      aspect: (r[2] * iw) / (r[3] * ih), texel: new THREE.Vector2(1 / iw, 1 / ih) };
  }
  /** Crop a source rect to `aspect` (cover), keeping horizontal focus fx. */
  function coverRect(src, aspect) {
    const r = src.rect.clone();
    if (src.aspect > aspect) { const w = r.z * aspect / src.aspect; r.x += clamp(src.fx * r.z - w / 2, 0, r.z - w); r.z = w; }
    else { const h = r.w * src.aspect / aspect; r.y += (r.w - h) / 2; r.w = h; }
    return r;
  }
  const footUniforms = () => ({
    tFoot: { value: null }, fRect: { value: new THREE.Vector4(0, 0, 1, 1) }, fTexel: { value: new THREE.Vector2(1 / 1280, 1 / 720) },
    fEncoded: { value: 0 }, fSharp: { value: 0 },
  });
  function bindFoot(u, src, rect, sharpen = 0) {
    u.tFoot.value = src.tex; u.fRect.value.copy(rect || src.rect);
    u.fTexel.value.copy(src.texel); u.fEncoded.value = src.encoded ? 1 : 0; u.fSharp.value = sharpen;
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // Post: bloom (dual filter, 1/4..1/32), spectral dispersion, tone, dither/grain
  // ════════════════════════════════════════════════════════════════════════════════════════
  const prefilter = passMat(/* glsl */`
    uniform sampler2D tIn; uniform vec2 uTexel; uniform float uThr;
    varying vec2 vUv;
    void main() {
      vec3 c = texture2D(tIn, vUv + uTexel * vec2(-1.0, -1.0)).rgb + texture2D(tIn, vUv + uTexel * vec2(1.0, -1.0)).rgb
             + texture2D(tIn, vUv + uTexel * vec2(-1.0, 1.0)).rgb + texture2D(tIn, vUv + uTexel * vec2(1.0, 1.0)).rgb;
      c *= 0.25;
      float m = max(max(c.r, c.g), c.b);
      gl_FragColor = vec4(c * (max(m - uThr, 0.0) / max(m, 1e-4)), 1.0);
    }`, { tIn: { value: null }, uTexel: { value: new THREE.Vector2() }, uThr: { value: 1 } });
  const down = passMat(/* glsl */`
    uniform sampler2D tIn; uniform vec2 uTexel; varying vec2 vUv;
    void main() {
      vec3 s = texture2D(tIn, vUv).rgb * 4.0;
      s += texture2D(tIn, vUv + uTexel * vec2(-1.0, -1.0)).rgb + texture2D(tIn, vUv + uTexel * vec2(1.0, -1.0)).rgb;
      s += texture2D(tIn, vUv + uTexel * vec2(-1.0, 1.0)).rgb + texture2D(tIn, vUv + uTexel * vec2(1.0, 1.0)).rgb;
      gl_FragColor = vec4(s / 8.0, 1.0);
    }`, { tIn: { value: null }, uTexel: { value: new THREE.Vector2() } });
  const up = passMat(/* glsl */`
    uniform sampler2D tIn; uniform vec2 uTexel; varying vec2 vUv;
    void main() {
      vec3 s = texture2D(tIn, vUv + uTexel * vec2(-2.0, 0.0)).rgb + texture2D(tIn, vUv + uTexel * vec2(2.0, 0.0)).rgb
             + texture2D(tIn, vUv + uTexel * vec2(0.0, -2.0)).rgb + texture2D(tIn, vUv + uTexel * vec2(0.0, 2.0)).rgb;
      s += 2.0 * (texture2D(tIn, vUv + uTexel * vec2(-1.0, -1.0)).rgb + texture2D(tIn, vUv + uTexel * vec2(1.0, -1.0)).rgb
             + texture2D(tIn, vUv + uTexel * vec2(-1.0, 1.0)).rgb + texture2D(tIn, vUv + uTexel * vec2(1.0, 1.0)).rgb);
      gl_FragColor = vec4(s / 12.0, 1.0);
    }`, { tIn: { value: null }, uTexel: { value: new THREE.Vector2() } },
  { blending: THREE.AdditiveBlending, transparent: true });

  const OUT_FRAG = (disp) => /* glsl */`
    ${COLOR_GLSL}
    uniform sampler2D tIn, tBloom; uniform float uBloom, uDisp, uGrain, uExposure, uVig, uFlash, uFade, uSeed, uAspect;
    varying vec2 vUv;
    float hash(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
    vec3 toneK(vec3 x) {
      x = max(x, 0.0);
      float m = max(max(x.r, x.g), x.b);
      x += max(m - 1.7, 0.0) * 0.3;                 // white-hot: very bright colour burns to white
      vec3 y = 0.8 + 0.2 * (1.0 - exp(-(x - 0.8) / 0.2));
      return mix(x, y, step(0.8, x));
    }
    void main() {
      vec3 c;
      ${disp ? `
        vec2 d = (vUv - 0.5) * vec2(uAspect, 1.0);
        vec2 o = (vUv - 0.5) * uDisp * 0.018 * (0.3 + dot(d, d));
        c  = texture2D(tIn, vUv + o).rgb * vec3(0.9, 0.05, 0.0);
        c += texture2D(tIn, vUv + o * 0.5).rgb * vec3(0.1, 0.45, 0.05);
        c += texture2D(tIn, vUv).rgb * vec3(0.0, 0.4, 0.15);
        c += texture2D(tIn, vUv - o * 0.5).rgb * vec3(0.0, 0.1, 0.4);
        c += texture2D(tIn, vUv - o).rgb * vec3(0.0, 0.0, 0.4);
      ` : 'c = texture2D(tIn, vUv).rgb;'}
      c += texture2D(tBloom, vUv).rgb * uBloom;
      c *= uExposure;
      vec2 q = (vUv - 0.5) * vec2(uAspect, 1.0);
      c *= 1.0 - uVig * smoothstep(0.25, 0.95, dot(q, q) * 1.6);
      c = toneK(c);
      c = mix(c, vec3(1.0), uFlash) * (1.0 - uFade);
      c = toSRGB(c);
      float g = hash(gl_FragCoord.xy + uSeed * 917.0) + hash(gl_FragCoord.xy * 1.37 + uSeed * 331.0) - 1.0;
      c += g * (0.5 / 255.0 + uGrain * (0.35 + 0.65 * (1.0 - abs(dot(c, vec3(0.333)) * 2.0 - 1.0))));
      gl_FragColor = vec4(c, 1.0);
    }`;
  const outUniforms = () => ({
    tIn: { value: null }, tBloom: { value: null }, uBloom: { value: 0 }, uDisp: { value: 0 }, uGrain: { value: 0 },
    uExposure: { value: 1 }, uVig: { value: 0 }, uFlash: { value: 0 }, uFade: { value: 0 }, uSeed: { value: 0 },
    uAspect: { value: ASPECT },
  });
  const outPlain = passMat(OUT_FRAG(false), outUniforms());
  const outDisp = passMat(OUT_FRAG(true), outUniforms());
  const blackTex = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1); blackTex.needsUpdate = true;

  const POST_DEFAULTS = { bloom: 0.5, threshold: 1.0, disp: 0, grain: 0, exposure: 1, vignette: 0, flash: 0, fade: 0 };
  const post = {
    defaults: POST_DEFAULTS,
    /** hdrTexture (linear) → target (null = canvas) as display-referred sRGB. */
    render(input, target = null, p = {}, t = 0) {
      p = { ...POST_DEFAULTS, ...p };
      withState(() => {
        let bloomTex = blackTex;
        if (p.bloom > 0) {
          prefilter.uniforms.tIn.value = input;
          prefilter.uniforms.uTexel.value.set(1 / W, 1 / H);
          prefilter.uniforms.uThr.value = p.threshold;
          pass(prefilter, bloomRT[0]);
          for (let i = 1; i < bloomRT.length; i++) {
            down.uniforms.tIn.value = bloomRT[i - 1].texture;
            down.uniforms.uTexel.value.set(1 / bloomRT[i - 1].width, 1 / bloomRT[i - 1].height);
            pass(down, bloomRT[i]);
          }
          for (let i = bloomRT.length - 1; i > 0; i--) {
            up.uniforms.tIn.value = bloomRT[i].texture;
            up.uniforms.uTexel.value.set(0.5 / bloomRT[i].width, 0.5 / bloomRT[i].height);
            pass(up, bloomRT[i - 1]);
          }
          bloomTex = bloomRT[0].texture;
        }
        const m = p.disp > 0 ? outDisp : outPlain;
        const u = m.uniforms;
        u.tIn.value = input; u.tBloom.value = bloomTex; u.uBloom.value = p.bloom * 0.35; u.uDisp.value = p.disp;
        u.uGrain.value = p.grain; u.uExposure.value = p.exposure; u.uVig.value = p.vignette;
        u.uFlash.value = p.flash; u.uFade.value = p.fade; u.uSeed.value = (Math.floor(t * 240) % 997) / 997;
        pass(m, target);
      });
    },
  };
  /** Scene render wrapper: HDR pass, then post with defaults ← tone ← auto ← params ← call. */
  function finish(sceneObj, target, layers) {
    withState(() => sceneObj.renderHDR(hdr));
    post.render(hdr.texture, target, Object.assign({}, ...layers), sceneObj._t || 0);
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // Ribbon system (ribbons, kaleido, sky, orbit)
  // ════════════════════════════════════════════════════════════════════════════════════════
  const ribbonGeo = sweepGeometry(260);
  const tubeGeo = sweepGeometry(300);
  const glassBlend = { transparent: true, depthWrite: false, blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor, blendEquation: THREE.AddEquation };

  function makeRibbonSystem({ seed: s, ribbons = 12, tubes = 6, rings = 0, arcs = 0, radius = [1.3, 6.5], width = [0.08, 0.6],
    tubeWidth = [0.018, 0.045], spread = 1, flat = [0.04, 0.12], spin = 0.16, ringRadius = null }) {
    const R = rng(s);
    const envU = envUniforms();
    const group = new THREE.Group();
    const items = [];
    const kinds = [...Array(ribbons).fill('ribbon'), ...Array(tubes).fill('tube'), ...Array(rings).fill('ring'), ...Array(arcs).fill('arc')];
    kinds.forEach((kind, i) => {
      const rr = kind === 'ring' || kind === 'arc' ? (ringRadius || radius) : radius;
      const rad = lerp(rr[0], rr[1], Math.pow(R(), 0.85));
      const own = {
        uTime: { value: 0 }, uSwell: { value: 1 }, uGrow: { value: 1 },
        uA: { value: new THREE.Vector4() }, uB: { value: new THREE.Vector4() },
        uC: { value: new THREE.Vector4() }, uD: { value: new THREE.Vector4() },
        uRot: { value: new THREE.Matrix3() }, uOff: { value: new THREE.Vector3() },
        uTint: { value: new THREE.Vector3(1, 1, 1) }, uRough: { value: 0 }, uFilm: { value: 0.3 },
        uBright: { value: 1 }, uFilmShift: { value: R() }, uAlpha: { value: 0.22 }, uPaint: { value: 0 }, uCamber: { value: 0 },
      };
      const uniforms = { ...envU, ...own };
      const chrome = new THREE.ShaderMaterial({ vertexShader: RIBBON_VERT, fragmentShader: CHROME_FRAG, uniforms });
      const glass = new THREE.ShaderMaterial({ vertexShader: RIBBON_VERT, fragmentShader: GLASS_FRAG, uniforms, ...glassBlend });
      const mesh = new THREE.Mesh(kind === 'ribbon' ? ribbonGeo : tubeGeo, chrome);
      mesh.frustumCulled = false;
      group.add(mesh);
      const round = kind !== 'ribbon';
      const it = {
        kind, mesh, chrome, glass, own, hue: i % 3,
        axis: new THREE.Vector3(R() - 0.5, R() - 0.5, R() - 0.5).normalize(),
        q0: new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(R() - 0.5, R() - 0.5, R() - 0.5).normalize(), R() * TAU),
        spin: (R() - 0.5) * spin * (round && kind !== 'tube' ? 2.2 : 1),
        glassRank: R(), showRank: R(), growAt: R(),
      };
      const A = [rad, kind === 'ring' ? TAU + 0.01 : kind === 'arc' ? lerp(1.6, 4.2, R()) : lerp(2.2, 5.2, R()), R() * TAU,
        (R() < 0.5 ? -1 : 1) * lerp(0.12, 0.42, R()) * (kind === 'ring' ? 0 : 1)];
      const B = kind === 'ring' || kind === 'arc' ? [0, 1, 0, 1] : [lerp(0.03, 0.22, R()), 1 + Math.floor(R() * 3), lerp(0.05, 0.9, R()) * spread, 1 + Math.floor(R() * 3)];
      const C = kind === 'ribbon'
        ? [lerp(width[0], width[1], Math.pow(R(), 1.6)), lerp(flat[0], flat[1], R()), lerp(0.2, 1.6, R()) * (R() < 0.5 ? -1 : 1), (R() - 0.5) * 0.8]
        : [lerp(tubeWidth[0], tubeWidth[1], R()), 1, 0, 0];
      const D = [kind === 'ribbon' || kind === 'tube' ? (R() - 0.5) * 2.4 * spread : 0, R() * TAU, R() * TAU, kind === 'ring' ? 0 : 1];
      const off = kind === 'ring' || kind === 'arc' ? [0, 0, 0] : [(R() - 0.5) * 0.8 * spread, (R() - 0.5) * 0.8 * spread, (R() - 0.5) * 0.8 * spread];
      own.uA.value.fromArray(A); own.uB.value.fromArray(B); own.uC.value.fromArray(C); own.uD.value.fromArray(D);
      own.uOff.value.fromArray(off);
      it.A = A;
      items.push(it);
    });
    const q = new THREE.Quaternion(), m4 = new THREE.Matrix4();
    return {
      group, items, envU,
      update(t, { tone = 'silver', speed = 1, glass = 0.45, count = 1, tubes: tubeShare = 1, energy = 0,
        envYaw = 0, bright = 1, glassAlpha = 0.22, grow = 1, camber = 0.75 } = {}) {
        const p = applyTone(envU, tone, envYaw, 1 + energy * 0.6);
        const tt = t * speed;
        for (const it of items) {
          const show = it.kind === 'ribbon' ? it.showRank < count : it.showRank < tubeShare;
          it.mesh.visible = show;
          if (!show) continue;
          const isGlass = it.kind === 'ribbon' && it.glassRank < glass;
          it.mesh.material = isGlass ? it.glass : it.chrome;
          it.mesh.renderOrder = isGlass ? 2 : 0;
          const o = it.own;
          o.uTime.value = tt;
          o.uSwell.value = 1 + energy * 0.2;
          o.uGrow.value = grow >= 1 ? 1 : smooth(0, 1, clamp(grow * 1.6 - it.growAt * 0.6, 0, 1));
          q.setFromAxisAngle(it.axis, it.spin * tt).multiply(it.q0);
          it.rot = o.uRot.value.setFromMatrix4(m4.makeRotationFromQuaternion(q));
          o.uTint.value.fromArray(it.kind === 'ribbon' ? (isGlass ? p.glass : p.chrome) : p.tubes[it.hue]);
          o.uFilm.value = p.film * (isGlass ? 1.2 : 1);
          o.uPaint.value = it.kind !== 'ribbon' && p.paint ? p.paint[it.hue] : 0;
          o.uCamber.value = it.kind === 'ribbon' ? camber : 0;
          o.uBright.value = bright * (it.kind === 'ribbon' ? 1 : 1.1) * (1 + energy * 0.3);
          o.uAlpha.value = glassAlpha;
        }
      },
    };
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // Glass/chrome slab carrying footage (orbit, sky pane)
  // ════════════════════════════════════════════════════════════════════════════════════════
  const SCREEN_FRAG = /* glsl */`
    ${COLOR_GLSL}
    ${ENV_GLSL}
    ${FOOTAGE_GLSL}
    uniform float uGloss, uSweep, uDim, uFadeY;
    centroid varying vec3 vW; centroid varying vec3 vN; varying vec2 vUv; centroid varying float vEdge;
    void main() {
      vec3 c = footage(vUv);
      vec3 n = normalize(vN), v = normalize(cameraPosition - vW);
      float ndv = clamp(dot(n, v), 0.0, 1.0);
      float F = pow(1.0 - ndv, 5.0);
      vec3 e = envMap(reflect(-v, n), 0.0);
      c += max(e - 0.9, 0.0) * (0.04 + F) * 0.25 * uGloss;            // only real highlights glint
      float band = exp(-pow((vUv.x * 0.8 + vUv.y * 0.45 - uSweep) * 10.0, 2.0));
      c += vec3(0.9, 0.95, 1.0) * band * 0.035;
      c *= uDim;
      float a = uFadeY > 0.0 ? 1.0 - smoothstep(0.0, uFadeY, vUv.y) : 1.0;
      gl_FragColor = vec4(c * a, 1.0);
    }`;
  function makeSlab(envU) {
    const frameU = { ...envU, uTint: { value: new THREE.Vector3(0.9, 0.92, 1.0) }, uRough: { value: 0.02 }, uFilm: { value: 0.4 },
      uBright: { value: 1 }, uFilmShift: { value: 0.1 } };
    const frameMat = new THREE.ShaderMaterial({ vertexShader: MESH_VERT, fragmentShader: CHROME_FRAG, uniforms: frameU });
    const screenU = { ...envU, ...footUniforms(), uGloss: { value: 1 }, uSweep: { value: -9 }, uDim: { value: 1 }, uFadeY: { value: 0 } };
    const screenMat = new THREE.ShaderMaterial({ vertexShader: MESH_VERT, fragmentShader: SCREEN_FRAG, uniforms: screenU });
    const reflU = { ...screenU, uDim: { value: 0.3 }, uFadeY: { value: 0.45 }, uGloss: { value: 0 }, uSweep: { value: -9 } };
    const reflMat = new THREE.ShaderMaterial({ vertexShader: MESH_VERT, fragmentShader: SCREEN_FRAG, uniforms: reflU,
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
    const group = new THREE.Group();
    const frame = new THREE.Mesh(new RoundedBoxGeometry(1, 1, 1, 4, 0.5), frameMat);
    const screen = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), screenMat);
    group.add(frame, screen);
    const refl = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), reflMat);
    return {
      group, refl, frameU,
      /** Unit-width slab; returns its height. */
      update(foot, t, { sharpen = 0.35, gloss = 1, sweep = 1, reflection = 0, bezel = 0.016, depth = 0.04, tint } = {}) {
        const sh = 1 / foot.aspect;
        screen.scale.set(1, sh, 1); screen.position.z = depth / 2 + 0.0015;
        frame.scale.set(1 + bezel * 2, sh + bezel * 2, depth);
        bindFoot(screenU, foot, foot.rect, sharpen);
        screenU.uGloss.value = gloss;
        screenU.uSweep.value = sweep > 0 ? lerp(-0.6, 2.2, ((t % 7) / 7)) : -9;
        if (tint) frameU.uTint.value.fromArray(tint);
        refl.visible = reflection > 0;
        reflU.uDim.value = 0.35 * reflection;
        return sh;
      },
    };
  }

  // ════════════════════════════════════════════════════════════════════════════════════════
  // Scene: ribbons
  // ════════════════════════════════════════════════════════════════════════════════════════
  const ribbons = (() => {
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(42, ASPECT, 0.05, 100);
    const systems = new Map();
    const sys = (sd) => {
      if (!systems.has(sd)) {
        const s = makeRibbonSystem({ seed: 1000 + sd * 7, ribbons: 13, tubes: 7 });
        systems.set(sd, s);
        scene.add(s.group);
      }
      return systems.get(sd);
    };
    const defaults = { tone: 'silver', seed: 1, speed: 1, glass: 0.45, count: 1, tubes: 1, energy: 0, unfurl: 0, dist: 8.5, orbit: 0.12,
      post: {} };
    let p = defaults;
    const self = {
      defaults,
      update(t, params = {}) {
        p = { ...defaults, ...params };
        p.tone = toneOf(p) || 'silver';
        self._t = t;
        for (const [k, s] of systems) s.group.visible = k === p.seed;
        sys(p.seed).update(t, { tone: p.tone, speed: p.speed, glass: p.glass, count: p.count, tubes: p.tubes, energy: p.energy,
          envYaw: t * 0.05 * p.speed, glassAlpha: p.tone === 'pearl' ? 0.3 : 0.2,
          grow: p.unfurl > 0 ? clamp(t / p.unfurl, 0, 1) : 1 });
        const a = 0.6 + t * p.orbit * p.speed;
        const d = p.dist * (1 - 0.04 * Math.sin(t * 0.21));
        cam.position.set(Math.sin(a) * d, 0.9 * Math.sin(t * 0.13 + 1) + 0.6, Math.cos(a) * d);
        cam.up.set(Math.sin(t * 0.07) * 0.25, 1, 0).normalize();
        cam.lookAt(0, 0, 0);
      },
      renderHDR(target) {
        background(target, T(p.tone).bg, p.tone === 'sky', [0.5, 0.55]);
        renderer.render(scene, cam);
      },
      render(target = null, postP = {}) {
        finish(self, target, [T(p.tone).post, { disp: T(p.tone).post.disp * 1.2 }, p.post, postP]);
      },
    };
    return self;
  })();

  // ════════════════════════════════════════════════════════════════════════════════════════
  // Scene: kaleido
  // ════════════════════════════════════════════════════════════════════════════════════════
  const kaleido = (() => {
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(38, ASPECT, 0.05, 100);
    const systems = new Map();
    const sys = (sd) => {
      if (!systems.has(sd)) {
        const s = makeRibbonSystem({ seed: 500 + sd * 13, ribbons: 12, tubes: 4, rings: 3, radius: [0.5, 3.4],
          width: [0.14, 0.8], tubeWidth: [0.025, 0.06], spread: 0.7, flat: [0.06, 0.2], ringRadius: [0.8, 2.6] });
        systems.set(sd, s);
        scene.add(s.group);
      }
      return systems.get(sd);
    };
    const mat = passMat(/* glsl */`
      ${COLOR_GLSL}
      ${FOOTAGE_GLSL}
      uniform sampler2D tSrc; uniform float uFolds, uAngle, uZoom, uAspect, uMode, uUseFoot, uSrcAspect;
      uniform vec2 uShift;
      varying vec2 vUv;
      mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }
      void main() {
        vec2 p = (vUv - 0.5) * vec2(uAspect, 1.0);
        p = rot(uAngle) * p / uZoom;
        if (uMode < 0.5) {
          float r = length(p), a = atan(p.y, p.x);
          float seg = 3.14159265 / uFolds;
          a = mod(a, 2.0 * seg); a = abs(a - seg);
          p = r * vec2(cos(a), sin(a));
        } else {
          for (int i = 0; i < 5; i++) {
            p = abs(p) - vec2(0.36, 0.22);
            p = rot(0.62 + uAngle * 0.15) * p;
            p *= 1.18;
          }
          p *= 0.55;
        }
        p = rot(-0.4) * p + uShift;
        vec2 uv = 0.5 + p * vec2(1.0 / uSrcAspect, 1.0);
        uv = 1.0 - abs(1.0 - mod(uv, 2.0));           // mirror-repeat: never smears
        vec3 c = uUseFoot > 0.5 ? footage(uv) : texture2D(tSrc, uv).rgb;
        gl_FragColor = vec4(c, 1.0);
      }`, { ...footUniforms(), tSrc: { value: null }, uFolds: { value: 6 }, uAngle: { value: 0 }, uZoom: { value: 1 },
      uAspect: { value: ASPECT }, uMode: { value: 0 }, uUseFoot: { value: 0 }, uSrcAspect: { value: ASPECT },
      uShift: { value: new THREE.Vector2() } });
    const defaults = { tone: 'silver', source: 'chrome', folds: 6, mode: 'radial', rotation: 0, spin: 0.15, zoom: 1,
      seed: 3, speed: 1, energy: 0, glass: 0.4, post: {} };
    let p = defaults, foot = null;
    const self = {
      defaults,
      update(t, params = {}) {
        p = { ...defaults, ...params };
        p.tone = toneOf(p) || 'silver';
        self._t = t;
        foot = source(p.source === 'chrome' ? null : p.source);
        const u = mat.uniforms;
        u.uFolds.value = p.folds; u.uAngle.value = p.rotation + p.spin * t; u.uZoom.value = p.zoom;
        u.uMode.value = p.mode === 'kifs' ? 1 : 0;
        if (foot) {
          bindFoot(u, foot, foot.rect, 0);
          u.uUseFoot.value = 1; u.uSrcAspect.value = foot.aspect;
          u.uShift.value.set(0.08 * Math.sin(t * 0.3), 0.05 * Math.cos(t * 0.23));
        } else {
          u.uUseFoot.value = 0; u.uSrcAspect.value = ASPECT; u.uShift.value.set(0.1, 0.02);
          for (const [k, s] of systems) s.group.visible = k === p.seed;
          sys(p.seed).update(t, { tone: p.tone, speed: p.speed, glass: p.glass, energy: p.energy, envYaw: t * 0.08, glassAlpha: 0.25 });
          const a = t * 0.1 * p.speed;
          cam.position.set(Math.sin(a) * 6.2, Math.cos(a * 0.7) * 1.2, Math.cos(a) * 6.2);
          cam.lookAt(0, 0, 0);
        }
      },
      renderHDR(target) {
        if (!foot) {
          background(aux, T(p.tone).bg, false);
          renderer.render(scene, cam);
          mat.uniforms.tSrc.value = aux.texture;
        }
        clearTo(target);
        pass(mat, target);
      },
      render(target = null, postP = {}) {
        const footPost = foot ? { bloom: 0.15, threshold: 1.7, disp: 0 } : {};
        finish(self, target, [T(p.tone).post, { disp: T(p.tone).post.disp * 1.5 }, footPost, p.post, postP]);
      },
    };
    return self;
  })();

  // ════════════════════════════════════════════════════════════════════════════════════════
  // Scene: shards (crystal burst + footage shatter)
  // ════════════════════════════════════════════════════════════════════════════════════════
  const shards = (() => {
    const R = rng(seed * 31 + 7);
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(50, ASPECT, 0.05, 200);
    const envU = envUniforms();
    const shardU = { ...envU, uTint: { value: new THREE.Vector3(1, 1, 1) }, uTint2: { value: new THREE.Vector3(0.5, 0.8, 1.2) },
      uBright: { value: 1.6 }, uFilm: { value: 0.6 } };
    const shardMat = new THREE.ShaderMaterial({ vertexShader: SHARD_VERT, fragmentShader: SHARD_FRAG, uniforms: shardU });
    const SLOTS = 3, PER = 260;
    const meshes = [0, 1, 2].map(() => {
      const g = crystalGeometry(R, 5 + Math.floor(R() * 3));
      const m = new THREE.InstancedMesh(g, shardMat, SLOTS * PER);
      const seeds = new Float32Array(SLOTS * PER * 4);
      for (let i = 0; i < seeds.length; i++) seeds[i] = R();
      g.setAttribute('aSeed', new THREE.InstancedBufferAttribute(seeds, 4));
      m.frustumCulled = false;
      scene.add(m);
      return m;
    });
    const shardData = Array.from({ length: SLOTS * PER * 3 }, () => {
      const z = lerp(-0.6, 1, R()), a = R() * TAU, r = Math.sqrt(1 - z * z);
      const dir = new THREE.Vector3(r * Math.cos(a), r * Math.sin(a) * 1.15, z).normalize();
      return { dir, speed: lerp(2.2, 11, Math.pow(R(), 1.8)), drift: lerp(0.2, 1.4, R()),
        axis: new THREE.Vector3(R() - 0.5, R() - 0.5, R() - 0.5).normalize(), spin: lerp(-5, 5, R()), spin2: lerp(-0.8, 0.8, R()),
        size: lerp(0.12, 0.6, Math.pow(R(), 2.2)), stretch: lerp(0.8, 2.6, R()),
        q0: new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir) };
    });

    // Light burst behind the shards (additive, full screen).
    const flashMat = passMat(/* glsl */`
      uniform float uFlash, uRays, uTime, uAspect; uniform vec3 uCol;
      varying vec2 vUv;
      float h(float n) { return fract(sin(n * 12.9898 + 4.1) * 43758.5453); }
      // periodic value noise (period = per cells), so the ray fan has no seam at +-pi
      float n1(float x, float per) { float i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
        return mix(h(mod(i, per)), h(mod(i + 1.0, per)), f); }
      void main() {
        vec2 p = (vUv - 0.5) * vec2(uAspect, 1.0);
        float r = length(p), a = atan(p.y, p.x) + 3.14159265;
        float A = a * 2.8647889;                        // 18 cells around the circle
        float rays = pow(n1(A + uTime * 0.6, 18.0) * n1(A * 2.0 + 7.0 - uTime * 0.9, 36.0), 3.0) * 3.0 + pow(n1(A * 4.0 + 11.0, 72.0), 8.0) * 4.0;
        vec3 c = uCol * (uFlash * (0.25 / (r * r * 18.0 + 0.08)) + uRays * rays * exp(-r * 2.2) * 0.9);
        gl_FragColor = vec4(c, 1.0);
      }`, { uFlash: { value: 0 }, uRays: { value: 0 }, uTime: { value: 0 }, uAspect: { value: ASPECT }, uCol: { value: new THREE.Vector3(1, 1, 1) } },
    { blending: THREE.AdditiveBlending, transparent: true });

    // ---- shatter --------------------------------------------------------------------------
    const shScene = new THREE.Scene();
    const shCam = new THREE.PerspectiveCamera(30, ASPECT, 0.05, 100);
    const PLANE_D = 5;
    const hh = Math.tan(THREE.MathUtils.degToRad(15)) * PLANE_D, hw = hh * ASPECT;
    shCam.position.set(0, 0, PLANE_D); shCam.lookAt(0, 0, 0);
    const pieceU = { ...envUniforms(), ...footUniforms(), uTau: { value: -1 }, uDur: { value: 1 }, uSpread: { value: 1 },
      uZoom: { value: 1 }, uImpact: { value: new THREE.Vector2() }, uCrack: { value: 0 }, uEdge: { value: new THREE.Vector3(1.6, 1.8, 2.2) } };
    const pieceMat = new THREE.ShaderMaterial({ vertexShader: PIECE_VERT, fragmentShader: PIECE_FRAG, uniforms: pieceU });
    let pieces = null, piecesKey = '';
    function buildPieces(ix, iy) {
      const polys = fracture(rng(seed * 17 + 3), hw, hh, ix, iy);
      const P = [], N = [], C = [], Rn = [], I = [], S = [];
      const th = 0.035, maxD = Math.hypot(hw * 2, hh * 2);
      const rr = rng(seed * 5 + 1);
      for (const poly of polys) {
        const cx = poly.reduce((s, q) => s + q[0], 0) / poly.length, cy = poly.reduce((s, q) => s + q[1], 0) / poly.length;
        const rnd = [rr(), rr(), rr(), rr()];
        const dist = Math.hypot(cx - ix, cy - iy) / maxD;
        const push = (x, y, z, nx, ny, nz, edge, face) => {
          P.push(x, y, z); N.push(nx, ny, nz); C.push(cx, cy, 0); Rn.push(...rnd); I.push(edge, face, dist);
          S.push(x / (2 * hw) + 0.5, y / (2 * hh) + 0.5);
        };
        for (let i = 0; i < poly.length; i++) {
          const [ax, ay] = poly[i], [bx, by] = poly[(i + 1) % poly.length];
          push(cx, cy, 0, 0, 0, 1, 0, 0); push(ax, ay, 0, 0, 0, 1, 1, 0); push(bx, by, 0, 0, 0, 1, 1, 0);         // front
          push(cx, cy, -th, 0, 0, -1, 0, 1); push(bx, by, -th, 0, 0, -1, 1, 1); push(ax, ay, -th, 0, 0, -1, 1, 1); // back
          let nx = by - ay, ny = -(bx - ax); const l = Math.hypot(nx, ny) || 1; nx /= l; ny /= l;
          push(ax, ay, 0, nx, ny, 0, 1, 2); push(ax, ay, -th, nx, ny, 0, 1, 2); push(bx, by, 0, nx, ny, 0, 1, 2);
          push(bx, by, 0, nx, ny, 0, 1, 2); push(ax, ay, -th, nx, ny, 0, 1, 2); push(bx, by, -th, nx, ny, 0, 1, 2);
        }
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
      g.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3));
      g.setAttribute('aCenter', new THREE.Float32BufferAttribute(C, 3));
      g.setAttribute('aRand', new THREE.Float32BufferAttribute(Rn, 4));
      g.setAttribute('aInfo', new THREE.Float32BufferAttribute(I, 3));
      g.setAttribute('aSuv', new THREE.Float32BufferAttribute(S, 2));
      if (pieces) { shScene.remove(pieces); pieces.geometry.dispose(); }
      pieces = new THREE.Mesh(g, pieceMat);
      pieces.frustumCulled = false;
      shScene.add(pieces);
    }
    const behindMat = passMat(/* glsl */`
      ${COLOR_GLSL}
      ${FOOTAGE_GLSL}
      uniform vec3 uColor; uniform float uUse;
      varying vec2 vUv;
      void main() { gl_FragColor = vec4(uUse > 0.5 ? footage(vUv) : uColor, 1.0); }`,
    { ...footUniforms(), uColor: { value: new THREE.Vector3() }, uUse: { value: 0 } });

    const q = new THREE.Quaternion(), q2 = new THREE.Quaternion(), m4 = new THREE.Matrix4(), v = new THREE.Vector3(), sc = new THREE.Vector3();
    const pos = new THREE.Vector3(), yAxis = new THREE.Vector3(0.3, 1, 0.1).normalize();
    const defaults = { tone: 'silver', mode: 'burst', hits: [0.5], count: 1, energy: 0,
      hit: 0.4, duration: 1.1, impact: [0.5, 0.5], behind: 'burst', behindColor: [0, 0, 0], post: {} };
    const look = {
      silver: { tints: [[1.05, 1.05, 1.1], [0.55, 0.85, 1.25]], env: 'silver', gain: 1.3, bright: 1.6, film: 0.6, flash: [1, 1, 1.08], bg: [[0.01, 0.01, 0.014], [0, 0, 0]] },
      electric: { tints: [[0.2, 0.42, 1.5], [0.75, 0.85, 1.3]], env: 'electric', gain: 1.3, bright: 1.7, film: 0.5, flash: [0.12, 0.3, 1.6], bg: TONES.electric.bg },
      pearl: { tints: [[0.95, 0.95, 1.05], [0.72, 0.68, 1.15]], env: 'silver', gain: 1.3, bright: 1.5, film: 0.7, flash: [1, 1, 1.05], bg: [[0.9, 0.91, 0.96], [0.66, 0.68, 0.78]] },
      prism: { tints: [[1.0, 1.0, 1.04], [0.55, 0.8, 1.25]], env: 'prism', gain: 0.75, bright: 1.1, film: 1.3, flash: [0.8, 0.8, 0.85], bg: [[1.35, 1.35, 1.4], [0.74, 0.75, 0.82]] },
      sky: { tints: [[1, 1, 1.05], [0.6, 0.85, 1.2]], env: 'sky', gain: 1.1, bright: 1.3, film: 0.6, flash: [1, 1, 1.05], bg: TONES.sky.bg },
    };
    let p = defaults, flash = 0, tau = 0, since = 1e9;

    function updateBurst(t, hitsIn) {
      const L = look[p.tone] || look.silver;
      applyTone(envU, L.env, t * 0.25, L.gain * (1 + p.energy * 0.45));
      shardU.uTint.value.fromArray(L.tints[0]); shardU.uTint2.value.fromArray(L.tints[1]);
      shardU.uBright.value = L.bright; shardU.uFilm.value = L.film;
      const hits = [...hitsIn].sort((a, b) => a - b);
      const past = hits.map((h, i) => ({ h, i })).filter((x) => x.h <= t);
      const counts = meshes.map(() => 0);
      const first = hits.length ? hits[0] : Infinity;
      const perSlot = Math.floor(PER * p.count);
      const place = (mi, P, Q, s, st) => {
        if (s <= 1e-4) return;
        m4.compose(P, Q, sc.set(s, s * st, s));
        meshes[mi].setMatrixAt(counts[mi]++, m4);
      };
      flash = 0;
      since = past.length ? t - past[past.length - 1].h : 1e9;
      if (t < first) {
        // Before the first hit: a slowly turning crystal cluster, spikes out.
        const k = hits.length ? smooth(first - 1.2, first, t) : 0;
        q.setFromAxisAngle(yAxis, t * 0.25 + k * 0.4);
        for (let i = 0; i < perSlot * 0.55; i++) {
          const d = shardData[i];
          pos.copy(d.dir).applyQuaternion(q).multiplyScalar(0.45 + d.size * 0.9 + k * 0.08);
          q2.copy(q).multiply(d.q0);
          place(i % 3, pos, q2, d.size * 1.6, d.stretch * 1.3);
        }
      }
      for (const { h, i: bi } of past.slice(-SLOTS)) {
        const tau = t - h;
        flash = Math.max(flash, Math.exp(-tau * 9) * 1.6 + Math.exp(-tau * 2.2) * 0.25);
        const grow = smooth(0, 0.05, tau), life = 1 - smooth(2.2, 3.4, tau);
        if (life <= 0) continue;
        const k = 1 - Math.exp(-tau * 5.5);
        const base = (bi % SLOTS) * PER;
        for (let j = 0; j < perSlot; j++) {
          const d = shardData[(base + j + bi * 97) % shardData.length];
          pos.copy(d.dir).multiplyScalar(d.speed * k + d.drift * tau);
          q.setFromAxisAngle(d.axis, d.spin * k + d.spin2 * tau).multiply(d.q0);
          place((j + bi) % 3, pos, q, d.size * grow * life, d.stretch);
        }
      }
      meshes.forEach((m, i) => { m.count = counts[i]; m.instanceMatrix.needsUpdate = true; });
      const a = t * 0.12;
      cam.position.set(Math.sin(a) * 7.5, 0.4 + Math.sin(t * 0.3) * 0.4, Math.cos(a) * 7.5);
      cam.up.set(Math.sin(t * 0.1) * 0.2, 1, 0).normalize();
      cam.lookAt(0, 0, 0);
      const fu = flashMat.uniforms;
      fu.uFlash.value = flash;
      fu.uRays.value = flash * 0.8 + (t < first ? 0.12 : 0);
      fu.uTime.value = t;
      fu.uCol.value.fromArray(L.flash);
    }

    function updateShatter(t) {
      const foot = source(p.footage);
      if (!foot) throw new Error('kit3d shards shatter: params.footage is required');
      const ix = (p.impact[0] - 0.5) * 2 * hw, iy = (p.impact[1] - 0.5) * 2 * hh;
      const key = `${ix.toFixed(3)},${iy.toFixed(3)}`;
      if (key !== piecesKey) { buildPieces(ix, iy); piecesKey = key; }
      applyTone(pieceU, p.tone === 'electric' ? 'electric' : 'silver', 0.3, 1.2);
      pieceU.uEdge.value.fromArray(p.tone === 'electric' ? [0.3, 0.6, 2.4] : [1.6, 1.8, 2.2]);
      bindFoot(pieceU, foot, coverRect(foot, ASPECT), 0);
      tau = t - p.hit;
      pieceU.uTau.value = tau; pieceU.uDur.value = p.duration;
      pieceU.uSpread.value = hw * 1.2; pieceU.uZoom.value = PLANE_D;
      pieceU.uImpact.value.set(ix, iy);
      pieceU.uCrack.value = tau < 0 ? 0 : Math.exp(-tau * 4) * 1.1 + 0.2;
      const b = p.behind && p.behind !== 'burst' ? source(p.behind) : null;
      behindMat.uniforms.uUse.value = b ? 1 : 0;
      behindMat.uniforms.uColor.value.fromArray(p.behindColor.map((c) => Math.pow(c, 2.2)));
      if (b) bindFoot(behindMat.uniforms, b, coverRect(b, ASPECT), 0);
      if (p.behind === 'burst') updateBurst(t, params_hits(p, true));
    }
    const params_hits = (pp, shatter) => (shatter ? (pp.hitsGiven ? pp.hits : [pp.hit + 0.03]) : pp.hits);

    function renderBurst(target) {
      background(target, (look[p.tone] || look.silver).bg, false);
      renderer.render(scene, cam);
      pass(flashMat, target);
    }
    const self = {
      defaults,
      update(t, params = {}) {
        p = { ...defaults, ...params, hitsGiven: !!params.hits };
        p.tone = toneOf(p) || 'silver';
        self._t = t;
        if (p.mode === 'shatter') updateShatter(t);
        else updateBurst(t, p.hits);
      },
      renderHDR(target) {
        if (p.mode === 'shatter') {
          if (p.behind === 'burst') renderBurst(target);
          else { clearTo(target); pass(behindMat, target); }
          renderer.setRenderTarget(target); renderer.clearDepth();
          renderer.render(shScene, shCam);
          return;
        }
        renderBurst(target);
      },
      render(target = null, postP = {}) {
        const L = T(p.tone).post;
        const auto = p.mode === 'shatter'
          ? { bloom: 0.6, threshold: 1.7, disp: tau > 0 ? L.disp * Math.exp(-tau * 1.5) + 0.25 * Math.exp(-tau * 3) : 0 }
          : { bloom: p.tone === 'prism' ? 0.8 : 1.1, threshold: p.tone === 'prism' ? 1.1 : 0.9, disp: L.disp + 0.3,
            // prism: the hit blows out to white and bleeds back over ~0.4 s; others: a brief lift
            flash: p.tone === 'prism' ? 0.92 * Math.exp(-since * 7) : clamp((flash - 1.1) * 0.4, 0, 0.35) };
        finish(self, target, [L, auto, p.post, postP]);
      },
    };
    return self;
  })();

  // ════════════════════════════════════════════════════════════════════════════════════════
  // Scene: sky (procedural clouds at 1/2 res; optional chrome object; optional footage pane)
  // ════════════════════════════════════════════════════════════════════════════════════════
  const sky = (() => {
    const noiseRT = new THREE.WebGLRenderTarget(512, 512, { type: THREE.UnsignedByteType, depthBuffer: false,
      wrapS: THREE.RepeatWrapping, wrapT: THREE.RepeatWrapping, minFilter: THREE.LinearMipmapLinearFilter,
      magFilter: THREE.LinearFilter, generateMipmaps: true });
    const noiseMat = passMat(/* glsl */`
      varying vec2 vUv;
      float hash(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
      float vn(vec2 p, float per) {
        vec2 i = floor(p), f = fract(p); vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
        float a = hash(mod(i, per)), b = hash(mod(i + vec2(1, 0), per)), c = hash(mod(i + vec2(0, 1), per)), d = hash(mod(i + 1.0, per));
        return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
      }
      float fbm(vec2 uv, float base, float seed) {
        float s = 0.0, a = 0.5, per = base; vec2 p = uv * base + seed;
        for (int i = 0; i < 6; i++) { s += a * vn(p, per); p = p * 2.0; per *= 2.0; a *= 0.5; }
        return s / 0.984;
      }
      void main() {
        float billow = 1.0 - abs(fbm(vUv, 8.0, 17.0) * 2.0 - 1.0);
        gl_FragColor = vec4(fbm(vUv, 4.0, 0.0), fbm(vUv, 8.0, 5.0), fbm(vUv, 16.0, 9.0), billow);
      }`);
    let noiseReady = false;
    const skyMat = passMat(/* glsl */`
      uniform sampler2D tN; uniform float uTime, uCover, uWind, uTanY, uAspect, uMono;
      uniform vec3 uF, uR, uU, uSun, uZen, uHor, uLilac;
      varying vec2 vUv;
      float fbmT(vec2 p) {
        return texture2D(tN, p * 0.045).r * 0.6 + texture2D(tN, p * 0.12 + 0.31).g * 0.28 + texture2D(tN, p * 0.33 + 0.71).b * 0.14;
      }
      void main() {
        vec2 s = (vUv * 2.0 - 1.0) * vec2(uTanY * uAspect, uTanY);
        vec3 rd = normalize(uF + s.x * uR + s.y * uU);
        float el = rd.y;
        float sd = max(dot(rd, uSun), 0.0);
        vec3 c = mix(uHor, uZen, pow(clamp(el, 0.0, 1.0), 0.45));
        c = mix(c, uLilac, exp(-max(el, 0.0) * 12.0) * 0.45);
        c += vec3(1.0, 0.97, 0.92) * (pow(sd, 8.0) * 0.16 + pow(sd, 600.0) * 2.0);
        if (el > 0.0) {
          float t = 1.0 / max(el, 0.04);
          float fade = exp(-t * 0.14);
          vec2 p = rd.xz * t * 5.0 + vec2(uTime * 0.25, uTime * 0.06) * uWind;
          float cover = 1.0 - uCover;
          float n = fbmT(p);
          float d = smoothstep(cover, cover + 0.11, n);
          float nl = fbmT(p + uSun.xz * 1.1);
          float lit = clamp(0.58 + (n - nl) * 3.2, 0.0, 1.0);                 // lit where density falls toward the sun
          float core = smoothstep(cover + 0.04, cover + 0.3, n);
          vec3 shade = mix(vec3(0.44, 0.52, 0.7), vec3(1.22, 1.21, 1.2), lit);
          shade *= mix(vec3(1.0), vec3(0.82, 0.86, 0.96), core * (1.0 - lit) * 0.7);
          shade += vec3(1.0, 0.97, 0.92) * pow(sd, 4.0) * (1.0 - core) * 0.9;  // silver lining
          c = mix(c, mix(c, shade, fade), d);
          vec2 p2 = rd.xz * t * 2.2 + vec2(uTime * 0.07, 0.0) * uWind;        // high cirrus
          float ci = smoothstep(0.55, 0.92, texture2D(tN, p2 * vec2(0.018, 0.06)).a) * 0.3 * fade * (1.0 - d);
          c = mix(c, vec3(1.05, 1.05, 1.08), ci);
        }
        c = mix(c, vec3(dot(c, vec3(0.2126, 0.7152, 0.0722))), uMono);
        gl_FragColor = vec4(c, 1.0);
      }`, { tN: { value: noiseRT.texture }, uTime: { value: 0 }, uCover: { value: 0.5 }, uWind: { value: 1 }, uMono: { value: 0 },
      uTanY: { value: 1 }, uAspect: { value: ASPECT }, uF: { value: new THREE.Vector3() }, uR: { value: new THREE.Vector3() },
      uU: { value: new THREE.Vector3() }, uSun: { value: new THREE.Vector3(-0.29, 0.7, -0.65).normalize() },
      uZen: { value: new THREE.Vector3(0.1, 0.27, 0.7) }, uHor: { value: new THREE.Vector3(0.62, 0.74, 0.93) },
      uLilac: { value: new THREE.Vector3(0.78, 0.74, 0.97) } });
    const blitMat = passMat(`uniform sampler2D tIn; varying vec2 vUv; void main() { gl_FragColor = vec4(texture2D(tIn, vUv).rgb, 1.0); }`,
      { tIn: { value: half.texture } });

    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(50, ASPECT, 0.05, 200);
    const envU = envUniforms();
    const chromeU = { ...envU, uTint: { value: new THREE.Vector3(0.92, 0.95, 1.0) }, uRough: { value: 0 }, uFilm: { value: 0.35 },
      uBright: { value: 1 }, uFilmShift: { value: 0.2 } };
    const chromeMat = new THREE.ShaderMaterial({ vertexShader: MESH_VERT, fragmentShader: CHROME_FRAG, uniforms: chromeU });
    const rings = new THREE.Group();
    const ringA = new THREE.Mesh(new THREE.TorusGeometry(1, 0.075, 32, 160), chromeMat);
    const ringB = new THREE.Mesh(new THREE.TorusGeometry(0.72, 0.05, 32, 140), chromeMat);
    ringB.rotation.x = Math.PI / 2; ringB.position.x = 0.7;
    rings.add(ringA, ringB);
    scene.add(rings);
    const rib = makeRibbonSystem({ seed: seed * 3 + 1, ribbons: 2, tubes: 1, radius: [2.2, 2.6], width: [0.5, 0.7], spread: 0.3 });
    scene.add(rib.group);
    const slab = makeSlab(envU);
    scene.add(slab.group);

    const defaults = { tone: 'pearl', object: 'rings', cross: [0, 5], cover: 0.5, wind: 1, pitch: 0.42, pane: 0.88, post: {} };
    let p = defaults, hasPane = false;
    const F = new THREE.Vector3(), Rv = new THREE.Vector3(), U = new THREE.Vector3();
    const self = {
      defaults,
      update(t, params = {}) {
        p = { ...defaults, ...params };
        self._t = t;
        const yaw = 0.4 + t * 0.018, pitch = p.pitch + Math.sin(t * 0.2) * 0.015;
        F.set(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));
        Rv.crossVectors(F, _up).normalize();
        U.crossVectors(Rv, F);
        const u = skyMat.uniforms;
        u.uF.value.copy(F); u.uR.value.copy(Rv); u.uU.value.copy(U);
        u.uTanY.value = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));
        u.uTime.value = t; u.uCover.value = p.cover; u.uWind.value = p.wind; u.uMono.value = toneOf(p) === 'silver' ? 1 : 0;
        cam.position.set(0, 0, 0); cam.up.set(0, 1, 0); cam.lookAt(F);
        applyTone(envU, 'sky', -yaw, 1.05);
        const k = clamp((t - p.cross[0]) / (p.cross[1] - p.cross[0]), 0, 1);
        const e = k * k * (3 - 2 * k) * 0.35 + k * 0.65;
        rings.visible = p.object === 'rings';
        rib.group.visible = p.object === 'ribbon';
        rings.position.copy(F).multiplyScalar(7).addScaledVector(Rv, lerp(-4.5, 4.5, e)).addScaledVector(U, lerp(-1.2, 0.6, e));
        rings.rotation.set(0.5 + t * 0.25, t * 0.35, 0.2 + t * 0.1);
        if (rib.group.visible) {
          rib.update(t, { tone: 'sky', glass: 0.5, speed: 0.6, glassAlpha: 0.25, envYaw: -yaw });
          rib.group.position.copy(F).multiplyScalar(8).addScaledVector(Rv, lerp(-2, 2, e));
        }
        // Footage pane: large, facing the camera, drifting and turning very slowly.
        const foot = source(p.footage);
        hasPane = !!foot;
        slab.group.visible = hasPane;
        if (hasPane) {
          slab.update(foot, t, { sharpen: 0.35, sweep: 1, tint: [0.92, 0.95, 1.0] });
          const tanX = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)) * ASPECT;
          const dist = 1 / (2 * tanX * p.pane);
          slab.group.position.copy(F).multiplyScalar(dist).addScaledVector(Rv, Math.sin(t * 0.21) * 0.012)
            .addScaledVector(U, 0.03 * dist + Math.sin(t * 0.17) * 0.01);
          slab.group.quaternion.copy(cam.quaternion);
          slab.group.rotateY(Math.sin(t * 0.23) * 0.05);
          slab.group.rotateX(Math.sin(t * 0.19 + 1) * 0.03);
        }
      },
      renderHDR(target) {
        if (!noiseReady) { pass(noiseMat, noiseRT); noiseReady = true; }
        pass(skyMat, half);
        clearTo(target);
        pass(blitMat, target);
        if (p.object !== 'none' || hasPane) renderer.render(scene, cam);
      },
      render(target = null, postP = {}) {
        finish(self, target, [TONES.sky.post, hasPane ? { threshold: 1.8 } : {}, p.post, postP]);
      },
    };
    return self;
  })();

  // ════════════════════════════════════════════════════════════════════════════════════════
  // Scene: orbit (footage slab with orbiting camera, or armillary arcs without footage)
  // ════════════════════════════════════════════════════════════════════════════════════════
  const orbit = (() => {
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(24, ASPECT, 0.1, 200);
    const envU = envUniforms();
    const slab = makeSlab(envU);
    scene.add(slab.group, slab.refl);
    // Background ribbons live in their own pass (drawn first, depth cleared) so they can
    // never cross in front of the footage.
    const back = makeRibbonSystem({ seed: seed * 7 + 5, ribbons: 5, tubes: 4, radius: [3.2, 6], width: [0.15, 0.5], spread: 0.6 });
    back.group.position.set(0, 0.2, -5.5);
    const backScene = new THREE.Scene().add(back.group);
    // Armillary: rings + tapered arcs + a slow glass ribbon, with chrome beads riding the rings.
    const arm = makeRibbonSystem({ seed: seed * 11 + 2, ribbons: 2, tubes: 0, rings: 4, arcs: 7, radius: [2.6, 3.4],
      width: [0.35, 0.6], ringRadius: [1.1, 2.9], tubeWidth: [0.012, 0.06], spin: 0.3 });
    const armCam = new THREE.PerspectiveCamera(34, ASPECT, 0.05, 100);
    const armScene = new THREE.Scene().add(arm.group);
    const beadU = { ...arm.envU, uTint: { value: new THREE.Vector3(1, 1, 1) }, uRough: { value: 0 }, uFilm: { value: 0.4 },
      uBright: { value: 1.1 }, uFilmShift: { value: 0.4 } };
    const beadMat = new THREE.ShaderMaterial({ vertexShader: MESH_VERT, fragmentShader: CHROME_FRAG, uniforms: beadU });
    const beadGeo = new THREE.SphereGeometry(1, 40, 24);
    const ringItems = arm.items.filter((it) => it.kind === 'ring');
    const beads = ringItems.map(() => { const m = new THREE.Mesh(beadGeo, beadMat); armScene.add(m); return m; });

    const defaults = { tone: 'pearl', fill: 0.9, yaw: 0.2, period: 9, reflection: 0.5, ribbons: 0.6, sharpen: 0.35, gloss: 1, sweep: 1,
      seed: 2, speed: 1, count: 1, energy: 0, post: {} };
    const bgs = { pearl: [[0.97, 0.975, 1.0], [0.72, 0.76, 0.9]], silver: [[0.06, 0.062, 0.07], [0, 0, 0]], electric: [[0.02, 0.035, 0.14], [0, 0, 0.005]],
      prism: [[1.1, 1.1, 1.12], [0.72, 0.74, 0.82]], sky: [[0.93, 0.95, 1.0], [0.45, 0.62, 0.92]] };
    let p = defaults, foot = null;
    const v = new THREE.Vector3();
    const self = {
      defaults,
      update(t, params = {}) {
        p = { ...defaults, ...params };
        p.tone = toneOf(p) || 'pearl';
        self._t = t;
        foot = source(p.footage);
        if (!foot) {
          // Armillary arcs.
          arm.update(t, { tone: p.tone, speed: p.speed, glass: 1, count: p.count, energy: p.energy, envYaw: t * 0.06, glassAlpha: 0.2 });
          const tt = t * p.speed;
          ringItems.forEach((it, i) => {
            const r = it.A[0], th = it.A[2] + tt * (0.35 + i * 0.12) * (i % 2 ? -1 : 1);
            v.set(r * Math.cos(th), 0, r * Math.sin(th)).applyMatrix3(it.rot);
            beads[i].position.copy(v);
            beads[i].scale.setScalar(0.06 + (i % 3) * 0.025);
          });
          beadU.uTint.value.fromArray(T(p.tone).chrome);
          const a = 0.5 + tt * 0.08;
          armCam.position.set(Math.sin(a) * 9, 1.2 + Math.sin(tt * 0.15) * 0.5, Math.cos(a) * 9);
          armCam.lookAt(0, 0.35, 0);
          return;
        }
        applyTone(envU, p.tone === 'electric' ? 'electric' : 'silver', t * 0.04, p.tone === 'electric' ? 1 : 1.1);
        back.update(t, { tone: p.tone, glass: 1, count: p.ribbons, tubes: p.ribbons * 0.5, speed: 0.5, glassAlpha: 0.18 });
        const sh = slab.update(foot, t, { sharpen: p.sharpen, gloss: p.gloss, sweep: p.sweep, reflection: p.reflection,
          tint: p.tone === 'electric' ? [0.4, 0.55, 1.0] : [0.9, 0.92, 1.0] });
        const floorY = -sh / 2 - 0.1;
        slab.refl.scale.set(1, -sh, 1);
        slab.refl.position.set(0, 2 * floorY, 0.022);
        slab.group.position.set(0, Math.sin(t * 0.6) * 0.006, 0);
        slab.group.rotation.set(Math.sin(t * 0.33) * 0.02, 0, Math.sin(t * 0.27) * 0.008);
        // Camera: slow orbit; distance puts the slab at `fill` of the frame width.
        const fovY = THREE.MathUtils.degToRad(cam.fov);
        const d = 1 / (2 * Math.tan(fovY / 2) * ASPECT * p.fill);
        const yaw = p.yaw * Math.sin((TAU * t) / p.period), pitch = 0.05 + 0.04 * Math.sin((TAU * t) / (p.period * 1.3));
        cam.position.set(Math.sin(yaw) * d * Math.cos(pitch), Math.sin(pitch) * d - sh * 0.12, Math.cos(yaw) * d * Math.cos(pitch));
        cam.lookAt(0, -sh * 0.12, 0);
      },
      renderHDR(target) {
        background(target, bgs[p.tone] || bgs.pearl, true);
        if (foot) {
          if (p.ribbons > 0) { renderer.render(backScene, cam); renderer.clearDepth(); }
          renderer.render(scene, cam);
        } else renderer.render(armScene, armCam);
      },
      render(target = null, postP = {}) {
        const auto = foot ? { bloom: 0.25, threshold: 1.8, disp: 0 } : {};
        finish(self, target, [T(p.tone).post, auto, p.post, postP]);
      },
    };
    return self;
  })();

  // PMREM of the same studio, for materials you add yourself.
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envCache = {};
  function envMap(tone = 'silver') {
    if (!envCache[tone]) {
      const u = envUniforms();
      applyTone(u, tone);
      const m = new THREE.ShaderMaterial({ side: THREE.BackSide, uniforms: u, vertexShader: MESH_VERT,
        fragmentShader: `${ENV_GLSL} centroid varying vec3 vW; centroid varying vec3 vN; varying vec2 vUv; centroid varying float vEdge; void main() { gl_FragColor = vec4(envMap(normalize(vW), 0.0), 1.0); }` });
      const s = new THREE.Scene().add(new THREE.Mesh(new THREE.SphereGeometry(10, 64, 32), m));
      withState(() => { envCache[tone] = pmrem.fromScene(s, 0, 0.1, 50).texture; });
    }
    return envCache[tone];
  }

  return {
    width, height, W, H, renderer, hdr, post, texture, envMap,
    tones: ['pearl', 'silver', 'electric', 'prism'],
    scenes: { ribbons, kaleido, shards, sky, orbit },
  };
}
