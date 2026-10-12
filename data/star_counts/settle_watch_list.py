# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Four objects on the TODO watch list, settled by the literature (9 Oct 2026).

    python settle_watch_list.py          plan: print every write; touches nothing
    python settle_watch_list.py write    write it all, log every deleted row, provenance, rename

They sat at the hydrogen-burning limit on Planetless 4+ Stars, kept as stars by migrate_bds.py until each was read
against the rule in docs/hybrasil-instructions.md section 6. The literature check and the owner's decisions:

- GJ 310.1 Bb is HD 72946 B, a brown dwarf: a dynamical 72.4 +/- 1.6 MJup and L5 (Maire et al. 2020), 'a BD whose
  mass is near the hydrogen-burning limit' (Brandt et al. 2021); no source says it fuses hydrogen. To Planets round
  GJ 310.1 Ba, as migrate_bds.py filed the others: B collapses into Ba, and AB's mass and barycentre are re-derived
  without the brown dwarf, as fix_bd_barycentres.py did.
- GJ 275.2 Ab is probably spurious: one preliminary 1981 astrometric orbit whose 0.94 yr period sits on the
  parallax's, which Gaia DR3 and two imaging surveys do not see. To Rejected candidates; A collapses into Aa.
- HR 1099 Bb stays a star: its only paper gives a minimum mass, 0.07 M-sun, and types it M; its 'brown dwarf' role
  was the MSC's reading of that floor. The role becomes 'star', with the Gaia doubt in a note.
- GJ 747.2 Bb stays a star: hollow, its mass the typical-companion rule's assumption; nothing detects it but
  Gaia DR3's RUWE 5.3 for B. A note says so.

Every deleted row is kept, values, formulas and notes, in settle_watch_list_log.json.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
import migrate_bds as M  # noqa: E402  (its PLAN is unused here; ours is below)

gs, q, letter, API, SID = M.gs, M.q, M.letter, M.API, M.SID
PLAN = "write" not in sys.argv[1:]
LOG = HERE / "settle_watch_list_log.json"
DATE, ISO = "9 Oct 2026", "2026-10-09"
M.DATE, M.ISO = DATE, ISO                       # planet_spec() stamps the flags text with these
RJ = "Rejected candidates"

MAIRE = "Maire et al. 2020, A&A 633, L2 (arXiv:1912.02565)"
BRANDT = "Brandt et al. 2021, AJ 162, 301 (arXiv:2109.07525)"
BOUCHY = "Bouchy et al. 2016, A&A 585, A46 (arXiv:1511.08397)"
HRR = "Harrington, Christy & Strand 1981, AJ 86, 909 (1981AJ.....86..909H)"
TG01 = "Tokovinin & Gorynya 2001, A&A 374, 227 (2001A&A...374..227T)"

BD = (M.PL, "GJ 310.1", "GJ 310.1 Bb", M.PN, "GJ 310.1 Bb", "GJ 310.1 Ba", "confirmed")
REJECT = ("GJ 275.2", "GJ 275.2 Ab")
HIERARCHY = {"GJ 310.1": ("((Aa,Ab),(Ba,Bb)),G", "((Aa,Ab),Ba),G"),
             "GJ 275.2": ("(Aa,Ab),(Ba,Bb)", "Aa,(Ba,Bb)")}
WHY_BD = (f"It is HD 72946 B. {MAIRE}: dynamical mass 72.4 +/- 1.6 MJup, spectral type L5.0 +/- 1.5, 'closest "
          f"benchmark brown dwarf companion to a solar-type star'; {BRANDT}: 72.5 +/- 1.3 MJup, 'a BD whose mass is "
          f"near the hydrogen-burning limit'; discovered by {BOUCHY}, Msini 60.4 +/- 2.2 MJup. No source says it "
          "sustains hydrogen fusion. The MSC's 0.07 M-sun (73 MJup) is carried; it agrees with both.")
