// SPDX-FileCopyrightText: 2026 Cade Summers
// SPDX-License-Identifier: AGPL-3.0-or-later
// Hybrasil Star and Exoplanet Map: the three.js viewer.  See hybrasil/viz/three_viewer.py.
//
// The scene arrives as window.SA3_SYSTEMS, converted from the Plotly figures
// the Plotly viewer draws, so both renderers draw identical geometry.  What
// this one does differently is the camera: a logarithmic depth buffer spreads
// depth precision over the whole range, so there is no axis box to re-cut as
// the camera moves in, and a zoom is a camera move and nothing else.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';

// Scenes by system id.  A file page arrives with its systems in it; the web
// app's page arrives empty and fetches each one from SA3_API the first time
// it is opened (hybrasil/web/app.py).  The static site has no server: its
// index is a file (SA3_INDEX_URL) and each entry names its scene file (url).
const SYSTEMS = window.SA3_SYSTEMS || {};
const LABELS = window.SA3_LABELS || {};
const KINDS = window.SA3_KINDS || {};   // System Type per system, file page only
const API = window.SA3_API || null;
const INDEX_URL = window.SA3_INDEX_URL || (API && `${API}/systems`);
let INDEX = [];                     // every system the system dropdown can find
let CATALOG_TITLE = '';             // the workbook version the scenes were built from
const FLY_MS = 700;           // double-click and Orient camera flights
const PICK_PX = 14;           // how close the pointer must be to a body

// ── Renderer, camera, controls ──────────────────────────────────────────────
const root = document.getElementById('sa3-root');
const renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
root.appendChild(renderer.domElement);

const labelRenderer = new CSS2DRenderer();
// CSS2DRenderer depth-sorts labels with a z-index each.  z-index 0 here makes
// the layer its own stacking context, so those numbers only rank labels
// against each other and never lift one over the bar, panels or dropdown.
Object.assign(labelRenderer.domElement.style,
  { position: 'absolute', inset: '0', pointerEvents: 'none', zIndex: '0' });
root.appendChild(labelRenderer.domElement);

// With a logarithmic depth buffer the near and far planes can sit fourteen
// orders of magnitude apart -- 1.5 km to a million AU -- which is the whole
// reason for this renderer.  Not further: OrbitControls' zoom-to-cursor
// unprojects a point on the far plane, and at a 1e21 ratio (1e-11 to 1e10,
// the first try) that point is infinite and the camera goes to NaN on the
// first wheel step.  Measured finite up to 1e14.
const camera = new THREE.PerspectiveCamera(45, 1, 1e-8, 1e6);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;      // wheel steps become continuous motion
controls.dampingFactor = 0.08;
controls.zoomToCursor = true;
controls.zoomSpeed = 2.5;           // 0.95^2.5 = 12% a notch, as the Plotly viewer
controls.screenSpacePanning = true;
controls.rotateSpeed = 0.6;
controls.minDistance = 1e-8;

const scene = new THREE.Scene();

