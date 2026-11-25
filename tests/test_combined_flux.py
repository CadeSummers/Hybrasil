# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Solvent bands under more than one star's light.

Around a lone star a band is its own circle.  Where a companion is close
enough to matter the fluxes add, the band is wherever the *summed* flux lies
between its hot and cold levels, and the ring is bent out of round -- on each
star's own plane, whatever angle the two planes make.

The solver exists twice, like the band equation: `mechanics/combined_flux.py`
and `band_kit.js`.  The last class here runs both and compares.
"""

import json
import math
import shutil
import subprocess

import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.mechanics.combined_flux import (
    NEGLIGIBLE_FLUX,
    band_outline,
    combined_flux,
    equilibrium_temperature_k,
    liquid_interval,
    relevant_sources,
)
from hybrasil.mechanics.solvent_bands import (
    WATER,
    SolventChoice,
    interpolated_liquid_range_k,
    solvent_band_at_albedo,
)
from hybrasil.mechanics.time_series import system_positions_at
from hybrasil.mechanics.units import J2000
from hybrasil.viz.export import _ZOOM_JS, build_solvent_table_js
from hybrasil.viz.static_plot import band_sources, zone_outline

TWO_SUNS = [(-1.0, 0.0, 0.0, 1.0), (1.0, 0.0, 0.0, 1.0)]


class TestTheTemperatureField:
    """`temperature_3d` as it was handed over: 254.6 * (sum L/d^2) ** 0.25."""

    def test_the_midpoint_of_two_suns(self):
        assert equilibrium_temperature_k((0, 0, 0), TWO_SUNS) == pytest.approx(
            302.77, abs=0.02)

    def test_one_au_above_the_midpoint(self):
        # Each star is sqrt(2) AU away, so together they give one Sun at 1 AU.
        assert equilibrium_temperature_k((0, 0, 1), TWO_SUNS) == pytest.approx(
            254.6, abs=0.02)

    def test_one_star_is_the_band_equation(self):
        # The edges of the single-star band sit exactly at the solvent's own
        # limits, greenhouse and albedo included.
        inner, outer = solvent_band_at_albedo(0.5, WATER, 1.0, 0.2, True, 33.0)
        t_melt, t_boil = interpolated_liquid_range_k(WATER, 1.0)
        sun = [(0.0, 0.0, 0.0, 0.5)]
        assert equilibrium_temperature_k((inner, 0, 0), sun, 0.2, 33.0) == \
            pytest.approx(t_boil, rel=1e-12)
        assert equilibrium_temperature_k((0, outer, 0), sun, 0.2, 33.0) == \
            pytest.approx(t_melt, rel=1e-12)

    def test_a_point_off_the_plane_is_lit_at_its_true_distance(self):
        # The 2-D form is the 3-D one with z = 0, and only then.
        on = combined_flux((0.0, 0.5, 0.0), TWO_SUNS)
        off = combined_flux((0.0, 0.5, 0.7), TWO_SUNS)
        assert on == pytest.approx(2 / 1.25)
        assert off == pytest.approx(2 / (1.25 + 0.49))


class TestWhenACompanionMatters:
    def test_a_lone_star_keeps_its_circle_exactly(self):
        r_in, r_out = band_outline(0, [(3.0, 1.0, 2.0, 0.7)], (0, 0, 1),
                                   0.5, 1.1, 12)
        assert r_in == [0.5] * 12 and r_out == [1.1] * 12

    def test_a_far_companion_is_left_out(self):
        # Proxima's light at Alpha Centauri A, and A's at 13,000 AU.
        sources = [(0.0, 0.0, 0.0, 1.5), (13000.0, 0.0, 0.0, 0.0017)]
        assert len(relevant_sources(0, sources, 2.0)) == 1
        r_in, r_out = band_outline(0, sources, (0, 0, 1), 1.0, 2.0, 8)
        assert r_in == [1.0] * 8 and r_out == [2.0] * 8

    def test_what_is_left_out_is_under_the_cutoff(self):
        sources = [(0.0, 0.0, 0.0, 1.0), (40.0, 0.0, 0.0, 1.0)]
        outer = 1.0
        dropped = len(relevant_sources(0, sources, outer)) == 1
        worst = 1.0 / (40.0 - outer) ** 2          # the companion's flux at the edge
        assert dropped == (worst < NEGLIGIBLE_FLUX * 1.0 / outer ** 2)

    def test_a_very_close_pair_is_one_star_of_their_summed_light(self):
        sources = [(0.0, 0.0, 0.0, 1.0), (1e-4, 0.0, 0.0, 1.0)]
        r_in, r_out = band_outline(0, sources, (0, 0, 1), 0.5, 1.0, 16)
        for a, b in zip(r_in, r_out):
            assert a == pytest.approx(0.5 * math.sqrt(2), rel=1e-3)
            assert b == pytest.approx(1.0 * math.sqrt(2), rel=1e-3)

    def test_the_band_bulges_toward_the_companion(self):
        sources = [(0.0, 0.0, 0.0, 1.0), (3.0, 0.0, 0.0, 1.0)]
        r_in, r_out = band_outline(0, sources, (0, 0, 1), 0.5, 1.0, 180)
        assert r_out[0] == max(r_out) and r_out[90] == min(r_out)
        assert min(r_out) > 1.0 and min(r_in) > 0.5      # more light everywhere
        # Mirror-symmetric about the line through the two stars.
        for t in range(1, 90):
            assert r_out[t] == pytest.approx(r_out[180 - t], rel=1e-8)

    def test_every_edge_is_on_a_flux_level(self):
        sources = [(0.0, 0.0, 0.0, 1.0), (2.2, 0.4, 0.3, 0.6),
                   (-1.5, 2.0, -0.2, 0.2)]
        normal, inner, outer, n = (0.2, -0.3, 0.9), 0.5, 1.0, 60
        from hybrasil.mechanics.orientation import plane_basis
        u, v = plane_basis(normal)
        r_in, r_out = band_outline(0, sources, normal, inner, outer, n)
        for t in range(n):
            a = 2 * math.pi * t / n
            d = [math.cos(a) * u[i] + math.sin(a) * v[i] for i in range(3)]
            hot = combined_flux([r_in[t] * c for c in d], sources)
            cold = combined_flux([r_out[t] * c for c in d], sources)
            assert hot == pytest.approx(1.0 / inner ** 2, rel=1e-8)
            assert (cold == pytest.approx(1.0 / outer ** 2, rel=1e-8)
                    or cold == pytest.approx(1.0 / inner ** 2, rel=1e-8))

    def test_a_ray_into_a_companion_stops_at_its_hot_zone(self):
        # Straight at a companion inside the band: liquid until its own
        # too-hot zone, not out to where the cold edge would have been.
        kept = relevant_sources(0, [(0.0, 0.0, 0.0, 1.0),
                                    (2.0, 0.0, 0.0, 0.01)], 3.0)
        r_in, r_out = liquid_interval(kept, (1.0, 0.0, 0.0), 0.5, 3.0)
        assert 0.5 < r_in < 0.6
        assert 1.5 < r_out < 2.0
        assert combined_flux((r_out, 0, 0), kept) == pytest.approx(1 / 0.25,
                                                                   rel=1e-8)

    def test_a_narrow_hot_zone_is_not_stepped_over(self):
        # A faint companion whose too-hot zone is far thinner than one step
        # of the march, sitting right on the ray.
        kept = relevant_sources(0, [(0.0, 0.0, 0.0, 1.0),
                                    (1.013, 0.0, 0.0, 1e-7)], 3.0)
        r_in, r_out = liquid_interval(kept, (1.0, 0.0, 0.0), 0.5, 3.0)
        assert r_out < 1.013

    def test_a_companion_off_the_plane_still_warms_it(self):
        # Directly above the star: every direction in the plane is the same
        # distance from it, so the ring stays round -- and gets bigger.
        sources = [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 2.0, 1.0)]
        r_in, r_out = band_outline(0, sources, (0, 0, 1), 0.5, 1.0, 24)
        assert max(r_out) == pytest.approx(min(r_out), rel=1e-8)
        assert min(r_out) > 1.05


class TestTheBuiltInSystems:
    def test_a_single_star_system_is_never_solved(self):
        system = get_builtin_system("solar", SolventChoice.parse("all"))
        sources, index = band_sources(system, system_positions_at(system, J2000))
        assert len(sources) == 1
        assert all(zone_outline(z, sources, index) is None
                   for z in system.belt_zones)

    def test_alpha_centauris_two_planes_each_show_the_other_star(self):
        # A and B do not share a band plane; each one's outer bands are bent
        # by the other all the same, in its own plane.
        system = get_builtin_system("alpha-centauri", SolventChoice.parse("all"))
        sources, index = band_sources(system, system_positions_at(system, J2000))
        assert len(sources) == 3
        normals, bent = {}, set()
        for zone in system.belt_zones:
            if not zone.is_solvent_band:
                continue
            normals[zone.centre_body] = zone.normal
            outline = zone_outline(zone, sources, index)
            if outline and max(outline[1]) > min(outline[1]) * 1.01:
                bent.add(zone.centre_body)
        a, b = normals["Alpha Centauri A"], normals["Alpha Centauri B"]
        assert abs(sum(x * y for x, y in zip(a, b))) < 0.999
        assert {"Alpha Centauri A", "Alpha Centauri B"} <= bent
        assert "Proxima Centauri" not in bent

    def test_a_bands_own_radii_are_untouched(self):
        # The data layer still records each star's own circle: the outline is
        # the figure's business, solved where the stars are when it is drawn.
        system = get_builtin_system("alpha-centauri", SolventChoice.parse("water"))
        zone = next(z for z in system.belt_zones
                    if z.centre_body == "Alpha Centauri A")
        want = solvent_band_at_albedo(zone.luminosity_sun, WATER, 1.0, 0.3, True,
                                      33.0, zone.colour_factor)
        assert (zone.r_inner_au, zone.r_outer_au) == pytest.approx(want)


def _extract_js_function(name: str) -> str:
    start = _ZOOM_JS.index("function %s(" % name)
    depth, i = 0, _ZOOM_JS.index("{", start)
    while True:
        if _ZOOM_JS[i] == "{":
            depth += 1
        elif _ZOOM_JS[i] == "}":
            depth -= 1
            if depth == 0:
                return _ZOOM_JS[start:i + 1]
        i += 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
class TestTheTwoSolversAgree:
    """`band_kit.js` against `combined_flux.py`, ray for ray."""

    N = 36
    CASES = [
        # own, sources [x, y, z, w], normal, inner, outer
        (0, [[0, 0, 0, 1.0], [3, 0, 0, 1.0]], [0, 0, 1], 0.5, 1.0),
        (1, [[0, 0, 0, 1.5], [17.6, -3.1, 9.4, 0.5], [-9000, 4000, 100, 0.002]],
         [-0.413, 0.891, 0.187], 4.0, 9.0),
        (0, [[5, 5, -5, 0.8], [5.05, 5.0, -5.0, 0.3], [40, 0, 0, 2.0]],
         [0.0, -1.0, 0.004], 0.3, 0.8),
        (0, [[0, 0, 0, 1.0], [2.0, 0.0, 0.0, 0.01]], [0, 0, 1], 0.5, 3.0),
        (0, [[0, 0, 0, 1.0], [5000, 0, 0, 1.0]], [0, 0, 1], 0.5, 1.0),   # a circle
        (0, [[0, 0, 0, 1.0]], [0, 0, 1], 0.5, 1.0),                        # a lone star
    ]

    def _run_js(self):
        script = "\n".join([
            "var window = {};",
            build_solvent_table_js(SolventChoice.parse("all")),
            *[_extract_js_function(f) for f in (
                "_bandConst", "_planeBasis", "_ringMesh", "_fluxAt",
                "_relevantSources", "_rayCrossing", "_liquidInterval",
                "_bandOutline", "_outlineMesh", "_shellMesh", "_bandSources")],
            "var cases = %s;" % json.dumps(self.CASES),
            "var out = [];",
            "for (var c = 0; c < cases.length; c++) {",
            "  var a = cases[c];",
            "  var ol = _bandOutline(a[0], a[1], a[2], a[3], a[4], %d);" % self.N,
            "  var flat = ol ? _outlineMesh(ol[0], ol[1], a[2], 0.01, a[1][a[0]]) : null;",
            "  var shell = _shellMesh(ol ? a[0] : -1, a[1], a[2], a[3], a[4], 8, 4, a[1][a[0]]);",
            "  out.push({outline: ol, flat: flat, shell: shell});",
            "}",
            "var metas = [{lum: 1.5, colour: 1.1, body: 'A', centre: [0, 0, 0]},",
            "             {lum: 1.5, colour: 1.1, body: 'A', centre: [0, 0, 0]},",
            "             {lum: 0, body: 'X', centre: [1, 1, 1]},",
            "             {lum: 0.5, body: 'B', centre: [3, 4, 5]}];",
            "console.log(JSON.stringify({cases: out, sources: _bandSources(metas)}));",
        ])
        proc = subprocess.run(["node", "-e", script], capture_output=True,
                              text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    def test_every_outline_matches(self):
        bent = 0
        for (own, sources, normal, inner, outer), got in zip(
                self.CASES, self._run_js()["cases"]):
            want_in, want_out = band_outline(own, [tuple(s) for s in sources],
                                             normal, inner, outer, self.N)
            if got["outline"] is None:
                # The viewer's "no companion matters" is Python's plain circle.
                assert want_in == [inner] * self.N and want_out == [outer] * self.N
                continue
            bent += 1
            assert got["outline"][0] == pytest.approx(want_in, rel=1e-10)
            assert got["outline"][1] == pytest.approx(want_out, rel=1e-10)
        assert bent >= 4

    def test_the_flat_mesh_is_the_one_python_builds(self):
        import numpy as np
        from hybrasil.models.system import BeltZone
        from hybrasil.viz.static_plot import _belt_trace

        for (own, sources, normal, inner, outer), got in zip(
                self.CASES, self._run_js()["cases"]):
            if got["flat"] is None:
                continue
            zone = BeltZone("ring", r_inner_au=inner, r_outer_au=outer,
                            normal=tuple(normal), offset_au=0.01)
            trace = _belt_trace(
                zone, n_pts=self.N, centre=tuple(sources[own][:3]),
                outline=band_outline(own, [tuple(s) for s in sources], normal,
                                     inner, outer, self.N))
            for axis, want in zip("xyz", (trace.x, trace.y, trace.z)):
                assert np.allclose(np.asarray(got["flat"][axis]),
                                   np.asarray(want), rtol=0, atol=1e-9), axis
            # The same triangles, which the two list in a different order.
            flat = got["flat"]
            assert (sorted(zip(flat["i"], flat["j"], flat["k"]))
                    == sorted((int(a), int(b), int(c)) for a, b, c
                              in zip(trace.i, trace.j, trace.k)))

    def test_the_shells_equator_is_the_flat_outline(self):
        # The 3-D heatmap's two surfaces, cut through the band's own plane,
        # are the flat band's two edges: latitude row 2 of 4 is the equator.
        for (own, sources, normal, inner, outer), got in zip(
                self.CASES, self._run_js()["cases"]):
            want_in, want_out = band_outline(own, [tuple(s) for s in sources],
                                             normal, inner, outer, 8)
            shell, centre, per = got["shell"], sources[own][:3], 5 * 8
            assert len(shell["x"]) == 2 * per
            for surface, want in ((0, want_in), (1, want_out)):
                for j in range(8):
                    q = surface * per + 2 * 8 + j
                    r = math.dist((shell["x"][q], shell["y"][q], shell["z"][q]),
                                  centre)
                    assert r == pytest.approx(want[j], rel=1e-8)

    def test_a_lone_stars_shells_are_spheres(self):
        shell = self._run_js()["cases"][-1]["shell"]
        per = 5 * 8
        for q in range(2 * per):
            r = math.dist((shell["x"][q], shell["y"][q], shell["z"][q]), (0, 0, 0))
            assert r == pytest.approx(0.5 if q < per else 1.0, rel=1e-12)

    def test_the_viewer_reads_its_sources_off_the_bands(self):
        got = self._run_js()["sources"]
        assert got["own"] == [0, 0, -1, 1]
        assert got["sources"] == [pytest.approx([0, 0, 0, 1.65]),
                                  pytest.approx([3, 4, 5, 0.5])]
