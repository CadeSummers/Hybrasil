# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
import math
from datetime import date, datetime

AU_TO_KM = 1.495978707e8       # km per AU
KM_TO_AU = 1.0 / AU_TO_KM
G = 6.67430e-11                 # m^3 kg^-1 s^-2
SECONDS_PER_DAY = 86400.0
AU_TO_METERS = AU_TO_KM * 1000.0

J2000 = 2451545.0               # Julian Date of J2000.0 epoch

# Body masses and radii, for catalogues that quote values in solar / Jovian /
# Earth units rather than SI.
M_SUN_KG   = 1.98892e30
M_JUP_KG   = 1.89813e27
M_EARTH_KG = 5.97217e24
R_SUN_KM   = 695700.0
R_JUP_KM   = 69911.0
R_EARTH_KM = 6371.0

T_SUN_K = 5772.0                # Sun's effective temperature
L_SUN_W = 3.828e26              # Sun's bolometric luminosity, W (IAU 2015 B3)
STEFAN_BOLTZMANN = 5.670374419e-8   # W m^-2 K^-4

# A light year per year is the speed of light, so a speed in km/s converts to
# light years travelled per year exactly.
C_KMS = 299792.458
LY_PER_YEAR_PER_KMS = 1.0 / C_KMS

# Blackbody equilibrium temperature at 1 AU from the Sun for a perfect
# absorber: T = (L_sun / (16 pi sigma AU^2))^(1/4) = 278.33 K.  The reference
# point every solvent band is scaled from.
T_EQ_1AU_K = (L_SUN_W / (16.0 * math.pi * STEFAN_BOLTZMANN * AU_TO_METERS ** 2)) ** 0.25


def derive_period_days(semi_major_axis_au: float, parent_mass_kg: float) -> float:
    """Kepler's third law: T = 2*pi * sqrt(a^3 / (G*M))."""
    a_m = semi_major_axis_au * AU_TO_METERS
    t_seconds = 2.0 * math.pi * math.sqrt(a_m ** 3 / (G * parent_mass_kg))
    return t_seconds / SECONDS_PER_DAY


def derive_semi_major_axis_au(period_days: float, parent_mass_kg: float) -> float:
    """Inverse of derive_period_days: a = (G*M*(T/2*pi)^2)^(1/3)."""
    t_seconds = period_days * SECONDS_PER_DAY
    a_m = (G * parent_mass_kg * (t_seconds / (2.0 * math.pi)) ** 2) ** (1.0 / 3.0)
    return a_m / AU_TO_METERS


def jd_now() -> float:
    """Return the current Julian Date."""
    return datetime_to_jd(datetime.utcnow())


def datetime_to_jd(dt: datetime) -> float:
    """Convert a datetime (UTC) to Julian Date."""
    # Algorithm from Meeus, "Astronomical Algorithms"
    y, m, d = dt.year, dt.month, dt.day
    ut = dt.hour / 24.0 + dt.minute / 1440.0 + dt.second / 86400.0
    if m <= 2:
        y -= 1
        m += 12
    A = int(y / 100)
    B = 2 - A + int(A / 4)
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + ut + B - 1524.5
    return jd


def jd_from_date(year: int, month: int, day: int) -> float:
    return datetime_to_jd(datetime(year, month, day))


def jd_to_date(jd: float) -> tuple[int, int, int]:
    """Convert Julian Date to (year, month, day)."""
    jd = jd + 0.5
    Z = int(jd)
    F = jd - Z
    if Z < 2299161:
        A = Z
    else:
        alpha = int((Z - 1867216.25) / 36524.25)
        A = Z + 1 + alpha - int(alpha / 4)
    B = A + 1524
    C = int((B - 122.1) / 365.25)
    D = int(365.25 * C)
    E = int((B - D) / 30.6001)
    day = B - D - int(30.6001 * E)
    month = E - 1 if E < 14 else E - 13
    year = C - 4716 if month > 2 else C - 4715
    return year, month, day
