# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Correct the three wrong Systems distances (GJ 411, GJ 273, VHS J1256) and their kinematics."""
from hybrasil.data import google_sheets as gs

sid = gs.resolve_spreadsheet_id()
api = gs._sheets_api()
SY = "'Systems within 100 ly'"
S = "Sources & Provenance"
SP = f"'{S}'"
LN = "'Legend & Notes'"
VHS = "VHS J125601.92-125723.9"

# --- where the provenance block will land -------------------------------
meta = api.get(spreadsheetId=sid, ranges=[f"{SP}!A1"],
               fields="sheets(properties(sheetId,gridProperties))").execute()["sheets"][0]["properties"]
rows = meta["gridProperties"]["rowCount"]
assert rows == 4998, rows
start = rows + 1
X = start + 1  # the heading line other cells point at

lines = [
    "",
    f"COLUMN C DISTANCE CORRECTIONS, 27 SEPTEMBER 2026: GJ 411, GJ 273 AND {VHS}.",
    "Why: the NASA Exoplanet Archive's sy_dist, which column C copies (line 13), contradicts the archive's own",
    "sy_plx on all three rows. pscomppars, queried 27 Sep 2026: GJ 411 sy_dist 5.676 pc against sy_plx 392.40 mas",
    "(2.548 pc), reference TICv8; GJ 273 5.922 pc against 263.26 mas (3.799 pc), TICv8; VHS J1256 12.7 +/- 1.0 pc",
    "from Gauza et al. 2015 (ApJ 804, 96), a ground parallax of 78.8 +/- 6.4 mas since superseded.",
    "Already flagged at line 53 (KNOWN ERRORS) and lines 3919-3922.",
    "",
    "NEW VALUES, ly = 3.26156 * 1000 / parallax (mas), Gaia DR3 parallax as SIMBAD gives it",
    "(data/unconfirmed_search/run2/writer/distance_audit.csv in the repo):",
    "  GJ 411 (Systems 241): 18.51 -> 8.30. plx 392.753 mas. This is Lalande 21185.",
    "  GJ 273 (Systems 300): 19.31 -> 12.35. plx 264.127 mas. This is Luyten's Star.",
    f"  {VHS} (Systems 361): 41.42 -> 68.99. plx 47.273 mas. Gaia RUWE is 7.30 (line 1302), the",
    "  parallax of an unresolved binary. Independent check: Dupuy et al. 2020, RNAAS (arXiv:2004.05180), CFHT",
    "  parallax, 22.2 +1.1/-1.2 pc = 72.4 ly, 1 sigma from Gaia. Both exclude the old 41 ly; the new value is",
    "  good to about 5%.",
    "",
    "MARKED ORANGE (FFFF9900) AND NOTED, C241, C300, C361: an inverted parallax is arithmetic on a published",
    "input, and these three no longer come from the column's stated source. The rest of column C is unchanged.",
    "The Planets and Unconfirmed tabs' column C look these up by INDEX/MATCH, so GJ 411 b/c/d, GJ 273 b/c/d/e",
    "and VHS J1256 b follow without an edit.",
    "",
    "KINEMATICS RECOMPUTED AT THE NEW DISTANCE (method of lines 3982-3985 and 4039-4040, unchanged):",
    "  Space velocity (AF): GJ 411 154.89 -> 103.02 km/s; GJ 273 106.233 -> 69.26 km/s.",
    "  Motion toward l/b (AI:AJ): GJ 411 295.87/-27.40 -> 310.78/-46.45; GJ 273 289.44/-15.57 -> 284.31/-14.30.",
    "  Check: at the old distance the same script reproduces the old AI:AJ exactly and AF to 0.03 km/s.",
    "  The WEAK clause is gone from the four AI:AJ notes, and DISTANCE MISMATCH from AK on all three rows.",
    "  VHS J1256 has no RV, so it has no space velocity or motion direction to recompute.",
    "Not changed: the 2-4% disagreements on 7 CMa, GJ 3222 and gam Cep, and HIP 86221 (no Gaia parallax).",
]
end = start + len(lines) - 1

# --- guarded value writes ------------------------------------------------
motion_note = ("INFERRED: direction the star is moving, relative to the Sun, in galactic l/b. From RA/Dec, "
               "distance (C), RV and proper motions (AB:AD) via astropy; no LSR correction. Its speed reproduces "
               "Space velocity (AF). Recomputed 27 Sep 2026 at the corrected distance ({new} ly; was {old}).")
