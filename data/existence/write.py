# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Step 3, the only writer: put plan.json's cells onto the live sheet.

    python write.py plan      what would be written now, against the live tabs; touches nothing
    python write.py write     the columns (added after each tab's last, header format copied from its neighbour),
                              each tab's filter widened over them, the cells, the Sources & Provenance rows, the rename
    python write.py filters   only widen the three tabs' filters to every column (the first run of 9 Oct 2026
                              added the columns outside them), with its own provenance line and rename

Safe to re-run after a crash:
  * Rows are found by name + Gaia id in a fresh read, never by a stored row number.
  * Each chunk of rows is re-read immediately before it is written; any row that is no longer the star planned, or
    a target cell holding anything but blank or the planned value, aborts the run before that chunk is written.
  * A cell already holding its planned value is skipped, so a second run writes only what the first did not.
Marks: looked-up identifiers keep the column's plain rule; a SIMBAD id found by system name or position gets the
orange box (gs.INFERRED_BORDER) and an INFERRED: note.
"""
import datetime
import sys
from collections import Counter

from common import (H_CNS5, H_EXIST, H_REFS, H_SIMBAD, PLAN, SP, TABS, WRITE_LOG, blank, key_of, letter, load, now,
                    q, read_tab, save, sheets)

CHUNK_ROWS = 400
TODAY = datetime.date.today().isoformat()


def sheet_meta(api, sid):
    return {s["properties"]["title"]: s["properties"]
            for s in api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]}


def add_columns(gs, api, sid, t):
    """Append the tab's new columns that are not there yet, formatted like its last column. Returns their headers."""
    h, _ = read_tab(api, sid, t["tab"])
    missing = [c for c in t["new"] if c not in h]
    if not missing:
        return []
    props = sheet_meta(api, sid)[t["tab"]]
    tid, ncols = props["sheetId"], props["gridProperties"]["columnCount"]
    nrows = props["gridProperties"]["rowCount"]
    first = len(h)                                  # the first free column after the last header
    need = first + len(missing) - ncols
    reqs = []
    if need > 0:
        reqs.append({"appendDimension": {"sheetId": tid, "dimension": "COLUMNS", "length": need}})
    for j in range(len(missing)):
        reqs.append({"copyPaste": {
            "source": {"sheetId": tid, "startRowIndex": 0, "endRowIndex": nrows,
                       "startColumnIndex": first - 1, "endColumnIndex": first},
            "destination": {"sheetId": tid, "startRowIndex": 0, "endRowIndex": nrows,
                            "startColumnIndex": first + j, "endColumnIndex": first + j + 1},
            "pasteType": "PASTE_FORMAT"}})
    api.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()
    a1 = f"{q(t['tab'])}!{letter(first)}1:{letter(first + len(missing) - 1)}1"
    gs.update_cells(sid, {a1: [missing]},
                    expect={f"{q(t['tab'])}!{letter(first + j)}1": "" for j in range(len(missing))})
    return missing


