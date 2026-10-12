# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A re-sort must carry every column of a star tab along with its rows.

On 3-4 Oct 2026 Multi-stars was re-sorted through a basic filter that ended at AP on a tab that runs to AT, so
'Separation from', 'Separation (AU)', 'Separation type' and 'Separation source' stayed where they were: 91 stars
showed another star's separation, and nothing failed -- catalog_loader draws a companion whose 'Separation from' is
not in its system round the primary. data/sort_repair/repair.py put them back. These read the snapshot in data/.
"""
import glob
import os

import pytest
from openpyxl.utils import range_boundaries

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MS = "Multi-stars within 100 ly"


@pytest.fixture(scope="module")
def workbook():
    openpyxl = pytest.importorskip("openpyxl")
    snaps = sorted(glob.glob(os.path.join(ROOT, "data", "hybrasil-*.xlsx")))
    if not snaps:
        pytest.skip("no workbook snapshot in data/")
    return openpyxl.load_workbook(snaps[-1], data_only=True)     # not read-only: that drops the filter


def _rows(ws):
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    return rows[0], [r for r in rows[1:] if r[0]]


def stray_separations(head, rows):
    """Stars whose 'Separation from' names a star outside their own system."""
    k, s = head.index("Star (component)"), head.index("Separation from")
    members = {}
    for r in rows:
        members.setdefault(r[0], set()).add(r[k])
    return [r[k] for r in rows if r[s] and r[s] not in members[r[0]]]


class TestSeparationsStayWithTheirStars:
    def test_every_separation_is_from_a_star_of_its_own_system(self, workbook):
        head, rows = _rows(workbook[MS])
        assert stray_separations(head, rows) == []

    def test_the_check_sees_a_scramble(self, workbook):
        """Shift AQ:AT down a row, as a sort that leaves them behind does: the check must notice."""
        head, rows = _rows(workbook[MS])
        s0 = head.index("Separation from")
        shifted = [r[:s0] + rows[i - 1][s0:] for i, r in enumerate(rows)]
        assert len(stray_separations(head, shifted)) > 20


class TestFiltersCoverTheWholeTable:
    """The cause: a filter's sort moves only the columns inside its range."""

    @pytest.mark.parametrize("tab", [MS, "Systems within 100 ly"])
    def test_filter_spans_every_column_and_row(self, workbook, tab):
        ws = workbook[tab]
        head, rows = _rows(ws)
        assert ws.auto_filter.ref, f"{tab} has no filter"
        c0, r0, c1, r1 = range_boundaries(ws.auto_filter.ref.replace("$", ""))
        width = max(i for i, h in enumerate(head) if h) + 1
        assert (c0, r0) == (1, 1)
        assert c1 >= width, f"{tab}: filter ends at column {c1}, table at {width}"
        assert r1 >= len(rows) + 1, f"{tab}: filter ends at row {r1}, data at {len(rows) + 1}"
