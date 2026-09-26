/*
 * lib/footage.js — the flat-footage side of a Three.js composition.
 *
 * One shader for every clip (crop, five looks, contrast-adaptive sharpening,
 * prism split, flash / dip, kaleidoscope, iris), crops and screen layouts that
 * keep 1280×720 sources at or below 1× where possible, beat-aware shot timing
 * (speed, stutter), and the short transitions into a segment. Segments and
 * shots use the plan.js vocabulary (see projects/reze2/CONTEXT.md).
 *
 * It imports 'three', so the page needs the usual import map:
 *
 *   <script type="importmap">
 *     { "imports": { "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js" } }
 *   </script>
 *
 * The quickest way in is the ready-made layer:
 *
 *   import { createFootageLayer, footageEntries } from '../../lib/footage.js';
 *   Studio.setup({ ..., footage: footageEntries({ clean: 'media/clean.mp4', church: 'media/church.mp4' }) });
 *   const layer = createFootageLayer(W, H);
 *   Studio.onFrame(async (t) => { await layer.render(renderer, segment, t); });
 *
 * Colour: the shader works on the footage's display (sRGB) values and hands
 * three.js linear light, so it looks the same drawn straight to the canvas or
 * through an EffectComposer (whose OutputPass also applies the renderer's tone
 * mapping — keep that in mind for footage inside 3D scenes).
 */
import * as THREE from 'three';

/** The song's beat (173 BPM). */
export const BEAT = 0.3468;

/** Look names in plan.js → the shader's `look` uniform. */
export const LOOKS = { natural: 0, ice: 1, chrome: 2, mono: 3, invert: 4 };

/** The user's palette: white, black, light blue, light purple and an electric blue accent. */
export const PALETTE = { white: 0xffffff, black: 0x000000, ice: 0xbfe3ff, lilac: 0xcfc3ff, electric: 0x2f6bff };

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// ---- the shader -----------------------------------------------------------------

const vertexShader = `
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }`;

