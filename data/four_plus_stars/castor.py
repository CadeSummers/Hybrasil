# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Complete Castor (alf Gem) on "Planetless 4+ Stars" from the literature, so the featured system can be drawn from it.

    python castor.py plan      print every cell it would write, old -> new; touches nothing
    python castor.py write     write, mark, note, provenance, rename

Every value comes from lit/castor.json (paper, identifier, URL and quote per value), gathered 30 Sep 2026.

1. Teff for the four stars that have one (Torres & Ribas 2002); Ab and Bb, which no paper characterises, get the
   Pecaut & Mamajek M2.5V value their class and luminosity were already inferred from (orange).
2. Periods at the precision the papers give. The rounded 0.8143 d put YY Gem a quarter of an orbit out of phase
   after 12,000 cycles.
3. AB-C period: the MSC orbit table has 134,630 yr, ten times too long -- ORB6 lists that solution as 134.63
   CENTURIES, the MSC's own pair table says 13.93 kyr, and Kepler's third law with a = 71.4" and 6.18 Msun gives
   ~14,200 yr. 13,463 yr it is.
4. Ba-Bb: e = 0 (fixed by Torres 2022), i 110.50 (the MSC has 110.55), and omega = 0 for Ba: T_B is Ba's time of
   maximum velocity, which for a circular orbit is its ascending node in the standard convention (node = receding).
5. YY Gem (Ca-Cb): e = 0, i 86.29, and the Torres & Ribas 2002 eclipse ephemeris in place of the 1927 SB orbit's T.
   At primary minimum Ca is eclipsed, so Cb is nearest us and Ca farthest: omega = 90 for Ca (convention as above).
   The node is not measurable for an eclipsing pair without astrometry: 0, WEAK, orange.
6. Cab-Cc: nothing constrains i or the node. Assumed coplanar with YY Gem (i 86.29, node 0), which is also the
   assumption under the paper's minimum mass. WEAK, orange.
7. A new column, 'Argument of periastron refers to', filled for Castor only: a spectroscopic omega is the
   primary's, a visual one the secondary's relative to the primary, and the two differ by 180 degrees. Blank
   elsewhere means not checked.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)

SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
FP, SP = "Planetless 4+ Stars", "Sources & Provenance"
LOG = HERE / "castor_log.json"
PLAN = sys.argv[1:] == ["plan"]
REFERS = "Argument of periastron refers to"

TR02 = "Torres & Ribas 2002, ApJ 567, 1140 (2002ApJ...567.1140T; arXiv:astro-ph/0111167) https://arxiv.org/abs/astro-ph/0111167"
T22 = "Torres et al. 2022, ApJ 941, 8 (2022ApJ...941....8T; arXiv:2210.16322) https://arxiv.org/abs/2210.16322"
W18 = ("Wolf, Kucakova, Zasche et al. 2018, A&A 620, A72 (2018A&A...620A..72W; doi:10.1051/0004-6361/201833620) "
       "https://doi.org/10.1051/0004-6361/201833620")
PM = ("Pecaut & Mamajek 2013, ApJS 208, 9, table v2022.04.16 "
      "(https://www.pas.rochester.edu/~emamajek/EEM_dwarf_UBVIJHK_colors_Teff.txt)")
CONV = ("Convention: the standard one, ascending node = the node where the star recedes from us. NB the viewer "
        "draws sky-frame orbits with z toward Earth, so its depth is mirrored for every such system alike.")
WEAK_NODE = "WEAK: ASSUMED, nothing measures it."

