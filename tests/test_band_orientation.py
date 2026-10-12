# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the plane a solvent band is drawn in.

A band used to lie flat on the reference plane whatever the system did.  That
is right only where the reference plane is the orbital plane, which is true of
the Solar System and false of TRAPPIST-1, whose planets are at 89.8 deg.  These
pin the derived plane, the geometry of the ring built in it, and the systems
that must not move.

They also pin what a band's plane is *not* built from: a companion star, whose
angular momentum would otherwise be the whole answer wherever there is one.
"""

import math

import numpy as np
import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.mechanics.kepler import rotate_to_reference_frame
from hybrasil.mechanics.orientation import (
    NEGLIGIBLE_TILT_DEG,
    Z_AXIS,
    band_plane,
    mean_orbital_plane,
    orbital_normal,
    plane_basis,
    plane_tilt_deg,
)
from hybrasil.mechanics.solvent_bands import SolventChoice, solvent_zones
from hybrasil.mechanics.time_series import (
    system_orbit_paths,
    system_positions_at,
)
from hybrasil.mechanics.units import J2000
from hybrasil.models.body import OrbitalBody
from hybrasil.models.elements import KeplerianElements
from hybrasil.viz.static_plot import _belt_trace, build_static_figure


def _body(name, inc, node, a=1.0, mass=1e24, status="confirmed",
          parent="Star", body_type="planet"):
    return OrbitalBody(
        name=name, body_type=body_type, parent=parent, mass_kg=mass,
        status=status,
        elements=KeplerianElements(
            semi_major_axis=a, eccentricity=0.0, inclination=inc,
            longitude_of_ascending_node=node, argument_of_periapsis=0.0,
            mean_anomaly_at_epoch=0.0, epoch=J2000, period=365.0),
    )


class TestOrbitalNormal:
    @pytest.mark.parametrize("inc,node,argp", [
        (79.2, 204.87, 37.0), (30.0, 100.0, 0.0),
        (89.8, 0.0, 180.0), (107.6, 126.0, 250.0),
    ])
    def test_it_is_the_normal_of_the_rotation_kepler_actually_applies(
            self, inc, node, argp):
        # Built from the same Euler rotation the positions come from, so an
        # orbit's points and its normal cannot drift apart: the cross product
        # of the two in-plane basis vectors must be what orbital_normal says.
        p = np.array(rotate_to_reference_frame(1.0, 0.0, inc, node, argp))
        q = np.array(rotate_to_reference_frame(0.0, 1.0, inc, node, argp))
        expected = np.cross(p, q)
        expected /= np.linalg.norm(expected)
        assert np.allclose(orbital_normal(inc, node), expected, atol=1e-12)

    def test_a_flat_orbit_has_the_reference_normal(self):
        assert orbital_normal(0.0, 0.0) == pytest.approx(Z_AXIS)

    def test_a_retrograde_orbit_points_its_normal_down(self):
        assert orbital_normal(107.6, 126.0)[2] < 0


class TestMeanPlane:
    def test_nothing_orbiting_gives_the_reference_plane(self):
        assert mean_orbital_plane([], "Star") == Z_AXIS
        assert mean_orbital_plane([_body("b", 45, 0, parent="Other")], "Star") == Z_AXIS

    def test_co_planar_bodies_give_their_own_plane(self):
        bodies = [_body("b", 89.8, 0.0), _body("c", 89.8, 0.0)]
        assert plane_tilt_deg(mean_orbital_plane(bodies, "Star")) == pytest.approx(89.8)

    def test_angular_momentum_dominates_the_average(self):
        # A Jupiter at 5 AU against a pebble at 1 AU: the plane is Jupiter's.
        bodies = [_body("giant", 2.0, 0.0, a=5.0, mass=1.9e27),
                  _body("pebble", 60.0, 0.0, a=1.0, mass=1e20)]
        assert plane_tilt_deg(mean_orbital_plane(bodies, "Star")) == pytest.approx(2.0, abs=0.01)

    def test_a_hypothetical_body_does_not_tilt_the_plane(self):
        real = [_body("b", 0.0, 0.0)]
        with_ghost = real + [_body("ghost", 80.0, 0.0, a=700.0, mass=1e28,
                                   status="hypothetical")]
        assert mean_orbital_plane(with_ghost, "Star") == mean_orbital_plane(real, "Star")

    def test_a_system_of_only_hypothetical_bodies_still_gets_a_plane(self):
        ghosts = [_body("b", 60.0, 0.0, status="hypothetical")]
        assert plane_tilt_deg(mean_orbital_plane(ghosts, "Star")) == pytest.approx(60.0)

    def test_a_massless_body_sits_the_average_out(self):
        # Pluto and Eris carry no mass in the built-in table; counting them
        # equally tilted the Solar System's plane by 5 degrees on nothing.
        bodies = [_body("planet", 1.0, 0.0, mass=1.9e27),
                  _body("iceball", 44.0, 0.0, a=68.0, mass=None)]
        assert plane_tilt_deg(mean_orbital_plane(bodies, "Star")) == pytest.approx(1.0, abs=0.01)

    def test_masses_are_only_skipped_when_some_body_has_one(self):
        massless = [_body("b", 30.0, 0.0, mass=None),
                    _body("c", 30.0, 0.0, mass=None)]
        assert plane_tilt_deg(mean_orbital_plane(massless, "Star")) == pytest.approx(30.0)

    def test_a_companion_star_does_not_set_the_planetary_plane(self):
        # The weights are m * sqrt(a), so an 0.9 M_sun companion outweighs a
        # Jupiter by ~1000x and simply is the answer.  A band is about the
        # host's planets, so the companion sits out.
        bodies = [_body("planet", 20.0, 0.0, a=1.0, mass=1.9e27),
                  _body("companion", 80.0, 0.0, a=23.4, mass=1.8e30,
                        body_type="star")]
        assert plane_tilt_deg(mean_orbital_plane(bodies, "Star")) == pytest.approx(20.0, abs=0.01)

    def test_the_binary_plane_is_still_reachable_on_request(self):
        bodies = [_body("planet", 20.0, 0.0, a=1.0, mass=1.9e27),
                  _body("companion", 80.0, 0.0, a=23.4, mass=1.8e30,
                        body_type="star")]
        tilt = plane_tilt_deg(mean_orbital_plane(bodies, "Star",
                                                 include_companions=True))
        # The planet is still in the average, and still worth about 0.01 deg
        # against a companion a thousand times its angular momentum.
        assert tilt == pytest.approx(80.0, abs=0.05)

    def test_a_host_with_only_a_companion_has_no_planetary_plane(self):
        only = [_body("companion", 80.0, 0.0, a=23.4, mass=1.8e30,
                      body_type="star")]
        assert mean_orbital_plane(only, "Star") == Z_AXIS

    def test_a_companion_is_excluded_before_the_confirmed_rule(self):
        # The companion is the only *confirmed* child.  Dropping it must fall
        # through to the host's own unconfirmed planets, not back to the binary.
        bodies = [_body("companion", 80.0, 0.0, a=23.4, mass=1.8e30,
                        body_type="star"),
                  _body("candidate", 35.0, 0.0, a=1.1, mass=1e27,
                        status="hypothetical")]
        assert plane_tilt_deg(mean_orbital_plane(bodies, "Star")) == pytest.approx(35.0, abs=0.01)

    @pytest.mark.parametrize("mass", [1.0, 1e24, 1.9e27])
    def test_opposed_orbits_cancel_back_to_the_reference_plane(self, mass):
        # The residue of the cancellation scales with the masses, so the test
        # for "this cancelled" has to scale with them too.
        opposed = [_body("b", 60.0, 0.0, mass=mass),
                   _body("c", 120.0, 180.0, mass=mass)]
        assert mean_orbital_plane(opposed, "Star") == Z_AXIS


class TestBandPlane:
    """Planets first, hypothetical ones included; then the binary partner."""

    def test_a_star_with_planets_keeps_its_planets_plane(self):
        bodies = [_body("planet", 20.0, 0.0, a=1.0, mass=1.9e27),
                  _body("companion", 80.0, 0.0, a=23.4, mass=1.8e30,
                        body_type="star")]
        assert band_plane(bodies, "Star") == mean_orbital_plane(bodies, "Star")
        assert plane_tilt_deg(band_plane(bodies, "Star")) == pytest.approx(20.0, abs=0.01)

    def test_a_candidate_planet_beats_a_known_partner(self):
        # A band is about where a planet could hold a liquid, so even an
        # unconfirmed planet says more about its plane than a star does.
        bodies = [_body("candidate", 35.0, 0.0, status="hypothetical"),
                  _body("companion", 80.0, 0.0, a=23.4, mass=1.8e30,
                        body_type="star")]
        assert plane_tilt_deg(band_plane(bodies, "Star")) == pytest.approx(35.0, abs=0.01)

    def test_a_planetless_primary_takes_its_companion_s_orbit(self):
        bodies = [_body("companion", 80.0, 30.0, a=23.4, mass=1.8e30,
                        body_type="star")]
        assert band_plane(bodies, "Star") == pytest.approx(orbital_normal(80.0, 30.0))

    def test_a_planetless_secondary_takes_its_own_orbit(self):
        bodies = [OrbitalBody(name="Star", body_type="star", parent=None),
                  _body("companion", 80.0, 30.0, a=23.4, mass=1.8e30,
                        body_type="star")]
        assert band_plane(bodies, "companion") == pytest.approx(orbital_normal(80.0, 30.0))

    def test_the_inner_pair_beats_the_outer_orbit(self):
        # A star in a tight pair that the pair's barycentre carries round a
        # wide orbit: the partner is the tight one.
        bodies = [OrbitalBody(name="Star", body_type="star", parent=None),
                  _body("pair", 120.0, 40.0, a=100.0, body_type="barycentre"),
                  _body("Ba", 35.0, 10.0, a=0.01, parent="pair", body_type="star"),
                  _body("Bb", 35.0, 10.0, a=0.05, parent="Ba", body_type="star")]
        for star in ("Ba", "Bb"):
            assert band_plane(bodies, star) == pytest.approx(orbital_normal(35.0, 10.0))

    def test_a_single_star_with_nothing_keeps_the_reference_plane(self):
        assert band_plane([OrbitalBody(name="Star", body_type="star",
                                       parent=None)], "Star") == Z_AXIS


class TestPlaneBasis:
    @pytest.mark.parametrize("normal", [
        Z_AXIS, (0.0, -1.0, 0.004), (-0.413, 0.891, 0.187), (0.3, 0.4, -0.866),
    ])
    def test_the_basis_spans_the_plane(self, normal):
        u, v = plane_basis(normal)
        n = np.array(normal) / np.linalg.norm(normal)
        assert np.dot(u, v) == pytest.approx(0.0, abs=1e-12)
        assert np.linalg.norm(u) == pytest.approx(1.0)
        assert np.linalg.norm(v) == pytest.approx(1.0)
        assert np.dot(u, n) == pytest.approx(0.0, abs=1e-12)
        assert np.dot(v, n) == pytest.approx(0.0, abs=1e-12)

    def test_a_flat_plane_keeps_the_x_axis_it_always_had(self):
        assert plane_basis(Z_AXIS) == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


class TestRingGeometry:
    def test_a_tilted_ring_is_still_a_ring_around_the_star(self):
        normal = mean_orbital_plane(get_builtin_system("trappist-1").bodies,
                                    "TRAPPIST-1")
        zone = next(z for z in solvent_zones(0.0005285766791, normal=normal)
                    if "margin" not in z.name)
        trace = _belt_trace(zone)
        pts = np.column_stack([np.asarray(trace.x), np.asarray(trace.y),
                               np.asarray(trace.z)])
        radii = np.linalg.norm(pts, axis=1)
        # Every vertex sits on one of the two edges, and every vertex lies in
        # the plane -- which is what separates a tilted ring from a sheared one.
        assert np.isclose(radii, zone.r_inner_au).sum() == len(pts) // 2
        assert np.isclose(radii, zone.r_outer_au).sum() == len(pts) // 2
        assert np.allclose(pts @ np.array(normal), 0.0, atol=1e-9)

    def test_a_tilted_band_reaches_out_of_the_reference_plane(self):
        flat = _belt_trace(next(z for z in solvent_zones(1.0)))
        tilted = _belt_trace(next(z for z in solvent_zones(1.0, normal=(0.0, -1.0, 0.0))))
        assert np.ptp(np.asarray(flat.z)) == pytest.approx(0.0)
        assert np.ptp(np.asarray(tilted.z)) > 1.0

    def test_the_stacking_offset_follows_the_normal(self):
        from hybrasil.mechanics.solvent_bands import SOLVENTS
        normal = np.array([0.0, -1.0, 0.0])
        zones = solvent_zones(1.0, SOLVENTS.values(), normal=tuple(normal))
        for zone in zones:
            pts = np.column_stack([np.asarray(_belt_trace(zone).x),
                                   np.asarray(_belt_trace(zone).y),
                                   np.asarray(_belt_trace(zone).z)])
            # Distance from the plane is the offset, for every vertex.
            assert np.allclose(pts @ normal, zone.offset_au, atol=1e-9)


class TestBuiltinSystems:
    @pytest.mark.parametrize("key,expected_tilt", [
        ("solar", 1.58),             # the invariable plane, set by Jupiter
        ("trappist-1", 89.76),       # edge-on, as the transits require
        # Alpha Centauri A has no planets of its own but the disputed Ab,
        # whose catalog elements carry no angles; a candidate planet beats the
        # companion B, so the band has no measured plane to take.
        ("alpha-centauri", 0.0),
        ("proxima-centauri", 0.0),   # the catalog gives no angles at all
    ])
    def test_each_system_gets_the_plane_its_bodies_orbit_in(self, key, expected_tilt):
        system = get_builtin_system(key)
        band = next(z for z in system.belt_zones if "band" in z.name)
        assert plane_tilt_deg(band.normal) == pytest.approx(expected_tilt, abs=0.02)

    def test_the_solar_system_is_unchanged_for_practical_purposes(self):
        # 1.58 degrees over the 1.12 AU water band -- its outer edge with
        # Earth's 33 K greenhouse offset -- is under 0.035 AU of rise: the
        # Solar System looks exactly as it did, which is the point.
        band = next(z for z in get_builtin_system("solar").belt_zones
                    if "band" in z.name)
        rise = band.r_outer_au * math.sin(math.radians(plane_tilt_deg(band.normal)))
        assert rise < 0.035

    def test_belts_stay_flat(self):
        # Only a solvent band takes the orbital plane; the asteroid and Kuiper
        # belts are drawn where they were measured, on the reference plane.
        for zone in get_builtin_system("solar").belt_zones:
            if "band" not in zone.name:
                assert zone.normal == Z_AXIS

    def test_the_tilt_is_stated_in_the_description(self):
        assert "89.8 degrees from the reference plane" in \
            get_builtin_system("trappist-1").description
        assert "14.8 degrees from the reference plane" in \
            get_builtin_system("upsilon-andromedae").description

    def test_a_companion_star_no_longer_sets_alpha_centauri_a_s_band(self):
        # It used to report 79.2 deg, which is Alpha Centauri B's orbit rather
        # than an inclination any planet of A's has.  A band is a statement
        # about one star's planetary system, so the binary sits out.
        system = get_builtin_system("alpha-centauri")
        band = next(z for z in system.belt_zones if "band" in z.name)
        assert plane_tilt_deg(band.normal) < NEGLIGIBLE_TILT_DEG
        binary = plane_tilt_deg(mean_orbital_plane(
            system.bodies, "Alpha Centauri A", include_companions=True))
        assert binary == pytest.approx(79.20, abs=0.02)

    @pytest.mark.parametrize("key,star,expected_tilt", [
        # Castor's six stars have no planets, only each other: each band lies
        # in its own inner pair's orbit (110.5 deg folds to 69.5).
        ("castor", "Castor Aa", 35.0), ("castor", "Castor Ab", 35.0),
        ("castor", "Castor Ba", 69.5), ("castor", "Castor Bb", 69.5),
        ("castor", "Castor Ca", 86.29), ("castor", "Castor Cb", 86.29),
        # B has no planets, so it takes its orbit about A.
        ("alpha-centauri", "Alpha Centauri B", 79.20),
    ])
    def test_a_planetless_star_takes_its_partner_s_plane(self, key, star,
                                                         expected_tilt):
        band = next(z for z in get_builtin_system(key).belt_zones
                    if z.is_solvent_band and z.centre_body == star)
        assert plane_tilt_deg(band.normal) == pytest.approx(expected_tilt, abs=0.02)

    def test_a_flat_system_says_nothing_about_a_plane(self):
        # Proxima's catalog elements carry no angles at all, so its band is on
        # the reference plane and the description has no tilt to report.
        system = get_builtin_system("proxima-centauri")
        assert plane_tilt_deg(
            next(z for z in system.belt_zones if "band" in z.name).normal
        ) < NEGLIGIBLE_TILT_DEG
        assert "from the reference plane" not in system.description

    def test_the_solar_systems_small_tilt_is_still_reported(self):
        # 1.6 degrees is the invariable plane, and worth stating even though
        # it is invisible: it says the band follows the planets, not z = 0.
        assert "1.6 degrees from the reference plane" in             get_builtin_system("solar").description

    def test_reference_plane_can_be_forced_back(self):
        flat = SolventChoice.parse("water", align_to_orbits=False)
        system = get_builtin_system("trappist-1", flat)
        assert all(z.normal == Z_AXIS for z in system.belt_zones)
        assert "from the reference plane" not in system.description

    def test_the_plane_is_part_of_the_cache_key(self):
        tilted = get_builtin_system("trappist-1")
        flat = get_builtin_system("trappist-1",
                                  SolventChoice.parse("water", align_to_orbits=False))
        assert tilted is not flat
        assert tilted.belt_zones[0].normal != flat.belt_zones[0].normal

    def test_a_tilted_band_still_fits_the_scene(self):
        # The scene floor is symmetric, so a band standing on edge needs the
        # same room in z that a flat one needed in x and y.
        system = get_builtin_system("trappist-1")
        orbit_paths, coil_paths = system_orbit_paths(system)
        fig = build_static_figure(system, system_positions_at(system, J2000),
                                  orbit_paths, coil_paths=coil_paths)
        band = next(z for z in system.belt_zones if "band" in z.name)
        for axis in (fig.layout.scene.xaxis, fig.layout.scene.yaxis,
                     fig.layout.scene.zaxis):
            assert axis.range[1] > band.r_outer_au


class TestABandPerStar:
    """A band belongs to one star: its plane, its radii and its centre.

    Alpha Centauri is the worked case -- three luminous stars, two of them in
    orbit, and one of those (Proxima) with three planets of its own.  It used
    to draw one band, for A, because a band was a ring around the origin.
    """

    def _system(self):
        return get_builtin_system("alpha-centauri")

    def test_every_luminous_star_gets_a_stack(self):
        system = self._system()
        centres = {z.centre_body for z in system.belt_zones if z.is_solvent_band}
        assert centres == {"Alpha Centauri A", "Alpha Centauri B",
                           "Proxima Centauri"}

    def test_each_stack_is_sized_by_its_own_star(self):
        # Luminosity runs 1.521 / 0.503 / 0.00151, and a band scales as sqrt(L),
        # so no two of these stars can share a radius.
        system = self._system()
        outer = {z.centre_body: z.r_outer_au for z in system.belt_zones
                 if z.is_solvent_band}
        assert outer["Alpha Centauri A"] > outer["Alpha Centauri B"]
        assert outer["Alpha Centauri B"] > outer["Proxima Centauri"]

    def test_a_band_is_drawn_around_its_own_star(self):
        system = self._system()
        positions = system_positions_at(system, J2000)
        zone = next(z for z in system.belt_zones
                    if z.centre_body == "Proxima Centauri")
        centre = np.array(positions["Proxima Centauri"])
        assert np.linalg.norm(centre) > 1000.0, "Proxima is far from the origin"

        trace = _belt_trace(zone, centre=tuple(centre))
        pts = np.column_stack([np.asarray(trace.x), np.asarray(trace.y),
                               np.asarray(trace.z)])
        radii = np.linalg.norm(pts - centre, axis=1)
        assert radii.min() == pytest.approx(zone.r_inner_au, rel=1e-9)
        assert radii.max() == pytest.approx(zone.r_outer_au, rel=1e-9)

    def test_a_primarys_band_still_sits_on_the_origin(self):
        system = get_builtin_system("solar")
        zone = next(z for z in system.belt_zones if z.is_solvent_band)
        assert zone.centre_body == "Sun"
        trace = _belt_trace(zone, centre=(0.0, 0.0, 0.0))
        pts = np.column_stack([np.asarray(trace.x), np.asarray(trace.y),
                               np.asarray(trace.z)])
        assert np.linalg.norm(pts, axis=1).max() == pytest.approx(
            zone.r_outer_au, rel=1e-9)

    def test_the_scene_is_wide_enough_for_a_distant_stars_band(self):
        # Proxima's band is 0.03 AU across but sits 8,700 AU out.  Claiming the
        # radius alone would leave it outside the box entirely.
        from hybrasil.viz.static_plot import belt_scene_extent
        assert belt_scene_extent(self._system()) > 8000.0

    def test_one_star_means_no_star_in_the_legend(self):
        # The search box reads these names, and a single-star system's legend
        # must be exactly what it always was.
        # Upsilon Andromedae left this list on 9 Oct 2026, when ups And B took
        # a luminosity and a stack of its own.
        for key in ("solar", "trappist-1", "proxima-centauri"):
            for zone in get_builtin_system(key).belt_zones:
                assert "\u2014" not in zone.name
                assert zone.star_label == ""

    def test_more_than_one_star_puts_the_star_in_the_legend(self):
        for zone in self._system().belt_zones:
            assert zone.star_label in ("Alpha Centauri A", "Alpha Centauri B",
                                       "Proxima Centauri")
            assert zone.star_label in zone.name

    def test_each_stars_bands_are_stacked_against_its_own_siblings(self):
        # Offsets exist so overlapping bands do not z-fight, and only bands
        # around the same star can overlap.  Ranking across the figure would
        # lift one star's bands by another star's radii.
        system = get_builtin_system("alpha-centauri", SolventChoice.parse("all"))
        for centre in ("Alpha Centauri A", "Proxima Centauri"):
            stack = [z for z in system.belt_zones if z.centre_body == centre
                     and z.r_outer_au > 0]
            assert min(z.offset_au for z in stack) == 0.0
            for zone in stack:
                assert abs(zone.offset_au) < zone.r_outer_au
