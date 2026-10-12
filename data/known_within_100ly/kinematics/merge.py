# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Decide every motion cell the pipeline will fill, from the catalogs and the agents' research.

    python merge.py            targets + cat/*.json + ../agent_output/*.json -> merged.json; prints the counts
    python merge.py --check    validate every agent_output file against BRIEF.md's schema; writes nothing
    python merge.py --batch    after the bulk write (P3): the rows still missing RV or PM -> batches.json (once)

Precedence per row, per input (a value already on the sheet always wins; this only fills blanks):
  proper motion   Gaia DR3 gaia_source > SIMBAD adopted pm > an agent's published value
  radial velocity Gaia DR3 radial_velocity > SIMBAD adopted RV (velocity type, quality A-C, nonzero) > an agent's
Derived (orange, as data/four_plus_stars/kinematics.py and Sources & Provenance lines 3977-3985):
  total proper motion from the PMs; galactic l/b from RA/Dec; space velocity and motion toward l/b from all of
  RA/Dec, distance, PMs and RV (astropy, heliocentric, no LSR correction). No RV -> those three stay blank.
"""
import glob
import json
import math
import re
import sys
from pathlib import Path

from common import (AGENT_OUT, BATCHES, BATCH_SIZE, CAT, MERGED, TARGETS, H_RV, H_PMRA, H_PMDE, H_MU, H_V, H_L,
                    H_B, H_ML, H_MB, done, load, mark, num, save)

RUN_DATE = "2026-10-08"
RUWE_FLAG = 1.4
RV_ERR_FLAG = 5.0        # km/s: a Gaia RV this uncertain moves the arrow visibly; flagged WEAK, still used
RV_ERR_REJECT = 20.0     # km/s: an agent RV this uncertain does not fix the arrow's direction; left in notes, unwritten
RV_MAX = 600.0          # km/s: anything faster within 100 ly is a catalog error (EZ Aqr's 6824.7 in SIMBAD)


def velocity(ra, de, dist_ly, pmra, pmde, rv):
    """(l, b) always; plus (speed, motion l, motion b) when rv is given -- data/four_plus_stars/kinematics.py."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    if rv is None:
        c = SkyCoord(ra=ra * u.deg, dec=de * u.deg, frame="icrs").galactic
        return float(c.l.deg), float(c.b.deg), None, None, None
    c = SkyCoord(ra=ra * u.deg, dec=de * u.deg, distance=dist_ly / 3.261563777 * u.pc,
                 pm_ra_cosdec=pmra * u.mas / u.yr, pm_dec=pmde * u.mas / u.yr, radial_velocity=rv * u.km / u.s,
                 frame="icrs").galactic
    v = c.velocity.d_xyz.to(u.km / u.s).value              # (U, V, W): heliocentric, toward l=0, l=90, b=90
    speed = float(math.sqrt(sum(x * x for x in v)))
    return (float(c.l.deg), float(c.b.deg), speed, math.degrees(math.atan2(v[1], v[0])) % 360.0,
            math.degrees(math.asin(v[2] / speed)))


def catalogs():
    gaia = {}
    for f in sorted(CAT.glob("gaia_*.json")):
        for r in json.loads(f.read_text())["rows"]:
            gaia[str(r["source_id"])] = r
    simbad = {r["k"]: r for f in ("simbad_gaia.json", "simbad_nogaia.json")
              for r in (load(CAT / f) or {"rows": []})["rows"]}
    return gaia, simbad


def simbad_rv_ok(s):
    v = num(s.get("rvz_radvel"))
    return (v is not None and v != 0.0 and abs(v) < RV_MAX and s.get("rvz_type") == "v"
            and s.get("rvz_qual") in ("A", "B", "C") and not s.get("component_risk"))


# ---- agent output ---------------------------------------------------------------------------------------------

# Agent values the orchestrator will not write, by row key and field, with why. The agent's record stays in its file.
REJECT = {
    "Gaia DR3 3338886345887759232|3338886345887759232": {
        "rv": "K006: LP 477-19 A, one low-S/N LAMOST spectrum whose releases disagree in sign (-68 in DR7+, +69 in "
              "DR4/DR5, Xiang 2019, Zhang 2021): the arrow could point the wrong way."},
    "GJ 10526|64989250397297280": {
        "rv": "K006: Li 2025 per-spectrum values run -6.5 to +5.2 while Zhang 2025 measures the same spectra at "
              "+12 to +15: no value to prefer."},
    "GJ 11222|": {"rv": "K028: WISE 0825+2805's -18.7 is quoted by Kiman 2025 from 'Faherty et al. in prep': not yet published."},
    "GJ 11329|1016186483391641216": {"rv": "K021: Kiman 2019 +5.5 +/- 12.2 vs Schmidt 2010 -33.2 +/- 20 (SDSS, likely the same spectrum)."},
    "GJ 11221|679088656539598592": {"rv": "K023: Kiman 2019 88.7 +/- 11.4 vs Schmidt 2010 40.6 +/- 20."},
    "Gaia DR3 1311454726097258368|1311454726097258368": {"rv": "K024: 2MASSI J1645+3004, Schmidt 2010 -8.2 vs Kiman 2019 -44.0, probably the same SDSS spectrum."},
    "Gaia DR3 1290498996544435200|1290498996544435200": {"rv": "K022: Schmidt 2010 -2.1 vs Kiman 2019 -53.7 for the same SDSS spectrum."},
    "GJ 12087|1611997094153823104": {"rv": "K022: Schmidt 2010 -8.8 vs Kiman 2019 -69.2 for the same SDSS spectrum."},
    "Gaia DR3 5877057330286155648|5877057330286155648": {"rv": "K020: bet Cir B, Smith 2015 calls its RVs LSR-relative: frame unclear."},
    "Gaia DR3 3203300859784180352|3203300859784180352": {"rv": "K016: G 160-54B, DESI spectrum likely contaminated by the SB2 primary 3.2 arcsec away and 4.5 mag brighter."},
    "Gaia DR3 6840706910418152320|6840706910418152320": {"rv": "K001: mu Cap, GCS -48.5 +/- 4.3 from one measurement against older values near -21."},
    "Gaia DR3 2656072582607976064|2656072582607976064": {"rv": "K014: LP 641-4 B, DESI fit unphysical (logg 1.2, [Fe/H] -3.6) beside a primary 5.5 mag brighter at 2.5 arcsec; the value is about A's."},
    "Gaia DR3 3433594669734887424|3433594669734887424": {"rv": "K011: LAMOST recommended +30.8 but other measurements run -1.6 to +63."},
    "GJ 12171|6256677841624904320": {"rv": "K011: Galvez-Ortiz 2010 -22.1 +/- 1.3 vs Reiners & Basri 2009 -2.5 +/- 3: 20 km/s apart, no basis to choose."},
    "GJ 11772|3902307268243107456": {"rv": "K012: Li 2025 -18.2 +/- 6.4 and Zhang 2021 -45.2 from the same LAMOST spectrum."},
    "Gaia DR3 224373459529824128|224373459529824128": {"rv": "K009: Li 2025 gives -104.4 +/- 16, two other pipelines about -47 from the same spectrum."},
    "Gaia DR3 517324103519209344|517324103519209344": {"rv": "K009: BOSS -44.4 vs Gaia DR3 -8.2 for the companion 4.5 arcsec away: a bound pair cannot differ by 36 km/s."},
}

# Combined-light RVs of unresolved pairs, which the agents found and withheld under the BRIEF's component rule (5).
# Accepted by the user on 2026-10-09, as the Gaia bulk pass already accepts its combined-light RVs. Taken from each
# agent's notes, re-checked where an error was missing (Fouque 2018, Soubiran 2018, DESI DR1 queried 2026-10-09), and
# written to every member row whose light is in the spectrum: a pair closer than ~2.5 arcsec whose members are within
# 2.5 mag in Gaia G (Gaia DR3 cone search, 2026-10-09). Not taken, with why:
#   G 164-42 A/B, LP 780-32 A/B (GJ 10963 A / GJ 10962 B), GJ 3183: values for the same blend disagree by 20+ km/s.
#   Gaia DR3 3252692330853394304: Shkolnik 2012's 31.7 for AB vs the companion's own Gaia DR3 52.7 (21 km/s).
#   GJ 10828 A: which of two LAMOST fibres was on A is not stated, and both sit 7-11 km/s off B's Gaia RV.
#   GJ 2069 D (CV Cnc B): Fouque 2018's 7.48 has e_HRV 25.9 km/s, over RV_ERR_REJECT.
#   GJ 12207 A: Burgasser 2007's -70 +/- 18 is not corrected for Earth's motion (not heliocentric).
#   GJ 11349: RAVE DR6 20.4 +/- 12, SIMBAD grade E (the bulk pass refuses D/E).
#   GJ 11391 B: DESI light dominated by the primary 5.6 mag brighter (as K014's LP 641-4 B in REJECT).
#   GJ 257 A/B: PMSU 'Gl 257 A' -20.3 has no error, and which star of the 2.4" pair it is depends on the A/B naming.
_APOGEE = ("Abdurro'uf et al. 2022, ApJS 259, 35 (APOGEE DR17, VizieR III/286)", "https://doi.org/10.3847/1538-4365/ac4414")
_GALAH = ("Buder et al. 2025, PASA 42, e051 (GALAH DR4, VizieR J/other/PASA/42.51)", "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/other/PASA/42.51")
_GIZIS = ("Gizis, Reid & Hawley 2002, AJ 123, 3356 (VizieR J/AJ/123/3356)", "https://doi.org/10.1086/340465")
_BURG15 = ("Burgasser et al. 2015, ApJS 220, 18 (VizieR J/ApJS/220/18)", "https://doi.org/10.1088/0067-0049/220/1/18")
_NLTT33370 = ("NLTT 33370 AB (LP 497-33), an equal-mass M7+M7 pair 0.1-0.2 arcsec apart: CNS5 3258/3259 list its two "
              "components as GJ 11905 A and GJ 11906 B. A systemic value, the same for both rows.")


def _b(agent, value, err, cite, where, pair, pm=None):
    return {"agent": agent, "value": value, "err": err, "citation": cite[0], "url": cite[1], "where": where,
            "pair": pair, "pm": pm}


BLENDED = {
    "Gaia DR3 3662657851291101824|3662657851291101824": _b(
        "K001", -6.08, 0.31, ("Tokovinin & Smekhov 2002, A&A 382, 118", "https://doi.org/10.1051/0004-6361:20011586"),
        "VizieR J/A+A/382/118, CORAVEL RV of HD 118036 AB combined",
        "HD 118036 A (Gaia DR3 3662657851291871104, G 7.53) is 1.7 arcsec away; this B is G 8.37"),
    "GJ 695 C|4594497838483177984": _b(
        "K001", -13.82, 0.3, ("Fouque et al. 2018, MNRAS 475, 1960", "https://doi.org/10.1093/mnras/stx3246"),
        "VizieR J/MNRAS/475/1960 tablea6, 'Gl 695BC', HRV/e_HRV (1 spectrum)",
        "GJ 695 B (Gaia DR3 4594497834189213184, G 9.18) is 0.6 arcsec away; this C is G 9.59"),
    "GJ 185 B|2974726136265625088": _b(
        "K001", -13.272, 0.032, ("Soubiran et al. 2018, A&A 616, A7", "https://doi.org/10.1051/0004-6361/201832795"),
        "VizieR J/A+A/616/A7 rvstdcat, HIP023452, RV/e_RV (2 epochs over 68 d)",
        "GJ 185 A (Gaia DR3 2974726131970829952, G 7.79) is 0.9 arcsec away; this B is G 9.64"),
    "GJ 9163 A|3185759697950315008": _b(
        "K001", -4.2, 1.0, ("Sperauskas et al. 2016, A&A 596, A116", "https://doi.org/10.1051/0004-6361/201629249"),
        "VizieR J/A+A/596/A116 table4, MCC 452 (from Upgren & Harlow 1996)",
        "GJ 9163 A and B (G 10.17, 10.25) are 1.7 arcsec apart in Gaia DR3"),
    "GJ 9163 B|3185759697949251456": _b(
        "K001", -4.2, 1.0, ("Sperauskas et al. 2016, A&A 596, A116", "https://doi.org/10.1051/0004-6361/201629249"),
        "VizieR J/A+A/596/A116 table4, MCC 452 (from Upgren & Harlow 1996)",
        "GJ 9163 A and B (G 10.17, 10.25) are 1.7 arcsec apart in Gaia DR3"),
    "GJ 3332 C|2962658549471532672": _b(
        "K002", 21.2, 0.9, _GIZIS, "VizieR J/AJ/123/3356 table2, 'Step 545C' (RHG95 875), 5 epochs",
        "BD-21 1074 B (Gaia DR3 2962658549474035712, G 10.33) is 0.96 arcsec away; this C is G 11.05. Also "
        "Zuniga-Fernandez et al. 2021 21.89 +/- 0.57 for 'BD-21 1074B'"),
    "GJ 10936 A|3327170877700242944": _b(
        "K002", 42.244, 0.045, _APOGEE, "APOGEE DR17 allStar 2M06274397+0923541, HRV (3 visits), on this Gaia id",
        "Ross 603 A and B (G 11.12, 12.25) are 1.17 arcsec apart, inside the 2 arcsec APOGEE fibre"),
    "GJ 10935 B|3327170877694724096": _b(
        "K002", 42.244, 0.045, _APOGEE, "APOGEE DR17 allStar 2M06274397+0923541, HRV (3 visits), on A's Gaia id",
        "Ross 603 A and B (G 11.12, 12.25) are 1.17 arcsec apart, inside the 2 arcsec APOGEE fibre"),
    "GJ 473 A|3902874650602495232": _b(
        "K002", 1.0, 4.0, ("Newton et al. 2014, AJ 147, 20", "https://doi.org/10.1088/0004-6256/147/1/20"),
        "VizieR J/AJ/147/20, LSPM J1233+0901 (unresolved)",
        "Wolf 424 A and B (both G 11.24) are 1.15 arcsec apart. Terrien 2015's 36.9 +/- 13.3 is the low-quality "
        "outlier; ARICNS -2.0 agrees with this"),
    "GJ 473 B|3902874650601954816": _b(
        "K002", 1.0, 4.0, ("Newton et al. 2014, AJ 147, 20", "https://doi.org/10.1088/0004-6256/147/1/20"),
        "VizieR J/AJ/147/20, LSPM J1233+0901 (unresolved)",
        "Wolf 424 A and B (both G 11.24) are 1.15 arcsec apart. Terrien 2015's 36.9 +/- 13.3 is the low-quality "
        "outlier; ARICNS -2.0 agrees with this"),
    "GJ 11408|5431884378073753984": _b(
        "K002", 59.19, 0.29, _GALAH, "GALAH DR4 RVcomp1 (flag_sp 24) on this Gaia id",
        "a companion (Gaia DR3 5431884382368809728, G 11.93) is 0.50 arcsec away, inside the 2 arcsec fibre"),
    "GJ 12429 A|4561968271578549632": _b(
        "K002", 7.515, 0.092, _APOGEE, "APOGEE DR17 allStar, HRV (1 visit), on A's Gaia id",
        "GJ 12429 A and GJ 12430 B (G 11.50, 12.54) are 0.65 arcsec apart. Also Malo et al. 2014 8.6 +/- 0.3"),
    "GJ 12430 B|4561968267282882688": _b(
        "K002", 7.515, 0.092, _APOGEE, "APOGEE DR17 allStar, HRV (1 visit), on A's Gaia id",
        "GJ 12429 A and GJ 12430 B (G 11.50, 12.54) are 0.65 arcsec apart. Also Malo et al. 2014 8.6 +/- 0.3"),
    "GJ 11692|3895876671408042496": _b(
        "K002", 29.41, 0.09, _APOGEE, "APOGEE DR17 allStar, HRV (1 visit), on this Gaia id",
        "a companion (Gaia DR3 3895876671408042368, G 12.18) is 0.32 arcsec away. Also GALAH DR4 29.24 +/- 0.51"),
    "GJ 10825 B|2966696643363780736": _b(
        "K002", 43.25, 14.2, ("Gaia Collaboration 2018, A&A 616, A1 (Gaia DR2, VizieR I/345)",
                              "https://doi.org/10.1051/0004-6361/201833051"),
        "Gaia DR2 gaia_source radial_velocity on this source id (Gaia DR3 has none)",
        "its companion (Gaia DR3 2966696643367820032, G 11.90, Gaia DR3 RV 46.69) is 0.81 arcsec away; this B is G 11.93"),
    "GJ 11|530438704553073280": _b(
        "K002", 12.373, 0.072, _APOGEE, "APOGEE DR17 allStar, HRV (12 visits), on A's Gaia id",
        "GJ 11 B (Gaia DR3 530438704558852352, G 12.05, equal brightness) is 1.1 arcsec away"),
    "GJ 12781|4087368200624899840": _b(
        "K002", -52.48, 0.16, _GALAH, "GALAH DR4 RVcomp1 (flag_sp 24) on this Gaia id",
        "a companion (Gaia DR3 4087368200640566656, G 12.61) is 0.48 arcsec away"),
    "GJ 4368 B|2759428634126128384": _b(
        "K002", -7.4, 1.0, _GIZIS, "VizieR J/AJ/123/3356 table2, 'LHS 4022' = G 29-73, 7 epochs",
        "G 29-73 A (Gaia DR3 2759428629829608064, G 10.60, Gaia DR3 RV -7.33) is 1.17 arcsec away; this B is G 12.38"),
    "Gaia DR3 2535718905961089280|2535718905961089280": _b(
        "K003", 34.10, 4.54, ("Terrien et al. 2015, ApJS 220, 16", "https://doi.org/10.1088/0067-0049/220/1/16"),
        "VizieR J/ApJS/220/16, 2MASS 01012466-0105586 (IRTF/SpeX)",
        "a companion about as bright (Gaia DR3 2535718901668737536, G 12.75) is 0.43 arcsec away"),
    "Gaia DR3 9178383766474496|9178383766474496": _b(
        "K005", -3.4, None, ("Reid, Hawley & Gizis 1995 / Hawley et al. 1996, PMSU (VizieR III/198)",
                             "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=III/198"),
        "VizieR III/198, 'LP 532-81' (unresolved; PMSU quotes no per-star error, about +/-10 km/s overall)",
        "LP 532-81 (Gaia DR3 9178383766474624, G 13.73) is 2.15 arcsec away; this component C is G 13.90"),
    "Gaia DR3 3674243817629910016|3674243817629910016": _b(
        "K008", -35.90, 3.51, ("Li et al. 2025, ApJS 281, 58 (LAMOST M stars, VizieR J/ApJS/281/58)",
                               "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/ApJS/281/58"),
        "VizieR J/ApJS/281/58, RV on this Gaia id (LAMOST LRS, 3.3 arcsec fibre)",
        "LP 559-44's other member (Gaia DR3 3674243817630610304, G 15.11, Gaia DR3 RV -28.95 +/- 10.65) is 1.13 "
        "arcsec away. Other analyses of the blend: -23.7 to -35.9"),
    "GJ 12702|2266317803873109504": _b(
        "K010", -21.463, 0.099, ("DESI Collaboration 2025, DESI DR1 Milky Way Survey (RVSpecFit)",
                                 "https://datalab.noirlab.edu/"),
        "NOIRLab Astro Data Lab desi_dr1.mws, vrad/vrad_err on this Gaia id (queried 2026-10-09)",
        "LP 44-334 B (Gaia DR3 2266317803875363968, G 15.73) is 0.83 arcsec away, inside the 1.5 arcsec DESI fibre"),
    "GJ 13099 A|6783123184369906944": _b(
        "K011", -19.77, 2.15, ("Galvez-Ortiz et al. 2010, MNRAS 409, 552 (arXiv:1007.3128)",
                               "https://arxiv.org/abs/1007.3128"),
        "Table of FEROS radial velocities, 'SIPS2128-3254' (the system)",
        "a companion (Gaia DR3 6783123184369906816, G 16.47) is 2.3 arcsec away; this A is G 15.80"),
    "GJ 12445|4364185165038935040": _b(
        "K015", 2.9, 2.2, _BURG15, "VizieR J/ApJS/220/18, 2MASS J1707-0558AB (MagE)",
        "the M9+L3 pair is 1.2 arcsec apart (B: Gaia DR3 4364185160742355200, G 19.09); this A is G 16.94"),
    "GJ 10808|287767756635519488": _b(
        "K020", 18.64, 0.23, ("Blake, Charbonneau & White 2010, ApJ 723, 684 (VizieR J/ApJ/723/684)", "https://doi.org/10.1088/0004-637X/723/1/684"),
        "VizieR J/ApJ/723/684, 2M0543+64 (2 epochs, unresolved)",
        "2MASS J05431887+6422528 A (Gaia DR3 287767760932246144, G 19.04) is 0.65 arcsec away; this B is G 19.35. "
        "Gagne et al. 2023 assign the value to A, whose row already carries it"),
    "GJ 13003 B|6450595924275742848": _b(
        "K021", 5.4, 2.2, _BURG15, "VizieR J/ApJS/220/18, 'J2045-6332' (MagE)",
        "SIPS J2045-6332 (Gaia DR3 6450595924277607040, G 17.62) is 0.8 arcsec away; this B is G 19.65"),
    "GJ 11905 A|": _b(
        "K030", -10.4, 1.0, ("Schlieder et al. 2014, arXiv:1401.0947 (NLTT 33370 AB)", "https://arxiv.org/abs/1401.0947"),
        "Section on radial velocities: system velocity from the resolved primary and secondary lines", _NLTT33370,
        pm={"pmra": -247.99, "pmdec": -183.58, "err": "0.10, 0.22",
            "citation": "Forbrich et al. 2016, arXiv:1605.07177 (NLTT 33370 AB, VLBA + Keck)", "url": "https://arxiv.org/abs/1605.07177",
            "where": "abstract: barycentric proper motion from the joint VLBA + Keck astrometric orbit"}),
    "GJ 11906 B|": _b(
        "K030", -10.4, 1.0, ("Schlieder et al. 2014, arXiv:1401.0947 (NLTT 33370 AB)", "https://arxiv.org/abs/1401.0947"),
        "Section on radial velocities: system velocity from the resolved primary and secondary lines", _NLTT33370,
        pm={"pmra": -247.99, "pmdec": -183.58, "err": "0.10, 0.22",
            "citation": "Forbrich et al. 2016, arXiv:1605.07177 (NLTT 33370 AB, VLBA + Keck)", "url": "https://arxiv.org/abs/1605.07177",
            "where": "abstract: barycentric proper motion from the joint VLBA + Keck astrometric orbit"}),
}

# RV sources with a known systematic, found by the research batches; their values are written as published and
# flagged WEAK (decided by the user, 2026-10-09). Matched against each value's citation and locator.
RV_SYSTEMATICS = (
    (re.compile(r"DESI", re.I), "DESI DR1 MWS reads 3-6 km/s high against high-resolution RVs for late-M dwarfs "
                                "(K017: GJ 10174, GJ 11775); its formal error understates this"),
    (re.compile(r"Hsu.{0,40}2026|2026.{0,40}JWST NIRSpec", re.I),
     "Hsu et al. 2026 JWST NIRSpec G395H RVs read 5-7 km/s low against high-resolution benchmarks (K028, K029)"),
)
FIDELITY_FLAG = 0.5      # Rybizki et al. 2022: below this a Gaia astrometric solution is probably spurious
FIDELITY_DATE = "2026-10-09"
NOT_OWN = "NOT THIS COMPONENT'S OWN (accepted 2026-10-09, as the Gaia pass accepts combined-light RVs)"


def systematic(rec):
    """The known-systematic warning for an RV record, or None."""
    text = f"{cite(rec)} {rec.get('where', '')}"
    return next((why for rx, why in RV_SYSTEMATICS if rx.search(text)), None)


def agent_values():
    """{row key: {'rv': rec, 'pm': rec, 'agent': id}} from every agent_output file that validates, plus BLENDED."""
    from common import progress
    finished = {b for b, s in progress().get("batches", {}).items() if s.get("state") in ("done", "partial")}
    out = {}
    for f in sorted(glob.glob(str(AGENT_OUT / "K*.json"))):
        if Path(f).stem not in finished:      # a running agent's file is still changing: wait for its finish
            continue
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        if check_file(d, Path(f).stem):
            continue
        for o in d["objects"]:
            for what in ("rv", "pm"):
                rec = o.get(what)
                if what == "rv" and rec and (num(rec.get("err")) or 0) > RV_ERR_REJECT:
                    continue
                if rec and what not in REJECT.get(o["key"], {}):
                    out.setdefault(o["key"], {"agent": d["agent_id"]})[what] = dict(rec, sources=o.get("sources", {}))
    for k, b in BLENDED.items():
        if b["agent"] not in finished:
            continue
        a = out.setdefault(k, {"agent": b["agent"]})
        if not a.get("rv") and "rv" not in REJECT.get(k, {}):
            a["rv"] = {"value": b["value"], "err": b["err"], "src": "BLEND", "where": b["where"], "wikipedia": False,
                       "blended": b["pair"], "sources": {"BLEND": {"citation": b["citation"], "url": b["url"]}}}
        if b["pm"] and not a.get("pm") and "pm" not in REJECT.get(k, {}):
            p = b["pm"]
            a["pm"] = {"pmra": p["pmra"], "pmdec": p["pmdec"], "err": p["err"], "src": "BLENDPM", "where": p["where"],
                       "wikipedia": False, "blended": b["pair"],
                       "sources": {"BLENDPM": {"citation": p["citation"], "url": p["url"]}}}
    return out


def check_file(d, stem):
    """Problems with one agent file, as a list of strings; [] means it is usable."""
    errs = []
    if d.get("agent_id") != stem:
        errs.append(f"agent_id {d.get('agent_id')!r} is not the file name {stem!r}")
    batch = (load(BATCHES) or {}).get("batches", {}).get(stem)
    keys = set(batch or [])
    for o in d.get("objects", []):
        k = o.get("key")
        if k not in keys:
            errs.append(f"{k!r} is not in batch {stem}")
            continue
        src = o.get("sources") or {}
        for what, fields in (("rv", ("value",)), ("pm", ("pmra", "pmdec"))):
            rec = o.get(what)
            if not rec:
                continue
            for fld in fields:
                if num(rec.get(fld)) is None:
                    errs.append(f"{k}: {what}.{fld} is not a number")
            if rec.get("src") not in src:
                errs.append(f"{k}: {what}.src {rec.get('src')!r} has no entry in sources")
            if not rec.get("where"):
                errs.append(f"{k}: {what} has no 'where' locator")
            if what == "rv" and num(rec.get("value")) is not None and abs(num(rec["value"])) >= RV_MAX:
                errs.append(f"{k}: rv {rec['value']} km/s is not credible")
            if rec.get("wikipedia") and not (rec.get("wikipedia_url") and rec.get("cited_source")
                                             and rec.get("cited_url")):
                errs.append(f"{k}: {what} is from Wikipedia but lacks wikipedia_url / cited_source / cited_url")
    return errs


def cite(rec):
    s = rec["sources"].get(rec["src"], {})
    return f"{s.get('citation', rec['src'])}" + (f" <{s['url']}>" if s.get("url") else "")


# ---- the plan -------------------------------------------------------------------------------------------------

def plan_row(t, g, s, a, fid=None):
    """What to write on one row: {header: {value, mark, note}}, plus the Kinematics source text and flags."""
    have = t["have"]
    cells, flags = {}, []
    pm = pm_src = rv = rv_src = None
    pm_wiki = rv_wiki = None
    # proper motion
    if have[H_PMRA] is not None and have[H_PMDE] is not None:
        pm, pm_src = (num(have[H_PMRA]), num(have[H_PMDE])), "the row's own"
    elif g and g["pmra"] is not None:
        pm, pm_src = (g["pmra"], g["pmdec"]), "Gaia DR3"
        note = (f"SOURCE: Gaia DR3 gaia_source {g['source_id']}: pmra {g['pmra']:.3f} ± {g['pmra_error']:.3f}, "
                f"pmdec {g['pmdec']:.3f} ± {g['pmdec_error']:.3f} mas/yr (epoch J2016.0). Queried {RUN_DATE}.")
        cells[H_PMRA] = {"value": round(g["pmra"], 3), "mark": "grey", "note": note}
        cells[H_PMDE] = {"value": round(g["pmdec"], 3), "mark": "grey", "note": note}
    elif s and num(s.get("s_pmra")) is not None and num(s.get("s_pmdec")) is not None and not s.get("component_risk"):
        pm, pm_src = (num(s["s_pmra"]), num(s["s_pmdec"])), "SIMBAD"
        note = (f"SOURCE: SIMBAD {s['main_id']} (matched by {s.get('how', 'Gaia DR3 identifier')}): adopted proper "
                f"motion {s['s_pmra']}, {s['s_pmdec']} mas/yr, quality {s.get('pm_qual')}, ref {s.get('pm_bibcode')}. "
                f"Gaia DR3 has none for this row. Queried {RUN_DATE}.")
        cells[H_PMRA] = {"value": round(pm[0], 3), "mark": "grey", "note": note}
        cells[H_PMDE] = {"value": round(pm[1], 3), "mark": "grey", "note": note}
    elif a and a.get("pm"):
        r = a["pm"]
        pm, pm_src, pm_wiki = (num(r["pmra"]), num(r["pmdec"])), f"literature ({a['agent']})", r.get("wikipedia")
        note = (f"SOURCE: {cite(r)}, {r['where']}: pmra {r['pmra']}, pmdec {r['pmdec']} mas/yr"
                f"{' ± ' + str(r['err']) if r.get('err') else ''}. Found by research batch {a['agent']}, {RUN_DATE}.")
        if pm_wiki:
            note = (f"WIKIPEDIA: {r['wikipedia_url']} gives this, citing {r['cited_source']} <{r['cited_url']}>. "
                    + note)
        if r.get("blended"):
            note += f" {NOT_OWN}: {r['blended']}"
            flags.append("PM is the pair's barycentric value")
        mk = "pink" if pm_wiki else "grey"
        cells[H_PMRA] = {"value": round(pm[0], 3), "mark": mk, "note": note, "wiki": r if pm_wiki else None}
        cells[H_PMDE] = {"value": round(pm[1], 3), "mark": mk, "note": note, "wiki": r if pm_wiki else None}
    # radial velocity
    if have[H_RV] is not None:
        rv, rv_src = num(have[H_RV]), "the row's own"
    elif g and g["radial_velocity"] is not None:
        rv, rv_src = g["radial_velocity"], "Gaia DR3"
        cells[H_RV] = {"value": round(rv, 3), "mark": "grey", "note": (
            f"SOURCE: Gaia DR3 gaia_source {g['source_id']}: radial_velocity {rv:.3f} ± "
            f"{g['radial_velocity_error']:.3f} km/s ({g['rv_nb_transits']} transits, G_RVS "
            f"{g['grvs_mag'] if g['grvs_mag'] is None else round(g['grvs_mag'], 2)}). A combined-light mean over 34 "
            f"months: for an unresolved binary it is not the systemic velocity. Queried {RUN_DATE}.")}
        if g["radial_velocity_error"] is not None and g["radial_velocity_error"] > RV_ERR_FLAG:
            flags.append(f"Gaia RV error {g['radial_velocity_error']:.1f} km/s")
            cells[H_RV]["note"] += f" WEAK: error over {RV_ERR_FLAG:.0f} km/s."
    elif s and simbad_rv_ok(s):
        rv, rv_src = num(s["rvz_radvel"]), "SIMBAD"
        weak = " WEAK: SIMBAD grades it C." if s["rvz_qual"] == "C" else ""
        cells[H_RV] = {"value": round(rv, 3), "mark": "grey", "note": (
            f"SOURCE: SIMBAD {s['main_id']} (matched by {s.get('how', 'Gaia DR3 identifier')}): adopted RV "
            f"{s['rvz_radvel']} ± {s.get('rvz_err')} km/s, quality {s['rvz_qual']}, ref {s.get('rvz_bibcode')}. "
            f"Gaia DR3 has no RV for this star. Queried {RUN_DATE}.{weak}")}
        if weak:
            flags.append("RV quality C (SIMBAD)")
    elif a and a.get("rv"):
        r = a["rv"]
        rv, rv_src, rv_wiki = num(r["value"]), f"literature ({a['agent']})", r.get("wikipedia")
        note = (f"SOURCE: {cite(r)}, {r['where']}: {r['value']}"
                f"{' ± ' + str(r['err']) if r.get('err') not in (None, '') else ''} km/s. Found by research batch "
                f"{a['agent']}, {RUN_DATE}.")
        if rv_wiki:
            note = (f"WIKIPEDIA: {r['wikipedia_url']} gives this, citing {r['cited_source']} <{r['cited_url']}>. "
                    + note)
        cells[H_RV] = {"value": round(rv, 3), "mark": "pink" if rv_wiki else "grey", "note": note,
                       "wiki": r if rv_wiki else None}
        e = num(r.get("err"))
        if e is None or e > RV_ERR_FLAG:
            flags.append("RV error " + ("not published" if e is None else f"{e:g} km/s"))
            cells[H_RV]["note"] += (" WEAK: no published error." if e is None
                                    else f" WEAK: error over {RV_ERR_FLAG:.0f} km/s.")
        why = systematic(r)
        if why:
            flags.append(f"RV systematic: {why}")
            cells[H_RV]["note"] += f" WEAK: {why}."
        if r.get("blended"):
            flags.append("RV is a pair's combined light or systemic value")
            cells[H_RV]["note"] += f" {NOT_OWN}: {r['blended']}"
    if g and g.get("ruwe") and g["ruwe"] > RUWE_FLAG:
        flags.append(f"RUWE {g['ruwe']:.2f} -- astrometry may be perturbed by a companion")
    dist_note = None
    if fid and fid["fidelity_v2"] < FIDELITY_FLAG:
        flags.append(f"fidelity_v2 {fid['fidelity_v2']:.2f} -- Gaia astrometry probably spurious; may lie beyond 100 ly")
        dist_note = (f"DOUBTFUL MEMBERSHIP: Gaia DR3 astrometric fidelity_v2 = {fid['fidelity_v2']:.3f} (Rybizki et al. "
                     f"2022, MNRAS 510, 2597; GAVO gedr3spur.main, queried {FIDELITY_DATE}). Below {FIDELITY_FLAG} a "
                     "solution is probably spurious, and this distance is 1/parallax from it, so the object may lie "
                     "well beyond 100 ly. Kept on the tab and flagged, not removed (decided 2026-10-09).")

    # derived
    ra, de, d = t["ra"], t["dec"], t["dist_ly"]
    method = ("INFERRED: astropy SkyCoord(RA, Dec, distance, pmRA, pmDec, RV) -> galactic (U, V, W), heliocentric, "
              "no LSR correction (Sources & Provenance lines 3977-3985), at this row's Distance (ly) and RA/Dec; "
              f"PM from {pm_src}, RV from {rv_src}.")
    weak = (" WEAK: " + "; ".join(flags) + ".") if flags else ""
    wiki_in = " One input is from Wikipedia (pink)." if (pm_wiki or rv_wiki) else ""
    if pm is not None:
        cells[H_MU] = {"value": round(math.hypot(*pm) / 1000.0, 4), "mark": "orange",
                       "note": f"INFERRED: sqrt(pmRA^2 + pmDec^2) / 1000, PM from {pm_src}.{wiki_in}"}
    if ra is not None and de is not None:
        l, b, speed, ml, mb = velocity(ra, de, d, *(pm or (0, 0)), rv if (pm is not None and d) else None)
        gal = "INFERRED: RA/Dec through the IAU ICRS-to-Galactic rotation (astropy). Exact transform; no model."
        cells[H_L] = {"value": round(l, 3), "mark": "orange", "note": gal}
        cells[H_B] = {"value": round(b, 3), "mark": "orange", "note": gal}
        if speed is not None:
            cells[H_V] = {"value": round(speed, 3), "mark": "orange", "note": f"{method} |(U, V, W)|.{weak}{wiki_in}"}
            cells[H_ML] = {"value": round(ml, 2), "mark": "orange", "note": f"{method} l = atan2(V, U).{weak}{wiki_in}"}
            cells[H_MB] = {"value": round(mb, 2), "mark": "orange", "note": f"{method} b = asin(W / |v|).{weak}{wiki_in}"}
    # only blanks are ever written
    cells = {h: c for h, c in cells.items() if h in t["blank"]}
    ks = f"RV: {rv_src or 'none found'}; PM: {pm_src or 'none found'}" + "".join(f" | {f}" for f in flags)
    return {"cells": cells, "kin_source": ks, "has_rv": rv is not None, "has_pm": pm is not None,
            "g_mag": g["phot_g_mean_mag"] if g else None, "dist_note": dist_note}


def build():
    targets = [t for t in load(TARGETS)["rows"] if t["blank"]]
    gaia, simbad = catalogs()
    fidelity = (load(CAT / "fidelity.json") or {"rows": {}})["rows"]
    agents = agent_values()
    plan = {}
    for t in targets:
        g = gaia.get(t["gaia"]) if t["gaia"] else None
        plan[t["key"]] = dict(plan_row(t, g, simbad.get(t["key"]), agents.get(t["key"]), fidelity.get(t["gaia"])),
                              name=t["name"],
                              plotted=t["plotted"], dist_ly=t["dist_ly"], kin_source_now=t["kin_source"])
    save(MERGED, {"built": RUN_DATE, "rows": plan})
    n = len(plan)
    count = {h: sum(1 for p in plan.values() if h in p["cells"]) for h in (H_RV, H_PMRA, H_PMDE, H_MU, H_V, H_L, H_B,
                                                                           H_ML, H_MB)}
    print(f"{n} rows with blanks; cells planned: " + ", ".join(f"{h.split(' (')[0]} {c}" for h, c in count.items()))
    print(f"  without RV after all sources: {sum(1 for p in plan.values() if not p['has_rv'])}; "
          f"without PM: {sum(1 for p in plan.values() if not p['has_pm'])}; agent rows used: {len(agents)}")
    return plan


def make_batches(plan):
    if load(BATCHES):
        raise SystemExit("batches.json exists; batches are fixed once agents have been given them.")
    if not done("P3_write"):
        raise SystemExit("Batch the residual only after the bulk write (P3), so agents never research what Gaia "
                         "and SIMBAD already answer.")
    resid = [(k, p) for k, p in plan.items() if not (p["has_rv"] and p["has_pm"])]
    resid.sort(key=lambda kp: (kp[1]["g_mag"] if kp[1]["g_mag"] is not None else 99.0, kp[1]["dist_ly"] or 999))
    keys = [k for k, _ in resid]
    batches = {f"K{i // BATCH_SIZE + 1:03d}": keys[i:i + BATCH_SIZE] for i in range(0, len(keys), BATCH_SIZE)}
    # one input file per batch: everything an agent needs to find each object, and what it is missing
    targets = {t["key"]: t for t in load(TARGETS)["rows"]}
    gaia, simbad = catalogs()
    (HERE_DIR := MERGED.parent / "batches").mkdir(exist_ok=True)
    for b, ks in batches.items():
        objs = []
        for k in ks:
            t, p, s = targets[k], plan[k], simbad.get(k) or {}
            g = gaia.get(t["gaia"]) if t["gaia"] else None
            objs.append({
                "key": k, "name": t["name"], "gaia_dr3": t["gaia"], "ra_deg_j2016": t["ra"], "dec_deg_j2016": t["dec"],
                "distance_ly": t["dist_ly"], "G_mag": g["phot_g_mean_mag"] if g else None,
                "pmra_known": None if not p["has_pm"] else (g["pmra"] if g else num(s.get("s_pmra"))),
                "pmdec_known": None if not p["has_pm"] else (g["pmdec"] if g else num(s.get("s_pmdec"))),
                "simbad_main_id": s.get("main_id"), "simbad_otype": s.get("otype"), "simbad_sp_type": s.get("sp_type"),
                "simbad_rv_rejected": (None if num(s.get("rvz_radvel")) is None or simbad_rv_ok(s) else
                                       f"{s.get('rvz_radvel')} km/s, quality {s.get('rvz_qual')}, type "
                                       f"{s.get('rvz_type')}, ref {s.get('rvz_bibcode')}"),
                "need": [x for x, ok in (("rv", p["has_rv"]), ("pm", p["has_pm"])) if not ok],
            })
        save(HERE_DIR / f"{b}.json", {"batch": b, "objects": objs})
    save(BATCHES, {"made": RUN_DATE, "size": BATCH_SIZE, "rows": len(keys), "batches": batches})
    mark("P4_batches", "done", residual=len(keys), batches=len(batches))
    print(f"{len(keys)} residual rows -> {len(batches)} batches of {BATCH_SIZE}")


def main():
    args = sys.argv[1:]
    if args == ["--check"]:
        bad = 0
        for f in sorted(glob.glob(str(AGENT_OUT / "K*.json"))):
            try:
                errs = check_file(json.loads(Path(f).read_text(encoding="utf-8")), Path(f).stem)
            except json.JSONDecodeError as e:
                errs = [f"not valid JSON: {e}"]
            bad += bool(errs)
            print(f"{Path(f).stem}: {'ok' if not errs else ''}" + "".join(f"\n  - {e}" for e in errs[:20]))
        sys.exit(1 if bad else 0)
    plan = build()
    if args == ["--batch"]:
        make_batches(plan)


if __name__ == "__main__":
    main()
