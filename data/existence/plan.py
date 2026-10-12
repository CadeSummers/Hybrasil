# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Step 2: decide every new cell, from live.json and the catalog caches.  Touches nothing on the sheet.

    python plan.py         plan.json + a summary

Per row of each tab (keyed by name + Gaia id):
  SIMBAD main_id   SIMBAD's own name for the object: by its Gaia DR3 identifier, else its exact name (a Planetless row
                   by the MSC's SimbadName), else -- orange, INFERRED -- the system's name or the nearest SIMBAD object
                   (kinematics/simbad.py's match for the Known tab's CNS5 rows).
  CNS5 id          (Known only) the CNS5 number: by Gaia DR3 id in CNS5 itself, else the source list's 'CNS5 n' row.
  Existence        'confirmed: <catalogs>' where a curated catalog lists the object (SIMBAD, CNS5, the MSC, the NASA
                   Exoplanet Archive); 'unconfirmed: only cited in Gaia DR3' where Gaia DR3 is the only one.
  Kinematics refs  'RV: <refs>; PM: <refs>', each ref a catalog name, ADS bibcode, DOI or URL, read from the motion
                   cells' own SOURCE notes and the Kinematics source column.
"""
import re
from collections import Counter

import openpyxl

from common import (CNS5_DAT, H_CNS5, H_DE, H_EXIST, H_KS, H_NAME, H_PMDE, H_PMRA, H_RA, H_REFS, H_RV, H_SID,
                    H_SIMBAD, KIN, LIVE, PLAN, SIMBAD_IDS, SOURCE_LIST, TABS, blank, gaia_of, key_of, load, name_of,
                    now, num, save)
from msc import components

HIPPARCOS_2007 = "2007A&A...474..653V"
BIBCODE = re.compile(r"\b(1[89]\d\d|20\d\d)[A-Za-z&.][A-Za-z&.]{4}[\dA-Za-z.]{4}[A-Za-z.][\d.]{4}[A-Z.]\b")
URL = re.compile(r"<(https?://[^>\s]+)>|\b(https?://[^\s,;)>]+)")
ARXIV = re.compile(r"arXiv[: ]\s*((?:astro-ph/)?\d{4}\.\d{4,5}|astro-ph/\d{7})", re.I)
DOI = re.compile(r"\b(10\.\d{4,9}/[^\s,;)>]+)")
# Known-tab rows renamed to the name the plotting tab uses, after the tab was built from the source list
# (data/known_within_100ly/match.json): live name -> the source list's 'GJ n component'.  Checked by position below.
RENAMED_CNS5 = {"alf Cen A": "GJ 559 AB", "GJ 667 A": "GJ 667 AB", "HD 62509": "GJ 286", "alf Ari": "GJ 84.3",
                "alf Tau": "GJ 171.1 A"}


def primary_bare(name):
    """'eps Ind A' -> 'eps Ind', 'GJ 1006 Aa' -> 'GJ 1006'; None for anything that is not a primary component."""
    m = re.fullmatch(r"(.+?)\s+Aa?", name.strip())
    return m.group(1) if m else None


def cns5_catalog():
    """{Gaia DR3 id: CNS5 number} and {CNS5 number: (GJ, component)} from cns5.dat (byte layout per its ReadMe)."""
    by_gaia, rec = {}, {}
    for line in CNS5_DAT.read_text(encoding="ascii", errors="replace").splitlines():
        if not line.strip():
            continue
        n = int(line[0:4])
        gj, comp = line[5:11].strip(), line[12:16].strip()
        g = line[27:46].strip()
        rec[n] = (gj, comp)
        if g.isdigit():
            by_gaia[g] = n
    return by_gaia, rec


def source_list_cns5():
    """[(CNS5 number, 'GJ n', component, RA, Dec)] for the source list's CNS5 rows (the Known tab was built from it)."""
    wb = openpyxl.load_workbook(SOURCE_LIST, read_only=True)
    rows = list(wb["Nearby stars"].iter_rows(min_row=5, values_only=True))
    h = list(rows[0])
    c = {k: h.index(k) for k in ("Catalog ID", "Other ID", "Component", "RA (deg)", "Dec (deg)")}
    out = []
    for r in rows[1:]:
        cid = str(r[c["Catalog ID"]] or "")
        if cid.startswith("CNS5 "):
            out.append((int(cid[5:]), str(r[c["Other ID"]] or "").strip(), str(r[c["Component"]] or "").strip(),
                        num(r[c["RA (deg)"]]), num(r[c["Dec (deg)"]])))
    return out


