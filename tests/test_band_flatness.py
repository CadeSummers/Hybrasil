# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A solvent band's geometry must be a flat annulus around its own star.

This is the geometric half of the "always a flat disc" rule in CLAUDE.md, and
it is deliberately not the whole of it.  When nineteen of Alpha Centauri's
bands rendered as tori made of beads, every one of them passed every check in
this file: the geometry was exactly planar the whole time, and the trace had
been retyped from mesh3d to scatter3d by the system switcher.  Being planar is
necessary and not sufficient, which is why the rule also says to open the
figure and look at it.

See `tests/test_system_switch.py` for the other half.
"""

import numpy as np
import pytest

from hybrasil.data.builtin_systems import BUILTIN_NAMES, get_builtin_system
from hybrasil.mechanics.solvent_bands import SolventChoice
from hybrasil.mechanics.time_series import (system_orbit_paths,
                                                 system_positions_at)
from hybrasil.mechanics.units import J2000
from hybrasil.viz.animation import build_animated_figure
from hybrasil.viz.static_plot import _belt_trace, build_static_figure

ALL_BANDS = SolventChoice.parse("all")

# A band is planar to floating point, not approximately planar.
FLAT_TOL_AU = 1e-9


def verify_band_is_a_flat_disc(trace, zone, centre=(0.0, 0.0, 0.0)):
    """Raise unless this trace's geometry is a flat annulus around `centre`.

    The single place the rule is expressed, so a new figure builder, data
    source or system is one call away from being covered.
    """
    pts = np.column_stack([np.asarray(trace.x, dtype=float),
                           np.asarray(trace.y, dtype=float),
                           np.asarray(trace.z, dtype=float)])
    if not len(pts):
        return                                  # no liquid phase: nothing drawn

    normal = np.asarray(zone.normal, dtype=float)
    normal = normal / np.linalg.norm(normal)
    origin = np.asarray(centre, dtype=float)

    # 1. Planar: every vertex the same distance along the normal.
    depth = (pts - origin) @ normal
    spread = float(depth.max() - depth.min())
    assert spread < FLAT_TOL_AU, (
        f"{zone.name} is not flat: it spans {spread:.3e} AU along its normal")

    # ...and that distance is its stacking offset, not somewhere arbitrary.
    assert depth[0] == pytest.approx(zone.offset_au, abs=1e-9), (
        f"{zone.name} does not sit in its own plane")

    # 2. An annulus of the right size, centred on its own star.
    in_plane = (pts - origin) - np.outer(depth, normal)
    radii = np.linalg.norm(in_plane, axis=1)
    assert radii.min() == pytest.approx(zone.r_inner_au, rel=1e-9)
    assert radii.max() == pytest.approx(zone.r_outer_au, rel=1e-9)

    # 3. Consistent winding: every face on the same side of the plane.  A mesh
    #    with mixed winding is lit as alternating facets whichever way it is
    #    shaded, and a degenerate triangle shows up here as a zero normal.
    faces = np.column_stack([np.asarray(trace.i, dtype=int),
                             np.asarray(trace.j, dtype=int),
                             np.asarray(trace.k, dtype=int)])
    face_n = np.cross(pts[faces[:, 1]] - pts[faces[:, 0]],
                      pts[faces[:, 2]] - pts[faces[:, 0]])
    along = face_n @ normal
    assert np.all(along > 0) or np.all(along < 0), (
        f"{zone.name} has faces wound both ways")

    # 4. It is a mesh, not a point cloud.  The bug this rule exists for was a
    #    band whose trace had become a scatter3d, drawn as 360 fat markers.
    assert trace.type == "mesh3d", (
        f"{zone.name} is a {trace.type}, so it is drawn as points, not a disc")


def _check_figure(fig, system, key):
    by_name = {z.name: z for z in system.belt_zones}
    positions = system_positions_at(system, J2000)
    seen = 0
    for trace in fig.data:
        zone = by_name.get(getattr(trace, "name", None))
        if zone is None or trace.type != "mesh3d":
            continue
        verify_band_is_a_flat_disc(
            trace, zone, positions.get(zone.centre_body, (0.0, 0.0, 0.0)))
        seen += 1
    assert seen == len(by_name), f"{key}: checked {seen} of {len(by_name)}"


class TestEveryBuiltinDrawsFlatDiscs:
    @pytest.mark.parametrize("key", BUILTIN_NAMES)
    def test_the_zones_themselves(self, key):
        system = get_builtin_system(key, ALL_BANDS)
        positions = system_positions_at(system, J2000)
        checked = 0
        for zone in system.belt_zones:
            centre = positions.get(zone.centre_body, (0.0, 0.0, 0.0))
            verify_band_is_a_flat_disc(_belt_trace(zone, centre=centre),
                                       zone, centre)
            checked += 1
        assert checked, f"{key} drew no zones at all"

    @pytest.mark.parametrize("key", BUILTIN_NAMES)
    def test_the_static_figure(self, key):
        system = get_builtin_system(key, ALL_BANDS)
        paths, coils = system_orbit_paths(system, 360, J2000, J2000 + 365.25)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  paths, coil_paths=coils)
        _check_figure(fig, system, key)

    @pytest.mark.parametrize("key", BUILTIN_NAMES)
    def test_the_animated_figure_the_cli_opens(self, key):
        system = get_builtin_system(key, ALL_BANDS)
        paths, coils = system_orbit_paths(system, 360, J2000, J2000 + 365.25)
        times = np.linspace(J2000, J2000 + 365.25, 3)
        at_start = system_positions_at(system, J2000)
        series = {b.name: tuple(np.full(3, c, dtype=float)
                                for c in at_start[b.name])
                  for b in system.bodies}
        fig = build_animated_figure(system, series, paths, times,
                                    coil_paths=coils)
        _check_figure(fig, system, key)


class TestTheRuleWouldCatchARegression:
    """A check that cannot fail is not a check. These break it on purpose."""

    def _zone_and_trace(self):
        system = get_builtin_system("solar", ALL_BANDS)
        zone = next(z for z in system.belt_zones if z.is_solvent_band
                    and z.r_outer_au > 0)
        return zone, _belt_trace(zone)

    def test_a_band_with_thickness_is_rejected(self):
        zone, trace = self._zone_and_trace()
        z = np.asarray(trace.z, dtype=float).copy()
        z[0] += 0.01
        trace.z = z
        with pytest.raises(AssertionError):
            verify_band_is_a_flat_disc(trace, zone)

    def test_a_band_drawn_around_the_wrong_star_is_rejected(self):
        system = get_builtin_system("alpha-centauri", ALL_BANDS)
        zone = next(z for z in system.belt_zones
                    if z.centre_body == "Proxima Centauri" and z.r_outer_au > 0)
        trace = _belt_trace(zone, centre=(0.0, 0.0, 0.0))   # the primary's spot
        positions = system_positions_at(system, J2000)
        with pytest.raises(AssertionError):
            verify_band_is_a_flat_disc(trace, zone,
                                       positions["Proxima Centauri"])

    def test_a_band_that_became_a_point_cloud_is_rejected(self):
        # Exactly what the system switcher used to do to it.  Plotly's own
        # Mesh3d will not let its type be reassigned, so this stands in for the
        # retyped trace the viewer actually ended up holding.
        zone, trace = self._zone_and_trace()

        class Retyped:
            type = "scatter3d"
            x, y, z = trace.x, trace.y, trace.z
            i, j, k = trace.i, trace.j, trace.k

        with pytest.raises(AssertionError):
            verify_band_is_a_flat_disc(Retyped(), zone)
