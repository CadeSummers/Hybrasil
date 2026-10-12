# Nearby Stellar Motion: the featured view of every Systems-tab star

`hybrasil/viz/star_motion.py`, `hybrasil/data/nearby_loader.py`,
`hybrasil/views.py`. Read this before touching any of them, the featured
views, or the viewer features they added (grouped legend rows, owned lines,
scene units, `info.rows`).

## What it draws

Every system on the Systems tab around the Sun, fixed in place: a sphere per star
coloured by spectral type and sized by luminosity, and an arrow for its velocity
**relative to the Sun**. Clicking a star opens its details; double-clicking also
flies to it.

- **Frame:** galactic Cartesian light years with the Sun at the origin. +x points
  at the galactic centre, +y along the galaxy's rotation (l = 90°), +z at the north
  galactic pole. This is the Milky Way map's own frame, so the view's
  `galactic_to_frame` is the identity and the sky needs no rotation. The three
  reference axes (90 ly, dashed) label the directions.
- **Position:** `d·(cos b cos l, cos b sin l, sin b)` from the sheet's
  `Distance (ly)` and `Galactic longitude/latitude`.
- **Velocity:** `Space velocity` along `Motion toward l/b`, which are heliocentric
  with no LSR correction. These are the sheet's own columns, read by header, so
  the view shows exactly what the sheet says. The arithmetic behind them is on
  Sources & Provenance (24 Sep 2026), not repeated here.