def widen_filters(gs, api, sid):
    """Set each tab's basic filter again over every column, rows, criteria and sort unchanged.

    A sort through a basic filter moves only the filter's columns (data/star_counts/widen_filters.py): a column added
    outside it is left behind by the next sort, and its cells end up on other stars' rows.  Returns
    {tab: (old end column, new)} for the tabs that needed it.
    """
    tabs = [t["tab"] for t in TABS.values()]
    meta = api.get(spreadsheetId=sid, fields="sheets(properties(title,gridProperties(columnCount)),basicFilter)"
                   ).execute()["sheets"]
    before = {s["properties"]["title"]: (s["basicFilter"], s["properties"]["gridProperties"]["columnCount"])
              for s in meta if s["properties"]["title"] in tabs and s.get("basicFilter")}
    short = {t: (f, n) for t, (f, n) in before.items() if f["range"].get("endColumnIndex", n) < n}
    if not short:
        return {}
    # Setting a filter that stores a sort RE-APPLIES the sort, and a sort moves values and notes but not borders.
    # That scrambled Planetless 4+ Stars on 9 Oct 2026 (restore_order.py put it back).  Refuse rather than repeat it.
    sorted_ = [t for t, (f, _) in short.items() if f.get("sortSpecs")]
    if sorted_:
        raise SystemExit(f"{sorted_}: the filter stores a sort, and setting it again would re-sort the rows and "
                         "strand their provenance borders. Widen it by hand, or sort the rows back afterwards with "
                         "restore_order.py.")
    values = {t: read_tab(api, sid, t) for t in short}
    api.batchUpdate(spreadsheetId=sid, body={"requests": [
        {"setBasicFilter": {"filter": dict(f, range=dict(f["range"], endColumnIndex=n))}}
        for f, n in short.values()]}).execute()
    gs.invalidate_cache(sid)
    meta = api.get(spreadsheetId=sid, fields="sheets(properties(title),basicFilter)").execute()["sheets"]
    after = {s["properties"]["title"]: s["basicFilter"] for s in meta if s["properties"]["title"] in short}
    for t, (old, n) in short.items():
        new = after[t]
        assert new["range"]["endColumnIndex"] == n, (t, "not widened")
        assert {k: v for k, v in new["range"].items() if k != "endColumnIndex"} ==                {k: v for k, v in old["range"].items() if k != "endColumnIndex"}, (t, "rows moved")
        assert new.get("sortSpecs") == old.get("sortSpecs") and new.get("filterSpecs") == old.get("filterSpecs"), t
        assert read_tab(api, sid, t) == values[t], (t, "a cell changed")
    return {t: (f["range"]["endColumnIndex"], n) for t, (f, n) in short.items()}


def filter_lines(widened):
    return ["", f"{TODAY}: FILTERS WIDENED OVER THE EXISTENCE COLUMNS -- "
            + "; ".join(f"{t} {a} -> {b} columns" for t, (a, b) in widened.items())
            + ". The columns added above sat outside each tab's basic filter, so a sort would have left them behind "
            "on the wrong rows. Each filter was set again over every column, its rows, criteria and sort order "
            "unchanged; no cell changed (data/existence/write.py widen_filters)."]


def cell_request(tid, r, c, cell):
    data, fields = {"userEnteredValue": {"stringValue": str(cell["value"])}}, ["userEnteredValue"]
    if cell.get("note"):
        data["note"] = cell["note"]
        fields.append("note")
    return {"updateCells": {"range": {"sheetId": tid, "startRowIndex": r - 1, "endRowIndex": r,
                                      "startColumnIndex": c, "endColumnIndex": c + 1},
                            "rows": [{"values": [data]}], "fields": ",".join(fields)}}


def border_request(gs, tid, r, c):
    side = {"style": "SOLID_MEDIUM", "color": gs._hex_to_color(gs.INFERRED_BORDER)}
    return {"updateBorders": {"range": {"sheetId": tid, "startRowIndex": r - 1, "endRowIndex": r,
                                        "startColumnIndex": c, "endColumnIndex": c + 1},
                              "top": side, "bottom": side, "left": side, "right": side}}


def todo_for(t, planned, h, rows):
    """{row number: {header: cell}} of planned cells not yet on the sheet, plus plan rows not found live."""
    col = {k: i for i, k in enumerate(h)}
    at = {}
    for n, r in enumerate(rows, start=2):
        if str(r[col[t["name_col"]]]).strip():
            at.setdefault(key_of(r, col, t), n)
    out, missing, skipped = {}, [], Counter()
    for k, p in planned.items():
        n = at.get(k)
        if n is None:
            missing.append(k)
            continue
        live = rows[n - 2]
        cells = {}
        for hd, c in p["cells"].items():
            got = live[col[hd]] if hd in col else ""
            if blank(got):
                cells[hd] = c
            elif got != c["value"]:
                skipped[hd] += 1                # filled by hand since: never overwritten
        if cells:
            out[n] = {"key": k, "cells": cells}
    return out, missing, skipped


