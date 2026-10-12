# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Give every "Planetless 4+ Stars" system a position and velocity in the galaxy, as the Systems tab has.

    python kinematics.py fetch    Gaia DR3 for each system's host star, into cat/gaia_hosts.json (~5 min)
    python kinematics.py          plan: print every cell that would change, old -> new, and why; touches nothing
    python kinematics.py write    insert the four galactic columns, write, mark, note, provenance, rename

The Nearby Stellar Motion view draws a system at its host's galactic position with an arrow for its velocity
relative to the Sun, read by header from 'Distance (ly)', 'Galactic longitude l (deg)', 'Galactic latitude b (deg)',
'Space velocity (km/s)', 'Motion toward l (deg, heliocentric)' and 'Motion toward b (deg, heliocentric)'. This tab
had the inputs on each system's host row -- RA/Dec, distance, and the MSC's radial velocity and proper motions --
but not the four galactic columns, and no space velocity.

Inputs, by the Systems tab's standard (Sources & Provenance, 24 Sep 2026: Gaia DR3 first):
  - Gaia DR3 gaia_source, cross-matched to the host: within 60" of its MSC position carried to J2016.0 by the
    MSC proper motion, parallax within 20% of the tab's, the brightest such source. Its proper motion replaces
    the MSC's, and its radial velocity the MSC's where Gaia has one. Each replaced cell's note keeps the old value.
  - Otherwise the MSC values already on the row stay (bright stars Gaia did not solve, or no Gaia RV).
  - Flags in 'Kinematics source', as on Systems: RUWE over 1.4 (astrometry may be perturbed by a companion), and a
    Gaia parallax more than 5% from the tab's distance. The distance itself is not changed: it scales every orbit.
Derived, by the construction of Sources & Provenance lines 3982-3985 (astropy, no LSR correction), orange-boxed:
  Total proper motion, Space velocity, Galactic l/b (from RA/Dec), Motion toward l/b (direction of (U, V, W)).
Only host rows: the view draws one point per system.
"""
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

GAIA = "https://gea.esac.esa.int/tap-server/tap/sync"
CACHE = HERE / "cat" / "gaia_hosts.json"
FP, SP = "Planetless 4+ Stars", "Sources & Provenance"
MODE = (sys.argv[1:] or ["plan"])[0]
RUWE_FLAG = 1.4
PLX_TOL = 0.05
NEW_COLS = ["Galactic longitude l (deg)", "Galactic latitude b (deg)", "Motion toward l (deg, heliocentric)",
            "Motion toward b (deg, heliocentric)"]
H_RV, H_PMRA, H_PMDE = ("Radial velocity (km/s)", "Proper motion in RA, μα·cos δ (mas/yr)",
                        "Proper motion in Dec, μδ (mas/yr)")
H_MU, H_V, H_KS, H_SID = ("Total proper motion, μ (arcsec/yr)", "Space velocity (km/s)", "Kinematics source",
                          "Gaia DR3 source_id")


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


def host_rows(values):
    """{system: (row number, {header: value})} for each system's host star."""
    h = [str(x).strip() for x in values[0]]
    out = {}
    for r, row in enumerate(values[1:], start=2):
        d = dict(zip(h, list(row) + [""] * (len(h) - len(row))))
        if d.get("Node type") == "star" and str(d.get("Role in system", "")).startswith("host"):
            assert d["System / Host"] not in out, d["System / Host"]
            out[d["System / Host"]] = (r, d)
    return h, out


