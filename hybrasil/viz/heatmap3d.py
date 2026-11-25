# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The "Enable 3D Heatmap" switch of the three.js viewer's Even more features menu.

A solvent band is the flat slice, through its star's orbital plane, of a region
that is really three-dimensional: the solvent is liquid between two closed
surfaces round the star -- spheres for a lone star, bulged toward a companion
where one is close enough to add its light (`mechanics/combined_flux.py`).  The
switch draws those two surfaces in place of the slice.

Nothing is built here but the menu entry.  The shells are the viewer's
(`_shellMesh` in `band_kit.js`), made from the same band meshes with the same
solver as the flat outline, so the switch adds no trace and cannot shift a
trace index.  It travels on ``layout.meta`` like the photosynthesis rings and
the reference orbits; the Plotly viewer has no such menu and stays flat.
"""
from __future__ import annotations

from ..models.system import StarSystem

SET_KEY = "heatmap3d"
LABEL = "Enable 3D Heatmap"


def attach(fig, system: StarSystem) -> None:
    """Offer the switch on any figure that has a solvent band to draw."""
    if not any(z.is_solvent_band for z in system.belt_zones):
        return
    meta = dict(fig.layout.meta) if isinstance(fig.layout.meta, dict) else {}
    sets = list(meta.get("optional_sets") or [])
    sets.append({
        "key": SET_KEY, "label": LABEL, "default": False, "menu": "features",
        "title": "Draw each solvent band as the two closed surfaces the solvent "
                 "is liquid between, instead of the flat slice through them",
    })
    meta["optional_sets"] = sets
    fig.update_layout(meta=meta)
