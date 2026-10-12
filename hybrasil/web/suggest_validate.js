// SPDX-FileCopyrightText: 2026 Cade Summers
// SPDX-License-Identifier: AGPL-3.0-or-later
// What a Suggest Changes submission may hold, checked against
// suggestion_rules.json.  One file, two users: the Cloudflare function imports
// it as a module (functions/api/suggestions.js), and the viewer page inlines it
// with the `export` keywords stripped (three_viewer.py, suggest_script()).
// hybrasil/web/suggestions.py is its Python twin for --serve;
// tests/test_suggestions.py runs both on the same cases so they cannot drift.
//
// validate(payload, rules) -> {clean, errors}: `clean` holds only the known
// fields, trimmed, lists as arrays of non-empty lines; `errors` maps a field
// to one message.  Lengths count characters (code points), as Python does.

export function validate(payload, rules) {
  const errors = {};
  const clean = {};
  const msg = (key, f, extra) => {
    let m = rules.messages[key];
    for (const [k, v] of Object.entries(Object.assign({}, f, extra || {}))) {
      m = m.split(`{${k}}`).join(String(v));
    }
    return m;
  };
  const len = (s) => [...s].length;
  const obj = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : {};

  for (const [name, f] of Object.entries(rules.fields)) {
    const raw = obj[name];
    if (f.type === 'list') {
      let items;
      if (raw === undefined || raw === null) items = [];
      else if (typeof raw === 'string') items = raw.split(/\r?\n/);
      else if (Array.isArray(raw)) items = raw;
      else { errors[name] = msg('not_list', f); continue; }
      if (items.some((x) => typeof x !== 'string')) { errors[name] = msg('not_list', f); continue; }
      items = items.map((x) => x.trim()).filter((x) => x.length > 0);
      clean[name] = items;
      if (f.required && items.length === 0 && !f.min_items) errors[name] = msg('required', f);
      else if (f.min_items && items.length < f.min_items) errors[name] = msg('too_few', f);
      else if (f.max_items && items.length > f.max_items) errors[name] = msg('too_many', f);
      else {
        const i = items.findIndex((x) => len(x) > f.max);
        if (i >= 0) errors[name] = msg('item_long', f, { n: i + 1 });
      }
    } else {
      if (raw !== undefined && raw !== null && typeof raw !== 'string') {
        errors[name] = msg('not_text', f); continue;
      }
      const v = (raw || '').trim();
      clean[name] = v;
      if (!v) { if (f.required) errors[name] = msg('required', f); continue; }
      if (f.min && len(v) < f.min) errors[name] = msg('too_short', f);
      else if (f.max && len(v) > f.max) errors[name] = msg('too_long', f);
      else if (f.type === 'email' && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) errors[name] = msg('not_email', f);
    }
  }
  const given = rules.one_of.some((n) => {
    const v = clean[n];
    return Array.isArray(v) ? v.length > 0 : !!v;
  });
  if (!given && !errors[rules.one_of[0]]) errors[rules.one_of[0]] = msg('one_of', {});
  return { clean, errors };
}
