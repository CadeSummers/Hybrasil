# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""BD+39 496 B (HD 13507): Grandjean et al. 2021's two brown dwarfs in place of the refuted single companion.

    python hd13507.py          plan: print every cell it would change
    python hd13507.py write    write, insert two rows, re-border, note, provenance, rename

The tab drew BD+39 496 Bb from the MSC's orbit for Ba,Bb -- Tokovinin's fit to Fischer et al. 2014's Lick RVs:
P = 6870 d, e = 0.338, K1 = 0.84 km/s, m sin i = 0.07 M_sun, a single companion. The single-companion fits in the
literature disagree with each other (Perrier et al. 2003: ~3000 d, 52 MJ; Wilson et al. 2016: 4890 d, 67 MJ; the
MSC: 6870 d), and Grandjean et al. 2021 (A&A 650, A39, arXiv:2106.10754, Sect. 3.1.2), fitting ELODIE + SOPHIE RVs,
refute the single solution and propose two brown dwarfs: 0.02 and 0.03 M_sun (21 and 31 MJup) at 4.2 au (8.3 yr)
and 5.4 au (12.1 yr), e = 0.27 and 0.2, near 3:2 resonance -- 'Other degenerate solutions may exist' and 'this
solution should be taken with caution, given the limited number of data points available'. No uncertainties, no
omega, no epoch. Gaia DR3 has no non-single-star solution (non_single_star = 0, RUWE 3.02). The owner chose (4 Oct
2026) to draw the two, hollow.

The tab is a tree of pairs (data/hierarchy.py), so a star cannot hold two companions directly. As Castor's C is
Cab + Cc, B becomes Bab + Bc: Bb (= HD 13507 b) orbits Ba inside the subsystem Bab, and Bc (= HD 13507 c) orbits
Bab's barycentre -- Jacobi coordinates; Bb's pull moves that point 0.085 au off Ba.

Taken as printed, including the paper's internal disagreement: a^3/P^2 at 4.2 au, 8.3 yr (or 5.4 au, 12.1 yr) is
1.076 M_sun, against the tab's 0.99 and 1.02 -- a 2-3% difference in a, within the rounding of '8.3 yr'.

Also corrects Rejected candidates' row for the single solution (planet_hosts.py, 2 Oct 2026): its 'b 20 MJ min,
P 3029.5 d; c 30 MJ min, P 4416.5 d' is not in the paper, which prints 21 / 31 MJup and 8.3 / 12.1 yr, and its
'Wilson et al. 2006' is Grandjean's 'Wilson et al. (2016)'.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from hybrasil.data import google_sheets as gs  # noqa: E402
from hybrasil.data.catalog_loader import _phase_deg  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)
from build import GREY_RULE  # noqa: E402  (this tab's plain rule; gs.PLAIN_RULE is black)

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
FP, RJ, SP = "Planetless 4+ Stars", "Rejected candidates", "Sources & Provenance"
ORANGE = gs.INFERRED_BORDER
YR = 365.25
J2000, J2016 = 2451545.0, 2457389.0
HYPO = "hypothetical and model-inferred"
DATE = "4 Oct 2026"

SYS = "BD+39 496"
BA, B, BAB, BB, BC, A, AA, AB = (f"{SYS} {x}" for x in ("Ba", "B", "Bab", "Bb", "Bc", "A", "Aa", "Ab"))
OLD_TREE, NEW_TREE = "(Ba,Bb),(Aa,Ab)", "((Ba,Bb),Bc),(Aa,Ab)"

G21 = "Grandjean et al. 2021, A&A 650, A39 (arXiv:2106.10754), Sect. 3.1.2"
G21_SHORT = "Grandjean+ 2021 A&A 650, A39 (2-BD sol., 'with caution')"
CAUTION = ("'Other degenerate solutions may exist' and 'this solution should be taken with caution, given the "
           "limited number of data points available' (no uncertainties given).")
PLX_MAS = 37.89                 # the tab's parallax for every BD+39 496 row (MSC, DR3)
M_BA, M_AAB = 0.97, 1.14        # Ba (MSC) and the A subsystem (MSC), unchanged
A_SEP, A_PA = 16233.83478, 160.2  # A's projected separation from B (au) and position angle (MSC), unchanged

