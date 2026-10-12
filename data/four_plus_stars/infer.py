# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fill every orbit "Planetless 4+ Stars" still lacks with stated assumptions, so every system can be drawn.

    python infer.py plan      print every cell that would change and why; touches nothing
    python infer.py write     write, mark (orange), note, provenance, rename

research.py took everything a catalog or paper gives. What is left has never been measured, and every value here is
INFERRED (orange) and WEAK, with its rule in the cell note. The owner's choices (30 Sep 2026):

  Wide pairs (a projected separation and an MSC period estimate, nothing else): a circular orbit in the plane of the
      sky (i = 0, node = 0, omega = 0), a = the projected separation, P from Kepler's third law with the tab's
      masses, and T chosen so the companion stands at its observed position angle (the MSC's) at J2016.0 -- the
      picture is right today; the depth is unknown and drawn flat. The sky frame is x = North, y = East, so with
      node = omega = 0 the orbital phase is the position angle.
  Measured orbits with no inclination or node (spectroscopic pairs): i = 60 degrees, the median of randomly oriented
      orbits (90 for an eclipsing pair), and the node from the name hash the catalog source uses for phases
      (catalog_loader._phase_deg). A missing e on a short-period pair is 0 (tidally circular); a missing omega is 0
      on a circular orbit, else hashed; a missing T is hashed.
  Suspected companions (a wobble or 'possibly spectroscopic', no separation, often no mass): a literature value
      first -- CD-77 1092 Aa-Ab has a Gaia DR3 orbit; otherwise the typical companion for the detection: mass 0.3 x
      the primary's, capped at 0.5 M_sun; a = 3 AU for an astrometric wobble, 0.3 AU for a spectroscopic hint;
      circular, i = 60, node hashed, T hashed. Drawn hollow: 'Drawing status' reads 'hypothetical and
      model-inferred'.

Masses, barycentre offsets and 'Argument of periastron refers to' follow. Castor (alf Gem) is left alone.
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from hybrasil.data import google_sheets as gs  # noqa: E402
from hybrasil.data.catalog_loader import _phase_deg  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)
from research import thiele_innes  # noqa: E402

SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
FP, SP = "Planetless 4+ Stars", "Sources & Provenance"
CAT = HERE / "cat"
LOG = HERE / "infer_log.json"
PLAN = sys.argv[1:] == ["plan"]
SKIP_SYSTEMS = {"alf Gem"}
YR = 365.25
J2000, J2016 = 2451545.0, 2457389.0
HYPO = "hypothetical and model-inferred"
SHAPE = ("Orbital eccentricity (e)", "Argument of periastron (deg)", "Time of periastron (JD)")


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    msc = json.loads((HERE / "msc.json").read_text(encoding="utf-8"))
    gaia = json.loads((CAT / "gaia_nss_orbits.json").read_text())
    v = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A1:CZ2000", valueRenderOption="UNFORMATTED_VALUE"
                         ).execute()["values"]
    h = v[0]
    col = {k: i for i, k in enumerate(h)}
    rows = {}
    for r, row in enumerate(v[1:], start=2):
        row = row + [""] * (len(h) - len(row))
        if row[col["Star (component)"]]:
            rows[row[col["Star (component)"]]] = (r, row)
    changes, notes, orange, why = {}, {}, set(), defaultdict(list)

    def val(n, hd):
        return rows[n][1][col[hd]]

    def cur(n, hd):
        return changes.get((n, hd), val(n, hd))

    def put(n, hd, value, note, reason=""):
        if isinstance(value, float):
            value = round(value, 6)
        changes[(n, hd)] = value
        notes[(n, hd)] = note
        orange.add((n, hd))
        if reason:
            why[n].append(reason)

    def label(n):
        return val(n, "MSC label") or n.split()[-1]

    def plx(n):
        return 3.26156 / num(val(n, "Distance (ly)"))

    pairs = [(n, row[col["Separation from"]]) for n, (r, row) in rows.items()
             if row[col["Separation from"]] and row[col["System / Host"]] not in SKIP_SYSTEMS]
    members = defaultdict(list)                     # subsystem -> its two members
    for n, (r, row) in rows.items():
        if row[col["Member of"]]:
            members[row[col["Member of"]]].append(n)
    counts = defaultdict(int)

    def mass(n):
        return num(cur(n, "Mass (M-sun)"))

    def detection(n):
        return str(val(n, "Detection (MSC)")).lower()

    # ── 0. CD-77 1092 Aa-Ab: the one suspected companion with a measured orbit (Gaia DR3) ────────────────
    gaia_orbit = {}
    for g in gaia["rows"]:
        if gaia["systems"][str(g["source_id"])][0] == "CD-77 1092" and g.get("a_thiele_innes") is not None:
            gaia_orbit["CD-77 1092 Ab"] = g

    # ── 1. masses: every star without one, then subsystem sums, until nothing changes ────────────────
    suspected = [(s, p) for s, p in pairs if num(val(s, "Separation (AU)")) is None]
    sep_of = {s: p for s, p in pairs}
    photocentre_a = {}                                   # star -> relative a from its dark-companion solution

    def dark_companion(m1, a0, p_yr):
        """M2 with a0 = a M2 / (M1 + M2), a = ((M1 + M2) P^2)^(1/3): a photocentre orbit of a dark companion."""
        lo, hi = 1e-4, 5.0
        for _i in range(100):
            m2 = (lo + hi) / 2
            a = ((m1 + m2) * p_yr ** 2) ** (1 / 3)
            lo, hi = (m2, hi) if a * m2 / (m1 + m2) < a0 else (lo, m2)
        m2 = (lo + hi) / 2
        return round(m2, 4), ((m1 + m2) * p_yr ** 2) ** (1 / 3)

    for _ in range(6):
        for n, (r, row) in rows.items():
            if row[col["System / Host"]] in SKIP_SYSTEMS or row[col["Node type"]] != "star" or mass(n) is not None:
                continue
            prim = sep_of.get(n)
            sub = row[col["Member of"]]
            sib = next((x for x in members.get(sub, []) if x != n), None)
            if prim is None:
                # a primary with no mass: its subsystem's mass, less or split with its companion
                if not sub or mass(sub) is None or sib is None:
                    continue
                if mass(sib) is not None:
                    m1 = round(mass(sub) - mass(sib), 4)
                    how = f"the subsystem's mass ({mass(sub)}, '{sub}') less its companion's ({mass(sib)}, '{sib}')"
                else:
                    m1 = round(mass(sub) / 1.3, 4)
                    how = (f"the subsystem's mass ({mass(sub)}, '{sub}') split 1 : 0.3 with its unweighed companion "
                           f"'{sib}', the typical-companion ratio")
                put(n, "Mass (M-sun)", m1, f"WEAK: no mass of its own on file.\nINFERRED: {how}.",
                    reason="primary mass from its subsystem")
                put(n, "Mass basis (MSC)", "INFERRED from the subsystem's mass (see the Mass note)",
                    "INFERRED: see Mass.")
                counts["mass_primary"] += 1
                continue
            if mass(prim) is None:
                continue
            m1 = mass(prim)
            a_tab, p_tab = num(val(n, "Separation (AU)")), num(val(n, "Orbital period (d)"))
            if n in gaia_orbit:
                g = gaia_orbit[n]
                a0_mas, *_ = thiele_innes(g["a_thiele_innes"], g["b_thiele_innes"], g["f_thiele_innes"],
                                          g["g_thiele_innes"])
                a0 = a0_mas / 1000.0 / plx(n)
                m2, _a = dark_companion(m1, a0, g["period"] / YR)
                note = (f"WEAK: Gaia's solution is an unvalidated OrbitalTargetedSearch, and the companion is taken to "
                        f"be dark.\nINFERRED: from Gaia DR3's photocentre orbit (a0 = {a0_mas:.3f} mas = {a0:.4f} AU, "
                        f"P = {g['period']:.2f} d): a0 = a M2 / (M1 + M2), a = ((M1 + M2) P^2)^(1/3), M1 = {m1}. "
                        f"SOURCE: Gaia DR3 nss_two_body_orbit, source_id {g['source_id']}.")
                basis = "INFERRED from the Gaia DR3 photocentre orbit (see the Mass note)"
            elif val(n, "Period basis") == "orbit" and a_tab and p_tab:
                mk = a_tab ** 3 / (p_tab / YR) ** 2
                if 0.01 < mk - m1 < 1.5 * m1:
                    m2 = round(mk - m1, 4)
                    note = (f"WEAK: rests on the published orbit's a being the relative orbit.\nINFERRED: Kepler's "
                            f"third law, a^3 / P^2 = {a_tab}^3 / ({p_tab} d / 365.25)^2 = {mk:.4f} M_sun, less the "
                            f"primary's {m1} ('{prim}'). Orbit source: {val(n, 'Orbit source')}.")
                else:
                    m2, a_rel = dark_companion(m1, a_tab, p_tab / YR)
                    photocentre_a[n] = a_rel
                    note = (f"WEAK: the published 'a' ({a_tab} AU) is too small for a relative orbit at these masses, "
                            f"so it is read as the photocentre's orbit of a dark companion.\nINFERRED: a0 = a M2 / "
                            f"(M1 + M2), a = ((M1 + M2) P^2)^(1/3), M1 = {m1}, P = {p_tab} d, solved for M2. Orbit "
                            f"source: {val(n, 'Orbit source')}.")
                basis = "INFERRED from the published orbit (see the Mass note)"
            else:
                m2 = round(min(0.3 * m1, 0.5), 4)
                note = (f"WEAK: nothing measures this companion ('{val(n, 'Detection (MSC)') or 'no detection note'}')."
                        f"\nINFERRED: a typical companion, 0.3 x the primary's mass ({m1} M_sun, '{prim}'), capped at "
                        "0.5 M_sun.")
                basis = "INFERRED (typical companion; see the Mass note)"
            put(n, "Mass (M-sun)", m2, note, reason="companion mass inferred")
            put(n, "Mass basis (MSC)", basis, "INFERRED: see Mass.")
            counts["mass_companion"] += 1
        for sub, ms in members.items():
            if rows[sub][1][col["System / Host"]] in SKIP_SYSTEMS or len(ms) != 2:
                continue
            vals = [mass(x) for x in ms]
            if None not in vals and (mass(sub) is None or abs(sum(vals) - mass(sub)) > 1e-3) and \
                    any((x, "Mass (M-sun)") in changes for x in ms):
                put(sub, "Mass (M-sun)", round(sum(vals), 4),
                    f"INFERRED: sum of its members' masses, {ms[0]} {vals[0]} + {ms[1]} {vals[1]}, at least one of "
                    "them inferred (WEAK).", reason="subsystem mass = sum")
                counts["mass_subsystem"] += 1

    def kepler_p(a, m):
        return math.sqrt(a ** 3 / m) * YR

    # ── 2. suspected companions: the orbit ────────────────────────────────────────────────────────
    for sec, prim in suspected:
        m = mass(prim) + mass(sec)
        P, S = label(prim), label(sec)
        if sec in gaia_orbit:
            g = gaia_orbit[sec]
            _, inc, node, w = thiele_innes(g["a_thiele_innes"], g["b_thiele_innes"], g["f_thiele_innes"],
                                           g["g_thiele_innes"])
            a = ((m) * (g["period"] / YR) ** 2) ** (1 / 3)
            src = f"Gaia DR3 nss_two_body_orbit, source_id {g['source_id']}, OrbitalTargetedSearch, P = {g['period']:.4f} d"
            base = f"WEAK: an unvalidated Gaia OrbitalTargetedSearch solution. SOURCE: {src}."
            put(sec, "Orbital period (d)", round(g["period"], 4), base)
            put(sec, "Orbital eccentricity (e)", round(g["eccentricity"], 4), base)
            put(sec, "Time of periastron (JD)", round(J2016 + g["t_periastron"], 4),
                f"{base} T = J2016.0 + t_periastron ({g['t_periastron']:.3f} d).")
            orient = f"{base} INFERRED: Campbell elements from the Thiele-Innes constants (as research.py)."
            put(sec, "Inclination (deg)", round(inc, 2), orient)
            put(sec, "Ascending node (deg)", round(node, 2), orient)
            put(sec, "Argument of periastron (deg)", round(w, 2), orient)
            put(sec, "Argument of periastron refers to", f"primary ({P})",
                "Gaia's omega is the photocentre's, i.e. the primary's.")
            put(sec, "Orbit source", f"Gaia DR3 NSS OrbitalTargetedSearch, source_id {g['source_id']}", base)
            put(sec, "Period basis", "orbit (Gaia DR3, unvalidated)", base)
            note_a = (f"INFERRED: a = ((M1 + M2) P^2)^(1/3) = (({mass(prim)} + {mass(sec)}) x ({g['period']:.2f} d / "
                      f"365.25)^2)^(1/3) AU, with the inferred companion mass (WEAK).")
            reason = "suspected: Gaia DR3 orbit"
        else:
            spec = "spectroscopic" in detection(sec) and "astrometric" not in detection(sec)
            a = 0.3 if spec else 3.0
            p_d = kepler_p(a, m)
            node = _phase_deg(f"{sec} node")
            phase = _phase_deg(sec)
            rule = (f"WEAK: a suspected companion ('{val(sec, 'Detection (MSC)')}'); nothing measures its orbit.\n"
                    "INFERRED (model): ")
            put(sec, "Orbital period (d)", round(p_d, 3),
                rule + f"P from Kepler's third law, P = (a^3 / M_tot)^(1/2) = ({a}^3 / {m:.4f})^(1/2) yr.")
            put(sec, "Orbital eccentricity (e)", 0.0, rule + "circular.")
            put(sec, "Inclination (deg)", 60.0, rule + "i = 60, the median of randomly oriented orbits.")
            put(sec, "Ascending node (deg)", round(node, 3), rule + f"node from the name hash of '{sec} node' "
                                                                   "(catalog_loader._phase_deg).")
            put(sec, "Argument of periastron (deg)", 0.0, rule + "omega = 0 on a circular orbit.")
            put(sec, "Time of periastron (JD)", round(J2000 + ((360.0 - phase) % 360.0) / 360.0 * p_d, 4),
                rule + f"phase {phase:.3f} deg at J2000 from the name hash (catalog_loader._phase_deg).")
            put(sec, "Argument of periastron refers to", f"primary ({P})", rule + "a convention, for a circular orbit.")
            put(sec, "Period basis", "model-inferred", rule + "see the orbit cells' notes.")
            note_a = rule + (f"a = {a} AU, typical for {'a spectroscopic hint (0.3 AU)' if spec else 'an astrometric '}"
                             f"{'' if spec else 'wobble (3 AU)'}.")
            reason = f"suspected: typical orbit, a = {a} AU"
        put(sec, "Separation (AU)", round(a, 5), note_a, reason=reason)
        put(sec, "Separation (arcsec)", round(a * plx(sec), 6), note_a)
        put(sec, "Separation type", "semi-major axis", note_a)
        put(sec, "Drawing status", HYPO, "WEAK: a suspected companion, drawn hollow with model-inferred values.")
        counts["suspected_orbit"] += 1

    # ── 3. wide pairs: face-on, circular, phased to the observed position angle ────────────────────────
    for sec, prim in pairs:
        if (sec, prim) in suspected or val(sec, "Period basis") == "orbit":
            continue
        a = num(cur(sec, "Separation (AU)"))
        if a is None:
            continue
        m = mass(prim) + mass(sec)
        P, S = label(prim), label(sec)
        rec = next((x for x in msc[val(sec, "WDS code")]["systems"] if x["Prim"] == P and x["Sec"] == S), None)
        p_old = num(val(sec, "Orbital period (d)"))
        p_d = kepler_p(a, m)
        rule = ("WEAK: nothing measures this orbit; only a projected separation and a position angle.\n"
                "INFERRED (model): ")
        if rec and rec.get("x_Sep") == '"' and rec.get("PA") is not None:
            pa = float(rec["PA"])
            t = J2016 + ((360.0 - pa) % 360.0) / 360.0 * p_d
            phase_note = (f"T puts the companion at its observed position angle, {pa:.0f} deg (MSC pair record "
                          f"{P},{S}), at J2016.0: face-on with node = omega = 0, the phase is the position angle.")
        else:
            pa = None
            t = J2000 + ((360.0 - _phase_deg(sec)) % 360.0) / 360.0 * p_d
            phase_note = "no position angle on file; phase at J2000 from the name hash (catalog_loader._phase_deg)."
        put(sec, "Orbital period (d)", round(p_d, 3),
            rule + f"P = (a^3 / M_tot)^(1/2) = ({a}^3 / {m:.4f})^(1/2) yr, with a the projected separation"
                   + (f"; replaces the MSC estimate ({p_old} d)" if p_old else "") + ".",
            reason=f"wide pair: face-on, PA {pa}")
        put(sec, "Orbital eccentricity (e)", 0.0, rule + "circular.")
        put(sec, "Inclination (deg)", 0.0, rule + "face-on: the orbit is drawn in the plane of the sky.")
        put(sec, "Ascending node (deg)", 0.0, rule + "face-on: the node is undefined; 0.")
        put(sec, "Argument of periastron (deg)", 0.0, rule + "circular: omega = 0.")
        put(sec, "Time of periastron (JD)", round(t, 4), rule + phase_note)
        put(sec, "Argument of periastron refers to", f"secondary ({S} relative to {P})",
            rule + "the position angle is the secondary's, relative to the primary.")
        put(sec, "Period basis", "model-inferred (face-on, circular)", rule + "see the orbit cells' notes.")
        counts["wide_pair"] += 1

    # ── 4. measured orbits missing an element ─────────────────────────────────────────────────────
    for sec, prim in pairs:
        if val(sec, "Period basis") != "orbit" or (sec, prim) in suspected:
            continue
        rule = "WEAK: the published orbit does not give this element.\nINFERRED (model): "
        P = label(prim)
        m = mass(prim) + mass(sec)
        p_d = num(cur(sec, "Orbital period (d)"))
        if p_d is None and num(cur(sec, "Separation (AU)")) is not None:
            p_d = kepler_p(num(cur(sec, "Separation (AU)")), m)
            put(sec, "Orbital period (d)", round(p_d, 3),
                rule + "P = (a^3 / M_tot)^(1/2) from the published a and the tab's masses.", reason="orbit: P Kepler")
            counts["orbit_P"] += 1
        if num(cur(sec, "Separation (AU)")) is None and p_d:
            a = ((m) * (p_d / YR) ** 2) ** (1 / 3)
            put(sec, "Separation (AU)", round(a, 5), rule + f"a = ((M1 + M2) P^2)^(1/3) with the tab's masses.")
            put(sec, "Separation (arcsec)", round(a * plx(sec), 6), rule + "from the Kepler a.")
            counts["orbit_a"] += 1
        if num(cur(sec, "Inclination (deg)")) is None:
            ecl = "eclips" in detection(sec)
            put(sec, "Inclination (deg)", 90.0 if ecl else 60.0,
                rule + ("i = 90: the pair eclipses." if ecl else "i = 60, the median of randomly oriented orbits."),
                reason="orbit: i, node assumed")
            put(sec, "Ascending node (deg)", round(_phase_deg(f"{sec} node"), 3),
                rule + f"node from the name hash of '{sec} node' (catalog_loader._phase_deg).")
            counts["orbit_i_node"] += 1
        elif num(cur(sec, "Ascending node (deg)")) is None:
            put(sec, "Ascending node (deg)", round(_phase_deg(f"{sec} node"), 3),
                rule + f"node from the name hash of '{sec} node' (catalog_loader._phase_deg).", reason="node assumed")
            counts["orbit_node"] += 1
        if (num(cur(sec, "Orbital eccentricity (e)")) or 0) >= 0.99:
            put(sec, "Orbital eccentricity (e)", 0.0,
                rule + f"e was {cur(sec, 'Orbital eccentricity (e)')}, a placeholder ({val(sec, 'Orbit source')}); "
                       "an orbit with e = 1 does not close, so circular.", reason="placeholder e -> 0")
            counts["orbit_e_placeholder"] += 1
        if num(cur(sec, "Orbital eccentricity (e)")) is None:
            put(sec, "Orbital eccentricity (e)", 0.0,
                rule + f"e = 0: a {p_d:.2f}-day pair is expected to be tidally circular.", reason="e = 0")
            counts["orbit_e"] += 1
        if num(cur(sec, "Argument of periastron (deg)")) is None:
            circ = num(cur(sec, "Orbital eccentricity (e)")) == 0
            put(sec, "Argument of periastron (deg)", 0.0 if circ else round(_phase_deg(f"{sec} omega"), 3),
                rule + ("omega = 0 on a circular orbit." if circ else "omega from the name hash."))
            counts["orbit_omega"] += 1
        if num(cur(sec, "Time of periastron (JD)")) is None:
            put(sec, "Time of periastron (JD)", round(J2000 + ((360.0 - _phase_deg(sec)) % 360.0) / 360.0 * p_d, 4),
                rule + "phase at J2000 from the name hash (catalog_loader._phase_deg)"
                + (". Fuhrmann 2005 (MNRAS 361, 803) may give the published T." if sec == "BD+08 2134 Ab" else "."),
                reason="T hashed")
            counts["orbit_T"] += 1
        if not cur(sec, "Argument of periastron refers to"):
            put(sec, "Argument of periastron refers to", f"primary ({P})",
                rule + "a spectroscopic orbit quotes the primary's omega.")

    for n, a_rel in photocentre_a.items():
        a0 = val(n, "Separation (AU)")
        note = (f"INFERRED: the published 'a' ({a0} AU) is a photocentre orbit; the relative a from Kepler's third law "
                "with the solved companion mass (owner's photocentre rule, 30 Sep 2026). WEAK: rests on that mass.")
        put(n, "Separation (AU)", round(a_rel, 5), note, reason="photocentre a -> Kepler a")
        put(n, "Separation (arcsec)", round(a_rel * plx(n), 6), note)
        counts["photocentre"] += 1

    # ── 5. barycentre offsets ─────────────────────────────────────────────────────────────────────
    for sub, ms in members.items():
        if rows[sub][1][col["System / Host"]] in SKIP_SYSTEMS or val(sub, "Node type") != "subsystem":
            continue
        prim = val(sub, "Barycentre from")
        sec = next((x for x in ms if x != prim), None)
        if not prim or not sec or cur(sec, "Separation from") != prim:
            continue
        a, m1, m2 = num(cur(sec, "Separation (AU)")), mass(prim), mass(sec)
        if None in (a, m1, m2):
            continue
        off = round(a * m2 / (m1 + m2), 6)
        if num(val(sub, "Barycentre offset (AU)")) is not None and abs(off - num(val(sub, "Barycentre offset (AU)"))) < 1e-6:
            continue
        put(sub, "Barycentre offset (AU)", off,
            ("WEAK: an input is inferred.\n" if any(k in changes for k in ((sec, "Separation (AU)"),
                                                                              (sec, "Mass (M-sun)"),
                                                                              (prim, "Mass (M-sun)"))) else "")
            + f"INFERRED: a x M_sec / (M_prim + M_sec) = {a} au x {m2} / ({m1} + {m2}) (infer.py, 30 Sep 2026).",
            reason="barycentre")
        counts["barycentre"] += 1

    # GJ 187.2 Ab: the MSC's own verdict, found after companions.py wrote it
    if "GJ 187.2 Ab" in rows:
        put("GJ 187.2 Ab", "Drawing status", HYPO,
            "WEAK: the MSC lists this pair (Aa,Ab, P = 391.7 d) as not physical ('X') with the comment "
            "'SB9_295 false?'; SB9 grade 2 (Abt 1965); Gaia DR3 has no orbit and RUWE 1.56 at G = 4.9. Drawn hollow, "
            "as a candidate (owner's decision, 30 Sep 2026).")

    # ── 6. is every pair now drawable? ─────────────────────────────────────────────────────────────
    need = ("Separation (AU)", "Orbital period (d)", "Orbital eccentricity (e)", "Inclination (deg)",
            "Ascending node (deg)", "Argument of periastron (deg)", "Time of periastron (JD)")
    left = [(s, [hd for hd in need if num(cur(s, hd)) is None] + ([] if cur(s, "Argument of periastron refers to")
                                                                  else ["refers to"])) for s, _ in pairs]
    left = [(s, x) for s, x in left if x]
    nobary = [s for s, ms in members.items() if rows[s][1][col["System / Host"]] not in SKIP_SYSTEMS
              and num(cur(s, "Barycentre offset (AU)")) is None]
    nomass = [n for n, (r, row) in rows.items() if row[col["System / Host"]] not in SKIP_SYSTEMS and mass(n) is None]

    by_name = defaultdict(list)
    for (n, hd), x in changes.items():
        by_name[n].append((hd, val(n, hd), x))
    sp = sp_entry(counts)
    if PLAN:
        for n in sorted(by_name, key=lambda n: rows[n][0]):
            print(f"\n{n} (row {rows[n][0]}) -- {'; '.join(dict.fromkeys(why[n]))}")
            for hd, old, new in by_name[n]:
                print(f"    {hd:34} {str(old)[:30]:>30} -> {str(new)[:50]}")
        print("\n" + json.dumps(counts, indent=1))
        print(f"{len(changes)} cells in {len(by_name)} rows")
        print("pairs still not drawable:", left)
        print("subsystems without a barycentre:", nobary)
        print("nodes without a mass:", nomass)
        print("\n".join(sp))
        return
    assert not left and not nobary and not nomass, (left, nobary, nomass)

    cell = {k: f"{q(FP)}!{letter(col[k[1]])}{rows[k[0]][0]}" for k in changes}
    items = [(cell[k], [[x]]) for k, x in changes.items()]
    expect = {f"{q(FP)}!{letter(col['Star (component)'])}{rows[n][0]}": n for n in by_name}
    for s in range(0, len(items), 200):
        chunk = dict(items[s:s + 200])
        rows_in = {c.rsplit("!", 1)[1].lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for c in chunk}
        gs.update_cells(SID, chunk, expect={k: x for k, x in expect.items()
                                            if k.rsplit("!", 1)[1].lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") in rows_in})
    oc = [cell[k] for k in orange]
    for s in range(0, len(oc), 200):
        gs.set_border(SID, oc[s:s + 200], gs.INFERRED_BORDER)
    ni = [(cell[k], x) for k, x in notes.items()]
    for s in range(0, len(ni), 200):
        gs.set_note(SID, dict(ni[s:s + 200]))

    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    spm = next(s["properties"] for s in meta if s["properties"]["title"] == SP)
    lastsp = spm["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{lastsp}"])[f"{q(SP)}!A{lastsp}"][0][0].strip()
    start, end = lastsp + 1, lastsp + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": spm["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps({"title": title, "counts": counts, "sp_rows": [start, end],
                               "changes": {f"{n} | {hd}": {"old": val(n, hd), "new": x, "cell": cell[(n, hd)]}
                                           for (n, hd), x in changes.items()}}, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print("done:", title, json.dumps(counts), "S&P", start, end)


def sp_entry(c):
    return [
        "",
        "30 SEPTEMBER 2026: 'Planetless 4+ Stars' -- MODEL-INFERRED ORBITS FOR EVERYTHING NOTHING MEASURES (infer.py).",
        "Writer: data/four_plus_stars/infer.py; log infer_log.json. Every value below is INFERRED (orange box) and WEAK "
        "(first line of its note), chosen by the owner on 30 Sep 2026 so that every system can be drawn. None is a "
        "measurement; replace any with a published value when one appears.",
        f"Wide pairs ({c['wide_pair']}): a circular orbit in the plane of the sky (i = 0, node = 0, omega = 0), a = the "
        "projected separation (a statistical underestimate: the mean true a is ~1.26 x the projected), P from "
        "Kepler's third law with the tab's masses (replacing the MSC's estimate), T placing the companion at the "
        "MSC's position angle at J2016.0. Drawn: right on the sky today, flat in depth. 'Period basis' reads "
        "'model-inferred (face-on, circular)'.",
        f"Measured orbits lacking an element: inclination and node ({c['orbit_i_node']}) -- i = 60 deg (median for "
        "random orientation; 90 for an eclipsing pair), node from the name hash catalog_loader._phase_deg('<name> "
        f"node'); node alone ({c['orbit_node']}); e = 0 for {c['orbit_e']} short-period pairs (tidally circular); "
        f"omega ({c['orbit_omega']}) 0 if circular, else hashed; T ({c['orbit_T']}) phase from the name hash; a "
        f"({c['orbit_a']}) from Kepler.",
        f"Suspected companions ({c['suspected_orbit']}; 'Drawing status' = 'hypothetical and model-inferred', drawn "
        "hollow): CD-77 1092 Aa-Ab from its Gaia DR3 OrbitalTargetedSearch orbit (unvalidated), its mass solved from "
        "the photocentre orbit for a dark companion; the rest a typical companion for the detection: mass 0.3 x the "
        "primary's, capped at 0.5 M_sun; a = 3 AU for an astrometric wobble, 0.3 AU for 'possibly spectroscopic'; "
        f"circular, i = 60, node and phase hashed. {c['mass_companion']} companion and {c['mass_primary']} primary "
        "masses inferred: a primary with no mass takes its subsystem's, split 1 : 0.3 with an unweighed companion; a "
        "companion on a measured orbit takes a^3/P^2 less the primary, or, where the published a is too small for "
        f"that, a dark-companion photocentre solution ({c['photocentre']}, whose a is then the Kepler relative a); "
        f"{c['mass_subsystem']} subsystem masses follow as sums.",
        f"Barycentre offsets: {c['barycentre']} computed or recomputed, a x M_sec / (M_prim + M_sec).",
        "GJ 187.2 Ab (added by companions.py): the MSC itself lists Aa,Ab as not physical ('X', 'SB9_295 false?'); "
        "kept as a hypothetical star by the owner's decision, and its note now says so.",
    ]


if __name__ == "__main__":
    main()
