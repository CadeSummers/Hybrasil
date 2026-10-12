# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Put the Planetless 4+ Stars rows back in the order they had before widen_filters re-set the tab's filter.

    python restore_order.py          plan: how many rows are out of place; touches nothing
    python restore_order.py write    sort them back, verify, provenance line, rename

Setting a basic filter again re-applies its stored sort (Luminosity descending, then Distance).  On 9 Oct 2026 that
re-sorted the tab's rows by luminosity, scattering each system's rows, and the sort moved values and notes but not
borders: 1,879 orange / pink provenance boxes were left on other stars' rows.  Sorting the rows back by their old
position (live.json, read before any write) returns every value to the row whose borders are its own.

The old position goes into a helper column after the last, the data rows are sorted by it, and the column is
deleted.  Rows are matched by name + Gaia id, never by row number.
"""
import sys

from common import LIVE, SP, TABS, key_of, letter, load, now, q, read_tab, save, sheets, WRITE_LOG
from write import append_sp, sheet_meta, TODAY

T = TABS["planetless"]


def main():
    write = "write" in sys.argv[1:]
    gs, sid, api = sheets()
    old = load(LIVE)["tabs"]["planetless"]
    ocol = {k: i for i, k in enumerate(old["headers"])}
    want = [key_of(r, ocol, T) for r in old["rows"]]
    h, rows = read_tab(api, sid, T["tab"])
    col = {k: i for i, k in enumerate(h)}
    now_keys = [key_of(r, col, T) for r in rows]
    assert sorted(now_keys) == sorted(want) and len(set(want)) == len(want), "the tab's rows are not the same set"
    moved = sum(1 for a, b in zip(now_keys, want) if a != b)
    print(f"{T['tab']}: {moved} of {len(rows)} rows out of their old place")
    if not moved or not write:
        return
    props = sheet_meta(api, sid)[T["tab"]]
    tid, ncols = props["sheetId"], props["gridProperties"]["columnCount"]
    pos = {k: i for i, k in enumerate(want)}
    helper = ncols                                   # a new last column
    api.batchUpdate(spreadsheetId=sid, body={"requests": [
        {"appendDimension": {"sheetId": tid, "dimension": "COLUMNS", "length": 1}}]}).execute()
    gs.update_cells(sid, {f"{q(T['tab'])}!{letter(helper)}2:{letter(helper)}{len(rows) + 1}":
                          [[pos[k]] for k in now_keys]},
                    expect={f"{q(T['tab'])}!{letter(helper)}2": ""})
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"sortRange": {
        "range": {"sheetId": tid, "startRowIndex": 1, "endRowIndex": len(rows) + 1,
                  "startColumnIndex": 0, "endColumnIndex": helper + 1},
        "sortSpecs": [{"dimensionIndex": helper, "sortOrder": "ASCENDING"}]}}]}).execute()
    h2, rows2 = read_tab(api, sid, T["tab"])
    hv = api.values().get(spreadsheetId=sid, range=f"{q(T['tab'])}!{letter(helper)}2:{letter(helper)}"
                          f"{len(rows) + 1}", valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
    assert [int(v[0]) for v in hv] == list(range(len(rows))), "helper column not in order"
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"deleteDimension": {"range": {
        "sheetId": tid, "dimension": "COLUMNS", "startIndex": helper, "endIndex": helper + 1}}}]}).execute()
    gs.invalidate_cache(sid)
    h3, rows3 = read_tab(api, sid, T["tab"])
    col3 = {k: i for i, k in enumerate(h3)}
    assert [key_of(r, col3, T) for r in rows3] == want, "order not restored"
    w = len(old["headers"])
    assert [r[:w] for r in rows3] == [(r + [""] * w)[:w] for r in old["rows"]], "a cell differs from before"
    lines = ["", f"{TODAY}: PLANETLESS 4+ STARS ROW ORDER RESTORED. Re-setting the tab's filter over the new "
             "existence columns re-applied its stored sort (Luminosity descending, then Distance), which moved "
             f"{moved} rows -- values and notes, but not borders. The rows were sorted back to their order as read "
             "before the edit (data/existence/live.json) through a temporary helper column, now deleted, so every "
             "value is again on the row whose provenance borders are its own; every cell checked equal to the "
             "pre-edit read. Script: data/existence/restore_order.py. NOTE: the filter still stores that sort, so "
             "setting the filter again, or Data > Sort with it, re-sorts the tab and strands the borders."]
    sp = append_sp(gs, api, sid, lines)
    title = gs.rename_workbook(None, gs.versioned_title())
    log = load(WRITE_LOG, {"runs": []})
    log.setdefault("restore_order", []).append({"at": now(), "moved": moved, "sp_rows": sp, "title": title})
    save(WRITE_LOG, log)
    print(f"restored {moved} rows; S&P {sp}; {title}")


if __name__ == "__main__":
    main()
