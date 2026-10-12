# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Turn the merged research into an exact write plan. Read-only except plan.json / plan.txt.

Owner's rulings applied (26-27 Sep 2026):
  * every candidate is written, tiered honestly; `unlikely` -> Rejected candidates tab;
  * a new Systems row only for a host with a live (strong/ambiguous) candidate;
  * Planets/Systems corrections are recorded, not made (except the Unconfirmed housekeeping);
  * Kiefer 2025: only the four exoplanet.eu lists (already the only four in the records);
  * Tuomi et al. 2019 alone caps at ambiguous; PMa / trend-only rows stay ambiguous candidates.
"""
import csv
import io
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pack"))
import hz  # noqa: E402  the sheet's own Kopparapu recipe

REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from hybrasil.data import google_sheets as gs  # noqa: E402  (reads only)

M_JUP_E, M_SUN_E, R_JUP_E = 317.828, 332946.0, 11.209
merged = json.loads((HERE / "merged.json").read_text(encoding="utf-8"))


def val(x):
    return x.get("value") if isinstance(x, dict) else x


def key(name):
    s = (name or "").lower().replace("gliese", "gj").replace("gl ", "gj ")
    return re.sub(r"[\s_\-.]+", "", s)


def load_csv(name):
    with open(HERE / "pack" / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


systems = {r["system_host"]: r for r in load_csv("systems.csv")}
multistars = {r["Star (component)"]: r for r in load_csv("multistars.csv")}

# ---- 1. candidates, with the writer's overrides ---------------------------------------------
DROP = {"CD-35 2722 b I": "already on the Exomoons tab (Hoy et al. 2026)",
        "CD-35 2722 b II": "the two-satellite alternative, already in the Exomoons row's Alternative solution"}
TIER = {"HD 192310 candidate P=24.6d": ("ambiguous", "Writer: K ~0.6 m/s at the first harmonic of the rotation period, "
                                        "which the brief tiers ambiguous."),
        "HD 3765 c": ("ambiguous", "Writer: the authors note the period is about 3x the 44.7 d rotation period, "
                      "which the brief tiers ambiguous."),
        "HD 82943 d": ("unlikely", "Writer: the California Legacy Survey (Rosenthal et al. 2021, Table 7) classes this "
                       "signal a false positive.")}
cands, dropped = [], []
for c in merged["candidates"]:
    if c["_on_sheet"] or c["_dup_of"]:
        continue
    if c["planet"] in DROP:
        dropped.append((c["planet"], DROP[c["planet"]]))
        continue
    if c["planet"] in TIER:
        t, why = TIER[c["planet"]]
        c["tier_reason"] = f"{c['tier_reason']} {why} (Agent tier: {c['tier']}.)"
        c["tier"] = t
    ref = (c.get("reference") or "") + " " + json.dumps(c.get("sources") or {})
    if c["tier"] == "strong" and "Tuomi" in ref and not re.search(r"(Feng|Mignon|Pinamonti|Ribas|Gonz)", ref):
        c["tier"], c["tier_reason"] = "ambiguous", c["tier_reason"] + " Capped: Tuomi et al. 2019 alone."
    cands.append(c)

# ---- 2. host renames (C07) and Systems rows ---------------------------------------------------
new_sys_records = {}
for s in merged["new_systems"]:
    if s["system_host"] in systems:
        continue                      # carried-over record of a host already on Systems
    new_sys_records.setdefault(s["system_host"], s)
RENAME = {}                           # TOI-2009 -> HD 6660 etc.
for s in new_sys_records.values():
    old = s.get("toi_host_name_on_unconfirmed_tab")
    if old and old != s["system_host"]:
        RENAME[old] = s["system_host"]
RENAME.update({"TOI-6276": "HIP 56998", "TOI-6713": "HD 104067"})
alias_to_new = {key(a): n for n, s in new_sys_records.items() for a in [n] + list(s.get("aliases") or [])}

for c in cands:
    for f in ("system_host", "planet_host_star"):
        h = c.get(f) or ""
        h = RENAME.get(h, h)
        if h not in systems and h not in new_sys_records and key(h) in alias_to_new:
            h = alias_to_new[key(h)]
        c[f] = h
    if not c.get("planet_host_star"):
        c["planet_host_star"] = c["system_host"]

unconf = load_csv("unconfirmed_existing.csv")
live_hosts = {c["system_host"] for c in cands if c["tier"] != "unlikely"}
for r in unconf:                      # the 22 TOI hosts of the existing rows
    h = RENAME.get(r["system_host"], r["system_host"])
    if r["tier"] != "unlikely":
        live_hosts.add(h)
need_rows = sorted(h for h in live_hosts if h not in systems)
missing_record = [h for h in need_rows if h not in new_sys_records]

# ---- 3. Gaia DR3 for every new host (one query) ------------------------------------------------
ids = {h: str(new_sys_records[h]["gaia_dr3_source_id"]).strip() for h in need_rows
       if h in new_sys_records and re.fullmatch(r"\d{10,20}", str(new_sys_records[h]["gaia_dr3_source_id"]).strip())}
q = ("select source_id, ra, dec, parallax, pmra, pmdec, radial_velocity, ruwe from gaiadr3.gaia_source "
     f"where source_id in ({','.join(ids.values())})")
url = "https://gea.esac.esa.int/tap-server/tap/sync?" + urllib.parse.urlencode(
    {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": q})
gaia = {r["source_id"]: r for r in csv.DictReader(io.StringIO(urllib.request.urlopen(url, timeout=180).read().decode()))}


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def sort_key(cls):
    m = re.match(r"\s*~?\s*([OBAFGKMLTYD])\s*([0-9.]*)", cls or "")
    if not m:
        return ""
    base = {"O": 0, "B": 10, "A": 20, "F": 30, "G": 40, "K": 50, "M": 60, "L": 70, "T": 80, "Y": 85, "D": 90}[m.group(1)]
    try:
        return base + (float(m.group(2)) if m.group(2) else 5)
    except ValueError:
        return base + 5


def kinematics(ra, dec, plx, pmra, pmdec, rv):
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    out = {"l": None, "b": None, "mu": None, "v": None, "ml": None, "mb": None}
    c = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs").galactic
    out["l"], out["b"] = round(c.l.deg, 2), round(c.b.deg, 2)
    if pmra is None or pmdec is None or not plx:
        return out
    mu = math.hypot(pmra, pmdec) / 1000.0
    out["mu"] = round(mu, 3)
    if rv is None:
        return out
    d_pc = 1000.0 / plx
    out["v"] = round(math.hypot(rv, 4.74047 * mu * d_pc), 3)
    s = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, distance=d_pc * u.pc, pm_ra_cosdec=pmra * u.mas / u.yr,
                 pm_dec=pmdec * u.mas / u.yr, radial_velocity=rv * u.km / u.s, frame="icrs").galactic
    vel = s.velocity.d_xyz.to(u.km / u.s).value
    U, V, W = (float(x) for x in vel)
    vv = math.sqrt(U * U + V * V + W * W)
    out["ml"], out["mb"] = round(math.degrees(math.atan2(V, U)) % 360, 2), round(math.degrees(math.asin(W / vv)), 2)
    return out


# Looked up by the writer, 27 Sep 2026 (gaiadr3.astrophysical_parameters): TIC v8.2 has no Teff for these.
FILL = {"GJ 412 A": (3382.2, 0.023333, "WEAK: Teff is Gaia DR3 GSP-Phot (3382 K), poor for M dwarfs; luminosity is "
                                      "Gaia DR3 FLAME lum_flame 0.02333. TIC v8.2 has no Teff for this star."),
        "GJ 257 A": (3179.5, 0.0078880, "WEAK: Teff is Gaia DR3 GSP-Phot (3179 K), poor for M dwarfs; luminosity is "
                                        "Gaia DR3 FLAME lum_flame 0.007888. A 2.4 arcsec binary: B's light may bias both.")}
systems_rows, orange, notes, host_facts = [], [], {}, {}
for h in need_rows:
    s = new_sys_records.get(h)
    if s is None:
        continue
    g = gaia.get(ids.get(h, ""), {})
    ra, dec, plx = fnum(g.get("ra")), fnum(g.get("dec")), fnum(g.get("parallax")) or fnum(val(s["parallax_mas"]))
    pmra = fnum(g.get("pmra")) if g else fnum(val(s["pmra_masyr"]))
    pmdec = fnum(g.get("pmdec")) if g else fnum(val(s["pmdec_masyr"]))
    rv = fnum(g.get("radial_velocity")) if g.get("radial_velocity") else fnum(val(s["rv_kms"]))
    rv_src = "Gaia DR3" if g.get("radial_velocity") else ("research record" if rv is not None else "")
    teff, lum, rad = fnum(val(s["teff_k"])), fnum(val(s["luminosity_lsun"])), fnum(val(s["radius_rsun"]))
    fill_note = ""
    if h in FILL and (teff is None or lum is None):
        teff, lum, fill_note = FILL[h]
    lum_inferred = False
    if lum is None and teff and rad:
        lum, lum_inferred = rad * rad * (teff / 5772.0) ** 4, True
    cls = val(s["stellar_class"]) or ""
    kin = kinematics(ra, dec, plx, pmra, pmdec, rv) if ra is not None else {}
    bnds = hz.bounds(lum, teff) if (teff and lum) else None
    host_facts[h] = {"mass": fnum(val(s["host_mass_msun"])), "lum": lum, "teff": teff, "hz": bnds,
                     "cls": cls, "ly": round(1000.0 / plx * 3.26156, 2) if plx else fnum(val(s["distance_ly"]))}
    ruwe = fnum(g.get("ruwe"))
    ksrc = (f"RV: {rv_src}; PM: Gaia DR3" if rv is not None else "PM: Gaia DR3; no RV") + (
        f" | RUWE {ruwe:.2f} -- astrometry may be perturbed" if ruwe and ruwe > 1.4 else "")
    systems_rows.append({
        "A": h, "B": s.get("nickname") or "", "C": host_facts[h]["ly"], "D": s.get("stars_in_system") or 1,
        "E": s.get("system_stars") or "", "F": 0, "G": host_facts[h]["mass"] or "", "H": cls, "I": sort_key(cls),
        "K": teff or "", "L": fnum(val(s["age_gyr"])) or "", "M": fnum(val(s["feh"])) if val(s["feh"]) is not None else "",
        "N": lum if lum is not None else "",
        "O": (f"{bnds[0]:.3f} - {bnds[3]:.3f}\n(conservative: {bnds[1]:.3f} - {bnds[2]:.3f})" if bnds else ""),
        "P": 0, "Q": "\u2014", "Z": "", "AA": "",
        "AB": rv if rv is not None else "", "AC": pmra if pmra is not None else "", "AD": pmdec if pmdec is not None else "",
        "AE": kin.get("mu") or "", "AF": kin.get("v") or "", "AG": kin.get("l") if kin.get("l") is not None else "",
        "AH": kin.get("b") if kin.get("b") is not None else "", "AI": kin.get("ml") if kin.get("ml") is not None else "",
        "AJ": kin.get("mb") if kin.get("mb") is not None else "", "AK": ksrc, "AL": ids.get(h, ""),
        "AM": h, "AN": cls, "AO": round(ra, 6) if ra is not None else "", "AP": round(dec, 6) if dec is not None else "",
        "_sources": s.get("sources"), "_agent": s["_agent"], "_lum_inferred": lum_inferred, "_fill_note": fill_note,
        "_companions": s.get("companions") or []})

# ---- 4. per-candidate row inputs ----------------------------------------------------------------
live_wb = gs.load_cached(gs.resolve_spreadsheet_id()) or gs.fetch_workbook(gs.resolve_spreadsheet_id())


def tab_rows(title):
    t = live_wb["tabs"][title]
    return t[0], t[1:]


host_hz = {}                          # planet-host star -> (H, I, J, K, L) from existing rows
for title in ("Planets within 100 ly", "Unconfirmed within 100 ly"):
    H, rows = tab_rows(title)
    ix = {h: i for i, h in enumerate(H)}
    for r in rows:
        g = lambda n: r[ix[n]] if ix[n] < len(r) else ""  # noqa: E731
        star = g("Planet-host star") or g("Host system (primary star)")
        vals = [fnum(g(n)) for n in ("Host luminosity (L-sun)", "HZ inner, optimistic (au)", "HZ inner, conservative (au)",
                                     "HZ outer, conservative (au)", "HZ outer, optimistic (au)")]
        if star and vals[0] is not None and star not in host_hz:
            host_hz[star] = vals


def host_mass(c):
    star, sysh = c["planet_host_star"], c["system_host"]
    if star in multistars and fnum(multistars[star].get("Mass (M-sun)")):
        return fnum(multistars[star]["Mass (M-sun)"]), "Multi-stars tab"
    if sysh in systems and fnum(systems[sysh]["host_mass_msun"]) and star == sysh:
        return fnum(systems[sysh]["host_mass_msun"]), "Systems tab"
    if sysh in host_facts and host_facts[sysh]["mass"]:
        return host_facts[sysh]["mass"], "research record (new Systems row)"
    m = fnum(val((c.get("host_inputs") or {}).get("mass_msun")))
    return (m, "research record host_inputs") if m else (None, "")


def as_earth(m):
    if not isinstance(m, dict) or val(m) is None:
        return None, None
    v, unit = float(val(m)), (m.get("unit") or "")
    if "jup" in unit.lower():
        return v * M_JUP_E, f"Published as {v} M-Jup; stored in M-earth as {v} x 317.828 (Planets C543)."
    if "sun" in unit.lower():
        return v * M_SUN_E, f"Published as {v} M-sun; stored in M-earth as {v} x 332946."
    return v, None


plan_rows = []
for c in cands:
    row, onotes, nnotes = {}, {}, {}
    row["A"], row["B"] = c["planet"], c["system_host"]
    row["E"] = c["planet_host_star"] if c["planet_host_star"] != c["system_host"] else ""
    star = c["planet_host_star"]
    hv = host_hz.get(star)
    if hv is None and c["system_host"] in host_facts:
        f = host_facts[c["system_host"]]
        hv = [f["lum"]] + (list(f["hz"]) if f["hz"] else [None] * 4)
    if hv is None:
        hi = c.get("host_inputs") or {}
        lum, teff = fnum(val(hi.get("luminosity_lsun"))), fnum(val(hi.get("teff_k")))
        b = hz.bounds(lum, teff) if (teff and lum) else None
        hv = [lum] + (list(b) if b else [None] * 4)
    for col, v in zip("HIJKL", hv):
        row[col] = v if v is not None else ""
    m, mnote = as_earth(c.get("mass_earth"))
    row["O"] = m if m is not None else ""
    if mnote:
        nnotes["O"] = mnote
    row["Q"] = (c.get("mass_earth") or {}).get("type") if isinstance(c.get("mass_earth"), dict) else ""
    r_e = val(c.get("radius_earth"))
    row["T"] = ("=RADIUS/" + str(r_e)) if r_e else ""          # resolved to a formula at write time
    row["_radius_e"] = r_e
    p, a = val(c.get("period_d")), val(c.get("a_au"))
    row["V"] = p if p is not None else ""
    if a is None and p:
        mh, msrc = host_mass(c)
        if mh:
            a = (mh * (p / 365.25) ** 2) ** (1 / 3)
            onotes["W"] = (f"INFERRED: Kepler's third law, a = (M P^2)^(1/3) with M = {mh} M-sun ({msrc}) and "
                           f"P = {p} d; the planet's own mass is neglected.")
            a = round(a, 5)
    row["W"] = a if a is not None else ""
    row["Z"] = val(c.get("ecc")) if val(c.get("ecc")) is not None else ""
    flags = (c.get("orbit_flags") or "").strip()
    row["AI"] = f"{flags} TIER: {c.get('tier_reason', '').strip()}".strip()
    row["AJ"], row["AK"], row["AL"] = c["tier"], c.get("designation") or "", c.get("tfopwg_disposition") or ""
    row["AM"], row["AN"] = c.get("reference") or "", c.get("vetting_date") or ""
    row["AO"] = val(c.get("catalogue_distance_ly")) or ""
    row["AP"] = c.get("detection_method") or ""
    if c["tier"] == "unlikely":
        row["AQ"] = c.get("tier_reason") or ""
    row["_tab"] = "Rejected candidates" if c["tier"] == "unlikely" else "Unconfirmed within 100 ly"
    row["_orange"], row["_notes"], row["_agent"] = onotes, nnotes, c["_agent"]
    row["_sources"] = c.get("sources") or {}
    plan_rows.append(row)

plan = {"rename": RENAME, "dropped": dropped, "systems_rows": systems_rows, "rows": plan_rows,
        "need_rows_without_record": missing_record,
        "housekeeping": {
            "rehost": RENAME,
            "delete_duplicates": {"TOI-7032.01": "GJ 523 b (Planets)", "TOI-6716.01": "TOI-6716 b (Planets)"},
            "move_to_planets": {"TOI-2540.01": "TOI-2540 b", "TOI-5961.01": "TOI-5961 b", "TOI-6662.01": "TOI-6662 b"}}}
(HERE / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False, default=str), encoding="utf-8")

import collections  # noqa: E402
print("candidates to write:", len(plan_rows), collections.Counter(r["_tab"] for r in plan_rows),
      collections.Counter(r["AJ"] for r in plan_rows))
print("dropped:", dropped)
print("renames:", RENAME)
print("new Systems rows:", len(systems_rows), "| live hosts lacking a record:", missing_record)
print("rows with inferred a:", sum(1 for r in plan_rows if "W" in r["_orange"]),
      "| mass conversions:", sum(1 for r in plan_rows if "O" in r["_notes"]),
      "| no luminosity:", sum(1 for r in plan_rows if r["H"] == ""),
      "| Systems rows lum from R^2T^4:", sum(1 for s in systems_rows if s["_lum_inferred"]))
