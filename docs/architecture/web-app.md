# The web app (`--serve`): Featured and More Modeled Systems

```bash
python -m hybrasil.cli --serve              # http://127.0.0.1:8765/
python -m hybrasil.cli --serve --system "tau Cet" --source catalog
python -m hybrasil.cli --serve --port 0 --no-open
```

This runs the three.js viewer from a small local server instead of a
temporary file. The page arrives with no systems in it and asks the server for
each one the first time it is opened. That is what lets the **More Modeled
Systems** dropdown search every catalog system (304 at the time of writing) without building
roughly 25 MB of scenes up front. It is also the shape a hosted deployment
needs: the page never cares whether it came from `localhost`.

## The API (`hybrasil/web/app.py`)

| Route | Returns |
|---|---|
| `GET /` | the viewer shell: `SA3_SYSTEMS = {}`, `SA3_API = "/api"`, the solvent table |
| `GET /api/systems` | `{systems: [...], catalog: {available, title, error}}`: every searchable system |
| `GET /api/systems/<id>` | `{id, name, scene, body_info}` for one system; 404 if unknown |
| `GET /llms.txt` | the canonical home, licences, citations and where to propose changes (`web/discovery.py`) |

An id is a featured key (`55-cancri`), a featured view's key
(`nearby-star-motion`, listed after the built-ins with `view: true` and built by
`views.build_view()` from the library's catalog, else the committed snapshot;
see `docs/architecture/star-motion.md`), or `catalog:<host>` (`catalog:tau Cet`,
URL-encoded in the path). Standard library only (`ThreadingHTTPServer`), bound
to `127.0.0.1` unless `--host` says otherwise.

`SystemLibrary` holds the index and a scene cache. A scene is built the first
time it is asked for, through `figures.build_figure()`, the same function the
CLI uses, then cached for the life of the process. So a system drawn by the
web app is the system the CLI draws. Building one takes about 0.2 s.

## Featured and catalog, listed once

`FEATURED_CATALOG_HOSTS` in `builtin_systems.py` names the catalog systems
each featured system already covers: `Sun`, `TRAPPIST-1`, `alf Cen A`,
`ups And` and `55 Cnc A`. A catalog system is a whole system (see
`docs/architecture/catalog.md`), so `alf Cen A` there means A, B and Proxima
together, which is what the featured Alpha Centauri draws. Proxima Centauri
covers no catalog system of its own, and keeps its names as aliases. Covered
systems are left out of the catalog half of the index and added to the
featured entry's aliases. So searching "55 Cnc A" opens the literature-built
55 Cancri, not a thinner catalog duplicate. The CLI makes the same fold
(`cli._featured_twin()`): `--source catalog --system "55 Cnc g"` opens the
featured 55 Cancri.

A catalog entry's aliases are its nickname and its other stars, so
"55 Cnc B" or "HD 18143 C" finds the system the star belongs to.
`FEATURED_ALIASES` adds the other names people use (Rigil Kentaurus, Toliman,
Titawin, Copernicus). **A new featured system needs entries in both**, or its
catalog twin shows up in the search as a second system.

A catalog entry's nickname, class and distance are its primary's
(`catalog_entry()`). A star's own nickname is used only for that star: Proxima
Cen's system row is alf Cen A's, and "Rigil Kentaurus" is not Proxima's name.

## When the catalog is unavailable

No credential or no network: `SystemLibrary.catalog()` falls back to the
committed snapshot (`data/snapshot.py`), as the planetless, Sgr A* and nearby
loaders do, and says so on stderr. `HYBRASIL_DATA_SOURCE=snapshot` skips the
sheet altogether. Only if the snapshot fails too does the app serve the
featured systems alone; `/api/systems` then reports why under
`catalog.error`. The catalog costs the catalog, never the app. `--offline`
and `--sheet-id` pass straight through.

## The search (`hybrasil/viz/system_search.js`)

Pure functions, loaded by the page as `window.SASystemSearch` and by
`tests/test_system_search.py` under node. Names are compared as written and
with the Bayer letter (first word) and constellation abbreviation (any later
word) spelled out. So "tau ceti" is an exact match for "tau Cet", and "tau
Boo" stays the letter tau in Bootes rather than Taurus. The tiers, best first:
exact, prefix, every typed word starts a word of the name, substring, then
within 1–3 typos (optimal string alignment). The typo tier is the autocorrect,
and the page labels it "Did you mean …?". Aliases and planet names match too.
A planet ranks a little below the star's own name.

## The More Modeled Systems list

The dropdown opens on a **System Type:** row with three buttons: **Planetary**
(the default), **High Star Count (Planetless)** and **Stellar Motion**. Each
index entry carries a `kind` (`planetary`, `planetless`, `motion`) and the list and the
search hold only entries of the chosen one. The kind comes from
`views.system_kind()`: `motion` for a featured view, `FEATURED_KINDS` in
`builtin_systems.py` for a built-in that has an entry there (none since
7 Oct 2026, when Castor's brown dwarf became a planet and Castor with it a
planetary system), `planetary` for everything else, every catalog system
included. A Planetless 4+ Stars system's own entry says `planetless`, or
`planetary` once a brown dwarf of it is a planet-tab row
(`planetless_loader.planetless_entry`).
The file page gets the same kinds as `window.SA3_KINDS`. The chosen type is
kept between opens while the page is open, and is Planetary again on a reload.

