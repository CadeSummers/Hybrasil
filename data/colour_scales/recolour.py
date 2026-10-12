# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repaint the workbook's static colour scales so every cell carries the colour its value earns.

    python recolour.py          plan: per column, how many cells change and why; touches nothing
    python recolour.py write    repaint, log every old fill, note it on Legend & Notes, rename

The scales on the star and planet tabs are STATIC fills (Legend & Notes: "computed once and will not repaint
themselves"). They drifted three ways: rows added with a fill copied from another row (87 Systems distances share
one green), values filled in later while the cell kept the "no data" grey FFDCDBE2 (83 temperatures, 71 masses),
and values edited without a repaint (VHS J1256 moved from 41.42 to 68.99 ly and kept its 41-ly colour).

The repaint uses the workbook's own rule for a new value -- "each new cell took the colour of the nearest existing
value" on the column's scale (Legend & Notes, luminosity coverage of 9 Sep 2026) -- so the documented anchors
(mass 0.089 / 0.640 / 1.760, Teff white at 5772 K, flux clamped at 0.001-1000x Earth, the 95th-percentile clips)
stay exactly where they are and every cell that was right keeps its colour:

1. Trusted cells. A cell's fill is trusted when it is the commonest fill among its six nearest neighbours in
   scale order, and its value sits between the median values of the colours either side of it in the palette.
   Copied and stale fills fail one test or the other; greys and blanks are never trusted.
2. Every cell with a value takes the fill of its nearest trusted cell, measured on the column's scale (below) --
   except Effective temp, which is painted by its legend's formula (FORMULA, teff_fill).
3. A cell with no value takes the column's missing-value fill (grey, or none where that column leaves gaps
   unfilled), unless it already has one.
4. Stellar Class and Class (sort key) share one colour per row, on the legend's class scale: |sort key - 42| plus
   the luminosity-class penalty (III +12, III-IV +9, IV +6, IV-V +3, V 0), so dwarfs run greener than evolved stars
   at the same subtype. A class with no sort key (white dwarfs, composites) is not on the scale and is left alone.
5. Solvent band is a label, not a scale: one band its own colour, two or more pink, none unfilled.
6. The Sun row of the Systems tab is coloured in the mass column only (Legend, 30 Aug 2026); its other scale cells
   are left unstyled. Known's Sun row is treated the same way.
7. Known within 100ly FOLLOWS Systems' scales (6 Oct 2026): its cells are painted from the same trusted table but
   are never trusted themselves, so its 10,000-odd rows cannot move a single Systems or Multi-stars colour. Its
   empty cells are unfilled and rule 3 keeps them so: a row with only a distance gets only a distance colour.
8. A Known class that is off the class scale (white dwarfs, '~M4') copies the hand-set fill of the Systems row of the
   same name (owner, 7 Oct 2026), so a star reads the same on both tabs. With no filled twin it is left alone.

Columns that share a scale are pooled, so a colour means the same thing on each tab (Legend: Systems and
Multi-stars share theirs, and Known follows them; Planets, Unconfirmed and Rejected share the flux scale).

