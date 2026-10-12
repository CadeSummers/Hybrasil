# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Decide every cell of the Sgr A* S-stars tab.  Touches nothing: writes plan.json and prints a summary.

    python plan.py

Inputs, all committed beside this file:
- cat/gillessen2017_table3.dat: the 40 orbits, early/late flags and K magnitudes (Gillessen et al. 2017).
- research/A.json, B.json: spectral types, masses, Teff, radial velocities, SIMBAD ids, per star, each with its
  bibcode (three research agents, 9 Oct 2026; every cited value checked to be in the paper before use).
- research/C.json: Sgr A* (GRAVITY 2022), GRAVITY's refits of S2/S29/S38/S55, the disputed stars (Peisker et al.).
- infer.py: class, Teff and mass from K for an early-type star no paper has typed.

A value computed rather than read is listed in plan['inferred'] with its note; build.py boxes it orange.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import infer  # noqa: E402
from hybrasil.data.sgr_a_loader import (CENTRE, HEADERS, SMBH, sky_elements, sky_motion,  # noqa: E402
                                             LY_PER_PC)

PLAN = HERE / "plan.json"
MOTION_EPOCH = 2026.77            # 9 Oct 2026, when the tab was built
G17, G17_R0, G17_M = "2017ApJ...837...30G", 8320.0, 4.28e6
L12, L12_R0, L12_M = "2022A&A...657L..12G", 8277.0, 4.297e6
AU_PER_MPC = 206.264806
EHT = "2022ApJ...930L..12E"
PETROV = "2011AJ....142...35P"


def jload(name):
    return json.loads((HERE / "research" / name).read_text(encoding="utf-8"))


def v(d, key="value"):
    return (d or {}).get(key) if isinstance(d, dict) else None


def table3():
    out = {}
    for line in (HERE / "cat" / "gillessen2017_table3.dat").read_text().splitlines():
        if not line.strip():
            continue
        f = lambda a, b: float(line[a:b]) if line[a:b].strip() else None   # noqa: E731
        out[line[0:4].strip()] = dict(
            a=f(7, 15), e=f(23, 29), i=f(37, 43), node=f(49, 55), omega=f(62, 68), tp=f(75, 82), P=f(90, 97),
            e_P=f(98, 105), group={"e": "early-type", "l": "late-type"}.get(line[106:107].strip(), ""),
            kmag=f(108, 113))
    return out


def fmt_err(d):
    if not isinstance(d, dict):
        return ""
    if d.get("err") is not None:
        return f" +/- {d['err']}"
    if d.get("err_plus") is not None:
        return f" +{d['err_plus']}/-{d['err_minus']}"
    return ""


