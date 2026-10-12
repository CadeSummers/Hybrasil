# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Brown dwarfs off the star tabs: each becomes a planet (or a planet's moon) under the 7 Oct 2026 rule.

    python migrate_bds.py          plan: print every write; touches nothing
    python migrate_bds.py write    write it all, log every deleted row, provenance, rename

The owner's rule (docs/hybrasil-instructions.md section 6): a star fuses protium or once did; a brown dwarf is a
planet. Seventeen brown dwarfs were rows on Multi-stars or Planetless 4+ Stars. The owner's decisions (7 Oct 2026):

- Multi-stars, planet-hosting systems: eps Ind Ba and HD 3651 B to Planets, eps Ind Bb to Exomoons as Ba's moon,
  psi1 Dra D to Unconfirmed under the name the tab gave it until 6 Oct, psi1 Dra B c (Endl et al. 2016). eps Ind A
  and HD 3651 are left with one star each, so their Multi-stars blocks go.
- Planetless 4+ Stars: the brown dwarfs go to the planet tabs, filed under the system's 'System / Host', and the stars
  stay with their measured orbits (moving them to Multi-stars would have lost about 25 pairs' 3-D orbits, which that
  tab has no columns for). A subsystem left with one member collapses into it: the member takes the subsystem's
  orbit cells (values, orange boxes and notes, by copyPaste) and its place in the tree. pi1 Cnc Eb becomes Ea's moon.
- Kept as stars: the nine objects at the hydrogen-burning limit and ksi UMa Bb ('WD?'), now a TODO watch list; and
  five hollow companions whose low mass is only the typical-companion rule's assumption (infer.py), not a measurement.

