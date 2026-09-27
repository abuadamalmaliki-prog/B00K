/*
 * eng.js — shared post pipeline and helpers for "Found" (from the engine lead's prototypes).
 * HDR linear render → low-res dual-filter bloom → ACES filmic + grade + vignette + grain.
 * Everything is a pure function of t (no clocks, seeded PRNG).
 */
import * as THREE from 'three';

export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const smooth = (a, b, x) => { const k = clamp((x - a) / (b - a), 0, 1); return k * k * (3 - 2 * k); };
export function rng(seed = 1) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

export function createRenderer(width, height) {
  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(devicePixelRatio);
  renderer.setSize(width, height);
  renderer.toneMapping = THREE.NoToneMapping;       // we tone-map in post
  document.getElementById('stage').prepend(renderer.domElement);
  return renderer;
}

const FS_VERT = /* glsl */`varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

/** Post pipeline. opts: { msaa, bloomDivs } */
export function createPost(renderer, width, height, opts = {}) {
  const { msaa = 0, bloomDivs = [4, 8, 16, 32], fxaa = true } = opts;
  const pr = renderer.getPixelRatio();
  const W = Math.round(width * pr), H = Math.round(height * pr);
  const rt = (w, h, o = {}) => new THREE.WebGLRenderTarget(w, h, {
    type: THREE.HalfFloatType, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false, ...o });
  const hdr = rt(W, H, { depthBuffer: true, samples: msaa });
  const blooms = bloomDivs.map((d) => rt(Math.ceil(W / d), Math.ceil(H / d)));
  const ldr = fxaa ? new THREE.WebGLRenderTarget(W, H, { minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false }) : null;

  const quadGeo = new THREE.BufferGeometry();
  quadGeo.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
  quadGeo.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
  const quad = new THREE.Mesh(quadGeo); quad.frustumCulled = false;
  const qScene = new THREE.Scene().add(quad), qCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const mat = (fs, u, extra = {}) => new THREE.ShaderMaterial({ vertexShader: FS_VERT, fragmentShader: fs, uniforms: u, depthTest: false, depthWrite: false, ...extra });
  const pass = (m, target) => { quad.material = m; renderer.setRenderTarget(target); renderer.render(qScene, qCam); };

  const pre = mat(/* glsl */`uniform sampler2D tIn; uniform vec2 tx; uniform float thr; varying vec2 vUv;
    void main(){ vec3 c = (texture2D(tIn,vUv+tx*vec2(-1,-1)).rgb+texture2D(tIn,vUv+tx*vec2(1,-1)).rgb+texture2D(tIn,vUv+tx*vec2(-1,1)).rgb+texture2D(tIn,vUv+tx*vec2(1,1)).rgb)*0.25;
      float m = max(max(c.r,c.g),c.b); gl_FragColor = vec4(c*(max(m-thr,0.0)/max(m,1e-4)),1.0); }`,
  { tIn: { value: null }, tx: { value: new THREE.Vector2() }, thr: { value: 1 } });
  const down = mat(/* glsl */`uniform sampler2D tIn; uniform vec2 tx; varying vec2 vUv;
    void main(){ vec3 s = texture2D(tIn,vUv).rgb*4.0 + texture2D(tIn,vUv+tx*vec2(-1,-1)).rgb+texture2D(tIn,vUv+tx*vec2(1,-1)).rgb+texture2D(tIn,vUv+tx*vec2(-1,1)).rgb+texture2D(tIn,vUv+tx*vec2(1,1)).rgb;
      gl_FragColor = vec4(s/8.0,1.0); }`, { tIn: { value: null }, tx: { value: new THREE.Vector2() } });
  const up = mat(/* glsl */`uniform sampler2D tIn; uniform vec2 tx; varying vec2 vUv;
    void main(){ vec3 s = texture2D(tIn,vUv+tx*vec2(-2,0)).rgb+texture2D(tIn,vUv+tx*vec2(2,0)).rgb+texture2D(tIn,vUv+tx*vec2(0,-2)).rgb+texture2D(tIn,vUv+tx*vec2(0,2)).rgb
      + 2.0*(texture2D(tIn,vUv+tx*vec2(-1,-1)).rgb+texture2D(tIn,vUv+tx*vec2(1,-1)).rgb+texture2D(tIn,vUv+tx*vec2(-1,1)).rgb+texture2D(tIn,vUv+tx*vec2(1,1)).rgb);
      gl_FragColor = vec4(s/12.0,1.0); }`, { tIn: { value: null }, tx: { value: new THREE.Vector2() } },
  { blending: THREE.AdditiveBlending, transparent: true });

  // ACES fitted (Hill) + lift/gain split-tone + vignette + CA + grain, then sRGB.
  const out = mat(/* glsl */`
    uniform sampler2D tIn, tBloom; uniform float uBloom, uExp, uVig, uGrain, uSeed, uAspect, uCA, uSat, uFade;
    uniform vec3 uShadowTint, uHighTint;
    varying vec2 vUv;
    const mat3 ACESIn = mat3(0.59719,0.07600,0.02840, 0.35458,0.90834,0.13383, 0.04823,0.01566,0.83777);
    const mat3 ACESOut = mat3(1.60475,-0.10208,-0.00327, -0.53108,1.10813,-0.07276, -0.07367,-0.00605,1.07602);
    vec3 RRTODT(vec3 v){ vec3 a = v*(v+0.0245786)-0.000090537; vec3 b = v*(0.983729*v+0.4329510)+0.238081; return a/b; }
    float hash(vec2 p){ vec3 p3 = fract(vec3(p.xyx)*0.1031); p3 += dot(p3,p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }
    vec3 toSRGB(vec3 c){ c = clamp(c,0.0,1.0); return mix(c*12.92, 1.055*pow(c,vec3(1.0/2.4))-0.055, step(0.0031308,c)); }
    void main(){
      vec2 q = vUv-0.5;
      #ifdef USE_CA
      vec2 o = q*uCA*0.004;
      vec3 c = vec3(texture2D(tIn,vUv+o).r, texture2D(tIn,vUv).g, texture2D(tIn,vUv-o).b);
      #else
      vec3 c = texture2D(tIn,vUv).rgb;
      #endif
      c += texture2D(tBloom,vUv).rgb*uBloom;
      c *= uExp;
      vec2 qa = q*vec2(uAspect,1.0);
      c *= 1.0 - uVig*smoothstep(0.15, 0.85, dot(qa,qa)*1.8);
      c = ACESOut*RRTODT(ACESIn*c);
      c = clamp(c,0.0,1.0);
      float l = dot(c, vec3(0.2126,0.7152,0.0722));
      c = mix(vec3(l), c, uSat);
      c += uShadowTint*(1.0-l)*(1.0-l)*0.06 + uHighTint*l*l*0.04;
      c = mix(c, vec3(0.0), uFade);
      c = toSRGB(c);
      ${fxaa ? '' : `float g = hash(gl_FragCoord.xy+uSeed*917.0)+hash(gl_FragCoord.xy*1.37+uSeed*331.0)-1.0;
      c += g*(0.6/255.0 + uGrain*(0.3+0.7*(1.0-abs(l*2.0-1.0))));`}
      gl_FragColor = vec4(c,1.0);
    }`, {
    tIn: { value: null }, tBloom: { value: null }, uBloom: { value: 0.12 }, uExp: { value: 1 }, uVig: { value: 0.35 },
    uGrain: { value: 0.025 }, uSeed: { value: 0 }, uAspect: { value: width / height }, uCA: { value: 0.6 }, uSat: { value: 1 },
    uFade: { value: 0 }, uShadowTint: { value: new THREE.Vector3(-0.2, 0.05, 0.25) }, uHighTint: { value: new THREE.Vector3(0.2, 0.08, -0.15) },
  });

  const fx = mat(/* glsl */`
    uniform sampler2D tIn; uniform vec2 tx; uniform float uGrain, uSeed; varying vec2 vUv;
    float lum(vec3 c){ return dot(c, vec3(0.299,0.587,0.114)); }
    float hash(vec2 p){ vec3 p3 = fract(vec3(p.xyx)*0.1031); p3 += dot(p3,p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }
    void main(){
      vec3 M = texture2D(tIn,vUv).rgb; float lM = lum(M);
      float lNW = lum(texture2D(tIn,vUv+vec2(-1.,-1.)*tx).rgb), lNE = lum(texture2D(tIn,vUv+vec2(1.,-1.)*tx).rgb);
      float lSW = lum(texture2D(tIn,vUv+vec2(-1.,1.)*tx).rgb), lSE = lum(texture2D(tIn,vUv+vec2(1.,1.)*tx).rgb);
      float lMin = min(lM,min(min(lNW,lNE),min(lSW,lSE))), lMax = max(lM,max(max(lNW,lNE),max(lSW,lSE)));
      vec3 c = M;
      if (lMax - lMin > max(0.03, lMax*0.1)) {
        vec2 dir = vec2(-((lNW+lNE)-(lSW+lSE)), ((lNW+lSW)-(lNE+lSE)));
        float red = max((lNW+lNE+lSW+lSE)*0.03125, 1.0/128.0);
        dir = clamp(dir/(min(abs(dir.x),abs(dir.y))+red), -8.0, 8.0)*tx;
        vec3 A = 0.5*(texture2D(tIn,vUv-dir/6.0).rgb + texture2D(tIn,vUv+dir/6.0).rgb);
        vec3 B = A*0.5 + 0.25*(texture2D(tIn,vUv-dir*0.5).rgb + texture2D(tIn,vUv+dir*0.5).rgb);
        float lB = lum(B);
        c = (lB<lMin||lB>lMax) ? A : B;
      }
      float l = lum(c);
      float g = hash(gl_FragCoord.xy+uSeed*917.0)+hash(gl_FragCoord.xy*1.37+uSeed*331.0)-1.0;
      c += g*(0.6/255.0 + uGrain*(0.3+0.7*(1.0-abs(l*2.0-1.0))));
      gl_FragColor = vec4(c,1.0);
    }`, { tIn: { value: null }, tx: { value: new THREE.Vector2(1 / W, 1 / H) }, uGrain: { value: 0.025 }, uSeed: { value: 0 } });

  const outCA = out.clone(); outCA.defines = { USE_CA: '' };
  const blackTex = new THREE.DataTexture(new Uint16Array([0, 0, 0, 0]), 1, 1, THREE.RGBAFormat, THREE.HalfFloatType); blackTex.needsUpdate = true;

  return {
    hdr, W, H, out, outCA,
    render(scene, camera, p = {}, t = 0) {
      renderer.setRenderTarget(hdr);
      renderer.render(scene, camera);
      const prevAuto = renderer.autoClear;
      renderer.autoClear = false;
      pre.uniforms.tIn.value = hdr.texture; pre.uniforms.tx.value.set(1 / W, 1 / H); pre.uniforms.thr.value = p.threshold ?? 1.0;
      const doBloom = !p.noBloom;
      if (doBloom) pass(pre, blooms[0]);
      if (doBloom) for (let i = 1; i < blooms.length; i++) {
        down.uniforms.tIn.value = blooms[i - 1].texture; down.uniforms.tx.value.set(1 / blooms[i - 1].width, 1 / blooms[i - 1].height);
        pass(down, blooms[i]);
      }
      if (doBloom) for (let i = blooms.length - 1; i > 0; i--) {
        up.uniforms.tIn.value = blooms[i].texture; up.uniforms.tx.value.set(0.5 / blooms[i].width, 0.5 / blooms[i].height);
        pass(up, blooms[i - 1]);
      }
      const om = (p.ca ?? 0.6) > 0 ? outCA : out;
      const u = om.uniforms;
      u.tIn.value = hdr.texture; u.tBloom.value = doBloom ? blooms[0].texture : blackTex;
      for (const k of ['bloom', 'exp', 'vig', 'grain', 'ca', 'sat', 'fade']) {
        const key = 'u' + (k === 'exp' ? 'Exp' : k === 'ca' ? 'CA' : k[0].toUpperCase() + k.slice(1));
        if (p[k] !== undefined) u[key].value = p[k];
      }
      u.uSeed.value = (Math.floor(t * 240) % 997) / 997;
      if (ldr) {
        pass(om, ldr);
        fx.uniforms.tIn.value = ldr.texture; fx.uniforms.uGrain.value = u.uGrain.value; fx.uniforms.uSeed.value = u.uSeed.value;
        pass(fx, null);
      } else pass(om, null);
      renderer.autoClear = prevAuto;
    },
  };
}

/** Deterministic first-person head motion. walk = steps per second (0 = standing). */
export function head(t, { amp = 1, walk = 0, seed = 0 } = {}) {
  const TAU = Math.PI * 2, s = seed * 1.7;
  const n = (f, p) => Math.sin(TAU * f * t + p + s);
  let y = 0.006 * n(0.23, 0.4) * amp;                     // breathing
  let yaw = amp * (0.010 * n(0.071, 1.0) + 0.005 * n(0.19, 2.3) + 0.0015 * n(0.53, 0.2));
  let pitch = amp * (0.007 * n(0.093, 0.7) + 0.003 * n(0.27, 1.9) + 0.001 * n(0.71, 3.1));
  let roll = amp * (0.004 * n(0.061, 2.2) + 0.0015 * n(0.33, 0.5));
  let x = 0;
  if (walk > 0) {
    const ph = Math.PI * walk * t;                         // one bob per step
    y += 0.022 * (Math.abs(Math.sin(ph)) - 0.64);
    x += 0.012 * Math.sin(ph);
    roll += 0.006 * Math.sin(ph);
    pitch += 0.004 * Math.sin(2 * ph + 0.6);
  }
  return { x, y, yaw, pitch, roll };
}

/** Place camera at pos looking along (yaw, pitch) + head motion. */
export function placeCamera(camera, pos, yaw, pitch, h) {
  camera.position.set(pos[0] + h.x * Math.cos(yaw), pos[1] + h.y, pos[2] - h.x * Math.sin(yaw));
  camera.rotation.order = 'YXZ';
  camera.rotation.set(pitch + h.pitch, yaw + h.yaw, h.roll);
  camera.updateMatrixWorld();
}

/** Canvas → sRGB texture with mipmaps + anisotropy. */
export function canvasTexture(renderer, canvas, { repeat = false } = {}) {
  const t = new THREE.CanvasTexture(canvas);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}
