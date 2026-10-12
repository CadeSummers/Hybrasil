# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""What the site tells search engines, LLMs and agents about itself (web/discovery.py).

The JSON-LD, llms.txt and AGENTS.md all point back at the canonical upstream,
each built from or checked against about.json, so
a DOI or a licence changes in one place.  The SPDX check keeps every source
file carrying its terms with it.
"""

import json
import re
import subprocess
import threading
from pathlib import Path

import pytest

from hybrasil.viz.three_viewer import about
from hybrasil.web import discovery
from hybrasil.web.app import app_page, make_server
from tests.test_static_site import site, small_library  # noqa: F401  (the site fixture)
from tests.test_web_app import _get

ROOT = Path(__file__).resolve().parents[1]


def _ld_blocks(page: str) -> list:
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    assert len(blocks) == 1
    return json.loads(blocks[0])


@pytest.fixture(scope="module")
def library():
    return small_library()


class TestJsonLd:
    def test_one_record_for_the_map_and_one_for_its_data(self):
        app, data = discovery.json_ld()
        assert app["@type"] == "SoftwareApplication" and data["@type"] == "Dataset"
        assert app["name"] == about()["title"] and data["name"] == about()["dataset_title"]

    def test_each_carries_its_own_licence(self):
        app, data = discovery.json_ld()
        assert app["license"] == about()["licences"]["code"]["url"]
        assert data["license"] == about()["licences"]["data"]["url"]

    def test_the_author_is_named_by_orcid(self):
        for record in discovery.json_ld():
            person = record.get("author") or record.get("creator")
            assert person["@id"] == f"https://orcid.org/{about()['author']['orcid']}"
            assert person["name"] == "Cade Summers"

    def test_a_doi_appears_only_once_minted(self):
        a = about()
        assert all("identifier" not in r for r in discovery.json_ld(a))
        a["dois"] = {"software": "10.5281/zenodo.1", "dataset": "10.5281/zenodo.2"}
        app, data = discovery.json_ld(a)
        assert app["identifier"] == "https://doi.org/10.5281/zenodo.1"
        assert data["identifier"] == "https://doi.org/10.5281/zenodo.2"
        assert "https://doi.org/10.5281/zenodo.2" in data["citation"]

    def test_googles_dataset_description_length(self):
        # Google Dataset Search wants 50 to 5000 characters.
        assert 50 <= len(discovery.json_ld()[1]["description"]) <= 5000

    def test_the_web_app_page_carries_it_in_its_head(self, library):
        page = app_page(library, "solar")
        head = page[:page.index("</head>")]
        assert 'application/ld+json' in head and '<meta name="description"' in head
        assert '<link rel="canonical" href="https://hybrasil.app/">' in head
        assert _ld_blocks(page) == discovery.json_ld()

    def test_the_static_site_page_carries_it(self, site):  # noqa: F811
        page = (site[0] / "index.html").read_text(encoding="utf-8")
        assert _ld_blocks(page) == discovery.json_ld()


class TestLlmsTxt:
    def test_it_names_the_home_the_licences_and_the_citations(self):
        text, a = discovery.llms_txt(), about()
        assert text.startswith(f"# {a['title']}\n\n> ")
        for must in (a["site"], a["source"], a["licences"]["code"]["name"],
                     a["licences"]["data"]["name"], a["contact"], a["author"]["orcid"],
                     *discovery.citations().values()):
            assert must in text, must

    def test_it_says_where_to_propose_changes(self):
        text = discovery.llms_txt()
        assert "## Propose changes" in text and "/issues/new/choose" in text
        assert "Suggest Changes" in text

    def test_the_static_site_writes_it(self, site):  # noqa: F811
        assert (site[0] / discovery.LLMS_FILE).read_text(encoding="utf-8") == discovery.llms_txt()

    def test_the_server_serves_it(self, library):
        srv = make_server(library, "solar", port=0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            status, ctype, body = _get(f"http://127.0.0.1:{srv.server_address[1]}/llms.txt")
        finally:
            srv.shutdown()
            srv.server_close()
        assert status == 200 and ctype.startswith("text/plain")
        assert body.decode("utf-8") == discovery.llms_txt()


class TestAgentsMd:
    """AGENTS.md is hand-written; it must agree with about.json."""

    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    def test_it_names_the_canonical_home(self):
        a = about()
        for must in (a["site"], a["source"], a["author"]["orcid"], a["contact"]):
            assert must in self.text, must

    def test_it_states_both_licences(self):
        a = about()
        assert a["licences"]["code"]["name"] in self.text
        assert a["licences"]["data"]["name"] in self.text

    def test_it_points_at_the_working_rules(self):
        assert "CLAUDE.md" in self.text and "CONTRIBUTING.md" in self.text


SPDX = "SPDX-License-Identifier: AGPL-3.0-or-later"


def _tracked_sources() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "*.py", "*.js", "*.sql"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / f for f in out]


def test_every_source_file_carries_its_licence():
    files = _tracked_sources()
    assert len(files) > 100
    missing = [str(p.relative_to(ROOT)) for p in files
               if SPDX not in "\n".join(p.read_text(encoding="utf-8").splitlines()[:5])]
    assert not missing, f"no SPDX header in the first lines of: {missing}"
