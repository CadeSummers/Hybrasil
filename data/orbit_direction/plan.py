# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Decide every Orbit Direction cell, and the spin-orbit cells it corrects.  Touches nothing: writes plan.json.

    python plan.py

Inputs, all committed beside this file:
- research/spin.json: every planet on the two tabs with a measured or bounded spin-orbit angle (lambda, psi), each
  value with its bibcode and the table or section it is printed in (research agent, 10 Oct 2026).
- research/orbits.json: retrograde or polar against something other than the star's spin -- a binary companion's
  orbit, a host binary, the other planets, a debris disk -- with the evidence graded strong / substantial / weak.
- The planet names on each tab, read from the newest data/ snapshot (write.py checks them against the live sheet).

The cell is "<Direction> (vs <reference>; <angle>)" for a measurement and "Prograde (assumed)" for every planet
nobody has measured, which is how all of them are drawn by default.  A direction the paper itself states in words
(polar, retrograde) is a plain cell with a SOURCE note.  One this project classified from a published angle --
psi where known, else |lambda|: under 70 deg prograde, 70-110 polar, over 110 retrograde -- is boxed orange with an
INFERRED note.  An ambiguous or weak result stays "Prograde (assumed)", with a note saying what is known.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hybrasil.data.snapshot import load_snapshot_workbook  # noqa: E402

PLAN = HERE / "plan.json"
PLANETS, UNCONFIRMED = "Planets within 100 ly", "Unconfirmed within 100 ly"
ASSUMED = "Prograde (assumed)"
THRESHOLDS = "prograde under 70 deg, polar 70-110 deg, retrograde over 110 deg (psi where measured, else |lambda|)"
REFERENCE = {"binary orbit": "vs binary orbit", "circumbinary binary": "vs host binary orbit",
             "other planets": "vs other planets", "debris disk": "vs debris disk"}
# The orbit-geometry results drawn as they stand.  Weak ones, and "unclear" ones, stay assumed with a note.
STRONG = ("strong", "substantial")
# Spin-orbit cells this edit corrects: the flagged planets whose AQ cell is stale or empty.
SPIN_CELLS = {
    "GJ 3470 b": ("97 +16/-11 (psi; Stefansson+2022, TEPCat)",
                  "95 +9/-8 (psi; Stefansson+2022, ApJL 931 L15 Table 4)",
                  "SOURCE: 2022ApJ...931L..15S (Stefansson et al. 2022, ApJL 931, L15), abstract, Sect. 6 and Table 4: "
                  "psi = 95 +9/-8 deg, lambda = 98 +15/-12 deg. The cell held the arXiv v1 numbers (97 +16/-11) that "
                  "TEPCat still lists; the published version (arXiv:2111.01295v2) supersedes them."),
    "GJ 3090 b": ("Data Sparse, Modeled in Sync with Stellar Spin Axis",
                  "136 +24/-18 (psi; Carteret+2026)",
                  "SOURCE: 2026A&A...713L..15C (Carteret et al. 2026, A&A 713, L15, arXiv:2609.24870), abstract and "
                  "Table C.1: psi = 136 +24/-18 deg; lambda = 208 +15/-18 deg (= -152). NIRPS RM-Revolutions over five "
                  "transits. 'the first planet on a retrograde orbit discovered around an M dwarf'."),
}


def tab_planets(wb, tab):
    rows = wb["tabs"][tab]
    h = [str(x).strip() for x in rows[0]]
    iP, iH = h.index("Planet"), h.index("Host system (primary star)")
    out = []
    for r in rows[1:]:
        r = list(r) + [""] * (len(h) - len(r))
        if not str(r[iH]).strip():
            break                                  # the Planets tab's constants block starts here
        out.append(str(r[iP]).strip())
    return out


def v(d, k="value"):
    return (d or {}).get(k) if isinstance(d, dict) else None


def deg(x):
    return f"{x:g}" if abs(x) < 10 else f"{round(x):d}"


def err(d):
    if v(d, "err_plus") is not None:
        return f" +{v(d, 'err_plus')}/-{v(d, 'err_minus')}"
    return ""


