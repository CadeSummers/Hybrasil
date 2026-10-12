# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Planetless 4+ Stars systems: every hierarchy on the tab, built from the committed snapshot.

Castor proved the machinery on one system (tests/test_castor.py). These are the other 79, read by
hybrasil/data/planetless_loader.py rather than copied by hand, so what is checked here is that the loader
reads what the tab says and that the geometry comes out right for every one of them: each barycentre really is its
pair's centre of mass, every band is a flat disc, and a hypothetical star is drawn hollow.
"""
import numpy as np
import pytest

from hybrasil.data.builtin_systems import FEATURED_CATALOG_HOSTS
from hybrasil.data.planetless_loader import (PREFIX, build_planetless_system, parse_planetless,
                                                  planetless_entry, planetless_span_days)
from hybrasil.data.snapshot import load_snapshot_workbook
from hybrasil.mechanics.solvent_bands import SolventChoice
from hybrasil.mechanics.time_series import system_orbit_paths, system_positions_at
from hybrasil.mechanics.units import J2000
from hybrasil.viz.static_plot import build_static_figure
from tests.test_band_flatness import _check_figure

ALL_BANDS = SolventChoice.parse("all")
TIMES = [J2000, J2000 + 1234.5, J2000 + 20000.0]


@pytest.fixture(scope="module")
def systems():
    return parse_planetless(load_snapshot_workbook(), skip=FEATURED_CATALOG_HOSTS["castor"])


@pytest.fixture(scope="module")
def built(systems):
    return {host: build_planetless_system(ps, ALL_BANDS) for host, ps in systems.items()}


class TestTheTab:
    def test_every_system_but_castor(self, systems):
        assert len(systems) == 79
        assert "alf Gem" not in systems

    def test_every_pair_has_a_complete_orbit(self, systems):
        for ps in systems.values():
            for r in ps.rows:
                if r.separation_from:
                    missing = [k for k in ("a_au", "e", "period_d", "inclination_deg", "node_deg", "omega_deg",
                                           "periastron_jd", "omega_refers_to") if getattr(r, k) is None]
                    assert not missing, (r.name, missing)

    def test_every_node_has_a_mass(self, systems):
        for ps in systems.values():
            assert all(r.mass_sun for r in ps.rows), ps.host

    def test_the_hypothetical_stars_are_the_ones_the_tab_marks(self, systems):
        hypo = {n for ps in systems.values() for n in ps.hypothetical}
        # CD-77 1092 Ab was the third example until 2 Oct 2026, when that system (HD 207496) left the tab.
        # GJ 3347 Aa2 was the third until 7 Oct 2026, when it became a planet (a brown dwarf); 1 Hya Cb's mass
        # is only the typical-companion rule's, so it stays a star.
        assert {"GJ 187.2 Ab", "1 Hya Cb", "GJ 171.2 Ac"} <= hypo
        assert "GJ 187.2 Aa" not in hypo


class TestTheDrawing:
    def test_every_system_builds_with_one_star_at_the_origin(self, built):
        for host, s in built.items():
            origins = [b for b in s.bodies if b.elements is None]
            assert len(origins) == 1 and origins[0].body_type == "star", host

    def test_each_barycentre_is_the_centre_of_mass_of_its_pair(self, systems, built):
        # hierarchy.py's own pairing: a pair is a secondary and the primary its row names, and the subsystem
        # placed from that primary is the pair's barycentre.
        for host, ps in systems.items():
            s = built[host]
            mass = {r.name: r.mass_sun for r in ps.rows}
            sec_of = {r.separation_from: r.name for r in ps.rows if r.separation_from}
            for sub in (r for r in ps.rows if r.node_type == "subsystem"):
                prim = sub.barycentre_from
                sec = sec_of[prim]
                m1, m2 = mass[prim], mass[sec]
                for t in TIMES:
                    pos = {k: np.array(v) for k, v in system_positions_at(s, t).items()}
                    want = (m1 * pos[prim] + m2 * pos[sec]) / (m1 + m2)
                    gap = np.linalg.norm(pos[prim] - pos[sec])
                    assert np.linalg.norm(pos[sub.name] - want) <= 1e-3 * gap + 1e-9, (host, sub.name, t)

    def test_every_band_is_a_flat_disc(self, built):
        for host, s in built.items():
            paths, coils = system_orbit_paths(s, 360, J2000, J2000 + planetless_span_days(s))
            fig = build_static_figure(s, system_positions_at(s, J2000), paths, coil_paths=coils)
            _check_figure(fig, s, host)

    def test_a_hypothetical_star_is_hollow_and_says_what_it_is(self, built):
        s = built["1 Hya"]
        b = next(x for x in s.bodies if x.name == "1 Hya Cb")
        assert b.status == "hypothetical" and b.status_note == "Hypothetical and model-inferred"
        assert "hypothetical, model-inferred" in b.label()
        paths, coils = system_orbit_paths(s, 360, J2000, J2000 + planetless_span_days(s))
        fig = build_static_figure(s, system_positions_at(s, J2000), paths, coil_paths=coils)
        marker = next(t for t in fig.data if t.name == b.label() and t.mode and "markers" in t.mode)
        assert marker.marker.color == "rgba(0,0,0,0)" and marker.marker.line.width

    def test_hd_13507_has_two_hollow_brown_dwarfs_in_place_of_the_refuted_one(self, systems, built):
        # Grandjean et al. 2021 (hd13507.py, 4 Oct 2026). Brown dwarfs are planets since 7 Oct 2026
        # (migrate_bds.py): both are Unconfirmed rows round Ba, and the subsystems Bab and B collapsed into Ba.
        ps, s = systems["BD+39 496"], built["BD+39 496"]
        by = {p.name: p for p in ps.planets}
        b, c = by["BD+39 496 Bb"], by["BD+39 496 Bc"]
        assert (b.planet_host, b.semi_major_axis_au, b.eccentricity) == ("BD+39 496 Ba", 4.2, 0.27)
        assert (c.planet_host, c.semi_major_axis_au, c.eccentricity) == ("BD+39 496 Ba", 5.4, 0.2)
        assert {r.name for r in ps.rows} == {"BD+39 496 Ba", "BD+39 496 A", "BD+39 496 Aa", "BD+39 496 Ab"}
        assert len(ps.stars) == 3
        bodies = {x.name: x for x in s.bodies}
        assert all(bodies[n].body_type == "planet" and bodies[n].parent == "BD+39 496 Ba"
                   and bodies[n].status == "hypothetical" for n in ("BD+39 496 Bb", "BD+39 496 Bc"))

    def test_a_candidate_brown_dwarf_is_a_hollow_planet(self, built):
        b = next(x for x in built["GJ 3347"].bodies if x.name == "GJ 3347 Aa2")
        assert (b.body_type, b.parent, b.status) == ("planet", "GJ 3347 Aa1", "hypothetical")

    def test_the_span_shows_the_tightest_pair_turning(self, built):
        for host, s in built.items():
            shortest = min(b.elements.period for b in s.bodies if b.elements is not None)
            span = planetless_span_days(s)
            assert 5.0 <= span <= 100 * 365.25
            assert span >= min(1.2 * shortest, 100 * 365.25) - 1e-9, host


class TestTheListing:
    def test_an_entry_is_planetless_and_findable_by_its_stars(self, systems):
        e = planetless_entry(systems["1 Hya"])
        assert e["id"] == PREFIX + "1 Hya" and e["kind"] == "planetless" and not e["featured"]
        assert "1 Hya Ab" in e["aliases"] and e["n_planets"] == 0
        assert e["n_stars"] == 6                      # Aa1, Aa2, Ab, B, Ca, Cb (a hypothetical)

    def test_a_system_with_a_brown_dwarf_is_planetary(self, systems):
        e = planetless_entry(systems["GJ 3347"])
        assert e["id"] == PREFIX + "GJ 3347" and e["kind"] == "planetary"
        assert e["planets"] == ["GJ 3347 Aa2"] and "GJ 3347 Aa2" in e["aliases"]
        assert e["n_stars"] == 5                      # Aa1, Ab, B, Ea, Eb; Aa2 is a planet now
        brown = {h for h, ps in systems.items() if ps.planets}
        assert brown == {"GJ 570", "ksi UMa", "GJ 867", "GJ 569", "tau Cyg", "pi1 Cnc", "GJ 9829", "BD+37 1091",
                         "BD+39 496", "GJ 3347", "GJ 310.1"}  # alf Gem's is the featured Castor's