// ── The Milky Way behind every system ───────────────────────────────────────
// An all-sky map in galactic coordinates (hybrasil/viz/sky/README.md),
// drawn in a pass of its own before the system: a unit sphere around a camera
// that copies only the main camera's rotation, so the sky sits at infinity
// however far the view zooms.  Each system carries the rotation from galactic
// coordinates into its own frame (sys.sky, from orientation.galactic_to_frame)
// -- the frame its galactic-centre arrow is quoted in, so the arrow points at
// the galactic centre in the picture.  Dimmed so orbits stay readable.
const SKY_URL = window.SA3_SKY || null;
const SKY_DIM = 0.35;
const SKY_PREF = 'sa3.sky';
const sky = {
  on: (() => { try { return localStorage.getItem(SKY_PREF) !== 'off'; } catch (e) { return true; } })(),
  loaded: false,          // the image has arrived
  have: false,            // this system says how to rotate it
  scene: new THREE.Scene(),
  camera: new THREE.PerspectiveCamera(45, 1, 0.1, 10),
  galFromWorld: new THREE.Matrix3(),
};
const skyMat = new THREE.ShaderMaterial({
  uniforms: { map: { value: null }, galFromWorld: { value: sky.galFromWorld },
              dim: { value: SKY_DIM } },
  vertexShader: `
    varying vec3 vDir;
    void main() {
      vDir = position;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
  // Galactic longitude increases to the left of the image and the galactic
  // centre is its middle, so u = 0.5 - l / 2pi and v = 0.5 + b / pi.
  fragmentShader: `
    uniform sampler2D map;
    uniform mat3 galFromWorld;
    uniform float dim;
    varying vec3 vDir;
    const float PI = 3.141592653589793;
    void main() {
      vec3 g = normalize(galFromWorld * vDir);
      vec2 uv = vec2(0.5 - atan(g.y, g.x) / (2.0 * PI),
                     0.5 + asin(clamp(g.z, -1.0, 1.0)) / PI);
      // uv.x jumps from 1 to 0 across l = 180 deg.  Take the derivatives from
      // a copy whose seam is elsewhere, or the GPU drops to the smallest mip
      // level along that line and draws it.
      vec2 alt = vec2(fract(uv.x + 0.5), uv.y);
      vec2 dx = dFdx(uv), dy = dFdy(uv), dxa = dFdx(alt), dya = dFdy(alt);
      if (abs(dxa.x) < abs(dx.x)) dx.x = dxa.x;
      if (abs(dya.x) < abs(dy.x)) dy.x = dya.x;
      gl_FragColor = vec4(textureGrad(map, uv, dx, dy).rgb * dim, 1.0);
    }`,
  side: THREE.BackSide, depthTest: false, depthWrite: false,
});
sky.scene.add(new THREE.Mesh(new THREE.SphereGeometry(1, 64, 32), skyMat));
if (SKY_URL) {
  new THREE.TextureLoader().load(SKY_URL, (tex) => {
    // The JPG's sRGB values pass straight through: the shader writes them
    // out as they are, so no colour-space conversion either way.
    tex.colorSpace = THREE.NoColorSpace;
    tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    skyMat.uniforms.map.value = tex;
    sky.loaded = true;
    try { ui.sync(); } catch (e) { /* the image beat the UI; its first sync shows it */ }
  }, undefined, () => { console.warn('Hybrasil: the background sky did not load'); });
}
function setSky(on) {
  sky.on = !!on;
  try { localStorage.setItem(SKY_PREF, sky.on ? 'on' : 'off'); } catch (e) { /* private mode */ }
  ui.sync();
}
// The sky's (u, v) for a direction in the current system's frame: the
// shader's lookup, for the tests that check the arrow lands on the centre.
function skyUV(dir) {
  const g = new THREE.Vector3(dir[0], dir[1], dir[2]).applyMatrix3(sky.galFromWorld).normalize();
  return [0.5 - Math.atan2(g.y, g.x) / (2 * Math.PI), 0.5 + Math.asin(g.z) / Math.PI];
}
renderer.autoClear = false;         // the sky pass, then the system over it

let world = null;                   // THREE.Group holding the current system
let current = null;                 // key into SYSTEMS
let sys = null;                     // SYSTEMS[current]
let bodies = [];                    // [{obj, data}]
let bandMeshes = [];                // THREE.Mesh, one per band/belt
let lineMats = [];                  // LineMaterials, which need the viewport size
let followers = [];                 // [{line, body, home, start}]: moon orbits riding their planet
                                    // (a band rides its star the same way, on userData.follow)
let clouds = [];                    // [{data, pts, arrows: {frame: LineSegments}, on}]: many points as one object

// ── Helpers ─────────────────────────────────────────────────────────────────
// A position array rebased on its own centre, in double precision, so the
// Float32 GPU buffer only has to hold small offsets.  55 Cnc B's planets sit
// 1,066 AU out; stored absolute, Float32 would round them to ~6e-5 AU.
function rebased(flat) {
  let cx = 0, cy = 0, cz = 0;
  const n = flat.length / 3;
  for (let i = 0; i < flat.length; i += 3) { cx += flat[i]; cy += flat[i + 1]; cz += flat[i + 2]; }
  cx /= n || 1; cy /= n || 1; cz /= n || 1;
  const out = new Float32Array(flat.length);
  for (let i = 0; i < flat.length; i += 3) {
    out[i] = flat[i] - cx; out[i + 1] = flat[i + 1] - cy; out[i + 2] = flat[i + 2] - cz;
  }
  return { local: out, centre: new THREE.Vector3(cx, cy, cz) };
}

// A body marker drawn the way Plotly draws it: a filled disc, a disc with an
// edge (a star's white outline), or an edge alone (a hypothetical or
// candidate body's hollow ring).  One texture per fill/edge pair.
const _markerTex = new Map();
function markerTexture(fill, edge, sizePx, borderPx) {
  const key = `${fill}|${edge}|${sizePx}|${borderPx}`;
  if (_markerTex.has(key)) return _markerTex.get(key);
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d');
  // The edge is borderPx wide on a sizePx marker; scale it to the canvas.
  const lw = edge ? Math.max(3, 64 * (borderPx || 2) / Math.max(sizePx, 1)) : 0;
  const r = 31 - lw / 2;
  g.beginPath(); g.arc(32, 32, r, 0, Math.PI * 2);
  if (fill) { g.fillStyle = fill; g.fill(); }
  if (edge) { g.lineWidth = lw; g.strokeStyle = edge; g.stroke(); }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  _markerTex.set(key, tex);
  return tex;
}

function labelEl(text, color, cls) {
  const el = document.createElement('div');
  el.textContent = text;
  el.className = cls || 'sa3-label';
  Object.assign(el.style, { color: color || '#ccccee', fontSize: '10px',
    fontFamily: 'monospace', transform: 'translateY(-14px)', whiteSpace: 'nowrap',
    textShadow: '0 0 3px #000' });
  return el;
}

function disposeWorld() {
  if (!world) return;
  world.traverse((o) => {
    if (o.isCSS2DObject && o.element) o.element.remove();
    if (o.geometry) o.geometry.dispose();
    if (o.material) o.material.dispose();
  });
  scene.remove(world);
  world = null;
}

// ── Building a system ───────────────────────────────────────────────────────
function build(key) {
  disposeWorld();
  current = key; sys = SYSTEMS[key];
  lineGroupsOff.clear();
  world = new THREE.Group();
  bodies = []; bandMeshes = []; lineMats = []; followers = []; clouds = [];
  renderer.setClearColor(new THREE.Color(sys.background || '#070714'));
  const rot = sys.sky && sys.sky.galactic_to_frame;
  sky.have = !!rot;
  if (rot) sky.galFromWorld.set(...rot[0], ...rot[1], ...rot[2]).transpose();

  for (const L of sys.lines) {
    const { local, centre } = rebased(L.pts);
    const dashed = L.dash && L.dash !== 'solid';
    // Dashes are in world units, so size them to the curve they break up.
    let len = 0;
    if (dashed) {
      for (let i = 3; i < local.length; i += 3) {
        len += Math.hypot(local[i] - local[i - 3], local[i + 1] - local[i - 2], local[i + 2] - local[i - 1]);
      }
    }
    let line;
    if (L.width > 1.5) {
      // Fat lines draw every segment as its own quad: worth it for the few
      // wide ones (stars' companions, reference arrows), not for a 12,000-
      // point coil -- three of those took Alpha Centauri from 17 to 103 ms a
      // frame under software rendering.
      const geo = new LineGeometry();
      geo.setPositions(local);
      const mat = new LineMaterial({
        color: L.color, linewidth: L.width, transparent: L.opacity < 1,
        opacity: L.opacity, dashed, worldUnits: false });
      if (dashed) { mat.dashSize = len / 120; mat.gapSize = len / 180; }
      lineMats.push(mat);
      line = new Line2(geo, mat);
    } else {
      // One-pixel GL lines, which is what Plotly draws these as too.
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(local, 3));
      const opts = { color: L.color, transparent: L.opacity < 1, opacity: L.opacity };
      const mat = dashed
        ? new THREE.LineDashedMaterial({ ...opts, dashSize: len / 120, gapSize: len / 180 })
        : new THREE.LineBasicMaterial(opts);
      line = new THREE.Line(geo, mat);
    }
    if (dashed) line.computeLineDistances();
    line.position.copy(centre);
    line.userData = { name: L.name, legend: L.legend, color: L.color,
                      group: L.group, groupTitle: L.groupTitle, owner: L.owner,
                      frame: L.frame, optional: L.optional, reach: L.reach };
    if (L.follows) followers.push({ line, name: L.follows, home: centre.clone() });
    world.add(line);
    if (L.label) {
      const n = local.length;
      const tag = new CSS2DObject(labelEl(L.label, L.color));
      tag.position.set(local[n - 3], local[n - 2], local[n - 1]);
      line.add(tag);
    }
  }

  // Every band gets a mesh, including one with no liquid phase at the
  // figure's pressure: a slider can give it a ring later.  `on` is whether the
  // viewer asked for it, `hasRing` whether there is anything to draw -- the
  // same split the Plotly viewer keeps as bandOn and a blank trace.
  for (const B of sys.bands) {
    const mat = new THREE.MeshBasicMaterial({ color: B.color, transparent: true,
      opacity: B.opacity, side: THREE.DoubleSide, depthWrite: false });
    const mesh = new THREE.Mesh(new THREE.BufferGeometry(), mat);
    mesh.renderOrder = 2;
    mesh.userData = { name: B.name, group: B.group, solvent: B.solvent, legend: B.legend,
                      meta: B.meta, on: B.visible, hasRing: false, follows: B.follows || null,
                      home: new THREE.Vector3(), follow: null };
    setRing(mesh, B.pos, B.index);
    applyBand(mesh);
    bandMeshes.push(mesh);
    world.add(mesh);
  }

  const px = renderer.getPixelRatio();
  for (const D of sys.bodies) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3), 3));
    const mat = new THREE.PointsMaterial({ size: D.size * 0.9 * px, sizeAttenuation: false,
      map: markerTexture(D.fill, D.edge, D.size, D.border), alphaTest: 0.3, transparent: true });
    const obj = new THREE.Points(geo, mat);
    obj.position.set(D.pos[0], D.pos[1], D.pos[2]);
    obj.renderOrder = 3;
    if (D.label) obj.add(new CSS2DObject(labelEl(D.name)));
    obj.userData = { name: D.name };
    bodies.push({ obj, data: D });
    world.add(obj);
  }
  // A cloud (Nearby Stellar Motion's unclassified objects): thousands of
  // points as one Points object and one LineSegments per motion frame, so
  // 10,000 objects cost three draw calls rather than 25,000.
  for (const C of sys.clouds || []) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(C.pos), 3));
    const pts = new THREE.Points(geo, new THREE.PointsMaterial({ size: C.size * 0.9 * px,
      sizeAttenuation: false, map: markerTexture(C.color, null, C.size, 0), alphaTest: 0.3, transparent: true }));
    pts.renderOrder = 3;
    pts.frustumCulled = false;          // Play moves the points; the bounds would go stale
    pts.userData = { cloud: C.key };
    world.add(pts);
    const arrows = {};
    for (const [frame, seg] of Object.entries(C.arrows || {})) {
      if (!seg.length) continue;
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(seg), 3));
      const l = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: C.color, transparent: true,
        opacity: 0.45 }));
      l.userData = { cloudArrows: C.key, frame };
      world.add(l);
      arrows[frame] = l;
    }
    clouds.push({ data: C, pts, arrows, on: true });
  }
  // A moon's ellipse is drawn round its planet where the planet is at frame
  // 0.  Each frame moves it by however far the planet has gone since, or the
  // planet and moon ride off it: CD-35 2722 b travels 0.32 au in the span
  // its moon's 0.2 au ellipse is drawn for.
  const P0 = (sys.frames.positions || [])[0];
  followers = followers.flatMap((f) => {
    const i = bodies.findIndex((b) => b.data.name === f.name);
    if (i < 0) return [];
    const p = P0 ? P0.slice(i * 3, i * 3 + 3) : bodies[i].data.pos;
    return [{ ...f, body: bodies[i].obj, start: new THREE.Vector3(p[0], p[1], p[2]) }];
  });
  // A band is built round its star where the star is at frame 0 and, like a
  // moon's orbit, moves by however far the star has gone since: Castor Ab's
  // bands circle Aa with Ab instead of staying where Ab started.
  for (const m of bandMeshes) {
    const i = m.userData.follows ? bodies.findIndex((b) => b.data.name === m.userData.follows) : -1;
    if (i < 0) continue;
    const p = P0 ? P0.slice(i * 3, i * 3 + 3) : bodies[i].data.pos;
    m.userData.follow = { body: bodies[i].obj, start: new THREE.Vector3(p[0], p[1], p[2]) };
  }
  // A scene with motion frames keeps the frame chosen last, if it has one of
  // that name, and opens showing only that frame's arrows.
  const mf = sys.motionFrames;
  if (mf && !mf.options.some((o) => o.key === motionFrame)) motionFrame = mf.default;
  // An optional set opens as it was left, else as its default (off).
  for (const o of sys.optionalSets || []) {
    if (!optionalState.has(o.key)) optionalState.set(o.key, !!o.default);
  }
  applyOptional();
  refreshOwnedLines();

  scene.add(world);
  anim.frame = 0; anim.playing = false;
  setFrame(0);
  resize();
  orient(false, 'initial');
  ui.hideInfo();
  // The sliders carry across a switch: the new system's bands arrive built
  // at the figure's pressure, and are rebuilt at the panel's.
  const v = ui.bandValues();
  if (v) recomputeBands(v.P, v.A, v.G);
  ui.sync();
}

// ── Animation ───────────────────────────────────────────────────────────────
const anim = { frame: 0, playing: false, last: 0 };
function nFrames() { return sys.drift ? sys.drift.steps + 1 : (sys.frames.positions || []).length; }

// Where elements put a body at Julian date t, relative to its parent: the
// pipeline of mechanics/kepler.py (elements_to_cartesian), step for step.
// el = [a, e, i, Omega, omega, M0, epoch, period]; tests/test_kepler_js.py
// runs this under node against the Python.
function keplerXYZ(el, t) {
  const [a, e, inc, node, peri, M0, epoch, period] = el;
  const D = Math.PI / 180;
  let Mdeg = (M0 + (360 / period) * (t - epoch)) % 360;
  if (Mdeg < 0) Mdeg += 360;
  const M = Mdeg * D;
  let E = M + e * Math.sin(M) * (1 + e * Math.cos(M));
  for (let k = 0; k < 100; k++) {           // Halley's method
    const s = Math.sin(E), c = Math.cos(E);
    const f = E - e * s - M, fp = 1 - e * c, fpp = e * s;
    const dE = -f / (fp - 0.5 * f * fpp / fp);
    E += dE;
    if (Math.abs(dE) < 1e-12) break;
  }
  const nu = 2 * Math.atan2(Math.sqrt(1 + e) * Math.sin(E / 2), Math.sqrt(1 - e) * Math.cos(E / 2));
  const r = a * (1 - e * e) / (1 + e * Math.cos(nu));
  const xo = r * Math.cos(nu), yo = r * Math.sin(nu);
  const cO = Math.cos(node * D), sO = Math.sin(node * D);
  const co = Math.cos(peri * D), so = Math.sin(peri * D);
  const ci = Math.cos(inc * D), si = Math.sin(inc * D);
  return [(cO * co - sO * so * ci) * xo + (-cO * so - sO * co * ci) * yo,
          (sO * co + cO * so * ci) * xo + (-sO * so + cO * co * ci) * yo,
          (so * si) * xo + (co * si) * yo];
}

// A body's position at t, its parents' added the way system_time_series adds
// them; `memo` holds the ones already placed at this t.
function keplerPosition(K, name, t, memo) {
  if (memo[name]) return memo[name];
  const B = K.bodies[name], p = keplerXYZ(B.el, t);
  if (B.parent) {
    const q = keplerPosition(K, B.parent, t, memo);
    p[0] += q[0]; p[1] += q[1]; p[2] += q[2];
  }
  return (memo[name] = p);
}

// Fractional frames are continuous at any frame rate rather than stepping at
// the figure's frame count.  A body with elements is placed by Kepler's
// equation at the fractional frame's moment, so it stays on its drawn orbit
// however far it goes in one frame step; anything else (a view's stars)
// interpolates linearly between frames.
function setFrame(f) {
  if (sys.drift) { driftFrame(f); return; }
  const P = sys.frames.positions, n = P.length;
  if (!n) return;
  anim.frame = ((f % n) + n) % n;
  const a = Math.floor(anim.frame), b = (a + 1) % n, t = anim.frame - a;
  const A = P[a], Bp = P[b];
  const w = (b === 0) ? 0 : t;            // never interpolate across the wrap
  const K = sys.kepler;
  const tNow = (K && K.n === n && n > 1) ? K.t0 + (a + w) * (K.t1 - K.t0) / (n - 1) : null;
  const memo = {};
  for (let i = 0; i < bodies.length; i++) {
    const name = bodies[i].data.name;
    if (tNow !== null && K.bodies[name]) {
      const p = keplerPosition(K, name, tNow, memo);
      bodies[i].obj.position.set(p[0], p[1], p[2]);
      continue;
    }
    const k = i * 3;
    bodies[i].obj.position.set(A[k] + (Bp[k] - A[k]) * w,
                               A[k + 1] + (Bp[k + 1] - A[k + 1]) * w,
                               A[k + 2] + (Bp[k + 2] - A[k + 2]) * w);
  }
  for (const f of followers) {
    f.line.position.copy(f.home).add(f.body.position).sub(f.start);
  }
  for (const m of bandMeshes) placeBand(m);
  ui.date(sys.frames.labels[Math.round(anim.frame) % n] || '');
}

// A view's Play (Nearby Stellar Motion): every star slides along its own
// arrow, from where it is now (frame 0) to the arrow's tip at the last frame,
// `drift.years` later, in the motion frame the Galaxy Motion Type button
// chose.  The arrows stay put: they are the path.  A star with no measured
// motion, and the Sun in its own frame, has no drift and stays.
function driftFrame(f) {
  const n = sys.drift.steps + 1;
  anim.frame = ((f % n) + n) % n;
  const s = anim.frame / (n - 1);
  for (const b of bodies) {
    const p = b.data.pos, d = b.data.drift && b.data.drift[motionFrame];
    if (d) b.obj.position.set(p[0] + d[0] * s, p[1] + d[1] * s, p[2] + d[2] * s);
    else b.obj.position.set(p[0], p[1], p[2]);
  }
  for (const c of clouds) {
    const D = c.data.drift && c.data.drift[motionFrame], P = c.data.pos;
    const attr = c.pts.geometry.attributes.position, a = attr.array;
    for (let i = 0; i < a.length; i++) a[i] = P[i] + (D ? D[i] * s : 0);
    attr.needsUpdate = true;
  }
  const yr = Math.round(s * sys.drift.years);
  ui.date(yr ? `+${yr.toLocaleString('en-US')} yr` : 'Now');
}

// ── Camera moves ────────────────────────────────────────────────────────────
let flight = null;
function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }

function flyTo(target, position, up) {
  flight = { t0: performance.now(), fromT: controls.target.clone(), toT: target.clone(),
             fromP: camera.position.clone(), toP: position.clone() };
  if (up) camera.up.copy(up);
}

function stepFlight(now) {
  if (!flight) return;
  const t = Math.min(1, (now - flight.t0) / FLY_MS), e = ease(t);
  controls.target.lerpVectors(flight.fromT, flight.toT, e);
  camera.position.lerpVectors(flight.fromP, flight.toP, e);
  if (t >= 1) flight = null;
}

function viewNormal() {
  const u = sys.up || [0, 0, 1];
  return new THREE.Vector3(u[0], u[1], u[2]).normalize();
}

// ── Back: the camera before each deliberate jump ────────────────────────────
// A double-click or a search pushes where the camera was; Back flies there.
// Scroll and drag push nothing, so the history holds only jumps, and Orient
// and a system switch clear it -- the Plotly viewer's _sceneStack rules.
// A jump made mid-flight pushes where that flight was going, not the point
// it had reached, so Back lands on the body rather than short of it.
const viewHistory = [];
const HISTORY_MAX = 12;
function pushView() {
  const t = flight ? flight.toT : controls.target, p = flight ? flight.toP : camera.position;
  viewHistory.push({ t: t.clone(), p: p.clone(), up: camera.up.clone() });
  if (viewHistory.length > HISTORY_MAX) viewHistory.shift();
}
function goBack() {
  const v = viewHistory.pop();
  if (!v) return false;
  flyTo(v.t, v.p, v.up);
  return true;
}

// ── Showing and hiding a body or a line from the legend ─────────────────────
// A body's label is a child CSS2DObject, which the label renderer draws by
// its own visibility, not its parent's -- so both are set.
function setShown(obj, on) {
  obj.visible = on;
  for (const c of obj.children) if (c.isCSS2DObject) c.visible = on;
}

// A line with an owner (a star's motion arrow) is shown when its line group
// is on and its owner is visible, so hiding a spectral class hides its arrows.
// A line drawn in a motion frame is shown only while that frame is chosen
// (the Galaxy Motion Type button): each arrow exists once per frame.  A line
// of an optional set (a photosynthesis ring) is shown only while its set is on.
const lineGroupsOff = new Set();
let motionFrame = null;
function refreshOwnedLines() {
  if (!world) return;
  const visible = new Map(bodies.map((b) => [b.data.name, b.obj.visible]));
  for (const o of world.children) {
    const u = o.userData;
    if (!u || !u.owner) continue;
    setShown(o, !lineGroupsOff.has(u.group) && visible.get(u.owner) !== false
      && (!u.frame || u.frame === motionFrame)
      && (!u.optional || optionalOn(u.optional)));
  }
  // A cloud shows while its legend row is on and its optional set is; its
  // arrows also follow the motion frame and the Motion legend row.
  for (const c of clouds) {
    const shown = c.on && cloudInSet(c);
    c.pts.visible = shown;
    for (const [frame, l] of Object.entries(c.arrows)) {
      l.visible = shown && frame === motionFrame && !lineGroupsOff.has(c.data.motionGroup);
    }
  }
}
function setMotionFrame(key) {
  motionFrame = key;
  if (sys.drift) setFrame(anim.frame);       // the stars move along the new frame's arrows
  refreshOwnedLines();
  ui.sync();
}

// Optional sets (Nearby Stellar Motion's Planetless Systems): bodies a scene
// offers behind a button of their own, off until asked for, with the lines
// they own.  The choice is kept across a switch to another system and back,
// as the motion frame is.
// A set with `modes` (the Known objects: All, Excluding unconfirmed, Unconfirmed
// only) keeps the chosen mode's key as its state, false when off; its button
// steps through the modes and then back to off.
const optionalState = new Map();
function optionalOn(key) { return !!optionalState.get(key); }
function optionalModes(key) {
  const o = ((sys && sys.optionalSets) || []).find((x) => x.key === key);
  return (o && o.modes && o.modes.length) ? o.modes : null;
}
function optionalMode(key) {
  const m = optionalModes(key), v = optionalState.get(key);
  return m && v ? (m.find((x) => x.key === v) || m[0]) : null;
}
function nextOptional(key) {
  const m = optionalModes(key);
  if (!m) return !optionalOn(key);
  const i = m.findIndex((x) => x.key === optionalState.get(key));
  return i + 1 < m.length ? m[i + 1].key : false;
}
// A cloud shows in its set's mode when the mode names it, or names no clouds.
function cloudInSet(c) {
  const k = c.data.optional;
  if (!k) return true;
  if (!optionalOn(k)) return false;
  const mode = optionalMode(k);
  return !mode || !mode.clouds || mode.clouds.includes(c.data.key);
}
function applyOptional(key) {
  for (const b of bodies) {
    if (b.data.optional && (key === undefined || b.data.optional === key)) {
      setShown(b.obj, optionalOn(b.data.optional));
    }
  }
}
function setOptional(key, on) {
  const m = optionalModes(key);
  if (m && on === true) on = m[0].key;          // "on" means the first mode
  if (m && on && !m.some((x) => x.key === on)) on = m[0].key;
  optionalState.set(key, on);
  applyOptional(key);
  refreshOwnedLines();
  controls.maxDistance = zoomLimit();
  ui.relegend();          // the set's legend row is listed only while it is on
  ui.sync();
}
// How far out the camera may go: sixty half-widths of the system, or far
// enough to see a shown line that declares its `reach` (a reference orbit:
// Neptune's 30 AU round TRAPPIST-1, whose half-width is a tenth of an AU).
function zoomLimit() {
  let far = (sys.half || 1) * 60;
  for (const o of (world ? world.children : [])) {
    if (o.userData && o.userData.reach && o.visible) far = Math.max(far, o.userData.reach * 6);
  }
  return far;
}

// 'initial' opens on the figure's own three-quarter view; otherwise Orient
// looks straight down the band plane's normal, as the Plotly Orient does.
function orient(animate = true, mode = 'above') {
  const half = sys.half || 1;
  controls.maxDistance = zoomLimit();
  const n = viewNormal();
  let pos;
  if (mode === 'initial') {
    const e = new THREE.Vector3(sys.eye[0], sys.eye[1], sys.eye[2]);
    // Plotly's eye is in units of the box half-width; a little further back
    // keeps an eccentric outer orbit (Planet Nine) inside the frame.
    pos = e.multiplyScalar(half * 1.3);
  } else {
    // A hair off the normal: a camera exactly along `up` has no defined roll.
    const side = Math.abs(n.z) < 0.9 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0);
    pos = n.clone().multiplyScalar(half * 2.4).addScaledVector(side.cross(n).normalize(), half * 1e-3);
  }
  viewHistory.length = 0;
  if (animate) { flyTo(new THREE.Vector3(), pos, n); return; }
  camera.up.copy(n);
  controls.target.set(0, 0, 0);
  camera.position.copy(pos);
  controls.update();
}

// Double-click framing: the same zoom_half_au the Plotly viewer uses, which
// holds a planet's moons (or a star's inner system) in view.
function frameBody(b) {
  // Found by search while hidden from the legend: show it, since framing a
  // body nobody can see is not an answer.  One of an optional set that is off
  // turns its set on: the button then says what is showing.
  if (b.data.optional && !optionalOn(b.data.optional)) setOptional(b.data.optional, true);
  if (b.cloud && !cloudInSet(b.cloud)) setOptional(b.data.optional, true);
  if (b.cloud) {
    if (!b.cloud.on) { b.cloud.on = true; refreshOwnedLines(); ui.sync(); }
    cloudInfo(b);
  } else if (!b.obj.visible) { setShown(b.obj, true); refreshOwnedLines(); ui.sync(); }
  pushView();
  const info = window._SA_BODY_INFO && window._SA_BODY_INFO[b.data.name];
  const p = b.obj.position.clone();
  // zoom_half is in the scene's own units (light years in a view);
  // zoom_half_au is what every star system's bodies carry.
  const half = (info && (info.zoom_half || info.zoom_half_au)) || Math.max(p.length() * 0.01, 1e-3);
  const dir = camera.position.clone().sub(controls.target).normalize();
  flyTo(p, p.clone().addScaledVector(dir, half * 2.2));
  ui.toast(b.data.name);
  ui.showInfo(b.data.name);
}

// Frame a set of objects -- a band's rings, an orbit -- by their combined
// bounding box, since none of them has a zoom_half_au of its own.
function frameObjects(objs, label) {
  const box = new THREE.Box3();
  for (const o of objs) box.expandByObject(o);
  if (box.isEmpty()) return;
  pushView();
  const c = box.getCenter(new THREE.Vector3());
  const half = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 1e-5);
  const dir = camera.position.clone().sub(controls.target).normalize();
  flyTo(c, c.clone().addScaledVector(dir, half * 2.6));
  ui.toast(label);
}

// ── Search ──────────────────────────────────────────────────────────────────
// The Plotly viewer's two passes, ranked by the same shared _nameMatches:
// bodies first, so "Jupiter" finds the planet rather than its orbit; then
// bands, then orbits and coils.  A band found by name is switched on if it
// was off -- framing a ring nobody can see is not an answer -- and only that
// band, not every band in the system.
function search(query) {
  const q = String(query || '').trim();
  const K = window.SABandKit;
  if (!q || !K) return false;
  const hitB = K.nameMatches(bodies.map((b) => b.data.name), q);
  if (hitB.length) { frameBody(bodies[hitB[0]]); return true; }
  for (const c of clouds) {
    const hitC = K.nameMatches(c.data.info.map((r) => r[0]), q);
    if (hitC.length) { frameBody(cloudPoint(c, hitC[0])); return true; }
  }

  const hitR = K.nameMatches(bandMeshes.map((m) => m.userData.name), q);
  if (hitR.length) {
    const ms = hitR.map((i) => bandMeshes[i]);
    for (const m of ms) { m.userData.on = true; applyBand(m); }
    ui.sync();
    const drawn = ms.filter((m) => m.userData.hasRing);
    if (!drawn.length) {
      ui.toast(`${ms[0].userData.name}: no liquid phase at this pressure`, false);
      return true;
    }
    frameObjects(drawn, ms[0].userData.name);
    return true;
  }

  const lines = world.children.filter((o) => o.userData && o.userData.name
    && !o.isPoints && !bandMeshes.includes(o));
  const hitL = K.nameMatches(lines.map((o) => o.userData.name), q);
  if (hitL.length) {
    // A ring of an optional set that is off, or of a legend row turned off,
    // is switched on first: framing a line nobody can see is not an answer.
    for (const i of hitL) {
      const u = lines[i].userData;
      if (u.optional && !optionalOn(u.optional)) setOptional(u.optional, true);
      if (u.group && lineGroupsOff.has(u.group)) { lineGroupsOff.delete(u.group); refreshOwnedLines(); ui.sync(); }
    }
    frameObjects(hitL.map((i) => lines[i]), lines[hitL[0]].userData.name);
    return true;
  }
  ui.toast(`No match for “${q}”`, false);
  return false;
}

// ── Picking, in screen space ────────────────────────────────────────────────
// Bodies are drawn a fixed number of pixels wide at every distance, so a
// world-space pick radius would be wrong at every zoom but one.
const _v = new THREE.Vector3();
function pick(clientX, clientY) {
  const r = renderer.domElement.getBoundingClientRect();
  let best = null, bd = PICK_PX;
  for (const b of bodies) {
    if (!b.obj.visible) continue;
    // Behind the camera?  Judged in view space: with near and far 1e14
    // apart, projected depth rounds to 1 for everything in the scene.
    _v.copy(b.obj.position).applyMatrix4(camera.matrixWorldInverse);
    if (_v.z >= 0) continue;
    _v.copy(b.obj.position).project(camera);
    const x = (_v.x + 1) / 2 * r.width + r.left, y = (1 - _v.y) / 2 * r.height + r.top;
    const d = Math.hypot(x - clientX, y - clientY);
    if (d < bd) { bd = d; best = b; }
  }
  for (const c of clouds) {
    if (!c.pts.visible) continue;
    const P = c.pts.geometry.attributes.position.array;   // where Play has moved them
    for (let i = 0; i < P.length; i += 3) {
      _v.set(P[i], P[i + 1], P[i + 2]).applyMatrix4(camera.matrixWorldInverse);
      if (_v.z >= 0) continue;
      _v.set(P[i], P[i + 1], P[i + 2]).project(camera);
      const x = (_v.x + 1) / 2 * r.width + r.left, y = (1 - _v.y) / 2 * r.height + r.top;
      const d = Math.hypot(x - clientX, y - clientY);
      if (d < bd) { bd = d; best = cloudPoint(c, i / 3); }
    }
  }
  return best;
}

// One point of a cloud, shaped like a body for pick, hover, search and framing.
function cloudPoint(c, i) {
  const P = c.pts.geometry.attributes.position.array;
  return { cloud: c, index: i, data: { name: c.data.info[i][0], optional: c.data.optional },
           obj: { position: new THREE.Vector3(P[3 * i], P[3 * i + 1], P[3 * i + 2]), visible: true } };
}

// A cloud point's Sources: its link template (star_motion.known_cloud, built
// by Python so every URL format lives in star_sources.py) with the point's own
// ids swapped in for the template's slots -- raw in a label, encoded in a URL.
function cloudSources(C, ids) {
  const tmpl = (C.linkTemplates || [])[ids.t] || [];
  const fill = (str, enc) => {
    for (const [k, slot] of Object.entries(C.idSlots || {})) {
      const id = ids[k] || '';
      str = str.split(enc ? encodeURIComponent(slot) : slot).join(enc ? encodeURIComponent(id) : id);
    }
    return str;
  };
  return tmpl.map(([label, url]) => [fill(label, false), fill(url, true)]);
}

// A cloud point's info panel, built from its compact row the first time it is
// opened: [name, distance, l, b, speed, motion l, motion b, RV, pm mas/yr, source,
// link template, Gaia DR3 id, SIMBAD id, CNS5 id, existence].
function cloudInfo(b) {
  const C = b.cloud.data;
  const [name, d, l, bb, v, ml, mb, rv, pm, si, ti, gaia, simbad, cns5, ei] = C.info[b.index];
  window._SA_BODY_INFO = window._SA_BODY_INFO || {};
  if (window._SA_BODY_INFO[name]) return;
  const f = (x, n) => x.toFixed(n);
  const sgn = (x, n) => (x >= 0 ? '+' : '') + x.toFixed(n);
  const verdict = (C.existence || [])[ei] || '';
  const fid = /fidelity_v2 ([\d.]+)/.exec(verdict);
  const rows = C.slug
    ? [[C.slug[0], C.slug[1], fid ? `fidelity_v2 ${fid[1]} (Rybizki et al. 2022): its Gaia astrometry is `
        + 'probably spurious, and no other catalog lists it' : 'no other catalog lists it']]
    : [];
  rows.push(['Classification', 'not yet classified', 'Known within 100ly tab'],
            ['Distance', d == null ? 'no data' : `${f(d, 2)} ly (${f(d / 3.261563777, 2)} pc)`, ''],
            ['Galactic position', l == null ? 'no data' : `l ${f(l, 2)}°, b ${sgn(bb, 2)}°`, '']);
  if (v != null) {
    const r = Math.PI / 180;
    const u = [Math.cos(mb * r) * Math.cos(ml * r), Math.cos(mb * r) * Math.sin(ml * r), Math.sin(mb * r)];
    const uvw = u.map((c) => c * v);
    const lsr = uvw.map((c, k) => c + C.sunPeculiar[k]);
    const sl = Math.hypot(lsr[0], lsr[1], lsr[2]);
    const ll = ((Math.atan2(lsr[1], lsr[0]) / r) + 360) % 360;
    rows.push(['Speed', `${f(v, 2)} km/s`, 'relative to the Sun'],
              ['Direction of motion', `toward l ${f(ml, 2)}°, b ${sgn(mb, 2)}°`, ''],
              ['U, V, W', uvw.map((c) => sgn(c, 1)).join(', ') + ' km/s',
               'toward the galactic centre, along rotation, to the north pole'],
              ['Speed (LSR)', `${f(sl, 2)} km/s`, 'relative to the local standard of rest'],
              ['Direction (LSR)', `toward l ${f(ll, 2)}°, b ${sgn(Math.asin(lsr[2] / sl) / r, 2)}°`, ''],
              [`Travel in ${C.arrowYears.toLocaleString('en-US')} yr`,
               `${f(v * C.lyPerKms, 2)} ly (${f(sl * C.lyPerKms, 2)} ly LSR)`, 'the length of its arrow']);
  } else {
    rows.push(['Speed', 'no data', rv == null ? 'no radial velocity on file' : 'not computed']);
  }
  rows.push(['Radial velocity', rv == null ? 'no data' : `${sgn(rv, 2)} km/s`, rv == null ? '' : 'positive = receding'],
            ['Proper motion', pm == null ? 'no data' : `${f(pm, 1)} mas/yr`, '']);
  if (C.sources[si]) rows.push(['Kinematics source', C.sources[si], '']);
  window._SA_BODY_INFO[name] = { rows, zoom_half: C.zoomHalf,
                                 sources: cloudSources(C, { t: ti, gaia, simbad, cns5 }) };
}

renderer.domElement.addEventListener('dblclick', (e) => {
  const b = pick(e.clientX, e.clientY);
  if (b) frameBody(b);
});
// A single click on a body opens its info panel where the camera is; a
// double-click also flies to it.  A click that ends a drag is a drag.
let pressedAt = null;
renderer.domElement.addEventListener('pointerdown', (e) => { pressedAt = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('click', (e) => {
  if (pressedAt && Math.hypot(e.clientX - pressedAt[0], e.clientY - pressedAt[1]) > 4) return;
  const b = pick(e.clientX, e.clientY);
  if (b && b.cloud) cloudInfo(b);
  if (b) ui.showInfo(b.data.name);
});
renderer.domElement.addEventListener('pointermove', (e) => {
  const b = pick(e.clientX, e.clientY);
  ui.hover(b, e.clientX, e.clientY);
});
// A user's own drag or wheel cancels a flight rather than fighting it, and
// puts the info panel away -- but not in the first 800 ms, or the flight a
// double-click starts would close the panel it just opened.
controls.addEventListener('start', () => {
  flight = null;
  ui.hideInfo(800);
});

// ── Bands ───────────────────────────────────────────────────────────────────
function solventBands() { return bandMeshes.filter((m) => m.userData.solvent); }

function applyBand(m) { m.visible = !!(m.userData.on && m.userData.hasRing); }

// Replace a band's ring.  `pos` is absolute AU, flat; `index` flat triangles.
// Empty means no liquid phase: the mesh stays, with nothing in it.
function setRing(mesh, pos, index) {
  mesh.geometry.dispose();
  const geo = new THREE.BufferGeometry();
  if (pos && pos.length) {
    const { local, centre } = rebased(pos);
    geo.setAttribute('position', new THREE.BufferAttribute(local, 3));
    geo.setIndex(Array.from(index, (v) => v | 0));
    mesh.userData.home.copy(centre);
    mesh.userData.hasRing = true;
  } else {
    mesh.userData.home.set(0, 0, 0);
    mesh.userData.hasRing = false;
  }
  mesh.geometry = geo;
  placeBand(mesh);
}

// Where a band sits now: where it was built (`home`, around its star at
// frame 0), plus however far its star has moved since.  A band with no star
// to follow -- a belt, a primary at the origin -- stays at home.
function placeBand(mesh) {
  const u = mesh.userData, f = u.follow;
  mesh.position.copy(u.home);
  if (f) mesh.position.add(f.body.position).sub(f.start);
}

// 'On', 'Some', 'Off', read back off the bands rather than remembered, so a
// band switched on from its legend row cannot leave the button lying.
function bandState() {
  const s = solventBands();
  const on = s.filter((m) => m.userData.on).length;
  return !s.length ? 'None' : (on === 0 ? 'Off' : (on === s.length ? 'On' : 'Some'));
}
function setBands(on) {
  for (const m of solventBands()) { m.userData.on = on; applyBand(m); }
  ui.sync();
}
function setGroup(group, on) {
  for (const m of bandMeshes) {
    if (m.userData.group === group) { m.userData.on = on; applyBand(m); }
  }
  ui.sync();
}

// Rebuild every solvent band at pressure P (bar), albedo A and greenhouse
// offset G (K), through band_kit.js -- the same functions the Plotly viewer's
// sliders call, so the two cannot disagree about where a band is.
function recomputeBands(P, A, G) {
  const K = window.SABandKit, C = K && K.bandConst();
  if (!C) return;
  const s = solventBands().filter((m) => m.userData.meta);
  if (!s.length) return;
  const metas = s.map((m) => m.userData.meta);
  const radii = metas.map((meta) => K.bandRadiiAU(meta, P, A, G));
  const outer = radii.map((r) => (r ? r[1] : 0)), inner = radii.map((r) => (r ? r[0] : 0));
  const offsets = K.stackOffsetsByCentre(metas, outer, inner);
  s.forEach((m, k) => {
    const meta = metas[k];
    m.userData.name = K.bandName(meta, P) || m.userData.name;
    if (!radii[k]) {
      setRing(m, [], []);
    } else {
      const r = K.ringMesh(radii[k][0], radii[k][1], meta.normal || [0, 0, 1],
                           offsets[k], C.ring_pts, meta.centre);
      const n = r.x.length, pos = new Array(n * 3), idx = new Array(r.i.length * 3);
      for (let i = 0; i < n; i++) { pos[3 * i] = r.x[i]; pos[3 * i + 1] = r.y[i]; pos[3 * i + 2] = r.z[i]; }
      for (let t = 0; t < r.i.length; t++) { idx[3 * t] = r.i[t]; idx[3 * t + 1] = r.j[t]; idx[3 * t + 2] = r.k[t]; }
      setRing(m, pos, idx);
    }
    applyBand(m);
  });
  ui.sync();
}

// ── UI ──────────────────────────────────────────────────────────────────────
const ui = (() => {
  const css = 'background:#111130;color:#aaddff;border:1px solid #333366;border-radius:4px;'
            + 'padding:4px 10px;font-family:monospace;font-size:12px;cursor:pointer;';
  const bar = document.createElement('div');
  // Above the legend and panels (10), so the system dropdown drops over them.
  Object.assign(bar.style, { position: 'absolute', top: '8px', left: '8px', right: '8px',
    display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center', zIndex: 12 });
  root.appendChild(bar);
  const btn = (text, onClick) => {
    const b = document.createElement('button'); b.textContent = text; b.style.cssText = css;
    b.addEventListener('click', onClick); bar.appendChild(b); return b;
  };
  btn('⦿  Orient', () => orient(true, 'above'));
  btn('◁  Back', () => {
    if (!goBack()) toast('Already at the widest view', false);
  }).title = 'Return to the view before the last double-click or search';
  // Anything short of all-on switches everything on: the button is a way out
  // of a mess of individually toggled bands, not another one.
  const bandsBtn = btn('◎  Bands: Off', () => setBands(bandState() !== 'On'));
  // In a scene with motion frames (Nearby Stellar Motion) this takes the Bands
  // button's place -- such a scene has no bands -- and steps through them.
  const frameBtn = btn('⇢', () => {
    const opts = sys.motionFrames.options;
    const i = opts.findIndex((o) => o.key === motionFrame);
    setMotionFrame(opts[(i + 1) % opts.length].key);
  });
  frameBtn.title = 'Which frame the motion arrows are measured in: the Sun, or the '
    + 'local standard of rest (the mean motion of stars near the Sun)';
  // One button per optional set the scene declares (Planetless Systems), made
  // when first needed and hidden in a scene without that set.
  const optWrap = document.createElement('span');
  optWrap.style.display = 'contents';
  bar.appendChild(optWrap);
  const optBtns = new Map();
  const skyBtn = btn('✦  Sky: On', () => setSky(!sky.on));
  skyBtn.title = 'The Milky Way behind the system, turned so the galactic-centre arrow points at its centre';
  if (!SKY_URL) skyBtn.style.display = 'none';
  // Even more features: a menu of optional sets that are not bodies to list
  // but extra things to draw (the photosynthesis rings), one toggle each.
  // Built like the More Modeled Systems dropdown; hidden in a scene that
  // offers none of them.
  const featWrap = document.createElement('span');
  featWrap.style.cssText = 'position:relative;display:inline-block';
  bar.appendChild(featWrap);
  const featBtn = document.createElement('button');
  featBtn.style.cssText = css;
  featBtn.setAttribute('aria-haspopup', 'menu');
  featBtn.setAttribute('aria-expanded', 'false');
  featWrap.appendChild(featBtn);
  const featBox = document.createElement('div');
  featBox.setAttribute('role', 'menu');
  featBox.style.cssText = 'position:absolute;top:calc(100% + 4px);left:0;width:300px;max-width:calc(100vw - 16px);'
    + 'box-sizing:border-box;display:none;flex-direction:column;gap:6px;z-index:20;'
    + 'background:rgba(10,10,30,0.97);border:1px solid #333366;border-radius:4px;'
    + 'padding:6px;box-shadow:0 6px 18px rgba(0,0,0,0.5)';
  featWrap.appendChild(featBox);
  const featRows = new Map();
  let featOpen = false;
  function openFeatures() {
    featOpen = true;
    // As the systems dropdown does: over the band kit's panels while open.
    bar.style.zIndex = '10000';
    featBox.style.display = 'flex';
    sync();
  }
  function closeFeatures() {
    if (!featOpen) return;
    featOpen = false;
    featBox.style.display = 'none';
    bar.style.zIndex = '12';
    sync();
  }
  featBtn.addEventListener('click', () => (featOpen ? closeFeatures() : openFeatures()));
  document.addEventListener('mousedown', (ev) => {
    if (featOpen && !featWrap.contains(ev.target)) closeFeatures();
  });
  function syncFeatures(feats) {
    featWrap.style.display = feats.length ? 'inline-block' : 'none';
    if (!feats.length && featOpen) { featOpen = false; featBox.style.display = 'none'; bar.style.zIndex = '12'; }
    const lit = feats.some((o) => optionalOn(o.key));
    featBtn.textContent = `✧  Even more features ${featOpen ? '▴' : '▾'}`;
    featBtn.style.background = lit || featOpen ? '#2a2a70' : '#111130';
    featBtn.setAttribute('aria-expanded', String(featOpen));
    for (const [k, b] of featRows) b.style.display = feats.some((o) => o.key === k) ? '' : 'none';
    for (const o of feats) {
      let b = featRows.get(o.key);
      if (!b) {
        b = document.createElement('button');
        b.style.cssText = css + 'text-align:left;';
        b.dataset.optional = o.key;
        b.setAttribute('role', 'menuitemcheckbox');
        b.addEventListener('click', () => setOptional(o.key, !optionalOn(o.key)));
        featBox.appendChild(b);
        featRows.set(o.key, b);
      }
      const on = optionalOn(o.key);
      b.textContent = `${on ? '☑' : '☐'}  ${o.label}`;
      b.title = o.title || '';
      b.setAttribute('aria-checked', String(on));
      b.style.background = on ? '#2a2a70' : '#111130';
    }
  }
  const searchIn = document.createElement('input');
  Object.assign(searchIn, { type: 'text', placeholder: 'Find in system…', spellcheck: false });
  searchIn.style.cssText = css + 'cursor:text;width:130px;';
  searchIn.setAttribute('aria-label', 'Search bodies, bands and orbits');
  searchIn.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') search(searchIn.value);
    e.stopPropagation();     // typing must not reach the camera controls
  });
  bar.appendChild(searchIn);
  btn('⌕', () => search(searchIn.value)).title = 'Search';
  const playBtn = btn('▶ Play', () => { anim.playing = !anim.playing; sync(); });
  const slider = document.createElement('input');
  Object.assign(slider, { type: 'range', min: 0, step: 'any', value: 0 });
  slider.style.width = '150px';
  slider.addEventListener('input', () => { anim.playing = false; setFrame(+slider.value); sync(); });
  bar.appendChild(slider);
  const dateEl = document.createElement('span'); dateEl.style.cssText = 'font-size:12px;min-width:90px';
  bar.appendChild(dateEl);
  const spacer = document.createElement('span'); spacer.style.flex = '1'; bar.appendChild(spacer);

  // ── Systems: featured buttons, and a More Modeled Systems dropdown ────
  // The featured systems -- the literature-built set -- get a button each.
  // "More Modeled Systems ▾" opens a dropdown headed by a System Type row
  // (Planetary, High Star Count (Planetless), Stellar Motion -- which holds the
  // Sgr A* Cluster (Galactic Center) beside Nearby Stellar Motion;
  // each index entry's `kind`).
  // Planetary lists every catalog system, most planets first, then nearest,
  // twelve rows tall and scrolling for the rest; the other two list every
  // system of their type, featured ones included.  The search box searches
  // the chosen type, ranked by system_search.js, which forgives typos and
  // understands catalog-style names ("tau Cet").
  const sysWrap = document.createElement('div');
  sysWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;align-items:center';
  bar.appendChild(sysWrap);
  const mk = (tag, text) => { const e = document.createElement(tag); if (text) e.textContent = text; return e; };
  const featuredLabel = mk('span', '★ Featured systems');
  featuredLabel.style.cssText = 'font-size:12px;color:#8899bb;padding:0 2px';
  sysWrap.appendChild(featuredLabel);
  const featuredRow = mk('span');
  featuredRow.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px';
  sysWrap.appendChild(featuredRow);
  // The dropdown hangs from its own button, so it lines up under it however
  // the bar wraps.
  const moreWrap = mk('span');
  moreWrap.style.cssText = 'position:relative;display:inline-block';
  sysWrap.appendChild(moreWrap);
  const tabMore = mk('button');
  tabMore.style.cssText = css;
  tabMore.setAttribute('aria-haspopup', 'listbox');
  tabMore.setAttribute('aria-expanded', 'false');
  moreWrap.appendChild(tabMore);
  const moreBox = mk('div');
  moreBox.style.cssText = 'position:absolute;top:calc(100% + 4px);right:0;width:680px;max-width:calc(100vw - 16px);box-sizing:border-box;display:none;'
    + 'z-index:20;background:rgba(10,10,30,0.97);border:1px solid #333366;border-radius:4px;'
    + 'padding:6px;box-shadow:0 6px 18px rgba(0,0,0,0.5)';
  // The System Type row: which kind of system the list below holds.
  const KIND_OPTIONS = [['planetary', 'Planetary'], ['planetless', 'High Star Count (Planetless)'],
    ['motion', 'Stellar Motion']];
  const kindRow = mk('div');
  kindRow.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:6px';
  const kindLabel = mk('span', 'System Type:');
  kindLabel.style.cssText = 'font-size:12px;color:#8899bb;padding:0 2px';
  kindRow.appendChild(kindLabel);
  const kindBtns = {};
  let moreKind = 'planetary';     // kept between opens; Planetary on a fresh page
  for (const [key, text] of KIND_OPTIONS) {
    const b = mk('button', text);
    b.style.cssText = css;
    b.dataset.kind = key;
    // mousedown, like the rows: the search box keeps its focus.
    b.addEventListener('mousedown', (ev) => { ev.preventDefault(); setKind(key); });
    kindRow.appendChild(b);
    kindBtns[key] = b;
  }
  const moreIn = mk('input');
  Object.assign(moreIn, { type: 'text', spellcheck: false, placeholder: 'Search systems…' });
  moreIn.style.cssText = css + 'cursor:text;width:100%;box-sizing:border-box;';
  moreIn.setAttribute('aria-label', 'Search all systems');
  const moreCaption = mk('div');
  moreCaption.style.cssText = 'padding:6px 4px 0;color:#8899bb;font-size:10px';
  const moreList = mk('div');
  moreList.setAttribute('role', 'listbox');
  moreList.style.cssText = 'margin-top:6px;font-size:12px;max-height:60vh;overflow-y:auto';
  moreBox.append(kindRow, moreIn, moreCaption, moreList);
  const VISIBLE_ROWS = 12;      // the list's height, in systems; the rest scroll
  moreWrap.appendChild(moreBox);
  const sysBtns = {};
  let moreOpen = false, hits = [], hi = 0;

  const kindOf = (e) => e.kind || 'planetary';
  const pool = () => INDEX.filter((e) => kindOf(e) === moreKind);

  function paintKinds() {
    for (const [key, b] of Object.entries(kindBtns)) {
      b.setAttribute('aria-pressed', String(key === moreKind));
      b.style.background = key === moreKind ? '#2a2a70' : '#111130';
    }
    moreIn.placeholder = moreKind === 'planetary'
      ? `Search ${pool().length} systems — star, nickname or planet`
      : `Search ${pool().length} system${pool().length === 1 ? '' : 's'}`;
  }

  function setKind(key) {
    moreKind = key;
    paintKinds();
    renderHits();
    moreIn.focus();
  }

  function openMore() {
    moreOpen = true;
    // The panel hangs leftward from the button's right edge -- unless the bar
    // has wrapped the button to the left of the window, where that would push
    // the panel off-screen; then it hangs rightward from the button's left.
    const room = tabMore.getBoundingClientRect().right;
    const leftward = room >= Math.min(440, window.innerWidth - 16);
    moreBox.style.right = leftward ? '0' : 'auto';
    moreBox.style.left = leftward ? 'auto' : '0';
    // Over the band kit's slider and info panels (z-index 9997-9998) while
    // open: hung from a wrapped button, the list drops right across them.
    bar.style.zIndex = '10000';
    moreBox.style.display = 'block';
    moreIn.value = '';
    renderHits();
    moreIn.focus();
    sync();
  }
  function closeMore() {
    if (!moreOpen) return;
    moreOpen = false;
    moreBox.style.display = 'none';
    bar.style.zIndex = '12';
    moreIn.blur();
    sync();
  }
  // The button is a toggle: a second click puts the list away.
  tabMore.addEventListener('click', () => (moreOpen ? closeMore() : openMore()));
  // So does a click anywhere outside the dropdown.
  document.addEventListener('mousedown', (ev) => {
    if (moreOpen && !moreWrap.contains(ev.target)) closeMore();
  });

  function setIndex(index) {
    featuredRow.innerHTML = '';
    for (const key of Object.keys(sysBtns)) delete sysBtns[key];
    for (const e of index.filter((x) => x.featured)) {
      const b = mk('button', LABELS[e.id] || e.name);
      b.style.cssText = css;
      b.addEventListener('click', () => { closeMore(); openSystem(e.id); });
      featuredRow.appendChild(b);
      sysBtns[e.id] = b;
    }
    paintKinds();
  }

  function describe(e) {
    const bits = [];
    if (e.featured) bits.push('★ featured');
    if (e.n_planets) bits.push(`${e.n_planets} planet${e.n_planets === 1 ? '' : 's'}`);
    if (e.n_stars) bits.push(`${e.n_stars} stars`);
    if (e.stellar_class) bits.push(e.stellar_class);
    if (e.distance_ly) bits.push(`${(+e.distance_ly).toFixed(1)} ly`);
    return bits.join(' · ');
  }

  function note(text) {
    const n = mk('div', text);
    n.style.cssText = 'padding:6px 10px;color:#667788;font-size:10px;font-style:italic';
    return n;
  }

  function renderHits() {
    const q = moreIn.value.trim();
    const S = window.SASystemSearch;
    // Nothing typed: every catalog system, most planets first, then nearest
    // (SASystemSearch.shelf).  Typed: the ranked search over every
    // system the index holds, featured ones included.
    // Only systems of the chosen System Type, in either case.  Planetary's
    // featured systems keep their buttons and are not shelved; the other
    // types shelve everything they have, since that is all featured so far.
    const browsing = !(q && S);
    const planetary = moreKind === 'planetary';
    if (!browsing) {
      hits = S.rank(pool(), q, 8);
    } else {
      const shelf = S ? S.shelf(pool()) : { featured: [], more: [] };
      const shown = planetary ? shelf.more : shelf.featured.concat(shelf.more);
      hits = shown.map((e) => ({ entry: e, tier: null, via: null }));
    }
    hi = 0;
    moreList.innerHTML = '';
    moreList.scrollTop = 0;
    const count = `${hits.length} system${hits.length === 1 ? '' : 's'}`;
    moreCaption.textContent = browsing && hits.length
      ? (planetary ? `${count} · most planets first, then nearest`
        : moreKind === 'planetless' ? `${count} · most stars first, then nearest` : count) : '';
    moreCaption.style.display = moreCaption.textContent ? 'block' : 'none';
    if (!browsing && hits.length && hits[0].tier === 'typo') {
      // The autocorrect, said out loud: what was typed matched nothing as
      // written, and this is the nearest name.
      const h = mk('div', `Did you mean ${hits[0].entry.name}?`);
      h.style.cssText = 'padding:5px 10px;color:#99aacc;font-size:11px;border-bottom:1px solid #222244';
      moreList.appendChild(h);
    }
    if (!hits.length) {
      moreList.appendChild(note(!browsing ? `No system matches “${q}”`
        : !planetary ? 'No systems of this type yet'
        : API ? 'The catalog is unavailable — only the featured systems are here' : 'This file holds only the featured systems — '
          + 'run python -m hybrasil.cli --serve for the rest'));
    }
    hits.forEach((hit, i) => {
      const row = mk('div');
      row.setAttribute('role', 'option');
      row.dataset.id = hit.entry.id;
      row.style.cssText = 'padding:5px 10px;cursor:pointer;border-bottom:1px solid #1a1a3a';
      const name = mk('div', hit.entry.name);
      name.style.cssText = 'color:#ddeeff';
      const meta = mk('div', describe(hit.entry) + (hit.via ? ` · matched “${hit.via}”` : ''));
      meta.style.cssText = 'color:#778899;font-size:10px';
      row.append(name, meta);
      // mousedown, not click: acting before the box loses focus.
      row.addEventListener('mousedown', (ev) => { ev.preventDefault(); choose(i); });
      row.addEventListener('mouseenter', () => { hi = i; paint(); });
      moreList.appendChild(row);
    });
    fitList();
    paint();
  }

  // Twelve rows tall, measured rather than assumed, since a row's height
  // depends on its text; never taller than 60% of the window.
  function fitList() {
    moreList.style.maxHeight = '60vh';
    const rows = moreList.querySelectorAll('[role=option]');
    if (rows.length <= VISIBLE_ROWS) return;
    const first = rows[0], last = rows[VISIBLE_ROWS - 1];
    const h = last.offsetTop + last.offsetHeight - first.offsetTop;
    moreList.style.maxHeight = `min(${h}px, 60vh)`;
  }

  // Keep the highlighted row in view while the arrow keys move it.
  function reveal() {
    const row = moreList.querySelectorAll('[role=option]')[hi];
    if (row) row.scrollIntoView({ block: 'nearest' });
  }

  function paint() {
    moreList.querySelectorAll('[role=option]').forEach((r, i) => {
      r.style.background = i === hi ? '#1a1a50' : 'transparent';
      r.setAttribute('aria-selected', String(i === hi));
    });
  }

  function choose(i) {
    const hit = hits[i];
    if (!hit) return;
    closeMore();
    openSystem(hit.entry.id);
  }

  moreIn.addEventListener('input', renderHits);
  moreIn.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); hi = Math.min(hi + 1, hits.length - 1); paint(); reveal(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); hi = Math.max(hi - 1, 0); paint(); reveal(); }
    else if (e.key === 'Enter') { e.preventDefault(); choose(hi); }
    else if (e.key === 'Tab' && hits[hi]) {
      // Tab completes the name in the box without opening it yet.
      e.preventDefault(); moreIn.value = hits[hi].entry.name; renderHits();
    } else if (e.key === 'Escape') { e.preventDefault(); closeMore(); }
    e.stopPropagation();     // typing must not reach the camera controls
  });

  const legend = document.createElement('div');
  Object.assign(legend.style, { position: 'absolute', top: '48px', right: '8px', maxHeight: '70%',
    overflowY: 'auto', background: 'rgba(10,10,30,0.8)', border: '1px solid #333366',
    borderRadius: '4px', padding: '6px 8px', fontSize: '11px', zIndex: 10 });
  root.appendChild(legend);

  const tip = document.createElement('div');
  Object.assign(tip.style, { position: 'absolute', pointerEvents: 'none', display: 'none',
    background: 'rgba(10,10,30,0.9)', border: '1px solid #333366', borderRadius: '4px',
    padding: '4px 8px', fontSize: '11px', zIndex: 11 });
  root.appendChild(tip);

  // ── Dialogs ──────────────────────────────────────────────────────────────
  // A modal over the viewer (Suggest Changes, About): Escape and a click
  // outside close it, Tab stays inside, typing never reaches the camera
  // controls, and focus goes back to whatever opened it.
  function makeDialog(tag, labelId) {
    const overlay = document.createElement('div');
    Object.assign(overlay.style, { position: 'fixed', inset: '0', background: 'rgba(0,0,12,0.6)',
      display: 'none', alignItems: 'center', justifyContent: 'center', zIndex: 10001 });
    const box = document.createElement(tag);
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-labelledby', labelId);
    Object.assign(box.style, { background: 'rgba(10,10,30,0.97)', border: '1px solid #333366',
      borderRadius: '6px', boxShadow: '0 6px 24px rgba(0,0,0,0.6)', color: '#aaddff',
      fontFamily: 'monospace', fontSize: '12px', padding: '14px 16px', boxSizing: 'border-box',
      width: 'min(560px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 32px)', overflowY: 'auto' });
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    let opener = null;
    const d = {
      box,
      isOpen: () => overlay.style.display !== 'none',
      open(from, focus) {
        opener = from || document.activeElement;
        overlay.style.display = 'flex';
        box.scrollTop = 0;
        (focus || box.querySelector('input,textarea,button,a[href]'))?.focus();
      },
      close() {
        if (!d.isOpen()) return;
        overlay.style.display = 'none';
        if (opener && document.contains(opener)) opener.focus();
      },
    };
    overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) d.close(); });
    box.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'Escape') { e.preventDefault(); d.close(); return; }
      if (e.key !== 'Tab') return;
      const f = [...box.querySelectorAll('input,textarea,button,a[href]')]
        .filter((x) => !x.disabled && x.offsetParent);
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    });
    return d;
  }

  // ── Suggest Changes ──────────────────────────────────────────────────────
  // A correction or an addition: any system (one this page has, or one it
  // has never heard of), any objects (new ones too), what should change, and
  // the sources for it.  It posts to SA3_SUGGEST_URL -- the web app's
  // /api/suggestions, or the hosted site's Cloudflare function -- which
  // records it for review and never touches the catalog workbook
  // (docs/architecture/suggestions.md).  A file page has nowhere to send it.
  const SUGGEST_URL = window.SA3_SUGGEST_URL || null;
  const SITEKEY = window.SA3_TURNSTILE_SITEKEY || null;
  const SG = window.SASuggest || null;
  const suggestBtn = btn('✎  Suggest Changes', () => openSuggest({}, suggestBtn));
  suggestBtn.title = 'Suggest a correction or an addition: a system, its objects, what should change, and your sources';
  suggestBtn.setAttribute('aria-haspopup', 'dialog');
  if (!SUGGEST_URL || !SG) suggestBtn.style.display = 'none';
  bar.insertBefore(suggestBtn, sysWrap);   // the first row's right end, not a row of its own

  const sgDialog = makeDialog('form', 'sa3-sg-title');
  const sgForm = sgDialog.box;
  sgForm.noValidate = true;
  const fieldCss = css + 'cursor:text;width:100%;box-sizing:border-box;margin-top:3px;resize:vertical;';
  const field = (id, label, hint, el) => `<label for="${id}" style="display:block;margin-top:10px;color:#ddeeff;">`
    + `${label}${hint ? ` <span style="color:#667788;">${hint}</span>` : ''}</label>${el}`;
  sgForm.innerHTML = `<div id="sa3-sg-title" style="font-size:14px;font-weight:bold;color:#ddeeff;">Suggest Changes</div>`
    + `<div style="color:#778899;margin-top:4px;">Corrections and additions are welcome, including systems and objects
       this map does not have yet. Every suggestion is checked against its sources before anything changes.</div>`
    + field('sa3-sg-system', 'System', '', `<input id="sa3-sg-system" list="sa3-sg-systems" autocomplete="off" style="${fieldCss}">`)
    + '<datalist id="sa3-sg-systems"></datalist>'
    + field('sa3-sg-objects', 'Object(s)', 'one per line, optional', `<textarea id="sa3-sg-objects" rows="2" style="${fieldCss}"></textarea>`)
    + field('sa3-sg-description', 'What should change', '', `<textarea id="sa3-sg-description" rows="4" style="${fieldCss}"></textarea>`)
    + field('sa3-sg-sources', 'Source(s)', 'one per line: a paper, DOI, catalogue or URL', `<textarea id="sa3-sg-sources" rows="3" style="${fieldCss}"></textarea>`)
    + '<div style="display:flex;gap:10px;">'
    + `<div style="flex:1;">${field('sa3-sg-name', 'Name', 'optional', `<input id="sa3-sg-name" autocomplete="name" style="${fieldCss}">`)}</div>`
    + `<div style="flex:1;">${field('sa3-sg-email', 'Email', 'optional', `<input id="sa3-sg-email" type="email" autocomplete="email" style="${fieldCss}">`)}</div>`
    + '</div>'
    + '<div style="color:#667788;margin-top:6px;font-size:11px;">Your name and email are kept private and used only'
    + ' to follow up on this suggestion. They are never published.</div>'
    + '<div id="sa3-sg-turnstile" style="margin-top:10px;"></div>'
    + '<div id="sa3-sg-error" role="alert" style="color:#ff9999;margin-top:8px;white-space:pre-line;"></div>'
    + '<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px;">'
    + `<button type="button" id="sa3-sg-cancel" style="${css}">Cancel</button>`
    + `<button type="submit" id="sa3-sg-send" style="${css}border-color:#4477aa;color:#ddeeff;">Send suggestion</button>`
    + '</div>';
  const sgEl = (id) => sgForm.querySelector(`#sa3-sg-${id}`);
  const SG_LABELS = { system: 'System', objects: 'Object(s)', description: 'What should change',
    sources: 'Source(s)', name: 'Name', email: 'Email' };
  let tsWidget = null;
  let tsToken = '';

  function loadTurnstile() {
    if (!SITEKEY || tsWidget !== null) return;
    tsWidget = 'loading';
    const render = () => {
      tsWidget = window.turnstile.render(sgEl('turnstile'), { sitekey: SITEKEY, theme: 'dark',
        callback: (t) => { tsToken = t; }, 'expired-callback': () => { tsToken = ''; } });
    };
    if (window.turnstile) { render(); return; }
    window.sa3TurnstileReady = render;
    const s = document.createElement('script');
    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=sa3TurnstileReady';
    s.async = true;
    s.onerror = () => { tsWidget = null; sgEl('error').textContent = 'The bot check could not load; please try again later.'; };
    document.head.appendChild(s);
  }

  // Opening fills System with the current system and, from an info panel,
  // Object(s) with the body; a half-written description and sources stay.
  function openSuggest({ object } = {}, opener = null) {
    if (!SUGGEST_URL || !SG) return;
    const names = [...new Set(INDEX.map((e) => e.name))];
    sgEl('systems').innerHTML = names.map((n) => `<option value="${n.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')}">`).join('');
    const entry = INDEX.find((e) => e.id === current);
    sgEl('system').value = entry ? entry.name : '';
    if (object) sgEl('objects').value = object;
    sgEl('error').textContent = '';
    sgDialog.open(opener, object || sgEl('system').value ? sgEl('description') : sgEl('system'));
    loadTurnstile();
  }

  const closeSuggest = () => sgDialog.close();
  sgEl('cancel').addEventListener('click', closeSuggest);

  const showErrors = (errors) => {
    sgEl('error').textContent = Object.entries(errors)
      .map(([k, m]) => `${SG_LABELS[k] || k} ${m}`).join('\n');
  };

  sgForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const systemName = sgEl('system').value.trim();
    const match = INDEX.find((x) => x.name.toLowerCase() === systemName.toLowerCase());
    const payload = {
      system: systemName, objects: sgEl('objects').value, description: sgEl('description').value,
      sources: sgEl('sources').value, name: sgEl('name').value, email: sgEl('email').value,
      system_id: match ? match.id : '', site_build: CATALOG_TITLE,
    };
    const { clean, errors } = SG.validate(payload, SG.rules);
    if (Object.keys(errors).length) { showErrors(errors); return; }
    if (SITEKEY && !tsToken) { sgEl('error').textContent = 'Please complete the bot check.'; return; }
    const send = sgEl('send');
    send.disabled = true;
    sgEl('error').textContent = '';
    try {
      const r = await fetch(SUGGEST_URL, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign(clean, SITEKEY ? { turnstile: tsToken } : {})) });
      let d = {};
      try { d = await r.json(); } catch (err) { d = {}; }
      if (!r.ok) {
        if (d.fields) showErrors(d.fields);
        else sgEl('error').textContent = d.error || `The suggestion could not be sent (${r.status}).`;
        return;
      }
      for (const k of ['objects', 'description', 'sources']) sgEl(k).value = '';
      closeSuggest();
      toast('Thanks — your suggestion was recorded for review', false);
    } catch (err) {
      sgEl('error').textContent = 'The suggestion could not be sent. Please check your connection and try again.';
    } finally {
      send.disabled = false;
      if (SITEKEY && window.turnstile && tsWidget && tsWidget !== 'loading') {
        window.turnstile.reset(tsWidget);
        tsToken = '';
      }
    }
  });

  // ── About ────────────────────────────────────────────────────────────────
  // Who made the map, how to cite it, its licences, its data credits and what
  // it keeps about a visitor -- all from hybrasil/about.json (SA3_ABOUT), so a
  // DOI or a support link is added there, not here.  Every page has it.
  const ABOUT = window.SA3_ABOUT || null;
  const aboutBtn = btn('ⓘ  About', () => openAbout(aboutBtn));
  aboutBtn.title = 'Who made this map, how to cite it, its licences and its data credits';
  aboutBtn.setAttribute('aria-haspopup', 'dialog');
  if (!ABOUT) aboutBtn.style.display = 'none';
  bar.insertBefore(aboutBtn, sysWrap);
  const aboutDialog = makeDialog('div', 'sa3-ab-title');
  const escHtml = (v) => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const link = (url, text) => `<a href="${escHtml(url)}" target="_blank" rel="noopener" `
    + `style="color:#77aadd;">${escHtml(text || url)}</a>`;

  // The two citations, plain (APA) and BibTeX, for the software and for the
  // dataset at the version these scenes were built from.  A DOI replaces the
  // site link once about.json has one, when Zenodo has minted it.
  function citations() {
    const A = ABOUT, au = A.author, initial = `${au.given[0]}.`;
    const where = (doi) => (doi ? `https://doi.org/${doi}` : A.site);
    const ver = CATALOG_TITLE;
    const bib = (type, key, fields) => `@${type}{${key},\n`
      + fields.filter(([, v]) => v).map(([k, v]) => `  ${k} = {${v}}`).join(',\n') + '\n}';
    return [
      { what: 'The map (software)',
        apa: `${au.family}, ${initial} (${A.year}). ${A.title} [Computer software]. ${where(A.dois.software)}`,
        bibtex: bib('software', `${au.family.toLowerCase()}${A.year}hybrasil`, [
          ['author', `${au.family}, ${au.given}`], ['title', A.title], ['year', A.year],
          ['url', A.site], ['doi', A.dois.software]]) },
      { what: 'The data (dataset)',
        apa: `${au.family}, ${initial} (${A.year}). ${A.dataset_title}${ver ? ` (Version ${ver})` : ''} [Data set]. `
          + where(A.dois.dataset),
        bibtex: bib('misc', `${au.family.toLowerCase()}${A.year}hybrasildata`, [
          ['author', `${au.family}, ${au.given}`], ['title', A.dataset_title], ['year', A.year],
          ['version', ver], ['howpublished', 'Data set'], ['url', A.site], ['doi', A.dois.dataset]]) },
    ];
  }

  function aboutHtml() {
    const A = ABOUT, au = A.author;
    const h = (t) => `<div style="margin-top:14px;color:#ddeeff;font-weight:bold;">${t}</div>`;
    const p = (t) => `<div style="margin-top:5px;line-height:1.5;">${t}</div>`;
    const copyBtn = (i, kind) => `<button type="button" data-copy="${i}:${kind}" style="${css}font-size:11px;`
      + `padding:2px 8px;margin-left:6px;">Copy ${kind === 'apa' ? 'APA' : 'BibTeX'}</button>`;
    let html = `<div id="sa3-ab-title" style="font-size:15px;font-weight:bold;color:#ddeeff;">${escHtml(A.title)}</div>`
      + p(escHtml(A.tagline));
    html += h('Made by') + p(`${escHtml(au.name)} · ORCID ${link(`https://orcid.org/${au.orcid}`, au.orcid)}`
      + ` · ${link(`https://github.com/${au.github}`, 'GitHub')} · ${link(A.site, A.site.replace(/^https?:\/\//, ''))}`
      + ` · ${link(`mailto:${A.contact}`, A.contact)}`);
    html += h('How to cite it');
    citations().forEach((c, i) => {
      html += p(`<span style="color:#ddeeff;">${escHtml(c.what)}</span>${copyBtn(i, 'apa')}${copyBtn(i, 'bibtex')}`
        + `<br>${escHtml(c.apa)}`)
        + `<pre style="margin:4px 0 0;padding:6px 8px;background:#0b0b22;border:1px solid #222244;`
        + `border-radius:4px;white-space:pre-wrap;color:#99bbdd;">${escHtml(c.bibtex)}</pre>`;
    });
    html += h('Licences')
      + p(`The code is free software under the ${link(A.licences.code.url, A.licences.code.name)}: use it, study it, `
        + 'share it and change it. Anyone who offers a changed copy to the public as a website must offer its '
        + `source code too. ${link(A.source, 'Source code')}.`)
      + p(`The compiled data is under ${link(A.licences.data.url, A.licences.data.name)}: credit `
        + `${escHtml(au.name)}, and share anything built on it under the same licence. Data from the sources below `
        + 'keeps its own terms.');
    const sup = [];
    if (A.support.ko_fi) sup.push(link(`https://ko-fi.com/${A.support.ko_fi}`, 'Ko-fi'));
    if (A.support.patreon) sup.push(link(`https://www.patreon.com/${A.support.patreon}`, 'Patreon'));
    if (sup.length) html += h('Support the map') + p(sup.join(' · '));
    html += h('Data and credits') + A.credits.map(([what, who, url]) =>
      `<div style="margin-top:4px;line-height:1.45;"><span style="color:#778899;">${escHtml(what)}:</span> `
      + `${link(url, who)}</div>`).join('')
      + p('<span style="color:#778899;">Each body\'s own sources are listed in its info panel.</span>');
    html += h('Privacy')
      + p('The map keeps one setting in your browser (whether the sky is shown). It has no ads and no tracking.'
        + (SUGGEST_URL ? ' Suggest Changes stores what you send, your name and email if you give them, and a salted '
          + 'hash of your network address, to review the suggestion and follow up. None of it is published. '
          + `To have a suggestion removed, email ${link(`mailto:${A.contact}`, A.contact)}.` : ''));
    html += '<div style="display:flex;justify-content:flex-end;margin-top:14px;">'
      + `<button type="button" id="sa3-ab-close" style="${css}">Close</button></div>`;
    return html;
  }

  function openAbout(opener) {
    if (!ABOUT) return;
    const box = aboutDialog.box;
    box.innerHTML = aboutHtml();
    const cites = citations();
    box.querySelector('#sa3-ab-close').addEventListener('click', () => aboutDialog.close());
    box.querySelectorAll('[data-copy]').forEach((b) => b.addEventListener('click', async () => {
      const [i, kind] = b.dataset.copy.split(':');
      try {
        await navigator.clipboard.writeText(cites[+i][kind]);
        toast('Citation copied', false);
      } catch (e) {
        toast('Could not copy; select the text instead', false);
      }
    }));
    aboutDialog.open(opener);      // the first link, at the top: the panel opens unscrolled
  }

  // NASA's credit for the sky, shown whenever the sky is (sky/README.md).
  const skyCredit = document.createElement('div');
  skyCredit.textContent = 'Milky Way: NASA/Goddard Space Flight Center Scientific Visualization '
    + 'Studio, Deep Star Maps 2020 · Gaia DR2: ESA/Gaia/DPAC';
  Object.assign(skyCredit.style, { position: 'absolute', left: '8px', bottom: '6px',
    fontSize: '10px', color: '#667788', pointerEvents: 'none', zIndex: 11, display: 'none' });
  root.appendChild(skyCredit);
  const toastEl = document.createElement('div');
  Object.assign(toastEl.style, { position: 'absolute', top: '48px', left: '50%',
    transform: 'translateX(-50%)', background: '#111130', border: '1px solid #333366',
    borderRadius: '4px', padding: '4px 12px', fontSize: '12px', opacity: '0',
    transition: 'opacity 0.3s', zIndex: 11, pointerEvents: 'none' });
  root.appendChild(toastEl);
  function toast(text, icon = true) {
    toastEl.textContent = icon ? `⊕ ${text}` : text; toastEl.style.opacity = '1';
    clearTimeout(toastEl._t); toastEl._t = setTimeout(() => { toastEl.style.opacity = '0'; }, 2200);
  }
  function clearToast() { clearTimeout(toastEl._t); toastEl.style.opacity = '0'; }

  // The pressure, albedo and greenhouse panel: band_kit.js's, the very one
  // the Plotly viewer shows, handing over its values once per frame.
  const K = window.SABandKit;
  const panel = K ? K.bandPanel({ toast: (t) => toast(t, false), top: '48px',
    onChange: (P, A, G) => recomputeBands(P, A, G) }) : null;
  if (panel) root.appendChild(panel.el);

  let infoShownAt = 0;

  // The Plotly legend, ported: every body, every solvent band and belt, and
  // the reference arrows, in that order.  Clicking a body hides its marker
  // and label and leaves its orbit, as a Plotly legend click does; a band row
  // moves its whole legend group through setGroup, the one band writer.
  function legendRow(kind, key, swatch) {
    const row = document.createElement('label');
    row.style.cssText = 'display:flex;gap:6px;align-items:center;cursor:pointer;white-space:nowrap';
    row.dataset.kind = kind;
    const box = document.createElement('input'); box.type = 'checkbox';
    box.dataset.kind = kind; box.dataset.key = key;
    const text = document.createElement('span');
    text.className = 'sa3-legend-name';
    row.append(box, swatch, text);
    return { row, box, text };
  }
  function heading(text) {
    const h = document.createElement('div');
    h.textContent = text;
    h.style.cssText = 'color:#778899;font-size:10px;margin:4px 0 2px;';
    return h;
  }

  function buildLegend() {
    legend.innerHTML = '';
    let n = 0;
    const shownBodies = bodies.filter((b) => b.data.legend !== false && !b.data.group);
    if (shownBodies.length) legend.appendChild(heading('Bodies'));
    shownBodies.forEach((b) => {
      const sw = document.createElement('span');
      sw.style.cssText = 'display:inline-block;width:10px;height:10px;border-radius:50%;box-sizing:border-box;'
        + `background:${b.data.fill || 'transparent'};`
        + (b.data.edge ? `border:2px solid ${b.data.edge};` : '');
      const r = legendRow('body', b.data.name, sw);
      r.text.textContent = b.data.name;
      // Its owned lines follow it: the Solar System's own LSR arrow.
      r.box.addEventListener('change', () => { setShown(b.obj, r.box.checked); refreshOwnedLines(); sync(); });
      legend.appendChild(r.row); n++;
    });

    // Bodies in a legend group get one row per group, in first-seen order --
    // the Nearby Stellar Motion view's spectral classes.  Toggling a group hides
    // its bodies and every line they own (their motion arrows).
    const groups = new Map();
    for (const b of bodies) {
      if (!b.data.group) continue;
      if (!groups.has(b.data.group)) groups.set(b.data.group, []);
      groups.get(b.data.group).push(b);
    }
    // A group of an optional set that is off is not listed until its button turns it on.
    for (const [group, members] of groups) {
      if (members.every((b) => b.data.optional && !optionalOn(b.data.optional))) groups.delete(group);
    }
    if (groups.size) legend.appendChild(heading(sys.groupHeading || 'Groups'));
    for (const [group, members] of groups) {
      const sw = document.createElement('span');
      // A group drawn with a ring (the planetless systems, every class) shows
      // the ring, not one member's class colour.
      const ring = members[0].data.edge;
      sw.style.cssText = 'display:inline-block;width:10px;height:10px;border-radius:50%;box-sizing:border-box;'
        + (ring ? `border:2px solid ${ring};background:transparent;`
                : `background:${members[0].data.fill || members[0].data.color};`);
      const r = legendRow('bgroup', group, sw);
      r.text.textContent = `${members[0].data.groupTitle || group} (${members.length})`;
      r.box.addEventListener('change', () => {
        for (const b of members) setShown(b.obj, r.box.checked);
        refreshOwnedLines(); sync();
      });
      legend.appendChild(r.row); n++;
    }
    // A cloud is one row, listed only while its optional set's mode shows it.
    for (const c of clouds) {
      if (!cloudInSet(c)) continue;
      const sw = document.createElement('span');
      sw.style.cssText = `display:inline-block;width:10px;height:10px;border-radius:50%;background:${c.data.color}`;
      const r = legendRow('cloud', c.data.key, sw);
      r.text.textContent = `${c.data.name} (${c.data.info.length.toLocaleString('en-US')})`;
      r.box.addEventListener('change', () => { c.on = r.box.checked; refreshOwnedLines(); sync(); });
      legend.appendChild(r.row); n++;
    }
    const lineGroups = new Map();
    for (const o of world.children) {
      const g = o.userData && o.userData.group;
      if (g && !o.isPoints && !bandMeshes.includes(o)) {
        if (!lineGroups.has(g)) lineGroups.set(g, o);
      }
    }
    // A line group of an optional set (the photosynthesis rings) is listed
    // only while its set is on, under the set's own heading, in its colour.
    let setHeading = null;
    for (const [group, first] of lineGroups) {
      const opt = first.userData.optional;
      if (opt && !optionalOn(opt)) continue;
      if (opt && setHeading !== opt) {
        const o = ((sys && sys.optionalSets) || []).find((x) => x.key === opt);
        legend.appendChild(heading(o ? o.label : opt));
        setHeading = opt;
      }
      const sw = document.createElement('span');
      sw.style.cssText = 'display:inline-block;width:12px;height:2px;'
        + `background:${opt ? first.userData.color : '#cccccc'}`;
      const r = legendRow('lgroup', group, sw);
      r.text.textContent = first.userData.groupTitle || group;
      r.box.addEventListener('change', () => {
        if (r.box.checked) lineGroupsOff.delete(group); else lineGroupsOff.add(group);
        refreshOwnedLines(); sync();
      });
      legend.appendChild(r.row); n++;
    }

    const seen = new Set();
    const bandRows = [];
    for (const m of bandMeshes) {
      const { group, legend: shown } = m.userData;
      if (!shown || seen.has(group)) continue;
      seen.add(group);
      const sw = document.createElement('span');
      sw.style.cssText = `display:inline-block;width:10px;height:10px;background:${m.material.color.getStyle()}`;
      const r = legendRow('band', group, sw);
      r.box.addEventListener('change', () => setGroup(group, r.box.checked));
      bandRows.push(r.row);
    }
    if (bandRows.length) legend.appendChild(heading('Bands and belts'));
    for (const row of bandRows) { legend.appendChild(row); n++; }

    const arrows = world.children.filter((o) => o.userData && o.userData.legend
      && !o.userData.group && !o.isPoints && !bandMeshes.includes(o));
    if (arrows.length) legend.appendChild(heading('Reference'));
    for (const o of arrows) {
      const sw = document.createElement('span');
      sw.style.cssText = `display:inline-block;width:12px;height:2px;background:${o.userData.color}`;
      const r = legendRow('line', o.userData.name, sw);
      r.text.textContent = o.userData.name;
      r.box.addEventListener('change', () => { setShown(o, r.box.checked); sync(); });
      legend.appendChild(r.row); n++;
    }
    legend.style.display = n ? 'block' : 'none';
  }

  // The bar wraps on a narrow window, so what sits under it is placed from
  // its measured height rather than a fixed offset.
  function layout() {
    const top = `${bar.offsetTop + bar.offsetHeight + 8}px`;
    legend.style.top = top;
    toastEl.style.top = top;
    if (panel) panel.el.style.top = top;
  }
  window.addEventListener('resize', layout);

  function sync() {
    layout();
    bandsBtn.textContent = `◎  Bands: ${bandState() === 'None' ? 'Off' : bandState()}`;
    const mf = sys && sys.motionFrames;
    bandsBtn.style.display = mf ? 'none' : '';
    frameBtn.style.display = mf ? '' : 'none';
    if (mf) {
      const o = mf.options.find((x) => x.key === motionFrame) || mf.options[0];
      frameBtn.textContent = `⇢  ${mf.title}: ${o.label}`;
    }
    const allSets = (sys && sys.optionalSets) || [];
    const sets = allSets.filter((o) => !o.menu);
    for (const [k, b] of optBtns) b.style.display = sets.some((o) => o.key === k) ? '' : 'none';
    syncFeatures(allSets.filter((o) => o.menu === 'features'));
    for (const o of sets) {
      let b = optBtns.get(o.key);
      if (!b) {
        b = document.createElement('button');
        b.style.cssText = css;
        b.dataset.optional = o.key;
        b.addEventListener('click', () => setOptional(o.key, nextOptional(o.key)));
        optWrap.appendChild(b);
        optBtns.set(o.key, b);
      }
      const on = optionalOn(o.key), mode = optionalMode(o.key);
      b.textContent = `✚  ${o.label}: ${on ? (mode ? mode.label : 'On') : 'Off'}`;
      b.dataset.mode = on ? (mode ? mode.key : 'on') : 'off';
      b.title = (o.title || '') + (o.count ? ` (${o.count})` : '');
      b.setAttribute('aria-pressed', String(on));
      b.style.background = on ? '#2a2a70' : '#111130';
    }
    skyBtn.textContent = `✦  Sky: ${sky.on ? 'On' : 'Off'}`;
    skyCredit.style.display = sky.on && sky.loaded && sky.have ? 'block' : 'none';
    if (panel) panel.el.style.display = solventBands().length ? 'block' : 'none';
    playBtn.textContent = anim.playing ? '❚❚ Pause' : '▶ Play';
    // A static figure (--mode static) has one moment and nothing to play.
    const animated = nFrames() > 1;
    for (const el of [playBtn, slider, dateEl]) el.style.display = animated ? '' : 'none';
    slider.max = Math.max(0, nFrames() - 1);
    slider.value = anim.frame;
    for (const [k, b] of Object.entries(sysBtns)) {
      b.style.background = k === current ? '#2a2a70' : '#111130';
    }
    // A system opened from the dropdown has no button; the dropdown names it
    // and is lit, as a featured system's button is.
    const entry = INDEX.find((e) => e.id === current);
    const other = !!(entry && !entry.featured);
    tabMore.textContent = `More Modeled Systems${other ? ` · ${entry.name}` : ''} ${moreOpen ? '▴' : '▾'}`;
    tabMore.style.background = other || moreOpen ? '#2a2a70' : '#111130';
    tabMore.setAttribute('aria-expanded', String(moreOpen));
    // Rebuilt whenever the scene is -- keyed on the world object, not the
    // system name, since re-opening the same system builds new objects and
    // rows still bound to the old ones would toggle nothing.
    if (legend._world !== world) { buildLegend(); legend._world = world; }
    // Bodies and arrows: the box follows the object.
    for (const box of legend.querySelectorAll('input[data-kind=body]')) {
      const b = bodies.find((x) => x.data.name === box.dataset.key);
      box.checked = !!(b && b.obj.visible);
    }
    for (const box of legend.querySelectorAll('input[data-kind=bgroup]')) {
      box.checked = bodies.some((b) => b.data.group === box.dataset.key && b.obj.visible);
    }
    for (const box of legend.querySelectorAll('input[data-kind=cloud]')) {
      const c = clouds.find((x) => x.data.key === box.dataset.key);
      box.checked = !!(c && c.pts.visible);
    }
    for (const box of legend.querySelectorAll('input[data-kind=lgroup]')) {
      box.checked = !lineGroupsOff.has(box.dataset.key);
    }
    for (const box of legend.querySelectorAll('input[data-kind=line]')) {
      const o = world.children.find((x) => x.userData && x.userData.name === box.dataset.key);
      box.checked = !!(o && o.visible);
    }
    // Names follow the sliders ("Water band (17.8 bar)"); a band with no
    // liquid phase at this pressure stays listed, dimmed, and says why.
    for (const box of legend.querySelectorAll('input[data-kind=band]')) {
      const group = bandMeshes.filter((m) => m.userData.group === box.dataset.key);
      box.checked = group.some((m) => m.userData.on);
      const row = box.parentElement, ring = group.some((m) => m.userData.hasRing);
      row.querySelector('.sa3-legend-name').textContent = group[0].userData.name;
      row.style.opacity = ring ? '1' : '0.45';
      row.title = ring ? '' : 'No liquid phase at this pressure';
    }
    if (sys) document.title = sys.title;
  }


  return {
    sync,
    setIndex,
    closeMore,
    // The next sync rebuilds the legend: an optional set came or went.
    relegend() { legend._world = null; },
    bandValues() { return panel ? panel.values() : null; },
    showInfo(name) {
      if (!K) return;
      K.showInfoPanel(name);
      infoShownAt = Date.now();
    },
    // Hide the info panel, unless it was opened less than `grace` ms ago.
    hideInfo(grace = 0) {
      if (K && Date.now() - infoShownAt >= grace) K.hideInfoPanel();
    },
    date(text) { dateEl.textContent = text; },
    hover(b, x, y) {
      if (!b) { tip.style.display = 'none'; renderer.domElement.style.cursor = ''; return; }
      const p = b.obj.position;
      tip.innerHTML = sys.units === 'ly'
        // A view in light years is centred on the Sun: say how far away.
        ? `<b>${b.data.name}</b><br>${p.length().toFixed(2)} ly from the Sun`
        : `<b>${b.data.name}</b><br>x ${p.x.toFixed(4)} AU<br>y ${p.y.toFixed(4)} AU<br>z ${p.z.toFixed(4)} AU`;
      Object.assign(tip.style, { display: 'block', left: `${x + 14}px`, top: `${y + 14}px` });
      renderer.domElement.style.cursor = 'pointer';
    },
    toast,
    clearToast,
    suggest: openSuggest,
    about: () => openAbout(null),
  };
})();

