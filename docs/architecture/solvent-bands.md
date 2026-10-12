# Solvent bands — physics, pressure/albedo, band plane

> Moved verbatim out of `CLAUDE.md` so it loads on demand. `CLAUDE.md` links here.

## Solvent bands — how they work

A solvent band is the ring of orbital distances where a solvent stays liquid,
given the host star's luminosity. All eight of the workbook's solvents are
wired up — methane, ethane, ammonia, water, formamide, sulfuric acid, sulfur
and carbon dioxide — at the workbook's seven pressures. All of them at 1 bar
is the default: a band is built hidden, so having every solvent in the legend
costs nothing on screen, and `--solvent` narrows what goes in the legend
rather than deciding what is drawn. The exception is a still image, which has
no button — `save_png()` switches every band it was given back on, so
`--solvent` is what narrows a PNG.

`--solvent` takes a comma-separated list or `all`; `--pressure` and
`--albedo` say where the viewer's two sliders *start*, and take any value in
0.1–100 bar and 0.01–0.99; `--list-solvents` prints which solvent has a band
at which of the workbook's columns. A `SolventChoice` carries the settings
from the CLI down through `get_system()` to every star; built-in systems are
cached by `(system, choice.cache_key)`, since the same system with different
bands is a different figure.

Blackbody equilibrium temperature, inverted for distance:

```
d_AU = T_EQ_1AU_K^2 * sqrt(L/L_sun) * sqrt(1 - A) / T^2
```

**The band is per system, never a fixed ring.** It scales as `sqrt(L)`, so the
Sun's water band is 0.56–0.87 AU and TRAPPIST-1's is 0.013–0.020 AU. Any code
path that hardcodes an AU figure here is wrong.

**The band is per *star*, not per system.** `SolventChoice.zones_for_system()`
builds one stack for every body with a `luminosity_sun`, each centred on that
star and in the plane of that star's own planets — so Alpha Centauri carries
three stacks of eight rather than one. That is the call every data source
makes; `zones()` builds a single star's stack and is what it calls per star.
Building only the primary's is how Alpha Centauri B and Proxima came to have
no band at all, Proxima despite having three planets of its own.

Four things follow, each a bug if dropped:

1. **A band is centred on its star, not on the origin.** `BeltZone.centre_body`
   names it and the figure builders resolve it against their `t_start`
   positions. Without it a companion's band is drawn around the primary, at
   radii measured from a star it does not belong to.
2. **`belt_scene_extent()` claims the star's distance plus the band's radius.**
   Proxima's band is 0.03 AU across and sits 8,700 AU out; the radius alone
   would leave it outside the box entirely.
3. **Stacking is per star.** Offsets exist so overlapping bands do not z-fight,
   and only bands around the same star can overlap. Python gets this free by
   building one stack per call; the viewer's `_stackOffsetsByStar` groups by
   `meta.centre` to match, because there every band arrives in one array.
4. **The star is in the legend name only where there are several.** The search
   box reads these names, so a single-star system's legend is byte-identical to
   what it always was. `_bandName` in `_ZOOM_JS` rebuilds the whole string as
   the pressure slider moves, so it has to rebuild the star too or a drag
   would quietly strip it off.

**A pressure with no liquid phase is a result, not a gap.** Methane below its
0.117 bar triple point, ethane above its 48.7 bar critical pressure and CO2
below 5.185 bar have no band at any distance from any star. Those pressures
are left out of `phase_points` and carry their reason in `absent`, which
`solvent_notes()` prints — a missing CO2 band at 1 bar is the answer, so it
says so rather than dropping the solvent silently.

## Pressure and albedo are sliders

Both were fixed numbers baked into the figure and are now dragged in the
viewer, which rebuilds every band as they move. See "Recomputing a band in the
browser" in `viewer-bands.md` for the viewer half.

**Pressure is interpolated between the workbook's seven columns, and never
past a solvent's own range.** `interpolated_liquid_range_k()` does it in the
form each curve actually takes:

- **Boiling point: 1/T linear in ln P**, which is Clausius–Clapeyron. The
  straight-line-in-T alternative puts water's 2 bar boiling point at 122.1 °C
  against a true 120.2; this gives 120.4.
