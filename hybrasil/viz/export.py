# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export Plotly figures to various output formats."""

import json
import math
import os
import pathlib
import tempfile
import webbrowser
import plotly.graph_objects as go
from ..mechanics.units import T_EQ_1AU_K
from .static_plot import BAND_RING_POINTS, is_band_trace


# JavaScript injected into every HTML output.
# Double-clicking a body marker zooms the 3D camera to center on it and shows
# an info panel (bottom-left) with mass, period, velocity, and axial tilt.
# The panel hides automatically when the camera is moved.
# An "Orient" button resets the camera to a top-down view from 100 AU above.
# window._saReattach(gd) is exposed so the system switcher can re-initialize
# the click handler, range cache, and relayout listener after a system swap.
# The band equation, ring, slider panel and info panel, shared with the
# three.js viewer.  Spliced into _ZOOM_JS below at /*@@BAND_KIT@@*/.
BAND_KIT_JS = (pathlib.Path(__file__).with_name("band_kit.js")
               .read_text(encoding="utf-8"))

_ZOOM_JS = """
(function () {
  // ── Range caching ──────────────────────────────────────────────────────────
  // Axis ranges captured once from the initial layout, before any relayout call.
  // Plotly rewrites gd._fullLayout.scene.*.range after relayout (it switches to
  // normalized coordinates), so we must snapshot the data-space ranges up front
  // and reuse them — otherwise viewFromAbove computes a wildly wrong eye height
  // on the second click.
  var _sa_ranges      = null;
  var _sa_ranges_orig = null;  // original full-system ranges, set once and never mutated
  var _sceneHalfAU    = null;  // current scene half-extent in AU
  var _sceneOrigHalfAU = null; // original full-system half-extent in AU (set once)
  var _sceneStack     = [];    // previous scenes for zoom-out: [{xr,yr,zr,halfAU}, ...]
  var _rescaleLock    = false; // 600 ms cooldown after any rescale

  function captureRanges(gd) {
    if (_sa_ranges) return true;
    // Prefer Python-injected preset ranges — computed from exact orbit extents,
    // always symmetric around the origin (mid == 0), immune to Plotly's internal
    // relayout rewrites that overwrite _fullLayout.scene.*.range with normalised coords.
    if (window._SA_SCENE_RANGES) {
      var r = window._SA_SCENE_RANGES;
      if (r.xr && r.yr && r.zr && r.xr.length >= 2 && r.yr.length >= 2 && r.zr.length >= 2) {
        _sa_ranges = { xr: r.xr.slice(), yr: r.yr.slice(), zr: r.zr.slice() };
        if (!_sa_ranges_orig) {
          _sa_ranges_orig = { xr: _sa_ranges.xr.slice(), yr: _sa_ranges.yr.slice(), zr: _sa_ranges.zr.slice() };
          _sceneHalfAU = Math.max(
            (_sa_ranges.xr[1] - _sa_ranges.xr[0]) / 2,
            (_sa_ranges.yr[1] - _sa_ranges.yr[0]) / 2,
            (_sa_ranges.zr[1] - _sa_ranges.zr[0]) / 2
          );
          _sceneOrigHalfAU = _sceneHalfAU;
        }
        return true;
      }
    }
    // Fallback: read from Plotly layout (correct on first call; may be overwritten
    // with normalised coords by Plotly after any relayout).
    var scene = gd._fullLayout && gd._fullLayout.scene;
    if (!scene) return false;
    var xr = scene.xaxis.range, yr = scene.yaxis.range, zr = scene.zaxis.range;
    if (!xr || !yr || !zr || xr.length < 2 || yr.length < 2 || zr.length < 2) return false;
    if (isNaN(xr[0]) || isNaN(yr[0]) || isNaN(zr[0])) return false;
    _sa_ranges = { xr: xr.slice(), yr: yr.slice(), zr: zr.slice() };
    if (!_sa_ranges_orig) {
      _sa_ranges_orig = { xr: _sa_ranges.xr.slice(), yr: _sa_ranges.yr.slice(), zr: _sa_ranges.zr.slice() };
      _sceneHalfAU = Math.max(
        (_sa_ranges.xr[1] - _sa_ranges.xr[0]) / 2,
        (_sa_ranges.yr[1] - _sa_ranges.yr[0]) / 2,
        (_sa_ranges.zr[1] - _sa_ranges.zr[0]) / 2
      );
      _sceneOrigHalfAU = _sceneHalfAU;
    }
    return true;
  }

  // ── rescaleScene / restoreScene / _findNearestBody ─────────────────────────

  function rescaleScene(gd, cx_au, cy_au, cz_au, halfAU, cam) {
    if (!halfAU || halfAU <= 0) return;
    if (_sa_ranges) {
      _sceneStack.push({
        xr: _sa_ranges.xr.slice(), yr: _sa_ranges.yr.slice(), zr: _sa_ranges.zr.slice(),
        halfAU: _sceneHalfAU
      });
      if (_sceneStack.length > 12) _sceneStack.shift();
    }
    var newXr = [cx_au - halfAU, cx_au + halfAU];
    var newYr = [cy_au - halfAU, cy_au + halfAU];
    var newZr = [cz_au - halfAU, cz_au + halfAU];
    _sa_ranges = { xr: newXr.slice(), yr: newYr.slice(), zr: newZr.slice() };
    window._SA_SCENE_RANGES = { xr: newXr, yr: newYr, zr: newZr };
    _sceneHalfAU = halfAU;
    _rescaleLock = true;
    setTimeout(function () { _rescaleLock = false; }, 600);
    var layout = {
      'scene.xaxis.range': newXr,
      'scene.yaxis.range': newYr,
      'scene.zaxis.range': newZr
    };
    if (cam) layout['scene.camera'] = cam;
    updateSceneVisibility(gd, newXr, newYr, newZr, layout);
  }

  // ── updateSceneVisibility ────────────────────────────────────────────────────
  // Keep what is inside the scene box, drop only what is outside it.
  //
  // Plotly clips 3D geometry to the axis ranges, and the scene is a cube, so a
  // ring of radius R centred in a cube of half-extent h is whole while R <= h,
  // sliced into four arcs with flat ends while h < R <= h*sqrt(2), and outside
  // the box beyond that. Those flat-ended arcs are the artifact: a belt with
  // straight edges, an orbit cut in half.
  //
  // The first rule against that hid any trace that did not fit *entirely*, and
  // it worked, but it took the view with it. Zoomed to Earth, the box is
  // 0.0077 AU across, and 51 of the Solar System's 54 traces fail that test --
  // including Earth's own orbit, which runs straight through the view, and the
  // water band Earth sits inside. The frame kept three traces.
  //
  // So the geometry is clipped to the box instead. A line is cut to the runs
  // that lie inside it, a mesh triangle to the polygon that lies inside it, and
  // a trace with nothing left is the only one hidden. The user sees the arc of
  // Earth's orbit crossing the view and the band's surface around it, with no
  // flat-ended ring anywhere, because the ends are now the box itself.
  //
  // This also keeps the property the whole rule exists for. Plotly's 3D
  // renderer normalises against the data that is still visible, not against the
  // axis range, so one marker left on at 700 AU -- Planet Nine, Eris, Neptune --
  // while the window is a few thousandths of an AU wide collapses everything
  // inside that window to nothing: no planet, no moon, no orbit, just
  // gridlines. Clipped geometry never reaches outside the box, so there is
  // nothing far away left in the visible set to normalise against.
  //
  // Markers keep the older, cruder treatment: a single point is either in the
  // box or out of it, and rewriting a marker's coordinates would fight the
  // animation, which updates exactly those traces by index every frame.
  //
  // 'legendonly' rather than false for what is dropped: the legend entry stays
  // put instead of appearing and vanishing as the user zooms, and clicking it
  // still forces the trace back on.

  // Plotly 3.x hands multi-point coordinate arrays over as base64 rather than
  // as JS arrays: trace.x is {bdata: '<base64>', dtype: 'f8'}, and trace.x.length
  // is undefined. Anything that reads coordinates off gd.data has to decode that
  // first, or it silently sees no data at all. Single-point marker traces are
  // still plain arrays, which is why the length checks elsewhere work unchanged.
  function _coords(v) {
    if (!v) return null;
    if (v.length !== undefined) return v;          // plain or already-typed array
    if (typeof v.bdata !== 'string') return null;
    var C = {f8: Float64Array, f4: Float32Array, i4: Int32Array, i2: Int16Array,
             i1: Int8Array, u4: Uint32Array, u2: Uint16Array, u1: Uint8Array}[v.dtype];
    if (!C) return null;
    var bin = atob(v.bdata), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new C(bytes.buffer);
  }

  function _traceBBox(t) {
    var axes = ['x', 'y', 'z'], out = {};
    for (var a = 0; a < 3; a++) {
      var arr = _coords(t[axes[a]]);
      if (!arr || !arr.length) return null;
      var lo = Infinity, hi = -Infinity;
      for (var j = 0; j < arr.length; j++) {
        var v = +arr[j];
        if (!isFinite(v)) continue;
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
      if (!isFinite(lo)) return null;
      out[axes[a]] = [lo, hi];
    }
    return out;
  }

  // Everything with coordinates takes part, body markers included.  An
  // exemption here is what broke deep zoom the first time.
  function _isClippable(t) {
    return !!(t.x && (t.x.length || t.x.bdata));
  }

  // ── Original geometry ────────────────────────────────────────────────────────
  // Clipping always runs from the coordinates the figure was built with, never
  // from what is on screen. Reading gd.data back would hand over the previous
  // clip's output, and the trace would erode a little further at every zoom
  // step until nothing was left of it.
  var _geom = null;

  function _traceKind(t, n) {
    if (t.type === 'mesh3d') return 'mesh';
    if (t.type === 'scatter3d' && n > 1 &&
        String(t.mode || 'lines').indexOf('lines') >= 0) return 'line';
    return 'points';
  }

  // Keyed on trace count, which is what changes when the system switcher swaps
  // one figure for another.
  function _buildGeom(gd) {
    _geom = { n: gd.data.length, items: [] };
    for (var i = 0; i < gd.data.length; i++) {
      var t = gd.data[i];
      if (!_isClippable(t)) { _geom.items.push(null); continue; }
      var x = _coords(t.x);
      var band = _isBandTrace(t);
      _geom.items.push({
        kind:  _traceKind(t, x ? x.length : 0),
        // A band of a newly built figure opens on whatever the button is set
        // to: a swapped-in system is a different set of bands, matched by
        // nothing an index could carry across.
        isBand: band,
        bandOn: band ? _bandsOn : true,
        bbox:  _traceBBox(t),
        x: x, y: _coords(t.y), z: _coords(t.z),
        fi: _coords(t.i), fj: _coords(t.j), fk: _coords(t.k),
        state: 'full'
      });
    }
  }

  // Liang-Barsky: the interval [t0, t1] of the segment p -> q that lies inside
  // the box, or null if the segment misses it entirely.
  function _clipSegment(p, d, lo, hi) {
    var t0 = 0, t1 = 1;
    for (var a = 0; a < 3; a++) {
      for (var s = 0; s < 2; s++) {
        var pk = s === 0 ? -d[a] : d[a];
        var qk = s === 0 ? p[a] - lo[a] : hi[a] - p[a];
        if (pk === 0) {
          if (qk < 0) return null;                 // parallel to this face, outside
          continue;
        }
        var r = qk / pk;
        if (pk < 0) { if (r > t1) return null; if (r > t0) t0 = r; }
        else        { if (r < t0) return null; if (r < t1) t1 = r; }
      }
    }
    return [t0, t1];
  }

  // A polyline cut to the parts inside the box, as one array per axis with
  // nulls where a run ends -- which is how a scatter3d line breaks.
  function _clipPolyline(g, lo, hi, eps) {
    var X = [], Y = [], Z = [], open = false, lx = 0, ly = 0, lz = 0;
    var p = [0, 0, 0], d = [0, 0, 0];
    for (var s = 0; s + 1 < g.x.length; s++) {
      p[0] = +g.x[s];     p[1] = +g.y[s];     p[2] = +g.z[s];
      d[0] = +g.x[s + 1] - p[0];
      d[1] = +g.y[s + 1] - p[1];
      d[2] = +g.z[s + 1] - p[2];
      if (!isFinite(p[0]) || !isFinite(p[1]) || !isFinite(p[2]) ||
          !isFinite(d[0]) || !isFinite(d[1]) || !isFinite(d[2])) { open = false; continue; }
      var seg = _clipSegment(p, d, lo, hi);
      if (!seg) { open = false; continue; }
      var ax = p[0] + seg[0] * d[0], ay = p[1] + seg[0] * d[1], az = p[2] + seg[0] * d[2];
      var bx = p[0] + seg[1] * d[0], by = p[1] + seg[1] * d[1], bz = p[2] + seg[1] * d[2];
      // A run continues only where this segment starts where the last one
      // ended; an orbit that crosses the box twice gets two runs.
      if (!open || Math.abs(ax - lx) > eps || Math.abs(ay - ly) > eps ||
          Math.abs(az - lz) > eps) {
        if (X.length) { X.push(null); Y.push(null); Z.push(null); }
        X.push(ax); Y.push(ay); Z.push(az);
      }
      X.push(bx); Y.push(by); Z.push(bz);
      lx = bx; ly = by; lz = bz; open = true;
    }
    return X.length > 1 ? { x: X, y: Y, z: Z } : null;
  }

  // Sutherland-Hodgman against one face of the box.  side = 1 keeps the half
  // above `bound` on this axis, side = -1 the half below it.
  function _clipPolyFace(poly, axis, bound, side) {
    var out = [];
    for (var m = 0; m < poly.length; m++) {
      var cur = poly[m], nxt = poly[(m + 1) % poly.length];
      var dc = side * (cur[axis] - bound), dn = side * (nxt[axis] - bound);
      if (dc >= 0) out.push(cur);
      if ((dc >= 0) !== (dn >= 0)) {
        var t = dc / (dc - dn);
        out.push([cur[0] + t * (nxt[0] - cur[0]),
                  cur[1] + t * (nxt[1] - cur[1]),
                  cur[2] + t * (nxt[2] - cur[2])]);
      }
    }
    return out;
  }

  // A mesh cut to the box, triangle by triangle.  Each surviving polygon is
  // fanned back into triangles; vertices are not shared between them, which
  // costs a little memory and saves welding them back together.
  function _clipMesh(g, lo, hi) {
    if (!g.fi || !g.fj || !g.fk) return null;
    var X = [], Y = [], Z = [], I = [], J = [], K = [];
    for (var f = 0; f < g.fi.length; f++) {
      var idx = [g.fi[f], g.fj[f], g.fk[f]];
      var poly = [];
      for (var c = 0; c < 3; c++) {
        poly.push([+g.x[idx[c]], +g.y[idx[c]], +g.z[idx[c]]]);
      }
      for (var a = 0; a < 3 && poly.length >= 3; a++) {
        poly = _clipPolyFace(poly, a, lo[a], 1);
        if (poly.length >= 3) poly = _clipPolyFace(poly, a, hi[a], -1);
      }
      if (poly.length < 3) continue;
      var base = X.length;
      for (var v = 0; v < poly.length; v++) {
        X.push(poly[v][0]); Y.push(poly[v][1]); Z.push(poly[v][2]);
      }
      for (var w = 1; w + 1 < poly.length; w++) {
        I.push(base); J.push(base + w); K.push(base + w + 1);
      }
    }
    return I.length ? { x: X, y: Y, z: Z, i: I, j: J, k: K } : null;
  }

  // ── Solvent bands ────────────────────────────────────────────────────────────
  // Two controls over the same set, and they have to agree.  Every band has
  // its own legend entry, as every trace does; the Bands button sits on top of
  // them and moves the whole set at once, because at 1 bar the Solar System
  // carries seven bands and clicking seven legend entries is not a way to
  // answer "where is water liquid".
  //
  // So the state is per trace, not one global flag: `g.bandOn` on the geometry
  // cache says whether the viewer has asked for that band, whichever control
  // asked.  The button reads the set back rather than remembering what it last
  // did, so switching one band on from the legend cannot leave its label lying.
  //
  // Python builds every band on 'legendonly' and tags the mesh with meta
  // 'solvent-band', so the two agree on load without anything having to run
  // before the first paint.  Matching the trace name instead would tie both
  // controls to the wording of a legend entry, which the search box also reads.
  var _bandsOn    = false;   // what the bands of a newly built figure take
  var _bandsBtnSync = null;  // set by addControls; keeps the button's label honest
  // The system switcher plots into a *fresh* graph div, so every control built
  // by addControls would otherwise keep acting on the previous system's div --
  // the Bands button and the sliders would simply stop working after one swap.
  // addControls holds its div in one closure variable and publishes a setter
  // here; _saReattach calls it with the live div on every (re)attach.
  var _controlsRebind = null;
  var _bandPanelSync = null; // set by addControls; hides the sliders where there are no bands

  // The tag is an object rather than a string because it carries what the
  // sliders recompute the ring from: which solvent, how bright the star is,
  // which plane, and whether the functional ceiling applies.
  function _isBandTrace(t) {
    return !!t && !!t.meta && t.meta.kind === 'solvent-band';
  }

  function _bandTraceIndices(gd) {
    var out = [];
    for (var i = 0; i < gd.data.length; i++) {
      if (_isBandTrace(gd.data[i])) out.push(i);
    }
    return out;
  }

  function _bandOn(i) {
    var g = _geom && _geom.items[i];
    return !!(g && g.bandOn);
  }

  // Every band trace that moves with trace i: itself, plus any band sharing its
  // legend group.  A band's two albedo margins are one group behind one legend
  // entry, and Plotly's own legend click toggles a whole group, so a handler
  // that took the clicked trace alone would leave half a band behind.
  function _bandGroup(gd, i) {
    var t = gd.data[i];
    if (!_isBandTrace(t)) return [];
    if (!t.legendgroup) return [i];
    var out = [];
    for (var j = 0; j < gd.data.length; j++) {
      var u = gd.data[j];
      if (_isBandTrace(u) && u.legendgroup === t.legendgroup) out.push(j);
    }
    return out;
  }

  // Draw or drop the bands at `idx`.  Switching one on hands it to
  // updateSceneVisibility rather than setting visible:true here: a band is
  // usually wider than the box the viewer is zoomed into, and a full-width ring
  // inside a moon-sized box puts coordinates outside it -- which is exactly
  // what collapses the view to bare gridlines.
  function _showBands(gd, idx, on) {
    if (!_geom || _geom.n !== gd.data.length) _buildGeom(gd);
    var offIdx = [], off = [];
    for (var k = 0; k < idx.length; k++) {
      var g = _geom.items[idx[k]];
      if (!g) continue;
      g.bandOn = !!on;
      // 'hidden' either way: off leaves it hidden, and on makes the clipper
      // re-send the geometry rather than skip a trace whose cached state
      // claims it is already fully drawn.
      g.state = 'hidden';
      if (!on && gd.data[idx[k]].visible !== 'legendonly') {
        offIdx.push(idx[k]); off.push('legendonly');
      }
    }
    if (offIdx.length) Plotly.restyle(gd, { visible: off }, offIdx);
    if (on && (_sa_ranges || captureRanges(gd))) {
      updateSceneVisibility(gd, _sa_ranges.xr, _sa_ranges.yr, _sa_ranges.zr);
    }
  }

  // How many bands there are and how many are drawn.  The button's label is
  // derived from this, never remembered.
  function _bandSummary(gd) {
    var idx = _bandTraceIndices(gd), on = 0;
    for (var k = 0; k < idx.length; k++) { if (_bandOn(idx[k])) on++; }
    return {
      total: idx.length,
      on:    on,
      state: (!idx.length || !on) ? 'none' : (on === idx.length ? 'all' : 'some')
    };
  }

  function _setAllBands(gd, on) {
    _bandsOn = !!on;
    _showBands(gd, _bandTraceIndices(gd), _bandsOn);
  }

  // Every scene change goes out as ONE Plotly call. Each restyle or relayout
  // re-normalises and re-draws the whole gl3d scene -- measured in Chrome at
  // 36-63 ms apiece, against 12-16 ms for moving the camera alone -- and a box
  // re-cut used to issue up to four of them in a row (visibility, clipped
  // lines, clipped meshes, then the ranges): a 150-240 ms stall mid-gesture,
  // which is what the scroll-zoom stutter was. Merged, the same re-cut costs
  // about what the relayout alone did.
  //
  // So the three groups share one restyle object, one entry per touched trace,
  // with `undefined` wherever an attribute does not apply -- Plotly's restyle
  // skips an undefined entry and leaves that trace's attribute alone. Pass
  // `layout` and the ranges and camera ride along in the same Plotly.update;
  // the promise it returns is what the wheel's backpressure waits on.
  function updateSceneVisibility(gd, xr, yr, zr, layout) {
    var done = function () {
      return layout ? Plotly.relayout(gd, layout) : Promise.resolve();
    };
    if (!gd || !gd.data || !xr || !yr || !zr) return done();
    if (!_geom || _geom.n !== gd.data.length) _buildGeom(gd);
    var lo = [xr[0], yr[0], zr[0]], hi = [xr[1], yr[1], zr[1]];
    var eps = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) * 1e-9;

    // A trace that is fully in view and was fully in view before contributes
    // nothing -- which is every trace, on most wheel events.
    var vIdx = [], vVal = [];
    var lIdx = [], lX = [], lY = [], lZ = [], lVis = [];
    var mIdx = [], mX = [], mY = [], mZ = [], mI = [], mJ = [], mK = [], mVis = [];

    for (var i = 0; i < gd.data.length; i++) {
      var g = _geom.items[i];
      if (!g || !g.bbox) continue;
      // A band the viewer has not asked for is not the box's to judge: its
      // visibility belongs to the Bands button and to its own legend entry.
      if (g.isBand && !g.bandOn) continue;
      var bb = g.bbox;
      var fits = bb.x[0] >= lo[0] && bb.x[1] <= hi[0]
              && bb.y[0] >= lo[1] && bb.y[1] <= hi[1]
              && bb.z[0] >= lo[2] && bb.z[1] <= hi[2];

      if (fits) {
        if (g.state === 'full') continue;
        if (g.kind === 'line') {
          lIdx.push(i); lX.push(g.x); lY.push(g.y); lZ.push(g.z); lVis.push(true);
        } else if (g.kind === 'mesh') {
          mIdx.push(i); mX.push(g.x); mY.push(g.y); mZ.push(g.z);
          mI.push(g.fi); mJ.push(g.fj); mK.push(g.fk); mVis.push(true);
        } else {
          vIdx.push(i); vVal.push(true);
        }
        g.state = 'full';
        continue;
      }

      var cut = g.kind === 'line' ? _clipPolyline(g, lo, hi, eps)
              : g.kind === 'mesh' ? _clipMesh(g, lo, hi)
              : null;

      if (!cut) {
        // Nothing of it is in view. A marker outside the box lands here too,
        // and that is the whole treatment it gets: its coordinates are left
        // alone so the animation can keep writing them.
        if (g.state !== 'hidden') { vIdx.push(i); vVal.push('legendonly'); }
        g.state = 'hidden';
        continue;
      }

      if (g.kind === 'line') {
        lIdx.push(i); lX.push(cut.x); lY.push(cut.y); lZ.push(cut.z); lVis.push(true);
      } else {
        mIdx.push(i); mX.push(cut.x); mY.push(cut.y); mZ.push(cut.z);
        mI.push(cut.i); mJ.push(cut.j); mK.push(cut.k); mVis.push(true);
      }
      g.state = 'clipped';
    }

    var idx = vIdx.concat(lIdx, mIdx);
    if (!idx.length) return done();
    var nv = vIdx.length, nl = lIdx.length, nm = mIdx.length;
    var pad = function (n) { return new Array(n); };   // n undefined entries
    var data = {
      visible: vVal.concat(lVis, mVis),
      x: pad(nv).concat(lX, mX),
      y: pad(nv).concat(lY, mY),
      z: pad(nv).concat(lZ, mZ),
      i: pad(nv + nl).concat(mI),
      j: pad(nv + nl).concat(mJ),
      k: pad(nv + nl).concat(mK)
    };
    if (!nm) { delete data.i; delete data.j; delete data.k; }
    if (!nl && !nm) { delete data.x; delete data.y; delete data.z; }
    return layout ? Plotly.update(gd, data, layout, idx)
                  : Plotly.restyle(gd, data, idx);
  }

  // ── Recomputing a band in the browser ────────────────────────────────────────
  // The pressure, albedo and greenhouse sliders rebuild every band's geometry
  // here rather than asking Python for a new figure. The equation is small -- a liquid
  // range against pressure, then one blackbody inversion per edge -- and the
  // alternative is a page reload per drag.
  //
  // window._SA_SOLVENTS holds the workbook's transcribed melting and boiling
  // points; each band trace's own meta holds the star it was computed for, so
  // a system swap needs no bookkeeping at all. Both come from Python, and
  // `mechanics/solvent_bands.py` states the same rules in full.
  var _bandP = null;   // current pressure, bar
  var _bandA = null;   // current albedo
  var _bandG = null;   // current greenhouse offset, K

  /*@@BAND_KIT@@*/

  // Stacking is per star, not per figure. The offsets exist so that bands
  // which overlap do not z-fight, and only bands around the *same* star can
  // overlap; ranking across a figure would lift one star's bands by another
  // star's radii, which at Alpha Centauri's scales is a band pushed clear of
  // the star it belongs to. Python gets this for free because it builds one
  // stack per star per call; here every band arrives in one array.
  function _stackOffsetsByStar(gd, idx, outer, inner) {
    var metas = [];
    for (var k = 0; k < idx.length; k++) metas.push(gd.data[idx[k]].meta || {});
    return _stackOffsetsByCentre(metas, outer, inner);
  }


  // Rebuild every band in the figure at the current slider positions.
  //
  // Geometry goes into the clipper's cache rather than straight onto the
  // trace, and updateSceneVisibility sends it from there. That is the same
  // path the Bands button takes, and it is what keeps a recomputed band
  // clipped to the scene box: writing visible geometry here would drop a
  // full-width ring into a moon-sized box the moment a slider moved while
  // someone was zoomed in.
  function _recomputeBands(gd) {
    var C = _bandConst();
    if (!C || !gd || !gd.data) return 0;
    if (!_geom || _geom.n !== gd.data.length) _buildGeom(gd);
    var P = _bandP === null ? C.p0 : _bandP;
    var A = _bandA === null ? C.a0 : _bandA;
    var G = _bandG === null ? C.g0 : _bandG;

    var idx = _bandTraceIndices(gd), k;
    if (!idx.length) return 0;

    var radii = [], outer = [], inner = [];
    for (k = 0; k < idx.length; k++) {
      var r = _bandRadiiAU(gd.data[idx[k]].meta, P, A, G);
      radii.push(r);
      outer.push(r ? r[1] : 0);
      inner.push(r ? r[0] : 0);
    }
    var offsets = _stackOffsetsByStar(gd, idx, outer, inner);

    var names = [], blankIdx = [], blank = [], blankVis = [];
    for (k = 0; k < idx.length; k++) {
      var i = idx[k], meta = gd.data[i].meta, prev = _geom.items[i];
      var wanted = !!(prev && prev.bandOn);
      names.push(_bandName(meta, P));
      if (!radii[k]) {
        // No liquid phase at this pressure, or a greenhouse offset that
        // boils it at every distance. The trace stays -- the set of
        // traces cannot change size -- but there is no ring, and the clipper
        // has to be told so rather than left holding the last pressure's.
        _geom.items[i] = {kind: 'mesh', bbox: null, isBand: true,
                          bandOn: wanted, state: 'hidden'};
        blankIdx.push(i); blank.push([]); blankVis.push('legendonly');
        continue;
      }
      var m = _ringMesh(radii[k][0], radii[k][1], meta.normal || [0, 0, 1],
                        offsets[k], C.ring_pts, meta.centre);
      _geom.items[i] = {
        kind: 'mesh',
        bbox: {x: _extent(m.x), y: _extent(m.y), z: _extent(m.z)},
        x: m.x, y: m.y, z: m.z, fi: m.i, fj: m.j, fk: m.k,
        isBand: true, bandOn: wanted, state: 'hidden'
      };
    }

    Plotly.restyle(gd, {name: names}, idx);
    if (blankIdx.length) {
      Plotly.restyle(gd, {x: blank, y: blank, z: blank,
                          i: blank, j: blank, k: blank, visible: blankVis},
                     blankIdx);
    }
    if (_sa_ranges || captureRanges(gd)) {
      updateSceneVisibility(gd, _sa_ranges.xr, _sa_ranges.yr, _sa_ranges.zr);
    }
    return idx.length;
  }

  function restoreScene(gd) {
    var prev = _sceneStack.pop();
    if (!prev) return;
    _sa_ranges = { xr: prev.xr.slice(), yr: prev.yr.slice(), zr: prev.zr.slice() };
    window._SA_SCENE_RANGES = { xr: prev.xr, yr: prev.yr, zr: prev.zr };
    _sceneHalfAU = prev.halfAU;
    _rescaleLock = true;
    setTimeout(function () { _rescaleLock = false; }, 600);
    updateSceneVisibility(gd, prev.xr, prev.yr, prev.zr, {
      'scene.xaxis.range': prev.xr,
      'scene.yaxis.range': prev.yr,
      'scene.zaxis.range': prev.zr,
      'scene.camera': {
        center: { x: 0, y: 0,   z: 0   },
        eye:    { x: 0, y: 0.3, z: 1.2 },
        up:     { x: 0, y: 0,   z: 1   }
      }
    });
  }

  function _findNearestBody(gd, ctr_norm) {
    if (!_sa_ranges) return null;
    var xr = _sa_ranges.xr, yr = _sa_ranges.yr, zr = _sa_ranges.zr;
    var xMid = (xr[0]+xr[1])/2, xHalf = (xr[1]-xr[0])/2;
    var yMid = (yr[0]+yr[1])/2, yHalf = (yr[1]-yr[0])/2;
    var zMid = (zr[0]+zr[1])/2, zHalf = (zr[1]-zr[0])/2;
    var maxHalf = Math.max(xHalf, yHalf, zHalf) || 1;
    var cx = ctr_norm.x * maxHalf + xMid;
    var cy = ctr_norm.y * maxHalf + yMid;
    var cz = ctr_norm.z * maxHalf + zMid;
    var bestD2 = Infinity, best = null;
    for (var i = 0; i < gd.data.length; i++) {
      var tr = gd.data[i];
      if (!tr || !tr.mode || tr.mode.indexOf('markers') < 0) continue;
      if (!tr.x || tr.x.length !== 1) continue;
      var bx = +tr.x[0], by = +tr.y[0], bz = +tr.z[0];
      if (isNaN(bx)) continue;
      var d2 = (bx-cx)*(bx-cx) + (by-cy)*(by-cy) + (bz-cz)*(bz-cz);
      if (d2 < bestD2) { bestD2 = d2; best = { name: tr.name, x: bx, y: by, z: bz }; }
    }
    if (!best) return null;
    best.info = window._SA_BODY_INFO && window._SA_BODY_INFO[best.name];
    return best;
  }

  // Exposed so the system switcher can hide the panel on system change.
  window._saHideInfo = hideInfoPanel;

  // ── zoomTo ─────────────────────────────────────────────────────────────────
  function zoomTo(gd, x, y, z, name, halfOverride) {
    // Use cached ranges — Plotly overwrites _fullLayout.scene.*.range with
    // normalized coordinates after every relayout, so reading them live gives
    // wrong values on every click after the first.
    if (!_sa_ranges && !captureRanges(gd)) return;

    var xr = _sa_ranges.xr, yr = _sa_ranges.yr, zr = _sa_ranges.zr;

    // Convert data coordinates → normalized scene coordinates.
    // With aspectmode='data' the longest axis spans [-1, 1]; others scale proportionally.
    var xMid = (xr[0] + xr[1]) / 2,  xHalf = (xr[1] - xr[0]) / 2;
    var yMid = (yr[0] + yr[1]) / 2,  yHalf = (yr[1] - yr[0]) / 2;
    var zMid = (zr[0] + zr[1]) / 2,  zHalf = (zr[1] - zr[0]) / 2;
    var maxHalf = Math.max(xHalf, yHalf, zHalf) || 1;

    var cx = (x - xMid) / maxHalf;
    var cy = (y - yMid) / maxHalf;
    var cz = (z - zMid) / maxHalf;

    // Direction from scene origin toward the body.
    var dist = Math.sqrt(cx*cx + cy*cy + cz*cz) || 0.001;
    var nx = cx / dist, ny = cy / dist, nz = cz / dist;

    // Determine zoom extent.  An explicit override wins — a belt or a solvent
    // band is not in _SA_BODY_INFO and is framed from its own geometry.  Then
    // the Python-injected zoom_half_au, then 1% of heliocentric distance.
    var info   = window._SA_BODY_INFO && window._SA_BODY_INFO[name];
    var halfAU = halfOverride
               ? halfOverride
               : ((info && info.zoom_half_au)
                  ? info.zoom_half_au
                  : Math.max(Math.sqrt(x*x + y*y + z*z) * 0.01, 0.001));

    // Eye direction in new scene (body will be at origin after rescale).
    // Use the direction from the solar-system origin toward the body, with a
    // slight upward tilt, so the view arrives from a natural angle.
    var upBlend = 0.5;
    var dx = nx, dy = ny, dz = nz + upBlend;
    var dlen = Math.sqrt(dx*dx + dy*dy + dz*dz) || 1;
    dx /= dlen; dy /= dlen; dz /= dlen;
    var cam = {
      center: { x: 0,          y: 0,          z: 0          },
      eye:    { x: dx * 0.40,  y: dy * 0.40,  z: dz * 0.40  },
      up:     { x: 0,          y: 0,           z: 1          }
    };

    // Show info panel BEFORE relayout so _infoPanelShownAt is stamped first.
    _infoPanelShownAt = Date.now();
    showInfoPanel(name);
    showToast(name);

    // Rescale scene to body's focus extent + reposition camera (single relayout).
    rescaleScene(gd, x, y, z, halfAU, cam);
  }

  // ── viewFromAbove ──────────────────────────────────────────────────────────
  // Restore the original full-system scene and move the camera to a top-down
  // view with the eye at 100 AU above the origin.  Always uses _sa_ranges_orig
  // so it works correctly even when zoomed into a moon system.
  // |(1.25, 1.25, 1.25)|, the length of Plotly's default camera eye, so Orient
  // frames a scene the same way the figure opens framing it.
  var ORIENT_EYE_DIST = 2.1650635;

  function viewFromAbove(gd) {
    if (!_sa_ranges && !captureRanges(gd)) return;

    // Use original (full-system) ranges, not the current potentially tiny scene.
    var origRanges = _sa_ranges_orig || _sa_ranges;
    var xr = origRanges.xr, yr = origRanges.yr, zr = origRanges.zr;

    var xMid = (xr[0] + xr[1]) / 2,  xHalf = (xr[1] - xr[0]) / 2;
    var yMid = (yr[0] + yr[1]) / 2,  yHalf = (yr[1] - yr[0]) / 2;
    var zMid = (zr[0] + zr[1]) / 2,  zHalf = (zr[1] - zr[0]) / 2;
    var maxHalf = Math.max(xHalf, yHalf, zHalf) || 1;

    // Restore scene state to original.
    _sa_ranges = { xr: xr.slice(), yr: yr.slice(), zr: zr.slice() };
    window._SA_SCENE_RANGES = { xr: xr.slice(), yr: yr.slice(), zr: zr.slice() };
    _sceneHalfAU = maxHalf;
    _sceneStack  = [];
    _rescaleLock = true;
    setTimeout(function () { _rescaleLock = false; }, 600);

    var cx = (0 - xMid) / maxHalf;
    var cy = (0 - yMid) / maxHalf;
    var cz = (0 - zMid) / maxHalf;

    // Look down the system's *band plane* normal, not down world z.  Only the
    // Solar System is quoted in the ecliptic; every system whose angles come
    // from transits or astrometry is quoted against the plane of the sky, so
    // its bands stand perpendicular to z and a camera on the z axis sees them
    // edge-on -- TRAPPIST-1 at 89.76 deg drew eight bands as eight lines.  A
    // flat system's normal is the z axis, so this is the old camera exactly.
    var n = _viewNormal();
    var up = _perpendicularTo(n);
    // A fixed distance in *normalised* units, not a fixed number of AU.  The
    // old camera sat 100 AU up, which is a sensible height only for a system
    // about 100 AU across: at the Solar System's 1,177 AU half-extent that is
    // 0.085 normalised units, practically inside the star, and at TRAPPIST-1's
    // 0.068 AU it is 1,460 units away and collapses the whole system to a dot.
    // The scene is a cube whatever it holds, so the framing that works for one
    // works for all -- this is the magnitude of Plotly's own default eye.
    var d = ORIENT_EYE_DIST;

    updateSceneVisibility(gd, xr, yr, zr, {
      'scene.xaxis.range': xr.slice(),
      'scene.yaxis.range': yr.slice(),
      'scene.zaxis.range': zr.slice(),
      'scene.camera': {
        center: { x: cx, y: cy, z: cz },
        eye:    { x: cx + n[0] * d, y: cy + n[1] * d, z: cz + n[2] * d },
        up:     { x: up[0], y: up[1], z: up[2] }
      }
    });
  }

  // The plane this system's solvent bands lie in, as a unit vector. Python
  // bakes it in from the same normal the bands were built with, so the camera
  // and the rings cannot disagree about which plane they are in.
  function _viewNormal() {
    var n = window._SA_VIEW_NORMAL;
    if (!n || n.length < 3) return [0, 0, 1];
    var L = Math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    return L > 1e-12 ? [n[0] / L, n[1] / L, n[2] / L] : [0, 0, 1];
  }

  // Any unit vector perpendicular to n -- the line of nodes, matching
  // plane_basis() on the Python side. An `up` parallel to the view direction
  // is degenerate and Plotly renders it as an empty scene, which is what makes
  // this worth a function rather than a hardcoded axis.
  function _perpendicularTo(n) {
    var ax = -n[1], ay = n[0], al = Math.sqrt(ax * ax + ay * ay);
    return al > 1e-12 ? [ax / al, ay / al, 0] : [1, 0, 0];
  }

  // ── Shared button/input style helpers ──────────────────────────────────────
  var _btnCss = [
    'background:#111130', 'color:#aaddff',
    'border:1px solid #333366', 'border-radius:4px',
    'padding:4px 12px', 'font-family:monospace', 'font-size:12px',
    'cursor:pointer'
  ].join(';');

  function _hoverOn(el)  { el.style.background = '#1a1a50'; }
  function _hoverOff(el) { el.style.background = '#111130'; }

  // ── Scroll-zoom state ──────────────────────────────────────────────────────
  var _zoomMode = 'center';   // 'center' | 'cursor'
  var _scrollAC = null;       // AbortController for scroll-listener cleanup
  var _mousePos = {x: 0.5, y: 0.5};  // cursor position on plot div, 0..1
  var _wheelAccum = 0;        // zoom pending since the last applied update, in notches
  var _wheelRAF   = 0;        // requestAnimationFrame handle, 0 when idle
  var _wheelTimer = 0;        // setTimeout backstop for when rAF is starved
  var _wheelBusy  = false;    // a zoom relayout is still rendering
  var WHEEL_EASE      = 0.3;  // fraction of the pending zoom applied per frame
  var WHEEL_EASE_TAIL = 0.08; // below this many notches, apply the rest at once

  // ── _initScrollZoom ────────────────────────────────────────────────────────
  // Replaces Plotly's native scroll zoom with a capture-phase wheel listener
  // that allows 50,000× deeper zoom (MIN_DIST = 1e-6 vs Plotly's ~0.05 floor).
  // In 'cursor' mode the camera also drifts toward the z=0 orbital-plane point
  // under the mouse cursor on each zoom-in step.
  //
  // The listener itself does no work beyond accumulating the delta. Rebuilding
  // a gl3d scene costs far more than the gap between two wheel events, so
  // acting on each event in turn queues relayouts faster than they can retire
  // and the view arrives in lurches. _scheduleWheel applies whatever has
  // accumulated once per animation frame, and never while a previous update is
  // still rendering.
  function _initScrollZoom(gd) {
    if (_scrollAC) { try { _scrollAC.abort(); } catch (e) {} }
    _scrollAC = new AbortController();
    var signal = _scrollAC.signal;
    if (_wheelRAF)   { cancelAnimationFrame(_wheelRAF); _wheelRAF = 0; }
    if (_wheelTimer) { clearTimeout(_wheelTimer);       _wheelTimer = 0; }
    _wheelAccum = 0;
    _wheelBusy  = false;

    // Track mouse position (0..1) continuously for cursor-mode zoom.
    gd.addEventListener('mousemove', function (evt) {
      var rect = gd.getBoundingClientRect();
      _mousePos.x = (evt.clientX - rect.left) / (rect.width  || 1);
      _mousePos.y = (evt.clientY - rect.top)  / (rect.height || 1);
    }, {signal: signal, passive: true});

    gd.addEventListener('wheel', function (evt) {
      evt.preventDefault();
      evt.stopImmediatePropagation();
      if (!_sa_ranges && !captureRanges(gd)) return;

      // Normalise the event to wheel "notches". One detent of a classic mouse
      // wheel is deltaY 100 in pixel mode; a trackpad sends a stream of small
      // deltas instead. Summing them means a gesture zooms by how far it was
      // pushed rather than by how many events the device happened to emit —
      // the fixed per-event step this replaced made a trackpad flick travel
      // dozens of times further than the same flick on a wheel.
      var unit    = evt.deltaMode === 1 ? 33 : (evt.deltaMode === 2 ? 400 : 1);
      var notches = (evt.deltaY * unit) / 100;
      if (!notches) return;
      _wheelAccum += Math.max(-4, Math.min(4, notches));
      _scheduleWheel(gd);
    }, {signal: signal, capture: true, passive: false});
  }

  function _scheduleWheel(gd) {
    if (_wheelRAF || _wheelTimer) return;
    var run = function () {
      if (_wheelRAF)   { cancelAnimationFrame(_wheelRAF); _wheelRAF = 0; }
      if (_wheelTimer) { clearTimeout(_wheelTimer);       _wheelTimer = 0; }
      // Hold the pending delta rather than dropping it: a double-click zoom
      // owns the scene for 600 ms, and a relayout still rendering means the
      // renderer is the bottleneck. Either way the gesture resumes where it
      // left off instead of being swallowed, which is what the old handler did
      // for the whole 600 ms lock.
      if (_rescaleLock || _wheelBusy) { if (_wheelAccum) _scheduleWheel(gd); return; }
      // Ease rather than jump: take a fraction of what is pending each frame
      // and leave the rest for the next, so one wheel detent becomes a short
      // glide over ~5 frames instead of a single 12% cut. The total travelled
      // is unchanged -- every notch is still applied, just spread out -- and
      // the extra frames are camera-only moves, the cheap kind of update.
      // release() in _applyWheelZoom reschedules while anything is left.
      var accum = Math.abs(_wheelAccum) <= WHEEL_EASE_TAIL
                ? _wheelAccum : _wheelAccum * WHEEL_EASE;
      _wheelAccum -= accum;
      if (Math.abs(_wheelAccum) < 1e-6) _wheelAccum = 0;
      if (accum) _applyWheelZoom(gd, accum);
    };
    _wheelRAF = requestAnimationFrame(run);
    // rAF never fires in a hidden or occluded tab, and can be starved under
    // load, so a plain timer backs it up. Whichever arrives first cancels the
    // other, so a scroll is coalesced but never simply dropped.
    _wheelTimer = setTimeout(run, 100);
  }

  // Apply `accum` notches of zoom (positive out, negative in) as one scene
  // update. Everything works in AU; normalised coordinates are produced only
  // at the end, for the camera Plotly is handed.
  function _applyWheelZoom(gd, accum) {
    if (!_sa_ranges && !captureRanges(gd)) return;

    var scam   = gd.layout && gd.layout.scene && gd.layout.scene.camera;
    var eye    = (scam && scam.eye)    || {x: 1.25, y: 1.25, z: 1.25};
    var center = (scam && scam.center) || {x: 0,    y: 0,    z: 0   };
    var up     = (scam && scam.up)     || {x: 0,    y: 0,    z: 1   };

    // ── Convert camera to AU ────────────────────────────────────────────────
    var xr = _sa_ranges.xr, yr = _sa_ranges.yr, zr = _sa_ranges.zr;
    var xMid = (xr[0]+xr[1])/2, xHalf = (xr[1]-xr[0])/2;
    var yMid = (yr[0]+yr[1])/2, yHalf = (yr[1]-yr[0])/2;
    var zMid = (zr[0]+zr[1])/2, zHalf = (zr[1]-zr[0])/2;
    var sceneHalf = Math.max(xHalf, yHalf, zHalf) || 1;

    var eyeAU  = {x: eye.x*sceneHalf+xMid,    y: eye.y*sceneHalf+yMid,    z: eye.z*sceneHalf+zMid};
    var centAU = {x: center.x*sceneHalf+xMid, y: center.y*sceneHalf+yMid, z: center.z*sceneHalf+zMid};
    var edxAU = eyeAU.x-centAU.x, edyAU = eyeAU.y-centAU.y, edzAU = eyeAU.z-centAU.z;
    var distAU = Math.sqrt(edxAU*edxAU + edyAU*edyAU + edzAU*edzAU) || 0.001;

    // ── Zoom step ───────────────────────────────────────────────────────────
    // Proportional to the accumulated notches, so half a notch travels half as
    // far as a whole one. Clamped per update: a hard flick still cannot move
    // the camera more than 2× in one frame, which is what keeps a fast gesture
    // reading as motion rather than as a cut.
    var STEP      = 0.88;
    var MIN_AU    = 1e-6;
    var factor    = Math.max(0.5, Math.min(2, Math.pow(STEP, -accum)));
    var newDistAU = Math.max(MIN_AU, distAU * factor);

    // ── Cursor-mode center drift (computed in normalized, converted to AU) ──
    var newCentAU = {x: centAU.x, y: centAU.y, z: centAU.z};
    if (_zoomMode === 'cursor' && factor < 1) {
      var fwdX = center.x-eye.x, fwdY = center.y-eye.y, fwdZ = center.z-eye.z;
      var flen = Math.sqrt(fwdX*fwdX+fwdY*fwdY+fwdZ*fwdZ)||1;
      fwdX/=flen; fwdY/=flen; fwdZ/=flen;
      var rX=fwdY*up.z-fwdZ*up.y, rY=fwdZ*up.x-fwdX*up.z, rZ=fwdX*up.y-fwdY*up.x;
      var rlen=Math.sqrt(rX*rX+rY*rY+rZ*rZ)||1; rX/=rlen; rY/=rlen; rZ/=rlen;
      var uX=rY*fwdZ-rZ*fwdY, uY=rZ*fwdX-rX*fwdZ, uZ=rX*fwdY-rY*fwdX;
      var ndx=(_mousePos.x-0.5)*2, ndy=(0.5-_mousePos.y)*2, halfTan=0.414;
      var rdX=fwdX+rX*ndx*halfTan+uX*ndy*halfTan;
      var rdY=fwdY+rY*ndx*halfTan+uY*ndy*halfTan;
      var rdZ=fwdZ+rZ*ndx*halfTan+uZ*ndy*halfTan;
      if (Math.abs(rdZ) > 0.01) {
        var t = -eye.z / rdZ;
        var eyeDistN = Math.sqrt(eye.x*eye.x+eye.y*eye.y+eye.z*eye.z)||1;
        if (t > 0 && t < eyeDistN * 10) {
          var tgtNX = eye.x+t*rdX, tgtNY = eye.y+t*rdY;
          var lerpAmt = (1-factor)*0.5;
          newCentAU = {
            x: (center.x+(tgtNX-center.x)*lerpAmt)*sceneHalf+xMid,
            y: (center.y+(tgtNY-center.y)*lerpAmt)*sceneHalf+yMid,
            z: centAU.z
          };
        }
      }
    }

    // ── Ideal scene half = distAU × 6, clamped to original full-system ─────
    var origHalf   = (_sceneOrigHalfAU || sceneHalf);
    var targetHalf = Math.min(newDistAU * 6, origHalf);
    targetHalf     = Math.max(targetHalf, 1e-5);

    // Re-cutting the scene box is the expensive half of a zoom: Plotly
    // re-normalises against the new ranges and re-uploads every trace's
    // geometry, where moving the camera alone costs a fraction of that. So the
    // box on screen is kept while the camera is still a reasonable fit for it,
    // and re-cut only once the ratio leaves the band — roughly one rebuild per
    // five notches instead of one per event. The band is narrow enough that
    // the normalised eye distance stays inside 0.08–0.33, well within the
    // bounds _pullBound enforces.
    var idealHalf = targetHalf;
    if (sceneHalf > 0) {
      var fitRatio = targetHalf / sceneHalf;
      if (fitRatio > 0.5 && fitRatio < 2) idealHalf = sceneHalf;
    }
    idealHalf = Math.max(idealHalf, 1e-5);

    // ── The box must follow the camera ──────────────────────────────────────
    // WebGL clips everything nearer the eye than its near plane, and Plotly
    // sets that plane in *normalised* scene units -- a fixed fraction of the
    // box, whatever the box holds.  So the camera's distance from what it is
    // looking at has to stay a healthy fraction of the box.  Let the box stay
    // large while the camera keeps dollying in and the near plane ends up
    // *past* the target: everything on the camera's side of it is sliced off,
    // along a flat cut through the middle of the view.  Every band became a
    // half-disc, every orbit a half-ellipse.
    //
    // That is exactly what the moon-system floor below used to do.  It is
    // `zoom_half_au`, which for the Sun is 1,050 AU: the Solar System has no
    // 50x gap between Neptune, Pluto, Eris and Planet Nine, so the Sun's "moon
    // system" is the whole system.  Scrolling toward the middle of the view --
    // toward the Sun -- pinned the box at 1,050 AU while the camera went on in
    // to fractions of an AU, down to 5e-8 of the box.
    //
    // safeHalf is the largest box the camera can sit in at MIN_EYE_NORM or
    // better, and nothing below -- not the sticky box, not the floor -- may
    // exceed it.  MIN_EYE_NORM is 8x Plotly's 0.01 near plane, and it is the
    // bottom of the 0.08-0.33 band the sticky box was always meant to hold.
    var MIN_EYE_NORM = 0.08;
    var safeHalf = newDistAU / MIN_EYE_NORM;
    idealHalf = Math.min(idealHalf, safeHalf);

    // ── Snap scene center to nearest body; enforce its moon-system floor ────
    // The floor keeps a planet's moons in frame as the camera closes on it,
    // which is what makes Jupiter's system readable -- but it may only raise
    // the box as far as safeHalf, or it is the bug above again.  And the snap
    // happens only when the camera's own target stays well inside the box it
    // snaps to.  It used to be judged against zoom_half_au, which put the
    // Sun's snap radius at 525 AU: the box re-centred on the Sun with the
    // camera looking at a point hundreds of AU outside it.
    var sceneCentAU  = {x: newCentAU.x, y: newCentAU.y, z: newCentAU.z};
    var nearest = _findNearestBody(gd, center);
    if (nearest && nearest.info && nearest.info.zoom_half_au) {
      var flooredHalf = Math.max(idealHalf,
                                 Math.min(nearest.info.zoom_half_au, safeHalf));
      var ndstAU = Math.sqrt(
        (nearest.x-newCentAU.x)*(nearest.x-newCentAU.x)+
        (nearest.y-newCentAU.y)*(nearest.y-newCentAU.y)+
        (nearest.z-newCentAU.z)*(nearest.z-newCentAU.z));
      if (ndstAU < flooredHalf * 0.5) {
        sceneCentAU = {x: nearest.x, y: nearest.y, z: nearest.z};
        idealHalf   = flooredHalf;
      }
    }

    // ── When fully zoomed out, lock to original and clear stack ────────────
    // Judged on the box the camera WANTS, not on the sticky one. targetHalf is
    // capped at origHalf, so once the sticky box passed origHalf / 2 the ratio
    // stayed inside the band, the box stopped growing short of 0.95, and the
    // lock never fired: zooming out of 55 Cnc B left a 1,000 AU box parked
    // on B, with A's half of the system cut off at its edge.
    if (idealHalf >= origHalf * 0.95 || newDistAU * 6 >= origHalf * 0.95) {
      idealHalf   = origHalf;
      sceneCentAU = {x: 0, y: 0, z: 0};
      _sceneStack = [];
    }

    // ── The box never leaves the full-system box ───────────────────────────
    // A box centred on an outlying body reaches past the edge of the system
    // into empty space, and cuts the far side of the system off by the same
    // amount. Sliding it back inside keeps the body in view -- a centre moved
    // by at most the overshoot, which is less than the half-width -- and makes
    // the box converge on the whole system as it grows, instead of jumping
    // there only at the lock.
    sceneCentAU = _clampInsideOrig(sceneCentAU, idealHalf);

    // ── Keep the box put while it still frames the target ─────────────────
    // Cursor-mode drift moves the target on every step, and re-centring the
    // box to follow it re-cut the scene -- the expensive update -- on every
    // step too. A box of unchanged size whose centre is still near the target
    // is kept as it is.
    if (idealHalf === sceneHalf) {
      var curC = {x: xMid, y: yMid, z: zMid};
      var dcx = sceneCentAU.x - curC.x, dcy = sceneCentAU.y - curC.y,
          dcz = sceneCentAU.z - curC.z;
      if (Math.sqrt(dcx*dcx + dcy*dcy + dcz*dcz) < idealHalf * 0.25) {
        sceneCentAU = curC;
      }
    }

    // ── Zooming out brings the target home ─────────────────────────────────
    // The camera keeps looking at whatever it was zoomed into, so without this
    // a full zoom-out ends with the whole system on screen but framed around
    // an outlying body at the edge of it. Each step out moves the target
    // toward the box centre in proportion to the step, so it glides in rather
    // than jumping. The snap keeps the box centred on the body until the
    // clamp above starts pulling it toward the system, so zooming out around
    // a planet's moons leaves the target where it is.
    if (factor > 1) {
      var pull = Math.min(1, 1 - 1 / factor);
      newCentAU = {
        x: newCentAU.x + (sceneCentAU.x - newCentAU.x) * pull,
        y: newCentAU.y + (sceneCentAU.y - newCentAU.y) * pull,
        z: newCentAU.z + (sceneCentAU.z - newCentAU.z) * pull
      };
    }

    // ── Update _sa_ranges with new scene ───────────────────────────────────
    var newXr = [sceneCentAU.x-idealHalf, sceneCentAU.x+idealHalf];
    var newYr = [sceneCentAU.y-idealHalf, sceneCentAU.y+idealHalf];
    var newZr = [sceneCentAU.z-idealHalf, sceneCentAU.z+idealHalf];
    // Identical inputs give bit-identical bounds, so === is enough to tell a
    // camera-only update from one that has to re-cut the box.
    var boxUnchanged = xr[0] === newXr[0] && xr[1] === newXr[1]
                    && yr[0] === newYr[0] && yr[1] === newYr[1]
                    && zr[0] === newZr[0] && zr[1] === newZr[1];
    _sa_ranges = {xr: newXr.slice(), yr: newYr.slice(), zr: newZr.slice()};
    window._SA_SCENE_RANGES = {xr: newXr, yr: newYr, zr: newZr};
    _sceneHalfAU = idealHalf;

    // ── New eye in AU → convert to new scene normalized ────────────────────
    var newEyeAU = {
      x: newCentAU.x + edxAU/distAU * newDistAU,
      y: newCentAU.y + edyAU/distAU * newDistAU,
      z: newCentAU.z + edzAU/distAU * newDistAU
    };
    var newEye = {
      x: (newEyeAU.x - sceneCentAU.x) / idealHalf,
      y: (newEyeAU.y - sceneCentAU.y) / idealHalf,
      z: (newEyeAU.z - sceneCentAU.z) / idealHalf
    };
    var newCenter = {
      x: (newCentAU.x - sceneCentAU.x) / idealHalf,
      y: (newCentAU.y - sceneCentAU.y) / idealHalf,
      z: (newCentAU.z - sceneCentAU.z) / idealHalf
    };

    var zoomLayout = {'scene.camera': {eye: newEye, center: newCenter, up: up}};

    // Backpressure: no further zoom update starts until this one has rendered,
    // so a long gesture tracks the input instead of queueing work the renderer
    // cannot retire.
    //
    // The watchdog matters as much as the flag. Plotly resolves the relayout
    // promise from its render loop, and a stalled or throttled renderer can
    // leave it pending indefinitely — which would strand _wheelBusy true and
    // kill scroll zoom for the rest of the session. Releasing on a timer at
    // worst falls back to the un-throttled behaviour; never releasing means
    // the wheel stops working.
    _wheelBusy = true;
    var settled = false;
    var release = function () {
      if (settled) return;
      settled = true;
      clearTimeout(watchdog);
      _wheelBusy = false;
      if (_wheelAccum) _scheduleWheel(gd);
    };
    var watchdog = setTimeout(release, 1000);
    try {
      var pr;
      if (boxUnchanged) {
        pr = Plotly.relayout(gd, zoomLayout);
      } else {
        zoomLayout['scene.xaxis.range'] = newXr;
        zoomLayout['scene.yaxis.range'] = newYr;
        zoomLayout['scene.zaxis.range'] = newZr;
        pr = updateSceneVisibility(gd, newXr, newYr, newZr, zoomLayout);
      }
      if (pr && pr.then) { pr.then(release, release); } else { release(); }
    } catch (e) { release(); }
  }

  // Slide a box of half-width `half` so it lies inside the original
  // full-system box, axis by axis. A box as large as the original is simply
  // centred on it.
  function _clampInsideOrig(c, half) {
    var o = _sa_ranges_orig;
    if (!o) return c;
    var fit = function (v, r) {
      var mid = (r[0] + r[1]) / 2, room = (r[1] - r[0]) / 2 - half;
      if (room <= 0) return mid;
      return Math.max(mid - room, Math.min(mid + room, v));
    };
    return {x: fit(c.x, o.xr), y: fit(c.y, o.yr), z: fit(c.z, o.zr)};
  }

  // ── addControls ────────────────────────────────────────────────────────────
  function addControls(gd_init) {
    // Shared by every handler below, and repointed on a system switch.
    var gd = gd_init;
    _controlsRebind = function (g) { if (g) gd = g; };
    // Wrapper: single fixed row at top-left holding Orient + search.
    var wrap = document.createElement('div');
    wrap.style.cssText = [
      'position:fixed', 'top:8px', 'left:8px',
      'display:flex', 'gap:6px', 'align-items:center', 'z-index:9999'
    ].join(';');

    // --- Orient button ---
    var orientBtn = document.createElement('button');
    orientBtn.textContent = '\u29BF  Orient';
    orientBtn.title = 'View from 100 AU above the system origin';
    orientBtn.style.cssText = _btnCss;
    orientBtn.addEventListener('mouseover', function () { _hoverOn(orientBtn); });
    orientBtn.addEventListener('mouseout',  function () { _hoverOff(orientBtn); });
    orientBtn.addEventListener('click', function () { viewFromAbove(gd); });

    // --- Back button: undo the last double-click / search zoom ---
    // Scroll zoom rewrites the scene in place and pushes nothing, so the stack
    // holds only the discrete jumps a user made by picking a body.
    var backBtn = document.createElement('button');
    backBtn.textContent = '\u25C1  Back';
    backBtn.title = 'Return to the scene before the last body zoom';
    backBtn.style.cssText = _btnCss;
    backBtn.addEventListener('mouseover', function () { _hoverOn(backBtn); });
    backBtn.addEventListener('mouseout',  function () { _hoverOff(backBtn); });
    backBtn.addEventListener('click', function () {
      if (!_sceneStack.length) { showToast('Already at the widest view'); return; }
      restoreScene(gd);
    });

    // --- Bands button: every solvent band in the system, together ---
    // The figure opens on the orbits alone, and each band still has its own
    // legend entry.  This is the control over all of them at once: at 1 bar
    // the Solar System carries seven bands, and clicking seven legend entries
    // is not a way to answer "where is water liquid".
    //
    // The label is read back off the traces, so a band switched on from the
    // legend shows up here as "Some" rather than leaving the label lying.
    var bandsBtn = document.createElement('button');
    bandsBtn.style.cssText = _btnCss;
    function _updateBandsBtn() {
      var s = _bandSummary(gd);
      bandsBtn.textContent = '\u25CE  Bands: ' +
        (s.state === 'all' ? 'On' : (s.state === 'some' ? 'Some' : 'Off'));
      bandsBtn.title = s.state === 'all'
        ? 'All ' + s.total + ' band traces shown \u2014 click to hide them all'
        : (s.state === 'some'
            ? s.on + ' of ' + s.total + ' band traces shown \u2014 click to show them all'
            : 'Solvent bands hidden \u2014 click to show them all, '
              + 'or switch one on from the legend');
    }
    _updateBandsBtn();
    _bandsBtnSync = _updateBandsBtn;
    bandsBtn.addEventListener('mouseover', function () { _hoverOn(bandsBtn); });
    bandsBtn.addEventListener('mouseout',  function () { _hoverOff(bandsBtn); });
    bandsBtn.addEventListener('click', function () {
      // Read before the flip, so the label never claims bands are on in a
      // system that has none to show.
      var summary = _bandSummary(gd);
      if (!summary.total) {
        showToast('No solvent bands in this system');
        return;
      }
      // Anything short of all-on means the click switches everything on; only
      // a full set switches off.  That is what makes the button a way out of
      // a mess of individually toggled bands rather than another one.
      var on = summary.state !== 'all';
      _setAllBands(gd, on);
      _updateBandsBtn();
      showToast(on ? 'All solvent bands on' : 'All solvent bands off');
    });

    // --- Search input ---
    var input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Search\u2026';
    input.style.cssText = [
      'background:#111130', 'color:#aaddff',
      'border:1px solid #333366', 'border-radius:4px',
      'padding:4px 8px', 'font-family:monospace', 'font-size:12px',
      'width:130px', 'outline:none'
    ].join(';');

    // --- Search button ---
    var searchBtn = document.createElement('button');
    searchBtn.textContent = '\u2192';
    searchBtn.title = 'Jump to a body, belt or band';
    searchBtn.style.cssText = _btnCss;
    searchBtn.addEventListener('mouseover', function () { _hoverOn(searchBtn); });
    searchBtn.addEventListener('mouseout',  function () { _hoverOff(searchBtn); });

    function doSearch() {
      var q = input.value.trim();
      if (!q) return;
      var found = searchTrace(gd, q);
      if (found) {
        input.value = '';
        zoomTo(gd, +found.x[0], +found.y[0], +found.z[0], found.name);
        return;
      }
      // No body marker matched — try belts, solvent bands and orbit lines.
      var group  = searchTraceGroup(gd, q);
      var target = group && traceGroupTarget(group);
      if (!target) { showToast('Not found: ' + q); return; }
      // Label the jump with the shortest name in the group: for a solvent band
      // that is the core ring rather than one of its albedo margins.
      var label = group[0].name;
      for (var gi = 1; gi < group.length; gi++) {
        if (group[gi].name.length < label.length) label = group[gi].name;
      }
      // A band matched by name is switched on if it was off: framing a ring
      // the viewer cannot see is not an answer to the search.  Only the band
      // that matched -- the rest stay as the viewer left them.
      var wanted = [];
      for (var bi = 0; bi < group.length; bi++) {
        var gi = [].indexOf.call(gd.data, group[bi]);
        if (gi >= 0 && _isBandTrace(group[bi]) && !_bandOn(gi)) wanted.push(gi);
      }
      if (wanted.length) { _showBands(gd, wanted, true); _updateBandsBtn(); }
      input.value = '';
      zoomTo(gd, target.x, target.y, target.z, label, target.halfAU);
    }

    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') doSearch(); });
    searchBtn.addEventListener('click', doSearch);

    wrap.appendChild(orientBtn);
    wrap.appendChild(backBtn);
    wrap.appendChild(bandsBtn);
    wrap.appendChild(input);
    wrap.appendChild(searchBtn);
    document.body.appendChild(wrap);

    // --- Zoom-mode toggle button (bottom-right) ---
    var zoomBtn = document.createElement('button');
    zoomBtn.style.cssText = _btnCss + ';position:fixed;bottom:8px;right:8px;z-index:9999';
    function _updateZoomBtn() {
      zoomBtn.textContent = _zoomMode === 'center'
        ? '\u2295  Zoom: Center'
        : '\u2295  Zoom: Cursor';
      zoomBtn.title = _zoomMode === 'center'
        ? 'Scroll zooms toward scene center \u2014 click to switch to cursor mode'
        : 'Scroll zooms toward cursor \u2014 click to switch to center mode';
    }
    _updateZoomBtn();
    zoomBtn.addEventListener('mouseover', function () { _hoverOn(zoomBtn); });
    zoomBtn.addEventListener('mouseout',  function () { _hoverOff(zoomBtn); });
    zoomBtn.addEventListener('click', function () {
      _zoomMode = _zoomMode === 'center' ? 'cursor' : 'center';
      _updateZoomBtn();
    });
    document.body.appendChild(zoomBtn);

    // --- Band sliders: pressure and albedo ---
    // Built by _bandPanel() in band_kit.js, which the three.js viewer shares,
    // so the track, the typed readouts and their rules exist once. Changes
    // arrive here coalesced to one per animation frame.
    var bandPanel = _bandPanel({
      toast: showToast,
      onChange: function (P, A, G) {
        _bandP = P; _bandA = A; _bandG = G;
        _recomputeBands(gd);
        if (_bandsBtnSync) _bandsBtnSync();
      }
    }).el;
    document.body.appendChild(bandPanel);

    // Shown only where there is something to move: a system whose star has no
    // known luminosity carries no bands at all.
    _bandPanelSync = function () {
      bandPanel.style.display = _bandTraceIndices(gd).length ? 'block' : 'none';
    };
    _bandPanelSync();

    createInfoPanel();  // create the panel element once; shown/hidden on demand
  }

  // ── searchTrace ────────────────────────────────────────────────────────────
  // Find the best-matching marker trace (single-point traces only — orbit lines
  // have many points). Tries exact match first, then prefix, then substring.
  // Body markers only. A plain .length of 1 is the test: Plotly leaves
  // single-point arrays as JS arrays and base64-encodes the multi-point ones,
  // so every line, coil and mesh fails this check without being decoded.
  function searchTrace(gd, query) {
    var cand = [];
    for (var i = 0; i < gd.data.length; i++) {
      var t = gd.data[i];
      if (!t.name || !t.x || t.x.length !== 1) continue;
      cand.push(t);
    }
    var hit = _nameMatches(cand.map(function (t) { return t.name; }), query);
    return hit.length ? cand[hit[0]] : null;
  }


  // ── searchTraceGroup ─────────────────────────────────────────────────
  // Second-pass search, over traces that searchTrace skips: belts, solvent
  // bands, orbit lines.  It runs only when no body marker matched, so typing
  // "Jupiter" still finds the planet rather than its orbit line.
  //
  // Returns every trace in the best-matching tier rather than the first one.
  // A solvent band is three separate rings sharing a name prefix, and framing
  // only the first would cut off the rest of the band.
  function searchTraceGroup(gd, query) {
    var cand = gd.data.filter(function (t) { return t.name && t.x; });
    var hit = _nameMatches(cand.map(function (t) { return t.name; }), query);
    return hit.length ? hit.map(function (i) { return cand[i]; }) : null;
  }


  // ── traceGroupTarget ─────────────────────────────────────────────────
  // Centre and half-extent that frame a group of traces, in AU.  A band is a
  // ring around the origin, so the bounding-box centre lands on the star and
  // the half-extent reaches its outer edge.
  function traceGroupTarget(traces) {
    var axes = ['x', 'y', 'z'];
    var lo = [Infinity, Infinity, Infinity];
    var hi = [-Infinity, -Infinity, -Infinity];
    for (var i = 0; i < traces.length; i++) {
      for (var a = 0; a < 3; a++) {
        var arr = _coords(traces[i][axes[a]]) || [];
        for (var j = 0; j < arr.length; j++) {
          var v = +arr[j];
          if (!isFinite(v)) continue;
          if (v < lo[a]) lo[a] = v;
          if (v > hi[a]) hi[a] = v;
        }
      }
    }
    if (!isFinite(lo[0]) || !isFinite(hi[0])) return null;
    var cx = (lo[0]+hi[0])/2, cy = (lo[1]+hi[1])/2, cz = (lo[2]+hi[2])/2;
    var c = [cx, cy, cz], half = 0;
    for (var a2 = 0; a2 < 3; a2++) {
      half = Math.max(half, hi[a2] - c[a2], c[a2] - lo[a2]);
    }
    return {x: cx, y: cy, z: cz, halfAU: Math.max(half * 1.15, 1e-5)};
  }

  // ── showToast ──────────────────────────────────────────────────────────────
  function showToast(name) {
    var el = document.getElementById('_sa_zoom_toast');
    if (!el) {
      el = document.createElement('div');
      el.id = '_sa_zoom_toast';
      el.style.cssText = [
        'position:fixed', 'top:56px', 'left:50%', 'transform:translateX(-50%)',
        'background:rgba(8,8,30,0.88)', 'color:#aaddff',
        'padding:6px 18px', 'border-radius:5px', 'border:1px solid #334d6e',
        'font-family:monospace', 'font-size:13px', 'pointer-events:none',
        'z-index:9999', 'transition:opacity 0.5s'
      ].join(';');
      document.body.appendChild(el);
    }
    el.style.opacity = '1';
    el.textContent = '\u25CE  ' + name;
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.style.opacity = '0'; }, 2200);
  }

  // ── _saReattach ────────────────────────────────────────────────────────────
  // Exposed so the system switcher can re-initialize the click handler and
  // range cache after a system swap.
  window._saReattach = function (gd) {
    // Point the already-built controls at this div before anything else:
    // a system switch hands us a new one.
    if (_controlsRebind) _controlsRebind(gd);
    _sa_ranges       = null;
    _sa_ranges_orig  = null;
    _sceneHalfAU     = null;
    _sceneOrigHalfAU = null;
    _sceneStack      = [];
    _rescaleLock     = false;
    // The swapped-in system has its own geometry, and the cache holds the old
    // one's originals. Trace counts can match across systems, so the count
    // check in updateSceneVisibility is not enough to catch this on its own.
    _geom            = null;
    _wheelAccum      = 0;
    _wheelBusy       = false;
    captureRanges(gd);
    if (_sa_ranges) {
      updateSceneVisibility(gd, _sa_ranges.xr, _sa_ranges.yr, _sa_ranges.zr);
    }
    // The swapped-in system's bands arrive on 'legendonly' the way every
    // figure's do, so a viewer who had them on has to be handed them again.
    // Per-band choices do not cross a swap: a different system is a different
    // set of bands, and the button's setting is what a new one opens with.
    // The swapped-in system's bands were built by Python at the pressure and
    // albedo the page opened on, not at wherever the sliders have since been
    // dragged to, so they are recomputed before being switched.
    _recomputeBands(gd);
    _setAllBands(gd, _bandsOn);
    if (_bandsBtnSync)  _bandsBtnSync();
    if (_bandPanelSync) _bandPanelSync();

    // Remove any stale listeners before attaching fresh ones.
    try { gd.removeAllListeners('plotly_click');   } catch (e) {}
    try { gd.removeAllListeners('plotly_relayout'); } catch (e) {}
    try { gd.removeAllListeners('plotly_legendclick');       } catch (e) {}
    try { gd.removeAllListeners('plotly_legenddoubleclick'); } catch (e) {}

    // A band's legend entry is handled here rather than by Plotly, and only a
    // band's: everything else keeps Plotly's own toggle. Two reasons the
    // default will not do for a band. It sets visible:true outright, so a band
    // switched on while zoomed into a moon would arrive unclipped, with
    // coordinates far outside the scene box -- the thing that collapses the
    // view to bare gridlines. And the clipper would not know the viewer had
    // asked for it, so the next zoom would drop it again.
    gd.on('plotly_legendclick', function (ev) {
      if (!ev || ev.curveNumber === undefined) return;
      var i = ev.curveNumber;
      if (!_isBandTrace(gd.data[i])) return;
      _showBands(gd, _bandGroup(gd, i), !_bandOn(i));
      if (_bandsBtnSync) _bandsBtnSync();
      return false;   // Plotly must not also toggle it
    });

    // Plotly's legend double-click isolates the clicked trace, switching every
    // other one off behind the clipper's back. The first click of the pair has
    // already toggled the band, so this only has to stop the isolate.
    gd.on('plotly_legenddoubleclick', function (ev) {
      if (!ev || ev.curveNumber === undefined) return;
      if (!_isBandTrace(gd.data[ev.curveNumber])) return;
      return false;
    });

    var lastClick = { time: 0, target: null };

    // plotly_click fires for every click on a data point (including both clicks
    // of a double-click).  We detect the double-click by timing, then schedule
    // the zoom 100 ms later so it fires AFTER Plotly's own double-click reset.
    gd.on('plotly_click', function (ev) {
      if (!ev || !ev.points || !ev.points.length) return;
      var pt  = ev.points[0];
      var x   = +pt.x, y = +pt.y, z = +pt.z;
      if (isNaN(x) || isNaN(y) || isNaN(z)) return;

      var traceName = pt.data.name || '';

      // If the user clicked an orbit or axis line (multi-point trace), redirect
      // to the corresponding body marker so zoom lands on the planet itself.
      if (!pt.data.x || pt.data.x.length !== 1) {
        var bodyName = traceName.replace(/ orbit$/, '').replace(/ axis$/, '');
        var marker = searchTrace(gd, bodyName);
        if (marker) {
          x = +marker.x[0]; y = +marker.y[0]; z = +marker.z[0];
          traceName = marker.name;
        }
      }

      var now    = Date.now();
      var target = { x: x, y: y, z: z, name: traceName };

      if (now - lastClick.time < 500 && lastClick.target) {
        // Second click within 500 ms → double-click confirmed.
        var t = target;
        setTimeout(function () { zoomTo(gd, t.x, t.y, t.z, t.name); }, 100);
        lastClick = { time: 0, target: null };
      } else {
        lastClick = { time: now, target: target };
      }
    });

    // Hide the info panel when the camera moves.  An 800 ms grace period
    // prevents the hide from triggering on the Plotly.relayout call issued by
    // zoomTo itself (which fires plotly_relayout too).
    gd.on('plotly_relayout', function () {
      if (_infoPanelEl && Date.now() - _infoPanelShownAt > 800) {
        hideInfoPanel();
      }
    });

    _initScrollZoom(gd);  // attach (or re-attach) deep scroll-zoom handler
  };

  // ── Init ───────────────────────────────────────────────────────────────────
  function attachHandlers() {
    var divs = document.querySelectorAll('.plotly-graph-div');
    if (!divs.length) { setTimeout(attachHandlers, 300); return; }

    var gd = divs[0];
    addControls(gd);        // UI elements created once
    window._saReattach(gd); // attach click + relayout handlers, capture ranges
  }

  // Plotly renders asynchronously; poll until the div is ready.
  setTimeout(attachHandlers, 600);
})();
"""
_ZOOM_JS = _ZOOM_JS.replace("  /*@@BAND_KIT@@*/" + chr(10), BAND_KIT_JS, 1)


