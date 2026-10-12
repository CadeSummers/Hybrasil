# The Galactic Center: Sgr A* and the S-stars

The web app lists one system here, `galactic:sgr-a`, as **Sgr A\* Cluster (Galactic Center)** (`sgr_a_loader.NAME`): the
S-stars on their Keplerian orbits round Sagittarius A*, the Milky Way's supermassive black hole. It sits under the
**Stellar Motion** System Type, after Nearby Stellar Motion (`kind: "motion"`); until 10 Oct 2026 it had a Galactic
Center type of its own. The id keeps its `galactic:` prefix so links to it still work.

- **Built by:** `data/sgr_a/` (9 Oct 2026), which wrote the workbook's **Sgr A\* S-stars** tab; `add.py` appended nine rows on 10 Oct 2026.
- **Read by:** `hybrasil/data/sgr_a_loader.py`.

## The tab

**Rows:** 57.
- **Sgr A\*:** one row, its `Object type` reading `Supermassive black hole`. A hover note flags it as neither a star nor a planet, and as the mass every other row orbits.
- **Gillessen et al. 2017:** the 40 stars with orbits (ApJ 837, 30; VizieR J/ApJ/837/30 table 3).
  - GRAVITY 2022's newer fits replace four of them: S2, S29, S38 and S55 (A&A 657, L12, Table B.1).
- **Disputed:** seven stars: S62 and S4711–S4716 (Peißker et al. 2020a, 2020b, 2022).
  - Their `Status` reads `disputed`. Its note gives both sides: GRAVITY 2021 and 2022, and GRAVITY+ 2026 (Nature 657, 359), which do not see them, and Peißker's replies.
- **Added 10 Oct 2026** (`data/sgr_a/research/D.json`, written by `data/sgr_a/add.py`):
  - **S301:** GRAVITY+ 2026 (Nature 657, 359, Extended Data Table 2), the shortest known period (8.68 yr) and the smallest pericentre (11.5 AU). With no radial velocity yet, the paper gives two near-mirror orientations; the tab and the viewer use the first, and the Ascending node cell's note holds the second.
  - **S5, R1, R14, R30, R70, S72:** young stars of von Fellenberg et al. 2022 (ApJ 932, L6, Table 4), out to 6″. SIMBAD splits R70 and S72 from the names the paper equates them with; the SIMBAD main_id note says so.
  - **G1, G2:** `Object type` `Dusty object`. Gillessen et al. 2026 (A&A 707, A79, Table B.1) fit their orbits with a drag force. Three groups agree on the orbits, not on whether they are gas clouds or dust-enshrouded stars.
  - **Left out on purpose:** R39 and R85 (errors as large as the values), S64 (one group, whose same table gets S29 wrong), D9 and the other single-group dusty sources, and S300, S63 and others with detections but no orbit. `D.json` holds them all (`new_stars`, `no_orbit`).

**Column groups:**
- Identity.
- Class, mass and Teff, with their source.
- The orbit: a in arcsec and in AU, e, i, Ω, ω, tP, P and pericentre, with its source.
- Motion at the epoch 2026.77.
- A measured RV.
- Sgr A*'s own position and distance.
- Existence and Refs.

`HEADERS` in the loader is the single list; `data/sgr_a/build.py` writes it.

**Sheet names:**
- The tab name holds a `*`, which an xlsx sheet name cannot. Google's export, and therefore the `data/` snapshot, calls it `Sgr A S-stars`.
- `parse_sgr_a` accepts both spellings (`XLSX_TAB`).

**What is inferred (orange, each cell with its note; `data/sgr_a/plan.py`):**
- **a in AU:** a″ × the orbit paper's own R0. Gillessen used 8320 pc and GRAVITY 8277 pc. Peißker's milliparsecs are converted at 206.265 AU/mpc.
- **Pericentre:** a(1 − e).
- **GRAVITY's periods:** √(a³/M), with the fit's own R0 and M. G1 and G2's periods the same way, from Gillessen 2026's M and R0.
- **von Fellenberg's a in AU:** the paper states no R0, so GRAVITY 2022's 8277 pc. Its periods agree with √(a³/M) at that distance.
- **S301's mass:** 1.3 M☉, the middle of the paper's 1.1–1.5 M☉.
- **Every motion column:** from the orbit, by Kepler's equation, at the epoch.
- **Class, mass and Teff for a star no paper has typed** (`data/sgr_a/infer.py`):
  - **Early-type star:** treated as a main-sequence dwarf. M_K = K − A_K − DM, with A_K = 2.42 (Fritz 2011) and R0 = 8277 pc, read off Pecaut & Mamajek's dwarf sequence.
    - Against Habibi 2017's 7 published masses it runs **+0.06 dex high, 0.075 dex rms**.
    - It only covers stars no brighter than O9 V. Brighter stars are left blank: they are giants or supergiants of the young disk.
  - **Late-type star:** a K–M giant at a nominal 1.5 M☉ (0.8–3), marked **WEAK**.

