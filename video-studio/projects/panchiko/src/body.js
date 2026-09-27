/*
 * body.js — the first-person body (asset scout).
 *
 * Quaternius "Universal Base Characters" male (CC0) with a light skin tone (texture re-toned
 * offline), a dark jacket and jeans painted + slightly inflated in the shader from bind-pose
 * zones, animated with Quaternius "Universal Animation Library 1" clips (CC0: Walk_Loop,
 * Idle_Loop) and procedural bones: two-bone arm IK to a palm target, hand orientation, per-finger
 * curl/spread, spine pitch that follows the camera. Every call is a pure function of (t, pose).
 *
 *   import { createBody } from './body.js';
 *   const body = await createBody({ renderer });           // loads ../assets/body/*, ../assets/env/*
 *   scene.add(body.root);
 *   Studio.onFrame((t) => {
 *     body.update(t, {
 *       cam: camera,                 // required: anything with .position + .quaternion (world);
 *                                    //   the body is placed so its eyes sit exactly at cam.position
 *       walk: 1,                     // 0..1 idle ↔ walk (legs, torso, arm swing)
 *       step: t / BEAT,              // footfall count: integers are heel strikes (even = left foot)
 *       armSwing: 0.6,               // 0..1 how much of the clip's arm swing to keep ("subtle")
 *       reachDoor: 0, pushDoor: 0,   // 0..1 right-arm pose weights (sum ≤ 1 is the arm IK weight)
 *       flick: 0, flickPhase: 0,     // flick: index/middle flick CDs; phase: +1 per flick
 *       holdCase: 0,                 // both hands hold a jewel case (attach it to body.anchors.case)
 *       target: V3, targetNormal: V3,// world contact point (door push point / bin) + surface normal
 *                                    //   facing the viewer; omitted → camera-relative defaults
 *       caseAt: V3,                  // world centre of the held case (default: in front of camera)
 *       env: 'street' | 'shop', envIntensity: 1,
 *     });
 *   });
 *   body.anchors: { handR, handL, palmR, palmL, case }   // Object3Ds to attach props to
 *   body.setEnv(nameOrTexture, intensity, rotY)           // lighting (MeshStandard + PMREM env)
 *   body.hideHead(bool)                                   // true (default) for first person
 *
 * Right-hand IK: the palm centre (on the palm skin) goes to the target; the arm solves with the
 * elbow pointing down/out, half the wrist twist goes into the forearm (no candy-wrap), and the
 * palm is kept ≥ 0.22 m from the eye so it never clips the near plane.
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';

export const BEAT = 0.68966;
const ASSET = (p) => new URL(`../assets/${p}`, import.meta.url).href;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const smooth = (a, b, x) => { const k = clamp((x - a) / (b - a), 0, 1); return k * k * (3 - 2 * k); };
const V = () => new THREE.Vector3();
const Q = () => new THREE.Quaternion();
const X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(0, 1, 0), Z = new THREE.Vector3(0, 0, 1);

const FINGERS = ['index', 'middle', 'ring', 'pinky'];
// curl (rad) at curl = 1 for joints 01, 02, 03
const CURL_MAX = { finger: [1.45, 1.75, 1.2], thumb: [0.35, 0.8, 1.0] };

// ---- shader: clothes from bind-pose zones -------------------------------------------------
const ZONES = /* glsl */`
  uniform float uWristX, uHemY, uNeckY, uAnkleY, uHideHead;
  varying vec3 vRest;
  // returns (hand, jacket, jeans, shoe) weights from the bind-pose position
  vec4 bodyZones(vec3 p) {
    float hand = smoothstep(uWristX - 0.030, uWristX - 0.022, abs(p.x));
    float head = step(uNeckY, p.y) * (1.0 - hand);
    float leg = 1.0 - smoothstep(uHemY - 0.004, uHemY + 0.004, p.y);
    float shoe = 1.0 - smoothstep(uAnkleY - 0.004, uAnkleY + 0.004, p.y);
    float jacket = (1.0 - hand) * (1.0 - head) * (1.0 - leg);
    return vec4(hand, jacket, leg * (1.0 - shoe), shoe);
  }
  float h3(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
  float vnoise(vec3 x) {
    vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(h3(i), h3(i + vec3(1,0,0)), f.x), mix(h3(i + vec3(0,1,0)), h3(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(h3(i + vec3(0,0,1)), h3(i + vec3(1,0,1)), f.x), mix(h3(i + vec3(0,1,1)), h3(i + vec3(1,1,1)), f.x), f.y), f.z);
  }`;

