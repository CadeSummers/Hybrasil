# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The static site (--build-site): the web app as files, for Cloudflare Pages.

Built from the test library of test_web_app -- the literal test workbook, no
network, no credential -- without the snapshot's planetless systems, so a
whole site builds in seconds.  The browser half is in test_browser.py.
"""

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin
import urllib.request

import pytest

from hybrasil.cli import build_parser
from hybrasil.data.builtin_systems import BUILTIN_NAMES
from hybrasil.web.app import CATALOG_PREFIX
from hybrasil.web.static_site import (INDEX_FILE, SiteBuildError, build_site, scene_files,
                                      slug)
from tests.test_web_app import _library


def small_library(**kw):
    """The test library without the snapshot's 79 planetless systems or Sgr A*."""
    kw.setdefault("planetless_loader", lambda: {})
    kw.setdefault("galactic_loader", lambda: None)
    return _library(**kw)


@pytest.fixture(scope="module")
def library():
    return small_library()


@pytest.fixture(scope="module")
def site(library, tmp_path_factory):
    out = tmp_path_factory.mktemp("site") / "site"
    summary = build_site(library, out, "solar")
    return out, summary


class TestFileNames:
    def test_an_id_becomes_a_plain_lower_case_name(self):
        assert slug("catalog:tau Cet") == "catalog-tau-cet"
        assert slug("planetless:1 Hya") == "planetless-1-hya"
        assert slug("galactic:sgr-a") == "galactic-sgr-a"
        assert slug("solar") == "solar"

    def test_never_empty(self):
        assert slug("***") and slug("") and slug("***") != slug("+++")

    def test_ids_that_slug_alike_get_distinct_files(self):
        # Case alone would collide on Windows and macOS file systems.
        files = scene_files(["catalog:HD 1", "catalog:hd-1", "solar"])
        assert len(set(files.values())) == 3
        assert files["solar"] == "solar.json"
        assert all(f.startswith("catalog-hd-1-") for k, f in files.items() if k != "solar")


class TestTheSite:
    def test_every_system_has_its_file_and_the_index_points_at_it(self, site, library):
        out, summary = site
        index = json.loads((out / INDEX_FILE).read_text(encoding="utf-8"))
        assert [e["id"] for e in index["systems"]] == [e["id"] for e in library.index()]
        assert summary["systems"] == len(index["systems"])
        for e in index["systems"]:
            assert not e["url"].startswith("/"), "a root-absolute URL breaks under a path prefix"
            payload = json.loads((out / e["url"]).read_text(encoding="utf-8"))
            assert payload["id"] == e["id"] and payload["scene"]["title"]

    def test_a_scene_file_is_what_the_server_sends(self, site, library):
        out, _ = site
        index = json.loads((out / INDEX_FILE).read_text(encoding="utf-8"))
        e = next(e for e in index["systems"] if e["id"] == CATALOG_PREFIX + "Test A")
        on_disk = json.loads((out / e["url"]).read_text(encoding="utf-8"))
        assert on_disk == json.loads(json.dumps(library.scene(e["id"])))

    def test_the_page_asks_only_for_relative_urls(self, site):
        page = (site[0] / "index.html").read_text(encoding="utf-8")
        assert 'window.SA3_API     = "api";' in page
        assert 'window.SA3_INDEX_URL = "api/systems.json";' in page
        assert 'window.SA3_SKY     = "sky/milky_way_4k.jpg";' in page
        assert 'window.SA3_INITIAL = "solar";' in page
        assert "window.SA3_SYSTEMS = {};" in page

    def test_the_host_files_are_there(self, site):
        out, _ = site
        assert (out / "sky" / "milky_way_4k.jpg").stat().st_size > 1_000_000
        assert "/api/*" in (out / "_headers").read_text(encoding="utf-8")
        assert (out / ".nojekyll").exists() and (out / "robots.txt").exists()

    def test_the_index_carries_no_error_text(self, site):
        # The server's error string can name a local path or a sheet ID.
        index = json.loads((site[0] / INDEX_FILE).read_text(encoding="utf-8"))
        assert index["catalog"]["available"] is True and index["catalog"]["error"] is None

    def test_a_rebuild_replaces_what_was_there(self, library, tmp_path):
        out = tmp_path / "site"
        out.mkdir()
        (out / "stale.json").write_text("{}", encoding="utf-8")
        build_site(library, out, "solar")
        assert not (out / "stale.json").exists()