def spin_cell(name, e):
    """(value, note, orange) for a planet with a spin-orbit measurement, or None if it stays assumed."""
    cls = e.get("class")
    psi, lam, bound = e.get("psi_deg"), e.get("lambda_deg"), e.get("psi_bound")
    words = e.get("paper_wording") or {}
    if cls == "unclear":
        return ASSUMED, (f"UNCLEAR, drawn prograde: {e.get('class_basis', '')} "
                         + (f"Bound: psi >= {v(bound)} ({v(bound, 'bibcode')}). " if v(bound) is not None else "")
                         + (f"'{words.get('quote')}' ({words.get('bibcode')}, {words.get('where')})." if words else "")
                         )[:1500], False
    if v(psi) is not None:
        angle, sym, d = v(psi), "psi", psi
    elif v(lam) is not None:
        angle, sym, d = abs(v(lam)), "lambda", lam
        if angle > 180:
            angle = 360 - angle
    else:
        angle, sym, d = v(bound), "psi >=", bound
    glyph = {"psi": "ψ", "lambda": "λ", "psi >=": "ψ ≥"}[sym]
    value = f"{cls.capitalize()} (vs stellar spin; {glyph} {deg(angle)}°)"
    where = f"{v(d, 'bibcode')} ({v(d, 'where')})"
    eq = sym if sym == "psi >=" else f"{sym} ="
    stated = cls in ("polar", "retrograde") and words
    if stated:
        note = (f"SOURCE: {where}: {eq} {v(d)}{err(d)} deg. The paper's words: '{words['quote']}' "
                f"({words.get('where', '')}).")
    else:
        note = (f"INFERRED: classified {cls} by this project's thresholds ({THRESHOLDS}) from {eq} "
                f"{v(d)}{err(d)} deg, {where}."
                + (" lambda alone is the sky-projected angle; the true psi can be larger."
                   if sym == "lambda" else ""))
    return value, note[:1500], not stated


def orbit_cell(name, e):
    cls, ev = e.get("class"), e.get("evidence")
    ref = REFERENCE.get(e.get("reference"), "vs " + str(e.get("reference")))
    a = e.get("angle_deg")
    words = e.get("paper_wording") or {}
    if cls not in ("prograde", "polar", "retrograde") or ev not in STRONG:
        return ASSUMED, (f"UNCLEAR or WEAK ({ev}), drawn prograde: {e.get('class_basis', '')} "
                         + (f"Angle {v(a)} deg ({v(a, 'bibcode')}, {v(a, 'where')}). " if v(a) is not None else "")
                         + (f"'{words.get('quote')}' ({words.get('bibcode')})." if words else ""))[:1500], False
    value = f"{cls.capitalize()} ({ref}" + (f"; {deg(v(a))}°)" if v(a) is not None else ")")
    stated = cls in ("polar", "retrograde") and words
    src = (f"{v(a, 'bibcode')} ({v(a, 'where')}): mutual inclination {v(a)}{err(a)} deg"
           if v(a) is not None else e.get("class_basis", ""))
    if stated:
        note = f"SOURCE: {src}. The paper's words: '{words['quote']}' ({words.get('bibcode')}, {words.get('where', '')})."
    else:
        note = f"INFERRED: classified {cls} by this project's thresholds ({THRESHOLDS}) from {src}."
    if e.get("notes"):
        note += " " + e["notes"]
    return value, note[:1500], not stated