def verify_chunk(api, sid, t, h, r0, r1, chunk):
    width = len(h)
    vals = api.values().get(spreadsheetId=sid, range=f"{q(t['tab'])}!A{r0}:{letter(width - 1)}{r1}",
                            valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [])
    col = {k: i for i, k in enumerate(h)}
    for n, item in chunk.items():
        live = list(vals[n - r0]) + [""] * width
        k = key_of(live, col, t)
        if k != item["key"]:
            raise SystemExit(f"{t['tab']} row {n} holds {k}, expected {item['key']}. Nothing in this chunk was "
                             "written.")
        for hd, c in item["cells"].items():
            if not (blank(live[col[hd]]) or live[col[hd]] == c["value"]):
                raise SystemExit(f"{t['tab']} {hd} row {n} ({k}) holds {live[col[hd]]!r}. Nothing in this chunk "
                                 "was written.")


SP_COLUMN_ROWS = [
    [H_SIMBAD,
     "SIMBAD (CDS) main identifier, by TAP: the object whose identifiers include this row's 'Gaia DR3 <source_id>', "
     "else this row's name (a Planetless row: the MSC's SimbadName). Known-tab rows with no Gaia id: the match made by "
     "data/known_within_100ly/kinematics/simbad.py (GJ name, else nearest source within 90\" with a parallax within "
     "25%). Known, Systems and Planetless tabs.",
     "High where looked up; orange box where matched by a system name or by position (INFERRED note says which)",
     "simbad.cds.unistra.fr/simbad/sim-id?Ident=<main_id>. Scripts: data/existence/fetch.py, plan.py, write.py."],
    [H_CNS5,
     "Fifth Catalogue of Nearby Stars (Golovin et al. 2023, A&A 670, A19; VizieR J/A+A/670/A19, cns5.dat corrected "
     "13 Dec 2023): by Gaia DR3 id in the catalog's own GaiaDR3 column; rows with no Gaia id by the 'CNS5 n' entry "
     "of 'Nearby stars within 100 light years.xlsx' they were built from. Known tab only.",
     "High",
     "vizier.cds.unistra.fr/viz-bin/VizieR-4?-source=J/A%2BA/670/A19/cns5&CNS5=<n>"],
    [H_EXIST,
     "Which curated catalogs list the object: 'confirmed: <catalogs>' (SIMBAD, CNS5, the Multiple Star Catalog, the "
     "NASA Exoplanet Archive for a host of a confirmed planet; Gaia DR3 listed too where the row has an id). "
     "'unconfirmed: only cited in Gaia DR3 (fidelity_v2 x)' where Gaia DR3 is the only one: no SIMBAD entry, no "
     "CNS5 row. fidelity_v2 is Rybizki et al. 2022 (MNRAS 510, 2597); below 0.5 the astrometry is probably spurious. "
     "Nearby Stellar Motion draws the unconfirmed objects aquamarine and links each catalog in the info panel.",
     "Derived from the columns above; the 'unconfirmed' rows are a quality flag, not a removal",
     "Open the SIMBAD / CNS5 / Gaia DR3 links; an unconfirmed row's note gives its fidelity_v2."],
    [H_REFS,
     "The references behind Radial velocity and Proper motion, read from those cells' own SOURCE notes (else this "
     "row's Kinematics source): 'RV: <refs>; PM: <refs>', each a catalog (Gaia DR3, Gaia DR2, CNS5, MSC, SIMBAD), an "
     "ADS bibcode, a DOI, an arXiv id or a URL. Machine-readable twin of Kinematics source, which keeps the flags.",
     "As the motion cells' notes",
     "ui.adsabs.harvard.edu/abs/<bibcode>; doi.org/<doi>; the Gaia DR3 row by source_id on VizieR I/355/gaiadr3."],
]


