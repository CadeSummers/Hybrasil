# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write plan.json's Orbit Direction column onto the live sheet -- the only writer.

    python write.py            what it would do against the live tabs; touches nothing
    python write.py write      add the column to both tabs (header format copied from the last column), write
                               every planet row's cell, note and orange box, any spin-orbit cells plan.json fills,
                               widen each tab's basic filter over the column, add the Sources & Provenance rows,
                               rename the workbook, and log

Rows are found by planet name (case-sensitive: "HD 3651 b" and "HD 3651 B" are two rows) in a fresh read, never by a
stored row number, and each tab's names are re-read immediately before its write: a row that is no longer the planet
planned, or a target cell that is not blank, aborts before anything is written to that tab.  A planet row is any row
from 2 down to the first with no host -- the Planets tab's constants block below its planets is never touched.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("kinematics_common",
                                               ROOT / "data" / "known_within_100ly" / "kinematics" / "common.py")
_kin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_kin)
gs = None                                 # hybrasil.data.google_sheets, set by main()

PLAN = HERE / "plan.json"
LOG = HERE / "write_log.json"
SP = "Sources & Provenance"
HEADER = "Orbit Direction"
NAME_COL, HOST_COL = "Planet", "Host system (primary star)"
SPIN_COL = "Spin-orbit angle (deg, vs stellar spin axis)"
TODAY = datetime.date.today().isoformat()


def letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def q(tab: str) -> str:
    return "'" + tab.replace("'", "''") + "'"


def read_tab(api, sid, tab):
    vals = api.values().get(spreadsheetId=sid, range=q(tab), valueRenderOption="UNFORMATTED_VALUE"
                            ).execute().get("values", [])
    header = [str(h).strip() for h in vals[0]]
    w = len(header)
    rows = [list(r) + [""] * (w - len(r)) for r in vals[1:]]
    host = header.index(HOST_COL)
    n = 0
    while n < len(rows) and str(rows[n][host]).strip():
        n += 1
    return header, rows[:n]                      # the planet rows only: 2 .. n + 1


def props_of(api, sid):
    return {s["properties"]["title"]: s for s in api.get(
        spreadsheetId=sid, fields="sheets(properties(title,sheetId,gridProperties),basicFilter)").execute()["sheets"]}


def add_column(api, sid, tab, header, nrows):
    """The column after the tab's last header, formatted like that last column; returns its index."""
    s = props_of(api, sid)[tab]
    tid, ncols = s["properties"]["sheetId"], s["properties"]["gridProperties"]["columnCount"]
    first = len(header)
    reqs = []
    if first + 1 > ncols:
        reqs.append({"appendDimension": {"sheetId": tid, "dimension": "COLUMNS", "length": first + 1 - ncols}})
    reqs.append({"copyPaste": {
        "source": {"sheetId": tid, "startRowIndex": 0, "endRowIndex": nrows + 1,
                   "startColumnIndex": first - 1, "endColumnIndex": first},
        "destination": {"sheetId": tid, "startRowIndex": 0, "endRowIndex": nrows + 1,
                        "startColumnIndex": first, "endColumnIndex": first + 1},
        "pasteType": "PASTE_FORMAT"}})
    api.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()
    # PASTE_FORMAT copies the neighbour's orange boxes too: put the plain rule back on every planet row first
    # (data/existence/newcol_borders.py), so only the cells this script boxes carry one.
    plain = {"style": "SOLID", "color": gs._hex_to_color(gs.PLAIN_RULE)}
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"updateBorders": {
        "range": {"sheetId": tid, "startRowIndex": 1, "endRowIndex": nrows + 1,
                  "startColumnIndex": first, "endColumnIndex": first + 1},
        "top": plain, "bottom": plain, "left": plain, "right": plain, "innerHorizontal": plain}}]}).execute()
    gs.update_cells(sid, {f"{q(tab)}!{letter(first)}1": [[HEADER]]}, expect={f"{q(tab)}!{letter(first)}1": ""})
    return tid, first


def widen_filter(api, sid, tab, end_col):
    s = props_of(api, sid)[tab]
    f = s.get("basicFilter")
    if not f or f["range"].get("endColumnIndex", 0) >= end_col:
        return None
    if f.get("sortSpecs"):
        raise SystemExit(f"{tab}: the filter stores a sort; setting it again would re-sort the rows")
    old = f["range"]["endColumnIndex"]
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"setBasicFilter": {
        "filter": dict(f, range=dict(f["range"], endColumnIndex=end_col))}}]}).execute()
    return [old, end_col]


def cell_request(tid, r, c, value, note=None):
    data, fields = {"userEnteredValue": {"stringValue": value}}, ["userEnteredValue"]
    if note:
        data["note"] = note
        fields.append("note")
    return {"updateCells": {"range": {"sheetId": tid, "startRowIndex": r - 1, "endRowIndex": r,
                                      "startColumnIndex": c, "endColumnIndex": c + 1},
                            "rows": [{"values": [data]}], "fields": ",".join(fields)}}


