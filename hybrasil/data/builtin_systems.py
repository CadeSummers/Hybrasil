# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Hardcoded well-known star systems using J2000 Keplerian elements.

Sources:
  Solar System: NASA planetary fact sheets + JPL DE430 mean elements at J2000.
  TRAPPIST-1: Agol et al. 2021, The Planetary Science Journal 2, 1.
  Alpha Centauri: Pourbaix et al. 2002 (binary orbit); Kervella et al. 2017 (Proxima orbit);
    Anglada-Escudé et al. 2016 (Proxima b); Faria et al. 2022 (Proxima d);
    Damasso et al. 2020 (Proxima c).
  Proxima Centauri: same sources as above; standalone focused system.
"""

from ..models.elements import KeplerianElements
from ..models.body import OrbitalBody
from ..models.system import StarSystem, BeltZone
from ..mechanics.orientation import (TOWARD_EARTH,
                                     galactic_centre_distance_ly,
                                     galactic_centre_in_sky_frame)
from .hierarchy import Look, NodeRow, hierarchy_bodies, relative_orbit
from ..mechanics.solvent_bands import SolventChoice, DEFAULT_CHOICE
from ..mechanics.units import M_SUN_KG, T_SUN_K

J2000 = 2451545.0  # Julian Date of J2000.0

# Bolometric luminosities, L/L_sun.  Taken from the catalog workbook so that a
# star drawn from this table and the same star drawn from --source catalog get
# the same solvent band rather than two subtly different ones.
_L_TRAPPIST_1  = 0.0005285766791
_L_ALPHA_CEN_A = 1.521
# Proxima's is Ribas et al. 2017 (A&A 603, A58), SED-integrated; the workbook
# took it on 2026-09-22 in place of 0.00126685, which was 16% low.
_L_PROXIMA     = 0.00151
_L_UPS_AND     = 3.56885103400897
_L_55_CNC_A    = 0.573260688081453
_L_55_CNC_B    = 0.00788

# Effective temperatures, K, which set each star's colour factor on its
# solvent bands (`mechanics.stellar_colour`).  From the catalog workbook for
# the same reason as the luminosities, except Proxima: the workbook cell was
# blank, and 2980 K is Ribas et al. 2017 (A&A 603, A58), the paper its
# luminosity comes from, whose R and Teff reproduce that luminosity.  55 Cnc B
# has none in the workbook and gets no colour correction rather than a guess.
_T_TRAPPIST_1  = 2516.0
_T_ALPHA_CEN_A = 5790.0
_T_ALPHA_CEN_B = 5260.0
_T_PROXIMA     = 2980.0
_T_UPS_AND     = 6212.0
_T_55_CNC_A    = 5172.0
_T_55_CNC_B    = None

# Sky positions (J2000), for the reference arrows.
#
# Every system here but the Solar System is quoted against the plane of the
# sky: TRAPPIST-1's inclinations come from transits, Alpha Centauri's from a
# visual-binary solution, Upsilon Andromedae's from HST astrometry.  Their
# reference plane is therefore the sky plane and their z axis is the line of
# sight, so the Sun is at `TOWARD_EARTH` and the galactic centre has to be
# worked out in that frame rather than taken from the ecliptic.
#
# Where a system's ascending nodes are a placeholder rather than a measurement
# -- TRAPPIST-1 and Proxima both carry Omega = 0 for every planet -- the sky
# frame's x axis is not really North, so only the line-of-sight component of
# these vectors means anything.  It is still the component that says whether
# the galactic centre lies beyond the system or back past us, and the ecliptic
# vector got even that wrong.
_SKY_TRAPPIST_1 = (346.62250,  -5.04139, 40.54)
_SKY_ALPHA_CEN  = (219.90208, -60.83389,  4.36)
_SKY_PROXIMA    = (217.42917, -62.67944,  4.24)
_SKY_UPS_AND    = ( 24.19933,  41.40544, 43.72)
_SKY_55_CNC     = (133.14921,  28.33082, 41.05)

# Rotation-axis unit vectors in J2000 ecliptic coordinates.
# Derived from IAU 2018 Working Group report (Archinal et al. 2018):
# equatorial (RA, Dec) of each body's north pole → rotated into ecliptic frame
# using ε = 23.4393°.  Retrograde rotators (Venus, Uranus) are negated so the
# vector represents the physical angular-momentum direction (obliquity > 90°),
# making Venus appear nearly upside-down and Uranus nearly sideways.
_POLE_SUN     = ( 0.122, -0.029,  0.992)  # obliquity ≈ 7.2°
_POLE_MERCURY = ( 0.091, -0.082,  0.993)  # obliquity ≈ 6.8°
_POLE_VENUS   = (-0.019, -0.009, -1.000)  # obliquity ≈ 177.4° (retrograde, negated)
_POLE_EARTH   = ( 0.000,  0.398,  0.917)  # obliquity ≈ 23.4°
_POLE_MARS    = ( 0.446, -0.055,  0.894)  # obliquity ≈ 26.6°
_POLE_JUPITER = (-0.015, -0.033,  0.999)  # obliquity ≈ 3.1°
_POLE_SATURN  = ( 0.085,  0.462,  0.883)  # obliquity ≈ 28.0°
_POLE_URANUS  = ( 0.213,  0.968, -0.134)  # obliquity ≈ 97.7° (retrograde, negated)
_POLE_NEPTUNE = ( 0.354, -0.307,  0.883)  # obliquity ≈ 28.0°
_POLE_PLUTO   = (-0.678,  0.625, -0.388)  # obliquity ≈ 112.8° (IAU pole already retrograde-facing)

# ── Source reference constants ─────────────────────────────────────────────
# Each entry is [display_label, url] for rendering as a hyperlink.
_SRC_JPL_SSD  = ["JPL Solar System Dynamics",        "https://ssd.jpl.nasa.gov/"]
_SRC_JPL_SATS = ["JPL Satellite Physical Parameters", "https://ssd.jpl.nasa.gov/sats/phys_par/"]
_SRC_IAU_POLE = ["IAU Working Group: Archinal et al. 2018", "https://doi.org/10.1007/s10569-017-9805-5"]
_SRC_AGOL     = ["Agol et al. 2021, PSJ 2 1",        "https://doi.org/10.3847/PSJ/abd022"]
_SRC_POURBAIX  = ["Pourbaix et al. 2002, A&A 382",    "https://doi.org/10.1051/0004-6361:20011605"]
_SRC_BATYGIN   = ["Batygin & Brown 2016, AJ 151",    "https://doi.org/10.3847/0004-6256/151/2/22"]
_SRC_KERVELLA_2017 = ["Kervella et al. 2017, A&A 598", "https://doi.org/10.1051/0004-6361/201629201"]
_SRC_ANGLADA_2016  = ["Anglada-Escudé et al. 2016, Nature 536", "https://doi.org/10.1038/nature19106"]
_SRC_DAMASSO_2020  = ["Damasso et al. 2020, Science Advances 6", "https://doi.org/10.1126/sciadv.aax7467"]
_SRC_FARIA_2022    = ["Faria et al. 2022, A&A 658",    "https://doi.org/10.1051/0004-6361/202142337"]
_SRC_WAGNER_2021   = ["Wagner et al. 2021, Nat. Commun. 12", "https://doi.org/10.1038/s41467-021-21176-6"]
# Upsilon Andromedae comes from the project catalog workbook rather than from a
# paper read directly, so it cites what the workbook cites: the Open Exoplanet
# Catalogue snapshot its orbit columns carry, and the archive entry for the
# system.
_SRC_OEC        = ["Open Exoplanet Catalogue (catalog workbook, 2026-07-31)",
                   "https://www.openexoplanetcatalogue.com/"]
_SRC_EXOARCHIVE = ["NASA Exoplanet Archive: ups And",
                   "https://exoplanetarchive.ipac.caltech.edu/overview/ups%20And"]
# The orbital angles the catalog has no column for.  Deitrick et al. searched
# for three-planet configurations consistent with both the radial velocities
# and the HST astrometry, and integrated them for 100 Myr; PRO1 is their
# nominal case, the lowest-chi-squared prograde solution that stayed stable.
_SRC_DEITRICK  = ["Deitrick et al. 2015, ApJ 798, 46",
                  "https://doi.org/10.1088/0004-637X/798/1/46"]
_SRC_MCARTHUR  = ["McArthur et al. 2010, ApJ 715, 1203 (HST astrometry)",
                  "https://doi.org/10.1088/0004-637X/715/2/1203"]
# ups And B, the wide M dwarf: its discovery, and the mass and Teff the
# catalog workbook's row carries (Gaia DR2 photometry and evolutionary models).
_SRC_LOWRANCE  = ["Lowrance, Kirkpatrick & Beichman 2002, ApJ 572, L79 (ups And B)",
                  "https://ui.adsabs.harvard.edu/abs/2002ApJ...572L..79L/abstract"]
_SRC_MUGRAUER_2019 = ["Mugrauer 2019, MNRAS 490, 5088, table 4 (ups And B)",
                      "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/MNRAS/490/5088"]
# Its luminosity, as the workbook's ups And B row has it since 9 Oct 2026: TIC v8.2
# (TIC 189576909 = Gaia DR3 348020242217448576, a source of its own 55 arcsec from
# A), 0.00445 +/- 0.00116 L_sun, which its R and Teff (0.223 R_sun, 3159 K) reproduce.
_L_UPS_AND_B   = 0.00445
_SRC_TIC_UPS_AND_B = ["Stassun et al. 2019, AJ 158, 138 (TESS Input Catalog v8.2), TIC 189576909 (ups And B)",
                      "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=IV/39/tic82"]
# Where ups And B is: Gaia DR3 positions of the two stars at 2016.0 put B
# 55.62 arcsec from A at position angle 148.77 deg, 749.6 AU in projection at
# A's parallax (74.194 mas).  No orbit has been measured, so B is drawn the way
# any unsolved companion is: a circle at its projected separation (a lower
# bound on the real one), here laid in the sky plane -- i = 0, node 0,
# periastron 0, which with x North and y East makes the orbital phase the
# position angle -- and phased to stand at that position angle in 2016.0.
# The sense of motion and the depth are unknown.
_PA_UPS_AND_B  = 148.77
_A_UPS_AND_B   = 749.6
_J2016         = 2457389.0  # Julian Date of 2016.0, Gaia DR3's epoch
# 55 Cancri.  Bourrier et al. re-fitted two decades of radial velocities with
# the star's 3822-day magnetic cycle modelled as a sixth Keplerian, which is
# what makes their outer-planet solution differ from earlier ones.
_SRC_BOURRIER  = ["Bourrier et al. 2018, A&A 619, A1",
                  "https://doi.org/10.1051/0004-6361/201833154"]
_SRC_VON_BRAUN = ["von Braun et al. 2011, ApJ 740, 49 (interferometric radius)",
                  "https://doi.org/10.1088/0004-637X/740/1/49"]
_SRC_MUGRAUER  = ["Mugrauer et al. 2006, AN 327, 321 (55 Cnc B)",
                  "https://doi.org/10.1002/asna.200510539"]
# The two planets of 55 Cnc B.  SPIRou radial velocities of the companion
# alone, 69 visits from 2019 to 2025; both orbits fitted circular.
_SRC_MOUTOU    = ["Moutou et al. 2026, A&A (SPIRou; 55 Cnc B b and c), Table 4",
                  "https://arxiv.org/abs/2510.11523"]
_SRC_MOUTOU_G  = ["Moutou et al. 2025, A&A accepted (SPIRou; candidate 55 Cnc g), Table 8",
                  "https://arxiv.org/abs/2510.11523"]
# Hipparcos-Gaia astrometry plus RV: 55 Cnc d's inclination and node, and a
# lofti_gaia orbit for 55 Cnc B about A.  Table 4.
_SRC_XIAO      = ["Xiao, Teng et al. 2026, ApJL (arXiv:2609.01377), Table 4",
                  "https://arxiv.org/abs/2609.01377"]
_SRC_EXO_55CNC = ["NASA Exoplanet Archive: 55 Cnc",
                  "https://exoplanetarchive.ipac.caltech.edu/overview/55%20Cnc"]


def _nasa_fact(body: str) -> list:
    """Return a [label, url] source entry for a NASA planetary fact sheet."""
    slug = body.lower().replace(" ", "")
    return [f"NASA {body} Fact Sheet",
            f"https://nssdc.gsfc.nasa.gov/planetary/factsheet/{slug}fact.html"]


# ── Per-body display metadata (notes shown in the info panel) ─────────────────
# Maps body name → dict of optional note keys:
#   mass_note  – shown next to the mass value
#   tilt_note  – shown next to the axial-tilt value
BODY_METADATA: dict[str, dict] = {
    # Reference-frame clarifications
    "Sun":       {"tilt_note": "relative to ecliptic"},
    "Moon":      {"tilt_note": "relative to ecliptic"},
    # Tidally-locked moons: tilts are very small and not precisely measured
    "Io":        {"tilt_note": "estimated; tidally locked"},
    "Europa":    {"tilt_note": "estimated; tidally locked"},
    "Ganymede":  {"tilt_note": "estimated; tidally locked"},
    "Callisto":  {"tilt_note": "estimated; tidally locked"},
    "Titan":     {"tilt_note": "estimated; tidally locked"},
    "Triton":    {"tilt_note": "unknown; complex retrograde orbit"},
    # Eris tilt poorly constrained
    "Eris":      {"tilt_note": "poorly constrained"},
    # Planet Nine — all parameters are theoretical predictions, not observations
    "Planet Nine": {
        "mass_note":     "predicted (Batygin & Brown 2016)",
        "period_note":   "predicted; body unconfirmed",
        "velocity_note": "predicted; mean, computed",
        "tilt_note":     "unknown; body unconfirmed",
    },
    # Alpha Centauri Ab — single-epoch thermal IR detection (Wagner et al. 2021)
    "Alpha Centauri Ab": {
        "mass_note":   "unknown; single-epoch thermal IR detection",
        "period_note": "candidate; not independently confirmed",
        "tilt_note":   "unknown",
    },
    # Proxima Centauri — orbit around Alpha Cen A is a best-estimate (Kervella et al. 2017)
    "Proxima Centauri": {
        "period_note": "best estimate (Kervella et al. 2017); very uncertain",
        "tilt_note":   "unknown",
    },
    "Proxima Centauri b": {"mass_note": "minimum mass (sin i); true mass unknown"},
    # Upsilon Andromedae — dynamical masses, since the orbital planes of c and
    # d were measured astrometrically.  Planet b's plane never was: everything
    # about its orientation, and therefore its mass, is one stable trial.
    "Upsilon Andromedae b": {
        "mass_note":   "2-9 M_Jup across stable solutions; plane not detected",
        "period_note": "orbit well measured; orientation is a stable trial",
        "tilt_note":   "unknown",
    },
    "Upsilon Andromedae c": {
        "mass_note": "dynamical mass (Deitrick et al. 2015), not Msini",
        "tilt_note": "unknown",
    },
    "Upsilon Andromedae d": {
        "mass_note": "dynamical mass (Deitrick et al. 2015), not Msini",
        "tilt_note": "unknown",
    },
    "Proxima Centauri c": {
        "mass_note":   "candidate; minimum mass estimate",
        "period_note": "candidate; disputed",
    },
    "Proxima Centauri d": {"mass_note": "minimum mass (sin i); very uncertain"},
    # TRAPPIST-1 planet masses derived from transit-timing variations
    "TRAPPIST-1b": {"mass_note": "estimated (transit timing variations)"},
    "TRAPPIST-1c": {"mass_note": "estimated (transit timing variations)"},
    "TRAPPIST-1d": {"mass_note": "estimated (transit timing variations)"},
    "TRAPPIST-1e": {"mass_note": "estimated (transit timing variations)"},
    "TRAPPIST-1f": {"mass_note": "estimated (transit timing variations)"},
    "TRAPPIST-1g": {"mass_note": "estimated (transit timing variations)"},
    "TRAPPIST-1h": {"mass_note": "estimated (transit timing variations)"},
}


def get_body_metadata(name: str) -> dict:
    """Return display-metadata notes for a built-in body, or empty dict."""
    return BODY_METADATA.get(name, {})


def _solar_system(bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    bodies = [
        OrbitalBody(name="Sun", body_type="star", radius_km=695700.0,
                    mass_kg=1.989e30, luminosity_sun=1.0, teff_k=T_SUN_K,
                    color="#FFF7AA", pole=_POLE_SUN,
                    axial_tilt_deg=7.25,
                    sources=[_nasa_fact("Sun"), _SRC_IAU_POLE]),

        OrbitalBody(name="Mercury", body_type="planet", parent="Sun",
                    radius_km=2439.7, mass_kg=3.301e23, color="#B5B5B5", pole=_POLE_MERCURY,
                    axial_tilt_deg=0.034,
                    sources=[_nasa_fact("Mercury"), _SRC_JPL_SSD],
                    elements=KeplerianElements(
                        semi_major_axis=0.38710, eccentricity=0.20563,
                        inclination=7.005, longitude_of_ascending_node=48.331,
                        argument_of_periapsis=29.124, mean_anomaly_at_epoch=174.796,
                        epoch=J2000, period=87.969)),

        OrbitalBody(name="Venus", body_type="planet", parent="Sun",
                    radius_km=6051.8, mass_kg=4.867e24, color="#E8D5A3", pole=_POLE_VENUS,
                    axial_tilt_deg=177.36,
                    sources=[_nasa_fact("Venus"), _SRC_JPL_SSD],
                    elements=KeplerianElements(
                        semi_major_axis=0.72333, eccentricity=0.00677,
                        inclination=3.395, longitude_of_ascending_node=76.680,
                        argument_of_periapsis=54.884, mean_anomaly_at_epoch=50.416,
                        epoch=J2000, period=224.701)),

        OrbitalBody(name="Earth", body_type="planet", parent="Sun",
                    radius_km=6371.0, mass_kg=5.972e24, color="#4488FF", pole=_POLE_EARTH,
                    axial_tilt_deg=23.44,
                    sources=[_nasa_fact("Earth"), _SRC_JPL_SSD],
                    elements=KeplerianElements(
                        semi_major_axis=1.00000, eccentricity=0.01671,
                        inclination=0.000, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=102.937, mean_anomaly_at_epoch=100.464,
                        epoch=J2000, period=365.256)),

        OrbitalBody(name="Moon", body_type="moon", parent="Earth",
                    radius_km=1737.4, mass_kg=7.342e22, color="#AAAAAA",
                    axial_tilt_deg=6.68,
                    sources=[_nasa_fact("Moon"), _SRC_JPL_SATS],
                    elements=KeplerianElements(
                        semi_major_axis=0.00257, eccentricity=0.0549,
                        inclination=5.145, longitude_of_ascending_node=125.08,
                        argument_of_periapsis=318.15, mean_anomaly_at_epoch=115.36,
                        epoch=J2000, period=27.322)),

        OrbitalBody(name="Mars", body_type="planet", parent="Sun",
                    radius_km=3389.5, mass_kg=6.390e23, color="#CC4422", pole=_POLE_MARS,
                    axial_tilt_deg=25.19,
                    sources=[_nasa_fact("Mars"), _SRC_JPL_SSD],
                    elements=KeplerianElements(
                        semi_major_axis=1.52366, eccentricity=0.09341,
                        inclination=1.850, longitude_of_ascending_node=49.558,
                        argument_of_periapsis=286.502, mean_anomaly_at_epoch=19.373,
                        epoch=J2000, period=686.971)),

        OrbitalBody(name="Jupiter", body_type="planet", parent="Sun",
                    radius_km=69911.0, mass_kg=1.898e27, color="#C88B3A", pole=_POLE_JUPITER,
                    axial_tilt_deg=3.13,
                    sources=[_nasa_fact("Jupiter"), _SRC_JPL_SSD],
                    elements=KeplerianElements(
                        semi_major_axis=5.20336, eccentricity=0.04839,
                        inclination=1.303, longitude_of_ascending_node=100.464,
                        argument_of_periapsis=273.867, mean_anomaly_at_epoch=20.020,
                        epoch=J2000, period=4332.589)),

        OrbitalBody(name="Io", body_type="moon", parent="Jupiter",
                    radius_km=1821.6, color="#E8D060",
                    axial_tilt_deg=0.05,
                    sources=[_SRC_JPL_SATS,
                             ["NASA Galilean Moon Fact Sheet",
                              "https://nssdc.gsfc.nasa.gov/planetary/factsheet/galileanfact_table.html"]],
                    elements=KeplerianElements(
                        semi_major_axis=0.002819, eccentricity=0.0041,
                        inclination=0.036, longitude_of_ascending_node=43.977,
                        argument_of_periapsis=84.129, mean_anomaly_at_epoch=342.021,
                        epoch=J2000, period=1.769)),

        OrbitalBody(name="Europa", body_type="moon", parent="Jupiter",
                    radius_km=1560.8, color="#C8A870",
                    axial_tilt_deg=0.10,
                    sources=[_SRC_JPL_SATS,
                             ["NASA Galilean Moon Fact Sheet",
                              "https://nssdc.gsfc.nasa.gov/planetary/factsheet/galileanfact_table.html"]],
                    elements=KeplerianElements(
                        semi_major_axis=0.004486, eccentricity=0.0094,
                        inclination=0.470, longitude_of_ascending_node=219.106,
                        argument_of_periapsis=88.970, mean_anomaly_at_epoch=171.016,
                        epoch=J2000, period=3.552)),

        OrbitalBody(name="Ganymede", body_type="moon", parent="Jupiter",
                    radius_km=2634.1, color="#9898A8",
                    axial_tilt_deg=0.33,
                    sources=[_SRC_JPL_SATS,
                             ["NASA Galilean Moon Fact Sheet",
                              "https://nssdc.gsfc.nasa.gov/planetary/factsheet/galileanfact_table.html"]],
                    elements=KeplerianElements(
                        semi_major_axis=0.007155, eccentricity=0.0013,
                        inclination=0.195, longitude_of_ascending_node=63.552,
                        argument_of_periapsis=192.417, mean_anomaly_at_epoch=317.540,
                        epoch=J2000, period=7.155)),

        OrbitalBody(name="Callisto", body_type="moon", parent="Jupiter",
                    radius_km=2410.3, color="#605850",
                    axial_tilt_deg=0.19,
                    sources=[_SRC_JPL_SATS,
                             ["NASA Galilean Moon Fact Sheet",
                              "https://nssdc.gsfc.nasa.gov/planetary/factsheet/galileanfact_table.html"]],
                    elements=KeplerianElements(
                        semi_major_axis=0.012585, eccentricity=0.0074,
                        inclination=0.281, longitude_of_ascending_node=298.848,
                        argument_of_periapsis=52.643, mean_anomaly_at_epoch=181.408,
                        epoch=J2000, period=16.690)),

        OrbitalBody(name="Saturn", body_type="planet", parent="Sun",
                    radius_km=58232.0, mass_kg=5.683e26, color="#E8D080", pole=_POLE_SATURN,
                    axial_tilt_deg=26.73,
                    sources=[_nasa_fact("Saturn"), _SRC_JPL_SSD],
                    elements=KeplerianElements(
                        semi_major_axis=9.53707, eccentricity=0.05386,
                        inclination=2.489, longitude_of_ascending_node=113.665,
                        argument_of_periapsis=339.392, mean_anomaly_at_epoch=317.021,
                        epoch=J2000, period=10759.22)),

        OrbitalBody(name="Titan", body_type="moon", parent="Saturn",
                    radius_km=2574.7, color="#E8A840",
                    axial_tilt_deg=0.33,
                    sources=[_SRC_JPL_SATS,
                             ["NASA Titan Fact Sheet",
                              "https://nssdc.gsfc.nasa.gov/planetary/factsheet/titanfact.html"]],
                    elements=KeplerianElements(
                        semi_major_axis=0.008168, eccentricity=0.0288,
                        inclination=0.306, longitude_of_ascending_node=28.060,
                        argument_of_periapsis=180.532, mean_anomaly_at_epoch=163.436,
                        epoch=J2000, period=15.945)),

        OrbitalBody(name="Uranus", body_type="planet", parent="Sun",
                    radius_km=25362.0, mass_kg=8.681e25, color="#88DDEE", pole=_POLE_URANUS,
                    axial_tilt_deg=97.77,
                    sources=[_nasa_fact("Uranus"), _SRC_JPL_SSD],
                    elements=KeplerianElements(
                        semi_major_axis=19.19126, eccentricity=0.04726,
                        inclination=0.773, longitude_of_ascending_node=74.006,
                        argument_of_periapsis=96.999, mean_anomaly_at_epoch=142.238,
                        epoch=J2000, period=30688.5)),

        OrbitalBody(name="Neptune", body_type="planet", parent="Sun",
                    radius_km=24622.0, mass_kg=1.024e26, color="#4466EE", pole=_POLE_NEPTUNE,
                    axial_tilt_deg=28.32,
                    sources=[_nasa_fact("Neptune"), _SRC_JPL_SSD],
                    elements=KeplerianElements(
                        semi_major_axis=30.06896, eccentricity=0.00859,
                        inclination=1.770, longitude_of_ascending_node=131.784,
                        argument_of_periapsis=276.336, mean_anomaly_at_epoch=256.228,
                        epoch=J2000, period=60182.0)),

        OrbitalBody(name="Triton", body_type="moon", parent="Neptune",
                    radius_km=1353.4, color="#AABBCC",
                    axial_tilt_deg=None,   # complex: retrograde orbit, tilt ~130° to Neptune's equator
                    sources=[_SRC_JPL_SATS,
                             ["NASA Triton Fact Sheet",
                              "https://nssdc.gsfc.nasa.gov/planetary/factsheet/tritonfact.html"]],
                    elements=KeplerianElements(
                        semi_major_axis=0.002371, eccentricity=0.000016,
                        inclination=156.865, longitude_of_ascending_node=177.43,
                        argument_of_periapsis=0.0, mean_anomaly_at_epoch=352.26,
                        epoch=J2000, period=5.877)),

        OrbitalBody(name="Pluto", body_type="asteroid", parent="Sun",
                    radius_km=1188.3, color="#BB9977", pole=_POLE_PLUTO,
                    axial_tilt_deg=122.53,
                    sources=[_nasa_fact("Pluto"),
                             ["JPL Small-Body Database",
                              "https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=134340"]],
                    elements=KeplerianElements(
                        semi_major_axis=39.48169, eccentricity=0.24881,
                        inclination=17.141, longitude_of_ascending_node=110.299,
                        argument_of_periapsis=113.834, mean_anomaly_at_epoch=14.530,
                        epoch=J2000, period=90560.0)),

        OrbitalBody(name="Eris", body_type="asteroid", parent="Sun",
                    radius_km=1163.0, color="#CCCCBB",
                    axial_tilt_deg=None,   # poorly constrained
                    sources=[["JPL Small-Body Database",
                               "https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=136199"],
                             ["Brown & Schaller 2007, Science 316",
                              "https://doi.org/10.1126/science.1139415"]],
                    elements=KeplerianElements(
                        semi_major_axis=67.864, eccentricity=0.44177,
                        inclination=44.040, longitude_of_ascending_node=35.951,
                        argument_of_periapsis=151.639, mean_anomaly_at_epoch=198.177,
                        epoch=J2000, period=204199.0)),

        # Hypothetical Planet Nine — orbital elements are predicted, not observed.
        # Best-fit parameters from Batygin & Brown 2016 (AJ 151).
        # Mass, radius, and position are unconstrained; shown here as a representative orbit.
        OrbitalBody(name="Planet Nine", body_type="planet", parent="Sun",
                    display_name="Planet Nine (hypothetical)",
                    status="hypothetical",
                    radius_km=15000.0, mass_kg=4.5e25, color="#7799BB",
                    axial_tilt_deg=None,
                    sources=[_SRC_BATYGIN,
                             ["Batygin et al. 2019, PhR 805",
                              "https://doi.org/10.1016/j.physrep.2019.01.009"]],
                    elements=KeplerianElements(
                        semi_major_axis=700.0, eccentricity=0.60,
                        inclination=30.0, longitude_of_ascending_node=100.0,
                        argument_of_periapsis=150.0, mean_anomaly_at_epoch=180.0,
                        epoch=J2000, period=6758000.0)),
    ]
    return StarSystem(
        name="Solar System",
        description="Our solar system: 8 planets, major moons, Pluto, and Eris. J2000 elements. "
                    + bands.note(1.0, bodies, "Sun", T_SUN_K),
        bodies=bodies,
        source="builtin",
        belt_zones=[
            BeltZone("Asteroid Belt", r_inner_au=2.2,  r_outer_au=3.2,  color="#997755", opacity=0.15),
            BeltZone("Kuiper Belt",   r_inner_au=30.0, r_outer_au=50.0, color="#446688", opacity=0.10),
        ] + bands.zones_for_system(bodies),
        distance_to_galactic_center_ly=26670.0,
    )


def _trappist1(bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    """TRAPPIST-1 system. Elements from Agol et al. 2021.

    Planet masses are median estimates from transit-timing variations (Agol et al. 2021,
    Table 3).  Axial tilts are unknown for all bodies.
    """
    _src = [_SRC_AGOL,
            ["Gillon et al. 2017, Nature 542", "https://doi.org/10.1038/nature21360"]]
    bodies = [
        OrbitalBody(name="TRAPPIST-1", body_type="star",
                    radius_km=84550.0, mass_kg=1.687e29,
                    luminosity_sun=_L_TRAPPIST_1, teff_k=_T_TRAPPIST_1,
                    color="#FF6622",
                    axial_tilt_deg=None,
                    sources=[_SRC_AGOL,
                             ["Gillon et al. 2017, Nature 542",
                              "https://doi.org/10.1038/nature21360"]]),

        OrbitalBody(name="TRAPPIST-1b", body_type="planet", parent="TRAPPIST-1",
                    radius_km=7200.0, mass_kg=8.21e24, color="#DD4444",
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.01154, eccentricity=0.00622,
                        inclination=89.728, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=336.86, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=1.51088)),

        OrbitalBody(name="TRAPPIST-1c", body_type="planet", parent="TRAPPIST-1",
                    radius_km=7620.0, mass_kg=7.81e24, color="#EE6633",
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.01580, eccentricity=0.00654,
                        inclination=89.778, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=282.41, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=2.42179)),

        OrbitalBody(name="TRAPPIST-1d", body_type="planet", parent="TRAPPIST-1",
                    radius_km=5350.0, mass_kg=2.32e24, color="#FFAA44",
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.02227, eccentricity=0.00837,
                        inclination=89.896, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=180.0, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=4.04982)),

        OrbitalBody(name="TRAPPIST-1e", body_type="planet", parent="TRAPPIST-1",
                    radius_km=5790.0, mass_kg=4.13e24, color="#44BB66",
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.02925, eccentricity=0.00510,
                        inclination=89.793, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=180.0, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=6.09957)),

        OrbitalBody(name="TRAPPIST-1f", body_type="planet", parent="TRAPPIST-1",
                    radius_km=6710.0, mass_kg=6.21e24, color="#4488CC",
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.03849, eccentricity=0.01007,
                        inclination=89.740, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=180.0, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=9.20669)),

        OrbitalBody(name="TRAPPIST-1g", body_type="planet", parent="TRAPPIST-1",
                    radius_km=7660.0, mass_kg=7.89e24, color="#8844BB",
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.04683, eccentricity=0.00208,
                        inclination=89.742, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=180.0, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=12.35294)),

        OrbitalBody(name="TRAPPIST-1h", body_type="planet", parent="TRAPPIST-1",
                    radius_km=5680.0, mass_kg=1.95e24, color="#AA66DD",
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.06189, eccentricity=0.00567,
                        inclination=89.805, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=180.0, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=18.76730)),
    ]
    return StarSystem(
        name="TRAPPIST-1",
        description="Seven Earth-sized planets around the ultracool red dwarf TRAPPIST-1. "
                    "Elements from Agol et al. 2021. "
                    + bands.note(_L_TRAPPIST_1, bodies, "TRAPPIST-1",
                                 _T_TRAPPIST_1),
        bodies=bodies,
        source="builtin",
        belt_zones=bands.zones_for_system(bodies),
        # TRAPPIST-1: RA 23h06m29.4s, Dec -05°02'29". Transit inclinations are
        # measured from the plane of the sky, so that is this system's
        # reference plane and the Sun lies along its z axis.
        distance_from_sun_ly=40.54,
        solar_system_direction=TOWARD_EARTH,
        galactic_center_direction=galactic_centre_in_sky_frame(*_SKY_TRAPPIST_1),
        sky_frame_radec=_SKY_TRAPPIST_1[:2],
        distance_to_galactic_center_ly=26666.0,
    )


def _alpha_centauri(bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    """Alpha Centauri triple system: A, B, and Proxima Centauri at true scale.

    Alpha Centauri A (G2V) sits at the origin; B (K1V) orbits it at ~23.4 AU
    (Pourbaix et al. 2002).  Proxima Centauri (M5.5Ve) orbits at ~8,700 AU
    semi-major axis (best estimate, Kervella et al. 2017) — its orbit is marked
    hypothetical (dashed) because the binding is not yet confirmed.

    Proxima hosts three known / candidate planets:
      - Proxima b  (confirmed, Anglada-Escudé et al. 2016)
      - Proxima d  (confirmed, Faria et al. 2022)
      - Proxima c  (candidate, Damasso et al. 2020)

    Note: At this scale the A-B binary (~23 AU) is a tiny dot near the origin;
    use the `proxima-centauri` system for a focused view of Proxima's planets.
    """
    _src_hip = ["ESA Hipparcos Catalogue", "https://www.cosmos.esa.int/web/hipparcos/home"]
    bodies = [
        OrbitalBody(name="Alpha Centauri A", body_type="star",
                    radius_km=852800.0, mass_kg=2.187e30,
                    luminosity_sun=_L_ALPHA_CEN_A, teff_k=_T_ALPHA_CEN_A,
                    color="#FFF5AA",
                    axial_tilt_deg=None,
                    sources=[_SRC_POURBAIX, _src_hip]),

        OrbitalBody(name="Alpha Centauri B", body_type="star",
                    parent="Alpha Centauri A",
                    radius_km=601200.0, mass_kg=1.804e30,
                    luminosity_sun=0.503, teff_k=_T_ALPHA_CEN_B,
                    color="#FFBB66",
                    axial_tilt_deg=None,
                    sources=[_SRC_POURBAIX, _src_hip],
                    elements=KeplerianElements(
                        semi_major_axis=23.4, eccentricity=0.5179,
                        inclination=79.20, longitude_of_ascending_node=204.87,
                        argument_of_periapsis=231.65, mean_anomaly_at_epoch=200.1,
                        epoch=J2000, period=29186.8)),

        # Alpha Centauri Ab — candidate detected in thermal mid-IR by Wagner et al. 2021.
        # Single-epoch detection at ~1.1 AU from Alpha Cen A; not independently confirmed.
        # Period derived from Kepler's third law (M_A = 1.1 M_sun, a = 1.1 AU → P ≈ 401.8 d).
        OrbitalBody(name="Alpha Centauri Ab", body_type="planet",
                    parent="Alpha Centauri A",
                    display_name="Alpha Centauri Ab (candidate)",
                    status="hypothetical",
                    radius_km=18000.0, color="#CC88FF",
                    axial_tilt_deg=None,
                    sources=[_SRC_WAGNER_2021],
                    elements=KeplerianElements(
                        semi_major_axis=1.1, eccentricity=0.0,
                        inclination=0.0, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=0.0, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=401.8)),

        # Proxima Centauri — best-estimate orbit from Kervella et al. 2017.
        # SMA 8,700 AU, e=0.50 → aphelion ~13,050 AU (consistent with current ~13,000 AU separation).
        # M0=175° places it near aphelion at J2000.  Marked hypothetical because
        # gravitational binding is unconfirmed; orbit dashes automatically via orbit_dash().
        OrbitalBody(name="Proxima Centauri", body_type="star",
                    parent="Alpha Centauri A",
                    display_name="Proxima Centauri (hypothetical orbit)",
                    status="hypothetical",
                    radius_km=107300.0, mass_kg=2.428e29,
                    luminosity_sun=_L_PROXIMA, teff_k=_T_PROXIMA,
                    color="#FF8866",
                    axial_tilt_deg=None,
                    sources=[_SRC_KERVELLA_2017,
                             ["Henry et al. 1999, ApJ 512",
                              "https://doi.org/10.1086/306793"]],
                    elements=KeplerianElements(
                        semi_major_axis=8700.0, eccentricity=0.50,
                        inclination=107.6, longitude_of_ascending_node=126.0,
                        argument_of_periapsis=72.0, mean_anomaly_at_epoch=175.0,
                        epoch=J2000, period=199800000.0)),

        # Proxima b — confirmed, RV detection (Anglada-Escudé et al. 2016).
        # Minimum mass ~1.27 M_Earth; inclination unknown, e~0 assumed.
        OrbitalBody(name="Proxima Centauri b", body_type="planet",
                    parent="Proxima Centauri",
                    radius_km=7160.0, mass_kg=7.58e24, color="#88BBFF",
                    axial_tilt_deg=None,
                    sources=[_SRC_ANGLADA_2016],
                    elements=KeplerianElements(
                        semi_major_axis=0.04856, eccentricity=0.0,
                        inclination=0.0, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=0.0, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=11.2186)),

        # Proxima d — confirmed, RV detection (Faria et al. 2022).
        # Minimum mass ~0.26 M_Earth; interior to Proxima b.
        OrbitalBody(name="Proxima Centauri d", body_type="planet",
                    parent="Proxima Centauri",
                    radius_km=4500.0, mass_kg=1.553e24, color="#AAFFCC",
                    axial_tilt_deg=None,
                    sources=[_SRC_FARIA_2022],
                    elements=KeplerianElements(
                        semi_major_axis=0.029, eccentricity=0.0,
                        inclination=0.0, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=0.0, mean_anomaly_at_epoch=45.0,
                        epoch=J2000, period=5.15)),

        # Proxima c — candidate, disputed (Damasso et al. 2020).
        # Super-Earth at ~1.49 AU; not confirmed by independent groups.
        OrbitalBody(name="Proxima Centauri c", body_type="planet",
                    parent="Proxima Centauri",
                    display_name="Proxima Centauri c (candidate)",
                    status="hypothetical",
                    radius_km=13000.0, mass_kg=4.18e25, color="#FFDDAA",
                    axial_tilt_deg=None,
                    sources=[_SRC_DAMASSO_2020],
                    elements=KeplerianElements(
                        semi_major_axis=1.489, eccentricity=0.0,
                        inclination=0.0, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=0.0, mean_anomaly_at_epoch=90.0,
                        epoch=J2000, period=1928.0)),
    ]
    return StarSystem(
        name="Alpha Centauri",
        description="The Alpha Centauri triple system at true scale. A (G2V) and B (K1V) orbit "
                    "each other at ~23.4 AU (Pourbaix et al. 2002). Proxima Centauri (M5.5Ve) "
                    "is shown at its estimated ~8,700 AU orbit (Kervella et al. 2017, hypothetical). "
                    "Proxima hosts Proxima b and d (confirmed) and Proxima c (candidate); because "
                    "Proxima is itself moving, their paths are drawn as coils spanning the animated "
                    "window rather than as closed ellipses. "
                    "Each of the three stars carries its own solvent bands, centred on "
                    "that star and in the plane of its own planets: A and B have no "
                    "planets with measured angles, so their bands lie on the reference "
                    "plane rather than in the 79.2-degree binary plane, which is the "
                    "companion's orbit and not an inclination any planet of theirs has. "
                    + bands.note(_L_ALPHA_CEN_A, bodies, "Alpha Centauri A",
                                 _T_ALPHA_CEN_A),
        bodies=bodies,
        source="builtin",
        belt_zones=bands.zones_for_system(bodies),
        # Alpha Centauri A: RA 14h39m36.5s, Dec -60°50'02" (Gaia DR3). The
        # binary's inclination and node are a visual-binary solution, quoted
        # against the sky plane with the node measured from North.
        distance_from_sun_ly=4.36,
        solar_system_direction=TOWARD_EARTH,
        galactic_center_direction=galactic_centre_in_sky_frame(*_SKY_ALPHA_CEN),
        sky_frame_radec=_SKY_ALPHA_CEN[:2],
        distance_to_galactic_center_ly=26667.0,
    )


def _proxima_centauri(bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    """Proxima Centauri standalone system — focused view for exploring Proxima's planets.

    Proxima sits at the origin.  Three planets:
      - Proxima b  (confirmed, Anglada-Escudé et al. 2016)
      - Proxima d  (confirmed, Faria et al. 2022)
      - Proxima c  (candidate, Damasso et al. 2020)
    """
    bodies = [
        OrbitalBody(name="Proxima Centauri", body_type="star",
                    radius_km=107300.0, mass_kg=2.428e29,
                    luminosity_sun=_L_PROXIMA, teff_k=_T_PROXIMA,
                    color="#FF8866",
                    axial_tilt_deg=None,
                    sources=[_SRC_KERVELLA_2017,
                             ["Henry et al. 1999, ApJ 512",
                              "https://doi.org/10.1086/306793"]]),

        OrbitalBody(name="Proxima Centauri b", body_type="planet",
                    parent="Proxima Centauri",
                    radius_km=7160.0, mass_kg=7.58e24, color="#88BBFF",
                    axial_tilt_deg=None,
                    sources=[_SRC_ANGLADA_2016],
                    elements=KeplerianElements(
                        semi_major_axis=0.04856, eccentricity=0.0,
                        inclination=0.0, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=0.0, mean_anomaly_at_epoch=0.0,
                        epoch=J2000, period=11.2186)),

        OrbitalBody(name="Proxima Centauri d", body_type="planet",
                    parent="Proxima Centauri",
                    radius_km=4500.0, mass_kg=1.553e24, color="#AAFFCC",
                    axial_tilt_deg=None,
                    sources=[_SRC_FARIA_2022],
                    elements=KeplerianElements(
                        semi_major_axis=0.029, eccentricity=0.0,
                        inclination=0.0, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=0.0, mean_anomaly_at_epoch=45.0,
                        epoch=J2000, period=5.15)),

        OrbitalBody(name="Proxima Centauri c", body_type="planet",
                    parent="Proxima Centauri",
                    display_name="Proxima Centauri c (candidate)",
                    status="hypothetical",
                    radius_km=13000.0, mass_kg=4.18e25, color="#FFDDAA",
                    axial_tilt_deg=None,
                    sources=[_SRC_DAMASSO_2020],
                    elements=KeplerianElements(
                        semi_major_axis=1.489, eccentricity=0.0,
                        inclination=0.0, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=0.0, mean_anomaly_at_epoch=90.0,
                        epoch=J2000, period=1928.0)),
    ]
    return StarSystem(
        name="Proxima Centauri",
        description="Proxima Centauri (M5.5Ve), the nearest star to the Sun at 4.24 ly. "
                    "Hosts Proxima b and d (confirmed) and Proxima c (candidate super-Earth). "
                    + bands.note(_L_PROXIMA, bodies, "Proxima Centauri",
                                 _T_PROXIMA),
        bodies=bodies,
        source="builtin",
        belt_zones=bands.zones_for_system(bodies),
        # Proxima Centauri: RA 14h29m43.0s, Dec -62°40'46". Its planets have no
        # measured angles at all, so the flat drawing is read as face-on from
        # Earth -- which makes this a sky frame like the others.
        distance_from_sun_ly=4.24,
        solar_system_direction=TOWARD_EARTH,
        galactic_center_direction=galactic_centre_in_sky_frame(*_SKY_PROXIMA),
        sky_frame_radec=_SKY_PROXIMA[:2],
        distance_to_galactic_center_ly=26667.0,
    )


def _upsilon_andromedae(bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    """Upsilon Andromedae (Titawin): the star from the catalog, the orbits in 3-D.

    An F8 V star at 43.72 ly with three giant planets, one of them -- ups And d
    -- inside the conservative habitable zone.  The star is the workbook's,
    which is what the solvent bands are computed from.  The orbits are not: the
    catalog has no column for inclination, ascending node or argument of
    periapsis, and this is the system where those angles are the whole point.

    Upsilon Andromedae was the first exoplanetary system to have the relative
    inclination of two planets measured directly, and c and d turn out to be
    about 30 degrees apart.  A co-planar drawing of it is not a simplification,
    it is the one thing the system is known for, left out.  So the orbital
    elements here are configuration PRO1 of Deitrick et al. 2015 -- their
    nominal case, the lowest-chi-squared prograde solution that survived a
    100 Myr N-body integration, fitted to the radial velocities and the HST
    astrometry together.  Only 10 of their 1000 trials were robustly stable
    over that span, which is the sense in which this system is chaotic: most
    configurations consistent with the data tear themselves apart.

    Four things to know about what is drawn:

    * **The reference plane is the plane of the sky.**  Deitrick et al. measure
      inclination from the sky plane and the ascending node counterclockwise
      from North, so the view here is oriented as seen from Earth, and the
      z axis is the line of sight.  That is also why `solar_system_direction`
      is simply +z for this system rather than an ecliptic vector.
    * **Planet b's plane is not observed.**  The paper is explicit that the
      inner planet's orbital plane has not been detected; b's inclination and
      node are the values of one stable trial, not a measurement.  Its mass
      accordingly ranges over 2-9 M_Jup across their stable solutions.
    * **The masses are dynamical, not Msini.**  With an inclination they stop
      being lower bounds, and each one is the catalog's own Msini divided by
      sin i to within a few percent -- a check that the two sources describe
      the same planets.
    * **The epoch is not the paper's.**  Deitrick et al. give a mean anomaly
      per planet but no date to hang it on, so the configuration is theirs and
      the J2000 label on it is arbitrary.  Relative phases -- which is what a
      three-body geometry is about -- are preserved.

    The system's second star, ups And B, an M dwarf about 750 AU out, is drawn
    hollow on a circle at its projected separation, since it has no orbit (see
    _PA_UPS_AND_B).

    One discrepancy left standing: these orbits imply a 1.32 M_sun star through
    Kepler's third law, consistently across all three planets, where the
    workbook's stellar row says 1.27.  Nothing drawn depends on it, since every
    period is given rather than derived, and adjusting either source to agree
    with the other would be inventing a figure neither one holds.
    """
    _src = [_SRC_DEITRICK, _SRC_MCARTHUR, _SRC_OEC, _SRC_EXOARCHIVE]
    # Planet colours are the catalog's own habitable-zone palette, so a planet
    # keeps its meaning between `--source catalog` and this table.
    _HZ_INSIDE, _HZ_CLOSER = "#44BB66", "#EE7744"
    bodies = [
        OrbitalBody(name="Upsilon Andromedae", body_type="star",
                    display_name="Upsilon Andromedae (Titawin)",
                    # Radius is not in the catalog: it is the Stefan-Boltzmann
                    # figure for L = 3.569 L_sun at 6212 K, as the catalog
                    # loader derives it for any star.
                    radius_km=1.13469e6, mass_kg=2.526e30,
                    luminosity_sun=_L_UPS_AND, teff_k=_T_UPS_AND,
                    color="#FFFFEE",
                    axial_tilt_deg=None, sources=_src),

        # Deitrick et al. 2015, Table 3, configuration PRO1.  Masses are
        # 8.02 / 8.69 / 10.05 M_Jup at 1.898e27 kg each.
        OrbitalBody(name="Upsilon Andromedae b", body_type="planet",
                    parent="Upsilon Andromedae", display_name="ups And b",
                    mass_kg=1.5222e28, color=_HZ_CLOSER,
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.059496, eccentricity=0.003547,
                        inclination=4.97, longitude_of_ascending_node=17.47,
                        argument_of_periapsis=48.39,
                        mean_anomaly_at_epoch=129.43,
                        epoch=J2000, period=4.61694)),

        OrbitalBody(name="Upsilon Andromedae c", body_type="planet",
                    parent="Upsilon Andromedae", display_name="ups And c",
                    mass_kg=1.6494e28, color=_HZ_CLOSER,
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.830939, eccentricity=0.254632,
                        inclination=12.62, longitude_of_ascending_node=259.40,
                        argument_of_periapsis=245.89,
                        mean_anomaly_at_epoch=153.03,
                        epoch=J2000, period=240.92)),

        OrbitalBody(name="Upsilon Andromedae d", body_type="planet",
                    parent="Upsilon Andromedae", display_name="ups And d",
                    mass_kg=1.9075e28, color=_HZ_INSIDE,
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=2.532293, eccentricity=0.274677,
                        inclination=24.55, longitude_of_ascending_node=10.22,
                        argument_of_periapsis=253.71,
                        mean_anomaly_at_epoch=83.16,
                        epoch=J2000, period=1281.08)),

        # ups And B -- an M4.5 V common-proper-motion companion (Lowrance et
        # al. 2002), mass 0.171 M_sun and Teff 3195 K from the catalog
        # workbook's row (Mugrauer 2019), its luminosity TIC v8.2's.  No orbit
        # is published, so it is hypothetical; where it is drawn is set out at
        # _PA_UPS_AND_B.  Its luminosity gives it a band stack of its own.  The period is Kepler's third
        # law on the two masses here, 1.27 + 0.171 M_sun: 17,100 years.
        OrbitalBody(name="Upsilon Andromedae B", body_type="star",
                    parent="Upsilon Andromedae", display_name="ups And B",
                    status="hypothetical",
                    mass_kg=3.4011e29, luminosity_sun=_L_UPS_AND_B, teff_k=3195.0,
                    color="#FFAA77", axial_tilt_deg=None,
                    sources=[_SRC_LOWRANCE, _SRC_MUGRAUER_2019, _SRC_TIC_UPS_AND_B],
                    elements=KeplerianElements(
                        semi_major_axis=_A_UPS_AND_B, eccentricity=0.0,
                        inclination=0.0, longitude_of_ascending_node=0.0,
                        argument_of_periapsis=0.0,
                        mean_anomaly_at_epoch=_PA_UPS_AND_B,
                        epoch=_J2016, period=6.24498e6)),
    ]
    return StarSystem(
        name="Upsilon Andromedae",
        description="Upsilon Andromedae (Titawin), an F8 V star at 43.72 ly with three "
                    "giant planets, and the first system whose planets had a mutual "
                    "inclination measured directly: c and d orbit about 30 degrees "
                    "apart. Orbits are configuration PRO1 of Deitrick et al. 2015, the "
                    "nominal fit to the radial velocities and HST astrometry that "
                    "survived a 100 Myr integration — only 10 of their 1000 trials did. "
                    "Angles are measured from the plane of the sky, so the scene is "
                    "oriented as seen from Earth. Planet b's orbital plane has never "
                    "been detected; its inclination and node here are one stable trial, "
                    "not a measurement. The paper gives no epoch for its mean "
                    "anomalies, so the configuration is real but the date is arbitrary. "
                    "ups And d sits inside the conservative habitable zone. "
                    "ups And B, an M4.5 V companion 750 AU away in projection, has no "
                    "measured orbit: it is drawn hollow on a circle in the sky plane at "
                    "that distance, standing where Gaia saw it in 2016. "
                    + bands.note(_L_UPS_AND, bodies, "Upsilon Andromedae",
                                 _T_UPS_AND),
        bodies=bodies,
        source="builtin",
        belt_zones=bands.zones_for_system(bodies),
        distance_from_sun_ly=43.72,
        # The reference plane is the sky plane, so the line of sight is the
        # z axis by construction. With +x North and +y East, North x East
        # points back along the line of sight, toward us.
        solar_system_direction=TOWARD_EARTH,
        galactic_center_direction=galactic_centre_in_sky_frame(*_SKY_UPS_AND),
        sky_frame_radec=_SKY_UPS_AND[:2],
        distance_to_galactic_center_ly=26697.4,
    )


# 55 Cancri's angles, all against the sky plane (x North, y East, node
# counterclockwise from North).  See _55_cancri() for which are measured.
#
# A's plane.  d: I = 93.9 +6.9/-6.7, node 124 +28/-30 (Xiao et al. 2026).
# e transits at 83.59, which a transit cannot tell from 180 - 83.59 = 96.41;
# 96.41 is the side d is on, 2.5 deg from it, so A's other planets take it
# and d's node.
_I_55CNC_A    = 96.41
_I_55CNC_D    = 93.9
_NODE_55CNC_A = 124.0
# B's orbit about A.  I, e and a are Xiao et al.'s lofti_gaia medians
# (67.7 +7.0/-24, 0.55 +0.32/-0.37, 1259 +826/-431 AU).  Their median node and
# periastron (177, 183) do not together pass through where B is, so these are
# the orbit that does -- within 4.9 AU of B's Gaia DR3 position relative to A
# (84.82 arcsec at PA 128.1 deg, epoch 2016.0) -- closest to the medians in
# units of their own errors: node 0.35 sigma, periastron 0.32 sigma away.
# The J2000 mean anomaly is the one that puts B there in 2016.0.
_I_55CNC_B     = 67.7
_NODE_55CNC_B  = 162.5
_OMEGA_55CNC_B = 140.0
_M_55CNC_B     = 122.914


def _55_cancri(bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    """55 Cancri: five planets spanning 0.015 to 6 AU, and one measured angle.

    A G8 V star at 41.05 ly with five confirmed planets, and a distant M4.5 V
    companion.  The star is the workbook's, so the solvent bands here and the
    ones ``--source catalog`` computes are the same bands.  The orbits are
    Bourrier et al. 2018, who re-fitted two decades of radial velocities with
    the star's 3822-day magnetic cycle modelled as a sixth Keplerian -- a
    column in their solution table that they did not count as a planet, which
    is the trap this system sets for anyone reading the table quickly.

    Moutou et al. 2025 reopen that signal.  Adding SPIRou near-infrared
    velocities, they find it at 3827 days with no colour dependence, a period
    drifting away from the cycle's, and more amplitude than activity predicts,
    and propose it may be mostly a sixth planet: **55 Cnc g**, drawn here as a
    hypothetical candidate.  If the whole signal is planetary it is at least
    0.9 M_Jup on an e = 0.35 orbit that crosses d's; a 1900-day solution is not
    excluded.  Its axis is the workbook's, which is the source of truth for it.

    What the geometry rests on, and what it does not:

    * **Two planets' tilts are measured, and they agree.**  e transits, at
      83.59 deg to the sky (Bourrier et al. 2018) -- or 96.41, since a transit
      cannot tell the two apart.  d's is measured from Hipparcos-Gaia
      astrometry: 93.9 +6.9/-6.7 deg, with its ascending node at 124 +28/-30
      deg (Xiao et al. 2026), and that paper finds the two planes at least
      3.9 deg apart, i.e. nearly co-planar.  So e is drawn at 96.41, the side
      d is on, and b, c, f and g are drawn in e's plane with d's node.  Their
      planes are an assumption; e's tilt and d's tilt and node are not.
    * **d's angles and d's orbit come from different fits.**  The period,
      eccentricity and periastron are Bourrier's; Xiao et al.'s own fit has
      P = 5084 d.  Only the two angles are taken from them.
    * **The masses stay as minimum masses.**  Only e has a true mass, 7.99
      M_Earth.  The rest are M sin i, carried here as the paper prints them;
      co-planar with e they would be low by 1/sin 83.59 = 1.006, well inside
      their error bars.  d's true mass from Xiao et al. is 3.23 M_Jup.
    * **The phases are real.**  Mean anomalies are computed from the paper's
      own conjunction times and arguments of periastron, propagated to J2000,
      so the relative positions of the five planets are the measured ones
      rather than a pleasing arrangement.

    The workbook credits this system with seven planets, and the other two are
    55 Cnc B b and c, around the companion.  The workbook has their masses but
    records period, axis and eccentricity as unsourced, so the orbits come from
    the discovery paper, Moutou et al. 2026: 6.80 and 33.75 days, 0.044 and
    0.13 AU, both fitted circular.  Their masses match the workbook's 3.5 and
    5.3 M_Earth, which is the check that the two are the same planets.

    **B's orbit about A is measured, loosely; B's planets' plane is not.**
    Xiao et al. 2026 fit the pair's Gaia motion with lofti_gaia: a = 1259 AU,
    e = 0.55, I = 67.7 deg, each with errors of tens of percent.  Their
    median node and periastron do not together pass through where B is, so
    the orbit drawn is the one through B's Gaia position nearest those
    medians (see _NODE_55CNC_B).  B's two planets are radial-velocity
    detections with no inclination, and B's spin cannot supply one -- its
    quoted v sin i of 1.29 km/s is ten times what a 92-day rotation allows,
    a resolution floor, not a rotation.  They are drawn in B's orbit plane,
    the one measured plane that belongs to B.  That is an ASSUMPTION.  It
    puts them 47 deg from A's planets; Xiao et al.'s own bound on B's orbit
    against A's planets is at least 23.7 deg, and the 3-D angle is loose
    because both nodes are.

    A note on scale: 55 Cnc B sits 1068 AU away in projection, against an inner
    system that ends at 6 AU.  The whole planetary system is a dot near the
    origin at default zoom, exactly as the A-B binary is in ``alpha-centauri``.
    """
    _src = [_SRC_BOURRIER, _SRC_VON_BRAUN, _SRC_EXO_55CNC]
    # The catalog's own habitable-zone palette, so a planet keeps its meaning
    # between `--source catalog` and this table.  See catalog_loader.hz_color.
    _HZ_INSIDE, _HZ_CLOSER, _HZ_FARTHER = "#44BB66", "#EE7744", "#5588CC"
    bodies = [
        OrbitalBody(name="55 Cancri A", body_type="star",
                    display_name="55 Cancri A (Copernicus)",
                    # Not in the catalog: the Stefan-Boltzmann figure for
                    # L = 0.5733 L_sun at 5172 K, which lands on von Braun's
                    # interferometric 0.943 R_sun to three decimals.
                    radius_km=656045.0, mass_kg=1.7997e30,
                    luminosity_sun=_L_55_CNC_A, teff_k=_T_55_CNC_A,
                    color="#FFE9A8",
                    axial_tilt_deg=None, sources=_src),

        # Bourrier et al. 2018, Table 3.  Mean anomalies derived from their
        # TC and omega, propagated to J2000.  Conjunction is where
        # omega + nu = 90 deg, whatever the node or the side of 90 deg the
        # inclination is on, so these phases hold in the rotated plane.
        OrbitalBody(name="55 Cancri e", body_type="planet",
                    parent="55 Cancri A", display_name="55 Cnc e (Janssen)",
                    radius_km=12191.0, mass_kg=4.7718e25, color=_HZ_CLOSER,
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.01544, eccentricity=0.05,
                        inclination=_I_55CNC_A,
                        longitude_of_ascending_node=_NODE_55CNC_A,
                        argument_of_periapsis=86.0,
                        mean_anomaly_at_epoch=258.046,
                        epoch=J2000, period=0.73654737)),

        OrbitalBody(name="55 Cancri b", body_type="planet",
                    parent="55 Cancri A", display_name="55 Cnc b (Galileo)",
                    mass_kg=1.52533e27, color=_HZ_CLOSER,
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.1134, eccentricity=0.00,
                        inclination=_I_55CNC_A,
                        longitude_of_ascending_node=_NODE_55CNC_A,
                        argument_of_periapsis=-21.5,
                        mean_anomaly_at_epoch=28.063,
                        epoch=J2000, period=14.6516)),

        OrbitalBody(name="55 Cancri c", body_type="planet",
                    parent="55 Cancri A", display_name="55 Cnc c (Brahe)",
                    mass_kg=3.05789e26, color=_HZ_CLOSER,
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.2373, eccentricity=0.03,
                        inclination=_I_55CNC_A,
                        longitude_of_ascending_node=_NODE_55CNC_A,
                        argument_of_periapsis=2.4,
                        mean_anomaly_at_epoch=65.062,
                        epoch=J2000, period=44.3989)),

        OrbitalBody(name="55 Cancri f", body_type="planet",
                    parent="55 Cancri A", display_name="55 Cnc f (Harriot)",
                    mass_kg=2.85289e26, color=_HZ_INSIDE,
                    axial_tilt_deg=None, sources=_src,
                    elements=KeplerianElements(
                        semi_major_axis=0.7708, eccentricity=0.08,
                        inclination=_I_55CNC_A,
                        longitude_of_ascending_node=_NODE_55CNC_A,
                        argument_of_periapsis=-97.6,
                        mean_anomaly_at_epoch=339.244,
                        epoch=J2000, period=259.88)),

        OrbitalBody(name="55 Cancri d", body_type="planet",
                    parent="55 Cancri A", display_name="55 Cnc d (Lipperhey)",
                    mass_kg=5.92216e27, color=_HZ_FARTHER,
                    axial_tilt_deg=None, sources=_src + [_SRC_XIAO],
                    elements=KeplerianElements(
                        semi_major_axis=5.957, eccentricity=0.13,
                        inclination=_I_55CNC_D,
                        longitude_of_ascending_node=_NODE_55CNC_A,
                        argument_of_periapsis=-69.1,
                        mean_anomaly_at_epoch=193.153,
                        epoch=J2000, period=5574.2)),

        # 55 Cnc g -- UNCONFIRMED.  Moutou et al. 2025, Table 8, the sixth
        # Keplerian 'k6': P = 3827.1 d, e = 0.35, omega = -1.66 rad,
        # Tconj = 2450841.5.  Its period sits on the star's magnetic cycle,
        # so part or all of it may be activity; 0.9 M_Jup is the paper's
        # minimum mass IF the whole signal is planetary.  a = 4.812 AU is the
        # workbook's (Unconfirmed tab), Kepler III on the paper's 1.015 M_sun
        # star -- not the 0.905 carried above, so it sits 4% wider than this
        # table's star alone would put it.  Mean anomaly from Tconj and omega,
        # propagated to J2000, as for the five above.
        OrbitalBody(name="55 Cancri g", body_type="planet",
                    parent="55 Cancri A", display_name="55 Cnc g (candidate)",
                    status="hypothetical",
                    mass_kg=1.7083e27, color=_HZ_FARTHER,
                    axial_tilt_deg=None, sources=[_SRC_MOUTOU_G],
                    elements=KeplerianElements(
                        semi_major_axis=4.812, eccentricity=0.35,
                        inclination=_I_55CNC_A,
                        longitude_of_ascending_node=_NODE_55CNC_A,
                        argument_of_periapsis=-95.11,
                        mean_anomaly_at_epoch=256.105,
                        epoch=J2000, period=3827.1)),

        # 55 Cnc B -- an M4.5 V common-proper-motion companion 84.8 arcsec from
        # A, 1068 AU in projection at 12.59 pc.  Its orbit is the lofti_gaia
        # fit of Xiao et al. 2026, loosely constrained (see _NODE_55CNC_B),
        # so it stays marked hypothetical.  The period is Kepler's third law
        # on the two masses here, 0.905 + 0.20 M_sun: 42,500 years.  Its
        # luminosity is the workbook's, so it carries its own band stack.
        OrbitalBody(name="55 Cancri B", body_type="star",
                    parent="55 Cancri A",
                    display_name="55 Cancri B (orbit poorly constrained)",
                    status="hypothetical",
                    radius_km=167000.0, mass_kg=3.977e29,
                    luminosity_sun=_L_55_CNC_B, teff_k=_T_55_CNC_B,
                    color="#FFAA77",
                    axial_tilt_deg=None,
                    sources=[_SRC_XIAO, _SRC_MUGRAUER, _SRC_EXO_55CNC],
                    elements=KeplerianElements(
                        semi_major_axis=1259.0, eccentricity=0.55,
                        inclination=_I_55CNC_B,
                        longitude_of_ascending_node=_NODE_55CNC_B,
                        argument_of_periapsis=_OMEGA_55CNC_B,
                        mean_anomaly_at_epoch=_M_55CNC_B,
                        epoch=J2000, period=1.5522e7)),

        # Moutou et al. 2026, Table 4.  Both are radial-velocity detections
        # with e fixed at 0 and no inclination.  ASSUMPTION: they are drawn in
        # B's orbit plane, the one measured plane that belongs to B.  omega =
        # 90 is the circular-orbit convention that puts conjunction at M = 0,
        # for any inclination and node, so each epoch is the paper's own Tc
        # and nothing is propagated here.
        # The axes are the paper's, for its 0.26 M_sun star; B above carries
        # the workbook's 0.20, and both are left as published.
        OrbitalBody(name="55 Cancri B b", body_type="planet",
                    parent="55 Cancri B", display_name="55 Cnc B b",
                    mass_kg=2.0903e25, color=_HZ_CLOSER,
                    axial_tilt_deg=None, sources=[_SRC_MOUTOU],
                    elements=KeplerianElements(
                        semi_major_axis=0.044, eccentricity=0.0,
                        inclination=_I_55CNC_B,
                        longitude_of_ascending_node=_NODE_55CNC_B,
                        argument_of_periapsis=90.0,
                        mean_anomaly_at_epoch=0.0,
                        epoch=2455495.7, period=6.7994)),

        # The paper puts B's habitable zone at 0.055-0.14 AU and c near its
        # outer edge, hence green.
        OrbitalBody(name="55 Cancri B c", body_type="planet",
                    parent="55 Cancri B", display_name="55 Cnc B c",
                    mass_kg=3.1653e25, color=_HZ_INSIDE,
                    axial_tilt_deg=None, sources=[_SRC_MOUTOU],
                    elements=KeplerianElements(
                        semi_major_axis=0.13, eccentricity=0.0,
                        inclination=_I_55CNC_B,
                        longitude_of_ascending_node=_NODE_55CNC_B,
                        argument_of_periapsis=90.0,
                        mean_anomaly_at_epoch=0.0,
                        epoch=2455491.8, period=33.747)),
    ]
    return StarSystem(
        name="55 Cancri",
        description="55 Cancri (Copernicus), a G8 V star at 41.05 ly with five confirmed "
                    "planets spanning 0.015 to 5.96 AU — from 55 Cnc e, a super-Earth on "
                    "a 17.7-hour orbit, out to 55 Cnc d, a gas giant beyond the habitable "
                    "zone. Orbits are Bourrier et al. 2018, who modelled the star's "
                    "3822-day magnetic cycle as a sixth Keplerian. Moutou et al. 2025 "
                    "argue that signal, at 3827 days, may be mostly a sixth planet: the "
                    "UNCONFIRMED candidate 55 Cnc g, drawn dashed at 4.81 AU on an "
                    "e = 0.35 orbit that crosses d's, at least 0.9 Jupiter masses if the "
                    "whole signal is planetary. Two of A's planets have measured tilts: "
                    "55 Cnc e transits (83.59 degrees to the sky, drawn as the equivalent "
                    "96.41), and 55 Cnc d's orbit is measured from Hipparcos-Gaia "
                    "astrometry at 93.9 degrees with its node at 124 degrees (Xiao et al. "
                    "2026), nearly co-planar with e. The others are drawn in that plane by "
                    "assumption, and their masses are minimum masses. 55 Cnc f orbits "
                    "inside the conservative habitable zone. The M4.5 V companion 55 Cnc B "
                    "lies 1068 AU away in projection, so the planets are a dot near the "
                    "origin at full zoom; its orbit about A is a loosely constrained Gaia "
                    "fit (a = 1259 AU, e = 0.55, 67.7 degrees to the sky), drawn through "
                    "B's measured position. B has two planets of its own, 55 Cnc B b and c "
                    "(Moutou et al. 2026), on circular 6.80- and 33.75-day orbits. Their "
                    "tilt is not measured: they are drawn in B's orbit plane, an "
                    "assumption, which puts them 47 degrees from A's planets; their masses "
                    "are minimum masses. "
                    + bands.note(_L_55_CNC_A, bodies, "55 Cancri A",
                                 _T_55_CNC_A),
        bodies=bodies,
        source="builtin",
        belt_zones=bands.zones_for_system(bodies),
        distance_from_sun_ly=41.05,
        # 55 Cnc e's inclination is a transit measurement, quoted against the
        # plane of the sky, so the reference plane is the sky plane and the
        # line of sight is the z axis.
        solar_system_direction=TOWARD_EARTH,
        galactic_center_direction=galactic_centre_in_sky_frame(*_SKY_55_CNC),
        sky_frame_radec=_SKY_55_CNC[:2],
        distance_to_galactic_center_ly=26673.0,
    )

# Castor, row for row as the "Planetless 4+ Stars" tab holds it (workbook
# hy-brasil-20261007-1547).  Every number here is a cell of that tab, keyed by
# the tab's own 'Star (component)'; tests/test_castor.py reads the snapshot in
# data/ and fails on any that has drifted.  To change one, change the sheet.
# The brown dwarf Cc is a planet since 7 Oct 2026 (docs/hybrasil-instructions.md
# section 6): its row is on the Planets tab, and the subsystem C it made with
# Cab is gone -- Cab carries C's orbit round AB.
_CASTOR_ROWS = [
    NodeRow("alf Gem Aa", "star", mass_sun=2.37, luminosity_sun=33.1, teff_k=9420),
    NodeRow("alf Gem AB", "subsystem", mass_sun=4.93,
            barycentre_from="alf Gem A", barycentre_offset_au=44.701456),
    NodeRow("alf Gem A", "subsystem", mass_sun=2.76,
            barycentre_from="alf Gem Aa", barycentre_offset_au=0.017034),
    NodeRow("alf Gem Ab", "star", mass_sun=0.39, luminosity_sun=0.0229, teff_k=3470,
            separation_from="alf Gem Aa", a_au=0.12055, e=0.488, period_d=9.2127496,
            inclination_deg=35.0, node_deg=95.1, omega_deg=264.97, periastron_jd=2455817.7868,
            omega_refers_to="primary (Aa)"),
    NodeRow("alf Gem B", "subsystem", mass_sun=2.18,
            separation_from="alf Gem A", a_au=101.29596, e=0.338, period_d=167686.275,
            inclination_deg=115.11, node_deg=41.3, omega_deg=251.8, periastron_jd=2436785.0961,
            omega_refers_to="secondary (B relative to A)",
            barycentre_from="alf Gem Ba", barycentre_offset_au=0.009287),
    NodeRow("alf Gem Ba", "star", mass_sun=1.79, luminosity_sun=11.5, teff_k=8240),
    NodeRow("alf Gem Bb", "star", mass_sun=0.39, luminosity_sun=0.0229, teff_k=3470,
            separation_from="alf Gem Ba", a_au=0.05191, e=0.0, period_d=2.92835083,
            inclination_deg=110.5, node_deg=106.47, omega_deg=0.0, periastron_jd=2456705.494,
            omega_refers_to="primary (Ba)"),
    NodeRow("alf Gem Cab", "subsystem", mass_sun=1.2,
            separation_from="alf Gem AB", a_au=1075.94937, e=0.3, period_d=4917360.75,
            inclination_deg=34.0, node_deg=343.0, omega_deg=290.0, periastron_jd=3403365.7034,
            omega_refers_to="secondary (Cab relative to AB)",
            barycentre_from="alf Gem Ca", barycentre_offset_au=0.009065),
    NodeRow("alf Gem Ca", "star", mass_sun=0.6, luminosity_sun=0.0733, teff_k=3820),
    NodeRow("alf Gem Cb", "star", mass_sun=0.6, luminosity_sun=0.0733, teff_k=3820,
            separation_from="alf Gem Ca", a_au=0.01813, e=0.0, period_d=0.814282212,
            inclination_deg=86.29, node_deg=0.0, omega_deg=90.0, periastron_jd=2449345.112327,
            omega_refers_to="primary (Ca)"),
]
# Castor Cc, the candidate brown dwarf round YY Gem: a planet.  a, e, P and the
# mass are cells of its Planets row; i, node, omega and T are in that row's
# flags text, the Planets tab having no columns for them.
_CASTOR_CC = NodeRow("alf Gem Cc", "star", mass_sun=0.05,
                     separation_from="alf Gem Cab", a_au=15.40084, e=0.11, period_d=19785.0,
                     inclination_deg=86.29, node_deg=0.0, omega_deg=37.6, periastron_jd=2454805.0,
                     omega_refers_to="primary (Cab)")
# The host row's position and distance: 'RA (deg, ICRS)', 'Dec (deg, ICRS)',
# 'Distance (ly)' (the Torres 2022 orbital parallax, 66.36 mas).
_SKY_CASTOR = (113.650002, 31.888639, 49.15)

_SRC_TORRES_2022 = ["Torres et al. 2022, ApJ 941, 8 (Castor A and B)",
                    "https://arxiv.org/abs/2210.16322"]
_SRC_TORRES_RIBAS_2002 = ["Torres & Ribas 2002, ApJ 567, 1140 (YY Gem)",
                          "https://arxiv.org/abs/astro-ph/0111167"]
_SRC_WOLF_2018 = ["Wolf et al. 2018, A&A 620, A72 (Castor Cc)",
                  "https://doi.org/10.1051/0004-6361/201833620"]
_SRC_MSC = ["Tokovinin 2018, Multiple Star Catalog (VizieR J/ApJS/235/6)",
            "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/ApJS/235/6"]
_SRC_ORB6 = ["Matvienko, Kiyaeva & Orlov 2015, Astron. Lett. 41, 43 (via ORB6)",
             "https://doi.org/10.1134/S1063773715010041"]


def _castor(bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    """Castor (alpha Geminorum): six stars in three pairs, and a brown dwarf.

    ((Aa,Ab),(Ba,Bb)),(Ca,Cb), with the brown dwarf Cc round (Ca,Cb).  Castor A and B are each an A-type star with
    an unseen M-dwarf companion on a days-long orbit, and the two pairs orbit
    each other every 459 years (Torres et al. 2022).  Castor C is YY Geminorum,
    two M dwarfs eclipsing every 0.81 days, with a candidate brown dwarf
    circling them every 54 years (Wolf et al. 2018) -- drawn as a planet, which
    is what this model counts a brown dwarf as; C orbits A+B ~1076 AU out, on an
    orbit so poorly covered its period is uncertain by thousands of years.

    The first featured system built from the catalog workbook's "Planetless 4+
    Stars" tab: every number is a cell of it (`_CASTOR_ROWS`).  An outer orbit
    here runs between *barycentres*, which the tab places and
    `data/hierarchy.py` turns into massless barycentre bodies.
    """
    looks = {
        "alf Gem Aa": Look(color="#CAD8FF", sources=[_SRC_TORRES_2022, _SRC_TORRES_RIBAS_2002]),
        "alf Gem Ab": Look(color="#FFB27A", sources=[_SRC_TORRES_2022]),
        "alf Gem Ba": Look(color="#DCE4FF", sources=[_SRC_TORRES_2022, _SRC_TORRES_RIBAS_2002]),
        "alf Gem Bb": Look(color="#FFAA70", sources=[_SRC_TORRES_2022]),
        "alf Gem Ca": Look(color="#FFA060", sources=[_SRC_TORRES_RIBAS_2002]),
        "alf Gem Cb": Look(color="#FF9858", sources=[_SRC_TORRES_RIBAS_2002]),
        "alf Gem A": Look(display_name="Castor A barycentre (Aa + Ab)", sources=[_SRC_MSC]),
        "alf Gem B": Look(display_name="Castor B barycentre (Ba + Bb)", sources=[_SRC_TORRES_2022]),
        "alf Gem AB": Look(display_name="Castor AB barycentre", sources=[_SRC_MSC]),
        # Grade 5, "indeterminate": one of a family of fits, none preferred.
        "alf Gem Cab": Look(display_name="Castor C barycentre (Ca + Cb; orbit indeterminate)",
                            status="hypothetical", sources=[_SRC_ORB6, _SRC_MSC]),
    }
    bodies = hierarchy_bodies(_CASTOR_ROWS, origin="alf Gem Aa", looks=looks,
                              name_of=lambda n: n.replace("alf Gem ", "Castor "))
    # A candidate, from eclipse timing alone, with a minimum mass: a brown
    # dwarf, so a planet, round YY Gem's barycentre.
    bodies.append(OrbitalBody(
        name="Castor Cc", body_type="planet", parent="Castor Cab", elements=relative_orbit(_CASTOR_CC),
        mass_kg=_CASTOR_CC.mass_sun * M_SUN_KG, color="#A0522D", status="hypothetical",
        display_name="Castor Cc (candidate brown dwarf)", sources=[_SRC_WOLF_2018]))
    return StarSystem(
        name="Castor",
        description="Castor (alpha Geminorum) at true scale: six stars and a candidate brown "
                    "dwarf, 49 light years away, as three pairs and a planet. Castor A (A1 V, with "
                    "an M dwarf on a 9.2-day orbit) and Castor B (A2 Vm, with an M dwarf on a "
                    "2.9-day orbit) orbit each other every 459 years, 101 AU apart (Torres et "
                    "al. 2022). Castor C is YY Geminorum, two M dwarfs eclipsing every 0.81 "
                    "days, with a candidate brown dwarf every 54 years, drawn as a planet "
                    "since this model counts a brown dwarf as one; YY Gem orbits A+B about "
                    "1,076 AU out on an indeterminate orbit (dashed), one of a family of fits "
                    "with periods of 13,000 to 19,000 years. B's and C's orbits are between "
                    "barycentres, shown as small hollow rings. The node of YY Gem, and the tilt "
                    "and node of the brown dwarf's orbit, are not measured: all are assumed. "
                    "Every value comes from the workbook's Planetless 4+ Stars tab, and the brown "
                    "dwarf's from its Planets tab. Each star "
                    "carries its own solvent bands; a band round a star with a close companion "
                    "is drawn as though the companion were not there. "
                    + bands.note(33.1, bodies, "Castor Aa", 9420),
        bodies=bodies,
        source="builtin",
        belt_zones=bands.zones_for_system(bodies),
        # Every orbit's angles are from astrometry or eclipses, quoted against
        # the plane of the sky, so the reference plane is the sky plane.
        distance_from_sun_ly=_SKY_CASTOR[2],
        solar_system_direction=TOWARD_EARTH,
        galactic_center_direction=galactic_centre_in_sky_frame(*_SKY_CASTOR),
        sky_frame_radec=_SKY_CASTOR[:2],
        distance_to_galactic_center_ly=galactic_centre_distance_ly(*_SKY_CASTOR),
    )

# Keyed by (system, solvent choice): the same system drawn with a different
# set of bands is a different figure, so it cannot share a cache entry.
_REGISTRY: dict[tuple, StarSystem] = {}

BUILTIN_NAMES = ["solar", "trappist-1", "alpha-centauri", "proxima-centauri",
                 "upsilon-andromedae", "55-cancri", "castor"]

# The catalog systems each featured system already covers, and the other names
# people know it by.  The web app's system search lists a featured system
# once: its catalog systems are folded into it, so "55 Cnc A" or "Titawin"
# opens the literature-built featured system, not a thinner catalog
# duplicate.  A catalog system is a whole system -- every star on the
# multi-stars tab -- so the catalog's alf Cen A is A, B and Proxima together,
# which is what the featured Alpha Centauri draws.  Proxima Centauri covers no
# catalog system of its own, but keeps its names as aliases.
FEATURED_CATALOG_HOSTS: dict[str, tuple[str, ...]] = {
    "solar":              ("Sun",),
    "trappist-1":         ("TRAPPIST-1",),
    "alpha-centauri":     ("alf Cen A",),
    "proxima-centauri":   (),
    "upsilon-andromedae": ("ups And",),
    "55-cancri":          ("55 Cnc A",),
    # Castor is on the Planetless 4+ Stars tab, not the catalog's; the web
    # app's Planetless Star list (planetless_loader) folds its row in here.
    "castor":             ("alf Gem",),
}
FEATURED_ALIASES: dict[str, tuple[str, ...]] = {
    "solar":              ("Sun", "Sol"),
    "trappist-1":         (),
    "alpha-centauri":     ("alf Cen A", "alf Cen B", "Rigil Kentaurus", "Toliman"),
    "proxima-centauri":   ("Proxima Cen", "Proxima", "alf Cen C"),
    "upsilon-andromedae": ("ups And", "Titawin"),
    "55-cancri":          ("55 Cnc", "rho1 Cancri", "Copernicus"),
    "castor":             ("alf Gem", "alpha Geminorum", "Castor", "YY Gem", "GJ 278"),
}
# A featured system's label on its button and in the system dropdown, where
# that differs from its name.  Titles and the Plotly switcher keep the name.
FEATURED_LABELS: dict[str, str] = {}
# Which System Type the dropdown lists a featured system under; anything not
# here is "planetary".  Featured views are "motion" (views.system_kind).
FEATURED_KINDS: dict[str, str] = {}

# A catalog system's id in the viewer and the web app: the prefix + its
# `System / Host`.
CATALOG_PREFIX = "catalog:"


def system_id_for_host(host: str) -> str:
    """The id that opens the system a catalog host belongs to.

    The featured system that covers it or goes by its name, as the web app's
    search folds them, else ``catalog:<host>``.  Nearby Stellar Motion's "Go to
    system" button uses it, so a click on the Sun opens the Solar System and
    one on alf Cen A the featured Alpha Centauri.
    """
    for table in (FEATURED_CATALOG_HOSTS, FEATURED_ALIASES):
        for key, names in table.items():
            if host in names:
                return key
    return CATALOG_PREFIX + host

_BUILDERS = {
    "solar":              ("solar",              _solar_system),
    "trappist-1":         ("trappist-1",         _trappist1),
    "trappist1":          ("trappist-1",         _trappist1),
    "alpha-centauri":     ("alpha-centauri",     _alpha_centauri),
    "alphacentauri":      ("alpha-centauri",     _alpha_centauri),
    "proxima-centauri":   ("proxima-centauri",   _proxima_centauri),
    "proximacentauri":    ("proxima-centauri",   _proxima_centauri),
    "proxima":            ("proxima-centauri",   _proxima_centauri),
    "upsilon-andromedae": ("upsilon-andromedae", _upsilon_andromedae),
    "upsilonandromedae":  ("upsilon-andromedae", _upsilon_andromedae),
    "upsilon-and":        ("upsilon-andromedae", _upsilon_andromedae),
    "ups-and":            ("upsilon-andromedae", _upsilon_andromedae),
    "upsand":             ("upsilon-andromedae", _upsilon_andromedae),
    "titawin":            ("upsilon-andromedae", _upsilon_andromedae),
    "55-cancri":          ("55-cancri",          _55_cancri),
    "55cancri":           ("55-cancri",          _55_cancri),
    "55-cnc":             ("55-cancri",          _55_cancri),
    "55cnc":              ("55-cancri",          _55_cancri),
    "rho1-cancri":        ("55-cancri",          _55_cancri),
    "copernicus":         ("55-cancri",          _55_cancri),
    "castor":             ("castor",             _castor),
    "alpha-geminorum":    ("castor",             _castor),
    "alf-gem":            ("castor",             _castor),
    "alfgem":             ("castor",             _castor),
}


def canonical_builtin_name(name: str) -> str:
    """Map any accepted spelling of a built-in system to its canonical key.

    `--system proxima` and `--system proxima-centauri` are the same system, but
    only the canonical key appears in `BUILTIN_NAMES`, which is what the
    multi-system switcher is built from.  Anything that uses the user's raw
    string as a dict key has to canonicalise it first or it will look up a key
    that is not there.  Unknown names are returned unchanged, so the caller
    still raises its own error rather than this one swallowing it.
    """
    entry = _BUILDERS.get(name.lower().strip())
    return entry[0] if entry else name


def get_builtin_system(name: str,
                       bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    """Return a built-in system by name. Names are case-insensitive."""
    entry = _BUILDERS.get(name.lower().strip())
    if entry is None:
        raise ValueError(
            f"Unknown built-in system '{name}'. "
            f"Available: {BUILTIN_NAMES}"
        )
    key, build = entry
    cached = (key, bands.cache_key)
    if cached not in _REGISTRY:
        _REGISTRY[cached] = build(bands)
    return _REGISTRY[cached]
