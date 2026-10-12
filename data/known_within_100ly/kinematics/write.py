# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The only writer: put merged.json's planned cells onto the live Known within 100ly tab.

    python write.py plan            what would be written now, against the live tab; touches nothing
    python write.py bulk            P3: the Gaia DR3 / SIMBAD fill (the first run)
    python write.py wave            P4: whatever the agents' research has added since the last run
    python write.py renote-plan     what renote would do; touches nothing
    python write.py renote          refresh notes and Kinematics source on cells already written, where the plan now
                                    flags more (a WEAK systematic, a doubtful-membership flag); values never change

Safe to re-run at any point, including after a crash:
  * Rows are found by name + Gaia DR3 source_id in a fresh read of the tab, never by a stored row number.
  * A planned cell is written only if it is blank on the live sheet; a filled cell is never touched.
  * Work goes in chunks of contiguous rows. Each chunk re-reads its rows immediately before writing and aborts the
    whole run on any mismatch (the expect= guard of gs.update_cells, applied to the chunk). Each chunk is one
    batchUpdate, values + notes + borders together, so a chunk lands whole or not at all.
  * write_log.json records every run; a run that stopped before its Sources & Provenance block finishes it next time.
Marks: looked-up values keep the tab's grey rule (+ a SOURCE: note); derived values get the orange box
(gs.INFERRED_BORDER, + an INFERRED: note); Wikipedia-sourced values get the pink box (gs.WIKIPEDIA_BORDER) and a row
in the Wikipedia sources tab's VALUES WRITTEN FROM WIKIPEDIA table.
"""
import datetime
import sys
from collections import Counter

from common import (KN, SP, WIKI, MERGED, WRITE_LOG, H_NAME, H_PLOT, H_UPD, H_SID, H_KS, H_RV, H_DIST, letter, load,
                    mark, now, q, read_known, live_key, save, sheets, blank, num, TARGET_COLS)

CHUNK_ROWS = 300
TODAY = datetime.date.today().isoformat()


def live_index(h, rows):
    col = {k: i for i, k in enumerate(h)}
    at = {}
    for n, r in enumerate(rows, start=2):
        k = live_key(r[col[H_NAME]], r[col[H_SID]])
        assert k not in at, f"two live rows are {k}"
        at[k] = n
    return col, at


def planned_now(plan, h, rows, mode):
    """{row number: {header: cell}} of planned cells that are blank on the live sheet, plus extras per row."""
    col, at = live_index(h, rows)
    out, skipped, missing = {}, Counter(), []
    for k, p in plan.items():
        n = at.get(k)
        if n is None:
            missing.append(k)
            continue
        live = rows[n - 2]
        cells = {}
        for hd, c in p["cells"].items():
            if blank(live[col[hd]]):
                cells[hd] = c
            else:
                skipped[hd] += 1
        if cells and blank(live[col[H_KS]]):
            cells[H_KS] = {"value": p["kin_source"], "mark": "grey", "note": None}
        elif cells and not p["plotted"] and str(live[col[H_KS]]) != p["kin_source"]:
            cells[H_KS] = {"value": p["kin_source"], "mark": "grey", "note": None, "replace": live[col[H_KS]]}
        real = any(not hd.startswith("__") for hd in cells)
        if mode == "bulk" and not p["plotted"] and blank(live[col[H_RV]]) and not p["has_rv"]:
            cells["__rv_note"] = {"note": f"BLANK: no radial velocity found in Gaia DR3 or SIMBAD ({TODAY}) or by "
                                          "agent research so far. Space velocity and motion toward l/b need one."}
        if real and not p["plotted"] and str(live[col[H_UPD]]) != TODAY:
            cells[H_UPD] = {"value": TODAY, "mark": "grey", "note": None, "replace": live[col[H_UPD]]}
        if real or "__rv_note" in cells:
            out[n] = {"key": k, "cells": cells}
    return col, out, skipped, missing


def cell_request(sheet_id, r, c, cell):
    v = cell.get("value")
    data = {}
    fields = []
    if "value" in cell:
        data["userEnteredValue"] = ({"numberValue": v} if isinstance(v, (int, float)) and not isinstance(v, bool)
                                    else {"stringValue": str(v)})
        fields.append("userEnteredValue")
    if cell.get("note"):
        data["note"] = cell["note"]
        fields.append("note")
    return {"updateCells": {"range": {"sheetId": sheet_id, "startRowIndex": r - 1, "endRowIndex": r,
                                      "startColumnIndex": c, "endColumnIndex": c + 1},
                            "rows": [{"values": [data]}], "fields": ",".join(fields)}}


def border_request(gs, sheet_id, r, c, colour):
    side = {"style": "SOLID_MEDIUM", "color": gs._hex_to_color(colour)}
    return {"updateBorders": {"range": {"sheetId": sheet_id, "startRowIndex": r - 1, "endRowIndex": r,
                                        "startColumnIndex": c, "endColumnIndex": c + 1},
                              "top": side, "bottom": side, "left": side, "right": side}}


def verify_chunk(api, sid, col, width, r0, r1, todo):
    """Re-read rows r0..r1 and check each planned row is still the same star with its target cells still blank."""
    vals = api.values().get(spreadsheetId=sid, range=f"{q(KN)}!A{r0}:{letter(width - 1)}{r1}",
                            valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [])
    for n, item in todo.items():
        live = list(vals[n - r0]) + [""] * width
        k = live_key(live[col[H_NAME]], live[col[H_SID]])
        if k != item["key"]:
            raise SystemExit(f"row {n} holds {k}, expected {item['key']}. Nothing in this chunk was written.")
        for hd, c in item["cells"].items():
            if hd.startswith("__"):
                continue
            want = c.get("replace", "")
            got = live[col[hd]]
            if (blank(got) and blank(want)) or got == want:
                continue
            raise SystemExit(f"{hd} on row {n} ({item['key']}) holds {got!r}, expected {want!r}. Nothing in this "
                             "chunk was written.")


def wiki_rows(gs, api, sid, entries):
    """Append rows to the VALUES WRITTEN FROM WIKIPEDIA table, keyed by STAR / FIELD."""
    if not entries:
        return None
    vals = api.values().get(spreadsheetId=sid, range=f"{q(WIKI)}!A1:K400").execute()["values"]
    top = next(i for i, r in enumerate(vals) if r and str(r[0]).startswith("VALUES WRITTEN FROM WIKIPEDIA"))
    assert vals[top + 1][0] == "SHEET", vals[top + 1][:3]
    end = top + 2
    while end < len(vals) and vals[end] and str(vals[end][0]).strip():
        end += 1
    # end is the 0-based index of the first blank row after the table: insert there
    meta = api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]
    wid = next(s["properties"]["sheetId"] for s in meta if s["properties"]["title"] == WIKI)
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"insertDimension": {
        "range": {"sheetId": wid, "dimension": "ROWS", "startIndex": end, "endIndex": end + len(entries)},
        "inheritFromBefore": True}}]}).execute()
    gs.update_cells(sid, {f"{q(WIKI)}!A{end + 1}:K{end + len(entries)}": entries},
                    expect={f"{q(WIKI)}!A{end + 1}": "", f"{q(WIKI)}!A{end}": vals[end - 1][0]})
    return [end + 1, end + len(entries)]


def sp_block(kind, counts, written_rows, agents, wiki_n, blended_n=0):
    head = (f"{TODAY}: 'Known within 100ly' -- MOTION COLUMNS FILLED FOR UNPLOTTED OBJECTS, "
            f"{'BULK CATALOG PASS' if kind == 'bulk' else 'RESEARCH WAVE ' + ', '.join(agents)} "
            f"({written_rows} rows; data/known_within_100ly/kinematics/, log write_log.json).")
    lines = ["", head.upper() if kind == "bulk" else head,
             "Why: so the Nearby Stellar Motion view can draw every known object within 100 ly (purple, unclassified "
             "for now), with an arrow where a space velocity exists. Blank cells only: nothing already on the tab was "
             "changed. Plotted rows keep their copies of Systems / Multi-stars values; only their blanks were filled.",
             "Cells written: " + ", ".join(f"{h.split(' (')[0].split(',')[0]} {n}" for h, n in counts.items() if n) + "."]
    if kind == "bulk":
        lines += [
            "Inputs, looked up (grey rule, SOURCE: note with id, value, error):",
            "  Proper motion: Gaia DR3 gaia_source by the row's source_id (ESA TAP, 2026-10-08); for rows with no Gaia "
            "id (CNS5 additions) SIMBAD's adopted proper motion, the object found by its GJ name, else the nearest "
            "SIMBAD object within 90\" with a parallax within 25% of the row's distance.",
            "  Radial velocity: Gaia DR3 radial_velocity (combined light, not systemic for an unresolved binary); "
            "where Gaia has none, SIMBAD's adopted RV if velocity-type, quality A-C, nonzero and under 600 km/s "
            "(SIMBAD gives EZ Aqr 6824.7 km/s: rejected). A component row (e.g. 'GJ 229 B') matched only at system "
            "level or by position takes no SIMBAD value -- it may be its primary's.",
            "Derived (orange box, INFERRED: note), by the construction of lines 3977-3985 (astropy SkyCoord -> "
            "galactic (U, V, W), heliocentric, no LSR correction): Total proper motion, Galactic l/b (from RA/Dec, "
            "exact), and -- only where an RV exists -- Space velocity = |(U, V, W)|, Motion toward l/b. Checked "
            "against the Systems tab's own values on 8 plotted stars (alf Cen A, Barnard's star, Wolf 359, GJ 411, "
            "GJ 65, GJ 729, eps Eri, GJ 887): l/b and motion l/b agree to the printed digit, speed to 0.04 km/s.",
            "  WEAK in the motion notes where Gaia RUWE > 1.4 (a companion may perturb the astrometry), the Gaia RV "
            "error is over 5 km/s, or the RV is SIMBAD quality C.",
            "No RV found: Radial velocity, Space velocity and Motion toward l/b stay BLANK, with a note on the RV "
            "cell saying so; the view draws a dot without an arrow. Those rows go to literature research next "
            "(data/known_within_100ly/agent_output/), brightest first.",
            "'Kinematics source' says, per row, where RV and PM came from; 'Last Updated' is today's date on every "
            "unplotted row written.",
        ]
    else:
        lines += [
            "Inputs: radial velocities and proper motions found by literature research agents (batches "
            + ", ".join(agents) + "; each value's paper, table and locator in its SOURCE: note, all agent records in "
            "data/known_within_100ly/agent_output/). Gaia DR3 and SIMBAD had none for these rows.",
            "Derived columns as in the bulk pass above (orange; astropy; no LSR correction).",
        ]
        if wiki_n:
            lines.append(f"  {wiki_n} values are from Wikipedia (pink box), each logged in 'Wikipedia sources' with the "
                         "source Wikipedia cites.")
        if blended_n:
            lines.append(
                f"  {blended_n} rows take a COMBINED-LIGHT (or, for NLTT 33370 AB, systemic) RV of an unresolved pair, "
                "which the agents had found and withheld under their component rule. Accepted by the owner on "
                "2026-10-09, as the bulk pass accepts Gaia DR3's combined-light RVs. Written to each member whose "
                "light is in the spectrum: pairs closer than ~2.5 arcsec with members within 2.5 mag in Gaia G. Each "
                "RV note says NOT THIS COMPONENT'S OWN and names the companion; 'Kinematics source' and the motion "
                "notes carry it as a WEAK flag. Values for one blend that disagree by 15+ km/s, errors over 20 km/s, "
                "and a companion swamped by a primary 5+ mag brighter were not taken (merge.py BLENDED, with each "
                "reason). NLTT 33370 AB's two rows also take its barycentric proper motion (Forbrich et al. 2016).")
    return lines


def append_sp(gs, api, sid, lines):
    meta = api.get(spreadsheetId=sid, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    last = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(sid, [f"{q(SP)}!A{last}"])[f"{q(SP)}!A{last}"][0][0].strip()
    start, end = last + 1, last + len(lines)
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(sid, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, end)})
    return [start, end]


def withdraw():
    """Clear agent RVs on the sheet that the agents' final files, or merge.REJECT, no longer support.

    A wave once wrote a running batch's partial file; two of its values changed afterwards. Each withdrawn row
    loses its RV and the three cells derived from it, the orange boxes go back to the tab's grey rule, and the RV
    cell's note says what was withdrawn and why.
    """
    from merge import agent_values, REJECT
    from common import GREY_RULE, H_V, H_ML, H_MB, H_PMRA, H_PMDE, num
    gs, sid, api = sheets()
    h, rows = read_known(api, sid)
    col, at = live_index(h, rows)
    ag = agent_values()
    todo = []
    for k, n in at.items():
        r = rows[n - 2]
        ks = str(r[col[H_KS]])
        if not ks.startswith("RV: literature ("):
            continue
        a = ag.get(k)
        want = round(num(a["rv"]["value"]), 3) if a and a.get("rv") else None
        if want is not None and abs(num(r[col[H_RV]]) - want) < 1e-6:
            continue
        why = REJECT.get(k, {}).get("rv") or "the research batch's final record has no RV for this row"
        todo.append((n, k, r[col[H_RV]], why, ks))
    print(f"withdraw: {len(todo)} rows")
    for n, k, v, why, ks in todo:
        print(f"  row {n} {k}: RV {v} -- {why}")
    if not todo:
        return
    meta = api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]
    kid = next(s["properties"]["sheetId"] for s in meta if s["properties"]["title"] == KN)
    grey = {"style": "SOLID", "color": gs._hex_to_color(GREY_RULE)}
    reqs = []
    for n, k, v, why, ks in todo:
        verify_chunk(api, sid, col, len(h), n, n, {n: {"key": k, "cells": {H_RV: {"replace": v}, H_KS: {"replace": ks}}}})
        for hd in (H_RV, H_V, H_ML, H_MB):
            c = col[hd]
            note = (f"WITHDRAWN {TODAY}: an RV of {v} km/s was written here earlier today and withdrawn: {why}. "
                    "Space velocity and motion toward l/b need an RV.") if hd == H_RV else ""
            reqs.append({"updateCells": {"range": {"sheetId": kid, "startRowIndex": n - 1, "endRowIndex": n,
                                                   "startColumnIndex": c, "endColumnIndex": c + 1},
                                         "rows": [{"values": [{"note": note}]}], "fields": "userEnteredValue,note"}})
            if hd != H_RV:
                reqs.append({"updateBorders": {"range": {"sheetId": kid, "startRowIndex": n - 1, "endRowIndex": n,
                                                         "startColumnIndex": c, "endColumnIndex": c + 1},
                                               "top": grey, "bottom": grey, "left": grey, "right": grey}})
        pm = ks.split(";", 1)[1].strip() if ";" in ks else "PM: Gaia DR3"
        reqs.append(cell_request(kid, n, col[H_KS], {"value": f"RV: none (withdrawn {TODAY}); {pm}"}))
    api.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()
    log = load(WRITE_LOG, {"runs": []})
    run = {"kind": "withdraw", "started": now(), "rows": [(n, k, v, why) for n, k, v, why, _ in todo]}
    run["sp_rows"] = append_sp(gs, api, sid, ["", f"{TODAY}: 'Known within 100ly' -- {len(todo)} RESEARCH RVs WITHDRAWN "
                                             "(data/known_within_100ly/kinematics/write.py withdraw). A research wave "
                                             "had written a batch's partial file; its final record, or the orchestrator's "
                                             "review, no longer supports these. RV, Space velocity and Motion toward l/b "
                                             "cleared, orange boxes restored to the grey rule, the reason in each RV note: "
                                             + "; ".join(f"{k.split('|')[0]} ({why})" for _, k, _, why, _ in todo) + "."])
    run["title"] = gs.rename_workbook(None, gs.versioned_title())
    run["state"], run["finished"] = "done", now()
    log["runs"].append(run)
    save(WRITE_LOG, log)
    gs.invalidate_cache(sid)
    print("done:", run["title"], gs.spreadsheet_url(sid))


def notes_of(api, sid, a1):
    """The hover notes of one single-column range on the Known tab, as a list ("" where none)."""
    d = api.get(spreadsheetId=sid, ranges=[f"{q(KN)}!{a1}"], includeGridData=True,
                fields="sheets.data.rowData.values.note").execute()
    rd = d["sheets"][0]["data"][0].get("rowData", [])
    return [((r.get("values") or [{}])[0].get("note") or "") for r in rd]


def renote(dry):
    """Re-note cells the pipeline already wrote, where merged.json now carries more flags.

    Touches a row only when its live 'Kinematics source' has the plan's base (the text before the first ' | ') and
    differs only in its flags, so a withdrawn or hand-edited row is left alone; and a cell only when it still holds
    the planned value. Values are never changed. A doubtful-membership note goes on the Distance cell, after any note
    already there.
    """
    plan = load(MERGED)["rows"]
    gs, sid, api = sheets()
    h, rows = read_known(api, sid)
    col, at = live_index(h, rows)
    dcol = letter(col[H_DIST])
    dist_notes = notes_of(api, sid, f"{dcol}2:{dcol}{len(rows) + 1}")
    todo, n_flag = {}, Counter()
    for k, p in plan.items():
        n = at.get(k)
        if n is None or p["plotted"]:
            continue
        live = rows[n - 2]
        ks_now = str(live[col[H_KS]])
        if ks_now == p["kin_source"] or ks_now.split(" | ")[0] != p["kin_source"].split(" | ")[0]:
            continue
        cells = {}
        for hd, c in p["cells"].items():
            v = num(live[col[hd]])
            if v is None or abs(v - c["value"]) > 1e-6:
                continue
            cells[hd] = {"note": c["note"], "replace": live[col[hd]]}
        if not cells:
            continue
        cells[H_KS] = {"value": p["kin_source"], "replace": live[col[H_KS]]}
        old = dist_notes[n - 2] if n - 2 < len(dist_notes) else ""
        if p.get("dist_note") and "DOUBTFUL MEMBERSHIP" not in old:
            cells["__dist"] = {"note": (old + "\n\n" if old else "") + p["dist_note"]}
        todo[n] = {"key": k, "cells": cells}
        for f in p["kin_source"].split(" | ")[1:]:
            if f not in ks_now:
                n_flag[f.split(" -- ")[0].split(":")[0].split(" 0.")[0]] += 1
    print(f"renote: {len(todo)} rows; new flags {dict(n_flag)}; distance notes "
          f"{sum('__dist' in it['cells'] for it in todo.values())}")
    if dry or not todo:
        for n in sorted(todo)[:3]:
            print(f"  row {n} {todo[n]['key']}: {todo[n]['cells'][H_KS]['replace']!r} -> {todo[n]['cells'][H_KS]['value']!r}")
        return
    log = load(WRITE_LOG, {"runs": []})
    run = {"kind": "renote", "started": now(), "state": "cells", "rows": 0}
    log["runs"].append(run)
    meta = api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]
    kid = next(s["properties"]["sheetId"] for s in meta if s["properties"]["title"] == KN)
    order = sorted(todo)
    i = 0
    while i < len(order):
        r0, chunk = order[i], {}
        while i < len(order) and order[i] < r0 + CHUNK_ROWS:
            chunk[order[i]] = todo[order[i]]
            i += 1
        verify_chunk(api, sid, col, len(h), r0, max(chunk), chunk)
        reqs = []
        for n, item in chunk.items():
            for hd, c in item["cells"].items():
                reqs.append(cell_request(kid, n, col[H_DIST] if hd == "__dist" else col[hd],
                                         {x: y for x, y in c.items() if x != "replace"}))
        api.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()
        run["rows"] += len(chunk)
        save(WRITE_LOG, log)
        print(f"  chunk rows {r0}-{max(chunk)}: {len(chunk)} rows, {len(reqs)} cells", flush=True)
    gs.invalidate_cache(sid)
    run["flags"] = dict(n_flag)
    run["sp_rows"] = append_sp(gs, api, sid, [
        "", f"{TODAY}: 'Known within 100ly' -- FLAGS ADDED TO MOTION VALUES ALREADY WRITTEN ({len(todo)} rows; "
            "data/known_within_100ly/kinematics/write.py renote). No value changed: notes, 'Kinematics source' and "
            "Distance notes only.",
        "Decided by the owner on 2026-10-09, from the research ledger's open questions:",
        "  WEAK on RVs from DESI DR1 MWS (RVSpecFit): batch K017 found it 3-6 km/s high against HIRES/NIRSPEC for "
        "late-M dwarfs (GJ 10174, GJ 11775), so its 0.1-0.3 km/s formal errors understate a systematic. Values kept "
        "as published.",
        "  WEAK on RVs from Hsu et al. 2026 (arXiv:2609.28746, JWST NIRSpec G395H): K028/K029 found them 5-7 km/s "
        "low against high-resolution benchmarks (GJ 12260, GJ 12049 B, GJ 12668). Values kept as published, with the "
        "paper's +/-5 km/s systematic.",
        "  DOUBTFUL MEMBERSHIP where Gaia DR3's astrometric fidelity_v2 < 0.5 (Rybizki et al. 2022, MNRAS 510, 2597: "
        "a neural-network classifier of spurious astrometric solutions; GAVO DC table gedr3spur.main, queried "
        "2026-10-09, cached in kinematics/cat/fidelity.json). Mostly anonymous G 19-20.5 sources toward the bulge "
        "(RA 255-300), whose large parallaxes are likely spurious, so such a row may lie far beyond 100 ly. Flagged "
        "in 'Kinematics source' (shown in the viewer's info panel), in the motion notes, and in a note on Distance "
        "(ly). Rows are kept, not removed. No plotted row fails the cut.",
        "  New flags by kind: " + ", ".join(f"{k} {v}" for k, v in n_flag.items()) + "."])
    run["title"] = gs.rename_workbook(None, gs.versioned_title())
    run["state"], run["finished"] = "done", now()
    save(WRITE_LOG, log)
    gs.invalidate_cache(sid)
    print("done:", run["title"], gs.spreadsheet_url(sid))


def main():
    mode = (sys.argv[1:] or ["plan"])[0]
    assert mode in ("plan", "bulk", "wave", "withdraw", "renote", "renote-plan"), mode
    if mode == "withdraw":
        return withdraw()
    if mode.startswith("renote"):
        return renote(dry=mode == "renote-plan")
    log = load(WRITE_LOG, {"runs": []})
    if mode == "bulk" and any(r["kind"] == "bulk" and r["state"] == "done" for r in log["runs"]):
        raise SystemExit("The bulk pass is already written. Use 'wave' for research results.")
    if mode == "wave" and not any(r["kind"] == "bulk" and r["state"] == "done" for r in log["runs"]):
        raise SystemExit("Run 'bulk' first.")
    merged = load(MERGED)
    assert merged, "run merge.py first"
    plan = merged["rows"]
    if mode == "wave":     # a research wave writes only rows an agent contributed to
        from merge import agent_values
        contributed = agent_values()
        plan = {k: p for k, p in plan.items() if k in contributed}
    gs, sid, api = sheets()
    h, rows = read_known(api, sid)
    col, todo, skipped, missing = planned_now(plan, h, rows, mode)
    counts = Counter(hd for it in todo.values() for hd in it["cells"] if not hd.startswith("__"))
    print(f"{mode}: {len(todo)} rows to write; cells " + ", ".join(f"{k.split(' (')[0]} {v}" for k, v in counts.items()))
    print(f"  already filled on the sheet (left alone): {dict(skipped) or 'none'}; plan rows not found live: "
          f"{len(missing)} {missing[:5]}")
    if mode == "plan":
        for n in sorted(todo)[:3]:
            print(f"  row {n} {todo[n]['key']}: " + "; ".join(f"{k.split(' (')[0]}={c.get('value')}"
                                                         for k, c in todo[n]["cells"].items()))
        return
    pending = next((r for r in log["runs"] if r["state"] != "done"), None)
    run = pending or {"kind": mode, "started": now(), "state": "cells", "chunks": 0, "counts": {}, "rows": 0,
                      "agents": []}
    if not pending:
        log["runs"].append(run)
    if mode == "wave":
        run["agents"] = sorted(set(run["agents"]) | {contributed[it["key"]]["agent"] for it in todo.values()})
    save(WRITE_LOG, log)

    meta = api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]
    kid = next(s["properties"]["sheetId"] for s in meta if s["properties"]["title"] == KN)
    colour = {"orange": gs.INFERRED_BORDER, "pink": gs.WIKIPEDIA_BORDER}
    wiki_entries = []
    order = sorted(todo)
    i = 0
    while i < len(order):
        r0 = order[i]
        chunk = {}
        while i < len(order) and order[i] < r0 + CHUNK_ROWS:
            chunk[order[i]] = todo[order[i]]
            i += 1
        r1 = max(chunk)
        verify_chunk(api, sid, col, len(h), r0, r1, chunk)
        reqs, borders = [], []
        for n, item in chunk.items():
            for hd, c in item["cells"].items():
                if hd == "__rv_note":
                    reqs.append(cell_request(kid, n, col[H_RV], c))
                    continue
                reqs.append(cell_request(kid, n, col[hd], c))
                if c.get("mark") in colour:
                    borders.append(border_request(gs, kid, n, col[hd], colour[c["mark"]]))
                if c.get("wiki"):
                    w = c["wiki"]
                    wiki_entries.append([KN, n, f"{letter(col[hd])}{n}", f"{item['key'].split('|')[0]} -- {hd}",
                                         c["value"], w.get("wikipedia_page", ""), w["wikipedia_url"],
                                         w["cited_source"], w["cited_url"], w.get("cross_check", ""), TODAY])
        api.batchUpdate(spreadsheetId=sid, body={"requests": reqs + borders}).execute()
        run["chunks"] += 1
        run["rows"] += len(chunk)
        for it in chunk.values():
            for hd in it["cells"]:
                if not hd.startswith("__"):
                    run["counts"][hd] = run["counts"].get(hd, 0) + 1
        save(WRITE_LOG, log)
        print(f"  chunk rows {r0}-{r1}: {len(chunk)} rows, {len(reqs)} cells, {len(borders)} boxes", flush=True)

    gs.invalidate_cache(sid)
    if wiki_entries:
        run["wikipedia_rows"] = wiki_rows(gs, api, sid, wiki_entries)
    shown = {hd: run["counts"].get(hd, 0) for hd in TARGET_COLS}
    from merge import BLENDED
    blended_n = sum(1 for it in todo.values() if it["key"] in BLENDED)
    run["sp_rows"] = append_sp(gs, api, sid, sp_block(mode, shown, run["rows"], run["agents"], len(wiki_entries),
                                                      blended_n))
    run["title"] = gs.rename_workbook(None, gs.versioned_title())
    run["state"], run["finished"] = "done", now()
    save(WRITE_LOG, log)
    gs.invalidate_cache(sid)
    phase = "P3_write" if mode == "bulk" else "P4_wave_write"
    mark(phase, "done", title=run["title"], rows=run["rows"], counts=run["counts"], agents=run["agents"])
    if mode == "wave":           # every finished batch's results are now on the sheet, found or not
        from common import PROGRESS, progress
        p = progress()
        for b, s in p["batches"].items():
            if s.get("state") in ("done", "partial") and not s.get("written"):
                s["written"] = run["title"]
        save(PROGRESS, p)
        import ledger
        ledger.regenerate()
    print("done:", run["title"], gs.spreadsheet_url(sid))


if __name__ == "__main__":
    main()
