# Google Sheets catalog source — code rules

> Moved verbatim out of `CLAUDE.md` so it loads on demand. `CLAUDE.md` links here.

## Google Sheets catalog (`--source catalog`)

Builds any host star in the catalog spreadsheet into a system on demand. Full setup and column mapping: `docs/google_sheet_catalog.md`.

The Sheets scope is `spreadsheets` (read/write), not `spreadsheets.readonly` — the API has no narrower scope that permits writing a cell. Cell *values* are the only thing wired up; formatting and Drive-level versioning are not.

**Before editing the spreadsheet itself, read `docs/hybrasil-instructions.md`.** It carries the standing rules: version naming, the three-version window, posting the new version's link in the terminal, where each kind of source must be recorded, and the pink-border convention marking Wikipedia-derived cells. Note that a new workbook version means a new Drive file ID, so the configured ID (`sheet_id.txt` in the config directory, or `$HYBRASIL_SHEET_ID`) must be updated or the loader silently keeps reading the old version.

Three rules matter when touching this code:

1. **Tabs and columns are matched by header text, never by position or tab title.** `classify_tables()` identifies a tab by the headers it contains (`Planet` + `Host system (primary star)` for planets, and so on). Renaming or reordering anything in the spreadsheet must not require a code change. Several tabs may match the planet signature — that is how the confirmed and candidate lists merge, keeping whichever row has more orbital detail.
2. **A system is drawn whole, and each planet orbits its own star.** The unit `hosts()`, `resolve_host()` and `build_star_system()` work in is the system, by its `System / Host` name. Every name in it reaches it: the primary, any member star, a nickname, or a planet. `Catalog.members()` lists its stars with the primary first. Planets still group by `Planet-host star` (`planets_by_host`), and that is what each planet's `parent` is set to. So alf Cen A draws A, B and Proxima, and Proxima's planets circle Proxima rather than A. A planet filed under the system's own name when no star has that name, such as RR Cae's circumbinary planet, goes round the primary.
3. **A companion is placed only from the stars tab's Separation columns.** `Separation from` is its parent. `Separation (AU)` is the distance. `Separation type` decides the drawing: `semi-major axis` is a solved orbit, drawn as an ellipse with the eccentricity from `Orbital eccentricity (e)` and marked confirmed. `projected` is a circle at that distance, marked hypothetical, because a sky-plane separation is a lower bound and no orbit is known. `assumed` is the same circle for a suspected companion nothing has resolved, at a model-inferred distance the sheet marks orange; the description says it is assumed, not projected. The period is Kepler's third law on both masses. A companion with no separation is never guessed into place. It is named in the description as not plotted, along with any planets of its own. Stars are placed parents first, because the mechanics add a parent's position to its child's. `_natural_span_days()` ignores star orbits, since a 30,000-year companion circle would otherwise set the animation window.

4. **A tab's data ends at its first blank or single-cell row.** `build_tables()` stops there, because the Planets tab keeps reference blocks ("CONSTANTS USED BY THIS SHEET", "SOLVENT BAND CONSTANTS") directly under its last planet with no blank row between. Read as data, the solvent table became nine "planets" of hosts named `c_inner` and `0.5575507229162847`. A real row always has at least a name and a host.
5. **Every system with a planet on file is listed and opens, orbit or not.** `hosts()` does not ask for an orbit. A system none of whose planets has a semi-major axis, a period, or a host mass to turn one into the other (`_planet_body()` returns None) is drawn as its stars and bands. Its description says so, and names the planets under "No orbit data". Before 25 Sep 2026 `hosts()` required an orbit, which hid 49 real systems (CD-35 2722, HD 48948, KOBE-1, most of the recent TOIs…) from the search and made GJ 773 B's host listed but unbuildable. `catalog_entry()` lists every planet, so a planet's name finds its system either way.
6. **A moon goes round its planet, from the exomoon tab.**
   - **Recognising the tab:** "Exomoons" (added 26 Sep 2026 as "Exomoons within 100 ly", renamed the same day when it grew past 100 ly) is recognised by the header pair `Exomoon` + `Host planet` (`MOON_SIGNATURE`). That check runs before the planet signature, because the tab also has a `Host system (primary star)` column.
   - **Indexing:** each row becomes a `MoonRecord` in `Catalog.moons_by_planet`, keyed by `match_key()` of `Host planet`.
   - **Drawing:** `build_star_system()` adds the moons after every planet, as `body_type="moon"` with `parent` set to the planet.
   - **Orbit:** `Semi-major axis (au)` and `Orbital period (d)` are measured about the planet. If one is missing, Kepler's third law on the planet's mass fills it in.
   - **Not drawn:** a moon whose planet is not drawn is not drawn either, and most rows are like that: their planets are far beyond 100 ly or free-floating, so they are records that would draw by themselves if the system were added. A moon with no usable orbit is named under "No orbit data". A moon tiered `unlikely` is never drawn and is named under "Rejected moon candidates, not drawn".
   - **Also read:** `Radius (R-earth)` / `Radius (R-Jup)` for the moon's size, and `Source / discovery reference` as the first source in its info panel.
   - **Status:** only a `confirmed` tier draws as confirmed.
   - **Not a coil:** a moon is never a coil body (`is_coil_body()` excludes it). Its closed ellipse round the planet is what makes the zoomed-in view readable.
   - **Time span:** `_natural_span_days()` is set by the moons when a system has any. CD-35 2722 b takes about 740 years round its star, so a span set by the planet would make the 171-day moon jump randomly between frames.
   - **First entry:** CD-35 2722 b I (Hoy et al. 2026, *Nature* 655, 865). Twenty-seven more followed the same day, every candidate on Wikipedia's list, each sourced from the paper Wikipedia cites; HD 189733 b I is the only one of them drawn.