- **Melting point: T linear in ln P.** Melting follows the Clapeyron equation
  rather than Clausius–Clapeyron, but these move so little — water's falls
  0.8 °C across all three decades, sulfur's not at all — that the simple form
  is inside a rounding error of anything fancier.

Outside a solvent's transcribed range there is **no band**, because that is
the line between interpolating and inventing: methane is transcribed 0.5–10
bar, and running a vapour-pressure curve past its last point is how you draw
a band where the substance is not liquid at all.
`interpolation_absent_reason()` gives the workbook's own reason for the
nearest column it left empty. The slider's ends are the workbook's ends —
0.1 and 100 bar — so the whole track is interpolation.

**One albedo gives one ring.** `solvent_band_at_albedo()` returns a single
annulus: inner edge from the boiling point, outer from the melting point.

The nested **conservative/optimistic** pair the workbook's "Orbital Bands" tab
defines is the same calculation run over an albedo *bracket*, A = 0.0 to 0.3,
because albedo is unknown for an arbitrary planet — conservative is liquid at
every albedo in the range, optimistic at some. With a slider setting albedo
there is nothing left to bracket, so that is not what is drawn any more.
`solvent_band_au()` still computes it and `tests/test_solvent_catalog.py`
still reproduces every workbook cell from it, including the two whose
conservative band inverts; the two functions agree edge for edge at the
bracket albedos, which `test_the_edges_are_the_bracket_edges_at_the_same_albedos`
pins.

## The greenhouse effect is a slider (beta)

**A flat offset in kelvin, added to the blackbody temperature.** The surface is
liquid where `T_eq + G` sits between the melting and boiling points, so each
edge is the distance at which `T_eq` is that point *minus* `G`:

```
d_AU = T_EQ_1AU_K^2 * sqrt(L/L_sun) * sqrt(1 - A) / (T - G)^2
```

The viewer's "Greenhouse effect (beta)" slider runs 0–1000 K and `--greenhouse`
says where it starts. The default, `DEFAULT_GREENHOUSE_K = 33`, is Earth's:
this code's own constants put Earth's `T_eq` at 254.6 K for A = 0.3, and 33 K
lands it within half a degree of its 288 K mean surface. It is "beta" because a
real greenhouse scales with the atmosphere and the flux it traps; a constant is
a first-order stand-in.

Four things follow, each a bug if dropped:

1. **The mechanics default to no offset; `SolventChoice` defaults to Earth's.**
   `solvent_band_at_albedo()` and the rest take `greenhouse_k=0.0`, which is
   the band the workbook computes and what every workbook-reproducing test
   pins. A figure opens at 33 K because `SolventChoice.greenhouse_k` does, so
   every default figure's bands sit further out than the workbook's — the Sun's
   water band is 0.56–1.12 AU rather than 0.47–0.87.
2. **Past the boiling point there is no band; past the melting point there is
   no cold edge.** An offset at or above `T_boil` boils the solvent at every
   distance, and `band_absent_reason()` says so in the description. One at or
   above `T_melt` means it never freezes however far out, so the cold edge is
   drawn where `T_eq` falls to `T_CMB_K` (2.725 K) — about 8,700 AU around the
   Sun at A = 0.3 — rather than at infinity, which would reach Plotly as null.
3. **The stacking lift is capped at `_STACK_SPAN_CAP` (10) inner radii.** The
   lift scales with the outer radius, and a band run out to the CMB distance
   would otherwise float its inner edge ~130 AU off its own plane. No band at
   the default offset spans more than ~7 inner radii, so the cap changes
   nothing about the default stack. `_stackOffsets` in the viewer applies the
   same cap, and `TestTheTwoImplementationsAgree::test_the_stacking_lift_agrees`
   compares them.
4. **The scene is sized for the offset the slider starts at, not its top.**
   At 1000 K every surviving band runs to the CMB distance, and a scene sized
   for that at every start would shrink a system's planets to a pixel. So
   dragging greenhouse up is the one slider move that can push a band past the
   edge of the scene; the clipper cuts it at the box like any other trace.

