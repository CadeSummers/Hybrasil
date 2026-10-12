# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NearbyStar:
    """One system of the Systems tab, as the Nearby Stellar Motion view draws it.

    Where it is and how it moves, both relative to the Sun and in galactic
    coordinates: (l, b) is its direction from the Sun, (motion_l, motion_b) the
    direction of its heliocentric velocity, `speed_kms` that velocity's size.
    A star with no radial velocity or proper motion on file has no motion.
    """
    name: str
    stellar_class: str = ""
    luminosity_class: str = ""
    distance_ly: Optional[float] = None
    l_deg: Optional[float] = None
    b_deg: Optional[float] = None
    speed_kms: Optional[float] = None
    motion_l_deg: Optional[float] = None
    motion_b_deg: Optional[float] = None
    radial_velocity_kms: Optional[float] = None
    total_pm_arcsec_yr: Optional[float] = None
    age_gyr: Optional[float] = None
    mass_sun: Optional[float] = None
    metallicity: Optional[float] = None
    luminosity_sun: Optional[float] = None
    nickname: str = ""
    partners: list[str] = field(default_factory=list)   # the system's other stars
    planets: list[str] = field(default_factory=list)
    n_planets: Optional[int] = None
    kinematics_source: str = ""
    is_sun: bool = False
    # A system of the Planetless 4+ Stars tab rather than the Systems tab: offered behind the view's
    # Planetless Systems button, off by default.  `system_id` is the id that opens it ("planetless:<host>").
    planetless: bool = False
    system_id: str = ""
    # An object of the Known within 100ly tab that no tab plots: unclassified, drawn in the view's purple
    # optional layer rather than as a star of its own.
    known: bool = False
    # Where it is on record, for the info panel's Sources (data/star_sources.py): its catalog identifiers, the
    # workbook's Existence verdict ('confirmed: SIMBAD, Gaia DR3' / 'unconfirmed: only cited in Gaia DR3 ...'),
    # its Kinematics refs, and the [label, url] links built from them.
    gaia_id: str = ""
    simbad_id: str = ""
    cns5_id: str = ""
    wds: str = ""
    existence: str = ""
    kinematics_refs: str = ""
    sources: list = field(default_factory=list)

    @property
    def has_position(self) -> bool:
        return self.is_sun or None not in (self.distance_ly, self.l_deg, self.b_deg)

    @property
    def existence_unconfirmed(self) -> bool:
        """Only Gaia DR3 lists it: no SIMBAD entry, not in CNS5 (the Existence column says so)."""
        return self.existence.lower().startswith("unconfirmed")

    @property
    def has_motion(self) -> bool:
        return None not in (self.speed_kms, self.motion_l_deg, self.motion_b_deg)
