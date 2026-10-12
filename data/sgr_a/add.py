# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Append plan.json's rows that the Sgr A* S-stars tab does not hold yet -- the second writer, after build.py.

    python add.py            what it would do; touches nothing
    python add.py write      append the rows, box and note their inferred cells, record it on Sources & Provenance,
                             rename

10 Oct 2026: S301 (GRAVITY+ 2026), von Fellenberg et al. 2022's S5, R1, R14, R30, R70 and S72, and the dusty objects
G1 and G2 (research/D.json).  Every row already on the tab must read back exactly as plan.json has it, or nothing is
written: the plan is the record of the tab, and a row edited by hand since would be silently disowned.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build  # noqa: E402
from build import GREY_RULE, SP, TAB, TODAY, append_sp, letter, now, q, rng, sheets  # noqa: E402

PLAN = HERE / "plan.json"
LOG = HERE / "write_log_20261010.json"


def same(x, y):
    return x == y or (isinstance(x, (int, float)) and isinstance(y, (int, float)) and abs(x - y) < 1e-9)


def sp_lines(new_rows, n_orange):
    names = ", ".join(r[0] for r in new_rows)
    return [
        "",
        f"{TODAY}: SGR A* S-STARS TAB: {len(new_rows)} ROWS ADDED (data/sgr_a/add.py, log write_log_20261010.json).",
        f"Rows: {names}. Research: data/sgr_a/research/D.json (one research agent; every orbit checked against the "
        "paper's own table before writing).",
        "S301: GRAVITY+ Collaboration 2026 (Nature 657, 359, 2026Natur.657..359A), Extended Data Table 2, the first of "
        "two solutions: no radial velocity yet, so the orbit's orientation is two-fold (the other is in the Ascending "
        "node cell's note). Class F1.5 and K 19.3 from the paper; its mass 1.3 Msun is the middle of the paper's "
        "1.1-1.5 (orange).",
        "S5, R1, R14, R30, R70, S72: von Fellenberg et al. 2022 (ApJ 932, L6, 2022ApJ...932L...6V), Table 4. The paper "
        "states no R0, so a in AU uses GRAVITY 2022's 8277 pc (orange); its periods agree with sqrt(a^3/M) at that "
        "distance. Classes and K via SIMBAD (Paumard et al. 2006; Schoedel et al. 2009). SIMBAD splits R70 (E54 vs "
        "S4-36) and S72 (S72 vs E18/W11): the SIMBAD main_id cell's note says so, and S72's class and K hold only "
        "if von Fellenberg's identification is right.",
        "G1, G2: Object type 'Dusty object'. Orbits from Gillessen et al. 2026 (A&A 707, A79, 2026A&A...707A..79G), "
        "Table B.1, individual fits with a drag force; three groups agree on the orbits, not on whether they are gas "
        "clouds or dust-enshrouded stars. No period is published: P = sqrt(a^3/M) with the fit's own M and R0 (orange), "
        "and the drag means the cloud does not follow it exactly. G2's K and SED mass (0.4 Msun, as a young star): "
        "Peisker et al. 2024 (2024A&A...686A.235P).",
        "Masses inferred from K (S5, R1, S72): the early-type dwarf relation above (+0.06 dex, 0.075 dex rms, valid "
        "M_K -3.2..+1); R14, R30, R70 are brighter than any dwarf and left blank. Motion columns: from each orbit at "
        f"2026.77, as before. Orange cells added: {n_orange}.",
    ]


