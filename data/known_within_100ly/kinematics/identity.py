# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fix the Known within 100ly rows the research batches found misnamed or misplaced (decided by the owner 2026-10-09).

    python identity.py plan     what would change, against the live tab; touches nothing
    python identity.py write    make the changes, with notes, a Sources & Provenance block and a rename

Each fix names its row by name + Gaia DR3 source_id, found in a fresh read, and every write is guarded by gs.update_cells'
expect=. Renamed rows keep their pipeline key through common.RENAMED. Checked by SIMBAD, CNS5 (VizieR J/A+A/670/A19)
and Gaia DR3 on 2026-10-09; the cases that turned out right as they stand get a CHECKED note instead of a change.
"""
import sys

from common import (KN, H_NAME, H_SID, H_RA, H_DE, H_L, H_B, WRITE_LOG, letter, load, now, q, read_known, row_key,
                    save, sheets)

TODAY = "2026-10-09"

RENAMES = [
    # (name now, Gaia id, new name, note)
    ("GJ 4378 B", "2421080250237097344", "GJ 4378 A",
     "RENAMED 2026-10-09 from 'GJ 4378 B'. CNS5 (5915) letters this Gaia source B, but SIMBAD and WDS J23573-1259 make "
     "GJ 4378 (G 273-186 = LDS 830A, Gaia DR3 2421080250237097344) the A component, and it is the brighter in Gaia G "
     "(11.68 vs GJ 4379's 11.84). GJ 4379 was renamed B to match."),
    ("GJ 4379 A", "2421080250237474176", "GJ 4379 B",
     "RENAMED 2026-10-09 from 'GJ 4379 A'. CNS5 (5914) letters this Gaia source A, but SIMBAD and WDS J23573-1259 make "
     "GJ 4379 (G 273-185 = LDS 830B, Gaia DR3 2421080250237474176) the B component, and it is the fainter in Gaia G "
     "(11.84 vs GJ 4378's 11.68). GJ 4378 was renamed A to match."),
    ("GJ 257 A", "5559035514779971456", "GJ 257 B",
     "RENAMED 2026-10-09 from 'GJ 257 A' (CNS5 1724's letter). This workbook's Multi-stars tab, row 'GJ 257 B', "
     "identifies Gaia DR3 5559035514779971456 as GJ 257 B (LPM 248 B) in the WDS geometry, and the tab's plotted row "
     "'GJ 257 A' is the other source, 5559035514776717312; SIMBAD and CNS5 swap the two Gaia identifiers (see that "
     "Multi-stars row's Separation note). Not yet marked Plotted: this tab was built on 2026-09-28, before Multi-stars "
     "gained its GJ 257 B row."),
    ("GJ 10808", "287767756635519488", "GJ 10808 B",
     "RENAMED 2026-10-09 from 'GJ 10808' (CNS5 1421, no component). This Gaia source is the B component of the "
     "0.65-arcsec pair 2MASS J05431887+6422528 AB (Gagne et al. 2023, ApJ 945, 119; VizieR J/ApJ/945/119 'members'); "
     "A is Gaia DR3 287767760932246144, renamed GJ 10808 A."),
    ("Gaia DR3 287767760932246144", "287767760932246144", "GJ 10808 A",
     "RENAMED 2026-10-09 from 'Gaia DR3 287767760932246144'. The A component of 2MASS J05431887+6422528 AB (Gagne et "
     "al. 2023, ApJ 945, 119), whose B is CNS5's GJ 10808 (1421); named for that system, as this tab names "
     "components."),
]

CHECKED = [
    # (name, Gaia id, note): left as they are
    ("GJ 11905 A", "",
     "CHECKED 2026-10-09: not a duplicate of GJ 11906 B. CNS5 3258 (GJ 11905 A) and 3259 (GJ 11906 B) are the two "
     "components of NLTT 33370 AB = LP 497-33, an equal-mass M7+M7 pair 0.1-0.2 arcsec apart, which SIMBAD keeps as "
     "one object. CNS5 gives A the Gaia DR3 source 3742871034173807488, a 2-parameter solution (no parallax or proper "
     "motion), which is why this row has no Gaia id."),
    ("GJ 11906 B", "",
     "CHECKED 2026-10-09: not a duplicate of GJ 11905 A. CNS5 3258 (GJ 11905 A) and 3259 (GJ 11906 B) are the two "
     "components of NLTT 33370 AB = LP 497-33, an equal-mass M7+M7 pair 0.1-0.2 arcsec apart, which SIMBAD keeps as "
     "one object."),
    ("GJ 3879 B", "1188693088920139136",
     "CHECKED 2026-10-09: the name is right. CNS5 3696 and WDS J14565+1755B both make GJ 3879 (LHS 3002, Gaia DR3 "
     "1188693088920139136) the B component of the pair with GJ 3878 A; SIMBAD's main id is plain 'GJ 3879'."),
    ("GJ 12804 B", "6644840974200903808",
     "CHECKED 2026-10-09: kept as CNS5 has it. CNS5 4783 makes this Gaia source GJ 12804 B, companion of GJ 12802 A "
     "30 arcsec away; SIMBAD names it 'L 274-88 A'. The catalogues pair it differently, so the letters differ; "
     "neither is a misidentification."),
]

# GJ 10108 B: CNS5 191 gives 54 Psc A's position; 54 Psc B is the T7.5 brown dwarf 43 arcsec away.
MOVE = ("GJ 10108 B", "", 9.828823, 21.254530,
        "SOURCE: SIMBAD '54 Psc B' (T7.5 brown dwarf), coordinates from Dupuy & Liu 2012, ApJS 201, 19, epoch J2000. "
        "Corrected 2026-10-09: CNS5 191 gave 9.838722, 21.248884, which is 54 Psc A's position, 43 arcsec away.",
        "CNS5 191 (GJ 10108 B) is 54 Psc B, the T7.5 brown dwarf 43 arcsec from 54 Psc A. CNS5 gives it A's position; "
        "RA/Dec corrected to 54 Psc B's on 2026-10-09 and Galactic l/b recomputed from them. (At the old position SIMBAD "
        "finds '54 Psc c', a planet candidate of A.) A brown dwarf, so a planet under this workbook's star/planet rule "
        "(docs/hybrasil-instructions.md section 6).")


def main():
    mode = (sys.argv[1:] or ["plan"])[0]
    assert mode in ("plan", "write"), mode
    from merge import velocity
    gs, sid, api = sheets()
    h, rows = read_known(api, sid)
    col = {k: i for i, k in enumerate(h)}
    at = {row_key(r[col[H_NAME]], r[col[H_SID]]): n for n, r in enumerate(rows, start=2)}

    def row(name, gaia):
        n = at.get(row_key(name, gaia))
        if n is None:
            raise SystemExit(f"no live row is {name!r} / {gaia!r}: already done, or the tab changed.")
        return n

    def cell(hd, n):
        return f"{q(KN)}!{letter(col[hd])}{n}"

    updates, expect, notes, orange = {}, {}, {}, []
    for old, gaia, new, note in RENAMES:
        n = row(old, gaia)
        updates[cell(H_NAME, n)] = new
        expect[cell(H_NAME, n)] = old
        expect[cell(H_SID, n)] = gaia
        notes[cell(H_NAME, n)] = note
    for name, gaia, note in CHECKED:
        n = row(name, gaia)
        expect[cell(H_NAME, n)] = name
        notes[cell(H_NAME, n)] = note
    name, gaia, ra, de, pos_note, name_note = MOVE
    n = row(name, gaia)
    live = rows[n - 2]
    l, b, *_ = velocity(ra, de, None, 0, 0, None)
    for hd, v in ((H_RA, ra), (H_DE, de), (H_L, round(l, 3)), (H_B, round(b, 3))):
        updates[cell(hd, n)] = v
        expect[cell(hd, n)] = live[col[hd]]
    expect[cell(H_NAME, n)] = name
    notes[cell(H_RA, n)] = notes[cell(H_DE, n)] = pos_note
    gal = ("INFERRED: RA/Dec through the IAU ICRS-to-Galactic rotation (astropy). Exact transform; no model. "
           "Recomputed 2026-10-09 from the corrected position.")
    notes[cell(H_L, n)] = notes[cell(H_B, n)] = gal
    orange += [cell(H_L, n), cell(H_B, n)]
    notes[cell(H_NAME, n)] = name_note

    # append to any note already on a name cell rather than replace it
    for a1 in list(notes):
        if a1.split("!")[1].startswith(letter(col[H_NAME])):
            old = gs.get_notes(sid, a1).get(a1.split("!")[1], "")
            if old and old not in notes[a1]:
                notes[a1] = old + "\n\n" + notes[a1]

    for a1, v in updates.items():
        print(f"  {a1}: {expect[a1]!r} -> {v!r}")
    print(f"{len(updates)} values, {len(notes)} notes, {len(orange)} orange boxes")
    if mode == "plan":
        return
    log = load(WRITE_LOG, {"runs": []})
    run = {"kind": "identity", "started": now(), "state": "cells", "updates": updates}
    log["runs"].append(run)
    save(WRITE_LOG, log)
    gs.update_cells(sid, updates, expect=expect)
    gs.set_note(sid, notes)
    gs.set_border(sid, orange, gs.INFERRED_BORDER)
    gs.invalidate_cache(sid)
    from write import append_sp
    run["sp_rows"] = append_sp(gs, api, sid, [
        "", f"{TODAY}: 'Known within 100ly' -- ROW IDENTITIES CORRECTED (data/known_within_100ly/kinematics/"
            "identity.py). Raised by the motion research batches (LEDGER.md), decided by the owner, checked against "
            "SIMBAD, CNS5 (VizieR J/A+A/670/A19) and Gaia DR3. Each changed or checked name cell carries a note.",
        "  Renamed: GJ 4378 B -> GJ 4378 A and GJ 4379 A -> GJ 4379 B (CNS5's letters run against WDS J23573-1259, "
        "SIMBAD and Gaia G); the unplotted 'GJ 257 A' (Gaia DR3 5559035514779971456) -> GJ 257 B, as the Multi-stars "
        "tab already identifies it (the plotted GJ 257 A is the other source); GJ 10808 -> GJ 10808 B and Gaia DR3 "
        "287767760932246144 -> GJ 10808 A (2MASS J05431887+6422528 AB, Gagne et al. 2023).",
        "  Moved: GJ 10108 B (54 Psc B) carried CNS5's position, which is 54 Psc A's; RA/Dec now SIMBAD's for 54 Psc B "
        "(Dupuy & Liu 2012, epoch J2000), l/b recomputed (orange).",
        "  Checked and left as they are: GJ 11905 A / GJ 11906 B (CNS5's two components of the 0.1-arcsec binary NLTT "
        "33370 AB, not duplicates), GJ 3879 B (CNS5 and WDS agree), GJ 12804 B (CNS5's lettering; SIMBAD's 'L 274-88 "
        "A' pairs it differently).",
        "  The motion pipeline keeps its own keys for renamed rows (kinematics/common.py RENAMED)."])
    run["title"] = gs.rename_workbook(None, gs.versioned_title())
    run["state"], run["finished"] = "done", now()
    save(WRITE_LOG, log)
    print("done:", run["title"], gs.spreadsheet_url(sid))


if __name__ == "__main__":
    main()