def refs_in(text, note=True):
    """Every reference a SOURCE note or Kinematics source string names, in order, de-duplicated."""
    if not text:
        return []
    out = []
    # A catalog counts where it is the note's source, not where the text merely mentions it ('Gaia DR3 has none',
    # 'matched by Gaia DR3 identifier'): the head of a SOURCE note, or the whole of a short Kinematics source half.
    if not note:
        head = text                            # a Kinematics source half names its sources and nothing else
    elif text.startswith("SOURCE:"):
        head = re.split(r"[(:,]", text[7:], maxsplit=1)[0]
    else:
        head = ""                              # a free-text note: only its bibcodes, DOIs and URLs count
    for cat in ("Gaia DR3", "Gaia DR2", "CNS5", "MSC"):
        if re.search(rf"\b{cat}\b", head):
            out.append(cat)
    if "van Leeuwen 2007" in head:
        out.append(HIPPARCOS_2007)
    urls = [a or b for a, b in URL.findall(text)]
    out += [u.rstrip(".") for u in urls]
    linked = " ".join(urls)
    out += [m.group(0) for m in BIBCODE.finditer(text) if m.group(0) not in linked]
    out += [f"arXiv:{a}" for a in ARXIV.findall(text) if a not in linked]
    out += [f"doi:{d.rstrip('.')}" for d in DOI.findall(text) if d not in linked]
    if not out and re.search(r"\bSIMBAD\b", head):
        out.append("SIMBAD")                   # SIMBAD's adopted value with no bibcode: the star's SIMBAD page
    return list(dict.fromkeys(out))


def refs_cell(rv_note, pm_note, ks_rv, ks_pm):
    rv = refs_in(rv_note) if rv_note else refs_in(ks_rv, note=False)
    pm = refs_in(pm_note) if pm_note else refs_in(ks_pm, note=False)
    parts = ([f"RV: {', '.join(rv)}"] if rv else []) + ([f"PM: {', '.join(pm)}"] if pm else [])
    return "; ".join(parts)


def split_ks(ks):
    """A Kinematics source string's RV and PM halves ('RV: x; PM: y | flags')."""
    head = ks.split("|")[0]
    rv = re.search(r"RV:\s*([^;|]*)", head)
    pm = re.search(r"PM:\s*([^;|]*)", head)
    return (rv.group(1) if rv else ""), (pm.group(1) if pm else "")


