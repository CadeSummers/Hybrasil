# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A three.js renderer for the same figures the Plotly viewer draws.

The default viewer since it gained every feature the Plotly viewer has;
``--renderer plotly`` opens the original, and PNG export still goes through
Plotly.

Why a second renderer.  Plotly's gl3d scene sets WebGL's near plane as a fixed
fraction of its axis box, so a camera that dollies in has to drag the box in
with it, and every re-cut of the box re-normalises and re-uploads every trace
(~50 ms, measured) -- the scroll-zoom stutter, and the reason zooming is a
state machine of sticky boxes and locks (docs/architecture/zoom-and-visibility.md).
three.js with a *logarithmic depth buffer* has no such box: depth precision is
spread over the whole range, so one camera covers 1e-6 AU to 1e4 AU and a zoom
is a camera move -- nothing is re-uploaded, and OrbitControls' damping turns
wheel steps into continuous motion.

The scene is converted from the Plotly figure Python already builds rather
than built a second time, so both renderers draw identical geometry: the same
orbit samples, the same coils, the same band vertices and faces.  A solvent
band is therefore a flat disc here for the same reason it is one in Plotly --
it is the same mesh -- and `tests/test_three_viewer.py` pins that the vertices
survive the conversion unchanged.
"""

from __future__ import annotations

import base64
import json
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional

import plotly.graph_objects as go

from . import photosynthesis_rings, reference_orbits
from .export import BAND_KIT_JS
from .static_plot import SOLVENT_BAND_META

# Pinned, so a three.js release cannot change the viewer under us.  Loaded
# from jsDelivr like Plotly is loaded from its CDN.
THREE_VERSION = "0.186.0"
_THREE_CDN = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}"

_JS_PATH = Path(__file__).with_name("three_viewer.js")
# The About panel's content: author, citation, licences, credits (a file of
# its own so a DOI or a support handle is added without touching code).
ABOUT_PATH = Path(__file__).resolve().parents[1] / "about.json"


def about() -> dict:
    data = json.loads(ABOUT_PATH.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data

_SEARCH_JS_PATH = Path(__file__).with_name("system_search.js")

# The background Milky Way (hybrasil/viz/sky/README.md).  The web app
# serves the 4k image as a file; a standalone page embeds the 2k one, which is
# ~0.75 MB of base64 rather than ~3.4 MB.
SKY_DIR = Path(__file__).with_name("sky")
SKY_FILE = "milky_way_4k.jpg"
SKY_EMBED_FILE = "milky_way_2k.jpg"
SKY_URL = f"/sky/{SKY_FILE}"


# The intro (hybrasil/web/intro/README.md): a map per screen shape, shown on
# arrival by the web app only.  Its files are served under /intro/ and copied
# to the static site's intro/.
INTRO_DIR = Path(__file__).parent.parent / "web" / "intro"
INTRO_URL = "/intro/"


def intro_files() -> list[str]:
    """Every file the intro serves: each slide's image."""
    path = INTRO_DIR / "intro.json"
    if not path.exists():
        return []
    slides = json.loads(path.read_text(encoding="utf-8"))["slides"]
    return [s["image"] for s in slides]


def intro_config(base: str = INTRO_URL) -> Optional[dict]:
    """intro.json with its file names as URLs under `base`, or None without it."""
    path = INTRO_DIR / "intro.json"
    if not path.exists():
        return None
    slides = json.loads(path.read_text(encoding="utf-8"))["slides"]
    return {"slides": [dict(s, image=base + s["image"]) for s in slides]}


