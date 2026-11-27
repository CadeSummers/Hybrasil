# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The 100 Brightest Stars tab, as stars with a place, a motion and three ranks.

One row is one naked-eye point of light, ranked by its combined apparent V magnitude
(`data/brightest_stars/`). The tab has every Systems column, so `catalog_loader` skips it by
its `Apparent rank` column (`BRIGHTEST_SIGNATURE`); this module is its only reader.

A row's columns are the Systems tab's, with the same meanings, plus the brightness ones.
"""
from __future__ import annotations

import sys
from typing import Optional

from ..models.nearby import NearbyStar
from .catalog_loader import (BRIGHTEST_SIGNATURE, Table, build_tables, nickname_cell,
                             source_columns)
from .nearby_loader import with_sources

TAB = "100 Brightest Stars"

_NUMBERS = {
    "distance_ly": "distance (ly)", "l_deg": "galactic longitude l (deg)", "b_deg": "galactic latitude b (deg)",
    "speed_kms": "space velocity (km/s)", "motion_l_deg": "motion toward l (deg, heliocentric)",
    "motion_b_deg": "motion toward b (deg, heliocentric)", "radial_velocity_kms": "radial velocity (km/s)",
    "total_pm_arcsec_yr": "total proper motion, μ (arcsec/yr)", "age_gyr": "age (gyr)",
    "mass_sun": "host mass (m-sun)", "metallicity": "metallicity [fe/h]",
    "luminosity_sun": "host luminosity (l-sun)", "apparent_mag": "apparent magnitude (v)",
    "abs_mag": "absolute magnitude (m_v)", "visual_luminosity_sun": "visual luminosity (l-sun)",
    "point_luminosity_sun": "point luminosity (l-sun)", "radius_sun": "radius (r-sun)",
    "distance_err_ly": "distance uncertainty (ly)", "extinction_av": "extinction a_v",
}
_INTS = {
    "rank_apparent": "apparent rank", "rank_bolometric": "luminosity rank (bolometric)",
    "rank_visual": "luminosity rank (visual)", "n_stars": "stars in system",
}
_TEXT = {
    "stellar_class": "stellar class", "luminosity_class": "luminosity class",
    "kinematics_source": "kinematics source", "constellation": "constellation",
    "designation": "bayer / flamsteed designation", "distance_source": "distance source",
    "variable_type": "variable type", "v_range": "v range", "on_tabs": "also on tabs",
}


def brightest_table(workbook: dict) -> Optional[Table]:
    """The tab, found by its headers as every tab is, or None when the workbook has none."""
    return next((t for t in build_tables(workbook) if t.has(*BRIGHTEST_SIGNATURE)), None)


def parse_brightest(workbook: dict) -> list[NearbyStar]:
    """One star per row, in apparent-rank order; an empty list when the workbook has no such tab."""
    table = brightest_table(workbook)
    if table is None:
        return []
    out = []
    for row in table.rows:
        name = table.text(row, "system / host")
        if not name:
            continue
        kw = {f: table.number(row, h) for f, h in _NUMBERS.items()}
        for f, h in _INTS.items():
            n = table.number(row, h)
            kw[f] = int(n) if n is not None else None
        kw.update({f: table.text(row, h) for f, h in _TEXT.items()})
        partners = [p.strip() for p in table.text(row, "system stars").splitlines() if p.strip()]
        star = NearbyStar(name=name, nickname=nickname_cell(table, row), partners=partners, **kw)
        out.append(with_sources(star, source_columns(table, row)))
    out.sort(key=lambda s: (s.rank_apparent is None, s.rank_apparent or 0))
    return out


def load_brightest(workbook: Optional[dict] = None) -> list[NearbyStar]:
    """The given workbook's tab, else the live sheet's, else the committed snapshot's."""
    from .snapshot import snapshot_only
    if workbook is None and not snapshot_only():
        try:
            from .google_sheets import get_workbook
            workbook = get_workbook()
        except Exception as e:                       # no credential, no network, no cache
            print(f"{TAB}: live sheet unavailable ({e.__class__.__name__}); using the committed snapshot.",
                  file=sys.stderr)
    if workbook is None:
        from .snapshot import load_snapshot_workbook
        workbook = load_snapshot_workbook()
    return parse_brightest(workbook)
