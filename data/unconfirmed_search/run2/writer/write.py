# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Execute plan.json against the live workbook, one guarded step at a time.

    python write.py <step>      step = 1 .. 5, run in order; each step checks its own preconditions.

1  Planets: move the three validated TOIs in; Unconfirmed: delete them and the two duplicates.
2  Unconfirmed: re-host rows onto their Systems names (TOI-2009 -> HD 6660, ...).
3  Systems: insert the new host rows inside the pinned $2:$363 range.
4  Unconfirmed + Rejected candidates: append the new candidate rows.
5  Orange borders and notes.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))
from hybrasil.data import google_sheets as gs  # noqa: E402

PLAN = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
PL, UN, RJ, SY = "Planets within 100 ly", "Unconfirmed within 100 ly", "Rejected candidates", "Systems within 100 ly"
LOG = HERE / "write_log.json"
log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}


def q(t):
    return "'" + t.replace("'", "''") + "'"


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def column_a(tab):
    v = API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:A2000").execute().get("values", [])
    return [r[0] if r else "" for r in v]


def last_data_row(tab):
    a = column_a(tab)
    n = 1
    for i, x in enumerate(a[1:], start=2):
        if not x:
            break
        n = i
    return n


def last_planet_row():
    """The loader's rule: data ends at the first row with at most one filled cell."""
    v = API.values().get(spreadsheetId=SID, range=f"{q(PL)}!A1:E2000").execute().get("values", [])
    n = 1
    for i, r in enumerate(v[1:], start=2):
        if sum(1 for c in r if str(c).strip()) <= 1:
            break
        n = i
    return n


def sheet_id(tab):
    return gs._sheet_ids(SID)[tab]


def grid(tab, r0, r1, c0=0, c1=42):
    return {"sheetId": sheet_id(tab), "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def batch(reqs):
    if reqs:
        API.batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()
    gs.invalidate_cache(SID)


def row_of(tab, name):
    a = column_a(tab)
    hits = [i + 1 for i, x in enumerate(a) if x == name]
    assert len(hits) == 1, (tab, name, hits)
    return hits[0]


def save_log():
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------------------------------------
def step1():
    assert "step1" not in log, "step 1 already done"
    moves = PLAN["housekeeping"]["move_to_planets"]
    src = {old: row_of(UN, old) for old in moves}
    last = last_planet_row()
    assert last == 540, last
    after = API.values().get(spreadsheetId=SID, range=f"{q(PL)}!A{last+1}:A{last+2}").execute().get("values", [])
    print("Planets last data row", last, "next:", after)
    n = len(moves)
    batch([{"insertDimension": {"range": {"sheetId": sheet_id(PL), "dimension": "ROWS", "startIndex": last,
                                          "endIndex": last + n}, "inheritFromBefore": True}}])
    reqs = []
    for k, (old, new) in enumerate(moves.items()):
        r = src[old]
        reqs.append({"copyPaste": {"source": grid(UN, r - 1, r, 0, 42), "destination": grid(PL, last + k, last + k + 1, 0, 42),
                                   "pasteType": "PASTE_NORMAL"}})
    batch(reqs)
    ren = PLAN["rename"]
    upd, exp = {}, {}
    for k, (old, new) in enumerate(moves.items()):
        r = last + 1 + k
        cur = gs.read_cells(SID, [f"{q(PL)}!A{r}", f"{q(PL)}!B{r}", f"{q(PL)}!AI{r}"])
        assert cur[f"{q(PL)}!A{r}"][0][0] == old, cur
        host = cur[f"{q(PL)}!B{r}"][0][0]
        flags = cur[f"{q(PL)}!AI{r}"][0][0] if cur[f"{q(PL)}!AI{r}"] else ""
        upd.update({f"{q(PL)}!A{r}": new, f"{q(PL)}!B{r}": ren.get(host, host), f"{q(PL)}!AJ{r}": "confirmed",
                    f"{q(PL)}!AK{r}": old, f"{q(PL)}!AL{r}": "CP",
                    f"{q(PL)}!AM{r}": ("Collier et al. 2026, 'Assessing the Impact of High-Resolution Imaging on Statistical "
                                       "Validation of TESS Planet Candidates', arXiv:2608.21560v3 (accepted to AAS Journals), "
                                       "Table 3 (newly validated planets)"),
                    f"{q(PL)}!AN{r}": "2026-09-27",
                    f"{q(PL)}!AI{r}": ("VALIDATED 27 Sep 2026 (moved from Unconfirmed): statistically validated with TRICERATOPS "
                                       "plus high-resolution imaging by Collier et al. 2026, Table 3; TFOPWG CP since "
                                       "2026-08-25. Not yet in NASA pscomppars. Orbit and radius are still the TOI table's. || "
                                       + flags)})
        exp[f"{q(PL)}!A{r}"] = old
    gs.update_cells(SID, upd, expect=exp)
    # Delete the moved rows and the two duplicates from Unconfirmed, bottom up.
    names = list(moves) + list(PLAN["housekeeping"]["delete_duplicates"])
    rows = sorted(((row_of(UN, nm), nm) for nm in names), reverse=True)
    for r, nm in rows:
        assert gs.read_cells(SID, [f"{q(UN)}!A{r}"])[f"{q(UN)}!A{r}"][0][0] == nm
    batch([{"deleteDimension": {"range": {"sheetId": sheet_id(UN), "dimension": "ROWS", "startIndex": r - 1, "endIndex": r}}}
           for r, _ in rows])
    log["step1"] = {"planets_rows": [last + 1 + k for k in range(n)], "unconfirmed_deleted": {nm: r for r, nm in rows}}
    save_log()
    print("step 1 done", log["step1"])


def step2():
    assert "step1" in log and "step2" not in log
    ren = PLAN["rename"]
    last = last_data_row(UN)
    v = API.values().get(spreadsheetId=SID, range=f"{q(UN)}!A2:E{last}").execute()["values"]
    upd, exp = {}, {}
    for i, r in enumerate(v, start=2):
        b = r[1] if len(r) > 1 else ""
        e = r[4] if len(r) > 4 else ""
        if b in ren:
            upd[f"{q(UN)}!B{i}"] = ren[b]
            exp[f"{q(UN)}!B{i}"] = b
            exp[f"{q(UN)}!A{i}"] = r[0]
        if e in ren:
            upd[f"{q(UN)}!E{i}"] = ren[e]
            exp[f"{q(UN)}!E{i}"] = e
    gs.update_cells(SID, upd, expect=exp)
    log["step2"] = {k: v for k, v in upd.items()}
    save_log()
    print("step 2 done:", len(upd), "cells re-hosted")


SYS_INPUT = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M", "N", "O", "P", "Q", "Z", "AA", "AB", "AC", "AD",
             "AE", "AF", "AG", "AH", "AI", "AJ", "AK", "AL", "AM", "AN", "AO", "AP"]


