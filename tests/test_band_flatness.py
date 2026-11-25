# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A solvent band's geometry must be a flat ring around its own star.

Flat always; round only where one star lights it.  With a companion close
enough to add its light the ring is the combined-flux outline
(`mechanics/combined_flux.py`) -- still one planar mesh on the star's own
plane, with the summed starlight at every edge vertex sitting exactly on the
band's hot or cold level.

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
from hybrasil.mechanics.combined_flux import NEGLIGIBLE_FLUX, combined_flux
from hybrasil.viz.static_plot import (_belt_trace, band_sources,
                                      build_static_figure, zone_outline)

ALL_BANDS = SolventChoice.parse("all")

# A band is planar to floating point, not approximately planar.
FLAT_TOL_AU = 1e-9


def verify_band_is_a_flat_disc(trace, zone, centre=(0.0, 0.0, 0.0),
                               sources=None):
    """Raise unless this trace's geometry is a flat ring around `centre`.

    The single place the rule is expressed, so a new figure builder, data
    source or system is one call away from being covered.

    `sources` is every band-bearing star as `(x, y, z, w)`, for a figure with
    more than one: the ring is then held to the summed starlight rather than
    to a circle.
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
    n = len(pts) // 2
    if sources is None or len(sources) < 2:
        assert radii.min() == pytest.approx(zone.r_inner_au, rel=1e-9)
        assert radii.max() == pytest.approx(zone.r_outer_au, rel=1e-9)
    else:
        # More than one star: the edges are where the *summed* flux reaches
        # the band's own two levels, so the ring is no smaller than the star's
        # own circle, and checked against the light rather than the solver.
        w = zone.luminosity_sun * zone.colour_factor
        s_hot, s_cold = w / zone.r_inner_au ** 2, w / zone.r_outer_au ** 2
        assert radii[:n].min() >= zone.r_inner_au * (1 - 1e-9)
        assert np.all(radii[n:] >= radii[:n])
        on_plane = in_plane + origin
        # A companion too faint and far to move an edge by a pixel is left
        # out of the solve, so "exactly" is to within what that leaves out.
        slack = 2 * NEGLIGIBLE_FLUX * s_cold
        for q in range(n):
            assert combined_flux(on_plane[q], sources) == pytest.approx(
                s_hot, rel=1e-6, abs=slack), (
                f"{zone.name}: inner vertex {q} is off the hot level")
            outer_flux = combined_flux(on_plane[n + q], sources)
            assert (outer_flux == pytest.approx(s_cold, rel=1e-6, abs=slack)
                    or outer_flux == pytest.approx(s_hot, rel=1e-6, abs=slack)), (
                f"{zone.name}: outer vertex {q} is on neither level")

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
    sources, _ = band_sources(system, positions)
    seen = 0
    for trace in fig.data:
        zone = by_name.get(getattr(trace, "name", None))
        if zone is None or trace.type != "mesh3d":
            continue
        verify_band_is_a_flat_disc(
            trace, zone, positions.get(zone.centre_body, (0.0, 0.0, 0.0)),
            sources if zone.is_solvent_band else None)
        seen += 1
    assert seen == len(by_name), f"{key}: checked {seen} of {len(by_name)}"


class TestEveryBuiltinDrawsFlatDiscs:
    @pytest.mark.parametrize("key", BUILTIN_NAMES)
    def test_the_zones_themselves(self, key):
        system = get_builtin_system(key, ALL_BANDS)
        positions = system_positions_at(system, J2000)
        sources, index = band_sources(system, positions)
        checked = 0
        for zone in system.belt_zones:
            centre = positions.get(zone.centre_body, (0.0, 0.0, 0.0))
            # On its own a zone is its star's circle...
            verify_band_is_a_flat_disc(_belt_trace(zone, centre=centre),
                                       zone, centre)
            # ...and with the system's other stars, the outline they bend it to.
            verify_band_is_a_flat_disc(
                _belt_trace(zone, centre=centre,
                            outline=zone_outline(zone, sources, index)),
                zone, centre, sources if zone.is_solvent_band else None)
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

    def test_a_band_that_ignores_its_companion_is_rejected(self):
        # Alpha Centauri A's outermost band reaches far enough for B to bend
        # it; drawn as A's own circle it is on neither flux level.
        system = get_builtin_system("alpha-centauri", ALL_BANDS)
        positions = system_positions_at(system, J2000)
        sources, index = band_sources(system, positions)
        bent = [z for z in system.belt_zones
                if zone_outline(z, sources, index) is not None
                and max(zone_outline(z, sources, index)[1]) > z.r_outer_au * 1.01]
        assert bent, "no band at Alpha Centauri is bent by a companion"
        zone = bent[0]
        centre = positions[zone.centre_body]
        with pytest.raises(AssertionError):
            verify_band_is_a_flat_disc(_belt_trace(zone, centre=centre),
                                       zone, centre, sources)
