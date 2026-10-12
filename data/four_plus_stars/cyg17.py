# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""17 Cyg A-B: take Romanenko et al. 2025's AMP orbit in place of the face-on circular model; note HR 1099 A-B.

    python cyg17.py          plan: print every cell it would change
    python cyg17.py write    write, re-border, note, provenance, rename

17 Cyg A-B (STF 2580 AB, ADS 12913) had no measured orbit, so infer.py drew it face-on and circular at its projected
separation. ORB6's only orbit, Izmailov 2019 (Astron. Lett. 45, 30; 7905 yr, a = 40.16"), needs 9.5 M_sun at the tab's
parallax, 4.7 times the tab's 2.02: Izmailov's catalogue fits the observed arc with no mass constraint, and the arc
is ~4 degrees long. The Pulkovo AMP catalogue (Romanenko, Kiyaeva, Izmailov, Shakht & Gorshanov 2025, Astronomy
Reports 69, 398; VizieR J/other/ARep/69.398, table3) fits the pair by the apparent-motion-parameters method from
Gaia DR3 positions, motions and radial velocities, with the mass sum fixed at 2.02 M_sun -- the tab's own. It
gives two solutions (beta = +59 and -59 degrees: B behind or in front of the sky plane through A) whose
ephemerides coincide over every observation from 1822 to 2019; the paper does not choose. The owner chose the first
listed, solution 1 (1 Oct 2026); solution 2 is written into the notes and the provenance entry.

HR 1099 A-B (STF 422) keeps the MSC's Hopmann 1964 orbit (owner's decision, 1 Oct 2026); its discrepancies are
recorded in a note on Orbit source and in the provenance entry, and nothing else changes.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)
from build import GREY_RULE  # noqa: E402  (this tab's plain rule; gs.PLAIN_RULE is black)

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
FP, SP = "Planetless 4+ Stars", "Sources & Provenance"
YR = 365.25

# Romanenko et al. 2025, table3, I = 46 (19464+3344 AB), k = 1 and k = 2. P and Tp in years, a in arcsec.
SOL1 = dict(beta=59, P=24195, eP=(10131, 5440), a=50.475, ea=(13.304, 7.824), i=119.9, ei=1.2, node=141.4,
            enode=(6.4, 6.1), Tp=-1473, eTp=(327, 370), e=0.672, ee=(0.062, 0.051), w=308.9, ew=5.1)
SOL2 = dict(beta=-59, P=24195, a=50.475, i=114.9, node=17.7, Tp=6259, e=0.479, w=48.3)
M_TOT = 2.02                                 # Romanenko's mass sum, = the tab's 1.31 + 0.71
PLX_MAS = 47.85                              # the tab's parallax for 17 Cyg (MSC), used for every au on its rows

SRC = ("Romanenko, Kiyaeva, Izmailov, Shakht & Gorshanov 2025, Astronomy Reports 69, 398 (Pulkovo catalogue of AMP "
       "orbits; VizieR J/other/ARep/69.398, table3, 19464+3344 AB, solution k = 1)")
SOL2_TXT = (f"Solution 2 (beta = {SOL2['beta']}, B on the other side of the sky plane) fits every observation as well: "
            f"i = {SOL2['i']}, node = {SOL2['node']}, e = {SOL2['e']}, omega = {SOL2['w']}, Tp = {SOL2['Tp']}; "
            "same P and a. The paper does not choose; the owner took solution 1 (1 Oct 2026).")
WAS_MODEL = "Was face-on circular (infer.py model, orange)."


def jd_of_year(y):
    """JD of a Julian-year epoch; Romanenko's Tp is given to the year, so the year convention does not matter."""
    return 2451545.0 + (y - 2000.0) * YR


A_AU = round(SOL1["a"] / (PLX_MAS / 1000.0), 5)
P_D = round(SOL1["P"] * YR, 2)
T_JD = round(jd_of_year(SOL1["Tp"]), 2)
KEPLER = A_AU ** 3 / SOL1["P"] ** 2 / M_TOT
OFFSET = round(A_AU * 0.71 / (1.31 + 0.71), 6)

