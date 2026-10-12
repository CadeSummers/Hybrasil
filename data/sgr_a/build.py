# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the Sgr A* S-stars tab from plan.json -- the only writer.

    python build.py          what it would do; touches nothing
    python build.py write    add the tab, fill it, box the inferred cells, record it on Sources & Provenance, rename

The tab is new, so every cell is expected blank before it is written; a tab of that name already there aborts the run.
The pattern is data/four_plus_stars/build.py's: addSheet after Planetless 4+ Stars, the header's look copied from
it, a grey rule on every cell, a basic filter over every column, then orange boxes and INFERRED notes keyed by the
object's name (re-read from column A, never assumed from a row number).
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("kinematics_common",
                                               ROOT / "data" / "known_within_100ly" / "kinematics" / "common.py")
kin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kin)
letter, q, sheets, now = kin.letter, kin.q, kin.sheets, kin.now

from hybrasil.data.sgr_a_loader import TAB  # noqa: E402

PLAN = HERE / "plan.json"
LOG = HERE / "write_log.json"
SP = "Sources & Provenance"
AFTER = "Planetless 4+ Stars"
GREY_RULE = "FFBFBFBF"
TODAY = datetime.date.today().isoformat()
WIDE = {"Role in system": 230, "Status": 230, "Star data source": 320, "Orbit source": 300, "Measured RV source": 260,
        "Existence": 230, "Refs": 320, "Stellar Class": 170, "SIMBAD main_id": 150}

