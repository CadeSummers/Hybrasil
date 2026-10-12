# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
import json, math, collections, sys, openpyxl
SP = sys.argv[1]
msc = json.load(open(f"{SP}/msc_100ly.json", encoding="utf-8"))
wb = openpyxl.load_workbook("data/hy-brasil-20261009-0929.xlsx", read_only=True, data_only=True)

def tab(name):
    rows = list(wb[name].iter_rows(values_only=True)); h = rows[0]
    return [dict(zip(h, r)) for r in rows[1:] if r and r[0]]

pairs = collections.defaultdict(list)
for p in msc["systems"]:
    pairs[p["ID"]].append(p)
recs = collections.defaultdict(list)
for r in msc["catalog"]:
    recs[r["ID"]].append(r)

def leaves(wid):
    ps = [p for p in pairs[wid] if not (p["Type"] or "").startswith("X") and "X" not in (p["Type"] or "").split(",")]
    firm = [p for p in ps if "?" not in (p["Type"] or "")]
    # a tree of n pairs has n + 1 leaves; an uncertain pair adds one uncertain star
    return len(ps) + 1, len(firm) + 1, ps

def sep_arcsec(ra1, de1, ra2, de2):
    d = math.radians
    c = math.sin(d(de1))*math.sin(d(de2)) + math.cos(d(de1))*math.cos(d(de2))*math.cos(d(ra1-ra2))
    return math.degrees(math.acos(max(-1, min(1, c)))) * 3600

def match(ra, de, radius=90):
    best = None
    for wid, rs in recs.items():
        for r in rs:
            if r["RAJ2000"] is None: continue
            s = sep_arcsec(ra, de, r["RAJ2000"], r["DEJ2000"])
            if s < radius and (best is None or s < best[1]):
                best = (wid, s, r["m_ID"])
    return best

sy = tab("Systems within 100 ly")
ms = tab("Multi-stars within 100 ly")
ms_count = {}
for r in ms:
    ms_count.setdefault(r["System / Host"], set()).add(r["Star (component)"])
out = []
for r in sy:
    ra, de = r.get("RA (deg, ICRS)"), r.get("Dec (deg, ICRS)")
    if ra is None: continue
    m = match(float(ra), float(de))
    if not m: continue
    wid, s, comp = m
    n_all, n_firm, ps = leaves(wid)
    have = int(r["Stars in system"] or 0)
    out.append(dict(host=r["System / Host"], have=have, ms_rows=len(ms_count.get(r["System / Host"], ())),
                    planets=r.get("Confirmed planets") or 0, wds=wid, comp=comp, sep=round(s, 1),
                    msc_all=n_all, msc_firm=n_firm,
                    pairs=[f"{p['Prim']},{p['Sec']}:{p['Type']}" for p in ps]))
json.dump(out, open(f"{SP}/audit_systems.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
under = [o for o in out if o["msc_all"] > o["have"]]
print(f"Systems hosts matched to an MSC system: {len(out)} of {len(sy)}; star count below the MSC's: {len(under)}")
for o in sorted(under, key=lambda o: (-(o["msc_firm"] - o["have"]), o["host"])):
    print(f"  {o['host']:22} tab {o['have']} (Multi-stars rows {o['ms_rows']})  MSC {o['msc_firm']} firm / {o['msc_all']} incl. uncertain  "
          f"planets {o['planets']}  {o['wds']} [{o['comp']} {o['sep']}\"]  {' '.join(o['pairs'])}")

# Planetless systems that host a planet or candidate: a Planetless row within 90" of a Systems row
pl = tab("Planetless 4+ Stars")
hits = {}
for r in pl:
    ra, de = r.get("RA (deg, ICRS)"), r.get("Dec (deg, ICRS)")
    if ra is None: continue
    for s in sy:
        if s.get("RA (deg, ICRS)") is None: continue
        d = sep_arcsec(float(ra), float(de), float(s["RA (deg, ICRS)"]), float(s["Dec (deg, ICRS)"]))
        if d < 90:
            hits.setdefault(r["System / Host"], set()).add((s["System / Host"], s.get("Confirmed planets") or 0, round(d)))
print(f"\nPlanetless systems that sit on a Systems-tab host (planet or candidate): {len(hits)}")
for k, v in hits.items():
    print(" ", k, "->", sorted(v))
