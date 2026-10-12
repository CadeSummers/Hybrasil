# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unified dispatch for loading star systems from any source."""

from ..mechanics.solvent_bands import SolventChoice, DEFAULT_CHOICE
from ..models.system import StarSystem
from .builtin_systems import get_builtin_system, BUILTIN_NAMES


def get_system(
    source: str,
    identifier: str,
    bands: SolventChoice = DEFAULT_CHOICE,
    **kwargs,
) -> StarSystem:
    """Load a StarSystem from the specified source.

    Args:
        source: One of "builtin", "horizons", "file", or "catalog".
        identifier: System name (builtin/horizons/catalog) or file path (file).
        bands: Which solvent bands to draw. Built-in and catalog systems only;
            a file or Horizons system carries whatever its own source gives it.
        **kwargs: Passed through to the underlying loader. The catalog loader
            accepts spreadsheet_id, refresh, ttl_seconds and offline.

    Raises:
        ValueError: For unknown source or identifier.
        FileNotFoundError: If source="file" and the file does not exist.
        ImportError: If source="horizons" and astroquery/astropy are not installed,
            or source="catalog" and the Google API client is not installed.
    """
    source = source.lower().strip()

    if source == "builtin":
        return get_builtin_system(identifier, bands)

    elif source == "file":
        from .custom_loader import load_custom_system
        return load_custom_system(identifier)

    elif source == "horizons":
        from .horizons_loader import load_horizons_solar_system
        return load_horizons_solar_system(**kwargs)

    elif source in ("catalog", "sheet"):
        from .catalog_loader import load_catalog_system
        return load_catalog_system(identifier, bands=bands, **kwargs)

    else:
        raise ValueError(
            f"Unknown source '{source}'. Choose from: builtin, file, horizons, catalog."
        )
