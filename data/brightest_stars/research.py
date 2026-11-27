# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The 100 brightest stars in the night sky: the list, its astrometry and its motion.

    python data/brightest_stars/research.py <cache dir>

Writes `list.json` beside this file: one record per naked-eye point of light, brightest first.
Nothing here writes to the workbook; `build.py` does.

What counts (decided by the owner, 26 Nov 2026): a point of light as the eye sees it, ranked by
its combined apparent V magnitude. The Sun is left out.

- Magnitudes: the Hipparcos catalogue's V (ESA 1997, VizieR I/239, field H5). A Hipparcos entry
  for a close pair is the pair's combined light (alf Cru, alf Gem, gam Leo). Every Hipparcos
  entry brighter than V 6.5 within 60 arcsec of a bright one is summed with it (alf Cen A + B,
  bet Sco 1 + 2). `EXTRA` adds the one bright companion with no entry of its own (Mizar B).
- A variable star is ranked on that catalogue V, which is near its mean.
- Ties keep catalogue order (HIP number).
- Astrometry: van Leeuwen 2007 (VizieR I/311), the Hipparcos re-reduction. Gaia saturates on
  these stars. Radial velocity, spectral type and identifiers: SIMBAD.
- Motion columns: the same arithmetic as `data/known_within_100ly/kinematics/merge.py`.
"""
import csv
import importlib.util
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

VIZIER = "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv"
SIMBAD = "https://simbad.harvard.edu/simbad/sim-tap/sync"
IAU_CSN = "https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt"
N = 100
MERGE_ARCSEC = 60.0
BRIGHT = 3.3                       # only a point this bright can reach the list; fainter entries only join one
LY_PER_PC = 3.261563777
# A companion the eye cannot split from its primary and Hipparcos's entry leaves out:
# HIP of the primary -> (V, what it is, source).
EXTRA = {"65378": (3.88, "zet02 UMa (Mizar B), 14.4 arcsec from zet01 UMa", "SIMBAD V")}
# Tabs searched for a star already on file: title -> column holding the star's name.
TABS = {"Systems within 100 ly": "System / Host", "Multi-stars within 100 ly": "Star (component)",
        "Planetless 4+ Stars": "Star (component)", "Known within 100ly": "System / Host"}
SHORT = {"Systems within 100 ly": "Systems", "Multi-stars within 100 ly": "Multi-stars",
         "Planetless 4+ Stars": "Planetless 4+ Stars", "Known within 100ly": "Known"}

_spec = importlib.util.spec_from_file_location("nick", HERE.parent / "star_nicknames" / "research.py")
nick = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nick)


def fetch(url: str, data: dict | None = None) -> bytes:
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def vizier(cache: Path, name: str, query: str) -> list[dict]:
    f = cache / name
    if not f.exists():
        f.write_bytes(fetch(f"{VIZIER}?{query}&-out.max=20000"))
    lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    head = lines[0].split("\t")
    return [dict(zip(head, (c.strip() for c in l.split("\t")))) for l in lines[3:]]


def simbad(cache: Path, hips: list[str]) -> dict[str, dict]:
    f = cache / "simbad_hip.tsv"
    if not f.exists():
        names = ",".join(f"'HIP {h}'" for h in hips)
        f.write_bytes(fetch(SIMBAD, {
            "request": "doQuery", "lang": "adql", "format": "tsv", "maxrec": 5000,
            "query": "SELECT i.id, b.main_id, b.otype, b.sp_type, b.sp_bibcode, b.rvz_radvel, b.rvz_err, "
                     "b.rvz_bibcode, b.plx_value, b.plx_err, b.plx_bibcode, ids.ids FROM ident AS i "
                     "JOIN basic AS b ON b.oid = i.oidref JOIN ids ON ids.oidref = b.oid "
                     f"WHERE i.id IN ({names})"}))
    rows = csv.DictReader(f.open(encoding="utf-8"), delimiter="\t")
    return {r["id"].replace("HIP", "").strip(): r for r in rows}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def sep_arcsec(a: dict, b: dict) -> float:
    ra1, de1, ra2, de2 = (math.radians(float(x)) for x in (a["RAICRS"], a["DEICRS"], b["RAICRS"], b["DEICRS"]))
    c = math.sin(de1) * math.sin(de2) + math.cos(de1) * math.cos(de2) * math.cos(ra1 - ra2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 3600


def combined(mags: list[float]) -> float:
    return -2.5 * math.log10(sum(10 ** (-0.4 * m) for m in mags))


def velocity(ra, de, dist_ly, pmra, pmde, rv):
    """(l, b) always; (speed, motion l, motion b) too when there is a radial velocity."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    if rv is None or pmra is None or dist_ly is None:
        c = SkyCoord(ra=ra * u.deg, dec=de * u.deg, frame="icrs").galactic
        return float(c.l.deg), float(c.b.deg), None, None, None
    c = SkyCoord(ra=ra * u.deg, dec=de * u.deg, distance=dist_ly / LY_PER_PC * u.pc,
                 pm_ra_cosdec=pmra * u.mas / u.yr, pm_dec=pmde * u.mas / u.yr, radial_velocity=rv * u.km / u.s,
                 frame="icrs").galactic
    v = c.velocity.d_xyz.to(u.km / u.s).value              # heliocentric, toward l=0, l=90, b=90
    speed = float(math.sqrt(sum(x * x for x in v)))
    return (float(c.l.deg), float(c.b.deg), speed, math.degrees(math.atan2(v[1], v[0])) % 360.0,
            math.degrees(math.asin(v[2] / speed)))


