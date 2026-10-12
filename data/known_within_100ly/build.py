# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create the "Known within 100ly" tab: every catalogued object within 100 ly, plotted or not.

    python build.py plan     print the layout and counts; touches nothing
    python build.py write    create the tab, write it, carry the markings, provenance, rename

Rows are the entries of 'data/Nearby stars within 100 light years.xlsx' (Gaia DR3 + CNS5, one row per
catalogued object, in its order: nearest first). Columns are the Systems tab's, with "Plotted" and
"Last Updated" inserted after "Nickname (IAU)".

  * Plotted by a Systems row (the host of a drawn system): that row's values, copied.
  * Plotted by a Multi-stars row (a companion, or a host whose Gaia source is the component's): that
    row's values under the matching Systems header; 'Star (component)' fills 'System / Host',
    'Mass'/'Luminosity' fill the 'Host ...' columns. RA/Dec come from the file, since Multi-stars has none.
  * Not plotted: identity only, from the file -- name, distance, RA/Dec, Gaia DR3 source_id.

Values are copied, not linked: this is a snapshot as of "Last Updated". Pink and orange markings and
their notes travel with a copied value, so a copy says what its original says. match.json (match.py)
decides which entry is which plotted star.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from hybrasil.data import google_sheets as gs  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402
from googleapiclient.http import HttpRequest  # noqa: E402

from match import load_file, gaia_id, SY, MS  # noqa: E402

_execute = HttpRequest.execute


def _execute_with_retry(self, *a, **k):
    """The Sheets API allows 60 reads a minute; wait out a 429 rather than stop half-way."""
    for attempt in range(8):
        try:
            return _execute(self, *a, **k)
        except HttpError as e:
            if e.resp.status != 429 or attempt == 7:
                raise
            time.sleep(35)


HttpRequest.execute = _execute_with_retry

SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
KN, SP = "Known within 100ly", "Sources & Provenance"
TODAY = "2026-09-28"
LOG = HERE / "write_log.json"
PLAN = sys.argv[1:] == ["plan"]
GREY_RULE = "FFBFBFBF"
MARKS = {"FF3399": gs.WIKIPEDIA_BORDER, "FF9900": gs.INFERRED_BORDER}
RENAME = {"Star (component)": "System / Host", "Mass (M-sun)": "Host mass (M-sun)",
          "Luminosity (L-sun)": "Host luminosity (L-sun)"}


def q(t):
    return "'" + t.replace("'", "''") + "'"


def letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def ix(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def split(a1):
    col = "".join(c for c in a1 if c.isalpha())
    return col, int(a1[len(col):])


def main():
    titles = [s["properties"]["title"] for s in API.get(spreadsheetId=SID, fields="sheets.properties.title"
                                                        ).execute()["sheets"]]
    assert KN not in titles, f"{KN} already exists"
    wb = gs.get_workbook(refresh=True)
    sy_rows, ms_rows = wb["tabs"][SY], wb["tabs"][MS]
    sy_h, ms_h = sy_rows[0], ms_rows[0]
    headers = sy_h[:2] + ["Plotted", "Last Updated"] + sy_h[2:]
    col = {h: i for i, h in enumerate(headers)}
    assert headers[0] == "System / Host" and headers[1] == "Nickname (IAU)" and len(set(headers)) == len(headers)

    # sheet row (1-based) of each plotted star on its own tab
    sy_at = {r[0]: n for n, r in enumerate(sy_rows[1:], start=2) if r and str(r[0]).strip()}
    ms_at = {r[1]: n for n, r in enumerate(ms_rows[1:], start=2) if r and len(r) > 1 and str(r[1]).strip()}
    m = json.loads((HERE / "match.json").read_text(encoding="utf-8"))
    entries = load_file()
    assert m["entries"] == len(entries)

    grid, source_of = [], {}           # source_of: new row -> (tab, source row, {src col idx: new col idx})
    for i, e in enumerate(entries):
        row = [""] * len(headers)
        hit = m["match"].get(str(i))
        r = i + 2
        if hit and hit["tab"] == SY:
            src = sy_rows[sy_at[hit["name"]] - 1]
            cmap = {j: col[h] for j, h in enumerate(sy_h)}
            source_of[r] = (SY, sy_at[hit["name"]], cmap)
        elif hit:
            src = ms_rows[ms_at[hit["name"]] - 1]
            cmap = {j: col[RENAME.get(h, h)] for j, h in enumerate(ms_h) if RENAME.get(h, h) in col}
            source_of[r] = (MS, ms_at[hit["name"]], cmap)
        if hit:
            for j, k in cmap.items():
                v = src[j] if j < len(src) else ""
                row[k] = "" if v is None else v
            if hit["tab"] == MS:
                for h, key in (("RA (deg, ICRS)", "RA (deg)"), ("Dec (deg, ICRS)", "Dec (deg)")):
                    if row[col[h]] in ("", None) and e[key] is not None:
                        row[col[h]] = round(e[key], 6)
        else:
            name = f"{e['Other ID']} {e['Component']}" if e.get("Other ID") and e.get("Component") \
                else (e.get("Other ID") or e["Catalog ID"])
            row[col["System / Host"]] = name
            row[col["Distance (ly)"]] = round(e["Distance (ly)"], 2)
            if e["RA (deg)"] is not None:
                row[col["RA (deg, ICRS)"]] = round(e["RA (deg)"], 6)
                row[col["Dec (deg, ICRS)"]] = round(e["Dec (deg)"], 6)
        if str(e["Catalog ID"]).startswith("Gaia DR3") and row[col["Gaia DR3 source_id"]] in ("", None):
            row[col["Gaia DR3 source_id"]] = gaia_id(e["Catalog ID"])
        if row[col["Gaia DR3 source_id"]] not in ("", None):
            row[col["Gaia DR3 source_id"]] = str(row[col["Gaia DR3 source_id"]])     # 19 digits: keep as text
        row[col["Plotted"]] = bool(hit)
        row[col["Last Updated"]] = TODAY
        grid.append(row)

    # markings and notes on every copied cell
    marks, notes = {}, {}
    for tab, width in ((SY, len(sy_h)), (MS, len(ms_h))):
        last = len(wb["tabs"][tab])
        # in slices: one whole tab's grid data trips httplib2's decompression-ratio limit
        b, n = {}, {}
        for r0 in range(1, last + 1, 100):
            a1 = f"{q(tab)}!A{r0}:{letter(width - 1)}{min(r0 + 99, last)}"
            b.update(gs.get_borders(SID, a1))
            n.update(gs.get_notes(SID, a1))
        for r, (t2, sr, cmap) in source_of.items():
            if t2 != tab:
                continue
            for j, k in cmap.items():
                a1 = f"{letter(j)}{sr}"
                colours = {c for c, _ in (b.get(a1) or {}).values()}
                for c in colours & set(MARKS):
                    marks.setdefault(MARKS[c], []).append(f"{q(KN)}!{letter(k)}{r}")
                if a1 in n:
                    notes[f"{q(KN)}!{letter(k)}{r}"] = n[a1]

    n_plot = sum(1 for g in grid if g[col["Plotted"]])
    unplotted = {"systems": m["unmatched"]["systems"],
                 "stars": [s for s in m["unmatched"]["stars"] if s not in m["unmatched"]["systems"]]}
    from collections import Counter
    how = Counter(v["how"] for v in m["match"].values())
    lines = [
        "",
        f"KNOWN WITHIN 100LY, 28 SEPTEMBER 2026: NEW TAB, {len(grid):,} ROWS -- EVERY CATALOGUED OBJECT WITHIN 100 LY.",
        "Builder: data/known_within_100ly/build.py (matching: match.py -> match.json); log write_log.json.",
        "SOURCE OF THE ROWS: data/Nearby stars within 100 light years.xlsx, compiled 26 Sep 2026 from ESA Gaia DR3",
        "  gaia_source (ARI TAP, parallax >= 32.6156 mas, i.e. <= 100 ly by inverse parallax) plus the Fifth Catalogue",
        "  of Nearby Stars, CNS5 (GAVO TAP, cns5.main, 25 pc only) for entries with no selected Gaia DR3 source.",
        "  10,041 Gaia DR3 + 669 CNS5 + the Sun. One row per catalogued object, so a resolved binary is two rows and an",
        "  unresolved one (e.g. 'GJ 559 AB', alf Cen A+B in CNS5) is one. Order: the file's, nearest first.",
        "COLUMNS: the Systems tab's, with 'Plotted' (TRUE/FALSE) and 'Last Updated' after 'Nickname (IAU)'.",
        f"PLOTTED = TRUE ({n_plot} rows): the object is drawn by the app, as a Systems row (a system's host) or a",
        "  Multi-stars row (any star of a drawn system). Its values are COPIED from that row as of 'Last Updated' --",
        "  not linked, so an edit there does not reach here. A Multi-stars row fills the Systems-named columns",
        "  (component -> System / Host, Mass -> Host mass, Luminosity -> Host luminosity); its RA/Dec come from the",
        "  file. Pink and orange boxes and their notes are carried with each copied value.",
        f"  Matched by Gaia DR3 source_id ({how['gaia']}); by position, the row's SIMBAD RA/Dec carried to J2016 with",
        f"  its own proper motion, < 3 arcsec and < 10% in distance ({how['position']}); by GJ name + component",
        f"  ({how['name']}); and by SIMBAD identifiers (astroquery query_objectids, 28 Sep 2026) for the rest",
        f"  ({how['simbad']}: e.g. Proxima Cen = Gaia DR3 5853498713190525696, alf Cen A = CNS5 3627 'GJ 559 AB').",
        "PLOTTED = FALSE: identity only, from the file -- name (GJ/HIP 'Other ID' + component, else the Gaia or",
        "  CNS5 catalogue ID), distance (1/parallax), RA/Dec (Gaia DR3 epoch 2016.0) and Gaia DR3 source_id.",
        "  Every stellar column is blank for now.",
        "PLOTTED BUT NOT ON THIS TAB (the file has no separate entry for them):",
        "  Systems rows beyond 100 ly on Gaia DR3's parallax: " + ", ".join(
            n for n in unplotted["systems"] if n != "nu Oct A") + ".",
        "  nu Oct A (too bright for Gaia DR3; CNS5 stops at 25 pc), and " + str(len(unplotted["stars"])) +
        " Multi-stars companions,",
        "  mostly unresolved from their primary in Gaia DR3: " + ", ".join(unplotted["stars"]) + ".",
        "NOT READ BY THE CODE: catalog_loader.KNOWN_SIGNATURE ('System / Host' + 'Plotted') skips this tab, which",
        "  would otherwise match the Systems signature and add every row as a system.",
    ]

    if PLAN:
        print(f"{len(grid)} rows x {len(headers)} cols; plotted {n_plot}; markings "
              f"{ {k: len(v) for k, v in marks.items()} }; notes {len(notes)}")
        print("headers:", headers[:6], "...", headers[-4:])
        for g in grid[:4] + grid[150:151]:
            print("  ", [str(x)[:22] for x in g[:8]], "...", [str(x)[:22] for x in g[-4:]])
        print("\n".join(lines))
        return

    # 1. the tab, sized to the data, after Systems
    sy_meta = next(s["properties"] for s in API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]
                   if s["properties"]["title"] == SY)
    nrows, ncols = len(grid) + 1, len(headers)
    res = API.batchUpdate(spreadsheetId=SID, body={"requests": [{"addSheet": {"properties": {
        "title": KN, "index": sy_meta["index"] + 1,
        "gridProperties": {"rowCount": nrows, "columnCount": ncols, "frozenRowCount": 1, "frozenColumnCount": 1}}}}]}
                           ).execute()
    kid = res["replies"][0]["addSheet"]["properties"]["sheetId"]
    gs.invalidate_cache(SID)

    # 2. values, in chunks (RAW: text stays text, TRUE/FALSE stay booleans)
    gs.update_cells(SID, {f"{q(KN)}!A1:{letter(ncols - 1)}1": [headers]})
    for s in range(0, len(grid), 2000):
        chunk = grid[s:s + 2000]
        gs.update_cells(SID, {f"{q(KN)}!A{s + 2}:{letter(ncols - 1)}{s + 1 + len(chunk)}": chunk})

    # 3. formatting: the Systems header's look, the plain grey rule, a filter
    def rng(sheet, r0, r1, c0, c1):
        return {"sheetId": sheet, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}
    sid_sy = sy_meta["sheetId"]
    grey = {"style": "SOLID", "color": gs._hex_to_color(GREY_RULE)}
    API.batchUpdate(spreadsheetId=SID, body={"requests": [
        {"copyPaste": {"source": rng(sid_sy, 0, 1, 0, 2), "destination": rng(kid, 0, 1, 0, 2), "pasteType": "PASTE_FORMAT"}},
        {"copyPaste": {"source": rng(sid_sy, 0, 1, 2, 3), "destination": rng(kid, 0, 1, 2, 4), "pasteType": "PASTE_FORMAT"}},
        {"copyPaste": {"source": rng(sid_sy, 0, 1, 2, len(sy_h)), "destination": rng(kid, 0, 1, 4, ncols),
                       "pasteType": "PASTE_FORMAT"}},
        {"updateBorders": {"range": rng(kid, 1, nrows, 0, ncols), "top": grey, "bottom": grey, "left": grey,
                           "right": grey, "innerHorizontal": grey, "innerVertical": grey}},
        {"setBasicFilter": {"filter": {"range": rng(kid, 0, nrows, 0, ncols)}}},
    ]}).execute()

    # 4. markings and notes, carried from the originals
    for colour, cells in marks.items():
        for s in range(0, len(cells), 200):
            gs.set_border(SID, cells[s:s + 200], colour)
    items = list(notes.items())
    for s in range(0, len(items), 300):
        gs.set_note(SID, dict(items[s:s + 300]))

    # 5. Sources & Provenance, below its last row (never values().append())
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    last = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{last}"])[f"{q(SP)}!A{last}"][0][0].strip()
    start, end = last + 1, last + len(lines)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log = {"tab": KN, "sheet_id": kid, "rows": len(grid), "plotted": n_plot, "sp_rows": [start, end],
           "marks": {k: len(v) for k, v in marks.items()}, "notes": len(notes), "title": title}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log, ensure_ascii=False))


if __name__ == "__main__":
    main()
