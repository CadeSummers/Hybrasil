# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Every system on the workbook's "Planetless 4+ Stars" tab, as a drawable StarSystem.

The tab describes each system as a tree of pairs, one row per node (a star or a subsystem), and by 30 Sep 2026
every pair carries a complete orbit: measured where a catalog or paper has one (data/four_plus_stars/research.py),
model-inferred and orange-boxed on the sheet where nothing measures it (infer.py). `data/hierarchy.py` turns the
rows into bodies round barycentres, as it does for the featured Castor, which is built from its own hand-checked
copy of the same rows and is left out here (`FEATURED_CATALOG_HOSTS`).

A star whose 'Drawing status' reads 'hypothetical and model-inferred' -- a suspected companion nothing has resolved,
or one of the two unconfirmed spectroscopic companions -- is drawn hollow and says so in its label and info panel.

A brown dwarf is a planet, not a star (docs/hybrasil-instructions.md section 6), so since 7 Oct 2026 the brown
dwarfs of these hierarchies live on the planet tabs, filed under the system's 'System / Host'. Each is drawn round
the node its 'Planet-host star' names -- a star, or a subsystem's barycentre for one that orbits a pair -- and its
moons (the Exomoons tab) round it. A system with a planet is listed as Planetary; the tab keeps its stars and orbits.

Two halves, like the catalog source: `parse_planetless()` is pure, from raw tab values; `load_planetless()` fetches
them -- the live sheet (through the 24-hour cache), else the committed snapshot in data/, which is also what the
tests read (`nearby_loader.SOURCE_ENV`).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Optional

from ..mechanics.orientation import (TOWARD_EARTH, galactic_centre_distance_ly, galactic_centre_in_sky_frame)
from ..mechanics.solvent_bands import DEFAULT_CHOICE, SolventChoice
from ..models.system import StarSystem
from .catalog_loader import _moon_body, _planet_body, match_key, parse_workbook
from .hierarchy import Look, NodeRow, hierarchy_bodies

TAB = "Planetless 4+ Stars"
PREFIX = "planetless:"
HYPOTHETICAL = "hypothetical and model-inferred"

_COLUMNS = {
    "node_type": "Node type", "mass_sun": "Mass (M-sun)", "luminosity_sun": "Luminosity (L-sun)",
    "teff_k": "Effective temp (K)", "separation_from": "Separation from", "a_au": "Separation (AU)",
    "e": "Orbital eccentricity (e)", "period_d": "Orbital period (d)", "inclination_deg": "Inclination (deg)",
    "node_deg": "Ascending node (deg)", "omega_deg": "Argument of periastron (deg)",
    "periastron_jd": "Time of periastron (JD)", "omega_refers_to": "Argument of periastron refers to",
    "barycentre_from": "Barycentre from", "barycentre_offset_au": "Barycentre offset (AU)",
}
_TEXT = {"node_type", "separation_from", "omega_refers_to", "barycentre_from"}
# The host row's place in the galaxy and its motion, under the headers the Systems tab uses, so the Nearby Stellar
# Motion view can draw these systems too (data/four_plus_stars/kinematics.py filled them, 1 Oct 2026).
_MOTION = {
    "l_deg": "Galactic longitude l (deg)", "b_deg": "Galactic latitude b (deg)",
    "speed_kms": "Space velocity (km/s)", "motion_l_deg": "Motion toward l (deg, heliocentric)",
    "motion_b_deg": "Motion toward b (deg, heliocentric)", "radial_velocity_kms": "Radial velocity (km/s)",
    "total_pm_arcsec_yr": "Total proper motion, μ (arcsec/yr)", "age_gyr": "Age (Gyr)",
    "metallicity": "Metallicity [Fe/H]", "luminosity_class": "Luminosity class",
    "kinematics_source": "Kinematics source",
    # What the view's info panel links (data/existence/ wrote the last three, 9 Oct 2026).
    "gaia_id": "Gaia DR3 source_id", "wds": "WDS code", "simbad_id": "SIMBAD main_id", "existence": "Existence",
    "kinematics_refs": "Kinematics refs",
}
_MOTION_TEXT = {"luminosity_class", "kinematics_source", "gaia_id", "wds", "simbad_id", "existence",
                "kinematics_refs"}
# A marker colour from the first letter of the spectral class, where the tab has no temperature for the ramp.
_CLASS_COLOR = {"O": "#9BB0FF", "B": "#AABFFF", "A": "#CAD8FF", "F": "#F8F7FF", "G": "#FFF4E8", "K": "#FFD2A1",
                "M": "#FFB07A", "L": "#E0704A", "T": "#B05A3A", "Y": "#8A4A30", "D": "#DDE8FF"}