REJECTED_BECAUSE = (
    f"Probably spurious. The only detection is {HRR}, who call their result 'still preliminary': the 0.94 yr "
    "perturbation period is close to the 1 yr parallax period and the amplitude is small. They suggest 'the faint "
    "component might be a low-mass red dwarf' of about 0.08 M-sun, and predict an RV variation 'of the order of "
    "10 km/s'. Gaia DR3 975968718869126144 (G 107-69) has no non-single-star solution and a constant RV over 17 "
    "transits; RUWE 1.36 (the MSC notes 1.1). No companion in POKEMON speckle (Clark et al. 2024, AJ 167, 56) or "
    "CARMENES FastCam imaging (Cortes-Contreras et al. 2017, A&A 597, A47). Winters et al. 2021 (AJ 161, 63) list it "
    "only as an astrometric detection, citing Harrington. Literature check and owner's decision, 9 Oct 2026. Source "
    "confidence MEDIUM: Gaia and the imaging surveys were read from VizieR tables; nobody has fitted Gaia's "
    "epoch astrometry against the predicted 13 mas wobble.")
NOTE_HR1099 = (
    f"{DATE}: kept a star (watch list settled). {TG01}, the only orbit: 'The minimum secondary mass is 0.07 M-sun', "
    "spectral type M in their Table 5, and the word 'brown' is not in the paper; a minimum mass at the limit makes a "
    "star the likelier answer. The role read 'brown dwarf', the MSC's reading of that floor, and now reads 'star'. "
    "DOUBT: the orbit is 'of low quality' (K1 = 1.76 +/- 0.55 km/s), and Gaia DR3 3263936658312134272 (HR 1099 B) "
    "has RUWE 1.03, no non-single-star solution and a constant RV, which argue against it.")
NOTE_GJ7472 = (
    f"{DATE}: kept a star (watch list settled). No paper detects, names or weighs this companion; the only evidence "
    "is Gaia DR3's RUWE 5.31 for B (Gaia DR3 2044289022840065408, no non-single-star solution), the MSC's "
    "'perturbed motion suspected'. RUWE cannot tell a brown dwarf from an M dwarf, so the 0.072 M-sun stays the "
    "typical-companion rule's assumption and, by section 6, a star.")


def pair_mass(rows, x):
    """(mass of node x, {subsystem: (new mass, new offset, primary, secondary, a)}) by the tab's own definitions."""
    sec_of = {r.get("Separation from"): n for n, r in rows.items() if r.get("Separation from")}
    out = {}

    def m(n):
        r = rows[n]
        if r.get("Node type") != "subsystem":
            return float(r["Mass (M-sun)"])
        p = r["Barycentre from"]
        s = sec_of[p]
        mp, ms = m(p), m(s)
        a = float(rows[s]["Separation (AU)"])
        out[n] = (round(mp + ms, 6), round(a * ms / (mp + ms), 6), p, s, a, mp, ms)
        return mp + ms
    m(x)
    return out


