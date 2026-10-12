# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fill "Planetless 4+ Stars" orbits from the catalogs that postdate the MSC, and fix what the MSC got wrong.

    python research.py plan     print every cell that would change, old -> new, and why; touches nothing
    python research.py write    write, mark, note, provenance, rename

Every orbit on the tab came from one place, the MSC (Tokovinin 2018, Dec 2023 update). This pass checks each pair
against three later or independent catalogs, cached in cat/:

  ORB6    Sixth Catalog of Orbits of Visual Binary Stars, www.astro.gsu.edu/wds/orb6 (orb6orbits.txt, 2026-07-09).
          omega is the secondary's, relative to the primary.
  SB9     Ninth Catalogue of Spectroscopic Binary Orbits, sb9.astro.ulb.ac.be (SB9public.tar.gz, 2024-06-21).
          omega is the primary's.
  Gaia    Gaia DR3 non-single-star solutions (gaiadr3.nss_two_body_orbit), cone-searched round each system and
          parallax-matched (gaia_nss_orbits.json). omega is the photocentre's, i.e. the primary's.

What it does, pair by pair (a pair is the secondary's row, which holds the pair's relative orbit):

1. ORB6. An orbit whose components (or, failing that, period) match the pair, graded 1-5, and passing Kepler's third
   law against the tab's masses (a^3/P^2 within a factor 2 of the mass sum) replaces the tab's orbit when the pair
   had only an MSC period estimate, or when ORB6's reference is newer than the tab's orbit source. Looked up, so
   plain; each changed cell's note names the ORB6 entry and the value it replaced.
2. SB9. Where a measured spectroscopic orbit on the tab lacks e, omega or T, the latest SB9 orbit of the same period
   supplies them (e = 0 for the circular ones). Plain.
3. Gaia DR3. Where a measured orbit lacks inclination and node, a Gaia astrometric solution of the same period gives
   them, converted from its Thiele-Innes constants (orange: arithmetic on published inputs). The 180-degree
   ambiguity of an astrometric node is resolved against the spectroscopic omega where there is one.