7. **A rejected candidate is never drawn, from any tab.**
   - **The tab:** "Rejected candidates", added 26 Sep 2026, holds the 25 rows that were tiered `unlikely` on Unconfirmed: TFOPWG false positives and false alarms, refuted Gaia ASOIs, and RV signals that turned out to be rotation or were never recovered. Its columns A:AP are Unconfirmed's, plus `Rejected because`. It is recognised by `Planet` + `Rejected because` (`REJECTED_SIGNATURE`), checked before the planet signature because the tab also has `Host system (primary star)`.
   - **The guard is the name:** each row becomes a `RejectedRecord` in `Catalog.rejected`, keyed by `match_key()`, and `parse_workbook()` drops that name from every planet tab. A rejected candidate re-imported onto Unconfirmed from an archive therefore stays undrawn.
   - **Second guard:** a planet row tiered `unlikely` on any other tab is rejected too, for a row not yet moved.
   - **What the user sees:** a system names its rejected candidates in its description ("Rejected candidates, not drawn: tau Cet e"). A host whose only entries are rejected is not listed. `resolve_host()` says why a rejected name or such a host does not open, rather than "not in the catalog".
   - **Before this:** the rows stayed on Unconfirmed, and 22 of the 25 drew as hypothetical planets. Two of them, Gaia-ASOI-025 and -054, are SB2s whose "planet" is the binary's own orbit.
   - **To reject or reinstate:** move the whole row between the two tabs. No code change is needed.
8. **"Known within 100ly" is a reference list, never read.** Added 28 Sep 2026: every catalogued object within 100 ly (Gaia DR3 + CNS5, one row per object, 10,711 rows), with the Systems tab's columns plus `Plotted` and `Last Updated`. A plotted row is a copy of its Systems or Multi-stars row; the rest hold identity only. It carries every Systems header, so it matches `SYSTEM_SIGNATURE` too; `classify_tables()` skips it first by `KNOWN_SIGNATURE` (`System / Host` + `Plotted`), or each of its rows would become a system and a star in Nearby Stellar Motion. Source and method: `data/README.md`, `data/known_within_100ly/`.
9. **"Planetless 4+ Stars" (first named "4+ Stars only") is not read yet either.** Added 28 Sep 2026: 82 systems of four or more stars (MSC, Tokovinin 2018); 80 since 2 Oct 2026, when CD-77 1092 (= HD 207496) and GJ 118.2 (= HD 18143) turned out to be planet hosts already on Multi-stars and were taken off (`data/four_plus_stars/planet_hosts.py`), one row per star and one per subsystem (a pair whose members are pairs), with Multi-stars' columns plus 14 for the hierarchy and orbits (`Node type`, `Member of`, `Hierarchy`, period, inclination, node, argument of periastron ...). A secondary's `Separation from` can name a subsystem, i.e. a barycentre, which the mechanics cannot place yet. It matches `STAR_SIGNATURE`; `classify_tables()` skips it first by `FOUR_PLUS_SIGNATURE` (`Star (component)` + `Node type`). Drawing it means placing a body round a barycentre: `orbits.py` added `Time of periastron (JD)`, RA/Dec and `Barycentre from` / `Barycentre offset (AU)` (30 Sep 2026), and `data/hierarchy.py` turns a system's rows into bodies with massless `barycentre` bodies for its subsystems. The featured Castor is built that way from rows copied out of the tab (`_CASTOR_ROWS`; `tests/test_castor.py` checks them against the snapshot). The catalog source still does not draw the tab. Since 7 Oct 2026 it reads one thing from it, its system names (`roles["four_plus"]`): a planet-tab row filed under one of them -- a brown dwarf, which this model counts as a planet (`docs/hybrasil-instructions.md` section 6) -- goes to `Catalog.planetless_planets` for `planetless_loader`, instead of founding a second, catalog copy of the system. Planet rows on several tabs are merged by name with its case kept, so 'HD 3651 B', a brown dwarf, and 'HD 3651 b' are two planets; `match_key()`, which folds case, still does the searching and the rejection guard.

