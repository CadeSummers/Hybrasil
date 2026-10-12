# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run 6: kinematics for Gliese 48 and TOI-2267 A, the two Systems rows run 3 added without them.

    python write6.py plan     print every planned write; touches nothing
    python write6.py write    write, the Sources & Provenance block, and the rename

Without RV, proper motion and galactic l/b a row has no position or arrow in the Nearby Star Motion view,
so neither system was drawn there. The fill follows the rule the column was built with (Sources &
Provenance 'FINAL PASS'): Gaia DR3, with a published RV where Gaia has none. Derived columns use the
construction of S&P lines 3982-3985 and 4039-4042: AE and AF typed; AG:AJ orange-boxed with the standard note.
"""
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from hybrasil.data import google_sheets as gs  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402
from googleapiclient.http import HttpRequest  # noqa: E402

_execute = HttpRequest.execute


def _execute_with_retry(self, *a, **k):
    """The Sheets API allows 60 reads a minute; wait out a 429 rather than stop half-way."""
    for attempt in range(8):
        try:
            return _execute(self, *a, **k)
        except HttpError as e:
            if e.resp.status != 429 or attempt == 7:
                raise
            time.sleep(35)


HttpRequest.execute = _execute_with_retry

SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
SY, MS, SP = "Systems within 100 ly", "Multi-stars within 100 ly", "Sources & Provenance"
DATE = "2026-09-28"
LOG = HERE / "write_log.json"
PLAN = sys.argv[1:] == ["plan"]

# Gaia DR3 gaia_source, queried 2026-09-28 (ESA TAP): source_id -> the published values.
GAIA = {
    "Gliese 48": dict(source_id="533621859441169920", plx=121.45982871489811, pmra=1746.7010132181863,
                      pmdec=-381.76236971875386, rv=1.3429941, rv_err=0.15439215, ruwe=1.0015539),
    "TOI-2267 A": dict(source_id="571488283984760960", plx=44.34956545765309, pmra=182.3880709721218,
                       pmdec=-213.50347500560025, rv=None, rv_err=None, ruwe=13.708653),
}
# Gaia DR3 has no RV for TOI-2267, nor does CNS5 or SIMBAD; the discovery paper measured one.
TOI2267_RV = -19.0
TOI2267_RV_NOTE = ("Zuniga-Fernandez et al. 2025 (arXiv:2508.14176), Table 2: combined RV -19.0 +/- 0.3 km/s from one "
                   "night of Keck/NIRSPEC K-band spectra (2022-03-13); the secondary was not detected in the spectrum. "
                   "Gaia DR3, CNS5 and SIMBAD give no RV. One epoch of an unresolved binary: A's orbital motion "
                   "(masses 0.171 and 0.099 Msun, 8.9 au projected) could offset it from the pair's systemic "
                   "velocity by roughly 2 km/s.")
SOURCE = {
    "Gliese 48": "RV: Gaia DR3; PM: Gaia DR3",
    "TOI-2267 A": ("RV: Zuniga-Fernandez et al. 2025 (Keck/NIRSPEC, combined light); PM: Gaia DR3 | RUWE 13.71 -- "
                   "astrometry may be perturbed"),
}
LB_NOTE = ("INFERRED: galactic l/b computed from this row's RA/Dec (AO:AP, SIMBAD ICRS) by the IAU ICRS-to-Galactic "
           "rotation (astropy). Exact transform; no model.")
MOTION_NOTE = ("INFERRED: direction the star is moving, relative to the Sun, in galactic l/b. From RA/Dec, distance "
               "(C), RV and proper motions (AB:AD) via astropy; no LSR correction. Its speed reproduces Space "
               "velocity (AF).")


def q(t):
    return "'" + t.replace("'", "''") + "'"


def values(rng):
    return API.values().get(spreadsheetId=SID, range=rng, valueRenderOption="UNFORMATTED_VALUE"
                            ).execute().get("values", [])


def row_of(tab, name, col="A"):
    v = values(f"{q(tab)}!{col}1:{col}2000")
    hits = [i + 1 for i, r in enumerate(v) if r and r[0] == name]
    assert len(hits) == 1, (tab, name, hits)
    return hits[0]


def kinematics(ra, dec, d_ly, pmra, pmdec, rv):
    """write3.py's construction: AE:AJ from RA/Dec, distance, proper motions and RV."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    mu = math.hypot(pmra, pmdec) / 1000
    c = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)
    g = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, distance=(d_ly / 3.26156) * u.pc, pm_ra_cosdec=pmra * u.mas / u.yr,
                 pm_dec=pmdec * u.mas / u.yr, radial_velocity=rv * u.km / u.s).galactic
    U, V, W = g.velocity.d_xyz.to(u.km / u.s).value
    s = math.sqrt(U * U + V * V + W * W)
    af = math.hypot(rv, 4.74047 * mu * d_ly / 3.26156)
    assert abs(s - af) < 0.05, (s, af)          # |(U,V,W)| reproduces Space velocity, as on every other row
    return {"AE": round(mu, 3), "AF": round(af, 2), "AG": round(float(c.galactic.l.deg), 2),
            "AH": round(float(c.galactic.b.deg), 2), "AI": round(math.degrees(math.atan2(V, U)) % 360, 2),
            "AJ": round(math.degrees(math.asin(W / s)), 2)}


