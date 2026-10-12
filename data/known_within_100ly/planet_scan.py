# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Which Known-within-100ly systems host a confirmed planet the workbook does not record?

    python data/known_within_100ly/planet_scan.py

Read-only. One NASA Exoplanet Archive query (pscomppars, sy_dist < 31 pc) against the newest snapshot in data/.
A planet is tied to a Known row by Gaia DR3 id, else by host name, else by position within 30" with distances
within 15%. It counts as recorded when any of its host's names -- the archive host, HD and HIP names, every Known
row with that Gaia id and its IAU nickname -- carries a planet with the same letter on Planets, Unconfirmed or
Rejected candidates, so "Barnard b" is found as "Barnard's star b" and "pi Men c" as "HD 39091 c".

Writes planet_scan.csv beside this file (every planet, flagged ones first) and prints the flagged ones.

First run, 6 Oct 2026 (hy-brasil-20261006-1909): of 541 planets, only four companions of brown dwarfs were on no
planet tab -- WISEP J1217+1626 A b (22 MJ), CWISEP J1935-1546 b (15.5 MJ), DENIS-P J0823-4912 b (28.5 MJ) and
CFBDSIR J1458+1013 b (10.5 MJ, no Known row). Every Known row reading 0 planets despite an archive planet had
it on Rejected or Unconfirmed on purpose.
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
OUT = HERE / "planet_scan.csv"
PC_LY = 3.26156
TABS = ("Planets within 100 ly", "Unconfirmed within 100 ly", "Rejected candidates")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower().replace("gliese", "gj"))


def rows(ws):
    it = ws.iter_rows(values_only=True)
    hdr = next(it)
    return [dict(zip(hdr, r)) for r in it if r and r[0] not in (None, "")]


def archive():
    q = ("select pl_name,hostname,hd_name,hip_name,gaia_dr3_id,ra,dec,sy_dist,discoverymethod,disc_year,pl_bmassj "
         "from pscomppars where sy_dist<31")
    url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?" + urllib.parse.urlencode({"query": q, "format": "csv"})
    return list(csv.DictReader(io.StringIO(urllib.request.urlopen(url, timeout=300).read().decode())))


def main():
    wb = openpyxl.load_workbook(SNAP, read_only=True, data_only=True)
    known = rows(wb["Known within 100ly"])
    by_gaia = collections.defaultdict(list)
    for r in known:
        if r.get("Gaia DR3 source_id"):
            by_gaia[str(r["Gaia DR3 source_id"]).split(".")[0]].append(r)
    by_name = {norm(r["System / Host"]): r for r in known}
    pos = [r for r in known if isinstance(r.get("RA (deg, ICRS)"), (int, float))]

    recorded = {}                      # (host, planet letter) -> (tab, planet name as the tab writes it)
    by_full = {}                       # whole planet name -> same
    by_toi = {}                        # TOI number -> same: the archive names some planets "TOI-4527.01"
    for t in TABS:
        for r in rows(wb[t]):
            name = str(r["Planet"])
            by_full[norm(name)] = (t.split()[0], name)
            for n in re.findall(r"TOI[- ]?(\d+)", name):
                by_toi[n] = (t.split()[0], name)
            letter = name.split()[-1].lower()
            for h in (r.get("Planet-host star"), r.get("Host system (primary star)"), name.rsplit(" ", 1)[0]):
                if h:
                    recorded[(norm(h), letter)] = (t.split()[0], name)

    def by_position(ra, dec, d_ly):
        best = None
        for r in pos:
            dd = abs(r["Dec (deg, ICRS)"] - dec)
            if dd > 0.01:
                continue
            sep = 3600 * math.hypot((r["RA (deg, ICRS)"] - ra) * math.cos(math.radians(dec)), dd)
            dist = r.get("Distance (ly)")
            if sep < 30 and (not isinstance(dist, (int, float)) or abs(dist - d_ly) / d_ly < 0.15):
                if best is None or sep < best[0]:
                    best = (sep, r)
        return best[1] if best else None

    arch = archive()
    out = []
    for p in arch:
        gid = p["gaia_dr3_id"].split()[-1] if p["gaia_dr3_id"] else ""
        d_ly = float(p["sy_dist"]) * PC_LY
        twins = by_gaia.get(gid, [])
        # where a star has two Known rows, prefer the plotted one
        how, r = "gaia", next((k for k in twins if k.get("Plotted")), twins[0] if twins else None)
        if r is None:
            how, r = "name", by_name.get(norm(p["hostname"]))
        if r is None and p["ra"]:
            how, r = "position", by_position(float(p["ra"]), float(p["dec"]), d_ly)
        if r is None:
            how = "none"
        letter = p["pl_name"].split()[-1].lower()
        hosts = {p["hostname"], p["hd_name"], p["hip_name"]} | {k["System / Host"] for k in twins + ([r] if r else [])} \
            | {k.get("Nickname (IAU)") for k in twins}
        hit = by_full.get(norm(p["pl_name"])) \
            or next((recorded[(norm(h), letter)] for h in hosts if h and (norm(h), letter) in recorded), None)
        toi = re.fullmatch(r"TOI-(\d+)\.\d+", p["pl_name"])
        if not hit and toi:
            hit = by_toi.get(toi.group(1))
        cp = r.get("Confirmed planets") if r else None
        flag = ("NOT ON ANY PLANET TAB" if not hit else "") \
            + ("; NO KNOWN ROW" if not r and d_ly <= 100 else "") \
            + ("; KNOWN ROW SAYS 0 BUT PLANET IS ON PLANETS" if r and not cp and hit and hit[0] == "Planets" else "")
        out.append({
            "planet": p["pl_name"], "archive_host": p["hostname"], "dist_ly": round(d_ly, 2),
            "mass_mjup": round(float(p["pl_bmassj"]), 4) if p["pl_bmassj"] else "", "method": p["discoverymethod"], "year": p["disc_year"], "match": how,
            "known_row": r["System / Host"] if r else "", "known_plotted": r.get("Plotted") if r else "",
            "known_confirmed_planets": cp, "on_tab": f"{hit[0]}: {hit[1]}" if hit else "", "flag": flag.strip("; "),
        })

    out.sort(key=lambda x: (not x["flag"], x["dist_ly"]))
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    flagged = [o for o in out if o["flag"]]
    print(f"snapshot {SNAP.name}; archive planets <31 pc: {len(arch)}; Known rows: {len(known)}")
    print("match:", dict(collections.Counter(o["match"] for o in out)))
    print(f"flagged: {len(flagged)}")
    for o in flagged:
        print(f"  {o['dist_ly']:6.2f} ly  {o['planet']:<30} {o['mass_mjup'] or '?':>6} MJ  "
              f"known={o['known_row'] or '-':<24} {o['flag']}")
    print("csv:", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
