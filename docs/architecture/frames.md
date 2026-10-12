# Which frame a system is in

> Moved verbatim out of `CLAUDE.md` so it loads on demand. `CLAUDE.md` links here.

## Which frame a system is in

Only the Solar System is quoted in the ecliptic. Every other built-in has its
angles from astrometry or transits, and those are measured **from the plane of
the sky**, with the ascending node counterclockwise from North. Such a system's
reference plane therefore *is* the sky plane: x is North, y is East, and
z = North × East runs back along the line of sight toward Earth.

Orbits do not care — the relative geometry is the same whichever way the frame
is labelled. The two **reference arrows** do, because a direction is only
meaningful in a frame:

- `solar_system_direction` is `TOWARD_EARTH`, `(0, 0, 1)`, for every sky-frame
  system. It is not a coincidence or a placeholder; the line of sight is the
  z axis by construction.
- `galactic_center_direction` is computed per system by
  `galactic_centre_in_sky_frame()` from the star's RA, Dec and distance. `None`
  falls back to `_GC_DIR` in `viz/static_plot.py`, the ecliptic constant, which
  is right for the Solar System and for anything drawn flat with no frame of
  its own.

Both were previously one shared ecliptic vector, which pointed somewhere three
of the four systems' own orbits did not agree with.

**A catalog system stays in the ecliptic frame.** Its orbits have no measured
angles, so no frame is better supported than the ecliptic, and keeping it means
the galactic-centre arrow (`_GC_DIR`) and the sky need nothing new. Its Sun arrow
is `toward_sun_in_ecliptic(ra, dec)`: the reverse of the star's line of sight,
in ecliptic coordinates, from the Systems tab's RA/Dec. That is correct against
the galactic-centre arrow and the Milky Way; how the flat disc is tilted against
it is not known. See `docs/architecture/catalog.md`.

Two limits worth knowing:

1. **An unmeasured node makes the in-plane azimuth arbitrary.** TRAPPIST-1 and
   Proxima carry `Ω = 0` for every planet because nothing measured it, so their
   frames' x axis is not really North and only the line-of-sight component of
   these vectors means anything. That component is still the one that says
   whether the galactic centre lies beyond the system or back past us, and the
   ecliptic vector got even that wrong.
2. **The distance and the direction are computed the same way.**
   `galactic_centre_distance_ly()` reproduces the figure each system carries to
   within 4 ly, which is what says the arrow and the label on it agree.

## Spin axes

A body with a `pole` gets its rotation axis drawn through it (`static_plot.axis_points`): a line from the south end to the north end, plus an arrowhead's two wings at the north end, so the sense of spin reads at a glance.
- **The arrowhead** (since 10 Oct 2026) is on every axis, the Solar System's included. It is part of the polyline because the three.js viewer skips cones.
- **Length:** `axis_half_au` when set; otherwise the body type's default from `themes.AXIS_HALF_LENGTHS`.
- **An assumed pole** (`pole_assumed`, e.g. nu Oct A, assumed to spin with its binary) is drawn dashed and named "… axis (assumed: …)".
- **Catalog stars** get a pole only from the Orbit Direction column (`docs/architecture/catalog.md`).

## The background sky follows the same frame

The three.js viewer draws the Milky Way behind every system: NASA's Deep Star
Maps 2020, an all-sky map in galactic coordinates (`hybrasil/viz/sky/`).
It is turned into each system's frame by `orientation.galactic_to_frame()`, so
the galactic-centre arrow points at the galactic centre in the picture.

- **It is a full rotation, not a direction.** The arrow needs one vector; the
  sky needs three, or it could spin about the arrow. `StarSystem.sky_frame_radec`
  records the star's (RA, Dec) for a sky-frame system, and the rotation is
  built from the same `sky_frame_basis()` the arrow uses. None means the
  ecliptic frame, the same fallback `_GC_DIR` is.
- **The two must be set together.** A sky-frame arrow over an ecliptic sky
  would point somewhere the galactic centre is not.
  `tests/test_sky.py::test_a_system_with_its_own_arrow_has_its_own_sky` pins it.
- **Distance does not enter.** From any star within 100 ly the Milky Way sits
  where it does from here to within 0.2 deg, so the sky is at infinity. The
  arrow is aimed at Sgr A* from the star itself, which puts it within 0.12 deg
  of the map's centre (l = b = 0) for every built-in.
- **How it reaches the page.** `static_plot.sky_meta()` puts the rotation on
  the figure (`layout.meta.sky`), since the figure is all the viewer receives.
  `figure_to_scene()` carries it into the scene as `sky.galactic_to_frame`, and
  the shader looks each view direction up in the map through its transpose.
  `__SA3.skyUV()` is that lookup in JavaScript, for the browser test that
  checks the arrow lands on (0.5, 0.5).
- **It has its own render pass.** A unit sphere around a camera that copies
  only the main camera's rotation, drawn before the system with depth off. So
  it stays at infinity at every zoom and never touches the logarithmic depth
  buffer.
- **The Plotly viewer has no sky**, and neither does `--output png`.
