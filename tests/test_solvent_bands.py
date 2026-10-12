# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for solvent liquid bands.

The reference figures come from the catalog workbook's "Orbital Bands" tab,
which is computed independently of this code.  Reproducing all seven of its
pressure columns to two decimal places is what pins the equation down.
"""

import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.mechanics.solvent_bands import (
    ALBEDO_HIGH,
    ALBEDO_LOW,
    DEFAULT_ALBEDO,
    DEFAULT_GREENHOUSE_K,
    WATER,
    Solvent,
    equilibrium_distance_au,
    solvent_band_au,
    solvent_band_note,
    solvent_belt_zones,
    widest_band_outer_au,
)
from hybrasil.mechanics.time_series import (
    compute_scene_extent,
    system_orbit_paths,
    system_positions_at,
)
from hybrasil.mechanics.units import J2000, T_EQ_1AU_K
from hybrasil.viz.export import _ZOOM_JS, save_html
from hybrasil.viz.static_plot import build_static_figure, belt_scene_extent


# Workbook "Orbital Bands", the Water (H2O) row, in AU:
# pressure -> (conservative, optimistic)
WORKBOOK_WATER = {
    0.1:   ((0.76, 0.87), (0.64, 1.04)),
    0.5:   ((0.62, 0.87), (0.52, 1.04)),
    1.0:   ((0.56, 0.87), (0.47, 1.04)),
    5.0:   ((0.43, 0.87), (0.36, 1.04)),
    10.0:  ((0.38, 0.87), (0.32, 1.04)),
    50.0:  ((0.27, 0.87), (0.22, 1.04)),
    100.0: ((0.23, 0.87), (0.19, 1.04)),
}


class TestReferenceTemperature:
    def test_matches_the_workbook_constant(self):
        assert T_EQ_1AU_K == pytest.approx(278.3298873, abs=1e-4)

    def test_earth_albedo_equilibrium_temperature(self):
        # Earth's blackbody temperature at A = 0.3 is the textbook 255 K.
        d = equilibrium_distance_au(255.0, 1.0, 0.3)
        assert d == pytest.approx(1.0, abs=0.01)


class TestWaterBandAgainstWorkbook:
    @pytest.mark.parametrize("pressure_bar", sorted(WORKBOOK_WATER))
    def test_every_pressure_column_reproduced(self, pressure_bar):
        expected_cons, expected_opt = WORKBOOK_WATER[pressure_bar]
        band = solvent_band_au(1.0, WATER, pressure_bar)
        assert tuple(round(v, 2) for v in band.conservative) == expected_cons
        assert tuple(round(v, 2) for v in band.optimistic) == expected_opt

    def test_optimistic_encloses_conservative(self):
        band = solvent_band_au(1.0)
        assert band.optimistic[0] < band.conservative[0]
        assert band.optimistic[1] > band.conservative[1]

    def test_earth_sits_inside_the_optimistic_band(self):
        inner, outer = solvent_band_au(1.0).optimistic
        assert inner < 1.0 < outer

    def test_band_omitted_where_the_solvent_has_no_liquid_phase(self):
        assert solvent_band_au(1.0, WATER, 0.001) is None

    def test_unknown_luminosity_yields_no_band(self):
        assert solvent_band_au(None) is None
        assert solvent_band_au(0.0) is None


class TestLuminosityScaling:
    def test_band_scales_as_sqrt_luminosity(self):
        sun = solvent_band_au(1.0)
        bright = solvent_band_au(4.0)
        for a, b in zip(sun.conservative, bright.conservative):
            assert b == pytest.approx(a * 2.0)

    def test_dim_star_band_is_far_closer_in(self):
        # TRAPPIST-1 at L = 5.286e-4: a band two orders of magnitude tighter
        # than the Sun's, which is the whole point of computing it per system.
        band = solvent_band_au(0.0005285766791)
        assert band.conservative[0] == pytest.approx(0.0128, abs=5e-4)
        assert band.conservative[1] == pytest.approx(0.0200, abs=5e-4)
        assert band.optimistic[1] < solvent_band_au(1.0).optimistic[0] / 10


class TestEmptyConservativeBand:
    def test_narrow_liquid_window_inverts_the_intersection(self):
        # The albedo bracket spreads the edges by sqrt(1 - 0.3) = 0.837.  A
        # liquid window narrower than that ratio in temperature has no
        # distance where the solvent is liquid at every albedo.
        narrow = Solvent(key="narrow", name="Narrow", formula="X",
                         color="#000000", phase_points={1.0: (0.0, 2.0)})
        band = solvent_band_au(1.0, narrow)
        assert band.conservative is None
        assert band.optimistic[0] < band.optimistic[1]

    def test_empty_conservative_band_renders_one_ring(self):
        narrow = Solvent(key="narrow", name="Narrow", formula="X",
                         color="#000000", phase_points={1.0: (0.0, 2.0)})
        zones = solvent_belt_zones(1.0, narrow)
        assert len(zones) == 1
        assert "optimistic" in zones[0].name


class TestBeltZones:
    def test_core_and_two_margins(self):
        zones = solvent_belt_zones(1.0)
        assert len(zones) == 3
        margins = [z for z in zones if "margin" in z.name]
        core = [z for z in zones if "margin" not in z.name]
        assert len(margins) == 2 and len(core) == 1

    def test_rings_are_disjoint_so_they_cannot_z_fight(self):
        zones = sorted(solvent_belt_zones(1.0), key=lambda z: z.r_inner_au)
        for lower, upper in zip(zones, zones[1:]):
            assert lower.r_outer_au == pytest.approx(upper.r_inner_au)

    def test_margins_share_one_legend_entry(self):
        margins = [z for z in solvent_belt_zones(1.0) if "margin" in z.name]
        assert [z.show_in_legend for z in margins] == [True, False]
        assert len({z.legend_group for z in margins}) == 1

    def test_core_is_the_more_opaque_ring(self):
        zones = solvent_belt_zones(1.0)
        core = next(z for z in zones if "margin" not in z.name)
        margin = next(z for z in zones if "margin" in z.name)
        assert core.opacity > margin.opacity

    def test_band_is_a_deeper_blue_than_the_kuiper_belt(self):
        kuiper = next(z for z in get_builtin_system("solar").belt_zones
                      if z.name == "Kuiper Belt")
        water = next(z for z in solvent_belt_zones(1.0) if "margin" not in z.name)

        def rgb(hex_color):
            h = hex_color.lstrip("#")
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

        k_r, k_g, k_b = rgb(kuiper.color)
        w_r, w_g, w_b = rgb(water.color)
        assert w_b > k_b                          # bluer
        assert w_r < k_r and w_g < k_g            # with less red and green

    def test_band_asks_to_stay_in_frame(self):
        assert all(z.extends_scene for z in solvent_belt_zones(1.0))

    def test_no_zones_without_a_luminosity(self):
        assert solvent_belt_zones(None) == []


class TestDescriptionNote:
    def test_note_states_the_span_and_the_caveat(self):
        # The drawn ring, at the albedo the slider starts on. The nested
        # conservative/optimistic pair is what the same sum gives when albedo
        # is *unknown*; with a slider setting it there is nothing to bracket.
        note = solvent_band_note(1.0)
        assert "0.466-0.869 AU" in note
        assert "not a published habitable zone" in note
        assert f"albedo {DEFAULT_ALBEDO:g}" in note
        assert "sliders" in note

    def test_no_note_without_a_luminosity(self):
        assert solvent_band_note(None) == ""


class TestBuiltinSystems:
    @pytest.mark.parametrize("key", ["solar", "trappist-1", "alpha-centauri",
                                     "proxima-centauri", "upsilon-andromedae"])
    def test_every_builtin_system_carries_a_water_band(self, key):
        system = get_builtin_system(key)
        assert [z for z in system.belt_zones if z.name.startswith("Water band")]
        assert "water band at 1 bar" in system.description

    def test_the_band_differs_per_star(self):
        solar = get_builtin_system("solar")
        trappist = get_builtin_system("trappist-1")

        def core(system):
            z = next(z for z in system.belt_zones
                     if z.name == "Water band (1 bar)")
            return (z.r_inner_au, z.r_outer_au)

        assert core(solar)[0] > core(trappist)[1] * 10

    def test_solar_keeps_its_existing_belts(self):
        names = [z.name for z in get_builtin_system("solar").belt_zones]
        assert names[:2] == ["Asteroid Belt", "Kuiper Belt"]

    def test_host_luminosities_are_recorded(self):
        sun = get_builtin_system("solar").get_body("Sun")
        assert sun.luminosity_sun == 1.0
        trappist = get_builtin_system("trappist-1").get_body("TRAPPIST-1")
        assert 0 < trappist.luminosity_sun < 0.001


class TestSceneExtent:
    def test_floor_widens_the_scene(self):
        assert compute_scene_extent({}, min_extent_au=4.0) == (4.4, 4.4, 4.4)

    def test_floor_never_shrinks_the_scene(self):
        wide = compute_scene_extent({"a": ([0.0, 50.0], [0.0, 0.0], [0.0, 0.0])})
        assert compute_scene_extent(
            {"a": ([0.0, 50.0], [0.0, 0.0], [0.0, 0.0])}, min_extent_au=1.0) == wide

    def test_only_solvent_bands_claim_room(self):
        # Filtering to Mercury must not zoom out to the Kuiper belt, but the
        # water band, which has no other representation, must stay in frame.
        system = get_builtin_system("solar").filter_bodies(["Mercury"])
        assert belt_scene_extent(system) == pytest.approx(
            widest_band_outer_au(1.0, WATER, 1.0,
                                 greenhouse_k=DEFAULT_GREENHOUSE_K))

    def test_the_scene_is_sized_for_the_darkest_albedo_the_slider_allows(self):
        # Not for the band being drawn: dragging albedo down pushes a band
        # outward, and it must not grow out of the box while doing so.
        system = get_builtin_system("solar").filter_bodies(["Mercury"])
        zone = next(z for z in system.belt_zones if z.is_solvent_band)
        assert zone.scene_claim_au > zone.r_outer_au
        assert belt_scene_extent(system) == pytest.approx(zone.scene_claim_au)

    def test_band_fits_inside_the_rendered_scene(self):
        system = get_builtin_system("solar").filter_bodies(["Mercury"])
        orbit_paths, coil_paths = system_orbit_paths(system)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  orbit_paths, coil_paths=coil_paths)
        half = fig.layout.scene.xaxis.range[1]
        assert half > widest_band_outer_au(1.0, WATER, 1.0,
                                           greenhouse_k=DEFAULT_GREENHOUSE_K)

    def test_band_meshes_reach_the_figure(self):
        system = get_builtin_system("trappist-1")
        orbit_paths, coil_paths = system_orbit_paths(system)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  orbit_paths, coil_paths=coil_paths)
        meshes = [t for t in fig.data if t.type == "mesh3d"]
        assert [t.name for t in meshes].count("Water band (1 bar)") == 1
        assert sum(1 for t in meshes if t.showlegend) == 1


class TestBandIsSearchable:
    """The band is not a body, so the search box has to reach it another way.

    The viewer's first-pass search only considers single-point traces, which
    are body markers.  A band is a 360-vertex mesh, so it needs the fallback
    pass; these guard the two halves of that contract.
    """

    def test_viewer_has_the_fallback_search(self):
        assert "function searchTraceGroup(" in _ZOOM_JS
        assert "function traceGroupTarget(" in _ZOOM_JS
        # zoomTo must accept the explicit extent the fallback computes, since a
        # band has no _SA_BODY_INFO entry to take one from.
        assert "function zoomTo(gd, x, y, z, name, halfOverride)" in _ZOOM_JS

    def test_band_traces_are_named_for_the_solvent(self):
        # "water" has to match, and match every ring of the band, or the jump
        # frames only part of it.
        names = [z.name for z in solvent_belt_zones(1.0)]
        assert len(names) == 3
        assert all(n.lower().startswith("water") for n in names)

    def test_band_names_survive_into_the_html(self, tmp_path):
        system = get_builtin_system("solar")
        orbit_paths, coil_paths = system_orbit_paths(system)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  orbit_paths, coil_paths=coil_paths)
        out = tmp_path / "solar.html"
        save_html(fig, str(out))
        html = out.read_text(encoding="utf-8")
        assert '"Water band (1 bar)"' in html
        assert "searchTraceGroup" in html
