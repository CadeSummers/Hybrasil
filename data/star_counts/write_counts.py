# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the star-count audit's first four systems to the sheet: psi1 Dra, HD 155555, WD 1856+534 and GJ 896.

    python write_counts.py          plan: print every write; touches nothing
    python write_counts.py write    write, re-border, note, provenance, legend, rename

The audit (README.md, 4 Oct 2026) matched every Systems-tab host to the MSC. Re-checked against the literature on
6 Oct 2026, with the owner's choices:

- psi1 Dra 2 -> 4. C is the MSC's Ab, a solved orbit: Gullikson et al. 2015, ApJ 815, 62 (doi:10.1088/0004-637X/
  815/1/62), Table 2. D is the MSC's suspected Bb ('a?', a Hipparcos-Gaia DR2 proper-motion difference, nothing
  else), counted under the owner's rule for '?' companions and renamed so as not to collide with the planet
  psi1 Dra Bb. Endl et al. 2016 (ApJ 818, 34) model B's long-term RV trend as an outer body; D is drawn hollow
  (Separation type 'assumed') at the orbit those two signals imply together -- orange, WEAK, see D_METHOD.
- HD 155555 2 -> 3, and onto Multi-stars although it has no confirmed planet, as a candidate host (the owner's
  choice; the other candidate-only multiples follow later, see README.md). The tab's A + B is the 1.68 d SB2 pair
  (V824 Ara; Dunstone et al. 2008, MNRAS, doi:10.1111/j.1365-2966.2008.13196.x, Table 1) and C is LDS 587 B
  (Messina et al. 2015, New Astron. 37, 105, doi:10.1016/j.newast.2014.12.007). The MSC calls the pair Aa,Ab and
  the M dwarf B; this keeps the tab's own A/B and the literature's C.