def _build_switcher_js(figures_by_name: dict, initial_system: str) -> str:
    """Build the system-switcher JavaScript block.

    Embeds all figures as compact JSON constants, creates a button row at
    top-right, and exposes window._saSwitch(name).  When switching, it:
      1. Hides the info panel (body may not exist in the new system).
      2. Stops any running animation.
      3. Calls Plotly.newPlot() with the new figure's data + layout.
         Not react: react updates traces in place by index and will not
         reliably change a trace's type, and the same index is a different
         kind of trace in every system.
      4. Overwrites animation frames (same frame names → safe overwrite).
      5. Jumps to frame 0 of the new system.
      6. Calls window._saReattach() to reset the zoom range cache and
         re-attach the double-click and relayout handlers.
    """
    all_systems: dict = {}
    for name, fig in figures_by_name.items():
        all_systems[name] = json.loads(fig.to_json())

    system_labels: dict = {}
    for name, fig in figures_by_name.items():
        try:
            label = fig.layout.title.text or name
        except Exception:
            label = name
        # Animated titles carry a " — <date>" suffix; the switcher button wants
        # the system name alone, and it must not shift as frames advance.
        system_labels[name] = label.split(" — ")[0]

    systems_js = json.dumps(all_systems, separators=(",", ":"))
    labels_js  = json.dumps(system_labels)
    initial_js = json.dumps(initial_system)

    return f"""
(function () {{
  var _SA_SYSTEMS = {systems_js};
  var _SA_LABELS  = {labels_js};
  var _SA_CURRENT = {initial_js};
  var _SA_BUTTONS = {{}};

  var _activeBg  = '#1a1a80', _inactiveBg  = '#111130';
  var _activeBdr = '#6666cc', _inactiveBdr = '#333366';

  function _setActive(name) {{
    Object.keys(_SA_BUTTONS).forEach(function (k) {{
      var b = _SA_BUTTONS[k];
      b.style.background   = k === name ? _activeBg  : _inactiveBg;
      b.style.borderColor  = k === name ? _activeBdr : _inactiveBdr;
    }});
  }}

  window._saSwitch = function (name) {{
    if (name === _SA_CURRENT) return;
    // Hide any open info panel — the selected body may not exist in new system.
    if (window._saHideInfo) window._saHideInfo();
    _SA_CURRENT = name;
    _setActive(name);
    // Swap scene ranges so captureRanges uses the correct extents for the new system.
    window._SA_SCENE_RANGES = window._SA_ALL_RANGES && window._SA_ALL_RANGES[name];
    // The new system has its own band plane, and Orient has to follow it.
    window._SA_VIEW_NORMAL = (window._SA_ALL_VIEW_NORMALS
                              && window._SA_ALL_VIEW_NORMALS[name]) || [0, 0, 1];

    var gd  = document.querySelector('.plotly-graph-div');
    var fig = _SA_SYSTEMS[name];
    if (!gd || !fig) return;

    // Stop any running animation before replacing figure data.
    try {{
      Plotly.animate(gd, null, {{
        mode: 'immediate', transition: {{duration: 0}}, frame: {{duration: 0, redraw: false}}
      }});
    }} catch (e) {{}}

    // Plot into a *fresh* div, never the one the previous system used.
    //
    // A frame carries the trace *indices* it writes to, and an index means
    // something different in every system.  The Solar System's frames write
    // single-point markers and axis lines to traces 18-46; in Alpha Centauri
    // traces 13-36 are the solvent bands.  Swapping figures on the same div
    // let the old system's frame data reach the new system's traces, turning
    // every mesh3d band that landed on a marker index into a scatter3d.  Such
    // a band was then drawn as its 360 vertices in fat markers -- two rings of
    // beads, at the inner and outer radius -- which reads as a torus rather
    // than a flat disc.
    //
    // The damage is exactly the overlap, which is what made it look like one
    // solvent was plotted differently from another:
    //
    //     into Alpha Centauri from Solar      frames 18-46 x bands 13-36 = 19
    //     into Proxima from TRAPPIST-1        frames  7-14 x bands  7-14 =  8
    //     into TRAPPIST-1 from Alpha Centauri frames  3-9  x bands 15-22 =  0
    //
    // Formamide is trace 17 and Sulfuric acid is trace 18, so coming from the
    // Solar System one was untouched and the next one along was a torus.
    // Nothing about the two bands themselves differed.
    //
    // Replacing the div is what makes this impossible rather than unlikely:
    // there is no previous trace list to index into, no frames left attached
    // and no state to carry over.  Neither newPlot on the same div nor
    // Plotly.purge is enough -- both were tried, and both still corrupted the
    // same nineteen traces.
    var holder = gd.parentNode;
    var fresh  = document.createElement('div');
    fresh.className     = gd.className;
    fresh.id            = gd.id;
    fresh.style.cssText = gd.style.cssText;
    try {{ Plotly.purge(gd); }} catch (e) {{}}
    holder.replaceChild(fresh, gd);
    gd = fresh;

    Plotly.newPlot(gd, {{
      data:   fig.data,
      layout: fig.layout,
      frames: fig.frames || []
    }}, {{responsive: true}}).then(function () {{
      if (fig.frames && fig.frames.length) {{
        // Jump to frame 0 of the new system.
        try {{
          Plotly.animate(gd, ['0'], {{
            mode: 'immediate', transition: {{duration: 0}}, frame: {{duration: 0, redraw: true}}
          }});
        }} catch (e) {{}}
      }}
      if (window._saReattach) window._saReattach(gd);
    }});
  }};

  function buildSwitcherUI() {{
    var gd = document.querySelector('.plotly-graph-div');
    if (!gd) {{ setTimeout(buildSwitcherUI, 300); return; }}

    var wrap = document.createElement('div');
    wrap.style.cssText = [
      'position:fixed', 'top:8px', 'right:8px',
      'display:flex', 'gap:6px', 'align-items:center', 'z-index:9999'
    ].join(';');

    var lbl = document.createElement('span');
    lbl.textContent = 'System:';
    lbl.style.cssText = 'color:#aaddff;font-family:monospace;font-size:12px;';
    wrap.appendChild(lbl);

    var btnBase = [
      'border-radius:4px', 'padding:4px 12px',
      'font-family:monospace', 'font-size:12px', 'cursor:pointer',
      'color:#aaddff', 'border-width:1px', 'border-style:solid'
    ].join(';');

    Object.keys(_SA_LABELS).forEach(function (key) {{
      var btn = document.createElement('button');
      btn.textContent     = _SA_LABELS[key];
      btn.style.cssText   = btnBase;
      btn.style.background  = key === _SA_CURRENT ? _activeBg  : _inactiveBg;
      btn.style.borderColor = key === _SA_CURRENT ? _activeBdr : _inactiveBdr;
      btn.addEventListener('mouseover', function () {{
        if (key !== _SA_CURRENT) btn.style.background = '#1a1a50';
      }});
      btn.addEventListener('mouseout', function () {{
        btn.style.background = key === _SA_CURRENT ? _activeBg : _inactiveBg;
      }});
      btn.addEventListener('click', function () {{ window._saSwitch(key); }});
      _SA_BUTTONS[key] = btn;
      wrap.appendChild(btn);
    }});

    document.body.appendChild(wrap);
  }}

  setTimeout(buildSwitcherUI, 600);
}})();
"""