SP_COLUMN_ROWS = [
    [f"{TAB}: Object, Object type, Role in system, Status",
     "The S-stars of Gillessen et al. 2017 (ApJ 837, 30, 2017ApJ...837...30G, Table 3: every star with an orbit) and "
     "the disputed newcomers S62, S4711-S4716 of Peisker et al. 2020a/b, 2022. Sgr A* is the one 'Supermassive black "
     "hole' row: neither a star nor a planet, the mass every row orbits.",
     "High; 'disputed' rows are claimed by Peisker et al. only -- GRAVITY 2021 (2021A&A...645A.127G) and 2022 "
     "(2022A&A...657A..82G) do not see them (the Status cell's note gives both sides)",
     "VizieR J/ApJ/837/30 table3; the Status notes' bibcodes on ADS"],
    [f"{TAB}: SIMBAD main_id, Existence, Refs",
     "SIMBAD (CDS) by name ([EG97] Sn and the IRS/W aliases); Existence: confirmed by SIMBAD and Gillessen 2017, or "
     "disputed; Refs: the bibcode behind each kind of value (Orbit, Class, Mass, Teff, RV, Disputed by).",
     "High",
     "SIMBAD sim-id?Ident=<main_id>; ui.adsabs.harvard.edu/abs/<bibcode>"],
    [f"{TAB}: Stellar Class, Mass (M-sun), Effective temp (K), Star data source",
     "Published where a paper gives it: Habibi et al. 2017 (2017ApJ...847..120H; masses, Teff of 7 B dwarfs), Martins "
     "et al. 2008 (S2), Habibi et al. 2019 (late-type giants), Paumard et al. 2006, Feldmeier-Krause et al. 2015, "
     "Martins 2006/2007, Peisker et al. Otherwise INFERRED from K (orange): an early-type star as a main-sequence "
     "dwarf through Pecaut & Mamajek 2013's sequence; a late-type star as a K/M giant of nominal 1.5 Msun (WEAK).",
     "Published: medium (spectroscopic masses, +/-15-25%). Inferred early-type: +0.06 dex bias, 0.075 dex rms against "
     "the 7 published masses; valid M_K -3.2..+1. Inferred late-type: WEAK, range 0.8-3 Msun",
     "Star data source names the table; data/sgr_a/infer.py reproduces every inferred cell"],
    [f"{TAB}: Spectral group (Gillessen 2017), K mag",
     "Gillessen et al. 2017 Table 3 (SpT flag e/l; Kmag). Disputed stars: Peisker et al.'s K.",
     "High", "VizieR J/ApJ/837/30 table3"],
    [f"{TAB}: Semi-major axis (arcsec), Orbital eccentricity (e), Inclination (deg), Ascending node (deg), Argument "
     "of periapsis (deg), Time of periapsis (yr), Orbital period (yr), Orbit source",
     "Gillessen et al. 2017 Table 3; GRAVITY Collaboration 2022 (A&A 657, L12, 2022A&A...657L..12G, Table B.1) for "
     "S2, S29, S38, S55; Peisker et al. 2020a (S62), 2020b (S4711-S4715), 2022 (S4716). Angles on the plane of the "
     "sky, node position angle East of North, ascending node = receding. GRAVITY gives no period: P = sqrt(a^3/M) "
     "with the fit's own R0 and M (orange).",
     "High (Gillessen, GRAVITY); disputed (Peisker)",
     "Orbit source names the table"],
    [f"{TAB}: Semi-major axis (AU), Pericentre distance (AU)",
     "INFERRED (orange): a = a\" x R0, with the orbit paper's own R0 (Gillessen 2017: 8320 pc; GRAVITY 2022: 8277 pc); "
     "Peisker's milliparsecs x 206.265 AU/mpc. Pericentre = a (1 - e).",
     "High: arithmetic on published values; R0's own 0.1-1% error carries over",
     "The cell's note gives the inputs"],
    [f"{TAB}: Motion epoch (yr), RA offset (mas), Dec offset (mas), Distance from Sgr A* (AU), Radial velocity "
     "(km/s), Proper motion (mas/yr), 3-D speed (km/s), Direction of sky motion (PA, deg)",
     "INFERRED (orange): where each star is and how it moves at the motion epoch (2026.77 = 9 Oct 2026), from its own "
     "orbit by Kepler's equation (hybrasil/data/sgr_a_loader.py sky_motion). Checked on S2 against Gillessen 2017 "
     "table 5: median 1-2 mas from its 145 positions, every one of 44 radial velocities the right sign and within "
     "150 km/s.",
     "Medium: as good as the orbit; long-period orbits (P > 300 yr) extrapolate far from their data",
     "Recompute with sky_motion() from the row's elements; compare with the Measured RV columns"],
    [f"{TAB}: Measured radial velocity (km/s), Measured RV epoch (yr), Measured RV source",
     "A published spectroscopic RV and its epoch: mostly the last SINFONI value of Gillessen 2017 table 5 or Gillessen "
     "2009 Appendix B; S6 Eisenhauer 2005; S97 the binary's systemic velocity (Martins 2006).",
     "High", "Measured RV source names the table"],
    [f"{TAB}: RA (deg, ICRS), Dec (deg, ICRS), Distance (pc), Distance (ly)",
     "Sgr A* only. Position: SIMBAD 'NAME Sgr A*' (Petrov et al. 2011, 2011AJ....142...35P, VLBA). Distance: R0 = "
     "8277 +/- 9 (stat) +/- 30 (sys) pc, GRAVITY 2022 L12; ly = pc x 3.2616 (orange).",
     "High", "SIMBAD; GRAVITY 2022 Sect. 6"],
]


