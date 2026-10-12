# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared paths, sheet access and resumable state for the Known within 100ly motion pipeline.

Every step records itself in progress.json; status.py reads it and says what to run next. Nothing here writes to the
sheet -- write.py is the only writer.
"""
import datetime
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KNOWN = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

CAT = HERE / "cat"
AGENT_OUT = KNOWN / "agent_output"
PROGRESS = HERE / "progress.json"
TARGETS = HERE / "targets.json"
MERGED = HERE / "merged.json"
BATCHES = HERE / "batches.json"
WRITE_LOG = HERE / "write_log.json"

KN, SP, WIKI = "Known within 100ly", "Sources & Provenance", "Wikipedia sources"
GREY_RULE = "FFBFBFBF"
BATCH_CAP = 30                    # agent batches before the run pauses for the user (decided 2026-10-08)
BATCH_SIZE = 100
MAX_PARALLEL = 6                  # the unconfirmed_search lesson: more than this and none finish

H_NAME, H_PLOT, H_UPD, H_DIST = "System / Host", "Plotted", "Last Updated", "Distance (ly)"
H_RV, H_PMRA, H_PMDE = "Radial velocity (km/s)", "Proper motion in RA, μα·cos δ (mas/yr)", "Proper motion in Dec, μδ (mas/yr)"
H_MU, H_V = "Total proper motion, μ (arcsec/yr)", "Space velocity (km/s)"
H_L, H_B = "Galactic longitude l (deg)", "Galactic latitude b (deg)"
H_ML, H_MB = "Motion toward l (deg, heliocentric)", "Motion toward b (deg, heliocentric)"
H_KS, H_SID, H_RA, H_DE = "Kinematics source", "Gaia DR3 source_id", "RA (deg, ICRS)", "Dec (deg, ICRS)"
MEASURED = (H_RV, H_PMRA, H_PMDE)
DERIVED = (H_MU, H_V, H_L, H_B, H_ML, H_MB)
TARGET_COLS = MEASURED + DERIVED


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def load(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default


def save(path, obj):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    for attempt in range(20):            # OneDrive briefly locks a file it is syncing
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(1.5)


def progress():
    return load(PROGRESS, {"phases": {}, "batches": {}})


def mark(phase, state, **info):
    p = progress()
    p["phases"][phase] = {"state": state, "at": now(), **info}
    save(PROGRESS, p)


def done(phase):
    return progress()["phases"].get(phase, {}).get("state") == "done"


def num(v):
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


# ---- sheet access (read helpers; the 429 wrapper is installed on import) -------------------------------------

def q(t):
    return "'" + t.replace("'", "''") + "'"


def letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


_retry_installed = False


def sheets():
    """(gs module, spreadsheet id, API) with a retry on 429 and transient 5xx, as build.py does."""
    global _retry_installed
    from hybrasil.data import google_sheets as gs
    if not _retry_installed:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import HttpRequest
        _execute = HttpRequest.execute

        def _execute_with_retry(self, *a, **k):
            for attempt in range(10):
                try:
                    return _execute(self, *a, **k)
                except HttpError as e:
                    if e.resp.status not in (429, 500, 502, 503) or attempt == 9:
                        raise
                    time.sleep(35)
        HttpRequest.execute = _execute_with_retry
        _retry_installed = True
    sid = gs.resolve_spreadsheet_id()
    return gs, sid, gs._sheets_api()


def read_known(api, sid):
    """(headers, rows) of the live Known tab, unformatted; rows padded to the header width."""
    vals = api.values().get(spreadsheetId=sid, range=f"{q(KN)}!A1:AZ20000",
                            valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
    h = [str(x).strip() for x in vals[0]]
    rows = [list(r) + [""] * (len(h) - len(r)) for r in vals[1:]]
    return h, rows


def row_key(name, gaia):
    """A row's identity: its name, plus its Gaia id where it has one. Never its row number."""
    g = str(gaia).strip() if gaia not in (None, "") else ""
    return f"{str(name).strip()}|{g if g.isdigit() else ''}"


# Rows renamed on the tab after targets.json was frozen (identity.py, 2026-10-09): live key -> the pipeline's key, so
# targets, batches, agent files and merged.json keep the key they were made with.
RENAMED = {
    "GJ 4378 A|2421080250237097344": "GJ 4378 B|2421080250237097344",
    "GJ 4379 B|2421080250237474176": "GJ 4379 A|2421080250237474176",
    "GJ 257 B|5559035514779971456": "GJ 257 A|5559035514779971456",
    "GJ 10808 B|287767756635519488": "GJ 10808|287767756635519488",
    "GJ 10808 A|287767760932246144": "Gaia DR3 287767760932246144|287767760932246144",
}


def live_key(name, gaia):
    """row_key() of a live row, mapped back through RENAMED to the key the pipeline knows it by."""
    k = row_key(name, gaia)
    return RENAMED.get(k, k)