- WD 1856+534 2 -> 3: count only, its three rows already exist.
- GJ 896 stays 2, with a note. The MSC's Aa,Ab and Ba,Bb rest on Delfosse et al. 1999's spectroscopic flags, which
  Reyle et al. 2021 (A&A 650, A201, the 10 pc catalogue's notes on EQ Peg A and B) call 'almost certainly due to
  activity'; Curiel et al. 2022 (AJ 164, 93) fit A's astrometric acceleration with B's pull plus the planet.

Rows by name, every value write guarded by `expect`. Pasted rows are re-ruled cell by cell, their notes cleared,
and then EVERY coloured box on Multi-stars is redrawn by name, because re-ruling a cell strips the shared edge off
the box next to it. The basic filter is extended over the new rows.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data" / "four_plus_stars"))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)
from build import GREY_RULE  # noqa: E402  (this tab's plain rule; gs.PLAIN_RULE is black)

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
MS, SY, SP, LG = "Multi-stars within 100 ly", "Systems within 100 ly", "Sources & Provenance", "Legend & Notes"
LOG = HERE / "write_counts_log.json"
DATE = "6 Oct 2026"
R_SUN_AU = 0.00465047
T_SUN = 5772.0
ORANGE = "FF9900"

# ── psi1 Dra ───────────────────────────────────────────────────────────────────────────────────────────────────
PSI = "psi1 Dra A"
PSI_C, PSI_D = "psi1 Dra C", "psi1 Dra D"
G15 = "Gullikson et al. 2015, ApJ 815, 62 (doi:10.1088/0004-637X/815/1/62), Table 2"
PSI_C_ORBIT = (f"{G15}: P = 6774 (+271/-167) d, e = 0.679 (+0.006/-0.004), omega = 32.6 +/- 0.7 deg, "
               "i = 31 +/- 1 deg, T0 = JD 2450388 (+169/-273), K2 = 11.1 +/- 0.2 km/s")
PSI_C_SRC = (f"{G15}: true mass 0.70 +/- 0.07 M-sun (i = 31 deg from RV + speckle), Teff 4400 +/- 300 K (from the "
             "mass, by isochrone). = the MSC's psi1 Dra Ab (WDS 17419+7209, 'S1,a,v', 0.16 arcsec, 18.2 yr); "
             "first seen as a ~4500 K companion 155 mas from A. No luminosity published. Added " + DATE + ".")
# psi1 Dra D, an assumed orbit (the owner's choice, 6 Oct 2026) from two measured signals of one unseen body:
#   the MSC's Hipparcos-Gaia DR2 proper-motion difference for B, dmu = (-0.2, 0.9) mas/yr, at B's parallax (MSC,
#   44.05 mas) -> a tangential velocity anomaly dv; and Endl et al. 2016's linear RV trend for B, 0.032 m/s/day
#   (Table 7) -> an acceleration g.  On a circular orbit the reflex speed and acceleration share one angular rate,
#   Omega = g / dv, so r = (G M_B / Omega^2)^(1/3) and m = dv M_B / sqrt(G M_B / r), with M_B = 1.19 (this tab).
#   Both inputs are projections (lower bounds) and the proper-motion difference is averaged over ~24 yr, so the
#   result is good to a factor of a few.  Check: it predicts B's RV curvature dv Omega^2, against Endl's quadratic
#   term of 4.1e-6 m/s/day^2.
DMU_MAS_YR, PLX_B_MAS, M_B, TREND_M_S_DAY, CURV_M_S_DAY2 = math.hypot(-0.2, 0.9), 44.05, 1.19, 0.032, 4.1e-6
G_SI, MSUN_KG, AU_M, MJUP_KG, DAY_S, YR_S = 6.674e-11, 1.98892e30, 1.495978707e11, 1.89813e27, 86400.0, 3.15576e7
_dv = 4.74047 * DMU_MAS_YR / PLX_B_MAS * 1000
_om = TREND_M_S_DAY / DAY_S / _dv
_r = (G_SI * M_B * MSUN_KG / _om ** 2) ** (1 / 3)
_m = _dv * M_B / math.sqrt(G_SI * M_B * MSUN_KG / _r)
D_SEP_AU, D_MASS = round(_r / AU_M, 1), round(_m, 4)
D_MJ, D_P_YR, D_CURV = _m * MSUN_KG / MJUP_KG, 2 * math.pi / _om / YR_S, _dv * _om ** 2 * DAY_S ** 2
D_METHOD = (f"B's proper-motion anomaly (MSC: Hipparcos-Gaia DR2 dmu = (-0.2, 0.9) mas/yr at 44.05 mas, dv = "
            f"{_dv:.1f} m/s) and B's RV trend (Endl et al. 2016, ApJ 818, 34, Table 7: 0.032 m/s/day) read as one "
            f"circular orbit: Omega = g/dv, r = (G M_B / Omega^2)^(1/3) = {D_SEP_AU} AU, m = dv M_B / v_orb = "
            f"{D_MASS} M-sun ({D_MJ:.1f} MJ), P = {D_P_YR:.0f} yr, with M_B = {M_B}")
D_WEAK = ("WEAK: an assumed orbit for a body nothing has resolved; both inputs are projections and the "
          "proper-motion difference is averaged over ~24 yr, so good to a factor of a few.")
D_SEP_NOTE = (f"{D_WEAK}\nINFERRED: {D_METHOD}. Check: it predicts B's RV curvature at {D_CURV:.1e} m/s/day^2 "
              f"against Endl's measured {CURV_M_S_DAY2:.1e}. Endl's Fig. 17 finds periods beyond 10^4 d degenerate "
              "in mass, as this one is.")
D_MASS_NOTE = (f"{D_WEAK}\nINFERRED with the separation: {D_METHOD}. {D_MJ:.1f} MJ is a brown dwarf just above "
               "the deuterium limit; a planet if the projections hide less than assumed.")
PSI_D_SRC = ("SUSPECTED companion of psi1 Dra B. MSC (Tokovinin 2018, VizieR J/ApJS/235/6, Dec 2023), WDS "
             "17419+7209 pair Ba,Bb, type 'a?': a Hipparcos-Gaia DR2 proper-motion difference, dmu = (-0.2, 0.9) "
             "mas/yr; no period, separation or mass measured. Endl et al. 2016, ApJ 818, 34, model B's long-term "
             "RV trend as an outer body 'psi1 Dra Bc'; this is that body. Mass and separation INFERRED from the two "
             "-- orange border, see the notes. Counted under the owner's rule for MSC '?' companions (4 Oct 2026), "
             "drawn hollow at the assumed separation. Named D, not Bb, because psi1 Dra Bb is the planet (Endl et "
             "al. 2016). Added " + DATE + ".")

# ── HD 155555 ──────────────────────────────────────────────────────────────────────────────────────────────────
H5 = "HD 155555"
H5A, H5B, H5C = f"{H5} A", f"{H5} B", f"{H5} C"
D08 = "Dunstone et al. 2008, MNRAS (doi:10.1111/j.1365-2966.2008.13196.x)"
M15 = "Messina et al. 2015, New Astron. 37, 105 (doi:10.1016/j.newast.2014.12.007)"
DUN = dict(m1=1.054, m2=0.986, r1=1.47, r2=1.32, t1=5300, t2=5050, a_rsun=7.5)
L_A = round(DUN["r1"] ** 2 * (DUN["t1"] / T_SUN) ** 4, 3)
L_B = round(DUN["r2"] ** 2 * (DUN["t2"] / T_SUN) ** 4, 3)
A_AB = round(DUN["a_rsun"] * R_SUN_AU, 4)
# Gaia DR3 (VizieR I/355/gaiadr3, queried 6 Oct 2026), epoch 2016.0
GA = dict(src="5811866422581688320", ra=259.35602884633, dec=-66.95164636305, plx=32.9511)
GC = dict(src="5811866358170877184", ra=259.38019925412, dec=-66.95216506016, plx=32.8822, pmra=-14.851,
          pmde=-145.204)
RHO_AC = math.hypot((GC["ra"] - GA["ra"]) * math.cos(math.radians((GA["dec"] + GC["dec"]) / 2)),
                    GC["dec"] - GA["dec"]) * 3600
SEP_AC = round(RHO_AC / (GA["plx"] / 1000), 1)
H5_ORBIT = (f"{D08}, Table 1: P = 1.6816463 d (Strassmeier & Rice 2000), e = 0 (adopted), i = 52 deg (adopted), "
            "K1 = 86.4 +/- 0.1, K2 = 94.7 +/- 0.2 km/s, q = 0.935")
H5_SEP_AB = f"{D08}, Sect. 7.6: binary separation 7.5 R-sun (= {A_AB} AU)"
H5_SEP_AC = (f"Gaia DR3 gaia_source positions and primary parallax, queried 2026-10-06: rho {RHO_AC:.2f} arcsec, "
             f"plx(A) {GA['plx']} mas")
H5A_SRC = (f"{D08}, Table 1: m = {DUN['m1']} M-sun (i = 52 deg), R = {DUN['r1']} R-sun, Teff = {DUN['t1']} +/- 100 K "
           "(SME). Class: SB9 (Pourbaix et al. 2004) no. 951, G5IV + K0IV-V (SIMBAD: G5V+K1V). L: INFERRED, NOT "
           "PUBLISHED -- orange border. Young (beta Pic moving group; 18 Myr, Dunstone et al. 2008).")
H5B_SRC = (f"{D08}, Table 1: m = {DUN['m2']} M-sun (i = 52 deg), R = {DUN['r2']} R-sun, Teff = {DUN['t2']} +/- 100 K "
           "(SME). Class: SB9 no. 951. L: INFERRED, NOT PUBLISHED -- orange border. = the MSC's HD 155555 Ab "
           "(WDS 17174-6657); this tab keeps the Systems tab's A/B for the SB2 pair.")
H5C_SRC = (f"{M15}: M3.5 (Pasquini et al. 1991), Teff 3300 +/- 100 K (SED), L = 0.042 +/- 0.005 L-sun at the "
           "Hipparcos 31.4 pc (0.039 at Gaia DR3's 30.35 pc; entered as published), mass 0.25 M-sun (D'Antona & "
           "Mazzitelli 1997 tracks). = LDS 587 B = 2MASS J17173128-6657055 = the MSC's HD 155555 B. MSC: "
           "common proper motion, 'Cmpr'.")
H5_ROLE_A = "host, candidate planet host (circumbinary candidate HD 155555 (AB) b, Unconfirmed tab)"
H5_ROLE_B = "companion; the candidate planet would orbit A + B"
H5_ROLE_C = "companion"
H5_NAMES_SYS = (f"{H5A}: G5 IV (host, candidate planet host)\n{H5B}: K0 IV-V (companion, 1.68 d SB2 with A)\n"
                f"{H5C}: M3.5 V (companion, LDS 587 B)")

L_NOTE = ("INFERRED from Dunstone et al. 2008's radius and Teff: L = R^2 (Teff / 5772 K)^4 = {r}^2 x ({t} / 5772)^4 "
          "= {l}. Both come from a fit that assumed i = 52 deg; Teff +/- 100 K alone is +/- 8% in L. No published "
          "component luminosity found; the Systems tab's 1.958 is for the unresolved pair.")
SEP_AC_NOTE = (f"INFERRED: Gaia DR3 projected separation, rho {RHO_AC:.2f} arcsec x {1000 / GA['plx']:.2f} pc "
               f"(A's parallax). C's own parallax is {GC['plx']} mas. MSC: 34 arcsec.")

NOTES_STARS = {
    "GJ 896 A": ("2 stars, checked " + DATE + ". The MSC (WDS 23319+1956) also lists Aa,Ab ('s1,a') and Ba,Bb "
                 "('s1?') from Delfosse et al. 1999 (A&A 344, 897); they are not counted. Reyle et al. 2021 (A&A "
                 "650, A201; the 10 pc catalogue's notes on EQ Peg A and on B): 'The spectroscopic binarity "
                 "classification proposed by 1999A&A...344..897D is almost certainly due to activity'. A's "
                 "astrometric acceleration is B's pull: Curiel et al. 2022 (AJ 164, 93) fit it with B plus the "
                 "planet GJ 896 A b."),
    PSI: ("4 stars since " + DATE + ": A, B, C (= the MSC's Ab; orbit from Gullikson et al. 2015) and D (the MSC's "
          "suspected Ba,Bb 'a?', the outer body behind B's RV trend in Endl et al. 2016; drawn hollow at an "
          f"assumed {D_SEP_AU} AU, mass {D_MASS} M-sun, both inferred). Was 2."),
    "WD 1856+534": ("3 stars since " + DATE + ": WD 1856+534 and G 229-20 A and B, all already listed; the count "
                    "said 2. MSC WDS 18576+5331: AB,C and A,B both common proper motion."),
    H5: ("3 stars since " + DATE + ": the 1.68 d SB2 pair A + B (V824 Ara) and C = LDS 587 B, 34 arcsec off. MSC "
         "WDS 17174-6657, which names them Aa, Ab and B; its A,C pair is optical and not counted. On Multi-stars "
         "as a candidate host (HD 155555 (AB) b, Unconfirmed tab), with no confirmed planet. Was 2."),
}
NEW_COUNT = {PSI: 4, "WD 1856+534": 3, H5: 3}


def values(tab, how="UNFORMATTED_VALUE"):
    return API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:AZ3000", valueRenderOption=how
                            ).execute().get("values", [])


