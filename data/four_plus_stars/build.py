# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create the "4+ Stars only" tab: systems of four or more stars within 100 ly, plus nu Sco (asked for by name).

    python build.py plan     print the rows and counts; touches nothing
    python build.py write    create the tab, write it, mark it, provenance, rename

Source: the Multiple Star Catalog (MSC; Tokovinin 2018, ApJS 235, 6; VizieR J/ApJS/235/6, Dec 2023 update),
pulled by fetch_msc.py into msc.json: every system with Nc >= 4 components and parallax >= 32.6156 mas.

The MSC describes a system as a tree of pairs ("subsystems"): Castor is ((Aa,Ab),(Ba,Bb)),((Ca,Cb),Cc), and its
outer orbits are between the BARYCENTRES of pairs, not between stars. Multi-stars' model -- each star placed from
another star by 'Separation from' -- cannot say "Castor C orbits the A+B pair". So this tab keeps Multi-stars'
columns and adds a row for every subsystem as well as every star, each node placed from its sibling in its parent
pair; see NEW_COLUMNS. The most massive star is the host, as on Multi-stars.
"""
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from hybrasil.data import google_sheets as gs  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402
from googleapiclient.http import HttpRequest  # noqa: E402

_execute = HttpRequest.execute


def _execute_with_retry(self, *a, **k):
    """The Sheets API allows 60 reads a minute; wait out a 429 rather than stop half-way."""
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
MS, FP, SP = "Multi-stars within 100 ly", "4+ Stars only", "Sources & Provenance"
LOG = HERE / "write_log.json"
PLAN = sys.argv[1:] == ["plan"]
GREY_RULE = "FFBFBFBF"
MSC = "MSC (Tokovinin 2018, ApJS 235, 6; VizieR J/ApJS/235/6, Dec 2023 update)"
LY_PER_MAS = 3261.563777       # distance (ly) = 3261.56 / parallax (mas)
# WDS 20013+3315 is a second, mis-keyed copy of GJ 4176/4177: both records give RA 315.3 deg (21h01m).
DROP = {"20013+3315": "duplicate of 21013+3315 (GJ 4176 + GJ 4177); its WDS code does not match its RA"}
BEYOND_100LY_OK = {"16120-1928"}     # nu Sco, asked for by name
IAU = {"07346+3153": "Castor", "05167+4600": "Capella", "13239+5456": "Mizar", "16120-1928": "Jabbah",
       "10084+1158": "Regulus", "14509-1603": "Zubenelgenubi", "08122+1739": "Tegmine",
       "11182+3132": "Alula Australis", "08592+4803": "Talitha"}

NEW_COLUMNS = [
    ("Node type", "'star', or 'subsystem' for a pair whose members are themselves stars or pairs"),
    ("MSC label", "the component label in the MSC: Aa, Ab, B, Cab ..."),
    ("Member of", "the pair (subsystem) this node belongs to, by name; blank for the two top-level nodes"),
    ("Hierarchy", "the whole system as nested pairs, the MSC's tree written out"),
    ("Hierarchy level", "1 for the two nodes of the outermost pair, 2 for their members, and so on"),
    ("Orbital period (d)", "period of the orbit this row's 'Separation from' describes"),
    ("Period basis", "'orbit' when a computed orbit gives it; otherwise the MSC's estimate from separation"),
    ("Inclination (deg)", "of that orbit, from the MSC orbit table, where a visual/astrometric orbit exists"),
    ("Ascending node (deg)", "position angle of the ascending node, same source"),
    ("Argument of periastron (deg)", "same source"),
    ("Separation (arcsec)", "the angular separation or semi-major axis as published, before conversion to au"),
    ("Detection (MSC)", "how the pair is known: visual orbit, spectroscopic, eclipsing, common proper motion ..."),
    ("Mass basis (MSC)", "how the MSC got the mass: published, from absolute magnitude, sum of a subsystem ..."),
    ("WDS code", "the system's Washington Double Star / MSC identifier"),
]

TYPE_CODES = [("S1", "spectroscopic orbit, single-lined"), ("S2", "spectroscopic orbit, double-lined"),
              ("E*", "eclipse-timing variation"), ("V", "visual orbit"), ("A", "astrometric orbit"),
              ("E", "eclipsing binary"), ("C", "common proper motion pair (> 3 arcsec)"),
              ("c", "wide, possibly common proper motion"), ("v", "close visual / interferometric pair"),
              ("a", "astrometric (perturbed motion suspected)"), ("s", "possibly spectroscopic"),
              ("o", "occultation binary"), ("e", "eclipsing, period unknown")]
CPM_QUALIFIERS = {"h": "hypothetical parallax", "r": "radial velocities", "p": "photometric distance or common "
                  "parallax", "m": "common proper motion"}
MASS_CODES = {"r": "published", "v": "estimated from absolute magnitude (MSC)",
              "a": "estimated from spectral type or B-V (MSC)", "s": "sum of the subsystem's masses (MSC)",
              "q": "from primary mass and SB2 mass ratio (MSC)", "m": "minimum mass, SB1 (MSC)",
              "k": "estimated from absolute K or H magnitude (MSC)"}
GREEK = {"alp": "alf", "alf": "alf", "bet": "bet", "gam": "gam", "del": "del", "eps": "eps", "zet": "zet",
         "eta": "eta", "tet": "tet", "iot": "iot", "kap": "kap", "lam": "lam", "mu": "mu", "nu": "nu", "ksi": "ksi",
         "omi": "omi", "pi": "pi", "rho": "rho", "sig": "sig", "tau": "tau", "ups": "ups", "phi": "phi",
         "chi": "chi", "psi": "psi", "ome": "ome"}


def q(t):
    return "'" + t.replace("'", "''") + "'"


def letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def decode_type(t):
    out = []
    for part in (t or "").split(","):
        part = part.strip()
        if not part:
            continue
        if part[0] == "X":
            out.append("optical (not physical)")
            continue
        for code, text in TYPE_CODES:
            if part.startswith(code):
                quals = [CPM_QUALIFIERS[c] for c in part[len(code):] if c in CPM_QUALIFIERS] \
                    if code in ("C", "c") else []
                out.append(text + (f" ({', '.join(quals)})" if quals else ""))
                break
        else:
            out.append(part)
    return "; ".join(out)


def system_name(oid):
    toks = [t.strip() for t in (oid or "").split(",") if t.strip()]
    for t in toks:                              # Bayer (Greek) or Flamsteed / Bayer letter, SIMBAD style
        if t.startswith("*"):
            m = re.match(r"^\*_?(\d*)([A-Za-z]+?)?_?0?(\d)?_?([A-Z][A-Za-z]{1,2})$", t)
            if m:
                flam, word, idx, con = m.groups()
                if word and word.lower() in GREEK:
                    return f"{GREEK[word.lower()]}{idx or ''} {con}"
                if word and len(word) == 1:
                    return f"{word} {con}"
                if flam:
                    return f"{flam} {con}"
    for prefix in ("GJ_", "HR_", "HD_"):
        for t in toks:
            if t.startswith(prefix):
                return re.sub(r"_?[A-D]{1,3}$", "", t).replace("_", " ")
    return toks[0].replace("V*_", "").replace("_", " ") if toks else ""


def sort_key(spt):
    m = re.match(r"^([OBAFGKMLT])(\d+(?:\.\d+)?)?", (spt or "").strip())
    if not m:
        return ""
    base = "OBAFGKMLT".index(m.group(1)) * 10
    return base + (float(m.group(2)) if m.group(2) else 0)


def days(per, unit):
    if per in (None, ""):
        return None
    return per * {"d": 1, "y": 365.25, "k": 365250.0, "M": 365.25e6}.get(unit or "d", 1)


def arcsec(sep, unit):
    if sep in (None, ""):
        return None
    return sep / 1000 if unit == "m" else sep if unit == '"' else None


def best_orbit(orbits, prim, sec):
    key = f"{prim},{sec}"
    cands = [o for o in orbits if re.sub(r"[.\s]", ",", o["Syst"] or "") == key]
    return max(cands, key=lambda o: sum(o[k] not in (None, "") for k in ("a", "Incl", "Node", "e", "LongP")),
               default=None)


def build_system(sid, rec):
    """The rows of one system: host first, then the tree in order. None if fewer than 4 physical stars."""
    nodes = [n for n in rec["systems"] if n["Parent"] != "X" and not (n["Type"] or "").startswith("X")]
    parents = {n["Parent"] for n in nodes}
    pair_of = {}                                   # label -> (pair record, 'Prim' | 'Sec')
    for n in nodes:
        pair_of[n["Prim"]] = (n, "Prim")
        pair_of[n["Sec"]] = (n, "Sec")
    own = {n["Prim"] + n["Sec"]: n for n in nodes}
    # a subsystem label (e.g. 'A', 'Cab') is the Parent of the pair record that splits it
    splits = {n["Parent"]: n for n in nodes if n["Parent"] not in ("*", "t")}
    root = [n for n in nodes if n["Parent"] == "*"]
    if len(root) != 1:
        return None, f"{len(root)} root pairs"
    root = root[0]
    leaves = [lab for lab in pair_of if lab not in splits]
    if len(leaves) < 4 and sid not in BEYOND_100LY_OK:
        return None, f"{len(leaves)} physical components"

    cat = rec["catalog"]
    main = max(cat, key=lambda c: c["Nc"] or 0)
    plx = main["plx"]
    name = system_name(main["OID"]) or main.get("SimbadName") or sid

    def tree(lab):
        s = splits.get(lab)
        return lab if s is None else f"({tree(s['Prim'])},{tree(s['Sec'])})"

    hierarchy = f"{tree(root['Prim'])},{tree(root['Sec'])}"

    def mass(lab):
        n, side = pair_of[lab]
        return (n["Mass1"], n["f_Mass1"], n["SpT1"]) if side == "Prim" else (n["Mass2"], n["f_Mass2"], n["SpT2"])

    order, level = [], {}

    def walk(lab, lv):
        order.append(lab)
        level[lab] = lv
        s = splits.get(lab)
        if s:
            walk(s["Prim"], lv + 1)
            walk(s["Sec"], lv + 1)

    walk(root["Prim"], 1)
    walk(root["Sec"], 1)
    host = max(leaves, key=lambda lab: (mass(lab)[0] or 0, -order.index(lab)))
    rows = []
    for lab in [host] + [x for x in order if x != host]:
        n, side = pair_of[lab]
        m, mcode, spt = mass(lab)
        is_star = lab in leaves
        spt = (spt or "").strip()
        comp = f"{name} {lab}"
        brown = is_star and m not in (None, "") and m < 0.075
        role = ("host (most massive star)" if lab == host else
                "brown dwarf" if brown else
                "white dwarf" if spt.startswith("D") else
                "star" if is_star else
                f"subsystem: {name} {splits[lab]['Prim']} + {name} {splits[lab]['Sec']}")
        r = {"System / Host": name, "Star (component)": comp, "Role in system": role,
             "Nickname (IAU)": IAU.get(sid, "") if lab == host else "",
             "Distance (ly)": round(LY_PER_MAS / plx, 2), "Stars in system": len(leaves),
             "Mass (M-sun)": m if m not in (None, "") else "",
             "Stellar Class": spt if is_star else "", "Class (sort key)": sort_key(spt) if is_star else "",
             "Star data source": f"{MSC}, WDS {sid}: class and mass (mass {MASS_CODES.get(mcode, mcode or 'n/a')})",
             "Primary mass (M-sun)": mass(host)[0],
             "Node type": "star" if is_star else "subsystem", "MSC label": lab,
             "Member of": "" if n["Parent"] == "*" else f"{name} {n['Parent']}",
             "Hierarchy": hierarchy, "Hierarchy level": level[lab],
             "Mass basis (MSC)": MASS_CODES.get(mcode, mcode or ""), "WDS code": sid}
        if side == "Sec":
            # this node holds the orbit of its pair: placed from the pair's primary
            o = best_orbit(rec["orbits"], n["Prim"], n["Sec"])
            a_as = o["a"] if o and o["a"] not in (None, "") else arcsec(n["Sep"], n["x_Sep"])
            per = days(o["Per"], o["x_Per"]) if o and o["Per"] not in (None, "") else days(n["Per"], n["x_Per"])
            has_orbit = bool(o) or any(c in (n["Type"] or "") for c in ("S1", "S2", "V", "A", "E"))
            r.update({
                "Separation from": f"{name} {n['Prim']}",
                "Separation (AU)": round(a_as * 1000 / plx, 5) if a_as else "",
                "Separation type": "semi-major axis" if has_orbit else "projected",
                "Separation (arcsec)": a_as if a_as else "",
                "Orbital period (d)": round(per, 4) if per else "",
                "Period basis": "orbit" if o and o["Per"] not in (None, "") else
                                ("MSC estimate from separation" if per else ""),
                "Detection (MSC)": decode_type(n["Type"]),
                "Orbital eccentricity (e)": o["e"] if o and o["e"] not in (None, "") else "",
                "Inclination (deg)": o["Incl"] if o and o["Incl"] not in (None, "") else "",
                "Ascending node (deg)": o["Node"] if o and o["Node"] not in (None, "") else "",
                "Argument of periastron (deg)": o["LongP"] if o and o["LongP"] not in (None, "") else "",
                "Orbit described": f"{name} {n['Prim']} + {name} {n['Sec']}",
                "Orbit source": (o["Note"] or "") if o else "",
                "Separation source": (f"{MSC}: {'orbit semi-major axis' if o and o['a'] else 'separation'} "
                                      f"{a_as}\" ({n['Comm'] or ''}); au = arcsec / parallax ({plx} mas)"
                                      if a_as else ""),
            })
        if lab == host:
            hc = next((c for c in cat if c["m_ID"] == re.match(r"[A-Z]*", lab).group(0)), main)
            r.update({"Radial velocity (km/s)": hc["RV"] if hc["RV"] not in (None, "") else "",
                      "Proper motion in RA, μα·cos δ (mas/yr)": hc["pmRA"],
                      "Proper motion in Dec, μδ (mas/yr)": hc["pmDE"],
                      "Kinematics source": f"{MSC}, component {hc['m_ID']} (parallax ref. {hc['r_plx']})"})
        rows.append(r)
    return rows, None


def main():
    d = json.loads((HERE / "msc.json").read_text(encoding="utf-8"))
    systems, skipped = [], {}
    for sid, rec in d.items():
        if sid in DROP:
            skipped[sid] = DROP[sid]
            continue
        rows, why = build_system(sid, rec)
        if rows is None:
            skipped[sid] = why
        else:
            systems.append(rows)
    systems.sort(key=lambda rs: rs[0]["Distance (ly)"])
    wb = gs.get_workbook(refresh=True)
    ms_h = wb["tabs"][MS][0]
    headers = ms_h + [c for c, _ in NEW_COLUMNS]
    col = {h: i for i, h in enumerate(headers)}
    rows = [r for rs in systems for r in rs]
    for r in rows:
        assert not set(r) - set(col), set(r) - set(col)
    grid = [[r.get(h, "") for h in headers] for r in rows]

    n_stars = sum(1 for r in rows if r["Node type"] == "star")
    nusco_ly = next(rs[0]["Distance (ly)"] for rs in systems if rs[0]["WDS code"] == "16120-1928")
    beyond = [rs[0]["System / Host"] for rs in systems if rs[0]["Distance (ly)"] > 100]
    lines = [
        "",
        f"4+ STARS ONLY, 28 SEPTEMBER 2026: NEW TAB, {len(systems)} SYSTEMS OF FOUR OR MORE STARS "
        f"({n_stars} stars, {len(rows) - n_stars} subsystems).",
        "Builder: data/four_plus_stars/ (fetch_msc.py -> msc.json -> build.py); log write_log.json.",
        f"SOURCE: {MSC}. Every system whose catalog row has Nc >= 4 and parallax >= 32.6156 mas (<= 100 ly),",
        "  queried 28 Sep 2026 from tapvizier.cds.unistra.fr: tables catalog (components, parallax, PM, RV),",
        "  systems (the pairs: primary, secondary, parent, period, separation, masses, spectral types) and",
        "  orbits (elements). Components whose MSC parent is 'X' (optical, not physical) are left out, and a",
        "  system counts only if it keeps 4+ physical components after that.",
        f"  Plus nu Sco (WDS 16120-1928), asked for by name: 7 components but {nusco_ly:.0f} ly (MSC parallax 7.06 mas),",
        "  so it is OUTSIDE the 100 ly scope and on this tab by request only.",
        "  Dropped: " + "; ".join(f"{k}: {v}" for k, v in skipped.items()) + ".",
        "MODEL: Multi-stars' columns, plus " + str(len(NEW_COLUMNS)) + " (listed below). The MSC is a tree of pairs, and an",
        "  outer orbit is between the barycentres of two pairs (Castor C orbits A+B), which a star-to-star",
        "  'Separation from' cannot express. So a SUBSYSTEM gets a row too, with its summed mass, and every",
        "  node that is the secondary of its pair carries that pair's orbit: 'Separation from' names the pair's",
        "  primary node (a star or a subsystem), the rest of the orbit is in the new columns.",
        "  Host: the most massive star, as on Multi-stars.",
        "NEW COLUMNS: " + "; ".join(f"{c} = {w}" for c, w in NEW_COLUMNS) + ".",
        "INFERRED (orange box + note): 'Separation (AU)', = published arcsec / MSC parallax. For a spectroscopic",
        "  pair with no visual orbit, the MSC's own separation is itself an estimate from period and masses.",
        "  No relation fitted; valid wherever the parallax is.",
        "PERIODS: from a computed orbit where the MSC orbit table has one ('Period basis' = orbit); otherwise the",
        "  MSC's own estimate from the projected separation, which for a wide pair is order-of-magnitude only.",
        "NOT FILLED: Teff, luminosity, age, metallicity -- the MSC carries none -- so the solvent-band columns read",
        "  'no luminosity on file'. Kinematics (RV, PM) are on each host row, from the MSC catalog table.",
        "NOT READ BY THE CODE: catalog_loader.FOUR_PLUS_SIGNATURE ('Star (component)' + 'Node type') skips this tab,",
        "  which would otherwise match the stars signature and add these rows to systems of the same name.",
    ]

    if PLAN:
        print(f"{len(systems)} systems, {n_stars} stars, {len(rows) - n_stars} subsystems, {len(headers)} columns;"
              f" beyond 100 ly: {beyond}; skipped {skipped}")
        for rs in systems:
            h = rs[0]
            print(f"  {h['System / Host']:16} {h['Nickname (IAU)']:15} {h['Distance (ly)']:7} ly "
                  f"{h['Stars in system']} stars  host {h['MSC label']:4} {h['Mass (M-sun)']!s:5} {h['Hierarchy']}")
        for r in systems[[s[0]['WDS code'] for s in systems].index("07346+3153")]:
            print("   ", {k: r.get(k) for k in ("Star (component)", "Node type", "Member of", "Mass (M-sun)",
                                              "Separation from", "Separation (AU)", "Orbital period (d)",
                                              "Period basis", "Inclination (deg)")})
        print("\n".join(lines))
        return

    titles = {s["properties"]["title"]: s["properties"] for s in
              API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}
    assert FP not in titles, f"{FP} already exists"
    ms_meta = titles[MS]
    nrows, ncols = len(grid) + 1, len(headers)
    res = API.batchUpdate(spreadsheetId=SID, body={"requests": [{"addSheet": {"properties": {
        "title": FP, "index": ms_meta["index"] + 1,
        "gridProperties": {"rowCount": nrows, "columnCount": ncols, "frozenRowCount": 1, "frozenColumnCount": 2}}}}]}
                           ).execute()
    fid = res["replies"][0]["addSheet"]["properties"]["sheetId"]
    gs.invalidate_cache(SID)

    def rng(sheet, r0, r1, c0, c1):
        return {"sheetId": sheet, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}
    # Formulas and formats from a Multi-stars star row (luminosity class, HZ and band columns work unchanged),
    # then the header's look, then the values over them.
    tmpl = next(i for i, r in enumerate(wb["tabs"][MS]) if len(r) > 1 and r[1] == "alf Cen B")
    msid, nms = ms_meta["sheetId"], len(ms_h)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [
        {"copyPaste": {"source": rng(msid, tmpl, tmpl + 1, 0, nms), "destination": rng(fid, 1, nrows, 0, nms),
                       "pasteType": "PASTE_NORMAL"}},
        {"copyPaste": {"source": rng(msid, 0, 1, 0, nms), "destination": rng(fid, 0, 1, 0, nms),
                       "pasteType": "PASTE_FORMAT"}},
        {"copyPaste": {"source": rng(msid, 0, 1, nms - 1, nms), "destination": rng(fid, 0, 1, nms, ncols),
                       "pasteType": "PASTE_FORMAT"}},
    ]}).execute()
    formula_cols = {h for h, v in zip(ms_h, API.values().get(
        spreadsheetId=SID, range=f"{q(MS)}!A{tmpl + 1}:{letter(nms - 1)}{tmpl + 1}",
        valueRenderOption="FORMULA").execute()["values"][0]) if str(v).startswith("=")}
    # A star row keeps the pasted formulas, so write only the runs of typed cells between them;
    # a subsystem row has no class or luminosity, so its formula cells are blanked.
    batch = {}
    for i, (r, g) in enumerate(zip(rows, grid)):
        rr = i + 2
        run, start = [], None
        for h, v in zip(headers, g):
            k = col[h]
            keep = h in formula_cols and r["Node type"] == "star"
            if keep:
                if run:
                    batch[f"{q(FP)}!{letter(start)}{rr}:{letter(start + len(run) - 1)}{rr}"] = [run]
                run, start = [], None
            else:
                if start is None:
                    start = k
                run.append(v)
        if run:
            batch[f"{q(FP)}!{letter(start)}{rr}:{letter(start + len(run) - 1)}{rr}"] = [run]
    gs.update_cells(SID, {f"{q(FP)}!A1:{letter(ncols - 1)}1": [headers]})
    items = list(batch.items())
    for s in range(0, len(items), 500):
        gs.update_cells(SID, dict(items[s:s + 500]))

    # markings: plain grey everywhere (the template's orange on AR came with the paste), orange on the au column
    grey = {"style": "SOLID", "color": gs._hex_to_color(GREY_RULE)}
    API.batchUpdate(spreadsheetId=SID, body={"requests": [
        {"updateBorders": {"range": rng(fid, 1, nrows, 0, ncols), "top": grey, "bottom": grey, "left": grey,
                           "right": grey, "innerHorizontal": grey, "innerVertical": grey}},
        {"updateCells": {"range": rng(fid, 1, nrows, 0, ncols), "fields": "note"}},
        {"setBasicFilter": {"filter": {"range": rng(fid, 0, nrows, 0, ncols)}}},
    ]}).execute()
    au = col["Separation (AU)"]
    orange, notes = [], {}
    for i, r in enumerate(rows):
        if r.get("Separation (AU)") not in (None, ""):
            cell = f"{q(FP)}!{letter(au)}{i + 2}"
            orange.append(cell)
            notes[cell] = (f"INFERRED: au = {r['Separation (arcsec)']}\" / parallax; the arcsec value and the parallax "
                           f"are the MSC's ({MSC}, WDS {r['WDS code']}). "
                           + ("The MSC's separation for a spectroscopic pair without a visual orbit is itself its "
                              "estimate from period and masses. " if "spectroscopic" in r.get("Detection (MSC)", "")
                              and "visual orbit" not in r.get("Detection (MSC)", "") else "")
                           + ("WEAK: projected separation, a lower bound on the orbit."
                              if r.get("Separation type") == "projected" else ""))
    for s in range(0, len(orange), 200):
        gs.set_border(SID, orange[s:s + 200], gs.INFERRED_BORDER)
    items = list(notes.items())
    for s in range(0, len(items), 300):
        gs.set_note(SID, dict(items[s:s + 300]))

    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    last = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{last}"])[f"{q(SP)}!A{last}"][0][0].strip()
    start, end = last + 1, last + len(lines)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log = {"tab": FP, "sheet_id": fid, "systems": len(systems), "stars": n_stars,
           "subsystems": len(rows) - n_stars, "rows": len(rows), "orange": len(orange), "sp_rows": [start, end],
           "skipped": skipped, "beyond_100ly": beyond, "title": title}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log, ensure_ascii=False))


if __name__ == "__main__":
    main()
