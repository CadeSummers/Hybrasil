# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Step 1: gather, read-only, what the existence and kinematics-reference columns are built from.

    python fetch.py            live.json (the three tabs as they are now, values + motion-cell notes),
                               cat/cns5.dat (CNS5, VizieR J/A+A/670/A19), cat/simbad_ids.json (SIMBAD main_id by Gaia
                               DR3 identifier and by name); each catalog file is skipped when already on disk

Nothing here writes to the sheet -- write.py is the only writer.  Rows are keyed by name + Gaia id, never by row
number (common.row_key).
"""
import sys
import urllib.request

from common import (CAT, CNS5_DAT, CNS5_URL, LIVE, SIMBAD_IDS, TABS, blank, load, name_of, gaia_of, notes_of, now,
                    q, read_tab, save, sheets)


def fetch_live():
    gs, sid, api = sheets()
    title = api.get(spreadsheetId=sid, fields="properties.title").execute()["properties"]["title"]
    out = {"read_from": title, "read_at": now(), "tabs": {}}
    for key, t in TABS.items():
        h, rows = read_tab(api, sid, t["tab"])
        col = {k: i for i, k in enumerate(h)}
        notes = {}
        for hd in t["motion_cols"]:
            c = col[hd]
            notes[hd] = notes_of(api, sid, t["tab"], c, len(rows) + 1)[1:]
        out["tabs"][key] = {"headers": h, "rows": rows, "notes": notes}
        print(f"  {t['tab']}: {len(rows)} rows, {len(h)} columns", flush=True)
    save(LIVE, out)
    print(f"read {title}")


def fetch_cns5():
    if CNS5_DAT.exists():
        return
    CAT.mkdir(exist_ok=True)
    with urllib.request.urlopen(CNS5_URL, timeout=120) as r:
        CNS5_DAT.write_bytes(r.read())
    print(f"  CNS5: {sum(1 for _ in CNS5_DAT.open(encoding='ascii', errors='replace'))} records")


def fetch_simbad():
    if SIMBAD_IDS.exists():
        return
    from astropy.table import Table
    from astroquery.simbad import Simbad
    from msc import simbad_names
    from plan import primary_bare
    live = load(LIVE)
    gaia, names = set(), set()
    for key, t in TABS.items():
        tab = live["tabs"][key]
        col = {k: i for i, k in enumerate(tab["headers"])}
        for r in tab["rows"]:
            g = gaia_of(r, col)
            if g:
                gaia.add(g)
            elif key != "known":                      # the Known tab's no-Gaia rows were matched in kinematics/simbad.py
                n0 = name_of(r, col, t)
                for n in (n0, str(r[col["System / Host"]]).strip(), primary_bare(n0)):
                    if n:
                        names.add(n)
    names |= set(simbad_names())

    def rows_of(tab):
        return [{c: (None if (hasattr(x[c], "mask") and x[c].mask) else
                     (x[c].decode() if isinstance(x[c], bytes) else str(x[c])).strip()) for c in tab.colnames}
                for x in tab]       # fixed-width char columns come back padded: '1013...216 '

    by_gaia = []
    ids = sorted(gaia)
    for s in range(0, len(ids), 2000):
        chunk = ids[s:s + 2000]
        up = Table({"g": chunk, "gid": [f"Gaia DR3 {g}" for g in chunk]})
        by_gaia += rows_of(Simbad.query_tap(
            "SELECT t.g, b.main_id, b.otype FROM TAP_UPLOAD.up AS t JOIN ident AS i ON i.id = t.gid "
            "JOIN basic AS b ON b.oid = i.oidref", up=up, maxrec=100000))
        print(f"  Gaia ids {s + len(chunk)}/{len(ids)}: {len(by_gaia)} in SIMBAD", flush=True)
    nm = sorted(names)
    by_name = rows_of(Simbad.query_tap(
        "SELECT t.nm, b.main_id, b.otype FROM TAP_UPLOAD.up AS t JOIN ident AS i ON i.id = t.nm "
        "JOIN basic AS b ON b.oid = i.oidref", up=Table({"nm": nm}), maxrec=100000))
    print(f"  names {len(nm)}: {len(by_name)} in SIMBAD", flush=True)
    save(SIMBAD_IDS, {"queried": now(), "service": "SIMBAD TAP (astroquery Simbad.query_tap), ident -> basic",
                      "gaia_tried": len(ids), "names_tried": nm,
                      "by_gaia": {r["g"]: r["main_id"] for r in by_gaia},
                      "by_name": {r["nm"]: r["main_id"] for r in by_name}})


def main():
    what = sys.argv[1:] or ["live", "cns5", "simbad"]
    if "live" in what:
        fetch_live()
    if "cns5" in what:
        fetch_cns5()
    if "simbad" in what:
        fetch_simbad()


if __name__ == "__main__":
    main()
