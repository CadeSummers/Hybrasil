# Scene visibility, camera centering, multi-scale zoom

> Moved verbatim out of `CLAUDE.md` so it loads on demand. `CLAUDE.md` links here.

## Scene visibility — what is drawn at deep zoom

Plotly clips 3D geometry to the axis ranges, and the scene is a cube. A ring of
radius `R` centred in a cube of half-extent `h` is therefore:

| Radius | What Plotly renders on its own |
|---|---|
| `R <= h` | the whole ring |
| `h < R <= h*sqrt(2)` | four arcs with flat, straight ends |
| `R > h*sqrt(2)` | nothing, it is outside the box |

The middle row is what a user reports as "the asteroid belt is cut" or "half
the orbit is missing".

**`updateSceneVisibility()` clips geometry to the box rather than hiding whole
traces.** A line is cut to the runs inside the box (`_clipPolyline`,
Liang-Barsky per segment, with a `null` between runs so an orbit that crosses
the box twice does not get a chord drawn straight across the view); a mesh is
cut triangle by triangle (`_clipMesh`, Sutherland-Hodgman against the six
faces, each surviving polygon fanned back into triangles). Only a trace with
nothing left inside the box is hidden.

The first version of this rule hid any trace whose bounding box did not fit
*entirely*, and that is what the user sees as things vanishing when they zoom
in. Measured at the Earth zoom (box half 0.0077 AU): **51 of the Solar System's
54 traces failed that test** — Earth's own orbit, which runs straight through
the view, and the water band Earth sits inside, among them. Three traces were
left. With clipping the same view keeps six, and the two that matter are the
arc of Earth's orbit and the band's surface around it.

**No visible coordinate may lie outside the box, and that is the point.**
Plotly normalises its 3D scene against the data that is still *visible*, not
against the axis range, so one marker left switched on at 700 AU — Planet Nine,
Eris, Neptune — while the axis window is a few thousandths of an AU wide
collapses everything inside that window to nothing: no planet, no moon, no
orbit, just gridlines. Hiding what did not fit was one way to guarantee that.
Clipping is the other, and it keeps the view. Verified in Chrome at four zoom
depths: zero points outside the box in every one.

**Markers are hidden, never rewritten.** A single point is either in the box or
out of it, so there is nothing to clip, and the animation writes exactly those
traces' coordinates by index every frame — clipping them would be two writers
fighting over one array. `_traceKind()` routes mesh3d to `mesh`, a multi-point
scatter3d in a `lines` mode to `line`, and everything else to `points`, which
gets visibility and nothing else.

Four things to keep right:

1. **Every path that rewrites the scene must call it.** `rescaleScene()`,
   `restoreScene()`, `viewFromAbove()`, the wheel handler, and `_saReattach()`
   all do. The wheel handler was missing the call, which is why scroll zoom used
   to leave chopped rings on screen.
2. **Clip from the original geometry, never from what is on screen.** `_geom`
   caches the decoded originals at first sight. Reading `gd.data` back would
   hand over the previous clip's output, and a trace would erode a little
   further at every zoom step until nothing was left of it. Zooming back out
   restores every trace to its exact original point count; that round trip is
   what proves the cache is doing its job.
3. **`_saReattach()` must drop `_geom`.** The switcher swaps in a system with
   its own geometry, and two systems can have the same trace count, so the
   count check in `updateSceneVisibility()` cannot catch a swap on its own.
4. **`'legendonly'`, not `false`,** for what is dropped. The legend entry stays
   put instead of appearing and vanishing as the user zooms, and clicking it
   forces the trace back on.

Cost, measured in Chrome: clipping a 12,000-point coil takes 0.27 ms and all 22
Solar System orbit traces together 0.09 ms, against roughly 6 ms for the gl3d
relayout that follows — so the clipping itself is free at the scale this draws
at. What it adds is up to three restyles per box re-cut (visibility, lines,
meshes) where there was one, and only for traces that are actually half in
view; a few kB of coordinates, not the ~480 kB the whole figure holds.

One honest limitation: a clipped line is the polyline's own chord through the
box, not the true curve. Orbits are sampled at one degree, so at deep zoom the
chord and the arc are the same line to well under a pixel — but a very coarse
ellipse (Planet Nine at 700 AU puts 12 AU between samples) clipped into a tiny
box would draw a secant offset from where the real orbit runs. Such an orbit is
almost never the one being zoomed into, and the alternative — hiding it — shows
nothing at all.

**Plotly 3.x base64-encodes coordinates.** `trace.x` on a multi-point trace is
`{bdata, dtype}` with no `.length`, so any code reading coordinates off
`gd.data` must go through `_coords()` first or it silently sees no data. Single-
point marker traces stay plain arrays, which is why the `t.x.length !== 1` test
in `searchTrace()` and `_findNearestBody()` still separates markers from
everything else without paying to decode. `tests/test_viewer_js.py` guards both
halves of this.

