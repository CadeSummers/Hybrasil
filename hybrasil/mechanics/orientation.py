# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The plane a system's bodies actually orbit in.

A solvent band is a ring around the star, and until now it was always drawn
flat on the reference plane (z = 0).  That is right for the Solar System, whose
reference plane *is* the ecliptic, and wrong everywhere the catalog's elements
are quoted against the sky instead: TRAPPIST-1's planets are inclined 89.8 deg,
so a band at z = 0 stood perpendicular to the planets it was drawn for.

The plane is derived from the bodies themselves rather than stored, so it is
right for any system by construction:

  normal = sum over the host's children of  L_i * n_i,   normalised

where `n_i` is the unit normal of body i's orbit and `L_i` is proportional to
its orbital angular momentum, `m * sqrt(a)`.  That makes this the system's
invariable plane, near enough: Jupiter sets the Solar System's (1.5 deg from
the ecliptic, as it should be).

Three rules keep it honest:

1. **A companion star is not part of the host's planetary plane.**  The weights
   are angular momentum, so a companion star is the whole answer wherever there
   is one: Alpha Centauri A used to come back 79.2 deg, which is Alpha Centauri
   B's orbit and not an inclination any planet of A's has.  A band is a
   statement about one star's planetary system, so stellar children sit out.
2. **Hypothetical bodies do not define the plane.**  Planet Nine's 30 deg
   orbit, Proxima's hypothetical 8,700 AU orbit and the disputed Alpha Cen Ab
   are all placeholders or unconfirmed, and none should tilt a band.  A system
   whose bodies are *all* unconfirmed falls back to using them, since that is
   all there is -- which is what catalog systems of candidate planets do.
3. **A body with no recorded mass contributes no known angular momentum**, so
   it sits the average out.  That is not a dodge: Pluto and Eris carry no mass
   in the built-in table, and including them at equal weight tilted the Solar
   System's plane to 6.5 deg on the strength of two bodies that between them
   hold a millionth of Jupiter's angular momentum.  Only when *no* body has a
   mass -- a catalog system of bare candidates -- does the average fall back to
   equal weights.

That average is for a star with planets.  A star with none takes its binary
partner's orbit instead (`band_plane`, `partner_plane`), so a band in Castor
lies in its pair's plane rather than flat on the reference plane.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

from ..models.body import OrbitalBody

# The reference plane's own normal: what everything used before, and still the
# answer for a co-planar system.
Z_AXIS: tuple[float, float, float] = (0.0, 0.0, 1.0)

# Below this the plane is the reference plane for drawing purposes, and the
# description says nothing about a tilt.
NEGLIGIBLE_TILT_DEG = 0.5


def orbital_normal(inclination_deg: float,
                   node_deg: float) -> tuple[float, float, float]:
    """Unit normal of an orbit, in the same frame `kepler.py` rotates into.

    Derived from that rotation, not assumed: with the orbital-plane basis
    vectors P and Q that `rotate_to_reference_frame` applies, P x Q is
    (sin O sin i, -cos O sin i, cos i).  A retrograde orbit (i > 90 deg) points
    its normal below the plane, which is correct and harmless -- a ring drawn
    from it is the same ring.
    """
    i = math.radians(inclination_deg)
    node = math.radians(node_deg)
    return (math.sin(node) * math.sin(i),
            -math.cos(node) * math.sin(i),
            math.cos(i))


def _normalise(v: Sequence[float],
               scale: float = 1.0) -> Optional[tuple[float, float, float]]:
    """Unit vector, or None if `v` is nothing but rounding error.

    `scale` is what the length is judged against, and it matters: a weighted
    sum of orbital normals carries the weights, so two orbits that cancel leave
    a residue the size of the masses times floating-point epsilon -- 1e8 for a
    pair of Jupiters, which no absolute threshold can call zero.
    """
    norm = math.sqrt(sum(c * c for c in v))
    if norm < 1e-9 * max(scale, 1e-300):
        return None
    return (v[0] / norm, v[1] / norm, v[2] / norm)


def reversed_orbit(body: OrbitalBody) -> bool:
    """Whether the body is drawn going round the wrong way on purpose: retrograde against a
    companion's orbit or its siblings' (the sheet's Orbit Direction column).  Retrograde against
    the star's spin is drawn by tilting the star's axis instead, so its orbit is not reversed."""
    d = (getattr(body, "orbit_direction", None) or "").lower()
    return d.startswith("retrograde") and "stellar spin" not in d