const fragmentShader = `
  uniform sampler2D map;
  uniform vec4 rect;      // crop inside the texture: uv offset (xy) and size (zw)
  uniform vec2 texel;     // 1 / texture size in pixels
  uniform float aspect;   // width / height of the quad on screen
  uniform float look, amount, sharpen, prism, flash, dip, kaleido, spin, iris, opacity;
  varying vec2 vUv;

  const vec3 ICE = vec3(.749, .890, 1.);        // #BFE3FF
  const vec3 LILAC = vec3(.812, .765, 1.);      // #CFC3FF
  const vec3 ELECTRIC = vec3(.184, .420, 1.);   // #2F6BFF
  const vec3 INK = vec3(.024, .055, .30);       // deep electric blue, for the negative

  float luma(vec3 c) { return dot(c, vec3(.2126, .7152, .0722)); }

  // Contrast-adaptive sharpening (after AMD's CAS): a 5-tap cross whose weight
  // backs off where the neighbourhood already has contrast, so edges get crisp
  // without halos and flat anime colour fields stay flat.
  vec3 sharpened(vec2 uv) {
    vec3 c = texture2D(map, uv).rgb;
    if (sharpen <= 0.) return c;
    vec3 n = texture2D(map, uv + vec2(0., texel.y)).rgb;
    vec3 s = texture2D(map, uv - vec2(0., texel.y)).rgb;
    vec3 e = texture2D(map, uv + vec2(texel.x, 0.)).rgb;
    vec3 w = texture2D(map, uv - vec2(texel.x, 0.)).rgb;
    vec3 mn = min(c, min(min(n, s), min(e, w)));
    vec3 mx = max(c, max(max(n, s), max(e, w)));
    vec3 amp = sqrt(clamp(min(mn, 1. - mx) / max(mx, 1e-4), 0., 1.));
    vec3 wt = -amp / mix(8., 5., clamp(sharpen, 0., 1.));
    return clamp((c + (n + s + e + w) * wt) / (1. + 4. * wt), 0., 1.);
  }

  // Mirror the quad into kaleido wedges around its centre; spin turns the tube.
  vec2 fold(vec2 uv) {
    if (kaleido < 1.) return uv;
    vec2 p = (uv - .5) * vec2(aspect, 1.);
    float seg = 6.2831853 / kaleido;
    float a = abs(mod(atan(p.y, p.x), seg) - seg * .5) + spin;
    vec2 q = length(p) * vec2(cos(a), sin(a)) / vec2(aspect, 1.) + .5;
    return 1. - abs(1. - mod(q, 2.));   // mirrored wrap: never leaves the crop
  }

  vec3 grade(vec3 c) {
    float l = luma(c);
    if (look < .5) {
      // natural — the source, a touch cleaner: gentle S-curve, whites nudged cool.
      vec3 x = mix(c, c * c * (3. - 2. * c), .12);
      return x * vec3(.985, 1., 1.02);
    }
    if (look < 1.5) {
      // ice — airy and high-key: half the colour, open mids, blue shadows lifting
      // into light-blue highlights over an ink-navy floor. Luminance order is kept,
      // so faces stay readable.
      vec3 x = pow(mix(vec3(l), c, .5), vec3(.8));
      x *= mix(vec3(.80, .88, 1.08), vec3(.97, 1., 1.03), smoothstep(.1, .9, luma(x)));
      x = mix(x, x * ICE / .87, .25 * smoothstep(.45, .8, luma(x)));
      return mix(vec3(.03, .05, .12), vec3(1.), x);
    }
    if (look < 2.5) {
      // chrome — cool silver: metallic contrast from blue-black to silver, a lilac
      // sheen in the mids, and only the very brightest tones blown to specular
      // white — light skin (luma ≈ .8) stays silver with its detail. A whisper of
      // the original colour keeps skin from going dead grey.
      float y = mix(l, l * l * (3. - 2. * l), .6);
      vec3 x = mix(vec3(.015, .02, .045), vec3(.86, .895, .97), y);
      x = mix(x, x * LILAC / .79, .35 * smoothstep(.3, .55, y) * (1. - smoothstep(.55, .8, y)));
      x = mix(x, vec3(1.), smoothstep(.9, 1., y));
      return mix(x, c, .07);
    }
    if (look < 3.5) {
      // mono — black and white through a light red filter (flattering on skin),
      // a soft S-curve, and the faintest cool in the shadows.
      float y = dot(c, vec3(.36, .54, .10));
      y = mix(y, y * y * (3. - 2. * y), .35);
      return vec3(y) * mix(vec3(.975, .985, 1.02), vec3(1.), y);
    }
    // invert — a blueprint negative: the source's darks become paper white, its
    // lights electric-blue ink, with lilac between. Every stop is a clean blue,
    // never a grey mix, and brightness stays monotonic.
    float y = 1. - smoothstep(.02, .98, l);
    vec3 x = mix(INK, ELECTRIC, smoothstep(0., .45, y));
    x = mix(x, LILAC, smoothstep(.4, .8, y));
    return mix(x, vec3(1.), smoothstep(.78, 1., y));
  }

  vec3 toLinear(vec3 c) { return mix(c / 12.92, pow((c + .055) / 1.055, vec3(2.4)), step(.04045, c)); }

  void main() {
    vec2 st = fold(vUv);
    vec2 lo = rect.xy + texel, hi = rect.xy + rect.zw - texel;
    vec2 uv = clamp(rect.xy + st * rect.zw, lo, hi);
    vec3 c = sharpened(uv);
    if (prism > 0.) {
      // Prismatic split: red and blue pulled apart, more toward the edges, like dispersion in glass.
      vec2 off = prism * (vec2(.012, 0.) + (st - .5) * .05) * rect.zw;
      c.r = texture2D(map, clamp(uv + off, lo, hi)).r;
      c.b = texture2D(map, clamp(uv - off, lo, hi)).b;
    }
    c = mix(c, clamp(grade(c), 0., 1.), amount);
    // Flash: an over-exposure — highlights blow out first, then everything goes white.
    c = mix(1. - pow(1. - c, vec3(1. + 5. * flash)), vec3(1.), flash * flash);
    c *= 1. - dip;
    if (iris < 1.) {
      // Iris: a circle opening from the centre, edged with a hairline of light blue.
      float d = length((vUv - .5) * vec2(aspect, 1.)) / length(vec2(aspect, 1.) * .5);
      float px = 1.5 * texel.y / rect.w;
      float r = iris * 1.02;
      c *= smoothstep(r + px, r - px, d);
      c = mix(c, ICE, (1. - smoothstep(0., px * 2., abs(d - r))) * (1. - iris));
    }
    gl_FragColor = vec4(toLinear(c), opacity);
    #include <colorspace_fragment>
  }`;

