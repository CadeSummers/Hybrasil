# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""VHS J125601.92-125723.9 A and B are brown dwarfs: B to Planets, both Multi-stars rows go, the system has no star.

    python migrate_vhs1256.py          plan: print every write; touches nothing
    python migrate_vhs1256.py write    write it all, log the deleted rows, provenance, rename

The pair sat on the TODO watch list at the hydrogen-burning limit. Dupuy et al. 2023 (MNRAS 519, 1688) measure a
dynamical total mass of 0.141 +/- 0.008 M-sun and call the components 'possibly brown dwarfs with masses of 74 +/- 4
MJup if their mass ratio is near unity'; the abstract allows 'a brown dwarf binary or pair of very low-mass stars'.
No source says either sustains hydrogen fusion, and docs/hybrasil-instructions.md section 6 files an object the
literature leaves undecided as a planet. The owner chose to migrate (7 Oct 2026).

Filed as add_bd_companions.py filed the starless pairs: the companion is the planet-tab row, and the brown-dwarf
primary fills the host columns. So B goes to Planets round A, A stays the Systems row's host (the viewer draws it at
the centre, as it does WISE 1217+16 A), both Multi-stars rows are deleted, and the Systems row counts no star.
The planet b (Planets) already goes round A and is not touched. The row is built by migrate_bds.py's own
planet_spec() and add_rows(); every deleted row is kept, values, formulas and notes, in migrate_vhs1256_log.json.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
import migrate_bds as M  # noqa: E402  (its PLAN is unused here; ours is below)

gs, q, letter, API, SID = M.gs, M.q, M.letter, M.API, M.SID
PLAN = "write" not in sys.argv[1:]
LOG = HERE / "migrate_vhs1256_log.json"
SYS = "VHS J125601.92-125723.9"
B = f"{SYS} B"
D23 = "Dupuy et al. 2023, MNRAS 519, 1688 (arXiv:2208.08448)"
MOVE = (M.MS, SYS, B, M.PN, B, SYS, "confirmed")
WHY = (f"Its primary, {SYS} (A), is a brown dwarf too: {D23} give 0.141 +/- 0.008 M-sun for the pair, 'possibly brown "
       "dwarfs with masses of 74 +/- 4 MJup' each, and no source says either sustains hydrogen fusion. So the "
       "system has no star; A fills the host columns, as the starless pairs of add_bd_companions.py do.")


