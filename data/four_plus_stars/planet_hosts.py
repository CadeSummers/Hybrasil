# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Take the two planet hosts off Planetless 4+ Stars, fold their extra star into Multi-stars, file refuted claims.

    python planet_hosts.py          plan: print every write; touches nothing
    python planet_hosts.py write    write them, note them on Sources & Provenance and Legend & Notes, rename

A check of the tab on 2 October 2026 (catalogue cross-match plus a literature search, every claim cited below)
found confirmed planets in two of its 82 systems, both already on the Systems, Planets and Multi-stars tabs under
their HD names: CD-77 1092 = HD 207496 and GJ 118.2 = HD 18143. The owner's choices for the merge:

- HD 18143: the tab's GJ 118.2 Ab (MSC "perturbed motion suspected", mass a typical-companion guess) is not
  carried over -- most likely it is the astrometric signal of planet c. A note on the host row says so.
- HD 207496: the tab's CD-77 1092 Ab drew a Gaia DR3 orbit that belongs to the companion, not the primary
  (research.py matched source 6356417496318028928, which is HD 207496 B, to Aa). Ab is dropped; the orbit
  becomes HD 207496 Bb, B's companion, and the system becomes three stars.

Every value write is guarded by `expect`; rows are found by name, never by number.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
PL, MS, SY, RJ = "Planetless 4+ Stars", "Multi-stars within 100 ly", "Systems within 100 ly", "Rejected candidates"
SP, LG = "Sources & Provenance", "Legend & Notes"
LOG = HERE / "planet_hosts_log.json"
DATE = "2 October 2026"
MOVED = {"GJ 118.2": "HD 18143", "CD-77 1092": "HD 207496"}

# HD 207496 Bb: Gaia DR3 nss_two_body_orbit, OrbitalTargetedSearch, source 6356417496318028928 (= HD 207496 B,
# TIC 290348382, G 10.84, RUWE 37.8). Mass: the lower bound of Gaia DR3 binary_masses (Orbital+M1), whose range is
# 0.199-0.645 with M1 = 0.557. Separation: Kepler's third law with this tab's B mass (0.531) and that lower bound.
BB = dict(period_d=1048.5689, period_err=6.3803, ecc=0.406, m2=0.199, m2_hi=0.645, m1=0.531, a_au=1.8188,
          a_hi=2.1321, source_id="6356417496318028928")
BB_SOURCE = (f"Gaia DR3 nss_two_body_orbit, OrbitalTargetedSearch (unvalidated), source_id {BB['source_id']} = "
             f"HD 207496 B: P = {BB['period_d']} +/- {BB['period_err']} d, e = {BB['ecc']}; a from Kepler's third law "
             f"(see the note)")
BB_DATA = (f"UNSEEN COMPANION of HD 207496 B, known only from Gaia DR3's orbit for B (source_id {BB['source_id']}). "
           f"MASS: {BB['m2']} M-sun is the lower bound of Gaia DR3 binary_masses (combination 'Orbital+M1': m2 "
           f"{BB['m2']}-{BB['m2_hi']}, M1 0.557), i.e. a dark companion; a luminous one is heavier. This orbit was "
           "previously misattributed to the primary as 'CD-77 1092 Ab' on the Planetless 4+ Stars tab, which matched "
           "B's Gaia source to Aa; it is B's (B's RUWE of 37.8 already marked it as unresolved). Added "
           f"{DATE}.")
BB_SEP_NOTE = (f"WEAK: rests on Gaia's lower-bound mass, a dark companion.\nINFERRED: a = ((M1 + M2) P^2)^(1/3) with "
               f"M1 = {BB['m1']} (HD 207496 B, this tab), M2 = {BB['m2']} (Gaia DR3 binary_masses lower bound), "
               f"P = {BB['period_d']} d. At Gaia's upper bound ({BB['m2_hi']}) a = {BB['a_hi']} AU.")