def main():
    t3 = table3()
    A, B, C = jload("A.json"), jload("B.json"), jload("C.json")
    research = {**A["stars"], **B["stars"]}
    papers = {**A.get("papers", {}), **B.get("papers", {}), **C.get("papers", {})}
    rows, inferred, notes = [], {}, {}

    def infer_cell(name, h, value, note):
        inferred[f"{name}|{h}"] = note
        return value

    # ── Sgr A* ──
    sa = C["sgr_a"]
    m, r0 = v(sa["mass_msun"]), v(sa["r0_pc"])
    ly = r0 * LY_PER_PC
    rows.append({
        "Object": CENTRE, "Object type": SMBH,
        "Role in system": "System centre: the black hole every S-star orbits (not a star)",
        "Status": "confirmed", "SIMBAD main_id": v(sa["simbad_main_id"]) or "NAME Sgr A*",
        "Stellar Class": "", "Mass (M-sun)": m,
        "Star data source": f"GRAVITY Collaboration 2022, A&A 657, L12 ({L12}), Sect. 6 and Table B.1: "
                            f"M = {m / 1e6:.3f} +/- {sa['mass_msun']['err'] / 1e6:.3f} x10^6 Msun (stat; ~0.04 sys)",
        "RA (deg, ICRS)": v(sa["ra_deg"]), "Dec (deg, ICRS)": v(sa["dec_deg"]), "Distance (pc)": r0,
        "Distance (ly)": infer_cell(CENTRE, "Distance (ly)", round(ly, 1),
                                    f"INFERRED: R0 = {r0:g} pc (GRAVITY 2022, {L12}) x {LY_PER_PC} ly/pc."),
        "Existence": "confirmed: SIMBAD, GRAVITY 2022, EHT 2022",
        "Refs": f"Mass: {L12}; Distance: {L12}; Position: {PETROV}; Image and mass check: {EHT}",
    })
    notes[f"{CENTRE}|Object type"] = (
        "FLAG: Sgr A* is the supermassive black hole at the centre of this system and of the Milky Way -- neither a "
        "star nor a planet (docs/hybrasil-instructions.md section 6). Every row below orbits it. "
        f"EHT 2022 ({EHT}) images its shadow and gives 4.0 +1.1/-0.6 x10^6 Msun from the maser distance.")
    newer = sa.get("newer") or ""
    if newer:
        notes[f"{CENTRE}|Mass (M-sun)"] = f"SOURCE: {L12}. {newer}"[:1500]

    # ── the S-stars ──
    refits = {k: g for k, g in C["gravity_refits"].items() if not k.startswith("_")}
    disputed = {k: d for k, d in C["disputed"].items() if not k.startswith("_")}
    names = list(t3) + list(disputed)
    published_mass = {}
    for name in names:
        g = t3.get(name)
        rs = research.get(name, {})
        dz = disputed.get(name)
        row = {"Object": name, "Object type": "Star", "SIMBAD main_id": "", "Role in system": "S-star: orbits Sgr A*"}
        refs = {}

        # identity and status
        sim = v(rs.get("simbad_main_id")) or v((dz or {}).get("simbad_main_id"))
        row["SIMBAD main_id"] = sim or ""
        if dz:
            row["Status"] = "disputed: Peisker et al. only; GRAVITY does not see it"
            by = "; ".join(f"{x['bibcode']}: {x['claim']}" for x in dz.get("disputed_by", []))
            rep = "; ".join(f"{x.get('bibcode')}: {x.get('claim') or x.get('summary') or ''}"
                            for x in dz.get("replies", []))
            notes[f"{name}|Status"] = (f"DISPUTED. Claimed by {dz['orbit']['bibcode']}. Disputed by: {by}"
                                       + (f" Replies: {rep}" if rep else ""))[:4000]
            refs["Disputed by"] = [x["bibcode"] for x in dz.get("disputed_by", [])]
        else:
            row["Status"] = "confirmed"

        # class, mass, Teff
        group = g["group"] if g else ""
        kmag = g["kmag"] if g else v((dz or {}).get("kmag"))
        row["Spectral group (Gillessen 2017)"] = group
        row["K mag"] = kmag
        st = rs.get("spectral_type") or (dz or {}).get("spectral_type")
        stv = v(st) or ""
        specific = stv and stv not in ("early-type", "late-type")
        mass_d = rs.get("mass_msun") or (dz or {}).get("mass_msun")
        teff_d = rs.get("teff_k") or (dz or {}).get("teff_k")
        src = []
        if specific:
            row["Stellar Class"] = stv
            src.append(f"class: {st['bibcode']} ({st.get('where', '')})")
            refs.setdefault("Class", []).append(st["bibcode"])
        if v(mass_d) is not None:
            row["Mass (M-sun)"] = v(mass_d)
            published_mass[name] = (kmag, v(mass_d))
            src.append(f"mass {v(mass_d)}{fmt_err(mass_d)}: {mass_d['bibcode']} ({mass_d.get('where', '')})")
            refs.setdefault("Mass", []).append(mass_d["bibcode"])
        if v(teff_d) is not None:
            row["Effective temp (K)"] = v(teff_d)
            src.append(f"Teff: {teff_d['bibcode']}")
            refs.setdefault("Teff", []).append(teff_d["bibcode"])
        need_class, need_mass = not specific, v(mass_d) is None
        inf_bits = []
        if (need_class or need_mass) and group == "early-type" and kmag is not None:
            try:
                d = infer.as_dwarf(kmag)
            except ValueError:
                d = None
            if d:
                lo, hi = infer.mass_range(kmag)
                base = (f"INFERRED: an early-type S-star as a main-sequence dwarf. M_K = K {kmag} - A_K {infer.A_K} "
                        f"({infer.A_K_BIB}) - DM at R0 {infer.R0_PC:g} pc ({infer.R0_BIB}) = {d['mk']:.2f}, "
                        f"interpolated in Pecaut & Mamajek's mean dwarf sequence ({infer.EEM_BIB}). Against the 7 "
                        "S-stars Habibi et al. 2017 weigh, it runs +0.06 dex high, 0.075 dex rms. Valid for B "
                        "dwarfs, M_K -3.2 to +1.")
                if need_class:
                    row["Stellar Class"] = infer_cell(name, "Stellar Class", d["spt"], base)
                    inf_bits.append("class")
                if need_mass:
                    row["Mass (M-sun)"] = infer_cell(name, "Mass (M-sun)", round(d["mass"], 1),
                                                     base + f" Range for K +/- 0.1 and A_K +/- 0.1: {lo:.1f}-{hi:.1f}.")
                    inf_bits.append("mass")
                if v(teff_d) is None:
                    row["Effective temp (K)"] = infer_cell(name, "Effective temp (K)", round(d["teff"], -2), base)
                    inf_bits.append("Teff")
            else:
                src.append(f"no inference: M_K {infer.absolute_k(kmag):.2f} is brighter than any dwarf -- a "
                           "giant or supergiant of the young disk, class unknown")
        elif (need_class or need_mass) and group == "late-type":
            base = ("INFERRED, WEAK: a late-type S-star is a K/M giant of the old nuclear cluster (Habibi et al. 2019, "
                    "2019ApJ...872L..15H, type the brightest as K0-K3 III and G III); its K magnitude barely "
                    f"constrains its mass. Nominal {infer.LATE_MASS} Msun, range {infer.LATE_RANGE[0]}-"
                    f"{infer.LATE_RANGE[1]}.")
            if need_class:
                row["Stellar Class"] = infer_cell(name, "Stellar Class", "late-type giant (K-M III)", base)
                inf_bits.append("class")
            if need_mass:
                row["Mass (M-sun)"] = infer_cell(name, "Mass (M-sun)", infer.LATE_MASS, base)
                inf_bits.append("mass")
        elif need_class and not group and not dz:
            src.append("spectral group unknown (Gillessen 2017): nothing to infer from")
        if inf_bits:
            src.insert(0, f"INFERRED ({', '.join(inf_bits)}) from K, see the cells' notes")
        row["Star data source"] = "; ".join(src)

        # orbit
        if name in refits:
            o = refits[name]
            a_as, r0, mass, bib = v(o["a_arcsec"]), L12_R0, L12_M, o["bibcode"]
            el = dict(e=v(o["e"]), i=v(o["i_deg"]), node=v(o["Omega_deg"]), omega=v(o["omega_deg"]), tp=v(o["tP_yr"]))
            a_au = a_as * r0
            P = math.sqrt(a_au ** 3 / mass)
            row["Orbital period (yr)"] = infer_cell(
                name, "Orbital period (yr)", round(P, 3),
                f"INFERRED: P = sqrt(a^3 / M), a = {a_as}\" x R0 {r0:g} pc, M = {mass / 1e6:.3f}e6 Msun, the "
                f"fit's own ({bib}, Table B.1, which tabulates no period). Osculating elements; the fit's conversion "
                "time is near apocentre."
                + (" GRAVITY 2020 (2020A&A...636L...5G, Table E.1) gives P = 16.0455 +/- 0.0013 yr." if name == "S2"
                   else ""))
            row["Orbit source"] = f"GRAVITY Collaboration 2022, A&A 657, L12 ({bib}), Table B.1; replaces {G17}"
            refs["Orbit"] = [bib]
        elif dz:
            o = dz["orbit"]
            a_au = v(o["a_mpc"]) * AU_PER_MPC
            a_as, r0, bib = None, None, o["bibcode"]
            el = dict(e=v(o["e"]), i=v(o["i_deg"]), node=v(o["Omega_deg"]), omega=v(o["omega_deg"]), tp=v(o["tP_yr"]))
            P = v(o["P_yr"])
            row["Orbital period (yr)"] = P
            row["Orbit source"] = f"Peisker et al. ({bib}), {o.get('where', '')[:160]}"
            refs["Orbit"] = [bib]
        else:
            a_as, r0, bib = g["a"], G17_R0, G17
            el = dict(e=g["e"], i=g["i"], node=g["node"], omega=g["omega"], tp=g["tp"])
            a_au = a_as * r0 if a_as and a_as > 0 else None
            P = g["P"]
            row["Orbital period (yr)"] = P
            row["Orbit source"] = f"Gillessen et al. 2017, ApJ 837, 30 ({G17}), Table 3 (VizieR J/ApJ/837/30)"
            refs["Orbit"] = [G17]
            if a_au and P:
                pk = math.sqrt(a_au ** 3 / G17_M)
                if abs(pk - P) > 3 * max(g["e_P"] or 0, 0.01 * P):
                    notes[f"{name}|Orbital period (yr)"] = (
                        f"CHECK: sqrt(a^3/M) with a = {a_as}\" x {G17_R0:g} pc and M = 4.28e6 (Gillessen 2017's own) "
                        f"gives {pk:.1f} yr, outside 3 sigma of the published {P} +/- {g['e_P']}; left as published.")
        row["Semi-major axis (arcsec)"] = a_as
        for h, k in (("Orbital eccentricity (e)", "e"), ("Inclination (deg)", "i"), ("Ascending node (deg)", "node"),
                     ("Argument of periapsis (deg)", "omega"), ("Time of periapsis (yr)", "tp")):
            row[h] = el[k]
        if a_au:
            how = (f"a = {a_as}\" x R0 {r0:g} pc, the orbit paper's own distance" if a_as
                   else f"a = {v(dz['orbit']['a_mpc'])} mpc x {AU_PER_MPC} AU/mpc, as Peisker et al. quote it")
            row["Semi-major axis (AU)"] = infer_cell(name, "Semi-major axis (AU)", round(a_au, 1), f"INFERRED: {how}.")
            peri = a_au * (1 - el["e"])
            row["Pericentre distance (AU)"] = infer_cell(name, "Pericentre distance (AU)", round(peri, 1),
                                                         f"INFERRED: a (1 - e) = {a_au:.1f} x (1 - {el['e']}).")
        if a_au and P and el["e"] < 1:
            sky = sky_elements(a_au, el["e"], el["i"], el["node"], el["omega"], el["tp"], P)
            from hybrasil.data.sgr_a_loader import year_to_jd
            dist = r0 or L12_R0
            mo = sky_motion(sky, year_to_jd(MOTION_EPOCH), dist)
            how = (f"INFERRED: from the orbit (this row's elements and period) by Kepler's equation at {MOTION_EPOCH} "
                   f"(9 Oct 2026), seen from {dist:g} pc; the papers' ascending node is the receding one "
                   "(hybrasil/data/sgr_a_loader.py). Checked on S2 against all 145 of Gillessen 2017's positions "
                   "and 44 radial velocities.")
            row["Motion epoch (yr)"] = MOTION_EPOCH
            for h, val, nd in (("RA offset (mas)", mo.ra_off_mas, 1), ("Dec offset (mas)", mo.dec_off_mas, 1),
                               ("Distance from Sgr A* (AU)", mo.r_au, 0), ("Radial velocity (km/s)", mo.rv_kms, 0),
                               ("Proper motion (mas/yr)", mo.pm_masyr, 2), ("3-D speed (km/s)", mo.speed_kms, 0),
                               ("Direction of sky motion (PA, deg)", mo.pa_deg, 1)):
                row[h] = infer_cell(name, h, round(val, nd), how)

        # measured RV
        rv = rs.get("rv_kms")
        if v(rv) is not None:
            row["Measured radial velocity (km/s)"] = v(rv)
            row["Measured RV epoch (yr)"] = v(rv, "epoch") if v(rv, "epoch") is not None else ""
            row["Measured RV source"] = f"{rv['bibcode']} ({rv.get('where', '')})"[:300]
            refs.setdefault("RV", []).append(rv["bibcode"])

        if dz:
            row["Existence"] = ("disputed: claimed by Peisker et al. only"
                                + (f"; SIMBAD lists {sim}" if sim else "; not in SIMBAD"))
        else:
            row["Existence"] = "confirmed: " + ", ".join(x for x in ("SIMBAD" if sim else "", "Gillessen 2017") if x)
        row["Refs"] = "; ".join(f"{k}: {', '.join(dict.fromkeys(b))}" for k, b in refs.items())
        rows.append(row)

    # ── added 10 Oct 2026 from research/D.json, after the 48 rows of 9 Oct (add.py appends only these) ──
    D = jload("D.json")
    papers.update(D.get("papers", {}))
    for name, d in [("S301", D["s301"])] + [(n, D["new_stars"][n]) for n in ADDED]:
        rows.append(added_row(name, d, infer_cell, notes))

    cal = infer.calibrate(published_mass_dwarfs(published_mass, research))
    plan = {"headers": HEADERS, "rows": [[r.get(h, "") if r.get(h) is not None else "" for h in HEADERS] for r in rows],
            "inferred": inferred, "notes": notes, "calibration": cal, "papers": papers, "motion_epoch": MOTION_EPOCH}
    PLAN.write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
    n_inf = {}
    for k in inferred:
        h = k.split("|", 1)[1]
        n_inf[h] = n_inf.get(h, 0) + 1
    print(f"{len(rows)} rows ({len(t3)} Gillessen, {len(disputed)} disputed, {1 + len(ADDED)} added, 1 Sgr A*); "
          f"{len(inferred)} inferred cells: {n_inf}")
    print(f"calibration: n={cal['n']} mean {cal['mean_dex']:+.3f} dex rms {cal['rms_dex']:.3f}")
    for r in rows:
        print(f"  {r['Object']:6} {r.get('Status', '')[:9]:9} {str(r.get('Stellar Class', ''))[:26]:26} "
              f"M={r.get('Mass (M-sun)', '')!s:9} P={r.get('Orbital period (yr)', '')!s:8} "
              f"r={r.get('Distance from Sgr A* (AU)', '')!s:7} RV={r.get('Radial velocity (km/s)', '')!s:6}")
    print("notes:", [k for k in notes])


