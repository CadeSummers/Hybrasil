# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for a solvent band starting hidden, and for what has to keep working.

The figure opens on the orbits alone and the viewer's Bands button brings
every band in the system back at once.  What a band carries out of Python is
the whole handle that button has on it: a `meta` dict tagged `solvent-band` and an
initial `visible` of 'legendonly'.  A belt that was observed is part of the
system and is drawn as it always was.
"""

import numpy as np
import pytest

from hybrasil.data.builtin_systems import get_builtin_system
from hybrasil.mechanics.solvent_bands import SolventChoice
from hybrasil.mechanics.time_series import (
    system_orbit_paths,
    system_positions_at,
    system_time_series,
)
from hybrasil.mechanics.units import J2000
from hybrasil.viz.animation import build_animated_figure
from hybrasil.viz.static_plot import (_belt_trace, build_static_figure,
                                           is_band_trace)


ALL_BANDS = SolventChoice.parse("all")


def _static_figure(key="solar", bands=ALL_BANDS):
    system = get_builtin_system(key, bands)
    paths, coils = system_orbit_paths(system, t_start=J2000)
    return system, build_static_figure(
        system, system_positions_at(system, J2000), paths, coil_paths=coils)


def _band_traces(fig):
    return [t for t in fig.data if is_band_trace(t)]


class TestTheZoneCarriesTheDistinction:
    def test_a_derived_band_says_it_is_one(self):
        zones = get_builtin_system("solar", ALL_BANDS).belt_zones
        assert all(z.is_solvent_band for z in zones if "band" in z.name)

    def test_an_observed_belt_does_not(self):
        zones = get_builtin_system("solar", ALL_BANDS).belt_zones
        belts = [z for z in zones if not z.is_solvent_band]
        assert [z.name for z in belts] == ["Asteroid Belt", "Kuiper Belt"]

    def test_the_default_is_a_belt(self):
        # Every other BeltZone in the codebase is a belt; only the solvent
        # module opts in.
        from hybrasil.models.system import BeltZone
        assert BeltZone("x", 1.0, 2.0).is_solvent_band is False


class TestTheTraceStartsHidden:
    @pytest.mark.parametrize("key", ["solar", "trappist-1", "alpha-centauri"])
    def test_every_band_is_tagged_and_hidden(self, key):
        _, fig = _static_figure(key)
        bands = _band_traces(fig)
        assert bands, f"{key} draws no solvent band"
        assert {t.visible for t in bands} == {"legendonly"}

    def test_the_tag_is_on_every_ring_of_a_band(self):
        # A band is up to three rings -- a conservative core and two albedo
        # margins -- and the button has to move all of them together.
        system, fig = _static_figure()
        assert len(_band_traces(fig)) == sum(
            1 for z in system.belt_zones if z.is_solvent_band)

    def test_nothing_else_in_the_figure_is_hidden(self):
        _, fig = _static_figure()
        assert [t.name for t in fig.data
                if not is_band_trace(t) and t.visible == "legendonly"] == []

    def test_a_belt_is_drawn_as_it_always_was(self):
        _, fig = _static_figure()
        belts = [t for t in fig.data if t.name in ("Asteroid Belt", "Kuiper Belt")]
        assert len(belts) == 2
        assert all(t.visible is None and t.meta is None for t in belts)

    def test_the_animated_figure_agrees_with_the_static_one(self):
        system = get_builtin_system("solar", ALL_BANDS)
        t_end = J2000 + 365.25
        paths, coils = system_orbit_paths(system, t_start=J2000, t_end=t_end)
        times, series = system_time_series(system, J2000, t_end, 5)
        fig = build_animated_figure(system, series, paths, times, coil_paths=coils)
        assert {t.visible for t in _band_traces(fig)} == {"legendonly"}


class TestWhatHidingMustNotBreak:
    def test_a_hidden_band_still_claims_its_room_in_the_scene(self):
        # The scene extent is unchanged by the band being off, so switching it
        # on never has to resize the scene under the viewer -- and a system
        # whose planets are all inside its band still frames the band.
        system, fig = _static_figure("trappist-1")
        outer = max(z.r_outer_au for z in system.belt_zones if z.extends_scene)
        assert fig.layout.scene.xaxis.range[1] >= outer

    def test_the_geometry_is_the_same_ring_it_always_was(self):
        # Only `visible` and `meta` change; a hidden band is a complete mesh,
        # which is what lets the viewer clip it into a deep zoom on demand.
        zone = next(z for z in get_builtin_system("solar", ALL_BANDS).belt_zones
                    if z.is_solvent_band)
        trace = _belt_trace(zone)
        pts = np.column_stack([trace.x, trace.y, trace.z])
        # Measured in the band's own plane: it is tilted with the system's
        # orbits and lifted along its normal by the stacking offset.
        normal = np.asarray(zone.normal)
        radii = np.linalg.norm(pts - np.outer(pts @ normal, normal), axis=1)
        assert np.isclose(radii.min(), zone.r_inner_au)
        assert np.isclose(radii.max(), zone.r_outer_au)

    def test_one_legend_entry_per_solvent(self):
        # One albedo gives one ring per solvent, so a legend entry is a
        # solvent rather than one of three rings making up a band.
        _, fig = _static_figure()
        bands = _band_traces(fig)
        assert all(t.showlegend for t in bands)
        assert len({t.name for t in bands}) == len(bands)

    def test_a_still_image_shows_the_bands(self):
        # A PNG has no button, so save_png switches them back on.  Without
        # this, `--solvent all --output png` renders an empty sky.
        import hybrasil.viz.export as export

        _, fig = _static_figure()
        captured = {}
        fig.write_image = lambda path, **kw: captured.update(
            visible={t.visible for t in _band_traces(fig)})
        export.save_png(fig, "unused.png")
        assert captured["visible"] == {True}

class TestTheCliBuildsEveryBand:
    """A band is built hidden, so drawing all eight costs nothing on screen.

    `--solvent` is about what goes in the legend, not about what is drawn --
    except for a PNG, which has no button to switch anything on with.
    """

    def test_the_default_is_every_solvent(self):
        from hybrasil.cli import build_parser

        args = build_parser().parse_args(["--system", "solar"])
        assert args.solvent == "all"

    def test_the_default_puts_all_eight_in_the_legend(self):
        from hybrasil.mechanics.solvent_bands import SOLVENTS

        choice = SolventChoice.parse("all")
        assert len(choice.solvents) == len(SOLVENTS) == 8
        zones = [z for z in get_builtin_system("solar", choice).belt_zones
                 if z.is_solvent_band]
        # One trace per solvent, always: the viewer's sliders rewrite these in
        # place, so a band that came and went would shift every index after it.
        assert len(zones) == 8
        # Carbon dioxide has no liquid phase at 1 bar, which is a result and
        # not a gap -- its ring is empty and solvent_notes() says why.
        empty = [z.name for z in zones if z.r_outer_au == 0.0]
        assert empty == ["Carbon dioxide band (1 bar)"]

    def test_narrowing_narrows_the_legend(self):
        zones = get_builtin_system("solar", SolventChoice.parse("water")).belt_zones
        assert {z.name.split(" band")[0] for z in zones if z.is_solvent_band} == {"Water"}
