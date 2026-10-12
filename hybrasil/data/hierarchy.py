# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A hierarchical multiple star, as the "Planetless 4+ Stars" tab writes it, turned into bodies.

The tab describes a system as a tree of pairs.  Castor is ((Aa,Ab),(Ba,Bb)),((Ca,Cb),Cc): Ab orbits Aa, but B --
the pair Ba+Bb -- orbits A, the pair Aa+Ab, so B's orbit is between two *barycentres*.  Every row is a node, a
star or a subsystem, and the tab carries what drawing one needs:

- a secondary's row holds its pair's relative orbit, as seen from the primary named in 'Separation from';
- a subsystem's row holds where its barycentre is: 'Barycentre offset (AU)' from the member in 'Barycentre from',
  on the line to the other member, i.e. a * M_sec / (M_prim + M_sec).

The mechanics place a body only from a parent body, so a subsystem becomes a massless `barycentre` body, and
every position is reached by a chain of Keplerian orbits from one star fixed at the origin (the host, as the
primary star is in every other system here).  Two pieces of exact two-body geometry do the rest:

- **up the tree**, from a member already placed, the pair's barycentre is the pair's own relative orbit scaled
  to the barycentre offset: same shape, same phase, smaller;
- **down the tree**, from a barycentre already placed, the primary member is the relative orbit scaled to the
  offset and turned through 180 degrees, and the secondary is the full relative orbit from the primary.

A barycentre placed from its own primary member exists only so the next pair up has something to orbit; its
ellipse is a scaled copy of its pair's, so it is drawn without one (`draw_orbit=False`).  So is a subsystem
primary placed from its barycentre.  A subsystem that is a pair's *secondary* is the one whose orbit is worth
drawing: that is the A-B orbit, or C's round AB.

Pure data transformation: no I/O, and nothing here knows which system it is building.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

from ..mechanics.units import M_SUN_KG
from ..models.body import OrbitalBody
from ..models.elements import KeplerianElements


@dataclass(frozen=True)
class NodeRow:
    """One row of the tab, reduced to what a drawing needs.  Names are the tab's 'Star (component)'."""
    name: str
    node_type: str                                  # 'star' or 'subsystem'
    mass_sun: Optional[float] = None
    luminosity_sun: Optional[float] = None
    teff_k: Optional[float] = None
    # the orbit this node's row holds: its own, relative to 'Separation from'
    separation_from: Optional[str] = None
    a_au: Optional[float] = None
    e: Optional[float] = None
    period_d: Optional[float] = None
    inclination_deg: Optional[float] = None
    node_deg: Optional[float] = None
    omega_deg: Optional[float] = None
    periastron_jd: Optional[float] = None
    omega_refers_to: Optional[str] = None           # 'primary (...)' or 'secondary (...)'
    # a subsystem's barycentre
    barycentre_from: Optional[str] = None
    barycentre_offset_au: Optional[float] = None


@dataclass
class Look:
    """How one node is drawn: everything about a body that is not where it is."""
    display_name: Optional[str] = None
    color: Optional[str] = None
    status: str = "confirmed"
    sources: Optional[list] = None
    extra: dict = field(default_factory=dict)       # any other OrbitalBody field


def relative_orbit(row: NodeRow) -> KeplerianElements:
    """The secondary's orbit about the primary, with omega turned to the secondary's if it was quoted for the primary."""
    missing = [k for k in ("a_au", "e", "period_d", "inclination_deg", "node_deg", "omega_deg", "periastron_jd",
                           "omega_refers_to") if getattr(row, k) is None]
    if missing:
        raise ValueError(f"{row.name}: its orbit needs {', '.join(missing)}")
    if row.omega_refers_to.startswith("primary"):
        omega = (row.omega_deg + 180.0) % 360.0
    elif row.omega_refers_to.startswith("secondary"):
        omega = row.omega_deg
    else:
        raise ValueError(f"{row.name}: 'Argument of periastron refers to' is {row.omega_refers_to!r}")
    # Phase: the mean anomaly is 0 at T.  For a circular orbit T is whatever point omega was chosen to mark.
    return KeplerianElements(
        semi_major_axis=row.a_au, eccentricity=row.e, inclination=row.inclination_deg,
        longitude_of_ascending_node=row.node_deg, argument_of_periapsis=omega,
        mean_anomaly_at_epoch=0.0, epoch=row.periastron_jd, period=row.period_d)


