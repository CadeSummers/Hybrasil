# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for Keplerian mechanics."""

import math
import pytest
from hybrasil.mechanics.kepler import (
    mean_anomaly_at_time,
    solve_kepler,
    eccentric_to_true_anomaly,
    true_anomaly_to_orbital_plane,
    rotate_to_reference_frame,
    elements_to_cartesian,
)
from hybrasil.models.elements import KeplerianElements

J2000 = 2451545.0


# Earth J2000 elements (mean)
EARTH = KeplerianElements(
    semi_major_axis=1.00000,
    eccentricity=0.01671,
    inclination=0.000,
    longitude_of_ascending_node=0.0,
    argument_of_periapsis=102.937,
    mean_anomaly_at_epoch=100.464,
    epoch=J2000,
    period=365.256,
)


class TestSolveKepler:
    def test_circular_orbit(self):
        """For e=0, E should equal M."""
        for M in [0, 45, 90, 180, 270, 359]:
            E = solve_kepler(float(M), 0.0)
            assert abs(E - math.radians(M)) < 1e-10

    def test_kepler_equation_satisfied(self):
        """E - e*sin(E) = M must hold to high precision."""
        for e in [0.0, 0.1, 0.5, 0.9]:
            for M_deg in [0, 30, 90, 180, 270]:
                E = solve_kepler(float(M_deg), e)
                M_rad = math.radians(M_deg)
                residual = abs(E - e * math.sin(E) - M_rad)
                assert residual < 1e-10, f"e={e}, M={M_deg}: residual={residual}"

    def test_high_eccentricity(self):
        """Halley's method should handle e=0.99 (extreme case)."""
        E = solve_kepler(90.0, 0.99)
        M_rad = math.radians(90.0)
        residual = abs(E - 0.99 * math.sin(E) - M_rad)
        assert residual < 1e-8


class TestTrueAnomaly:
    def test_periapsis(self):
        """At E=0, true anomaly should be 0."""
        nu = eccentric_to_true_anomaly(0.0, 0.1)
        assert abs(nu) < 1e-12

    def test_apoapsis(self):
        """At E=pi, true anomaly should be pi."""
        nu = eccentric_to_true_anomaly(math.pi, 0.3)
        assert abs(nu - math.pi) < 1e-10

    def test_range(self):
        """True anomaly should stay in [-2*pi, 2*pi] (2*atan2 range)."""
        for E in [0, 1, 2, 3, 4, 5, 6]:
            nu = eccentric_to_true_anomaly(float(E), 0.5)
            assert -2 * math.pi <= nu <= 2 * math.pi


class TestOrbitalPlane:
    def test_periapsis_distance(self):
        """At nu=0, r should equal a*(1-e)."""
        a, e = 1.5, 0.3
        x, y = true_anomaly_to_orbital_plane(0.0, a, e)
        r = math.sqrt(x**2 + y**2)
        assert abs(r - a * (1 - e)) < 1e-12

    def test_apoapsis_distance(self):
        """At nu=pi, r should equal a*(1+e)."""
        a, e = 1.5, 0.3
        x, y = true_anomaly_to_orbital_plane(math.pi, a, e)
        r = math.sqrt(x**2 + y**2)
        assert abs(r - a * (1 + e)) < 1e-10


class TestRotation:
    def test_zero_angles_identity(self):
        """With i=Omega=omega=0, orbital plane = reference plane."""
        x, y, z = rotate_to_reference_frame(1.0, 0.0, 0.0, 0.0, 0.0)
        assert abs(x - 1.0) < 1e-12
        assert abs(y) < 1e-12
        assert abs(z) < 1e-12

    def test_90_inclination(self):
        """With i=90, y_orb maps to z."""
        x, y, z = rotate_to_reference_frame(0.0, 1.0, 90.0, 0.0, 0.0)
        assert abs(z - 1.0) < 1e-10


class TestEarthPosition:
    def test_earth_at_j2000_distance(self):
        """Earth at J2000 should be ~1 AU from the Sun."""
        x, y, z = elements_to_cartesian(EARTH, J2000)
        r = math.sqrt(x**2 + y**2 + z**2)
        assert 0.98 < r < 1.02, f"Expected ~1 AU, got {r:.4f} AU"

    def test_earth_near_ecliptic(self):
        """Earth's inclination is ~0, so z should be near zero."""
        x, y, z = elements_to_cartesian(EARTH, J2000)
        assert abs(z) < 0.01, f"Expected z~0, got z={z:.6f}"

    def test_period_returns_to_start(self):
        """After one orbital period, Earth should be at same position."""
        x0, y0, z0 = elements_to_cartesian(EARTH, J2000)
        x1, y1, z1 = elements_to_cartesian(EARTH, J2000 + EARTH.period)
        dr = math.sqrt((x1-x0)**2 + (y1-y0)**2 + (z1-z0)**2)
        assert dr < 1e-4, f"Expected dr~0 after one period, got {dr:.6f} AU"


class TestMeanAnomaly:
    def test_at_epoch(self):
        """Mean anomaly at epoch should equal M0."""
        M = mean_anomaly_at_time(100.0, 365.25, J2000, J2000)
        assert abs(M - 100.0) < 1e-12

    def test_after_one_period(self):
        """Mean anomaly after one full period should equal M0 (mod 360)."""
        M = mean_anomaly_at_time(50.0, 365.25, J2000 + 365.25, J2000)
        assert abs(M - 50.0) < 1e-8
