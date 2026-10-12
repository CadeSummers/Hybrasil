# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Multiple Star Catalog rows the Planetless 4+ Stars tab was built from (data/four_plus_stars/msc.json).

Each component row carries SIMBAD's own name for the star ('SimbadName'), which is how a Planetless row with no Gaia
DR3 id is found in SIMBAD.
"""
import json

from common import ROOT

MSC_JSON = ROOT / "data" / "four_plus_stars" / "msc.json"


def components():
    """{(WDS code, MSC component letter): catalog row} for every system in msc.json."""
    d = json.loads(MSC_JSON.read_text(encoding="utf-8"))
    return {(wds, str(c.get("m_ID") or "").strip()): c for wds, s in d.items() for c in s.get("catalog", [])}


def simbad_names():
    return sorted({str(c["SimbadName"]).strip() for c in components().values() if c.get("SimbadName")})
