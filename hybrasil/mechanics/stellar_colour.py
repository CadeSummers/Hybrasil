# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""How a star's colour changes the flux a planet needs for the same climate.

Pure math, like the rest of `mechanics`.  The blackbody band in
`solvent_bands` takes a star's luminosity and nothing else, so a red dwarf
and a Sun-like star of the same brightness get the same band.  They should
not: a redder spectrum is Rayleigh-scattered less and absorbed more in the
near-IR, so a planet's albedo is lower and the same flux keeps it warmer.

Kopparapu et al. (2013) put a number on it.  Their climate model gives the
effective flux S_eff at each habitable-zone limit as a quartic in stellar
temperature:

    S_eff(Teff) = S0 + a t + b t^2 + c t^3 + d t^4,    t = Teff - 5780 K

valid for 2600 K <= Teff <= 7200 K.  This module uses the *runaway
greenhouse* limit only -- a thin, water-vapour-rich atmosphere, the nearest
of their limits to the fixed Earth-like atmosphere a solvent band assumes --
and turns it into a factor on the flux a planet absorbs:

    f(Teff) = S_eff(T_sun) / S_eff(Teff)

Normalised at this code's own solar temperature, so the Sun's factor is
exactly 1 and the Solar System is untouched.  Around Proxima (2980 K) f is
1.217: a planet there absorbs as if it received 22% more flux than it does.

The factor multiplies absorbed flux, never a solvent's temperatures, so every
band around one star moves by the same sqrt(f).  The coefficients were fitted
for water-vapour atmospheres; applying them to a methane or a sulfur band
assumes the same scattering and absorption behaviour, which is the caveat.
"""

from __future__ import annotations

from typing import Optional

from .units import T_SUN_K

# Kopparapu et al. 2013, ApJ 765, 131, Table 3, "Runaway Greenhouse" column,
# as printed in arXiv:1301.6674v2 (the version accepted to ApJ).
KOPPARAPU_2013_RUNAWAY = (1.0512, 1.3242e-4, 1.5418e-8, -7.9895e-12, -1.8328e-15)

# The fit's reference temperature, which is Kopparapu's, not T_SUN_K.
KOPPARAPU_T_REF_K = 5780.0

# Where the fit is valid.  Outside it the quartic is extrapolation, and a
# quartic extrapolated turns over fast, so a star outside is clamped to the
# nearer end rather than run through it.
TEFF_RANGE_K = (2600.0, 7200.0)


def clamp_teff_k(teff_k: float) -> float:
    """Teff moved into the fit's valid range."""
    lo, hi = TEFF_RANGE_K
    return min(max(teff_k, lo), hi)


def seff_runaway(teff_k: float) -> float:
    """Runaway-greenhouse effective flux, S_earth units, at this Teff."""
    s0, a, b, c, d = KOPPARAPU_2013_RUNAWAY
    t = clamp_teff_k(teff_k) - KOPPARAPU_T_REF_K
    return s0 + a * t + b * t ** 2 + c * t ** 3 + d * t ** 4


def colour_factor(teff_k: Optional[float]) -> float:
    """Factor on absorbed flux for a star of this Teff; 1.0 for the Sun.

    An unknown temperature gets 1.0 -- no correction rather than a guessed
    one -- and the band's description says so.
    """
    if not teff_k or teff_k <= 0:
        return 1.0
    return seff_runaway(T_SUN_K) / seff_runaway(teff_k)


def is_clamped(teff_k: Optional[float]) -> bool:
    """Whether this Teff sits outside the range the fit was made over."""
    return bool(teff_k) and clamp_teff_k(teff_k) != teff_k