Every value is the star row's own, carried across; what the planet tabs need that the star row lacks -- a period for
a wide pair, a host luminosity for a planet round a pair -- is computed here and boxed orange with its method. The
orbital elements the planet tabs have no columns for (i, node, omega, T) are written into the flags text. Every row
deleted is kept, values, formulas and notes, in migrate_bds_log.json.
"""
import json
import math
import re
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
SY, MS, PL = "Systems within 100 ly", "Multi-stars within 100 ly", "Planetless 4+ Stars"
PN, UN, EX, SP = "Planets within 100 ly", "Unconfirmed within 100 ly", "Exomoons", "Sources & Provenance"
LOG = HERE / "migrate_bds_log.json"
DATE, ISO = "7 Oct 2026", "2026-10-07"
ORANGE, PINK = "FF9900", "FF3399"
M_EARTH_PER_M_SUN = 332946.0487
MJ_PER_M_SUN = 1047.57
RULE = "docs/hybrasil-instructions.md section 6"

# ---------------------------------------------------------------------------------------------------- decisions
# (tab, system, component, target tab, planet name, host node, tier). A moon's 'host node' is its planet.
MOVES = [
    (MS, "eps Ind A", "eps Ind Ba", PN, "eps Ind Ba", "eps Ind A", "confirmed"),
    (MS, "eps Ind A", "eps Ind Bb", EX, "eps Ind Bb", "eps Ind Ba", "confirmed"),
    (MS, "HD 3651", "HD 3651 B", PN, "HD 3651 B", "HD 3651", "confirmed"),
    (MS, "psi1 Dra A", "psi1 Dra D", UN, "psi1 Dra B c", "psi1 Dra B", "ambiguous"),
    (PL, "GJ 570", "GJ 570 G", PN, "GJ 570 G", "GJ 570 AB", "confirmed"),
    (PL, "ksi UMa", "ksi UMa D", PN, "ksi UMa D", "ksi UMa AB", "confirmed"),
    (PL, "GJ 867", "GJ 867 Bb", PN, "GJ 867 Bb", "GJ 867 Ba", "confirmed"),
    (PL, "GJ 569", "GJ 569 Bb", PN, "GJ 569 Bb", "GJ 569 Ba", "confirmed"),
    (PL, "alf Gem", "alf Gem Cc", PN, "alf Gem Cc", "alf Gem Cab", "confirmed"),
    (PL, "tau Cyg", "tau Cyg Ab", UN, "tau Cyg Ab", "tau Cyg Aa", "strong"),
    (PL, "pi1 Cnc", "pi1 Cnc Ea", PN, "pi1 Cnc Ea", "pi1 Cnc A", "confirmed"),
    (PL, "pi1 Cnc", "pi1 Cnc Eb", EX, "pi1 Cnc Eb", "pi1 Cnc Ea", "confirmed"),
    (PL, "GJ 9829", "GJ 9829 C", PN, "GJ 9829 C", "GJ 9829 B", "confirmed"),
    (PL, "BD+37 1091", "BD+37 1091 Ab", PN, "BD+37 1091 Ab", "BD+37 1091 Aa", "confirmed"),
    (PL, "BD+39 496", "BD+39 496 Bb", UN, "BD+39 496 Bb", "BD+39 496 Ba", "ambiguous"),
    (PL, "BD+39 496", "BD+39 496 Bc", UN, "BD+39 496 Bc", "BD+39 496 Ba", "ambiguous"),
    (PL, "GJ 3347", "GJ 3347 Aa2", UN, "GJ 3347 Aa2", "GJ 3347 Aa1", "ambiguous"),
]
# A planet whose orbit is its subsystem's: pi1 Cnc Ea is E's primary, so E's row holds the orbit round A.
ORBIT_ROW = {"pi1 Cnc Ea": "pi1 Cnc E"}
# What a candidate is called elsewhere, from its star row's own source text.
DESIG = {"BD+39 496 Bb": "HD 13507 b (Grandjean et al. 2021, A&A 650, A39)",
         "BD+39 496 Bc": "HD 13507 c (Grandjean et al. 2021, A&A 650, A39)",
         "GJ 3347 Aa2": "Gaia DR3 3340966243931480448, nss_two_body_orbit SB1 (Arenou et al. 2023)"}
# The new 'Hierarchy' text on every row of a Planetless system.
HIERARCHY = {
    "GJ 570": ("(A,(Ba,Bb)),G", "A,(Ba,Bb)"), "ksi UMa": ("((Aa,Ab),(Ba,Bb)),D", "(Aa,Ab),(Ba,Bb)"),
    "GJ 867": ("(Aa,Ab),(Ba,Bb)", "(Aa,Ab),Ba"), "GJ 569": ("(Aa,Ab),(Ba,Bb)", "(Aa,Ab),Ba"),
    "alf Gem": ("((Aa,Ab),(Ba,Bb)),((Ca,Cb),Cc)", "((Aa,Ab),(Ba,Bb)),(Ca,Cb)"),
    "tau Cyg": ("((Aa,Ab),B),(Fa,Fb)", "(Aa,B),(Fa,Fb)"), "pi1 Cnc": ("(Aa,Ab),(Ea,Eb)", "Aa,Ab"),
    "GJ 9829": ("(A,D),(B,C)", "(A,D),B"), "BD+37 1091": ("(Aa,Ab),(Ba,Bb)", "Aa,(Ba,Bb)"),
    "BD+39 496": ("((Ba,Bb),Bc),(Aa,Ab)", "Ba,(Aa,Ab)"), "GJ 3347": ("(((Aa1,Aa2),Ab),B),(Ea,Eb)", "((Aa1,Ab),B),(Ea,Eb)"),
}
# Systems tab: the new 'System stars' line set, by removing the migrated stars' lines.
SYSTEMS_OF_MS = {"eps Ind A": ["eps Ind Ba", "eps Ind Bb"], "HD 3651": ["HD 3651 B"], "psi1 Dra A": ["psi1 Dra D"]}
# The cells of a Planetless row that describe its own orbit: a collapsed subsystem's go to the member that replaces it.
ORBIT_COLS = ["Orbital eccentricity (e)", "Orbit described", "Orbit source", "Separation from", "Separation (AU)",
              "Separation type", "Separation source", "Member of", "Orbital period (d)", "Period basis",
              "Inclination (deg)", "Ascending node (deg)", "Argument of periastron (deg)", "Separation (arcsec)",
              "Detection (MSC)", "Time of periastron (JD)", "Argument of periastron refers to"]


def values(tab, how="UNFORMATTED_VALUE"):
    return API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:DZ3000", valueRenderOption=how
                            ).execute().get("values", [])


class Tab:
    def __init__(self, title, key):
        self.title, self.key = title, key
        self.v, self.f = values(title), values(title, "FORMULA")
        self.h = self.v[0]
        self.col = {h: i for i, h in enumerate(self.h)}

    def row(self, r):
        vals = self.v[r - 1] if r - 1 < len(self.v) else []
        return {h: (vals[i] if i < len(vals) else "") for i, h in enumerate(self.h)}

    def formula(self, r, h):
        fr = self.f[r - 1] if r - 1 < len(self.f) else []
        i = self.col[h]
        return fr[i] if i < len(fr) else ""

    def find(self, name, key=None):
        k = self.col[key or self.key]
        hits = [i + 1 for i, r in enumerate(self.v) if i and len(r) > k and r[k] == name]
        assert len(hits) == 1, (self.title, name, hits)
        return hits[0]

    def rows_of(self, system):
        return [i + 1 for i, r in enumerate(self.v) if i and r and r[0] == system]

    def a1(self, h, r):
        return f"{q(self.title)}!{letter(self.col[h])}{r}"

    def last_data_row(self):
        n = 1
        for i, r in enumerate(self.v[1:], start=2):
            if sum(1 for c in r if str(c).strip()) <= 1:
                break
            n = i
        return n


def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def marks(tab, rows):
    """{(row, header): (border colour or None, note)} for the rows given."""
    out = {}
    for r in rows:
        b = gs.get_borders(SID, f"{q(tab.title)}!A{r}:{letter(len(tab.h) - 1)}{r}")
        n = gs.get_notes(SID, f"{q(tab.title)}!A{r}:{letter(len(tab.h) - 1)}{r}")
        for a1 in set(b) | set(n):
            c = re.match(r"([A-Z]+)(\d+)", a1)
            h = tab.h[sum((ord(ch) - 64) * 26 ** i for i, ch in enumerate(reversed(c.group(1)))) - 1]
            cols = {x for x, _ in b.get(a1, {}).values()}
            colour = next((x for x in cols if x in (ORANGE, PINK)), None) if len(b.get(a1, {})) == 4 else None
            out[(r, h)] = (colour, n.get(a1, ""))
    return out


# ---------------------------------------------------------------------------------------------------- planet rows
def kepler_p(a_au, m_sun):
    return math.sqrt(a_au ** 3 / m_sun) * 365.25


def subtree_stars(rows, node):
    """Every star row at or under `node` in a Planetless hierarchy."""
    kids = [n for n, r in rows.items() if r.get("Member of") == node]
    if rows[node].get("Node type") == "star":
        return [node]
    return [s for k in kids for s in subtree_stars(rows, k)]


def host_facts(tab, system, node, planned, sys_tab):
    """(luminosity, class, distance, mass, orange note or None) for the node a planet goes round."""
    rows = {tab.row(r)["Star (component)"]: tab.row(r) for r in tab.rows_of(system)}
    if tab.title == MS or node not in rows:
        srow = sys_tab.row(sys_tab.find(system, "System / Host"))
        if node == system or node not in rows:
            lum = num(srow["Host luminosity (L-sun)"])
            return lum, srow["Stellar Class"], srow["Distance (ly)"], num(srow["Host mass (M-sun)"]), None
        r = rows[node]
        return num(r["Luminosity (L-sun)"]), r["Stellar Class"], r["Distance (ly)"], num(r["Mass (M-sun)"]), None
    r = rows[node]
    if r.get("Node type") == "star":
        return num(r["Luminosity (L-sun)"]), r["Stellar Class"], r["Distance (ly)"], num(r["Mass (M-sun)"]), None
    stars = [s for s in subtree_stars(rows, node) if s not in planned]
    lums = [(s, num(rows[s]["Luminosity (L-sun)"])) for s in stars]
    known = [(s, x) for s, x in lums if x is not None]
    total = sum(x for _, x in known)
    note = (f"INFERRED: the light of the pair (or group) this planet orbits, {node}: the sum of its stars' "
            f"luminosities on Planetless 4+ Stars, " + " + ".join(f"{s} {x:.4g}" for s, x in known)
            + f" = {total:.4g} L-sun." + (f" No luminosity on file for {', '.join(s for s, x in lums if x is None)}"
                                         f", left out." if len(known) < len(lums) else ""))
    cls = "+".join(rows[s]["Stellar Class"] or "?" for s in stars)
    return total or None, cls, r.get("Distance (ly)") or rows[stars[0]]["Distance (ly)"], num(r["Mass (M-sun)"]), note


def planet_spec(move, src, sys_tab, planned, src_marks):
    """{header: value} for the new planet-tab row, plus {header: note} for orange cells and carried notes."""
    tab_title, system, comp, target, name, node, tier = move
    r = src.find(comp)
    row = src.row(r)
    orow_n = src.find(ORBIT_ROW[comp]) if comp in ORBIT_ROW else r
    orow = src.row(orow_n)
    mass = num(row["Mass (M-sun)"])
    a = num(orow.get("Separation (AU)"))
    e = num(orow.get("Orbital eccentricity (e)"))
    p = num(orow.get("Orbital period (d)")) if "Orbital period (d)" in src.col else None
    orange, notes = {}, {}

    def carry(src_h, dst_h, rr=r, how=""):
        colour, note = src_marks.get((rr, src_h), (None, ""))
        # A note that says the value was inferred counts as the box: psi1 Dra D's two inferred cells had lost
        # theirs on Multi-stars (found 7 Oct 2026), and the note is what travels with a value.
        if colour == ORANGE or re.match(r"\s*(WEAK|INFERRED)", note or ""):
            orange[dst_h] = (f"{how}Carried from the {src.title} row of {comp if rr == r else src.row(rr)['Star (component)']}"
                             f" ({src_h}), where it is inferred: " + (note or "see that cell's provenance."))
        elif note:
            notes[dst_h] = f"{how}From the {src.title} row ({src_h}): {note}"

    carry("Mass (M-sun)", "Mass (M-earth)", how=f"Converted from {mass} M-sun x {M_EARTH_PER_M_SUN:.0f}. ")
    carry("Separation (AU)", "Semi-major axis (au)", rr=orow_n)
    carry("Orbital eccentricity (e)", "Eccentricity", rr=orow_n)
    lum, cls, dist, host_mass, lum_note = host_facts(src, system, node, planned, sys_tab)
    if lum_note:
        orange["Host luminosity (L-sun)"] = lum_note
    if p is not None:
        carry("Orbital period (d)", "Orbital period (d)", rr=orow_n)
    elif a and host_mass:
        p = round(kepler_p(a, host_mass + (mass or 0)), 1)
        orange["Orbital period (d)"] = (
            ("WEAK: " if "assumed" in str(orow.get("Separation type")) else "")
            + f"INFERRED: Kepler's third law on a = {a} AU ({orow.get('Separation type')}) and M = {host_mass} "
            f"(host) + {mass} (this body) M-sun, circular. = {p} d ({p / 365.25:.0f} yr). The {src.title} row "
            "had no period column to carry.")
    sep_type = str(orow.get("Separation type") or "")
    elements = [f"{k} {orow[k]}" for k in ("Inclination (deg)", "Ascending node (deg)", "Argument of periastron (deg)",
                                          "Time of periastron (JD)", "Argument of periastron refers to")
                if orow.get(k) not in ("", None)]
    flags = (f"MOVED FROM {src.title.upper()} {DATE}: a brown dwarf is a planet under the model's rule ({RULE}). "
             f"Was the star row '{comp}' (role '{row['Role in system']}', class {row['Stellar Class'] or 'none'}, "
             f"Teff {row['Effective temp (K)'] or 'none'}, L {row['Luminosity (L-sun)'] or 'none'}). "
             f"Orbit: {sep_type or 'no'} separation {a} AU from {orow.get('Separation from') or node}"
             + (f", e {e}" if e is not None else "") + (f", P {p} d" if p else "")
             + (f" ({orow['Period basis']})" if orow.get("Period basis") else "")
             + (f"; elements the planet tabs have no columns for: {'; '.join(elements)}" if elements else "")
             + (f". Orbit source: {orow.get('Orbit source') or orow.get('Separation source')}"
                if orow.get("Orbit source") or orow.get("Separation source") else "")
             + (f". Detection: {orow.get('Detection (MSC)') or row.get('Detection (MSC)')}"
                if orow.get("Detection (MSC)") or row.get("Detection (MSC)") else "")
             + (". Drawn hollow on the star tab (hypothetical and model-inferred)."
                if "hypothetical" in str(row.get("Drawing status", "")).lower() else "."))
    basis = str(row.get("Mass basis (MSC)") or "")
    mass_type = ("Msini (minimum mass, SB1)" if "minimum" in basis
                 else "INFERRED (see the Mass note)" if basis.startswith("INFERRED")
                 else "Mass (dynamical)" if "dynamical" in str(row.get("Star data source", "")).lower()
                 else "Mass" if mass else "")
    spec = {
        "Planet": name, "Host system (primary star)": system, "Planet-host star": node, "Planet-host class": cls,
        "Host luminosity (L-sun)": lum if lum is not None else "",
        "Mass (M-earth)": round(mass * M_EARTH_PER_M_SUN, 1) if mass else "", "Mass type": mass_type,
        "Orbital period (d)": p if p else "", "Semi-major axis (au)": a if a else "",
        "Eccentricity": e if e is not None else "", "Orbit data source / flags": flags, "Confidence tier": tier,
        "Source / discovery reference": row.get("Star data source", ""), "Vetting date / last updated": ISO,
        "Catalogue distance (ly)": dist, "Detection method": orow.get("Detection (MSC)") or row.get("Detection (MSC)")
        or "",
    }
    return spec, orange, notes, {"mass_sun": mass, "a": a, "p": p, "e": e}


# ---------------------------------------------------------------------------------------------------- Planetless
def collapse_plan(pl, system, removed):
    """Simulate the removals on one system: (final rows {name: row}, copyPastes [(from, to)], deleted names)."""
    names = [pl.row(r)["Star (component)"] for r in pl.rows_of(system)]
    rows = {n: dict(pl.row(pl.find(n))) for n in names}
    gone = list(removed)
    for n in removed:
        rows.pop(n)
    pastes = []
    label = {n: rows[n].get("MSC label") or n.split()[-1] for n in rows}
    changed = True
    while changed:
        changed = False
        for x, xr in list(rows.items()):
            if xr.get("Node type") != "subsystem":
                continue
            members = [n for n, r in rows.items() if r.get("Member of") == x]
            if len(members) >= 2:
                continue
            if len(members) == 0:
                rows.pop(x)
                gone.append(x)
                changed = True
                break
            if len(members) == 1:
                k = members[0]
                pastes.append((x, k))
                for h in ORBIT_COLS:
                    rows[k][h] = xr.get(h, "")
                for n, r in rows.items():
                    if r.get("Separation from") == x:
                        r["Separation from"] = k
                    if r.get("Barycentre from") == x:
                        r["Barycentre from"] = k
                    for h in ("Role in system", "Orbit described"):
                        if x in str(r.get(h, "")):
                            r[h] = re.sub(rf"(?<![\w+-]){re.escape(x)}(?![\w+-])", k, str(r[h]))
                    lx, lk = label.get(x, x), label.get(k, k)
                    if r.get("Argument of periastron refers to"):
                        r["Argument of periastron refers to"] = re.sub(
                            rf"(?<![\w]){re.escape(lx)}(?![\w])", lk, str(r["Argument of periastron refers to"]))
                for d in [k] + _descendants(rows, k):
                    if isinstance(rows[d].get("Hierarchy level"), (int, float)):
                        rows[d]["Hierarchy level"] -= 1
                rows.pop(x)
                gone.append(x)
                changed = True
                break
    return rows, pastes, gone


def check_hierarchies(pl_final, specs):
    """Build every changed system from its simulated rows, planets included, as the viewer will."""
    from hybrasil.data.hierarchy import NodeRow, hierarchy_bodies
    from hybrasil.data.planetless_loader import _COLUMNS, _TEXT
    for system, rows in pl_final.items():
        nodes = []
        for n, r in rows.items():
            kw = {}
            for f, h in _COLUMNS.items():
                v = r.get(h, "")
                kw[f] = (str(v).strip() or None) if f in _TEXT else (float(v) if num(v) is not None else None)
            nodes.append(NodeRow(name=n, **kw))
        origin = next(n for n, r in rows.items() if str(r.get("Role in system")).startswith("host"))
        bodies = {b.name for b in hierarchy_bodies(nodes, origin=origin)}
        for m, spec, *_ in specs:
            if m[1] == system and m[3] != EX:
                assert m[5] in bodies, (system, m[4], "host node", m[5], "missing")
        print(f"  built {system}: {len(bodies)} bodies")


def _descendants(rows, node):
    kids = [n for n, r in rows.items() if r.get("Member of") == node]
    return kids + [d for k in kids for d in _descendants(rows, k)]


# ---------------------------------------------------------------------------------------------------- main
def main():
    sy, ms, pl = Tab(SY, "System / Host"), Tab(MS, "Star (component)"), Tab(PL, "Star (component)")
    pn, un, ex = Tab(PN, "Planet"), Tab(UN, "Planet"), Tab(EX, "Exomoon")
    rej = Tab("Rejected candidates", "Planet")
    taken = {r[0] for t in (pn, un, rej) for r in t.v[1:] if r} | {r[0] for r in ex.v[1:] if r}
    for m in MOVES:
        assert m[4] not in taken, f"{m[4]} is already on a planet tab or rejected"
    planned = {m[2] for m in MOVES}

    src_rows = {MS: {}, PL: {}}
    for m in MOVES:
        t = ms if m[0] == MS else pl
        src_rows[m[0]].setdefault(t.find(m[2]), None)
        if m[2] in ORBIT_ROW:
            src_rows[m[0]].setdefault(t.find(ORBIT_ROW[m[2]]), None)
    src_marks = {MS: marks(ms, sorted(src_rows[MS])), PL: marks(pl, sorted(src_rows[PL]))}

    specs = []
    for m in MOVES:
        src = ms if m[0] == MS else pl
        spec, orange, notes, facts = planet_spec(m, src, sy, planned, src_marks[m[0]])
        specs.append((m, spec, orange, notes, facts))

    # psi1 Dra B c: back under its planet-tab name, with what the 6 Oct row said that D's row does not.
    bc = json.loads((HERE / "merge_psi1_bc_log.json").read_text(encoding="utf-8"))["values"]
    for m, spec, orange, notes, facts in specs:
        if m[4] == "psi1 Dra B c":
            for h in ("Candidate designation (TOI / KOI / other)", "Detection method"):
                spec[h] = bc[h]
            spec["Source / discovery reference"] = bc["Source / discovery reference"] + \
                "; mass and assumed orbit: data/star_counts/write_counts.py (6 Oct 2026), as psi1 Dra D"
            spec["Orbit data source / flags"] += (
                " Until 6 Oct 2026 this body was this row, psi1 Dra B c, at a nominal 16.2 AU with no mass; it was "
                "then merged into the star row psi1 Dra D (merge_psi1_bc.py), whose assumed 15 AU and 0.014 M-sun "
                "(from the RV trend plus B's proper-motion anomaly) it now keeps. 6 Oct text: " + bc["Orbit data source / flags"])
        if m[2] == "eps Ind Bb":                       # published (Chen et al. 2022 Table 4), not Kepler's
            spec["Orbital period (d)"] = round(11.0197 * 365.25, 2)
            orange.pop("Orbital period (d)", None)
            notes["Orbital period (d)"] = "Chen et al. 2022, AJ 163, 288, Table 4: P = 11.0197 +/- 0.0076 yr, x 365.25."
        if m[4] in DESIG:
            spec["Candidate designation (TOI / KOI / other)"] = DESIG[m[4]]

    # Planet tabs: the HZ of a host that already has a planet on Planets is that planet's.
    hz_cols = ["HZ inner, optimistic (au)", "HZ inner, conservative (au)", "HZ outer, conservative (au)",
               "HZ outer, optimistic (au)"]
    for m, spec, *_ in specs:
        if m[3] in (PN, UN):
            sib = [r for r in range(2, pn.last_data_row() + 1) if pn.row(r)["Planet-host star"] == m[5]]
            for h in hz_cols:
                spec[h] = pn.row(sib[0])[h] if sib else ""

    # ---- Planetless: removals and collapses, per system
    pl_final, pl_pastes, pl_gone = {}, [], []
    for system in dict.fromkeys(m[1] for m in MOVES if m[0] == PL):
        removed = [m[2] for m in MOVES if m[0] == PL and m[1] == system]
        rows, pastes, gone = collapse_plan(pl, system, removed)
        old, new = HIERARCHY[system]
        assert all(r.get("Hierarchy") == old for r in rows.values()), (system, "hierarchy text changed")
        n_stars = sum(1 for r in rows.values() if r.get("Node type") == "star")
        n_conf = sum(1 for m in MOVES if m[1] == system and m[3] == PN)
        for r in rows.values():
            r["Hierarchy"] = new
            r["Stars in system"] = n_stars
            r["Confirmed planets"] = n_conf
        pl_final[system], pl_pastes, pl_gone = rows, pl_pastes + pastes, pl_gone + gone

    # ---- Multi-stars and Systems
    ms_gone, ms_upd, sy_upd, sy_exp, notes_append = [], {}, {}, {}, {}
    for system, comps in SYSTEMS_OF_MS.items():
        rows = [ms.row(r)["Star (component)"] for r in ms.rows_of(system)]
        left = [c for c in rows if c not in comps]
        sr = sy.find(system, "System / Host")
        srow = sy.row(sr)
        old_n = srow["Stars in system"]
        assert old_n == len(rows), (system, old_n, rows)
        n_new_conf = sum(1 for m in MOVES if m[1] == system and m[3] == PN)
        if len(left) == 1:
            ms_gone += rows
        else:
            ms_gone += comps
            for c in left:
                r = ms.find(c)
                ms_upd[ms.a1("Stars in system", r)] = (len(left), old_n)
        lines = [ln for ln in str(srow["System stars"]).split("\n") if not any(ln.startswith(c + ":") for c in comps)]
        sy_upd[sy.a1("Stars in system", sr)] = len(left)
        sy_upd[sy.a1("System stars", sr)] = "\n".join(lines)
        sy_exp[sy.a1("Stars in system", sr)] = old_n
        sy_exp[sy.a1("System stars", sr)] = srow["System stars"]
        if n_new_conf:
            conf = num(srow["Confirmed planets"]) or 0
            sy_upd[sy.a1("Confirmed planets", sr)] = conf + n_new_conf
            sy_exp[sy.a1("Confirmed planets", sr)] = srow["Confirmed planets"]
            extra = [f"{s['Planet']}:{s['Mass (M-earth)']:.0f} ({s['Mass (M-earth)'] / 317.828:.1f} MJ, brown dwarf)"
                     for m, s, *_ in specs if m[1] == system and m[3] == PN]
            sy_upd[sy.a1("Planet masses (M-earth)", sr)] = "\n".join([str(srow["Planet masses (M-earth)"])] + extra)
            sy_exp[sy.a1("Planet masses (M-earth)", sr)] = srow["Planet masses (M-earth)"]
        notes_append[sy.a1("Stars in system", sr)] = (
            f"{DATE}: {', '.join(comps)} moved to the planet tabs -- a brown dwarf is a planet under the model's "
            f"rule ({RULE}). Was {old_n}.")

    check_hierarchies(pl_final, specs)
    sp = sp_lines(specs, pl_final, pl_gone, ms_gone)
    print(f"{len(specs)} planet-tab rows:")
    for m, spec, orange, notes, facts in specs:
        print(f"  {m[3][:12]:12} {spec['Planet']:16} round {m[5]:16} a={facts['a']} P={spec['Orbital period (d)']} "
              f"e={facts['e']} M={facts['mass_sun']} L={spec.get('Host luminosity (L-sun)', '')!r:.10} "
              f"orange={sorted(orange)} notes={sorted(notes)}")
    print("\nPlanetless copyPastes (subsystem -> member):", pl_pastes)
    print("Planetless rows deleted:", pl_gone)
    for system, rows in pl_final.items():
        print(f"  {system}: {[(n, r.get('Member of'), r.get('Separation from'), r.get('Hierarchy level')) for n, r in rows.items()]}")
    print("Multi-stars rows deleted:", ms_gone)
    print("Multi-stars updates:", ms_upd)
    print("Systems updates:", json.dumps(sy_upd, ensure_ascii=False)[:1500])
    if PLAN:
        print("\nSources & Provenance:\n" + "\n".join(x[:400] for x in sp))
        return
    write(sy, ms, pl, pn, un, ex, specs, pl_final, pl_pastes, pl_gone, ms_gone, ms_upd, sy_upd, sy_exp,
          notes_append, sp)


def write(sy, ms, pl, pn, un, ex, specs, pl_final, pl_pastes, pl_gone, ms_gone, ms_upd, sy_upd, sy_exp,
          notes_append, sp):
    props = {s["properties"]["title"]: s["properties"] for s in
             API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}
    log = {"deleted": {}, "planet_rows": {}}

    # Keep every row about to be deleted, values, formulas and notes.
    for t, names in ((pl, pl_gone), (ms, ms_gone)):
        for n in names:
            r = t.find(n)
            log["deleted"][f"{t.title} / {n}"] = {
                "row": r, "values": t.row(r), "formulas": {h: t.formula(r, h) for h in t.h
                                                           if str(t.formula(r, h)).startswith("=")},
                "notes": gs.get_notes(SID, f"{q(t.title)}!A{r}:{letter(len(t.h) - 1)}{r}")}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")

    # ---- 1. planet-tab rows
    for tab, items in ((PN, [s for s in specs if s[0][3] == PN]), (UN, [s for s in specs if s[0][3] == UN]),
                       (EX, [s for s in specs if s[0][3] == EX])):
        if items:
            add_rows(tab, items, props, log)
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")

    # ---- 2. Planetless: collapse (copyPaste orbit cells), then the final values
    pl = Tab(PL, "Star (component)")
    sid = props[PL]["sheetId"]
    reqs = []
    for x, k in pl_pastes:
        rx, rk = pl.find(x), pl.find(k)
        for h in ORBIT_COLS:
            c = pl.col[h]
            reqs.append({"copyPaste": {
                "source": {"sheetId": sid, "startRowIndex": rx - 1, "endRowIndex": rx, "startColumnIndex": c,
                           "endColumnIndex": c + 1},
                "destination": {"sheetId": sid, "startRowIndex": rk - 1, "endRowIndex": rk, "startColumnIndex": c,
                                "endColumnIndex": c + 1}, "pasteType": "PASTE_NORMAL"}})
    if reqs:
        API.batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()
    upd, exp = {}, {}
    for system, rows in pl_final.items():
        for n, want in rows.items():
            r = pl.find(n)
            exp[pl.a1("Star (component)", r)] = n
            have = pl.row(r)
            for h in ["Stars in system", "Confirmed planets", "Hierarchy", "Hierarchy level", "Role in system",
                      "Orbit described", "Barycentre from"] + ORBIT_COLS:
                if h in pl.col and not str(pl.formula(r, h)).startswith("=") and want.get(h, "") != have.get(h, "") \
                        or (h in ORBIT_COLS and any(p[1] == n for p in pl_pastes)):
                    upd[pl.a1(h, r)] = want.get(h, "")
    gs.update_cells(SID, upd, expect=exp)
    host_rows = {system: pl.find(next(n for n, r in rows.items() if str(r.get("Role in system")).startswith("host")))
                 for system, rows in pl_final.items()}
    for system, r in host_rows.items():
        moved = [m[2] for m in MOVES if m[1] == system]
        notes_append[pl.a1("Stars in system", r)] = (
            f"{DATE}: {', '.join(moved)} moved to the planet tabs -- a brown dwarf is a planet under the model's rule "
            f"({RULE}); the stars and their orbits stay here. Hierarchy was {HIERARCHY[system][0]}.")

    # ---- 3. Systems and Multi-stars values, then the notes
    gs.update_cells(SID, sy_upd, expect=sy_exp)
    if ms_upd:
        gs.update_cells(SID, {k: v[0] for k, v in ms_upd.items()}, expect={k: v[1] for k, v in ms_upd.items()})
    old = {}
    for a1 in notes_append:
        old.update({a1: gs.get_notes(SID, a1).get(a1.split("!")[1], "")})
    gs.set_note(SID, {a1: (old[a1] + "\n\n" + n) if old[a1] else n for a1, n in notes_append.items()})

    # ---- 4. deletions, bottom-up, each checked by name
    for t_title, names in ((PL, pl_gone), (MS, ms_gone)):
        t = Tab(t_title, "Star (component)")
        for r in sorted((t.find(n) for n in names), reverse=True):
            assert t.row(r)["Star (component)"] in names
            API.batchUpdate(spreadsheetId=SID, body={"requests": [{"deleteDimension": {"range": {
                "sheetId": props[t_title]["sheetId"], "dimension": "ROWS", "startIndex": r - 1,
                "endIndex": r}}}]}).execute()
        gs.invalidate_cache(SID)
        t = Tab(t_title, "Star (component)")
        assert not set(names) & {r[1] for r in t.v[1:] if len(r) > 1}, f"{t_title}: a row survived"

    # ---- 5. provenance, rename
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{end}"])[f"{q(SP)}!A{end}"][0][0].strip()
    sp0, sp1 = end + 1, end + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{sp0}:A{sp1}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (sp0, sp1)})
    log.update(sp_rows=[sp0, sp1], title=gs.rename_workbook(None, gs.versioned_title()))
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("done:", json.dumps({k: v for k, v in log.items() if k != "deleted"}, ensure_ascii=False)[:2000])


def add_rows(title, items, props, log):
    """Append the rows to a planet tab: a template row's formulas and formats, the values typed over them."""
    t = Tab(title, "Exomoon" if title == EX else "Planet")
    sid = props[title]["sheetId"]
    last = t.last_data_row()
    tmpl = last
    while True:                                      # a template row that wears no coloured box
        b = gs.get_borders(SID, f"{q(title)}!A{tmpl}:{letter(len(t.h) - 1)}{tmpl}")
        if not any(c in (ORANGE, PINK) for s in b.values() for c, _ in s.values()):
            break
        tmpl -= 1
    n = len(items)
    if title == PN:                                  # the constants block sits under the data: insert, don't append
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"insertDimension": {"range": {
            "sheetId": sid, "dimension": "ROWS", "startIndex": last, "endIndex": last + n},
            "inheritFromBefore": True}}]}).execute()
    else:
        assert not any(str(c).strip() for r in t.v[last:last + n] for c in r), f"{title}: rows below data in use"
    API.batchUpdate(spreadsheetId=SID, body={"requests": [
        {"copyPaste": {"source": {"sheetId": sid, "startRowIndex": tmpl - 1, "endRowIndex": tmpl,
                                  "startColumnIndex": 0, "endColumnIndex": len(t.h)},
                       "destination": {"sheetId": sid, "startRowIndex": last, "endRowIndex": last + n,
                                       "startColumnIndex": 0, "endColumnIndex": len(t.h)},
                       "pasteType": "PASTE_NORMAL"}},
        {"updateCells": {"range": {"sheetId": sid, "startRowIndex": last, "endRowIndex": last + n,
                                   "startColumnIndex": 0, "endColumnIndex": len(t.h)},
                         "rows": [{"values": [{} for _ in t.h]} for _ in range(n)], "fields": "note"}}]}).execute()
    gs.invalidate_cache(SID)
    t2 = Tab(title, "Exomoon" if title == EX else "Planet")
    upd, notes, orange = {}, {}, []
    for k, (m, spec, orange_h, notes_h, facts) in enumerate(items):
        r = last + 1 + k
        if title == EX:
            spec = moon_spec(m, spec, facts)
        for h in t2.h:
            if str(t2.formula(r, h)).startswith("="):
                if h == "Distance (ly)" and title in (PN, UN):
                    upd[t2.a1(h, r)] = ("=ARRAY_CONSTRAIN(ARRAYFORMULA(IFERROR(INDEX('Systems within 100 ly'!$C$2:"
                                        f"$C$428,MATCH($B{r},'Systems within 100 ly'!$A$2:$A$428,0)),"
                                        f"{letter(t2.col['Catalogue distance (ly)'])}{r})), 1, 1)")
                continue
            upd[t2.a1(h, r)] = spec.get(h, "")
        for h, note in {**notes_h, **orange_h}.items():
            if h in t2.col:
                notes[t2.a1(h, r)] = note
        orange += [t2.a1(h, r) for h in orange_h if h in t2.col]
        log["planet_rows"][spec.get("Planet") or spec.get("Exomoon")] = f"{title} row {r}"
    formulas = {k: v for k, v in upd.items() if str(v).startswith("=")}
    plain = {k: v for k, v in upd.items() if k not in formulas}
    gs.update_cells(SID, plain, expect={t2.a1(t2.h[0], last + 1): t.row(tmpl)[t.h[0]]})
    if formulas:
        gs.update_cells(SID, formulas, value_input="USER_ENTERED")
    if notes:
        gs.set_note(SID, notes)
    if orange:
        gs.set_border(SID, orange, gs.INFERRED_BORDER)
    f = [s for s in API.get(spreadsheetId=SID, fields="sheets(properties(title),basicFilter)").execute()["sheets"]
         if s["properties"]["title"] == title][0].get("basicFilter")
    if f and f["range"].get("endRowIndex", 0) < last + n:
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"setBasicFilter": {
            "filter": dict(f, range=dict(f["range"], endRowIndex=last + n))}}]}).execute()
    gs.invalidate_cache(SID)


