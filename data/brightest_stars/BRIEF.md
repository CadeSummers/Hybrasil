# Brief: physical data for the 100 brightest stars

You are a research agent. Your batch is one file of 25 stars, `research/in_qN.json`; write your
answers to `research/qN.json` in the same directory. Each input record is one naked-eye point
of light with its rank, designation, IAU name, HIP number(s), SIMBAD spectral type and
Hipparcos distance. The list and its astrometry are settled: do not change them.

Save your output file after every five stars. If it already exists, keep what is in it and
carry on with the stars it lacks.

## What to find, per star

"The star" is the brightest star of the point (Sirius A, Capella Aa, Antares A).

| Key | Meaning |
|---|---|
| `mass_msun` | Mass of the star, solar masses |
| `luminosity_lsun` | Bolometric luminosity of the star, solar luminosities |
| `system_luminosity_lsun` | Bolometric luminosity of every star in the point added together, only where a companion adds more than 5% (alf Cen, Capella, Castor, Acrux, Spica, Mizar, Algieba) |
| `teff_k` | Effective temperature of the star |
| `radius_rsun` | Radius of the star |
| `age_gyr` | Age in Gyr (0.012 for 12 Myr) |
| `feh` | Metallicity [Fe/H], dex |
| `n_stars` | Number of stars in the gravitationally bound system, counting spectroscopic companions. A brown dwarf is not a star. Optical (line-of-sight) companions do not count |
| `components` | List of strings `"name: class (role)"`, one per star, brightest first, e.g. `"alf CMa A: A1 V (primary)"`, `"alf CMa B: DA2 (white dwarf companion)"` |
| `variable_type` | Variability class (GCVS/AAVSO style: `SRc`, `Algol (EA)`, `bet Cep`, `del Sct`, `alf Cyg`, `gam Cas`, `Cepheid`), or `"not variable"` |
| `v_range` | The V range as a string, `"0.0 to 1.6"`, variables only |
| `distance_ly`, `distance_err_ly` | ONLY where a published distance is better than the Hipparcos value in the input (a far supergiant whose parallax error is large, a dynamical or cluster distance, an interferometric orbit). Otherwise null |
| `av_mag` | Visual extinction A_V toward the star, magnitudes. 0 is a fine answer for a star within about 100 ly if a source says so; null if you find nothing |
| `nicknames` | List of common names NOT the IAU name already in the input: traditional names, variant spellings in real use, and the full Bayer name ("Alpha Canis Majoris") |
| `notes` | Anything a reader of the table must know, one or two sentences |

Every key except `components`, `nicknames` and `notes` is an object:

```json
"mass_msun": {"value": 2.063, "source": "Bond et al. 2017, ApJ 840, 70", "url": "https://doi.org/10.3847/1538-4357/aa6af8", "wikipedia": false}
```

`components` and `nicknames` are `{"value": [...], "source": "...", "url": "...", "wikipedia": false}`.

## Rules

1. **Never guess.** A value you could not source is `null`. A null is a good answer; an
   invented number is the one thing that makes the batch worthless.
2. **Cite the paper or catalogue the number is printed in**, with author, year, journal,
   volume, page, and a DOI or ADS link. Prefer a dedicated study of the star (interferometry,
   asteroseismology, an orbit) over a large survey, and a recent one over an old one.
3. **Wikipedia may point you to the paper, but read the number from the paper.** Only if you
   cannot reach the paper may you take the number from Wikipedia; then set `"wikipedia": true`,
   put the Wikipedia article URL in `url`, and put the citation Wikipedia gives in `source`.
   The owner marks these cells differently, so this flag must be honest.
4. **Do not compute values yourself**, except unit conversions (pc to ly x 3.261563777, Myr to
   Gyr, log L to L). If you converted, say so in `source` ("log L = 4.90").
5. Values as published, not rounded further. One value per key: where papers disagree, take the
   best-founded recent one and name the other in `notes`.
6. Web requests carry no names or project details: search for the star and the quantity only.
7. Do not write anywhere except your output file. Do not touch the workbook, git, or other files.

## Output

A JSON list, one object per star, in rank order:

```json
[{"rank": 1, "name": "alf CMa", "mass_msun": {...}, "luminosity_lsun": {...}, "system_luminosity_lsun": null,
  "teff_k": {...}, "radius_rsun": {...}, "age_gyr": {...}, "feh": {...}, "n_stars": {...},
  "components": {...}, "variable_type": {...}, "v_range": null, "distance_ly": null, "distance_err_ly": null,
  "av_mag": {...}, "nicknames": {...}, "notes": "..."}]
```

Finish by replying with: how many stars are complete, how many values are null (by key), how
many are flagged `wikipedia: true`, and any star where sources disagree badly.