def column_table_rows(gs, api, sid):
    """Insert the four column rows at the end of WHERE EACH COLUMN CAME FROM (rows 12..), keyed by COLUMN text."""
    vals = api.values().get(spreadsheetId=sid, range=f"{q(SP)}!A1:A60").execute()["values"]
    top = next(i for i, r in enumerate(vals) if r and str(r[0]).startswith("WHERE EACH COLUMN CAME FROM"))
    assert vals[top + 1][0] == "COLUMN", vals[top + 1]
    end = top + 2
    while end < len(vals) and vals[end] and str(vals[end][0]).strip():
        end += 1
    have = {str(r[0]).strip() for r in vals[top + 2:end] if r}
    rows = [r for r in SP_COLUMN_ROWS if r[0] not in have]
    if not rows:
        return None
    pid = sheet_meta(api, sid)[SP]["sheetId"]
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"insertDimension": {
        "range": {"sheetId": pid, "dimension": "ROWS", "startIndex": end, "endIndex": end + len(rows)},
        "inheritFromBefore": True}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{end + 1}:D{end + len(rows)}": rows},
                    expect={f"{q(SP)}!A{end + 1}": "", f"{q(SP)}!A{end}": vals[end - 1][0]})
    return [end + 1, end + len(rows)]


def sp_block(counts, summary):
    k, s, p = summary["known"], summary["systems"], summary["planetless"]
    lines = [
        "",
        f"{TODAY}: EXISTENCE AND KINEMATICS-REFERENCE COLUMNS ADDED -- Known within 100ly, Systems within 100 ly, "
        "Planetless 4+ Stars (data/existence/, log write_log.json).",
        "Why: so every star Nearby Stellar Motion draws carries a source a reader can open that affirms it exists, and "
        "links for its motion data. New columns, appended after each tab's last: SIMBAD main_id, CNS5 id (Known "
        "only), Existence, Kinematics refs. Blank cells only; nothing already on a tab was changed.",
        f"Known within 100ly: SIMBAD id on {k.get('simbad looked up', 0) + k.get('simbad inferred', 0)} rows "
        f"({k.get('simbad inferred', 0)} orange: matched by name or position, not by an identifier the row carries); "
        f"CNS5 number on {k.get('cns5', 0)}; {k.get('confirmed', 0)} confirmed; {k.get('unconfirmed', 0)} "
        "UNCONFIRMED -- Gaia DR3 is the only catalog that lists them (no SIMBAD entry for their Gaia DR3 identifier, "
        "not in CNS5). All of those have fidelity_v2 < 0.5 (Rybizki et al. 2022): their parallaxes are probably "
        "spurious and they may not be within 100 ly at all. Kept on the tab and drawn aquamarine, not removed.",
        f"Systems within 100 ly: SIMBAD id on {s.get('simbad looked up', 0) + s.get('simbad inferred', 0)} of 426 "
        f"stars ({s.get('simbad inferred', 0)} orange: a primary found by its system's name); all confirmed.",
        f"Planetless 4+ Stars: every star row confirmed by the Multiple Star Catalog (Tokovinin 2018, J/ApJS/235/6, "
        f"by WDS code); SIMBAD id on {p.get('simbad looked up', 0) + p.get('simbad inferred', 0)} star rows "
        f"({p.get('simbad inferred', 0)} orange). Barycentre rows are left blank: not objects.",
        "Kinematics refs is read from the RV and PM cells' own SOURCE notes (else Kinematics source): Gaia DR3 where "
        "the note's source is Gaia, SIMBAD's adopted value as its bibcode, a literature value as the paper's URL / "
        "DOI / arXiv id the note gives.",
        "Cells written: " + ", ".join(f"{t} {h} {n}" for (t, h), n in sorted(counts.items())) + ".",
    ]
    return lines


