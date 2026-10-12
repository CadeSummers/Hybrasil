# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Add two spectroscopic companions the MSC does not list to "Planetless 4+ Stars", as hypothetical stars.

    python companions.py plan     print the rows that would be inserted and every cell that would change
    python companions.py write    insert, write, mark, note, provenance, rename

research.py found two single-lined orbits on stars the tab draws as single. The owner chose (30 Sep 2026) to add
both, drawn hollow and labelled hypothetical and model-inferred, with the doubts stated:

  GJ 187.2 A   SB9 system 295: P = 391.7 d, e = 0.37, omega = 84.0, K1 = 5.8 km/s (Abt 1965, ApJS 11, 429;
               SB9 grade 2). The MSC leaves it out. Gaia DR3 has no orbit for it and RUWE 1.56 (G = 4.9), where a
               companion of this size would move the star ~7 mas.
  GJ 3347 Aa   Gaia DR3 SB1, source_id 3340966243931480448: P = 3.7794 d, e = 0.512, omega = 345.6, K1 = 1.785 km/s,
               significance 16.8. The known 1427-d companion Ab dominates this star's velocities, and a period
               search over Gaia's 34 months can alias it; e = 0.5 at 3.8 d is unusual for a close pair.

Each host row A becomes a subsystem (A = Aa + Ab), a copy of it becomes the host star Aa, and a new row holds the
companion. The companion's mass is its minimum mass from the mass function, as the MSC gives SB1 companions; the
relative semi-major axis is from Kepler's third law with it. Ancestor masses and barycentre offsets follow.

