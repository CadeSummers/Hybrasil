# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Orbital bands in which a solvent can be liquid.

Pure math, like the rest of `mechanics`.  Given a star's luminosity and a
solvent's melting and boiling points at some pressure, this returns the
annulus of orbital distances whose blackbody equilibrium temperature keeps
that solvent liquid.  The band therefore differs from star to star: it scales
as sqrt(L), so TRAPPIST-1's water band sits around 0.013-0.020 AU while the
Sun's sits around 0.56-0.87 AU.

Equilibrium temperature at distance d, for a body of Bond albedo A:

    T_eq = T_1AU * (L/L_sun)^(1/4) * (1 - A)^(1/4) / sqrt(d_AU)

inverted for distance:

    d_AU = T_1AU^2 * sqrt(L/L_sun) * sqrt(1 - A) / T^2

Albedo is unknown for an arbitrary planet, so the band is bracketed by two
albedos rather than assumed at one.  That yields two nested bands, defined
here exactly as the catalog workbook's "Orbital Bands" tab defines them:

    conservative  liquid at *every* albedo in the range.  Inner edge from the
                  boiling point at the low albedo, outer edge from the melting
                  point at the high albedo.
    optimistic    liquid at *some* albedo in the range.  The reverse pairing,
                  so it always encloses the conservative band.

The intersection can invert when the liquid window is narrower than the spread
the albedo bracket introduces; that is an empty conservative band, not an
error, and `SolventBand.conservative` is None for it.  Two of the workbook's
cells do this: ammonia at 0.1 bar and carbon dioxide at 10 bar.

Eight solvents are defined, the workbook's full set.  A pressure at which a
solvent has no liquid phase is absent from `phase_points` and carries its
reason in `absent`: below the triple point, above the critical point, or the
substance decomposes before it boils.  Nothing is interpolated between the
workbook's seven pressures, so only those seven produce a band.

Three solvents stop working as solvents *below* their boiling point, and carry
that limit as `functional_ceiling_c`: sulfur's 159 C lambda transition, above
which it polymerises into tar; formamide's ~180 C decomposition; sulfuric
acid's ~300 C SO3 loss.  The ceiling is applied by default, so what is drawn
is the band where the substance is a usable liquid rather than merely a
liquid.  Pass `apply_ceiling=False` for the thermodynamic band the workbook
prints outside its parentheses.

Greenhouse warming is a single flat offset, `greenhouse_k`, added to the
blackbody temperature: the surface is liquid where T_eq + offset sits between
the melting and boiling points, so each edge is the distance at which T_eq is
that point *minus* the offset.  Earth's is ~33 K; Venus's is several hundred.
It is a beta approximation -- a real greenhouse scales with the atmosphere and
the flux it traps, not by a constant -- and is what the viewer's third slider
moves.  An offset past a solvent's melting point leaves it liquid out to where
the cosmic microwave background rather than the star sets the temperature, so
the cold edge is drawn at the distance where T_eq falls to `T_CMB_K`.

The star's colour enters as a factor `colour` on the flux the planet
absorbs, from `stellar_colour` (Kopparapu et al. 2013's runaway-greenhouse
S_eff ratio): a red dwarf's light is scattered less and absorbed more, so the
same flux keeps a planet warmer.  It defaults to 1 here, the pure blackbody,
and `SolventChoice` switches it on per star.

Not accounted for: internal and tidal heating, day/night and seasonal swings,
and orbital eccentricity.  A first-order screen, not a habitability verdict.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from ..models.body import OrbitalBody
from ..models.system import BeltZone
from .orientation import (NEGLIGIBLE_TILT_DEG, Z_AXIS, band_plane,
                          plane_tilt_deg)
from .stellar_colour import TEFF_RANGE_K, colour_factor, is_clamped
from .units import T_EQ_1AU_K

# Bond albedo bracket.  0.0 is a perfect absorber, 0.3 is Earth-like.  These
# are the workbook's own inputs, and they set which edge comes from which
# albedo.
ALBEDO_LOW = 0.0
ALBEDO_HIGH = 0.3

# Below this ratio the two edges are the same line, and the annulus would
# render as a sliver rather than a band.
_MIN_SPAN_RATIO = 1.0005

CELSIUS_TO_KELVIN = 273.15

# The workbook's seven pressure columns.  A band exists only at these.
PRESSURES_BAR = (0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0)

# Reasons a pressure column is empty, as the workbook's n/a cells state them.
BELOW_TRIPLE_POINT = "below its triple point"
SUPERCRITICAL = "supercritical"
DECOMPOSES = "decomposes before boiling"


@dataclass(frozen=True)
class Solvent:
    """A candidate biosolvent and its liquid range across pressure.

    `phase_points` maps pressure in bar to (melting point, boiling point) in
    degrees Celsius.  A pressure absent from the mapping has no liquid phase
    for this solvent, and `absent` says why.

    `functional_ceiling_c` is a chemical or physical limit that bites below the
    boiling point: above it the substance is still liquid but no longer works
    as a solvent.  `ceiling_reason` names it for the description text.

    The colour lives here rather than in `viz.themes` for the same reason the
    asteroid and Kuiper belt colours live in `builtin_systems`: a BeltZone
    carries its own colour, and a solvent's band should look the same in every
    system it is drawn for.
    """
    key: str
    name: str
    formula: str
    color: str
    phase_points: dict[float, tuple[float, float]]
    functional_ceiling_c: Optional[float] = None
    ceiling_reason: str = ""
    absent: dict[float, str] = field(default_factory=dict)

    def liquid_range_k(self, pressure_bar: float,
                       apply_ceiling: bool = True) -> Optional[tuple[float, float]]:
        point = self.phase_points.get(pressure_bar)
        if point is None:
            return None
        t_melt, t_boil = point
        if apply_ceiling and self.functional_ceiling_c is not None:
            t_boil = min(t_boil, self.functional_ceiling_c)
        return (t_melt + CELSIUS_TO_KELVIN, t_boil + CELSIUS_TO_KELVIN)

    def is_capped_at(self, pressure_bar: float) -> bool:
        """Whether the functional ceiling actually bites at this pressure."""
        point = self.phase_points.get(pressure_bar)
        if point is None or self.functional_ceiling_c is None:
            return False
        return point[1] > self.functional_ceiling_c

    def absent_reason(self, pressure_bar: float) -> Optional[str]:
        """Why there is no band at this pressure, or None if there is one."""
        if pressure_bar in self.phase_points:
            return None
        return self.absent.get(pressure_bar, "no liquid phase")


