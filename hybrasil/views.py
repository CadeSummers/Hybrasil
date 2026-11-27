# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Featured views: featured buttons that show something other than one star system.

A built-in system (`builtin_systems.BUILTIN_NAMES`) is a StarSystem with orbits,
bands and a Plotly twin, and a great deal of code and testing assumes exactly
that.  A view is a figure built directly -- Nearby Stellar Motion draws several
hundred stars at light-year scale with no orbits at all -- so it is registered
here instead, after the built-ins, and only the three.js viewer shows it.

`build(catalog=None, planetless=None)` returns ``(figure, body_info)``.
`catalog` is a parsed Catalog and `planetless` the Planetless 4+ Stars systems
(`planetless_loader.load_planetless()`), when the caller already holds them
(the web app does); without them the view reads the live sheet, or the
committed snapshot when the sheet cannot be reached.
"""

from __future__ import annotations

from typing import Callable, Optional


def _nearby_star_motion(catalog=None, planetless=None):
    from .data.nearby_loader import known_nearby, load_planetless_nearby, nearby_catalog, nearby_stars
    from .viz.star_motion import build_star_motion_figure, star_motion_info
    catalog, source = nearby_catalog(catalog)
    stars = nearby_stars(catalog)
    extra = load_planetless_nearby(planetless)
    # The unclassified objects carry their own compact info in the figure, not 10,000 entries here.
    return (build_star_motion_figure(stars, source, extra, known_nearby(catalog)),
            star_motion_info(stars + extra))


def _brightest_star_motion(catalog=None, planetless=None):
    from .data.brightest_loader import load_brightest_sourced
    from .viz.brightest_stars import build_brightest_figure
    stars, source = load_brightest_sourced()
    if not stars:
        raise LookupError("the workbook has no 100 Brightest Stars tab")
    return build_brightest_figure(stars, source)


# key -> (button label, builder), in button order.
FEATURED_VIEWS: dict[str, tuple[str, Callable]] = {
    "nearby-star-motion": ("Nearby Stellar Motion", _nearby_star_motion),
}

# Views with no featured button: the web app lists them under Stellar Motion, after the featured
# views, and nothing else shows them.  key -> (name, builder, index fields).
LISTED_VIEWS: dict[str, tuple[str, Callable, dict]] = {
    "brightest-star-motion": ("Brightest Stars in the Night Sky", _brightest_star_motion,
                              {"n_stars": 100,
                               "aliases": ["brightest stars", "100 brightest stars", "night sky",
                                           "brightest stars in the sky"]}),
}


def view_name(key: str) -> str:
    return (FEATURED_VIEWS.get(key) or LISTED_VIEWS[key])[0]


def build_view(key: str, catalog: Optional[object] = None, planetless: Optional[dict] = None):
    """(figure, body_info) for one view, featured or listed."""
    return (FEATURED_VIEWS.get(key) or LISTED_VIEWS[key])[1](catalog, planetless)


def system_kind(key: str) -> str:
    """The System Type the viewer's dropdown lists `key` under.

    "motion" for a featured view, the `FEATURED_KINDS` entry for a built-in
    that has one, else "planetary" -- every catalog system included.
    """
    if key in FEATURED_VIEWS or key in LISTED_VIEWS:
        return "motion"
    from .data.builtin_systems import FEATURED_KINDS
    return FEATURED_KINDS.get(key, "planetary")
