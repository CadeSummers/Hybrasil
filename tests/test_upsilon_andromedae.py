# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the Upsilon Andromedae built-in system.

The system is assembled from two sources, and these check both seams.

The **star** is the project catalog workbook's, and the solvent bands follow
from its luminosity alone -- so the band figures are checked against the
workbook's own ups And row. A wrong luminosity moves every one of them.

The **orbits** are configuration PRO1 of Deitrick et al. 2015 (ApJ 798, 46),
the nominal three-planet solution fitted to radial velocities plus HST
astrometry and integrated for 100 Myr. That paper is where the angles come
from, and the angles are the point: c and d are inclined about 30 degrees to
each other, the first mutual inclination ever measured in an exoplanet system.

Two claims the paper makes about the configuration are checked here against
what this code derives independently from the elements: the c-d mutual
inclination, and the invariable plane sitting about 15 degrees from the sky.
Neither number is in the table the elements were copied from.

The workbook quotes a band per star as a single "A=0.3" pair. That pair is the
inner edge at albedo 0.3 and the outer edge at albedo 0.3, which in this code's
terms is (optimistic inner, conservative outer). `_A03` says so once rather
than at each use.
"""

import math

import pytest

from hybrasil.cli import _NATURAL_SPANS
from hybrasil.data.builtin_systems import (
    BODY_METADATA,
    BUILTIN_NAMES,
    _L_UPS_AND,
    get_builtin_system,
)
from hybrasil.mechanics.orientation import (Z_AXIS, mean_orbital_plane,
                                                 orbital_normal, plane_tilt_deg)
from hybrasil.mechanics.solvent_bands import (
    SOLVENTS,
    SolventChoice,
    solvent_band_au,
)
from hybrasil.mechanics.time_series import system_orbit_paths
from hybrasil.mechanics.units import derive_period_days

M_SUN_KG = 1.989e30
M_JUP_KG = 1.898e27

# The workbook's Msini figures, in Jupiter masses. The system no longer uses
# them -- with an inclination the masses stop being lower bounds -- but they
# are what the dynamical masses have to agree with once sin i is put back.
WORKBOOK_MSINI_MJUP = {"b": 0.68905194, "c": 1.982204211, "d": 4.131165284}


@pytest.fixture(scope="module")
def system():
    return get_builtin_system("upsilon-andromedae")


def _planet(system, letter):
    return system.get_body(f"Upsilon Andromedae {letter}")


def _A03(solvent_key, pressure_bar=1.0):
    """The workbook's per-star band pair, at albedo 0.3 on both edges.

    None where that solvent has no liquid phase at that pressure, which is
    carbon dioxide at 1 bar -- it is below its triple point there, so no orbit
    around any star puts a planet in it.
    """
    band = solvent_band_au(_L_UPS_AND, SOLVENTS[solvent_key], pressure_bar)
    return None if band is None else (band.optimistic[0], band.conservative[1])


class TestRegistration:
    def test_it_is_a_built_in_system(self):
        assert "upsilon-andromedae" in BUILTIN_NAMES

    @pytest.mark.parametrize("alias", ["upsilon-andromedae", "Upsilon-Andromedae",
                                       "ups-and", "upsand", "titawin", "UPSAND"])
    def test_the_names_a_user_would_type_all_resolve(self, alias):
        assert get_builtin_system(alias).name == "Upsilon Andromedae"

    def test_it_has_an_animation_span_that_shows_every_planet_round_once(self, system):
        # Planets only: B's 17,000-year circle is not what the animation is for.
        span = _NATURAL_SPANS["upsilon-andromedae"]
        assert span > max(b.elements.period for b in system.get_planets())

    def test_the_star_is_named_for_search_and_labelled_for_reading(self, system):
        star = system.get_body("Upsilon Andromedae")
        assert star.label() == "Upsilon Andromedae (Titawin)"
        assert [b.label() for b in system.get_planets()] == ["ups And b", "ups And c",
                                                             "ups And d"]


class TestDeitrickPRO1:
    """Table 3 of Deitrick et al. 2015, configuration PRO1, transcribed."""

    @pytest.mark.parametrize("letter,mass_mjup,period_d,a_au,ecc,inc,argp,node,ma", [
        ("b",  8.02,    4.61694, 0.059496, 0.003547,  4.97,  48.39,  17.47, 129.43),
        ("c",  8.69,  240.92,    0.830939, 0.254632, 12.62, 245.89, 259.40, 153.03),
        ("d", 10.05, 1281.08,    2.532293, 0.274677, 24.55, 253.71,  10.22,  83.16),
    ])
    def test_every_column_of_the_row(self, system, letter, mass_mjup, period_d,
                                     a_au, ecc, inc, argp, node, ma):
        body = _planet(system, letter)
        e = body.elements
        assert body.mass_kg / M_JUP_KG == pytest.approx(mass_mjup, rel=1e-3)
        assert e.period == period_d
        assert e.semi_major_axis == a_au
        assert e.eccentricity == ecc
        assert e.inclination == inc
        assert e.argument_of_periapsis == argp
        assert e.longitude_of_ascending_node == node
        assert e.mean_anomaly_at_epoch == ma

    def test_no_planet_is_left_on_the_reference_plane(self, system):
        # A zero here would mean an angle was dropped in transcription, and the
        # co-planar drawing this system was added to get away from is back.
        for body in system.get_planets():
            assert body.elements.inclination > 0
            assert body.elements.argument_of_periapsis > 0

    def test_the_paper_is_cited_on_every_planet(self, system):
        for body in system.get_planets():
            labels = " ".join(s[0] for s in body.sources)
            assert "Deitrick" in labels and "McArthur" in labels


class TestArchitecture:
    """What the elements imply, against what the paper says they imply.

    These are the tests that would catch a mistranscribed angle: the numbers
    below appear nowhere in the table the elements came from.
    """

    def _normal(self, system, letter):
        e = _planet(system, letter).elements
        return orbital_normal(e.inclination, e.longitude_of_ascending_node)

    def _between(self, system, one, two):
        a, b = self._normal(system, one), self._normal(system, two)
        dot = sum(p * q for p, q in zip(a, b))
        return math.degrees(math.acos(max(-1.0, min(1.0, dot))))

    def test_c_and_d_are_about_thirty_degrees_apart(self, system):
        # The paper's headline: 29.9 +/- 1 deg from HST astrometry, oscillating
        # between ~30 and ~40 deg over time. PRO1 is a snapshot in that range.
        assert self._between(system, "c", "d") == pytest.approx(31.2, abs=0.5)

    def test_b_lies_near_the_plane_of_the_other_two(self, system):
        # "Planet b's orbit must lie near the invariable plane of planets c
        # and d" -- so it is closer to both of them than they are to each other.
        assert self._between(system, "b", "c") < self._between(system, "c", "d")
        assert self._between(system, "b", "d") < self._between(system, "c", "d")

    def test_b_is_prograde_with_respect_to_the_others(self, system):
        # PRO1 is a prograde configuration; the paper's RETRO cases flip b.
        for other in ("c", "d"):
            assert self._between(system, "b", other) < 90.0

    def test_the_invariable_plane_matches_the_papers_own_figure(self, system):
        # Derived here by weighting each orbit's normal by its angular
        # momentum. The paper states the invariable plane is inclined ~15 deg
        # from the sky, and never gives the number in the elements table.
        plane = mean_orbital_plane(system.bodies, "Upsilon Andromedae")
        assert plane_tilt_deg(plane) == pytest.approx(15.0, abs=1.0)

    def test_the_masses_are_the_catalogs_msini_with_sin_i_put_back(self, system):
        # The two sources have to be describing the same three planets.
        for letter, msini in WORKBOOK_MSINI_MJUP.items():
            body = _planet(system, letter)
            implied = (body.mass_kg / M_JUP_KG) * math.sin(
                math.radians(body.elements.inclination))
            assert implied == pytest.approx(msini, rel=0.05)

    def test_the_masses_are_no_longer_lower_bounds(self, system):
        for letter in ("c", "d"):
            note = BODY_METADATA[f"Upsilon Andromedae {letter}"]["mass_note"]
            assert note.startswith("dynamical mass")
            assert "not Msini" in note

    def test_planet_b_is_flagged_as_an_unmeasured_orientation(self):
        note = BODY_METADATA["Upsilon Andromedae b"]
        assert "plane not detected" in note["mass_note"]
        assert "stable trial" in note["period_note"]


class TestTheStarIsStillTheCatalogs:
    def test_the_star_matches_the_workbook_row(self, system):
        star = system.get_body("Upsilon Andromedae")
        assert star.luminosity_sun == _L_UPS_AND == 3.56885103400897
        assert star.mass_kg / M_SUN_KG == pytest.approx(1.27, rel=1e-3)
        assert system.distance_from_sun_ly == 43.72

    def test_the_orbits_imply_a_heavier_star_than_the_workbook_says(self, system):
        # 1.32 M_sun from Kepler's third law, consistently across all three
        # planets, against the workbook's 1.27. Nothing drawn depends on it --
        # every period is given rather than derived -- but the disagreement is
        # real and is recorded here rather than papered over.
        for body in system.get_planets():
            a, p = body.elements.semi_major_axis, body.elements.period
            implied = (a ** 3) / ((p / 365.25) ** 2)
            assert implied == pytest.approx(1.32, abs=0.01)
        assert system.get_body("Upsilon Andromedae").mass_kg / M_SUN_KG < 1.30

    def test_the_derived_stellar_radius_agrees_with_the_literature(self, system):
        # Stefan-Boltzmann from L and Teff gives 1.63 R_sun; Takeda et al. 2007
        # measured 1.64. The catalog carries no stellar radii, so this is the
        # only check available that the derived one is sane.
        r_sun_km = 695700.0
        assert system.get_body("Upsilon Andromedae").radius_km / r_sun_km == (
            pytest.approx(1.64, abs=0.02))


class TestBandsAgainstTheWorkbookRow:
    @pytest.mark.parametrize("solvent,pressure,inner,outer", [
        ("water",          1.0,  0.8812, 1.6411),
        ("ammonia",        1.0,  2.1284, 3.2052),
        ("formamide",      1.0,  0.5963, 1.6173),   # functional, per the workbook
        ("sulfuric-acid",  1.0,  0.3727, 1.5272),   # functional
        ("sulfur",         1.0,  0.6556, 0.8127),   # functional
        ("carbon-dioxide", 50.0, 1.4819, 2.5729),
    ])
    def test_band_matches(self, solvent, pressure, inner, outer):
        got_inner, got_outer = _A03(solvent, pressure)
        assert got_inner == pytest.approx(inner, abs=0.0002)
        assert got_outer == pytest.approx(outer, abs=0.0002)

    @pytest.mark.parametrize("solvent,inner,outer", [
        ("methane", 9.8, 14.9),
        ("ethane",  3.6, 15.0),
    ])
    def test_the_rows_quoted_to_one_decimal_match_too(self, solvent, inner, outer):
        got_inner, got_outer = _A03(solvent)
        assert round(got_inner, 1) == inner
        assert round(got_outer, 1) == outer


class TestPlanetPlacement:
    """The workbook's per-planet 'Solvent band (1 bar, A=0.3)' verdicts.

    Swapping the orbits for Deitrick's moved every semi-major axis by less than
    0.1%, so these verdicts have to survive the change unaltered.
    """

    def _inside(self, a_au, solvent, pressure=1.0):
        band = _A03(solvent, pressure)
        return band is not None and band[0] <= a_au <= band[1]

    def test_b_is_inward_of_every_band(self, system):
        a = _planet(system, "b").elements.semi_major_axis
        assert a < _A03("sulfur")[0]
        assert not any(self._inside(a, key) for key in SOLVENTS)

    def test_c_is_in_sulfuric_acid_and_formamide_and_nothing_else(self, system):
        a = _planet(system, "c").elements.semi_major_axis
        assert {key for key in SOLVENTS if self._inside(a, key)} == {"sulfuric-acid",
                                                                     "formamide"}

    def test_d_is_in_ammonia_and_in_the_50_bar_carbon_dioxide_band(self, system):
        a = _planet(system, "d").elements.semi_major_axis
        assert {key for key in SOLVENTS if self._inside(a, key)} == {"ammonia"}
        assert self._inside(a, "carbon-dioxide", 50.0)

    def test_d_is_the_habitable_zone_planet_and_is_coloured_for_it(self, system):
        d = _planet(system, "d")
        assert d.color == "#44BB66"                    # the catalog's in-HZ colour
        assert d.color != _planet(system, "b").color


class TestDrawing:
    def test_the_bands_follow_the_planets_out_of_the_sky_plane(self, system):
        # The whole point of adding the angles: a band drawn flat on z = 0
        # would now cut across the orbits it is drawn for.
        a = [z for z in system.belt_zones if z.centre_body == "Upsilon Andromedae"]
        assert a
        for zone in a:
            assert zone.normal != Z_AXIS
            assert plane_tilt_deg(zone.normal) == pytest.approx(15.0, abs=1.0)

    def test_b_has_no_planets_so_its_bands_lie_in_the_sky_plane(self, system):
        # ups And B has no planets to set a plane, and its hollow circle is
        # drawn in the sky plane, so its stack lies there.
        b = [z for z in system.belt_zones if z.centre_body == "Upsilon Andromedae B"]
        assert b
        for zone in b:
            assert plane_tilt_deg(zone.normal) == pytest.approx(0.0, abs=1e-9)
            assert zone.star_label == "Upsilon Andromedae B"

    def test_the_tilt_is_stated_in_the_description(self, system):
        assert "degrees from the reference plane" in system.description
        assert "plane of the sky" in system.description
        assert "30 degrees apart" in system.description

    def test_the_line_of_sight_is_the_z_axis(self, system):
        # Angles are measured from the sky plane, so Earth is perpendicular to
        # it by construction rather than off in some ecliptic direction.
        assert system.solar_system_direction == (0.0, 0.0, 1.0)

    def test_every_planet_gets_a_closed_orbit_not_a_coil(self, system):
        # The planets orbit A, which sits still at the origin; B's circle about A
        # is a closed orbit too.
        orbit_paths, coil_paths = system_orbit_paths(system)
        assert set(orbit_paths) == {"Upsilon Andromedae b", "Upsilon Andromedae c",
                                    "Upsilon Andromedae d", "Upsilon Andromedae B"}
        assert coil_paths == {}

    def test_the_orbits_are_drawn_out_of_plane(self, system):
        # An inclined orbit has to reach off z = 0, or the angles are being
        # dropped somewhere between the elements and the geometry.
        orbit_paths, _ = system_orbit_paths(system)
        _, _, zs = orbit_paths["Upsilon Andromedae d"]
        reach = max(abs(v) for v in zs)
        # sin(24.55 deg) x apoapsis, near enough for a sampled ellipse.
        assert reach == pytest.approx(
            2.532293 * 1.274677 * math.sin(math.radians(24.55)), rel=0.05)

    def test_it_carries_the_solvent_bands_like_every_other_system(self, system):
        assert [z for z in system.belt_zones if z.name.startswith("Water band")]
        all_bands = get_builtin_system("upsilon-andromedae",
                                       SolventChoice.parse("all"))
        drawn = {z.name.split(" band")[0] for z in all_bands.belt_zones}
        assert len(drawn) == 8      # every solvent with a 1 bar liquid phase


class TestCompanionB:
    """ups And B: an M4.5 V companion with no measured orbit, drawn where Gaia saw it."""

    J2016 = 2457389.0

    @pytest.fixture
    def b(self, system):
        return system.get_body("Upsilon Andromedae B")

    def test_it_is_a_hypothetical_star_round_a(self, b):
        assert b.body_type == "star" and b.parent == "Upsilon Andromedae"
        assert b.status == "hypothetical"
        assert b.label() == "ups And B"

    def test_it_carries_the_workbook_rows_mass_and_teff(self, b):
        # Mugrauer 2019, table 4, as the catalog workbook's ups And B row has it.
        assert b.mass_kg / M_SUN_KG == pytest.approx(0.171, abs=0.001)
        assert b.teff_k == 3195.0

    def test_it_carries_the_workbook_rows_luminosity_and_a_band_stack(self, system, b):
        # TIC v8.2, as the workbook's ups And B row has it since 9 Oct 2026;
        # its R and Teff (0.223 R_sun, 3159 K) reproduce it.
        assert b.luminosity_sun == pytest.approx(0.223 ** 2 * (3159 / 5772) ** 4, rel=0.01)
        assert {z.centre_body for z in system.belt_zones} == {"Upsilon Andromedae",
                                                               "Upsilon Andromedae B"}

    def test_it_stands_at_its_gaia_position_in_2016(self, b):
        # Gaia DR3: 55.62 arcsec at PA 148.77 deg, 749.6 AU at A's 74.194 mas.
        # x is North and y East, so the position angle is atan2(y, x).
        from hybrasil.mechanics.kepler import elements_to_cartesian
        x, y, z = elements_to_cartesian(b.elements, self.J2016)[:3]
        assert math.hypot(x, y) == pytest.approx(749.6, abs=0.1)
        assert math.degrees(math.atan2(y, x)) % 360 == pytest.approx(148.77, abs=0.01)
        assert z == pytest.approx(0.0, abs=1e-9)

    def test_it_lies_in_the_sky_plane_on_a_circle(self, b):
        assert b.elements.inclination == 0.0
        assert b.elements.eccentricity == 0.0

    def test_the_period_is_keplers_third_law_on_both_masses(self, system, b):
        star = system.get_body("Upsilon Andromedae")
        assert b.elements.period == pytest.approx(
            derive_period_days(749.6, star.mass_kg + b.mass_kg), rel=1e-3)

    def test_it_is_cited_and_described(self, system, b):
        assert any("Lowrance" in s[0] for s in b.sources)
        assert any("Mugrauer 2019" in s[0] for s in b.sources)
        assert "ups And B" in system.description
