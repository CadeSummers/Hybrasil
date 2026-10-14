# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The viewer, driven in a real browser: what Python-side tests cannot see.

The rest of the suite checks the figure Python builds and runs pieces of the
viewer's JavaScript under node.  Neither can see what WebGL is handed after a
system switch, a wheel gesture or a slider drag -- and the one real failure of
the flat-disc rule so far was invisible to Python entirely: Alpha Centauri's
bands were retyped from mesh3d to scatter3d by a stale frame and drawn as tori
of beads, with the geometry exactly planar the whole time.

So this opens the multi-system page in headless Chromium (software WebGL, so it
needs no GPU and no visible window) and, for every built-in system:

* zooms out of its outermost body with real wheel events and checks the scene
  ends on the whole system -- the 55 Cnc B cutoff;
* switches the bands on from the Bands button and from a band's own legend
  entry, moves the pressure slider, and checks every band is still a planar
  mesh3d after arriving from another system.

Needs `pip install pytest-playwright` and `python -m playwright install
chromium`; skipped otherwise.  `pytest tests/test_browser.py --headed` shows
the browser while it runs.
"""

import math
import shutil

import pytest

pytest.importorskip("playwright")
pytest.importorskip("pytest_playwright")

# About two minutes for the lot; `pytest -m "not browser"` leaves them out.
pytestmark = pytest.mark.browser

from hybrasil import cli  # noqa: E402
from hybrasil.data.builtin_systems import BUILTIN_NAMES  # noqa: E402
from hybrasil.views import FEATURED_VIEWS  # noqa: E402
from hybrasil.viz import export  # noqa: E402

# Wheel events before a zoom-out from the outermost body must have restored
# the full scene.  55 Cnc B, the worst case, takes about 56.
MAX_WHEEL_EVENTS = 250
# A frame this long is a stall, not software rendering being slow: SwiftShader
# measured a 97 ms worst frame on the whole 55 Cnc B zoom-out.
STALL_MS = 1500


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # Software WebGL, so the suite runs on a machine with no GPU and no window.
    args = list(browser_type_launch_args.get("args", []))
    args += ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
    return {**browser_type_launch_args, "args": args}


@pytest.fixture(scope="session")
def viewer_url(tmp_path_factory):
    """The multi-system page exactly as `python -m hybrasil.cli` writes it."""
    out = tmp_path_factory.mktemp("viewer") / "viewer.html"
    real_open = export._open_in_browser
    export._open_in_browser = lambda p: shutil.copy(p, out)
    try:
        cli.main(["--system", "solar", "--renderer", "plotly"])
    finally:
        export._open_in_browser = real_open
    return out.as_uri()


# Page-side helpers.  Coordinates can arrive base64-encoded (Plotly 3.x), so
# everything reads them through decode().
_HELPERS = r"""
window.__t = {
  gd() { return [...document.querySelectorAll('.js-plotly-plot')].pop(); },
  decode(v) {
    if (!v) return [];
    if (v.bdata) {
      const C = {f8: Float64Array, f4: Float32Array, i4: Int32Array, i2: Int16Array,
                 u4: Uint32Array, u2: Uint16Array, i1: Int8Array, u1: Uint8Array};
      const bin = atob(v.bdata), buf = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
      return Array.from(new C[v.dtype](buf.buffer));
    }
    return Array.from(v);
  },
  async switchTo(key) {
    window._saSwitch(key);
    await new Promise(r => setTimeout(r, 1500));
  },
  bands() {
    const gd = this.gd();
    return gd.data.map((t, i) => ({t, i}))
      .filter(o => o.t.meta && o.t.meta.solvent !== undefined || /band/i.test(o.t.name || ''));
  },
  // Largest deviation of a trace's vertices from the plane through three of
  // them, relative to the trace's own size.
  planarity(t) {
    const X = this.decode(t.x), Y = this.decode(t.y), Z = this.decode(t.z);
    const n = X.length; if (n < 3) return {n, dev: 0};
    const p = i => [X[i], Y[i], Z[i]];
    const sub = (a, b) => [a[0]-b[0], a[1]-b[1], a[2]-b[2]];
    const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
    const len = a => Math.hypot(a[0], a[1], a[2]);
    const p0 = p(0); let far = 1, fd = 0;
    for (let i = 1; i < n; i++) { const d = len(sub(p(i), p0)); if (d > fd) { fd = d; far = i; } }
    let best = null, bl = 0;
    for (let i = 1; i < n; i++) {
      const c = cross(sub(p(far), p0), sub(p(i), p0)); const l = len(c);
      if (l > bl) { bl = l; best = c; }
    }
    const nrm = best.map(v => v / bl); let dev = 0;
    for (let i = 0; i < n; i++) {
      const d = sub(p(i), p0); dev = Math.max(dev, Math.abs(d[0]*nrm[0]+d[1]*nrm[1]+d[2]*nrm[2]));
    }
    return {n, dev: dev / (fd || 1)};
  },
  bandReport() {
    return this.bands().map(({t, i}) => ({
      i, name: t.name, type: t.type, visible: t.visible, ...this.planarity(t)}));
  },
  outermostBody() {
    let best = null, bd = -1;
    for (const t of this.gd().data) {
      if (!t.mode || !t.mode.includes('markers') || !t.x || t.x.length !== 1) continue;
      const d = Math.hypot(+t.x[0], +t.y[0], +t.z[0]);
      if (d > bd) { bd = d; best = t.name; }
    }
    return best;
  },
  async search(q) {
    const inp = [...document.querySelectorAll('input')]
      .find(i => /search/i.test(i.placeholder || ''));
    inp.value = q;
    inp.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
    await new Promise(r => setTimeout(r, 900));
  },
  isFull() {
    const s = this.gd().layout.scene, o = window._SA_SCENE_RANGES_ORIG;
    const tol = (o.xr[1] - o.xr[0]) * 1e-9;
    return ['x', 'y', 'z'].every(a => {
      const r = s[a + 'axis'].range, w = o[a + 'r'];
      return Math.abs(r[0] - w[0]) <= tol && Math.abs(r[1] - w[1]) <= tol;
    });
  },
  async zoomOut(maxEvents) {
    const gd = this.gd(), r = gd.getBoundingClientRect();
    const frames = []; let last = performance.now(), run = true;
    const tick = () => { const t = performance.now(); frames.push(t - last); last = t;
                         if (run) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    let n = 0;
    while (n < maxEvents && !this.isFull()) {
      gd.dispatchEvent(new WheelEvent('wheel', {deltaY: 100, bubbles: true, cancelable: true,
        clientX: r.left + r.width / 2, clientY: r.top + r.height / 2}));
      n++;
      await new Promise(res => setTimeout(res, 60));
    }
    await new Promise(res => setTimeout(res, 500));   // let the easing finish
    // A starved page (a hosted runner's software WebGL) may not have drawn
    // twice yet: wait, bounded, for frames to time, and count the one still
    // open, so a real stall reports as a long frame rather than as nothing.
    for (let i = 0; i < 50 && frames.length < 3; i++) await new Promise(res => setTimeout(res, 100));
    run = false;
    frames.push(performance.now() - last);
    const f = frames.slice(1).sort((a, b) => a - b);
    return {events: n, full: this.isFull(), p50: f[Math.floor(f.length / 2)],
            p95: f[Math.floor(f.length * 0.95)], max: f[f.length - 1]};
  },
};
"""


@pytest.fixture
def viewer(page, viewer_url):
    return _load_plotly(page, viewer_url)


def _load_plotly(page, url):
    page.set_viewport_size({"width": 1400, "height": 850})
    page.goto(url)
    page.wait_for_function("!!(document.querySelector('.js-plotly-plot')"
                           " && window._saSwitch)", timeout=60_000)
    page.evaluate(_HELPERS)
    return page


def _open(page, key):
    page.evaluate("k => window.__t.switchTo(k)", key)
    # The original full-system box, before any zoom: what Orient restores.
    page.evaluate("() => { const r = window._SA_SCENE_RANGES;"
                  " window._SA_SCENE_RANGES_ORIG = {xr: r.xr.slice(),"
                  " yr: r.yr.slice(), zr: r.zr.slice()}; }")


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_zooming_out_of_the_outermost_body_restores_the_system(viewer, key):
    _open(viewer, key)
    body = viewer.evaluate("() => window.__t.outermostBody()")
    viewer.evaluate("q => window.__t.search(q)", body)
    assert not viewer.evaluate("() => window.__t.isFull()"), (
        f"searching for {body} did not zoom in, so this proves nothing")
    result = viewer.evaluate("n => window.__t.zoomOut(n)", MAX_WHEEL_EVENTS)
    # Software rendering, so only a stall fails; `pytest -s` shows the timings.
    print(f"\n{key}: out of {body} in {result['events']} wheel events, frames "
          f"p50 {result['p50']:.0f} ms, p95 {result['p95']:.0f} ms, "
          f"max {result['max']:.0f} ms")
    assert result["full"], f"{key}: zooming out of {body} never restored the " \
                           f"full scene ({result})"
    assert result["max"] < STALL_MS, f"{key}: a {result['max']:.0f} ms frame"


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_every_band_is_a_flat_disc_after_a_switch(viewer, key):
    # Arrive from a different system, which is what retyped Alpha Centauri's
    # bands; the Solar System has the most traces to collide with.
    _plotly_band_clickthrough(viewer, key,
                              "alpha-centauri" if key == "solar" else "solar")


def _plotly_band_clickthrough(viewer, key, arrive_from):
    """Bands button, pressure slider, a band's own legend entry: all flat."""
    _open(viewer, arrive_from)
    _open(viewer, key)

    # From the Bands button.
    viewer.get_by_text("Bands:", exact=False).first.click()
    viewer.wait_for_timeout(600)
    _assert_flat(viewer, key, "Bands button", expect_all_visible=True)

    # Through the pressure slider, which rebuilds every band in the browser.
    viewer.evaluate("""() => {
      const s = document.querySelectorAll('input[type=range]')[0];
      s.value = s.max * 0.75;
      s.dispatchEvent(new Event('input', {bubbles: true}));
      s.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    viewer.wait_for_timeout(900)
    _assert_flat(viewer, key, "pressure slider", expect_all_visible=True)

    # Off again, then one band from its own legend entry.
    viewer.get_by_text("Bands:", exact=False).first.click()
    viewer.wait_for_timeout(600)
    # A band with no liquid phase at this pressure has no ring and stays
    # hidden by design (methane at 17.8 bar with a 33 K greenhouse), so pick
    # one that has a ring to show.
    name = viewer.evaluate("() => window.__t.bands()"
                           ".find(o => window.__t.decode(o.t.x).length).t.name")
    # Plotly lays a transparent rect over each legend row to catch the click.
    viewer.locator("g.legend g.traces", has_text=name).first \
          .locator("rect.legendtoggle").click()
    viewer.wait_for_timeout(600)
    report = _assert_flat(viewer, key, "legend entry")
    shown = [r["name"] for r in report if r["visible"] is True]
    assert name in shown, f"{key}: clicking {name!r} in the legend did not show it"


def _assert_flat(page, key, via, expect_all_visible=False):
    report = page.evaluate("() => window.__t.bandReport()")
    assert report, f"{key}: no solvent bands in the figure"
    wrong = [(r["name"], r["type"]) for r in report if r["type"] != "mesh3d"]
    assert not wrong, f"{key} via {via}: bands no longer mesh3d: {wrong}"
    bent = [(r["name"], r["dev"]) for r in report if r["dev"] > 1e-9]
    assert not bent, f"{key} via {via}: bands not planar: {bent}"
    if expect_all_visible:
        hidden = [r["name"] for r in report if r["visible"] is not True]
        # The box may clip a band it cannot show, never one it can.
        assert len(hidden) < len(report), f"{key} via {via}: no band visible"
    return report


# ── The three.js renderer (--renderer three) ─────────────────────────────────

@pytest.fixture(scope="session")
def three_url(tmp_path_factory):
    """The multi-system page as `--renderer three` writes it."""
    from hybrasil.viz import three_viewer

    out = tmp_path_factory.mktemp("three") / "three.html"
    real_open = three_viewer._open_in_browser
    three_viewer._open_in_browser = lambda p: shutil.copy(p, out)
    try:
        cli.main(["--system", "solar"])          # three.js is the default
    finally:
        three_viewer._open_in_browser = real_open
    return out.as_uri()


_THREE_HELPERS = r"""
window.__t3 = {
  // Largest deviation of a band's vertices from their best plane, relative to
  // the band's size -- on the geometry actually uploaded to the GPU.
  planarity(mesh) {
    // A band with no liquid phase at this pressure has an empty geometry.
    const pos = mesh.geometry.attributes.position;
    if (!pos) return 0;
    const a = pos.array, n = a.length / 3;
    const p = i => [a[3*i], a[3*i+1], a[3*i+2]];
    const sub = (u, v) => [u[0]-v[0], u[1]-v[1], u[2]-v[2]];
    const cross = (u, v) => [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]];
    const len = u => Math.hypot(u[0], u[1], u[2]);
    const p0 = p(0); let far = 1, fd = 0;
    for (let i = 1; i < n; i++) { const d = len(sub(p(i), p0)); if (d > fd) { fd = d; far = i; } }
    let best = null, bl = 0;
    for (let i = 1; i < n; i++) {
      const c = cross(sub(p(far), p0), sub(p(i), p0)), l = len(c);
      if (l > bl) { bl = l; best = c; }
    }
    const nrm = best.map(v => v / bl); let dev = 0;
    for (let i = 0; i < n; i++) {
      const d = sub(p(i), p0); dev = Math.max(dev, Math.abs(d[0]*nrm[0]+d[1]*nrm[1]+d[2]*nrm[2]));
    }
    return dev / (fd || 1);
  },
  report() {
    return window.__SA3.bands().map(m => ({
      name: m.userData.name, solvent: m.userData.solvent, visible: m.visible,
      hasRing: !!m.userData.hasRing,
      isMesh: !!m.isMesh, isPoints: !!m.isPoints, isLine: !!m.isLine,
      triangles: m.geometry.index ? m.geometry.index.count / 3 : 0,
      dev: this.planarity(m)}));
  },
  // Fraction of bodies whose position projects inside the viewport.
  inView() {
    const S = window.__SA3, out = [];
    for (const b of S.bodies()) {
      // In front of the camera (view space; projected depth is ~1 for
      // everything at this near/far ratio) and inside the viewport.
      const w = b.obj.position.clone().applyMatrix4(S.camera.matrixWorldInverse);
      const v = b.obj.position.clone().project(S.camera);
      if (!(w.z < 0 && Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1)) out.push(b.data.name);
    }
    return out;
  },
  async zoomOut(maxEvents) {
    const el = window.__SA3.renderer.domElement, r = el.getBoundingClientRect();
    const frames = []; let last = performance.now(), run = true;
    const tick = () => { const t = performance.now(); frames.push(t - last); last = t;
                         if (run) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    let n = 0;
    while (n < maxEvents && this.inView().length) {
      el.dispatchEvent(new WheelEvent('wheel', {deltaY: 100, bubbles: true, cancelable: true,
        clientX: r.left + r.width / 2, clientY: r.top + r.height / 2}));
      n++;
      await new Promise(res => setTimeout(res, 60));
    }
    await new Promise(res => setTimeout(res, 800));   // let the damping settle
    // A starved page (a hosted runner's software WebGL) may not have drawn
    // twice yet: wait, bounded, for frames to time, and count the one still
    // open, so a real stall reports as a long frame rather than as nothing.
    for (let i = 0; i < 50 && frames.length < 3; i++) await new Promise(res => setTimeout(res, 100));
    run = false;
    frames.push(performance.now() - last);
    const f = frames.slice(1).sort((a, b) => a - b);
    return {events: n, outside: this.inView(), p50: f[Math.floor(f.length / 2)],
            p95: f[Math.floor(f.length * 0.95)], max: f[f.length - 1]};
  },
};
"""


@pytest.fixture
def three(page, three_url):
    yield from _load_three(page, three_url)


def _load_three(page, url):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_viewport_size({"width": 1400, "height": 850})
    page.goto(url)
    page.wait_for_function("!!(window.__SA3 && window.__SA3.ready)", timeout=60_000)
    page.evaluate(_THREE_HELPERS)
    yield page
    assert not errors, f"page errors: {errors}"


def test_three_between_frames_a_planet_stays_on_its_orbit(three):
    # Proxima d goes round about four times in one 19-day frame step. The viewer
    # used to slide it along the chord between two frames, through the inside
    # of its ring; it now solves Kepler's equation at the moment shown
    # (tests/test_kepler_js.py checks the solver; this checks setFrame uses it).
    three.evaluate("k => window.__SA3.switchTo(k)", "proxima-centauri")
    worst = three.evaluate("""() => {
      const S = window.__SA3, out = {};
      for (const name of ['Proxima Centauri b', 'Proxima Centauri d']) {
        const B = S.bodies().find(b => b.data.name === name);
        const L = S.lines().find(o => o.userData.name === name + ' orbit');
        const a = L.geometry.attributes.position.array, q = L.position;
        let worst = 0, size = 0;
        for (let k = 0; k < a.length; k += 3) size = Math.max(size, Math.hypot(a[k], a[k + 1], a[k + 2]));
        for (let f = 0; f < S.nFrames() - 1; f += 2) {
          S.setFrame(f + 0.5);
          const p = B.obj.position;
          let best = Infinity;
          for (let k = 0; k + 6 <= a.length; k += 3) {
            const ax = a[k] + q.x, ay = a[k + 1] + q.y, az = a[k + 2] + q.z;
            const ux = a[k + 3] - a[k], uy = a[k + 4] - a[k + 1], uz = a[k + 5] - a[k + 2];
            const s = Math.max(0, Math.min(1, ((p.x - ax) * ux + (p.y - ay) * uy + (p.z - az) * uz)
                                             / (ux * ux + uy * uy + uz * uz)));
            best = Math.min(best, Math.hypot(ax + s * ux - p.x, ay + s * uy - p.y, az + s * uz - p.z));
          }
          worst = Math.max(worst, best / size);
        }
        out[name] = worst;
      }
      return out;
    }""")
    for name, w in worst.items():
        assert w < 1e-3, f"{name} is {w:.1%} of its orbit off its ring between frames"


def test_three_a_rotation_axis_rides_its_body(three):
    # The axis is drawn through the body where it is at frame 0; Plotly's frames
    # redraw it, but the three.js viewer read only the markers from them, so
    # the axis stayed behind as the planet orbited (9 Oct 2026). Its midpoint
    # must be the body's position at every moment, between frames included.
    three.evaluate("k => window.__SA3.switchTo(k)", "solar")
    worst = three.evaluate("""() => {
      const S = window.__SA3, out = {};
      for (const L of S.lines().filter(o => o.userData.name.endsWith(' axis'))) {
        const name = L.userData.name.slice(0, -5);
        const B = S.bodies().find(b => b.data.name === name);
        // A 2-px line is a Line2, whose segment ends live in instanceStart.
        const g = L.geometry.attributes, q = L.position;
        const a = (g.instanceStart ? g.instanceStart.data : g.position).array;
        let worst = 0;
        for (let f = 0; f < S.nFrames() - 1; f += 3) {
          S.setFrame(f + 0.37);
          const p = B.obj.position;
          const mx = (a[0] + a[3]) / 2 + q.x, my = (a[1] + a[4]) / 2 + q.y, mz = (a[2] + a[5]) / 2 + q.z;
          worst = Math.max(worst, Math.hypot(mx - p.x, my - p.y, mz - p.z) / Math.hypot(a[3] - a[0], a[4] - a[1], a[5] - a[2]));
        }
        out[name] = worst;
      }
      return out;
    }""")
    assert len(worst) >= 9, worst
    for name, w in worst.items():
        assert w < 1e-6, f"{name}'s axis is {w:.2%} of its own length off the body"


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_three_every_band_is_a_flat_disc(three, key):
    # Arrive from another system first, as the Plotly test does.
    _three_band_clickthrough(three, key,
                             "alpha-centauri" if key == "solar" else "solar")


def _three_band_clickthrough(three, key, arrive_from):
    """Bands button, then a band's own legend entry: every band a flat mesh."""
    three.evaluate("k => window.__SA3.switchTo(k)", arrive_from)
    three.evaluate("k => window.__SA3.switchTo(k)", key)

    # From the Bands button.
    three.get_by_text("Bands:", exact=False).first.click()
    three.wait_for_timeout(200)
    report = three.evaluate("() => window.__t3.report()")
    solvent = [r for r in report if r["solvent"]]
    assert solvent, f"{key}: no solvent bands"
    for r in report:
        assert r["isMesh"] and not r["isPoints"] and not r["isLine"], r
        # A band with no liquid phase at this pressure (carbon dioxide at
        # 1 bar) is an empty mesh, and must never be drawn.
        assert (r["triangles"] > 0) == r["hasRing"], r
        assert r["hasRing"] or not r["visible"], r
        assert r["dev"] < 1e-6, f"{key}: {r['name']} is not planar ({r['dev']:.2e})"
    assert all(r["visible"] for r in solvent if r["hasRing"]), (
        f"{key}: Bands button left some off")

    # Off, then one band from its own legend entry.
    three.get_by_text("Bands:", exact=False).first.click()
    first = next(r["name"] for r in solvent if r["hasRing"])
    three.locator("label", has_text=first).first.locator("input").check()
    three.wait_for_timeout(200)
    shown = [r["name"] for r in three.evaluate("() => window.__t3.report()")
             if r["solvent"] and r["visible"]]
    assert first in shown, f"{key}: the legend entry did not show {first!r}"


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_three_zooming_out_brings_the_whole_system_into_view(three, key):
    three.evaluate("k => window.__SA3.switchTo(k)", key)
    three.evaluate("""() => {
      const S = window.__SA3; let best = null, bd = -1;
      for (const b of S.bodies()) { const d = b.obj.position.length();
                                    if (d > bd) { bd = d; best = b; } }
      S.frameBody(best);
    }""")
    three.wait_for_function("() => !window.__SA3.flying()", timeout=10_000)  # the 700 ms flight
    # Then further in, until something is out of view: Proxima c's own
    # framing still holds the whole Proxima system.
    three.evaluate("""async () => {
      const el = window.__SA3.renderer.domElement, r = el.getBoundingClientRect();
      for (let i = 0; i < 40 && !window.__t3.inView().length; i++) {
        el.dispatchEvent(new WheelEvent('wheel', {deltaY: -100, bubbles: true,
          cancelable: true, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2}));
        await new Promise(res => setTimeout(res, 60));
      }
      await new Promise(res => setTimeout(res, 800));
    }""")
    assert three.evaluate("() => window.__t3.inView().length"), (
        f"{key}: framing the outermost body left everything in view, so this "
        "proves nothing")
    result = three.evaluate("n => window.__t3.zoomOut(n)", MAX_WHEEL_EVENTS)
    print(f"\n{key} (three.js): whole system in view after {result['events']} "
          f"wheel events, frames p50 {result['p50']:.0f} ms, "
          f"p95 {result['p95']:.0f} ms, max {result['max']:.0f} ms")
    assert not result["outside"], f"{key}: still out of view: {result['outside']}"
    assert result["max"] < STALL_MS, f"{key}: a {result['max']:.0f} ms frame"


_THREE_BAND_CHECK = r"""
(key) => {
  // Every solvent band's drawn vertices (local + mesh position, i.e. world)
  // against the ring Python built into the figure, band for band.
  const S = window.__SA3, want = window.SA3_SYSTEMS[key].bands, out = [];
  S.bands().forEach((m, k) => {
    if (!m.userData.solvent || !want[k].pos.length) return;
    const a = m.geometry.attributes.position.array, p = m.position, w = want[k].pos;
    let size = 0, err = 0;
    for (let i = 0; i < w.length; i += 3) {
      size = Math.max(size, Math.hypot(w[i] - p.x, w[i+1] - p.y, w[i+2] - p.z));
    }
    for (let i = 0; i < w.length; i++) {
      err = Math.max(err, Math.abs(a[i] + [p.x, p.y, p.z][i % 3] - w[i]));
    }
    out.push({name: m.userData.name, n: a.length, want: w.length, rel: err / (size || 1)});
  });
  return out;
}
"""


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_three_sliders_rebuild_the_bands_python_builds(three, key):
    three.evaluate("k => window.__SA3.switchTo(k)", key)
    # On load the viewer has already rebuilt every band through band_kit.js
    # at the panel's pressure -- the figure's own -- so it must have landed
    # on Python's ring, to float32.
    report = three.evaluate(_THREE_BAND_CHECK, key)
    assert report, f"{key}: no solvent band with a ring"
    for r in report:
        assert r["n"] == r["want"], r
        assert r["rel"] < 1e-6, f"{key}: {r['name']} differs from Python ({r['rel']:.1e})"

    # Type a pressure: every name follows, and every band is still a planar
    # mesh.  A band with no liquid phase is hidden but stays asked-for.
    three.get_by_text("Bands:", exact=False).first.click()
    box = three.get_by_label("Pressure")
    box.fill("17.8")
    box.press("Enter")
    three.wait_for_timeout(400)
    bands = three.evaluate("() => window.__t3.report()")
    for r in (b for b in bands if b["solvent"]):
        assert "17.8 bar" in r["name"], r["name"]
        assert r["isMesh"] and not r["isPoints"], r
        assert r["triangles"] == 0 or r["dev"] < 1e-6, r
    states = three.evaluate("""() => window.__SA3.bands().filter(m => m.userData.solvent)
        .map(m => ({on: m.userData.on, ring: m.userData.hasRing, visible: m.visible}))""")
    assert all(s["on"] for s in states)
    assert all(s["visible"] == s["ring"] for s in states)

    # Back to 1 bar: exactly the rings Python built.
    box.fill("1")
    box.press("Enter")
    three.wait_for_timeout(400)
    for r in three.evaluate(_THREE_BAND_CHECK, key):
        assert r["rel"] < 1e-6, f"{key}: {r['name']} did not come back ({r['rel']:.1e})"


def test_three_the_sliders_carry_across_a_system_switch(three):
    box = three.get_by_label("Pressure")
    box.fill("17.8")
    box.press("Enter")
    three.wait_for_timeout(300)
    three.evaluate("() => window.__SA3.switchTo('trappist-1')")
    names = three.evaluate("""() => window.__SA3.bands()
        .filter(m => m.userData.solvent).map(m => m.userData.name)""")
    assert names and all("17.8 bar" in n for n in names), names


def test_three_a_typed_value_past_the_end_clamps_and_says_so(three):
    box = three.get_by_label("Pressure")
    box.fill("500")
    box.press("Enter")
    three.wait_for_timeout(300)
    assert three.evaluate("() => window.__SA3.bandValues().P") == 100
    assert three.get_by_text("Range is", exact=False).first.is_visible()


def test_three_search_frames_a_body_and_opens_its_info_panel(three):
    three.evaluate("() => window.__SA3.switchTo('solar')")
    search = three.get_by_placeholder("Find in system…")
    search.fill("earth")
    search.press("Enter")
    # The flight is FLY_MS of animation frames, which a hosted CI runner's
    # software WebGL can stretch well past a fixed wait: poll for arrival.
    off_js = """() => { const S = window.__SA3;
        const e = S.bodies().find(b => b.data.name === 'Earth').obj.position;
        return S.controls.target.distanceTo(e); }"""
    try:
        three.wait_for_function(f"() => ({off_js})() < 1e-6", timeout=10_000)
    except Exception:
        pass  # the assertion below reports how far off it stopped
    off = three.evaluate(off_js)
    assert off < 1e-6, f"the camera is not on Earth ({off} AU off)"
    panel = three.locator("#_sa_info_panel")
    assert panel.is_visible() and "Earth" in panel.inner_text()


_MARKER_SIZES = """() => { const S = window.__SA3, ratio = S.renderer.getPixelRatio();
  return Object.fromEntries(S.bodies().map(b => [b.data.name,
    [b.obj.material.size / ratio, b.data.size]])); }"""


_FIRST_DRAWN = """f => { const S = window.__SA3, b = S.bodies()[0];
  return Math.abs(b.obj.material.size / S.renderer.getPixelRatio() - b.data.size * f) < 1e-6; }"""


def test_three_markers_are_smaller_on_a_phone(page, three_url):
    # Every body is drawn at 70% on a phone, and the change follows the
    # layout live: a phone turned, a window narrowed.  0.9 is the Plotly match.
    page.set_viewport_size({"width": 1400, "height": 850})
    page.goto(three_url)
    page.wait_for_function("!!(window.__SA3 && window.__SA3.ready)", timeout=60_000)
    wide = page.evaluate(_MARKER_SIZES)
    assert all(drawn == pytest.approx(size * 0.9) for drawn, size in wide.values())
    page.set_viewport_size({"width": 390, "height": 844})
    # The media query's change event lands on the next rendering step, after
    # matchMedia() already says so: wait for the markers, not the query.
    page.wait_for_function(_FIRST_DRAWN, arg=0.9 * 0.7, timeout=5_000)
    phone = page.evaluate(_MARKER_SIZES)
    assert all(drawn == pytest.approx(size * 0.9 * 0.7) for drawn, size in phone.values())
    assert phone["Sun"][0] == pytest.approx(wide["Sun"][0] * 0.7)
    # A system opened on the phone is built small, not just resized.
    page.evaluate("() => window.__SA3.switchTo('trappist-1')")
    built = page.evaluate(_MARKER_SIZES)
    assert all(drawn == pytest.approx(size * 0.9 * 0.7) for drawn, size in built.values())
    page.set_viewport_size({"width": 1400, "height": 850})
    page.wait_for_function(_FIRST_DRAWN, arg=0.9, timeout=5_000)
    back = page.evaluate(_MARKER_SIZES)
    assert all(drawn == pytest.approx(size * 0.9) for drawn, size in back.values())


def test_three_a_phone_folds_featured_bands_and_legend(page, three_url):
    # At iPhone size the featured buttons, band panel and legend are folded
    # dropdowns, closed until tapped (docs/architecture/three-renderer.md,
    # "On a phone").  Every other browser test runs wide, where none of this shows.
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(three_url)
    page.wait_for_function("!!(window.__SA3 && window.__SA3.ready)", timeout=60_000)
    page.evaluate(_THREE_HELPERS)
    trappist = page.get_by_role("button", name="TRAPPIST-1", exact=True)
    pressure = page.get_by_label("Pressure")
    a_row = page.locator("input[data-kind=body]").first
    assert not trappist.is_visible() and not pressure.is_visible() and not a_row.is_visible()

    # The toolbar is one row of icons plus a ⋯ menu holding the rest.
    about = page.get_by_role("button", name="About", exact=False)
    menu = page.get_by_role("button", name="More controls")
    assert not about.is_visible()
    bar = page.get_by_role("button", name="Orient").bounding_box()
    assert abs(menu.bounding_box()["y"] - bar["y"]) < 4, "the ⋯ button left the first row"
    menu.click()
    assert about.is_visible() and page.get_by_label("Search bodies, bands and orbits").is_visible()
    menu.click()
    assert not about.is_visible()

    # Featured: the toggle names the open system; a pick opens it and folds up.
    toggle = page.locator("button[aria-haspopup=menu]", has_text="★")
    assert "Solar System" in toggle.inner_text()
    toggle.click()
    trappist.click()
    page.wait_for_function("window.__SA3.key === 'trappist-1'", timeout=30_000)
    assert "TRAPPIST-1" in toggle.inner_text() and not trappist.is_visible()

    # The band header carries the values, and opening it shows the sliders.
    head = page.get_by_role("button", name="Band inputs", exact=False)
    assert "1 bar" in head.inner_text()
    head.click()
    assert pressure.is_visible()
    # The legend: opening it folds the band panel away again.
    page.get_by_role("button", name="Legend", exact=False).click()
    assert a_row.is_visible() and not pressure.is_visible()

    # The bands still come on, flat, from the Bands button.
    page.get_by_role("button", name="Bands", exact=False).click()
    page.wait_for_timeout(300)
    assert page.get_by_role("button", name="Bands: On").is_visible()
    for r in page.evaluate("() => window.__t3.report()"):
        if r["solvent"]:
            assert r["isMesh"] and not r["isPoints"] and r["dev"] < 1e-6, r

    # Wide again (a phone turned into a tablet, a window dragged): unfolded.
    page.set_viewport_size({"width": 1400, "height": 850})
    page.wait_for_timeout(300)
    assert trappist.is_visible() and pressure.is_visible() and a_row.is_visible()
    assert not toggle.is_visible() and not menu.is_visible() and about.is_visible()
    assert page.get_by_text("Orient").is_visible()           # labelled again
    assert not errors, errors


def test_three_searching_a_band_switches_on_that_band_only(three):
    three.evaluate("() => window.__SA3.switchTo('solar')")
    search = three.get_by_placeholder("Find in system…")
    search.fill("water band")
    search.press("Enter")
    three.wait_for_timeout(300)
    on = three.evaluate("""() => window.__SA3.bands()
        .filter(m => m.userData.solvent && m.userData.on).map(m => m.userData.name)""")
    assert on and all(n.lower().startswith("water band") for n in on), on
    assert three.evaluate("() => window.__SA3.bandState()") == "Some"


def test_three_a_search_with_no_match_says_so(three):
    search = three.get_by_placeholder("Find in system…")
    search.fill("no such body")
    search.press("Enter")
    assert three.get_by_text("No match for", exact=False).first.is_visible()


def test_plotly_search_still_finds_a_body_and_opens_its_info_panel(viewer):
    # searchTrace now ranks through band_kit.js's _nameMatches, and the info
    # panel lives in the kit; the Plotly viewer must behave exactly as before.
    _open(viewer, "solar")
    viewer.evaluate("q => window.__t.search(q)", "jupiter")
    panel = viewer.locator("#_sa_info_panel")
    assert panel.is_visible() and "Jupiter" in panel.inner_text()
    x = viewer.evaluate("() => window.__t.gd().layout.scene.xaxis.range")
    assert x[1] - x[0] < 10, f"search did not zoom to Jupiter's system: {x}"


def test_plotly_typed_pressure_renames_every_band(viewer):
    _open(viewer, "solar")
    box = viewer.get_by_label("Pressure")
    box.fill("17.8")
    box.press("Enter")
    viewer.wait_for_timeout(600)
    names = [r["name"] for r in viewer.evaluate("() => window.__t.bandReport()")
             if "band" in r["name"] and "Belt" not in r["name"]]
    assert names and all("17.8 bar" in n for n in names), names


def _target_is(page, name):
    return page.evaluate("""n => { const S = window.__SA3;
        const b = S.bodies().find(x => x.data.name === n);
        return S.controls.target.distanceTo(b.obj.position) < 1e-6; }""", name)


def _landed(page):
    # A flight is 700 ms of wall clock, but a software-GPU stall can hold a
    # frame for ~350 ms (the sky's first composite, about a second after
    # load), so wait for the flight to end rather than for a fixed time.
    page.wait_for_function("() => !window.__SA3.flying()", timeout=5_000)


def test_three_a_moons_orbit_rides_with_its_planet(three):
    # Drawn round Earth where Earth is at frame 0; without the carry, Earth
    # and the Moon leave the ellipse within a few frames.
    three.evaluate("() => window.__SA3.switchTo('solar')")
    offsets = three.evaluate("""() => {
      const A = window.__SA3, n = A.nFrames();
      const earth = A.bodies().find(b => b.data.name === 'Earth').obj;
      const orbit = A.lines().find(o => o.userData.name === 'Moon orbit');
      return [0, Math.floor(n / 3), Math.floor(2 * n / 3) + 0.5].map(f => {
        A.setFrame(f);
        return [earth.position.toArray(), orbit.position.clone().sub(earth.position).toArray()];
      });
    }""")
    # The whole position, not x alone: on some opening dates Earth's x a third
    # of a year on is back within 1e-3 AU of frame 0's (7 Oct 2026: 0.0003).
    (p0, first), *rest = offsets
    for p, off in rest:
        assert math.dist(p, p0) > 1e-3, "Earth did not move"
        assert off == pytest.approx(first, abs=1e-9), "the Moon's orbit left Earth behind"


@pytest.mark.parametrize("key", ["castor", "alpha-centauri"])
def test_three_a_band_rides_with_its_star(three, key):
    # Each band is built round its star where the star is at frame 0.  A star
    # in orbit must carry its bands with it, through a slider rebuild too;
    # the primary at the origin keeps its own still.
    three.evaluate("k => window.__SA3.switchTo(k)", key)
    three.get_by_text("Bands:", exact=False).first.click()
    report = three.evaluate("""() => {
      const A = window.__SA3, n = A.nFrames(), out = [];
      const frames = [0, Math.floor(n / 3), Math.floor(2 * n / 3) + 0.5];
      const run = () => frames.map(f => {
        A.setFrame(f);
        return A.bands().filter(m => m.userData.solvent && m.userData.hasRing).map(m => {
          const star = A.bodies().find(b => b.data.name === m.userData.follows).obj;
          return [m.userData.follows, star.position.toArray(),
                  m.position.clone().sub(star.position).toArray()];
        });
      });
      out.push(run());
      A.recomputeBands(3, 0.3, 33);
      out.push(run());
      return out;
    }""")
    for runs in report:
        first, *rest = runs
        moved = set()
        for later in rest:
            for (star, p0, off0), (_, p, off) in zip(first, later):
                if math.dist(p, p0) > 1e-6:
                    moved.add(star)
                assert off == pytest.approx(off0, abs=1e-7), f"{key}: {star}'s band left it behind"
        assert moved, f"{key}: no band-bearing star moved, so this proves nothing"


def test_three_back_returns_through_each_jump(three):
    three.evaluate("() => window.__SA3.switchTo('solar')")
    start = three.evaluate("() => window.__SA3.controls.target.toArray()")
    search = three.get_by_placeholder("Find in system…")
    for q in ("earth", "jupiter"):
        search.fill(q)
        search.press("Enter")
        _landed(three)
    assert _target_is(three, "Jupiter")
    back = three.get_by_role("button", name="Back")
    back.click()
    _landed(three)
    assert _target_is(three, "Earth"), "Back did not return to Earth"
    back.click()
    _landed(three)
    now = three.evaluate("() => window.__SA3.controls.target.toArray()")
    assert now == pytest.approx(start, abs=1e-9), "Back did not return to the opening view"
    back.click()
    assert three.get_by_text("Already at the widest view").first.is_visible()


def test_three_a_jump_made_mid_flight_goes_back_to_where_that_flight_was_going(three):
    # Searching again before the first flight lands must not store the point
    # the camera had reached, or Back stops short of Earth.
    three.evaluate("() => window.__SA3.switchTo('solar')")
    three.evaluate("() => { window.__SA3.search('earth'); window.__SA3.search('jupiter'); }")
    _landed(three)
    assert _target_is(three, "Jupiter")
    three.evaluate("() => window.__SA3.goBack()")
    _landed(three)
    assert _target_is(three, "Earth"), "Back stopped where the first flight had got to"


def test_three_scroll_zoom_is_not_a_jump(three):
    # Only double-clicks and searches go in the history, as in Plotly.
    three.evaluate("() => window.__SA3.switchTo('solar')")
    three.evaluate("""async () => {
      const el = window.__SA3.renderer.domElement, r = el.getBoundingClientRect();
      for (let i = 0; i < 10; i++) {
        el.dispatchEvent(new WheelEvent('wheel', {deltaY: -100, bubbles: true,
          cancelable: true, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2}));
        await new Promise(res => setTimeout(res, 30));
      }
    }""")
    assert three.evaluate("() => window.__SA3.viewHistory()") == 0


# ── Free rotation (docs/architecture/three-renderer.md, rule 7) ───────────────
# OrbitControls was a turntable round world +Y, read once at construction, so
# a drag stopped dead with the Solar System edge-on.  A drag eases in and
# coasts out over frames, and CI's software GPU draws few of them, so each
# check applies what is left at once (__SA3.settle) and measures the result.

_VIEW = """() => { const S = window.__SA3, off = S.camera.position.clone().sub(S.controls.target);
  return { dir: off.clone().normalize().toArray(), dist: off.length(),
           up: S.camera.up.toArray(), pos: S.camera.position.toArray() }; }"""


def _solar(page):
    page.evaluate("() => window.__SA3.switchTo('solar')")
    _landed(page)
    return page.evaluate(_VIEW)


def _settled(page):
    page.evaluate("() => window.__SA3.settle()")
    assert not page.evaluate("() => window.__SA3.spinning()")
    return page.evaluate(_VIEW)


def _deg(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))


def _drag(page, deg, axis, shift=False):
    """One drag across the canvas centre worth `deg` of turn (at most ~half a screen)."""
    left, top, w, h = page.evaluate("""() => { const r = window.__SA3.renderer.domElement
      .getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }""")
    px = deg / (360 / h * 0.6)                   # controls.rotateSpeed
    cx, cy = left + w / 2, top + h / 2
    at = lambda f: (cx + px * f, cy) if axis == "x" else (cx, cy + px * f)
    if shift:
        page.keyboard.down("Shift")
    page.mouse.move(*at(-0.5))
    page.mouse.down()
    for i in range(1, 21):
        page.mouse.move(*at(i / 20 - 0.5))
    page.mouse.up()
    if shift:
        page.keyboard.up("Shift")


def test_three_a_drag_carries_the_camera_over_the_pole(three):
    # Three downward drags of 90 deg turn the camera up, over the top, down the
    # far side and under the system.  A turntable stops at the first pole.
    v0 = _solar(three)
    n = v0["up"]                                  # the band plane's normal
    e0 = sum(a * b for a, b in zip(v0["dir"], n))
    for _ in range(3):
        _drag(three, 90, "y")
        v = _settled(three)
    e = sum(a * b for a, b in zip(v["dir"], n))
    assert e == pytest.approx(-math.sqrt(1 - e0 * e0), abs=0.02), (
        f"elevation {e:.3f} after 270 deg; the old turntable stalled edge-on, near 0")
    assert v["dist"] == pytest.approx(v0["dist"], rel=1e-9), "a rotation zoomed"


def test_three_dragging_sideways_never_stops(three):
    v = _solar(three)
    turned = 0.0
    for _ in range(8):
        before = v["dir"]
        _drag(three, 90, "x")
        v = _settled(three)
        turned += _deg(before, v["dir"])
    assert turned == pytest.approx(720, abs=10), f"eight 90 deg drags turned {turned:.0f} deg"


def test_three_shift_drag_rolls_the_view(three):
    v0 = _solar(three)
    _drag(three, 90, "x", shift=True)
    v = _settled(three)
    assert v["pos"] == pytest.approx(v0["pos"], rel=1e-9, abs=1e-12), "a roll moved the camera"
    assert _deg(v0["up"], v["up"]) == pytest.approx(90, abs=3)


def test_three_a_two_finger_twist_rolls_the_view(three):
    # Real touches through the DevTools protocol, so the pointer ids are live
    # and OrbitControls' pinch runs on the same gesture.  A twist about a fixed
    # midpoint at a fixed spread is no pinch and no pan: only the roll.
    v0 = _solar(three)
    cdp = three.context.new_cdp_session(three)
    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
    cx, cy = three.evaluate("""() => { const r = window.__SA3.renderer.domElement
      .getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }""")

    def points(deg):
        a = math.radians(deg)
        return [{"x": cx + s * 120 * math.cos(a), "y": cy + s * 120 * math.sin(a), "id": i}
                for i, s in enumerate((-1, 1))]

    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": points(0)})
    for deg in range(3, 61, 3):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": points(deg)})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    v = _settled(three)
    assert _deg(v0["up"], v["up"]) == pytest.approx(60, abs=6)
    assert v["dir"] == pytest.approx(v0["dir"], abs=1e-6), "a twist turned the view direction"
    assert v["dist"] == pytest.approx(v0["dist"], rel=1e-6), "a twist zoomed"


def test_three_orient_levels_a_rolled_view(three):
    n = _solar(three)["up"]
    _drag(three, 90, "x", shift=True)
    _settled(three)
    three.get_by_role("button", name="Orient").click()
    _landed(three)
    assert three.evaluate("() => window.__SA3.camera.up.toArray()") == pytest.approx(n, abs=1e-9)


# ── Nearby Stellar Motion: the featured view ───────────────────────────────────
# Every Systems-tab star in galactic light years (docs/architecture/star-motion.md).
# tests/conftest.py points it at the committed snapshot.

VIEW = "nearby-star-motion"

_SCREEN_OF = """n => { const S = window.__SA3, b = S.bodies().find(x => x.data.name === n);
  const v = b.obj.position.clone().project(S.camera), r = S.renderer.domElement.getBoundingClientRect();
  return [r.left + (v.x + 1) / 2 * r.width, r.top + (1 - v.y) / 2 * r.height]; }"""


def _open_view(page):
    page.get_by_role("button", name="Nearby Stellar Motion").click()
    page.wait_for_function("k => window.__SA3.key === k", arg=VIEW)


def test_three_the_view_has_a_featured_button_and_opens_in_light_years(three):
    _open_view(three)
    assert three.evaluate("() => window.__SA3.units()") == "ly"
    assert three.evaluate("() => window.__SA3.bodies().length") > 300
    owned = three.evaluate("() => window.__SA3.lines().filter(l => l.userData.owner).length")
    assert owned > 300
    assert "Stars by spectral class" in three.locator("body").inner_text()


def test_three_clicking_a_star_shows_its_details(three):
    _open_view(three)
    three.evaluate("""() => { const S = window.__SA3;
      S.frameBody(S.bodies().find(b => b.data.name === 'tau Cet')); }""")
    three.wait_for_function("() => !window.__SA3.flying()", timeout=5_000)
    three.evaluate("() => window.SABandKit.hideInfoPanel()")
    three.wait_for_timeout(350)
    x, y = three.evaluate(_SCREEN_OF, "tau Cet")
    three.mouse.move(x, y)
    assert "ly from the Sun" in three.locator("body").inner_text()
    three.mouse.click(x, y)
    panel = three.locator("#_sa_info_panel")
    panel.wait_for(state="visible")
    text = panel.inner_text()
    for field in ("tau Cet", "Spectral type", "Age", "Mass", "Metallicity", "Stellar partners",
                  "Planets", "Luminosity", "Speed", "Direction of motion", "km/s"):
        assert field in text, field
    # Its Sources: a catalog that lists it, and where its motion came from, each a link.
    assert "Sources" in text and "Exists: SIMBAD" in text and "Exists: NASA Exoplanet Archive" in text
    links = panel.locator("a").evaluate_all("as => as.map(a => [a.textContent, a.href])")
    assert links and all(href.startswith("https://") for _, href in links)
    assert any("simbad.cds.unistra.fr" in href for _, href in links)


def test_three_hiding_a_class_hides_its_stars_and_their_arrows(three):
    _open_view(three)
    three.locator("label", has_text="M-type").locator("input").uncheck()
    counts = three.evaluate("""() => { const S = window.__SA3;
      const m = S.bodies().filter(b => b.data.group === 'M-type');
      const names = new Set(m.map(b => b.data.name));
      // The planetless systems' arrows are off with their button, whatever a class row does.
      const optional = new Set(S.bodies().filter(b => b.data.optional).map(b => b.data.name));
      const own = S.lines().filter(l => names.has(l.userData.owner));
      const other = S.lines().filter(l => l.userData.owner && !names.has(l.userData.owner)
        && !optional.has(l.userData.owner) && l.userData.frame === S.motionFrame());
      return {m: m.length, mShown: m.filter(b => b.obj.visible).length,
              arrows: own.length, arrowsShown: own.filter(l => l.visible).length,
              otherShown: other.filter(l => l.visible).length, other: other.length}; }""")
    assert counts["m"] > 100 and counts["mShown"] == 0
    assert counts["arrows"] > 100 and counts["arrowsShown"] == 0
    assert counts["otherShown"] == counts["other"] > 0
    # ...and the motion row switches every arrow, leaving the stars.
    three.locator("label", has_text="Motion (").locator("input").uncheck()
    assert three.evaluate("() => window.__SA3.lines().filter(l => l.userData.owner && l.visible).length") == 0
    assert three.evaluate("() => window.__SA3.bodies().filter(b => b.data.group === 'G-type' && b.obj.visible).length") > 0


def test_three_the_known_objects_are_a_purple_layer_behind_their_button(three):
    # The Known within 100ly tab's unplotted objects: one cloud, off until its button turns it on.
    _open_view(three)
    cloud = """() => { const c = window.__SA3.clouds()[0];
      return {n: c.data.info.length, pts: c.pts.visible,
              arrows: Object.fromEntries(Object.entries(c.arrows).map(([k, l]) => [k, l.visible]))}; }"""
    off = three.evaluate(cloud)
    assert off["n"] > 9000 and not off["pts"] and not any(off["arrows"].values())
    assert "Unclassified (All Known Systems within 100 ly)" not in three.locator("body").inner_text()
    assert "All Known Systems within 100 ly" in three.locator("button[data-optional=known]").inner_text()
    three.locator("button[data-optional=known]").click()
    on = three.evaluate(cloud)
    assert on["pts"] and on["arrows"] == {"sun": True, "lsr": False}
    # Its arrows follow the Galaxy Motion Type button...
    three.evaluate("() => window.__SA3.setMotionFrame('lsr')")
    assert three.evaluate(cloud)["arrows"] == {"sun": False, "lsr": True}
    three.evaluate("() => window.__SA3.setMotionFrame('sun')")
    # ...search finds one of its objects and opens its panel...
    assert three.evaluate("() => window.__SA3.search('GJ 244 A')")
    three.wait_for_function("() => !window.__SA3.flying()", timeout=8_000)
    panel = three.locator("#_sa_info_panel")
    panel.wait_for(state="visible")
    assert "not yet classified" in panel.inner_text() and "Speed" in panel.inner_text()
    # ...and its legend row hides the points and the arrows together.
    three.locator("label", has_text="Unclassified (All Known Systems within 100 ly)").locator("input").uncheck()
    hidden = three.evaluate(cloud)
    assert not hidden["pts"] and not any(hidden["arrows"].values())


_DRIFT = """() => { const S = window.__SA3;
  const b = S.bodies().find(x => x.data.drift && x.data.drift.sun && x.data.name !== 'Solar System');
  const sun = S.bodies().find(x => x.data.name === 'Solar System');
  const c = S.clouds()[0], a = c.pts.geometry.attributes.position.array;
  return {name: b.data.name, pos: b.obj.position.toArray(), start: b.data.pos, drift: b.data.drift,
          sun: sun.obj.position.toArray(), cloud: [a[0], a[1], a[2]], cloudStart: c.data.pos.slice(0, 3),
          cloudDrift: c.data.drift.sun.slice(0, 3)}; }"""


def test_three_play_moves_every_star_along_its_arrow(three):
    _open_view(three)
    play = three.get_by_role("button", name="▶ Play")
    assert play.is_visible() and three.evaluate("() => window.__SA3.nFrames()") == 201
    assert three.locator("text=Now").first.is_visible()
    # The last frame: every moving star at its arrow's tip, 50,000 years on; the Sun, relative to itself, stays.
    three.evaluate("() => window.__SA3.setFrame(200)")
    d = three.evaluate(_DRIFT)
    assert d["pos"] == pytest.approx([p + v for p, v in zip(d["start"], d["drift"]["sun"])], abs=1e-3)
    assert d["sun"] == [0, 0, 0]
    assert d["cloud"] == pytest.approx([p + v for p, v in zip(d["cloudStart"], d["cloudDrift"])], abs=1e-3)
    assert "+50,000 yr" in three.locator("body").inner_text()
    # Relative to the local standard of rest the Sun moves too, along its green arrow.
    three.evaluate("() => window.__SA3.setMotionFrame('lsr')")
    d = three.evaluate(_DRIFT)
    assert d["pos"] == pytest.approx([p + v for p, v in zip(d["start"], d["drift"]["lsr"])], abs=1e-3)
    assert d["sun"] != [0, 0, 0]
    three.evaluate("() => window.__SA3.setMotionFrame('sun')")
    # Play runs the frames on; Pause stops them.
    three.evaluate("() => window.__SA3.setFrame(0)")
    play.click()
    three.wait_for_function("() => window.__SA3.anim().frame > 5", timeout=5_000)
    three.get_by_role("button", name="❚❚ Pause").click()
    f = three.evaluate("() => window.__SA3.anim().frame")
    three.wait_for_timeout(300)
    assert three.evaluate("() => window.__SA3.anim().frame") == f


def test_three_the_known_button_cycles_all_confirmed_unconfirmed_off(three):
    # Off -> All -> Excluding unconfirmed -> Unconfirmed only -> Off: the purple cloud (a curated catalog lists
    # them) and the aquamarine one (only Gaia DR3 does), shown by the mode, legend rows following.
    _open_view(three)
    btn = three.locator("button[data-optional=known]")
    shown = """() => Object.fromEntries(window.__SA3.clouds().map(c => [c.data.key, c.pts.visible]))"""
    rows = lambda: (three.locator("label", has_text="Unclassified (All Known Systems").count(),   # noqa: E731
                    three.locator("label", has_text="Existence unconfirmed (Gaia DR3 only)").count())
    steps = [("All", {"known": True, "known-unconfirmed": True}, (1, 1)),
             ("Excluding unconfirmed", {"known": True, "known-unconfirmed": False}, (1, 0)),
             ("Unconfirmed only", {"known": False, "known-unconfirmed": True}, (0, 1)),
             ("Off", {"known": False, "known-unconfirmed": False}, (0, 0))]
    assert btn.inner_text().endswith("Off")
    for label, want, legend in steps:
        btn.click()
        assert btn.inner_text().endswith(label), label
        assert three.evaluate(shown) == want, label
        assert rows() == legend, label
    # Searching for a hidden object brings its cloud back: the set returns to All.
    btn.click()
    btn.click()                                    # Excluding unconfirmed
    name = three.evaluate("() => window.__SA3.clouds().find(c => c.data.key === 'known-unconfirmed').data.info[0][0]")
    assert three.evaluate(f"() => window.__SA3.search({name!r})")
    assert btn.inner_text().endswith("All") and three.evaluate(shown)["known-unconfirmed"]


def test_three_an_object_only_gaia_lists_is_aquamarine_and_says_so(three):
    # The Known layer's objects that no curated catalog lists: their own cloud and legend row, behind the same
    # button, and a panel that opens with the verdict and links the one Gaia DR3 row that cites them.
    _open_view(three)
    three.locator("button[data-optional=known]").click()
    doubt = three.evaluate("""() => { const c = window.__SA3.clouds().find(c => c.data.key === 'known-unconfirmed');
      return {n: c.data.info.length, shown: c.pts.visible, color: c.data.color, name: c.data.info[0][0],
              gaia: c.data.info[0][11]}; }""")
    assert doubt["n"] == 689 and doubt["shown"] and doubt["color"] == "#7FFFD4"
    assert "Existence unconfirmed (Gaia DR3 only)" in three.locator("body").inner_text()
    assert three.evaluate(f"() => window.__SA3.search({doubt['name']!r})")
    three.wait_for_function("() => !window.__SA3.flying()", timeout=8_000)
    panel = three.locator("#_sa_info_panel")
    panel.wait_for(state="visible")
    text = panel.inner_text()
    assert "Existence unconfirmed" in text and "Only cited in Gaia DR3" in text and "fidelity_v2" in text
    hrefs = panel.locator("a").evaluate_all("as => as.map(a => a.href)")
    assert f"gaiadr3&Source={doubt['gaia']}" in hrefs[0]


def test_three_a_source_label_from_the_sheet_is_text_not_markup(three):
    _open_view(three)
    three.evaluate("""() => { window._SA_BODY_INFO['Test <b>star</b>'] = {rows: [['Name', 'x', '']],
        sources: [['Exists: <b>bold</b> & co', 'https://example.org/?a=1&b="2"']]};
      window.SABandKit.showInfoPanel('Test <b>star</b>'); }""")
    panel = three.locator("#_sa_info_panel")
    panel.wait_for(state="visible")
    assert panel.locator("b").count() == 0
    a = panel.locator("a")
    assert a.inner_text() == "Exists: <b>bold</b> & co"
    assert a.get_attribute("href") == 'https://example.org/?a=1&b="2"'


_SHOWN_BY_FRAME = """() => { const S = window.__SA3, out = {};
  for (const l of S.lines()) if (l.userData.owner && l.visible)
    out[l.userData.frame] = (out[l.userData.frame] || 0) + 1;
  return out; }"""


def test_three_galaxy_motion_type_switches_the_arrows_between_frames(three):
    _open_view(three)
    # It takes the Bands button's place: the view has no bands.
    frame_btn = three.get_by_role("button", name="Galaxy Motion Type")
    assert frame_btn.inner_text().endswith("Solar Reference")
    assert not three.get_by_role("button", name="Bands").is_visible()
    shown = three.evaluate(_SHOWN_BY_FRAME)
    assert list(shown) == ["sun"] and shown["sun"] > 300

    frame_btn.click()
    assert frame_btn.inner_text().endswith("Local Standard of Rest (LSR)")
    lsr = three.evaluate(_SHOWN_BY_FRAME)
    assert list(lsr) == ["lsr"] and lsr["lsr"] == shown["sun"] + 1    # ...plus the Sun's own
    sun_arrow = """() => window.__SA3.lines().find(l => l.userData.owner === 'Solar System').visible"""
    assert three.evaluate(sun_arrow)
    # The Solar System's legend row hides its arrow with it; the Motion row hides every arrow.
    three.locator("label", has_text="Solar System").locator("input").uncheck()
    assert not three.evaluate(sun_arrow)
    three.locator("label", has_text="Motion (").locator("input").uncheck()
    assert three.evaluate(_SHOWN_BY_FRAME) == {}
    three.locator("label", has_text="Motion (").locator("input").check()
    three.locator("label", has_text="Solar System").locator("input").check()
    assert three.evaluate(_SHOWN_BY_FRAME) == lsr

    # A star system gets its Bands button back; returning keeps the frame chosen.
    three.get_by_role("button", name="Alpha Centauri").click()
    three.wait_for_function("() => window.__SA3.key === 'alpha-centauri'")
    assert three.get_by_role("button", name="Bands").is_visible() and not frame_btn.is_visible()
    _open_view(three)
    assert frame_btn.inner_text().endswith("(LSR)") and three.evaluate(_SHOWN_BY_FRAME) == lsr
    frame_btn.click()
    assert three.evaluate(_SHOWN_BY_FRAME) == shown


_PLANETLESS = """() => { const S = window.__SA3;
  const p = S.bodies().filter(b => b.data.optional === 'planetless');
  const names = new Set(p.map(b => b.data.name));
  const own = S.lines().filter(l => names.has(l.userData.owner) && l.userData.frame === S.motionFrame());
  return {n: p.length, shown: p.filter(b => b.obj.visible).length,
          arrows: own.length, arrowsShown: own.filter(l => l.visible).length, on: S.optional('planetless')}; }"""


def test_three_planetless_systems_are_a_button_off_by_default(three):
    _open_view(three)
    btn = three.get_by_role("button", name="High Star Count Systems")
    legend_row = three.locator("label", has_text="High star count systems (4+ stars)")
    assert btn.inner_text().endswith("Off")
    assert three.evaluate(_PLANETLESS) == {"n": 80, "shown": 0, "arrows": 80, "arrowsShown": 0, "on": False}
    assert legend_row.count() == 0
    before = three.evaluate(_SHOWN_BY_FRAME)["sun"]

    btn.click()
    assert btn.inner_text().endswith("On")
    assert three.evaluate(_PLANETLESS) == {"n": 80, "shown": 80, "arrows": 80, "arrowsShown": 80, "on": True}
    assert three.evaluate(_SHOWN_BY_FRAME) == {"sun": before + 80}
    assert "High star count systems (4+ stars) (80)" in legend_row.inner_text()
    # Its legend row hides them and their arrows, as a class row does.
    legend_row.locator("input").uncheck()
    assert three.evaluate(_PLANETLESS)["shown"] == 0 and three.evaluate(_PLANETLESS)["arrowsShown"] == 0
    legend_row.locator("input").check()

    # A star system has no such button; coming back keeps the choice.
    three.get_by_role("button", name="Alpha Centauri").click()
    three.wait_for_function("() => window.__SA3.key === 'alpha-centauri'")
    assert not btn.is_visible()
    _open_view(three)
    assert btn.inner_text().endswith("On") and three.evaluate(_PLANETLESS)["shown"] == 80

    btn.click()
    assert three.evaluate(_PLANETLESS)["shown"] == 0 and legend_row.count() == 0
    # Searching for one of them turns the set back on: framing a hidden star answers nothing.
    search = three.get_by_placeholder("Find in system…")
    search.fill("nu Sco")
    search.press("Enter")
    three.wait_for_timeout(300)
    assert three.evaluate(_PLANETLESS)["on"] and btn.inner_text().endswith("On")


_RINGS = """() => { const S = window.__SA3;
  const r = S.lines().filter((l) => l.userData.optional === 'photosynthesis');
  return {n: r.length, shown: r.filter((l) => l.visible).length, on: S.optional('photosynthesis')}; }"""


def test_three_photosynthesis_rings_are_a_menu_feature_off_by_default(three):
    from hybrasil.data.photosynthesis_limits import drawn_limits
    n = len(drawn_limits())
    three.evaluate("() => window.__SA3.switchTo('alpha-centauri')")
    feat = three.get_by_role("button", name="Even more features")
    item = three.get_by_role("menuitemcheckbox", name="Photosynthesis limits")
    legend_row = three.locator("label[data-kind=lgroup]", has_text="Mosses")
    # Off by default: no ring drawn, no legend row, the menu closed.
    assert three.evaluate(_RINGS) == {"n": 3 * n, "shown": 0, "on": False}
    assert legend_row.count() == 0 and not item.is_visible()
    feat.click()
    assert item.get_attribute("aria-checked") == "false"
    item.click()
    # One ring per organism around each of the three stars.
    assert three.evaluate(_RINGS) == {"n": 3 * n, "shown": 3 * n, "on": True}
    assert item.get_attribute("aria-checked") == "true"
    # An organism's legend row hides its ring around every star.
    legend_row.locator("input").uncheck()
    assert three.evaluate(_RINGS)["shown"] == 3 * (n - 1)
    legend_row.locator("input").check()
    # Kept across a switch, as an optional set is; a view has no feature menu.
    three.evaluate("() => window.__SA3.switchTo('solar')")
    assert three.evaluate(_RINGS) == {"n": n, "shown": n, "on": True}
    _open_view(three)
    assert not feat.is_visible()
    three.evaluate("() => window.__SA3.switchTo('solar')")
    feat.click()
    item.click()
    assert three.evaluate(_RINGS)["shown"] == 0


def test_three_bands_are_still_flat_with_the_rings_on(three):
    # CLAUDE.md's standing rule: the rings share a star, a plane and a scene
    # with the bands, and must leave every band a flat disc.
    three.evaluate("() => window.__SA3.setOptional('photosynthesis', true)")
    _three_band_clickthrough(three, "alpha-centauri", "solar")


_REF = """k => { const S = window.__SA3;
  const r = S.lines().filter((l) => l.userData.optional === k);
  return {n: r.length, shown: r.filter((l) => l.visible).length, on: S.optional(k),
          owners: [...new Set(r.filter((l) => l.visible).map((l) => l.userData.owner))].sort()}; }"""


def test_three_reference_orbits_ring_every_star_from_the_features_menu(three):
    three.evaluate("() => window.__SA3.switchTo('alpha-centauri')")
    feat = three.get_by_role("button", name="Even more features")
    feat.click()
    items = [three.get_by_role("menuitemcheckbox", name=f"{p} reference orbit") for p in ("Neptune", "Earth",
                                                                                            "Mercury")]
    assert all(i.get_attribute("aria-checked") == "false" for i in items)
    stars = ["Alpha Centauri A", "Alpha Centauri B", "Proxima Centauri"]
    assert three.evaluate(_REF, "reference-earth") == {"n": 3, "shown": 0, "on": False, "owners": []}
    items[1].click()
    # Earth's orbit round all three stars; the other two stay off.
    assert three.evaluate(_REF, "reference-earth") == {"n": 3, "shown": 3, "on": True, "owners": stars}
    assert three.evaluate(_REF, "reference-neptune")["shown"] == 0
    assert three.locator("label[data-kind=lgroup]", has_text="Earth's orbit (1.00 AU)").count() == 1
    # Neptune's 30 AU round TRAPPIST-1, a tenth of an AU across: the camera may now go out far enough to see it.
    three.evaluate("() => window.__SA3.switchTo('trappist-1')")
    before = three.evaluate("() => window.__SA3.controls.maxDistance")
    three.evaluate("() => window.__SA3.setOptional('reference-neptune', true)")
    assert three.evaluate("() => window.__SA3.controls.maxDistance") >= 6 * 30 > before
    three.evaluate("() => window.__SA3.setOptional('reference-neptune', false)")
    assert three.evaluate("() => window.__SA3.controls.maxDistance") == before


def test_three_bands_are_still_flat_with_the_reference_orbits_on(three):
    # CLAUDE.md's standing rule: the rings share stars and planes with the bands, and must leave every band flat.
    for p in ("neptune", "earth", "mercury"):
        three.evaluate(f"() => window.__SA3.setOptional('reference-{p}', true)")
    _three_band_clickthrough(three, "alpha-centauri", "solar")


def test_three_bands_are_still_flat_after_the_view(three):
    # CLAUDE.md's standing rule: arriving from anywhere must leave every band a
    # flat disc.  The view has no bands, and a system after it must not care.
    _open_view(three)
    _three_band_clickthrough(three, "alpha-centauri", VIEW)


def test_three_orient_clears_the_history(three):
    three.evaluate("() => window.__SA3.switchTo('solar')")
    search = three.get_by_placeholder("Find in system…")
    search.fill("mars")
    search.press("Enter")
    three.wait_for_timeout(300)
    assert three.evaluate("() => window.__SA3.viewHistory()") == 1
    three.get_by_role("button", name="Orient").click()
    assert three.evaluate("() => window.__SA3.viewHistory()") == 0


def test_three_legend_hides_a_body_and_keeps_its_orbit(three):
    three.evaluate("() => window.__SA3.switchTo('solar')")
    row = three.locator("label[data-kind=body]", has_text="Saturn").first
    row.locator("input").uncheck()
    state = three.evaluate("""() => { const S = window.__SA3;
        const b = S.bodies().find(x => x.data.name === 'Saturn');
        const orbit = S.scene.getObjectByProperty('name', undefined);
        const line = b.obj.parent.children.find(o => o.userData && o.userData.name === 'Saturn orbit');
        return {marker: b.obj.visible,
                label: b.obj.children.every(c => !c.isCSS2DObject || !c.visible),
                orbit: !!(line && line.visible)}; }""")
    assert state == {"marker": False, "label": True, "orbit": True}, state
    # A hidden body cannot be double-clicked...
    hit = three.evaluate("""() => { const S = window.__SA3;
        const b = S.bodies().find(x => x.data.name === 'Saturn');
        const v = b.obj.position.clone().project(S.camera), r = S.renderer.domElement.getBoundingClientRect();
        const p = S.pick((v.x + 1) / 2 * r.width + r.left, (1 - v.y) / 2 * r.height + r.top);
        return p && p.data.name; }""")
    assert hit != "Saturn"
    # ...but a search for it shows it again and ticks its row.
    search = three.get_by_placeholder("Find in system…")
    search.fill("saturn")
    search.press("Enter")
    three.wait_for_timeout(200)
    assert row.locator("input").is_checked()


def test_three_legend_hides_a_reference_arrow(three):
    three.evaluate("() => window.__SA3.switchTo('proxima-centauri')")
    row = three.locator("label[data-kind=line]", has_text="Galactic Center").first
    row.locator("input").uncheck()
    visible = three.evaluate("""() => window.__SA3.scene.children.flatMap(g => g.children)
        .filter(o => o.userData && /^Galactic Center/.test(o.userData.name || ''))
        .map(o => o.visible)""")
    assert visible == [False]


# ── The background sky ───────────────────────────────────────────────────────

def _sky_ready(page):
    page.wait_for_function("window.__SA3.sky().loaded", timeout=30_000)


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_three_the_galactic_centre_arrow_points_at_the_centre_of_the_sky(three, key):
    three.evaluate(f"() => window.__SA3.switchTo({key!r})")
    _sky_ready(three)
    assert three.evaluate("() => window.__SA3.sky().have")
    # The arrow as drawn, through the shader's own lookup (skyUV): the map's
    # centre is l = b = 0, the galactic centre.
    u, v = three.evaluate("""(key) => {
        const L = window.SA3_SYSTEMS[key].lines.find(l => /^Galactic Center/.test(l.name || ''));
        const p = L.pts;
        return window.__SA3.skyUV([p[3] - p[0], p[4] - p[1], p[5] - p[2]]); }""", key)
    # Sgr A* is 0.07 deg from l = b = 0, and the arrow starts at the star, not
    # the Sun: 0.2 deg is 0.0006 in u and 0.001 in v.
    assert u == pytest.approx(0.5, abs=0.002)
    assert v == pytest.approx(0.5, abs=0.002)


def test_three_the_sky_is_drawn_and_the_button_turns_it_off(three):
    _sky_ready(three)
    # A patch of canvas clear of the panels, the legend and the credit line.
    clip = {"x": 360, "y": 560, "width": 300, "height": 200}
    on = three.screenshot(clip=clip)
    credit = three.get_by_text("Deep Star Maps 2020", exact=False)
    assert credit.is_visible()
    three.get_by_role("button", name="Sky: On").click()
    assert three.evaluate("() => window.__SA3.sky().on") is False
    assert not credit.is_visible()
    three.wait_for_timeout(200)
    assert three.screenshot(clip=clip) != on        # the sky was what was there
    # Off stays off across a system switch; the button brings it back.
    three.evaluate("() => window.__SA3.switchTo('trappist-1')")
    assert three.get_by_role("button", name="Sky: Off").is_visible()
    three.get_by_role("button", name="Sky: Off").click()
    assert three.evaluate("() => window.__SA3.sky().on") is True
    assert credit.is_visible()


@pytest.mark.parametrize("size", [(1400, 850), (390, 844)], ids=["desktop", "phone"])
def test_three_the_author_is_credited_bottom_right(page, three_url, size):
    # In the sky credit's type, from about.json, and never under the sky
    # credit, which on a phone wraps beside it.
    from hybrasil.viz.three_viewer import about

    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.goto(three_url)
    page.wait_for_function("!!(window.__SA3 && window.__SA3.ready)", timeout=60_000)
    _sky_ready(page)
    author = page.locator("#sa3-author-credit")
    assert author.is_visible()
    assert author.inner_text() == f"Created by {about()['author']['name']}"
    sky = page.get_by_text("Deep Star Maps 2020", exact=False)
    a, s = author.bounding_box(), sky.bounding_box()
    assert a["x"] + a["width"] == pytest.approx(size[0] - 8, abs=1)
    assert a["y"] + a["height"] == pytest.approx(size[1] - 6, abs=1)
    assert a["x"] >= s["x"] + s["width"], "the author credit overlaps the sky credit"
    style = "el => { const c = getComputedStyle(el); return [c.fontFamily, c.fontSize, c.color]; }"
    assert author.evaluate(style) == sky.evaluate(style)


def test_three_go_to_system_opens_a_stars_featured_system(three):
    _open_view(three)
    panel = three.locator("#_sa_info_panel")
    goto = three.get_by_role("button", name="Go to system")
    # A file page holds only the featured systems: tau Cet's is not in it.
    three.evaluate("() => window.SABandKit.showInfoPanel('tau Cet')")
    panel.wait_for(state="visible")
    assert goto.count() == 0
    three.evaluate("() => window.SABandKit.showInfoPanel('alf Cen A')")
    goto.click()
    three.wait_for_function("() => window.__SA3.key === 'alpha-centauri'", timeout=10_000)
    panel.wait_for(state="hidden")
    assert three.evaluate("() => window.__SA3.units()") == "AU"
    for r in three.evaluate("() => window.__t3.report()"):
        assert r["isMesh"] and r["dev"] < 1e-6, r


# ── The web app (--serve): Featured / More Modeled Systems ───────────────────────────

@pytest.fixture(scope="module")
def app_url():
    import threading
    from hybrasil.web.app import make_server
    from tests.test_web_app import _library

    # Three catalog systems: Test A has four planets, Cand X and Bin Sys one
    # each at 10 and 20 ly.
    srv = make_server(_library(), "solar", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def app(page, app_url):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_viewport_size({"width": 1400, "height": 850})
    page.goto(app_url + "?intro=0")     # the intro has tests of its own
    page.wait_for_function("!!(window.__SA3 && window.__SA3.ready)", timeout=60_000)
    page.evaluate(_THREE_HELPERS)
    yield page
    assert not errors, f"page errors: {errors}"


# ── The intro (docs/architecture/web-app.md, "Intro") ───────────────────────

def _arrive(page, url, width=1400, height=850):
    """Arrive at the app as a visitor does: no ?intro=0, so the map plays."""
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_viewport_size({"width": width, "height": height})
    page.goto(url)
    page.wait_for_function("!!(window.__SA3 && window.__SA3.intro)", timeout=60_000)
    return errors


def test_intro_plays_on_arrival_and_reveals_a_random_body(page, app_url):
    errors = _arrive(page, app_url)
    first = page.evaluate("() => window.__SA3.intro()")
    assert first["arrived"] and first["slide"] == "standard"
    assert first["state"] in ("map", "fading")
    # The map fades, all of it at once, and goes for good.
    page.wait_for_function("['fading', 'done'].includes(window.__SA3.intro().state)",
                           timeout=60_000)
    assert page.evaluate("() => document.querySelectorAll('#sa3-intro *').length") == 0
    page.wait_for_function("window.__SA3.intro().state === 'done'", timeout=10_000)
    assert page.evaluate("() => document.getElementById('sa3-intro')") is None
    page.wait_for_function("!window.__SA3.flying()", timeout=10_000)
    r = page.evaluate("""() => {
        const S = window.__SA3, i = S.intro();
        const entry = S.index().find(e => e.id === S.key);
        const b = S.bodies().find(b => b.data.name === i.body);
        const info = window._SA_BODY_INFO[i.body] || {};
        return { kind: entry.kind, view: !!entry.view, found: !!b, type: info.type,
                 visible: !!(b && b.obj.visible),
                 off: b ? S.controls.target.distanceTo(b.obj.position)
                          / Math.max(b.obj.position.length(), 1e-9) : null };
    }""")
    assert r["kind"] != "motion" and not r["view"], r
    assert r["found"] and r["visible"] and r["type"] != "barycentre", r
    assert r["off"] < 1e-6, r                    # centred on it once the map is gone
    assert not errors, errors


def test_intro_body_is_where_the_island_is(page, app_url):
    # Framed under the map, the body is drawn where the island is.
    _arrive(page, app_url)
    page.wait_for_function("(i => !!i.body && i.state === 'map')(window.__SA3.intro())",
                           timeout=60_000)
    r = page.evaluate("""() => {
        const S = window.__SA3, slide = window.SA3_INTRO_PLAY;
        const b = S.bodies().find(b => b.data.name === S.intro().body);
        const v = b.obj.position.clone().project(S.camera);
        const W = innerWidth, H = innerHeight;
        const k = Math.max(W / slide.width, H / slide.height);
        return { state: S.intro().state,
                 px: (v.x + 1) / 2 * W, py: (1 - v.y) / 2 * H,
                 hx: (W - slide.width * k) / 2 + slide.island.x * slide.width * k,
                 hy: (H - slide.height * k) / 2 + slide.island.y * slide.height * k };
    }""")
    assert r["state"] == "map", r     # not yet flying out
    assert abs(r["px"] - r["hx"]) < 2 and abs(r["py"] - r["hy"]) < 2, r


@pytest.mark.parametrize("size, slide", [((390, 844), "mobile"), ((1400, 850), "standard"),
                                         ((2560, 1080), "ultrawide")])
def test_intro_slide_follows_the_screen_shape(page, app_url, size, slide):
    _arrive(page, app_url, *size)
    assert page.evaluate("() => window.SA3_INTRO_PLAY.name") == slide
    page.wait_for_function("window.__SA3.intro().state === 'done'", timeout=60_000)


def test_a_reload_skips_the_intro_and_keeps_the_system(page, app_url):
    errors = _arrive(page, app_url)
    page.wait_for_function("window.__SA3.intro().state === 'done'", timeout=60_000)
    page.get_by_role("button", name="Alpha Centauri", exact=True).click()
    page.wait_for_function("window.__SA3.key === 'alpha-centauri'", timeout=60_000)
    page.reload()
    page.wait_for_function("!!(window.__SA3 && window.__SA3.ready)", timeout=60_000)
    r = page.evaluate("""() => ({ key: window.__SA3.key, state: window.__SA3.intro().state,
                                   arrived: window.__SA3.intro().arrived,
                                   overlay: !!document.getElementById('sa3-intro') })""")
    assert r == {"key": "alpha-centauri", "state": "off", "arrived": False, "overlay": False}
    assert not errors, errors


def test_a_click_lifts_the_map_early(page, app_url):
    _arrive(page, app_url)
    page.wait_for_function("!!window.__SA3.intro().body", timeout=60_000)
    if page.evaluate("() => window.__SA3.intro().state") == "map":
        page.mouse.click(700, 700)
    page.wait_for_function("window.__SA3.intro().state === 'done'", timeout=5_000)


def test_app_opens_on_a_featured_system_with_a_button_for_each(app):
    assert app.evaluate("() => window.__SA3.key") == "solar"
    featured = app.evaluate("() => window.__SA3.index().filter(e => e.featured).length")
    assert featured == len(BUILTIN_NAMES) + len(FEATURED_VIEWS)
    for name in ("Solar System", "TRAPPIST-1", "55 Cancri", "Castor",
                 "Nearby Stellar Motion"):
        assert app.get_by_role("button", name=name, exact=True).is_visible()


def test_app_the_sky_arrives_as_a_file_and_is_drawn(app):
    _sky_ready(app)
    assert app.evaluate("() => window.SA3_SKY") == "/sky/milky_way_4k.jpg"
    assert app.evaluate("() => window.__SA3.sky().have")


def test_app_featured_button_opens_its_system(app):
    app.get_by_role("button", name="TRAPPIST-1", exact=True).click()
    app.wait_for_function("window.__SA3.key === 'trappist-1'", timeout=30_000)


def test_app_more_systems_is_a_dropdown_of_every_system_by_planets_then_distance(app):
    more = app.get_by_role("button", name="More Modeled Systems")
    assert more.get_attribute("aria-expanded") == "false"
    assert not app.locator("[role=listbox]").is_visible()
    more.click()
    listbox = app.locator("[role=listbox]")
    listbox.wait_for(state="visible")
    assert more.get_attribute("aria-expanded") == "true"
    ids = app.evaluate("""() => [...document.querySelectorAll('[role=option]')]
        .map(o => o.dataset.id)""")
    # Every catalog system -- the featured ones keep their buttons -- most
    # planets first (Test A has four), then nearest (Cand X 10 ly, Bin Sys 20);
    # with them the eleven Planetless 4+ Stars systems whose brown dwarfs are
    # planets (7 Oct 2026; GJ 310.1's since 9 Oct), each placed by its planets and stars too.
    assert [i for i in ids if i.startswith("catalog:")] == ["catalog:Test A", "catalog:Cand X", "catalog:Bin Sys"]
    assert ids[0] == "catalog:Test A" and len(ids) == 14
    assert "14 systems" in app.evaluate("() => document.querySelector('[role=listbox]')"
                                        ".previousElementSibling.textContent")
    # The featured buttons stay in the bar while it is open.
    assert app.get_by_role("button", name="TRAPPIST-1", exact=True).is_visible()
    # A second click puts it away; so does Escape, and a click elsewhere.
    more.click()
    assert more.get_attribute("aria-expanded") == "false"
    assert not listbox.is_visible()
    more.click()
    app.get_by_label("Search all systems").press("Escape")
    assert not listbox.is_visible()
    more.click()
    app.mouse.click(150, 600)   # left of the dropdown panel, which is right-aligned
    assert not listbox.is_visible()
    # An entry opens its system, closes the list, and names it on the button.
    more.click()
    app.locator("[role=option][data-id='catalog:Cand X']").click()
    app.wait_for_function("window.__SA3.key === 'catalog:Cand X'", timeout=30_000)
    assert not listbox.is_visible()
    assert "Cand X" in more.inner_text()


_OPTION_IDS = "() => [...document.querySelectorAll('[role=option]')].map(o => o.dataset.id)"


def _system_type(page, text):
    """The System Type button `text` in the open dropdown."""
    return page.get_by_role("button", name=text, exact=True)


def test_app_the_dropdown_asks_for_a_system_type_planetary_first(app):
    more = app.get_by_role("button", name="More Modeled Systems")
    more.click()
    app.locator("[role=listbox]").wait_for(state="visible")
    assert app.get_by_text("System Type:", exact=True).is_visible()
    planetary, planetless, motion = (_system_type(app, t) for t in
                                     ("Planetary", "High Star Count (Planetless)", "Stellar Motion"))
    for b in (planetary, planetless, motion):
        assert b.is_visible()
    # The Sgr A* Cluster is listed under Stellar Motion, not a type of its own (10 Oct 2026).
    assert _system_type(app, "Galactic Center").count() == 0
    assert planetary.get_attribute("aria-pressed") == "true"
    assert planetless.get_attribute("aria-pressed") == "false"
    # Planetary: the catalog systems, and the Planetless 4+ Stars systems whose brown dwarfs are planets
    # (7 Oct 2026, docs/hybrasil-instructions.md section 6).
    ids = app.evaluate(_OPTION_IDS)
    assert [i for i in ids if i.startswith("catalog:")] == ["catalog:Test A", "catalog:Cand X", "catalog:Bin Sys"]
    assert {i[len("planetless:"):] for i in ids if i.startswith("planetless:")} == {"GJ 570", "ksi UMa", "GJ 867", "GJ 569", "tau Cyg", "pi1 Cnc", "GJ 9829", "BD+37 1091", "BD+39 496", "GJ 3347", "GJ 310.1"}
    # High Star Count (Planetless): every hierarchy on the tab with no planet, and searching stays within the type.
    # Castor is planetary since its brown dwarf Cc became a planet.
    planetless.click()
    assert planetless.get_attribute("aria-pressed") == "true"
    ids = app.evaluate(_OPTION_IDS)
    assert len(ids) == 68 and all(i.startswith("planetless:") for i in ids) and "castor" not in ids
    # Most stars first, then nearest, as the Planetary list goes by planets.
    stars = app.evaluate("() => [...document.querySelectorAll('[role=option]')]"
                         ".map(o => window.__SA3.index().find(e => e.id === o.dataset.id).n_stars)")
    assert stars == sorted(stars, reverse=True) and stars[0] > stars[-1]
    assert "most stars first" in app.locator("[role=listbox]").evaluate("l => l.previousElementSibling.textContent")
    box = app.get_by_label("Search all systems")
    box.type("trappist", delay=20)
    assert "trappist-1" not in app.evaluate(_OPTION_IDS)
    box.fill("")
    box.type("1 Hya", delay=20)
    assert app.evaluate(_OPTION_IDS)[0] == "planetless:1 Hya"
    box.fill("")
    # Stellar Motion: the Nearby Stellar Motion view, then the Sgr A* Cluster.
    motion.click()
    assert app.evaluate(_OPTION_IDS) == ["nearby-star-motion", "galactic:sgr-a"]
    # The type is kept between opens.
    more.click()
    more.click()
    assert motion.get_attribute("aria-pressed") == "true"
    assert app.evaluate(_OPTION_IDS) == ["nearby-star-motion", "galactic:sgr-a"]
    app.locator("[role=option][data-id='nearby-star-motion']").click()
    app.wait_for_function("window.__SA3.key === 'nearby-star-motion'", timeout=60_000)
    # And back to High Star Count (Planetless), to open one from the list: the dropdown names it.
    more.click()
    planetless.click()
    app.locator("[role=option][data-id='planetless:1 Hya']").click()
    app.wait_for_function("window.__SA3.key === 'planetless:1 Hya'", timeout=60_000)
    assert "1 Hya" in more.inner_text()
    # A featured system is named by its own button, not the dropdown's.
    app.get_by_role("button", name="Castor", exact=True).click()
    app.wait_for_function("window.__SA3.key === 'castor'", timeout=60_000)
    assert "Castor" not in more.inner_text()


def test_app_the_sgr_a_cluster_opens_from_stellar_motion(app):
    app.get_by_role("button", name="More Modeled Systems").click()
    _system_type(app, "Stellar Motion").click()
    assert app.evaluate(_OPTION_IDS) == ["nearby-star-motion", "galactic:sgr-a"]
    assert "Sgr A* Cluster (Galactic Center)" in app.locator("[role=option][data-id='galactic:sgr-a']").inner_text()
    app.locator("[role=option][data-id='galactic:sgr-a']").click()
    app.wait_for_function("window.__SA3.key === 'galactic:sgr-a'", timeout=60_000)
    bodies = dict(app.evaluate("() => window.__SA3.bodies().map(b => [b.data.name, b.data.fill])"))
    assert "Sgr A* (supermassive black hole)" in bodies and "S2" in bodies
    assert bodies["S4716 (disputed)"] is None          # disputed: a ring, no fill
    assert "S301" in bodies and bodies["G2 (dusty object)"] is not None     # dusty, but its orbit is not disputed
    panel = app.locator("#_sa_info_panel")
    app.evaluate("() => window.SABandKit.showInfoPanel('S2')")
    panel.wait_for(state="visible")
    text = panel.inner_text()
    assert "B0-2.5 V" in text and "Sources" in text and "Exists: SIMBAD [EG97] S2" in text
    hrefs = panel.locator("a").evaluate_all("as => as.map(a => decodeURIComponent(a.href))")
    assert any("abs/2022A&A...657L..12G" in h for h in hrefs)
    app.evaluate("() => window.SABandKit.showInfoPanel('Sgr A* (supermassive black hole)')")
    assert "Supermassive black hole" in panel.inner_text()
    app.evaluate("() => window.SABandKit.showInfoPanel('S4716 (disputed)')")
    assert "Disputed" in panel.inner_text()
    app.evaluate("() => window.SABandKit.showInfoPanel('G2 (dusty object)')")
    assert "Nature disputed" in panel.inner_text()
    app.evaluate("() => window.SABandKit.showInfoPanel('S301')")
    text = panel.inner_text()
    assert "F1.5" in text and "8.68 yr" in text and "F1.5 (inferred)" not in text
    assert "Sgr A* Cluster (Galactic Center)" in app.get_by_role("button", name="More Modeled Systems").inner_text()


def test_app_a_planetless_system_opens_with_flat_bands_and_a_hollow_candidate(app):
    # GJ 3347's candidate brown dwarf Aa2 is a planet since 7 Oct 2026, so the system is Planetary.
    app.get_by_role("button", name="More Modeled Systems").click()
    _system_type(app, "Planetary").click()
    app.get_by_label("Search all systems").type("GJ 3347", delay=20)
    app.get_by_label("Search all systems").press("Enter")
    app.wait_for_function("window.__SA3.key === 'planetless:GJ 3347'", timeout=60_000)
    bodies = app.evaluate("() => window.__SA3.bodies().map(b => [b.data.name, b.data.fill])")
    hypo = [b for b in bodies if b[0].startswith("GJ 3347 Aa2")]
    assert hypo and hypo[0][1] is None, hypo          # a ring, no fill
    for r in app.evaluate("() => window.__t3.report()"):
        assert r["isMesh"] and r["dev"] < 1e-6, r
    # The dropdown names it, lit, like any non-featured pick.
    assert "GJ 3347" in app.get_by_role("button", name="More Modeled Systems").inner_text()


def test_three_the_file_page_lists_each_system_type(three):
    three.get_by_role("button", name="More Modeled Systems").click()
    three.locator("[role=listbox]").wait_for(state="visible")
    # No catalog in a file page: Planetary has nothing beyond the buttons.
    assert three.evaluate(_OPTION_IDS) == []
    # Castor is planetary since 7 Oct 2026 (its brown dwarf is a planet), so it is a button, not a list entry.
    _system_type(three, "High Star Count (Planetless)").click()
    assert three.evaluate(_OPTION_IDS) == []
    _system_type(three, "Stellar Motion").click()
    assert three.evaluate(_OPTION_IDS) == ["nearby-star-motion"]
    assert three.get_by_role("button", name="Castor", exact=True).is_visible()


@pytest.fixture(scope="module")
def padded_app_url():
    """The test catalog plus twenty listing-only systems, to fill the list."""
    import threading
    from hybrasil.web.app import CATALOG_PREFIX, make_server
    from tests.test_web_app import _library

    lib = _library()
    lib._index = lib.index() + [
        {"id": f"{CATALOG_PREFIX}Pad {i:02d}", "name": f"Pad {i:02d}", "featured": False,
         "aliases": [], "planets": [], "n_planets": 2 + i % 5,
         "distance_ly": 30.0 + i, "stellar_class": "K0 V"}
        for i in range(20)
    ]
    srv = make_server(lib, "solar", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()
    srv.server_close()


def test_app_more_systems_shows_twelve_and_scrolls_to_the_rest(page, padded_app_url):
    page.set_viewport_size({"width": 1400, "height": 1000})
    page.goto(padded_app_url + "?intro=0")
    page.wait_for_function("!!(window.__SA3 && window.__SA3.ready)", timeout=60_000)
    page.get_by_role("button", name="More Modeled Systems").click()
    page.locator("[role=listbox]").wait_for(state="visible")
    geom = page.evaluate("""() => {
        const l = document.querySelector('[role=listbox]');
        const box = l.getBoundingClientRect();
        const rows = [...l.querySelectorAll('[role=option]')];
        const inView = rows.map(r => { const b = r.getBoundingClientRect();
            return b.top >= box.top - 0.5 && b.bottom <= box.bottom + 0.5; });
        return {n: rows.length, inView, scrolls: l.scrollHeight > l.clientHeight,
                planets: rows.map(r => parseInt(r.children[1].textContent, 10) || 0)};
    }""")
    assert geom["n"] == 34                      # every system, none held back: 3 + 20 + 11 planetless
    assert geom["inView"][:12] == [True] * 12   # twelve rows tall...
    assert not any(geom["inView"][12:])         # ...and the rest below the fold
    assert geom["scrolls"]
    assert geom["planets"] == sorted(geom["planets"], reverse=True)
    # Scene labels stay under the list. They ignore the pointer, so a hit
    # test cannot see them; what keeps them down is their layer's own
    # stacking context, which CSS2DRenderer's per-label z-index cannot leave.
    assert page.evaluate("""() => { const l = [...document.querySelectorAll('div')]
        .find(d => d.style.pointerEvents === 'none' && d.style.inset === '0px');
        return l && getComputedStyle(l).zIndex; }""") == "0"
    # The arrow keys walk past the fold and the list follows.
    box = page.get_by_label("Search all systems")
    for _ in range(15):
        box.press("ArrowDown")
    assert page.evaluate("""() => {
        const l = document.querySelector('[role=listbox]');
        const r = l.querySelector('[aria-selected=true]').getBoundingClientRect();
        const b = l.getBoundingClientRect();
        return r.top >= b.top - 0.5 && r.bottom <= b.bottom + 0.5; }""")
    # The last system is reachable by scrolling, and opens like any other.
    page.evaluate("() => { const l = document.querySelector('[role=listbox]'); "
                  "l.scrollTop = l.scrollHeight; }")
    last = page.locator("[role=option]").last
    assert last.is_visible()
    page.locator("[role=option][data-id='catalog:Cand X']").scroll_into_view_if_needed()
    page.locator("[role=option][data-id='catalog:Cand X']").click()
    page.wait_for_function("window.__SA3.key === 'catalog:Cand X'", timeout=30_000)


@pytest.fixture(scope="module")
def snapshot_app_url():
    """The web app on the committed snapshot: every catalog system, as served."""
    import threading
    from hybrasil.data.catalog_loader import parse_workbook
    from hybrasil.data.snapshot import load_snapshot_workbook
    from hybrasil.web.app import make_server
    from tests.test_web_app import _library

    cat = parse_workbook(load_snapshot_workbook())
    srv = make_server(_library(catalog_loader=lambda: cat), "solar", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()
    srv.server_close()


def test_app_go_to_system_opens_a_stars_catalog_system(page, snapshot_app_url):
    for p in _load_three(page, snapshot_app_url + "?intro=0"):
        _open_view(p)
        panel = p.locator("#_sa_info_panel")
        goto = p.get_by_role("button", name="Go to system")
        # GJ 680's only planet was rejected: there is no system to open.
        p.evaluate("() => window.SABandKit.showInfoPanel('GJ 680')")
        panel.wait_for(state="visible")
        assert goto.count() == 0
        p.evaluate("() => window.SABandKit.showInfoPanel('tau Cet')")
        goto.click()
        p.wait_for_function("() => window.__SA3.key === 'catalog:tau Cet'", timeout=30_000)
        names = p.evaluate("() => window.__SA3.bodies().map(b => b.data.name)")
        assert any(n.startswith("tau Cet ") for n in names)
        assert "tau Cet" in p.get_by_role("button", name="More Modeled Systems").inner_text()
        for r in p.evaluate("() => window.__t3.report()"):
            assert r["isMesh"] and r["dev"] < 1e-6, r


def test_app_more_systems_finds_and_loads_a_catalog_system(app):
    app.get_by_role("button", name="More Modeled Systems").click()
    box = app.get_by_label("Search all systems")
    box.type("testia", delay=20)                 # Test A's IAU nickname
    first = app.locator("[role=option]").first
    assert "Test A" in first.inner_text() and "Testia" in first.inner_text()
    # The list drops over the legend rather than under it.
    hit = app.evaluate("""() => { const o = document.querySelector('[role=option]');
        const r = o.getBoundingClientRect();
        return o.contains(document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)); }""")
    assert hit, "the suggestion list is covered by something"
    box.press("Enter")
    app.wait_for_function("window.__SA3.key === 'catalog:Test A'", timeout=30_000)
    names = app.evaluate("() => window.__SA3.bodies().map(b => b.data.name)")
    assert any(n.startswith("Test A b") for n in names)
    assert "Test A" in app.get_by_role("button", name="More Modeled Systems").inner_text()
    # Its bands are flat meshes like any other system's.
    for r in app.evaluate("() => window.__t3.report()"):
        assert r["isMesh"] and r["dev"] < 1e-6, r


def test_app_more_systems_corrects_a_typo(app):
    app.get_by_role("button", name="More Modeled Systems").click()
    box = app.get_by_label("Search all systems")
    box.type("trapist", delay=20)
    listing = app.locator("[role=listbox]").inner_text()
    assert "Did you mean TRAPPIST-1?" in listing
    box.press("Enter")
    app.wait_for_function("window.__SA3.key === 'trappist-1'", timeout=30_000)
    # A pick closes the dropdown; a featured system is named by its own button.
    more = app.get_by_role("button", name="More Modeled Systems")
    assert more.get_attribute("aria-expanded") == "false"
    assert "TRAPPIST" not in more.inner_text()


def test_app_a_featured_systems_catalog_name_opens_the_featured_one(app):
    app.get_by_role("button", name="More Modeled Systems").click()
    box = app.get_by_label("Search all systems")
    box.type("55 cnc a", delay=20)
    box.press("Enter")
    app.wait_for_function("window.__SA3.key === '55-cancri'", timeout=30_000)


def test_app_tab_completes_without_opening(app):
    app.get_by_role("button", name="More Modeled Systems").click()
    box = app.get_by_label("Search all systems")
    box.type("upsil", delay=20)
    box.press("Tab")
    assert box.input_value() == "Upsilon Andromedae"
    assert app.evaluate("() => window.__SA3.key") == "solar"


def test_app_sliders_carry_to_a_system_fetched_later(app):
    box = app.get_by_label("Pressure")
    box.fill("17.8")
    box.press("Enter")
    app.evaluate("() => window.__SA3.openSystem('catalog:Test A')")
    app.wait_for_function("window.__SA3.key === 'catalog:Test A'", timeout=30_000)
    names = app.evaluate("""() => window.__SA3.bands()
        .filter(m => m.userData.solvent).map(m => m.userData.name)""")
    assert names and all("17.8 bar" in n for n in names), names


# ── A catalog system beside the featured ones ───────────────────────────────
#
# Every browser launch now carries the six featured systems, so a catalog
# system is a seventh button -- with its own trace indices, and one band stack
# per star.  That is the ground the torus bug stood on, so it gets the same
# click-through, arriving from a featured system and leaving to one.  The
# catalog is the synthetic test workbook: Bin Sys is a binary whose companion
# has a planet and a band stack of its own.  No credential, no network.

CATALOG_KEY = "Bin Sys"
_AROUND_THE_CATALOG_SYSTEM = [(CATALOG_KEY, "alpha-centauri"),
                              ("alpha-centauri", CATALOG_KEY),
                              ("55-cancri", CATALOG_KEY)]


def _catalog_page(tmp_path_factory, module, extra_args):
    from hybrasil.data import catalog_loader
    from tests.test_catalog_loader import make_workbook

    out = tmp_path_factory.mktemp("catalog") / "viewer.html"
    real_open, real_get = module._open_in_browser, catalog_loader.get_catalog
    module._open_in_browser = lambda p: shutil.copy(p, out)
    catalog_loader.get_catalog = (
        lambda *a, **k: catalog_loader.parse_workbook(make_workbook()))
    try:
        cli.main(["--source", "catalog", "--system", CATALOG_KEY] + extra_args)
    finally:
        module._open_in_browser = real_open
        catalog_loader.get_catalog = real_get
    return out.as_uri()


@pytest.fixture(scope="session")
def catalog_viewer_url(tmp_path_factory):
    return _catalog_page(tmp_path_factory, export, ["--renderer", "plotly"])


@pytest.fixture(scope="session")
def catalog_three_url(tmp_path_factory):
    from hybrasil.viz import three_viewer
    return _catalog_page(tmp_path_factory, three_viewer, [])


@pytest.fixture
def catalog_viewer(page, catalog_viewer_url):
    return _load_plotly(page, catalog_viewer_url)


@pytest.fixture
def catalog_three(page, catalog_three_url):
    yield from _load_three(page, catalog_three_url)


def test_three_a_catalog_launch_carries_every_featured_system(catalog_three):
    keys = catalog_three.evaluate("() => Object.keys(window.SA3_SYSTEMS)")
    assert keys == list(BUILTIN_NAMES) + list(FEATURED_VIEWS) + [CATALOG_KEY]
    assert catalog_three.evaluate("() => window.__SA3.key") == CATALOG_KEY


@pytest.mark.parametrize("key,arrive_from", _AROUND_THE_CATALOG_SYSTEM)
def test_bands_stay_flat_around_a_catalog_system(catalog_viewer, key, arrive_from):
    _plotly_band_clickthrough(catalog_viewer, key, arrive_from)


@pytest.mark.parametrize("key,arrive_from", _AROUND_THE_CATALOG_SYSTEM)
def test_three_bands_stay_flat_around_a_catalog_system(catalog_three, key,
                                                       arrive_from):
    _three_band_clickthrough(catalog_three, key, arrive_from)


def test_three_a_catalog_binary_has_a_band_stack_per_star(catalog_three):
    catalog_three.evaluate("k => window.__SA3.switchTo(k)", CATALOG_KEY)
    names = [r["name"] for r in catalog_three.evaluate("() => window.__t3.report()")
             if r["solvent"]]
    assert any("Bin Sys B" in n for n in names), names
    assert any("Bin Sys B" not in n for n in names), names


# ── The static site (--build-site): the web app as files, under a path prefix ─

@pytest.fixture(scope="module")
def static_site_url(tmp_path_factory):
    """The static site, served as plain files from /hybrasil/ -- no API server."""
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    from hybrasil.web.static_site import build_site
    from tests.test_static_site import small_library

    root = tmp_path_factory.mktemp("static")
    build_site(small_library(), root / "hybrasil", "solar")

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/hybrasil/"
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def static_app(page, static_site_url):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_viewport_size({"width": 1400, "height": 850})
    page.goto(static_site_url + "?intro=0")
    page.wait_for_function("!!(window.__SA3 && window.__SA3.ready)", timeout=60_000)
    page.evaluate(_THREE_HELPERS)
    yield page
    assert not errors, f"page errors: {errors}"


def test_static_site_plays_the_intro_from_its_own_files(page, static_site_url):
    errors = _arrive(page, static_site_url)
    assert page.evaluate("() => window.SA3_INTRO_PLAY.image") == "intro/standard.webp"
    page.wait_for_function("window.__SA3.intro().state === 'done'", timeout=60_000)
    assert page.evaluate("() => window.__SA3.intro().body")
    assert not errors, errors


def test_static_site_opens_with_every_featured_system_and_the_sky(static_app):
    assert static_app.evaluate("() => window.__SA3.key") == "solar"
    featured = static_app.evaluate("() => window.__SA3.index().filter(e => e.featured).length")
    assert featured == len(BUILTIN_NAMES) + len(FEATURED_VIEWS)
    _sky_ready(static_app)
    assert static_app.evaluate("() => window.__SA3.sky().have")


def test_static_site_loads_a_catalog_system_from_its_file(static_app):
    static_app.get_by_role("button", name="More Modeled Systems").click()
    box = static_app.get_by_label("Search all systems")
    box.type("testia", delay=20)
    box.press("Enter")
    static_app.wait_for_function("window.__SA3.key === 'catalog:Test A'", timeout=30_000)
    names = static_app.evaluate("() => window.__SA3.bodies().map(b => b.data.name)")
    assert any(n.startswith("Test A b") for n in names)
    for r in static_app.evaluate("() => window.__t3.report()"):
        assert r["isMesh"] and r["dev"] < 1e-6, r


@pytest.mark.parametrize("key", BUILTIN_NAMES)
def test_static_site_bands_stay_flat_after_a_switch(static_app, key):
    arrive_from = "alpha-centauri" if key == "solar" else "solar"
    for k in (arrive_from, key):          # fetch both scene files first
        assert static_app.evaluate("k => window.__SA3.openSystem(k)", k), k
    _three_band_clickthrough(static_app, key, arrive_from)


# ── Suggest Changes ─────────────────────────────────────────────────────────

def _suggest_dialog(page):
    page.get_by_role("button", name="Suggest Changes").first.click()
    dialog = page.get_by_role("dialog", name="Suggest Changes")
    dialog.wait_for(state="visible")
    return dialog


def test_suggest_changes_opens_on_the_current_system_and_keeps_keys_to_itself(app):
    opener = app.get_by_role("button", name="Suggest Changes").first
    dialog = _suggest_dialog(app)
    assert app.locator("#sa3-sg-system").input_value() == "Solar System"
    # Every system the map has is offered, Sgr A* and Nearby Stellar Motion included,
    # but the field is free text.
    offered = app.evaluate("() => [...document.querySelectorAll('#sa3-sg-systems option')].map(o => o.value)")
    assert "Nearby Stellar Motion" in offered and any("Sgr A*" in o for o in offered)
    before = app.evaluate("() => window.__SA3.camera.position.toArray()")
    app.locator("#sa3-sg-description").press_sequentially("wasd", delay=10)
    app.locator("#sa3-sg-description").press("ArrowUp")
    assert app.evaluate("() => window.__SA3.camera.position.toArray()") == before
    app.keyboard.press("Escape")
    dialog.wait_for(state="hidden")
    assert app.evaluate("() => document.activeElement.textContent").endswith("Suggest Changes")
    assert opener.is_visible()


def test_suggest_changes_checks_the_form_before_sending(app, tmp_path, monkeypatch):
    store = tmp_path / "s.jsonl"
    monkeypatch.setenv("HYBRASIL_SUGGESTIONS_FILE", str(store))
    _suggest_dialog(app)
    app.locator("#sa3-sg-description").fill("")
    app.get_by_role("button", name="Send suggestion").click()
    err = app.locator("#sa3-sg-error")
    assert "What should change is required" in err.inner_text()
    assert "Source(s) needs at least 1" in err.inner_text()
    assert not store.exists()


def test_suggest_changes_from_an_info_panel_records_a_new_system(app, tmp_path, monkeypatch):
    import json as _json
    store = tmp_path / "s.jsonl"
    monkeypatch.setenv("HYBRASIL_SUGGESTIONS_FILE", str(store))
    app.evaluate("() => window.SABandKit.showInfoPanel('Earth')")
    app.locator("#_sa_info_panel").get_by_role("button", name="Suggest Changes").click()
    dialog = app.get_by_role("dialog", name="Suggest Changes")
    dialog.wait_for(state="visible")
    assert app.locator("#sa3-sg-objects").input_value() == "Earth"
    # A system the map does not have: accepted as written.
    app.locator("#sa3-sg-system").fill("Kepler-452")
    app.locator("#sa3-sg-objects").fill("Kepler-452 b")
    app.locator("#sa3-sg-description").fill("Add this planet; its radius and period are published.")
    app.locator("#sa3-sg-sources").fill("Jenkins et al. 2015, AJ 150, 56\nhttps://doi.org/10.1088/0004-6256/150/2/56")
    app.locator("#sa3-sg-email").fill("someone@example.org")
    app.get_by_role("button", name="Send suggestion").click()
    dialog.wait_for(state="hidden")
    [rec] = [_json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    assert rec["system"] == "Kepler-452" and rec["system_id"] == ""
    assert rec["objects"] == ["Kepler-452 b"] and len(rec["sources"]) == 2
    assert rec["email"] == "someone@example.org" and rec["status"] == "new"


def test_suggest_changes_names_a_known_system_by_its_id(app, tmp_path, monkeypatch):
    import json as _json
    store = tmp_path / "s.jsonl"
    monkeypatch.setenv("HYBRASIL_SUGGESTIONS_FILE", str(store))
    _suggest_dialog(app)
    app.locator("#sa3-sg-system").fill("nearby stellar motion")
    app.locator("#sa3-sg-objects").fill("")
    app.locator("#sa3-sg-description").fill("Barnard's Star's arrow looks too short.")
    app.locator("#sa3-sg-sources").fill("Gaia DR3")
    app.get_by_role("button", name="Send suggestion").click()
    app.get_by_role("dialog", name="Suggest Changes").wait_for(state="hidden")
    [rec] = [_json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    assert rec["system_id"] == "nearby-star-motion"


def test_suggest_changes_on_the_static_site_posts_to_the_relative_endpoint(static_app):
    assert static_app.evaluate("() => window.SA3_SUGGEST_URL") == "api/suggestions"
    _suggest_dialog(static_app)
    static_app.locator("#sa3-sg-description").fill("A change worth checking against its source.")
    static_app.locator("#sa3-sg-sources").fill("A source")
    with static_app.expect_request(lambda r: r.method == "POST") as req:
        static_app.get_by_role("button", name="Send suggestion").click()
    assert req.value.url.endswith("/hybrasil/api/suggestions")
    # A plain file server has no function behind that path: the form says so
    # and keeps what was written.
    static_app.wait_for_function("document.querySelector('#sa3-sg-error').textContent.length > 0")
    assert static_app.locator("#sa3-sg-description").input_value().startswith("A change")


def test_a_file_page_offers_no_suggest_changes(three):
    assert three.evaluate("() => window.SA3_SUGGEST_URL") is None
    assert not three.get_by_role("button", name="Suggest Changes").is_visible()
    three.evaluate("() => window.SABandKit.showInfoPanel('Earth')")
    assert three.locator("#_sa_info_panel").get_by_role("button", name="Suggest Changes").count() == 0


# ── About ───────────────────────────────────────────────────────────────────

def _about(page):
    page.get_by_role("button", name="About").click()
    dialog = page.get_by_role("dialog", name="Hybrasil Star and Exoplanet Map")
    dialog.wait_for(state="visible")
    return dialog


def test_about_credits_the_author_and_cites_the_data_at_its_version(app):
    dialog = _about(app)
    text = dialog.inner_text()
    assert "Cade Summers" in text and "AGPL-3.0-or-later" in text and "CC BY-SA 4.0" in text
    assert dialog.get_by_role("link", name="0009-0007-0361-4779").get_attribute("href") == \
        "https://orcid.org/0009-0007-0361-4779"
    assert "Summers, C. (2026). Hybrasil Star and Exoplanet Map [Computer software]. https://hybrasil.app" in text
    title = app.evaluate("() => fetch('/api/systems').then(r => r.json()).then(d => d.catalog.title)")
    assert f"(Version {title}) [Data set]" in text
    assert "@software{summers2026hybrasil," in text
    assert "Scientific Visualization Studio" in text
    # No support links until about.json has the handles.
    assert "Ko-fi" not in text and "Patreon" not in text
    assert "Suggest Changes stores what you send" in text
    app.keyboard.press("Escape")
    dialog.wait_for(state="hidden")
    assert app.evaluate("() => document.activeElement.textContent").endswith("About")


def test_about_shows_a_doi_once_about_json_has_one(app):
    app.evaluate("() => { window.SA3_ABOUT.dois.software = '10.5281/zenodo.1234';"
                 " window.SA3_ABOUT.support.ko_fi = 'hybrasil'; }")
    text = _about(app).inner_text()
    assert "[Computer software]. https://doi.org/10.5281/zenodo.1234" in text
    assert "doi = {10.5281/zenodo.1234}" in text
    assert "Ko-fi" in text


def test_a_file_page_has_about_too_but_no_suggestion_privacy_line(three):
    text = _about(three).inner_text()
    assert "Cade Summers" in text and "[Data set]" in text and "(Version" not in text
    assert "Suggest Changes stores" not in text