/**
 * The footage ShaderMaterial. Uniforms (all plain numbers unless noted):
 *   map (texture), rect (Vector4 crop — use fitRect), texel (Vector2, 1/texture px),
 *   aspect (quad w/h), look (0 natural, 1 ice, 2 chrome, 3 mono, 4 invert),
 *   amount (look strength 0–1), sharpen (0–1), prism (0–1 RGB split),
 *   flash (0–1 to white), dip (0–1 to black), kaleido (fold count, 0 = off),
 *   spin (radians, turns the kaleidoscope), iris (0 closed … 1 open), opacity.
 * `params` go to THREE.ShaderMaterial (e.g. { transparent: true } to fade with opacity).
 */
export function createFootageMaterial(params = {}) {
  return new THREE.ShaderMaterial({
    uniforms: {
      map: { value: null }, rect: { value: new THREE.Vector4(0, 0, 1, 1) }, texel: { value: new THREE.Vector2(1 / 1280, 1 / 720) },
      aspect: { value: 16 / 9 }, look: { value: 0 }, amount: { value: 1 }, sharpen: { value: 0 }, prism: { value: 0 },
      flash: { value: 0 }, dip: { value: 0 }, kaleido: { value: 0 }, spin: { value: 0 }, iris: { value: 1 }, opacity: { value: 1 },
    },
    vertexShader,
    fragmentShader,
    toneMapped: false,
    ...params,
  });
}

/** Set several uniforms at once from { name: value } (e.g. the result of transitionIn). */
export function applyUniforms(mat, values) {
  for (const [k, v] of Object.entries(values)) if (mat.uniforms[k]) mat.uniforms[k].value = v;
  return mat;
}

// ---- framing ----------------------------------------------------------------------

/**
 * Usable vertical band of each source when a shot doesn't give one (flipY
 * texture coords, 0 = bottom): church has burned-in subtitles at the bottom and
 * credits / a title logo at the top; fireworks a dark box bottom-left.
 */
export const BANDS = { church: [0.13, 0.86], fireworks: [0.1, 1] };

