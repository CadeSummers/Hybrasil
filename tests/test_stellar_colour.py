# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the star-colour correction on solvent bands.

A blackbody band takes a star's luminosity and nothing else.  A red dwarf's
light is scattered less and absorbed more in the near-IR, so the same flux
keeps a planet warmer; Kopparapu et al. 2013 quantify it as a Teff-dependent
effective flux.  `mechanics.stellar_colour` turns their runaway-greenhouse
limit into a factor on absorbed flux, and every band around a star scales by
its square root.
"""

import json
import math
import shutil
import subprocess

import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.mechanics.solvent_bands import (
    SOLVENTS,
    WATER,
    SolventChoice,
    band_absent_reason,
    colour_note,
    solvent_band_at_albedo,
    solvent_zones,
)
from hybrasil.mechanics.stellar_colour import (
    KOPPARAPU_2013_RUNAWAY,
    TEFF_RANGE_K,
    colour_factor,
    is_clamped,
    seff_runaway,
)
from hybrasil.mechanics.units import T_SUN_K

PROXIMA_B_AU = 0.04857


class TestTheFactor:
    def test_the_sun_is_exactly_one(self):
        # Normalised at this code's own solar temperature, so the Solar
        # System cannot move by a rounding error.
        assert colour_factor(T_SUN_K) == 1.0

    def test_the_coefficients_are_kopparapus(self):
        # Table 3, Runaway Greenhouse column, arXiv:1301.6674v2.
        assert KOPPARAPU_2013_RUNAWAY == (1.0512, 1.3242e-4, 1.5418e-8,
                                          -7.9895e-12, -1.8328e-15)
        assert seff_runaway(5780.0) == pytest.approx(1.0512)

    def test_proxima(self):
        # Kopparapu's own S_eff at 2980 K is 0.864; the workbook's HZ columns
        # for Proxima imply 0.863, so this is the same fit the sheet uses.
        assert seff_runaway(2980.0) == pytest.approx(0.864, abs=1e-3)
        assert colour_factor(2980.0) == pytest.approx(1.2154, abs=1e-4)

    def test_redder_is_more(self):
        temps = [7000, 6200, 5772, 5000, 4000, 3200, 2700]
        factors = [colour_factor(t) for t in temps]
        assert factors == sorted(factors)
        assert colour_factor(6212.0) < 1.0 < colour_factor(5260.0)

    def test_outside_the_fit_is_clamped(self):
        # TRAPPIST-1 at 2516 K is below the fit's 2600 K floor; a quartic
        # extrapolated turns over, so the end of the range is used instead.
        assert colour_factor(2516.0) == colour_factor(TEFF_RANGE_K[0])
        assert colour_factor(9000.0) == colour_factor(TEFF_RANGE_K[1])
        assert is_clamped(2516.0) and not is_clamped(2980.0)

    @pytest.mark.parametrize("teff", [None, 0.0, -5.0])
    def test_an_unknown_temperature_gets_no_correction(self, teff):
        assert colour_factor(teff) == 1.0


class TestEveryBandMovesTogether:
    @pytest.mark.parametrize("g", [0.0, 33.0, 120.0])
    def test_every_solvent_scales_by_the_same_root(self, g):
        # The factor multiplies absorbed flux, never a solvent's
        # temperatures, so each ring moves by exactly sqrt(f) -- the same for
        # water, methane and sulfur -- and no band appears or disappears.
        f = colour_factor(2980.0)
        for solvent in SOLVENTS.values():
            bare = solvent_band_at_albedo(0.00151, solvent, 1.0, 0.3, True, g)
            red = solvent_band_at_albedo(0.00151, solvent, 1.0, 0.3, True, g, f)
            assert (bare is None) == (red is None), solvent.key
            if bare:
                assert red[0] / bare[0] == pytest.approx(math.sqrt(f))
                assert red[1] / bare[1] == pytest.approx(math.sqrt(f))

    def test_presence_is_the_solvents_business(self):
        assert band_absent_reason(WATER, 1.0, True, 400.0) is not None
        assert solvent_band_at_albedo(1.0, WATER, 1.0, 0.3, True, 400.0,
                                      1.6) is None

    def test_zones_carry_the_factor_to_the_viewer(self):
        zones = solvent_zones(0.00151, SOLVENTS.values(), colour=1.2)
        assert {z.colour_factor for z in zones} == {1.2}

    def test_the_scene_is_claimed_with_the_factor(self):
        # A band moved outward must not grow out of a box sized without it.
        plain = solvent_zones(0.00151, (WATER,))[0]
        red = solvent_zones(0.00151, (WATER,), colour=1.2)[0]
        assert red.scene_claim_au == pytest.approx(
            plain.scene_claim_au * math.sqrt(1.2))


class TestTheBuiltInSystems:
    def _water(self, system, star):
        return next(z for z in system.belt_zones
                    if z.centre_body == star and z.solvent_key == WATER.key)

    def test_the_solar_system_does_not_move(self):
        on = get_builtin_system("solar", SolventChoice.parse("all"))
        off = get_builtin_system("solar", SolventChoice.parse(
            "all", star_colour=False))
        assert ([(z.r_inner_au, z.r_outer_au) for z in on.belt_zones]
                == [(z.r_inner_au, z.r_outer_au) for z in off.belt_zones])

    def test_proxima_moves_out_by_the_root_of_its_factor(self):
        on = get_builtin_system("proxima-centauri")
        off = get_builtin_system("proxima-centauri",
                                 SolventChoice.parse("water", star_colour=False))
        w_on = self._water(on, "Proxima Centauri")
        w_off = self._water(off, "Proxima Centauri")
        assert w_on.colour_factor == pytest.approx(colour_factor(2980.0))
        assert w_off.colour_factor == 1.0
        assert w_on.r_outer_au / w_off.r_outer_au == pytest.approx(
            math.sqrt(colour_factor(2980.0)))

    def test_proxima_b_is_just_outside_at_earths_greenhouse(self):
        # Pinned so the marginal result stays visible: star colour alone
        # moves the water band to within 0.0005 AU of Proxima b, and the
        # greenhouse has to reach 34.05 K -- one kelvin past Earth's -- to put
        # it inside.  Nobody should read the correction as having "fixed" the
        # habitable zone.
        f = colour_factor(2980.0)

        def outer(g):
            return solvent_band_at_albedo(0.00151, WATER, 1.0, 0.3, True, g, f)[1]

        assert outer(33.0) < PROXIMA_B_AU < outer(33.0) + 0.0005
        assert outer(34.0) < PROXIMA_B_AU < outer(34.1)

    def test_every_star_in_alpha_centauri_gets_its_own_factor(self):
        system = get_builtin_system("alpha-centauri")
        by_star = {z.centre_body: z.colour_factor for z in system.belt_zones}
        assert by_star["Alpha Centauri A"] == pytest.approx(colour_factor(5790.0))
        assert by_star["Alpha Centauri B"] == pytest.approx(colour_factor(5260.0))
        assert by_star["Proxima Centauri"] == pytest.approx(colour_factor(2980.0))

    def test_a_star_with_no_temperature_is_left_alone_and_says_so(self):
        system = get_builtin_system("55-cancri")
        b = [z for z in system.belt_zones if z.centre_body == "55 Cancri B"]
        assert b and all(z.colour_factor == 1.0 for z in b)
        assert "unknown" in colour_note(None)

    def test_the_description_names_the_correction(self):
        system = get_builtin_system("proxima-centauri")
        assert "Kopparapu et al. 2013" in system.description
        assert "2980 K" in system.description
        trappist = get_builtin_system("trappist-1")
        assert "taken at 2600 K" in trappist.description


class TestTheSwitch:
    def test_the_cli_defaults_on_and_turns_off(self):
        from hybrasil.cli import build_parser

        assert build_parser().parse_args([]).star_colour == "on"
        assert build_parser().parse_args(
            ["--star-colour", "off"]).star_colour == "off"

    def test_off_is_a_different_figure(self):
        # The registry caches by cache_key, so it has to include the switch.
        assert (SolventChoice.parse("water").cache_key
                != SolventChoice.parse("water", star_colour=False).cache_key)

    def test_the_flag_reaches_the_choice(self, monkeypatch):
        from hybrasil import cli

        seen = {}
        real = SolventChoice.parse

        def spy(*args, **kwargs):
            seen["choice"] = real(*args, **kwargs)
            raise SystemExit(0)

        monkeypatch.setattr(cli.SolventChoice, "parse", spy)
        with pytest.raises(SystemExit):
            cli.main(["--star-colour", "off"])
        assert seen["choice"].star_colour is False


class TestTheViewerGetsIt:
    def test_the_band_meta_carries_the_factor(self):
        from hybrasil.viz.static_plot import band_meta

        zone = solvent_zones(0.00151, (WATER,), colour=1.2154)[0]
        assert band_meta(zone)["colour"] == pytest.approx(1.2154)

    @pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
    def test_the_viewer_applies_it_the_way_python_does(self):
        from hybrasil.viz.export import build_solvent_table_js
        from tests.test_band_sliders import _extract_js_function

        cases = [(1.0, 0.3, 33.0, 1.0), (1.0, 0.3, 33.0, 1.2154),
                 (7.5, 0.1, 90.0, 1.6), (40.0, 0.5, 0.0, 0.95)]
        script = "\n".join([
            "var window = {};",
            build_solvent_table_js(SolventChoice.parse("all")),
            _extract_js_function("_bandConst"),
            _extract_js_function("_liquidRangeK"),
            _extract_js_function("_bandRadiiAU"),
            "var cases = %s;" % json.dumps(cases),
            "var keys = Object.keys(window._SA_SOLVENTS), out = [];",
            "for (var c = 0; c < cases.length; c++) {",
            "  var row = {};",
            "  for (var k = 0; k < keys.length; k++) {",
            "    var meta = {solvent: keys[k], lum: 0.00151, ceiling: true,",
            "                colour: cases[c][3]};",
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
        compared = 0
        for (p, a, g, f), row in zip(cases, json.loads(proc.stdout)):
            for key, solvent in SOLVENTS.items():
                want = solvent_band_at_albedo(0.00151, solvent, p, a, True, g, f)
                got = row[key]
                assert (want is None) == (got is None), (key, p, g, f)
                if want:
                    compared += 1
                    assert got[0] == pytest.approx(want[0], rel=1e-12)
                    assert got[1] == pytest.approx(want[1], rel=1e-12)
        assert compared > 10
