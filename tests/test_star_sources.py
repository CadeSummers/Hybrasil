# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Identifiers into the links of a Nearby Stellar Motion info panel's Sources (data/star_sources.py).

Each URL pattern was opened by hand on 9 Oct 2026 and found to return the record; these tests pin the patterns, so a
change to one is a decision rather than an accident.
"""

from hybrasil.data import star_sources as ss


def test_each_catalog_links_its_own_row():
    assert ss.link("gaia_dr3", "4472832130942575872") == \
        "https://vizier.cds.unistra.fr/viz-bin/VizieR-4?-source=I/355/gaiadr3&Source=4472832130942575872"
    assert ss.link("cns5", "4") == "https://vizier.cds.unistra.fr/viz-bin/VizieR-4?-source=J/A%2BA/670/A19/cns5&CNS5=4"
    # The WDS code's '+' must reach VizieR as a '+', not a space.
    assert ss.link("msc", "07346+3153") == \
        "https://vizier.cds.unistra.fr/viz-bin/VizieR-4?-source=J/ApJS/235/6/systems&ID=07346%2B3153"
    assert ss.link("exoplanet_archive", "tau Cet") == "https://exoplanetarchive.ipac.caltech.edu/overview/tau%20Cet"


def test_identifiers_are_quoted():
    # SIMBAD main ids carry '*', spaces and dots; a bibcode carries '&'.
    assert ss.link("simbad", "* nu. Oct") == "https://simbad.cds.unistra.fr/simbad/sim-id?Ident=%2A%20nu.%20Oct"
    assert ss.link("ads", "2018A&A...616A...7S") == \
        "https://ui.adsabs.harvard.edu/abs/2018A%26A...616A...7S/abstract"


def test_existence_links_come_in_a_fixed_order_and_say_exists():
    out = ss.existence_sources(simbad_id="* alf Gem", gaia_id="1", cns5_id="CNS5 12", wds="07346+3153",
                               exoplanet_host="alf Gem")
    assert [lbl.split(":")[1].split()[0] for lbl, _ in out] == ["SIMBAD", "Gaia", "CNS5", "Multiple", "NASA"]
    assert all(lbl.startswith("Exists: ") for lbl, _ in out)
    assert out[2] == ["Exists: CNS5 12 (Golovin et al. 2023)", ss.link("cns5", "12")]
    assert ss.existence_sources() == []


def test_kinematics_refs_become_labelled_links():
    out = ss.kinematics_sources("RV: 2018A&A...616A...7S, https://arxiv.org/abs/2208.00070; "
                                "PM: 2007A&A...474..653V, doi:10.1088/0004-6256/147/1/20")
    assert out == [
        ["Radial velocity: 2018A&A...616A...7S", ss.link("ads", "2018A&A...616A...7S")],
        ["Radial velocity: arXiv:2208.00070", "https://arxiv.org/abs/2208.00070"],
        ["Proper motion: 2007A&A...474..653V", ss.link("ads", "2007A&A...474..653V")],
        ["Proper motion: doi:10.1088/0004-6256/147/1/20", "https://doi.org/10.1088%2F0004-6256%2F147%2F1%2F20"],
    ]


def test_a_catalog_named_for_both_is_listed_once_and_points_at_the_stars_row():
    out = ss.kinematics_sources("RV: Gaia DR3; PM: Gaia DR3", gaia_id="123")
    assert out == [["Radial velocity and proper motion: Gaia DR3 123", ss.link("gaia_dr3", "123")]]


def test_a_catalog_with_no_row_to_point_at_links_its_landing_page():
    assert ss.kinematics_sources("RV: CNS5; PM: Gaia DR2") == [
        ["Radial velocity: CNS5", ss.CATALOG_PAGES["CNS5"]],
        ["Proper motion: Gaia DR2", ss.CATALOG_PAGES["Gaia DR2"]],
    ]


def test_nothing_linkable_gives_nothing():
    assert ss.kinematics_sources("") == [] and ss.kinematics_sources("RV: none found") == []
