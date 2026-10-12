# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the other seven solvents, against the workbook's own figures.

`test_solvent_bands.py` pins the equation down on water.  This file pins the
transcription down on everything else: every solvent, at every one of the
workbook's seven pressures, checked against the "Orbital Bands" tab rounded the
way that tab prints it.  Get a melting or boiling point wrong by a digit and
one of these fails.

The workbook prints two figures for sulfur, formamide and sulfuric acid: a
plain one from the boiling point, and a parenthesised "functional" one from the
limit that stops the substance working as a solvent first.  Both are here,
since both are reachable -- `--band-limit` chooses between them.
"""

import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.mechanics.solvent_bands import (
    AMMONIA,
    CARBON_DIOXIDE,
    DEFAULT_CHOICE,
    ETHANE,
    FORMAMIDE,
    METHANE,
    PRESSURES_BAR,
    SOLVENTS,
    Solvent,
    SULFUR,
    SULFURIC_ACID,
    WATER,
    SolventChoice,
    resolve_solvents,
    solvent_band_au,
    solvent_notes,
    solvent_zones,
    stack_offsets_au,
)
from hybrasil.mechanics.time_series import (
    system_orbit_paths,
    system_positions_at,
)
from hybrasil.mechanics.units import J2000
from hybrasil.viz.static_plot import build_static_figure

# Workbook "Orbital Bands", every row but water, at L = 1.0, in AU:
# solvent -> pressure -> (conservative, optimistic), where conservative is
# None for an inverted (empty) band and the whole entry is absent where the
# workbook says n/a.  Figures are the tab's own, to two decimals.
WORKBOOK = {
    "methane": {
        0.5:   ((7.20, 7.89), (6.02, 9.43)),
        1.0:   ((6.21, 7.89), (5.20, 9.43)),
        5.0:   ((4.24, 7.63), (3.55, 9.12)),
        10.0:  ((3.51, 7.63), (2.93, 9.12)),
    },
    "ethane": {
        0.1:   ((3.42, 7.94), (2.86, 9.49)),
        0.5:   ((2.60, 7.94), (2.18, 9.49)),
        1.0:   ((2.27, 7.94), (1.90, 9.49)),
        5.0:   ((1.60, 7.80), (1.33, 9.32)),
        10.0:  ((1.33, 7.80), (1.11, 9.32)),
    },
    "ammonia": {
        0.1:   (None,         (1.62, 2.03)),   # the workbook's EMPTY BAND cell
        0.5:   ((1.52, 1.70), (1.27, 2.03)),
        1.0:   ((1.35, 1.70), (1.13, 2.03)),
        5.0:   ((1.01, 1.68), (0.84, 2.01)),
        10.0:  ((0.87, 1.68), (0.73, 2.01)),
        50.0:  ((0.59, 1.67), (0.50, 1.99)),
        100.0: ((0.49, 1.65), (0.41, 1.97)),
    },
    "formamide": {
        0.1:   ((0.43, 0.86), (0.36, 1.02)),
        0.5:   ((0.36, 0.86), (0.30, 1.02)),
        1.0:   ((0.33, 0.86), (0.28, 1.02)),
    },
    "sulfuric-acid": {
        0.1:   ((0.31, 0.81), (0.26, 0.97)),
        0.5:   ((0.24, 0.81), (0.20, 0.97)),
        1.0:   ((0.21, 0.81), (0.17, 0.97)),
    },
    "sulfur": {
        0.1:   ((0.22, 0.43), (0.18, 0.51)),
        0.5:   ((0.17, 0.43), (0.14, 0.51)),
        1.0:   ((0.15, 0.43), (0.13, 0.51)),
        5.0:   ((0.11, 0.43), (0.09, 0.51)),
        10.0:  ((0.10, 0.43), (0.08, 0.51)),
        50.0:  ((0.07, 0.43), (0.05, 0.51)),
        100.0: ((0.05, 0.43), (0.05, 0.51)),
    },
    "carbon-dioxide": {
        10.0:  (None,         (1.19, 1.65)),   # the workbook's EMPTY BAND cell
        50.0:  ((0.94, 1.36), (0.78, 1.63)),
        100.0: ((0.84, 1.34), (0.70, 1.60)),
    },
}

# The parenthesised figures: the boiling point replaced by the limit that
# stops the substance functioning as a solvent.  Only where the cap bites.
WORKBOOK_FUNCTIONAL = {
    "formamide": {
        0.5:   ((0.377, 0.856), (0.316, 1.023)),
        1.0:   ((0.377, 0.856), (0.316, 1.023)),
    },
    "sulfuric-acid": {
        1.0:   ((0.236, 0.808), (0.197, 0.966)),
    },
    # Identical at every pressure: the lambda transition does not move, so
    # pressure buys sulfur nothing usable anywhere.
    "sulfur": {p: ((0.415, 0.430), (0.347, 0.514)) for p in PRESSURES_BAR},
}

_CASES = [(SOLVENTS[k], p) for k, cols in WORKBOOK.items() for p in cols]
_FUNCTIONAL_CASES = [(SOLVENTS[k], p)
                     for k, cols in WORKBOOK_FUNCTIONAL.items() for p in cols]


def _id(value):
    """pytest hands each parameter over one at a time, not as the pair."""
    return value.key if isinstance(value, Solvent) else f"{value:g}bar"


class TestEveryWorkbookCell:
    @pytest.mark.parametrize("solvent,pressure", _CASES, ids=_id)
    def test_thermodynamic_band_reproduced(self, solvent, pressure):
        expected_cons, expected_opt = WORKBOOK[solvent.key][pressure]
        band = solvent_band_au(1.0, solvent, pressure, apply_ceiling=False)
        assert band is not None
        assert tuple(round(v, 2) for v in band.optimistic) == expected_opt
        if expected_cons is None:
            assert band.conservative is None
        else:
            assert tuple(round(v, 2) for v in band.conservative) == expected_cons

    @pytest.mark.parametrize("solvent,pressure", _FUNCTIONAL_CASES, ids=_id)
    def test_functional_band_reproduced(self, solvent, pressure):
        expected_cons, expected_opt = WORKBOOK_FUNCTIONAL[solvent.key][pressure]
        band = solvent_band_au(1.0, solvent, pressure)
        assert band.capped
        assert tuple(round(v, 3) for v in band.conservative) == expected_cons
        assert tuple(round(v, 3) for v in band.optimistic) == expected_opt

    @pytest.mark.parametrize("solvent", list(SOLVENTS.values()), ids=lambda s: s.key)
    def test_no_band_where_the_workbook_has_none(self, solvent):
        # Water is the one row with a band in all seven columns, and it has
        # its own file; every other row has n/a cells, and each must stay a
        # None with a stated reason rather than a computed figure.
        printed = set(WORKBOOK.get(solvent.key, {p: None for p in PRESSURES_BAR}))
        for pressure in PRESSURES_BAR:
            if pressure in printed:
                continue
            assert solvent_band_au(1.0, solvent, pressure) is None
            assert solvent.absent_reason(pressure)

    def test_uncapped_solvents_are_unaffected_by_the_ceiling(self):
        for solvent in (METHANE, ETHANE, AMMONIA, WATER, CARBON_DIOXIDE):
            capped = solvent_band_au(1.0, solvent, 10.0)
            plain = solvent_band_au(1.0, solvent, 10.0, apply_ceiling=False)
            assert capped == plain


class TestFunctionalCeiling:
    def test_sulfur_band_does_not_move_with_pressure(self):
        # The lambda transition is fixed at 159 C while the boiling point
        # climbs, so every pressure gives the same usable band.
        bands = {solvent_band_au(1.0, SULFUR, p).conservative
                 for p in PRESSURES_BAR}
        assert len(bands) == 1

    def test_sulfurs_usable_band_is_far_narrower_than_its_liquid_range(self):
        usable = solvent_band_au(1.0, SULFUR, 1.0).conservative
        liquid = solvent_band_au(1.0, SULFUR, 1.0, apply_ceiling=False).conservative
        assert (usable[1] - usable[0]) == pytest.approx(0.015, abs=0.001)
        assert (liquid[1] - liquid[0]) > 10 * (usable[1] - usable[0])

    def test_capping_pushes_the_inner_edge_outward(self):
        # Capping the temperature can only move the hot edge further out, so a
        # functional band is never wider at the inner edge than the plain one.
        for solvent in (SULFUR, FORMAMIDE, SULFURIC_ACID):
            capped = solvent_band_au(1.0, solvent, 1.0)
            plain = solvent_band_au(1.0, solvent, 1.0, apply_ceiling=False)
            assert capped.conservative[0] > plain.conservative[0]
            assert capped.conservative[1] == pytest.approx(plain.conservative[1])

    def test_capped_bands_say_so_in_their_name(self):
        names = [z.name for z in solvent_zones(1.0, [SULFUR])]
        assert all("functional" in n for n in names)
        assert all("functional" not in z.name for z in solvent_zones(1.0, [WATER]))


class TestSolarSystemPlacement:
    """The workbook's "Bodies in 1 bar Optimistic Band" column, checked."""

    @pytest.mark.parametrize("solvent,pressure,body_au", [
        (METHANE, 1.0, 5.20),          # Jupiter
        (ETHANE, 1.0, 2.77),           # Ceres
        (AMMONIA, 1.0, 1.52),          # Mars
        (WATER, 1.0, 0.72),            # Venus
        (WATER, 1.0, 1.00),            # Earth
        (FORMAMIDE, 1.0, 0.39),        # Mercury
        (FORMAMIDE, 1.0, 1.00),        # Earth
        (SULFURIC_ACID, 1.0, 0.72),    # Venus, where the droplets actually are
        (CARBON_DIOXIDE, 50.0, 1.00),  # Earth
        (CARBON_DIOXIDE, 50.0, 1.52),  # Mars
    ])
    def test_body_sits_inside_the_optimistic_band(self, solvent, pressure, body_au):
        inner, outer = solvent_band_au(1.0, solvent, pressure,
                                       apply_ceiling=False).optimistic
        assert inner < body_au < outer

    def test_sulfurs_usable_band_contains_nothing(self):
        # Mercury at 0.387 AU falls just short of the 0.415 AU inner edge.
        inner, outer = solvent_band_au(1.0, SULFUR, 1.0).conservative
        assert not inner < 0.387 < outer

    @pytest.mark.parametrize("solvent,body_au,edge", [
        (METHANE, 9.54, 9.427),   # Saturn, past the outer edge by 0.11 AU
        (ETHANE, 1.52, 1.903),    # Mars, inside the inner edge by 0.38 AU
    ])
    def test_two_bodies_the_workbook_lists_are_actually_just_outside(
            self, solvent, body_au, edge):
        """The workbook's body column is looser than its own AU figures.

        Its "Bodies in 1 bar Optimistic Band" column names Saturn for methane
        and Mars for ethane, and its notes say the methane edge "sits at
        Saturn".  Neither body is in fact inside the band those same rows
        print.  The AU figures are what this code reproduces, so the near
        misses are recorded here rather than papered over -- if the workbook's
        temperatures are ever corrected, this is where it shows.
        """
        band = solvent_band_au(1.0, solvent, 1.0, apply_ceiling=False)
        assert not band.optimistic[0] < body_au < band.optimistic[1]
        assert min(abs(body_au - e) for e in band.optimistic) < 0.4
        assert edge in band.optimistic or round(edge, 3) in [
            round(v, 3) for v in band.optimistic]


