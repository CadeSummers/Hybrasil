# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Castor: the workbook's numbers, placed round barycentres that really are barycentres.

Castor is the first featured system built from the "Planetless 4+ Stars" tab, and every number it draws is a
cell there. The first class reads the snapshot in data/ and fails on any that has drifted, so a change to
Castor is a change to the sheet first. Its brown dwarf, Cc, is a planet since 7 Oct 2026, and its numbers are
checked against its Planets row instead.

The rest is geometry. The tab gives each pair's relative orbit and where its barycentre sits; hierarchy.py
turns that into chains of Keplerian orbits from Aa at the origin. If a flip or a scale were wrong the stars
would still orbit something -- just not their own centre of mass -- and nothing would look broken. So the
barycentres are checked as barycentres, at several times, from the stars' own positions.
"""
import glob
import math
import os

import numpy as np
import pytest

import re

from hybrasil.data.builtin_systems import _CASTOR_CC, _CASTOR_ROWS, _SKY_CASTOR, get_builtin_system
from hybrasil.data.hierarchy import hierarchy_bodies, relative_orbit
from hybrasil.mechanics.time_series import system_orbit_paths, system_positions_at
from hybrasil.models.system import StarSystem

TAB = "Planetless 4+ Stars"
COLUMNS = {
    "node_type": "Node type", "mass_sun": "Mass (M-sun)", "luminosity_sun": "Luminosity (L-sun)",
    "teff_k": "Effective temp (K)", "separation_from": "Separation from", "a_au": "Separation (AU)",
    "e": "Orbital eccentricity (e)", "period_d": "Orbital period (d)", "inclination_deg": "Inclination (deg)",
    "node_deg": "Ascending node (deg)", "omega_deg": "Argument of periastron (deg)",
    "periastron_jd": "Time of periastron (JD)", "omega_refers_to": "Argument of periastron refers to",
    "barycentre_from": "Barycentre from", "barycentre_offset_au": "Barycentre offset (AU)",
}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROWS = {r.name: r for r in _CASTOR_ROWS}
NAME = {r.name: r.name.replace("alf Gem ", "Castor ") for r in _CASTOR_ROWS}
# (subsystem, primary member, secondary member)
PAIRS = [("alf Gem A", "alf Gem Aa", "alf Gem Ab"), ("alf Gem B", "alf Gem Ba", "alf Gem Bb"),
         ("alf Gem AB", "alf Gem A", "alf Gem B"), ("alf Gem Cab", "alf Gem Ca", "alf Gem Cb")]
TIMES = [2451545.0, 2455817.7868, 2460000.0, 2461000.3, 2470000.0]


@pytest.fixture(scope="module")
def castor():
    return get_builtin_system("castor")


def _pos(system, t):
    return {k: np.array(v) for k, v in system_positions_at(system, t).items()}


class TestEveryNumberIsTheWorkbooks:
    @pytest.fixture(scope="class")
    def sheet(self):
        openpyxl = pytest.importorskip("openpyxl")
        snaps = sorted(glob.glob(os.path.join(ROOT, "data", "hybrasil-*.xlsx")))
        if not snaps:
            pytest.skip("no workbook snapshot in data/")
        ws = openpyxl.load_workbook(snaps[-1], read_only=True, data_only=True)[TAB]
        it = ws.iter_rows(values_only=True)
        head = list(next(it))
        rows = {}
        for r in it:
            d = dict(zip(head, r))
            if str(d.get("Star (component)") or "").startswith("alf Gem "):
                rows[d["Star (component)"]] = d
        return rows

    def test_the_same_ten_rows(self, sheet):
        assert set(sheet) == set(ROWS)

    @pytest.mark.parametrize("name", sorted(ROWS))
    def test_every_cell(self, sheet, name):
        row = ROWS[name]
        for field, header in COLUMNS.items():
            ours, theirs = getattr(row, field), sheet[name][header]
            theirs = None if theirs in ("", None) else theirs
            if isinstance(ours, float) or isinstance(theirs, float):
                assert ours is not None and theirs is not None and math.isclose(ours, theirs, rel_tol=1e-12), \
                    (name, header, ours, theirs)
            else:
                assert ours == theirs, (name, header, ours, theirs)

    def test_the_sky_position_and_distance(self, sheet):
        host = sheet["alf Gem Aa"]
        assert _SKY_CASTOR == (host["RA (deg, ICRS)"], host["Dec (deg, ICRS)"], host["Distance (ly)"])


class TestTheBrownDwarfIsAPlanet:
    @pytest.fixture(scope="class")
    def row(self):
        openpyxl = pytest.importorskip("openpyxl")
        snaps = sorted(glob.glob(os.path.join(ROOT, "data", "hybrasil-*.xlsx")))
        if not snaps:
            pytest.skip("no workbook snapshot in data/")
        ws = openpyxl.load_workbook(snaps[-1], read_only=True, data_only=True)["Planets within 100 ly"]
        it = ws.iter_rows(values_only=True)
        head = list(next(it))
        rows = [dict(zip(head, r)) for r in it if r and r[0] == "alf Gem Cc"]
        assert len(rows) == 1
        return rows[0]

    def test_its_orbit_and_mass_are_its_planets_row(self, row):
        assert row["Planet-host star"] == "alf Gem Cab" and row["Host system (primary star)"] == "alf Gem"
        assert (row["Semi-major axis (au)"], row["Eccentricity"], row["Orbital period (d)"]) ==             (_CASTOR_CC.a_au, _CASTOR_CC.e, _CASTOR_CC.period_d)
        assert row["Mass (M-earth)"] / 332946.0487 == pytest.approx(_CASTOR_CC.mass_sun, rel=1e-5)

    def test_its_angles_are_in_the_flags_text(self, row):
        flags = row["Orbit data source / flags"]
        for label, ours in (("Inclination (deg)", _CASTOR_CC.inclination_deg),
                            ("Ascending node (deg)", _CASTOR_CC.node_deg),
                            ("Argument of periastron (deg)", _CASTOR_CC.omega_deg),
                            ("Time of periastron (JD)", _CASTOR_CC.periastron_jd)):
            m = re.search(re.escape(label) + r" ([-\d.]+)", flags)
            assert m and float(m.group(1)) == ours, label
        assert f"Argument of periastron refers to {_CASTOR_CC.omega_refers_to}" in flags

    def test_it_goes_round_yy_gem(self, castor):
        cc = next(b for b in castor.bodies if b.name == "Castor Cc")
        assert (cc.body_type, cc.parent, cc.status) == ("planet", "Castor Cab", "hypothetical")


class TestTheBarycentresAreBarycentres:
    @pytest.mark.parametrize("t", TIMES)
    @pytest.mark.parametrize("x,prim,sec", PAIRS)
    def test_mass_weighted_centre(self, castor, t, x, prim, sec):
        p = _pos(castor, t)
        m1, m2 = ROWS[prim].mass_sun, ROWS[sec].mass_sun
        centre = (m1 * p[NAME[prim]] + m2 * p[NAME[sec]]) / (m1 + m2)
        assert np.linalg.norm(centre - p[NAME[x]]) < 2e-5 * ROWS[sec].a_au

    @pytest.mark.parametrize("t", TIMES)
    def test_the_same_from_any_origin(self, t):
        # Ab is a pair's secondary, so starting there walks the other branch of the builder.
        other = StarSystem(name="x", description="", bodies=hierarchy_bodies(
            _CASTOR_ROWS, origin="alf Gem Ab", name_of=lambda n: n.replace("alf Gem ", "Castor ")))
        a, b = _pos(get_builtin_system("castor"), t), _pos(other, t)
        shift = b["Castor Aa"] - a["Castor Aa"]
        for n in b:                                  # the hierarchy's bodies: Cc, a planet, is not one
            assert np.linalg.norm(b[n] - a[n] - shift) < 1e-6, n


class TestTheOrbits:
    @pytest.mark.parametrize("name", [r.name for r in _CASTOR_ROWS if r.separation_from] + [_CASTOR_CC.name])
    def test_keplers_third_law(self, name):
        # Would have caught the MSC's AB-C period, ten times too long. 15 % covers
        # the indeterminate AB-C orbit (5 %) and Cc's minimum mass.
        r = ROWS.get(name, _CASTOR_CC)
        total = ROWS[r.separation_from].mass_sun + r.mass_sun
        kepler_d = math.sqrt(r.a_au ** 3 / total) * 365.25
        assert abs(r.period_d / kepler_d - 1) < 0.15, (name, r.period_d, kepler_d)

    def test_ab_is_at_periastron_at_t(self, castor):
        r = ROWS["alf Gem Ab"]
        p = _pos(castor, r.periastron_jd)
        assert np.linalg.norm(p["Castor Ab"] - p["Castor Aa"]) == pytest.approx(r.a_au * (1 - r.e), rel=1e-9)

    @pytest.mark.parametrize("n", [0, 1, 12345])
    def test_yy_gem_is_eclipsing_at_primary_minimum(self, castor, n):
        # Ca and Cb line up along the line of sight (z): the sky-plane separation is a cos i, not a.
        r = ROWS["alf Gem Cb"]
        p = _pos(castor, r.periastron_jd + n * r.period_d)
        d = p["Castor Cb"] - p["Castor Ca"]
        assert math.hypot(d[0], d[1]) == pytest.approx(r.a_au * math.cos(math.radians(r.inclination_deg)), rel=1e-6)
        assert abs(d[2]) == pytest.approx(r.a_au * math.sin(math.radians(r.inclination_deg)), rel=1e-6)

    def test_omega_quoted_for_the_primary_is_turned_for_the_secondary(self):
        assert relative_orbit(ROWS["alf Gem Ab"]).argument_of_periapsis == pytest.approx(84.97)
        assert relative_orbit(ROWS["alf Gem B"]).argument_of_periapsis == pytest.approx(251.8)


class TestHowItIsDrawn:
    def test_stars_and_barycentres(self, castor):
        kinds = {b.name: b.body_type for b in castor.bodies}
        assert sorted(n for n, k in kinds.items() if k == "barycentre") == sorted(
            NAME[n] for n, r in ROWS.items() if r.node_type == "subsystem")
        assert sum(k == "star" for k in kinds.values()) == 6
        assert kinds["Castor Cc"] == "planet"

    def test_parents_come_first(self, castor):
        seen = set()
        for b in castor.bodies:
            assert b.parent is None or b.parent in seen, b.name
            seen.add(b.name)

    def test_a_band_for_every_luminous_star_and_no_barycentre(self, castor):
        centres = {z.centre_body for z in castor.belt_zones}
        assert centres == {NAME[n] for n, r in ROWS.items() if r.luminosity_sun}

    def test_only_the_bookkeeping_barycentres_go_undrawn(self, castor):
        t0 = 2461000.5
        paths, coils = system_orbit_paths(castor, t_start=t0, t_end=t0 + 10.0)
        drawn = set(paths) | set(coils)
        assert {"Castor A", "Castor AB"}.isdisjoint(drawn)
        assert {"Castor B", "Castor Cab", "Castor Ab", "Castor Cc"} <= set(paths)
        # a star round a moving barycentre, or round a moving star, is a coil
        assert {"Castor Ba", "Castor Bb", "Castor Ca", "Castor Cb"} <= set(coils)

    def test_the_outer_orbits_are_closed_ellipses(self, castor):
        t0 = 2461000.5
        paths, _ = system_orbit_paths(castor, t_start=t0, t_end=t0 + 10.0)
        for name in ("Castor B", "Castor Cab"):
            xs, ys, zs = paths[name]
            assert (xs[0], ys[0], zs[0]) == (xs[-1], ys[-1], zs[-1])
