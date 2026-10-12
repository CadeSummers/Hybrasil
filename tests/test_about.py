# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The About panel's content (hybrasil/about.json): complete, public, and on every page."""

import re

from hybrasil.viz.three_viewer import about, build_app_html


def test_it_names_the_author_and_how_to_reach_the_project():
    a = about()
    assert a["author"]["name"] == "Cade Summers"
    assert re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", a["author"]["orcid"])
    assert a["site"] == "https://hybrasil.app" and a["contact"] == "cade@hybrasil.app"
    assert a["licences"]["code"]["name"].startswith("AGPL-3.0")
    assert a["licences"]["data"]["name"] == "CC BY-SA 4.0"


def test_every_credit_has_a_link_and_the_sky_credit_is_first():
    credits = about()["credits"]
    assert all(len(c) == 3 and c[2].startswith(("https://", "http://")) for c in credits)
    assert "Scientific Visualization Studio" in credits[0][1]


def test_unknowns_are_null_not_placeholders():
    # A DOI or a handle is filled in when it exists; until then the panel hides it.
    a = about()
    for v in list(a["dois"].values()) + list(a["support"].values()):
        assert v is None or (isinstance(v, str) and "<" not in v and "TODO" not in v.upper())


def test_nothing_private_in_it():
    text = str(about()).lower()
    for private in ("gmail", "godaddy", "spreadsheets/d/", "users\\cadet"):
        assert private not in text


def test_every_page_carries_it():
    assert "window.SA3_ABOUT" in build_app_html("solar")