## Camera centering — how it works

Double-click zoom converts a body's Cartesian AU position to Plotly's normalized scene coordinates using `normalized = (data - mid) / maxHalf`. Getting this right requires knowing the scene's axis ranges *before* any user interaction — Plotly overwrites `_fullLayout.scene.*.range` with normalized values after every relayout call, making runtime reads unreliable.

**The solution** (implemented 2026-03-24):

1. `mechanics/time_series.py` — `compute_scene_extent(orbit_paths)` scans every orbit path and returns `(x_half, y_half, z_half)`: the max absolute coordinate per axis × 1.1 padding. **There is no 1 AU floor on a system that has something to measure** — there used to be, for the star-only case, and it silently inflated every compact system: TRAPPIST-1 spans 0.068 AU and was drawn in a 1.1 AU box, so its planets and its bands were a sixteenth of the frame. The 1 AU fallback now applies only when there is nothing to size from at all. Because the ranges are symmetric around the origin, `mid == 0` on every axis — eliminating the offset error that caused distant bodies (e.g. Planet Nine) to appear off-center.

2. `viz/themes.py` — `make_scene_style(x_half, y_half, z_half, view_normal)` bakes those half-extents as explicit `range=[-half, half]` entries into the Plotly figure layout at build time, along with a camera rotated into the system's band plane.

3. `viz/animation.py` and `viz/static_plot.py` — both call `compute_scene_extent` on their `orbit_paths` dict and pass the result to `make_scene_style`, replacing the old bare `SCENE_STYLE`.

4. `viz/export.py` — `_build_scene_ranges_js(fig)` reads the baked ranges from `fig.layout.scene.*.range` and emits `window._SA_SCENE_RANGES = {xr, yr, zr}` as a JS constant injected before `_ZOOM_JS`. The multi-system variant emits `window._SA_ALL_RANGES` (keyed by system name) and the system-switcher updates `window._SA_SCENE_RANGES` on every system change. `captureRanges()` in `_ZOOM_JS` checks `window._SA_SCENE_RANGES` first; the old Plotly-layout read remains as a fallback.

**Mathematical guarantee**: with `half = max_orbit_extent × 1.1`, any body's normalized coordinate ≤ `1/1.1 ≈ 0.909`. Worst-case camera eye ≈ `0.963`, safely inside the `±0.98` scene boundary enforced by `_pullBound`.

**Rule**: whenever you add a body — no matter how far out — the centering fix is automatic. No JS changes needed; the Python build pipeline handles it.

## Multi-scale zoom — how it works

The zoom system supports continuous navigation from the full solar system (~770 AU) down to individual moon orbits (~0.003 AU) without any fixed floor or snap-out.

**Double-click zoom** (implemented 2026-03-25):

- `build_body_info_js()` in `export.py` pre-computes `zoom_half_au` per body: for parents it is the core child extent × 3 (so the children fit in frame); for a satellite of any body that is itself in orbit it is own SMA × 1.5; for everything else it is own SMA × 0.01, minimum 0.001 AU.
- Core child extent comes from `_core_child_extent()`, which walks a body's children outward and stops at the first gap wider than `CORE_GAP_RATIO` (50×). Without it Alpha Centauri A would be framed around Proxima at 8,700 AU, leaving the 23 AU A–B binary unreachable by double-click. The Solar System has no such gap, so its framing is unchanged.
- `_SA_BODY_INFO` is shared across the system switcher, so a body appearing in two built-in systems keeps the widest framing of the two.
- `zoom_half_au` is injected into `window._SA_BODY_INFO[name]` alongside mass, period, etc.
- Double-clicking calls `zoomTo()` → `rescaleScene(gd, cx, cy, cz, halfAU, cam)`, which calls `Plotly.relayout` with updated `scene.*.range` **and** the camera in one call. The scene is physically resized around the body, so orbit traces get proper pixel coverage at any scale.
- `_sceneStack` stores up to 12 previous scene states for potential zoom-out history.

**Scroll zoom** (AU-native, implemented 2026-03-25):

The wheel handler works entirely in AU space — no normalized-coordinate fixed floors. The listener itself does nothing but accumulate; `_applyWheelZoom()` does the work:

