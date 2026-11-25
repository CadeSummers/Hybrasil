# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Starlight from more than one star, and the band outline it gives.

Around a lone star a solvent band is a circular annulus, because the flux falls
as 1/d^2 from one point.  With a companion close enough to matter the fluxes
add,

    S(p) = sum_i  w_i / |p - p_i|^2,        w_i = colour_i * L_i

and the equilibrium temperature there is

    T(p) = T_EQ_1AU_K * ((1 - A) * S(p)) ** 0.25  (+ the greenhouse offset)

which for one star is exactly what `solvent_bands.equilibrium_distance_au`
inverts.  The liquid region is then no longer a ring of constant radius: it is
wherever S lies between the flux at the band's hot edge and the flux at its
cold edge.

Everything here works in flux rather than temperature.  A band's own closed-form
radii already hold the albedo, the greenhouse offset and the solvent's limits:
the hot-edge flux is `w_own / inner^2` and the cold-edge flux `w_own / outer^2`.
So the solver takes those two radii and never sees a temperature, and a change
to the band equation cannot leave this file behind.

A source is `(x, y, z, w)`: a position in AU and a colour-weighted luminosity
in suns.  `band_kit.js` holds the same solver for the viewers
(`_liquidInterval`, `_bandOutline`); `tests/test_band_sliders.py` holds the
two together.
"""
from __future__ import annotations

import math
from typing import Sequence

from hybrasil.mechanics.orientation import plane_basis
from hybrasil.mechanics.units import T_EQ_1AU_K

Source = tuple[float, float, float, float]

# A companion is left out of a band's solve when, everywhere inside the band's
# own outer radius, it adds less than this fraction of the cold-edge flux
# (shared between however many companions there are).  Flux goes as 1/r^2, so
# 1e-3 in flux is 0.05 % in radius: under a pixel at any zoom.  With every
# companion left out the band is its own circle, exactly as for a lone star.
NEGLIGIBLE_FLUX = 1e-3

# The march along a ray steps by this ratio, and each crossing it brackets is
# then bisected a fixed number of times -- fixed, so that the JavaScript copy
# lands on the same number rather than on its own idea of converged.  28
# halvings of a 5 % step put an edge within 2e-10 of its radius.
MARCH_RATIO = 1.05
BISECTIONS = 28

# Past the last star by this much more than the distance at which all the
# light together would fall to the cold edge, the ray is certainly cold.
_REACH_MARGIN = 1.01

# A ray through a star's own position: the flux is as good as infinite.
_MIN_D2 = 1e-30


def combined_flux(point: Sequence[float], sources: Sequence[Source]) -> float:
    """Summed flux at `point`, in units of the Sun's at 1 AU (times colour)."""
    total = 0.0
    for sx, sy, sz, w in sources:
        dx, dy, dz = point[0] - sx, point[1] - sy, point[2] - sz
        d2 = dx * dx + dy * dy + dz * dz
        total += w / (d2 if d2 > _MIN_D2 else _MIN_D2)
    return total


def equilibrium_temperature_k(point: Sequence[float],
                              sources: Sequence[Source],
                              albedo: float = 0.3,
                              greenhouse_k: float = 0.0) -> float:
    """Surface temperature at `point` under every source's light at once.

    With albedo 0.3 and no greenhouse the leading constant is 254.6 K, Earth's
    blackbody temperature.
    """
    flux = combined_flux(point, sources)
    return T_EQ_1AU_K * ((1.0 - albedo) * flux) ** 0.25 + greenhouse_k


def relevant_sources(own: int, sources: Sequence[Source],
                     outer: float) -> list[Source]:
    """The band's own star, then each companion bright and near enough to bend it.

    Positions come back relative to the own star, which is first.  One entry
    means the band is a plain circle.
    """
    ox, oy, oz, w0 = sources[own]
    others = sum(1 for i, s in enumerate(sources) if i != own and s[3] > 0)
    kept: list[Source] = [(0.0, 0.0, 0.0, w0)]
    if not others or outer <= 0 or w0 <= 0:
        return kept
    limit = NEGLIGIBLE_FLUX * (w0 / (outer * outer)) / others
    for i, (sx, sy, sz, w) in enumerate(sources):
        if i == own or w <= 0:
            continue
        rx, ry, rz = sx - ox, sy - oy, sz - oz
        reach = math.sqrt(rx * rx + ry * ry + rz * rz) - outer
        if reach > 0 and w / (reach * reach) < limit:
            continue
        kept.append((rx, ry, rz, w))
    return kept


