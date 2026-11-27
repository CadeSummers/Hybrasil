# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The 100 Brightest Stars tab, as rows: `list.json` + `research/q*.json` + what the workbook holds.

    python data/brightest_stars/plan.py

Reads the live sheet (never writes it) and writes `plan.json`: headers, rows, the formula
cells, the inferred (orange) and Wikipedia (pink) cells with their notes, and `ranks.md`.

Where a value comes from, in order:
1. The workbook, for a star already on the Systems tab (its row) or the Planetless 4+ Stars
   tab (its host star's row). The motion columns are taken together or not at all.
2. The research agents' files, each value with its citation (`Star data source`).
3. `list.json`: Hipparcos magnitudes and astrometry, SIMBAD class and radial velocity.

Computed here, boxed orange (`INFERRED`): absolute magnitude, visual luminosity, a luminosity
from R and Teff where no paper gives one, and the three ranks.
"""
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))

SYS, PLS, MUL = "Systems within 100 ly", "Planetless 4+ Stars", "Multi-stars within 100 ly"
LY_PER_PC = 3.261563777
MV_SUN = 4.81            # Willmer 2018, ApJS 236, 47 (V, Vega system)
TEFF_SUN = 5772.0        # IAU 2015 Resolution B3
EXTRA = ["Apparent rank", "Apparent magnitude (V)", "Absolute magnitude (M_V)", "Luminosity rank (bolometric)",
         "Luminosity rank (visual)", "Point luminosity (L-sun)", "Visual luminosity (L-sun)", "Extinction A_V",
         "Constellation", "Bayer / Flamsteed designation", "Distance uncertainty (ly)", "Distance source",
         "Variable type", "V range", "Radius (R-sun)", "Magnitude note", "Also on tabs", "Star data source", "Notes"]
MOTION = ["Radial velocity (km/s)", "Proper motion in RA, μα·cos δ (mas/yr)", "Proper motion in Dec, μδ (mas/yr)",
          "Total proper motion, μ (arcsec/yr)", "Space velocity (km/s)", "Galactic longitude l (deg)",
          "Galactic latitude b (deg)", "Motion toward l (deg, heliocentric)", "Motion toward b (deg, heliocentric)",
          "Kinematics source", "Kinematics refs"]
# Research key -> (column, label in Star data source)
RESEARCH = {"mass_msun": ("Host mass (M-sun)", "Mass"), "luminosity_lsun": ("Host luminosity (L-sun)", "Luminosity"),
            "teff_k": ("Effective temp (K)", "Teff"), "radius_rsun": ("Radius (R-sun)", "Radius"),
            "age_gyr": ("Age (Gyr)", "Age"), "feh": ("Metallicity [Fe/H]", "[Fe/H]"),
            "n_stars": ("Stars in system", "Star count"), "variable_type": ("Variable type", "Variability"),
            "v_range": ("V range", "V range"), "av_mag": ("Extinction A_V", "A_V"),
            "system_luminosity_lsun": ("Point luminosity (L-sun)", "Point luminosity")}
# Planetless 4+ Stars column -> this tab's column, for a host star's own facts.
FROM_PLS = {"Mass (M-sun)": "Host mass (M-sun)", "Stellar Class": "Stellar Class", "Effective temp (K)": "Effective temp (K)",
            "Age (Gyr)": "Age (Gyr)", "Metallicity [Fe/H]": "Metallicity [Fe/H]", "Luminosity (L-sun)": "Host luminosity (L-sun)",
            "Distance (ly)": "Distance (ly)", "Stars in system": "Stars in system", "Gaia DR3 source_id": "Gaia DR3 source_id",
            "RA (deg, ICRS)": "RA (deg, ICRS)", "Dec (deg, ICRS)": "Dec (deg, ICRS)", "SIMBAD main_id": "SIMBAD main_id",
            "Existence": "Existence"}


def sort_key(spt):
    """`data/four_plus_stars/build.py`'s: O0 = 0, B0 = 10 ... M0 = 60, plus the subtype."""
    m = re.match(r"^([OBAFGKMLT])(\d+(?:\.\d+)?)?", (spt or "").strip())
    return "" if not m else "OBAFGKMLT".index(m.group(1)) * 10 + (float(m.group(2)) if m.group(2) else 0)


def blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def val(rec, key):
    """A research value and its record, or (None, None)."""
    r = (rec or {}).get(key)
    if isinstance(r, dict) and not blank(r.get("value")):
        return r["value"], r
    return None, None


def tab(api, sid, title, render="UNFORMATTED_VALUE"):
    v = api.values().get(spreadsheetId=sid, range=f"'{title}'!A1:CB1200", valueRenderOption=render).execute()["values"]
    h = [str(x).strip() for x in v[0]]
    return h, [dict(zip(h, list(r) + [""] * (len(h) - len(r)))) for r in v[1:] if r and str(r[0]).strip()]


def main():
    from hybrasil.data import google_sheets as gs
    sid, api = gs.resolve_spreadsheet_id(), gs._sheets_api()
    stars = json.loads((HERE / "list.json").read_text(encoding="utf-8"))
    research = {}
    for f in sorted((HERE / "research").glob("q*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            research[r["rank"]] = r
    # The checking agent's verdicts on luminosities that disagreed with their radius and Teff: its
    # replacements win, and its verdict is kept beside the first researcher's notes.
    check = HERE / "research" / "check.json"
    for c in (json.loads(check.read_text(encoding="utf-8")) if check.exists() else []):
        r = research[c["rank"]]
        for k in ("luminosity_lsun", "radius_rsun", "teff_k"):
            if isinstance(c.get(k), dict) and not blank(c[k].get("value")):
                r[k] = c[k]
        r["notes"] = f"{r.get('notes') or ''} CHECKED: {c.get('verdict', '')}".strip()
    sys_h, sys_rows = tab(api, sid, SYS)
    formulas = dict(zip(*[x for x in (sys_h, api.values().get(
        spreadsheetId=sid, range=f"'{SYS}'!A2:AT2", valueRenderOption="FORMULA").execute()["values"][0])]))
    systems = {r["System / Host"]: r for r in sys_rows}
    _, pls_rows = tab(api, sid, PLS)
    _, mul_rows = tab(api, sid, MUL)
    multi = {r["Star (component)"]: r for r in mul_rows}
    headers = sys_h + EXTRA
    # Formula columns kept from the Systems tab: the luminosity class and the eight solvent bands.
    kept = [h for h in sys_h if h == "Luminosity class" or " band, " in h]
    assert len(kept) == 9 and all(str(formulas[h]).startswith("=") for h in kept), kept

    rows, inferred, wiki, notes, missing = [], {}, [], {}, []
    for s in stars:
        r = dict.fromkeys(headers, "")
        res = research.get(s["rank"], {})
        name = s["name"]
        cite = []
        on_sys = (s["tab_names"].get("Systems") or [None])[0]
        hosts = [p for p in pls_rows if p["Star (component)"] in s["tab_names"].get("Planetless 4+ Stars", [])
                 and str(p["Role in system"]).startswith("host")]
        src = systems.get(on_sys)
        if src:                                              # 1a. a Systems row: every column as it stands
            r.update({h: src[h] for h in sys_h})
            own = multi.get(on_sys)                          # the star's own luminosity, not its planet host's
            if own and not blank(own.get("Luminosity (L-sun)")):
                r["Host luminosity (L-sun)"] = own["Luminosity (L-sun)"]
            cite.append(f"Copied from the Systems tab row '{on_sys}'")
        elif hosts:                                          # 1b. a Planetless host star's row
            p = hosts[0]
            r.update({t: p[f] for f, t in FROM_PLS.items() if not blank(p.get(f))})
            if not blank(p.get("Space velocity (km/s)")):
                r.update({h: p[h] for h in MOTION if h in p})
            members = [x for x in pls_rows if x["System / Host"] == p["System / Host"] and x["Node type"] == "star"]
            r["System stars"] = "\n".join(f"{x['Star (component)']}: {x['Stellar Class']}" for x in members)
            cite.append(f"Host star's facts copied from the Planetless 4+ Stars row '{p['Star (component)']}'")

        # 2. research, where the workbook left a cell empty
        for key, (h, label) in RESEARCH.items():
            v, rec = val(res, key)
            if v is None or not blank(r[h]):
                continue
            # One batch took A_V from a 3-D dust map (Gontcharov & Mosenkov 2018, VizieR II/354), which reads
            # 0.2 to 0.3 mag for stars within 40 pc where dedicated studies give ~0. Left out: it would shift
            # one quarter of the visual ranks against the rest.
            if key == "av_mag" and re.search(r"Gontcharov|II/354", str(rec.get("source", ""))):
                continue
            r[h] = v
            cite.append(f"{label}: {rec.get('source', '')}".strip())
            if rec.get("wikipedia"):
                wiki.append({"name": name, "header": h, "value": v, "url": rec.get("url", ""), "source": rec.get("source", "")})
        comp, crec = val(res, "components")
        if comp and blank(r["System stars"]):
            r["System stars"] = "\n".join(comp)
            cite.append(f"System stars: {crec.get('source', '')}")
            if crec.get("wikipedia"):
                wiki.append({"name": name, "header": "System stars", "value": "; ".join(comp),
                             "url": crec.get("url", ""), "source": crec.get("source", "")})
        dist, drec = val(res, "distance_ly")
        derr, _ = val(res, "distance_err_ly")

        # 3. the list: names, magnitude, astrometry
        nicks, nrec = val(res, "nicknames")
        if nicks and nrec.get("wikipedia"):
            wiki.append({"name": name, "header": "Nicknames", "value": "; ".join(nicks),
                         "url": nrec.get("url", ""), "source": nrec.get("source", "")})
        names = [s["iau"]] + [n.strip() for n in str(r["Nicknames"]).split(";")] + list(nicks or [])
        r["System / Host"] = name
        r["Nicknames"] = "; ".join(dict.fromkeys(n for n in names if n and n != name))
        r["IAU official designation"] = s["iau"]
        if blank(r["Distance (ly)"]):
            r["Distance (ly)"] = round(dist if dist else s["distance_ly"], 2)
            r["Distance uncertainty (ly)"] = round(derr, 2) if dist and derr else (
                "" if dist else round(s["distance_err_ly"], 2))
            r["Distance source"] = drec["source"] if dist else "van Leeuwen 2007, A&A 474, 653 (Hipparcos parallax)"
        else:
            r["Distance source"] = cite[0]
        if blank(r["Stellar Class"]):
            r["Stellar Class"] = s["sp_type"]
        r["Class (sort key)"] = sort_key(r["Stellar Class"])
        if blank(r["Space velocity (km/s)"]):
            d = float(r["Distance (ly)"])
            if dist:                                         # a better distance moves the velocity with it
                from research import velocity
                l, b, speed, ml, mb = velocity(s["ra"], s["dec"], d, s["pmra"], s["pmdec"], s["rv"])
            else:
                l, b, speed, ml, mb = s["l"], s["b"], s["speed"], s["motion_l"], s["motion_b"]
            r.update({"Radial velocity (km/s)": s["rv"], MOTION[1]: s["pmra"], MOTION[2]: s["pmdec"],
                      MOTION[3]: round(math.hypot(s["pmra"], s["pmdec"]) / 1000, 4),
                      "Space velocity (km/s)": round(speed, 2), MOTION[5]: round(l, 4), MOTION[6]: round(b, 4),
                      MOTION[7]: round(ml, 2), MOTION[8]: round(mb, 2),
                      "Kinematics source": "RV: SIMBAD; PM and parallax: Hipparcos (van Leeuwen 2007)",
                      "Kinematics refs": f"RV: {s['rv_bibcode']}; PM: 2007A&A...474..653V"})
        copied = " Copied with its row from another tab." if (src or hosts) and not blank(r["Space velocity (km/s)"]) else ""
        for h, how in ((MOTION[3], "sqrt(pmRA^2 + pmDec^2) / 1000."),
                       (MOTION[4], "heliocentric space velocity from RA/Dec, distance, radial velocity and proper "
                                   "motions (astropy; no LSR correction). Its error follows the distance's."),
                       (MOTION[5], "RA/Dec through the IAU ICRS-to-Galactic rotation (astropy). Exact transform."),
                       (MOTION[6], "RA/Dec through the IAU ICRS-to-Galactic rotation (astropy). Exact transform."),
                       (MOTION[7], "direction of the heliocentric space velocity, galactic longitude."),
                       (MOTION[8], "direction of the heliocentric space velocity, galactic latitude.")):
            if not blank(r[h]):
                inferred[f"{name}|{h}"] = f"INFERRED: {how}{copied}"
        for h, v in (("RA (deg, ICRS)", round(s["ra"], 6)), ("Dec (deg, ICRS)", round(s["dec"], 6)),
                     ("SIMBAD main_id", s["simbad"]), ("Existence", "confirmed: SIMBAD, Hipparcos")):
            if blank(r[h]):
                r[h] = v
        gaia = next((i.replace("Gaia DR3", "").strip() for i in s["ids"] if i.startswith("Gaia DR3")), "")
        if blank(r["Gaia DR3 source_id"]) and gaia:
            r["Gaia DR3 source_id"] = gaia

        # computed: boxed orange, method in the note
        r["Apparent rank"], r["Apparent magnitude (V)"], r["Magnitude note"] = s["rank"], s["v"], s["v_note"]
        r["Constellation"], r["Bayer / Flamsteed designation"] = s["constellation"], s["bayer"]
        r["Also on tabs"] = "; ".join(s["on_tabs"])
        if blank(r["Variable type"]) and s["hip_var"]["type"] in ("", "C"):
            pass
        L, R, T = r["Host luminosity (L-sun)"], r["Radius (R-sun)"], r["Effective temp (K)"]
        if blank(L) and not blank(R) and not blank(T):
            r["Host luminosity (L-sun)"] = round(float(R) ** 2 * (float(T) / TEFF_SUN) ** 4, 4 if float(R) < 3 else 1)
            inferred[f"{name}|Host luminosity (L-sun)"] = (
                f"INFERRED: L = R^2 (Teff/5772)^4 from this row's radius {R} R-sun and Teff {T} K (Stefan-Boltzmann). "
                "No paper's luminosity was found. As good as the radius and Teff: typically 10 to 20%.")
        if not blank(L) and not blank(R) and not blank(T):
            sb = float(R) ** 2 * (float(T) / TEFF_SUN) ** 4
            if abs(sb / float(L) - 1) > 0.2:
                notes[f"{name}|Host luminosity (L-sun)"] = (
                    f"CHECK: R = {R} and Teff = {T} give {sb:.4g} L-sun by Stefan-Boltzmann, "
                    f"{(sb / float(L) - 1) * 100:+.0f}% from this value. The sources differ.")
        if blank(r["Point luminosity (L-sun)"]):
            r["Point luminosity (L-sun)"] = r["Host luminosity (L-sun)"]
        av = r["Extinction A_V"]
        d_pc = float(r["Distance (ly)"]) / LY_PER_PC
        mv = s["v"] - 5 * math.log10(d_pc / 10) - (float(av) if not blank(av) else 0.0)
        r["Absolute magnitude (M_V)"] = round(mv, 2)
        r["Visual luminosity (L-sun)"] = float(f"{10 ** (-0.4 * (mv - MV_SUN)):.4g}")
        how = (f"INFERRED: M_V = V - 5 log10(d / 10 pc) - A_V, with V = {s['v']}, d = {r['Distance (ly)']} ly, "
               + (f"A_V = {av}." if not blank(av) else "A_V taken as 0 (none on file).")
               + " The whole point of light, every star in it.")
        inferred[f"{name}|Absolute magnitude (M_V)"] = how + " Its error is the distance's: 0.1 mag per 5% in distance."
        inferred[f"{name}|Visual luminosity (L-sun)"] = (
            f"INFERRED: 10^(-0.4 (M_V - {MV_SUN})), the Sun's M_V from Willmer 2018. V band only: it leaves out the "
            "ultraviolet of a hot star and the infrared of a cool one.")
        r["Star data source"] = "\n".join(c for c in cite if c)
        r["Notes"] = res.get("notes") or ""
        for h in ("Host mass (M-sun)", "Host luminosity (L-sun)", "Effective temp (K)", "Stars in system", "Stellar Class"):
            if blank(r[h]):
                missing.append((s["rank"], name, h))
        rows.append(r)

    def rank(h, target, reverse):
        have = sorted((x for x in rows if not blank(x[h])), key=lambda x: (-float(x[h]) if reverse else float(x[h])))
        for i, x in enumerate(have, 1):
            x[target] = i
            inferred[f"{x['System / Host']}|{target}"] = (
                f"INFERRED: this row's place among the tab's {len(have)} rows with a value, by {h}. "
                "It moves with the distance: see Distance uncertainty.")
    rank("Point luminosity (L-sun)", "Luminosity rank (bolometric)", True)
    rank("Visual luminosity (L-sun)", "Luminosity rank (visual)", True)

    grid = [[("" if h in kept else r[h]) for h in headers] for r in rows]
    plan = {"headers": headers, "rows": grid, "formula_headers": kept,
            "formulas": {h: formulas[h] for h in kept}, "inferred": inferred, "wikipedia": wiki, "notes": notes,
            "n_systems_columns": len(sys_h)}
    (HERE / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# The 100 brightest stars: three ranks", "",
             "| Apparent | Star | Name | V | Distance (ly) | Point luminosity (L-sun) | Bolometric rank | Visual rank |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['Apparent rank']} | {r['System / Host']} | {r['IAU official designation']} | "
                     f"{r['Apparent magnitude (V)']} | {r['Distance (ly)']} | {r['Point luminosity (L-sun)']} | "
                     f"{r['Luminosity rank (bolometric)']} | {r['Luminosity rank (visual)']} |")
    (HERE / "ranks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    far = max(rows, key=lambda x: float(x["Distance (ly)"]))
    print(f"{len(rows)} rows x {len(headers)} columns; research for {len(research)} stars; "
          f"{len(inferred)} inferred cells; {len(wiki)} Wikipedia cells; {len(notes)} check notes")
    print("farthest:", far["System / Host"], far["Distance (ly)"], "ly")
    print("missing:", len(missing), missing[:40])


if __name__ == "__main__":
    main()
