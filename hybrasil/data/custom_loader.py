# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Load user-defined star systems from YAML or JSON files."""

import json
from pathlib import Path
from ..models.elements import KeplerianElements
from ..models.body import OrbitalBody
from ..models.system import StarSystem
from ..mechanics.units import derive_period_days

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


def _optional_float(value) -> float | None:
    """A number from the file, or None.

    PyYAML follows YAML 1.1, which reads `1.989e30` -- no sign on the
    exponent -- as a string, so the schema's own example mass arrived as text
    and broke the first comparison that touched it.
    """
    return None if value is None else float(value)


def _parse_elements(data: dict, body_name: str, parent_body: OrbitalBody | None) -> KeplerianElements:
    required = [
        "semi_major_axis", "eccentricity", "inclination",
        "longitude_of_ascending_node", "argument_of_periapsis",
        "mean_anomaly_at_epoch", "epoch",
    ]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Body '{body_name}' orbital_elements missing fields: {missing}")

    # Derive period if not given
    if "period" in data:
        period = float(data["period"])
    elif parent_body is not None and parent_body.mass_kg is not None:
        period = derive_period_days(float(data["semi_major_axis"]), parent_body.mass_kg)
    else:
        raise ValueError(
            f"Body '{body_name}' needs either 'period' (days) in orbital_elements "
            f"or a parent body with 'mass_kg' to derive it."
        )

    return KeplerianElements(
        semi_major_axis=float(data["semi_major_axis"]),
        eccentricity=float(data["eccentricity"]),
        inclination=float(data["inclination"]),
        longitude_of_ascending_node=float(data["longitude_of_ascending_node"]),
        argument_of_periapsis=float(data["argument_of_periapsis"]),
        mean_anomaly_at_epoch=float(data["mean_anomaly_at_epoch"]),
        epoch=float(data["epoch"]),
        period=period,
    )


def load_custom_system(file_path: str) -> StarSystem:
    """Load a StarSystem from a YAML or JSON file.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the file content is invalid.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"System file not found: {file_path}")

    suffix = path.suffix.lower()
    with open(path, "r", encoding="utf-8") as f:
        if suffix in (".yaml", ".yml"):
            if not _YAML_AVAILABLE:
                raise ImportError("PyYAML is required for YAML files: pip install pyyaml")
            data = yaml.safe_load(f)
        elif suffix == ".json":
            data = json.load(f)
        else:
            raise ValueError(f"Unsupported file format '{suffix}'. Use .yaml or .json.")

    name = data.get("name", path.stem)
    description = data.get("description", "")
    reference_frame = data.get("reference_frame", "heliocentric")
    distance_unit = data.get("distance_unit", "AU")

    raw_bodies = data.get("bodies", [])
    if not raw_bodies:
        raise ValueError("System file must contain at least one body under 'bodies'.")

    # Index bodies by name for parent lookups
    bodies_by_name: dict[str, OrbitalBody] = {}
    bodies: list[OrbitalBody] = []

    for bd in raw_bodies:
        bname = bd.get("name")
        if not bname:
            raise ValueError("Each body must have a 'name' field.")

        body_type = bd.get("body_type", "custom")
        parent_name = bd.get("parent")
        parent_body = bodies_by_name.get(parent_name) if parent_name else None

        elements = None
        if "orbital_elements" in bd:
            elements = _parse_elements(bd["orbital_elements"], bname, parent_body)

        body = OrbitalBody(
            name=bname,
            body_type=body_type,
            elements=elements,
            parent=parent_name,
            radius_km=_optional_float(bd.get("radius_km")),
            mass_kg=_optional_float(bd.get("mass_kg")),
            color=bd.get("color"),
            display_name=bd.get("display_name"),
            status=bd.get("status", "confirmed"),
        )
        bodies.append(body)
        bodies_by_name[bname] = body

    return StarSystem(
        name=name,
        description=description,
        bodies=bodies,
        reference_frame=reference_frame,
        distance_unit=distance_unit,
        source="custom",
    )
