# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GJ 229 B, the first methane brown dwarf, onto the planet tabs: Ba on Planets, Bb as its moon on Exomoons.

    python add_gj229_b.py          plan: print every write; touches nothing
    python add_gj229_b.py write    add the rows, notes, the Systems cells, provenance, rename

GJ 229's Systems row was left with no planet on file once GJ 229 b and GJ 229 A c went to Rejected candidates
(27 Sep 2026, likely activity), so the star had no system to open. Its well-known companion was never on file.

Under the owner's rule (docs/hybrasil-instructions.md section 6) a brown dwarf is a planet, and a brown dwarf that
orbits another is that planet's moon, as eps Ind Bb is eps Ind Ba's. GJ 229 B is a pair of brown dwarfs (Xuan et al.
2024), each far below the hydrogen-burning limit, so Ba is a Planets row round GJ 229 and Bb an Exomoons row round Ba.

Every number was read from the paper named beside it (the arXiv PDFs, 25 Nov 2026), none from memory or Wikipedia:

  Xuan et al. 2024, Nature 634, 1070 (arXiv:2410.11953), the discovery that B is double (VLTI/GRAVITY + VLT/CRIRES+):
    Ba 38.1 +/- 1.0 M-Jup, Bb 34.4 +/- 1.5 M-Jup; inner orbit P 12.134 +/- 0.003 d, a 0.0424 +/- 0.0004 AU,
    e 0.234 +/- 0.004, i 31.4 +/- 0.3 deg (frequentist column of its orbit table); total 72.5 +/- 1.3 M-Jup;
    ATMO 2020: Ba Teff 860 +/- 20 K, log L -5.41 +/- 0.04; Bb Teff 770 +/- 20 K, log L -5.58 +/- 0.04; age
    2.45 +/- 0.20 Gyr; closest types T7 (Ba) and T8 (Bb).
  Thompson et al. 2025, AJ 169, 193 (arXiv:2502.05359; doi 10.3847/1538-3881/adb4f2), Table 6, the outer orbit of the
    pair round A refitted with new Keck/NIRC2 astrometry: a 42.9 (+3.0/-2.4) AU, e 0.736 (+0.014/-0.011),
    P 349 (+37/-29) Julian yr, i 47.7 (+2.5/-2.9) deg, node 168.3 (+0.3/-0.4) deg, omega (of B) 132 +/- 5 deg,
    M_A 0.581 +/- 0.007 M-sun, M_B 71.7 +/- 0.6 M-Jup; mutual inclination of the two orbits 31 +/- 2.5 deg.
    Its refit of the inner orbit: P 12.1346 +/- 0.0011 d, e 0.2317 +/- 0.0025, Ba 37.7 +/- 1.1, Bb 33.4 +/- 1.0 M-Jup.
  Brandt et al. 2021 (arXiv:2109.07525), Table 11, the earlier outer orbit, of B as one body: a 33.3 (+0.4/-0.3) AU,
    e 0.851 (+0.002/-0.008), P 237.9 (+5.1/-4.6) yr, i 7.7 (+7.6/-4.4) deg, M_B 71.4 +/- 0.6 M-Jup.

The outer orbit written is Thompson et al.'s: the later fit, with more astrometry, by a team that includes the
discoverers. It differs from Brandt et al.'s well outside either's errors (43 vs 33 AU, e 0.74 vs 0.85, i 48 vs
8 deg), as Thompson et al. say themselves (Sect. 4.2); the earlier orbit is kept in the row's flags.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data" / "four_plus_stars"))
sys.path.insert(0, str(ROOT / "data" / "star_counts"))
from hybrasil.data import google_sheets as gs  # noqa: E402
import migrate_bds as mb  # noqa: E402  (Tab, add_rows: a template row's formulas, the values typed over them)
from fill import letter, q  # noqa: E402

PLAN = "write" not in sys.argv[1:]
SID, API = mb.SID, mb.API
SY, PN, EX, SP = mb.SY, mb.PN, mb.EX, mb.SP
LOG = HERE / "add_gj229_b_log.json"
DATE, ISO = "25 Nov 2026", "2026-11-25"
HOST = "GJ 229"
RULE = "docs/hybrasil-instructions.md section 6"

XUAN = "Xuan et al. 2024, Nature 634, 1070 (arXiv:2410.11953)"
THOMPSON = "Thompson et al. 2025, AJ 169, 193 (arXiv:2502.05359)"
BRANDT = "Brandt et al. 2021 (arXiv:2109.07525)"

