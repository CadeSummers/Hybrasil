# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Standing rules

### A solvent band is always depicted as a flat disc — verify it in the viewer

A solvent band is a region of orbital distances drawn as a flat annulus around
its star. **Any change that touches how a band is built, placed, styled,
clipped, recomputed, or carried across a system switch must be verified to
still draw flat discs before it is called done.**

```bash
pytest tests/test_band_flatness.py tests/test_system_switch.py
pytest tests/test_browser.py        # Playwright: both renderers, in Chromium
```

**Verifying means opening the figure and looking at it.** The suite checks the
figure Python builds; it cannot see what WebGL draws, and the one real failure
of this rule so far was invisible to Python entirely — the geometry was exactly
planar the whole time. Open it, switch systems, switch a band on from **both**
the Bands button and its own legend entry, and move the pressure slider:

```bash
python -m hybrasil.cli --system solar                    # three.js (default)
python -m hybrasil.cli --system solar --renderer plotly  # then click through to Alpha Centauri
```

Alpha Centauri is the system to look at: three stars, three band stacks, and
the largest trace count after the Solar System.

`tests/test_browser.py` automates that click-through in headless Chromium
for every system and **both renderers** (three.js, the default, and `--renderer plotly`):
arrive from another system, Bands button, a band's own legend entry, the
pressure slider (Plotly only -- three.js has no sliders yet), then every band
must still be a planar mesh. It is what the
Python suite cannot be, but it reads what the page holds, not the pixels -- a
Playwright `page.screenshot()` you then look at is the cheap way to do the
looking when no browser window is to hand.

**Check the multi-system figure, not a single-system one.** `--output html`
writes one system and exercises none of the switching; the bug below could not
happen there, and testing there is how it was missed twice.

#### The failure this rule exists for

Nineteen of Alpha Centauri's twenty-four bands rendered as **tori made of
beads** rather than flat discs. The cause was not geometry, lighting, or
anything about the bands:

- A frame carries the trace **indices** it writes to, and an index means
  something different in every system. Solar's frames write single-point
  markers to traces 18–46; Alpha Centauri's bands are traces 13–36.
- Swapping figures on the same graph div let the old system's frame data reach
  the new system's traces, retyping a `mesh3d` band as `scatter3d`. Plotly then
  drew its 360 vertices as fat markers — two rings of beads, at the inner and
  outer radius.
- The damage was exactly the index overlap, which is why it looked like one
  solvent was plotted differently from another. Formamide is trace 17 and
  Sulfuric acid is trace 18, so coming from the Solar System one was a flat
  disc and the next one along was a torus. Nothing about the two bands
  differed — same function, same style, same everything but colour and radius.

The switcher therefore plots into a **fresh div** every time. `Plotly.react` on
the same div was the original bug; `newPlot` on the same div and `Plotly.purge`
were both tried and both still corrupted the same nineteen traces.

Two things that must stay true, each a bug if dropped:

1. **`addControls` holds its graph div in one rebindable closure variable**,
   and `_saReattach` repoints it. A fresh div is useless if the Bands button
   and the sliders keep acting on the old one — they silently stop working
   after a single system switch.
2. **`tests/test_system_switch.py` pins that the hazard is real**, not just
   that the fix is present. A test that the indices never collide would pass
   for the wrong reason the day the trace order changes.

#### What a band's geometry must satisfy

`verify_band_is_a_flat_disc()` in `tests/test_band_flatness.py` is the single
expression of the geometric half: planar to 1e-9 AU along its own normal,
sitting at its stacking offset, spanning exactly `[r_inner_au, r_outer_au]`
about `centre_body`'s position, every face wound the same way, and the trace
still a `mesh3d` rather than a point cloud. Being planar is necessary and not
sufficient — the torus bug passed every geometric check in that file.

## Commands