def main():
    sy, pl, pn = M.Tab(M.SY, "System / Host"), M.Tab(M.PL, "Star (component)"), M.Tab(M.PN, "Planet")
    rj = M.Tab(RJ, "Planet")
    taken = {r[0] for t in (pn, M.Tab(M.UN, "Planet"), rj) for r in t.v[1:] if r}
    assert BD[4] not in taken and REJECT[1] not in taken, "already on a planet tab or rejected"
    for s in HIERARCHY:
        assert s not in {r[0] for r in sy.v[1:] if r}, f"{s} is on Systems; this script does not update it"

    # ---- GJ 310.1 Bb: the Planets row
    r_bd = pl.find(BD[2])
    spec, orange, notes, facts = M.planet_spec(BD, pl, sy, {BD[2]}, M.marks(pl, [r_bd]))
    spec["Candidate designation (TOI / KOI / other)"] = "HD 72946 B"
    spec["Orbit data source / flags"] += " " + WHY_BD
    spec["Source / discovery reference"] += f"; brown dwarf: {MAIRE}; {BRANDT}; {BOUCHY}"
    # The star tab boxed 0.07 orange with no note, but its row says 'mass published' (MSC), and the dynamical
    # masses below agree with it, so it is carried as published.
    orange.pop("Mass (M-earth)", None)
    notes["Mass (M-earth)"] = (f"Converted from the MSC's 0.07 M-sun x {M.M_EARTH_PER_M_SUN:.0f}. Published "
                               f"dynamical masses: {MAIRE} 72.4 +/- 1.6 MJup; {BRANDT} 72.5 +/- 1.3 MJup.")
    specs = [(BD, spec, orange, notes, facts)]

    # ---- GJ 275.2 Ab: the Rejected row
    rows_275 = {pl.row(r)["Star (component)"]: pl.row(r) for r in pl.rows_of(REJECT[0])}
    ab, aa, host = rows_275["GJ 275.2 Ab"], rows_275["GJ 275.2 Aa"], rows_275["GJ 275.2 Ba"]
    assert ab["Mass (M-sun)"] == 0.0652 and ab["Orbital period (d)"] == 343.335, ab
    elements = "; ".join(f"{k} {ab[k]}" for k in ("Inclination (deg)", "Ascending node (deg)",
                                                  "Argument of periastron (deg)", "Time of periastron (JD)"))
    rj_spec = {
        "Planet": REJECT[1], "Host system (primary star)": REJECT[0], "Distance (ly)": ab["Distance (ly)"],
        "Primary star class": host["Stellar Class"], "Planet-host star": "GJ 275.2 Aa (G 107-69, LHS 229)",
        "Planet-host class": "M4.0 V", "Orbits the primary?": "No",
        "Host luminosity (L-sun)": aa["Luminosity (L-sun)"],
        "Mass (M-earth)": round(0.08 * M.M_EARTH_PER_M_SUN, 1), "Mass (M-Jup)": round(0.08 * M.MJ_PER_M_SUN, 2),
        "Mass type": "Estimate (Harrington et al. 1981, 'about 0.08 M-sun')",
        "Orbital period (d)": ab["Orbital period (d)"], "Semi-major axis (au)": ab["Separation (AU)"],
        "Eccentricity": ab["Orbital eccentricity (e)"],
        "Orbit data source / flags": (
            f"MOVED FROM PLANETLESS 4+ STARS {DATE}: was the star row '{REJECT[1]}' (role 'star', 0.0652 M-sun "
            f"inferred from the published orbit), the unseen companion of GJ 275.2 Aa. Orbit: {ab['Orbit source']}; "
            f"a 0.054\" is ORB6's, from Kepler's law, not the paper's; {elements}. "
            f"Separation source: {ab['Separation source']}."),
        "Confidence tier": "unlikely", "Candidate designation (TOI / KOI / other)": "GJ 275.2 Ab (G 107-69 B)",
        "Source / discovery reference": HRR, "Vetting date / last updated": ISO,
        "Catalogue distance (ly)": ab["Distance (ly)"], "Detection method": "Astrometry (photographic parallax plates)",
        "Rejected because": REJECTED_BECAUSE,
    }
    rj_item = ((M.PL, REJECT[0], REJECT[1], RJ, REJECT[1], "GJ 275.2 Aa", "unlikely"), rj_spec, {}, {}, {})

    # ---- Planetless: removals, collapses, barycentres
    pl_final, pl_pastes, pl_gone, bary = {}, [], [], {}
    for system, removed in (("GJ 310.1", [BD[2]]), (REJECT[0], [REJECT[1]])):
        rows, pastes, gone = M.collapse_plan(pl, system, removed)
        old, new = HIERARCHY[system]
        assert all(r.get("Hierarchy") == old for r in rows.values()), (system, "hierarchy text changed")
        n_stars = sum(1 for r in rows.values() if r.get("Node type") == "star")
        for r in rows.values():
            r["Hierarchy"] = new
            r["Stars in system"] = n_stars
            if system == "GJ 310.1":
                r["Confirmed planets"] = 1
        for top in [n for n, r in rows.items() if r.get("Node type") == "subsystem" and not r.get("Member of")]:
            for x, (mass, off, p, s, a, mp, ms) in pair_mass(rows, top).items():
                old_m, old_off = rows[x]["Mass (M-sun)"], rows[x]["Barycentre offset (AU)"]
                for h, o, nv, how in (("Mass (M-sun)", old_m, mass, f"{p} {mp:g} + {s} {ms:g} M-sun"),
                                      ("Barycentre offset (AU)", old_off, off,
                                       f"a * M_sec / (M_prim + M_sec) = {a} x {ms:g} / ({mp:g} + {ms:g})")):
                    if abs(float(o) - nv) > 1e-6:
                        rows[x][h] = nv
                        bary[(x, h)] = (o, nv, f"{DATE}: was {o}, with {removed[0]} in it; re-derived without it "
                                               f"(settle_watch_list.py): {how}.")
        pl_final[system], pl_pastes, pl_gone = rows, pl_pastes + pastes, pl_gone + gone

    M.check_hierarchies(pl_final, specs)
    sp = sp_lines(spec, pl_gone, bary)
    print(f"Planets row: {spec['Planet']} round {spec['Planet-host star']}: a={facts['a']} P={spec['Orbital period (d)']}"
          f" e={facts['e']} M={facts['mass_sun']} M-sun = {spec['Mass (M-earth)']} M-earth, L={spec['Host luminosity (L-sun)']}"
          f", tier {spec['Confidence tier']}, orange={sorted(orange)}, notes={sorted(notes)}")
    print("  flags:", spec["Orbit data source / flags"])
    print("Rejected row:", json.dumps(rj_spec, ensure_ascii=False)[:1500])
    print("Planetless copyPastes (subsystem -> member):", pl_pastes)
    print("Planetless rows deleted:", pl_gone)
    for system, rows in pl_final.items():
        print(f"  {system}: {[(n, r.get('Member of'), r.get('Separation from'), r.get('Hierarchy level'), r.get('Orbit described')) for n, r in rows.items()]}")
    print("Barycentres:", {f"{x} / {h}": v[:2] for (x, h), v in bary.items()})
    print("HR 1099 Bb role: 'brown dwarf' -> 'star', notes on role and mass; GJ 747.2 Bb: note on mass")
    if PLAN:
        print("\nSources & Provenance:\n" + "\n".join(sp))
        return
    write(pl, specs, rj_item, pl_final, pl_pastes, pl_gone, bary, sp)