class TestStrictness:
    def test_no_catalog_is_no_site(self, tmp_path):
        def broken():
            raise RuntimeError("no credential")
        with pytest.raises(SiteBuildError, match="catalog did not load"):
            build_site(small_library(catalog_loader=broken), tmp_path / "site")

    def test_featured_only_when_asked(self, tmp_path):
        def broken():
            raise RuntimeError("no credential")
        summary = build_site(small_library(catalog_loader=broken), tmp_path / "site",
                             require_catalog=False)
        assert summary["systems"] >= len(BUILTIN_NAMES)

    def test_one_failed_system_fails_the_build_and_names_it(self, tmp_path, monkeypatch):
        lib = small_library()
        real = lib.scene

        def scene(system_id):
            if system_id == "castor":
                raise ValueError("boom")
            return real(system_id)
        monkeypatch.setattr(lib, "scene", scene)
        with pytest.raises(SiteBuildError, match="castor: ValueError: boom"):
            build_site(lib, tmp_path / "site")

    def test_an_unknown_initial_system_is_refused(self, library, tmp_path):
        with pytest.raises(SiteBuildError, match="initial system"):
            build_site(library, tmp_path / "site", "nowhere")


class TestUnderAPathPrefix:
    """GitHub Pages serves a project at /<repo>/: the page must still find everything."""

    def test_every_url_resolves_from_the_page(self, site):
        out, _ = site
        handler = partial(SimpleHTTPRequestHandler, directory=str(out.parent))
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            page_url = f"http://127.0.0.1:{srv.server_address[1]}/{out.name}/"

            def get(url):
                with urllib.request.urlopen(url, timeout=30) as r:
                    return r.status, r.read()
            assert get(page_url)[0] == 200
            status, body = get(urljoin(page_url, "api/systems.json"))
            index = json.loads(body)
            for e in index["systems"]:
                assert get(urljoin(page_url, e["url"]))[0] == 200, e["id"]
            assert get(urljoin(page_url, "sky/milky_way_4k.jpg"))[0] == 200
        finally:
            srv.shutdown()
            srv.server_close()


class TestTheDataSource:
    """The site is built from the snapshot; the app falls back to it without a credential."""

    @pytest.mark.parametrize("name", ["HYBRASIL_DATA_SOURCE", "HYBRASIL_NEARBY_SOURCE"])
    def test_either_name_selects_the_snapshot(self, monkeypatch, name):
        from hybrasil.data.snapshot import snapshot_only
        monkeypatch.delenv("HYBRASIL_DATA_SOURCE", raising=False)
        monkeypatch.delenv("HYBRASIL_NEARBY_SOURCE", raising=False)
        assert not snapshot_only()
        monkeypatch.setenv(name, "Snapshot")
        assert snapshot_only()

    def test_the_catalog_reads_the_snapshot_when_asked(self, monkeypatch):
        from hybrasil.data import google_sheets
        from hybrasil.data.catalog_loader import get_catalog
        monkeypatch.setenv("HYBRASIL_DATA_SOURCE", "snapshot")

        def no_network(*a, **k):
            raise AssertionError("the live sheet was read")
        monkeypatch.setattr(google_sheets, "get_workbook", no_network)
        cat = get_catalog()
        assert cat.workbook_title.startswith("hybrasil-") and len(cat.hosts()) > 300

    def test_the_app_falls_back_to_the_snapshot_without_a_credential(self, monkeypatch):
        from hybrasil.data import catalog_loader
        monkeypatch.delenv("HYBRASIL_DATA_SOURCE", raising=False)
        monkeypatch.delenv("HYBRASIL_NEARBY_SOURCE", raising=False)

        def no_credential(*a, **k):
            raise RuntimeError("Google Sheets access is not configured")
        monkeypatch.setattr(catalog_loader, "get_catalog", no_credential)
        lib = small_library(catalog_loader=None)
        status = lib.catalog_status()
        assert status["available"] and status["title"].startswith("hybrasil-")

    def test_the_snapshot_is_read_once(self):
        from hybrasil.data.snapshot import load_snapshot_workbook
        assert load_snapshot_workbook() is load_snapshot_workbook()


def test_the_switch():
    args = build_parser().parse_args(["--build-site", "site"])
    assert args.build_site == "site" and not args.serve