# Melting and boiling points transcribed from the catalog workbook's
# "Liquid Range vs Pressure" tab, which is what drives its "Orbital Bands"
# figures.  Pressures are the workbook's seven: 0.1 / 0.5 / 1 / 5 / 10 / 50 /
# 100 bar.  The order of the definitions below is the workbook's row order.
METHANE = Solvent(
    key="methane",
    name="Methane",
    formula="CH4",
    color="#17A2A2",          # Titan's lakes: a cold teal
    phase_points={
        0.5:   (-182.5, -169.4),
        1.0:   (-182.5, -161.5),
        5.0:   (-181.0, -138.0),
        10.0:  (-181.0, -124.5),
    },
    absent={0.1: BELOW_TRIPLE_POINT, 50.0: SUPERCRITICAL, 100.0: SUPERCRITICAL},
)

ETHANE = Solvent(
    key="ethane",
    name="Ethane",
    formula="C2H6",
    color="#2E9E4F",
    phase_points={
        0.1:   (-182.8, -122.7),
        0.5:   (-182.8, -100.7),
        1.0:   (-182.8, -88.6),
        5.0:   (-182.0, -52.8),
        10.0:  (-182.0, -32.0),
    },
    absent={50.0: SUPERCRITICAL, 100.0: SUPERCRITICAL},
)

AMMONIA = Solvent(
    key="ammonia",
    name="Ammonia",
    formula="NH3",
    color="#7A4FD8",
    phase_points={
        0.1:   (-77.7, -72.9),
        0.5:   (-77.7, -47.3),
        1.0:   (-77.7, -33.3),
        5.0:   (-77.0,   4.4),
        10.0:  (-77.0,  25.2),
        50.0:  (-76.0,  88.7),
        100.0: (-75.0, 125.0),   # estimate, close to the 132.4 C critical point
    },
)

WATER = Solvent(
    key="water",
    name="Water",
    formula="H2O",
    color="#1E4FD8",          # deeper than the Kuiper belt's #446688
    phase_points={
        0.1:   (0.0,  45.8),
        0.5:   (0.0,  81.3),
        1.0:   (0.0,  99.6),
        5.0:   (0.0,  151.8),
        10.0:  (-0.1, 179.9),
        50.0:  (-0.4, 263.9),
        100.0: (-0.8, 311.0),
    },
)

FORMAMIDE = Solvent(
    key="formamide",
    name="Formamide",
    formula="HCONH2",
    color="#C43FB0",
    phase_points={
        0.1:   (2.0, 151.3),
        0.5:   (2.0, 191.4),
        1.0:   (2.0, 210.9),
    },
    functional_ceiling_c=180.0,
    ceiling_reason="decomposition from about 180 C",
    absent={5.0: DECOMPOSES, 10.0: DECOMPOSES, 50.0: DECOMPOSES, 100.0: DECOMPOSES},
)

SULFURIC_ACID = Solvent(
    key="sulfuric-acid",
    name="Sulfuric acid",
    formula="H2SO4",
    color="#C9701E",
    phase_points={
        0.1:   (10.0, 230.0),    # estimate: no verified vapour-pressure curve
        0.5:   (10.0, 290.0),    # estimate
        1.0:   (10.0, 337.0),
    },
    functional_ceiling_c=300.0,
    ceiling_reason="SO3 loss above about 300 C",
    absent={5.0: DECOMPOSES, 10.0: DECOMPOSES, 50.0: DECOMPOSES, 100.0: DECOMPOSES},
)

SULFUR = Solvent(
    key="sulfur",
    name="Sulfur",
    formula="S",
    color="#D9C523",
    phase_points={
        0.1:   (115.0, 324.0),
        0.5:   (115.0, 403.0),
        1.0:   (115.0, 445.0),
        5.0:   (115.0, 561.0),
        10.0:  (115.0, 624.0),
        50.0:  (115.0, 815.0),
        100.0: (115.0, 925.0),
    },
    functional_ceiling_c=159.0,
    ceiling_reason="the 159 C lambda transition, above which viscosity rises "
                   "about 10,000-fold",
)

CARBON_DIOXIDE = Solvent(
    key="carbon-dioxide",
    name="Carbon dioxide",
    formula="CO2",
    color="#8FA0B8",
    phase_points={
        10.0:  (-56.4, -40.1),
        50.0:  (-55.0,  14.3),
        100.0: (-53.4,  31.0),   # above P_crit the bound is T_crit, not a bp
    },
    absent={0.1: BELOW_TRIPLE_POINT, 0.5: BELOW_TRIPLE_POINT,
            1.0: BELOW_TRIPLE_POINT, 5.0: BELOW_TRIPLE_POINT},
)

SOLVENTS: dict[str, Solvent] = {
    s.key: s for s in (METHANE, ETHANE, AMMONIA, WATER, FORMAMIDE,
                       SULFURIC_ACID, SULFUR, CARBON_DIOXIDE)
}