# The intro's first paint: its overlay, styled and filled in before the
# three.js module (and the CDN it imports from) has loaded.  It plays on an
# arrival -- a link, a typed or searched URL -- and never on a reload or
# back/forward; ?intro=0 turns it off (the browser tests).  SA3_ARRIVED is
# what opens a random body (three_viewer.js, "Intro"), with or without the map:
# reduced motion skips only the map.  The slide is the one whose shape is
# nearest the window's, on a log scale.  The whole map fades as one over
# 1.25 s: to 90% opacity by 0.25 s, 50% by 1 s, gone at 1.25 s.  A browser
# without linear() easing keeps the cubic-bezier, an ease-in close to it.
_INTRO_CSS = """
  #sa3-intro { position: fixed; inset: 0; z-index: 100000; cursor: pointer;
               background-size: cover; background-position: center;
               background-repeat: no-repeat;
               transition: opacity 1.25s cubic-bezier(0.5, 0, 0.75, 0);
               transition-timing-function: linear(0, 0.1 20%, 0.5 80%, 1); }
  #sa3-intro.sa3-intro-out { opacity: 0; }
"""
_INTRO_PICK = """
(function () {
  var el = document.getElementById('sa3-intro'), cfg = window.SA3_INTRO;
  var arrived = false, off = /(^|[?&])intro=0(&|$)/.test(location.search), still = false;
  try {
    var nav = performance.getEntriesByType('navigation')[0];
    arrived = nav ? nav.type === 'navigate' : !sessionStorage.getItem('sa3.system');
  } catch (e) { arrived = true; }
  try { still = matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}
  window.SA3_ARRIVED = arrived && !off;
  window.SA3_INTRO_PLAY = null;
  if (!window.SA3_ARRIVED || still || !cfg || !cfg.slides.length) { el.remove(); return; }
  var aspect = Math.log(innerWidth / Math.max(innerHeight, 1)), slide = cfg.slides[0];
  cfg.slides.forEach(function (s) {
    if (Math.abs(Math.log(s.width / s.height) - aspect)
        < Math.abs(Math.log(slide.width / slide.height) - aspect)) slide = s;
  });
  var img = new Image();
  el.style.backgroundColor = slide.colour;
  window.SA3_INTRO_PLAY = slide;
  // Shown once the image is in, so the 1.5 s on the map are 1.5 s of map
  // rather than of plain tan.
  window.SA3_INTRO_SHOWN = new Promise(function (resolve, reject) {
    img.onload = function () {
      el.style.backgroundImage = 'url("' + slide.image + '")';
      resolve(performance.now());
    };
    img.onerror = function () { reject(new Error('intro image')); };
    img.src = slide.image;
  });
  window.SA3_INTRO_SHOWN.catch(function () {});
})();
"""


def _intro_html(intro: Optional[dict]) -> tuple[str, str]:
    """The intro's <style> rules and its <body> markup, both empty without one."""
    if not intro:
        return "", ""
    return _INTRO_CSS, ('<div id="sa3-intro" aria-hidden="true"></div>\n'
                        f"<script>\nwindow.SA3_INTRO = {_script_json(intro)};\n{_INTRO_PICK}</script>\n")


def sky_data_uri() -> Optional[str]:
    """The 2k sky as a data: URI, or None if the image is missing."""
    path = SKY_DIR / SKY_EMBED_FILE
    if not path.exists():
        return None
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _floats(values) -> list[float]:
    return [float(v) for v in values]


def _flat(xs, ys, zs) -> list[float]:
    """x0, y0, z0, x1, ... -- the layout a BufferGeometry position array takes."""
    out: list[float] = []
    for x, y, z in zip(xs, ys, zs):
        out += (float(x), float(y), float(z))
    return out


def _arr(values):
    # Plotly hands back numpy arrays, whose truth value is ambiguous.
    return [] if values is None else values


def _transparent(color) -> bool:
    """A Plotly colour with zero alpha, as hypothetical bodies are filled."""
    if not color:
        return True
    c = str(color).replace(" ", "").lower()
    return c == "transparent" or (c.startswith("rgba(") and c.rstrip(")").endswith(",0"))


def _is_marker(trace) -> bool:
    return (trace.type == "scatter3d" and trace.mode is not None
            and "markers" in trace.mode and trace.x is not None
            and len(trace.x) == 1)


def _group_title(trace) -> str:
    title = trace.legendgrouptitle.text if trace.legendgrouptitle else None
    return title or trace.legendgroup


