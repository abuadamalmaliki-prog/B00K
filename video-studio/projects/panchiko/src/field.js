/*
 * field.js — "nowhere on earth": rolling green land, wind grass, blue sky (from the engine lead's prototype).
 *   const field = createField({ renderer }); field.update(t, camera); renderer.render(field.scene, camera)
 * One baked tileable noise texture (GPU, once) drives clouds, gusts and ground variation.
 * Grass: instanced 9-vertex blades, log-distributed in a view sector (constant screen density),
 * wind in the vertex shader. Terrain: warped grid (dense near camera), aerial-perspective haze.
 */
import * as THREE from 'three';
import { rng, smooth } from './eng.js';

export function terrainHeight(x, z) {
  const d = Math.hypot(x, z);
  let h = 1.6 * Math.sin(x * 0.018 + 0.5) * Math.cos(z * 0.021 - 0.3) + 0.9 * Math.sin((x + z) * 0.037 + 1.1)
    + 0.3 * Math.sin(x * 0.09 - z * 0.07 + 2.0) * Math.cos(z * 0.083);
  h *= 0.35 + 0.65 * smooth(15, 120, d);
  const a = Math.atan2(x, -z);
  h += 9 * smooth(60, 260, d) * Math.sin(x * 0.011 + 0.4) * Math.sin(z * 0.009 + 1.3);            // mid rolling hills
  h += 95 * smooth(500, 1800, d) * (0.5 + 0.5 * Math.sin(a * 2.3 + 0.7)) * (0.7 + 0.3 * Math.sin(a * 5.1 + 2.0));  // far ridges
  return h;
}

const SKY_GLSL = /* glsl */`
  uniform vec3 uSun; uniform sampler2D tNoise; uniform float uTime;
  vec3 skyBase(vec3 d) {
    float y = max(d.y, 0.0);
    vec3 col = mix(vec3(0.56, 0.72, 0.92), vec3(0.09, 0.26, 0.68), pow(y, 0.5));
    float sd = max(dot(d, uSun), 0.0);
    col += vec3(1.0, 0.86, 0.66) * (pow(sd, 5.0) * 0.22 + pow(sd, 48.0) * 0.5);
    return col;
  }
  vec3 haze(vec3 d) {                     // colour of distant air in direction d
    vec3 h = vec3(0.60, 0.74, 0.90);
    float s = max(dot(normalize(vec3(d.x, 0.0, d.z)), normalize(vec3(uSun.x, 0.0, uSun.z))), 0.0);
    return h + vec3(0.30, 0.22, 0.10) * pow(s, 6.0);
  }
  vec3 aerial(vec3 col, vec3 P) {
    vec3 V = P - cameraPosition; float dist = length(V);
    float f = 1.0 - exp(-dist * 0.0024);
    f *= 0.55 + 0.45 * exp(-max(P.y, 0.0) * 0.02);
    return mix(col, haze(V / dist), f);
  }`;

