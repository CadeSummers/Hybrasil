# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Gaia DR3 co-moving companions of every Systems-tab host, by El-Badry, Rix & Heintz 2021 (MNRAS 506, 2269) cuts."""
import json, math, sys
import numpy as np
from astropy.table import Table
import openpyxl

SP = sys.argv[1]
g = Table.read(f"{SP}/gaia_plx28.csv", format="ascii.csv")
for a, b in (("Source", "source_id"), ("RA_ICRS", "ra"), ("DE_ICRS", "dec"), ("Plx", "parallax"), ("e_Plx", "parallax_error"),
             ("pmRA", "pmra"), ("e_pmRA", "pmra_error"), ("pmDE", "pmdec"), ("e_pmDE", "pmdec_error"), ("Gmag", "phot_g_mean_mag"),
             ("BP-RP", "bp_rp"), ("RUWE", "ruwe"), ("RV", "radial_velocity")):
    g.rename_column(a, b)
g = g[(g["parallax"] / g["parallax_error"] > 5)]
ra, de = np.radians(np.array(g["ra"], float)), np.radians(np.array(g["dec"], float))
sid = np.array(g["source_id"], dtype=np.int64)
idx = {int(s): i for i, s in enumerate(sid)}
hosts = json.load(open(f"{SP}/hosts.json", encoding="utf-8"))

wb = openpyxl.load_workbook("data/hy-brasil-20261009-0929.xlsx", read_only=True, data_only=True)
rows = list(wb["Multi-stars within 100 ly"].iter_rows(values_only=True)); c = {x: i for i, x in enumerate(rows[0])}
known = {}                                   # host -> Gaia ids already on Multi-stars
for r in rows[1:]:
    if r[0]:
        known.setdefault(r[0], set()).add(str(r[c["Gaia DR3 source_id"]] or "").strip())

def f(i, k):
    v = g[k][i]
    return None if np.ma.is_masked(v) else float(v)

out = []
for h in hosts:
    if not h["sid"].isdigit() or int(h["sid"]) not in idx:
        continue
    i = idx[int(h["sid"])]
    plx = f(i, "parallax")
    cosd = np.sin(de[i]) * np.sin(de) + np.cos(de[i]) * np.cos(de) * np.cos(ra - ra[i])
    theta = np.degrees(np.arccos(np.clip(cosd, -1, 1))) * 3600
    s_au = theta * 1000 / plx
    for j in np.where((s_au <= 206265) & (sid != sid[i]))[0]:
        th = float(theta[j])
        dplx = abs(plx - f(j, "parallax"))
        sig = math.hypot(f(i, "parallax_error"), f(j, "parallax_error"))
        if dplx > (6 if th < 4 else 3) * sig:
            continue
        if None in (f(i, "pmra"), f(j, "pmra")):
            continue
        dmu = math.hypot(f(i, "pmra") - f(j, "pmra"), f(i, "pmdec") - f(j, "pmdec"))
        smu = math.hypot(math.hypot(f(i, "pmra_error"), f(j, "pmra_error")), math.hypot(f(i, "pmdec_error"), f(j, "pmdec_error")))
        dmu_orb = 0.44 * plx ** 1.5 * th ** -0.5
        if dmu > dmu_orb + 2 * smu:
            continue
        out.append(dict(host=h["host"], host_sid=h["sid"], stars=h["stars"], planets=h["planets"], comp_sid=str(int(sid[j])),
                        sep_arcsec=round(th, 2), sep_au=round(float(s_au[j])), G=round(f(j, "phot_g_mean_mag"), 2),
                        bp_rp=None if f(j, "bp_rp") is None else round(f(j, "bp_rp"), 2), ruwe=round(f(j, "ruwe") or 0, 2),
                        dmu=round(dmu, 2), dmu_orb=round(dmu_orb, 2), dplx=round(dplx, 3),
                        on_multistars=str(int(sid[j])) in known.get(h["host"], set())))
json.dump(out, open(f"{SP}/gaia_binaries.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
from collections import defaultdict
by = defaultdict(list)
for o in out:
    by[o["host"]].append(o)
miss = {k: v for k, v in by.items() if len(v) + 1 > (v[0]["stars"] or 1)}
print(f"{len(out)} co-moving companions for {len(by)} hosts; {len(miss)} hosts whose Stars in system is below 1 + companions")
for k, v in sorted(miss.items()):
    print(f"  {k:24} tab {int(v[0]['stars'] or 0)}  planets {int(v[0]['planets'])}  " +
          "; ".join(f"{o['comp_sid']} {o['sep_arcsec']}\" {o['sep_au']}au G{o['G']} bprp{o['bp_rp']}{' [on MS]' if o['on_multistars'] else ''}" for o in v))