def mean_orbital_plane(bodies: Iterable[OrbitalBody],
                       host: Optional[str] = None,
                       include_companions: bool = False) -> tuple[float, float, float]:
    """The normal of the plane the host's children orbit in.

    Falls back to `Z_AXIS` when nothing orbits the host, or when the children's
    normals cancel out -- two bodies orbiting in opposite directions have no
    shared plane to speak of, and the reference plane is the honest answer.

    **A companion star is not part of the host's planetary plane.**  The weights
    are `m * sqrt(a)`, so a companion outweighs any planet by three or four
    orders of magnitude and simply *is* the answer: Alpha Centauri A came back
    79.2 deg, which is Alpha Centauri B's orbit rather than an inclination any
    planet of A's has.  A band drawn there would be a statement about the binary
    and not about the system it rings, so stellar children sit out by default.
    `include_companions=True` asks for the old behaviour -- the plane of
    everything orbiting the host, binary included -- which is the right question
    for the binary itself and the wrong one for a band.

    Excluding companions happens *before* the confirmed-bodies rule, so a host
    whose only confirmed child is a companion star falls back to its own
    unconfirmed planets rather than to the binary.
    """
    # A barycentre is a pair of stars, so it sits out with the companions.
    children = [b for b in bodies
                if b.elements is not None and (host is None or b.parent == host)
                and (include_companions or b.body_type not in ("star", "barycentre"))]
    if not children:
        return Z_AXIS

    confirmed = [b for b in children if b.status == "confirmed"]
    chosen = confirmed or children

    massive = [b for b in chosen if b.mass_kg]
    if massive:
        chosen = massive
        weights = [b.mass_kg * math.sqrt(b.elements.semi_major_axis)
                   for b in chosen]
    else:
        weights = [1.0] * len(chosen)

    total = [0.0, 0.0, 0.0]
    for body, weight in zip(chosen, weights):
        n = orbital_normal(body.elements.inclination,
                           body.elements.longitude_of_ascending_node)
        # A planet drawn retrograde against its companion or siblings (nu Oct A b) counts its
        # plane, not its sense: otherwise a lone one turns the band's normal, and with it the
        # camera, upside down, and seen from below a retrograde orbit looks prograde.
        if reversed_orbit(body):
            n = (-n[0], -n[1], -n[2])
        for axis in range(3):
            total[axis] += weight * n[axis]
    return _normalise(total, sum(abs(w) for w in weights)) or Z_AXIS


def partner_plane(bodies: Iterable[OrbitalBody],
                  host: str) -> Optional[tuple[float, float, float]]:
    """The normal of the host's tightest stellar orbit, or None if it has none.

    A star's stellar links are its own orbit, where its parent is a star or a
    pair's barycentre, and the orbits of any stars or barycentres hung off it.
    The tightest is its partner: in a hierarchy the inner pair sets the plane,
    not the wide orbit the pair makes about the next one out.  A confirmed link
    beats a hypothetical one, as planets do in `mean_orbital_plane`.
    """
    bodies = list(bodies)
    by_name = {b.name: b for b in bodies}
    me = by_name.get(host)
    links = [b for b in bodies
             if b.parent == host and b.elements is not None
             and b.body_type in ("star", "barycentre")]
    if (me is not None and me.elements is not None
            and getattr(by_name.get(me.parent), "body_type", None)
            in ("star", "barycentre")):
        links.append(me)
    if not links:
        return None
    confirmed = [b for b in links if b.status == "confirmed"]
    tightest = min(confirmed or links, key=lambda b: b.elements.semi_major_axis)
    return orbital_normal(tightest.elements.inclination,
                          tightest.elements.longitude_of_ascending_node)


def band_plane(bodies: Iterable[OrbitalBody],
               host: Optional[str]) -> tuple[float, float, float]:
    """The plane one star's solvent bands lie in.

    Its planets' plane wherever it has planets, hypothetical ones included: a
    band is a statement about where a planet could hold a liquid, so a
    candidate planet says more about where to draw it than a star does.  A
    star with no planets of its own takes its binary partner's orbit
    (`partner_plane`) -- Castor's six stars have nothing but each other, and
    were drawn flat on the reference plane whatever their pairs' inclinations.
    A single star with no planets keeps the reference plane.  No host means
    every body, as in `mean_orbital_plane`.
    """
    bodies = list(bodies)
    if host is None:
        return mean_orbital_plane(bodies)
    if any(b.parent == host and b.elements is not None
           and b.body_type not in ("star", "barycentre") for b in bodies):
        return mean_orbital_plane(bodies, host)
    return partner_plane(bodies, host) or Z_AXIS