# (component, column): (new value, note or None, orange?)
EDITS = {
    ("alf Gem Aa", "Effective temp (K)"): (9420, f"SOURCE: {TR02}: Teff 9420 +/- 100 K for Castor A, from colour "
                                                 "calibrations of the unresolved A pair; Aa dominates its light.", False),
    ("alf Gem Ba", "Effective temp (K)"): (8240, f"SOURCE: {TR02}: Teff 8240 +/- 150 K for Castor B, from colour "
                                                 "calibrations of the unresolved B pair; Ba dominates its light.", False),
    ("alf Gem Ca", "Effective temp (K)"): (3820, f"SOURCE: {TR02}: Teff 3820 +/- 100 K for each YY Gem star.", False),
    ("alf Gem Cb", "Effective temp (K)"): (3820, f"SOURCE: {TR02}: Teff 3820 +/- 100 K for each YY Gem star.", False),
    ("alf Gem Ab", "Effective temp (K)"): (3470, "WEAK: rests on the MSC mass alone (0.39 Msun, Torres 2022: "
                                                 "0.3859).\nINFERRED from the class M2.5V (itself inferred from the "
                                                 f"mass) through {PM}: M2.5V = 3470 K, the row the luminosity came from. "
                                                 "No paper has a spectrum of Ab; Torres 2022 calls it M2-M3.", True),
    ("alf Gem Bb", "Effective temp (K)"): (3470, "WEAK: rests on the MSC mass alone (0.39 Msun, Torres 2022: "
                                                 "0.3865).\nINFERRED from the class M2.5V (itself inferred from the "
                                                 f"mass) through {PM}: M2.5V = 3470 K, the row the luminosity came from. "
                                                 "No paper has a spectrum of Bb; Torres 2022 calls it M2-M3.", True),

    ("alf Gem Ab", "Orbital period (d)"): (9.2127496, f"SOURCE: {T22}: P = 9.2127496 +/- 0.0000052 d.", False),
    ("alf Gem Ab", REFERS): ("primary (Aa)", f"{T22} quotes omega for the primary, Aa (264.968). Ab relative to "
                                             "Aa is 84.968.", False),

    ("alf Gem B", REFERS): ("secondary (B relative to A)", f"{T22}: the A-B omega (251.84) is the secondary's.", False),

    ("alf Gem Bb", "Orbital period (d)"): (2.92835083, f"SOURCE: {T22}: P = 2.92835083 +/- 0.00000031 d.", False),
    ("alf Gem Bb", "Orbital eccentricity (e)"): (0, f"SOURCE: {T22}: circular orbit, e fixed at 0.", False),
    ("alf Gem Bb", "Inclination (deg)"): (110.5, f"SOURCE: {T22}: i = 110.50 +/- 0.12 deg. The MSC has 110.55.", False),
    ("alf Gem Bb", "Argument of periastron (deg)"): (
        0, "INFERRED (a convention, not a measurement): the orbit is circular, so it has no periastron. Torres 2022's "
           "T_B (the 'Time of periastron' cell) is Ba's time of maximum radial velocity; omega = 0 for Ba makes T_B "
           f"its ascending node, which is where a receding star's velocity peaks. {CONV}", True),
    ("alf Gem Bb", REFERS): ("primary (Ba)", "See the omega cell's note.", False),
    ("alf Gem Bb", "Time of periastron (JD)"): (
        2456705.494, f"SOURCE: {T22}: T_B = HJD 2456705.4942 +/- 0.0012, the time of MAXIMUM radial velocity of Ba, "
                     "not a periastron (the orbit is circular). Paired with omega = 0 for Ba.", False),

    ("alf Gem C", "Orbital period (d)"): (
        4917360.75, "CORRECTED from 49,173,607.5 d (134,630 yr), a factor-of-ten error in the MSC orbit table: ORB6 "
                    "lists this Kiyaeva 2015 solution as 134.63 CENTURIES, the MSC's own pair table gives 13.93 kyr, "
                    "and Kepler's third law with a = 71.4\" (1076 au) and 6.18 Msun gives ~14,200 yr. 13,463 yr x "
                    "365.25. Matvienko, Kiyaeva & Orlov 2015 (Astron. Lett. 41, 43) give a family of orbits (ORB6: "
                    "128.17, 134.63 and 187.12 centuries) and prefer none; this is the one the MSC carries. "
                    "Grade 5: indeterminate.", False),
    ("alf Gem C", REFERS): ("secondary (C relative to AB)", "A visual orbit: omega is the secondary's.", False),

    ("alf Gem Cb", "Orbital period (d)"): (0.814282212, f"SOURCE: {TR02}: Min I = HJD 2449345.112327 + 0.814282212 E.",
                                           False),
    ("alf Gem Cb", "Orbital eccentricity (e)"): (0, f"SOURCE: {TR02}, circular orbit adopted; Kochukhov & Shulyak "
                                                    "2019 (ApJ 873, 69) fit e = 0.00035 +/- 0.00028.", False),
    ("alf Gem Cb", "Inclination (deg)"): (86.29, f"SOURCE: {TR02}: i = 86.29 +/- 0.10 deg (180 - i is equally "
                                                 "allowed by the light curve). Butler et al. 2015: 86.0.", False),
    ("alf Gem Cb", "Ascending node (deg)"): (
        0, f"{WEAK_NODE}\nAn eclipsing, double-lined pair has no measured node without astrometry, and YY Gem has "
           "none. 0, as for every unmeasured node in the featured systems.", True),
    ("alf Gem Cb", "Argument of periastron (deg)"): (
        90, "INFERRED (a convention, not a measurement): the orbit is circular. The 'Time of periastron' cell is the "
            "time of primary minimum, when Ca is eclipsed, so Cb is between Ca and us: Ca is at its farthest, "
            f"argument of latitude 90 deg, so omega = 90 for Ca. {CONV}", True),
    ("alf Gem Cb", REFERS): ("primary (Ca)", "See the omega cell's note.", False),
    ("alf Gem Cb", "Time of periastron (JD)"): (
        2449345.112327, f"SOURCE: {TR02}: Min I = HJD 2449345.112327 + 0.814282212 E, the time of primary minimum "
                        "(Ca eclipsed), not a periastron: the orbit is circular; see the omega cell. Replaces the "
                        "MSC's T from the 1927 SB orbit (SB 463), HJD 2424989.1. Wolf et al. 2018: BJD_TDB "
                        "2424595.82174, P = 0.81428219.", False),
    ("alf Gem Cb", "Orbit source"): ("Torres & Ribas 2002 (ApJ 567, 1140); SB 463", None, False),

    ("alf Gem Cc", "Inclination (deg)"): (
        86.29, "WEAK: ASSUMED.\nNothing measures it: the orbit is from eclipse timing (Wolf et al. 2018), which "
               "gives a12 sin i only. Assumed coplanar with YY Gem (86.29), which is also the assumption behind the "
               "paper's minimum mass for Cc (0.047 Msun at i ~ 90).", True),
    ("alf Gem Cc", "Ascending node (deg)"): (
        0, f"{WEAK_NODE}\nAssumed coplanar with YY Gem, whose own node is assumed 0.", True),
    ("alf Gem Cc", REFERS): (
        "primary (Cab)", f"INFERRED: {W18} does not say which body omega3 = 37.6 belongs to. A light-travel-time fit "
                         "(Irwin 1952) quotes the eclipsing pair's orbit about the triple's barycentre, i.e. Cab's; "
                         "Cc relative to Cab is then 217.6.", True),
}