def rng(sheet, r0, r1, c0, c1):
    return {"sheetId": sheet, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def sp_lines(plan, n_orange):
    rows = plan["rows"]
    n_dis = sum(1 for r in rows if str(r[3]).startswith("disputed"))
    cal = plan["calibration"]
    return [
        "",
        f"{TODAY}: SGR A* S-STARS TAB ADDED (data/sgr_a/, log write_log.json).",
        f"Why: to plot the S-stars round Sagittarius A*, the Milky Way's supermassive black hole, as the viewer's "
        f"Galactic Center system. {len(rows)} rows: Sgr A* (flagged: a black hole, not a star), the 40 stars Gillessen "
        f"et al. 2017 fit orbits for, and {n_dis} disputed newcomers (Peisker et al.), which GRAVITY does not see.",
        "Orbits: Gillessen 2017 Table 3, with GRAVITY 2022's newer fits for S2, S29, S38, S55. S111 is unbound "
        "(e = 1.09): listed, not drawn.",
        "Classes, masses and Teff: published where a paper gives one (Star data source names it); else inferred from K "
        f"and boxed orange. The early-type relation, checked against Habibi et al. 2017's {cal['n']} masses, runs "
        f"{cal['mean_dex']:+.3f} dex high with {cal['rms_dex']:.3f} dex rms. A late-type star's 1.5 Msun is WEAK: "
        "its K magnitude barely constrains a giant's mass.",
        "Motion columns: computed from each orbit at 2026.77, orange. The papers' ascending node is the receding one; "
        "the viewer turns Omega and omega by 180 deg to put z toward Earth, checked against S2's measured RVs.",
        f"Orange cells: {n_orange}. Research: data/sgr_a/research/A.json, B.json, C.json (three research agents, every "
        "value with its bibcode and table; spot-checked against the GRAVITY 2022 and Habibi 2017 PDFs).",
    ]


def column_table_rows(gs, api, sid, meta):
    vals = api.values().get(spreadsheetId=sid, range=f"{q(SP)}!A1:A80").execute()["values"]
    top = next(i for i, r in enumerate(vals) if r and str(r[0]).startswith("WHERE EACH COLUMN CAME FROM"))
    assert vals[top + 1][0] == "COLUMN", vals[top + 1]
    end = top + 2
    while end < len(vals) and vals[end] and str(vals[end][0]).strip():
        end += 1
    have = {str(r[0]).strip() for r in vals[top + 2:end] if r}
    rows = [r for r in SP_COLUMN_ROWS if r[0] not in have]
    if not rows:
        return None
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"insertDimension": {
        "range": {"sheetId": meta[SP]["sheetId"], "dimension": "ROWS", "startIndex": end, "endIndex": end + len(rows)},
        "inheritFromBefore": True}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{end + 1}:D{end + len(rows)}": rows},
                    expect={f"{q(SP)}!A{end + 1}": "", f"{q(SP)}!A{end}": vals[end - 1][0]})
    return [end + 1, end + len(rows)]