## The frame: the papers' ascending node recedes

The orbits are on the plane of the sky like every astrometric orbit here: x is North, y is East and z points toward Earth (`frames.md`).

**The difference is the node.** The Galactic Centre papers fix it by the radial velocity: their ascending node is where the star moves **away** from us.
- With z toward Earth, the standard rotation puts the ascending node where the star *approaches*.
- Taken as published, every orbit therefore comes out mirrored through the sky plane. The sky positions are right, but every radial velocity has the wrong sign.

**The fix:** `sky_elements` turns Ω and ω by 180° each.
- This leaves the Thiele–Innes constants A, B, F and G alone, so nothing moves on the sky.
- It flips C and H, which is exactly z → −z.

**The test** (`tests/test_sgr_a.py`) uses Gillessen 2017's own S2 data (table 5, committed in `data/sgr_a/cat/`):
- the median offset from the 145 measured positions is 1–2 mas;
- each of the 44 radial velocities has the right sign and lies within 150 km/s.

**Other astrometric systems.** The built-in astrometric systems (Alpha Centauri, Castor) take Ω as published. Visual-binary orbits leave the node ambiguous unless a radial velocity fixes it, so whether they need the same turn has not been checked here.

## What is drawn

**Sgr A\*:**
- It is a `star` body at the origin with `luminosity_sun=None`.
- That gives it no solvent band and no photosynthesis ring.
- Its marker is near-black with the star's white rim.

**The S-stars:**
- Every S-star is a `star` with `parent="Sgr A*"`. None is given a luminosity either, so none grows a band stack.
- Early-type stars are blue-white and late-type stars orange. A star Gillessen 2017 does not group is coloured by its class's first letter (O, B, W blue-white; G, K, M orange; A, F, as S301, near-white).
- A dusty object (G1, G2) is drawn solid and brown, labelled "(dusty object)": its orbit is not in dispute, only its nature.
- A disputed star is `status="hypothetical"` with the note "Disputed", so it is drawn hollow with a dashed orbit.

**S111** is unbound (e = 1.09). `kepler.py` solves only ellipses, so S111 is on the tab but not drawn, and the system description says so.

**Arrows:**
- **No galactic-centre arrow.** `StarSystem.at_galactic_center` drops it: the system *is* the galactic centre. The Solar System arrow (`TOWARD_EARTH`, 26,996 ly) stays.
- The Milky Way behind is rotated by Sgr A*'s own RA/Dec (`sky_frame_radec`).

**Info panel:**
- `OrbitalBody.info_rows` replaces the mass/period/velocity/tilt rows with the tab's own: class, mass, Teff, K, the orbit, the motion at the epoch and the measured RV. `build_body_info` passes them as `rows`, the way the Nearby Stellar Motion view does.
- The Sources list gives SIMBAD and an ADS link for each kind of value (Orbit, Class, Mass, Teff, RV, Disputed by).

**Span:** 20 years (`SPAN_YR`), so S2 (16.0 yr), S55 (12.8 yr) and S38 (19.2 yr) each go round once. The planetless rule, 1.2 × the shortest period, would stop at S55's 15 years.

## Tests

`tests/test_sgr_a.py` covers:
- the frame, against Gillessen's data;
- parsing, the system and the panel, from literal rows;
- the tab, from the snapshot:
  - all 56 objects are there;
  - S301 and the six von Fellenberg orbits are on the tab as published, and G1 and G2 are dusty and solid;
  - the 36 Gillessen orbits not refit by GRAVITY match table 3 exactly;
  - S2 is GRAVITY's fit;
  - 55 orbits are drawn and S111 is left out;
  - the catalog does not read the tab as a star system.

Other tests:
- `tests/test_web_app.py`: the index entry, and that the scene builds.
- `tests/test_browser.py::test_app_galactic_center_opens_the_s_stars_round_sgr_a`: the dropdown type, a hollow disputed star, S2's panel with its class and Sources, G2's "Nature disputed" and S301's panel.
