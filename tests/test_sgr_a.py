# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The S-stars round Sgr A*: the Sgr A* S-stars tab, its loader, and the system it draws.

The frame tests read Gillessen et al. 2017's own data (data/sgr_a/cat/, VizieR J/ApJ/837/30), so they say whether
an orbit as the loader turns it lands where the star was measured -- on the sky and along the line of sight.
"""
import math
from pathlib import Path

import pytest

from hybrasil.data.sgr_a_loader import (CENTRE, HEADERS, SMBH, TAB, build_sgr_a_system, parse_sgr_a,
                                             sgr_a_entry, sgr_a_span_days, sky_elements, sky_motion, year_to_jd)

CAT = Path(__file__).resolve().parent.parent / "data" / "sgr_a" / "cat"
R0_GILLESSEN_PC = 8320.0
# S2 as Gillessen et al. 2017 table 3 gives it.
S2 = dict(a=0.1255, e=0.8839, i=134.18, node=226.94, omega=65.51, tp=2002.33, period=16.00)


def _row(**kw):
    col = {h: i for i, h in enumerate(HEADERS)}
    r = [""] * len(HEADERS)
    for k, v in kw.items():
        r[col[k]] = v
    return r


def _star(name, a, e, i, node, omega, tp, period, **kw):
    return _row(**{"Object": name, "Object type": "Star", "Semi-major axis (arcsec)": a,
                   "Semi-major axis (AU)": a * R0_GILLESSEN_PC, "Orbital eccentricity (e)": e,
                   "Inclination (deg)": i, "Ascending node (deg)": node, "Argument of periapsis (deg)": omega,
                   "Time of periapsis (yr)": tp, "Orbital period (yr)": period, **kw})


CENTRE_ROW = _row(**{"Object": CENTRE, "Object type": SMBH, "Mass (M-sun)": 4.297e6, "Distance (pc)": 8277,
                     "Distance (ly)": 26996, "RA (deg, ICRS)": 266.41684, "Dec (deg, ICRS)": -29.00781,
                     "SIMBAD main_id": "NAME Sgr A*", "Refs": "Mass: 2022A&A...657L..12G"})


def _workbook(*rows):
    return {"title": "test", "tabs": {TAB: [HEADERS, CENTRE_ROW, *rows]}}


def _s2_row(**kw):
    return _star("S2", S2["a"], S2["e"], S2["i"], S2["node"], S2["omega"], S2["tp"], S2["period"],
                 **{"Spectral group (Gillessen 2017)": "early-type", "Refs": "Orbit: 2017ApJ...837...30G", **kw})


# ── the frame: Gillessen's own measurements ───────────────────────────────────────────────────────────────────────

def _table5_s2():
    """(year, flag, RA offset mas, Dec offset mas, RV km/s) for S2, from Gillessen et al. 2017 table 5."""
    out = []
    for line in (CAT / "gillessen2017_table5.dat").read_text().splitlines():
        if len(line) < 75:
            continue
        year, flag = float(line[0:8]), line[9:11].strip()
        ra, dec, rv = line[46:51].strip(), line[56:61].strip(), line[66:71].strip()
        if flag == "a" and ra and dec:
            out.append((year, "a", float(ra), float(dec), None))
        elif flag == "rv" and rv:
            out.append((year, "rv", None, None, float(rv)))
    return out


def _s2_elements():
    return sky_elements(S2["a"] * R0_GILLESSEN_PC, S2["e"], S2["i"], S2["node"], S2["omega"], S2["tp"],
                        S2["period"])


def test_s2_lands_on_its_measured_positions():
    """North and East come out where they were measured: the sky half of the frame."""
    el = _s2_elements()
    off = []
    for year, flag, ra, dec, _ in _table5_s2():
        if flag == "a":
            m = sky_motion(el, year_to_jd(year), R0_GILLESSEN_PC)
            off.append(((m.ra_off_mas - ra) ** 2 + (m.dec_off_mas - dec) ** 2) ** 0.5)
    assert len(off) > 100
    off.sort()
    assert off[len(off) // 2] < 2.0          # median, mas
    assert sum(o > 5.0 for o in off) <= 10   # the early SHARP epochs scatter more


def test_s2_recedes_and_approaches_when_it_was_measured_to():
    """The line-of-sight half: the papers' ascending node is the receding one, and z here points at Earth.

    Taken as published, every radial velocity comes out with the wrong sign; sky_elements turns Omega and omega
    by 180 deg, which flips the orbit through the sky plane and nothing else.
    """
    el = _s2_elements()
    rvs = [(y, rv) for y, flag, _, _, rv in _table5_s2() if flag == "rv"]
    assert len(rvs) > 40
    for year, rv in rvs:
        model = sky_motion(el, year_to_jd(year), R0_GILLESSEN_PC).rv_kms
        if abs(rv) > 100:
            assert model * rv > 0, (year, rv, model)
        assert abs(model - rv) < 150, (year, rv, model)


def test_the_flip_moves_nothing_on_the_sky():
    from hybrasil.mechanics.kepler import elements_to_cartesian
    from hybrasil.models.elements import KeplerianElements
    el = _s2_elements()
    raw = KeplerianElements(semi_major_axis=el.semi_major_axis, eccentricity=el.eccentricity,
                            inclination=el.inclination, longitude_of_ascending_node=S2["node"],
                            argument_of_periapsis=S2["omega"], mean_anomaly_at_epoch=0.0, epoch=el.epoch,
                            period=el.period)
    for year in (2000.5, 2002.4, 2010.0, 2018.38):
        x, y, z = elements_to_cartesian(el, year_to_jd(year))
        xr, yr, zr = elements_to_cartesian(raw, year_to_jd(year))
        assert (x, y) == pytest.approx((xr, yr), abs=1e-6) and z == pytest.approx(-zr, abs=1e-6)


def test_s2_pericentre_is_about_120_au():
    el = _s2_elements()
    m = sky_motion(el, year_to_jd(S2["tp"]), R0_GILLESSEN_PC)
    assert m.r_au == pytest.approx(S2["a"] * R0_GILLESSEN_PC * (1 - S2["e"]), rel=1e-3)
    assert 110 < m.r_au < 130
    assert 7000 < m.speed_kms < 8000           # GRAVITY 2018: 7650 km/s at pericentre


# ── parsing and the system, from literal rows ─────────────────────────────────────────────────────────────────────

def test_no_tab_no_cluster():
    assert parse_sgr_a({"tabs": {}}) is None


def test_exactly_one_black_hole_row():
    with pytest.raises(ValueError):
        parse_sgr_a({"tabs": {TAB: [HEADERS, _s2_row()]}})


def test_sgr_a_is_the_dark_massive_centre_with_no_light():
    system = build_sgr_a_system(parse_sgr_a(_workbook(_s2_row())))
    centre = system.get_body(CENTRE)
    assert centre.elements is None and centre.luminosity_sun is None
    assert centre.mass_kg == pytest.approx(4.297e6 * 1.98847e30)
    assert centre.info_rows[0][:2] == ["Object type", SMBH]
    assert system.belt_zones == []
    assert system.at_galactic_center


def test_each_star_orbits_sgr_a_with_its_published_elements_in_the_sky_frame():
    system = build_sgr_a_system(parse_sgr_a(_workbook(_s2_row())))
    s2 = system.get_body("S2")
    assert s2.parent == CENTRE and s2.luminosity_sun is None
    el = s2.elements
    assert el.semi_major_axis == pytest.approx(S2["a"] * R0_GILLESSEN_PC)
    assert (el.eccentricity, el.inclination) == (S2["e"], S2["i"])
    assert el.longitude_of_ascending_node == pytest.approx((S2["node"] + 180) % 360)
    assert el.argument_of_periapsis == pytest.approx((S2["omega"] + 180) % 360)
    assert el.period == pytest.approx(S2["period"] * 365.25)
    assert el.epoch == pytest.approx(year_to_jd(S2["tp"]))


def test_a_disputed_star_is_drawn_hollow_and_says_so():
    row = _star("S4716", 0.0303, 0.756, 161.24, 141.5, 0.0, 2017.0, 4.0, **{"Status": "disputed: not confirmed"})
    system = build_sgr_a_system(parse_sgr_a(_workbook(_s2_row(), row)))
    b = system.get_body("S4716")
    assert b.status == "hypothetical" and b.status_note == "Disputed"
    assert "disputed" in b.label()
    assert system.get_body("S2").status == "confirmed"


def test_an_unbound_star_is_listed_but_not_drawn():
    s111 = _row(**{"Object": "S111", "Object type": "Star", "Semi-major axis (arcsec)": -12.3,
                   "Orbital eccentricity (e)": 1.092, "Inclination (deg)": 102.68, "Ascending node (deg)": 52.34,
                   "Argument of periapsis (deg)": 132.4, "Time of periapsis (yr)": 1947.7})
    cluster = parse_sgr_a(_workbook(_s2_row(), s111))
    assert [r.name for r in cluster.stars] == ["S2", "S111"]
    system = build_sgr_a_system(cluster)
    assert "S111" not in [b.name for b in system.bodies]
    assert "S111 unbound" in system.description


def test_sources_link_simbad_and_each_paper():
    system = build_sgr_a_system(parse_sgr_a(_workbook(_s2_row(**{
        "SIMBAD main_id": "S2", "Refs": "Orbit: 2017ApJ...837...30G; Mass: 2017ApJ...847..120H"}))))
    src = system.get_body("S2").sources
    assert src[0] == ["Exists: SIMBAD S2", "https://simbad.cds.unistra.fr/simbad/sim-id?Ident=S2"]
    assert ["Orbit: 2017ApJ...837...30G", "https://ui.adsabs.harvard.edu/abs/2017ApJ...837...30G/abstract"] in src
    assert any(s[0].startswith("Mass: 2017ApJ...847..120H") for s in src)


def test_twenty_years_turns_s2_once():
    system = build_sgr_a_system(parse_sgr_a(_workbook(_s2_row())))
    assert sgr_a_span_days(system) > system.get_body("S2").elements.period


def test_the_figure_has_no_bands_and_no_galactic_centre_arrow():
    from hybrasil.figures import build_figure
    system = build_sgr_a_system(parse_sgr_a(_workbook(_s2_row())))
    fig = build_figure(system, 2461000.5, 2461000.5 + sgr_a_span_days(system), frames=10)
    names = [t.name or "" for t in fig.data]
    assert not any("Galactic Center" in n for n in names)
    assert any(n.startswith("Solar System") for n in names)
    assert not any("band" in n.lower() or "photosynth" in n.lower() for n in names)


def test_the_panel_shows_the_rows_the_sheet_gives():
    from hybrasil.viz.export import build_body_info
    system = build_sgr_a_system(parse_sgr_a(_workbook(_s2_row(**{"Stellar Class": "B0-2.5 V"}))))
    info = build_body_info({"sgr": system})
    assert info["S2"]["rows"][2] == ["Stellar class", "B0-2.5 V", ""]
    assert info[system.get_body(CENTRE).label()]["rows"][0][1] == SMBH


def test_listed_under_stellar_motion_as_the_sgr_a_cluster():
    e = sgr_a_entry(parse_sgr_a(_workbook(_s2_row())))
    assert e["name"] == "Sgr A* Cluster (Galactic Center)"
    assert e["kind"] == "motion" and "Sgr A*" in e["aliases"] and "S2" in e["aliases"]


# ── the tab itself, from the committed snapshot ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def snapshot_cluster():
    from hybrasil.data.snapshot import load_snapshot_workbook
    cluster = parse_sgr_a(load_snapshot_workbook())
    if cluster is None:
        pytest.skip("the snapshot has no Sgr A* S-stars tab")
    return cluster


GRAVITY_REFITS = {"S2", "S29", "S38", "S55"}
DISPUTED = {"S62", "S4711", "S4712", "S4713", "S4714", "S4715", "S4716"}
VON_FELLENBERG = {"S5", "R1", "R14", "R30", "R70", "S72"}           # 2022ApJ...932L...6V, Table 4
DUSTY = {"G1", "G2"}                                                # 2026A&A...707A..79G, Table B.1
ADDED = {"S301"} | VON_FELLENBERG | DUSTY                           # 10 Oct 2026, data/sgr_a/research/D.json


def _table3():
    out = {}
    for line in (CAT / "gillessen2017_table3.dat").read_text().splitlines():
        if line.strip():
            f = lambda a, b: float(line[a:b]) if line[a:b].strip() else None   # noqa: E731
            out[line[0:4].strip()] = (f(7, 15), f(23, 29), f(37, 43), f(49, 55), f(62, 68), f(75, 82), f(90, 97))
    return out


def test_the_tab_holds_sgr_a_the_40_the_disputed_seven_and_the_nine_added(snapshot_cluster):
    names = [r.name for r in snapshot_cluster.stars]
    assert snapshot_cluster.centre.name == CENTRE and snapshot_cluster.centre.object_type == SMBH
    assert snapshot_cluster.centre.mass == pytest.approx(4.297e6)
    assert set(names) == set(_table3()) | DISPUTED | ADDED and len(names) == 56
    assert {r.name for r in snapshot_cluster.stars if r.disputed} == DISPUTED


def test_every_gillessen_orbit_is_on_the_tab_as_published(snapshot_cluster):
    t3 = _table3()
    for r in snapshot_cluster.stars:
        if r.name in t3 and r.name not in GRAVITY_REFITS:
            a, e, i, node, omega, tp, period = t3[r.name]
            assert (r.a_arcsec, r.e, r.i, r.node, r.omega, r.tp_yr) == (a, e, i, node, omega, tp), r.name
            assert r.period_yr == period or (period is None and r.period_yr is None), r.name


def test_s2_is_gravitys_fit_and_still_turns_in_sixteen_years(snapshot_cluster):
    s2 = next(r for r in snapshot_cluster.stars if r.name == "S2")
    assert s2.a_arcsec == 0.12495 and s2.tp_yr == pytest.approx(2018.3789)
    assert s2.period_yr == pytest.approx(16.0455, abs=0.01)     # GRAVITY 2020's published period
    assert s2.peri_au == pytest.approx(120, abs=2)


def test_s301_is_the_first_of_gravity_plus_two_solutions(snapshot_cluster):
    s301 = next(r for r in snapshot_cluster.stars if r.name == "S301")
    assert (s301.a_arcsec, s301.e, s301.i, s301.node, s301.omega, s301.tp_yr, s301.period_yr) ==         (0.083, 0.9832, 124.09, 73.8, 293.4, 2023.126, 8.68)          # Nature 657, 359, Extended Data Table 2
    # its period agrees with Kepler's third law at the fit's own M and R0
    assert math.sqrt(s301.a_au ** 3 / 4.297e6) == pytest.approx(s301.period_yr, rel=0.01)
    assert s301.peri_au == pytest.approx(11.5, abs=0.2)               # the smallest pericentre on the tab
    assert s301.peri_au == min(r.peri_au for r in snapshot_cluster.stars if r.peri_au)


def test_the_von_fellenberg_orbits_are_on_the_tab_as_published(snapshot_cluster):
    # Table 4: a", e, i, Omega, omega, P, t0
    table4 = {"S5": (0.53, 0.72, 115.96, 128.58, 271.99, 140.03, 1954.49),
              "R1": (2.63, 0.53, 125.09, 117.28, 243.87, 1523.25, 4005.64),
              "R14": (2.78, 0.44, 118.86, 113.28, 158.8, 1659.39, 3510.03),
              "R30": (6.36, 0.61, 113.02, 94.51, 12.33, 5739.49, 2242.8),
              "R70": (3.48, 0.35, 147.27, 115.55, 43.19, 2326.65, 3667.56),
              "S72": (2.2, 0.33, 119.18, 316.04, 205.09, 1184.02, 1055.3)}
    rows = {r.name: r for r in snapshot_cluster.stars}
    for name, want in table4.items():
        r = rows[name]
        assert (r.a_arcsec, r.e, r.i, r.node, r.omega, r.period_yr, r.tp_yr) == want, name
        assert r.status == "confirmed" and not r.disputed and not r.dusty


def test_g1_and_g2_are_dusty_objects_drawn_solid_and_dust_coloured(snapshot_cluster):
    from hybrasil.data.sgr_a_loader import DUST_COLOUR
    rows = {r.name: r for r in snapshot_cluster.stars}
    assert {n for n, r in rows.items() if r.dusty} == DUSTY
    assert sgr_a_entry(snapshot_cluster)["n_stars"] == 54           # 56 objects less G1 and G2
    assert (rows["G2"].e, rows["G2"].tp_yr) == (0.989, 2014.18)
    system = build_sgr_a_system(snapshot_cluster)
    for name in DUSTY:
        b = system.get_body(name)
        assert b.color == DUST_COLOUR and b.status != "hypothetical" and "dusty object" in b.label()
    assert "G1 and G2 are dusty objects" in system.description


def test_the_snapshot_system_draws_55_orbits_and_leaves_s111_out(snapshot_cluster):
    system = build_sgr_a_system(snapshot_cluster)
    drawn = [b for b in system.bodies if b.elements is not None]
    assert len(drawn) == 55 and "S111" not in [b.name for b in system.bodies]
    assert sum(b.status == "hypothetical" for b in drawn) == 7
    assert all(b.sources for b in system.bodies)
    assert not any(b.luminosity_sun for b in system.bodies)


def test_the_catalog_does_not_read_the_tab_as_a_star_system():
    from hybrasil.data.catalog_loader import parse_workbook
    from hybrasil.data.snapshot import load_snapshot_workbook
    cat = parse_workbook(load_snapshot_workbook())
    hosts = set(cat.hosts())
    assert CENTRE not in hosts and "S2" not in hosts and "S4716" not in hosts
