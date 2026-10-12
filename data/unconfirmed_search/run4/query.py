# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run 4: catalogue values for the Systems tab's blank mass, Teff, luminosity and class cells.

Reads systems_gaps.json (rows with a gap), queries the NASA Exoplanet Archive, Gaia DR3, TIC v8.2 and SIMBAD,
and writes candidates.json: every catalogue's value for every gap, with the reference. Read-only.
"""
import csv
import io
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "systems_gaps.json").read_text(encoding="utf-8"))


def tap(url, query, extra):
    key = extra.pop("_key")
    p = dict(extra)
    p[key] = query
    for attempt in range(4):
        try:
            body = urllib.request.urlopen(url + "?" + urllib.parse.urlencode(p), timeout=180).read().decode()
            if body.lstrip().startswith("<"):
                raise RuntimeError(body[:400])
            return list(csv.DictReader(io.StringIO(body)))
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            print("retry", e)
            time.sleep(5)


def nasa(q):
    return tap("https://exoplanetarchive.ipac.caltech.edu/TAP/sync", q, {"_key": "query", "format": "csv"})


def gaia(q):
    return tap("https://gea.esac.esa.int/tap-server/tap/sync", q,
               {"_key": "QUERY", "REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv"})


def vizier(q):
    return tap("https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync", q,
               {"_key": "query", "request": "doQuery", "lang": "adql", "format": "csv"})


def simbad(q):
    return tap("https://simbad.cds.unistra.fr/simbad/sim-tap/sync", q,
               {"_key": "query", "request": "doQuery", "lang": "adql", "format": "csv"})


def chunks(xs, n=40):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def sq(s):
    return "'" + s.replace("'", "''") + "'"


out = {r["name"]: {"row": r["row"], "missing": r["missing"], "class": r["class"], "gaia": r["gaia"],
                   "nasa": None, "gaia_ap": None, "tic": None, "simbad": None} for r in rows}

# 1. NASA pscomppars: by host name (Systems name and planet-host star) and by Gaia DR3 id.
names = sorted({n for r in rows for n in (r["name"], r["planet_host"]) if n})
by_gaia = {r["gaia"]: r["name"] for r in rows if r["gaia"]}
cols = ("hostname,gaia_dr3_id,st_spectype,st_teff,st_teff_reflink,st_mass,st_mass_reflink,st_lum,st_lum_reflink,"
        "st_rad,st_rad_reflink")
found = []
for ch in chunks(names):
    found += nasa(f"select distinct {cols} from pscomppars where hostname in ({','.join(sq(n) for n in ch)})")
for ch in chunks(list(by_gaia)):
    found += nasa(f"select distinct {cols} from pscomppars where gaia_dr3_id in ({','.join(sq('Gaia DR3 ' + g) for g in ch)})")
for f in found:
    g = (f.get("gaia_dr3_id") or "").replace("Gaia DR3 ", "")
    for r in rows:
        if f["hostname"] in (r["name"], r["planet_host"]) or (g and g == r["gaia"]):
            out[r["name"]]["nasa"] = f

# 2. Gaia DR3 astrophysical parameters, and the DR2 ids TIC is keyed on.
ids = [g for g in by_gaia if g]
ap, dr2 = [], []
for ch in chunks(ids, 80):
    ap += gaia("select source_id, teff_gspphot, teff_gspspec, mass_flame, lum_flame, radius_flame, flags_flame "
               f"from gaiadr3.astrophysical_parameters where source_id in ({','.join(ch)})")
    dr2 += gaia("select dr2_source_id, dr3_source_id, angular_distance from gaiadr3.dr2_neighbourhood "
                f"where dr3_source_id in ({','.join(ch)})")
for a in ap:
    out[by_gaia[a["source_id"]]]["gaia_ap"] = a
dr2map = {}
for d in dr2:
    best = dr2map.get(d["dr3_source_id"])
    if best is None or float(d["angular_distance"]) < float(best["angular_distance"]):
        dr2map[d["dr3_source_id"]] = d

# 3. TIC v8.2 (VizieR IV/39/tic82), keyed on the Gaia DR2 id.
tic = []
g2 = [d["dr2_source_id"] for d in dr2map.values()]
for ch in chunks(g2, 60):
    tic += vizier('select TIC, GAIA, Teff, s_Teff, Mass, s_Mass, Rad, Lum, s_Lum, LClass, r_Teff '
                  f'from "IV/39/tic82" where GAIA in ({",".join(ch)})')
rev = {d["dr2_source_id"]: d["dr3_source_id"] for d in dr2map.values()}
for t in tic:
    g3 = rev.get(t["GAIA"])
    if g3:
        out[by_gaia[g3]]["tic"] = t

# 4. SIMBAD spectral types for rows with no class.
for r in rows:
    if "H" in r["missing"]:
        res = simbad(f"select b.main_id, b.sp_type, b.sp_bibcode from ident i join basic b on b.oid=i.oidref "
                     f"where i.id = {sq(r['name'])}")
        if not res and r["gaia"]:
            res = simbad(f"select b.main_id, b.sp_type, b.sp_bibcode from ident i join basic b on b.oid=i.oidref "
                         f"where i.id = {sq('Gaia DR3 ' + r['gaia'])}")
        out[r["name"]]["simbad"] = res[0] if res else None

(HERE / "candidates.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print("rows", len(out), "| nasa", sum(1 for v in out.values() if v["nasa"]), "| gaia_ap", sum(1 for v in out.values() if v["gaia_ap"]),
      "| tic", sum(1 for v in out.values() if v["tic"]), "| simbad", sum(1 for v in out.values() if v["simbad"]))
