# Contributing to hybrasil

Thank you for helping. Corrections to the data are the most valuable thing
anyone can send, and you need neither a GitHub account nor any code to send
one.

## Ways to help

- **Suggest Changes, in the map.** Open <https://hybrasil.app>, pick the system,
  and press **Suggest Changes** on the toolbar or in a body's info panel. Name
  the value, what it should be, and where that number comes from. No account
  is needed. Every suggestion is read and checked by hand, and none is
  published.
- **An issue.** Use the **Data correction**, **New system** or **Bug**
  template.
- **A pull request** for code, documentation or tests (see below).

## Changing the data

The dataset is kept in a private spreadsheet, which is the single source of
truth. The snapshot in `data/` is exported from it, and the site is
built from that snapshot. That is why a pull request that edits the snapshot
directly cannot be merged as it stands: the next export would overwrite it.
Instead, a data change goes like this:

1. You propose it, through Suggest Changes, an issue, or a pull request that
   explains the change.
2. The maintainer checks the source and enters the value in the spreadsheet,
   recording where it came from.
3. The next snapshot is exported automatically and opened as a pull request
   that shows every value that changed. Once that is reviewed and merged, the
   site is rebuilt with your change.

What makes a proposal easy to accept:

- **One source per value**, specific enough to find the number: the paper with
  its table or section, or the catalogue and the row. A link to the paper's
  DOI or its ADS entry is ideal.
- **Primary sources over aggregators.** A Wikipedia figure is welcome as a
  lead, but the citation Wikipedia gives for it is what counts.
- **Measured over inferred.** If your number is derived (a fitted relation, or
  arithmetic on published values), say how, so it can be reproduced.

In the dataset, two border colours flag values that need a second look:

| Colour | Means |
| --- | --- |
| Pink | Copied from Wikipedia. Check the source Wikipedia cites. |
| Orange | Inferred, not measured. Check the method. |

Replacing a pink or orange value with a measured one from a primary source is
one of the most useful corrections there is.

One definition is fixed: a star fuses hydrogen, now or in the past (white
dwarfs count). A brown dwarf is listed as a planet, whatever its mass.

## Changing the code

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium   # once, for the browser tests

pytest                     # everything, about 7 minutes
pytest -m "not browser"    # skip the Playwright tests
```

- Read `CLAUDE.md` and the deep dive in `docs/architecture/` for the area you
  are changing. They record rules that the tests alone do not show.
- **A solvent band must always draw as a flat disc.** If your change touches
  how bands are built, styled or carried across a system switch, run
  `tests/test_band_flatness.py`, `tests/test_system_switch.py` and
  `tests/test_browser.py`, then open the viewer and look at it.
- Two pieces of physics exist twice, in Python and in JavaScript: the band
  equation (`mechanics/solvent_bands.py` and `viz/band_kit.js`) and Kepler's
  equation (`mechanics/kepler.py` and `viz/three_viewer.js`). Change both, and
  the tests will check that they agree.
- Keep the layers apart: data sources produce `KeplerianElements`, mechanics
  is pure math, and the viz layer knows only positions.

## Sign your commits (DCO)

Every commit must carry a sign-off certifying the
[Developer Certificate of Origin](https://developercertificate.org/), that is,
that you wrote the change or otherwise have the right to submit it under the
project's licences. Add it with `-s`:

```bash
git commit -s -m "Fix the period of HD 219134 h"
```

which appends a line with your name and email:

```
Signed-off-by: Your Name <you@example.com>
```

GitHub's noreply address is fine for this.

## Licences of contributions

Code you contribute is licensed under AGPL-3.0-or-later (`LICENSE`). Data you
contribute is licensed under CC BY-SA 4.0 (`LICENSE-DATA`). See `NOTICE`.

## Conduct

Everyone taking part agrees to the [Code of Conduct](CODE_OF_CONDUCT.md).
Questions about it, or reports, go to <cade@hybrasil.app>.
