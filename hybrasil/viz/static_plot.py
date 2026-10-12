# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a static 3D Plotly figure for a star system snapshot."""

import math
from typing import Optional

import numpy as np
import plotly.graph_objects as go
from ..models.body import OrbitalBody
from ..mechanics.orientation import galactic_to_frame, plane_basis
from ..models.system import StarSystem, BeltZone
from ..mechanics.time_series import compute_scene_extent
from . import themes

# ---------------------------------------------------------------------------
# Galactic-center reference vector
# ---------------------------------------------------------------------------

# Unit vector toward the galactic center in ecliptic J2000 Cartesian.
# Source: Sgr A* at RA 266.417°, Dec −29.008° (J2000), converted to ecliptic
# using obliquity ε = 23.439°.  The GC lies almost entirely in the −Y
# direction of the ecliptic frame.
#
# This is the fallback only.  It is right for the Solar System, whose frame is
# the ecliptic, and for a system drawn flat with no frame of its own; a system
# quoted against the plane of the sky carries its own vector instead, since
# this one would point somewhere its orbits do not agree with.
_GC_DIR: tuple[float, float, float] = (-0.05466, -0.99365, -0.09774)


def sky_meta(system: StarSystem) -> dict:
    """What the three.js viewer needs to hang the Milky Way behind a system.

    Carried on the figure (``layout.meta``) because the figure is all the
    viewer receives.  The rotation comes from the same frame the
    galactic-centre arrow is quoted in, so the arrow points at the galactic
    centre in the picture: a sky-frame system's own (RA, Dec), or the
    ecliptic for everything else -- the same fallback `_GC_DIR` is.
    """
    m = galactic_to_frame(system.sky_frame_radec)
    return {"sky": {"galactic_to_frame": [list(row) for row in m]}}


def _largest_body_position(
    system: StarSystem,
    positions: dict[str, tuple[float, float, float]],
) -> tuple[float, float, float]:
    """Position of the most massive body in the system.

    Falls back to the first star with a known position, then to the origin.
    """
    bodies = system.bodies
    known = [(b.mass_kg or 0.0, b.name) for b in bodies if b.name in positions]
    if known:
        _, name = max(known, key=lambda t: t[0])
        return positions[name]
    return (0.0, 0.0, 0.0)


def _galactic_center_traces(
    system: StarSystem,
    positions: dict[str, tuple[float, float, float]],
    scene_half_au: float,
) -> list:
    """Scatter3d shaft + Cone arrowhead from the stellar barycenter toward
    the galactic center.

    Arrow length = 25 % of the scene half-extent so it is always visible
    without dominating the view at any scale.  None for a system at the
    galactic centre itself, which the arrow would point from and to.
    """
    if system.at_galactic_center:
        return []
    bx, by, bz = _largest_body_position(system, positions)
    dx, dy, dz = system.galactic_center_direction or _GC_DIR
    length = scene_half_au * 0.25
    tip_x = bx + dx * length
    tip_y = by + dy * length
    tip_z = bz + dz * length
    cone_size = length * 0.12
    color = "#88CCFF"

    if system.distance_to_galactic_center_ly is not None:
        au = system.distance_to_galactic_center_ly * 63241.1
        label = (f"Galactic Center: {system.distance_to_galactic_center_ly:,.0f} Light Years"
                 f" / {au:,.0f} AU Away")
    else:
        label = "Galactic Center"

    shaft = go.Scatter3d(
        x=[bx, tip_x], y=[by, tip_y], z=[bz, tip_z],
        mode="lines+text",
        name=label,
        text=["", label],
        textposition="top center",
        textfont=dict(color=color, size=10),
        line=dict(color=color, width=3),
        showlegend=True,
        hoverinfo="skip",
    )
    cone = go.Cone(
        x=[tip_x], y=[tip_y], z=[tip_z],
        u=[dx], v=[dy], w=[dz],
        colorscale=[[0, color], [1, color]],
        showscale=False,
        sizemode="absolute",
        sizeref=cone_size,
        name=label,
        showlegend=False,
        hoverinfo="skip",
    )
    return [shaft, cone]


