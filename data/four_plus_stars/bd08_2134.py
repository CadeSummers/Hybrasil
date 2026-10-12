# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""BD+08 2134 Aa-Ab (HD 75767): take SB9's Griffin 1991 orbit whole.

    python bd08_2134.py          plan: print every cell it would change
    python bd08_2134.py write    write, unmark, note, provenance, rename

The tab's orbit was Fuhrmann et al. 2005 (MNRAS 361, 803): P, e = 0.016 and omega = 356.2, but no epoch, so
infer.py hashed T. Fuhrmann's Table 3 is an image behind the publisher's paywall. SB9 system 541 carries Griffin
1991 (BASI 19, 183) with every element, and an epoch only means something with the e and omega it was fitted with,
so the owner chose (30 Sep 2026) to take Griffin's P, e, omega and T together rather than graft one onto the other.
Griffin & Fuhrmann 2013 (MNRAS 430, 1390) both cite Griffin's period as the accurate one.

Gaia DR3's inclination and node stay: their 180-degree node ambiguity was resolved against the spectroscopic omega,
and Griffin's omega (0) picks the same branch as Fuhrmann's (356.2) -- Gaia's photocentre omega is 318.18, 42 degrees
from 0 and 138 from the alternative.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)
from research import SB9_SRC  # noqa: E402
from build import GREY_RULE  # noqa: E402  (this tab's plain rule; gs.PLAIN_RULE is black)

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
FP, SP = "Planetless 4+ Stars", "Sources & Provenance"
STAR = "BD+08 2134 Ab"
BIB = "1991BASI...19..183G"
SRC = f"{SB9_SRC}, system 541, orbit {BIB} (Griffin 1991, BASI 19, 183)"
WHOLE = ("Taken with Griffin's e, omega and T as one orbit: Fuhrmann et al. 2005 (MNRAS 361, 803) gives no "
         "readable epoch, and an epoch only means something with the e and omega it was fitted with.")
CIRC = " The orbit is circular (e = 0): omega is conventional and T marks the zero point of phase."

# header -> (expected current value, new value, note)
CHANGES = {
    "Orbital period (d)": (10.2485, 10.24806, f"SOURCE: {SRC}; P = 10.24806 +- 0.00003 d. {WHOLE} Was 10.2485 "
                                               "(Fuhrmann et al. 2005)."),
    "Orbital eccentricity (e)": (0.016, 0, f"SOURCE: {SRC}. {WHOLE} Was 0.016 (Fuhrmann et al. 2005).{CIRC}"),
    "Argument of periastron (deg)": (356.2, 0, f"SOURCE: {SRC}. {WHOLE} Was 356.2 (Fuhrmann et al. 2005).{CIRC}"),
    "Time of periastron (JD)": (2451545.8797, 2447212.16,
                                f"SOURCE: {SRC}; T = JD 2447212.160 +- 0.007. {WHOLE} Was 2451545.8797, hashed by "
                                f"infer.py (orange).{CIRC}"),
    "Orbit source": ("2005MNRAS.361.803 Fuhrmann+", f"SB9 541 {BIB} Griffin",
                     f"SOURCE: {SRC}. Was '2005MNRAS.361.803 Fuhrmann+'. {WHOLE}"),
}
# header -> note only, value unchanged
GAIA_ADD = (" 30 Sep 2026: the spectroscopic orbit is now Griffin 1991 (omega = 0, circular); the same branch is kept "
            "(318.18 is 42 degrees from 0, the alternative 138).")
RENOTE = {"Argument of periastron refers to": f"SOURCE: {SB9_SRC} convention: omega is the primary's."}


