# Workbook snapshots

A point-in-time copy of the hybrasil catalog workbook, so the repo carries the
data the project reads rather than only a Drive file ID.

**This directory is a supplementary copy, not the source.** The live Google
Sheet is the primary source for every value in this project; see
`docs/hybrasil-instructions.md` section 0. Read the sheet when the answer must
be current, never edit the xlsx to change data, and where the two disagree the
sheet wins.

| File | Workbook name when exported | Drive file ID | Exported | How |
| --- | --- | --- | --- | --- |
| `hybrasil-20261010-2036.xlsx` | `hy-brasil-20261010-2036` | private (`sheet_id.txt`) | 2026-10-10 | Google's xlsx export (`docs.google.com/spreadsheets/d/<id>/export?format=xlsx`), with the project's own credential |

The middle column is the name the workbook carried **at export time**, not its
name now. Every edit renames the live sheet to a fresh timestamp
(`docs/hybrasil-instructions.md` rule 2), so this column drifts by design and
a mismatch is not a fault. The file ID is the stable handle. A snapshot whose
`Exported` date is older than the live workbook's name is simply out of date.
That is the normal state between exports, and step 9 of the checklist is what
fixes it.

## What this is

**This snapshot is Google's own xlsx conversion of the sheet**, downloaded
from the spreadsheet's export URL with the credential `hybrasil/` already
uses. It carries:

- all 23 tabs, every cell, as **formulas with cached values**;
- the provenance borders exactly as the sheet holds them: orange `FFFF9900`
  and pink `FFFF3399`, checked after export with no palette drift;
- hover notes, fills (the luminosity colour ramp), column widths, fonts and
  merged cells.

**How to re-export** (checklist step 9). There are two routes, and they
produce the same file.

- **Automatically.** `.github/workflows/snapshot.yml` runs every Monday and
  can also be run by hand. When the sheet's content has changed, it opens a pull request
  with the new snapshot. Merging that pull request is what publishes the data,
  because hybrasil.app is built from `main`. It signs in without a key
  (`docs/architecture/catalog.md`, Snapshot pull requests).
- **By hand,** with the stored credential:

```bash
python -m hybrasil.data.export_snapshot            # "no change", or a new snapshot
python -m hybrasil.data.export_snapshot --force    # replace it regardless
```

Either way it downloads the export URL, names the file after the workbook,
deletes the previous snapshot and rewrites the table row above. It replaces
nothing when every cell's value, border, fill and note is unchanged. A rename
alone is therefore no change, and neither is the zip's own timestamp. The export URL
and the title lookup both accept a `spreadsheets` scope, so no Drive scope is
needed.

Earlier snapshots were made other ways: `hy-brasil-20260925-1342` through the
Drive connector's `files.export`, and `hy-brasil-20260920-2253` as a Sheets-API
rebuild that had values, borders and notes but no formula text or fills.

## Reading it

The catalog loader reads the live spreadsheet, not this file. That is the
intended direction, not an oversight. **One code path reads it on purpose:**
the Nearby Stellar Motion featured view (`hybrasil/data/snapshot.py`) falls
back to the newest `hybrasil-*.xlsx` here when the live sheet cannot be
reached, so that featured button opens without a Google credential. Setting
`HYBRASIL_NEARBY_SOURCE=snapshot` makes it read this file directly, and the
test suite does. That view is therefore only as current as this snapshot when
the sheet is unreachable, and it names which one it used in its title.

To read the snapshot yourself, open it with `openpyxl`, and pass
**`data_only=True`** to get values: a Drive export stores each computed cell as
a formula plus its cached value, and without the flag you get the formula text.

```python
import openpyxl
wb = openpyxl.load_workbook("data/hy-brasil-20260928-1438.xlsx", data_only=True)
ws = wb["Systems within 100 ly"]
print(ws["A1"].value, ws["J1"].value)
```

## Formatting: what this file is still good for

`google_sheets.get_borders()` reads borders straight off the live sheet, so
auditing the workbook's provenance markings (pink for a Wikipedia value,
orange for an inferred one) does not need an export at all. This file shows
those markings **as of its export date**. It is the right tool for asking what
a marking looked like before a change, not what it looks like now.

That matters more than it sounds. **Provenance borders do not survive a sort,
and this workbook re-sorts whenever a luminosity changes.** The notes travel
with their cells and the borders do not, so a snapshot's borders are only as
trustworthy as the last repair before it was taken.

**A filter's sort moves only the columns inside its range.** Multi-stars' filter
ended at AP after AQ:AT were added, so a re-sort on 3-4 Oct 2026 left the four
Separation columns behind on 105 rows. A tab that gains columns or rows needs its
filter widened in the same edit (`setBasicFilter` with the old filter and a new
range; `tests/test_workbook_sort.py` checks the snapshot). After any re-sort,
`sort_repair/repair.py` (plan, then `write`) re-homes the provenance boxes by
name; set `GOOD_REV`/`GOOD_FILE` to an export taken after the last intended
border change first.

