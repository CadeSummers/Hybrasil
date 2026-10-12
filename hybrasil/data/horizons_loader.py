# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Load orbital elements from NASA JPL Horizons via astroquery."""

from ..models.elements import KeplerianElements
from ..models.body import OrbitalBody
from ..models.system import StarSystem
from ..mechanics.units import jd_now

# NAIF IDs for Solar System planets
_SOLAR_BODY_IDS = {
    "Mercury": 199,
    "Venus": 299,
    "Earth": 399,
    "Mars": 499,
    "Jupiter": 599,
    "Saturn": 699,
    "Uranus": 799,
    "Neptune": 899,
    "Pluto": 999,
}

_BODY_COLORS = {
    "Mercury": "#B5B5B5",
    "Venus": "#E8D5A3",
    "Earth": "#4488FF",
    "Mars": "#CC4422",
    "Jupiter": "#C88B3A",
    "Saturn": "#E8D080",
    "Uranus": "#88DDEE",
    "Neptune": "#4466EE",
    "Pluto": "#BB9977",
}

_BODY_RADII = {
    "Mercury": 2439.7,
    "Venus": 6051.8,
    "Earth": 6371.0,
    "Mars": 3389.5,
    "Jupiter": 69911.0,
    "Saturn": 58232.0,
    "Uranus": 25362.0,
    "Neptune": 24622.0,
    "Pluto": 1188.3,
}


def _check_imports():
    try:
        from astroquery.jplhorizons import Horizons
        import astropy
    except ImportError:
        raise ImportError(
            "astroquery and astropy are required for Horizons data.\n"
            "Install them with: pip install astroquery astropy"
        )


def load_horizons_solar_system(
    epoch_jd: float | None = None,
    body_names: list[str] | None = None,
) -> StarSystem:
    """Fetch current osculating elements from NASA JPL Horizons.

    Args:
        epoch_jd: Julian Date for the element query. Defaults to now.
        body_names: Subset of planet names to include. Defaults to all 8 planets.
    """
    _check_imports()
    from astroquery.jplhorizons import Horizons

    if epoch_jd is None:
        epoch_jd = jd_now()
    if body_names is None:
        body_names = list(_SOLAR_BODY_IDS.keys())[:8]  # exclude Pluto by default

    bodies: list[OrbitalBody] = [
        OrbitalBody(name="Sun", body_type="star", radius_km=695700.0,
                    mass_kg=1.989e30, color="#FFF7AA"),
    ]

    for name in body_names:
        naif_id = _SOLAR_BODY_IDS.get(name)
        if naif_id is None:
            raise ValueError(f"Unknown body '{name}'. Known bodies: {list(_SOLAR_BODY_IDS)}")

        obj = Horizons(id=naif_id, location="@sun", epochs=epoch_jd)
        el = obj.elements()

        elements = KeplerianElements(
            semi_major_axis=float(el["a"][0]),
            eccentricity=float(el["e"][0]),
            inclination=float(el["incl"][0]),
            longitude_of_ascending_node=float(el["Omega"][0]),
            argument_of_periapsis=float(el["w"][0]),
            mean_anomaly_at_epoch=float(el["M"][0]),
            epoch=float(el["datetime_jd"][0]),
            period=float(el["P"][0]),
        )

        body = OrbitalBody(
            name=name,
            body_type="planet",
            parent="Sun",
            elements=elements,
            radius_km=_BODY_RADII.get(name),
            color=_BODY_COLORS.get(name),
        )
        bodies.append(body)

    return StarSystem(
        name="Solar System (Horizons)",
        description=f"Solar System with live osculating elements from NASA JPL Horizons at JD {epoch_jd:.1f}.",
        bodies=bodies,
        source="horizons",
    )