def step3():
    assert "step2" in log and "step3" not in log
    rows = PLAN["systems_rows"]
    moved_hosts = {PLAN["rename"].get(h, h) for h in ("TOI-2540", "TOI-5961", "TOI-6662")}
    last = last_data_row(SY)
    assert last == 363, last
    tmpl = row_of(SY, "Wolf 359")
    n = len(rows)
    at = last - 1                       # insert before the last row, inside $2:$363
    batch([{"insertDimension": {"range": {"sheetId": sheet_id(SY), "dimension": "ROWS", "startIndex": at,
                                          "endIndex": at + n}, "inheritFromBefore": True}}])
    tmpl = row_of(SY, "Wolf 359")
    batch([{"copyPaste": {"source": grid(SY, tmpl - 1, tmpl, 0, 42), "destination": grid(SY, at, at + n, 0, 42),
                          "pasteType": "PASTE_NORMAL"}}])
    upd = {}
    for k, s in enumerate(rows):
        r = at + 1 + k
        if s["A"] in moved_hosts:
            s = dict(s, F=1)
        for c in SYS_INPUT:
            upd[f"{q(SY)}!{c}{r}"] = s.get(c, "")
    gs.update_cells(SID, upd, expect={f"{q(SY)}!A{at+1}": "Wolf 359"})
    f = API.values().get(spreadsheetId=SID, range=f"{q(UN)}!C2", valueRenderOption="FORMULA").execute()["values"][0][0]
    log["step3"] = {"first": at + 1, "last": at + n, "unconfirmed_C2_formula": f[:140]}
    save_log()
    print("step 3 done", log["step3"])