# ── Body info JS builder ────────────────────────────────────────────────────

# A child orbiting more than this many times farther out than everything kept
# so far belongs to a different scale, not to the same core. Proxima Centauri
# at 8,700 AU sits next to the 23 AU Alpha Cen A-B binary: framing the outlier
# puts the entire system back on screen and leaves the binary unreachable.
CORE_GAP_RATIO = 50.0


def _core_child_extent(smas: list[float]) -> float:
    """Largest semi-major axis among a body's children, ignoring far outliers.

    Walks the children outward and stops at the first gap wider than
    CORE_GAP_RATIO, so the result is the extent of the compact group around the
    parent rather than the distance to its most remote companion.
    """
    kept = 0.0
    for a in sorted(smas):
        if a <= 0.0:
            continue
        if kept > 0.0 and a > kept * CORE_GAP_RATIO:
            break
        kept = a
    return kept


def build_body_info_js(systems_by_name: dict, body_metadata: dict | None = None) -> str:
    """Return a JS snippet that sets window._SA_BODY_INFO.

    The same data as `build_body_info()`, as a script: the file-based viewers
    embed it, and the web app serves the dict with each system instead.
    """
    info_json = json.dumps(build_body_info(systems_by_name, body_metadata),
                           separators=(",", ":"))
    return f"window._SA_BODY_INFO = {info_json};"


