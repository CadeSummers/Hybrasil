# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
from dataclasses import dataclass


@dataclass
class KeplerianElements:
    """Orbital elements defining an elliptical orbit.

    All angles in degrees. Distances in AU. Time in Julian Date / days.
    """
    semi_major_axis: float          # AU
    eccentricity: float             # 0 <= e < 1 for elliptical orbits
    inclination: float              # degrees
    longitude_of_ascending_node: float  # degrees (Omega)
    argument_of_periapsis: float    # degrees (omega)
    mean_anomaly_at_epoch: float    # degrees (M0)
    epoch: float                    # Julian Date of the reference epoch
    period: float                   # orbital period in days
