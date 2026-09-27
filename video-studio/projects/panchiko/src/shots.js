/*
 * shots.js — shots 3–10 of "Found" (film 11.035 s → 60.69 s); camera.js covers shots 1–2.
 *
 *   shotAt(t) → { scene: 'store' | 'field', pos: V3, look: V3, pose: {...body.update pose},
 *                 hero: { show, flip }, player: { show, lid, lcd, spin }, flash }
 *
 * Every moment hangs off the song (sync.js beats): the flicks land on snares, the case
 * comes up on the last snare before the drop-out, the player is loaded in the quiet, and
 * play is pressed on the slam at 22.069 s, where the shop blooms white into the field.
 */
import * as THREE from 'three';
import sync from './sync.js';
import { BIN, STAND } from './camera.js';
import { terrainHeight } from './field.js';

const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const smooth = (a, b, x) => { const k = clamp((x - a) / (b - a), 0, 1); return k * k * (3 - 2 * k); };
const beat = (n) => sync.beats[n - 1];                       // 1-based, as in copy.js

export const T = {
  start: beat(17),          // 11.035 downbeat: cut to the bin
  flickEnd: beat(23),       // 15.173: the last flick lands, fingers stop on it
  lift: beat(24) - 0.2,     // it comes up out of the row
  show: beat(26),           // 17.242: the drop-out — the cover in the light
  turn: beat(28) - 0.3,     // turned over: track titles, no surnames
  player: beat(29),         // 19.311 downbeat: into the player
  lid: beat(30),
  reading: beat(32) - 0.45,
  slam: beat(33),           // 22.069: PLAY — the full band comes in
  stop: beat(61),           // 41.380: stands still
  rise: beat(65),           // 44.138: the title rises, one group per beat
  cards: beat(77),          // 52.414
  title: beat(84),          // 57.242
  end: sync.WINDOW.duration,
};

// ---- the shop: at the bin ------------------------------------------------------------------
const EYE_BIN = STAND.clone().addScaledVector(BIN.front, -0.1).setY(1.6);
const IN_ROWS = BIN.cds.clone();

function flickPhase(t) {
  // One flick per snare between the cut and the stop; fractional progress between snares.
  const hits = sync.snares.filter((s) => s >= T.start - 0.05 && s <= T.flickEnd + 0.05);
  let n = 0;
  while (n < hits.length && hits[n] <= t) n++;
  if (n === 0) return 0;
  const prev = hits[n - 1], next = hits[n] ?? prev + 0.35;
  return n - 1 + clamp((t - prev) / Math.min(0.3, next - prev), 0, 1);
}

function storeShot(t) {
  const lean = smooth(T.start, T.start + 0.8, t) * 0.08 + smooth(T.flickEnd, T.lift, t) * 0.07;
  const pos = EYE_BIN.clone().addScaledVector(BIN.front, -lean);
  pos.y -= lean * 0.6;
  const lifting = smooth(T.lift, T.show, t);
  // The case: from its slot in the rows up to the hands, 0.34 m in front of the eye.
  const inHands = pos.clone().add(V3(0, -0.17, 0)).addScaledVector(BIN.front, -0.32);
  const caseAt = IN_ROWS.clone().lerp(inHands, lifting);
  const look = IN_ROWS.clone().lerp(caseAt, smooth(T.flickEnd - 0.2, T.show, t));
  const flicking = t < T.flickEnd + 0.25;
  const pose = {
    walk: 0, step: 0, armSwing: 0, env: 'shop',
    flick: flicking ? 1 - smooth(T.flickEnd, T.flickEnd + 0.25, t) : 0,
    flickPhase: flickPhase(t),
    target: IN_ROWS.clone().add(V3(0, 0.03, 0)), targetNormal: BIN.front.clone(),
    holdCase: smooth(T.flickEnd + 0.1, T.lift + 0.2, t),
    caseAt,
  };
  return {
    scene: 'store', pos, look, pose,
    hero: { show: t >= T.flickEnd - 0.05 && t < T.player, flip: smooth(T.turn, T.turn + 0.8, t) },
    player: { show: t >= T.player, lid: 1 - smooth(T.lid, T.lid + 0.7, t), lcd: t >= T.slam - 0.02 ? 'play' : t >= T.reading ? 'reading' : 'idle', spin: t >= T.reading ? (t - T.reading) : 0 },
    flash: smooth(T.slam - 0.12, T.slam, t),
  };
}

// ---- the field ----------------------------------------------------------------------------
const WALK = 0.72;                                             // m/s, one step per beat
function fieldPath(t) {
  const walked = Math.min(t, T.stop) - T.slam;
  const settle = t > T.stop ? WALK * 0.35 * (1 - Math.exp(-(t - T.stop) * 3)) : 0;
  const d = Math.max(0, walked) * WALK + settle;
  const x = 0.8 * Math.sin(d * 0.07) - 0.25 * d * 0.05;
  const z = -d;
  return V3(x, terrainHeight(x, z) + 1.62, z);
}

function fieldShot(t) {
  const pos = fieldPath(t);
  const walking = 1 - smooth(T.stop - 0.4, T.stop + 0.3, t);
  // Where he looks: the grass and the land ahead; up into the sky at the stop; then the title.
  const ahead = V3(pos.x + 0.6 * Math.sin(t * 0.21), pos.y - 0.9 + 0.25 * Math.sin(t * 0.33), pos.z - 6);
  const sky = V3(pos.x - 1.5, pos.y + 5.5, pos.z - 6);
  const title = V3(0, terrainHeight(0, -62) + 5, -62);
  let look = ahead.clone().lerp(sky, smooth(T.stop, T.stop + 1.6, t));
  look.lerp(title, smooth(T.rise - 0.6, T.rise + 0.6, t));
  look.lerp(V3(0, terrainHeight(0, -54) + 10.5, -54), smooth(T.cards - 0.3, T.cards + 1.2, t) * (1 - smooth(T.title - 0.5, T.title + 0.6, t)));
  // The right hand trails through the grass tips while he walks.
  const ground = terrainHeight(pos.x + 0.35, pos.z - 0.4);
  const brush = walking * (0.7 + 0.3 * Math.sin(t * 1.7));
  return {
    scene: 'field', pos, look,
    pose: {
      walk: walking, step: (t - T.slam) / (sync.BEAT), armSwing: 0.5, env: 'field',
      reachDoor: brush * 0.8,
      target: V3(pos.x + 0.36 + 0.05 * Math.sin(t * 2.1), ground + 0.62, pos.z - 0.42), targetNormal: V3(0, 1, 0),
    },
    hero: { show: false }, player: { show: false },
    flash: 1 - smooth(T.slam, T.slam + 0.55, t),
  };
}

export function shotAt(t) {
  return t < T.slam ? storeShot(t) : fieldShot(t);
}
