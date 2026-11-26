# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The two Gaia-numbered star pairs with no Multi-stars rows get them, and four Gaia-numbered rows a readable name.

    python add_pairs.py          plan: print every write; touches nothing
    python add_pairs.py write    nicknames, the four rows, notes, boxes, provenance, rename

Gaia-ASOI-054 and Gaia-ASOI-037 were Gaia DR3 astrometric "planets" that are their host's own stellar orbit
(Rejected candidates). Their Systems rows already count two stars, but the pairs were kept off Multi-stars on
6 Oct 2026 for having no live candidate. Since 26 Nov 2026 a system of stars with no planet opens as a page of its
own (Catalog.star_systems()), so the stars go on file, as GJ 773 B's did on 26 Sep 2026:

  GJ 4113 (Ross 1063, Gaia DR3 2052469973468984192): a twin double-lined binary.
    Marcussen & Albrecht 2023, AJ 165, 266 (arXiv:2305.08623), Sect. 4.5 and Table 1: SB2 from two FIES spectra,
      flux ratio F2/F1 ~ 0.85; no K1/K2, no mass ratio, no orbit of their own; M1 = M2 = 0.47 M-sun is assumed
      (Gaia DR3 binary_masses M1).
    Stefansson et al. 2025, AJ 169, 107 (arXiv:2410.05654), Table 4, G-ASOI-54: SB2; M* 0.42 +/- 0.02 M-sun as a
      single star.
    Gaia DR3 nss_two_body_orbit (Orbital): P 209.3157 +/- 0.7392 d, e 0.4698 +/- 0.0444, parallax 57.5696 mas.
    No component value is published, so each star's mass is INFERRED the way GJ 773 B's was: the blend's 2MASS Ks
    split equally, through the Mann et al. 2019 M_Ks relation (ApJ 871, 63; n = 5, no [Fe/H] term).

  APM 89 AB (APMPM J0710-5704, WDS 07096-5704, Gaia DR3 5486916932205092352): resolved by SOAR speckle.
    Vrijmoet et al. 2026, AJ 171, 186 (arXiv:2601.18905), Table 4: P 0.69778 +/- 0.00274 yr, a 0.0342 +/- 0.0011
      arcsec, e 0.1373 +/- 0.0275, i 36.72 deg, node 310.25 deg, omega 125.72 deg, T0 2021.3645, Mtot 0.409 +/-
      0.040 M-sun (Gaia parallax). First resolved in Vrijmoet et al. 2022, AJ 163, 178 (arXiv:2202.04688):
      Delta I = 0.1 mag.
    Gaia DR3 nss_two_body_orbit: parallax 58.5739 mas (P 253.479 d, e 0.1339: the orbit Gaia-ASOI-037 was read from).

Every number above was read from the paper's arXiv source, IRSA (2MASS) or the ARI mirror of the Gaia archive on
26 Nov 2026; none from memory or Wikipedia. The rows are written by data/star_counts/apply_specs.py, from the spec
this script builds (pairs_spec.json beside it).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = HERE / "pairs_spec.json"
LOG = HERE / "add_pairs_log.json"
WRITE = "write" in sys.argv[1:]
DATE = "26 Nov 2026"

GJ4113, APM, GJ773B, WD = ("Gaia DR3 2052469973468984192", "Gaia DR3 5486916932205092352",
                           "Gaia DR3 4188996885011268608", "Gaia DR3 4698424845771339520")
NICKNAMES = {GJ773B: "GJ 773 B", GJ4113: "GJ 4113", APM: "APM 89", WD: "WD 0141-675"}

MA23 = "Marcussen & Albrecht 2023, AJ 165, 266 (arXiv:2305.08623)"
ST25 = "Stefansson et al. 2025, AJ 169, 107 (arXiv:2410.05654)"
VR26 = "Vrijmoet et al. 2026, AJ 171, 186 (arXiv:2601.18905)"
VR22 = "Vrijmoet et al. 2022, AJ 163, 178 (arXiv:2202.04688)"
MANN = "Mann et al. 2019, ApJ 871, 63 (arXiv:1811.06938)"

# Mann et al. 2019, Table 6, the preferred n = 5 fit with no [Fe/H] term: log10(M/M-sun) = sum a_i (M_Ks - 7.5)^i.
MANN_A = (-0.642, -0.208, -8.43e-4, 7.87e-3, 1.42e-4, -2.13e-4)


