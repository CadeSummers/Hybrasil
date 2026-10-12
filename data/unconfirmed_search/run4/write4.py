# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run 4: fill the Systems tab's blank Stellar Class, Host mass, Effective temp and Host luminosity cells.

    python write4.py            write, then add the Sources & Provenance block and rename the workbook

Values come from plan.json (catalogue picks made by resolve.py from candidates.json) and, where the agents
researched a row, from agent_output/S1.json and S2.json, which take precedence. Every written cell gets a note
naming its source; derived values also get the orange border. Luminosity class (J) is a formula on the
Stellar Class and fills itself.

Host luminosity follows the workbook's rule that Planets col H is the master column: where the Systems
cell is the INDEX/MATCH formula and the host still has planets, the value goes into those Planets rows; the
Systems cell then resolves by itself. Otherwise the Systems cell is typed.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from googleapiclient.errors import HttpError  # noqa: E402
from googleapiclient.http import HttpRequest  # noqa: E402

from hybrasil.data import google_sheets as gs  # noqa: E402

_execute = HttpRequest.execute


def _execute_with_retry(self, *a, **k):
    for attempt in range(8):
        try:
            return _execute(self, *a, **k)
        except HttpError as e:
            if e.resp.status != 429 or attempt == 7:
                raise
            time.sleep(35)


HttpRequest.execute = _execute_with_retry

SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
SY, PL, SP = "'Systems within 100 ly'", "'Planets within 100 ly'", "'Sources & Provenance'"
COL = {"Stellar Class": "H", "Host mass (M-sun)": "G", "Effective temp (K)": "K", "Host luminosity (L-sun)": "N"}
KEY = {"H": "Stellar Class", "G": "Host mass (M-sun)", "K": "Effective temp (K)", "N": "Host luminosity (L-sun)"}
DATE = "27 Sep 2026"
LOG = HERE / "write_log.json"

plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
gaps = {g["name"]: g for g in json.loads((HERE / "systems_gaps.json").read_text(encoding="utf-8"))}

# name -> {col: (value, source text, derived, method)}
fill = {name: {c: (v[0], v[1], v[2], "") for c, v in p["pick"].items()} for name, p in plan.items()}
for agent in ("S1", "S2"):
    path = HERE / "agent_output" / f"{agent}.json"
    if not path.exists():
        assert "--dry" in sys.argv, f"{path.name} missing"
        continue
    for it in json.loads(path.read_text(encoding="utf-8"))["items"]:
        name = it["name"]
        for h, v in (it.get("fields") or {}).items():
            if h not in COL or v.get("value") in (None, ""):
                continue
            c = COL[h]
            if name not in gaps or c not in gaps[name]["missing"]:
                if not (name == "DE CVn" and c in ("K", "N")):   # DE CVn: S1 re-decides the automated picks
                    print(f"skip {agent} {name} {h}: cell is not blank")
                    continue
            fill.setdefault(name, {})[c] = (v["value"], f"{v.get('source', '')} {v.get('url', '')}".strip(),
                                            bool(v.get("derived")), v.get("method") or "")


def values(rng, formula=False):
    return API.values().get(spreadsheetId=SID, range=rng,
                            valueRenderOption="FORMULA" if formula else "UNFORMATTED_VALUE").execute().get("values", [])


sys_a = [r[0] if r else "" for r in values(f"{SY}!A1:A500")]
pl_rows = values(f"{PL}!A1:H800")
upd, exp, notes, orange, done = {}, {}, {}, [], {}
for name, cols in sorted(fill.items()):
    if not cols:
        continue
    assert sys_a.count(name) == 1, name
    r = sys_a.index(name) + 1                         # the live row: the sheet re-sorts, so never trust a stored number
    exp[f"{SY}!A{r}"] = name
    for c, (val, src, derived, method) in cols.items():
        note = (f"{'INFERRED' if derived else 'SOURCE'} (filled {DATE}): {src}" + (f" Method: {method}" if method else ""))[:1500]
        target = f"{SY}!{c}{r}"
        if c == "N" and gaps[name]["N_is_formula"]:
            host = gaps[name]["planet_host"] or name
            prow = [i + 1 for i, x in enumerate(pl_rows) if len(x) > 4 and x[4] == host and i > 0]
            if prow:                                   # Planets col H is the master column
                for i in prow:
                    cur = pl_rows[i - 1][7] if len(pl_rows[i - 1]) > 7 else ""
                    assert cur in ("", None), (name, i, cur)
                    upd[f"{PL}!H{i}"] = val
                    exp[f"{PL}!A{i}"] = pl_rows[i - 1][0]
                    notes[f"{PL}!H{i}"] = note
                    if derived:
                        orange.append(f"{PL}!H{i}")
                done.setdefault(name, {})[c] = {"value": val, "via": [f"Planets H{i}" for i in prow]}
                continue
        exp[target] = ""                                # every target cell is blank now
        upd[target] = val
        notes[target] = note
        if derived:
            orange.append(target)
        done.setdefault(name, {})[c] = {"value": val, "source": src[:200], "derived": derived}

