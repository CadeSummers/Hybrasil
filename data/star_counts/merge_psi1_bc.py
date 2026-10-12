# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fold the candidate psi1 Dra B c into the star psi1 Dra D: one body, drawn once.

    python merge_psi1_bc.py          plan: print every write; touches nothing
    python merge_psi1_bc.py write    delete the Unconfirmed row, re-point D's text, provenance, rename

Unconfirmed's psi1 Dra B c is Endl et al. 2016's 'external perturber' behind psi1 Dra B's long-term RV trend, at a
nominal 16.2 AU. write_counts.py (6 Oct 2026) added the same body to Multi-stars as psi1 Dra D, at an assumed 15 AU
and 0.014 M_sun from that trend plus B's proper-motion anomaly, so the viewer drew it twice. The owner's choice
(6 Oct 2026): keep D, remove B c. The deleted row, values and notes, is kept in merge_psi1_bc_log.json.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data" / "four_plus_stars"))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
UN, MS, SP = "Unconfirmed within 100 ly", "Multi-stars within 100 ly", "Sources & Provenance"
LOG = HERE / "merge_psi1_bc_log.json"
DATE = "6 Oct 2026"
BC, D, PSI = "psi1 Dra B c", "psi1 Dra D", "psi1 Dra A"
D_EXTRA = (" Until " + DATE + " the same body was also on the Unconfirmed tab as the candidate planet psi1 Dra B c "
           "(ambiguous tier, nominal a = 16.2 AU); that row was removed so it is drawn once.")
PSI_NOTE_EXTRA = " The Unconfirmed tab's psi1 Dra B c was this same body and was removed on " + DATE + "."


def values(tab, how="FORMULA"):
    return API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:DZ3000", valueRenderOption=how
                            ).execute().get("values", [])


def main():
    props = {s["properties"]["title"]: s["properties"] for s in
             API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}
    un, ms = values(UN), values(MS, "UNFORMATTED_VALUE")
    rows = [i + 1 for i, r in enumerate(un) if r and r[0] == BC]
    assert len(rows) == 1, rows
    row = rows[0]
    ncols = len(un[0])
    grid = API.get(spreadsheetId=SID, ranges=[f"{q(UN)}!A{row}:{letter(ncols - 1)}{row}"], includeGridData=True,
                   fields="sheets(data(rowData(values(note))))").execute()["sheets"][0]["data"][0]
    notes = {letter(i): v["note"] for i, v in enumerate(grid["rowData"][0].get("values", [])) if v.get("note")}
    removed = {un[0][i]: x for i, x in enumerate(un[row - 1]) if x not in ("", None) and i < ncols}

    mc = {h: i for i, h in enumerate(ms[0])}
    comp = mc["Star (component)"]
    d_row = next(i + 1 for i, r in enumerate(ms) if len(r) > comp and r[comp] == D)
    host_row = next(i + 1 for i, r in enumerate(ms) if len(r) > comp and r[comp] == PSI)
    src_cell = f"{q(MS)}!{letter(mc['Star data source'])}{d_row}"
    old_src = ms[d_row - 1][mc["Star data source"]]
    assert "psi1 Dra B c" not in old_src
    sic = f"{q(MS)}!{letter(mc['Stars in system'])}{host_row}"
    old_note = API.get(spreadsheetId=SID, ranges=[sic], includeGridData=True,
                       fields="sheets(data(rowData(values(note))))").execute()["sheets"][0]["data"][0][
        "rowData"][0]["values"][0].get("note", "")
    assert old_note and "B c" not in old_note
    sp = sp_lines(row)

    if PLAN:
        print(f"Delete {UN}!{row} ({BC}):")
        for h, x in removed.items():
            print(f"    {h:42.42} {str(x)[:200]!r}")
        print("  notes on it:", {k: v[:120] for k, v in notes.items()})
        print(f"\n{D} Star data source (row {d_row}) gains:\n  {D_EXTRA}")
        print(f"{PSI} Stars in system note gains:\n  {PSI_NOTE_EXTRA}")
        print("\nSources & Provenance:\n" + "\n".join(sp))
        return

    # Log first, so the deleted row survives whatever happens next.
    LOG.write_text(json.dumps({"tab": UN, "row": row, "values": removed, "notes": notes}, indent=1,
                              ensure_ascii=False), encoding="utf-8")
    now = values(UN)
    assert now[row - 1][0] == BC
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"deleteDimension": {"range": {
        "sheetId": props[UN]["sheetId"], "dimension": "ROWS", "startIndex": row - 1, "endIndex": row}}}]}).execute()
    gs.invalidate_cache(SID)
    assert not [r for r in values(UN) if r and r[0] == BC]

    gs.update_cells(SID, {src_cell: old_src + D_EXTRA}, expect={src_cell: old_src})
    gs.set_note(SID, {sic: old_note + PSI_NOTE_EXTRA})

    meta = props[SP]
    end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{end}"])[f"{q(SP)}!A{end}"][0][0].strip()
    sp0, sp1 = end + 1, end + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{sp0}:A{sp1}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (sp0, sp1)})

    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log = json.loads(LOG.read_text(encoding="utf-8"))
    log.update(sp_rows=[sp0, sp1], title=title)
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps({"deleted_row": row, "sp_rows": [sp0, sp1], "title": title}))


def sp_lines(row):
    return [
        "",
        f"psi1 Dra B c FOLDED INTO psi1 Dra D, {DATE.upper()}",
        f"  The Unconfirmed tab's psi1 Dra B c (row {row} until today; ambiguous tier, nominal a = 16.2 AU; Endl et "
        "al. 2016, ApJ 818, 34, Sect. 5.2.2: the 'external perturber' behind psi1 Dra B's long-term RV trend) is the "
        "same body as Multi-stars' psi1 Dra D, added today for the MSC's suspected Ba,Bb and placed from that very "
        "trend plus B's proper-motion anomaly (15 AU, 0.014 M-sun, both inferred, WEAK). Drawn twice, so the owner "
        "chose to keep D and remove B c. The deleted row, values and notes, is kept in the repo at "
        "data/star_counts/merge_psi1_bc_log.json. The earlier entry for B c on this sheet (the line beginning "
        "'psi1 Dra B c -> Unconfirmed') is history and stays.",
    ]


if __name__ == "__main__":
    main()
