# The Sgr A* S-stars tab

These scripts built the workbook's **Sgr A\* S-stars** tab on 9 Oct 2026; the workbook was then `hy-brasil-20261009-2313`.

- **The tab:** Sgr A*, the 40 S-star orbits of Gillessen et al. 2017, and seven disputed newcomers.
- **10 Oct 2026:** `add.py` appended nine rows from `research/D.json` (workbook `hy-brasil-20261010-1302`): S301, six von Fellenberg et al. 2022 stars, and the dusty objects G1 and G2.
- **The viewer side:** `docs/architecture/galactic-centre.md`.

| File | What it is |
|---|---|
| `cat/gillessen2017_table3.dat`, `table5.dat`, `ReadMe` | VizieR J/ApJ/837/30. Table 3 holds the orbits, early/late flags and K; table 5 holds S2's positions and RVs, which the frame test uses |
| `cat/EEM_dwarf_UBVIJHK_colors_Teff.txt` | Mamajek's mean dwarf sequence (Pecaut & Mamajek 2013; version 2022.04.16) |
| `research/A.json`, `B.json` | Spectral type, mass, Teff, measured RV and SIMBAD id per star, each value with its bibcode and table. A covers S1–S31, B covers S33–R44 |
| `research/D.json` | S301 (GRAVITY+ 2026, both orbit solutions), every other orbit published 2017–2026 that the tab lacked (`new_stars`), detections with no orbit (`no_orbit`), and the S0-x/E-number cross-identifications onto tab names. Every orbit added was checked against the paper's table |
| `research/C.json` | Sgr A* (GRAVITY 2022 mass and R0, SIMBAD position, the EHT mass), GRAVITY's refits of S2/S29/S38/S55, and the disputed stars' orbits with both sides of each dispute |
| `infer.py` | Class, Teff and mass from K for an untyped early-type star, plus `calibrate()` |
| `plan.py` | Decides every cell and writes `plan.json`. It touches nothing |
| `add.py` | The second writer: appends the plan's rows the tab lacks, after checking every row already there reads back as the plan has it. Log `write_log_20261010.json` |
| `build.py` | The first writer. It adds the tab, writes it, re-reads every value, boxes and notes the inferred cells by name, checks the boxes read back, adds rows to Sources & Provenance, and renames the workbook |
| `write_log.json` | The record of the write |

## How the research was checked

Three research agents gathered the values (`research/`). Every value had to carry a bibcode and the table it came from, or stay null.

**Checks before writing:**
- **GRAVITY 2022 (arXiv:2112.07478):** all four refits, the mass and R0 were found in the PDF.
- **Habibi et al. 2017 (arXiv:1708.06353):** all seven masses and Teffs were found in the PDF.
- **The 2026 GRAVITY+ Nature paper:** confirmed through Crossref (Nature 657, 359–363, 19 Aug 2026).
- **Periods:** every Gillessen period agrees with √(a³/M) at their own R0 and M within 3σ.

**Doubts carried into the notes:**
- Two different stars are called S62. SIMBAD merges them.
- R44 is S2-21 only on one cross-identification.
- S83's radial velocities disagree between papers.

## Result

| | Count |
|---|---|
| Rows | 57 (Sgr A* + 40 + 7 disputed + 9 added 10 Oct) |
| Published spectral types | 20 of 47 (6 of them Habibi 2017's B0-B3 V range) |
| Published masses | 17 of 47 |
| Inferred (orange) | 565 cells: 478 on 9 Oct (classes 18, masses 24, Teff 17, a(AU) and pericentre 46 each, periods 4, motion 7 × 46, Sgr A*'s distance in ly), 87 on 10 Oct (a(AU), pericentre and motion for the nine, masses 4, periods 2) |
| Drawn | 55 orbits (7 hollow, 2 dusty); S111 is unbound and not drawn |
