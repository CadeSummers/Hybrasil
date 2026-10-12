# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rebuild STAR_SYSTEM_SOURCES.md: the project's sources, aggregated from what the workbook and the repo cite.

    python data/sources/build_sources_md.py

Reads every text cell and cell note of the newest snapshot in data/ (a full openpyxl load, ~1 min: read-only mode
drops notes) and the repo's code and docs, then writes STAR_SYSTEM_SOURCES.md at the repo root:

- Most Used Sources: the ten institutions in INSTITUTIONS with the most mentions -- the number of cells, notes and
  repo files that match the institution's pattern. A rough measure of use, not of importance. Publication venues
  (arXiv, journals) are not institutions here: they are how papers are reached, not where data comes from.
- Other Sources Used: the institutions that did not make the ten, OTHER_SERVICES, and every paper cited by author
  and year, alphabetical, with the journal or arXiv reference where the text writes one straight after the citation.

The literature list is extracted, not curated. It reads "A et al. 2019", "A & B 2019", "A, B & C 2019" (as
A et al.), "Gaia Collaboration, A et al. 2023", and a single author when a journal reference follows; it folds
accents and German umlaut spellings, merges entries that share a journal reference, and drops the tail of a
hyphenated surname broken across a line. Check new output by eye before committing it.
"""
import collections
import datetime
import re
import unicodedata
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SNAP = sorted(ROOT.glob("data/hybrasil-*.xlsx"))[-1]
OUT = ROOT / "STAR_SYSTEM_SOURCES.md"
REPO_TEXT = ("hybrasil/**/*.py", "hybrasil/**/*.js", "docs/**/*.md", "data/**/*.py", "data/**/*.md",
             "README.md", "CLAUDE.md", "schemas/*")

# (institution, pattern, what we use, key reference). The ten with the most mentions are Most Used Sources.
INSTITUTIONS = [
    ("European Space Agency (ESA)", r"\bGaia\b|Hipparcos|\bHIP\b ?\d|FLAME|GSP-Phot",
     "Gaia DR3 / EDR3 / DR2: positions, parallaxes and distances, proper motions, radial velocities, FLAME masses "
     "and luminosities, GSP-Phot temperatures, non-single-star orbits, RUWE. Hipparcos: HIP identifiers and the "
     "older astrometric baseline behind proper-motion anomalies.",
     "Gaia Collaboration, Vallenari et al. 2023, A&A 674, A1; Gaia Collaboration, Creevey et al. 2023, A&A 674, A26; "
     "Gaia Collaboration, Arenou et al. 2023, A&A 674, A34; van Leeuwen 2007, A&A 474, 653"),
    ("Centre de Données astronomiques de Strasbourg (CDS), Université de Strasbourg",
     r"SIMBAD|VizieR|J/A\+A|J/AJ|J/ApJ|J/MNRAS",
     "SIMBAD for spectral types, identifiers and cross-matches; VizieR for published catalogue tables "
     "(e.g. Kervella et al. 2022, Cifuentes et al. 2020, Tokovinin 2018).",
     "Wenger et al. 2000, A&AS 143, 9; Ochsenbein et al. 2000, A&AS 143, 23"),
    ("NSF NOIRLab / Cerro Tololo Inter-American Observatory", r"\bMSC\b|Multiple Star Catalog|Tokovinin",
     "Andrei Tokovinin's Multiple Star Catalog (MSC): stellar hierarchies, companions and star counts, including "
     "the Planetless 4+ Stars systems.",
     "Tokovinin 2018, ApJS 235, 6"),
    ("NASA TESS mission (MIT)", r"\bTESS\b|\bTOI\b|\bTIC\b",
     "TESS Objects of Interest (TOI) for planet candidates; TESS Input Catalog v8.2 for stellar masses, "
     "temperatures and radii.",
     "Ricker et al. 2015, JATIS 1, 014003; Stassun et al. 2019, AJ 158, 138; Guerrero et al. 2021, ApJS 254, 39"),
    ("U.S. Naval Observatory", r"\bWDS\b|Washington Double|ORB6|Sixth Catalog|USNO",
     "Washington Double Star Catalog (WDS) separations and position angles; Sixth Catalog of Orbits of Visual "
     "Binary Stars (ORB6).",
     "Mason et al. 2001, AJ 122, 3466"),
    ("NASA Exoplanet Science Institute (Caltech/IPAC)", r"Exoplanet Archive|pscomppars|\bst_lum\b|ExoFOP|NASA ?EA\b",
     "NASA Exoplanet Archive (Planetary Systems Composite Parameters: confirmed planets, host luminosities); "
     "ExoFOP follow-up records for TESS candidates.",
     "Akeson et al. 2013, PASP 125, 989"),
    ("University of Rochester / NASA JPL (E. Mamajek)", r"Pecaut|Mamajek",
     "The Pecaut & Mamajek mean dwarf colour-temperature sequence: spectral type to temperature, luminosity and "
     "mass where a star has no direct measurement.",
     "Pecaut & Mamajek 2013, ApJS 208, 9"),
    ("University of Toronto", r"\bOEC\b|Open Exoplanet",
     "Open Exoplanet Catalogue (OEC): the independent cross-check on every planet mass.",
     "Rein 2012, arXiv:1211.7121"),
    ("Pennsylvania State University", r"Kopparapu",
     "Kopparapu et al. habitable-zone limits (the HZ columns) and the runaway-greenhouse ratio behind each "
     "star's colour factor in the solvent bands.",
     "Kopparapu et al. 2013, ApJ 765, 131"),
    ("University of Massachusetts / IPAC", r"2MASS",
     "Two Micron All Sky Survey (2MASS) JHK photometry, the K-band input to M-dwarf mass relations.",
     "Skrutskie et al. 2006, AJ 131, 1163"),
    ("Paris Observatory", r"exoplanet\.eu|Exoplanet Encyclop",
     "The Extrasolar Planets Encyclopaedia (exoplanet.eu).", ""),
    ("European Southern Observatory", r"HARPS|ESPRESSO|SPHERE|\bESO\b",
     "HARPS, ESPRESSO and SPHERE, through the papers that use them.", ""),
]
OTHER_SERVICES = [
    "arXiv (Cornell University): preprints of most of the papers below",
    "NASA Astrophysics Data System (ADS): bibliographic look-ups",
    "Calar Alto Observatory: CARMENES radial velocities and stellar parameters, through their papers",
    "W. M. Keck Observatory: HIRES radial velocities, through their papers",
    "Hipparcos-Gaia Catalog of Accelerations (Brandt 2021) and Kervella et al. proper-motion anomalies",
    "Ninth Catalogue of Spectroscopic Binary Orbits (SB9), Université Libre de Bruxelles (Pourbaix et al. 2004)",
    "Fifth Catalogue of Nearby Stars (CNS5), Astronomisches Rechen-Institut, Heidelberg (Golovin et al. 2023)",
    "Gaia white dwarf catalogue (Gentile Fusillo et al. 2021)",
    "NASA Kepler mission, through its planet papers",
    "Pan-STARRS1 and WISE imaging, for companion checks",
    "JWST and Hubble Space Telescope, through their papers",
    "NASA JPL Horizons: live osculating elements for the Solar System (--source horizons)",
    "NASA Scientific Visualization Studio: Deep Star Maps 2020, the background Milky Way",
    "IAU Working Group on Star Names: proper names",
    "Wikipedia: a handful of values, each marked with a pink border on the workbook",
]

# ── citations ──────────────────────────────────────────────────────────────────────────────────────
L = r"[^\W\d_]"
NAME = rf"(?:(?:van|de|da|von|del|Van|De|Del|Di) )?{L}[\w'\-]+(?: {L}[\w'\-]+)?"
JOUR = (r"(?:A&AS|A&A|AJ|ApJS|ApJL|ApJ|MNRAS|PASP|PASJ|PSJ|Nature Astronomy|Nature|Science|AN|RNAAS|Icarus|"
        r"Acta Astron\.?|NewA|ARA&A|JAAVSO|JATIS|Ap&SS|AstL|Astron\. Lett\.|ESA SP)\s*\d+,?\s*[A-Z]?\d+")
REF = re.compile(rf"^[,:;]?\s*\(?\s*(?:{JOUR}|arXiv[: ]\d{{4}}\.\d{{4,5}})")
MULTI = re.compile(rf"\b({NAME}) (et al\.?|& {L}[\w'\-]+),? \(?((?:19|20)\d\d)([a-z]?)\b")
SINGLE = re.compile(rf"\b({L}[\w'\-]+) \(?((?:19|20)\d\d)([a-z]?)\)?(?=[,:;]?\s*\(?\s*(?:{JOUR}|arXiv[: ]\d{{4}}\.\d))")
LIST3 = re.compile(rf"(?<![\w.])(?!Collaboration)([A-Z][a-z][\w'\-]*), (?:{L}[\w'\-]+, )*{L}[\w'\-]+ (?:&|and) "
                   rf"{L}[\w'\-]+,? \(?((?:19|20)\d\d)([a-z]?)\b")
GAIA = re.compile(r"Gaia Collaboration(?:,? \(?([A-Z][\w'\-]+) et al\.?)?,? \(?((?:19|20)\d\d)\b")
# the match is only the end of a longer author list ("Sperauskas, Deveikis & Tokovinin 2019")
TAIL_OF_LIST = re.compile(r"(?:(?<![\w.])(?!(?:Collaboration|Sources|Source|Planets|Kinematics|Class|Mass|Teff|See"
                          r"|Also|Note)\b)[A-Z][a-z][\w'\-]*,|&|\band)\s*$")
STOP = set("RV PM Teff Mass Class SIMBAD See and from via per by in of the The with on ON as As At at Now Was was L M R "
           "K Kmag mass class spec sp Gaia MSC WDS TIC ORB6 SB9 HGCA NASA OEC Table Fig Sect FLAME also Also cf Cf "
           "after After than see like Like Re-implement Replaces Using Following Unlike However Per Both Only From "
           "Source SOURCE Sources Catalog Catalogue Release Data Note NOTE INFERRED METHOD VALID SCATTER CHECK".split())


def fold(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()
    return s.replace("oe", "o").replace("ue", "u").replace("ae", "a")       # Schoenrich = Schönrich


def clean(a):
    parts = a.split()
    while len(parts) > 1 and (parts[0] in STOP or (parts[0].isupper() and len(parts[0]) <= 4)):
        parts = parts[1:]
    if parts[0] in STOP or not parts[0][0].isupper() or parts[0].isupper() and len(parts[0]) <= 3:
        return None
    return " ".join(p.title() if p.isupper() and len(p) > 2 else p for p in parts)


def texts():
    """Every text blob: workbook cells (not formulas) and notes, then repo files."""
    wb = openpyxl.load_workbook(SNAP)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and not c.value.startswith("=") and len(c.value) > 3:
                    yield c.value
                if c.comment:
                    yield c.comment.text
    for pat in REPO_TEXT:
        for p in ROOT.glob(pat):
            if p.is_file() and p != OUT and HERE not in p.resolve().parents:     # not this script's own patterns
                yield p.read_text(encoding="utf-8", errors="ignore")


def literature(blobs):
    cit = collections.defaultdict(lambda: {"refs": collections.Counter(), "co": collections.Counter(),
                                           "names": collections.Counter()})

    def ref_of(c, tail):
        m = REF.match(tail)
        if m:
            r = re.sub(r"^[,:;(\s]+", "", m.group(0))
            c["refs"][re.sub(r"\s+", " ", r).replace("arXiv ", "arXiv:")] += 1

    def add(name, co, year, tail):
        name = clean(name)
        if name:
            c = cit[(fold(name), year)]
            c["co"][co] += 1
            c["names"][name] += 1
            ref_of(c, tail)

    for text in blobs:
        for m in MULTI.finditer(text):
            if TAIL_OF_LIST.search(text[max(0, m.start() - 30):m.start()]):
                continue
            conj = m.group(2)
            co = "et al." if conj.startswith("et") else "& " + (conj[2:].title() if conj[2:].isupper() else conj[2:])
            add(m.group(1), co, m.group(3) + m.group(4), text[m.end():m.end() + 60])
        for m in GAIA.finditer(text):
            c = cit[(fold("gaia collaboration " + (m.group(1) or "")), m.group(2))]
            c["co"][""] += 1
            c["names"][f"Gaia Collaboration, {m.group(1)} et al." if m.group(1) else "Gaia Collaboration"] += 1
            ref_of(c, text[m.end():m.end() + 60])
        for m in LIST3.finditer(text):
            add(m.group(1), "et al.", m.group(2) + m.group(3), text[m.end():m.end() + 60])
        for m in SINGLE.finditer(text):
            if m.group(1) != "Collaboration" and not TAIL_OF_LIST.search(text[max(0, m.start() - 30):m.start()]):
                add(m.group(1), "", m.group(2) + m.group(3), text[m.end():m.end() + 60])

    entries = []
    for (key, year), c in cit.items():
        name = max(c["names"], key=lambda n: (c["names"][n], any(ord(ch) > 127 for ch in n)))
        co = c["co"].most_common(1)[0][0]
        ref = c["refs"].most_common(1)[0][0] if c["refs"] else ""
        entries.append((key, year, ref, f"{name}{(' ' + co) if co else ''} {year}" + (f", {ref}" if ref else "")))
    # a hyphenated surname broken across a line (Hardegree- / Ullman) also reads as "Ullman": drop the fragment
    whole = {(k, y) for k, y, *_ in entries}
    entries = [e for e in entries if not any(k.endswith("-" + e[0]) and y == e[1] for k, y in whole)]
    # one paper cited two ways shares its journal reference: keep the fullest author form
    best = {}
    for e in entries:
        if e[2] and (e[2] not in best or len(e[3]) > len(best[e[2]][3])):
            best[e[2]] = e
    entries = [e for e in entries if not e[2] or best[e[2]] is e]
    return sorted(entries)


def main():
    blobs = list(texts())
    counts = {name: sum(1 for b in blobs if re.search(pat, b)) for name, pat, *_ in INSTITUTIONS}
    ranked = sorted(INSTITUTIONS, key=lambda i: -counts[i[0]])
    top, rest = ranked[:10], ranked[10:]
    entries = literature(blobs)

    lines = [
        "# Star System Sources",
        "",
        "An aggregated list of the sources behind the hybrasil workbook and code. It is for keeping track, not "
        "for citing values: every value's own source is on its cell, in its note, or in the workbook's Sources & "
        "Provenance tab.",
        "",
        f"Compiled {datetime.date.today().day} {datetime.date.today():%B %Y} from the workbook snapshot `data/{SNAP.name}` (every cell and "
        "cell note on all tabs) and the repository's code and documentation, by `data/sources/build_sources_md.py`.",
        "",
        "## Most Used Sources",
        "",
        "The ten institutions whose data the project draws on most, ranked by how many workbook cells, cell notes "
        "and repository files name one of their catalogues, missions or services. The count is a rough measure of "
        "how often the source is used, not how important it is. Publication venues (arXiv, journals) are left out, "
        "because they are how papers are reached, not where the data comes from.",
        "",
        "| # | Institution | What we use | Key reference | Mentions |",
        "|---|---|---|---|---|",
    ]
    for i, (inst, _, what, ref) in enumerate(top, 1):
        lines.append(f"| {i} | {inst} | {what} | {ref} | {counts[inst]:,} |")
    lines += ["", "## Other Sources Used", "", "In no particular order.", "",
              "### Catalogues, archives and services", ""]
    lines += [f"- {inst}: {what}" for inst, _, what, _ in rest]
    lines += [f"- {s}" for s in OTHER_SERVICES]
    lines += ["", "### Literature", "",
              f"{len(entries)} papers and catalogues cited by author and year. They are listed alphabetically so an "
              "entry is easy to find; the order says nothing about weight. A journal or arXiv reference is "
              "given where the workbook writes one next to the citation.", ""]
    letter = None
    for key, _, _, text in entries:
        if key[0].upper() != letter:
            letter = key[0].upper()
            lines += ["", f"**{letter}**", ""]
        lines.append(f"- {text}")
    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{SNAP.name}: {len(blobs)} texts; top ten "
          + ", ".join(f"{i[0].split(' (')[0]} {counts[i[0]]}" for i in top))
    print(f"{len(entries)} literature entries, {sum(1 for e in entries if e[2])} with a reference -> {OUT.name}")


if __name__ == "__main__":
    main()
