# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""How far from a star its light falls to a given photosynthetic threshold.

Pure math, like the rest of `mechanics`.  A threshold is a photon flux of
photosynthetically active radiation (PAR, 400-700 nm), the quantity plant and
algal physiology measures, given here as a fraction `f` of Earth's full-sun
PAR at the surface.  Around the Sun that fraction is reached at

    d = 1 / sqrt(f)  AU,

and around any other star at

    d = sqrt(L * k(Teff) / f)  AU,

where L is the bolometric luminosity in L_sun and k is the star's PAR photon
yield: the PAR photons a blackbody at Teff emits per watt, over the same at
the Sun's temperature.  k is 1 for the Sun by construction.  A cool star puts
most of its energy into the infrared, so k < 1 for an M dwarf and its rings sit
closer in than sqrt(L) alone would put them (Proxima, 2980 K: k = 0.234, so
0.48 of the distance; TRAPPIST-1, 2516 K: k = 0.105, so 0.32).  k peaks at about 1.05 near 6800-7000 K and falls below 1
again past about 8200 K, where the excess goes into the ultraviolet.

Two caveats, both stated wherever the rings are drawn:

- A blackbody is a fair stand-in for an FGK star's visible spectrum and a poor
  one for an M dwarf's, whose molecular bands (TiO, VO) carve deep troughs out
  of the 400-700 nm window.  k is the blackbody figure, not a model atmosphere.
- The thresholds were measured beneath Earth's air and water, so a distance
  assumes the light reaching the organism is starlight thinned the same way.
  Nothing here models another planet's atmosphere.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Optional

from .units import T_SUN_K

# CODATA 2018, exact by definition of the SI.
_H = 6.62607015e-34       # J s
_C = 299792458.0          # m / s
_K_B = 1.380649e-23       # J / K
_SIGMA = 2 * math.pi ** 5 * _K_B ** 4 / (15 * _H ** 3 * _C ** 2)

# The PAR window, metres.
PAR_BAND_M = (400e-9, 700e-9)

# Simpson's rule over the window; 2000 intervals is converged to ~1e-12.
_INTERVALS = 2000


def _photon_radiance(wavelength_m: float, teff_k: float) -> float:
    """Planck photon spectral radiance, photons s^-1 m^-2 sr^-1 m^-1."""
    x = _H * _C / (wavelength_m * _K_B * teff_k)
    return 2 * _C / wavelength_m ** 4 / math.expm1(x)


@lru_cache(maxsize=4096)
def par_photons_per_watt(teff_k: float) -> float:
    """PAR photons a blackbody at Teff emits per joule of its total output."""
    lo, hi = PAR_BAND_M
    h = (hi - lo) / _INTERVALS
    s = _photon_radiance(lo, teff_k) + _photon_radiance(hi, teff_k)
    for i in range(1, _INTERVALS):
        s += (4 if i % 2 else 2) * _photon_radiance(lo + i * h, teff_k)
    photons = s * h / 3
    return photons / (_SIGMA * teff_k ** 4 / math.pi)


def par_photon_factor(teff_k: Optional[float]) -> float:
    """The star's PAR photon yield per watt over the Sun's; 1.0 for the Sun.

    An unknown temperature gets 1.0 -- no correction rather than a guessed
    one -- as `stellar_colour.colour_factor` does.
    """
    if not teff_k or teff_k <= 0:
        return 1.0
    return par_photons_per_watt(float(teff_k)) / par_photons_per_watt(T_SUN_K)


def photosynthesis_distance_au(luminosity_sun: float, par_fraction: float,
                               teff_k: Optional[float] = None) -> Optional[float]:
    """Distance at which the star's PAR photon flux is `par_fraction` of Earth's.

    None when there is no answer: no luminosity, or a non-positive fraction.
    """
    if not luminosity_sun or luminosity_sun <= 0 or not par_fraction or par_fraction <= 0:
        return None
    return math.sqrt(luminosity_sun * par_photon_factor(teff_k) / par_fraction)


def total_energy_distance_au(luminosity_sun: float, energy_fraction: float) -> Optional[float]:
    """The same distance by total energy alone, sqrt(L / f): no colour term.

    Recorded in the workbook beside the PAR figure; not what is drawn.
    """
    if not luminosity_sun or luminosity_sun <= 0 or not energy_fraction or energy_fraction <= 0:
        return None
    return math.sqrt(luminosity_sun / energy_fraction)
