# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Coil trajectories for planets of an orbiting star, and zoom framing."""

import math
import numpy as np
import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.mechanics.kepler import elements_to_cartesian
from hybrasil.mechanics.time_series import (
    COIL_MAX_POINTS,
    COIL_MIN_POINTS,
    generate_coil_orbit_path,
    is_coil_body,
    system_orbit_paths,
)
from hybrasil.mechanics.units import J2000
from hybrasil.viz.export import _core_child_extent


T_START = J2000
T_END = J2000 + 365.25 * 20


def _alpha_centauri():
    return get_builtin_system("alpha-centauri")


def _body(system, name):
    return {b.name: b for b in system.bodies}[name]


class TestCoilDetection:
    def test_planet_of_orbiting_star_coils(self):
        system = _alpha_centauri()
        by_name = {b.name: b for b in system.bodies}
        assert is_coil_body(by_name["Proxima Centauri b"], by_name)

    def test_moon_of_planet_does_not_coil(self):
        """A closed ellipse is what makes the zoomed-in moon view readable."""
        system = get_builtin_system("solar")
        by_name = {b.name: b for b in system.bodies}
        assert not is_coil_body(by_name["Moon"], by_name)
        assert not is_coil_body(by_name["Io"], by_name)

    def test_star_orbiting_the_primary_does_not_coil(self):
        system = _alpha_centauri()
        by_name = {b.name: b for b in system.bodies}
        assert not is_coil_body(by_name["Proxima Centauri"], by_name)
        assert not is_coil_body(by_name["Alpha Centauri B"], by_name)


class TestCoilGeometry:
    def test_radius_about_moving_parent_is_the_semi_major_axis(self):
        system = _alpha_centauri()
        planet = _body(system, "Proxima Centauri b")
        parent = _body(system, "Proxima Centauri")
        xs, ys, zs = generate_coil_orbit_path(
            planet.elements, parent.elements, T_START, T_END
        )
        times = np.linspace(T_START, T_END, len(xs))
        centers = np.array([elements_to_cartesian(parent.elements, t) for t in times])
        radii = np.linalg.norm(np.stack([xs, ys, zs], axis=1) - centers, axis=1)
        assert np.allclose(radii, planet.elements.semi_major_axis, rtol=1e-9)

    def test_winding_count_matches_span_over_period(self):
        system = _alpha_centauri()
        planet = _body(system, "Proxima Centauri c")
        parent = _body(system, "Proxima Centauri")
        xs, ys, zs = generate_coil_orbit_path(
            planet.elements, parent.elements, T_START, T_END
        )
        times = np.linspace(T_START, T_END, len(xs))
        centers = np.array([elements_to_cartesian(parent.elements, t) for t in times])
        rel = np.stack([xs, ys, zs], axis=1) - centers
        angle = np.unwrap(np.arctan2(rel[:, 1], rel[:, 0]))
        turns = abs(angle[-1] - angle[0]) / (2 * math.pi)
        assert turns == pytest.approx((T_END - T_START) / planet.elements.period, rel=0.02)

    def test_the_curve_is_open(self):
        """Unlike an ellipse, the body never returns to where it started."""
        system = _alpha_centauri()
        planet = _body(system, "Proxima Centauri b")
        parent = _body(system, "Proxima Centauri")
        xs, ys, zs = generate_coil_orbit_path(
            planet.elements, parent.elements, T_START, T_END
        )
        gap = math.dist((xs[0], ys[0], zs[0]), (xs[-1], ys[-1], zs[-1]))
        assert gap > planet.elements.semi_major_axis

    def test_point_count_is_clamped(self):
        system = _alpha_centauri()
        parent = _body(system, "Proxima Centauri")
        short = _body(system, "Proxima Centauri d")     # 5.15 d over 20 yr
        long = _body(system, "Proxima Centauri c")      # 1928 d over 20 yr
        assert len(generate_coil_orbit_path(
            short.elements, parent.elements, T_START, T_END)[0]) == COIL_MAX_POINTS
        assert len(generate_coil_orbit_path(
            long.elements, parent.elements, T_START, T_END)[0]) == COIL_MIN_POINTS

    def test_backwards_window_is_rejected(self):
        system = _alpha_centauri()
        planet = _body(system, "Proxima Centauri b")
        parent = _body(system, "Proxima Centauri")
        with pytest.raises(ValueError):
            generate_coil_orbit_path(planet.elements, parent.elements, T_END, T_START)


class TestSystemOrbitPaths:
    def test_each_body_with_elements_appears_exactly_once(self):
        for name in ("solar", "trappist-1", "alpha-centauri", "proxima-centauri"):
            system = get_builtin_system(name)
            orbits, coils = system_orbit_paths(system, t_start=T_START, t_end=T_END)
            expected = {b.name for b in system.bodies if b.elements is not None}
            assert set(orbits).isdisjoint(coils), name
            assert set(orbits) | set(coils) == expected, name

    def test_proxima_planets_coil_inside_alpha_centauri(self):
        orbits, coils = system_orbit_paths(
            _alpha_centauri(), t_start=T_START, t_end=T_END
        )
        assert set(coils) == {
            "Proxima Centauri b", "Proxima Centauri c", "Proxima Centauri d"
        }
        assert "Proxima Centauri" in orbits

    def test_solar_system_has_no_coils(self):
        _, coils = system_orbit_paths(
            get_builtin_system("solar"), t_start=T_START, t_end=T_END
        )
        assert coils == {}

    def test_without_a_window_everything_stays_an_ellipse(self):
        orbits, coils = system_orbit_paths(_alpha_centauri(), t_start=T_START)
        assert coils == {}
        assert "Proxima Centauri b" in orbits


class TestCoreChildExtent:
    def test_distant_companion_is_excluded(self):
        """Proxima at 8,700 AU must not set the framing for the 23 AU binary."""
        assert _core_child_extent([1.1, 23.4, 8700.0]) == 23.4

    def test_a_smoothly_spaced_group_is_kept_whole(self):
        assert _core_child_extent([0.029, 0.04856, 1.489]) == 1.489

    def test_empty_and_degenerate_inputs(self):
        assert _core_child_extent([]) == 0.0
        assert _core_child_extent([0.0, -1.0]) == 0.0