def fetch():
    import glob
    import openpyxl
    snap = sorted(glob.glob(str(ROOT / "data" / "hybrasil-*.xlsx")))[-1]
    values = [list(r) for r in openpyxl.load_workbook(snap, read_only=True, data_only=True)[FP].iter_rows(values_only=True)]
    _, hosts = host_rows(values)
    found = {}
    for s, (_, d) in hosts.items():
        ra, de = num(d["RA (deg, ICRS)"]), num(d["Dec (deg, ICRS)"])
        pmra, pmde = num(d[H_PMRA]) or 0.0, num(d[H_PMDE]) or 0.0
        dt = 16.0                                          # MSC positions are J2000; Gaia DR3's epoch is J2016.0
        ra16 = ra + pmra * dt / 3.6e6 / math.cos(math.radians(de))
        de16 = de + pmde * dt / 3.6e6
        plx = 3261.563777 / num(d["Distance (ly)"])
        rows = tap("SELECT source_id, ra, dec, parallax, parallax_error, pmra, pmra_error, pmdec, pmdec_error, "
                   "radial_velocity, radial_velocity_error, ruwe, phot_g_mean_mag, "
                   f"DISTANCE(POINT(ra, dec), POINT({ra16}, {de16})) * 3600 AS sep "
                   f"FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT(ra, dec), CIRCLE({ra16}, {de16}, {60 / 3600})) "
                   f"AND parallax BETWEEN {plx * 0.8} AND {plx * 1.2}")
        found[s] = {"host": d["Star (component)"], "query": {"ra16": ra16, "de16": de16, "plx_tab": plx},
                    "rows": sorted(rows, key=lambda x: x["phot_g_mean_mag"] if x["phot_g_mean_mag"] else 99)}
        print(f"{s:16} {len(rows)} match(es)", flush=True)
    CACHE.write_text(json.dumps(found, indent=1))


