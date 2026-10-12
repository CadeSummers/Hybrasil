# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Orbit Direction: the sheet's column, and the retrograde and polar orbits it makes the model draw.

nu Oct A b goes round retrograde against its binary (Signor et al. 2026; Cheng et al. 2025), drawn inclined 174 deg
to it with A's axis assumed (dashed) to follow the binary.  A planet polar or retrograde against its star's spin
(GJ 436 b, GJ 3470 b, GJ 3090 b, GJ 523 b) stays in its plane and tilts the star's axis instead.
"""
import math

import pytest

from hybrasil.data import catalog_loader as cl
from hybrasil.data.snapshot import load_snapshot_workbook
from hybrasil.mechanics.orientation import mean_orbital_plane, reversed_orbit
from hybrasil.models.body import OrbitalBody
from hybrasil.models.elements import KeplerianElements as KE
from hybrasil.viz.static_plot import _axis_trace, axis_points

FLAGGED = {
    "GJ 436 b": "Polar (vs stellar spin; ψ 103°)",
    "GJ 3470 b": "Polar (vs stellar spin; ψ 95°)",
    "GJ 523 b": "Polar (vs stellar spin; ψ ≥ 71°)",
    "GJ 3090 b": "Retrograde (vs stellar spin; ψ 136°)",
    "nu Oct A b": "Retrograde (vs binary orbit; 174°)",
    "GJ 896 A b": "Retrograde (vs binary orbit; 148°)",
    "VHS J125601.92-125723.9 b": "Retrograde (vs host binary orbit; 118°)",
}


def _angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))


@pytest.fixture(scope="module")
def workbook():
    return load_snapshot_workbook()


@pytest.fixture(scope="module")
def catalog(workbook):
    return cl.parse_workbook(workbook)


def _column(workbook, tab):
    rows = workbook["tabs"][tab]
    h = [str(x).strip() for x in rows[0]]
    iP, iH, iD = h.index("Planet"), h.index("Host system (primary star)"), h.index("Orbit Direction")
    out = {}
    for r in rows[1:]:
        r = list(r) + [""] * (len(h) - len(r))
        if not str(r[iH]).strip():
            break
        out[str(r[iP]).strip()] = str(r[iD]).strip()
    return out


# ── the sheet ────────────────────────────────────────────────────────────────

def test_both_tabs_carry_the_column_and_only_seven_planets_are_not_prograde(workbook):
    planets = _column(workbook, "Planets within 100 ly")
    unconfirmed = _column(workbook, "Unconfirmed within 100 ly")
    assert len(planets) == 540 and len(unconfirmed) == 178
    assert {p: d for p, d in {**planets, **unconfirmed}.items() if not d.startswith("Prograde")} == FLAGGED
    assert set(unconfirmed.values()) == {"Prograde (assumed)"}
    measured = [d for d in planets.values() if d.startswith("Prograde (vs")]
    assert len(measured) == 30 and planets["Earth"].startswith("Prograde (vs stellar spin")


def test_the_spin_orbit_cells_it_corrected(workbook):
    rows = workbook["tabs"]["Planets within 100 ly"]
    h = [str(x).strip() for x in rows[0]]
    col = h.index("Spin-orbit angle (deg, vs stellar spin axis)")
    cell = {r[0]: r[col] for r in rows[1:] if r and r[0] in ("GJ 3470 b", "GJ 3090 b")}
    assert cell == {"GJ 3470 b": "95 +9/-8 (psi; Stefansson+2022, ApJL 931 L15 Table 4)",
                    "GJ 3090 b": "136 +24/-18 (psi; Carteret+2026)"}


# ── reading it ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cell,direction,angle", [
    ("Retrograde (vs binary orbit; 174°)", "Retrograde (vs binary orbit; 174°)", 174.0),
    ("Polar (vs stellar spin; ψ ≥ 71°)", "Polar (vs stellar spin; ψ ≥ 71°)", 71.0),
    ("Prograde (vs stellar spin; λ 4.7°)", "Prograde (vs stellar spin; λ 4.7°)", 4.7),
    ("Prograde (vs other planets)", "Prograde (vs other planets)", None),
    ("Prograde (assumed)", "", None),
    ("", "", None),
])
def test_the_cell_gives_a_direction_and_an_angle(cell, direction, angle):
    rec = cl.PlanetRecord(name="x b", host="x", orbit_direction=cell)
    assert rec.measured_direction == direction and rec.direction_angle_deg == angle


def test_the_spin_orbit_cell_is_the_fallback_angle():
    rec = cl.PlanetRecord(name="x b", host="x", orbit_direction="Polar (vs stellar spin)",
                          spin_orbit="103 +13/-12 (psi; Bourrier+2022, TEPCat)")
    assert rec.spin_orbit_deg == 103.0


# ── drawing it ───────────────────────────────────────────────────────────────

def test_nu_oct_ab_goes_round_against_the_binary_with_an_assumed_axis(catalog):
    s = cl.build_star_system(catalog, "nu Oct")
    a, b, ab = (s.get_body(n) for n in ("nu Oct A", "nu Oct B", "nu Oct A b"))
    assert b.elements.inclination == 0.0 and ab.elements.inclination == 174.0
    assert a.pole == pytest.approx((0.0, 0.0, 1.0)) and a.pole_assumed
    assert a.pole_note == "assumed: aligned with the binary orbit"
    # The band still opens from above: the planet counts its plane, not its sense.
    band = next(z for z in s.belt_zones if z.is_solvent_band and z.centre_body == "nu Oct A")
    assert band.normal[2] > 0.99
    assert "nu Oct A b: Retrograde" in s.description


@pytest.mark.parametrize("host,planet,psi", [("GJ 436", "GJ 436 b", 103), ("GJ 3470", "GJ 3470 b", 95),
                                             ("GJ 3090", "GJ 3090 b", 136), ("GJ 523", "GJ 523 b", 71)])
def test_a_spin_misaligned_planet_tilts_its_stars_axis_by_the_angle(catalog, host, planet, psi):
    s = cl.build_star_system(catalog, host)
    star, p = s.get_body(host), s.get_body(planet)
    assert p.elements.inclination == 0.0                       # the planet stays in its plane
    band = next(z for z in s.belt_zones if z.is_solvent_band and z.centre_body == host)
    assert _angle(star.pole, band.normal) == pytest.approx(psi, abs=0.5)
    assert not star.pole_assumed and star.axial_tilt_deg == pytest.approx(psi, abs=0.5)
    assert star.axis_half_au == pytest.approx(0.8 * p.elements.semi_major_axis)


def test_a_reversed_planet_does_not_flip_the_mean_plane():
    def planet(name, inc, direction=None):
        return OrbitalBody(name=name, body_type="planet", parent="A", mass_kg=1e25, orbit_direction=direction,
                           elements=KE(semi_major_axis=1.0, eccentricity=0.0, inclination=inc,
                                       longitude_of_ascending_node=0.0, argument_of_periapsis=0.0,
                                       mean_anomaly_at_epoch=0.0, epoch=2451545.0, period=365.0))
    lone = planet("b", 180.0, "Retrograde (vs binary orbit)")
    assert reversed_orbit(lone)
    assert mean_orbital_plane([lone], "A")[2] == pytest.approx(1.0)
    # Against the star's spin the orbit is never reversed, so it is not counted reversed either.
    assert not reversed_orbit(planet("c", 0.0, "Retrograde (vs stellar spin; ψ 136°)"))


def test_every_axis_has_an_arrowhead_and_an_assumed_one_is_dashed():
    star = OrbitalBody(name="A", body_type="star", pole=(0.0, 0.0, 1.0), axis_half_au=2.0)
    xs, ys, zs = axis_points(star, 1.0, 0.0, 0.0)
    assert len(xs) == 5 and (zs[0], zs[1]) == (-2.0, 2.0)          # south, north
    assert ys[2] == -ys[4] != 0 and zs[2] == zs[4] < 2.0           # two wings back from the north end
    assert _axis_trace(star, 1, 0, 0).line.dash == "solid"
    star.pole_assumed, star.pole_note = True, "assumed: aligned with the binary orbit"
    tr = _axis_trace(star, 1, 0, 0)
    assert tr.line.dash == "dash" and tr.name == "A axis (assumed: aligned with the binary orbit)"


def test_nu_oct_b_and_ab_go_round_in_opposite_senses(catalog):
    from hybrasil.mechanics.time_series import system_positions_at
    s = cl.build_star_system(catalog, "nu Oct")
    t0 = 2461000.5

    def sense(name, parent):
        # The sign of the z-component of r x dr about the parent, seen from above (+z).
        p0, p1 = (system_positions_at(s, t) for t in (t0, t0 + 5.0))
        r0 = [p0[name][k] - p0[parent][k] for k in range(3)]
        r1 = [p1[name][k] - p1[parent][k] for k in range(3)]
        return math.copysign(1, r0[0] * r1[1] - r0[1] * r1[0])
    assert sense("nu Oct B", "nu Oct A") == 1.0
    assert sense("nu Oct A b", "nu Oct A") == -1.0
