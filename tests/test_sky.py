# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Milky Way behind the three.js viewer, and the rotation that places it.

The sky is an all-sky map in galactic coordinates; each system carries the
rotation from galactic coordinates into its own frame.  What matters is that
the galactic-centre arrow points at the galactic centre in the picture, so
the rotation is checked against the arrow itself, for every built-in, and
against published coordinates it did not come from.
"""

import json
import math
import struct
import threading
import urllib.request

import pytest

from hybrasil.data.builtin_systems import BUILTIN_NAMES, get_builtin_system
from hybrasil.figures import build_figure
from hybrasil.mechanics.orientation import (EQUATORIAL_TO_GALACTIC,
                                                 equatorial_unit, galactic_to_frame)
from hybrasil.mechanics.solvent_bands import SolventChoice
from hybrasil.mechanics.units import J2000
from hybrasil.viz import three_viewer
from hybrasil.viz.static_plot import _GC_DIR, sky_meta

BANDS = SolventChoice.parse("all")


def _angle_deg(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / (na * nb)))))


def _column(m, i):
    return [row[i] for row in m]


# ── The rotation ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("radec", [None, (346.6225, -5.04139), (219.902, -60.834),
                                   (24.199, 41.405), (0.0, 89.9), (180.0, -89.9)])
def test_galactic_to_frame_is_a_proper_rotation(radec):
    m = galactic_to_frame(radec)
    for i in range(3):
        for j in range(3):
            dot = sum(m[i][k] * m[j][k] for k in range(3))
            assert dot == pytest.approx(1.0 if i == j else 0.0, abs=1e-12)
    det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
           - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
           + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    # +1: a rotation.  -1 would draw the sky mirrored, every constellation
    # backwards, while the arrow still hit the centre.
    assert det == pytest.approx(1.0, abs=1e-12)


def test_the_galactic_axes_are_where_published_coordinates_put_them():
    # Independent of the matrix: the galactic centre (l = b = 0) is at RA
    # 266.405, Dec -28.936 and the north galactic pole at RA 192.859,
    # Dec 27.128 (ICRS; Hipparcos definition).
    centre = equatorial_unit(266.40499, -28.93617)
    pole = equatorial_unit(192.85948, 27.12825)
    assert _angle_deg(EQUATORIAL_TO_GALACTIC[0], centre) < 1e-4
    assert _angle_deg(EQUATORIAL_TO_GALACTIC[2], pole) < 1e-4


def test_the_north_galactic_pole_sits_at_its_ecliptic_latitude():
    # beta = +29.81 deg, which the obliquity and the galactic matrix have to
    # reproduce between them.
    pole = _column(galactic_to_frame(None), 2)
    assert math.degrees(math.asin(pole[2])) == pytest.approx(29.81, abs=0.01)


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_the_sky_centre_is_where_the_arrow_points(key):
    system = get_builtin_system(key, BANDS)
    arrow = system.galactic_center_direction or _GC_DIR
    centre = _column(galactic_to_frame(system.sky_frame_radec), 0)
    # The arrow aims at Sgr A*, 0.07 deg from l = b = 0, and from the star
    # rather than the Sun: 0.12 deg at most among the built-ins.
    assert _angle_deg(arrow, centre) < 0.2


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_a_system_with_its_own_arrow_has_its_own_sky(key):
    # The two are one decision: a sky-frame arrow with an ecliptic sky would
    # put the galactic centre somewhere the arrow does not point.
    system = get_builtin_system(key, BANDS)
    assert (system.galactic_center_direction is None) == (system.sky_frame_radec is None)


# ── Carried to the viewer ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def alpha_cen_figure():
    system = get_builtin_system("alpha-centauri", BANDS)
    return system, build_figure(system, J2000, J2000 + 30, frames=4)


def test_the_figure_carries_the_rotation(alpha_cen_figure):
    system, fig = alpha_cen_figure
    _carries_the_sky(fig, system)
    assert sky_meta(system)["sky"]["galactic_to_frame"] == [
        list(r) for r in galactic_to_frame(system.sky_frame_radec)]


def test_a_static_figure_carries_it_too():
    system = get_builtin_system("trappist-1", BANDS)
    fig = build_figure(system, J2000, J2000 + 10, mode="static")
    _carries_the_sky(fig, system)


def _carries_the_sky(fig, system):
    # The layout meta also carries the photosynthesis rings, the reference
    # orbits and their optional sets (viz/photosynthesis_rings.py,
    # viz/reference_orbits.py) and, on an animated figure, the bodies'
    # elements (animation.kepler_meta); everything else in it is sky_meta's.
    from hybrasil.viz import photosynthesis_rings as pr
    from hybrasil.viz import reference_orbits as ro
    meta = dict(fig.layout.meta)
    assert set(meta) - set(sky_meta(system)) <= {pr.META_KEY, ro.META_KEY, "optional_sets", "kepler"}
    meta.pop(pr.META_KEY, None)
    meta.pop(ro.META_KEY, None)
    meta.pop("optional_sets", None)
    meta.pop("kepler", None)
    assert meta == sky_meta(system)


def test_the_scene_carries_the_rotation(alpha_cen_figure):
    system, fig = alpha_cen_figure
    scene = three_viewer.figure_to_scene(fig)
    assert scene["sky"] == sky_meta(system)["sky"]
    json.dumps(scene["sky"])


def test_a_standalone_page_embeds_the_small_sky(alpha_cen_figure):
    _, fig = alpha_cen_figure
    html = three_viewer.build_html({"alpha-centauri": fig}, "alpha-centauri")
    assert 'window.SA3_SKY     = "data:image/jpeg;base64,' in html
    small = (three_viewer.SKY_DIR / three_viewer.SKY_EMBED_FILE).stat().st_size
    big = (three_viewer.SKY_DIR / three_viewer.SKY_FILE).stat().st_size
    assert small < big
    assert len(html) < 4 * small + 2_000_000       # the 2k image, not the 4k


def test_the_app_page_points_at_the_served_sky():
    html = three_viewer.build_app_html("solar")
    assert f'window.SA3_SKY     = "{three_viewer.SKY_URL}"' in html
    assert "base64" not in html


# ── The image files ──────────────────────────────────────────────────────────

def _jpeg_size(path):
    """(width, height) from a JPEG's start-of-frame marker, no image library."""
    data = path.read_bytes()
    assert data[:2] == b"\xff\xd8"
    i = 2
    while i < len(data):
        marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xC3:
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + length
    raise AssertionError("no start-of-frame marker")


