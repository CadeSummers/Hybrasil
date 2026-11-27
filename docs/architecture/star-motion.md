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
  - **The arrow beside Play chooses the range** (since 25 Nov 2026): now to
    +50,000 yr (the default), −50,000 yr to now, or −50,000 yr to +50,000 yr.
    The past needs no data of its own: it is the same straight line run
    backwards, `pos + drift × s` with `s` from −1. The ranges are declared in
    Python (`star_motion.drift_ranges()` → `scene.drift.ranges`, `from`/`to`
    in units of `ARROW_YEARS`); the viewer's `driftSpan()` reads them.
    - The pace is the same in each: 200 steps per 50,000 years, so the
      combined range is 401 frames and 20 s.
    - Choosing a range pauses and keeps the moment on screen if the new range
      holds it; otherwise it shows today (`setDriftRange()`, `nowFrame()`).
      The choice survives a switch to another system and back.
    - **Past trails:** in the two past ranges each star with an arrow also
      gets a faint line from where it was 50,000 years ago to where it is
      now. `buildTrails()` makes them in the browser from `drift`, one per
      arrow and one `LineSegments` per cloud and motion frame, so the scene
      file does not grow. A trail is shown under its arrow's rules (class
      row, Motion row, motion frame, optional set) and only while the range
      reaches into the past. A trail has no `name`, so `__SA3.lines()`,
      search and the legend never see it; `__SA3.trails()`, `driftRange()`
      and `setDriftRange()` are the test handles.

## Systems Modeled: the dropdown that chooses what is drawn

Since 27 Nov 2026 one dropdown, **Systems Modeled ▾**, replaces the two cycling
buttons (✚ High Star Count Systems, ✚ All Known Systems within 100 ly).

- **By default the view draws only systems with a planet or a planet candidate
  on file**: 409 on the 26 Nov 2026 snapshot, plus the Sun. The dropdown's first
  row says so, ticked and fixed ("Systems with exoplanets or candidates").
- **Four tick boxes follow, all off to begin with, each an optional set of its own:**

  | Box | Set key | What it adds |
  |---|---|---|
  | High Star Count Systems | `planetless` | the Planetless 4+ Stars tab's 80 systems and the Systems tab's 5 star pairs with no planet, ringed white |
  | All Known Systems within 100 ly | `known` | the purple cloud |
  | Unconfirmed Systems (Gaia DR3 only) | `known-unconfirmed` | the aquamarine cloud |
  | Refuted Systems | `refuted` | the 12 refuted systems, ringed red |

- **All** is the last row. It ticks every box; clicked while every box is
  ticked, it clears them. It reads ticked only while all four are.
- The boxes are independent. The old cycle's steps are combinations of them:
  "Excluding unconfirmed" is the purple box alone, "Refuted only" the red one
  alone. A search that lands on a hidden object ticks that object's box and no
  other.
- **The five star pairs moved.** HIP 55507, GJ 680 and three Gaia DR3 pairs have
  no planet on file (each "planet" was a companion star), so they are not drawn
  by default any more: `build_star_motion_figure` puts a Systems-tab star with no
  planet, not refuted, in the `planetless` set (`MotionView.planet_hosts_only`,
  off for Brightest Stars in the Night Sky). They keep their arrows, panels and
  "Go to system".
- **In the figure:** each set carries `menu: "systems"`, and
  `layout.meta.optional_menus` = `{"systems": {label, base, all}}` declares the
  dropdown (`scene.optionalMenus`). In the viewer, `setMenu()` is the one
  dropdown component: Even more features is an instance of it, and a scene's
  own menus are made on demand (`syncSetMenus()`). On a phone it moves into the
  ⋯ menu and opens in place, as Even more features does.

## The planetless systems, behind a tick box

The 80 systems of the workbook's **Planetless 4+ Stars** tab can be added to the
view with the **High Star Count Systems** box of Systems Modeled (a button of its own until 27 Nov 2026), which is **off by default**.

