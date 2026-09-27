/*
 * camera.js: PANCHIKO "Found". First-person camera for shots 1–2 (film 0 – 11.035 s).
 * Owner: cinematographer. Everything is a pure function of film time t (window-relative
 * seconds, 0 = song 176.016 s). There are no clocks and no randomness.
 *
 * ── WORLD COORDINATES (engine lead: build store.js to these, or tell me what to move) ──
 *   Units are metres, +y up, three.js right-handed. The street outside and the shop floor are
 *   both at y = 0: a flat pedestrian street with no kerb (a 2 cm threshold strip is fine).
 *   SHOPFRONT  The glazing line is the plane z = 0, facing +z. Street z > 0, interior z < 0.
 *              We walk along -z, starting about 4.3 m out at x ≈ +1.1.
 *   DOOR       Opening centred on x = 0, 1.00 m wide, 2.15 m high. The hinge is on the
 *              LEFT jamb (x = -0.50, seen from the street) and the door swings INWARD (-z).
 *              The push plate sits on the right: x = +0.32, y = 1.12, on the street face.
 *              Leaf angle = doorAt(t) · 90°, applied as leaf.rotation.y = +angle about the
 *              hinge (positive opens it inward). Keep x ∈ [-0.55, 0.55], z ∈ [-1.05, 0] clear.
 *   WINDOW     Main display window left of the door: x -4.2 … -0.70, y 0.45 … 2.45 (he looks
 *              into it from 1.4 s to 3.4 s). Right of the door, x 0.70 … 3.0, is free
 *              (a second window is suggested).
 *   AISLE      The walk corridor (≥ 0.9 m wide, keep it clear) runs from the door straight
 *              down x ≈ 0.1 to z ≈ -2, then bends slightly right to STAND (see below).
 *   BIN        "PRE-OWNED / DONATED CDs". Footprint centre (1.05, -3.85), 1.00 m wide ×
 *              0.60 m deep, CD tops at y 0.80, turned BIN.rotY = -35° about +y. Its browsing
 *              face (local +z) points at the aisle, toward world (-0.57, 0, 0.82). CDs stand
 *              upright in rows facing that side. The sign card ("PRE-OWNED / DONATED CDs")
 *              stands at the back edge, top at about y 1.10: BIN.sign. Its eye-catch is the
 *              cue for the head turn.
 *   STAND      Where he stops at the bin: BIN centre + 0.78 m along its browsing normal.
 *
 * ── TIMELINE (every anchor is a beat from work/music/timing.json, 1-based beat numbers) ──
 *   0.000  b1   Walking (steps on every beat, even steps = left foot, as body.js). Looking
 *               at the shopfront.
 *   1.379  b3   Head drifts left into the display window and scans it while walking.
 *   3.448  b6   (snare) Eyes go to the door: look first ...
 *   3.72        ... then the right hand rises into frame (handAt weight).
 *   4.138  b7   Palm meets the push plate; the door starts to move.
 *   4.60        Shove and release. The door swings to ~83° (doorAt); the hand drops out.
 *   5.517  b9   (downbeat, bar 3) Eye crosses the threshold z = 0. Shot 1 → shot 2 happens
 *               inside one continuous take; the lead can still hard-cut here.
 *   5.45–6.9    Eye adaptation to the bright shop (gradeAt().exposure bump). Grade crossfades
 *               street → store.
 *   6.207  b10  (snare) Lazy glance left at the racks and posters.
 *   7.586  b12  (snare) Back to the aisle ahead.
 *   8.966  b14  (snare) Head snaps right to the bin sign (min-jerk with 4 % overshoot). The body
 *               slows and follows.
 *   ~10.1       He stops at STAND. Stillness = attention (breathing only).
 *   10.345 b16  (snare + accent) Leans in and tilts down into the CDs.
 *   11.035 b17  Downbeat: cut to shot 3 (flicking in the bin).
 *
 * ── API ──
 *   cameraAt(t)   → { position: V3, quaternion: Quat, fov, yaw, pitch, roll (rad), speed (m/s),
 *                     walk (0..1), step (footfall count) }
 *   applyCamera(camera, t)   Sets position/quaternion/fov, updates the matrices, returns cameraAt(t).
 *   doorAt(t)     → 0..1: door leaf angle as a fraction of 90° (for store.js ctx.door).
 *   handAt(t)     → { weight 0..1, reach 0..1, push 0..1, target: V3, normal: V3 }: right palm
 *                     on the push plate (it follows the leaf while pushing).
 *   bodyPoseAt(t) → the pose object body.update(t, pose) takes, except `cam`.
 *   gradeAt(t)    → { grade: { street, store }, exposure } for look.js render params.
 *   footfalls     [{ t, n, side: 'L'|'R', x, z, weight }]: heel strikes (puddle splashes).
 *   useSync(sync) Adopts sync.js beats ({ beats: [s…] }) if they differ from the table below.
 *   Constants: EYE, VFOV, BEATS, DOOR, WINDOW, BIN, STAND, CUE.
 */
