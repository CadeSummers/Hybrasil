# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fill the blank 'Luminosity (L-sun)' of the 49 stars that drew no solvent band (9 Oct 2026).

    python fill_missing_lum.py          plan: print every write; touches nothing
    python fill_missing_lum.py write    write values, borders, notes, provenance; rename

TODO.md listed 51 stars with no luminosity, 49 after GJ 310.1 Bb became a planet and GJ 275.2 Ab was rejected.
They are on two tabs: Planetless 4+ Stars and Multi-stars within 100 ly (ups And B, featured, is a Multi-stars row).
Four research passes read the literature for them (lum_research/*.json, BRIEF.md: paper, identifier, URL and a
verbatim quote for every number). No value is taken from Wikipedia, so nothing is pink; the Wikipedia pages were
read and the numbers they cite are in the records. In tiers, as fill.py's 29 Sep pass:

1. PUBLISHED for this component alone: plain, the cell note cites the source.
2. DERIVED from published inputs (R and Teff, a resolved M_bol, a blend split by a delta-mag, V plus a bolometric
   correction), or a published whole-light value assigned to the component: ORANGE, the note gives the arithmetic.
3. INFERRED FROM MASS, WEAK: a companion nobody has seen (hypothetical, or an unseen SB1 secondary) takes the
   Pecaut & Mamajek dwarf sequence's L at the type whose tabulated mass is nearest, as fill.py's last tier did.
   The owner's decision of 9 Oct 2026. ORANGE.
4. FLOOR, WEAK, POSSIBLE BROWN DWARF: an assumed mass below the sequence's last tabulated mass (L2V, 0.075 M-sun,
   log L -3.82) takes that row's L, an upper bound if it is a brown dwarf. The seven are flagged in the Star data
   source cell and in TODO.md; they stay stars under section 6 for now (owner, 9 Oct 2026). ORANGE.
5. BLANK, with a note saying why: white dwarfs with no Teff, companions of undecided nature, and two companions the
   literature doubts exist.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.argv, _argv = sys.argv[:1], sys.argv[1:]          # fill.py reads sys.argv at import
import fill as F  # noqa: E402

sys.argv += _argv
gs, q, letter, sig, API, SID = F.gs, F.q, F.letter, F.sig, F.API, F.SID
PLAN = _argv != ["write"]
LOG = HERE / "fill_missing_lum_log.json"
PL, MS, SP = "Planetless 4+ Stars", "Multi-stars within 100 ly", "Sources & Provenance"
DATE = "9 Oct 2026"
PM, PM_URL = F.PM, F.PM_URL

RECORDS = {}
for f in ("evolved", "companions_a", "companions_b", "unseen"):
    for r in json.loads((HERE / "lum_research" / f"{f}.json").read_text(encoding="utf-8")):
        RECORDS[r["component"]] = dict(r, _file=f"lum_research/{f}.json")

# Tier 1 and 2: star -> (tab, how, value, weak, note lead). 'how' is 'lit' (plain) or 'inf' (orange).
# The value is the record's, except where a record gives a reason to differ (said in the lead).
RESEARCHED = {
    "ups And B": (MS, "lit", None, False, ""),
    "GJ 644 C": (PL, "lit", None, False,
                 "This row is the MSC's component C = GJ 643 = Wolf 629 = HIP 82809 (M3.5 V), the star this L is "
                 "for. SIMBAD's 'GJ 644 C' is vB 8, the MSC's F. "),
    "HD 23439 Ba": (MS, "lit", None, False,
                    "TIC's distance is 24.16 pc, the workbook's 23.86 pc: at the workbook's it would be 0.199. "),
    "iot UMa Aa": (PL, "inf", None, False,
                   "INFERRED (attribution): the published L is the whole light of iot UMa A, assigned to Aa because "
                   "Ab is most likely a white dwarf (Zhuchkov et al. 2012); even a 0.75 Msun dwarf would add ~2%. "
                   "Gaia RUWE 4.84. "),
    "chi Cet Aa": (PL, "inf", None, False,
                   "INFERRED (attribution): the published L is the whole light of chi Cet A, assigned to Aa because "
                   "the astrometric Ab (~0.58 Msun, K9-M0 V) adds ~1.3% bolometrically. "),
    "tau Cyg Aa": (PL, "inf", None, False, ""),
    "alf2 Lib Aa": (PL, "inf", None, False, ""),
    "kap Tuc Aa": (PL, "inf", None, False,
                   "DISTANCE: this L is at Tokovinin 2020's 47.66 mas (68.4 ly); the workbook's 75.87 ly is A's own "
                   "Gaia parallax, corrupted by the Aa,Ab orbit (RUWE 10.4). At 75.87 ly it would be 4.85. "),
    "ksi Sco A": (PL, "inf", None, False, ""),
    "nu Sco Da": (PL, "inf", None, True,
                  "Da+Db together (unresolved); Db's own row is a mass-inferred 0.04 Lsun, so nearly all is Da's. "),
    "GJ 684 A": (MS, "inf", None, False, ""),
    "GJ 684 B": (MS, "inf", None, False,
                 "Its brightness fits a K6-K7 dwarf, not the K3 V in its class column. "),
    "HD 142 B": (MS, "inf", None, False, ""),
    "psi1 Dra C": (MS, "inf", None, False, ""),
    "GJ 4317 Bb": (PL, "inf", None, True,
                   "The Ba,Bb resolution is one tentative SOAR epoch. "),
    "2MASS J19273089-4833528 Ca": (PL, "inf", None, True,
                                   "The split subtracts the hypothetical Cb at its assumed 0.09 Msun; Gaia's "
                                   "double image hints Cb is brighter, which would lower Ca (to 0.0082 at equal "
                                   "light). "),
    "HD 10647 Ba": (MS, "inf", None, False, "The 0.03 arcsec pair is a tentative speckle resolution. "),
    "HD 10647 Bb": (MS, "inf", None, False, "The 0.03 arcsec pair is a tentative speckle resolution. "),
    "GJ 376 Bb": (MS, "inf", None, False,
                  "Bb is no longer only suspected: Winters et al. 2026 find B double-lined, P 945 d. "),
    "HD 149806 Bb": (MS, "inf", None, True,
                     "No Ba/Bb flux ratio is published; the equal split is inferred from An et al. 2025's dynamical "
                     "mass of B (0.829 Msun), which also puts Bb near 0.4 Msun, not the 0.27 on file. "),
}

# Tier 3: inferred from mass. Hypothetical (infer.py) unless said otherwise.
FROM_MASS = ["GJ 569 Ab", "GJ 1006 Ac", "GJ 171.2 Ac", "13 Cyg Eb", "GJ 734 Ab", "GJ 119 C", "GJ 119 Bb",
             "NLTT 14412 Ab", "iot Leo Cb", "GJ 3376 Ab", "GJ 754.2 Cb", "2MASS J19273089-4833528 Cb",
             "2MASS J17061767+6438088 Ab", "nu Sco Db", "HD 23439 Bb"]
UNSEEN_MIN_MASS = {"HD 23439 Bb": "an unseen SB1 secondary whose 0.12 Msun is a MINIMUM mass (Latham et al. 2002); "
                                  "Tokovinin et al. 1994: it 'corresponds to that of M-type dwarf'. A lower bound "
                                  "for a main-sequence companion."}

# Tier 4: floored, possible brown dwarfs.
FLOOR = ["2MASS J15472982-2755121 Cb", "ADS 9982 Cb", "1 Hya Cb", "GJ 3725 Cb", "GJ 747.2 Bb", "BD+37 1091 Bb",
         "CD-52 2036 Bb"]

# Tier 5: blank, why.
BLANK = {
    "nu Oct B": (MS, "white dwarf with no published Teff or L (Cheng et al. 2025 give its mass only). A cooling-track "
                     "estimate, ~2.3e-4 Lsun (1.7-3.6e-4), would rest on a press-quoted cooling age of ~2 Gyr and is "
                     "not written."),
    "ksi UMa Bb": (PL, "the literature favours a white dwarf (Fuhrmann et al. 2016: Ba's barium excess; an M dwarf "
                       "'highly implausible'), and no WD Teff exists, so no main-sequence relation may be applied. "
                       "Fuhrmann 2016's mass, 0.17 (+0.13/-0.05) Msun at i 12.7 deg, supersedes the 0.14 on file."),
    "HD 151613 B": (MS, "unseen and undecided: no paper classifies it. Kervella et al. 2022 need ~0.81 Msun at 3 au "
                        "for a dark companion; a 0.8 Msun dwarf beside an F star might be seen, a white dwarf not."),
    "HD 207496 Bb": (MS, "unseen and undecided. Gaia DR3 binary_masses' 0.199-0.645 Msun assumes a LUMINOUS "
                         "main-sequence companion (flux ratio 0.08-0.59) and carries no compact-companion flag, so "
                         "this row's 'dark companion' reading is wrong; no flux ratio is measured."),
    "GJ 2130 C": (PL, "probably not a separate star: HST (Dieterich et al. 2012) and Gaia DR3 see no third object, and "
                      "Winters et al. 2019 count the system as a triple whose third star is the SB2 secondary, so the "
                      "MSC's C at 1.33 arcsec is probably Bb listed twice."),
    "GJ 187.2 Ab": (PL, "probably nonexistent: Abt & Levy 1974 could not confirm Abt 1965's 391.7 d orbit, and the "
                        "RV variation of 9 Aur A is its own gamma Dor pulsation (Krisciunas et al. 1993, 1995; Aerts "
                        "& Krisciunas 1996). The MSC marks it 'false?'."),
    "HR 1099 Bb": (PL, "nature unknown: the only orbit (Tokovinin & Gorynya 2001) gives a minimum mass, 0.07 Msun, "
                       "at the star/brown-dwarf boundary. Gaia DR3 (RUWE 1.03, a near-constant RV) sits badly with "
                       "an orbit that should wobble B by >= 5.8 mas (the researcher's arithmetic, not in print)."),
}
WHY_SHORT = {"nu Oct B": "white dwarf, no Teff", "ksi UMa Bb": "probably a white dwarf, no Teff",
             "HD 151613 B": "unseen, nature undecided", "HD 207496 Bb": "unseen, nature undecided",
             "GJ 2130 C": "probably Bb listed twice", "GJ 187.2 Ab": "orbit refuted; pulsation",
             "HR 1099 Bb": "nature unknown, orbit doubted"}
TAB_OF = {**{k: v[0] for k, v in RESEARCHED.items()}, **{k: PL for k in FROM_MASS if k != "HD 23439 Bb"},
          "HD 23439 Bb": MS, **{k: PL for k in FLOOR}, **{k: v[0] for k, v in BLANK.items()}}
assert len(TAB_OF) == 49, len(TAB_OF)


def cite(r):
    return f"{r['source']} ({r['identifier']})"


def researched_note(name, how, weak, lead):
    r = RECORDS[name]
    if how == "lit":
        return (f"SOURCE: {cite(r)} {r['url']}: \"{r['quote'][:450]}\" {lead}NOTE: {r['notes'][:500]}",
                f"L: {r['source'][:80]}")
    head = "INFERRED -- WEAK: " if weak else ("" if lead.startswith("INFERRED") else "INFERRED: ")
    method = r["derivation"] or f"published value {r['luminosity_lsun']} Lsun: \"{r['quote'][:300]}\""
    rng = f" Range {r['luminosity_range'][0]}-{r['luminosity_range'][1]} Lsun." if r.get("luminosity_range") else ""
    return (f"{head}{lead}{method[:900]}{rng} SOURCES: {cite(r)[:300]}. NOTE: {r['notes'][:400]}",
            f"L: INFERRED ({r['source'][:60]})")


def main():
    pm = F.load_pm()
    massed = [x for x in pm if x["mass"] is not None]
    last = min(massed, key=lambda x: x["mass"])            # L2V, 0.075 Msun, log L -3.82
    wb = gs.fetch_workbook(SID)
    tabs = {}
    for title in (PL, MS):
        t = wb["tabs"][title]
        h = t[0]
        col = {k: i for i, k in enumerate(h)}
        rows = {}
        for i, r in enumerate(t[1:], start=2):
            r = r + [""] * (len(h) - len(r))
            rows.setdefault(r[col["Star (component)"]], []).append((i, dict(zip(h, r))))
        tabs[title] = (col, rows)

    plan, upd, expect, orange, notes = [], {}, {}, [], {}
    for name, tab in TAB_OF.items():
        col, rows = tabs[tab]
        assert len(rows.get(name, [])) == 1, (tab, name, len(rows.get(name, [])))
        i, row = rows[name][0]
        lcell = f"{q(tab)}!{letter(col['Luminosity (L-sun)'])}{i}"
        ncell = f"{q(tab)}!{letter(col['Star (component)'])}{i}"
        scell = f"{q(tab)}!{letter(col['Star data source'])}{i}"
        assert str(row["Luminosity (L-sun)"]).strip() == "", (name, row["Luminosity (L-sun)"])
        m = row["Mass (M-sun)"]
        src_bit, value, tier = None, None, None
        if name in RESEARCHED:
            _, how, override, weak, lead = RESEARCHED[name]
            value = sig(override or RECORDS[name]["luminosity_lsun"])
            note, src_bit = researched_note(name, how, weak, lead)
            tier = "published" if how == "lit" else "derived"
        elif name in FROM_MASS:
            p = F.class_from_mass(pm, m)
            value = sig(10 ** p["logL"])
            what = UNSEEN_MIN_MASS.get(name, f"a hypothetical companion: its {m} Msun is the typical-companion "
                                             "rule's assumption (infer.py) and its light has never been seen")
            note = (f"INFERRED from mass -- WEAK: the {PM} L at the type whose tabulated mass is nearest this star's "
                    f"{m} Msun: {p['spt']} ({p['mass']} Msun), log L {p['logL']}. This is {what}. Assumes a "
                    f"main-sequence dwarf of solar metallicity; sequence scatter ~0.1-0.2 dex. {PM_URL}")
            src_bit, tier = "L: INFERRED from mass (Pecaut & Mamajek), WEAK", "mass"
        elif name in FLOOR:
            value = sig(10 ** last["logL"])
            note = (f"FLOOR -- WEAK, POSSIBLE BROWN DWARF: this star's assumed {m} Msun (the typical-companion "
                    f"rule's, infer.py) is at or below the last mass the {PM} tabulates, {last['spt']} at {last['mass']} "
                    f"Msun, log L {last['logL']}; this is that row's L. If it is a brown dwarf its L is lower, and "
                    "it belongs on a planet tab (docs/hybrasil-instructions.md section 6); kept a star for now, "
                    f"owner's decision, {DATE}. {PM_URL}")
            src_bit = (f"POSSIBLE BROWN DWARF: assumed mass below {last['mass']} Msun, the dwarf sequence's last "
                       f"tabulated mass ({last['spt']}); L floored at that row's, {DATE}")
            tier = "floor"
        else:
            note = f"BLANK ({DATE} literature check): " + BLANK[name][1]
            tier = "blank"
        if value is not None:
            upd[lcell] = value
            expect[lcell] = ""
            if tier != "published":
                orange.append(lcell)
        expect[ncell] = name
        notes[lcell] = note
        if src_bit:
            upd[scell] = (str(row["Star data source"]).rstrip("; ") + "; " + src_bit).lstrip("; ")
            expect[scell] = row["Star data source"]
        plan.append({"star": name, "tab": tab, "row": i, "tier": tier, "L": value, "mass": m})

    counts = {k: sum(p["tier"] == k for p in plan) for k in ("published", "derived", "mass", "floor", "blank")}
    lines = [
        "",
        f"LUMINOSITY FOR THE 49 STARS THAT DREW NO BAND, {DATE.upper()} (data/four_plus_stars/fill_missing_lum.py)",
        "  Planetless 4+ Stars and Multi-stars within 100 ly. Research: data/four_plus_stars/lum_research/*.json (paper,",
        "  identifier, URL and a verbatim quote for every number). No value is from Wikipedia (nothing pink); the pages",
        "  were read, and kap Tuc's (Harada et al. 2024, 4.59) and iot UMa's (Gaspar et al. 2016, 8.98) were set aside",
        "  for the sources below. Log: fill_missing_lum_log.json. Every cell has a note.",
        f"  PUBLISHED ({counts['published']}, plain): " + "; ".join(
            f"{p['star']} {p['L']} ({RECORDS[p['star']]['source'].split(' (')[0]})" for p in plan if p["tier"] == "published"),
        f"  DERIVED ({counts['derived']}, ORANGE): from published inputs -- R and Teff, a resolved M_bol, V plus a",
        "  Pecaut & Mamajek bolometric correction, a blend's L split by a delta-mag, or a whole-light value assigned to",
        "  its dominant star. Each note gives the arithmetic. " + "; ".join(
            f"{p['star']} {p['L']}" for p in plan if p["tier"] == "derived") + ".",
        f"  INFERRED FROM MASS, WEAK ({counts['mass']}, ORANGE): the {PM} L at the type whose tabulated",
        "  mass is nearest. All but HD 23439 Bb are hypothetical companions whose mass is itself an assumption; HD",
        "  23439 Bb's is a minimum mass. Valid for main-sequence dwarfs of solar metallicity only; scatter ~0.1-0.2 dex.",
        f"  Owner's decision, {DATE}. " + "; ".join(f"{p['star']} {p['L']}" for p in plan if p["tier"] == "mass") + ".",
        f"  FLOOR, POSSIBLE BROWN DWARFS ({counts['floor']}, ORANGE, WEAK): assumed masses at or below the last mass the",
        f"  sequence tabulates, {last['spt']} at {last['mass']} Msun (log L {last['logL']}), take that row's L,",
        f"  {sig(10 ** last['logL'])} Lsun -- an upper bound if they are brown dwarfs. Flagged POSSIBLE BROWN DWARF in Star",
        "  data source; they stay stars under the section 6 rule for now (owner, 9 Oct 2026): "
        + ", ".join(p["star"] for p in plan if p["tier"] == "floor") + ".",
        f"  LEFT BLANK ({counts['blank']}), each note says why: " + "; ".join(
            f"{k} ({WHY_SHORT[k]})" for k in BLANK) + ".",
    ]

    if PLAN:
        for p in plan:
            print(f"  {p['tier']:9} {p['tab'][:10]:10} r{p['row']:<4} {p['star']:30} L {p['L']}  (mass {p['mass']})")
        print(counts, f"orange {len(orange)}, notes {len(notes)}, cells {len(upd)}")
        print("\n".join(lines))
        print("\nsample notes:")
        for k in list(notes)[:3] + [c for c in notes if "FLOOR" in notes[c]][:1]:
            print(" ", k, notes[k][:600])
        return

    gs.update_cells(SID, upd, expect=expect)
    gs.set_border(SID, orange, gs.INFERRED_BORDER)
    gs.set_note(SID, notes)
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    n = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{n}"])[f"{q(SP)}!A{n}"][0][0].strip()
    start, end = n + 1, n + len(lines)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, start + 1, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    LOG.write_text(json.dumps({"title": title, "sp_rows": [start, end], "counts": counts, "plan": plan,
                               "orange": orange}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", title, counts, f"S&P {start}-{end}")


if __name__ == "__main__":
    main()