1. Convert Plotly's normalized `eye` and `center` to AU using current `_sa_ranges`.
2. Scale eye distance: `newDistAU = distAU × factor`, `factor = STEP^-accum` clamped to [0.5, 2].
3. Compute `targetHalf = min(newDistAU × 6, origHalf)`, then keep the current box if `targetHalf / sceneHalf` is inside (0.5, 2) — see **why the box is sticky** below.
4. Clamp the box to `safeHalf = newDistAU / MIN_EYE_NORM` (0.08) — see **the box must follow the camera** below. Then snap the scene centre to the nearest body if the camera's target stays within half of the box it would snap to, applying that body's `zoom_half_au` as a moon-system floor *capped at `safeHalf`*.
5. Lock back to original full-system scene when `idealHalf ≥ origHalf × 0.95`.
6. Single `Plotly.relayout`: always the camera, and the three ranges only when the box actually changed (`boxUnchanged`).

**Why the wheel is coalesced.** Rebuilding a gl3d scene costs far more than the gap
between two wheel events, and a trackpad emits dozens per gesture. Acting on each
one in turn queues relayouts faster than they can retire, which is what made scroll
zoom lurch. So every event only adds to `_wheelAccum`, and `_scheduleWheel()` applies
the total once per animation frame. Measured on the Solar System: a 40-event
trackpad flick went from 40 relayouts + 40 restyles to **one relayout and no
restyle**.

Three things hold that together, and each one is a bug if removed:

- **The step is proportional to `deltaY`, not to the event count.** `deltaMode` is
  normalised to pixels first (lines × 33, pages × 400). With the old fixed per-event
  step, one trackpad flick zoomed ~24× further than the identical flick on a wheel,
  and a hard flick collapsed straight onto the `MIN_AU` floor.
- **`requestAnimationFrame` has a `setTimeout(run, 100)` backstop.** rAF never fires
  in a hidden or occluded tab; whichever arrives first cancels the other, so a
  scroll is coalesced but never simply dropped.
- **`_wheelBusy` has a 1 s watchdog.** It is cleared from Plotly's relayout promise,
  which Plotly resolves from its render loop — a stalled or throttled renderer can
  leave it pending for good, and the flag would then strand scroll zoom until
  reload.

**The box must follow the camera.** WebGL clips everything nearer the eye than
its near plane, and Plotly sets that plane in *normalised* scene units — a fixed
fraction of the box, whatever the box holds. So the camera's distance from what
it is looking at has to stay a healthy fraction of the box. Let the box stay
large while the camera keeps dollying in and the near plane lands *past* the
target: everything on the camera's side is sliced off along a flat cut through
the middle of the view. Every band became a half-disc and every orbit a
half-ellipse, which is what "zooming in cuts half the model" was.

The moon-system floor did it. `zoom_half_au` for the Sun is 1,050 AU — the
Solar System has no 50× gap between Neptune, Pluto, Eris and Planet Nine, so
`_core_child_extent` makes the Sun's "moon system" the whole system — and
scrolling toward the middle of the view, which is toward the Sun, pinned the box
at 1,050 AU while the camera went on in to 5e-8 of it. Verified in Chrome with
the camera held 3 AU from the Sun: a 1,177 AU box cut the scene in half, an
18 AU box around the same camera did not.

Three rules, each a bug if dropped:

1. **Nothing may make the box larger than `safeHalf`** — not the sticky box,
   not the floor. `MIN_EYE_NORM = 0.08` is 8× Plotly's 0.01 near plane and the
   bottom of the band the sticky box was always meant to hold.
2. **The floor is capped at `safeHalf`**, so it still does its job — holding a
   planet's moons in frame as the camera closes on it, all four Galilean moons
   down to a 0.013 AU box — but can never pin the box.
3. **The snap is judged against the box being built, not against
   `zoom_half_au`.** The old radius was `zoom_half_au × 0.5`, which for the Sun
   is 525 AU: the box re-centred on the Sun with the camera looking at a point
   hundreds of AU outside it.

Measured scrolling straight in toward the Sun: the box now tracks the camera
from 1,180 AU down to 0.007 AU — over five orders of magnitude — with the
normalised eye distance never below 0.08. Double-click (eye at 0.40) and Orient
(eye at 2.165) were always safe; only scroll zoom could dive.
`tests/test_scroll_zoom.py` pins the rules and that the Sun's floor really is
the whole system.

**Why the box is sticky.** Re-cutting `scene.*.range` is the expensive half of a
zoom: Plotly re-normalises against the new ranges and re-uploads every trace's
geometry, where moving the camera alone costs a fraction of that. Pinning
`idealHalf = newDistAU × 6` exactly meant every single event re-cut the box. The
band keeps the box on screen while the camera is still a reasonable fit, so it is
re-cut about once every five detents instead — and it is narrow enough that the
normalised eye distance stays inside 0.08–0.33, well within the ±0.98 `_pullBound`
limit. `updateSceneVisibility()` is called only on the events that do re-cut, and it
now restyles only the traces whose visibility actually flips.

