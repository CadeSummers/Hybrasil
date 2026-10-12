# Working rules for the hybrasil workbook

Standing instructions for anyone, human or agent, who edits the catalog
spreadsheet. Read this before changing a cell. They are also the method behind
every value in the published dataset: where a number may come from, how it is
sourced, and how a reader can tell a looked-up value from a copied or inferred
one.

The workbook is private; the maintainer's Drive workflow (version files,
backups, reporting each edit) is kept outside the repository. It is the source
behind `--source catalog`; see `docs/google_sheet_catalog.md` for how the code
reads it.

---

## 0. The live Google Sheet is the source of truth

The workbook on Drive is the **primary source**. Every value this project
reports about a star comes from it, `--source catalog` reads it directly, and
an edit is not made until it is made *there*.

`data/*.xlsx` is a **supplementary local copy** — a point-in-time export kept
so the repo carries its own data and so a reviewer can diff a change without a
Google credential. It is downstream of the sheet in every sense:

- **Read the sheet, not the snapshot, whenever the answer must be current.**
  `google_sheets.get_workbook()` is the right call. Reach for the xlsx only for
  what the Sheets values API cannot give you — cell formatting, borders, fills
  — or when you deliberately want the state as of that export.
- **Never edit the xlsx to change the data.** It is regenerated from the sheet,
  so an edit there is discarded at the next export and, until then, is a second
  disagreeing copy. Fix the sheet and re-export.
- **A snapshot is stale the moment the sheet changes**, and nothing detects
  that. Step 5 of the checklist below is what keeps it honest.
- **Where the two disagree, the sheet wins** — including when the xlsx looks
  more complete. Say so plainly rather than reconciling them silently.

---

## 1. Version naming

Every new version of the workbook is named:

```
hybrasil-{YYYYMMDD}-{HHMM}
```

Local time, 24-hour clock, zero-padded, no seconds, so `hybrasil-20261011-1549`
is a version made on 11 October 2026 at 15:49. Never overwrite a timestamp; a
new edit session means a new name.

Versions before 11 October 2026 were named `hy-brasil-{YYYYMMDD}-{HHMM}`, with
a hyphen, when the project was StarAnalysis. Those names stay as they were in
the logs, the Sources & Provenance tab and the TODO history: they are what the
file was called at the time.

## 2. Versions and renames

**Every edit renames the workbook** to a fresh rule-1 timestamp, local time,
down to a single cell, so the name always says when the file last changed:

```python
from hybrasil.data import google_sheets as gs
gs.rename_workbook(None, gs.versioned_title())
```

A rename keeps the Drive file ID, so nothing needs re-pointing. Cutting a
separate version file, and the backups kept beside it, is the maintainer's
Drive workflow and is not part of this document. A new version file has a new
ID, so the configured sheet ID (`sheet_id.txt` or `$HYBRASIL_SHEET_ID`) has to
follow it, and `--refresh-catalog` has to run once so the cache stops serving
the old one.
## 3. Sourcing anything added from outside

If a value comes from an external source, the source gets recorded in the same
edit. Two destinations, by subject matter:

**Stars, planets and systems** go in the **Sources & Provenance** sheet. Its
`WHERE EACH COLUMN CAME FROM` table has four columns:

| COLUMN | SOURCE | CONFIDENCE | HOW TO VERIFY IT |
| --- | --- | --- | --- |

Add a row for a new column, or amend the existing row when a column's contents
change origin. `HOW TO VERIFY IT` is meant to be actionable: name the query,
the catalogue, or the paper table a reader can re-run or open. Follow the
existing tone, which is blunt about weak data. Rows in that sheet already say
things like `RECALLED FROM MEMORY by Claude. Not queried.` with confidence
`LOW`. Preserve that honesty rather than smoothing it over.

**Solvent and chemistry values** go in the solvent sources table, which is
keyed by ID:

| ID | Source | Type | Used For | Reference / Link | Confidence Notes |
| --- | --- | --- | --- | --- | --- |

Take the next unused `S` number. `Used For` should name the specific constants
or claims the source backs, the way `S3` names the exact Antoine parameters it
supplied, not just the substance.

## 4. Wikipedia is marked, twice

