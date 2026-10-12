# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Guards on the viewer JavaScript injected into every HTML export.

These assert on the shape of `_ZOOM_JS` rather than on behaviour, because the
behaviour only exists in a browser.  Each one stands for a bug that actually
shipped and was caught in Chrome, not a hypothetical.
"""

import pytest

from hybrasil.viz.export import _ZOOM_JS


class TestCoordinateDecoding:
    """Plotly 3.x base64-encodes multi-point coordinate arrays.

    `trace.x` arrives as `{bdata, dtype}` with no `.length`, so anything that
    reads coordinates off `gd.data` sees nothing at all unless it decodes
    first.  This silently disabled both the band search and the visibility
    rule until it was caught in the browser.
    """

    def test_decoder_exists(self):
        assert "function _coords(" in _ZOOM_JS
        assert "v.bdata" in _ZOOM_JS
        assert "atob(" in _ZOOM_JS

    def test_decoder_covers_the_dtype_plotly_emits(self):
        # Float64 is what Plotly uses for AU coordinates.
        assert "f8: Float64Array" in _ZOOM_JS

    @pytest.mark.parametrize("reader", ["_traceBBox", "traceGroupTarget"])
    def test_coordinate_readers_decode(self, reader):
        start = _ZOOM_JS.index("function %s(" % reader)
        end = _ZOOM_JS.index("\n  function ", start + 1)
        assert "_coords(" in _ZOOM_JS[start:end], (
            f"{reader} reads coordinates and must decode them first"
        )


class TestGeometryClipping:
    """What does not fit the scene box is cut to it, not thrown away.

    Hiding every trace that did not fit entirely left the Earth zoom with
    three traces out of 54 — no Earth orbit, no water band, nothing but the
    Moon. Clipping keeps the part that is in view and still keeps every
    coordinate inside the box, which is what stops the scene collapsing.
    """

    def test_the_clippers_exist(self):
        for fn in ("_clipSegment", "_clipPolyline", "_clipMesh", "_clipPolyFace"):
            assert "function %s(" % fn in _ZOOM_JS

    def test_clipping_reads_the_original_geometry_not_the_screen(self):
        # Clipping the previous clip's output erodes a trace a little further
        # at every zoom step until nothing is left of it.
        start = _ZOOM_JS.index("function _buildGeom(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "_coords(t.x)" in body and "_coords(t.y)" in body
        clip = _ZOOM_JS[_ZOOM_JS.index("function _clipPolyline("):]
        clip = clip[:clip.index("\n  function ")]
        assert "g.x[" in clip and "gd.data" not in clip

    def test_a_system_swap_drops_the_cached_geometry(self):
        # Two systems can have the same trace count, so the count check in
        # updateSceneVisibility cannot catch a swap on its own.
        start = _ZOOM_JS.index("window._saReattach = function")
        end = _ZOOM_JS.index("captureRanges(gd);", start)
        assert "_geom            = null;" in _ZOOM_JS[start:end]

    def test_markers_are_never_rewritten_only_hidden(self):
        # The animation writes marker coordinates by index every frame, so
        # clipping them would be a fight over the same arrays.
        start = _ZOOM_JS.index("function updateSceneVisibility(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "g.kind === 'line' ? _clipPolyline(g, lo, hi, eps)" in body
        assert "g.kind === 'mesh' ? _clipMesh(g, lo, hi)" in body
        assert ": null;" in body, "a third kind is being clipped; markers must not be"

    def test_a_clipped_mesh_carries_its_faces(self):
        # x/y/z alone would leave Plotly indexing the old vertex list.
        start = _ZOOM_JS.index("function updateSceneVisibility(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        for face in ("i: pad(nv + nl).concat(mI)", "j: pad(nv + nl).concat(mJ)",
                     "k: pad(nv + nl).concat(mK)"):
            assert face in body

    def test_a_line_breaks_rather_than_joining_two_runs(self):
        # An orbit can enter and leave the box twice; joining the runs would
        # draw a chord straight across the view.
        start = _ZOOM_JS.index("function _clipPolyline(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "X.push(null); Y.push(null); Z.push(null);" in body


class TestSceneVisibility:
    """A ring larger than the scene cube is cut into flat-ended arcs.

    Plotly clips to the axis ranges, so a ring wider than the box renders as
    four arcs with flat ends.  Clipping the geometry ourselves is what stops
    that, and what keeps every visible coordinate inside the box.
    """

    def test_rule_is_containment_not_a_radius_ratio(self):
        assert "function updateSceneVisibility(" in _ZOOM_JS
        assert "updateOrbitVisibility" not in _ZOOM_JS, "stale LOD reference left behind"

    def test_markers_take_part_too(self):
        """Body markers are why deep zoom used to render an empty frame.

        Plotly normalises its 3D scene against the data still visible, not
        against the axis range, so one marker left on at 700 AU while the
        window is a few thousandths of an AU wide collapses everything inside
        that window. Every trace with coordinates must be eligible for hiding.
        """
        start = _ZOOM_JS.index("function _isClippable(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "t.x.length" in body and "t.x.bdata" in body
        # No trace type is carved out: an exemption here is what broke deep zoom.
        for exempt in ("mesh3d", "' orbit'", "trajectory ("):
            assert exempt not in body, (
                f"{exempt} is special-cased again; every trace must be eligible"
            )

    def test_hidden_traces_keep_their_legend_entry(self):
        # 'legendonly' rather than false, so the legend does not reshuffle as
        # the user zooms.
        assert "'legendonly'" in _ZOOM_JS

    def test_every_path_that_changes_the_scene_refreshes_visibility(self):
        # The scroll-zoom handler rewrote the scene without refreshing
        # visibility, which is how chopped rings survived a wheel zoom.
        for anchor in ("'scene.camera': {eye: newEye, center: newCenter, up: up}",
                       "if (cam) layout['scene.camera'] = cam;"):
            assert anchor in _ZOOM_JS
        assert _ZOOM_JS.count("updateSceneVisibility(gd,") >= 5

    def test_scroll_zoom_refreshes_visibility(self):
        wheel = _ZOOM_JS[_ZOOM_JS.index("addEventListener('wheel'"):]
        wheel = wheel[:wheel.index("function addControls(")]
        # The box re-cut and its visibility pass go out as one Plotly call.
        assert "updateSceneVisibility(gd, newXr, newYr, newZr, zoomLayout)" in wheel


class TestMarkerSearchUnaffected:
    def test_single_point_test_still_guards_the_marker_search(self):
        # Markers stay plain arrays, so the length check is what separates them
        # from lines and meshes without paying to decode anything.
        start = _ZOOM_JS.index("function searchTrace(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        assert "t.x.length !== 1" in _ZOOM_JS[start:end]


class TestScrollZoomSmoothness:
    """Scroll zoom used to do a full scene rebuild per wheel event.

    A trackpad emits dozens of events per gesture, and each one relaid out the
    scene *and* restyled every trace, so the browser was asked for ~80 gl3d
    rebuilds per flick and delivered them in lurches.  The same fixed step per
    event also meant a flick zoomed roughly 24x further on a trackpad than the
    identical flick on a wheel.
    """

    def _wheel_listener_body(self):
        start = _ZOOM_JS.index("addEventListener('wheel'")
        end = _ZOOM_JS.index("}, {signal: signal, capture: true, passive: false});", start)
        return _ZOOM_JS[start:end]

    def test_the_listener_only_accumulates(self):
        # Nothing that touches Plotly may run per event: that is the whole
        # point of coalescing.  The work belongs in _applyWheelZoom.
        body = self._wheel_listener_body()
        assert "_wheelAccum +=" in body
        assert "_scheduleWheel(gd)" in body
        assert "Plotly." not in body, "the wheel listener is doing render work again"

    def test_the_step_follows_the_delta_not_the_event_count(self):
        # deltaMode 1 is lines and 2 is pages; both have to reach the same
        # scale as pixel mode or a Firefox wheel zooms a different amount.
        body = self._wheel_listener_body()
        assert "evt.deltaMode === 1" in body and "evt.deltaMode === 2" in body
        assert "Math.pow(STEP, -accum)" in _ZOOM_JS, "fixed per-event step is back"

    def test_a_single_update_cannot_jump_the_camera(self):
        # Without the clamp a fast flick collapses straight onto MIN_AU, which
        # reads as a cut rather than as motion.
        assert "Math.max(0.5, Math.min(2, Math.pow(STEP, -accum)))" in _ZOOM_JS

    def test_the_scene_box_is_kept_when_it_still_fits(self):
        # Re-cutting the box re-normalises and re-uploads every trace; moving
        # the camera alone does not.  The band is what makes most wheel events
        # camera-only.
        assert "fitRatio" in _ZOOM_JS
        assert "boxUnchanged" in _ZOOM_JS

    def test_visibility_restyle_is_diffed(self):
        # Sending every trace on every event was the other half of the
        # per-event rebuild cost, and on most events every trace is fully in
        # view and was fully in view before, so nothing has to be sent.
        start = _ZOOM_JS.index("function updateSceneVisibility(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "if (g.state === 'full') continue;" in body
        assert "if (g.state !== 'hidden') {" in body

    def test_backpressure_cannot_strand_the_wheel(self):
        # _wheelBusy is cleared from a Plotly promise.  Plotly resolves it from
        # its render loop, so a stalled or throttled renderer can leave it
        # pending for good -- and scroll zoom would be dead until reload.
        assert "var watchdog = setTimeout(release, 1000);" in _ZOOM_JS
        assert "clearTimeout(watchdog);" in _ZOOM_JS

    def test_raf_has_a_timer_backstop(self):
        # requestAnimationFrame never fires in a hidden or occluded tab.  Any
        # scroll that arrives there has to still be applied, not queued forever.
        start = _ZOOM_JS.index("function _scheduleWheel(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "requestAnimationFrame(run)" in body
        assert "_wheelTimer = setTimeout(run," in body

    def test_a_locked_scene_holds_the_gesture_instead_of_dropping_it(self):
        # The old handler returned outright while _rescaleLock was set, so the
        # 600 ms after a double-click swallowed every scroll in that window.
        start = _ZOOM_JS.index("function _scheduleWheel(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "if (_rescaleLock || _wheelBusy) { if (_wheelAccum) _scheduleWheel(gd); return; }" in body


class TestSolventBandControls:
    """Two controls over one set of bands, and they have to agree.

    Each band keeps its own legend entry, as every trace has; the Bands button
    sits on top of them and moves the whole set.  So the state is per trace and
    the button reads it back, rather than either control holding a flag the
    other can contradict.
    """

    def test_the_controls_match_on_meta_not_on_the_trace_name(self):
        # Band names carry the solvent, the pressure and the albedo margin,
        # and they are what the search box reads.  Matching a name here would
        # tie both controls to the wording of a legend entry.
        start = _ZOOM_JS.index("function _isBandTrace(")
        end = _ZOOM_JS.index("\n  function ", start + 1)
        body = _ZOOM_JS[start:end]
        assert "t.meta.kind === 'solvent-band'" in body
        assert "name" not in body

    def test_the_state_is_per_trace_not_one_flag(self):
        # One global flag cannot express "the viewer switched water on from
        # the legend and left the other six off".
        start = _ZOOM_JS.index("function _buildGeom(")
        end = _ZOOM_JS.index("\n  // Liang-Barsky", start + 1)
        body = _ZOOM_JS[start:end]
        assert "isBand: band," in body
        assert "bandOn: band ? _bandsOn : true," in body

    def test_a_band_nobody_asked_for_is_not_the_boxs_to_judge(self):
        # Without this the next zoom -- of which there is one on load -- would
        # clip every hidden band straight back into view.
        start = _ZOOM_JS.index("function updateSceneVisibility(")
        end = _ZOOM_JS.index("\n  function restoreScene(", start + 1)
        body = _ZOOM_JS[start:end]
        assert "if (g.isBand && !g.bandOn) continue;" in body

    def test_switching_on_goes_through_the_clipper(self):
        # A band is usually wider than the box the viewer is zoomed into, and
        # visible:true on a full-width ring inside a moon-sized box puts
        # coordinates far outside it -- which collapses the view to gridlines.
        start = _ZOOM_JS.index("function _showBands(")
        end = _ZOOM_JS.index("\n  // How many bands", start + 1)
        body = _ZOOM_JS[start:end]
        assert "updateSceneVisibility(gd, _sa_ranges.xr" in body
        assert "visible: off" in body and "'legendonly'" in body
        assert "visible: true" not in body

    def test_switching_forces_the_cached_state_to_hidden(self):
        # updateSceneVisibility skips a trace whose cached state says it is
        # already fully drawn, so a band switched back on has to be marked
        # hidden first or nothing is ever re-sent for it.
        start = _ZOOM_JS.index("function _showBands(")
        end = _ZOOM_JS.index("\n  // How many bands", start + 1)
        assert "g.state = 'hidden';" in _ZOOM_JS[start:end]

    def test_the_legend_entry_still_switches_one_band(self):
        # This is the control that was there before the button, and it has to
        # keep working -- through the same path, not Plotly's default toggle.
        start = _ZOOM_JS.index("gd.on('plotly_legendclick'")
        end = _ZOOM_JS.index("gd.on('plotly_legenddoubleclick'", start)
        body = _ZOOM_JS[start:end]
        assert "if (!_isBandTrace(gd.data[i])) return;" in body, (
            "only a band's legend entry may be intercepted"
        )
        assert "_showBands(gd, _bandGroup(gd, i), !_bandOn(i));" in body
        assert "return false;" in body, "Plotly must not also toggle it"

    def test_a_legend_click_moves_the_whole_band(self):
        # A band's two albedo margins share one legend entry, and Plotly's own
        # toggle moves a whole legend group; taking the clicked trace alone
        # would leave half a band behind.
        start = _ZOOM_JS.index("function _bandGroup(")
        end = _ZOOM_JS.index("\n  // Draw or drop", start + 1)
        body = _ZOOM_JS[start:end]
        assert "u.legendgroup === t.legendgroup" in body

    def test_the_double_click_isolate_is_stopped_for_a_band(self):
        # Plotly's default switches every other trace off behind the clipper's
        # back, leaving its cached state describing a figure that is gone.
        start = _ZOOM_JS.index("gd.on('plotly_legenddoubleclick'")
        end = _ZOOM_JS.index("\n    // Hide the info panel", start)
        body = _ZOOM_JS[start:end]
        assert "if (!_isBandTrace(gd.data[ev.curveNumber])) return;" in body
        assert "return false;" in body

    def test_the_button_reads_the_set_back_rather_than_remembering(self):
        # Switching one band on from the legend must not leave a label saying
        # every band is off.
        start = _ZOOM_JS.index("function _updateBandsBtn(")
        end = _ZOOM_JS.index("_updateBandsBtn();", start)
        body = _ZOOM_JS[start:end]
        assert "_bandSummary(gd)" in body
        assert "'some'" in body and "'all'" in body

    def test_a_part_switched_set_switches_all_the_way_on(self):
        # The button is the way out of a mess of individually toggled bands,
        # so anything short of all-on switches everything on.
        start = _ZOOM_JS.index("bandsBtn.addEventListener('click'")
        end = _ZOOM_JS.index("// --- Search input ---", start)
        body = _ZOOM_JS[start:end]
        assert "var on = summary.state !== 'all';" in body

    def test_a_system_swap_re_applies_the_buttons_setting(self):
        # Every figure's bands arrive on 'legendonly', so a viewer who had
        # them on would silently lose them on the next system button.
        start = _ZOOM_JS.index("window._saReattach = function")
        end = _ZOOM_JS.index("removeAllListeners", start)
        body = _ZOOM_JS[start:end]
        assert "_setAllBands(gd, _bandsOn);" in body
        assert "_bandsBtnSync();" in body, "the label has to follow the swap"

    def test_a_system_with_no_bands_says_so_rather_than_lying(self):
        # The count is checked before the flip: a label reading "Bands: On"
        # over a system that has none is worse than no button at all.
        start = _ZOOM_JS.index("// --- Bands button")
        end = _ZOOM_JS.index("// --- Search input", start)
        body = _ZOOM_JS[start:end]
        assert "if (!summary.total) {" in body
        assert "No solvent bands in this system" in body

    def test_searching_a_band_switches_on_only_that_band(self):
        # Framing a ring the viewer cannot see is not an answer to the search;
        # neither is answering it by switching on six bands nobody asked for.
        start = _ZOOM_JS.index("function doSearch(")
        end = _ZOOM_JS.index("\n    input.addEventListener", start)
        body = _ZOOM_JS[start:end]
        assert "_showBands(gd, wanted, true);" in body
        assert "_setAllBands" not in body
