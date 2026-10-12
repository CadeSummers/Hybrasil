# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Add periastron epochs, sky positions and barycentres to "Planetless 4+ Stars" -- what drawing a system needs.

    python orbits.py plan      print the new columns and a sample of every kind of cell; touches nothing
    python orbits.py write     add the columns, write, mark, note, provenance, rename

build.py wrote each orbit's shape and orientation but not *when* the stars are where: a Keplerian orbit needs a
phase, and the MSC orbit table's T (periastron epoch) is that phase. Nor did it write a sky position, which a
drawing needs to orient the sky-plane frame and the galactic-centre arrow. Both are in msc.json already. And the
tab says which pairs orbit which, but not where a pair's barycentre is, which is what the outer member of the next
pair up actually circles. Six columns, appended after 'WDS code':

  Time of periastron (JD)    from the orbit build.py chose (build.best_orbit), on the row that holds that orbit.
                             The MSC gives T as JD-2400000 or, for visual orbits, a Besselian year; a year is
                             converted, JD = 2415020.31352 + 365.242198781 (B - 1900), and the cell note says so.
                             For a circular orbit the MSC's T is its zero point of phase, not a periastron.
  RA (deg, ICRS)             the MSC catalog record for this component (exact label, else the longest label that
  Dec (deg, ICRS)            prefixes it, else the system's main record), RAJ2000 / DEJ2000.
  Position source            which record that was.
  Barycentre from            on a subsystem row: the pair's primary member, by name.
  Barycentre offset (AU)     on a subsystem row: a * M_sec / (M_prim + M_sec), where a is the pair's separation
                             (on the secondary's row) and the masses are the two members' rows. For a semi-major
                             axis this is the semi-major axis of the barycentre's orbit round the primary member.
                             Arithmetic on published inputs, so orange, with a note; WEAK where the separation is
                             projected or a mass is a minimum.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)
from build import best_orbit  # noqa: E402

SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
FP, SP = "Planetless 4+ Stars", "Sources & Provenance"
LOG = HERE / "orbits_log.json"
PLAN = sys.argv[1:] == ["plan"]
MSC = "MSC (Tokovinin 2018, ApJS 235, 6; VizieR J/ApJS/235/6, Dec 2023 update)"
NEW = ["Time of periastron (JD)", "RA (deg, ICRS)", "Dec (deg, ICRS)", "Position source",
       "Barycentre from", "Barycentre offset (AU)"]


def jd_of(t):
    """The MSC's T as a full Julian Date, and whether it was converted from a Besselian year. None if absent."""
    if t in (None, "", 0):
        return None, False
    if t < 10000:
        return round(2415020.31352 + 365.242198781 * (t - 1900.0), 4), True
    return round(2400000.0 + t, 4), False


def catalog_record(cat, label):
    exact = [c for c in cat if c["m_ID"] == label]
    if exact:
        return exact[0], "exact"
    pre = sorted((c for c in cat if c["m_ID"] and label.startswith(c["m_ID"])), key=lambda c: -len(c["m_ID"]))
    if pre:
        return pre[0], "prefix"
    return max(cat, key=lambda c: c["Nc"] or 0), "main"


def main():
    msc = json.loads((HERE / "msc.json").read_text(encoding="utf-8"))
    v = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A1:CZ2000", valueRenderOption="UNFORMATTED_VALUE"
                         ).execute()["values"]
    h = v[0]
    assert h[-1] == "WDS code" and not set(NEW) & set(h), h[-3:]
    col = {k: i for i, k in enumerate(h)}
    rows = {}
    for r, row in enumerate(v[1:], start=2):
        row = row + [""] * (len(h) - len(row))
        name = row[col["Star (component)"]]
        if not name:
            continue
        assert name not in rows, f"{name} appears twice"
        rows[name] = (r, row)

    def val(name, header):
        return rows[name][1][col[header]]

    by_sys = {}
    for name, (r, row) in rows.items():
        by_sys.setdefault(row[col["WDS code"]], {})[row[col["MSC label"]]] = name

    out, notes, orange = {}, {}, []
    c0 = len(h)
    counts = {"T": 0, "T_years": 0, "T_missing": 0, "pos": {"exact": 0, "prefix": 0, "main": 0},
              "bary": 0, "bary_weak": 0, "bary_blank": 0}
    for name, (r, row) in rows.items():
        wds, lab = row[col["WDS code"]], row[col["MSC label"]]
        rec = msc[wds]
        sysname = row[col["System / Host"]]
        cells = [""] * len(NEW)

        # periastron epoch, on the row that holds its pair's orbit (the secondary's)
        pair = next((n for n in rec["systems"] if n["Sec"] == lab and n["Parent"] != "X"
                     and not (n["Type"] or "").startswith("X")), None)
        if pair is not None and row[col["Orbit described"]]:
            o = best_orbit(rec["orbits"], pair["Prim"], pair["Sec"])
            # a T without a period (a grade-7 placeholder such as GJ 118.2's, P = 0, e = 1) places nothing
            jd, conv = jd_of(o["T"]) if o and o["Per"] not in (None, "", 0) else (None, False)
            if jd is not None:
                p = row[col["Orbital period (d)"]]
                assert p != "" and abs(p - o["Per"] * {"d": 1, "y": 365.25, "k": 365250.0}[o["x_Per"] or "d"]) < 1, \
                    (name, p, o)
                cells[0] = jd
                counts["T"] += 1
                a1 = f"{q(FP)}!{letter(c0)}{r}"
                src = f"{MSC} orbit table, {o['Note']}"
                if conv:
                    counts["T_years"] += 1
                    notes[a1] = (f"SOURCE: {src}. The MSC gives T = {o['T']} (Besselian year); converted as "
                                 "JD = 2415020.31352 + 365.242198781 x (B - 1900).")
                else:
                    notes[a1] = f"SOURCE: {src}. The MSC gives T = {o['T']} (JD - 2400000)."
                if row[col["Orbital eccentricity (e)"]] in ("", 0):
                    notes[a1] += (" No eccentricity on file: if the orbit is circular this T is the MSC's zero "
                                  "point of phase (usually the ascending node or maximum velocity), not a periastron.")
            else:
                counts["T_missing"] += 1

        # sky position
        c, how = catalog_record(rec["catalog"], lab)
        counts["pos"][how] += 1
        cells[1], cells[2] = c["RAJ2000"], c["DEJ2000"]
        fallback = "the record whose label prefixes it" if how == "prefix" else "the system's main record"
        cells[3] = (f"{MSC}, catalog record for component {c['m_ID']} (RAJ2000/DEJ2000)"
                    + ("" if how == "exact" else f"; no record for {lab} itself, so {fallback}"))

        # barycentre of a subsystem
        if row[col["Node type"]] == "subsystem":
            split = next(n for n in rec["systems"] if n["Parent"] == lab)
            prim, sec = by_sys[wds].get(split["Prim"]), by_sys[wds].get(split["Sec"])
            a = val(sec, "Separation (AU)") if sec else ""
            m1 = val(prim, "Mass (M-sun)") if prim else ""
            m2 = val(sec, "Mass (M-sun)") if sec else ""
            cells[4] = prim or ""
            a1 = f"{q(FP)}!{letter(c0 + 5)}{r}"
            assert sec and val(sec, "Separation from") == prim, (name, sec, prim)
            if a != "" and m1 != "" and m2 != "":
                off = a * m2 / (m1 + m2)
                cells[5] = round(off, 6)
                orange.append(a1)
                counts["bary"] += 1
                kind = val(sec, "Separation type")
                weak = []
                if kind != "semi-major axis":
                    weak.append(f"the separation is {kind or 'of unknown kind'}, not a semi-major axis")
                if "minimum" in str(val(sec, "Mass basis (MSC)")) or "minimum" in str(val(prim, "Mass basis (MSC)")):
                    weak.append("a mass is a minimum mass")
                counts["bary_weak"] += bool(weak)
                notes[a1] = (("WEAK: " + "; ".join(weak) + ".\n" if weak else "")
                             + f"INFERRED: a x M_sec / (M_prim + M_sec) = {a} au x {m2} / ({m1} + {m2}), from "
                               f"'{sec}' (Separation (AU), Mass) and '{prim}' (Mass). The barycentre of {sysname} "
                               f"{lab} lies this far from {prim}, on the line to {sec}"
                             + ("; for a semi-major axis, it is the semi-major axis of the barycentre's orbit round "
                                f"{prim}." if not weak or kind == "semi-major axis" else ".")
                             + f" Mass bases: {prim} {val(prim, 'Mass basis (MSC)') or 'n/a'}, "
                               f"{sec} {val(sec, 'Mass basis (MSC)') or 'n/a'}.")
            else:
                counts["bary_blank"] += 1
                missing = [w for w, x in (("the separation", a), (f"{prim}'s mass", m1), (f"{sec}'s mass", m2))
                           if x == ""]
                notes[a1] = f"BLANK: needs {', '.join(missing)}, which the tab does not have."
        out[r] = cells

    sp_lines = [
        "",
        "30 SEPTEMBER 2026: 'Planetless 4+ Stars' -- PERIASTRON EPOCHS, SKY POSITIONS AND BARYCENTRES ADDED "
        "(orbits.py).",
        "Writer: data/four_plus_stars/orbits.py; log orbits_log.json. Six columns after 'WDS code'.",
        f"'Time of periastron (JD)': {MSC} orbit table (msc.json), T of the same orbit build.py chose for the row "
        f"(most complete record). {counts['T']} orbits; {counts['T_years']} converted from a Besselian year with "
        "JD = 2415020.31352 + 365.242198781 x (B - 1900), each saying so in its note. For a circular orbit T is the "
        "MSC's zero point of phase, not a periastron. Confidence: as the orbit it belongs to. Verify: VizieR "
        "J/ApJS/235/6 orb.dat, column T.",
        f"'RA (deg, ICRS)', 'Dec (deg, ICRS)', 'Position source': {MSC} catalog (comp.dat) RAJ2000/DEJ2000, the "
        "record for the row's component, else the record whose label prefixes it (Ab -> A), else the system's main "
        f"record ({counts['pos']['exact']} exact / {counts['pos']['prefix']} prefix / {counts['pos']['main']} main). "
        "J2000 equinox; the difference from ICRS is under 0.1 arcsec. Confidence HIGH. Verify: comp.dat by WDS code.",
        "'Barycentre from', 'Barycentre offset (AU)' (subsystem rows): where the pair's barycentre is, as a distance "
        "from its primary member toward its secondary: a x M_sec / (M_prim + M_sec), with a the secondary's "
        "'Separation (AU)' and the masses the two members' 'Mass (M-sun)'. INFERRED (orange box + note): exact "
        "two-body arithmetic, so its error is its inputs' -- the MSC masses (often estimates; each note names the "
        f"basis) and the au conversion. {counts['bary']} filled, {counts['bary_weak']} of them WEAK (projected "
        f"separation or a minimum mass); {counts['bary_blank']} blank for want of an input, each with a note.",
        "  Why: an outer orbit in this tab is between barycentres, e.g. Castor C circles the A+B pair. A drawing "
        "places each barycentre from its primary member by this offset, then the next pair up from it.",
    ]

    if PLAN:
        print(f"{len(out)} rows; new columns {letter(c0)}..{letter(c0 + len(NEW) - 1)}: {NEW}")
        print(json.dumps(counts))
        for name in ("alf Gem AB", "alf Gem A", "alf Gem Ab", "alf Gem B", "alf Gem Bb", "alf Gem C", "alf Gem Cab",
                     "alf Gem Cb", "alf Gem Cc"):
            r = rows[name][0]
            print(f"  {name:14} {out[r]}")
            for k in range(len(NEW)):
                n = notes.get(f"{q(FP)}!{letter(c0 + k)}{r}")
                if n:
                    print(f"      note {NEW[k]}: {n}")
        print("\n".join(sp_lines))
        return

    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    fp = next(s["properties"] for s in meta if s["properties"]["title"] == FP)
    need = c0 + len(NEW) - fp["gridProperties"]["columnCount"]
    if need > 0:
        API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
            "sheetId": fp["sheetId"], "dimension": "COLUMNS", "length": need}}]}).execute()
    last = max(out)
    rng = f"{q(FP)}!{letter(c0)}1:{letter(c0 + len(NEW) - 1)}{last}"
    grid = [NEW] + [out.get(r, [""] * len(NEW)) for r in range(2, last + 1)]
    gs.update_cells(SID, {rng: grid}, expect={f"{q(FP)}!{letter(c0)}1": "", f"{q(FP)}!{letter(c0 + 5)}{last}": ""})
    # header and cell formats copied from the column before, then the markings
    src = {"sheetId": fp["sheetId"], "startRowIndex": 0, "endRowIndex": last,
           "startColumnIndex": c0 - 1, "endColumnIndex": c0}
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"copyPaste": {
        "source": src, "destination": {**src, "startColumnIndex": c0 + k, "endColumnIndex": c0 + k + 1},
        "pasteType": "PASTE_FORMAT"}} for k in range(len(NEW))]}).execute()
    for s in range(0, len(orange), 200):
        gs.set_border(SID, orange[s:s + 200], gs.INFERRED_BORDER)
    items = list(notes.items())
    for s in range(0, len(items), 200):
        gs.set_note(SID, dict(items[s:s + 200]))

    spm = next(s["properties"] for s in meta if s["properties"]["title"] == SP)
    lastsp = spm["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{lastsp}"])[f"{q(SP)}!A{lastsp}"][0][0].strip()
    start, end = lastsp + 1, lastsp + len(sp_lines)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": spm["sheetId"], "dimension": "ROWS", "length": len(sp_lines)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in sp_lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log = {"columns": dict(zip(NEW, (letter(c0 + k) for k in range(len(NEW))))), "counts": counts,
           "orange": orange, "sp_rows": [start, end], "title": title,
           "rows": {rows_name: out[r] for rows_name, (r, _) in rows.items()}}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps({k: log[k] for k in ("columns", "counts", "sp_rows", "title")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
