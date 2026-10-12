# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Suggest Changes: submissions recorded for review, never written to the workbook.

A visitor names a system (any, including one the project has no data on yet),
any number of objects (new ones too), what should change, and the sources for
it, with an optional name and email for a follow-up.  Each submission is a
record in a store of its own:

    the hosted site     Cloudflare D1, through functions/api/suggestions.js
    --serve             a JSON-lines file, suggestions_file()

Nothing here imports google_sheets or holds a credential for it.  Whether a
suggestion reaches the workbook is decided by a person, after checking its
sources -- docs/architecture/suggestions.md.

The limits live in suggestion_rules.json, shared with the function and the
form; `validate()` is the Python twin of suggest_validate.js, and
tests/test_suggestions.py runs both on the same cases.
"""

from __future__ import annotations

import csv
import json
import os
import re
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

RULES_PATH = Path(__file__).with_name("suggestion_rules.json")
VALIDATE_JS_PATH = Path(__file__).with_name("suggest_validate.js")
RULES = json.loads(RULES_PATH.read_text(encoding="utf-8"))

# The columns a record has, in the order an export writes them.  The D1 table
# (migrations/0001_suggestions.sql) has the same names.
COLUMNS = ["id", "created_at", "status", "system", "system_id", "objects", "description",
           "sources", "name", "email", "site_build", "reviewer_note"]

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _msg(key: str, field: dict, **extra) -> str:
    m = RULES["messages"][key]
    for k, v in {**field, **extra}.items():
        m = m.replace("{" + k + "}", str(v))
    return m


def validate(payload, rules: dict = RULES) -> tuple[dict, dict]:
    """(clean, errors) for a submission, exactly as suggest_validate.js computes them."""
    errors: dict[str, str] = {}
    clean: dict = {}
    obj = payload if isinstance(payload, dict) else {}
    for name, f in rules["fields"].items():
        raw = obj.get(name)
        if f["type"] == "list":
            if raw is None:
                items = []
            elif isinstance(raw, str):
                items = re.split(r"\r?\n", raw)
            elif isinstance(raw, list):
                items = raw
            else:
                errors[name] = _msg("not_list", f)
                continue
            if any(not isinstance(x, str) for x in items):
                errors[name] = _msg("not_list", f)
                continue
            items = [x.strip() for x in items if x.strip()]
            clean[name] = items
            if f.get("required") and not items and not f.get("min_items"):
                errors[name] = _msg("required", f)
            elif f.get("min_items") and len(items) < f["min_items"]:
                errors[name] = _msg("too_few", f)
            elif f.get("max_items") and len(items) > f["max_items"]:
                errors[name] = _msg("too_many", f)
            else:
                long = next((i for i, x in enumerate(items) if len(x) > f["max"]), None)
                if long is not None:
                    errors[name] = _msg("item_long", f, n=long + 1)
        else:
            if raw is not None and not isinstance(raw, str):
                errors[name] = _msg("not_text", f)
                continue
            v = (raw or "").strip()
            clean[name] = v
            if not v:
                if f.get("required"):
                    errors[name] = _msg("required", f)
                continue
            if f.get("min") and len(v) < f["min"]:
                errors[name] = _msg("too_short", f)
            elif f.get("max") and len(v) > f["max"]:
                errors[name] = _msg("too_long", f)
            elif f["type"] == "email" and not _EMAIL.fullmatch(v):
                errors[name] = _msg("not_email", f)
    first = rules["one_of"][0]
    if not any(clean.get(n) for n in rules["one_of"]) and first not in errors:
        errors[first] = _msg("one_of", {})
    return clean, errors


# ── The --serve store ───────────────────────────────────────────────────────

def suggestions_file() -> Path:
    """Where --serve records submissions: $HYBRASIL_SUGGESTIONS_FILE, else beside the catalog cache."""
    override = os.environ.get("HYBRASIL_SUGGESTIONS_FILE")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "hybrasil" / "suggestions.jsonl"


def new_record(clean: dict) -> dict:
    """A record for a validated submission: an id, a time, and status 'new'."""
    rec = {c: "" for c in COLUMNS}
    rec.update({"objects": [], "sources": []}, **{k: v for k, v in clean.items() if k in rec})
    rec["id"] = str(uuid.uuid4())
    rec["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    rec["status"] = "new"
    return rec


def record_local(clean: dict, path: Optional[Path] = None) -> dict:
    """Append one validated submission to the local store; return its record."""
    rec = new_record(clean)
    path = Path(path) if path else suggestions_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_local(path: Optional[Path] = None) -> list[dict]:
    path = Path(path) if path else suggestions_file()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── The hosted store, read for review ───────────────────────────────────────

D1_QUERY_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{database}/query"


def load_remote(account: Optional[str] = None, database: Optional[str] = None,
                token: Optional[str] = None) -> list[dict]:
    """Every record in the D1 database, oldest first, through Cloudflare's REST API.

    The identifiers and the token come from the environment
    ($CLOUDFLARE_ACCOUNT_ID, $HYBRASIL_D1_DATABASE_ID, $CLOUDFLARE_API_TOKEN)
    and are never written anywhere.  The token needs D1 read access only.
    """
    account = account or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    database = database or os.environ.get("HYBRASIL_D1_DATABASE_ID")
    token = token or os.environ.get("CLOUDFLARE_API_TOKEN")
    missing = [n for n, v in (("CLOUDFLARE_ACCOUNT_ID", account), ("HYBRASIL_D1_DATABASE_ID", database),
                              ("CLOUDFLARE_API_TOKEN", token)) if not v]
    if missing:
        raise RuntimeError("Reading the hosted suggestions needs " + ", ".join(missing)
                           + " in the environment")
    body = json.dumps({"sql": f"SELECT {', '.join(COLUMNS)} FROM suggestions ORDER BY created_at"})
    req = urllib.request.Request(
        D1_QUERY_URL.format(account=account, database=database), data=body.encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    if not data.get("success"):
        raise RuntimeError(f"Cloudflare refused the query: {data.get('errors')}")
    rows = data["result"][0]["results"]
    for row in rows:                 # the function stores the lists as JSON text
        for k in ("objects", "sources"):
            if isinstance(row.get(k), str):
                try:
                    row[k] = json.loads(row[k])
                except json.JSONDecodeError:
                    pass
    return rows


def write_csv(records: Iterable[dict], path) -> int:
    """One row per suggestion, lists as one entry per line in their cell."""
    n = 0
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for rec in records:
            w.writerow(["\n".join(v) if isinstance(v, list) else ("" if v is None else v)
                        for v in (rec.get(c) for c in COLUMNS)])
            n += 1
    return n