const sourceKey = (src) => String(src || '').split('/').pop().replace(/\.\w+$/, '').replace(/#\d+$/, '');

/**
 * Crop (uv offset + size, as a Vector4 for the `rect` uniform) that fills
 * targetAspect from the source. Honours shot.band = [y0, y1] (the usable
 * vertical band, flipY texture coords: 0 = bottom; defaults from BANDS by
 * shot.src), shot.fx (horizontal focus 0–1), and optionally shot.fy (vertical
 * focus) and shot.zoom (≥ 1, crops tighter).
 */
export function fitRect(shot, targetAspect, sourceAspect = 16 / 9) {
  const [y0, y1] = shot.band || BANDS[sourceKey(shot.src)] || [0, 1];
  let h = y1 - y0;
  let w = (targetAspect * h) / sourceAspect;
  if (w > 1) { w = 1; h = sourceAspect / targetAspect; }
  const zoom = Math.max(1, shot.zoom ?? 1);
  w /= zoom; h /= zoom;
  const x = clamp((shot.fx ?? 0.5) - w / 2, 0, 1 - w);
  const y = clamp((shot.fy ?? (y0 + y1) / 2) - h / 2, y0, y1 - h);
  return new THREE.Vector4(x, y, w, h);
}

/**
 * Pixel rects { x, y, w, h } (top-left origin) for a layout on a W×H frame:
 *   full   — the whole frame (a 16:9 source is cover-cropped, ~1.9× at 1080×1350)
 *   strip  — one 16:9 strip, centred (1040×585 at 1080×1350: a downscale, crisp)
 *   stack2 — two 16:9 strips with a thin gap
 *   stack3 — three strips (≈2.5:1 crops) with thin gaps
 * Strips are `width` wide (default 1040 at W = 1080), centred horizontally, and
 * centred vertically above a `bottomSafe` band (default 80 px at H = 1350) kept
 * free for the watermark. 'kaleido' is 'full' (set the kaleido uniform); 'glass'
 * is a 3D layout — on flat footage it falls back to 'strip'.
 */
export function layout(name, W, H, opts = {}) {
  const { width = Math.round((W * 1040) / 1080), bottomSafe = Math.round((H * 80) / 1350), gap = Math.round(W / 135) } = opts;
  const x = Math.round((W - width) / 2);
  const room = H - bottomSafe;
  const n = { strip: 1, glass: 1, stack2: 2, stack3: 3 }[name];
  if (!n) return [{ x: 0, y: 0, w: W, h: H }];
  const h = Math.min(Math.round((width * 9) / 16), Math.floor((room - gap * (n + 1)) / n));
  const top = Math.round((room - n * h - (n - 1) * gap) / 2);
  return Array.from({ length: n }, (_, i) => ({ x, y: top + i * (h + gap), w: width, h }));
}

/** Put a PlaneGeometry(1, 1) mesh on a pixel rect, for an OrthographicCamera(0, W, H, 0). */
export function placeRect(mesh, rect, H) {
  mesh.position.set(rect.x + rect.w / 2, H - rect.y - rect.h / 2, 0);
  mesh.scale.set(rect.w, rect.h, 1);
  return mesh;
}

// ---- timing -----------------------------------------------------------------------

/**
 * Source time (seconds) to show for a shot of segment `seg` at timeline time t.
 * speed (shot's, else the segment's) scales playback; stutter N loops the first
 * N beats of the shot (0.5 → every half beat it jumps back to `from`); hold
 * freezes the shot that many seconds in.
 */
export function shotTime(seg, shot, t, beat = BEAT) {
  let local = Math.max(0, t - seg.start);
  const stutter = shot.stutter ?? seg.stutter ?? 0;
  if (stutter > 0) local %= stutter * beat;
  if (shot.hold != null) local = Math.min(local, shot.hold);
  return (shot.from ?? 0) + local * (shot.speed ?? seg.speed ?? 1);
}

// ---- textures ---------------------------------------------------------------------

const textures = new WeakMap();

/**
 * The THREE.Texture for a footage element (Studio.footage / footageAt). It is
 * re-uploaded only when the element shows a different frame — at 120 fps a
 * 30 fps clip changes every fourth frame, and each upload of a 1280×720 frame
 * costs real time in software WebGL.
 */
export function footageTexture(el) {
  let entry = textures.get(el);
  if (!entry) {
    const tex = new THREE.Texture(el);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;
    entry = { tex, key: null };
    textures.set(el, entry);
  }
  const video = el.tagName === 'VIDEO';
  const ready = video ? el.readyState >= 2 : el.complete && el.naturalWidth > 0;
  const key = video ? el.currentTime : el.getAttribute('src');
  if (ready && key !== entry.key) {
    entry.key = key;
    entry.tex.needsUpdate = true;
  }
  return entry.tex;
}

/** Width and height of the frame an element shows (0 × 0 before it has one). */
export function frameSize(el) {
  return el.tagName === 'VIDEO' ? [el.videoWidth, el.videoHeight] : [el.naturalWidth, el.naturalHeight];
}

/** Point a footage material at an element: texture, texel size and the crop for targetAspect. */
export function bindFootage(mat, el, shot, targetAspect) {
  const [w, h] = frameSize(el);
  const u = mat.uniforms;
  u.map.value = footageTexture(el);
  if (w && h) u.texel.value.set(1 / w, 1 / h);
  u.rect.value.copy(fitRect(shot, targetAspect, w && h ? w / h : 16 / 9));
  u.aspect.value = targetAspect;
  return mat;
}

// ---- transitions ------------------------------------------------------------------

/** How long each transition takes, in seconds (about half a beat). */
export const TRANSITION_DURATION = { flash: 0.14, prism: 0.18, iris: 0.2, shatter: 0.16 };

/**
 * Uniform values { flash, prism, dip, iris } for the transition into `seg`
 * (seg.in) at time t. They settle to neutral after the first ~0.14–0.2 s.
 *   flash   — starts white, the over-exposure drains out, highlights last
 *   prism   — an RGB split that closes up, with a breath of white
 *   iris    — a circle opening from the centre (black outside)
 *   cut     — nothing
 *   shatter — the 3D kit's; on flat footage it falls back to a prismatic white hit
 */
export function transitionIn(seg, t, dur) {
  const kind = seg.in || 'cut';
  const v = { flash: 0, prism: 0, dip: 0, iris: 1 };
  const k = clamp((t - seg.start) / (dur ?? TRANSITION_DURATION[kind] ?? 0.16), 0, 1);
  const r = 1 - k;
  if (k >= 1) return v;
  if (kind === 'flash') { v.flash = r * r; v.prism = 0.25 * r * r * r; }
  else if (kind === 'prism') { v.prism = Math.pow(r, 1.5); v.flash = 0.12 * r * r * r; }
  else if (kind === 'iris') v.iris = 1 - r * r * r;
  else if (kind === 'shatter') { v.prism = r; v.flash = 0.5 * r * r; }
  return v;
}

// ---- footage entries and a ready-made layer ------------------------------------------

/** Name of footage slot i of a source: 'clean', 'clean#2', 'clean#3'. */
export const slotName = (src, i) => (i ? `${src}#${i + 1}` : src);

/**
 * Studio.setup footage entries for footageAt(): each source as a manual clip,
 * declared `slots` times (clean, clean#2, clean#3) so a stacked layout can show
 * several moments of one source at once — render.mjs extracts it only once.
 * Give `from`/`duration` to extract less of a long source.
 *   footageEntries({ clean: 'media/clean.mp4', church: { src: 'media/church.mp4', duration: 84 } })
 */
export function footageEntries(sources, { slots = 3 } = {}) {
  const entries = {};
  for (const [name, spec] of Object.entries(sources)) {
    const s = typeof spec === 'string' ? { src: spec } : spec;
    for (let i = 0; i < slots; i++) entries[slotName(name, i)] = { from: 0, ...s, manual: true };
  }
  return entries;
}

/**
 * Flat footage for 'clip' segments: up to three quads in an orthographic scene,
 * laid out, cropped, graded, sharpened and transitioned straight from a plan.js
 * segment. layer.render(renderer, seg, t) clears to seg.bg and draws;
 * layer.update(seg, t, renderer) only prepares scene + camera, to draw yourself
 * over your own background (layer.background(seg) gives its colour).
 * Options: beat, layout ({ width, bottomSafe, gap } for layout()), background
 * (default black), name(shot, i) → Studio footage name (default shot.name or
 * slotName(shot.src, i)).
 *
 * Shot fields: src, from, fx, fy, zoom, band, look (wins over the segment's),
 *   speed, stutter, hold, sharpen.
 * Segment fields: start, layout, look, speed, stutter (applies to every shot,
 *   each looping its own window), in, folds (kaleido, default 6),
 *   bg ('white' | 'black' | a colour: the space around strips and stacks).
 * Fewer shots than strips repeat the shots.
 */
export function createFootageLayer(W, H, opts = {}) {
  const beat = opts.beat ?? BEAT;
  const background = (seg) => ({ white: PALETTE.white, black: PALETTE.black })[seg.bg] ?? seg.bg ?? opts.background ?? PALETTE.black;
  const name = opts.name || ((shot, i) => shot.name || slotName(shot.src, i));
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(0, W, H, 0, -1, 1);
  const quads = Array.from({ length: 3 }, () => {
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), createFootageMaterial());
    scene.add(mesh);
    return mesh;
  });

  async function update(seg, t, renderer) {
    const rects = layout(seg.layout || 'full', W, H, opts.layout);
    const shots = seg.shots || [];
    const hit = transitionIn(seg, t);
    const pixelRatio = renderer ? renderer.getPixelRatio() : 1;
    await Promise.all(quads.map(async (mesh, i) => {
      const rect = rects[i];
      const shot = shots.length ? shots[i % shots.length] : null;
      mesh.visible = !!(rect && shot);
      if (!mesh.visible) return;
      const el = await Studio.footageAt(name(shot, i), shotTime(seg, shot, t, beat));
      const mat = bindFootage(mesh.material, el, shot, rect.w / rect.h);
      const u = mat.uniforms;
      u.look.value = LOOKS[shot.look ?? seg.look ?? 'natural'] ?? 0;
      // Sharpen only what gets enlarged: none for a downscaled strip, up to 0.5 for a
      // full-frame crop (rect uniform is x, y, w, h — its .w is the crop's height).
      const [, th] = frameSize(el);
      const magnify = th ? (rect.h * pixelRatio) / (th * u.rect.value.w) : 1;
      u.sharpen.value = shot.sharpen ?? seg.sharpen ?? clamp((magnify - 1) * 0.6, 0, 0.5);
      u.kaleido.value = seg.layout === 'kaleido' ? seg.folds ?? 6 : 0;
      u.spin.value = (t - seg.start) * 0.6;
      applyUniforms(mat, hit);
      placeRect(mesh, rect, H);
    }));
  }

  return {
    scene, camera, quads, update, background,
    async render(renderer, seg, t) {
      await update(seg, t, renderer);
      renderer.setClearColor(background(seg));
      renderer.clear();
      renderer.render(scene, camera);
    },
  };
}
