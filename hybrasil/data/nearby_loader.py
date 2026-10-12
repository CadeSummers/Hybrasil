# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Every system on the Systems tab, as the Nearby Stellar Motion view draws it.

Positions and motions are the sheet's own galactic columns, read by header: the
view shows exactly what the sheet says, and the arithmetic behind those columns
is recorded on Sources & Provenance, not repeated here.

The data comes from the live sheet when it can be reached and from the
committed snapshot (`snapshot.py`) when it cannot, so the featured view opens
without a Google credential.  Which one was used is returned with the stars.
"""

from __future__ import annotations

import sys
from typing import Optional

from ..models.nearby import NearbyStar
from . import star_sources
from .catalog_loader import Catalog, _is_confirmed, _star_facts, parse_workbook

SUN = "Sun"


def _planet_label(p) -> str:
    """A planet's name, with its tier when it is not a confirmed planet.

    The eight Solar System planets carry the tier 'Solar System reference';
    they are as confirmed as planets get.
    """
    tier = (p.confidence or "").strip()
    if _is_confirmed(p) or tier.lower().startswith("solar system"):
        return p.name
    return f"{p.name} ({tier} candidate)"


_IDS = ("gaia_id", "simbad_id", "cns5_id", "wds", "existence", "kinematics_refs")


def with_sources(s: NearbyStar, row: dict, exoplanet_host: str = "") -> NearbyStar:
    """Copy a row's identifier columns onto the star and build its Sources links: existence first, then motion."""
    for f in _IDS:
        setattr(s, f, str(row.get(f) or "").strip())
    if s.is_sun:
        s.sources = [star_sources.SUN_LSR]
        return s
    ids = dict(gaia_id=s.gaia_id, simbad_id=s.simbad_id, cns5_id=s.cns5_id, wds=s.wds)
    s.sources = (star_sources.existence_sources(exoplanet_host=exoplanet_host, **ids)
                 + star_sources.kinematics_sources(s.kinematics_refs, **ids))
    return s


def nearby_stars(catalog: Catalog) -> list[NearbyStar]:
    """One NearbyStar per Systems row, in sheet order, the Sun among them."""
    out = []
    for host, row in catalog.system_rows.items():
        members = catalog.members(host)
        partners = [m for m in members if m != host]
        if not partners and len(members) == 1 and (row.get("system_stars") or "").strip():
            # No stars-tab rows, but the Systems row names the stars itself.
            partners = [row["system_stars"].strip()]
        planets = []
        for star in dict.fromkeys(members + [host]):
            for p in catalog.planets_by_host.get(star, []):
                planets.append(_planet_label(p))
        n = row.get("confirmed_planets")
        # The primary's own facts: the stars tab first, then this row.  The
        # Systems tab's 'Host luminosity' is the PLANET host's on some rows
        # (alf Cen A carries Proxima's), so it cannot speak for the primary.
        facts = _star_facts(catalog, members[0], host)
        out.append(with_sources(NearbyStar(
            name=host,
            stellar_class=facts.stellar_class or row.get("stellar_class") or "",
            luminosity_class=row.get("luminosity_class") or "",
            distance_ly=0.0 if host == SUN else row.get("distance_ly"),
            l_deg=row.get("gal_l_deg"),
            b_deg=row.get("gal_b_deg"),
            speed_kms=row.get("space_velocity_kms"),
            motion_l_deg=row.get("motion_l_deg"),
            motion_b_deg=row.get("motion_b_deg"),
            radial_velocity_kms=row.get("radial_velocity_kms"),
            total_pm_arcsec_yr=row.get("total_pm_arcsec_yr"),
            age_gyr=row.get("age_gyr"),
            mass_sun=facts.mass_sun,
            metallicity=row.get("metallicity"),
            luminosity_sun=facts.lum,
            nickname=row.get("nickname") or "",
            partners=partners,
            planets=planets,
            n_planets=int(n) if n is not None else None,
            kinematics_source=row.get("kinematics_source") or "",
            is_sun=host == SUN,
        ), row, exoplanet_host=host if "NASA Exoplanet Archive" in (row.get("existence") or "") else ""))
    return out