def main():
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    assert PLAN or "write" not in log, "already written"
    upd, exp, orange, notes, done = {}, {}, [], {}, {}
    for name, g in GAIA.items():
        r = row_of(SY, name)
        row = values(f"{q(SY)}!A{r}:AP{r}")[0]
        get = lambda c: row[_ix(c)] if _ix(c) < len(row) else ""
        assert str(get("AL")) == g["source_id"], (name, get("AL"))
        d = get("C")
        assert abs(3261.56 / g["plx"] - d) < 0.05, (name, d, 3261.56 / g["plx"])    # the row's distance is Gaia's
        for c in ("AB", "AC", "AD", "AE", "AF", "AG", "AH", "AI", "AJ", "AK"):
            assert get(c) in ("", None), (name, c, get(c))
            exp[f"{q(SY)}!{c}{r}"] = ""
        rv = round(g["rv"], 2) if g["rv"] is not None else TOI2267_RV
        pmra, pmdec = round(g["pmra"], 3), round(g["pmdec"], 3)
        k = kinematics(get("AO"), get("AP"), d, pmra, pmdec, rv)
        cells = {"AB": rv, "AC": pmra, "AD": pmdec, **k, "AK": SOURCE[name]}
        for c, val in cells.items():
            upd[f"{q(SY)}!{c}{r}"] = val
        for c in ("AG", "AH", "AI", "AJ"):
            orange.append(f"{q(SY)}!{c}{r}")
            notes[f"{q(SY)}!{c}{r}"] = LB_NOTE if c in ("AG", "AH") else MOTION_NOTE
        if g["rv"] is None:
            notes[f"{q(SY)}!AB{r}"] = TOI2267_RV_NOTE
        done[name] = {"row": r, **cells}
    # TOI-2267 A's Multi-stars row: the same Gaia source. B has no astrometry of its own and stays blank.
    hm = {h: i for i, h in enumerate(values(f"{q(MS)}!A1:AT1")[0])}
    rm = row_of(MS, "TOI-2267 A", "B")
    mrow = values(f"{q(MS)}!A{rm}:AT{rm}")[0]
    assert str(mrow[hm["Gaia DR3 source_id"]]) == GAIA["TOI-2267 A"]["source_id"]
    t = done["TOI-2267 A"]
    for h, val in (("Radial velocity (km/s)", t["AB"]), ("Proper motion in RA, μα·cos δ (mas/yr)", t["AC"]),
                   ("Proper motion in Dec, μδ (mas/yr)", t["AD"]), ("Total proper motion, μ (arcsec/yr)", t["AE"]),
                   ("Space velocity (km/s)", t["AF"]), ("Kinematics source", t["AK"])):
        cell = f"{q(MS)}!{_letter(hm[h])}{rm}"
        assert (mrow[hm[h]] if hm[h] < len(mrow) else "") in ("", None), (h, mrow[hm[h]])
        upd[cell] = val
        exp[cell] = ""
    notes[f"{q(MS)}!{_letter(hm['Radial velocity (km/s)'])}{rm}"] = TOI2267_RV_NOTE
    done["TOI-2267 A (Multi-stars)"] = {"row": rm}

    lines = [
        "",
        "RUN 6, 28 SEPTEMBER 2026: KINEMATICS FOR GLIESE 48 AND TOI-2267 A (rows added in run 3 without them).",
        "Writer: data/unconfirmed_search/run6/write6.py; log write_log.json. Without RV, proper motion and",
        "galactic l/b these rows had no place in the Nearby Star Motion view.",
        "Gaia DR3 gaia_source, queried 28 Sep 2026 (ESA TAP), by the rows' own source_id:",
        f"  Gliese 48 (533621859441169920): RV {GAIA['Gliese 48']['rv']:.3f} +/- {GAIA['Gliese 48']['rv_err']:.3f} km/s, "
        f"PM {GAIA['Gliese 48']['pmra']:.3f} / {GAIA['Gliese 48']['pmdec']:.3f} mas/yr, RUWE 1.00.",
        f"    SIMBAD (Ross 318) adopts 1.56 km/s (2018MNRAS.475.1960F); Gaia DR3 first, as the column was built.",
        f"  TOI-2267 A (571488283984760960): PM {GAIA['TOI-2267 A']['pmra']:.3f} / {GAIA['TOI-2267 A']['pmdec']:.3f} "
        "mas/yr;",
        "    RUWE 13.71 (the unresolved A+B pair), so flagged in 'Kinematics source'. No RV in Gaia DR3,",
        "    CNS5 (J/A+A/670/A19, CNS5 1077) or SIMBAD (G 222-3); RV -19.0 +/- 0.3 km/s from Zuniga-Fernandez et al.",
        "    2025 (arXiv:2508.14176), Table 2: one night of Keck/NIRSPEC, combined light; caveat in the cell note.",
        "  Both parallaxes reproduce the rows' distances (26.85 and 73.54 ly), which were left alone.",
        "DERIVED by the construction of lines 3982-3985 and 4039-4042: Total PM (AE), Space velocity (AF);",
        "Galactic l/b (AG:AH) and Motion toward l/b (AI:AJ) orange-boxed and noted; |(U,V,W)| checked against AF.",
        f"  Gliese 48: " + ", ".join(f"{c} {done['Gliese 48'][c]}" for c in ("AE", "AF", "AG", "AH", "AI", "AJ")) + ".",
        f"  TOI-2267 A: " + ", ".join(f"{c} {done['TOI-2267 A'][c]}" for c in ("AE", "AF", "AG", "AH", "AI", "AJ"))
        + ".",
        "  TOI-2267 A's Multi-stars row takes the same RV, PM and derived values; TOI-2267 B has no astrometry of its own.",
    ]
    if PLAN:
        for c, val in upd.items():
            print(f"  WRITE {c} = {val!r}")
        for c, n in notes.items():
            print(f"  NOTE  {c}: {n[:110]}")
        print("  ORANGE", orange)
        print("\n".join(lines))
        return
    gs.update_cells(SID, upd, expect=exp)
    gs.set_border(SID, orange, gs.INFERRED_BORDER)
    gs.set_note(SID, notes)
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    rows = meta["gridProperties"]["rowCount"]
    assert values(f"{q(SP)}!A{rows}")[0][0].strip()
    start, end = rows + 1, rows + len(lines)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log["write"] = {"rows": done, "sp_rows": [start, end], "title": title}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log["write"], ensure_ascii=False))


def _ix(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


if __name__ == "__main__":
    main()