NOTE_18143 = ("The MSC (WDS 02556+2652, as GJ 118.2) also suspects an inner companion Ab from perturbed motion; it is "
              "not counted here. Most likely it is the astrometric signal of planet c (10.0 +/- 1.9 MJ true, ~17.5 "
              "AU, from RV plus Hipparcos-Gaia astrometry; Feng et al. 2022, ApJS 262, 21, "
              "doi:10.3847/1538-4365/ac7e57). This system was on Planetless 4+ Stars as GJ 118.2 until "
              f"{DATE}.")
NOTE_207496 = ("3 stars since " + DATE + ": HD 207496, B and Bb (B's unseen companion, from Gaia DR3's orbit for B). "
               "This system was on Planetless 4+ Stars as CD-77 1092 until then; that tab's Ab, which used B's Gaia "
               "orbit for the primary, was dropped.")

# The refuted claims, for Rejected candidates.  Host system is the Planetless tab's name, so the tab files each
# claim under the system it was checked in; 'Planet-host star' names the sheet component and the catalogue name.
REJECTED = [
    dict(planet="HD 131977 b", system="GJ 570", comp="GJ 570 A", hd="HD 131977", orbits="Yes", mj=0.75,
         mtype="Msini (as listed)", period=None, desig="HR 5568 b", method="Astrometry (Hipparcos) + RV",
         ref="Listed as HR 5568 b, 0.75 MJ at ~1 AU, in Sudarsky et al. 2000, ApJ 538, 885, Table 2a; from a "
             "Hipparcos astrometric candidate (Bernstein 1997) and a possible K ~ 50 m/s RV variation (Kurster "
             "et al. 1999), as quoted by the refuting paper",
         why="Refuted: Endl, Kurster & Els 2000, A&A 362, 585 (2000A&A...362..585E): 'a close-by brown dwarf "
             "companion (and even a giant planet) can be excluded'; RV rms 7.7 m/s, and Lick found the star "
             "constant (Cumming et al. 1999). Laliotis et al. 2023, AJ (doi:10.3847/1538-3881/acc067): only a "
             "linear trend."),
    dict(planet="HD 53680 B", system="GJ 264.1", comp="GJ 264.1 Ca", hd="HD 53680", orbits="No", mj=None,
         mtype="True mass 0.22 +/- 0.02 M-sun (a star)", period=1688.6, desig="HD 53680 B",
         method="RV (CORALIE)", ref="CORALIE brown-dwarf candidate, as reviewed by Sahlmann et al. 2011",
         why="Not substellar: Hipparcos astrometry gives i = 163.6 deg, so the companion is a 0.22 +/- 0.02 M-sun "
             "star (Sahlmann et al. 2011, A&A 525, A95, doi:10.1051/0004-6361/201015427). It is this sheet's "
             "GJ 264.1 Cb."),
    dict(planet="HD 18445 B", system="GJ 120.1", comp="GJ 120.1 Ca", hd="HD 18445", orbits="Yes", mj=44,
         mtype="Msini; true mass 0.176 M-sun (Hipparcos)", period=554.6, desig="HD 18445 B", method="RV",
         ref="RV brown-dwarf candidate, m sin i 0.042 M-sun, as tested by Halbwachs et al. 2000",
         why="Not substellar: Hipparcos astrometric true mass 0.176 M-sun (Halbwachs et al. 2000, A&A 355, 581, "
             "2000A&A...355..581H; Zucker & Mazeh 2001 also found it stellar). It is this sheet's GJ 120.1 Cb."),
    dict(planet="HD 283750 b", system="GJ 171.2", comp="GJ 171.2 Aa", hd="HD 283750", orbits="Yes", mj=50,
         mtype="Msini (old estimate)", period=1.788, desig="HD 283750 b",
         method="RV", ref="Brown-dwarf and planet candidate lists of the early 2000s (SIMBAD 'HD 283750b', type "
                          "Pl?); minimum mass ~50 MJ in Reffert & Quirrenbach 2011, Table 1",
         why="Stellar: it is the 1.79-day single-lined companion, this sheet's GJ 171.2 Ab. Reffert & Quirrenbach "
             "2011, A&A 527, A140 (doi:10.1051/0004-6361/201015861): 'probably formed as a close stellar binary "
             "system, rather than as a primary star with a low-mass substellar companion'; mass estimate "
             "0.128 +/- 0.037 M-sun (Glebocki & Stawikowski 1995)."),
    dict(planet="VB 8 B", system="GJ 644", comp="GJ 644 F", hd="vB 8", orbits="No", mj=None, mtype="",
         period=None, desig="VB 8 B (vB 8 b)", method="Infrared speckle interferometry",
         ref="McCarthy, Probst & Low 1985, ApJ 290, L9 (1985ApJ...290L...9M)",
         why="Not confirmed: Perrier & Mariotti 1987, ApJ 312 (page not verified) is quoted in secondary sources "
             "as showing it was a background star; it is generally accepted that VB 8 b does not exist. Source "
             "confidence MEDIUM: the refutation was read through secondary sources."),
    dict(planet="HD 13507 B (single-companion solution)", system="BD+39 496", comp="BD+39 496 Ba", hd="HD 13507",
         orbits="Yes", mj=52, mtype="Msini (Perrier et al. 2003; 67 in Wilson et al. 2006, as cited by Grandjean "
                                      "et al. 2021)", period=None, desig="HD 13507 b (single)", method="RV",
         ref="Perrier et al. 2003; Wilson et al. 2006, as cited by Grandjean et al. 2021",
         why="Refuted as a single companion: Grandjean et al. 2021, A&A 650, A39 (arXiv:2106.10754): 'We refute "
             "the HD13507 single brown dwarf companion solution and propose a double BD companion solution' (b 20 "
             "MJ min, P 3029.5 d; c 30 MJ min, P 4416.5 d), to be 'taken with caution'. Named so as not to block "
             "that newer HD 13507 b."),
]
MJ_TO_ME = 317.828