def planetless_nearby(systems: dict) -> list[NearbyStar]:
    """One NearbyStar per Planetless 4+ Stars system, from its host star's row.

    `systems` is what `planetless_loader.load_planetless()` returns.  The host
    row carries the same galactic columns as a Systems row (data/four_plus_stars/
    kinematics.py); the star's own mass and luminosity come from that row too.
    The featured Castor opens as itself, every other system as planetless:<host>.
    """
    from ..data.builtin_systems import CATALOG_PREFIX, system_id_for_host
    from .planetless_loader import PREFIX
    out = []
    for host, ps in systems.items():
        m = ps.motion or {}
        origin = next((r for r in ps.rows if r.name == ps.origin), None)
        key = system_id_for_host(host)
        out.append(with_sources(NearbyStar(
            name=host,
            stellar_class=ps.stellar_class,
            luminosity_class=m.get("luminosity_class") or "",
            distance_ly=ps.distance_ly or None,
            l_deg=m.get("l_deg"), b_deg=m.get("b_deg"),
            speed_kms=m.get("speed_kms"), motion_l_deg=m.get("motion_l_deg"), motion_b_deg=m.get("motion_b_deg"),
            radial_velocity_kms=m.get("radial_velocity_kms"), total_pm_arcsec_yr=m.get("total_pm_arcsec_yr"),
            age_gyr=m.get("age_gyr"), metallicity=m.get("metallicity"),
            mass_sun=origin.mass_sun if origin else None,
            luminosity_sun=origin.luminosity_sun if origin else None,
            nickname=ps.nickname,
            partners=[s for s in ps.stars if s != ps.origin],
            planets=[_planet_label(pl) for pl in ps.planets], n_planets=len(ps.planets),
            kinematics_source=m.get("kinematics_source") or "",
            planetless=True,
            system_id=PREFIX + host if key.startswith(CATALOG_PREFIX) else key,
        ), m))
    return out


def known_nearby(catalog: Catalog) -> list[NearbyStar]:
    """Every unplotted object of the Known within 100ly tab, unclassified.

    The tab's own position and motion columns, read by header (filled by
    data/known_within_100ly/kinematics/).  An object any other tab draws is left
    out, so nothing is drawn twice.
    """
    from .catalog_loader import match_key
    drawn = {match_key(n) for n in catalog.system_rows} | set(catalog.stars_by_component)
    # The cloud builds its panels' links in the browser from these ids (star_motion.known_cloud), so no
    # `sources` list is made here for ten thousand objects.
    return [NearbyStar(
        name=r["name"], distance_ly=r["distance_ly"], l_deg=r["gal_l_deg"], b_deg=r["gal_b_deg"],
        speed_kms=r["space_velocity_kms"], motion_l_deg=r["motion_l_deg"], motion_b_deg=r["motion_b_deg"],
        radial_velocity_kms=r["radial_velocity_kms"], total_pm_arcsec_yr=r["total_pm_arcsec_yr"],
        kinematics_source=r["kinematics_source"], known=True,
        **{f: str(r.get(f) or "").strip() for f in _IDS},
    ) for r in catalog.known_unplotted if match_key(r["name"]) not in drawn]


def load_planetless_nearby(systems: Optional[dict] = None) -> list[NearbyStar]:
    """The planetless systems for the view: the ones given (the web app's), else the tab, live or snapshot.

    A failure costs these systems and nothing else: the view still opens.
    """
    if systems is None:
        try:
            from .planetless_loader import load_planetless
            systems = load_planetless()[0]
        except Exception as e:
            print(f"Nearby Stellar Motion: Planetless 4+ Stars unavailable ({e.__class__.__name__}).",
                  file=sys.stderr)
            return []
    return planetless_nearby(systems)


# Set to "snapshot" to skip the live sheet (snapshot.SOURCE_ENV); kept here
# under its old name for the loaders that import it from this module.
from .snapshot import SOURCE_ENV, snapshot_only  # noqa: E402


def _from_snapshot() -> tuple[Catalog, str]:
    from .snapshot import load_snapshot_workbook
    wb = load_snapshot_workbook()
    return parse_workbook(wb), f"snapshot {wb['title']}"


def nearby_catalog(catalog: Optional[Catalog] = None) -> tuple[Catalog, str]:
    """(catalog, where it came from): the given catalog, the live sheet, or the snapshot."""
    if catalog is None and snapshot_only():
        return _from_snapshot()
    if catalog is None:
        try:
            from .catalog_loader import get_catalog
            catalog = get_catalog()
        except Exception as e:                  # no credential, no network, no cache
            print(f"Nearby Stellar Motion: live sheet unavailable ({e.__class__.__name__}); "
                  "using the committed snapshot.", file=sys.stderr)
            return _from_snapshot()
    return catalog, f"sheet {catalog.workbook_title}" if catalog.workbook_title else "sheet"


def load_nearby(catalog: Optional[Catalog] = None) -> tuple[list[NearbyStar], str]:
    """(stars, where they came from): the given catalog, the live sheet, or the snapshot."""
    catalog, source = nearby_catalog(catalog)
    return nearby_stars(catalog), source
