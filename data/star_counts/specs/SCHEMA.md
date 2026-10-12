# Star-count spec format (one JSON file per research batch)

You are researching systems for the hybrasil workbook's star-count audit. You DO NOT write to the
Google Sheet. You produce a JSON file, a list of system specs, that a writer script will apply.
Repo: `<repo>`. The current sheet snapshot (read it with
openpyxl, `data_only=True`) is `data/hy-brasil-20261006-1120.xlsx`. Use it to see the existing rows of
every tab. The live sheet is identical to it as of now.

## Read first

- `docs/hybrasil-instructions.md`: sections 3, 4 and 5, on sourcing, Wikipedia pink and inferred orange.
- `data/star_counts/README.md`: the audit, the owner's decisions and the false alarms.
- `data/star_counts/write_counts.py`: the worked example of the four systems already written, with the
  exact wording style for Star data source, notes, orange cells and provenance.
- On the snapshot, the Multi-stars rows of `psi1 Dra A` and `HD 155555`, the precedent rows.

## Evidence already gathered

`data/star_counts/audit_systems.json` (the MSC pairs per host), `msc_100ly.json` (the MSC records),
`gaia_binaries.json` and `gaia_comp_simbad.json` (Gaia DR3 co-moving companions, with SIMBAD names).
A plain-text dump of all of it is `scratchpad/evidence.txt`, next to this file.

## Rules, from the owner and the workbook

1. **Check each companion in the literature before adding it.** Two traps have already been hit:
   - GJ 896: the MSC's spectroscopic companions were activity artefacts (Reylé et al. 2021). Look for a
     refutation of every spectroscopic, astrometric or `?` companion.
   - psi1 Dra: a "companion" that was already on the Unconfirmed tab as a candidate planet.
   Search the Planets, Unconfirmed, Rejected candidates, Exomoons and Planetless 4+ Stars tabs for every
   companion, by name and by what it physically is, before you count it. If the MSC's companion is
   a planet already on Planets or Unconfirmed, it is NOT a new star: say so in `flags` and do not add a row.
2. SUPERSEDED 7 Oct 2026: brown dwarfs are planets, not stars (`docs/hybrasil-instructions.md` §6).
   This rule read: "Brown dwarfs count as stars on Multi-stars (role mentions 'brown dwarf')." The rows it added
   were migrated to the planet tabs on 7 Oct 2026 (`migrate_bds.py`). Brown dwarfs already on the Planets tab
   (CD-35 2722 b, G 196-3 b) stay there.
3. An MSC companion flagged `?` gets a row, counted, and drawn hollow. Being drawn needs a separation.
   Derive one from measured signals where they exist, as psi1 Dra D was derived: its proper-motion anomaly
   plus its RV trend, read as one circular orbit. Failing that, use the typical-companion rule of
   `data/four_plus_stars/infer.py`: mass 0.3 × the primary's, capped at 0.5 M_sun; a = 3 AU for an
   astrometric wobble, 0.3 AU for a spectroscopic hint; circular. Do not use it if the data exclude it
   (e.g. RV precision that would have seen it). Then say so and leave the separation blank. Either way it is
   inferred: Separation type `assumed`, orange, with a note whose first line starts `WEAK:`.
4. **Orange (inferred) cells**: anything computed rather than looked up. That includes a projected
   separation from Gaia positions × parallax, a luminosity from R and Teff, a mass from a relation, and
   Kepler's-third-law arithmetic. Every orange cell needs a note giving the inputs, method and scatter.
   Published values are not orange. Unit conversions of a published value are not orange.
5. **No Wikipedia values.** Use primary sources (papers, VizieR: Gaia DR3 `I/355/gaiadr3`, MSC
   `J/ApJS/235/6`, SB9 `B/sb9`, Gaia DR3 FLAME in `I/355/paramp`). Wikipedia may be used only to find the
   primary citation, never as the source of a value.