# The two brown dwarfs as Grandjean et al. 2021 print them: a in au, P in yr, e, m sin i in M_sun.
COMP = {
    BB: dict(letter="b", a=4.2, p_yr=8.3, e=0.27, m=0.02, mj=21, prim=BA, prim_label="Ba"),
    BC: dict(letter="c", a=5.4, p_yr=12.1, e=0.20, m=0.03, mj=31, prim=BAB, prim_label="Bab"),
}
M_BAB = round(M_BA + COMP[BB]["m"], 4)
M_B = round(M_BAB + COMP[BC]["m"], 4)
OFF_BAB = round(COMP[BB]["a"] * COMP[BB]["m"] / (M_BA + COMP[BB]["m"]), 6)
OFF_B = round(COMP[BC]["a"] * COMP[BC]["m"] / (M_BAB + COMP[BC]["m"]), 6)
I_DEG = 60.0
NODE = round(_phase_deg(f"{BB} node"), 3)          # Bb's, unchanged; Bc is drawn coplanar with it
for n, c in COMP.items():
    c["p_d"] = round(c["p_yr"] * YR, 3)
    c["arcsec"] = round(c["a"] * PLX_MAS / 1000.0, 6)
    c["omega"] = round(_phase_deg(f"{n} omega"), 3)
    c["phase"] = _phase_deg(n)
    c["t"] = round(J2000 + ((360.0 - c["phase"]) % 360.0) / 360.0 * c["p_d"], 4)
    c["kepler_m"] = c["a"] ** 3 / c["p_yr"] ** 2
M_TOT_A = round(M_B + M_AAB, 4)
_P_A = math.sqrt(A_SEP ** 3 / M_TOT_A) * YR       # infer.py's rule: T from the unrounded period
P_A, T_A = round(_P_A, 3), round(J2016 + ((360.0 - A_PA) % 360.0) / 360.0 * _P_A, 4)

WAS_SINGLE = ("Was the MSC's single-companion orbit (Tokovinin from Fischer et al. 2014 data: P = 6870 d, e = 0.338, "
              "omega = 169, m sin i = 0.07 M_sun, a = 7.0995 au), which Grandjean et al. 2021 refute.")


def comp_notes(n):
    """{header: (note, orange?)} for one brown dwarf's orbit cells."""
    c = COMP[n]
    k = c["kepler_m"]
    mtot = M_BA + c["m"] if n == BB else M_BAB + c["m"]
    was = f" {WAS_SINGLE}" if n == BB else ""
    weak = "WEAK: the paper gives no omega and no epoch; nothing measures this orbit's orientation.\nINFERRED (model): "
    return {
        "Mass (M-sun)": (f"SOURCE: {G21}: 'two BD companions of lower masses, 0.02 and 0.03 M_sun (21 MJup and 31 "
                         f"MJup, respectively)'. RV only, so a minimum mass (m sin i); {c['m']} M_sun = HD 13507 "
                         f"{c['letter']}. {CAUTION}{was}", False),
        "Orbital eccentricity (e)": (f"SOURCE: {G21}: e = {c['e']}. The fit constrained both eccentricities below "
                                     "0.3 and regularised them with a normal prior (0, 0.1) (the paper's footnote)."
                                     + was, False),
        "Separation (AU)": (f"SOURCE: {G21}: 'orbiting at 4.2 (<=> 8.3 yr) and 5.4 au (<=> 12.1 yr)'; {c['a']} au "
                            f"as printed. Taken with the paper's own disagreement: a^3 / P^2 = {k:.3f} M_sun against "
                            f"this tab's {mtot:.2f}, a {100 * ((k / mtot) ** (1 / 3) - 1):.1f}% difference in a, "
                            f"within the rounding of the period.{was}", False),
        "Orbital period (d)": (f"INFERRED: {c['p_yr']} yr x 365.25 = {c['p_d']} d. {G21} gives the period only as "
                               f"'{c['p_yr']} yr', to 0.1 yr (+-18 d).{was}", True),
        "Separation (arcsec)": (f"INFERRED: a x parallax = {c['a']} au x {PLX_MAS} mas (the MSC's, as on every "
                                f"{SYS} row)." + (" Was 0.269\" (MSC)." if n == BB else ""), True),
        "Argument of periastron (deg)": (weak + f"omega from the name hash of '{n} omega' "
                                         "(catalog_loader._phase_deg), as infer.py does for an orbit lacking it.", True),
        "Time of periastron (JD)": (weak + f"phase {c['phase']:.3f} deg at J2000 from the name hash "
                                    "(catalog_loader._phase_deg).", True),
        "Argument of periastron refers to": (f"INFERRED by rule: an RV fit quotes the star's omega. Moot while omega "
                                             "is hashed.", True),
        "Drawing status": ("WEAK: a published but unconfirmed solution, with every orbital angle and the epoch "
                           f"model-inferred. {CAUTION} Drawn hollow (owner's decision, {DATE}).", True),
    }


