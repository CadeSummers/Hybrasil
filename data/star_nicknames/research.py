# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Common names for every star on the Systems, Multi-stars and Planetless 4+ Stars tabs.

    python research.py CACHE_DIR        writes nicknames.json and collisions.md beside this file

Reads the star lists from the live sheet and writes nothing to it. Three sources, in order:

1. the IAU Catalog of Star Names (IAU-CSN.txt, WGSN), matched by HIP / HD number, plus the
   NameExoWorlds 2022 names, which that file predates (``IAU_2022``);
2. SIMBAD's ``NAME`` identifiers and its Bayer / Flamsteed designations;
3. ``COMMON``, a hand-checked list of names in common use that SIMBAD does not file as names.

CACHE_DIR holds the two downloads (IAU-CSN.txt and simbad_near.tsv, every SIMBAD object with a
parallax over 30 mas and its identifiers) and what SIMBAD returns for the stars not among them.
"""
import collections
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hybrasil.data import google_sheets as gs  # noqa: E402

HERE = Path(__file__).parent
SIMBAD = "https://simbad.harvard.edu/simbad/"
IAU_CSN = "https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt"
TABS = {"S": ("Systems within 100 ly", None), "M": ("Multi-stars within 100 ly", "Star (component)"),
        "P": ("Planetless 4+ Stars", "Star (component)")}

# NameExoWorlds 2022 (approved June 2023): later than the IAU-CSN file used here.
IAU_2022 = {"GJ 1214": "Orkaria", "GJ 367": "Añañuca", "GJ 436": "Noquisi", "GJ 486": "Gar",
            "GJ 3470": "Kaewkosin", "LHS 3844": "Batsũ̀", "WD 0806-661": "Maru"}
ASCII = {"Añañuca": "Ananuca", "Batsũ̀": "Batsu", "Citalá": "Citala"}      # as typed without diacritics

# Names in common use that SIMBAD does not file as names. Each was checked against the star's
# SIMBAD identifiers (the catalogue number behind the name is among them).
COMMON = {
    "GJ 411": ["Lalande 21185"],
    "GJ 15 A": ["Groombridge 34", "Groombridge 34 A"],
    "GJ 15 B": ["Groombridge 34 B"],
    "GJ 729": ["Ross 154"],
    "GJ 65": ["Luyten 726-8"],
    "GJ 65 A": ["Luyten 726-8 A", "BL Ceti"],
    "GJ 65 B": ["Luyten 726-8 B", "UV Ceti"],
    "Gl 725 A": ["Struve 2398", "Struve 2398 A"],
    "Gl 725 B": ["Struve 2398 B"],
    "Kapteyn": ["Kapteyn's Star"],
    "Wolf 359": ["CN Leonis"],
    "GJ 876": ["Ross 780"],
    "61 Cyg A": ["Bessel's Star"],
    "Ross 128": ["FI Virginis"],
    "Ross 458": ["DT Virginis"],
    "HD 20794": ["82 G. Eridani", "e Eridani"],
    "alf Cen A": ["Alpha Centauri", "Alpha Centauri A"],
    "alf Cen B": ["Alpha Centauri B"],
    "Proxima Cen": ["Alpha Centauri C"],
}

# SIMBAD NAME identifiers that are not names of the star: a planet's name, a catalogue number,
# or a second spelling of a name already taken.
DROP = re.compile(r"^(HD|BD|CD|G|GJ|LTT|PM|SO|APM|V\d+|KOBE|COCONUTS|TOI|vMA)[ \-+\d]|"
                  r"[\d ][b-h]$| AB$| BC$|^(Kapteyn's|Kapteyn Star|van Maanen Star|Barnard Star)$")
COMPONENT = re.compile(r" ([A-D])[a-c]?\d?$")


def key(name: str, fold: bool = False) -> str:
    """A name as SIMBAD and the workbook both spell it: no catalogue prefix, spacing or dots."""
    s = re.sub(r"^(NAME|\*\*?|V\*)\s+", "", name.strip())
    s = re.sub(r"^(Gliese|Gl)\b\.?\s*", "GJ ", s)
    s = re.sub(r"\b([a-z]{1,3})\.", r"\1", s)                     # "mu." -> "mu"
    s = re.sub(r"\b([a-z]{1,3})0(\d)\b", r"\1\2", s)              # "zet01" -> "zet1"
    s = re.sub(r"[\s_]+", "", s)
    return s.lower() if fold else s


def bare(name: str) -> str:
    """A name without its component letter: "tau Boo A" adds nothing to "tau Boo"."""
    return key(COMPONENT.sub("", name) if COMPONENT.search(name) and " " in name.strip() else name, True)


def fetch(url: str, data: dict | None = None) -> str:
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read().decode("utf-8", "replace")


def simbad_near(cache: Path) -> list[list[str]]:
    f = cache / "simbad_near.tsv"
    if not f.exists():
        f.write_text(fetch(SIMBAD + "sim-tap/sync", {
            "request": "doQuery", "lang": "adql", "format": "tsv", "maxrec": 200000,
            "query": "SELECT b.main_id, b.plx_value, b.otype, ids.ids FROM basic AS b "
                     "JOIN ids ON ids.oidref = b.oid WHERE b.plx_value > 30"}), encoding="utf-8")
    rows = list(csv.reader(f.open(encoding="utf-8"), delimiter="\t"))[1:]
    return [r[3].split("|") for r in rows if len(r) >= 4]


def simbad_spelling(name: str) -> str:
    s = re.sub(r"^(Gliese|Gl)\b\.?\s*", "GJ ", name)
    return "Kapteyn's star" if s == "Kapteyn" else s


def simbad_by_name(cache: Path, names: list[str]) -> dict[str, list[str]]:
    """SIMBAD's identifiers for each name it knows, asked for eighty to a script."""
    f = cache / "simbad_named.json"
    have = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    todo = [n for n in names if n not in have]
    for i in range(0, len(todo), 80):
        chunk = todo[i:i + 80]
        script = 'output console=off script=off\nformat object "@@%IDLIST[%*|]"\n' + "".join(
            f"echodata ##{n}\nquery id {simbad_spelling(n)}\n" for n in chunk)
        current = None
        for line in fetch(SIMBAD + "sim-script", {"script": script}).splitlines():
            if line.startswith("##"):
                current = line[2:].strip()
                have.setdefault(current, [])
            elif line.startswith("@@") and current:
                have[current] = [x.strip() for x in line[2:].split("|") if x.strip()]
        for n in chunk:
            have.setdefault(n, [])
        f.write_text(json.dumps(have, ensure_ascii=False, indent=0), encoding="utf-8")
    return {n: have[n] for n in names}