def values(tab, how="UNFORMATTED_VALUE"):
    return API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:DZ3000", valueRenderOption=how
                            ).execute().get("values", [])


def main():
    props = {s["properties"]["title"]: s["properties"] for s in
             API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}
    pl, ms, sy, rj = values(PL), values(MS), values(SY), values(RJ)
    ph, mh, shh, rh = pl[0], ms[0], sy[0], rj[0]
    pc, mc, sc, rc = ({h: i for i, h in enumerate(x)} for x in (ph, mh, shh, rh))
    cell = lambda row, c: row[c] if c < len(row) else ""

    # 1. Planetless rows of the two systems: contiguous blocks, by name.
    blocks = {}
    for name in MOVED:
        rr = [i + 1 for i, r in enumerate(pl) if r and r[0] == name]
        assert rr and rr == list(range(rr[0], rr[-1] + 1)), (name, rr)
        blocks[name] = rr
    pl_rows = {cell(r, pc["Star (component)"]): r for r in pl[1:] if r}

    # 2. Multi-stars: HD 207496's rows, and HD 18143's host.
    m207 = [i + 1 for i, r in enumerate(ms) if r and r[0] == "HD 207496"]
    m181 = [i + 1 for i, r in enumerate(ms) if r and r[0] == "HD 18143"]
    assert len(m207) == 2 and len(m181) == 3, (m207, m181)
    b_row = next(rr for rr in m207 if ms[rr - 1][mc["Star (component)"]] == "HD 207496 B")
    host207 = next(rr for rr in m207 if ms[rr - 1][mc["Star (component)"]] == "HD 207496")
    host181 = next(rr for rr in m181 if ms[rr - 1][mc["Star (component)"]] == "HD 18143")
    assert all(ms[rr - 1][mc["Stars in system"]] == 2 for rr in m207)

    # 3. Systems: HD 207496's row.
    s207 = [i + 1 for i, r in enumerate(sy) if r and r[0] == "HD 207496"]
    assert len(s207) == 1
    s207 = s207[0]
    sys_stars = sy[s207 - 1][sc["System stars"]]
    assert sy[s207 - 1][sc["Stars in system"]] == 2 and "HD 207496 Bb" not in sys_stars

    # 4. Rejected: none of ours yet; first empty row after the data.
    have = {r[0] for r in rj[1:] if r}
    assert not have & {x["planet"] for x in REJECTED}, have & {x["planet"] for x in REJECTED}
    rj_last = max(i + 1 for i, r in enumerate(rj) if r and r[0])
    rj0 = rj_last + 1
    rj_rows = []
    for x in REJECTED:
        host = next(r for r in pl[1:] if r and r[0] == x["system"] and
                    cell(r, pc["Role in system"]).startswith("host"))
        comp = pl_rows[x["comp"]]
        row = {"Planet": x["planet"], "Host system (primary star)": x["system"],
               "Distance (ly)": cell(host, pc["Distance (ly)"]), "Primary star class": cell(host, pc["Stellar Class"]),
               "Planet-host star": f"{x['comp']} ({x['hd']})", "Planet-host class": cell(comp, pc["Stellar Class"]),
               "Orbits the primary?": x["orbits"],
               "Mass (M-earth)": round(x["mj"] * MJ_TO_ME, 1) if x["mj"] else "",
               "Mass (M-Jup)": x["mj"] if x["mj"] else "", "Mass type": x["mtype"],
               "Orbital period (d)": x["period"] if x["period"] else "", "Confidence tier": "unlikely",
               "Candidate designation (TOI / KOI / other)": x["desig"], "Source / discovery reference": x["ref"],
               "Vetting date / last updated": "2026-10-02", "Catalogue distance (ly)": cell(host, pc["Distance (ly)"]),
               "Detection method": x["method"], "Rejected because": x["why"]}
        assert set(row) <= set(rh), set(row) - set(rh)
        rj_rows.append([row.get(h, "") for h in rh])

    lines = sp_lines(rj0, rj0 + len(REJECTED) - 1, blocks)
    note = legend_lines()
    if PLAN:
        print("Planetless rows to delete:", blocks)
        print("Multi-stars: HD 207496 rows", m207, "B at", b_row, "-> Bb inserted at", b_row + 1, "; HD 18143 host",
              host181)
        print("Systems HD 207496 row", s207, "System stars:", repr(sys_stars))
        print(f"Rejected rows {rj0}-{rj0 + len(REJECTED) - 1}:")
        for r in rj_rows:
            print("   ", {h: v for h, v in zip(rh, r) if v not in ("", None)})
        print("\n".join(lines))
        print("\n".join(note))
        return

    # ── writes ──────────────────────────────────────────────────────────────────────────────────────────────
    # Rejected candidates: grow the grid if needed, then explicit ranges (never values().append()).
    need = rj0 + len(REJECTED) - 1 - props[RJ]["gridProperties"]["rowCount"]
    if need > 0:
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
            "sheetId": props[RJ]["sheetId"], "dimension": "ROWS", "length": need}}]}).execute()
    end_col = letter(len(rh) - 1)
    gs.update_cells(SID, {f"{q(RJ)}!A{rj0}:{end_col}{rj0 + len(REJECTED) - 1}": rj_rows},
                    expect={f"{q(RJ)}!A{rj0}": "", f"{q(RJ)}!A{rj0 + len(REJECTED) - 1}": ""})
    # Copy the look of the tab's last data row onto the new ones (fills, borders, wrap) -- formats only.
    rid = props[RJ]["sheetId"]
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"copyPaste": {
        "source": {"sheetId": rid, "startRowIndex": rj_last - 1, "endRowIndex": rj_last, "startColumnIndex": 0,
                   "endColumnIndex": len(rh)},
        "destination": {"sheetId": rid, "startRowIndex": rj0 - 1, "endRowIndex": rj0 - 1 + len(REJECTED),
                        "startColumnIndex": 0, "endColumnIndex": len(rh)},
        "pasteType": "PASTE_FORMAT"}}]}).execute()

    # Multi-stars: a row for Bb under B, formulas and formats from B's row, then Bb's own values.
    mid = props[MS]["sheetId"]
    API.batchUpdate(spreadsheetId=SID, body={"requests": [
        {"insertDimension": {"range": {"sheetId": mid, "dimension": "ROWS", "startIndex": b_row,
                                       "endIndex": b_row + 1}, "inheritFromBefore": True}},
        {"copyPaste": {"source": {"sheetId": mid, "startRowIndex": b_row - 1, "endRowIndex": b_row,
                                  "startColumnIndex": 0, "endColumnIndex": len(mh)},
                       "destination": {"sheetId": mid, "startRowIndex": b_row, "endRowIndex": b_row + 1,
                                       "startColumnIndex": 0, "endColumnIndex": len(mh)},
                       "pasteType": "PASTE_NORMAL"}}]}).execute()
    gs.invalidate_cache(SID)
    bb = b_row + 1
    formulas = API.values().get(spreadsheetId=SID, range=f"{q(MS)}!A{bb}:{letter(len(mh) - 1)}{bb}",
                                valueRenderOption="FORMULA").execute()["values"][0]
    bb_vals = {"Star (component)": "HD 207496 Bb", "Role in system": "companion", "Nickname (IAU)": "",
               "Stars in system": 3, "Mass (M-sun)": BB["m2"], "Stellar Class": "", "Class (sort key)": "",
               "Effective temp (K)": "", "Star data source": BB_DATA, "Luminosity (L-sun)": "",
               "Radial velocity (km/s)": "", "Gaia DR3 source_id": "", "Kinematics source": "",
               "Proper motion in RA, μα·cos δ (mas/yr)": "", "Proper motion in Dec, μδ (mas/yr)": "",
               "Total proper motion, μ (arcsec/yr)": "", "Space velocity (km/s)": "",
               "Orbital eccentricity (e)": BB["ecc"], "Orbit described": "HD 207496 B + HD 207496 Bb",
               "Orbit source": BB_SOURCE, "Separation from": "HD 207496 B", "Separation (AU)": BB["a_au"],
               "Separation type": "semi-major axis", "Separation source": BB_SOURCE}
    upd = {}
    for h, v in bb_vals.items():
        c = mc[h]
        if str(formulas[c] if c < len(formulas) else "").startswith("="):
            continue                                   # keep the copied formula
        upd[f"{q(MS)}!{letter(c)}{bb}"] = v
    gs.update_cells(SID, upd, expect={f"{q(MS)}!{letter(mc['Star (component)'])}{bb}": "HD 207496 B"})
    sic = letter(mc["Stars in system"])
    gs.update_cells(SID, {f"{q(MS)}!{sic}{host207}": 3, f"{q(MS)}!{sic}{b_row}": 3},
                    expect={f"{q(MS)}!{sic}{host207}": 2, f"{q(MS)}!{sic}{b_row}": 2})
    sep_cell = f"{q(MS)}!{letter(mc['Separation (AU)'])}{bb}"
    # The paste brought B's orange box on Mass (B's mass is inferred; Bb's is Gaia's, looked up): back to the
    # tab's thin grey rule.  B's Mass note came too, and is overwritten below.
    gs.set_border(SID, [f"{q(MS)}!{letter(mc['Mass (M-sun)'])}{bb}"], "FFBFBFBF", style="SOLID")
    gs.set_border(SID, [sep_cell], gs.INFERRED_BORDER)
    gs.set_note(SID, {sep_cell: BB_SEP_NOTE,
                      f"{q(MS)}!{letter(mc['Mass (M-sun)'])}{bb}":
                          f"Gaia DR3 binary_masses, source_id {BB['source_id']}: m2 between {BB['m2']} and "
                          f"{BB['m2_hi']} M-sun (Orbital+M1, M1 = 0.557); the lower bound, a dark companion, is "
                          "entered.",
                      f"{q(MS)}!{sic}{host207}": NOTE_207496,
                      f"{q(MS)}!{sic}{host181}": NOTE_18143})

    # Systems: HD 207496 is three stars.
    ssc, sst = letter(sc["Stars in system"]), letter(sc["System stars"])
    new_stars = sys_stars + "\nHD 207496 Bb: class unknown (unseen companion of B, Gaia DR3 orbit)"
    gs.update_cells(SID, {f"{q(SY)}!{ssc}{s207}": 3, f"{q(SY)}!{sst}{s207}": new_stars},
                    expect={f"{q(SY)}!{ssc}{s207}": 2, f"{q(SY)}!A{s207}": "HD 207496"})
    gs.set_note(SID, {f"{q(SY)}!{ssc}{s207}": NOTE_207496})

    # Planetless: delete both blocks, the lower first so the upper's row numbers hold.  Names re-checked.
    pid = props[PL]["sheetId"]
    now = values(PL)
    for name, rr in sorted(blocks.items(), key=lambda kv: -kv[1][0]):
        assert all(now[i - 1][0] == name for i in rr), name
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"deleteDimension": {"range": {
            "sheetId": pid, "dimension": "ROWS", "startIndex": rr[0] - 1, "endIndex": rr[-1]}}}]}).execute()
    gs.invalidate_cache(SID)
    left = {r[0] for r in values(PL)[1:] if r and r[0]}
    assert not left & set(MOVED) and len(left) == 80, (len(left), left & set(MOVED))

    # Sources & Provenance, then Legend & Notes.
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{end}"])[f"{q(SP)}!A{end}"][0][0].strip()
    sp0, sp1 = end + 1, end + len(lines)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{sp0}:A{sp1}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (sp0, sp0 + 1, sp1)})
    lv = API.values().get(spreadsheetId=SID, range=f"{q(LG)}!A1:A3000").execute().get("values", [])
    lg0 = len(lv) + 2
    lg1 = lg0 + len(note) - 1
    gs.update_cells(SID, {f"{q(LG)}!A{lg0}:A{lg1}": [[x] for x in note]},
                    expect={f"{q(LG)}!A{lg0}": "", f"{q(LG)}!A{lg1}": ""})

    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log = {"deleted": blocks, "multi_bb_row": bb, "systems_row": s207, "rejected_rows": [rj0, rj0 + len(REJECTED) - 1],
           "sp_rows": [sp0, sp1], "legend_rows": [lg0, lg1], "title": title,
           "planetless_systems_left": len(left)}
    LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
    print("done:", json.dumps(log))