def figure_to_scene(fig: go.Figure) -> dict:
    """Everything the three.js viewer draws, lifted out of a Plotly figure.

    Returns a JSON-ready dict: ``lines`` (orbits, coils, reference arrows),
    ``bodies`` (one marker each), ``bands`` (solvent bands and belts, as
    indexed meshes), ``frames`` (body positions over time), and the scene's
    half-width and camera.
    """
    lines, bodies, bands = [], [], []
    body_of_trace: dict[int, int] = {}

    for i, t in enumerate(fig.data):
        if t.type == "scatter3d" and _is_marker(t):
            marker = t.marker
            border = marker.line.width if marker.line and marker.line.width else 0
            # A hypothetical or candidate body is a hollow ring in Plotly:
            # transparent fill, coloured edge.  Taking `marker.color` alone
            # drew those as black dots on a black sky -- invisible.
            fill = None if _transparent(marker.color) else marker.color
            edge = marker.line.color if border else None
            body_of_trace[i] = len(bodies)
            bodies.append({
                "name": t.name,
                "color": fill or edge or "#cccccc",
                "fill": fill,
                "edge": edge,
                "size": float(marker.size or 8),
                "border": float(border),
                "label": bool(t.mode and "text" in t.mode),
                # Whether Plotly lists it in the legend, so the three.js
                # legend lists the same entries.
                "legend": t.showlegend is not False,
                "pos": [float(t.x[0]), float(t.y[0]), float(t.z[0])],
            })
            # A body in a legend group is listed once per group, not by name
            # (the Nearby Stellar Motion view: one row per spectral class).
            if t.legendgroup:
                bodies[-1]["group"] = t.legendgroup
                bodies[-1]["groupTitle"] = _group_title(t)
            bmeta = t.meta if isinstance(t.meta, dict) else {}
            if bmeta.get("optional"):
                # One of the scene's optional sets (optionalSets): shown only
                # while that set's button is on, with the lines it owns.
                bodies[-1]["optional"] = bmeta["optional"]
            if bmeta.get("drift"):
                # A view's star: where Play carries it, per motion frame (star_motion.drift_ly).
                bodies[-1]["drift"] = bmeta["drift"]
        elif t.type == "scatter3d" and t.mode and "lines" in t.mode \
                and t.x is not None and len(t.x) > 1:
            line = t.line
            text = list(t.text) if t.text is not None else []
            lines.append({
                "name": t.name,
                "color": line.color if line else "#888888",
                "width": float(line.width or 1) if line else 1.0,
                "dash": (line.dash or "solid") if line else "solid",
                "opacity": float(t.opacity if t.opacity is not None else 1.0),
                "pts": _flat(t.x, t.y, t.z),
                # A reference arrow labels its far end.
                "label": next((s for s in reversed(text) if s), ""),
                "legend": bool(t.showlegend),
            })
            meta = t.meta if isinstance(t.meta, dict) else {}
            if t.legendgroup:
                lines[-1]["group"] = t.legendgroup
                lines[-1]["groupTitle"] = _group_title(t)
            if meta.get("owner"):
                # The body this line belongs to, hidden with it from the legend.
                lines[-1]["owner"] = meta["owner"]
            if meta.get("frame"):
                # Which motion frame the line is drawn in; see motionFrames.
                lines[-1]["frame"] = meta["frame"]
            if meta.get("follows"):
                # A moon's orbit: moved with this body every frame.
                lines[-1]["follows"] = meta["follows"]
        elif t.type == "mesh3d":
            meta = t.meta if isinstance(t.meta, dict) else {}
            bands.append({
                "name": t.name,
                "color": t.color,
                "opacity": float(t.opacity if t.opacity is not None else 0.2),
                "pos": _flat(_arr(t.x), _arr(t.y), _arr(t.z)),
                "index": _flat(_arr(t.i), _arr(t.j), _arr(t.k)),
                "solvent": meta.get("kind") == SOLVENT_BAND_META,
                # What the sliders recompute the ring from: the same meta the
                # Plotly trace carries (solvent, star luminosity, plane,
                # centre, ceiling, colour factor).
                "meta": meta if meta.get("kind") == SOLVENT_BAND_META else None,
                # The star a solvent band rings: moved with it every frame.
                "follows": meta.get("body") or None,
                "group": t.legendgroup or t.name,
                "legend": t.showlegend is not False,
                "visible": t.visible is not False and t.visible != "legendonly",
            })
        # Cones (the reference arrows' heads) are left out: the line and its
        # label carry the information.

    # The photosynthesis rings travel on the layout meta, not as traces
    # (photosynthesis_rings.py): three.js draws them, Plotly never sees them.
    lines.extend(photosynthesis_rings.scene_lines(
        fig.layout.meta if isinstance(fig.layout.meta, dict) else None))
    # So do the reference orbits (reference_orbits.py): Neptune's, Earth's and Mercury's round every star.
    lines.extend(reference_orbits.scene_lines(
        fig.layout.meta if isinstance(fig.layout.meta, dict) else None))

    frames = {"names": [], "positions": []}
    for fr in fig.frames or ():
        pos = [list(b["pos"]) for b in bodies]
        for ti, d in zip(fr.traces or (), fr.data):
            b = body_of_trace.get(ti)
            if b is not None and d.x is not None and len(d.x):
                pos[b] = [float(d.x[0]), float(d.y[0]), float(d.z[0])]
        frames["positions"].append([c for p in pos for c in p])
        frames["names"].append(str(fr.name))

    # Date labels come from the animation slider, one step per frame.
    labels = []
    if fig.layout.sliders:
        labels = [str(s.label) for s in fig.layout.sliders[0].steps]
    frames["labels"] = labels

    # The rotation that hangs the Milky Way behind this system (sky_meta()).
    meta = fig.layout.meta if isinstance(fig.layout.meta, dict) else {}
    scene = fig.layout.scene
    half = max(abs(float(v)) for v in
               list(scene.xaxis.range) + list(scene.yaxis.range)
               + list(scene.zaxis.range))
    cam = scene.camera
    return {
        "title": fig.layout.title.text or "",
        "background": scene.bgcolor or fig.layout.paper_bgcolor or "#070714",
        "half": half,
        "eye": [float(cam.eye.x), float(cam.eye.y), float(cam.eye.z)],
        "up": [float(cam.up.x), float(cam.up.y), float(cam.up.z)],
        "lines": lines,
        "bodies": bodies,
        "bands": bands,
        "frames": frames,
        # Each orbiting body's elements and the frames' time span, so a body
        # between two frames is placed on its orbit (kepler_meta()); None for a
        # static figure or a view, which interpolate between frames.
        "kepler": meta.get("kepler"),
        "sky": meta.get("sky"),
        # Scene units: AU for every star system, light years for a view.
        "units": meta.get("units", "AU"),
        # The legend heading over grouped bodies, when a figure has groups.
        "groupHeading": meta.get("group_heading"),
        # Alternative frames for the owned lines, and the button that picks
        # one ({title, default, options: [{key, label}]}); None for a system.
        "motionFrames": meta.get("motion_frames"),
        # Sets of bodies or lines offered behind a button each, off by default
        # ([{key, label, default, count, title, menu?}]); a set with
        # menu "features" is a row of the Even more features menu instead.
        "optionalSets": meta.get("optional_sets"),
        # Many points drawn as one object each, with arrows per motion frame
        # and compact info rows (star_motion.known_cloud); [] for a system.
        "clouds": meta.get("clouds") or [],
        # A view whose stars Play moves along their arrows ({years, steps}); None for a system.
        "drift": meta.get("drift"),
    }