export function createField({ renderer, width = 1080, height = 1350, blades = 60000, mergedGrass = true } = {}) {
  const text = false;                                    // the film's 3D text lives in index.html
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(58, width / height, 0.05, 6000);
  const R = rng(23);
  const sun = new THREE.Vector3(0.55, 0.62, -0.56).normalize();
  const waits = [];

  // ---- bake a tileable noise texture once (R: cumulus fbm, G: large blotches, B: fine, A: mid) ----
  const noiseRT = new THREE.WebGLRenderTarget(512, 512, { generateMipmaps: true, minFilter: THREE.LinearMipmapNearestFilter,
    magFilter: THREE.LinearFilter, wrapS: THREE.RepeatWrapping, wrapT: THREE.RepeatWrapping, depthBuffer: false });
  {
    const m = new THREE.ShaderMaterial({
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
      fragmentShader: /* glsl */`
        varying vec2 vUv;
        float h(vec2 p, float per) { p = mod(p, per); return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float vn(vec2 p, float per) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
          return mix(mix(h(i, per), h(i + vec2(1, 0), per), f.x), mix(h(i + vec2(0, 1), per), h(i + vec2(1, 1), per), f.x), f.y); }
        float fbm(vec2 p, float per, int oct) { float a = 0.5, s = 0.0, n = 0.0;
          for (int i = 0; i < 7; i++) { if (i >= oct) break; s += a * vn(p, per); n += a; p *= 2.0; per *= 2.0; a *= 0.5; } return s / n; }
        void main() {
          vec2 p = vUv;
          float r = fbm(p * 6.0 + vec2(fbm(p * 3.0, 3.0, 3) * 1.5), 6.0, 7);
          gl_FragColor = vec4(r, fbm(p * 3.0, 3.0, 3), fbm(p * 64.0, 64.0, 2), fbm(p * 16.0, 16.0, 4));
        }`,
      depthTest: false, depthWrite: false,
    });
    const q = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), m);
    renderer.setRenderTarget(noiseRT); renderer.render(q, new THREE.Camera()); renderer.setRenderTarget(null);
  }
  const tNoise = noiseRT.texture;
  const common = { uSun: { value: sun }, tNoise: { value: tNoise }, uTime: { value: 0 } };

  // ---- sky dome (drawn last, depth-tested → only visible pixels shade) -------------------
  const sky = new THREE.Mesh(new THREE.SphereGeometry(5000, 48, 24), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, uniforms: common,
    vertexShader: 'varying vec3 vD; void main(){ vD = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: /* glsl */`${SKY_GLSL}
      varying vec3 vD;
      void main() {
        vec3 d = normalize(vD);
        vec3 col = skyBase(d);
        if (d.y > 0.0) {
          vec2 p = d.xz / (d.y + 0.06) * 0.22 + vec2(0.0035, 0.0012) * uTime;
          float n = texture2D(tNoise, p).r;
          float dens = smoothstep(0.50, 0.72, n);
          float toward = texture2D(tNoise, p + normalize(uSun.xz) * 0.012).r;
          float lit = clamp(0.62 + (n - toward) * 7.0, 0.0, 1.0);
          vec3 cl = mix(vec3(0.60, 0.66, 0.78), vec3(1.30, 1.26, 1.18), lit);
          cl += vec3(0.5, 0.42, 0.3) * pow(max(dot(d, uSun), 0.0), 8.0) * (1.0 - dens) ; // silver lining
          float fade = smoothstep(0.0, 0.18, d.y);
          col = mix(col, mix(haze(d), cl, fade), dens * (0.35 + 0.6 * fade));
        } else col = haze(d);
        col += vec3(30.0) * smoothstep(0.99955, 0.9998, dot(d, uSun));
        gl_FragColor = vec4(col, 1.0);
      }`,
  }));
  sky.renderOrder = 10; sky.frustumCulled = false;
  scene.add(sky);

  // ---- terrain: warped grid, dense near the camera -----------------------------------------
  const N = 300, RAD = 3000;
  const tg = new THREE.PlaneGeometry(2, 2, N, N); tg.rotateX(-Math.PI / 2);
  const tp = tg.attributes.position;
  for (let i = 0; i < tp.count; i++) {
    const u = tp.getX(i), v = tp.getZ(i);
    const x = Math.sign(u) * u * u * RAD, z = Math.sign(v) * v * v * RAD;
    tp.setXYZ(i, x, terrainHeight(x, z), z);
  }
  tg.computeVertexNormals();
  const terrain = new THREE.Mesh(tg, new THREE.ShaderMaterial({
    uniforms: common,
    vertexShader: 'varying vec3 vW; varying vec3 vN; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vN = normal; gl_Position = projectionMatrix * viewMatrix * w; }',
    fragmentShader: /* glsl */`${SKY_GLSL}
      varying vec3 vW; varying vec3 vN;
      void main() {
        vec3 N = normalize(vN);
        float big = texture2D(tNoise, vW.xz * 0.0021).g, mid = texture2D(tNoise, vW.xz * 0.013).a, fine = texture2D(tNoise, vW.xz * 0.21).b;
        vec3 alb = mix(vec3(0.09, 0.19, 0.035), vec3(0.22, 0.30, 0.07), smoothstep(0.3, 0.75, big * 0.7 + mid * 0.3));
        alb *= 0.8 + 0.4 * fine;
        float dist = length(vW - cameraPosition);
        alb *= mix(0.35, 1.0, smoothstep(6.0, 34.0, dist));   // under the grass layer near camera
        vec3 lit = vec3(2.9, 2.7, 2.35) * max(dot(N, uSun), 0.0) + vec3(0.30, 0.42, 0.62) * (0.55 + 0.45 * N.y);
        gl_FragColor = vec4(aerial(alb * lit, vW), 1.0);
      }`,
  }));
  terrain.renderOrder = 5;
  scene.add(terrain);

  // ---- grass blades ---------------------------------------------------------------------------
  const SEG = 3;
  const bg = new THREE.BufferGeometry();
  { const pos = [], idx = [];
    for (let i = 0; i < SEG; i++) { const v = i / SEG; pos.push(-0.5, v, 0, 0.5, v, 0); }
    pos.push(0, 1, 0);
    for (let i = 0; i < SEG - 1; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    const a = (SEG - 1) * 2; idx.push(a, a + 1, SEG * 2);
    bg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); bg.setIndex(idx); }
  const ib = new THREE.InstancedBufferGeometry().copy(bg);
  const base = new Float32Array(blades * 4), shape = new Float32Array(blades * 4);
  const RMIN = 0.7, RMAX = 32, HALF = 0.5;
  const rs = [];
  for (let i = 0; i < blades; i++) rs.push(RMIN * Math.pow(RMAX / RMIN, R()));
  rs.sort((a, b) => a - b);                                    // front-to-back
  for (let i = 0; i < blades; i++) {
    const r = rs[i], th = (R() * 2 - 1) * HALF + (R() - 0.5) * 0.05;
    const x = Math.sin(th) * r, z = -Math.cos(th) * r;
    base.set([x, terrainHeight(x, z), z, R() * Math.PI], i * 4);
    const clump = 0.5 + 0.5 * Math.sin(x * 1.7 + Math.sin(z * 0.9) * 2.0) * Math.sin(z * 1.3 + Math.sin(x * 0.6) * 1.5);
    const tall = ((0.16 + 0.34 * Math.pow(R(), 1.6)) * (0.55 + 0.8 * clump) + (R() < 0.04 ? 0.35 : 0)) * (1 - 0.85 * smooth(RMAX * 0.55, RMAX, r));
    shape.set([tall, (0.011 + R() * 0.009) * (1 + r * 0.05), (R() - 0.5) * 0.6, R()], i * 4);
  }
  ib.setAttribute('aBase', new THREE.InstancedBufferAttribute(base, 4));
  ib.setAttribute('aShape', new THREE.InstancedBufferAttribute(shape, 4));
  ib.instanceCount = blades;
  let grassGeo = ib;
  if (mergedGrass) {
    // SwiftShader pays ~10 µs per instance: bake all blades into ONE plain geometry instead.
    const nv = bg.attributes.position.count, bi = bg.index.array, ni = bi.length;
    const P = new Float32Array(blades * nv * 3), B = new Float32Array(blades * nv * 4), S = new Float32Array(blades * nv * 4);
    const I = new Uint32Array(blades * ni);
    for (let i = 0; i < blades; i++) {
      P.set(bg.attributes.position.array, i * nv * 3);
      for (let k = 0; k < nv; k++) { B.set(base.subarray(i * 4, i * 4 + 4), (i * nv + k) * 4); S.set(shape.subarray(i * 4, i * 4 + 4), (i * nv + k) * 4); }
      for (let k = 0; k < ni; k++) I[i * ni + k] = bi[k] + i * nv;
    }
    grassGeo = new THREE.BufferGeometry();
    grassGeo.setAttribute('position', new THREE.BufferAttribute(P, 3));
    grassGeo.setAttribute('aBase', new THREE.BufferAttribute(B, 4));
    grassGeo.setAttribute('aShape', new THREE.BufferAttribute(S, 4));
    grassGeo.setIndex(new THREE.BufferAttribute(I, 1));
  }
  const grass = new THREE.Mesh(grassGeo, new THREE.ShaderMaterial({
    side: THREE.DoubleSide, uniforms: { ...common, uWind: { value: new THREE.Vector2(0.8, -0.6).normalize() } },
    vertexShader: /* glsl */`${SKY_GLSL}
      uniform vec2 uWind;
      attribute vec4 aBase, aShape;
      varying vec3 vCol; varying vec3 vW;
      void main() {
        float v = position.y, side = position.x;
        float hgt = aShape.x, wid = aShape.y * (1.0 - 0.8 * v * v), seed = aShape.w;
        vec2 wp = aBase.xz;
        float gust = texture2D(tNoise, wp * 0.011 - uWind * uTime * 0.045).g;
        float sway = sin(uTime * 2.3 + dot(wp, uWind) * 0.9 + seed * 6.28) * 0.5 + sin(uTime * 4.1 + seed * 19.0) * 0.18;
        float bend = aShape.z * 0.6 + (smoothstep(0.35, 0.8, gust) * 0.9 + 0.25 + sway * 0.28);
        float yaw = aBase.w;
        vec3 across = vec3(cos(yaw), 0.0, sin(yaw));
        vec3 wdir = vec3(uWind.x, 0.0, uWind.y);
        float b = bend * v;
        vec3 P = aBase.xyz + across * side * wid + wdir * hgt * 0.55 * bend * v * v + vec3(0.0, hgt * v * (1.0 - 0.22 * b * b), 0.0);
        vec3 tng = normalize(wdir * 1.1 * bend * v + vec3(0.0, 1.0, 0.0));
        vec3 N = normalize(cross(across, tng));
        vec3 V = normalize(cameraPosition - P);
        N = faceforward(N, -V, N);
        N = normalize(mix(N, vec3(0.0, 1.0, 0.0), 0.35));
        // colour: dark root → sunlit tip, per-blade hue, a few dry blades
        float dry = step(0.92, fract(seed * 7.13));
        float patchN = texture2D(tNoise, wp * 0.018).g;
        vec3 tip = mix(vec3(0.16, 0.33, 0.05), vec3(0.36, 0.45, 0.10), clamp(patchN * 1.4 - 0.2 + (fract(seed * 3.7) - 0.5) * 0.35, 0.0, 1.0));
        tip = mix(tip, vec3(0.46, 0.42, 0.18), dry);
        vec3 alb = mix(vec3(0.025, 0.06, 0.015), tip, smoothstep(0.0, 0.9, v));
        float ao = mix(0.28, 1.0, pow(v, 0.8));
        float sunD = max(dot(N, uSun), 0.0) * 0.75 + 0.25;
        float trans = pow(max(dot(-V, uSun), 0.0), 3.0) * 0.9 * v;
        vec3 lit = vec3(2.9, 2.7, 2.35) * (sunD * ao + trans) + vec3(0.30, 0.42, 0.62) * 0.8 * ao;
        vCol = aerial(alb * lit, P);   // haze per vertex: blades are tiny, saves a full-res fragment cost
        vW = P;
        gl_Position = projectionMatrix * viewMatrix * vec4(P, 1.0);
      }`,
    fragmentShader: /* glsl */`${SKY_GLSL}
      varying vec3 vCol; varying vec3 vW;
      void main() { gl_FragColor = vec4(vCol, 1.0); }`,
  }));
  grass.frustumCulled = false; grass.renderOrder = 0;
  scene.add(grass);

  // ---- 3D text (troika SDF) -----------------------------------------------------------------
  let label = null;
  if (text) {
    waits.push(import('troika-three-text').then(({ Text }) => new Promise((res) => {
      label = new Text();
      label.text = 'nowhere on earth';
      label.font = 'https://cdn.jsdelivr.net/npm/@fontsource/inter@5.1.0/files/inter-latin-300-normal.woff';
      label.fontSize = 4.2; label.letterSpacing = 0.08; label.anchorX = 'center'; label.anchorY = 'middle';
      label.color = 0xffffff; label.material.toneMapped = false; label.material.fog = false;
      label.position.set(-2, 13, -70); label.renderOrder = 8;
      label.sync(res);
      scene.add(label);
    })));
  }

  return {
    scene, sun, ready: Promise.all(waits), grass, terrain, sky,
    /** Advance wind and clouds to t and keep the sky dome centred on the camera. */
    update(t, cam) {
      common.uTime.value = t;
      sky.position.copy(cam.position); sky.updateMatrixWorld();
    },
  };
}
