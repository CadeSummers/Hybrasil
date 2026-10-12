# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Zooming out of any body must end on the whole system, framed on its centre.

Zooming out of 55 Cnc B left a 1,000 AU box parked on B with A's half of the
system cut off at its edge.  The lock that restores the full scene was judged
on the *sticky* box: targetHalf is capped at the full-system half-width, so
once the sticky box passed half of that the ratio sat inside the (0.5, 2) band,
the box stopped growing short of the 0.95 threshold, and the lock never fired.

These run the viewer's own `_applyWheelZoom` under node, with Plotly stubbed to
record the layout it is handed, and zoom out of every body in every built-in
system -- a range from TRAPPIST-1's 0.07 AU to the Solar System's 1,170 AU,
flat and inclined, one star or three.
"""

import json
import shutil
import subprocess

import pytest

from hybrasil.cli import _NATURAL_SPANS
from hybrasil.data.builtin_systems import BUILTIN_NAMES, get_builtin_system
from hybrasil.mechanics.time_series import (
    system_orbit_paths,
    system_positions_at,
)
from hybrasil.mechanics.units import J2000
from hybrasil.viz.export import build_body_info_js
from hybrasil.viz.static_plot import build_static_figure
from tests.test_band_sliders import _extract_js_function

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

# Plotly's own default eye, |(1.25, 1.25, 1.25)| in normalised units: the
# distance at which the figure opens showing the whole system.
FULL_VIEW_EYE = 2.1650635

_HARNESS = r"""
var _sa_ranges = null, _sa_ranges_orig = null, _sceneHalfAU = null,
    _sceneOrigHalfAU = null, _sceneStack = [], _rescaleLock = false;
var _zoomMode = 'center', _mousePos = {x: 0.5, y: 0.5};
var _wheelAccum = 0, _wheelBusy = false;
var now = {then: function (f) { f(); }};
var gd = {data: MARKERS, layout: {scene: {camera: null}}};
function apply(g, l) {
  if (l['scene.camera']) g.layout.scene.camera = l['scene.camera'];
  return now;
}
var Plotly = {relayout: apply,
              update: function (g, d, l) { return apply(g, l); },
              restyle: function () { return now; }};
function updateSceneVisibility(g, xr, yr, zr, layout) {
  return layout ? Plotly.relayout(g, layout) : now;
}
function _scheduleWheel() {}
FUNCTIONS

