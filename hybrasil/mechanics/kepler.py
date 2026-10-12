# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Keplerian orbital mechanics: elements -> 3D Cartesian positions."""

import math
from ..models.elements import KeplerianElements


def mean_anomaly_at_time(M0_deg: float, period_days: float, t_jd: float, epoch_jd: float) -> float:
    """Compute mean anomaly (degrees) at Julian Date t_jd."""
    dt = t_jd - epoch_jd
    n = 360.0 / period_days  # mean motion deg/day
    M = (M0_deg + n * dt) % 360.0
    if M < 0:
        M += 360.0
    return M


def solve_kepler(M_deg: float, e: float, tol: float = 1e-12) -> float:
    """Solve Kepler's equation M = E - e*sin(E) using Halley's method.

    Args:
        M_deg: Mean anomaly in degrees.
        e: Eccentricity (0 <= e < 1).
        tol: Convergence tolerance in radians.

    Returns:
        Eccentric anomaly E in radians.
    """
    M = math.radians(M_deg)
    # Initial guess
    E = M + e * math.sin(M) * (1.0 + e * math.cos(M))
    for _ in range(100):
        sin_E = math.sin(E)
        cos_E = math.cos(E)
        f = E - e * sin_E - M
        fp = 1.0 - e * cos_E
        fpp = e * sin_E
        # Halley's method step
        dE = -f / (fp - 0.5 * f * fpp / fp)
        E += dE
        if abs(dE) < tol:
            break
    return E


def eccentric_to_true_anomaly(E_rad: float, e: float) -> float:
    """Convert eccentric anomaly E (radians) to true anomaly nu (radians)."""
    nu = 2.0 * math.atan2(
        math.sqrt(1.0 + e) * math.sin(E_rad / 2.0),
        math.sqrt(1.0 - e) * math.cos(E_rad / 2.0),
    )
    return nu


def true_anomaly_to_orbital_plane(nu_rad: float, a: float, e: float) -> tuple[float, float]:
    """Position in the orbital plane (AU).

    Returns (x_orb, y_orb) where x is toward periapsis.
    """
    r = a * (1.0 - e ** 2) / (1.0 + e * math.cos(nu_rad))
    x = r * math.cos(nu_rad)
    y = r * math.sin(nu_rad)
    return x, y


def rotate_to_reference_frame(
    x_orb: float,
    y_orb: float,
    i_deg: float,
    Omega_deg: float,
    omega_deg: float,
) -> tuple[float, float, float]:
    """Apply Euler rotations from orbital plane to reference frame (AU).

    Rotation order:
      1. By argument of periapsis omega around z-axis (orbital plane orientation)
      2. By inclination i around x-axis (tilt out of reference plane)
      3. By longitude of ascending node Omega around z-axis (orientation of node)
    """
    i = math.radians(i_deg)
    Omega = math.radians(Omega_deg)
    omega = math.radians(omega_deg)

    cos_O, sin_O = math.cos(Omega), math.sin(Omega)
    cos_o, sin_o = math.cos(omega), math.sin(omega)
    cos_i, sin_i = math.cos(i), math.sin(i)

    x = (cos_O * cos_o - sin_O * sin_o * cos_i) * x_orb + (-cos_O * sin_o - sin_O * cos_o * cos_i) * y_orb
    y = (sin_O * cos_o + cos_O * sin_o * cos_i) * x_orb + (-sin_O * sin_o + cos_O * cos_o * cos_i) * y_orb
    z = (sin_o * sin_i) * x_orb + (cos_o * sin_i) * y_orb

    return x, y, z


def elements_to_cartesian(elements: KeplerianElements, t_jd: float) -> tuple[float, float, float]:
    """Full pipeline: KeplerianElements + Julian Date -> (x, y, z) in AU."""
    M = mean_anomaly_at_time(
        elements.mean_anomaly_at_epoch,
        elements.period,
        t_jd,
        elements.epoch,
    )
    E = solve_kepler(M, elements.eccentricity)
    nu = eccentric_to_true_anomaly(E, elements.eccentricity)
    x_orb, y_orb = true_anomaly_to_orbital_plane(nu, elements.semi_major_axis, elements.eccentricity)
    x, y, z = rotate_to_reference_frame(
        x_orb, y_orb,
        elements.inclination,
        elements.longitude_of_ascending_node,
        elements.argument_of_periapsis,
    )
    return x, y, z
