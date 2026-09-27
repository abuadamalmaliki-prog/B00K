/*
 * store.js — LANTERNFISH · MUSIC & FILM: the wet street outside and the shop inside.
 *
 * Built to the world coordinates in camera.js: shopfront glazing on z = 0 (street z > 0,
 * interior z < 0), door opening x ∈ [-0.5, 0.5] hinged on the left jamb and swinging
 * inward, the main display window x -4.2…-0.7, the aisle kept clear down x ≈ 0.1, and
 * the PRE-OWNED bin at BIN. All names and artwork are invented (copy.js); nothing
 * reproduces a real brand.
 *
 *   import { createStore } from './store.js';
 *   const store = await createStore({ renderer });
 *   scene.add(store.root);
 *   Studio.onFrame((t) => store.update(t, { door: doorAt(t) }));
 *
 *   store.anchors: { door, doorHinge, bin, binSign, counter, window }
 *   store.envs:    { street, shop }  PMREM textures (also used by body.js)
 *
 * Cheap on SwiftShader: static props are merged into a handful of meshes, text and
 * artwork are drawn once into canvases, the light is a PMREM environment per side
 * plus two point lights; wet reflections on the street are additive light streaks.
 */
import * as THREE from 'three';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import copy from './copy.js';
import { DOOR, WINDOW, BIN } from './camera.js';
import { rng } from './eng.js';

const ASSETS = new URL('../assets/', import.meta.url).href;
const PI = Math.PI;

// ---- canvas artwork ----------------------------------------------------------------------

function canvas(w, h, draw) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  return c;
}

function texture(c, { repeat = 0, srgb = true } = {}) {
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 1;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat, repeat); }
  return t;
}

function fitText(g, text, maxW, size, font) {
  let s = size;
  do { g.font = font.replace('%', s); s -= 2; } while (g.measureText(text).width > maxW && s > 8);
}

const PALETTES = [
  ['#1d2a44', '#e8d9b0'], ['#6b1f2a', '#f1e6d2'], ['#20352b', '#d7e8c9'], ['#e2c044', '#1b1b1b'],
  ['#2b2b2b', '#f25c3c'], ['#d9dde3', '#23324a'], ['#3b2a57', '#f0c6ff'], ['#f3efe6', '#b3261e'],
  ['#0f5257', '#f6e7b5'], ['#8a5a2b', '#faf1dc'], ['#101820', '#7fd6ff'], ['#c9b7a2', '#3a2618'],
];

/** 128 CD spines (vertical text) in a 2048×1024 atlas: 64 × 2 cells of 32×512. */
function spineAtlas(R) {
  const cells = [];
  const c = canvas(2048, 1024, (g) => {
    for (let i = 0; i < 128; i++) {
      const cd = copy.cdSpines[i % copy.cdSpines.length];
      const [bg, fg] = PALETTES[Math.floor(R() * PALETTES.length)];
      const x = (i % 64) * 32, y = Math.floor(i / 64) * 512;
      g.fillStyle = bg; g.fillRect(x, y, 32, 512);
      g.fillStyle = 'rgba(255,255,255,.08)'; g.fillRect(x, y, 2, 512);
      g.save(); g.translate(x + 22, y + 500); g.rotate(-PI / 2);
      g.fillStyle = fg;
      fitText(g, `${cd.artist.toUpperCase()}  ·  ${cd.title}`, 470, 15, '600 %px "Helvetica Neue", Arial, sans-serif');
      g.fillText(`${cd.artist.toUpperCase()}  ·  ${cd.title}`, 0, 0);
      g.restore();
      cells.push([x / 2048, 1 - (y + 512) / 1024, 32 / 2048, 512 / 1024]);
    }
  });
  return { tex: texture(c), cells };
}

/** 64 invented front covers (CD + DVD) in a 2048² atlas of 256² cells. */
function coverAtlas(R) {
  const cells = [];
  const titles = [...copy.cdSpines.map((d) => [d.artist, d.title]), ...copy.dvdTitles.map((d) => [d.format || 'DVD', d.title])];
  const c = canvas(2048, 2048, (g) => {
    for (let i = 0; i < 64; i++) {
      const [who, title] = titles[(i * 7) % titles.length];
      const [bg, fg] = PALETTES[Math.floor(R() * PALETTES.length)];
      const x = (i % 8) * 256, y = Math.floor(i / 8) * 256;
      g.save(); g.beginPath(); g.rect(x, y, 256, 256); g.clip();
      g.fillStyle = bg; g.fillRect(x, y, 256, 256);
      // One of a few simple, period-plausible layouts: circle, bars, grid, big type.
      const kind = i % 4;
      g.fillStyle = fg; g.strokeStyle = fg;
      if (kind === 0) { g.globalAlpha = 0.85; g.beginPath(); g.arc(x + 70 + R() * 120, y + 90 + R() * 70, 30 + R() * 50, 0, PI * 2); g.fill(); }
      if (kind === 1) { g.globalAlpha = 0.7; for (let k = 0; k < 5; k++) g.fillRect(x, y + 30 + k * 34, 256 * (0.3 + R() * 0.7), 14); }
      if (kind === 2) { g.globalAlpha = 0.5; g.lineWidth = 2; for (let k = 0; k < 6; k++) { g.beginPath(); g.moveTo(x + k * 44, y); g.lineTo(x + k * 44 + 60, y + 256); g.stroke(); } }
      if (kind === 3) { g.globalAlpha = 0.18; g.font = '900 190px Georgia, serif'; g.fillText(title[0] || 'A', x + 20, y + 200); }
      g.globalAlpha = 1;
      fitText(g, title.toUpperCase(), 230, 22, '800 %px "Helvetica Neue", Arial, sans-serif');
      g.fillText(title.toUpperCase(), x + 13, y + 228);
      fitText(g, who, 230, 15, '400 %px "Helvetica Neue", Arial, sans-serif');
      g.globalAlpha = 0.8; g.fillText(who, x + 13, y + 246);
      g.restore();
      cells.push([x / 2048, 1 - (y + 256) / 2048, 256 / 2048, 256 / 2048]);
    }
  });
  return { tex: texture(c), cells };
}

