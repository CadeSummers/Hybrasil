# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Four brown-dwarf companions on Unconfirmed, each filed under its brown-dwarf primary as host.

    python add_bd_companions.py          plan: print every write; touches nothing
    python add_bd_companions.py write    append the rows, notes, orange boxes, provenance, rename

The owner's rule of 7 Oct 2026 (docs/hybrasil-instructions.md section 6): a star fuses protium or once did; a brown
dwarf is a very large planet. planet_scan.py found these four NASA Exoplanet Archive companions on no planet tab, each
orbiting a brown dwarf. Under the rule, the pair has no star. The companion is the row, and its brown-dwarf
primary fills the host columns (owner's choice). The host luminosity is the primary's own.

Every number was read from the paper or catalogue named beside it, not from the archive, which is stale on three:
  - WISE 1217+16 and CFBDSIR 1458+10: the archive's 'semi-major axis' is a projected separation at an old distance.
  - DENIS 0823-49: Sahlmann et al. 2015 replace the 2013 masses. The primary is a brown dwarf too, not 0.075 M-sun.
  - CFBDSIR 1458+10 is at 104 +/- 8 ly (Dupuy & Liu 2012), beyond 100 ly. The owner chose to keep it, flagged, as
    HD 8326 and GJ 9689 are kept.

A host with no Systems row has no host mass, so the loader cannot derive a period from a (catalog_loader._planet_body).
Each row therefore carries both a and P, and whichever of the two was derived is orange, with the method in its note.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data" / "four_plus_stars"))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
UN, SP = "Unconfirmed within 100 ly", "Sources & Provenance"
LOG = HERE / "add_bd_companions_log.json"
DATE, ISO = "7 Oct 2026", "2026-10-07"
MJ_PER_MSUN = 1047.57
LY_PER_PC = 3.26156
RULE = ("BROWN-DWARF HOST: under the model's rule (docs/hybrasil-instructions.md section 6) a brown dwarf is a "
        "planet, not a star, so this pair has no star. The companion is filed under its brown-dwarf primary as host.")


def kepler_p_days(a_au, m_sun):
    return math.sqrt(a_au ** 3 / m_sun) * 365.25


def kepler_a_au(p_days, m_sun):
    return (m_sun * (p_days / 365.25) ** 2) ** (1 / 3)


# ---------------------------------------------------------------- the four, from the sources named
# WISE 1217+16: parallax 107.4 +/- 3.5 mas (Kirkpatrick+2021 Table 5); A's log L -6.04 at 99 mas (Dupuy & Kraus 2013
# Table S5); masses A 30 +/- 5, B 22 +/- 2 MJ (Leggett+2014 Table 3); separation 0.76" (Leggett+2014 Table 1).
W_PLX, W_PLX_DK13, W_LOGL = 107.4, 99.0, -6.04
W_L = round(10 ** W_LOGL * (W_PLX_DK13 / W_PLX) ** 2, 10)
W_A = round(0.76 * 1000 / W_PLX, 2)
W_P = round(kepler_p_days(W_A, (30 + 22) / MJ_PER_MSUN))
# CWISE 1935-15: 69.3 +/- 3.8 mas (Kirkpatrick+2021 Table 5); pair's log L -6.3 +/- 0.1 (Faherty+2024 ED Table 1);
# separation 2.48 au, masses A 12-39 MJ and B 7-24 MJ for 1-10 Gyr (De Furio+2025 section 4.1).
C_L = round(10 ** -6.3, 10)
C_A = 2.48
C_P = round(kepler_p_days(C_A, ((12 + 39) / 2 + (7 + 24) / 2) / MJ_PER_MSUN))
# DENIS 0823-49: Gaia DR3 orbital solution, 48.612 +/- 0.138 mas (I/357/tbootsvc); A's log L -3.74 +/- 0.04, L1.5
# + L5.5 (Sahlmann+2015 Table 2); P 247.75 d, e 0.36 (Table 1); M2 0.030 M-sun best fit, q 0.64-0.74 (Table 3).
D_L = round(10 ** -3.74, 7)
D_M2 = 0.030
D_M1 = round(D_M2 / 0.69, 4)
D_P, D_E = 247.75, 0.36
D_A = round(kepler_a_au(D_P, D_M1 + D_M2), 3)
# CFBDSIR 1458+10: 31.3 +/- 2.5 mas (Dupuy & Liu 2012); A's log L -5.82 +/- 0.26 at 31.9 pc and B 10 (+2/-3) MJ at
# 1 Gyr (Dupuy & Kraus 2013 Table S5); projected separation 3.5 +/- 0.3 au (Liu+2012 Table 4); A 0.021 M-sun
# (Liu+2011, the only primary mass published).
F_L = round(10 ** -5.82, 9)
F_A = 3.5
F_P = round(kepler_p_days(F_A, 0.021 + 10 / MJ_PER_MSUN))

ROWS = [
    dict(
        planet="WISEP J121756.91+162640.2 A b", host="WISEP J121756.91+162640.2 A", host_class="T8.5",
        lum=W_L, mj=22.0, mass_type="model-dependent (evolutionary models at 4-8 Gyr; not Msini)",
        p=W_P, a=W_A, e="", dist=round(1000 / W_PLX * LY_PER_PC, 2), tier="strong",
        desig="WISE 1217+1626 B (Liu et al. 2012); T9 + Y0 there, T8.5 + Y0-0.5 from resolved spectra",
        ref=("Liu et al. 2012, ApJ 758, 57 (discovery, Table 2); Leggett et al. 2014, ApJ 780, 62, Tables 1 and 3 "
             "(types, masses, separation); Kirkpatrick et al. 2021, ApJS 253, 7, Table 5 (parallax); Dupuy & Kraus "
             "2013, Science 341, 1492, Table S5 (A's luminosity)"),
        vetted=ISO, method="Direct imaging",
        flags=(f"{RULE} No measured orbit: a is the 0.76\" projected separation at Kirkpatrick+2021's 107.4 mas "
               f"(= {W_A} au; the archive's 8.0 au is the same separation at a photometric 10.5 pc), and P is "
               "Kepler's third law on it (orange). Liu+2012 estimate 130-210 yr for the true orbit. Masses "
               "22 +/- 2 MJ (B) and 30 +/- 5 MJ (A) at 4-8 Gyr, Leggett+2014 Table 3."),
        orange={"lum": f"INFERRED: Dupuy & Kraus 2013 (Table S5) give A log L = -6.04 (+0.29/-0.28) at 99 mas; "
                       f"rescaled by (99/107.4)^2 to Kirkpatrick+2021's parallax = {W_L:.3e} L-sun (log "
                       f"{math.log10(W_L):.2f}). Cross-check: Leggett+2014's R 0.091 R-sun, Teff 550-600 K give "
                       "log L ~ -6.09.",
                "a": f"INFERRED: projected separation, not a semi-major axis. 0.76\" (Leggett+2014 Table 1) x "
                     f"{1000 / W_PLX:.3f} pc = {W_A} au. WEAK as an orbit: the true a is likely larger.",
                "p": f"INFERRED, WEAK: Kepler's third law on a = {W_A} au and M = 30 + 22 MJ (Leggett+2014), "
                     f"circular. = {W_P} d ({W_P / 365.25:.0f} yr). Liu+2012 estimate 130-210 yr statistically."}),
    dict(
        planet="CWISEP J193518.59-154620.3 b", host="CWISEP J193518.59-154620.3", host_class="≥Y1",
        lum=C_L, mj=15.5, mass_type="model-dependent (range 7-24 MJ for 1-10 Gyr; archive midpoint)",
        p=C_P, a=C_A, e="", dist=round(1000 / 69.3 * LY_PER_PC, 2), tier="strong",
        desig="CWISE 1935-1546 B (De Furio et al. 2025); A is >=Y1 (estimated), B likely later",
        ref=("De Furio et al. 2025, ApJ 990, L63 (arXiv:2508.17176), section 4.1 (separation, masses, period); "
             "Kirkpatrick et al. 2021, ApJS 253, 7, Table 5 (parallax); Faherty et al. 2024, Nature 628, 511, "
             "Extended Data Table 1 (pair's luminosity)"),
        vetted=ISO, method="Direct imaging",
        flags=(f"{RULE} No measured orbit: a is the 172 mas projected separation, 2.48 (+0.27/-0.11) au, and P is "
               "Kepler's third law on it (orange). De Furio+2025 give 16-28 yr for a circular orbit. Masses are "
               "ranges, A 12-39 MJ and B 7-24 MJ for ages 1-10 Gyr; 15.5 MJ is the archive's midpoint. The host "
               "luminosity is the unresolved pair's (orange): no resolved value is published."),
        orange={"lum": "INFERRED, WEAK: this is the PAIR's luminosity, log L = -6.3 +/- 0.1 (Faherty+2024 ED Table 1, "
                       "fitted before the binary was resolved), adopted for A because no resolved value is published "
                       "(checked De Furio+2025, Faherty+2024, Kirkpatrick+2021). It overstates A's light, at most by "
                       "the companion's share.",
                "p": f"INFERRED, WEAK: Kepler's third law on a = 2.48 au (projected) and M = 25.5 + 15.5 MJ, the "
                     f"midpoints of De Furio+2025's ranges, circular. = {C_P} d ({C_P / 365.25:.1f} yr), inside "
                     "their 16-28 yr."}),
    dict(
        planet="DENIS-P J082303.1-491201 b", host="DENIS-P J082303.1-491201", host_class="L1.5",
        lum=D_L, mj=round(D_M2 * MJ_PER_MSUN, 1),
        mass_type="model-dependent (Lbol + age; best fit 0.030 M-sun, range 0.018-0.045)",
        p=D_P, a=D_A, e=D_E, dist=round(1000 / 48.612 * LY_PER_PC, 2), tier="strong",
        desig="DE0823-49 b (Sahlmann et al. 2013); L5.5 +/- 1.1",
        ref=("Sahlmann et al. 2013, A&A 556, A133 (discovery); Sahlmann et al. 2015, A&A 579, A61 (arXiv:1505.07972), "
             "Tables 1-3 (orbit, types, luminosity, masses); Gaia DR3 orbital solution, VizieR I/357/tbootsvc "
             "(parallax)"),
        vetted=ISO, method="Astrometry (ground-based orbit; Gaia DR3 also has an orbital solution)",
        flags=(f"{RULE} Measured 3-D astrometric orbit, Sahlmann+2015 Table 1: P = 247.75 +/- 0.64 d, e = 0.36 +/- "
               "0.04, i = 52.2 deg (Gaia DR3 NSS: 249.96 d, e 0.225, i 50.5). Sahlmann+2015 replace the 2013 masses "
               "(M1 78 MJ, M2 28.5 MJ, the archive's): age 80-500 Myr, M1 0.028-0.063 and M2 0.018-0.045 M-sun, so "
               "the primary is a brown dwarf as well. a is derived (orange)."),
        orange={"a": f"INFERRED: Kepler's third law on P = 247.75 d (Sahlmann+2015 Table 1) and M1 + M2 = "
                     f"{D_M1} + {D_M2} M-sun (best-fit M2; M1 = M2 / 0.69, the middle of q = 0.64-0.74, Table 3). "
                     f"= {D_A} au. Sahlmann+2013's 0.36 au rests on the superseded masses."}),
    dict(
        planet="CFBDSIR J145829+101343 b", host="CFBDSIR J145829+101343", host_class="T9",
        lum=F_L, mj=10.0, mass_type="model-dependent (10 +2/-3 MJ at 1 Gyr; 24 MJ at 5 Gyr)",
        p=F_P, a=F_A, e="", dist=round(1000 / 31.3 * LY_PER_PC, 1), tier="strong",
        desig="CFBDSIR 1458+10 B (Liu et al. 2011); T9 + Y0 (Liu et al. 2012)",
        ref=("Liu et al. 2011, ApJ 740, 108 (discovery); Liu et al. 2012, ApJ 758, 57, section 3.3.3 and Table 4 "
             "(types, separation); Dupuy & Liu 2012, ApJS 201, 19 (parallax); Dupuy & Kraus 2013, Science 341, 1492, "
             "Table S5 (A's luminosity, B's mass)"),
        vetted=ISO, method="Direct imaging",
        flags=(f"{RULE} BEYOND 100 LY: 31.3 +/- 2.5 mas (Dupuy & Liu 2012) = 104 +/- 8 ly, within 1 sigma of the "
               "line; kept, flagged, by the owner's decision (7 Oct 2026), as HD 8326 and GJ 9689 are. The archive's "
               "75 ly is Liu+2011's superseded 43.3 mas; it has no Known row. No fitted orbit: a is the 3.5 +/- 0.3 au "
               "projected separation (Liu+2012 Table 4) and P is Kepler's third law on it (orange). The archive's "
               "2.6 au and 27.5 yr are Liu+2011's at the old distance."),
        orange={"p": f"INFERRED, WEAK: Kepler's third law on a = 3.5 au (projected, Liu+2012) and M = 0.021 M-sun "
                     f"(A, Liu+2011, the only published primary mass) + 10 MJ (B, Dupuy & Kraus 2013 at 1 Gyr), "
                     f"circular. = {F_P} d ({F_P / 365.25:.0f} yr)."}),
]
COL = {"lum": "Host luminosity (L-sun)", "a": "Semi-major axis (au)", "p": "Orbital period (d)"}


def values(rng, how="UNFORMATTED_VALUE"):
    return API.values().get(spreadsheetId=SID, range=rng, valueRenderOption=how).execute().get("values", [])


def last_data_row():
    v = values(f"{q(UN)}!A1:E2000")
    n = 1
    for i, r in enumerate(v[1:], start=2):
        if sum(1 for c in r if str(c).strip()) <= 1:
            break
        n = i
    return n


def typed(row, m_earth_per_mj):
    """{header: value} for every column this script types; formula columns are left to the copied template."""
    return {
        "Planet": row["planet"], "Host system (primary star)": row["host"], "Planet-host star": row["host"],
        "Planet-host class": row["host_class"], "Host luminosity (L-sun)": row["lum"],
        "HZ inner, optimistic (au)": "", "HZ inner, conservative (au)": "", "HZ outer, conservative (au)": "",
        "HZ outer, optimistic (au)": "", "Mass (M-earth)": round(row["mj"] * m_earth_per_mj, 1),
        "Mass type": row["mass_type"], "OEC mass (M-Jup) -- cross-check": "", "Radius (R-Jup)": "",
        "Orbital period (d)": row["p"], "Semi-major axis (au)": row["a"], "Eccentricity": row["e"],
        "Rotation period, measured (h)": "", "Orbit data source / flags": row["flags"],
        "Confidence tier": row["tier"], "Candidate designation (TOI / KOI / other)": row["desig"],
        "Disposition (TFOPWG)": "", "Source / discovery reference": row["ref"],
        "Vetting date / last updated": row["vetted"], "Catalogue distance (ly)": row["dist"],
        "Detection method": row["method"],
    }


def main():
    hdr = values(f"{q(UN)}!A1:AP1")[0]
    col = {h: letter(i) for i, h in enumerate(hdr)}
    assert len(hdr) == 42, len(hdr)
    names = {r[0] for r in values(f"{q(UN)}!A2:A2000") if r}
    assert not names & {r["planet"] for r in ROWS}, "already on Unconfirmed"
    for tab in ("Planets within 100 ly", "Rejected candidates"):
        there = {r[0] for r in values(f"{q(tab)}!A2:A2000") if r}
        assert not there & {r["planet"] for r in ROWS}, tab
    m_earth = values(f"{q('Planets within 100 ly')}!A532:C532")[0]
    assert m_earth[0] == "M-earth per M-Jup", m_earth
    m_earth = m_earth[2]

    last = last_data_row()
    n = len(ROWS)
    assert not values(f"{q(UN)}!A{last + 1}:B{last + n}"), "rows below Unconfirmed data are not empty"
    tmpl = values(f"{q(UN)}!A{last}:AP{last}", "FORMULA")[0]
    borders = gs.get_borders(SID, f"{q(UN)}!A{last}:AP{last}")
    assert all(c[0] in (None, "000000") for b in borders.values() for c in b.values()), "template row is marked"
    formula_cols = {hdr[i] for i, v in enumerate(tmpl) if str(v).startswith("=")}

    upd, notes, orange = {}, {}, []
    for k, row in enumerate(ROWS):
        r = last + 1 + k
        for h, v in typed(row, m_earth).items():
            assert h not in formula_cols, (h, "is a formula column")
            upd[f"{q(UN)}!{col[h]}{r}"] = v
        for key, text in row["orange"].items():
            cell = f"{q(UN)}!{col[COL[key]]}{r}"
            notes[cell] = text
            orange.append(cell)
        notes[f"{q(UN)}!{col['Planet-host star']}{r}"] = RULE

    print(f"Unconfirmed: copy row {last} ({tmpl[0]}) to rows {last + 1}..{last + n}, then type:")
    for row in ROWS:
        print(f"  {row['planet']}: L={row['lum']:.3e} a={row['a']} P={row['p']} e={row['e']!r} "
              f"MJ={row['mj']} d={row['dist']} ly")
    print("orange:", [c.split("!")[1] for c in orange])
    sp = sp_lines(last + 1, last + n)
    if PLAN:
        print("\nnotes:\n" + "\n".join(f"  {c.split('!')[1]}: {t}" for c, t in notes.items()))
        print("\nSources & Provenance:\n" + "\n".join(sp))
        return

    sid_un = gs._sheet_ids(SID)[UN]
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"copyPaste": {
        "source": {"sheetId": sid_un, "startRowIndex": last - 1, "endRowIndex": last,
                   "startColumnIndex": 0, "endColumnIndex": 42},
        "destination": {"sheetId": sid_un, "startRowIndex": last, "endRowIndex": last + n,
                        "startColumnIndex": 0, "endColumnIndex": 42},
        "pasteType": "PASTE_NORMAL"}}]}).execute()
    gs.invalidate_cache(SID)
    copied = gs.get_notes(SID, f"{q(UN)}!A{last + 1}:AP{last + n}")
    gs.set_note(SID, {f"{q(UN)}!{a1}": "" for a1 in copied})
    gs.update_cells(SID, upd, expect={f"{q(UN)}!A{last + 1}": tmpl[0], f"{q(UN)}!A{last}": tmpl[0]})
    gs.set_note(SID, notes)
    gs.set_border(SID, orange, gs.INFERRED_BORDER)
    gs.invalidate_cache(SID)

    after = values(f"{q(UN)}!A{last + 1}:AP{last + n}")
    for k, row in enumerate(ROWS):
        got = dict(zip(hdr, after[k]))
        assert got["Planet"] == row["planet"] and got["Distance (ly)"] == row["dist"], got
        assert isinstance(got["Stellar flux received (S-earth)"], float), got

    f = [s for s in API.get(spreadsheetId=SID, fields="sheets(properties(title),basicFilter)").execute()["sheets"]
         if s["properties"]["title"] == UN][0].get("basicFilter")
    if f and f["range"].get("endRowIndex", 0) < last + n:
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"setBasicFilter": {
            "filter": dict(f, range=dict(f["range"], endRowIndex=last + n))}}]}).execute()

    meta = next(s["properties"] for s in API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]
                if s["properties"]["title"] == SP)
    end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{end}"])[f"{q(SP)}!A{end}"][0][0].strip()
    sp0, sp1 = end + 1, end + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{sp0}:A{sp1}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (sp0, sp1)})

    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps({"rows": [last + 1, last + n], "template": [last, tmpl[0]], "cells": upd,
                               "orange": orange, "sp_rows": [sp0, sp1], "title": title},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps({"rows": [last + 1, last + n], "sp_rows": [sp0, sp1], "title": title}))