def main():
    write = "write" in sys.argv[1:]
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    headers, rows = plan["headers"], plan["rows"]
    col = {h: i for i, h in enumerate(headers)}
    ncols = len(headers)
    gs, sid, api = sheets()
    meta = {s["properties"]["title"]: s["properties"] for s in
            api.get(spreadsheetId=sid, fields="sheets.properties").execute()["sheets"]}
    props = meta[TAB]
    tid, have_rows = props["sheetId"], props["gridProperties"]["rowCount"]
    last = f"{letter(ncols - 1)}{have_rows}"
    live = api.values().get(spreadsheetId=sid, range=f"{q(TAB)}!A1:{last}",
                            valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
    live = [list(r) + [""] * (ncols - len(r)) for r in live]
    assert live[0] == headers, "the tab's header row is not plan.json's"
    on_tab = [r[0] for r in live[1:]]
    by_name = {r[0]: r for r in rows}
    for r in live[1:]:
        w = by_name.get(r[0])
        assert w is not None, f"{r[0]} is on the tab but not in plan.json"
        bad = [headers[j] for j, (x, y) in enumerate(zip(r, w)) if not same(x, y)]
        assert not bad, f"{r[0]} on the tab differs from plan.json in {bad[:5]}"
    new = [r for r in rows if r[0] not in on_tab]
    assert [r[0] for r in rows[:len(on_tab)]] == on_tab and new == rows[len(on_tab):], \
        "the new rows are not plan.json's tail"
    names = {r[0] for r in new}
    inferred = {k: n for k, n in plan["inferred"].items() if k.split("|", 1)[0] in names}
    notes = {k: n for k, n in plan["notes"].items() if k.split("|", 1)[0] in names}
    print(f"{TAB}: {len(on_tab)} rows match plan.json; {len(new)} to append ({', '.join(r[0] for r in new)}); "
          f"{len(inferred)} orange cells, {len(notes)} other notes")
    if not write or not new:
        return

    start, end = have_rows + 1, have_rows + len(new)
    api.batchUpdate(spreadsheetId=sid, body={"requests": [{"appendDimension": {
        "sheetId": tid, "dimension": "ROWS", "length": len(new)}}]}).execute()
    gs.invalidate_cache(sid)
    span = f"{q(TAB)}!A{start}:{letter(ncols - 1)}{end}"
    gs.update_cells(sid, {span: new}, expect={f"{q(TAB)}!A{start}": "", f"{q(TAB)}!A{end}": "",
                                              f"{q(TAB)}!A{have_rows}": on_tab[-1]})
    grey = {"style": "SOLID", "color": gs._hex_to_color(GREY_RULE)}
    api.batchUpdate(spreadsheetId=sid, body={"requests": [
        {"updateBorders": {"range": rng(tid, start - 1, end, 0, ncols), "top": grey, "bottom": grey, "left": grey,
                           "right": grey, "innerHorizontal": grey, "innerVertical": grey}},
        {"repeatCell": {"range": rng(tid, start - 1, end, 0, ncols), "cell": {"userEnteredFormat": {
            "verticalAlignment": "TOP"}}, "fields": "userEnteredFormat.verticalAlignment"}},
        {"setBasicFilter": {"filter": {"range": rng(tid, 0, end, 0, ncols)}}},
    ]}).execute()

    # Orange boxes and notes, by name: column A re-read.
    col_a = gs.read_cells(sid, [f"{q(TAB)}!A2:A{end}"])[f"{q(TAB)}!A2:A{end}"]
    at = {r[0]: i + 2 for i, r in enumerate(col_a)}
    assert [at[r[0]] for r in new] == list(range(start, end + 1)), "column A is not the plan's order"

    def cell(key):
        name, h = key.split("|", 1)
        return f"{q(TAB)}!{letter(col[h])}{at[name]}"
    orange = [cell(k) for k in inferred]
    for s in range(0, len(orange), 200):
        gs.set_border(sid, orange[s:s + 200], gs.INFERRED_BORDER)
    all_notes = {cell(k): n for k, n in inferred.items()}
    all_notes.update({cell(k): n for k, n in notes.items()})
    gs.set_note(sid, all_notes)

    # read back: the new values, and the orange boxes by name
    back = api.values().get(spreadsheetId=sid, range=span, valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
    for b, w in zip(back, new):
        b = list(b) + [""] * (ncols - len(b))
        bad = [headers[j] for j, (x, y) in enumerate(zip(b, w)) if not same(x, y)]
        assert not bad, f"{w[0]}: wrote and read back differ in {bad[:5]}"
    borders = gs.get_borders(sid, span)
    boxed = {k.split("!")[-1] for k, b in borders.items()
             if all("FF9900" in str((b.get(s) or (None,))[0] or "").upper() for s in ("top", "bottom", "left", "right"))}
    want = {c.split("!")[-1] for c in orange}
    assert want <= boxed, f"{len(want - boxed)} inferred cells are not boxed: {sorted(want - boxed)[:5]}"

    sp = append_sp(gs, api, sid, sp_lines(new, len(orange)))
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(sid)
    log = {"at": now(), "tab": TAB, "rows_added": [r[0] for r in new], "tab_rows": [start, end],
           "orange": len(orange), "notes": len(all_notes), "boxed_read_back": len(want & boxed), "sp_block": sp,
           "title": title}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log, ensure_ascii=False))


if __name__ == "__main__":
    main()
