# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Brightest Stars in the Night Sky: the 100 Brightest Stars tab as a view of stars in motion.

The same figure as Nearby Stellar Motion (`star_motion.build_star_motion_figure`), through a
`MotionView` of its own: the scene reaches the most distant of the hundred, a star is sized by how
bright it looks from Earth (or, at a switch, by how bright it is), each carries its three ranks, and
the distances can be compressed so the far supergiants and the near neighbours share a screen.
See docs/architecture/star-motion.md, "Brightest Stars in the Night Sky".
"""

from __future__ import annotations

import math
from typing import Optional

import plotly.graph_objects as go

from ..data.builtin_systems import BUILTIN_NAMES, system_id_for_host
from ..data.catalog_loader import split_names
from ..models.nearby import NearbyStar
from .star_motion import (ARROW_YEARS, LY_PER_PC, SUN_SIZE, MotionView, build_star_motion_figure,
                          star_motion_info)

VIEW_KEY = "brightest-star-motion"
VIEW_NAME = "Brightest Stars in the Night Sky"

# The scene is this much wider than the most distant star, and the axes stop short of its edge.
MARGIN = 1.1
REFERENCE_FRACTION = 0.82

# The Sun's neighbourhood, for scale: Nearby Stellar Motion's whole extent.
SPHERE_LY = 100.0
SPHERE_COLOUR = "#8899BB"
# With the distances compressed, the radii that say how much: drawn only then.
SHELLS_LY = (10.0, 1000.0)
COMPRESS_R0_LY = 10.0

# Optional sets, each a row of the viewer's Even more features menu.
SIZE_SET = "size-luminosity"
TAG_SET = "rank-labels"
COMPRESS_SET = "compress-distances"
TAG_MODES = (("apparent", "Apparent brightness"), ("bolometric", "Luminosity (all light)"),
             ("visual", "Luminosity (visible light)"))


def apparent_size(v_mag: Optional[float]) -> float:
    """Pixels from the apparent V magnitude: 13 for Sirius, about 4 for the hundredth star."""
    if v_mag is None:
        return 5.0
    return max(4.0, min(14.0, 13.0 - 2.2 * (v_mag + 1.44)))


def luminosity_size(luminosity_sun: Optional[float]) -> float:
    """Pixels from the luminosity: 4 for a Sun, 14 at 800,000 L-sun.  Nearby Stellar Motion's scale
    tops out at 1,500 L-sun, which most of these hundred pass."""
    if luminosity_sun is None or luminosity_sun <= 0:
        return 5.0
    return max(3.0, min(14.0, 4.0 + 1.7 * math.log10(luminosity_sun)))


def luminosity(s: NearbyStar) -> Optional[float]:
    """What the bolometric rank orders: every star of the point of light together."""
    return s.point_luminosity_sun if s.point_luminosity_sun is not None else s.luminosity_sun


def common_name(s: NearbyStar) -> str:
    names = split_names(s.nickname)
    return names[0] if names else s.name


def goto_id(s: NearbyStar) -> str:
    """The system the star opens, from the tab's `Also on tabs`: the Sun's, its Systems-tab host's, or
    its hierarchy on the Planetless 4+ Stars tab.  "" for a star no other tab draws as a system."""
    if s.is_sun:
        return system_id_for_host(s.name)
    for part in s.on_tabs.split(";"):
        tab, _, names = part.partition(":")
        first = names.split(",")[0].strip()
        if tab.strip() == "Systems" and first:
            return system_id_for_host(first)
        if tab.strip().startswith("Planetless"):
            featured = system_id_for_host(s.name)
            return featured if featured in BUILTIN_NAMES else f"planetless:{s.name}"
    return ""


def _circles(radius: float, steps: int = 72) -> list[tuple[float, float, float]]:
    """Three great circles of a sphere round the Sun as one polyline: the galactic plane's, then the two
    through the poles, joined along a quarter of the first."""
    turn = [2 * math.pi * i / steps for i in range(steps + 1)]
    xy = [(radius * math.cos(a), radius * math.sin(a), 0.0) for a in turn]
    xz = [(radius * math.cos(a), 0.0, radius * math.sin(a)) for a in turn]
    yz = [(0.0, radius * math.cos(a), radius * math.sin(a)) for a in turn]
    return xy + xz + xy[:steps // 4 + 1] + yz


def sphere_trace(radius: float, compress_only: bool = False) -> go.Scatter3d:
    """A sphere of `radius` ly round the Sun, labelled with its radius.  `compress_only` is one of the
    shells the viewer draws only while the distances are compressed."""
    pts = _circles(radius)
    label = f"{radius:,.0f} ly"
    return go.Scatter3d(
        x=[p[0] for p in pts], y=[p[1] for p in pts], z=[p[2] for p in pts], mode="lines+text",
        name=f"{label} from the Sun", text=[""] * (len(pts) - 1) + [label],
        line=dict(color=SPHERE_COLOUR, width=1), opacity=0.35,
        showlegend=not compress_only, hoverinfo="skip",
        meta={"compress_only": True} if compress_only else None,
    )


def _ranks(s: NearbyStar) -> dict:
    return {k: str(v) for k, v in (("apparent", s.rank_apparent), ("bolometric", s.rank_bolometric),
                                   ("visual", s.rank_visual)) if v is not None}


def _body_meta(s: NearbyStar) -> dict:
    if s.is_sun:
        return {}
    return {"alt_size": round(luminosity_size(luminosity(s)), 2), "tags": _ranks(s)}


def _of(rank: Optional[int], n: int) -> str:
    return "no data" if rank is None else f"{rank} of {n}"


def brightest_rows(s: NearbyStar, rows: list, n: int) -> list:
    """The star's panel: the standard rows, with what the tab adds and without what it does not hold."""
    if s.is_sun:
        return rows
    out = []
    for row in rows:
        label = row[0]
        if label == "Planets":
            continue                    # the tab lists no planets; "Go to system" opens them where there are any
        if label == "Stellar partners":
            row = ["Stars of this point of light", "; ".join(s.partners) or "no data",
                   f"{s.n_stars} on file" if s.n_stars else ""]
        if label == "Distance" and s.distance_ly is not None:
            err = f" ± {s.distance_err_ly:,.4g}" if s.distance_err_ly is not None else ""
            row = [label, f"{s.distance_ly:,.2f}{err} ly ({s.distance_ly / LY_PER_PC:,.2f} pc)",
                   s.distance_source]
        if label == "Luminosity":
            row = [label, row[1], "the host star's"]
            out += [
                ["Luminosity of the point", "no data" if luminosity(s) is None else f"{luminosity(s):,.4g} L☉",
                 "every star of it together, all wavelengths"],
                ["Luminosity rank (all light)", _of(s.rank_bolometric, n), "bolometric"],
                ["Visual luminosity", "no data" if s.visual_luminosity_sun is None
                 else f"{s.visual_luminosity_sun:,.4g} L☉", "in the V band"],
                ["Luminosity rank (visible light)", _of(s.rank_visual, n), ""],
            ]
        out.append(row)
        if label == "Spectral type":
            where = ", ".join(x for x in (s.designation, s.constellation) if x)
            if where:
                out.append(["Designation, constellation", where, ""])
            out += [
                ["Apparent brightness rank", _of(s.rank_apparent, n), "by combined V magnitude"],
                ["Apparent magnitude (V)", "no data" if s.apparent_mag is None else f"{s.apparent_mag:+.2f}",
                 f"varies {s.v_range}" if s.v_range else ""],
                ["Absolute magnitude (M_V)", "no data" if s.abs_mag is None else f"{s.abs_mag:+.2f}",
                 "" if s.extinction_av is None else f"extinction A_V {s.extinction_av:.2f}"],
                ["Variability", s.variable_type or "no data", ""],
            ]
    if s.radius_sun is not None:
        out.append(["Radius", f"{s.radius_sun:,.4g} R☉", ""])
    if s.on_tabs:
        out.append(["Also on tabs", s.on_tabs, "of the workbook"])
    return out


