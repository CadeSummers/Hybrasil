# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Hybrasil Star and Exoplanet Map web app: the three.js viewer, every system on demand.

    python -m hybrasil.cli --serve

The page asks this server for what it needs, so nothing is built until
someone looks at it:

    GET /                      the viewer shell (no systems in it)
    GET /api/systems           every system the search box can find
    GET /api/systems/<id>      one system's scene and info-panel data
    POST /api/suggestions      record a Suggest Changes submission (suggestions.py)

Featured systems are the literature-built ones in builtin_systems; the rest
come from the catalog workbook -- its planet systems, and every hierarchy of
four or more stars on its Planetless 4+ Stars tab (planetless_loader), listed
under the High Star Count (Planetless) type only -- and the S-stars round Sgr A*
on its Sgr A* S-stars tab (sgr_a_loader), under Stellar Motion as the Sgr A* Cluster (Galactic Center).  A catalog host that a featured system already
covers (FEATURED_CATALOG_HOSTS) is folded into it, so each system is listed
once.  Scenes are built the first time they are asked for and cached for the
life of the process.

The same API is what a hosted deployment would serve: the page does not care
whether it came from localhost.  The catalog credential stays on the server --
the browser only ever receives built scenes.  Standard library only, so
serving needs nothing beyond what the CLI already requires.
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import unquote, urlparse

from ..data.builtin_systems import (
    BODY_METADATA,
    BUILTIN_NAMES,
    CATALOG_PREFIX,
    FEATURED_ALIASES,
    FEATURED_CATALOG_HOSTS,
    FEATURED_LABELS,
    get_builtin_system,
)
from ..data.planetless_loader import (PREFIX as PLANETLESS_PREFIX, build_planetless_system,
                                      load_planetless, planetless_entry, planetless_span_days)
from ..data.sgr_a_loader import (SYSTEM_ID as SGR_A_ID, build_sgr_a_system, load_sgr_a, sgr_a_entry,
                                 sgr_a_span_days)
from ..figures import _NATURAL_SPANS, _natural_span_days, build_figure
from ..mechanics.solvent_bands import SolventChoice
from ..views import FEATURED_VIEWS, build_view, system_kind
from ..mechanics.units import jd_now
from ..viz.export import build_body_info, build_solvent_table_js
from ..viz.three_viewer import (SKY_DIR, SKY_FILE, SKY_URL, build_app_html,
                                figure_to_scene)
from . import discovery, suggestions


