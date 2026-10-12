# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for data loaders."""

import pytest
from hybrasil.data.builtin_systems import get_builtin_system, BUILTIN_NAMES
from hybrasil.data.loader import get_system


class TestBuiltinLoader:
    def test_solar_system_loads(self):
        system = get_builtin_system("solar")
        assert system.name == "Solar System"
        assert len(system.get_planets()) == 9  # 8 confirmed + Planet Nine (hypothetical)

    def test_solar_system_has_sun(self):
        system = get_builtin_system("solar")
        stars = system.get_stars()
        assert len(stars) == 1
        assert stars[0].name == "Sun"

    def test_solar_planets_have_elements(self):
        system = get_builtin_system("solar")
        for planet in system.get_planets():
            assert planet.elements is not None

    def test_trappist1_loads(self):
        system = get_builtin_system("trappist-1")
        assert "TRAPPIST-1" in system.name
        # 7 planets
        assert len(system.get_planets()) == 7

    def test_unknown_system_raises(self):
        with pytest.raises(ValueError, match="Unknown built-in"):
            get_builtin_system("bogus-system")

    def test_case_insensitive(self):
        s1 = get_builtin_system("Solar")
        s2 = get_builtin_system("SOLAR")
        assert s1.name == s2.name


class TestDispatchLoader:
    def test_builtin_dispatch(self):
        system = get_system("builtin", "solar")
        assert system is not None

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            get_system("ftp", "solar")

    def test_file_missing_raises(self):
        from hybrasil.data.custom_loader import load_custom_system
        with pytest.raises(FileNotFoundError):
            load_custom_system("nonexistent_file.yaml")
