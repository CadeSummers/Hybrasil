# Research brief: radial velocities (and a few proper motions) for objects within 100 ly

You are one of several research agents filling the motion columns of the **"Known within 100ly"**
tab of a private star-catalog spreadsheet (the `hybrasil` workbook behind the hybrasil project).
Your job is **research only**. You produce one JSON file. A single writer (the orchestrating session)
validates every agent's JSON and makes all spreadsheet edits itself.

Repository root, referred to as `ROOT`: `<repo>`

- **Your input:** `ROOT\data\known_within_100ly\kinematics\batches\<BATCH>.json`. It holds about 100
  objects. Each one gives its `key` (copy it exactly), name, Gaia DR3 source_id (may be null), RA/Dec at
  epoch J2016.0, distance in ly, Gaia G magnitude, the SIMBAD main identifier, object type and spectral type,
  and `need`, which says what is missing: `rv`, `pm`, or both.
- **Your output:** `ROOT\data\known_within_100ly\agent_output\<BATCH>.json`.

## What is already known, so do not repeat it

Gaia DR3 (`gaiadr3.gaia_source`) and SIMBAD's adopted values were already queried for every object.
None of your objects has a Gaia DR3 radial velocity. None has a usable SIMBAD RV either: the RV was
absent, of quality D/E, zero, or of "z" type. Where SIMBAD had a value that was rejected, the input shows
it under `simbad_rv_rejected`. You may confirm or replace it from the paper it cites. Nearly all objects
already have a proper motion. Only rows with `"pm"` in `need` lack one.

Most of these objects are faint: M dwarfs, L/T/Y brown dwarfs, white dwarfs, and companions. Many
genuinely have no published RV. **"Searched, nothing found" is a valid and useful result.** Record it,
then move on.

## Hard rules

1. **Do not write anything except your one output file.** Do not write to the Google Sheet. Do not
   import `hybrasil.data.google_sheets`. Do not edit the repo. Read-only web and TAP queries are fine.
2. **Never fabricate.** Every number needs a source you actually opened or queried this session, with a
   locator: a table, a VizieR catalog ID with its column, or the query you ran. A value you remember but
   could not re-find goes in `notes`, marked "recalled, not verified". It never goes in `rv` or `pm`.
3. **Measured values only. Do not derive.**
   - Report a published heliocentric radial velocity in km/s, with its uncertainty.
   - Do not compute space velocities or anything else.
   - Do not average several RVs yourself. Pick one, in this order:
     1. the most precise multi-epoch value;
     2. a published systemic (gamma) velocity, for a known spectroscopic binary;
     3. otherwise the most recent large survey.
     Name the alternatives you saw in `notes`.
4. **White dwarfs.** A white dwarf's measured line shift includes its gravitational redshift, often
   20–80 km/s. Report an RV only where the paper gives the redshift-corrected, kinematic RV, and say so in
   `where`. Otherwise record "only uncorrected line velocity" in `notes` and leave `rv` null.
