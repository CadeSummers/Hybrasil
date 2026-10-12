# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ksi UMa Bb is a star, not a brown dwarf: role, mass and inclination from Fuhrmann 2008, barycentres re-derived.

    python fix_ksi_uma_bb.py          plan: print every write; touches nothing
    python fix_ksi_uma_bb.py write    write, note, provenance, rename

The TODO watch list (7 Oct 2026) kept ksi UMa Bb a star on the strength of its MSC class 'WD?', with the role
'brown dwarf' and the MSC's SB1 minimum mass, 0.04 M-sun. The literature makes it a star either way:
  - Fuhrmann 2008, MNRAS 384, 173: M_Bb = 0.14 (-0.05/+0.09) M-sun, 'an ordinary M dwarf', from an inclination of
    about 15 deg (Ba's v sin i = 3.0 +/- 1.0 km/s under bound rotation) and Griffin 1998's mass function.
  - Fuhrmann et al. 2016, MNRAS 459, 1682: Ba is barium-enriched against Aa, so Bb may be a white dwarf.
The owner chose role + mass (7 Oct 2026). The mass only holds at i ~ 15 deg, so the orange i = 60 (median of random
orientations) goes with it. Ba's mass stays the MSC's 0.96 (Fuhrmann used 0.86): the workbook's figures are taken
as they are.

The subsystems above Bb follow by the tab's own definitions (fix_bd_barycentres.py): a subsystem's mass is its pair's
sum, its barycentre a * M_sec / (M_prim + M_sec) from 'Barycentre from'. ksi UMa D, a planet round ksi UMa AB since
migrate_bds.py, has an orange period from Kepler's law on AB's mass, so it moves too.
"""
import json
import math
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
PL, PN, SP = "Planetless 4+ Stars", "Planets within 100 ly", "Sources & Provenance"
LOG = HERE / "fix_ksi_uma_bb_log.json"
DATE = "7 Oct 2026"
M_EARTH_PER_M_SUN = 332946.0487
F08 = "Fuhrmann 2008, MNRAS 384, 173"
F16 = "Fuhrmann et al. 2016, MNRAS 459, 1682"
M_BB, I_BB = 0.14, 15
ROLE = (f"star: the unseen SB1 companion of Ba -- an ordinary M dwarf by its mass ({F08}) or a white dwarf by Ba's "
        f"barium excess ({F16}); not a brown dwarf")


def values(tab):
    return API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:DZ3000", valueRenderOption="UNFORMATTED_VALUE"
                            ).execute()["values"]


def main():
    v = values(PL)
    col = {x: i for i, x in enumerate(v[0])}

    def cell(r, h):
        row = v[r - 1]
        return row[col[h]] if col[h] < len(row) else ""

    def find(name):
        hits = [i + 1 for i, r in enumerate(v) if i and len(r) > 1 and r[0] == "ksi UMa" and r[col["Star (component)"]] == name]
        assert len(hits) == 1, (name, hits)
        return hits[0]

    def a1(h, r, tab=PL, c=None):
        return f"{q(tab)}!{letter((c or col)[h])}{r}"

    r_bb, r_ba, r_b, r_a, r_ab = (find(n) for n in ("ksi UMa Bb", "ksi UMa Ba", "ksi UMa B", "ksi UMa A", "ksi UMa AB"))
    m_ba, m_a = cell(r_ba, "Mass (M-sun)"), cell(r_a, "Mass (M-sun)")
    a_bb, a_b = cell(r_bb, "Separation (AU)"), cell(r_b, "Separation (AU)")
    assert cell(r_b, "Barycentre from") == "ksi UMa Ba" and cell(r_ab, "Barycentre from") == "ksi UMa A"
    m_b = round(m_ba + M_BB, 6)
    m_ab = round(m_a + m_b, 6)
    off_b = round(a_bb * M_BB / m_b, 6)
    off_ab = round(a_b * m_b / m_ab, 6)

    upd, exp, notes, plain = {}, {}, {}, []

    def put(addr, new, old, note=None):
        upd[addr], exp[addr] = new, old
        if note:
            notes[addr] = note

    old_src = cell(r_bb, "Star data source")
    put(a1("Role in system", r_bb), ROLE, cell(r_bb, "Role in system"))
    put(a1("Mass (M-sun)", r_bb), M_BB, cell(r_bb, "Mass (M-sun)"),
        f"{DATE}: was 0.04, the MSC's SB1 minimum mass. {F08}: M_Bb = 0.14 (-0.05/+0.09) M-sun, 'an ordinary M dwarf', "
        "from i ~ 15 deg (Ba's v sin i 3.0 +/- 1.0 km/s, bound rotation and coplanarity assumed) and the mass function "
        f"of Griffin 1998, with M_Ba = 0.86. {F16} suggest a white dwarf instead (Ba is barium-enriched); a star either "
        "way. fix_ksi_uma_bb.py.")
    put(a1("Mass basis (MSC)", r_bb), f"{F08}: from i ~ 15 deg and the SB1 mass function (MSC: minimum mass 0.04, SB1)",
        cell(r_bb, "Mass basis (MSC)"))
    put(a1("Star data source", r_bb), old_src + f"; mass and inclination: {F08} (M_Bb 0.14, i ~ 15 deg); nature: {F16} "
        "(white dwarf suggested from Ba's barium excess)", old_src)
    put(a1("Inclination (deg)", r_bb), I_BB, cell(r_bb, "Inclination (deg)"),
        f"{F08}: i ~ 15 deg, from Ba's v sin i = 3.0 +/- 1.0 km/s, assuming bound rotation and coplanarity; the mass "
        f"0.14 M-sun is derived at this inclination, so the two go together. Was 60 (orange: the median of randomly "
        f"oriented orbits), replaced {DATE} by fix_ksi_uma_bb.py. The sense (15 or 165) is not known.")
    plain.append(a1("Inclination (deg)", r_bb))
    put(a1("Mass (M-sun)", r_b), m_b, cell(r_b, "Mass (M-sun)"))
    put(a1("Barycentre offset (AU)", r_b), off_b, cell(r_b, "Barycentre offset (AU)"),
        f"INFERRED: a x M_sec / (M_prim + M_sec) = {a_bb} au x {M_BB} / ({m_ba} + {M_BB}), from 'ksi UMa Bb' "
        f"(Separation (AU), Mass) and 'ksi UMa Ba' (Mass). The barycentre of ksi UMa B lies this far from ksi UMa Ba, "
        f"on the line to ksi UMa Bb. {DATE}: was {cell(r_b, 'Barycentre offset (AU)')}, with Bb's minimum mass 0.04; "
        f"re-derived with {F08}'s 0.14 (fix_ksi_uma_bb.py).")
    put(a1("Mass (M-sun)", r_ab), m_ab, cell(r_ab, "Mass (M-sun)"))
    put(a1("Barycentre offset (AU)", r_ab), off_ab, cell(r_ab, "Barycentre offset (AU)"),
        f"INFERRED: a x M_sec / (M_prim + M_sec) = {a_b} au x {m_b} / ({m_a} + {m_b}), from 'ksi UMa B' "
        f"(Separation (AU), Mass) and 'ksi UMa A' (Mass). The barycentre of ksi UMa AB lies this far from ksi UMa A, "
        f"on the line to ksi UMa B. {DATE}: was {cell(r_ab, 'Barycentre offset (AU)')}, with Bb at 0.04 M-sun; "
        f"re-derived with {F08}'s 0.14 (fix_ksi_uma_bb.py).")
    for r in (r_b, r_ab):
        old = cell(r, "Mass (M-sun)")
        notes[a1("Mass (M-sun)", r)] = (f"{DATE}: was {old}; the sum of its pair's masses, re-derived with ksi UMa Bb at "
                                        f"{F08}'s 0.14 M-sun in place of the MSC minimum mass 0.04 (fix_ksi_uma_bb.py).")

    # ksi UMa D, round ksi UMa AB: its orange period is Kepler's law on AB's mass plus its own.
    pv = values(PN)
    pcol = {x: i for i, x in enumerate(pv[0])}
    r_d = [i + 1 for i, r in enumerate(pv) if i and r and r[0] == "ksi UMa D"]
    assert len(r_d) == 1, r_d
    d = pv[r_d[0] - 1]
    assert d[pcol["Planet-host star"]] == "ksi UMa AB"
    a_d, p_old = d[pcol["Semi-major axis (au)"]], d[pcol["Orbital period (d)"]]
    m_d = round(d[pcol["Mass (M-earth)"]] / M_EARTH_PER_M_SUN, 4)
    assert abs(math.sqrt(a_d ** 3 / (cell(r_ab, "Mass (M-sun)") + m_d)) * 365.25 - p_old) / p_old < 1e-6, "D's P basis"
    p_new = round(math.sqrt(a_d ** 3 / (m_ab + m_d)) * 365.25, 3)
    pd = a1("Orbital period (d)", r_d[0], PN, pcol)
    old_note = gs.get_notes(SID, pd).get(pd.split("!")[1], "")
    put(pd, p_new, p_old, old_note + f"\n\n{DATE}: was {p_old} d with M_tot = {cell(r_ab, 'Mass (M-sun)')} + {m_d}; "
        f"now ({a_d}^3 / ({m_ab} + {m_d}))^(1/2) yr = {p_new} d, ksi UMa AB's mass having moved with ksi UMa Bb's "
        f"({F08}; fix_ksi_uma_bb.py).")

    for k in upd:
        print(f"  {k}: {exp[k]!r:.70} -> {upd[k]!r:.110}")
    sp = ["", f"KSI UMA Bb IS A STAR, NOT A BROWN DWARF, {DATE.upper()}",
          "  From the TODO watch list. The Planetless row had role 'brown dwarf', class 'WD?' (MSC) and the MSC's SB1 "
          f"minimum mass 0.04 M-sun. {F08} (its text on xi UMa):M_Bb = 0.14 (-0.05/+0.09) M-sun, 'an ordinary M "
          "dwarf', from i ~ 15 deg (Ba's v sin i 3.0 +/- 1.0 km/s, bound rotation) and Griffin 1998's mass function. "
          f"{F16}: Ba is barium-enriched against Aa, which suggests Bb is a white dwarf. Either way a star under the "
          "model's rule (docs/hybrasil-instructions.md section 6). Wikipedia's Xi Ursae Majoris page quotes the 2008 "
          "mass with its error bars swapped; the paper's are used.",
          "  Written: Bb role, mass 0.04 -> 0.14, mass basis, star data source, inclination 60 (orange, the median of "
          f"random orientations) -> 15 (published; plain rule restored), since the mass holds only at that inclination. "
          f"Re-derived by the tab's own definitions: ksi UMa B mass -> {m_b}, offset -> {off_b}; ksi UMa AB mass -> "
          f"{m_ab}, offset -> {off_ab}; ksi UMa D (Planets, round AB) orange period {p_old} -> {p_new} d. Ba keeps the "
          "MSC's 0.96 M-sun (Fuhrmann used 0.86). Old values are in each cell's note. Script: "
          "data/star_counts/fix_ksi_uma_bb.py."]
    if PLAN:
        print("\n".join(sp))
        return
    gs.update_cells(SID, upd, expect=exp)
    gs.set_note(SID, notes)
    gs.set_border(SID, plain, gs.PLAIN_RULE, style="SOLID")
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
    LOG.write_text(json.dumps({"written": {k: [exp[k], upd[k]] for k in upd}, "sp_rows": [sp0, sp1], "title": title},
                              indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("done:", title, [sp0, sp1])


if __name__ == "__main__":
    main()
