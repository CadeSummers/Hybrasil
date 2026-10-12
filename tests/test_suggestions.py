# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Suggest Changes: the rules, the --serve endpoint, and the Cloudflare function.

The one property that matters most is pinned first: a suggestion is a record
for review, and nothing on its way there can write to the catalog workbook.
The function and the form share suggest_validate.js, and --serve has a Python
twin of it; the two are run here on the same cases so they cannot drift.
"""

import csv
import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from hybrasil.data import google_sheets
from hybrasil.cli import build_parser, main
from hybrasil.web import suggestions
from hybrasil.web.app import make_server
from hybrasil.web.suggestions import RULES, validate
from tests.test_static_site import small_library

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = ROOT / "functions" / "api" / "suggestions.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

GOOD = {
    "system": "Kepler-452",                        # a system the map does not have
    "objects": ["Kepler-452 b"],
    "description": "Add this planet; its radius and period are published.",
    "sources": ["Jenkins et al. 2015, AJ 150, 56", "https://doi.org/10.1088/0004-6256/150/2/56"],
}

# The same table runs through Python and through node: every rule, both ways.
CASES = [
    GOOD,
    {**GOOD, "objects": "Kepler-452 b\n\n  Kepler-452 c  \r\n"},   # lines, blanks dropped
    {**GOOD, "system": "", "objects": []},                            # neither system nor object
    {**GOOD, "system": "", "objects": ["New object"]},                # an object alone is enough
    {**GOOD, "description": "short"},
    {**GOOD, "description": "x" * 5001},
    {**GOOD, "description": None},
    {**GOOD, "sources": []},
    {**GOOD, "sources": "   \n  "},
    {**GOOD, "sources": ["s"] * 21},
    {**GOOD, "sources": ["s" * 501]},
    {**GOOD, "objects": ["o"] * 51},
    {**GOOD, "objects": ["ok", "o" * 201]},
    {**GOOD, "objects": [1, 2]},
    {**GOOD, "objects": {"a": 1}},
    {**GOOD, "system": 42},
    {**GOOD, "email": "not-an-address"},
    {**GOOD, "email": "  someone@example.org  ", "name": "  A. Person "},
    {**GOOD, "name": "n" * 101},
    {**GOOD, "system": "🌟" * 200},                                    # code points, not UTF-16 units
    {**GOOD, "system": "🌟" * 201},
    {**GOOD, "unexpected": "dropped", "turnstile": "token"},
    {},
    [],
    "text",
]


class TestTheRules:
    def test_a_system_and_object_the_map_does_not_have_are_accepted(self):
        clean, errors = validate(GOOD)
        assert errors == {} and clean["system"] == "Kepler-452"
        assert clean["objects"] == ["Kepler-452 b"] and len(clean["sources"]) == 2

    def test_lines_become_entries_and_blanks_go(self):
        clean, errors = validate({**GOOD, "sources": "a\n\n b \r\nc"})
        assert errors == {} and clean["sources"] == ["a", "b", "c"]

    @pytest.mark.parametrize("change,field", [
        ({"description": ""}, "description"),
        ({"sources": []}, "sources"),
        ({"system": "", "objects": []}, "system"),
        ({"email": "nope"}, "email"),
        ({"description": "x" * 5001}, "description"),
    ])
    def test_what_is_refused(self, change, field):
        assert field in validate({**GOOD, **change})[1]

    def test_unknown_fields_are_dropped(self):
        clean, _ = validate({**GOOD, "turnstile": "t", "admin": True})
        assert set(clean) == set(RULES["fields"])


@needs_node
class TestOneSetOfChecks:
    def test_the_function_and_python_agree_on_every_case(self, tmp_path):
        harness = tmp_path / "agree.mjs"
        harness.write_text(
            "import { pathToFileURL } from 'node:url';\n"
            "import fs from 'node:fs';\n"
            "const [validator, rules, cases] = process.argv.slice(2);\n"
            "const { validate } = await import(pathToFileURL(validator));\n"
            "const R = JSON.parse(fs.readFileSync(rules, 'utf8'));\n"
            "const C = JSON.parse(fs.readFileSync(cases, 'utf8'));\n"
            "console.log(JSON.stringify(C.map((c) => validate(c, R))));\n", encoding="utf-8")
        cases = tmp_path / "cases.json"
        cases.write_text(json.dumps(CASES), encoding="utf-8")
        out = subprocess.run([NODE, str(harness), str(suggestions.VALIDATE_JS_PATH),
                              str(suggestions.RULES_PATH), str(cases)],
                             capture_output=True, text=True, encoding="utf-8", check=True)
        js = json.loads(out.stdout)
        for case, got in zip(CASES, js):
            clean, errors = validate(case)
            assert got == {"clean": clean, "errors": errors}, case


# ── --serve's endpoint ──────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "suggestions.jsonl"
    monkeypatch.setenv("HYBRASIL_SUGGESTIONS_FILE", str(path))
    return path


@pytest.fixture
def no_sheet_writes(monkeypatch):
    """Any write to the workbook fails the test."""
    def forbidden(*a, **k):
        raise AssertionError("a suggestion reached the catalog workbook")
    for name in ("update_cells", "set_border", "clear_border", "set_note", "rename_workbook",
                 "fetch_workbook", "_sheets_api"):
        if hasattr(google_sheets, name):
            monkeypatch.setattr(google_sheets, name, forbidden)


@pytest.fixture(scope="module")
def server():
    srv = make_server(small_library(), "solar", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _post(url, body, ctype="application/json"):
    data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


class TestTheLocalEndpoint:
    def test_a_suggestion_is_recorded_and_the_workbook_is_untouched(self, server, store, no_sheet_writes):
        status, body = _post(server + "/api/suggestions", {**GOOD, "turnstile": "ignored here"})
        assert status == 201 and body["id"]
        [rec] = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
        assert rec["id"] == body["id"] and rec["status"] == "new"
        assert rec["system"] == "Kepler-452" and rec["objects"] == ["Kepler-452 b"]
        assert "turnstile" not in rec

    def test_an_invalid_one_names_its_fields_and_records_nothing(self, server, store):
        status, body = _post(server + "/api/suggestions", {**GOOD, "sources": []})
        assert status == 400 and "sources" in body["fields"]
        assert not store.exists()

    def test_not_json_is_refused(self, server, store):
        assert _post(server + "/api/suggestions", b"system=x", "application/x-www-form-urlencoded")[0] == 415
        assert _post(server + "/api/suggestions", b"{not json")[0] == 400
        assert _post(server + "/api/suggestions", [1, 2])[0] == 400
        assert not store.exists()

    def test_too_large_is_refused(self, server, store):
        big = {**GOOD, "description": "x" * (RULES["max_body_bytes"] + 10)}
        assert _post(server + "/api/suggestions", big)[0] == 413
        assert not store.exists()

    def test_only_that_path_takes_a_post_and_it_takes_nothing_else(self, server):
        assert _post(server + "/api/systems", GOOD)[0] == 404
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(server + "/api/suggestions", timeout=30)
        assert e.value.code == 405


class TestTheExport:
    def test_local_records_export_as_csv(self, tmp_path, store, capsys):
        suggestions.record_local(validate(GOOD)[0])
        suggestions.record_local(validate({**GOOD, "system": "Sgr A* Cluster (Galactic Center)"})[0])
        out = tmp_path / "review.csv"
        main(["--export-suggestions", str(out), "--suggestions-from", "local"])
        rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
        assert [r["system"] for r in rows] == ["Kepler-452", "Sgr A* Cluster (Galactic Center)"]
        assert rows[0]["sources"].split("\n") == GOOD["sources"]
        assert "2 suggestion(s)" in capsys.readouterr().out

    def test_remote_needs_its_three_settings(self, monkeypatch):
        for n in ("CLOUDFLARE_ACCOUNT_ID", "HYBRASIL_D1_DATABASE_ID", "CLOUDFLARE_API_TOKEN"):
            monkeypatch.delenv(n, raising=False)
        with pytest.raises(RuntimeError, match="CLOUDFLARE_ACCOUNT_ID"):
            suggestions.load_remote()

    def test_the_switches(self):
        args = build_parser().parse_args(["--export-suggestions", "x.csv"])
        assert args.export_suggestions == "x.csv" and args.suggestions_from == "remote"


# ── The Cloudflare function, under node with a fake D1 and Turnstile ───────

FUNCTION_HARNESS = r"""
import { pathToFileURL } from 'node:url';
import fs from 'node:fs';
const [fnPath, scenarioPath] = process.argv.slice(2);
const { handle, LIMITS } = await import(pathToFileURL(fnPath));
const scenarios = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));

