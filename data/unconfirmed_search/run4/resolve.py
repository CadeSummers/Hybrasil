# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pick one catalogue value per blank Systems cell from candidates.json; write plan.json. Read-only."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = json.loads((HERE / "candidates.json").read_text(encoding="utf-8"))


def num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def ref(link):
    m = re.search(r">\s*([^<]+?)\s*</a>", link or "")
    return m.group(1) if m else (link or "")


BANDS = {"O": (25000, 60000), "B": (10000, 32000), "A": (7000, 11000), "F": (5900, 7600), "G": (5100, 6300),
         "K": (3800, 5400), "M": (2300, 4100), "L": (1200, 2500), "T": (500, 1400), "Y": (250, 600)}


def band(cls):
    m = re.match(r"~?\s*(sd|d)?([OBAFGKMLTY])", (cls or "").strip())
    return m.group(2) if m else None


plan, flags = {}, []
for name, c in C.items():
    n, t, g = c["nasa"] or {}, c["tic"] or {}, c["gaia_ap"] or {}
    # Mass and Teff are the row's own star (the primary); an archive row matched only through the
    # planet-host star is a different star when the planets orbit a companion (GJ 667 A vs C).
    # GJ 900 A: the archive's st_mass (1.08, Rothermich et al. 2024) is the whole triple's mass, not A's.
    own = name != "GJ 900 A" and bool(n) and (n.get("hostname") == name or (n.get("gaia_dr3_id") or "").replace("Gaia DR3 ", "") == c["gaia"])
    nk = n if own else {}
    cls = c["class"] or ((c["simbad"] or {}).get("sp_type") or "")
    kind = "WD" if cls.strip().startswith("D") or "WD" in name or "white" in cls.lower() else \
        "BD" if band(cls) in ("L", "T", "Y") else ""
    pick = {}
    if "H" in c["missing"] and c["simbad"] and c["simbad"].get("sp_type"):
        s = c["simbad"]
        pick["H"] = (s["sp_type"].strip(), f"SIMBAD sp_type ({s['main_id'].strip()}; ref {s.get('sp_bibcode') or 'n/a'})", False)
    if "K" in c["missing"]:
        if num(nk.get("st_teff")):
            pick["K"] = (round(num(nk["st_teff"])), f"NASA Exoplanet Archive pscomppars st_teff ({ref(nk.get('st_teff_reflink'))})", False)
        elif num(t.get("Teff")) and not kind:
            pick["K"] = (round(num(t["Teff"])), f"TIC v8.2 Teff (Stassun et al. 2019; source {t.get('r_Teff','').strip() or 'n/a'}), "
                                                f"+/- {t.get('s_Teff') or '?'} K", False)
        elif num(g.get("teff_gspspec")) and band(cls) not in ("M", "L", "T", "Y"):   # GSP-Spec is weak for M dwarfs
            pick["K"] = (round(num(g["teff_gspspec"])), "Gaia DR3 GSP-Spec teff_gspspec", False)
    if "G" in c["missing"]:
        if num(nk.get("st_mass")):
            pick["G"] = (round(num(nk["st_mass"]), 3), f"NASA Exoplanet Archive pscomppars st_mass ({ref(nk.get('st_mass_reflink'))})", False)
        elif num(t.get("Mass")) and not kind:
            pick["G"] = (round(num(t["Mass"]), 3), f"TIC v8.2 Mass (Stassun et al. 2019), +/- {t.get('s_Mass') or '?'} M-sun", False)
        elif num(g.get("mass_flame")) and not kind:
            pick["G"] = (round(num(g["mass_flame"]), 3), "Gaia DR3 FLAME mass_flame", False)
    if "N" in c["missing"]:
        teff = num(n.get("st_teff")) or num(t.get("Teff")) or 0
        cool = teff and teff < 4000
        if num(t.get("Lum")) and not kind and (cool or not num(g.get("lum_flame"))):
            pick["N"] = (float(f"{num(t['Lum']):.4g}"), f"TIC v8.2 Lum (Stassun et al. 2019), +/- {t.get('s_Lum') or '?'} L-sun", False)
        elif num(g.get("lum_flame")) and not kind:
            pick["N"] = (float(f"{num(g['lum_flame']):.4g}"), "Gaia DR3 FLAME lum_flame (bolometric)", False)
        elif num(n.get("st_lum")):
            v = 10 ** num(n["st_lum"])
            pick["N"] = (float(f"{v:.4g}"), f"10^st_lum, NASA Exoplanet Archive pscomppars ({ref(n.get('st_lum_reflink'))}); "
                                            f"st_lum = {n['st_lum']} (log10 L-sun)", True)
    # sanity: Teff inside the class's band
    b = band(pick.get("H", (cls,))[0] if "H" in pick else cls)
    tv = pick.get("K", (None,))[0]
    if tv and b in BANDS and not (BANDS[b][0] <= tv <= BANDS[b][1]):
        flags.append(f"{name}: Teff {tv} outside class {cls!r} band {BANDS[b]}")
    left = [m for m in c["missing"] if m not in pick]
    if kind or left:
        flags.append(f"{name}: {kind or 'dwarf'} class {cls!r}; unfilled {left}")
    plan[name] = {"row": c["row"], "missing": c["missing"], "pick": pick, "kind": kind, "unfilled": left}

(HERE / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
from collections import Counter
cnt = Counter(k for p in plan.values() for k in p["pick"])
src = Counter((k, v[1].split(" (")[0].split(",")[0]) for p in plan.values() for k, v in p["pick"].items())
print("filled:", dict(cnt), "| unfilled:", Counter(k for p in plan.values() for k in p["unfilled"]))
for (k, s), m in sorted(src.items()): print(f"  {k} {m:3} {s}")
print("FLAGS:"); [print("  " + f) for f in flags]
