# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""P0: freeze what the Known within 100ly tab holds now, keyed by name + Gaia id.

    python targets.py          read the live tab -> targets.json (re-running overwrites it only if P3 has not run)

Each record: name, Gaia DR3 source_id, RA/Dec, distance, Plotted, and the current value of every motion column.
'blank' lists the columns this pipeline may fill; a filled cell is never touched. The Sun is skipped.
"""
from collections import Counter

from common import (TARGETS, TARGET_COLS, H_NAME, H_PLOT, H_DIST, H_SID, H_RA, H_DE, H_KS, blank, done, mark,
                    num, read_known, row_key, save, sheets)


def main():
    if done("P3_write"):
        raise SystemExit("P3 has written to the sheet; targets.json is the record of the cells as they were. "
                         "Not overwriting it.")
    gs, sid, api = sheets()
    title = api.get(spreadsheetId=sid, fields="properties.title").execute()["properties"]["title"]
    h, rows = read_known(api, sid)
    col = {k: i for i, k in enumerate(h)}
    for need in TARGET_COLS + (H_NAME, H_PLOT, H_DIST, H_SID, H_RA, H_DE, H_KS):
        assert need in col, need
    out, keys = [], Counter()
    for r in rows:
        name = str(r[col[H_NAME]]).strip()
        if not name or name == "Sun":
            continue
        gaia = str(r[col[H_SID]]).strip()
        k = row_key(name, gaia)
        keys[k] += 1
        have = {c: (None if blank(r[col[c]]) else r[col[c]]) for c in TARGET_COLS}
        out.append({
            "key": k, "name": name, "gaia": gaia if gaia.isdigit() else None,
            "ra": num(r[col[H_RA]]), "dec": num(r[col[H_DE]]), "dist_ly": num(r[col[H_DIST]]),
            "plotted": r[col[H_PLOT]] is True or str(r[col[H_PLOT]]).upper() == "TRUE",
            "kin_source": None if blank(r[col[H_KS]]) else str(r[col[H_KS]]),
            "have": have, "blank": [c for c in TARGET_COLS if have[c] is None],
        })
    dup = [k for k, n in keys.items() if n > 1]
    assert not dup, f"rows share a name + Gaia id: {dup[:10]}"
    todo = [t for t in out if t["blank"]]
    save(TARGETS, {"read_from": title, "headers": h, "rows": out})
    mark("P0_targets", "done", sheet=title, rows=len(out), rows_with_blanks=len(todo),
         with_gaia=sum(1 for t in todo if t["gaia"]), plotted_with_blanks=sum(1 for t in todo if t["plotted"]))
    print(f"{title}: {len(out)} rows (Sun skipped); {len(todo)} with a blank motion cell; "
          f"{sum(1 for t in todo if t['gaia'])} of those have a Gaia DR3 id; "
          f"{sum(1 for t in todo if t['plotted'])} are Plotted rows")


if __name__ == "__main__":
    main()
