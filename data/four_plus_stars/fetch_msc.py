# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pull the Multiple Star Catalog (Tokovinin 2018, ApJS 235, 6; VizieR J/ApJS/235/6, Dec 2023 update) records
for every system with 4+ components within 100 ly, plus nu Sco, which the owner asked for by name.

    python fetch_msc.py      writes msc.json: {WDS id: {"catalog": [...], "systems": [...], "orbits": [...]}}
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLX_100LY = 32.6156            # mas: 3261.56 / 100
ALSO = ["nu_Sco"]              # asked for by name, whatever the distance


def tap(q):
    url = "https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync?" + urllib.parse.urlencode(
        {"request": "doQuery", "lang": "adql", "format": "json", "query": q})
    r = json.load(urllib.request.urlopen(url, timeout=300))
    cols = [c["name"] for c in r["metadata"]]
    return [{k: (v.strip() if isinstance(v, str) else v) for k, v in zip(cols, row)} for row in r["data"]]


def main():
    rows = tap(f'SELECT ID FROM "J/ApJS/235/6/catalog" WHERE plx >= {PLX_100LY} AND Nc >= 4')
    ids = {r["ID"] for r in rows}
    for name in ALSO:
        hit = tap(f"SELECT ID FROM \"J/ApJS/235/6/catalog\" WHERE OID LIKE '%*{name}%' OR OID LIKE '%*14{name}%'")
        print(name, "->", [h["ID"] for h in hit])
        ids |= {h["ID"] for h in hit}
    out = {}
    idl = sorted(ids)
    for i in range(0, len(idl), 40):
        inl = ",".join(f"'{x}'" for x in idl[i:i + 40])
        for table in ("catalog", "systems", "orbits"):
            for r in tap(f'SELECT * FROM "J/ApJS/235/6/{table}" WHERE ID IN ({inl})'):
                out.setdefault(r["ID"], {"catalog": [], "systems": [], "orbits": []})[table].append(r)
    (HERE / "msc.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(len(out), "systems;", sum(len(v["systems"]) for v in out.values()), "subsystem records;",
          sum(len(v["orbits"]) for v in out.values()), "orbits")


if __name__ == "__main__":
    main()