Only background colour is written (fields = userEnteredFormat.backgroundColor), so borders, notes, number formats
and values are untouched. Every old and new fill is logged by tab, star name and column in recolour_log.json.
"""
import collections
import datetime
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data" / "four_plus_stars"))
from hybrasil.data import google_sheets as gs  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
API = gs._sheets_api()
LOG = HERE / "recolour_log.json"

SYS, MUL, PLA, UNC, REJ = ("Systems within 100 ly", "Multi-stars within 100 ly", "Planets within 100 ly",
                           "Unconfirmed within 100 ly", "Rejected candidates")
KNO = "Known within 100ly"
FOLLOWERS = {KNO}                                       # painted from a pool's trusted cells, never trusted
SUN_TABS = (SYS, KNO)                                   # tabs with a Sun row (rule 6)
GREY = "FFDCDBE2"
NOT_PALETTE = {None, GREY, "FFBFBFBF", "FFFFFFFF"}     # never trusted as a scale colour (white is, on a diverging
WHITE_OK = {"luminosity", "teff", "flux"}               # scale: these pools put white at their reference point)
PINK = "FFF3A5C4"

# pool -> (scale, reference, [(tab, header), ...]).  Scales: lin x; log log10 x; div |x - ref|; divlog |log10(x/ref)|.
POOLS = {
    "distance": ("lin", 0, [(SYS, "Distance (ly)"), (MUL, "Distance (ly)"), (KNO, "Distance (ly)")]),
    "stars": ("lin", 0, [(SYS, "Stars in system"), (MUL, "Stars in system"), (KNO, "Stars in system")]),
    "planets": ("lin", 0, [(SYS, "Confirmed planets"), (MUL, "Confirmed planets"), (KNO, "Confirmed planets")]),
    "mass": ("lin", 0, [(SYS, "Host mass (M-sun)"), (MUL, "Mass (M-sun)"), (KNO, "Host mass (M-sun)")]),
    "teff": ("lin", 0, [(SYS, "Effective temp (K)"), (MUL, "Effective temp (K)"), (KNO, "Effective temp (K)")]),
    "age": ("div", 4.6, [(SYS, "Age (Gyr)"), (MUL, "Age (Gyr)"), (KNO, "Age (Gyr)")]),
    "feh": ("lin", 0, [(SYS, "Metallicity [Fe/H]"), (MUL, "Metallicity [Fe/H]"), (KNO, "Metallicity [Fe/H]")]),
    "luminosity": ("log", 0, [(SYS, "Host luminosity (L-sun)"), (MUL, "Luminosity (L-sun)"), (KNO, "Host luminosity (L-sun)")]),
    "hz": ("lin", 0, [(SYS, "Planets in HZ"), (MUL, "Planets in HZ"), (KNO, "Planets in HZ")]),
    "velocity": ("lin", 0, [(SYS, "Space velocity (km/s)"), (MUL, "Space velocity (km/s)"), (KNO, "Space velocity (km/s)")]),
    "p_distance": ("lin", 0, [(PLA, "Distance (ly)")]),
    "p_luminosity": ("log", 0, [(PLA, "Host luminosity (L-sun)")]),
    "p_mass": ("divlog", 1, [(PLA, "Mass (M-earth)")]),
    "p_agreement": ("div", 0, [(PLA, "Mass agreement, OEC vs archive")]),
    "p_radius": ("divlog", 1, [(PLA, "Radius (R-earth)")]),
    "p_period": ("divlog", 365.25, [(PLA, "Orbital period (d)")]),
    "p_sma": ("divlog", 1, [(PLA, "Semi-major axis (au)")]),
    "flux": ("log", 0, [(PLA, "Stellar flux received (S-earth)"), (UNC, "Stellar flux received (S-earth)"),
                        (REJ, "Stellar flux received (S-earth)")]),
    "p_ecc": ("lin", 0, [(PLA, "Eccentricity")]),
    "p_vmean": ("divlog", 29.78, [(PLA, "Mean orbital velocity (km/s)")]),
    "p_vperi": ("divlog", 29.78, [(PLA, "Periastron velocity (km/s)")]),
    "p_vapo": ("divlog", 29.78, [(PLA, "Apoastron velocity (km/s)")]),
    "p_rot": ("divlog", 24, [(PLA, "Rotation period, assumed if tidally locked (h)")]),
    "p_vrot": ("divlog", 0.465, [(PLA, "Equatorial rotation speed (km/s)")]),
}
# Effective temp is painted by its legend's own formula, not by nearest neighbour: "Linear in kelvin on each side
# of white, quantised into 24 steps per side", white at the Sun's 5772 K, ends at 2516 K (TRAPPIST-1) and 7540 K
# (RR Cae). Step 0 is white and step 23 the end colour, which are the column's palest-blue and palest-red extremes
# as they were before (9DC2EB, FAC8C7); a star beyond an end takes the end colour. Nearest neighbour could not
# draw this scale: 278 of 514 values (2267-4072 K) had come to share the one blue, so there was nothing to copy.
TEFF_SUN, TEFF_COOL, TEFF_HOT, TEFF_STEPS = 5772, 2516, 7540, 24
TEFF_COOL_END, TEFF_HOT_END = "FF9DC2EB", "FFFAC8C7"


def teff_fill(x):
    if x == TEFF_SUN:
        return "FFFFFFFF"
    end, t = ((TEFF_COOL_END, (TEFF_SUN - x) / (TEFF_SUN - TEFF_COOL)) if x < TEFF_SUN
              else (TEFF_HOT_END, (x - TEFF_SUN) / (TEFF_HOT - TEFF_SUN)))
    k = min(TEFF_STEPS - 1, int(t * TEFF_STEPS))
    f = k / (TEFF_STEPS - 1)
    return "FF" + "".join(f"{round(255 + (int(end[i:i + 2], 16) - 255) * f):02X}" for i in (2, 4, 6))


FORMULA = {"teff": teff_fill}          # pool -> fill of a value; these pools ignore the trusted-cell table

CLASS_COLS = [(SYS, "Stellar Class"), (SYS, "Class (sort key)"), (MUL, "Stellar Class"), (MUL, "Class (sort key)"),
              (KNO, "Stellar Class"), (KNO, "Class (sort key)")]
BAND_COLS = [(PLA, "Solvent band (1 bar, A=0.3)"), (UNC, "Solvent band (1 bar, A=0.3)"),
             (REJ, "Solvent band (1 bar, A=0.3)")]
BAND_COLOUR = {"Ethane": "FF717EA8", "Liquid sulfur": "FFFFE799", "Liquid CO2": "FFBFBFBF", "Ammonia": "FFB8E0F0"}
SUN_ONLY = {(SYS, "Host mass (M-sun)"), (KNO, "Host mass (M-sun)")}   # the Sun row keeps a colour here only
FIRST_COL = {SYS: "System / Host", MUL: "System / Host", KNO: "System / Host", PLA: "Planet", UNC: "Planet",
             REJ: "Planet"}
# What names a row in the log: unique per row. Multi-stars repeats the system in column A for every component.
ID_COL = {**FIRST_COL, MUL: "Star (component)"}
# Where a name repeats, this column is appended to it in the log. Known has two 'GJ 257 A' rows (6 Oct 2026),
# different Gaia sources; its Gaia DR3 source_id is unique wherever it is filled.
DISAMBIG = {KNO: "Gaia DR3 source_id"}


# ── reading ────────────────────────────────────────────────────────────────────────────────────────
def hexof(color):
    if not color:
        return None
    return "FF" + "".join(f"{round(color.get(k, 0) * 255):02X}" for k in ("red", "green", "blue"))


def colour_of(h):
    return {"red": int(h[2:4], 16) / 255, "green": int(h[4:6], 16) / 255, "blue": int(h[6:8], 16) / 255}


def read_tab(tab, headers):
    """{header: [(row, value, fill), ...]} over the tab's data rows (2 .. last row with a name in column A)."""
    hdr = API.values().get(spreadsheetId=SID, range=f"{q(tab)}!1:1").execute()["values"][0]
    col = {h: i for i, h in enumerate(hdr)}
    first = col[FIRST_COL[tab]]
    out = {}
    for h in dict.fromkeys([FIRST_COL[tab], ID_COL[tab], *([DISAMBIG[tab]] if tab in DISAMBIG else []), *headers]):
        c = letter(col[h])
        res = API.get(spreadsheetId=SID, ranges=[f"{q(tab)}!{c}2:{c}"], includeGridData=True,
                      fields="sheets(data(rowData(values(effectiveValue,userEnteredFormat.backgroundColor))))"
                      ).execute()
        rows = res["sheets"][0]["data"][0].get("rowData", [])
        cells = []
        for k, rd in enumerate(rows, start=2):
            v = (rd.get("values") or [{}])[0]
            ev = v.get("effectiveValue", {})
            val = ev.get("numberValue", ev.get("stringValue", ev.get("boolValue")))
            cells.append((k, val, hexof(v.get("userEnteredFormat", {}).get("backgroundColor"))))
        out[h] = cells
    firsts = out.pop(FIRST_COL[tab])
    ids = out.pop(ID_COL[tab], firsts)
    extra = {k: val for k, val, _ in out.pop(DISAMBIG[tab])} if tab in DISAMBIG else {}
    last = 1
    for k, val, _ in firsts:
        if val in (None, ""):
            break
        last = k
    name_of = {k: val for k, val, _ in ids if k <= last}
    seen = collections.Counter(name_of.values())
    name_of = {k: f"{v} [{extra[k]}]" if seen[v] > 1 and extra.get(k) else v for k, v in name_of.items()}
    assert first == 0, (tab, first)
    assert len(set(name_of.values())) == len(name_of), f"{tab}: {ID_COL[tab]} does not name each row once"
    return {h: [c for c in cells if c[0] <= last] for h, cells in out.items()}, name_of, col


