// SPDX-FileCopyrightText: 2026 Cade Summers
// SPDX-License-Identifier: AGPL-3.0-or-later
// POST /api/suggestions on the hosted site: a Cloudflare Pages Function.
//
// Records one Suggest Changes submission in the D1 database bound as env.DB,
// for review -- docs/architecture/suggestions.md.  It has no Google credential
// and no binding to anything but that database, so it cannot touch the
// catalog workbook.
//
// Every request must:
//   - be a same-origin POST of JSON, no larger than the rules allow;
//   - carry a Cloudflare Turnstile token that verifies (env.TURNSTILE_SECRET);
//   - pass suggest_validate.js against suggestion_rules.json -- the very
//     rules the form and --serve use;
//   - come from an address that has sent fewer than 5 this hour and 20 today.
// The address is kept only as a salted hash (env.IP_SALT).  With any secret
// or the database missing, nothing is accepted.

import RULES from '../../hybrasil/web/suggestion_rules.json' with { type: 'json' };
import { validate } from '../../hybrasil/web/suggest_validate.js';

const TURNSTILE_VERIFY = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';
export const LIMITS = { hour: 5, day: 20 };

function json(status, body, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...extra },
  });
}

async function sha256hex(text) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function verifyTurnstile(token, secret, ip, fetchImpl) {
  if (!token || typeof token !== 'string') return false;
  const form = new FormData();
  form.append('secret', secret);
  form.append('response', token);
  if (ip) form.append('remoteip', ip);
  try {
    const r = await fetchImpl(TURNSTILE_VERIFY, { method: 'POST', body: form });
    const d = await r.json();
    return d.success === true;
  } catch (e) {
    return false;
  }
}

// The whole request, testable without Cloudflare: `now` and `fetchImpl` are
// injectable (tests/test_suggestions.py runs it under node).
export async function handle(request, env, { fetchImpl = fetch, now = () => new Date() } = {}) {
  if (request.method !== 'POST') return json(405, { error: 'use POST' }, { Allow: 'POST' });

  const origin = request.headers.get('Origin');
  if (origin && new URL(origin).host !== new URL(request.url).host) {
    return json(403, { error: 'cross-site submissions are not accepted' });
  }
  if (!(request.headers.get('Content-Type') || '').toLowerCase().startsWith('application/json')) {
    return json(415, { error: 'send JSON' });
  }
  if (Number(request.headers.get('Content-Length') || 0) > RULES.max_body_bytes) {
    return json(413, { error: 'too large' });
  }
  const text = await request.text();
  if (new TextEncoder().encode(text).length > RULES.max_body_bytes) return json(413, { error: 'too large' });

  let payload;
  try { payload = JSON.parse(text); } catch (e) { return json(400, { error: 'not JSON' }); }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return json(400, { error: 'not a submission' });
  }

  if (!env || !env.DB || !env.TURNSTILE_SECRET || !env.IP_SALT) {
    return json(503, { error: 'suggestions are not being accepted right now' });
  }

  const ip = request.headers.get('CF-Connecting-IP') || '';
  if (!(await verifyTurnstile(payload.turnstile, env.TURNSTILE_SECRET, ip, fetchImpl))) {
    return json(403, { error: 'the bot check did not pass; please try again' });
  }

  const { clean, errors } = validate(payload, RULES);
  if (Object.keys(errors).length) return json(400, { error: 'invalid', fields: errors });

  const ipHash = await sha256hex(env.IP_SALT + ip);
  const t = now();
  const since = (s) => new Date(t.getTime() - s * 1000).toISOString();
  const count = async (s) => (await env.DB.prepare(
    'SELECT COUNT(*) AS n FROM suggestions WHERE ip_hash = ? AND created_at > ?')
    .bind(ipHash, since(s)).first()).n;
  if ((await count(3600)) >= LIMITS.hour || (await count(86400)) >= LIMITS.day) {
    return json(429, { error: 'too many suggestions from here; please try again later' });
  }

  const id = crypto.randomUUID();
  await env.DB.prepare(
    'INSERT INTO suggestions (id, created_at, status, system, system_id, objects, description, '
    + 'sources, name, email, site_build, ip_hash, reviewer_note) '
    + "VALUES (?, ?, 'new', ?, ?, ?, ?, ?, ?, ?, ?, ?, '')")
    .bind(id, t.toISOString(), clean.system, clean.system_id, JSON.stringify(clean.objects),
      clean.description, JSON.stringify(clean.sources), clean.name, clean.email, clean.site_build,
      ipHash)
    .run();
  return json(201, { id });
}

export const onRequest = ({ request, env }) => handle(request, env);
