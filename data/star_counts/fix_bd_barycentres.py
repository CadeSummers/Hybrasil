# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Barycentres without the brown dwarfs: subsystem masses and offsets re-derived after migrate_bds.py.

    python fix_bd_barycentres.py          plan: print every write; touches nothing
    python fix_bd_barycentres.py write    write, note, provenance, rename

The tab's own definitions (data/hierarchy.py): a subsystem's mass is the sum of its pair's, and its barycentre sits
'Barycentre offset (AU)' = a * M_sec / (M_prim + M_sec) from 'Barycentre from' along the line to the secondary.
migrate_bds.py (7 Oct 2026) took the brown dwarfs out of the hierarchies -- they are planets now, and the drawing
gives a planet no pull on its star -- but left the subsystems' masses and offsets with the brown dwarfs in them, so a
drawn barycentre was no longer its drawn pair's centre of mass (tau Cyg AB by 0.036 AU,
tests/test_planetless.py). This re-derives both, bottom-up, for the eleven systems the migration touched, and writes
only what moved. Each written cell keeps its box and gets a note saying what it was.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data" / "four_plus_stars"))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
PL, SP = "Planetless 4+ Stars", "Sources & Provenance"
LOG = HERE / "fix_bd_barycentres_log.json"
DATE = "7 Oct 2026"
# The subsystems a brown dwarf was taken out from under. Any other mismatch found is reported, not written:
# alf Gem AB reads 4.93 against its pair's 4.94 from before the migration, and Castor's built-in copies it.
AFFECTED = {"tau Cyg AB", "GJ 3347 A", "GJ 3347 AB"}
SYSTEMS = ["GJ 570", "ksi UMa", "GJ 867", "GJ 569", "alf Gem", "tau Cyg", "pi1 Cnc", "GJ 9829", "BD+37 1091",
           "BD+39 496", "GJ 3347"]


def main():
    v = API.values().get(spreadsheetId=SID, range=f"{q(PL)}!A1:DZ3000", valueRenderOption="UNFORMATTED_VALUE"
                         ).execute()["values"]
    h = v[0]
    col = {x: i for i, x in enumerate(h)}

    def cell(r, x):
        return r[col[x]] if col[x] < len(r) else ""

    upd, exp, notes, changes = {}, {}, {}, []
    for system in SYSTEMS:
        rows = {cell(r, "Star (component)"): (i + 1, r) for i, r in enumerate(v) if i and r and r[0] == system}
        mass = {n: cell(r, "Mass (M-sun)") for n, (_, r) in rows.items()}
        sec_of = {cell(r, "Separation from"): n for n, (_, r) in rows.items() if cell(r, "Separation from")}
        subs = [n for n, (_, r) in rows.items() if cell(r, "Node type") == "subsystem"]

        def pair(x):
            prim = cell(rows[x][1], "Barycentre from")
            return prim, sec_of[prim]

        def m(n):
            if n in subs:
                p, s = pair(n)
                return m(p) + m(s)
            return mass[n]

        for x in subs:
            p, s = pair(x)
            a = cell(rows[s][1], "Separation (AU)")
            new_m = round(m(p) + m(s), 6)
            new_off = round(a * m(s) / (m(p) + m(s)), 6)
            r = rows[x][0]
            for hdr, old, new in (("Mass (M-sun)", mass[x], new_m),
                                  ("Barycentre offset (AU)", cell(rows[x][1], "Barycentre offset (AU)"), new_off)):
                if abs(float(old) - new) > 1e-6 and x not in AFFECTED:
                    print("   not the migration's, left alone:", (system, x, hdr, old, new))
                elif abs(float(old) - new) > 1e-6:
                    a1 = f"{q(PL)}!{letter(col[hdr])}{r}"
                    upd[a1], exp[a1] = new, old
                    notes[a1] = (f"{DATE}: was {old}, with a brown dwarf in it; re-derived without it now that the "
                                 f"brown dwarf is a planet (fix_bd_barycentres.py): "
                                 + (f"{p} {m(p)} + {s} {m(s)} M-sun." if hdr.startswith("Mass") else
                                    f"a * M_sec / (M_prim + M_sec) = {a} x {m(s)} / ({m(p)} + {m(s)})."))
                    changes.append((system, x, hdr, old, new))
    for c in changes:
        print("  ", c)
    sp = ["", f"BARYCENTRES WITHOUT THE BROWN DWARFS, {DATE.upper()}",
          "  After 'BROWN DWARFS OFF THE STAR TABS' above: the brown dwarfs are planets now, which the drawing gives no "
          "pull, so the subsystems' masses (the sum of their pair's) and barycentre offsets (a * M_sec / (M_prim + "
          "M_sec)) were re-derived without them, bottom-up, by the tab's own definitions. Changed: "
          + "; ".join(f"{x} {hdr} {old} -> {new}" for _, x, hdr, old, new in changes)
          + ". The old value is in each cell's note. Script: data/star_counts/fix_bd_barycentres.py."]
    if PLAN:
        print("\n".join(sp))
        return
    gs.update_cells(SID, upd, expect=exp)
    old = {a1: gs.get_notes(SID, a1).get(a1.split("!")[1], "") for a1 in notes}
    gs.set_note(SID, {a1: (old[a1] + "\n\n" + n) if old[a1] else n for a1, n in notes.items()})
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{end}"])[f"{q(SP)}!A{end}"][0][0].strip()
    sp0, sp1 = end + 1, end + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{sp0}:A{sp1}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (sp0, sp1)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps({"changes": changes, "sp_rows": [sp0, sp1], "title": title}, indent=1,
                              ensure_ascii=False), encoding="utf-8")
    print("done:", title, [sp0, sp1])


if __name__ == "__main__":
    main()