- **Two frames, one button.** Every arrow is drawn twice, and the **Galaxy Motion
  Type** button (in the Bands button's place, since the view has no bands)
  shows one set:
  - **Solar Reference** (the default): the sheet's heliocentric velocity, as above.
    The Sun has no arrow, since its velocity relative to itself is zero.
  - **Local Standard of Rest (LSR):** the heliocentric velocity plus the Sun's
    own motion relative to the LSR, `SUN_PECULIAR_KMS` = (U, V, W) = (11.1, 12.24,
    7.25) km/s (Schönrich, Binney & Dehnen 2010). That is the only number this
    frame adds, and Sources & Provenance already cites it (line 3984). The Solar
    System gets its own arrow here, green like its marker: 18.04 km/s toward the
    solar apex, l 47.8°, b +23.7°, so 3.0 ly long.
  - The sheet stays heliocentric. The LSR figures are computed in
    `star_motion.velocity_lsr_kms()` and shown in the info panel (`Speed (LSR)`,
    `Direction (LSR)`) beside the Sun-relative ones.
- **Arrow length:** the tip is where the star will be after **50,000 years**
  (`ARROW_YEARS`), so length is exactly proportional to speed.
  - The conversion is exact: 1 ly/yr is the speed of light, so 1 km/s is
    1/299,792.458 ly/yr (`units.LY_PER_YEAR_PER_KMS`), or 0.1668 ly of arrow per km/s.
  - The head is two wings drawn back through the tip in the same polyline,
    because the three.js viewer skips Plotly cones.
- **No arrow** for a star without an RV or a proper motion on file (27 of 426 on
  the 9 Oct 2026 snapshot). Its panel says which is missing.
- **Play** (since 10 Oct 2026): the view has the systems' ▶ Play button and
  slider. Over 201 frames (`DRIFT_STEPS` = 200 steps, 10 s) every star slides
  along its own arrow, from where it is now to the arrow's tip 50,000 years on;
  the readout runs from "Now" to "+50,000 yr". The arrows stay where they are:
  they are the path.
  - Each star carries `drift` = {frame: its arrow's tip minus its base} in ly
    (`star_motion.drift_ly`), and each cloud a flat `drift` per frame beside its
    `pos`; the layout meta's `drift` = {years, steps} turns it on
    (`scene.drift`). The viewer's `driftFrame()` places everything at
    `pos + drift[motion frame] × fraction`, so switching Galaxy Motion Type
    mid-play moves the stars onto the other frame's arrows.
  - No arrow, no drift: a star with no measured motion stays put, and so does
    the Sun relative to itself. In the LSR frame the Sun moves too.
  - The motion is a straight line at today's velocity, as the arrows are, with
    no galactic orbit or encounter bending it.

## The planetless systems, behind a button

The 80 systems of the workbook's **Planetless 4+ Stars** tab can be added to the
view with the **✚ High Star Count Systems** button (labelled "Planetless Systems" until 10 Oct 2026), which is **off by default**.

- **Data:** each system's host-star row, under the same headers the view reads from
  Systems (`Distance (ly)`, `Galactic longitude/latitude`, `Space velocity`,
  `Motion toward l/b`), filled by `data/four_plus_stars/kinematics.py` (Sources &
  Provenance, 1 Oct 2026). `planetless_loader.parse_planetless()` keeps those
  columns in `PlanetlessSystem.motion`; `nearby_loader.planetless_nearby()` turns
  each system into a `NearbyStar` with `planetless=True` and its own `system_id`.
- **Drawing:** coloured by class like every star, with a white ring
  (`PLANETLESS_RING`), all in one legend group, `PLANETLESS_GROUP`. Their arrows
  are owned by their markers, so they hide with them. The title's system count is
  still the Systems tab's; it adds "(+80 high star count systems on request)". The legend group reads "High star count systems (4+ stars)".
- **"Go to system":** `planetless:<host>`, the web app's id; Castor (alf Gem)
  opens the featured Castor.
- **Where they come from:** the web app passes the systems its library already
  holds (`SystemLibrary.planetless()`); the CLI and the file page load the tab
  themselves, live or snapshot. A failure costs these systems and nothing else.

## The unclassified objects of the Known within 100ly tab, behind a button

Every other catalogued object within 100 ly can be added with the **✚ All Known Systems
within 100 ly** button (labelled "Known within 100 ly" until 10 Oct 2026), **off by default**. These are the unplotted rows of the workbook's
`Known within 100ly` tab, about 10,200 of them, which no other tab draws.

- **Data:** `catalog_loader.parse_workbook()` keeps the tab's `Plotted = FALSE`
  rows in `Catalog.known_unplotted`, though the tab is still never a source of
  systems (`KNOWN_SIGNATURE`). `nearby_loader.known_nearby()` turns them into
  `NearbyStar`s with `known=True` and leaves out any name the Systems or stars
  tabs already draw. The position and motion columns were filled by
  `data/known_within_100ly/kinematics/` (Gaia DR3, SIMBAD, then literature
  research; Sources & Provenance, 8 Oct 2026).
- **Drawing:** purple, `UNCLASSIFIED_COLOUR` `#B266FF`, at 4 px, because none is
  classified yet (TODO.md). An object with a space velocity gets an arrow, and
  one with only a proper motion gets a dot.
- **Existence unconfirmed, aquamarine:** the 689 objects whose `Existence` cell
  reads `unconfirmed: only cited in Gaia DR3` are a second cloud,
  `UNCONFIRMED_COLOUR` `#7FFFD4`, with its own legend row ("Existence unconfirmed
  (Gaia DR3 only)"), behind the same button (`known_clouds()`). SIMBAD has no entry
  for their Gaia DR3 identifier and CNS5 does not list them. Gaia's own
  spurious-astrometry score, `fidelity_v2` (Rybizki et al. 2022), is below 0.05
  for every one, so most are probably not within 100 ly at all. They are flagged,
  not removed. Their panel opens with **Existence unconfirmed: Only cited in Gaia
  DR3** and the score.
- **The button cycles** (since 10 Oct 2026): Off → **All** → **Excluding
  unconfirmed** (the purple cloud alone) → **Unconfirmed only** (the aquamarine
  cloud alone) → Off. The set carries `modes` (`KNOWN_MODES`); a search that
  finds an object its mode hides turns the set back to All.
- **A cloud, not traces:** 10,000 single-point traces and 14,000 arrow traces
  would be 24,000 draw calls. `star_motion.known_cloud()` ships them as one
  compact `layout.meta.clouds` entry instead. `figure_to_scene` passes it on as
  `scene.clouds`, and the viewer draws one `THREE.Points` and one
  `THREE.LineSegments` per motion frame. The entry holds:
  - `pos`: flat light years;
  - `arrows`: segment pairs per frame, base–tip plus the two head wings;
  - `info`: one compact row per object, which the viewer turns into an info
    panel the first time the object is opened;
  - `sources`: the distinct Kinematics source strings that `info` indexes into;
  - `linkTemplates`, `idSlots`, `existence`: the Sources links, below.
- **Behaviour:** picking, hover, single and double click, search and the info
  panel all work per point (`cloudPoint()`, `cloudInfo()`). The cloud has one
  legend row, listed while its set is on, and its arrows follow the motion
  frame and the Motion row. `__SA3.clouds()` is the test handle.

### Optional sets, the general feature

A figure may declare `layout.meta.optional_sets` = `[{key, label, default, count,
title, modes?}]` and tag marker traces with `meta.optional = key`. `figure_to_scene`
carries them as `scene.optionalSets` and each body's `optional`. The viewer then:

- draws one button per set (`✚  <label>: Off|On`), shown only in a scene that
  declares it. A set with `modes` (`[{key, label, clouds?}]`) keeps the mode's
  key as its state: the button reads `✚  <label>: <mode label>` and steps
  through the modes, then back to Off; a mode that names `clouds` shows only
  those clouds of the set;
- shows a set's bodies, and the lines they own, only while it is on;
- lists the set's legend group only while it is on;
- keeps the choice across a switch to another system and back, as the motion
  frame is kept;
- turns the set on when a search lands on one of its bodies.

`__SA3.optional(key)` and `setOptional(key, on)` are the test handles.

A set may hold **lines** as well as bodies: a scene line with `optional: key`
is shown only while its set is on (`refreshOwnedLines`), and its legend group is
listed under the set's label only while it is on. A set declared with
`menu: "features"` gets no bar button: it is a toggle row of the **Even more
features ▾** menu instead, which is hidden in a scene without such a set. The
photosynthesis rings are the first (`docs/architecture/photosynthesis.md`).

## Sources: where each star is on record

Every star's info panel ends with a **Sources** section, the one a system's
star has (`band_kit.js` `showInfoPanel`, `[label, url]` pairs, escaped). It
lists:

- **Existence**, labelled `Exists:`: a curated catalog that lists the object
  (SIMBAD, CNS5, the Multiple Star Catalog, the NASA Exoplanet Archive for a host
  of a confirmed planet), and its Gaia DR3 row;
- **Motion**, labelled `Radial velocity:` / `Proper motion:`: the papers and
  catalogs behind those two numbers. One source for both is listed once.

The data comes from four columns that `data/existence/` added to the Known,
Systems and Planetless 4+ Stars tabs on 9 Oct 2026 (README there):

- `SIMBAD main_id`, `CNS5 id` (Known only) and the existing `Gaia DR3 source_id`
  and `WDS code`;
- `Existence`, the verdict;
- `Kinematics refs`, `RV: <refs>; PM: <refs>`, read from the motion cells' own
  SOURCE notes.

`catalog_loader.source_columns()` and `planetless_loader._MOTION` read them by
header, and `nearby_loader.with_sources()` builds each star's links.

- **Every URL format is in `data/star_sources.py`, once.** Each was opened and
  found to return its record. A bibcode goes to ADS; a catalog named without a
  row goes to its VizieR landing page.
- **The cloud builds its links in the browser.** Shipping ten thousand link lists
  would add megabytes, so `known_cloud()` makes one link template per distinct
  pattern of ids present and Kinematics refs, with `@GAIA@` / `@SIMBAD@` / `@CID@`
  in place of the ids. `cloudSources()` in `three_viewer.js` swaps a point's ids
  in: raw in a label, URI-encoded in a URL. No URL is written in the JavaScript.
- **The Sun** links Schönrich, Binney & Dehnen 2010, the source of its LSR motion.

## Colours and sizes

| Class | Colour | | Class | Colour |
|---|---|---|---|---|
| O | `#9BB0FF` | | K | `#FFA040` orange |
| B | `#AABFFF` | | M | `#FF4A3A` red |
| A | `#CAD7FF` | | Brown dwarf (L/T/Y) | `#A0522D` |
| F | `#FAF3C0` pale yellow | | White dwarf | `#9A9A9A` grey |
| G | `#FFE24A` yellow | | Sun | `#33DD55` green |
| Class unknown | `#CCCCCC` | | Unclassified (All Known Systems within 100 ly) | `#B266FF` purple |
| | | | Existence unconfirmed (Gaia DR3 only) | `#7FFFD4` aquamarine |

- **Class** comes from the first letter of `Stellar Class` after stripping `~` and
  an `sd`/`esd` prefix. A composite takes its primary (`G5V+K1V` is G). A class
  starting with `D`, or luminosity class "White dwarf", is a white dwarf, so RR Cae
  (`DAZ8+M4`) is grey. Brown dwarfs were not in the original request; dark
  red-brown was chosen for them.
- **Size:** `clamp(7 + 2.2·log10(L), 3, 14)` px. The Sun is drawn at 11 as the
  focal point. A star with no luminosity is 5.
- **Legend:** one row per class, listed O → M, then brown and white dwarfs. A
  class row hides its stars and the arrows they own. The Motion row hides every
  arrow and leaves the stars.

## Each star's own facts, not its row's

The Systems tab's `Host luminosity` is **the planet host's** on some rows
(Sources & Provenance, line 1276): alf Cen A's row carries Proxima's 0.0015 L☉.
So class, mass and luminosity come from `catalog_loader._star_facts()`, which
reads the stars tab first, as the rest of the catalog code does. Age and
metallicity come from the Systems row, which describes the primary. Planets are
listed from every star in the system. A non-confirmed planet is named with its tier
("Planet Nine (ambiguous candidate)"), and the "Solar System reference" tier
counts as confirmed.

## Where the data comes from

`load_nearby()` uses, in this order:

1. the catalog it is handed (the web app passes its own);
2. the live sheet (`get_catalog()`, 24-hour cache, stale cache on a failed fetch);
3. the newest committed snapshot `data/hybrasil-*.xlsx` (`data/snapshot.py`,
   openpyxl).

So the button opens without a Google credential. The source is named at the end
of the view's title. `HYBRASIL_DATA_SOURCE=snapshot` (formerly
`HYBRASIL_NEARBY_SOURCE`, still honoured) skips straight to the snapshot, for
every workbook loader. `tests/conftest.py` sets it, so the suite needs no credential and
sees the same stars every run. **A snapshot is only as current as its export**
(data/README.md). Refresh it when the Systems tab's positions or kinematics change.

## Why a view and not a built-in system

A built-in (`BUILTIN_NAMES`) is a `StarSystem` with orbits, bands, animation
frames and a Plotly twin. A great deal assumes exactly that: band flatness in
both renderers, the Plotly switcher, frames and natural spans. This view has
none of those, and is in light years, which the Plotly viewer's AU-native zoom
does not understand. So `views.FEATURED_VIEWS` registers it separately:

- **CLI (`_with_views`):** added after the built-ins, **three.js only**, with its
  info merged into `_SA_BODY_INFO`.
- **Web app:** a featured index entry after the built-ins, built on demand from
  the library's catalog, else the snapshot.
- **Plotly renderer and `--output html`/`png`:** not shown.
- `tests/test_featured_baseline.py` and `tests/test_web_app.py` pin the order.

## Viewer features it added, all general

- **`scene.units`** (default "AU"): a "ly" scene's hover tooltip gives the
  distance from the Sun instead of x/y/z in AU.
- **Grouped bodies** (`legendgroup` → `group`, `groupTitle`): one legend row per
  group under `scene.groupHeading`.
- **Owned lines** (`meta.owner`): a line is shown when its line group is on and
  its owner is visible (`refreshOwnedLines`). A body's own legend row refreshes
  them too, so the Solar System's row hides its LSR arrow.
- **Motion frames** (`layout.meta.motion_frames` → `scene.motionFrames`, and
  `meta.frame` on each line): a scene that declares them gets a button titled
  after them in the Bands button's place, cycling through the options. An owned
  line with a frame is shown only while that frame is chosen. The choice
  survives a switch to another system and back. `__SA3.motionFrame()` and
  `setMotionFrame()` are the test handles.
- **`info.rows`:** an info-panel entry may carry `[label, value, note]` rows,
  which `band_kit.js` renders escaped. Entries without it are unchanged in both
  viewers.
- **`info.zoom_half`:** double-click framing in the scene's own units, ahead of
  `zoom_half_au`.
- **A single click** on any body opens its panel without moving the camera; a
  click that ends a drag does not.
- **`info.goto`: the "Go to system" button.** Each star's entry carries the id of
  its own system, from `builtin_systems.system_id_for_host()`: the featured
  system that covers or goes by the host (the Sun opens the Solar System, alf
  Cen A the featured Alpha Centauri), else `catalog:<host>`, the web app's id.
  `band_kit.js` draws the button only when the viewer's `setInfoGoto` handler
  says the page can open that id: every system the server lists in the web app,
  only the featured ones in a file page. A star whose planets were all rejected
  (GJ 680, Kapteyn) has no system to open and no button: 18 of 427 on the
  28 Sep 2026 snapshot.

## Tests

- `tests/test_star_motion.py`:
  - colours, sizes, arrow proportionality and direction;
  - the two frames: every LSR arrow is its heliocentric one plus
    `SUN_PECULIAR_KMS`, and the Sun's green arrow exists only in the LSR frame;
  - positions against RA/Dec through `orientation.EQUATORIAL_TO_GALACTIC`;
  - the loader on literal rows and the snapshot fallback;
  - every requested info field;
  - every star's Sources opens with an `Exists:` link; the source columns are read
    by header; the aquamarine cloud holds exactly the Gaia-only objects (689 on the
    snapshot, all `fidelity_v2` < 0.5) and its link templates fill to what
    `star_sources` builds (`tests/test_star_sources.py` pins each URL format);
  - each star's `goto` id, and that the web app's index can open them;
  - the scene conversion, with existing systems unchanged;
  - registration.
- `tests/test_browser.py` (three.js):
  - the button opens a ly scene;
  - a real click shows the panel with its Sources links, and the hover reads ly;
  - an aquamarine point's panel says "Existence unconfirmed: Only cited in Gaia
    DR3" and links its Gaia DR3 row; a source label holding markup is shown as text;
  - a class toggle hides stars and their arrows;
  - Galaxy Motion Type replaces Bands, switches the arrow set (plus the Sun's in
    LSR), and keeps its choice across a system switch;
  - Alpha Centauri's bands are still flat after the view;
  - "Go to system" opens alf Cen A's featured system in a file page (and is
    absent for tau Cet there), and tau Cet's catalog system in the web app
    (absent for GJ 680), bands flat after each.
