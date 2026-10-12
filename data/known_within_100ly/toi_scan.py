# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Which open TESS candidates near the Sun does the workbook not record?

    python data/known_within_100ly/toi_scan.py

Read-only. One query of the NASA Exoplanet Archive's toi table: TFOPWG disposition PC or APC, within 31 pc,
against the newest snapshot in data/. A TOI is tied to a Known row by position -- its TIC (J2000) position carried
to Gaia's 2016.0 by its own proper motion, within 10" (or 60" with distances within 15%). It counts as recorded
when its TOI number appears in any cell of Planets, Unconfirmed or Rejected candidates, or when a planet on those
tabs around the same Known star has its period to within 1% (a TOI confirmed under its published name, as
TOI-7032.01 is GJ 523 b).

Writes toi_scan.csv beside this file (unrecorded candidates first) and prints every candidate.

First run, 6 Oct 2026 (hy-brasil-20261006-1909): 24 open candidates, 22 recorded by TOI number; TOI-7032.01 was
GJ 523 b, and TOI-253.01 is at 100.6 ly, just outside the tab.
"""
import collections
import csv
import io
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SNAP = sorted(ROOT.glob("data/hybrasil-*.xlsx"))[-1]
OUT = HERE / "toi_scan.csv"
PC_LY = 3.26156
TABS = ("Planets within 100 ly", "Unconfirmed within 100 ly", "Rejected candidates")


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def main():
    wb = openpyxl.load_workbook(SNAP, read_only=True, data_only=True)

    def rows(name):
        it = wb[name].iter_rows(values_only=True)
        hdr = next(it)
        return [dict(zip(hdr, r)) for r in it if r and r[0] not in (None, "")]

    known = rows("Known within 100ly")
    pos = [r for r in known if isinstance(r.get("RA (deg, ICRS)"), (int, float))]
    mentions = collections.defaultdict(list)       # TOI number -> ["Tab: planet"]
    periods = collections.defaultdict(list)        # host -> [(period, "Tab: planet")]
    for t in TABS:
        for r in rows(t):
            label = f"{t.split()[0]}: {r['Planet']}"
            text = " ".join(str(v) for v in r.values() if v is not None)
            for n in set(re.findall(r"TOI[- ]?(\d+)", text)):
                mentions[n].append(label)
            if num(r.get("Orbital period (d)")) > 0:
                for h in {r.get("Planet-host star"), r.get("Host system (primary star)")} - {None, ""}:
                    periods[norm(h)].append((num(r["Orbital period (d)"]), label))

    q = ("select toi,tid,tfopwg_disp,ra,dec,st_pmra,st_pmdec,st_dist,pl_orbper,pl_rade,pl_eqt,toi_created "
         "from toi where st_dist<31 and tfopwg_disp in ('PC','APC')")
    url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?" + urllib.parse.urlencode({"query": q, "format": "csv"})
    tois = list(csv.DictReader(io.StringIO(urllib.request.urlopen(url, timeout=300).read().decode())))

    def match(t):
        dec0 = num(t["dec"])
        ra = num(t["ra"]) + 16 * num(t["st_pmra"]) / 3.6e6 / math.cos(math.radians(dec0))
        dec = dec0 + 16 * num(t["st_pmdec"]) / 3.6e6
        d_ly = num(t["st_dist"]) * PC_LY
        best = None
        for r in pos:
            dd = abs(r["Dec (deg, ICRS)"] - dec)
            if dd > 0.02:
                continue
            sep = 3600 * math.hypot((r["RA (deg, ICRS)"] - ra) * math.cos(math.radians(dec)), dd)
            dist = r.get("Distance (ly)")
            ok_d = isinstance(dist, (int, float)) and d_ly and abs(dist - d_ly) / d_ly < 0.15
            if (sep < 10 or (sep < 60 and ok_d)) and (best is None or sep < best[0]):
                best = (sep, r)
        return best

    out = []
    for t in tois:
        m = match(t)
        r = m[1] if m else None
        on = mentions.get(t["toi"].split(".")[0], [])
        p = num(t["pl_orbper"])
        if not on and r and p:
            on = [f"{label} (same period)" for per, label in periods.get(norm(r["System / Host"]), [])
                  if abs(per - p) / p < 0.01]
        out.append({
            "toi": t["toi"], "disp": t["tfopwg_disp"], "tic": t["tid"], "dist_ly": round(num(t["st_dist"]) * PC_LY, 2),
            "period_d": round(p, 3), "radius_re": round(num(t["pl_rade"]), 2), "teq_k": t["pl_eqt"],
            "created": t["toi_created"][:10], "known_row": r["System / Host"] if r else "",
            "sep_arcsec": round(m[0], 1) if m else "", "known_plotted": r.get("Plotted") if r else "",
            "known_confirmed": r.get("Confirmed planets") if r else "", "on_tabs": "; ".join(on),
        })

    out.sort(key=lambda o: (bool(o["on_tabs"]), o["dist_ly"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    print(f"snapshot {SNAP.name}; open TOIs (PC/APC) <31 pc: {len(tois)}; "
          f"recorded: {sum(bool(o['on_tabs']) for o in out)}; matched to Known: {sum(bool(o['known_row']) for o in out)}")
    for o in out:
        print(f"  {o['dist_ly']:6.2f} ly  TOI-{o['toi']:<8} {o['disp']:<3} P={o['period_d']:<9} R={o['radius_re']:<5} "
              f"known={o['known_row'] or '-':<20} {o['on_tabs'] or 'NOT RECORDED'}")
    print("csv:", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