// ── Loop ────────────────────────────────────────────────────────────────────
function resize() {
  const w = root.clientWidth || window.innerWidth, h = root.clientHeight || window.innerHeight;
  renderer.setSize(w, h);
  labelRenderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  for (const m of lineMats) m.resolution.set(w, h);
}
window.addEventListener('resize', resize);

const FRAME_MS = 50;       // one figure frame per 50 ms, as the Plotly player
function loop(now) {
  requestAnimationFrame(loop);
  const dt = anim.last ? now - anim.last : 0;
  anim.last = now;
  if (sys && anim.playing && nFrames() > 1) { setFrame(anim.frame + dt / FRAME_MS); ui.sync(); }
  stepFlight(now);
  controls.update();
  renderer.clear();
  if (sky.on && sky.loaded && sky.have) {
    sky.camera.quaternion.copy(camera.quaternion);
    if (sky.camera.fov !== camera.fov || sky.camera.aspect !== camera.aspect) {
      sky.camera.fov = camera.fov; sky.camera.aspect = camera.aspect;
      sky.camera.updateProjectionMatrix();
    }
    renderer.render(sky.scene, sky.camera);
  }
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}

// Test and debugging handle.  Nothing in the viewer reads it.
window.__SA3 = {
  get key() { return current; },
  switchTo: build, setBands, setGroup, orient, frameBody, search, recomputeBands,
  bandState, bandValues: () => ui.bandValues(), goBack,
  viewHistory: () => viewHistory.length,
  flying: () => !!flight,
  bands: () => bandMeshes, bodies: () => bodies, clouds: () => clouds,
  camera, controls, renderer, scene,
  pick,
  sky: () => ({ on: sky.on, loaded: sky.loaded, have: sky.have, url: !!SKY_URL }),
  lines: () => world ? world.children.filter((o) => o.userData && o.userData.name && !o.isPoints
    && !bandMeshes.includes(o)) : [],
  units: () => (sys && sys.units) || 'AU',
  motionFrame: () => motionFrame, setMotionFrame,
  optional: (key) => optionalOn(key), setOptional,
  setSky, skyUV,
  setFrame, nFrames, anim: () => anim,
};

