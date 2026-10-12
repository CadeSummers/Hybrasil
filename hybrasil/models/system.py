# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional
from .body import OrbitalBody


@dataclass
class BeltZone:
    """A visual annular band around the central body (e.g. asteroid belt).

    Rendered as a flat semi-transparent disk in the ecliptic plane.
    No orbital mechanics — purely decorative.
    """
    name: str
    r_inner_au: float
    r_outer_au: float
    color: str = "#997755"
    opacity: float = 0.12
    # A band drawn as several disjoint rings shows one legend entry: the first
    # ring carries it and the rest join it by legend group.
    show_in_legend: bool = True
    legend_group: str = ""
    # Whether the scene must be wide enough to show this band.  False for
    # decorative belts, so filtering down to two inner planets does not zoom
    # out to the Kuiper belt.  True for a derived band such as a solvent band,
    # which has no other representation and would otherwise be clipped away
    # entirely in a system whose only planets are close in.
    extends_scene: bool = False
    # Unit normal of the plane the annulus lies in.  (0, 0, 1) is the
    # reference plane, which is where every decorative belt sits; a solvent
    # band takes the plane its system's bodies actually orbit in.
    normal: tuple[float, float, float] = (0.0, 0.0, 1.0)
    # Displacement from the centre along `normal`, in AU.  0.0 for a belt and
    # for a lone solvent band.  A stack of solvent bands whose radii overlap
    # gives each band its own tiny offset, since coplanar transparent meshes
    # z-fight.
    offset_au: float = 0.0
    # Whether this zone is a derived solvent band rather than a belt that was
    # observed.  The viewer starts these hidden and switches the whole set on
    # and off from one button, so the figure opens on the orbits alone; a belt
    # is part of the system and is always drawn.
    is_solvent_band: bool = False
    # Everything the viewer needs to recompute this ring itself as its
    # pressure and albedo sliders move: which solvent it is, how bright the
    # star is, and whether the functional ceiling is being applied.  The ring
    # is recomputed in the browser rather than re-fetched, so each band trace
    # has to carry its own inputs.
    solvent_key: str = ""
    luminosity_sun: Optional[float] = None
    apply_ceiling: bool = True
    # Factor on the flux a planet absorbs, from the star's colour (see
    # `mechanics.stellar_colour`).  1.0 for the Sun, for a star with no known
    # temperature, and whenever the correction is switched off.
    colour_factor: float = 1.0
    # The star this band rings, by name.  Empty means the origin, which is
    # every belt and every band of a system's primary.
    #
    # A *name* rather than a position, because a star that is itself in orbit
    # -- Alpha Centauri B at 23 AU, Proxima at 8,700 AU -- does not have one
    # until a time is chosen, and the data layer has no time.  The figure
    # builders already hold every body's position at `t_start` and resolve it
    # there, which is the convention a moon's ellipse already uses.  Without
    # this a band belonging to a companion is drawn around the primary, at
    # radii measured from a star it does not belong to.
    centre_body: str = ""
    # The star's name as it appears in this band's legend entry, empty where
    # the figure has only one band-bearing star and there is nothing to tell
    # apart.  Distinct from `centre_body`, which is set whenever a band rings
    # a named star whether or not the legend has to say so.
    star_label: str = ""
    # Radius the scene must be wide enough for, when that is *not* the radius
    # being drawn.  A solvent band is recomputed live as the viewer's albedo
    # slider moves, and a darker albedo pushes it outward; the scene is sized
    # for the darkest the slider allows, so dragging can never grow a band out
    # of the box.  None means the drawn outer radius is the claim, which is
    # true of every belt and of any band that cannot change.
    scene_extent_au: Optional[float] = None

    @property
    def scene_claim_au(self) -> float:
        """Outer radius for the purpose of sizing the scene."""
        return self.r_outer_au if self.scene_extent_au is None else self.scene_extent_au


@dataclass
class StarSystem:
    """A collection of orbital bodies that form a star system."""
    name: str
    description: str
    bodies: list[OrbitalBody]
    reference_frame: Literal["heliocentric", "barycentric"] = "heliocentric"
    distance_unit: Literal["AU", "km"] = "AU"
    source: str = "unknown"
    belt_zones: list[BeltZone] = field(default_factory=list)
    distance_from_sun_ly: Optional[float] = None
    # Both reference arrows are unit vectors *in this system's own frame*. A
    # system whose angles come from astrometry or transits is quoted against
    # the plane of the sky, not the ecliptic, so an ecliptic vector points
    # somewhere its own orbits do not agree with. None on the galactic-centre
    # direction falls back to the ecliptic constant in `viz.static_plot`,
    # which is right for the Solar System and for any system drawn flat with
    # no frame of its own.
    solar_system_direction: Optional[tuple[float, float, float]] = None
    galactic_center_direction: Optional[tuple[float, float, float]] = None
    distance_to_galactic_center_ly: Optional[float] = None
    # The (RA, Dec) of the star whose plane of the sky is this system's frame,
    # for a system quoted that way; None means the ecliptic frame.  The
    # background sky is rotated by it (orientation.galactic_to_frame), which
    # is what puts the galactic centre in the picture where the arrow points.
    sky_frame_radec: Optional[tuple[float, float]] = None
    # True for a system that sits at the galactic centre itself (Sgr A*): its
    # galactic-centre arrow would have no length and no direction, so none is
    # drawn.  The Solar System arrow still is.
    at_galactic_center: bool = False

    def get_body(self, name: str) -> OrbitalBody:
        for body in self.bodies:
            if body.name == name:
                return body
        raise KeyError(f"Body '{name}' not found in system '{self.name}'")

    def get_stars(self) -> list[OrbitalBody]:
        return [b for b in self.bodies if b.body_type == "star"]

    def get_planets(self) -> list[OrbitalBody]:
        return [b for b in self.bodies if b.body_type == "planet"]

    def get_moons_of(self, planet_name: str) -> list[OrbitalBody]:
        return [b for b in self.bodies if b.body_type == "moon" and b.parent == planet_name]

    def filter_bodies(self, names: list[str]) -> StarSystem:
        """Return a new StarSystem containing only the named bodies (plus stars)."""
        star_names = {s.name for s in self.get_stars()}
        keep = set(names) | star_names
        return StarSystem(
            name=self.name,
            description=self.description,
            bodies=[b for b in self.bodies if b.name in keep],
            reference_frame=self.reference_frame,
            distance_unit=self.distance_unit,
            source=self.source,
            belt_zones=self.belt_zones,
        )
