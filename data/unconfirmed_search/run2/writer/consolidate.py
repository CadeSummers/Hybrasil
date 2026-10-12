# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Merge every agent's OUT/*.json into one reviewed candidate list.

Read-only: writes merged.json and review.txt next to this file, nothing else.
"""
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK, OUT = HERE / "pack", HERE / "out"


def key(name: str) -> str:
    s = (name or "").lower().replace("gliese", "gj").replace("gl ", "gj ")
    return re.sub(r"[\s_\-.]+", "", s)


def load_csv(name):
    with open(PACK / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


on_sheet = {}
for fn, where in (("planets_confirmed.csv", "Planets"), ("unconfirmed_existing.csv", "Unconfirmed"),
                  ("rejected_candidates.csv", "Rejected")):
    for r in load_csv(fn):
        on_sheet[key(r["planet"])] = (where, r["sheet_row"], r["planet"])
systems = {r["system_host"] for r in load_csv("systems.csv")}

# Same host, period within 2%: the same signal under another name.
by_host = {}
for fn, where in (("planets_confirmed.csv", "Planets"), ("unconfirmed_existing.csv", "Unconfirmed")):
    for r in load_csv(fn):
        try:
            per = float(r["period_d"])
        except (TypeError, ValueError):
            continue
        for h in {r["system_host"], r.get("planet_host_star") or ""} - {""}:
            by_host.setdefault(key(h), []).append((where, r["sheet_row"], r["planet"], per))
rej_by_host = {}
for r in load_csv("rejected_candidates.csv"):
    m = re.search(r"P\s*=\s*([\d.]+)", r["planet"])
    rej_by_host.setdefault(key(r["system_host"]), []).append(("Rejected", r["sheet_row"], r["planet"], float(m.group(1)) if m else None))

files = sorted(p for p in OUT.glob("*.json"))
problems, cands, new_systems, missing_conf = [], [], [], []
for p in files:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:           # noqa: BLE001
        problems.append(f"{p.name}: invalid JSON ({e})")
        continue
    for c in d.get("candidates", []):
        c["_agent"] = p.stem
        cands.append(c)
    for s in d.get("new_systems", []):
        s["_agent"] = p.stem
        new_systems.append(s)
    for m in d.get("confirmed_missing_from_confirmed_sheet", []):
        missing_conf.append((p.stem, m))

REQ = ("planet", "system_host", "tier", "detection_method", "reference", "sources")
seen = {}
for c in cands:
    for f in REQ:
        if not c.get(f):
            problems.append(f"{c['_agent']} {c.get('planet')}: missing {f}")
    if c.get("tier") not in ("strong", "ambiguous", "unlikely"):
        problems.append(f"{c['_agent']} {c.get('planet')}: bad tier {c.get('tier')!r}")
    names = [c.get("planet", "")] + list(c.get("aliases") or [])
    hits = [on_sheet[key(n)] for n in names if key(n) in on_sheet]
    per = c.get("period_d") if isinstance(c.get("period_d"), dict) else None
    per = per.get("value") if per else None
    if isinstance(per, (int, float)) and per > 0:
        for h in {c.get("system_host", ""), c.get("planet_host_star") or ""} - {""}:
            for w, row, n, p2 in by_host.get(key(h), []) + rej_by_host.get(key(h), []):
                if p2 and abs(p2 - per) / per < 0.02 and (w, row, n) not in hits:
                    hits.append((w, row, n + f" [period {p2}]"))
    c["_on_sheet"] = hits
    c["_dup_of"] = None
    for n in names:
        k = key(n)
        if k in seen and seen[k] is not c:
            c["_dup_of"] = f"{seen[k]['_agent']}:{seen[k]['planet']}"
        seen.setdefault(k, c)
    host = c.get("system_host", "")
    c["_host_on_systems"] = host in systems or bool(c.get("new_system"))
    # Every numeric field must carry a source key that exists.
    for f in ("period_d", "a_au", "ecc", "mass_earth", "radius_earth"):
        v = c.get(f)
        if isinstance(v, dict) and v.get("src") and v["src"] not in (c.get("sources") or {}):
            problems.append(f"{c['_agent']} {c['planet']}: {f} cites missing source {v['src']}")

(HERE / "merged.json").write_text(json.dumps(
    {"candidates": cands, "new_systems": new_systems, "confirmed_missing": missing_conf,
     "problems": problems}, indent=1, ensure_ascii=False), encoding="utf-8")

lines = [f"files: {', '.join(p.stem for p in files)}",
         f"candidates: {len(cands)}  new_systems: {len(new_systems)}  problems: {len(problems)}", ""]
for c in sorted(cands, key=lambda c: (c["tier"], c["system_host"])):
    val = lambda f: (c.get(f) or {}).get("value") if isinstance(c.get(f), dict) else None  # noqa: E731
    flag = []
    if c["_on_sheet"]:
        flag.append("ON SHEET " + "; ".join(f"{w} r{r} {n}" for w, r, n in c["_on_sheet"]))
    if c["_dup_of"]:
        flag.append("DUP of " + c["_dup_of"])
    if not c["_host_on_systems"]:
        flag.append("HOST NOT ON SYSTEMS")
    unit = (c.get("mass_earth") or {}).get("unit") if isinstance(c.get("mass_earth"), dict) else None
    lines.append(f"{c['_agent']:4s} {c['tier']:9s} {c['planet'][:44]:44s} host={c['system_host'][:16]:16s} "
                 f"P={val('period_d')} a={val('a_au')} M={val('mass_earth')}{' '+unit if unit else ''} "
                 f"R={val('radius_earth')}  {' | '.join(flag)}")
lines += ["", "PROBLEMS:"] + problems + ["", "CONFIRMED MISSING:"] + [f"{a}: {m}" for a, m in missing_conf]
(HERE / "review.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines[:3]))