@dataclass
class PlanetlessSystem:
    """One system of the tab: its rows as NodeRows, and what a drawing and a listing need besides."""
    host: str                                   # 'System / Host'
    origin: str                                 # the host star's row name, fixed at the origin
    rows: list[NodeRow]
    ra_deg: float
    dec_deg: float
    distance_ly: float
    stellar_class: str = ""
    nickname: str = ""
    hierarchy: str = ""
    classes: dict = field(default_factory=dict)     # row name -> spectral class
    roles: dict = field(default_factory=dict)       # row name -> 'Role in system'
    hypothetical: set = field(default_factory=set)  # row names drawn hollow
    motion: dict = field(default_factory=dict)      # the host row's galactic position and motion (_MOTION)
    planets: list = field(default_factory=list)     # catalog_loader.PlanetRecord, from the planet tabs
    moons: dict = field(default_factory=dict)       # match_key(planet) -> [catalog_loader.MoonRecord]

    @property
    def stars(self) -> list[str]:
        return [r.name for r in self.rows if r.node_type == "star"]


def _num(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_planetless(workbook: dict, skip: tuple = ()) -> dict[str, PlanetlessSystem]:
    """{'System / Host': PlanetlessSystem} for every system on the tab, in tab order; `skip` hosts are left out."""
    values = (workbook.get("tabs") or {}).get(TAB)
    if not values:
        return {}
    head = [str(h).strip() for h in values[0]]
    col = {h: i for i, h in enumerate(head)}

    def cell(row, h):
        i = col.get(h)
        return row[i] if i is not None and i < len(row) else ""

    by: dict[str, list] = {}
    for row in values[1:]:
        host, name = str(cell(row, "System / Host")).strip(), str(cell(row, "Star (component)")).strip()
        if host and name and host not in skip:
            by.setdefault(host, []).append(row)
    catalog = parse_workbook(workbook)
    out = {}
    for host, rows in by.items():
        nodes, classes, roles, hypo = [], {}, {}, set()
        origin = None
        for row in rows:
            name = str(cell(row, "Star (component)")).strip()
            kw = {}
            for f, h in _COLUMNS.items():
                v = cell(row, h)
                kw[f] = (str(v).strip() or None) if f in _TEXT else _num(v)
            nodes.append(NodeRow(name=name, **kw))
            classes[name] = str(cell(row, "Stellar Class") or "").strip()
            roles[name] = str(cell(row, "Role in system") or "").strip()
            if HYPOTHETICAL in str(cell(row, "Drawing status")).lower():
                hypo.add(name)
            if str(cell(row, "Role in system")).startswith("host") and kw["node_type"] == "star":
                origin = name
        if origin is None:                           # no host marked: the heaviest star
            stars = [n for n in nodes if n.node_type == "star"]
            origin = max(stars, key=lambda n: n.mass_sun or 0).name
        first = next(r for r in rows if str(cell(r, "Star (component)")).strip() == origin)
        planets = catalog.planetless_planets.get(host, [])
        out[host] = PlanetlessSystem(
            planets=planets,
            moons={match_key(p.name): catalog.moons_by_planet.get(match_key(p.name), []) for p in planets},
            host=host, origin=origin, rows=nodes,
            ra_deg=_num(cell(first, "RA (deg, ICRS)")) or 0.0, dec_deg=_num(cell(first, "Dec (deg, ICRS)")) or 0.0,
            distance_ly=_num(cell(first, "Distance (ly)")) or 0.0, stellar_class=classes.get(origin, ""),
            nickname=str(cell(first, "Nickname (IAU)") or "").strip(),
            hierarchy=str(cell(first, "Hierarchy") or "").strip(), classes=classes, roles=roles, hypothetical=hypo,
            motion={f: (str(cell(first, h)).strip() if f in _MOTION_TEXT else _num(cell(first, h)))
                    for f, h in _MOTION.items()})
    return out


def load_planetless(workbook: Optional[dict] = None, skip: tuple = ()) -> tuple[dict[str, PlanetlessSystem], str]:
    """(systems, where they came from): the given workbook, the live sheet, or the committed snapshot."""
    from .snapshot import snapshot_only
    if workbook is None and not snapshot_only():
        try:
            from .google_sheets import get_workbook
            workbook = get_workbook()
        except Exception as e:                       # no credential, no network, no cache
            print(f"Planetless 4+ Stars: live sheet unavailable ({e.__class__.__name__}); using the committed "
                  "snapshot.", file=sys.stderr)
    if workbook is None:
        from .snapshot import load_snapshot_workbook
        workbook = load_snapshot_workbook()
    return parse_planetless(workbook, skip), workbook.get("title", "")


def _look(ps: PlanetlessSystem, row: NodeRow) -> Look:
    if row.node_type != "star":
        kids = [r.name for r in ps.rows if r.separation_from and (r.separation_from == row.barycentre_from)
                and r.name != row.name]
        pair = f" ({row.barycentre_from.split()[-1]} + {kids[0].split()[-1]})" if row.barycentre_from and kids else ""
        return Look(display_name=f"{row.name} barycentre{pair}")
    cls = ps.classes.get(row.name, "")
    color = _CLASS_COLOR.get(cls[:1].upper()) if cls else None
    if cls.upper().startswith(("D", "WD")):
        color = _CLASS_COLOR["D"]
    if row.name in ps.hypothetical:
        return Look(color=color or "#C8A07A", status="hypothetical",
                    display_name=f"{row.name} (hypothetical, model-inferred)",
                    extra={"status_note": "Hypothetical and model-inferred"})
    return Look(color=color)


def planetless_span_days(system: StarSystem) -> float:
    """A window that shows the tightest pair turning: 1.2 x the shortest period, between 5 days and 100 years.

    Castor's rule (figures._NATURAL_SPANS): no window shows every orbit of a hierarchy moving -- its periods run
    from days to hundreds of thousands of years -- so the short ones turn and the long ones are drawn whole.
    """
    periods = [b.elements.period for b in system.bodies if b.elements is not None and b.elements.period > 0]
    if not periods:
        return 365.25
    return min(max(1.2 * min(periods), 5.0), 100 * 365.25)


def build_planetless_system(ps: PlanetlessSystem, bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    looks = {r.name: _look(ps, r) for r in ps.rows}
    bodies = hierarchy_bodies(ps.rows, origin=ps.origin, looks=looks)
    n_stars = len(ps.stars)
    n_hypo = len(ps.hypothetical)
    host = next(r for r in ps.rows if r.name == ps.origin)
    planet_bodies, moon_bodies, unplaced = _planets(ps)
    worlds = ""
    if ps.planets:
        named = ", ".join(f"{b.name} round {b.parent}" for b in planet_bodies)
        worlds = (f"{len(ps.planets)} planet{'s' if len(ps.planets) > 1 else ''} from the planet tabs -- brown "
                  f"dwarfs, which this model counts as planets: {named or 'none with an orbit on file'}"
                  + (f"; with moons {', '.join(b.name for b in moon_bodies)}" if moon_bodies else "")
                  + (f"; not drawn, no orbit on file: {', '.join(unplaced)}" if unplaced else "") + ". ")
    description = (
        f"{ps.host}: {n_stars} stars{f' ({n_hypo} hypothetical)' if n_hypo else ''}, "
        f"{ps.distance_ly:.1f} light years away, {ps.hierarchy or 'a hierarchy of pairs'}. Every value is a cell of "
        "the workbook's Planetless 4+ Stars tab: orbits from the MSC (Tokovinin 2018), ORB6, SB9 or Gaia DR3 where "
        "they are measured; where nothing measures them, model-inferred (orange on the sheet) -- a wide pair is drawn "
        "as a circle in the plane of the sky at today's position angle, flat in depth, and an unresolved suspected "
        "companion as a typical one, hollow. Outer orbits run between barycentres, shown as small hollow rings. "
        + worlds + bands.note(host.luminosity_sun, bodies, ps.origin, host.teff_k))
    bodies = bodies + planet_bodies + moon_bodies
    return StarSystem(
        name=ps.host,
        description=description,
        bodies=bodies,
        source="catalog",
        belt_zones=bands.zones_for_system(bodies),
        distance_from_sun_ly=ps.distance_ly,
        solar_system_direction=TOWARD_EARTH,
        galactic_center_direction=galactic_centre_in_sky_frame(ps.ra_deg, ps.dec_deg, ps.distance_ly),
        sky_frame_radec=(ps.ra_deg, ps.dec_deg),
        distance_to_galactic_center_ly=galactic_centre_distance_ly(ps.ra_deg, ps.dec_deg, ps.distance_ly),
    )


def _planets(ps: PlanetlessSystem) -> tuple[list, list, list]:
    """(planet bodies, moon bodies, planets with no usable orbit): each planet round the node its row names.

    'Planet-host star' names a star or a subsystem of the hierarchy; a planet naming neither goes round the host
    star at the origin, as a catalog planet filed under its system's name goes round the primary.
    """
    mass = {r.name: r.mass_sun for r in ps.rows}
    planets, moons, unplaced = [], [], []
    for rec in ps.planets:
        parent = rec.planet_host if rec.planet_host in mass else ps.origin
        body = _planet_body(rec, parent, mass[parent], [], "")
        if body is None:
            unplaced.append(rec.name)
            continue
        planets.append(body)
        for m in ps.moons.get(match_key(rec.name), []):
            if m.is_rejected:
                continue
            mb = _moon_body(m, body, [], "")
            if mb is not None:
                moons.append(mb)
    return planets, moons, unplaced


def planetless_entry(ps: PlanetlessSystem) -> dict:
    """What the web app's system list says about one system.

    A system whose brown dwarfs are on the planet tabs (7 Oct 2026) has planets, so it is listed as Planetary.
    """
    aliases = ([ps.nickname] if ps.nickname else []) + [s for s in ps.stars if s != ps.host]
    names = [p.name for p in ps.planets]
    # Every star row, candidates included, as a planet count includes candidates.
    return {"id": PREFIX + ps.host, "name": ps.host, "featured": False,
            "kind": "planetary" if names else "planetless",
            "aliases": aliases + names, "planets": names, "n_planets": len(names), "n_stars": len(ps.stars),
            "distance_ly": ps.distance_ly or None, "stellar_class": ps.stellar_class}
