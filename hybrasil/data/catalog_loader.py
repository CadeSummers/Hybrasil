# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build StarSystems from the Google Sheets star catalog.

This module is pure parsing: it takes the raw tab values produced by
`google_sheets.get_workbook()` and converts them into `StarSystem` objects.
No network, no credentials -- which means every rule in here is testable from
a literal list of rows.

Tabs are identified by their header signature rather than by tab title, so
renaming a tab in the spreadsheet does not break the loader.  Columns are read
by header name for the same reason.

What the spreadsheet provides per planet: semi-major axis, orbital period and
eccentricity.  What it does not provide: inclination, longitude of ascending
node, and argument of periapsis.  Those are set to zero, which renders every
catalog system as a flat, co-planar disk.  Mean anomaly is spread around the
orbit from a hash of the planet name so that planets in the same system do not
all start stacked at periapsis; it is arbitrary, not observed.

A multi-star system is drawn whole: every star on the stars tab, each planet
around the star it orbits.  A companion is placed by the stars tab's
Separation columns -- a solved orbit ('semi-major axis') is drawn as its
ellipse, a sky-plane separation ('projected') as a circle at that distance,
marked hypothetical because no orbit has been solved; an 'assumed' one, a
suspected companion at a model-inferred distance, likewise.  A companion with no
separation on file cannot be placed, and the description says so.

An exomoon tab ('Exomoon' + 'Host planet') adds each moon around its planet,
with the semi-major axis and period measured about the planet, not the star.
A moon whose planet is not drawn is not drawn either.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Optional

from ..models.elements import KeplerianElements
from ..models.body import OrbitalBody
from ..models.system import StarSystem
from ..mechanics.orientation import (Z_AXIS, band_plane, partner_plane, plane_basis, reversed_orbit,
                                     toward_sun_in_ecliptic)
from ..mechanics.solvent_bands import SolventChoice, DEFAULT_CHOICE
from ..mechanics.units import (
    J2000,
    M_SUN_KG, M_JUP_KG, M_EARTH_KG,
    R_SUN_KM, R_JUP_KM, R_EARTH_KM,
    T_SUN_K,
    derive_period_days,
    derive_semi_major_axis_au,
)

# Eccentricities at or above this are almost always a data-entry artefact and
# would blow the scene extent out; clamp rather than drop the planet.
MAX_ECCENTRICITY = 0.95


# --------------------------------------------------------------------------
# Header / cell normalisation
# --------------------------------------------------------------------------

def normalize_header(value) -> str:
    """Canonical form of a header cell, for name-based column lookup."""
    s = str(value if value is not None else "")
    s = s.replace("\\", "")                      # markdown escaping artefacts
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = s.replace(" / ", "/")
    return s


_BLANK = {"", "-", "--", "—", "–", "n/a", "na", "none", "null", "?"}


def gaia_id_text(value) -> str:
    """A Gaia DR3 source_id as its digits, whether the cell holds text or an integer; "" for anything else.

    A float is refused: 19 digits do not survive a double, and a rounded id names another star."""
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    s = str(value if value is not None else "").strip()
    return s if s.isdigit() else ""


def source_columns(table, row) -> dict:
    """The identifier and source columns the Nearby Stellar Motion info panel links (data/existence/ wrote them)."""
    return {
        "gaia_id": gaia_id_text(table.value(row, "gaia dr3 source_id")),
        "simbad_id": table.text(row, "simbad main_id"),
        "cns5_id": table.text(row, "cns5 id"),
        "existence": table.text(row, "existence"),
        "kinematics_refs": table.text(row, "kinematics refs"),
    }


def cell_text(value) -> str:
    """Trimmed string form of a cell; empty string for blank-ish values."""
    if value is None:
        return ""
    s = str(value).replace("\\", "").strip()
    return "" if s.lower() in _BLANK else s


_NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def cell_number(value) -> Optional[float]:
    """Parse a cell as a float, or None if it does not hold a plain number.

    Cells that hold a range ("0.696 - 1.636") or prose return None: a range is
    not a scalar and guessing a midpoint would invent precision.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = cell_text(value)
    if not s:
        return None
    s = s.replace(",", "").replace("−", "-")
    try:
        return float(s)
    except ValueError:
        pass
    # A lone number wrapped in stray characters is still usable; a range is not.
    matches = _NUM_RE.findall(s)
    if len(matches) == 1:
        try:
            return float(matches[0])
        except ValueError:
            return None
    return None


def _first(*values):
    """First value that is neither None nor an empty string."""
    for v in values:
        if v is not None and v != "":
            return v
    return None


def match_key(name: str) -> str:
    """Loose key for matching a system name typed on the command line."""
    s = normalize_header(name)
    return re.sub(r"[\s_-]+", "", s)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

@dataclass
class Table:
    """One spreadsheet tab, addressable by header name."""
    title: str
    headers: list[str]
    rows: list[list]

    def index_of(self, header: str) -> Optional[int]:
        try:
            return self.headers.index(normalize_header(header))
        except ValueError:
            return None

    def has(self, *headers: str) -> bool:
        return all(self.index_of(h) is not None for h in headers)

    def value(self, row: list, header: str):
        i = self.index_of(header)
        if i is None or i >= len(row):
            return None
        return row[i]

    def text(self, row: list, header: str) -> str:
        return cell_text(self.value(row, header))

    def number(self, row: list, header: str) -> Optional[float]:
        return cell_number(self.value(row, header))

    def as_dicts(self) -> list[dict]:
        out = []
        for row in self.rows:
            out.append({h: (row[i] if i < len(row) else None)
                        for i, h in enumerate(self.headers)})
        return out


def build_tables(workbook: dict) -> list[Table]:
    """Turn raw tab values into Tables, one per tab that has a usable header.

    Tabs in this workbook sometimes carry a title or spacer row above the real
    header, so the header row is located by content rather than assumed at
    row 0.

    The data ends at the first row that is blank or holds a single cell -- a
    section title.  The Planets tab keeps reference blocks under its data
    ("CONSTANTS USED BY THIS SHEET", then "SOLVENT BAND CONSTANTS"), with no
    blank row between; read as data, their rows became planets of hosts named
    "0.5575507229162847" and "c_inner".  A real row always has at least a name
    and a host.
    """
    tables: list[Table] = []
    for title, rows in (workbook.get("tabs") or {}).items():
        if not rows:
            continue
        # Use the first row with at least two distinct non-empty headers.
        header_i = None
        for i, row in enumerate(rows[:8]):
            named = [normalize_header(c) for c in row if cell_text(c)]
            if len(set(named)) >= 2:
                header_i = i
                break
        if header_i is None:
            continue
        headers = [normalize_header(c) for c in rows[header_i]]
        body = []
        for r in rows[header_i + 1:]:
            if sum(1 for c in r if cell_text(c)) <= 1:
                break
            body.append(r)
        tables.append(Table(title=title, headers=headers, rows=body))
    return tables


# Header signatures that identify each kind of tab.
PLANET_SIGNATURE = ("planet", "host system (primary star)")
STAR_SIGNATURE = ("system/host", "star (component)")
SYSTEM_SIGNATURE = ("system/host", "host mass (m-sun)")
MOON_SIGNATURE = ("exomoon", "host planet")
# The rejected-candidates tab is a planet tab with one extra column, so it is
# told apart by that column and checked before the planet signature.
REJECTED_SIGNATURE = ("planet", "rejected because")
# "Known within 100ly" carries every Systems column plus "Plotted" and "Last
# Updated", one row per catalogued object within 100 ly, plotted or not. It is a
# reference list, never a source of systems: read as one, its ~10,700 rows would
# each become a system and a star in the Nearby Stellar Motion view.
KNOWN_SIGNATURE = ("system/host", "plotted")
# "4+ Stars only" has every Multi-stars column plus a row per SUBSYSTEM (a pair
# of pairs) and "Node type" to tell the two apart. Read as a stars tab, its rows
# would join same-named systems (psi1 Dra) and its subsystems would be drawn as
# stars, so it is skipped until the viewer can place a star round a barycentre.
FOUR_PLUS_SIGNATURE = ("star (component)", "node type")


def classify_tables(tables: list[Table]) -> dict[str, list[Table]]:
    """Group tables by role. A tab matching no signature is ignored."""
    roles: dict[str, list[Table]] = {"planets": [], "stars": [], "systems": [],
                                     "moons": [], "rejected": [], "four_plus": []}
    for t in tables:
        if t.has(*FOUR_PLUS_SIGNATURE):
            roles["four_plus"].append(t)
            continue
        if t.has(*KNOWN_SIGNATURE):
            continue
        if t.has(*MOON_SIGNATURE):
            roles["moons"].append(t)
        elif t.has(*REJECTED_SIGNATURE):
            roles["rejected"].append(t)
        elif t.has(*PLANET_SIGNATURE):
            roles["planets"].append(t)
        elif t.has(*STAR_SIGNATURE):
            roles["stars"].append(t)
        elif t.has(*SYSTEM_SIGNATURE):
            roles["systems"].append(t)
    return roles


# --------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------

@dataclass
class PlanetRecord:
    name: str
    host: str                        # "Host system (primary star)"
    planet_host: str = ""            # the specific star it orbits
    orbits_primary: str = ""
    # Host properties repeated on the planet row.  "Host luminosity" and
    # "Planet-host class" describe the star the planet actually orbits, which
    # in a binary is not always the system primary.
    distance_ly: Optional[float] = None
    primary_class: str = ""
    planet_host_class: str = ""
    host_luminosity_sun: Optional[float] = None
    semi_major_axis_au: Optional[float] = None
    period_days: Optional[float] = None
    eccentricity: Optional[float] = None
    mass_kg: Optional[float] = None
    radius_km: Optional[float] = None
    mass_type: str = ""
    hz_position: str = ""
    confidence: str = ""
    detection: str = ""
    orbit_source: str = ""
    # "Orbit Direction": "Prograde (assumed)", or a measured "Polar (vs stellar spin)",
    # "Retrograde (vs binary orbit)" ...; and the Planets tab's spin-orbit cell, e.g.
    # "103 +13/-12 (psi; Bourrier+2022, TEPCat)", whose first number tilts a star's axis.
    orbit_direction: str = ""
    spin_orbit: str = ""

    @property
    def measured_direction(self) -> str:
        """The Orbit Direction cell when it is a measurement, else ""."""
        d = self.orbit_direction.strip()
        return "" if not d or "assumed" in d.lower() else d

    @property
    def direction_angle_deg(self) -> Optional[float]:
        """The Orbit Direction cell's angle, degrees: "Retrograde (vs binary orbit; 174°)" -> 174,
        "Polar (vs stellar spin; ψ ≥ 71°)" -> 71 (a lower bound taken as it is)."""
        m = re.search(r";[^0-9-]*(-?\d+(?:\.\d+)?)\s*°", self.measured_direction)
        return abs(float(m.group(1))) if m else None

    @property
    def spin_orbit_deg(self) -> Optional[float]:
        """The angle against the star's spin: the Orbit Direction cell's, else the spin-orbit cell's first
        number (a lower bound taken as it is)."""
        if self.direction_angle_deg is not None:
            return self.direction_angle_deg
        m = re.match(r"\s*(?:>=|>|~)?\s*(-?\d+(?:\.\d+)?)", self.spin_orbit or "")
        return float(m.group(1)) if m else None

    @property
    def orbit_host(self) -> str:
        """The star this planet actually goes around."""
        return self.planet_host or self.host

    def has_orbit(self) -> bool:
        return self.semi_major_axis_au is not None or self.period_days is not None


@dataclass
class MoonRecord:
    """One row of the exomoon tab.  The orbit is about `planet`, not the star."""
    name: str
    planet: str                      # "Host planet"
    host: str                        # "Host system (primary star)"
    semi_major_axis_au: Optional[float] = None
    period_days: Optional[float] = None
    eccentricity: Optional[float] = None
    mass_kg: Optional[float] = None
    radius_km: Optional[float] = None
    mass_type: str = ""
    confidence: str = ""
    detection: str = ""
    orbit_source: str = ""
    reference: str = ""              # "Source / discovery reference"

    @property
    def is_rejected(self) -> bool:
        return self.confidence.lower().startswith("unlikely")


@dataclass
class RejectedRecord:
    """A candidate the catalog has examined and turned down.  Never drawn."""
    name: str
    host: str
    reason: str = ""


@dataclass
class StarRecord:
    host: str
    component: str
    role: str = ""
    nickname: str = ""
    distance_ly: Optional[float] = None
    mass_sun: Optional[float] = None
    stellar_class: str = ""
    luminosity_class: str = ""
    effective_temp_k: Optional[float] = None
    luminosity_sun: Optional[float] = None
    hz_distance: str = ""
    # Where the star sits relative to another star in its system.  Blank on
    # the system primary, which is the origin.
    separation_from: str = ""
    separation_au: Optional[float] = None
    separation_type: str = ""        # "projected", "semi-major axis" or "assumed"
    separation_source: str = ""
    orbit_eccentricity: Optional[float] = None

    @property
    def has_solved_orbit(self) -> bool:
        return self.separation_type.lower().startswith("semi-major")

    @property
    def has_assumed_separation(self) -> bool:
        """A suspected companion nothing has resolved, placed at a model-inferred distance."""
        return self.separation_type.lower().startswith("assumed")


@dataclass
class Catalog:
    """Everything the spreadsheet knows, indexed for lookup.

    Two levels.  Planets are grouped by the star they actually orbit, which in
    a binary is not always the system primary: Proxima Cen's planets are filed
    by the spreadsheet under the alf Cen A system but orbit Proxima itself.
    What gets *plotted* is the whole system -- `hosts()` lists systems by their
    'System / Host' name, and alf Cen A draws A, B and Proxima together, each
    planet around its own star.
    """
    spreadsheet_id: str = ""
    workbook_title: str = ""
    fetched_at: float = 0.0
    planets_by_host: dict[str, list[PlanetRecord]] = field(default_factory=dict)
    # Keyed by match_key(planet name), so spacing and case need not agree.
    moons_by_planet: dict[str, list[MoonRecord]] = field(default_factory=dict)
    # Keyed by match_key(planet name).  A name here is dropped from every
    # planet tab, so a rejected candidate pasted back onto one stays undrawn.
    rejected: dict[str, RejectedRecord] = field(default_factory=dict)
    stars_by_host: dict[str, list[StarRecord]] = field(default_factory=dict)
    stars_by_component: dict[str, StarRecord] = field(default_factory=dict)
    system_rows: dict[str, dict] = field(default_factory=dict)
    system_of: dict[str, str] = field(default_factory=dict)
    # Planets filed under a Planetless 4+ Stars system (a brown dwarf is a
    # planet, docs/hybrasil-instructions.md section 6), by that 'System /
    # Host'. planetless_loader draws them in the system's hierarchy; they
    # are kept out of planets_by_host so no second, catalog copy is listed.
    planetless_planets: dict[str, list[PlanetRecord]] = field(default_factory=dict)
    # The Known within 100ly tab's rows that no tab plots (Plotted = FALSE): every
    # other catalogued object within 100 ly, unclassified, with its position and
    # motion (data/known_within_100ly/kinematics/). Never systems: the Nearby
    # Stellar Motion view draws them as one optional layer.
    known_unplotted: list[dict] = field(default_factory=list)
    _aliases: dict[str, set] = field(default_factory=dict)

    def hosts(self) -> list[str]:
        """Every system with a planet on file, by 'System / Host' name.

        A planet with no orbit on file still counts: the system is drawn as
        its stars and bands, and its description names the planets it could
        not place (CD-35 2722, whose only companion is a directly imaged brown
        dwarf with no semi-major axis or period, was unreachable otherwise).
        """
        return sorted({self.system_of.get(h, h) for h in self.planets_by_host},
                      key=str.lower)

    def members(self, system_host: str) -> list[str]:
        """Every star in a system, primary first, then the stars tab's order.

        A single-star system has no row on the stars tab and is just its own
        name.  The primary is the star named like the system, or failing that
        the one whose role says host -- RR Cae's stars are 'RR Cae A' and
        'RR Cae B', and neither is called 'RR Cae'.  A planet host the stars
        tab does not list is a member too, so a name that fails to match is
        reported as an unplaced star rather than silently dropped.
        """
        rows = self.stars_by_host.get(system_host, [])
        names = [s.component for s in rows]
        if not rows:
            # No stars-tab rows, but a planet may still name another star (GJ 65 b
            # orbits GJ 65 B): list it, so it is reported as unplaced, not lost.
            return [system_host] + sorted(
                h for h, s in self.system_of.items() if s == system_host and h != system_host)
        if system_host in names:
            root = system_host
        else:
            root = next((s.component for s in rows
                         if "host" in s.role.lower()
                         and not s.role.lower().startswith("planet host")),
                        names[0])
        others = [n for n in names if n != root]
        for host, sys_host in self.system_of.items():
            if (sys_host == system_host and host not in names
                    and host != system_host):
                others.append(host)
        return [root] + others

    def resolve_host(self, identifier: str) -> str:
        """Map a user-typed name to a system: its primary, any member star,
        a nickname, or a planet name."""
        key = match_key(identifier)
        hits = self._aliases.get(key)
        if not hits:
            self._refuse_rejected(key, identifier)
            # Fall back to a unique prefix match so "trappist" finds TRAPPIST-1.
            hits = {h for k, v in self._aliases.items() if k.startswith(key)
                    for h in v}
        if len(hits) == 1:
            return next(iter(hits))
        if len(hits) > 1:
            ordered = sorted(hits, key=str.lower)
            raise ValueError(
                f"'{identifier}' matches several catalog systems: "
                + ", ".join(ordered[:8])
                + ("..." if len(ordered) > 8 else "")
            )
        near = [h for h in self.hosts() if key in match_key(h)][:8]
        hint = f" Did you mean: {', '.join(near)}?" if near else ""
        raise ValueError(
            f"'{identifier}' is not in the catalog spreadsheet.{hint} "
            "Run with --list-catalog to see every system."
        )

    def _refuse_rejected(self, key: str, identifier: str) -> None:
        """Say why a rejected candidate, or a host with nothing else, is absent."""
        rec = self.rejected.get(key)
        if rec is not None:
            why = f" ({rec.reason.rstrip('.')})" if rec.reason else ""
            raise ValueError(
                f"'{identifier}' is a rejected candidate{why}, so it is not "
                "drawn. See the Rejected candidates tab.")
        names = [r.name for r in self.rejected.values() if match_key(r.host) == key]
        if names:
            raise ValueError(
                f"'{identifier}' has no planet on file but rejected candidates "
                f"({', '.join(names)}), so it is not drawn. See the Rejected "
                "candidates tab.")

    def rejected_in(self, system_host: str) -> list[str]:
        """Names of the rejected candidates filed under a system."""
        key = match_key(system_host)
        return [r.name for r in self.rejected.values() if match_key(r.host) == key]


def _star_records(table: Table) -> list[StarRecord]:
    out = []
    for row in table.rows:
        host = table.text(row, "system/host")
        if not host:
            continue
        out.append(StarRecord(
            host=host,
            component=table.text(row, "star (component)") or host,
            role=table.text(row, "role in system"),
            nickname=table.text(row, "nickname (iau)"),
            distance_ly=table.number(row, "distance (ly)"),
            mass_sun=table.number(row, "mass (m-sun)"),
            stellar_class=table.text(row, "stellar class"),
            luminosity_class=table.text(row, "luminosity class"),
            effective_temp_k=table.number(row, "effective temp (k)"),
            luminosity_sun=table.number(row, "luminosity (l-sun)"),
            hz_distance=table.text(row, "hz distance"),
            separation_from=table.text(row, "separation from"),
            separation_au=table.number(row, "separation (au)"),
            separation_type=table.text(row, "separation type"),
            separation_source=table.text(row, "separation source"),
            orbit_eccentricity=table.number(row, "orbital eccentricity (e)"),
        ))
    return out


def _planet_records(table: Table) -> list[PlanetRecord]:
    out = []
    for row in table.rows:
        name = table.text(row, "planet")
        host = table.text(row, "host system (primary star)")
        if not name or not host:
            continue

        mass_kg = None
        m_earth = table.number(row, "mass (m-earth)")
        m_jup = table.number(row, "mass (m-jup)")
        if m_earth is not None:
            mass_kg = m_earth * M_EARTH_KG
        elif m_jup is not None:
            mass_kg = m_jup * M_JUP_KG

        radius_km = None
        r_earth = table.number(row, "radius (r-earth)")
        r_jup = table.number(row, "radius (r-jup)")
        if r_earth is not None:
            radius_km = r_earth * R_EARTH_KM
        elif r_jup is not None:
            radius_km = r_jup * R_JUP_KM

        out.append(PlanetRecord(
            name=name,
            host=host,
            planet_host=table.text(row, "planet-host star"),
            orbits_primary=table.text(row, "orbits the primary?"),
            distance_ly=table.number(row, "distance (ly)"),
            primary_class=table.text(row, "primary star class"),
            planet_host_class=table.text(row, "planet-host class"),
            host_luminosity_sun=table.number(row, "host luminosity (l-sun)"),
            semi_major_axis_au=table.number(row, "semi-major axis (au)"),
            period_days=table.number(row, "orbital period (d)"),
            eccentricity=table.number(row, "eccentricity"),
            mass_kg=mass_kg,
            radius_km=radius_km,
            mass_type=table.text(row, "mass type"),
            hz_position=table.text(row, "hz position"),
            confidence=table.text(row, "confidence tier"),
            detection=table.text(row, "detection method"),
            orbit_source=table.text(row, "orbit data source/flags"),
            orbit_direction=table.text(row, "orbit direction"),
            spin_orbit=table.text(row, "spin-orbit angle (deg, vs stellar spin axis)"),
        ))
    return out


def _moon_records(table: Table) -> list[MoonRecord]:
    out = []
    for row in table.rows:
        name = table.text(row, "exomoon")
        planet = table.text(row, "host planet")
        if not name or not planet:
            continue
        m_earth = table.number(row, "mass (m-earth)")
        m_jup = table.number(row, "mass (m-jup)")
        mass_kg = (m_earth * M_EARTH_KG if m_earth is not None
                   else m_jup * M_JUP_KG if m_jup is not None else None)
        r_earth = table.number(row, "radius (r-earth)")
        r_jup = table.number(row, "radius (r-jup)")
        radius_km = (r_earth * R_EARTH_KM if r_earth is not None
                     else r_jup * R_JUP_KM if r_jup is not None else None)
        out.append(MoonRecord(
            name=name,
            planet=planet,
            host=table.text(row, "host system (primary star)"),
            semi_major_axis_au=table.number(row, "semi-major axis (au)"),
            period_days=table.number(row, "orbital period (d)"),
            eccentricity=table.number(row, "eccentricity"),
            mass_kg=mass_kg,
            radius_km=radius_km,
            mass_type=table.text(row, "mass type"),
            confidence=table.text(row, "confidence tier"),
            detection=table.text(row, "detection method"),
            orbit_source=table.text(row, "orbit data source/flags"),
            reference=table.text(row, "source/discovery reference"),
        ))
    return out


def _score(p: PlanetRecord) -> int:
    """How complete a planet row is, for de-duplicating across tabs."""
    return sum(v is not None for v in
               (p.semi_major_axis_au, p.period_days, p.eccentricity,
                p.mass_kg, p.radius_km))


def parse_workbook(workbook: dict) -> Catalog:
    """Convert raw tab values into an indexed Catalog."""
    tables = build_tables(workbook)
    roles = classify_tables(tables)

    catalog = Catalog(
        spreadsheet_id=workbook.get("spreadsheet_id", ""),
        workbook_title=workbook.get("title", ""),
        fetched_at=workbook.get("fetched_at", 0.0),
    )

    # Rejected candidates first, so no planet tab can bring one back.  A row
    # tiered `unlikely` is rejected wherever it sits, as a second guard for
    # one not yet moved to the rejected tab.
    for table in roles["rejected"]:
        for row in table.rows:
            name = table.text(row, "planet")
            if name:
                catalog.rejected[match_key(name)] = RejectedRecord(
                    name=name, host=table.text(row, "host system (primary star)"),
                    reason=table.text(row, "rejected because"))

    # Planets can appear on more than one tab (confirmed and candidate lists).
    # Keep whichever row carries the most orbital detail.  Case counts here:
    # 'HD 3651 B', a brown dwarf and so a planet (7 Oct 2026), is not the
    # planet 'HD 3651 b'.
    best: dict[str, PlanetRecord] = {}
    for table in roles["planets"]:
        for rec in _planet_records(table):
            key = match_key(rec.name)
            same = re.sub(r"[\s_-]+", "", rec.name.strip())
            if rec.confidence.lower().startswith("unlikely"):
                catalog.rejected.setdefault(key, RejectedRecord(
                    name=rec.name, host=rec.host,
                    reason=f"tiered unlikely on {table.title}"))
            if key in catalog.rejected:
                continue
            if same not in best or _score(rec) > _score(best[same]):
                best[same] = rec
    planetless = {table.text(row, "system/host") for table in roles["four_plus"]
                  for row in table.rows} - {""}
    for rec in best.values():
        if rec.host in planetless:
            catalog.planetless_planets.setdefault(rec.host, []).append(rec)
            continue
        catalog.planets_by_host.setdefault(rec.orbit_host, []).append(rec)
        catalog.system_of.setdefault(rec.orbit_host, rec.host)
    for plist in [*catalog.planets_by_host.values(), *catalog.planetless_planets.values()]:
        plist.sort(key=lambda p: (p.semi_major_axis_au is None,
                                  p.semi_major_axis_au or 0.0,
                                  p.name))

    for table in roles["moons"]:
        for moon in _moon_records(table):
            catalog.moons_by_planet.setdefault(match_key(moon.planet), []).append(moon)

    for table in roles["stars"]:
        for rec in _star_records(table):
            bucket = catalog.stars_by_host.setdefault(rec.host, [])
            if not any(s.component == rec.component for s in bucket):
                bucket.append(rec)
            catalog.stars_by_component.setdefault(match_key(rec.component), rec)

    for table in roles["systems"]:
        for row in table.rows:
            host = table.text(row, "system/host")
            if not host or host in catalog.system_rows:
                continue
            catalog.system_rows[host] = {
                "nickname": table.text(row, "nickname (iau)"),
                "distance_ly": table.number(row, "distance (ly)"),
                "mass_sun": table.number(row, "host mass (m-sun)"),
                "stellar_class": table.text(row, "stellar class"),
                "luminosity_class": table.text(row, "luminosity class"),
                "effective_temp_k": table.number(row, "effective temp (k)"),
                "luminosity_sun": table.number(row, "host luminosity (l-sun)"),
                "stars_in_system": table.number(row, "stars in system"),
                "hz_distance": table.text(row, "hz distance"),
                "hz_planet_names": table.text(row, "hz planet names"),
                "age_gyr": table.number(row, "age (gyr)"),
                "ra_deg": table.number(row, "ra (deg, icrs)"),
                "dec_deg": table.number(row, "dec (deg, icrs)"),
                # Kinematics, for the Nearby Stellar Motion view.  The galactic
                # columns are computed on the sheet from RA/Dec, distance, RV
                # and proper motion (Sources & Provenance, 24 Sep 2026).
                "metallicity": table.number(row, "metallicity [fe/h]"),
                "confirmed_planets": table.number(row, "confirmed planets"),
                "system_stars": table.text(row, "system stars"),
                "radial_velocity_kms": table.number(row, "radial velocity (km/s)"),
                "total_pm_arcsec_yr": table.number(row, "total proper motion, μ (arcsec/yr)"),
                "space_velocity_kms": table.number(row, "space velocity (km/s)"),
                "gal_l_deg": table.number(row, "galactic longitude l (deg)"),
                "gal_b_deg": table.number(row, "galactic latitude b (deg)"),
                "motion_l_deg": table.number(row, "motion toward l (deg, heliocentric)"),
                "motion_b_deg": table.number(row, "motion toward b (deg, heliocentric)"),
                "kinematics_source": table.text(row, "kinematics source"),
                **source_columns(table, row),
            }

    for table in (t for t in tables if t.has(*KNOWN_SIGNATURE)):
        for row in table.rows:
            name = table.text(row, "system/host")
            if not name or table.text(row, "plotted").upper() != "FALSE":
                continue
            catalog.known_unplotted.append({
                "name": name,
                "distance_ly": table.number(row, "distance (ly)"),
                "gal_l_deg": table.number(row, "galactic longitude l (deg)"),
                "gal_b_deg": table.number(row, "galactic latitude b (deg)"),
                "space_velocity_kms": table.number(row, "space velocity (km/s)"),
                "motion_l_deg": table.number(row, "motion toward l (deg, heliocentric)"),
                "motion_b_deg": table.number(row, "motion toward b (deg, heliocentric)"),
                "radial_velocity_kms": table.number(row, "radial velocity (km/s)"),
                "total_pm_arcsec_yr": table.number(row, "total proper motion, μ (arcsec/yr)"),
                "kinematics_source": table.text(row, "kinematics source"),
                **source_columns(table, row),
            })

    _build_aliases(catalog)
    return catalog


def _build_aliases(catalog: Catalog) -> None:
    """Index every name that should resolve to a system with planets.

    Every name in a system reaches the whole system: its primary, any member
    star, their nicknames, and every planet -- so "55 Cnc B", "Proxima Cen b"
    and "Copernicus" each open the system they belong to.  Targets are stored
    as sets so a name that genuinely reaches two systems is reported as
    ambiguous rather than guessed.
    """
    alias = catalog._aliases

    def add(name: str, system: str) -> None:
        if name:
            alias.setdefault(match_key(name), set()).add(system)

    systems = {catalog.system_of.get(h, h) for h in catalog.planets_by_host}
    for host, planets in catalog.planets_by_host.items():
        system = catalog.system_of.get(host, host)
        add(host, system)
        for p in planets:
            add(p.name, system)

    for system in systems:
        add(system, system)
        srow = catalog.system_rows.get(system, {})
        if srow.get("nickname"):
            add(srow["nickname"], system)
        for name in catalog.members(system):
            add(name, system)
            star = catalog.stars_by_component.get(match_key(name))
            if star and star.nickname:
                add(star.nickname, system)


# --------------------------------------------------------------------------
# Presentation helpers
# --------------------------------------------------------------------------

def _phase_deg(name: str) -> float:
    """Stable pseudo-random mean anomaly so planets do not start collinear."""
    digest = hashlib.sha1(name.encode("utf-8")).digest()
    return (int.from_bytes(digest[:4], "big") % 360_000) / 1000.0


# Rough blackbody appearance by effective temperature.
_TEMP_COLORS = [
    (3000, "#FF6644"),
    (3900, "#FF8C4A"),
    (5300, "#FFCC77"),
    (6000, "#FFF7AA"),
    (7500, "#FFFFEE"),
    (10000, "#DDE8FF"),
    (30000, "#AACCFF"),
]


def star_color(teff_k: Optional[float]) -> str:
    if teff_k is None:
        return "#FFD98C"
    for ceiling, color in _TEMP_COLORS:
        if teff_k <= ceiling:
            return color
    return _TEMP_COLORS[-1][1]


def star_radius_km(luminosity_sun: Optional[float],
                   teff_k: Optional[float]) -> Optional[float]:
    """Stefan-Boltzmann radius from luminosity and temperature.

    R/Rsun = sqrt(L/Lsun) * (Tsun/Teff)^2.  The spreadsheet carries no stellar
    radii, so this is derived, not observed.
    """
    if not luminosity_sun or not teff_k or luminosity_sun <= 0 or teff_k <= 0:
        return None
    r_sun = (luminosity_sun ** 0.5) * (T_SUN_K / teff_k) ** 2
    return r_sun * R_SUN_KM


def hz_color(hz_position: str) -> Optional[str]:
    """Colour a planet by where it sits relative to the habitable zone."""
    s = hz_position.lower()
    if not s:
        return None
    if "closer" in s or "inward" in s or "too close" in s:
        return "#EE7744"
    if "farther" in s or "further" in s or "beyond" in s or "outward" in s:
        return "#5588CC"
    if "hz" in s or "habitable" in s:
        return "#44BB66"
    return None


def _is_confirmed(rec: PlanetRecord) -> bool:
    tier = rec.confidence.lower()
    if not tier:
        return True
    return tier.startswith("confirm")


# --------------------------------------------------------------------------
# StarSystem construction
# --------------------------------------------------------------------------

@dataclass
class _StarFacts:
    """One star's properties, from the best row that has them."""
    name: str
    mass_sun: Optional[float]
    teff: Optional[float]
    lum: Optional[float]
    stellar_class: str
    distance_ly: Optional[float]
    nickname: str


