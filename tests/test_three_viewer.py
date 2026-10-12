# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The three.js renderer draws exactly what the Plotly figure holds.

The scene is converted from the Plotly figure rather than built a second time,
which is what makes a band a flat disc in both renderers for the same reason:
it is the same mesh.  These pin that the conversion loses nothing -- every
band vertex and face, every body, every orbit, every frame.
"""

import json
import re

import numpy as np
import pytest

from hybrasil.cli import _NATURAL_SPANS, build_parser
from hybrasil.data.builtin_systems import BUILTIN_NAMES, get_builtin_system
from hybrasil.mechanics.time_series import (
    system_orbit_paths,
    system_time_series,
)
from hybrasil.mechanics.units import J2000
from hybrasil.viz.animation import build_animated_figure
from hybrasil.viz.three_viewer import (
    THREE_VERSION,
    build_html,
    figure_to_scene,
)


def _figure(key, frames=12):
    system = get_builtin_system(key)
    t1 = J2000 + _NATURAL_SPANS.get(key, 365.25)
    orbits, coils = system_orbit_paths(system, t_start=J2000, t_end=t1)
    times, ts = system_time_series(system, J2000, t1, frames)
    return build_animated_figure(system=system, time_series=ts, orbit_paths=orbits,
                                 times_jd=times, coil_paths=coils)


@pytest.fixture(scope="module", params=BUILTIN_NAMES)
def converted(request):
    fig = _figure(request.param)
    return request.param, fig, figure_to_scene(fig)


class TestNothingIsLost:
    def test_every_band_keeps_its_vertices_and_faces(self, converted):
        key, fig, scene = converted
        meshes = [t for t in fig.data if t.type == "mesh3d"]
        assert len(scene["bands"]) == len(meshes)
        for t, b in zip(meshes, scene["bands"]):
            xyz = np.column_stack([t.x, t.y, t.z]).ravel() if len(t.x) else []
            ijk = np.column_stack([t.i, t.j, t.k]).ravel() if len(t.i) else []
            assert b["pos"] == pytest.approx(list(xyz), abs=0, rel=0), t.name
            assert b["index"] == list(map(float, ijk)), t.name

    def test_every_band_is_still_planar(self, converted):
        # The geometric half of verify_band_is_a_flat_disc(), on the converted
        # data: the renderer gets a disc because the data is a disc.
        key, _, scene = converted
        for b in scene["bands"]:
            if not b["pos"]:
                continue
            p = np.asarray(b["pos"]).reshape(-1, 3)
            centred = p - p.mean(axis=0)
            normal = np.linalg.svd(centred)[2][-1]
            assert np.abs(centred @ normal).max() < 1e-9, b["name"]

    def test_every_marker_is_a_body(self, converted):
        key, fig, scene = converted
        markers = [t.name for t in fig.data if t.type == "scatter3d"
                   and t.mode and "markers" in t.mode and len(t.x) == 1]
        assert [b["name"] for b in scene["bodies"]] == markers

    def test_every_orbit_and_coil_is_a_line(self, converted):
        key, fig, scene = converted
        lines = [t.name for t in fig.data if t.type == "scatter3d"
                 and t.mode and "lines" in t.mode and len(t.x) > 1]
        # The photosynthesis rings are scene lines with no trace behind them
        # (they ride on the layout meta), so they are left out here.
        assert [l["name"] for l in scene["lines"] if not l.get("optional")] == lines

    def test_frames_move_every_body(self, converted):
        key, fig, scene = converted
        frames = scene["frames"]["positions"]
        assert len(frames) == len(fig.frames)
        assert all(len(f) == 3 * len(scene["bodies"]) for f in frames)
        assert len(scene["frames"]["labels"]) == len(frames)


class TestThePage:
    def test_three_is_pinned(self):
        html = build_html({"trappist-1": _figure("trappist-1", 3)}, "trappist-1")
        m = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
        imports = json.loads(m.group(1))["imports"]
        assert imports["three"].endswith(f"three@{THREE_VERSION}/build/three.module.js")

    def test_the_depth_buffer_is_logarithmic(self):
        # The one setting this renderer exists for.
        html = build_html({"trappist-1": _figure("trappist-1", 3)}, "trappist-1")
        assert "logarithmicDepthBuffer: true" in html

    def test_script_data_cannot_close_its_own_tag(self):
        html = build_html({"trappist-1": _figure("trappist-1", 3)}, "trappist-1")
        data = html.split("window.SA3_SYSTEMS = ", 1)[1].split(";\n", 1)[0]
        assert "</" not in data


class TestTheSwitch:
    def _renderer(self, *argv):
        from hybrasil.cli import _renderer
        return _renderer(build_parser().parse_args(list(argv)))

    def test_three_is_the_default(self):
        assert self._renderer() == "three"
        assert self._renderer("--output", "html") == "three"

    def test_plotly_can_be_chosen(self):
        assert self._renderer("--renderer", "plotly") == "plotly"

    def test_a_png_uses_plotly_unless_told_otherwise(self):
        # three.js cannot write a PNG; kaleido renders the Plotly figure.
        assert self._renderer("--output", "png") == "plotly"
        assert self._renderer("--output", "png", "--renderer", "three") == "three"


class TestTheSharedKit:
    """The sliders, search ranking and info panel come from band_kit.js."""

    def test_every_solvent_band_ships_what_the_sliders_need(self, converted):
        key, fig, scene = converted
        for b in scene["bands"]:
            if not b["solvent"]:
                assert b["meta"] is None
                continue
            for field in ("solvent", "lum", "normal", "centre", "ceiling", "colour"):
                assert field in b["meta"], (b["name"], field)

    def test_every_export_is_a_kit_function(self):
        from hybrasil.viz.export import BAND_KIT_JS
        from hybrasil.viz.three_viewer import _KIT_EXPORTS
        for js_name in _KIT_EXPORTS.values():
            assert f"function {js_name}(" in BAND_KIT_JS, js_name

    def test_the_page_loads_the_kit_before_the_viewer(self):
        html = build_html({"trappist-1": _figure("trappist-1", 3)}, "trappist-1")
        assert html.index("window.SABandKit =") < html.index('<script type="module">')


class TestTheLegendMatchesPlotly:
    def test_the_same_bodies_and_arrows_are_listed(self, converted):
        # Plotly's legend is every trace with showlegend on; the three.js
        # legend lists the bodies and lines flagged the same way.
        key, fig, scene = converted
        plotly = {t.name for t in fig.data
                  if t.showlegend is not False and t.type == "scatter3d"}
        three = ({b["name"] for b in scene["bodies"] if b["legend"]}
                 | {l["name"] for l in scene["lines"] if l["legend"]})
        assert three == plotly


class TestMarkersAreDrawnAsPlotlyDrawsThem:
    def test_a_hypothetical_body_is_a_ring_not_a_black_dot(self):
        # Plotly fills these rgba(0,0,0,0) and draws the edge; lifting the
        # fill alone drew Planet Nine as black on a black sky.
        scene = figure_to_scene(_figure("solar", 2))
        nine = next(b for b in scene["bodies"] if b["name"].startswith("Planet Nine"))
        assert nine["fill"] is None and nine["edge"], nine
        assert nine["color"] == nine["edge"]

    def test_a_star_keeps_its_outline(self):
        scene = figure_to_scene(_figure("alpha-centauri", 2))
        a = next(b for b in scene["bodies"] if b["name"] == "Alpha Centauri A")
        assert a["fill"] and a["edge"], a


class TestMoonOrbitsRideTheirPlanet:
    """A moon's ellipse is drawn round its planet at t_start; the viewer moves
    it with the planet, and needs to be told which planet."""

    def test_every_moon_orbit_names_its_planet(self):
        system = get_builtin_system("solar")
        scene = figure_to_scene(_figure("solar", 2))
        follows = {l["name"]: l.get("follows") for l in scene["lines"]}
        for moon in (b for b in system.bodies if b.body_type == "moon"):
            assert follows[f"{moon.label()} orbit"] == moon.parent

    def test_no_planet_orbit_follows_anything(self):
        system = get_builtin_system("solar")
        scene = figure_to_scene(_figure("solar", 2))
        follows = {l["name"]: l.get("follows") for l in scene["lines"]}
        for planet in system.get_planets():
            assert follows.get(f"{planet.label()} orbit") is None

    def test_any_ellipse_round_a_moving_parent_rides_it(self):
        # Not only moons: Castor C's 13,000-year ellipse is drawn round Castor
        # AB at t_start, and AB moves about 38 AU along its 459-year orbit in
        # the span. Left behind, C drifted 2% of its orbit off the line
        # (9 Oct 2026). Every followed name must be a marker the viewer has.
        scene = figure_to_scene(_figure("castor", 2))
        follows = {l["name"]: l.get("follows") for l in scene["lines"]}
        markers = {b["name"] for b in scene["bodies"]}
        cab = next(n for n in follows if n.startswith("Castor C barycentre"))
        assert follows[cab] == next(m for m in markers if m.startswith("Castor AB"))
        assert {f for f in follows.values() if f} <= markers


class TestBandsRideTheirStar:
    """A band is built round its star at t_start; the viewer moves it with the
    star, and needs the star's name as the scene spells its marker."""

    def test_every_solvent_band_names_a_marker_in_the_scene(self, converted):
        key, _, scene = converted
        markers = {b["name"] for b in scene["bodies"]}
        bands = [b for b in scene["bands"] if b["solvent"]]
        assert bands, f"{key}: no solvent bands"
        for b in bands:
            assert b["follows"] in markers, f"{key}: {b['name']} follows {b['follows']!r}"

    def test_a_hypothetical_star_is_followed_by_its_label(self):
        # Proxima's orbit is hypothetical, so its marker carries a label
        # rather than its bare name; matching on the name left its bands behind.
        system = get_builtin_system("alpha-centauri")
        proxima = next(b for b in system.bodies if b.name == "Proxima Centauri")
        scene = figure_to_scene(_figure("alpha-centauri", 2))
        follows = {b["follows"] for b in scene["bands"] if b["solvent"]}
        assert proxima.label() in follows
