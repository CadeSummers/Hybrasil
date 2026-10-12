# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Re-export the workbook snapshot in data/ from the live sheet (data/README.md).

    python -m hybrasil.data.export_snapshot [--force]

Downloads Google's own xlsx conversion of the sheet, the same export the
README's step 9 describes, and replaces ``data/hybrasil-*.xlsx`` with it,
named after the workbook as it is called now.  The README's table row is
rewritten to match.

**Nothing changes when the content has not.**  Two exports of an unchanged
sheet differ byte for byte (an xlsx is a zip, and the zip carries
timestamps), so the comparison is on what the snapshot is for: every cell's
value, its provenance border colours, its fill and its note, tab by tab.  A
rename alone is no change either; every edit renames the sheet, so a new name
with old content means nothing was edited.

Credentials, in order:

- ``$HYBRASIL_GOOGLE_TOKEN``, an OAuth access token.  This is what
  ``.github/workflows/snapshot.yml`` passes: a short-lived token for the
  keyless, read-only service account, reached through Workload Identity
  Federation, scoped ``drive.readonly``: the export URL refuses
  ``spreadsheets.readonly`` (HTTP 401), though the title lookup takes it.
- otherwise the maintainer's local credential (`google_sheets._load_credentials`).

Under GitHub Actions it writes ``changed`` and ``title`` to ``$GITHUB_OUTPUT``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from . import google_sheets as gs
from .snapshot import DATA_DIR, latest_snapshot

TOKEN_ENV = "HYBRASIL_GOOGLE_TOKEN"
EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx"
TITLE_URL = "https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=properties.title"
README = "README.md"

# The README table row this script owns: the one naming the snapshot file.
_ROW = re.compile(r"^\| `hybrasil-[^`]+\.xlsx` \|.*$", re.MULTILINE)
# A workbook name that is safe as a file name and that latest_snapshot() finds.
_TITLE = re.compile(r"^hybrasil-\d{8}-\d{4}$")

Fetch = Callable[[str, str], bytes]


def _http_get(url: str, token: str) -> bytes:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def access_token() -> str:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if token:
        return token
    from google.auth.transport.requests import Request
    creds = gs._load_credentials()
    if not creds.valid:
        creds.refresh(Request())
    return creds.token


def fingerprint(path: Path) -> str:
    """A hash of what the snapshot is for, blind to how the zip was packed.

    Per tab, in order: every non-empty cell's coordinate, cached value, border
    colours, fill colour and note.  Formulas count through their cached
    values, which is what every loader reads (`snapshot.load_snapshot_workbook`).
    """
    import openpyxl

    def colour(c) -> str:
        # An rgb colour is a str; a theme or indexed one is not, and says which.
        if c is None:
            return ""
        return c.rgb if isinstance(c.rgb, str) else f"{c.type}:{c.theme}:{c.indexed}:{c.tint}"

    def side(s) -> str:
        return "" if s is None or s.style is None else f"{s.style}/{colour(s.color)}"

    h = hashlib.sha256()
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        for ws in wb.worksheets:
            h.update(f"\x00tab\x00{ws.title}\x00".encode())
            for row in ws.iter_rows():
                for cell in row:
                    b, f = cell.border, cell.fill
                    rec = (
                        "" if cell.value is None else repr(cell.value),
                        side(b.left), side(b.right), side(b.top), side(b.bottom),
                        colour(f.fgColor) if f.fill_type else "",
                        cell.comment.text if cell.comment else "",
                    )
                    if any(rec):
                        h.update(f"{cell.coordinate}\x00{rec!r}\x00".encode())
    finally:
        wb.close()
    return h.hexdigest()


def readme_row(name: str, title: str, exported: _dt.date) -> str:
    return (f"| `{name}` | `{title}` | private (`sheet_id.txt`) | {exported.isoformat()} "
            "| Google's xlsx export (`docs.google.com/spreadsheets/d/<id>/export?format=xlsx`), "
            "by `python -m hybrasil.data.export_snapshot` |")


def update_readme(readme: Path, row: str) -> None:
    text = readme.read_text(encoding="utf-8")
    new, n = _ROW.subn(row, text, count=1)
    if n != 1:
        raise RuntimeError(f"No snapshot row in {readme}'s table to replace")
    readme.write_text(new, encoding="utf-8", newline="\n")


def export(data_dir: Path = DATA_DIR, *, force: bool = False,
           sheet_id: Optional[str] = None, fetch: Optional[Fetch] = None,
           today: Optional[_dt.date] = None) -> dict:
    """Fetch the sheet; replace the snapshot if its content changed (or `force`).

    Returns ``{"changed", "title", "path"}``.  `fetch(url, token)` is the
    network, replaceable in tests.
    """
    sid = gs.resolve_spreadsheet_id(sheet_id)
    q = urllib.parse.quote(sid, safe="")
    if fetch is None:
        token = access_token()
        fetch = lambda url, _t=token: _http_get(url, _t)  # noqa: E731
    title = json.loads(fetch(TITLE_URL.format(sid=q)))["properties"]["title"]
    if not _TITLE.match(title):
        raise RuntimeError(f"Workbook name {title!r} is not hybrasil-YYYYMMDD-HHMM; "
                           "rename it (docs/hybrasil-instructions.md rule 1) and re-run")
    blob = fetch(EXPORT_URL.format(sid=q))

    old = latest_snapshot(data_dir)
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / f"{title}.xlsx"
        fresh.write_bytes(blob)
        if old is not None and not force and fingerprint(fresh) == fingerprint(old):
            return {"changed": False, "title": title, "path": old}
        target = data_dir / fresh.name
        target.write_bytes(blob)
    if old is not None and old.resolve() != target.resolve():
        old.unlink()
    update_readme(data_dir / README,
                  readme_row(target.name, title, today or _dt.datetime.now(_dt.timezone.utc).date()))
    return {"changed": True, "title": title, "path": target}


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m hybrasil.data.export_snapshot",
                                description=__doc__.split("\n\n")[0])
    p.add_argument("--force", action="store_true",
                   help="replace the snapshot even when its content is unchanged")
    p.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = p.parse_args(argv)

    result = export(args.data_dir, force=args.force)
    verdict = "updated" if result["changed"] else "no change"
    print(f"{verdict}: {result['title']} -> {result['path']}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if result['changed'] else 'false'}\n")
            fh.write(f"title={result['title']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
