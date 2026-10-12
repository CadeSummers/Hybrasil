# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Correct five wrong or hybrid confirmed-planet orbits (unconfirmed_search.md section 8.4).

Wolf 1061 d, YZ Cet b, GJ 1151 c, HD 99492 c and HD 114386 c carried a refuted,
alias or superseded period on the Planets tab. Each is replaced by the NASA
Exoplanet Archive pscomppars solution (queried 27 Sep 2026), which for all five
is the paper the research agents named. HD 99492 c has no archive semi-major
axis, so its a is derived by Kepler III and marked orange.
"""
from hybrasil.data import google_sheets as gs

sid = gs.resolve_spreadsheet_id()
api = gs._sheets_api()
PL = "'Planets within 100 ly'"
S = "Sources & Provenance"
SP = f"'{S}'"
OEC = "OEC 2026-07-31"
Q = "NASA Exoplanet Archive pscomppars, queried 2026-09-27: "

meta = api.get(spreadsheetId=sid, ranges=[f"{SP}!A1"],
               fields="sheets(properties(sheetId,gridProperties))").execute()["sheets"][0]["properties"]
rows = meta["gridProperties"]["rowCount"]
assert rows == 5027, rows
start = rows + 1
X = start + 1

# row: (name, {col: (old, new)}, new AI)
FIX = {
    37: ("YZ Cet b", {"V": (1.96876, 2.02087), "W": (0.01557, 0.01634), "Z": (0, 0.06)},
         Q + "P Stock et al. 2020; a Stock et al. 2020; e Stock et al. 2020. CORRECTED 27 Sep 2026: OEC's "
             "1.96876 d is the alias period (Astudillo-Defru et al. 2017); Stock et al. 2020 resolved the true one."),
    245: ("Wolf 1061 d", {"V": (67.27, 217.21), "W": (0.2039, 0.47), "Z": (0.32, 0.55)},
          Q + "P Astudillo-Defru et al. 2017; a Astudillo-Defru et al. 2017; e Astudillo-Defru et al. 2017. "
              "CORRECTED 27 Sep 2026: OEC carried 67.27 d (Wright et al. 2016), a signal since rejected; planet d "
              "is the 217 d signal, whose 7.70 M-earth the row already had."),
    290: ("GJ 1151 c", {"V": (2.018, 389.7), "W": (0.01735, 0.5714)},
          Q + "P Blanco-Pozo et al. 2023; a Blanco-Pozo et al. 2023; e not published. CORRECTED 27 Sep 2026: "
              "OEC's 2.018 d and 0.01735 au belong to the refuted Mahadevan et al. 2021 signal, paired with the "
              "real planet's mass."),
    344: ("HD 99492 c", {"V": (4970, 95.233), "W": (5.4, 0.3866), "Z": (0.1, 0.063)},
          Q + "P Stalport et al. 2023; e Stalport et al. 2023; a DERIVED (Kepler III, paper's M = 0.85 M-sun), "
              "not in the archive. CORRECTED 27 Sep 2026: OEC's 4970 d / 5.4 au is the refuted Meschiari et al. "
              "2011 signal, paired with the real planet's mass."),
    397: ("HD 114386 c", {"V": (1046, 444.0), "W": ("", 1.05), "Z": (0.06, 0.1)},
          Q + "P Wu et al. 2026; a Wu et al. 2026; e Wu et al. 2026. CORRECTED 27 Sep 2026: OEC's 1046 d is the "
              "old solution (1.19 MJ); Wu et al. 2026 (AJ 171, 189) put c at 444.0 d with the 0.37 MJ mass the "
              "row already had."),
}

lines = [
    "",
    "PLANETS-TAB ORBIT CORRECTIONS, 27 SEPTEMBER 2026: WOLF 1061 d, YZ Cet b, GJ 1151 c, HD 99492 c, HD 114386 c.",
    "Why: each row carried a refuted, alias or superseded period from OEC (line 124), found by the unconfirmed-",
    "candidate search (repo: unconfirmed_search.md section 8.4; agents B03, B04, B16, C05). Three were hybrids,",
    "the real planet's mass beside a dead signal's period. Each row now takes period, a and e from NASA Exoplanet",
    "Archive pscomppars, queried 27 Sep 2026, which for all five is the paper the agents named. Masses unchanged.",
    "",
    "  YZ Cet b (Planets 37): P 1.96876 -> 2.02087 d, a 0.01557 -> 0.01634 au, e 0 -> 0.06. Stock et al. 2020,",
    "    A&A 636, A119: 1.97 d was the alias. Mignon et al. 2024 (2.02101 d) and CARMENES DR1 agree.",
    "  Wolf 1061 d (Planets 245): P 67.27 -> 217.21 d, a 0.2039 -> 0.47 au, e 0.32 -> 0.55. Astudillo-Defru et",
    "    al. 2017, A&A 602, A88. The 67 d signal (Wright et al. 2016) was rejected there and by Tuomi et al. 2019.",
    "  GJ 1151 c (Planets 290): P 2.018 -> 389.7 d, a 0.01735 -> 0.5714 au, e blank (not published). Blanco-Pozo",
    "    et al. 2023, A&A 671, A50. The 2.02 d signal (Mahadevan et al. 2021) is challenged in CARMENES DR1 Table 4.",
    "  HD 99492 c (Planets 344): P 4970 -> 95.233 d, a 5.4 -> 0.3866 au, e 0.1 -> 0.063. Stalport et al. 2023,",
    "    A&A 678, A90. The 4970 d signal (Meschiari et al. 2011) is refuted there.",
    "  HD 114386 c (Planets 397): P 1046 -> 444.0 d, a blank -> 1.05 au, e 0.06 -> 0.10. Wu et al. 2026, AJ 171,",
    "    189 (arXiv:2601.11280). The research agent read 444.8 d; the abstract and the archive both give 444.00.",
    "Column AI on each row names the new source and what it replaced.",
    "",
    "INFERRED, MARKED ORANGE (FFFF9900) AND NOTED: HD 99492 c semi-major axis, W344. The archive has no a for it.",
    "Kepler III, a = (M * P_yr^2)^(1/3), P = 95.233 d, M = 0.85 +/- 0.022 M-sun (Stalport et al. 2023 Table 1; the",
    "Systems tab has 0.85 too). Planet mass neglected (5e-5 M-sun). The quoted mass error gives +/-0.003 au; the",
    "paper adds 5-10% model variance on M, which is up to 3% (+/-0.012 au) on a. Valid for a bound Keplerian orbit.",
    "",
    "Derived columns (flux X, solvent band Y, velocities AA:AC, rotation AE:AH, HZ position M) are formulas and",
    "follow. None of the five moves into its star's HZ: HD 99492 c goes from beyond it to inside it, and HD 114386 c",
    "(1.05 au) now has a position, just beyond the optimistic outer edge (1.017 au).",
]
end = start + len(lines) - 1

updates, expect = {}, {}
for r, (name, cols, ai) in FIX.items():
    expect[f"{PL}!A{r}"] = name
    expect[f"{PL}!AI{r}"] = OEC
    updates[f"{PL}!AI{r}"] = ai
    for c, (old, new) in cols.items():
        expect[f"{PL}!{c}{r}"] = old
        updates[f"{PL}!{c}{r}"] = new
expect[f"{SP}!A{rows}"] = gs.read_cells(sid, [f"{SP}!A{rows}"])[f"{SP}!A{rows}"][0][0]
assert expect[f"{SP}!A{rows}"].startswith("Not changed: the 2-4% disagreements"), expect[f"{SP}!A{rows}"]

cur = gs.read_cells(sid, list(expect))
got = lambda k: cur[k][0][0] if cur[k] and cur[k][0] else ""
bad = {k: (got(k), v) for k, v in expect.items() if got(k) != v}
assert not bad, bad

api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
    "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
updates[f"{SP}!A{start}:A{end}"] = [[x] for x in lines]
expect.update({f"{SP}!A{i}": "" for i in (start, start + 1, end)})
print("cells written", gs.update_cells(sid, updates, expect=expect))

gs.set_border(sid, [f"{PL}!W344"], gs.INFERRED_BORDER)
gs.set_note(sid, {f"{PL}!W344":
    "INFERRED: Kepler III, a = (M P^2)^(1/3), P = 95.233 d, M = 0.85 +/- 0.022 M-sun (both Stalport et al. 2023). "
    "The archive has no a for this planet. +/-0.003 au from the quoted mass error; up to +/-0.012 au with the "
    f"paper's 5-10% model variance on M. Sources & Provenance, line {X}."})
print(f"S&P rows {start}-{end}, heading at {X}")
print(gs.rename_workbook(sid, gs.versioned_title()))
