# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GJ 1177 A's mass on its Multi-stars row: Kervella et al. 2022's 0.67 M-sun.

    python fix_gj1177a_mass.py          plan: print every write; touches nothing
    python fix_gj1177a_mass.py write    write the mass, its note, the source text, provenance, rename

A's Multi-stars row (Sources & Provenance 'MULTI-STARS ROWS 91-94') has no mass, and its Star
data source says none was found: Gaia DR3 has no FLAME solution for the star. Kervella et al. 2022 (A&A 657, A7,
VizieR J/A+A/657/A7, Table A.1) list HIP 67308 = HD 120036 A, Gaia DR3 6171492074455952128 (A's own source_id on
this row), with M1 = 0.67 +/- 0.01 M-sun from the Mann et al. 2015 M_K-mass relation (r_M1 'M15'). That is a
catalogued value, looked up rather than derived here, so the cell keeps its plain border.

Systems and Known already carry A's mass as 0.64 +/- 0.076 (TIC v8.2, filled 27 Sep 2026). The two agree within
TIC's error and both are left as their sources give them. The viewer reads this tab first, so A is now drawn with
0.67 and falls back to Systems' 0.64 no longer; B's projected 135.3 AU circle has a ~1% shorter period.
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
MS, SP = "Multi-stars within 100 ly", "Sources & Provenance"
LOG = HERE / "fix_gj1177a_mass_log.json"
DATE = "6 Oct 2026"
STAR, GAIA = "GJ 1177 A", "6171492074455952128"
NEW = 0.67
OLD_SRC = ("class: SIMBAD sp_type (HD 120036A); kinematics: Gaia DR3. No mass, Teff or luminosity found: "
           "Gaia DR3 has no FLAME or GSP-Phot solution for this star.")
NEW_SRC = ("class: SIMBAD sp_type (HD 120036A); mass: Kervella et al. 2022 (J/A+A/657/A7; Mann et al. 2015 M_K "
           "relation); kinematics: Gaia DR3. No Teff or luminosity found: Gaia DR3 has no FLAME or GSP-Phot "
           "solution for this star.")
NOTE = (f"SOURCE (filled {DATE}): Kervella et al. 2022, A&A 657, A7 (VizieR J/A+A/657/A7, Table A.1), HIP 67308 = "
        f"Gaia DR3 {GAIA}: M1 = 0.67 +/- 0.01 M-sun, from the Mann et al. 2015 M_K-mass relation. "
        "TIC v8.2 gives 0.64 +/- 0.076 (Systems and Known), within its error. "
        "Sources & Provenance: 'GJ 1177 A MASS'.")


def values(tab, how="UNFORMATTED_VALUE"):
    return API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:DZ", valueRenderOption=how
                            ).execute().get("values", [])


def cells():
    """A's mass and source cells, found by name and Gaia id, never by row number."""
    v = values(MS)
    col = {h: i for i, h in enumerate(v[0])}
    rows = [i + 1 for i, r in enumerate(v) if len(r) > col["Star (component)"]
            and r[col["Star (component)"]] == STAR]
    assert len(rows) == 1, rows
    r = rows[0]
    assert str(v[r - 1][col["Gaia DR3 source_id"]]) == GAIA, v[r - 1][col["Gaia DR3 source_id"]]
    return (f"{q(MS)}!{letter(col['Mass (M-sun)'])}{r}", f"{q(MS)}!{letter(col['Star data source'])}{r}", r)


def main():
    mass, src, row = cells()
    now = gs.read_cells(SID, [mass, src])
    got = {a1: (now[a1][0][0] if now.get(a1) and now[a1][0] else "") for a1 in (mass, src)}
    old_note = gs.get_notes(SID, mass).get(mass.split("!")[1], "")
    border = gs.get_borders(SID, mass)
    sp = sp_lines(row)

    print("now:", json.dumps(got, ensure_ascii=False))
    print("note now:", repr(old_note), " border now:", json.dumps(border))
    if PLAN:
        print(f"\nWrite {NEW} to {mass} (expect empty); border unchanged (looked up, not inferred).")
        print(f"Note:\n  {NOTE}")
        print(f"Rewrite {src}:\n  {NEW_SRC}")
        print("\nSources & Provenance:\n" + "\n".join(sp))
        return

    LOG.write_text(json.dumps({"cells": [mass, src], "old": got, "old_note": old_note, "border": border},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    gs.update_cells(SID, {mass: NEW, src: NEW_SRC}, expect={mass: "", src: OLD_SRC})
    gs.set_note(SID, {mass: NOTE})
    gs.invalidate_cache(SID)
    after = gs.read_cells(SID, [mass, src])
    assert abs(float(after[mass][0][0]) - NEW) < 1e-12 and after[src][0][0] == NEW_SRC, after

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
    print("done:", json.dumps({"cells": [mass, src], "sp_rows": [sp0, sp1], "title": title}))


def sp_lines(row):
    return [
        "",
        f"GJ 1177 A MASS, {DATE.upper()}: (none) -> 0.67 M-sun",
        f"  Multi-stars within 100 ly, GJ 1177 A (row {row} today; Gaia DR3 {GAIA}), Mass (M-sun) and Star data "
        "source. The row was added (see 'MULTI-STARS ROWS 91-94') with no mass because Gaia DR3 has no "
        "FLAME solution for A.",
        "  Now 0.67 +/- 0.01: Kervella et al. 2022, A&A 657, A7 (VizieR J/A+A/657/A7, Table A.1), HIP 67308 = HD "
        "120036 A, M1 from the Mann et al. 2015 M_K-mass relation (their r_M1 'M15'), at Kmag 5.557 and Gaia EDR3 "
        "parallax 68.636 mas. Looked up, not inferred: plain border. Found by the 6 Oct 2026 star-count audit "
        "(data/star_counts/specs/C.json).",
        "  Systems within 100 ly and Known within 100ly keep A's 0.64 +/- 0.076 (TIC v8.2, Stassun et al. 2019, "
        "filled 27 Sep 2026); the two agree within TIC's error and neither is rescaled. The viewer reads this tab "
        "first, so A is drawn with 0.67, and B's projected 135.3 AU orbit has a ~1% shorter period. No luminosity "
        "changed, so no solvent band moved.",
    ]


if __name__ == "__main__":
    main()
