# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run 7: DE CVn recorded as the binary it is -- a DA white dwarf and an M3 V red dwarf.

    python write7.py plan     print every planned write; touches nothing
    python write7.py write    write, the Sources & Provenance block, and the rename

DE CVn had one star and no Multi-stars rows. Its Systems row paired the white dwarf's Teff (8000 K) with the
pair's luminosity (0.0172 Lsun, all but 4% of it the red dwarf's), so the white dwarf's solvent bands were drawn
five times too far out and the red dwarf, which outshines it 24 to 1, was not drawn at all.

Modelled on RR Cae, the workbook's other eclipsing WD + dM pair with a circumbinary planet: A is the white dwarf
(van den Besselaar et al. 2007 call it the primary), B the red dwarf, placed by B's 'Separation from' A at the
eclipse solution's orbital separation. The circumbinary planet stays filed under 'DE CVn', which names no star,
so the loader puts it round the primary; its Unconfirmed 'Host luminosity' stays the pair's, since a
circumbinary planet is lit by both.
"""
import json
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
SY, MS, UN, SP = ("Systems within 100 ly", "Multi-stars within 100 ly", "Unconfirmed within 100 ly",
                  "Sources & Provenance")
LOG = HERE / "write_log.json"
PLAN = sys.argv[1:] == ["plan"]
# The thin grey rule every unmarked data cell on these tabs wears (read back with get_borders()).
GREY_RULE = "FFBFBFBF"

# ------------------------------------------------------------------ published inputs
T_SUN = 5772.0                 # K, IAU 2015 nominal
RSUN_AU = 0.00465047           # IAU 2015 nominal solar radius in au
VDB = ("van den Besselaar et al. 2007, A&A 466, 1031 (arXiv:astro-ph/0701560)")
HAN = ("Han et al. 2018, ApJ 868, 53 (doi:10.3847/1538-4357/aae64d)")
WD = dict(mass=0.51, radius=0.0136, r_lo=0.0134, r_hi=0.0144, teff=8000.0, t_lo=7000.0, t_hi=9000.0)
RD = dict(mass=0.41, radius=0.37, r_lo=0.363, r_hi=0.43, teff=3400.0)
A_RSUN = 2.07                  # orbital separation, van den Besselaar et al. 2007 Sect. 4.1 (+0.09 / -0.04)


def lum(r, t):
    return r * r * (t / T_SUN) ** 4


L_WD = round(lum(WD["radius"], WD["teff"]), 6)
L_WD_LO, L_WD_HI = lum(WD["r_lo"], WD["t_lo"]), lum(WD["r_hi"], WD["t_hi"])
L_RD = round(lum(RD["radius"], RD["teff"]), 5)
L_RD_LO, L_RD_HI = lum(RD["r_lo"], RD["teff"]), lum(RD["r_hi"], RD["teff"])
SEP_AU = round(A_RSUN * RSUN_AU, 5)

NOTE_L_WD = (
    f"INFERRED from published white-dwarf parameters: L = R^2 (Teff/5772 K)^4 with R = 0.0136 (+0.0008/-0.0002) Rsun "
    f"from the eclipse solution and Teff = 8000 +/- 1000 K from the composite-spectrum fit, both {VDB}. "
    f"= {L_WD:.6f} Lsun; the Teff uncertainty dominates, spanning {L_WD_LO:.5f} - {L_WD_HI:.5f}. "
    "The M-dwarf M_abs relation used elsewhere on this sheet does NOT apply to a white dwarf.")
NOTE_L_RD = (
    f"INFERRED from published parameters: L = R^2 (Teff/5772 K)^4 with R = 0.37 (+0.06/-0.007) Rsun ({VDB}, Sect. 4.1) "
    f"and Teff = 3400 K, the value {HAN}, Sect. 4.2, adopt for an M3 V star to compute this same luminosity "
    f"(they print the formula, not the number). = {L_RD:.4f} Lsun; the radius range alone gives "
    f"{L_RD_LO:.4f} - {L_RD_HI:.4f}. WEAK on Teff: 3400 K is a spectral-type value, not a fit to this star.")
NOTE_T_RD = (f"SOURCE: {HAN}, Sect. 4.2: 'Using T2 = 3400 K for the secondary star with a spectral type of M3V'. "
             f"Adopted for the spectral type (M3 V, {VDB}), not measured for this star.")
NOTE_SYS_N = (
    "TYPED 2026-09-28, CORRECTED the same day (run 7): this cell held 0.0172, the white dwarf and red dwarf together "
    f"(L_A + L_B = {L_WD + L_RD:.4f}), beside the white dwarf's own Teff. It now holds the white dwarf's (host, DE CVn A) "
    "alone, as RR Cae's row does; the red dwarf is DE CVn B on Multi-stars. " + NOTE_L_WD)
NOTE_UN_H = (
    f"The PAIR's luminosity, kept deliberately (run 7, 2026-09-28): DE CVn b is circumbinary, so both stars light it. "
    f"DE CVn A {L_WD:.6f} + DE CVn B {L_RD:.4f} = {L_WD + L_RD:.4f} Lsun (Multi-stars column P). The Systems row's "
    "Host luminosity is the white dwarf's alone.")
SEP_SOURCE = (
    f"{VDB}, Sect. 4.1: orbital separation a = 2.07 (+0.09/-0.04) Rsun from the eclipse + RV solution "
    f"(= {SEP_AU} au at 1 Rsun = 0.00465047 au); P = 0.3641394 d eclipsing binary, i = 86 deg; "
    "e = 0.02 +/- 0.02, so a circular orbit is assumed. Han et al. 2018 recompute a = 2.09 Rsun by Kepler's third law.")
STAR_SRC_A = (f"class, mass: {VDB} (DA; 0.51 +0.06/-0.02 Msun); Teff: same paper, 8000 +/- 1000 K; "
              "L: INFERRED from R and Teff -- orange box, method in the note")
STAR_SRC_B = (f"class, mass: {VDB} (M3 V; 0.41 +/- 0.06 Msun); Teff: {HAN}, Sect. 4.2 (adopted for M3 V); "
              "L: INFERRED from R and Teff -- orange box, method in the note")
SYSTEM_STARS = ("DE CVn A: DA (host, white dwarf, circumbinary planet orbits AB)\n"
                "DE CVn B: M3 V (red dwarf, circumbinary planet orbits AB)")
HOST_CLASS = "DA+dM"


# ------------------------------------------------------------------ sheet helpers
def q(t):
    return "'" + t.replace("'", "''") + "'"


def letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def values(rng, formula=False):
    return API.values().get(spreadsheetId=SID, range=rng,
                            valueRenderOption="FORMULA" if formula else "UNFORMATTED_VALUE").execute().get("values", [])


def H(tab):
    """{header: column letter}, matched by header text as the loader does."""
    return {h: letter(i) for i, h in enumerate(values(f"{q(tab)}!A1:AZ1")[0])}


def row_of(tab, name, col="A"):
    v = values(f"{q(tab)}!{col}1:{col}2000")
    hits = [i + 1 for i, r in enumerate(v) if r and r[0] == name]
    assert len(hits) == 1, (tab, name, hits)
    return hits[0]


def last_data_row(tab):
    """Data ends at the first row with at most one filled cell (the loader's rule)."""
    v = values(f"{q(tab)}!A1:E2000")
    n = 1
    for i, r in enumerate(v[1:], start=2):
        if sum(1 for c in r if str(c).strip()) <= 1:
            break
        n = i
    return n


def sheet_id(tab):
    return gs._sheet_ids(SID)[tab]


def grid(tab, r0, r1, c0, c1):
    return {"sheetId": sheet_id(tab), "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def batch(reqs):
    if reqs:
        API.batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()
    gs.invalidate_cache(SID)


def extend_filter(tab, end_row):
    f = [s for s in API.get(spreadsheetId=SID, fields="sheets(properties(title),basicFilter)").execute()["sheets"]
         if s["properties"]["title"] == tab][0].get("basicFilter")
    if f and f["range"].get("endRowIndex") != end_row:
        batch([{"setBasicFilter": {"filter": dict(f, range=dict(f["range"], endRowIndex=end_row))}}])


def main():
    assert not LOG.exists(), "run 7 already written; see write_log.json"
    hs, hm, hu = H(SY), H(MS), H(UN)
    assert not [r for r in values(f"{q(MS)}!B1:B2000") if r and r[0].startswith("DE CVn")], "DE CVn already on Multi-stars"

    # ---- Systems row: the source of the values the star rows repeat
    sr = row_of(SY, "DE CVn")
    srow = values(f"{q(SY)}!A{sr}:AP{sr}")[0]
    sv = {h: (srow[i] if i < len(srow) else "") for i, h in enumerate(values(f"{q(SY)}!A1:AP1")[0])}
    assert sv["Stars in system"] == 1 and sv["Host luminosity (L-sun)"] == 0.0172 and sv["Effective temp (K)"] == 8000
    assert sv["Host mass (M-sun)"] == 0.51 and sv["Stellar Class"] == "DA", sv

    def sc(h):
        return f"{q(SY)}!{hs[h]}{sr}"

    sys_upd = {sc("Stars in system"): 2, sc("System stars"): SYSTEM_STARS,
               sc("Host luminosity (L-sun)"): L_WD, sc("Planet-host class"): HOST_CLASS}
    sys_exp = {sc("Stars in system"): 1, sc("System stars"): "", sc("Host luminosity (L-sun)"): 0.0172,
               sc("Planet-host class"): ""}

    # ---- Unconfirmed: DE CVn b's host class; its host luminosity stays the pair's
    ur = row_of(UN, "DE CVn b")
    un_upd = {f"{q(UN)}!{hu['Planet-host class']}{ur}": HOST_CLASS}
    un_exp = {f"{q(UN)}!{hu['Planet-host class']}{ur}": "", f"{q(UN)}!{hu['Host luminosity (L-sun)']}{ur}": 0.0172,
              f"{q(UN)}!A{ur}": "DE CVn b"}

    # ---- Multi-stars: two rows, A then B (a parent precedes its child)
    common = {"System / Host": "DE CVn", "Distance (ly)": sv["Distance (ly)"], "Stars in system": 2,
              "Confirmed planets": sv["Confirmed planets"], "Planet-host star": "DE CVn",
              "Planet-host class": HOST_CLASS, "Primary mass (M-sun)": WD["mass"],
              "Planets in HZ": 0, "HZ planet names": "—"}
    star_a = dict(common, **{
        "Star (component)": "DE CVn A", "Role in system": "host, white dwarf, circumbinary planet orbits AB",
        "Mass (M-sun)": WD["mass"], "Stellar Class": "DA", "Effective temp (K)": int(WD["teff"]),
        "Star data source": STAR_SRC_A, "Luminosity (L-sun)": L_WD,
        "HZ distance": "Teff outside 2600-7200 K\n(Kopparapu limits do not apply)",
        # the pair is one Gaia source; the host row carries its astrometry, as RR Cae A's does
        "Radial velocity (km/s)": sv["Radial velocity (km/s)"],
        "Proper motion in RA, μα·cos δ (mas/yr)": sv["Proper motion in RA, μα·cos δ (mas/yr)"],
        "Proper motion in Dec, μδ (mas/yr)": sv["Proper motion in Dec, μδ (mas/yr)"],
        "Total proper motion, μ (arcsec/yr)": sv["Total proper motion, μ (arcsec/yr)"],
        "Space velocity (km/s)": sv["Space velocity (km/s)"],
        "Kinematics source": sv["Kinematics source"], "Gaia DR3 source_id": str(sv["Gaia DR3 source_id"])})
    star_b = dict(common, **{
        "Star (component)": "DE CVn B", "Role in system": "red dwarf, circumbinary planet orbits AB",
        "Mass (M-sun)": RD["mass"], "Stellar Class": "M3 V", "Class (sort key)": 63,
        "Effective temp (K)": int(RD["teff"]), "Star data source": STAR_SRC_B, "Luminosity (L-sun)": L_RD,
        "HZ distance": "circumbinary planet orbits A+B\n(HZ not computed per star)",
        "Separation from": "DE CVn A", "Separation (AU)": SEP_AU, "Separation type": "semi-major axis",
        "Separation source": SEP_SOURCE})
    for rec in (star_a, star_b):
        missing = set(rec) - set(hm)
        assert not missing, missing

    tmpl = row_of(MS, "alf Cen B", "B")
    tf = values(f"{q(MS)}!A{tmpl}:AZ{tmpl}", formula=True)[0]
    formula_cols = {letter(i) for i, c in enumerate(tf) if str(c).startswith("=")}
    # HZ distance is a Planets lookup in the template; with no Planets row it would read "not a planet host",
    # so it is typed, as RR Cae's rows are.
    typed = [c for c in hm.values() if c not in formula_cols or c == hm["HZ distance"]]
    last = last_data_row(MS)
    n = 2
    rows = {"DE CVn A": last + 1, "DE CVn B": last + 2}
    ms_upd = {}
    for rec in (star_a, star_b):
        r = rows[rec["Star (component)"]]
        for h, c in hm.items():
            if c in typed:
                ms_upd[f"{q(MS)}!{c}{r}"] = rec.get(h, "")
    orange = [f"{q(SY)}!{hs['Host luminosity (L-sun)']}{sr}",
              f"{q(MS)}!{hm['Luminosity (L-sun)']}{rows['DE CVn A']}",
              f"{q(MS)}!{hm['Luminosity (L-sun)']}{rows['DE CVn B']}"]
    # the template's own marking on 'Separation (AU)' is pasted with it; these rows' separation is published
    unmark = [f"{q(MS)}!{hm['Separation (AU)']}{r}" for r in rows.values()]
    # and so are the template's notes, which say nothing true of these rows
    note_cols = [c.rstrip("0123456789") for c in gs.get_notes(SID, f"{q(MS)}!A{tmpl}:AZ{tmpl}")]
    notes = {f"{q(MS)}!{c}{r}": "" for c in note_cols for r in rows.values()}
    notes.update({
        f"{q(SY)}!{hs['Host luminosity (L-sun)']}{sr}": NOTE_SYS_N,
        f"{q(MS)}!{hm['Luminosity (L-sun)']}{rows['DE CVn A']}": NOTE_L_WD,
        f"{q(MS)}!{hm['Luminosity (L-sun)']}{rows['DE CVn B']}": NOTE_L_RD,
        f"{q(MS)}!{hm['Effective temp (K)']}{rows['DE CVn B']}": NOTE_T_RD,
        f"{q(UN)}!{hu['Host luminosity (L-sun)']}{ur}": NOTE_UN_H,
    })

    lines = [
        "",
        "RUN 7, 28 SEPTEMBER 2026: DE CVn RECORDED AS A BINARY -- DA WHITE DWARF (A, host) + M3 V RED DWARF (B).",
        "Writer: data/unconfirmed_search/run7/write7.py; log write_log.json. Modelled on RR Cae (the other WD + dM",
        "eclipsing binary with a circumbinary planet): Multi-stars rows DE CVn A and B; B placed from A by 'Separation'.",
        "WHY: the Systems row paired the white dwarf's Teff (8000 K, run 4) with 0.0172 Lsun, which is the PAIR's",
        f"luminosity: L_A + L_B = {L_WD:.6f} + {L_RD:.4f} = {L_WD + L_RD:.4f}. The red dwarf outshines the white dwarf",
        f"{L_RD / L_WD:.0f} to 1, so the host's bands were computed from light that is not its own, and B was not drawn.",
        f"SOURCES: {VDB}: DA white dwarf 0.51 (+0.06/-0.02) Msun, 0.0136 (+0.0008/-0.0002) Rsun,",
        "  8000 +/- 1000 K (composite-spectrum fit); M3 V red dwarf 0.41 +/- 0.06 Msun, 0.37 (+0.06/-0.007) Rsun;",
        "  orbital separation 2.07 (+0.09/-0.04) Rsun, i = 86 deg, P = 0.3641394 d, e = 0.02 +/- 0.02 (circular assumed).",
        f"  The paper calls the white dwarf the primary. {HAN}, Sect. 4.2: T2 = 3400 K adopted for the M3 V secondary.",
        f"  Separation {A_RSUN} Rsun x 0.00465047 au/Rsun = {SEP_AU} au (unit conversion only; not marked).",
        "INFERRED (orange box + note): Luminosity for A and B, and Systems 'Host luminosity' (= A's), by L = R^2 (Teff/5772)^4",
        f"  on the published R and Teff. A = {L_WD:.6f} (range {L_WD_LO:.5f}-{L_WD_HI:.5f} from the Teff and R errors);",
        f"  B = {L_RD:.4f} (range {L_RD_LO:.4f}-{L_RD_HI:.4f} from R alone). B is WEAK on Teff: 3400 K is a spectral-type",
        "  value, not a fit. Valid for any star with a measured radius; no relation fitted, so no scatter to quote.",
        "  Not the M_abs relation: the pair is one unresolved Gaia source, and A is a white dwarf.",
        "UNCHANGED, deliberately: Systems Teff (8000 K, the host's); DE CVn b's Unconfirmed 'Host luminosity' (0.0172, the",
        "  pair's -- a circumbinary planet is lit by both; cell note added). Kinematics: the pair is one Gaia source,",
        "  so A's row repeats the Systems row's and B's is blank, as RR Cae's are.",
        "  Systems 'Stars in system' 1 -> 2, 'System stars' written, 'Planet-host class' DA+dM (and on DE CVn b's row).",
    ]

    if PLAN:
        print(f"Systems row {sr}, Unconfirmed row {ur}, Multi-stars template row {tmpl}, new rows {rows}")
        for c, v in {**sys_upd, **un_upd, **ms_upd}.items():
            if v != "":
                print(f"  WRITE {c} = {v!r}"[:230])
        print("  EXPECT", {**sys_exp, **un_exp})
        print("  ORANGE", orange)
        print("  GREY  ", unmark)
        for c, t in notes.items():
            print(f"  NOTE  {c}: {t[:150]!r}")
        print("\n".join(lines))
        return

    # 1. Multi-stars: paste the template (formulas and formats), then the typed values over it.
    rc = API.get(spreadsheetId=SID, ranges=[f"{q(MS)}!A1"], fields="sheets(properties(gridProperties))").execute()[
        "sheets"][0]["properties"]["gridProperties"]["rowCount"]
    if last + n > rc:
        batch([{"appendDimension": {"sheetId": sheet_id(MS), "dimension": "ROWS", "length": last + n - rc}}])
    assert not values(f"{q(MS)}!A{last + 1}:B{last + n}")
    width = len(hm)
    batch([{"copyPaste": {"source": grid(MS, tmpl - 1, tmpl, 0, width), "destination": grid(MS, last, last + n, 0, width),
                          "pasteType": "PASTE_NORMAL"}}])
    gs.update_cells(SID, ms_upd, expect={f"{q(MS)}!B{tmpl}": "alf Cen B"})
    extend_filter(MS, last + n)
    # 2. Systems and Unconfirmed, each guarded by its current values.
    gs.update_cells(SID, sys_upd, expect=sys_exp)
    gs.update_cells(SID, un_upd, expect=un_exp)
    # 3. Markings and notes.
    gs.set_border(SID, unmark, GREY_RULE, style="SOLID")
    gs.set_border(SID, orange, gs.INFERRED_BORDER)
    gs.set_note(SID, notes)
    # 4. Sources & Provenance, appended below its last row (never values().append()).
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    nrows = meta["gridProperties"]["rowCount"]
    assert values(f"{q(SP)}!A{nrows}")[0][0].strip()
    start, end = nrows + 1, nrows + len(lines)
    batch([{"appendDimension": {"sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}])
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log = {"systems_row": sr, "unconfirmed_row": ur, "multistars_rows": rows, "sp_rows": [start, end],
           "L_A": L_WD, "L_B": L_RD, "separation_au": SEP_AU, "orange": orange, "title": title}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log, ensure_ascii=False))


if __name__ == "__main__":
    main()
