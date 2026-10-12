# The Google Sheets star catalog

`--source catalog` builds a plottable system out of the catalog spreadsheet
instead of hardcoded elements. Any host star in the workbook becomes a system
on demand:

```bash
python -m hybrasil.cli --list-catalog
python -m hybrasil.cli --source catalog --system TRAPPIST-1
python -m hybrasil.cli --source catalog --system "Proxima Cen b"
python -m hybrasil.cli --source catalog --system "tau Cet" --mode static
```

The workbook is private, so its ID is not in the source. Give it with
`--sheet-id <id-or-url>`, `$HYBRASIL_SHEET_ID`, or once by saving the ID or URL
as `sheet_id.txt` in the config directory, beside the credential
(`%APPDATA%\hybrasil\` on Windows, `~/.config/hybrasil/` elsewhere).

## One-time setup

Install the client libraries:

```bash
pip install google-api-python-client google-auth google-auth-oauthlib
```

Then give the project access to the sheet. The loader asks for the read/write
Sheets scope, because the same module is used to edit the catalog workbook; see
`docs/hybrasil-instructions.md` for the rules that govern those edits. A
**service account** is the least-effort option: no browser, no token expiry,
and the sheet stays private.

1. In the Google Cloud console, enable the **Google Sheets API**.
2. Create a service account and download a JSON key.
3. Save the key where the loader looks for it:
   - Windows: `%APPDATA%\hybrasil\service_account.json`
   - macOS / Linux: `~/.config/hybrasil/service_account.json`
   - or set `$HYBRASIL_GOOGLE_CREDENTIALS` to its path.
4. Open the spreadsheet, press Share, and add the key's `client_email` as an
   **Editor**. Viewer is enough to read the catalog, but any write will fail.

If you would rather sign in as yourself, save a Desktop-app OAuth client JSON
as `oauth_client.json` in the same directory. The first run opens a browser and
caches the token in `oauth_token.json` beside it. Never commit either file. A
token cached under an older, narrower scope is discarded automatically, so
widening the scope simply prompts for consent again.

## Caching

Every fetch pulls all tabs once and writes them to a cache:

- Windows: `%LOCALAPPDATA%\hybrasil\catalog\<sheet-id>.json`
- macOS / Linux: `~/.cache/hybrasil/catalog/<sheet-id>.json`

The cache is reused for 24 hours, so repeated runs do not hit the network.

| Flag | Effect |
| --- | --- |
| `--refresh-catalog` | Refetch now, ignoring the cache age |
| `--offline` | Use the cache only; fail if there is none |
| `$HYBRASIL_CATALOG_TTL` | Cache lifetime in seconds |
| `$HYBRASIL_CACHE_DIR` | Move the cache elsewhere |

A failed fetch falls back to a stale cache when one exists, so losing the
network degrades to slightly old data rather than an error.

## How the workbook is read

Tabs are matched by the headers they contain, not by tab title, so renaming or
reordering a tab does not break anything. Columns are read by header name for
the same reason. Three header signatures matter:

| Role | Identified by |
| --- | --- |
| Planets | `Planet` + `Host system (primary star)` |
| Stars | `System / Host` + `Star (component)` |
| Systems | `System / Host` + `Host mass (M-sun)` |

Every other tab is ignored. More than one tab may match the planet signature,
which is how the confirmed and candidate lists are merged: a planet appearing
on both keeps whichever row carries more orbital detail.

A system is drawn whole: every star on the stars tab, each planet around the
star it actually orbits (`Planet-host star`). Proxima Centauri's planets are
filed in the workbook under the Alpha Centauri A system, and that is the
system they are drawn in, circling Proxima, with A and B beside it.

Names resolve loosely, and every name reaches the whole system. A primary, a
companion star, an IAU nickname, a planet name, or an unambiguous prefix all
work. An ambiguous name lists the candidates rather than guessing.

## What is real and what is filled in

Taken from the sheet:

| Element | Column |
| --- | --- |
| Semi-major axis | `Semi-major axis (au)` |
| Orbital period | `Orbital period (d)` |
| Eccentricity | `Eccentricity` |
| Planet mass | `Mass (M-earth)`, else `Mass (M-Jup)` |
| Planet radius | `Radius (R-earth)`, else `Radius (R-Jup)` |
| Star mass | `Mass (M-sun)`, else `Host mass (M-sun)` |

Derived or defaulted, and stated in every system's description:

- **Inclination, ascending node and argument of periapsis are set to zero.**
  The workbook does not carry orbital orientation, so catalog systems render as
  a flat co-planar disk. This is the one place where a catalog plot is
  guaranteed to differ from a built-in system such as TRAPPIST-1, whose real
  inclinations come from Agol et al. 2021.
- **Mean anomaly is a hash of the planet name.** It spreads planets around
  their orbits instead of stacking them all at periapsis. It is stable across
  runs but it is not an observed phase.
- **Missing period or semi-major axis** is derived from the other through
  Kepler's third law, when the host mass is known. A planet with neither is
  skipped and named in the description.
- **Eccentricity** is clamped to 0.95.
- **Stellar radius** comes from luminosity and effective temperature via
  `R/Rsun = sqrt(L/Lsun) x (Tsun/Teff)^2`. The workbook carries no radii.
- **Star colour** follows effective temperature; **planet colour** follows the
  `HZ position` column, so a system shows at a glance which planets sit inside
  the habitable zone.
- **Confidence tier** other than `confirmed` marks a planet `hypothetical`,
  which the viz already renders as a hollow marker on a dashed orbit.

Companion stars are placed from four columns on the stars tab, added
23 September 2026:

| Column | Used as |
| --- | --- |
| `Separation from` | The star it is drawn around; the primary if blank or not in the system |
| `Separation (AU)` | The orbit's size |
| `Separation type` | `semi-major axis`: a solved orbit, drawn as its ellipse with `Orbital eccentricity (e)`. `projected`: a circle at that distance, marked hypothetical, because a sky-plane separation is a lower bound on the real one. `assumed`: the same hypothetical circle, at a model-inferred distance (orange in the sheet) for a suspected companion |
| `Separation source` | Shown in the star's info panel |

- **Period:** Kepler's third law on the two stars' masses.
- **Orientation:** a companion's orbit is co-planar and flat, like every
  catalog orbit.
- **Missing separation:** a companion with none is not drawn, and the
  description names it and any planets of its own.
- **Where the values come from:** Sources & Provenance, the entry
  "MULTI-STARS: SEPARATION COLUMNS AQ:AT ADDED".