def _ray_flux(kept: Sequence[Source], d: Sequence[float], r: float) -> float:
    return combined_flux((r * d[0], r * d[1], r * d[2]), kept)


def _crossing(kept: Sequence[Source], d: Sequence[float],
              lo: float, hi: float, level: float, lo_above: bool) -> float:
    """Where the flux along the ray passes `level` between `lo` and `hi`."""
    for _ in range(BISECTIONS):
        mid = 0.5 * (lo + hi)
        if (_ray_flux(kept, d, mid) >= level) == lo_above:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def liquid_interval(kept: Sequence[Source], direction: Sequence[float],
                    inner: float, outer: float) -> tuple[float, float]:
    """The first stretch of a ray from the star on which the solvent is liquid.

    `kept` is `relevant_sources()`: the star at the origin first.  `inner` and
    `outer` are that star's own closed-form radii, which fix the two flux
    levels.  The stretch starts where the summed flux first falls to the hot
    level and ends where it either falls to the cold one or -- running into a
    companion's own too-hot zone -- climbs back over the hot one.

    The march also stops at each companion's closest approach to the ray, so a
    hot zone narrower than a step is not stepped over.
    """
    if len(kept) < 2:
        return inner, outer
    w0 = kept[0][3]
    s_hot = w0 / (inner * inner)
    s_cold = w0 / (outer * outer)

    total, far = 0.0, 0.0
    for sx, sy, sz, w in kept:
        total += w
        far = max(far, math.sqrt(sx * sx + sy * sy + sz * sz))
    r_max = (far + math.sqrt(total / s_cold)) * _REACH_MARGIN

    marks = sorted(t for t in (s[0] * direction[0] + s[1] * direction[1]
                               + s[2] * direction[2] for s in kept[1:])
                   if inner < t < r_max)
    marks.append(r_max)

    m = 0
    prev = inner
    r_in = None
    while True:
        nxt = prev * MARCH_RATIO
        if marks[m] <= nxt:
            nxt = marks[m]
            m += 1
        flux = _ray_flux(kept, direction, nxt)
        if r_in is None:
            if flux < s_hot:
                r_in = _crossing(kept, direction, prev, nxt, s_hot, True)
                if flux < s_cold:
                    return r_in, _crossing(kept, direction, r_in, nxt, s_cold, True)
        elif flux < s_cold:
            return r_in, _crossing(kept, direction, prev, nxt, s_cold, True)
        elif flux > s_hot:
            return r_in, _crossing(kept, direction, prev, nxt, s_hot, False)
        if m >= len(marks):
            # Unreachable: the flux at r_max is under the cold level by
            # construction.  Fall back to the star's own ring over looping.
            return (inner, outer) if r_in is None else (r_in, max(nxt, r_in))
        prev = nxt


def band_outline(own: int, sources: Sequence[Source],
                 normal: Sequence[float], inner: float, outer: float,
                 n_pts: int) -> tuple[list[float], list[float]]:
    """A band's inner and outer radius at each of `n_pts` angles round its star.

    Sampled on the star's own plane (`normal`), at the angles a ring's vertices
    sit at, measured from `plane_basis(normal)`'s `u`.  Every star's light is
    counted at its true 3-D distance, so a companion off the plane still warms
    it -- and two stars whose planes differ each show the other's effect in
    their own.
    """
    kept = relevant_sources(own, sources, outer)
    if len(kept) < 2:
        return [inner] * n_pts, [outer] * n_pts
    u, v = plane_basis(normal)
    r_in, r_out = [], []
    for t in range(n_pts):
        a = 2.0 * math.pi * t / n_pts
        ca, sa = math.cos(a), math.sin(a)
        d = (ca * u[0] + sa * v[0], ca * u[1] + sa * v[1], ca * u[2] + sa * v[2])
        lo, hi = liquid_interval(kept, d, inner, outer)
        r_in.append(lo)
        r_out.append(hi)
    return r_in, r_out