def new_row_values(h, n):
    """Every value of a new row, by header; headers left out are blank."""
    pos = ("MSC (Tokovinin 2018, ApJS 235, 6; VizieR J/ApJS/235/6, Dec 2023 update), catalog record for component B "
           "(RAJ2000/DEJ2000)")
    base = {"System / Host": SYS, "Star (component)": n, "Distance (ly)": 86.08, "Stars in system": 5,
            "Primary mass (M-sun)": M_BA, "Hierarchy": NEW_TREE, "WDS code": "02129+4040",
            "RA (deg, ICRS)": 33.229117, "Dec (deg, ICRS)": 40.668389}
    if n == BAB:
        return base | {
            "Role in system": f"subsystem: {BA} + {BB}", "Mass (M-sun)": M_BAB,
            "Star data source": f"Sum of the subsystem's masses: {BA} (MSC) + {BB} (m sin i, {G21})",
            "Node type": "subsystem", "MSC label": "Bab", "Member of": B, "Hierarchy level": 2,
            "Mass basis (MSC)": "sum of the subsystem's masses (Ba MSC + Bb m sin i)", "Position source": pos,
            "Barycentre from": BA, "Barycentre offset (AU)": OFF_BAB}
    c = COMP[BC]
    return base | {
        "Role in system": "brown dwarf", "Mass (M-sun)": c["m"],
        "Star data source": (f"{G21}: mass (m sin i) and orbit of HD 13507 c, the outer of two brown dwarfs proposed "
                             "in place of the refuted single companion"),
        "HZ distance": "no luminosity on file",
        "Orbital eccentricity (e)": c["e"], "Orbit described": f"{BAB} + {BC}", "Orbit source": G21_SHORT,
        "Separation from": BAB, "Separation (AU)": c["a"], "Separation type": "semi-major axis",
        "Separation source": f"{G21}: semi-major axis {c['a']} au as printed",
        "Node type": "star", "MSC label": "Bc", "Member of": B, "Hierarchy level": 2,
        "Orbital period (d)": c["p_d"], "Period basis": "orbit", "Inclination (deg)": I_DEG,
        "Ascending node (deg)": NODE, "Argument of periastron (deg)": c["omega"], "Separation (arcsec)": c["arcsec"],
        "Detection (MSC)": "not in the MSC; RV, two-Keplerian fit (Grandjean et al. 2021)",
        "Mass basis (MSC)": "minimum mass (m sin i), RV (Grandjean et al. 2021)", "Time of periastron (JD)": c["t"],
        "Position source": pos + "; no record for Bc itself, so the record whose label prefixes it",
        "Argument of periastron refers to": "primary (Bab)", "Drawing status": HYPO}


