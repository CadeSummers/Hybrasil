# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One system in, one figure out -- the step the CLI and the web app share.

Both need the same thing: a system's time window, its orbit and coil paths,
and the animated (or static) figure built from them. Keeping it here means the
web app cannot draw a system differently from `python -m hybrasil.cli`.
"""

from __future__ import annotations

from typing import Optional

from .mechanics.time_series import (
    system_orbit_paths,
    system_positions_at,
    system_time_series,
)
from .models.system import StarSystem
from .viz import photosynthesis_rings, reference_orbits
from .viz.animation import build_animated_figure
from .viz.static_plot import build_static_figure

# Natural animation time spans (in days) for each built-in system.
# TRAPPIST-1 has very short periods so 30 days shows rich motion;
# Alpha Centauri B has a ~80-year period so 20 years shows meaningful movement.
_NATURAL_SPANS: dict[str, float] = {
    "solar":              365.25,
    "trappist-1":         30.0,
    "alpha-centauri":     365.25 * 20,
    # ups And d takes 1282.57 days, so a little over that shows every planet
    # round once.
    "upsilon-andromedae": 1540.0,
    # 55 Cnc d takes 5574.2 days.  The span is set by the outermost PLANET, not
    # by 55 Cnc B, whose circle is a 33,000-year placeholder and would never
    # close no matter how long the window.
    "55-cancri":          5700.0,
    # Castor's periods run from 0.81 days to ~13,000 years, so no span shows
    # them all moving.  A little over the longest close pair (Aa-Ab, 9.2 days)
    # shows every star turn once round its partner; the 459-year A-B orbit and
    # C's are drawn whole, as ellipses, and stand still.
    "castor":             10.0,
}


def _natural_span_days(system) -> float:
    """A time span that shows real motion: a bit over the slowest orbit.

    Used for catalog systems, whose periods range from hours to decades and so
    have no sensible fixed default.  Set by the planets, not by a companion
    star: 55 Cnc B's circle takes 33,000 years and would never close however
    long the window.  A system with no planet orbit falls back to its stars.

    A system with a moon is set by its moons instead: CD-35 2722 b takes ~740
    years round its star, and at that span the 171-day moon would jump
    randomly from frame to frame.
    """
    orbiting = [b for b in system.bodies
                if b.elements is not None and b.elements.period > 0]
    planets = [b for b in orbiting if b.body_type not in ("star", "barycentre")]
    moons = [b for b in planets if b.body_type == "moon"]
    periods = [b.elements.period for b in (moons or planets or orbiting)]
    if not periods:
        return 365.25
    return max(periods) * 1.2


def build_figure(system: StarSystem, t_start: float, t_end: float, *,
                 mode: str = "animated", frames: int = 120,
                 frame_duration_ms: int = 50, title: Optional[str] = None):
    """The Plotly figure for one system over [t_start, t_end] (Julian dates)."""
    orbit_paths, coil_paths = system_orbit_paths(system, t_start=t_start, t_end=t_end)
    if mode == "animated":
        times_jd, ts = system_time_series(system, t_start, t_end, frames)
        fig = build_animated_figure(
            system=system,
            time_series=ts,
            orbit_paths=orbit_paths,
            times_jd=times_jd,
            title=title,
            frame_duration_ms=frame_duration_ms,
            coil_paths=coil_paths,
        )
    else:
        fig = build_static_figure(
            system=system,
            positions=system_positions_at(system, t_start),
            orbit_paths=orbit_paths,
            title=title,
            coil_paths=coil_paths,
            coil_span_days=t_end - t_start,
        )
    # The three.js viewer's photosynthesis rings and reference orbits ride on
    # the layout meta, so they cannot shift a trace index (photosynthesis_rings.py).
    photosynthesis_rings.attach(fig, system, t_start)
    reference_orbits.attach(fig, system, t_start)
    return fig
