# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The 100 Brightest Stars tab: a hundred ranked points of light, read by its own loader only.

The tab has every Systems column, so the catalog must not take its rows for systems
(`BRIGHTEST_SIGNATURE`). These read the snapshot in `data/` (26 Nov 2026, `data/brightest_stars/`).
"""
import pytest

from hybrasil.data import snapshot
from hybrasil.data.brightest_loader import TAB, brightest_table, parse_brightest
from hybrasil.data.catalog_loader import build_tables, classify_tables, parse_workbook

from tests.test_catalog_loader import SYSTEM_HEADERS, make_workbook


@pytest.fixture(scope="module")
def workbook():
    return snapshot.load_snapshot_workbook()


@pytest.fixture(scope="module")
def stars(workbook):
    return parse_brightest(workbook)


def test_a_hundred_points_of_light_brightest_first(stars):
    assert len(stars) == 100
    assert [s.rank_apparent for s in stars] == list(range(1, 101))
    mags = [s.apparent_mag for s in stars]
    assert mags == sorted(mags)
    assert stars[0].name == "alf CMa" and "Sirius" in stars[0].nickname


def test_each_luminosity_rank_is_a_full_order(stars):
    for ranks in ([s.rank_bolometric for s in stars], [s.rank_visual for s in stars]):
        assert sorted(ranks) == list(range(1, 101))
    # The eye's order is not the true one: the brightest star in the sky is a modest one nearby.
    sirius = stars[0]
    assert sirius.rank_bolometric > 50 and sirius.rank_visual > 50
    by_light = sorted(stars, key=lambda s: s.rank_bolometric)
    lums = [s.point_luminosity_sun for s in by_light]
    assert lums == sorted(lums, reverse=True) and lums[0] > 100_000


def test_every_star_can_be_placed_and_most_can_be_moved(stars):
    assert all(s.has_position and s.distance_ly > 0 for s in stars)
    assert all(s.stellar_class and s.constellation for s in stars)
    assert sum(s.has_motion for s in stars) == 100
    far = max(stars, key=lambda s: s.distance_ly)
    assert far.distance_ly > 1000                # the view's extent is this star's distance


def test_the_tab_is_not_a_systems_tab(workbook, stars):
    table = brightest_table(workbook)
    assert table is not None and table.title == TAB
    roles = classify_tables(build_tables(workbook))
    assert TAB not in {t.title for group in roles.values() for t in group}
    catalog = parse_workbook(workbook)
    # Canopus is on no other tab, so it can only have come from this one.
    assert "alf Car" in {s.name for s in stars} and "alf Car" not in catalog.system_rows


def test_also_on_tabs_names_rows_that_exist(workbook, stars):
    catalog = parse_workbook(workbook)
    seen = 0
    for s in stars:
        for part in filter(None, (p.strip() for p in s.on_tabs.split(";"))):
            tab, names = part.split(":", 1)
            if tab == "Systems":
                seen += 1
                assert all(n.strip() in catalog.system_rows for n in names.split(","))
    assert seen >= 4                             # alf Cen, Aldebaran, Pollux, Hamal


def test_a_tab_with_an_apparent_rank_column_is_skipped():
    wb = make_workbook()
    wb["tabs"][TAB] = [SYSTEM_HEADERS + ["Apparent rank"], ["Faraway Giant"] + [""] * (len(SYSTEM_HEADERS) - 1) + [1]]
    assert "Faraway Giant" not in parse_workbook(wb).system_rows
    assert [s.name for s in parse_brightest(wb)] == ["Faraway Giant"]


def test_a_workbook_without_the_tab_has_no_brightest_stars():
    assert parse_brightest(make_workbook()) == []
