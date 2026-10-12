# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run 3: apply the agents' records (../agent_output/*.json) to the live workbook, one guarded step at a time.

    python write3.py <step>      run in order; each step asserts its predecessor and refuses to run twice.

1  Planets: correct 15 rows' values (W1), rename two, fix the stale WD 1856 flag; Unconfirmed: TOI-4353.01's period.
2  Systems: Gaia distances for GJ 3222, HD 8326, GJ 9689, TOI-1801 (+ kinematics); notes on 7 CMa, gam Cep, HIP 86221.
3  Gaia ids: Kapteyn, 55 Cnc A/B, GJ 338 A/B (with GJ 338 A's own astrometry and recomputed kinematics).
4  Reject nine planets (R1): Planets -> Rejected candidates; host Systems rows updated.
5  Multi-stars: 22 systems' star rows (C1, C2, C3, R1); Systems star counts; GJ 680's class.
6  New planets (M1): TOI-2427 c, TOI-2267 b/c/d, Gliese 48 b, TOI-4324 b; two new Systems rows; TOI-2267 A/B stars.
7  Sources & Provenance block, and the rename.

Every value written comes from an agent record that names its source; derived values get the orange
border and a note carrying the method. write_log.json records what each step did.
"""
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "agent_output"
sys.path.insert(0, str(HERE.parents[3]))
from hybrasil.data import google_sheets as gs  # noqa: E402
import time  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402
from googleapiclient.http import HttpRequest  # noqa: E402

_execute = HttpRequest.execute


def _execute_with_retry(self, *a, **k):
    """The Sheets API allows 60 reads a minute; wait out a 429 rather than stop half-way through a step."""
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
PL, UN, RJ, SY, MS = ("Planets within 100 ly", "Unconfirmed within 100 ly", "Rejected candidates",
                      "Systems within 100 ly", "Multi-stars within 100 ly")
SP = "Sources & Provenance"
DATE = "2026-09-27"
LOG = HERE / "write_log.json"
log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
REC = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in OUT.glob("*.json")}


def items(agent, action=None, tab=None):
    for it in REC[agent]["items"]:
        a = it["action"] if isinstance(it["action"], list) else [it["action"]]
        if (action is None or action in a) and (tab is None or (it.get("tab") or "").startswith(tab)):
            yield it


# --------------------------------------------------------------------------- sheet helpers
def q(t):
    return "'" + t.replace("'", "''") + "'"


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def values(rng, formula=False):
    return API.values().get(spreadsheetId=SID, range=rng,
                            valueRenderOption="FORMULA" if formula else "UNFORMATTED_VALUE").execute().get("values", [])


_HDR = {}


def H(tab):
    """{header: column letter} for a tab."""
    if tab not in _HDR:
        _HDR[tab] = {h: col_letter(i) for i, h in enumerate(values(f"{q(tab)}!A1:AZ1")[0])}
    return _HDR[tab]


def column_a(tab):
    return [r[0] if r else "" for r in values(f"{q(tab)}!A1:A2000")]


def row_of(tab, name, col="A"):
    v = values(f"{q(tab)}!{col}1:{col}2000")
    hits = [i + 1 for i, r in enumerate(v) if r and r[0] == name]
    assert len(hits) == 1, (tab, name, hits)
    return hits[0]


def last_data_row(tab):
    """Data ends at the first row with at most one filled cell (the loader's rule)."""
    v = values(f"{q(tab)}!A1:E2000")
    n = 1
    for i, r in enumerate(v[1:], start=2):
        if sum(1 for c in r if str(c).strip()) <= 1:
            break
        n = i
    return n


def sheet_id(tab):
    return gs._sheet_ids(SID)[tab]


def grid(tab, r0, r1, c0, c1):
    return {"sheetId": sheet_id(tab), "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def batch(reqs):
    if reqs:
        API.batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()
    gs.invalidate_cache(SID)


def extend_filter(tab, end_row):
    f = [s for s in API.get(spreadsheetId=SID, fields="sheets(properties(title),basicFilter)").execute()["sheets"]
         if s["properties"]["title"] == tab][0].get("basicFilter")
    if f and f["range"].get("endRowIndex") != end_row:
        batch([{"setBasicFilter": {"filter": dict(f, range=dict(f["range"], endRowIndex=end_row))}}])


def typed_columns(tab, row):
    """Columns of a template row that hold values, not formulas."""
    f = values(f"{q(tab)}!A{row}:AZ{row}", formula=True)[0]
    hdr = H(tab)
    return [c for h, c in hdr.items() if not str(f[_ix(c)] if _ix(c) < len(f) else "").startswith("=")]


def _ix(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def save_log():
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")


def mark(orange, notes):
    for i in range(0, len(orange), 80):
        gs.set_border(SID, orange[i:i + 80], gs.INFERRED_BORDER)
    if notes:
        gs.set_note(SID, notes)


def derived_note(v):
    src = v.get("source") or ""
    return f"INFERRED: {v.get('method') or 'derived'} Source: {src}"[:1500]


def fmt_mass(m):
    return f"{m:.0f}" if abs(m) >= 1000 else f"{m:.2f}"


def replace_mass_line(old_name, new_line, remove=False):
    """Rewrite the 'name:mass' line for a planet in every Systems Z / Multi-stars AB cell that carries it."""
    upd, exp = {}, {}
    for tab, header in ((SY, "Planet masses (M-earth)"), (MS, "Planet masses (M-earth)")):
        c = H(tab)[header]
        v = values(f"{q(tab)}!{c}1:{c}2000")
        for i, r in enumerate(v, start=1):
            if not r or not isinstance(r[0], str):
                continue
            lines = r[0].split("\n")
            hit = [k for k, ln in enumerate(lines) if ln.startswith(old_name + ":")]
            if not hit:
                continue
            new = [ln for k, ln in enumerate(lines) if k not in hit] if remove else \
                [new_line if k == hit[0] else ln for k, ln in enumerate(lines) if k == hit[0] or k not in hit]
            upd[f"{q(tab)}!{c}{i}"] = "\n".join(new)
            exp[f"{q(tab)}!{c}{i}"] = r[0]
    return upd, exp


# --------------------------------------------------------------------------- kinematics (method of S&P 3982-3985, 4039-4040)
def kinematics(ra, dec, d_ly, pmra, pmdec, rv):
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    mu = math.hypot(pmra, pmdec) / 1000
    c = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)
    out = {"AE": round(mu, 3), "AG": round(c.galactic.l.deg, 2), "AH": round(c.galactic.b.deg, 2)}
    if rv in ("", None):
        return dict(out, AF="", AI="", AJ="")
    g = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, distance=(d_ly / 3.26156) * u.pc, pm_ra_cosdec=pmra * u.mas / u.yr,
                 pm_dec=pmdec * u.mas / u.yr, radial_velocity=rv * u.km / u.s).galactic
    U, V, W = g.velocity.d_xyz.to(u.km / u.s).value
    s = math.sqrt(U * U + V * V + W * W)
    return dict(out, AF=round(math.hypot(rv, 4.74047 * mu * d_ly / 3.26156), 2),
                AI=round(math.degrees(math.atan2(V, U)) % 360, 2), AJ=round(math.degrees(math.asin(W / s)), 2))


MOTION_NOTE = ("INFERRED: direction the star is moving, relative to the Sun, in galactic l/b. From RA/Dec, distance (C), "
               "RV and proper motions (AB:AD) via astropy; no LSR correction. Its speed reproduces Space velocity (AF). "
               "Recomputed 27 Sep 2026: {why}")


# =========================================================================== step 1
def step1():
    assert "step1" not in log
    hp = H(PL)
    upd, formulas, orange, notes, done = {}, {}, [], {}, {}
    text_upd, text_exp = {}, {}
    for it in items("W1"):
        old = (it.get("current") or {}).get("Planet", it["name"])
        r = row_of(PL, old)
        upd_row = {}
        for k, v in it["fields"].items():
            if k.startswith("Systems within 100 ly row"):
                continue
            cell = f"{q(PL)}!{hp['Radius (R-Jup)'] if k == 'Radius (R-earth)' else hp[k]}{r}"
            if k == "Radius (R-earth)":
                const = re.search(r"\$C\$(\d+)", values(f"{q(PL)}!U{r}", formula=True)[0][0]).group(1)
                formulas[cell] = f"={v['value']}/$C${const}"
            else:
                upd[cell] = v["value"]
            upd_row[k] = v["value"]
            if v.get("derived"):
                orange.append(cell)
                notes[cell] = derived_note(v)
        done[old] = {"row": r, "fields": upd_row}
        # the host's 'name:mass' line
        f = it["fields"]
        new_name = f.get("Planet", {}).get("value", old)
        mt = f.get("Mass type", {}).get("value", (it.get("current") or {}).get("Mass type", ""))
        m = f.get("Mass (M-earth)", {}).get("value", (it.get("current") or {}).get("Mass (M-earth)"))
        if old == "TOI-2427 b" or m in ("", None):
            continue                      # TOI-2427's whole cell is rewritten in step 6
        cur = it.get("current") or {}
        sign = "<" if "upper" in str(mt) else ">" if "lower" in str(mt) else ""
        if new_name == old and not sign and float(m) == float(cur.get("Mass (M-earth)") or -1)                 and "likely BD" not in str(cur.get("Orbit data source / flags", "")):
            continue                      # name and mass unchanged: leave the line alone
        line = f"{new_name}:{sign}{fmt_mass(float(m))}"
        if old == "GJ 508.2 b":
            line += " (>1.85 MJ)"
        elif float(m) >= 318:
            line += f" ({float(m) / 317.828:.2f} MJ)"
        u, e = replace_mass_line(old, line)
        text_upd.update(u)
        text_exp.update(e)
    # Unconfirmed: TOI-4353.01's period (M1); the radius is left as it is.
    hu = H(UN)
    it = next(items("M1", "correct_values", "Unconfirmed"))
    r = row_of(UN, "TOI-4353.01")
    for k in ("Orbital period (d)", "Semi-major axis (au)", "Orbit data source / flags"):
        v = it["fields"][k]
        cell = f"{q(UN)}!{hu[k]}{r}"
        upd[cell] = v["value"]
        if v.get("derived"):
            orange.append(cell)
            notes[cell] = derived_note(v)
    done["TOI-4353.01"] = {"row": r}
    gs.update_cells(SID, {**upd, **text_upd}, expect=text_exp)
    gs.update_cells(SID, formulas, value_input="USER_ENTERED")
    mark(orange, notes)
    log["step1"] = {"rows": done, "text_cells": list(text_upd), "orange": orange}
    save_log()
    print("step 1 done:", len(upd), "values,", len(formulas), "radius formulas,", len(text_upd), "mass-text cells,",
          len(orange), "orange")


# =========================================================================== step 2
DIST = {  # Gaia DR3 parallax (mas), queried 2026-09-27
    "GJ 3222": 56.556967342552554, "HD 8326": 32.56471150776688,
    "GJ 9689": 32.587878933269494, "TOI-1801": 32.36972061451368,
}
KEEP = {
    "7 CMa": "NOT CHANGED 27 Sep 2026: 64.61 ly is the Hipparcos (van Leeuwen 2007) parallax, 50.63 +/- 0.23 mas. "
             "Gaia DR3 gives 48.85 +/- 0.13 mas (66.77 ly) but with RUWE 2.37 at G = 3.7, where Gaia's astrometry of "
             "bright stars is unreliable, so Hipparcos is kept.",
    "gam Cep": "NOT CHANGED 27 Sep 2026: 46 ly is the Hipparcos (van Leeuwen 2007) parallax, 70.91 +/- 0.40 mas. Gaia "
               "DR3 gives 72.52 +/- 0.15 mas (44.98 ly) with RUWE 3.21 at G = 2.9, perturbed by the 20 au companion; "
               "Van Zandt et al. 2026 adopt 72.5 mas. Kept pending a decision.",
    "HIP 86221": "NOT CHANGED 27 Sep 2026: 96.18 ly is the Hipparcos (van Leeuwen 2007) parallax, 33.91 +/- 3.88 mas "
                 "(+/- 11 ly). Gaia DR3 has no parallax for the unresolved A+B pair. Its bound component C (Gaia DR3 "
                 "4595441868000475520) has 31.07 mas = 104.99 ly, so the system probably lies BEYOND 100 LY; kept by "
                 "the owner's decision of 27 Sep 2026.",
}


def step2():
    assert "step1" in log and "step2" not in log
    hs = H(SY)
    upd, exp, orange, notes, done = {}, {}, [], {}, {}
    for name, plx in DIST.items():
        r = row_of(SY, name)
        row = values(f"{q(SY)}!A{r}:AP{r}")[0]
        get = lambda c: row[_ix(c)] if _ix(c) < len(row) else ""
        old = get("C")
        d = round(3261.56 / plx, 2)
        k = kinematics(get("AO"), get("AP"), d, get("AC"), get("AD"), get("AB"))
        exp[f"{q(SY)}!C{r}"] = old
        upd[f"{q(SY)}!C{r}"] = d
        for c in ("AF", "AI", "AJ"):
            if get(c) not in ("", None):
                upd[f"{q(SY)}!{c}{r}"] = k[c]
        beyond = " BEYOND 100 LY: kept by the owner's decision of 27 Sep 2026." if d > 100 else ""
        orange.append(f"{q(SY)}!C{r}")
        notes[f"{q(SY)}!C{r}"] = (f"INFERRED: 3.26156 * 1000 / {plx:.3f} mas, the Gaia DR3 parallax. Replaces {old} ly, the "
                                  f"NASA archive's sy_dist.{beyond}")
        for c in ("AI", "AJ"):
            if get(c) not in ("", None):
                notes[f"{q(SY)}!{c}{r}"] = MOTION_NOTE.format(why=f"at the corrected distance ({d} ly; was {old}).")
        done[name] = {"row": r, "old": old, "new": d, "kin": {c: k[c] for c in ("AF", "AI", "AJ")}}
    for name, text in KEEP.items():
        r = row_of(SY, name)
        notes[f"{q(SY)}!C{r}"] = text
    gs.update_cells(SID, upd, expect=exp)
    mark(orange, notes)
    log["step2"] = done
    save_log()
    print("step 2 done:", json.dumps(done))


# =========================================================================== step 3
def step3():
    assert "step2" in log and "step3" not in log
    hs, hm = H(SY), H(MS)
    upd, exp, orange, notes = {}, {}, [], {}
    for it in items("M1", "set_gaia_id"):
        tab = SY if it["tab"].startswith("Systems") else MS
        hdr = hs if tab == SY else hm
        r = row_of(tab, it["name"], "A" if tab == SY else "B")
        for k, v in it["fields"].items():
            cell = f"{q(tab)}!{hdr[k]}{r}"
            upd[cell] = str(v["value"]) if k == "Gaia DR3 source_id" else v["value"]
            cur = (it.get("current") or {}).get(k)
            if cur is not None and k != "Gaia DR3 source_id":
                exp[cell] = cur
    gs.update_cells(SID, upd, expect=exp)
    # GJ 338 A: recompute its kinematics from its own astrometry; GJ 338 A/B Multi-stars totals too.
    r = row_of(SY, "GJ 338 A")
    row = values(f"{q(SY)}!A{r}:AP{r}")[0]
    get = lambda c: row[_ix(c)] if _ix(c) < len(row) else ""
    k = kinematics(get("AO"), get("AP"), get("C"), get("AC"), get("AD"), get("AB"))
    kupd = {f"{q(SY)}!{c}{r}": k[c] for c in ("AE", "AF", "AG", "AH", "AI", "AJ")}
    for c in ("AI", "AJ"):
        notes[f"{q(SY)}!{c}{r}"] = MOTION_NOTE.format(why="from GJ 338 A's own Gaia DR3 astrometry; the row carried "
                                                           "GJ 338 B's id, RV and proper motion until then.")
    notes[f"{q(SY)}!{hs['Gaia DR3 source_id']}{r}"] = ("CORRECTED 27 Sep 2026: this row carried GJ 338 B's id "
                                                        "(1022456104850892928), RA/Dec, RV and proper motion.")
    for comp in ("GJ 338 A", "GJ 338 B"):
        rm = row_of(MS, comp, "B")
        mrow = values(f"{q(MS)}!A{rm}:AT{rm}")[0]
        g = lambda h: mrow[_ix(hm[h])] if _ix(hm[h]) < len(mrow) else ""
        pmra, pmdec, rv, d = (g("Proper motion in RA, μα·cos δ (mas/yr)"), g("Proper motion in Dec, μδ (mas/yr)"),
                              g("Radial velocity (km/s)"), g("Distance (ly)"))
        mu = math.hypot(pmra, pmdec) / 1000
        kupd[f"{q(MS)}!{hm['Total proper motion, μ (arcsec/yr)']}{rm}"] = round(mu, 3)
        kupd[f"{q(MS)}!{hm['Space velocity (km/s)']}{rm}"] = round(math.hypot(rv, 4.74047 * mu * d / 3.26156), 2)
        kupd[f"{q(MS)}!{hm['Kinematics source']}{rm}"] = f"RV: Gaia DR3; PM: Gaia DR3 (own source, corrected {DATE})"
    gs.update_cells(SID, kupd)
    mark(orange, notes)
    log["step3"] = {"ids": list(upd), "gj338a_kinematics": k}
    save_log()
    print("step 3 done:", len(upd), "id/astrometry cells; GJ 338 A kinematics", k)


# =========================================================================== step 4
def step4():
    assert "step3" in log and "step4" not in log
    hp, hr = H(PL), H(RJ)
    rej = list(items("R1", "reject"))
    src = {it["name"]: row_of(PL, it["name"]) for it in rej}
    typed = [c for c in typed_columns(PL, src[rej[0]["name"]]) if c in hr.values()]
    last = last_data_row(RJ)
    tmpl = last
    n = len(rej)
    assert not values(f"{q(RJ)}!A{last+1}:A{last+n+1}"), "rows below Rejected data are not empty"
    batch([{"appendDimension": {"sheetId": sheet_id(RJ), "dimension": "ROWS", "length": n}}]
          if last + n > API.get(spreadsheetId=SID, ranges=[f"{q(RJ)}!A1"], fields="sheets(properties(gridProperties))")
          .execute()["sheets"][0]["properties"]["gridProperties"]["rowCount"] else [])
    batch([{"copyPaste": {"source": grid(RJ, tmpl - 1, tmpl, 0, 43), "destination": grid(RJ, last, last + n, 0, 43),
                          "pasteType": "PASTE_NORMAL"}}])
    upd, placed = {}, {}
    for k, it in enumerate(rej):
        r = last + 1 + k
        prow = values(f"{q(PL)}!A{src[it['name']]}:AQ{src[it['name']]}")[0]
        for c in typed:
            if c == "AQ":
                continue
            upd[f"{q(RJ)}!{c}{r}"] = prow[_ix(c)] if _ix(c) < len(prow) else ""
        f = it["fields"]
        upd[f"{q(RJ)}!{hr['Rejected because']}{r}"] = f["Rejected because"]["value"]
        upd[f"{q(RJ)}!{hr['Confidence tier']}{r}"] = f["Confidence tier"]["value"]
        upd[f"{q(RJ)}!{hr['Vetting date / last updated']}{r}"] = DATE
        if "Source / discovery reference" in f:
            upd[f"{q(RJ)}!{hr['Source / discovery reference']}{r}"] = f["Source / discovery reference"]["value"]
        flags = prow[_ix(hp["Orbit data source / flags"])] if _ix(hp["Orbit data source / flags"]) < len(prow) else ""
        upd[f"{q(RJ)}!{hr['Orbit data source / flags']}{r}"] = (f"MOVED FROM PLANETS {DATE} (was tiered confirmed). || "
                                                                 + str(flags))
        placed[it["name"]] = r
    gs.update_cells(SID, upd, expect={f"{q(RJ)}!A{last}": values(f"{q(RJ)}!A{last}")[0][0]})
    extend_filter(RJ, last + n)
    # Delete from Planets, bottom up, each checked by name.
    rows = sorted(((row_of(PL, nm), nm) for nm in src), reverse=True)
    batch([{"deleteDimension": {"range": {"sheetId": sheet_id(PL), "dimension": "ROWS", "startIndex": r - 1,
                                          "endIndex": r}}} for r, _ in rows])
    assert all(nm not in column_a(PL) for nm in src)
    # Host Systems rows, and any Multi-stars mass line.
    hs = H(SY)
    su, se = {}, {}
    for it in items("R1", "update_host", "Systems"):
        r = row_of(SY, it["name"])
        for k, v in it["fields"].items():
            if k in ("Stars in system", "System stars"):
                continue          # step 5 writes these from the star rows themselves
            su[f"{q(SY)}!{hs[k]}{r}"] = v["value"]
        se[f"{q(SY)}!A{r}"] = it["name"]
    for nm in src:
        u, e = replace_mass_line(nm, None, remove=True)
        for cell in list(u):
            if cell.startswith(q(SY)):
                u.pop(cell)
                e.pop(cell)
        su.update(u)
        se.update(e)
    gs.update_cells(SID, su, expect=se)
    log["step4"] = {"rejected_rows": placed, "planets_deleted": {nm: r for r, nm in rows}, "systems_cells": list(su)}
    save_log()
    print("step 4 done:", placed)


# =========================================================================== step 5
MS_GROUPS = [  # (agent, System / Host); host row first, then companions parents-first
    ("R1", "GJ 680"), ("R1", "HIP 55507"),
    ("C1", "gam Cep"), ("C1", "nu Oct A"), ("C1", "HD 27442"), ("C1", "HD 19994"), ("C1", "GJ 86"), ("C1", "HD 204941"),
    ("C1", "HD 86728"),
    ("C2", "HD 46375"), ("C2", "HD 147513"), ("C2", "GJ 3222"), ("C2", "HD 147379"), ("C2", "TOI-1801"),
    ("C2", "Ross 458"), ("C2", "TOI-1452"),
    ("C3", "HD 99492"), ("C3", "HD 6660"), ("C3", "HIP 87773"), ("C3", "GJ 65"), ("C3", "61 Cyg A"),
]
GJ680_CLASS = ("M1.5 V", 61.5, "CORRECTED 27 Sep 2026 from K5: SIMBAD gives M1.5V and Gaia DR3 GSP-Phot Teff 3235 K "
                               "(R1 research record, run 3).")


def star_rows(agent, system):
    """The host row, then companions ordered so that each parent precedes its child."""
    host = [it for it in items(agent, "add_host_row") if it["fields"]["System / Host"]["value"] == system]
    comps = [it for it in REC[agent]["items"]
             if (it["action"] in ("add_companion", "reclassify_as_star"))
             and it["fields"]["System / Host"]["value"] == system]
    assert len(host) == 1 and comps, (agent, system, len(host), len(comps))
    ordered, placed = [host[0]], {host[0]["fields"]["Star (component)"]["value"]}
    while comps:
        nxt = [c for c in comps if c["fields"].get("Separation from", {}).get("value") in placed] or comps[:1]
        ordered.append(nxt[0])
        placed.add(nxt[0]["fields"]["Star (component)"]["value"])
        comps.remove(nxt[0])
    return ordered


def write_star_rows(groups, extra_fields=None):
    """Append star rows for [(system, [records])] to Multi-stars; returns {component: row}."""
    hm, hs = H(MS), H(SY)
    tmpl = row_of(MS, "alf Cen B", "B")
    typed = typed_columns(MS, tmpl)
    last = last_data_row(MS)
    recs = [(system, rec) for system, rs in groups for rec in rs]
    n = len(recs)
    rc = API.get(spreadsheetId=SID, ranges=[f"{q(MS)}!A1"], fields="sheets(properties(gridProperties))").execute()[
        "sheets"][0]["properties"]["gridProperties"]["rowCount"]
    assert last + n <= rc and not values(f"{q(MS)}!A{last+1}:B{last+n}")
    batch([{"copyPaste": {"source": grid(MS, tmpl - 1, tmpl, 0, 46), "destination": grid(MS, last, last + n, 0, 46),
                          "pasteType": "PASTE_NORMAL"}}])
    upd, orange, notes, placed = {}, [], {}, {}
    for k, (system, rec) in enumerate(recs):
        r = last + 1 + k
        f = dict(rec["fields"])
        f.update((extra_fields or {}).get(f["Star (component)"]["value"], {}))
        sr = row_of(SY, system)
        srow = values(f"{q(SY)}!A{sr}:AP{sr}")[0]
        f["Distance (ly)"] = {"value": srow[_ix(hs["Distance (ly)"])]}      # the Systems row's (corrected) distance
        f["Stars in system"] = {"value": sum(len(rs) for s, rs in groups if s == system)}
        f.setdefault("Confirmed planets", {"value": srow[_ix(hs["Confirmed planets"])]})
        for c in typed:
            h = next(h for h, cc in hm.items() if cc == c)
            v = f.get(h, {}).get("value", "")
            upd[f"{q(MS)}!{c}{r}"] = "" if v is None else (str(v) if h == "Gaia DR3 source_id" and v != "" else v)
            if f.get(h, {}).get("derived") and v not in ("", None):
                orange.append(f"{q(MS)}!{c}{r}")
                notes[f"{q(MS)}!{c}{r}"] = derived_note(f[h])
        placed[f["Star (component)"]["value"]] = r
    gs.update_cells(SID, upd, expect={f"{q(MS)}!B{tmpl}": "alf Cen B"})
    extend_filter(MS, last + n)
    mark(orange, notes)
    # Systems: star count and the System stars text, generated from the rows just written.
    su = {}
    for system, rs in groups:
        sr = row_of(SY, system)
        lines = []
        for rec in rs:
            f = rec["fields"]
            cls = (f.get("Stellar Class") or {}).get("value") or "class unknown"
            role = (f.get("Role in system") or {}).get("value") or ""
            lines.append(f"{f['Star (component)']['value']}: {cls}" + (f" ({role})" if role else ""))
        su[f"{q(SY)}!{hs['Stars in system']}{sr}"] = len(rs)
        su[f"{q(SY)}!{hs['System stars']}{sr}"] = "\n".join(lines)
    gs.update_cells(SID, su)
    return placed, len(orange)


def step5():
    assert "step4" in log and "step5" not in log
    groups = [(system, star_rows(agent, system)) for agent, system in MS_GROUPS]
    extra = {"GJ 680": {"Stellar Class": {"value": GJ680_CLASS[0]}, "Class (sort key)": {"value": GJ680_CLASS[1]}}}
    placed, n_orange = write_star_rows(groups, extra)
    # GJ 680's Systems class was K5; the star is M1.5 V.
    hs = H(SY)
    r = row_of(SY, "GJ 680")
    gs.update_cells(SID, {f"{q(SY)}!{hs['Stellar Class']}{r}": GJ680_CLASS[0],
                          f"{q(SY)}!{hs['Class (sort key)']}{r}": GJ680_CLASS[1]},
                    expect={f"{q(SY)}!{hs['Stellar Class']}{r}": "K5"})
    gs.set_note(SID, {f"{q(SY)}!{hs['Stellar Class']}{r}": GJ680_CLASS[2]})
    log["step5"] = {"multistars_rows": placed, "orange": n_orange}
    save_log()
    print("step 5 done:", len(placed), "star rows,", n_orange, "orange")


# =========================================================================== step 6
TOI2267_STARS = [
    {"System / Host": "TOI-2267 A", "Star (component)": "TOI-2267 A", "Role in system": "host, planet host",
     "Mass (M-sun)": 0.171, "Stellar Class": "M5 V", "Effective temp (K)": 3030, "Luminosity (L-sun)": 0.0033,
     "Star data source": "Zuniga-Fernandez et al. 2025 (arXiv:2508.14176), Tables 2 and 4",
     "Planet-host star": "TOI-2267 A", "Planet-host class": "M5 V", "Gaia DR3 source_id": "571488283984760960"},
    {"System / Host": "TOI-2267 A", "Star (component)": "TOI-2267 B", "Role in system": "planet host",
     "Mass (M-sun)": 0.0989, "Stellar Class": "M6 V", "Effective temp (K)": 2930, "Luminosity (L-sun)": 0.0011,
     "Star data source": "Zuniga-Fernandez et al. 2025 (arXiv:2508.14176), Tables 2 and 4",
     "Planet-host star": "TOI-2267 B", "Planet-host class": "M6 V",
     "Primary mass (M-sun)": 0.171, "Separation from": "TOI-2267 A", "Separation type": "projected",
     "Separation source": "Zuniga-Fernandez et al. 2025 (arXiv:2508.14176): 0.384-0.408 arcsec; Gaia DR3 does not "
                          "resolve the pair (one source, RUWE 13.7)"},
]
SORT_KEY = {"M5 V": 65, "M3.5 V": 63.5}


def step6():
    assert "step5" in log and "step6" not in log
    hs, hp, hu = H(SY), H(PL), H(UN)
    # 6a  two new Systems rows, inside the pinned range (before its last row)
    new_sys = [it for it in items("M1", "update_host", "Systems") if it["name"] in ("TOI-2267 A", "Gliese 48")]
    last = last_data_row(SY)
    at = last - 1
    tmpl = row_of(SY, "Wolf 359")
    n = len(new_sys)
    batch([{"insertDimension": {"range": {"sheetId": sheet_id(SY), "dimension": "ROWS", "startIndex": at,
                                          "endIndex": at + n}, "inheritFromBefore": True}}])
    tmpl = row_of(SY, "Wolf 359")
    batch([{"copyPaste": {"source": grid(SY, tmpl - 1, tmpl, 0, 42), "destination": grid(SY, at, at + n, 0, 42),
                          "pasteType": "PASTE_NORMAL"}}])
    styped = typed_columns(SY, tmpl)
    su, orange, notes = {}, [], {}
    for k, it in enumerate(new_sys):
        r = at + 1 + k
        f = it["fields"]
        for c in styped:
            h = next(h for h, cc in hs.items() if cc == c)
            v = f.get(h, {}).get("value", "")
            su[f"{q(SY)}!{c}{r}"] = "" if v is None else (str(v) if h == "Gaia DR3 source_id" and v != "" else v)
            if f.get(h, {}).get("derived") and v not in ("", None):
                orange.append(f"{q(SY)}!{c}{r}")
                notes[f"{q(SY)}!{c}{r}"] = derived_note(f[h])
        su[f"{q(SY)}!{hs['Class (sort key)']}{r}"] = SORT_KEY[f["Stellar Class"]["value"]]
    gs.update_cells(SID, su, expect={f"{q(SY)}!A{at+1}": "Wolf 359"})
    # TOI-2267 B's separation: projected, 0.396" (mean of 0.384-0.408) x the Systems distance.
    d_ly = values(f"{q(SY)}!C{row_of(SY, 'TOI-2267 A')}")[0][0]
    sep = round(0.396 * d_ly / 3.26156, 1)
    stars = [{h: {"value": v} for h, v in s.items()} for s in TOI2267_STARS]
    stars[1]["Separation (AU)"] = {"value": sep, "derived": True,
                                   "method": f"0.396 arcsec (mean of the paper's 0.384-0.408) x {d_ly} ly / 3.26156 = "
                                             f"{sep} au, a projected separation; +/- 0.5 au from the arcsec range.",
                                   "source": "Zuniga-Fernandez et al. 2025 (arXiv:2508.14176)"}
    placed_ms, _ = write_star_rows([("TOI-2267 A", [{"fields": s} for s in stars])])
    # 6b  Planets: append the new rows (template: the last planet row), then move TOI-4324.01 in.
    adds = list(items("M1", "add_planet"))
    mv = next(items("M1", "move_to_planets"))
    last = last_data_row(PL)
    tmpl = last
    n = len(adds) + 1
    batch([{"insertDimension": {"range": {"sheetId": sheet_id(PL), "dimension": "ROWS", "startIndex": last,
                                          "endIndex": last + n}, "inheritFromBefore": True}}])
    batch([{"copyPaste": {"source": grid(PL, tmpl - 1, tmpl, 0, 43), "destination": grid(PL, last, last + n, 0, 43),
                          "pasteType": "PASTE_NORMAL"}}])
    ptyped = typed_columns(PL, tmpl)
    aq = values(f"{q(PL)}!{hp['Spin-orbit angle (deg, vs stellar spin axis)']}{tmpl}")
    un_r = row_of(UN, "TOI-4324.01")
    un_row = values(f"{q(UN)}!A{un_r}:AP{un_r}")[0]
    pu, placed = {}, {}
    for k, it in enumerate(adds + [mv]):
        r = last + 1 + k
        f = it["fields"]
        base = {} if it is not mv else {h: {"value": un_row[_ix(c)] if _ix(c) < len(un_row) else ""}
                                        for h, c in hu.items() if c in ptyped}
        base.update(f)
        if f["Planet"]["value"] == "Gliese 48 b":
            base["Orbit data source / flags"] = {"value": (
                "WEAK -- an amateur re-analysis of archival RVs (Conzo, Moriconi & Correa Jr. 2026, OEJV), not yet "
                "confirmed by an independent team; NASA lists it as confirmed. || " + f["Orbit data source / flags"]["value"])}
        for c in ptyped:
            h = next(h for h, cc in hp.items() if cc == c)
            if h == "Spin-orbit angle (deg, vs stellar spin axis)":
                pu[f"{q(PL)}!{c}{r}"] = aq[0][0] if aq else ""
                continue
            v = base.get(h, {}).get("value", "")
            pu[f"{q(PL)}!{c}{r}"] = "" if v is None else v
            if base.get(h, {}).get("derived") and v not in ("", None):
                orange.append(f"{q(PL)}!{c}{r}")
                notes[f"{q(PL)}!{c}{r}"] = derived_note(base[h])
        placed[f["Planet"]["value"]] = r
    gs.update_cells(SID, pu, expect={f"{q(PL)}!A{tmpl}": values(f"{q(PL)}!A{tmpl}")[0][0]})
    extend_filter(PL, last + n)
    batch([{"deleteDimension": {"range": {"sheetId": sheet_id(UN), "dimension": "ROWS", "startIndex": un_r - 1,
                                          "endIndex": un_r}}}])
    # 6c  host updates: TOI-2427 and HIP 47619
    hu2 = {}
    for it in items("M1", "update_host", "Systems"):
        if it["name"] in ("TOI-2267 A", "Gliese 48"):
            continue
        r = row_of(SY, it["name"])
        for k, v in it["fields"].items():
            hu2[f"{q(SY)}!{hs[k]}{r}"] = v["value"]
    gs.update_cells(SID, hu2)
    mark(orange, notes)
    log["step6"] = {"systems_rows": {it["name"]: at + 1 + k for k, it in enumerate(new_sys)}, "planets_rows": placed,
                    "multistars_rows": placed_ms, "unconfirmed_deleted": un_r, "toi2267_sep_au": sep}
    save_log()
    print("step 6 done:", log["step6"])


# =========================================================================== step 7
def step7():
    assert "step6" in log and "step7" not in log
    import textwrap
    L = log
    lines = [
        "",
        "RUN 3, 27 SEPTEMBER 2026: THE REST OF THE CONFIRMED-TAB ERRORS, AND THE MISSING DATA (unconfirmed_search.md 8.4).",
        "Research: six agents (W1, R1, C1, C2, C3, M1), records in the repo at data/unconfirmed_search/run3/agent_output/,",
        "each value with the paper or catalogue query it came from. Writer: run3/writer/write3.py; log write_log.json.",
        "Derived values carry an orange border and a note with the method, as always.",
        "",
        "1. PLANETS VALUES CORRECTED (W1): new sources in each row's 'Orbit data source / flags'.",
    ]
    for it in items("W1"):
        old = (it.get("current") or {}).get("Planet", it["name"])
        ch = ", ".join(f"{k.split(' (')[0]} {(it.get('current') or {}).get(k, '')} -> {v['value']}"
                       for k, v in it["fields"].items() if k not in ("Orbit data source / flags",)
                       and not k.startswith("Systems within"))
        lines += textwrap.wrap(f"{old}: {ch}. {it.get('reason', '')}", 110, initial_indent="  ",
                               subsequent_indent="    ")
    lines += ["  TOI-4353.01 (Unconfirmed): P 718.18 -> 39.8991 d (Tschudi 2026, arXiv:2607.23781, unrefereed); a derived.",
              "  Stale 'likely BD' text on WD 1856+534 b removed from Planets, Systems and Multi-stars.", "",
              "2. DISTANCES (Gaia DR3 parallax, 3.26156 * 1000 / plx; orange): "
              + "; ".join(f"{k} {v['old']} -> {v['new']} ly" for k, v in L["step2"].items()) + ".",
              "  HD 8326, GJ 9689, TOI-1801 lie just BEYOND 100 LY, as does HIP 86221 probably (via its bound C). Kept and",
              "  flagged in the cell notes, by the owner's decision. 7 CMa and gam Cep keep Hipparcos (Gaia RUWE 2.4 / 3.2",
              "  on bright stars). Space velocity and motion direction recomputed at the new distances.", "",
              "3. GAIA DR3 IDS (M1): Kapteyn 4810594479418041856; 55 Cnc A 704967037090946688 (Systems and Multi-stars),",
              "  55 Cnc B 704966762213039488; GJ 338 A 1022456139210632064. GJ 338 A's rows carried B's id, RA/Dec, RV and",
              "  proper motion; A now has its own and B has B's. GJ 338 A's kinematics recomputed.", "",
              "4. REJECTED (R1), moved from Planets to Rejected candidates with the reason in 'Rejected because':"]
    for it in items("R1", "reject"):
        lines += textwrap.wrap(f"{it['name']}: {it['fields']['Rejected because']['value']}", 110, initial_indent="  ",
                               subsequent_indent="    ")
    lines += ["  Host Systems rows: planet count, masses and HZ names updated.", "",
              "5. STARS ADDED TO MULTI-STARS (C1, C2, C3, R1): " + ", ".join(L["step5"]["multistars_rows"]) + ".",
              "  GJ 680 B and HIP 55507 B are the former planets 'GJ 680 b' and 'HIP 55507 b'. GJ 65 A/B and 61 Cyg A/B",
              "  let their candidates draw. Separation type 'semi-major axis' where an orbit is solved, else 'projected'.",
              "  Systems 'Stars in system' and 'System stars' rewritten from the new rows. GJ 680's class K5 -> M1.5 V.", "",
              "6. NEW PLANETS (M1): " + ", ".join(L["step6"]["planets_rows"]) + ". New Systems rows TOI-2267 A and",
              "  Gliese 48; TOI-2267 A/B on Multi-stars (B at a derived projected separation). Gliese 48 b is WEAK: an",
              "  amateur re-analysis of archival RVs (Conzo et al. 2026, OEJV), and CARMENES DR1 attributes this star's",
              "  strongest RV signal to activity; NASA lists it as confirmed. TOI-4324 b moved from Unconfirmed",
              "  (Collier et al. 2026, Table 3). TOI-2267 d's host star (B) follows NASA; the papers cannot tell.",
              "", "Not changed, recorded: the agents' incidental finds are in their JSON files (e.g. GJ 86's age, 61 Cyg A's",
              "[Fe/H] sign, host masses for gam Cep, HD 150706, HD 27442, HD 204941, and 14 Her b / GJ 3929 b hybrids)."]
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    rows = meta["gridProperties"]["rowCount"]
    last = values(f"{q(SP)}!A{rows}")
    assert last and last[0][0].startswith("(1.05 au) now has a position"), last
    start, end = rows + 1, rows + len(lines)
    batch([{"appendDimension": {"sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}])
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    log["step7"] = {"sp_rows": [start, end], "heading": start + 1, "title": title}
    save_log()
    print("step 7 done:", log["step7"])


if __name__ == "__main__":
    {"1": step1, "2": step2, "3": step3, "4": step4, "5": step5, "6": step6, "7": step7}[sys.argv[1]]()
