# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The migrated brown dwarfs' star-row notes, onto their planet rows: provenance migrate_bds.py left in its log.

    python carry_bd_notes.py          plan: print every note; touches nothing
    python carry_bd_notes.py write    write the notes, provenance, rename

migrate_bds.py (7 Oct 2026) carried the notes of the cells it copied (mass, separation, eccentricity, period) and
kept every deleted row's notes in migrate_bds_log.json. The others -- the brown dwarf's own luminosity, temperature,
class and mass basis, whose values went into the flags text -- were then on no tab, and five papers cited only there
dropped out of STAR_SYSTEM_SOURCES.md. This puts each deleted star row's notes, every one, on the name cell of the
planet (or moon) row it became.
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
SP = "Sources & Provenance"
DATE = "7 Oct 2026"
sys.path.insert(0, str(HERE))
from migrate_bds import MOVES  # noqa: E402


def main():
    log = json.loads((HERE / "migrate_bds_log.json").read_text(encoding="utf-8"))
    deleted = log["deleted"]
    notes = {}
    for tab, system, comp, target, name, node, tier in MOVES:
        rec = deleted[f"{tab} / {comp}"]
        head = {i: h for i, h in enumerate(rec["values"])}
        cols = {letter(i): h for i, h in head.items()}
        parts = []
        for a1, note in sorted(rec["notes"].items()):
            col = "".join(ch for ch in a1 if ch.isalpha())
            parts.append(f"[{cols.get(col, col)}] {note}")
        if not parts:
            continue
        v = API.values().get(spreadsheetId=SID, range=f"{q(target)}!A1:A3000").execute()["values"]
        rows = [i + 1 for i, r in enumerate(v) if r and r[0] == name]
        assert len(rows) == 1, (target, name, rows)
        a1 = f"{q(target)}!A{rows[0]}"
        notes[a1] = (f"FROM ITS FORMER STAR ROW ({tab}, '{comp}', deleted {DATE} by migrate_bds.py; a brown dwarf "
                     "is a planet): its cell notes, by column.\n" + "\n".join(parts))
    for a1, n in notes.items():
        print(a1, len(n), n[:200].replace("\n", " | "))
    sp = ["", f"BROWN DWARFS' STAR-ROW NOTES CARRIED, {DATE.upper()}",
          "  After 'BROWN DWARFS OFF THE STAR TABS' above: every cell note of each deleted brown-dwarf star row (kept in "
          "data/star_counts/migrate_bds_log.json) is now a note on the name cell of the planet or moon row it became, "
          f"so the sources of its luminosity, temperature, class and mass basis stay on the sheet. {len(notes)} rows. "
          "Script: data/star_counts/carry_bd_notes.py."]
    if PLAN:
        return
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
    print("done:", gs.rename_workbook(None, gs.versioned_title()), [sp0, sp1])
    gs.invalidate_cache(SID)


if __name__ == "__main__":
    main()