# 17 Cyg B: header -> (expected current value, new value, note, border: None keeps it, else the colour to set)
B_CHANGES = {
    "Orbital period (d)": (3279071.457, P_D,
                           f"SOURCE: {SRC}; P = {SOL1['P']} +{SOL1['eP'][0]} / -{SOL1['eP'][1]} yr, x 365.25. "
                           f"Fitted with the mass sum fixed at {M_TOT} M_sun: a^3/P^2 at this tab's parallax gives "
                           f"{KEPLER * M_TOT:.2f} M_sun. {WAS_MODEL} {SOL2_TXT}", GREY_RULE),
    "Period basis": ("model-inferred (face-on, circular)", "orbit", f"SOURCE: {SRC}.", GREY_RULE),
    "Separation (AU)": (546.03971, A_AU,
                        f"INFERRED: au = {SOL1['a']}\" / parallax ({PLX_MAS} mas, the MSC's, as for every 17 Cyg "
                        f"row); the semi-major axis in arcsec is {SRC}, +{SOL1['ea'][0]} / -{SOL1['ea'][1]}\". "
                        "Was the projected separation, 546.03971 au.", None),
    "Separation (arcsec)": (26.128, SOL1["a"], f"SOURCE: {SRC}. Was the projected separation, 26.128\" (MSC).", None),
    "Separation type": ("projected", "semi-major axis", None, None),
    "Separation source": (None, f"{SRC}: orbit semi-major axis {SOL1['a']}\"; au = arcsec / parallax ({PLX_MAS} mas)",
                          None, None),
    "Orbit source": ("", "Romanenko+ 2025 ARep 69, 398 AMP sol. 1",
                     f"SOURCE: {SRC}. AMP method: an orbit from one epoch's relative position, motion and radial "
                     "velocity (Gaia DR3), checked against every observation (136, 1822-2019). The arc observed is "
                     "about 4 degrees, so P is uncertain by 40% (the paper's largest). ORB6's only orbit, "
                     "Izmailov 2019 (7905 yr, 40.16\"), needs 9.5 M_sun at this parallax and was not taken.",
                     None),
    "Orbital eccentricity (e)": (0, SOL1["e"], f"SOURCE: {SRC}; e = {SOL1['e']} +{SOL1['ee'][0]} / "
                                               f"-{SOL1['ee'][1]}. {WAS_MODEL} {SOL2_TXT}", GREY_RULE),
    "Inclination (deg)": (0, SOL1["i"], f"SOURCE: {SRC}; i = {SOL1['i']} +- {SOL1['ei']}. {WAS_MODEL} {SOL2_TXT}",
                          GREY_RULE),
    "Ascending node (deg)": (0, SOL1["node"], f"SOURCE: {SRC}; node = {SOL1['node']} +{SOL1['enode'][0]} / "
                                              f"-{SOL1['enode'][1]}, unambiguous: the AMP fit uses the measured "
                                              f"relative radial velocity. {WAS_MODEL} {SOL2_TXT}", GREY_RULE),
    "Argument of periastron (deg)": (0, SOL1["w"], f"SOURCE: {SRC}; omega = {SOL1['w']} +- {SOL1['ew']} (the "
                                                   f"paper's 'longitude of periastron', counted from the node). "
                                                   f"{WAS_MODEL} {SOL2_TXT}", GREY_RULE),
    "Argument of periastron refers to": ("secondary (B relative to A)", "secondary (B relative to A)",
                                         f"SOURCE: {SRC} convention: the AMP orbit is B's motion relative to A.",
                                         GREY_RULE),
    "Time of periastron (JD)": (5114347.7336, T_JD,
                                f"SOURCE: {SRC}; Tp = year {SOL1['Tp']} (astronomical; 1474 BC) "
                                f"+{SOL1['eTp'][0]} / -{SOL1['eTp'][1]} yr, converted as JD = 2451545.0 + 365.25 x "
                                f"(year - 2000). {WAS_MODEL} {SOL2_TXT}", GREY_RULE),
}
AB_OFFSET = (191.924849, OFFSET,
             f"INFERRED: a x M_sec / (M_prim + M_sec) = {A_AU} au x 0.71 / (1.31 + 0.71), from '17 Cyg B' "
             "(Separation (AU), Romanenko et al. 2025's semi-major axis, cyg17.py, 1 Oct 2026; Mass) and '17 Cyg A' "
             "(Mass). The barycentre of 17 Cyg AB lies this far from 17 Cyg A, on the line to 17 Cyg B. Mass bases: "
             "17 Cyg A estimated from absolute magnitude (MSC), 17 Cyg B estimated from absolute magnitude (MSC).")