ADDED = ("S5", "R1", "R14", "R30", "R70", "S72", "G1", "G2")
NATURE26, VF22, GIL25 = "2026Natur.657..359A", "2022ApJ...932L...6V", "2026A&A...707A..79G"
ORBIT_PAPER = {NATURE26: "GRAVITY+ Collaboration 2026, Nature 657, 359", VF22: "von Fellenberg et al. 2022, ApJ 932, L6",
               GIL25: "Gillessen et al. 2026, A&A 707, A79"}


def motion_cells(name, el, a_au, P, dist, infer_cell, row):
    """Where the star is and how it moves at MOTION_EPOCH, from its own orbit: every cell orange."""
    from hybrasil.data.sgr_a_loader import year_to_jd
    sky = sky_elements(a_au, el["e"], el["i"], el["node"], el["omega"], el["tp"], P)
    mo = sky_motion(sky, year_to_jd(MOTION_EPOCH), dist)
    how = (f"INFERRED: from the orbit (this row's elements and period) by Kepler's equation at {MOTION_EPOCH} "
           f"(9 Oct 2026), seen from {dist:g} pc; the papers' ascending node is the receding one "
           "(hybrasil/data/sgr_a_loader.py). Checked on S2 against all 145 of Gillessen 2017's positions "
           "and 44 radial velocities.")
    row["Motion epoch (yr)"] = MOTION_EPOCH
    for h, val, nd in (("RA offset (mas)", mo.ra_off_mas, 1), ("Dec offset (mas)", mo.dec_off_mas, 1),
                       ("Distance from Sgr A* (AU)", mo.r_au, 0), ("Radial velocity (km/s)", mo.rv_kms, 0),
                       ("Proper motion (mas/yr)", mo.pm_masyr, 2), ("3-D speed (km/s)", mo.speed_kms, 0),
                       ("Direction of sky motion (PA, deg)", mo.pa_deg, 1)):
        row[h] = infer_cell(name, h, round(val, nd), how)