def _star_facts(catalog: Catalog, name: str, system_host: str) -> _StarFacts:
    """Prefer the stars tab, then the systems tab, then the planet rows' copy.

    The systems tab describes the primary, so it only speaks for this star
    when this star *is* the system -- Proxima's system row is alf Cen A's, and
    'Rigil Kentaurus' is not Proxima's name.  Stars that appear only on the
    planet tabs still get a class, a distance and a luminosity this way.
    """
    star = catalog.stars_by_component.get(match_key(name))
    srow = catalog.system_rows.get(system_host, {}) if name == system_host else {}
    planets = catalog.planets_by_host.get(name, [])
    p0 = planets[0] if planets else None
    return _StarFacts(
        name=name,
        mass_sun=_first(star and star.mass_sun, srow.get("mass_sun")),
        teff=_first(star and star.effective_temp_k, srow.get("effective_temp_k")),
        lum=_first(star and star.luminosity_sun, srow.get("luminosity_sun"),
                   p0 and p0.host_luminosity_sun),
        stellar_class=_first(star and star.stellar_class,
                             srow.get("stellar_class"),
                             p0 and (p0.planet_host_class or p0.primary_class)) or "",
        distance_ly=_first(star and star.distance_ly, srow.get("distance_ly"),
                           p0 and p0.distance_ly),
        nickname=_first(star and star.nickname, srow.get("nickname")) or "",
    )


