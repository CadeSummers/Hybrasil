# Star nicknames: what is left

Done on 26 Nov 2026 (`research.py`, `apply.py`): the Systems, Multi-stars and Planetless 4+ Stars
tabs. Two things were left for later.

## 1. The Known within 100ly tab

- 10,711 rows. It has the two new headers (`Nicknames`, `IAU official designation`) and its 23
  IAU names were moved across, but no names were researched for it.
- Method: the same as `research.py`. Its SIMBAD download (every object with a parallax over
  30 mas, with all identifiers) already covers almost every row, so the work is matching the
  tab's names to it, then the IAU catalogue by HIP / HD number.
- Rows that are also Systems rows should take the Systems row's cell as it stands.
- Expect well-known stars that are on no other tab: Sirius, Procyon, Vega, Altair, Fomalhaut.
- The code does not read this tab's nicknames. The Nearby Stellar Motion view's cloud points
  are searched by name only, so finding them by nickname is a code change as well.

## 2. Catalogue cross-identifiers

- Asked for by the owner: HD, HIP, HR, GJ, Gaia DR3, 2MASS, TIC and similar for every star, so
  the model can be reached from other bodies of work.
- Likely its own column or tab, not the Nicknames cell: a star has dozens.
- Source: SIMBAD's `ids` table, which `research.py` already downloads.

## Known oddity

- `tet Cyg` (Systems tab) and `13 Cyg` (Planetless 4+ Stars) are the same star under two
  names: see `collisions.md`. Not resolved.