def build_body_info(systems_by_name: dict, body_metadata: dict | None = None) -> dict:
    """Body name -> what the info panel shows for it.

    Called by the CLI with all displayed systems so the info panel can look up
    any body by name regardless of which system is currently shown.

    Args:
        systems_by_name: Mapping of system key → StarSystem.
        body_metadata:   Optional dict of body name → display notes, e.g.
                         {"mass_note": "estimated", "tilt_note": "..."}.
                         Typically BODY_METADATA from builtin_systems.
    """
    meta = body_metadata or {}

    # Unicode superscript digits for exponent notation.
    # Using these avoids embedding <sup>…</sup> HTML inside the JSON, which
    # would put closing tags like </sup> into the <script> block — some browsers
    # treat any </ sequence as a potential end-tag and may terminate the block
    # early, causing a JS syntax error that prevents Plotly from rendering.
    _SUPS = str.maketrans(
        "0123456789-",
        "\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207b",
    )

    def fmt_mass(kg: float) -> str:
        exp   = int(math.floor(math.log10(kg)))
        coeff = kg / (10 ** exp)
        sup   = str(exp).translate(_SUPS)
        return f"{coeff:.3g} \u00d7 10{sup} kg"   # e.g. "5.97 × 10²⁴ kg"

    def fmt_period(days: float) -> str:
        if days >= 365.25 * 2:
            return f"{days / 365.25:.2f} yr"
        if days >= 1:
            return f"{days:.4g} d"
        return f"{days * 24:.3g} hr"

    def mean_vel(a_au: float, period_days: float) -> str:
        v = 2 * math.pi * (a_au * 1.496e8) / (period_days * 86400.0)
        return f"{v:.2f} km/s"

    # Build parent → core child extent map (used for zoom_half_au).
    children_sma: dict[str, list[float]] = {}
    for s in systems_by_name.values():
        for b in s.bodies:
            if b.parent and b.elements:
                children_sma.setdefault(b.parent, []).append(b.elements.semi_major_axis)
    parent_to_max_child_sma = {
        name: _core_child_extent(smas) for name, smas in children_sma.items()
    }

    info: dict = {}
    for system in systems_by_name.values():
        bodies_by_name = {b.name: b for b in system.bodies}
        for body in system.bodies:
            bm = meta.get(body.name, {})
            entry: dict = {}

            # Mass
            if body.mass_kg is not None:
                entry["mass"]      = fmt_mass(body.mass_kg)
                entry["mass_note"] = bm.get("mass_note", "")
            else:
                entry["mass"]      = "Unknown"
                entry["mass_note"] = ""

            # Orbital period
            if body.elements is not None:
                entry["period"]      = fmt_period(body.elements.period)
                entry["period_note"] = bm.get("period_note", "")
                entry["orbit_au"]    = body.elements.semi_major_axis
                child_max = parent_to_max_child_sma.get(body.name, 0.0)
                parent = bodies_by_name.get(body.parent) if body.parent else None
                satellite = (body.body_type == "moon"
                             or (parent is not None and parent.elements is not None))
                if child_max > 0:
                    entry["zoom_half_au"] = child_max * 3.0
                elif satellite:
                    # Frame the whole orbit: a satellite is only legible next to
                    # the body it circles, and for a planet of an orbiting star
                    # that orbit is the coil the double-click is meant to show.
                    entry["zoom_half_au"] = max(body.elements.semi_major_axis * 1.5, 0.001)
                else:
                    entry["zoom_half_au"] = max(body.elements.semi_major_axis * 0.01, 0.001)
            else:
                entry["period"]      = "N/A (host body)"
                entry["period_note"] = ""
                child_max = parent_to_max_child_sma.get(body.name, 0.0)
                if child_max > 0:
                    entry["zoom_half_au"] = child_max * 1.5

            # Mean orbital velocity
            if body.elements is not None:
                entry["velocity"]      = mean_vel(body.elements.semi_major_axis,
                                                  body.elements.period)
                entry["velocity_note"] = bm.get("velocity_note", "mean, computed")
            else:
                entry["velocity"]      = "N/A"
                entry["velocity_note"] = ""

            # Axial tilt
            tilt_note = bm.get("tilt_note", "") or body.pole_note or ""
            if body.axial_tilt_deg is not None:
                entry["tilt"]      = f"{body.axial_tilt_deg:.2f}\u00b0"
                entry["tilt_note"] = tilt_note
            else:
                entry["tilt"]      = "Unknown"
                entry["tilt_note"] = tilt_note

            # A planet's measured sense of orbit, and what it is measured against.
            if body.orbit_direction:
                entry["orbit_direction"] = body.orbit_direction

            # Sources
            entry["sources"] = body.sources or []
            if body.info_rows:
                entry["rows"] = body.info_rows

            # What it is: star, planet, moon, barycentre, ...
            entry["type"] = body.body_type

            # Confirmation status
            entry["status"] = body.status
            if body.status_note:
                entry["status_label"] = body.status_note

            # One body can appear in several built-in systems (Proxima's planets
            # are in both alpha-centauri and proxima-centauri) and _SA_BODY_INFO
            # is shared across the switcher. Keep the widest framing so the
            # double-click always lands on the body's orbit rather than inside it.
            prev = info.get(body.label())
            if prev is not None:
                entry["zoom_half_au"] = max(entry.get("zoom_half_au", 0.0),
                                            prev.get("zoom_half_au", 0.0))
            info[body.label()] = entry

    # ensure_ascii=True (default) keeps the JSON output to safe ASCII characters,
    # representing all Unicode (×, °, superscripts) as \uXXXX escapes — valid in
    # JavaScript string literals and completely safe inside a <script> block.
    return info