def _companion_elements(star: StarRecord, own_mass_sun: Optional[float],
                        parent_mass_sun: Optional[float]) -> KeplerianElements:
    """Where a companion is drawn, from the stars tab's Separation columns.

    A solved orbit keeps its eccentricity; a projected separation is a circle
    at that distance -- the only honest shape for a pair with no orbit, and a
    lower bound on the real one.  The period is Kepler's third law on the two
    masses, so the drawing moves at the right rate for its size.
    """
    a = star.separation_au
    ecc = (star.orbit_eccentricity or 0.0) if star.has_solved_orbit else 0.0
    ecc = min(max(ecc, 0.0), MAX_ECCENTRICITY)
    total_sun = ((own_mass_sun or 0.0) + (parent_mass_sun or 0.0)) or 1.0
    return KeplerianElements(
        semi_major_axis=a,
        eccentricity=ecc,
        inclination=0.0,
        longitude_of_ascending_node=0.0,
        argument_of_periapsis=0.0,
        mean_anomaly_at_epoch=_phase_deg(star.component),
        epoch=J2000,
        period=derive_period_days(a, total_sun * M_SUN_KG),
    )


def build_star_system(catalog: Catalog, identifier: str,
                      bands: SolventChoice = DEFAULT_CHOICE) -> StarSystem:
    """Assemble one whole system from the catalog: every star, every planet.

    The primary sits at the origin.  Each other star is drawn around the star
    its Separation row names, and each planet around the star it orbits -- so
    a planet of a companion traces the coil it really does in the primary's
    frame.  A planet filed under the system's own name when that is not one
    of its stars (RR Cae's circumbinary planet) goes round the primary.

    Raises:
        ValueError: if the identifier does not resolve, or the system has no
                    planet with enough orbital data to plot.
    """
    system_host = catalog.resolve_host(identifier)
    members = catalog.members(system_host)
    root = members[0]
    facts = {name: _star_facts(catalog, name, system_host) for name in members}
    root_facts = facts[root]

    sheet_url = (f"https://docs.google.com/spreadsheets/d/"
                 f"{catalog.spreadsheet_id}/edit" if catalog.spreadsheet_id else "")
    sheet_label = catalog.workbook_title or "Catalog spreadsheet"
    base_sources = [[f"{sheet_label} (Google Sheets)", sheet_url]]

    def star_body(f: _StarFacts, parent: Optional[str] = None,
                  elements: Optional[KeplerianElements] = None,
                  status: str = "confirmed",
                  sources: Optional[list] = None) -> OrbitalBody:
        return OrbitalBody(
            name=f.name,
            body_type="star",
            parent=parent,
            radius_km=star_radius_km(f.lum, f.teff),
            mass_kg=f.mass_sun * M_SUN_KG if f.mass_sun else None,
            luminosity_sun=f.lum,
            teff_k=f.teff,
            color=star_color(f.teff),
            display_name=f.nickname or None,
            status=status,
            sources=sources or list(base_sources),
            elements=elements,
        )

    # Stars, parents before children: the mechanics add a parent's position
    # to its child's, so a parent has to be placed first.
    bodies: list[OrbitalBody] = [star_body(root_facts)]
    placed = {root}
    projected: list[str] = []
    assumed: list[str] = []
    pending = members[1:]
    progress = True
    while pending and progress:
        progress = False
        for name in list(pending):
            rec = catalog.stars_by_component.get(match_key(name))
            if rec is None or not rec.separation_au or rec.separation_au <= 0:
                continue
            parent = rec.separation_from if rec.separation_from in members else root
            if parent not in placed:
                continue
            sources = list(base_sources)
            if rec.separation_source:
                sources.append([f"Separation: {rec.separation_source}", sheet_url])
            bodies.append(star_body(
                facts[name], parent=parent,
                elements=_companion_elements(rec, facts[name].mass_sun,
                                             facts[parent].mass_sun),
                status="confirmed" if rec.has_solved_orbit else "hypothetical",
                sources=sources,
            ))
            if rec.has_assumed_separation:
                assumed.append(name)
            elif not rec.has_solved_orbit:
                projected.append(name)
            placed.add(name)
            pending.remove(name)
            progress = True
    unplaced = pending

    skipped: list[str] = []
    stranded: list[str] = []
    n_planets = 0

    def add_planets(records: list[PlanetRecord], parent: str) -> None:
        nonlocal n_planets
        for rec in records:
            if parent not in placed:
                stranded.append(rec.name)
                continue
            body = _planet_body(rec, parent, facts[parent].mass_sun,
                                base_sources, sheet_url)
            if body is None:
                skipped.append(rec.name)
                continue
            bodies.append(body)
            n_planets += 1

    for star_name in members:
        add_planets(catalog.planets_by_host.get(star_name, []), star_name)
    if system_host not in members:
        add_planets(catalog.planets_by_host.get(system_host, []), root)
    records = {r.name: r for rs in catalog.planets_by_host.values() for r in rs}
    direction_notes = _spin_axes(bodies, records)

    # Moons after every planet, since each goes round a planet already placed.
    moons: list[str] = []
    rejected_moons: list[str] = []
    for planet in [b for b in bodies if b.body_type == "planet"]:
        for rec in catalog.moons_by_planet.get(match_key(planet.name), []):
            if rec.is_rejected:
                rejected_moons.append(rec.name)
                continue
            body = _moon_body(rec, planet, base_sources, sheet_url)
            if body is None:
                skipped.append(rec.name)
                continue
            bodies.append(body)
            moons.append(f"{rec.name} ({rec.confidence or 'untiered'})")

    cls, dist = root_facts.stellar_class, root_facts.distance_ly
    bits = [b for b in (cls, f"{dist:.2f} ly" if dist else "") if b]
    header = f"{system_host}" + (f" ({', '.join(bits)})" if bits else "")
    notes = [f"{header}. {n_planets} planets from the catalog spreadsheet."]
    if n_planets:
        notes.append(
            "Inclination, ascending node and argument of periapsis are not in the "
            "catalog, so orbits are drawn co-planar and the starting phase of each "
            "planet is arbitrary.")
        notes += direction_notes
    else:
        # Still worth opening: the stars, their bands, and where it is.
        notes.append("No planet here has a semi-major axis or period on file "
                     "(or a host mass to derive one from), so only the stars are drawn.")
    if moons:
        notes.append(f"{len(moons)} moon{'s' if len(moons) > 1 else ''} from the "
                     f"exomoon tab: {', '.join(moons)}.")
    stars_drawn = [b.name for b in bodies if b.body_type == "star"]
    if len(stars_drawn) > 1:
        notes.append(f"{len(stars_drawn)} stars: {', '.join(stars_drawn)}.")
    if projected:
        notes.append(
            "No orbit has been solved for " + ", ".join(projected) + ", so each "
            "is drawn on a circle at its projected separation -- a lower bound "
            "on the real one -- and marked hypothetical."
        )
    if assumed:
        notes.append(
            "Suspected, never resolved: " + ", ".join(assumed) + " -- drawn on a "
            "circle at an assumed separation (inferred, see the sheet's note) and "
            "marked hypothetical."
        )
    if unplaced:
        notes.append("Not plotted, no separation on file: "
                     + ", ".join(unplaced) + ".")
    if stranded:
        notes.append("Not plotted because their star is not: "
                     + ", ".join(stranded) + ".")
    if skipped:
        notes.append("No orbit data: " + ", ".join(skipped) + ".")
    rejected = catalog.rejected_in(system_host)
    if rejected:
        notes.append("Rejected candidates, not drawn: " + ", ".join(rejected) + ".")
    if rejected_moons:
        notes.append("Rejected moon candidates, not drawn: "
                     + ", ".join(rejected_moons) + ".")

    # The Solar System arrow needs the star's RA/Dec. With no measured
    # inclination the disc is drawn in the ecliptic, the frame the
    # galactic-centre arrow and the sky already use for a catalog system, so
    # the arrow is placed right against both and only the disc's tilt is a guess.
    srow = catalog.system_rows.get(system_host, {})
    ra, dec = srow.get("ra_deg"), srow.get("dec_deg")
    toward_sun = (toward_sun_in_ecliptic(ra, dec)
                  if ra is not None and dec is not None else None)
    if toward_sun:
        notes.append("The Solar System arrow is placed from the star's RA and "
                     "Dec; the disc's tilt against it is not known.")

    # One band stack per luminous star, each centred on its own star.
    belt_zones = bands.zones_for_system(bodies)
    if belt_zones:
        notes.append(bands.note(root_facts.lum, bodies, root, root_facts.teff))

    return StarSystem(
        name=system_host,
        description=" ".join(notes),
        bodies=bodies,
        source="catalog",
        belt_zones=belt_zones,
        distance_from_sun_ly=dist,
        solar_system_direction=toward_sun,
    )


