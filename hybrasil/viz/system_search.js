// SPDX-FileCopyrightText: 2026 Cade Summers
// SPDX-License-Identifier: AGPL-3.0-or-later
// System search for the "More Modeled Systems" dropdown: typo-tolerant autocomplete over
// every system the viewer can open, featured and catalog alike.
//
// Pure functions, no DOM.  The page loads this as a classic script
// (window.SASystemSearch); tests/test_system_search.py loads it under node.
//
// Star names come in the catalog's style -- "tau Cet", "alf Cen A",
// "55 Cnc B" -- and people type them the long way: "tau ceti", "alpha
// centauri", "55 cancri".  So every name is compared both as written and with
// its Bayer letter and constellation abbreviation spelled out, and a query
// gets the same treatment.  Then, in order of preference:
//
//   exact  >  prefix  >  every typed word starts a word of the name
//          >  substring  >  within a few typos (optimal string alignment)
//
// The last tier is the autocorrect: "trapist" still finds TRAPPIST-1.
(function (root) {
  'use strict';

  // Bayer letters as the catalog abbreviates them.
  var GREEK = {
    alf: 'alpha', bet: 'beta', gam: 'gamma', del: 'delta', eps: 'epsilon',
    zet: 'zeta', eta: 'eta', the: 'theta', iot: 'iota', kap: 'kappa',
    lam: 'lambda', mu: 'mu', nu: 'nu', ksi: 'xi', xi: 'xi', omi: 'omicron',
    pi: 'pi', rho: 'rho', sig: 'sigma', tau: 'tau', ups: 'upsilon',
    phi: 'phi', chi: 'chi', psi: 'psi', ome: 'omega'
  };

  // The 88 IAU constellation abbreviations, to the genitive a star name uses.
  var CONSTELLATIONS = {
    and: 'andromedae', ant: 'antliae', aps: 'apodis', aqr: 'aquarii',
    aql: 'aquilae', ara: 'arae', ari: 'arietis', aur: 'aurigae',
    boo: 'bootis', cae: 'caeli', cam: 'camelopardalis', cnc: 'cancri',
    cvn: 'canum venaticorum', cma: 'canis majoris', cmi: 'canis minoris',
    cap: 'capricorni', car: 'carinae', cas: 'cassiopeiae', cen: 'centauri',
    cep: 'cephei', cet: 'ceti', cha: 'chamaeleontis', cir: 'circini',
    col: 'columbae', com: 'comae berenices', cra: 'coronae australis',
    crb: 'coronae borealis', crv: 'corvi', crt: 'crateris', cru: 'crucis',
    cyg: 'cygni', del: 'delphini', dor: 'doradus', dra: 'draconis',
    equ: 'equulei', eri: 'eridani', for: 'fornacis', gem: 'geminorum',
    gru: 'gruis', her: 'herculis', hor: 'horologii', hya: 'hydrae',
    hyi: 'hydri', ind: 'indi', lac: 'lacertae', leo: 'leonis',
    lmi: 'leonis minoris', lep: 'leporis', lib: 'librae', lup: 'lupi',
    lyn: 'lyncis', lyr: 'lyrae', men: 'mensae', mic: 'microscopii',
    mon: 'monocerotis', mus: 'muscae', nor: 'normae', oct: 'octantis',
    oph: 'ophiuchi', ori: 'orionis', pav: 'pavonis', peg: 'pegasi',
    per: 'persei', phe: 'phoenicis', pic: 'pictoris', psc: 'piscium',
    psa: 'piscis austrini', pup: 'puppis', pyx: 'pyxidis', ret: 'reticuli',
    sge: 'sagittae', sgr: 'sagittarii', sco: 'scorpii', scl: 'sculptoris',
    sct: 'scuti', ser: 'serpentis', sex: 'sextantis', tau: 'tauri',
    tel: 'telescopii', tri: 'trianguli', tra: 'trianguli australis',
    tuc: 'tucanae', uma: 'ursae majoris', umi: 'ursae minoris',
    vel: 'velorum', vir: 'virginis', vol: 'volantis', vul: 'vulpeculae'
  };

  function tokens(text) {
    var s = String(text || '').toLowerCase();
    if (s.normalize) s = s.normalize('NFD').replace(/[̀-ͯ]/g, '');
    return s.split(/[^a-z0-9]+/).filter(Boolean);
  }

  // The first word may be a Bayer letter ("alf", "psi1"); any later word may
  // be a constellation ("Cen").  Position matters because "tau" is both: the
  // letter in "tau Cet", Taurus in "HD 284149 Tau".
  function expandTokens(toks) {
    return toks.map(function (t, i) {
      if (i === 0) {
        var m = /^([a-z]+)(\d*)$/.exec(t);
        if (m && GREEK[m[1]]) return GREEK[m[1]] + m[2];
        return t;
      }
      return CONSTELLATIONS[t] ? CONSTELLATIONS[t].replace(/ /g, '') : t;
    });
  }

  // Every way a string is compared: as written and expanded, each both as
  // words and run together.
  function forms(text) {
    var raw = tokens(text), exp = expandTokens(raw);
    return {raw: raw.join(''), exp: exp.join(''), rawTokens: raw, expTokens: exp};
  }

  // Optimal string alignment distance: Levenshtein plus adjacent swaps, so
  // "tarppist" is one typo from "trappist", not two.
  function osa(a, b) {
    var n = a.length, m = b.length, i, j;
    if (!n) return m;
    if (!m) return n;
    var d = [];
    for (i = 0; i <= n; i++) { d.push(new Array(m + 1)); d[i][0] = i; }
    for (j = 0; j <= m; j++) d[0][j] = j;
    for (i = 1; i <= n; i++) {
      for (j = 1; j <= m; j++) {
        var cost = a[i - 1] === b[j - 1] ? 0 : 1;
        var v = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
          v = Math.min(v, d[i - 2][j - 2] + 1);
        }
        d[i][j] = v;
      }
    }
    return d[n][m];
  }

  function allowedTypos(len) { return len <= 4 ? 1 : (len <= 8 ? 2 : 3); }

  // How well one name matches the query, 0-100, and which tier it came from.
  function scoreForms(q, k) {
    var best = 0, tier = null, pairs = [[q.raw, k.raw], [q.exp, k.exp],
                                        [q.raw, k.exp], [q.exp, k.raw]];
    function take(s, t) { if (s > best) { best = s; tier = t; } }
    for (var p = 0; p < pairs.length; p++) {
      var qs = pairs[p][0], ks = pairs[p][1];
      if (!qs || !ks) continue;
      if (ks === qs) take(100, 'exact');
      else if (ks.indexOf(qs) === 0) take(90 - Math.min(9, (ks.length - qs.length) / 3), 'prefix');
      else if (ks.indexOf(qs) > 0) take(65, 'substring');
    }
    // Every typed word starts some word of the name: "cen alpha".
    var words = [[q.rawTokens, k.rawTokens], [q.expTokens, k.expTokens]];
    for (var w = 0; w < words.length; w++) {
      var qt = words[w][0], kt = words[w][1];
      if (qt.length > 1 && qt.every(function (t) {
        return kt.some(function (x) { return x.indexOf(t) === 0; });
      })) take(75, 'words');
    }
    // Typos.  Compared with the whole name and with its first len(query)
    // letters, so a mistyped *start* of a long name still matches mid-typing.
    if (best < 60) {
      for (var f = 0; f < pairs.length; f++) {
        var a = pairs[f][0], b = pairs[f][1];
        if (!a || a.length < 3 || !b) continue;
        var d = Math.min(osa(a, b), osa(a, b.slice(0, a.length)),
                         osa(a, b.slice(0, a.length + 1)));
        if (d <= allowedTypos(a.length)) take(58 - 12 * d, 'typo');
      }
    }
    return {score: best, tier: tier};
  }

  // Cached per entry: the forms of its name, aliases and planet names.
  function entryForms(entry) {
    if (entry._forms) return entry._forms;
    var out = [];
    out.push({f: forms(entry.name), weight: 1, label: entry.name});
    (entry.aliases || []).forEach(function (a) {
      out.push({f: forms(a), weight: 1, label: a});
    });
    // A planet leads to its star, a little behind the star's own names.
    (entry.planets || []).forEach(function (p) {
      out.push({f: forms(p), weight: 0.85, label: p});
    });
    Object.defineProperty(entry, '_forms', {value: out, enumerable: false});
    return out;
  }

  // The best `limit` entries for `query`, best first, each as
  // {entry, score, tier, via}: `via` is the alias or planet name that matched
  // when it was not the entry's own name.
  function rank(index, query, limit) {
    var q = forms(query);
    if (!q.raw) return [];
    var hits = [];
    for (var i = 0; i < index.length; i++) {
      var e = index[i], best = {score: 0};
      var fs = entryForms(e);
      for (var j = 0; j < fs.length; j++) {
        var r = scoreForms(q, fs[j].f), s = r.score * fs[j].weight;
        if (s > best.score) {
          best = {score: s, tier: r.tier,
                  via: fs[j].label === e.name ? null : fs[j].label};
        }
      }
      if (best.score > 0) {
        hits.push({entry: e, score: best.score, tier: best.tier, via: best.via});
      }
    }
    hits.sort(function (a, b) {
      return (b.score - a.score)
        || ((b.entry.featured ? 1 : 0) - (a.entry.featured ? 1 : 0))
        || ((a.entry.distance_ly || 1e9) - (b.entry.distance_ly || 1e9))
        || String(a.entry.name).localeCompare(String(b.entry.name));
    });
    return hits.slice(0, limit || 8);
  }

  // What the system dropdown shows before anything is typed: the featured
  // systems in their own order, then every other system -- most planets
  // first, then most stars (a High Star Count (Planetless) entry has no planets and an
  // n_stars; a planetary one has no n_stars), then nearest, then by name.  An
  // entry with no distance sorts after those that have one.
  function shelf(index) {
    var featured = [], more = [];
    for (var i = 0; i < index.length; i++) {
      if (index[i].featured) featured.push(index[i]);
      else more.push(index[i]);
    }
    var dist = function (e) {
      return (typeof e.distance_ly === 'number') ? e.distance_ly : Infinity;
    };
    more.sort(function (a, b) {
      return ((b.n_planets || 0) - (a.n_planets || 0))
        || ((b.n_stars || 0) - (a.n_stars || 0))
        || (dist(a) === dist(b) ? 0 : (dist(a) < dist(b) ? -1 : 1))
        || String(a.name).localeCompare(String(b.name));
    });
    return {featured: featured, more: more};
  }

  var api = {tokens: tokens, forms: forms, osa: osa, rank: rank, shelf: shelf};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.SASystemSearch = api;
})(typeof window !== 'undefined' ? window : this);