UN_INPUT = ["A", "B", "E", "F", "H", "I", "J", "K", "L", "O", "Q", "R", "T", "V", "W", "Z", "AD", "AI", "AJ", "AK", "AL",
            "AM", "AN", "AO", "AP"]


def radius_constant():
    f = API.values().get(spreadsheetId=SID, range=f"{q(UN)}!U2", valueRenderOption="FORMULA").execute()["values"][0][0]
    m = re.search(r"'Planets within 100 ly'!\$C\$(\d+)", f)
    assert m, f
    return f"'Planets within 100 ly'!$C${m.group(1)}"


def append(tab, rows, tmpl_name):
    last = last_data_row(tab)
    tmpl = row_of(tab, tmpl_name)
    n = len(rows)
    empty = API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A{last+1}:A{last+n+2}").execute().get("values", [])
    assert not empty, empty
    ncol = 43 if tab == RJ else 42
    batch([{"copyPaste": {"source": grid(tab, tmpl - 1, tmpl, 0, ncol), "destination": grid(tab, last, last + n, 0, ncol),
                          "pasteType": "PASTE_NORMAL"}}])
    rc = radius_constant()
    raw, formulas, placed = {}, {}, {}
    cols = UN_INPUT + (["AQ"] if tab == RJ else [])
    for k, row in enumerate(rows):
        r = last + 1 + k
        for c in cols:
            if c == "T":
                continue
            raw[f"{q(tab)}!{c}{r}"] = row.get(c, "")
        formulas[f"{q(tab)}!T{r}"] = f"={row['_radius_e']}/{rc}" if row.get("_radius_e") else ""
        placed[row["A"]] = r
    gs.update_cells(SID, raw, expect={f"{q(tab)}!A{last+1}": tmpl_name})
    gs.update_cells(SID, formulas, value_input="USER_ENTERED")
    # The filter follows the data.
    f = [s for s in API.get(spreadsheetId=SID, fields="sheets(properties(title),basicFilter)").execute()["sheets"]
         if s["properties"]["title"] == tab][0].get("basicFilter")
    if f:
        rng = dict(f["range"], endRowIndex=last + n)
        batch([{"setBasicFilter": {"filter": dict(f, range=rng)}}])
    return placed


def step4():
    assert "step3" in log and "step4" not in log
    un = [r for r in PLAN["rows"] if r["_tab"] == UN]
    rj = [r for r in PLAN["rows"] if r["_tab"] == RJ]
    placed = {UN: append(UN, un, "HD 23439 A b"), RJ: append(RJ, rj, "TOI-1955.01")}
    log["step4"] = placed
    save_log()
    print("step 4 done:", {t: len(v) for t, v in placed.items()})


def step5():
    assert "step4" in log and "step5" not in log
    orange, notes = [], {}
    for row in PLAN["rows"]:
        tab = row["_tab"]
        r = log["step4"][tab][row["A"]]
        for c, txt in row["_orange"].items():
            orange.append(f"{q(tab)}!{c}{r}")
            notes[f"{q(tab)}!{c}{r}"] = txt
        for c, txt in row["_notes"].items():
            notes[f"{q(tab)}!{c}{r}"] = txt
    first = log["step3"]["first"]
    for k, s in enumerate(PLAN["systems_rows"]):
        r = first + k
        if s.get("_lum_inferred"):
            orange.append(f"{q(SY)}!N{r}")
            notes[f"{q(SY)}!N{r}"] = ("INFERRED: L = R^2 (Teff/5772)^4 from the research record's radius and Teff "
                                      "(TIC v8.2 or the source it names).")
        if s.get("_fill_note"):
            notes[f"{q(SY)}!N{r}"] = s["_fill_note"]
        if s.get("O"):
            notes[f"{q(SY)}!O{r}"] = ("TYPED, not looked up: Kopparapu et al. 2013 bounds from this row's Teff (K) and "
                                      "luminosity (N), computed with the column's own recipe (data/unconfirmed_search/pack/hz.py).")
    for i in range(0, len(orange), 80):
        gs.set_border(SID, orange[i:i + 80], gs.INFERRED_BORDER)
    gs.set_note(SID, notes)
    log["step5"] = {"orange": len(orange), "notes": len(notes)}
    save_log()
    print("step 5 done", log["step5"])


{"1": step1, "2": step2, "3": step3, "4": step4, "5": step5}[sys.argv[1]]()