# ── Solvent-table JS builder ────────────────────────────────────────────────

def build_solvent_table_js(choice) -> str:
    """Emit the phase data and constants the viewer recomputes bands from.

    The pressure, albedo and greenhouse sliders rebuild every band in the
    browser, so the browser needs what `mechanics.solvent_bands` needs: each solvent's
    transcribed melting and boiling points against pressure, its functional
    ceiling, and the handful of constants the equation uses.  It is a few
    hundred bytes, and it is what makes a slider feel like a slider rather
    than a page reload.

    The star itself is not here -- each band trace carries its own luminosity
    and plane in `meta`, so a system swap needs no bookkeeping at all.
    """
    from ..mechanics import solvent_bands as sb

    table = {
        solvent.key: {
            "name": solvent.name,
            "formula": solvent.formula,
            # [bar, melting C, boiling C], ascending in pressure.
            "points": [[p, mc, bc] for p, (mc, bc)
                       in sorted(solvent.phase_points.items())],
            "ceiling_c": solvent.functional_ceiling_c,
        }
        for solvent in sb.SOLVENTS.values()
    }
    const = {
        "t_eq": T_EQ_1AU_K,
        "c2k": sb.CELSIUS_TO_KELVIN,
        "min_span": sb._MIN_SPAN_RATIO,
        "stack": sb._STACK_FRACTION,
        "stack_cap": sb._STACK_SPAN_CAP,
        "t_cmb": sb.T_CMB_K,
        "p_min": sb.MIN_PRESSURE_BAR,
        "p_max": sb.MAX_PRESSURE_BAR,
        "a_min": sb.MIN_ALBEDO,
        "a_max": sb.MAX_ALBEDO,
        "g_min": sb.MIN_GREENHOUSE_K,
        "g_max": sb.MAX_GREENHOUSE_K,
        "p0": choice.pressure_bar,
        "a0": choice.albedo,
        "g0": choice.greenhouse_k,
        "ring_pts": BAND_RING_POINTS,
    }
    compact = {"separators": (",", ":")}
    return "\n".join([
        f"window._SA_SOLVENTS = {json.dumps(table, **compact)};",
        f"window._SA_BAND_CONST = {json.dumps(const, **compact)};",
    ])