# ── the scale ──────────────────────────────────────────────────────────────────────────────────────
def scale(kind, ref, x):
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        return None
    if kind == "lin":
        return float(x)
    if kind == "div":
        return abs(x - ref)
    if x <= 0:
        return None
    return math.log10(x) if kind == "log" else abs(math.log10(x / ref))


def trusted(points, allow_white=False):
    """points: [(s, fill, key)] with s not None. Returns {key: fill} for the trusted ones."""
    bad = NOT_PALETTE - ({"FFFFFFFF"} if allow_white else set())
    # Ties in s are ordered by cell, never by fill, so a run of equal values mixes its colours honestly.
    pts = sorted((p for p in points if p[1] not in bad), key=lambda p: (p[0], p[2]))
    uses = collections.Counter(p[1] for p in pts)
    first = {}
    for k, (s, f, key) in enumerate(pts):
        near = collections.Counter(p[1] for p in pts[max(0, k - 3):k] + pts[k + 1:k + 4])
        # A colour on one or two cells is an end of the scale (Kapteyn's -0.89, the 495 L-sun star), not a copy:
        # copied fills are common ones. It still has to sit in palette order below.
        if near and near.most_common(1)[0][0] == f or uses[f] <= 2:
            first[key] = (s, f)
    # palette order: each colour's median scale value among first-pass trusted cells
    by = collections.defaultdict(list)
    for s, f in first.values():
        by[f].append(s)
    med = sorted((sorted(v)[len(v) // 2], f) for f, v in by.items())
    rank = {f: i for i, (_, f) in enumerate(med)}
    out = {}
    for key, (s, f) in first.items():
        i = rank[f]
        lo = med[i - 1][0] if i > 0 else -math.inf
        hi = med[i + 1][0] if i + 1 < len(med) else math.inf
        if lo <= s <= hi:
            out[key] = f
    return out


def palette_table(points, tr):
    """Sorted [(s, fill)], one entry per distinct s: the commonest trusted fill at that value."""
    at = collections.defaultdict(collections.Counter)
    for s, f, key in points:
        if key in tr:
            at[s][f] += 1
    table = sorted((s, c.most_common(1)[0][0]) for s, c in at.items())
    # A few trusted cells straddle a neighbour's bin by one shade (mass 0.48 / 0.49, 1.05 / 1.07): keep the
    # longest run of entries already in palette order, so each colour owns one unbroken stretch of the scale.
    by = collections.defaultdict(list)
    for s, f in table:
        by[f].append(s)
    rank = {f: sorted(v)[len(v) // 2] for f, v in by.items()}
    import bisect
    tails, tail_at, prev = [], [], [None] * len(table)
    for k, (_, f) in enumerate(table):
        j = bisect.bisect_right(tails, rank[f])
        prev[k] = tail_at[j - 1] if j else None
        if j == len(tails):
            tails.append(rank[f])
            tail_at.append(k)
        else:
            tails[j], tail_at[j] = rank[f], k
    keep, k = [], tail_at[-1] if tail_at else None
    while k is not None:
        keep.append(table[k])
        k = prev[k]
    return keep[::-1]


def nearest(s, table):
    """table: sorted [(s, fill)], one per s; the fill of the nearest s (ties to the lower)."""
    import bisect
    i = bisect.bisect_left(table, (s, ""))
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(table) and (best is None or abs(table[j][0] - s) < abs(best[0] - s)):
            best = table[j]
    return best[1]


LUM_PENALTY = [("III-IV", 9), ("IV-V", 3), ("III", 12), ("IV", 6), ("V", 0)]


def class_score(text, key):
    if not isinstance(key, (int, float)):
        return None
    t = str(text or "").replace(" ", "")
    pen = next((p for tag, p in LUM_PENALTY if tag in t[1:]), 0)
    return abs(key - 42) + pen


def bands_named(text):
    t = str(text or "")
    if not t or t.startswith(("Too ", "no ", "between", "In the gap", "Between")) or "," not in t and \
            t.rstrip("*").strip() not in {*BAND_COLOUR, "Methane", "Water", "Formamide", "Sulfuric acid"}:
        return []
    return [b.strip().rstrip("*").strip() for b in t.split(",") if b.strip()]


# ── planning ───────────────────────────────────────────────────────────────────────────────────────
def plan():
    """Read the sheet, then repaint in memory until a pass changes nothing.

    Each pass trusts more cells than the last, which can move a bin boundary by one shade; iterating to a fixed
    point means the sheet, once written, plans to zero changes. Returns the net changes against the sheet.
    """
    want = collections.defaultdict(set)
    for _, _, members in POOLS.values():
        for t, h in members:
            want[t].add(h)
    for t, h in CLASS_COLS + BAND_COLS:
        want[t].add(h)
    data, names, cols = {}, {}, {}
    for t, hs in want.items():
        data[t], names[t], cols[t] = read_tab(t, sorted(hs))
    sheet = {(t, r, h): f for t in data for h, cells in data[t].items() for r, _, f in cells}
    work = {t: {h: list(cells) for h, cells in data[t].items()} for t in data}
    why_of, summary = {}, None
    for _ in range(25):
        changes, summary = compute(work, names)
        if not changes:
            break
        for t, r, h, old, new, why in changes:
            why_of.setdefault((t, r, h), why)
            work[t][h] = [(rr, v, new if rr == r else f) for rr, v, f in work[t][h]]
    else:
        raise RuntimeError("the repaint did not settle in 25 passes")
    net = [(t, r, h, sheet[(t, r, h)], f, why_of[(t, r, h)])
           for t in work for h, cells in work[t].items() for r, _, f in cells if f != sheet[(t, r, h)]]
    return net, summary, names, cols, data


def compute(data, names):
    """One repaint pass over data ({tab: {header: [(row, value, fill)]}}): (changes, summary)."""
    sun = {(t, next(k for k, n in names[t].items() if str(n).strip() == "Sun")) for t in SUN_TABS}

    changes = []                       # (tab, row, header, old, new, why)
    summary = collections.OrderedDict()

    def missing_fill(cells):
        c = collections.Counter(f for _, v, f in cells if v in (None, ""))
        return c.most_common(1)[0][0] if c else GREY

    for pool, (kind, ref, members) in POOLS.items():
        pts = []
        for t, h in members:
            for r, v, f in data[t][h]:
                s = scale(kind, ref, v)
                if s is not None and (t, r) not in sun and t not in FOLLOWERS:
                    pts.append((s, f, (t, h, r)))
        tr = trusted(pts, allow_white=pool in WHITE_OK)
        table = palette_table(pts, tr)
        for t, h in members:
            miss = missing_fill(data[t][h])
            n = collections.Counter()
            for r, v, f in data[t][h]:
                s = scale(kind, ref, v)
                if (t, r) in sun and (t, h) not in SUN_ONLY:
                    new, why = None, "Sun row left unstyled"
                elif s is not None:
                    new = FORMULA[pool](v) if pool in FORMULA else nearest(s, table)
                    why = ("grey with a value" if f == GREY else "unfilled with a value"
                           if f is None else "colour off its scale")
                elif v in (None, ""):
                    new, why = (f if f in (GREY, None) else miss), "stale colour on an empty cell"
                else:
                    new, why = f, ""                                          # text in a numeric column: leave
                if new != f:
                    changes.append((t, r, h, f, new, why))
                    n[why] += 1
            summary[(t, h)] = (pool, kind, len(tr), len({f for f in tr.values()}), dict(n))

    # Stellar Class / Class (sort key): both cells of a row take one colour, from the class's score on the
    # legend's scale, |sort key - 42| plus the luminosity-class penalty. A class with no sort key (white dwarfs,
    # composite types) is not on the scale and is left as it is.
    rows, pts = [], []
    for t in (SYS, MUL, KNO):
        text = {r: v for r, v, _ in data[t]["Stellar Class"]}
        key = {r: v for r, v, _ in data[t]["Class (sort key)"]}
        for h in ("Stellar Class", "Class (sort key)"):
            for r, v, f in data[t][h]:
                s = class_score(text.get(r), key.get(r))
                rows.append((t, h, r, s, f))
                if s is not None and (t, r) not in sun and t not in FOLLOWERS:
                    pts.append((s, f, (t, h, r)))
    tr = trusted(pts)
    table = palette_table(pts, tr)
    # Rule 8: a follower's class off the scale takes its Systems twin's hand-set fill, the twin found by name.
    twin = {h: {names[SYS][r]: f for r, _, f in data[SYS][h] if f is not None}
            for h in ("Stellar Class", "Class (sort key)")}
    for t, h in CLASS_COLS:
        n = collections.Counter()
        for tt, hh, r, s, f in rows:
            if (tt, hh) != (t, h):
                continue
            if (t, r) in sun:
                new, why = None, "Sun row left unstyled"
            elif s is not None:
                new, why = nearest(s, table), ("grey with a value" if f == GREY else "colour off its scale")
            elif t in FOLLOWERS and names[t].get(r) in twin[h]:
                new, why = twin[h][names[t][r]], "off the class scale: Systems twin's fill"
            else:
                new, why = f, ""
            if new != f:
                changes.append((t, r, h, f, new, why))
                n[why] += 1
        summary[(t, h)] = ("class", "score", len(tr), len(set(tr.values())), dict(n))

    for t, h in BAND_COLS:
        n = collections.Counter()
        for r, v, f in data[t][h]:
            b = bands_named(v)
            new = None if not b else PINK if len(b) > 1 else BAND_COLOUR.get(b[0], f)
            if new != f:
                changes.append((t, r, h, f, new, "band label"))
                n["band label"] += 1
        summary[(t, h)] = ("band", "label", 0, 0, dict(n))
    return changes, summary


def main():
    changes, summary, names, cols, data = plan()
    print(f"{len(changes)} cells change")
    net = collections.defaultdict(collections.Counter)
    for t, r, h, old, new, why in changes:
        net[(t, h)][why] += 1
    for (t, h), (pool, kind, ntr, ncol, _) in summary.items():
        print(f"  {t[:24]:24} {h[:40]:40} {pool:12} {kind:6} trusted={ntr:4} colours={ncol:3}  {dict(net[(t, h)])}")
    if PLAN:
        for t, r, h, old, new, why in changes[:: max(1, len(changes) // 40)]:
            print(f"    e.g. {t[:12]:12} {names[t][r]!s:22} {h[:28]:28} {old} -> {new}  ({why})")
        return

    # Guard: re-read the sheet and stop if any row's name or any cell's fill moved since the plan was made.
    again = plan()
    for t in names:
        assert names[t] == again[2][t], f"{t}: rows moved since the plan"
    now = {(t, r, h): f for t in again[4] for h, cells in again[4][t].items() for r, _, f in cells}
    for t, r, h, old, *_ in changes:
        assert now[(t, r, h)] == old, (t, names[t][r], h, now[(t, r, h)], old)
    # One log and one Legend note per day: a second run the same day merges into them, keeping each cell's
    # original fill as 'old', so the log always undoes the day's work in one step.
    today = datetime.date.today().isoformat()
    prior = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    merged = {(c["tab"], c["name"], c["column"]): c for c in prior.get("cells", [])} \
        if prior.get("date") == today else {}
    for t, r, h, old, new, why in changes:
        k = (t, names[t][r], h)
        c = merged.get(k, {"tab": t, "name": names[t][r], "row": r, "column": h, "old": old, "why": why})
        c["new"] = new
        if c["new"] == c["old"]:
            merged.pop(k, None)
        else:
            merged[k] = c
    log = {"date": today, "cells": list(merged.values())}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    day_changes = [(c["tab"], c["row"], c["column"], c["old"], c["new"], c["why"]) for c in log["cells"]]

    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
    sheet_id = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta}
    reqs = []
    for t, r, h, old, new, why in changes:
        cell = {"userEnteredFormat": {"backgroundColor": colour_of(new)}} if new else {}
        reqs.append({"updateCells": {
            "range": {"sheetId": sheet_id[t], "startRowIndex": r - 1, "endRowIndex": r,
                      "startColumnIndex": cols[t][h], "endColumnIndex": cols[t][h] + 1},
            "rows": [{"values": [cell]}], "fields": "userEnteredFormat.backgroundColor"}})
    for k in range(0, len(reqs), 500):
        API.batchUpdate(spreadsheetId=SID, body={"requests": reqs[k:k + 500]}).execute()

    lg = "Legend & Notes"
    lv = API.values().get(spreadsheetId=SID, range=f"{q(lg)}!A1:A2000").execute().get("values", [])
    note = legend_note(day_changes, summary)
    hit = [k for k, row in enumerate(lv, start=1) if row and row[0] == note[0]]
    if hit:                                    # today's note is already there: rewrite it with the day's totals
        start = hit[-1]
        old = {f"{q(lg)}!A{start + i}": (lv[start + i - 1][0] if start + i - 1 < len(lv) and lv[start + i - 1]
                                         else "") for i in range(len(note))}
        expect = {k: v for k, v in old.items() if k.endswith(f"A{start}") or k.endswith(f"A{start + 1}")}
    else:
        start = len(lv) + 2
        expect = {f"{q(lg)}!A{start}": "", f"{q(lg)}!A{start + len(note) - 1}": ""}
    gs.update_cells(SID, {f"{q(lg)}!A{start}:A{start + len(note) - 1}": [[x] for x in note]}, expect=expect)
    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    print("done:", {"cells": len(changes), "day_total": len(day_changes),
                    "legend_rows": [start, start + len(note) - 1], "title": title})


def legend_note(changes, summary):
    by_why = collections.Counter(why for *_, why in changes)
    by_tab = collections.Counter(t for t, *_ in changes)
    return [
        f"COLOUR SCALES REPAINTED -- {datetime.date.today():%d %B %Y}".upper(),
        "The static fills had drifted: rows added with a colour copied from another row, values filled in later "
        "while the cell kept the no-data grey, and values edited without a repaint.",
        f"{len(changes)} cells repainted: " + ", ".join(f"{t} {n}" for t, n in by_tab.most_common()) + ".",
        "  By reason: " + ", ".join(f"{w} {n}" for w, n in by_why.most_common()) + ".",
        "METHOD: the rule this file already uses for a new value -- each cell takes the colour of the nearest "
        "correctly coloured value on its column's scale (log for luminosity and flux; distance from the Sun's or "
        "Earth's value for the divergent columns). A fill counts as correct when it matches its neighbours in "
        "value order and sits in palette order. So no anchor moved: the scales, endpoints and clips described "
        "above still hold, and every cell that was right kept its colour.",
        f"Effective temp is the exception: it is painted by its own rule above, white at {TEFF_SUN} K and 24 steps "
        f"per side, linear in kelvin to {TEFF_COOL} K (#{TEFF_COOL_END[2:]}) and {TEFF_HOT} K "
        f"(#{TEFF_HOT_END[2:]}), a star beyond an end taking the end colour. Nearest neighbour could not keep it: "
        "every star below about 4,090 K had come to share one blue.",
        "Stellar Class and its sort key share one colour per row, from the class scale above (|sort key - 42| "
        "plus the luminosity-class penalty); classes with no sort key are left as they were. Solvent band follows "
        "its label "
        "rule (one band its colour, two or more pink, none unfilled). The Sun row is coloured in the mass "
        "column only, as stated above. Systems and Multi-stars share each scale; so do the three flux columns. "
        "Known within 100ly follows the Systems scales: its cells take their colours from the same table but never "
        "set it, so they move no Systems or Multi-stars colour, and its empty cells stay unfilled.",
        "Every old and new fill is logged by tab, name and column in the repo: data/colour_scales/recolour_log.json. "
        "The fills are still static: re-run data/colour_scales/recolour.py after adding rows or editing values.",
    ]


if __name__ == "__main__":
    main()