The spreadsheet has no inclination, ascending node or argument of periapsis, so catalog systems are drawn **co-planar with all three angles zero**, and mean anomaly is a stable hash of the planet name purely to keep planets from stacking at periapsis. Both facts are stated in every generated `StarSystem.description`. If orientation columns are ever added to the workbook, read them in `_planet_records()` and the disk shape disappears on its own.

**The one exception: Orbit Direction** (since 10 Oct 2026; `data/orbit_direction/README.md`). Both planet tabs carry an `Orbit Direction` column: `Prograde (assumed)` for most planets, or a measurement in the form `<Direction> (vs <reference>; <angle>)`. `PlanetRecord.measured_direction` and `.direction_angle_deg` read it; the angle falls back to the spin-orbit cell (`spin_orbit_deg`).
- **Against a binary or the other planets** (nu Oct A b, GJ 896 A b, VHS 1256 b): the planet is drawn at that inclination to the reference plane, the plane the companion is drawn in, so it goes round the other way.
  - Its star gets an assumed, dashed axis along the binary's orbit (`partner_plane`, else +z).
  - `orientation.reversed_orbit()` makes the band plane count the planet's plane but not its sense.
- **Against the star's spin** (GJ 436 b, GJ 3470 b, GJ 3090 b, GJ 523 b): the planet stays at i = 0. The star's `pole` is the band normal turned by the angle (`_spin_axes`), with `axial_tilt_deg` and `pole_note` set, and the axis is 0.8 of the planet's semi-major axis long.
- The info panel shows the planet's "Orbit direction" row and a source line.

**The Solar System arrow comes from the Systems tab's `RA (deg, ICRS)` and `Dec (deg, ICRS)` columns** (from SIMBAD, added 2026-09-24; provenance on Sources & Provenance from row 3895). They are found by header, never by letter: they were AK:AL when added and moved to AO:AP the same day, when four galactic-position and direction-of-motion columns were inserted after Space velocity. The code does not read those four. A catalog disc is drawn in the ecliptic, the frame the galactic-centre arrow and the background sky already use for a system with no frame of its own, so `orientation.toward_sun_in_ecliptic()` turns the star's RA/Dec into `solar_system_direction` and leaves `sky_frame_radec` and `galactic_center_direction` as `None`. The arrow is then right against the galactic-centre arrow and the Milky Way; only the disc's tilt against it is unknown, and the description says so. A row without both values draws no arrow, which is what a host listed only on a planet tab (the TOI candidates with no Systems row) gets.

## Snapshot pull requests (`.github/workflows/snapshot.yml`)

The hosted site is built from `data/hybrasil-*.xlsx` and never reads the sheet.
`snapshot.yml` refreshes that file, through a pull request. It runs every
Monday and can be run by hand. It calls
`python -m hybrasil.data.export_snapshot`, the same exporter
`data/README.md` gives for a hand export. The exporter opens no pull request
when every cell's value, border, fill and note is unchanged.

**It signs in without a key.** `google-github-actions/auth` exchanges the run's
GitHub OIDC token, through Workload Identity Federation, for a 10-minute
`drive.readonly` access token for `hybrasil-snapshot-ro`. (The xlsx export
URL refuses `spreadsheets.readonly` with a 401.) That service
account has three limits:

- it has no key and no project role;
- the workbook is shared with it as Viewer, and nothing else is;
- the federation provider admits only `CadeSummers/Hybrasil`'s `main`, matched
  by numeric repository and owner id, so a renamed or recreated repo does not
  inherit access, and Hybrasil-dev cannot sign in.

The read-write credential behind `google_sheets.py` stays on the maintainer's
machine and never reaches CI.

**A snapshot pull request needs its tests approved once.** It is opened by
`github-actions[bot]`, so GitHub holds its `tests` run until a maintainer
clicks **Approve workflows to run** on the pull request. Dispatching
`tests.yml` on the branch instead was tried and does not work: a dispatched
run does not satisfy the required check on a bot's pull request. From the
command line, with the run's id from the pull request's Checks tab:

```bash
gh api -X POST repos/CadeSummers/Hybrasil/actions/runs/<id>/approve
```