// ── Opening systems ─────────────────────────────────────────────────────────
// The index is what the system dropdown searches: the server's list in the
// web app, or just the systems in the file otherwise.
async function loadIndex() {
  if (API) {
    try {
      const r = await fetch(INDEX_URL);
      const d = await r.json();
      INDEX = d.systems || [];
      CATALOG_TITLE = (d.catalog && d.catalog.title) || '';
    } catch (e) {
      INDEX = [];
      ui.toast('Could not reach the Hybrasil server', false);
    }
  } else {
    INDEX = Object.keys(SYSTEMS).map((k) => ({
      id: k, name: LABELS[k] || k, featured: true, aliases: [], kind: KINDS[k] || 'planetary',
      planets: (SYSTEMS[k].bodies || []).map((b) => b.name) }));
  }
  ui.setIndex(INDEX);
}

// Open a system by id, fetching its scene first if this page does not have
// it.  Picks can overlap -- a slow catalog system, then a quick click on a
// featured one -- so only the latest pick is built.
let openToken = 0;
async function openSystem(id) {
  const token = ++openToken;
  const entry = INDEX.find((e) => e.id === id);
  const name = entry ? entry.name : id;
  if (!SYSTEMS[id]) {
    if (!API) {
      ui.toast(`${name} is not in this file — run python -m hybrasil.cli --serve`, false);
      return false;
    }
    ui.toast(`Loading ${name}…`, false);
    try {
      const r = await fetch((entry && entry.url) || `${API}/systems/${encodeURIComponent(id)}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || r.statusText);
      window._SA_BODY_INFO = Object.assign(window._SA_BODY_INFO || {}, d.body_info || {});
      SYSTEMS[id] = d.scene;
    } catch (e) {
      if (token === openToken) ui.toast(`Could not load ${name}: ${e.message}`, false);
      return false;
    }
  }
  if (token !== openToken) return false;
  ui.clearToast();              // the "Loading…" is done
  build(id);
  return true;
}

window.__SA3.openSystem = openSystem;
window.__SA3.index = () => INDEX;

// The info panel's "Go to system" button, on a star in Nearby Stellar Motion.
// Offered only for a system this page can open: any the server lists in the
// web app, only the featured ones in a file page.
if (window.SABandKit && window.SABandKit.setInfoGoto) {
  window.SABandKit.setInfoGoto({
    can: (id) => id !== current && (!!SYSTEMS[id] || INDEX.some((e) => e.id === id)),
    // The star's hover tooltip would otherwise outlive the view it was in.
    go: (id) => { ui.hideInfo(); ui.hover(null); openSystem(id); },
  });
}
// Its "Suggest Changes" button: the form, with that body as the object.
if (window.SA3_SUGGEST_URL && window.SABandKit && window.SABandKit.setInfoSuggest) {
  window.SABandKit.setInfoSuggest({ go: (name) => ui.suggest({ object: name }) });
}

requestAnimationFrame(loop);
(async () => {
  await loadIndex();
  const first = window.SA3_INITIAL;
  const start = (SYSTEMS[first] || INDEX.some((e) => e.id === first))
    ? first : (INDEX[0] && INDEX[0].id);
  if (start) await openSystem(start);
  window.__SA3.ready = true;
})();
