# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The light Earth's photosynthesisers need, as the workbook's Photosynthesis limits tab gives it.

Every number here is a cell of that tab (`TAB`), copied as literal rows the way
Castor's are (`builtin_systems._CASTOR_ROWS`), so drawing the rings needs no
Google credential.  `tests/test_photosynthesis.py` checks the rows against the
newest `data/hybrasil-*.xlsx` snapshot: change the sheet, then the rows.

Only organisms whose primary way of gaining energy is photosynthesis from
starlight are listed.  Life on geothermal light (the green sulfur bacterium
GSB1 at a deep-sea vent) and life for which light only supplements another
energy source (mixotrophs, photosynthetic symbioses) are left out on purpose.

Each organism has three levels, in PAR photon flux (400-700 nm,
umol photons m^-2 s^-1):

- ``optimal``  -- light saturation: more light no longer speeds it up;
- ``growth``   -- the compensation point, the least light that still gives net
  growth.  This is the level the viewer draws a ring at;
- ``survival`` -- the least light it has been found to persist under.

A level no source gives is None, never a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

TAB = "Photosynthesis limits"

LEVELS = ("optimal", "growth", "survival")
DRAWN_LEVEL = "growth"


@dataclass(frozen=True)
class Organism:
    """One row group of the tab: an organism and its three light levels."""
    name: str                      # "Sun-loving plants"
    examples: str                  # "Sunflower (Helianthus annuus), maize (Zea mays)"
    optimal: Optional[float]       # umol photons m^-2 s^-1, PAR
    growth: Optional[float]
    survival: Optional[float]

    def level(self, key: str) -> Optional[float]:
        return getattr(self, key)


# Earth's full-sun PAR at the surface, the 100% every fraction is taken of:
# "about 2000" (Taiz & Zeiger 2010, Plant Physiology 5th ed., ch. 9), the
# tab's REFERENCE VALUES block.
EARTH_FULL_SUN_PAR: float = 2000.0

# Ordered from the most light-hungry to the least, which is the order the
# rings run outward and the legend lists them.  The tab's Example species and
# Source columns name each value's organism and paper; the two flagged rows
# (sea-ice algae, deep coralline red algae) carry a published doubt that they
# live mainly on light, kept and noted there.
ORGANISMS: tuple[Organism, ...] = (
    Organism("Sun-loving crops", "Maize (Zea mays)", 1800, 31, None),
    Organism("C3 crops", "Rice (Oryza sativa)", 1000, 16.9, None),
    Organism("Shade-tolerant understory herbs", "Wood sorrel (Oxalis acetosella); cave flora", 92.5, 5.55, 0.35),
    Organism("Mosses", "39 mosses; 10 Hawaiian mosses; Amblystegium serpens", 583, 5.4, 4.29),
    Organism("Filmy ferns", "Trichomanes speciosum; Hymenoglossum cruentum", 30, 3.9, 0.1),
    Organism("Low-light cyanobacteria", "Prochlorococcus low-light strains", 13.9, 1.5, None),
    Organism("Kelp", "Laminaria hyperborea; L. solidungula", 20, 1, 0.285),
    Organism("Marine diatoms", "Thalassiosira pseudonana; Phaeodactylum tricornutum", 89.5, 1, None),
    Organism("Green sulfur bacteria", "Chlorobium phaeobacteroides BS1, Black Sea", 1, 0.25, 0.00075),
    Organism("Sea-ice algae", "Ice-algae community, NE Greenland; MOSAiC under-ice algae", 7, 0.17, 0.04),
    Organism("Deep crustose coralline red algae", "Crustose Corallinales", 4.2, None, 0.000158),
)


def par_fraction(par_umol: Optional[float]) -> Optional[float]:
    """A PAR photon flux as a fraction of Earth's full sun."""
    if par_umol is None or par_umol <= 0 or EARTH_FULL_SUN_PAR <= 0:
        return None
    return par_umol / EARTH_FULL_SUN_PAR


def drawn_limits() -> list[tuple[Organism, float]]:
    """(organism, fraction of Earth's PAR) for every organism with a growth limit."""
    out = []
    for o in ORGANISMS:
        f = par_fraction(o.level(DRAWN_LEVEL))
        if f is not None:
            out.append((o, f))
    return out