A new last column, 'Drawing status', says 'hypothetical and model-inferred' on the two new stars; blank means drawn
as confirmed.
"""
import json
import math
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
LOG = HERE / "companions_log.json"
PLAN = sys.argv[1:] == ["plan"]
STATUS = "Drawing status"
HYPO = "hypothetical and model-inferred"
YR = 365.25
# The star-only columns a subsystem row leaves blank; formulas among them are written back on star rows.
STAR_ONLY = ["Stellar Class", "Class (sort key)", "Luminosity class", "Effective temp (K)", "Age (Gyr)",
             "Metallicity [Fe/H]", "Luminosity (L-sun)", "HZ distance", "Planets in HZ", "HZ planet names",
             "Methane band, 1 bar A=0.3 (AU)", "Ethane band, 1 bar A=0.3 (AU)", "Ammonia band, 1 bar A=0.3 (AU)",
             "Water band, 1 bar A=0.3 (AU)", "Formamide band, 1 bar A=0.3 (AU)",
             "Sulfuric acid band, 1 bar A=0.3 (AU)", "Liquid sulfur band, 1 bar A=0.3 (AU)",
             "Liquid CO2 band, 50 bar A=0.3 (AU)", "Radial velocity (km/s)",
             "Proper motion in RA, μα·cos δ (mas/yr)", "Proper motion in Dec, μδ (mas/yr)",
             "Total proper motion, μ (arcsec/yr)", "Space velocity (km/s)", "Kinematics source",
             "Gaia DR3 source_id", "Planet-host star", "Planet-host class"]

NEW = [
    dict(system="GJ 187.2", host="GJ 187.2 A", star="GJ 187.2 Aa", comp="GJ 187.2 Ab", lab=("Aa", "Ab"),
         hierarchy="((Aa,Ab),B),(C,D)", role="star",
         P=391.7, e=0.37, omega=84.0, T=2418619.0, K1=5.8,
         orbit_source="SB9_295 1965ApJS...11..429A",
         detection="spectroscopic orbit, single-lined (SB9 only; not in the MSC)",
         src="SB9 (Pourbaix et al. 2004, A&A 424, 727; release of 2024-06-21), system 295, orbit of Abt 1965, ApJS 11, "
             "429, grade 2",
         doubt="SB9 grade 2 (poor), a 1965 orbit of an F0 star, and left out of the MSC; Gaia DR3 has no orbit for "
               "GJ 187.2 A and RUWE 1.56 at G = 4.9, where a companion this size would move it ~7 mas"),
    dict(system="GJ 3347", host="GJ 3347 Aa", star="GJ 3347 Aa1", comp="GJ 3347 Aa2", lab=("Aa1", "Aa2"),
         hierarchy="(((Aa1,Aa2),Ab),B),(Ea,Eb)", role="brown dwarf (candidate)",
         P=3.7794, e=0.5118, omega=345.59, T=2457389.0 - 0.8288, K1=1.785,
         orbit_source="Gaia DR3 NSS SB1, source_id 3340966243931480448",
         detection="spectroscopic orbit, single-lined (Gaia DR3 only; not in the MSC)",
         src="Gaia DR3 non-single-star catalogue (Arenou et al. 2023, A&A 674, A34), nss_two_body_orbit, source_id "
             "3340966243931480448, solution SB1, P = 3.7794 d, significance 16.8; T = J2016.0 (JD 2457389.0) - "
             "0.8288 d",
         doubt="the known 1427-d companion Ab dominates this star's velocities (Gaia RUWE 10, non_single_star 3), a "
               "period search over Gaia's 34 months can alias it, and e = 0.51 at 3.8 d is unusual for a close pair"),
]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def min_mass(m1, f):
    """M2 with M2^3 / (M1 + M2)^2 = f (i = 90 degrees), by bisection."""
    lo, hi = 0.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if mid ** 3 / (m1 + mid) ** 2 < f:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def read():
    v = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A1:CZ2000", valueRenderOption="UNFORMATTED_VALUE"
                         ).execute()["values"]
    h = v[0]
    rows = [(r, row + [""] * (len(h) - len(row))) for r, row in enumerate(v[1:], start=2)]
    return h, rows


def main():
    h, rows = read()
    col = {k: i for i, k in enumerate(h)}
    by = {row[col["Star (component)"]]: (r, row) for r, row in rows if row[col["Star (component)"]]}
    for n in NEW:
        assert n["star"] not in by and n["comp"] not in by, f"{n['comp']} already on the tab"
        assert by[n["host"]][1][col["Node type"]] == "star"
    plan = []
    for n in NEW:
        r, row = by[n["host"]]
        m1 = num(row[col["Mass (M-sun)"]])
        f = 1.0361e-7 * (1 - n["e"] ** 2) ** 1.5 * n["K1"] ** 3 * n["P"]
        m2 = min_mass(m1, f)
        a = ((m1 + m2) * (n["P"] / YR) ** 2) ** (1 / 3)
        plx = 3.26156 / num(row[col["Distance (ly)"]])
        n.update(r=r, m1=m1, f=f, m2=round(m2, 4), a=round(a, 6), plx=plx)
        plan.append(n)
        print(f"{n['host']} (row {r}): f(M) = {f:.3e} M_sun, M1 = {m1}, M2 >= {m2:.4f} M_sun "
              f"({m2 * 1047.6:.1f} M_jup), a = {a:.5f} AU = {a * plx:.6f}\"")
    if PLAN:
        return

    # ── structure: a status column, then two rows after each host (the lower host first) ───────────────
    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    fp = next(s["properties"] for s in meta if s["properties"]["title"] == FP)
    sheet = fp["sheetId"]
    reqs = []
    if STATUS not in col:
        cs = len(h)
        if fp["gridProperties"]["columnCount"] <= cs:
            reqs.append({"appendDimension": {"sheetId": sheet, "dimension": "COLUMNS", "length": 1}})
        reqs.append({"copyPaste": {
            "source": {"sheetId": sheet, "startRowIndex": 0, "endRowIndex": fp["gridProperties"]["rowCount"],
                       "startColumnIndex": cs - 1, "endColumnIndex": cs},
            "destination": {"sheetId": sheet, "startRowIndex": 0, "endRowIndex": fp["gridProperties"]["rowCount"],
                            "startColumnIndex": cs, "endColumnIndex": cs + 1}, "pasteType": "PASTE_FORMAT"}})
    for n in sorted(plan, key=lambda n: -n["r"]):
        r0 = n["r"] - 1                                    # 0-based index of the host row
        reqs.append({"insertDimension": {"range": {"sheetId": sheet, "dimension": "ROWS", "startIndex": r0 + 1,
                                                   "endIndex": r0 + 3}, "inheritFromBefore": True}})
        for k in (1, 2):
            reqs.append({"copyPaste": {
                "source": {"sheetId": sheet, "startRowIndex": r0, "endRowIndex": r0 + 1},
                "destination": {"sheetId": sheet, "startRowIndex": r0 + k, "endRowIndex": r0 + k + 1},
                "pasteType": "PASTE_NORMAL"}})
    API.batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()
    if STATUS not in col:
        gs.update_cells(SID, {f"{q(FP)}!{letter(len(h))}1": [[STATUS]]},
                        expect={f"{q(FP)}!{letter(len(h))}1": ""})

    # ── values ──────────────────────────────────────────────────────────────────────────────────
    h, rows = read()
    col = {k: i for i, k in enumerate(h)}
    idx = {r: row for r, row in rows}
    updates, expect, orange, plain, notes, blank_notes = {}, {}, [], [], {}, []

    def a1(hd, r):
        return f"{q(FP)}!{letter(col[hd])}{r}"

    def put(r, hd, value, note=None, inferred=False):
        updates[a1(hd, r)] = [[value]]
        (orange if inferred else plain).append(a1(hd, r))
        if note:
            notes[a1(hd, r)] = note

    shift = 0
    for n in sorted(plan, key=lambda n: n["r"]):
        rA = n["r"] + shift                                 # the host row, moved down by earlier inserts
        rS, rC = rA + 1, rA + 2
        shift += 2
        for rr in (rA, rS, rC):
            expect[a1("Star (component)", rr)] = n["host"]
        host_row = idx[rA]
        sysname = n["system"]
        m1, m2, a = n["m1"], n["m2"], n["a"]
        pa, pc = n["lab"]
        why_m = (f"WEAK: {n['doubt']}.\nINFERRED: minimum mass (i = 90) from the mass function f(M) = 1.0361e-7 "
                 f"(1 - e^2)^1.5 K1^3 P = 1.0361e-7 x (1 - {n['e']}^2)^1.5 x {n['K1']}^3 x {n['P']} = {n['f']:.3e} "
                 f"M_sun, solved M2^3 / (M1 + M2)^2 = f(M) with M1 = {m1} ({n['star']}, this tab). SOURCE: {n['src']}.")
        why_a = (f"WEAK: rests on the inferred minimum mass of {n['comp']}.\nINFERRED: a = ((M1 + M2) P^2)^(1/3) = "
                 f"(({m1} + {m2}) x ({n['P']} d / 365.25)^2)^(1/3) AU; arcsec = AU x parallax ({n['plx'] * 1000:.2f} "
                 f"mas, from the distance).")
        # the host row becomes the subsystem
        put(rA, "Role in system", f"subsystem: {n['star']} + {n['comp']}")
        put(rA, "Node type", "subsystem")
        put(rA, "Mass (M-sun)", round(m1 + m2, 4), f"INFERRED: {m1} ({n['star']}) + {m2} ({n['comp']}, a minimum "
                                                   "mass from the mass function; WEAK).", inferred=True)
        put(rA, "Mass basis (MSC)", "sum of the subsystem's masses")
        put(rA, "Star data source", f"Subsystem {n['star']} + {n['comp']}, added 30 Sep 2026 (companions.py); "
                                   f"{n['star']} carries what this row held as a single star.")
        for hd in STAR_ONLY:
            if hd in col and host_row[col[hd]] not in ("", None):
                put(rA, hd, "")
                blank_notes.append(a1(hd, rA))
        put(rA, "Barycentre from", n["star"])
        put(rA, "Barycentre offset (AU)", round(a * m2 / (m1 + m2), 6),
            f"WEAK: {n['comp']}'s mass is an inferred minimum mass.\nINFERRED: a x M_sec / (M_prim + M_sec) = {a} au "
            f"x {m2} / ({m1} + {m2}), from '{n['comp']}' (Separation (AU), Mass) and '{n['star']}' (Mass).",
            inferred=True)
        # the copy becomes the host star
        put(rS, "Star (component)", n["star"])
        put(rS, "MSC label", pa)
        put(rS, "Member of", n["host"])
        put(rS, "Hierarchy level", num(host_row[col["Hierarchy level"]]) + 1)
        # the companion
        put(rC, "Star (component)", n["comp"])
        put(rC, "Role in system", n["role"])
        put(rC, "MSC label", pc)
        put(rC, "Member of", n["host"])
        put(rC, "Hierarchy level", num(host_row[col["Hierarchy level"]]) + 1)
        for hd in STAR_ONLY + ["Star data source", "Mass basis (MSC)"]:
            if hd in col and hd not in ("Luminosity class", "HZ distance") and "band" not in hd:
                put(rC, hd, "")
                blank_notes.append(a1(hd, rC))
        put(rC, "Mass (M-sun)", m2, why_m, inferred=True)
        put(rC, "Mass basis (MSC)", "minimum mass, SB1 (inferred from the mass function; not in the MSC)")
        put(rC, "Star data source", f"Not in the MSC. Companion from {n['src']}. Mass INFERRED (a minimum mass); "
                                    "no class or luminosity on file, so no solvent band.")
        put(rC, "Separation from", n["star"])
        put(rC, "Orbit described", f"{n['star']} + {n['comp']}")
        put(rC, "Orbit source", n["orbit_source"])
        put(rC, "Separation (AU)", a, why_a, inferred=True)
        put(rC, "Separation (arcsec)", round(a * n["plx"], 6), why_a, inferred=True)
        put(rC, "Separation type", "semi-major axis")
        put(rC, "Separation source", f"INFERRED from Kepler's third law with the minimum mass (see the cell note); "
                                     f"orbit from {n['src']}.")
        put(rC, "Orbital period (d)", n["P"], f"SOURCE: {n['src']}.")
        put(rC, "Period basis", "orbit")
        put(rC, "Orbital eccentricity (e)", n["e"], f"SOURCE: {n['src']}.")
        put(rC, "Argument of periastron (deg)", n["omega"], f"SOURCE: {n['src']}.")
        put(rC, "Time of periastron (JD)", round(n["T"], 4), f"SOURCE: {n['src']}.")
        put(rC, "Argument of periastron refers to", f"primary ({pa})",
            "SOURCE: a spectroscopic orbit quotes the primary's omega (SB9 and Gaia DR3 conventions).")
        put(rC, "Detection (MSC)", n["detection"])
        put(rC, "Barycentre from", "")
        put(rC, "Barycentre offset (AU)", "")
        put(rC, STATUS, HYPO, f"WEAK: {n['doubt']}. Drawn hollow, as a candidate.")
        # every row of the system: star count and hierarchy
        members = [r for r, row in rows if row[col["System / Host"]] == sysname]
        # the host row is still a star in the sheet and becomes a subsystem; its two copies are the new stars
        n_stars = sum(1 for r in members if idx[r][col["Node type"]] == "star") - 1
        for r in members:
            expect.setdefault(a1("Star (component)", r), idx[r][col["Star (component)"]])
            put(r, "Stars in system", n_stars)
            put(r, "Hierarchy", n["hierarchy"])
        n["rows"] = [rA, rS, rC]
        n["members"] = members

    # ancestor masses and barycentre offsets, recomputed from the members' masses as they will stand
    def cur(r, hd):
        u = updates.get(a1(hd, r))
        return u[0][0] if u else idx[r][col[hd]]
    for n in plan:
        members = n["members"]
        name_row = {cur(r, "Star (component)"): r for r in members}
        subs = [r for r in members if cur(r, "Node type") == "subsystem"]
        for _ in range(4):                                    # up the tree, a level at a time
            for r in subs:
                kids = [x for x in members if cur(x, "Member of") == cur(r, "Star (component)")]
                ms = [num(cur(x, "Mass (M-sun)")) for x in kids]
                if len(kids) == 2 and None not in ms and abs(sum(ms) - num(cur(r, "Mass (M-sun)"))) > 1e-9:
                    put(r, "Mass (M-sun)", round(sum(ms), 4),
                        f"INFERRED: sum of its members' masses, {' + '.join(str(m) for m in ms)}, one of them the "
                        f"inferred minimum mass of {n['comp']} (WEAK).", inferred=True)
        for r in subs:
            prim = cur(r, "Barycentre from")
            if not prim or r == n["rows"][0]:
                continue
            sec = next((x for x in members if cur(x, "Separation from") == prim
                        and cur(x, "Member of") == cur(r, "Star (component)")), None)
            if sec is None:
                continue
            aa, ma, mb = num(cur(sec, "Separation (AU)")), num(cur(name_row[prim], "Mass (M-sun)")), \
                num(cur(sec, "Mass (M-sun)"))
            if None in (aa, ma, mb):
                continue
            off = round(aa * mb / (ma + mb), 6)
            if off != num(cur(r, "Barycentre offset (AU)")):
                put(r, "Barycentre offset (AU)", off,
                    f"INFERRED: a x M_sec / (M_prim + M_sec) = {aa} au x {mb} / ({ma} + {mb}), masses as revised by "
                    f"companions.py (30 Sep 2026) for {n['comp']}.", inferred=True)

    gs.update_cells(SID, updates, expect=expect)
    for s in range(0, len(orange), 200):
        gs.set_border(SID, orange[s:s + 200], gs.INFERRED_BORDER)
    wiped = [c for c in blank_notes if c not in orange]
    for s in range(0, len(wiped), 200):
        gs.set_border(SID, wiped[s:s + 200], gs.PLAIN_RULE, style="SOLID")
    gs.set_note(SID, {**{c: "" for c in blank_notes}, **notes})

    sp_lines = [
        "",
        "30 SEPTEMBER 2026: 'Planetless 4+ Stars' -- TWO SPECTROSCOPIC COMPANIONS ADDED AS HYPOTHETICAL STARS "
        "(companions.py).",
        "Writer: data/four_plus_stars/companions.py; log companions_log.json. Owner's decision: add both, drawn "
        "hollow and labelled 'hypothetical and model-inferred' in the new last column 'Drawing status' (blank = drawn "
        "as confirmed). Neither is in the MSC.",
    ] + [
        f"{n['comp']}: orbit from {n['src']} (P = {n['P']} d, e = {n['e']}, omega = {n['omega']}, K1 = {n['K1']} "
        f"km/s). Mass INFERRED, WEAK: minimum mass {n['m2']} M_sun from the mass function f(M) = {n['f']:.3e} "
        f"M_sun with M1 = {n['m1']} M_sun. Separation INFERRED from Kepler's third law: {n['a']} AU. Doubts: "
        f"{n['doubt']}. {n['host']} is now the subsystem {n['star']} + {n['comp']}; {n['star']} carries the star's "
        "data, and ancestor masses and barycentre offsets follow (orange). Confidence LOW. Verify: re-observe; "
        "check Gaia DR4 when released."
        for n in plan
    ]
    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    spm = next(s["properties"] for s in meta if s["properties"]["title"] == SP)
    lastsp = spm["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{lastsp}"])[f"{q(SP)}!A{lastsp}"][0][0].strip()
    start, end = lastsp + 1, lastsp + len(sp_lines)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": spm["sheetId"], "dimension": "ROWS", "length": len(sp_lines)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in sp_lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps({"title": title, "sp_rows": [start, end],
                               "added": [{k: v for k, v in n.items() if k != "members"} for n in plan],
                               "cells": {k: v[0][0] for k, v in updates.items()}, "orange": orange},
                              indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("done:", title, "S&P rows", start, end)


if __name__ == "__main__":
    main()