function patchMaterial(mat, U) {
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', `#include <common>\n${ZONES}`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        vRest = position;
        vec4 zb = bodyZones(position);
        // inflate clothes along the bind-pose normal (cuff a little thicker than the sleeve)
        float cuff = zb.y * smoothstep(uWristX - 0.075, uWristX - 0.045, abs(position.x));
        transformed += normal * (zb.y * 0.016 + cuff * 0.005 + zb.z * 0.006 + zb.w * 0.012);`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>\n${ZONES}\nuniform vec3 uJacket, uJeans, uShoe;`)
      .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
        vec4 zf = bodyZones(vRest);
        if (uHideHead > 0.5 && vRest.y > uNeckY + 0.035 && abs(vRest.x) < 0.2) discard;
        float cloth = zf.y + zf.z + zf.w;
        float nz = vnoise(vRest * 90.0) * 0.6 + vnoise(vRest * 23.0) * 0.4;`)
      .replace('#include <map_fragment>', `#include <map_fragment>
        {
          float cuffBand = zf.y * smoothstep(uWristX - 0.075, uWristX - 0.06, abs(vRest.x));
          float hem = zf.y * (1.0 - smoothstep(uHemY + 0.01, uHemY + 0.045, vRest.y));
          vec3 jk = uJacket * (0.86 + 0.28 * nz) * (1.0 - 0.28 * max(cuffBand, hem));
          vec3 jn = uJeans * (0.8 + 0.4 * nz);
          vec3 sh = uShoe * (0.9 + 0.2 * nz);
          diffuseColor.rgb = mix(diffuseColor.rgb, jk * zf.y + jn * zf.z + sh * zf.w, clamp(cloth, 0.0, 1.0));
        }`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        roughnessFactor = mix(roughnessFactor, 0.72 + 0.12 * nz, clamp(cloth, 0.0, 1.0));`)
      .replace('#include <normal_fragment_begin>', '#include <normal_fragment_begin>\nvec3 nGeo = normal;')
      .replace('#include <normal_fragment_maps>', '#include <normal_fragment_maps>\nnormal = normalize(mix(normal, nGeo, clamp(cloth, 0.0, 1.0)));');
  };
  mat.customProgramCacheKey = () => 'panchiko-body-v1';
}

// ---- clip sampling (rotations only; the body is pinned to the camera) ------------------------
function makeSampler(clip, bones) {
  const tracks = [];
  for (const tr of clip.tracks) {
    const i = tr.name.lastIndexOf('.');
    const bone = bones[tr.name.slice(0, i)];
    if (bone && tr.name.slice(i + 1) === 'quaternion') tracks.push({ name: bone.name, interp: tr.createInterpolant() });
  }
  return {
    duration: clip.duration,
    sample(time, out) {
      const tt = ((time % clip.duration) + clip.duration) % clip.duration;
      for (const k of tracks) { const v = k.interp.evaluate(tt); (out[k.name] ||= Q()).set(v[0], v[1], v[2], v[3]); }
      return out;
    },
  };
}