class TestStacking:
    def test_a_lone_band_stays_on_its_plane(self):
        assert all(z.offset_au == 0.0 for z in solvent_zones(1.0, [WATER]))

    def test_overlapping_bands_never_share_a_plane(self):
        # Only among the bands that are actually drawn: a solvent with no
        # liquid phase at this pressure is an empty ring at offset 0, and two
        # of those sharing a plane is two of nothing on one plane.
        drawn = [z for z in solvent_zones(1.0, SOLVENTS.values()) if z.r_outer_au > 0]
        planes = {z.name.split(" band")[0]: z.offset_au for z in drawn}
        assert len(set(planes.values())) == len(planes)

    def test_the_lift_is_negligible_against_the_band_itself(self):
        # The offset exists to break coplanarity, not to be seen: every band
        # sits within a few percent of its own outer radius of the ecliptic.
        for z in solvent_zones(1.0, SOLVENTS.values()):
            if z.r_outer_au > 0:
                assert abs(z.offset_au) < 0.05 * z.r_outer_au

    def test_offsets_are_ordered_by_band_size(self):
        bands = [solvent_band_au(1.0, s, 1.0) for s in (WATER, AMMONIA, ETHANE)]
        assert stack_offsets_au(bands) == sorted(stack_offsets_au(bands))

    def test_a_band_with_no_liquid_phase_takes_no_rank(self):
        # CO2 has no band at 1 bar. It still gets a trace -- the viewer's
        # sliders rewrite these in place, so the set cannot change size -- but
        # it takes no slot in the stack, and the solvents that are drawn keep
        # the consecutive ranks they would have had on their own.
        with_co2 = solvent_zones(1.0, [WATER, CARBON_DIOXIDE])
        alone = solvent_zones(1.0, [WATER])
        assert [z.name for z in with_co2] == ["Water band (1 bar)",
                                              "Carbon dioxide band (1 bar)"]
        assert with_co2[1].r_outer_au == 0.0
        assert with_co2[0].offset_au == alone[0].offset_au


