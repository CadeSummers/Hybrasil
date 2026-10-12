# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The baseline: every featured system is in the viewer, whatever opened it.

`python -m hybrasil.cli` opens a switcher.  Before this, only
`--source builtin` got one; `--source catalog` or `--source file` opened a
single system and the featured ones were simply gone.
"""

from pathlib import Path

import pytest

from hybrasil import cli
from hybrasil.data.builtin_systems import BUILTIN_NAMES
from hybrasil.models.system import StarSystem
from hybrasil.views import FEATURED_VIEWS

# The three.js viewer also gets every featured view, after the built-ins.
FEATURED = list(BUILTIN_NAMES) + list(FEATURED_VIEWS)

EXAMPLE = Path(__file__).resolve().parent.parent / "schemas" / "custom_system.yaml.example"


@pytest.fixture
def opened(monkeypatch):
    """What the CLI would have opened: ({key: figure}, initial key)."""
    seen = {}

    def fake_show(figures, initial, extra_js=""):
        seen["figures"], seen["initial"] = figures, initial

    monkeypatch.setattr(cli, "show_three_in_browser", fake_show)
    monkeypatch.setattr(cli, "show_in_browser_multi", fake_show)
    return seen


class TestEveryFeaturedSystemIsAlwaysThere:
    def test_a_builtin_opens_among_all_of_them(self, opened):
        cli.main(["--system", "trappist-1", "--frames", "4"])
        assert list(opened["figures"]) == FEATURED
        assert opened["initial"] == "trappist-1"

    def test_an_alias_is_not_listed_twice(self, opened):
        cli.main(["--system", "proxima", "--frames", "4"])
        assert list(opened["figures"]) == FEATURED
        assert opened["initial"] == "proxima-centauri"

    def test_a_system_from_a_file_is_added_after_them_and_opens_first(
            self, opened, tmp_path):
        custom = tmp_path / "custom.yaml"
        custom.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        cli.main(["--source", "file", "--system", str(custom), "--frames", "4"])
        keys = list(opened["figures"])
        assert keys[:len(FEATURED)] == FEATURED
        assert len(keys) == len(FEATURED) + 1
        assert opened["initial"] == keys[-1]

    def test_the_plotly_renderer_gets_them_too(self, opened):
        # ...but not the views, which are drawn in light years and so need
        # the three.js viewer.
        cli.main(["--system", "solar", "--renderer", "plotly", "--frames", "4"])
        assert list(opened["figures"]) == list(BUILTIN_NAMES)


class TestACatalogSystemAFeaturedOneDraws:
    def _system(self, name):
        return StarSystem(name=name, description="", bodies=[], source="catalog")

    def test_opens_as_the_featured_one(self):
        assert cli._featured_twin(self._system("55 Cnc A")) == "55-cancri"
        assert cli._featured_twin(self._system("alf Cen A")) == "alpha-centauri"

    def test_anything_else_opens_as_itself(self):
        assert cli._featured_twin(self._system("HD 18143")) is None

    def test_only_a_catalog_system_is_folded(self):
        s = StarSystem(name="55 Cnc A", description="", bodies=[], source="file")
        assert cli._featured_twin(s) is None
