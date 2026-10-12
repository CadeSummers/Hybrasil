# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The three.js viewer places a body by Kepler's equation between frames, and agrees with Python doing it.

Between two frames the viewer used to slide each marker along the straight line joining them. A planet that goes
round several times in one frame step -- Proxima d, 5.2 d, in Proxima's 19-day steps -- then cut across the inside
of its orbit, which is what 'a planet drifts off its orbit' was (9 Oct 2026). Now the viewer solves Kepler's
equation at the moment shown (`keplerXYZ` / `keplerPosition` in three_viewer.js, from `kepler_meta()` in
animation.py), so the Kepler pipeline exists twice. These tests run the viewer's own JavaScript under node and
hold it to `elements_to_cartesian`, through the figure the viewer is actually given.
"""
import json
import shutil
import subprocess

import numpy as np
import pytest

from hybrasil.data.builtin_systems import BUILTIN_NAMES, FEATURED_CATALOG_HOSTS
from hybrasil.data.loader import get_system
from hybrasil.data.planetless_loader import build_planetless_system, parse_planetless, planetless_span_days
from hybrasil.data.snapshot import load_snapshot_workbook
from hybrasil.figures import _natural_span_days, build_figure
from hybrasil.mechanics.kepler import elements_to_cartesian
from hybrasil.mechanics.time_series import system_orbit_paths
from hybrasil.mechanics.units import J2000
from hybrasil.viz.three_viewer import _JS_PATH, figure_to_scene

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

_JS = _JS_PATH.read_text(encoding="utf-8")
FRAMES = 120
# Fractions of a frame step: on a frame, a quarter, halfway, nearly the next.
FRACTIONS = (0.0, 0.25, 0.5, 0.97)


def _js_function(name: str) -> str:
    """One `function name(...) {...}` out of three_viewer.js, braces matched."""
    start = _JS.index("function %s(" % name)
    depth, i = 0, _JS.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(_JS[i], 0)
        if depth == 0:
            return _JS[start:i + 1]
        i += 1


def _js_positions(kepler: dict, times: list) -> dict:
    """{body: [[x, y, z] per time]} from the viewer's own functions, under node."""
    script = "\n".join([
        _js_function("keplerXYZ"), _js_function("keplerPosition"),
        "var K = %s, T = %s, out = {};" % (json.dumps(kepler), json.dumps(times)),
        "for (var name in K.bodies) out[name] = T.map(function (t) { return keplerPosition(K, name, t, {}); });",
        "console.log(JSON.stringify(out));",
    ])
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _python_position(system, name: str, t: float) -> np.ndarray:
    """Where Python puts a body at t: its elements plus its parent chain, as system_time_series adds it."""
    bodies = {b.name: b for b in system.bodies}
    seen = [b.name for b in system.bodies]
    p = np.array(elements_to_cartesian(bodies[name].elements, t))
    parent = bodies[name].parent
    if parent and seen.index(parent) < seen.index(name) and bodies[parent].elements is not None:
        p = p + _python_position(system, parent, t)
    return p


def _scene(system, span: float, t0: float = J2000) -> dict:
    return figure_to_scene(build_figure(system, t0, t0 + span, mode="animated", frames=FRAMES))


def _times(kepler: dict) -> list:
    step = (kepler["t1"] - kepler["t0"]) / (kepler["n"] - 1)
    return [kepler["t0"] + (k + f) * step for k in range(0, kepler["n"] - 1, 7) for f in FRACTIONS]


def _featured():
    return [(key, get_system("builtin", key)) for key in BUILTIN_NAMES]


@pytest.fixture(scope="module")
def planetless():
    """A few hierarchies from the snapshot: barycentres, coils, a brown dwarf on a subsystem."""
    systems = parse_planetless(load_snapshot_workbook(), skip=FEATURED_CATALOG_HOSTS["castor"])
    return [(h, build_planetless_system(systems[h])) for h in ("GJ 310.1", "ksi UMa", "1 Hya", "GJ 3347")]


