# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Apply researched star-count specs to the sheet: the rest of the audit after write_counts.py.

    python apply_specs.py specs/*.json           plan: print every write; touches nothing
    python apply_specs.py specs/*.json write     write, re-border, note, provenance, legend, rename

A spec (one per system; the format is specs/SCHEMA.md) says what the literature check found: the new star count,
the Multi-stars rows to add (only the companions -- a host new to Multi-stars is built from its Systems row), the
cells that are inferred (orange, with their notes), the new 'System stars' text, a note for the 'Stars in system'
cells and a Sources & Provenance paragraph. Actions: new_system, add_rows, count_only, no_change,
move_from_planetless, and systems_only (a system kept off Multi-stars whose Systems count and text change: tet Cyg,
whose rows stay on Planetless 4+ Stars).

Everything write_counts.py does, generalised: rows found by name, every value write guarded by `expect`, a pasted
row re-ruled cell by cell and its notes cleared, then EVERY coloured box on Multi-stars redrawn by name (a re-ruled
cell strips the shared edge off its neighbour's box), the basic filter extended over the new rows, and a new system
placed where the tab's sort (stars descending, then distance) would put it.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data" / "four_plus_stars"))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)
from build import GREY_RULE  # noqa: E402  (this tab's plain rule; gs.PLAIN_RULE is black)

ARGS = [a for a in sys.argv[1:] if a != "write"]
PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
MS, SY, PL, PN = "Multi-stars within 100 ly", "Systems within 100 ly", "Planetless 4+ Stars", "Planets within 100 ly"
SP, LG = "Sources & Provenance", "Legend & Notes"
LOG = HERE / "apply_specs_log.json"
DATE = "6 Oct 2026"
ORANGE, PINK = "FF9900", "FF3399"
TEMPLATE_TYPED, TEMPLATE_PLANET_HOST = "psi1 Dra A", "psi1 Dra B"   # P (luminosity) typed / a Planets lookup
ACTIONS = {"new_system", "add_rows", "count_only", "no_change", "move_from_planetless", "systems_only"}
SYSTEM_LEVEL = ("Distance (ly)", "Confirmed planets", "Planet masses (M-earth)", "Mass type", "Planet-host star",
                "Planet-host class", "Primary mass (M-sun)")
# Systems column -> Multi-stars column, for a host row built from the Systems tab.
HOST_FROM_SYSTEMS = {
    "Nickname (IAU)": "Nickname (IAU)", "Host mass (M-sun)": "Mass (M-sun)", "Stellar Class": "Stellar Class",
    "Class (sort key)": "Class (sort key)", "Effective temp (K)": "Effective temp (K)", "Age (Gyr)": "Age (Gyr)",
    "Metallicity [Fe/H]": "Metallicity [Fe/H]", "Host luminosity (L-sun)": "Luminosity (L-sun)",
    "Radial velocity (km/s)": "Radial velocity (km/s)",
    "Proper motion in RA, μα·cos δ (mas/yr)": "Proper motion in RA, μα·cos δ (mas/yr)",
    "Proper motion in Dec, μδ (mas/yr)": "Proper motion in Dec, μδ (mas/yr)",
    "Total proper motion, μ (arcsec/yr)": "Total proper motion, μ (arcsec/yr)",
    "Space velocity (km/s)": "Space velocity (km/s)", "Kinematics source": "Kinematics source",
    "Gaia DR3 source_id": "Gaia DR3 source_id",
}


def values(tab, how="UNFORMATTED_VALUE"):
    return API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:DZ3000", valueRenderOption=how
                            ).execute().get("values", [])


def cell(row, c):
    return row[c] if c < len(row) else ""


class Tab:
    """A tab's live values, re-read on demand, with lookups by name."""

    def __init__(self, title, key="Star (component)"):
        self.title, self.key = title, key
        self.reload()

    def reload(self):
        self.data = values(self.title)
        self.col = {h: i for i, h in enumerate(self.data[0])}

    def get(self, r, h):
        return cell(self.data[r - 1], self.col[h])

    def rows_of(self, system):
        return [i + 1 for i, r in enumerate(self.data) if i and r and r[0] == system]

    def row_of(self, name):
        rr = [i + 1 for i, r in enumerate(self.data) if i and cell(r, self.col[self.key]) == name]
        assert len(rr) == 1, (self.title, name, rr)
        return rr[0]

    def has(self, name):
        return any(i and cell(r, self.col[self.key]) == name for i, r in enumerate(self.data))

    def last(self):
        return max(i + 1 for i, r in enumerate(self.data) if r and r[0])

    def a1(self, h, r):
        return f"{q(self.title)}!{letter(self.col[h])}{r}"


def notes_at(a1_cells):
    """{A1: existing note} for single cells, so a new note is appended rather than clobbering one."""
    out = {}
    for a1 in a1_cells:
        d = API.get(spreadsheetId=SID, ranges=[a1], includeGridData=True,
                    fields="sheets(data(rowData(values(note))))").execute()["sheets"][0]["data"][0]
        out[a1] = (d.get("rowData") or [{}])[0].get("values", [{}])[0].get("note", "")
    return out


def load_specs():
    specs = []
    for p in ARGS:
        for s in json.loads(Path(p).read_text(encoding="utf-8")):
            s["_file"] = Path(p).name
            specs.append(s)
    names = [s["system"] for s in specs]
    assert len(set(names)) == len(names), "a system is in two specs"
    return specs


def check(specs, ms, sy, planet_hosts):
    """Every assumption the write rests on, before anything is written."""
    problems = []
    seen = set()
    for s in specs:
        name, act = s["system"], s["action"]
        if act not in ACTIONS:
            problems.append(f"{name}: unknown action {act!r}")
            continue
        sr = sy.rows_of(name)
        if len(sr) != 1:
            problems.append(f"{name}: {len(sr)} Systems rows")
            continue
        have = sy.get(sr[0], "Stars in system")
        if have != s["old_count"]:
            problems.append(f"{name}: Systems says {have} stars, spec says old_count {s['old_count']}")
        on_ms = bool(ms.rows_of(name))
        if act in ("new_system", "move_from_planetless") and on_ms:
            problems.append(f"{name}: {act} but already on Multi-stars")
        if act in ("add_rows", "count_only") and not on_ms:
            problems.append(f"{name}: {act} but not on Multi-stars")
        if act == "no_change" and s["new_count"] != s["old_count"]:
            problems.append(f"{name}: no_change but the count changes")
        for row in s.get("rows", []):
            v = row["values"]
            comp = v.get("Star (component)")
            if not comp:
                problems.append(f"{name}: a row with no Star (component)")
                continue
            if ms.has(comp) or comp in seen:
                problems.append(f"{name}: {comp} already exists")
            seen.add(comp)
            for h in list(v) + list(row.get("orange", {})) + list(row.get("notes", {})):
                if h not in ms.col:
                    problems.append(f"{name}/{comp}: no Multi-stars column {h!r}")
            for h in SYSTEM_LEVEL + ("System / Host", "Stars in system"):
                if h in v:
                    problems.append(f"{name}/{comp}: {h!r} is the writer's to fill")
            if "Gaia DR3 source_id" in v and v["Gaia DR3 source_id"] not in ("", None) \
                    and not isinstance(v["Gaia DR3 source_id"], str):
                problems.append(f"{name}/{comp}: Gaia DR3 source_id must be a string")
        for h in list(s.get("host_overrides", {})) + list(s.get("host_orange", {})) + list(s.get("host_notes", {})):
            if h not in ms.col:
                problems.append(f"{name}: host override, no column {h!r}")
        if act == "systems_only" and (on_ms or s.get("rows")):
            problems.append(f"{name}: systems_only, but it has Multi-stars rows or rows to add")
        if act in ("new_system", "add_rows") and not s.get("rows"):
            problems.append(f"{name}: {act} with no rows")
        if act != "no_change" and not s.get("systems_text"):
            problems.append(f"{name}: no systems_text")
    return problems


def host_row(spec, sy, planet_hosts):
    """A host new to Multi-stars, from its Systems row: what Multi-stars' own host rows hold."""
    r = sy.rows_of(spec["system"])[0]
    v = {mh: sy.get(r, sh) for sh, mh in HOST_FROM_SYSTEMS.items()}
    v["Gaia DR3 source_id"] = str(v["Gaia DR3 source_id"]) if v["Gaia DR3 source_id"] not in ("", None) else ""
    name = spec["system"]
    v["Star (component)"] = name
    role = "host, planet host" if name in planet_hosts else "host"
    v["Role in system"] = role
    v["Star data source"] = f"host: as the Systems tab's row for {name}"
    v.update(spec.get("host_overrides", {}))
    return v


def system_level(spec, ms, sy):
    """The columns every row of a system shares: from its existing Multi-stars host row, else from Systems."""
    rows = ms.rows_of(spec["system"])
    if rows:
        r = rows[0]
        return {h: ms.get(r, h) for h in SYSTEM_LEVEL}
    r = sy.rows_of(spec["system"])[0]
    out = {h: sy.get(r, h) for h in SYSTEM_LEVEL if h in sy.col and h != "Primary mass (M-sun)"}
    out["Primary mass (M-sun)"] = sy.get(r, "Host mass (M-sun)")
    return out


def anchor_for(spec, ms, sy):
    """The component after which a new system's block goes: the end of the last system that sorts before it."""
    n = spec["new_count"]
    dist = float(sy.get(sy.rows_of(spec["system"])[0], "Distance (ly)"))
    # The tab is only roughly in order (a count changed in place stays where it was), so prefer the last system
    # of the same count that is no farther; failing that, the last system with more stars.
    same = more = None
    for r in range(2, ms.last() + 1):
        stars, d = ms.get(r, "Stars in system"), ms.get(r, "Distance (ly)")
        try:
            if stars == n and float(d) <= dist:
                same = r
            elif stars > n:
                more = r
        except (TypeError, ValueError):
            continue
    best = same or more
    if best is None:
        return None
    system = ms.data[best - 1][0]
    return ms.get(ms.rows_of(system)[-1], "Star (component)")


def plan_rows(specs, ms, sy, planet_hosts):
    """[(spec, after component or None for row 2, template, values, orange, notes)] in write order."""
    out = []
    for s in specs:
        if s["action"] in ("count_only", "no_change", "systems_only"):
            continue
        common = dict(system_level(s, ms, sy), **{"System / Host": s["system"], "Stars in system": s["new_count"]})
        rows = []
        if s["action"] in ("new_system", "move_from_planetless"):
            # A spec that carries its own host row (tet Cyg's, moved whole) gets no second one from Systems.
            if not any(r["values"]["Star (component)"] == s["system"] for r in s.get("rows", [])):
                h = host_row(s, sy, planet_hosts)
                # host_orange: a host value the spec infers in place of the Systems one (a pair's share of a
                # combined mass), with its note.
                rows.append(({**common, **h}, s.get("host_orange", {}), s.get("host_notes", {})))
            after = anchor_for(s, ms, sy)
        else:
            after = None
        for row in s.get("rows", []):
            rows.append(({**common, **row["values"]}, row.get("orange", {}), row.get("notes", {})))
        prev = after
        for vals, orange, notes in rows:
            comp = vals["Star (component)"]
            want = None
            if s["action"] == "add_rows":
                want = next((r.get("after") for r in s["rows"] if r["values"]["Star (component)"] == comp), None)
            where = want or prev
            tmpl = TEMPLATE_PLANET_HOST if comp in planet_hosts else TEMPLATE_TYPED
            out.append((s, where, tmpl, vals, orange, notes))
            prev = comp
    return out


def main():
    specs = load_specs()
    ms, sy = Tab(MS), Tab(SY, key="System / Host")
    pn = Tab(PN, key="Planet")
    planet_hosts = {pn.get(r, "Planet-host star") for r in range(2, pn.last() + 1)}
    problems = check(specs, ms, sy, planet_hosts)
    plan = plan_rows(specs, ms, sy, planet_hosts) if not problems else []
    sp, lg = sp_lines(specs), legend_lines(specs)

    if PLAN or problems:
        for p in problems:
            print("PROBLEM:", p)
        if problems:
            sys.exit(1)
        for s in specs:
            print(f"\n== {s['system']} [{s['_file']}]: {s['action']}, {s['old_count']} -> {s['new_count']}")
            for f in s.get("flags", []):
                print("   FLAG:", f)
        print(f"\n{len(plan)} Multi-stars rows to insert:")
        for s, where, tmpl, vals, orange, notes in plan:
            print(f"  {vals['Star (component)']!r} after {where!r} (template {tmpl}); orange: {sorted(orange)}")
        print("\nSources & Provenance:\n" + "\n".join(x[:300] for x in sp))
        print("\nLegend & Notes:\n" + "\n".join(lg))
        return

    write(specs, plan, ms, sy, sp, lg)


def write(specs, plan, ms, sy, sp, lg):
    props = {s["properties"]["title"]: s["properties"] for s in
             API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}
    mid = props[MS]["sheetId"]
    ncols = len(ms.data[0])
    comp_col = ms.col["Star (component)"]
    log = {"inserted": [], "planetless_deleted": [], "counts": {}}

    # Every coloured box on the tab, by name, before anything moves: redrawn at the end.
    # Read in chunks: the whole tab's grid data in one response trips httplib2's decompression-ratio guard.
    boxes, found = {}, {}
    for r0 in range(2, ms.last() + 1, 30):
        found.update(gs.get_borders(SID, f"{q(MS)}!A{r0}:{letter(ncols - 1)}{min(r0 + 29, ms.last())}"))
    for a1, sides in found.items():
        cols = {c for c, _ in sides.values()}
        if len(cols) == 1 and len(sides) == 4 and (col := cols.pop()) in (ORANGE, PINK):
            c = "".join(ch for ch in a1 if ch.isalpha())
            r = int("".join(ch for ch in a1 if ch.isdigit()))
            boxes[(ms.get(r, "Star (component)"), next(h for h, i in ms.col.items() if letter(i) == c))] = col
    orange_notes, plain_notes = {}, {}

    for s, where, tmpl, vals, orange, notes in plan:
        ms.reload()
        at = ms.row_of(where) if where else 1
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"insertDimension": {"range": {
            "sheetId": mid, "dimension": "ROWS", "startIndex": at, "endIndex": at + 1},
            "inheritFromBefore": at > 1}}]}).execute()
        ms.reload()
        src, new = ms.row_of(tmpl), at + 1
        API.batchUpdate(spreadsheetId=SID, body={"requests": [
            {"copyPaste": {"source": {"sheetId": mid, "startRowIndex": src - 1, "endRowIndex": src,
                                      "startColumnIndex": 0, "endColumnIndex": ncols},
                           "destination": {"sheetId": mid, "startRowIndex": new - 1, "endRowIndex": new,
                                           "startColumnIndex": 0, "endColumnIndex": ncols},
                           "pasteType": "PASTE_NORMAL"}},
            {"updateCells": {"range": {"sheetId": mid, "startRowIndex": new - 1, "endRowIndex": new,
                                       "startColumnIndex": 0, "endColumnIndex": ncols},
                             "rows": [{"values": [{} for _ in range(ncols)]}], "fields": "note"}}]}).execute()
        gs.invalidate_cache(SID)
        formulas = API.values().get(spreadsheetId=SID, range=f"{q(MS)}!A{new}:{letter(ncols - 1)}{new}",
                                    valueRenderOption="FORMULA").execute()["values"][0]
        upd = {}
        for h, c in ms.col.items():
            if str(cell(formulas, c)).startswith("="):
                continue                               # keep the copied formula
            v = vals.get(h, "")
            upd[f"{q(MS)}!{letter(c)}{new}"] = "" if v is None else v
        gs.update_cells(SID, upd, expect={f"{q(MS)}!{letter(comp_col)}{new}": tmpl})
        comp = vals["Star (component)"]
        log["inserted"].append(comp)
        for h, n in orange.items():
            boxes[(comp, h)] = ORANGE
            orange_notes[(comp, h)] = n
        for h, n in notes.items():
            plain_notes[(comp, h)] = n

    # Re-rule every pasted cell to the tab's plain rule, then redraw every box by name.
    ms.reload()
    new_rows = [ms.row_of(n) for n in log["inserted"]]
    cells = [f"{q(MS)}!{letter(c)}{r}" for r in new_rows for c in range(ncols)]
    for i in range(0, len(cells), 400):
        gs.set_border(SID, cells[i:i + 400], GREY_RULE, style="SOLID")
    for colour in sorted(set(boxes.values())):
        want = [f"{q(MS)}!{letter(ms.col[h])}{ms.row_of(c)}" for (c, h), col in boxes.items() if col == colour]
        for i in range(0, len(want), 400):
            gs.set_border(SID, want[i:i + 400], "FF" + colour)
    gs.set_note(SID, {f"{q(MS)}!{letter(ms.col[h])}{ms.row_of(c)}": n
                      for (c, h), n in {**plain_notes, **orange_notes}.items()})

    # Stars in system: every existing row of a changed system, on Multi-stars and Systems; then the notes.
    upd, exp = {}, {}
    for s in specs:
        if s["new_count"] == s["old_count"]:
            continue
        for r in ms.rows_of(s["system"]):
            if ms.get(r, "Star (component)") in log["inserted"]:
                continue
            upd[ms.a1("Stars in system", r)] = s["new_count"]
            exp[ms.a1("Stars in system", r)] = s["old_count"]
        r = sy.rows_of(s["system"])[0]
        upd[sy.a1("Stars in system", r)] = s["new_count"]
        exp[sy.a1("Stars in system", r)] = s["old_count"]
        exp[sy.a1("System / Host", r)] = s["system"]
        log["counts"][s["system"]] = [s["old_count"], s["new_count"]]
    for s in specs:
        if s["action"] == "no_change" or not s.get("systems_text"):
            continue
        r = sy.rows_of(s["system"])[0]
        upd[sy.a1("System stars", r)] = s["systems_text"]
        exp[sy.a1("System stars", r)] = sy.get(r, "System stars")
    if upd:
        gs.update_cells(SID, upd, expect=exp)
    targets = {}
    for s in specs:
        if not s.get("stars_note"):
            continue
        rows = ms.rows_of(s["system"])
        if rows:
            targets[ms.a1("Stars in system", rows[0])] = s["stars_note"]
        targets[sy.a1("Stars in system", sy.rows_of(s["system"])[0])] = s["stars_note"]
    old = notes_at(targets)
    gs.set_note(SID, {a1: (old[a1] + "\n\n" + n) if old[a1] else n for a1, n in targets.items()})

    end = ms.last()
    f = API.get(spreadsheetId=SID, fields="sheets(properties(title),basicFilter)").execute()["sheets"]
    flt = next(x for x in f if x["properties"]["title"] == MS)["basicFilter"]
    if flt["range"].get("endRowIndex") != end:
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"setBasicFilter": {
            "filter": dict(flt, range=dict(flt["range"], endRowIndex=end))}}]}).execute()
    log["filter_end_row"] = end

    # Planetless: delete what moved, bottom-up, each block checked by name first.
    for s in specs:
        if s["action"] != "move_from_planetless":
            continue
        pl = Tab(PL)
        rows = sorted(pl.row_of(c) for c in s["planetless_components"])
        left = [r for r in pl.rows_of(pl.data[rows[0] - 1][0]) if r not in rows]
        assert not left, f"{s['system']}: Planetless rows of the system not in the spec: {left}"
        assert rows == list(range(rows[0], rows[-1] + 1)), rows
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"deleteDimension": {"range": {
            "sheetId": props[PL]["sheetId"], "dimension": "ROWS", "startIndex": rows[0] - 1,
            "endIndex": rows[-1]}}}]}).execute()
        gs.invalidate_cache(SID)
        log["planetless_deleted"] += s["planetless_components"]

    # Sources & Provenance (grow the grid, never values().append()), then Legend & Notes.
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    sp_end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{sp_end}"])[f"{q(SP)}!A{sp_end}"][0][0].strip()
    sp0, sp1 = sp_end + 1, sp_end + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{sp0}:A{sp1}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (sp0, sp1)})
    lv = API.values().get(spreadsheetId=SID, range=f"{q(LG)}!A1:A3000").execute().get("values", [])
    lg0 = len(lv) + 2
    lg1 = lg0 + len(lg) - 1
    gs.update_cells(SID, {f"{q(LG)}!A{lg0}:A{lg1}": [[x] for x in lg]},
                    expect={f"{q(LG)}!A{lg0}": "", f"{q(LG)}!A{lg1}": ""})

    log.update(sp_rows=[sp0, sp1], legend_rows=[lg0, lg1], boxes_redrawn=len(boxes),
               title=gs.rename_workbook(None, gs.versioned_title()))
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps({k: v for k, v in log.items() if k != "inserted"}, ensure_ascii=False),
          f"\ninserted {len(log['inserted'])} rows")


def sp_lines(specs):
    changed = [s for s in specs if s["new_count"] != s["old_count"]]
    out = ["", f"STAR COUNTS OF PLANET HOSTS, THE REST OF THE AUDIT, {DATE.upper()}",
           "  METHOD as for the first four systems (the entry 'STAR COUNTS OF PLANET HOSTS, FIRST FOUR SYSTEMS' above): "
           "Multiple Star Catalog and Gaia DR3 co-moving matches, then a literature check of every companion and a "
           "search of the planet tabs for duplicates. Research by Claude; the owner's rules: brown dwarfs count as "
           "stars, MSC '?' companions are counted and drawn hollow at an inferred ('assumed') separation, "
           "candidate-only hosts go onto Multi-stars with the candidate named in 'Role in system'. "
           f"{len(changed)} counts changed; scripts in the repo at data/star_counts/apply_specs.py."]
    for s in specs:
        out.append(f"  {s['system']} ({s['old_count']} -> {s['new_count']}): {s.get('sp_paragraph', '').strip()}")
    return out


def legend_lines(specs):
    changed = [f"{s['system']} {s['old_count']}->{s['new_count']}" for s in specs if s["new_count"] != s["old_count"]]
    same = [s["system"] for s in specs if s["new_count"] == s["old_count"]]
    return [
        f"STAR COUNTS OF PLANET HOSTS -- {DATE.upper()} (the rest of the audit)",
        "Star counts corrected against the Multiple Star Catalog, Gaia DR3 and the literature: " + "; ".join(changed)
        + (". Checked and left as they were: " + ", ".join(same) if same else "") + ". Method and citations on "
        f"Sources & Provenance under 'STAR COUNTS OF PLANET HOSTS, THE REST OF THE AUDIT, {DATE.upper()}'.",
    ]


if __name__ == "__main__":
    main()