def designation(main_id: str, grouped: bool) -> str:
    """SIMBAD's main id the workbook's way: "* alf CMa" -> "alf CMa"; a merged pair loses its number."""
    s = re.sub(r"^(\*\*?|V\*|NAME)\s+", "", main_id.strip())
    s = re.sub(r"\b([a-z]{1,3})\.", r"\1", s)
    s = re.sub(r"\b([a-z]{1,3})0(\d)\b", r"\1" if grouped else r"\1\2", s)
    s = re.sub(r"\s+", " ", s)
    return re.sub(r" [AB]$", "", s) if grouped else s


def on_tabs(ids: list[str]) -> tuple[list[str], dict]:
    """Where the workbook already holds this star: ["Systems: alf Tau", ...] and the names per tab."""
    from hybrasil.data import google_sheets as gs
    global _TABS
    if "_TABS" not in globals():
        book = gs.fetch_workbook(gs.resolve_spreadsheet_id())["tabs"]
        _TABS = {}
        for title, col in TABS.items():
            grid = book[title]
            c = [str(h).strip() for h in grid[0]].index(col)
            _TABS[title] = list(dict.fromkeys(str(r[c]).strip() for r in grid[1:] if len(r) > c and str(r[c]).strip()))
    keys = {nick.key(i, True) for i in ids} | {nick.bare(re.sub(r"^(NAME|\*\*?|V\*)\s+", "", i)) for i in ids}
    found = {}
    for title, names in _TABS.items():
        hit = [n for n in names if nick.key(n, True) in keys or nick.bare(n) in keys]
        if hit:
            found[SHORT[title]] = hit
    return [f"{t}: {', '.join(n)}" for t, n in found.items()], found