def write(pl, specs, rj_item, pl_final, pl_pastes, pl_gone, bary, sp):
    props = {s["properties"]["title"]: s["properties"] for s in
             API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}
    log = {"deleted": {}, "planet_rows": {}}
    for n in pl_gone:
        r = pl.find(n)
        log["deleted"][f"{M.PL} / {n}"] = {
            "row": r, "values": pl.row(r),
            "formulas": {h: pl.formula(r, h) for h in pl.h if str(pl.formula(r, h)).startswith("=")},
            "notes": gs.get_notes(SID, f"{q(M.PL)}!A{r}:{letter(len(pl.h) - 1)}{r}")}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")

    # ---- 1. the Planets row, and the Rejected row (that tab's grid has no spare row: grow it first)
    M.add_rows(M.PN, specs, props, log)
    rj = M.Tab(RJ, "Planet")
    if props[RJ]["gridProperties"]["rowCount"] <= rj.last_data_row():
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
            "sheetId": props[RJ]["sheetId"], "dimension": "ROWS", "length": 1}}]}).execute()
    M.add_rows(RJ, [rj_item], props, log)
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")

    # ---- 2. Planetless: collapse (copyPaste orbit cells), then the final values
    pl = M.Tab(M.PL, "Star (component)")
    sid = props[M.PL]["sheetId"]
    reqs = []
    for x, k in pl_pastes:
        rx, rk = pl.find(x), pl.find(k)
        for h in M.ORBIT_COLS:
            c = pl.col[h]
            reqs.append({"copyPaste": {
                "source": {"sheetId": sid, "startRowIndex": rx - 1, "endRowIndex": rx, "startColumnIndex": c,
                           "endColumnIndex": c + 1},
                "destination": {"sheetId": sid, "startRowIndex": rk - 1, "endRowIndex": rk, "startColumnIndex": c,
                                "endColumnIndex": c + 1}, "pasteType": "PASTE_NORMAL"}})
    API.batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()
    upd, exp, notes = {}, {}, {}
    for system, rows in pl_final.items():
        for n, want in rows.items():
            r = pl.find(n)
            exp[pl.a1("Star (component)", r)] = n
            have = pl.row(r)
            for h in ["Stars in system", "Confirmed planets", "Hierarchy", "Hierarchy level", "Role in system",
                      "Orbit described", "Barycentre from", "Mass (M-sun)", "Barycentre offset (AU)"] + M.ORBIT_COLS:
                if h in pl.col and not str(pl.formula(r, h)).startswith("=") and want.get(h, "") != have.get(h, "") \
                        or (h in M.ORBIT_COLS and any(p[1] == n for p in pl_pastes)):
                    upd[pl.a1(h, r)] = want.get(h, "")
            for (x, h), (_, _, note) in bary.items():
                if x == n:
                    notes[pl.a1(h, r)] = note
        host = pl.find(next(n for n, r in rows.items() if str(r.get("Role in system")).startswith("host")))
        what = (f"{BD[2]} moved to Planets -- a brown dwarf is a planet under the model's rule ({M.RULE})"
                if system == "GJ 310.1" else f"{REJECT[1]} moved to Rejected candidates, probably spurious")
        notes[pl.a1("Stars in system", host)] = (f"{DATE}: {what}; settle_watch_list.py. Hierarchy was "
                                                 f"{HIERARCHY[system][0]}.")
    r_hr, r_gj = pl.find("HR 1099 Bb"), pl.find("GJ 747.2 Bb")
    upd[pl.a1("Role in system", r_hr)] = "star"
    exp[pl.a1("Role in system", r_hr)] = "brown dwarf"
    notes[pl.a1("Role in system", r_hr)] = NOTE_HR1099
    notes[pl.a1("Mass (M-sun)", r_hr)] = NOTE_HR1099
    notes[pl.a1("Mass (M-sun)", r_gj)] = NOTE_GJ7472
    gs.update_cells(SID, upd, expect=exp)
    old = {a1: gs.get_notes(SID, a1).get(a1.split("!")[1], "") for a1 in notes}
    gs.set_note(SID, {a1: (old[a1] + "\n\n" + n) if old[a1] else n for a1, n in notes.items()})

    # ---- 3. deletions, bottom-up, each checked by name
    t = M.Tab(M.PL, "Star (component)")
    for r in sorted((t.find(n) for n in pl_gone), reverse=True):
        assert t.row(r)["Star (component)"] in pl_gone
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"deleteDimension": {"range": {
            "sheetId": sid, "dimension": "ROWS", "startIndex": r - 1, "endIndex": r}}}]}).execute()
    gs.invalidate_cache(SID)
    t = M.Tab(M.PL, "Star (component)")
    assert not set(pl_gone) & {r[1] for r in t.v[1:] if len(r) > 1}, "a Planetless row survived"

    # ---- 4. provenance, rename
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