**Matching counts are not evidence of health.** A sort permutes rows without
adding or removing anything, so an audit that checks totals will pass on a
completely scrambled column. Audit by star name.

## Keeping it current

A snapshot is stale the moment the workbook changes, and nothing detects that
automatically. `docs/hybrasil-instructions.md` is the authority on
versioning. Step 9 of its checklist is what refreshes this directory, and it
runs *after* the sheet is edited, never instead of editing it. Keep one
snapshot, named after the version it was exported from.

## `Nearby stars within 100 light years.xlsx`

Not a workbook snapshot: the object list behind the **Known within 100ly** tab,
added 28 Sep 2026. 10,711 entries, one per catalogued object within 100 ly by
inverse parallax: ESA Gaia DR3 `gaia_source` (parallax >= 32.6156 mas), plus
CNS5 entries with no selected Gaia source, plus the Sun. Its own "Method and
sources" tab gives both queries. `known_within_100ly/` holds the matcher
(`match.py`: which entry is which plotted star) and the builder (`build.py`)
that wrote the tab; Sources & Provenance carries the full method.

## `four_plus_stars/`

The builder behind the **Planetless 4+ Stars** tab (28 Sep 2026; first named "4+ Stars only"): every system of four
or more stars within 100 ly in the Multiple Star Catalog (Tokovinin 2018, ApJS
235, 6; VizieR `J/ApJS/235/6`, Dec 2023 update), plus nu Sco by request (462 ly).
`fetch_msc.py` pulls the catalogue into `msc.json` (`msc_ReadMe.txt` explains its
codes); `build.py` writes the tab. Sources & Provenance carries the model and the
14 columns it adds to Multi-stars'. `fill.py` then filled its classes and luminosities in
tiers: published values researched per component (`lit/*.json`, each with paper, identifier,
URL and a verbatim quote), else inferred from the Pecaut & Mamajek dwarf sequence
(`EEM_dwarf_UBVIJHK_colors_Teff.txt`, v2022.04.16), orange-boxed. `classes.py` then replaced
the MSC's class for the eight components a paper contradicts (the class cell's note quotes
the paper and names what the MSC had), and made the three tabs' Luminosity class formula
case-sensitive, so an old `dM1` no longer reads as a white dwarf.
`orbits.py` (30 Sep 2026) added six columns for drawing: `Time of periastron (JD)` (the MSC's T), `RA/Dec (deg,
ICRS)` and `Position source`, and on subsystem rows `Barycentre from` / `Barycentre offset (AU)`, where a pair's
centre of mass sits (orange: arithmetic). `castor.py` then completed Castor from the literature (`lit/castor.json`)
for the featured system, corrected its AB-C period (the MSC's is ten times too long) and added `Argument of
periastron refers to`, filled for Castor only.
`research.py` (30 Sep 2026) checked every other system's orbits against three catalogs that postdate or are
independent of the MSC, cached in `cat/` by `fetch_catalogs.py`: ORB6 (`orb6orbits.txt`, 2026-07-09), SB9
(`sb9.tar.gz`, 2024-06-21) and Gaia DR3 non-single-star solutions (`gaia_nss*.json`). An ORB6 orbit replaces the
tab's only at grade 1-5, when newer or when the tab had only an MSC period estimate, and only if Kepler's third law
holds against the tab's masses; SB9 fills e/omega/T only from the paper the tab's orbit came from; Gaia gives
inclination and node for measured orbits that lacked them (orange: Thiele-Innes arithmetic). Two owner decisions
are recorded on Sources & Provenance and in each cell's note: **photocentre orbits** (ksi UMa Aa-Ab, chi Cet Aa-Ab,
HR 2158 Aa-Ab, CD-52 2036 Aa-Ab), whose published 'a' is the light-centre's wobble, carry a from Kepler's third law
(orange, old value in the note), and **GJ 319 A-B and zet1 Cnc AB-C**, whose published a and P cannot both hold,
keep a and take P from Kepler (orange, WEAK). `Argument of periastron refers to` is now filled for every pair with
an omega. `companions.py` then added two single-lined companions the MSC does not list, GJ 187.2 Ab (SB9, Abt 1965)
and GJ 3347 Aa2 (Gaia DR3 SB1), as hypothetical stars with minimum masses from the mass function; both are doubtful
and say why in their notes. Their `Drawing status`, a new last column, reads `hypothetical and model-inferred`;
blank means drawn as confirmed.
`infer.py` (30 Sep 2026) then filled everything nothing measures, all orange and WEAK, by the owner's rules: a wide
pair is a circle in the plane of the sky (a = its projected separation, P from Kepler) phased to the MSC's position
angle at J2016.0; a spectroscopic orbit without a tilt gets i = 60 (90 if eclipsing) and a node from the name hash;
a suspected companion gets 0.3 x its primary's mass (capped at 0.5 M_sun) at 3 AU (astrometric) or 0.3 AU
(spectroscopic) and is `hypothetical and model-inferred`. Every pair on the tab now has a complete orbit, and
`hybrasil/data/planetless_loader.py` draws all of them.