def mann_mass(m_ks):
    assert 4.0 < m_ks < 11.0, m_ks
    return 10 ** sum(a * (m_ks - 7.5) ** i for i, a in enumerate(MANN_A))


# The relation as coded reproduces the sheet's GJ 773 B cells (0.174 as one star, 0.126 split).
assert round(mann_mass(8.066), 3) == 0.174 and round(mann_mass(8.818), 3) == 0.126

# ---- GJ 4113
G_KS, G_PLX, G_P_D, G_E = 7.339, 57.5696, 209.3157, 0.4698       # 2MASS J19333940+3931372; Gaia DR3 NSS
G_MKS = G_KS - 5 * math.log10(100.0 / G_PLX)
G_BLEND = mann_mass(G_MKS)
G_M = round(mann_mass(G_MKS + 2.5 * math.log10(2)), 3)
G_M85 = (mann_mass(G_MKS + 2.5 * math.log10(1.85)), mann_mass(G_MKS + 2.5 * math.log10(1.85 / 0.85)))
G_A = round(((G_P_D / 365.25) ** 2 * 2 * G_M) ** (1 / 3), 3)
G_A85 = ((G_P_D / 365.25) ** 2 * sum(G_M85)) ** (1 / 3)
# ---- APM 89
A_MTOT, A_P_YR, A_ARCSEC, A_E, A_PLX = 0.409, 0.69778, 0.0342, 0.1373, 58.5739
A_M = round(A_MTOT / 2, 4)
A_A = round(A_ARCSEC / (A_PLX / 1000.0), 3)
A_KEPLER_YR = math.sqrt(A_A ** 3 / A_MTOT)