def main(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    hip = vizier(cache, "hip.tsv", "-source=I/239/hip_main&Vmag=%3C6.5&-out=HIP,Vmag,VarFlag,CCDM,MultFlag,Ncomp,"
                 "RAICRS,DEICRS,Plx,e_Plx,pmRA,pmDE,SpType,B-V,HvarType,Hpmax,Hpmin")
    hip2 = {r["HIP"]: r for r in vizier(
        cache, "hip2.tsv", "-source=I/311/hip2&Hpmag=%3C3.6&-out=HIP,RArad,DErad,Plx,e_Plx,pmRA,pmDE,e_pmRA,e_pmDE,Hpmag")}
    hip = [r for r in hip if r["Vmag"] and r["RAICRS"] and r["DEICRS"]]
    hip.sort(key=lambda r: (float(r["Vmag"]), int(r["HIP"])))
    groups: list[list[dict]] = []
    for r in hip:
        near = [g for g in groups if abs(float(g[0]["DEICRS"]) - float(r["DEICRS"])) < 0.05
                and any(sep_arcsec(r, m) < MERGE_ARCSEC for m in g)]
        if near:
            near[0].append(r)
        elif float(r["Vmag"]) < BRIGHT:
            groups.append([r])
    ranked = []
    for g in groups:
        mags = [float(m["Vmag"]) for m in g] + [EXTRA[m["HIP"]][0] for m in g if m["HIP"] in EXTRA]
        ranked.append((combined(mags), int(g[0]["HIP"]), g))
    ranked.sort(key=lambda x: (round(x[0], 2), x[1]))
    top, runners = ranked[:N], ranked[N:N + 5]
    info = simbad(cache, [m["HIP"] for _, _, g in ranked[:N + 5] for m in g])

    iau_file = cache / "IAU-CSN.txt"
    if not iau_file.exists():
        iau_file.write_bytes(fetch(IAU_CSN))
    iau = {}
    for n in nick.iau_names(cache):
        iau.setdefault(n["hip"], n["name"])

    out = []
    for rank, (v, _, g) in enumerate(top, 1):
        p, s = g[0], info[g[0]["HIP"]]
        a = hip2.get(p["HIP"], {})
        ids = [x.strip() for m in g for x in info[m["HIP"]]["ids"].split("|") if x.strip()]
        plx, e_plx = num(a.get("Plx")), num(a.get("e_Plx"))
        dist = 1000.0 * LY_PER_PC / plx if plx and plx > 0 else None
        ra, de = num(a.get("RArad")) or float(p["RAICRS"]), num(a.get("DErad")) or float(p["DEICRS"])
        pmra, pmde, rv = num(a.get("pmRA")), num(a.get("pmDE")), num(s["rvz_radvel"])
        l, b, speed, ml, mb = velocity(ra, de, dist, pmra, pmde, rv)
        grouped = len(g) > 1 or p["HIP"] in EXTRA or int(p["Ncomp"] or 1) > 1
        tabs, found = on_tabs(ids)
        name = designation(s["main_id"], grouped)
        bayer = nick.bayer(ids)
        note = "Hipparcos V"
        if len(g) > 1:
            note = "combined: " + " + ".join(f"HIP {m['HIP']} ({m['Vmag']})" for m in g)
        if p["HIP"] in EXTRA:
            note = f"combined: HIP {p['HIP']} ({p['Vmag']}) + {EXTRA[p['HIP']][1]} ({EXTRA[p['HIP']][0]}, {EXTRA[p['HIP']][2]})"
        out.append({
            "rank": rank, "name": name, "simbad": s["main_id"], "hip": [m["HIP"] for m in g],
            "iau": iau.get(p["HIP"], ""), "bayer": bayer[0] if bayer else "",
            "constellation": (re.search(r" ([A-Z][A-Za-z]{2})( [A-D])?$", bayer[0]).group(1) if bayer else ""),
            "v": round(v, 2), "v_note": note, "hip_entry_components": int(p["Ncomp"] or 1),
            "sp_type": s["sp_type"], "sp_bibcode": s["sp_bibcode"], "otype": s["otype"],
            "ra": ra, "dec": de, "plx_mas": plx, "plx_err_mas": e_plx,
            "distance_ly": dist, "distance_err_ly": dist * e_plx / plx if dist and e_plx else None,
            "pmra": pmra, "pmdec": pmde, "rv": rv, "rv_err": num(s["rvz_err"]), "rv_bibcode": s["rvz_bibcode"],
            "l": l, "b": b, "speed": speed, "motion_l": ml, "motion_b": mb,
            "hip_var": {"type": p.get("HvarType", ""), "hp_max": num(p.get("Hpmax")), "hp_min": num(p.get("Hpmin"))},
            "on_tabs": tabs, "tab_names": found, "ids": ids})
    (HERE / "list.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for o in out:
        print(f"{o['rank']:3d} {o['v']:5.2f} {o['name']:12s} {o['iau']:16s} {o['sp_type']:18s} "
              f"{(o['distance_ly'] or 0):7.0f} ly +/-{(o['distance_err_ly'] or 0):5.0f}  rv {o['rv']}  {'; '.join(o['on_tabs'])}")
    print("next five:", [(round(v, 2), designation(info[g[0]['HIP']]['main_id'], False)) for v, _, g in runners])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