def sun() -> NearbyStar:
    """The Sun at the origin, as Nearby Stellar Motion draws it: the tab lists night-sky stars only."""
    from ..data.nearby_loader import SUN, with_sources
    return with_sources(NearbyStar(name=SUN, stellar_class="G2V", luminosity_class="Main sequence",
                                   luminosity_sun=1.0, mass_sun=1.0, age_gyr=4.57, metallicity=0.0,
                                   is_sun=True), {})


def view_config(stars: list[NearbyStar]) -> MotionView:
    """The `MotionView` for these stars: everything about the view that depends on the data."""
    placed = [s for s in stars if s.has_position and not s.is_sun]
    far = max(placed, key=lambda s: s.distance_ly)
    half = far.distance_ly * MARGIN
    n = len(placed)

    def title(counts: dict, source: str) -> str:
        return (f"{VIEW_NAME} — {counts['systems']} stars, out to {far.distance_ly:,.0f} ly "
                f"({common_name(far)}), {counts['moving']} with a measured motion · sized by apparent "
                f"brightness · arrow = {ARROW_YEARS:,} yr of travel" + (f" · {source}" if source else ""))

    meta = {
        "alt_size": {"set": SIZE_SET},
        "tags": {"set": TAG_SET, "prefix": "#"},
        "compress": {"set": COMPRESS_SET, "r0": COMPRESS_R0_LY},
        "optional_sets": [
            {"key": SIZE_SET, "label": "Size by true luminosity", "default": False, "menu": "features",
             "title": "Size each star by how much light it gives out, not by how bright it looks from Earth"},
            {"key": TAG_SET, "label": "Rank labels", "default": False, "menu": "features",
             "modes": [{"key": k, "label": lbl} for k, lbl in TAG_MODES],
             "title": f"Label each star with its place among the {n}: by apparent brightness, then by "
                      "luminosity over all wavelengths, then in visible light"},
            {"key": COMPRESS_SET, "label": "Compress distances", "default": False, "menu": "features",
             "title": "Draw each star at the logarithm of its distance, in its true direction, so the "
                      f"nearest and the farthest share the screen; shells mark 10, 100 and 1,000 ly"},
        ],
    }
    return MotionView(
        key=VIEW_KEY, name=VIEW_NAME, half_ly=half, reference_ly=half * REFERENCE_FRACTION,
        size=lambda s: SUN_SIZE if s.is_sun else apparent_size(s.apparent_mag),
        # Wide enough to show a far star's surroundings, never tighter than the nearby view's.
        zoom_half=lambda s: max(4.0, 0.05 * (s.distance_ly or 0.0)),
        title=title, planet_hosts_only=False, body_meta=_body_meta, rows=lambda s, rows: brightest_rows(s, rows, n), goto=goto_id,
        extra_traces=(sphere_trace(SPHERE_LY),) + tuple(sphere_trace(r, True) for r in SHELLS_LY),
        meta=meta,
    )


def build_brightest_figure(stars: list[NearbyStar], source: str = "") -> tuple[go.Figure, dict]:
    """(figure, body info) for the hundred, with the Sun added at the origin."""
    config = view_config(stars)
    everyone = [sun()] + list(stars)
    return (build_star_motion_figure(everyone, source, config=config),
            star_motion_info(everyone, config))
