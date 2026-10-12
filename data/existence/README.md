# Existence and kinematics-reference columns

Every star that Nearby Stellar Motion draws carries a link to a catalog that lists
it, plus links for its motion data. This directory built the sheet columns those
links come from (9 Oct 2026, workbook `hy-brasil-20261009-1937`).

The viewer side is described in `docs/architecture/star-motion.md`, "Sources".

| Tab | Columns added (after the tab's last) |
|---|---|
| Known within 100ly | `SIMBAD main_id`, `CNS5 id`, `Existence`, `Kinematics refs` |
| Systems within 100 ly | `SIMBAD main_id`, `Existence`, `Kinematics refs` |
| Planetless 4+ Stars | `SIMBAD main_id`, `Existence`, `Kinematics refs` (star rows only; barycentres blank) |

## Steps

| Script | What it does |
|---|---|
| `fetch.py` | Read-only. Reads the three tabs into `live.json` (not committed: it is the sheet), along with the RV and PM cells' notes. Downloads `cat/cns5.dat` (VizieR J/A+A/670/A19). Queries SIMBAD TAP once into `cat/simbad_ids.json`: every Gaia DR3 id on the tabs, plus every name (row, host, a primary's bare system name, and the MSC's `SimbadName`s). |
| `plan.py` | Decides every cell, writing `plan.json` (not committed) and a summary. Touches nothing. |
| `restore_order.py`, `newcol_borders.py` | The two follow-ups below. |
| `write.py plan` / `write.py write` | The only writer. It adds the columns with their neighbour's format, then writes in chunks of 400 rows. Each chunk's rows are re-read by name + Gaia id first, and a target cell holding anything but blank or its planned value aborts the run. It then adds the Sources & Provenance rows and renames the workbook. A re-run writes only what is missing. `write_log.json` is the record. |

### Two follow-ups the first run needed (9 Oct 2026, workbook `hy-brasil-20261009-2008`)

- **The filters.** The columns were added outside each tab's basic filter, and a
  sort through a filter moves only its own columns (`tests/test_workbook_sort.py`
  caught it on Systems). All three filters were set again over every column.
  - Setting a filter that stores a sort **re-applies that sort**.
  - On Planetless 4+ Stars this re-sorted the rows by luminosity. The sort moved values and notes, but not borders, so 1,879 provenance boxes were left on other stars' rows.
  - `restore_order.py` sorted the rows back to their order in `live.json` through a temporary helper column. Every border was then checked against the pre-edit snapshot by name: 2,967 of 2,967 were back.
  - `write.py` now refuses to widen a filter that stores a sort.
- **Copied boxes.** `add_columns` copies the left neighbour's format, orange boxes
  included. On Planetless that put 183 orange boxes in the new columns
  (Drawing status had them on 61 rows). `newcol_borders.py` restored the plain
  rule, and `write.py` now runs it after every write.

## How each value was decided

- **SIMBAD main_id.** Matched by the row's Gaia DR3 identifier, else by its exact name, else (Planetless) by the MSC's `SimbadName`.
  - The Known tab's rows with no Gaia id take the match `kinematics/simbad.py` made: a GJ name, else the nearest source within 90″ with a parallax within 25%.
  - A primary with no match by its own name (`eps Ind A`) takes its system's bare name, which SIMBAD gives the primary.
  - A match by a system name or by position is **orange** (`gs.INFERRED_BORDER`) with an `INFERRED:` note saying how it was made. There are 551 on Known, 4 on Systems and 8 on Planetless.
- **CNS5 id.** By Gaia DR3 id in CNS5's own `GaiaDR3` column. A row with no Gaia id takes the `CNS5 n` entry of `data/Nearby stars within 100 light years.xlsx` it was built from. That entry is matched by name, or, for the five rows renamed to their plotted names (`RENAMED_CNS5`), by name checked against position.
- **Existence.**
  - `confirmed: <catalogs>` where SIMBAD, CNS5, the MSC (Planetless) or the NASA Exoplanet Archive (a Systems host with a confirmed planet) lists the object.
  - `unconfirmed: only cited in Gaia DR3 (fidelity_v2 x)` where only Gaia DR3 does, with a note giving the Rybizki et al. 2022 score.
  - The Sun reads `reference: the Sun`.
- **Kinematics refs.** `RV: <refs>; PM: <refs>`, read from the RV and PM cells' own `SOURCE:` notes, else from the row's Kinematics source.
  - A catalog counts only where it is the note's source, not where the note merely mentions it ("Gaia DR3 has none").
  - Bibcodes, DOIs, arXiv ids and URLs are taken wherever they appear.

## Result

| Tab | Rows | Confirmed | Unconfirmed | SIMBAD id | CNS5 id |
|---|---|---|---|---|---|
| Known within 100ly | 10,711 (incl. the Sun) | 10,021 | **689** | 10,000 | 5,876 |
| Systems within 100 ly | 427 | 426 | 0 | 426 | -- |
| Planetless 4+ Stars | 330 star rows | 330 (MSC) | 0 | 141 | -- |

The 689 unconfirmed objects all have `fidelity_v2` < 0.05. They are anonymous
faint Gaia sources, mostly toward the bulge, that are probably not within 100 ly.
They stay on the tab, and the view draws them aquamarine (TODO.md, "Tab
membership review").
