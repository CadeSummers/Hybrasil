# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Photosynthesis limits: the PAR factor, the distances, the rows, and the rings.

The rows in `data/photosynthesis_limits.py` are cells of the workbook's
Photosynthesis limits tab, checked here against the newest snapshot the way
`test_castor.py` checks Castor's.
"""
import copy
import glob
import math
import os

import numpy as np
import pytest

from hybrasil.data import photosynthesis_limits as pl
from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.figures import build_figure
from hybrasil.mechanics.photosynthesis import (
    par_photon_factor, photosynthesis_distance_au, total_energy_distance_au)
from hybrasil.mechanics.time_series import system_positions_at
from hybrasil.mechanics.units import J2000, T_SUN_K
from hybrasil.viz import photosynthesis_rings as pr
from hybrasil.viz.three_viewer import figure_to_scene

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestTheParFactor:
    def test_the_sun_is_exactly_one(self):
        assert par_photon_factor(T_SUN_K) == 1.0

    def test_an_unknown_temperature_is_no_correction(self):
        assert par_photon_factor(None) == 1.0 and par_photon_factor(0) == 1.0

    def test_red_dwarfs_give_fewer_par_photons_per_watt(self):
        assert par_photon_factor(2980) == pytest.approx(0.2343, abs=1e-4)      # Proxima
        assert par_photon_factor(2516) == pytest.approx(0.1054, abs=1e-4)      # TRAPPIST-1
        assert par_photon_factor(2516) < par_photon_factor(2980) < par_photon_factor(5000) < 1

    def test_it_peaks_just_above_one_and_falls_for_hot_stars(self):
        assert 1.04 < par_photon_factor(6900) < 1.06
        assert par_photon_factor(10000) < 1

    def test_the_sun_yields_the_blackbody_photon_count(self):
        # Planck at 5772 K: about 1.67 umol of 400-700 nm photons per joule of
        # total output, i.e. 4.57 umol/J of PAR times a PAR share of ~0.37.
        from hybrasil.mechanics.photosynthesis import par_photons_per_watt
        assert par_photons_per_watt(T_SUN_K) / 6.02214076e23 * 1e6 == pytest.approx(1.673, abs=1e-3)


class TestTheDistance:
    def test_around_the_sun_it_is_the_inverse_square(self):
        for f in (1.0, 0.25, 1e-4):
            assert photosynthesis_distance_au(1.0, f, T_SUN_K) == pytest.approx(1 / math.sqrt(f), rel=1e-12)

    def test_it_scales_as_root_l_times_k(self):
        d = photosynthesis_distance_au(0.00151, 0.01, 2980)
        assert d == pytest.approx(math.sqrt(0.00151 * par_photon_factor(2980) / 0.01), rel=1e-12)
        assert d < total_energy_distance_au(0.00151, 0.01)

    def test_no_light_no_answer(self):
        assert photosynthesis_distance_au(0, 0.1) is None
        assert photosynthesis_distance_au(1.0, 0) is None


class TestTheRowsAreTheWorkbooks:
    @pytest.fixture(scope="class")
    def sheet(self):
        openpyxl = pytest.importorskip("openpyxl")
        snaps = sorted(glob.glob(os.path.join(ROOT, "data", "hybrasil-*.xlsx")))
        if not snaps:
            pytest.skip("no workbook snapshot in data/")
        wb = openpyxl.load_workbook(snaps[-1], read_only=True, data_only=True)
        if pl.TAB not in wb.sheetnames:
            pytest.skip("snapshot predates the Photosynthesis limits tab")
        it = wb[pl.TAB].iter_rows(values_only=True)
        head = list(next(it))
        rows, refs = {}, {}
        for r in it:
            if not any(c not in (None, "") for c in r):
                break                   # the data ends at the first blank row
            d = dict(zip(head, r))
            par = d.get("PAR (umol photons m-2 s-1)")
            level = d["Level"].split()[0].lower()
            rows.setdefault(d["Organism"], {})[level] = d["PAR (umol photons m-2 s-1)"]
        # The REFERENCE VALUES block, further down: quantity in A, value in E.
        for r in it:
            if r and r[0] and len(r) > 4 and isinstance(r[4], (int, float)):
                refs[r[0]] = r[4]
        return rows, refs

    def test_the_same_organisms_in_the_same_order(self, sheet):
        assert list(sheet[0]) == [o.name for o in pl.ORGANISMS]

    @pytest.mark.parametrize("org", pl.ORGANISMS, ids=lambda o: o.name)
    def test_every_level(self, sheet, org):
        for level in pl.LEVELS:
            theirs = sheet[0][org.name][level]
            ours = org.level(level)
            if theirs is None:
                assert ours is None, (org.name, level)
            else:
                assert ours is not None and math.isclose(ours, theirs, rel_tol=1e-12), (org.name, level)

    def test_full_sun_is_the_reference_block(self, sheet):
        assert sheet[1]["Earth full-sun PAR at the surface, midday, clear sky"] == pl.EARTH_FULL_SUN_PAR


class TestTheRows:
    def test_the_rings_run_outward(self):
        f = [x for _, x in pl.drawn_limits()]
        assert f == sorted(f, reverse=True)

    def test_an_organism_with_no_growth_limit_draws_no_ring(self):
        names = [o.name for o, _ in pl.drawn_limits()]
        assert "Deep crustose coralline red algae" not in names
        assert len(names) == len(pl.ORGANISMS) - 1


def _fig(key, frames=3, span=30):
    return build_figure(get_builtin_system(key), J2000, J2000 + span, frames=frames)


class TestTheRings:
    def test_one_ring_per_luminous_star_per_organism(self):
        fig = _fig("alpha-centauri")
        specs = fig.layout.meta[pr.META_KEY]
        stars = {s["star"] for s in specs}
        assert stars == {"Alpha Centauri A", "Alpha Centauri B", "Proxima Centauri"}
        assert len(specs) == 3 * len(pl.drawn_limits())
        # More than one star: the star goes in the name, as a band's does.
        assert all(s["name"].endswith(f"({s['star']})") for s in specs)

    def test_a_single_star_ring_is_named_by_organism_alone(self):
        specs = _fig("solar").layout.meta[pr.META_KEY]
        assert [s["name"] for s in specs] == [f"{o.name} growth limit" for o, _ in pl.drawn_limits()]

    def test_the_suns_rings_are_at_the_inverse_square_distance(self):
        specs = _fig("solar").layout.meta[pr.META_KEY]
        for s, (_, f) in zip(specs, pl.drawn_limits()):
            assert s["radius_au"] == pytest.approx(1 / math.sqrt(f), rel=1e-12)

    def test_each_ring_is_a_flat_circle_round_its_own_star(self):
        system = get_builtin_system("alpha-centauri")
        fig = build_figure(system, J2000, J2000 + 30, frames=3)
        pos = system_positions_at(system, J2000)
        for s in fig.layout.meta[pr.META_KEY]:
            pts = np.array(pr.ring_points(s)).reshape(-1, 3)
            c, n = np.array(pos[s["star"]]), np.array(s["normal"])
            assert np.allclose(np.linalg.norm(pts - c, axis=1), s["radius_au"], rtol=1e-12)
            assert np.allclose((pts - c) @ n, 0, atol=1e-9 * max(1.0, s["radius_au"]))
            assert np.allclose(pts[0], pts[-1])                    # closed

    def test_a_ring_lies_in_its_stars_band_plane(self):
        system = get_builtin_system("trappist-1")
        fig = build_figure(system, J2000, J2000 + 5, frames=3)
        band = next(z for z in system.belt_zones if z.is_solvent_band)
        for s in fig.layout.meta[pr.META_KEY]:
            assert s["normal"] == pytest.approx(list(band.normal))

    def test_a_star_with_no_luminosity_gets_none(self):
        system = copy.deepcopy(get_builtin_system("solar"))     # never the cached one
        for b in system.bodies:
            if b.body_type == "star":
                b.luminosity_sun = None
        assert pr.ring_specs(system, J2000) == []

    def test_no_plotly_trace_is_added(self):
        fig = _fig("solar")
        assert not any(pr.SET_KEY in str(t.meta) for t in fig.data)


class TestTheScene:
    def test_the_set_is_a_menu_feature_off_by_default(self):
        scene = figure_to_scene(_fig("solar"))
        (o,) = [o for o in scene["optionalSets"] if o["key"] == pr.SET_KEY]
        assert (o["key"], o["label"], o["default"], o["menu"]) == \
            (pr.SET_KEY, "Photosynthesis limits", False, "features")
        assert o["count"] == len(pl.drawn_limits())

    def test_every_ring_is_an_optional_line_owned_by_and_riding_its_star(self):
        scene = figure_to_scene(_fig("alpha-centauri"))
        rings = [l for l in scene["lines"] if l.get("optional") == pr.SET_KEY]
        assert len(rings) == 3 * len(pl.drawn_limits())
        assert all(l["owner"] == l["follows"] for l in rings)
        assert {l["owner"] for l in rings} == {"Alpha Centauri A", "Alpha Centauri B", "Proxima Centauri"}
        # One legend row per organism, whatever the star.
        assert {l["group"] for l in rings} == {o.name for o, _ in pl.drawn_limits()}
        assert all(l["width"] <= 1.5 and not l["legend"] for l in rings)
        assert all(len(l["pts"]) == 3 * (pr.RING_POINTS + 1) for l in rings)