# Spellings a user is likely to type.  Formulae are included, since the
# workbook labels every row with one.
_ALIASES: dict[str, str] = {
    "ch4": "methane",
    "c2h6": "ethane",
    "nh3": "ammonia",
    "h2o": "water",
    "hconh2": "formamide",
    "h2so4": "sulfuric-acid",
    "sulphuric-acid": "sulfuric-acid",
    "sulfuric": "sulfuric-acid",
    "s": "sulfur",
    "sulphur": "sulfur",
    "liquid-sulfur": "sulfur",
    "co2": "carbon-dioxide",
    "carbon": "carbon-dioxide",
    "carbondioxide": "carbon-dioxide",
}

DEFAULT_PRESSURE_BAR = 1.0

# Each band in a stack is lifted off z = 0 by this fraction of its own outer
# radius, times its rank.  See `stack_offsets_au`.
_STACK_FRACTION = 0.005

# ...but never by more than this many inner radii's worth.  Every band the
# workbook defines spans well under this ratio; only a greenhouse offset near
# a melting point stretches one further, out to the CMB distance, and scaling
# the lift by *that* outer edge floats the ring hundreds of AU off the plane
# at the zoom where its inner edge is on screen.
_STACK_SPAN_CAP = 10.0


def resolve_solvents(spec: Optional[str]) -> list[Solvent]:
    """Parse a CLI spec -- "water", "all", "water,ammonia,co2" -- into solvents.

    Names are matched case-insensitively, with spaces and underscores read as
    hyphens, so "Sulfuric Acid" and "sulfuric_acid" both land.  The result is
    in workbook order whatever order was asked for, so a stack of bands is
    always built the same way.
    """
    if spec is None or not spec.strip():
        return [WATER]
    wanted: list[str] = []
    for raw in spec.split(","):
        token = raw.strip().lower().replace(" ", "-").replace("_", "-")
        if not token:
            continue
        if token == "all":
            return list(SOLVENTS.values())
        key = _ALIASES.get(token, token)
        if key not in SOLVENTS:
            raise ValueError(
                f"Unknown solvent '{raw.strip()}'. Choose from: "
                + ", ".join(SOLVENTS) + ", or 'all'."
            )
        if key not in wanted:
            wanted.append(key)
    if not wanted:
        return [WATER]
    return [s for s in SOLVENTS.values() if s.key in wanted]


@dataclass(frozen=True)
class SolventBand:
    """Where one solvent is liquid around one star, in AU.

    `optimistic` always encloses `conservative`.  `conservative` is None when
    the intersection inverts.  `capped` records that the functional ceiling was
    applied, so the band is the usable one rather than the thermodynamic one.
    """
    solvent: str
    pressure_bar: float
    luminosity_sun: float
    optimistic: tuple[float, float]
    conservative: Optional[tuple[float, float]]
    capped: bool = False


def equilibrium_distance_au(temp_k: float, luminosity_sun: float,
                            albedo: float, colour: float = 1.0) -> float:
    """Distance at which a blackbody of this albedo sits at `temp_k`.

    `colour` multiplies the absorbed flux, (1 - A), so a star whose light a
    planet absorbs more readily pushes the distance out by sqrt(colour).
    """
    return ((T_EQ_1AU_K ** 2) * math.sqrt(luminosity_sun)
            * math.sqrt((1.0 - albedo) * colour) / (temp_k ** 2))


# Pressure bounds the viewer's slider runs between.  0.1 and 100 bar are the
# workbook's own first and last columns, so the whole slider is interpolation
# between transcribed points and never extrapolation past them.
MIN_PRESSURE_BAR = 0.1
MAX_PRESSURE_BAR = 100.0

# Albedo bounds the viewer's slider runs between.  Neither end is reachable in
# practice -- 0 is a perfect absorber and 1 a perfect mirror, which has no
# equilibrium temperature at all -- so the slider stops short of both.
MIN_ALBEDO = 0.01
MAX_ALBEDO = 0.99
DEFAULT_ALBEDO = 0.3

# Greenhouse offset bounds, in K, for the viewer's "greenhouse effect (beta)"
# slider.  The default is Earth's: a 288 K mean surface over a ~255 K blackbody
# at albedo 0.3.  This module's own constants put Earth's T_eq at 254.6 K, so
# 33 K lands its surface within half a degree of 288.  1000 K is past Venus.
MIN_GREENHOUSE_K = 0.0
MAX_GREENHOUSE_K = 1000.0
DEFAULT_GREENHOUSE_K = 33.0

# The coldest a body far from its star can get: the cosmic microwave
# background.  With a greenhouse offset at or above a solvent's melting point
# the solvent never freezes however far out, and the band's cold edge is drawn
# where starlight stops setting the temperature rather than at infinity.
T_CMB_K = 2.725

# Why a band is missing when the greenhouse offset, not the pressure, took it.
BOILS_EVERYWHERE = "above its boiling point at every distance"


