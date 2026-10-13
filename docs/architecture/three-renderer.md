# The three.js renderer (the default)

The viewer every browser and HTML command opens, drawing the same figures the
Plotly viewer draws. `--renderer plotly` opens the original Plotly viewer, and
`--output png` still goes through Plotly, since three.js does not write
images. The default became three.js once this viewer had the band sliders,
search, info panel, Back button and legend.

## Why it exists

Plotly's gl3d scene puts WebGL's near plane at a fixed fraction of its axis
box. A camera that dollies in has to drag the box in with it, and every re-cut
of the box re-normalises and re-uploads every trace (~50 ms, measured). That
is where the Plotly viewer's zoom machinery comes from: sticky boxes, the lock,
clipping, the near-plane rule (`zoom-and-visibility.md`). It is also the floor
under how smooth that zoom can get.

three.js with `logarithmicDepthBuffer: true` has no box. Depth precision is
spread logarithmically over the whole near–far range, so one camera covers a
moon's orbit and the whole system. A zoom is a camera move: nothing is
re-uploaded, and OrbitControls' damping turns wheel steps into continuous
motion.

Measured in headless Chromium (software WebGL) while zooming out of each
system's outermost body (`pytest -s tests/test_browser.py`):

| System | Plotly p50 / max | three.js p50 / max |
|---|---|---|
| Solar System | 17 / 181 ms | 17 / 18 ms |
| Alpha Centauri | 17 / 169 ms | 17 / 18 ms |
| 55 Cancri | 17 / 102 ms | 17 / 18 ms |

## How it is built

`figure_to_scene()` in `three_viewer.py` converts the **Plotly figure** into a
JSON scene instead of building the scene a second time from the system. So
both renderers draw identical data: the same orbit samples, the same coils, the
same band vertices and faces. A solvent band is a flat disc here for the same
reason it is one in Plotly: it is the same mesh.
`tests/test_three_viewer.py` pins that the conversion loses nothing.

| Plotly trace | three.js object |
|---|---|
| `scatter3d` lines, width > 1.5 | `Line2` (fat line, pixel width) |
| `scatter3d` lines, width ≤ 1.5 | `THREE.Line` (1 px GL line, as Plotly draws it) |
| one-point `scatter3d` marker | `THREE.Points`, fixed pixel size, CSS2D label |
| `mesh3d` band / belt | `THREE.Mesh`, `MeshBasicMaterial`, double-sided, no depth write |
| frames + `layout.meta.kepler` | a body with elements placed by Kepler's equation at the moment shown (rule below); anything else interpolated linearly between frames |
| `cone` (arrow heads) | left out; the arrow's line and label carry it |
| `layout.meta.photosynthesis_rings` (no trace) | `THREE.Line` per ring, an optional-set line; see `photosynthesis.md` |

## Rules, each a bug if dropped

0. **Between frames a body is placed by Kepler's equation, never by the chord.**
   - A frame step can be longer than an orbit: Proxima's is 19 days and Proxima d's orbit 5.2.
   - Sliding a marker along the straight line between two frames cut through the inside of its ring, by up to 35% of
     the orbit. That was the "planet drifts off its orbit" report of 9 Oct 2026.
   - `kepler_meta()` (animation.py) puts each body's elements on the layout meta, keyed by its marker's label.
     `setFrame()` solves for the fractional frame's date with `keplerXYZ()` / `keplerPosition()`, adding parents as
     `system_time_series` does.
   - This is a second copy of `mechanics/kepler.py`. `tests/test_kepler_js.py` runs it under node against
     `elements_to_cartesian()`, and `test_three_between_frames_a_planet_stays_on_its_orbit` checks `setFrame()` uses it.
   - Plotly does not interpolate (its transitions are 0 ms), so its markers jump from frame to frame but always land
     on their rings.

1. **Near and far stay within 1e14 of each other.** OrbitControls'
   zoom-to-cursor unprojects a point on the far plane. At 1e-11 / 1e10 AU (a
   1e21 ratio, the first try) that point is infinite and the camera went to NaN
   on the first wheel step. The limits are `1e-8` AU (1.5 km) and `1e6` AU.
2. **Nothing reads projected depth.** At that ratio `Vector3.project()` puts
   every point in the scene at depth ≈ 1. "Behind the camera" is judged in
   view space (`applyMatrix4(camera.matrixWorldInverse)`, z ≥ 0) in picking
   and in the tests.
3. **Geometry is re-based on its own centre in double precision** before it
   becomes a `Float32Array`. 55 Cnc B's planets sit 1,066 AU out; stored
   absolute, float32 rounds them to ~6e-5 AU and they jitter at deep zoom.
   Each line and mesh carries its centre as `object.position`, which three.js
   keeps in doubles.
4. **Wide lines only.** Fat `Line2` draws each segment as its own quad. Three
   12,000-point coils as `Line2` took Alpha Centauri from 17 to 103 ms a frame
   under software rendering; as 1 px lines they cost nothing measurable.
