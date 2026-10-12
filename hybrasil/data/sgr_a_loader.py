# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The workbook's "Sgr A* S-stars" tab, as a drawable StarSystem: the stars on Keplerian orbits round Sgr A*.

One row for Sgr A* -- the supermassive black hole, neither a star nor a planet -- and one per S-star: the 40 orbits
of Gillessen et al. 2017 (GRAVITY's newer fits for S2, S29, S38 and S55), S301 (GRAVITY+ 2026), six young stars of
von Fellenberg et al. 2022, the dusty objects G1 and G2, and the disputed newcomers S62 and S4711-S4716, drawn
hollow.  `data/sgr_a/` built the tab; `docs/architecture/galactic-centre.md` is the deep dive.

**The frame.**  The orbits are quoted on the plane of the sky like every astrometric orbit here (x North, y East,
z toward Earth; `docs/architecture/frames.md`), but the Galactic Centre papers fix the node by the radial velocity:
their ascending node is where the star **recedes**.  With z toward Earth, the standard rotation puts it where the
star approaches, which mirrors every orbit through the sky plane: the picture on the sky is the same, the radial
velocities all have the wrong sign (S2: +1199 km/s measured in 2000.49, Gillessen 2017 table 5).  Turning both
Omega and omega by 180 deg leaves the Thiele-Innes constants A, B, F, G alone and flips C and H, i.e. z -> -z, and
is done once, here (`sky_elements`).  `tests/test_sgr_a.py` pins it against S2's measured positions and RVs.

**What is drawn.**  Sgr A* sits at the origin with no luminosity, so it carries no solvent band or photosynthesis
ring, and neither does any S-star: they are B dwarfs and giants with luminosities nothing here has measured, and a
band round a star on a 16-year plunge past a black hole would mean nothing.  S111 is unbound (e = 1.09, Gillessen
2017) and `kepler.py` solves only ellipses, so it is on the sheet but not drawn.

Two halves, like the other sheet sources: `parse_sgr_a()` is pure, from raw tab values; `load_sgr_a()` fetches them
-- the live sheet, else the committed snapshot (`nearby_loader.SOURCE_ENV`).
"""
from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field, replace
from typing import Optional

from ..mechanics.kepler import elements_to_cartesian
from ..mechanics.orientation import TOWARD_EARTH
from ..models.body import OrbitalBody
from ..models.elements import KeplerianElements
from ..models.system import StarSystem
from .star_sources import link, ref_link

TAB = "Sgr A* S-stars"
# An xlsx tab name cannot hold '*', so Google's export (the data/ snapshot) drops it.
XLSX_TAB = TAB.replace("*", "")
PREFIX = "galactic:"
SYSTEM_ID = "galactic:sgr-a"
KIND = "motion"                 # listed under Stellar Motion, beside Nearby Stellar Motion
NAME = "Sgr A* Cluster (Galactic Center)"
CENTRE = "Sgr A*"
SMBH = "Supermassive black hole"
DISPUTED = "disputed"

M_SUN_KG = 1.98847e30
AU_KM = 1.495978707e8
JD_J2000 = 2451545.0
JULIAN_YEAR_D = 365.25
LY_PER_PC = 3.261563777

# Every header of the tab, in order: data/sgr_a/build.py writes them, this module reads them by name.
HEADERS = [
    "Object", "Object type", "Role in system", "Status", "SIMBAD main_id",
    "Stellar Class", "Spectral group (Gillessen 2017)", "K mag", "Mass (M-sun)", "Effective temp (K)",
    "Star data source",
    "Semi-major axis (arcsec)", "Semi-major axis (AU)", "Orbital eccentricity (e)", "Inclination (deg)",
    "Ascending node (deg)", "Argument of periapsis (deg)", "Time of periapsis (yr)", "Orbital period (yr)",
    "Pericentre distance (AU)", "Orbit source",
    "Motion epoch (yr)", "RA offset (mas)", "Dec offset (mas)", "Distance from Sgr A* (AU)",
    "Radial velocity (km/s)", "Proper motion (mas/yr)", "3-D speed (km/s)", "Direction of sky motion (PA, deg)",
    "Measured radial velocity (km/s)", "Measured RV epoch (yr)", "Measured RV source",
    "RA (deg, ICRS)", "Dec (deg, ICRS)", "Distance (pc)", "Distance (ly)",
    "Existence", "Refs",
]

_NUM = {
    "kmag": "K mag", "mass": "Mass (M-sun)", "teff": "Effective temp (K)",
    "a_arcsec": "Semi-major axis (arcsec)", "a_au": "Semi-major axis (AU)", "e": "Orbital eccentricity (e)",
    "i": "Inclination (deg)", "node": "Ascending node (deg)", "omega": "Argument of periapsis (deg)",
    "tp_yr": "Time of periapsis (yr)", "period_yr": "Orbital period (yr)", "peri_au": "Pericentre distance (AU)",
    "epoch_yr": "Motion epoch (yr)", "ra_off": "RA offset (mas)", "dec_off": "Dec offset (mas)",
    "r_au": "Distance from Sgr A* (AU)", "rv": "Radial velocity (km/s)", "pm": "Proper motion (mas/yr)",
    "speed": "3-D speed (km/s)", "pa": "Direction of sky motion (PA, deg)",
    "rv_measured": "Measured radial velocity (km/s)", "rv_epoch": "Measured RV epoch (yr)",
    "ra_deg": "RA (deg, ICRS)", "dec_deg": "Dec (deg, ICRS)", "distance_pc": "Distance (pc)",
    "distance_ly": "Distance (ly)",
}
_TEXT = {
    "name": "Object", "object_type": "Object type", "role": "Role in system", "status": "Status",
    "simbad_id": "SIMBAD main_id", "stellar_class": "Stellar Class", "group": "Spectral group (Gillessen 2017)",
    "star_source": "Star data source", "orbit_source": "Orbit source", "rv_source": "Measured RV source",
    "existence": "Existence", "refs": "Refs",
}

# Early-type S-stars are B dwarfs; late-type ones are K/M giants.
EARLY_COLOUR = "#9BB0FF"
LATE_COLOUR = "#FFB46B"
AF_COLOUR = "#F8F4E8"           # S301, an F1.5 dwarf: neither of Gillessen's two groups
UNKNOWN_COLOUR = "#CCCCCC"
DUST_COLOUR = "#B5651D"         # G1, G2: gas clouds or dust-enshrouded stars
SMBH_COLOUR = "#111111"
DUSTY = "dusty object"


def _num(v) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("−", "-")
    try:
        return float(s)
    except ValueError:
        return None


@dataclass
class SRow:
    """One row of the tab."""
    name: str
    object_type: str = ""
    role: str = ""
    status: str = ""
    simbad_id: str = ""
    stellar_class: str = ""
    group: str = ""
    star_source: str = ""
    orbit_source: str = ""
    rv_source: str = ""
    existence: str = ""
    refs: str = ""
    kmag: Optional[float] = None
    mass: Optional[float] = None
    teff: Optional[float] = None
    a_arcsec: Optional[float] = None
    a_au: Optional[float] = None
    e: Optional[float] = None
    i: Optional[float] = None
    node: Optional[float] = None
    omega: Optional[float] = None
    tp_yr: Optional[float] = None
    period_yr: Optional[float] = None
    peri_au: Optional[float] = None
    epoch_yr: Optional[float] = None
    ra_off: Optional[float] = None
    dec_off: Optional[float] = None
    r_au: Optional[float] = None
    rv: Optional[float] = None
    pm: Optional[float] = None
    speed: Optional[float] = None
    pa: Optional[float] = None
    rv_measured: Optional[float] = None
    rv_epoch: Optional[float] = None
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    distance_pc: Optional[float] = None
    distance_ly: Optional[float] = None

    @property
    def is_centre(self) -> bool:
        return self.object_type.lower().startswith(SMBH.lower())

    @property
    def dusty(self) -> bool:
        """G1, G2: an orbit three groups agree on, round something that may be a gas cloud or a star."""
        return self.object_type.lower().startswith(DUSTY)

    @property
    def disputed(self) -> bool:
        return self.status.lower().startswith(DISPUTED)

    @property
    def bound(self) -> bool:
        """A closed orbit kepler.py can draw: every element, e < 1, a period."""
        return (None not in (self.a_au, self.e, self.i, self.node, self.omega, self.tp_yr, self.period_yr)
                and 0 <= self.e < 1 and self.a_au > 0 and self.period_yr > 0)


@dataclass
class SgrACluster:
    centre: SRow
    stars: list[SRow] = field(default_factory=list)
    title: str = ""


def parse_sgr_a(workbook: dict) -> Optional[SgrACluster]:
    """The tab's rows, or None when the workbook has no such tab."""
    tabs = workbook.get("tabs") or {}
    values = tabs.get(TAB) or tabs.get(XLSX_TAB)
    if not values:
        return None
    head = [str(h).strip() for h in values[0]]
    col = {h: i for i, h in enumerate(head)}

    def cell(row, h):
        i = col.get(h)
        return row[i] if i is not None and i < len(row) else ""

    rows = []
    for row in values[1:]:
        name = str(cell(row, "Object") or "").strip()
        if not name:
            continue
        kw = {f: str(cell(row, h) or "").strip() for f, h in _TEXT.items()}
        kw.update({f: _num(cell(row, h)) for f, h in _NUM.items()})
        rows.append(SRow(**kw))
    centres = [r for r in rows if r.is_centre]
    if len(centres) != 1:
        raise ValueError(f"{TAB}: expected one '{SMBH}' row, found {len(centres)}")
    return SgrACluster(centre=centres[0], stars=[r for r in rows if not r.is_centre],
                       title=workbook.get("title", ""))


def load_sgr_a(workbook: Optional[dict] = None) -> Optional[SgrACluster]:
    """The given workbook's tab, else the live sheet's, else the committed snapshot's."""
    from .snapshot import snapshot_only
    if workbook is None and not snapshot_only():
        try:
            from .google_sheets import get_workbook
            workbook = get_workbook()
        except Exception as e:                       # no credential, no network, no cache
            print(f"{TAB}: live sheet unavailable ({e.__class__.__name__}); using the committed snapshot.",
                  file=sys.stderr)
    if workbook is None:
        from .snapshot import load_snapshot_workbook
        workbook = load_snapshot_workbook()
    return parse_sgr_a(workbook)


# ── orbits ──────────────────────────────────────────────────────────────────────────────────────────────────────

def year_to_jd(year: float) -> float:
    """A fractional (Julian) year, as the Galactic Centre papers quote epochs, to a Julian Date."""
    return JD_J2000 + (year - 2000.0) * JULIAN_YEAR_D


def sky_elements(a_au: float, e: float, i: float, node: float, omega: float, tp_yr: float,
                 period_yr: float) -> KeplerianElements:
    """A Galactic Centre orbit as published, in this code's sky frame (z toward Earth): Omega and omega + 180.

    The papers' ascending node is the receding one; see the module docstring.
    """
    return KeplerianElements(
        semi_major_axis=a_au, eccentricity=e, inclination=i,
        longitude_of_ascending_node=(node + 180.0) % 360.0, argument_of_periapsis=(omega + 180.0) % 360.0,
        mean_anomaly_at_epoch=0.0, epoch=year_to_jd(tp_yr), period=period_yr * JULIAN_YEAR_D)


def row_elements(r: SRow) -> KeplerianElements:
    return sky_elements(r.a_au, r.e, r.i, r.node, r.omega, r.tp_yr, r.period_yr)


@dataclass
class SkyMotion:
    """Where a star is and how it moves at one moment, as an observer at distance_pc sees it."""
    ra_off_mas: float           # East of Sgr A*
    dec_off_mas: float          # North of Sgr A*
    r_au: float                 # 3-D distance from Sgr A*
    rv_kms: float               # positive = receding
    pm_masyr: float
    speed_kms: float
    pa_deg: float               # direction of the sky motion, East of North


def sky_motion(el: KeplerianElements, t_jd: float, distance_pc: float, dt_d: float = 0.01) -> SkyMotion:
    """Position and velocity from the orbit at t_jd, by a central difference of Kepler's equation."""
    x0, y0, z0 = elements_to_cartesian(el, t_jd - dt_d)
    x, y, z = elements_to_cartesian(el, t_jd)
    x1, y1, z1 = elements_to_cartesian(el, t_jd + dt_d)
    vx, vy, vz = ((x1 - x0) / (2 * dt_d), (y1 - y0) / (2 * dt_d), (z1 - z0) / (2 * dt_d))   # AU/day
    kms = AU_KM / 86400.0
    mas_per_au = 1000.0 / distance_pc
    return SkyMotion(
        ra_off_mas=y * mas_per_au, dec_off_mas=x * mas_per_au, r_au=math.sqrt(x * x + y * y + z * z),
        rv_kms=-vz * kms, pm_masyr=math.hypot(vx, vy) * JULIAN_YEAR_D * mas_per_au,
        speed_kms=math.sqrt(vx * vx + vy * vy + vz * vz) * kms,
        pa_deg=math.degrees(math.atan2(vy, vx)) % 360.0)


# ── the system ──────────────────────────────────────────────────────────────────────────────────────────────────

def _fmt(v: Optional[float], unit: str = "", digits: int = 4) -> str:
    if v is None:
        return "Unknown"
    s = f"{v:,.{digits}g}" if abs(v) < 1000 else f"{v:,.0f}"
    return f"{s} {unit}".strip()


def _inferred(source: str, what: str) -> str:
    """'inferred' when the star data source says this value was: "INFERRED (class, mass) ..." names which."""
    if not source.upper().startswith("INFERRED"):
        return ""
    named = re.match(r"INFERRED\s*\(([^)]*)\)", source, re.I)
    return "inferred" if not named or what.lower() in named.group(1).lower() else ""


def _refs(r: SRow) -> list:
    """[label, url] pairs: the catalog that lists the object, then each paper the Refs cell names."""
    out = []
    if r.simbad_id:
        out.append([f"Exists: SIMBAD {r.simbad_id}", link("simbad", r.simbad_id)])
    for part in re.split(r";\s*", r.refs or ""):
        if not part.strip():
            continue
        what, _, toks = part.partition(":") if ":" in part and not part.lower().startswith(("doi:", "arxiv:")) \
            else ("", "", part)
        for tok in re.split(r",\s*", toks):
            hit = ref_link(tok)
            if hit:
                out.append([f"{what.strip()}: {hit[0]}" if what.strip() else hit[0], hit[1]])
    return out


def _star_rows(r: SRow, centre: SRow) -> list:
    rows = [["Object type", r.object_type or "Star", r.role],
            ["Status", "Disputed" if r.disputed else "Nature disputed" if r.dusty else "Confirmed",
             r.status if r.disputed or r.dusty else ""],
            ["Stellar class", r.stellar_class or "Unknown", _inferred(r.star_source, "class")],
            ["Spectral group", r.group or "Unknown", "Gillessen et al. 2017" if r.group else ""],
            ["Mass", _fmt(r.mass, "M☉", 3), _inferred(r.star_source, "mass")],
            ["Effective temp", _fmt(r.teff, "K", 3), _inferred(r.star_source, "Teff")],
            ["K magnitude", _fmt(r.kmag, "", 3), ""],
            ["Semi-major axis", _fmt(r.a_au, "AU"), f"{r.a_arcsec:g} arcsec" if r.a_arcsec is not None else ""],
            ["Eccentricity", _fmt(r.e, "", 4), ""],
            ["Orbital period", _fmt(r.period_yr, "yr"), ""],
            ["Pericentre", _fmt(r.peri_au, "AU"), f"passage {r.tp_yr:.2f}" if r.tp_yr is not None else ""]]
    if r.epoch_yr is not None:
        when = f"at {r.epoch_yr:.2f}, computed from the orbit"
        rows += [["Distance from Sgr A*", _fmt(r.r_au, "AU"), when],
                 ["Radial velocity", _fmt(r.rv, "km/s"), "positive = receding"],
                 ["3-D speed", _fmt(r.speed, "km/s"), when],
                 ["Direction on the sky", _fmt(r.pa, "deg E of N", 3), "position angle of its motion"]]
    if r.rv_measured is not None:
        rows.append(["Measured radial velocity", _fmt(r.rv_measured, "km/s"),
                     f"{r.rv_epoch:.2f}" if r.rv_epoch is not None else ""])
    rows.append(["Orbit source", r.orbit_source or "", ""])
    return rows


def _centre_rows(c: SRow) -> list:
    return [["Object type", SMBH, "the system's centre: every S-star orbits it"],
            ["Mass", _fmt(c.mass, "M☉", 4), c.star_source],
            ["Distance from the Sun", _fmt(c.distance_ly, "ly", 5),
             f"{c.distance_pc:,.0f} pc (R0)" if c.distance_pc else ""],
            ["Position (ICRS)", f"RA {c.ra_deg:.6f}°, Dec {c.dec_deg:.6f}°"
             if c.ra_deg is not None and c.dec_deg is not None else "Unknown", ""]]


def _colour(r: SRow) -> str:
    """Gillessen's group where he gives one, else the class's first letter; a dusty object is dust-coloured."""
    if r.dusty:
        return DUST_COLOUR
    group = r.group.lower()
    if group.startswith("early"):
        return EARLY_COLOUR
    if group.startswith("late"):
        return LATE_COLOUR
    first = r.stellar_class[:1].upper()
    if not first:
        return UNKNOWN_COLOUR
    return (EARLY_COLOUR if first in "OBW" else LATE_COLOUR if first in "GKM"
            else AF_COLOUR if first in "AF" else UNKNOWN_COLOUR)


def build_sgr_a_system(cluster: SgrACluster) -> StarSystem:
    c = cluster.centre
    centre = OrbitalBody(
        name=CENTRE, body_type="star", mass_kg=(c.mass or 0.0) * M_SUN_KG or None, color=SMBH_COLOUR,
        display_name=f"{CENTRE} ({SMBH.lower()})", sources=_refs(c), info_rows=_centre_rows(c))
    bodies = [centre]
    for r in cluster.stars:
        if not r.bound:                              # S111: unbound, not drawn
            continue
        body = OrbitalBody(
            name=r.name, body_type="star", parent=CENTRE, elements=row_elements(r),
            mass_kg=r.mass * M_SUN_KG if r.mass else None, color=_colour(r), sources=_refs(r),
            info_rows=_star_rows(r, c))
        if r.disputed:
            body = replace(body, status="hypothetical", status_note="Disputed",
                           display_name=f"{r.name} (disputed)")
        elif r.dusty:
            body = replace(body, display_name=f"{r.name} (dusty object)")
        bodies.append(body)
    n = len(bodies) - 1
    n_disputed = sum(1 for r in cluster.stars if r.disputed and r.bound)
    dusty = [r.name for r in cluster.stars if r.dusty and r.bound]
    unbound = [r.name for r in cluster.stars if not r.bound]
    desc = (f"The S-stars round Sagittarius A*, the Milky Way's {SMBH.lower()}: {n} orbits"
            + (f", {n_disputed} of them disputed and drawn hollow" if n_disputed else "")
            + (f"; {' and '.join(dusty)} {'are dusty objects' if len(dusty) > 1 else 'is a dusty object'}, "
               "gas cloud or star" if dusty else "")
            + (f"; {', '.join(unbound)} unbound and not drawn" if unbound else "")
            + ". Orbits on the plane of the sky (Gillessen et al. 2017; GRAVITY 2022; von Fellenberg et al. 2022; "
               "GRAVITY+ 2026).")
    return StarSystem(
        name=NAME, description=desc, bodies=bodies, source="catalog",
        distance_from_sun_ly=c.distance_ly, solar_system_direction=TOWARD_EARTH,
        sky_frame_radec=(c.ra_deg, c.dec_deg) if c.ra_deg is not None and c.dec_deg is not None else None,
        at_galactic_center=True)


SPAN_YR = 20.0


def sgr_a_span_days(system: StarSystem) -> float:
    """Twenty years: S2 (16.0 yr), S55 (12.8) and S38 (19.2) each go round once, the rest move along their orbits.

    The planetless rule, 1.2 x the shortest period, would stop at S55's 15 years and leave S2 short of a turn.
    """
    return SPAN_YR * JULIAN_YEAR_D


def sgr_a_entry(cluster: SgrACluster) -> dict:
    """What the web app's system list says about the cluster."""
    names = [r.name for r in cluster.stars]
    return {"id": SYSTEM_ID, "name": NAME, "featured": False, "kind": KIND,
            "aliases": ["Sgr A*", "Sagittarius A*", "S-stars", "Sgr A* S-stars", "Galactic Center", "Galactic Centre"]
            + names,
            "planets": [], "n_planets": 0, "n_stars": sum(1 for r in cluster.stars if not r.dusty),
            "distance_ly": cluster.centre.distance_ly, "stellar_class": SMBH}