def interpolated_liquid_range_k(
    solvent: Solvent, pressure_bar: float,
    apply_ceiling: bool = True) -> Optional[tuple[float, float]]:
    """Melting and boiling points in K at *any* pressure, interpolated.

    The workbook transcribes seven pressure columns.  A slider needs the
    values between them, and the two curves are interpolated in the form each
    one actually takes:

    - **Boiling point: 1/T linear in ln P.**  That is the Clausius-Clapeyron
      relation, ln P = -L/(R T) + c, which is what a vapour-pressure curve is.
      Interpolating T linearly instead puts water's 2 bar boiling point at
      122.1 C against a true 120.2; this form gives 120.4.
    - **Melting point: T linear in ln P.**  Melting is the Clapeyron equation,
      not Clausius-Clapeyron, and in any case these barely move -- water's
      falls 0.8 C across the full three decades and sulfur's does not move at
      all -- so the simple form is within a rounding error of any other.

    Returns None outside the solvent's own transcribed range, because that is
    the boundary between interpolating and inventing.  Methane is transcribed
    from 0.5 to 10 bar; below that it is under its triple point and above it
    heads for its critical point, and neither is something to extrapolate a
    straight line into.  `interpolation_absent_reason` says which side.
    """
    points = sorted(solvent.phase_points.items())
    if not points:
        return None
    lo_p, hi_p = points[0][0], points[-1][0]
    if pressure_bar < lo_p or pressure_bar > hi_p:
        return None

    # An exact hit on a transcribed column must return the transcribed value,
    # not a rounding of it: those cells are what the workbook tests pin.
    exact = solvent.phase_points.get(pressure_bar)
    if exact is not None:
        t_melt_c, t_boil_c = exact
    else:
        i = 0
        while points[i + 1][0] < pressure_bar:
            i += 1
        p0, (m0, b0) = points[i]
        p1, (m1, b1) = points[i + 1]
        f = (math.log(pressure_bar) - math.log(p0)) / (math.log(p1) - math.log(p0))
        t_melt_c = m0 + f * (m1 - m0)
        k0, k1 = b0 + CELSIUS_TO_KELVIN, b1 + CELSIUS_TO_KELVIN
        t_boil_c = 1.0 / ((1.0 / k0) + f * ((1.0 / k1) - (1.0 / k0))) - CELSIUS_TO_KELVIN

    if apply_ceiling and solvent.functional_ceiling_c is not None:
        t_boil_c = min(t_boil_c, solvent.functional_ceiling_c)
    return (t_melt_c + CELSIUS_TO_KELVIN, t_boil_c + CELSIUS_TO_KELVIN)


def interpolation_absent_reason(solvent: Solvent,
                                pressure_bar: float) -> Optional[str]:
    """Why this solvent has no band at this pressure, or None if it has one.

    Inside the transcribed range there is always a band.  Outside it, the
    reason is the workbook's own for the nearest column it left empty -- CO2
    below 5.185 bar is under its triple point, methane above 50 bar is
    supercritical -- falling back to a plain statement of the range.
    """
    if interpolated_liquid_range_k(solvent, pressure_bar) is not None:
        return None
    points = sorted(solvent.phase_points)
    if not points:
        return "no liquid phase at any pressure in the workbook"
    below = pressure_bar < points[0]
    stated = [r for p, r in sorted(solvent.absent.items())
              if (p < points[0]) == below and (p < points[0] or p > points[-1])]
    if stated:
        return stated[-1] if below else stated[0]
    edge = points[0] if below else points[-1]
    return f"{'below' if below else 'above'} its transcribed range ({edge:g} bar)"


def solvent_band_at_albedo(luminosity_sun: Optional[float],
                           solvent: Solvent = WATER,
                           pressure_bar: float = DEFAULT_PRESSURE_BAR,
                           albedo: float = DEFAULT_ALBEDO,
                           apply_ceiling: bool = True,
                           greenhouse_k: float = 0.0,
                           colour: float = 1.0
                           ) -> Optional[tuple[float, float]]:
    """The liquid band for one solvent at one *known* albedo, in AU.

    One albedo gives one ring, inner edge from the boiling point and outer
    from the melting point.  The nested conservative/optimistic pair that
    `solvent_band_au` returns is what the same calculation gives when albedo is
    *unknown* and has to be bracketed instead; with the viewer's slider setting
    it, there is nothing left to bracket.

    `greenhouse_k` is added to the blackbody temperature, so each edge sits
    where T_eq is that point *minus* the offset, and the whole ring moves out.
    It defaults to 0, the pure blackbody band the workbook computes;
    `SolventChoice` is what starts a figure at Earth's.  An offset that puts
    the boiling point at or below `T_CMB_K` leaves no band; one past the
    melting point pins the cold edge at `T_CMB_K` rather than at infinity.

    `colour` is the star-colour factor on absorbed flux, 1 for the Sun.  It
    scales both edges by sqrt(colour) and never decides whether there is a
    band -- that is the solvent's and the greenhouse's business alone.
    """
    if not luminosity_sun or luminosity_sun <= 0:
        return None
    liquid = interpolated_liquid_range_k(solvent, pressure_bar, apply_ceiling)
    if liquid is None:
        return None
    t_melt, t_boil = liquid
    if t_melt <= 0 or t_boil <= t_melt:
        return None
    t_hot = t_boil - greenhouse_k
    t_cold = max(t_melt - greenhouse_k, T_CMB_K)
    if t_hot <= t_cold:
        return None
    inner = equilibrium_distance_au(t_hot, luminosity_sun, albedo, colour)
    outer = equilibrium_distance_au(t_cold, luminosity_sun, albedo, colour)
    return (inner, outer) if outer > inner * _MIN_SPAN_RATIO else None


def band_absent_reason(solvent: Solvent, pressure_bar: float,
                       apply_ceiling: bool = True,
                       greenhouse_k: float = 0.0) -> Optional[str]:
    """Why a solvent has no band -- pressure first, then greenhouse -- or None.

    The luminosity plays no part: it scales where a band is, never whether.
    """
    reason = interpolation_absent_reason(solvent, pressure_bar)
    if reason is not None:
        return reason
    if solvent_band_at_albedo(1.0, solvent, pressure_bar, DEFAULT_ALBEDO,
                              apply_ceiling, greenhouse_k) is None:
        return BOILS_EVERYWHERE
    return None


