# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the 100 Brightest Stars tab from plan.json -- the only writer.

    python data/brightest_stars/build.py          what it would do; touches nothing
    python data/brightest_stars/build.py write    add the tab, fill it, mark it, record it, rename the workbook
    python data/brightest_stars/build.py resume   the tab is there and filled: read it back, record it, rename

`resume` exists because the first run (26 Nov 2026) stopped at the border read-back: one request for the
whole tab's borders is too large a response. They are now read ten rows at a time.

The tab is new, so every cell is expected blank before it is written; a tab of that name already
there aborts the run. The pattern is `data/sgr_a/build.py`'s: addSheet after Planetless 4+ Stars,
the header's look copied from the Systems tab, a grey rule on every cell, a basic filter, then
orange boxes (inferred), pink boxes (Wikipedia) and notes keyed by the star's name, re-read from
column A and never assumed from a row number.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import re
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

from hybrasil.data.brightest_loader import TAB  # noqa: E402

PLAN = HERE / "plan.json"
LOG = HERE / "write_log.json"
SP, LG, WK = "Sources & Provenance", "Legend & Notes", "Wikipedia sources"
SYS, AFTER = "Systems within 100 ly", "Planetless 4+ Stars"
GREY_RULE = "FFBFBFBF"
TODAY = datetime.date.today().isoformat()
DATE = datetime.date.today().strftime("%d %b %Y").lstrip("0").upper()
WIDE = {"System / Host": 110, "Nicknames": 230, "System stars": 260, "Kinematics source": 260, "Existence": 200,
        "Kinematics refs": 230, "Distance source": 260, "Magnitude note": 240, "Also on tabs": 260,
        "Star data source": 420, "Notes": 360, "HZ distance": 190, "Stellar Class": 130, "SIMBAD main_id": 110}

SP_COLUMN_ROWS = [
    [f"{TAB}: Apparent rank, Apparent magnitude (V), Magnitude note",
     "Hipparcos catalogue V (ESA 1997, VizieR I/239, field H5). One row is one naked-eye point of light: a Hipparcos "
     "entry for a close pair is the pair's combined light; entries within 60 arcsec are summed (alf Cen, bet Sco), "
     "and Mizar B (SIMBAD V) is added to Mizar. A variable is ranked on the catalogue V. The Sun is left out.",
     "High; +/-0.01 to 0.02 mag for a steady star. A variable's rank moves with it (see V range)",
     "VizieR I/239/hip_main by HIP number (list.json holds each row's); data/brightest_stars/research.py rebuilds the list"],
    [f"{TAB}: Distance (ly), Distance uncertainty (ly), Distance source, motion columns",
     "Parallax and proper motion: van Leeuwen 2007 (A&A 474, 653, VizieR I/311), the Hipparcos re-reduction; Gaia "
     "saturates on these stars. Radial velocity: SIMBAD's adopted value (bibcode in Kinematics refs). A row whose "
     "Distance source names a paper uses that paper's distance. A star already on the Systems or Planetless 4+ Stars "
     "tab keeps that tab's values (Star data source says so). Derived motion cells are orange.",
     "High within ~300 ly. Beyond ~1,000 ly the parallax error is 10 to 30% and the distance, space velocity and "
     "both luminosity ranks carry it",
     "VizieR I/311/hip2 by HIP; SIMBAD sim-id?Ident=<SIMBAD main_id>"],
    [f"{TAB}: Host mass, Host luminosity, Effective temp, Radius, Age, Metallicity, Stars in system, System stars, "
     "Variable type, V range, Extinction A_V, Point luminosity",
     "Literature research, 26 Nov 2026: four research agents, 25 stars each (data/brightest_stars/research/q1..q4.json, "
     "brief BRIEF.md), each value with its paper. The row's Star data source cell lists the citation of every value. "
     "'Host' is the brightest star of the point; Point luminosity is every star of the point together.",
     "Medium: single-paper values. Masses of evolved and massive stars are model-dependent (+/-10 to 30%). A luminosity "
     "whose note starts CHECK disagrees with its row's radius and Teff by over 20%",
     "The citation in Star data source; ui.adsabs.harvard.edu"],
    [f"{TAB}: Absolute magnitude (M_V), Visual luminosity (L-sun), Luminosity rank (bolometric), Luminosity rank (visual)",
     "INFERRED (orange). M_V = V - 5 log10(d / 10 pc) - A_V for the whole point of light; visual luminosity = "
     "10^(-0.4 (M_V - 4.81)), the Sun's M_V from Willmer 2018 (ApJS 236, 47). Bolometric rank: order of Point "
     "luminosity. Visual rank: order of Visual luminosity.",
     "As good as the distance: 0.1 mag per 5%. Ranks among the far supergiants (Deneb, Alnilam, Aludra, Wezen, Sadr, "
     "Arneb, Naos) can swap within the distance errors. A_V is 0 where none is on file",
     "Recompute from the row's V, Distance and Extinction A_V"],
    [f"{TAB}: Also on tabs",
     "Which other star tabs hold this star, and under what name, matched by SIMBAD identifier (26 Nov 2026).",
     "High", "Search the named tab for the named row"],
]


