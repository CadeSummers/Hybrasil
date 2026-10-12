# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional
from .elements import KeplerianElements


BodyType = Literal["star", "planet", "moon", "asteroid", "comet", "custom", "barycentre"]
BodyStatus = Literal["confirmed", "hypothetical"]


@dataclass
class OrbitalBody:
    """A single body in a star system."""
    name: str
    body_type: BodyType
    elements: Optional[KeplerianElements] = None   # None for the central star
    parent: Optional[str] = None                   # name of the body being orbited
    radius_km: Optional[float] = None
    mass_kg: Optional[float] = None
    luminosity_sun: Optional[float] = None   # bolometric, L/L_sun; stars only
    teff_k: Optional[float] = None           # effective temperature, K; stars only
    color: Optional[str] = None                    # hex or CSS color; None = auto-assigned
    display_name: Optional[str] = None             # override label in plot
    pole: Optional[tuple[float, float, float]] = None  # rotation-axis unit vector (J2000 ecliptic)
    axial_tilt_deg: Optional[float] = None             # degrees; None = unknown
    # A pole nobody measured, drawn because the model needs one (nu Oct A: assumed to spin with
    # the binary it is in).  Its axis is dashed and its name says so, with `pole_note` as the why.
    pole_assumed: bool = False
    pole_note: Optional[str] = None
    # Half the drawn axis, AU; None = the body type's default (themes.AXIS_HALF_LENGTHS), which is
    # far too long for a star whose planets are hundredths of an AU out.
    axis_half_au: Optional[float] = None
    # A planet's measured sense of orbit, as the sheet's Orbit Direction column words it:
    # "Retrograde (vs binary orbit)", "Polar (vs stellar spin)"; None = prograde, assumed.
    orbit_direction: Optional[str] = None
    sources: Optional[list] = None                     # [[label, url], ...] reference pairs
    status: BodyStatus = "confirmed"               # "confirmed" or "hypothetical"
    # How the info panel words a hypothetical body's status, where "Hypothetical"
    # alone would undersell it: "Hypothetical and model-inferred".
    status_note: Optional[str] = None
    # False for a body whose orbit is bookkeeping rather than something to look
    # at: a barycentre placed from a pair's primary exists only so the next
    # pair up has something to orbit, and its ellipse is a scaled copy of the
    # pair's own.  Its marker is still drawn and it still moves.
    draw_orbit: bool = True
    # The info panel's own [label, value, note] rows, in place of the
    # mass / period / velocity / tilt it would otherwise show: a body whose
    # facts are not those, such as an S-star or the black hole it orbits.
    info_rows: Optional[list] = None

    def label(self) -> str:
        return self.display_name if self.display_name else self.name