## Star colour scales every band (Kopparapu runaway ratio)

**A solvent band and a habitable zone are different calculations.** The band
is blackbody energy balance plus a flat greenhouse offset, and luminosity is
its only stellar input:

```
d = T_EQ_1AU_K^2 * sqrt(L) * sqrt(f * (1 - A)) / (T - G)^2
```

A habitable zone (Kopparapu et al. 2013) is a climate model's answer written
as an effective flux, `d = sqrt(L / S_eff(Teff))`, and the `Teff` in it is the
star's colour: a redder spectrum is Rayleigh-scattered less and absorbed more
in the near-IR, so a planet's albedo is lower and less flux gives the same
climate. `f` above is that effect, and nothing else, brought into the band:

```
f(Teff) = S_eff,RG(5772 K) / S_eff,RG(Teff)
S_eff,RG = 1.0512 + 1.3242e-4 t + 1.5418e-8 t^2 - 7.9895e-12 t^3 - 1.8328e-15 t^4,
           t = Teff - 5780 K
```

The coefficients are Kopparapu et al. 2013 (ApJ 765, 131) Table 3, "Runaway
Greenhouse", as printed in arXiv:1301.6674v2. They are the same fit the
workbook's HZ columns (Planets I:L) reproduce. `mechanics/stellar_colour.py`
holds them; nothing else does.

Five things follow, each a bug if dropped:

1. **The runaway limit only.** It is a thin, water-vapour atmosphere, the
   nearest of Kopparapu's limits to the fixed Earth-like atmosphere a band
   assumes. The maximum-greenhouse ratio would build a dense-CO2 atmosphere
   into every band.
2. **Normalised at `T_SUN_K`, not at Kopparapu's 5780 K**, so the Sun's factor
   is exactly 1 and the Solar System is byte-identical with the correction
   on or off. `TestTheBuiltInSystems::test_the_solar_system_does_not_move`
   pins it.
3. **Clamped to 2600-7200 K**, the fit's range. A quartic extrapolated turns
   over; TRAPPIST-1 (2516 K) is taken at 2600 K and its description says so.
   **No Teff means `f = 1`**, never a guess, and the description says "Teff
   unknown": 55 Cnc B is the live case.
4. **`f` multiplies absorbed flux, never a solvent's temperatures**, so every
   band around one star moves by the same `sqrt(f)` and no band appears or
   disappears because of it. The caveat is that the fit was made for
   water-vapour atmospheres, and applying it to a methane or sulfur band
   assumes the same scattering and absorption behaviour.
5. **Python computes `f` once per star and ships the number** in the band's
   `meta.colour`; `_bandRadiiAU` only multiplies `(1 - A)` by it. The fit
   cannot drift between the two implementations because it is not in the
   JavaScript at all. `test_stellar_colour.py::TestTheViewerGetsIt` compares
   the two band equations with `f` applied.

A star's `Teff` travels on `OrbitalBody.teff_k`: built-in systems set it
beside their `_L_*` constants (from the workbook, except Proxima's 2980 K,
Ribas et al. 2017, since written into the workbook too), the catalog loader
puts its already-read Teff on the body, and `SolventChoice.zones_for_system`
passes it on. `SolventChoice.star_colour` / `--star-colour off` switches the
correction off and is part of `cache_key`. The mechanics functions default
to `colour=1.0`, so every workbook-reproducing test is untouched, and the
workbook's own band columns stay pure blackbody on purpose.

**It does not make the band a habitable zone, and Proxima b shows it.** `f` is
1.215 at 2980 K, so bands move out by 1.102x: the water band at 1 bar,
A = 0.3, 33 K goes from 0.0218-0.0437 to 0.0241-0.0481 AU, and b at 0.04857 AU
is still 0.0004 AU outside, inside from a 34.05 K greenhouse.
`test_proxima_b_is_just_outside_at_earths_greenhouse` pins that margin. The
rest of the gap is the HZ's edges being set by climate feedbacks (runaway
water loss inside, CO2 build-up outside) that a constant offset cannot model.