def rng(sheet_id, r0, r1, c0, c1):
    return {"sheetId": sheet_id, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def sp_lines(plan, n_orange, n_pink, far):
    return [
        "",
        f"100 BRIGHTEST STARS TAB ADDED, {DATE} (data/brightest_stars/, log write_log.json).",
        "Why: a second Stellar Motion model, of the brightest stars in the night sky and not only those within "
        f"100 ly. {len(plan['rows'])} rows, one per naked-eye point of light, in the Systems tab's columns plus the "
        "magnitude, rank, constellation, distance-error and variability columns. The model's extent is its most "
        f"distant star: {far[0]}, {far[1]:,.0f} ly.",
        "The list: Hipparcos V (ESA 1997), points within 60 arcsec summed. Astrometry: van Leeuwen 2007. Radial "
        "velocity, class, identifiers: SIMBAD. Names: IAU WGSN catalogue (IAU-CSN) by HIP number.",
        "Physical data: four research agents, every value with its paper (research/q1..q4.json); the citations are in "
        "each row's Star data source cell. Stars already on the Systems or Planetless 4+ Stars tab were copied from it.",
        f"Orange (inferred) cells: {n_orange}: absolute magnitude, visual luminosity, both luminosity ranks, the derived "
        "motion cells, and any luminosity computed from radius and Teff (its note says so). Each cell's note gives the "
        f"method. Pink (Wikipedia) cells: {n_pink}"
        + (", listed on the Wikipedia sources tab." if n_pink else "."),
        "The solvent band columns are the Systems tab's formulas, reading this tab's own Host luminosity, which is a "
        "typed value here. HZ and planet columns are filled only for a star copied from the Systems tab.",
        "Known limits: a far supergiant's distance is uncertain by hundreds of ly and its ranks with it; a variable's "
        "apparent rank changes over time; A_V is taken as 0 where no source gives one.",
    ]


def column_table_rows(gs, api, sid, meta):
    vals = api.values().get(spreadsheetId=sid, range=f"{q(SP)}!A1:A80").execute()["values"]
    top = next(i for i, r in enumerate(vals) if r and str(r[0]).startswith("WHERE EACH COLUMN CAME FROM"))
    assert vals[top + 1][0] == "COLUMN", vals[top + 1]
    end = top + 2
    while end < len(vals) and vals[end] and str(vals[end][0]).strip():
        end += 1
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"insertDimension": {
        "range": {"sheetId": meta[SP]["sheetId"], "dimension": "ROWS", "startIndex": end,
                  "endIndex": end + len(SP_COLUMN_ROWS)}, "inheritFromBefore": True}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{end + 1}:D{end + len(SP_COLUMN_ROWS)}": SP_COLUMN_ROWS},
                    expect={f"{q(SP)}!A{end + 1}": "", f"{q(SP)}!A{end}": vals[end - 1][0]})
    return [end + 1, end + len(SP_COLUMN_ROWS)]


def append_rows(gs, api, sid, title, lines):
    props = {s["properties"]["title"]: s["properties"] for s in
             api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]}[title]
    last = props["gridProperties"]["rowCount"]
    start, end = last + 1, last + len(lines)
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
        "sheetId": props["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(sid, {f"{q(title)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(title)}!A{i}": "" for i in (start, end)})
    return [start, end]


def wikipedia_rows(gs, api, sid, meta, wiki, cell_of):
    """One row per pink cell in the Wikipedia sources tab's VALUES WRITTEN FROM WIKIPEDIA table."""
    vals = api.values().get(spreadsheetId=sid, range=f"{q(WK)}!A1:A200").execute()["values"]
    top = next(i for i, r in enumerate(vals) if r and str(r[0]).startswith("VALUES WRITTEN FROM WIKIPEDIA"))
    end = top + 2
    while end < len(vals) and vals[end] and str(vals[end][0]).strip():
        end += 1
    rows = []
    for w in wiki:
        a1 = cell_of(f"{w['name']}|{w['header']}").split("!")[-1]
        rows.append([TAB, re.sub(r"\D", "", a1), a1, f"{w['name']} -- {w['header']}", w["value"],
                     w["url"].rsplit("/", 1)[-1].replace("_", " "), w["url"], w["source"], "",
                     f"Written {TODAY}; the research agent could not reach the cited paper. "
                     "Row and cell as of that date: find the star by name."])
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"insertDimension": {
        "range": {"sheetId": meta[WK]["sheetId"], "dimension": "ROWS", "startIndex": end, "endIndex": end + len(rows)},
        "inheritFromBefore": True}}]}).execute()
    gs.update_cells(sid, {f"{q(WK)}!A{end + 1}:J{end + len(rows)}": rows},
                    expect={f"{q(WK)}!A{end + 1}": "", f"{q(WK)}!A{end}": vals[end - 1][0]})
    return [end + 1, end + len(rows)]


