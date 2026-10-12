# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the pressure, albedo and greenhouse sliders.

Two things were fixed numbers baked into the figure and are now dragged: the
pressure a band is computed at and the albedo of the body it is computed for.
A third, the greenhouse offset, was not modelled at all and is now a flat
number of kelvin on its own slider, labelled beta.  That made two demands on
the code.

The first is **interpolation**.  The workbook transcribes seven pressure
columns and a slider needs every value between them, so the melting and
boiling points are interpolated -- and the form matters, which is what
`TestInterpolation` pins.

The second is that the band is recomputed **in the browser**, since a page
reload per drag is not a slider.  That means the same equation exists twice,
once in `mechanics/solvent_bands.py` and once in the viewer's JavaScript, and
the only thing stopping them drifting apart is `TestTheTwoImplementationsAgree`
below, which runs both and compares.
"""

import json
import math
import shutil
import subprocess

import pytest

from hybrasil.mechanics.solvent_bands import (
    AMMONIA,
    CARBON_DIOXIDE,
    DEFAULT_ALBEDO,
    DEFAULT_GREENHOUSE_K,
    ETHANE,
    FORMAMIDE,
    MAX_ALBEDO,
    MAX_GREENHOUSE_K,
    MAX_PRESSURE_BAR,
    METHANE,
    MIN_ALBEDO,
    MIN_GREENHOUSE_K,
    MIN_PRESSURE_BAR,
    PRESSURES_BAR,
    SOLVENTS,
    SULFUR,
    SULFURIC_ACID,
    T_CMB_K,
    WATER,
    BOILS_EVERYWHERE,
    CELSIUS_TO_KELVIN,
    SolventChoice,
    band_absent_reason,
    equilibrium_distance_au,
    solvent_zones,
    stack_offsets_for_outer,
    interpolated_liquid_range_k,
    interpolation_absent_reason,
    solvent_band_at_albedo,
    solvent_band_au,
    widest_band_outer_au,
)
from hybrasil.mechanics.units import T_EQ_1AU_K
from hybrasil.viz.export import (BAND_KIT_JS, _ZOOM_JS,
                                      build_solvent_table_js)


class TestInterpolation:
    """Between the workbook's columns, and never past a solvent's own range."""

    @pytest.mark.parametrize("pressure", PRESSURES_BAR)
    def test_a_transcribed_column_comes_back_exactly(self, pressure):
        # Interpolation must not round-trip the cells the workbook tests pin.
        transcribed = WATER.phase_points.get(pressure)
        if transcribed is None:
            return
        got = interpolated_liquid_range_k(WATER, pressure, apply_ceiling=False)
        assert got == pytest.approx((transcribed[0] + CELSIUS_TO_KELVIN,
                                     transcribed[1] + CELSIUS_TO_KELVIN))

    def test_boiling_follows_clausius_clapeyron(self):
        # Water boils at 120.2 C at 2 bar. Interpolating T linearly in ln P
        # gives 122.1, which is wrong by two degrees; interpolating 1/T -- the
        # form a vapour-pressure curve actually takes -- gives 120.4.
        t_boil = interpolated_liquid_range_k(WATER, 2.0)[1] - CELSIUS_TO_KELVIN
        assert t_boil == pytest.approx(120.4, abs=0.15)

        p0, p1 = 1.0, 5.0
        f = (math.log(2.0) - math.log(p0)) / (math.log(p1) - math.log(p0))
        naive = (WATER.phase_points[p0][1]
                 + f * (WATER.phase_points[p1][1] - WATER.phase_points[p0][1]))
        assert abs(naive - 120.2) > abs(t_boil - 120.2)

    def test_melting_barely_moves_at_all(self):
        # Which is why it is interpolated in the simple form: water's melting
        # point falls less than a degree across the whole slider.
        lo = interpolated_liquid_range_k(WATER, MIN_PRESSURE_BAR)[0]
        hi = interpolated_liquid_range_k(WATER, MAX_PRESSURE_BAR)[0]
        assert abs(hi - lo) < 1.0

    @pytest.mark.parametrize("solvent,pressure,reason", [
        (METHANE, 0.2, "below its triple point"),      # 0.5 bar is its lowest
        (METHANE, 60.0, "supercritical"),              # 10 bar is its highest
        (CARBON_DIOXIDE, 2.0, "below its triple point"),
        (FORMAMIDE, 5.0, "decomposes before boiling"),
    ])
    def test_outside_its_range_a_solvent_has_no_band(self, solvent, pressure, reason):
        # Extrapolating a vapour-pressure curve past its last transcribed point
        # is how you draw a band where the substance is not liquid at all.
        assert interpolated_liquid_range_k(solvent, pressure) is None
        assert interpolation_absent_reason(solvent, pressure) == reason

    def test_inside_its_range_there_is_always_a_band(self):
        assert interpolation_absent_reason(WATER, 37.4) is None
        assert interpolation_absent_reason(METHANE, 7.0) is None

    def test_the_slider_ends_are_the_workbook_ends(self):
        # So the whole track is interpolation and none of it is invention.
        assert MIN_PRESSURE_BAR == PRESSURES_BAR[0]
        assert MAX_PRESSURE_BAR == PRESSURES_BAR[-1]


class TestOneAlbedoGivesOneRing:
    """Setting albedo is what removes the need to bracket it."""

    def test_the_edges_are_the_bracket_edges_at_the_same_albedos(self):
        # The nested conservative/optimistic pair is this same calculation run
        # at two albedos because the real one is unknown. Fixing the albedo has
        # to land on the same numbers, or the slider and the workbook disagree.
        bracket = solvent_band_au(1.0, WATER, 1.0)
        at_low = solvent_band_at_albedo(1.0, WATER, 1.0, 0.0)
        at_high = solvent_band_at_albedo(1.0, WATER, 1.0, 0.3)
        assert at_high[0] == pytest.approx(bracket.optimistic[0])
        assert at_low[1] == pytest.approx(bracket.optimistic[1])
        assert at_low[0] == pytest.approx(bracket.conservative[0])
        assert at_high[1] == pytest.approx(bracket.conservative[1])

    def test_a_darker_body_pushes_the_band_outward(self):
        # A darker body is hotter at the same distance, so it has to sit
        # further out to stay in the same temperature window.
        dark = solvent_band_at_albedo(1.0, WATER, 1.0, MIN_ALBEDO)
        bright = solvent_band_at_albedo(1.0, WATER, 1.0, MAX_ALBEDO)
        assert dark[0] > bright[0] and dark[1] > bright[1]

    def test_albedo_scales_both_edges_by_the_same_factor(self):
        # sqrt(1 - A) multiplies the whole ring; it does not reshape it.
        a, b = 0.1, 0.8
        one = solvent_band_at_albedo(1.0, AMMONIA, 1.0, a)
        two = solvent_band_at_albedo(1.0, AMMONIA, 1.0, b)
        expect = math.sqrt((1 - b) / (1 - a))
        assert two[0] / one[0] == pytest.approx(expect)
        assert two[1] / one[1] == pytest.approx(expect)

    def test_the_scene_is_claimed_at_the_darkest_albedo(self):
        # Not at the albedo being drawn: dragging albedo down must not grow a
        # band out of a scene box that was sized for a brighter one.
        assert widest_band_outer_au(1.0, WATER, 1.0) == pytest.approx(
            solvent_band_at_albedo(1.0, WATER, 1.0, MIN_ALBEDO)[1])
        assert widest_band_outer_au(1.0, WATER, 1.0) > solvent_band_at_albedo(
            1.0, WATER, 1.0, DEFAULT_ALBEDO)[1]

    def test_no_band_where_the_solvent_is_not_liquid(self):
        assert solvent_band_at_albedo(1.0, CARBON_DIOXIDE, 1.0, 0.3) is None
        assert solvent_band_at_albedo(1.0, CARBON_DIOXIDE, 40.0, 0.3) is not None


class TestTheGreenhouseOffset:
    """A flat number of kelvin on top of the blackbody temperature.

    The surface is liquid where T_eq + offset sits between the melting and
    boiling points, so each edge is where T_eq is that point *minus* the
    offset.  Simple on purpose, and labelled beta in the viewer for it.
    """

    def test_the_default_is_earths(self):
        # Earth's blackbody temperature at albedo 0.3, from this code's own
        # constant, plus the offset has to land on Earth's 288 K mean surface.
        earth_t_eq = T_EQ_1AU_K * (1 - 0.3) ** 0.25
        assert earth_t_eq + DEFAULT_GREENHOUSE_K == pytest.approx(288.0, abs=0.6)
        assert (MIN_GREENHOUSE_K, MAX_GREENHOUSE_K) == (0.0, 1000.0)

    def test_no_offset_is_the_blackbody_band(self):
        # The workbook's figures are the zero-offset band, and the mechanics
        # default to it: only SolventChoice starts a figure at Earth's.
        assert (solvent_band_at_albedo(1.0, WATER, 1.0, 0.3)
                == solvent_band_at_albedo(1.0, WATER, 1.0, 0.3, True, 0.0))
        assert SolventChoice().greenhouse_k == DEFAULT_GREENHOUSE_K

    @pytest.mark.parametrize("g", [0.0, 33.0, 150.0])
    def test_each_edge_sits_where_the_surface_is_at_its_point(self, g):
        # Put the offset back on the blackbody temperature at each edge and
        # the result has to be the boiling and the melting point.
        lum, albedo = 0.8, 0.25
        inner, outer = solvent_band_at_albedo(lum, WATER, 1.0, albedo, True, g)
        t_melt, t_boil = interpolated_liquid_range_k(WATER, 1.0)

        def t_eq(d):
            return T_EQ_1AU_K * lum ** 0.25 * (1 - albedo) ** 0.25 / math.sqrt(d)

        assert t_eq(inner) + g == pytest.approx(t_boil)
        if t_melt - g > T_CMB_K:
            assert t_eq(outer) + g == pytest.approx(t_melt)

    def test_a_warmer_surface_pushes_the_band_outward(self):
        cold = solvent_band_at_albedo(1.0, AMMONIA, 1.0, 0.3, True, 0.0)
        warm = solvent_band_at_albedo(1.0, AMMONIA, 1.0, 0.3, True, 33.0)
        assert warm[0] > cold[0] and warm[1] > cold[1]

    def test_past_the_boiling_point_there_is_no_band(self):
        # Water boils at 373 K, so a 400 K offset boils it at every distance
        # -- and the description says so rather than dropping it silently.
        assert solvent_band_at_albedo(1.0, WATER, 1.0, 0.3, True, 400.0) is None
        assert band_absent_reason(WATER, 1.0, True, 400.0) == BOILS_EVERYWHERE
        assert band_absent_reason(WATER, 1.0, True, 33.0) is None
        # A pressure reason still comes first: CO2 at 1 bar is under its
        # triple point whatever the greenhouse does.
        assert band_absent_reason(CARBON_DIOXIDE, 1.0, True, 400.0) == (
            "below its triple point")

    def test_past_the_melting_point_the_cold_edge_is_the_cmb(self):
        # Methane melts at 91 K. A 100 K offset leaves it liquid at any
        # distance, so the cold edge is where starlight stops setting the
        # temperature -- finite, and the same for every such solvent.
        band = solvent_band_at_albedo(1.0, METHANE, 1.0, 0.3, True, 100.0)
        cmb = equilibrium_distance_au(T_CMB_K, 1.0, 0.3)
        assert band is not None and math.isfinite(band[1])
        assert band[1] == pytest.approx(cmb)
        assert solvent_band_at_albedo(1.0, ETHANE, 1.0, 0.3, True, 100.0)[1] == (
            pytest.approx(cmb))

    def test_the_whole_track_is_finite(self):
        # Every band at every offset is either absent or a finite ring: an
        # infinite edge would reach Plotly as a null and draw nothing at all.
        for g in range(0, 1001, 10):
            for solvent in SOLVENTS.values():
                band = solvent_band_at_albedo(1.0, solvent, 1.0, MIN_ALBEDO,
                                              True, float(g))
                assert band is None or all(math.isfinite(r) for r in band)

    def test_the_scene_is_claimed_where_the_slider_starts(self):
        zone = solvent_zones(1.0, (WATER,), greenhouse_k=33.0)[0]
        assert zone.scene_claim_au == pytest.approx(
            widest_band_outer_au(1.0, WATER, 1.0, greenhouse_k=33.0))
        assert zone.scene_claim_au > widest_band_outer_au(1.0, WATER, 1.0)

    def test_a_band_run_out_to_the_cmb_stays_on_its_plane(self):
        # Stacking lifts a band by a fraction of its outer radius. At 300 K
        # water, formamide and sulfuric acid all run out to ~8,700 AU, and a
        # lift scaled by that would float sulfuric acid's 0.87 AU inner edge
        # ~130 AU off the plane.  Capped, it is a fraction of that inner edge,
        # the same order as an ordinary band's lift.
        zones = solvent_zones(1.0, SOLVENTS.values(), greenhouse_k=300.0)
        acid = next(z for z in zones if z.solvent_key == SULFURIC_ACID.key)
        assert acid.r_outer_au > 1000
        assert 0 < acid.offset_au < 0.5 * acid.r_inner_au

    def test_the_stacking_cap_leaves_ordinary_bands_alone(self):
        # Every band at the offset the figure opens on spans under the cap,
        # so capping changes nothing about how the default figure stacks.
        bands = [solvent_band_at_albedo(1.0, s, 1.0, 0.3, True,
                                        DEFAULT_GREENHOUSE_K)
                 for s in SOLVENTS.values()]
        outer = [b[1] if b else 0.0 for b in bands]
        inner = [b[0] if b else 0.0 for b in bands]
        assert stack_offsets_for_outer(outer, inner) == stack_offsets_for_outer(outer)


class TestTheCliStartsTheSliders:
    def test_the_defaults_are_the_slider_defaults(self):
        from hybrasil.cli import build_parser

        args = build_parser().parse_args([])
        assert args.albedo == DEFAULT_ALBEDO
        assert args.pressure == 1.0
        assert args.greenhouse == DEFAULT_GREENHOUSE_K

    @pytest.mark.parametrize("flag,value", [
        ("--albedo", "1.5"), ("--albedo", "0"),
        ("--pressure", "500"), ("--pressure", "0.01"),
        ("--greenhouse", "-1"), ("--greenhouse", "1000.5"),
    ])
    def test_a_start_outside_the_track_is_refused(self, flag, value):
        from hybrasil.cli import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args([flag, value])

    def test_any_pressure_in_the_range_is_accepted_now(self):
        # It used to be one of the workbook's seven, which a slider cannot be.
        from hybrasil.cli import build_parser

        assert build_parser().parse_args(["--pressure", "37.4"]).pressure == 37.4

    def test_the_choice_carries_the_albedo_to_the_bands(self):
        from hybrasil.data.builtin_systems import get_builtin_system

        dark = get_builtin_system("solar", SolventChoice.parse("water", albedo=0.05))
        bright = get_builtin_system("solar", SolventChoice.parse("water", albedo=0.9))
        assert (next(z for z in dark.belt_zones if z.is_solvent_band).r_outer_au
                > next(z for z in bright.belt_zones if z.is_solvent_band).r_outer_au)

    def test_the_choice_carries_the_greenhouse_to_the_bands(self):
        from hybrasil.data.builtin_systems import get_builtin_system

        bare = SolventChoice.parse("water", greenhouse_k=0.0)
        warm = SolventChoice.parse("water", greenhouse_k=60.0)
        # Two figures, so two cache entries: the registry keys on this.
        assert bare.cache_key != warm.cache_key
        cold = get_builtin_system("solar", bare)
        hot = get_builtin_system("solar", warm)
        assert (next(z for z in hot.belt_zones if z.is_solvent_band).r_outer_au
                > next(z for z in cold.belt_zones if z.is_solvent_band).r_outer_au)
        assert "60 K greenhouse offset" in hot.description
        assert "no greenhouse offset" in cold.description

    def test_the_greenhouse_flag_reaches_the_choice(self, monkeypatch):
        # main() builds the choice; a flag parsed and then dropped is the
        # figure silently opening at Earth's offset whatever was asked for.
        from hybrasil import cli

        seen = {}
        real = SolventChoice.parse

        def spy(*args, **kwargs):
            choice = real(*args, **kwargs)
            seen["choice"] = choice
            raise SystemExit(0)

        monkeypatch.setattr(cli.SolventChoice, "parse", spy)
        with pytest.raises(SystemExit):
            cli.main(["--greenhouse", "120"])
        assert seen["choice"].greenhouse_k == 120.0


class TestTheTableTheViewerReadsFrom:
    def test_every_solvent_reaches_the_browser(self):
        js = build_solvent_table_js(SolventChoice.parse("all"))
        table = json.loads(js.split("window._SA_SOLVENTS = ")[1].split(";\n")[0])
        assert set(table) == set(SOLVENTS)

    def test_the_transcribed_points_go_across_in_pressure_order(self):
        js = build_solvent_table_js(SolventChoice.parse("all"))
        table = json.loads(js.split("window._SA_SOLVENTS = ")[1].split(";\n")[0])
        for key, entry in table.items():
            pressures = [p for p, _, _ in entry["points"]]
            assert pressures == sorted(pressures)
            assert pressures == sorted(SOLVENTS[key].phase_points)

    def test_the_sliders_start_where_the_command_line_said(self):
        js = build_solvent_table_js(
            SolventChoice.parse("all", pressure_bar=12.5, albedo=0.44,
                                greenhouse_k=71.5))
        const = json.loads(js.split("window._SA_BAND_CONST = ")[1].rstrip(";"))
        assert const["p0"] == 12.5 and const["a0"] == 0.44 and const["g0"] == 71.5
        assert (const["p_min"], const["p_max"]) == (MIN_PRESSURE_BAR, MAX_PRESSURE_BAR)
        assert (const["a_min"], const["a_max"]) == (MIN_ALBEDO, MAX_ALBEDO)
        assert (const["g_min"], const["g_max"]) == (MIN_GREENHOUSE_K, MAX_GREENHOUSE_K)
        assert const["t_cmb"] == T_CMB_K

    def test_both_sides_agree_on_the_ring_resolution(self):
        # The clipper caches a band's original geometry by point count, so a
        # ring the viewer rebuilds at a different resolution than Python built
        # it at would be a different trace as far as the cache is concerned.
        from hybrasil.viz.static_plot import BAND_RING_POINTS

        js = build_solvent_table_js(SolventChoice.parse("all"))
        const = json.loads(js.split("window._SA_BAND_CONST = ")[1].rstrip(";"))
        assert const["ring_pts"] == BAND_RING_POINTS


class TestTheViewerRecomputes:
    def test_the_recompute_writes_through_the_clippers_cache(self):
        # Writing visible geometry instead would drop a full-width ring into a
        # moon-sized scene box the moment a slider moved while zoomed in.
        start = _ZOOM_JS.index("function _recomputeBands(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "_geom.items[i] = {" in body
        assert "updateSceneVisibility(gd, _sa_ranges.xr" in body
        assert "Plotly.restyle(gd, {name: names}, idx);" in body

    def test_a_band_that_loses_its_liquid_phase_is_blanked(self):
        # Left alone it would keep drawing the last pressure's ring, which is
        # the figure showing a band for a pressure that has none.
        start = _ZOOM_JS.index("function _recomputeBands(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "blankIdx.push(i); blank.push([]); blankVis.push('legendonly');" in body
        assert "bbox: null" in body

    def test_a_recompute_keeps_each_bands_own_switch(self):
        # The sliders move geometry, not visibility: a band the viewer switched
        # off from the legend stays off across a drag.
        start = _ZOOM_JS.index("function _recomputeBands(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "var wanted = !!(prev && prev.bandOn);" in body
        assert body.count("bandOn: wanted") == 2

    def test_a_system_swap_recomputes_before_switching(self):
        # The swapped-in figure's bands were built by Python at the pressure
        # the page opened on, not at wherever the sliders have been dragged to.
        start = _ZOOM_JS.index("window._saReattach = function")
        end = _ZOOM_JS.index("removeAllListeners", start)
        body = _ZOOM_JS[start:end]
        assert body.index("_recomputeBands(gd);") < body.index("_setAllBands(gd,")

    def test_the_drag_is_coalesced_like_the_wheel(self):
        # A drag emits an event per pixel; rebuilding eight meshes and
        # re-cutting the scene box that often queues work faster than it
        # retires, which is what made scroll zoom lurch before it was fixed.
        start = _ZOOM_JS.index("function _scheduleBands(")
        end = _ZOOM_JS.index("function _onSlide(", start)
        body = _ZOOM_JS[start:end]
        assert "requestAnimationFrame(run)" in body
        assert "_bandTimer = setTimeout(run," in body, "rAF needs its backstop"

    def test_the_pressure_track_lands_on_the_pressure_it_opened_at(self):
        # A coarser track put 1 bar back at 0.998, so the legend and the slider
        # disagreed from the first frame.
        assert "var _perDecade = 1000;" in _ZOOM_JS
        assert "_pSteps = Math.round((_logHi - _logLo) * _perDecade)" in _ZOOM_JS

    def test_the_legend_name_follows_the_pressure(self):
        # An entry still reading "1 bar" at 40 would be the figure lying about
        # what it is showing.
        assert "function _bandName(" in _ZOOM_JS
        assert "_fmtBar(P)" in _ZOOM_JS


def _extract_js_function(name: str) -> str:
    """One `function name(...) {...}` out of the viewer script, braces matched."""
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
class TestTheTwoImplementationsAgree:
    """The band equation exists twice, and this is what stops them drifting.

    Python builds the figure and the browser rebuilds it as the sliders move,
    so a change to one that is not made to the other shows up as a band that
    jumps the first time anyone touches a slider.  Rather than trusting that,
    run the viewer's own JavaScript under node and compare it to Python across
    the whole of both tracks.
    """

    # pressure, albedo, greenhouse offset.  The offsets cover no greenhouse,
    # Earth's, one either side of methane's melting point (the cold edge
    # hitting the CMB), one that boils half the solvents away, and the top.
    CASES = [
        (1.0, 0.3, 0.0), (2.0, 0.3, 0.0), (0.1, 0.01, 0.0), (100.0, 0.99, 0.0),
        (40.0, 0.5, 0.0), (0.3, 0.05, 0.0), (7.5, 0.75, 0.0), (12.5, 0.44, 0.0),
        (0.5, 0.3, 0.0), (50.0, 0.2, 0.0), (37.4, 0.6, 0.0), (5.0, 0.0999, 0.0),
        (9.99, 0.31, 0.0), (0.101, 0.98, 0.0),
        (1.0, 0.3, 33.0), (7.5, 0.3, 88.0), (7.5, 0.3, 93.0), (40.0, 0.2, 250.0),
        (100.0, 0.01, 1000.0), (1.0, 0.3, 360.0), (12.5, 0.44, 0.1),
    ]

    def _run_js(self):
        table = build_solvent_table_js(SolventChoice.parse("all"))
        script = "\n".join([
            "var window = {};",
            table,
            _extract_js_function("_bandConst"),
            _extract_js_function("_liquidRangeK"),
            _extract_js_function("_bandRadiiAU"),
            "var cases = %s;" % json.dumps(self.CASES),
            "var keys = Object.keys(window._SA_SOLVENTS);",
            "var out = [];",
            "for (var c = 0; c < cases.length; c++) {",
            "  var row = {};",
            "  for (var k = 0; k < keys.length; k++) {",
            "    var meta = {solvent: keys[k], lum: 1.0, ceiling: true};",
            "    row[keys[k]] = _bandRadiiAU(meta, cases[c][0], cases[c][1],",
            "                                cases[c][2]);",
            "  }",
            "  out.push(row);",
            "}",
            "console.log(JSON.stringify(out));",
        ])
        proc = subprocess.run(["node", "-e", script], capture_output=True,
                              text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    def test_every_band_matches_across_both_tracks(self):
        from_js = self._run_js()
        compared = 0
        for (pressure, albedo, greenhouse), row in zip(self.CASES, from_js):
            for key, solvent in SOLVENTS.items():
                want = solvent_band_at_albedo(1.0, solvent, pressure, albedo,
                                              True, greenhouse)
                got = row[key]
                compared += 1
                assert (want is None) == (got is None), (
                    f"{key} at {pressure} bar: python {want}, viewer {got}"
                )
                if want is None:
                    continue
                assert got[0] == pytest.approx(want[0], rel=1e-12)
                assert got[1] == pytest.approx(want[1], rel=1e-12)
        assert compared == len(self.CASES) * len(SOLVENTS)

    def test_the_comparison_would_notice_a_drift(self):
        # A test that passes because it compares nothing is worse than none.
        row = self._run_js()[0]
        assert row["water"] is not None
        assert row["water"][1] != pytest.approx(row["water"][0])

    def test_the_greenhouse_cases_reach_every_regime(self):
        # Guards the cases above: each branch of the offset has to be hit, or
        # the comparison could pass while one of them drifts.
        rows = self._run_js()
        cmb = [r for r in rows for band in r.values()
               if band and band[1] > 1000]
        boiled = [r for (_, _, g), r in zip(self.CASES, rows)
                  if g > 0 and r["water"] is None]
        assert cmb, "no case runs a cold edge out to the CMB"
        assert boiled, "no case boils a band away"

    def test_the_stacking_lift_agrees(self):
        # The lift is capped for a band run out to the CMB, on both sides; a
        # cap on one alone would move a band the first time a slider moved.
        cases = []
        for g in (0.0, 33.0, 100.0, 300.0, 500.0):
            bands = [solvent_band_at_albedo(1.0, s, 1.0, 0.3, True, g)
                     for s in SOLVENTS.values()]
            cases.append(([b[1] if b else 0.0 for b in bands],
                          [b[0] if b else 0.0 for b in bands]))
        script = "\n".join([
            "var window = {};",
            build_solvent_table_js(SolventChoice.parse("all")),
            _extract_js_function("_bandConst"),
            _extract_js_function("_stackOffsets"),
            "var cases = %s;" % json.dumps(cases),
            "console.log(JSON.stringify(cases.map(function (c) {",
            "  return _stackOffsets(c[0], c[1]); })));",
        ])
        proc = subprocess.run(["node", "-e", script], capture_output=True,
                              text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        for (outer, inner), got in zip(cases, json.loads(proc.stdout)):
            assert got == pytest.approx(stack_offsets_for_outer(outer, inner),
                                        rel=1e-12, abs=1e-15)



class TestTypingAValue:
    """The readout is also the way in.

    A slider cannot be dragged to 37.4 bar on purpose, so each one's readout is
    an input: type a number and the slider moves to it. Both routes end at the
    same place, because the slider stays the single source of truth for what is
    drawn -- a typed value sets the track position and is then read back off
    it, rather than becoming a second number the two controls could disagree on.
    """

    def _panel(self) -> str:
        # The panel lives in band_kit.js, shared by both viewers.
        return BAND_KIT_JS[BAND_KIT_JS.index("function _bandPanel("):]

    def _slice(self, first: str, last: str) -> str:
        body = self._panel()
        start = body.index(first)
        return body[start:body.index(last, start + len(first))]

    def test_the_readout_is_an_input(self):
        row = self._slice("function _sliderRow(", "\n    var pRow")
        assert "var read = document.createElement('input');" in row
        assert "read.type = 'text';" in row

    def test_a_typed_value_goes_through_the_slider(self):
        # Not into _bandP directly: two numbers for one setting is two
        # controls that can disagree about what the figure is showing.
        panel = self._panel()
        assert "pRow.input.value = _barToPos(v);" in panel
        assert "aRow.input.value = v;" in panel
        assert "gRow.input.value = v;" in panel
        commit = self._slice("function _commitTyped(", "function _wireTyping(")
        assert "place(v);" in commit and "_readSliders();" in commit
        assert "_bandP =" not in commit and "_bandA =" not in commit

    def test_committing_happens_on_blur_not_on_keystroke(self):
        # Recomputing per character would rebuild every band at 1 bar on the
        # way to typing 12.
        wire = self._slice("function _wireTyping(", "var _bandRAF")
        assert "row.read.addEventListener('blur', function () {" in wire
        assert "_commitTyped(row" in wire
        assert "addEventListener('input'" not in wire

    def test_enter_commits_and_escape_puts_it_back(self):
        wire = self._slice("function _wireTyping(", "var _bandRAF")
        assert "if (e.key === 'Enter') { e.preventDefault(); row.read.blur(); }" in wire
        assert "else if (e.key === 'Escape') { _readSliders(); row.read.blur(); }" in wire

    def test_a_value_past_the_end_clamps_and_says_so(self):
        # The slider cannot go past it either, so clamping is the honest
        # answer -- but silently drawing 100 bar for someone who asked for 500
        # is the figure answering a question they did not ask.
        commit = self._slice("function _commitTyped(", "function _wireTyping(")
        assert "opts.toast('Range is '" in commit
        assert "v = v < lo ? lo : hi;" in commit

    def test_something_that_is_not_a_number_puts_the_real_value_back(self):
        commit = self._slice("function _commitTyped(", "function _wireTyping(")
        assert "if (v === null) { _readSliders(); return; }" in commit

    def test_the_parser_tolerates_the_unit_being_typed_too(self):
        # "2.5 bar" is what someone reading the row back to themselves types.
        parse = self._slice("function _parseTyped(", "function _commitTyped(")
        assert ".match(" in parse and "[0-9]" in parse

    def test_a_box_being_edited_is_never_overwritten(self):
        # _readSliders runs on every drag and every recompute; writing into a
        # half-typed number is how a readout that is also an input becomes
        # unusable.
        read = self._slice("function _readSliders(", "function _parseTyped(")
        assert "document.activeElement !== pRow.read" in read
        assert "document.activeElement !== aRow.read" in read
        assert "document.activeElement !== gRow.read" in read

    def test_the_unit_sits_outside_the_box(self):
        # So what is in the box is only ever the number it will parse back.
        panel = self._panel()
        assert "_sliderRow('Pressure', 'bar'," in panel
        assert "_sliderRow('Albedo', ''," in panel
        assert "_sliderRow('', 'K', gTitle)" in panel

    def test_the_greenhouse_slider_is_named_and_wired(self):
        # Named as asked, on a line of its own because it is longer than the
        # label column; and moving it has to rebuild the bands like the others.
        panel = self._panel()
        assert "gCaption.textContent = 'Greenhouse effect (beta)';" in panel
        assert "gRow.input.addEventListener('input', _onSlide);" in panel
        assert "_wireTyping(gRow, C0.g_min, C0.g_max, 'K'," in panel
        assert "gRow.input.value = C0.g0;" in panel
        assert panel.index("bandPanel.appendChild(gCaption);") < panel.index(
            "bandPanel.appendChild(gRow.row);")

    def test_the_recompute_reads_the_greenhouse(self):
        start = _ZOOM_JS.index("function _recomputeBands(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "var G = _bandG === null ? C.g0 : _bandG;" in body
        assert "_bandRadiiAU(gd.data[idx[k]].meta, P, A, G)" in body

    def test_the_panel_says_both_routes_exist(self):
        assert "Drag or type" in _ZOOM_JS


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
class TestTheRingGeometryAgrees:
    """The ring itself is built twice as well, and the centre is new to both.

    A band belonging to a star that is itself in orbit is centred on that star,
    and the viewer rebuilds every ring as the sliders move.  If `_ringMesh`
    were to forget the centre, the band would sit correctly until the first
    drag and then jump to the origin -- which is exactly the class of bug the
    equation test above exists to catch, one layer out.
    """

    CASES = [
        # inner, outer, normal, offset, centre
        (0.5, 0.9, [0.0, 0.0, 1.0], 0.0, [0.0, 0.0, 0.0]),
        (0.5, 0.9, [0.0, 0.0, 1.0], 0.004, [23.4, -1.2, 0.7]),
        (0.0166, 0.0309, [0.0, -1.0, 0.004], 0.0, [-8100.0, 3000.0, 12.0]),
        (1.0, 2.0, [-0.413, 0.891, 0.187], 0.01, [5.0, 5.0, -5.0]),
    ]

    def _run_js(self):
        script = "\n".join([
            "var window = {};",
            _extract_js_function("_planeBasis"),
            _extract_js_function("_ringMesh"),
            "var cases = %s;" % json.dumps(self.CASES),
            "var out = [];",
            "for (var c = 0; c < cases.length; c++) {",
            "  var a = cases[c];",
            "  var m = _ringMesh(a[0], a[1], a[2], a[3], 180, a[4]);",
            "  out.push({x: m.x, y: m.y, z: m.z});",
            "}",
            "console.log(JSON.stringify(out));",
        ])
        proc = subprocess.run(["node", "-e", script], capture_output=True,
                              text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    def test_the_viewer_builds_the_same_ring_python_does(self):
        import numpy as np
        from hybrasil.models.system import BeltZone
        from hybrasil.viz.static_plot import _belt_trace

        for (inner, outer, normal, offset, centre), got in zip(
                self.CASES, self._run_js()):
            zone = BeltZone("ring", r_inner_au=inner, r_outer_au=outer,
                            normal=tuple(normal), offset_au=offset)
            trace = _belt_trace(zone, centre=tuple(centre))
            for axis, want in zip("xyz", (trace.x, trace.y, trace.z)):
                assert np.allclose(np.asarray(got[axis]), np.asarray(want),
                                   rtol=0, atol=1e-9), (
                    f"{axis} disagrees for centre {centre}")

    def test_a_centred_ring_is_not_the_same_as_an_uncentred_one(self):
        # Guards the guard: if the centre were dropped on both sides at once
        # the comparison above would still pass.
        import numpy as np
        rings = self._run_js()
        assert not np.allclose(np.asarray(rings[0]["x"]),
                               np.asarray(rings[1]["x"]))


class TestOneCopyForBothViewers:
    """The band equation, ring, panel and info panel exist once, in band_kit.js.

    Both viewers carry that file verbatim: the Plotly viewer spliced into its
    script, the three.js viewer wrapped and exported.  A copy edited in one
    place and not the other is the drift this layout exists to prevent.
    """

    def test_the_plotly_viewer_carries_the_kit_verbatim(self):
        assert BAND_KIT_JS in _ZOOM_JS

    def test_the_three_viewer_carries_the_kit_verbatim(self):
        from hybrasil.viz.three_viewer import kit_script
        assert BAND_KIT_JS in kit_script()

    def test_the_kit_holds_what_both_share(self):
        for fn in ("_bandRadiiAU", "_liquidRangeK", "_bandName", "_ringMesh",
                   "_stackOffsetsByCentre", "_nameMatches", "showInfoPanel",
                   "_bandPanel"):
            assert f"function {fn}(" in BAND_KIT_JS, fn
            assert _ZOOM_JS.count(f"function {fn}(") == 1, f"{fn} defined twice"

    def test_the_panel_hands_its_values_to_the_caller(self):
        # Coalesced, then handed over: the panel knows nothing about Plotly.
        panel = BAND_KIT_JS[BAND_KIT_JS.index("function _bandPanel("):]
        assert "opts.onChange(_bandP, _bandA, _bandG)" in panel
        assert "Plotly" not in panel and "gd" not in panel.split("(")[1]
