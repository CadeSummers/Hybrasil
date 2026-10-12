# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build an animated 3D Plotly figure for a star system."""

import numpy as np
import plotly.graph_objects as go
from ..models.system import StarSystem
from ..mechanics.units import jd_to_date
from ..mechanics.time_series import compute_scene_extent
from . import themes
from .static_plot import (belt_scene_extent, system_view_normal,
                          _orbit_trace, _coil_trace, _body_trace, _axis_trace, axis_points, _belt_trace,
                          _galactic_center_traces, _solar_system_traces, sky_meta,
                          centre_body_label, parent_of)


def kepler_meta(system: StarSystem, times_jd: np.ndarray) -> dict:
    """What the three.js viewer needs to place a body at any moment, not only at a frame.

    Between two frames the viewer used to slide each marker along the straight
    line joining them.  A planet that goes round several times in one frame step
    (Proxima d, 5.2 d, in Proxima's 19-day steps) then cut across the inside of
    its orbit.  With each body's elements the viewer solves Kepler's equation at
    the moment shown instead, so a marker never leaves its drawn orbit.

    Keyed by `body.label()`, the marker trace's name, which is how the viewer
    knows its bodies ('Proxima Centauri c (candidate)').  A parent is listed
    exactly when `system_time_series` adds its position: it is an earlier body
    with elements (a star at the origin adds nothing).
    """
    bodies: dict[str, dict] = {}
    label = {}
    for b in system.bodies:
        if b.elements is None:
            continue
        el = b.elements
        label[b.name] = b.label()
        bodies[b.label()] = {
            "el": [el.semi_major_axis, el.eccentricity, el.inclination,
                   el.longitude_of_ascending_node, el.argument_of_periapsis,
                   el.mean_anomaly_at_epoch, el.epoch, el.period],
            "parent": label.get(b.parent),
        }
    return {"t0": float(times_jd[0]), "t1": float(times_jd[-1]), "n": int(len(times_jd)),
            "bodies": bodies}


def _date_label(jd: float) -> str:
    try:
        y, m, d = jd_to_date(jd)
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return f"JD {jd:.1f}"