# What the three.js viewer uses from band_kit.js.  The kit is written as bare
# function declarations for the Plotly viewer's IIFE; here it gets an IIFE of
# its own and this export list.
_KIT_EXPORTS = {
    "bandConst": "_bandConst", "bandRadiiAU": "_bandRadiiAU",
    "bandName": "_bandName", "ringMesh": "_ringMesh",
    "stackOffsetsByCentre": "_stackOffsetsByCentre",
    "nameMatches": "_nameMatches", "bandPanel": "_bandPanel",
    "showInfoPanel": "showInfoPanel", "hideInfoPanel": "hideInfoPanel",
    "setInfoGoto": "setInfoGoto", "setInfoSuggest": "setInfoSuggest",
}


def suggest_script() -> str:
    """The Suggest Changes rules and their validator, for the form in the page.

    web/suggest_validate.js is an ES module, because the Cloudflare function
    imports it; the page gets the same text as a classic script, its `export`
    keywords stripped, so there is one copy of the checks
    (docs/architecture/suggestions.md).
    """
    from ..web.suggestions import RULES, VALIDATE_JS_PATH
    js = VALIDATE_JS_PATH.read_text(encoding="utf-8").replace("export function ", "function ")
    return ("(function () {\n" + js
            + f"\n  window.SASuggest = {{validate: validate, rules: {_script_json(RULES)}}};\n}})();\n")


def kit_script() -> str:
    """band_kit.js, verbatim, as a classic script exporting window.SABandKit."""
    exports = ", ".join(f"{k}: {v}" for k, v in _KIT_EXPORTS.items())
    return ("(function () {\n" + BAND_KIT_JS
            + f"\n  window.SABandKit = {{{exports}}};\n}})();\n")


def _script_json(value) -> str:
    # "</" inside a <script> block would end it early.
    return json.dumps(value, separators=(",", ":")).replace("</", "<\\/")