def main():
    resume = "resume" in sys.argv[1:]
    write = "write" in sys.argv[1:] or resume
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    headers, rows = plan["headers"], plan["rows"]
    col = {h: i for i, h in enumerate(headers)}
    nrows, ncols, nsys = len(rows) + 1, len(headers), plan["n_systems_columns"]
    far = max(((r[0], float(r[col["Distance (ly)"]])) for r in rows), key=lambda x: x[1])
    print(f"{TAB}: {len(rows)} rows x {ncols} columns; {len(plan['inferred'])} orange cells; "
          f"{len(plan['wikipedia'])} pink cells; {len(plan['notes'])} check notes; farthest {far}")
    if not write:
        return
    gs, sid, api = sheets()
    meta = {s["properties"]["title"]: s["properties"] for s in
            api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]}
    last = f"{letter(ncols - 1)}{nrows}"
    if resume:
        tid = meta[TAB]["sheetId"]
    else:
        assert TAB not in meta, f"{TAB} already exists"
        after, source = meta[AFTER], meta[SYS]
        res = api.batchUpdate(spreadsheetId=sid, body={"requests": [{"addSheet": {"properties": {
            "title": TAB, "index": after["index"] + 1,
            "gridProperties": {"rowCount": nrows, "columnCount": ncols, "frozenRowCount": 1, "frozenColumnCount": 1}}}}]}
                              ).execute()
        tid = res["replies"][0]["addSheet"]["properties"]["sheetId"]
        gs.invalidate_cache(sid)
        # The header's look from the Systems tab; its first header cell's look for the added columns.
        api.batchUpdate(spreadsheetId=sid, body={"requests": [
            {"copyPaste": {"source": rng(source["sheetId"], 0, 1, 0, nsys), "destination": rng(tid, 0, 1, 0, nsys),
                           "pasteType": "PASTE_FORMAT"}},
            {"copyPaste": {"source": rng(source["sheetId"], 0, 1, 0, 1), "destination": rng(tid, 0, 1, nsys, ncols),
                           "pasteType": "PASTE_FORMAT"}}]}).execute()
        last = f"{letter(ncols - 1)}{nrows}"
        gs.update_cells(sid, {f"{q(TAB)}!A1:{last}": [headers] + rows},
                        expect={f"{q(TAB)}!A1": "", f"{q(TAB)}!A2": "", f"{q(TAB)}!{last}": ""})
        # The Systems tab's formulas (luminosity class, the eight bands), each pointed at its own row.
        formulas = {}
        for h in plan["formula_headers"]:
            c = letter(col[h])
            formulas[f"{q(TAB)}!{c}2:{c}{nrows}"] = [
                [re.sub(r"\$([A-Z]{1,2})2(?![0-9])", rf"$\g<1>{n}", plan["formulas"][h])] for n in range(2, nrows + 1)]
        gs.update_cells(sid, formulas, value_input="USER_ENTERED",
                        expect={k.split(":")[0]: "" for k in formulas})
        grey = {"style": "SOLID", "color": gs._hex_to_color(GREY_RULE)}
        widths = [{"updateDimensionProperties": {
            "range": {"sheetId": tid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": WIDE.get(h, 105)}, "fields": "pixelSize"}} for i, h in enumerate(headers)]
        api.batchUpdate(spreadsheetId=sid, body={"requests": widths + [
            {"updateBorders": {"range": rng(tid, 1, nrows, 0, ncols), "top": grey, "bottom": grey, "left": grey,
                               "right": grey, "innerHorizontal": grey, "innerVertical": grey}},
            {"repeatCell": {"range": rng(tid, 1, nrows, 0, ncols), "cell": {"userEnteredFormat": {
                "verticalAlignment": "TOP", "wrapStrategy": "CLIP"}},
                "fields": "userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy"}},
            {"setBasicFilter": {"filter": {"range": rng(tid, 0, nrows, 0, ncols)}}},
        ]}).execute()

    # Boxes and notes, by name: column A re-read.
    names = [r[0] for r in gs.read_cells(sid, [f"{q(TAB)}!A2:A{nrows}"])[f"{q(TAB)}!A2:A{nrows}"]]
    assert names == [r[0] for r in rows], "column A is not the plan's order"
    at = {n: i + 2 for i, n in enumerate(names)}

    def cell(key):
        name, h = key.split("|", 1)
        return f"{q(TAB)}!{letter(col[h])}{at[name]}"
    pink = [cell(f"{w['name']}|{w['header']}") for w in plan["wikipedia"]]
    orange = [cell(k) for k in plan["inferred"] if cell(k) not in pink]
    for s in range(0, 0 if resume else len(orange), 200):
        gs.set_border(sid, orange[s:s + 200], gs.INFERRED_BORDER)
    for s in range(0, 0 if resume else len(pink), 200):
        gs.set_border(sid, pink[s:s + 200], gs.WIKIPEDIA_BORDER)
    notes = {cell(k): n for k, n in plan["inferred"].items()}
    notes.update({cell(k): n for k, n in plan["notes"].items()})
    notes.update({cell(f"{w['name']}|{w['header']}"): f"WIKIPEDIA: {w['url']} -- citing {w['source']}"
                  for w in plan["wikipedia"]})
    items = list(notes.items())
    for s in range(0, 0 if resume else len(items), 300):
        gs.set_note(sid, dict(items[s:s + 300]))

    # Read back: every typed value, the formulas' results, and the boxes.
    back = api.values().get(spreadsheetId=sid, range=f"{q(TAB)}!A1:{last}",
                            valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
    skip = {col[h] for h in plan["formula_headers"]}
    for i, (b, w) in enumerate(zip(back, [headers] + rows)):
        b = list(b) + [""] * (ncols - len(b))
        for j, (x, y) in enumerate(zip(b, w)):
            if i and j in skip:
                assert not str(x).startswith("#"), f"row {i + 1} {headers[j]}: formula error {x!r}"
                continue
            if not (x == y or (isinstance(x, (int, float)) and isinstance(y, (int, float)) and abs(x - y) < 1e-9)):
                raise AssertionError(f"row {i + 1} {headers[j]}: wrote {y!r}, reads {x!r}")
    borders = {}
    for r0 in range(1, nrows + 1, 10):
        borders.update(gs.get_borders(sid, f"{q(TAB)}!A{r0}:{letter(ncols - 1)}{min(r0 + 9, nrows)}"))
    assert len(gs.get_notes(sid, f"{q(TAB)}!A1:{last}")) == len(notes), "notes differ from the plan"

    def sides(a1):
        return [str((borders[a1].get(x) or (None,))[0] or "").upper() for x in ("top", "bottom", "left", "right")]
    borders = {k.split("!")[-1]: v for k, v in borders.items()}
    want_o, want_p = {c.split("!")[-1] for c in orange}, {c.split("!")[-1] for c in pink}
    # An edge two boxes share holds one colour, and pink was drawn last: an orange cell beside a pink
    # one reads orange on its other sides and nothing on the shared one.
    assert all(set(sides(c)) == {"FF3399"} for c in want_p), "a Wikipedia cell is not boxed pink"
    assert all(sides(c).count("FF9900") >= 2 and set(sides(c)) <= {"FF9900", "FF3399", ""} for c in want_o),         "an inferred cell is not boxed orange"
    assert not [c for c in borders if c not in want_o | want_p and set(sides(c)) <= {"FF9900", "FF3399"}],         "a cell outside the plan is boxed"

    sp_cols = column_table_rows(gs, api, sid, meta)
    sp = append_rows(gs, api, sid, SP, sp_lines(plan, len(orange), len(pink), far))
    wk = wikipedia_rows(gs, api, sid, meta, plan["wikipedia"], cell) if plan["wikipedia"] else None
    lv = api.values().get(spreadsheetId=sid, range=f"{q(LG)}!A1:A3000").execute().get("values", [])
    row = len(lv) + 2
    gs.update_cells(sid, {f"{q(LG)}!A{row}": [[
        f"100 BRIGHTEST STARS ({DATE}): the tab '{TAB}' lists the hundred brightest points of light in the night sky, "
        "ranked by apparent V magnitude, with each one's rank by true luminosity. Orange cells are computed, pink "
        f"ones are from Wikipedia. Sources on Sources & Provenance under '100 BRIGHTEST STARS TAB ADDED, {DATE}'."]]},
        expect={f"{q(LG)}!A{row}": ""})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(sid)
    log = {"at": now(), "tab": TAB, "sheet_id": tid, "rows": len(rows), "cols": ncols, "orange": len(orange),
           "pink": len(pink), "notes": len(notes), "sp_column_rows": sp_cols, "sp_block": sp, "wikipedia_rows": wk,
           "legend_row": row, "title": title, "farthest": far}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log, ensure_ascii=False))


if __name__ == "__main__":
    main()