def sp_lines(r0, r1, blocks):
    return [
        "",
        f"PLANETLESS 4+ STARS CHECKED FOR PLANETS, {DATE.upper()}: TWO SYSTEMS MOVED OUT, SIX REFUTED CLAIMS FILED",
        "  METHOD: every star component's position (this tab's RA/Dec, ICRS) cross-matched within 90 arcsec "
        "against the NASA Exoplanet Archive (pscomppars, toi), exoplanet.eu (EPN-TAP exoplanet.epn_core) and "
        "SIMBAD (object types Pl, Pl?, BD*, BD?), then a literature search per system (ADS, arXiv, web). Control: "
        "GJ 86 b is found by the same path. Done by Claude; every claim below cites its paper.",
        "  RESULT: confirmed planets in two systems, both already on Systems, Planets and Multi-stars under their "
        "HD names: CD-77 1092 = HD 207496 (HD 207496 b, transiting, 6.44 d; Barros et al. 2023, A&A 673, A4) and "
        "GJ 118.2 = HD 18143 (b and c; Feng et al. 2022, ApJS 262, 21, doi:10.3847/1538-4365/ac7e57). Their "
        f"{sum(len(v) for v in blocks.values())} rows (subsystems included) were deleted from Planetless 4+ Stars, "
        "which now holds 80 systems.",
        "  HD 18143: the deleted GJ 118.2 Ab (MSC 'astrometric, perturbed motion suspected'; mass 0.1984 a "
        "typical-companion guess; drawn hypothetical) was NOT carried to Multi-stars: most likely it is the "
        "astrometric signal of planet c (10.0 +/- 1.9 MJ true, ~17.5 AU, RV plus Hipparcos-Gaia astrometry, Feng "
        "et al. 2022). Its Aa, B and C were already Multi-stars' HD 18143, B and C. Noted on the host row.",
        "  HD 207496: the deleted CD-77 1092 Ab used a Gaia DR3 orbit that is the companion's, not the primary's: "
        f"OrbitalTargetedSearch source_id {BB['source_id']} is HD 207496 B (TIC 290348382, G 10.84, RUWE 37.8); "
        "the primary is 6356417496318028800. research.py's Gaia match paired them wrongly. That orbit is now "
        f"Multi-stars' HD 207496 Bb, B's companion: P = {BB['period_d']} +/- {BB['period_err']} d, e = {BB['ecc']} "
        f"(Gaia DR3 nss_two_body_orbit); mass {BB['m2']} M-sun, the lower bound of Gaia DR3 binary_masses "
        f"(Orbital+M1; m2 {BB['m2']}-{BB['m2_hi']}, M1 0.557), entered as looked up. INFERRED (orange): its "
        f"separation, a = ((M1 + M2) P^2)^(1/3) = {BB['a_au']} AU with M1 = {BB['m1']} (B on this tab) and M2 = "
        f"{BB['m2']}; WEAK, it rests on the lower-bound mass (at the upper bound a = {BB['a_hi']} AU). Exact "
        "arithmetic, no scatter beyond the mass range. HD 207496 is now 3 stars on Systems and Multi-stars.",
        f"  REJECTED CANDIDATES rows {r0}-{r1}: HD 131977 b (GJ 570 A), HD 53680 B (GJ 264.1 Ca), HD 18445 B "
        "(GJ 120.1 Ca), HD 283750 b (GJ 171.2 Aa), VB 8 B (GJ 644 F) and HD 13507 B (single-companion solution; "
        "BD+39 496 Ba). Each row's 'Rejected because' cites its refuting paper. TOI-1113.01, a false positive on "
        "HD 207496 B, was already on the tab. These rows hold typed distance, class and mass values rather than "
        "the tab's lookup formulas, since their hosts are on Planetless 4+ Stars, not Systems.",
        "  STILL OPEN, NOT CHANGED: BD+39 496 Bb (0.07 M-sun, 7.1 AU) resembles the refuted single brown dwarf of "
        "HD 13507, for which Grandjean et al. 2021 propose two brown dwarfs; GJ 120.1 Cb is typed K2V? and "
        "0.71 M-sun where Halbwachs et al. 2000 give 0.176 M-sun; tau Cyg Ab (0.0138 M-sun) is the doubtful "
        "PHASES astrometric candidate (Muterspaugh et al. 2010, arXiv:1010.4048).",
    ]


def legend_lines():
    return [
        f"PLANETLESS 4+ STARS CHECKED FOR PLANETS -- {DATE.upper()}",
        "Two of its 82 systems turned out to have confirmed planets and were already on this workbook's planet "
        "tabs under their HD names: CD-77 1092 = HD 207496 and GJ 118.2 = HD 18143. They were taken off the tab "
        "(80 systems now) and kept on Multi-stars, where HD 207496 gained a third star, Bb, from Gaia DR3's orbit "
        "for B. Six refuted planet and brown-dwarf claims found around the remaining systems were filed on "
        "Rejected candidates. Sources & Provenance has the method and every citation, under 'PLANETLESS 4+ STARS "
        f"CHECKED FOR PLANETS, {DATE.upper()}'.",
    ]


if __name__ == "__main__":
    main()