```bash
# Install dependencies (requirements.txt alone to run, without the tests)
pip install -r requirements-dev.txt

# Run the visualizer (opens in browser)
python -m hybrasil.cli --system solar
python -m hybrasil.cli --system trappist-1
python -m hybrasil.cli --source file --system schemas/custom_system.yaml.example

# Static snapshot instead of animation
python -m hybrasil.cli --system solar --mode static

# Filter to specific bodies
python -m hybrasil.cli --system solar --bodies "Earth,Mars,Jupiter"

# Custom time range
python -m hybrasil.cli --system solar --time-start 2024-01-01 --time-end 2026-01-01 --frames 200

# Export to HTML or PNG
python -m hybrasil.cli --system solar --output html --out-file solar.html
python -m hybrasil.cli --system solar --mode static --output png --out-file solar.png  # requires kaleido

# Live data from NASA Horizons (requires: pip install astroquery astropy)
python -m hybrasil.cli --source horizons --system solar

# Google Sheets star catalog (requires: pip install google-api-python-client google-auth)
python -m hybrasil.cli --list-catalog
python -m hybrasil.cli --source catalog --system TRAPPIST-1
python -m hybrasil.cli --source catalog --system "Proxima Cen b" --refresh-catalog
python -m hybrasil.cli --source catalog --system "tau Cet" --offline

# Solvent bands (default: all eight at 1 bar, built hidden)
python -m hybrasil.cli --system solar --solvent water   # one band in the legend
python -m hybrasil.cli --list-solvents
python -m hybrasil.cli --system solar --solvent all
python -m hybrasil.cli --system solar --solvent methane,ethane
python -m hybrasil.cli --system solar --solvent carbon-dioxide --pressure 50
python -m hybrasil.cli --system solar --pressure 2.5 --albedo 0.12  # where the sliders start
python -m hybrasil.cli --system solar --greenhouse 0    # greenhouse (beta) slider; default 33 K, Earth's
python -m hybrasil.cli --system proxima-centauri --star-colour off  # drop the Kopparapu star-colour factor
python -m hybrasil.cli --system solar --solvent sulfur --band-limit thermodynamic
python -m hybrasil.cli --system trappist-1 --band-plane reference  # lay bands flat on z = 0

# The default viewer is three.js; the original Plotly viewer is one flag away.
# --output png always renders through Plotly.
python -m hybrasil.cli --system solar --renderer plotly

# Web app: three.js viewer, Featured systems + More Modeled Systems (every catalog
# system, searchable with typo-tolerant autocomplete, built on demand)
python -m hybrasil.cli --serve                     # http://127.0.0.1:8765/
python -m hybrasil.cli --serve --source catalog --system "tau Cet"
python -m hybrasil.cli --serve --port 0 --no-open  # any free port, no browser

# The static site for hosting: every system pre-built into site/ (~2 min, ~420 MB)
HYBRASIL_DATA_SOURCE=snapshot python -m hybrasil.cli --build-site site

# Every workbook loader reads the live sheet, else the data/ snapshot; force the snapshot:
HYBRASIL_DATA_SOURCE=snapshot python -m hybrasil.cli --system solar

# Suggest Changes submissions, for review (never written to the workbook)
python -m hybrasil.cli --export-suggestions review.csv --suggestions-from local   # what --serve recorded
python -m hybrasil.cli --export-suggestions review.csv   # the hosted D1 database; needs CLOUDFLARE_* env

# Run tests
pytest
pytest -m "not browser"                      # skip the ~3 min Playwright tests
pytest tests/test_browser.py --headed        # watch the browser tests run
# Playwright's browser, once after pip install:  python -m playwright install chromium

# Run a single test file
pytest tests/test_kepler.py

# Run a single test
pytest tests/test_kepler.py::TestEarthPosition::test_earth_at_j2000_distance -v
```

## Architecture

The application is split into four layers that never bleed into each other:

### Data flow
```
Data sources  →  models.KeplerianElements  →  mechanics (math)  →  viz (Plotly)
```

Every data source (built-in, custom YAML, NASA Horizons) converts to `KeplerianElements` before anything else. The mechanics layer only knows about elements; the viz layer only knows about positions.

### Layer breakdown