def append_sp(gs, api, sid, lines):
    props = sheet_meta(api, sid)[SP]
    last = props["gridProperties"]["rowCount"]
    assert gs.read_cells(sid, [f"{q(SP)}!A{last}"])[f"{q(SP)}!A{last}"][0][0].strip()
    start, end = last + 1, last + len(lines)
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
        "sheetId": props["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, end)})
    return [start, end]


def main():
    mode = (sys.argv[1:] or ["plan"])[0]
    assert mode in ("plan", "write", "filters"), mode
    if mode == "filters":
        gs, sid, api = sheets()
        widened = widen_filters(gs, api, sid)
        if not widened:
            print("every filter already spans every column")
            return
        log = load(WRITE_LOG, {"runs": []})
        rows = append_sp(gs, api, sid, filter_lines(widened))
        title = gs.rename_workbook(None, gs.versioned_title())
        log.setdefault("filters", []).append({"at": now(), "widened": widened, "sp_rows": rows, "title": title})
        save(WRITE_LOG, log)
        print(f"done: {title}  {widened}  S&P {rows}")
        return
    plan = load(PLAN)
    assert plan, "run plan.py first"
    gs, sid, api = sheets()
    log = load(WRITE_LOG, {"runs": []})
    run = next((r for r in log["runs"] if r["state"] != "done"), None)
    if mode == "write" and run is None:
        run = {"started": now(), "state": "cells", "plan_built": plan["built"], "counts": {}, "chunks": 0}
        log["runs"].append(run)
        save(WRITE_LOG, log)
    for key, t in TABS.items():
        if mode == "write":
            added = add_columns(gs, api, sid, t)
            if added:
                print(f"  {t['tab']}: added columns {added}")
        h, rows = read_tab(api, sid, t["tab"])
        hh = h + [c for c in t["new"] if c not in h]          # the plan's headers, before they exist
        rows = [r + [""] * (len(hh) - len(r)) for r in rows]
        todo, missing, skipped = todo_for(t, plan["tabs"][key], hh, rows)
        cnt = Counter(hd for it in todo.values() for hd in it["cells"])
        print(f"{t['tab']}: {len(todo)} rows to write; cells {dict(cnt)}; filled by hand (left alone): "
              f"{dict(skipped) or 'none'}; plan rows not found live: {len(missing)} {missing[:5]}")
        if mode == "plan":
            for n in sorted(todo)[:2]:
                print(f"    row {n} {todo[n]['key']}: " + "; ".join(f"{k}={c['value']!r}"
                                                             for k, c in todo[n]["cells"].items()))
            continue
        assert not missing, missing[:10]
        tid = sheet_meta(api, sid)[t["tab"]]["sheetId"]
        col = {k: i for i, k in enumerate(h)}
        order = sorted(todo)
        i = 0
        while i < len(order):
            r0, chunk = order[i], {}
            while i < len(order) and order[i] < r0 + CHUNK_ROWS:
                chunk[order[i]] = todo[order[i]]
                i += 1
            r1 = max(chunk)
            verify_chunk(api, sid, t, h, r0, r1, chunk)
            reqs, borders = [], []
            for n, item in chunk.items():
                for hd, c in item["cells"].items():
                    reqs.append(cell_request(tid, n, col[hd], c))
                    if c.get("mark") == "orange":
                        borders.append(border_request(gs, tid, n, col[hd]))
                    run["counts"][f"{key}|{hd}"] = run["counts"].get(f"{key}|{hd}", 0) + 1
            api.batchUpdate(spreadsheetId=sid, body={"requests": reqs + borders}).execute()
            run["chunks"] += 1
            save(WRITE_LOG, log)
            print(f"    rows {r0}-{r1}: {len(chunk)} rows, {len(reqs)} cells, {len(borders)} orange", flush=True)
    if mode == "plan":
        return
    gs.invalidate_cache(sid)
    if "filters" not in run:
        run["filters"] = widen_filters(gs, api, sid)
        save(WRITE_LOG, log)
    if "border_fix" not in run:              # the neighbour's orange boxes came over with its format
        import newcol_borders
        run["border_fix"] = newcol_borders.run(write=True)
        save(WRITE_LOG, log)
    if "sp_columns" not in run:
        run["sp_columns"] = column_table_rows(gs, api, sid)
        save(WRITE_LOG, log)
    if "sp_rows" not in run:
        counts = Counter({tuple(k.split("|")): v for k, v in run["counts"].items()})
        run["sp_rows"] = append_sp(gs, api, sid, sp_block(counts, plan["summary"])
                                   + (filter_lines(run["filters"])[1:] if run["filters"] else []))
        save(WRITE_LOG, log)
    run["title"] = gs.rename_workbook(None, gs.versioned_title())
    run["state"], run["finished"] = "done", now()
    save(WRITE_LOG, log)
    gs.invalidate_cache(sid)
    print(f"done: {run['title']}  S&P column rows {run['sp_columns']}, block {run['sp_rows']}")


if __name__ == "__main__":
    main()