def velocity(ra, de, dist_ly, pmra, pmde, rv):
    """(total mu arcsec/yr, space velocity km/s, l, b, motion l, motion b) -- Sources & Provenance 3982-3985."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    pc = dist_ly / 3.261563777
    c = SkyCoord(ra=ra * u.deg, dec=de * u.deg, distance=pc * u.pc, pm_ra_cosdec=pmra * u.mas / u.yr,
                 pm_dec=pmde * u.mas / u.yr, radial_velocity=rv * u.km / u.s, frame="icrs").galactic
    v = c.velocity.d_xyz.to(u.km / u.s).value              # (U, V, W): heliocentric, toward l=0, l=90, b=90
    speed = float(math.sqrt(sum(x * x for x in v)))
    ml = math.degrees(math.atan2(v[1], v[0])) % 360.0
    mb = math.degrees(math.asin(v[2] / speed))
    return (math.hypot(pmra, pmde) / 1000.0, speed, float(c.l.deg), float(c.b.deg), ml, mb)


MATCH_SEP = 3.0                # arcsec from the MSC position carried to J2016.0
MATCH_GV = (-2.0, 0.8)         # G - V for a star of any class here (M dwarfs run G well below V)
MATCH_PM = 20.0                # mas/yr: a source further than this from the MSC's proper motion is another star
                               # (2MASS J07495087, GJ 490, zet1 Cnc); less is photocentre wobble (HR 2468, 10)


def msc_record(msc, wds, label):
    """The MSC catalog record for a component: its own label, else the longest label that prefixes it."""
    recs = (msc.get(wds) or {}).get("catalog", [])
    best = [x for x in recs if label.startswith(x["m_ID"])]
    return max(best, key=lambda x: len(x["m_ID"])) if best else None


def gaia_match(cands, vmag, pmra, pmde):
    """The Gaia source that is the host: near, of its brightness and moving with it; None when none is."""
    ok = [x for x in cands if x["sep"] <= MATCH_SEP and x["phot_g_mean_mag"] is not None
          and (vmag is None or MATCH_GV[0] <= x["phot_g_mean_mag"] - vmag <= MATCH_GV[1])
          and (x["pmra"] is None or math.hypot(x["pmra"] - pmra, x["pmdec"] - pmde) <= MATCH_PM)]
    return min(ok, key=lambda x: x["sep"]) if ok else None


def plan_rows(values):
    """Per host: the cells to write, with notes and marks.

    Proper motion and radial velocity stay the MSC's, which the tab already carries: the MSC's RV is the
    SYSTEMIC velocity where a host is a spectroscopic binary, while Gaia DR3's is a combined-light average over its
    34 months (HR 1099: Gaia -21.2 km/s, MSC -15.9, published gamma -15.4), and the MSC's proper motions are Gaia
    DR3's on most hosts already. Gaia DR3 is used for the source_id, the RUWE and parallax flags, and the RV where the
    MSC has none (its 0.0 is a blank); failing that, a bound companion's MSC RV.
    """
    import json as _json
    h, hosts = host_rows(values)
    gaia = _json.loads(CACHE.read_text())
    msc = _json.loads((HERE / "msc.json").read_text(encoding="utf-8"))
    out = {}
    for s, (r, d) in hosts.items():
        rec = msc_record(msc, d["WDS code"], str(d["MSC label"]))
        vmag = rec.get("Vmag") if rec else None
        rv, pmra, pmde = num(d[H_RV]), num(d[H_PMRA]), num(d[H_PMDE])
        g = gaia_match((gaia.get(s) or {}).get("rows") or [], vmag, pmra, pmde)
        rv_txt, flags, rv_note = "MSC", [], None
        if not rv:                                         # the MSC's blank RV reads 0.0
            if g and g["radial_velocity"] is not None:
                rv, rv_txt = round(g["radial_velocity"], 3), "Gaia DR3 (the MSC has none)"
                rv_note = (f"SOURCE: Gaia DR3 gaia_source {g['source_id']}, radial_velocity "
                           f"{g['radial_velocity']:.3f} +- {g['radial_velocity_error']:.3f} km/s. The MSC lists no RV "
                           "for this star (its 0.0 was a blank).")
            else:
                comp = [x for x in (msc.get(d["WDS code"]) or {}).get("catalog", []) if x.get("RV")]
                if comp:
                    x = min(comp, key=lambda x: x["m_ID"])
                    rv, rv_txt = x["RV"], f"MSC, component {x['m_ID']}'s (a bound companion; the host has none)"
                    rv_note = (f"SOURCE: MSC catalog record for component {x['m_ID']} of WDS {d['WDS code']}: RV "
                               f"{x['RV']} km/s. WEAK: the host has no RV in the MSC or Gaia DR3, so its bound "
                               "companion's stands in; an orbit adds a few km/s at most.")
                else:
                    rv, rv_txt = None, "none"
        pm_txt = "MSC"
        if g and g["pmra"] is not None:
            same = math.hypot(g["pmra"] - pmra, g["pmdec"] - pmde) < 0.5
            pm_txt = "MSC (= Gaia DR3)" if same else (
                f"MSC (Gaia DR3 differs by {math.hypot(g['pmra'] - pmra, g['pmdec'] - pmde):.1f} mas/yr)")
        if g and g["ruwe"] and g["ruwe"] > RUWE_FLAG:
            flags.append(f"RUWE {g['ruwe']:.2f} -- astrometry may be perturbed")
        plx_tab = 3261.563777 / num(d["Distance (ly)"])
        if g and g["parallax"] and abs(g["parallax"] / plx_tab - 1) > PLX_TOL:
            flags.append(f"DISTANCE: Gaia DR3 parallax {g['parallax']:.2f} mas is "
                         f"{100 * (g['parallax'] / plx_tab - 1):+.0f}% from the tab's {plx_tab:.2f} mas; the tab's "
                         "distance is used")
        if g is None:
            flags.append("no Gaia DR3 source identified (bright, or not resolved from a companion)")
        res = dict(row=r, d=d, g=g, rv=rv, rv_txt=rv_txt, rv_note=rv_note, pm_txt=pm_txt, flags=flags,
                   msc_rv=num(d[H_RV]))
        if rv is not None:
            mu, speed, l, b, ml, mb = velocity(num(d["RA (deg, ICRS)"]), num(d["Dec (deg, ICRS)"]),
                                               num(d["Distance (ly)"]), pmra, pmde, rv)
            res.update(mu=round(mu, 4), v=round(speed, 3), l=round(l, 3), b=round(b, 3), ml=round(ml, 2),
                       mb=round(mb, 2))
        out[s] = res
    return h, out


def kin_source(p):
    return " | ".join([f"RV: {p['rv_txt']}; PM: {p['pm_txt']}", *p["flags"]])


def main():
    if MODE == "fetch":
        return fetch()
    from hybrasil.data import google_sheets as gs
    from fill import q  # noqa: F401  (importing fill also installs its 429 retry wrapper)
    from build import GREY_RULE
    sid = gs.resolve_spreadsheet_id()
    api = gs._sheets_api()
    values = api.values().get(spreadsheetId=sid, range=f"{q(FP)}!A1:CZ2000",
                              valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
    h, plan = plan_rows(values)
    have = [c for c in NEW_COLS if c in h]
    assert not have or have == NEW_COLS, have
    print(f"{len(plan)} hosts: Gaia DR3 source identified on {sum(p['g'] is not None for p in plan.values())}; "
          f"velocity on {sum('v' in p for p in plan.values())}; flagged {sum(bool(p['flags']) for p in plan.values())}")
    for s, p in plan.items():
        v = (f"v={p['v']:7.2f} km/s  l/b {p['l']:7.2f} {p['b']:6.2f}  toward {p['ml']:6.1f} {p['mb']:5.1f}"
             if "v" in p else "no velocity")
        print(f"  {s:24} {p['d']['Star (component)']:26} RV {p['rv']!s:>8}  {v}  {kin_source(p)[:120]}")
    if MODE == "write":
        write(gs, api, sid, h, plan, GREY_RULE)


def write(gs, api, sid, h, plan, grey):
    from fill import letter, q
    meta = api.get(spreadsheetId=sid, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    tab = next(s["properties"] for s in meta if s["properties"]["title"] == FP)
    # 1. Insert the four galactic columns after Space velocity, as on Systems (AF Space velocity, AG:AJ).
    if NEW_COLS[0] not in h:
        at = h.index(H_V) + 1
        assert h[at] == H_KS, h[at]
        api.batchUpdate(spreadsheetId=sid, body={"requests": [{"insertDimension": {
            "range": {"sheetId": tab["sheetId"], "dimension": "COLUMNS", "startIndex": at, "endIndex": at + 4},
            "inheritFromBefore": True}}]}).execute()
        gs.update_cells(sid, {f"{q(FP)}!{letter(at)}1:{letter(at + 3)}1": [NEW_COLS]},
                        expect={f"{q(FP)}!{letter(at)}1": "", f"{q(FP)}!{letter(at + 4)}1": H_KS})
        values = api.values().get(spreadsheetId=sid, range=f"{q(FP)}!A1:CZ2000",
                                  valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
        h, again = plan_rows(values)
        assert {s: p["row"] for s, p in again.items()} == {s: p["row"] for s, p in plan.items()}
    col = {k: i for i, k in enumerate(h)}

    cells, expect, notes, orange, plain = {}, {}, {}, [], []
    method = ("INFERRED: astropy SkyCoord(RA, Dec, distance, pmRA, pmDec, RV) -> galactic (U, V, W), heliocentric, "
              "no LSR correction (Sources & Provenance lines 3982-3985), at this row's Distance (ly).")
    for s, p in plan.items():
        r = p["row"]
        a1 = lambda hd: f"{q(FP)}!{letter(col[hd])}{r}"   # noqa: E731
        expect[a1("Star (component)")] = p["d"]["Star (component)"]
        g = p["g"]
        if g is not None:
            cells[a1(H_SID)] = str(g["source_id"])
            notes[a1(H_SID)] = (f"SOURCE: Gaia DR3 gaia_source, the host: G = {g['phot_g_mean_mag']:.2f}, "
                                f"{g['sep']:.2f}\" from the MSC position carried to J2016.0, parallax "
                                f"{g['parallax']:.2f} mas, RUWE {g['ruwe']:.2f}.")
            plain.append(a1(H_SID))
        if p["rv_note"]:
            cells[a1(H_RV)] = p["rv"]
            expect[a1(H_RV)] = p["msc_rv"]
            notes[a1(H_RV)] = p["rv_note"]
            plain.append(a1(H_RV))
        cells[a1(H_KS)] = kin_source(p)
        notes[a1(H_KS)] = f"Was: {p['d'][H_KS]}"
        if "v" not in p:
            continue
        weak = " WEAK: " + "; ".join(p["flags"]) + "." if p["flags"] else ""
        for hd, v, note in (
                (H_MU, p["mu"], "INFERRED: sqrt(pmRA^2 + pmDec^2) / 1000 (as on Systems)."),
                (H_V, p["v"], f"{method} |(U, V, W)|.{weak}"),
                ("Galactic longitude l (deg)", p["l"], "INFERRED: RA/Dec through the IAU ICRS-to-Galactic rotation "
                                                       "(astropy)."),
                ("Galactic latitude b (deg)", p["b"], "INFERRED: RA/Dec through the IAU ICRS-to-Galactic rotation "
                                                      "(astropy)."),
                ("Motion toward l (deg, heliocentric)", p["ml"], f"{method} l = atan2(V, U).{weak}"),
                ("Motion toward b (deg, heliocentric)", p["mb"], f"{method} b = asin(W / |v|).{weak}")):
            cells[a1(hd)] = v
            notes[a1(hd)] = note
            orange.append(a1(hd))

    gs.update_cells(sid, {k: [[v]] for k, v in cells.items()}, expect=expect)
    gs.set_border(sid, orange, gs.INFERRED_BORDER)
    gs.set_border(sid, plain, grey, style="SOLID")
    gs.set_note(sid, notes)

    spm = next(s["properties"] for s in meta if s["properties"]["title"] == SP)
    last = spm["gridProperties"]["rowCount"]
    assert gs.read_cells(sid, [f"{q(SP)}!A{last}"])[f"{q(SP)}!A{last}"][0][0].strip()
    sp = sp_entry(plan)
    start, end = last + 1, last + len(sp)
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
        "sheetId": spm["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{start}:A{end}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(sid)
    print("done:", {"cells": len(cells), "sp_rows": [start, end], "title": title})


def sp_entry(plan):
    import datetime
    n = len(plan)
    matched = sum(p["g"] is not None for p in plan.values())
    same = sum(p["pm_txt"] == "MSC (= Gaia DR3)" for p in plan.values())
    rv_fill = {s: p["rv_txt"] for s, p in plan.items() if p["rv_note"]}
    ruwe = sum(any(f.startswith("RUWE") for f in p["flags"]) for p in plan.values())
    dist = [s for s, p in plan.items() if any(f.startswith("DISTANCE") for f in p["flags"])]
    none = [s for s, p in plan.items() if p["g"] is None]
    nov = [s for s, p in plan.items() if "v" not in p]
    filled = "; ".join(f"{s} ({t})" for s, t in rv_fill.items()) or "none"
    return [
        "",
        f"{datetime.date.today():%d %B %Y}".upper() + ": 'Planetless 4+ Stars' -- GALACTIC POSITION AND MOTION FOR "
        f"EVERY SYSTEM'S HOST STAR ({n} rows; data/four_plus_stars/kinematics.py). Four columns inserted after Space "
        "velocity, as on Systems (AG:AJ there): Galactic longitude l, Galactic latitude b, Motion toward l, Motion "
        "toward b.",
        "Why: so the Nearby Stellar Motion view can offer these systems; it reads exactly these headers. Host rows "
        "only: the view draws one point per system.",
        "Inputs. Proper motion and radial velocity are the MSC's, already on each host row, and were kept: the MSC's "
        "RV is the SYSTEMIC velocity where the host is a spectroscopic binary, while Gaia DR3's is a combined-light "
        "average (HR 1099: Gaia -21.2 km/s, MSC -15.9, published gamma about -15.4), and the MSC's proper motions are "
        f"Gaia DR3's on {same} of {n} hosts to 0.5 mas/yr. 'Kinematics source' says which, per row; its old text is "
        "kept in the note.",
        f"  Gaia DR3 gaia_source identified for {matched} hosts (nearest source within {MATCH_SEP:.0f}\" of the MSC "
        f"position carried to J2016.0, parallax within 20%, G - V in [{MATCH_GV[0]}, {MATCH_GV[1]}]); source_id "
        f"filled. Not identified ({len(none)}): {', '.join(none)}.",
        f"  The MSC's blank RV reads 0.0; filled on {filled}. No velocity at all: {', '.join(nov) or 'none'}.",
        f"  Flags in Kinematics source, as on Systems: RUWE > {RUWE_FLAG} on {ruwe} hosts (a companion may perturb "
        f"the astrometry); Gaia parallax more than {PLX_TOL:.0%} from the tab's distance on {len(dist)}: "
        f"{', '.join(dist) or 'none'}. The tab's distance is kept on every row; it scales the orbits.",
        "Derived, by the construction of lines 3982-3985 (astropy SkyCoord -> galactic (U, V, W); no LSR "
        "correction, so motion relative to the SUN): Total proper motion, Space velocity = |(U, V, W)|, Galactic "
        "l/b, Motion toward l/b. Orange-boxed and noted (arithmetic on published inputs); WEAK in the motion notes "
        "where a flag applies.",
    ]


if __name__ == "__main__":
    main()