def main():
    wb = load_snapshot_workbook()
    spin = json.loads((HERE / "research" / "spin.json").read_text(encoding="utf-8"))["planets"]
    orbits = json.loads((HERE / "research" / "orbits.json").read_text(encoding="utf-8"))["planets"]
    # 14 Her b-c: the JWST orbit leaves 32 or 145 deg; Lu et al. 2026 still call it unresolved.
    for n in ("14 Her b", "14 Her c"):
        if n in orbits:
            orbits[n] = dict(orbits[n], evidence="weak", class_basis="14 Her b-c mutual inclination: 32 or 145 "
                             "deg (JWST 2025); Xiao & Feng 2025 favour 35 deg, Lu et al. 2026 call it unresolved.")
    plan = {"tabs": {}, "flagged": []}
    for tab in (PLANETS, UNCONFIRMED):
        cells = []
        for name in tab_planets(wb, tab):
            value, note, orange = ASSUMED, None, False
            s, o = spin.get(name), orbits.get(name)
            # Orbit against orbit first when it is retrograde or polar (nu Oct, GJ 896 A, VHS 1256): it is what the
            # model reverses.  Otherwise the star's spin, then an aligned orbit-against-orbit result.
            if o and o.get("class") in ("polar", "retrograde") and o.get("evidence") in STRONG:
                value, note, orange = orbit_cell(name, o)
            elif s:
                value, note, orange = spin_cell(name, s)
                if value == ASSUMED and o:
                    _, n2, _ = orbit_cell(name, o)
                    note = (note + " | " + n2)[:1500]
            elif o:
                value, note, orange = orbit_cell(name, o)
            cell = {"planet": name, "value": value}
            if note:
                cell["note"] = note
            if orange:
                cell["orange"] = True
            cells.append(cell)
            if not value.startswith("Prograde"):
                plan["flagged"].append({"tab": tab, "planet": name, "value": value, "note": note})
        t = {"cells": cells}
        if tab == PLANETS:
            t["spin"] = [{"planet": p, "expect": a, "value": b, "note": n} for p, (a, b, n) in SPIN_CELLS.items()]
        plan["tabs"][tab] = t
    plan["sp_column_rows"] = [
        ["PLANETS WITHIN 100 LY", [
            "Orbit Direction",
            "Measured where a paper measured it: the spin-orbit angle (Rossiter-McLaughlin / Doppler tomography; "
            "TEPCat and the papers, data/orbit_direction/research/spin.json) or the orbit against a binary "
            "companion, a host binary or the other planets (astrometry, imaging; research/orbits.json). Written "
            "'<Direction> (vs <reference>; <angle>)'. Every other planet reads 'Prograde (assumed)' -- the "
            "model's default, not a measurement (no border, as the Data Sparse spin-orbit cells).",
            "High where the paper states polar/retrograde (plain cell, SOURCE note); a direction classified from a "
            "published angle by this project's thresholds (prograde < 70 deg, polar 70-110, retrograde > 110; psi "
            "where known, else |lambda|) is boxed orange with an INFERRED note. Weak or ambiguous results stay "
            "'assumed', with a note saying what is known.",
            "Each measured cell's note names the bibcode and table or section; the 7 polar/retrograde planets were "
            "checked against the papers' own text (data/orbit_direction/README.md)."]],
        ["UNCONFIRMED PLANETS -- SOURCES AND SELECTION", [
            "Orbit Direction",
            "As on the Planets sheet. No unconfirmed planet has a spin-orbit or orbit-orbit measurement strong enough "
            "to draw, so every row reads 'Prograde (assumed)'; candidates with a weak or ambiguous result carry a "
            "note (e.g. alf Cen A b).",
            "Assumed throughout", "The notes name the papers; data/orbit_direction/research/."]],
    ]
    plan["sp_lines"] = sp_lines(plan)
    PLAN.write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
    for tab, t in plan["tabs"].items():
        c = t["cells"]
        print(f"{tab}: {len(c)} rows; {sum(1 for x in c if x['value'] != ASSUMED)} measured, "
              f"{sum(1 for x in c if x.get('orange'))} orange, {sum(1 for x in c if x.get('note'))} noted")
    for f in plan["flagged"]:
        print(f"  {f['planet']}: {f['value']}")


def sp_lines(plan):
    import datetime
    flagged = "; ".join(f"{f['planet']}: {f['value']}" for f in plan["flagged"])
    return [
        "",
        f"{datetime.date.today().isoformat()}: ORBIT DIRECTION COLUMN ADDED to Planets within 100 ly and Unconfirmed "
        "within 100 ly (data/orbit_direction/, log write_log.json).",
        "Why: nu Oct A b orbits retrograde against its binary (Ramm et al. 2009/2021; Cheng et al. 2025, Nature 641, "
        "866) but was drawn prograde -- every catalog planet was drawn coplanar and prograde. Each planet on both tabs "
        "was checked for a measured or well-evidenced polar or retrograde orbit.",
        f"Polar or retrograde: {flagged}.",
        "Against the star's spin (polar/retrograde) the viewer tilts the star's spin axis by the angle; against a "
        "binary companion it draws the planet going round the other way, the star's axis assumed (dashed) to follow "
        "the binary. Everything else reads 'Prograde (assumed)'.",
        "Spin-orbit column corrected: GJ 3470 b to the published psi = 95 +9/-8 (was arXiv v1's 97 +16/-11); GJ 3090 b "
        "filled, psi = 136 +24/-18 (Carteret et al. 2026).",
        "Not drawn as misaligned, weak or ambiguous: gam Cep b (113.9 deg vs binary, marginal Hipparcos inclination), "
        "14 Her b-c (32 or 145 deg), pi Men b-c (52-129 deg, sense unknown), AU Mic c (aligned or polar), alf Cen A b; "
        "lower bounds only for GJ 504 b, 51 Eri b, CD-35 2722 b. Their cells carry the note.",
    ]


if __name__ == "__main__":
    main()
