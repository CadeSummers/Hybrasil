# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Google Sheets API access for the star catalog workbook.

I/O only: resolve credentials, pull every tab's raw cell values, cache them on
disk.  Nothing in here knows what the columns mean -- that is catalog_loader's
job.  Keeping the split lets the parser be tested without a network or a
credential file.

Credential resolution order (first hit wins):
  1. $HYBRASIL_GOOGLE_CREDENTIALS          -- path to a JSON key file
  2. <config>/hybrasil/service_account.json
  3. <config>/hybrasil/oauth_client.json   -- installed-app flow, token
                                                   cached beside it

A service-account key is the least-effort option for a private sheet: share
the sheet with the account's client_email as a Viewer and no browser flow is
ever needed.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

# The workbook is private, so its ID is not in the source.  Give it per-run
# with --sheet-id, globally with $HYBRASIL_SHEET_ID, or once in this file in
# config_dir(), beside the credential.
SHEET_ID_FILE = "sheet_id.txt"

# Read/write.  The catalog itself only reads, but edits to the workbook are
# made through this module too, and the Sheets API offers no narrower scope
# that permits writing.  docs/hybrasil-instructions.md governs those edits.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Cached tab values are reused for this long before a refetch is attempted.
DEFAULT_TTL_SECONDS = 24 * 3600

_SETUP_HELP = """
Google Sheets access is not configured.  Pick one:

  Service account (recommended -- no browser, keeps the sheet private)
    1. In the Google Cloud console, enable the Google Sheets API and create a
       service account with a JSON key.
    2. Save the key as:
         {config}/service_account.json
       or point $HYBRASIL_GOOGLE_CREDENTIALS at it.
    3. Share the spreadsheet with the key's "client_email" as an Editor.

  OAuth client (signs in as you, opens a browser once)
    1. Create a Desktop-app OAuth client and download its JSON.
    2. Save it as:
         {config}/oauth_client.json
    3. The first run opens a browser; the token is cached alongside it.

Install the client libraries with:
    pip install google-api-python-client google-auth google-auth-oauthlib
""".strip()

_NO_SHEET_HELP = """
No spreadsheet ID is configured.  Pick one:
  - pass --sheet-id <id or URL>
  - set $HYBRASIL_SHEET_ID
  - save the ID or URL in {path}
""".strip()


def resolve_spreadsheet_id(explicit: Optional[str] = None) -> str:
    """Return the spreadsheet ID to use, honouring overrides.

    Accepts a bare ID or a full Google Sheets URL.  Raises RuntimeError when
    none is configured, the way a missing credential does.
    """
    raw = explicit or os.environ.get("HYBRASIL_SHEET_ID") or _sheet_id_from_file()
    if not raw:
        raise RuntimeError(_NO_SHEET_HELP.format(path=config_dir() / SHEET_ID_FILE))
    raw = raw.strip()
    if "/spreadsheets/d/" in raw:
        raw = raw.split("/spreadsheets/d/", 1)[1].split("/", 1)[0]
    return raw


def _sheet_id_from_file() -> Optional[str]:
    try:
        return (config_dir() / SHEET_ID_FILE).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def spreadsheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


# --------------------------------------------------------------------------
# Filesystem locations
# --------------------------------------------------------------------------

