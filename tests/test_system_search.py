# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The More Modeled Systems search: the right system first, however it is typed.

system_search.js runs in the page; here it runs under node against an index
shaped like /api/systems, with featured and catalog entries mixed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

SEARCH_JS = (Path(__file__).resolve().parent.parent
             / "hybrasil" / "viz" / "system_search.js")

INDEX = [
    {"id": "solar", "name": "Solar System", "featured": True,
     "aliases": ["Sun", "Sol"], "planets": ["Earth", "Mars", "Jupiter"]},
    {"id": "trappist-1", "name": "TRAPPIST-1", "featured": True,
     "aliases": ["TRAPPIST-1"], "planets": ["TRAPPIST-1e"], "distance_ly": 40.5},
    {"id": "alpha-centauri", "name": "Alpha Centauri", "featured": True,
     "aliases": ["alf Cen A", "Rigil Kentaurus", "Toliman"], "planets": []},
    {"id": "proxima-centauri", "name": "Proxima Centauri", "featured": True,
     "aliases": ["Proxima Cen"], "planets": ["Proxima Centauri b"]},
    {"id": "55-cancri", "name": "55 Cancri", "featured": True,
     "aliases": ["55 Cnc", "rho1 Cancri", "Copernicus", "55 Cnc A", "55 Cnc B"]},
    {"id": "catalog:tau Cet", "name": "tau Cet", "featured": False,
     "planets": ["tau Cet e", "tau Cet f"], "distance_ly": 11.9},
    {"id": "catalog:tau Boo", "name": "tau Boo", "featured": False,
     "planets": ["tau Boo b"], "distance_ly": 50.9},
    {"id": "catalog:51 Peg", "name": "51 Peg", "featured": False,
     "aliases": ["Helvetios"], "planets": ["51 Peg b"], "distance_ly": 50.4},
    {"id": "catalog:gam Cep A", "name": "gam Cep A", "featured": False,
     "distance_ly": 45.0},
    {"id": "catalog:GJ 667 C", "name": "GJ 667 C", "featured": False,
     "distance_ly": 23.6},
    {"id": "catalog:HD 219134", "name": "HD 219134", "featured": False,
     "distance_ly": 21.3},
    {"id": "catalog:eps Eri", "name": "eps Eri", "featured": False,
     "aliases": ["Ran"], "distance_ly": 10.5},
]