def moon_spec(m, spec, facts):
    """A planet spec re-keyed for the Exomoons tab."""
    mass = facts["mass_sun"]
    return {"Exomoon": spec["Planet"], "Host planet": m[5], "Host system (primary star)": spec["Host system (primary star)"],
            "Distance (ly)": spec["Catalogue distance (ly)"],
            "Mass (M-earth)": round(mass * M_EARTH_PER_M_SUN, 1) if mass else "",
            "Mass (M-Jup)": round(mass * MJ_PER_M_SUN, 2) if mass else "", "Mass type": spec["Mass type"],
            "Orbital period (d)": spec["Orbital period (d)"], "Semi-major axis (au)": spec["Semi-major axis (au)"],
            "Eccentricity": spec["Eccentricity"], "Detection method": spec["Detection method"],
            "Confidence tier": spec["Confidence tier"], "Source / discovery reference": spec["Source / discovery reference"],
            "Orbit data source / flags": spec["Orbit data source / flags"].replace(
                "a brown dwarf is a planet", f"a brown dwarf is a planet, and this one orbits the brown dwarf {m[5]}, "
                "so it is that planet's moon"), "Date added": ISO}


def sp_lines(specs, pl_final, pl_gone, ms_gone):
    out = ["", f"BROWN DWARFS OFF THE STAR TABS, {DATE.upper()}",
           f"  Owner's rule, 7 Oct 2026 ({RULE}): an object is a star if it fuses protium (proton-only hydrogen) or "
           "once did; a brown dwarf is a very large planet. Seventeen brown dwarfs were rows on Multi-stars or "
           "Planetless 4+ Stars and are now planet-tab rows (or, where one orbits another brown dwarf, a moon on "
           "Exomoons). Writer: data/star_counts/migrate_bds.py; every deleted row is kept, values, formulas and "
           "notes, in data/star_counts/migrate_bds_log.json.",
           "  Planetless 4+ Stars keeps its stars and their measured orbits; the brown dwarfs are filed under the "
           "system's 'System / Host', round the node 'Planet-host star' names (a star, or a subsystem's barycentre for "
           "a planet round a pair), and the viewer draws them in the hierarchy (planetless_loader.py). A subsystem left "
           "with one member was collapsed into it: the member took the subsystem's orbit cells by copyPaste (values, "
           "orange boxes and notes) and its place in the tree. Barycentre offsets were left as they were: they "
           "describe the physical masses, brown dwarf included. Deleted on Planetless: " + ", ".join(pl_gone) + ".",
           "  Multi-stars: deleted " + ", ".join(ms_gone) + "; eps Ind A and HD 3651 are single stars now and have no "
           "Multi-stars block. psi1 Dra D is back on Unconfirmed under its 6 Oct name, psi1 Dra B c.",
           "  NOT migrated: the nine objects at the hydrogen-burning limit (VHS 1256 A and B, TVLM 513-46546, GJ 569 Ba, "
           "GJ 747.2 Bb, GJ 310.1 Bb, HR 1099 Bb, GJ 9829 D, GJ 275.2 Ab) and ksi UMa Bb (MSC class 'WD?'), on the TODO "
           "watch list; and 2MASS J15472982-2755121 Cb, ADS 9982 Cb, 1 Hya Cb, GJ 3725 Cb and BD+37 1091 Bb, whose "
           "low masses are the typical-companion rule's assumption (infer.py), not a measurement.",
           "  Orange cells on the new rows: a period from Kepler's third law where the star row had none (a wide "
           "pair's projected separation), a host luminosity summed over a pair a planet orbits, and every value "
           "carried from a cell that was already orange there. Each has its method in the cell note."]
    for m, spec, orange, notes, facts in specs:
        out.append(f"  {spec['Planet']} -> {m[3]} (round {m[5]}, tier {m[6]}): was {m[2]} on {m[0]}; a {facts['a']} AU, "
                   f"P {spec['Orbital period (d)']} d, e {facts['e']}, M {facts['mass_sun']} M-sun."
                   + (" Orange: " + "; ".join(f"{h}: {n}" for h, n in orange.items()) if orange else ""))
    return out


if __name__ == "__main__":
    main()
