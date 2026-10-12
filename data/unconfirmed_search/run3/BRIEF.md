# Run 3 research brief: shared rules for every agent

You are researching corrections to the **hybrasil** catalog workbook (a Google Sheet of stars,
planets and multi-star systems within 100 ly). The repo is
`<repo>`. Another session writes to the sheet; **you only research.**

## Hard rules

1. **Never write to the Google Sheet.** Do not call `update_cells`, `set_border`, `set_note`,
   `rename_workbook`, `batchUpdate`, or anything else that modifies it. Reading is allowed:
   ```bash
   cd <repo>
   PYTHONIOENCODING=utf-8 PYTHONPATH=. python -c "from hybrasil.data import google_sheets as gs; wb = gs.get_workbook(None); print(wb['tabs']['Planets within 100 ly'][0])"
   ```
   `wb['tabs'][tab]` is a list of rows, and row 0 is the header. Tabs: `Systems within 100 ly`,
   `Multi-stars within 100 ly`, `Planets within 100 ly`, `Unconfirmed within 100 ly`, `Rejected candidates`.
2. **Do not edit repo files.** The one file you write is your output JSON:
   `data/unconfirmed_search/run3/agent_output/<YOUR_ID>.json`.
3. **Every value needs a source you actually opened**: paper plus table or section, or a catalogue
   query you ran. Give the URL. Never write a value from memory. If you cannot find it, say so and
   leave it null. A gap is fine; a guess is not.
4. **Wikipedia is not a source.** You may use it to find the paper it cites; then cite and check that paper.
5. **Say whether a value is published or derived.** Derived covers arithmetic on published inputs:
   Kepler III, L from R and Teff, ly from parallax, AU from arcsec times distance. For a derived value
   give the inputs, the formula and the uncertainty. The sheet marks derived values orange.
6. Prefer the most recent refereed solution. Where sources disagree, report both and recommend one, with the reason.

## Useful endpoints (all work from Python `urllib`)

- **NASA Exoplanet Archive TAP:** `https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=<ADQL>&format=csv`
  - Tables: `pscomppars` (one row per planet, with per-field `*_reflink` columns), `ps` (one row per
    planet per paper; `default_flag=1` is the adopted one), `stellarhosts`.
  - Use `LIKE`; there is no `pl_refname` in pscomppars.
- **SIMBAD TAP:** `https://simbad.cds.unistra.fr/simbad/sim-tap/sync?request=doQuery&lang=adql&format=csv&query=<ADQL>`
  (tables `basic`, `ident`, `ids`; `basic.plx_value`, `sp_type`, `rvz_radvel`, `pmra`, `pmdec`).
- **Gaia DR3 TAP:** `https://gea.esac.esa.int/tap-server/tap/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY=<ADQL>`
  (`gaiadr3.gaia_source`: `source_id`, `parallax`, `parallax_error`, `ruwe`, `radial_velocity`, `pmra`, `pmdec`,
  `phot_g_mean_mag`; `gaiadr3.astrophysical_parameters`: `teff_gspphot`, `lum_flame`, `mass_flame`).
- **VizieR TAP:** `https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync?request=doQuery&lang=adql&format=csv&query=<ADQL>`
- **arXiv:** abstracts at `https://arxiv.org/abs/<id>`; the full text is often at `https://arxiv.org/html/<id>`.
- **ExoFOP:** `https://exofop.ipac.caltech.edu/tess/`

## Evidence already gathered

`data/unconfirmed_search/run3/run2_incidental_finds.txt` holds the previous run's findings.
Each line is an agent id followed by one JSON finding. Read the ones for your items first, then verify them.

## Output format

Write `data/unconfirmed_search/run3/agent_output/<YOUR_ID>.json`:

```json
{
  "agent": "<YOUR_ID>",
  "items": [
    {
      "name": "exact name as on the sheet (or the new name for a new row)",
      "tab": "the tab it is on, or goes to",
      "action": "one of the actions your task names",
      "current": {"<column header>": "value on the sheet now"},
      "fields": {
        "<exact column header>": {"value": 123.4, "source": "Author et al. YEAR, Journal vol, page, Table N",
                                   "url": "https://...", "derived": false, "method": null}
      },
      "reason": "one to three sentences a reader of the sheet can act on; cite the paper",
      "confidence": "high | medium | low",
      "notes": "anything the writer must know: disagreements, caveats, what you could not find"
    }
  ],
  "incidental_finds": ["anything wrong you noticed outside your scope, with a source"]
}
```

Use the sheet's exact column headers as `fields` keys; print the header row to get them. Give
numbers as numbers, not strings. Keep going until every item has a record, even if that record says
"not found". Finish with a short summary of what you found.