def _planet_body(rec: PlanetRecord, parent: str, star_mass_sun: Optional[float],
                 base_sources: list, sheet_url: str) -> Optional[OrbitalBody]:
    """One planet around one star, or None when the row has no usable orbit."""
    star_mass_kg = star_mass_sun * M_SUN_KG if star_mass_sun else None
    a = rec.semi_major_axis_au
    p = rec.period_days
    if a is None and p is not None and star_mass_kg:
        a = derive_semi_major_axis_au(p, star_mass_kg)
    if p is None and a is not None and star_mass_kg:
        p = derive_period_days(a, star_mass_kg)
    if a is None or p is None or a <= 0 or p <= 0:
        return None

    ecc = rec.eccentricity if rec.eccentricity is not None else 0.0
    ecc = min(max(ecc, 0.0), MAX_ECCENTRICITY)

    sources = list(base_sources)
    if rec.orbit_source:
        sources.append([f"Orbit data: {rec.orbit_source}", sheet_url])
    direction = rec.measured_direction or None
    if direction:
        sources.append([f"Orbit direction: {direction}"
                        + (f"; spin-orbit {rec.spin_orbit}" if rec.spin_orbit_deg is not None else ""), sheet_url])

    body = OrbitalBody(
        orbit_direction=direction,
        name=rec.name,
        body_type="planet",
        parent=parent,
        radius_km=rec.radius_km,
        mass_kg=rec.mass_kg,
        color=hz_color(rec.hz_position),
        status="confirmed" if _is_confirmed(rec) else "hypothetical",
        sources=sources,
        elements=KeplerianElements(
            semi_major_axis=a,
            eccentricity=ecc,
            inclination=0.0,
            longitude_of_ascending_node=0.0,
            argument_of_periapsis=0.0,
            mean_anomaly_at_epoch=_phase_deg(rec.name),
            epoch=J2000,
            period=p,
        ),
    )
    # Retrograde against its companion or siblings: tilted by the measured mutual inclination from the
    # reference plane the binary is drawn in (nu Oct A b 174 deg), or the same plane gone round the other way.
    # (Against the star's spin it is the star's axis that turns -- _spin_axes.)
    if reversed_orbit(body):
        body.elements.inclination = rec.direction_angle_deg or 180.0
    return body