def cell(row, c):
    return row[c] if c < len(row) else ""


def rows_of(data, system):
    return [i + 1 for i, r in enumerate(data) if r and r[0] == system]


def row_of(data, comp_col, comp):
    rr = [i + 1 for i, r in enumerate(data) if cell(r, comp_col) == comp]
    assert len(rr) == 1, (comp, rr)
    return rr[0]


def class_key(sp):
    """'G5 IV' -> 45, as the tab's Class (sort key) column: O0 B10 A20 F30 G40 K50 M60, plus the subtype."""
    base = {"O": 0, "B": 10, "A": 20, "F": 30, "G": 40, "K": 50, "M": 60}[sp[0]]
    return base + float(sp[1:].split()[0])


def planned_rows(ms, mc, sy, sc):
    """[(insert after this component, template component, {header: value})], in write order."""
    psi = {h: cell(ms[row_of(ms, mc["Star (component)"], PSI) - 1], mc[h]) for h in mc}
    s5 = sy[rows_of(sy, H5)[0] - 1]
    sys5 = {h: cell(s5, sc[h]) for h in sc}
    psi_common = {"System / Host": PSI, "Distance (ly)": psi["Distance (ly)"], "Stars in system": NEW_COUNT[PSI],
                  "Confirmed planets": psi["Confirmed planets"], "Age (Gyr)": psi["Age (Gyr)"],
                  "Planet masses (M-earth)": psi["Planet masses (M-earth)"], "Mass type": psi["Mass type"],
                  "Planet-host star": psi["Planet-host star"], "Planet-host class": psi["Planet-host class"],
                  "Primary mass (M-sun)": psi["Primary mass (M-sun)"]}
    h5_common = {"System / Host": H5, "Distance (ly)": sys5["Distance (ly)"], "Stars in system": NEW_COUNT[H5],
                 "Confirmed planets": 0, "Planet-host star": sys5["Planet-host star"],
                 "Planet-host class": sys5["Planet-host class"], "Primary mass (M-sun)": sys5["Host mass (M-sun)"]}
    pm_c = round(math.hypot(GC["pmra"], GC["pmde"]) / 1000, 3)
    return [
        (PSI, PSI, dict(psi_common, **{
            "Star (component)": PSI_C, "Role in system": "companion of psi1 Dra A", "Mass (M-sun)": 0.70,
            "Effective temp (K)": 4400, "Star data source": PSI_C_SRC, "Orbital eccentricity (e)": 0.679,
            "Orbit described": f"{PSI} + {PSI_C}", "Orbit source": PSI_C_ORBIT, "Separation from": PSI,
            "Separation (AU)": 9.1, "Separation type": "semi-major axis", "Separation source": PSI_C_ORBIT})),
        ("psi1 Dra B", PSI, dict(psi_common, **{
            "Star (component)": PSI_D, "Role in system": "suspected companion of psi1 Dra B (MSC 'a?'; a brown "
                                                         "dwarf or giant planet)",
            "Mass (M-sun)": D_MASS, "Star data source": PSI_D_SRC, "Orbital eccentricity (e)": 0,
            "Orbit described": f"psi1 Dra B + {PSI_D}", "Orbit source": "assumed circular; see the Separation note",
            "Separation from": "psi1 Dra B", "Separation (AU)": D_SEP_AU, "Separation type": "assumed",
            "Separation source": D_METHOD})),
        # HD 155555: after the last 3-star system nearer than it, so the tab stays in its sort order
        (None, PSI, dict(h5_common, **{
            "Star (component)": H5A, "Role in system": H5_ROLE_A, "Mass (M-sun)": DUN["m1"], "Stellar Class": "G5 IV",
            "Class (sort key)": class_key("G5 IV"), "Effective temp (K)": DUN["t1"], "Star data source": H5A_SRC,
            "Luminosity (L-sun)": L_A, "Radial velocity (km/s)": sys5["Radial velocity (km/s)"],
            "Proper motion in RA, μα·cos δ (mas/yr)": sys5["Proper motion in RA, μα·cos δ (mas/yr)"],
            "Proper motion in Dec, μδ (mas/yr)": sys5["Proper motion in Dec, μδ (mas/yr)"],
            "Total proper motion, μ (arcsec/yr)": sys5["Total proper motion, μ (arcsec/yr)"],
            "Space velocity (km/s)": sys5["Space velocity (km/s)"], "Kinematics source": sys5["Kinematics source"],
            "Gaia DR3 source_id": str(sys5["Gaia DR3 source_id"])})),
        (H5A, PSI, dict(h5_common, **{
            "Star (component)": H5B, "Role in system": H5_ROLE_B, "Mass (M-sun)": DUN["m2"], "Stellar Class": "K0 IV-V",
            "Class (sort key)": class_key("K0 IV-V"), "Effective temp (K)": DUN["t2"], "Star data source": H5B_SRC,
            "Luminosity (L-sun)": L_B, "Orbital eccentricity (e)": 0, "Orbit described": f"{H5A} + {H5B}",
            "Orbit source": H5_ORBIT, "Separation from": H5A, "Separation (AU)": A_AB,
            "Separation type": "semi-major axis", "Separation source": H5_SEP_AB})),
        (H5B, PSI, dict(h5_common, **{
            "Star (component)": H5C, "Role in system": H5_ROLE_C, "Mass (M-sun)": 0.25, "Stellar Class": "M3.5 V",
            "Class (sort key)": class_key("M3.5 V"), "Effective temp (K)": 3300, "Star data source": H5C_SRC,
            "Luminosity (L-sun)": 0.042, "Proper motion in RA, μα·cos δ (mas/yr)": GC["pmra"],
            "Proper motion in Dec, μδ (mas/yr)": GC["pmde"], "Total proper motion, μ (arcsec/yr)": pm_c,
            "Kinematics source": "PM: Gaia DR3", "Gaia DR3 source_id": GC["src"], "Separation from": H5A,
            "Separation (AU)": SEP_AC, "Separation type": "projected", "Separation source": H5_SEP_AC})),
    ]


