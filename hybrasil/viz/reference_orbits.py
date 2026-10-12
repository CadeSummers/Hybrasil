# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reference orbits: Mercury's, Earth's and Neptune's orbit drawn round every star, for scale.

Each is a circle at the planet's semi-major axis -- the built-in Solar System's own J2000 value, so the reference
and the planet drawn round the Sun agree -- in the planet's colour, dashed.  Every star of the system gets one, a
star in orbit included (Alpha Centauri's three, a hierarchy's every member), so the reader can see how big the
system is against the Solar System.  Like the photosynthesis rings, they are a three.js feature, one toggle each in
its Even more features menu and off by default, carried on ``layout.meta`` rather than as Plotly traces: no trace
index anywhere moves (CLAUDE.md's band rule).  A ring lies in its star's band plane and rides with the star.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from ..mechanics.time_series import system_positions_at
from ..models.system import StarSystem
from .photosynthesis_rings import ring_points, star_normal

META_KEY = "reference_orbits"
PLANETS = ("Neptune", "Earth", "Mercury")        # the menu's order
SET_PREFIX = "reference-"


def set_key(planet: str) -> str:
    return SET_PREFIX + planet.lower()


@lru_cache(maxsize=1)
def reference_planets() -> tuple[tuple[str, float, str], ...]:
    """(planet, semi-major axis in AU, colour), from the built-in Solar System."""
    from ..data.builtin_systems import get_builtin_system
    solar = get_builtin_system("solar")
    out = []
    for name in PLANETS:
        b = solar.get_body(name)
        out.append((name, b.elements.semi_major_axis, b.color))
    return tuple(out)


def _au(a: float) -> str:
    return f"{a:.2f} AU" if a < 10 else f"{a:.1f} AU"


def orbit_specs(system: StarSystem, t_jd: float) -> list[dict]:
    """Every reference ring the figure carries: one per planet per star."""
    stars = [b for b in system.bodies if b.body_type == "star"]
    if not stars:
        return []
    positions = system_positions_at(system, t_jd)
    label = len(stars) > 1
    specs = []
    for planet, a, colour in reference_planets():
        for star in stars:
            specs.append({
                "name": f"{planet}'s orbit" + (f" ({star.name})" if label else ""),
                "planet": planet,
                "star": star.name,
                "radius_au": a,
                "centre": [float(c) for c in positions.get(star.name, (0.0, 0.0, 0.0))],
                "normal": [float(c) for c in star_normal(system, star.name)],
                "color": colour,
            })
    return specs


def attach(fig, system: StarSystem, t_jd: float) -> None:
    """Put the rings and one optional set per planet on the figure's layout meta."""
    specs = orbit_specs(system, t_jd)
    if not specs:
        return
    meta = dict(fig.layout.meta) if isinstance(fig.layout.meta, dict) else {}
    meta[META_KEY] = specs
    sets = list(meta.get("optional_sets") or [])
    n_stars = len({s["star"] for s in specs})
    for planet, a, _ in reference_planets():
        sets.append({
            "key": set_key(planet), "label": f"{planet} reference orbit", "default": False, "menu": "features",
            "count": n_stars,
            "title": f"{planet}'s orbit ({_au(a)}) drawn round "
                     + ("every star of the system" if n_stars > 1 else "the star")
                     + ", to show the system's size against the Solar System",
        })
    meta["optional_sets"] = sets
    fig.update_layout(meta=meta)


def scene_lines(meta: Optional[dict]) -> list[dict]:
    """The rings as three.js scene lines (`three_viewer.figure_to_scene`)."""
    out = []
    for s in (meta or {}).get(META_KEY) or ():
        group = f"{s['planet']}'s orbit"
        out.append({
            "name": s["name"],
            "color": s["color"],
            "width": 1.0,
            "dash": "dash",
            "opacity": 0.8,
            "pts": ring_points(s),
            "label": "",
            "legend": False,
            # One legend row per planet, under its set's heading, toggling its ring round every star.
            "group": group,
            "groupTitle": f"{group} ({_au(s['radius_au'])})",
            # Hidden with its star, moved with it, shown only while its set is on; `reach` lets the
            # viewer zoom out far enough to see it (Neptune's 30 AU round TRAPPIST-1's 0.06 AU).
            "owner": s["star"],
            "follows": s["star"],
            "optional": set_key(s["planet"]),
            "reach": s["radius_au"] + max(abs(c) for c in s["centre"]),
        })
    return out