def main():
    v = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A1:BT2000", valueRenderOption="UNFORMATTED_VALUE"
                         ).execute()["values"]
    h = v[0]
    col = {k: i for i, k in enumerate(h)}
    row = {}
    for name in (BA, B, BB, A, AA, AB):
        hits = [r for r, x in enumerate(v[1:], start=2) if len(x) > 1 and x[col["Star (component)"]] == name]
        assert len(hits) == 1, (name, hits)
        row[name] = hits[0]
    assert [row[n] for n in (BA, B, BB, A, AA, AB)] == list(range(row[BA], row[BA] + 6)), row
    assert not any(len(x) > 1 and x[col["Star (component)"]] in (BAB, BC) for x in v), "already applied"
    a1 = lambda hd, r: f"{q(FP)}!{letter(col[hd])}{r}"  # noqa: E731
    got = lambda n, hd: (v[row[n] - 1] + [""] * len(h))[col[hd]]  # noqa: E731

    # Existing rows: (name, header) -> (expected current value, new value, note or None, border or None).
    ch = {}
    for n in (BA, B, BB, A, AA, AB):
        ch[(n, "Stars in system")] = (4, 5, None, None)
        ch[(n, "Hierarchy")] = (OLD_TREE, NEW_TREE, None, None)
    ch[(BA, "Member of")] = (B, BAB, None, None)
    ch[(BA, "Hierarchy level")] = (2, 3, None, None)

    ch[(B, "Role in system")] = (f"subsystem: {BA} + {BB}", f"subsystem: {BAB} + {BC}", None, None)
    ch[(B, "Mass (M-sun)")] = (1.04, M_B,
                               f"WEAK: two minimum masses.\nINFERRED: sum of the subsystem's masses, {M_BA} (Ba, MSC) "
                               f"+ {COMP[BB]['m']} (Bb) + {COMP[BC]['m']} (Bc), the brown dwarfs' m sin i from {G21}. "
                               "Was 1.04, the MSC's sum with the refuted single companion (0.07).", ORANGE)
    ch[(B, "Star data source")] = (got(B, "Star data source"),
                                   f"Sum of the subsystem's masses: {BA} (MSC) + {BB} and {BC} (m sin i, {G21})",
                                   None, None)
    ch[(B, "Mass basis (MSC)")] = ("sum of the subsystem's masses (MSC)", "sum of the subsystem's masses (Bab + Bc)",
                                   None, None)
    ch[(B, "Barycentre from")] = (BA, BAB, None, None)
    ch[(B, "Barycentre offset (AU)")] = (
        0.477851, OFF_B,
        f"WEAK: the masses are minimum masses.\nINFERRED: a x M_sec / (M_prim + M_sec) = {COMP[BC]['a']} au x "
        f"{COMP[BC]['m']} / ({M_BAB} + {COMP[BC]['m']}), from '{BC}' (Separation (AU), Mass) and '{BAB}' (Mass). The "
        f"barycentre of {B} lies this far from the barycentre of Ba + Bb, on the line to {BC} (hd13507.py, {DATE}).",
        ORANGE)

    cb = COMP[BB]
    notes_b = comp_notes(BB)
    for hd, old, new in (("Mass (M-sun)", 0.07, cb["m"]), ("Orbital eccentricity (e)", 0.338, cb["e"]),
                         ("Separation (AU)", 7.0995, cb["a"]), ("Orbital period (d)", 6870, cb["p_d"]),
                         ("Separation (arcsec)", 0.269, cb["arcsec"]), ("Argument of periastron (deg)", 169, cb["omega"]),
                         ("Time of periastron (JD)", 2452330.14, cb["t"]),
                         ("Argument of periastron refers to", "primary (Ba)", "primary (Ba)"),
                         ("Drawing status", got(BB, "Drawing status"), HYPO)):
        note, orange = notes_b[hd]
        ch[(BB, hd)] = (old, new, note, ORANGE if orange else GREY_RULE)
    ch[(BB, "Star data source")] = (got(BB, "Star data source"),
                                    f"{G21}: mass (m sin i) and orbit of HD 13507 b, the inner of two brown dwarfs "
                                    "proposed in place of the refuted single companion (the MSC's Ba,Bb orbit, "
                                    "Tokovinin from Fischer 2014 data)", None, None)
    ch[(BB, "Orbit source")] = ("Tok from Fischer2014 data", G21_SHORT, None, None)
    ch[(BB, "Separation source")] = (got(BB, "Separation source"), f"{G21}: semi-major axis {cb['a']} au as printed",
                                     None, None)
    ch[(BB, "Member of")] = (B, BAB, None, None)
    ch[(BB, "Hierarchy level")] = (2, 3, None, None)
    ch[(BB, "Mass basis (MSC)")] = ("minimum mass, SB1 (MSC)", "minimum mass (m sin i), RV (Grandjean et al. 2021)",
                                    None, None)

    wide = "WEAK: nothing measures this orbit; only a projected separation and a position angle.\nINFERRED (model): "
    ch[(A, "Orbital period (d)")] = (
        511674366.136, P_A,
        wide + f"P = (a^3 / M_tot)^(1/2) = ({A_SEP}^3 / {M_TOT_A:.4f})^(1/2) yr, with a the projected separation; "
        f"replaces the MSC estimate (511167375.0 d). M_tot from 2.18 to {M_TOT_A} on {DATE} (B's mass, hd13507.py).",
        ORANGE)
    ch[(A, "Time of periastron (JD)")] = (
        286436662.2052, T_A,
        wide + f"T puts the companion at its observed position angle, {A_PA:.0f} deg (MSC pair record B,A), at J2016.0: "
        "face-on with node = omega = 0, the phase is the position angle. Recomputed with P on " + DATE + ".", ORANGE)

    for (n, hd), (old, *_) in ch.items():
        assert got(n, hd) == old, (n, hd, got(n, hd), old)

    # Rejected candidates: the single solution's row, by name.
    rv = API.values().get(spreadsheetId=SID, range=f"{q(RJ)}!A1:AZ400", valueRenderOption="UNFORMATTED_VALUE"
                          ).execute()["values"]
    rcol = {k: i for i, k in enumerate(rv[0])}
    rj_hits = [r for r, x in enumerate(rv[1:], start=2) if x and x[0] == "HD 13507 B (single-companion solution)"]
    assert len(rj_hits) == 1, rj_hits
    rr = rj_hits[0]
    rgot = lambda hd: (rv[rr - 1] + [""] * len(rv[0]))[rcol[hd]]  # noqa: E731
    mass_type_hd = next(hd for hd in rcol if "Mass type" in hd or hd == "Mass type")
    src_hd = "Source / discovery reference"
    why_hd = "Rejected because"
    rj = {
        mass_type_hd: (rgot(mass_type_hd), "Msini (Perrier et al. 2003; 67 in Wilson et al. 2016, as cited by "
                                           "Grandjean et al. 2021)"),
        src_hd: (rgot(src_hd), "Perrier et al. 2003; Wilson et al. 2016, as cited by Grandjean et al. 2021"),
        why_hd: (rgot(why_hd),
                 "Refuted as a single companion: Grandjean et al. 2021, A&A 650, A39 (arXiv:2106.10754): 'We refute "
                 "the HD13507 single brown dwarf companion solution and propose a double BD companion solution' -- "
                 "0.02 and 0.03 M_sun (21 and 31 MJup, m sin i) at 4.2 au (8.3 yr) and 5.4 au (12.1 yr), e = 0.27 and "
                 "0.2, 'taken with caution'. Named so as not to block that newer HD 13507 b. Drawn on Planetless 4+ "
                 f"Stars as BD+39 496 Bb and Bc ({DATE})."),
    }
    assert "3029.5" in rj[why_hd][0] and "2006" in rj[src_hd][0], rj

    # New rows, as they will sit after the two inserts: Bab above Bb, Bc below it.
    r_bab, r_bb, r_bc = row[BB], row[BB] + 1, row[BB] + 2
    new_rows = {BAB: new_row_values(h, BAB), BC: new_row_values(h, BC)}
    for vals in new_rows.values():
        assert set(vals) <= set(col), set(vals) - set(col)
    nb = comp_notes(BC)
    new_notes = {
        BAB: {"Mass (M-sun)": (f"WEAK: Bb's is a minimum mass.\nINFERRED: {M_BA} (Ba, MSC) + {COMP[BB]['m']} (Bb, m sin "
                               f"i, {G21}).", True),
              "Barycentre offset (AU)": (
                  f"WEAK: a minimum mass.\nINFERRED: a x M_sec / (M_prim + M_sec) = {COMP[BB]['a']} au x "
                  f"{COMP[BB]['m']} / ({M_BA} + {COMP[BB]['m']}), from '{BB}' (Separation (AU), Mass) and '{BA}' "
                  f"(Mass). The barycentre of {BAB} lies this far from {BA}, on the line to {BB} (hd13507.py, {DATE}).",
                  True)},
        BC: {**{hd: x for hd, x in nb.items()},
             "Inclination (deg)": ("WEAK: the paper gives no inclination.\nINFERRED (model): i = 60, the median of "
                                   f"randomly oriented orbits, as for {BB}: drawn coplanar with it.", True),
             "Ascending node (deg)": ("WEAK: the paper gives no node.\nINFERRED (model): coplanar with "
                                      f"{BB} (its node, the name hash of '{BB} node'): the two come from one RV fit "
                                      "and sit near 3:2 resonance.", True),
             "Luminosity (L-sun)": ("BLANK: below the dwarf sequence's mass range (brown dwarf) and no class.", False),
             "Separation from": (f"{G21} fit two Keplerians about the star. In this tab's tree of pairs c orbits the "
                                 f"barycentre of Ba + Bb (Jacobi coordinates), {OFF_BAB} au from Ba.", False)},
    }

    sp = sp_entry(r_bab, r_bc)
    if PLAN:
        print(f"rows: {row}; new: {BAB} -> {r_bab}, {BB} -> {r_bb}, {BC} -> {r_bc}")
        print(f"M_Bab {M_BAB}  M_B {M_B}  off_Bab {OFF_BAB}  off_B {OFF_B}  node {NODE}  P_A {P_A}  T_A {T_A}")
        for n, c in COMP.items():
            print(f"  {n}: P {c['p_d']} d, omega {c['omega']}, T {c['t']}, arcsec {c['arcsec']}, "
                  f"a^3/P^2 {c['kepler_m']:.4f}")
        for (n, hd), (old, new, note, border) in ch.items():
            print(f"  {n:15} {hd:34} {str(old)[:50]:>50} -> {str(new)[:70]}"
                  f"{'   [' + ('orange' if border == ORANGE else 'grey') + ']' if border else ''}")
            if note:
                print(f"      note: {note}")
        for n, vals in new_rows.items():
            print(f"  NEW {n}:")
            for hd, x in vals.items():
                note, orange = new_notes[n].get(hd, (None, False))
                print(f"      {hd:34} {x}{'   [orange]' if orange else ''}" + (f"\n         note: {note}" if note else ""))
        for hd, (old, new) in rj.items():
            print(f"  {RJ} row {rr} {hd}:\n      {old}\n   -> {new}")
        print("\n".join(sp))
        return

    # 1. Existing rows, every old value checked first.
    gs.update_cells(SID, {a1(hd, row[n]): [[new]] for (n, hd), (_, new, *_) in ch.items()},
                    expect={a1(hd, row[n]): old for (n, hd), (old, *_) in ch.items()})

    # 2. Two rows: Bc after Bb (a copy of Bb, formulas and formats), then Bab before Bb (a copy of B).
    pid = next(s["properties"]["sheetId"] for s in API.get(spreadsheetId=SID, fields="sheets.properties"
                                                           ).execute()["sheets"] if s["properties"]["title"] == FP)
    ncol = len(h)

    def insert_copy(at, src):
        """Insert a row so it becomes row `at` (1-based) and paste row `src` (1-based, before the insert) into it."""
        src_after = src + (1 if src >= at else 0)
        return [{"insertDimension": {"range": {"sheetId": pid, "dimension": "ROWS", "startIndex": at - 1,
                                               "endIndex": at}, "inheritFromBefore": True}},
                {"copyPaste": {"source": {"sheetId": pid, "startRowIndex": src_after - 1, "endRowIndex": src_after,
                                          "startColumnIndex": 0, "endColumnIndex": ncol},
                               "destination": {"sheetId": pid, "startRowIndex": at - 1, "endRowIndex": at,
                                               "startColumnIndex": 0, "endColumnIndex": ncol},
                               "pasteType": "PASTE_NORMAL"}}]
    API.batchUpdate(spreadsheetId=SID, body={"requests": insert_copy(row[BB] + 1, row[BB])
                                             + insert_copy(row[BB], row[B])}).execute()
    gs.invalidate_cache(SID)

    # 3. The pasted rows carry their source's values, notes and orange boxes: clear the notes, re-rule the borders,
    #    then write every non-formula cell (blank where the new row has no value).
    for r in (r_bab, r_bc):
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"updateCells": {
            "range": {"sheetId": pid, "startRowIndex": r - 1, "endRowIndex": r, "startColumnIndex": 0,
                      "endColumnIndex": ncol}, "fields": "note"}}]}).execute()
    # Cell by cell: a range's updateBorders sets only its outer edges, so a pasted orange box inside would survive.
    gs.set_border(SID, [f"{q(FP)}!{letter(i)}{r}" for r in (r_bab, r_bc) for i in range(ncol)], GREY_RULE,
                  style="SOLID")
    upd, exp = {}, {}
    for n, r, src in ((BAB, r_bab, B), (BC, r_bc, BB)):
        f = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A{r}:{letter(ncol - 1)}{r}",
                             valueRenderOption="FORMULA").execute()["values"][0]
        for hd, i in col.items():
            if str(f[i] if i < len(f) else "").startswith("="):
                continue                                # keep the copied formula (class, HZ, bands)
            upd[a1(hd, r)] = [[new_rows[n].get(hd, "")]]
        exp[a1("Star (component)", r)] = src
    exp[a1("Star (component)", r_bb)] = BB
    gs.update_cells(SID, upd, expect=exp)

    # 4. Borders and notes: orange where inferred, the tab's grey where a value is now looked up.
    orange, grey, notes = [], [], {}
    shifted = {BA: row[BA], B: row[B], BB: r_bb, A: row[A] + 2, AA: row[AA] + 2, AB: row[AB] + 2}
    for (n, hd), (_, _, note, border) in ch.items():
        cell = a1(hd, shifted[n])
        if border == ORANGE:
            orange.append(cell)
        elif border == GREY_RULE:
            grey.append(cell)
        if note:
            notes[cell] = note
    for n, r in ((BAB, r_bab), (BC, r_bc)):
        for hd, (note, is_orange) in new_notes[n].items():
            notes[a1(hd, r)] = note
            if is_orange:
                orange.append(a1(hd, r))
    gs.set_border(SID, grey, GREY_RULE, style="SOLID")
    gs.set_border(SID, orange, ORANGE)
    gs.set_note(SID, notes)

    # 5. Rejected candidates.
    rja = lambda hd: f"{q(RJ)}!{letter(rcol[hd])}{rr}"  # noqa: E731
    gs.update_cells(SID, {rja(hd): [[new]] for hd, (_, new) in rj.items()},
                    expect={rja(hd): old for hd, (old, _) in rj.items()})

    # 6. Sources & Provenance: grow the grid, then explicit ranges (never values().append()).
    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    spm = next(s["properties"] for s in meta if s["properties"]["title"] == SP)
    last = spm["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{last}"])[f"{q(SP)}!A{last}"][0][0].strip()
    start, end = last + 1, last + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": spm["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    print("done:", {"rows": {BAB: r_bab, BB: r_bb, BC: r_bc}, "rejected_row": rr, "sp_rows": [start, end],
                    "orange": len(orange), "grey": len(grey), "notes": len(notes), "title": title})


