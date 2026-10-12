# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The committed workbook snapshot, read into the same shape as the live sheet.

`data/hybrasil-*.xlsx` is a supplementary copy of the catalog workbook
(data/README.md): the live Google Sheet is the source, and wins wherever the
two disagree.  This module is what lets the app run without a Google
credential -- the hosted site, the test suite, anyone who clones the repo --
and returns the ``{"title", "tabs"}`` dict that `catalog_loader.parse_workbook()`
already takes, so a snapshot parses exactly as the live sheet does.

Every workbook loader reads the live sheet and falls back to the snapshot;
``$HYBRASIL_DATA_SOURCE=snapshot`` skips the sheet altogether (`snapshot_only`).
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Set to "snapshot" to read the committed snapshot and never the live sheet:
# the static site build, offline work, and the test suite, which must not
# depend on a credential or the network.  The older name still works.
SOURCE_ENV = "HYBRASIL_DATA_SOURCE"
LEGACY_SOURCE_ENV = "HYBRASIL_NEARBY_SOURCE"


def snapshot_only() -> bool:
    """True when the environment asks for the snapshot instead of the live sheet."""
    raw = os.environ.get(SOURCE_ENV) or os.environ.get(LEGACY_SOURCE_ENV) or ""
    return raw.strip().lower() == "snapshot"


def latest_snapshot(data_dir: Optional[Path] = None) -> Optional[Path]:
    """The newest ``hybrasil-*.xlsx``, by the timestamp in its name."""
    files = sorted((data_dir or DATA_DIR).glob("hybrasil-*.xlsx"))
    return files[-1] if files else None


def load_snapshot_workbook(path: Optional[Path] = None) -> dict:
    """Every tab of a snapshot as rows of cell values, formulas as their cached values.

    Read once per file and process (it takes seconds, and four loaders want
    it), so the dict is shared: treat it as read-only.
    """
    path = Path(path) if path else latest_snapshot()
    if path is None or not path.exists():
        raise FileNotFoundError(f"No workbook snapshot in {DATA_DIR}")
    return _load(str(path.resolve()), path.stat().st_mtime)


@functools.lru_cache(maxsize=2)
def _load(path_str: str, mtime: float) -> dict:
    path = Path(path_str)
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        tabs = {ws.title: [["" if c is None else c for c in row]
                           for row in ws.iter_rows(values_only=True)]
                for ws in wb.worksheets}
    finally:
        wb.close()
    return {"spreadsheet_id": "", "title": path.stem, "fetched_at": mtime, "tabs": tabs}
