# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Visual constants and Plotly styling for star system plots."""

from ..mechanics.orientation import camera_for_plane

BODY_COLORS: dict[str, str] = {
    "star": "#FFD700",
    "planet": "#4488CC",
    "moon": "#999999",
    "asteroid": "#CC8844",
    "comet": "#88CCFF",
    "custom": "#AADDAA",
    "barycentre": "#9A9AB0",
}

BODY_SIZES: dict[str, int] = {
    "star": 26,
    "planet": 18,
    "moon": 11,
    "asteroid": 8,
    "comet": 9,
    "custom": 12,
    "barycentre": 7,
}

ORBIT_OPACITY: dict[str, float] = {
    "star": 0.70,  # bright so stellar orbits (e.g. Proxima) are clearly visible
    "planet": 0.35,
    "moon": 0.25,
    "asteroid": 0.2,
    "comet": 0.2,
    "custom": 0.3,
    # A barycentre's orbit is a stellar pair's orbit about another pair.
    "barycentre": 0.70,
}

ORBIT_WIDTHS: dict[str, int] = {
    "star": 2,
    "planet": 1,
    "moon": 1,
    "asteroid": 1,
    "comet": 1,
    "custom": 1,
    "barycentre": 2,
}

BACKGROUND_COLOR = "#070714"
GRID_COLOR = "#1a1a3a"
ZERO_LINE_COLOR = "#2a2a5a"
PAPER_COLOR = "#07071a"
FONT_COLOR = "#ccccee"

_AXIS_STYLE = dict(
    backgroundcolor=BACKGROUND_COLOR,
    gridcolor=GRID_COLOR,
    showbackground=True,
    zerolinecolor=ZERO_LINE_COLOR,
    tickfont=dict(color=FONT_COLOR, size=10),
)

SCENE_STYLE = dict(
    xaxis=dict(**_AXIS_STYLE, title=dict(text="X (AU)", font=dict(color=FONT_COLOR))),
    yaxis=dict(**_AXIS_STYLE, title=dict(text="Y (AU)", font=dict(color=FONT_COLOR))),
    zaxis=dict(**_AXIS_STYLE, title=dict(text="Z (AU)", font=dict(color=FONT_COLOR))),
    bgcolor=BACKGROUND_COLOR,
    aspectmode="cube",
)

# Plotly's own default camera, written against the reference plane.  Kept here
# because `make_scene_style` rotates it into the system's band plane and the
# viewer has to start from the same vector to reproduce it.
DEFAULT_EYE = (1.25, 1.25, 1.25)


def make_scene_style(x_half: float, y_half: float, z_half: float,
                     view_normal: tuple[float, float, float] = (0.0, 0.0, 1.0)
                     ) -> dict:
    """Return a SCENE_STYLE copy with explicit symmetric axis ranges.

    Explicit ranges guarantee that the JS coordinate converter always uses the
    correct mid == 0 / maxHalf values regardless of when or how often Plotly
    rewrites _fullLayout.scene.*.range internally after relayout calls.

    `view_normal` is the plane the system's solvent bands lie in, and the
    camera is rotated into it.  The angle is unchanged -- it is the same
    three-quarter view Plotly would give -- but it is measured against the band
    rather than against world z, so a system whose reference plane is the plane
    of the sky opens looking *at* its bands instead of along them.  A flat
    system's normal is the z axis and the rotation is the identity, so the
    Solar System's camera does not move.
    """
    style = dict(SCENE_STYLE)
    style["xaxis"] = dict(style["xaxis"], range=[-x_half, x_half])
    style["yaxis"] = dict(style["yaxis"], range=[-y_half, y_half])
    style["zaxis"] = dict(style["zaxis"], range=[-z_half, z_half])
    eye, up = camera_for_plane(view_normal, DEFAULT_EYE)
    style["camera"] = dict(eye=dict(x=eye[0], y=eye[1], z=eye[2]),
                           up=dict(x=up[0], y=up[1], z=up[2]),
                           center=dict(x=0, y=0, z=0))
    return style


LAYOUT_DEFAULTS = dict(
    paper_bgcolor=PAPER_COLOR,
    plot_bgcolor=PAPER_COLOR,
    font=dict(color=FONT_COLOR, family="monospace"),
    margin=dict(l=0, r=0, t=50, b=0),
    legend=dict(
        bgcolor="rgba(10,10,30,0.7)",
        bordercolor="#333366",
        borderwidth=1,
        font=dict(color=FONT_COLOR, size=11),
    ),
)


def body_color(body_type: str, override: str | None) -> str:
    if override:
        return override
    return BODY_COLORS.get(body_type, BODY_COLORS["custom"])


def body_size(body_type: str) -> int:
    return BODY_SIZES.get(body_type, BODY_SIZES["custom"])


def orbit_opacity(body_type: str) -> float:
    return ORBIT_OPACITY.get(body_type, 0.3)


def orbit_width(body_type: str) -> int:
    return ORBIT_WIDTHS.get(body_type, 1)


def orbit_dash(body_type: str, status: str) -> str:
    """Return the Plotly line dash style for an orbit path.

    Star orbits are always solid — the ring must be clearly legible at any scale.
    Hypothetical planets/moons use a dashed line to flag uncertain elements.
    """
    if body_type == "star":
        return "solid"
    return "dash" if status == "hypothetical" else "solid"


# Half-length of the rotation-axis line in AU (total line = 2× this value).
AXIS_HALF_LENGTHS: dict[str, float] = {
    "star":    1.5,
    "planet":  0.5,
    "moon":    0.0,
    "asteroid": 0.5,
    "comet":   0.0,
    "custom":  0.3,
}


def axis_half_length(body_type: str) -> float:
    return AXIS_HALF_LENGTHS.get(body_type, 0.0)


def body_marker_style(body_type: str, color: str | None, status: str) -> dict:
    """Return a Plotly marker dict. Hypothetical bodies and barycentres are hollow circles.

    A hypothetical star -- a candidate or a model-inferred companion nothing has
    resolved -- is hollow too, a ring in its own colour, as a candidate planet is.
    """
    resolved = body_color(body_type, color)
    base = dict(color=resolved, size=body_size(body_type), opacity=1.0)
    if body_type == "star" and status == "hypothetical":
        base["color"] = "rgba(0,0,0,0)"
        base["line"] = dict(color=resolved, width=2)
    elif body_type == "star":
        base["line"] = dict(color="#FFFFFF", width=2)
    elif body_type == "barycentre":
        # A point, not a body: always a hollow ring, whatever its status.
        base["color"] = "rgba(0,0,0,0)"
        base["line"] = dict(color=resolved, width=1.5)
    elif status == "hypothetical":
        base["color"] = "rgba(0,0,0,0)"
        base["line"] = dict(color=resolved, width=2)
    return base


