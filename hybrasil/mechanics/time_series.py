# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate position arrays over time for entire systems."""

import math
from typing import Sequence, Union

import numpy as np
from ..models.elements import KeplerianElements
from ..models.system import StarSystem
from .kepler import (elements_to_cartesian, eccentric_to_true_anomaly, rotate_to_reference_frame,
                     true_anomaly_to_orbital_plane)


# Points per closed orbit. The drawn line is a polygon, and a body's marker sits
# on the true ellipse, so the gap between them is the polygon's chord error.
# Sampled evenly in eccentric anomaly, an ellipse's worst chord error is a
# circle's, (1 - cos(pi/n)) * a: 9.5e-6 a at 720, under half a pixel at the
# double-click zoom (+/- 1% of a). Sampled in true anomaly, 360 points left
# Eris 0.007 AU and Planet Nine 0.1 AU off their own orbits near aphelion.
ORBIT_POINTS = 720


def generate_orbit_path(
    elements: KeplerianElements,
    n_points: int = ORBIT_POINTS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ellipse sampled evenly in eccentric anomaly (not time), relative to its parent.

    Eccentric anomaly spaces the points evenly enough around an eccentric
    orbit that its aphelion is drawn as finely as its perihelion (see
    ORBIT_POINTS); true anomaly bunches them at perihelion.

    Returns (xs, ys, zs) in AU. The last point equals the first to close the loop.
    For planets this is heliocentric. For moons, add the parent's position to get
    heliocentric coordinates (see generate_moon_orbit_path).
    """
    Es = np.linspace(0.0, 2.0 * math.pi, n_points, endpoint=False)
    xs, ys, zs = [], [], []
    for E in Es:
        nu = eccentric_to_true_anomaly(E, elements.eccentricity)
        x_orb, y_orb = true_anomaly_to_orbital_plane(nu, elements.semi_major_axis, elements.eccentricity)
        x, y, z = rotate_to_reference_frame(
            x_orb, y_orb,
            elements.inclination,
            elements.longitude_of_ascending_node,
            elements.argument_of_periapsis,
        )
        xs.append(x)
        ys.append(y)
        zs.append(z)
    xs.append(xs[0])
    ys.append(ys[0])
    zs.append(zs[0])
    return np.array(xs), np.array(ys), np.array(zs)


# The elements of a body's parent, or of every moving body above it, nearest
# first.  A bare KeplerianElements is a chain of one.
ParentChain = Union[KeplerianElements, Sequence[KeplerianElements]]


def _as_chain(parent: ParentChain) -> list[KeplerianElements]:
    return [parent] if isinstance(parent, KeplerianElements) else list(parent)


def _chain_position(chain: list[KeplerianElements], t: float) -> tuple[float, float, float]:
    """Where the chain puts the body's parent at t: the sum of every link."""
    x = y = z = 0.0
    for el in chain:
        dx, dy, dz = elements_to_cartesian(el, t)
        x += dx; y += dy; z += dz
    return x, y, z


def ancestor_chain(body, bodies_by_name: dict) -> list[KeplerianElements]:
    """The elements of every moving body between this one and the origin, nearest first.

    A planet of a star at the origin has none.  Castor Bb has three: Ba, the B
    barycentre and the A barycentre, with Aa at the origin.  A parent that is
    not in the system ends the chain, as it always has.
    """
    chain: list[KeplerianElements] = []
    seen: set[str] = set()
    name = body.parent
    while name and name not in seen:
        seen.add(name)
        parent = bodies_by_name.get(name)
        if parent is None:
            break
        if parent.elements is not None:
            chain.append(parent.elements)
        name = parent.parent
    return chain


def generate_moon_orbit_path(
    moon_elements: KeplerianElements,
    parent_elements: ParentChain,
    n_points: int = ORBIT_POINTS,
    t_ref: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Heliocentric orbit path for a moon, centered on parent's position at t_ref.

    Samples the moon's orbit evenly in eccentric anomaly (a clean ellipse in the
    parent's frame), then translates by the parent's heliocentric position at
    t_ref (defaults to moon_elements.epoch).  `parent_elements` may be the whole
    chain above the moon (see `ancestor_chain`), so a body several levels down a
    hierarchy -- a star orbiting a pair's barycentre -- is centred where its
    parent really is, not where its parent's own orbit alone would put it.

    Using t_ref=t_start ensures the orbit trace aligns with animated markers,
    which are computed from t_start. Using the old time-sampling approach caused
    the trace to be centered at the parent's J2000 position regardless of when
    the animation starts.
    """
    t = t_ref if t_ref is not None else moon_elements.epoch
    px, py, pz = _chain_position(_as_chain(parent_elements), t)
    xs, ys, zs = generate_orbit_path(moon_elements, n_points)
    return xs + px, ys + py, zs + pz


# Coil sampling. A planet orbiting a companion star traces a helix in the
# primary's frame, so the trace is sampled in *time* rather than true anomaly.
# PTS_PER_LOOP sets the density; the total is clamped so a short-period planet
# over a long window still produces a trace the browser can draw.
COIL_POINTS_PER_LOOP = 16
COIL_MIN_POINTS      = 360
COIL_MAX_POINTS      = 12000


def generate_coil_orbit_path(
    body_elements: KeplerianElements,
    parent_elements: ParentChain,
    t_start: float,
    t_end: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The body's true path in the primary's frame over [t_start, t_end].

    Adds the parent's position at each sample time to the body's own, so the
    result is the helix the body actually traverses while its parent moves.
    Unlike generate_orbit_path this is an open curve: the body never returns
    to where it started.

    Sampling is dense enough to resolve individual loops when there are few,
    and degrades to a tube when there are thousands.  `parent_elements` may be
    the whole chain above the body, as for `generate_moon_orbit_path`.
    """
    chain = _as_chain(parent_elements)
    span = float(t_end) - float(t_start)
    if span <= 0.0:
        raise ValueError("t_end must be later than t_start")

    period = body_elements.period or 0.0
    n_loops = (span / period) if period > 0 else 1.0
    n_points = int(math.ceil(n_loops * COIL_POINTS_PER_LOOP))
    n_points = max(COIL_MIN_POINTS, min(COIL_MAX_POINTS, n_points))

    times = np.linspace(float(t_start), float(t_end), n_points)
    xs = np.empty(n_points)
    ys = np.empty(n_points)
    zs = np.empty(n_points)
    for i, t in enumerate(times):
        px, py, pz = _chain_position(chain, t)
        bx, by, bz = elements_to_cartesian(body_elements, t)
        xs[i], ys[i], zs[i] = px + bx, py + by, pz + bz
    return xs, ys, zs


def is_coil_body(body, bodies_by_name: dict) -> bool:
    """True when the body orbits a star, or a barycentre, that is itself in orbit.

    Such a body has no closed orbit in the primary's frame, so a Keplerian
    ellipse misrepresents it and drifts away from the animated marker. A moon
    of a planet is deliberately excluded: its parent stays a planet, and the
    closed ellipse is what makes the zoomed-in moon view readable.
    """
    if not body.parent:
        return False
    parent = bodies_by_name.get(body.parent)
    return (parent is not None
            and parent.elements is not None
            and parent.body_type in ("star", "barycentre"))


def system_orbit_paths(
    system: StarSystem,
    n_points: int = ORBIT_POINTS,
    t_start: float | None = None,
    t_end: float | None = None,
) -> tuple[dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
           dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]]:
    """Compute trace paths for all bodies in primary-centred coordinates.

    Returns ``(orbit_paths, coil_paths)``. Every body with elements lands in
    exactly one of the two, so trace counts stay predictable.

    Planets get smooth eccentric-anomaly-sampled ellipses.
    Moons get eccentric-anomaly-sampled ellipses centered on parent's position at
    t_start (or parent's epoch if t_start is None).
    Planets of an orbiting star get a time-sampled coil spanning
    [t_start, t_end]; without a window they fall back to an ellipse, and so
    does a body that would not finish one loop inside the window -- an arc of a
    459-year orbit is not a drawing of it, and its closed ellipse is.
    A parent's position counts every moving body above it (`ancestor_chain`).
    Stars at the origin are skipped, and so is a body marked `draw_orbit=False`
    (a bookkeeping barycentre): those land in neither dict.
    """
    bodies_by_name = {b.name: b for b in system.bodies}
    paths: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    coils: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    have_window = (t_start is not None and t_end is not None and t_end > t_start)

    for body in system.bodies:
        if body.elements is None or not body.draw_orbit:
            continue
        chain = ancestor_chain(body, bodies_by_name)
        if chain:
            loops = (have_window and body.elements.period > 0
                     and body.elements.period <= t_end - t_start)
            if loops and is_coil_body(body, bodies_by_name):
                coils[body.name] = generate_coil_orbit_path(
                    body.elements, chain, t_start, t_end
                )
            else:
                paths[body.name] = generate_moon_orbit_path(
                    body.elements, chain, n_points, t_ref=t_start
                )
            continue
        # Planet (or body whose parent is a star / has no elements)
        paths[body.name] = generate_orbit_path(body.elements, n_points)

    return paths, coils


def system_time_series(
    system: StarSystem,
    t_start_jd: float,
    t_end_jd: float,
    n_frames: int = 100,
) -> tuple[np.ndarray, dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]]:
    """Compute heliocentric time series for every body in the system.

    Returns (times_jd, {body_name: (xs, ys, zs)}).
    Stars stay at origin. Moon positions include their parent planet's position.
    Bodies must be ordered so parents appear before their moons (builtin data already is).
    """
    times = np.linspace(t_start_jd, t_end_jd, n_frames)
    result: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    for body in system.bodies:
        if body.elements is None:
            result[body.name] = (
                np.zeros(n_frames),
                np.zeros(n_frames),
                np.zeros(n_frames),
            )
        else:
            xs = np.empty(n_frames)
            ys = np.empty(n_frames)
            zs = np.empty(n_frames)
            for i, t in enumerate(times):
                x, y, z = elements_to_cartesian(body.elements, t)
                if body.parent and body.parent in result:
                    px, py, pz = result[body.parent]
                    x += px[i]; y += py[i]; z += pz[i]
                xs[i], ys[i], zs[i] = x, y, z
            result[body.name] = (xs, ys, zs)

    return times, result