Wikipedia is an aggregator, not a primary source. The workbook already treats
it that way and the rule is unchanged: it is the fastest route to a Gaia DR3 or
CARMENES number, but the citation underneath is the thing that counts.

When a cell's value is read off Wikipedia, do both of the following.

**Mark the cell.** A medium pink border, colour `FFFF3399`, on all four sides.
The colour carries the meaning, not the presence of a border: thin grey rules
and one dark-teal box already exist in the file and mean nothing of the kind.
The border is independent of the cell fill, so a pink-bordered cell keeps its
luminosity ramp colour. The convention applies to every column, not only
luminosity.

**Log it.** Append a row to the `VALUES WRITTEN FROM WIKIPEDIA` table in the
Wikipedia sources sheet:

| SHEET | ROW | CELL | STAR / FIELD | VALUE | WIKIPEDIA PAGE | WIKIPEDIA URL | SOURCE WIKIPEDIA CITES | SOURCE URL | CROSS-CHECK PERFORMED | DATE ADDED |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Both links are required. `SOURCE WIKIPEDIA CITES` names the paper or catalogue
Wikipedia gives as its reference for that specific number, with enough detail
to find the value inside it, down to the table where the existing rows can
manage it. A pink border is an instruction to a reader to check that second
link before relying on the cell, which only works if the second link is there.

**That table is keyed by `STAR / FIELD`, not by its `ROW` and `CELL` columns.**
A row number is a position, not an identifier, and a sort changes it silently.
This has already gone wrong once: the Multi-stars sheet was re-sorted after the
first Wikipedia pass, the three pink borders stayed on the row numbers instead
of travelling with the values, and the convention ended up reading backwards —
two blank cells and one Gaia FLAME value wearing the badge, and all three real
Wikipedia values wearing none. Where `ROW`/`CELL` disagree with the star name,
the star name is right.

**Re-sorting a sheet that carries provenance borders means re-checking them
afterwards**, by star name, with `get_borders()`.

### Luminosity needs a cross-check before it is written

Star infoboxes sometimes quote a **visual** luminosity, which for a cool dwarf
can be several times smaller than the bolometric one. Every formula in this
workbook takes the square root of luminosity, so a visual value shrinks every
derived orbital radius without ever looking obviously wrong.

Recompute the luminosity from the radius and effective temperature printed in
the same infobox. Write the value only if the two agree, and record the check
in `CROSS-CHECK PERFORMED`. If it fails, do not write it, and add a row to
`CANDIDATES FOUND ON WIKIPEDIA BUT DELIBERATELY NOT WRITTEN` saying why. The
rejection of GJ 15 B is the worked example: the infobox radius and temperature
gave a bolometric luminosity four times the quoted figure, which is the
signature of a visual value.

## 5. Inferred values are marked orange

Wikipedia is not the only kind of number that needs a reader to stop and look
twice. A value **calculated rather than looked up** — a relation fitted during
a session, arithmetic over published inputs, anything that has not been through
peer review — is marked with a **medium orange box, colour `FFFF9900`, on all
four sides**, and the Sources & Provenance entry must say how it was derived
well enough that someone can reproduce it or throw it out.

The two markings answer different questions and both are workbook-wide:

| Colour | Hex | What it means |
| --- | --- | --- |
| Pink | `FFFF3399` | Copied from Wikipedia. Check the citation underneath. |
| Orange | `FFFF9900` | Inferred, not peer reviewed. Check the method. |

As with pink, the **colour carries the meaning, not the border** — grey rules
and a dark-teal box already exist and mean nothing of the kind — and the border
is independent of the fill, so a marked cell keeps its luminosity-ramp colour.
A cell could in principle need both markings; none does today.

What the provenance entry has to contain, at minimum: the inputs and their
sources, the method, its residual scatter, and the range over which it is
valid. The worked example is the `M_abs`-to-`L_bol` relation behind 16 Cyg C
and GJ 3021 B, written up under **PASS 10** on the Sources & Provenance sheet —
it names the 1829-star training set, the 0.048 dex scatter, the valid magnitude
range, and a nine-point validation against stars whose luminosity *is*
published. Anything less than that is not a provenance record, it is a note.