4. Kepler fixes (owner's decisions, 30 Sep 2026):
   - photocentre orbits, whose 'a' is the light-centre's wobble, get a = (M_tot P^2)^(1/3) (orange);
   - GJ 319 A-B and zet1 Cnc AB-C, whose published a and P cannot both hold at a solid parallax and masses, keep
     the published a and get P = (a^3 / M_tot)^(1/2) (orange, WEAK).
5. 'Argument of periastron refers to' for every pair with an omega: 'secondary (...)' for an ORB6 orbit, 'primary
   (...)' for SB9 and Gaia, and by rule from the MSC orbit record otherwise (orange): visual -> secondary,
   spectroscopic or combined -> primary.
6. Every barycentre offset whose pair's separation changed is recomputed (orange, as before).

Castor (alf Gem) is left alone: castor.py curated it value by value.
"""
import json
import math
import re
import sys
from collections import defaultdict
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
CAT = HERE / "cat"
LOG = HERE / "research_log.json"
PLAN = sys.argv[1:] == ["plan"]
SKIP_SYSTEMS = {"alf Gem"}
ORB6_SRC = "ORB6 (Sixth Catalog of Orbits of Visual Binary Stars, USNO/GSU, version of 2026-07-09)"
SB9_SRC = "SB9 (Pourbaix et al. 2004, A&A 424, 727; public release of 2024-06-21)"
GAIA_SRC = "Gaia DR3 non-single-star catalogue (Gaia Collaboration, Arenou et al. 2023, A&A 674, A34), nss_two_body_orbit"
GAIA_EPOCH_JD = 2457389.0          # J2016.0, the reference epoch of Gaia DR3 t_periastron
YR = 365.25

# The pairs whose ORB6 orbit is taken whatever the year rule says (owner's decisions, 30 Sep 2026):
#   GJ 310.1 A-B: the tab's i = 27.0 is ORB6's node; ORB6's elements replace the tab's.
#   GJ 264.1 Ca-Cb, sig CrB Ea-Eb: the tab's 'a' is a photocentre orbit; ORB6 has the measured relative orbit.
FORCE_ORB6 = {"GJ 310.1 B", "GJ 264.1 Cb", "sig CrB Eb"}
# Photocentre orbits with no relative orbit anywhere: a from Kepler.
PHOTOCENTRE = {"ksi UMa Ab", "chi Cet Ab", "HR 2158 Ab", "CD-52 2036 Ab"}
# Published a and P that cannot both hold: keep a, P from Kepler.
KEEP_A = {
    "GJ 319 B": "Josties, Gaia & Mason, IAU Commission G1 Double Stars Information Circular 205 (2021), ST 8; "
                "ORB6 grade 4 (USN2021c), listed under WDS 08427+0935",
    "zet1 Cnc C": "Izmailov 2019 (ORB6 Izm2019, STF 1196 AB,C, grade 4; sigma_P = 335 yr, sigma_a = 2.5\"); "
                  "Tokovinin et al. 2022, AJ 164, 58, note systematic residuals in Izmailov's fits for this system",
}
# ORB6 orbits that match a pair but are not taken, and why (reviewed by hand).
REJECT_ORB6 = {
    ("BD+37 1091 B", "SEI 105AB"): "ORB6 gives P = 1124 yr, which with a = 831 AU needs 455 M_sun; the tab's 21,124 yr "
                                   "passes Kepler's third law",
    # Izmailov 2019 (Astron. Lett. 45, 30) fits a short arc with no mass constraint (paper check, 1 Oct 2026, cyg17.py).
    ("17 Cyg B", "STF2580AB"): "Izm2019: 7905 yr, 40.16\" needs 9.5 M_sun (x4.7); the tab has Romanenko et al. "
                               "2025's AMP orbit, fitted with the tab's 2.02 M_sun",
    ("HR 1099 B", "STF 422"): "Izm2019: 1210 yr, 9.91\" needs 17 M_sun (x5.6); the tab keeps Hopmann 1964 "
                              "(discrepancies noted on its Orbit source cell)",
    ("iot UMa BC", "HJ 2477A,BC"): "Izm2019: 486 yr, 8.31\" needs 7.7 M_sun (x2.3); the tab keeps Zhuchkov et al. "
                                   "2012's AMP orbit, fitted with the masses fixed",
}


# ── reading ────────────────────────────────────────────────────────────────────
def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ref_year(s):
    """The year of an orbit reference: 'Tok2021b' -> 2021, '2018A&A...' -> 2018, 'VB6_Hle1994 ...' -> 1994."""
    s = str(s or "")
    m = re.search(r"[A-Za-z_]{2,4}(\d{4})[a-z]?\b", s) or re.search(r"\b(1[89]\d\d|20\d\d)", s)
    return int(m.group(1)) if m else None


def read_orb6():
    out = []

    def f(line, a, b):
        try:
            return float(line[a - 1:b].strip())
        except ValueError:
            return None

    for line in open(CAT / "orb6orbits.txt", encoding="latin-1"):
        if len(line) < 230 or not line[:2].isdigit():
            continue
        p, a, T = f(line, 82, 92), f(line, 106, 114), f(line, 163, 174)
        pu, au, tu = line[92:93], line[114:115], line[174:175]
        if not p or not a or pu not in "dyc" or au not in "am":
            continue
        tjd = None
        if T is not None:
            tjd = {"y": lambda t: 2415020.31352 + 365.242198781 * (t - 1900.0), "d": lambda t: 2400000.0 + t,
                   "m": lambda t: 2400000.5 + t, "c": lambda t: 2415020.31352 + 365.242198781 * (100 * t - 1900.0)
                   }.get(tu, lambda t: None)(T)
        desig = line[30:44].strip()
        m = re.match(r"^(.*?\d+)\s*([A-Za-z].*)?$", desig)
        out.append(dict(
            wds=line[19:29].strip(), desig=desig, comps=(m.group(2) or "").replace(" ", "") if m else "",
            P_d=p * {"d": 1.0, "y": YR, "c": 100 * YR}[pu], a_as=a / 1000.0 if au == "m" else a,
            i=f(line, 126, 133), node=f(line, 144, 151), T_jd=tjd, T_raw=f"{T}{tu}" if T is not None else None,
            e=f(line, 188, 195), omega=f(line, 206, 213), grade=line[233:235].strip(), ref=line[237:245].strip()))
    return out


def wds_near(a, b):
    """Two WDS codes for the same place: same RA to 0.2 min, declination within 3 arcmin."""
    try:
        ra = abs(int(a[:5]) - int(b[:5])) <= 2
        da = int(a[6:8]) * 60 + int(a[8:10])
        db = int(b[6:8]) * 60 + int(b[8:10])
        return ra and a[5] == b[5] and abs(da - db) <= 3
    except (ValueError, IndexError):
        return False


def read_sb9():
    def radec(s):
        ra = int(s[0:2]) + int(s[2:4]) / 60 + int(s[4:9]) / 1000 / 3600
        de = int(s[10:12]) + int(s[12:14]) / 60 + int(s[14:18]) / 100 / 3600
        return ra * 15, (-1 if s[9] == "-" else 1) * de

    pos, orbs = {}, defaultdict(list)
    for line in open(CAT / "sb9" / "Main.dta", encoding="latin-1"):
        f = line.rstrip("\r\n").split("|")
        try:
            pos[f[0]] = radec(f[2])
        except (ValueError, IndexError):
            pass
    for line in open(CAT / "sb9" / "Orbits.dta", encoding="latin-1"):
        f = line.rstrip("\r\n").split("|")
        if len(f) < 26:
            continue
        orbs[f[0]].append(dict(seq=f[0], P=num(f[2]), T=num(f[4]), e=num(f[7]), w=num(f[9]), K1=num(f[11]),
                               bib=f[22], tref=f[25]))
    return pos, orbs


def thiele_innes(A, B, F, G):
    """Campbell elements (a, i, node, omega), degrees, from Thiele-Innes constants; node in [0, 180)."""
    u = (A * A + B * B + F * F + G * G) / 2.0
    v = A * G - B * F
    a = math.sqrt(u + math.sqrt((u + v) * (u - v)))
    wpo = math.atan2(B - F, A + G)
    wmo = math.atan2(-B - F, A - G)
    w, node = (wpo + wmo) / 2.0, (wpo - wmo) / 2.0
    if node < 0:
        node += math.pi
        w += math.pi
    if node >= math.pi:
        node -= math.pi
        w -= math.pi
    i = math.degrees(math.acos(max(-1.0, min(1.0, v / (a * a)))))
    return a, i, math.degrees(node) % 360.0, math.degrees(w) % 360.0


def main():
    msc = json.loads((HERE / "msc.json").read_text(encoding="utf-8"))
    v = API.values().get(spreadsheetId=SID, range=f"{q(FP)}!A1:CZ2000", valueRenderOption="UNFORMATTED_VALUE"
                         ).execute()["values"]
    h = v[0]
    col = {k: i for i, k in enumerate(h)}
    rows = {}
    for r, row in enumerate(v[1:], start=2):
        row = row + [""] * (len(h) - len(row))
        name = row[col["Star (component)"]]
        if name:
            assert name not in rows, f"{name} appears twice"
            rows[name] = (r, row)

    changes = {}           # (name, header) -> new value
    notes = {}             # (name, header) -> note
    orange = set()         # (name, header)
    why = defaultdict(list)

    def val(name, header):
        return rows[name][1][col[header]]

    def cur(name, header):
        return changes.get((name, header), val(name, header))

    def put(name, header, value, note=None, inferred=False, reason=""):
        old = val(name, header)
        if isinstance(value, float):
            value = round(value, 6)
        if old == value and not note:
            return
        changes[(name, header)] = value
        if note:
            notes[(name, header)] = note
        if inferred:
            orange.add((name, header))
        if reason:
            why[name].append(reason)

    def mass(name):
        return num(cur(name, "Mass (M-sun)"))

    def plx_arcsec(name):
        """The parallax the tab used for this system's AU, in arcsec (from a 'Separation source' note)."""
        sysname = val(name, "System / Host")
        for n, (_, row) in rows.items():
            if row[col["System / Host"]] == sysname:
                m = re.search(r"parallax \(([\d.]+) mas\)", str(row[col["Separation source"]]))
                if m:
                    return float(m.group(1)) / 1000.0
        return 3.26156 / num(val(name, "Distance (ly)"))

    def label(name):
        return val(name, "MSC label") or name.split()[-1]

    def pairs():
        for name, (r, row) in rows.items():
            if row[col["Separation from"]] and row[col["System / Host"]] not in SKIP_SYSTEMS:
                yield name, row[col["Separation from"]]

    def kepler_ratio(sec, prim, a_au, p_d):
        m1, m2 = mass(prim), mass(sec)
        if not (m1 and m2 and a_au and p_d):
            return None
        return a_au ** 3 / (p_d / YR) ** 2 / (m1 + m2)

    counts = defaultdict(int)
    orb6 = read_orb6()

    # ── 1. ORB6 ───────────────────────────────────────────────────────────────────
    src_of = {}            # sec name -> which catalog the pair's final orbit came from
    for sec, prim in pairs():
        wds = val(sec, "WDS code")
        P, S = label(prim), label(sec)
        forms = {f"{P}{S}", f"{P},{S}"}
        common = "".join(x for x, y in zip(P, S) if x == y)
        if common and len(common) < min(len(P), len(S)):
            forms.add(f"{P},{S[len(common):]}")               # Aa1,Aa2 -> Aa1,2
        cands = [o for o in orb6 if wds_near(o["wds"], wds)]
        p_tab = num(val(sec, "Orbital period (d)"))
        by_comp = [o for o in cands if o["comps"] in forms]
        by_per = [o for o in cands if not o["comps"] or o["comps"] not in
                  {c for n2, p2 in pairs() if val(n2, "WDS code") == wds
                   for c in (f"{label(p2)}{label(n2)}", f"{label(p2)},{label(n2)}")}]
        by_per = [o for o in by_per if p_tab and abs(math.log(o["P_d"] / p_tab)) < 0.2]
        matches = by_comp or by_per
        # ORB6 and the MSC can label the same components differently (ORB6's nu Sco "Aa,Ab" is the MSC's Aab,Ac),
        # so a component match must also agree in period: within 1.5x of a measured orbit, 3x of an MSC estimate.
        if p_tab:
            tol = math.log(1.5 if val(sec, "Period basis") == "orbit" else 3.0)
            matches = [o for o in matches if abs(math.log(o["P_d"] / p_tab)) < tol]
        if not matches:
            continue
        plx = plx_arcsec(sec)
        scored = []
        for o in matches:
            if (sec, o["desig"]) in REJECT_ORB6:
                counts["orb6_rejected_by_hand"] += 1
                continue
            a_au = o["a_as"] / plx
            k = kepler_ratio(sec, prim, a_au, o["P_d"])
            grade = int(o["grade"]) if o["grade"].isdigit() else 9
            scored.append((grade, -(ref_year(o["ref"]) or 0), o, a_au, k))
        if not scored:
            continue
        scored.sort(key=lambda s: (s[0], s[1]))
        ok = [s for s in scored if s[0] <= 5 and (s[4] is None or 0.5 < s[4] < 2.0)]
        if not ok:
            counts["orb6_fails_grade_or_kepler"] += 1
            continue
        grade, _, o, a_au, k = ok[0]
        basis = val(sec, "Period basis")
        same = (p_tab and abs(o["P_d"] / p_tab - 1) < 0.005 and num(val(sec, "Inclination (deg)")) is not None
                and abs(o["i"] - num(val(sec, "Inclination (deg)"))) < 0.5)
        year_tab = ref_year(val(sec, "Orbit source"))
        newer = (ref_year(o["ref"]) or 0) > (year_tab or 0)
        take = sec in FORCE_ORB6 or (basis != "orbit") or (newer and not same)
        if same and sec not in FORCE_ORB6:
            src_of[sec] = "orb6-same"
            counts["orb6_same_as_tab"] += 1
            continue
        if not take:
            counts["orb6_older_kept_tab"] += 1
            continue
        old = {hd: val(sec, hd) for hd in ("Orbital period (d)", "Separation (AU)", "Orbital eccentricity (e)",
                                           "Inclination (deg)", "Ascending node (deg)", "Argument of periastron (deg)",
                                           "Time of periastron (JD)", "Orbit source")}
        src = f"{ORB6_SRC}: {o['desig']} ({o['wds']}), {o['ref']}, grade {o['grade']}"
        was = "; ".join(f"{hd} was {x!r}" for hd, x in old.items() if x not in ("", None))
        base = f"SOURCE: {src}. Replaces the MSC value ({was or 'no orbit on file'})."
        kind = ("new orbit (the tab had only an MSC period estimate)" if basis != "orbit" else
                "forced by review" if sec in FORCE_ORB6 else f"newer than the tab's orbit ({year_tab})")
        reason = f"ORB6 {o['desig']} {o['ref']} gr{o['grade']}: {kind}; Kepler ratio {k:.2f}" if k else \
            f"ORB6 {o['desig']} {o['ref']} gr{o['grade']}: {kind}"
        put(sec, "Orbital period (d)", round(o["P_d"], 4), base, reason=reason)
        put(sec, "Separation (AU)", round(a_au, 5), f"{base} au = {o['a_as']}\" / parallax ({plx * 1000:.2f} mas).")
        put(sec, "Separation (arcsec)", o["a_as"])
        put(sec, "Separation type", "semi-major axis")
        put(sec, "Period basis", "orbit")
        put(sec, "Orbit source", f"ORB6 {o['desig']} {o['ref']} Gr.{o['grade']}")
        put(sec, "Separation source", f"{src}: orbit semi-major axis {o['a_as']}\"; au = arcsec / parallax "
                                      f"({plx * 1000:.2f} mas)")
        for hd, x in (("Orbital eccentricity (e)", o["e"]), ("Inclination (deg)", o["i"]),
                      ("Ascending node (deg)", o["node"]), ("Argument of periastron (deg)", o["omega"])):
            if x is not None:
                put(sec, hd, x, base)
        if o["T_jd"] is not None:
            put(sec, "Time of periastron (JD)", round(o["T_jd"], 4),
                f"{base} ORB6 gives T = {o['T_raw']}"
                + (" (Besselian year; JD = 2415020.31352 + 365.242198781 x (B - 1900))" if o["T_raw"].endswith("y")
                   else "") + ".")
        src_of[sec] = "orb6"
        counts["orb6_new_orbit" if basis != "orbit" else "orb6_replaced"] += 1

    # ── 2. SB9: e, omega, T for measured spectroscopic orbits that lack them ─────────────────────
    sb9_pos, sb9_orbs = read_sb9()
    for sec, prim in pairs():
        if val(sec, "Period basis") != "orbit" or src_of.get(sec) == "orb6":
            continue
        need = [hd for hd in ("Orbital eccentricity (e)", "Argument of periastron (deg)", "Time of periastron (JD)")
                if num(cur(sec, hd)) is None]
        if not need:
            continue
        p_tab = num(val(sec, "Orbital period (d)"))
        ra, de = num(val(sec, "RA (deg, ICRS)")), num(val(sec, "Dec (deg, ICRS)"))
        best = None
        for seq, (sra, sde) in sb9_pos.items():
            if math.hypot((sra - ra) * math.cos(math.radians(de)), sde - de) * 3600 > 30:
                continue
            for o in sb9_orbs[seq]:
                if o["P"] and p_tab and abs(o["P"] / p_tab - 1) < 0.002 and o["e"] is not None:
                    if best is None or (ref_year(o["bib"]) or 0) > (ref_year(best["bib"]) or 0):
                        best = o
        if not best:
            continue
        # T only means something with the e and omega it was fitted with: take a missing element only from the
        # paper the tab's orbit already came from (or when the tab has none of the three).
        if len(need) < 3 and best["bib"] not in str(val(sec, "Orbit source")):
            counts["sb9_other_paper_skipped"] += 1
            continue
        src = f"{SB9_SRC}, system {best['seq']}, orbit {best['bib']}"
        tjd = best["T"] + (2400000.5 if best["tref"] == "MJD" else 2400000.0) if best["T"] is not None else None
        fill = {"Orbital eccentricity (e)": best["e"], "Argument of periastron (deg)": best["w"],
                "Time of periastron (JD)": tjd}
        for hd in need:
            if fill[hd] is not None:
                circ = " The orbit is circular (e = 0): omega is conventional and T marks the zero point of phase." \
                    if best["e"] == 0 else ""
                put(sec, hd, fill[hd], f"SOURCE: {src}.{circ}", reason=f"SB9 {best['bib']}: {hd}")
                counts["sb9_filled"] += 1
        src_of.setdefault(sec, "sb9")

    # ── 3. Gaia DR3: inclination and node for measured orbits that lack them ───────────────────
    gaia = json.loads((CAT / "gaia_nss_orbits.json").read_text())
    for sec, prim in pairs():
        # a measured orbit only: a Gaia solution near an MSC estimate is as likely another pair's (BD+08 2134)
        if num(cur(sec, "Inclination (deg)")) is not None or cur(sec, "Period basis") != "orbit":
            continue
        sysname = val(sec, "System / Host")
        p_tab = num(cur(sec, "Orbital period (d)"))
        for g in gaia["rows"]:
            if gaia["systems"][str(g["source_id"])][0] != sysname or g.get("a_thiele_innes") is None:
                continue
            if not p_tab or abs(math.log(g["period"] / p_tab)) > 0.2:
                continue
            a_mas, inc, node, w = thiele_innes(g["a_thiele_innes"], g["b_thiele_innes"], g["f_thiele_innes"],
                                               g["g_thiele_innes"])
            w_sb = num(cur(sec, "Argument of periastron (deg)"))
            flipped = False
            if w_sb is not None:
                d = abs((w - w_sb + 180) % 360 - 180)
                if d > 90:
                    node, w, flipped = (node + 180) % 360, (w + 180) % 360, True
            weak = []
            if g["nss_solution_type"] == "OrbitalTargetedSearch":
                weak.append("an OrbitalTargetedSearch solution, which Gaia did not validate")
            if abs(g["period"] / p_tab - 1) > 0.02:
                weak.append(f"Gaia's period ({g['period']:.1f} d) differs from the tab's ({p_tab:.1f} d)")
            src = (f"{GAIA_SRC}, source_id {g['source_id']}, solution type {g['nss_solution_type']}, "
                   f"P = {g['period']:.4f} d, significance {g['significance']:.1f}")
            how = ("INFERRED: Campbell elements from Gaia's Thiele-Innes constants A, B, F, G (the standard "
                   "transformation, Gaia DR3 documentation 4.2): "
                   f"A={g['a_thiele_innes']:.4f}, B={g['b_thiele_innes']:.4f}, F={g['f_thiele_innes']:.4f}, "
                   f"G={g['g_thiele_innes']:.4f} mas -> photocentre a = {a_mas:.3f} mas, i = {inc:.2f}, node = "
                   f"{node:.2f}, omega = {w:.2f}. "
                   + ("The astrometric node's 180-degree ambiguity is resolved against the spectroscopic omega "
                      f"({w_sb}): {'flipped' if flipped else 'kept'}. " if w_sb is not None else
                      "An astrometric node is ambiguous by 180 degrees; Gaia's convention (node < 180) is kept. "))
            note = ("WEAK: " + "; ".join(weak) + ".\n" if weak else "") + how + f"SOURCE: {src}."
            put(sec, "Inclination (deg)", round(inc, 2), note, inferred=True,
                reason=f"Gaia {g['nss_solution_type']} P={g['period']:.2f} d: i, node")
            put(sec, "Ascending node (deg)", round(node, 2), note, inferred=True)
            # e, omega and T only as a set, and only where the tab has none of them: mixing one fit's T with
            # another's e and omega puts the star at the wrong phase.
            shape = ("Orbital eccentricity (e)", "Argument of periastron (deg)", "Time of periastron (JD)")
            if all(num(cur(sec, hd)) is None for hd in shape):
                put(sec, "Argument of periastron (deg)", round(w, 2), note, inferred=True)
                put(sec, "Orbital eccentricity (e)", round(g["eccentricity"], 4), f"SOURCE: {src}.")
                put(sec, "Time of periastron (JD)", round(GAIA_EPOCH_JD + g["t_periastron"], 4),
                    f"SOURCE: {src}. T = J2016.0 (JD {GAIA_EPOCH_JD}) + t_periastron ({g['t_periastron']:.3f} d).")
            src_of.setdefault(sec, "gaia")
            counts["gaia_i_node"] += 1
            break

    # ── 4. Kepler fixes ───────────────────────────────────────────────────────────────────
    for sec, prim in pairs():
        if sec in PHOTOCENTRE:
            P = num(cur(sec, "Orbital period (d)"))
            m1, m2 = mass(prim), mass(sec)
            a_old = num(cur(sec, "Separation (AU)"))
            a_new = ((m1 + m2) * (P / YR) ** 2) ** (1 / 3)
            plx = plx_arcsec(sec)
            weak = "minimum" in f"{val(sec, 'Mass basis (MSC)')} {val(prim, 'Mass basis (MSC)')}"
            note = (("WEAK: a mass is a minimum mass.\n" if weak else "")
                    + f"INFERRED: the published orbit's 'a' ({a_old} AU, {val(sec, 'Separation (arcsec)')}\") is the "
                    f"photocentre's orbit, not the relative orbit: with these masses Kepler's third law needs "
                    f"{a_new:.4f} AU. a = ((M_{prim.split()[-1]} + M_{sec.split()[-1]}) x P^2)^(1/3) = (({m1} + "
                    f"{m2}) x ({P} d / 365.25)^2)^(1/3), masses from this tab. Orbit source: "
                    f"{val(sec, 'Orbit source')}.")
            put(sec, "Separation (AU)", round(a_new, 5), note, inferred=True, reason="photocentre a -> Kepler a")
            put(sec, "Separation (arcsec)", round(a_new * plx, 6), note, inferred=True)
            counts["kepler_a"] += 1
        if sec in KEEP_A:
            a = num(cur(sec, "Separation (AU)"))
            m1, m2 = mass(prim), mass(sec)
            p_old = num(cur(sec, "Orbital period (d)"))
            p_new = math.sqrt(a ** 3 / (m1 + m2)) * YR
            note = (f"WEAK: the published period ({p_old:.1f} d = {p_old / YR:.1f} yr) and semi-major axis ({a} AU) "
                    f"cannot both hold: together they need {a ** 3 / (p_old / YR) ** 2:.2f} M_sun, against "
                    f"{m1 + m2:.2f} M_sun from this tab's masses at the Gaia parallax.\n"
                    f"INFERRED: the owner kept the measured a and orientation and set P = (a^3 / M_tot)^(1/2) x 365.25 "
                    f"= ({a}^3 / {m1 + m2:.2f})^(1/2) yr = {p_new / YR:.1f} yr. Published orbit: {KEEP_A[sec]}.")
            put(sec, "Orbital period (d)", round(p_new, 1), note, inferred=True, reason="Kepler P, a kept")
            counts["kepler_p"] += 1

    # ── 5. omega convention ────────────────────────────────────────────────────────────────
    RULE_NOTE = ("INFERRED by rule from the MSC orbit record ({kind}): {why}. Not checked against the paper; "
                 "a wrong convention puts the star 180 degrees round its orbit.")
    for sec, prim in pairs():
        if num(cur(sec, "Argument of periastron (deg)")) is None or cur(sec, "Argument of periastron refers to"):
            continue
        P, S = label(prim), label(sec)
        how = src_of.get(sec)
        if how in ("orb6", "orb6-same"):
            put(sec, "Argument of periastron refers to", f"secondary ({S} relative to {P})",
                f"SOURCE: {ORB6_SRC} convention: omega is the secondary's, relative to the primary.")
            counts["omega_orb6"] += 1
            continue
        if how in ("sb9", "gaia"):
            put(sec, "Argument of periastron refers to", f"primary ({P})",
                f"SOURCE: {SB9_SRC if how == 'sb9' else GAIA_SRC} convention: omega is the primary's.")
            counts["omega_catalog"] += 1
            continue
        rec = msc[val(sec, "WDS code")]
        o = best_orbit(rec["orbits"], P, S)
        vis = o is not None and o["a"] not in (None, "")
        spec = o is not None and o["K1"] not in (None, "")
        if vis and not spec:
            text, kind, w = f"secondary ({S} relative to {P})", "visual orbit", "a visual orbit quotes the " \
                                                                             "secondary's omega"
        elif spec:
            text, kind = f"primary ({P})", "combined visual-spectroscopic orbit" if vis else "spectroscopic orbit"
            w = ("a spectroscopic orbit quotes the primary's omega" if not vis else
                 "a combined orbit is usually quoted with the primary's omega so that it matches the radial "
                 "velocities; WEAK, check the paper")
        else:
            text, kind, w = f"primary ({P})", "no orbit record", "WEAK: nothing says which; the primary's is assumed"
        note = RULE_NOTE.format(kind=kind, why=w)
        if "WEAK" in w:
            note = "WEAK: convention not stated by the source.\n" + note
        put(sec, "Argument of periastron refers to", text, note, inferred=True)
        counts["omega_rule"] += 1

    # ── 6. barycentre offsets that follow a changed separation ───────────────────────────────
    for name, (r, row) in rows.items():
        if row[col["Node type"]] != "subsystem" or row[col["System / Host"]] in SKIP_SYSTEMS:
            continue
        prim = row[col["Barycentre from"]]
        if not prim:
            continue
        sec = next((n for n, p in pairs() if p == prim and val(n, "System / Host") == row[col["System / Host"]]
                    and val(n, "Member of") == name), None)
        if not sec or (sec, "Separation (AU)") not in changes:
            continue
        a, m1, m2 = num(cur(sec, "Separation (AU)")), mass(prim), mass(sec)
        if a is None or m1 is None or m2 is None:
            continue
        off = a * m2 / (m1 + m2)
        put(name, "Barycentre offset (AU)", round(off, 6),
            f"INFERRED: a x M_sec / (M_prim + M_sec) = {a} au x {m2} / ({m1} + {m2}), from '{sec}' (Separation (AU), "
            f"revised by research.py, 30 Sep 2026) and '{prim}' (Mass).", inferred=True,
            reason="barycentre follows the new separation")
        counts["barycentre"] += 1

    # ── report / write ─────────────────────────────────────────────────────────────────────
    by_name = defaultdict(list)
    for (name, hd), x in changes.items():
        by_name[name].append((hd, val(name, hd), x))
    sp_lines = sp_entry(counts)
    if PLAN:
        for name in sorted(by_name, key=lambda n: rows[n][0]):
            print(f"\n{name}  (row {rows[name][0]})  -- {'; '.join(dict.fromkeys(why[name]))}")
            for hd, old, new in by_name[name]:
                mark = " [orange]" if (name, hd) in orange else ""
                print(f"    {hd:34} {str(old)[:40]!s:>40} -> {str(new)[:60]}{mark}")
        print("\n" + json.dumps(counts, indent=1))
        print(f"{len(changes)} cells in {len(by_name)} rows; {len(orange)} orange")
        print("\n".join(sp_lines))
        return

    cell = {}
    for (name, hd) in changes:
        cell[(name, hd)] = f"{q(FP)}!{letter(col[hd])}{rows[name][0]}"
    updates = {cell[k]: [[x]] for k, x in changes.items()}
    expect = {cell[k]: val(*k) for k in changes}
    items = list(updates.items())
    for s in range(0, len(items), 150):
        chunk = dict(items[s:s + 150])
        gs.update_cells(SID, chunk, expect={k: expect[k] for k in chunk})
    orange_cells = [cell[k] for k in orange]
    for s in range(0, len(orange_cells), 200):
        gs.set_border(SID, orange_cells[s:s + 200], gs.INFERRED_BORDER)
    nitems = [(cell[k], n) for k, n in notes.items()]
    for s in range(0, len(nitems), 200):
        gs.set_note(SID, dict(nitems[s:s + 200]))

    meta = API.get(spreadsheetId=SID, fields="sheets(properties(title,sheetId,gridProperties))").execute()["sheets"]
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
    log = {"counts": counts, "sp_rows": [start, end], "title": title,
           "changes": {f"{n} | {hd}": {"old": val(n, hd), "new": x, "cell": cell[(n, hd)],
                                        "orange": (n, hd) in orange} for (n, hd), x in changes.items()}}
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    print("done:", json.dumps({"counts": counts, "sp_rows": [start, end], "title": title}, ensure_ascii=False))


def sp_entry(c):
    return [
        "",
        "30 SEPTEMBER 2026: 'Planetless 4+ Stars' -- ORBITS CHECKED AGAINST ORB6, SB9 AND GAIA DR3 (research.py).",
        "Writer: data/four_plus_stars/research.py; log research_log.json; catalogs cached in data/four_plus_stars/cat/. "
        "Every changed cell carries a note naming its source and the value it replaced.",
        f"ORB6 ({ORB6_SRC}; orb6orbits.txt). Matched by WDS code (declination within 3 arcmin, since ORB6 and the "
        "MSC can differ by a minute: GJ 319 is 08427+0935 in ORB6, 08427+0933 in the MSC) and by components, else by "
        "period within 20%. Taken only at grade 1-5 and only if a^3/P^2 is within a factor 2 of the tab's mass sum. "
        f"{c['orb6_new_orbit']} pairs with only an MSC period estimate got a measured orbit; {c['orb6_replaced']} "
        f"MSC orbits were replaced by a newer ORB6 one; {c['orb6_same_as_tab']} matched the tab exactly. Confidence: "
        "as ORB6's grade. Verify: orb6orbits.txt by WDS code.",
        "  Reviewed by hand: GJ 310.1 A-B took ORB6's elements (Baize 2021, grade 5) because the tab's inclination "
        "(27.0) was ORB6's node; GJ 264.1 Ca-Cb (Tokovinin 2019) and sig CrB Ea-Eb (Tokovinin 2019) took ORB6's "
        "relative orbits because the tab's 'a' was a photocentre orbit; BD+37 1091 A-B kept the tab's 21,124 yr "
        "because ORB6's 1,124 yr needs 455 M_sun.",
        f"SB9 ({SB9_SRC}). For measured orbits lacking e, omega or T: the latest SB9 orbit within 30 arcsec whose "
        f"period agrees to 0.2%. {c['sb9_filled']} cells. For a circular orbit (e = 0) omega is conventional and T is "
        "SB9's zero point of phase. Confidence HIGH. Verify: SB9 Orbits.dta by system number (in each note).",
        f"Gaia DR3 ({GAIA_SRC}). Cone search (72 arcsec) round each component, parallax within 20%. "
        f"{c['gaia_i_node']} measured orbits lacking inclination and node got them from a Gaia astrometric "
        "solution of the same period. INFERRED (orange): Campbell elements from the Thiele-Innes constants, "
        "u = (A^2+B^2+F^2+G^2)/2, v = AG-BF, a = sqrt(u + sqrt(u^2-v^2)), tan(w+O) = (B-F)/(A+G), tan(w-O) = "
        "(-B-F)/(A-G), cos i = v/a^2. The astrometric node's 180-degree ambiguity is resolved against the "
        "spectroscopic omega where there is one. WEAK where the solution is an unvalidated OrbitalTargetedSearch "
        "or its period differs from the tab's by more than 2%. Verify: gaiadr3.nss_two_body_orbit by source_id.",
        f"Photocentre orbits (owner's decision, 30 Sep 2026): {c['kepler_a']} astrometric orbits whose 'a' was the "
        "light-centre's wobble (ksi UMa Aa-Ab, chi Cet Aa-Ab, HR 2158 Aa-Ab, CD-52 2036 Aa-Ab; all Hipparcos-era "
        "grade-9 or single-star astrometric solutions) now carry the relative semi-major axis from Kepler's third "
        "law, a = ((M1 + M2) P^2)^(1/3) in AU, years and solar masses, with the tab's masses. INFERRED (orange); "
        "the old value is in each note. Its error is the masses': a 10% mass error is 3% in a.",
        f"Dynamically inconsistent orbits (owner's decision, 30 Sep 2026): GJ 319 A-B (Josties, Gaia & Mason, DS "
        "Circ. 205, 2021) and zet1 Cnc AB-C (Izmailov 2019) have published a and P that need 4.6 and 16.9 M_sun "
        "against 1.16 and 4.28 M_sun from the tab's masses at the Gaia parallax. Both keep the published a and "
        "orientation; P = (a^3/M_tot)^(1/2). INFERRED, WEAK (orange); the published P is in each note. Tokovinin et "
        "al. 2022 (AJ 164, 58) found systematic residuals in Izmailov's fits for zet Cnc.",
        f"'Argument of periastron refers to': filled for every pair with an omega. From the catalog's documented "
        f"convention for ORB6 ({c['omega_orb6']}), SB9 and Gaia ({c['omega_catalog']}) orbits; otherwise by rule "
        f"from the MSC orbit record ({c['omega_rule']}, orange): visual -> secondary, spectroscopic -> primary, "
        "combined -> primary (WEAK; papers differ). Why it matters: a wrong convention puts a star 180 degrees round "
        "its orbit, which no other check can see.",
        f"Barycentre offsets: {c['barycentre']} recomputed where their pair's separation changed, by the formula of "
        "orbits.py (orange, as before).",
    ]


if __name__ == "__main__":
    main()