export async function createBody({ renderer, eyeHeight = 1.66 } = {}) {
  const loader = new GLTFLoader();
  const rgbe = new RGBELoader();
  const [gBody, gClips, hShop, hStreet] = await Promise.all([
    loader.loadAsync(ASSET('body/ubc_male.glb')), loader.loadAsync(ASSET('body/ual1_clips.glb')),
    rgbe.loadAsync(ASSET('env/phone_shop_1k.hdr')), rgbe.loadAsync(ASSET('env/cobblestone_street_night_1k.hdr')),
  ]);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envs = { shop: pmrem.fromEquirectangular(hShop).texture, street: pmrem.fromEquirectangular(hStreet).texture };
  hShop.dispose(); hStreet.dispose(); pmrem.dispose();

  const model = gBody.scene;
  const bones = {}; let skin = null; const extras = [];
  model.traverse((o) => {
    if (o.isBone) bones[o.name] = o;
    if (o.isSkinnedMesh) { o.frustumCulled = false; if (o.name === 'SuperHero_Male') skin = o; else extras.push(o); }
  });
  model.updateMatrixWorld(true);

  // ---- rest data (model space = bind space) ----
  const rest = {};
  for (const [n, b] of Object.entries(bones)) rest[n] = { q: b.quaternion.clone(), wq: b.getWorldQuaternion(Q()), wp: b.getWorldPosition(V()) };
  const eyeAttr = extras.find((m) => m.name === 'Eyes')?.geometry.attributes.position;
  const eyeRest = V(); if (eyeAttr) { for (let i = 0; i < eyeAttr.count; i++) eyeRest.add(V().fromBufferAttribute(eyeAttr, i)); eyeRest.divideScalar(eyeAttr.count); } else eyeRest.set(0, 1.698, 0.066);
  const eyeLocal = bones.Head.worldToLocal(eyeRest.clone());
  const S = eyeHeight / eyeRest.y;
  const sideSign = rest.hand_r.wp.x < 0 ? 1 : -1;        // model faces +Z; right hand is on -X

  // per hand: finger direction, palm normal (rest pose: palms down), palm centre, finger axes
  const hands = {};
  for (const s of ['r', 'l']) {
    const h = rest[`hand_${s}`], hq = h.wq.clone().invert();
    const mid = rest[`middle_01_${s}`].wp, idx = rest[`index_01_${s}`].wp, pin = rest[`pinky_01_${s}`].wp;
    const fW = mid.clone().sub(h.wp).normalize();
    // palm normal: the side the clip's relaxed fist curls towards (checked against -Y)
    let nW = new THREE.Vector3(0, -1, 0);
    nW.sub(fW.clone().multiplyScalar(nW.dot(fW))).normalize();
    const fL = fW.clone().applyQuaternion(hq), nL = nW.clone().applyQuaternion(hq);
    const palmL = mid.clone().sub(h.wp).multiplyScalar(0.55).applyQuaternion(hq).add(nL.clone().multiplyScalar(0.02));
    const joints = {};
    for (const f of [...FINGERS, 'thumb']) {
      for (let j = 1; j <= 3; j++) {
        const b = `${f}_0${j}_${s}`, c = `${f}_0${j + 1}${j === 3 ? '_leaf' : ''}_${s}`;
        const child = rest[c] || rest[`${f}_04_leaf_${s}`];
        const d = child.wp.clone().sub(rest[b].wp).normalize();
        const axisW = d.clone().cross(nW).normalize();
        let spreadAxis = null;
        if (j === 1 && f !== 'thumb' && f !== 'middle') {
          const lat = rest[b].wp.clone().sub(mid); lat.sub(fW.clone().multiplyScalar(lat.dot(fW))).normalize();
          spreadAxis = d.clone().cross(lat).normalize().applyQuaternion(rest[b].wq.clone().invert());
        }
        joints[b] = { axis: axisW.applyQuaternion(rest[b].wq.clone().invert()), spreadAxis, kind: f === 'thumb' ? 'thumb' : 'finger', j: j - 1 };
      }
    }
    const lower = rest[`lowerarm_${s}`], upper = rest[`upperarm_${s}`];
    hands[s] = {
      fL, nL, bL: fL.clone().cross(nL).normalize(), palmL, joints,
      L1: lower.wp.distanceTo(upper.wp) * S, L2: h.wp.distanceTo(lower.wp) * S,
      twistAxisL: bones[`hand_${s}`].position.clone().normalize(),   // forearm → wrist, in forearm space
    };
  }

  // ---- materials ----
  const U = {
    uWristX: { value: Math.abs(rest.hand_r.wp.x) }, uHemY: { value: rest.pelvis.wp.y + 0.03 },
    uNeckY: { value: rest.neck_01.wp.y + 0.03 }, uAnkleY: { value: rest.foot_r.wp.y + 0.035 }, uHideHead: { value: 1 },
    uJacket: { value: new THREE.Color(0x1d2127) }, uJeans: { value: new THREE.Color(0x2a3b58) }, uShoe: { value: new THREE.Color(0x1a1a1c) },
  };
  const mat = skin.material;
  mat.side = THREE.FrontSide;
  patchMaterial(mat, U);
  const allMats = [mat, ...extras.map((m) => m.material)];
  for (const m of allMats) { m.envMapRotation = new THREE.Euler(); }
  const setEnv = (e = 'shop', intensity = 1, rotY = 0) => {
    const tex = typeof e === 'string' ? envs[e] : e;
    for (const m of allMats) { m.envMap = tex; m.envMapIntensity = intensity; m.envMapRotation.set(0, rotY, 0); }
  };
  setEnv('shop', 1);
  const hideHead = (on = true) => { U.uHideHead.value = on ? 1 : 0; for (const m of extras) m.visible = !on; };
  hideHead(true);

  // ---- scene graph ----
  const root = new THREE.Group(); root.name = 'body';
  model.scale.setScalar(S);
  root.add(model);
  const anchors = { handR: bones.hand_r, handL: bones.hand_l, palmR: new THREE.Object3D(), palmL: new THREE.Object3D(), case: new THREE.Object3D() };
  anchors.palmR.position.copy(hands.r.palmL); bones.hand_r.add(anchors.palmR);
  anchors.palmL.position.copy(hands.l.palmL); bones.hand_l.add(anchors.palmL);
  root.add(anchors.case);

  // ---- clips ----
  const clip = (n) => gClips.animations.find((a) => a.name === n);
  const walk = makeSampler(clip('Walk_Loop'), bones), idle = makeSampler(clip('Idle_Loop'), bones);
  // heel-strike offset: the time the left foot is furthest forward (model +Z) = footfall
  let heel = 0; {
    const tmp = {}; let best = -1e9;
    for (let i = 0; i < 96; i++) {
      const tt = (i / 96) * walk.duration; walk.sample(tt, tmp);
      for (const [n, q] of Object.entries(tmp)) bones[n].quaternion.copy(q);
      model.updateMatrixWorld(true);
      const z = bones.foot_l.getWorldPosition(V()).z - bones.pelvis.getWorldPosition(V()).z;
      if (z > best) { best = z; heel = tt; }
    }
  }
  const ARM = new Set(Object.keys(bones).filter((n) => /^(clavicle|upperarm|lowerarm|hand|index|middle|ring|pinky|thumb)_/.test(n)));

  // ---- scratch ----
  const pw = {}, pi = {}, qa = Q(), qb = Q(), qc = Q(), va = V(), vb = V(), vc = V(), vd = V(), m3 = new THREE.Matrix4(), m4 = new THREE.Matrix4();
  const camPos = V(), camQ = Q(), fwd = V(), right = V(), up = V();

  const setWorldQ = (bone, wq) => { bone.parent.getWorldQuaternion(qa); bone.quaternion.copy(qa.invert().multiply(wq)); bone.updateMatrixWorld(true); };
  const rotWorld = (bone, axis, ang) => { bone.getWorldQuaternion(qb); qc.setFromAxisAngle(axis, ang).multiply(qb); setWorldQ(bone, qc); };
  const aim = (bone, child, target) => {           // rotate bone so bone→child points at target
    const p = bone.getWorldPosition(V()), c = child.getWorldPosition(V());
    const from = c.sub(p).normalize(), to = target.clone().sub(p).normalize();
    bone.getWorldQuaternion(qb); qc.setFromUnitVectors(from, to).multiply(qb); setWorldQ(bone, qc);
  };
  const handWorldQ = (h, fW, nW, out) => {        // world quat taking (fL, nL) → (fW, nW)
    const f = fW.clone().normalize(), n = nW.clone().sub(f.clone().multiplyScalar(nW.dot(f))).normalize(), b = f.clone().cross(n);
    m3.makeBasis(f, n, b); m4.makeBasis(h.fL, h.nL, h.bL).transpose();
    return out.setFromRotationMatrix(m3.multiply(m4));
  };

  // solve one arm: palm centre → P (world), finger dir F, palm normal N, curls {index,middle,ring,pinky,thumb}, spread
  function solveArm(s, P, F, N, curls, spread, pole) {
    const h = hands[s], upper = bones[`upperarm_${s}`], lower = bones[`lowerarm_${s}`], hand = bones[`hand_${s}`];
    const hq = handWorldQ(h, F, N, Q());
    // wrist target = palm target − palm offset (in world, scaled)
    const T = P.clone().sub(h.palmL.clone().multiplyScalar(S).applyQuaternion(hq));
    const Sh = upper.getWorldPosition(V());
    const d = T.clone().sub(Sh); const len = d.length(); const dir = d.normalize();
    const reach = (h.L1 + h.L2) * 0.995, dist = clamp(len, 0.08, reach);
    const a = (h.L1 * h.L1 - h.L2 * h.L2 + dist * dist) / (2 * dist), hh = Math.sqrt(Math.max(h.L1 * h.L1 - a * a, 0));
    const perp = pole.clone().sub(dir.clone().multiplyScalar(pole.dot(dir))).normalize();
    const E = Sh.clone().add(dir.clone().multiplyScalar(a)).add(perp.multiplyScalar(hh));
    const W = Sh.clone().add(dir.clone().multiplyScalar(dist));
    aim(upper, lower, E);
    aim(lower, hand, W);
    // hand orientation, half of the twist into the forearm
    lower.getWorldQuaternion(qa); const loc = qa.clone().invert().multiply(hq);        // desired hand local
    const D = loc.multiply(rest[`hand_${s}`].q.clone().invert());                       // change vs rest, forearm frame
    const ax = h.twistAxisL, pr = vd.set(D.x, D.y, D.z).projectOnVector(ax);
    const twist = new THREE.Quaternion(pr.x, pr.y, pr.z, D.w).normalize();
    const half = Q().slerp(twist, 0.5);
    lower.quaternion.multiply(half); lower.updateMatrixWorld(true);
    setWorldQ(hand, hq);
    // fingers
    for (const [b, jn] of Object.entries(h.joints)) {
      const f = b.split('_')[0];
      const c = (curls[f] ?? 0.3) * CURL_MAX[jn.kind][jn.j];
      const bone = bones[b];
      bone.quaternion.copy(rest[b].q).multiply(qa.setFromAxisAngle(jn.axis, c));
      if (jn.spreadAxis && spread) bone.quaternion.multiply(qb.setFromAxisAngle(jn.spreadAxis, spread * ({ index: 0.12, ring: 0.1, pinky: 0.22 }[f] || 0)));
    }
    hand.updateMatrixWorld(true);
  }

  const captureArm = (s, out) => { for (const n of ARM) if (n.endsWith(`_${s}`)) (out[n] ||= Q()).copy(bones[n].quaternion); return out; };
  const clipArm = { r: {}, l: {} }, ikArm = { r: {}, l: {} };

  // camera-space → world helpers
  const camPt = (x, y, z) => V().set(x, y, z).applyQuaternion(camQ).add(camPos);
  const camDir = (x, y, z) => V().set(x, y, z).applyQuaternion(camQ).normalize();

  function update(t, pose = {}) {
    const cam = pose.cam; if (!cam) return;
    camPos.copy(cam.position); camQ.copy(cam.quaternion);
    if (pose.env !== undefined || pose.envIntensity !== undefined) setEnv(pose.env ?? 'shop', pose.envIntensity ?? 1, pose.envRotY ?? 0);
    fwd.set(0, 0, -1).applyQuaternion(camQ);
    const yaw = Math.atan2(fwd.x, fwd.z), pitch = Math.asin(clamp(fwd.y, -1, 1));

    // 1) clip pose: idle ↔ walk, arms with reduced swing
    const wWalk = clamp(pose.walk ?? 0, 0, 1), swing = clamp(pose.armSwing ?? 0.6, 0, 1);
    const step = pose.step ?? t / BEAT;
    walk.sample(heel + (step / 2) * walk.duration, pw);
    idle.sample(t, pi);
    for (const n in bones) {
      const a = pi[n], b = pw[n]; if (!a || !b) continue;
      bones[n].quaternion.copy(a).slerp(b, ARM.has(n) ? wWalk * swing : wWalk);
    }
    // 2) place: yaw from the camera, spine follows pitch, eyes pinned to the camera
    root.position.set(0, 0, 0); root.quaternion.setFromAxisAngle(Y, yaw); root.updateMatrixWorld(true);
    right.set(-sideSign, 0, 0).applyQuaternion(root.quaternion); up.set(0, 1, 0);
    // a positive rotation about the body's right axis tilts forward vectors up (= positive pitch)
    const pr = [['spine_02', 0.12], ['spine_03', 0.13], ['neck_01', 0.25], ['Head', 0.5]];
    for (const [n, k] of pr) rotWorld(bones[n], right, pitch * k);
    model.updateMatrixWorld(true);
    const eye = bones.Head.localToWorld(eyeLocal.clone());
    root.position.add(camPos.clone().sub(eye)); root.updateMatrixWorld(true);

    // 3) arm poses
    const wReach = clamp(pose.reachDoor ?? 0, 0, 1), wPush = clamp(pose.pushDoor ?? 0, 0, 1);
    const wFlick = clamp(pose.flick ?? 0, 0, 1), wHold = clamp(pose.holdCase ?? 0, 0, 1);
    const wR = clamp(wReach + wPush + wFlick + wHold, 0, 1);
    const tgt = pose.target ? pose.target.clone() : camPt(0.17, -0.27, -0.52);
    const tN = pose.targetNormal ? pose.targetNormal.clone().normalize() : camDir(0, 0, 1);
    const caseAt = pose.caseAt ? pose.caseAt.clone() : camPt(0.0, -0.14, -0.34);
    const caseN = camPos.clone().sub(caseAt).normalize();                  // case faces the eye
    const caseR = up.clone().cross(caseN).normalize(), caseU = caseN.clone().cross(caseR).normalize();
    anchors.case.position.copy(root.worldToLocal(caseAt.clone()));
    m3.makeBasis(caseR, caseU, caseN); anchors.case.quaternion.setFromRotationMatrix(m3).premultiply(root.quaternion.clone().invert());

    const poleR = right.clone().multiplyScalar(0.55).add(V().set(0, -1, 0)).add(fwd.clone().setY(0).normalize().multiplyScalar(-0.25)).normalize();
    const poleL = right.clone().multiplyScalar(-0.55).add(V().set(0, -1, 0)).add(fwd.clone().setY(0).normalize().multiplyScalar(-0.25)).normalize();

    const ensureAway = (P) => {                                           // keep ≥ 0.22 m in front of the eye
      const c = P.clone().sub(camPos).applyQuaternion(camQ.clone().invert());
      if (c.z > -0.22) c.z = -0.22; return c.applyQuaternion(camQ).add(camPos);
    };
    const inward = (s) => right.clone().multiplyScalar(s === 'r' ? -1 : 1);

    if (wR > 0.001) {
      captureArm('r', clipArm.r);
      // blend the pose targets
      const acc = { P: V(), F: V(), N: V(), curls: { index: 0, middle: 0, ring: 0, pinky: 0, thumb: 0 }, spread: 0 };
      const add = (w, P, F, N, c, sp) => {
        if (w <= 0) return; acc.P.addScaledVector(P, w); acc.F.addScaledVector(F, w); acc.N.addScaledVector(N, w);
        for (const k in acc.curls) acc.curls[k] += w * c[k]; acc.spread += w * sp;
      };
      const tw = wReach + wPush + wFlick + wHold;
      const upOnDoor = up.clone().sub(tN.clone().multiplyScalar(up.dot(tN))).normalize();
      const fDoor = upOnDoor.clone().multiplyScalar(0.94).add(inward('r').multiplyScalar(0.34)).normalize();
      // reach: 11 cm short of the door, palm opening towards it, fingers forward-up
      add(wReach / tw, tgt.clone().addScaledVector(tN, 0.11).addScaledVector(up, -0.05),
        fDoor.clone().add(tN.clone().multiplyScalar(-0.8)).normalize(), tN.clone().multiplyScalar(-1).addScaledVector(up, -0.5).normalize(),
        { index: 0.22, middle: 0.28, ring: 0.34, pinky: 0.4, thumb: 0.25 }, 0.4);
      // push: palm flat on the surface, fingers up and slightly inward, gently spread
      add(wPush / tw, tgt.clone().addScaledVector(tN, 0.004), fDoor, tN.clone().multiplyScalar(-1),
        { index: 0.06, middle: 0.07, ring: 0.1, pinky: 0.14, thumb: 0.12 }, 0.8);
      // flick: palm down over the bin, index/middle flicking the spines forward
      const ph = (pose.flickPhase ?? 0) % 1, k = Math.sin(Math.PI * clamp(ph / 0.55, 0, 1)) * (ph < 0.55 ? 1 : 0);
      const fl = pose.target ? tgt.clone() : camPt(0.06, -0.26, -0.40);
      const fwdH = fwd.clone().setY(0).normalize();
      add(wFlick / tw, fl.addScaledVector(fwdH, 0.03 * k).addScaledVector(up, 0.015 * k),
        fwdH.clone().addScaledVector(up, -0.45).normalize(), V().set(0, -1, 0).addScaledVector(fwdH, 0.2).normalize(),
        { index: 0.12 + 0.5 * k, middle: 0.2 + 0.45 * k, ring: 0.62, pinky: 0.7, thumb: 0.35 }, 0.3);
      // hold case (right hand on the right edge)
      add(wHold / tw, caseAt.clone().addScaledVector(caseR, 0.07).addScaledVector(caseN, -0.012),
        caseN.clone().multiplyScalar(-0.75).addScaledVector(caseR, -0.35).addScaledVector(caseU, -0.35).normalize(), caseR.clone().multiplyScalar(-1),
        { index: 0.42, middle: 0.46, ring: 0.5, pinky: 0.55, thumb: 0.15 }, 0.1);
      solveArm('r', ensureAway(acc.P), acc.F.normalize(), acc.N.normalize(), acc.curls, acc.spread, poleR);
      captureArm('r', ikArm.r);
      for (const n in ikArm.r) bones[n].quaternion.copy(clipArm.r[n]).slerp(ikArm.r[n], wR);
      model.updateMatrixWorld(true);
    }
    if (wHold > 0.001) {
      captureArm('l', clipArm.l);
      solveArm('l', ensureAway(caseAt.clone().addScaledVector(caseR, -0.07).addScaledVector(caseN, -0.012)),
        caseN.clone().multiplyScalar(-0.75).addScaledVector(caseR, 0.35).addScaledVector(caseU, -0.35).normalize(), caseR.clone(),
        { index: 0.42, middle: 0.46, ring: 0.5, pinky: 0.55, thumb: 0.15 }, 0.1, poleL);
      captureArm('l', ikArm.l);
      for (const n in ikArm.l) bones[n].quaternion.copy(clipArm.l[n]).slerp(ikArm.l[n], wHold);
      model.updateMatrixWorld(true);
    }
    root.updateMatrixWorld(true);
  }

  // outfit: the clothing colours (THREE.Color), so the same rig can dress other people in the shop.
  const outfit = { jacket: U.uJacket.value, jeans: U.uJeans.value, shoe: U.uShoe.value };
  return { root, update, anchors, setEnv, hideHead, bones, envs, outfit, scale: S };
}
