# Star-count audit (4 Oct 2026)

Is every planet or candidate host's star count right, and is every system with a planet or
candidate on Multi-stars rather than Planetless 4+ Stars? Two read-only passes over the
Systems tab's 427 hosts, against the `hy-brasil-20261004-1158` snapshot (its Systems values are unchanged in `-2255`, which replaced it). On 6 Oct 2026,
`write_counts.py` wrote the first four systems to the sheet (`hy-brasil-20261006-1018`): psi1 Dra, HD 155555,
WD 1856+534 and GJ 896. Its log is in `write_counts_log.json`. `apply_specs.py` wrote the rest the same day, from
the researched specs in `specs/`. The format and rules are in `specs/SCHEMA.md`; the research agents' raw output is in
`specs/research/`, and `specs/finalize.py` applies the owner's choices to it. Its log is in `apply_specs_log.json`.
`audit.py` and `binaries.py` read the snapshot named in them.

| File | What |
|---|---|
| `hosts.json` | Systems-tab hosts: name, Gaia DR3 id, Stars in system, confirmed planets |
| `msc_100ly.json` | MSC (Tokovinin 2018, VizieR J/ApJS/235/6, Dec 2023): every catalog record with plx >= 30 mas and its systems (pairs) |
| `audit.py` → `audit_systems.json` | Pass 1: hosts matched to an MSC system by position (90"), stars = pairs + 1 (optical `X` pairs dropped; `?` pairs counted separately) |
| `gaia_plx28.csv` | Gaia DR3 (VizieR I/355/gaiadr3), every source with parallax > 28 mas (16,432) |
| `binaries.py` → `gaia_binaries.json` | Pass 2: co-moving companions within 1 pc by El-Badry, Rix & Heintz 2021 (MNRAS 506, 2269) cuts: parallax within 3 sigma (6 inside 4"), parallax/error > 5, delta-mu <= 0.44 plx^1.5 theta^-0.5 + 2 sigma |
| `gaia_comp_simbad.json` | SIMBAD main id, class and type for each Gaia companion |

Run from the repo root: `python data/star_counts/audit.py data/star_counts`, likewise `binaries.py`.

## Owner's decisions (4 Oct 2026)

- ~~Brown dwarfs count as stars on Multi-stars, as on Planetless 4+ Stars (role `brown dwarf`).~~ Reversed
  7 Oct 2026; see below.
- An MSC companion flagged `?` gets a row, counted, drawn hollow (`Drawing status` =
  `hypothetical and model-inferred`), as on Planetless 4+ Stars.
- AU Mic stays one star: AT Mic BC is a beta Pic moving-group co-member 78' away (MSC: "Too wide").
- Brown dwarfs already on the Planets tab (CD-35 2722 b, G 196-3 b) stay there as planets, with a
  note. (The planned pass over every >13 MJ "planet" was dropped on 7 Oct: a brown dwarf is now a planet.)
- 13 Cyg (= tet Cyg, candidate tet Cyg b) leaves Planetless 4+ Stars for Multi-stars, with 4 stars.

## Owner's decisions (6 Oct 2026), `write_counts.py`

The first four systems were re-checked in the literature before writing:

- GJ 896 stays at 2 stars, with a note. The MSC's Aa,Ab and Ba,Bb rest on Delfosse et al. 1999's spectroscopic
  flags, and Reylé et al. 2021 (VizieR J/A+A/650/A201, notes on EQ Peg A and B) call them "almost certainly due to
  activity".
- psi1 Dra goes to 4. C is the MSC's Ab (Gullikson et al. 2015 orbit). D is the MSC's suspected Bb, which keeps the
  hollow-companion rule even though it may be the outer body behind B's RV trend in Endl et al. 2016. It is named D
  because psi1 Dra Bb is Endl's planet. It is drawn hollow at an assumed orbit, 15 AU and 0.014 M_sun. Both values are
  inferred and orange: B's proper-motion anomaly and RV trend, read as one circular orbit (`write_counts.py`).
  Multi-stars marks this with Separation type `assumed`. The Unconfirmed tab's psi1 Dra B c was the same body, so it
  was removed and D kept (`merge_psi1_bc.py`; the deleted row is in `merge_psi1_bc_log.json`).
- HD 155555 joins Multi-stars as a candidate host. "Role in system" says that the planet is a candidate.

## Owner's decisions (6 Oct 2026), `apply_specs.py`

Every remaining target was re-checked in the literature (the `flags` and `sources_checked` in `specs/`):

- **tet Cyg stays on Planetless 4+ Stars.** This reverses the 4 Oct decision. Its only planet claim, tet Cyg b, is on
  Rejected candidates, so it has no live planet or candidate. Only the Systems count (2 -> 4) and its text changed.
- **APM 89 (Gaia DR3 5486916932205092352) and GJ 4113 (Gaia DR3 2052469973468984192) get no Multi-stars rows.** Each
  one's only candidate is on Rejected candidates as the binary's own orbit. A note on the Systems count says so.
- **The other candidate-only multiples were added to Multi-stars**, as HD 155555 was. That finishes the old TODO:
  CM Dra, HD 23439 A, GJ 412 A, GJ 257 A, GJ 654, GJ 548 A, CD-45 543 A, GJ 237 and HD 151613.
- **Not counted, on the evidence:**
  - Gl 49's suspected Bb: GJ 51 B's precise RVs match Gl 49's.
  - ups And's suspected Ab: planet d's astrometric signal, and 974 RVs exclude a star.
  - tau Boo C: the MSC itself places it outside the system, and nothing detects it after 2MASS.
  - GJ 338 Ab: the RVs show only the A-B trend, and the proper-motion anomaly points at B.
  - GJ 1177 Ab: the anomaly matches B.
  - HD 207496 Ab: the anomaly is B's pull plus Bb's.
- **HD 10647 goes to 3**, not 2. The Gaia companion WT 50, 37,300 AU away (WEAK), was itself resolved into Ba and Bb
  (tentative; Tokovinin et al. 2024).

## Owner's decisions (7 Oct 2026)

- **A star fuses protium, or once did; a brown dwarf is a planet.** The full rule is in
  `docs/hybrasil-instructions.md` §6. It reverses the 4 Oct rule that brown dwarfs count as stars.
- The four brown-dwarf companions on no planet tab go on Unconfirmed. Each is filed under its brown-dwarf primary
  as host: WISEP J1217+1626 A b, CWISEP J1935-1546 b, DENIS-P J0823-4912 b and CFBDSIR J1458+1013 b
  (`data/known_within_100ly/planet_scan.py` found them).
- The brown dwarfs already on Multi-stars and Planetless 4+ Stars as stars stay where they are for now. Moving
  them is an open item (below).
- The 11 Known Stellar Class cells off the class scale (white dwarfs, `~M4`) take their Systems twin's fill.
  This is rule 8 of `data/colour_scales/recolour.py`.

## Open items found on the way

- Done 7 Oct 2026: **the brown-dwarf "stars" are planets** (`migrate_bds.py`, then `fix_bd_barycentres.py`;
  `docs/hybrasil-instructions.md` section 6). Seventeen rows: eps Ind Ba, HD 3651 B, GJ 570 G, ksi UMa D, GJ 867 Bb,
  GJ 569 Bb, alf Gem Cc, pi1 Cnc Ea, GJ 9829 C and BD+37 1091 Ab to Planets; psi1 Dra D (as psi1 Dra B c, its 6 Oct
  name), tau Cyg Ab, BD+39 496 Bb and Bc and GJ 3347 Aa2 to Unconfirmed; eps Ind Bb and pi1 Cnc Eb to Exomoons, as
  the moons of Ba and Ea. Owner's choices: the Planetless 4+ Stars systems keep their stars and orbits on the tab
  (Multi-stars has no columns for the 3-D orbits) and are listed as Planetary once they have a planet; the nine
  objects at the hydrogen-burning limit and ksi UMa Bb stay stars, on the `TODO.md` watch list; the five hollow
  companions whose low mass is only `infer.py`'s assumption stay stars. Every deleted row is in
  `migrate_bds_log.json`.
- Done 7 Oct 2026, from the watch list: VHS 1256 A and B are planets (`migrate_vhs1256.py`; Dupuy et al. 2023 leave
  them undecided at 74 +/- 4 M_Jup, so section 6 files them as planets). B is on Planets round A, A fills the host
  columns, both Multi-stars rows are deleted (`migrate_vhs1256_log.json`), and Systems counts 0 stars. ksi UMa Bb is a
  star (`fix_ksi_uma_bb.py`): Fuhrmann 2008's 0.14 M_sun M dwarf at i ~ 15 deg, or Fuhrmann et al. 2016's white
  dwarf; ksi UMa B and AB's masses and offsets and ksi UMa D's period follow.

- Done 6 Oct 2026: ups And B is in the built-in ups And (`builtin_systems.py`). It is drawn hollow on a sky-plane
  circle at its 749.6 AU projected separation, standing at its Gaia DR3 position angle in 2016.0.
- Done 6 Oct 2026: VHS 1256's host luminosity, 0.0007244 (the pair's light at an old parallax), is now Dupuy et al.
  2023's 0.001042 for A (`fix_vhs1256_lum.py`). It is written to Planets col H, the master that Systems' and Multi-stars'
  formulas read, and to Known's typed copy. `apply_specs.py` had written it only into A's source text: it keeps a
  copied formula in preference to a spec value, so a `host_overrides` entry on a formula column is silently dropped.
  This was the only such override.
- Done 6 Oct 2026: GJ 1177 A's Multi-stars row has Kervella et al. 2022's 0.67 +/- 0.01 M_sun (Mann et al. 2015
  M_K relation; `fix_gj1177a_mass.py`). It was looked up, not inferred, so the border stays plain. Systems and Known keep
  TIC v8.2's 0.64 +/- 0.076, which agrees within its error.
- HD 149806 b's 12.6 MJ true mass may have absorbed B's pull, since A's proper-motion anomaly points at B.
- eps Ind A's Systems row has no Gaia DR3 id (6412595290592307840).
- Pinfield et al. 2006 list an unchecked candidate near psi1 Dra (2MASS J17420515+7208002).
- iot Hyi may belong to a young moving group (Kerr et al. 2022), which conflicts with its Systems age of 2.51 Gyr.

## False alarms, left alone

GJ 896's Aa,Ab and Ba,Bb (see above).

gam Cep Ab and tau Boo Ab are the MSC's entries for those systems' planets; Ross 458 C, G 196-3B,
VHS 1256 B and CD-35 2722 B are on the Planets tab; GJ 687 only shares a WDS field (17364+6820) and
is in none of its pairs; HD 18143 and HD 207496 stay at 3 firm stars as decided on 2 Oct. (The plan to give HD 207496
a hollow Ab was dropped on 6 Oct; see above.)