def config_dir() -> Path:
    override = os.environ.get("HYBRASIL_CONFIG_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "hybrasil"


def cache_dir() -> Path:
    override = os.environ.get("HYBRASIL_CACHE_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "hybrasil" / "catalog"


def cache_path(spreadsheet_id: str) -> Path:
    return cache_dir() / f"{spreadsheet_id}.json"


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------

def _credential_file() -> Optional[Path]:
    env = os.environ.get("HYBRASIL_GOOGLE_CREDENTIALS")
    if env:
        p = Path(env)
        if not p.exists():
            raise FileNotFoundError(
                f"HYBRASIL_GOOGLE_CREDENTIALS points at a missing file: {p}"
            )
        return p
    for name in ("service_account.json", "oauth_client.json"):
        p = config_dir() / name
        if p.exists():
            return p
    return None


def _load_credentials():
    """Build a google.auth credentials object, or raise with setup guidance."""
    path = _credential_file()
    if path is None:
        raise RuntimeError(_SETUP_HELP.format(config=config_dir()))

    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Could not read credentials at {path}: {e}") from e

    if blob.get("type") == "service_account":
        try:
            from google.oauth2 import service_account
        except ImportError as e:
            raise ImportError(
                "google-auth is required: pip install google-auth google-api-python-client"
            ) from e
        return service_account.Credentials.from_service_account_file(
            str(path), scopes=SCOPES
        )

    if "installed" in blob or "web" in blob:
        return _oauth_credentials(path)

    raise RuntimeError(
        f"{path} is neither a service-account key nor an OAuth client file.\n\n"
        + _SETUP_HELP.format(config=config_dir())
    )


def _oauth_credentials(client_path: Path):
    """Installed-app OAuth flow with an on-disk token cache."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise ImportError(
            "google-auth-oauthlib is required for the OAuth flow: "
            "pip install google-auth-oauthlib"
        ) from e

    token_path = client_path.with_name("oauth_token.json")
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        # A token cached before SCOPES widened still carries the old grant, and
        # creds.valid only checks expiry. Without this the first write fails
        # with an opaque 403 instead of re-prompting for consent.
        if creds is not None and not creds.has_scopes(SCOPES):
            creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
        creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        os.chmod(token_path, 0o600)
    except OSError:
        pass
    return creds


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def _quote_range(title: str) -> str:
    """A1 range covering a whole tab, with the title safely quoted."""
    escaped = title.replace("'", "''")
    return "'" + escaped + "'"


def _sheets_api():
    """An authenticated spreadsheets() handle, or a setup error."""
    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ImportError(
            "google-api-python-client is required for --source catalog:\n"
            "    pip install google-api-python-client google-auth google-auth-oauthlib"
        ) from e

    creds = _load_credentials()
    return build("sheets", "v4", credentials=creds,
                 cache_discovery=False).spreadsheets()


def fetch_workbook(spreadsheet_id: str) -> dict:
    """Pull every tab from the spreadsheet.

    Returns a dict shaped:
        {"spreadsheet_id": str, "title": str, "fetched_at": float,
         "tabs": {tab_title: [[cell, ...], ...]}}

    Raises RuntimeError/ImportError with setup guidance if credentials or the
    client libraries are missing.
    """
    sheets_api = _sheets_api()

    meta = sheets_api.get(
        spreadsheetId=spreadsheet_id,
        fields="properties.title,sheets.properties.title",
    ).execute()

    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if not titles:
        raise RuntimeError(f"Spreadsheet {spreadsheet_id} has no tabs.")

    result = sheets_api.values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=[_quote_range(t) for t in titles],
        valueRenderOption="UNFORMATTED_VALUE",
        dateTimeRenderOption="FORMATTED_STRING",
    ).execute()

    tabs: dict[str, list] = {}
    for title, block in zip(titles, result.get("valueRanges", [])):
        tabs[title] = block.get("values", [])

    return {
        "spreadsheet_id": spreadsheet_id,
        "title": meta.get("properties", {}).get("title", ""),
        "fetched_at": time.time(),
        "tabs": tabs,
    }


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------

class CellMismatch(RuntimeError):
    """A guarded write found something other than the expected current value."""


def _as_grid(value) -> list[list]:
    """Normalise a scalar, a row, or a grid into the API's 2-D values shape."""
    if isinstance(value, list) and value and isinstance(value[0], list):
        return value
    if isinstance(value, list):
        return [value]
    return [[value]]


def read_cells(spreadsheet_id: str, ranges, formatted: bool = False) -> dict:
    """Values for specific A1 ranges, without pulling the whole workbook.

    Ranges are A1 notation, tab-qualified, e.g. "'Systems within 100 ly'!J4".
    Returns {range: [[cell, ...], ...]}; a range with no data maps to [].
    """
    ranges = list(ranges)
    if not ranges:
        return {}
    result = _sheets_api().values().batchGet(
        spreadsheetId=resolve_spreadsheet_id(spreadsheet_id),
        ranges=ranges,
        valueRenderOption="FORMATTED_VALUE" if formatted else "UNFORMATTED_VALUE",
        dateTimeRenderOption="FORMATTED_STRING",
    ).execute()
    blocks = result.get("valueRanges", [])
    return {rng: block.get("values", [])
            for rng, block in zip(ranges, blocks)}


def update_cells(spreadsheet_id: str, updates: dict,
                 expect: Optional[dict] = None,
                 value_input: str = "RAW") -> int:
    """Write values into specific A1 ranges. Returns the cell count written.

    Args:
        updates:     {A1 range: value}. A value may be a scalar, a row, or a grid.
        expect:      Optional {A1 range: current scalar value}. Every one is read
                     back and compared first, and a single mismatch aborts the
                     whole write. Rows shift; this is what stops an edit landing
                     on the wrong star.
        value_input: "RAW" writes the value literally. "USER_ENTERED" lets Sheets
                     reinterpret it, so a leading "=" becomes a formula and a
                     date-like string becomes a date. RAW is the safe default.

    Writing invalidates the local cache for this workbook, which would otherwise
    keep serving pre-write values for up to the TTL.
    """
    if not updates:
        return 0
    sid = resolve_spreadsheet_id(spreadsheet_id)

    if expect:
        current = read_cells(sid, list(expect))
        for rng, want in expect.items():
            grid = current.get(rng) or []
            got = grid[0][0] if grid and grid[0] else ""
            if got != want:
                raise CellMismatch(
                    f"{rng} holds {got!r}, expected {want!r}. Nothing was written."
                )

    result = _sheets_api().values().batchUpdate(
        spreadsheetId=sid,
        body={
            "valueInputOption": value_input,
            "data": [{"range": rng, "values": _as_grid(val)}
                     for rng, val in updates.items()],
        },
    ).execute()
    invalidate_cache(sid)
    return int(result.get("totalUpdatedCells", 0))


# --------------------------------------------------------------------------
# Formatting and naming
#
# Values alone cannot say where a value came from, so this workbook encodes
# provenance in the colour of a cell's border.  docs/hybrasil-instructions.md
# is the authority; what matters here is that the COLOUR carries the meaning,
# not the presence of a border -- thin grey rules and one dark-teal box already
# exist in the file and mean nothing of the kind.
# --------------------------------------------------------------------------

#: A value copied from Wikipedia.  Check the citation underneath before use.
WIKIPEDIA_BORDER = "FFFF3399"

#: A value from an inferred calculation that no one has peer reviewed -- a
#: relation fitted here, or arithmetic on published inputs.  Not a published
#: measurement, and the Sources & Provenance entry must say how it was derived.
INFERRED_BORDER = "FFFF9900"

#: The plain thin rule an unmarked cell wears in this workbook's data columns.
#: Unmarking a cell means restoring THIS, not removing the border: clearing to
#: nothing leaves a visible gap where its neighbours have a rule.
PLAIN_RULE = "000000"

_BORDER_SIDES = ("top", "bottom", "left", "right")


def _column_index(letters: str) -> int:
    """'A' -> 0, 'Z' -> 25, 'AA' -> 26."""
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def _sheet_ids(spreadsheet_id: str) -> dict:
    """{tab title: sheetId} for the workbook."""
    meta = _sheets_api().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties(title,sheetId)"
    ).execute()
    return {s["properties"]["title"]: s["properties"]["sheetId"]
            for s in meta.get("sheets", [])}


def _a1_to_grid_range(a1: str, sheet_ids: dict) -> dict:
    """Turn "'Tab'!P2" or "'Tab'!P2:Q4" into the API's GridRange shape."""
    if "!" not in a1:
        raise ValueError(f"range must name its tab: {a1!r}")
    title, cells = a1.split("!", 1)
    title = title.strip()
    if title.startswith("'") and title.endswith("'"):
        title = title[1:-1].replace("''", "'")
    if title not in sheet_ids:
        raise KeyError(f"no tab named {title!r}")

    start, _, end = cells.partition(":")
    end = end or start

    def split(ref):
        m = re.fullmatch(r"([A-Za-z]+)(\d+)", ref.strip())
        if not m:
            raise ValueError(f"unsupported cell reference: {ref!r}")
        return _column_index(m.group(1)), int(m.group(2)) - 1

    c0, r0 = split(start)
    c1, r1 = split(end)
    return {
        "sheetId": sheet_ids[title],
        "startRowIndex": min(r0, r1), "endRowIndex": max(r0, r1) + 1,
        "startColumnIndex": min(c0, c1), "endColumnIndex": max(c0, c1) + 1,
    }


def _hex_to_color(rgb: str) -> dict:
    """'FFFF9900' or 'FF9900' -> the API's {red, green, blue} floats."""
    h = rgb.lstrip("#").upper()
    if len(h) == 8:      # leading alpha, as the xlsx spells it
        h = h[2:]
    if len(h) != 6:
        raise ValueError(f"expected a 6- or 8-digit hex colour, got {rgb!r}")
    return {"red": int(h[0:2], 16) / 255.0,
            "green": int(h[2:4], 16) / 255.0,
            "blue": int(h[4:6], 16) / 255.0}


def set_border(spreadsheet_id: Optional[str], ranges, color: str,
               style: str = "SOLID_MEDIUM") -> int:
    """Put a coloured box round every cell in each A1 range.  Returns the count.

    Args:
        ranges: A1 ranges, tab-qualified, e.g. "'Multi-stars within 100 ly'!P2".
        color:  A hex string -- use WIKIPEDIA_BORDER or INFERRED_BORDER rather
                than a literal, so the meaning travels with the call.
        style:  A Sheets border style.  SOLID_MEDIUM is what this workbook's
                provenance markings use.

    Read a marking back with get_borders(), not with the values API, which
    returns values only.
    """
    ranges = list(ranges)
    if not ranges:
        return 0
    sid = resolve_spreadsheet_id(spreadsheet_id)
    ids = _sheet_ids(sid)
    side = {"style": style, "color": _hex_to_color(color)}
    requests = []
    for rng in ranges:
        req = {"range": _a1_to_grid_range(rng, ids)}
        req.update({s: dict(side) for s in _BORDER_SIDES})
        requests.append({"updateBorders": req})
    _sheets_api().batchUpdate(
        spreadsheetId=sid, body={"requests": requests}).execute()
    return len(ranges)


def _color_to_hex(color: Optional[dict]) -> Optional[str]:
    """The API's float colour back to 'RRGGBB'.  None when it is unset."""
    if not color:
        return None
    return "%02X%02X%02X" % tuple(
        int(round(color.get(k, 0.0) * 255)) for k in ("red", "green", "blue")
    )


def get_borders(spreadsheet_id: Optional[str], a1_range: str) -> dict:
    """Read back the border on every cell of one A1 range.

    Returns {A1 cell: {side: (hex colour or None, style)}}, with a cell omitted
    when it carries no border at all.  A colour of None is the default black
    that an unmarked cell wears -- see PLAIN_RULE.

    This reaches past the values API to spreadsheets.get(includeGridData=True),
    which is the only way to see formatting without exporting the file.  It is
    how a provenance marking is audited: docs/hybrasil-instructions.md section
    5 says which colour means what.
    """
    sid = resolve_spreadsheet_id(spreadsheet_id)
    ids = _sheet_ids(sid)
    grid = _a1_to_grid_range(a1_range, ids)
    result = _sheets_api().get(
        spreadsheetId=sid, ranges=[a1_range], includeGridData=True,
        fields="sheets/data/rowData/values/effectiveFormat/borders",
    ).execute()

    data = (result.get("sheets") or [{}])[0].get("data") or [{}]
    rows = data[0].get("rowData") or []
    col0 = grid["startColumnIndex"]
    row0 = grid["startRowIndex"]

    out = {}
    for dr, row in enumerate(rows):
        for dc, cell in enumerate(row.get("values") or []):
            borders = (cell.get("effectiveFormat") or {}).get("borders")
            if not borders:
                continue
            out[_grid_to_a1(col0 + dc, row0 + dr)] = {
                side: (_color_to_hex(spec.get("color")), spec.get("style"))
                for side, spec in borders.items()
            }
    return out


def _grid_to_a1(col: int, row: int) -> str:
    """(0, 0) -> 'A1'."""
    letters = ""
    n = col + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return f"{letters}{row + 1}"


def clear_border(spreadsheet_id: Optional[str], ranges) -> int:
    """Remove the box from every cell in each A1 range.  Returns the count.

    To UNMARK a cell in a data column, prefer
    ``set_border(..., PLAIN_RULE, style="SOLID")``.  The unmarked cells around
    it carry a thin rule rather than nothing, so removing the border outright
    leaves a hole in the grid.
    """
    ranges = list(ranges)
    if not ranges:
        return 0
    sid = resolve_spreadsheet_id(spreadsheet_id)
    ids = _sheet_ids(sid)
    none = {"style": "NONE"}
    requests = []
    for rng in ranges:
        req = {"range": _a1_to_grid_range(rng, ids)}
        req.update({s: dict(none) for s in _BORDER_SIDES})
        requests.append({"updateBorders": req})
    _sheets_api().batchUpdate(
        spreadsheetId=sid, body={"requests": requests}).execute()
    return len(ranges)


def set_note(spreadsheet_id: Optional[str], notes: dict) -> int:
    """Attach a hover note to cells.  {A1 cell: text}; "" removes the note.

    A border says a value is marked; a note says WHY, on the cell itself, where
    a reader meets it.  Every inferred cell should carry one -- its method in a
    line, and the word WEAK where the value rests on an assumption nothing
    measures.  The long form still belongs in Sources & Provenance.

    Notes travel with the cell when a sheet is sorted, which borders do not.
    """
    if not notes:
        return 0
    sid = resolve_spreadsheet_id(spreadsheet_id)
    ids = _sheet_ids(sid)
    requests = []
    for cell, text in notes.items():
        grid = _a1_to_grid_range(cell, ids)
        requests.append({"updateCells": {
            "range": grid,
            "rows": [{"values": [{"note": text}]}],
            "fields": "note",
        }})
    _sheets_api().batchUpdate(
        spreadsheetId=sid, body={"requests": requests}).execute()
    return len(notes)


def get_notes(spreadsheet_id: Optional[str], a1_range: str) -> dict:
    """Read notes back.  {A1 cell: text} for the cells that carry one."""
    sid = resolve_spreadsheet_id(spreadsheet_id)
    ids = _sheet_ids(sid)
    grid = _a1_to_grid_range(a1_range, ids)
    result = _sheets_api().get(
        spreadsheetId=sid, ranges=[a1_range], includeGridData=True,
        fields="sheets/data/rowData/values/note",
    ).execute()
    data = (result.get("sheets") or [{}])[0].get("data") or [{}]
    out = {}
    for dr, row in enumerate(data[0].get("rowData") or []):
        for dc, cell in enumerate(row.get("values") or []):
            if cell.get("note"):
                out[_grid_to_a1(grid["startColumnIndex"] + dc,
                                grid["startRowIndex"] + dr)] = cell["note"]
    return out


def versioned_title(when=None) -> str:
    """The workbook name for an edit made now: hybrasil-{YYYYMMDD}-{HHMM}.

    Local time, 24-hour clock, per docs/hybrasil-instructions.md rule 1.
    """
    stamp = time.localtime() if when is None else when
    return time.strftime("hybrasil-%Y%m%d-%H%M", stamp)


def rename_workbook(spreadsheet_id: Optional[str], title: str) -> str:
    """Rename the spreadsheet in place.  Returns the title that was set.

    A rename keeps the Drive file ID, so the configured ID stays valid --
    unlike making a new version, which does not.  Every edit session renames
    the workbook to versioned_title(); rule 1 of the instructions is why.
    """
    sid = resolve_spreadsheet_id(spreadsheet_id)
    _sheets_api().batchUpdate(
        spreadsheetId=sid,
        body={"requests": [{"updateSpreadsheetProperties": {
            "properties": {"title": title}, "fields": "title"}}]},
    ).execute()
    invalidate_cache(sid)
    return title


def invalidate_cache(spreadsheet_id: str) -> bool:
    """Drop the cached copy of a workbook. True if a file was removed."""
    path = cache_path(resolve_spreadsheet_id(spreadsheet_id))
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def load_cached(spreadsheet_id: str) -> Optional[dict]:
    path = cache_path(spreadsheet_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_cache(workbook: dict) -> Path:
    path = cache_path(workbook["spreadsheet_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(workbook), encoding="utf-8")
    return path


def get_workbook(
    spreadsheet_id: Optional[str] = None,
    refresh: bool = False,
    ttl_seconds: Optional[float] = None,
    offline: bool = False,
) -> dict:
    """Return workbook values, preferring a fresh cache over a network call.

    Args:
        spreadsheet_id: ID or URL; defaults to resolve_spreadsheet_id().
        refresh: Ignore the cache and refetch.
        ttl_seconds: Cache lifetime; defaults to $HYBRASIL_CATALOG_TTL
                     or 24 hours.
        offline: Never touch the network; fail if there is no cache.

    A failed fetch falls back to a stale cache when one exists, so a dropped
    connection degrades to slightly old data rather than an error.
    """
    sid = resolve_spreadsheet_id(spreadsheet_id)

    if ttl_seconds is None:
        env_ttl = os.environ.get("HYBRASIL_CATALOG_TTL")
        ttl_seconds = float(env_ttl) if env_ttl else DEFAULT_TTL_SECONDS

    cached = load_cached(sid)

    if offline:
        if cached is None:
            raise RuntimeError(
                f"No cached copy of spreadsheet {sid}; cannot run offline. "
                f"Run once without --offline to populate {cache_path(sid)}."
            )
        return cached

    fresh_enough = (
        cached is not None
        and not refresh
        and (time.time() - cached.get("fetched_at", 0)) < ttl_seconds
    )
    if fresh_enough:
        return cached

    try:
        workbook = fetch_workbook(sid)
    except Exception:
        if cached is not None:
            return cached
        raise

    save_cache(workbook)
    return workbook