def widest_band_outer_au(luminosity_sun: Optional[float],
                         solvent: Solvent,
                         pressure_bar: float,
                         apply_ceiling: bool = True,
                         greenhouse_k: float = 0.0,
                         colour: float = 1.0) -> float:
    """The band's outer edge at the darkest albedo the slider allows.

    The scene has to be wide enough for whatever the slider is dragged to, or
    a band would grow out of the box the moment albedo was lowered.  Only the
    albedo matters here: the outer edge comes from the melting point, which
    barely moves with pressure at all.

    The greenhouse offset is taken where its slider *starts*, not at its top.
    Past a solvent's melting point the cold edge runs out to the CMB distance
    -- ten thousand AU around the Sun -- and a scene sized for that at every
    start would shrink a star's planets to one pixel.  Dragging greenhouse up
    is therefore the one way to push a band past the edge of the scene, where
    the clipper cuts it at the box like anything else.
    """
    band = solvent_band_at_albedo(luminosity_sun, solvent, pressure_bar,
                                  MIN_ALBEDO, apply_ceiling, greenhouse_k,
                                  colour)
    return band[1] if band else 0.0


def solvent_band_au(luminosity_sun: Optional[float],
                    solvent: Solvent = WATER,
                    pressure_bar: float = DEFAULT_PRESSURE_BAR,
                    albedo_low: float = ALBEDO_LOW,
                    albedo_high: float = ALBEDO_HIGH,
                    apply_ceiling: bool = True) -> Optional[SolventBand]:
    """The liquid band for one solvent around a star of this luminosity.

    Returns None when the luminosity is unknown or the solvent has no liquid
    phase at this pressure.
    """
    if not luminosity_sun or luminosity_sun <= 0:
        return None
    liquid = solvent.liquid_range_k(pressure_bar, apply_ceiling)
    if liquid is None:
        return None
    t_melt, t_boil = liquid
    if t_melt <= 0 or t_boil <= t_melt:
        return None

    # The hot edge comes from the boiling point, the cold edge from the melting
    # point.  A darker body is hotter at the same distance, so a lower albedo
    # pushes both edges outward.
    opt_inner = equilibrium_distance_au(t_boil, luminosity_sun, albedo_high)
    opt_outer = equilibrium_distance_au(t_melt, luminosity_sun, albedo_low)
    cons_inner = equilibrium_distance_au(t_boil, luminosity_sun, albedo_low)
    cons_outer = equilibrium_distance_au(t_melt, luminosity_sun, albedo_high)

    conservative = (cons_inner, cons_outer) if cons_outer > cons_inner else None
    return SolventBand(
        solvent=solvent.name,
        pressure_bar=pressure_bar,
        luminosity_sun=luminosity_sun,
        optimistic=(opt_inner, opt_outer),
        conservative=conservative,
        capped=apply_ceiling and solvent.is_capped_at(pressure_bar),
    )


def _pressure_label(pressure_bar: float) -> str:
    return f"{pressure_bar:g} bar"


def _band_qualifier(band: SolventBand) -> str:
    """What goes in the parentheses of a band's trace name."""
    return _pressure_label(band.pressure_bar) + (", functional" if band.capped else "")


def solvent_belt_zones(luminosity_sun: Optional[float],
                       solvent: Solvent = WATER,
                       pressure_bar: float = DEFAULT_PRESSURE_BAR,
                       apply_ceiling: bool = True,
                       offset_au: float = 0.0,
                       normal: tuple[float, float, float] = Z_AXIS) -> list[BeltZone]:
    """Renderable annuli for one solvent band: a core plus its albedo margins.

    The optimistic band is drawn as the two rings lying *outside* the
    conservative core rather than as one annulus spanning it.  Two coplanar
    transparent meshes at z = 0 would z-fight; disjoint rings cannot.  The two
    margin rings share a legend entry, so the reader still sees one band.

    `offset_au` lifts the whole band off the plane along `normal`, which is how
    two *different* solvents whose bands overlap are kept from z-fighting with
    each other.  `normal` is the plane the band lies in: the reference plane
    unless the system's bodies orbit in another one.
    """
    band = solvent_band_au(luminosity_sun, solvent, pressure_bar,
                           apply_ceiling=apply_ceiling)
    if band is None:
        return []

    qualifier = _band_qualifier(band)
    opt_inner, opt_outer = band.optimistic

    if band.conservative is None:
        return [BeltZone(f"{solvent.name} band ({qualifier}, optimistic)",
                         r_inner_au=opt_inner, r_outer_au=opt_outer,
                         color=solvent.color, opacity=0.09,
                         extends_scene=True, offset_au=offset_au,
                         normal=normal, is_solvent_band=True)]

    cons_inner, cons_outer = band.conservative
    margin_name = f"{solvent.name} band ({qualifier}, albedo margin)"
    group = f"solvent-{solvent.key}-{pressure_bar:g}"

    zones: list[BeltZone] = []
    shown = False
    for r_in, r_out in ((opt_inner, cons_inner), (cons_outer, opt_outer)):
        if r_out <= r_in * _MIN_SPAN_RATIO:
            continue
        zones.append(BeltZone(margin_name, r_inner_au=r_in, r_outer_au=r_out,
                              color=solvent.color, opacity=0.09,
                              show_in_legend=not shown, legend_group=group,
                              extends_scene=True, offset_au=offset_au,
                              normal=normal, is_solvent_band=True))
        shown = True

    zones.append(BeltZone(f"{solvent.name} band ({qualifier})",
                          r_inner_au=cons_inner, r_outer_au=cons_outer,
                          color=solvent.color, opacity=0.18,
                          extends_scene=True, offset_au=offset_au,
                          normal=normal, is_solvent_band=True))
    return zones