def build_spec(sy_row):
    """The apply_specs spec for both pairs. `sy_row(name)` is the Systems row as a dict."""
    g, a = sy_row(GJ4113), sy_row(APM)
    g_l, a_l = g["Host luminosity (L-sun)"], a["Host luminosity (L-sun)"]
    assert g["Host mass (M-sun)"] == 0.47 and a["Host mass (M-sun)"] == A_MTOT, (g, a)
    g_half, a_half = round(g_l / 2, 5), round(a_l / 2, 5)
    reverse = (f"ADDED TO MULTI-STARS {DATE} (data/refuted_pairs/add_pairs.py): a system of stars with no planet now "
               "opens as a page of its own in the viewer, so its stars are on file. This reverses the 6 Oct 2026 "
               "decision above, which kept it off Multi-stars for having no live candidate. Count unchanged. Was 2.")

    g_mass_note = (
        f"WEAK -- INFERRED, equal-mass assumption. GJ 4113 is a twin SB2 ({MA23}, Sect. 4.5; {ST25}, Table 4) with "
        f"no published component mass. Blend Ks = {G_KS} (2MASS J19333940+3931372), parallax {G_PLX} mas (Gaia DR3 "
        f"nss_two_body_orbit) -> M_Ks = {G_MKS:.3f}; the {MANN} M_Ks relation (n = 5, no [Fe/H] term) gives "
        f"{G_BLEND:.3f} Msun for it as one star (Stefansson et al.'s single-star 0.42 +/- 0.02, reproduced). Split "
        f"equally, each component is 0.753 mag fainter, M_Ks = {G_MKS + 0.7526:.3f} -> {G_M} Msun. Relation scatter "
        f"~2%; valid for M_Ks 4-11, main-sequence stars. Marcussen & Albrecht's flux ratio of ~0.85 instead of 1 "
        f"gives {G_M85[0]:.3f} + {G_M85[1]:.3f}. Their working assumption, M1 = M2 = 0.47 Msun (Gaia DR3 "
        "binary_masses M1, the Systems row's value), is a mass for the blend's light and is not used here.")
    g_lum_note = (f"WEAK -- INFERRED: half the Systems row's {g_l} Lsun, which is the pair's combined light, on the "
                  "equal-mass assumption (see the Mass cell). Cifuentes et al. 2025 (A&A 693, A228) give 0.02593 "
                  "Lsun for the unresolved pair.")
    g_sep_note = (
        f"WEAK -- COMPUTED: a = (P^2 M)^(1/3) with P = {G_P_D} d = {G_P_D / 365.25:.4f} yr (Gaia DR3 "
        f"nss_two_body_orbit) and M = {2 * G_M:.3f} Msun, the inferred A + B (Mass cells) -> {G_A} au. Insensitive "
        f"to the flux ratio: {G_A85:.3f} au at 0.85. Rests on the Mann 2019 masses; with Marcussen & Albrecht's "
        f"assumed 0.47 + 0.47 Msun it would be {((G_P_D / 365.25) ** 2 * 0.94) ** (1 / 3):.3f} au. No spectroscopic "
        "orbit is published: P and e are Gaia's photocentre orbit, taken as the binary's own.")
    a_mass_note = (
        f"WEAK -- INFERRED, equal-mass assumption: half the pair's dynamical total, {A_MTOT} +/- 0.040 Msun "
        f"({VR26}, Table 4). No component mass is published. The pair is near-equal: Delta I = 0.1 mag at first "
        f"resolution ({VR22}, Table 2); WDS 07096-5704 lists 12.1 and 12.2 mag.")
    a_lum_note = (f"WEAK -- INFERRED: half the Systems row's {a_l} Lsun, which is the pair's combined light, on the "
                  "equal-mass assumption (see the Mass cell); Delta I = 0.1 mag.")
    a_sep_note = (
        f"COMPUTED from published values: a = {A_ARCSEC} +/- 0.0011 arcsec ({VR26}, Table 4) / parallax {A_PLX} mas "
        f"(Gaia DR3 nss_two_body_orbit) = {A_A} au (+/- 0.019 from a's error). Check: Kepler III with the paper's "
        f"Mtot {A_MTOT} Msun gives P = {A_KEPLER_YR:.3f} yr against its {A_P_YR}.")

    return [
        {"system": GJ4113, "action": "new_system", "old_count": 2, "new_count": 2,
         "host_overrides": {
             "Role in system": "host (= GJ 4113, Ross 1063; a twin SB2); drawn as GJ 4113 A, the SB2's primary, "
                               "with GJ 4113 B on the next row. Its candidate Gaia-ASOI-054 is on Rejected candidates",
             "Mass (M-sun)": G_M, "Luminosity (L-sun)": g_half,
             "Star data source": f"class, Teff: as the Systems tab's row, in COMBINED light of the SB2 | {DATE}: "
                                 "mass and L per component, INFERRED (orange, cell notes): equal split of the "
                                 "blend, Mann et al. 2019 M_Ks relation."},
         "host_orange": {"Mass (M-sun)": g_mass_note, "Luminosity (L-sun)": g_lum_note},
         "rows": [{"values": {
             "Star (component)": "GJ 4113 B",
             "Role in system": f"companion (SB2 secondary of GJ 4113; {MA23.split(' (')[0]})",
             "Mass (M-sun)": G_M, "Stellar Class": g["Stellar Class"], "Class (sort key)": g["Class (sort key)"],
             "Effective temp (K)": g["Effective temp (K)"], "Luminosity (L-sun)": g_half,
             "Star data source": "INFERRED, all of it: the unresolved SB2 secondary, assumed equal to A (Marcussen "
                                 "& Albrecht 2023 call it a twin binary, flux ratio ~0.85). Class and Teff are the "
                                 "blend's; mass and L as on A's row. The names A and B are this workbook's, not a "
                                 "catalogue's.",
             "Kinematics source": "none of its own: unresolved, shares GJ 4113's Gaia entry",
             "Orbital eccentricity (e)": G_E, "Orbit described": "B relative to A",
             "Orbit source": f"Gaia DR3 nss_two_body_orbit (Orbital) for 2052469973468984192: P = {G_P_D} +/- 0.74 "
                             f"d, e = {G_E} +/- 0.044. This is the photocentre orbit that Gaia-ASOI-054 was read "
                             f"from; {MA23} (Sect. 4.5) and {ST25} (Table 4, G-ASOI-54) find the star an SB2, so "
                             "it is the binary's orbit. Neither paper fits an orbit of its own.",
             "Separation from": GJ4113, "Separation (AU)": G_A, "Separation type": "semi-major axis",
             "Separation source": f"COMPUTED here, not published: Kepler III on Gaia DR3's P = {G_P_D} d and the "
                                  f"inferred total mass {2 * G_M:.3f} Msun (2 x {G_M}). Orange; see cell note."},
             "orange": {"Mass (M-sun)": g_mass_note, "Luminosity (L-sun)": g_lum_note,
                        "Stellar Class": "INFERRED: equal-mass secondary, so given the blend's class.",
                        "Effective temp (K)": "INFERRED: equal-mass secondary, so given the blend's Teff.",
                        "Separation (AU)": g_sep_note}}],
         "systems_text": "Gaia DR3 2052469973468984192 = GJ 4113 (Ross 1063): M2V, a twin SB2; drawn as GJ 4113 A "
                         "(host; candidate Gaia-ASOI-054 is on Rejected candidates)\n"
                         "GJ 4113 B: M2V, inferred equal to A (SB2 secondary; Marcussen & Albrecht 2023 Sect. 4.5); "
                         "the names A and B are this workbook's, not a catalogue's",
         "stars_note": reverse,
         "sp_paragraph": (
             f"GJ 4113 (Ross 1063), a twin SB2: {MA23}, Sect. 4.5 and Table 1 (two FIES spectra, flux ratio ~0.85, "
             f"M1 = M2 = 0.47 Msun ASSUMED); {ST25}, Table 4 (SB2; 0.42 +/- 0.02 Msun as one star). Neither gives "
             f"K1/K2, a mass ratio or an orbit. ORBIT: Gaia DR3 nss_two_body_orbit, P {G_P_D} d, e {G_E}. INFERRED "
             f"(orange): each star's mass {G_M} Msun, from the blend's 2MASS Ks {G_KS} and parallax {G_PLX} mas "
             f"(M_Ks {G_MKS:.3f}), split equally, through the {MANN} M_Ks relation, n = 5, no [Fe/H] term "
             f"(coefficients {', '.join(str(x) for x in MANN_A)}; zero point 7.5; scatter 2.0%; valid 4 < M_Ks < 11, "
             f"main-sequence, -0.6 < [Fe/H] < +0.4); as one star it gives {G_BLEND:.3f}, Stefansson et al.'s value. "
             f"Each star's L {g_half} Lsun = half the Systems row's {g_l}. Separation {G_A} au = (P^2 M)^(1/3). "
             "CONFIDENCE: LOW for the masses and the separation (no component is measured); the period is Gaia's. "
             "HOW TO VERIFY: IRSA fp_psc for the Ks, the Gaia archive for the orbit, Mann et al.'s Table 6 for the "
             "coefficients; data/refuted_pairs/add_pairs.py recomputes all of it.")},
        {"system": APM, "action": "new_system", "old_count": 2, "new_count": 2,
         "host_overrides": {
             "Role in system": "host (= APM 89 A, APMPM J0710-5704, WDS 07096-5704); the primary of the speckle "
                               "pair, with APM 89 B on the next row. Its candidate Gaia-ASOI-037 is on Rejected "
                               "candidates",
             "Mass (M-sun)": A_M, "Luminosity (L-sun)": a_half,
             "Star data source": f"class, Teff: as the Systems tab's row, in COMBINED light of the pair | {DATE}: "
                                 "mass and L per component, INFERRED (orange, cell notes): half the dynamical "
                                 "total mass of Vrijmoet et al. 2026, half the combined L."},
         "host_orange": {"Mass (M-sun)": a_mass_note, "Luminosity (L-sun)": a_lum_note},
         "rows": [{"values": {
             "Star (component)": "APM 89 B",
             "Role in system": f"companion (resolved by SOAR speckle; {VR22.split(' (')[0]}, {VR26.split(' (')[0]})",
             "Mass (M-sun)": A_M, "Stellar Class": a["Stellar Class"], "Class (sort key)": a["Class (sort key)"],
             "Effective temp (K)": a["Effective temp (K)"], "Luminosity (L-sun)": a_half,
             "Star data source": "orbit: Vrijmoet et al. 2026 Table 4. INFERRED: mass and L (half the pair's), "
                                 "class and Teff (the blend's); the pair is near-equal, Delta I = 0.1 mag "
                                 "(Vrijmoet et al. 2022).",
             "Kinematics source": "none of its own: 0.034 arcsec from A, shares its Gaia entry",
             "Orbital eccentricity (e)": A_E, "Orbit described": "B relative to A",
             "Orbit source": f"{VR26}, Table 4, APM 89 AB: P = {A_P_YR} +/- 0.00274 yr (254.86 d), a = {A_ARCSEC} "
                             f"+/- 0.0011 arcsec, e = {A_E} +/- 0.0275, i = 36.72 +/- 5.16 deg, node 310.25 +/- "
                             "8.43 deg, omega 125.72 +/- 8.06 deg, T0 2021.3645, Mtot 0.409 +/- 0.040 Msun; SOAR "
                             "speckle imaging only, a first orbit. Gaia DR3 nss_two_body_orbit has the same pair "
                             "at P = 253.48 d, e = 0.134 (the orbit Gaia-ASOI-037 was read from); the paper finds "
                             "the periods and eccentricities agree and the angles differ by 2.5-7.4 sigma.",
             "Separation from": APM, "Separation (AU)": A_A, "Separation type": "semi-major axis",
             "Separation source": f"COMPUTED from published values: {A_ARCSEC} arcsec (Vrijmoet et al. 2026, Table "
                                  f"4) / Gaia DR3 parallax {A_PLX} mas. Orange; see cell note."},
             "orange": {"Mass (M-sun)": a_mass_note, "Luminosity (L-sun)": a_lum_note,
                        "Stellar Class": "INFERRED: near-equal secondary (Delta I = 0.1 mag), so given the blend's "
                                         "class (WDS: M4V).",
                        "Effective temp (K)": "INFERRED: near-equal secondary, so given the blend's Teff.",
                        "Separation (AU)": a_sep_note}}],
         "systems_text": "Gaia DR3 5486916932205092352 = APM 89 A (APMPM J0710-5704, WDS 07096-5704): M4V (host; "
                         "candidate Gaia-ASOI-037 is on Rejected candidates)\n"
                         "APM 89 B: M4V, inferred near-equal to A (SOAR speckle pair, a = 0.034 arcsec, P = 0.698 "
                         "yr; Vrijmoet et al. 2026)",
         "stars_note": reverse,
         "sp_paragraph": (
             f"APM 89 AB (APMPM J0710-5704, WDS 07096-5704 TSN 140): {VR26}, Table 4: P {A_P_YR} +/- 0.00274 yr, "
             f"a {A_ARCSEC} +/- 0.0011 arcsec, e {A_E} +/- 0.0275, Mtot {A_MTOT} +/- 0.040 Msun; first resolved in "
             f"{VR22} (Delta I 0.1 mag). The paper does not discuss the planet candidate. INFERRED (orange): each "
             f"star's mass {A_M} Msun = Mtot / 2 and L {a_half} Lsun = half the Systems row's {a_l}, on the "
             f"near-equal pair; separation {A_A} au = a / Gaia DR3 parallax {A_PLX} mas, arithmetic on published "
             f"values (Kepler III with Mtot returns P = {A_KEPLER_YR:.3f} yr). CONFIDENCE: HIGH for the orbit's "
             "period and size (speckle and Gaia agree), MEDIUM for the equal split. HOW TO VERIFY: the paper's "
             "Table 4; the WDS summary line for 07096-5704; data/refuted_pairs/add_pairs.py.")},
    ]