def _rotate_about(n, u, deg: float) -> tuple[float, float, float]:
    """n turned by deg about the unit axis u, which is perpendicular to it (Rodrigues)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    cross = (u[1] * n[2] - u[2] * n[1], u[2] * n[0] - u[0] * n[2], u[0] * n[1] - u[1] * n[0])
    return tuple(c * a + s * b for a, b in zip(n, cross))


def _spin_axes(bodies: list[OrbitalBody], records: dict[str, PlanetRecord]) -> list[str]:
    """Give each star with a planet of measured orbit direction the spin axis that shows it.

    Against the star's spin (polar or retrograde): the planet stays in its plane and the star's
    axis is the plane's normal turned by the measured spin-orbit angle -- lying in the plane at
    90 deg, pointing below it past 90.  Against a companion or siblings (nu Oct A b, drawn at
    i = 180): the star's spin was never measured, so its axis is assumed to follow the binary or
    the other planets -- the plane's normal -- and is drawn dashed.  The axis is 0.8 of the
    planet's semi-major axis long each way, so it reads against that orbit.  Returns notes.
    """
    notes = []
    by_name = {b.name: b for b in bodies}
    for planet in [b for b in bodies if b.body_type == "planet" and b.orbit_direction]:
        star = by_name.get(planet.parent)
        if star is None or star.body_type != "star" or star.pole is not None:
            continue
        rec = records[planet.name]
        normal = band_plane(bodies, star.name)
        d = planet.orbit_direction.lower()
        half = 0.8 * planet.elements.semi_major_axis
        if d.startswith("prograde"):
            continue
        if "stellar spin" in d:
            psi = rec.spin_orbit_deg
            if psi is None:
                psi = 90.0 if d.startswith("polar") else 180.0
                how = f"{planet.orbit_direction}, angle not measured: {psi:g} deg drawn"
            else:
                how = f"spin-orbit {rec.spin_orbit}"
            star.pole = _rotate_about(normal, plane_basis(normal)[0], abs(psi))
            star.axial_tilt_deg = abs(psi)
            star.pole_note = f"vs {planet.name}'s orbit: {how}"
            notes.append(f"{planet.name}: {planet.orbit_direction}; {star.name}'s axis is tilted {abs(psi):g} deg "
                         "from the planet's orbit.")
        else:
            against = ("the host binary's orbit" if "host binary" in d else "the binary orbit" if "binary" in d
                       else "the other planets")
            # The binary's own orbit where the star has a companion drawn round it.  With none drawn (VHS 1256's
            # host binary is one star here) the reference plane stands for the binary, as the planet's measured
            # mutual inclination is drawn from it; against the other planets, their plane.
            if "binary" in d:
                star.pole = tuple(partner_plane(bodies, star.name) or Z_AXIS)
            else:
                star.pole = tuple(normal)
            star.pole_assumed = True
            star.pole_note = f"assumed: aligned with {against}"
            notes.append(f"{planet.name}: {planet.orbit_direction}, drawn inclined "
                         f"{planet.elements.inclination:g} deg to {against}, so going round the other way; "
                         f"{star.name}'s axis is assumed to follow {against} (dashed).")
        star.axis_half_au = half
    return notes


def _moon_body(rec: MoonRecord, planet: OrbitalBody, base_sources: list,
               sheet_url: str) -> Optional[OrbitalBody]:
    """One moon around its planet, or None when the row has no usable orbit.

    Kepler's third law on the planet's mass fills whichever of a and P is
    missing; the moon's own mass is left out, as it is for planets.
    """
    a, p = rec.semi_major_axis_au, rec.period_days
    if a is None and p is not None and planet.mass_kg:
        a = derive_semi_major_axis_au(p, planet.mass_kg)
    if p is None and a is not None and planet.mass_kg:
        p = derive_period_days(a, planet.mass_kg)
    if a is None or p is None or a <= 0 or p <= 0:
        return None

    ecc = rec.eccentricity if rec.eccentricity is not None else 0.0
    ecc = min(max(ecc, 0.0), MAX_ECCENTRICITY)

    sources = list(base_sources)
    if rec.reference:
        sources.append([rec.reference, sheet_url])
    if rec.orbit_source:
        sources.append([f"Orbit data: {rec.orbit_source}", sheet_url])

    return OrbitalBody(
        name=rec.name,
        body_type="moon",
        parent=planet.name,
        mass_kg=rec.mass_kg,
        radius_km=rec.radius_km,
        status="confirmed" if rec.confidence.lower().startswith("confirm") else "hypothetical",
        sources=sources,
        elements=KeplerianElements(
            semi_major_axis=a,
            eccentricity=ecc,
            inclination=0.0,
            longitude_of_ascending_node=0.0,
            argument_of_periapsis=0.0,
            mean_anomaly_at_epoch=_phase_deg(rec.name),
            epoch=J2000,
            period=p,
        ),
    )


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------

def get_catalog(spreadsheet_id: Optional[str] = None, **kwargs) -> Catalog:
    """Fetch (or reuse cached) workbook values and parse them.

    Reads the committed snapshot instead when $HYBRASIL_DATA_SOURCE=snapshot.
    """
    from .snapshot import load_snapshot_workbook, snapshot_only
    if snapshot_only():
        return parse_workbook(load_snapshot_workbook())
    from .google_sheets import get_workbook
    return parse_workbook(get_workbook(spreadsheet_id, **kwargs))


def load_catalog_system(identifier: str,
                        spreadsheet_id: Optional[str] = None,
                        bands: SolventChoice = DEFAULT_CHOICE,
                        **kwargs) -> StarSystem:
    """Load one catalog system by host name, nickname, or planet name."""
    return build_star_system(get_catalog(spreadsheet_id, **kwargs), identifier,
                             bands)


def catalog_entry(catalog: Catalog, host: str) -> dict:
    """What a listing says about one system.

    Every planet on file, around any of its stars -- with an orbit or not, so
    searching for one finds its system; the primary's
    spectral class, distance and IAU nickname; and the other stars' names,
    so a search for a companion finds the system it belongs to.
    """
    members = catalog.members(host)
    planets = [p for name in dict.fromkeys(members + [host])
               for p in catalog.planets_by_host.get(name, [])]
    f = _star_facts(catalog, members[0], host)
    return {"planets": [p.name for p in planets], "stellar_class": f.stellar_class,
            "distance_ly": f.distance_ly, "nickname": f.nickname,
            "stars": members}


def catalog_listing(catalog: Catalog) -> list[str]:
    """One human-readable line per plottable system, for --list-catalog."""
    lines = []
    for host in catalog.hosts():
        entry = catalog_entry(catalog, host)
        cls, dist = entry["stellar_class"], entry["distance_ly"]
        parts = [f"{host:<28}", f"{len(entry['stars'])} star(s)",
                 f"{len(entry['planets']):>2} planet(s)"]
        if cls:
            parts.append(f"{cls:<10}")
        if dist:
            parts.append(f"{dist:>7.2f} ly")
        lines.append("  ".join(parts))
    return lines
