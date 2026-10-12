# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared paths, tab layout and sheet access for the existence columns (data/existence/README.md).

The sheet helpers are the Known-tab motion pipeline's (data/known_within_100ly/kinematics/common.py): its 429 retry,
its name + Gaia id row key, its renamed-row map.  Nothing here writes to the sheet -- write.py is the only writer.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KIN = ROOT / "data" / "known_within_100ly" / "kinematics"
sys.path.insert(0, str(ROOT))

# kinematics/common.py, loaded under its own name: this file is 'common' too.
_spec = importlib.util.spec_from_file_location("kinematics_common", KIN / "common.py")
kin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kin)
blank, letter, load, now, num, q, row_key, save, sheets = (kin.blank, kin.letter, kin.load, kin.now, kin.num, kin.q,
                                                           kin.row_key, kin.save, kin.sheets)

CAT = HERE / "cat"
LIVE = HERE / "live.json"                 # what fetch.py read; not committed (it is the sheet)
PLAN = HERE / "plan.json"
WRITE_LOG = HERE / "write_log.json"
CNS5_DAT = CAT / "cns5.dat"
CNS5_URL = "https://cdsarc.cds.unistra.fr/ftp/J/A+A/670/A19/cns5.dat"
SIMBAD_IDS = CAT / "simbad_ids.json"
SOURCE_LIST = ROOT / "data" / "Nearby stars within 100 light years.xlsx"

SP = "Sources & Provenance"
H_NAME, H_SID, H_KS = "System / Host", "Gaia DR3 source_id", "Kinematics source"
H_RV, H_PMRA, H_PMDE = ("Radial velocity (km/s)", "Proper motion in RA, μα·cos δ (mas/yr)",
                        "Proper motion in Dec, μδ (mas/yr)")
H_RA, H_DE = "RA (deg, ICRS)", "Dec (deg, ICRS)"

# The new columns, appended after each tab's last.
H_SIMBAD, H_CNS5, H_EXIST, H_REFS = "SIMBAD main_id", "CNS5 id", "Existence", "Kinematics refs"

TABS = {
    "known": {"tab": "Known within 100ly", "name_col": H_NAME, "new": (H_SIMBAD, H_CNS5, H_EXIST, H_REFS),
              "motion_cols": (H_RV, H_PMRA, H_PMDE)},
    "systems": {"tab": "Systems within 100 ly", "name_col": H_NAME, "new": (H_SIMBAD, H_EXIST, H_REFS),
                "motion_cols": (H_RV, H_PMRA, H_PMDE)},
    "planetless": {"tab": "Planetless 4+ Stars", "name_col": "Star (component)", "new": (H_SIMBAD, H_EXIST, H_REFS),
                   "motion_cols": (H_RV, H_PMRA, H_PMDE)},
}


def read_tab(api, sid, tab):
    """(headers, rows) of a live tab, unformatted; rows padded to the header width."""
    vals = api.values().get(spreadsheetId=sid, range=f"{q(tab)}!A1:CZ20000",
                            valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
    h = [str(x).strip() for x in vals[0]]
    rows = [list(r) + [""] * (len(h) - len(r)) for r in vals[1:]]
    return h, rows


def notes_of(api, sid, tab, c, last_row):
    """The hover notes of column index c, rows 1..last_row, as a list ("" where none)."""
    a1 = f"{letter(c)}1:{letter(c)}{last_row}"
    d = api.get(spreadsheetId=sid, ranges=[f"{q(tab)}!{a1}"], includeGridData=True,
                fields="sheets.data.rowData.values.note").execute()
    rd = d["sheets"][0]["data"][0].get("rowData", [])
    out = [((r.get("values") or [{}])[0].get("note") or "") for r in rd]
    return out + [""] * (last_row - len(out))


def gaia_of(r, col):
    g = str(r[col[H_SID]]).strip()
    return g if g.isdigit() else None


def name_of(r, col, t):
    return str(r[col[t["name_col"]]]).strip()


def key_of(r, col, t):
    """A row's identity: its name (the component's on Planetless) plus its Gaia id. Never its row number."""
    return row_key(name_of(r, col, t), r[col[H_SID]])