def added_row(name, d, infer_cell, notes):
    """One row from research/D.json: S301, a von Fellenberg 2022 star, or a dusty object (G1, G2)."""
    dusty = "dusty" in (d.get("object_class") or "")
    o = d["orbit"]
    bib = o["bibcode"]
    aka = [n for n in d.get("names", []) if n != name]
    row = {"Object": name, "Object type": "Dusty object" if dusty else "Star"}
    refs = {"Orbit": [bib]}
    if dusty:
        row["Role in system"] = ("Dusty object: orbits Sgr A*; a gas cloud or a dust-enshrouded star (disputed)"
                                 + (f". Also {', '.join(aka)}" if aka else ""))
        row["Status"] = "orbit confirmed; nature disputed (gas cloud or star)"
    else:
        row["Role in system"] = "S-star: orbits Sgr A*" + (f". Also {', '.join(aka)}" if aka else "")
        row["Status"] = "confirmed"
    notes[f"{name}|Status"] = d["status"][:4000]
    sim = v(d.get("simbad_main_id"))
    row["SIMBAD main_id"] = sim or ""
    if not sim:
        notes[f"{name}|SIMBAD main_id"] = f"CHECK: {d['simbad_main_id']['where']}"[:1500]

    # class, mass, Teff, K: published only, else inferred
    src = []
    for h, key, label, ref in (("Stellar Class", "spectral_type", "class", "Class"), ("K mag", "kmag", "K", "K"),
                               ("Mass (M-sun)", "mass_msun", "mass", "Mass"),
                               ("Effective temp (K)", "teff_k", "Teff", "Teff")):
        x = d.get(key) or {}
        if v(x) is not None:
            row[h] = v(x)
            src.append(f"{label} {v(x)}{fmt_err(x)}: {x['bibcode']} ({x.get('where', '')[:140]})")
            refs.setdefault(ref, []).append(x["bibcode"])
    cls, kmag = str(row.get("Stellar Class") or ""), row.get("K mag")
    if name == "S301" and row.get("Mass (M-sun)") is None:
        row["Mass (M-sun)"] = infer_cell(
            name, "Mass (M-sun)", 1.3,
            f"INFERRED: the middle of the paper's range ({NATURE26}, Methods 'Spectral type, mass and age of "
            "S301': 'a mass of just below 1.5 Msun. Alternatively ... between approximately 1.1 Msun and 1.5 Msun, "
            "depending on the age'), from its K magnitude and an F1.5 main-sequence star. Range 1.1-1.5.")
        src.insert(0, "INFERRED (mass) from the paper's 1.1-1.5 Msun range, see the cell's note")
    elif not dusty and row.get("Mass (M-sun)") is None and kmag is not None and cls[:1] in ("O", "B"):
        try:
            dw = infer.as_dwarf(kmag)
        except ValueError:
            dw = None
        if dw:
            try:
                lo, hi = infer.mass_range(kmag)
            except ValueError:                       # K - 0.14 is off the bright end of the sequence
                lo = hi = dw["mass"]
            row["Mass (M-sun)"] = infer_cell(
                name, "Mass (M-sun)", round(dw["mass"], 1),
                f"INFERRED: an early-type ({cls}) S-star as a main-sequence dwarf. M_K = K {kmag} - A_K {infer.A_K} "
                f"({infer.A_K_BIB}) - DM at R0 {infer.R0_PC:g} pc ({infer.R0_BIB}) = {dw['mk']:.2f}, interpolated "
                f"in Pecaut & Mamajek's mean dwarf sequence ({infer.EEM_BIB}). Against the 7 S-stars Habibi et al. "
                "2017 weigh, it runs +0.06 dex high, 0.075 dex rms. Valid for B dwarfs, M_K -3.2 to +1."
                + (f" Range for K +/- 0.1 and A_K +/- 0.1: {lo:.1f}-{hi:.1f}." if lo != hi else ""))
            src.insert(0, "INFERRED (mass) from K, see the cell's note")
        else:
            src.append(f"no inference: M_K {infer.absolute_k(kmag):.2f} is brighter than any dwarf -- a "
                       "giant or supergiant of the young disk")
    row["Star data source"] = "; ".join(src) or "no class, K or mass published"

    # orbit
    a_as = v(o.get("a_arcsec"))
    if a_as is None and v(o.get("a_mas")) is not None:
        a_as = v(o["a_mas"]) / 1000.0
    el = dict(e=v(o["e"]), i=v(o["i_deg"]), node=v(o["Omega_deg"]), omega=v(o["omega_deg"]), tp=v(o["tP_yr"]))
    r0 = o.get("r0_pc_used") or L12_R0
    mass = o.get("mass_used_msun") or L12_M
    r0_how = ("the fit's own" if o.get("r0_pc_used") else
              f"GRAVITY 2022's ({L12}; the orbit paper states none, and quotes 8.28 kpc from it in Sect. 2.7)")
    a_au = a_as * r0
    for h, k in (("Orbital eccentricity (e)", "e"), ("Inclination (deg)", "i"), ("Ascending node (deg)", "node"),
                 ("Argument of periapsis (deg)", "omega"), ("Time of periapsis (yr)", "tp")):
        row[h] = el[k]
    row["Semi-major axis (arcsec)"] = a_as
    row["Semi-major axis (AU)"] = infer_cell(name, "Semi-major axis (AU)", round(a_au, 1),
                                             f"INFERRED: a = {a_as}\" x R0 {r0:g} pc, {r0_how}.")
    row["Pericentre distance (AU)"] = infer_cell(name, "Pericentre distance (AU)", round(a_au * (1 - el["e"]), 1),
                                                 f"INFERRED: a (1 - e) = {a_au:.1f} x (1 - {el['e']}).")
    P = v(o.get("P_yr"))
    pk = math.sqrt(a_au ** 3 / mass)
    if P is None:
        P = round(pk, 1)
        row["Orbital period (yr)"] = infer_cell(
            name, "Orbital period (yr)", P,
            f"INFERRED: P = sqrt(a^3 / M), a = {a_as}\" x R0 {r0:g} pc, M = {mass / 1e6:.3f}e6 Msun, the fit's own "
            f"({bib}, which tabulates no period). Osculating elements of a fit with a drag force: the cloud does "
            "not follow a closed Keplerian orbit.")
    else:
        row["Orbital period (yr)"] = P
        if abs(pk - P) > 0.03 * P:
            notes[f"{name}|Orbital period (yr)"] = (
                f"CHECK: sqrt(a^3/M) with a = {a_as}\" x {r0:g} pc and M = {mass / 1e6:.3f}e6 gives {pk:.1f} yr, "
                f"not the published {P}; left as published.")
    where = ("Extended Data Table 2, first of two solutions (arXiv:2607.12664 prints the same)" if name == "S301"
             else o.get("where", ""))
    row["Orbit source"] = f"{ORBIT_PAPER[bib]} ({bib}), {where[:200]}"
    if name == "S301":
        alt = d["orbit_alt"]
        notes[f"{name}|Ascending node (deg)"] = (
            "TWO SOLUTIONS: no radial velocity is measured yet, so the paper gives two orbit orientations, nearly "
            "mirror images through the sky plane (Extended Data Table 2). This row and the viewer use the first, the "
            f"one whose posterior is Extended Data Fig. 5. The second: e {v(alt['e'])}, i {v(alt['i_deg'])}, "
            f"Omega {v(alt['Omega_deg'])}, omega {v(alt['omega_deg'])}, tP {v(alt['tP_yr'])}. "
            f"a = {v(o['a_mas'])} +/- {o['a_mas']['err']} mas as printed; M {mass:g} Msun and R0 {r0:g} pc fixed. "
            "Angles follow Gillessen et al. 2009 (ascending node receding). 1PN fit, so the elements are osculating.")
    elif dusty:
        notes[f"{name}|Orbit source"] = (
            f"{o.get('conventions', '')} Individual fit, drag-force parameter free (Gillessen et al. 2019's model). "
            + "; ".join(f"Alternative: {x['bibcode']} {x.get('where', '')}" for x in o.get("alternates", [])
                        if isinstance(x, dict)))[:4000]
    motion_cells(name, el, a_au, P, r0, infer_cell, row)

    if dusty:
        row["Existence"] = (f"orbit confirmed by three groups (MPE, UCLA, Cologne); SIMBAD lists {sim}" if sim
                            else "orbit confirmed by three groups (MPE, UCLA, Cologne)")
    else:
        paper = "GRAVITY+ 2026" if bib == NATURE26 else "von Fellenberg 2022"
        row["Existence"] = f"confirmed: {'SIMBAD, ' if sim else ''}{paper}" + (
            "" if sim else "; SIMBAD cross-identification ambiguous (see SIMBAD main_id note)")
    row["Refs"] = "; ".join(f"{k}: {', '.join(dict.fromkeys(b))}" for k, b in refs.items())
    return row


def published_mass_dwarfs(published, research):
    """The published masses the dwarf relation should reproduce: B dwarfs with a Habibi 2017 mass."""
    return {s: km for s, km in published.items()
            if km[0] is not None and (research.get(s, {}).get("mass_msun") or {}).get("bibcode") == "2017ApJ...847..120H"}


if __name__ == "__main__":
    main()