def stack_offsets_au(bands: Sequence[SolventBand]) -> list[float]:
    """A distinct z for each band, so overlapping bands cannot z-fight.

    Bands sorted by outer radius take rank 0, 1, 2 ... and a lift of that rank
    times a small fraction of their own outer radius.  Scaling by the band's
    own size is what keeps the lift invisible at the zoom where that band is on
    screen: sulfur's 0.5 AU band rises by thousandths of an AU while methane's
    9.4 AU band rises by hundredths.  Ranking by radius makes the offsets
    strictly increasing, so no two bands ever land on the same plane.

    A lone band gets 0.0, so one solvent still draws flat on the ecliptic.
    """
    if len(bands) < 2:
        return [0.0] * len(bands)
    order = sorted(range(len(bands)), key=lambda i: bands[i].optimistic[1])
    offsets = [0.0] * len(bands)
    for rank, i in enumerate(order):
        offsets[i] = rank * _STACK_FRACTION * bands[i].optimistic[1]
    return offsets


def band_zone_name(solvent: Solvent, pressure_bar: float,
                   apply_ceiling: bool = True, star_label: str = "") -> str:
    """The legend name for one solvent's band at this pressure.

    The pressure is in the name because the slider moves it, and a legend
    entry that still said "1 bar" at 40 would be the figure lying about what
    it is showing.  The viewer rewrites this string as the slider moves, from
    the same rule -- so `_bandName` in `_ZOOM_JS` has to build the same string,
    star and all, or a drag would quietly strip the star back off.

    `star_label` names the star the band rings, and is only passed where a
    figure holds more than one band-bearing star.  A single-star system's
    legend is unchanged, which matters: the search box reads these names.
    """
    capped = (apply_ceiling and solvent.functional_ceiling_c is not None
              and _boiling_exceeds_ceiling(solvent, pressure_bar))
    star = f" — {star_label}" if star_label else ""
    return (f"{solvent.name} band{star} ({_pressure_label(pressure_bar)}"
            + (", functional" if capped else "") + ")")


def _boiling_exceeds_ceiling(solvent: Solvent, pressure_bar: float) -> bool:
    """Whether the functional ceiling actually bites at this pressure."""
    if solvent.functional_ceiling_c is None:
        return False
    raw = interpolated_liquid_range_k(solvent, pressure_bar, apply_ceiling=False)
    if raw is None:
        return False
    return raw[1] - CELSIUS_TO_KELVIN > solvent.functional_ceiling_c


def stack_offsets_for_outer(outer_au: Sequence[float],
                            inner_au: Optional[Sequence[float]] = None
                            ) -> list[float]:
    """The stacking lift for bands with these outer radii.  See `stack_offsets_au`.

    A band with no outer radius -- no liquid phase at this pressure -- takes no
    rank, so the solvents that *are* drawn keep consecutive ranks and the stack
    does not develop gaps as the pressure slider moves.

    With `inner_au`, the radius the lift scales by is capped at
    `_STACK_SPAN_CAP` inner radii, so a band a greenhouse offset has run out to
    the CMB distance stays on its plane.  `_stackOffsets` in the viewer does
    the same.
    """
    live = [i for i, r in enumerate(outer_au) if r > 0]
    if len(live) < 2:
        return [0.0] * len(outer_au)
    order = sorted(live, key=lambda i: outer_au[i])
    offsets = [0.0] * len(outer_au)
    for rank, i in enumerate(order):
        scale = outer_au[i]
        if inner_au is not None:
            scale = min(scale, _STACK_SPAN_CAP * inner_au[i])
        offsets[i] = rank * _STACK_FRACTION * scale
    return offsets


def solvent_zones(luminosity_sun: Optional[float],
                  solvents: Iterable[Solvent] = (WATER,),
                  pressure_bar: float = DEFAULT_PRESSURE_BAR,
                  apply_ceiling: bool = True,
                  normal: tuple[float, float, float] = Z_AXIS,
                  albedo: float = DEFAULT_ALBEDO,
                  centre_body: str = "",
                  star_label: str = "",
                  greenhouse_k: float = 0.0,
                  colour: float = 1.0) -> list[BeltZone]:
    """One renderable annulus per solvent asked for, at this albedo and offset.

    **Exactly one zone per solvent, always, in workbook order** -- including a
    solvent with no liquid phase at this pressure, which gets an empty one
    (`r_outer_au` 0).  The viewer recomputes these rings as its pressure,
    albedo and greenhouse sliders move, by rewriting each trace's geometry in place, so the
    set of traces has to be the same at every slider position: a band that
    appeared and disappeared would shift every trace index after it, and the
    animation writes marker traces by index.

    `extends_scene` is claimed from the band at the *darkest* albedo the slider
    allows, not from the one being drawn, so dragging albedo down can never
    grow a band out of the scene box.

    `centre_body` is the star these rings are around, and `star_label` puts it
    in the legend name.  One call is one star's stack, which is also what keeps
    the stacking offsets per-star: ranking across a whole figure would lift one
    star's bands by another star's radii.
    """
    # An unknown luminosity has no band at any pressure or albedo, so such a
    # system gets no band traces at all rather than a row of empty ones: there
    # is nothing for a slider to move.
    if not luminosity_sun or luminosity_sun <= 0:
        return []
    chosen = list(solvents)
    bands = [solvent_band_at_albedo(luminosity_sun, s, pressure_bar, albedo,
                                    apply_ceiling, greenhouse_k, colour)
             for s in chosen]
    offsets = stack_offsets_for_outer([b[1] if b else 0.0 for b in bands],
                                      [b[0] if b else 0.0 for b in bands])

    zones: list[BeltZone] = []
    for solvent, band, offset in zip(chosen, bands, offsets):
        inner, outer = band if band else (0.0, 0.0)
        zones.append(BeltZone(
            band_zone_name(solvent, pressure_bar, apply_ceiling, star_label),
            r_inner_au=inner, r_outer_au=outer,
            color=solvent.color, opacity=0.18,
            extends_scene=True, offset_au=offset, normal=normal,
            centre_body=centre_body, star_label=star_label,
            is_solvent_band=True,
            solvent_key=solvent.key,
            luminosity_sun=luminosity_sun,
            apply_ceiling=apply_ceiling,
            colour_factor=colour,
            scene_extent_au=widest_band_outer_au(luminosity_sun, solvent,
                                                 pressure_bar, apply_ceiling,
                                                 greenhouse_k, colour),
        ))
    return zones