def plane_tilt_deg(normal: Sequence[float]) -> float:
    """Angle between a plane and the reference plane, 0-90 degrees.

    Folded at 90 deg: a retrograde plane inclined 107.6 deg is tilted 72.4 deg
    away from the reference plane, and that is what a reader seeing the ring
    would measure.
    """
    unit = _normalise(normal)
    if unit is None:
        return 0.0
    return math.degrees(math.acos(min(1.0, abs(unit[2]))))


# ── Sky frames ───────────────────────────────────────────────────────────────
# Where a system's angles come from astrometry or transits, they are quoted
# against the plane of the sky rather than the ecliptic: inclination is measured
# from that plane and the ascending node counterclockwise from North.  Such a
# system's reference plane therefore *is* the sky plane, with x along North,
# y along East, and z = North x East, which points back along the line of sight
# toward Earth.
#
# That matters for anything drawn as a direction rather than an orbit.  An
# ecliptic vector for "where the Sun is" or "where the galactic centre is" is
# simply in the wrong frame there, and points somewhere the system's own
# geometry does not agree with.

# Sagittarius A*: RA 17h45m40.04s, Dec -29d00'28.1" (J2000), ~26,670 ly away.
GALACTIC_CENTRE_RA_DEG = 266.41683
GALACTIC_CENTRE_DEC_DEG = -29.00781
GALACTIC_CENTRE_DISTANCE_LY = 26670.0

# In a sky frame the line of sight is the z axis by construction, so this is
# where the Sun is from any star quoted that way.
TOWARD_EARTH: tuple[float, float, float] = (0.0, 0.0, 1.0)


def galactic_unit(l_deg: float, b_deg: float) -> tuple[float, float, float]:
    """Unit vector toward galactic (l, b): x at the galactic centre, y along
    the direction of rotation (l = 90 deg), z at the north galactic pole."""
    l, b = math.radians(l_deg), math.radians(b_deg)
    return (math.cos(b) * math.cos(l), math.cos(b) * math.sin(l), math.sin(b))


def equatorial_unit(ra_deg: float, dec_deg: float) -> tuple[float, float, float]:
    """Unit vector toward (RA, Dec) in equatorial Cartesian coordinates."""
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    return (math.cos(dec) * math.cos(ra),
            math.cos(dec) * math.sin(ra),
            math.sin(dec))


def sky_frame_basis(ra_deg: float, dec_deg: float) -> tuple[
        tuple[float, float, float], tuple[float, float, float],
        tuple[float, float, float]]:
    """The (North, East, toward-Earth) basis on the sky at (RA, Dec).

    North and East are the on-sky tangent directions, and the third vector is
    their cross product: for an observer looking out along the line of sight,
    East is counterclockwise from North, so North x East points back at the
    observer.  That is the handedness the astrometric convention implies, and
    it is what makes the line of sight the +z axis of a sky frame.
    """
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    north = (-math.sin(dec) * math.cos(ra),
             -math.sin(dec) * math.sin(ra),
             math.cos(dec))
    east = (-math.sin(ra), math.cos(ra), 0.0)
    toward_earth = (north[1] * east[2] - north[2] * east[1],
                    north[2] * east[0] - north[0] * east[2],
                    north[0] * east[1] - north[1] * east[0])
    return north, east, toward_earth


def direction_in_sky_frame(ra_deg: float, dec_deg: float, distance_ly: float,
                           target_ra_deg: float, target_dec_deg: float,
                           target_distance_ly: float) -> tuple[float, float, float]:
    """Where a distant target lies, in the sky frame of a star at (RA, Dec).

    Both positions are taken from the Sun, and the offset between the Sun and
    the star is subtracted -- which matters not at all for the galactic centre
    at 26,670 ly and a star at 40, but costs nothing and keeps the function
    honest for a nearer target.
    """
    star = equatorial_unit(ra_deg, dec_deg)
    target = equatorial_unit(target_ra_deg, target_dec_deg)
    offset = [target[a] * target_distance_ly - star[a] * distance_ly
              for a in range(3)]
    unit = _normalise(offset) or target
    return tuple(sum(unit[a] * axis[a] for a in range(3))
                 for axis in sky_frame_basis(ra_deg, dec_deg))