def main():
    v = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A1:CZ2000", valueRenderOption="UNFORMATTED_VALUE"
                         ).execute()["values"]
    h = v[0]
    col = {k: i for i, k in enumerate(h)}
    hits = [r for r, row in enumerate(v[1:], start=2) if len(row) > 1 and row[col["Star (component)"]] == STAR]
    assert len(hits) == 1, hits
    r = hits[0]
    row = v[r - 1] + [""] * len(h)
    cell = {hd: f"{q(FP)}!{letter(col[hd])}{r}" for hd in (*CHANGES, *RENOTE, "Inclination (deg)",
                                                           "Ascending node (deg)")}
    for hd, (old, _, _) in CHANGES.items():
        assert row[col[hd]] == old, (hd, row[col[hd]], old)

    gaia_notes = {}
    for hd in ("Inclination (deg)", "Ascending node (deg)"):
        old = gs.get_notes(SID, cell[hd])
        old = next(iter(old.values()))
        assert "spectroscopic omega (356.2): kept" in old, old
        gaia_notes[cell[hd]] = old if GAIA_ADD in old else old + GAIA_ADD

    sp = sp_entry()
    if PLAN:
        print(f"{STAR}  (row {r})")
        for hd, (old, new, note) in CHANGES.items():
            print(f"  {cell[hd]:28} {hd:32} {old!s:>28} -> {new}\n      note: {note}")
        for c, n in {**{cell[k]: n for k, n in RENOTE.items()}, **gaia_notes}.items():
            print(f"  {c:28} note -> ...{n[-160:]}")
        print(f"  {cell['Time of periastron (JD)']}: orange border -> grey rule")
        print("\n".join(sp))
        return

    gs.update_cells(SID, {cell[hd]: [[new]] for hd, (_, new, _) in CHANGES.items()},
                    expect={cell[hd]: old for hd, (old, _, _) in CHANGES.items()})
    gs.set_border(SID, [cell["Time of periastron (JD)"]], GREY_RULE, style="SOLID")
    gs.set_note(SID, {**{cell[hd]: note for hd, (_, _, note) in CHANGES.items()},
                      **{cell[k]: n for k, n in RENOTE.items()}, **gaia_notes})

    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    spm = next(s["properties"] for s in meta if s["properties"]["title"] == SP)
    last = spm["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{last}"])[f"{q(SP)}!A{last}"][0][0].strip()
    start, end = last + 1, last + len(sp)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": spm["sheetId"], "dimension": "ROWS", "length": len(sp)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{start}:A{end}": [[x] for x in sp]},
                    expect={f"{q(SP)}!A{i}": "" for i in (start, end)})
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    print("done:", {"row": r, "sp_rows": [start, end], "title": title})


def sp_entry():
    return [
        "",
        "30 SEPTEMBER 2026: 'Planetless 4+ Stars' -- BD+08 2134 Aa-Ab (HD 75767) TAKES GRIFFIN 1991'S ORBIT "
        "(bd08_2134.py).",
        f"Orbital period, e, omega, T and Orbit source of BD+08 2134 Ab: {SRC}. P = 10.24806 +- 0.00003 d, "
        "T = JD 2447212.160 +- 0.007, e = 0, omega = 0 (circular: omega conventional, T the zero point of phase), "
        "K1 = 23.59 km/s. Replaces Fuhrmann et al. 2005 (MNRAS 361, 803; P = 10.2485, e = 0.016, omega = 356.2), "
        "whose epoch is in a table image behind the paywall; T had been hashed by infer.py (orange, now the tab's grey rule). "
        "Owner's decision: one paper's orbit whole rather than one paper's T on another's e and omega. Griffin & "
        "Fuhrmann 2013 (MNRAS 430, 1390) cite Griffin's period. Confidence MEDIUM: SB9 grade 2 of 5 (5 = "
        "definitive), though the formal errors on P and T are small. "
        "Verify: SB9 Orbits.dta, system 541, second orbit.",
        "  Gaia DR3 inclination and node unchanged: the node branch chosen against Fuhrmann's omega (356.2) is the "
        "one Griffin's omega (0) picks too.",
    ]


if __name__ == "__main__":
    main()