**`solvent_zones()` returns exactly one zone per solvent asked for, always**,
including a solvent with no liquid phase at this pressure, which gets an empty
one. The viewer rewrites these rings in place as the sliders move, so the set
of traces has to be identical at every slider position — a band that appeared
and disappeared would shift every trace index after it, and the animation
writes marker traces by index.

**The scene is sized for the darkest albedo the slider allows, not for the
band being drawn.** A lower albedo pushes a band outward, so `BeltZone`
carries `scene_extent_au` (from `widest_band_outer_au()`, at A = 0.01)
separately from `r_outer_au`, and `belt_scene_extent()` reads
`scene_claim_au`. Without it, dragging albedo down grows a band straight out
of the scene box.

**Three solvents stop working before they boil**, and carry that as
`functional_ceiling_c`: sulfur's 159 °C lambda transition (viscosity rises
~10,000×, so it is tar above it), formamide's ~180 °C decomposition, sulfuric
acid's ~300 °C SO3 loss. The ceiling is applied by default — what is drawn is
where the substance is a *usable* liquid — and those bands are named
`… (1 bar, functional)`. `--band-limit thermodynamic` turns it off and gives
the figure the workbook prints outside its parentheses. It matters most for
sulfur: 0.15–0.43 AU thermodynamic against 0.415–0.430 AU functional, a band
0.015 AU wide that no solar system body sits in, and the same at every
pressure, because the lambda transition does not move while the boiling point
climbs.

**Overlapping bands are stacked.** Seven bands at 1 bar overlap heavily around
the Sun, and coplanar transparent meshes z-fight. `stack_offsets_au()` ranks
the bands by outer radius and lifts each by `rank × 0.005 ×` its own outer
radius *along the band's normal*, so every band is planar, no two share a
plane, and the lift stays invisible at the zoom where that band is on screen. A
single band gets 0.0 and sits exactly in its plane. Which plane that is comes
from "Which plane a band lies in" below.

Melting and boiling points are transcribed from the workbook's "Liquid Range
vs Pressure" tab at its seven pressures. `tests/test_solvent_bands.py`
reproduces all seven of the workbook's water columns to two decimals, which is
what pins the equation down; `tests/test_solvent_catalog.py` does the same for
every other row, thermodynamic and functional, including the two cells whose
conservative band inverts (ammonia at 0.1 bar, CO2 at 10 bar). Change a
constant and those tests fail.

Note that two entries in the workbook's own "Bodies in 1 bar Optimistic Band"
column contradict the AU figures on the same row: it lists Saturn (9.54 AU)
for methane, whose outer edge is 9.427 AU, and Mars (1.52 AU) for ethane,
whose inner edge is 1.903 AU. The AU figures are what this code reproduces;
`test_two_bodies_the_workbook_lists_are_actually_just_outside` records the
near misses.

Three things to know before touching this:

1. **The band is not drawn until it is asked for.** The figure opens on the
   orbits; each band has its own legend entry and the Bands button moves the
   whole set. That is why drawing all eight solvents by default costs nothing
   — and why `--solvent` is about what goes in the legend, not about what is
   on screen. `BeltZone.is_solvent_band` separates a derived band from an
   observed belt, which is always drawn. See "The solvent bands start off"
   above for the viewer half.
2. **The band is not a habitable zone.** Greenhouse warming is one flat
   offset (see above), and there is no tidal or internal heating, no
   day/night or seasonal swing, no eccentricity. Every generated
   `StarSystem.description` says so, and that sentence should survive any
   rewrite.
3. **A band claims room in the scene.** `compute_scene_extent()` takes
   `min_extent_au`, and both figure builders pass `belt_scene_extent(system)`.
   Without it a system whose only planets are close in would clip its band away
   entirely. Decorative belts leave `extends_scene` false, so `--bodies Earth`
   still does not zoom out to the Kuiper belt.

## Which plane a band lies in

A belt is drawn where it was measured — flat on the reference plane. A solvent
band is *derived*, so it belongs in the plane the system's bodies actually
orbit in, and `mechanics/orientation.py` works that plane out from the bodies
rather than storing it:

```
normal = normalise( sum over the host's children of  m_i * sqrt(a_i) * n_i )
```