# ── Scene-range JS builders ─────────────────────────────────────────────────

def _fig_view_normal(fig: go.Figure) -> list:
    """The band plane this figure's camera was built against.

    Taken from the `up` vector `make_scene_style` baked in, rather than
    recomputed from the system: the figure is the thing the viewer is looking
    at, and reading it back is what stops the Orient button and the bands
    disagreeing about which plane they are in.
    """
    try:
        up = fig.layout.scene.camera.up
        vec = [float(up.x), float(up.y), float(up.z)]
        if any(c != 0.0 for c in vec):
            return vec
    except Exception:
        pass
    return [0.0, 0.0, 1.0]


def _build_scene_ranges_js(fig: go.Figure) -> str:
    """Return a JS snippet setting window._SA_SCENE_RANGES from fig's axis ranges.

    Reads the explicit ranges set by make_scene_style() so the JS coordinate
    converter always uses the Python-computed, origin-symmetric values.
    """
    try:
        xr = list(fig.layout.scene.xaxis.range)
        yr = list(fig.layout.scene.yaxis.range)
        zr = list(fig.layout.scene.zaxis.range)
        if len(xr) < 2 or len(yr) < 2 or len(zr) < 2:
            return ""
    except Exception:
        return ""
    ranges = {"xr": xr, "yr": yr, "zr": zr}
    return (f"window._SA_SCENE_RANGES = "
            f"{json.dumps(ranges, separators=(',', ':'))};\n"
            f"window._SA_VIEW_NORMAL = {json.dumps(_fig_view_normal(fig))};")