def iau_names(cache: Path) -> list[dict]:
    f = cache / "IAU-CSN.txt"
    if not f.exists():
        f.write_text(fetch(IAU_CSN), encoding="utf-8")
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line[0] in "#$":
            continue
        t = line[49:].split()
        d = next((i for i, x in enumerate(t) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)), None)
        if d is None:
            continue
        out.append({"name": line[18:36].strip(), "designation": line[36:49].strip(),
                    "component": t[3].strip("_"), "hip": t[d - 4].strip("_"), "hd": t[d - 3].strip("_")})
    return out


def bayer(ids: list[str]) -> list[str]:
    """SIMBAD's Bayer and Flamsteed designations, spelt the workbook's way ("pi Men", "54 Psc")."""
    out = []
    for i in ids:
        m = re.fullmatch(r"\*\s+(\S+)\s+([A-Z][A-Za-z]{2})( [A-D])?", i)
        if m:
            g = re.sub(r"^([a-z]+)0(\d)$", r"\1\2", m.group(1).replace(".", ""))
            out.append(f"{g} {m.group(2)}{m.group(3) or ''}")
    return out


def main(cache: Path) -> None:
    grids = gs.read_cells(None, [f"'{t}'!A1:D" for t, _ in TABS.values()])
    stars = []                              # (tab, host, star, current nickname, first row of its system)
    for tab, (title, comp) in TABS.items():
        grid = next(v for k, v in grids.items() if title in k)
        head = [str(h).strip() for h in grid[0]]
        hi, ni = head.index("System / Host"), head.index("Nickname (IAU)")
        ci = head.index(comp) if comp else hi
        for r in grid[1:]:
            r = [str(c).strip() for c in list(r) + [""] * 4]
            if r[hi]:
                # The Planetless tab's first row of a system stands for the system as well as its star.
                stars.append((tab, r[hi], r[ci], r[ni], tab == "P" and r[2].lower().startswith("host")))

    objects = simbad_near(cache)
    index, folded = collections.defaultdict(set), collections.defaultdict(set)

    def file(n: int, names: list[str]) -> None:
        for i in names:
            index[key(i)].add(n)
            folded[key(i, True)].add(n)

    for n, ids in enumerate(objects):
        file(n, ids)

    def find(name: str) -> int | None:
        """The star's SIMBAD object. Case decides a component letter: "ups And b" is a planet."""
        tries = [index.get(key(name))]
        if not re.search(r"\d ?[A-Da-d]$| [A-Da-d][a-c]?\d?$", name):
            tries.append(folded.get(key(name, True)))
        if name.endswith(" A"):                       # a primary filed as "55 Cnc A" is SIMBAD's "55 Cnc"
            tries.append(index.get(key(name[:-2])))
        return next((next(iter(h)) for h in tries if h and len(h) == 1), None)

    asked = sorted({x for _, h, s, _, _ in stars for x in (h, s) if find(x) is None})
    asked += [x[:-2] for x in asked if x.endswith(" A")]
    for name, ids in simbad_by_name(cache, asked).items():
        # SIMBAD ignores case: asked for the star "gam Cep B" it answers with the planet "gam Cep b".
        if ids and (not COMPONENT.search(name) or key(name) in {key(i) for i in ids}):
            objects.append(ids)
            file(len(objects) - 1, ids + [name])

    iau_by, iau_all = {}, set(IAU_2022.values())
    for row in iau_names(cache):
        iau_all.add(row["name"])
        for k in (f"HIP {row['hip']}" if row["hip"] else "", f"HD {row['hd']}" if row["hd"] else "",
                  row["designation"]):
            if k and "999999" not in k:
                iau_by.setdefault(key(k), []).append(row)

    def names_of(ids: list[str], star: str, own_letter: bool) -> tuple[str, list[tuple[str, str]]]:
        letter = (COMPONENT.search(star) or [None, ""])[1]
        iau = IAU_2022.get(star, "")
        for row in {r["name"]: r for i in ids for r in iau_by.get(key(i), [])}.values():
            # A HD number is often the whole system's: take the name for the star it was given to.
            if not own_letter or not letter or row["component"][:1] in ("", letter):
                iau = iau or row["name"]
        found = [(iau, "IAU"), (ASCII.get(iau, ""), "IAU")]
        found += [(re.sub(r" star$", " Star", i[5:]), "SIMBAD") for i in ids
                  if i.startswith("NAME ") and not DROP.search(i[5:])]
        # A star the workbook already files by its Bayer letter gains nothing from its Flamsteed number.
        lettered = star[:1].islower()
        found += [(b, "SIMBAD") for b in bayer(ids)
                  if not (lettered and b[:1].isdigit()) and not b.startswith(("alf1 Cen", "alf2 Cen"))]
        return iau, [f for f in found if f[0]]

    result, unresolved = {}, []
    for tab, host, star, current, origin in stars:
        n = find(star)
        iau, found = names_of(objects[n], star, tab != "S") if n is not None else ("", [])
        if n is None and not origin:
            unresolved.append(f"{tab}: {star}")
        if origin:                                   # the system's names go on its first row
            hn = find(host)
            host_iau, host_found = names_of(objects[hn], host, False) if hn is not None else ("", [])
            iau, found = host_iau or iau, host_found + found
            if hn is None:
                unresolved.append(f"P host: {host}")
        if current and not iau and current in iau_all:
            iau = current
        found.insert(1, (current, "workbook"))
        found += [(x, "common usage") for x in COMMON.get(star, [])]
        names, sources = [], {}
        for name, source in found:
            if name and all(bare(name) != bare(x) for x in names + [star, host]):
                names.append(name)
                sources[name] = source
        if names or iau:
            result[f"{tab}|{host}|{star}"] = {"tab": tab, "host": host, "star": star, "current": current,
                                             "origin": origin, "iau": iau, "names": names, "sources": sources}
    # A component row does not repeat what its system's first row already says.
    first = {r["host"]: r for r in result.values() if r["origin"]}
    for r in result.values():
        if r["tab"] == "P" and not r["origin"] and r["host"] in first:
            r["names"] = [x for x in r["names"] if x not in first[r["host"]]["names"]]
            r["iau"] = "" if r["iau"] == first[r["host"]]["iau"] else r["iau"]
    result = {k: r for k, r in result.items() if r["names"] or r["iau"]}

    owners = collections.defaultdict(set)
    for _, host, star, _, _ in stars:                # a nickname can also be another system's own name
        owners[key(star, True)].add((host, star))
        owners[key(host, True)].add((host, host))
    for r in result.values():
        for name in r["names"]:
            owners[key(name, True)].add((r["host"], name))
    clashes = {k: sorted(v) for k, v in owners.items() if len({h for h, _ in v}) > 1}

    (HERE / "nicknames.json").write_text(json.dumps(
        {"stars": list(result.values()), "unresolved": unresolved}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    lines = ["# Nicknames shared by more than one system", "",
             "Written by `research.py`; not resolved here. A search for a shared name lists every system.", ""]
    lines += [f"- **{v[0][1]}**: " + ", ".join(sorted({h for h, _ in v})) for v in clashes.values()] or ["None."]
    (HERE / "collisions.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(len(stars), "rows;", len(result), "with a name;", len(unresolved), "not in SIMBAD;",
          len(clashes), "shared names")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
