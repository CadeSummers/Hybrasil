# Coil trajectories

> Moved verbatim out of `CLAUDE.md` so it loads on demand. `CLAUDE.md` links here.

## Coil trajectories — how it works

A planet orbiting a star that is itself in orbit has no closed path in the primary's frame. Proxima Centauri b circles Proxima every 11.2 days while Proxima drifts along an 8,700 AU orbit around Alpha Centauri A, so the planet traces a helix. Drawing a Keplerian ellipse there is wrong twice over: the shape is not what the body traverses, and the ellipse is pinned to the parent's position at `t_start` while the animated marker rides along with the parent.

`is_coil_body()` decides this from the hierarchy alone: **the parent has elements and the parent is a star or a barycentre**. That catches any planet of a companion star in any multi-star system, and deliberately excludes a moon of a planet — a moon's closed ellipse is what makes the zoomed-in moon view readable, and turning it into a 2.7 AU tube along Jupiter's orbit would destroy that.

`generate_coil_orbit_path()` samples `parent(t) + body(t)` across the animation window, so the trace *is* the path the marker walks. Consequences worth knowing:

- **The window sets the coil.** `system_orbit_paths()` needs both `t_start` and `t_end`; given only `t_start` it falls back to ellipses. So does a body that would not finish one loop inside the window: an arc of Castor B's 459-year orbit is not a drawing of it, and its closed ellipse is.
- **The parent's position is the whole chain above it** (`ancestor_chain()`), not the parent's own orbit alone. Castor Bb sits three moving bodies down (Ba, the B barycentre, the A barycentre); a one-level lookup centred its coil on the wrong point.
- **A barycentre** (`body_type="barycentre"`, from `data/hierarchy.py`) is a massless point a pair orbits. One placed from its own primary member is bookkeeping, marked `draw_orbit=False`, and lands in neither dict. A longer `--time-end` stretches the coil, and the span is written into the trace name.
- **Sampling is clamped** to `[COIL_MIN_POINTS, COIL_MAX_POINTS]` = 360 to 12,000 at 16 points per loop. A few loops render as an open coil; thousands render as a tube. Both are the same curve at different densities.
- **Coils take part in scene visibility.** `_isClippable()` matches a coil by its `… trajectory (N yr)` name, so a coil that does not fit the scene box is hidden like any other closed shape. See "Scene visibility" in `zoom-and-visibility.md`.

**Playback starts paused.** `write_html()` is called with `auto_play=False` in both
`_write_html` and `_write_multi_html`. Plotly's default is `auto_play=True`, which
injects a `Plotly.animate(...)` call right after `newPlot` — the figure itself has no
autostart in it, so that argument is the only thing holding playback until the user
presses ▶ Play. The initial title carries frame 0's date for the same reason, and
`_build_switcher_js` strips the `" — <date>"` suffix back off for the system buttons.
