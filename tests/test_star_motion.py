# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Nearby Stellar Motion featured view: every Systems-tab star around the Sun.

Drawn in galactic Cartesian light years (docs/architecture/star-motion.md).
The data tests run on literal rows; the geometry tests run on the committed
snapshot in data/, which tests/conftest.py makes the view's source.
"""

import math

import pytest

from hybrasil.data.builtin_systems import BUILTIN_NAMES
from hybrasil.data.catalog_loader import parse_workbook
from hybrasil.data.nearby_loader import load_nearby, nearby_stars
from hybrasil.mechanics.orientation import (EQUATORIAL_TO_GALACTIC, equatorial_unit,
                                                 galactic_unit)
from hybrasil.models.nearby import NearbyStar
from hybrasil.views import FEATURED_VIEWS, build_view
from hybrasil.viz import star_motion as sm
from hybrasil.viz.three_viewer import figure_to_scene

pytest.importorskip("openpyxl")


def _angle_deg(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


@pytest.fixture(scope="module")
def snapshot_catalog():
    from hybrasil.data.snapshot import load_snapshot_workbook
    return parse_workbook(load_snapshot_workbook())


@pytest.fixture(scope="module")
def stars(snapshot_catalog):
    return nearby_stars(snapshot_catalog)


@pytest.fixture(scope="module")
def all_stars(stars):
    """The Systems-tab stars and the planetless systems: every star the view draws an arrow for."""
    from hybrasil.data.nearby_loader import load_planetless_nearby
    return stars + load_planetless_nearby()


@pytest.fixture(scope="module")
def view():
    fig, info = build_view("nearby-star-motion")
    return fig, info, figure_to_scene(fig)


# ── colours and sizes ────────────────────────────────────────────────────────

@pytest.mark.parametrize("cls,lum,kind", [
    ("O9V", "", "O"), ("B3", "", "B"), ("A1V", "", "A"), ("F8", "", "F"),
    ("G2V", "", "G"), ("K5.5V", "", "K"), ("M4.5 V", "", "M"),
    ("~M5", "", "M"),                      # estimated subtype
    ("G5V+K1V", "", "G"),                  # a composite takes the primary
    ("DAZ8+M4", "", "WD"), ("DC", "", "WD"), ("M3", "White dwarf", "WD"),
    ("L5", "", "BD"), ("T8", "", "BD"), ("M9", "Binary Brown Dwarfs", "BD"),
    ("sdK7", "", "K"), ("", "", "?"),
])
def test_spectral_kind(cls, lum, kind):
    assert sm.spectral_kind(cls, lum) == kind


def test_the_colour_scheme_asked_for():
    colour = lambda cls: sm.spectral_colour(NearbyStar(name="x", stellar_class=cls))
    assert colour("M2V") == "#FF4A3A"                    # red
    assert colour("K2V") == "#FFA040"                    # orange
    assert colour("G8V") == "#FFE24A"                    # yellow
    assert colour("F5V") == "#FAF3C0"                    # pale yellow
    for hot in ("O5", "B2", "A0"):                       # whiter and bluer
        r, g, b = (int(colour(hot)[i:i + 2], 16) for i in (1, 3, 5))
        assert b == 255 and r > 150 and g > 150
    assert colour("DA") == "#9A9A9A"                     # grey
    assert sm.spectral_colour(NearbyStar(name="Sun", stellar_class="G2V", is_sun=True)) == "#33DD55"


def test_sizes_grow_with_luminosity_and_are_clamped():
    sizes = [sm.marker_size(l) for l in (1e-5, 0.01, 0.1, 1.0, 10.0, 500.0, 1e6)]
    assert sizes == sorted(sizes)
    assert sizes[0] == 3.0 and sizes[-1] == 14.0 and sm.marker_size(1.0) == 7.0
    assert sm.marker_size(None) == 5.0


# ── geometry ────────────────────────────────────────────────────────────────

def test_positions_agree_with_ra_and_dec(stars, snapshot_catalog):
    # The sheet's galactic columns are computed from RA/Dec; the repo's own
    # rotation must land in the same place, to the sheet's 2-decimal rounding.
    worst, n = 0.0, 0
    for s in stars:
        row = snapshot_catalog.system_rows[s.name]
        if s.is_sun or row.get("ra_deg") is None or s.l_deg is None:
            continue
        e = equatorial_unit(row["ra_deg"], row["dec_deg"])
        g = tuple(sum(EQUATORIAL_TO_GALACTIC[i][k] * e[k] for k in range(3)) for i in range(3))
        worst = max(worst, _angle_deg(g, galactic_unit(s.l_deg, s.b_deg)))
        n += 1
    assert n >= 360 and worst < 0.01


def test_the_sun_is_the_origin(stars):
    sun = [s for s in stars if s.is_sun]
    assert len(sun) == 1 and sm.position_ly(sun[0]) == (0.0, 0.0, 0.0)


def test_a_star_sits_at_its_distance(stars):
    for s in stars:
        if s.has_position and not s.is_sun:
            assert math.dist((0, 0, 0), sm.position_ly(s)) == pytest.approx(s.distance_ly)


def test_arrow_length_is_speed_times_fifty_thousand_years():
    s = NearbyStar(name="x", distance_ly=10, l_deg=0, b_deg=0,
                   speed_kms=40.0, motion_l_deg=90, motion_b_deg=0)
    pts = sm.arrow_points(sm.position_ly(s), sm.velocity_kms(s))
    base, tip = pts[0], pts[1]
    assert math.dist(base, tip) == pytest.approx(40.0 * 50_000 / 299_792.458)
    assert sm.LY_PER_KMS == pytest.approx(0.166782, rel=1e-5)
    # ...pointing along the motion, (l, b) = (90, 0) -> +y
    d = tuple((t - b) / math.dist(base, tip) for t, b in zip(tip, base))
    assert d == pytest.approx((0.0, 1.0, 0.0), abs=1e-12)
    # the head is drawn back through the tip, as one polyline
    assert pts[3] == tip and len(pts) == 5


def _arrows(fig, frame):
    return [t for t in fig.data if isinstance(t.meta, dict) and t.meta.get("owner")
            and t.meta.get("frame") == frame]


def _vector(t):
    base, tip = (t.x[0], t.y[0], t.z[0]), (t.x[1], t.y[1], t.z[1])
    return tuple((b - a) / sm.LY_PER_KMS for a, b in zip(base, tip))


def test_every_arrow_in_the_figure_is_proportional_to_speed(view, all_stars):
    fig = view[0]
    by_name = {s.name: s for s in all_stars}
    arrows = _arrows(fig, sm.FRAME_SUN)
    assert len(arrows) == sum(1 for s in all_stars if s.has_motion and not s.is_sun)
    for t in arrows:
        s = by_name[t.meta["owner"]]
        length = math.dist((t.x[0], t.y[0], t.z[0]), (t.x[1], t.y[1], t.z[1]))
        assert length == pytest.approx(s.speed_kms * sm.LY_PER_KMS)
        d = tuple((b - a) / length for a, b in zip((t.x[0], t.y[0], t.z[0]), (t.x[1], t.y[1], t.z[1])))
        assert d == pytest.approx(galactic_unit(s.motion_l_deg, s.motion_b_deg), abs=1e-9)


def test_every_arrow_is_drawn_in_exactly_the_two_frames(view):
    frames = {t.meta["frame"] for t in view[0].data if isinstance(t.meta, dict) and t.meta.get("owner")}
    assert frames == {k for k, _ in sm.MOTION_FRAMES} == {sm.FRAME_SUN, sm.FRAME_LSR}


def test_an_lsr_arrow_is_the_heliocentric_one_plus_the_suns_motion(view, all_stars):
    # The LSR frame adds one published constant and nothing else.
    by_name = {s.name: s for s in all_stars}
    lsr = _arrows(view[0], sm.FRAME_LSR)
    helio = {t.meta["owner"]: _vector(t) for t in _arrows(view[0], sm.FRAME_SUN)}
    assert len(lsr) == len(helio) + 1                       # ...and the Sun's own
    for t in lsr:
        if t.meta["owner"] == sm.SUN_NAME:
            continue
        want = tuple(h + s for h, s in zip(helio[t.meta["owner"]], sm.SUN_PECULIAR_KMS))
        assert _vector(t) == pytest.approx(want, abs=1e-9)
        assert (t.x[0], t.y[0], t.z[0]) == pytest.approx(sm.position_ly(by_name[t.meta["owner"]]))


def test_the_solar_system_has_a_green_arrow_only_in_the_lsr_frame(view):
    sun = [t for t in view[0].data if isinstance(t.meta, dict) and t.meta.get("owner") == sm.SUN_NAME]
    assert len(sun) == 1 and sun[0].meta["frame"] == sm.FRAME_LSR
    assert sun[0].line.color == sm.SUN_COLOUR
    assert (sun[0].x[0], sun[0].y[0], sun[0].z[0]) == (0.0, 0.0, 0.0)
    assert _vector(sun[0]) == pytest.approx(sm.SUN_PECULIAR_KMS)
    # Schoenrich et al. 2010: about 18 km/s toward the solar apex, l ~ 48, b ~ 24.
    speed, l, b = sm.speed_and_direction(sm.SUN_PECULIAR_KMS)
    assert speed == pytest.approx(18.04, abs=0.01)
    assert (l, b) == pytest.approx((47.8, 23.7), abs=0.1)


def test_a_star_without_motion_has_no_arrow(view, stars):
    fig = view[0]
    owners = {t.meta["owner"] for t in fig.data if isinstance(t.meta, dict) and t.meta.get("owner")}
    still = [s.name for s in stars if s.has_position and not s.has_motion and not s.is_sun]
    assert still and not owners & set(still)


# ── data ────────────────────────────────────────────────────────────────────

SYSTEM_HEADERS = [
    "System / Host", "Nickname (IAU)", "Distance (ly)", "Host mass (M-sun)", "Stellar Class",
    "Luminosity class", "Age (Gyr)", "Metallicity [Fe/H]", "Host luminosity (L-sun)",
    "Confirmed planets", "Radial velocity (km/s)", "Total proper motion, μ (arcsec/yr)",
    "Space velocity (km/s)", "Galactic longitude l (deg)", "Galactic latitude b (deg)",
    "Motion toward l (deg, heliocentric)", "Motion toward b (deg, heliocentric)", "Kinematics source",
]
STAR_HEADERS = ["System / Host", "Star (component)", "Role in system", "Mass (M-sun)",
                "Stellar Class", "Luminosity (L-sun)"]
PLANET_HEADERS = ["Planet", "Host system (primary star)", "Planet-host star",
                  "Orbital period (d)", "Confidence tier"]


def _workbook():
    return {"title": "test", "tabs": {
        "Systems": [SYSTEM_HEADERS,
                    ["Sun", "", 0, 1.0, "G2V", "Main sequence", 4.6, 0.0, 1.0, 8,
                     "", "", "", "", "", "", "", ""],
                    ["Bin A", "Nick", 12.5, 1.1, "K1V", "Main sequence", 3.0, -0.2, 0.003, 1,
                     -20.0, 0.5, 30.0, 45.0, -10.0, 200.0, 5.0, "RV: Gaia DR3; PM: Gaia DR3"],
                    ["Lone", "", 40.0, 0.3, "M3V", "", "", "", 0.01, 1,
                     "", 0.2, "", 120.0, 30.0, "", "", "PM: Gaia DR3"]],
        "Stars": [STAR_HEADERS,
                  ["Bin A", "Bin A", "host", 1.1, "K1V", 0.45],
                  ["Bin A", "Bin B", "secondary, planet host", 0.2, "M4V", 0.003]],
        "Planets": [PLANET_HEADERS,
                    ["Bin B b", "Bin A", "Bin B", 10.0, "confirmed"],
                    ["Bin A c", "Bin A", "Bin A", 50.0, "strong"],
                    ["Earth", "Sun", "Sun", 365.25, "Solar System reference"]],
    }}


def test_the_loader_reads_every_field_by_header():
    by = {s.name: s for s in nearby_stars(parse_workbook(_workbook()))}
    a = by["Bin A"]
    assert (a.distance_ly, a.l_deg, a.b_deg) == (12.5, 45.0, -10.0)
    assert (a.speed_kms, a.motion_l_deg, a.motion_b_deg) == (30.0, 200.0, 5.0)
    assert (a.radial_velocity_kms, a.total_pm_arcsec_yr) == (-20.0, 0.5)
    assert (a.age_gyr, a.metallicity, a.nickname) == (3.0, -0.2, "Nick")
    assert a.partners == ["Bin B"]
    assert a.planets == ["Bin A c (strong candidate)", "Bin B b"] or \
        sorted(a.planets) == sorted(["Bin A c (strong candidate)", "Bin B b"])
    assert by["Sun"].is_sun and by["Sun"].planets == ["Earth"]
    assert not by["Lone"].has_motion and by["Lone"].has_position


def test_the_primarys_own_luminosity_not_the_planet_hosts():
    # The Systems row's 'Host luminosity' is the planet host's (Bin B, 0.003);
    # the view shows Bin A's own, from the stars tab (alf Cen A carried
    # Proxima's 0.0015 this way).
    a = next(s for s in nearby_stars(parse_workbook(_workbook())) if s.name == "Bin A")
    assert a.luminosity_sun == 0.45 and a.mass_sun == 1.1


def test_a_live_sheet_that_fails_falls_back_to_the_snapshot(monkeypatch):
    from hybrasil.data import catalog_loader
    monkeypatch.delenv("HYBRASIL_DATA_SOURCE", raising=False)
    monkeypatch.delenv("HYBRASIL_NEARBY_SOURCE", raising=False)

    def broken(*a, **k):
        raise RuntimeError("no credential")
    monkeypatch.setattr(catalog_loader, "get_catalog", broken)
    stars, source = load_nearby()
    assert source.startswith("snapshot hybrasil-") and len(stars) >= 360


def test_a_given_catalog_is_used_as_is():
    stars, source = load_nearby(parse_workbook(_workbook()))
    assert source == "sheet test" and len(stars) == 3


# ── the info panel ──────────────────────────────────────────────────────────

def test_the_info_panel_has_every_field_asked_for(view):
    info = view[1]
    rows = {r[0]: r[1] for r in info["TRAPPIST-1"]["rows"]}
    for label in ("Spectral type", "Age", "Mass", "Metallicity [Fe/H]", "Stellar partners",
                  "Planets", "Luminosity", "Speed", "Direction of motion", "U, V, W"):
        assert label in rows, label
    assert rows["Speed"].endswith("km/s") and rows["Direction of motion"].startswith("toward l ")
    assert "TRAPPIST-1 e" in rows["Planets"]


def test_a_star_without_motion_says_why(view):
    # TOI-1256 has a proper motion but no radial velocity anywhere in SIMBAD.
    rows = {r[0]: r for r in view[1]["TOI-1256"]["rows"]}
    assert rows["Speed"][1] == "no data" and "on file" in rows["Speed"][2]


def test_a_star_in_a_multiple_system_names_its_partners(view):
    rows = {r[0]: r for r in view[1]["alf Cen A"]["rows"]}
    assert "Proxima Cen" in rows["Stellar partners"][1]
    assert rows["Luminosity"][1].startswith("1.5")      # A's own, not Proxima's


def test_the_sun_is_named_solar_system_and_is_the_origin(view):
    rows = {r[0]: r[1] for r in view[1][sm.SUN_NAME]["rows"]}
    assert rows["Position"] == "the origin"


# ── the scene ───────────────────────────────────────────────────────────────

def test_each_star_names_its_own_system_for_go_to_system(view):
    info = view[1]
    assert info[sm.SUN_NAME]["goto"] == "solar"
    assert info["alf Cen A"]["goto"] == "alpha-centauri"
    assert info["TRAPPIST-1"]["goto"] == "trappist-1"
    assert info["tau Cet"]["goto"] == "catalog:tau Cet"


def test_every_catalog_system_is_reachable_from_its_star(snapshot_catalog):
    # The ids are the web app's own: every system its index lists that has a
    # star in the view is one "Go to system" can open.
    from tests.test_web_app import _library
    lib = _library(catalog_loader=lambda: snapshot_catalog)
    ids = {e["id"] for e in lib.index()}
    _, info = build_view("nearby-star-motion", snapshot_catalog)
    targets = {e["goto"] for e in info.values()}
    reachable = targets & ids
    # Proxima is reached as Alpha Centauri; Castor's stars are on the
    # Planetless 4+ Stars tab rather than the Systems tab the view plots.
    assert set(BUILTIN_NAMES) - {"proxima-centauri", "castor"} <= reachable
    assert len(reachable) > 380
    # A star whose planets were all rejected has no system to open.
    assert info["GJ 680"]["goto"] not in ids


def test_the_scene_is_in_light_years_in_the_galactic_frame(view):
    scene = view[2]
    assert scene["units"] == "ly"
    assert scene["sky"]["galactic_to_frame"] == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    assert scene["groupHeading"] == "Stars by spectral class"


def test_stars_are_grouped_by_class_and_only_the_sun_is_labelled(view):
    scene = view[2]
    sun = [b for b in scene["bodies"] if b["name"] == sm.SUN_NAME]
    assert len(sun) == 1 and sun[0]["label"] and sun[0]["color"] == sm.SUN_COLOUR
    others = [b for b in scene["bodies"] if b["name"] != sm.SUN_NAME and not b.get("optional")]
    assert all(b["group"] and not b["label"] and not b["legend"] for b in others)
    assert {b["group"] for b in others} <= {g for g, _ in sm.CLASS_COLOURS.values()}


def test_arrows_are_owned_and_grouped(view):
    arrows = [l for l in view[2]["lines"] if l.get("owner")]
    assert arrows and all(l["group"] == sm.MOTION_GROUP for l in arrows)
    assert {l["frame"] for l in arrows} == {sm.FRAME_SUN, sm.FRAME_LSR}
    assert {l["name"] for l in view[2]["lines"] if l["legend"]} == {r[0] for r in sm.REFERENCE}


def test_the_scene_offers_the_galaxy_motion_type_button(view):
    mf = view[2]["motionFrames"]
    assert mf["title"] == "Galaxy Motion Type" and mf["default"] == sm.FRAME_SUN
    assert [(o["key"], o["label"]) for o in mf["options"]] == [
        ("sun", "Solar Reference"), ("lsr", "Local Standard of Rest (LSR)")]


# ── Play: the stars slide along their arrows ─────────────────────────────────

def test_play_carries_every_star_to_its_arrows_tip_in_each_frame(view):
    scene = view[2]
    assert scene["drift"] == {"years": sm.ARROW_YEARS, "steps": sm.DRIFT_STEPS}
    bodies = {b["name"]: b for b in scene["bodies"]}
    arrows = {(l["owner"], l["frame"]): l["pts"] for l in scene["lines"] if l.get("owner") and l.get("frame")}
    assert arrows
    for (owner, frame), pts in arrows.items():
        b = bodies[owner]
        tip = [b["pos"][k] + b["drift"][frame][k] for k in range(3)]
        assert tip == pytest.approx(pts[3:6], abs=0.02), (owner, frame)     # the arrow's second point is its tip
    # No arrow, no drift: a star with no measured motion, and the Sun relative to itself, stay put.
    for name, b in bodies.items():
        assert set(b.get("drift", {})) == {f for (o, f) in arrows if o == name}, name


def test_a_cloud_point_drifts_to_its_arrows_tip_or_not_at_all():
    from hybrasil.data.nearby_loader import known_nearby
    cat = parse_workbook(_sourced_workbook())
    clouds = sm.known_clouds(known_nearby(cat))
    for c in clouds:
        for frame, _ in sm.MOTION_FRAMES:
            assert len(c["drift"][frame]) == len(c["pos"])
    sure = clouds[0]
    seg = sure["arrows"][sm.FRAME_SUN]
    tip = [sure["pos"][k] + sure["drift"][sm.FRAME_SUN][k] for k in range(3)]
    assert tip == pytest.approx(seg[3:6], abs=0.02)


def test_the_panels_give_the_lsr_motion(view):
    sun = {r[0]: r for r in view[1][sm.SUN_NAME]["rows"]}
    assert sun["Speed (LSR)"][1] == "18.04 km/s" and "solar apex" in sun["Direction (LSR)"][2]
    star = {r[0]: r for r in view[1]["TRAPPIST-1"]["rows"]}
    assert star["Speed (LSR)"][1].endswith("km/s") and star["Direction (LSR)"][1].startswith("toward l ")


# ── the planetless systems, behind their button ─────────────────────────────

def test_every_planetless_system_is_offered_with_a_position_and_a_motion(view):
    from hybrasil.data.nearby_loader import load_planetless_nearby
    extra = load_planetless_nearby()
    assert len(extra) == 80 and all(s.planetless and s.has_position and s.has_motion for s in extra)
    opt = [b for b in view[2]["bodies"] if b.get("optional") == sm.PLANETLESS_SET]
    assert sorted(b["name"] for b in opt) == sorted(s.name for s in extra)


def test_the_planetless_set_is_one_ringed_group_off_by_default(view):
    sets = [o for o in view[2]["optionalSets"] if o["key"] == sm.PLANETLESS_SET]
    assert sets == [{"key": sm.PLANETLESS_SET, "label": "High Star Count Systems", "default": False, "count": 80,
                     "title": sets[0]["title"]}]
    opt = [b for b in view[2]["bodies"] if b.get("optional")]
    assert {b["group"] for b in opt} == {sm.PLANETLESS_GROUP}
    assert {b["edge"] for b in opt} == {sm.PLANETLESS_RING} and all(b["fill"] for b in opt)
    assert "+80 high star count systems on request" in view[2]["title"]
    # The Systems-tab count in the title is unchanged by them.
    assert "426 systems within 100 ly" in view[2]["title"]


def test_a_planetless_systems_arrows_are_owned_by_it(view):
    names = {b["name"] for b in view[2]["bodies"] if b.get("optional")}
    arrows = [l for l in view[2]["lines"] if l.get("owner") in names]
    assert len(arrows) == 2 * len(names)                     # one per frame
    assert all(l["group"] == sm.MOTION_GROUP for l in arrows)


def test_a_planetless_systems_panel_and_go_to_system(view):
    info = view[1]
    castor = {r[0]: r for r in info["alf Gem"]["rows"]}
    # Cc, a brown dwarf, is a planet since 7 Oct 2026 (docs/hybrasil-instructions.md section 6).
    assert castor["Name"][1] == "Castor" and castor["System"][1] == "6 stars, 1 planet (brown dwarf)"
    assert castor["Speed"][1].endswith("km/s") and castor["Planets"][1] == "1 confirmed: alf Gem Cc"
    assert {r[0]: r for r in info["1 Hya"]["rows"]}["System"][1] == "6 stars, no known planet"
    # Castor opens as the featured Castor; every other system as itself.
    assert info["alf Gem"]["goto"] == "castor"
    assert info["GJ 570"]["goto"] == "planetless:GJ 570"


def test_planetless_kinematics_are_the_tabs_own_columns():
    from hybrasil.data.planetless_loader import parse_planetless
    head = ["System / Host", "Star (component)", "Role in system", "Node type", "Mass (M-sun)", "Distance (ly)",
            "Stellar Class", "Galactic longitude l (deg)", "Galactic latitude b (deg)", "Space velocity (km/s)",
            "Motion toward l (deg, heliocentric)", "Motion toward b (deg, heliocentric)",
            "Radial velocity (km/s)", "Kinematics source"]
    rows = [["X", "X A", "host (most massive star)", "star", 1.0, 20.0, "G2V", 10.0, -5.0, 30.0, 200.0, 4.0,
             -12.0, "RV: MSC; PM: MSC"],
            ["X", "X B", "star", "star", 0.5, 20.0, "M1V", "", "", "", "", "", "", ""]]
    from hybrasil.data.nearby_loader import planetless_nearby
    (s,) = planetless_nearby(parse_planetless({"tabs": {"Planetless 4+ Stars": [head] + rows}}))
    assert (s.name, s.distance_ly, s.l_deg, s.b_deg, s.speed_kms, s.motion_l_deg, s.motion_b_deg) == \
        ("X", 20.0, 10.0, -5.0, 30.0, 200.0, 4.0)
    assert s.radial_velocity_kms == -12.0 and s.partners == ["X B"] and s.system_id == "planetless:X"
    assert s.mass_sun == 1.0 and s.kinematics_source == "RV: MSC; PM: MSC"


# ── the unclassified objects of the Known within 100ly tab ─────────────────

KNOWN_HEADERS = ["System / Host", "Nickname (IAU)", "Plotted", "Last Updated", "Distance (ly)",
                 "Radial velocity (km/s)", "Total proper motion, μ (arcsec/yr)", "Space velocity (km/s)",
                 "Galactic longitude l (deg)", "Galactic latitude b (deg)", "Motion toward l (deg, heliocentric)",
                 "Motion toward b (deg, heliocentric)", "Kinematics source"]


def _known_workbook():
    wb = _workbook()
    wb["tabs"]["Known within 100ly"] = [
        KNOWN_HEADERS,
        ["Bin A", "", True, "2026-09-28", 12.5, -20.0, 0.5, 30.0, 45.0, -10.0, 200.0, 5.0, "RV: Gaia DR3"],
        ["Faint 1", "", False, "2026-10-08", 20.0, 15.0, 0.3, 40.0, 100.0, 20.0, 10.0, -5.0,
         "RV: Gaia DR3; PM: Gaia DR3"],
        ["Faint 2", "", False, "2026-10-08", 30.0, "", 1.2, "", 200.0, -30.0, "", "", "RV: none found; PM: Gaia DR3"],
        ["Bin B", "", False, "2026-09-28", 12.5, "", "", "", 45.0, -10.0, "", "", ""],     # drawn as Bin A's star
        ["No position", "", False, "2026-09-28", 50.0, "", "", "", "", "", "", "", ""],
    ]
    return wb


def test_the_known_tabs_unplotted_rows_are_read_and_nothing_drawn_twice():
    from hybrasil.data.nearby_loader import known_nearby
    cat = parse_workbook(_known_workbook())
    known = {s.name: s for s in known_nearby(cat)}
    # Plotted rows and an unplotted row any other tab draws (Bin B, a Stars-tab component) are left out.
    assert set(known) == {"Faint 1", "Faint 2", "No position"}
    f1, f2 = known["Faint 1"], known["Faint 2"]
    assert f1.known and (f1.distance_ly, f1.l_deg, f1.b_deg, f1.speed_kms) == (20.0, 100.0, 20.0, 40.0)
    assert (f1.motion_l_deg, f1.motion_b_deg, f1.radial_velocity_kms) == (10.0, -5.0, 15.0)
    assert f2.has_position and not f2.has_motion and f2.total_pm_arcsec_yr == 1.2
    assert not known["No position"].has_position
    # It is still never a source of systems.
    assert "Faint 1" not in cat.system_rows and "faint1" not in cat.stars_by_component


def test_the_known_objects_are_one_purple_cloud_behind_their_own_button():
    from hybrasil.data.nearby_loader import known_nearby
    cat = parse_workbook(_known_workbook())
    fig = sm.build_star_motion_figure(nearby_stars(cat), "sheet test", (), known_nearby(cat))
    scene = figure_to_scene(fig)
    (c,) = scene["clouds"]
    assert c["key"] == c["optional"] == sm.KNOWN_SET and c["color"] == sm.UNCLASSIFIED_COLOUR
    assert [r[0] for r in c["info"]] == ["Faint 1", "Faint 2"]           # only objects with a position
    assert len(c["pos"]) == 6 and c["moving"] == 1
    # Positions as every star's: distance along (l, b).
    assert c["pos"][:3] == [round(x, 3) for x in sm.position_ly(known_nearby(cat)[0])]
    # One arrow (three segments, six points) per frame, for the one object with a velocity, the LSR one
    # being its heliocentric velocity plus the Sun's.
    assert {k: len(v) for k, v in c["arrows"].items()} == {sm.FRAME_SUN: 18, sm.FRAME_LSR: 18}
    f1 = known_nearby(cat)[0]
    for frame, v in ((sm.FRAME_SUN, sm.velocity_kms(f1)), (sm.FRAME_LSR, sm.velocity_lsr_kms(f1))):
        base, tip = c["arrows"][frame][0:3], c["arrows"][frame][3:6]
        length = math.dist(base, tip)
        assert length == pytest.approx(math.sqrt(sum(x * x for x in v)) * sm.LY_PER_KMS, abs=0.02)
    # Its button is off by default and counts the cloud; the classified stars are untouched by it.
    (opt,) = scene["optionalSets"]
    assert (opt["key"], opt["label"], opt["default"], opt["count"]) == (sm.KNOWN_SET, "All Known Systems within 100 ly",
                                                                        False, 2)
    assert "+2 unclassified objects on request" in scene["title"]
    assert "modes" not in opt                      # nothing unconfirmed: a plain on/off button
    assert not any(b.get("optional") for b in scene["bodies"])
    assert {b["name"] for b in scene["bodies"]} == {sm.SUN_NAME, "Bin A", "Lone"}
    # The info row the viewer builds the panel from, and the sources it indexes into.
    f2 = c["info"][1]
    assert f2[:4] == ["Faint 2", 30.0, 200.0, -30.0] and f2[4] is None and f2[8] == 1200.0
    assert c["sources"][f2[9]] == "RV: none found; PM: Gaia DR3"


def test_no_known_objects_means_no_cloud():
    from hybrasil.data.nearby_loader import load_nearby
    stars, source = load_nearby()
    scene = figure_to_scene(sm.build_star_motion_figure(stars, source))
    assert scene["clouds"] == []


def test_no_planetless_systems_means_no_button():
    from hybrasil.data.nearby_loader import load_nearby
    stars, source = load_nearby()
    scene = figure_to_scene(sm.build_star_motion_figure(stars, source))
    assert scene["optionalSets"] is None and not any(b.get("optional") for b in scene["bodies"])


def test_a_star_system_scene_is_unchanged():
    from hybrasil.data.builtin_systems import get_builtin_system
    from hybrasil.figures import build_figure
    from hybrasil.mechanics.units import J2000
    scene = figure_to_scene(build_figure(get_builtin_system("trappist-1"), J2000, J2000 + 5, frames=3))
    assert scene["units"] == "AU" and scene["groupHeading"] is None
    assert scene["motionFrames"] is None
    # Its optional sets are the photosynthesis rings and the reference orbits, menu features of lines.
    assert [o["key"] for o in scene["optionalSets"]] == ["photosynthesis", "reference-neptune", "reference-earth",
                                                         "reference-mercury"]
    assert {o["menu"] for o in scene["optionalSets"]} == {"features"}
    assert not any("group" in b or "optional" in b for b in scene["bodies"])
    assert not any("owner" in l or "group" in l or "frame" in l
                   for l in scene["lines"] if not l.get("optional"))


# ── registration ────────────────────────────────────────────────────────────

def test_it_is_registered_as_a_featured_view():
    assert list(FEATURED_VIEWS) == ["nearby-star-motion"]
    assert FEATURED_VIEWS["nearby-star-motion"][0] == "Nearby Stellar Motion"


def test_the_web_app_lists_and_serves_it():
    from tests.test_web_app import _library
    lib = _library(use_catalog=False)
    entry = next(e for e in lib.index() if e["id"] == "nearby-star-motion")
    assert entry["featured"] and entry["name"] == "Nearby Stellar Motion"
    p = lib.scene("nearby-star-motion")
    assert p["scene"]["units"] == "ly" and "TRAPPIST-1" in p["body_info"]
    assert "snapshot" in p["scene"]["title"]


# ── sources: where each star is on record ───────────────────────────────────

def test_every_star_and_planetless_system_links_a_catalog_that_lists_it(view):
    # The Sun aside, every panel's Sources opens with at least one 'Exists:' link (data/existence/ wrote the
    # identifier columns, 9 Oct 2026): SIMBAD, Gaia DR3, CNS5, the MSC or the NASA Exoplanet Archive.
    info = view[1]
    missing = [n for n, e in info.items() if n != sm.SUN_NAME
               and not any(lbl.startswith("Exists: ") for lbl, _ in e.get("sources", []))]
    assert not missing, missing[:10]
    assert len(info) > 500                                           # Systems stars and planetless systems both
    tau = dict(info["tau Cet"]["sources"])
    assert any(lbl.startswith("Exists: SIMBAD") for lbl in tau)
    assert any(lbl.startswith("Exists: NASA Exoplanet Archive") for lbl in tau)
    assert any(lbl.startswith(("Radial velocity", "Proper motion")) for lbl in tau)
    assert info[sm.SUN_NAME]["sources"][0][0].startswith("Motion: Schönrich")


def test_a_planetless_system_is_on_record_in_the_multiple_star_catalog(view):
    planetless = [e for e in view[1].values() if any("Planetless 4+ Stars tab" in r[2] for r in e["rows"])]
    assert len(planetless) >= 70
    for e in planetless:
        assert any(lbl.startswith("Exists: Multiple Star Catalog") for lbl, _ in e["sources"])


SOURCE_HEADERS = ["Gaia DR3 source_id", "SIMBAD main_id", "CNS5 id", "Existence", "Kinematics refs"]


def _sourced_workbook():
    wb = _known_workbook()
    tab = wb["tabs"]["Known within 100ly"]
    ids = {"Faint 1": ["111", "* fnt 1", "CNS5 7", "confirmed: SIMBAD, CNS5, Gaia DR3",
                       "RV: Gaia DR3; PM: 2007A&A...474..653V"],
           "Faint 2": ["222", "", "", "unconfirmed: only cited in Gaia DR3 (fidelity_v2 0.03)", "PM: Gaia DR3"]}
    tab[0] = tab[0] + SOURCE_HEADERS
    for r in tab[1:]:
        r += ids.get(r[0], [""] * 5)
    return wb


def test_the_known_tabs_source_columns_are_read_by_header():
    from hybrasil.data.nearby_loader import known_nearby
    known = {s.name: s for s in known_nearby(parse_workbook(_sourced_workbook()))}
    f1, f2 = known["Faint 1"], known["Faint 2"]
    assert (f1.gaia_id, f1.simbad_id, f1.cns5_id) == ("111", "* fnt 1", "CNS5 7")
    assert f1.kinematics_refs == "RV: Gaia DR3; PM: 2007A&A...474..653V"
    assert not f1.existence_unconfirmed and f2.existence_unconfirmed


def test_objects_only_gaia_lists_are_an_aquamarine_cloud_behind_the_same_button():
    from hybrasil.data.nearby_loader import known_nearby
    cat = parse_workbook(_sourced_workbook())
    scene = figure_to_scene(sm.build_star_motion_figure(nearby_stars(cat), "sheet test", (), known_nearby(cat)))
    sure, doubt = scene["clouds"]
    assert (sure["color"], doubt["color"]) == (sm.UNCLASSIFIED_COLOUR, "#7FFFD4")
    assert sure["optional"] == doubt["optional"] == sm.KNOWN_SET
    assert [r[0] for r in sure["info"]] == ["Faint 1"] and [r[0] for r in doubt["info"]] == ["Faint 2"]
    assert doubt["name"] == "Existence unconfirmed (Gaia DR3 only)"
    assert doubt["slug"] == ["Existence unconfirmed", "Only cited in Gaia DR3"] and "slug" not in sure
    (opt,) = scene["optionalSets"]
    assert opt["count"] == 2 and "1 in aquamarine" in opt["title"]
    # Its button cycles All -> Excluding unconfirmed -> Unconfirmed only, each mode naming the clouds it shows.
    assert [(m["key"], m["label"], m.get("clouds")) for m in opt["modes"]] == [
        ("all", "All", None), ("confirmed", "Excluding unconfirmed", [sure["key"]]),
        ("unconfirmed", "Unconfirmed only", [doubt["key"]])]
    # A point's links are its template with its ids swapped in, as the viewer does it.
    row = sure["info"][0]
    assert row[11:14] == ["111", "* fnt 1", "7"]
    tmpl = sure["linkTemplates"][row[10]]
    from hybrasil.data import star_sources as ss
    filled = [[lbl.replace("@GAIA@", "111").replace("@SIMBAD@", "* fnt 1").replace("@CID@", "7"),
               url.replace("%40GAIA%40", "111").replace("%40SIMBAD%40", "%2A%20fnt%201").replace("%40CID%40", "7")]
              for lbl, url in tmpl]
    assert filled == ss.existence_sources(simbad_id="* fnt 1", gaia_id="111", cns5_id="7") + \
        ss.kinematics_sources("RV: Gaia DR3; PM: 2007A&A...474..653V", gaia_id="111")
    assert doubt["existence"][doubt["info"][0][14]].endswith("(fidelity_v2 0.03)")


def test_the_snapshots_unconfirmed_objects_are_all_doubtful_gaia_sources(view):
    clouds = {c["key"]: c for c in view[2]["clouds"]}
    doubt, sure = clouds[sm.UNCONFIRMED_KEY], clouds[sm.KNOWN_SET]
    assert len(doubt["info"]) == 689
    import re
    fid = [float(re.search(r"fidelity_v2 ([\d.]+)", doubt["existence"][r[14]]).group(1)) for r in doubt["info"]]
    assert max(fid) < 0.5
    # Every one has a Gaia DR3 row and nothing else; every purple point has a curated catalog.
    assert all(r[11] and not r[12] and not r[13] for r in doubt["info"])
    assert all(sure["existence"][r[14]].startswith("confirmed:") for r in sure["info"])
    assert all(any(l.startswith("Exists: ") for l, _ in sure["linkTemplates"][r[10]]) for r in sure["info"])