class SystemLibrary:
    """Every system the web app can show: the index, and scenes on demand.

    `catalog_loader` returns a parsed Catalog, or raises; the default reads
    the workbook with `catalog_kwargs`, and falls back to the committed
    snapshot when the live sheet fails, as the other workbook loaders do.  If
    that fails too the library still serves the featured systems and says why
    in `catalog_status()`, so a missing credential costs at most the catalog.
    """

    def __init__(self, bands: SolventChoice, *, t_start: Optional[float] = None,
                 frames: int = 120, frame_duration_ms: int = 50,
                 catalog_loader: Optional[Callable] = None,
                 catalog_kwargs: Optional[dict] = None,
                 use_catalog: bool = True,
                 planetless_loader: Optional[Callable] = None,
                 galactic_loader: Optional[Callable] = None):
        self.bands = bands
        self.t_start = t_start if t_start is not None else jd_now()
        self.frames = frames
        self.frame_duration_ms = frame_duration_ms
        self._use_catalog = use_catalog
        self._catalog_kwargs = catalog_kwargs or {}
        self._catalog_loader = catalog_loader
        self._catalog = None
        self._catalog_error: Optional[str] = None
        self._catalog_tried = False
        self._planetless_loader = planetless_loader
        self._planetless: Optional[dict] = None
        self._galactic_loader = galactic_loader
        self._galactic = None
        self._galactic_tried = False
        self._index: Optional[list[dict]] = None
        self._scenes: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ── the catalog ─────────────────────────────────────────────────────────
    def catalog(self):
        if not self._use_catalog:
            return None
        with self._lock:
            if not self._catalog_tried:
                self._catalog_tried = True
                try:
                    if self._catalog_loader is not None:
                        self._catalog = self._catalog_loader()
                    else:
                        self._catalog = _catalog_or_snapshot(self._catalog_kwargs)
                except Exception as e:     # credential, network, parse
                    self._catalog_error = str(e)
                    print(f"Catalog unavailable, serving featured systems "
                          f"only: {e}", file=sys.stderr)
        return self._catalog

    def planetless(self) -> dict:
        """{'System / Host': PlanetlessSystem}: the Planetless 4+ Stars tab, read once.

        The live sheet, else the committed snapshot. Switched off with the
        catalog, since it is the same workbook; a failure costs these systems
        and nothing else.
        """
        if not self._use_catalog:
            return {}
        with self._lock:
            if self._planetless is None:
                try:
                    if self._planetless_loader is not None:
                        self._planetless = self._planetless_loader()
                    else:
                        self._planetless = load_planetless()[0]
                except Exception as e:
                    print(f"Planetless 4+ Stars unavailable: {e}", file=sys.stderr)
                    self._planetless = {}
        return self._planetless

    def galactic(self):
        """The Sgr A* S-stars tab (SgrACluster), read once, or None.

        Like planetless(): the live sheet, else the snapshot, off with the
        catalog; a failure costs this one system.
        """
        if not self._use_catalog:
            return None
        with self._lock:
            if not self._galactic_tried:
                self._galactic_tried = True
                try:
                    self._galactic = (self._galactic_loader or load_sgr_a)()
                except Exception as e:
                    print(f"Sgr A* S-stars unavailable: {e}", file=sys.stderr)
        return self._galactic

    def catalog_status(self) -> dict:
        cat = self.catalog()
        return {
            "available": cat is not None,
            "title": getattr(cat, "workbook_title", "") if cat else "",
            "error": None if cat is not None else (
                self._catalog_error or "catalog disabled"),
        }

    # ── the index ───────────────────────────────────────────────────────────
    def index(self) -> list[dict]:
        """Every system the search box can find, featured first."""
        if self._index is not None:
            return self._index
        entries: list[dict] = []
        covered: set[str] = set()
        for key in BUILTIN_NAMES:
            system = get_builtin_system(key, self.bands)
            planets = [b.name for b in system.bodies if b.body_type == "planet"]
            hosts = FEATURED_CATALOG_HOSTS.get(key, ())
            covered.update(hosts)
            aliases = list(dict.fromkeys(FEATURED_ALIASES.get(key, ()) + hosts))
            entries.append({
                "id": key, "name": FEATURED_LABELS.get(key, system.name),
                "featured": True, "kind": system_kind(key),
                "aliases": aliases, "planets": planets,
                "n_planets": len(planets),
                "distance_ly": system.distance_from_sun_ly,
                "stellar_class": "",
            })
        # Featured views (hybrasil/views.py) come after the built-ins.
        for key, (label, _) in FEATURED_VIEWS.items():
            entries.append({
                "id": key, "name": label, "featured": True, "view": True,
                "kind": system_kind(key),
                "aliases": [], "planets": [], "n_planets": 0,
                "distance_ly": None, "stellar_class": "",
            })
        # Every hierarchy of 4+ stars on the Planetless tab, but the one a
        # featured system draws (Castor): listed under High Star Count (Planetless) only.
        for host, ps in self.planetless().items():
            if host not in covered:
                entries.append(planetless_entry(ps))
        # The S-stars round Sgr A*, under Stellar Motion after Nearby Stellar Motion.
        if self.galactic() is not None:
            entries.append(sgr_a_entry(self.galactic()))
        cat = self.catalog()
        if cat is not None:
            from ..data.catalog_loader import catalog_entry
            for host in cat.hosts():
                if host in covered:
                    continue
                e = catalog_entry(cat, host)
                # The nickname, then every other star, so "55 Cnc B" finds
                # the system it belongs to.
                aliases = ([e["nickname"]] if e["nickname"] else []) + [
                    s for s in e["stars"] if s != host]
                entries.append({
                    "id": CATALOG_PREFIX + host, "name": host, "featured": False,
                    "kind": "planetary",
                    "aliases": aliases,
                    "planets": e["planets"], "n_planets": len(e["planets"]),
                    "distance_ly": e["distance_ly"],
                    "stellar_class": e["stellar_class"],
                })
        self._index = entries
        return entries

    def known(self, system_id: str) -> bool:
        return any(e["id"] == system_id for e in self.index())

    # ── one system ──────────────────────────────────────────────────────────
    def _build_system(self, system_id: str):
        if system_id == SGR_A_ID:
            system = build_sgr_a_system(self.galactic())
            return system, sgr_a_span_days(system)
        if system_id.startswith(PLANETLESS_PREFIX):
            system = build_planetless_system(self.planetless()[system_id[len(PLANETLESS_PREFIX):]], self.bands)
            return system, planetless_span_days(system)
        if system_id.startswith(CATALOG_PREFIX):
            from ..data.catalog_loader import build_star_system
            host = system_id[len(CATALOG_PREFIX):]
            system = build_star_system(self.catalog(), host, self.bands)
            return system, _natural_span_days(system)
        system = get_builtin_system(system_id, self.bands)
        return system, _NATURAL_SPANS.get(system_id, 365.25)

    def scene(self, system_id: str) -> dict:
        """The scene and info-panel data for one system, built once."""
        with self._lock:
            hit = self._scenes.get(system_id)
        if hit is not None:
            return hit
        if not self.known(system_id):
            raise KeyError(system_id)
        if system_id in FEATURED_VIEWS:
            # The live catalog when it loaded, else the committed snapshot; and
            # the planetless systems the library already holds, for the view's
            # Planetless Systems button.
            fig, info = build_view(system_id, self.catalog(), self.planetless())
            payload = {"id": system_id, "name": FEATURED_VIEWS[system_id][0],
                       "scene": figure_to_scene(fig), "body_info": info}
            with self._lock:
                self._scenes.setdefault(system_id, payload)
            return payload
        system, span = self._build_system(system_id)
        fig = build_figure(system, self.t_start, self.t_start + span,
                           frames=self.frames,
                           frame_duration_ms=self.frame_duration_ms)
        payload = {
            "id": system_id,
            "name": system.name,
            "scene": figure_to_scene(fig),
            "body_info": build_body_info({system_id: system}, BODY_METADATA),
        }
        with self._lock:
            self._scenes.setdefault(system_id, payload)
        return payload


