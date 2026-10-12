# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Switching systems must not let one system's frames reach another's traces.

A frame carries the trace *indices* it writes to, and an index means something
different in every system.  The Solar System's frames write single-point
markers and axis lines to traces 18-46; in Alpha Centauri traces 13-36 are the
solvent bands.  Swapping figures on the same graph div let the old system's
frame data reach the new system's traces, turning every mesh3d band that landed
on a marker index into a scatter3d -- drawn as its 360 vertices in fat markers,
two rings of beads at the inner and outer radius, which reads as a torus rather
than a flat disc.

The damage was exactly the overlap, which is what made it look like one solvent
was plotted differently from another: coming from the Solar System, Formamide
(trace 17) was untouched and Sulfuric acid (trace 18) was a torus.

These tests pin the fix and, just as importantly, pin that the hazard is real --
a test that the indices never collide would pass for the wrong reason.
"""

import numpy as np
import pytest

from hybrasil.data.builtin_systems import BUILTIN_NAMES, get_builtin_system
from hybrasil.mechanics.solvent_bands import SolventChoice
from hybrasil.mechanics.time_series import (system_orbit_paths,
                                                 system_time_series)
from hybrasil.mechanics.units import J2000
from hybrasil.viz.animation import build_animated_figure
from hybrasil.viz.export import _ZOOM_JS, _build_switcher_js

ALL_BANDS = SolventChoice.parse("all")


def _figure(key):
    system = get_builtin_system(key, ALL_BANDS)
    paths, coils = system_orbit_paths(system, 360, J2000, J2000 + 365.25)
    times, series = system_time_series(system, J2000, J2000 + 365.25, 3)
    return build_animated_figure(system, series, paths, times, coil_paths=coils)


def _band_indices(fig):
    return {i for i, t in enumerate(fig.data)
            if isinstance(getattr(t, "meta", None), dict)
            and t.meta.get("kind") == "solvent-band"}


def _frame_targets(fig):
    targets = set()
    for frame in fig.frames:
        targets.update(frame.traces or ())
    return targets


class TestTheHazardIsReal:
    """Without this, the tests below would pass for the wrong reason."""

    def test_some_system_writes_frames_where_another_keeps_bands(self):
        figs = {k: _figure(k) for k in BUILTIN_NAMES}
        collisions = {}
        for src in BUILTIN_NAMES:
            for dst in BUILTIN_NAMES:
                if src == dst:
                    continue
                overlap = _frame_targets(figs[src]) & _band_indices(figs[dst])
                if overlap:
                    collisions[(src, dst)] = len(overlap)
        assert collisions, (
            "no system's frame indices overlap another's band indices; the "
            "switcher test below would then prove nothing")
        # The case the bug was reported from.
        assert collisions.get(("solar", "alpha-centauri")) == 19

    def test_a_systems_own_frames_never_touch_its_own_bands(self):
        # Which is why a single-system figure was always fine, and why this
        # only ever showed up in the multi-system switcher.
        for key in BUILTIN_NAMES:
            fig = _figure(key)
            assert not (_frame_targets(fig) & _band_indices(fig)), key


class TestTheSwitcherStartsClean:
    def _js(self):
        return _build_switcher_js(
            {"solar": _figure("solar"),
             "alpha-centauri": _figure("alpha-centauri")}, "solar")

    def test_it_plots_into_a_fresh_div(self):
        js = self._js()
        assert "createElement('div')" in js
        assert "replaceChild(fresh, gd)" in js
        assert "Plotly.purge(gd)" in js

    def test_it_replaces_data_layout_and_frames_together(self):
        js = self._js()
        assert "Plotly.newPlot(gd, {" in js
        assert "frames: fig.frames || []" in js

    def test_it_does_not_swap_systems_with_react(self):
        # react updates traces in place by index, which is the whole problem.
        js = self._js()
        assert "Plotly.react(gd, fig.data" not in js
        assert "Plotly.addFrames(gd, fig.frames)" not in js


class TestTheControlsFollowTheNewDiv:
    """A fresh div is useless if the toolbar keeps acting on the old one."""

    def test_controls_publish_a_rebind_hook(self):
        assert "_controlsRebind" in _ZOOM_JS
        assert "_controlsRebind = function (g)" in _ZOOM_JS

    def test_reattach_repoints_the_controls(self):
        i = _ZOOM_JS.find("window._saReattach = function (gd) {")
        assert i > 0
        assert "if (_controlsRebind) _controlsRebind(gd);" in _ZOOM_JS[i:i + 400]

    def test_addControls_keeps_its_div_in_one_rebindable_variable(self):
        i = _ZOOM_JS.find("function addControls(gd_init) {")
        assert i > 0, "addControls must take the div as gd_init and shadow it"
        assert "var gd = gd_init;" in _ZOOM_JS[i:i + 400]
