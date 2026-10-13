// SPDX-FileCopyrightText: 2026 Cade Summers
// SPDX-License-Identifier: AGPL-3.0-or-later
  // ══ band_kit.js ══════════════════════════════════════════════════════════
  // Shared by both viewers: spliced into the Plotly viewer's _ZOOM_JS, and
  // wrapped and exported as window.SABandKit for the three.js viewer.  One
  // copy, so the band equation, the ring it draws, the slider panel and the
  // info panel cannot drift between renderers.  (The equation itself also
  // lives in mechanics/solvent_bands.py; tests/test_band_sliders.py holds the
  // two to 1e-12.)
  //
  // Plain ES5 function declarations at two-space indent, because that is what
  // the Plotly viewer's IIFE is written in and what its tests slice on.
  // Reads window._SA_BAND_CONST, window._SA_SOLVENTS and window._SA_BODY_INFO,
  // which build_solvent_table_js() and build_body_info_js() write.

  function _bandConst() { return window._SA_BAND_CONST || null; }

  function _extent(arr) {
    var lo = Infinity, hi = -Infinity;
    for (var i = 0; i < arr.length; i++) {
      var v = +arr[i];
      if (!isFinite(v)) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    return isFinite(lo) ? [lo, hi] : [0, 0];
  }

  // Melting and boiling points in K at any pressure, interpolated between the
  // workbook's seven columns: the boiling point as 1/T linear in ln P, which
  // is Clausius-Clapeyron, and the melting point as T linear in ln P, which is
  // a different equation but moves so little it makes no odds. Outside a
  // solvent's own transcribed range there is nothing to interpolate between,
  // and running a vapour-pressure curve past its last point is how you draw a
  // band where the substance is not liquid at all -- so: null.
  function _liquidRangeK(sol, P, ceiling) {
    var C = _bandConst(), pts = sol && sol.points;
    if (!C || !pts || !pts.length) return null;
    if (P < pts[0][0] || P > pts[pts.length - 1][0]) return null;
    var mC, bC;
    if (pts.length === 1) {
      mC = pts[0][1]; bC = pts[0][2];
    } else {
      var i = 0;
      while (i + 2 < pts.length && pts[i + 1][0] <= P) i++;
      var p0 = pts[i], p1 = pts[i + 1];
      var f = (Math.log(P) - Math.log(p0[0])) / (Math.log(p1[0]) - Math.log(p0[0]));
      mC = p0[1] + f * (p1[1] - p0[1]);
      var k0 = p0[2] + C.c2k, k1 = p1[2] + C.c2k;
      bC = 1 / ((1 / k0) + f * ((1 / k1) - (1 / k0))) - C.c2k;
    }
    if (ceiling && sol.ceiling_c !== null && sol.ceiling_c !== undefined) {
      bC = Math.min(bC, sol.ceiling_c);
    }
    return [mC + C.c2k, bC + C.c2k];
  }

  // d_AU = T_1AU^2 * sqrt(L) * sqrt(1 - A) / T^2, once per edge. The hot edge
  // is the boiling point and the cold edge the melting point, so a darker body
  // -- hotter at the same distance -- pushes the whole ring outward.
  //
  // G is the greenhouse offset: a flat number of kelvin on top of the
  // blackbody, so each edge sits where T_eq is its point *minus* G. Past the
  // boiling point there is no band; past the melting point the solvent never
  // freezes, and the cold edge is where T_eq reaches the CMB, not infinity.
  //
  // meta.colour is the star's colour factor on absorbed flux, 1 for the Sun.
  // Python computes it from the Kopparapu fit and ships the number, so the
  // fit itself lives in one place; here it only multiplies (1 - A).
  function _bandRadiiAU(meta, P, A, G) {
    var C = _bandConst();
    var sol = meta && window._SA_SOLVENTS && window._SA_SOLVENTS[meta.solvent];
    if (!C || !sol || !meta.lum || meta.lum <= 0) return null;
    var lr = _liquidRangeK(sol, P, meta.ceiling);
    if (!lr) return null;
    var tMelt = lr[0], tBoil = lr[1];
    if (tMelt <= 0 || tBoil <= tMelt) return null;
    var g = G || 0;
    var tHot = tBoil - g, tCold = Math.max(tMelt - g, C.t_cmb);
    if (tHot <= tCold) return null;
    var colour = meta.colour > 0 ? meta.colour : 1;
    var k = C.t_eq * C.t_eq * Math.sqrt(meta.lum) * Math.sqrt((1 - A) * colour);
    var inner = k / (tHot * tHot), outer = k / (tCold * tCold);
    return outer > inner * C.min_span ? [inner, outer] : null;
  }

  // The bare number, for the box the viewer types into; _fmtBar adds the unit
  // for the legend entry, where there is nothing to say what the number is.
  function _fmtBarNum(P) {
    var v = P >= 10 ? P.toFixed(1) : (P >= 1 ? P.toFixed(2) : P.toFixed(3));
    return String(parseFloat(v));
  }

  function _fmtBar(P) { return _fmtBarNum(P) + ' bar'; }

  // The legend entry names the pressure, so it is rewritten as the slider
  // moves -- an entry still reading "1 bar" at 40 would be the figure lying
  // about what it is showing. ", functional" marks a band whose outer
  // temperature is capped by the solvent giving up before it boils.
  function _bandName(meta, P) {
    var sol = meta && window._SA_SOLVENTS && window._SA_SOLVENTS[meta.solvent];
    if (!sol) return '';
    var capped = false;
    if (meta.ceiling && sol.ceiling_c !== null && sol.ceiling_c !== undefined) {
      var raw = _liquidRangeK(sol, P, false);
      capped = !!raw && (raw[1] - _bandConst().c2k) > sol.ceiling_c;
    }
    // The star, where the figure holds more than one band-bearing star.  It
    // has to be rebuilt here too: the slider rewrites this whole string, so
    // leaving it out would strip the star off the first time anyone dragged.
    var star = meta.star ? ' — ' + meta.star : '';
    return sol.name + ' band' + star + ' (' + _fmtBar(P)
           + (capped ? ', functional' : '') + ')';
  }

  // Two perpendicular unit vectors spanning the band's plane, u along the line
  // of nodes so a tilted ring is reproducible rather than arbitrarily rolled.
  // The third is the unit normal, which the stacking offset runs along.
  function _planeBasis(n) {
    var L = Math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) || 1;
    var w = [n[0] / L, n[1] / L, n[2] / L];
    var ax = -w[1], ay = w[0], al = Math.sqrt(ax * ax + ay * ay);
    var u = al > 1e-12 ? [ax / al, ay / al, 0] : [1, 0, 0];
    var v = [w[1] * u[2] - w[2] * u[1],
             w[2] * u[0] - w[0] * u[2],
             w[0] * u[1] - w[1] * u[0]];
    var vl = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    return [u, vl > 1e-12 ? [v[0] / vl, v[1] / vl, v[2] / vl] : [0, 1, 0], w];
  }

  // The annulus, built the way Python builds it: n vertices on the inner edge
  // then n on the outer, two triangles per quad between them.
  // `centre` is the star the ring is around, which is the origin for a
  // primary's band and the companion's position at t_start for anyone else's.
  // It has to be applied here as well as in Python: the sliders rewrite this
  // geometry, so a band built around a companion would jump back to the origin
  // the first time anyone dragged one.
  function _ringMesh(inner, outer, normal, offset, n, centre) {
    var b = _planeBasis(normal), u = b[0], v = b[1], w = b[2];
    var o = centre || [0, 0, 0];
    var cx = w[0] * offset + o[0], cy = w[1] * offset + o[1],
        cz = w[2] * offset + o[2];
    var X = new Array(2 * n), Y = new Array(2 * n), Z = new Array(2 * n);
    for (var s = 0; s < 2; s++) {
      var r = s ? outer : inner;
      for (var t = 0; t < n; t++) {
        var a = 2 * Math.PI * t / n, ca = Math.cos(a) * r, sa = Math.sin(a) * r;
        var q = s * n + t;
        X[q] = ca * u[0] + sa * v[0] + cx;
        Y[q] = ca * u[1] + sa * v[1] + cy;
        Z[q] = ca * u[2] + sa * v[2] + cz;
      }
    }
    var I = [], J = [], K = [];
    for (var t2 = 0; t2 < n; t2++) {
      var n2 = (t2 + 1) % n;
      I.push(t2); J.push(n2);      K.push(n + t2);
      I.push(n2); J.push(n + n2);  K.push(n + t2);
    }
    return {x: X, y: Y, z: Z, i: I, j: J, k: K};
  }

  // Rank by outer radius and lift each band by that rank times a small
  // fraction of its own size, so overlapping bands never share a plane and the
  // lift stays invisible at the zoom that band is read at. A band with no
  // liquid phase takes no rank, so the stack does not develop gaps as the
  // pressure slider moves a solvent in and out of its range.
  //
  // The size the lift scales by is capped at a few inner radii: a greenhouse
  // offset can run a band's cold edge out to the CMB distance, thousands of AU,
  // and a lift scaled by that floats the ring clean off its own plane.
  // `stack_offsets_for_outer` in Python applies the same cap.
  function _stackOffsets(outer, inner) {
    var C = _bandConst(), live = [], out = [], i;
    for (i = 0; i < outer.length; i++) { out.push(0); if (outer[i] > 0) live.push(i); }
    if (!C || live.length < 2) return out;
    live.sort(function (a, b) { return outer[a] - outer[b]; });
    for (var r = 0; r < live.length; r++) {
      var j = live[r], scale = outer[j];
      if (inner) scale = Math.min(scale, C.stack_cap * inner[j]);
      out[j] = r * C.stack * scale;
    }
    return out;
  }

  // Stacking offsets for a list of band metas, grouped by the star each band
  // is centred on.  Pure, so both viewers call it: the Plotly viewer passes
  // its traces' metas, the three.js viewer its meshes'.
  function _stackOffsetsByCentre(metas, outer, inner) {
    var groups = {}, k, key;
    for (k = 0; k < metas.length; k++) {
      key = ((metas[k] || {}).centre || [0, 0, 0]).join(',');
      (groups[key] || (groups[key] = [])).push(k);
    }
    var out = new Array(metas.length);
    for (k = 0; k < out.length; k++) out[k] = 0;
    for (key in groups) {
      if (!Object.prototype.hasOwnProperty.call(groups, key)) continue;
      var members = groups[key], sub = [], subIn = [];
      for (k = 0; k < members.length; k++) {
        sub.push(outer[members[k]]); subIn.push(inner[members[k]]);
      }
      var got = _stackOffsets(sub, subIn);
      for (k = 0; k < members.length; k++) out[members[k]] = got[k];
    }
    return out;
  }

  // Indices of `names` in the best tier matching `query`: every exact match,
  // else every prefix match, else every substring match, case-insensitive.
  // [] when nothing matches.  The search boxes of both viewers rank with it.
  function _nameMatches(names, query) {
    var q = String(query).toLowerCase(), exact = [], prefix = [], substr = [];
    for (var i = 0; i < names.length; i++) {
      var n = String(names[i] || '').toLowerCase();
      if (!n) continue;
      if (n === q)                 exact.push(i);
      else if (n.indexOf(q) === 0) prefix.push(i);
      else if (n.indexOf(q) >= 0)  substr.push(i);
    }
    return exact.length ? exact : (prefix.length ? prefix : substr);
  }

  // ── Info panel ─────────────────────────────────────────────────────────────
  // Shows mass, orbital period, mean velocity, and axial tilt for the selected
  // body.  Data comes from window._SA_BODY_INFO, injected by build_body_info_js.
  // Auto-hides when the user moves the camera (plotly_relayout).
  var _infoPanelEl      = null;
  var _infoPanelShownAt = 0;
  // An entry with `goto` (a system id -- a star in Nearby Stellar Motion) gets a
  // "Go to system" button, when the viewer has said it can open that id:
  // {can: function (id), go: function (id)}.  Only the three.js viewer sets it.
  var _infoGoto = null;
  // Every entry gets a "Suggest Changes" button when the viewer has somewhere
  // to send one: {go: function (name)}.  Only the three.js viewer sets it, and
  // only on a page with a suggestions endpoint (docs/architecture/suggestions.md).
  var _infoSuggest = null;

  function setInfoGoto(handler) { _infoGoto = handler; }
  function setInfoSuggest(handler) { _infoSuggest = handler; }

  function createInfoPanel() {
    if (_infoPanelEl) return;
    var el = document.createElement('div');
    el.id = '_sa_info_panel';
    el.style.cssText = [
      'position:fixed', 'bottom:12px', 'left:12px',
      'background:rgba(6,6,24,0.94)', 'color:#aaddff',
      'border:1px solid #334d6e', 'border-radius:6px',
      'padding:10px 14px', 'font-family:monospace', 'font-size:12px',
      'min-width:200px', 'max-width:340px', 'z-index:9997',
      'opacity:0', 'transition:opacity 0.25s',
      'pointer-events:auto', 'display:none'
    ].join(';');
    document.body.appendChild(el);
    _infoPanelEl = el;
  }

  function showInfoPanel(name) {
    if (!_infoPanelEl) createInfoPanel();
    var info = window._SA_BODY_INFO && window._SA_BODY_INFO[name];
    // Orbit / axis line traces are named "<body> orbit" / "<body> axis".
    // If the direct lookup misses, strip the suffix and try the body name.
    var displayName = name;
    if (!info) {
      displayName = name.replace(/ orbit$/, '').replace(/ axis$/, '');
      info = window._SA_BODY_INFO && window._SA_BODY_INFO[displayName];
    }
    if (!info) { hideInfoPanel(); return; }

    function row(lbl, val, note) {
      var n = note ? ' <span style="color:#667788;font-size:10px;">(' + note + ')</span>' : '';
      return '<tr>'
        + '<td style="color:#778899;padding:2px 10px 2px 0;white-space:nowrap;vertical-align:top;">'
        + lbl + '</td>'
        + '<td style="padding:2px 0;color:#aaddff;">' + val + n + '</td>'
        + '</tr>';
    }

    // Sheet text, escaped for an element or an attribute.
    var esc = function (v) {
      return String(v == null ? '' : v).replace(/&/g, '&amp;')
        .replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    };
    var html = '<div style="font-size:13px;font-weight:bold;margin-bottom:7px;color:#ddeeff;'
             + 'border-bottom:1px solid #334d6e;padding-bottom:5px;">' + esc(displayName) + '</div>';
    html += '<table style="border-collapse:collapse;width:100%;">';
    if (info.rows) {
      // An entry that brings its own [label, value, note] rows -- a star in
      // the Nearby Stellar Motion view.  Its values are sheet text, so escaped.
      for (var r = 0; r < info.rows.length; r++) {
        html += row(esc(info.rows[r][0]), esc(info.rows[r][1]), esc(info.rows[r][2]));
      }
    } else {
      html += row('Status',         info.status === 'hypothetical' ? (info.status_label || 'Hypothetical') : 'Confirmed', '');
      html += row('Mass',           info.mass,     info.mass_note);
      html += row('Orbital period', info.period,   info.period_note);
      html += row('Mean velocity',  info.velocity, info.velocity_note);
      // A planet whose sense of orbit is measured (the sheet's Orbit Direction column).
      if (info.orbit_direction) html += row('Orbit direction', esc(info.orbit_direction), esc(info.orbit_direction_note || ''));
      html += row('Axial tilt',     info.tilt,     esc(info.tilt_note || ''));
    }
    html += '</table>';

    if (info.sources && info.sources.length > 0) {
      html += '<div style="margin-top:8px;padding-top:6px;border-top:1px solid #223344;">';
      html += '<div style="color:#667788;font-size:10px;margin-bottom:3px;">Sources</div>';
      // Labels and links come from sheet text (a bibcode has '&', a name may
      // have '<'), so both are escaped like the rows above.
      for (var i = 0; i < info.sources.length; i++) {
        var s = info.sources[i];
        html += '<div style="font-size:10px;line-height:1.6;">'
              + '\u2022 <a href="' + esc(s[1]) + '" target="_blank" rel="noopener"'
              + ' style="color:#5588bb;text-decoration:underline;">'
              + esc(s[0]) + '</a></div>';
      }
      html += '</div>';
    }

    var target = info.goto && _infoGoto && _infoGoto.can(info.goto) ? info.goto : null;
    if (target || _infoSuggest) {
      var btnCss = 'font:inherit;font-size:11px;color:#ddeeff;background:#1a2a44;'
                 + 'border:1px solid #4477aa;border-radius:3px;padding:3px 10px;cursor:pointer;';
      html += '<div style="margin-top:8px;padding-top:6px;border-top:1px solid #223344;'
            + 'display:flex;gap:6px;flex-wrap:wrap;">';
      if (target) html += '<button type="button" id="_sa_info_goto" style="' + btnCss + '">Go to system</button>';
      if (_infoSuggest) html += '<button type="button" id="_sa_info_suggest" style="' + btnCss + '">Suggest Changes</button>';
      html += '</div>';
    }

    _infoPanelEl.innerHTML = html;
    if (target) {
      document.getElementById('_sa_info_goto').addEventListener('click', function () {
        _infoGoto.go(target);
      });
    }
    if (_infoSuggest) {
      document.getElementById('_sa_info_suggest').addEventListener('click', function () {
        _infoSuggest.go(displayName);
      });
    }
    _infoPanelEl.style.display = 'block';
    requestAnimationFrame(function () { _infoPanelEl.style.opacity = '1'; });
    _infoPanelShownAt = Date.now();
  }

  function hideInfoPanel() {
    if (!_infoPanelEl) return;
    _infoPanelEl.style.opacity = '0';
    var el = _infoPanelEl;
    setTimeout(function () {
      if (el.style.opacity === '0') el.style.display = 'none';
    }, 280);
  }

  // The pressure, albedo and greenhouse panel.  opts.onChange(P, A, G) is
  // called at most once per animation frame; opts.toast(text) reports a
  // typed value that had to be clamped.  The caller places .el.
  function _bandPanel(opts) {
    opts = opts || {};
    // This panel's own reading of the three tracks.
    var _bandP = null, _bandA = null, _bandG = null;

    // --- Band sliders: pressure and albedo ---
    // The inputs the band equation takes that are not properties of the star.
    // Each was a fixed number baked into the figure; each is now read off a
    // slider and the bands are rebuilt as it moves. The third, the greenhouse
    // offset, is a beta: a flat number of kelvin, where a real greenhouse
    // depends on the atmosphere and the flux it traps.
    //
    // Pressure is logarithmic. The range is three decades, and a linear track
    // would spend its first one percent on 0.1 to 1 bar -- where four of the
    // eight solvents do all of their interesting moving.
    var bandPanel = document.createElement('div');
    bandPanel.style.cssText = [
      'position:fixed', 'top:38px', 'left:8px',
      'background:rgba(6,6,24,0.92)', 'border:1px solid #333366',
      'border-radius:4px', 'padding:7px 10px 8px',
      'font-family:monospace', 'font-size:11px', 'color:#aaddff',
      'z-index:9998', 'display:none'
    ].join(';');

    var _sliderCss = [
      'width:132px', 'vertical-align:middle', 'margin:0 7px',
      'accent-color:#5588bb', 'cursor:pointer'
    ].join(';');

    // The readout is an input, not a label: a slider cannot be dragged to
    // 37.4 bar on purpose, and a figure meant to answer a question about one
    // pressure needs that pressure rather than one near it. Typing and
    // dragging are two ways into the same track -- the box sets the slider,
    // and the slider stays the single source of truth for what is drawn.
    function _sliderRow(label, unit, title) {
      var row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:2px;line-height:1.9;';
      row.title = title;
      var name = document.createElement('span');
      name.textContent = label;
      name.style.cssText = 'display:inline-block;width:58px;color:#778899;';
      var input = document.createElement('input');
      input.type = 'range';
      input.style.cssText = _sliderCss;
      var read = document.createElement('input');
      read.type = 'text';
      read.spellcheck = false;
      read.setAttribute('aria-label', label);
      read.style.cssText = [
        'width:50px', 'text-align:right', 'background:transparent',
        'border:1px solid transparent', 'border-radius:3px', 'color:#aaddff',
        'font-family:monospace', 'font-size:11px', 'padding:1px 3px',
        'outline:none', 'cursor:text'
      ].join(';');
      // Editable, but only obviously so once it has focus: a box outlined at
      // rest reads as a form, and this is a readout most of the time.
      read.addEventListener('focus', function () {
        read.style.borderColor = '#334d6e';
        read.style.background = '#0b0b22';
        read.select();
      });
      read.addEventListener('blur', function () {
        read.style.borderColor = 'transparent';
        read.style.background = 'transparent';
      });
      var suffix = document.createElement('span');
      suffix.textContent = unit;
      suffix.style.cssText = 'display:inline-block;width:24px;color:#778899;'
                           + 'padding-left:3px;';
      row.appendChild(name); row.appendChild(input);
      row.appendChild(read); row.appendChild(suffix);
      return {row: row, input: input, read: read};
    }

    var pRow = _sliderRow('Pressure', 'bar',
      'Atmospheric pressure the bands are computed at — drag, or type a '
      + 'value. Between the workbook’s seven columns the melting and '
      + 'boiling points are interpolated; outside a solvent’s own range '
      + 'it has no band at all.');
    var aRow = _sliderRow('Albedo', '',
      'Bond albedo of the body the band is drawn for — drag, or type a '
      + 'value. A darker body is hotter at the same distance, so a lower '
      + 'albedo pushes every band outward.');
    var gTitle = 'A flat offset added to the blackbody temperature — drag, or '
      + 'type a value. Earth\u2019s is about 33 K. A warmer surface pushes '
      + 'every band outward; past a melting point the band runs out to where '
      + 'the CMB sets the temperature, and can leave the edge of the scene. '
      + 'Beta: a real greenhouse is not a constant.';
    var gRow = _sliderRow('', 'K', gTitle);
    // The name is longer than the label column, so it gets a line of its own
    // above the slider rather than widening every row to fit it.
    var gCaption = document.createElement('div');
    gCaption.textContent = 'Greenhouse effect (beta)';
    gCaption.title = gTitle;
    gCaption.style.cssText = 'color:#778899;line-height:1.5;padding-top:2px;';

    // Pressure rides a 0-1000 track mapped through log10, albedo a plain
    // 0.01 step -- it spans less than two decades and reads naturally.
    var C0 = window._SA_BAND_CONST || {p_min: 0.1, p_max: 100, a_min: 0.01,
                                       a_max: 0.99, p0: 1, a0: 0.3,
                                       g_min: 0, g_max: 1000, g0: 33};
    var _logLo = Math.log10(C0.p_min), _logHi = Math.log10(C0.p_max);

    // 1000 steps per decade. Coarser and the round trip through the track
    // does not land back on a round number -- 1 bar came back as 0.998, and a
    // figure that cannot open on the pressure it was built at is a figure
    // whose legend and slider disagree from the first frame.
    var _perDecade = 1000;
    var _pSteps = Math.round((_logHi - _logLo) * _perDecade);

    function _posToBar(pos) {
      var raw = Math.pow(10, _logLo + (pos / _pSteps) * (_logHi - _logLo));
      // Three significant figures, so the number under the slider and the
      // number in the legend are the same number.
      return parseFloat(raw.toPrecision(3));
    }
    function _barToPos(bar) {
      return Math.round(_pSteps * (Math.log10(bar) - _logLo) / (_logHi - _logLo));
    }

    pRow.input.min = 0; pRow.input.max = _pSteps; pRow.input.step = 1;
    pRow.input.value = _barToPos(C0.p0);
    aRow.input.min = C0.a_min; aRow.input.max = C0.a_max; aRow.input.step = 0.01;
    aRow.input.value = C0.a0;
    // Linear, in tenths of a kelvin. A log track would suit three decades,
    // but 0 K -- no greenhouse at all -- has to be reachable, and no log is.
    gRow.input.min = C0.g_min; gRow.input.max = C0.g_max; gRow.input.step = 0.1;
    gRow.input.value = C0.g0;

    function _readSliders() {
      _bandP = _posToBar(+pRow.input.value);
      _bandA = parseFloat((+aRow.input.value).toFixed(2));
      _bandG = parseFloat((+gRow.input.value).toFixed(1));
      // Never while the viewer is mid-edit: overwriting a half-typed number
      // is how a box that is also a readout becomes unusable.
      if (document.activeElement !== pRow.read) pRow.read.value = _fmtBarNum(_bandP);
      if (document.activeElement !== aRow.read) aRow.read.value = _bandA.toFixed(2);
      if (document.activeElement !== gRow.read) gRow.read.value = String(_bandG);
      if (head) _paintHead();    // the folded header's copy of the values
    }

    // A typed value, or null if there is no number in there at all. Lenient
    // about what surrounds it, so "2.5 bar" and " 2.5 " both land.
    function _parseTyped(text) {
      var m = String(text).replace(/,/g, '').match(/-?[0-9]*[.]?[0-9]+(?:[eE][-+]?[0-9]+)?/);
      if (!m) return null;
      var v = parseFloat(m[0]);
      return isFinite(v) ? v : null;
    }

    // Take what was typed, or put back what is actually set if it was not a
    // number. Out of range clamps to the end of the track rather than being
    // refused -- the slider cannot go past it either -- and says so, because
    // silently drawing 100 bar for someone who asked for 500 is the figure
    // answering a question they did not ask.
    function _commitTyped(row, lo, hi, unit, place) {
      var v = _parseTyped(row.read.value);
      if (v === null) { _readSliders(); return; }
      if (v < lo || v > hi) {
        opts.toast('Range is ' + lo + ' to ' + hi + (unit ? ' ' + unit : '')
                  + ' — using ' + (v < lo ? lo : hi));
        v = v < lo ? lo : hi;
      }
      place(v);
      _readSliders();
      _scheduleBands();
    }

    function _wireTyping(row, lo, hi, unit, place) {
      row.read.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); row.read.blur(); }
        else if (e.key === 'Escape') { _readSliders(); row.read.blur(); }
        // Arrow keys nudge the slider itself, so the box behaves like one.
        else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
          e.preventDefault();
          var step = (e.key === 'ArrowUp' ? 1 : -1) * (+row.input.step || 1);
          row.input.value = +row.input.value + step;
          _readSliders();
          _scheduleBands();
        }
        e.stopPropagation();
      });
      // Commit on blur, never on keystroke: recomputing on every character
      // would rebuild the bands at 1 bar on the way to typing 12.
      row.read.addEventListener('blur', function () {
        _commitTyped(row, lo, hi, unit, place);
      });
    }

    // Coalesced the way the wheel is: a drag emits an event per pixel, and
    // rebuilding eight meshes and re-cutting the scene box per pixel queues
    // work faster than it retires. One rebuild per animation frame instead.
    var _bandRAF = 0, _bandTimer = 0;
    function _scheduleBands() {
      if (_bandRAF || _bandTimer) return;
      var run = function () {
        if (_bandRAF)   { cancelAnimationFrame(_bandRAF); _bandRAF = 0; }
        if (_bandTimer) { clearTimeout(_bandTimer);       _bandTimer = 0; }
        if (opts.onChange) opts.onChange(_bandP, _bandA, _bandG);
      };
      _bandRAF = requestAnimationFrame(run);
      // rAF never fires in a hidden or occluded tab, so a plain timer backs it
      // up; whichever arrives first cancels the other.
      _bandTimer = setTimeout(run, 100);
    }

    function _onSlide() { _readSliders(); _scheduleBands(); }
    pRow.input.addEventListener('input', _onSlide);
    aRow.input.addEventListener('input', _onSlide);
    gRow.input.addEventListener('input', _onSlide);

    _wireTyping(pRow, C0.p_min, C0.p_max, 'bar', function (v) {
      pRow.input.value = _barToPos(v);
    });
    _wireTyping(aRow, C0.a_min, C0.a_max, '', function (v) {
      aRow.input.value = v;
    });
    _wireTyping(gRow, C0.g_min, C0.g_max, 'K', function (v) {
      gRow.input.value = v;
    });

    var hint = document.createElement('div');
    hint.style.cssText = 'color:#556677;font-size:10px;padding-top:3px;';
    hint.textContent = 'Drag or type — bands recompute live';

    // A narrow screen folds the panel behind a one-line header that carries
    // the three values, so the system keeps the screen until someone asks
    // for the sliders.  Only the three.js viewer, on a phone, calls
    // setCompact(); for any other caller the header never shows.
    var head = document.createElement('button');
    head.type = 'button';
    head.style.cssText = [
      'display:none', 'width:100%', 'text-align:left', 'background:none',
      'border:0', 'padding:0', 'font:inherit', 'color:inherit', 'cursor:pointer'
    ].join(';');
    var body = document.createElement('div');
    body.appendChild(pRow.row);
    body.appendChild(aRow.row);
    body.appendChild(gCaption);
    body.appendChild(gRow.row);
    body.appendChild(hint);
    bandPanel.appendChild(head);
    bandPanel.appendChild(body);
    var _compact = false, _open = true;
    function _paintHead() {
      head.textContent = 'Band inputs: ' + _fmtBarNum(_bandP) + ' bar · '
        + _bandA.toFixed(2) + ' · ' + _bandG + ' K ' + (_open ? '▴' : '▾');
      head.setAttribute('aria-expanded', String(_open));
      head.style.display = _compact ? 'block' : 'none';
      body.style.display = !_compact || _open ? '' : 'none';
      body.style.paddingTop = _compact && _open ? '4px' : '';
    }
    function _setOpen(open) { _open = !!open; _paintHead(); }
    head.addEventListener('click', function () {
      _setOpen(!_open);
      if (opts.onToggle) opts.onToggle(_open);
    });
    _readSliders();
    if (opts.top) bandPanel.style.top = opts.top;

    return {
      el: bandPanel,
      read: _readSliders,
      values: function () { return {P: _bandP, A: _bandA, G: _bandG}; },
      // Folded (and closed) on a narrow screen, always open otherwise.
      setCompact: function (on) { _compact = !!on; _open = !_compact; _paintHead(); },
      setOpen: _setOpen,
      isOpen: function () { return !_compact || _open; }
    };
  }
