# Research brief: planet candidates within 100 ly

You are one of several research agents widening the **"Unconfirmed within 100 ly"**
tab of a private star-catalog spreadsheet (the `hybrasil` workbook behind the
hybrasil project). Your job is **research only**. You produce one JSON file.
A single writer (the orchestrating session) validates every agent's JSON and
makes all spreadsheet edits itself.

Pack directory (read-only inputs), referred to below as `PACK`:
`<scratchpad>\pack`

Output directory, referred to as `OUT`: the sibling `...\scratchpad\out`

## Hard rules

1. **Do not write to the Google Sheet, the repo, or anything outside `OUT`.**
   Do not import `hybrasil.data.google_sheets` and do not call
   `update_cells`, `set_border`, `rename_workbook` or any other write. Read-only
   web and TAP queries are fine.
2. **Never fabricate.** Every number needs a source you actually opened this
   session, with a locator: table, section or figure, or the query you ran.
   A value you remember but could not re-find goes in `considered_not_added`
   or in the system's coverage `notes`, marked "recalled, not verified". It
   never goes in a candidate record. If a claimed candidate cannot be traced
   to a publication or catalogue, report that plainly.
3. **Primary sources win.** Prefer the discovery paper or a catalogue, in this
   order: refereed paper or arXiv preprint > NASA Exoplanet Archive / ExoFOP /
   Gaia archive > exoplanet.eu / Open Exoplanet Catalogue > Wikipedia.
   Wikipedia is fine for **finding leads**. If a value can **only** be had from
   Wikipedia, record it under `wikipedia_values` with the Wikipedia URL **and**
   the source Wikipedia cites for that exact number, plus its URL. The writer
   gives such cells a pink border. For a stellar luminosity taken from
   Wikipedia, recompute L = R² (Teff/5772)⁴ from the same infobox and report
   whether the two agree. Infoboxes sometimes quote a *visual* luminosity.
4. **Don't derive, report inputs.** Do not compute semi-major axes, luminosities
   or HZ limits yourself for the record. Report the published values and the
   inputs a writer needs (stellar mass, radius, Teff, log g) with sources. The
   writer derives the rest by the sheet's own methods and marks those cells
   orange. Report a paper's own derived values (its a, its m sin i) as
   published values.
5. **The 100 ly cut is a parallax of at least 32.616 mas** (distance under
   30.66 pc). Use the Gaia DR3 parallax where there is one and name the
   parallax you used. Anything farther goes in `considered_not_added`.