HR1099_SOURCE = "VB6_Hop1964b STF_422 Gr.5"
HR1099_NOTE = (
    "DISCREPANCIES (recorded 1 Oct 2026, cyg17.py; orbit kept by the owner's decision): "
    "(1) ORB6 (version of 2026-07-09) no longer carries Hopmann 1964 for STF 422; its only orbit is Izmailov 2019 "
    "(Astron. Lett. 45, 30), grade 4: P = 1210 yr, a = 9.912\", which at this tab's parallax (33.98 mas) needs "
    "17 M_sun against the tab's 3.03 (x5.6); Izmailov's unweighted solution (1391 yr, 12.82\") needs 28. Izmailov "
    "fits the arc with no mass constraint, so neither was taken. "
    "(2) Hopmann's orbit (2101 yr, 8.023\") gives 2.98 M_sun, but orbits of that era often took the distance from "
    "assumed masses, so the agreement may be built in. It still places B at 6.70\", PA 272.9 at J2016.0, against "
    "6.71\", PA 274.2 from Izmailov's ephemeris of the observations. "
    "(3) T = 1900.0 exactly (the MSC's value) -- a round epoch, not checked against Hopmann 1964 itself. "
    "(4) Grade 5 (indeterminate): only part of the orbit has been observed.")


def main():
    v = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A1:CZ2000", valueRenderOption="UNFORMATTED_VALUE"
                         ).execute()["values"]
    h = v[0]
    col = {k: i for i, k in enumerate(h)}

    def row_of(name):
        hits = [r for r, row in enumerate(v[1:], start=2) if len(row) > 1 and row[col["Star (component)"]] == name]
        assert len(hits) == 1, (name, hits)
        return hits[0]

    rb, rab, rhr = row_of("17 Cyg B"), row_of("17 Cyg AB"), row_of("HR 1099 B")
    a1 = lambda hd, r: f"{q(FP)}!{letter(col[hd])}{r}"  # noqa: E731
    cell = {hd: a1(hd, rb) for hd in B_CHANGES}
    off_cell, hr_cell = a1("Barycentre offset (AU)", rab), a1("Orbit source", rhr)

    olds = {(rb, hd): old for hd, (old, *_) in B_CHANGES.items() if old is not None}
    olds[(rab, "Barycentre offset (AU)")] = AB_OFFSET[0]
    olds[(rhr, "Orbit source")] = HR1099_SOURCE
    for (r, hd), old in olds.items():
        got = (v[r - 1] + [""] * len(h))[col[hd]]
        assert got == old, (r, hd, got, old)
    expect = {a1(hd, r): old for (r, hd), old in olds.items()}
    assert str(v[rb - 1][col["Separation source"]]).startswith("MSC "), v[rb - 1][col["Separation source"]]
    assert 0.95 < KEPLER < 1.05, KEPLER

    values = {cell[hd]: [[new]] for hd, (_, new, *_) in B_CHANGES.items()}
    values[off_cell] = [[AB_OFFSET[1]]]
    notes = {cell[hd]: note for hd, (_, _, note, _) in B_CHANGES.items() if note}
    notes[off_cell] = AB_OFFSET[2]
    notes[hr_cell] = HR1099_NOTE
    grey = [cell[hd] for hd, (*_, border) in B_CHANGES.items() if border == GREY_RULE]

    sp = sp_entry()
    if PLAN:
        print(f"17 Cyg B (row {rb}), 17 Cyg AB (row {rab}), HR 1099 B (row {rhr});  a^3/P^2 / M = {KEPLER:.3f}")
        for hd, (old, new, note, border) in B_CHANGES.items():
            print(f"  {cell[hd]:28} {hd:34} {str(old)[:40]!s:>40} -> {new}"
                  f"{'   [orange -> grey]' if border else ''}\n      note: {note}")
        print(f"  {off_cell:28} Barycentre offset (AU) {AB_OFFSET[0]} -> {AB_OFFSET[1]}   [stays orange]"
              f"\n      note: {AB_OFFSET[2]}")
        print(f"  {hr_cell:28} note only: {HR1099_NOTE}")
        print("\n".join(sp))
        return

    gs.update_cells(SID, values, expect=expect)
    gs.set_border(SID, grey, GREY_RULE, style="SOLID")
    gs.set_note(SID, notes)

    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    spm = next(s["properties"] for s in meta if s["properties"]["title"] == SP)
    last = spm["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{last}"])[f"{q(SP)}!A{last}"][0][0].strip()
    start, end = last + 1, last + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": spm["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    print("done:", {"rows": [rb, rab, rhr], "sp_rows": [start, end], "title": title})


