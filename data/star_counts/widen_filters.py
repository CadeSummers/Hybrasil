# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Widen the Planetless 4+ Stars and Planets filters to every column (9 Oct 2026).

    python widen_filters.py          plan: print each filter's range now and after; touches nothing
    python widen_filters.py write    widen, verify, provenance, rename

A sort through a basic filter moves only the filter's columns. Planetless 4+ Stars' filter spanned A:BL of A:BT, so a
sort on 9 Oct 2026 left BM:BT behind (realign_planetless_sort.py); Planets' spanned A:AP of A:AQ. Each filter is
set again with its own rows, criteria and sort specs, only its last column moved out to the grid's. No cell changes.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
import migrate_bds as M  # noqa: E402

gs, q, API, SID = M.gs, M.q, M.API, M.SID
PLAN = "write" not in sys.argv[1:]
LOG = HERE / "widen_filters_log.json"
TABS = [M.PL, M.PN]


def filters():
    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,gridProperties(columnCount)),basicFilter)"
                   ).execute()["sheets"]
    return {s["properties"]["title"]: (s["basicFilter"], s["properties"]["gridProperties"]["columnCount"])
            for s in meta if s["properties"]["title"] in TABS}


def main():
    before = filters()
    for t, (f, ncol) in before.items():
        print(f"{t}: columns {f['range'].get('startColumnIndex', 0)}..{f['range']['endColumnIndex']} of {ncol}, "
              f"rows {f['range'].get('startRowIndex', 0)}..{f['range'].get('endRowIndex')}, sort {f.get('sortSpecs')}")
    if PLAN:
        return

    values = {t: M.values(t) for t in TABS}
    API.batchUpdate(spreadsheetId=SID, body={"requests": [
        {"setBasicFilter": {"filter": dict(f, range=dict(f["range"], endColumnIndex=ncol))}}
        for f, ncol in before.values()]}).execute()
    gs.invalidate_cache(SID)

    after = filters()
    for t, (f, ncol) in after.items():
        old = before[t][0]
        assert f["range"]["endColumnIndex"] == ncol, (t, "not widened")
        assert {k: v for k, v in f["range"].items() if k != "endColumnIndex"} == \
               {k: v for k, v in old["range"].items() if k != "endColumnIndex"}, (t, "rows moved")
        assert f.get("sortSpecs") == old.get("sortSpecs") and f.get("filterSpecs") == old.get("filterSpecs"), t
        assert M.values(t) == values[t], (t, "a cell changed")
        print(f"verified {t}: filter spans all {ncol} columns; rows, sort and every cell as they were")

    sp = ["", "FILTERS WIDENED TO EVERY COLUMN, 9 OCT 2026",
          "  A sort through a basic filter moves only the filter's columns, which is how BM:BT of Planetless 4+ Stars "
          "were split from their rows on 9 Oct 2026 (see 'A SORT THAT SPLIT THE ROWS' above). Both filters that "
          "stopped short were set again to the full width, with their rows, criteria and sort order unchanged: "
          + "; ".join(f"{t} {before[t][0]['range']['endColumnIndex']} -> {after[t][1]} columns" for t in TABS)
          + ". No cell changed. Script: data/star_counts/widen_filters.py. A column added to either tab later must "
          "be inside the filter too."]
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
    LOG.write_text(json.dumps({"before": {t: v[0] for t, v in before.items()},
                               "after": {t: v[0] for t, v in after.items()}, "sp_rows": [sp0, sp1], "title": title},
                              indent=1), encoding="utf-8")
    print("done:", title, [sp0, sp1])


if __name__ == "__main__":
    main()