def sp_entry(r_bab, r_bc):
    cb, cc = COMP[BB], COMP[BC]
    return [
        "",
        f"{DATE.upper()}: 'Planetless 4+ Stars' -- BD+39 496 B (HD 13507) TAKES GRANDJEAN ET AL. 2021'S TWO BROWN "
        "DWARFS IN PLACE OF THE REFUTED SINGLE COMPANION (hd13507.py).",
        f"Source: {G21}. A two-Keplerian RV fit (Dpass) to ELODIE (Perrier et al. 2003) and SOPHIE RVs refutes the "
        "single brown dwarf and proposes two: 0.02 and 0.03 M_sun (21 and 31 MJup, minimum masses, RV only) at 4.2 au "
        f"(8.3 yr) and 5.4 au (12.1 yr), e = 0.27 and 0.2, near 3:2 resonance. {CAUTION} Confidence LOW. The "
        "single-companion fits disagree with each other -- Perrier et al. 2003 ~3000 d, 52 MJ; Wilson et al. 2016 "
        "4890 d, 67 MJ; the MSC's (Tokovinin from Fischer et al. 2014's Lick RVs, which Grandjean did not use) "
        "6870 d, e 0.338, m sin i 0.07 M_sun, which the tab drew until now. Gaia DR3 has no non-single-star solution "
        "(non_single_star = 0, RUWE 3.02). Owner's decision, " + DATE + ": draw the two, hollow. Verify: arXiv:"
        "2106.10754, Sect. 3.1.2 and Fig. 4.",
        f"  STRUCTURE: the tab is a tree of pairs, so B ({M_B} M_sun) is now Bab + Bc, as Castor's C is Cab + Cc. "
        f"New row {r_bab}, BD+39 496 Bab (subsystem Ba + Bb, {M_BAB} M_sun, barycentre {OFF_BAB} au from Ba); "
        f"BD+39 496 Bb is HD 13507 b, round Ba; new row {r_bc}, BD+39 496 Bc, is HD 13507 c, round Bab's barycentre "
        "(Jacobi coordinates; the paper's two Keplerians are both about the star). Hierarchy "
        f"'{NEW_TREE}'; Stars in system 4 -> 5 on every row.",
        f"  LOOKED UP (grey rule): a = {cb['a']} / {cc['a']} au, e = {cb['e']} / {cc['e']}, mass (m sin i) = "
        f"{cb['m']} / {cc['m']} M_sun, as printed. The paper's own figures disagree slightly: a^3/P^2 = "
        f"{cb['kepler_m']:.3f} M_sun for both, against the tab's 0.99 (Ba + b) and 1.02 (Bab + c) -- 2.8% and 1.8% in a, "
        "within the rounding of the periods. Taken as printed, not rescaled.",
        f"  INFERRED (orange, every one noted on its cell): P = 8.3 / 12.1 yr x 365.25 = {cb['p_d']} / {cc['p_d']} d "
        f"(the paper rounds to 0.1 yr); separation in arcsec = a x {PLX_MAS} mas; omega and T from the name hash "
        "(catalog_loader._phase_deg), the paper giving neither; i = 60 (median of random orientations) and Bb's "
        f"hashed node ({NODE}), with Bc drawn coplanar with Bb -- WEAK, an assumption nothing measures; masses of "
        f"Bab ({M_BAB}) and B ({M_B}, was 1.04) as sums; barycentre offsets a x M_sec / (M_prim + M_sec): Bab "
        f"{OFF_BAB} au, B {OFF_B} au (was 0.477851); and BD+39 496 A's model orbit round B recomputed by infer.py's "
        f"rule with M_tot = {M_TOT_A} (was 2.18): P = {P_A} d, T = {T_A}. Both brown dwarfs: 'Drawing status' = "
        f"'{HYPO}'.",
        "  REJECTED CANDIDATES, 'HD 13507 B (single-companion solution)': corrected. Its 'b 20 MJ min, P 3029.5 d; "
        "c 30 MJ min, P 4416.5 d' (planet_hosts.py, 2 Oct 2026) is not in the paper, which prints 21 / 31 MJup and "
        "8.3 / 12.1 yr; and 'Wilson et al. 2006' is Grandjean's 'Wilson et al. (2016)' (A&A 588, A144, its Table 7: "
        "67 +8 / -9 MJup, 4890 +209 / -185 d, e = 0.20).",
    ]


if __name__ == "__main__":
    main()
