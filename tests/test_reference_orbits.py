# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reference orbits: Neptune's, Earth's and Mercury's orbit round every star, in the Even more features menu.

They ride on the layout meta like the photosynthesis rings, so they never add a Plotly trace or move a trace index
(CLAUDE.md's band rule); `tests/test_browser.py` switches them on in the viewer and checks every band stays flat.
"""
import numpy as np
import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.figures import build_figure
from hybrasil.mechanics.time_series import system_positions_at
from hybrasil.mechanics.units import J2000
from hybrasil.viz import reference_orbits as ro
from hybrasil.viz.photosynthesis_rings import ring_points
from hybrasil.viz.three_viewer import figure_to_scene

ALPHA_CEN = {"Alpha Centauri A", "Alpha Centauri B", "Proxima Centauri"}


def _fig(key, span=30):
    return build_figure(get_builtin_system(key), J2000, J2000 + span, frames=3)


def test_the_radii_and_colours_are_the_solar_systems_own():
    solar = get_builtin_system("solar")
    got = {p: (a, c) for p, a, c in ro.reference_planets()}
    assert list(got) == ["Neptune", "Earth", "Mercury"]
    for p, (a, c) in got.items():
        b = solar.get_body(p)
        assert (a, c) == (b.elements.semi_major_axis, b.color)
    assert got["Earth"][0] == pytest.approx(1.0) and got["Neptune"][0] == pytest.approx(30.07, abs=0.01)


def test_every_star_of_alpha_centauri_gets_each_planets_ring():
    specs = _fig("alpha-centauri").layout.meta[ro.META_KEY]
    for planet in ro.PLANETS:
        assert {s["star"] for s in specs if s["planet"] == planet} == ALPHA_CEN
    assert len(specs) == 3 * len(ALPHA_CEN)
    assert all(s["name"].endswith(f"({s['star']})") for s in specs)       # more than one star: named by it


def test_each_ring_is_a_flat_circle_round_its_own_star_in_its_band_plane():
    system = get_builtin_system("alpha-centauri")
    fig = build_figure(system, J2000, J2000 + 30, frames=3)
    pos = system_positions_at(system, J2000)
    for s in fig.layout.meta[ro.META_KEY]:
        pts = np.array(ring_points(s)).reshape(-1, 3)
        c, n = np.array(pos[s["star"]]), np.array(s["normal"])
        assert np.allclose(np.linalg.norm(pts - c, axis=1), s["radius_au"], rtol=1e-12)
        assert np.allclose((pts - c) @ n, 0, atol=1e-9 * max(1.0, s["radius_au"]))
        band = next(z for z in system.belt_zones if z.is_solvent_band and z.centre_body == s["star"])
        assert s["normal"] == pytest.approx(list(band.normal))


def test_every_star_gets_one_and_a_barycentre_none():
    castor = _fig("castor", span=400).layout.meta[ro.META_KEY]
    system = get_builtin_system("castor")
    stars = {b.name for b in system.bodies if b.body_type == "star"}
    assert {s["star"] for s in castor} == stars
    assert not {b.name for b in system.bodies if b.body_type == "barycentre"} & {s["star"] for s in castor}


def test_three_menu_features_off_by_default_and_no_plotly_trace():
    fig = _fig("solar")
    sets = [o for o in figure_to_scene(fig)["optionalSets"] if o["key"].startswith(ro.SET_PREFIX)]
    assert [(o["key"], o["label"], o["default"], o["menu"], o["count"]) for o in sets] == [
        ("reference-neptune", "Neptune reference orbit", False, "features", 1),
        ("reference-earth", "Earth reference orbit", False, "features", 1),
        ("reference-mercury", "Mercury reference orbit", False, "features", 1)]
    assert not any(ro.SET_PREFIX in str(t.meta) for t in fig.data)


def test_every_ring_is_a_dashed_optional_line_riding_its_star_with_a_reach():
    lines = [l for l in figure_to_scene(_fig("alpha-centauri"))["lines"]
             if (l.get("optional") or "").startswith(ro.SET_PREFIX)]
    assert len(lines) == 9
    assert all(l["owner"] == l["follows"] and l["dash"] == "dash" and not l["legend"] for l in lines)
    # One legend row per planet, whatever the star, named with its distance.
    assert {l["group"]: l["groupTitle"] for l in lines} == {
        "Neptune's orbit": "Neptune's orbit (30.1 AU)", "Earth's orbit": "Earth's orbit (1.00 AU)",
        "Mercury's orbit": "Mercury's orbit (0.39 AU)"}
    assert all(l["reach"] >= ro.reference_planets()[0][1] for l in lines if l["optional"] == "reference-neptune")
