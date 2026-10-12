# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Append the Sources & Provenance entry for the resumed search, then rename the workbook."""
import json
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))
from hybrasil.data import google_sheets as gs  # noqa: E402

PLAN = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
LOG = json.loads((HERE / "write_log.json").read_text(encoding="utf-8"))
UN, RJ = "Unconfirmed within 100 ly", "Rejected candidates"


def first_url(sources):
    for s in (sources or {}).values():
        if isinstance(s, dict) and s.get("url"):
            return s["url"]
    return ""


paras = [
    "RESUMED UNCONFIRMED-CANDIDATE SEARCH, 26-27 SEPTEMBER 2026: 151 CANDIDATES (89 ON UNCONFIRMED, 62 ON REJECTED "
    "CANDIDATES), 63 NEW SYSTEMS ROWS, THREE TOIs MOVED TO PLANETS.",
    "What: the search halted on 24 September (entry from row 3583) was finished. Nineteen research agents worked to the "
    "same brief (data/unconfirmed_search/pack/BRIEF.md, with a 26 September section on what changed): per-system batches "
    "B03-B16 over every Systems-tab host the first run had not reached (B04 finished its literature search), and sweeps "
    "C03 exoplanet.eu Candidate/Controversial/Unconfirmed statuses, C04 Feng et al. 2022 and the California Legacy "
    "Survey, C05 LCES (Butler et al. 2017) and CARMENES DR1 (Ribas et al. 2023), C06 ExoFOP community TOIs, and C07 "
    "Systems data for the TOI hosts that had none. Agents wrote only local JSON; every sheet edit here was made by one "
    "guarded script with expect-checks. The full records, with every source URL, table locator, alias searched and "
    "exclusion reason, are committed as data/unconfirmed_search/agent_output/ (second run).",
    "Owner's rulings applied (26-27 Sep): TRAPPIST-1 i stays; rows backed only by a proper-motion anomaly or an RV trend "
    "stay on Unconfirmed as ambiguous; a signal from Tuomi et al. 2019 alone is at best ambiguous; every candidate is "
    "written and tiered honestly, with unlikely ones filed on Rejected candidates; a new Systems row only for a host with "
    "a strong or ambiguous candidate; of Kiefer et al. 2025 (GaiaPMEX) only the four hosts exoplanet.eu lists; errors "
    "found in the Planets and Systems tabs are recorded in TODO.md, not fixed here.",
    "Dedupe: every candidate was checked against Planets, Unconfirmed and Rejected by name and alias, and by host plus "
    "period within 2%, which caught records filed under other names (GJ 739 b as 'GJ 739 c', GJ 654 b, GJ 3822's "
    "18.26 d signal). 49 agent records were already on the sheet; 2 duplicated each other; CD-35 2722 b I and II were "
    "dropped as already on the Exomoons tab. Writer's tier changes: HD 192310 P=24.6d strong -> ambiguous and HD 3765 c "
    "strong -> ambiguous (both near the rotation period); HD 82943 d ambiguous -> unlikely (California Legacy Survey "
    "Table 7 false positive).",
    "Housekeeping on Unconfirmed: TOI-2540.01, TOI-5961.01 and TOI-6662.01, validated by Collier et al. 2026 "
    "(arXiv:2608.21560v3, Table 3), moved to Planets rows 541-543 as TOI-2540 b, TOI-5961 b and TOI-6662 b (the rows "
    "were copied whole, so the orbit and radius are still the TOI table's). TOI-7032.01 (= GJ 523 b, Planets) and "
    "TOI-6716.01 (= TOI-6716 b, Planets) deleted as duplicates. Candidate rows re-hosted onto the Systems names of their "
    "stars: TOI-6276 -> HIP 56998, TOI-6713 -> HD 104067, and eight TOI hosts given their HD/HIP names by C07 "
    "(TOI-2009 -> HD 6660, TOI-2540 -> HD 274255, TOI-4324 -> HIP 47619, TOI-4328 -> HD 29086, TOI-5961 -> HIP 114941, "
    "TOI-6978 -> HD 188559, TOI-7052 -> HIP 87773, TOI-802 -> HD 47252). The Planets constants block moved down three "
    "rows (now from row 544); every formula that points at it followed.",
    "New Systems rows 363-425, inserted inside the pinned range, which is now $2:$426. Kinematics from Gaia DR3 "
    "gaia_source by source_id (RA, Dec, parallax, proper motion, RV), total proper motion and space velocity as "
    "hypot(RV, 4.74047 mu d), galactic l/b and direction of motion by the astropy method of the entry from row 3973. "
    "Stellar mass, Teff, radius and luminosity from the research records (a paper's table, else TIC v8.2, else Gaia DR3 "
    "FLAME); for GJ 412 A and GJ 257 A, which TIC v8.2 gives no Teff, the writer took Gaia DR3 FLAME luminosity and "
    "GSP-Phot Teff, with a WEAK note. Host luminosity (N) and HZ distance (O) are TYPED, as on the rows added on 24 "
    "September; O uses the column's Kopparapu recipe (pack/hz.py). Class sort key: letter x10 plus subtype (O=0 ... M=60), "
    "a bare letter +5, extended here to L=70, T=80 and white dwarfs D=90. Hosts left without a luminosity (so 'no "
    "luminosity on file'): GJ 65, GJ 237, GJ 4248, CM Dra, two Gaia-named hosts and the white dwarfs.",
    "Orange (inferred) cells, 59, each with a hover note: 56 semi-major axes from Kepler's third law on the host mass "
    "named in the note, and 3 Systems luminosities from R^2 (Teff/5772)^4. 29 masses were published in M-Jup or M-sun "
    "and are stored in M-earth x 317.828 or x 332946 (note, no border). Radii are written as R-earth / the Planets "
    "R-earth-per-R-Jup constant, so the sheet's own column converts them back. No value came from Wikipedia: no pink.",
    "Known limits: SIMBAD and exoplanet.eu's TAP were often unreachable and the arXiv API rate-limited, so several agents "
    "took aliases from NASA, OEC and the papers and searched through arXiv HTML, OpenAlex and VizieR; each coverage note "
    "in the JSON says which. The shared web-search budget ran out during C03, C05, C06 and C07. Listed but not drawn: "
    "GJ 65 b and 61 Cyg b orbit companions (GJ 65 B, 61 Cyg B) that have no Multi-stars rows; trend-, PMa- and "
    "single-transit rows have no orbit.",
    "PER-ROW INDEX (name -> tab and row, tier, reference, first source URL):",
]
lines = []
for p in paras:
    lines += textwrap.wrap(p, 110) + [""]