function posterTexture(p, i) {
  const [bg, fg] = PALETTES[(i * 5 + 3) % PALETTES.length];
  return texture(canvas(512, 768, (g, w, h) => {
    g.fillStyle = bg; g.fillRect(0, 0, w, h);
    g.fillStyle = fg; g.globalAlpha = 0.9;
    if (i % 2) { g.beginPath(); g.arc(w * 0.5, h * 0.36, 150, 0, PI * 2); g.fill(); }
    else for (let k = 0; k < 9; k++) g.fillRect(40 + k * 50, 90, 22, 380 - k * 30);
    g.globalAlpha = 1;
    fitText(g, p.title, w - 60, 54, '900 %px "Helvetica Neue", Arial, sans-serif');
    g.fillText(p.title, 30, h - 150);
    if (p.tagline) { fitText(g, p.tagline, w - 60, 22, 'italic 400 %px Georgia, serif'); g.fillText(p.tagline, 30, h - 105); }
    g.font = '600 18px "Helvetica Neue", Arial, sans-serif'; g.globalAlpha = 0.75;
    g.fillText((p.kind || '').toUpperCase(), 30, h - 50);
  }));
}

function signTexture() {
  const s = copy.sign;
  return texture(canvas(2048, 256, (g, w, h) => {
    g.fillStyle = '#0d1b2e'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#f4ead2';
    g.font = '800 132px "Helvetica Neue", Arial, sans-serif';
    g.fillText(s.main, 70, 168);
    const mw = g.measureText(s.main).width;
    g.fillStyle = '#e8b64c'; g.font = '600 60px "Helvetica Neue", Arial, sans-serif';
    g.fillText(`·  ${s.sub}`, 100 + mw, 162);
    g.fillStyle = 'rgba(244,234,210,.7)'; g.font = '500 30px "Helvetica Neue", Arial, sans-serif';
    g.fillText(s.strap, 72, 226);
    g.textAlign = 'right'; g.fillText(`No. ${s.number}`, w - 60, 226);
  }));
}

function lettering(lines, { w = 1024, h = 256, size = 58, color = 'rgba(255,255,255,.92)' } = {}) {
  return texture(canvas(w, h, (g) => {
    g.fillStyle = color; g.textAlign = 'center';
    lines.forEach((line, i) => {
      fitText(g, line, w - 40, i ? size * 0.55 : size, `${i ? 500 : 800} %px "Helvetica Neue", Arial, sans-serif`);
      g.fillText(line, w / 2, (h / (lines.length + 1)) * (i + 1) + size * 0.3);
    });
  }));
}

function binSignTexture() {
  const b = copy.bargainBin;
  return texture(canvas(1024, 560, (g, w, h) => {
    g.fillStyle = '#f7f1e3'; g.fillRect(0, 0, w, h);
    g.strokeStyle = '#c0392b'; g.lineWidth = 14; g.strokeRect(14, 14, w - 28, h - 28);
    g.fillStyle = '#1a1a1a'; g.textAlign = 'center';
    fitText(g, b.title, w - 90, 86, '900 %px "Helvetica Neue", Arial, sans-serif'); g.fillText(b.title, w / 2, 150);
    g.fillStyle = '#c0392b'; g.font = '900 150px "Helvetica Neue", Arial, sans-serif'; g.fillText(b.price, w / 2, 330);
    g.fillStyle = '#1a1a1a'; g.font = '700 54px "Helvetica Neue", Arial, sans-serif'; g.fillText(b.deal, w / 2, 410);
    fitText(g, b.note, w - 90, 30, 'italic 400 %px Georgia, serif'); g.fillText(b.note, w / 2, 480);
  }));
}

function floorTexture() {
  return texture(canvas(512, 512, (g, w) => {
    const a = '#d9dcd6', b = '#b9bfb8';
    for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) { g.fillStyle = (i + j) % 2 ? a : b; g.fillRect(i * 256, j * 256, 256, 256); }
    g.fillStyle = 'rgba(0,0,0,.05)'; for (let k = 0; k < 900; k++) g.fillRect((k * 97) % w, (k * 61) % w, 2, 2);
  }), { repeat: 1 });
}

function pavementTexture() {
  return texture(canvas(512, 512, (g, w) => {
    g.fillStyle = '#23262b'; g.fillRect(0, 0, w, w);
    g.strokeStyle = '#121418'; g.lineWidth = 5;
    for (let k = 0; k <= 4; k++) { g.beginPath(); g.moveTo(k * 128, 0); g.lineTo(k * 128, w); g.stroke(); g.beginPath(); g.moveTo(0, k * 128); g.lineTo(w, k * 128); g.stroke(); }
    for (let k = 0; k < 2000; k++) { g.fillStyle = `rgba(255,255,255,${0.02 + (k % 5) * 0.01})`; g.fillRect((k * 131) % w, (k * 71) % w, 2, 2); }
  }), { repeat: 1 });
}