def main():
    v = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A1:CZ2000", valueRenderOption="UNFORMATTED_VALUE"
                         ).execute()["values"]
    h = v[0]
    assert h[-1] == "Barycentre offset (AU)" and REFERS not in h, h[-2:]
    h = h + [REFERS]
    col = {k: i for i, k in enumerate(h)}
    rows = {}
    for r, row in enumerate(v[1:], start=2):
        row = row + [""] * (len(h) - len(row))
        if row[col["Star (component)"]].startswith("alf Gem "):
            rows[row[col["Star (component)"]]] = (r, row)
    assert len(rows) == 12, sorted(rows)

    upd, expect, notes, orange = {}, {}, {}, []
    for (name, header), (new, note, inferred) in EDITS.items():
        r, row = rows[name]
        c = f"{q(FP)}!{letter(col[header])}{r}"
        expect[c] = row[col[header]]
        upd[c] = new
        if note:
            notes[c] = note
        if inferred:
            orange.append(c)
    for name, extra in (("alf Gem Aa", "Teff: Torres & Ribas 2002"), ("alf Gem Ba", "Teff: Torres & Ribas 2002"),
                        ("alf Gem Ca", "Teff: Torres & Ribas 2002"), ("alf Gem Cb", "Teff: Torres & Ribas 2002"),
                        ("alf Gem Ab", "Teff: INFERRED (Pecaut & Mamajek)"),
                        ("alf Gem Bb", "Teff: INFERRED (Pecaut & Mamajek)")):
        r, row = rows[name]
        c = f"{q(FP)}!{letter(col['Star data source'])}{r}"
        expect[c] = row[col["Star data source"]]
        upd[c] = f"{row[col['Star data source']]}; {extra}"
    head = f"{q(FP)}!{letter(col[REFERS])}1"
    expect[head], upd[head] = "", REFERS
    notes[head] = ("A spectroscopic omega is the primary's; a visual (relative) orbit's is the secondary's relative to "
                   "the primary; the two differ by 180 deg, and the MSC mixes them. Filled where checked against the "
                   "paper (Castor, 30 Sep 2026); blank = not checked.")

    lines = [
        "",
        "30 SEPTEMBER 2026: 'Planetless 4+ Stars' -- CASTOR (alf Gem) COMPLETED FROM THE LITERATURE (castor.py).",
        "Writer: data/four_plus_stars/castor.py; log castor_log.json. Records with quotes: "
        "data/four_plus_stars/lit/castor.json (108 values).",
        "Teff: Aa 9420, Ba 8240, Ca = Cb 3820 K (Torres & Ribas 2002, ApJ 567, 1140; colour calibrations, +/-100-150 K). "
        "Ab, Bb 3470 K INFERRED (orange, WEAK) from the M2.5V row of Pecaut & Mamajek v2022.04.16, the class their "
        "luminosity was already inferred from. Confidence MEDIUM for A and B (the pair's combined colours), HIGH for YY Gem.",
        "Periods at published precision: Aa-Ab 9.2127496 d, Ba-Bb 2.92835083 d (Torres et al. 2022, ApJ 941, 8); "
        "Ca-Cb 0.814282212 d (Torres & Ribas 2002).",
        "AB-C period CORRECTED 49,173,607.5 -> 4,917,360.75 d (13,463 yr): the MSC orbit table's 134,630 yr is ten "
        "times ORB6's 134.63 centuries, the MSC pair table's 13.93 kyr and Kepler's ~14,200 yr. Kiyaeva et al. 2015 "
        "give a family of solutions and prefer none (grade 5, indeterminate). Other MSC 'y' periods from ORB6 "
        "centuries may carry the same slip: not checked.",
        "Ba-Bb: e = 0 and i 110.50 (Torres 2022; MSC 110.55); omega = 0 for Ba INFERRED (orange), a convention: T_B is "
        "Ba's time of maximum velocity. Ca-Cb: e = 0, i 86.29 and the eclipse ephemeris HJD 2449345.112327 (Torres & "
        "Ribas 2002) replace the 1927 SB orbit's T; omega = 90 for Ca INFERRED (orange), from Ca being eclipsed at "
        "primary minimum; node 0 ASSUMED (orange, WEAK).",
        "Cab-Cc (Wolf et al. 2018, A&A 620, A72): i 86.29 and node 0 ASSUMED coplanar with YY Gem (orange, WEAK); "
        "which body omega3 = 37.6 refers to INFERRED as Cab (light-travel-time convention; orange).",
        "NEW COLUMN 'Argument of periastron refers to': primary (spectroscopic omega) or secondary (visual omega, "
        "relative to the primary); they differ by 180 deg and the MSC mixes them. Castor only; blank = not checked.",
        "  All omegas and nodes in the standard convention (ascending node = receding). The viewer draws sky-frame "
        "orbits with z toward Earth, which mirrors every such system's depth alike (Alpha Centauri included).",
    ]

    if PLAN:
        for c, val in upd.items():
            print(f"  {'O ' if c in orange else '  '}{c:42} {expect[c]!r:>28.28} -> {val!r:.60}")
        print(f"{len(upd)} cells, {len(notes)} notes, {len(orange)} orange")
        print("\n".join(lines))
        return

    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    fp = next(s["properties"] for s in meta if s["properties"]["title"] == FP)
    c0 = col[REFERS]
    if fp["gridProperties"]["columnCount"] <= c0:
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
            "sheetId": fp["sheetId"], "dimension": "COLUMNS", "length": c0 + 1 - fp["gridProperties"]["columnCount"]}}]}
        ).execute()
    last = len(v)
    src = {"sheetId": fp["sheetId"], "startRowIndex": 0, "endRowIndex": last,
           "startColumnIndex": c0 - 2, "endColumnIndex": c0 - 1}          # 'Barycentre from': plain rules
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"copyPaste": {
        "source": src, "destination": {**src, "startColumnIndex": c0, "endColumnIndex": c0 + 1},
        "pasteType": "PASTE_FORMAT"}}]}).execute()
    gs.update_cells(SID, upd, expect=expect)
    gs.set_border(SID, orange, gs.INFERRED_BORDER)
    gs.set_note(SID, notes)

    spm = next(s["properties"] for s in meta if s["properties"]["title"] == SP)
    lastsp = spm["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{lastsp}"])[f"{q(SP)}!A{lastsp}"][0][0].strip()
    start, end = lastsp + 1, lastsp + len(lines)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": spm["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log = {"cells": {c: [expect[c], val] for c, val in upd.items()}, "orange": orange, "notes": sorted(notes),
           "sp_rows": [start, end], "title": title}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps({k: log[k] for k in ("sp_rows", "title")}), len(upd), "cells,", len(orange), "orange")


if __name__ == "__main__":
    main()