class TestTheTwoImplementationsAgree:

    @pytest.mark.parametrize("key,system", _featured(), ids=[k for k, _ in _featured()])
    def test_featured_system(self, key, system):
        self._agree(system, _scene(system, _natural_span_days(system)))

    def test_planetless_hierarchies(self, planetless):
        for _, system in planetless:
            self._agree(system, _scene(system, planetless_span_days(system)))

    def _agree(self, system, scene):
        K = scene["kepler"]
        assert K and K["n"] == len(scene["frames"]["positions"]) == FRAMES
        names = [b["name"] for b in scene["bodies"]]
        assert set(K["bodies"]) <= set(names)
        by_label = {b.label(): b.name for b in system.bodies}
        times = _times(K)
        got = _js_positions(K, times)
        for label in K["bodies"]:
            for t, p in zip(times, got[label]):
                want = _python_position(system, by_label[label], t)
                scale = max(1.0, float(np.linalg.norm(want)))
                assert np.allclose(p, want, rtol=0, atol=1e-9 * scale), (label, t, p, want)
        # And on a frame, the viewer's position is the figure's own frame position.
        pos = scene["frames"]["positions"]
        step = (K["t1"] - K["t0"]) / (K["n"] - 1)
        for fi in (0, 37, FRAMES - 1):
            on_frame = _js_positions(K, [K["t0"] + fi * step])
            for label in K["bodies"]:
                k = names.index(label) * 3
                assert np.allclose(on_frame[label][0], pos[fi][k:k + 3], rtol=0, atol=1e-9), (label, fi)


class TestBetweenFramesABodyStaysOnItsOrbit:

    def test_proxima_b_and_d_stay_on_their_rings(self):
        system = get_system("builtin", "proxima-centauri")
        span = _natural_span_days(system)
        scene = _scene(system, span)
        K = scene["kepler"]
        paths, _ = system_orbit_paths(system, t_start=J2000, t_end=J2000 + span)
        mids = [K["t0"] + (k + 0.5) * (K["t1"] - K["t0"]) / (K["n"] - 1) for k in range(K["n"] - 1)]
        got = _js_positions(K, mids)
        for name in ("Proxima Centauri b", "Proxima Centauri d"):
            a = K["bodies"][name]["el"][0]
            ring = np.array(paths[name]).T
            for p in got[name]:
                assert _distance_to_polyline(np.array(p), ring) < 1e-4 * a, name

    def test_the_hazard_is_real(self):
        # What the viewer did before: the chord between two frames. Proxima d goes round several times per frame
        # step, so halfway along the chord it is well off its ring. If the span ever shrinks enough for the chord
        # to stay on the ring, this test no longer guards anything and must be revisited.
        system = get_system("builtin", "proxima-centauri")
        span = _natural_span_days(system)
        scene = _scene(system, span)
        K, names, pos = scene["kepler"], [b["name"] for b in scene["bodies"]], scene["frames"]["positions"]
        name = "Proxima Centauri d"
        assert (K["t1"] - K["t0"]) / (K["n"] - 1) > K["bodies"][name]["el"][7]   # a step is longer than an orbit
        paths, _ = system_orbit_paths(system, t_start=J2000, t_end=J2000 + span)
        ring, k, a = np.array(paths[name]).T, names.index(name) * 3, K["bodies"][name]["el"][0]
        worst = max(_distance_to_polyline((np.array(pos[f][k:k + 3]) + np.array(pos[f + 1][k:k + 3])) / 2, ring)
                    for f in range(len(pos) - 1))
        assert worst > 0.1 * a


def _distance_to_polyline(p: np.ndarray, pts: np.ndarray) -> float:
    """Shortest distance from p to the closed polyline through pts."""
    a, b = pts, np.roll(pts, -1, axis=0)
    ab = b - a
    s = np.clip(np.einsum("ij,ij->i", p - a, ab) / np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-300), 0, 1)
    return float(np.min(np.linalg.norm(a + s[:, None] * ab - p, axis=1)))