def _span_text(band: SolventBand) -> str:
    opt_inner, opt_outer = band.optimistic
    if band.conservative is None:
        return f"{opt_inner:.3g}-{opt_outer:.3g} AU optimistic only"
    cons_inner, cons_outer = band.conservative
    return (f"{cons_inner:.3g}-{cons_outer:.3g} AU conservative, "
            f"{opt_inner:.3g}-{opt_outer:.3g} AU optimistic")


def colour_note(teff_k: Optional[float], applied: bool = True) -> str:
    """A sentence on the star-colour correction for one star's bands."""
    if not applied:
        return " No star-colour correction (switched off)."
    if not teff_k or teff_k <= 0:
        return (" No star-colour correction: the star's effective "
                "temperature is unknown.")
    f = colour_factor(teff_k)
    if abs(f - 1.0) < 5e-4:
        return ""
    clamped = ""
    if is_clamped(teff_k):
        end = TEFF_RANGE_K[0] if teff_k < TEFF_RANGE_K[0] else TEFF_RANGE_K[1]
        clamped = (f", taken at {end:g} K because {teff_k:g} K is outside the "
                   f"{TEFF_RANGE_K[0]:g}-{TEFF_RANGE_K[1]:g} K range the fit "
                   f"covers")
    return (f" Star colour: at {teff_k:g} K a planet absorbs as if it received "
            f"{f:.3f}x the flux (Kopparapu et al. 2013, runaway-greenhouse "
            f"limit{clamped}), which moves every band out by "
            f"{f ** 0.5:.3f}x.")


def _caveat(albedo: float, greenhouse_k: float = 0.0) -> str:
    greenhouse = (f"a flat {greenhouse_k:g} K greenhouse offset"
                  if greenhouse_k else "no greenhouse offset")
    return (f"It is a blackbody estimate at albedo {albedo:g} with "
            f"{greenhouse} and no tidal or internal heating, so it is not a "
            f"published habitable zone. Albedo, pressure and greenhouse "
            f"effect are all sliders in the viewer, and the bands move with "
            f"them.")


def plane_note(normal: tuple[float, float, float]) -> str:
    """A sentence naming the plane the band is drawn in, if it is not flat."""
    tilt = plane_tilt_deg(normal)
    if tilt < NEGLIGIBLE_TILT_DEG:
        return ""
    return (f" The band is drawn in the mean orbital plane of the system's "
            f"confirmed bodies, {tilt:.1f} degrees from the reference plane, "
            f"so it rings the star the way the planets do.")


def _ring_text(band: tuple[float, float]) -> str:
    return f"{band[0]:.3f}-{band[1]:.3f} AU"


def solvent_band_note(luminosity_sun: Optional[float],
                      solvent: Solvent = WATER,
                      pressure_bar: float = DEFAULT_PRESSURE_BAR,
                      apply_ceiling: bool = True,
                      albedo: float = DEFAULT_ALBEDO,
                      greenhouse_k: float = 0.0,
                      colour: float = 1.0) -> str:
    """One sentence describing the drawn band, for a system description."""
    band = solvent_band_at_albedo(luminosity_sun, solvent, pressure_bar,
                                  albedo, apply_ceiling, greenhouse_k, colour)
    if band is None:
        return ""
    capped = (f"Its outer temperature is capped by {solvent.ceiling_reason}. "
              if _boiling_exceeds_ceiling(solvent, pressure_bar) and apply_ceiling
              else "")
    return (f"The {solvent.name.lower()} band at "
            f"{_pressure_label(pressure_bar)} spans {_ring_text(band)}. "
            f"{capped}{_caveat(albedo, greenhouse_k)}")


def solvent_notes(luminosity_sun: Optional[float],
                  solvents: Iterable[Solvent] = (WATER,),
                  pressure_bar: float = DEFAULT_PRESSURE_BAR,
                  apply_ceiling: bool = True,
                  albedo: float = DEFAULT_ALBEDO,
                  greenhouse_k: float = 0.0,
                  colour: float = 1.0) -> str:
    """Description text for a stack of bands: one span each, one caveat.

    For a single solvent this is exactly `solvent_band_note`.  A solvent with
    no band at this pressure is named with its reason rather than silently
    dropped -- carbon dioxide missing from a 1 bar plot is a result, not an
    omission.
    """
    chosen = list(solvents)
    if len(chosen) == 1:
        return solvent_band_note(luminosity_sun, chosen[0], pressure_bar,
                                 apply_ceiling, albedo, greenhouse_k, colour)
    if not luminosity_sun or luminosity_sun <= 0:
        return ""

    pressure = _pressure_label(pressure_bar)
    spans, capped, missing = [], [], []
    for solvent in chosen:
        band = solvent_band_at_albedo(luminosity_sun, solvent, pressure_bar,
                                      albedo, apply_ceiling, greenhouse_k,
                                      colour)
        if band is None:
            reason = band_absent_reason(solvent, pressure_bar, apply_ceiling,
                                        greenhouse_k)
            missing.append(f"{solvent.name.lower()} ({reason})")
            continue
        spans.append(f"{solvent.name.lower()} {_ring_text(band)}")
        if apply_ceiling and _boiling_exceeds_ceiling(solvent, pressure_bar):
            capped.append(f"{solvent.name.lower()} by {solvent.ceiling_reason}")
    if not spans:
        return ""

    parts = [f"Solvent bands at {pressure}, albedo {albedo:g}: "
             + "; ".join(spans) + "."]
    if capped:
        parts.append("Outer temperature capped for " + "; ".join(capped) + ".")
    if missing:
        parts.append(f"No liquid phase at {pressure}: " + ", ".join(missing) + ".")
    parts.append(_caveat(albedo, greenhouse_k))
    return " ".join(parts)