def compute_scene_extent(
    orbit_paths: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    padding: float = 1.1,
    min_extent_au: float = 0.0,
) -> tuple[float, float, float]:
    """Return (x_half, y_half, z_half) symmetric extents covering all orbit paths.

    All three half-extents are set to the same value — the maximum absolute
    coordinate across *all* axes and *all* orbit paths, multiplied by
    ``padding`` (default 10 % margin).  This produces a cubic scene where
    1 AU looks identical in every direction, so circular orbits rendered with
    Plotly's ``aspectmode="data"`` appear as circles from any camera angle.

    Symmetric ranges also guarantee mid == 0 on every axis, so the JS
    coordinate conversion ``(data - mid) / maxHalf`` has no offset error.

    ``min_extent_au`` raises the floor for scene features that are not orbits,
    such as a solvent band wider than every orbit in the system.

    **There is no 1 AU floor on a system that has something to measure.**  There
    used to be, for the star-only case, and it silently inflated every compact
    system to fill a box nothing in it came near: TRAPPIST-1 spans 0.068 AU and
    was drawn in a 1.1 AU box, so its planets and its bands were a sixteenth of
    the frame and read as a smudge around the star.  The fallback now applies
    only when there is genuinely nothing to size from, which is what it was for.
    """
    max_x = max_y = max_z = float(min_extent_au)
    for xs, ys, zs in orbit_paths.values():
        max_x = max(max_x, float(np.max(np.abs(xs))))
        max_y = max(max_y, float(np.max(np.abs(ys))))
        max_z = max(max_z, float(np.max(np.abs(zs))))
    # Use the single largest extent for all three axes → cubic scene.
    # A non-cubic scene box distorts the isometric projection of circular orbits
    # into ovals; equal ranges eliminate that distortion.
    max_all = max(max_x, max_y, max_z)
    if max_all <= 0:
        # A star on its own, with no orbit and no band: 1 AU so it renders.
        max_all = 1.0
    return max_all * padding, max_all * padding, max_all * padding


def system_positions_at(
    system: StarSystem,
    t_jd: float,
) -> dict[str, tuple[float, float, float]]:
    """Single heliocentric position snapshot for every body at time t_jd.

    Moon positions include their parent planet's position.
    """
    result: dict[str, tuple[float, float, float]] = {}
    for body in system.bodies:
        if body.elements is None:
            result[body.name] = (0.0, 0.0, 0.0)
        else:
            x, y, z = elements_to_cartesian(body.elements, t_jd)
            if body.parent and body.parent in result:
                px, py, pz = result[body.parent]
                x += px; y += py; z += pz
            result[body.name] = (x, y, z)
    return result