def _solar_system_traces(
    system: StarSystem,
    positions: dict[str, tuple[float, float, float]],
    scene_half_au: float,
) -> list:
    """Scatter3d shaft + Cone arrowhead from the stellar barycenter toward the
    Solar System, labeled with the distance in light-years and AU.

    Returns an empty list when the system has no solar_system_direction set
    (e.g. the Solar System itself).
    """
    if system.solar_system_direction is None or system.distance_from_sun_ly is None:
        return []
    bx, by, bz = _largest_body_position(system, positions)
    dx, dy, dz = system.solar_system_direction
    length = scene_half_au * 0.25
    tip_x = bx + dx * length
    tip_y = by + dy * length
    tip_z = bz + dz * length
    cone_size = length * 0.12
    color = "#FFCC88"

    au = system.distance_from_sun_ly * 63241.1
    label = (f"Solar System: {system.distance_from_sun_ly:.1f} Light Years"
             f" / {au:,.0f} AU Away")

    shaft = go.Scatter3d(
        x=[bx, tip_x], y=[by, tip_y], z=[bz, tip_z],
        mode="lines+text",
        name=label,
        text=["", label],
        textposition="top center",
        textfont=dict(color=color, size=10),
        line=dict(color=color, width=3),
        showlegend=True,
        hoverinfo="skip",
    )
    cone = go.Cone(
        x=[tip_x], y=[tip_y], z=[tip_z],
        u=[dx], v=[dy], w=[dz],
        colorscale=[[0, color], [1, color]],
        showscale=False,
        sizemode="absolute",
        sizeref=cone_size,
        name=label,
        showlegend=False,
        hoverinfo="skip",
    )
    return [shaft, cone]


# Tag carried by every solvent-band mesh, and the only thing the viewer's
# Bands button matches on.  A band is drawn hidden and this is what switches
# it back on; see `_belt_trace`.
SOLVENT_BAND_META = "solvent-band"

# Vertices per edge of a band or belt ring.  The viewer rebuilds solvent-band
# rings as its sliders move and has to use the same number, or the clipper's
# cache and the trace would disagree on how many points a band has.
BAND_RING_POINTS = 180


def is_band_trace(trace) -> bool:
    """Whether a Plotly trace is a solvent band, by its tag alone."""
    meta = getattr(trace, "meta", None)
    return isinstance(meta, dict) and meta.get("kind") == SOLVENT_BAND_META


def band_meta(zone: BeltZone,
              centre: tuple[float, float, float] = (0.0, 0.0, 0.0),
              body: str = "") -> dict:
    """What a band mesh carries so the viewer can recompute it.

    The viewer's pressure and albedo sliders rebuild these rings in the
    browser, so each trace holds its own inputs: which solvent, how bright the
    star, which plane, whether the functional ceiling applies, and the star's
    colour factor -- computed here in Python once, so the viewer only
    multiplies by it and the Kopparapu fit exists in one place.  Keeping
    them on the trace is what lets a system swap work without any bookkeeping
    -- the new system's traces arrive carrying the new system's star.
    """
    return {
        "kind": SOLVENT_BAND_META,
        "solvent": zone.solvent_key,
        "lum": zone.luminosity_sun,
        "normal": list(zone.normal),
        "centre": [float(c) for c in centre],
        # The star at that centre, as its marker is named (`centre_body_label`):
        # the three.js viewer moves the band with it as it orbits.  `centre`
        # stays where the star was at t_start.
        "body": body,
        "star": zone.star_label,
        "ceiling": bool(zone.apply_ceiling),
        "colour": float(zone.colour_factor),
    }


def band_centre_distance_au(system: StarSystem, zone: BeltZone) -> float:
    """How far from the origin the star this band rings can get.

    Apoapsis rather than the semi-major axis, so a band around an eccentric
    companion still has room at the far end of its star's orbit.  A band at the
    origin, which is every belt and every primary's band, is 0.
    """
    if not zone.centre_body:
        return 0.0
    body = next((b for b in system.bodies if b.name == zone.centre_body), None)
    if body is None or body.elements is None:
        return 0.0
    return body.elements.semi_major_axis * (1.0 + body.elements.eccentricity)