class TestResolveSolvents:
    def test_default_is_water_alone(self):
        assert resolve_solvents(None) == [WATER]
        assert resolve_solvents("") == [WATER]

    def test_all_gives_the_whole_workbook(self):
        assert resolve_solvents("all") == list(SOLVENTS.values())

    @pytest.mark.parametrize("spec", ["co2", "CO2", "Carbon Dioxide",
                                      "carbon_dioxide", "carbon-dioxide"])
    def test_formulae_and_spacing_both_resolve(self, spec):
        assert resolve_solvents(spec) == [CARBON_DIOXIDE]

    def test_result_is_in_workbook_order_whatever_the_input_order(self):
        assert (resolve_solvents("water,methane,ammonia")
                == [METHANE, AMMONIA, WATER])

    def test_duplicates_collapse(self):
        assert resolve_solvents("water,h2o,Water") == [WATER]

    def test_unknown_name_names_the_alternatives(self):
        with pytest.raises(ValueError, match="methane"):
            resolve_solvents("nitrogen")


class TestNotes:
    def test_one_solvent_reads_as_the_ring_that_is_drawn(self):
        # The albedo-0.3 ring: inner edge from the boiling point, outer from
        # the melting point, both at the albedo the slider starts on.
        note = solvent_notes(1.0, [WATER])
        assert note.startswith("The water band at 1 bar spans 0.466-0.869 AU")
        assert "albedo 0.3" in note
        assert "not a published habitable zone" in note

    def test_many_solvents_carry_one_caveat_between_them(self):
        note = solvent_notes(1.0, SOLVENTS.values())
        assert note.count("not a published habitable zone") == 1
        for solvent in (METHANE, ETHANE, AMMONIA, WATER):
            assert solvent.name.lower() in note

    def test_an_absent_solvent_is_named_with_its_reason(self):
        note = solvent_notes(1.0, [WATER, CARBON_DIOXIDE])
        assert "carbon dioxide (below its triple point)" in note

    def test_a_capped_band_says_what_capped_it(self):
        assert "lambda transition" in solvent_notes(1.0, [SULFUR])
        assert "lambda transition" in solvent_notes(1.0, [WATER, SULFUR])

    def test_no_note_without_a_luminosity(self):
        assert solvent_notes(None, SOLVENTS.values()) == ""