import * as THREE from 'three';

export const EYE = 1.68;        // eye height of a 1.80 m man
export const VFOV = 60;         // vertical FOV in degrees; in 4:5 that is ≈ 50° horizontal (≈ 28 mm feel)

// Beat times (film s) from work/music/timing.json → beats[].rel (87 BPM, straight grid).
export let BEATS = [0, 0.69, 1.379, 2.069, 2.759, 3.448, 4.138, 4.828, 5.517, 6.207, 6.897, 7.586,
  8.276, 8.966, 9.655, 10.345, 11.035, 11.724, 12.414, 13.104, 13.793, 14.483, 15.173, 15.862,
  16.552, 17.242, 17.931, 18.621, 19.311, 20, 20.69, 21.38, 22.069, 22.759, 23.449, 24.138, 24.828,
  25.518, 26.207, 26.897, 27.587, 28.276, 28.966, 29.656, 30.345, 31.035, 31.724, 32.414, 33.104,
  33.793, 34.483, 35.173, 35.862, 36.552, 37.242, 37.931, 38.621, 39.311, 40, 40.69, 41.38,
  42.069, 42.759, 43.449, 44.138, 44.828, 45.518, 46.207, 46.897, 47.587, 48.276, 48.966, 49.656,
  50.345, 51.035, 51.725, 52.414, 53.104, 53.794, 54.483, 55.173, 55.863, 56.552, 57.242, 57.932,
  58.621, 59.311, 60.001];
const beat = (n) => BEATS[n - 1];

const D2R = Math.PI / 180;
const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const smooth = (a, b, x) => { const k = clamp((x - a) / (b - a), 0, 1); return k * k * (3 - 2 * k); };
const minjerk = (x) => { x = clamp(x, 0, 1); return x * x * x * (10 + x * (6 * x - 15)); };
// Quick head turn: reach 104 % at 70 % of the time, then settle back to 100 % (C1 continuous).
const overshoot = (x) => (x < 0.7 ? 1.04 * minjerk(x / 0.7) : 1.04 - 0.04 * minjerk((x - 0.7) / 0.3));

// ── world ──────────────────────────────────────────────────────────────────────────────
export const DOOR = { x: 0, z: 0, width: 1.0, height: 2.15, hingeX: -0.5, plate: { x: 0.2, y: 1.3 }, maxDeg: 90 };
export const WINDOW = { x0: -4.2, x1: -0.7, y0: 0.45, y1: 2.45, z: 0 };
const binRot = -35 * D2R;
export const BIN = {
  x: 1.05, z: -3.85, width: 1.0, depth: 0.6, top: 0.8, rotY: binRot,
  front: V3(Math.sin(binRot), 0, Math.cos(binRot)),         // browsing side, world
};
BIN.sign = V3(BIN.x, 1.1, BIN.z).addScaledVector(BIN.front, -0.26);   // card at the back edge
BIN.cds = V3(BIN.x, 0.74, BIN.z).addScaledVector(BIN.front, 0.08);    // where the eyes land in the rows
export const STAND = V3(BIN.x, 0, BIN.z).addScaledVector(BIN.front, 0.78);