BA_MJ, BB_MJ = 38.1, 34.4
OUT_A, OUT_E, OUT_P_YR = 42.9, 0.736, 349
OUT_P_D = round(OUT_P_YR * 365.25)                       # Julian years, as the paper's table says
IN_P, IN_A, IN_E = 12.134, 0.0424, 0.234


def main():
    sy, pn, ex = mb.Tab(SY, "System / Host"), mb.Tab(PN, "Planet"), mb.Tab(EX, "Exomoon")
    for t, key in ((pn, "Planet"), (ex, "Exomoon")):
        assert not [r for r in t.v[1:] if r and str(r[0]).startswith("GJ 229 B")], f"{t.title}: already there"
    sr = sy.find(HOST)
    srow = sy.row(sr)
    assert srow["Confirmed planets"] == 0 and srow["Planet masses (M-earth)"] == "", srow
    dist, cls, lum = srow["Distance (ly)"], srow["Stellar Class"], srow["Host luminosity (L-sun)"]
    # M-Jup in M-earth: the Planets tab's own constant, the one its Mass (M-Jup) column divides by.
    last = pn.last_data_row()
    mj = next(v for r in range(last + 1, last + 12) for v in [pn.row(r).get("Distance (ly)")]
              if isinstance(v, (int, float)) and 317 < v < 318.5)
    ba_me, bb_me = round(BA_MJ * mj, 1), round(BB_MJ * mj, 1)

    flags = (
        f"ADDED {DATE}: a brown dwarf is a planet under the model's rule ({RULE}). GJ 229 B, the first methane (T) "
        f"dwarf, is a pair of brown dwarfs, Ba and Bb ({XUAN}); this row is Ba, and Bb is its moon on Exomoons, as "
        f"eps Ind Bb is eps Ind Ba's. THE ORBIT IS THE PAIR'S round GJ 229 A, from {THOMPSON}, Table 6: a 42.9 "
        "(+3.0/-2.4) AU, e 0.736 (+0.014/-0.011), P 349 (+37/-29) Julian yr (written as 349 x 365.25 d). Elements "
        "the planet tabs have no columns for: i 47.7 (+2.5/-2.9) deg, ascending node 168.3 (+0.3/-0.4) deg, "
        "argument of periapsis of B 132 +/- 5 deg; the two orbits are inclined to each other by 31 +/- 2.5 deg. "
        f"EARLIER ORBIT, NOT USED: {BRANDT}, Table 11, fitting B as one body: a 33.3 (+0.4/-0.3) AU, e 0.851 "
        "(+0.002/-0.008), P 237.9 (+5.1/-4.6) yr, i 7.7 (+7.6/-4.4) deg. The two differ well outside their errors; "
        "Thompson et al. say so (Sect. 4.2) and theirs is the later fit, with more astrometry. The masses agree: "
        "71.7 +/- 0.6 (Thompson) and 71.4 +/- 0.6 M-Jup (Brandt) for the pair. No radius is written: none is "
        "measured. The system's two radial-velocity candidates, GJ 229 b and GJ 229 A c, stay on Rejected candidates.")
    source = (
        f"{XUAN}: resolved GJ 229 B into Ba and Bb with VLTI/GRAVITY and VLT/CRIRES+; Ba 38.1 +/- 1.0 M-Jup "
        "(dynamical), Teff 860 +/- 20 K and log(L/L-sun) -5.41 +/- 0.04 (ATMO 2020), closest type T7; system age "
        "2.45 +/- 0.20 Gyr from the same models; both far below the hydrogen-burning limit (about 70-73 M-Jup in the "
        f"models it cites). {THOMPSON}: the outer orbit (flags), and Ba 37.7 +/- 1.1 M-Jup on its own fit. "
        f"{BRANDT}: the pair's total, 71.4 +/- 0.6 M-Jup, and A's mass, 0.579 +/- 0.007 M-sun.")
    spec = {
        "Planet": "GJ 229 Ba", "Host system (primary star)": HOST, "Planet-host star": HOST, "Planet-host class": cls,
        "Host luminosity (L-sun)": lum, "Mass (M-earth)": ba_me, "Mass type": "Mass (dynamical)",
        "Orbital period (d)": OUT_P_D, "Semi-major axis (au)": OUT_A, "Eccentricity": OUT_E,
        "Orbit data source / flags": flags, "Confidence tier": "confirmed",
        "Source / discovery reference": source, "Vetting date / last updated": ISO, "Catalogue distance (ly)": dist,
        "Detection method": "Imaging; interferometry (VLTI/GRAVITY) and RV (VLT/CRIRES+) for the pair",
        "Orbit Direction": "Prograde (assumed)",
    }
    # The host luminosity is the Systems row's, the one the model draws GJ 229's bands from. The Rejected candidates
    # rows of GJ 229 b and A c carry another (0.043), with habitable-zone limits computed from it, so those limits
    # are not carried here: the disagreement is recorded in the flags and left for the owner.
    rj = mb.Tab("Rejected candidates", "Planet")
    lum_rejected = rj.row(rj.find("GJ 229 b"))["Host luminosity (L-sun)"]
    spec["Orbit data source / flags"] += (
        f" HOST LUMINOSITY: {lum} L-sun, the Systems row's; the Rejected candidates rows of GJ 229 b and A c carry "
        f"{lum_rejected}, unreconciled, so no habitable-zone limits are written on this row.")
    notes = {
        "Mass (M-earth)": f"Converted: {BA_MJ} M-Jup ({XUAN}) x {mj} M-earth per M-Jup = {ba_me}.",
        "Orbital period (d)": f"Converted: {OUT_P_YR} Julian yr ({THOMPSON}, Table 6) x 365.25 = {OUT_P_D} d.",
    }
    moon_flags = (
        f"ADDED {DATE}: a brown dwarf is a planet, and this one orbits the brown dwarf GJ 229 Ba, so it is that "
        f"planet's moon under the model's rule ({RULE}). Orbit of Bb relative to Ba, from {XUAN} (the frequentist "
        "column of its orbit table): P 12.134 +/- 0.003 d, a 0.0424 +/- 0.0004 AU, e 0.234 +/- 0.004, i 31.4 +/- "
        "0.3 deg. The pair's orbit round GJ 229 A is on Ba's Planets row.")
    moon_source = (
        f"{XUAN}: Bb 34.4 +/- 1.5 M-Jup (dynamical), Teff 770 +/- 20 K and log(L/L-sun) -5.58 +/- 0.04 (ATMO 2020), "
        "closest type T8; K-band flux ratio Bb/Ba 0.47 +/- 0.03.")
    moon_alt = (f"{THOMPSON}, an independent refit of the same data: P 12.1346 +/- 0.0011 d, e 0.2317 +/- 0.0025, "
                "i 31.8 +/- 0.4 deg, Ba 37.7 +/- 1.1 and Bb 33.4 +/- 1.0 M-Jup.")
    moon = {
        "Planet": "GJ 229 Bb", "Host system (primary star)": HOST, "Catalogue distance (ly)": dist,
        "Mass type": "Mass (dynamical)", "Orbital period (d)": IN_P, "Semi-major axis (au)": IN_A,
        "Eccentricity": IN_E, "Detection method": "Interferometry (VLTI/GRAVITY) and RV (VLT/CRIRES+)",
        "Confidence tier": "confirmed", "Source / discovery reference": moon_source,
        "Orbit data source / flags": "a brown dwarf is a planet",        # replaced below, after moon_spec()
    }
    sy_upd = {sy.a1("Confirmed planets", sr): 1,
              sy.a1("Planet masses (M-earth)", sr): f"GJ 229 Ba:{ba_me:.0f} ({BA_MJ} MJ, brown dwarf)",
              sy.a1("Mass type", sr): "Mass"}
    sy_exp = {sy.a1("Confirmed planets", sr): 0, sy.a1("Planet masses (M-earth)", sr): "", sy.a1("Mass type", sr): ""}
    sp = ["", f"GJ 229 B ADDED, {DATE.upper()} (data/gj229/add_gj229_b.py)",
          "  GJ 229's Systems row had no planet on file: GJ 229 b and GJ 229 A c are on Rejected candidates (likely "
          "activity, Deslieres et al. 2025). Its brown-dwarf companion was never entered. Under the owner's rule of "
          f"7 Oct 2026 ({RULE}) a brown dwarf is a planet, and one that orbits another is its moon.",
          f"  GJ 229 Ba -> Planets (round GJ 229, confirmed): {BA_MJ} +/- 1.0 M-Jup ({XUAN}); orbit of the Ba+Bb pair "
          f"round A from {THOMPSON}, Table 6: a {OUT_A} AU, e {OUT_E}, P {OUT_P_YR} Julian yr = {OUT_P_D} d.",
          f"  GJ 229 Bb -> Exomoons (round GJ 229 Ba, confirmed): {BB_MJ} +/- 1.5 M-Jup; P {IN_P} d, a {IN_A} AU, "
          f"e {IN_E} ({XUAN}).",
          f"  NOT USED, kept in Ba's flags: the earlier outer orbit of {BRANDT}, Table 11 (a 33.3 AU, e 0.851, "
          "P 237.9 yr, i 7.7 deg), which fits B as one body and disagrees with Thompson et al. well outside the "
          "errors. HOW TO VERIFY: open each paper's table named above; every number was read from the arXiv PDF on "
          f"{DATE}, none from memory, Wikipedia or an archive. CONFIDENCE: HIGH for the masses and the inner orbit "
          "(two analyses agree); MEDIUM for the outer orbit (under a fifth of it observed, and two fits disagree).",
          f"  Systems row GJ 229: Confirmed planets 0 -> 1, Planet masses and Mass type filled. No cell is inferred: "
          "the two notes on Ba's row record unit conversions only. No radius is written for either body."]

    print(f"Systems row {sr}: {srow['System / Host']}  dist {dist}  class {cls}  L {lum};  M-Jup = {mj} M-earth")
    print("Planets, after row", last, "->", json.dumps(spec, ensure_ascii=False, indent=1))
    print("Exomoons, after row", ex.last_data_row(), "-> GJ 229 Bb", bb_me, "M-earth", moon_alt)
    print("Systems:", sy_upd)
    for t in (pn, ex):
        r = t.last_data_row()
        print(f"\n{t.title}: last data row {r} = {t.row(r)[t.h[0]]!r}; its formula cells:")
        for h in t.h:
            if str(t.formula(r, h)).startswith("="):
                print("   ", h, "=", str(t.formula(r, h))[:110])
        print("    typed cells of that row that the new row would blank unless given:",
              [h for h in t.h if t.row(r)[h] not in ("", None) and not str(t.formula(r, h)).startswith("=")
               and h not in spec])
    if PLAN:
        print("\nPLAN only. Run with 'write' to apply.")
        return

    props = {s["properties"]["title"]: s["properties"] for s in
             API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}
    log = {"planet_rows": {}, "date": ISO}
    mb.add_rows(PN, [((PN, HOST, "", PN, "GJ 229 Ba", HOST, "confirmed"), spec, {}, notes, {})], props, log)
    facts = {"mass_sun": BB_MJ / mb.MJ_PER_M_SUN}
    mb.add_rows(EX, [((EX, HOST, "", EX, "GJ 229 Bb", "GJ 229 Ba", "confirmed"), moon, {}, {}, facts)], props, log)

    # Fix-ups the shared writer does not know about.
    pn2, ex2 = mb.Tab(PN, "Planet"), mb.Tab(EX, "Exomoon")
    pr, er = pn2.find("GJ 229 Ba"), ex2.find("GJ 229 Bb")
    fix = {ex2.a1("Mass (M-earth)", er): bb_me, ex2.a1("Mass (M-Jup)", er): BB_MJ,
           ex2.a1("Orbit data source / flags", er): moon_flags, ex2.a1("Alternative solution", er): moon_alt,
           ex2.a1("Date added", er): ISO}
    # A radius copied in with the template row's formula is not this body's: none is measured.
    for h in ("Radius (R-Jup)",):
        f = str(pn2.formula(pr, h))
        if f.startswith("=") and "$" + letter(pn2.col["Radius (R-earth)"]) not in f:
            fix[pn2.a1(h, pr)] = ""
    gs.update_cells(SID, fix, expect={pn2.a1("Planet", pr): "GJ 229 Ba", ex2.a1("Exomoon", er): "GJ 229 Bb"})
    gs.update_cells(SID, sy_upd, expect=sy_exp)

    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{end}"])[f"{q(SP)}!A{end}"][0][0].strip()
    sp0, sp1 = end + 1, end + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{sp0}:A{sp1}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (sp0, sp1)})
    log.update(planets_row=pr, exomoons_row=er, systems_row=sr, sp_rows=[sp0, sp1],
               title=gs.rename_workbook(None, gs.versioned_title()))
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("done:", json.dumps(log, ensure_ascii=False))


if __name__ == "__main__":
    main()
