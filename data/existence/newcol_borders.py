# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Audit (and with 'write', fix) the borders of the existence columns.

    python newcol_borders.py          count each border style in the new columns and their left neighbour
    python newcol_borders.py write    restore the plain rule on every new-column cell not meant to be orange

The columns were added with their left neighbour's format (write.py add_columns, PASTE_FORMAT), which copied that
column's orange provenance boxes too: an orange box in a new column on a row whose own cell was never inferred.  The
only orange cells meant to be there are the SIMBAD ids plan.json marks orange.  A cell is unmarked by restoring the
plain rule its unmarked neighbours wear, not by clearing it (docs/hybrasil-instructions.md).
"""
import re
import sys
from collections import Counter

from common import PLAN, SP, TABS, key_of, letter, load, now, q, read_tab, save, sheets, WRITE_LOG

ROWS_PER_READ = 1500


def borders(gs, sid, tab, c, last):
    out = {}
    for r0 in range(2, last + 1, ROWS_PER_READ):
        r1 = min(last, r0 + ROWS_PER_READ - 1)
        for a1, s in gs.get_borders(sid, f"{q(tab)}!{letter(c)}{r0}:{letter(c)}{r1}").items():
            out[int(re.match(r"[A-Z]+(\d+)", a1).group(1))] = s
    return out


def run(write):
    gs, sid, api = sheets()
    plan = load(PLAN)
    meta = {s["properties"]["title"]: s["properties"]["sheetId"]
            for s in api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]}
    fixed = {}
    for key, t in TABS.items():
        h, rows = read_tab(api, sid, t["tab"])
        col = {k: i for i, k in enumerate(h)}
        last = len(rows) + 1
        neighbour = col[t["new"][0]] - 1
        nb = borders(gs, sid, t["tab"], neighbour, last)
        plain = Counter(tuple(s.get("top") or ()) for s in nb.values()
                        if (s.get("top") or (None,))[0] not in ("FF9900", "FF3399")).most_common(1)
        plain = plain[0][0] if plain else (None, "SOLID")
        stray = []
        for hd in t["new"]:
            c = col[hd]
            for n, s in borders(gs, sid, t["tab"], c, last).items():
                if (s.get("top") or (None,))[0] in ("FF9900", "FF3399"):
                    k = key_of(rows[n - 2], col, t)
                    meant = plan["tabs"][key].get(k, {}).get("cells", {}).get(hd, {}).get("mark") == "orange"
                    if not meant:
                        stray.append((n, c, hd, k))
        print(f"{t['tab']}: plain rule {plain}; stray boxes {len(stray)} "
              f"{Counter(x[2] for x in stray)} e.g. {[(x[3], x[2]) for x in stray[:3]]}")
        if write and stray:
            colour, style = plain
            side = {"style": style or "SOLID",
                    "color": gs._hex_to_color(colour or gs.PLAIN_RULE)}
            api.batchUpdate(spreadsheetId=sid, body={"requests": [{"updateBorders": {
                "range": {"sheetId": meta[t["tab"]], "startRowIndex": n - 1, "endRowIndex": n,
                          "startColumnIndex": c, "endColumnIndex": c + 1},
                "top": side, "bottom": side, "left": side, "right": side}} for n, c, _, _ in stray]}).execute()
            fixed[t["tab"]] = len(stray)
    if write and fixed:
        log = load(WRITE_LOG, {"runs": []})
        log.setdefault("border_fix", []).append({"at": now(), "fixed": fixed})
        save(WRITE_LOG, log)
        print("restored the plain rule on", fixed)
    return fixed


if __name__ == "__main__":
    run("write" in sys.argv[1:])