updates = {
    f"{SY}!C241": 8.3, f"{SY}!C300": 12.35, f"{SY}!C361": 68.99,
    f"{SY}!AF241": 103.02, f"{SY}!AF300": 69.26,
    f"{SY}!AI241": 310.78, f"{SY}!AJ241": -46.45,
    f"{SY}!AI300": 284.31, f"{SY}!AJ300": -14.3,
    f"{SY}!AK241": "RV: Gaia DR3; PM: Gaia DR3 | DISTANCE: Gaia DR3 parallax (was 18.51 ly, corrected 27 Sep 2026)",
    f"{SY}!AK300": "RV: Gaia DR3; PM: Gaia DR3 | DISTANCE: Gaia DR3 parallax (was 19.31 ly, corrected 27 Sep 2026)",
    f"{SY}!AK361": "PM: Gaia DR3 | DISTANCE: Gaia DR3 parallax (was 41.42 ly, corrected 27 Sep 2026); "
                   "RUWE 7.30 -- astrometry may be perturbed",
    # Sources & Provenance: the column row and the KNOWN ERRORS row
    f"{SP}!B13": "Archive sy_dist (parsecs), multiplied by 3.26156. GJ 411, GJ 273, VHS J1256: "
                 "3.26156 * 1000 / Gaia DR3 parallax",
    f"{SP}!C13": "High; 3 rows corrected 27 Sep 2026",
    f"{SP}!D13": f"The archive's sy_dist contradicted its own parallax on GJ 411, GJ 273 and VHS J1256; those "
                 f"now use Gaia DR3 (line {X}). Still 2-4% off Gaia: 7 CMa, GJ 3222, gam Cep. HIP 86221 has "
                 f"no Gaia parallax.",
    f"{SP}!B53": "FIXED 27 SEP 2026",
    f"{SP}!D53": f"Corrected to 8.30 (Gaia DR3 plx 392.753 mas). Space velocity 154.89 -> 103.02 km/s. "
                 f"See line {X}.",
    # Legend & Notes paragraph that pointed at the error
    f"{LN}!A155": "COLUMN C DISTANCES (FIXED 27 SEPTEMBER 2026)",
    f"{LN}!A156": "  GJ 411 is Lalande 21185, the fourth-nearest star system, at 8.30 ly. Column C said 18.51 until",
    f"{LN}!A157": "  27 Sep 2026: the NASA archive's sy_dist contradicted its own parallax. It now uses Gaia DR3, as",
    f"{LN}!A158": "  do GJ 273 (19.31 -> 12.35) and VHS J1256 (41.42 -> 68.99). GJ 411's velocity is now 103.02 km/s,",
    f"{LN}!A159": f"  not 154.89. See Sources & Provenance, line {X}.",
}
expect = {
    f"{SY}!A241": "GJ 411", f"{SY}!A300": "GJ 273", f"{SY}!A361": VHS,
    f"{SY}!C241": 18.51, f"{SY}!C300": 19.31, f"{SY}!C361": 41.42,
    f"{SY}!AF241": 154.89, f"{SY}!AF300": 106.233,
    f"{SY}!AI241": 295.87, f"{SY}!AJ241": -27.4, f"{SY}!AI300": 289.44, f"{SY}!AJ300": -15.57,
    f"{SP}!A13": "Distance (ly)", f"{SP}!A53": "GJ 411 distance = 18.51 ly",
    f"{SP}!B53": "CONFIRMED WRONG",
    f"{LN}!A155": "ONE THING TO CHECK IN COLUMN B",
    f"{LN}!A156": "  GJ 411 is Lalande 21185, the fourth-nearest star system, at about 8.3 ly. Column B says 18.51.",
    f"{SP}!A{rows}": gs.read_cells(sid, [f"{SP}!A{rows}"])[f"{SP}!A{rows}"][0][0],
}
assert expect[f"{SP}!A{rows}"].startswith("    exoplanet.eu planet pages delta Pav"), expect[f"{SP}!A{rows}"]

# Check every existing cell before growing the grid, so a mismatch leaves the sheet untouched.
cur = gs.read_cells(sid, list(expect))
bad = {k: (cur[k][0][0] if cur[k] and cur[k][0] else "", v) for k, v in expect.items()
       if (cur[k][0][0] if cur[k] and cur[k][0] else "") != v}
assert not bad, bad

# Append the provenance rows first so their range exists, then write everything under one guard.
api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
    "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
updates[f"{SP}!A{start}:A{end}"] = [[x] for x in lines]
expect.update({f"{SP}!A{i}": "" for i in (start, start + 1, end)})
n = gs.update_cells(sid, updates, expect=expect)
print("cells written", n)

# --- markings ------------------------------------------------------------
gs.set_border(sid, [f"{SY}!C241", f"{SY}!C300", f"{SY}!C361"], gs.INFERRED_BORDER)
gs.set_note(sid, {
    f"{SY}!C241": f"INFERRED: 3.26156 * 1000 / 392.753 mas, the Gaia DR3 parallax (via SIMBAD). Replaces 18.51 ly, "
                  f"the NASA archive's sy_dist, which contradicts the archive's own parallax. "
                  f"Sources & Provenance, line {X}.",
    f"{SY}!C300": f"INFERRED: 3.26156 * 1000 / 264.127 mas, the Gaia DR3 parallax (via SIMBAD). Replaces 19.31 ly, "
                  f"the NASA archive's sy_dist, which contradicts the archive's own parallax. "
                  f"Sources & Provenance, line {X}.",
    f"{SY}!C361": f"INFERRED: 3.26156 * 1000 / 47.273 mas, the Gaia DR3 parallax (via SIMBAD). Replaces 41.42 ly "
                  f"(Gauza et al. 2015's 12.7 pc, superseded). Gaia RUWE is 7.30, an unresolved binary; Dupuy et al. "
                  f"2020's independent CFHT parallax gives 72.4 ly, within 1 sigma. Sources & Provenance, line {X}.",
    f"{SY}!AI241": motion_note.format(new="8.30", old="18.51"),
    f"{SY}!AJ241": motion_note.format(new="8.30", old="18.51"),
    f"{SY}!AI300": motion_note.format(new="12.35", old="19.31"),
    f"{SY}!AJ300": motion_note.format(new="12.35", old="19.31"),
})
print(f"S&P rows {start}-{end}, heading at {X}")
print(gs.rename_workbook(sid, gs.versioned_title()))