def main():
    live = load(LIVE)
    simb = load(SIMBAD_IDS)
    by_gaia_simbad, by_name_simbad = simb["by_gaia"], simb["by_name"]
    nogaia = {r["k"]: r for r in load(KIN / "cat" / "simbad_nogaia.json")["rows"]}
    fid = load(KIN / "cat" / "fidelity.json")["rows"]
    cns5_by_gaia, cns5_rec = cns5_catalog()
    cns5_list = source_list_cns5()
    msc = components()

    plan = {"built": now(), "read_from": live["read_from"], "tabs": {}}
    summary = {}
    for key, t in TABS.items():
        tab = live["tabs"][key]
        h, rows, notes = tab["headers"], tab["rows"], tab["notes"]
        col = {k: i for i, k in enumerate(h)}
        out, count = {}, Counter()
        cns5_left = list(cns5_list) if key == "known" else []
        for i, r in enumerate(rows):
            name = name_of(r, col, t)
            if not name:
                continue
            k = key_of(r, col, t)
            assert k not in out, f"{t['tab']}: two rows are {k}"
            g = gaia_of(r, col)
            if name == "Sun":
                out[k] = {"cells": {H_EXIST: {"value": "reference: the Sun"}}}
                continue
            if key == "planetless" and str(r[col["Node type"]]).strip().lower() not in ("", "star"):
                continue                                   # a barycentre is not an object to look up
            cells = {}
            # -- SIMBAD
            sim, how = None, None
            if g and g in by_gaia_simbad:
                sim, how = by_gaia_simbad[g], "Gaia DR3 identifier"
            elif name in by_name_simbad:
                sim, how = by_name_simbad[name], "name"
            elif key == "planetless":
                c = msc.get((str(r[col["WDS code"]]).strip(), str(r[col["MSC label"]]).strip()))
                sn = str(c.get("SimbadName") or "").strip() if c else ""
                if sn in by_name_simbad:
                    sim, how = by_name_simbad[sn], f"the MSC's SIMBAD name '{sn}'"
            if sim is None and key == "known" and not g and k in nogaia:
                m = nogaia[k]
                sim, how = m["main_id"], m["how"]
                if m.get("component_risk"):
                    how += "; a component row matched at system level or by position -- may be its primary"
            if sim is None and key != "known":
                # A primary ('eps Ind A', 'nu Oct Aa') is the object SIMBAD files under the system's bare name; a
                # secondary is not, so it gets no fallback.
                alt = primary_bare(name)
                if alt in by_name_simbad:
                    sim, how = by_name_simbad[alt], f"the system's name '{alt}', which SIMBAD gives its primary"
            if sim:
                sim = re.sub(r"\s+", " ", sim).strip()
                inferred = how not in ("Gaia DR3 identifier", "name") and not how.startswith("the MSC's")
                note = (f"INFERRED: SIMBAD object matched by {how} (SIMBAD TAP, {simb['queried'][:10]}); not by an "
                        "identifier this row carries." if inferred else None)
                cells[H_SIMBAD] = {"value": sim, "mark": "orange" if inferred else "plain", "note": note}
                count["simbad " + ("inferred" if inferred else "looked up")] += 1
            # -- CNS5 (Known only)
            cns = None
            if key == "known":
                if g and g in cns5_by_gaia:
                    cns = cns5_by_gaia[g]
                elif not g:
                    ra, de = num(r[col[H_RA]]), num(r[col[H_DE]])
                    was = RENAMED_CNS5.get(name, name)
                    hit = [x for x in cns5_left if f"{x[1]} {x[2]}".strip() == was]
                    if name in RENAMED_CNS5:
                        assert len(hit) == 1 and abs(hit[0][3] - ra) < 0.05 and abs(hit[0][4] - de) < 0.05, name
                    if len(hit) != 1:
                        hit = [x for x in cns5_left if ra is not None and x[3] is not None
                               and abs(x[3] - ra) < 1e-6 and abs(x[4] - de) < 1e-6]
                    if len(hit) == 1:
                        cns = hit[0][0]
                        cns5_left.remove(hit[0])
                    else:
                        count["no-Gaia row with no CNS5 match"] += 1
                if cns is not None:
                    cells[H_CNS5] = {"value": f"CNS5 {cns}", "mark": "plain"}
                    count["cns5"] += 1
            # -- Existence
            cats = []
            if key == "planetless" and str(r[col["WDS code"]]).strip():
                cats.append("MSC")
            if sim:
                cats.append("SIMBAD")
            if cns is not None:
                cats.append("CNS5")
            if key == "systems" and (num(r[col["Confirmed planets"]]) or 0) > 0:
                cats.append("NASA Exoplanet Archive")
            if g:
                cats.append("Gaia DR3")
            if set(cats) - {"Gaia DR3"}:
                cells[H_EXIST] = {"value": "confirmed: " + ", ".join(cats), "mark": "plain"}
                count["confirmed"] += 1
            elif g:
                f = (fid.get(g) or {}).get("fidelity_v2")
                fv = f" (fidelity_v2 {f:.2f})" if f is not None else ""
                cells[H_EXIST] = {
                    "value": f"unconfirmed: only cited in Gaia DR3{fv}", "mark": "plain",
                    "note": ("Gaia DR3 is the only catalog that lists this object: SIMBAD has no entry for its Gaia "
                             "DR3 identifier and CNS5 does not list it."
                             + (f" Gaia's spurious-astrometry score fidelity_v2 is {f:.2f} (Rybizki et al. 2022, "
                                "MNRAS 510, 2597; below 0.5 means the parallax is probably spurious)." if f is not None
                                else ""))}
                count["unconfirmed"] += 1
            else:
                count["no catalog at all"] += 1
            # -- Kinematics refs
            rv_n, pm_n = notes[H_RV][i], (notes[H_PMRA][i] or notes[H_PMDE][i])
            ks_rv, ks_pm = split_ks(str(r[col[H_KS]] or ""))
            refs = refs_cell(rv_n, pm_n, ks_rv, ks_pm)
            if refs:
                cells[H_REFS] = {"value": refs, "mark": "plain"}
                count["refs"] += 1
            # never touch a cell already filled
            for hd in list(cells):
                if hd in col and not blank(r[col[hd]]):
                    del cells[hd]
                    count[f"already filled: {hd}"] += 1
            out[k] = {"name": name, "gaia": g, "cells": cells}
        plan["tabs"][key] = out
        summary[key] = dict(count)
        if key == "known":
            summary[key]["CNS5 source-list rows unmatched"] = len(cns5_left)
    plan["summary"] = summary
    save(PLAN, plan)
    for key, s in summary.items():
        print(key, s)


if __name__ == "__main__":
    main()
