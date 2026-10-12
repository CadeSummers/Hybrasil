# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Identifiers into links: the Sources section of a Nearby Stellar Motion info panel.

A star's sources come in two kinds, both read from the workbook (data/existence/ wrote the columns):

- **Existence**: a curated catalog that lists the object -- SIMBAD, CNS5, the Multiple Star Catalog, the NASA
  Exoplanet Archive -- and its Gaia DR3 row.  The `Existence` column says which; this module turns the identifiers
  into links.
- **Motion**: the references behind its radial velocity and proper motion, the `Kinematics refs` column:
  'RV: <refs>; PM: <refs>', each a catalog name, ADS bibcode, DOI, arXiv id or URL.

Pure: no I/O.  Every URL format lives here once; `LINK_TEMPLATES` is the same set handed to the three.js viewer for
the purple cloud, whose ten thousand panels are built in the browser rather than shipped.  Each pattern was opened and
found to return the record (9 Oct 2026).
"""

from __future__ import annotations

import re
from urllib.parse import quote

# '{id}' is replaced by the URL-quoted identifier.
LINK_TEMPLATES = {
    "simbad": "https://simbad.cds.unistra.fr/simbad/sim-id?Ident={id}",
    "gaia_dr3": "https://vizier.cds.unistra.fr/viz-bin/VizieR-4?-source=I/355/gaiadr3&Source={id}",
    "cns5": "https://vizier.cds.unistra.fr/viz-bin/VizieR-4?-source=J/A%2BA/670/A19/cns5&CNS5={id}",
    "msc": "https://vizier.cds.unistra.fr/viz-bin/VizieR-4?-source=J/ApJS/235/6/systems&ID={id}",
    "exoplanet_archive": "https://exoplanetarchive.ipac.caltech.edu/overview/{id}",
    "ads": "https://ui.adsabs.harvard.edu/abs/{id}/abstract",
    "doi": "https://doi.org/{id}",
    "arxiv": "https://arxiv.org/abs/{id}",
}

# A catalog named without a row to point at: its own landing page.
CATALOG_PAGES = {
    "Gaia DR3": "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=I/355",
    "Gaia DR2": "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=I/345",
    "CNS5": "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/A%2BA/670/A19",
    "MSC": "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/ApJS/235/6",
}

SUN_LSR = ["Motion: Schönrich, Binney & Dehnen 2010 (the Sun's motion, LSR)",
           "https://ui.adsabs.harvard.edu/abs/2010MNRAS.403.1829S/abstract"]

BIBCODE = re.compile(r"^(1[89]|20)\d\d[A-Za-z&.]{5}[\dA-Za-z.]{4}[A-Za-z.][\d.]{4}[A-Z.]$")


def link(kind: str, ident) -> str:
    return LINK_TEMPLATES[kind].replace("{id}", quote(str(ident).strip(), safe=""))


def gaia_dr3(source_id) -> list:
    return [f"Gaia DR3 {source_id}", link("gaia_dr3", source_id)]


def existence_sources(simbad_id: str = "", gaia_id: str = "", cns5_id: str = "", wds: str = "",
                      exoplanet_host: str = "") -> list[list]:
    """[label, url] pairs for the catalogs that list the star: SIMBAD, Gaia DR3, CNS5, MSC, the Exoplanet Archive."""
    out = []
    if simbad_id:
        out.append([f"Exists: SIMBAD {simbad_id}", link("simbad", simbad_id)])
    if gaia_id:
        out.append([f"Exists: Gaia DR3 {gaia_id}", link("gaia_dr3", gaia_id)])
    if cns5_id:
        n = str(cns5_id).replace("CNS5", "").strip()
        out.append([f"Exists: CNS5 {n} (Golovin et al. 2023)", link("cns5", n)])
    if wds:
        out.append([f"Exists: Multiple Star Catalog, WDS {wds} (Tokovinin 2018)", link("msc", wds)])
    if exoplanet_host:
        out.append([f"Exists: NASA Exoplanet Archive, {exoplanet_host}", link("exoplanet_archive", exoplanet_host)])
    return out


def _url_label(url: str) -> str:
    """A paper's handle where the URL carries one (arXiv id, DOI, bibcode), else its site and path."""
    for pat, fmt in ((r"arxiv\.org/(?:abs|pdf)/([^?#]+?)(?:v\d+)?(?:\.pdf)?$", "arXiv:{}"),
                     (r"doi\.org/(.+)$", "doi:{}"),
                     (r"adsabs\.harvard\.edu/abs/([^/?#]+)", "{}"),
                     (r"/viz-bin/cat/([^?#]+)$", "VizieR {}")):
        m = re.search(pat, url)
        if m:
            return fmt.format(m.group(1).replace("%26", "&"))
    rest = url.split("//", 1)[-1]
    return rest if len(rest) <= 60 else rest[:57] + "..."


def ref_link(token: str, gaia_id: str = "", simbad_id: str = "", wds: str = "", cns5_id: str = ""):
    """(label, url) for one Kinematics refs token, or None when it names nothing linkable."""
    t = token.strip()
    if not t:
        return None
    if t == "Gaia DR3" and gaia_id:
        return f"Gaia DR3 {gaia_id}", link("gaia_dr3", gaia_id)
    if t == "CNS5" and cns5_id:
        n = str(cns5_id).replace("CNS5", "").strip()
        return f"CNS5 {n}", link("cns5", n)
    if t == "MSC" and wds:
        return f"MSC, WDS {wds}", link("msc", wds)
    if t == "SIMBAD" and simbad_id:
        return f"SIMBAD {simbad_id}", link("simbad", simbad_id)
    if t in CATALOG_PAGES:
        return t, CATALOG_PAGES[t]
    if t.startswith(("http://", "https://")):
        return _url_label(t), t
    if t.lower().startswith("doi:"):
        return t, link("doi", t[4:])
    if t.lower().startswith("arxiv:"):
        return t, LINK_TEMPLATES["arxiv"].replace("{id}", t[6:])
    if BIBCODE.match(t):
        return t, link("ads", t)
    return None


def kinematics_sources(refs: str, gaia_id: str = "", simbad_id: str = "", wds: str = "",
                       cns5_id: str = "") -> list[list]:
    """[label, url] pairs for a 'RV: a, b; PM: c' Kinematics refs cell, labelled by what each one measured."""
    out, seen = [], {}
    for part in (refs or "").split(";"):
        what, _, toks = part.partition(":")
        what = {"RV": "Radial velocity", "PM": "Proper motion"}.get(what.strip())
        if not what:
            continue
        for tok in toks.split(","):
            hit = ref_link(tok, gaia_id, simbad_id, wds, cns5_id)
            if not hit:
                continue
            label, url = hit
            if url in seen:                    # one source for both: say so once
                seen[url][0] = seen[url][0].replace(":", " and " + what.lower() + ":", 1)
                continue
            seen[url] = [f"{what}: {label}", url]
            out.append(seen[url])
    return out
