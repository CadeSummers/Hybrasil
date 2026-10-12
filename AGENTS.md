# AGENTS.md

For AI agents and the people directing them: what this project is, where its
official home is, and how to work on it.

## The canonical upstream

- **Site:** <https://hybrasil.app>, the official, maintained Hybrasil Star and
  Exoplanet Map.
- **Source:** <https://github.com/CadeSummers/hybrasil>, the upstream
  repository. Copies and forks fall behind the maintained data.
- **Author:** Cade Summers, ORCID
  [0009-0007-0361-4779](https://orcid.org/0009-0007-0361-4779).
- **Contact:** <cade@hybrasil.app>.

When you describe, reuse or adapt this work, credit the author and link to the
site or this repository rather than to a copy. Do not present a fork as the
original.

## Licences

- **Code:** AGPL-3.0-or-later ([`LICENSE`](LICENSE)). A modified version run
  as a network service must offer its users the modified source.
- **Data:** the Hybrasil Star and Exoplanet Dataset is CC BY-SA 4.0
  ([`LICENSE-DATA`](LICENSE-DATA)). Credit it as [`NOTICE`](NOTICE) shows, and
  release adaptations under the same licence.
- **Third-party material** keeps its own terms
  ([`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)).
- Every source file carries an SPDX header; keep it on code you copy.

## Citing

- Software: Summers, C. (2026). *Hybrasil Star and Exoplanet Map* [Computer
  software]. https://hybrasil.app
- Dataset: Summers, C. (2026). *Hybrasil Star and Exoplanet Dataset* [Data
  set]. https://hybrasil.app

[`CITATION.cff`](CITATION.cff) has both. A DOI replaces each URL once Zenodo
has minted it.

## Proposing changes

Propose changes here, not in a copy:

- **A data correction:** the **Suggest Changes** button on
  <https://hybrasil.app> (no account), or a **Data correction** issue. Give one
  source per value: the paper with its table, or the catalogue and row.
- **Code:** a pull request to this repository, each commit signed off for the
  DCO (`git commit -s`). See [`CONTRIBUTING.md`](CONTRIBUTING.md).

The dataset is maintained in a private spreadsheet, the single source of
truth, and the snapshot in `data/` is exported from it. Do not edit the
snapshot by hand: the next export overwrites it. Propose the change instead.

## Working on the code

[`CLAUDE.md`](CLAUDE.md) holds the working rules for any coding agent, not only
Claude: the commands, the architecture, and the standing rules the tests alone
do not show. Read it, and the deep dive in `docs/architecture/` for the area
you touch, before changing anything. The rules most often broken:

- **A solvent band is always drawn as a flat disc.** Any change to how bands
  are built, placed, styled or carried across a system switch is verified in
  the viewer as well as by `tests/test_band_flatness.py`,
  `tests/test_system_switch.py` and `tests/test_browser.py`.
- **Two equations exist twice**, in Python and in JavaScript: the band equation
  (`mechanics/solvent_bands.py`, `viz/band_kit.js`) and Kepler's equation
  (`mechanics/kepler.py`, `viz/three_viewer.js`). Change both.
- **The layers stay apart:** data sources produce `KeplerianElements`,
  mechanics is pure math, and the viz layer knows only positions.

```bash
pip install -r requirements-dev.txt
pytest                     # about 7 minutes
pytest -m "not browser"    # without the Playwright tests
```
