# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The time spans the three.js viewer's Play menu offers (animation.time_spans).

One run of Play covers the figure's own window by default.  The menu beside the
button also offers one cycle of the shortest planet orbit, a year, the longest
planet orbit and, where a star's orbit is the longer, that too.  The spans are
declared here in Python and travel on the kepler meta; the browser half is in
tests/test_browser.py.
"""
import pytest

from hybrasil.data.loader import get_system
from hybrasil.figures import _NATURAL_SPANS, build_figure
from hybrasil.mechanics.units import J2000 as J2000_JD
from hybrasil.viz import animation
from hybrasil.viz.three_viewer import figure_to_scene


def _spans(key, default=365.25):
    return animation.time_spans(get_system("builtin", key), default)


def _keys(spans):
    return [s["key"] for s in spans]


def test_trappist_runs_from_b_to_h():
    spans = _spans("trappist-1", 30.0)
    assert _keys(spans) == ["default", "shortest", "year", "longest"]
    by = {s["key"]: s for s in spans}
    assert by["default"]["days"] == 30.0 and by["default"]["label"] == "Default: 30.0 d (as drawn)"
    assert by["shortest"]["body"] == "TRAPPIST-1b" and by["shortest"]["days"] == pytest.approx(1.51, abs=0.01)
    assert by["shortest"]["label"] == "Shortest planet orbit: TRAPPIST-1b (1.51 d)"
    assert by["year"] == {"key": "year", "days": 365.0, "label": "One Earth year (365 d)"}
    assert by["longest"]["body"] == "TRAPPIST-1h" and by["longest"]["label"].endswith("(18.8 d)")


def test_a_moon_never_sets_the_shortest_orbit():
    # The Solar System's fastest drawn orbit is a moon's; the span is Mercury's.
    system = get_system("builtin", "solar")
    moons = [b for b in system.bodies if b.body_type == "moon"]
    by = {s["key"]: s for s in _spans("solar")}
    assert moons and min(m.elements.period for m in moons) < by["shortest"]["days"]
    assert by["shortest"]["body"] == "Mercury"


def test_a_hypothetical_body_sets_a_span_only_where_no_confirmed_one_can():
    # Planet Nine is drawn, at 18,500 years; the Solar System's longest orbit is Eris's.
    by = {s["key"]: s for s in _spans("solar")}
    assert by["longest"]["body"] == "Eris" and "longest-star" not in by
    # Castor's one planet is a candidate, and it is all there is.
    assert {s["key"]: s for s in _spans("castor")}["shortest"]["label"].startswith("The planet's orbit: Castor Cc")


def test_a_longer_star_orbit_is_offered_beside_the_planets():
    spans = _spans("alpha-centauri")
    assert _keys(spans) == ["default", "shortest", "year", "longest", "longest-star"]
    star = spans[-1]
    # Alpha Centauri B, 79.9 years: not Proxima's hypothetical 550,000-year orbit.
    assert star["body"] == "Alpha Centauri B" and star["label"] == "Longest star orbit: Alpha Centauri B (79.9 yr)"
    assert star["days"] > spans[3]["days"]


def test_a_shorter_star_orbit_is_offered_too():
    # Castor's close pairs turn in under a day, far inside its brown dwarf's 54 years.
    spans = _spans("castor")
    assert _keys(spans) == ["default", "shortest-star", "shortest", "year", "longest-star"]
    assert spans[1]["days"] < 1 < spans[2]["days"]


def test_every_label_says_whose_orbit_it_is():
    for key in _NATURAL_SPANS:
        for s in _spans(key):
            if s["key"] in ("default", "year"):
                continue
            assert " orbit: " in s["label"] and s["body"] in s["label"], s
            assert ("planet" in s["label"]) != ("star" in s["label"].split(":")[0]), s


def test_durations_read_in_days_then_years():
    assert animation.span_text(1.5109) == "1.51 d"
    assert animation.span_text(18.77) == "18.8 d"
    assert animation.span_text(365.0) == "365 d"
    assert animation.span_text(79.91 * 365.25) == "79.9 yr"
    assert animation.span_text(13463 * 365.25) == "13,463 yr"


def test_the_spans_ride_the_kepler_meta_and_a_static_figure_has_none():
    system = get_system("builtin", "trappist-1")
    scene = figure_to_scene(build_figure(system, J2000_JD, J2000_JD + 30.0, frames=12))
    assert _keys(scene["kepler"]["spans"]) == ["default", "shortest", "year", "longest"]
    assert scene["kepler"]["spansHeading"] == animation.SPANS_HEADING
    assert "around a star" in animation.SPANS_HEADING
    static = figure_to_scene(build_figure(system, J2000_JD, J2000_JD + 30.0, mode="static"))
    assert not static["kepler"]


def test_a_coil_names_its_body():
    # The viewer re-samples a coil for another span, so each must say whose path it is.
    system = get_system("builtin", "alpha-centauri")
    scene = figure_to_scene(build_figure(system, J2000_JD, J2000_JD + 365.25 * 20, frames=12))
    coils = [ln for ln in scene["lines"] if ln.get("coil")]
    assert coils and all(ln["name"].startswith(ln["coil"] + " trajectory") for ln in coils)
    assert all(ln["coil"] in scene["kepler"]["bodies"] for ln in coils)