@dataclass(frozen=True)
class SolventChoice:
    """Which bands a system should be built with.

    One argument that the data loaders can carry down to every star, rather
    than three that each of them has to thread separately.  The default is the
    water band at 1 bar, which is what every system was drawn with before the
    other seven solvents arrived.
    """
    solvents: tuple[Solvent, ...] = (WATER,)
    pressure_bar: float = DEFAULT_PRESSURE_BAR
    apply_ceiling: bool = True
    align_to_orbits: bool = True
    # Where the viewer's sliders start.  All are continuous, so these are
    # positions rather than choices from a list.
    albedo: float = DEFAULT_ALBEDO
    greenhouse_k: float = DEFAULT_GREENHOUSE_K
    # Whether each star's colour scales its bands (`stellar_colour`).  Off,
    # every star is treated as if it shone like the Sun.
    star_colour: bool = True

    @classmethod
    def parse(cls, spec: Optional[str] = None,
              pressure_bar: float = DEFAULT_PRESSURE_BAR,
              apply_ceiling: bool = True,
              align_to_orbits: bool = True,
              albedo: float = DEFAULT_ALBEDO,
              greenhouse_k: float = DEFAULT_GREENHOUSE_K,
              star_colour: bool = True) -> "SolventChoice":
        return cls(tuple(resolve_solvents(spec)), pressure_bar, apply_ceiling,
                   align_to_orbits, albedo, greenhouse_k, star_colour)

    def colour(self, teff_k: Optional[float]) -> float:
        """The star-colour factor for a star of this Teff, or 1 when off."""
        return colour_factor(teff_k) if self.star_colour else 1.0

    def plane(self, bodies: Iterable[OrbitalBody] = (),
              host: Optional[str] = None) -> tuple[float, float, float]:
        """The plane to draw the bands in, given the system's bodies.

        The reference plane when there is nothing to derive one from, which is
        also what `--band-plane reference` forces.
        """
        bodies = list(bodies)
        if not self.align_to_orbits or not bodies:
            return Z_AXIS
        return band_plane(bodies, host)

    def zones(self, luminosity_sun: Optional[float],
              bodies: Iterable[OrbitalBody] = (),
              host: Optional[str] = None,
              star_label: str = "",
              teff_k: Optional[float] = None) -> list[BeltZone]:
        """One stack of bands for one star.

        `host` is both the star whose planets set the plane and the star the
        rings are centred on, because those are the same star.  A figure with
        more than one band-bearing star calls this once per star and passes
        `star_label`, which puts the star in each legend entry.  `teff_k` is
        the star's effective temperature, which sets its colour factor.
        """
        return solvent_zones(luminosity_sun, self.solvents, self.pressure_bar,
                             self.apply_ceiling, self.plane(bodies, host),
                             self.albedo, centre_body=(host or ""),
                             star_label=star_label,
                             greenhouse_k=self.greenhouse_k,
                             colour=self.colour(teff_k))

    def luminous_stars(self,
                       bodies: Iterable[OrbitalBody] = ()) -> list[OrbitalBody]:
        """Every star in the system that a band can be computed for.

        A band is a statement about one star's luminosity, so a system with
        three luminous stars has three bands' worth of answer in it.  Order is
        the body order, so the primary's stack comes first and the legend reads
        the way the system is written.
        """
        return [b for b in bodies
                if b.body_type == "star" and b.luminosity_sun
                and b.luminosity_sun > 0]

    def zones_for_system(self,
                         bodies: Iterable[OrbitalBody] = ()) -> list[BeltZone]:
        """One band stack per luminous star, each in its own star's plane.

        This is what every data source should call.  `zones()` builds one
        star's stack; a figure almost always wants all of them, and calling it
        once for the primary is how Alpha Centauri came to draw a band for A
        while B and Proxima -- one of which has three planets of its own --
        got nothing.

        Each star's rings are centred on that star and lie in the plane of
        *its* planets, so two stars whose systems are inclined differently
        carry two stacks at two angles.  The star goes in each legend entry
        only where there is more than one stack to tell apart, which leaves a
        single-star system's legend exactly as it was.
        """
        stars = self.luminous_stars(bodies)
        bodies = list(bodies)
        label = len(stars) > 1
        zones: list[BeltZone] = []
        for star in stars:
            zones.extend(self.zones(star.luminosity_sun, bodies, star.name,
                                    star_label=star.name if label else "",
                                    teff_k=star.teff_k))
        return zones

    def note(self, luminosity_sun: Optional[float],
             bodies: Iterable[OrbitalBody] = (),
             host: Optional[str] = None,
             teff_k: Optional[float] = None) -> str:
        text = solvent_notes(luminosity_sun, self.solvents, self.pressure_bar,
                             self.apply_ceiling, self.albedo, self.greenhouse_k,
                             self.colour(teff_k))
        if not text:
            return text
        return (text + colour_note(teff_k, self.star_colour)
                + plane_note(self.plane(bodies, host)))

    @property
    def cache_key(self) -> tuple:
        """Hashable identity -- `solvents` holds dicts, so it is not one."""
        return (tuple(s.key for s in self.solvents), self.pressure_bar,
                self.apply_ceiling, self.align_to_orbits, self.albedo,
                self.greenhouse_k, self.star_colour)


DEFAULT_CHOICE = SolventChoice()