function streakTexture() {
  return texture(canvas(64, 256, (g, w, h) => {
    const gr = g.createLinearGradient(0, 0, 0, h);
    gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.35, 'rgba(255,255,255,.35)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr; g.fillRect(0, 0, w, h);
    const side = g.createLinearGradient(0, 0, w, 0);
    side.addColorStop(0, 'rgba(0,0,0,1)'); side.addColorStop(0.5, 'rgba(0,0,0,0)'); side.addColorStop(1, 'rgba(0,0,0,1)');
    g.globalCompositeOperation = 'destination-out'; g.fillStyle = side; g.fillRect(0, 0, w, h);
  }));
}

// ---- geometry helpers ---------------------------------------------------------------------

/** A box whose `face` (0 +x, 1 -x, 2 +y, 3 -y, 4 +z, 5 -z) shows atlas `rect`; the rest show `plain`. */
function atlasBox(w, h, d, face, rect, plain) {
  const geo = new THREE.BoxGeometry(w, h, d);
  const uv = geo.attributes.uv;
  for (let f = 0; f < 6; f++) {
    const [u, v, uw, vh] = f === face ? rect : plain;
    for (let k = 0; k < 4; k++) {
      const i = f * 4 + k;
      uv.setXY(i, u + uv.getX(i) * uw, v + uv.getY(i) * vh);
    }
  }
  return geo;
}

class Bucket {
  constructor() { this.geos = []; }
  add(geo, pos, rotY = 0, rotX = 0) {
    const m = new THREE.Matrix4().compose(pos, new THREE.Quaternion().setFromEuler(new THREE.Euler(rotX, rotY, 0, 'YXZ')), new THREE.Vector3(1, 1, 1));
    this.geos.push(geo.clone().applyMatrix4(m));
  }
  mesh(material) {
    const geos = this.geos.map((g) => (g.index ? g.toNonIndexed() : g));
    for (const g of geos) for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
    const mesh = new THREE.Mesh(mergeGeometries(geos), material);
    mesh.matrixAutoUpdate = false;
    return mesh;
  }
}

const texLoader = new THREE.TextureLoader();
/** A Poly Haven PBR set (diff / nor_gl / arm) from assets/tex, tiled `repeat` times. */
async function pbr(name, res, repeat) {
  const load = async (kind, srgb) => {
    const t = await texLoader.loadAsync(`${ASSETS}tex/${name}_${kind}_${res}.jpg`);
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); t.anisotropy = 1;
    return t;
  };
  const [map, normalMap, arm] = await Promise.all([load('diff', true), load('nor_gl', false), load('arm', false)]);
  return { map, normalMap, roughnessMap: arm };
}

async function prop(name, env) {
  const gltf = await new GLTFLoader().loadAsync(`${ASSETS}props/${name}/${name}_1k.gltf`);
  gltf.scene.traverse((o) => { if (o.isMesh) { o.material.envMap = env; o.material.envMapIntensity = 0.7; } });
  return gltf.scene;
}

/** Soft contact shadow: a dark patch that fades out, laid on the floor. */
let blobTex = null;
function aoBlob(w, d, strength = 0.55) {
  blobTex ??= texture(canvas(256, 256, (g, s) => {
    const r = g.createRadialGradient(s / 2, s / 2, s * 0.12, s / 2, s / 2, s / 2);
    r.addColorStop(0, '#fff'); r.addColorStop(1, '#000');
    g.fillStyle = r; g.fillRect(0, 0, s, s);
  }), { srgb: false });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshBasicMaterial({ color: 0x000000, alphaMap: blobTex, transparent: true, opacity: strength, depthWrite: false }));
  m.rotation.x = -PI / 2;
  return m;
}