5. **An orbit round a moving parent rides with it** -- a moon's round its planet, and any other ellipse whose parent
   moves, such as Castor C's round the Castor AB barycentre.
   - The ellipse is sampled round the parent where the parent is at `t_start` (`system_orbit_paths()`).
   - `_orbit_trace()` tags the orbit `meta={"follows": <parent's marker label>}` whenever the parent has elements,
     and `figure_to_scene()` carries that tag across as the line's `follows`.
   - Until 9 Oct 2026 only moons were tagged. Castor C's 13,000-year ellipse then stayed where Castor AB was at
     `t_start`, while AB moved about 38 AU in the span: 2% of C's orbit
     (`TestMoonOrbitsRideTheirPlanet::test_any_ellipse_round_a_moving_parent_rides_it`).
   - Every `setFrame()` sets the line's position to its home centre plus how far the planet has moved since frame 0.
   - Without this, the planet and moon leave the ellipse during playback. CD-35 2722 b moves 0.32 au over a span its moon's 0.2 au ellipse is drawn for.
   - The move is a change of `object.position`, which three.js keeps in doubles, so rule 3's precision is unchanged.
   - The Plotly viewer ignores the tag, and its moon ellipses still stay put (`TODO.md`).
   - `test_three_a_moons_orbit_rides_with_its_planet` pins it with Earth's Moon.
   - **A rotation axis rides with its own body the same way.** `_axis_trace()` tags the axis
     `meta={"follows": <the body's label>}`. Plotly's frames redraw the axis, but the three.js viewer reads only
     the markers from them, so until 9 Oct 2026 every axis stayed where its body was at frame 0
     (`test_three_a_rotation_axis_rides_its_body`). The pole's direction is fixed, as it is in the frames.
   - **A band rides with its star the same way.** Each band is built round its star at `t_start`, and
     `band_meta()` names that star as `body`. `figure_to_scene()` passes it on as the band's `follows`.
     `placeBand()` puts the mesh at its home centre plus how far the star has moved, on every
     `setFrame()` and every slider rebuild (`setRing()`).
     - `body` is the star's **label** (`centre_body_label()`), because that is what its marker is called.
       Proxima's label is "Proxima Centauri (hypothetical orbit)", and matching on the bare name left
       its bands behind.
     - A primary at the origin never moves, so its bands stay put. Castor Ab's circle Aa with Ab.
     - `meta.centre` stays the `t_start` position: `stackOffsetsByCentre()` groups a stack by it.
     - The Plotly viewer leaves its bands where they were built. Moving them there means frames writing
       to band traces by index, which is the hazard behind the torus bug (CLAUDE.md).
     - `test_three_a_band_rides_with_its_star` and `TestBandsRideTheirStar` pin it.
6. **Picking is in screen space.** Bodies are a fixed number of pixels wide at
   every distance, so a world-space pick radius would be right at one zoom
   only.
7. **Rotation is free; OrbitControls only zooms and pans.**
   - **Why OrbitControls' rotation is off.** OrbitControls is a turntable: it
     orbits one pole and clamps at it. It also reads that pole from `camera.up`
     once, in its constructor (`_quat`). That was +Y, before `orient()` levelled
     the view to the band plane, so a drag stopped dead with the Solar System
     edge-on.
   - **Its settings.** `enableRotate` is false. `mouseButtons.LEFT` and
     `touches.ONE` are null: OrbitControls would otherwise turn Shift+left
     into a pan.
   - **What turns the camera.** The "Free rotation" block in `three_viewer.js`.
     - A drag turns the camera about the screen's own axes, at OrbitControls'
       scale.
     - Shift+drag rolls, and so does a two-finger twist. On a twist the pinch
       still belongs to OrbitControls.
   - **`camera.up` is view state now.** `rotateView()` turns it with the camera,
       so it stays square to the view direction and there is no pole. Orient
       and a system switch level it to the band plane again. A flight
       (`flyTo`) turns it over the flight rather than snapping it, so Back
       restores a rolled view.
   - **The damping.** A drag feeds `spin`, and `loop()` spends a
     `dampingFactor` share of it each frame. That is OrbitControls' damping.
     Only a flight discards what is left: the rest is part of the drag, not
     just momentum.
   - **The tests.** `test_three_a_drag_carries_the_camera_over_the_pole` fails
     on the turntable, so it pins the hazard. Its siblings pin the sideways
     drag, Shift+drag, the twist, and Orient levelling a roll.

## Shared with the Plotly viewer: `band_kit.js`

The band sliders, the info panel and the search ranking are not reimplemented
here. They come from `viz/band_kit.js`, the same file the Plotly viewer splices
into `_ZOOM_JS`. The page loads it as a classic script exporting
`window.SABandKit` (see `kit_script()`), before the viewer module.