A featured system's label on its button and in the list is
`FEATURED_LABELS.get(key, system.name)`. None differs today; Castor's read
"Castor (Planetless)" until 7 Oct 2026.

**Stellar Motion** also holds `galactic:sgr-a`, listed as **Sgr A\* Cluster (Galactic Center)** after Nearby
Stellar Motion (it had a Galactic Center type of its own until 10 Oct 2026): the S-stars round Sgr A*, read from the workbook's
Sgr A* S-stars tab by `sgr_a_loader.py` (`SystemLibrary.galactic()`, cached like `planetless()`, off with the
catalog) and built on demand. See `docs/architecture/galactic-centre.md`.

Under **High Star Count (Planetless)** and **Stellar Motion** the list holds every system of
the type, featured ones included: High Star Count (Planetless) is the hierarchies of the
workbook's Planetless 4+ Stars tab with no planet (69 of its 79 non-featured
systems; the other ten, whose brown dwarfs are planets, are under Planetary),
most stars first (every
star row, candidates included: `n_stars`), then nearest
(`planetless_loader.py`, ids `planetless:<host>`, built on demand like a
catalog system); Stellar Motion is Nearby Stellar Motion.
`SystemLibrary.planetless()` reads the tab once, from the live sheet or the
snapshot, and follows `use_catalog`; a failure costs those systems only. Each
opens over a window of 1.2 x its shortest period (5 days to 100 years,
`planetless_span_days`), so the tightest pair turns and the wide orbits are
drawn whole. Under **Planetary** it lists **every
catalog system** in the index, below the featured ones, which keep their own
buttons. Nothing is hand-picked: a system appears as
soon as the workbook gives it a planet, with an orbit or not. One with no orbit
on file opens as its stars and bands (docs/architecture/catalog.md, rule 5).
The page sorts the list itself (`SASystemSearch.shelf()`): most planets first,
then nearest, then by name. A system with no distance sorts after those with one
at the same planet count. The planet count is `n_planets`, every planet on file,
candidates included. It can be more than the viewer draws, when some have no orbit.

The list is **twelve rows tall** (`VISIBLE_ROWS` in `three_viewer.js`) and
scrolls for the rest. The height is measured from the rows once they are drawn,
not assumed, and never exceeds 60% of the window.

## In the page

- **Suggest Changes** and **ⓘ About** sit at the right end of the first row.
  - Suggest Changes is described in `docs/architecture/suggestions.md`.
  - About shows who made the map, how to cite it (APA and BibTeX for the
    software and the dataset, the dataset at the snapshot version the page
    was built from), its licences, its data credits and a privacy note.
  - Its content is `hybrasil/about.json`, shipped to every three.js page as
    `window.SA3_ABOUT`. Fill in a DOI or a Ko-fi/Patreon handle there; a
    null hides its line. The "Created by" credit at the bottom right of the
    canvas takes the author's name from the same file. It shares one row with
    the Milky Way credit, so on a phone the sky credit wraps beside it.
  - Both are modals built by `makeDialog()` in `three_viewer.js`. Escape and
    a click outside close them, Tab stays inside, keys never reach the
    camera, and focus returns to the opener.
- **★ Featured systems** labels one button per featured system. The buttons
  are always in the bar.
- **More Modeled Systems ▾** is a dropdown button. A click opens a panel beneath it:
  - the System Type row, the chosen type lit;
  - a search box, focused and empty;
  - a caption giving the number of systems and the order;
  - under it, for Planetary, every catalog system, most planets first, then
    nearest, twelve rows tall and scrolling for the rest; for the other types,
    every system of the type.
- **Typing** in the box replaces the list with the ranked search over every
  system of the chosen type, featured ones included.
- **Keys:** arrow keys move the highlight, and the list scrolls to keep it in
  view. Enter opens it, and Tab completes the name without opening it.
- **Closing the panel:** picking a system, a second click on the button,
  Escape, or a click anywhere else.
- **An open catalog system** has no button of its own. The dropdown button
  names it ("More Modeled Systems · HD 219134 ▾") and is lit, as a featured system's
  button is.
- `openSystem(id)` fetches a scene the page does not have, merges its
  `body_info` into `_SA_BODY_INFO`, then builds it. Picks can overlap, so a
  token makes sure only the latest one is built.
- The slider values carry over to a system fetched later, as they do across
  any switch.
- The in-scene search (bodies, bands, orbits of the open system) is labelled
  "Find in system…", so the two boxes cannot be mistaken for each other.
- **The file-based page** (`--output html`, or the default browser view)
  holds only the featured systems. There the dropdown's search covers the
  systems in the file, and the Planetary list says `--serve` opens the rest.

## The static site (`--build-site`, `hybrasil/web/static_site.py`)

The hosted app is the API written out as files, so no server and no Google
credential is ever online (Cloudflare Pages, with GitHub Pages as the
fallback).