def column_table_row(api, sid, title, row):
    """Append `row` to the COLUMN table that follows the S&P heading `title`; returns its row number."""
    vals = api.values().get(spreadsheetId=sid, range=f"{q(SP)}!A1:A400").execute()["values"]
    a = [str(r[0]).strip() if r else "" for r in vals]
    top = next(i for i, x in enumerate(a) if x.startswith(title))
    head = next(i for i in range(top, len(a)) if a[i] == "COLUMN")
    end = head + 1
    while end < len(a) and a[end]:
        end += 1
    if row[0] in a[head + 1:end]:
        return None
    tid = props_of(api, sid)[SP]["properties"]["sheetId"]
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"insertDimension": {
        "range": {"sheetId": tid, "dimension": "ROWS", "startIndex": end, "endIndex": end + 1},
        "inheritFromBefore": True}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{end + 1}:D{end + 1}": [row]},
                    expect={f"{q(SP)}!A{end + 1}": "", f"{q(SP)}!A{end}": a[end - 1]})
    return end + 1


def append_sp(api, sid, lines):
    props = props_of(api, sid)[SP]["properties"]
    last = props["gridProperties"]["rowCount"]
    start, end = last + 1, last + len(lines)
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
        "sheetId": props["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, end)})
    return [start, end]


def main():
    write = "write" in sys.argv[1:]
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    global gs
    gs, sid, api = _kin.sheets()             # with a retry on 429 and transient 5xx
    log = {"at": datetime.datetime.now().isoformat(timespec="seconds"), "tabs": {}}
    for tab, t in plan["tabs"].items():
        header, rows = read_tab(api, sid, tab)
        names = [str(r[header.index(NAME_COL)]).strip() for r in rows]
        planned = [c["planet"] for c in t["cells"]]
        assert sorted(names) == sorted(planned), (tab, set(names) ^ set(planned))
        assert len(set(names)) == len(names), (tab, "duplicate planet names")
        have = HEADER in header
        n_orange = sum(1 for c in t["cells"] if c.get("orange"))
        print(f"{tab}: {len(rows)} planet rows; column {'present' if have else 'to add as ' + letter(len(header))}; "
              f"{len(t['cells'])} cells, {n_orange} orange, {len(t.get('spin', []))} spin-orbit cells")
        if not write:
            continue
        assert not have, f"{tab} already has {HEADER}"
        tid, col = add_column(api, sid, tab, header, len(rows))
        gs.invalidate_cache(sid)
        # Names again, immediately before writing: the rows must still be the planets planned.
        header2, rows2 = read_tab(api, sid, tab)
        at = {str(r[header2.index(NAME_COL)]).strip(): i + 2 for i, r in enumerate(rows2)}
        assert set(at) == set(names) and header2[col] == HEADER, tab
        assert all(not str(r[col]).strip() for r in rows2), (tab, "the new column is not blank")
        reqs = []
        for c in t["cells"]:
            reqs.append(cell_request(tid, at[c["planet"]], col, c["value"], c.get("note")))
        spin_col = header2.index(SPIN_COL) if SPIN_COL in header2 else None
        for c in t.get("spin", []):
            cur = str(rows2[at[c["planet"]] - 2][spin_col]).strip()
            assert cur == c["expect"], (c["planet"], cur, c["expect"])
            reqs.append(cell_request(tid, at[c["planet"]], spin_col, c["value"], c.get("note")))
        for s in range(0, len(reqs), 300):
            api.batchUpdate(spreadsheetId=sid, body={"requests": reqs[s:s + 300]}).execute()
        orange = [f"{q(tab)}!{letter(col)}{at[c['planet']]}" for c in t["cells"] if c.get("orange")]
        orange += [f"{q(tab)}!{letter(spin_col)}{at[c['planet']]}" for c in t.get("spin", []) if c.get("orange")]
        if orange:
            gs.set_border(sid, orange, gs.INFERRED_BORDER)
        widened = widen_filter(api, sid, tab, col + 1)
        gs.invalidate_cache(sid)
        # Read back: every value, and the orange boxes by name.
        header3, rows3 = read_tab(api, sid, tab)
        got = {str(r[header3.index(NAME_COL)]).strip(): str(r[col]) for r in rows3}
        bad = [c["planet"] for c in t["cells"] if got.get(c["planet"]) != c["value"]]
        assert not bad, (tab, bad[:5])
        if orange:
            borders = gs.get_borders(sid, f"{q(tab)}!A1:{letter(len(header3) - 1)}{len(rows3) + 1}")
            boxed = {k.split("!")[-1] for k, b in borders.items()
                     if all("FF9900" in str((b.get(s) or (None,))[0] or "").upper()
                            for s in ("top", "bottom", "left", "right"))}
            missing = {o.split("!")[-1] for o in orange} - boxed
            assert not missing, (tab, sorted(missing)[:5])
        log["tabs"][tab] = {"column": letter(col), "cells": len(t["cells"]), "orange": len(orange),
                            "spin": len(t.get("spin", [])), "filter": widened}
    if not write:
        return
    log["sp_column_rows"] = [column_table_row(api, sid, title, row) for title, row in plan["sp_column_rows"]]
    log["sp_block"] = append_sp(api, sid, plan["sp_lines"])
    log["title"] = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(sid)
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log, ensure_ascii=False))


if __name__ == "__main__":
    main()
