# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Brightest Stars in the Night Sky: the 100 Brightest Stars tab as a view of stars in motion.

The same figure as Nearby Stellar Motion through a `MotionView` of its own
(docs/architecture/star-motion.md).  Everything here runs on the committed snapshot, which
tests/conftest.py makes the source; tests/test_star_motion.py is what holds the nearby view still.
"""

import math

import pytest

from hybrasil.data.brightest_loader import load_brightest
from hybrasil.views import FEATURED_VIEWS, LISTED_VIEWS, build_view, system_kind
from hybrasil.viz import brightest_stars as bs
from hybrasil.viz import star_motion as sm
from hybrasil.viz.three_viewer import figure_to_scene

pytest.importorskip("openpyxl")

KEY = "brightest-star-motion"


@pytest.fixture(scope="module")
def stars():
    return load_brightest()


@pytest.fixture(scope="module")
def built():
    fig, info = build_view(KEY)
    return fig, info, figure_to_scene(fig)


def _body(scene, name):
    return next(b for b in scene["bodies"] if b["name"] == name)


# ── registration ────────────────────────────────────────────────────────────

def test_it_is_a_listed_view_not_a_featured_one():
    assert KEY in LISTED_VIEWS and KEY not in FEATURED_VIEWS
    assert LISTED_VIEWS[KEY][0] == bs.VIEW_NAME == "Brightest Stars in the Night Sky"
    assert system_kind(KEY) == "motion"


def test_the_web_app_lists_it_under_stellar_motion_between_nearby_and_sgr_a(stars):
    from tests.test_web_app import _library
    index = _library().index()
    entry = next(e for e in index if e["id"] == KEY)
    assert not entry["featured"] and entry["view"] and entry["kind"] == "motion"
    assert entry["n_stars"] == len(stars) == 100 and "brightest stars" in entry["aliases"]
    assert [e["id"] for e in index if e["kind"] == "motion"] == ["nearby-star-motion", KEY, "galactic:sgr-a"]
    # The dropdown's own order: more stars first, so it is listed before the S-stars.
    sgr = next(e for e in index if e["id"] == "galactic:sgr-a")
    assert entry["n_stars"] > sgr["n_stars"]


def test_it_is_switched_off_with_the_catalog():
    from tests.test_web_app import _library
    assert KEY not in [e["id"] for e in _library(use_catalog=False).index()]


def test_the_web_app_serves_it_as_it_serves_the_nearby_view():
    from tests.test_web_app import _library
    p = _library().scene(KEY)
    assert p["name"] == bs.VIEW_NAME and p["scene"]["units"] == "ly"
    # The index entry is marked a view, which is what keeps these panels with this scene in the viewer.
    assert "alf CMa" in p["body_info"] and "Solar System" in p["body_info"]


# ── the scene ───────────────────────────────────────────────────────────────

def test_the_scene_reaches_the_most_distant_star_and_the_title_says_so(built, stars):
    _, _, scene = built
    far = max(stars, key=lambda s: s.distance_ly)
    assert far.name == "alf Cyg"
    assert scene["half"] == pytest.approx(far.distance_ly * bs.MARGIN)
    assert scene["units"] == "ly"
    assert f"100 stars, out to {far.distance_ly:,.0f} ly (Deneb)" in scene["title"]
    assert "snapshot" in scene["title"]


def test_every_star_is_drawn_with_the_sun_at_the_origin(built, stars):
    _, _, scene = built
    assert len(scene["bodies"]) == len(stars) + 1
    assert _body(scene, sm.SUN_NAME)["pos"] == [0.0, 0.0, 0.0]
    for s in stars:
        assert math.dist(_body(scene, s.name)["pos"], [0, 0, 0]) == pytest.approx(s.distance_ly)


def test_every_star_has_an_arrow_in_each_frame_and_drifts_along_it(built, stars):
    _, _, scene = built
    for frame in (sm.FRAME_SUN, sm.FRAME_LSR):
        owners = {l["owner"] for l in scene["lines"] if l.get("frame") == frame}
        assert {s.name for s in stars} <= owners
    assert (sm.SUN_NAME in {l["owner"] for l in scene["lines"] if l.get("frame") == sm.FRAME_LSR})
    sirius = _body(scene, "alf CMa")
    arrow = next(l for l in scene["lines"] if l.get("owner") == "alf CMa" and l["frame"] == sm.FRAME_SUN)
    tip = [arrow["pts"][3 + i] - arrow["pts"][i] for i in range(3)]
    assert tip == pytest.approx(sirius["drift"][sm.FRAME_SUN], abs=1e-3)
    assert scene["drift"]["years"] == sm.ARROW_YEARS


def test_a_star_is_sized_by_apparent_brightness_and_carries_its_luminosity_size(built, stars):
    _, _, scene = built
    by_rank = sorted(stars, key=lambda s: s.rank_apparent)
    sizes = [_body(scene, s.name)["size"] for s in by_rank]
    assert sizes[0] == max(sizes) == pytest.approx(13.0) and sizes[-1] == pytest.approx(min(sizes), abs=0.5)
    # Brighter looks bigger: no star is drawn larger than one that outshines it by half a magnitude.
    for a, b in zip(by_rank, by_rank[1:]):
        assert bs.apparent_size(a.apparent_mag) >= bs.apparent_size(b.apparent_mag) - 1e-9
    # By luminosity the order is another one altogether: Sirius is among the smallest, Naos the largest.
    alt = {s.name: _body(scene, s.name)["altSize"] for s in stars}
    assert alt["zet Pup"] == max(alt.values()) and alt["alf CMa"] < alt["alf Cyg"]
    assert "altSize" not in _body(scene, sm.SUN_NAME)
    assert scene["altSize"] == {"set": bs.SIZE_SET}


def test_the_luminosity_scale_tells_these_stars_apart_where_the_nearby_one_cannot(stars):
    lum = [bs.luminosity(s) for s in stars]
    assert sum(sm.marker_size(x) == 14.0 for x in lum) > 30          # the nearby scale: clamped
    assert sum(bs.luminosity_size(x) == 14.0 for x in lum) <= 1


def test_each_star_carries_its_three_ranks_as_tags(built, stars):
    _, _, scene = built
    for s in stars:
        assert _body(scene, s.name)["tags"] == {"apparent": str(s.rank_apparent),
                                                "bolometric": str(s.rank_bolometric),
                                                "visual": str(s.rank_visual)}
    assert _body(scene, "alf CMa")["tags"] == {"apparent": "1", "bolometric": "93", "visual": "94"}
    assert scene["tags"] == {"set": bs.TAG_SET, "prefix": "#"}


def test_the_three_switches_are_rows_of_the_even_more_features_menu(built):
    _, _, scene = built
    sets = {o["key"]: o for o in scene["optionalSets"]}
    assert list(sets) == [bs.SIZE_SET, bs.TAG_SET, bs.COMPRESS_SET]
    assert all(o["menu"] == "features" and o["default"] is False for o in sets.values())
    assert [m["key"] for m in sets[bs.TAG_SET]["modes"]] == ["apparent", "bolometric", "visual"]
    assert scene["compress"] == {"set": bs.COMPRESS_SET, "r0": bs.COMPRESS_R0_LY}
    assert not scene["clouds"]              # the viewer does not compress a cloud


def test_the_100_ly_sphere_is_three_great_circles_and_the_shells_wait_for_compression(built):
    _, _, scene = built
    sphere = next(l for l in scene["lines"] if l["name"] == "100 ly from the Sun")
    pts = [sphere["pts"][i:i + 3] for i in range(0, len(sphere["pts"]), 3)]
    assert all(math.hypot(*p) == pytest.approx(100.0) for p in pts)
    for axis in range(3):                   # one circle in each of the three planes
        assert sum(abs(p[axis]) < 1e-9 for p in pts) > 60
    assert sphere["legend"] and sphere["label"] == "100 ly" and not sphere.get("compressOnly")
    shells = [l for l in scene["lines"] if l.get("compressOnly")]
    assert [l["label"] for l in shells] == ["10 ly", "1,000 ly"] and not any(l["legend"] for l in shells)


def test_the_reference_axes_stop_short_of_the_scene_edge(built):
    _, _, scene = built
    axis = next(l for l in scene["lines"] if l["name"] == "Galactic Center")
    assert axis["pts"][3] == pytest.approx(scene["half"] * bs.REFERENCE_FRACTION)


def test_stars_are_grouped_by_spectral_class(built):
    _, _, scene = built
    assert scene["groupHeading"] == "Stars by spectral class"
    assert _body(scene, "alf CMa")["group"] == "A-type" and _body(scene, "alf Ori")["group"] == "M-type"


# ── the panels ──────────────────────────────────────────────────────────────

def test_a_panel_gives_the_ranks_the_magnitudes_and_where_else_the_star_is(built):
    _, info, _ = built
    rows = {r[0]: r for r in info["alf CMa"]["rows"]}
    assert rows["Apparent brightness rank"][1] == "1 of 100"
    assert rows["Apparent magnitude (V)"][1] == "-1.44"
    assert rows["Absolute magnitude (M_V)"][1] == "+1.45"
    assert rows["Luminosity rank (all light)"][1] == "93 of 100"
    assert rows["Luminosity rank (visible light)"][1] == "94 of 100"
    assert rows["Designation, constellation"][1] == "alf CMa A, CMa"
    assert rows["Distance"][1].startswith("8.60 ± 0.04 ly") and "Hipparcos" in rows["Distance"][2]
    assert rows["Variability"][1] == "not variable"
    assert rows["Also on tabs"][1] == "Known: GJ 244 A, GJ 244 B"
    assert "Planets" not in rows and "Stellar partners" not in rows
    assert "alf CMa B" in rows["Stars of this point of light"][1]
    assert "Sirius" in info["alf CMa"]["aka"]
    # The standard rows are all still there: the motion, in both frames.
    assert {"Speed", "Speed (LSR)", "Radial velocity", "Proper motion"} <= set(rows)


def test_the_most_distant_star_states_its_uncertainty_and_frames_wider(built):
    _, info, _ = built
    rows = {r[0]: r for r in info["alf Cyg"]["rows"]}
    assert rows["Distance"][1].startswith("2,616.00 ± 215 ly")
    assert rows["Luminosity rank (visible light)"][1] == "1 of 100"
    assert info["alf Cyg"]["zoom_half"] > info["alf CMa"]["zoom_half"] == 4.0


def test_go_to_system_opens_the_system_another_tab_draws_and_nothing_else(built, stars):
    _, info, _ = built
    assert info["alf Cen"]["goto"] == "alpha-centauri"         # Systems: alf Cen A, the featured system
    assert info["alf Gem"]["goto"] == "castor"                  # Planetless 4+ Stars, featured
    assert info["alf Aur"]["goto"] == "planetless:alf Aur"
    assert info["bet Gem"]["goto"] == "catalog:HD 62509"        # Pollux, under the Systems tab's name
    assert info[sm.SUN_NAME]["goto"] == "solar"
    assert "goto" not in info["alf CMa"] and "goto_note" not in info["alf CMa"]
    # Every id it names is one the web app can open.
    from hybrasil.data.catalog_loader import parse_workbook
    from hybrasil.data.snapshot import load_snapshot_workbook
    from tests.test_web_app import _library
    cat = parse_workbook(load_snapshot_workbook())
    ids = {e["id"] for e in _library(catalog_loader=lambda: cat).index()}
    gotos = {e["goto"] for e in info.values() if e.get("goto")}
    assert len(gotos) == 9 and gotos <= ids


def test_the_sun_keeps_its_own_panel(built):
    _, info, _ = built
    labels = [r[0] for r in info[sm.SUN_NAME]["rows"]]
    assert "Position" in labels and "Apparent brightness rank" not in labels


# ── the nearby view is what it was ──────────────────────────────────────────

def test_the_default_config_is_the_nearby_views():
    c = sm.NEARBY
    assert (c.key, c.name, c.half_ly, c.reference_ly) == (sm.VIEW_KEY, sm.VIEW_NAME, 110.0, 90.0)
    star = sm.NearbyStar(name="x", luminosity_sun=100.0)
    assert c.size(star) == sm.marker_size(100.0) and c.zoom_half(star) == 4.0


def test_the_nearby_scene_declares_none_of_the_new_switches():
    scene = figure_to_scene(build_view("nearby-star-motion")[0])
    assert scene["compress"] is None and scene["tags"] is None and scene["altSize"] is None
    assert not any("altSize" in b or "tags" in b for b in scene["bodies"])
    assert not any(l.get("compressOnly") for l in scene["lines"])
    assert scene["half"] == 110.0
