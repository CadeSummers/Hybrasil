# plan.md

Design rules that are not yet fully implemented, kept here so the shape of the
work is settled before anyone writes it. Rules that *are* implemented live in
`CLAUDE.md`; when one of these lands, move it there.

## Orbital inclination and the plane a solvent band lies in

The target case is a multi-star system where each star carries its own
planetary system at its own mean inclination — star A's planets averaging 20°,
star B's averaging 80° — and each star's bands lie flat in *that star's*
plane. Everything below follows from that.

### The invariant

**A solvent band lies in the plane of the planets that orbit its own star, and
is centred on that star.** A band is derived from one star's luminosity, so it
is a statement about that star's system and nothing else. Two stars in one
figure with different planetary inclinations therefore carry two band stacks at
two different angles, and that is correct rather than a rendering fault.

Everything else here is a consequence of holding that invariant.

### Rule 1 — one band set per luminous star, not one per system

Every body with a `luminosity_sun` gets its own call to `SolventChoice.zones()`
with its own name as `host`. A system with three luminous stars builds three
band stacks.

Today every data source calls `zones()` exactly once, for the primary, so
Alpha Centauri B and Proxima Centauri each get nothing despite being stars with
luminosities in the figure — and Proxima has three planets of its own. That is
the first thing to fix, and the per-host plumbing already exists:
`zones(luminosity, bodies, host)` filters children by `b.parent == host`.

### Rule 2 — the plane comes from a star's planets, never from its stellar companions

`mean_orbital_plane` weights a host's children by `mass × √a`. A companion star
outweighs any planet by three or four orders of magnitude, so a host with both
returns the *binary* plane and the planets have no say in it. Alpha Centauri A
reports 79.20°, which is Alpha Centauri B's orbit, not a planetary inclination.

So the weighted average that sets a band's plane must consider only the host's
**non-stellar** children. Where a star has no planets of its own, it has no
planetary plane; see Rule 7 for what it gets instead.

This does not change which bodies define the *system's* plane for any other
purpose — it is specifically the band's plane that must ignore companions.

### Rule 3 — a band is centred on its star, not on the origin

`BeltZone` carries `normal` and `offset_au` but no centre, and `_belt_trace()`
builds its ring around `(0, 0, 0)`. A band belonging to a star that is itself
in orbit — Alpha Centauri B at 23 AU, Proxima at 8,700 AU — would be drawn
around the primary instead of around its own star, at radii measured from a
star it does not belong to.

`BeltZone` therefore needs a centre, and the things that read a band's geometry
have to follow it:

- `_belt_trace()` adds the centre to every ring vertex.
- `belt_scene_extent()` claims `|centre| + scene_claim_au`, not the radius alone.
- The viewer's `_recomputeBands()` carries the centre in `meta` alongside
  `solvent`, `lum`, `normal` and `ceiling`, since the pressure and albedo
  sliders rebuild each ring in the browser from what its own trace holds.
- `stack_offsets_au()` ranks bands **within one star**, not across the figure.
  Ranking globally would lift one star's bands by another star's radii.

A star that is itself in orbit moves, and its band moves with it. The band is
built at the star's position at `t_start`, the same convention a moon's ellipse
already uses, and the trace name should say so where the motion is large
enough to matter.

### Rule 4 — bands are never flattened onto z = 0 by default

Drawing every band on the reference plane would make each one a disc from the
default camera with no other work, and it is the wrong trade. It throws away
the per-star inclination this whole section exists to represent, and in an
edge-on system it puts the band at right angles to the orbits it describes.

`--band-plane reference` stays available as an explicit opt-in, and stays out
of the default path.

### Rule 5 — the camera orients to one chosen star's plane

With A's planets at 20° and B's at 80°, no single camera is face-on to both.
A view can only ever frame one plane at a time, so orientation is a per-star
action rather than a global one:

- **Orient** targets a star's plane: the eye goes along that star's band
  normal, centred on that star.
- With one luminous star, or several sharing a plane, this is the current
  behaviour and nothing visibly changes.
- The Solar System's plane is 1.58° off z, so it keeps the view it has now.

The default camera keeps its oblique three-quarter angle, but measured against
the target star's normal rather than against world z — otherwise a system whose
angles are measured from the plane of the sky opens edge-on. That is why
TRAPPIST-1 (89.76°) and Alpha Centauri A (79.20°) currently draw their bands as
lines: the geometry is right and the camera is looking along the plane.

### Rule 6 — which plane z is depends on where the angles came from

Only the Solar System is quoted in the ecliptic. Angles from transits or
astrometry are measured **from the plane of the sky**, and a transiting system
has i ≈ 90° by construction. A band at 89.76° is not an error to correct; it
is the system being edge-on to us, and the fix belongs in the camera, never in
the geometry.

When a system mixes sources — angles from a paper, star from the workbook — the
frame each figure is in has to be stated in `StarSystem.description`, as it is
now.

### Rule 7 — a star with no planets of its own still gets a band

Its luminosity is known, so where its solvents are liquid is known, and that is
the whole content of a band. With no planets there is no planetary plane to
derive, so it falls back in this order:

