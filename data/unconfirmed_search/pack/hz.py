# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Kopparapu HZ bounds exactly as the workbook computes them (recovered by fit)."""
import math
# (S_eff_sun, a, b, c, d): Kopparapu et al. 2013 erratum-corrected Table 3, 1 M_earth
COEF = {
    "recent_venus": (1.7763, 1.4335e-4, 3.3954e-9, -7.6364e-12, -1.1950e-15),
    "runaway":      (1.0385, 1.2456e-4, 1.4612e-8, -7.6345e-12, -1.7511e-15),
    "max_gh":       (0.3507, 5.9578e-5, 1.6707e-9, -3.0058e-12, -5.1925e-16),
    "early_mars":   (0.3207, 5.4471e-5, 1.5275e-9, -2.1709e-12, -3.8282e-16),
}
def seff(kind, teff):
    s, a, b, c, d = COEF[kind]; t = teff - 5780.0
    return s + a*t + b*t**2 + c*t**3 + d*t**4
def bounds(L, teff):
    return tuple(math.sqrt(L/seff(k, teff)) for k in ("recent_venus","runaway","max_gh","early_mars"))
