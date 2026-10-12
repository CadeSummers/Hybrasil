# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""P2: SIMBAD's adopted radial velocity and proper motion for every target row.

    python simbad.py     cat/simbad_gaia.json (by Gaia DR3 identifier) and cat/simbad_nogaia.json (rows with no Gaia
                         id: by name, else by position); each file is skipped when already on disk

SIMBAD's basic table carries one adopted RV per object (rvz_radvel, with its bibcode and a quality grade A-E) and one
adopted proper motion. merge.py uses an RV only where Gaia DR3 has none, and a proper motion only where Gaia has none.

Rows with no Gaia id are the CNS5 additions: bright stars Gaia did not solve (Sirius, Procyon, Altair...) and objects
named by CNS5 numbers SIMBAD does not know ('GJ 11551'). Their RA/Dec are at epoch J2016, SIMBAD's at J2000, so a
fast mover is up to a minute of arc away: they are matched by name first (the GJ number without its component
letters, accepted when SIMBAD's parallax is within 25% of the row's distance), else by the nearest source within 90"
whose parallax agrees as well.
"""
import re

from astropy.table import Table
from astroquery.simbad import Simbad

from common import CAT, TARGETS, load, mark, num, save

BASIC = ("b.main_id, b.ra AS s_ra, b.dec AS s_dec, b.plx_value, b.rvz_radvel, b.rvz_err, b.rvz_type, b.rvz_qual, "
         "b.rvz_bibcode, b.rvz_wavelength, b.pmra AS s_pmra, b.pmdec AS s_pmdec, b.pm_err_maj, b.pm_qual, "
         "b.pm_bibcode, b.otype, b.sp_type")
CONE_ARCSEC = 90.0
PLX_TOL = 0.25


def rows_of(tab):
    out = []
    for r in tab:
        d = {}
        for c in tab.colnames:
            v = r[c]
            if hasattr(v, "mask") and v.mask:
                v = None
            elif hasattr(v, "item"):
                v = v.item()
            if isinstance(v, bytes):
                v = v.decode()
            if isinstance(v, str):
                v = v.strip()
            if isinstance(v, float) and v != v:
                v = None
            d[c] = v
        out.append(d)
    return out


def by_gaia(targets):
    f = CAT / "simbad_gaia.json"
    if f.exists():
        return
    ids = [t for t in targets if t["gaia"]]
    got = []
    for s in range(0, len(ids), 2000):
        chunk = ids[s:s + 2000]
        up = Table({"k": [t["key"] for t in chunk], "gid": [f"Gaia DR3 {t['gaia']}" for t in chunk]})
        tab = Simbad.query_tap(f"SELECT t.k, {BASIC} FROM TAP_UPLOAD.up AS t JOIN ident AS i ON i.id = t.gid "
                               "JOIN basic AS b ON b.oid = i.oidref", up=up, maxrec=100000)
        got += rows_of(tab)
        print(f"  gaia ids {s + len(chunk)}/{len(ids)}: {len(got)} matched", flush=True)
    save(f, {"rows": got})


def gj_names(name):
    """(exact, bare): 'GJ 229 B' -> ('GJ 229 B', 'GJ 229'); 'GJ 280.0' -> ('GJ 280', 'GJ 280'). GJ-style names only."""
    m = re.fullmatch(r"(GJ|Gl|NN|Wo)\s+(\d+(?:\.\d+)?)(?:\s+([A-Z]{1,4}))?", name.strip())
    if not m:
        return None, None
    n = m.group(2)
    n = n[:-2] if n.endswith(".0") else n
    bare = f"{m.group(1)} {n}"
    return (f"{bare} {m.group(3)}" if m.group(3) else bare), bare


def one_component(name):
    """True for a row that is one star of a multiple ('GJ 229 B'), where a system-level match is another object."""
    return bool(re.search(r"\s[A-Z]$", name.strip()))


def plx_ok(plx, dist_ly):
    if not plx or not dist_ly:
        return False
    return abs(plx / (3261.563777 / dist_ly) - 1) <= PLX_TOL


def by_position(targets):
    f = CAT / "simbad_nogaia.json"
    if f.exists():
        return
    ts = [t for t in targets if not t["gaia"] and t["ra"] is not None]
    q_name = f"SELECT t.k, {BASIC} FROM TAP_UPLOAD.up AS t JOIN ident AS i ON i.id = t.nm JOIN basic AS b ON b.oid = i.oidref"
    exact = rows_of(Simbad.query_tap(q_name, up=Table({"k": [t["key"] for t in ts],
                                                      "nm": [gj_names(t["name"])[0] or "-" for t in ts]}), maxrec=100000))
    bare = rows_of(Simbad.query_tap(q_name, up=Table({"k": [t["key"] for t in ts],
                                                     "nm": [gj_names(t["name"])[1] or "-" for t in ts]}), maxrec=100000))
    up = Table({"k": [t["key"] for t in ts], "ra": [t["ra"] for t in ts], "de": [t["dec"] for t in ts]})
    cone = rows_of(Simbad.query_tap(
        f"SELECT t.k, {BASIC}, DISTANCE(POINT('ICRS', b.ra, b.dec), POINT('ICRS', t.ra, t.de)) * 3600 AS sep "
        "FROM TAP_UPLOAD.up AS t JOIN basic AS b ON 1 = CONTAINS(POINT('ICRS', b.ra, b.dec), "
        f"CIRCLE('ICRS', t.ra, t.de, {CONE_ARCSEC / 3600}))", up=up, maxrec=200000))
    by_key = {t["key"]: t for t in ts}
    pick = {}
    for how, rows in (("name", exact), ("system name", bare)):
        for r in rows:
            if r["k"] not in pick and plx_ok(r["plx_value"], by_key[r["k"]]["dist_ly"]):
                pick[r["k"]] = dict(r, how=how)
    for r in sorted(cone, key=lambda x: x["sep"]):
        if r["k"] not in pick and plx_ok(r["plx_value"], by_key[r["k"]]["dist_ly"]):
            pick[r["k"]] = dict(r, how=f"position, {r['sep']:.1f}\"")
    for k, p in pick.items():
        # a component row matched at system level, or by position, may have found its primary instead
        p["component_risk"] = p["how"] != "name" and one_component(by_key[k]["name"])
    save(f, {"rows": list(pick.values()), "tried": len(ts)})
    print(f"  no-Gaia rows: {len(pick)}/{len(ts)} matched ({sum(1 for p in pick.values() if p['how'] == 'name')} "
          f"by exact name; {sum(1 for p in pick.values() if p['component_risk'])} component rows matched loosely)", flush=True)


def main():
    targets = [t for t in load(TARGETS)["rows"] if t["blank"]]
    CAT.mkdir(exist_ok=True)
    mark("P2_simbad", "running")
    by_gaia(targets)
    by_position(targets)
    g = load(CAT / "simbad_gaia.json")["rows"]
    n = load(CAT / "simbad_nogaia.json")["rows"]
    mark("P2_simbad", "done", by_gaia=len(g), by_gaia_with_rv=sum(1 for r in g if num(r["rvz_radvel"]) is not None),
         no_gaia=len(n), no_gaia_with_rv=sum(1 for r in n if num(r["rvz_radvel"]) is not None))
    print(f"by Gaia id {len(g)} (RV {sum(1 for r in g if num(r['rvz_radvel']) is not None)}); "
          f"no Gaia id {len(n)} (RV {sum(1 for r in n if num(r['rvz_radvel']) is not None)})")


if __name__ == "__main__":
    main()