**`hybrasil/models/`** — Pure dataclasses, no logic.
- `KeplerianElements`: the universal interface between data and mechanics. All angles in degrees, distances in AU, time in Julian Date / days.
- `OrbitalBody`: a single body. Stars have `elements=None` (they sit at origin). Moons have `parent` pointing to their planet. `luminosity_sun` is set on host stars and is what a solvent band is computed from.
- `StarSystem`: a collection of bodies with helper methods (`get_planets()`, `get_moons_of()`, `filter_bodies()`).
- `BeltZone`: a flat annulus, no mechanics. `extends_scene` decides whether the scene must be wide enough to show it — false for decorative belts, true for solvent bands. `is_solvent_band` marks a band that was *derived* rather than observed: those start hidden and move as one group under the viewer's Bands button. `normal` is the plane it lies in — `(0, 0, 1)` for every belt, its own star's orbital plane for a solvent band — and `offset_au` displaces it along that normal, 0 for everything but a stack of solvent bands. `centre_body` is the star the ring is around, by *name* rather than by position: a star that is itself in orbit has no position until a time is chosen, and the data layer has none, so the figure builders resolve it from the positions they already hold at `t_start`. `star_label` is that star as the legend spells it, set only where a figure holds more than one band-bearing star.

**`hybrasil/mechanics/`** — Pure math, no I/O.
- `kepler.py`: Kepler's equation solver (Halley's method), eccentric→true anomaly, orbital plane → reference frame (three Euler rotations). `elements_to_cartesian()` is the full pipeline entry point.
- `time_series.py`: `generate_orbit_path()` samples the ellipse evenly in *eccentric anomaly* (not time), `ORBIT_POINTS` = 720 — a closed curve whose worst chord error is a circle's, so a body's marker stays within half a pixel of its drawn orbit at the double-click zoom, aphelion included (`tests/test_orbit_path.py`; 360 points in true anomaly left Eris visibly off it). `system_time_series()` samples by *time* for animation frames. `generate_coil_orbit_path()` samples by time as well, adding the parent's position at each step, and is what draws a planet whose star is itself in orbit. `system_orbit_paths()` returns `(orbit_paths, coil_paths)` — every body with elements lands in exactly one of the two, except a bookkeeping barycentre (`draw_orbit=False`), which lands in neither. A parent's position counts the whole chain above it (`ancestor_chain()`).
- `units.py`: Julian Date conversions, `derive_period_days()` via Kepler's third law, and `T_EQ_1AU_K`, the 278.33 K blackbody reference every solvent band scales from.
- `orientation.py`: the plane a system's bodies orbit in, as a unit normal, plus the 2-D basis that spans it. See `docs/architecture/solvent-bands.md`.
- `solvent_bands.py`: where a solvent is liquid around a star, as a ring of orbital distances. See `docs/architecture/solvent-bands.md`.
- `photosynthesis.py`: how far from a star its PAR photon flux falls to a photosynthetic threshold, `sqrt(L × k(Teff) / f)`, k being the blackbody PAR photon yield per watt over the Sun's. See `docs/architecture/photosynthesis.md`.