# One deliberate correction, not a gap: WD 0806-661's 5700 K contradicts every modern source, and the
# luminosity filled above is computed at 10393 K, so leaving 5700 beside it would make the row inconsistent.
r = sys_a.index("WD 0806-661") + 1
upd[f"{SY}!K{r}"] = 10393
exp[f"{SY}!K{r}"] = 5700
notes[f"{SY}!K{r}"] = (f"CORRECTED ({DATE}) from 5700 K, which no source supports: O'Brien et al. 2024, MNRAS 527, 8687, "
                       "Table A1 (VizieR J/MNRAS/527/8687/tablea1): He-atmosphere DQ, Teff 10393 +/- 114 K, log g 8.041. "
                       "Leggett & Tremblin 2026 (arXiv:2606.04294) and NASA pscomppars adopt it; Gentile Fusillo 2021 (He) "
                       "gives 10721 K. The luminosity in N is computed at this Teff.")
done.setdefault("WD 0806-661", {})["K"] = {"value": 10393, "source": "O'Brien et al. 2024 (CORRECTION of 5700 K)",
                                            "derived": False}

if "--dry" in sys.argv:
    print(len(upd), "cells;", len(orange), "orange;", len(done), "rows")
    sys.exit()
print("writing", len(upd), "cells")
gs.update_cells(SID, upd, expect=exp)
for i in range(0, len(orange), 80):
    gs.set_border(SID, orange[i:i + 80], gs.INFERRED_BORDER)
gs.set_note(SID, notes)
LOG.write_text(json.dumps({"filled": done, "orange": orange}, indent=1, ensure_ascii=False), encoding="utf-8")

# Sources & Provenance block, then the rename.
from collections import Counter  # noqa: E402
cnt = Counter(c for d in done.values() for c in d)
src = Counter((c, (v.get("source") or "Planets H (master)").split(" (")[0].split(",")[0][:60]) for d in done.values()
              for c, v in d.items())
lines = ["", f"SYSTEMS TAB GAP FILL, {DATE.upper()}: STELLAR CLASS, HOST MASS, EFFECTIVE TEMP, HOST LUMINOSITY.",
         f"Filled: {', '.join(f'{KEY[c]} {n}' for c, n in sorted(cnt.items()))} cells, in {len(done)} rows. "
         "Luminosity class follows by formula.",
         "Every filled cell carries a hover note naming its source; derived values are orange-boxed as usual.",
         "Order of preference, per value (repo: data/unconfirmed_search/run4/, resolve.py and write4.py):",
         "  Teff: NASA Exoplanet Archive pscomppars st_teff (its per-field reference) > TIC v8.2 Teff > Gaia DR3 GSP-Spec",
         "    (not for M dwarfs). Gaia GSP-Phot is never used. Teff is never estimated from the spectral class.",
         "  Mass: pscomppars st_mass > TIC v8.2 Mass > Gaia DR3 FLAME mass_flame. Mass and Teff are the row's own star:",
         "    archive rows matched only through a companion planet host (GJ 667 C, GJ 338 B, psi1 Dra B) are not used,",
         "    and GJ 900 A's archive mass (1.08, Rothermich et al. 2024) is the whole triple's, so TIC's 0.675 is used.",
         "  Luminosity: TIC v8.2 Lum for M dwarfs (Mann-relation radii), Gaia DR3 FLAME lum_flame otherwise, then",
         "    10^st_lum from the archive (orange). For a host that still has planets the value went into Planets col H,",
         "    the master column the Systems formula reads (DE CVn, WD 0806-661, VHS J1256); elsewhere it is typed.",
         "  Stellar Class: SIMBAD sp_type where present; the six stars SIMBAD has no type for, from the literature.",
         "  White dwarfs, ultracool dwarfs and stars no catalogue covered were researched from papers by agents S1 and",
         "    S2 (records in run4/agent_output/); white dwarfs never take a main-sequence relation or a TIC dwarf value.",
         "Sources by count: " + "; ".join(f"{KEY[c].split(' (')[0]} <- {s} x{n}" for (c, s), n in sorted(src.items())) + "."]
import textwrap  # noqa: E402
wrapped = []
for ln in lines:
    wrapped += textwrap.wrap(ln, 112, subsequent_indent="    ") or [""]
meta = API.get(spreadsheetId=SID, ranges=[f"{SP}!A1"], fields="sheets(properties(sheetId,gridProperties))").execute()[
    "sheets"][0]["properties"]
rows = meta["gridProperties"]["rowCount"]
last = values(f"{SP}!A{rows}")
assert last and last[0][0].startswith("[Fe/H] sign, host masses"), last
start, end = rows + 1, rows + len(wrapped)
API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
    "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(wrapped)}}]}).execute()
gs.update_cells(SID, {f"{SP}!A{start}:A{end}": [[x] for x in wrapped]},
                expect={f"{SP}!A{i}": "" for i in (start, start + 1, end)})
title = gs.rename_workbook(None, gs.versioned_title())
log = json.loads(LOG.read_text(encoding="utf-8"))
log.update({"sp_rows": [start, end], "title": title})
LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
print("done:", len(done), "rows,", len(upd), "cells,", len(orange), "orange; S&P", start, "-", end, "; title", title)
