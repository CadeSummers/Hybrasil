# Third-party notices

Hybrasil's own code is AGPL-3.0-or-later (`LICENSE`), and its compiled dataset
is CC BY-SA 4.0 (`LICENSE-DATA`). The material below comes from other people
and keeps its own terms. This file lists the main sources and the credit each
asks for. The value-by-value record is in the dataset itself: each value's
source is on its cell, in its cell note, or on the workbook's Sources &
Provenance tab. `STAR_SYSTEM_SOURCES.md` aggregates every source.

## Images

**Milky Way background** (`hybrasil/viz/sky/`). Converted from NASA's Deep
Star Maps 2020, <https://svs.gsfc.nasa.gov/4851>. The credit NASA asks for:

> NASA/Goddard Space Flight Center Scientific Visualization Studio.
> Gaia DR2: ESA/Gaia/DPAC.

The viewer shows this credit whenever the sky is on.

## Data

**ESA Gaia** (DR2, EDR3 and DR3: positions, parallaxes, proper motions,
radial velocities, astrophysical parameters and non-single-star orbits).
Gaia data are released under CC BY-SA 3.0 IGO.

> This work has made use of data from the European Space Agency (ESA) mission
> Gaia (<https://www.cosmos.esa.int/gaia>), processed by the Gaia Data
> Processing and Analysis Consortium (DPAC,
> <https://www.cosmos.esa.int/web/gaia/dpac/consortium>). Funding for the DPAC
> has been provided by national institutions, in particular the institutions
> participating in the Gaia Multilateral Agreement.

**NASA Exoplanet Archive** (confirmed planets and host parameters).

> This research has made use of the NASA Exoplanet Archive, which is operated
> by the California Institute of Technology, under contract with the National
> Aeronautics and Space Administration under the Exoplanet Exploration Program.

**ExoFOP** (follow-up records for TESS candidates).

> This research has made use of the Exoplanet Follow-up Observation Program
> (ExoFOP; DOI: 10.26134/ExoFOP5) website, which is operated by the California
> Institute of Technology, under contract with the National Aeronautics and
> Space Administration under the Exoplanet Exploration Program.

**SIMBAD and VizieR**, CDS, Strasbourg (spectral types, identifiers,
cross-matches and published catalogue tables).

> This research has made use of the SIMBAD database (Wenger et al. 2000,
> A&AS 143, 9) and the VizieR catalogue access tool (DOI:
> 10.26093/cds/vizier; Ochsenbein et al. 2000, A&AS 143, 23), operated at CDS,
> Strasbourg, France.

**Catalogues**, each cited by its paper:

- Fifth Catalogue of Nearby Stars, CNS5: Golovin et al. 2023, A&A 670, A19.
- Multiple Star Catalog, MSC: Tokovinin 2018, ApJS 235, 6.
- Sixth Catalog of Orbits of Visual Binary Stars (ORB6) and the Washington
  Double Star Catalog: Mason et al. 2001, AJ 122, 3466; U.S. Naval Observatory.
- Ninth Catalogue of Spectroscopic Binary Orbits, SB9: Pourbaix et al. 2004,
  A&A 424, 727.
- A Modern Mean Dwarf Stellar Color and Effective Temperature Sequence:
  E. Mamajek, after Pecaut & Mamajek 2013, ApJS 208, 9.
- Habitable-zone limits and the runaway-greenhouse ratio behind each star's
  colour factor: Kopparapu et al. 2013, ApJ 765, 131.
- Open Exoplanet Catalogue, used as a cross-check: Rein 2012,
  arXiv:1211.7121.
- TESS Objects of Interest and the TESS Input Catalog: Guerrero et al. 2021,
  ApJS 254, 39; Stassun et al. 2019, AJ 158, 138.
- The S-stars around Sgr A*: Gillessen et al. 2017, ApJ 837, 30, and the
  GRAVITY Collaboration's refits.

**Built-in systems.** The orbits of the systems built into the code come from
the papers named in `hybrasil/data/builtin_systems.py`, among them Agol et al.
2021 (TRAPPIST-1), Pourbaix 2002 and Kervella et al. 2017 (Alpha Centauri and
Proxima Centauri), and Deitrick et al. 2015 (Upsilon Andromedae).

**Wikipedia.** Some values were read from Wikipedia, which is CC BY-SA. Each
one is marked in the dataset with a pink border and logged on its Wikipedia
sources tab, with both the Wikipedia page and the source Wikipedia cites for
that number.

## Software

- **three.js** (MIT licence, <https://threejs.org>), loaded by the viewer from
  the jsDelivr CDN and not redistributed here.
- **Plotly** (plotly.py and plotly.js, MIT licence, <https://plotly.com>).
  The Plotly viewer loads plotly.js from Plotly's CDN, or embeds it, with its
  own licence header, when an HTML file is written to work offline.
- Python dependencies installed by pip, each under its own licence: NumPy
  (BSD-3-Clause), PyYAML (MIT), openpyxl (MIT), and the optional
  Google API client, Astroquery and Astropy (Apache-2.0 / BSD), and Kaleido
  (MIT).
