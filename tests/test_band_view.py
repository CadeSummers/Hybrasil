# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the camera that looks at a solvent band, and the box around it.

A band is built in the plane its star's planets orbit in, and that plane is the
plane of the sky for every system whose angles come from transits or
astrometry.  A camera pointed down world z therefore sees a transiting
system's band edge-on: TRAPPIST-1 at 89.76 degrees drew eight bands as eight
lines, which is the geometry being right and the view being wrong.

These pin the view following the plane, the scene box no longer being inflated
by a floor meant for a different case, and the two systems that must not move.
"""

import math
from dataclasses import replace

import numpy as np
import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.mechanics.orientation import (
    Z_AXIS,
    camera_for_plane,
    face_on_camera,
    plane_tilt_deg,
    rotate_from_z,
)
from hybrasil.mechanics.solvent_bands import SolventChoice
from hybrasil.mechanics.time_series import compute_scene_extent
from hybrasil.viz import themes
from hybrasil.viz.export import _fig_view_normal
from hybrasil.viz.static_plot import (belt_scene_extent,
                                           build_static_figure,
                                           system_view_normal)
from hybrasil.mechanics.time_series import (system_orbit_paths,
                                                 system_positions_at)
from hybrasil.mechanics.units import J2000


class TestTheSceneFloor:
    def test_a_system_with_orbits_is_not_inflated_to_1_au(self):
        # TRAPPIST-1 spans 0.068 AU.  The old floor drew it in a 1.1 AU box,
        # so everything in it was a sixteenth of the frame.
        paths = {"b": (np.array([0.06, -0.06]), np.array([0.0, 0.0]),
                       np.array([0.0, 0.0]))}
        half = compute_scene_extent(paths)[0]
        assert half == pytest.approx(0.06 * 1.1)

    def test_a_system_with_nothing_to_measure_still_renders(self):
        # The floor's actual purpose: a lone star with no orbit and no band.
        assert compute_scene_extent({})[0] == pytest.approx(1.1)

    def test_a_band_still_raises_the_floor(self):
        paths = {"b": (np.array([0.01]), np.array([0.0]), np.array([0.0]))}
        assert compute_scene_extent(paths, min_extent_au=0.5)[0] == \
            pytest.approx(0.55)

    def test_trappist_1_is_sized_by_its_outermost_planet(self):
        system = get_builtin_system("trappist-1")
        paths, coils = system_orbit_paths(system, 360, J2000, J2000 + 30.0)
        half = compute_scene_extent({**paths, **coils},
                                    min_extent_au=belt_scene_extent(system))[0]
        assert half < 0.1, "TRAPPIST-1 fits in a tenth of an AU"
        band = max(z.r_outer_au for z in system.belt_zones if z.is_solvent_band)
        assert band / half > 0.25, "the band should fill a quarter of the frame"


class TestTheCameraFollowsThePlane:
    @pytest.mark.parametrize("normal", [
        Z_AXIS, (0.026, 0.008, 0.9996), (0.0, -1.0, 0.004),
        (-0.413, 0.891, 0.187), (0.0, 0.0, -1.0),
    ])
    def test_the_view_angle_to_the_plane_is_the_same_for_every_plane(self, normal):
        # The camera is rotated into the band's plane, not tilted relative to
        # it: every system opens on the same three-quarter view of its own
        # band, which is the whole point.
        eye, up = camera_for_plane(normal)
        eye = np.asarray(eye) / np.linalg.norm(eye)
        assert float(np.dot(eye, up)) == pytest.approx(
            1.25 / math.sqrt(3 * 1.25 ** 2), abs=1e-9)

    def test_up_is_the_plane_normal(self):
        _, up = camera_for_plane((0.0, -1.0, 0.004))
        assert np.linalg.norm(up) == pytest.approx(1.0)
        assert plane_tilt_deg(up) == pytest.approx(89.76, abs=0.02)

    def test_a_flat_plane_leaves_the_camera_exactly_alone(self):
        eye, up = camera_for_plane(Z_AXIS)
        assert eye == pytest.approx(themes.DEFAULT_EYE)
        assert up == pytest.approx(Z_AXIS)

    @pytest.mark.parametrize("normal", [
        Z_AXIS, (0.0, -1.0, 0.004), (-0.413, 0.891, 0.187),
    ])
    def test_a_face_on_camera_has_a_usable_up(self, normal):
        # An `up` parallel to the view direction is degenerate, and Plotly
        # renders it as an empty scene.
        eye, up = face_on_camera(normal, 2.165)
        assert float(np.dot(eye, up)) == pytest.approx(0.0, abs=1e-12)
        assert np.linalg.norm(up) == pytest.approx(1.0)

    def test_rotating_z_gives_back_the_normal(self):
        for normal in [(0.0, -1.0, 0.004), (-0.413, 0.891, 0.187), Z_AXIS]:
            got = rotate_from_z(normal, Z_AXIS)
            unit = np.asarray(normal) / np.linalg.norm(normal)
            assert np.allclose(got, unit, atol=1e-12)


class TestTheFigureCarriesIt:
    def test_the_view_normal_is_read_off_the_band(self):
        # Not derived a second time: the camera and the ring it is pointed at
        # cannot drift apart if there is only one source for the plane.
        system = get_builtin_system("trappist-1")
        band = next(z for z in system.belt_zones if z.is_solvent_band)
        assert system_view_normal(system) == band.normal

    def test_a_system_with_no_band_looks_down_z(self):
        # A copy: get_builtin_system caches, and stripping the bands off the
        # cached object would leave every later test looking at a system with
        # no band in it.
        system = replace(get_builtin_system("solar"),
                         belt_zones=[z for z in get_builtin_system("solar").belt_zones
                                     if not z.is_solvent_band])
        assert system_view_normal(system) == Z_AXIS

    def test_band_plane_reference_puts_the_camera_back_on_z(self):
        flat = SolventChoice.parse("water", align_to_orbits=False)
        system = get_builtin_system("trappist-1", flat)
        assert plane_tilt_deg(system_view_normal(system)) == pytest.approx(0.0)

    @pytest.mark.parametrize("key,tilt", [
        ("solar", 1.58), ("trappist-1", 89.76), ("proxima-centauri", 0.0),
    ])
    def test_the_built_figure_carries_the_plane_its_bands_are_in(self, key, tilt):
        system = get_builtin_system(key)
        paths, coils = system_orbit_paths(system, 360, J2000, J2000 + 365.25)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  paths, coil_paths=coils)
        assert plane_tilt_deg(_fig_view_normal(fig)) == pytest.approx(tilt, abs=0.02)

    def test_trappist_1s_camera_is_not_in_its_band_plane(self):
        # The bug, stated as a test: a camera in the plane of a disc sees a
        # line.  The dot product of the view direction with the normal is how
        # much of the disc's face is turned toward the viewer.
        system = get_builtin_system("trappist-1")
        paths, coils = system_orbit_paths(system, 360, J2000, J2000 + 30.0)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  paths, coil_paths=coils)
        eye = fig.layout.scene.camera.eye
        view = np.array([eye.x, eye.y, eye.z])
        view /= np.linalg.norm(view)
        normal = np.asarray(_fig_view_normal(fig))
        assert abs(float(np.dot(view, normal))) > 0.5, \
            "the band must be turned toward the camera, not edge-on to it"


class TestTheViewerGetsTheNormal:
    """The switcher swaps systems in place, so the plane has to travel too."""

    def test_the_single_figure_snippet_carries_a_normal(self):
        from hybrasil.viz.export import _build_scene_ranges_js
        system = get_builtin_system("trappist-1")
        paths, coils = system_orbit_paths(system, 360, J2000, J2000 + 30.0)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  paths, coil_paths=coils)
        js = _build_scene_ranges_js(fig)
        assert "window._SA_VIEW_NORMAL" in js

    def test_every_system_in_the_switcher_brings_its_own_plane(self):
        from hybrasil.viz.export import _build_multi_scene_ranges_js
        figures = {}
        for key in ("solar", "trappist-1"):
            system = get_builtin_system(key)
            paths, coils = system_orbit_paths(system, 360, J2000, J2000 + 30.0)
            figures[key] = build_static_figure(
                system, system_positions_at(system, J2000), paths,
                coil_paths=coils)
        js = _build_multi_scene_ranges_js(figures, "solar")
        assert "_SA_ALL_VIEW_NORMALS" in js
        for key in figures:
            assert f'"{key}"' in js

    def test_orient_no_longer_hardcodes_an_eye_on_the_z_axis(self):
        from hybrasil.viz.export import _ZOOM_JS
        assert "_SA_VIEW_NORMAL" in _ZOOM_JS
        assert "_viewNormal()" in _ZOOM_JS
        # The old camera: 100 AU up the z axis, whatever the system's scale.
        assert "(100 - zMid)" not in _ZOOM_JS
