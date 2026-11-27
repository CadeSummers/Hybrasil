# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write research.py's nicknames to the workbook, and give the IAU names a column of their own.

    python apply.py            plan: print every write; touches nothing
    python apply.py --write    do it, once

On the Systems, Multi-stars, Planetless 4+ Stars and Known within 100ly tabs the column
"Nickname (IAU)" becomes "Nicknames" (every common name, "; " between them, the IAU name first)
and a new column "IAU official designation" is inserted to its right. The Known tab gets the
two headers and its IAU names moved, and no new names: see TODO.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hybrasil.data import google_sheets as gs  # noqa: E402

HERE = Path(__file__).parent
OLD, NEW, IAU = "Nickname (IAU)", "Nicknames", "IAU official designation"
SEP = "; "
TABS = {"S": "Systems within 100 ly", "M": "Multi-stars within 100 ly", "P": "Planetless 4+ Stars",
        "K": "Known within 100ly"}
SP, LG = "Sources & Provenance", "Legend & Notes"
DATE = "26 Nov 2026"


def q(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def plan(sid: str) -> dict:
    found = json.loads((HERE / "nicknames.json").read_text(encoding="utf-8"))["stars"]
    by = {(r["tab"], r["host"], r["star"]): r for r in found}
    official = {r["iau"] for r in found if r["iau"]}
    grids = gs.read_cells(sid, [f"{q(t)}!A1:E" for t in TABS.values()])
    out = {}
    for tab, title in TABS.items():
        grid = next(v for k, v in grids.items() if title in k)
        head = [str(h).strip() for h in grid[0]]
        assert OLD in head and IAU not in head, f"{title}: already converted, or the header moved: {head}"
        ni, hi = head.index(OLD), head.index("System / Host")
        ci = head.index("Star (component)") if "Star (component)" in head else hi
        names, iaus, changed = [[NEW]], [[IAU]], []
        for r in grid[1:]:
            r = [str(c).strip() for c in list(r) + [""] * 5]
            rec = by.get((tab, r[hi], r[ci]))
            was = r[ni]
            if rec:
                listed = rec["names"] if rec["iau"] in rec["names"] or not rec["iau"] else [rec["iau"]] + rec["names"]
                cell, iau = SEP.join(listed), rec["iau"]
            else:
                cell, iau = was, was if was in official else ""
            names.append([cell])
            iaus.append([iau])
            if cell != was or iau:
                changed.append((r[ci], was, cell, iau))
        out[tab] = {"title": title, "col": ni, "names": names, "iaus": iaus, "changed": changed,
                    "last": [r[ni] if len(r) > ni else "" for r in (grid[1], grid[-1])]}
    return out


def provenance(todo: dict) -> list[str]:
    n = sum(1 for t in "SMP" for c in todo[t]["changed"] if c[1] != c[2])
    return ["", f"STAR NICKNAMES AND THE IAU COLUMN, {DATE.upper()}",
            f"  WHAT CHANGED: on {', '.join(TABS.values())} the column '{OLD}' is now '{NEW}' and holds every common "
            f"name of the star, '{SEP.strip()}' between them, the IAU name first; the IAU name alone is in the new "
            f"column '{IAU}' to its right. {n} cells gained names on the first three tabs; the Known tab gained none "
            "(data/star_nicknames/TODO.md). Names are looked up, not inferred: no border.",
            "  SOURCES: (1) IAU Catalog of Star Names, IAU Division C Working Group on Star Names, file IAU-CSN.txt "
            "(https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt, edition of 2022-04-04), matched by HIP and HD "
            "number; (2) IAU NameExoWorlds 2022 full table (https://nameexoworlds.iau.org/2022approved-names) for "
            "Orkaria (GJ 1214), Añañuca (GJ 367), Noquisi (GJ 436), Gar (GJ 486), Kaewkosin (GJ 3470), Batsũ̀ (LHS 3844) "
            "and Maru (WD 0806-661); (3) SIMBAD (CDS, Strasbourg; simbad.harvard.edu mirror, read 26 Nov 2026): its "
            "'NAME' identifiers, and its Bayer / Flamsteed designations for stars this workbook files otherwise; "
            "(4) names in common use that SIMBAD does not file as names, each tied to a SIMBAD identifier of the star: "
            "Lalande 21185 (LAL 21185), Ross 154, Ross 780, Luyten 726-8 (L 726-8), Struve 2398 (STF 2398), CN Leonis, "
            "FI Virginis, DT Virginis, BL Ceti, UV Ceti, 82 G. Eridani / e Eridani, Kapteyn's Star, Alpha Centauri A/B/C; "
            "and two with no SIMBAD identifier, from general usage: Groombridge 34 (GJ 15) and Bessel's Star (61 Cyg).",
            "  RULES: a planet's IAU name is never a star's (SIMBAD's 'ups And b' is the planet Saffar, not the star "
            "ups And B); a Flamsteed number is not added to a star already filed by its Bayer letter; a component "
            "row of a Planetless system does not repeat its system's names. One star is on two tabs under two names: "
            "tet Cyg (Systems) is 13 Cyg (Planetless 4+ Stars). Script: data/star_nicknames/ (research.py, apply.py)."]


def main(write: bool) -> None:
    sid = gs.resolve_spreadsheet_id(None)
    todo = plan(sid)
    for tab, t in todo.items():
        print(f"{t['title']}: column {col(t['col'])} -> '{NEW}', new column {col(t['col'] + 1)} '{IAU}', "
              f"{len(t['changed'])} rows carry a name")
        if tab != "K":
            for star, was, cell, iau in t["changed"]:
                print(f"   {star:32} {was!r:20} -> {cell!r}   IAU: {iau!r}".encode("ascii", "replace").decode())
    sp = provenance(todo)
    if not write:
        print("\n".join(sp))
        return
    api = gs._sheets_api()
    ids = gs._sheet_ids(sid)
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"insertDimension": {
        "range": {"sheetId": ids[t["title"]], "dimension": "COLUMNS", "startIndex": t["col"] + 1,
                  "endIndex": t["col"] + 2}, "inheritFromBefore": True}} for t in todo.values()]}).execute()
    gs.invalidate_cache(sid)
    for t in todo.values():
        a, b, n = col(t["col"]), col(t["col"] + 1), len(t["names"])
        tq = q(t["title"])
        gs.update_cells(sid, {f"{tq}!{a}1:{a}{n}": t["names"], f"{tq}!{b}1:{b}{n}": t["iaus"]},
                        expect={f"{tq}!{a}1": OLD, f"{tq}!{b}1": "", f"{tq}!{a}2": t["last"][0],
                                f"{tq}!{a}{n}": t["last"][1], f"{tq}!{b}{n}": ""})
    meta = api.get(spreadsheetId=sid, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    end = meta["gridProperties"]["rowCount"]
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{end + 1}:A{end + len(sp)}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{end + 1}": "", f"{q(SP)}!A{end + len(sp)}": ""})
    lv = api.values().get(spreadsheetId=sid, range=f"{q(LG)}!A1:A3000").execute().get("values", [])
    row = len(lv) + 2
    gs.update_cells(sid, {f"{q(LG)}!A{row}": [[
        f"NICKNAMES ({DATE}): '{NEW}' lists every common name of a star, '{SEP.strip()}' between them, so a search "
        f"finds it by any of them; '{IAU}' holds the one name the IAU has approved, where there is one. Sources on "
        f"Sources & Provenance under 'STAR NICKNAMES AND THE IAU COLUMN, {DATE.upper()}'."]]},
        expect={f"{q(LG)}!A{row}": ""})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(sid)
    log = {"title": title, "provenance_rows": [end + 1, end + len(sp)], "legend_row": row,
           "tabs": {t["title"]: {"nicknames_column": col(t["col"]), "iau_column": col(t["col"] + 1),
                                 "rows_with_a_name": len(t["changed"])} for t in todo.values()}}
    (HERE / "apply_log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", title)


if __name__ == "__main__":
    main("--write" in sys.argv)
