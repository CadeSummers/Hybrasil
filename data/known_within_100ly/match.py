# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Match 'Nearby stars within 100 light years.xlsx' to the stars the workbook plots.

    python match.py        writes match.json beside this file and prints the counts

A plotted star is a Systems row (a system's host) or a Multi-stars row (any star drawn in a system).
Matching, in order of trust:
  1. Gaia DR3 source_id, exact.
  2. Position: the row's RA/Dec (SIMBAD ICRS, J2000 epoch) carried to Gaia's J2016.0 with the row's own
     proper motion, within 3 arcsec of a file entry and 10% in distance. Systems rows only; Multi-stars has
     no RA/Dec.
  3. Name: 'GJ n' + component, against the file's 'Other ID' + 'Component'.
A file entry takes one plotted star at most; a Systems row wins over a Multi-stars row for the same entry.
"""
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from hybrasil.data import google_sheets as gs  # noqa: E402

SOURCE = ROOT / "data" / "Nearby stars within 100 light years.xlsx"
SY, MS = "Systems within 100 ly", "Multi-stars within 100 ly"


def load_file():
    import openpyxl
    wb = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    rows = list(wb["Nearby stars"].iter_rows(values_only=True))
    wb.close()
    hdr_i = next(i for i, r in enumerate(rows) if r and r[0] == "Distance (ly)")
    hdr = rows[hdr_i]
    out = []
    for r in rows[hdr_i + 1:]:
        if not r or all(c is None for c in r):
            continue
        out.append(dict(zip(hdr, r)))
    return out


def norm(s):
    s = str(s or "").strip().lower()
    s = re.sub(r"^(gliese|gl)\s*", "gj ", s)
    return re.sub(r"\s+", " ", s)


def gaia_id(v):
    s = str(v or "").strip()
    m = re.search(r"(\d{6,})", s)
    return m.group(1) if m else ""


def table(tab, wb):
    rows = wb["tabs"][tab]
    hdr = rows[0]
    return hdr, [dict(zip(hdr, r)) for r in rows[1:] if r and str(r[0]).strip()]


def sep_arcsec(ra1, de1, ra2, de2):
    d = math.radians
    c = (math.sin(d(de1)) * math.sin(d(de2)) + math.cos(d(de1)) * math.cos(d(de2)) * math.cos(d(ra1 - ra2)))
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 3600


def main():
    wb = gs.get_workbook(refresh=True)
    sh, systems = table(SY, wb)
    mh, stars = table(MS, wb)
    entries = load_file()
    by_gaia = {}
    for i, e in enumerate(entries):
        g = gaia_id(e["Catalog ID"]) if str(e["Catalog ID"]).startswith("Gaia") else ""
        if g:
            by_gaia[g] = i
    names = {}
    for i, e in enumerate(entries):
        if e.get("Other ID"):
            base = norm(e["Other ID"])
            names.setdefault(base + (" " + e["Component"].lower() if e.get("Component") else ""), []).append(i)

    match = {}          # entry index -> {"tab", "name", "how"}
    unmatched = {"systems": [], "stars": []}

    def take(i, tab, name, how):
        if i in match:
            if match[i]["tab"] == SY or tab != SY:
                return False
        match[i] = {"tab": tab, "name": name, "how": how}
        return True

    # Systems rows
    for s in systems:
        name = s["System / Host"]
        g = gaia_id(s.get("Gaia DR3 source_id"))
        if g and g in by_gaia:
            take(by_gaia[g], SY, name, "gaia")
            continue
        ra, de = s.get("RA (deg, ICRS)"), s.get("Dec (deg, ICRS)")
        hit = None
        if isinstance(ra, (int, float)) and isinstance(de, (int, float)):
            pmra = s.get("Proper motion in RA, μα·cos δ (mas/yr)") or 0
            pmde = s.get("Proper motion in Dec, μδ (mas/yr)") or 0
            pmra = pmra if isinstance(pmra, (int, float)) else 0
            pmde = pmde if isinstance(pmde, (int, float)) else 0
            ra16 = ra + 16 * pmra / 3.6e6 / max(math.cos(math.radians(de)), 1e-6)
            de16 = de + 16 * pmde / 3.6e6
            dist = s.get("Distance (ly)")
            best = None
            for i, e in enumerate(entries):
                if e["RA (deg)"] is None or abs(e["Dec (deg)"] - de16) > 0.01:
                    continue
                d = sep_arcsec(ra16, de16, e["RA (deg)"], e["Dec (deg)"])
                if d < 3 and (not isinstance(dist, (int, float)) or abs(e["Distance (ly)"] - dist) < 0.1 * dist):
                    if best is None or d < best[0]:
                        best = (d, i)
            hit = best and best[1]
        if hit is not None:
            take(hit, SY, name, "position")
            continue
        cand = names.get(norm(name), [])
        if len(cand) == 1:
            take(cand[0], SY, name, "name")
            continue
        unmatched["systems"].append(name)

    # Multi-stars rows
    for s in stars:
        name = s["Star (component)"]
        g = gaia_id(s.get("Gaia DR3 source_id"))
        if g and g in by_gaia:
            i = by_gaia[g]
            if i in match and match[i]["tab"] == SY:
                continue            # the host's own row already covers this source
            take(i, MS, name, "gaia")
            continue
        cand = names.get(norm(name), [])
        if len(cand) == 1 and cand[0] not in match:
            take(cand[0], MS, name, "name")
            continue
        unmatched["stars"].append(name)

    # 4. SIMBAD identifiers (simbad_aliases.json, astroquery Simbad.query_objectids, 28 Sep 2026) for what is
    #    left: a Gaia DR3 id, a CNS5 id, or a GJ name the file carries.
    aliases = json.loads((HERE / "simbad_aliases.json").read_text(encoding="utf-8"))
    by_cns5 = {str(e["Catalog ID"]): i for i, e in enumerate(entries) if str(e["Catalog ID"]).startswith("CNS5")}
    sun = next(i for i, e in enumerate(entries) if e["Catalog ID"] == "Sun")
    for kind, tab in (("systems", SY), ("stars", MS)):
        left = []
        for name in unmatched[kind]:
            if name == "Sun":
                take(sun, tab, name, "name")
                continue
            ids = aliases.get(name) or []
            hit = next((by_gaia[gaia_id(a)] for a in ids if a.startswith("Gaia DR3") and gaia_id(a) in by_gaia), None)
            if hit is None:
                hit = next((by_cns5[a] for a in ids if a in by_cns5), None)
            if hit is None:
                # 'GJ 667 A' may be on the file only as the unresolved 'GJ 667 AB' (CNS5); the primary takes it.
                gj = [norm(a) + tail for a in ids if a.startswith("GJ ")
                      for tail in (("", "b", "bc") if a.endswith(" A") else ("",))]
                hit = next((names[k][0] for k in gj if len(names.get(k, [])) == 1), None)
            if hit is not None and (hit not in match or (tab == SY and match[hit]["tab"] != SY)):
                take(hit, tab, name, "simbad")
            else:
                left.append(name)
        unmatched[kind] = left
    # A star named on both tabs (a system's host) is plotted once; drop it from the stars list if its
    # system row found the entry.
    systems_found = {v["name"] for v in match.values() if v["tab"] == SY}
    unmatched["stars"] = [n for n in unmatched["stars"] if n not in systems_found]

    out = {"entries": len(entries), "match": {str(k): v for k, v in sorted(match.items())}, "unmatched": unmatched}
    (HERE / "match.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("entries", len(entries), "matched", len(match), Counter((v["tab"][:5], v["how"]) for v in match.values()))
    print("Systems rows", len(systems), "unmatched", len(unmatched["systems"]))
    print("Multi-stars rows", len(stars), "unmatched", len(unmatched["stars"]))


if __name__ == "__main__":
    main()