**An inferred cell also carries a hover note.** The border says a value was
inferred; it cannot say *how*, or how much to trust it, and a reader who meets
the cell will not go hunting through Sources & Provenance to find out. Put the
method in a line or two on the cell itself — which band or input was used,
which was dropped and why, and the word **WEAK** in the first line where the
value rests on an assumption nothing measures.

Notes have a property the borders lack: **they travel with the cell when a
sheet is sorted.** That is exactly what stranded the three pink borders on the
wrong rows, so a note is the more robust carrier of the two.

```python
from hybrasil.data import google_sheets as gs
gs.set_border(None, ["'Multi-stars within 100 ly'!P2"], gs.INFERRED_BORDER)
gs.set_note(None, {"'Multi-stars within 100 ly'!P2": "INFERRED from a single band..."})
```

Reading one back:

```python
b = gs.get_borders(None, "'Multi-stars within 100 ly'!P1:P90")
[k for k, v in b.items() if any(c == "FF3399" for c, _ in v.values())]
# ['P72', 'P85', 'P88']
```

The *values* API returns values and nothing else, which is why `read_cells()`
cannot see a marking. `get_borders()` goes through
`spreadsheets.get(includeGridData=True)` instead, which can — so auditing a
marking needs neither an xlsx export nor a Google Docs session.

**Unmarking a cell means restoring the plain rule, not removing the border.**
Unmarked cells in these data columns wear a thin rule like their neighbours, so
`clear_border()` leaves a visible hole. Use `set_border(..., gs.PLAIN_RULE,
style="SOLID")`.

The same LibreOffice palette-snap trap that moved `FFFF3399` to `FFFA6A6D`
applies here. Anyone who recalculates this file must check both colours and
patch `xl/styles.xml` back if either has drifted.

### An inferred method is only valid over the population it was fitted to

The `M_abs`→`L_bol` relation behind most of the orange cells is fitted to
K5 V–L8 **dwarfs**. Applied to anything else it returns a plausible-looking
number that is simply wrong: on the DA white dwarf HD 140901 B it reads 2.2×
high, and 0.0037 L☉ is an unremarkable M-dwarf luminosity, so nothing about
the answer looks off.

**Check what the object is before applying a relation to it.** A white dwarf
needs `Teff`, `log g` and the mass–radius relation instead; Gentile Fusillo et
al. 2021 (VizieR `J/MNRAS/508/3877`) carries all three. Record the valid
population alongside the method, and say in the cell note which one was used.

## 6. What counts as a star, and what counts as a planet

The owner set this boundary on 7 October 2026. It decides which tab an object
goes on, and it is not the IAU's 13 M_Jup line.

- **A star fuses ordinary hydrogen** (protium, proton-only), **or once did.**
  Main-sequence stars, giants and white dwarfs are all stars. A white dwarf no
  longer fuses anything, but it fused hydrogen in the past.
- **A brown dwarf is not a star.** Fusing deuterium alone, now or in the past,
  does not make an object a star. This model treats a brown dwarf as a very
  large planet. It goes on a planet tab: Planets when it is confirmed,
  Unconfirmed otherwise.
- **A brown dwarf's own companion is filed under the brown dwarf.** The primary
  fills the host columns and is not added as a star. Its row's note says the
  host is a planet under this rule. Such a pair has no star: the host
  luminosity is the brown dwarf's own, so the HZ and solvent-band columns come
  out tiny or empty.
- **Mass alone does not decide it.** The hydrogen-burning limit is about
  0.075 M_sun (about 78 M_Jup). An object near it counts as a star only if a
  source says it sustains hydrogen fusion. Where the literature calls it a
  brown dwarf, or leaves it undecided, file it as a planet and say so in the
  note.

This reverses the 4 October 2026 decision that brown dwarfs count as stars on
Multi-stars and Planetless 4+ Stars (`data/star_counts/README.md`). The brown
dwarfs that were star rows there were migrated the same day
(`data/star_counts/migrate_bds.py`; the deleted rows are in its log):