1. the mean plane of the host's other planet-bearing stars, if the system has one;
2. the reference plane.

A fallback plane is a guess about orientation, not about radius, and the
`StarSystem.description` says which of the two it used — the same way a
co-planar catalog system already declares that its angles are zeros.

### Rule 8 — hypothetical bodies do not define a plane

Unchanged from the existing rule, restated because it interacts with Rule 2:
confirmed children set the plane, and only a host whose children are *all*
unconfirmed falls back to using them. Applying Rule 2 first and Rule 8 second
matters — a host whose only confirmed child is a companion star must not fall
through to weighting hypothetical planets against it.

### Rule 9 — the scene frames the whole system, hypothetical outliers included

A scene is sized so the viewer can see the entire system at its true scale,
and a hypothetical body counts. Planet Nine at 700 AU sizes the Solar System's
box; Proxima's estimated 8,700 AU orbit sizes Alpha Centauri's. That is the
intended behaviour and is not to be "fixed" by dropping outliers from the
extent calculation — being able to take in the whole scale at once is the
point, and the zoom controls are how a viewer gets down to a band.

The consequence is accepted deliberately: in Alpha Centauri a band around A is
roughly 8/100,000 of the opening frame, and the viewer zooms to reach it. Rule
5's per-star Orient is what makes that a short trip rather than a hunt.

One thing that is *not* covered by this rule and is a plain bug:
`compute_scene_extent` floors every half-extent at `max(1.0, min_extent_au)`,
so any system smaller than 1 AU is inflated to fill a box nothing in it comes
near — TRAPPIST-1 spans 0.068 AU and is drawn in a 1.1 AU box. That floor
exists so a star-only system with no orbits still renders, and it should apply
only in that case, never as a floor on a system that has orbits to measure.
Removing it takes nothing out of frame.

### What each rule needs, shortest path first

| Rule | Touches |
|---|---|
| 1 | every `bands.zones()` call site in `data/` |
| 2 | `mean_orbital_plane` in `mechanics/orientation.py` |
| 3 | `BeltZone`, `_belt_trace`, `belt_scene_extent`, `band_meta`, `stack_offsets_au`, `_recomputeBands` in `_ZOOM_JS` |
| 4 | nothing — this is a rule about what not to do |
| 5 | `make_scene_style`, `viewFromAbove` and the switcher's per-system constants in `viz/export.py` |
| 6 | descriptions only |
| 7 | `SolventChoice.plane` |
| 8 | `mean_orbital_plane` |
| 9 | `compute_scene_extent` — the 1 AU floor only |

Rules 1 and 2 are independent of the rest and change what is drawn immediately.
Rule 3 is the largest, because a band's centre reaches the viewer's slider code.
Rule 5 is what makes any of it legible.

### Two things to keep right while doing this

- **The set of band traces must stay identical at every slider position.** The
  viewer rewrites rings in place as pressure and albedo move, and the animation
  writes marker traces by index; a band that appeared or disappeared would shift
  every index after it. `solvent_zones()` returns one zone per solvent asked
  for, always, including an empty one. Per-star bands multiply the count but
  must not make it variable.
- **The two implementations of the band equation must stay in step.** It lives
  in `mechanics/solvent_bands.py` and again in `_ZOOM_JS`, and
  `tests/test_band_sliders.py::TestTheTwoImplementationsAgree` is the only thing
  holding them together. Anything added to a band's geometry — a centre above
  all — has to be added to both sides.

## Tasks

Ordered so that each one leaves the figure correct. T2 depends on T3a — see
the note on that pair before reordering them.

**Status: T1-T5 are done** (2026-09-19). Rules 1, 2, 3, 5 and 9 now hold in
the code, and their prose lives in `CLAUDE.md`; what is left here is T6 and T7.

### T1 — a band's plane ignores stellar companions  *(Rule 2)*  ✅ done

`mean_orbital_plane` weights a host's children by `mass × √a`, so a companion
star outweighs any planet by three or four orders of magnitude and returns the
binary plane. Restrict the average to the host's **non-stellar** children.