def _build_multi_scene_ranges_js(figures_by_name: dict, initial_system: str) -> str:
    """Return a JS snippet setting window._SA_ALL_RANGES and window._SA_SCENE_RANGES.

    window._SA_ALL_RANGES holds per-system ranges so the system switcher can
    update window._SA_SCENE_RANGES when the user changes systems.
    """
    all_ranges: dict = {}
    all_normals: dict = {}
    for name, fig in figures_by_name.items():
        try:
            xr = list(fig.layout.scene.xaxis.range)
            yr = list(fig.layout.scene.yaxis.range)
            zr = list(fig.layout.scene.zaxis.range)
            if len(xr) >= 2 and len(yr) >= 2 and len(zr) >= 2:
                all_ranges[name] = {"xr": xr, "yr": yr, "zr": zr}
                all_normals[name] = _fig_view_normal(fig)
        except Exception:
            pass
    if not all_ranges:
        return ""
    initial_js = json.dumps(initial_system)
    return (
        f"window._SA_ALL_RANGES = {json.dumps(all_ranges, separators=(',', ':'))};\n"
        f"window._SA_ALL_VIEW_NORMALS = "
        f"{json.dumps(all_normals, separators=(',', ':'))};\n"
        f"window._SA_SCENE_RANGES = window._SA_ALL_RANGES[{initial_js}];\n"
        f"window._SA_VIEW_NORMAL = window._SA_ALL_VIEW_NORMALS[{initial_js}];"
    )