@pytest.mark.parametrize("name,size", [("milky_way_4k.jpg", (4096, 2048)),
                                       ("milky_way_2k.jpg", (2048, 1024))])
def test_the_sky_images_are_whole_equirectangular_maps(name, size):
    # 2:1 is what an equirectangular map of the whole sky has to be.
    assert _jpeg_size(three_viewer.SKY_DIR / name) == size


def test_the_credit_travels_with_the_images():
    readme = (three_viewer.SKY_DIR / "README.md").read_text(encoding="utf-8")
    assert "NASA/Goddard Space Flight Center Scientific" in readme
    assert "ESA/Gaia/DPAC" in readme
    js = three_viewer._JS_PATH.read_text(encoding="utf-8")
    assert "Deep Star Maps 2020" in js and "ESA/Gaia/DPAC" in js


# ── Served by the web app ────────────────────────────────────────────────────

def test_the_web_app_serves_the_sky():
    from hybrasil.web.app import make_server
    from tests.test_web_app import _library

    srv = make_server(_library(), "solar", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}{three_viewer.SKY_URL}"
        with urllib.request.urlopen(url) as r:
            body = r.read()
            assert r.status == 200
            assert r.headers["Content-Type"] == "image/jpeg"
        assert body == (three_viewer.SKY_DIR / three_viewer.SKY_FILE).read_bytes()
    finally:
        srv.shutdown()
        srv.server_close()