def _scaled(el: KeplerianElements, a_au: float, flip: bool) -> KeplerianElements:
    """The same orbit, shrunk to a_au and, if flip, pointing the other way: r -> -r is omega + 180."""
    return replace(el, semi_major_axis=a_au,
                   argument_of_periapsis=(el.argument_of_periapsis + (180.0 if flip else 0.0)) % 360.0)


def hierarchy_bodies(rows: list[NodeRow], origin: str, looks: dict[str, Look] | None = None,
                     name_of=lambda n: n) -> list[OrbitalBody]:
    """Every node as a body, parents before children, with `origin` (a star) fixed at the centre.

    `name_of` maps a row's name to the body's; `looks` (keyed by row name) styles it.
    """
    looks = looks or {}
    by = {r.name: r for r in rows}
    pair_of: dict[str, tuple[str, str]] = {}        # member -> (primary, secondary)
    for r in rows:
        if r.separation_from:
            pair_of[r.name] = pair_of[r.separation_from] = (r.separation_from, r.name)
    parent_of: dict[tuple[str, str], Optional[str]] = {}
    for pair in set(pair_of.values()):
        subs = [r.name for r in rows if r.node_type == "subsystem" and r.barycentre_from == pair[0]]
        if len(subs) > 1:
            raise ValueError(f"{pair}: {subs} all claim this pair")
        parent_of[pair] = subs[0] if subs else None
    # A root pair has no subsystem over it, or one that is in no pair of its own: the barycentre of the whole
    # system, kept so a circumbinary planet has something to orbit (GJ 570 G round GJ 570 AB, 7 Oct 2026).
    roots = [p for p, x in parent_of.items() if x is None or x not in pair_of]
    if len(roots) != 1:
        raise ValueError(f"expected one root pair, found {sorted(roots)}")
    if by[origin].node_type != "star":
        raise ValueError(f"{origin} is not a star")

    out: list[OrbitalBody] = []
    placed: set[str] = set()

    def body(name: str, parent: Optional[str], el: Optional[KeplerianElements], draw: bool = True) -> None:
        r, look = by[name], looks.get(name, Look())
        star = r.node_type == "star"
        out.append(OrbitalBody(
            name=name_of(name), body_type="star" if star else "barycentre",
            elements=el, parent=name_of(parent) if parent else None,
            mass_kg=r.mass_sun * M_SUN_KG if r.mass_sun else None,
            luminosity_sun=r.luminosity_sun if star else None, teff_k=r.teff_k if star else None,
            color=look.color, display_name=look.display_name, sources=look.sources,
            status=look.status, draw_orbit=draw, **look.extra))
        placed.add(name)

    def members(x: str) -> tuple[str, str]:
        return next(p for p, par in parent_of.items() if par == x)

    def down(x: str) -> None:
        """x (a subsystem) is placed; place its two members and everything below them."""
        prim, sec = members(x)
        rel = relative_orbit(by[sec])
        if prim not in placed:
            body(prim, x, _scaled(rel, by[x].barycentre_offset_au, flip=True),
                 draw=by[prim].node_type == "star")
        if sec not in placed:
            body(sec, prim, rel)
        for m in (prim, sec):
            if by[m].node_type == "subsystem":
                down(m)

    body(origin, None, None)
    node = origin
    while True:
        pair = pair_of[node]
        prim, sec = pair
        x = parent_of[pair]
        rel = relative_orbit(by[sec])
        if node == prim:
            if x is not None:
                body(x, prim, _scaled(rel, by[x].barycentre_offset_au, flip=False), draw=False)
            body(sec, prim, rel)
            if by[sec].node_type == "subsystem":
                down(sec)
        else:
            # The origin is a secondary: its primary is the relative orbit reversed.
            body(prim, sec, _scaled(rel, rel.semi_major_axis, flip=True))
            if x is not None:
                body(x, sec, _scaled(rel, rel.semi_major_axis - by[x].barycentre_offset_au, flip=True), draw=False)
            if by[prim].node_type == "subsystem":
                down(prim)
        if x is None or x not in pair_of:
            break
        node = x

    missing = set(by) - placed
    if missing:
        raise ValueError(f"not reachable from {origin}: {sorted(missing)}")
    return out
