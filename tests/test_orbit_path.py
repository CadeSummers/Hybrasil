# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A body's marker sits on its own drawn orbit.

The marker is on the true ellipse (elements_to_cartesian); the orbit line is the
polygon generate_orbit_path returns.  The gap between them is the polygon's chord
error, and a double-click on a heliocentric body frames it at +/- 1% of its
semi-major axis (viz/export.py), where 360 points in true anomaly left Eris a
visible few pixels off its orbit near aphelion.
"""

import math

import numpy as np
import pytest

from hybrasil.data.builtin_systems import BUILTIN_NAMES, get_builtin_system
from hybrasil.mechanics.kepler import (elements_to_cartesian, rotate_to_reference_frame,
                                            true_anomaly_to_orbital_plane)
from hybrasil.mechanics.time_series import generate_orbit_path
from hybrasil.mechanics.units import J2000

# At the double-click zoom (+/- 0.01 a, camera 2.2 half-widths back, 45 deg
# field) an 850 px view spans about 1.8e-2 a, so one pixel is 2.1e-5 a.
HALF_PIXEL_A = 1.1e-5


def _gap(point, path):
    """Distance from `point` to the closed polyline `path` (N x 3)."""
    a, b = path[:-1], path[1:]
    ab = b - a
    t = np.clip(((point - a) * ab).sum(1) / (ab * ab).sum(1), 0.0, 1.0)[:, None]
    return float(np.linalg.norm(point - (a + t * ab), axis=1).min())


def _worst_gap(elements, path, n_times=97):
    times = np.linspace(J2000, J2000 + elements.period, n_times, endpoint=False)
    return max(_gap(np.array(elements_to_cartesian(elements, t)), path) for t in times)


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_every_body_sits_on_its_drawn_orbit(key):
    for body in get_builtin_system(key).bodies:
        if body.elements is None:
            continue
        path = np.column_stack(generate_orbit_path(body.elements))
        a = body.elements.semi_major_axis
        assert _worst_gap(body.elements, path) < HALF_PIXEL_A * a, body.name


def test_eris_was_off_its_orbit_with_360_points_in_true_anomaly():
    # The hazard is real: the old sampling put Eris's marker 0.007 AU -- over
    # four pixels at its double-click zoom -- inside its drawn orbit near aphelion.
    el = next(b for b in get_builtin_system("solar").bodies if b.name == "Eris").elements
    old = []
    for nu in np.linspace(0.0, 2.0 * math.pi, 361):
        x, y = true_anomaly_to_orbital_plane(nu, el.semi_major_axis, el.eccentricity)
        old.append(rotate_to_reference_frame(x, y, el.inclination, el.longitude_of_ascending_node,
                                             el.argument_of_periapsis))
    assert _worst_gap(el, np.array(old)) > 4 * 2 * HALF_PIXEL_A * el.semi_major_axis
    assert _worst_gap(el, np.column_stack(generate_orbit_path(el))) < HALF_PIXEL_A * el.semi_major_axis
