# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""55 Cancri B's two planets: present, around the right star, and the workbook's.

The workbook has their masses and nothing else, so the orbits come from the
discovery paper (Moutou et al. 2026).  The masses are what tie the two
sources together: if the paper's planets were not the workbook's, they would
not both come out at 3.5 and 5.3 M_Earth.
"""

import math

import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.mechanics.time_series import is_coil_body, system_orbit_paths

M_EARTH_KG = 5.9722e24
AU_M = 1.495978707e11
G = 6.674e-11
M_SUN_KG = 1.98847e30

# The workbook's "Planet masses (M-earth)" column for 55 Cnc.
WORKBOOK_MASSES = {"55 Cancri B b": 3.5, "55 Cancri B c": 5.3}


@pytest.fixture(scope="module")
def system():
    return get_builtin_system("55-cancri")


@pytest.fixture(scope="module")
def by_name(system):
    return {b.name: b for b in system.bodies}


class TestThePlanetsOfB:
    def test_both_orbit_b_not_a(self, by_name):
        for name in WORKBOOK_MASSES:
            assert by_name[name].parent == "55 Cancri B"

    def test_the_masses_are_the_workbooks(self, by_name):
        for name, m_earth in WORKBOOK_MASSES.items():
            assert by_name[name].mass_kg / M_EARTH_KG == pytest.approx(
                m_earth, rel=1e-3)

    def test_the_orbits_imply_the_papers_star(self, by_name):
        # Kepler's third law on the paper's P and a gives back its
        # 0.26 +/- 0.02 M_sun, which is what the axes were computed for.
        for name in WORKBOOK_MASSES:
            el = by_name[name].elements
            m = (4 * math.pi ** 2 * (el.semi_major_axis * AU_M) ** 3
                 / (G * (el.period * 86400.0) ** 2)) / M_SUN_KG
            assert 0.24 < m < 0.28

    def test_they_are_drawn_as_coils(self, system, by_name):
        # B is itself in orbit, so its planets have no closed ellipse.
        t0 = 2461306.5
        _, coils = system_orbit_paths(system, t_start=t0, t_end=t0 + 5700.0)
        for name in WORKBOOK_MASSES:
            assert is_coil_body(by_name[name], by_name)
            assert name in coils

    def test_they_come_after_their_star(self, system):
        # Bodies must be listed in dependency order.
        names = [b.name for b in system.bodies]
        for name in WORKBOOK_MASSES:
            assert names.index(name) > names.index("55 Cancri B")

    def test_the_description_no_longer_says_they_are_missing(self, system):
        assert "not drawn" not in system.description
        assert "Moutou et al. 2026" in system.description


class TestTheCandidateG:
    """55 Cnc g: Moutou et al.'s sixth signal, drawn as the candidate it is."""

    def test_it_is_drawn_and_marked_unconfirmed(self, by_name):
        g = by_name["55 Cancri g"]
        assert g.parent == "55 Cancri A"
        assert g.status == "hypothetical"
        assert "candidate" in g.display_name

    def test_its_orbit_is_the_workbooks(self, by_name):
        # The Unconfirmed tab's row: P and e from the paper's Table 8, a by
        # Kepler III on the paper's 1.015 M_sun star.
        e = by_name["55 Cancri g"].elements
        assert e.period == 3827.1
        assert e.eccentricity == 0.35
        assert e.semi_major_axis == 4.812
        assert (e.semi_major_axis ** 3 / (e.period / 365.25) ** 2
                == pytest.approx(1.015, rel=1e-3))

    def test_it_is_co_planar_with_the_measured_planet(self, by_name):
        assert (by_name["55 Cancri g"].elements.inclination
                == by_name["55 Cancri e"].elements.inclination)

    def test_the_description_does_not_oversell_it(self, system):
        assert "UNCONFIRMED" in system.description
        assert "55 Cnc g" in system.description