`SolventChoice.plane()` is the only production caller, so the blast radius is
the band plane and nothing else. Alpha Centauri A's band moves from 79.20°
(which is Alpha Centauri B's orbit) to its planetary fallback.

- `mechanics/orientation.py`
- Test: a host with a massive companion and one light planet takes the
  planet's plane.

### T2 — one band set per luminous star  *(Rule 1)*  ✅ done

Every body with a `luminosity_sun` gets its own `zones()` call with its own
name as `host`. The per-host plumbing already exists and is unused: every data
source calls `zones()` once, for the primary.

**Do not land this before T3a.** A band is built around the origin, so a band
belonging to a star that is itself in orbit would be drawn around the primary
at radii measured from the wrong star — three overlapping stacks piled on
Alpha Centauri A. T2 without a centre is a worse figure than no T2 at all.

Band names need their star once a figure holds more than one set, since the
legend and the search box both read the name.

- `data/builtin_systems.py` (5 builders), `data/catalog_loader.py`
- Test: Alpha Centauri builds three band stacks; Proxima's sits on Proxima.

### T3 — a band is centred on its own star  *(Rule 3)*  ✅ done

**T3a — the centre reaches the geometry.** `BeltZone` carries the *name* of the
star it rings rather than a position, because a star that is in orbit has no
fixed one and the data layer has no time to evaluate it at. The figure builders
already hold every body's position at `t_start` and resolve the name there,
which is the convention a moon's ellipse already uses.

- `models/system.py` (`BeltZone.centre_body`), `viz/static_plot.py`
  (`_belt_trace`, `belt_scene_extent`), `viz/animation.py`
- `belt_scene_extent` claims `|centre| + scene_claim_au`, so a band around a
  distant companion does not fall outside the box.

**T3b — the viewer's sliders keep the centre.** `band_meta` carries it and
`_recomputeBands` in `_ZOOM_JS` rebuilds around it. Without this a band snaps
back to the origin the first time anyone touches pressure or albedo.

**T3c — stacking offsets rank within one star.** `solvent_zones` is already
called once per star, so its offsets are per-star by construction; confirm it
and pin it with a test rather than assume it.

### T4 — Orient targets a star's plane  *(Rule 5)*  ✅ done (primary's plane)

The eye goes along the chosen star's band normal, centred on that star; the
default camera keeps its oblique angle but measured against that normal instead
of world z. With one luminous star, or several sharing a plane, nothing visibly
changes, and the Solar System's 1.58° keeps the view it has now.

This is what makes T2 and T3 legible: with A's planets at 20° and B's at 80°
no single camera is face-on to both, so orientation has to be per-star.

- `viz/themes.py` (`make_scene_style`), `viz/export.py` (`viewFromAbove`,
  `_build_scene_ranges_js` and the switcher's per-system constants)

### T5 — the 1 AU scene floor applies only to a system with no orbits  *(Rule 9)*  ✅ done

`compute_scene_extent` floors every half-extent at 1 AU, inflating TRAPPIST-1's
0.068 AU system into a 1.1 AU box. Keep the floor for a system that has nothing
to measure; drop it for one that does. Hypothetical outliers keep sizing the
scene — that is Rule 9 and is deliberate.

- `mechanics/time_series.py`
- Test: TRAPPIST-1's extent comes from its outermost planet, and a star-only
  system still renders.

### T6 — a star with no planets falls back for its plane  *(Rule 7)*

In order: the mean plane of the system's other planet-bearing stars, then the
reference plane. T1 creates this case — Alpha Centauri A has no confirmed
planets once its companion is excluded — so T6 is what stops the fallback being
an accident of Rule 8.

- `mechanics/solvent_bands.py` (`SolventChoice.plane`)

### T7 — descriptions say which plane and which frame  *(Rules 6, 7)*

`plane_note` speaks of "the system's confirmed bodies" and one plane. With a
band stack per star it has to name the star, and say when a plane was fallen
back to rather than measured. Alpha Centauri's description still claims the
band is drawn "for Alpha Centauri A only, since a band is a ring around the
star at the origin" — untrue after T2 and T3.

- `mechanics/solvent_bands.py`, `data/builtin_systems.py`


## Done so far

**T1, T2, T3 — 2026-09-19.** A band is now one star's statement: built for
every luminous star, in the plane of *that star's* planets with stellar
companions excluded, centred on that star at `t_start`, stacked against its own
siblings only, and named with its star wherever a figure holds more than one
set. Alpha Centauri went from one band to three stacks of eight.

Two things turned up while doing it and are worth remembering:

- **The offset was applied along the raw stored normal in Python and along the
  normalised one in the viewer.** `offset_au` is a distance in AU, which it
  only is if what it multiplies has length 1. Every stored normal happens to be
  a unit vector, so nothing was visibly wrong, but it was the one place the two
  implementations could disagree. Python normalises now, and
  `TestTheRingGeometryAgrees` compares the two ring builders directly rather
  than only the equation behind them.
- **`_stackOffsets` ranked across the whole figure.** Harmless with one star;
  with three it would lift one star's bands by another star's radii, which at
  Alpha Centauri's scales pushes a band clear of the star it belongs to. The
  viewer groups by centre now, which is what Python gets for free by building
  one stack per call.


**T4, T5 - 2026-09-19.** The camera now follows the band plane, and the scene
floor no longer inflates a compact system. TRAPPIST-1's bands went from eight
lines in a box sixteen times too big to a disc filling the frame.

T4 landed as the *primary's* plane rather than a per-star choice. That is the
whole of Rule 5 for every system that exists today, since no built-in has two
band-bearing stars whose planes differ - Alpha Centauri's three are all flat.
The per-star target becomes real the day a system has an A at 20 degrees and a
B at 80, and the hook for it is `system_view_normal`, which picks the first
band; pointing it at a chosen star is the remaining work.

One more bug fell out of it: **Orient's eye sat at a fixed 100 AU**, which is a
distance only meaningful for a system about 100 AU across. It put the Solar
System's camera practically inside the Sun and TRAPPIST-1's 1,460 normalised
units away, which is what collapsed the scene to a dot the first time Orient
was pressed on a compact system. The scene is a cube whatever it holds, so the
distance belongs in normalised units.