def sp_lines(specs):
    return ["", f"STAR PAIRS WITH NO PLANET, ONTO MULTI-STARS, {DATE.upper()} (data/refuted_pairs/add_pairs.py)",
            "  Two Systems rows that count two stars had no Multi-stars rows: their Gaia DR3 astrometric 'planets' "
            "(Gaia-ASOI-054, Gaia-ASOI-037) are the pairs' own orbits and are on Rejected candidates, and on 6 Oct "
            "2026 the pairs were kept off Multi-stars for having no live candidate. The viewer now opens a system "
            "of stars with no planet as its stars and bands, so the stars are on file. Research by Claude from the "
            "papers' arXiv sources, IRSA and the ARI mirror of the Gaia archive; nothing from memory or Wikipedia. "
            "NICKNAMES written the same day on four Gaia-numbered Systems rows, each the name its own row and "
            "SIMBAD already give it: " + "; ".join(f"{k} -> {v}" for k, v in NICKNAMES.items()) + ". "
            "ORANGE BOXES RESTORED on GJ 773 B's two rows (mass, luminosity, HZ, class, Teff, primary mass, "
            "separation): the cells carried their INFERRED notes of 26 Sep 2026 but no box."
            ] + [f"  {NICKNAMES[s['system']]} ({s['system']}): {s['sp_paragraph']}" for s in specs]