def system_view_normal(system: StarSystem) -> tuple[float, float, float]:
    """The plane the camera should look at this system's bands in.

    Read straight off the first solvent band rather than derived a second time,
    so the camera and the band it is pointed at cannot drift apart -- including
    under `--band-plane reference`, which puts every band back on z and should
    put the camera back with it.  The first band is the primary's, since
    `zones_for_system` builds the stacks in body order; a figure whose stars
    disagree about their planes can only be face-on to one of them, and the
    primary is the one to pick.
    """
    for zone in system.belt_zones:
        if zone.is_solvent_band:
            return zone.normal
    return (0.0, 0.0, 1.0)


def belt_scene_extent(system: StarSystem) -> float:
    """How wide the scene must be for every belt zone that asks to stay in frame.

    A band centred on a star that is itself in orbit claims its star's distance
    *plus* its own outer radius: the ring is around that star, not around the
    origin, so the radius alone would leave most of it outside the box.
    """
    return max((band_centre_distance_au(system, z) + z.scene_claim_au
                for z in system.belt_zones if z.extends_scene),
               default=0.0)


def centre_body_label(system: StarSystem, zone: BeltZone) -> str:
    """The legend name of the star a band rings, which is what its marker is
    called -- a hypothetical star's label is not its name."""
    body = next((b for b in system.bodies if b.name == zone.centre_body), None)
    return body.label() if body is not None else ""


def _belt_trace(zone: BeltZone, n_pts: int = BAND_RING_POINTS,
                centre: tuple[float, float, float] = (0.0, 0.0, 0.0),
                body: str = "") -> go.Mesh3d:
    """Flat semi-transparent annulus in the zone's own plane.

    The ring is built in the 2-D basis that spans that plane rather than in
    x-y, so a band inclined with its system's orbits (TRAPPIST-1's are at
    89.8 deg) is a ring around the star rather than a wall across it.

    A solvent band carries `meta = SOLVENT_BAND_META` and starts on
    'legendonly'.  That is the whole handle the viewer's Bands button has on
    it: the figure opens on the orbits, and one click brings every band in the
    system back.  Matching on the trace name would break the moment a solvent
    is renamed, and the name is already load-bearing for the search.
    """
    if zone.r_outer_au <= zone.r_inner_au:
        # No liquid phase at this pressure, so there is no ring to draw -- but
        # the trace still has to exist, because the viewer's sliders rewrite
        # these in place and an appearing trace would shift every index after
        # it.  An empty mesh keeps its legend entry and draws nothing.
        trace = go.Mesh3d(x=[], y=[], z=[], i=[], j=[], k=[],
                          color=zone.color, opacity=zone.opacity,
                          name=zone.name, showlegend=zone.show_in_legend,
                          hoverinfo="skip", flatshading=True)
        if zone.legend_group:
            trace.legendgroup = zone.legend_group
        if zone.is_solvent_band:
            trace.meta = band_meta(zone, centre, body)
            trace.visible = "legendonly"
        return trace

    theta = np.linspace(0, 2 * np.pi, n_pts, endpoint=False)
    radius = np.concatenate([np.full(n_pts, zone.r_inner_au),
                             np.full(n_pts, zone.r_outer_au)])
    angle = np.concatenate([theta, theta])
    u, v = plane_basis(zone.normal)
    # The stacking offset runs along the *unit* normal -- `offset_au` is a
    # distance in AU, which it only is if what it multiplies has length 1.  A
    # stored normal is normalised in practice, but `plane_basis` normalises and
    # the viewer's `_ringMesh` does too, so not normalising here was the one
    # place the two implementations could disagree.
    unit = np.asarray(zone.normal, dtype=float)
    length = float(np.linalg.norm(unit))
    if length > 0:
        unit = unit / length
    # The star the band rings is wherever it happens to be at t_start.
    origin = unit * zone.offset_au + np.asarray(centre, dtype=float)
    ring = (radius[:, None] * np.cos(angle)[:, None] * np.asarray(u)
            + radius[:, None] * np.sin(angle)[:, None] * np.asarray(v)
            + origin)
    x, y, z = ring[:, 0], ring[:, 1], ring[:, 2]

    # Two triangles per quad between inner[i]→inner[i+1] and outer[i]→outer[i+1]
    idx = np.arange(n_pts)
    nxt = (idx + 1) % n_pts
    i_f = np.concatenate([idx,         nxt        ])
    j_f = np.concatenate([nxt,         n_pts + nxt])
    k_f = np.concatenate([n_pts + idx, n_pts + idx])

    trace = go.Mesh3d(
        x=x, y=y, z=z,
        i=i_f, j=j_f, k=k_f,
        color=zone.color,
        opacity=zone.opacity,
        name=zone.name,
        showlegend=zone.show_in_legend,
        hoverinfo="skip",
        flatshading=True,
    )
    if zone.legend_group:
        trace.legendgroup = zone.legend_group
    if zone.is_solvent_band:
        trace.meta = band_meta(zone, centre, body)
        trace.visible = "legendonly"
    return trace