def orange_cells():
    """{(component, header): note} for the inferred values this script writes."""
    return {(H5A, "Luminosity (L-sun)"): L_NOTE.format(r=DUN["r1"], t=DUN["t1"], l=L_A),
            (H5B, "Luminosity (L-sun)"): L_NOTE.format(r=DUN["r2"], t=DUN["t2"], l=L_B),
            (H5C, "Separation (AU)"): SEP_AC_NOTE,
            (PSI_D, "Mass (M-sun)"): D_MASS_NOTE,
            (PSI_D, "Separation (AU)"): D_SEP_NOTE}


def h5_anchor(ms, mc, sy, sc):
    """The component after which HD 155555's rows go: the last row of 3 stars no farther than it."""
    dist = float(sy[rows_of(sy, H5)[0] - 1][sc["Distance (ly)"]])
    best = None
    for r in ms[1:]:
        if r and cell(r, mc["Stars in system"]) == 3 and float(cell(r, mc["Distance (ly)"])) <= dist:
            best = cell(r, mc["Star (component)"])
    return best


def main():
    props = {s["properties"]["title"]: s for s in
             API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties),basicFilter)"
                     ).execute()["sheets"]}
    ms, sy = values(MS), values(SY)
    mc, sc = {h: i for i, h in enumerate(ms[0])}, {h: i for i, h in enumerate(sy[0])}
    comp = mc["Star (component)"]
    have = {cell(r, comp) for r in ms[1:] if r}
    assert not have & {PSI_C, PSI_D, H5A, H5B, H5C}, have & {PSI_C, PSI_D, H5A, H5B, H5C}
    assert not rows_of(ms, H5), "HD 155555 is already on Multi-stars"
    for system, now in ((PSI, 2), ("WD 1856+534", 2), ("GJ 896 A", 2)):
        assert {cell(ms[i - 1], mc["Stars in system"]) for i in rows_of(ms, system)} == {now}, system
    for system in (PSI, "WD 1856+534", "GJ 896 A", H5):
        assert sy[rows_of(sy, system)[0] - 1][sc["Stars in system"]] == 2, system
    old_h5_text = sy[rows_of(sy, H5)[0] - 1][sc["System stars"]]
    old_psi_text = sy[rows_of(sy, PSI)[0] - 1][sc["System stars"]]
    assert "psi1 Dra C" not in old_psi_text and "LDS 587 B" not in old_h5_text
    new_psi_text = (old_psi_text + "\npsi1 Dra C: class unknown (companion of A; Teff 4400 K)"
                    "\npsi1 Dra D: class unknown (suspected companion of B, MSC 'a?'; assumed orbit)")

    plan = planned_rows(ms, mc, sy, sc)
    anchor = h5_anchor(ms, mc, sy, sc)
    plan[2] = (anchor,) + plan[2][1:]
    for _, _, vals in plan:
        assert set(vals) <= set(mc), set(vals) - set(mc)
    sp = sp_lines()
    lg = legend_lines()

    if PLAN:
        print(f"Multi-stars: {len(plan)} rows to insert (filter end row {props[MS]['basicFilter']['range']['endRowIndex']}"
              f" -> {props[MS]['basicFilter']['range']['endRowIndex'] + len(plan)})")
        for after, tmpl, vals in plan:
            at = [i + 1 for i, r in enumerate(ms) if cell(r, comp) == after]
            print(f"\n  after {after!r} (row {at[0] if at else 'new'}), template {tmpl!r}:")
            for h, v in vals.items():
                print(f"    {h:42.42} {v!r}"[:400])
        print("\nOrange (inferred) cells, each with a note:")
        for (c, h), n in orange_cells().items():
            print(f"  {c} / {h}: {n}")
        print("\nStars in system:")
        for s, n in NEW_COUNT.items():
            print(f"  {s}: Multi-stars rows {rows_of(ms, s) or '(new)'} and Systems row {rows_of(sy, s)} -> {n}")
        print("\nNotes on Stars in system (Multi-stars host row and Systems):")
        for s, n in NOTES_STARS.items():
            print(f"  {s}: {n}")
        print(f"\nSystems 'System stars', {PSI}:\n  {old_psi_text!r}\n  -> {new_psi_text!r}")
        print(f"Systems 'System stars', {H5}:\n  {old_h5_text!r}\n  -> {H5_NAMES_SYS!r}")
        print("\nSources & Provenance:\n" + "\n".join(sp))
        print("\nLegend & Notes:\n" + "\n".join(lg))
        return

    # ── writes ──────────────────────────────────────────────────────────────────────────────────────────────
    mid = props[MS]["properties"]["sheetId"]
    # Every coloured box on the tab, by name, before anything moves: redrawn at the end.
    last = max(i + 1 for i, r in enumerate(ms) if r and r[0])
    boxes = {}
    for a1, sides in gs.get_borders(SID, f"{q(MS)}!A2:{letter(len(ms[0]) - 1)}{last}").items():
        cols = {c for c, _ in sides.values()}
        if len(cols) == 1 and (col := cols.pop()) in (ORANGE, "FF3399") and len(sides) == 4:
            c, r = "".join(ch for ch in a1 if ch.isalpha()), int("".join(ch for ch in a1 if ch.isdigit()))
            boxes[(cell(ms[r - 1], comp), next(h for h, i in mc.items() if letter(i) == c))] = col
    for (c, h) in orange_cells():
        boxes[(c, h)] = ORANGE

    ncols = len(ms[0])
    inserted = []
    for after, tmpl, vals in plan:
        now = values(MS)
        at = row_of(now, comp, after)
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"insertDimension": {"range": {
            "sheetId": mid, "dimension": "ROWS", "startIndex": at, "endIndex": at + 1}, "inheritFromBefore": True}}]}
                        ).execute()
        src = row_of(values(MS), comp, tmpl)
        new = at + 1
        API.batchUpdate(spreadsheetId=SID, body={"requests": [
            {"copyPaste": {"source": {"sheetId": mid, "startRowIndex": src - 1, "endRowIndex": src,
                                      "startColumnIndex": 0, "endColumnIndex": ncols},
                           "destination": {"sheetId": mid, "startRowIndex": new - 1, "endRowIndex": new,
                                           "startColumnIndex": 0, "endColumnIndex": ncols},
                           "pasteType": "PASTE_NORMAL"}},
            {"updateCells": {"range": {"sheetId": mid, "startRowIndex": new - 1, "endRowIndex": new,
                                       "startColumnIndex": 0, "endColumnIndex": ncols},
                             "rows": [{"values": [{} for _ in range(ncols)]}], "fields": "note"}}]}).execute()
        gs.invalidate_cache(SID)
        formulas = API.values().get(spreadsheetId=SID, range=f"{q(MS)}!A{new}:{letter(ncols - 1)}{new}",
                                    valueRenderOption="FORMULA").execute()["values"][0]
        upd = {}
        for h, c in mc.items():
            if str(cell(formulas, c)).startswith("="):
                continue                               # keep the copied formula
            upd[f"{q(MS)}!{letter(c)}{new}"] = vals.get(h, "")
        gs.update_cells(SID, upd, expect={f"{q(MS)}!{letter(comp)}{new}": tmpl})
        inserted.append(vals["Star (component)"])

    # Re-rule every pasted cell to the tab's plain rule, then redraw every box by name.
    now = values(MS)
    new_rows = [row_of(now, comp, n) for n in inserted]
    gs.set_border(SID, [f"{q(MS)}!{letter(c)}{r}" for r in new_rows for c in range(ncols)], GREY_RULE, style="SOLID")
    for colour in sorted(set(boxes.values())):
        gs.set_border(SID, [f"{q(MS)}!{letter(mc[h])}{row_of(now, comp, c)}" for (c, h), col in boxes.items()
                            if col == colour], "FF" + colour)
    gs.set_note(SID, {f"{q(MS)}!{letter(mc[h])}{row_of(now, comp, c)}": n for (c, h), n in orange_cells().items()})

    # Stars in system: the systems already on the tab, then the notes.
    sic = letter(mc["Stars in system"])
    upd, exp = {}, {}
    for s in (PSI, "WD 1856+534"):
        for r in rows_of(now, s):
            if cell(now[r - 1], comp) in inserted:
                continue
            upd[f"{q(MS)}!{sic}{r}"] = NEW_COUNT[s]
            exp[f"{q(MS)}!{sic}{r}"] = 2
    gs.update_cells(SID, upd, expect=exp)
    host_row = {s: next(r for r in rows_of(now, s) if cell(now[r - 1], comp) in (s, H5A)) for s in NOTES_STARS}
    gs.set_note(SID, {f"{q(MS)}!{sic}{host_row[s]}": n for s, n in NOTES_STARS.items()})

    end = max(i + 1 for i, r in enumerate(now) if r and r[0])
    f = API.get(spreadsheetId=SID, fields="sheets(properties(title),basicFilter)").execute()["sheets"]
    flt = next(s for s in f if s["properties"]["title"] == MS)["basicFilter"]
    if flt["range"].get("endRowIndex") != end:
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"setBasicFilter": {
            "filter": dict(flt, range=dict(flt["range"], endRowIndex=end))}}]}).execute()

    # Systems.
    ssc, sst = letter(sc["Stars in system"]), letter(sc["System stars"])
    upd, exp = {}, {}
    for s, n in NEW_COUNT.items():
        r = rows_of(sy, s)[0]
        upd[f"{q(SY)}!{ssc}{r}"] = n
        exp[f"{q(SY)}!{ssc}{r}"] = 2
        exp[f"{q(SY)}!A{r}"] = s
    rp, r5 = rows_of(sy, PSI)[0], rows_of(sy, H5)[0]
    upd[f"{q(SY)}!{sst}{rp}"], exp[f"{q(SY)}!{sst}{rp}"] = new_psi_text, old_psi_text
    upd[f"{q(SY)}!{sst}{r5}"], exp[f"{q(SY)}!{sst}{r5}"] = H5_NAMES_SYS, old_h5_text
    gs.update_cells(SID, upd, expect=exp)
    gs.set_note(SID, {f"{q(SY)}!{ssc}{rows_of(sy, s)[0]}": n for s, n in NOTES_STARS.items()})

    # Sources & Provenance (grow the grid, never values().append()), then Legend & Notes.
    meta = props[SP]["properties"]
    sp_end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{sp_end}"])[f"{q(SP)}!A{sp_end}"][0][0].strip()
    sp0, sp1 = sp_end + 1, sp_end + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{sp0}:A{sp1}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (sp0, sp0 + 1, sp1)})
    lv = API.values().get(spreadsheetId=SID, range=f"{q(LG)}!A1:A3000").execute().get("values", [])
    lg0 = len(lv) + 2
    lg1 = lg0 + len(lg) - 1
    gs.update_cells(SID, {f"{q(LG)}!A{lg0}:A{lg1}": [[x] for x in lg]},
                    expect={f"{q(LG)}!A{lg0}": "", f"{q(LG)}!A{lg1}": ""})

    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log = {"inserted": {n: row_of(values(MS), comp, n) for n in inserted}, "filter_end_row": end,
           "boxes_redrawn": len(boxes), "sp_rows": [sp0, sp1], "legend_rows": [lg0, lg1], "title": title}
    LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
    print("done:", json.dumps(log))