def galactic_centre_in_sky_frame(ra_deg: float, dec_deg: float,
                                 distance_ly: float) -> tuple[float, float, float]:
    """The galactic centre's direction in the sky frame of a star."""
    return direction_in_sky_frame(ra_deg, dec_deg, distance_ly,
                                  GALACTIC_CENTRE_RA_DEG,
                                  GALACTIC_CENTRE_DEC_DEG,
                                  GALACTIC_CENTRE_DISTANCE_LY)


# ── The whole sky, rotated into a frame ─────────────────────────────────────
# The background sky is an all-sky map in galactic coordinates: x toward the
# galactic centre (l = 0, b = 0), y toward l = 90 deg, z toward the north
# galactic pole.  Turning it into a system's frame takes the full rotation,
# not just the one direction the arrow needs, or the sky could spin about the
# arrow.  Distances do not enter: from any star within 100 ly the Milky Way
# sits where it does from here to within 0.2 deg.

# ICRS equatorial -> galactic (Hipparcos, ESA 1997, vol. 1 sec. 1.5.3; the
# matrix astropy uses).  Each row is a galactic axis in equatorial coordinates.
EQUATORIAL_TO_GALACTIC: tuple[tuple[float, float, float], ...] = (
    (-0.0548755604162154, -0.8734370902348850, -0.4838350155487132),
    (+0.4941094278755837, -0.4448296299600112, +0.7469822444972189),
    (-0.8676661490190047, -0.1980763734312015, +0.4559837761750669),
)

# Obliquity of the ecliptic at J2000 (IAU 2006), for the ecliptic frame.
OBLIQUITY_J2000_DEG = 23.4392911


def ecliptic_basis() -> tuple[tuple[float, float, float], ...]:
    """The ecliptic J2000 axes in equatorial coordinates, one per row."""
    e = math.radians(OBLIQUITY_J2000_DEG)
    return ((1.0, 0.0, 0.0),
            (0.0, math.cos(e), math.sin(e)),
            (0.0, -math.sin(e), math.cos(e)))


def toward_sun_in_ecliptic(ra_deg: float, dec_deg: float) -> tuple[float, float, float]:
    """Where the Sun is from a star at (RA, Dec), in the ecliptic frame.

    For a system with no frame of its own -- a catalog system, drawn flat with
    no measured inclination -- which is drawn in the ecliptic like the Solar
    System.  The Sun lies straight back along the star's line of sight, so no
    distance enters.  The disc's tilt against this arrow is not known; the
    arrow's direction against the galactic-centre arrow and the sky is.
    """
    star = equatorial_unit(ra_deg, dec_deg)
    return tuple(-sum(axis[k] * star[k] for k in range(3))
                 for axis in ecliptic_basis())


def galactic_to_frame(sky_frame_radec: Optional[Sequence[float]] = None
                      ) -> tuple[tuple[float, float, float], ...]:
    """The rotation taking a galactic direction into a system's own frame.

    `sky_frame_radec` is the (RA, Dec) of a star whose system is quoted
    against the plane of the sky; None is the ecliptic frame, which is the
    Solar System's and the one every system with no frame of its own is
    drawn in.  Row i is frame axis i in galactic coordinates, so
    ``frame = M @ galactic``.  It turns the galactic centre, (1, 0, 0), into
    the same direction the galactic-centre arrow points along.
    """
    basis = (sky_frame_basis(*sky_frame_radec[:2]) if sky_frame_radec
             else ecliptic_basis())
    g = EQUATORIAL_TO_GALACTIC
    # frame axis in galactic = G @ (frame axis in equatorial)
    return tuple(tuple(sum(g[r][k] * axis[k] for k in range(3)) for r in range(3))
                 for axis in basis)