def _page(systems: dict, labels: dict, kinds: dict, initial: str, extra_js: str,
          api_base: Optional[str], title: str, sky: Optional[str],
          index_url: Optional[str] = None, suggest_url: Optional[str] = None,
          turnstile_sitekey: Optional[str] = None, head: str = "",
          intro: Optional[dict] = None) -> str:
    intro_css, intro_body = _intro_html(intro)
    importmap = {"imports": {
        "three": f"{_THREE_CDN}/build/three.module.js",
        "three/addons/": f"{_THREE_CDN}/examples/jsm/",
    }}
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{head}<style>
  html, body {{ margin: 0; height: 100%; background: #07071a; overflow: hidden;
               font-family: monospace; color: #ccccee; }}
  #sa3-root {{ position: absolute; inset: 0; }}{intro_css}
</style>
<script type="importmap">{json.dumps(importmap)}</script>
</head>
<body>
<div id="sa3-root"></div>
{intro_body}<script>
window.SA3_SYSTEMS = {_script_json(systems)};
window.SA3_LABELS  = {_script_json(labels)};
window.SA3_KINDS   = {_script_json(kinds)};
window.SA3_INITIAL = {_script_json(initial)};
window.SA3_API     = {_script_json(api_base)};
window.SA3_INDEX_URL = {_script_json(index_url)};
window.SA3_SKY     = {_script_json(sky)};
window.SA3_SUGGEST_URL = {_script_json(suggest_url)};
window.SA3_TURNSTILE_SITEKEY = {_script_json(turnstile_sitekey)};
window.SA3_ABOUT   = {_script_json(about())};
{extra_js}
</script>
<script>
{kit_script()}
</script>
<script>
{suggest_script()}
</script>
<script>
{_SEARCH_JS_PATH.read_text(encoding="utf-8")}
</script>
<script type="module">
{_JS_PATH.read_text(encoding="utf-8")}
</script>
</body>
</html>
"""


def build_html(figures: dict, initial: str, labels: Optional[dict] = None,
               extra_js: str = "") -> str:
    """One self-contained page holding every system in `figures`.

    `extra_js` is the same constants block the Plotly viewer gets
    (`_SA_BODY_INFO` and the solvent table); the three.js viewer reads its
    double-click framing from `_SA_BODY_INFO`.  The More Modeled Systems search
    covers only what is in the file; `--serve` opens the whole catalog.
    """
    from ..data.builtin_systems import FEATURED_LABELS
    from ..views import system_kind
    systems = {key: figure_to_scene(fig) for key, fig in figures.items()}
    labels = labels or {key: FEATURED_LABELS.get(key) or (s["title"].split(" — ")[0] or key)
                        for key, s in systems.items()}
    # Which System Type the dropdown lists each under; the web app's index
    # carries its own.
    kinds = {key: system_kind(key) for key in systems}
    return _page(systems, labels, kinds, initial, extra_js, None,
                 systems[initial]["title"] or "Hybrasil Star and Exoplanet Map", sky_data_uri())


def build_app_html(initial: str, extra_js: str = "", api_base: str = "/api",
                   index_url: Optional[str] = None, sky: str = SKY_URL,
                   suggest_url: Optional[str] = None,
                   turnstile_sitekey: Optional[str] = None, head: str = "",
                   intro: Optional[dict] = None) -> str:
    """The web app's shell: no systems in it, everything fetched from `api_base`.

    `initial` is the system id opened first -- a featured key or
    ``catalog:<host>``, as `/api/systems` lists them.  The static site
    (web/static_site.py) passes relative URLs, so the page works under any
    path: `index_url` is its systems.json, and each index entry carries the
    `url` of its own scene file.  `suggest_url` is where Suggest Changes
    posts (no button without one), and `turnstile_sitekey` the hosted site's
    bot check (web/suggestions.py).  `head` is added to the page's <head>:
    the web app's description and JSON-LD (web/discovery.py).  `intro` is
    `intro_config()`'s, for the map shown on arrival; none, no intro.
    """
    return _page({}, {}, {}, initial, extra_js, api_base, "Hybrasil Star and Exoplanet Map", sky,
                 index_url, suggest_url, turnstile_sitekey, head, intro)


def save_three_html(figures: dict, initial: str, path: str,
                    extra_js: str = "") -> str:
    Path(path).write_text(build_html(figures, initial, extra_js=extra_js),
                          encoding="utf-8")
    return path


def show_three_in_browser(figures: dict, initial: str, extra_js: str = "") -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    tmp.close()
    save_three_html(figures, initial, tmp.name, extra_js=extra_js)
    _open_in_browser(tmp.name)
    return tmp.name


def _open_in_browser(path: str) -> None:
    webbrowser.open(Path(path).resolve().as_uri())