5. **Identify the object correctly.**
   - Match by Gaia DR3 source_id wherever a catalog carries it.
   - Match by position only after carrying the J2016.0 position to the catalog's epoch with the proper
     motion. Many of these objects move several arcseconds a year.
   - For a component (a name ending in A, B, C), the value must be for that component. If only a
     primary-star RV exists (the companion's light is not in the spectrum), do not report it as the
     component's. Mention it in `notes`.
   - **A blended value is reportable** (decided 2026-10-09): where the component is in an unresolved pair
     closer than ~2.5" and within ~2.5 mag of its companion, a combined-light or systemic RV of the pair
     goes in `rv`, with `"blended": "<the companion, its separation and G>"` added to the record. The writer
     notes it as not the component's own.
6. **Source order:**
   1. refereed paper or arXiv, or a VizieR catalog of one;
   2. a large survey catalog (APOGEE, LAMOST, RAVE, GALAH, Gaia-ESO);
   3. **Wikipedia, as a last resort only, and only when it cites a source for that exact number.**

   A Wikipedia value needs `"wikipedia": true`, `wikipedia_url`, `wikipedia_page`, `cited_source` (the
   reference Wikipedia gives, with enough detail to find the number in it) and `cited_url`. The writer
   gives such cells a pink border and logs them. Try to open the cited source and quote it directly. If
   that works, it is not a Wikipedia value.
7. **Budget.** First run the bulk catalog queries below for your whole batch, which usually answers most
   of what can be answered. Then spend a few web searches on each remaining object, and more on a named,
   well-studied star than on an anonymous Gaia source.

## Suggested method

1. **Load the batch.** `python` is available, with `astroquery` 0.4.11 and `astropy` 8.
   `astroquery.vizier` (Vizier with `columns=["**"]` and `row_limit=-1`) and `astroquery.xmatch` (CDS
   XMatch against `vizier:<catalog>`) are the fast path for a whole batch at once.
2. **Bulk crossmatch** the batch against RV catalogs, by Gaia DR3 id where the catalog has it, else by
   position at the right epoch. Starting points (verify each catalog ID on VizieR yourself):
   - **Surveys:** APOGEE DR17 (III/286), LAMOST DR (low and medium resolution), RAVE DR6 (III/283),
     GALAH DR3/DR4, Gaia-ESO DR5.
   - **M dwarfs:**
     - CARMENES: Reiners et al. 2018 (J/A+A/612/A49), Lafarga et al. 2020, Jeffers et al. 2018.
     - Fouqué et al. 2018 (SPIRou input catalogue), Newton et al. 2014, Terrien et al. 2015,
       Shkolnik et al. 2012, Sperauskas et al. 2019, Gizis et al. 2002, Malo et al. 2014.
   - **Brown dwarfs:** Hsu et al. 2021 (APOGEE/NIRSPEC late-M/L/T RVs), Blake et al. 2010,
     Burgasser et al. 2015, Vos et al. 2017.
   - **SDSS DR19 Milky Way Mapper** (`mwm_apogee_allstar` / `allvisit`, queried by Gaia DR3 id through the
     SkyServer SQL service): not on VizieR, and the best single source in batch K004.
   - **DESI DR1 Milky Way Survey** (`desi_dr1.mws` on the NOIRLab Astro Data Lab TAP service, by Gaia DR3 id,
     with errors): the best new source in batches K009 and K013. The SpecDis VizieR copy lacks the errors.
   - **DESI's caveat:** for late-M dwarfs, DESI read 3–6 km/s higher than high-resolution values in batch K017,
     so its formal 0.2 km/s errors understate a systematic error. Prefer a high-resolution value where one
     exists. The writer flags every DESI DR1 value WEAK, and Hsu et al. 2026 JWST values too.
   - **Warning:** SDSS DR19 / APOGEE `v_rad` fails for late-M dwarfs and returns ±500–1000 km/s. Never use a
     value like that.
   - **LAMOST M stars:** Li et al. 2025 (J/ApJS/281/58; check its validity flag n_RVel), Zhang B. et al. 2022
     (J/ApJS/258/26, medium resolution), LAMOST DR11 (V/162; for MRS use rv_br1 with flag 0).
   - **Others that paid off:** GALAH DR4 (J/other/PASA/42.51), PMSU (III/198, ±10 km/s; its CNS3 number is SIMBAD's
     [RHG95]), Hsu et al. 2024 (J/ApJS/274/40), Latham 2002 (J/AJ/124/1144), Gizis 2002 (J/AJ/123/3356).
   - **Prefer Lafarga et al. 2020 (J/A+A/636/A36) over Reiners et al. 2018** where both have a star: about 50 of
     Reiners' 316 differ from Lafarga's by over 2 km/s.
   - **Catalogs that hand a companion its primary's RV:** GCNS and Kervella et al. 2022 do this for some B
     components, so check the value is the component's own before using it.
   - **Also not a measurement:** a BANYAN or moving-group membership paper's "predicted" RV (for example Gagné et
     al. 2015 and 2018).
   - **SDSS DR19 BOSS** (`mwm_boss_allstar`) RVs are low resolution, with errors of 6–9 km/s. Use one only when
     nothing better exists.
   - **Hsu et al. 2021** (J/ApJS/257/45, `dwarf20pc`) reference codes are shifted by one: 760 is meant as 761,
     771 as 772, 755 as 756. Trace each value to its own paper.
   - **Not data:** VizieR `gum_mw` rows are Gaia Universe Model simulations, never measurements. Tokovinin's
     "gamma" column is an angle.
   - **Bright stars:** Soubiran et al. 2018 (J/A+A/616/A7), Gontcharov 2006 (III/252),
     Nordström 2004 GCS (V/130).
   - **White dwarfs:** Raddi et al., Napiwotzki et al. (SPY). Remember rule 4.
3. **Per object,** search ADS, arXiv and Google Scholar for its names (SIMBAD lists them all) together
   with "radial velocity".
4. **Query VizieR in chunks of about 30 coordinates.** A `query_region` call with around 200 coordinates
   silently dropped matches in batch K022.
5. **Kiman et al. 2019 vs Schmidt et al. 2010:** these SDSS pipeline RVs often disagree by 30–60 km/s for the
   same spectrum. Report one only when the two agree, or when only one exists, and put the other in `notes`.
6. **Save your output file after every 10 objects,** and whenever a bulk query finishes. It must be valid
   JSON at every save (write to a temporary name, then rename). If you are stopped, the next agent resumes
   from your file.

**Resuming:** if `agent_output\<BATCH>.json` already exists when you start, read it first. Keep every
object already in it, and research only the batch keys that are missing or have `"done": false`.

## Output schema

```json
{
  "agent_id": "K001",
  "batch": "K001",
  "complete": false,
  "objects": [
    {
      "key": "LHS 1234|1234567890123456789",
      "name": "LHS 1234",
      "done": true,
      "rv": {"value": -12.3, "err": 0.4, "src": "S1",
             "where": "VizieR J/A+A/612/A49, table1, col RV (CARMENES, 12 epochs)",
             "wikipedia": false},
      "pm": null,
      "sources": {"S1": {"citation": "Reiners et al. 2018, A&A 612, A49", "url": "https://doi.org/10.1051/0004-6361/201732054",
                         "what": "CARMENES M-dwarf RVs"}},
      "searched": ["APOGEE DR17 (by Gaia id): no match", "LAMOST MRS: no match", "ADS 'LHS 1234 radial velocity'"],
      "notes": "Also Newton 2014: -11.9 +/- 0.6 (fewer epochs)."
    }
  ]
}
```

- **`rv`** is `{"value", "err", "src", "where", "wikipedia"}` or `null`. `value` and `err` are numbers in km/s;
  use `null` for `err` when none is given.
- **`pm`** is `{"pmra", "pmdec", "err", "src", "where", "wikipedia"}` or `null`. Fill it only when `need`
  includes `pm`. `pmra` is μα·cos δ, in mas/yr.
- **A Wikipedia value** also carries `wikipedia_url`, `wikipedia_page`, `cited_source`, `cited_url`, and
  optionally `cross_check`.
- **Every batch object** must appear exactly once with `"done": true` before you set `"complete": true`.
  That includes objects where nothing was found: `rv` null and `searched` filled in.
- **`src`** must name a key of that object's `sources`.

When finished, reply with five lines:
1. objects with an RV found;
2. objects with a PM found;
3. Wikipedia values, if any;
4. catalogs that paid off;
5. anything the orchestrator should know, such as a mis-identified row or a duplicate.