def sp_lines(r0, r1):
    out = ["", f"BROWN-DWARF COMPANIONS ON UNCONFIRMED, {DATE.upper()} (rows {r0}-{r1} today)",
           "  Owner's rule, 7 Oct 2026 (docs/hybrasil-instructions.md section 6): an object is a star if it fuses "
           "protium (proton-only hydrogen) or once did, white dwarfs included; a brown dwarf, which only ever fused "
           "deuterium, is not a star but a very large planet. This reverses the 4 Oct 2026 rule that brown dwarfs "
           "count as stars on Multi-stars and Planetless 4+ Stars; those rows are not migrated yet.",
           "  Four NASA Exoplanet Archive companions were on no planet tab (data/known_within_100ly/planet_scan.py). "
           "Each orbits a brown dwarf, so each pair has no star: the companion is the row, and the brown-dwarf primary "
           "is its host (Host system and Planet-host star), with the primary's own luminosity. Tier 'strong': every "
           "companion is a resolved or astrometrically measured object; only its status is the model's choice. HZ "
           "bounds are left blank, as on other rows whose host has no Systems row.",
           "  Values were read from the papers, not the archive, which is stale on three. Orange cells are arithmetic "
           "on those values, each with its method in the cell note. Writer: data/star_counts/add_bd_companions.py "
           "(log add_bd_companions_log.json)."]
    for row in ROWS:
        out.append(f"  {row['planet']} (host {row['host']}, {row['host_class']}): {row['flags'][len(RULE) + 1:]} "
                   f"Sources: {row['ref']}.")
        for key, text in row["orange"].items():
            out.append(f"    {COL[key]} (orange): {text}")
    return out


if __name__ == "__main__":
    main()