**Zooming out must end on the whole system.** The lock back to the original
scene is judged on the box the camera *wants* (`newDistAU × 6`), not on the
sticky one. `targetHalf` is capped at `origHalf`, so a sticky box past
`origHalf / 2` sat inside the band forever and never reached the 0.95 lock:
zooming out of 55 Cnc B left a 1,000 AU box parked on B with A's side of the
system cut off at its edge. Two more rules keep the way out clean:

- **The box never leaves the full-system box.** `_clampInsideOrig()` slides it
  back inside, axis by axis, so it converges on the whole system as it grows
  instead of jumping there at the lock. The body stays in view, because the
  centre moves by at most the overshoot, which is less than the half-width.
- **Zooming out brings the target home.** Each step out moves the camera target
  toward the box centre by `1 - 1/factor`. The snap keeps the box on a planet
  while its moons are in frame, so the target only moves once the clamp starts
  pulling the box toward the system.

`tests/test_zoom_out.py` runs the real `_applyWheelZoom` under node and zooms
out of every body in every built-in system. It checks that each one ends on the
full box, that the box never leaves the system, that the target is within 10%
of the centre by the time the camera is as far out as the figure opens, and
that the near-plane rule still holds. It also pins that the hazard is real:
without the wanted-box clause, all four bodies on B's side of 55 Cancri stick.

**One Plotly call per scene change.** Each restyle or relayout re-draws the
whole gl3d scene. Measured in Chrome, a restyle costs 36–63 ms and a relayout
of the ranges about 50 ms, against 12–16 ms to move the camera alone. A re-cut
used to issue up to four in a row, a 150–240 ms stall mid-gesture.
`updateSceneVisibility(gd, xr, yr, zr, layout)` now builds a single restyle
object, one entry per touched trace with `undefined` wherever an attribute does
not apply (Plotly skips those, verified in Chrome), and sends it together with
the layout as one `Plotly.update`. That call's promise is what the wheel's
backpressure waits on. `rescaleScene`, `restoreScene`, `viewFromAbove` and the
wheel all pass their layout through it.

**Wheel zoom eases.** `_scheduleWheel` applies `WHEEL_EASE` (30%) of the pending
notches per frame and the rest in later frames, down to `WHEEL_EASE_TAIL`. So a
detent becomes a glide over about five frames instead of one 12% cut. The total
travelled is unchanged, and the extra frames are camera-only, the cheap kind of
update. A box of unchanged size is also kept where it is while its centre stays
within a quarter of its half-width of the target, so cursor-mode drift no longer
re-cuts the scene on every step.

`_rescaleLock` (600 ms cooldown after any `rescaleScene`) prevents scroll events from
racing with double-click zoom. The pending delta is **held** across it rather than
discarded, so the 600 ms after a double-click no longer swallows the gesture.

**Orient button** — always restores `_sa_ranges_orig` (the original full-system scene captured at page load) before positioning the camera, so it works correctly even when zoomed deep into a moon system.

**The camera follows the system's band plane, not world z.** Only the Solar
System is quoted in the ecliptic; every system whose angles come from transits
or astrometry is quoted against the plane of the sky, so its bands stand
perpendicular to z by construction and a camera on the z axis sees them
edge-on. TRAPPIST-1 at 89.76 degrees drew eight bands as eight lines.

- `make_scene_style(x, y, z, view_normal)` rotates Plotly's default eye into
  that plane with `camera_for_plane()`. The *angle* is unchanged — it is the
  same three-quarter view — but it is measured against the band. A flat
  system's normal is the z axis, so the rotation is the identity and the Solar
  System's camera does not move.
- `system_view_normal(system)` reads the plane off the first solvent band
  rather than deriving it again, so the camera and the ring it is pointed at
  cannot disagree. `--band-plane reference` puts the bands back on z and takes
  the camera with them, for free.
- `viewFromAbove()` looks down that normal, with `up` set to the line of nodes
  — an `up` parallel to the view direction is degenerate and Plotly renders it
  as an empty scene.
- Python bakes the normal into `scene.camera.up`; `_fig_view_normal()` reads it
  back out into `window._SA_VIEW_NORMAL`, and the multi-system variant emits
  `window._SA_ALL_VIEW_NORMALS` which the switcher updates alongside
  `_SA_SCENE_RANGES`. A swap that moved the ranges but not the normal would
  leave Orient pointing at the previous system's plane.

**Orient's eye distance is in normalised units, not AU.** It used to sit 100 AU
up, which is a sensible height only for a system about 100 AU across: at the
Solar System's 1,177 AU half-extent that is 0.085 normalised units, practically
inside the star, and at TRAPPIST-1's 0.068 AU it is 1,460 units away and
collapses the whole system to a dot. The scene is a cube whatever it holds, so
one framing works for all — `ORIENT_EYE_DIST` is the magnitude of Plotly's own
default eye.