function run(body) {
  // Start where a double-click on the body leaves the scene: rescaleScene's
  // box around it, zoomTo's camera.
  _sa_ranges = null; _sa_ranges_orig = null; _sceneStack = [];
  captureRanges(gd);
  var o = _sa_ranges_orig, oh = _sceneOrigHalfAU;
  var info = window._SA_BODY_INFO[body.name] || {};
  var h = info.zoom_half_au ||
          Math.max(Math.sqrt(body.x*body.x + body.y*body.y + body.z*body.z) * 0.01, 0.001);
  _sa_ranges = {xr: [body.x - h, body.x + h], yr: [body.y - h, body.y + h],
                zr: [body.z - h, body.z + h]};
  _sceneHalfAU = h;
  var n = Math.sqrt(body.x*body.x + body.y*body.y + body.z*body.z) || 1;
  var dx = body.x / n, dy = body.y / n, dz = body.z / n + 0.5;
  var dl = Math.sqrt(dx*dx + dy*dy + dz*dz) || 1;
  gd.layout.scene.camera = {center: {x: 0, y: 0, z: 0},
                            eye: {x: dx/dl*0.4, y: dy/dl*0.4, z: dz/dl*0.4},
                            up: {x: 0, y: 0, z: 1}};

  var tol = oh * 1e-9, outside = 0, minEye = Infinity, stepsToFull = -1;
  var targetAtFullView = null;
  for (var s = 0; s < 400; s++) {
    _applyWheelZoom(gd, 1.0);
    var r = _sa_ranges, half = (r.xr[1] - r.xr[0]) / 2;
    if (r.xr[0] < o.xr[0] - tol || r.xr[1] > o.xr[1] + tol ||
        r.yr[0] < o.yr[0] - tol || r.yr[1] > o.yr[1] + tol ||
        r.zr[0] < o.zr[0] - tol || r.zr[1] > o.zr[1] + tol) outside++;
    var c = gd.layout.scene.camera;
    var ex = c.eye.x - c.center.x, ey = c.eye.y - c.center.y, ez = c.eye.z - c.center.z;
    var eyeNorm = Math.sqrt(ex*ex + ey*ey + ez*ez);
    minEye = Math.min(minEye, eyeNorm);
    var full = Math.abs(half - oh) <= tol && Math.abs(r.xr[0] + oh) <= tol;
    if (full && stepsToFull < 0) stepsToFull = s + 1;
    if (full && eyeNorm >= FULL_VIEW_EYE) {
      // Camera target in AU: the box is the full one, centred on the origin.
      var tx = c.center.x * oh, ty = c.center.y * oh, tz = c.center.z * oh;
      targetAtFullView = Math.sqrt(tx*tx + ty*ty + tz*tz) / oh;
      break;
    }
  }
  return {name: body.name, stepsToFull: stepsToFull, outside: outside,
          minEye: minEye, targetAtFullView: targetAtFullView};
}
var out = [];
for (var b = 0; b < MARKERS.length; b++) {
  var m = MARKERS[b];
  out.push(run({name: m.name, x: m.x[0], y: m.y[0], z: m.z[0]}));
}
console.log(JSON.stringify(out));
"""

_FUNCTIONS = ("captureRanges", "_findNearestBody", "_clampInsideOrig",
              "_applyWheelZoom")


def _system_scene(key):
    """What the browser holds for one system: its body markers and its box."""
    system = get_builtin_system(key)
    t0 = J2000
    t1 = t0 + _NATURAL_SPANS.get(key, 365.25)
    orbit_paths, coil_paths = system_orbit_paths(system, t_start=t0, t_end=t1)
    fig = build_static_figure(system=system,
                              positions=system_positions_at(system, t0),
                              orbit_paths=orbit_paths, coil_paths=coil_paths,
                              coil_span_days=t1 - t0)
    markers = [{"name": t.name, "mode": t.mode,
                "x": [float(t.x[0])], "y": [float(t.y[0])], "z": [float(t.z[0])]}
               for t in fig.data
               if t.type == "scatter3d" and t.mode and "markers" in t.mode
               and t.x is not None and len(t.x) == 1]
    ranges = {"xr": list(fig.layout.scene.xaxis.range),
              "yr": list(fig.layout.scene.yaxis.range),
              "zr": list(fig.layout.scene.zaxis.range)}
    return system, markers, ranges


def _run(key, mutate=None):
    system, markers, ranges = _system_scene(key)
    functions = "\n".join(_extract_js_function(f) for f in _FUNCTIONS)
    if mutate:
        functions = mutate(functions)
    script = "\n".join([
        "var window = {};",
        build_body_info_js({key: system}),
        "window._SA_SCENE_RANGES = %s;" % json.dumps(ranges),
        "var MARKERS = %s;" % json.dumps(markers),
        "var FULL_VIEW_EYE = %r;" % FULL_VIEW_EYE,
        _HARNESS.replace("FUNCTIONS", functions),
    ])
    proc = subprocess.run(["node", "-e", script], capture_output=True,
                          text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.fixture(scope="module", params=BUILTIN_NAMES)
def results(request):
    return request.param, _run(request.param)


class TestZoomingOutOfEveryBody:
    def test_it_ends_on_the_whole_system(self, results):
        key, rows = results
        stuck = [r["name"] for r in rows if r["stepsToFull"] < 0]
        assert not stuck, f"{key}: zooming out never restored the full box: {stuck}"

    def test_the_box_never_leaves_the_system(self, results):
        key, rows = results
        bad = [(r["name"], r["outside"]) for r in rows if r["outside"]]
        assert not bad, f"{key}: box reached outside the full-system box: {bad}"

    def test_the_whole_view_is_framed_on_the_centre(self, results):
        # By the time the camera is as far out as the figure opens, the target
        # has come home: within 10% of the system's half-width of the centre.
        key, rows = results
        off = [(r["name"], round(r["targetAtFullView"], 3)) for r in rows
               if r["targetAtFullView"] is None or r["targetAtFullView"] > 0.10]
        assert not off, f"{key}: full view still framed off-centre: {off}"

    def test_the_box_still_follows_the_camera(self, results):
        # MIN_EYE_NORM: the near-plane rule from test_scroll_zoom.py.
        key, rows = results
        low = [(r["name"], r["minEye"]) for r in rows if r["minEye"] < 0.08 - 1e-9]
        assert not low, f"{key}: camera closer than 0.08 of the box: {low}"


class TestTheHazardIsReal:
    """Without the lock judged on the wanted box, 55 Cnc B really does stick."""

    def test_the_sticky_lock_alone_strands_55_cnc_b(self):
        rows = _run("55-cancri", mutate=lambda js: js.replace(
            " || newDistAU * 6 >= origHalf * 0.95", ""))
        b = next(r for r in rows if r["name"].startswith("55 Cancri B"))
        assert b["stepsToFull"] < 0

    def test_with_it_55_cnc_b_comes_back(self):
        rows = _run("55-cancri")
        b = next(r for r in rows if r["name"].startswith("55 Cancri B"))
        assert b["stepsToFull"] > 0