def append_sp(gs, api, sid, lines):
    props = {s["properties"]["title"]: s["properties"] for s in
             api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]}[SP]
    last = props["gridProperties"]["rowCount"]
    assert gs.read_cells(sid, [f"{q(SP)}!A{last}"])[f"{q(SP)}!A{last}"][0][0].strip()
    start, end = last + 1, last + len(lines)
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
        "sheetId": props["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, end)})
    return [start, end]


def main():
    write = "write" in sys.argv[1:]
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    headers, rows = plan["headers"], plan["rows"]
    col = {h: i for i, h in enumerate(headers)}
    nrows, ncols = len(rows) + 1, len(headers)
    print(f"{TAB}: {len(rows)} rows x {ncols} columns; {len(plan['inferred'])} orange cells; "
          f"{len(plan['notes'])} other notes")
    if not write:
        return
    gs, sid, api = sheets()
    meta = {s["properties"]["title"]: s["properties"] for s in
            api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]}
    assert TAB not in meta, f"{TAB} already exists"
    after = meta[AFTER]
    res = api.batchUpdate(spreadsheetId=sid, body={"requests": [{"addSheet": {"properties": {
        "title": TAB, "index": after["index"] + 1,
        "gridProperties": {"rowCount": nrows, "columnCount": ncols, "frozenRowCount": 1, "frozenColumnCount": 1}}}}]}
                          ).execute()
    tid = res["replies"][0]["addSheet"]["properties"]["sheetId"]
    gs.invalidate_cache(sid)
    # the header's look from Planetless 4+ Stars (its first ncols columns), then the values
    api.batchUpdate(spreadsheetId=sid, body={"requests": [
        {"copyPaste": {"source": rng(after["sheetId"], 0, 1, 0, ncols), "destination": rng(tid, 0, 1, 0, ncols),
                       "pasteType": "PASTE_FORMAT"}}]}).execute()
    last = f"{letter(ncols - 1)}{nrows}"
    gs.update_cells(sid, {f"{q(TAB)}!A1:{last}": [headers] + rows},
                    expect={f"{q(TAB)}!A1": "", f"{q(TAB)}!A2": "", f"{q(TAB)}!{last}": ""})
    grey = {"style": "SOLID", "color": gs._hex_to_color(GREY_RULE)}
    widths = [{"updateDimensionProperties": {
        "range": {"sheetId": tid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
        "properties": {"pixelSize": WIDE.get(h, 110)}, "fields": "pixelSize"}} for i, h in enumerate(headers)]
    api.batchUpdate(spreadsheetId=sid, body={"requests": widths + [
        {"updateBorders": {"range": rng(tid, 1, nrows, 0, ncols), "top": grey, "bottom": grey, "left": grey,
                           "right": grey, "innerHorizontal": grey, "innerVertical": grey}},
        {"repeatCell": {"range": rng(tid, 1, nrows, 0, ncols), "cell": {"userEnteredFormat": {
            "verticalAlignment": "TOP"}}, "fields": "userEnteredFormat.verticalAlignment"}},
        {"setBasicFilter": {"filter": {"range": rng(tid, 0, nrows, 0, ncols)}}},
    ]}).execute()

    # Orange boxes and notes, by name: column A re-read.
    names = [r[0] for r in gs.read_cells(sid, [f"{q(TAB)}!A2:A{nrows}"])[f"{q(TAB)}!A2:A{nrows}"]]
    assert names == [r[0] for r in rows], "column A is not the plan's order"
    at = {n: i + 2 for i, n in enumerate(names)}

    def cell(key):
        name, h = key.split("|", 1)
        return f"{q(TAB)}!{letter(col[h])}{at[name]}"
    orange = [cell(k) for k in plan["inferred"]]
    for s in range(0, len(orange), 200):
        gs.set_border(sid, orange[s:s + 200], gs.INFERRED_BORDER)
    notes = {cell(k): n for k, n in plan["inferred"].items()}
    notes.update({cell(k): n for k, n in plan["notes"].items()})
    items = list(notes.items())
    for s in range(0, len(items), 300):
        gs.set_note(sid, dict(items[s:s + 300]))

    # read back: every value, and the orange boxes by name
    back = api.values().get(spreadsheetId=sid, range=f"{q(TAB)}!A1:{last}",
                            valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
    want = [headers] + rows
    for i, (b, w) in enumerate(zip(back, want)):
        b = list(b) + [""] * (ncols - len(b))
        for j, (x, y) in enumerate(zip(b, w)):
            if not (x == y or (isinstance(x, (int, float)) and isinstance(y, (int, float)) and abs(x - y) < 1e-9)):
                raise AssertionError(f"row {i + 1} {headers[j]}: wrote {y!r}, reads {x!r}")
    borders = gs.get_borders(sid, f"{q(TAB)}!A1:{last}")
    boxed = {k.split("!")[-1] for k, b in borders.items()
             if all("FF9900" in str((b.get(s) or (None,))[0] or "").upper() for s in ("top", "bottom", "left", "right"))}
    want_boxed = {c.split("!")[-1] for c in orange}
    assert want_boxed <= boxed, f"{len(want_boxed - boxed)} inferred cells are not boxed: {sorted(want_boxed - boxed)[:5]}"
    got = boxed

    sp_cols = column_table_rows(gs, api, sid, meta)
    sp = append_sp(gs, api, sid, sp_lines(plan, len(orange)))
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(sid)
    log = {"at": now(), "tab": TAB, "sheet_id": tid, "rows": len(rows), "cols": ncols, "orange": len(orange),
           "notes": len(notes), "sp_column_rows": sp_cols, "sp_block": sp, "title": title,
           "borders_read_back": None if got is None else len(got)}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log, ensure_ascii=False))


if __name__ == "__main__":
    main()
