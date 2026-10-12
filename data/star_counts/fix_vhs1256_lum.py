# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""VHS 1256's host luminosity: Dupuy et al. 2023's A component at the Gaia distance, not the pair at an old parallax.

    python fix_vhs1256_lum.py          plan: print every write; touches nothing
    python fix_vhs1256_lum.py write    write both cells, their notes, provenance, rename

The host luminosity was 0.0007244 L-sun: 10^-3.14, the NASA Exoplanet Archive's st_lum, which is Gauza et al. 2015's
combined light of the unresolved A + B pair at their 78.8 mas parallax (12.7 pc). Dupuy et al. 2023 (MNRAS 519, 1688,
Sect. 3) resolve the pair and give log(L/L-sun) = -2.982 +/- 0.021 for A at the Gaia EDR3 21.14 pc, the distance the
sheet already uses (Systems' Distance note, Sources & Provenance 'COLUMN C DISTANCE CORRECTIONS, 27 SEPTEMBER 2026').

apply_specs.py (6 Oct 2026) meant to put that value on A's new Multi-stars row, and A's Star data source says so, but
the row's luminosity cell is a formula reading Planets col H, which apply_specs keeps in preference to a spec value.
So the value goes where every formula reads it: Planets col H (the master: Systems and Multi-stars both look it up
there) and its typed mirror on Known within 100ly. 10^-2.982 is arithmetic on a published value, so both cells keep
the orange border they already have, as every other 10^st_lum host luminosity on the sheet does.
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
PL, KN, SY, MS, SP = ("Planets within 100 ly", "Known within 100ly", "Systems within 100 ly",
                      "Multi-stars within 100 ly", "Sources & Provenance")
LOG = HERE / "fix_vhs1256_lum_log.json"
DATE = "6 Oct 2026"
HOST, PLANET = "VHS J125601.92-125723.9", "VHS J125601.92-125723.9 b"
OLD, NEW = 0.0007244, 0.001042
LUM = "Host luminosity (L-sun)"
NOTE = (f"INFERRED ({DATE}): 10^-2.982, Dupuy et al. 2023, MNRAS 519, 1688 (arXiv:2208.08448), Sect. 3: "
        "log(L/L-sun) = -2.982 +/- 0.021 for A alone (+/- 5%), at the Gaia EDR3 21.14 pc; the pair's combined -2.687 "
        "split by the K-band flux ratio (dK = 0.033 mag). Replaces 0.0007244 (10^-3.14, NASA Exoplanet Archive "
        "st_lum after Gauza et al. 2015), which is A + B together at the superseded 78.8 mas parallax. "
        "Sources & Provenance: 'VHS J125601.92-125723.9 HOST LUMINOSITY'.")


def values(tab, how="UNFORMATTED_VALUE"):
    return API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:DZ", valueRenderOption=how
                            ).execute().get("values", [])


def cell_of(tab, key_header, key, header):
    """The A1 cell under `header` on the one row whose `key_header` is `key` -- by name, never by row number."""
    v = values(tab)
    col = {h: i for i, h in enumerate(v[0])}
    rows = [i + 1 for i, r in enumerate(v) if len(r) > col[key_header] and r[col[key_header]] == key]
    assert len(rows) == 1, (tab, key, rows)
    return f"{q(tab)}!{letter(col[header])}{rows[0]}", rows[0]


def lookups():
    """Cells that only read the master through a formula: they must move with it."""
    return [cell_of(SY, "System / Host", HOST, LUM)[0],
            cell_of(MS, "Star (component)", HOST, "Luminosity (L-sun)")[0]]


def main():
    master, prow = cell_of(PL, "Planet", PLANET, LUM)
    mirror, krow = cell_of(KN, "System / Host", HOST, LUM)
    cells = [master, mirror]
    now = gs.read_cells(SID, cells + lookups())
    got = {a1: now[a1][0][0] for a1 in now}
    old_notes = {a1: gs.get_notes(SID, a1).get(a1.split("!")[1], "") for a1 in cells}
    borders = {a1: gs.get_borders(SID, a1) for a1 in cells}
    sp = sp_lines(prow, krow)

    print("now:", json.dumps(got))
    print("notes now:", json.dumps(old_notes, ensure_ascii=False))
    print("borders now:", json.dumps(borders))
    if PLAN:
        print(f"\nWrite {NEW} to {master} and {mirror} (expect {OLD}); orange border kept.")
        print(f"Note on both:\n  {NOTE}")
        print("Lookups that should then read", NEW, ":", lookups())
        print("\nSources & Provenance:\n" + "\n".join(sp))
        return

    LOG.write_text(json.dumps({"cells": cells, "old": got, "old_notes": old_notes, "borders": borders},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    gs.update_cells(SID, {a1: NEW for a1 in cells}, expect={a1: OLD for a1 in cells})
    gs.set_note(SID, {a1: NOTE for a1 in cells})
    gs.set_border(SID, cells, gs.INFERRED_BORDER)
    gs.invalidate_cache(SID)
    after = gs.read_cells(SID, cells + lookups())
    bad = {a1: v[0][0] for a1, v in after.items() if abs(float(v[0][0]) - NEW) > 1e-12}
    assert not bad, bad

    meta = next(s["properties"] for s in API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]
                if s["properties"]["title"] == SP)
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
    print("done:", json.dumps({"cells": cells, "sp_rows": [sp0, sp1], "title": title}))


def sp_lines(prow, krow):
    return [
        "",
        f"VHS J125601.92-125723.9 HOST LUMINOSITY, {DATE.upper()}: 0.0007244 -> 0.001042 L-sun",
        f"  Planets col H (row {prow} today, the planet {PLANET}: the master that Systems' and Multi-stars' "
        f"luminosity formulas look up) and its typed mirror on Known within 100ly (row {krow} today). Was "
        "10^-3.14, the NASA Exoplanet Archive's st_lum (filled 27 Sep 2026), which is Gauza et al. 2015's light "
        "for the unresolved A + B pair at their 78.8 mas parallax: (12.69 / 21.14 pc)^2 x 10^-2.687 = 7.4e-4.",
        "  Now 10^-2.982 = 0.001042: Dupuy et al. 2023, MNRAS 519, 1688 (arXiv:2208.08448), Sect. 3, log(L/L-sun) = "
        "-2.982 +/- 0.021 for A alone, at the Gaia EDR3 21.14 pc the sheet already uses for this star's distance "
        "(27 Sep 2026 correction). Method: unit conversion of a published log value, orange as every 10^st_lum "
        "host luminosity is. Scatter: +/- 0.021 dex, i.e. 0.000993 to 0.001094. Valid for A alone at 21.14 pc; Dupuy "
        "split the pair's combined light by the K-band flux ratio, so it moves with that distance as d^2.",
        "  Why it was missed: on 6 Oct 2026 apply_specs.py wrote this value into A's Multi-stars Star data source, "
        "but the luminosity cell there is a formula reading Planets col H and was kept, so it still showed the old "
        "figure, and the viewer drew A's solvent bands from it. They now sit sqrt(0.001042 / 0.0007244) = 1.20 "
        "times further out. B's Multi-stars row (0.001014, Dupuy's -2.994) was already right.",
    ]


if __name__ == "__main__":
    main()
