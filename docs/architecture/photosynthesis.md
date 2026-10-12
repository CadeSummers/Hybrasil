# Photosynthesis limits

One ring per Earth photosynthesiser around every luminous star, where that
star's light falls to the organism's **growth limit**: its compensation point,
the least light that still gives net growth. A three.js feature, off by
default, under **Even more features ▾ → Photosynthesis limits**.

## Where the numbers come from

The workbook's **Photosynthesis limits** tab, built by
`data/photosynthesis/build.py` on 2 October 2026 from literature research. It
gives each organism three levels in PAR photons (400–700 nm, µmol m⁻² s⁻¹):

- optimal (light saturation);
- growth limit (drawn);
- survival limit (the least light it has been found to persist under).

Each level carries its paper, page or figure, conditions and confidence. A
level no source gives is blank and grey. Its SCOPE AND METHOD block holds the
rules below. Sources & Provenance and Legend & Notes carry the methods and the
check of the draft table the tab was started from.

`hybrasil/data/photosynthesis_limits.py` copies the PAR numbers as literal
rows (the Castor pattern), so the rings need no Google credential.
`tests/test_photosynthesis.py::TestTheRowsAreTheWorkbooks` checks them against
the newest snapshot. **Change the sheet, then the rows.**

**Scope rule (the owner's).** Only organisms whose *primary* way of gaining
energy is photosynthesis from *starlight*. These are left out:

- life on geothermal light: GSB1 at a hydrothermal vent;
- life that also fixes carbon in the dark: purple sulfur bacteria;
- mixotrophs, photoheterotrophs and photosynthetic symbioses.

Two kept rows carry a published doubt and are flagged in the tab's Notes: sea-ice
algae and deep coralline red algae.

## The distance

`hybrasil/mechanics/photosynthesis.py`, pure math:

    d = sqrt(L × k(Teff) / f)  AU

- `f` is the threshold over Earth's full-sun PAR, 2000 µmol m⁻² s⁻¹ (Taiz &
  Zeiger 2010).
- `k` is `par_photon_factor(teff)`: the PAR photons a blackbody at Teff emits
  per watt, over the same at 5772 K. It is exactly 1 for the Sun and for an
  unknown Teff, as `stellar_colour.colour_factor` is.
  - Proxima: 0.234. TRAPPIST-1: 0.105. A peak of about 1.05 near 6900 K.
  - **WEAK for M dwarfs**: their molecular bands remove visible light that a
    blackbody keeps.

- **The thresholds were measured under Earth's air and water**, so a distance
  assumes starlight is thinned the same way.
- `total_energy_distance_au` is the same distance without the colour term,
  `sqrt(L / f)`. The workbook records it for comparison; it is not drawn.
- Unlike the band equation, nothing here is recomputed in the browser, so there
  is no JS copy to keep in step.

## Into the viewer

`viz/photosynthesis_rings.py`, called from `figures.build_figure()` for both
modes, so the CLI and the web app cannot differ:

- **The rings ride on `layout.meta.photosynthesis_rings`, not as Plotly traces.**
  Nothing about the trace list changes, so no frame index can move. This is the
  hazard of CLAUDE.md's band rule. The Plotly viewer ignores the meta.
- **Plane:** a ring lies in its star's solvent-band plane, else in the star's
  planets' mean plane.
- **Centre:** the star's position at `t_start`.
- **Which stars:** one stack per star with a luminosity, so Alpha Centauri has
  three.
- **Names:** a ring's name carries the star only where more than one star has
  rings, as a band's does.
- **The optional set:** `optional_sets` gains
  `{key: "photosynthesis", menu: "features", default: false}`.

`three_viewer.figure_to_scene` turns each spec into a 361-point closed scene line
with these fields:

| Field | Value | Effect |
|---|---|---|
| `optional` | `"photosynthesis"` | shown only while the set is on |
| `owner` | its star | hides with the star |
| `follows` | its star | moves with it, as a moon's orbit moves with its planet |
| `group` | the organism | one legend row per organism, under the heading "Photosynthesis limits" |
| width | 1 | a plain `THREE.Line` (three-renderer rule 4) |

The colour is graded yellow → violet outward.

Rings never widen the scene (the owner's choice): the outer ones show on
zooming out.

## Tests

- `tests/test_photosynthesis.py`:
  - the factor and the distances;
  - the rows against the snapshot;
  - each ring is a closed circle of the right radius, planar about its own star
    and in its band plane;
  - no Plotly trace is added;
  - the scene's optional set and lines.
- `tests/test_browser.py::test_three_photosynthesis_rings_are_a_menu_feature_off_by_default`:
  the menu, the per-organism legend rows, persistence across a switch, and no
  menu in Nearby Stellar Motion.
- `tests/test_browser.py::test_three_bands_are_still_flat_with_the_rings_on`:
  the standing band rule with the rings on.

## Reference orbits, the menu's other entries

Added 10 Oct 2026: **Neptune reference orbit**, **Earth reference orbit** and
**Mercury reference orbit**, three more toggles in **Even more features ▾**,
each off by default. `viz/reference_orbits.py` is built on the same pattern as
the rings and is called beside them from `figures.build_figure()`:

- **What:** a dashed circle at the planet's semi-major axis, in the planet's
  colour. The radius and colour are the built-in Solar System's own J2000
  values (`reference_planets()`), so the reference and the real orbit agree.
- **Round which stars:** every `star` body, luminous or not. Alpha Centauri gets
  each ring three times, a hierarchy round each member, and the Sgr A* Cluster
  round the black hole and every S-star. A barycentre gets none.
- **Plane, centre, motion:** as a photosynthesis ring: the star's band plane
  (`photosynthesis_rings.star_normal`), its position at `t_start`, and
  `owner`/`follows` its star.
- **Meta and sets:** `layout.meta.reference_orbits`, and one optional set per
  planet, `reference-neptune`, `reference-earth` and `reference-mercury`. No
  Plotly trace is added.
- **Legend:** one row per planet ("Earth's orbit (1.00 AU)") under the set's
  heading, toggling that ring round every star.
- **Zoom:** each line carries a `reach` (radius plus its centre's distance from
  the origin). While one is shown, the viewer's `zoomLimit()` lets the camera
  go out to six reaches, so Neptune's 30 AU ring round TRAPPIST-1 can be seen.
  Without one, the limit is the usual sixty half-widths.

Tests: `tests/test_reference_orbits.py`;
`tests/test_browser.py::test_three_reference_orbits_ring_every_star_from_the_features_menu`
and `::test_three_bands_are_still_flat_with_the_reference_orbits_on` (the
standing band rule).