// ── paths (xz, y ignored). Signed distance d: d < 0 outside, d = 0 at the threshold ──────────
const OUT_PTS = [[1.30, 5.2], [1.02, 3.3], [0.45, 1.55], [0.10, 0.60], [0.08, 0.0]];
const IN_PTS = [[0.08, 0.0], [0.10, -1.0], [0.20, -1.95], [STAND.x, STAND.z]];
const mkCurve = (pts) => {
  const c = new THREE.CatmullRomCurve3(pts.map(([x, z]) => V3(x, 0, z)), false, 'centripetal');
  c.arcLengthDivisions = 2000; return c;
};
const OUT = mkCurve(OUT_PTS), IN = mkCurve(IN_PTS);
const L_OUT = OUT.getLength(), L_IN = IN.getLength();
function pathAt(d, out = new THREE.Vector3(), tan = new THREE.Vector3()) {
  if (d <= 0) {
    const u = clamp((L_OUT + d) / L_OUT, 0, 1);
    OUT.getPointAt(u, out); OUT.getTangentAt(u, tan);
    if (L_OUT + d < 0) out.addScaledVector(tan, L_OUT + d);            // before the path start
  } else {
    const u = clamp(d / L_IN, 0, 1);
    IN.getPointAt(u, out); IN.getTangentAt(u, tan);
  }
  return out;
}

// ── cues and the distance profile (cubic Hermite keys [t, d, v]) ─────────────────────────
export const CUE = {};
let DKEYS = [], DOOR_KEYS = [];
function build() {
  Object.assign(CUE, {
    start: beat(1), lookWindow: beat(3), lookDoor: beat(6), reach: 3.72, contact: beat(7),
    release: beat(7) + 0.462, threshold: beat(9), glanceLeft: beat(10), glanceBack: beat(12),
    binTurn: beat(14), leanIn: beat(16), end: beat(17),
  });
  const c = CUE;
  // Inside: aisle speed, then slow after the bin turn and stop exactly at STAND.
  const vIn = 0.9, dA = 0.5 * (0.5 + vIn) * (c.glanceLeft - c.threshold);         // threshold → b10
  const dB = dA + vIn * (beat(13) - c.glanceLeft);                                   // → b13
  const dC = dB + 0.5 * (vIn + 0.6) * (c.binTurn - beat(13));                        // → b14
  const stopT = c.binTurn + Math.max(L_IN - dC, 0.05) / 0.3;                         // linear 0.6 → 0
  CUE.stop = stopT;
  // Outside: steady 0.95 m/s, slowing into the push; contact at 0.42 m from the door (arm's reach, hand in frame).
  const dContact = -0.42, dRelease = -0.28;
  const dLook = dContact - 0.5 * (0.95 + 0.40) * (c.contact - c.lookDoor);
  const d0 = dLook - 0.95 * (c.lookDoor - c.start);
  DKEYS = [
    [c.start, d0, 0.95],
    [c.lookDoor, dLook, 0.95],
    [c.contact, dContact, 0.40],
    [c.release, dRelease, 0.30],
    [c.threshold, 0, 0.50],
    [c.glanceLeft, dA, vIn],
    [beat(13), dB, vIn],
    [c.binTurn, dC, 0.6],
    [stopT, L_IN, 0],
  ];
  // Door angle in degrees: push (0 → 12°), shove to ~83°, the closer brings it back behind us.
  DOOR_KEYS = [
    [c.contact, 0, 0], [c.release, 12, 55], [c.release + 0.72, 79, 25], [c.release + 1.05, 83, 0],
    [c.threshold + 1.45, 83, 0], [c.threshold + 3.35, 4, -14], [c.threshold + 3.6, 0, 0],
  ];
  buildFootfalls();
}