**`hybrasil/data/`** — Data sources, all converge to `StarSystem`.
- `loader.py`: `get_system(source, identifier)` dispatches to the right loader. This is the single call the CLI uses.
- `sgr_a_loader.py`: the Sgr A* S-stars tab (Sgr A*, the 40 Gillessen 2017 orbits, GRAVITY's refits of S2/S29/S38/S55, seven disputed Peisker stars drawn hollow, and since 10 Oct 2026 S301, six von Fellenberg 2022 stars and the dusty objects G1/G2) as one `StarSystem` round the black hole, live sheet else snapshot; listed by the web app as `galactic:sgr-a`, "Sgr A* Cluster (Galactic Center)", under the Stellar Motion type after Nearby Stellar Motion. The papers' ascending node is the receding one, so it turns Omega and omega by 180 deg for this code's z-toward-Earth sky frame (`sky_elements`). See `docs/architecture/galactic-centre.md`.
- `planetless_loader.py`: every other system on the Planetless 4+ Stars tab (79 of them) as a `StarSystem`, through `hierarchy.py`, read from the live sheet or the snapshot (the tests' `HYBRASIL_DATA_SOURCE=snapshot` applies). Every pair on the tab has a complete orbit: measured (`data/four_plus_stars/research.py`: MSC, ORB6, SB9, Gaia DR3) or model-inferred and orange (`infer.py`). A row whose `Drawing status` reads `hypothetical and model-inferred` is drawn hollow (`status="hypothetical"`, `status_note`). A brown dwarf is a planet (`docs/hybrasil-instructions.md` §6), so a hierarchy's brown dwarfs are planet-tab rows filed under its `System / Host`, each drawn round the node its `Planet-host star` names -- a star, or a subsystem's barycentre -- with its Exomoons moons; `catalog_loader` keeps them in `Catalog.planetless_planets`, out of its own systems, and `hierarchy.py` takes a top subsystem with no outer pair as the root barycentre. Listed by the web app as `planetless:<host>`, `kind: "planetless"` -- or `"planetary"` once it has a planet, as eleven have; Castor's row folds into the featured Castor via `FEATURED_CATALOG_HOSTS`.
- `hierarchy.py`: a hierarchical multiple star, as the Planetless 4+ Stars tab writes it (`NodeRow`s), turned into bodies. A subsystem becomes a massless `barycentre` body; everything hangs off one star at the origin by exact two-body geometry. Castor is built with it.
- `builtin_systems.py`: Seven hardcoded systems, no network or file I/O needed — the Solar System (J2000 elements, 8 planets + major moons + Pluto + Eris), TRAPPIST-1 (Agol et al. 2021), Alpha Centauri and Proxima Centauri (Pourbaix 2002, Kervella 2017 and the Proxima planet papers), Upsilon Andromedae, 55 Cancri and Castor. Castor is every number a cell of the workbook's Planetless 4+ Stars tab (`_CASTOR_ROWS`, checked against the snapshot by `tests/test_castor.py`), and its brown dwarf Cc a planet whose numbers are its Planets row (`_CASTOR_CC`): change the sheet, then the rows. Upsilon Andromedae is assembled from two sources on purpose: the star is the catalog workbook's, so the solvent bands match what `--source catalog` computes and need no Google credential, while the orbits are configuration PRO1 of Deitrick et al. 2015 — the catalog has no angle columns, and a co-planar drawing of the one system with a measured mutual inclination would leave out the only thing it is famous for.
- `custom_loader.py`: Parses user YAML/JSON files. Period is optional if parent has `mass_kg`.
- `horizons_loader.py`: Fetches live osculating elements from NASA JPL Horizons. Requires `astroquery` + `astropy`.
- `google_sheets.py`: I/O half of the catalog source — credentials, tab fetch, 24-hour disk cache. Knows nothing about columns. It holds the only write path into the workbook: `read_cells()` and `update_cells()`, the latter taking an `expect` mapping that is read back and compared before anything is written. Always pass `expect` — rows shift, and it is what stops an edit landing on the wrong star. A write invalidates the disk cache, which would otherwise serve pre-write values until the TTL expires.
- `catalog_loader.py`: Parsing half — turns raw tab values into `StarSystem`, one whole system per `System / Host`: every star, companions placed by the multi-stars tab's Separation columns, each planet around its own star, each exomoon (the Exomoons tab) around its own planet. Orbits are co-planar except where the planet tabs' `Orbit Direction` column (10 Oct 2026, `data/orbit_direction/`) says a planet is retrograde against its binary (drawn at that inclination, its star's axis assumed and dashed) or polar/retrograde against its star's spin (the star's axis tilted by the angle). A name on the Rejected candidates tab, or a row tiered `unlikely`, is never drawn from any tab. No network, so every rule is testable from literal rows.

**`hybrasil/viz/`** — Plotly figure construction.
- `themes.py`: All visual constants (colors, sizes, dark background style). `make_scene_style(x_half, y_half, z_half)` returns a `SCENE_STYLE` copy with explicit symmetric axis ranges baked in — required for correct camera centering.
- `static_plot.py`: Snapshot figure. Each body gets two traces: an orbit ellipse line + a marker. A coil body gets a `_coil_trace()` in place of the ellipse, styled identically so the two read as the same kind of object.
- `animation.py`: Animated figure. Critical structure: orbit-line traces come first (indices 0..N-1), marker traces follow (indices N..2N-1). Animation frames **only update marker traces** by index. This prevents orbit lines from flickering every frame. Coil traces are appended *after* the marker and axis block, so adding one can never shift a marker index.
- `export.py`: `show_in_browser()`, `save_html(cdn=True)`, `save_png()` (png requires kaleido). `save_png()` switches the solvent bands back on first, because a still image has no Bands button to switch them on with. All HTML output injects `_ZOOM_JS` via Plotly's `post_script` — a custom double-click-to-zoom handler, AU-native scroll zoom, and a fixed "Orient" button. The double-click handler uses `plotly_click` event timing (not the native `dblclick`) and delays the camera update by 100 ms so it fires *after* Plotly's own double-click camera reset. The Orient button calls `viewFromAbove()`, which restores the original full-system scene ranges and sets the camera eye at 100 AU above the origin. The Back button calls `restoreScene()`, popping `_sceneStack` to undo the last double-click or search zoom; scroll zoom rewrites the scene in place and pushes nothing, so the stack holds only deliberate jumps. The search box runs two passes: `searchTrace()` matches single-point traces, which are body markers, and only if that finds nothing does `searchTraceGroup()` match everything else by name — belts, solvent bands, orbit lines. The second pass returns every trace in its best-matching tier, not the first, because a solvent band is three rings sharing a name prefix; `traceGroupTarget()` then frames their combined bounding box and passes the extent to `zoomTo()` as `halfOverride`, since a band has no `_SA_BODY_INFO` entry to take one from. Marker-first ordering is what keeps "Jupiter" finding the planet rather than its orbit line, which is drawn earlier in the trace list.
- `three_viewer.py` / `three_viewer.js`: the default viewer (`--renderer plotly` for the original). `figure_to_scene()` converts the *Plotly figure* into a three.js scene rather than building one a second time, so both renderers draw identical orbit samples, coils and band meshes. A logarithmic depth buffer replaces Plotly's axis box, so a zoom is a camera move and nothing is re-uploaded. The band sliders, search ranking and info panel come from `band_kit.js`, shared with the Plotly viewer. Behind every system it draws the Milky Way (`viz/sky/`, NASA Deep Star Maps 2020), rotated into the system's frame by `orientation.galactic_to_frame()` so the galactic-centre arrow points at the galactic centre in the picture; a system that sets `galactic_center_direction` must set `sky_frame_radec` too. See `docs/architecture/frames.md`.

### Deep dives — read the one you need before touching that area

These sections used to live here and were moved out verbatim so they load on
demand instead of every turn. The rules in them are just as binding.

| File | Read before touching |
|---|---|
| `docs/architecture/solvent-bands.md` | Band physics, `solvent_bands.py`, pressure/albedo interpolation, the greenhouse offset, star colour (Kopparapu factor), stacking, `orientation.py` / which plane a band lies in |
| `docs/architecture/viewer-bands.md` | The Bands button, band legend clicks, `_showBands()`, the pressure/albedo sliders and readouts, `_recomputeBands()`, the JS copy of the band equation |
| `docs/architecture/zoom-and-visibility.md` | `updateSceneVisibility()` / clipping, `compute_scene_extent()`, camera centering, double-click and scroll zoom, Orient, `_saReattach()` |
| `docs/architecture/frames.md` | Sky-plane vs ecliptic frames, the Solar System and galactic-centre reference arrows, the background Milky Way |
| `docs/architecture/coils.md` | `is_coil_body()`, `generate_coil_orbit_path()`, playback starting paused |
| `docs/architecture/catalog.md` | `catalog_loader.py`, `google_sheets.py`, `--source catalog` |
| `docs/architecture/three-renderer.md` | `three_viewer.py` / `three_viewer.js`, the default renderer, the depth-range limits |
| `docs/architecture/web-app.md` | `--serve`, `web/app.py`, the featured buttons and the More Modeled Systems dropdown (System Type row), `system_search.js`, `FEATURED_CATALOG_HOSTS` |
| `docs/architecture/photosynthesis.md` | The Photosynthesis limits tab, `mechanics/photosynthesis.py` (the PAR photon factor), `data/photosynthesis_limits.py`, `viz/photosynthesis_rings.py`, the Even more features menu and its reference orbits (`viz/reference_orbits.py`) |
| `docs/architecture/galactic-centre.md` | The Sgr A* S-stars tab, `data/sgr_a_loader.py`, `data/sgr_a/`, the Sgr A* Cluster's place under Stellar Motion, the receding-node frame flip, `at_galactic_center` |
| `docs/architecture/suggestions.md` | Suggest Changes: the form, `web/suggestions.py`, `web/suggestion_rules.json` / `suggest_validate.js` (one set of rules for the form, `--serve` and the Cloudflare function), `functions/api/suggestions.js`, the D1 table, `--export-suggestions`. A suggestion is a record for review and never writes to the workbook |
| `docs/architecture/star-motion.md` | The Nearby Stellar Motion view, `views.py` / `FEATURED_VIEWS`, `viz/star_motion.py`, `data/nearby_loader.py`, `data/snapshot.py`, grouped legend rows, owned lines, `scene.units`, `info.rows` |

Rules that stay here because they are easy to break without opening a deep dive:

- **The band is per star and scales as `sqrt(L)`.** Any code path that hardcodes an AU figure for a band is wrong.
- **Star colour is a per-star factor on absorbed flux**, from `mechanics/stellar_colour.py` (Kopparapu 2013 runaway ratio, 1 for the Sun). Python computes it and ships it in `meta.colour`; the fit must never be copied into the JavaScript.
- **The equation exists twice**, in `mechanics/solvent_bands.py` and in `viz/band_kit.js` -- one JS copy, spliced into the Plotly viewer's `_ZOOM_JS` and exported to the three.js viewer as `window.SABandKit`. Change the Python, change the kit; `tests/test_band_sliders.py::TestTheTwoImplementationsAgree` is what catches drift, and `TestOneCopyForBothViewers` what stops a second JS copy appearing.
- **Kepler's equation exists twice too**, in `mechanics/kepler.py` and as `keplerXYZ()` in `viz/three_viewer.js`. The viewer uses it to keep a body on its orbit between frames; `tests/test_kepler_js.py` catches drift. See `docs/architecture/three-renderer.md`, rule 0.
- **Every path that rewrites the scene must call `updateSceneVisibility()`**, and clipping always starts from the cached original geometry, never from `gd.data`.
- **The live Google Sheet is the primary source; `data/*.xlsx` is a supplementary local copy.** Read the sheet when the answer must be current, never edit the xlsx to change data, and where the two disagree the sheet wins. The xlsx shows formatting *as of its export date*; for formatting as it is **now**, use `gs.get_borders()`, which reads the live sheet — `read_cells()` speaks the values API and cannot see borders or fills.
- **Every edit to the sheet renames it** to `hybrasil-{YYYYMMDD}-{HHMM}` via `gs.rename_workbook(None, gs.versioned_title())` — a rename keeps the file ID. A single cell counts.
- **A value that was inferred rather than looked up gets an orange border** (`FFFF9900`, `gs.set_border(..., gs.INFERRED_BORDER)`), the way a Wikipedia-copied value gets a pink one (`FFFF3399`). Fitted relations and arithmetic on published inputs both count; the Sources & Provenance entry must carry the method, its scatter and its valid range.
- **A row number is not an identifier.** Provenance records key on the star name; `ROW`/`CELL` columns drift on a sort and have already been wrong once. Re-sorting a sheet that carries provenance borders means re-checking them afterwards by name, and unmarking a cell means restoring `gs.PLAIN_RULE`, not clearing the border.
- **A star fuses protium, or once did (white dwarfs count); a brown dwarf is a planet**, whatever its mass. It goes
  on a planet tab, never Multi-stars or Rejected for being over 13 M_Jup. See `docs/hybrasil-instructions.md` §6.
- **Every source file starts with an SPDX header**: `SPDX-FileCopyrightText: 2026 Cade Summers`
  and `SPDX-License-Identifier: AGPL-3.0-or-later`, as comments, after any shebang. A new
  file without one fails `tests/test_discovery.py`. Code is AGPL wherever it lives, `data/`
  scripts included; the data itself is CC BY-SA 4.0 (`NOTICE`).
- **Before editing the spreadsheet itself, read `docs/hybrasil-instructions.md`**, and `CLAUDE.local.md` where it exists: the maintainer's private Drive workflow lives there, outside the repository.

**`hybrasil/views.py`** — Featured *views*: featured buttons that are not one star system. `FEATURED_VIEWS` holds Nearby Stellar Motion (every Systems-tab star in galactic light years, with velocity arrows), placed after the built-ins in the three.js viewer and the web app only. It is not in `BUILTIN_NAMES`, on purpose: it has no orbits, bands or Plotly twin. See `docs/architecture/star-motion.md`.

**`hybrasil/figures.py`** — `build_figure(system, t_start, t_end, ...)` and the natural time spans: the one step from a system to its figure, shared by the CLI and the web app so the two cannot draw a system differently. `cli.py` re-exports `_NATURAL_SPANS` / `_natural_span_days` for older callers.

**`hybrasil/web/app.py`** — The web app behind `--serve`: `SystemLibrary` (the index of featured + catalog systems, and a scene cache built on demand) and a standard-library HTTP server with `/`, `/api/systems` and `/api/systems/<id>`. A catalog system a featured system covers is folded into it via `FEATURED_CATALOG_HOSTS` / `FEATURED_ALIASES` in `builtin_systems.py`, so every system is listed once. The More Modeled Systems dropdown opens on a System Type row -- Planetary, High Star Count (Planetless), Stellar Motion -- filtering on each index entry's `kind` (`views.system_kind()`, `FEATURED_KINDS`); Planetary lists every catalog system, most planets first, then nearest, twelve rows tall and scrolling for the rest (`SASystemSearch.shelf()`, `VISIBLE_ROWS` in `three_viewer.js`). A featured system's button and dropdown label is `FEATURED_LABELS.get(key, system.name)` (none differs since Castor's brown dwarf became a planet, 7 Oct 2026). `web/static_site.py` writes the same app as static files for hosting (`--build-site`): each index entry carries the `url` of its scene file, and every URL is relative. The About panel's content (author, citation, licences, credits, DOIs and support handles once they exist) is `hybrasil/about.json`, edited there and never in the JavaScript. `web/discovery.py` builds the page's JSON-LD and `/llms.txt` from the same file; `AGENTS.md` is its hand-written twin for coding agents. See `docs/architecture/web-app.md`.

**`hybrasil/cli.py`** — Thin wiring layer. `build_parser()` holds every option, split out of `main()` so a default can be asserted on without running a command. `main()` parses args, calls `get_system()` → `system_time_series()` / `system_positions_at()` → `build_animated_figure()` / `build_static_figure()` → export. **Every browser launch opens with every featured system in the switcher** (`_with_featured()`), whatever the source; a catalog, file or Horizons system is added after them and opens first, and a catalog system a featured one covers opens as the featured one (`_featured_twin()`). `tests/test_featured_baseline.py` pins this.

### Custom system files

`schemas/custom_system.yaml.example` is the documented schema. Bodies must be listed in dependency order (moons after their parent planet). The `period` field is optional in `orbital_elements` if the parent body has `mass_kg`.

### Adding a new built-in system

1. Add a `_mysystem(bands: SolventChoice = DEFAULT_CHOICE)` function in
   `builtin_systems.py`, following `_solar_system()`. It must pass its bodies
   and host name to `bands.zones()` and `bands.note()`, or the system gets no
   solvent band and no band orientation.
2. Register it in `_BUILDERS` — once per spelling a user might type, each
   mapping to `(canonical_key, builder)` — and add the canonical key to
   `BUILTIN_NAMES`, which sets the switcher button order.
3. Add `FEATURED_CATALOG_HOSTS` and `FEATURED_ALIASES` entries: the catalog
   systems (by `System / Host` name) the new system covers and the names
   people know it by. Without them
   the web app's More Modeled Systems search lists its catalog twin as a second system.
   A system with no planets needs a `FEATURED_KINDS` entry (`"planetless"`), or
   the dropdown lists it under Planetary.
4. Add a `_NATURAL_SPANS` entry in `figures.py` if the default 365.25 days does not
   show meaningful motion. The rule of thumb is a little over the outermost
   period: TRAPPIST-1 needs 30 days, Upsilon Andromedae 1540.

Where figures come from the catalog workbook rather than from papers, take them
as they are, including any internal disagreement, and say so in the description
rather than rescaling to make them agree — Upsilon Andromedae's orbits imply a
1.32 M_sun star where the workbook's stellar row says 1.27, and both are left
alone because nothing drawn depends on the difference. Where the workbook gives
no phase at all, use the same `catalog_loader._phase_deg` name hash the catalog
source uses, so both routes to the same star draw it the same way.

**Orbital angles are worth going to the literature for.** The workbook has no
inclination, node or argument of periapsis, so a system built from it alone is
drawn flat. That is honest for a system with no measured angles, and wrong for
one that has them. Upsilon Andromedae is the worked example: its angles come
from a paper, its star from the workbook, and the two are checked against each
other by putting sin i back into the dynamical masses to recover the workbook's
Msini (`tests/test_upsilon_andromedae.py`). See `docs/architecture/frames.md`: angles
from astrometry or transits are measured against the plane of the sky, and both
reference arrows have to follow.