def build_animated_figure(
    system: StarSystem,
    time_series: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    orbit_paths: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    times_jd: np.ndarray,
    title: str | None = None,
    frame_duration_ms: int = 50,
    coil_paths: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] | None = None,
) -> go.Figure:
    """Build an animated Plotly 3D figure.

    Architecture:
      - Traces 0..N_orbit-1                          : static orbit lines (never updated)
      - Traces N_orbit..N_orbit+N_bodies-1            : body markers     (updated each frame)
      - Traces N_orbit+N_bodies..+N_bodies+N_axes-1   : rotation axes    (updated each frame)
      - Everything after                              : static coils, belts, reference vectors

    Frames only touch marker + axis traces by index; orbit lines never flicker.
    Coil traces are appended after the dynamic block so adding one cannot shift
    a marker index.
    """
    coil_paths = coil_paths or {}
    # Separate bodies with orbits from stars
    bodies_with_orbits = [b for b in system.bodies if b.elements is not None
                          and b.name in orbit_paths]
    bodies_with_poles  = [b for b in system.bodies if b.pole is not None]
    all_bodies = system.bodies
    n_orbit_traces = len(bodies_with_orbits)

    # --- Build initial traces ---
    traces: list = []

    # 1. Static orbit lines
    for body in bodies_with_orbits:
        if body.name in orbit_paths:
            xs, ys, zs = orbit_paths[body.name]
            traces.append(_orbit_trace(body, xs, ys, zs, parent_of(system, body)))

    # 2. Initial body positions (frame 0)
    marker_trace_indices = list(range(n_orbit_traces, n_orbit_traces + len(all_bodies)))
    for body in all_bodies:
        xs, ys, zs = time_series[body.name]
        traces.append(_body_trace(body, float(xs[0]), float(ys[0]), float(zs[0])))

    # 3. Initial rotation-axis lines (frame 0)
    axis_start = n_orbit_traces + len(all_bodies)
    axis_trace_indices = list(range(axis_start, axis_start + len(bodies_with_poles)))
    for body in bodies_with_poles:
        xs, ys, zs = time_series[body.name]
        traces.append(_axis_trace(body, float(xs[0]), float(ys[0]), float(zs[0])))

    dynamic_indices = marker_trace_indices + axis_trace_indices

    # 4. Coil trajectories — static, never updated by frames
    coil_span_days = float(times_jd[-1] - times_jd[0]) if len(times_jd) > 1 else 0.0
    for body in system.bodies:
        if body.name in coil_paths:
            xs, ys, zs = coil_paths[body.name]
            traces.append(_coil_trace(body, xs, ys, zs, coil_span_days))

    # Positions at t=0, for anything static that has to sit on a body.
    positions_t0 = {
        name: (float(xs[0]), float(ys[0]), float(zs[0]))
        for name, (xs, ys, zs) in time_series.items()
    }

    # 5. Belt zones — static, never updated by frames.
    # A band rings its own star, and a star that is itself in orbit moves; the
    # band is built where that star is at t_start, the way a moon's ellipse is.
    for zone in system.belt_zones:
        traces.append(_belt_trace(
            zone, centre=positions_t0.get(zone.centre_body, (0.0, 0.0, 0.0)),
            body=centre_body_label(system, zone)))

    # 6. Galactic-center reference vector — static, never updated by frames.
    # Use t=0 star positions for the barycenter (stars are fixed or nearly so).
    x_half, y_half, z_half = compute_scene_extent(
        {**orbit_paths, **coil_paths}, min_extent_au=belt_scene_extent(system))
    traces.extend(_galactic_center_traces(system, positions_t0, x_half))
    traces.extend(_solar_system_traces(system, positions_t0, x_half))

    # --- Build animation frames ---
    n_frames = len(times_jd)
    frames = []
    for fi in range(n_frames):
        frame_data = []

        # Marker updates
        for body in all_bodies:
            xs, ys, zs = time_series[body.name]
            marker = themes.body_marker_style(body.body_type, body.color, body.status)
            frame_data.append(go.Scatter3d(
                x=[float(xs[fi])],
                y=[float(ys[fi])],
                z=[float(zs[fi])],
                marker=marker,
            ))

        # Axis line updates — move endpoints with the body each frame
        for body in bodies_with_poles:
            xs, ys, zs = time_series[body.name]
            bx, by, bz = float(xs[fi]), float(ys[fi]), float(zs[fi])
            axs, ays, azs = axis_points(body, bx, by, bz)
            frame_data.append(go.Scatter3d(x=axs, y=ays, z=azs))

        frames.append(go.Frame(
            data=frame_data,
            traces=dynamic_indices,
            name=str(fi),
            layout=go.Layout(
                title_text=f"{system.name} — {_date_label(times_jd[fi])}"
            ),
        ))

    # --- Slider steps ---
    slider_steps = []
    # Show ~20 labels max to keep slider readable
    label_every = max(1, n_frames // 20)
    for fi in range(n_frames):
        label = _date_label(times_jd[fi]) if fi % label_every == 0 else ""
        slider_steps.append(dict(
            args=[[str(fi)], dict(
                frame=dict(duration=frame_duration_ms, redraw=True),
                mode="immediate",
                transition=dict(duration=0),
            )],
            label=label,
            method="animate",
        ))

    sliders = [dict(
        active=0,
        steps=slider_steps,
        x=0.0,
        xanchor="left",
        y=0.0,
        yanchor="top",
        pad=dict(b=10, t=10),
        len=1.0,
        currentvalue=dict(
            prefix="Date: ",
            visible=True,
            xanchor="center",
            font=dict(color=themes.FONT_COLOR, size=12),
        ),
        tickcolor=themes.FONT_COLOR,
        font=dict(color=themes.FONT_COLOR, size=9),
        bgcolor="#111130",
        bordercolor="#333366",
    )]

    # --- Play / Pause buttons ---
    updatemenus = [dict(
        type="buttons",
        showactive=False,
        y=0,
        x=0,
        xanchor="right",
        yanchor="top",
        pad=dict(t=10, r=10),
        buttons=[
            dict(
                label="▶ Play",
                method="animate",
                args=[None, dict(
                    frame=dict(duration=frame_duration_ms, redraw=True),
                    fromcurrent=True,
                    transition=dict(duration=0),
                )],
            ),
            dict(
                label="⏸ Pause",
                method="animate",
                args=[[None], dict(
                    frame=dict(duration=0, redraw=False),
                    mode="immediate",
                    transition=dict(duration=0),
                )],
            ),
        ],
        bgcolor="#111130",
        bordercolor="#333366",
        font=dict(color=themes.FONT_COLOR),
    )]

    # The figure opens paused on frame 0, so the initial title carries that
    # frame's date — same shape the frames use, rather than a bare system name
    # that only grows a date once the user presses Play.
    layout_title = title or system.name
    if len(times_jd):
        layout_title = f"{layout_title} — {_date_label(times_jd[0])}"
    fig = go.Figure(
        data=traces,
        layout=go.Layout(
            title=dict(text=layout_title, font=dict(color=themes.FONT_COLOR, size=16)),
            scene=themes.make_scene_style(x_half, y_half, z_half,
                                          system_view_normal(system)),
            updatemenus=updatemenus,
            sliders=sliders,
            meta={**sky_meta(system),
                  **({"kepler": kepler_meta(system, times_jd)} if len(times_jd) else {})},
            **themes.LAYOUT_DEFAULTS,
        ),
        frames=frames,
    )
    return fig