function hermite(keys, t) {
  const k0 = keys[0], kn = keys[keys.length - 1];
  if (t <= k0[0]) return { p: k0[1] + k0[2] * (t - k0[0]), v: k0[2] };
  if (t >= kn[0]) return { p: kn[1] + kn[2] * (t - kn[0]), v: kn[2] };
  let i = 0; while (t > keys[i + 1][0]) i++;
  const [t0, p0, m0] = keys[i], [t1, p1, m1] = keys[i + 1];
  const h = t1 - t0, u = (t - t0) / h, u2 = u * u, u3 = u2 * u;
  return {
    p: (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * h * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * h * m1,
    v: ((6 * u2 - 6 * u) * p0 + (3 * u2 - 4 * u + 1) * h * m0 + (-6 * u2 + 6 * u) * p1 + (3 * u2 - 2 * u) * h * m1) / h,
  };
}

/** Continuous footfall count: integer n = heel strike on beat n+1 (even = left foot). */
function stepCount(t) {
  if (t <= BEATS[0]) return (t - BEATS[0]) / (BEATS[1] - BEATS[0]);
  let i = 0; while (i < BEATS.length - 2 && t >= BEATS[i + 1]) i++;
  return i + (t - BEATS[i]) / (BEATS[i + 1] - BEATS[i]);
}
const walkWeight = (v) => smooth(0.06, 0.62, v);

// ── door + hand ────────────────────────────────────────────────────────────────────────
export function doorAt(t) { return clamp(hermite(DOOR_KEYS, t).p, 0, 90) / 90; }

function plateAt(deg) {
  const a = deg * D2R, r = DOOR.plate.x - DOOR.hingeX;                         // 0.82 m from the hinge
  const n = V3(Math.sin(a), 0, Math.cos(a));                                   // street-side face normal
  return { p: V3(DOOR.hingeX + r * Math.cos(a), DOOR.plate.y, -r * Math.sin(a)).addScaledVector(n, 0.03), n };
}

export function handAt(t) {
  const c = CUE;
  const reach = smooth(c.reach, c.contact, t) * (1 - smooth(c.contact, c.contact + 0.12, t));
  const push = smooth(c.contact - 0.06, c.contact + 0.06, t) * (1 - smooth(c.release, c.release + 0.45, t));
  const weight = Math.max(reach, push);
  const { p, n } = plateAt(90 * doorAt(Math.min(t, c.release)));
  if (t > c.release) p.y -= 0.35 * smooth(c.release, c.release + 0.45, t);     // hand drops away
  return { weight, reach, push, target: p, normal: n };
}

// ── gaze: world targets, blended by eased yaw/pitch ────────────────────────────────────
const SHOPFRONT_LOOK = V3(-0.55, 1.95, 0);
const PLATE_LOOK = V3(0.12, 1.4, 0);                      // glance down at the plate as the hand meets it
const THROUGH_DOOR = V3(0.05, 1.5, -8);
const LEFT_RACKS = V3(-2.3, 1.55, -3.0);
const AHEAD_IN = V3(0.45, 1.45, -9);
const windowPan = (t) => {                                // scans the display as we walk
  const k = smooth(CUE.lookWindow, CUE.lookDoor, t);
  return V3(-2.7 + 1.3 * k, 1.28 - 0.08 * k, 0.05);
};
function gazeKeys() {
  const c = CUE;
  return [
    { t: -1e9, dur: 1, to: () => SHOPFRONT_LOOK },
    { t: c.lookWindow, dur: 1.0, to: windowPan },
    { t: c.lookDoor, dur: 0.55, to: () => PLATE_LOOK },
    { t: c.contact + 0.2, dur: 0.85, to: () => THROUGH_DOOR },
    { t: c.glanceLeft, dur: 1.0, to: () => LEFT_RACKS },
    { t: c.glanceBack, dur: 0.9, to: () => AHEAD_IN },
    { t: c.binTurn, dur: 0.62, to: () => BIN.sign, ease: overshoot },
    { t: c.leanIn, dur: 0.66, to: () => BIN.cds },
  ];
}
const angles = (from, to) => {
  const dx = to.x - from.x, dy = to.y - from.y, dz = to.z - from.z;
  return [Math.atan2(-dx, -dz), Math.atan2(dy, Math.hypot(dx, dz))];
};
const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));
function gazeAt(t, from) {
  const G = gazeKeys();
  let i = 0; while (i < G.length - 1 && t >= G[i + 1].t) i++;
  const cur = G[i], [y1, p1] = angles(from, cur.to(t));
  if (i === 0) return [y1, p1];
  const prev = G[i - 1], [y0, p0] = angles(from, prev.to(t));
  const e = (cur.ease || minjerk)((t - cur.t) / cur.dur);
  return [y0 + wrap(y1 - y0) * e, p0 + (p1 - p0) * e];
}

// ── the camera ─────────────────────────────────────────────────────────────────────────
const TAU = Math.PI * 2;
const s = (f, ph, t) => Math.sin(TAU * f * t + ph);