class TestSystemsCarryTheChosenBands:
    def test_default_is_still_the_water_band_alone(self):
        system = get_builtin_system("solar")
        bands = [z for z in system.belt_zones if "band" in z.name]
        assert {z.name.split(" band")[0] for z in bands} == {"Water"}

    def test_choosing_solvents_changes_the_bands_drawn(self):
        # With no greenhouse offset, so the span is the workbook's own.
        system = get_builtin_system(
            "solar", SolventChoice.parse("methane,ammonia", greenhouse_k=0.0))
        drawn = {z.name.split(" band")[0] for z in system.belt_zones
                 if "band" in z.name}
        assert drawn == {"Methane", "Ammonia"}
        assert "methane 5.199-7.887 AU" in system.description

    def test_the_same_system_at_two_pressures_is_two_systems(self):
        # The registry caches by system name, so it has to key on the bands
        # too or the second call hands back the first one's figure.
        one = get_builtin_system("solar", SolventChoice.parse("ammonia", 1.0))
        fifty = get_builtin_system("solar", SolventChoice.parse("ammonia", 50.0))
        assert [z.name for z in one.belt_zones] != [z.name for z in fifty.belt_zones]

    @pytest.mark.parametrize("key", ["solar", "trappist-1", "alpha-centauri",
                                     "proxima-centauri", "upsilon-andromedae"])
    def test_every_builtin_takes_the_full_set(self, key):
        system = get_builtin_system(key, SolventChoice.parse("all"))
        drawn = {z.name.split(" band")[0] for z in system.belt_zones
                 if "band" in z.name}
        # Every solvent gets a trace, because the viewer's sliders rewrite them
        # in place and the set cannot change size as a band comes and goes.
        assert len(drawn) == 8
        # CO2 has no liquid phase at 1 bar, so its trace is an empty ring --
        # which is the result, and the description says why.  One per luminous
        # star, since each star gets its own stack: Alpha Centauri has three.
        empty = [z for z in system.belt_zones if z.r_outer_au == 0.0]
        assert all(z.name.startswith("Carbon dioxide band") for z in empty)
        stars = [b for b in system.bodies
                 if b.body_type == "star" and b.luminosity_sun]
        assert len(empty) == len(stars)

    def test_a_dim_star_scales_every_band_the_same_way(self):
        solar = get_builtin_system("solar", SolventChoice.parse("all"))
        trappist = get_builtin_system("trappist-1", SolventChoice.parse("all"))

        def core(system, solvent):
            return next(z for z in system.belt_zones
                        if z.name.startswith(solvent)).r_outer_au

        ratio = core(trappist, "Water") / core(solar, "Water")
        for solvent in ("Methane", "Ethane", "Ammonia", "Sulfur"):
            assert core(trappist, solvent) / core(solar, solvent) == pytest.approx(ratio)

    def test_bands_reach_the_figure_as_meshes(self):
        system = get_builtin_system("solar", SolventChoice.parse("all"))
        orbit_paths, coil_paths = system_orbit_paths(system)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  orbit_paths, coil_paths=coil_paths)
        meshes = [t for t in fig.data if t.type == "mesh3d"]
        # One ring per solvent -- one albedo, one band -- plus the asteroid
        # and Kuiper belts.  CO2's is empty at 1 bar but still a trace.
        assert len(meshes) == 8 + 2
        assert sum(1 for t in meshes if t.showlegend) == 8 + 2
        assert sum(1 for t in meshes if not len(t.x)) == 1

    def test_the_widest_band_sets_the_scene(self):
        system = get_builtin_system("solar", SolventChoice.parse("all"))
        system = system.filter_bodies(["Mercury"])
        orbit_paths, coil_paths = system_orbit_paths(system)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  orbit_paths, coil_paths=coil_paths)
        half = fig.layout.scene.xaxis.range[1]
        assert half > solvent_band_au(1.0, ETHANE).optimistic[1]


class TestDefaultChoice:
    def test_it_is_the_water_band_at_one_bar(self):
        assert DEFAULT_CHOICE.solvents == (WATER,)
        assert DEFAULT_CHOICE.pressure_bar == 1.0
        assert DEFAULT_CHOICE.apply_ceiling

    def test_cache_key_is_hashable(self):
        # Solvent carries dicts, so the choice itself is not hashable; the
        # registry leans on this instead.
        assert len({DEFAULT_CHOICE.cache_key,
                    SolventChoice.parse("all").cache_key}) == 2
