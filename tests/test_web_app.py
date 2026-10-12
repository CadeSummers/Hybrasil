# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The web app: its index, its scenes, and the HTTP API that serves them.

The catalog here is the literal test workbook from test_catalog_loader, with
one host renamed TRAPPIST-1 so the featured/catalog merge has something to
merge -- no network, no credential.
"""

import copy
import json
import threading
import urllib.error
import urllib.request

import pytest

from hybrasil.cli import build_parser
from hybrasil.data.builtin_systems import BUILTIN_NAMES
from hybrasil.views import FEATURED_VIEWS
from hybrasil.data.catalog_loader import parse_workbook
from hybrasil.mechanics.solvent_bands import SolventChoice
from hybrasil.mechanics.units import J2000
from hybrasil.web.app import CATALOG_PREFIX, SystemLibrary, make_server
from tests.test_catalog_loader import make_workbook


def _workbook_with_trappist():
    """The test workbook, with 'Test B' renamed to a host a featured system covers."""
    wb = copy.deepcopy(make_workbook())
    for rows in wb["tabs"].values():
        for row in rows:
            for i, cell in enumerate(row):
                if isinstance(cell, str) and cell.startswith("Test B"):
                    row[i] = cell.replace("Test B", "TRAPPIST-1")
    return wb


def _library(**kw):
    kw.setdefault("catalog_loader", lambda: parse_workbook(_workbook_with_trappist()))
    return SystemLibrary(SolventChoice.parse("all"), t_start=J2000, frames=6, **kw)


@pytest.fixture(scope="module")
def library():
    return _library()


class TestTheIndex:
    def test_featured_systems_come_first_in_their_order(self, library):
        ids = [e["id"] for e in library.index()]
        assert ids[:len(BUILTIN_NAMES)] == list(BUILTIN_NAMES)
        assert all(e["featured"] for e in library.index()[:len(BUILTIN_NAMES)])

    def test_catalog_systems_follow(self, library):
        # A Planetless 4+ Stars system with a brown dwarf is planetary too (7 Oct 2026), under its own prefix.
        cat = [e for e in library.index() if not e["featured"] and e["kind"] == "planetary"
               and not e["id"].startswith("planetless:")]
        assert {e["id"] for e in cat} >= {CATALOG_PREFIX + "Test A"}
        assert all(e["id"].startswith(CATALOG_PREFIX) for e in cat)

    def test_a_catalog_host_a_featured_system_covers_is_not_listed_twice(self, library):
        # The catalog's TRAPPIST-1 is the featured TRAPPIST-1, reachable by
        # its catalog name as an alias.
        ids = [e["id"] for e in library.index()]
        assert CATALOG_PREFIX + "TRAPPIST-1" not in ids
        trappist = next(e for e in library.index() if e["id"] == "trappist-1")
        assert "TRAPPIST-1" in trappist["aliases"]

    def test_a_catalog_entry_carries_what_the_search_shows(self, library):
        a = next(e for e in library.index() if e["id"] == CATALOG_PREFIX + "Test A")
        assert a["aliases"] == ["Testia"]              # the IAU nickname
        assert "Test A b" in a["planets"]
        assert a["n_planets"] == len(a["planets"])
        assert a["distance_ly"] == pytest.approx(10.0)

    def test_every_entry_is_json(self, library):
        json.dumps(library.index())


class TestTheMoreSystemsList:
    def test_every_plottable_catalog_host_is_offered(self, library):
        # The dropdown lists the whole index; nothing is hand-picked any more.
        cat = library.catalog()
        offered = {e["name"] for e in library.index() if e["id"].startswith(CATALOG_PREFIX)}
        assert offered == {h for h in cat.hosts() if h != "TRAPPIST-1"}

    def test_each_entry_carries_what_the_list_sorts_on(self, library):
        for e in library.index():
            assert "listed" not in e
            assert isinstance(e["n_planets"], int)
            assert "distance_ly" in e


class TestSystemTypes:
    """The dropdown's System Type row filters on each entry's `kind`."""

    def test_every_entry_has_one_of_the_three_kinds(self, library):
        assert {e["kind"] for e in library.index()} <= {"planetary", "planetless", "motion"}

    def test_castor_is_planetary_since_its_brown_dwarf_is_a_planet(self, library):
        # Until 7 Oct 2026 it was 'Castor (Planetless)', under High Star Count (Planetless).
        castor = next(e for e in library.index() if e["id"] == "castor")
        assert castor["kind"] == "planetary"
        assert castor["name"] == "Castor"
        assert "Castor" in castor["aliases"]           # "castor" still finds it

    def test_the_views_are_stellar_motion(self, library):
        for key in FEATURED_VIEWS:
            assert next(e for e in library.index() if e["id"] == key)["kind"] == "motion"

    def test_everything_else_is_planetary(self, library):
        rest = [e for e in library.index() if e["id"] != "castor" and e["id"] not in FEATURED_VIEWS
                and not e["id"].startswith(("planetless:", "galactic:"))]
        assert rest and all(e["kind"] == "planetary" for e in rest)

    def test_every_planetless_tab_system_is_listed_once(self, library):
        # The tab's other 79 hierarchies; its Castor row is the featured Castor, not a second listing. The ten
        # whose brown dwarfs are planets now (7 Oct 2026) are listed as Planetary.
        ids = [e["id"] for e in library.index()]
        planetless = [e for e in library.index() if e["id"].startswith("planetless:")]
        assert len(planetless) == 79
        assert {e["name"] for e in planetless if e["kind"] == "planetary"} == {
            "GJ 570", "ksi UMa", "GJ 867", "GJ 569", "tau Cyg", "pi1 Cnc", "GJ 9829", "BD+37 1091", "BD+39 496",
            "GJ 3347", "GJ 310.1"}
        assert all(e["kind"] == "planetless" for e in planetless if not e["n_planets"])
        assert "planetless:alf Gem" not in ids and ids.count("castor") == 1

    def test_a_planetless_system_opens(self, library):
        scene = library.scene("planetless:1 Hya")
        names = {b["name"] for b in scene["scene"]["bodies"]}
        assert "1 Hya Cb (hypothetical, model-inferred)" in names
        # and one whose brown dwarf is a planet now
        names = {b["name"] for b in library.scene("planetless:GJ 3347")["scene"]["bodies"]}
        assert "GJ 3347 Aa2" in names and "GJ 3347 Aa1" in names

    def test_the_s_stars_are_stellar_motion_after_nearby_stellar_motion(self, library):
        e = next(e for e in library.index() if e["id"] == "galactic:sgr-a")
        assert e["kind"] == "motion" and not e["featured"] and e["name"] == "Sgr A* Cluster (Galactic Center)"
        assert "Sgr A*" in e["aliases"] and "S2" in e["aliases"]
        assert [x["id"] for x in library.index() if x["kind"] == "motion"] == ["nearby-star-motion", "galactic:sgr-a"]

    def test_the_s_stars_open_round_a_black_hole(self, library):
        p = library.scene("galactic:sgr-a")
        names = {b["name"] for b in p["scene"]["bodies"]}
        assert "Sgr A* (supermassive black hole)" in names and "S2" in names and "S4716 (disputed)" in names
        assert p["body_info"]["S2"]["rows"][0][:2] == ["Object type", "Star"]
        assert p["body_info"]["Sgr A* (supermassive black hole)"]["rows"][0][1] == "Supermassive black hole"

    def test_the_label_is_the_dropdowns_not_the_systems(self):
        # Titles and the Plotly switcher keep the system's own name.
        from hybrasil.data.builtin_systems import get_builtin_system
        assert get_builtin_system("castor").name == "Castor"


class TestWithoutTheCatalog:
    def test_a_catalog_that_fails_costs_the_catalog_not_the_app(self):
        def broken():
            raise RuntimeError("no credential")
        lib = _library(catalog_loader=broken)
        ids = [e["id"] for e in lib.index()]
        # The Planetless and Sgr A* tabs come through their own loaders, so they survive too.
        assert [i for i in ids if not i.startswith(("planetless:", "galactic:"))] == (
            list(BUILTIN_NAMES) + list(FEATURED_VIEWS))
        assert any(i.startswith("planetless:") for i in ids) and "galactic:sgr-a" in ids
        status = lib.catalog_status()
        assert status["available"] is False and "no credential" in status["error"]

    def test_the_catalog_can_be_switched_off(self):
        lib = _library(use_catalog=False)
        assert [e["id"] for e in lib.index()] == list(BUILTIN_NAMES) + list(FEATURED_VIEWS)


class TestScenes:
    def test_a_featured_scene(self, library):
        p = library.scene("trappist-1")
        assert p["id"] == "trappist-1" and p["name"] == "TRAPPIST-1"
        assert {"bodies", "lines", "bands", "frames"} <= set(p["scene"])
        assert "TRAPPIST-1e" in p["body_info"]

    def test_a_catalog_scene(self, library):
        p = library.scene(CATALOG_PREFIX + "Test A")
        names = [b["name"] for b in p["scene"]["bodies"]]
        assert any(n.startswith("Test A b") for n in names)
        assert p["body_info"]

    def test_scenes_are_built_once(self, library):
        assert library.scene("trappist-1") is library.scene("trappist-1")

    def test_an_unknown_system_is_a_key_error(self, library):
        with pytest.raises(KeyError):
            library.scene(CATALOG_PREFIX + "Nowhere")


@pytest.fixture(scope="module")
def server(library):
    srv = make_server(library, "trappist-1", port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


class TestTheAPI:
    def test_the_page_is_the_app_shell(self, server):
        status, ctype, body = _get(server + "/")
        assert status == 200 and ctype.startswith("text/html")
        page = body.decode("utf-8")
        assert 'window.SA3_API     = "/api";' in page
        assert 'window.SA3_INITIAL = "trappist-1";' in page
        assert "window.SA3_SYSTEMS = {};" in page      # nothing prebuilt
        assert "SASystemSearch" in page

    def test_the_index(self, server):
        status, ctype, body = _get(server + "/api/systems")
        assert status == 200 and ctype.startswith("application/json")
        data = json.loads(body)
        assert data["catalog"]["available"] is True
        assert data["systems"][0]["id"] == BUILTIN_NAMES[0]

    def test_a_system_by_id_with_spaces_and_a_colon(self, server):
        sid = urllib.request.quote(CATALOG_PREFIX + "Test A", safe="")
        status, _, body = _get(f"{server}/api/systems/{sid}")
        assert status == 200
        assert json.loads(body)["id"] == CATALOG_PREFIX + "Test A"

    def test_an_unknown_system_is_404(self, server):
        status, _, body = _get(server + "/api/systems/catalog%3ANowhere")
        assert status == 404 and "Nowhere" in json.loads(body)["error"]

    def test_anything_else_is_404(self, server):
        assert _get(server + "/etc/passwd")[0] == 404


class TestTheSwitch:
    def test_serve_defaults_to_this_machine_only(self):
        args = build_parser().parse_args(["--serve"])
        assert args.serve and args.host == "127.0.0.1" and args.port == 8765

    def test_serving_is_off_by_default(self):
        assert build_parser().parse_args([]).serve is False


class TestWholeSystemsInTheIndex:
    def test_a_companion_star_is_an_alias_of_its_system(self, library):
        # The test workbook's Bin Sys B has a planet; searching for the star
        # must find the system it belongs to.
        entry = next(e for e in library.index()
                     if e["id"] == CATALOG_PREFIX + "Bin Sys")
        assert "Bin Sys B" in entry["aliases"]
        assert "Bin Sys B b" in entry["planets"]