- **Data:** each system's host-star row, under the same headers the view reads from
  Systems (`Distance (ly)`, `Galactic longitude/latitude`, `Space velocity`,
  `Motion toward l/b`), filled by `data/four_plus_stars/kinematics.py` (Sources &
  Provenance, 1 Oct 2026). `planetless_loader.parse_planetless()` keeps those
  columns in `PlanetlessSystem.motion`; `nearby_loader.planetless_nearby()` turns
  each system into a `NearbyStar` with `planetless=True` and its own `system_id`.
- **Drawing:** coloured by class like every star, with a white ring
  (`PLANETLESS_RING`), all in one legend group, `PLANETLESS_GROUP`. Their arrows
  are owned by their markers, so they hide with them. The title's system count is
  the Systems tab's systems with a planet; it adds "(+85 high star count systems on request)", the five star pairs included. The legend group reads "High star count systems (no known planet)".
- **"Go to system":** `planetless:<host>`, the web app's id; Castor (alf Gem)
  opens the featured Castor.
- **Where they come from:** the web app passes the systems its library already
  holds (`SystemLibrary.planetless()`); the CLI and the file page load the tab
  themselves, live or snapshot. A failure costs these systems and nothing else.

## The unclassified objects of the Known within 100ly tab, behind two tick boxes

