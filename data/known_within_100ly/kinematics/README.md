# Known within 100ly: motion columns

This pipeline fills the nine motion columns of the `Known within 100ly` tab for every object:
radial velocity, both proper motions, total proper motion, space velocity, galactic l/b, and motion
toward l/b. The goal is for Nearby Stellar Motion to draw all of them, as purple "unclassified" dots,
with an arrow wherever a space velocity exists. The plan was agreed 2026-10-08 and lives at
`~/.claude/plans/i-want-to-do-gleaming-stallman.md`.

**Where are we?** Run `python status.py` in this directory. It prints each phase's state and the next
command to run. `LEDGER.md` is the human-readable view of the research batches.

## Phases

| Phase | Script | What it does |
|---|---|---|
| P0 | `targets.py` | Freezes the live tab into `targets.json`: name, Gaia id, RA/Dec, distance, and current values. Rows are keyed by name + Gaia id, never by row number. |
| P1 | `gaia.py` | Fetches Gaia DR3 `gaia_source` by source_id into `cat/gaia_NNN.json`. It resumes per chunk. |
| P2 | `simbad.py` | Fetches SIMBAD's adopted RV and PM: by Gaia identifier, or by GJ name and then position for the CNS5 rows with no Gaia id. |
| P3 | `merge.py`, `write.py bulk` | Writes the bulk fill. Only blank cells are written, and they get grey/orange/pink marks and notes, a Sources & Provenance block, and a rename. |
| P4 | `merge.py --batch`, agents, `write.py wave` | Literature research on the rows still missing RV or PM: 33 batches of 100 in `batches/`, capped at 30. |
| -- | `write.py renote` | Re-notes cells already written when `merge.py` gains a flag: notes and `Kinematics source` only, never a value. |
| -- | `identity.py` | One-off fixes to rows the research found misnamed or misplaced (2026-10-09). Renamed rows keep their pipeline key through `common.RENAMED`. |
| P5 | (code in `hybrasil/`) | The purple layer in Nearby Stellar Motion. |

Results so far:
- **P3** (2026-10-08, workbook `hy-brasil-20261008-1430`) filled:
  - PM on 10,206 rows;
  - RV on 7,005 rows: 6,283 from Gaia DR3 and the rest from SIMBAD;
  - space velocity and motion direction on about 7,015 rows;
  - l/b on 10,288 rows.
- **After P3:** 3,297 rows have no RV, and 64 of them have no PM either.
- **P4** (2026-10-08, 30 batches, K001–K030, four waves plus one withdrawal; last write `hy-brasil-20261008-1707`):
  - 438 RVs and 20 PMs found in the literature.
  - Values held back, listed in `merge.REJECT` with the reason for each, plus the `RV_ERR_REJECT` cut:
    - values where independent measurements disagree by about 15 km/s or more;
    - a value contaminated by its primary;
    - a value from an unpublished paper;
    - any RV with an error over 20 km/s.
  - Still missing after P4: 2,881 rows have no RV, and 44 have no PM.
  - Not launched: K031–K033, the faintest (the user said not now, 2026-10-09).
  - Open notes for the user: `LEDGER.md`, "For the user's judgement"; what was decided is under "Decided by the user".
- **Owner decisions of 2026-10-09** (workbook `hy-brasil-20261009-0929`):
  - **Blended RVs accepted**, as the bulk pass accepts Gaia's combined-light ones: `merge.BLENDED`, 28 rows, each pair
    closer than ~2.5" with members within 2.5 mag in G. The note says NOT THIS COMPONENT'S OWN, and it is a WEAK flag.
    What was not taken is listed with its reason above the table. NLTT 33370 AB's two rows also take its systemic RV and
    barycentric PM.
  - **DESI DR1 and Hsu 2026 RVs flagged WEAK** (`merge.RV_SYSTEMATICS`), values as published.
  - **Doubtful membership flagged, not removed:** Gaia DR3 `fidelity_v2` < 0.5 (Rybizki et al. 2022; `cat/fidelity.json`)
    on 761 rows, none plotted, mostly anonymous G 19–20.5 sources toward the bulge. The flag is in `Kinematics source`
    (shown in the viewer), the motion notes and a note on Distance.
  - **Misnamed rows** (`identity.py`): GJ 4378/4379 letters swapped to WDS's; the unplotted GJ 257 A renamed B, as
    Multi-stars already has it; GJ 10808 split into A/B; GJ 10108 B moved to 54 Psc B's position. GJ 11905 A / 11906 B
    (CNS5's two components of one binary), GJ 3879 B and GJ 12804 B were right and got CHECKED notes.
- **P5:** done. The snapshot `data/hy-brasil-20261009-0929.xlsx` carries the filled columns, so the purple layer
  works offline too.

## Running the research (P4)

- **Concurrency:** at most 6 agents at once. With 20 in parallel in the unconfirmed_search run, none
  finished.
- **Launching:** for each batch to start, run `python ledger.py launch K00N`, then start a
  general-purpose agent in the background with this prompt:

  > You are a research agent. Read and follow
  > `<repo>\data\known_within_100ly\kinematics\BRIEF.md`.
  > Your batch is **K00N**: input `...\kinematics\batches\K00N.json`, output
  > `...\known_within_100ly\agent_output\K00N.json`. If the output file already exists, resume from it as
  > the brief describes.

- **When an agent finishes:** run `python ledger.py finish K00N`. It validates the file and records counts
  in `progress.json` and `LEDGER.md`. A batch that is incomplete or has errors is marked `partial`. Relaunch
  it and it resumes from its own file.
- **About every 6 finished batches:** run `python merge.py`, then `python write.py plan` to look, then
  `python write.py wave`. The wave writes to the sheet and marks those batches written.

### Resuming after a stop

- **Nothing is lost:** every agent saves its file every 10 objects, and `write.py` writes only cells
  that are blank on the live sheet.
- **In a new session:** run `status.py`. Batches it reports as "running" have no live agent any more, so
  relaunch them; they resume from their own files.
- **The cap:** do not launch K031–K033 without the user's go-ahead.
- **Unsupported values:** `python write.py withdraw` clears any research RV on the sheet that the final agent
  files, or `merge.REJECT`, no longer support. It is safe to run at any time and prints 0 rows when the sheet
  is clean.

## Files

- `cat/`: raw catalog query results, kept so the plan can be rebuilt offline.
- `targets.json`: the tab as it was before P3. It is the record of what was already filled.
- `merged.json`: every planned cell, with its value, mark and note.
- `batches.json` and `batches/`: the research batches, fixed once made.
- `../agent_output/`: one JSON file per research batch.
- `progress.json`, `write_log.json` and `LEDGER.md`: the state.
