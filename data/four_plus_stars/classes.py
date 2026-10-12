# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Correct the classes the literature disputes on "Planetless 4+ Stars", and the luminosity-class formula.

    python classes.py plan      print every cell it would write, old -> new; touches nothing
    python classes.py write     write, note, provenance, rename

1. Seven MSC classes that a component-level paper contradicts are replaced by the paper's, with a note on the
   class cell quoting it and naming what the MSC had (lit/*.json holds the full records):
     alf Aur A/B (Capella) G5III/G0II -> G8III/G0III      Torres et al. 2015
     GJ 275.2 Ba/Bb        DC9        -> DA               Limoges, Bergeron & Lepine 2015
     HR 2158 C             G0IV       -> F9V              Gray et al. 2006
     alf2 Lib Ba           F5IV       -> F4V              Gray et al. 2006
   GJ 275.2 Ab loses the MSC's 'DA': it is the unseen astrometric companion of the sdM star, never observed, so
   no class exists; its role goes from 'white dwarf' to 'star', the tab's word for a companion of unknown kind.
   HR 1099 Aa/Ab: the MSC gives the more massive Aa the G5 class, but Garcia-Alvarez et al. 2003 make the K1 IV
   star the primary and the G5 star a dwarf. The classes, luminosities and luminosity notes swap between the two
   rows; masses and labels stay the MSC's. Both luminosities were already matched to their star by spectral type.
2. 'Luminosity class' tests LEFT(class,1)="D" for a white dwarf, and Sheets compares text case-insensitively, so the
   old dwarf prefix ('dM1', 'dK6') read as "White dwarf". EXACT() makes it case-sensitive, and a lowercase 'd' now
   reads "Main sequence", which is what the prefix means. Same formula on Systems, Multi-stars and this tab.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q, sort_key  # noqa: E402  (importing fill also installs its 429 retry wrapper)

SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
FP, SP = "Planetless 4+ Stars", "Sources & Provenance"
FORMULA_TABS = ["Systems within 100 ly", "Multi-stars within 100 ly", FP]
LOG = HERE / "classes_log.json"
PLAN = sys.argv[1:] == ["plan"]

TORRES = ("Torres et al. 2015, ApJ 807, 26 (arXiv:1505.07461; doi:10.1088/0004-637X/807/1/26) "
          "https://arxiv.org/abs/1505.07461")
LIMOGES = ("Limoges, Bergeron & Lepine 2015, ApJS 219, 19 (arXiv:1505.02297; VizieR J/ApJS/219/19) "
           "https://arxiv.org/pdf/1505.02297")
GRAY = ("Gray et al. 2006, AJ 132, 161 (VizieR J/AJ/132/161) "
        "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/AJ/132/161")
GARCIA = ("Garcia-Alvarez et al. 2003, A&A 402, 1073 (arXiv:astro-ph/0303154; doi:10.1051/0004-6361:20030288) "
          "https://arxiv.org/html/astro-ph/0303154")
HR1099_QUOTE = ('"a K1 IV (HD 92588 and HD 39523 ...) with a photospheric temperature T=4 800 K for the primary '
                'component, and a G5 V (HD 5268 and HD 36079 ...) with temperature T=5 400 K for the secondary '
                'component." The primary is also the more massive (m sin^3 i 0.2256 vs 0.1752 Msun).')

# component: (MSC class now on the row, new class, short source for 'Star data source', class-cell note)
CLASSES = {
    "alf Aur A": ("G5III", "G8III", "Torres et al. 2015",
                  f"SOURCE: {TORRES}: 'Capella (alpha Aurigae, HD 34029, HR 1708, HIP 24608, G8 III+G0 III, ...)' "
                  "(introduction). This is the primary: 2.5687 Msun, the cooler clump giant, Teff 4970 K. "
                  "The MSC had G5III."),
    "alf Aur B": ("G0II", "G0III", "Torres et al. 2015",
                  f"SOURCE: {TORRES}: 'G8 III+G0 III' (introduction). The secondary: 2.4828 Msun, Teff 5730 K, "
                  "crossing the Hertzsprung gap. The MSC had G0II; luminosity class II is not supported by this paper."),
    "GJ 275.2 Ba": ("DC9", "DA", "Limoges et al. 2015",
                    f"SOURCE: {LIMOGES}, Table 5: \"07307+4810A DA 4910 (105) 7.86 ...\" (Teff 4910 K). "
                    "Holberg et al. 2016 (MNRAS 462, 2295) give DA10.0 for WD 0727+482.1. The MSC had DC9, which is older."),
    "GJ 275.2 Bb": ("DC9", "DA", "Limoges et al. 2015",
                    f"SOURCE: {LIMOGES}, Table 5: \"07307+4810B DA 4940 (85) 8.12 ...\" (Teff 4940 K). "
                    "Holberg et al. 2016 give DA10.1 for WD 0727+482.2. The MSC had DC9, which is older."),
    "GJ 275.2 Ab": ("DA", "", "class withdrawn (unseen companion)",
                    "BLANK: the unseen astrometric companion of the sdM5 star G 107-69 (Harrington, Christy & Strand "
                    "1981, P = 0.94 yr). Never detected directly, so no spectrum exists. The MSC's 'DA' (pair flagged "
                    "'A?') is not a classification of an observed object; the system's DA white dwarfs are Ba and Bb "
                    "(G 107-70 = WD 0727+482). Holberg et al. 2016, MNRAS 462, 2295 (arXiv:1606.01236)."),
    "HR 2158 C": ("G0IV", "F9V", "Gray et al. 2006",
                  f"SOURCE: {GRAY}: 'HIP 28764 ... 41700 F9 V Fe-0.4 6241 4.40'. log g 4.40 is a dwarf's; SIMBAD F8V. "
                  "HR 2158 C = HD 41700 = HR 2157 = HIP 28764. The MSC had G0IV."),
    "alf2 Lib Ba": ("F5IV", "F4V", "Gray et al. 2006",
                    f"SOURCE: {GRAY}: 'HIP 72603 ... 130819 F4 V 6745 4.25'. SIMBAD F3V. alf2 Lib Ba = alf1 Lib = "
                    "HD 130819 = HIP 72603. The MSC had F5IV."),
    "HR 1099 Aa": ("G5IV", "K1IV", "Garcia-Alvarez et al. 2003",
                   f"SOURCE: {GARCIA}: {HR1099_QUOTE} The MSC puts G5IV on Aa, its more massive star (1.2 Msun), "
                   "and K1IV on Ab; the paper's primary is the K1 IV star, so the classes and luminosities are "
                   "swapped between Aa and Ab here and the MSC masses left where they were."),
    "HR 1099 Ab": ("K1IV", "G5V", "Garcia-Alvarez et al. 2003",
                   f"SOURCE: {GARCIA}: {HR1099_QUOTE} The MSC had K1IV here and G5IV on Aa; see the note on Aa's class."),
}
ROLE = {"GJ 275.2 Ab": ("white dwarf", "star")}
SWAP_L = ("HR 1099 Aa", "HR 1099 Ab")

OLD_BRANCH = re.compile(r'IF\(LEFT\(TRIM\((\$[A-Z]+\d+)\),1\)="D","White dwarf",')


def new_formula(f):
    """The case-sensitive formula, or None if f is not the old one."""
    m = OLD_BRANCH.search(f or "")
    if not m or f.count('"White dwarf"') != 2:
        return None
    c = m.group(1)
    return (f[:m.start()] + f'IF(EXACT(LEFT(TRIM({c}),1),"D"),"White dwarf",'
            f'IF(EXACT(LEFT(TRIM({c}),1),"d"),"Main sequence",' + f[m.end():] + ")")


def main():
    upd, expect, notes = {}, {}, {}
    fp = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A1:BZ2000", valueRenderOption="UNFORMATTED_VALUE"
                          ).execute()["values"]
    h = fp[0]
    col = {k: i for i, k in enumerate(h)}
    rows = {}
    for r, row in enumerate(fp[1:], start=2):
        name = row[col["Star (component)"]] if len(row) > col["Star (component)"] else ""
        if name in CLASSES:
            assert name not in rows, f"{name} appears twice"
            rows[name] = (r, row + [""] * (len(h) - len(row)))
    assert set(rows) == set(CLASSES), set(CLASSES) - set(rows)

    def cell(name, header):
        return f"{q(FP)}!{letter(col[header])}{rows[name][0]}"

    def put(name, header, new):
        c = cell(name, header)
        old = rows[name][1][col[header]]
        expect[c] = old
        upd[c] = new

    for name, (old, new, short, note) in CLASSES.items():
        row = rows[name][1]
        assert row[col["Stellar Class"]] == old, (name, row[col["Stellar Class"]], old)
        put(name, "Stellar Class", new)
        k = sort_key(new) if new and not new.startswith("D") else None
        if row[col["Class (sort key)"]] != (k if k is not None else ""):
            put(name, "Class (sort key)", k if k is not None else "")
        put(name, "Star data source", f"{row[col['Star data source']]}; class: {short}")
        notes[cell(name, "Stellar Class")] = note
    for name, (old, new) in ROLE.items():
        assert rows[name][1][col["Role in system"]] == old
        put(name, "Role in system", new)

    a, b = SWAP_L
    la, lb = rows[a][1][col["Luminosity (L-sun)"]], rows[b][1][col["Luminosity (L-sun)"]]
    put(a, "Luminosity (L-sun)", lb)
    put(b, "Luminosity (L-sun)", la)
    lnotes = gs.get_notes(SID, f"{q(FP)}!P{rows[a][0]}:P{rows[b][0]}")
    na, nb = lnotes[f"P{rows[a][0]}"], lnotes[f"P{rows[b][0]}"]
    assert "R = 1.1 Rsun" in na and "R = 3.3 Rsun" in nb, (na, nb)
    notes[cell(a, "Luminosity (L-sun)")] = nb + " This is the K1 IV primary (see the class note)."
    notes[cell(b, "Luminosity (L-sun)")] = na + " This is the G5 V secondary (see the class note on Aa)."
    bd = gs.get_borders(SID, f"{q(FP)}!P{rows[a][0]}:P{rows[b][0]}")
    for k in (f"P{rows[a][0]}", f"P{rows[b][0]}"):
        assert all(c == "FF9900" for c, _ in bd[k].values()) and len(bd[k]) == 4, (k, bd[k])

    # ---- the formula, on every tab that carries it
    formulas, fcount = {}, {}
    for tab in FORMULA_TABS:
        v = API.values().get(spreadsheetId=SID, range=f"{q(tab)}!A1:BZ2000", valueRenderOption="FORMULA"
                             ).execute()["values"]
        il = v[0].index("Luminosity class")
        n = 0
        for r, row in enumerate(v[1:], start=2):
            f = row[il] if len(row) > il else ""
            if isinstance(f, str) and f.startswith("="):
                nf = new_formula(f)
                assert nf, (tab, r, f)
                assert f"${letter(v[0].index('Stellar Class'))}{r})" in f, (tab, r, f)
                formulas[f"{q(tab)}!{letter(il)}{r}"] = (f, nf)
                n += 1
        fcount[tab] = n

    lines = [
        "",
        "29 SEPTEMBER 2026: 'Planetless 4+ Stars' -- DISPUTED CLASSES CORRECTED; LUMINOSITY-CLASS FORMULA MADE "
        "CASE-SENSITIVE (classes.py).",
        "Writer: data/four_plus_stars/classes.py; log classes_log.json. Records with quotes: data/four_plus_stars/lit/.",
        "CLASS: the MSC's class replaced where a component-level paper contradicts it; the class cell's note quotes "
        "the paper and names the MSC's value.",
        "  alf Aur A/B (Capella) G5III/G0II -> G8III/G0III (Torres et al. 2015, ApJ 807, 26). GJ 275.2 Ba/Bb DC9 -> DA "
        "(Limoges, Bergeron & Lepine 2015, ApJS 219, 19; Holberg et al. 2016: DA10.0/DA10.1).",
        "  HR 2158 C G0IV -> F9V and alf2 Lib Ba F5IV -> F4V (Gray et al. 2006, AJ 132, 161, J/AJ/132/161).",
        "  GJ 275.2 Ab: the MSC's 'DA' removed and role 'white dwarf' -> 'star'. It is the unseen astrometric companion "
        "of G 107-69 (Harrington et al. 1981); no spectrum exists. The DA pair is Ba/Bb.",
        "  HR 1099 Aa/Ab: classes G5IV/K1IV -> K1IV/G5V, and luminosities 0.927/5.21 swapped with their notes "
        "(Garcia-Alvarez et al. 2003, A&A 402, 1073: the K1 IV star is the primary, the G5 star a dwarf). MSC masses "
        "and labels unchanged. Luminosities stay INFERRED (orange) from that paper's R and Teff.",
        "  Confidence HIGH for Capella and GJ 275.2 Ba/Bb (component classes in the cited tables); MEDIUM for "
        "HR 2158 C, alf2 Lib Ba (catalogue types; SIMBAD gives F8V, F3V) and HR 1099 (which star the MSC called Aa).",
        "FORMULA: 'Luminosity class' tested LEFT(class,1)=\"D\", which Sheets evaluates case-insensitively, so the old "
        "dwarf prefix (dM1, dK6) read as \"White dwarf\": GJ 867 Ab, alf Aur H, alf Aur L, CD-65 332 Ba, 17 Cyg B.",
        f"  Now EXACT(...,\"D\") for a white dwarf and EXACT(...,\"d\") -> \"Main sequence\". Rewritten on "
        + ", ".join(f"{t} ({n} rows)" for t, n in fcount.items()) + "; only this tab had an affected row.",
    ]

    if PLAN:
        for c, v in upd.items():
            print(f"  {c:40} {expect[c]!r:>60.60}  ->  {v!r:.80}")
        for c, v in notes.items():
            print(f"  NOTE {c}: {v[:160]}")
        print("formulas:", fcount, "e.g.", next(iter(formulas.values()))[1])
        print("\n".join(lines))
        return

    gs.update_cells(SID, upd, expect=expect)
    gs.set_note(SID, notes)
    items = list(formulas.items())
    for s in range(0, len(items), 300):
        chunk = items[s:s + 300]
        now = {}
        for tab in FORMULA_TABS:
            rngs = [c for c, _ in chunk if c.startswith(q(tab) + "!")]
            if rngs:
                res = API.values().batchGet(spreadsheetId=SID, ranges=rngs, valueRenderOption="FORMULA").execute()
                now.update({c: vr["values"][0][0] for c, vr in zip(rngs, res["valueRanges"])})
        for c, (old, _) in chunk:
            assert now[c] == old, f"{c} changed under us: {now[c]!r}"
        gs.update_cells(SID, {c: nf for c, (_, nf) in chunk}, value_input="USER_ENTERED")
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
    log = {"cells": {c: [expect[c], v] for c, v in upd.items()}, "notes": sorted(notes),
           "formula_rows": fcount, "sp_rows": [start, end], "title": title}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps({k: v for k, v in log.items() if k != "cells"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