6. Luminosity: if no published component luminosity exists, either compute it from a published R and Teff
   (orange) or leave it blank. Do NOT use an M_abs→L dwarf relation on a white dwarf, giant or pre-main-
   sequence star.
7. Names: keep names the sheet already uses. New components get the literature's name. Never reuse a
   planet's spelling: "X Bb" collides with planet "X B b".
8. Separation type is one of `semi-major axis` (solved orbit, drawn solid), `projected` (sky-plane,
   drawn hollow; orange if you computed it), or `assumed` (rule 3, orange, WEAK).
9. Class (sort key): O 0, B 10, A 20, F 30, G 40, K 50, M 60, plus the subtype. Leave it blank if there is
   no class. L/T/Y brown dwarfs and white dwarfs: blank, like existing rows.
10. Gaia DR3 source_id is always a STRING.

## Multi-stars columns you may fill (exact header text)

System / Host, Star (component), Role in system, Nickname (IAU), Distance (ly), Stars in system,
Confirmed planets, Mass (M-sun), Stellar Class, Class (sort key), Effective temp (K), Star data source,
Age (Gyr), Metallicity [Fe/H], Luminosity (L-sun), Planet masses (M-earth), Mass type,
Radial velocity (km/s), Proper motion in RA, μα·cos δ (mas/yr), Proper motion in Dec, μδ (mas/yr),
Total proper motion, μ (arcsec/yr), Space velocity (km/s), Kinematics source, Gaia DR3 source_id,
Planet-host star, Planet-host class, Primary mass (M-sun), Orbital eccentricity (e), Orbit described,
Orbit source, Separation from, Separation (AU), Separation type, Separation source

The writer fills these itself, so leave them out: the system-level columns (Distance, Stars in system,
Confirmed planets, Planet masses, Mass type, Planet-host star, Planet-host class, Primary mass,
System / Host), which it copies from the Systems tab. A HOST row, when the system is new to Multi-stars,
is built from the Systems tab too. Give a host row only if a value must differ from Systems (e.g. the
Systems mass is a combined pair mass).

## JSON shape

```json
[
 {
  "system": "<exact 'System / Host' as on the Systems tab>",
  "action": "new_system" | "add_rows" | "count_only" | "no_change" | "move_from_planetless",
  "old_count": 1,
  "new_count": 3,
  "host_overrides": {"<header>": value},
  "rows": [
    {"after": "<existing or earlier-listed component this row goes under>",
     "values": {"Star (component)": "...", "Role in system": "...", "...": "..."},
     "orange": {"<header>": "<cell note; first line 'WEAK: ...' if it rests on an assumption>"},
     "notes":  {"<header>": "<plain hover note on a non-orange cell, optional>"}}
  ],
  "systems_text": "<the full new 'System stars' text for the Systems tab, one 'Name: class (role)' per line>",
  "stars_note": "<note for the 'Stars in system' cells: what changed and why, with citations, ending 'Was N.'>",
  "sp_paragraph": "<one Sources & Provenance paragraph: inputs, sources, method/scatter/valid range for every orange value>",
  "flags": ["<anything the owner must hear: a refuted companion, a duplicate, a judgement call>"],
  "sources_checked": ["<citation or VizieR table, one per item>"]
 }
]
```

`action` meanings:
- `new_system`: the system has no Multi-stars rows. The writer builds the host row from Systems; you give
  the companion rows.
- `add_rows`: the system is already on Multi-stars and gains rows.
- `count_only`: the rows exist, and only the count is wrong.
- `no_change`: the audit's target proved wrong (like GJ 896). Explain why in stars_note and flags.
- `move_from_planetless`: (tet Cyg only) translate its Planetless 4+ Stars rows into Multi-stars rows.
  Carry every value, and turn its orange cells into `orange` entries with the same notes. Also list the
  Planetless rows to delete by component name in a top-level key `"planetless_components"`.

When finished, print a short summary: per system, old → new count, and every flag.