def sp_lines():
    return [
        "",
        f"STAR COUNTS OF PLANET HOSTS, FIRST FOUR SYSTEMS, {DATE.upper()}: psi1 Dra, HD 155555, WD 1856+534, GJ 896",
        "  METHOD: every Systems-tab host matched by position (90 arcsec) to the Multiple Star Catalog (Tokovinin "
        "2018, ApJS 235, 6; VizieR J/ApJS/235/6, Dec 2023), stars = pairs + 1, optical 'X' pairs dropped, '?' pairs "
        "counted separately; then a Gaia DR3 co-moving search (El-Badry, Rix & Heintz 2021 cuts). Scripts and "
        "results: data/star_counts/ in the repo. Each disagreement was then checked in the literature. Done by "
        "Claude; the owner chose how to handle each.",
        f"  psi1 Dra (2 -> 4): psi1 Dra C added, = the MSC's Ab. Mass 0.70 +/- 0.07 M-sun, Teff 4400 K and the "
        f"orbit (P 6774 d, e 0.679, a 9.1 AU, i 31 deg) from {G15}, all as published. psi1 Dra D added for the MSC's "
        "suspected Ba,Bb ('a?', a Hipparcos-Gaia DR2 proper-motion difference only), counted under the owner's rule "
        f"for '?' companions; Endl et al. 2016 (ApJ 818, 34) model B's long-term RV trend as an outer body, and D is "
        f"that body. INFERRED (orange, WEAK): its mass {D_MASS} M-sun ({D_MJ:.1f} MJ) and separation {D_SEP_AU} AU. "
        f"METHOD: {D_METHOD}. Inputs: MSC (VizieR J/ApJS/235/6) for dmu and B's parallax; Endl et al. 2016 Table 7 "
        f"for the trend; this tab for M_B. SCATTER: both inputs are projections (lower bounds) and the proper-motion "
        f"difference is a ~24 yr average, so a factor of a few. CHECK: it predicts B's RV curvature at {D_CURV:.1e} "
        f"m/s/day^2 against Endl's measured {CURV_M_S_DAY2:.1e}. VALID: a single circular orbit with a period longer "
        "than the RV baseline (Endl's Fig. 17: beyond 10^4 d), as this is. Drawn hollow, Separation type 'assumed'. "
        "Named D because psi1 Dra Bb is Endl's planet.",
        f"  HD 155555 (2 -> 3): added to Multi-stars as a candidate host (HD 155555 (AB) b on Unconfirmed), with no "
        f"confirmed planet. A and B, the 1.68 d SB2 V824 Ara: masses, radii, Teff, orbit and the 7.5 R-sun "
        f"separation from {D08}, Table 1 and Sect. 7.6; classes from SB9 no. 951. INFERRED (orange): A's and B's "
        f"luminosities, L = R^2 (Teff/5772)^4 = {L_A} and {L_B}, exact arithmetic on the published R and Teff, whose "
        "+/- 100 K alone is +/- 8% in L; valid for these two stars only, and the radii assume i = 52 deg. C = LDS "
        f"587 B: M3.5, Teff 3300 K, L 0.042, 0.25 M-sun from {M15}; kinematics Gaia DR3 {GC['src']}. INFERRED "
        f"(orange): C's projected separation, rho {RHO_AC:.2f} arcsec (Gaia DR3 positions) x A's distance = "
        f"{SEP_AC} AU. The MSC names the stars Aa, Ab and B; the tab keeps the Systems tab's A/B for the pair and "
        "the literature's C. Systems 'System stars' rewritten to list all three.",
        "  WD 1856+534 (2 -> 3): count only. Its three rows (the white dwarf, G 229-20 A and B) were already on "
        "Multi-stars; MSC WDS 18576+5331 has AB,C and A,B, both common proper motion.",
        "  GJ 896 (stays 2): the MSC's Aa,Ab ('s1,a') and Ba,Bb ('s1?') rest on Delfosse et al. 1999 (A&A 344, "
        "897). Reyle et al. 2021 (A&A 650, A201; VizieR J/A+A/650/A201, notes on EQ Peg A and B): 'almost certainly "
        "due to activity'. Curiel et al. 2022 (AJ 164, 93) fit A's astrometric acceleration with B plus the planet. "
        "Not counted; noted on the Stars in system cells.",
        "  Notes on every changed 'Stars in system' cell say what changed. The other targets of the audit are "
        "not yet written.",
    ]


def legend_lines():
    return [
        f"STAR COUNTS OF PLANET HOSTS -- {DATE.upper()} (first four systems)",
        "An audit of every planet host's star count against the Multiple Star Catalog and Gaia DR3. psi1 Dra gained "
        "C (a solved orbit) and D (a suspected companion of B, drawn hollow at an assumed orbit); HD 155555 joined Multi-stars as a "
        "candidate host with three stars; WD 1856+534's count was corrected to 3; GJ 896 stays at 2, its "
        "catalogued spectroscopic companions being activity artefacts. Method and citations on Sources & "
        f"Provenance under 'STAR COUNTS OF PLANET HOSTS, FIRST FOUR SYSTEMS, {DATE.upper()}'.",
    ]


if __name__ == "__main__":
    main()
