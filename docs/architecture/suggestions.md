# Suggest Changes: submissions for review

Visitors can propose a correction or an addition from the viewer. A
suggestion is **a record for review, never an edit**. Nothing on its path can
write to the catalog workbook. Whether it reaches the sheet is decided by a
person, after checking its sources, and then made by hand under
`docs/hybrasil-instructions.md`.

## What a suggestion holds

| Field | Rule |
|---|---|
| System | free text, up to 200 characters. Any system: one the map has (a featured system, the Sgr A* Cluster, Nearby Stellar Motion, a catalog system) or one it has never heard of |
| Object(s) | 0–50 lines. New objects are welcome, so nothing is matched against the catalog |
| What should change | required, 10–5000 characters |
| Source(s) | required, 1–20 lines of up to 500 characters: a paper, DOI, catalogue or URL |
| Name, Email | optional; private, used only to follow up |

A suggestion must name a system or at least one object. The page also sends
`system_id`, the matching id when the typed system is one the map has, and
`site_build`, the workbook version the page was built from.

**One copy of the rules.** `hybrasil/web/suggestion_rules.json` holds every
limit and message, and three things read it:

- `hybrasil/web/suggest_validate.js` checks it in the form and in the
  Cloudflare function. It is an ES module because the function imports it.
  The page gets it inline as a classic script with its `export` keywords
  stripped (`three_viewer.py`, `suggest_script()`).
- `hybrasil/web/suggestions.py`, `validate()`, is the Python twin used by
  `--serve`. `tests/test_suggestions.py::TestOneSetOfChecks` runs both on
  one table of cases, so they cannot drift.

## Where they go

```
Suggest Changes (toolbar, or an info panel's button)
   │  POST JSON to window.SA3_SUGGEST_URL
   ├─ hosted site:  api/suggestions → functions/api/suggestions.js → Cloudflare D1 (private)
   └─ --serve:      /api/suggestions → suggestions.record_local() → suggestions.jsonl
```

- **Hosted** (`functions/api/suggestions.js`, a Cloudflare Pages Function):
  - The request must be a same-origin POST of JSON within the size limit.
  - A Turnstile token must verify against `TURNSTILE_SECRET`.
  - The submission must pass the rules.
  - The sender must have sent fewer than 5 this hour and 20 today.
  - The sender's address is kept only as `SHA-256(IP_SALT + address)`.
  - With any secret or the database missing, the function refuses everything
    (503).
  - It imports nothing but the rules and the validator, and calls nothing but
    Turnstile. A test pins both.
- **`--serve`** appends JSON lines to `%LOCALAPPDATA%\hybrasil\suggestions.jsonl`
  (`~/.local/share/hybrasil/` elsewhere, or `$HYBRASIL_SUGGESTIONS_FILE`).
  It has no Turnstile and no rate limit, because it is a local tool.
- **A file page** (`--output html`, the CLI's browser launch) has nowhere to
  send a suggestion and shows no button.

The table is `migrations/0001_suggestions.sql`. Each record has `status`
`new` → `verified` / `rejected` / `applied`, and a `reviewer_note`.

## Reviewing

```bash
# Hosted: needs CLOUDFLARE_ACCOUNT_ID, HYBRASIL_D1_DATABASE_ID and a D1-only
# CLOUDFLARE_API_TOKEN in the environment (never in a file).
python -m hybrasil.cli --export-suggestions review.csv
# What --serve recorded:
python -m hybrasil.cli --export-suggestions review.csv --suggestions-from local

# Mark one after checking its sources:
npx wrangler d1 execute hybrasil-suggestions --remote --command \
  "UPDATE suggestions SET status='verified', reviewer_note='matches Jenkins+2015' WHERE id='…'"
```

## Setup (once, before the first deploy)

In order:

1. `npx wrangler d1 create hybrasil-suggestions`. Keep the database id as
   the GitHub secret `D1_DATABASE_ID`.
2. `npx wrangler d1 migrations apply hybrasil-suggestions --remote`.
3. Create a Turnstile widget for `hybrasil.app`. Its **site key** is public;
   give it to the build as `HYBRASIL_TURNSTILE_SITEKEY`. Its **secret key**
   becomes a Pages secret: `npx wrangler pages secret put TURNSTILE_SECRET`.
4. `npx wrangler pages secret put IP_SALT`, with a long random string.
5. The deploy workflow (`.github/workflows/pages.yml`) writes `wrangler.toml`
   from `wrangler.example.toml` and `D1_DATABASE_ID`, so no Cloudflare
   identifier is committed. `wrangler.toml` is git-ignored.
6. The same workflow runs `d1 migrations apply --remote` before every deploy.
   It is idempotent, so a new file in `migrations/` reaches the database with
   the commit that adds it. Step 2 is only the first run of it.

Before the first deploy, `npx wrangler pages dev site` with a local D1 runs
the function end to end. The tests run it under node with a fake database
and a fake Turnstile.
