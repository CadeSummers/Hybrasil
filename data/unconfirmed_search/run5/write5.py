# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run 5: the 26 contested confirmed-tab planets (TODO.md; unconfirmed_search.md 8.4), by the owner's rule of 28 Sep 2026.

    python write5.py plan        print every planned write; touches nothing
    python write5.py <step>      run in order; each step asserts its predecessor and refuses to run twice.

The rule:
  A  a later paper argues against the planet and nothing rebuts it -> moved to Unconfirmed, tier `ambiguous` (11).
  B  challenged, then supported by later work                      -> stays confirmed, flags note (8).
  C  its own discovery paper calls it a candidate                  -> stays confirmed, flags note (7).

1  Planets -> Unconfirmed for group A; host Systems / Multi-stars rows (count, mass text, HZ names); a host
   left with no Planets row gets its luminosity typed, since Systems N is a lookup of Planets H.
2  Flags notes for groups B and C, prefixed to 'Orbit data source / flags'.
3  Sources & Provenance block, and the rename.

Evidence: ../run2/agent_output/*.json and ../run3/run2_incidental_finds.txt; GJ 251 c checked against
Beard et al. 2025 on 28 Sep 2026. write_log.json records what each step did.
"""
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from hybrasil.data import google_sheets as gs  # noqa: E402
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
PL, UN, SY, MS, SP = ("Planets within 100 ly", "Unconfirmed within 100 ly", "Systems within 100 ly",
                      "Multi-stars within 100 ly", "Sources & Provenance")
DATE = "2026-09-28"
LOG = HERE / "write_log.json"
log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
PLAN = len(sys.argv) > 1 and sys.argv[1] == "plan"

HARADA = "Harada et al. 2025 (SPORES-HWO II, AJ 170, 343; arXiv:2409.10679)"
FENG20 = "Feng et al. 2020 (ApJS 246, 11; arXiv:2001.02577)"

# --------------------------------------------------------------------------- group A: moved to Unconfirmed
MOVE = {
    "GJ 433 c": f"{FENG20} list it among the planet candidates 'which need to be confirmed'; Tuomi et al. 2019 "
                "(arXiv:1906.04644, App. A.29) find no long-period signal without the UVES data and attribute it to a "
                "UVES barycentric bias. NASA lists it as confirmed (Tuomi et al. 2014).",
    "GJ 180 c": f"{FENG20}, Sect. IV.2: the 24-day signal of Tuomi et al. 2014 'is not found to be significant'; "
                "Mignon et al. 2024 (A&A 689, A32, Table 4) recover only GJ 180 b. Tuomi et al. 2019 still recover it. "
                "NASA lists it as confirmed.",
    "DE CVn b": "NASA pl_controv_flag = 1. Pulley et al. 2022 (MNRAS 514, 5725): 17 eclipse times from 2020-2022 do "
                "not fit the Han et al. 2018 one-planet light-travel-time model; Pulley et al. 2025 (arXiv:2507.06748) "
                "count DE CVn among the post-common-envelope binaries whose published circumbinary models failed to "
                "predict new eclipses.",
    "alf Tau b": "Reichert et al. 2019 (A&A 625, A22; arXiv:1903.09157), 'Evidence against the proposed planet "
                 "Aldebaran b': the ~620 d signal is absent before ~2006, shifts phase, a two-planet fit is unstable, "
                 "and oscillatory convective modes are proposed instead. NASA pl_controv_flag = 1; OEC and exoplanet.eu "
                 "list it as Controversial.",
    "BD-06 1339 b": "Simpson et al. 2022 (AJ 163, 215; arXiv:2203.06191), 'Revisiting BD-06 1339b: A Likely False "
                    "Positive Caused by Stellar Activity': the 3.87 d RV signal is attributed to activity. exoplanet.eu "
                    "no longer lists b.",
    "HD 140901 b": f"NASA pl_controv_flag = 1 (queried 2026-09-27). {HARADA}, App. C.6 and Table 8, list it as a "
                   "'Disputed planet candidate' that their RVs do not recover.",
    "HD 1461 c": "Boulkaboul, Sozzetti, Soubiran & Damerdji 2026 (RAA, doi:10.1088/1674-4527/ae587e; "
                 "arXiv:2604.23694): the 13.5065 d RV signal lies beside a 13.5506 d S-index signal, with positive "
                 "RV-BIS and RV-S correlations; they call its origin 'ambiguous'.",
    "HD 147513 b": f"NASA pl_controv_flag = 1. {HARADA}, App. C.7: adding 46 nights of HARPS RVs to the 30 CORALIE "
                   "RVs makes the 528 d signal vanish, leaving a sub-threshold 504.1 d peak; they call for further "
                   "analysis 'to determine whether HD 147513 b is a real planet'.",
    "61 Vir d": "Rosenthal et al. 2021 (California Legacy Survey, ApJS 255, 8, App. G.1 and Table 7; arXiv:2105.11583): "
                "the 124 d signal sits at 1/3 year with a 1/4-year harmonic and correlates with HIRES PSF parameters; "
                "'we designated the 124 day signal as a yearly systematic.' NASA still lists it (controversial flag 0).",
    "RR Cae b": "NASA pl_controv_flag = 1. Pulley et al. 2025 (arXiv:2507.06748) find that none of the recent "
                "eclipse-timing models (including Rattanamala et al. 2023, which move b to 15.0-16.6 yr) fit the "
                "2022-2025 timings.",
    "GJ 160.2 b": f"{FENG20} 'fail to confirm ... GJ 160.2 b'; the 5.2-day signal 'is unlikely to be Keplerian and "
                  "might arise from data reduction'. Tuomi et al. 2019 (App. A.7) could not recover it either (they "
                  "find 9.75 d). NASA and OEC still list it.",
}
# HZ names on Systems that name a moved planet: {host: (Q now, Q after, P after)}
HZ = {"GJ 180": ("GJ 180 c, GJ 180 d†", "GJ 180 d†", 1), "HD 147513": ("HD 147513 b*", "—", 0)}

# --------------------------------------------------------------------------- groups B and C: stay, with a note
B = "CONTESTED, KEPT CONFIRMED (reviewed 28 Sep 2026): "
C = "CANDIDATE PER ITS DISCOVERY PAPER, KEPT CONFIRMED (reviewed 28 Sep 2026): "
KEEP = {
    "GJ 3998 b": B + "Dodson-Robinson et al. 2022 (arXiv:2201.13342) find high RV-activity coherence at the periods of "
                     "b and c and say they 'may actually be stellar signals'; Stefanov et al. 2025 (arXiv:2503.08405) "
                     "confirm both with more HARPS-N data.",
    "BD-210397 b": B + "exoplanet.eu lists it as Unconfirmed, citing Philipot et al. 2023 (no evidence, doubtful "
                       "stability); it is supported by Frensch et al. 2023, by an independent detection in Tuomi et "
                       "al. 2019 (GJ 1044 b, 1721 d), and NASA lists it as confirmed.",
    "GJ 15 A b": B + "Trifonov et al. 2018 (CARMENES, arXiv:1710.01595) did not detect it and suggest the 11.4 d "
                     "signal may be activity; Pinamonti et al. 2018 recovered it. NASA and exoplanet.eu list it as "
                     "confirmed.",
    "nu Oct A b": B + "NASA pl_controv_flag = 1 and OEC 'Controversial', for its dynamically extreme retrograde "
                      "orbit; Ramm et al. 2021 (MNRAS 502, 2793; arXiv:2101.06844) find no activity explanation.",
    "eps Eri b": B + "OEC files it under 'Controversial'; every recent analysis treats it as real (Laliotis et al. "
                     "2023; Harada et al. 2025, SPORES-HWO II; Llop-Sayson et al. 2026).",
    "HD 115404 A b": B + f"{HARADA}, App. C.5, cannot recover either Feng et al. 2022 planet (b or c) from 95 "
                         "ELODIE/HIRES/SOPHIE RVs and call both disputed, since the discovery paper gives no "
                         "system-specific analysis. NASA does not flag them.",
    "GJ 3323 c": C + "Astudillo-Defru et al. 2017 (A&A 602, A88, Sect. 4.3.2): 'GJ 3323c should be considered a planet "
                     "candidate' (P = 40.54 d, near the ~33 d expected rotation). NASA, exoplanet.eu and OEC list it "
                     "as confirmed; no later paper either way.",
    "HD 177565 b": C + "Feng et al. 2017 (MNRAS 470, 4794, Sect. 4.5; arXiv:1705.03089) call it a planet candidate "
                       "(68 HARPS points, K = 2.71 m/s); exoplanet.eu status Candidate. NASA and OEC list it as "
                       "confirmed; no independent confirmation found.",
    "HD 21411 b": C + "one of the '15 planet candidates found in PFS data' of Feng et al. 2019 (ApJS 242, 25; "
                      "arXiv:1904.08567); NASA and exoplanet.eu now list it as confirmed. One signal; no follow-up "
                      "found.",
    "HD 39855 b": C + "one of the '15 planet candidates found in PFS data' of Feng et al. 2019 (ApJS 242, 25; "
                      "arXiv:1904.08567); NASA and exoplanet.eu now list it as confirmed. One signal; no follow-up "
                      "found.",
    "GJ 9689 b": C + "Maldonado et al. 2021 (A&A 651, A93; arXiv:2105.06155) call it a candidate in their title; its "
                     "period is close to half the star's rotation period.",
    "Gl 725 A b": C + "Cortes-Zuleta et al. 2025 (A&A 693, A164; arXiv:2411.09506) call it a 'potential super-Earth' "
                      "and a 'low-mass planet candidate'; NASA lists it as confirmed.",
    "GJ 251 c": C + "Beard et al. 2025 (AJ 170, 279; arXiv:2510.19956) present it as a candidate: 'Stellar activity can masquerade "
                    "as planetary signals, and we cannot eliminate this possibility entirely.' They argue against rotation (P_rot ~122 d from photometry; 54 d is no "
                    "harmonic of it; the signal is strongest in the infrared). CARMENES DR1 (Ribas et al. 2023, "
                    "arXiv:2302.10528, Table C.1) labels a 53.65 d signal 'rotation'; Beard et al. do not address "
                    "that label directly.",
}
KEEP["GJ 3998 c"] = KEEP["GJ 3998 b"]
KEEP["HD 115404 A c"] = KEEP["HD 115404 A b"]


# --------------------------------------------------------------------------- sheet helpers (as write3.py)
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
    if tab not in _HDR:
        _HDR[tab] = {h: col_letter(i) for i, h in enumerate(values(f"{q(tab)}!A1:AZ1")[0])}
    return _HDR[tab]


def row_of(tab, name, col="A"):
    v = values(f"{q(tab)}!{col}1:{col}2000")
    hits = [i + 1 for i, r in enumerate(v) if r and r[0] == name]
    assert len(hits) == 1, (tab, name, hits)
    return hits[0]


def last_data_row(tab):
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
    if reqs and not PLAN:
        API.batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()
    gs.invalidate_cache(SID)


def extend_filter(tab, end_row):
    f = [s for s in API.get(spreadsheetId=SID, fields="sheets(properties(title),basicFilter)").execute()["sheets"]
         if s["properties"]["title"] == tab][0].get("basicFilter")
    if f and f["range"].get("endRowIndex") != end_row:
        batch([{"setBasicFilter": {"filter": dict(f, range=dict(f["range"], endRowIndex=end_row))}}])


def _ix(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def write(upd, expect=None, value_input="RAW"):
    if PLAN:
        for k, v in upd.items():
            print(f"  WRITE {k} = {str(v)[:140]!r}" + (f"   (expect {str(expect[k])[:60]!r})" if expect and k in expect
                                                        else ""))
        return
    gs.update_cells(SID, upd, expect=expect, value_input=value_input)


def notes(n):
    if PLAN:
        for k, v in n.items():
            print(f"  NOTE  {k}: {v[:140]}")
        return
    gs.set_note(SID, n)


def save_log():
    if not PLAN:
        LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")


def remove_mass_line(name):
    """Drop the 'name:mass' line from every Systems / Multi-stars mass-text cell that carries it."""
    upd, exp = {}, {}
    for tab in (SY, MS):
        c = H(tab)["Planet masses (M-earth)"]
        for i, r in enumerate(values(f"{q(tab)}!{c}1:{c}2000"), start=1):
            if r and isinstance(r[0], str) and any(ln.startswith(name + ":") for ln in r[0].split("\n")):
                upd[f"{q(tab)}!{c}{i}"] = "\n".join(ln for ln in r[0].split("\n") if not ln.startswith(name + ":"))
                exp[f"{q(tab)}!{c}{i}"] = r[0]
    return upd, exp


# =========================================================================== step 1
def step1():
    assert PLAN or "step1" not in log
    hp, hu, hs, hm = H(PL), H(UN), H(SY), H(MS)
    assert list(hu)[:42] == list(hp)[:42], "Planets and Unconfirmed columns no longer line up"
    src = {nm: row_of(PL, nm) for nm in MOVE}
    rows = {nm: values(f"{q(PL)}!A{r}:AQ{r}", formula=True)[0] for nm, r in src.items()}
    for nm, r in rows.items():
        assert r[_ix(hp["Confidence tier"])] == "confirmed", (nm, r[_ix(hp["Confidence tier"])])
    hosts = {nm: r[1] for nm, r in rows.items()}
    pl_hosts = [r[0] if r else "" for r in values(f"{q(PL)}!B1:B2000")]

    # 1a  hosts that will have no Planets row left: type their luminosity before the lookup loses its source.
    lum_upd, lum_exp, lum_notes, orphaned = {}, {}, {}, []
    for nm, host in hosts.items():
        if pl_hosts.count(host) == sum(1 for h in hosts.values() if h == host):
            orphaned.append(host)
            r = row_of(SY, host)
            f = values(f"{q(SY)}!N{r}", formula=True)[0][0]
            assert str(f).startswith("=") and "'Planets within 100 ly'!$H$" in f, (host, f)
            cur = values(f"{q(SY)}!N{r}")[0][0]
            assert isinstance(cur, (int, float)) and cur > 0, (host, cur)
            cell = f"{q(SY)}!N{r}"
            lum_upd[cell] = cur
            lum_notes[cell] = (f"TYPED {DATE}: this cell was a lookup of Planets column H. {nm}, the host's only "
                               f"planet row, moved to Unconfirmed as contested, so the value ({cur}) is kept as it "
                               f"was. Its source is that planet's host luminosity, now on Unconfirmed column H.")
    print("step 1a: host luminosity typed for", orphaned)
    write(lum_upd)          # the value is the formula's own result: no expect needed beyond the asserts above
    notes(lum_notes)

    # 1b  append the moved rows to Unconfirmed, from its last data row as the template.
    last = last_data_row(UN)
    n = len(MOVE)
    assert not values(f"{q(UN)}!A{last + 1}:B{last + n}"), "rows below Unconfirmed data are not empty"
    tmpl_f = values(f"{q(UN)}!A{last}:AP{last}", formula=True)[0]
    batch([{"copyPaste": {"source": grid(UN, last - 1, last, 0, 42), "destination": grid(UN, last, last + n, 0, 42),
                          "pasteType": "PASTE_NORMAL"}}])
    upd, formulas, placed = {}, {}, {}
    for k, nm in enumerate(MOVE):
        r = last + 1 + k
        prow = rows[nm]
        get = lambda h: prow[_ix(hp[h])] if _ix(hp[h]) < len(prow) else ""
        for h, c in hu.items():
            t = tmpl_f[_ix(c)] if _ix(c) < len(tmpl_f) else ""
            cell = f"{q(UN)}!{c}{r}"
            if h == "Radius (R-Jup)":
                v = get(h)                       # Unconfirmed's template carries the fixed 1.03 R-earth formula
                if str(v).startswith("="):
                    formulas[cell] = re.sub(r"(?<!!)\$C\$", "'Planets within 100 ly'!$C$", v)
                else:
                    upd[cell] = v
            elif not str(t).startswith("="):
                v = get(h)
                assert not str(v).startswith("="), (nm, h, v)
                upd[cell] = v
        upd[f"{q(UN)}!{hu['Confidence tier']}{r}"] = "ambiguous"
        upd[f"{q(UN)}!{hu['Vetting date / last updated']}{r}"] = DATE
        upd[f"{q(UN)}!{hu['Orbit data source / flags']}{r}"] = (
            f"MOVED FROM PLANETS {DATE} (was tiered confirmed), CONTESTED: {MOVE[nm]} || {get('Orbit data source / flags')}")
        placed[nm] = r
    if PLAN:
        print(f"step 1b: copy Unconfirmed row {last} to {last + 1}..{last + n}; then, for {list(MOVE)[0]}:")
        write({k: v for k, v in upd.items() if k.endswith(f"{last + 1}")})
        write({k: v for k, v in formulas.items() if k.endswith(f"{last + 1}")})
    else:
        write(upd, expect={f"{q(UN)}!A{last}": tmpl_f[0]})
        if formulas:
            write(formulas, value_input="USER_ENTERED")
        extend_filter(UN, last + n)

    # 1c  delete from Planets, bottom up, each checked by name.
    order = sorted(((row_of(PL, nm), nm) for nm in MOVE), reverse=True)
    print("step 1c: delete Planets rows", order)
    batch([{"deleteDimension": {"range": {"sheetId": sheet_id(PL), "dimension": "ROWS", "startIndex": r - 1,
                                          "endIndex": r}}} for r, _ in order])
    if not PLAN:
        names = [r[0] if r else "" for r in values(f"{q(PL)}!A1:A2000")]
        assert not any(nm in names for nm in MOVE)      # the Planets filter range shrinks with the deletes

    # 1d  host rows: planet count, mass text, mass type, HZ names; Multi-stars count and mass text.
    su, se = {}, {}
    for nm in MOVE:
        u, e = remove_mass_line(nm)
        su.update(u)
        se.update(e)
    for host in sorted(set(hosts.values())):
        k = sum(1 for h in hosts.values() if h == host)
        r = row_of(SY, host)
        cur = values(f"{q(SY)}!F{r}")[0][0]
        su[f"{q(SY)}!{hs['Confirmed planets']}{r}"] = cur - k
        se[f"{q(SY)}!{hs['Confirmed planets']}{r}"] = cur
        if host in orphaned:
            mt = values(f"{q(SY)}!{hs['Mass type']}{r}")
            su[f"{q(SY)}!{hs['Mass type']}{r}"] = ""
            se[f"{q(SY)}!{hs['Mass type']}{r}"] = mt[0][0] if mt else ""
        if host in HZ:
            now, after, p = HZ[host]
            su[f"{q(SY)}!{hs['HZ planet names']}{r}"] = after
            se[f"{q(SY)}!{hs['HZ planet names']}{r}"] = now
            su[f"{q(SY)}!{hs['Planets in HZ']}{r}"] = p
        ms_hosts = values(f"{q(MS)}!A1:A2000")
        for i, mr in enumerate(ms_hosts, start=1):
            if mr and mr[0] == host:
                c = hm["Confirmed planets"]
                mcur = values(f"{q(MS)}!{c}{i}")[0][0]
                su[f"{q(MS)}!{c}{i}"] = mcur - k
                se[f"{q(MS)}!{c}{i}"] = mcur
    print("step 1d: host cells")
    write(su, expect=se)
    log["step1"] = {"unconfirmed_rows": placed, "planets_deleted": {nm: r for r, nm in order},
                    "luminosity_typed": orphaned, "host_cells": list(su)}
    save_log()
    print("step 1 done:", placed)


# =========================================================================== step 1e
# Systems O (HZ distance) is also a lookup of the host's Planets rows (columns I:L), and read 'no luminosity on
# file' once step 1 left these five hosts with none. Restored as typed text, exactly as the 27 Sep snapshot
# (data/hy-brasil-20260927-1851.xlsx, no sheet edits between it and step 1) had it. The 'Teff outside' text is the
# formula's fallback for a planet row with blank HZ bounds, not a statement about the star; kept as it was.
HZ_TEXT = {
    "DE CVn": "Teff outside 2600-7200 K\n(Kopparapu limits do not apply)",
    "alf Tau": "17.777 - 45.527\n(conservative: 23.584 - 43.344)",
    "HD 147513": "Teff outside 2600-7200 K\n(Kopparapu limits do not apply)",
    "RR Cae": "Teff outside 2600-7200 K\n(Kopparapu limits do not apply)",
    "GJ 160.2": "Teff outside 2600-7200 K\n(Kopparapu limits do not apply)",
}


def step1e():
    assert PLAN or ("step1" in log and "step1e" not in log)
    upd, exp, n = {}, {}, {}
    for host, text in HZ_TEXT.items():
        r = row_of(SY, host)
        cell = f"{q(SY)}!O{r}"
        upd[cell] = text
        exp[cell] = "no luminosity on file"
        n[cell] = (f"TYPED {DATE}: this cell was a lookup of the host's Planets rows (columns I:L); its only planet "
                   f"moved to Unconfirmed as contested. Text restored as it read on 27 Sep 2026.")
    write(upd, expect=exp)
    notes(n)
    log["step1e"] = list(upd)
    save_log()
    print("step 1e done:", list(upd))


# =========================================================================== step 2
def step2():
    assert PLAN or ("step1e" in log and "step2" not in log)
    c = H(PL)["Orbit data source / flags"]
    tc = H(PL)["Confidence tier"]
    upd, exp = {}, {}
    for nm, text in KEEP.items():
        r = row_of(PL, nm)
        cur, tier = (values(f"{q(PL)}!{c}{r}") or [[""]])[0][0], values(f"{q(PL)}!{tc}{r}")[0][0]
        assert tier == "confirmed" and not str(cur).startswith(("CONTESTED", "CANDIDATE PER")), (nm, tier, cur)
        upd[f"{q(PL)}!{c}{r}"] = f"{text} || {cur}" if cur else text
        exp[f"{q(PL)}!{c}{r}"] = cur
    write(upd, expect=exp)
    log["step2"] = {"flag_cells": {nm: cell for nm, cell in zip(KEEP, upd)}}
    save_log()
    print("step 2 done:", len(upd), "flag notes")


# =========================================================================== step 3
def step3():
    assert PLAN or ("step2" in log and "step3" not in log)
    import textwrap
    wrap = lambda s: textwrap.wrap(s, 110, initial_indent="  ", subsequent_indent="    ")
    lines = ["",
             "RUN 5, 28 SEPTEMBER 2026: THE 26 CONTESTED CONFIRMED-TAB PLANETS (TODO.md; unconfirmed_search.md 8.4).",
             "Evidence: run-2 agent records (data/unconfirmed_search/run2/agent_output/, run3/run2_incidental_finds.txt);",
             "GJ 251 c checked against Beard et al. 2025 the same day. Writer: run5/write5.py; log write_log.json.",
             "The owner's rule: a planet a later paper argues against, with nothing rebutting it, moves to Unconfirmed",
             "tiered 'ambiguous' (drawn, not rejected); a planet challenged and then supported, or one its own discovery",
             "paper calls a candidate, stays confirmed with a note at the front of its 'Orbit data source / flags'.",
             "", "1. MOVED TO UNCONFIRMED (tier ambiguous), each with its reason in 'Orbit data source / flags':"]
    for nm, why in MOVE.items():
        lines += wrap(f"{nm}: {why}")
    lines += wrap("Host Systems rows: 'Confirmed planets', 'Planet masses' and (GJ 180, HD 147513) the HZ names "
                  "updated; Multi-stars counts for HD 140901, HD 147513 and RR Cae. DE CVn, alf Tau, HD 147513, "
                  "RR Cae and GJ 160.2 now have no Planets row, so their Systems 'Host luminosity' (a lookup of "
                  "Planets column H) is typed at the same value, and 'HZ distance' (a lookup of Planets I:L) is "
                  "typed as it read on 27 Sep 2026; both carry a cell note.")
    lines += ["", "2. KEPT CONFIRMED, NOTE ADDED: challenged, then supported by later work:"]
    lines += wrap("GJ 3998 b/c (Stefanov et al. 2025), BD-210397 b (Tuomi et al. 2019; Frensch et al. 2023), GJ 15 A b "
                  "(Pinamonti et al. 2018), nu Oct A b (Ramm et al. 2021), eps Eri b (only OEC flags it), HD 115404 A "
                  "b/c (Harada et al. 2025 cannot recover them; NASA does not flag them).")
    lines += ["", "3. KEPT CONFIRMED, NOTE ADDED: their own discovery paper calls them candidates:"]
    lines += wrap("GJ 3323 c, HD 177565 b, HD 21411 b, HD 39855 b, GJ 9689 b, Gl 725 A b, and GJ 251 c (Beard et al. "
                  "2025 argue against rotation, but call it a candidate because activity cannot be excluded).")
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    rows = meta["gridProperties"]["rowCount"]
    last = values(f"{q(SP)}!A{rows}")
    assert last and last[0][0].strip(), ("last Sources & Provenance row is empty", rows)
    start, end = rows + 1, rows + len(lines)
    if PLAN:
        print(f"step 3: append {len(lines)} rows at {start}..{end}:")
        print("\n".join(lines))
        return
    batch([{"appendDimension": {"sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}])
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    log["step3"] = {"sp_rows": [start, end], "heading": start + 1, "title": title}
    save_log()
    print("step 3 done:", log["step3"])


if __name__ == "__main__":
    if PLAN:
        step1(); step2(); step3()
    else:
        {"1": step1, "1e": step1e, "2": step2, "3": step3}[sys.argv[1]]()
