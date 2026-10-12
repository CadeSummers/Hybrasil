# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Photosynthesis limits: one ring per organism around every luminous star.

A ring sits where the star's PAR photon flux falls to an organism's growth
limit (`mechanics.photosynthesis`, `data.photosynthesis_limits`).  The rings
are a three.js feature, offered in its Even more features menu and off by
default, so they travel in ``layout.meta`` rather than as Plotly traces: the
Plotly viewer never sees them, and no trace index anywhere moves.  CLAUDE.md's
band rule is why that matters -- a frame writes to traces by index.

Each ring lies in the plane of its own star's planets, the plane its solvent
bands use, and is centred on the star where it stands at the figure's first
moment; the three.js viewer moves it with the star after that.
"""

from __future__ import annotations

import math
from typing import Optional

from ..data.photosynthesis_limits import drawn_limits
from ..mechanics.orientation import band_plane, plane_basis
from ..mechanics.photosynthesis import par_photon_factor, photosynthesis_distance_au
from ..mechanics.time_series import system_positions_at
from ..models.system import StarSystem

META_KEY = "photosynthesis_rings"
SET_KEY = "photosynthesis"
SET_LABEL = "Photosynthesis limits"
RING_POINTS = 360

# Outward from the sun-lovers to the extremophiles: warm to cold to violet.
_PALETTE = ("#ffd23f", "#b5e34a", "#4fc96b", "#2fae8f", "#2a9bb5",
            "#3a7fd0", "#5b63d6", "#7b4fd0", "#9b3fc4", "#b836a8", "#c8327f")


def _colour(i: int, n: int) -> str:
    if n <= 1:
        return _PALETTE[0]
    return _PALETTE[round(i * (len(_PALETTE) - 1) / (n - 1))]


def star_normal(system: StarSystem, star: str) -> tuple[float, float, float]:
    """The plane this star's solvent bands lie in, else `band_plane`'s answer."""
    for z in system.belt_zones:
        if z.is_solvent_band and z.centre_body == star:
            return tuple(z.normal)
    return band_plane(system.bodies, star)


def ring_specs(system: StarSystem, t_jd: float) -> list[dict]:
    """Every ring the figure carries: star, organism, radius, centre, plane, colour."""
    stars = [b for b in system.bodies
             if b.body_type == "star" and b.luminosity_sun and b.luminosity_sun > 0]
    limits = drawn_limits()
    if not stars or not limits:
        return []
    positions = system_positions_at(system, t_jd)
    label = len(stars) > 1
    specs = []
    for star in stars:
        centre = positions.get(star.name, (0.0, 0.0, 0.0))
        normal = star_normal(system, star.name)
        k = par_photon_factor(star.teff_k)
        for i, (org, f) in enumerate(limits):
            r = photosynthesis_distance_au(star.luminosity_sun, f, star.teff_k)
            if r is None:
                continue
            specs.append({
                "name": f"{org.name} growth limit" + (f" ({star.name})" if label else ""),
                "organism": org.name,
                "star": star.name,
                "radius_au": r,
                "par_fraction": f,
                "par_factor": k,
                "centre": [float(c) for c in centre],
                "normal": [float(c) for c in normal],
                "color": _colour(i, len(limits)),
            })
    return specs


def attach(fig, system: StarSystem, t_jd: float) -> None:
    """Put the rings and their optional set on the figure's layout meta."""
    specs = ring_specs(system, t_jd)
    if not specs:
        return
    meta = dict(fig.layout.meta) if isinstance(fig.layout.meta, dict) else {}
    meta[META_KEY] = specs
    sets = list(meta.get("optional_sets") or [])
    sets.append({
        "key": SET_KEY, "label": SET_LABEL, "default": False, "menu": "features",
        "count": len({s["organism"] for s in specs}),
        "title": "Where each star's light falls to the least an Earth photosynthesiser needs to grow, "
                 "from sun-loving plants out to light-fed extremophiles (PAR photons, corrected for "
                 "the star's temperature)",
    })
    meta["optional_sets"] = sets
    fig.update_layout(meta=meta)


def ring_points(spec: dict, n: int = RING_POINTS) -> list[float]:
    """The ring as a closed loop of x, y, z triples, flattened."""
    u, v = plane_basis(spec["normal"])
    cx, cy, cz = spec["centre"]
    r = spec["radius_au"]
    out: list[float] = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        c, s = math.cos(a) * r, math.sin(a) * r
        out += [cx + c * u[0] + s * v[0], cy + c * u[1] + s * v[1], cz + c * u[2] + s * v[2]]
    return out


def scene_lines(meta: Optional[dict]) -> list[dict]:
    """The rings as three.js scene lines (`three_viewer.figure_to_scene`)."""
    out = []
    for s in (meta or {}).get(META_KEY) or ():
        out.append({
            "name": s["name"],
            "color": s["color"],
            "width": 1.0,
            "dash": "solid",
            "opacity": 0.85,
            "pts": ring_points(s),
            "label": "",
            "legend": False,
            # One legend row per organism, under the set's heading, toggling
            # that organism's ring around every star.
            "group": s["organism"],
            "groupTitle": s["organism"],
            # Hidden with its star, moved with it, and shown only while the
            # set is on.
            "owner": s["star"],
            "follows": s["star"],
            "optional": SET_KEY,
        })
    return out