def sp_entry():
    return [
        "",
        "1 OCTOBER 2026: 'Planetless 4+ Stars' -- 17 Cyg A-B TAKES ROMANENKO ET AL. 2025'S AMP ORBIT; HR 1099 A-B'S "
        "ORBIT DISCREPANCIES RECORDED (cyg17.py).",
        f"17 Cyg B (STF 2580 AB, ADS 12913): Orbital period, Period basis, Separation (AU, arcsec, type, source), "
        f"Orbit source, e, i, node, omega, omega convention and T: {SRC}. P = {SOL1['P']} (+{SOL1['eP'][0]} / "
        f"-{SOL1['eP'][1]}) yr, a = {SOL1['a']}\" = {A_AU} au at {PLX_MAS} mas, e = {SOL1['e']}, i = {SOL1['i']}, "
        f"node = {SOL1['node']}, omega = {SOL1['w']}, Tp = year {SOL1['Tp']} (1474 BC) = JD {T_JD}. Fitted with "
        f"the mass sum fixed at {M_TOT} M_sun, the tab's. Replaces infer.py's face-on circular model at the "
        "projected separation (26.128\", 546.04 au); the model cells' orange borders are now the tab's grey rule, "
        "except Separation (AU), which stays orange (arcsec / parallax). "
        f"{SOL2_TXT} Confidence LOW-MEDIUM: the observed arc is ~4 degrees; P is uncertain by 40%. "
        "ORB6's only orbit for the pair, Izmailov 2019 (7905 yr, 40.16\"), needs 9.5 M_sun (x4.7) and was not "
        "taken. Verify: izmccd.puldb.ru/vds9/table3.dat, I = 46.",
        f"  17 Cyg AB Barycentre offset recomputed for the new separation: {AB_OFFSET[0]} -> {OFFSET} au (orange).",
        "HR 1099 B (STF 422): orbit unchanged (VB6_Hop1964b, owner's decision); its discrepancies are noted on "
        "Orbit source: ORB6 now carries only Izmailov 2019 (1210 yr, 9.912\", grade 4), which needs 17 M_sun "
        "(x5.6); Hopmann's agreement with the masses may be built in; T = 1900.0 exactly; grade 5.",
        "  iot UMa BC (HJ 2477 A,BC) also unchanged: ORB6's Izmailov 2019 (486 yr, 8.31\") needs 7.7 M_sun (x2.3); "
        "the tab's Zhuchkov et al. 2012 (Astronomy Reports 56, 512) orbit is an AMP fit with the masses fixed.",
    ]


if __name__ == "__main__":
    main()