def parent_of(system: StarSystem, body: OrbitalBody) -> Optional[OrbitalBody]:
    """The body's parent, if it is in the system."""
    return next((b for b in system.bodies if b.name == body.parent), None) if body.parent else None


def _orbit_trace(body: OrbitalBody, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray,
                 parent: Optional[OrbitalBody] = None) -> go.Scatter3d:
    color = themes.body_color(body.body_type, body.color)
    opacity = themes.orbit_opacity(body.body_type)
    width = themes.orbit_width(body.body_type)
    dash = themes.orbit_dash(body.body_type, body.status)
    # An ellipse round a parent that moves -- a moon's planet, or a barycentre
    # like Castor AB, round which Castor C's 13,000-year orbit is drawn -- is
    # drawn round the parent's position at t_start, and the three.js viewer
    # carries it along with the parent during playback.  Keyed by the parent
    # marker's label, which is how the viewer names its bodies.
    follows = parent.label() if parent is not None and parent.elements is not None else None
    return go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode="lines",
        name=f"{body.label()} orbit",
        line=dict(color=color, width=width, dash=dash),
        opacity=opacity,
        showlegend=False,
        hoverinfo="skip",
        meta={"follows": follows} if follows else None,
    )


def _coil_trace(body: OrbitalBody, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray,
                span_days: float) -> go.Scatter3d:
    """The open helix a body traces while its parent star moves.

    Styled like the body's ellipse would have been, so a coil reads as the same
    kind of object. The span is in the trace name because the curve is only
    closed over the window that was drawn.
    """
    color = themes.body_color(body.body_type, body.color)
    opacity = themes.orbit_opacity(body.body_type)
    width = themes.orbit_width(body.body_type)
    dash = themes.orbit_dash(body.body_type, body.status)
    years = span_days / 365.25
    return go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode="lines",
        name=f"{body.label()} trajectory ({years:.1f} yr)",
        line=dict(color=color, width=width, dash=dash),
        opacity=opacity,
        showlegend=False,
        hoverinfo="skip",
    )


def _body_trace(body: OrbitalBody, x: float, y: float, z: float) -> go.Scatter3d:
    marker = themes.body_marker_style(body.body_type, body.color, body.status)
    if body.body_type == "star":
        marker["symbol"] = "circle"
    # A barycentre sits within a hair of the stars it belongs to; a label on it
    # would sit on top of theirs.  Hovering names it.
    unlabelled = body.body_type == "barycentre"
    return go.Scatter3d(
        x=[x], y=[y], z=[z],
        mode="markers" if unlabelled else "markers+text",
        name=body.label(),
        text=[body.label()],
        textposition="top center",
        textfont=dict(color=themes.FONT_COLOR, size=10),
        marker=marker,
        hovertemplate=f"<b>{body.label()}</b><br>x: %{{x:.4f}} AU<br>y: %{{y:.4f}} AU<br>z: %{{z:.4f}} AU<extra></extra>",
    )