for row in PLAN["rows"]:
    tab = row["_tab"]
    r = LOG["step4"][tab][row["A"]]
    short = "Unconfirmed" if tab == UN else "Rejected"
    lines += textwrap.wrap(f"{row['A']} -> {short} {r}, {row['AJ']} [{row['_agent']}]: {row['AM']} {first_url(row['_sources'])}",
                           110, subsequent_indent="    ")
lines += ["", "NEW SYSTEMS ROWS (host -> row, source of the stellar values):"]
first = LOG["step3"]["first"]
for k, s in enumerate(PLAN["systems_rows"]):
    cites = "; ".join(sorted({v.get("citation", "")[:70] for v in (s.get("_sources") or {}).values()
                              if isinstance(v, dict) and v.get("citation")}))[:300]
    lines += textwrap.wrap(f"{s['A']} -> Systems {first + k} [{s['_agent']}]: Gaia DR3 {s['AL']}; {cites}", 110,
                           subsequent_indent="    ")
lines = [""] + lines

sid = gs.resolve_spreadsheet_id()
api = gs._sheets_api()
S = "Sources & Provenance"
meta = api.get(spreadsheetId=sid, ranges=[f"'{S}'!A1"], fields="sheets(properties(sheetId,gridProperties))").execute()["sheets"][0]["properties"]
rows = meta["gridProperties"]["rowCount"]
last = gs.read_cells(sid, [f"'{S}'!A{rows}"])[f"'{S}'!A{rows}"]
assert last and "claimed no moon" in last[0][0], last
start, end = rows + 1, rows + len(lines)
api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {"sheetId": meta["sheetId"], "dimension": "ROWS",
                                                                           "length": len(lines)}}]}).execute()
gs.update_cells(sid, {f"'{S}'!A{start}:A{end}": [[x] for x in lines]},
                expect={f"'{S}'!A{i}": "" for i in (start, start + 1, end)})
print(f"S&P rows {start}-{end}")
print(gs.rename_workbook(None, gs.versioned_title()))
