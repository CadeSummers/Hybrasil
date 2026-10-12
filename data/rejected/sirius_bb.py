# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Mark Sirius Bb, on the Rejected candidates tab, as refuted, and note the JWST search that may settle it.

    python sirius_bb.py          what it would write; touches nothing
    python sirius_bb.py write    write the three cells (each checked against its expected old value first), log a
                                 dated block on Sources & Provenance, rename the workbook

10 Oct 2026.  Sirius Bb is exoplanet.eu's 'Candidate' (1.5 +/- 0.5 MJup at 0.9 +/- 0.4 au, 2024).  No paper claims it,
and none refutes it by name: the verdict is this project's, from Kiefer et al. 2024 (arXiv:2409.16992, Sect. 8.4:
Sirius A 'may indeed explain the ruwe') and Lucas et al. 2022 (AJ 163, 81: Keck/NIRC2, no companion).  JWST GO 7612
(Cycle 4, PI L. Pearce: MIRI coronagraphy of Sirius B, 0.004-3.9 au) is the search that could still find one.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from hybrasil.data import google_sheets as gs  # noqa: E402

TAB, SP = "Rejected candidates", "Sources & Provenance"
PLANET = "Sirius Bb"
LOG = HERE / "sirius_bb_log.json"
TODAY = datetime.date.today().isoformat()

JWST = ("JWST GO 7612 (Cycle 4, PI L. Pearce, Univ. of Michigan; 'We can directly image super-Earth-sized planets "
        "near the habitable zone of Sirius B with JWST/MIRI'): MIRI coronagraphy and an infrared-excess search of "
        "Sirius B from the Roche limit (0.004 au) to the Hill sphere (3.9 au), 16 h; no result published as of "
        f"{TODAY}. If it finds a source at 0.5-1.3 au this row must be revisited "
        "(https://www.stsci.edu/jwst-program-info/download/jwst/pdf/7612/).")
OLD_REASON = ("No detection. Kiefer+2024 find that Sirius A itself (resolved, ~20 au) can explain Sirius B's Gaia RUWE "
              "('seems to explain the observed ruwe without the need to invoke a supplementary companion'; A lies "
              "within the 3-sigma region). What remains is a PSF-shape statistic (ipd_frac_multi_peak 18%, "
              "ipd_gof_harmonic_amplitude 0.05) that 'implies' a faint source (flux ratio 1e-4 to 1e-3) at 200-500 mas "
              "(0.5-1.3 au); the authors only say this 'strongly suggests digging further'. exoplanet.eu turned that "
              "into a 1.5 MJup planet at 0.9 au. Keck imaging (Lucas+2022, as quoted in S1) excludes >2.4 MJup beyond "
              "0.5 au.")
NEW_REASON = ("REFUTED (this project's verdict, 10 Oct 2026; no paper refutes it by name, and none ever claimed it). "
              + OLD_REASON + " " + JWST)


def main():
    write = "write" in sys.argv[1:]
    sid = gs.resolve_spreadsheet_id()
    q = "'" + TAB + "'"
    vals = gs.read_cells(sid, [f"{q}!A1:AQ200"])[f"{q}!A1:AQ200"]
    h = vals[0]
    hits = [i for i, r in enumerate(vals) if r and r[0] == PLANET]
    assert len(hits) == 1, hits
    n = hits[0] + 1
    row = vals[hits[0]] + [""] * (len(h) - len(vals[hits[0]]))

    def cell(col):
        j = h.index(col)
        return f"{q}!{chr(65 + j) if j < 26 else 'A' + chr(65 + j - 26)}{n}", row[j]

    flags_a1, flags = cell("Orbit data source / flags")
    date_a1, date = cell("Vetting date / last updated")
    why_a1, why = cell("Rejected because")
    assert why == OLD_REASON, "the Rejected because cell is not what was planned against"
    updates = {flags_a1: [[flags + " " + JWST]], date_a1: [[TODAY]], why_a1: [[NEW_REASON]]}
    print(f"{PLANET}: row {n}; will write {', '.join(updates)}")
    if not write:
        return
    gs.update_cells(sid, updates, expect={flags_a1: flags, date_a1: date, why_a1: why})
    back = gs.read_cells(sid, list(updates))
    assert all(back[a][0][0] == v[0][0] for a, v in updates.items()), "read-back differs"

    api = gs._sheets_api()
    props = {s["properties"]["title"]: s["properties"]
             for s in api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]}[SP]
    last = props["gridProperties"]["rowCount"]
    lines = ["", f"{TODAY}: SIRIUS Bb MARKED REFUTED (Rejected candidates row {n}; data/rejected/sirius_bb.py).",
             "Rejected because now opens 'REFUTED (this project's verdict...)': exoplanet.eu lists it as a candidate "
             "(1.5 +/- 0.5 MJup, 0.9 +/- 0.4 au, 2024), but no paper claims it. Its only basis is Kiefer et al. 2024 "
             "(GaiaPMEX I, arXiv:2409.16992, Sect. 8.4), which finds Sirius A 'may indeed explain the ruwe' and leaves "
             "only a PSF-shape hint; Keck/NIRC2 (Lucas et al. 2022, AJ 163, 81) sees no companion.",
             "Added to the row: " + JWST,
             "Vetting date set to the re-vetting date."]
    sq = "'" + SP + "'"
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
        "sheetId": props["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(sid, {f"{sq}!A{last + 1}:A{last + len(lines)}": [[x] for x in lines]},
                    expect={f"{sq}!A{last + 1}": "", f"{sq}!A{last + len(lines)}": ""})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(sid)
    log = {"at": datetime.datetime.now().isoformat(timespec="seconds"), "row": n, "cells": list(updates),
           "sp_block": [last + 1, last + len(lines)], "title": title}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log))


if __name__ == "__main__":
    main()
