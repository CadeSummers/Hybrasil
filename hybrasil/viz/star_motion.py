# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Nearby Stellar Motion view: every Systems-tab star around the Sun, and where it is going.

A featured *view*, not a star system: several hundred stars at light-year
scale, fixed in place, each with an arrow for its velocity relative to the Sun
-- or, at the Galaxy Motion Type button, to the local standard of rest.
It is drawn in galactic Cartesian light years with the Sun at the origin --
+x toward the galactic centre, +y along the galaxy's rotation, +z to the north
galactic pole -- which is the frame the background Milky Way map is in, so the
sky needs no rotation at all.  See docs/architecture/star-motion.md.

The figure is built as a Plotly figure so the three.js viewer can convert it
like any other (`three_viewer.figure_to_scene`), but only the three.js viewer
shows it: `layout.meta.units` is "ly", which the Plotly viewer's AU-native
zoom does not understand.
"""

from __future__ import annotations

import math
from typing import Optional

import plotly.graph_objects as go

from ..data import star_sources
from ..data.builtin_systems import system_id_for_host
from ..mechanics.orientation import galactic_unit
from ..mechanics.units import LY_PER_YEAR_PER_KMS
from ..models.nearby import NearbyStar
from . import themes

VIEW_KEY = "nearby-star-motion"
VIEW_NAME = "Nearby Stellar Motion"

# An arrow's tip is where the star will be, relative to the Sun, after this
# many years -- so its length is exactly proportional to speed.
ARROW_YEARS = 50_000
LY_PER_KMS = ARROW_YEARS * LY_PER_YEAR_PER_KMS        # 0.16678 ly per km/s

SCENE_HALF_LY = 110.0
# The reference axes stop short of the scene edge so the pole's label stays
# in frame, clear of the button bar.
REFERENCE_LY = 90.0
# The Solar System is the focal point: drawn a little larger than a Sun-like
# star elsewhere would be.
SUN_SIZE = 11.0
LY_PER_PC = 3.261563777

# Spectral class -> (legend group, colour).  O/B/A run blue-white, F pale
# yellow, G yellow, K orange, M red; white dwarfs grey; the Sun green.
CLASS_COLOURS = {
    "O": ("O-type", "#9BB0FF"),
    "B": ("B-type", "#AABFFF"),
    "A": ("A-type", "#CAD7FF"),
    "F": ("F-type", "#FAF3C0"),
    "G": ("G-type", "#FFE24A"),
    "K": ("K-type", "#FFA040"),
    "M": ("M-type", "#FF4A3A"),
    "BD": ("Brown dwarfs", "#A0522D"),
    "WD": ("White dwarfs", "#9A9A9A"),
    "?": ("Class unknown", "#CCCCCC"),
}
SUN_NAME = "Solar System"
SUN_COLOUR = "#33DD55"
REFERENCE = (("Galactic Center", (1.0, 0.0, 0.0), "#88CCFF"),
             ("Galactic rotation", (0.0, 1.0, 0.0), "#88DDAA"),
             ("North Galactic Pole", (0.0, 0.0, 1.0), "#DDDDDD"))
MOTION_GROUP = "motion"
MOTION_TITLE = f"Motion ({ARROW_YEARS:,} yr of travel)"
DRIFT_STEPS = 200          # Play's frames over ARROW_YEARS: 10 s at the viewer's 50 ms a frame

# The Planetless 4+ Stars systems: one optional set, off until the viewer's
# Planetless Systems button turns it on.  Coloured by class like every star,
# with a white ring so they read as the other tab's, in one legend group.
PLANETLESS_SET = "planetless"
PLANETLESS_LABEL = "High Star Count Systems"
PLANETLESS_GROUP = "High star count systems (4+ stars)"
PLANETLESS_RING = "#FFFFFF"

# Every other catalogued object within 100 ly (the Known within 100ly tab's
# unplotted rows): one optional layer, off until its button turns it on.  They
# are not classified yet, so all are one purple, smaller than any classified
# star; thousands of them travel as one compact "cloud" (layout.meta.clouds)
# rather than a trace each, and the viewer draws them as one point set with one
# arrow set per motion frame.
KNOWN_SET = "known"
KNOWN_LABEL = "All Known Systems within 100 ly"
KNOWN_GROUP = "Unclassified (All Known Systems within 100 ly)"
UNCLASSIFIED_COLOUR = "#B266FF"
KNOWN_SIZE = 4.0
# Of those, the objects no curated catalog lists -- only Gaia DR3 does, and Gaia's own quality score calls their
# astrometry probably spurious (the workbook's Existence column, data/existence/).  Kept, but in their own colour
# and cloud, behind the same button.
UNCONFIRMED_KEY = "known-unconfirmed"
UNCONFIRMED_GROUP = "Existence unconfirmed (Gaia DR3 only)"
UNCONFIRMED_COLOUR = "#7FFFD4"                 # aquamarine
UNCONFIRMED_SLUG = ("Existence unconfirmed", "Only cited in Gaia DR3")
# The Known button cycles Off -> All -> Excluding unconfirmed -> Unconfirmed only -> Off.  A mode that names
# `clouds` shows only those clouds of the set; one that names none shows them all.
KNOWN_MODES = [{"key": "all", "label": "All"},
               {"key": "confirmed", "label": "Excluding unconfirmed", "clouds": [KNOWN_SET]},
               {"key": "unconfirmed", "label": "Unconfirmed only", "clouds": [UNCONFIRMED_KEY]}]
# Stand-ins for a cloud point's own ids in its link templates; the viewer swaps each point's ids in.
ID_SLOTS = {"gaia_id": "@GAIA@", "simbad_id": "@SIMBAD@", "cns5_id": "@CID@"}

# The two frames the Galaxy Motion Type button switches between.  Every arrow
# is drawn once per frame, tagged with its frame's key; the viewer shows one set.
FRAME_SUN = "sun"
FRAME_LSR = "lsr"
MOTION_FRAMES = ((FRAME_SUN, "Solar Reference"), (FRAME_LSR, "Local Standard of Rest (LSR)"))
MOTION_FRAME_TITLE = "Galaxy Motion Type"
# The Sun's own motion relative to the local standard of rest, (U, V, W) in
# km/s: Schoenrich, Binney & Dehnen 2010, MNRAS 403, 1829.  The one number the
# LSR frame adds; a star's LSR velocity is its heliocentric one plus this.
SUN_PECULIAR_KMS = (11.1, 12.24, 7.25)
SUN_PECULIAR_REF = "Schönrich, Binney & Dehnen 2010"


def spectral_kind(stellar_class: str, luminosity_class: str = "") -> str:
    """'O'..'M', 'BD' (brown dwarf), 'WD' (white dwarf) or '?'.

    From the first letter of the class once a '~' (estimated) and a subdwarf
    'sd'/'esd' prefix are stripped, so '~M5' is M, 'G5V+K1V' is G -- the
    primary -- and 'DAZ8+M4' (RR Cae) is a white dwarf.
    """
    lum = (luminosity_class or "").lower()
    if "white dwarf" in lum:
        return "WD"
    if "brown dwarf" in lum:
        return "BD"
    s = (stellar_class or "").strip().lstrip("~").strip()
    for prefix in ("esd", "sd"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    if not s:
        return "?"
    first = s[0].upper()
    if first == "D":
        return "WD"
    if first in "OBAFGKM":
        return first
    if first in "LTY":
        return "BD"
    return "?"


def spectral_colour(star: NearbyStar) -> str:
    if star.is_sun:
        return SUN_COLOUR
    return CLASS_COLOURS[spectral_kind(star.stellar_class, star.luminosity_class)][1]


def spectral_group(star: NearbyStar) -> Optional[str]:
    if star.is_sun:
        return None
    return CLASS_COLOURS[spectral_kind(star.stellar_class, star.luminosity_class)][0]


def marker_size(luminosity_sun: Optional[float]) -> float:
    """Pixels: 7 for the Sun, growing with log luminosity, clamped to 3..14."""
    if luminosity_sun is None or luminosity_sun <= 0:
        return 5.0
    return max(3.0, min(14.0, 7.0 + 2.2 * math.log10(luminosity_sun)))


def position_ly(star: NearbyStar) -> tuple[float, float, float]:
    if star.is_sun:
        return (0.0, 0.0, 0.0)
    u = galactic_unit(star.l_deg, star.b_deg)
    return tuple(star.distance_ly * c for c in u)


def velocity_kms(star: NearbyStar) -> tuple[float, float, float]:
    """Heliocentric (U, V, W) in km/s, from the speed and its direction."""
    u = galactic_unit(star.motion_l_deg, star.motion_b_deg)
    return tuple(star.speed_kms * c for c in u)


def velocity_lsr_kms(star: NearbyStar) -> tuple[float, float, float]:
    """(U, V, W) in km/s relative to the local standard of rest.

    The Sun's is its peculiar motion; any other star's is its heliocentric
    velocity plus the Sun's, since the sheet measures from a moving Sun.
    """
    if star.is_sun:
        return SUN_PECULIAR_KMS
    return tuple(v + s for v, s in zip(velocity_kms(star), SUN_PECULIAR_KMS))


def speed_and_direction(velocity) -> tuple[float, float, float]:
    """Speed in km/s and the galactic (l, b) in degrees it points toward."""
    u, v, w = velocity
    speed = math.sqrt(u * u + v * v + w * w)
    return speed, math.degrees(math.atan2(v, u)) % 360.0, math.degrees(math.asin(w / speed))


def drift_ly(star: NearbyStar) -> dict:
    """Where the star's arrow tip is from it, per motion frame: its travel in ARROW_YEARS, in light years.

    The Play button moves the star along it.  A star with no measured motion has none, and neither has the Sun in
    its own frame -- exactly the stars with no arrow.
    """
    out = {}
    for frame, _ in MOTION_FRAMES:
        if star.is_sun and frame == FRAME_SUN or not star.is_sun and not star.has_motion:
            continue
        v = velocity_lsr_kms(star) if frame == FRAME_LSR else velocity_kms(star)
        out[frame] = [round(c * LY_PER_KMS, 4) for c in v]
    return out


def arrow_points(start, velocity) -> list[tuple[float, float, float]]:
    """Base, tip, then a two-wing head drawn back through the tip, as one polyline."""
    speed = math.sqrt(sum(c * c for c in velocity))
    length = speed * LY_PER_KMS
    if length <= 0:
        return [start, start]
    d = tuple(c / speed for c in velocity)
    tip = tuple(s + length * c for s, c in zip(start, d))
    # A wing direction perpendicular to the arrow, in the plane it shares with z.
    side = (d[1], -d[0], 0.0)
    n = math.sqrt(side[0] ** 2 + side[1] ** 2)
    side = (1.0, 0.0, 0.0) if n < 1e-6 else (side[0] / n, side[1] / n, 0.0)
    head = min(0.18 * length, 2.5)
    back = tuple(t - head * c for t, c in zip(tip, d))
    wing1 = tuple(b + 0.5 * head * s for b, s in zip(back, side))
    wing2 = tuple(b - 0.5 * head * s for b, s in zip(back, side))
    return [start, tip, wing1, tip, wing2]


def _xyz(points):
    return [p[0] for p in points], [p[1] for p in points], [p[2] for p in points]


def _r(v, nd):
    return None if v is None else round(v, nd)


def _source_template(s: NearbyStar) -> list:
    """The star's Sources links with its ids replaced by ID_SLOTS, so one template serves every point that has the
    same ids present and the same Kinematics refs."""
    ids = {f: (slot if getattr(s, f) else "") for f, slot in ID_SLOTS.items()}
    return (star_sources.existence_sources(**ids)
            + star_sources.kinematics_sources(s.kinematics_refs, **ids))


def known_cloud(known: list[NearbyStar], key: str = KNOWN_SET, name: str = KNOWN_GROUP,
                colour: str = UNCLASSIFIED_COLOUR) -> dict:
    """The unclassified objects as one cloud: positions, arrows per motion frame, and compact info rows.

    `pos` and each frame's `arrows` are flat [x, y, z, ...] light years; arrows are segment pairs (base-tip and
    the two head wings), so one LineSegments draws them all.  `info[i]` is [name, distance ly, l, b, speed,
    motion l, motion b, RV, total pm mas/yr, kinematics-source index into `sources`, link-template index into
    `linkTemplates`, Gaia DR3 id, SIMBAD id, CNS5 number, existence index into `existence`]; the viewer builds the
    panel, swapping the point's ids for `idSlots` in its template.
    """
    placed = [s for s in known if s.has_position]
    pos, info, sources, templates, existence = [], [], {}, {}, {}
    arrows = {frame: [] for frame, _ in MOTION_FRAMES}
    drift = {frame: [] for frame, _ in MOTION_FRAMES}
    for s in placed:
        p = position_ly(s)
        pos += [round(c, 3) for c in p]
        d = drift_ly(s)
        for frame, _ in MOTION_FRAMES:
            drift[frame] += d.get(frame, [0.0, 0.0, 0.0])
        if s.has_motion:
            for frame, _ in MOTION_FRAMES:
                v = velocity_lsr_kms(s) if frame == FRAME_LSR else velocity_kms(s)
                a, tip, w1, _, w2 = arrow_points(p, v)
                for q in (a, tip, tip, w1, tip, w2):
                    arrows[frame] += [round(c, 2) for c in q]
        src = sources.setdefault(s.kinematics_source, len(sources))
        tmpl = _source_template(s)
        ti = templates.setdefault(repr(tmpl), (len(templates), tmpl))[0]
        ei = existence.setdefault(s.existence, len(existence))
        info.append([s.name, _r(s.distance_ly, 2), _r(s.l_deg, 2), _r(s.b_deg, 2), _r(s.speed_kms, 2),
                     _r(s.motion_l_deg, 2), _r(s.motion_b_deg, 2), _r(s.radial_velocity_kms, 2),
                     None if s.total_pm_arcsec_yr is None else round(s.total_pm_arcsec_yr * 1000, 1), src,
                     ti, s.gaia_id, s.simbad_id, s.cns5_id.replace("CNS5", "").strip(), ei])
    out = {"key": key, "name": name, "optional": KNOWN_SET, "color": colour,
           "size": KNOWN_SIZE, "motionGroup": MOTION_GROUP, "zoomHalf": 4.0, "pos": pos, "arrows": arrows,
           "drift": drift, "info": info, "sources": list(sources), "sunPeculiar": list(SUN_PECULIAR_KMS),
           "linkTemplates": [t for _, t in sorted(templates.values(), key=lambda x: x[0])],
           "idSlots": dict(zip(("gaia", "simbad", "cns5"), ID_SLOTS.values())),
           "existence": list(existence),
           "lyPerKms": LY_PER_KMS, "arrowYears": ARROW_YEARS,
           "moving": sum(1 for s in placed if s.has_motion)}
    if key == UNCONFIRMED_KEY:
        out["slug"] = list(UNCONFIRMED_SLUG)
    return out


def known_clouds(known: list[NearbyStar]) -> list[dict]:
    """The Known layer as two clouds: what a curated catalog lists (purple), and what only Gaia DR3 does
    (aquamarine).  An empty one is left out."""
    sure = [s for s in known if not s.existence_unconfirmed]
    doubt = [s for s in known if s.existence_unconfirmed]
    clouds = [known_cloud(sure), known_cloud(doubt, UNCONFIRMED_KEY, UNCONFIRMED_GROUP, UNCONFIRMED_COLOUR)]
    return [c for c in clouds if c["info"]]


def build_star_motion_figure(stars: list[NearbyStar], source: str = "",
                             planetless: tuple = (), known: tuple = ()) -> go.Figure:
    """The view's figure: `stars` from the Systems tab, `planetless` systems and the `known` (unclassified)
    objects each behind their own button."""
    traces = []
    # The Sun first, then O -> M, brown and white dwarfs: the legend lists
    # classes in the order it first meets them.  The planetless systems last,
    # so their one group row follows the classes.
    rank = {k: i for i, k in enumerate(CLASS_COLOURS)}
    placed = sorted((s for s in stars if s.has_position),
                    key=lambda s: (not s.is_sun,
                                   rank[spectral_kind(s.stellar_class, s.luminosity_class)]))
    taken = {s.name for s in placed}
    extra = [s for s in planetless if s.has_position and s.name not in taken]
    for s in extra:
        x, y, z = position_ly(s)
        traces.append(go.Scatter3d(
            x=[x], y=[y], z=[z], mode="markers", name=s.name,
            marker=dict(size=marker_size(s.luminosity_sun), color=spectral_colour(s),
                        line=dict(width=1.5, color=PLANETLESS_RING)),
            showlegend=False, hoverinfo="name",
            legendgroup=PLANETLESS_GROUP, legendgrouptitle=dict(text=PLANETLESS_GROUP),
            meta={"optional": PLANETLESS_SET, "drift": drift_ly(s)},
        ))
    planetless_traces, traces = traces, []
    placed_all = placed + extra
    for s in placed:
        x, y, z = position_ly(s)
        colour = spectral_colour(s)
        trace = go.Scatter3d(
            x=[x], y=[y], z=[z],
            mode="markers+text" if s.is_sun else "markers",
            name=SUN_NAME if s.is_sun else s.name,
            text=[SUN_NAME] if s.is_sun else None,
            marker=dict(size=SUN_SIZE if s.is_sun else marker_size(s.luminosity_sun), color=colour,
                        line=dict(width=0)),
            showlegend=s.is_sun,
            hoverinfo="name",
            meta={"drift": drift_ly(s)},
        )
        group = spectral_group(s)
        if group:
            trace.update(legendgroup=group, legendgrouptitle=dict(text=group))
        traces.append(trace)
    traces += planetless_traces

    # One arrow per star per frame.  Relative to the Sun, the Sun has none; in
    # the LSR frame it has its own, green like its marker.  A planetless
    # system's arrows are owned by its marker, so they hide with it.
    for frame, _ in MOTION_FRAMES:
        for s in placed_all:
            if s.is_sun and frame == FRAME_SUN or not s.is_sun and not s.has_motion:
                continue
            v = velocity_lsr_kms(s) if frame == FRAME_LSR else velocity_kms(s)
            xs, ys, zs = _xyz(arrow_points(position_ly(s), v))
            name = SUN_NAME if s.is_sun else s.name
            traces.append(go.Scatter3d(
                x=xs, y=ys, z=zs, mode="lines",
                name=f"{name} motion" + (" (LSR)" if frame == FRAME_LSR else ""),
                line=dict(color=spectral_colour(s), width=3 if s.is_sun else 2),
                opacity=1.0 if s.is_sun else 0.7,
                showlegend=False, hoverinfo="skip",
                legendgroup=MOTION_GROUP, legendgrouptitle=dict(text=MOTION_TITLE),
                meta={"owner": name, "frame": frame},
            ))

    for name, axis, colour in REFERENCE:
        tip = tuple(REFERENCE_LY * c for c in axis)
        traces.append(go.Scatter3d(
            x=[0, tip[0]], y=[0, tip[1]], z=[0, tip[2]], mode="lines+text",
            name=name, text=["", name], line=dict(color=colour, width=2, dash="dash"),
            opacity=0.6, showlegend=True, hoverinfo="skip",
        ))

    n_moving = sum(1 for s in placed if s.has_motion and not s.is_sun)
    n_systems = sum(1 for s in placed if not s.is_sun)
    clouds = known_clouds(list(known)) if known else []
    n_known = sum(len(c["info"]) for c in clouds)
    n_doubt = sum(len(c["info"]) for c in clouds if c["key"] == UNCONFIRMED_KEY)
    title = (f"{VIEW_NAME} — {n_systems} systems within 100 ly, {n_moving} with a "
             f"measured motion" + (f" (+{len(extra)} high star count systems on request)" if extra else "")
             + (f" (+{n_known:,} unclassified objects on request)" if n_known else "")
             + f" · velocity relative to the Sun or the LSR · arrow = "
             f"{ARROW_YEARS:,} yr of travel" + (f" · {source}" if source else ""))
    fig = go.Figure(data=traces)
    h = SCENE_HALF_LY
    meta = {"units": "ly", "view": VIEW_KEY, "group_heading": "Stars by spectral class",
            "sky": {"galactic_to_frame": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
            "motion_frames": {"title": MOTION_FRAME_TITLE, "default": FRAME_SUN,
                              "options": [{"key": k, "label": lbl} for k, lbl in MOTION_FRAMES]},
            # Play moves every star along its arrow: the arrow's ARROW_YEARS in DRIFT_STEPS frames.
            "drift": {"years": ARROW_YEARS, "steps": DRIFT_STEPS}}
    if extra:
        # A set of bodies the viewer offers behind a button, off until asked for.
        meta["optional_sets"] = [{"key": PLANETLESS_SET, "label": PLANETLESS_LABEL, "default": False,
                                  "count": len(extra),
                                  "title": "Add the systems of the workbook's Planetless 4+ Stars tab: "
                                           "hierarchies of stars with no known planet but, for some, brown "
                                           "dwarfs, which this model counts as planets"}]
    if n_known:
        meta.setdefault("optional_sets", []).append({
            "key": KNOWN_SET, "label": KNOWN_LABEL, "default": False, "count": n_known,
            "title": "Add every other catalogued object within 100 ly (the workbook's Known within 100ly tab), "
                     f"not yet classified, in purple; {sum(c['moving'] for c in clouds):,} have a measured space "
                     "velocity and an arrow, the rest a dot"
                     + (f". {n_doubt:,} in aquamarine are listed only by Gaia DR3, whose astrometry for them is "
                        "probably spurious: existence unconfirmed. Click again to leave them out, again for "
                        "them alone, again for off" if n_doubt else "")})
        if n_doubt and n_doubt < n_known:
            meta["optional_sets"][-1]["modes"] = KNOWN_MODES
        meta["clouds"] = clouds
    fig.update_layout(
        title=dict(text=title, font=dict(color=themes.FONT_COLOR, size=16)),
        scene=themes.make_scene_style(h, h, h),
        meta=meta,
        **themes.LAYOUT_DEFAULTS,
    )
    return fig


# ── the info panel ──────────────────────────────────────────────────────────

def _num(v, fmt, unit="", none="no data"):
    return none if v is None else f"{format(v, fmt)}{unit}"


def _missing_motion(s: NearbyStar) -> str:
    gaps = [what for what, v in (("radial velocity", s.radial_velocity_kms),
                                 ("proper motion", s.total_pm_arcsec_yr)) if v is None]
    return "no " + " or ".join(gaps) + " on file" if gaps else "not computed"


def star_rows(s: NearbyStar) -> list[list]:
    """[label, value, note] rows for one star's info panel."""
    rows = []
    if s.nickname:
        rows.append(["Name", s.nickname, ""])
    cls = s.stellar_class or "no data"
    rows.append(["Spectral type", cls + (f" ({s.luminosity_class})" if s.luminosity_class else ""), ""])
    if s.planetless:
        # A brown dwarf is a planet in this model (7 Oct 2026): the tab's systems keep their stars there and
        # their brown dwarfs on the planet tabs.
        worlds = (f"{s.n_planets} planet{'s' if s.n_planets > 1 else ''} (brown dwarf"
                  f"{'s' if s.n_planets > 1 else ''})" if s.n_planets else "no known planet")
        rows.append(["System", f"{len(s.partners) + 1} stars, {worlds}",
                     "Planetless 4+ Stars tab; position and motion are its host star's"])
    if s.is_sun:
        rows.append(["Position", "the origin", "every position is measured from here"])
        speed, l, b = speed_and_direction(velocity_lsr_kms(s))
        rows += [
            ["Speed (LSR)", f"{speed:.2f} km/s", "relative to the local standard of rest"],
            ["Direction (LSR)", f"toward l {l:.2f}°, b {b:+.2f}°", "the solar apex"],
            ["U, V, W (LSR)", ", ".join(f"{c:+.2f}" for c in SUN_PECULIAR_KMS) + " km/s",
             SUN_PECULIAR_REF],
        ]
    else:
        rows.append(["Distance", _num(s.distance_ly, ".2f", " ly")
                     + ("" if s.distance_ly is None else f" ({s.distance_ly / LY_PER_PC:.2f} pc)"), ""])
        rows.append(["Galactic position", "no data" if s.l_deg is None else
                     f"l {s.l_deg:.2f}°, b {s.b_deg:+.2f}°", ""])
        if s.has_motion:
            u, v, w = velocity_kms(s)
            lsr, l_lsr, b_lsr = speed_and_direction(velocity_lsr_kms(s))
            rows += [
                ["Speed", f"{s.speed_kms:.2f} km/s", "relative to the Sun"],
                ["Direction of motion", f"toward l {s.motion_l_deg:.2f}°, b {s.motion_b_deg:+.2f}°", ""],
                ["U, V, W", f"{u:+.1f}, {v:+.1f}, {w:+.1f} km/s",
                 "toward the galactic centre, along rotation, to the north pole"],
                ["Speed (LSR)", f"{lsr:.2f} km/s", "relative to the local standard of rest"],
                ["Direction (LSR)", f"toward l {l_lsr:.2f}°, b {b_lsr:+.2f}°", ""],
                [f"Travel in {ARROW_YEARS:,} yr", f"{s.speed_kms * LY_PER_KMS:.2f} ly"
                 f" ({lsr * LY_PER_KMS:.2f} ly LSR)", "the arrow's length"],
            ]
        else:
            rows.append(["Speed", "no data", _missing_motion(s)])
        rows.append(["Radial velocity", _num(s.radial_velocity_kms, "+.2f", " km/s"),
                     "" if s.radial_velocity_kms is None else "positive = receding"])
        rows.append(["Proper motion", "no data" if s.total_pm_arcsec_yr is None
                     else f"{s.total_pm_arcsec_yr * 1000:.1f} mas/yr", ""])
    rows += [
        ["Age", _num(s.age_gyr, ".2f", " Gyr"), ""],
        ["Mass", _num(s.mass_sun, ".3f", " M☉"), ""],
        ["Metallicity [Fe/H]", _num(s.metallicity, "+.2f"), ""],
        ["Luminosity", _num(s.luminosity_sun, ".4g", " L☉"), ""],
        ["Stellar partners", ", ".join(s.partners) if s.partners else "none on file", ""],
    ]
    cand = [p for p in s.planets if p.endswith(" candidate)")]
    conf = len(s.planets) - len(cand)
    if s.planets:
        count = f"{conf} confirmed" + (f", {len(cand)} candidate" if cand else "")
        rows.append(["Planets", f"{count}: {', '.join(s.planets)}", ""])
    else:
        rows.append(["Planets", "none on file" if not s.n_planets else str(s.n_planets), ""])
    if s.kinematics_source and not s.is_sun:
        rows.append(["Kinematics source", s.kinematics_source, ""])
    return rows


def star_motion_info(stars: list[NearbyStar]) -> dict:
    """Body name -> info-panel entry, keyed as the figure names the markers.

    `goto` is the id of the star's own system, for the panel's "Go to system"
    button; the viewer shows the button only where it can open that id.
    """
    return {(SUN_NAME if s.is_sun else s.name): {"rows": star_rows(s), "zoom_half": 4.0,
                                                 "goto": s.system_id or system_id_for_host(s.name),
                                                 "sources": s.sources}
            for s in stars if s.has_position}
