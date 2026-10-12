# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the Google Sheets catalog loader.

Everything here runs against a synthetic workbook, so no network access and no
credentials are involved.
"""

import pytest

from hybrasil.data.catalog_loader import (
    Catalog,
    build_star_system,
    build_tables,
    catalog_entry,
    catalog_listing,
    cell_number,
    classify_tables,
    hz_color,
    normalize_header,
    parse_workbook,
    star_radius_km,
)
from hybrasil.mechanics.units import (
    J2000, M_SUN_KG, M_EARTH_KG, R_SUN_KM, T_SUN_K,
)


SYSTEM_HEADERS = [
    "System / Host", "Nickname (IAU)", "Distance (ly)", "Host mass (M-sun)",
    "Stellar Class", "Effective temp (K)", "Host luminosity (L-sun)",
]

STAR_HEADERS = [
    "System / Host", "Star (component)", "Role in system", "Nickname (IAU)",
    "Distance (ly)", "Mass (M-sun)", "Stellar Class", "Effective temp (K)",
    "Luminosity (L-sun)", "Orbital eccentricity (e)", "Separation from",
    "Separation (AU)", "Separation type", "Separation source",
]

PLANET_HEADERS = [
    "Planet", "Host system (primary star)", "Distance (ly)",
    "Primary star class", "Planet-host star", "Planet-host class",
    "Orbits the primary?", "Host luminosity (L-sun)", "HZ position",
    "Mass (M-earth)", "Mass (M-Jup)", "Radius (R-earth)", "Radius (R-Jup)",
    "Orbital period (d)", "Semi-major axis (au)", "Eccentricity",
    "Confidence tier", "Detection method", "Orbit data source / flags",
]


def _planet(name, host, *, planet_host="", planet_host_class="", lum="",
            hz="", m_earth="", r_earth="", period="", sma="", ecc="",
            tier="confirmed", distance=10.0, source="OEC"):
    return [name, host, distance, "G2 V", planet_host, planet_host_class,
            "yes" if not planet_host or planet_host == host else "NO -- secondary",
            lum, hz, m_earth, "", r_earth, "", period, sma, ecc, tier,
            "Transit", source]


def make_workbook():
    return {
        "spreadsheet_id": "SHEET123",
        "title": "Test Catalog",
        "fetched_at": 1_700_000_000.0,
        "tabs": {
            "Systems": [
                ["Systems within 100 ly"],          # title row, skipped
                [],                                  # spacer, skipped
                SYSTEM_HEADERS,
                ["Test A", "Testia", 10.0, 1.0, "G2 V", T_SUN_K, 1.0],
                ["Test B", "", 30.0, 0.5, "K5 V", 4200, 0.1],
                ["Bin Sys", "", 20.0, 0.9, "K0 V", 5000, 0.5],
            ],
            "System stars": [
                STAR_HEADERS,
                ["Test A", "Test A", "host, planet host", "Testia", 10.0, 1.0,
                 "G2 V", T_SUN_K, 1.0],
                ["Test B", "Test B", "host, planet host", "", 30.0, 0.5,
                 "K5 V", 4200, 0.1],
                ["Bin Sys", "Bin Sys", "host", "", 20.0, 0.9, "K0 V", 5000, 0.5],
                # No orbit solved: a projected separation, drawn as a circle.
                ["Bin Sys", "Bin Sys B", "secondary, planet host", "", 20.0, 0.4,
                 "M2 V", 3400, 0.02, "", "Bin Sys", 300.0, "projected",
                 "GP24"],
            ],
            "Planets": [
                PLANET_HEADERS,
                # Full row: everything present.
                _planet("Test A b", "Test A", planet_host="Test A", lum=1.0,
                        hz="In HZ (conservative)", m_earth=1.0, r_earth=1.0,
                        period=365.25, sma=1.0, ecc=0.0167),
                # Semi-major axis missing -> derived from period.
                _planet("Test A c", "Test A", planet_host="Test A", lum=1.0,
                        hz="Closer than HZ", m_earth=5.0, period=100.0),
                # Period missing -> derived from semi-major axis.
                _planet("Test A d", "Test A", planet_host="Test A", lum=1.0,
                        hz="Farther than HZ", m_earth=2.0, sma=2.0),
                # Neither -> not plottable.
                _planet("Test A e", "Test A", planet_host="Test A", lum=1.0),
                # Absurd eccentricity -> clamped, not dropped.
                _planet("Test A f", "Test A", planet_host="Test A", lum=1.0,
                        period=50.0, sma=0.3, ecc=1.4),
                # Orbits the secondary of a binary.
                _planet("Bin Sys B b", "Bin Sys", planet_host="Bin Sys B",
                        planet_host_class="M2 V", lum=0.02, hz="In HZ",
                        m_earth=3.0, period=10.0, sma=0.05, distance=20.0),
                _planet("Test B b", "Test B", planet_host="Test B", lum=0.1,
                        period=20.0, sma=0.1),
            ],
            "Candidates": [
                PLANET_HEADERS,
                # Same planet as above but thinner: the richer row must win.
                _planet("Test A b", "Test A", planet_host="Test A", period=365.25),
                _planet("Cand X b", "Cand X", planet_host="Cand X",
                        period=8.0, sma=0.07, tier="strong"),
            ],
            # No signature match: must be ignored entirely.
            "Solvent bands": [
                ["Solvent", "Polarity", "1 bar - CONSERVATIVE (AU)"],
                ["Water", "polar", "0.9 - 1.2"],
            ],
        },
    }


@pytest.fixture
def catalog():
    return parse_workbook(make_workbook())


class TestCellParsing:
    def test_normalize_header_collapses_and_lowers(self):
        assert normalize_header("  System /  Host ") == "system/host"
        assert normalize_header("Metallicity \\[Fe/H\\]") == "metallicity [fe/h]"

    def test_number_from_numeric_cell(self):
        assert cell_number(1.5) == 1.5
        assert cell_number("2.25") == 2.25
        assert cell_number("1,024") == 1024.0

    def test_range_is_not_a_number(self):
        assert cell_number("0.696 - 1.636") is None
        assert cell_number("17.5 - 30.3") is None

    def test_blank_markers_are_none(self):
        for blank in ("", "  ", "—", "N/A", "none"):
            assert cell_number(blank) is None


class TestTableClassification:
    def test_header_row_found_below_title_and_spacer(self):
        tables = {t.title: t for t in build_tables(make_workbook())}
        assert tables["Systems"].has("system/host", "host mass (m-sun)")
        assert len(tables["Systems"].rows) == 3

    def test_roles_assigned_by_signature(self):
        roles = classify_tables(build_tables(make_workbook()))
        assert {t.title for t in roles["planets"]} == {"Planets", "Candidates"}
        assert [t.title for t in roles["stars"]] == ["System stars"]
        assert [t.title for t in roles["systems"]] == ["Systems"]

    def test_data_ends_at_a_title_row(self):
        # The Planets tab keeps reference blocks under its data with no blank
        # row between; their rows once parsed as planets of hosts like "c_inner".
        wb = make_workbook()
        wb["tabs"]["Planets"] = wb["tabs"]["Planets"] + [
            ["SOLVENT BAND CONSTANTS"],
            ["SOLVENT", "c_inner", "c_outer", "c_workable"],
            ["Water", "0.5575507229162847", "1.0382866686270509", "0"],
        ]
        n = len(parse_workbook(make_workbook()).planets_by_host)
        cat = parse_workbook(wb)
        assert len(cat.planets_by_host) == n
        assert "c_inner" not in cat.planets_by_host and "c_inner" not in cat.hosts()

    def test_known_objects_tab_is_not_a_systems_tab(self):
        # "Known within 100ly" has every Systems header, so it matches the
        # systems signature too; its rows are a reference list, not systems.
        wb = make_workbook()
        headers = SYSTEM_HEADERS[:2] + ["Plotted", "Last Updated"] + SYSTEM_HEADERS[2:]
        wb["tabs"]["Known within 100ly"] = [
            headers, ["Unplotted Star", "", False, "2026-09-28", 50.0, "", "", "", ""]]
        roles = classify_tables(build_tables(wb))
        assert "Known within 100ly" not in {t.title for g in roles.values() for t in g}
        assert "Unplotted Star" not in parse_workbook(wb).system_rows

    def test_four_plus_tab_is_not_a_stars_tab(self):
        # "4+ Stars only" has every Multi-stars header, so it matches the stars
        # signature too; its subsystem rows are pairs, not stars.
        wb = make_workbook()
        wb["tabs"]["4+ Stars only"] = [
            STAR_HEADERS + ["Node type"],
            ["Bin Sys", "Bin Sys AB", "subsystem", "", 20.0, 2.0, "", "", "", "", "", "", "", "",
             "subsystem"]]
        roles = classify_tables(build_tables(wb))
        # Its own role only: the catalog reads it for system names, so a planet
        # filed under one is left to planetless_loader (7 Oct 2026).
        assert [t.title for t in roles["four_plus"]] == ["4+ Stars only"]
        assert "4+ Stars only" not in {t.title for k, g in roles.items() if k != "four_plus" for t in g}
        cat = parse_workbook(wb)
        assert all(s.component != "Bin Sys AB" for s in cat.stars_by_host.get("Bin Sys", []))

    def test_unrelated_tab_ignored(self):
        roles = classify_tables(build_tables(make_workbook()))
        titles = {t.title for group in roles.values() for t in group}
        assert "Solvent bands" not in titles


class TestCatalogIndexing:
    def test_planets_grouped_by_the_star_they_orbit(self, catalog):
        assert "Bin Sys B" in catalog.planets_by_host
        assert "Bin Sys" not in catalog.planets_by_host
        assert catalog.system_of["Bin Sys B"] == "Bin Sys"

    def test_duplicate_planet_keeps_the_richer_row(self, catalog):
        rec = next(p for p in catalog.planets_by_host["Test A"]
                   if p.name == "Test A b")
        assert rec.semi_major_axis_au == 1.0
        assert rec.eccentricity == 0.0167

    def test_hosts_lists_only_plottable_systems(self, catalog):
        # By system, not by planet-hosting star: Bin Sys B's planet makes
        # Bin Sys plottable, and Bin Sys is what is listed.
        assert catalog.hosts() == ["Bin Sys", "Cand X", "Test A", "Test B"]

    def test_members_put_the_primary_first(self, catalog):
        assert catalog.members("Bin Sys") == ["Bin Sys", "Bin Sys B"]
        assert catalog.members("Test A") == ["Test A"]

    def test_planets_sorted_outward(self, catalog):
        names = [p.name for p in catalog.planets_by_host["Test A"]
                 if p.semi_major_axis_au]
        assert names == ["Test A f", "Test A b", "Test A d"]


class TestResolveHost:
    def test_exact_name(self, catalog):
        assert catalog.resolve_host("Test A") == "Test A"

    def test_case_and_spacing_insensitive(self, catalog):
        assert catalog.resolve_host("  test-a ") == "Test A"

    def test_planet_name_resolves_to_its_star(self, catalog):
        assert catalog.resolve_host("Test A d") == "Test A"

    def test_nickname_resolves(self, catalog):
        assert catalog.resolve_host("Testia") == "Test A"

    def test_every_name_in_a_system_reaches_the_whole_system(self, catalog):
        assert catalog.resolve_host("Bin Sys") == "Bin Sys"
        assert catalog.resolve_host("Bin Sys B") == "Bin Sys"
        assert catalog.resolve_host("Bin Sys B b") == "Bin Sys"

    def test_ambiguous_prefix_reports_candidates(self, catalog):
        with pytest.raises(ValueError, match="matches several"):
            catalog.resolve_host("Test")

    def test_unknown_name_raises(self, catalog):
        with pytest.raises(ValueError, match="not in the catalog"):
            catalog.resolve_host("Vulcan")


class TestBuildStarSystem:
    def test_star_and_planets_present(self, catalog):
        system = build_star_system(catalog, "Test A")
        assert system.source == "catalog"
        assert [s.name for s in system.get_stars()] == ["Test A"]
        assert len(system.get_planets()) == 4       # Test A e has no orbit
        assert system.distance_from_sun_ly == 10.0

    def test_star_mass_and_display_name(self, catalog):
        star = build_star_system(catalog, "Test A").get_stars()[0]
        assert star.mass_kg == pytest.approx(M_SUN_KG)
        assert star.display_name == "Testia"
        assert star.radius_km == pytest.approx(R_SUN_KM, rel=1e-6)

    def test_elements_use_sheet_values(self, catalog):
        system = build_star_system(catalog, "Test A")
        b = system.get_body("Test A b")
        assert b.elements.semi_major_axis == 1.0
        assert b.elements.period == 365.25
        assert b.elements.eccentricity == pytest.approx(0.0167)
        assert b.elements.epoch == J2000
        assert b.mass_kg == pytest.approx(M_EARTH_KG)

    def test_unknown_angles_are_zero(self, catalog):
        e = build_star_system(catalog, "Test A").get_body("Test A b").elements
        assert e.inclination == 0.0
        assert e.longitude_of_ascending_node == 0.0
        assert e.argument_of_periapsis == 0.0

    def test_mean_anomaly_is_spread_and_stable(self, catalog):
        planets = build_star_system(catalog, "Test A").get_planets()
        phases = [p.elements.mean_anomaly_at_epoch for p in planets]
        assert len(set(phases)) == len(phases)
        assert all(0.0 <= p < 360.0 for p in phases)
        again = build_star_system(catalog, "Test A").get_planets()
        assert [p.elements.mean_anomaly_at_epoch for p in again] == phases

    def test_semi_major_axis_derived_from_period(self, catalog):
        e = build_star_system(catalog, "Test A").get_body("Test A c").elements
        assert e.period == 100.0
        # a = (P / 365.25 d)^(2/3) AU around a 1 M-sun star
        assert e.semi_major_axis == pytest.approx((100.0 / 365.25) ** (2 / 3),
                                                  rel=1e-3)

    def test_period_derived_from_semi_major_axis(self, catalog):
        e = build_star_system(catalog, "Test A").get_body("Test A d").elements
        assert e.semi_major_axis == 2.0
        assert e.period == pytest.approx(365.25 * 2 ** 1.5, rel=1e-3)

    def test_eccentricity_clamped(self, catalog):
        e = build_star_system(catalog, "Test A").get_body("Test A f").elements
        assert e.eccentricity == 0.95

    def test_planet_without_orbit_is_noted_not_plotted(self, catalog):
        system = build_star_system(catalog, "Test A")
        assert "Test A e" not in [p.name for p in system.get_planets()]
        assert "No orbit data: Test A e" in system.description

    def test_description_flags_missing_orientation(self, catalog):
        system = build_star_system(catalog, "Test A")
        assert "co-planar" in system.description
        assert "arbitrary" in system.description

    def test_candidate_tier_is_hypothetical(self, catalog):
        system = build_star_system(catalog, "Cand X")
        assert system.get_body("Cand X b").status == "hypothetical"

    def test_confirmed_tier_is_confirmed(self, catalog):
        system = build_star_system(catalog, "Test A")
        assert system.get_body("Test A b").status == "confirmed"

    def test_secondary_host_uses_its_own_properties(self, catalog):
        system = build_star_system(catalog, "Bin Sys B")
        star = system.get_body("Bin Sys B")
        assert star.mass_kg == pytest.approx(0.4 * M_SUN_KG)
        assert star.luminosity_sun == 0.02

    def test_sources_point_at_the_spreadsheet(self, catalog):
        body = build_star_system(catalog, "Test A").get_body("Test A b")
        labels = [label for label, _ in body.sources]
        urls = [url for _, url in body.sources]
        assert any("Test Catalog" in label for label in labels)
        assert all("SHEET123" in url for url in urls)

    def test_host_luminosity_reaches_the_star_and_its_water_band(self, catalog):
        system = build_star_system(catalog, "Test A")
        assert system.get_stars()[0].luminosity_sun == 1.0
        core = next(z for z in system.belt_zones
                    if z.name == "Water band (1 bar)")
        # The ring where the viewer's sliders start: albedo 0.3 and Earth's
        # 33 K greenhouse offset.  With no offset it would be 0.47-0.87.
        assert (round(core.r_inner_au, 2), round(core.r_outer_au, 2)) == (0.56, 1.12)
        assert "water band at 1 bar" in system.description

    def test_dimmer_host_gets_a_tighter_band(self, catalog):
        bright = build_star_system(catalog, "Test A")        # L = 1.0
        binary = build_star_system(catalog, "Bin Sys")       # B: L = 0.02

        def core(system, star):
            z = next(z for z in system.belt_zones
                     if z.name.startswith("Water band")
                     and z.centre_body == star)
            return (z.r_inner_au, z.r_outer_au)

        assert core(binary, "Bin Sys B")[1] < core(bright, "Test A")[0]

    def test_no_band_when_the_catalog_has_no_luminosity(self):
        wb = make_workbook()
        wb["tabs"]["Systems"] = [SYSTEM_HEADERS,
                                 ["Dark", "", 15.0, 1.0, "G2 V", T_SUN_K, ""]]
        wb["tabs"]["System stars"] = [STAR_HEADERS,
                                      ["Dark", "Dark", "host, planet host", "",
                                       15.0, 1.0, "G2 V", T_SUN_K, ""]]
        wb["tabs"]["Planets"] = [PLANET_HEADERS,
                                 _planet("Dark b", "Dark", planet_host="Dark",
                                         period=365.25, sma=1.0)]
        wb["tabs"]["Candidates"] = [PLANET_HEADERS]
        system = build_star_system(parse_workbook(wb), "Dark")
        assert system.belt_zones == []
        assert "water band" not in system.description

    def test_system_without_orbit_data_is_listed_and_drawn_as_its_stars(self):
        # CD-35 2722: its one companion has no semi-major axis or period, and
        # the system used to be neither listed nor buildable.
        wb = make_workbook()
        wb["tabs"]["Planets"] = [PLANET_HEADERS,
                                 _planet("Lonely b", "Lonely",
                                         planet_host="Lonely")]
        wb["tabs"]["Candidates"] = [PLANET_HEADERS]
        cat = parse_workbook(wb)
        assert "Lonely" in cat.hosts()
        assert catalog_entry(cat, "Lonely")["planets"] == ["Lonely b"]
        system = build_star_system(cat, "Lonely")
        assert [b.body_type for b in system.bodies] == ["star"]
        assert "only the stars are drawn" in system.description
        assert "No orbit data: Lonely b." in system.description


def _multi_workbook(star_rows, planet_rows):
    """The test workbook with its stars and planets replaced."""
    wb = make_workbook()
    wb["tabs"]["System stars"] = [STAR_HEADERS] + star_rows
    wb["tabs"]["Planets"] = [PLANET_HEADERS] + planet_rows
    wb["tabs"]["Candidates"] = [PLANET_HEADERS]
    return parse_workbook(wb)


def _star(system, name, role, mass, lum, *, ecc="", frm="", sep="", typ=""):
    return [system, name, role, "", 20.0, mass, "M2 V", 3400, lum,
            ecc, frm, sep, typ, "test source" if sep else ""]


class TestWholeSystems:
    """A multi-star system is drawn whole -- every star, each planet on its own."""

    def test_a_projected_companion_is_a_hypothetical_circle(self, catalog):
        system = build_star_system(catalog, "Bin Sys")
        b = system.get_body("Bin Sys B")
        assert b.parent == "Bin Sys"
        assert b.status == "hypothetical"
        assert b.elements.semi_major_axis == 300.0
        assert b.elements.eccentricity == 0.0
        # Kepler III on both stars' masses, 0.9 + 0.4 M-sun.
        assert b.elements.period == pytest.approx(
            365.25 * (300.0 ** 3 / 1.3) ** 0.5, rel=1e-3)
        assert "projected separation" in system.description

    def test_the_companions_planet_goes_round_the_companion(self, catalog):
        from hybrasil.mechanics.time_series import is_coil_body
        system = build_star_system(catalog, "Bin Sys")
        planet = system.get_body("Bin Sys B b")
        assert planet.parent == "Bin Sys B"
        assert is_coil_body(planet, {b.name: b for b in system.bodies})

    def test_every_luminous_star_gets_its_own_band_stack(self, catalog):
        system = build_star_system(catalog, "Bin Sys")
        assert {z.centre_body for z in system.belt_zones} == {"Bin Sys", "Bin Sys B"}

    def test_a_solved_orbit_keeps_its_eccentricity(self):
        cat = _multi_workbook(
            [_star("Pair", "Pair", "host, planet host", 1.0, 1.0),
             _star("Pair", "Pair B", "companion", 0.5, 0.05, ecc=0.52,
                   frm="Pair", sep=23.3, typ="semi-major axis")],
            [_planet("Pair b", "Pair", planet_host="Pair", period=365.25, sma=1.0)])
        b = build_star_system(cat, "Pair").get_body("Pair B")
        assert b.status == "confirmed"
        assert b.elements.semi_major_axis == 23.3
        assert b.elements.eccentricity == pytest.approx(0.52)

    def test_an_assumed_separation_is_hypothetical_and_says_so(self):
        cat = _multi_workbook(
            [_star("Sus", "Sus", "host, planet host", 1.0, 1.0),
             _star("Sus", "Sus D", "suspected companion", 0.014, "",
                   frm="Sus", sep=15.0, typ="assumed")],
            [_planet("Sus b", "Sus", planet_host="Sus", period=365.25, sma=1.0)])
        system = build_star_system(cat, "Sus")
        d = system.get_body("Sus D")
        assert d.status == "hypothetical"
        assert d.elements.semi_major_axis == 15.0
        assert d.elements.eccentricity == 0.0
        assert "assumed separation" in system.description
        assert "projected separation" not in system.description

    def test_a_hierarchical_triple_places_parents_first(self):
        # C is listed before B and measured from B: B still has to come first.
        cat = _multi_workbook(
            [_star("Tri", "Tri", "host, planet host", 1.0, 1.0),
             _star("Tri", "Tri C", "companion", 0.3, 0.01,
                   frm="Tri B", sep=5.0, typ="projected"),
             _star("Tri", "Tri B", "companion", 0.3, 0.01,
                   frm="Tri", sep=500.0, typ="projected")],
            [_planet("Tri b", "Tri", planet_host="Tri", period=365.25, sma=1.0)])
        system = build_star_system(cat, "Tri")
        names = [b.name for b in system.bodies]
        assert names.index("Tri B") < names.index("Tri C")
        assert system.get_body("Tri C").parent == "Tri B"
        assert "3 stars" in system.description

    def test_a_companion_with_no_separation_is_reported_not_guessed(self):
        cat = _multi_workbook(
            [_star("Lost", "Lost", "host, planet host", 1.0, 1.0),
             _star("Lost", "Lost B", "planet host", 0.3, 0.01)],
            [_planet("Lost b", "Lost", planet_host="Lost", period=365.25, sma=1.0),
             _planet("Lost B b", "Lost", planet_host="Lost B", period=10.0, sma=0.05)])
        system = build_star_system(cat, "Lost")
        assert [s.name for s in system.get_stars()] == ["Lost"]
        assert "no separation on file: Lost B" in system.description
        assert "Lost B b" in system.description
        assert "Lost B b" not in [b.name for b in system.bodies]

    def test_a_companions_planet_is_reported_when_the_stars_tab_has_no_rows(self):
        # GJ 65 b orbits GJ 65 B, but GJ 65 has no stars-tab rows: the planet
        # must be named as not plotted, not silently dropped.
        wb = make_workbook()
        wb["tabs"]["Candidates"].append(
            _planet("Solo B b", "Solo", planet_host="Solo B", period=156.0, sma=0.27))
        wb["tabs"]["Systems"].append(["Solo", "", 9.0, 0.12, "M5.5 V", 2900, 0.001])
        cat = parse_workbook(wb)
        assert cat.members("Solo") == ["Solo", "Solo B"]
        system = build_star_system(cat, "Solo")
        assert "Solo B b" not in [b.name for b in system.bodies]
        assert "Not plotted, no separation on file: Solo B." in system.description
        assert "Not plotted because their star is not: Solo B b." in system.description

    def test_a_system_named_for_neither_star_uses_its_host(self):
        # RR Cae: the stars are 'RR Cae A' and 'RR Cae B', the circumbinary
        # planet is filed under 'RR Cae', and neither star is called that.
        cat = _multi_workbook(
            [_star("Duo", "Duo A", "host, white dwarf", 0.6, 0.001),
             _star("Duo", "Duo B", "red dwarf", 0.2, 0.004,
                   frm="Duo A", sep=0.007, typ="semi-major axis")],
            [_planet("Duo b", "Duo", period=4350.0, sma=5.3)])
        assert cat.members("Duo") == ["Duo A", "Duo B"]
        system = build_star_system(cat, "Duo b")
        assert system.get_body("Duo b").parent == "Duo A"
        assert system.get_body("Duo B").parent == "Duo A"

    def test_the_time_span_is_set_by_planets_not_by_a_companion(self, catalog):
        from hybrasil.figures import _natural_span_days
        system = build_star_system(catalog, "Bin Sys")
        # B's circle takes ~4,500 years; the planet takes 10 days.
        assert _natural_span_days(system) == pytest.approx(12.0)


MOON_HEADERS = [
    "Exomoon", "Host planet", "Host system (primary star)", "Distance (ly)",
    "Mass (M-earth)", "Mass (M-Jup)", "Mass type", "Orbital period (d)",
    "Semi-major axis (au)", "Eccentricity", "Confidence tier",
    "Orbit data source / flags",
]


def _moon(name, planet, host, *, period="", sma="", ecc="", m_jup="",
          tier="strong"):
    return [name, planet, host, 20.0, "", m_jup, "Msini (minimum)", period,
            sma, ecc, tier, "test paper"]


def _moon_catalog(*moon_rows):
    wb = make_workbook()
    wb["tabs"]["Exomoons"] = [MOON_HEADERS, *moon_rows]
    return parse_workbook(wb)


class TestExomoons:
    """The exomoon tab: each moon drawn round its planet, never round the star."""

    def test_moon_tab_is_its_own_role_not_a_planet_tab(self):
        wb = make_workbook()
        wb["tabs"]["Exomoons"] = [MOON_HEADERS,
                                  _moon("Test A b I", "Test A b", "Test A", period=5.0, sma=0.01)]
        roles = classify_tables(build_tables(wb))
        assert [t.title for t in roles["moons"]] == ["Exomoons"]
        assert "Exomoons" not in [t.title for t in roles["planets"]]

    def test_moon_goes_round_its_planet(self):
        # CD-35 2722 b I: the paper's a and P are both about the brown dwarf.
        cat = _moon_catalog(_moon("Test A b I", "Test A b", "Test A",
                                  period=171.112, sma=0.2, ecc=0.269, m_jup=0.918))
        system = build_star_system(cat, "Test A")
        moon = system.get_body("Test A b I")
        assert moon.body_type == "moon"
        assert moon.parent == "Test A b"
        assert moon.status == "hypothetical"
        assert moon.elements.semi_major_axis == 0.2
        assert moon.elements.period == 171.112
        assert moon.elements.eccentricity == pytest.approx(0.269)
        assert moon.mass_kg == pytest.approx(0.918 * 1.89813e27, rel=1e-3)
        assert "1 moon from the exomoon tab: Test A b I (strong)" in system.description

    def test_missing_period_comes_from_the_planets_mass(self):
        # Test A b is 1 Earth mass: Kepler III about it, not about the star.
        cat = _moon_catalog(_moon("Test A b I", "Test A b", "Test A", sma=0.001))
        moon = build_star_system(cat, "Test A").get_body("Test A b I")
        star_mass_period = 365.25 * 0.001 ** 1.5
        assert moon.elements.period == pytest.approx(
            star_mass_period / (M_EARTH_KG / M_SUN_KG) ** 0.5, rel=1e-3)

    def test_planet_names_match_loosely(self):
        cat = _moon_catalog(_moon("Moon X", "test a  B", "Test A", period=5.0, sma=0.01))
        assert build_star_system(cat, "Test A").get_body("Moon X").parent == "Test A b"

    def test_moon_of_an_undrawn_planet_is_not_drawn(self):
        # Test A e has no orbit, so there is nowhere to put its moon.
        cat = _moon_catalog(_moon("Test A e I", "Test A e", "Test A", period=5.0, sma=0.01))
        system = build_star_system(cat, "Test A")
        assert "Test A e I" not in [b.name for b in system.bodies]

    def test_moon_with_no_orbit_is_noted_not_drawn(self):
        cat = _moon_catalog(_moon("Test A b I", "Test A b", "Test A"))
        system = build_star_system(cat, "Test A")
        assert "Test A b I" not in [b.name for b in system.bodies]
        assert "Test A b I" in system.description

    def test_confirmed_moon_is_confirmed(self):
        cat = _moon_catalog(_moon("Test A b I", "Test A b", "Test A",
                                  period=5.0, sma=0.01, tier="confirmed"))
        assert build_star_system(cat, "Test A").get_body("Test A b I").status == "confirmed"

    def test_the_time_span_is_set_by_the_moons(self):
        from hybrasil.figures import _natural_span_days
        cat = _moon_catalog(_moon("Test A b I", "Test A b", "Test A", period=5.0, sma=0.01))
        system = build_star_system(cat, "Test A")
        # Test A's slowest planet takes 2.83 years; the moon takes 5 days.
        assert _natural_span_days(system) == pytest.approx(6.0)

    def test_an_unlikely_moon_is_not_drawn(self):
        # A refuted candidate stays on the tab as a record, and is never drawn.
        cat = _moon_catalog(_moon("Test A b I", "Test A b", "Test A",
                                  period=5.0, sma=0.01, tier="unlikely"))
        system = build_star_system(cat, "Test A")
        assert "Test A b I" not in [b.name for b in system.bodies]
        assert "Rejected moon candidates, not drawn: Test A b I." in system.description

    def test_radius_and_reference_are_read(self):
        wb = make_workbook()
        wb["tabs"]["Exomoons"] = [
            MOON_HEADERS + ["Radius (R-earth)", "Source / discovery reference"],
            _moon("Test A b I", "Test A b", "Test A", period=5.0, sma=0.01)
            + [1.7, "Limbach et al. 2021, ApJL 918, L25"]]
        moon = build_star_system(parse_workbook(wb), "Test A").get_body("Test A b I")
        assert moon.radius_km == pytest.approx(1.7 * 6371.0, rel=1e-3)
        assert any("Limbach" in s[0] for s in moon.sources)

    def test_a_moon_of_a_planet_not_in_the_catalog_is_kept_but_not_drawn(self):
        # Most candidates orbit planets far beyond 100 ly: recorded, never placed.
        cat = _moon_catalog(_moon("Far b I", "Far b", "Far", period=5.0, sma=0.01))
        assert "Far" not in cat.hosts()
        assert [m.name for m in cat.moons_by_planet["farb"]] == ["Far b I"]

    def test_the_moon_draws_as_a_closed_orbit_not_a_coil(self):
        from hybrasil.mechanics.time_series import is_coil_body
        cat = _moon_catalog(_moon("Test A b I", "Test A b", "Test A", period=5.0, sma=0.01))
        system = build_star_system(cat, "Test A")
        by_name = {b.name: b for b in system.bodies}
        assert not is_coil_body(by_name["Test A b I"], by_name)


REJECTED_HEADERS = PLANET_HEADERS + ["Rejected because"]


def _rejected_catalog(*rejected_rows, extra_planets=()):
    wb = make_workbook()
    wb["tabs"]["Rejected candidates"] = [REJECTED_HEADERS, *rejected_rows]
    wb["tabs"]["Candidates"].extend(extra_planets)
    return parse_workbook(wb)


class TestRejectedCandidates:
    """A rejected candidate is never drawn, whichever tab it turns up on."""

    def test_rejected_tab_is_its_own_role_not_a_planet_tab(self):
        wb = make_workbook()
        wb["tabs"]["Rejected candidates"] = [
            REJECTED_HEADERS,
            _planet("Test A z", "Test A", period=5.0, sma=0.05) + ["FP"]]
        roles = classify_tables(build_tables(wb))
        assert [t.title for t in roles["rejected"]] == ["Rejected candidates"]
        assert "Rejected candidates" not in [t.title for t in roles["planets"]]

    def test_a_rejected_row_builds_no_body(self):
        cat = _rejected_catalog(
            _planet("Test A z", "Test A", period=5.0, sma=0.05) + ["TFOPWG FP"])
        system = build_star_system(cat, "Test A")
        assert "Test A z" not in [b.name for b in system.bodies]
        assert "Rejected candidates, not drawn: Test A z." in system.description

    def test_a_rejected_name_pasted_back_onto_a_planet_tab_stays_undrawn(self):
        # The guard is the name, so a rejected candidate re-imported from an
        # archive onto the candidates tab does not come back.
        cat = _rejected_catalog(
            _planet("Test A z", "Test A") + ["refuted"],
            extra_planets=[_planet("test a  Z", "Test A", period=5.0, sma=0.05,
                                   tier="strong")])
        names = [b.name for b in build_star_system(cat, "Test A").bodies]
        assert not any(n.lower().replace(" ", "") == "testaz" for n in names)

    def test_unlikely_candidate_is_not_drawn(self):
        # A row tiered `unlikely` left on a live tab is rejected too.
        cat = _rejected_catalog(extra_planets=[
            _planet("Test A y", "Test A", period=5.0, sma=0.05, tier="unlikely")])
        system = build_star_system(cat, "Test A")
        assert "Test A y" not in [b.name for b in system.bodies]
        assert "Test A y" in cat.rejected_in("Test A")

    def test_a_host_with_only_rejected_candidates_is_not_listed(self):
        cat = _rejected_catalog(_planet("Ghost b", "Ghost", period=5.0, sma=0.05)
                                + ["FA"])
        assert "Ghost" not in cat.hosts()

    def test_a_rejected_name_says_why_it_is_missing(self):
        cat = _rejected_catalog(_planet("Ghost b", "Ghost", period=5.0, sma=0.05)
                                + ["SB2: the orbit is the binary's"])
        with pytest.raises(ValueError, match="rejected candidate.*SB2"):
            cat.resolve_host("Ghost b")
        with pytest.raises(ValueError, match=r"rejected candidates \(Ghost b\)"):
            cat.resolve_host("ghost")

    def test_the_other_planets_of_the_system_still_draw(self):
        cat = _rejected_catalog(_planet("Test A z", "Test A", period=5.0, sma=0.05)
                                + ["FP"])
        names = [b.name for b in build_star_system(cat, "Test A").bodies]
        assert {"Test A b", "Test A c", "Test A d"} <= set(names)


class TestPresentation:
    def test_hz_position_drives_colour(self):
        assert hz_color("In HZ (conservative)") == "#44BB66"
        assert hz_color("Closer than HZ") == "#EE7744"
        assert hz_color("Farther than HZ") == "#5588CC"
        assert hz_color("") is None

    def test_sun_radius_recovered_from_luminosity_and_temperature(self):
        assert star_radius_km(1.0, T_SUN_K) == pytest.approx(R_SUN_KM, rel=1e-6)

    def test_radius_unknown_without_inputs(self):
        assert star_radius_km(None, 5000) is None
        assert star_radius_km(1.0, None) is None

    def test_listing_covers_every_plottable_system(self, catalog):
        lines = catalog_listing(catalog)
        assert len(lines) == len(catalog.hosts())
        # One line for the binary, as its primary, counting both stars.
        line = next(line for line in lines if line.startswith("Bin Sys"))
        assert "K0 V" in line and "2 star(s)" in line


class TestEmptyWorkbook:
    def test_empty_workbook_parses_to_empty_catalog(self):
        cat = parse_workbook({"tabs": {}})
        assert isinstance(cat, Catalog)
        assert cat.hosts() == []


class TestSolarSystemArrow:
    """RA/Dec on the systems tab place the arrow back to the Sun."""

    @staticmethod
    def _with_radec(ra, dec):
        wb = make_workbook()
        rows = wb["tabs"]["Systems"]
        rows[2] = SYSTEM_HEADERS + ["RA (deg, ICRS)", "Dec (deg, ICRS)"]
        rows[3] = rows[3] + [ra, dec]
        return parse_workbook(wb)

    def test_ra_and_dec_give_a_unit_direction_in_the_ecliptic_frame(self):
        from hybrasil.mechanics.orientation import toward_sun_in_ecliptic
        system = build_star_system(self._with_radec(219.9, -60.83), "Test A")
        v = system.solar_system_direction
        assert v == pytest.approx(toward_sun_in_ecliptic(219.9, -60.83))
        assert sum(c * c for c in v) == pytest.approx(1.0)
        # The disc stays in the ecliptic: no sky frame, so the galactic-centre
        # arrow and the Milky Way keep the ecliptic values they already had.
        assert system.sky_frame_radec is None
        assert system.galactic_center_direction is None
        assert "Solar System arrow" in system.description

    def test_no_ra_or_dec_means_no_arrow(self, catalog):
        system = build_star_system(catalog, "Test A")
        assert system.solar_system_direction is None
        assert "Solar System arrow" not in system.description

    def test_a_row_with_only_one_of_the_two_has_no_arrow(self):
        system = build_star_system(self._with_radec(219.9, ""), "Test A")
        assert system.solar_system_direction is None

    def test_the_arrow_reaches_the_figure(self):
        from hybrasil.mechanics.time_series import system_positions_at
        from hybrasil.viz.static_plot import build_static_figure
        system = build_star_system(self._with_radec(219.9, -60.83), "Test A")
        fig = build_static_figure(system, system_positions_at(system, J2000), {})
        names = [t.name for t in fig.data if t.name]
        assert any(n.startswith("Solar System: 10.0 Light Years") for n in names)