- **A brown dwarf in a Planetless 4+ Stars hierarchy** becomes a planet-tab
  row filed under the system's `System / Host`. Its `Planet-host star` names
  the node it orbits: a star, or a subsystem when it orbits a pair (its host
  luminosity is then the pair's summed, orange). The stars and their measured
  orbits stay on the tab, because Multi-stars has no columns for them. A
  subsystem left with one member is collapsed into that member, which takes
  the subsystem's orbit cells and its place in the tree; the subsystems above
  have their masses and barycentre offsets re-derived without the brown dwarf
  (`fix_bd_barycentres.py`), since the drawing gives a planet no pull.
- **A brown dwarf that orbits another brown dwarf** is that planet's moon, on
  Exomoons (eps Ind Bb round eps Ind Ba, pi1 Cnc Eb round pi1 Cnc Ea).
- **A planet-tab name differs from the planets' by case alone where the
  literature's does**: `HD 3651 B` is the brown dwarf, `HD 3651 b` the planet.
- **Not migrated**: objects at the hydrogen-burning limit, and ksi UMa Bb
  (class `WD?`), stay stars on a watch list in `TODO.md` until each is
  reviewed by the rule above. Two are settled: VHS 1256 A and B are planets
  (`migrate_vhs1256.py`, the system has no star), and ksi UMa Bb is a star,
  an M dwarf or a white dwarf (`fix_ksi_uma_bb.py`). Four more were settled
  on 9 Oct 2026 by a literature check (`settle_watch_list.py`):
  - GJ 310.1 Bb (HD 72946 B) is a planet;
  - GJ 275.2 Ab is rejected as probably spurious;
  - HR 1099 Bb and GJ 747.2 Bb stay stars.

  A hollow companion
  whose low mass is only the typical-companion rule's assumption
  (`data/four_plus_stars/infer.py`) is not a brown dwarf on that evidence, and
  stays a star.

---

## Checklist for a workbook edit

Steps 1 to 4 run on **every** edit, down to a single cell. Step 5 runs when a
new version is cut.

1. Make the changes, in the sheet. Guard every write with `expect`.
2. Record every external source in Sources & Provenance or the solvent sources
   table, and every inferred value's full method.
3. Pink-border any Wikipedia-derived cell and log it with both links.
   Orange-border any inferred cell.
4. Rename the workbook to `hybrasil-{YYYYMMDD}-{HHMM}` for the time of the
   edit: `gs.rename_workbook(None, gs.versioned_title())`.
5. Re-export into `data/` and update that directory's README, so the
   supplementary local copy matches the sheet it was taken from. The export
   follows the sheet; it never leads it. Nothing detects a stale one.
## What the code can and cannot do here

The integration requested read-only access until 10 September 2026. It now asks
for `https://www.googleapis.com/auth/spreadsheets`, which is read and write,
because the Sheets API has no narrower scope that permits writing a cell. So
`hybrasil/` can now change values in the workbook, and every rule above
governs those writes exactly as it governs a human edit.

Two functions in `google_sheets.py` do the work. `read_cells()` reads specific
A1 ranges without pulling the whole workbook. `update_cells()` writes them, and
takes an `expect` mapping of the current values: each one is read back and
compared first, and a single mismatch aborts the whole write. Always pass
`expect`. Rows shift as the catalog grows, and it is what stops an edit landing
on the wrong star. Writes default to `RAW`, so a value is stored literally
rather than reinterpreted as a formula or a date.

Borders are wired up too, as of pass 10: `set_border()` and `clear_border()`
take A1 ranges and a colour, with `WIKIPEDIA_BORDER` and `INFERRED_BORDER` as
named constants so the meaning travels with the call. `rename_workbook()` and
`versioned_title()` cover the rename in rule 2.

Borders can be read back too, with `get_borders()`. The *values* API returns
values only, which is what `read_cells()` speaks; `get_borders()` uses
`spreadsheets.get(includeGridData=True)`, which carries formatting. So an audit
of a provenance marking needs no export.

One thing the code still cannot do: create a version file or rename a backup,
because copying is a Drive operation, not a Sheets one.

Appending to a sheet has one trap worth stating outright: **never use
`values().append()`**. It anchors on the table its range names rather than on
the last row of the sheet, and on Sources & Provenance it will insert at row 3
and shift the whole sheet down, silently invalidating every absolute line
reference in the workbook. Grow the grid with `appendDimension`, then write by
explicit A1 range through `update_cells()` with an `expect` mapping. This is
recorded as a real incident under PASS 10 on that sheet.
