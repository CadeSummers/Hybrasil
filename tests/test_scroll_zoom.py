# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Scroll zoom must keep the scene box following the camera.

WebGL clips everything nearer the eye than its near plane, and Plotly sets that
plane in *normalised* scene units -- a fixed fraction of the box.  If the box
stays large while the camera dollies in, the near plane ends up past the point
the camera is looking at, and everything on the camera's side of it is sliced
off along a flat cut through the middle of the view: every band a half-disc,
every orbit a half-ellipse.

The moon-system floor did exactly that.  It is `zoom_half_au`, which for the
Sun is 1,050 AU -- the Solar System has no 50x gap between Neptune, Pluto, Eris
and Planet Nine, so the Sun's "moon system" is the whole system -- and scrolling
toward the middle of the view pinned the box there while the camera went on in
to 5e-8 of it.  Verified in Chrome with the camera held 3 AU from the Sun: a
1,177 AU box cut the scene in half, an 18 AU box around the same camera did not.

These pin the fix and that the hazard is real.
"""

import json
import re

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.viz.export import _ZOOM_JS, build_body_info_js


def _wheel_js():
    i = _ZOOM_JS.find("function _applyWheelZoom(")
    assert i > 0
    return _ZOOM_JS[i:i + 12000]


def _body_info(key):
    js = build_body_info_js({key: get_builtin_system(key)})
    m = re.search(r"window\._SA_BODY_INFO\s*=\s*(\{.*\})\s*;", js, re.S)
    assert m, "could not find _SA_BODY_INFO in the emitted snippet"
    return json.loads(m.group(1))


class TestTheHazardIsReal:
    """Without this, the tests below would pass for the wrong reason."""

    def test_the_suns_floor_is_the_whole_system(self):
        # An uncapped floor this size pins the box at full-system scale for
        # anyone scrolling toward the middle of the view.
        info = _body_info("solar")
        assert info["Sun"]["zoom_half_au"] > 500.0

    def test_jupiters_floor_is_its_moon_system(self):
        # Which is the case the floor exists for, and must keep working.
        info = _body_info("solar")
        assert info["Jupiter"]["zoom_half_au"] < 0.1


class TestTheBoxFollowsTheCamera:
    def test_there_is_a_minimum_normalised_eye_distance(self):
        js = _wheel_js()
        assert "var MIN_EYE_NORM = 0.08;" in js
        assert "var safeHalf = newDistAU / MIN_EYE_NORM;" in js

    def test_the_box_is_clamped_to_what_the_camera_can_sit_in(self):
        # Applied after the sticky box, so neither can exceed it.
        js = _wheel_js()
        sticky = js.find("idealHalf = sceneHalf;")
        clamp = js.find("idealHalf = Math.min(idealHalf, safeHalf);")
        assert 0 < sticky < clamp

    def test_the_floor_cannot_raise_the_box_past_the_safe_limit(self):
        js = _wheel_js()
        assert "Math.min(nearest.info.zoom_half_au, safeHalf)" in js
        # The old, uncapped floor.
        assert "idealHalf = Math.max(idealHalf, centeredHalf)" not in js

    def test_the_snap_keeps_the_cameras_target_inside_the_box(self):
        # Judged against the box being built, not against zoom_half_au, which
        # put the Sun's snap radius at 525 AU.
        js = _wheel_js()
        assert "if (ndstAU < flooredHalf * 0.5)" in js
        assert "ndstAU < nearest.info.zoom_half_au * 0.5" not in js


class TestTheOtherCamerasAreAlreadySafe:
    """Only scroll zoom could dive; these place the eye at a fixed fraction."""

    def test_double_click_places_the_eye_well_clear(self):
        i = _ZOOM_JS.find("function zoomTo(")
        assert "eye:    { x: dx * 0.40,  y: dy * 0.40,  z: dz * 0.40  }" in \
            _ZOOM_JS[i:i + 4000]

    def test_orient_places_the_eye_at_the_default_distance(self):
        assert "var ORIENT_EYE_DIST = 2.1650635;" in _ZOOM_JS
