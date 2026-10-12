# Luminosity research brief (shared by every research agent)

We fill the blank `Luminosity (L-sun)` cells of stars in a nearby-star workbook. A star with no
luminosity draws no solvent band, so each value matters. You RESEARCH ONLY: you never write to the
Google Sheet or to the repository. Your output is one JSON file.

## Inputs
- `rows.txt` (this folder): the live workbook row for every star, with mass, class, Teff, the
  "Star data source" note, MSC label, WDS code, Gaia DR3 id, hierarchy and distance.
- `prior_lit.json` (this folder): what an earlier pass (29 Sep 2026) already found. Many evolved
  primaries were left blank because the only luminosity found was COMBINED LIGHT of an unresolved
  pair. Read those records for your stars first and do not redo them -- go further.

## What counts
Bolometric luminosity of THIS COMPONENT ALONE, in L_sun. In order of preference:
1. **published** -- a peer-reviewed paper or catalogue that prints L (or log L) for this component
   alone. Gaia DR3 `lum_flame` (I/355/paramp) and TIC v8.2 (IV/39/tic82) count as catalogues, but
   say which, and check the Gaia/TIC source really is this component and not a blend (RUWE, a
   companion inside ~1 arcsec, an SB2).
2. **wikipedia** -- a value read off a Wikipedia infobox. Record the page URL AND the reference
   Wikipedia cites for that exact number (paper + its URL/bibcode). Cross-check is mandatory:
   recompute L = R^2 (Teff/5772)^4 from the same infobox's R and Teff and report both; a cool dwarf
   infobox sometimes quotes a VISUAL luminosity, several times too small. If they disagree by more
   than ~30 %, say "fails cross-check".
3. **derivable** -- no L printed, but published inputs give one: R and Teff from the same source
   (L = R^2 (Teff/5772 K)^4); or a combined-light L split with a published flux ratio / delta-mag /
   companion luminosity; or M_bol from a published M_V/M_K and bolometric correction. Give every
   input with its own source, the formula, and the result. We will mark these ORANGE (inferred).
4. **none** -- nothing usable. Say what you checked and, if the object's nature is uncertain
   (white dwarf vs M dwarf vs brown dwarf), say what the literature says, because that decides
   which inference relation is even allowed.

Never recall a number from memory. Every number needs a fetched source: open the paper (arXiv,
ADS abstract page, journal HTML) or query VizieR, e.g.
`https://vizier.cds.unistra.fr/viz-bin/asu-tsv?-source=I/355/paramp&Source=<gaia_dr3_id>&-out=lum_flame,lum_flame_lower,lum_flame_upper,radius_flame,teff_gspphot`
or `https://vizier.cds.unistra.fr/viz-bin/asu-tsv?-source=IV/39/tic82&-c=<ra>+<dec>&-c.rs=5&-out.all`
(or the TAP endpoint). Quote the line or table row VERBATIM in `quote`.

Distance matters: L scales as d^2. If a source's L rests on a distance far from the workbook's
`Distance (ly)`, note it (and the factor) in `notes`.

## Output
Write a JSON list to the output file named in your task, one record per star, every star in your
list present:

```json
{
  "component": "exact name as in rows.txt",
  "outcome": "published | wikipedia | derivable | none",
  "luminosity_lsun": 0.0123,            // null for none
  "luminosity_range": [lo, hi],          // if the source gives errors, else null
  "applies_to_component_alone": true,
  "source": "Author et al. YEAR, Journal Vol, Page",
  "identifier": "bibcode / doi / VizieR table",
  "url": "https://...",
  "quote": "verbatim line or table row the number comes from",
  "radius_rsun": null, "teff_k": null,   // the values a cross-check or derivation used
  "derivation": "formula with every input and its source; null unless outcome is derivable",
  "wikipedia": {"page": "", "url": "", "cited_source": "", "cited_url": "", "cross_check": ""},
  "nature": "M dwarf | K dwarf | subgiant | giant | white dwarf | brown dwarf | unknown ...",
  "notes": "caveats: blends, distance used, disagreements between sources, alternatives found"
}
```

Report back in under 150 words: per star, the outcome and the value. The JSON is the deliverable.