6. Budget: be thorough but proportionate. Spend a few queries on an obscure
   M dwarf and more on a much-studied star with many names (tau Cet, eps Eri,
   GJ 581, Barnard's star, AU Mic...).

## What counts as a candidate (add it)

- TESS TOIs with TFOPWG disposition **PC** or **APC** (from the NASA TOI table;
  the pack holds today's pull). FP/FA are recorded but tiered `unlikely`, as
  the tab already does.
- Gaia astrometric candidates (the ESA "Gaia (candidate) exoplanet list",
  Gaia DR3 `nss_two_body_orbit` candidates named in papers, and later Gaia
  candidate papers).
- Radial-velocity, astrometric, TTV, imaging or other signals that a paper
  calls a **planet candidate**, "unconfirmed planet", "tentative", "possible
  planet" or "signal of possible planetary origin". The Tuomi et al. 2019 M-dwarf survey
  (arXiv:1906.04644), Feng et al. 2022 (ApJS 262, 21), the California Legacy
  Survey (Rosenthal et al. 2021) candidate lists, and CARMENES, HARPS, ESPRESSO,
  HIRES, HPF, MAROON-X and SPIRou papers are rich sources.
- Planets that were published but are **disputed**: a later paper argues
  activity or an alias. Examples are Proxima c and alpha Cen Ab. Tier them `ambiguous`.
- Anything exoplanet.eu lists as "Candidate", "Controversial" or "Unconfirmed",
  or the Open Exoplanet Catalogue lists as "Controversial", within 100 ly, that is
  not on the confirmed tab.
- Directly imaged point-source candidates that have not been confirmed as
  comoving or bound.

## What does not get added (record it in `considered_not_added`, with the reason and source)

- **Already on the sheet:** in `PACK/planets_confirmed.csv` (the confirmed
  tab, rows 2-540) or `PACK/unconfirmed_existing.csv`. Check **every alias**:
  GJ / Gl / HD / HIP / LHS / Ross / Wolf / TOI / TIC / Gaia designations, and
  Bayer and Flamsteed names. The sheet uses its own spellings, such as
  "GJ 411" for Lalande 21185 and "alf Cen A" for the alpha Cen system.
- **Refuted or retracted** claims: a later refereed paper shows the signal is
  activity, an alias or instrumental, or the authors withdrew it. Say who
  refuted it. A claim that is merely *contested* is a candidate, tiered
  `ambiguous`. A claim that has been *shown wrong* is not.
- Objects whose own authors call them **brown dwarfs**, with a minimum or true
  mass above 13 M_Jup.
- Pure dynamical or disk-structure inferences with no detected signal, such as
  "a planet may carve this gap". The one exception is the phase-1 agent's
  built-in bodies (Planet Nine).
- Anything beyond 100 ly.

Separately, list **confirmed planets that are missing from the confirmed tab**
(for example, a planet NASA or a refereed paper calls confirmed that is not in
`planets_confirmed.csv`) under `confirmed_missing_from_confirmed_sheet`. These
are **not** candidates and will not be added to the Unconfirmed tab. They are a
report for the user.

## Confidence tier (column AJ). Use exactly one of these three words.

- `strong`: a TOI PC, or a candidate with a significant detection and no
  published contrary evidence. Also one with partial independent support.
- `ambiguous`: a TOI APC, or a published claim that is contested. Also a signal
  close to the stellar rotation or magnetic-cycle period, a single-instrument
  low-significance signal, or a single-epoch imaging detection.
- `unlikely`: a TOI FP/FA, or a candidate whose best current reading is
  "probably not a planet" but that has not been formally refuted.

Put the reasoning in `tier_reason`, bluntly. The workbook's existing tone is
candid about weak data. Keep it that way.

## Naming

- `planet`: the designation the discovery paper or catalogue uses, prefixed
  with the host **as the Systems tab spells it** when a letter is used, e.g.
  "TRAPPIST-1 i", "GJ 411 d". Keep TOIs as "TOI-1234.01" and Gaia as
  "Gaia-ASOI-008". If a paper gives no letter, use host + " candidate P=<period>d"
  (for example "GJ 1002 candidate P=20.2d"). A letter must never collide with a confirmed
  planet's letter on the same host.
- `system_host`: exactly as in column `system_host` of `PACK/systems.csv`.
  For a new system (phase 3), use the most common catalogue name in the
  sheet's style: "GJ 406", "HD 26965", "Wolf 359", "TOI-6276".
- `planet_host_star`: the star it actually orbits, spelled as
  `PACK/multistars.csv` column "Star (component)" spells it when the system is
  multiple. Otherwise the same as `system_host`.

## Where to look (all reachable from this machine)

- NASA Exoplanet Archive TAP: `https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=...&format=csv`.
  Useful tables are `toi`, `ps`, and `pscomppars`. `pscomppars` holds the
  confirmed planets, so use it to check status.
- ExoFOP-TESS target pages: `https://exofop.ipac.caltech.edu/tess/target.php?id=<TIC>`.
- Gaia archive TAP: `https://gea.esac.esa.int/tap-server/tap/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY=...`.
  Useful tables are `gaiadr3.gaia_source`, `gaiadr3.astrophysical_parameters`
  and `gaiadr3.nss_two_body_orbit`.
- SIMBAD TAP: `https://simbad.cds.unistra.fr/simbad/sim-tap/sync` (for aliases,
  the `ident` table). Or `https://simbad.cds.unistra.fr/simbad/sim-id?Ident=<name>&output.format=ASCII`.
- arXiv API: `https://export.arxiv.org/api/query?search_query=...&max_results=50`.
  Search every major alias with terms such as candidate, unconfirmed,
  tentative, "planetary signal", "planet candidate", "additional signal".
  Read the abstract, and the paper when the abstract names a candidate.
- exoplanet.eu: per-star or per-planet pages via WebFetch
  (`https://exoplanet.eu/catalog/?query=<name>` or planet pages). The bulk CSV
  export ignores its filters; don't rely on it.
- Open Exoplanet Catalogue: raw XML at
  `https://raw.githubusercontent.com/OpenExoplanetCatalogue/open_exoplanet_catalogue/master/systems/<Name>.xml`.
  The `<list>` element says Confirmed, Controversial or Retracted.
- WebSearch and WebFetch, for anything else (journal pages, Wikipedia leads).

Record the searches you ran for each system in its coverage entry. An empty
result is a result. It shows the system was examined, not skipped.

## Output: one JSON file, `OUT/<AGENT_ID>.json`

**Save as you go:** rewrite the file after each system you finish, and keep it
valid JSON at every save (partial is fine). Usage limits can cut an agent off
mid-task, and anything that is not on disk is lost. UTF-8. Schema:

```json
{
  "agent_id": "B07",
  "phase": 2,
  "coverage": [
    {"system_host": "GJ 411",
     "aliases_searched": ["Lalande 21185", "HD 95735", "GJ 411"],
     "sources_checked": ["arXiv API", "exoplanet.eu", "OEC", "NASA pscomppars", "TOI table"],
     "result": "1 candidate",
     "notes": "b and c confirmed (on sheet). d candidate from Hurt+2022..."}
  ],
  "candidates": [
    {
      "planet": "GJ 411 d",
      "system_host": "GJ 411",
      "new_system": false,
      "planet_host_star": "GJ 411",
      "aliases": ["Lalande 21185 d"],
      "designation": "d (Hurt et al. 2022, Table 5)",
      "tfopwg_disposition": "",
      "tier": "ambiguous",
      "tier_reason": "...",
      "detection_method": "Radial velocity",
      "period_d":     {"value": 215.0, "err": "+/-1.2", "src": "S1", "where": "Table 5"},
      "a_au":         null,
      "ecc":          {"value": 0.1,   "err": "+0.1/-0.07", "src": "S1", "where": "Table 5"},
      "mass_earth":   {"value": 4.0,   "err": "...", "type": "Msini", "src": "S1", "where": "Table 5"},
      "radius_earth": null,
      "host_inputs": {
        "mass_msun":       {"value": 0.39, "src": "S1", "where": "Table 1"},
        "teff_k":          {"value": 3547, "src": "S1", "where": "Table 1"},
        "radius_rsun":     null,
        "luminosity_lsun": null,
        "logg":            null
      },
      "orbit_flags": "Text for the 'Orbit data source / flags' column: what is measured, what is missing, caveats.",
      "reference": "Hurt et al. 2022, AJ 163, 218, 'Lalande 21185 ...', Table 5",
      "vetting_date": "2022-04-01",
      "catalogue_distance_ly": {"value": 8.31, "src": "S2", "where": "Gaia DR3 parallax 392.75 mas"},
      "wikipedia_values": [],
      "sources": {
        "S1": {"citation": "Hurt et al. 2022, AJ 163, 218", "url": "https://arxiv.org/abs/2201.xxxxx", "what": "orbit and Msini"},
        "S2": {"citation": "Gaia DR3 gaia_source", "url": "https://gea.esac.esa.int/...", "what": "parallax"}
      },
      "dedupe": "Checked planets_confirmed.csv and unconfirmed_existing.csv for GJ 411 / Lalande 21185 / HD 95735: b and c only; no d.",
      "confidence_notes": "Blunt, one or two lines."
    }
  ],
  "new_systems": [],
  "considered_not_added": [
    {"name": "GJ 581 d", "system_host": "GJ 581", "reason": "refuted: activity (Robertson et al. 2014, Science 345, 440)", "source_url": "..."}
  ],
  "confirmed_missing_from_confirmed_sheet": [],
  "incidental_finds_outside_my_scope": []
}
```

`host_inputs` matters only when the host is **not** on the Planets tab or is a
new system. For hosts already on the sheet, `null` values are fine.

**Phase-3 agents** also fill `new_systems`, one object per system that is not on
the Systems tab. Every value is `{"value", "src", "where"}` or null:

```json
{"system_host": "Wolf 359", "nickname": "", "aliases": ["GJ 406", "CN Leo"],
 "parallax_mas": {...}, "distance_ly": {...},
 "stars_in_system": 1, "system_stars": "",
 "host_mass_msun": {...}, "stellar_class": {...}, "teff_k": {...},
 "radius_rsun": {...}, "luminosity_lsun": {...}, "logg": {...},
 "age_gyr": {...}, "feh": {...},
 "rv_kms": {...}, "pmra_masyr": {...}, "pmdec_masyr": {...},
 "gaia_dr3_source_id": "...", "companions": [],
 "sources": {...}}
```

Take the kinematics from Gaia DR3 `gaia_source` (`radial_velocity`, `pmra`,
`pmdec`, `parallax`) whenever it has them, as the existing rows do. For mass,
Teff, luminosity and radius, prefer a paper's stellar-parameter table, then
Gaia DR3 FLAME/GSP-Phot (`astrophysical_parameters`: `mass_flame`,
`lum_flame`, `radius_flame`, `teff_gspphot`). Name which one you used. GSP-Phot is
poor for M dwarfs, so say so if that is all there is.

Finish by replying with a five-line summary: systems covered, candidates found,
new systems (phase 3), notable exclusions, and anything that needs the writer's
judgement.
