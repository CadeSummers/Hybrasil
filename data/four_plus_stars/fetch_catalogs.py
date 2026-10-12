# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Download the catalogs research.py checks "Planetless 4+ Stars" against, into cat/.

    python fetch_catalogs.py          ORB6, SB9 and Gaia DR3 non-single-star solutions for every system on the tab

  cat/orb6orbits.txt        ORB6, www.astro.gsu.edu/wds/orb6 (the version research.py used: 2026-07-09)
  cat/sb9.tar.gz, cat/sb9/  SB9 public release, sb9.astro.ulb.ac.be (2024-06-21); unpacked alongside
  cat/gaia_nss.json         Gaia DR3 NSS solutions (two-body, acceleration, non-linear) within 72" of any component
                            of a tab system, parallax within 20% of the system's, from the ESA Gaia archive
  cat/gaia_nss_orbits.json  the full nss_two_body_orbit rows of those, with the system each belongs to

Reads the committed snapshot in data/ for positions, so it needs no Google credential. The archive TAP service is
slow; the cone searches take ~20 minutes.
"""
import glob
import json
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAT = HERE / "cat"
ROOT = HERE.parents[1]
GAIA = "https://gea.esac.esa.int/tap-server/tap/sync"
TABLES = {
    "nss_two_body_orbit": "n.nss_solution_type, n.period, n.eccentricity, n.a_thiele_innes",
    "nss_acceleration_astro": "n.nss_solution_type, n.significance",
    "nss_non_linear_spectro": "n.nss_solution_type",
}


def tap(q):
    url = GAIA + "?" + urllib.parse.urlencode({"request": "doQuery", "lang": "adql", "format": "json", "query": q})
    r = json.load(urllib.request.urlopen(url, timeout=600))
    cols = [c["name"] for c in r["metadata"]]
    return [dict(zip(cols, row)) for row in r["data"]]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    CAT.mkdir(exist_ok=True)
    urllib.request.urlretrieve("https://www.astro.gsu.edu/wds/orb6/orb6orbits.txt", CAT / "orb6orbits.txt")
    urllib.request.urlretrieve("https://sb9.astro.ulb.ac.be/SB9public.tar.gz", CAT / "sb9.tar.gz")
    with tarfile.open(CAT / "sb9.tar.gz") as t:
        t.extractall(CAT / "sb9", filter="data")

    import openpyxl
    snap = sorted(glob.glob(str(ROOT / "data" / "hybrasil-*.xlsx")))[-1]
    ws = openpyxl.load_workbook(snap, read_only=True, data_only=True)["Planetless 4+ Stars"]
    it = ws.iter_rows(values_only=True)
    head = list(next(it))
    by = {}
    for r in it:
        d = dict(zip(head, r))
        if d.get("System / Host"):
            by.setdefault(d["System / Host"], []).append(d)
    found = {}
    for s, rs in by.items():
        plx = 3261.56 / num(rs[0]["Distance (ly)"])
        pts = {(round(num(r["RA (deg, ICRS)"]), 4), round(num(r["Dec (deg, ICRS)"]), 4)) for r in rs}
        circles = " OR ".join(f"1=CONTAINS(POINT(g.ra, g.dec), CIRCLE({ra}, {de}, 0.02))" for ra, de in pts)
        for t, cols in TABLES.items():
            for x in tap(f"SELECT g.source_id, g.ra, g.dec, g.parallax, g.phot_g_mean_mag, {cols} "
                         f"FROM gaiadr3.{t} AS n JOIN gaiadr3.gaia_source AS g ON g.source_id = n.source_id "
                         f"WHERE ({circles}) AND g.parallax BETWEEN {plx * 0.8} AND {plx * 1.2}"):
                found.setdefault(s, []).append({"table": t, **x})
        print(s, len(found.get(s, [])), flush=True)
    (CAT / "gaia_nss.json").write_text(json.dumps(found, indent=1))
    two = {x["source_id"]: s for s, xs in found.items() for x in xs if x["table"] == "nss_two_body_orbit"}
    rows = tap(f"SELECT * FROM gaiadr3.nss_two_body_orbit WHERE source_id IN ({','.join(map(str, two))})")
    (CAT / "gaia_nss_orbits.json").write_text(json.dumps(
        {"rows": rows, "systems": {str(k): [v, None] for k, v in two.items()}}, indent=1))
    print(len(found), "systems with a Gaia NSS solution;", len(rows), "two-body rows")


if __name__ == "__main__":
    main()