function fakeDB(rows) {
  return {
    prepare(sql) {
      return {
        bind(...a) {
          return {
            async first() {
              const [hash, since] = a;
              return { n: rows.filter((r) => r[10] === hash && r[1] > since).length };
            },
            async run() { rows.push(a); return { success: true }; },
          };
        },
      };
    },
  };
}

const out = [];
for (const s of scenarios) {
  const rows = [];
  for (let i = 0; i < (s.prior || 0); i++) {
    rows.push(['p' + i, new Date(Date.now() - 60_000).toISOString(), '', '', '[]', '', '[]', '', '', '', s.priorHash]);
  }
  const env = s.env === null ? {} : { DB: fakeDB(rows), TURNSTILE_SECRET: 'secret', IP_SALT: 'salt', ...(s.env || {}) };
  for (const k of s.unset || []) delete env[k];
  let verified = null;
  const fetchImpl = async (url, init) => {
    verified = { url, secret: init.body.get('secret'), token: init.body.get('response'), ip: init.body.get('remoteip') };
    return new Response(JSON.stringify({ success: s.turnstileOk !== false }));
  };
  const headers = { 'Content-Type': s.ctype || 'application/json', 'CF-Connecting-IP': '203.0.113.7' };
  if (s.origin) headers.Origin = s.origin;
  const req = new Request('https://hybrasil.app/api/suggestions', {
    method: s.method || 'POST', headers,
    body: (s.method || 'POST') === 'GET' ? undefined : (typeof s.body === 'string' ? s.body : JSON.stringify(s.body)),
  });
  const r = await handle(req, env, { fetchImpl });
  out.push({ status: r.status, body: await r.json(), rows, verified, limits: LIMITS });
}
console.log(JSON.stringify(out));
"""


def _run_function(tmp_path, scenarios):
    harness = tmp_path / "fn.mjs"
    harness.write_text(FUNCTION_HARNESS, encoding="utf-8")
    sc = tmp_path / "scenarios.json"
    sc.write_text(json.dumps(scenarios), encoding="utf-8")
    out = subprocess.run([NODE, str(harness), str(FUNCTION), str(sc)],
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@needs_node
class TestTheFunction:
    def test_a_good_suggestion_is_stored_with_a_hash_not_the_address(self, tmp_path):
        [r] = _run_function(tmp_path, [{"body": {**GOOD, "turnstile": "tok"}}])
        assert r["status"] == 201 and r["body"]["id"]
        assert r["verified"]["secret"] == "secret" and r["verified"]["token"] == "tok"
        [row] = r["rows"]
        flat = json.dumps(row)
        assert "203.0.113.7" not in flat, "the sender's address was stored"
        # The INSERT's bound values, in order: id, created_at, system, system_id,
        # objects, description, sources, name, email, site_build, ip_hash.
        assert len(row[10]) == 64                          # sha-256 hex
        assert json.loads(row[4]) == ["Kepler-452 b"] and row[2] == "Kepler-452"

    def test_it_fails_closed_without_its_secrets_or_database(self, tmp_path):
        rs = _run_function(tmp_path, [
            {"body": {**GOOD, "turnstile": "t"}, "unset": ["TURNSTILE_SECRET"]},
            {"body": {**GOOD, "turnstile": "t"}, "unset": ["IP_SALT"]},
            {"body": {**GOOD, "turnstile": "t"}, "unset": ["DB"]},
        ])
        assert [r["status"] for r in rs] == [503, 503, 503]

    def test_the_bot_check_must_pass(self, tmp_path):
        rs = _run_function(tmp_path, [
            {"body": {**GOOD, "turnstile": "t"}, "turnstileOk": False},
            {"body": GOOD},                                 # no token at all
        ])
        assert [r["status"] for r in rs] == [403, 403] and not any(r["rows"] for r in rs)

    def test_requests_it_refuses(self, tmp_path):
        rs = _run_function(tmp_path, [
            {"method": "GET"},
            {"body": GOOD, "origin": "https://elsewhere.example"},
            {"body": "system=x", "ctype": "text/plain"},
            {"body": "{nope"},
            {"body": {**GOOD, "description": "x" * (RULES["max_body_bytes"] + 1)}},
            {"body": {**GOOD, "sources": [], "turnstile": "t"}},
        ])
        assert [r["status"] for r in rs] == [405, 403, 415, 400, 413, 400]
        assert "sources" in rs[-1]["body"]["fields"]

    def test_a_sender_is_limited(self, tmp_path):
        # Five from the same address in the last hour: the sixth is refused.
        import hashlib
        h = hashlib.sha256(b"salt203.0.113.7").hexdigest()
        rs = _run_function(tmp_path, [
            {"body": {**GOOD, "turnstile": "t"}, "prior": 4, "priorHash": h},
            {"body": {**GOOD, "turnstile": "t"}, "prior": 5, "priorHash": h},
            {"body": {**GOOD, "turnstile": "t"}, "prior": 5, "priorHash": "someone-else"},
        ])
        assert [r["status"] for r in rs] == [201, 429, 201]
        assert rs[0]["limits"] == {"hour": 5, "day": 20}

    def test_it_has_no_way_to_the_workbook(self):
        # Code, not comments: it imports only the rules and their validator,
        # and the only place it calls out to is Turnstile.
        import re
        code = "\n".join(line for line in FUNCTION.read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("//"))
        imports = re.findall(r"^import .* from '([^']+)'", code, re.M)
        assert imports == ["../../hybrasil/web/suggestion_rules.json", "../../hybrasil/web/suggest_validate.js"]
        assert re.findall(r"https://[^'\"\s]+", code) == [
            "https://challenges.cloudflare.com/turnstile/v0/siteverify"]
        assert "google" not in code.lower()