/** Rain on glass: bright beads and a few runs, drawn once; the texture scrolls down slowly. */
function dropsTexture(R) {
  const t = texture(canvas(512, 1024, (g, w, h) => {
    for (let i = 0; i < 900; i++) {
      const x = R() * w, y = R() * h, r = 0.8 + R() * R() * 2.6;
      g.fillStyle = `rgba(210,225,240,${0.25 + R() * 0.45})`; g.beginPath(); g.arc(x, y, r, 0, PI * 2); g.fill();
      g.fillStyle = 'rgba(255,255,255,.9)'; g.fillRect(x - r * 0.3, y - r * 0.4, Math.max(1, r * 0.4), Math.max(1, r * 0.3));
    }
    g.strokeStyle = 'rgba(200,215,235,.35)';
    for (let i = 0; i < 26; i++) { g.lineWidth = 1 + R() * 2; const x = R() * w, y = R() * h; g.beginPath(); g.moveTo(x, y); g.lineTo(x + (R() - 0.5) * 12, y + 80 + R() * 220); g.stroke(); }
  }));
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

async function loadEnv(renderer, file) {
  const hdr = await new RGBELoader().loadAsync(ASSETS + 'env/' + file);
  hdr.mapping = THREE.EquirectangularReflectionMapping;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromEquirectangular(hdr).texture;
  hdr.dispose(); pmrem.dispose();
  return env;
}

// ---- the store ------------------------------------------------------------------------------

export async function createStore({ renderer }) {
  const R = rng(27);
  const [streetEnv, shopEnv] = await Promise.all([
    loadEnv(renderer, 'cobblestone_street_night_1k.hdr'),
    loadEnv(renderer, 'phone_shop_1k.hdr'),
  ]);

  const root = new THREE.Group();
  const exterior = new THREE.Group();
  const interior = new THREE.Group();
  root.add(exterior, interior);

  const spines = spineAtlas(R);
  const covers = coverAtlas(R);
  const PLAIN_DARK = [0.001, 0.001, 0.0005, 0.0005];      // the dark first pixel of the spine atlas

  const shopStd = (o) => new THREE.MeshStandardMaterial({ envMap: shopEnv, envMapIntensity: 0.42, ...o });
  const streetStd = (o) => new THREE.MeshStandardMaterial({ envMap: streetEnv, envMapIntensity: 1.3, ...o });

  // ---- exterior: street, facade, window, sign, lamp, rain -----------------------------------
  // Wet asphalt: the photo texture's roughness, pushed glossy (it's raining), so lights streak in it.
  const asphalt = await pbr('asphalt_02', '2k', [5, 4.5]);
  const street = new THREE.Mesh(new THREE.PlaneGeometry(18, 16),
    streetStd({ ...asphalt, roughness: 0.42, metalness: 0.0, color: 0x8f959c, envMapIntensity: 1.6, normalScale: new THREE.Vector2(0.6, 0.6) }));
  street.rotation.x = -PI / 2; street.position.set(-0.5, 0, 8.0);
  exterior.add(street);

  const facadeMat = streetStd({ color: 0x14233a, roughness: 0.55 });
  const trimMat = streetStd({ color: 0xc9c2b0, roughness: 0.4 });
  const fac = new Bucket(), trim = new Bucket();
  const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  // Pillars and bands around the openings (window left, door, window right).
  for (const [x0, x1] of [[-5.2, -4.2], [-0.7, -0.5], [0.5, 0.7], [3.0, 3.8]]) fac.add(box(x1 - x0, 2.6, 0.24), V((x0 + x1) / 2, 1.3, 0.12));
  fac.add(box(3.5, 0.45, 0.24), V(-2.45, 0.225, 0.12));                 // stall riser under the left window
  fac.add(box(2.3, 0.45, 0.24), V(1.85, 0.225, 0.12));                  // … and the right one
  fac.add(box(1.0, 0.45, 0.24), V(0, 2.375, 0.12));                     // transom over the door
  fac.add(box(9.0, 1.6, 0.3), V(-0.7, 3.4, 0.15));                      // wall above the fascia
  for (const x of [-4.2, -0.7, 0.7, 3.0]) trim.add(box(0.06, 2.1, 0.3), V(x, 1.45, 0.15));
  trim.add(box(3.6, 0.06, 0.3), V(-2.45, 2.47, 0.15)); trim.add(box(2.4, 0.06, 0.3), V(1.85, 2.47, 0.15));
  trim.add(box(3.6, 0.08, 0.34), V(-2.45, 0.47, 0.17)); trim.add(box(2.4, 0.08, 0.34), V(1.85, 0.47, 0.17));
  exterior.add(fac.mesh(facadeMat), trim.mesh(trimMat));

  // Neighbours: a shuttered shop to the left, a dark doorway to the right.
  const nb = new Bucket();
  nb.add(box(4, 4.2, 0.3), V(-7.2, 2.1, 0.3)); nb.add(box(4, 4.2, 0.3), V(5.8, 2.1, 0.3));
  exterior.add(nb.mesh(streetStd({ color: 0x2a2320, roughness: 0.8 })));
  const shutter = new THREE.Mesh(new THREE.PlaneGeometry(3, 2.3), streetStd({ color: 0x3b4046, roughness: 0.5, metalness: 0.6 }));
  shutter.position.set(-7.2, 1.2, 0.46); exterior.add(shutter);
  const nbSign = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 0.4), new THREE.MeshBasicMaterial({ map: lettering([copy.street[0]], { w: 1024, h: 160, size: 90, color: '#b9c7c9' }), transparent: true }));
  nbSign.position.set(-7.2, 2.8, 0.47); exterior.add(nbSign);

  // Fascia sign (backlit), with light spilling on the wet pavement below.
  const sign = new THREE.Mesh(new THREE.PlaneGeometry(8.4, 1.05),
    new THREE.MeshBasicMaterial({ map: signTexture(), color: new THREE.Color(1.6, 1.6, 1.6) }));
  sign.position.set(-0.7, 3.12, 0.31); exterior.add(sign);

  // Window lettering on the glass, and the door's opening-hours decal.
  const slogan = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 0.42),
    new THREE.MeshBasicMaterial({ map: lettering([copy.windowSlogans[0]], { w: 2048, h: 256, size: 96 }), transparent: true, depthWrite: false }));
  slogan.position.set(-2.45, 2.12, 0.012); exterior.add(slogan);

  const glassMat = new THREE.MeshStandardMaterial({ color: 0x0a0d10, roughness: 0.04, metalness: 1.0, envMap: streetEnv, envMapIntensity: 0.55, transparent: true, opacity: 0.16, depthWrite: false });
  for (const [x0, x1] of [[WINDOW.x0, WINDOW.x1], [0.7, 3.0]]) {
    const g = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, WINDOW.y1 - WINDOW.y0), glassMat);
    g.position.set((x0 + x1) / 2, (WINDOW.y0 + WINDOW.y1) / 2, 0.0); exterior.add(g);
  }

  // Street lamp (sodium orange) and the cool spill from the window.
  const lampPole = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.07, 4.4, 10), streetStd({ color: 0x1b1d20, roughness: 0.5, metalness: 0.8 }));
  lampPole.position.set(4.3, 2.2, 3.4); exterior.add(lampPole);
  const lampHead = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.12, 0.26), new THREE.MeshBasicMaterial({ color: new THREE.Color(6, 3.2, 1.1) }));
  lampHead.position.set(4.05, 4.35, 3.4); exterior.add(lampHead);
  const lamp = new THREE.PointLight(0xffa25a, 45, 16, 2); lamp.position.set(4.0, 4.1, 3.4); root.add(lamp);
  const lamp2Head = lampHead.clone(); lamp2Head.position.set(-6.2, 4.35, 6.0); exterior.add(lamp2Head);
  const lamp2Pole = lampPole.clone(); lamp2Pole.position.set(-6.45, 2.2, 6.0); exterior.add(lamp2Pole);
  const lamp2 = new THREE.PointLight(0xffa25a, 38, 16, 2); lamp2.position.set(-6.2, 4.1, 6.0); root.add(lamp2);
  // The shop's glow falling out onto the wet pavement.
  const spill = new THREE.PointLight(0xd8f0ff, 22, 8, 2); spill.position.set(-2.2, 1.7, 0.9); root.add(spill);
  const spill2 = new THREE.PointLight(0xd8f0ff, 12, 7, 2); spill2.position.set(1.9, 1.7, 0.9); root.add(spill2);

  // Wet-ground reflections: additive streaks under the bright things.
  const streak = streakTexture();
  const streakMat = (c) => new THREE.MeshBasicMaterial({ map: streak, color: c, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
  const addStreak = (x, w, len, c, z0 = 0.05) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, len), streakMat(c));
    m.rotation.x = -PI / 2; m.position.set(x, 0.004, z0 + len / 2); exterior.add(m);
  };
  addStreak(-2.45, 3.2, 3.6, new THREE.Color(0.55, 0.62, 0.6));      // shop window
  addStreak(1.85, 2.1, 3.2, new THREE.Color(0.5, 0.58, 0.56));
  addStreak(-0.7, 7.0, 2.2, new THREE.Color(0.18, 0.2, 0.26), 0.35); // fascia
  addStreak(4.05, 0.7, 5.5, new THREE.Color(1.1, 0.55, 0.2), 1.0);   // lamp
  addStreak(-6.2, 0.8, 6.0, new THREE.Color(0.9, 0.45, 0.16), 2.0);  // far lamp

  // Rain: thin streaks falling through the street, positions a pure function of t.
  const RAIN = 3800;
  const rain = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.006, 0.42),
    new THREE.MeshBasicMaterial({ color: 0xb4c6d6, transparent: true, opacity: 0.42, depthWrite: false, blending: THREE.AdditiveBlending }), RAIN);
  rain.frustumCulled = false;
  const drops = Array.from({ length: RAIN }, () => [-4.8 + R() * 9.6, R() * 5.5, 0.15 + R() * 8.5, 6.5 + R() * 2]);
  const dm = new THREE.Matrix4(), dq = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, 0.09)), ds = new THREE.Vector3(1, 1, 1), dp = new THREE.Vector3();
  exterior.add(rain);

  // Splashes: tiny rings that open and fade where drops hit the pavement.
  const SPLASH = 520;
  const ringTex = texture(canvas(64, 64, (g) => { g.strokeStyle = '#fff'; g.lineWidth = 5; g.beginPath(); g.arc(32, 32, 24, 0, PI * 2); g.stroke(); }), { srgb: false });
  const splashes = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1).rotateX(-PI / 2),
    new THREE.MeshBasicMaterial({ map: ringTex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, color: 0xffffff }), SPLASH);
  splashes.frustumCulled = false;
  const splashData = Array.from({ length: SPLASH }, () => [-4.6 + R() * 9.2, 0.15 + R() * 7.5, R(), 0.35 + R() * 0.45]);
  const splashColor = new THREE.Color();
  for (let i = 0; i < SPLASH; i++) splashes.setColorAt(i, splashColor.setRGB(0, 0, 0));
  exterior.add(splashes);

  // Drops beading and running on the shop glass (windows and door), street side.
  const drops2 = dropsTexture(R);
  const dropsMat = new THREE.MeshBasicMaterial({ map: drops2, transparent: true, opacity: 0.55, depthWrite: false, blending: THREE.AdditiveBlending });
  for (const [x0, x1] of [[WINDOW.x0, WINDOW.x1], [0.7, 3.0]]) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, WINDOW.y1 - WINDOW.y0), dropsMat);
    m.position.set((x0 + x1) / 2, (WINDOW.y0 + WINDOW.y1) / 2, 0.02); exterior.add(m);
  }

  // ---- door: hinge on the left jamb, swings inward ------------------------------------------
  const doorHinge = new THREE.Group();
  doorHinge.position.set(DOOR.hingeX, 0, 0);
  const door = new THREE.Group();
  const frameMat = streetStd({ color: 0x0e1a2c, roughness: 0.45 });
  const df = new Bucket();
  df.add(box(0.07, DOOR.height, 0.05), V(0.035, DOOR.height / 2, 0)); df.add(box(0.07, DOOR.height, 0.05), V(DOOR.width - 0.035, DOOR.height / 2, 0));
  df.add(box(DOOR.width, 0.09, 0.05), V(DOOR.width / 2, DOOR.height - 0.045, 0)); df.add(box(DOOR.width, 0.22, 0.05), V(DOOR.width / 2, 0.11, 0));
  door.add(df.mesh(frameMat));
  // The door pane is a touch more present than the windows: a faint tint and a soft street reflection.
  const doorGlassMat = glassMat.clone(); doorGlassMat.opacity = 0.3; doorGlassMat.color.set(0x1a2530); doorGlassMat.envMapIntensity = 0.9;
  const doorGlass = new THREE.Mesh(new THREE.PlaneGeometry(DOOR.width - 0.14, DOOR.height - 0.31), doorGlassMat);
  doorGlass.position.set(DOOR.width / 2, (DOOR.height + 0.13) / 2, 0); door.add(doorGlass);
  // Brushed-steel push bar across the glass, centred on the push point.
  const plate = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.045, 0.03), streetStd({ color: 0xe6e8ea, metalness: 1, roughness: 0.22, envMapIntensity: 1.6 }));
  plate.position.set(Math.min(DOOR.plate.x - DOOR.hingeX, DOOR.width - 0.36), DOOR.plate.y, 0.04); door.add(plate);
  const hours = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.15),
    new THREE.MeshBasicMaterial({ map: lettering([copy.sign.hours], { w: 1024, h: 256, size: 70 }), transparent: true, depthWrite: false }));
  hours.scale.setScalar(0.55); hours.position.set(DOOR.width * 0.62, 0.95, 0.03); door.add(hours);
  const doorDrops = new THREE.Mesh(new THREE.PlaneGeometry(DOOR.width - 0.14, DOOR.height - 0.31), dropsMat);
  doorDrops.material = dropsMat.clone(); doorDrops.material.opacity = 0.3;
  doorDrops.position.set(DOOR.width / 2, (DOOR.height + 0.13) / 2, 0.035); door.add(doorDrops);
  doorHinge.add(door);
  root.add(doorHinge);

  // ---- interior ------------------------------------------------------------------------------
  const Z_BACK = -9.2, X_L = -4.6, X_R = 3.9, CEIL = 2.8;
  // Worn polished concrete: scuffed, patchy, a soft sheen under the tubes.
  const concrete = await pbr('concrete_floor_worn_001', '2k', [3, 3.2]);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(X_R - X_L, -Z_BACK),
    shopStd({ ...concrete, color: 0xb9bdb4, roughness: 0.75, normalScale: new THREE.Vector2(0.5, 0.5) }));
  floor.rotation.x = -PI / 2; floor.position.set((X_L + X_R) / 2, 0.002, Z_BACK / 2); interior.add(floor);

  const shell = new Bucket();
  shell.add(box(X_R - X_L, 0.05, -Z_BACK), V((X_L + X_R) / 2, CEIL, Z_BACK / 2));            // ceiling
  shell.add(box(0.05, CEIL, -Z_BACK), V(X_L, CEIL / 2, Z_BACK / 2));                          // left wall
  shell.add(box(0.05, CEIL, -Z_BACK), V(X_R, CEIL / 2, Z_BACK / 2));                          // right wall
  shell.add(box(X_R - X_L, CEIL, 0.05), V((X_L + X_R) / 2, CEIL / 2, Z_BACK));                // back wall
  interior.add(shell.mesh(shopStd({ color: 0xc9cdc4, roughness: 0.85 })));

  // Fluorescent panels: bright emissive tiles (they bloom), rows along the aisles.
  const panels = new Bucket();
  for (const x of [-2.9, -0.2, 2.5]) for (let z = -1.0; z > Z_BACK + 0.6; z -= 1.8) panels.add(box(1.2, 0.03, 0.3), V(x, CEIL - 0.03, z));
  const panelMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(5.0, 5.4, 5.1) });
  interior.add(panels.mesh(panelMat));
  // One tube near the back flickers on the song's fills.
  const flickerTube = new THREE.Mesh(box(1.2, 0.03, 0.3), new THREE.MeshBasicMaterial({ color: new THREE.Color(3.4, 3.7, 3.5) }));
  flickerTube.position.set(2.5, CEIL - 0.03, -8.2); interior.add(flickerTube);
  // Pools of cool light under the tubes, so the room falls off toward the walls and corners.
  for (const [x, z, i] of [[-1.75, -2.8, 7], [-0.2, -5.6, 6], [2.45, -6.4, 5], [0.9, -3.2, 5], [-3.3, -6.8, 4]]) {
    const l = new THREE.PointLight(0xe6f4ff, i, 5.5, 2); l.position.set(x, CEIL - 0.25, z); root.add(l);
  }

  // CD racks: double-sided gondolas, CDs spine-out on four tiers.
  const rackMat = shopStd({ color: 0x1c1f24, roughness: 0.55, metalness: 0.3 });
  const cdMat = shopStd({ map: spines.tex, roughness: 0.35 });
  const racks = new Bucket(), cds = new Bucket(), faceCases = new Bucket();
  const gondola = (x, z0, z1) => {
    const len = z0 - z1, cz = (z0 + z1) / 2;
    racks.add(box(0.12, 1.55, len), V(x, 0.775, cz));                                    // spine board
    for (const y of [0.08, 0.42, 0.76, 1.1]) for (const s of [-1, 1]) racks.add(box(0.34, 0.02, len), V(x + s * 0.23, y, cz));
    racks.add(box(0.8, 0.08, len), V(x, 1.59, cz));                                      // top cap
    for (const y of [0.09, 0.43, 0.77, 1.11]) for (const s of [-1, 1]) {
      let z = z0 - 0.03;
      while (z > z1 + 0.03) {
        if (R() < 0.04) { z -= 0.04; continue; }                                         // a gap now and then
        const cell = spines.cells[Math.floor(R() * spines.cells.length)];
        cds.add(atlasBox(0.142, 0.125, 0.0104, s > 0 ? 0 : 1, cell, PLAIN_DARK), V(x + s * 0.29, y + 0.0625, z));
        z -= 0.0106;
      }
    }
  };
  gondola(-1.75, -3.2, -7.2);                                                 // starts deep, so the counter is in view
  gondola(2.45, -5.0, -8.0);
  // Wall shelves: DVDs and Blu-rays face-out down the left wall; new releases face-out on the back wall.
  const faceOut = (px, pz, rotY, rows, span, w, h) => {
    for (let r = 0; r < rows; r++) {
      const y = 0.35 + r * 0.3;
      racks.add(box(span, 0.02, 0.2), V(px, y - 0.01, pz), rotY);
      for (let k = 0; k < Math.floor(span / (w + 0.012)); k++) {
        const off = -span / 2 + (k + 0.5) * (w + 0.012);
        const pos = new THREE.Vector3(px + Math.cos(rotY) * off, y + h / 2, pz - Math.sin(rotY) * off);
        const cell = covers.cells[Math.floor(R() * covers.cells.length)];
        faceCases.add(atlasBox(w, h, 0.014, 4, cell, PLAIN_DARK), pos, rotY, -0.08);
      }
    }
  };
  faceOut(X_L + 0.12, -4.9, PI / 2, 6, 7.6, 0.135, 0.19);            // left wall, facing +x
  faceOut(-1.0, Z_BACK + 0.12, 0, 5, 5.0, 0.142, 0.125);              // back wall, facing +z
  const coverMat = shopStd({ map: covers.tex, roughness: 0.3 });
  interior.add(racks.mesh(rackMat), cds.mesh(cdMat), faceCases.mesh(coverMat));

  // Posters on the right wall and above the back shelves.
  copy.posters.slice(0, 6).forEach((p, i) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 1.05), shopStd({ map: posterTexture(p, i), roughness: 0.6 }));
    if (i < 4) { m.position.set(X_R - 0.03, 1.75, -1.6 - i * 1.5); m.rotation.y = -PI / 2; }
    else { m.position.set(1.6 + (i - 4) * 1.0, 2.05, Z_BACK + 0.03); }
    interior.add(m);
  });

  // Hanging section signs over the aisles.
  copy.sections.slice(0, 4).forEach((s, i) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1.3, 0.28),
      new THREE.MeshBasicMaterial({ map: lettering([s.label], { w: 1024, h: 220, size: 120, color: '#1c2a3f' }), transparent: true }));
    const back = new THREE.Mesh(new THREE.PlaneGeometry(1.34, 0.32), new THREE.MeshBasicMaterial({ color: 0xf4f1e8 }));
    const g = new THREE.Group(); g.add(back, m); m.position.z = 0.002;
    g.position.set([-1.75, -1.75, 2.45, -3.6][i], 2.32, [-3.9, -6.2, -6.2, -4.6][i]);
    interior.add(g);
  });

  // Counter with the till, near the entrance on the right.
  const counter = new THREE.Group();
  const cb = new Bucket();
  cb.add(box(0.6, 1.0, 1.6), V(0, 0.5, 0)); cb.add(box(0.7, 0.04, 1.7), V(0, 1.02, 0));
  counter.add(cb.mesh(shopStd({ color: 0x1d2530, roughness: 0.5 })));
  const till = new THREE.Mesh(box(0.34, 0.22, 0.3), shopStd({ color: 0x2a2a2a, roughness: 0.4 }));
  till.position.set(0, 1.15, 0.3); counter.add(till);
  const pay = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.16), new THREE.MeshBasicMaterial({ map: lettering([copy.misc.counter], { w: 512, h: 140, size: 80, color: '#f4ead2' }), color: 0xffffff }));
  pay.position.set(0.31, 0.8, 0); pay.rotation.y = PI / 2; counter.add(pay);
  // Left of the entrance, where the glance at the racks passes over it.
  counter.position.set(-2.45, 0, -2.0);
  interior.add(counter);

  // Display window: stepped risers with face-out cases looking at the street.
  const disp = new Bucket(), dispCases = new Bucket();
  [[-0.25, 0.5], [-0.55, 0.8], [-0.85, 1.1]].forEach(([z, h]) => disp.add(box(3.4, h, 0.3), V(-2.45, h / 2, z)));
  [[-0.25, 0.5], [-0.55, 0.8], [-0.85, 1.1]].forEach(([z, h], r) => {
    for (let k = 0; k < 9; k++) {
      const cell = covers.cells[(r * 9 + k * 3) % covers.cells.length];
      const big = r === 2 && k % 3 === 1;
      const w = big ? 0.3 : 0.142, hh = big ? 0.3 : 0.125;
      dispCases.add(atlasBox(w, hh, 0.012, 4, cell, PLAIN_DARK), V(-4.0 + k * 0.39, h + hh / 2 + 0.01, z + 0.05), 0, -0.25);
    }
  });
  interior.add(disp.mesh(shopStd({ color: 0xf1ede4, roughness: 0.7 })), dispCases.mesh(coverMat));
  const winPoster = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 1.35), shopStd({ map: posterTexture(copy.posters[6], 6), roughness: 0.6, emissive: 0xffffff, emissiveIntensity: 0.15 }));
  winPoster.position.set(-1.35, 1.72, -1.05); interior.add(winPoster);

  // ---- the PRE-OWNED / DONATED bin ----------------------------------------------------------
  const bin = new THREE.Group();
  bin.position.set(BIN.x, 0, BIN.z); bin.rotation.y = BIN.rotY;
  const bb = new Bucket();
  const FLOOR_Y = BIN.top - 0.135;                                                          // CD tops land on BIN.top
  bb.add(box(BIN.width + 0.06, 0.03, BIN.depth + 0.06), V(0, FLOOR_Y - 0.015, 0));           // floor of the tray
  bb.add(box(BIN.width + 0.06, 0.1, 0.03), V(0, FLOOR_Y + 0.05, BIN.depth / 2 + 0.03));     // low front lip
  bb.add(box(BIN.width + 0.06, 0.2, 0.03), V(0, FLOOR_Y + 0.1, -BIN.depth / 2 - 0.03));     // back
  for (const s of [-1, 1]) bb.add(box(0.03, 0.14, BIN.depth + 0.06), V(s * (BIN.width / 2 + 0.03), FLOOR_Y + 0.07, 0));
  bb.add(box(BIN.width + 0.06, FLOOR_Y - 0.03, BIN.depth + 0.06), V(0, (FLOOR_Y - 0.03) / 2, 0)); // cabinet base
  bin.add(bb.mesh(shopStd({ color: 0x6b4a2f, roughness: 0.55 })));
  // Six lanes of cases standing upright, covers facing the browsing side (+z), leaning back.
  const lanes = new Bucket();
  for (let lane = 0; lane < 6; lane++) {
    const lx = -BIN.width / 2 + 0.085 + lane * 0.166;
    for (let k = 0; k < 44; k++) {
      const z = BIN.depth / 2 - 0.03 - k * 0.0125;
      const cell = covers.cells[Math.floor(R() * covers.cells.length)];
      lanes.add(atlasBox(0.142, 0.125, 0.0104, 4, cell, PLAIN_DARK), V(lx, FLOOR_Y + 0.0625, z), (R() - 0.5) * 0.05, -0.22);
    }
  }
  bin.add(lanes.mesh(coverMat));
  const binSign = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 0.34), shopStd({ map: binSignTexture(), roughness: 0.7, emissive: 0xffffff, emissiveIntensity: 0.12 }));
  binSign.position.set(0, BIN.sign.y - 0.05, -BIN.depth / 2 - 0.05); binSign.rotation.x = -0.12;
  bin.add(binSign);
  interior.add(bin);

  // Contact shadows: where things meet the floor, the light can't reach.
  const blob = (w, d, x, z, rotY = 0, k = 0.55) => { const m = aoBlob(w, d, k); m.position.set(x, 0.006, z); m.rotation.z = -rotY; interior.add(m); };
  blob(1.3, 4.6, -1.75, -5.2); blob(1.2, 3.6, 2.45, -6.5);
  blob(1.5, 1.1, BIN.x, BIN.z, BIN.rotY, 0.65); blob(1.1, 2.2, -2.45, -2.0, 0, 0.6);
  blob(3.8, 1.4, -2.45, -0.55, 0, 0.45);
  blob(0.7, 8.6, X_L + 0.3, -4.6, 0, 0.5); blob(0.7, 8.6, X_R - 0.3, -4.6, 0, 0.45); blob(8.4, 0.7, -0.35, Z_BACK + 0.3, 0, 0.5);

  // Real props (Poly Haven, CC0): the till on the counter, a wet-floor sign by the door
  // (it's raining), a crate of unsorted stock next to the bin.
  const [register, wetSign, crate] = await Promise.all([
    prop('CashRegister_01', shopEnv), prop('WetFloorSign_01', shopEnv), prop('plastic_crate_02', shopEnv),
  ]);
  register.position.set(-2.5, 1.04, -1.55); register.rotation.y = PI / 2; interior.add(register);
  till.visible = false;
  wetSign.position.set(-1.0, 0, -0.95); wetSign.rotation.y = 0.5; interior.add(wetSign);
  crate.position.set(1.95, 0, -4.35); crate.rotation.y = 0.3; interior.add(crate);
  blob(0.7, 0.5, 1.95, -4.35, 0.3, 0.6);

  root.updateMatrixWorld(true);

  let lastT = null;
  function update(t, ctx = {}) {
    doorHinge.rotation.y = (ctx.door ?? 0) * (DOOR.maxDeg * PI / 180);
    doorHinge.updateMatrixWorld(true);
    if (t !== lastT) {
      for (let i = 0; i < RAIN; i++) {
        const [x, y0, z, v] = drops[i];
        const y = ((y0 - v * t) % 5.5 + 5.5) % 5.5;
        dp.set(x + 0.09 * y, y, z);
        dm.compose(dp, dq, ds);
        rain.setMatrixAt(i, dm);
      }
      rain.instanceMatrix.needsUpdate = true;
      for (let i = 0; i < SPLASH; i++) {
        const [x, z, ph, per] = splashData[i];
        const k = ((t / per + ph) % 1 + 1) % 1;
        dp.set(x, 0.008, z); ds.setScalar(0.015 + 0.1 * k);
        dm.compose(dp, new THREE.Quaternion(), ds); splashes.setMatrixAt(i, dm);
        splashes.setColorAt(i, splashColor.setScalar(0.5 * (1 - k) * (1 - k)));
      }
      ds.setScalar(1);
      splashes.instanceMatrix.needsUpdate = true; splashes.instanceColor.needsUpdate = true;
      drops2.offset.y = t * 0.035;
      const f = ctx.flicker ?? 0;
      flickerTube.material.color.setRGB(3.4 * (1 - 0.85 * f), 3.7 * (1 - 0.85 * f), 3.5 * (1 - 0.85 * f));
      lastT = t;
    }
  }

  return {
    root, exterior, interior, update,
    anchors: { door, doorHinge, bin, binSign, counter, window: slogan },
    envs: { street: streetEnv, shop: shopEnv },
    atlases: { spines, covers },
  };
}