def sp_lines(spec, pl_gone, bary):
    return [
        "", f"WATCH LIST SETTLED BY THE LITERATURE, {DATE.upper()}",
        "  Four objects at the hydrogen-burning limit that migrate_bds.py (7 Oct 2026) kept as stars on Planetless "
        f"4+ Stars were read against the model's rule ({M.RULE}: a star fuses protium or once did; where the "
        "literature calls an object a brown dwarf, or leaves it undecided, it is a planet). Literature check and "
        "owner's decisions 9 Oct 2026. Writer: data/star_counts/settle_watch_list.py; every deleted row is kept, "
        "values, formulas and notes, in data/star_counts/settle_watch_list_log.json.",
        f"  GJ 310.1 Bb -> Planets within 100 ly (round GJ 310.1 Ba, tier confirmed). {WHY_BD} GJ 310.1 B collapsed "
        "into Ba (Ba took B's orbit cells by copyPaste); hierarchy ((Aa,Ab),(Ba,Bb)),G -> ((Aa,Ab),Ba),G, 5 stars -> "
        "4. Re-derived without the brown dwarf: " + "; ".join(f"{x} {h} {o} -> {n}" for (x, h), (o, n, _) in
                                                             bary.items() if x.startswith("GJ 310.1"))
        + ". Periods inferred from these masses (G round AB) were left as they were, as fix_bd_barycentres.py did.",
        f"  GJ 275.2 Ab -> Rejected candidates (tier unlikely). {REJECTED_BECAUSE} Its tab mass, 0.0652 M-sun, was "
        "inferred and is not the paper's 0.08. GJ 275.2 A collapsed into Aa; hierarchy (Aa,Ab),(Ba,Bb) -> "
        "Aa,(Ba,Bb), 4 stars -> 3. Left alone: Aa's 0.19 M-sun (MSC) against Winters et al. 2021's 0.147 +/- 0.014.",
        f"  HR 1099 Bb stays a star; Role in system 'brown dwarf' -> 'star'. {NOTE_HR1099.split('settled). ', 1)[1]}",
        f"  GJ 747.2 Bb stays a star. {NOTE_GJ7472.split('settled). ', 1)[1]}",
        "  Deleted on Planetless: " + ", ".join(pl_gone) + ". The Known within 100ly tab's typed counts are left for "
        "the pass that re-matches that tab.",
    ]


if __name__ == "__main__":
    main()