def axis_points(body: OrbitalBody, x: float, y: float, z: float) -> tuple[list, list, list]:
    """The body's rotation axis through (x, y, z): south end, north end, then an arrowhead's two
    wings drawn back from the north end, as one polyline (the three.js viewer skips cones).

    The arrowhead is what says which way the body spins: north is the end its spin points along by
    the right-hand rule, so a retrograde spin -- an axis tilted past 90 deg -- reads at a glance.
    """
    px, py, pz = body.pole  # type: ignore[misc]
    half = body.axis_half_au if body.axis_half_au is not None else themes.axis_half_length(body.body_type)
    south = (x - px * half, y - py * half, z - pz * half)
    north = (x + px * half, y + py * half, z + pz * half)
    # A wing direction perpendicular to the axis: whichever of x and z is further from it.
    ref = (1.0, 0.0, 0.0) if abs(px) < 0.9 else (0.0, 0.0, 1.0)
    side = (py * ref[2] - pz * ref[1], pz * ref[0] - px * ref[2], px * ref[1] - py * ref[0])
    n = math.sqrt(sum(c * c for c in side)) or 1.0
    side = tuple(c / n for c in side)
    head = 0.25 * half
    back = tuple(t - head * c for t, c in zip(north, (px, py, pz)))
    wing1 = tuple(b + 0.5 * head * s for b, s in zip(back, side))
    wing2 = tuple(b - 0.5 * head * s for b, s in zip(back, side))
    pts = [south, north, wing1, north, wing2]
    return [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]


def _axis_trace(body: OrbitalBody, x: float, y: float, z: float) -> go.Scatter3d:
    """The body's rotation axis, arrowhead at its north end; dashed where the pole is assumed."""
    color = themes.body_color(body.body_type, body.color)
    xs, ys, zs = axis_points(body, x, y, z)
    return go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode="lines",
        name=f"{body.label()} axis" + (f" ({body.pole_note})" if body.pole_assumed and body.pole_note else ""),
        line=dict(color=color, width=2, dash="dash" if body.pole_assumed else "solid"),
        opacity=0.7,
        showlegend=False,
        hoverinfo="skip",
        # The three.js viewer moves the line with its body, as it moves a
        # moon's ellipse; Plotly's frames redraw it instead.
        meta={"follows": body.label()},
    )


def build_static_figure(
    system: StarSystem,
    positions: dict[str, tuple[float, float, float]],
    orbit_paths: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    title: str | None = None,
    coil_paths: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] | None = None,
    coil_span_days: float = 0.0,
) -> go.Figure:
    """Assemble a static 3D Plotly figure.

    Orbit lines are drawn first, then body markers, then rotation-axis lines on top.
    """
    coil_paths = coil_paths or {}
    traces: list = []

    # Belt zones first (background)
    for zone in system.belt_zones:
        traces.append(_belt_trace(
            zone, centre=positions.get(zone.centre_body, (0.0, 0.0, 0.0)),
            body=centre_body_label(system, zone)))

    # Orbit lines
    for body in system.bodies:
        if body.elements is not None and body.name in orbit_paths:
            xs, ys, zs = orbit_paths[body.name]
            traces.append(_orbit_trace(body, xs, ys, zs, parent_of(system, body)))

    # Coil trajectories (bodies orbiting a star that is itself in orbit)
    for body in system.bodies:
        if body.name in coil_paths:
            xs, ys, zs = coil_paths[body.name]
            traces.append(_coil_trace(body, xs, ys, zs, coil_span_days))

    # Body markers
    for body in system.bodies:
        if body.name in positions:
            x, y, z = positions[body.name]
            traces.append(_body_trace(body, x, y, z))

    # Rotation-axis lines (only for bodies with a pole defined)
    for body in system.bodies:
        if body.pole is not None and body.name in positions:
            x, y, z = positions[body.name]
            traces.append(_axis_trace(body, x, y, z))

    x_half, y_half, z_half = compute_scene_extent(
        {**orbit_paths, **coil_paths}, min_extent_au=belt_scene_extent(system))

    # Reference vectors
    traces.extend(_galactic_center_traces(system, positions, x_half))
    traces.extend(_solar_system_traces(system, positions, x_half))
    layout_title = title or f"{system.name} — Snapshot"
    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(text=layout_title, font=dict(color=themes.FONT_COLOR, size=16)),
        scene=themes.make_scene_style(x_half, y_half, z_half,
                                          system_view_normal(system)),
        meta=sky_meta(system),
        **themes.LAYOUT_DEFAULTS,
    )
    return fig
