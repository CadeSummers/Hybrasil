# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fill 'Stellar Class' and 'Luminosity (L-sun)' on the "Planetless 4+ Stars" tab, in tiers.

    python fill.py plan      print what each star would get, and the counts; touches nothing
    python fill.py write     write, mark, note, provenance, rename

Class, first that applies:
  1. the MSC's own (already on the row): published, left alone;
  2. the MSC component table's class, for a star that is a whole visual component there;
  3. a published class for that component (lit/*.json, read off the paper, with a quote);
  4. INFERRED from the MSC mass through the Pecaut & Mamajek (2013) dwarf sequence, v2022.04.16
     (EEM_dwarf_UBVIJHK_colors_Teff.txt): the type whose tabulated mass is nearest. Orange.
Luminosity, first that applies:
  1. a published bolometric luminosity for that component alone (lit/*.json): plain, with a note citing it;
  2. the paper's own R and Teff through L = R^2 (Teff/5772)^4 when it prints no L: orange;
  3. INFERRED from the class through the same sequence (log L interpolated in spectral subtype): orange;
  4. INFERRED from the MSC mass through the sequence, when the class was itself inferred: orange, WEAK.
The dwarf sequence is used only for main-sequence and brown dwarfs: never for a subgiant, giant or white
dwarf (IV, III, II, D*), which stay blank unless the literature has them.
"""
import json
import math
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
FP, SP = "Planetless 4+ Stars", "Sources & Provenance"
LOG = HERE / "fill_log.json"
PLAN = sys.argv[1:] == ["plan"]
T_SUN = 5772.0
PM = "Pecaut & Mamajek 2013 (ApJS 208, 9) dwarf sequence, v2022.04.16"
PM_URL = "https://www.pas.rochester.edu/~emamajek/EEM_dwarf_UBVIJHK_colors_Teff.txt"
MSC = "MSC (Tokovinin 2018, J/ApJS/235/6, Dec 2023)"
# The spreadsheet's component names differ from the research files' for the famous systems.
LIT_ALIAS = {"Castor": "alf Gem", "Mizar": "zet UMa", "Alcor": "zet UMa", "Regulus": "alf Leo", "Capella": "alf Aur"}
LIT_FIX = {"Capella Aa": "alf Aur A", "Capella Ab": "alf Aur B", "ksi UMa D": "ksi UMa D", "Regulus B": "alf Leo B",
           "Regulus C": "alf Leo C"}


def q(t):
    return "'" + t.replace("'", "''") + "'"


def letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def dwarf_prefix(spt):
    """'dM1e' -> 'M1e': the old 'd' prefix means dwarf. 'sd' (subdwarf) is left alone."""
    s = (spt or "").strip()
    return s[1:] if re.match(r"^d[OBAFGKM]", s) else s


def sort_key(spt):
    m = re.match(r"^([OBAFGKMLTY])(\d+(?:\.\d+)?)?", dwarf_prefix(spt))
    if not m:
        return None
    return "OBAFGKMLTY".index(m.group(1)) * 10 + (float(m.group(2)) if m.group(2) else 0)


def lum_class(spt):
    """'dwarf', 'evolved' or 'wd' -- the first component of a composite type decides."""
    s = dwarf_prefix((spt or "").strip().split("+")[0])
    if s.startswith(("D", "WD")):
        return "wd"
    if s.startswith("sd"):
        return "subdwarf"
    m = re.match(r"^[OBAFGKMLTY][\d.]*\s*(Ia|Ib|III|II|IV|I|V|VI)?", s)
    lc = m.group(1) if m else None
    return "evolved" if lc in ("I", "Ia", "Ib", "II", "III", "IV") else "dwarf"


def load_pm():
    rows = []
    for line in (HERE / "EEM_dwarf_UBVIJHK_colors_Teff.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("#SpT"):
            if rows:
                break                     # the first block is the table; a second header starts the notes
            hdr = line[1:].split()
            continue
        if not rows and "hdr" not in locals():
            continue
        f = line.split()
        if not f or not re.match(r"^[OBAFGKMLTY]\d", f[0]):
            if rows:
                break
            continue
        d = dict(zip(hdr, f))
        rows.append({"spt": d["SpT"], "key": sort_key(d["SpT"]), "teff": _num(d["Teff"]),
                     "logL": _num(d["logL"]), "mass": _num(d["Msun"])})
    return rows


def _num(s):
    try:
        return float(s.rstrip(":"))
    except (ValueError, AttributeError):
        return None


def interp(rows, x, xk, yk):
    pts = sorted((r[xk], r[yk]) for r in rows if r[xk] is not None and r[yk] is not None)
    if not pts or x < pts[0][0] or x > pts[-1][0]:
        return None
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def class_from_mass(rows, m):
    cands = [r for r in rows if r["mass"] is not None]
    if not cands or m < min(r["mass"] for r in cands) or m > max(r["mass"] for r in cands):
        return None
    return min(cands, key=lambda r: abs(r["mass"] - m))


def load_lit():
    out = {}
    for p in sorted((HERE / "lit").glob("*.json")):
        for rec in json.loads(p.read_text(encoding="utf-8")):
            name = re.sub(r"^([a-z]{2,3})0(\d) ", r"\1\2 ", LIT_FIX.get(rec["component"], rec["component"]))
            for k, v in LIT_ALIAS.items():
                if name.startswith(k + " "):
                    name = v + name[len(k):]
            rec["_file"] = p.name
            out[name] = rec
    return out


def sig(x, n=3):
    return float(f"{x:.{n}g}")


def main():
    pm = load_pm()
    lit = load_lit()
    msc = json.loads((HERE / "msc.json").read_text(encoding="utf-8"))
    wb = gs.get_workbook(refresh=True)
    t = wb["tabs"][FP]
    h = t[0]
    col = {k: i for i, k in enumerate(h)}
    plan, counts = [], {}
    for i, r in enumerate(t[1:], start=2):
        row = dict(zip(h, r + [""] * (len(h) - len(r))))
        if row["Node type"] != "star":
            continue
        comp, spt, m = row["Star (component)"], str(row["Stellar Class"]).strip(), row["Mass (M-sun)"]
        m = m if isinstance(m, (int, float)) else None
        weak_mass = "minimum" in row["Mass basis (MSC)"] or "estimated" in row["Mass basis (MSC)"]
        rec = lit.get(comp) if lit.get(comp, {}).get("applies_to_component_alone") else None
        blend = lit.get(comp) if rec is None and lit.get(comp, {}).get("luminosity_lsun") else None
        out = {"row": i, "comp": comp}
        # ---- class
        cls_src = "msc" if spt else None
        if not spt:
            c = next((c for c in msc[row["WDS code"]]["catalog"] if c["m_ID"] == row["MSC label"]), None)
            if c and (c["SpT"] or "").strip():
                spt, cls_src = c["SpT"].strip(), "msc-component"
        if not spt and rec and rec.get("spectral_type"):
            spt, cls_src = rec["spectral_type"], "lit"
        pm_row = None
        if not spt and m is not None and m >= 0.075:
            pm_row = class_from_mass(pm, m)
            if pm_row:
                spt, cls_src = pm_row["spt"], "pm-mass"
        if cls_src and cls_src != "msc":
            out["class"] = (spt, cls_src)
        # ---- luminosity
        kind = lum_class(spt) if spt else None
        L, lsrc = None, None
        if rec and rec.get("luminosity_lsun"):
            L, lsrc = rec["luminosity_lsun"], "lit"
        elif rec and rec.get("radius_rsun") and rec.get("teff_k"):
            L, lsrc = rec["radius_rsun"] ** 2 * (rec["teff_k"] / T_SUN) ** 4, "lit-RT"
        elif cls_src == "pm-mass":
            L, lsrc = 10 ** pm_row["logL"] if pm_row["logL"] is not None else None, "pm-mass"
        elif spt and kind == "dwarf" and sort_key(spt) is not None:
            lg = interp(pm, sort_key(spt), "key", "logL")
            if lg is not None:
                L, lsrc = 10 ** lg, "pm-class"
        if L:
            out["lum"] = (sig(L), lsrc)
        else:
            out["why_blank"] = ("evolved star, no component luminosity found" if kind == "evolved" else
                                "white dwarf, no component luminosity found" if kind == "wd" else
                                "subdwarf (metal-poor), off the dwarf sequence" if kind == "subdwarf" else
                                "no class and no mass in the MSC" if not spt and m is None else
                                "below the dwarf sequence's mass range (brown dwarf) and no class" if not spt else
                                "class outside the dwarf sequence")
        out.update(rec=rec, blend=blend, weak=weak_mass, mass=m, spt=spt, kind=kind)
        plan.append(out)
        key = (out.get("class", (None, "kept"))[1], out.get("lum", (None, "blank"))[1])
        counts[key] = counts.get(key, 0) + 1

    # ---- cells, markings, notes
    upd, orange, notes = {}, [], {}
    for p in plan:
        r = p["row"]
        src_bits = []
        if "class" in p:
            spt, how = p["class"]
            cell = f"{q(FP)}!{letter(col['Stellar Class'])}{r}"
            upd[cell] = spt
            k = sort_key(spt)
            upd[f"{q(FP)}!{letter(col['Class (sort key)'])}{r}"] = k if k is not None and p["kind"] != "wd" else ""
            if how == "pm-mass":
                orange.append(cell)
                notes[cell] = (f"INFERRED from mass{' -- WEAK' if p['weak'] else ''}: the {PM} type whose tabulated "
                               f"mass is nearest this star's {p['mass']} Msun (MSC). No spectrum of this component "
                               "has been classified; it is unresolved from its primary.")
                src_bits.append("class: INFERRED from mass (Pecaut & Mamajek)")
            elif how == "msc-component":
                src_bits.append(f"class: {MSC} component table")
            else:
                rec = p["rec"]
                notes[cell] = f"SOURCE: {rec['paper']} ({rec['identifier']}): \"{rec['quote'][:400]}\""
                src_bits.append(f"class: {rec['paper']}")
        elif p["spt"] and t[r - 1][col["Class (sort key)"]] in ("", None) and sort_key(p["spt"]) is not None                 and p["kind"] == "dwarf":
            upd[f"{q(FP)}!{letter(col['Class (sort key)'])}{r}"] = sort_key(p["spt"])
        cellL = f"{q(FP)}!{letter(col['Luminosity (L-sun)'])}{r}"
        if "lum" in p:
            L, how = p["lum"]
            upd[cellL] = L
            if how == "lit":
                rec = p["rec"]
                notes[cellL] = (f"SOURCE: {rec['paper']} ({rec['identifier']}) {rec['url']}: \"{rec['quote'][:500]}\""
                                + (f" NOTE: {rec['notes'][:300]}" if rec.get("notes") else ""))
                src_bits.append(f"L: {rec['paper']}")
            else:
                orange.append(cellL)
                if how == "lit-RT":
                    rec = p["rec"]
                    notes[cellL] = (f"INFERRED: L = R^2 (Teff/5772 K)^4 with R = {rec['radius_rsun']} Rsun and Teff = "
                                    f"{rec['teff_k']} K from {rec['paper']} ({rec['identifier']}), which prints no L.")
                elif how == "pm-class":
                    notes[cellL] = (f"INFERRED from class: log L interpolated in spectral subtype along the {PM}, "
                                    f"for {p['spt']} treated as a dwarf. Typical scatter ~0.1-0.2 dex; a young, "
                                    "metal-poor or unresolved star can sit well off it.")
                else:
                    notes[cellL] = (f"INFERRED from mass -- WEAK: the {PM} luminosity at the type nearest this star's "
                                    f"{p['mass']} Msun (MSC{', ' + 'minimum/estimated mass' if p['weak'] else ''}). "
                                    "Assumes a main-sequence dwarf of solar metallicity.")
                src_bits.append(f"L: INFERRED ({'R, Teff' if how == 'lit-RT' else 'Pecaut & Mamajek'})")
        else:
            b = p["blend"]
            notes[cellL] = f"BLANK: {p['why_blank']}." + (
                f" Found but NOT written: {b['luminosity_lsun']} Lsun from {b['paper']} ({b['identifier']}), which is not "
                f"this component's own light: {b.get('notes', '')[:400]}" if b else "")
        if src_bits:
            mcell = f"{q(FP)}!{letter(col['Star data source'])}{r}"
            upd[mcell] = t[r - 1][col["Star data source"]] + "; " + "; ".join(src_bits)

    n_lit = sum(1 for p in plan if p.get("lum", (0, ""))[1] == "lit")
    n_inf = sum(1 for p in plan if p.get("lum", (0, ""))[1] in ("pm-class", "pm-mass", "lit-RT"))
    n_cls = sum(1 for p in plan if "class" in p)
    blank = [p for p in plan if "lum" not in p]
    lines = [
        "",
        "28 SEPTEMBER 2026: 'Planetless 4+ Stars' -- STELLAR CLASS AND LUMINOSITY FILLED, IN TIERS (fill.py).",
        "Writer: data/four_plus_stars/fill.py; literature records in data/four_plus_stars/lit/*.json (paper, id, URL,",
        "  verbatim quote for every value); log fill_log.json. psi1 Dra and GJ 896 were removed from the tab first:",
        "  both host planets on file (psi1 Dra B b; GJ 896 A b), so they do not belong on a 'Planetless' list.",
        f"CLASS: {n_cls} filled. The MSC's own classes are kept. Where the star is a whole visual component, the MSC",
        "  component table's class; else a published class for that component; else INFERRED from the MSC mass:",
        f"  the {PM} type whose tabulated mass is nearest (orange). Most inferred ones are spectroscopic or",
        "  astrometric companions that have never been seen separately, so no spectrum of their own exists.",
        f"LUMINOSITY: {n_lit} published for the component alone (cell note cites paper and quote); {n_inf} INFERRED",
        "  (orange): from the paper's R and Teff where it prints no L; else log L interpolated in spectral subtype",
        f"  along the dwarf sequence ({PM_URL}); else, for a class inferred from mass, the",
        "  sequence's L at that type (WEAK). Sequence scatter ~0.1-0.2 dex; valid for main-sequence and brown dwarfs",
        "  only, so never applied to a subgiant, giant or white dwarf.",
        f"LEFT BLANK ({len(blank)}), each with a note saying why: " + ", ".join(
            f"{p['comp']} ({p['why_blank'].split(',')[0]})" for p in blank) + ".",
    ]

    if PLAN:
        from collections import Counter
        print(f"{len(plan)} stars; class filled {n_cls}; L published {n_lit}, inferred {n_inf}, blank {len(blank)}")
        print("by (class source, L source):", dict(Counter(counts)))
        for p in plan:
            if p.get("lum", (0, ""))[1] in ("lit", "lit-RT") or "class" in p and p["class"][1] != "pm-mass":
                print(f"  {p['comp']:30} class {p.get('class')}  L {p.get('lum')}")
        for p in plan[:25]:
            print(f"  .. {p['comp']:30} {p['spt']!s:10} class {p.get('class', ('kept',))[-1]:14} L {p.get('lum')}")
        print(f"orange {len(orange)}, notes {len(notes)}")
        print("\n".join(lines))
        return

    items = list(upd.items())
    for s in range(0, len(items), 400):
        gs.update_cells(SID, dict(items[s:s + 400]))
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
    log = {"stars": len(plan), "class_filled": n_cls, "lum_published": n_lit, "lum_inferred": n_inf,
           "blank": [p["comp"] for p in blank], "orange": len(orange), "sp_rows": [start, end], "title": title}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps(log, ensure_ascii=False))


if __name__ == "__main__":
    main()
