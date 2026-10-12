# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Planetless 4+ Stars: put BM:BT back with their rows after a filter sort split the tab (9 Oct 2026).

    python realign_planetless_sort.py          plan: check the damage is what it was; touches nothing
    python realign_planetless_sort.py write    move the cells, verify, provenance, rename

Between 10:06 and the afternoon of 9 Oct 2026 the tab was sorted through its basic filter (column P descending,
then E). The filter spans A:BL, so the sort moved A:BL and left BM:BT -- Time of periastron, RA, Dec, Position
source, Barycentre from, Barycentre offset, Argument of periastron refers to, Drawing status -- in the old order:
every row carried another star's eight cells. The sort order is kept; BM:BT follow it. The old order is the 10:06
catalog cache, saved as planetless_before_sort_cache.json. Each row's eight cells are copyPasted (values, notes,
borders, formats) from a scratch copy of the old block to the row that now holds the same star, matched by name.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
import migrate_bds as M  # noqa: E402

gs, q, letter, API, SID = M.gs, M.q, M.letter, M.API, M.SID
PLAN = "write" not in sys.argv[1:]
PL = M.PL
LOG = HERE / "realign_planetless_sort_log.json"
OLD = json.loads((HERE / "planetless_before_sort_cache.json").read_text(encoding="utf-8"))["tab"]
FIRST, LAST = "BM", "BT"                          # the columns the filter left behind


def col(a):
    return sum((ord(ch) - 64) * 26 ** i for i, ch in enumerate(reversed(a))) - 1


C0, C1 = col(FIRST), col(LAST) + 1


def check(live, old, aligned):
    """A:BL matches the old tab by star name; BM:BT matches it by name if aligned, else by position."""
    h = live[0]
    assert h == old[0], "headers changed"
    by_name = {r[1]: r for r in old[1:]}
    assert len(by_name) == len(old) - 1 == len(live) - 1, "row count or names changed"

    def cell(r, j):
        return str(r[j]) if j < len(r) else ""
    for i, r in enumerate(live[1:], start=1):
        o = by_name[r[1]]
        assert all(cell(r, j) == cell(o, j) for j in range(C0)), ("A:BL moved", r[1])
        ref = o if aligned else old[i]
        assert all(cell(r, j) == cell(ref, j) for j in range(C0, C1)), ("BM:BT", r[1], aligned)


def main():
    live = gs.fetch_workbook(SID)["tabs"][PL]           # the same rendering as the cache
    check(live, OLD, aligned=False)
    old_row = {r[1]: i + 1 for i, r in enumerate(OLD) if i}
    moves = [(old_row[r[1]], i + 1) for i, r in enumerate(live) if i]
    print(f"damage as diagnosed: A:BL sorted, {FIRST}:{LAST} in the old order; {len(moves)} rows, "
          f"{sum(1 for a, b in moves if a != b)} to move")
    if PLAN:
        return

    old_notes = gs.get_notes(SID, f"{q(PL)}!{FIRST}2:{LAST}{len(OLD)}")
    props = {s["properties"]["title"]: s["properties"] for s in
             API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}[PL]
    sid, ncol, nrow = props["sheetId"], props["gridProperties"]["columnCount"], len(OLD)
    width = C1 - C0
    rng = lambda r0, r1, c0: {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,  # noqa: E731
                              "startColumnIndex": c0, "endColumnIndex": c0 + width}
    # 1. a scratch copy of the old block, past the last column
    API.batchUpdate(spreadsheetId=SID, body={"requests": [
        {"appendDimension": {"sheetId": sid, "dimension": "COLUMNS", "length": width}},
        {"copyPaste": {"source": rng(1, nrow, C0), "destination": rng(1, nrow, ncol), "pasteType": "PASTE_NORMAL"}},
    ]}).execute()
    # 2. each star's eight cells to the row that now holds it
    API.batchUpdate(spreadsheetId=SID, body={"requests": [
        {"copyPaste": {"source": rng(a - 1, a, ncol), "destination": rng(b - 1, b, C0), "pasteType": "PASTE_NORMAL"}}
        for a, b in moves]}).execute()
    # 3. scratch columns gone
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"deleteDimension": {"range": {
        "sheetId": sid, "dimension": "COLUMNS", "startIndex": ncol, "endIndex": ncol + width}}}]}).execute()
    gs.invalidate_cache(SID)

    live = gs.fetch_workbook(SID)["tabs"][PL]           # the same rendering as the cache
    check(live, OLD, aligned=True)
    new_notes = gs.get_notes(SID, f"{q(PL)}!{FIRST}2:{LAST}{nrow}")
    for a, b in moves:
        for c in range(C0, C1):
            assert old_notes.get(f"{letter(c)}{a}", "") == new_notes.get(f"{letter(c)}{b}", ""), ("note", a, b, c)
    print("verified: every row's BM:BT values and notes are its own star's again")

    sp = ["", "PLANETLESS 4+ STARS: A SORT THAT SPLIT THE ROWS, REPAIRED 9 OCT 2026",
          "  The tab was sorted through its basic filter (P descending, then E) on 9 Oct 2026. The filter spans A:BL, "
          "so BM:BT (Time of periastron, RA, Dec, Position source, Barycentre from, Barycentre offset, Argument of "
          "periastron refers to, Drawing status) stayed in the old order and every row carried another star's eight "
          "cells. Repaired the same day: the sort order is kept, and each star's BM:BT cells (values, notes, borders) "
          "were moved to its new row by name from the 10:06 catalog cache. Script: "
          "data/star_counts/realign_planetless_sort.py. The filter still spans A:BL, so a filter sort will do this "
          "again until it is widened."]
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(M.SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(M.SP)}!A{end}"])[f"{q(M.SP)}!A{end}"][0][0].strip()
    sp0, sp1 = end + 1, end + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(M.SP)}!A{sp0}:A{sp1}": [[x] for x in sp]},
                    expect={f"{q(M.SP)}!A{i}": "" for i in (sp0, sp1)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps({"moves": moves, "sp_rows": [sp0, sp1], "title": title}, indent=1), encoding="utf-8")
    print("done:", title, [sp0, sp1])


if __name__ == "__main__":
    main()