def rank(*queries):
    script = "\n".join([
        f"const S = require({json.dumps(str(SEARCH_JS))});",
        f"const index = {json.dumps(INDEX)};",
        f"const qs = {json.dumps(list(queries))};",
        "console.log(JSON.stringify(qs.map(q => S.rank(index, q, 5).map(h =>",
        "  ({id: h.entry.id, tier: h.tier, via: h.via, score: h.score})))));",
    ])
    proc = subprocess.run(["node", "-e", script], capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def top(query):
    hits = rank(query)[0]
    return hits[0]["id"] if hits else None


@pytest.mark.parametrize("query, want", [
    # As the catalog writes it, and the long way.
    ("tau Cet", "catalog:tau Cet"),
    ("tau ceti", "catalog:tau Cet"),
    ("51 pegasi", "catalog:51 Peg"),
    ("epsilon eridani", "catalog:eps Eri"),
    ("gamma cephei", "catalog:gam Cep A"),
    # Featured systems by any name they go by.
    ("alpha centauri", "alpha-centauri"),
    ("alf cen", "alpha-centauri"),
    ("toliman", "alpha-centauri"),
    ("copernicus", "55-cancri"),
    ("55 cnc b", "55-cancri"),
    ("proxima", "proxima-centauri"),
    ("sun", "solar"),
    # Partial words, words out of order, a planet's name.
    ("gj667", "catalog:GJ 667 C"),
    ("hd 2191", "catalog:HD 219134"),
    ("cen alpha", "alpha-centauri"),
    ("earth", "solar"),
    # Typos: the autocorrect.
    ("trapist", "trappist-1"),
    ("trappsit", "trappist-1"),
    ("ganma cep", "catalog:gam Cep A"),
    ("helvetious", "catalog:51 Peg"),
])
def test_the_right_system_comes_first(query, want):
    assert top(query) == want


def test_nothing_is_returned_for_nonsense():
    assert rank("zzzzqqq")[0] == []


def test_a_typo_match_says_it_is_one():
    # The page shows "Did you mean …?" from this tier.
    assert rank("trapist")[0][0]["tier"] == "typo"
    assert rank("trappist")[0][0]["tier"] in ("exact", "prefix")


def test_an_alias_match_says_which_alias():
    hit = rank("copernicus")[0][0]
    assert hit["via"] == "Copernicus"


def test_tau_is_a_letter_first_and_a_constellation_after():
    # "tau Boo" is the Bayer letter tau in Bootes, not Taurus.
    assert top("tau bootis") == "catalog:tau Boo"


def test_a_planet_name_ranks_below_the_stars_own_name():
    # "tau Cet e" matches the star by its planet; the star's own name wins.
    hits = rank("tau cet")[0]
    assert hits[0]["id"] == "catalog:tau Cet" and hits[0]["via"] is None


def test_equal_matches_come_nearest_first():
    # "tau" starts both tau Cet (11.9 ly) and tau Boo (50.9 ly) equally well.
    ids = [h["id"] for h in rank("tau")[0]]
    assert ids.index("catalog:tau Cet") < ids.index("catalog:tau Boo")


# ── The shelf: what the list shows before anything is typed ──────────────────

def shelf(index):
    script = "\n".join([
        f"const S = require({json.dumps(str(SEARCH_JS))});",
        f"const s = S.shelf({json.dumps(index)});",
        "console.log(JSON.stringify({featured: s.featured.map(e => e.id),",
        "                            more: s.more.map(e => e.id)}));",
    ])
    proc = subprocess.run(["node", "-e", script], capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


SHELF_INDEX = [
    {"id": "solar", "name": "Solar System", "featured": True, "n_planets": 9},
    {"id": "trappist-1", "name": "TRAPPIST-1", "featured": True, "n_planets": 7,
     "distance_ly": 40.5},
    {"id": "catalog:far six", "name": "Far Six", "n_planets": 6, "distance_ly": 90.0},
    {"id": "catalog:HD 219134", "name": "HD 219134", "n_planets": 6, "distance_ly": 21.3},
    {"id": "catalog:near one", "name": "Near One", "n_planets": 1, "distance_ly": 5.0},
    {"id": "catalog:no distance", "name": "No Distance", "n_planets": 1,
     "distance_ly": None},
    {"id": "catalog:eight", "name": "Eight", "n_planets": 8, "distance_ly": 30.0},
]


def test_the_shelf_keeps_featured_systems_in_their_own_order():
    assert shelf(SHELF_INDEX)["featured"] == ["solar", "trappist-1"]


def test_the_shelf_lists_every_catalog_system_most_planets_first_then_nearest():
    assert shelf(SHELF_INDEX)["more"] == [
        "catalog:eight",           # 8 planets
        "catalog:HD 219134",       # 6 planets, 21.3 ly
        "catalog:far six",         # 6 planets, 90 ly
        "catalog:near one",        # 1 planet, 5 ly
        "catalog:no distance",     # 1 planet, distance unknown: last
    ]


def test_the_planetless_shelf_lists_most_stars_first_then_nearest():
    index = [
        {"id": "castor", "name": "Castor", "featured": True, "kind": "planetless"},
        {"id": "planetless:four far", "name": "Four Far", "n_planets": 0, "n_stars": 4, "distance_ly": 80.0},
        {"id": "planetless:six", "name": "Six", "n_planets": 0, "n_stars": 6, "distance_ly": 90.0},
        {"id": "planetless:four near", "name": "Four Near", "n_planets": 0, "n_stars": 4, "distance_ly": 10.0},
        {"id": "planetless:five", "name": "Five", "n_planets": 0, "n_stars": 5, "distance_ly": 50.0},
    ]
    s = shelf(index)
    assert s["featured"] == ["castor"]
    assert s["more"] == ["planetless:six", "planetless:five", "planetless:four near", "planetless:four far"]


def test_the_featured_systems_are_not_on_the_shelf_twice():
    # They keep their own buttons; the search still finds them.
    assert not {"solar", "trappist-1"} & set(shelf(SHELF_INDEX)["more"])
    assert top("trappist") == "trappist-1"
