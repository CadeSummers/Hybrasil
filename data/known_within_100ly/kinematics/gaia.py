# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""P1: Gaia DR3 gaia_source for every target row with a Gaia DR3 source_id.

    python gaia.py      fetch in chunks of 1,000 ids into cat/gaia_NNN.json; a chunk already on disk is skipped,
                        so an interrupted run resumes where it stopped

Columns: astrometry (pm, parallax, errors, RUWE, astrometric_params_solved), radial velocity with its error and
the RVS magnitude it was measured at, and G for ordering the residual. The ESA archive is the one
data/four_plus_stars/kinematics.py uses.
"""
import json
import urllib.parse
import urllib.request

from common import CAT, TARGETS, load, mark, save

GAIA = "https://gea.esac.esa.int/tap-server/tap/sync"
CHUNK = 1000
COLS = ("source_id, ra, dec, parallax, parallax_error, pmra, pmra_error, pmdec, pmdec_error, radial_velocity, "
        "radial_velocity_error, rv_nb_transits, grvs_mag, rv_template_teff, ruwe, astrometric_params_solved, "
        "phot_g_mean_mag")


def tap(query):
    body = urllib.parse.urlencode({"request": "doQuery", "lang": "adql", "format": "json", "query": query}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request(GAIA, data=body), timeout=900))
    cols = [c["name"] for c in r["metadata"]]
    return [dict(zip(cols, row)) for row in r["data"]]


def main():
    ids = sorted({t["gaia"] for t in load(TARGETS)["rows"] if t["blank"] and t["gaia"]})
    CAT.mkdir(exist_ok=True)
    chunks = [ids[i:i + CHUNK] for i in range(0, len(ids), CHUNK)]
    mark("P1_gaia", "running", ids=len(ids), chunks=len(chunks))
    for n, chunk in enumerate(chunks):
        f = CAT / f"gaia_{n:03d}.json"
        if f.exists() and len(json.loads(f.read_text())["ids"]) == len(chunk):
            continue
        rows = tap(f"SELECT {COLS} FROM gaiadr3.gaia_source WHERE source_id IN ({','.join(chunk)})")
        save(f, {"ids": chunk, "rows": rows})
        print(f"chunk {n + 1}/{len(chunks)}: {len(rows)} of {len(chunk)} found", flush=True)
    got = {}
    for n in range(len(chunks)):
        for r in json.loads((CAT / f"gaia_{n:03d}.json").read_text())["rows"]:
            got[str(r["source_id"])] = r
    missing = [i for i in ids if i not in got]
    mark("P1_gaia", "done", ids=len(ids), found=len(got), missing=missing,
         with_pm=sum(1 for r in got.values() if r["pmra"] is not None),
         with_rv=sum(1 for r in got.values() if r["radial_velocity"] is not None))
    print(f"{len(got)}/{len(ids)} found; pm {sum(1 for r in got.values() if r['pmra'] is not None)}; "
          f"rv {sum(1 for r in got.values() if r['radial_velocity'] is not None)}; missing {len(missing)}")


if __name__ == "__main__":
    main()
