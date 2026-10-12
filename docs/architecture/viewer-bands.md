# Solvent bands in the viewer — toggles, sliders, in-browser recompute

> Moved verbatim out of `CLAUDE.md` so it loads on demand. `CLAUDE.md` links here.

## The solvent bands start off

**The solvent bands start off, and two controls bring them back.** Each band
keeps its own legend entry, as every trace has; the Bands button sits on top
of them and moves the whole set, because at 1 bar the Solar System carries
seven bands and clicking seven legend entries is not a way to answer "where is
water liquid".

So the state is **per trace, not one flag**: `g.bandOn` on the geometry cache
says whether the viewer has asked for that band, whichever control asked, and
the button's label is read back off the set — `'Off'`, `'Some'`, `'On'` —
rather than remembered, so switching one band on from the legend cannot leave
it lying. Anything short of all-on switches everything on, which is what makes
the button a way *out* of a mess of individually toggled bands rather than
another one.

`_belt_trace()` gives a solvent-band mesh `meta = SOLVENT_BAND_META`
(`'solvent-band'`) and an initial `visible` of `'legendonly'`, so the figure
and the button agree on load without anything running before the first paint.
Matching the trace *name* would tie both controls to the wording of a legend
entry, which the search box also reads.

Five things hold it together, each a bug if dropped:

1. **`_showBands()` is the one writer**, for the button and the legend alike.
   Switching on hands the bands to `updateSceneVisibility()` rather than
   setting `visible: true`, because a band is usually wider than the box the
   viewer is zoomed into and a full-width ring inside a moon-sized box puts
   coordinates outside it — which is exactly what collapses the view to bare
   gridlines.
2. **A band's legend click is intercepted, and only a band's.** Plotly's own
   toggle sets `visible: true` outright, so a band switched on at depth would
   arrive unclipped; and the clipper would not know the viewer had asked for
   it, so the next zoom would drop it again. The handler returns `false` so
   Plotly does not also toggle it, and `_bandGroup()` moves the whole legend
   group — a band's two albedo margins are one entry behind two rings.
   `plotly_legenddoubleclick` is stopped for a band too: its isolate switches
   every other trace off behind the clipper's back.
3. **`updateSceneVisibility()` skips a band nobody asked for.** Without that,
   the next zoom — of which there is one on load — clips every hidden band
   straight back into view.
4. **Both directions leave the cached `state` at `'hidden'`.** The clipper
   skips a trace whose state says it is already fully drawn, so a band
   switched back on has nothing re-sent for it unless the state is reset.
5. **`_saReattach()` re-applies the button's setting.** Every figure's bands
   arrive on `'legendonly'`, so a viewer who had them on would lose them
   silently at the next system button. Per-band choices do not cross a swap: a
   different system is a different set of bands, and the button's setting is
   what a new one opens with.

## Recomputing a band in the browser

The pressure, albedo and greenhouse sliders rebuild every band's geometry in JavaScript
rather than asking Python for a new figure — a page reload per drag is not a
slider. `build_solvent_table_js()` ships the workbook's transcribed melting
and boiling points and the handful of constants the equation uses, about
1.5 kB; each band mesh carries its own star in `meta` (`solvent`, `lum`,
`normal`, `ceiling`, `colour`), which is why a system swap needs no bookkeeping
at all — the new system's traces arrive carrying the new system's star.
`colour` is the star-colour factor Python computed from the star's Teff (see
"Star colour" in `solvent-bands.md`); the viewer only multiplies `(1 - A)` by
it, so the Kopparapu fit exists once, in Python.

**The equation therefore exists twice**, in `mechanics/solvent_bands.py` and
in `viz/band_kit.js`. The kit is the one JavaScript copy: `export.py` splices
it into `_ZOOM_JS` for the Plotly viewer, and `three_viewer.py` wraps it and
exports it as `window.SABandKit` for the three.js viewer. It holds the
equation, the ring, the stacking, the slider panel (`_bandPanel`, with every
rule below), the info panel and the search ranking, so the two viewers cannot
disagree about any of them. `TestOneCopyForBothViewers` fails if either viewer
stops carrying the kit verbatim or a kit function is defined a second time. `tests/test_band_sliders.py::TestTheTwoImplementationsAgree`
runs the viewer's own functions under node and compares them to Python across
both tracks, to 1e-12 — that test is the only thing stopping the two drifting,
and a change to either side that is not made to the other shows up as a band
that jumps the first time anyone touches a slider.

Four things in `_recomputeBands()` are load-bearing:

1. **Geometry is written into the clipper's cache, not onto the trace**, and
   `updateSceneVisibility()` sends it from there. That is the same path the
   Bands button takes, and it is what keeps a recomputed band clipped: writing
   visible geometry would drop a full-width ring into a moon-sized scene box
   the moment a slider moved while someone was zoomed in.
2. **A band that loses its liquid phase is blanked**, geometry and cache
   entry both. Left alone it would keep drawing the last pressure's ring,
   which is the figure showing a band at a pressure that has none.
3. **Each band's own switch survives a drag.** The sliders move geometry, not
   visibility, so `bandOn` is carried across from the previous cache entry.
4. **The drag is coalesced per animation frame**, with the same
   `setTimeout` backstop the wheel has, because a drag emits an event per
   pixel and rebuilding eight meshes that often queues work faster than it
   retires.

The pressure track is **logarithmic** — three decades, and a linear track
would spend its first one percent on 0.1–1 bar, where half the solvents do all
of their moving — at 1000 steps per decade, which is what makes the round trip
through the track land back on the pressure the figure opened at. A coarser
track returned 1 bar as 0.998, so the legend and the slider disagreed from the
first frame. The legend name carries the pressure and is rewritten as the
slider moves, since an entry still reading "1 bar" at 40 would be the figure
lying about what it is showing.

**Each readout is also an input**, because a slider cannot be dragged to
37.4 bar on purpose and a figure meant to answer a question about one pressure
needs that pressure rather than one near it. Typing and dragging are two ways
into the same track: a typed value sets the slider position and is then read
back off it, so the slider stays the single source of truth and the two
controls cannot come to disagree. Four rules:

- **Commit on blur and on Enter, never on keystroke**, or the bands rebuild at
  1 bar on the way to typing 12. Escape puts the real value back; the arrow
  keys nudge the slider, so the box behaves like one.
- **A value past the end of the track clamps, and says so in a toast.** The
  slider cannot go past it either — but silently drawing 100 bar for someone
  who asked for 500 is the figure answering a question they did not ask.
- **Anything that is not a number restores what is actually set.** The parser
  is otherwise lenient, so "2.5 bar" lands as 2.5.
- **`_readSliders()` never writes into a box that has focus.** It runs on
  every drag and every recompute, and overwriting a half-typed number is how a
  readout that is also an input becomes unusable.

The unit sits outside the box, so what is in the box is only ever the number
it will parse back.

Searching a band by name switches on **that** band if it was off, since
framing a ring the viewer cannot see is not an answer — and neither is
answering it by switching on six bands nobody asked for. A system with no band
says so in a toast rather than flipping a label that would then be lying. The
scene extent is unchanged by the bands being off — `belt_scene_extent()` still
counts them — so switching them on never resizes the scene under the viewer.
