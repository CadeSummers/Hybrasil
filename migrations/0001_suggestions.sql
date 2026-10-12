-- SPDX-FileCopyrightText: 2026 Cade Summers
-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Suggest Changes submissions, for review (docs/architecture/suggestions.md).
-- Applied with:  npx wrangler d1 migrations apply hybrasil-suggestions --remote
-- Lists (objects, sources) are JSON text.  ip_hash is SHA-256 of a secret salt
-- and the sender's address; the address itself is never stored.

CREATE TABLE suggestions (
  id            TEXT PRIMARY KEY,
  created_at    TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'new'
                CHECK (status IN ('new', 'verified', 'rejected', 'applied')),
  system        TEXT NOT NULL DEFAULT '',
  system_id     TEXT NOT NULL DEFAULT '',
  objects       TEXT NOT NULL DEFAULT '[]',
  description   TEXT NOT NULL,
  sources       TEXT NOT NULL DEFAULT '[]',
  name          TEXT NOT NULL DEFAULT '',
  email         TEXT NOT NULL DEFAULT '',
  site_build    TEXT NOT NULL DEFAULT '',
  ip_hash       TEXT NOT NULL,
  reviewer_note TEXT NOT NULL DEFAULT ''
);

CREATE INDEX suggestions_by_sender ON suggestions (ip_hash, created_at);
CREATE INDEX suggestions_by_status ON suggestions (status, created_at);