- **Sliders.** `SABandKit.bandPanel()` is the Plotly viewer's panel, with the
  log pressure track, typed readouts, clamping toast and per-frame
  coalescing. Its `onChange(P, A, G)` calls `recomputeBands()`, which rebuilds
  every solvent band with `bandRadiiAU`, `stackOffsetsByCentre`, `ringMesh`
  and `bandName`. On load that rebuild lands on Python's rings to float32,
  which the browser tests check band by band.
- **A band with no liquid phase is a mesh with nothing in it.** Each band
  keeps `on` (asked for, by the Bands button, a legend row or a search) apart
  from `hasRing` (something to draw at this pressure), and is visible only when
  both hold. The Plotly viewer keeps the same split as `bandOn` and a blank
  trace. The legend row stays, dimmed.
- **The sliders carry across a system switch.** `build()` rebuilds the new
  system's bands at the panel's values.
- **Search** ranks with `nameMatches` in the Plotly viewer's order: bodies,
  then bands (switching on only the band found), then orbits and coils.
- **Info panel.** `showInfoPanel` is the Plotly viewer's panel, reading
  `_SA_BODY_INFO`. A camera drag puts it away, but not within 800 ms of
  opening it, or the flight a double-click starts would close it.

## Back and the legend

- **Back** flies to the camera as it was before the last double-click or
  search (`pushView` / `goBack`, 12 deep). Scroll and drag push nothing, so
  the history holds only deliberate jumps, and Orient and a system switch clear
  it: the Plotly viewer's `_sceneStack` rules. With nothing left it says
  "Already at the widest view". A jump made while a flight is still under way
  pushes that flight's destination, not the point the camera had reached, or
  two quick searches leave Back stopping short of the first body. Browser
  tests wait on `__SA3.flying()` rather than a fixed delay: under SwiftShader
  the sky's first composite, about a second after load, stalls a frame for
  ~350 ms, longer than the gap between a 700 ms flight and a 900 ms sleep.
- **The legend** lists what Plotly's does, in the same three groups: every
  body, every band and belt, and the reference arrows (a Python test holds the
  two lists equal for every system). A body row hides the marker and its label
  and leaves the orbit, as a Plotly legend click does. A hidden body can't be
  double-clicked. A search for it shows it again.
- **The legend is rebuilt with the scene, keyed on the world object.** Keyed
  on the system name, re-opening the same system left rows bound to the
  discarded objects, and a click toggled nothing.
- **Markers are drawn as Plotly draws them:** a filled disc, a star's disc
  with a white edge, or a hypothetical body's hollow ring. The scene carries
  `fill` and `edge` separately. Taking the marker colour alone drew every
  hollow body (fill `rgba(0,0,0,0)`) as a black dot on a black sky.

## On a phone: compact

Below 700 px wide, or 500 px tall (a phone on its side), the viewer folds its
controls away so the system has the screen (`COMPACT`, `setCompact()` in
`three_viewer.js`). Everything starts closed until tapped. Since 13 Oct 2026:

- **The toolbar is one row:** `⦿` Orient, `◁` Back, `◎ Off` Bands, `▶` Play,
  the time slider and its date, and `⋯`. Each icon-only button keeps its full
  name as `aria-label`. The `⋯` menu holds search, Sky, Even more features
  (opening in place), the optional-set buttons, Suggest Changes and About.
  These are the same elements, moved by `MENU_ITEMS`, which leaves a comment
  marker where each one stood so it goes back to that exact place on a wider
  screen.
- **More Modeled Systems** drops from the whole bar, edge to edge.

- **The featured systems** sit under one `★ <open system> ▾` toggle. They are
  the same buttons, moved into a popup, so nothing about what a button does
  changes. On a wide screen the wrapper is `display:contents` and the row lays
  out as it always has.
- **The band panel** folds behind a header that carries its three values
  (`Band inputs: 1 bar · 0.30 · 33 K ▾`). This is `band_kit.js`'s
  `setCompact()` / `setOpen()`, opt-in, so the Plotly viewer, which never calls
  it, is unchanged.
- **The legend** folds behind `☰ Legend ▾`. Its rows go into `legendBody`, and
  the `legend` box keeps the header.

The two folded headers share a row. Opening one closes the other. An open band
panel pushes the legend header below it, and an open legend is drawn opaque over
the panel's header. `test_three_a_phone_folds_featured_bands_and_legend` drives all of
this at iPhone size, and every other browser test runs at 1400 × 850, which is
not compact.

## What it does not do yet

- PNG export. `--output png` renders the Plotly figure, and an explicit
  `--renderer three --output png` is refused.
- Plotly's legend double-click, which isolates one entry.
- The Zoom: Center / Cursor toggle. three.js always zooms toward the cursor.

## Testing

`tests/test_browser.py` runs the three.js viewer in headless Chromium for every
system. It checks that every band is a planar `THREE.Mesh`, not points or
lines, from the Bands button and from a band's own legend entry, after arriving
from another system. It also checks that zooming out of a body brings every
body back into view with no frame over the stall limit.