which is the system's invariable plane, near enough. Results: the Solar System
1.58° (Jupiter sets it, and the band moves by less than 0.03 AU — invisible,
which is why nothing there had to change), TRAPPIST-1 89.76° (edge-on, as its
transits require), Proxima 0° (its catalog elements carry no angles at all),
and Alpha Centauri A 0° — it has no planets with measured angles, and its
companion is excluded by the rule below.

That average is for a star *with planets*. `band_plane()` is what a band
actually calls, and it ranks the sources:

1. the star's planets, confirmed first, then hypothetical (`mean_orbital_plane`);
2. with no planets at all, its binary partner (`partner_plane()`): the tightest
   of its own orbit about a parent star or barycentre and the orbits of the
   stars and barycentres hung off it, confirmed links first;
3. a single star with nothing orbiting it: the reference plane.

A candidate planet beats a known partner on purpose: a band is about where a
planet could hold a liquid, so even an unconfirmed planet says more about its
plane than a star does. That is why Alpha Centauri A stays at 0° (the disputed
Ab) while B, with no planets, takes its orbit about A at 79.20°. Castor's six
stars have only each other, so each band lies in its inner pair's orbit — Aa
and Ab 35°, Ba and Bb 110.5° (69.5° folded), Ca and Cb 86.29° — where they
were all flat before. The tightest link is the partner because in a hierarchy
the inner pair is the star's binary, not the wide orbit the pair makes about
the next one out. Photosynthesis rings with no band to copy use the same call.

Four rules for the planetary average, each of which is a bug if dropped:

1. **A companion star does not define a planetary plane.** The weights are
   `m * sqrt(a)`, so a companion outweighs any planet by three or four orders
   of magnitude and simply *is* the answer: Alpha Centauri A used to come back
   79.20°, which is Alpha Centauri B's orbit rather than an inclination any
   planet of A's has. Stellar children sit out, and
   `mean_orbital_plane(..., include_companions=True)` is how the binary plane
   is asked for on purpose. The exclusion happens *before* the confirmed-bodies
   rule, so a host whose only confirmed child is a companion falls back to its
   own unconfirmed planets rather than to the binary.
2. **Hypothetical bodies do not define a plane.** Planet Nine at 30°, Proxima's
   hypothetical 8,700 AU orbit and the disputed Alpha Cen Ab are placeholders.
   A system whose bodies are *all* unconfirmed falls back to using them, which
   is what a catalog system of candidates does.
3. **A body with no recorded mass sits the average out**, because unknown mass
   is unknown angular momentum. Pluto and Eris carry no mass in the built-in
   table, and counting them equally tilted the Solar System to 6.5° on two
   bodies holding a millionth of Jupiter's angular momentum. Only when *no*
   body has a mass does the average fall back to equal weights.
4. **The "these cancelled out" test is relative to the weights.** Two opposed
   orbits leave a residue of mass × floating-point epsilon — around 1e8 for a
   pair of Jupiters — so an absolute epsilon calls a cancelled sum a plane and
   returns garbage. `_normalise` takes the weight scale for this reason.

`orbital_normal()` is derived from the same Euler rotation `kepler.py` applies,
not assumed, and `tests/test_band_orientation.py` checks it against the cross
product of that rotation's own basis vectors — so an orbit's points and its
normal cannot drift apart.

The stacking offset runs along the **unit** normal, in both implementations:
`offset_au` is a distance in AU, which it only is if what it multiplies has
length 1. Every stored normal is a unit vector in practice, so this was
invisible — and was the one place the Python and JavaScript ring builders could
disagree. `tests/test_band_sliders.py::TestTheRingGeometryAgrees` compares the
two directly, centre included, rather than only the equation behind them.

`plane_basis()` returns the ring's 2-D basis with `u` along the line of nodes,
so a tilted ring is reproducible rather than arbitrarily rolled, and an
untilted one still starts at the x axis exactly as a belt always did. The
stacking offset from `stack_offsets_au()` runs along the normal, so it stays
perpendicular to a tilted band instead of shearing it.

`--band-plane reference` puts every band back on z = 0. It is part of
`SolventChoice.cache_key`, since a system drawn both ways is two figures.