# ── Internal HTML writers ───────────────────────────────────────────────────

def _write_html(fig: go.Figure, path: str, cdn: bool = True,
                extra_js: str = "") -> None:
    ranges_js  = _build_scene_ranges_js(fig)
    combined   = (
        (extra_js   + "\n" if extra_js   else "")
        + (ranges_js + "\n" if ranges_js else "")
        + _ZOOM_JS
    )
    include_js = "cdn" if cdn else True
    # auto_play=False: the figure opens on frame 0 and waits for the user to
    # press Play. Plotly's default emits an animate() call on load, which
    # starts the system moving before the viewer has oriented themselves.
    fig.write_html(path, include_plotlyjs=include_js, post_script=combined,
                   auto_play=False)


def _write_multi_html(
    figures_by_name: dict,
    initial_system: str,
    path: str,
    cdn: bool = True,
    extra_js: str = "",
) -> None:
    """Write a multi-system HTML file with a system-switcher button row."""
    ranges_js   = _build_multi_scene_ranges_js(figures_by_name, initial_system)
    switcher_js = _build_switcher_js(figures_by_name, initial_system)
    combined    = (
        (extra_js   + "\n" if extra_js   else "")
        + (ranges_js + "\n" if ranges_js else "")
        + switcher_js + "\n"
        + _ZOOM_JS
    )
    include_js  = "cdn" if cdn else True
    figures_by_name[initial_system].write_html(
        path, include_plotlyjs=include_js, post_script=combined,
        auto_play=False,
    )


# ── Public API ─────────────────────────────────────────────────────────────

def _open_in_browser(path: str) -> None:
    """Hand a local HTML file to the default browser.

    `pathlib.as_uri()` rather than an f-string: on Windows the naive form keeps
    the path separators a URL cannot use and gives a local path one slash too
    few after the scheme.  Nothing opens and nothing is raised, which is
    exactly as confusing as it sounds.

    `webbrowser.open` still returns False when it cannot find a browser at all,
    so fall back to letting the shell open the file by its plain path.
    """
    if webbrowser.open(pathlib.Path(path).as_uri()):
        return
    opener = getattr(os, "startfile", None)
    if opener is not None:
        opener(path)
    else:
        print(f"Could not open a browser. The figure is at: {path}")


def show_in_browser(fig: go.Figure, extra_js: str = "") -> None:
    """Open the figure in the default web browser with double-click-to-zoom enabled."""
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    tmp.close()
    _write_html(fig, tmp.name, cdn=True, extra_js=extra_js)
    _open_in_browser(tmp.name)


def show_in_browser_multi(figures_by_name: dict, initial_system: str,
                          extra_js: str = "") -> None:
    """Open a multi-system figure in the browser with a system-switcher UI.

    Args:
        figures_by_name: Ordered mapping of system key → go.Figure.
        initial_system:  Key of the system to display on first load.
        extra_js:        Optional JS snippet prepended before the switcher and
                         zoom scripts (e.g. the body-info constant).
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    tmp.close()
    _write_multi_html(figures_by_name, initial_system, tmp.name,
                      cdn=True, extra_js=extra_js)
    _open_in_browser(tmp.name)


def save_html(fig: go.Figure, path: str, cdn: bool = True,
              extra_js: str = "") -> None:
    """Save as an HTML file with double-click-to-zoom enabled.

    Args:
        path:     Output file path (e.g. "output/solar.html").
        cdn:      If True, links to Plotly CDN (smaller file). If False, embeds full JS.
        extra_js: Optional JS snippet prepended before the zoom script.
    """
    _write_html(fig, path, cdn=cdn, extra_js=extra_js)
    print(f"Saved HTML to {path}")


def save_png(fig: go.Figure, path: str, width: int = 1920, height: int = 1080) -> None:
    """Save a static PNG image. Requires the kaleido package.

    Solvent bands are switched back on first.  They are built hidden because
    the viewer opens on the orbits alone and its Bands button brings them in,
    and a still image has no such button: leaving them off would silently drop
    the band from every PNG a `--solvent` run asks for.

    Install with: pip install kaleido
    """
    for trace in fig.data:
        if is_band_trace(trace):
            trace.visible = True
    try:
        fig.write_image(path, width=width, height=height)
        print(f"Saved PNG to {path}")
    except Exception as e:
        if "kaleido" in str(e).lower() or "orca" in str(e).lower():
            raise ImportError(
                "kaleido is required for PNG export.\n"
                "Install it with: pip install kaleido"
            ) from e
        raise