export function cameraAt(tIn) {
  const t = Math.min(tIn, CUE.end);
  const { p: dRaw, v } = hermite(DKEYS, t);
  const w = walkWeight(v);
  const n = stepCount(t), ph = TAU * n;
  const d = dRaw + 0.004 * w * Math.sin(ph);                                   // per-step surge
  const tan = new THREE.Vector3();
  const base = pathAt(d, new THREE.Vector3(), tan);
  const right = V3(-tan.z, 0, tan.x).normalize();

  // Neck pivot: body path + lateral sway over the stance foot (even count = left foot),
  // vertical bob lowest just after each heel strike, breathing.
  const neck = base.clone()
    .addScaledVector(right, -0.011 * w * Math.sin(Math.PI * n));
  neck.y = EYE - 0.10 - 0.013 * w * Math.cos(ph - 0.35) + 0.0035 * s(1 / 3.9, 0, t);

  // Lean into the bin on the b16 snare.
  const lean = minjerk((t - CUE.leanIn) / 0.7);
  if (lean > 0) {
    const toBin = V3(BIN.x - STAND.x, 0, BIN.z - STAND.z).normalize();
    neck.addScaledVector(toBin, 0.17 * lean); neck.y -= 0.06 * lean;
  }

  let [yaw, pitch] = gazeAt(t, neck);
  let roll = 0;
  // Walk: nod after each strike, roll toward the stance side, a hint of counter-yaw.
  pitch += -0.25 * D2R * w * Math.cos(ph - 0.6);
  roll += 0.30 * D2R * w * Math.sin(Math.PI * n);
  yaw += 0.22 * D2R * w * Math.sin(Math.PI * n + 0.5);
  // Breathing + micro-sway (incommensurate sines, all ≤ 0.1°).
  pitch += 0.20 * D2R * s(1 / 3.9, -0.8, t);
  yaw += D2R * (0.10 * s(0.13, 0.4, t) + 0.06 * s(0.31, 2.1, t) + 0.035 * s(0.57, 4.0, t));
  pitch += D2R * (0.08 * s(0.11, 1.1, t) + 0.05 * s(0.37, 0.3, t) + 0.03 * s(0.61, 5.2, t));
  roll += D2R * (0.06 * s(0.09, 3.3, t) + 0.03 * s(0.43, 1.7, t));

  const quaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(pitch, yaw, roll, 'YXZ'));
  // Eyes sit 0.10 m above and 0.09 m in front of the neck pivot, so head turns carry parallax.
  const position = neck.clone().add(V3(0, 0.10, -0.09).applyQuaternion(quaternion));
  return { position, quaternion, fov: VFOV, yaw, pitch, roll, speed: v, walk: w, step: n };
}

export function applyCamera(camera, t) {
  const c = cameraAt(t);
  camera.position.copy(c.position); camera.quaternion.copy(c.quaternion);
  if (camera.fov !== c.fov) { camera.fov = c.fov; camera.updateProjectionMatrix(); }
  camera.updateMatrixWorld();
  return c;
}

// ── helpers for the other modules ──────────────────────────────────────────────────────
export function gradeAt(t) {
  const store = smooth(CUE.threshold - 0.55, CUE.threshold + 0.25, t);
  // Eye adaptation: stepping into the bright shop over-exposes a touch, then settles.
  const adapt = smooth(CUE.threshold - 0.1, CUE.threshold + 0.2, t) * (1 - smooth(CUE.threshold + 0.2, CUE.threshold + 1.4, t));
  return { grade: { street: 1 - store, store }, exposure: 1 + 0.22 * adapt };
}

export function bodyPoseAt(t) {
  const c = cameraAt(t), h = handAt(t);
  return {
    walk: c.walk, step: c.step, armSwing: 0.6 * (1 - h.weight),
    reachDoor: h.reach, pushDoor: h.push, target: h.target, targetNormal: h.normal,
    env: t < CUE.threshold ? 'street' : 'shop',
  };
}

export let footfalls = [];
function buildFootfalls() {
  footfalls = [];
  const tan = new THREE.Vector3();
  for (let i = 0; i < BEATS.length && BEATS[i] <= CUE.end + 1e-6; i++) {
    const t = BEATS[i], { p: d, v } = hermite(DKEYS, t), w = walkWeight(v);
    if (w < 0.15) continue;
    const side = i % 2 === 0 ? 'L' : 'R';
    const p = pathAt(d + 0.12, new THREE.Vector3(), tan);                      // foot lands a little ahead
    const r = V3(-tan.z, 0, tan.x).normalize();
    p.addScaledVector(r, side === 'L' ? -0.11 : 0.11);
    footfalls.push({ t, n: i, side, x: p.x, z: p.z, weight: w });
  }
}

export function useSync(sync) {
  if (!sync || !Array.isArray(sync.beats) || sync.beats.length < 20) return;
  const b = sync.beats.map((x) => (typeof x === 'number' ? x : x.rel ?? x.t));
  if (b.every((x, i) => Math.abs(x - (BEATS[i] ?? x)) < 1e-4)) return;
  BEATS = b; build();
}

build();