```bash
HYBRASIL_DATA_SOURCE=snapshot python -m hybrasil.cli --build-site site
```

- `site/index.html` is `app_page()`, the server's own shell, with relative
  URLs: `SA3_API = "api"`, `SA3_INDEX_URL = "api/systems.json"`, `SA3_SKY =
  "sky/milky_way_4k.jpg"`. Nothing starts with `/`, so the site works under a
  path prefix (a GitHub Pages project site) as well as at a domain's root.
- `site/api/systems.json` is `/api/systems`, with one addition: every entry
  carries `url`, its scene file. The viewer fetches `entry.url` when there is
  one and `${API}/systems/<id>` otherwise, so **the browser never turns an id
  into a file name** and there is no second copy of `slug()` in JavaScript.
- `site/api/systems/<slug>.json` is `/api/systems/<id>`. `slug()` lower-cases
  and hyphenates (`catalog:tau Cet` -> `catalog-tau-cet`); ids that slug alike,
  case included, get a hash suffix (`scene_files()`), because Windows and
  macOS file systems ignore case.
- `llms.txt`, from `discovery.llms_txt()`.
- `_headers` (Cloudflare's caching and security headers), `robots.txt`,
  `.nojekyll` (GitHub Pages), and the 4k sky.

**The build is strict where the server is forgiving.** No catalog, or any one
system failing to build, fails the whole build (`SiteBuildError`, naming every
failure): a partial site is not one to deploy. The index's `catalog.error` is
always null, because the server's error text can name a local path.

**Size.** From the 10 Oct 2026 snapshot: 496 systems, about 416 MB of JSON,
median 0.5 MB a scene and 6.2 MB the largest (the Sgr A* Cluster), in
2 minutes. That fits Cloudflare Pages (25 MiB a file, 20,000 files), and a
scene travels compressed (Solar: 1.4 MB, 0.55 MB gzipped). Most of a scene is
orbit-line coordinates (`lines`). Trimming their precision is the obvious cut
if size ever matters; it must leave band geometry alone (CLAUDE.md, the
flat-disc rule).

### Deploy: hybrasil.app is `main`

`.github/workflows/pages.yml` builds the site from the committed snapshot and
uploads it to the Cloudflare Pages project `hybrasil`. The project is a
**Direct Upload** project, not a Git-integrated one: GitHub Actions is the
link to the repository. Three things follow from that.

- **Tests gate the deploy.** The deploy job `needs` the `tests` job, which is
  `tests.yml` called as a reusable workflow, so a red commit never goes live.
- **There is one deploy source.** The guard is `github.repository ==
  'CadeSummers/Hybrasil' && github.ref == 'refs/heads/main'`. Hybrasil-dev
  carries the same files and runs the tests, but its deploy is skipped. No
  branch gets a preview build.
- **The weekly run rebuilds the same commit.** Scenes start at build time, so a
  Monday cron keeps the planets where they are now. `workflow_dispatch` does
  the same by hand.

The workflow never runs on `pull_request`, because the deploy holds secrets.

**`main` changes only by squash-merging a pull request.** The repository's
`main` ruleset requires all of the following:

- a pull request, with no approving review (there is one maintainer);
- the `tests` check;
- linear history.

Commit signatures are not required (since 12 Oct 2026): local commits are
unsigned, and the rule blocked every merge.

A change goes to the public repo as a short-lived `pr/<name>` branch, which is
deleted on merge. The local pre-push hook allows that branch and refuses a
direct push to `main`. Snapshot pull requests (`catalog.md`) follow the same
route on `snapshot/auto`.

It writes `wrangler.toml` from `wrangler.example.toml` and applies the D1
migrations before deploying (`suggestions.md` § Setup). Its secrets live in the
GitHub environment `production`, which is restricted to `main`.

## Telling crawlers and agents whose it is (`hybrasil/web/discovery.py`)

The defence against copies is being the canonical
upstream, so the site says so to anything that reads it. Every piece comes
from `hybrasil/about.json`, the About panel's file, so a DOI or a licence is
changed in one place:

- **The page head** (`head_html()`, passed by `app_page()` into
  `build_app_html(head=...)`): a description, `<link rel="canonical">`, and
  schema.org JSON-LD, a `SoftwareApplication` for the map and a `Dataset` for
  the data, each with its own licence, the author by ORCID, and an
  `identifier` once its DOI is in `about.json`. The server's page and the
  static site's carry it; a standalone `--output html` file does not.
- **`/llms.txt`** (`llms_txt()`): served by `--serve` and written by
  `--build-site`.
- **`AGENTS.md`**, hand-written, says the same to coding agents and points at
  `CLAUDE.md` for the working rules.

The citations are worded as the About panel words them (`citations()` mirrors
`three_viewer.js`'s). `tests/test_discovery.py` checks all three against
`about.json`, and that every tracked source file carries its SPDX header.

Scenes start at the build time, like the server's, so a weekly rebuild keeps
the animation current. `tests/test_static_site.py` covers the files and a
path-prefixed serve; `tests/test_browser.py -k static_site` opens the site in
Chromium from `/hybrasil/` and runs the band click-through on every featured
system.
