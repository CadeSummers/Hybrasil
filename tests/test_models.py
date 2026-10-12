# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for data models."""

import pytest
from hybrasil.models.elements import KeplerianElements
from hybrasil.models.body import OrbitalBody
from hybrasil.models.system import StarSystem

J2000 = 2451545.0


def _earth_elements():
    return KeplerianElements(
        semi_major_axis=1.0, eccentricity=0.017, inclination=0.0,
        longitude_of_ascending_node=0.0, argument_of_periapsis=102.9,
        mean_anomaly_at_epoch=100.0, epoch=J2000, period=365.25,
    )


def _make_system():
    sun = OrbitalBody(name="Sun", body_type="star", color="#FFD700")
    earth = OrbitalBody(name="Earth", body_type="planet", parent="Sun",
                        elements=_earth_elements(), color="#4488FF")
    moon = OrbitalBody(name="Moon", body_type="moon", parent="Earth",
                       elements=KeplerianElements(
                           semi_major_axis=0.00257, eccentricity=0.055,
                           inclination=5.1, longitude_of_ascending_node=125.0,
                           argument_of_periapsis=318.0, mean_anomaly_at_epoch=115.0,
                           epoch=J2000, period=27.32,
                       ))
    return StarSystem(name="Test", description="", bodies=[sun, earth, moon])


class TestStarSystem:
    def test_get_body(self):
        s = _make_system()
        assert s.get_body("Earth").name == "Earth"

    def test_get_body_missing(self):
        s = _make_system()
        with pytest.raises(KeyError):
            s.get_body("Mars")

    def test_get_stars(self):
        s = _make_system()
        assert len(s.get_stars()) == 1
        assert s.get_stars()[0].name == "Sun"

    def test_get_planets(self):
        s = _make_system()
        assert len(s.get_planets()) == 1

    def test_get_moons_of(self):
        s = _make_system()
        moons = s.get_moons_of("Earth")
        assert len(moons) == 1
        assert moons[0].name == "Moon"

    def test_filter_bodies(self):
        s = _make_system()
        filtered = s.filter_bodies(["Earth"])
        names = {b.name for b in filtered.bodies}
        assert "Sun" in names   # stars always kept
        assert "Earth" in names
        assert "Moon" not in names


class TestOrbitalBody:
    def test_label_default(self):
        b = OrbitalBody(name="Earth", body_type="planet")
        assert b.label() == "Earth"

    def test_label_override(self):
        b = OrbitalBody(name="Earth", body_type="planet", display_name="Terra")
        assert b.label() == "Terra"