SUGGEST_URL = "/api/suggestions"


def _catalog_or_snapshot(kwargs: dict):
    """The live catalog, else the committed snapshot's."""
    from ..data.catalog_loader import get_catalog, parse_workbook
    try:
        return get_catalog(**kwargs)
    except Exception as e:                       # no credential, no network, no cache
        print(f"Catalog: live sheet unavailable ({e.__class__.__name__}); using the "
              "committed snapshot.", file=sys.stderr)
        from ..data.snapshot import load_snapshot_workbook
        return parse_workbook(load_snapshot_workbook())


def app_page(library: SystemLibrary, initial: str, *, api_base: str = "/api",
             index_url: Optional[str] = None, sky: str = SKY_URL,
             suggest_url: Optional[str] = SUGGEST_URL,
             turnstile_sitekey: Optional[str] = None) -> str:
    """The viewer shell for `library`: the server's page, and the static site's."""
    extra_js = build_solvent_table_js(library.bands) + "\nwindow._SA_BODY_INFO = {};"
    return build_app_html(initial, extra_js=extra_js, api_base=api_base,
                          index_url=index_url, sky=sky, suggest_url=suggest_url,
                          turnstile_sitekey=turnstile_sitekey, head=discovery.head_html())


def _json(handler: BaseHTTPRequestHandler, status: int, body) -> None:
    data = json.dumps(body, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def make_handler(library: SystemLibrary, shell_html: str):
    """The request handler, bound to one library and one page."""
    page = shell_html.encode("utf-8")
    # The background sky, read once.  Missing is not fatal: the page falls
    # back to its plain background when the image does not load.
    sky_path = SKY_DIR / SKY_FILE
    sky = sky_path.read_bytes() if sky_path.exists() else None

    class Handler(BaseHTTPRequestHandler):
        server_version = "Hybrasil"

        def log_message(self, fmt, *args):        # quiet by default
            pass

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
                return
            if path == f"/{discovery.LLMS_FILE}":
                body = discovery.llms_txt().encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == SKY_URL and sky is not None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(sky)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(sky)
                return
            if path == "/api/systems":
                _json(self, HTTPStatus.OK, {"systems": library.index(),
                                            "catalog": library.catalog_status()})
                return
            if path.startswith("/api/systems/"):
                system_id = unquote(path[len("/api/systems/"):])
                try:
                    _json(self, HTTPStatus.OK, library.scene(system_id))
                except KeyError:
                    _json(self, HTTPStatus.NOT_FOUND,
                          {"error": f"no system '{system_id}'"})
                except Exception as e:                 # a build that failed
                    _json(self, HTTPStatus.INTERNAL_SERVER_ERROR,
                          {"error": f"could not build '{system_id}': {e}"})
                return
            if path == SUGGEST_URL:
                _json(self, HTTPStatus.METHOD_NOT_ALLOWED, {"error": "use POST"})
                return
            _json(self, HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self):
            # Suggest Changes, recorded to the local store for review.  The
            # workbook is never touched (suggestions.py).
            if urlparse(self.path).path != SUGGEST_URL:
                _json(self, HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                size = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                size = -1
            if size < 0 or size > suggestions.RULES["max_body_bytes"]:
                self.close_connection = True       # the body is left unread
                _json(self, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too large"})
                return
            body = self.rfile.read(size)
            ctype = (self.headers.get("Content-Type") or "").lower()
            if not ctype.startswith("application/json"):
                _json(self, HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "send JSON"})
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                _json(self, HTTPStatus.BAD_REQUEST, {"error": "not JSON"})
                return
            if not isinstance(payload, dict):
                _json(self, HTTPStatus.BAD_REQUEST, {"error": "not a submission"})
                return
            clean, errors = suggestions.validate(payload)
            if errors:
                _json(self, HTTPStatus.BAD_REQUEST, {"error": "invalid", "fields": errors})
                return
            rec = suggestions.record_local(clean)
            _json(self, HTTPStatus.CREATED, {"id": rec["id"]})

    return Handler


def make_server(library: SystemLibrary, initial: str, *, host: str = "127.0.0.1",
                port: int = 8765) -> ThreadingHTTPServer:
    """A server for `library`, opening on `initial`; port 0 picks a free one."""
    shell = app_page(library, initial)
    server = ThreadingHTTPServer((host, port), make_handler(library, shell))
    server.daemon_threads = True
    return server


def serve(library: SystemLibrary, initial: str, *, host: str = "127.0.0.1",
          port: int = 8765, open_browser: bool = True) -> None:
    """Serve until interrupted."""
    server = make_server(library, initial, host=host, port=port)
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"Hybrasil serving at {url}  (Ctrl+C to stop)", flush=True)
    # The index is built now rather than on the first request, so a catalog
    # problem is reported in the terminal before anyone opens the page.
    n = len(library.index())
    status = library.catalog_status()
    print(f"{n} systems searchable"
          + ("" if status["available"] else " (featured only: catalog unavailable)"),
          flush=True)
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