Every other catalogued object within 100 ly can be added with the **All Known Systems
within 100 ly** box of Systems Modeled (a button of its own until 27 Nov 2026), **off by default**. These are the unplotted rows of the workbook's
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
  (Gaia DR3 only)"), behind a
  box of its own, **Unconfirmed Systems (Gaia DR3 only)** (`known_clouds()`; each cloud's `optional` is its own key). SIMBAD has no entry
  for their Gaia DR3 identifier and CNS5 does not list them. Gaia's own
  spurious-astrometry score, `fidelity_v2` (Rybizki et al. 2022), is below 0.05
  for every one, so most are probably not within 100 ly at all. They are flagged,
  not removed. Their panel opens with **Existence unconfirmed: Only cited in Gaia
  DR3** and the score.
- **No cycle any more.** From 10 Oct to 27 Nov 2026 one button stepped Off → All →
  Excluding unconfirmed → Unconfirmed only → Refuted only. Each of those is now a
  combination of tick boxes ("Systems Modeled" above).
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

## Refuted systems, behind their own tick box

A **refuted system** is a Systems-tab star whose every planet has gone to the
Rejected candidates tab, and which has no companion star to draw in a planet's
place: 12 of 426 on the 26 Nov 2026 snapshot, Kapteyn's star among them. It
has no planet on file (`Catalog.hosts()`) and is no system of stars
(`Catalog.star_systems()`), so there is no system to open. Since 25 Nov 2026 the view keeps it, apart from the rest:

- **The rule is derived, never a list.** `nearby_stars()` fills
  `NearbyStar.rejected` with the (name, reason) of every rejected candidate
  filed under the system's stars, and sets `refuted` where there is at least
  one, no planet left and no page of stars to open. A workbook change moves a star in or out.
- **Hidden until asked for.** Its marker keeps its class colour inside a red
  ring (`REFUTED_RING`), in the legend group "Exoplanet system refuted", and is
  tagged `meta={"optional": REFUTED_SET}`. It is drawn only while Systems
  Modeled's **Refuted Systems** box is ticked; every ordinary star stays as it is. Its
  arrows are owned by it, so they come and go with it. The title counts the
  refuted apart ("409 systems ... (+12 refuted systems on request)"). GJ 229
  left the list on 25 Nov 2026, when its brown dwarf pair went on file
  (`data/gj229/`): Ba on Planets, Bb its moon on Exomoons. HIP 55507, GJ 680
  and GJ 773 B left it on 26 Nov 2026: each "planet" was a companion star, the
  stars are on Multi-stars, and the system opens as its stars and bands. GJ 4113
  and APM 89 followed the same day, once their pairs were on Multi-stars
  (`data/refuted_pairs/`). Their panels keep the "Rejected candidates" row.
- **The panel says so.** The entry carries `goto_note` instead of `goto`:
  `band_kit.js` draws "Go to system" disabled and greyed, with **Exoplanet
  system recently refuted** in red under it (`#_sa_info_goto_note`, escaped).
- **"Rejected candidates" row.** Any star with a rejected candidate, refuted
  or not, lists each with the first sentence of the sheet's reason
  (`_rejected_text()`): Kapteyn's reads "Kapteyn b (...); Kapteyn c (ROTATION)".

### Optional sets, the general feature

A figure may declare `layout.meta.optional_sets` = `[{key, label, default, count,
title, modes?}]` and tag marker traces with `meta.optional = key`. `figure_to_scene`
carries them as `scene.optionalSets` and each body's `optional`. The viewer then:

- draws one button per set (`✚  <label>: Off|On`), shown only in a scene that
  declares it. A set with `modes` (`[{key, label, clouds?}]`) keeps the mode's
  key as its state: the button reads `✚  <label>: <mode label>` and steps
  through the modes, then back to Off; a mode that names `clouds` shows only
  those clouds of the set;
- shows a set's bodies, and the lines they own, only while it is on; a body
  that names a `mode` (`meta.mode`, a refuted system) only in that mode
  (`bodyInSet()`), and its legend group is listed only then;
- lists the set's legend group only while it is on;
- keeps the choice across a switch to another system and back, as the motion
  frame is kept;
- turns the set on when a search lands on one of its bodies.

`__SA3.optional(key)` and `setOptional(key, on)` are the test handles.

A set may hold **lines** as well as bodies: a scene line with `optional: key`
is shown only while its set is on (`refreshOwnedLines`), and its legend group is
listed under the set's label only while it is on. A set declared with
`menu: "features"` gets no bar button: it is a toggle row of the **Even more
features ▾** menu instead, which is hidden in a scene without such a set. A set
whose `menu` names an entry of the scene's `optionalMenus` is a row of that
dropdown ("Systems Modeled" above). No scene declares a bar button or a set with
`clouds` modes today; the viewer still supports both. The
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
  and which has no companion star on file (Kapteyn, GJ 682) has no system to open: its button is drawn dead, with a
  note in red (`info.goto_note`; "Refuted systems" above).

## Brightest Stars in the Night Sky: the same figure, another view

`hybrasil/viz/brightest_stars.py`, `hybrasil/data/brightest_loader.py`, `views.LISTED_VIEWS`.
The workbook's **100 Brightest Stars** tab (`data/brightest_stars/`) drawn the way this view
draws the Systems tab: the same frame, colours, arrows, Galaxy Motion Type button, Play and
ranges. Since 27 Nov 2026.

- **One builder, a config.** `star_motion.MotionView` holds what differs between two views
  of stars in motion: key, name, scene half-width, reference-axis length, marker size,
  double-click framing, title, extra marker meta, panel rows, "Go to system" id, extra
  traces and layout meta. `build_star_motion_figure(..., config=)` and
  `star_motion_info(..., config)` take one; the default, `NEARBY`, is this view as it
  was, and `tests/test_star_motion.py` passes unchanged.
- **Listed, not featured.** `views.LISTED_VIEWS` registers it: the web app lists it
  under Stellar Motion between Nearby Stellar Motion and the Sgr A* Cluster
  (`n_stars: 100` puts it before the cluster in the dropdown), with no featured button,
  and the CLI's file page does not hold it. `FEATURED_VIEWS` is untouched.
- **Extent.** The scene's half-width is the most distant star's distance × 1.1
  (`MARGIN`); on the 26 Nov 2026 snapshot that is Deneb (`alf Cyg`) at 2,616 ly, and the
  title says so. The axes run to 0.82 of it. The Sun is added at the origin
  (`brightest_stars.sun()`); the tab lists night-sky stars only.
- **The 100 ly sphere.** Three great circles round the Sun, one polyline, in the
  Reference legend: Nearby Stellar Motion's whole extent, for scale.
- **Size.** `apparent_size()`: `clamp(13 − 2.2·(V + 1.44), 4, 14)` px, so Sirius is 13
  and the hundredth star about 4. Each marker also carries `alt_size`,
  `luminosity_size()` of the point's luminosity: `clamp(4 + 1.7·log10(L), 3, 14)`. This
  view's own scale, because the nearby one (`marker_size`) clamps at 1,500 L☉ and more
  than thirty of the hundred pass that.
- **Ranks.** Each marker carries `tags` = its apparent, bolometric and visual ranks, as
  the tab has them. Nothing is re-ranked here.
- **Panel** (`brightest_rows()`): the standard rows, plus designation and constellation,
  the three ranks, V and M_V (with the variable's range and A_V where on file),
  variability, distance ± its uncertainty and source, the point's luminosity and the
  visual luminosity, radius, and "Also on tabs". No Planets row: the tab lists none.
- **"Go to system"** (`goto_id()`), from the tab's `Also on tabs`: the Systems-tab host
  through `system_id_for_host()` (Pollux is `bet Gem` here and opens `catalog:HD 62509`;
  `alf Cen` opens the featured Alpha Centauri), or `planetless:<host>` (Castor opens the
  featured Castor). Nine of the hundred, plus the Sun. A star no tab draws as a system
  (Sirius is on the Known tab only) gets no button.

### Three switches, all in Even more features, none of them this view's alone

The scene declares each as an optional set with `menu: "features"` and names the set in
a layout-meta entry; `figure_to_scene` carries them as `scene.altSize`, `scene.tags` and
`scene.compress`. The viewer has no view id in it.

- **Size by true luminosity** (`altSize: {set}`): while the set is on, a body with an
  `altSize` is drawn at it (`bodySize()`, `resizeMarkers()`).
- **Rank labels** (`tags: {set, prefix}`): the set has `modes`, and a features row of a
  set with modes steps through them and then off, as a bar button does. Each body gets a
  label under its marker reading `prefix + tags[mode]` (`applyTags()`). A label hidden
  for its own reasons stays hidden when its body is shown again
  (`setShown()` honours `userData.hidden`).
- **Compress distances** (`compress: {set, r0}`): every point is drawn at
  `half · log10(1 + r/r0) / log10(1 + half/r0)` from the origin, in its true direction
  (`squash()`), with `r0` = 10 ly. The scale keeps the scene's half-width where it is, so
  the camera does not move.
  - Bodies, arrows, trails and the reference lines all go through the map
    (`applyCompress()`, `setLinePts()`). A short polyline is cut into eight pieces a
    segment first (`squashPts()`), since the map bends a straight line and a star playing
    along its arrow must stay on it.
  - Lines tagged `meta.compress_only` (shells at 10 and 1,000 ly; the 100 ly sphere is
    always there) are drawn only while it is on.
  - Each body keeps its true position in `b.at`; the hover tooltip reads that, and
    double-click framing converts its `zoom_half` through the map.
  - Off again redraws every line from the points it was built from, so positions and
    geometry are exactly what they were (`tests/test_browser.py` compares them).
  - **Clouds are not mapped.** A scene with a cloud must not declare `compress`; this
    view has none.
- The three choices are optional-set state, so they survive a switch to another system
  and back like any other.

### A view's panels stay with its scene

Until 27 Nov 2026 every scene's `body_info` was merged into the page's one
`_SA_BODY_INFO`, keyed by body name. A star is `tau Cet` in this view and in its catalog
system, so "Go to system" and back left the view showing the system's entry for it. In
the web app the viewer now keeps a view's entries as `scene.info` (any index entry marked
`view`) and reads there first (`infoFor()`; `showInfoPanel(name, own)` in `band_kit.js`);
a cloud point's panel is written beside them. A file page still merges, as it holds one
view and no catalog system. `__SA3.showInfo(name)` is the test handle; calling
`SABandKit.showInfoPanel(name)` alone reads only the page's table.

## Tests

- `tests/test_brightest_view.py`: registration and index order; extent and title; sizes
  and the two scales; ranks as tags; the three switches' declarations; the sphere and the
  shells; every panel row; every `goto` id is one the web app lists; the nearby scene
  declares none of the new switches.
- `tests/test_browser.py`, "Brightest Stars in the Night Sky": picked from Stellar Motion
  with no featured button; the size and rank rows; compress on, Play to an arrow's tip,
  and off again exactly; the choice kept across a switch, with Alpha Centauri's bands flat
  in between; Aldebaran's panel right in each view and in its own system; a long panel
  scrolls inside the window.
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
    (dead for GJ 682; GJ 680 opens as its two stars), bands flat after each.