def galactic_centre_distance_ly(ra_deg: float, dec_deg: float,
                                distance_ly: float) -> float:
    """How far a star at (RA, Dec, distance) is from the galactic centre."""
    star = equatorial_unit(ra_deg, dec_deg)
    centre = equatorial_unit(GALACTIC_CENTRE_RA_DEG, GALACTIC_CENTRE_DEC_DEG)
    return math.sqrt(sum((centre[a] * GALACTIC_CENTRE_DISTANCE_LY
                          - star[a] * distance_ly) ** 2 for a in range(3)))


def plane_basis(normal: Sequence[float]) -> tuple[tuple[float, float, float],
                                                  tuple[float, float, float]]:
    """Two perpendicular unit vectors spanning the plane with this normal.

    `u` is the ascending node direction where there is one, so the ring's
    vertices start where the plane crosses the reference plane and a tilted
    ring is reproducible rather than arbitrarily rolled.  For an untilted plane
    there is no node, and `u` is the x axis -- which is what a flat belt has
    always been drawn from.
    """
    unit = _normalise(normal) or Z_AXIS
    node = _normalise((-unit[1], unit[0], 0.0))       # n x z, the line of nodes
    u = node or (1.0, 0.0, 0.0)
    v = (unit[1] * u[2] - unit[2] * u[1],   # n x u, completing the basis
         unit[2] * u[0] - unit[0] * u[2],
         unit[0] * u[1] - unit[1] * u[0])
    return u, _normalise(v) or (0.0, 1.0, 0.0)


# ── Looking at a plane ───────────────────────────────────────────────────────
# A band is a disc, and a disc is only a disc from a camera that is not in its
# plane.  The reference frame is the plane of the sky for every system whose
# angles come from transits or astrometry, so a transiting system's band stands
# perpendicular to z by construction and a camera pointed down z sees a line.
# TRAPPIST-1 at 89.76 deg is the worked case.
#
# The fix belongs here rather than in the geometry: the band is in the right
# place, and it is the view that has to follow it.

def rotate_from_z(normal: Sequence[float],
                  v: Sequence[float]) -> tuple[float, float, float]:
    """Apply the rotation that carries the z axis onto `normal`, to `v`.

    Rodrigues about `z x normal`.  Used to re-express a camera that was written
    against the reference plane in the plane a band actually lies in, so the
    view keeps its angle *relative to the band* whatever the system's
    inclination: the Solar System's 1.58 deg barely moves the camera, and
    TRAPPIST-1's 89.76 deg turns an edge-on line into a disc.
    """
    unit = _normalise(normal) or Z_AXIS
    cos_t = max(-1.0, min(1.0, unit[2]))
    axis = _normalise((-unit[1], unit[0], 0.0))   # z x n
    if axis is None:
        # Parallel to z (or antiparallel): identity, or a flip about x.
        return (v[0], v[1], v[2]) if cos_t >= 0 else (v[0], -v[1], -v[2])
    sin_t = math.sqrt(max(0.0, 1.0 - cos_t * cos_t))
    cross = (axis[1] * v[2] - axis[2] * v[1],
             axis[2] * v[0] - axis[0] * v[2],
             axis[0] * v[1] - axis[1] * v[0])
    dot = sum(axis[a] * v[a] for a in range(3))
    return tuple(v[a] * cos_t + cross[a] * sin_t + axis[a] * dot * (1.0 - cos_t)
                 for a in range(3))


def camera_for_plane(normal: Sequence[float],
                     eye: Sequence[float] = (1.25, 1.25, 1.25)
                     ) -> tuple[tuple[float, float, float],
                                tuple[float, float, float]]:
    """`(eye, up)` for an oblique view of the plane with this normal.

    `eye` is the camera Plotly would use against the reference plane; it comes
    back rotated into this plane, so the view is the same three-quarter angle
    measured against the band rather than against world z.  `up` is the normal
    itself, which is what keeps the ring level in frame.
    """
    return rotate_from_z(normal, eye), (_normalise(normal) or Z_AXIS)


def face_on_camera(normal: Sequence[float], distance: float
                   ) -> tuple[tuple[float, float, float],
                              tuple[float, float, float]]:
    """`(eye, up)` looking straight down `normal` from `distance`.

    What the Orient button wants: the band square to the viewer.  `up` is the
    line of nodes, which is perpendicular to the normal by construction -- an
    `up` parallel to the view direction is degenerate and Plotly renders it as
    an empty scene.
    """
    unit = _normalise(normal) or Z_AXIS
    return (tuple(c * distance for c in unit), plane_basis(unit)[0])