class TestMeasuredGeometry:
    """Which angles are measured, and that the drawing keeps them.

    A's planets looked perpendicular to B's because B's were drawn face-on to
    us and A's edge-on.  Now: e's transit tilt (Bourrier et al. 2018), d's
    astrometric tilt and node and B's orbit about A (Xiao et al. 2026), and
    B's planets in B's orbit plane -- the last an assumption, said so.
    """

    GAIA_SEP_AU = 84.82 * 12.587       # rho (arcsec) x distance (pc)
    GAIA_PA_DEG = 128.1                # B from A, Gaia DR3, epoch 2016.0
    GAIA_EPOCH = 2457389.0

    @staticmethod
    def _normal(body):
        from hybrasil.mechanics.orientation import orbital_normal
        el = body.elements
        return orbital_normal(el.inclination, el.longitude_of_ascending_node)

    @staticmethod
    def _angle(u, v):
        dot = sum(a * b for a, b in zip(u, v))
        return math.degrees(math.acos(max(-1.0, min(1.0, dot))))

    def test_d_carries_its_measured_tilt_and_node(self, by_name):
        el = by_name["55 Cancri d"].elements
        assert el.inclination == 93.9
        assert el.longitude_of_ascending_node == 124.0

    def test_every_planet_of_a_shares_ds_node(self, by_name):
        for name in ("e", "b", "c", "f", "d", "g"):
            el = by_name[f"55 Cancri {name}"].elements
            assert el.longitude_of_ascending_node == 124.0, name

    def test_e_keeps_its_transit_tilt(self, by_name):
        # 96.41 and the transit's 83.59 are the same tilt to the sky.
        i = by_name["55 Cancri e"].elements.inclination
        assert math.sin(math.radians(i)) == pytest.approx(
            math.sin(math.radians(83.59)))

    def test_e_and_d_are_nearly_co_planar(self, by_name):
        a = self._angle(self._normal(by_name["55 Cancri e"]),
                        self._normal(by_name["55 Cancri d"]))
        assert a < 5.0

    def test_bs_orbit_is_the_fitted_one(self, by_name):
        el = by_name["55 Cancri B"].elements
        assert (el.semi_major_axis, el.eccentricity, el.inclination) == (
            1259.0, 0.55, 67.7)

    def test_b_is_where_gaia_sees_it(self, system):
        # Pins the frame as well as the phase: a mirrored node or a flipped
        # inclination would put B at the wrong position angle.
        from hybrasil.mechanics.time_series import system_positions_at
        x, y, _ = system_positions_at(system, self.GAIA_EPOCH)["55 Cancri B"]
        assert math.hypot(x, y) == pytest.approx(self.GAIA_SEP_AU, rel=0.01)
        pa = math.degrees(math.atan2(y, x)) % 360.0
        assert pa == pytest.approx(self.GAIA_PA_DEG, abs=1.0)

    def test_bs_planets_lie_in_bs_orbit_plane(self, by_name):
        star = by_name["55 Cancri B"].elements
        for name in ("55 Cancri B b", "55 Cancri B c"):
            el = by_name[name].elements
            assert (el.inclination, el.longitude_of_ascending_node) == (
                star.inclination, star.longitude_of_ascending_node)

    def test_the_two_planet_systems_are_not_drawn_perpendicular(self, system,
                                                                by_name):
        a = self._angle(self._normal(by_name["55 Cancri e"]),
                        self._normal(by_name["55 Cancri B b"]))
        assert a == pytest.approx(47.4, abs=0.5)
        assert "47 degrees" in system.description

    def test_each_band_stack_lies_in_its_own_stars_planet_plane(self, system,
                                                              by_name):
        for star, planet in (("55 Cancri A", "55 Cancri e"),
                             ("55 Cancri B", "55 Cancri B b")):
            zone = next(z for z in system.belt_zones if z.centre_body == star)
            # A band's normal may point either way along the plane's normal.
            a = self._angle(zone.normal, self._normal(by_name[planet]))
            assert min(a, 180.0 - a) < 5.0, star