def main():
    sy, ms, pn = M.Tab(M.SY, "System / Host"), M.Tab(M.MS, "Star (component)"), M.Tab(M.PN, "Planet")
    taken = {r[0] for t in (pn, M.Tab(M.UN, "Planet"), M.Tab("Rejected candidates", "Planet")) for r in t.v[1:] if r}
    assert B not in taken, f"{B} is already on a planet tab or rejected"
    r_a, r_b = ms.find(SYS), ms.find(B)
    assert [ms.row(r)["Star (component)"] for r in ms.rows_of(SYS)] == [SYS, B]

    spec, orange, notes, facts = M.planet_spec(MOVE, ms, sy, {SYS, B}, M.marks(ms, [r_a, r_b]))
    # Published, not Kepler's: Dupuy et al. 2023 fit the period.
    kepler = facts["p"]
    spec["Orbital period (d)"] = facts["p"] = round(7.31 * 365.25, 2)
    assert f"P {kepler} d" in spec["Orbit data source / flags"]
    spec["Orbit data source / flags"] = spec["Orbit data source / flags"].replace(
        f"P {kepler} d", f"P {facts['p']} d (published)")
    orange.pop("Orbital period (d)", None)
    notes["Orbital period (d)"] = f"{D23}: P = 7.31 +/- 0.02 yr, x 365.25."
    spec["Detection method"] = "Imaging"
    spec["Orbit data source / flags"] += " " + WHY
    sib = pn.find(f"{SYS} b")
    for h in ("HZ inner, optimistic (au)", "HZ inner, conservative (au)", "HZ outer, conservative (au)",
              "HZ outer, optimistic (au)"):
        spec[h] = pn.row(sib)[h]

    sr = sy.find(SYS, "System / Host")
    srow = sy.row(sr)
    assert srow["Stars in system"] == 2 and srow["Confirmed planets"] == 1, srow
    mj = spec["Mass (M-earth)"] / 317.828
    sy_upd = {
        sy.a1("Stars in system", sr): 0,
        sy.a1("System stars", sr): (f"none: {SYS} (M7.5) and its 7.3 yr partner B are brown dwarfs, planets under the "
                                    "model's rule; A fills the host columns, B and b are on Planets"),
        sy.a1("Confirmed planets", sr): 2,
        sy.a1("Planet masses (M-earth)", sr): (f"{srow['Planet masses (M-earth)']}\n"
                                               f"{B}:{spec['Mass (M-earth)']:.0f} ({mj:.1f} MJ, brown dwarf)"),
    }
    sy_exp = {k: srow[h] for k, h in zip(sy_upd, ("Stars in system", "System stars", "Confirmed planets",
                                                   "Planet masses (M-earth)"))}
    stars_note = (f"{M.DATE}: 2 -> 0. {SYS} and {SYS} B are brown dwarfs under the model's rule "
                  f"({M.RULE}): {D23}, 74 +/- 4 MJup each, 'possibly brown dwarfs', and no source says either fuses "
                  "hydrogen. B is on Planets round A; A stays the host (migrate_vhs1256.py).")

    print(f"Planets row: {spec['Planet']} round {spec['Planet-host star']}: a={facts['a']} P={spec['Orbital period (d)']}"
          f" e={facts['e']} M={facts['mass_sun']} M-sun = {spec['Mass (M-earth)']} M-earth, L={spec['Host luminosity (L-sun)']}"
          f", tier {spec['Confidence tier']}, orange={sorted(orange)}, notes={sorted(notes)}")
    print("  flags:", spec["Orbit data source / flags"])
    print("Systems:", json.dumps({k: [sy_exp[k], v] for k, v in sy_upd.items()}, ensure_ascii=False))
    print("Multi-stars rows deleted:", [SYS, B], "at", [r_a, r_b])
    sp = ["", f"VHS J1256-1257 A AND B ARE BROWN DWARFS, {M.DATE.upper()}",
          f"  From the TODO watch list. {D23}: dynamical total mass 0.141 +/- 0.008 M-sun; 'possibly brown dwarfs with "
          "masses of 74 +/- 4 MJup if their mass ratio is near unity'; the abstract allows 'a brown dwarf binary or "
          "pair of very low-mass stars'; lithium not detected, which at 140 Myr does not decide it. No source says "
          f"either sustains hydrogen fusion, so under the model's rule ({M.RULE}: 'where the literature calls it a "
          "brown dwarf, or leaves it undecided, file it as a planet') both are planets. Owner's decision, 7 Oct 2026.",
          f"  {B} -> Planets within 100 ly (round {SYS}, tier confirmed): a 1.96 AU, P 7.31 yr (published), e 0.883, "
          f"M {facts['mass_sun']} M-sun = {spec['Mass (M-earth)']} M-earth. {SYS} (A) is not given a planet row: as "
          "with the starless pairs of add_bd_companions.py, the brown-dwarf primary fills the host columns, and the "
          "Systems row stays as the host's. Multi-stars rows of A and B deleted (kept, values, formulas and notes, in "
          "data/star_counts/migrate_vhs1256_log.json). Systems: Stars in system 2 -> 0, Confirmed planets 1 -> 2. The "
          "Known within 100ly tab's typed counts are left for the same pass as the other migrated brown dwarfs. "
          "Script: data/star_counts/migrate_vhs1256.py."]
    if PLAN:
        print("\n".join(sp))
        return

    props = {s["properties"]["title"]: s["properties"] for s in
             API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}
    log = {"deleted": {}, "planet_rows": {}}
    for r in (r_a, r_b):
        n = ms.row(r)["Star (component)"]
        log["deleted"][f"{M.MS} / {n}"] = {
            "row": r, "values": ms.row(r),
            "formulas": {h: ms.formula(r, h) for h in ms.h if str(ms.formula(r, h)).startswith("=")},
            "notes": gs.get_notes(SID, f"{q(M.MS)}!A{r}:{letter(len(ms.h) - 1)}{r}")}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")

    M.add_rows(M.PN, [(MOVE, spec, orange, notes, facts)], props, log)
    gs.update_cells(SID, sy_upd, expect=sy_exp)
    a1 = sy.a1("Stars in system", sr)
    old = gs.get_notes(SID, a1).get(a1.split("!")[1], "")
    gs.set_note(SID, {a1: (old + "\n\n" + stars_note) if old else stars_note})

    t = M.Tab(M.MS, "Star (component)")
    for r in sorted((t.find(SYS), t.find(B)), reverse=True):
        assert t.row(r)["Star (component)"] in (SYS, B)
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"deleteDimension": {"range": {
            "sheetId": props[M.MS]["sheetId"], "dimension": "ROWS", "startIndex": r - 1, "endIndex": r}}}]}).execute()
    gs.invalidate_cache(SID)
    t = M.Tab(M.MS, "Star (component)")
    assert not {SYS, B} & {r[1] for r in t.v[1:] if len(r) > 1}, "a Multi-stars row survived"

    meta = API.get(spreadsheetId=SID, ranges=[f"{q(M.SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(M.SP)}!A{end}"])[f"{q(M.SP)}!A{end}"][0][0].strip()
    sp0, sp1 = end + 1, end + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(M.SP)}!A{sp0}:A{sp1}": [[x] for x in sp]},
                    expect={f"{q(M.SP)}!A{i}": "" for i in (sp0, sp1)})
    log.update(sp_rows=[sp0, sp1], title=gs.rename_workbook(None, gs.versioned_title()))
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("done:", json.dumps({k: v for k, v in log.items() if k != "deleted"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