def legend_lines(specs):
    return [f"STAR PAIRS WITH NO PLANET -- {DATE.upper()}",
            "GJ 4113 A+B and APM 89 A+B are on Multi-stars: two pairs whose Gaia 'planets' were the pairs' own "
            "orbits. Component masses, luminosities and both separations are inferred or computed (orange). Method and "
            f"citations on Sources & Provenance under 'STAR PAIRS WITH NO PLANET, ONTO MULTI-STARS, {DATE.upper()}'."]


def main():
    sys.argv = [sys.argv[0], str(SPEC)] + (["write"] if WRITE else [])
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "data" / "star_counts"))
    sys.path.insert(0, str(ROOT / "data" / "four_plus_stars"))
    import apply_specs as ap
    from hybrasil.data import google_sheets as gs
    from fill import letter, q
    ap.DATE, ap.sp_lines, ap.legend_lines = DATE, sp_lines, legend_lines
    ap.LOG = HERE / "apply_specs_log.json"

    sy = ap.Tab(ap.SY, key="System / Host")

    def sy_row(name):
        r = sy.rows_of(name)[0]
        return {h: sy.get(r, h) for h in sy.col}

    spec = build_spec(sy_row)
    SPEC.write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
    nick = {sy.a1("Nickname (IAU)", sy.rows_of(k)[0]): v for k, v in NICKNAMES.items()}
    nick_expect = {a1: "" for a1 in nick}
    nick_expect.update({sy.a1("System / Host", sy.rows_of(k)[0]): k for k in NICKNAMES})
    print(f"GJ 4113: M_Ks {G_MKS:.3f}, blend {G_BLEND:.3f}, each {G_M}, a {G_A} au (0.85: {G_M85}, {G_A85:.3f})")
    print(f"APM 89: each {A_M}, a {A_A} au, Kepler P {A_KEPLER_YR:.4f} yr vs {A_P_YR}")
    print("Nicknames:", nick)
    if WRITE:
        gs.update_cells(ap.SID, nick, expect=nick_expect)
        gs.invalidate_cache(ap.SID)
    ap.main()
    if not WRITE:
        return

    # Fix-ups the shared writer does not know about.
    ms = ap.Tab(ap.MS)
    fix, expect = {}, {}
    for comp, mass in (("GJ 4113 B", G_M), ("APM 89 B", A_M), (GJ4113, G_M), (APM, A_M)):
        r = ms.row_of(comp)
        # 'Primary mass' is the star the row's orbit is about: A's own inferred mass, not the blend's.
        fix[ms.a1("Primary mass (M-sun)", r)] = mass if comp.endswith(" B") else ""
        expect[ms.a1("Star (component)", r)] = comp
    gs.update_cells(ap.SID, fix, expect=expect)
    notes = {ms.a1("Primary mass (M-sun)", ms.row_of(c)): f"A's mass. See the Mass cell of {NICKNAMES[h]}'s host row."
             for c, h in (("GJ 4113 B", GJ4113), ("APM 89 B", APM))}
    gs.set_note(ap.SID, notes)
    # GJ 773 B's inferred cells carry their notes of 26 Sep 2026 but had lost their boxes.
    boxes = list(notes)
    for comp, heads in ((GJ773B, ("Mass (M-sun)", "Luminosity (L-sun)", "HZ distance")),
                        ("GJ 773 Bb", ("Mass (M-sun)", "Stellar Class", "Effective temp (K)", "Luminosity (L-sun)",
                                       "Primary mass (M-sun)", "Separation (AU)"))):
        r = ms.row_of(comp)
        have = gs.get_notes(ap.SID, f"{q(ap.MS)}!A{r}:{letter(len(ms.col) - 1)}{r}")
        for h in heads:
            a1 = f"{letter(ms.col[h])}{r}"
            assert "INFERRED" in have.get(a1, "") or "COMPUTED" in have.get(a1, ""), (comp, h, have.get(a1))
            boxes.append(ms.a1(h, r))
    gs.set_border(ap.SID, boxes, gs.INFERRED_BORDER)
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(ap.SID)
    LOG.write_text(json.dumps({"date": DATE, "nicknames": NICKNAMES, "boxes_restored": boxes, "title": title},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", title)


if __name__ == "__main__":
    main()
