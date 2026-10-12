# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the two reference arrows: the Sun and the galactic centre.

Both are drawn as directions, and a direction is only meaningful in a frame.
Every built-in system but the Solar System is quoted against the plane of the
sky -- TRAPPIST-1's inclinations come from transits, Alpha Centauri's from a
visual-binary solution, Upsilon Andromedae's from HST astrometry -- so an
ecliptic vector points somewhere those systems' own orbits do not agree with.
That was the bug: one ecliptic constant served every system.

The checks that matter here are the ones that do not depend on the convention
being right: that the vectors are unit, that the line-of-sight component has
the sign the sky geometry requires, and that the Solar System is left alone.
"""

import math

import pytest

from hybrasil.data.builtin_systems import (
    BUILTIN_NAMES,
    _SKY_ALPHA_CEN,
    _SKY_PROXIMA,
    _SKY_TRAPPIST_1,
    _SKY_UPS_AND,
    get_builtin_system,
)
from hybrasil.mechanics.orientation import (
    GALACTIC_CENTRE_DEC_DEG,
    GALACTIC_CENTRE_DISTANCE_LY,
    GALACTIC_CENTRE_RA_DEG,
    TOWARD_EARTH,
    equatorial_unit,
    galactic_centre_distance_ly,
    galactic_centre_in_sky_frame,
    sky_frame_basis,
    toward_sun_in_ecliptic,
)
from hybrasil.mechanics.time_series import system_positions_at
from hybrasil.mechanics.units import J2000
from hybrasil.viz.static_plot import _GC_DIR, build_static_figure

SKY = {
    "trappist-1": _SKY_TRAPPIST_1,
    "alpha-centauri": _SKY_ALPHA_CEN,
    "proxima-centauri": _SKY_PROXIMA,
    "upsilon-andromedae": _SKY_UPS_AND,
}


def _norm(v):
    return math.sqrt(sum(c * c for c in v))


def _dot(a, b):
    return sum(p * q for p, q in zip(a, b))


class TestSkyFrameBasis:
    @pytest.mark.parametrize("ra,dec", [(0.0, 0.0), (346.6225, -5.04139),
                                        (219.90208, -60.83389), (24.19933, 41.40544),
                                        (180.0, 89.0)])
    def test_it_is_orthonormal(self, ra, dec):
        north, east, out = sky_frame_basis(ra, dec)
        for v in (north, east, out):
            assert _norm(v) == pytest.approx(1.0)
        assert _dot(north, east) == pytest.approx(0.0, abs=1e-12)
        assert _dot(north, out) == pytest.approx(0.0, abs=1e-12)
        assert _dot(east, out) == pytest.approx(0.0, abs=1e-12)

    @pytest.mark.parametrize("ra,dec", [(0.0, 0.0), (346.6225, -5.04139),
                                        (24.19933, 41.40544)])
    def test_the_third_axis_points_back_at_the_observer(self, ra, dec):
        # North x East is the line of sight *toward* Earth, which is what makes
        # the Sun's direction +z in a sky frame.
        _, _, out = sky_frame_basis(ra, dec)
        assert _dot(out, equatorial_unit(ra, dec)) == pytest.approx(-1.0)

    def test_north_points_north(self):
        # At the celestial equator, North on the sky is the +z of the
        # equatorial frame.
        north, _, _ = sky_frame_basis(123.0, 0.0)
        assert north == pytest.approx((0.0, 0.0, 1.0), abs=1e-12)


class TestGalacticCentreDirection:
    @pytest.mark.parametrize("key", sorted(SKY))
    def test_it_is_a_unit_vector(self, key):
        assert _norm(galactic_centre_in_sky_frame(*SKY[key])) == pytest.approx(1.0)

    def test_from_the_sun_it_reduces_to_the_line_of_sight(self):
        # A star in the exact direction of the galactic centre sees it dead
        # ahead: straight down its own -z, since +z points back at us.
        ra, dec = GALACTIC_CENTRE_RA_DEG, GALACTIC_CENTRE_DEC_DEG
        v = galactic_centre_in_sky_frame(ra, dec, 100.0)
        assert v == pytest.approx((0.0, 0.0, -1.0), abs=1e-9)

    def test_a_star_beyond_the_centre_sees_it_behind_them(self):
        # Same sky direction, but further away than the centre: it is now back
        # toward Earth, so +z.
        v = galactic_centre_in_sky_frame(GALACTIC_CENTRE_RA_DEG,
                                         GALACTIC_CENTRE_DEC_DEG,
                                         GALACTIC_CENTRE_DISTANCE_LY * 2)
        assert v == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)

    def test_alpha_centauri_looks_toward_the_centre_and_ups_and_away_from_it(self):
        # Alpha Centauri is in Centaurus, roughly centre-ward, so the galactic
        # centre lies beyond it, away from Earth: negative z. Upsilon
        # Andromedae is most of the sky away, so the centre is back past us.
        assert galactic_centre_in_sky_frame(*_SKY_ALPHA_CEN)[2] < 0
        assert galactic_centre_in_sky_frame(*_SKY_UPS_AND)[2] > 0

    @pytest.mark.parametrize("key,expected_ly", [
        ("trappist-1", 26666.0), ("alpha-centauri", 26667.0),
        ("proxima-centauri", 26667.0), ("upsilon-andromedae", 26697.4),
    ])
    def test_the_distance_agrees_with_the_figure_each_system_carries(self, key,
                                                                    expected_ly):
        # Direction and distance are computed the same way, so this says the
        # geometry behind the arrows matches the label printed on them.
        got = galactic_centre_distance_ly(*SKY[key])
        assert got == pytest.approx(expected_ly, abs=5.0)
        assert get_builtin_system(key).distance_to_galactic_center_ly == expected_ly


class TestBuiltinSystems:
    @pytest.mark.parametrize("key", sorted(SKY))
    def test_a_sky_frame_system_puts_the_sun_on_its_z_axis(self, key):
        assert get_builtin_system(key).solar_system_direction == TOWARD_EARTH

    @pytest.mark.parametrize("key", sorted(SKY))
    def test_a_sky_frame_system_carries_its_own_centre_direction(self, key):
        system = get_builtin_system(key)
        assert system.galactic_center_direction is not None
        assert system.galactic_center_direction != _GC_DIR
        assert _norm(system.galactic_center_direction) == pytest.approx(1.0)

    def test_the_solar_system_keeps_the_ecliptic_constant(self):
        # Its frame *is* the ecliptic, so the fallback is correct for it and
        # it has no Sun arrow to draw at all.
        solar = get_builtin_system("solar")
        assert solar.galactic_center_direction is None
        assert solar.solar_system_direction is None

    def test_no_system_is_left_on_an_ecliptic_vector_by_accident(self):
        for key in BUILTIN_NAMES:
            system = get_builtin_system(key)
            if system.solar_system_direction is None:
                continue                      # the Solar System itself
            assert system.solar_system_direction == TOWARD_EARTH, (
                f"{key} still carries an ecliptic direction to the Sun")


class TestArrowsReachTheFigure:
    @pytest.mark.parametrize("key", sorted(SKY))
    def test_the_drawn_arrow_uses_the_systems_own_direction(self, key):
        system = get_builtin_system(key)
        positions = system_positions_at(system, J2000)
        orbit_paths = {}
        fig = build_static_figure(system, positions, orbit_paths)
        shaft = next(t for t in fig.data
                     if t.name and t.name.startswith("Galactic Center"))
        # The shaft runs from the primary to primary + direction * length, so
        # its own direction has to be the system's, not the ecliptic constant.
        tail = (shaft.x[0], shaft.y[0], shaft.z[0])
        tip = (shaft.x[1], shaft.y[1], shaft.z[1])
        drawn = [tip[a] - tail[a] for a in range(3)]
        length = _norm(drawn)
        unit = tuple(c / length for c in drawn)
        assert unit == pytest.approx(system.galactic_center_direction, abs=1e-9)

    def test_a_system_without_its_own_direction_falls_back(self):
        solar = get_builtin_system("solar")
        positions = system_positions_at(solar, J2000)
        fig = build_static_figure(solar, positions, {})
        shaft = next(t for t in fig.data
                     if t.name and t.name.startswith("Galactic Center"))
        tail = (shaft.x[0], shaft.y[0], shaft.z[0])
        tip = (shaft.x[1], shaft.y[1], shaft.z[1])
        drawn = [tip[a] - tail[a] for a in range(3)]
        # _GC_DIR is written out to five decimals, so it is not quite a unit
        # vector; the drawn arrow normalises it and lands 6e-5 away.
        unit = tuple(c / _norm(drawn) for c in drawn)
        assert unit == pytest.approx(_GC_DIR, abs=1e-4)


class TestTowardTheSunInTheEcliptic:
    """A catalog system is drawn in the ecliptic; its Sun arrow is -star."""

    def test_a_star_at_the_north_ecliptic_pole_sees_the_sun_straight_down(self):
        v = toward_sun_in_ecliptic(270.0, 66.560708)
        assert v == pytest.approx((0.0, 0.0, -1.0), abs=1e-6)

    def test_a_star_toward_the_vernal_equinox_sees_the_sun_along_minus_x(self):
        assert toward_sun_in_ecliptic(0.0, 0.0) == pytest.approx((-1.0, 0.0, 0.0), abs=1e-12)

    def test_it_agrees_with_the_ecliptic_galactic_centre_constant(self):
        # _GC_DIR is Sgr A* in ecliptic coordinates, so a star sitting in that
        # direction sees the Sun exactly opposite it.
        v = toward_sun_in_ecliptic(GALACTIC_CENTRE_RA_DEG, GALACTIC_CENTRE_DEC_DEG)
        assert v == pytest.approx(tuple(-c for c in _GC_DIR), abs=1e-4)

    def test_it_agrees_with_astropy(self):
        coords = pytest.importorskip("astropy.coordinates")
        import astropy.units as u
        ra, dec = _SKY_ALPHA_CEN[:2]
        ecl = coords.SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs"
                              ).transform_to(coords.BarycentricMeanEcliptic(equinox="J2000"))
        lon, lat = math.radians(ecl.lon.deg), math.radians(ecl.lat.deg)
        expected = (-math.cos(lat) * math.cos(lon), -math.cos(lat) * math.sin(lon),
                    -math.sin(lat))
        # ICRS vs the dynamical J2000 equinox differ by ~0.02 arcsec.
        assert toward_sun_in_ecliptic(ra, dec) == pytest.approx(expected, abs=1e-6)
