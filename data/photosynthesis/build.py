# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build the Photosynthesis limits tab: the light Earth's photosynthesisers need, with sources.

    python build.py          plan: print every row and the blocks below it; touches nothing
    python build.py write    create the tab, mark inferred cells, write S&P and Legend notes, rename

Every PAR value comes from the paper named in its row (research of 2 October 2026; nothing from memory). A level
no source gives is left blank and grey. Values converted from lux or from annual totals are orange-bordered with a
hover note, and so is every computed column (% of full sun, W m^-2, AU) and the per-star block.

hybrasil/data/photosynthesis_limits.py carries the PAR numbers as literal rows for the viewer, checked against
the snapshot of this tab by tests/test_photosynthesis.py: change the sheet, then the rows.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data" / "four_plus_stars"))
from hybrasil.data import google_sheets as gs  # noqa: E402
from hybrasil.mechanics.photosynthesis import par_photon_factor  # noqa: E402
from fill import letter, q  # noqa: E402  (importing fill also installs its 429 retry wrapper)

PLAN = "write" not in sys.argv[1:]
SID = gs.resolve_spreadsheet_id()
TAB, AFTER = "Photosynthesis limits", "Orbital Bands"
SP, LG = "Sources & Provenance", "Legend & Notes"
LOG = HERE / "build_log.json"
GREY_RULE, GREY_FILL = "FFBFBFBF", "FFDCDBE2"
DATE = "2 October 2026"

HEADERS = ["Organism", "Example species", "Primary energy", "Level",
           "PAR (umol photons m-2 s-1)", "% of Earth full-sun PAR", "PAR energy (W m-2)",
           "Total-energy equivalent, top of atmosphere (W m-2)", "Distance from the Sun (AU)",
           "Drawn as a ring?", "Conditions measured", "Source", "Confidence", "Notes"]
COL = {h: i for i, h in enumerate(HEADERS)}

LUX = ("INFERRED: {lux} lux x 0.0185 umol m-2 s-1 per lux (the sunlight factor, Thimijan & Heins 1983, HortScience "
       "18:818). WEAK: shade and cave light is spectrally unlike sunlight, so the factor is approximate.")
YEAR = ("INFERRED: {mol} mol m-2 yr-1 x 1e6 / 31,557,600 s per year = {v} umol m-2 s-1. A year-round mean that "
        "includes the dark months, not a noon value.")

SUN_C4 = "Oxygenic photoautotroph (C4 plant)"
SUN_C3 = "Oxygenic photoautotroph (C3 plant)"
OXY = "Oxygenic photoautotroph"
FLAG = "Oxygenic photoautotroph; see Notes on mixotrophy"
GSB = ("Obligate anoxygenic photolithoautotroph: no growth in the dark (Overmann et al. 1992, p. 152; "
       "Manske et al. 2005, p. 8057)")

# (organism, primary energy, [optimal, growth, survival]); each level is None or a dict.
ORGANISMS = [
    ("Sun-loving crops", SUN_C4, [
        dict(par=1800, sp="Maize (Zea mays)", cond="Field leaves; saturation 1800-2000 by leaf position and growth stage",
             src="Li et al. 2016, Chinese Journal of Plant Ecology 40:1310, doi:10.17521/cjpe.2016.0082 (abstract table)",
             conf="Medium",
             note="No leaf-level sunflower (Helianthus annuus) value was found; maize stands in for the sun-lovers. "
                  "Lab maize grown at 300 was not saturated at 2000 and reached ~4700 (Pappert et al. 2025, Front. "
                  "Plant Sci., doi:10.3389/fpls.2025.1511768, Fig. 3B)."),
        dict(par=31, sp="Maize (Zea mays)", cond="Field leaves; light compensation 31-49",
             src="Li et al. 2016, Chinese Journal of Plant Ecology 40:1310, doi:10.17521/cjpe.2016.0082 (abstract table)",
             conf="Medium",
             note="Textbook range for sun plants 10-20 (Taiz & Zeiger 2010, Plant Physiology 5th ed., ch. 9)."),
        None]),
    ("C3 crops", SUN_C3, [
        dict(par=1000, sp="Rice (Oryza sativa), flag leaf",
             cond="Field, 400 ppm CO2, 24-45 C; median saturation (829 for low-light leaves)",
             src="Yao et al. 2025, Plants 14:23, doi:10.3390/plants14010023, Results and Figs 1-2", conf="High",
             note="Wheat saturated at 1500 (Inghels et al. 2026, Physiol. Plant., doi:10.1111/ppl.70997, Methods)."),
        dict(par=16.9, sp="Rice (Oryza sativa), flag leaf", cond="Field; compensation medians 16.9-22.3",
             src="Yao et al. 2025, Plants 14:23, doi:10.3390/plants14010023, Results", conf="High",
             note="Wheat 41.7-63.8, mean 56.3 (Inghels et al. 2026, Table 1; low-medium confidence, the unit is "
                  "mislabelled there)."),
        None]),
    ("Shade-tolerant understory herbs", OXY, [
        dict(par=92.5, lux=5000, sp="Wood sorrel (Oxalis acetosella)",
             cond="Field, montane beech forest; saturation at 5-6 klx",
             src="Schulze 1972, Oecologia 9:235, doi:10.1007/BF00345234, abstract point 1", conf="Medium", note=""),
        dict(par=5.55, lux=300, sp="Wood sorrel (Oxalis acetosella) and other herb-layer species",
             cond="Field, montane beech forest; compensation at 300-500 lux",
             src="Schulze 1972, Oecologia 9:235, doi:10.1007/BF00345234, abstract", conf="Medium",
             note="Textbook range for shade plants 1-5 (Taiz & Zeiger 2010, ch. 9)."),
        dict(par=0.35, sp="Cave flora, SW China (418 vascular species, 81% flowering plants; Elatostema commonest)",
             cond="Field spot readings in cave twilight zones; lowest per-cave mean 0.35 (overall mean 1.97)",
             src="Monro et al. 2018, PLoS ONE 13:e0190801, Table 1", conf="Medium",
             note="Spot readings, not daily light integrals.")]),
    ("Mosses", OXY, [
        dict(par=583, sp="39 moss species", cond="Lab; PPFD at 95% of light saturation, median (16 liverworts: 214)",
             src="Marschall & Proctor 2004, Annals of Botany 94:593, doi:10.1093/aob/mch178, abstract", conf="High",
             note=""),
        dict(par=5.4, sp="10 Hawaiian moss species", cond="Compensation 5.4-32.6",
             src="Waite & Sack 2010, New Phytologist 185:156, Results", conf="Medium",
             note="Read from a search snippet of the Results."),
        dict(par=4.29, lux=232, sp="Amblystegium serpens, Hungarian caves", cond="Field; 232 lux",
             src="Buczko & Rajczy 1989, as cited in Glime, Bryophyte Ecology, ch. 9-5", conf="Medium", note="")]),
    ("Filmy ferns", OXY, [
        dict(par=30, sp="Killarney fern (Trichomanes speciosum)",
             cond="Lab, 20 C, saturating CO2; light saturation 30-50",
             src="Johnson et al. 2000, New Phytologist 148:423, p. 427, Fig. 3", conf="High",
             note="Hymenoglossum cruentum 24.6, Hymenophyllum dentatum 40.5 (Parra et al. 2015, PLoS ONE, "
                  "doi:10.1371/journal.pone.0145475, Table 2)."),
        dict(par=3.9, sp="Hymenoglossum cruentum", cond="Lab, 15 C, 390 ppm CO2; light compensation",
             src="Parra et al. 2015, PLoS ONE, doi:10.1371/journal.pone.0145475, Table 2", conf="High",
             note="T. speciosum c. 2-5 at 20 C, estimated below 1 at in-situ cave temperatures (Johnson et al. "
                  "2000, pp. 427, 429)."),
        dict(par=0.1, sp="Killarney fern (Trichomanes speciosum), gametophyte",
             cond="Field, UK; below 1 for ~85% of daylight hours, often ~0.1; '<0.01% of full sunlight'",
             src="Johnson et al. 2000, New Phytologist 148:423, pp. 423-429", conf="High",
             note="The free-living gametophyte generation, not the vascular sporophyte.")]),
    ("Low-light cyanobacteria", "Oxygenic photoautotroph (cyanobacterium)", [
        dict(par=13.9, sp="Prochlorococcus low-light strains MIT1300xe, MIT1327",
             cond="Lab; maximum growth at 13.9-33.8",
             src="Becker et al. 2024, mBio, doi:10.1128/mbio.03497-23, Fig. 2A, Table 2", conf="High", note=""),
        dict(par=1.5, sp="Prochlorococcus low-light strains MIT1300xe, MIT1327",
             cond="Lab; grew at 1.5, the lowest irradiance tested, so the true limit is at or below it",
             src="Becker et al. 2024, mBio, doi:10.1128/mbio.03497-23, Fig. 2A, Table 2", conf="High",
             note="MIT1214 grew at 0.22 mol m-2 d-1, its lowest tested (Hawco et al. 2020, ISME J, "
                  "doi:10.1038/s41396-020-00776-y, Fig. 1)."),
        None]),
    ("Kelp", OXY, [
        dict(par=20, sp="Laminaria hyperborea, Saccharina latissima, L. digitata, Alaria (young sporophytes)",
             cond="Lab, continuous light; growth saturated at 20-30",
             src="Han & Kain 1996, European Journal of Phycology 31:233 (abstract)", conf="Medium",
             note="In situ Ik 20-30 (meristem) for L. solidungula (Dunton & Jodwalis 1988, Marine Biology 98:277)."),
        dict(par=1, sp="Laminaria hyperborea (young sporophytes)",
             cond="Lab; ~1 minimum for growth, 1-2 sustained growth in all four species",
             src="Han & Kain 1996, European Journal of Phycology 31:233 (abstract)", conf="Medium",
             note="An unverified snippet gives ~30 for adult L. hyperborea blade compensation in summer: a "
                  "different measure (adult photosynthesis, not juvenile growth)."),
        dict(par=0.285, mol=9, sp="Arctic kelp (Laminaria solidungula)",
             cond="Field, 79 N; depth limit 20 m, 0.18% of surface light, 9 mol m-2 yr-1",
             src="Markager & Sand-Jensen 1992, via Runcie et al. 2008, European Journal of Phycology 43:377, "
                 "doi:10.1080/09670260801979303, Table 1", conf="High", note="")]),
    ("Marine diatoms", "Oxygenic photoautotroph (diatom)", [
        dict(par=89.5, sp="Thalassiosira pseudonana",
             cond="Lab, 20 C, 12:12 light:dark, grown at 75; Ik 89.5-99.2 from the P-I curve",
             src="Yang & Gao 2012, Marine Environmental Research 79:142, Table 2", conf="High", note=""),
        dict(par=1, sp="Phaeodactylum tricornutum",
             cond="Lab; compensation for growth below 1 (division 0 per day at 0.75, 0.045 per day at 3.5)",
             src="Geider, Osborne & Raven 1986, Journal of Phycology, doi:10.1111/j.1529-8817.1986.tb02513.x",
             conf="Medium", note="An upper bound: the compensation point lies between 0.75 and 1."),
        None]),
    ("Green sulfur bacteria", GSB, [
        dict(par=1, sp="Chlorobium phaeobacteroides BS1 (strain MN1), Black Sea",
             cond="Culture, 15 C, 14C fixation; photosynthesis saturated at 1 (cultures grown at 3)",
             src="Manske et al. 2005, Applied and Environmental Microbiology 71:8049, "
                 "doi:10.1128/AEM.71.12.8049-8060.2005, Fig. 6", conf="High",
             note="Light-inhibited above 200 (Overmann et al. 1992, p. 151)."),
        dict(par=0.25, sp="Chlorobium phaeobacteroides BS1 (strain MN1), Black Sea",
             cond="Culture; significant growth at 0.25 uEinst m-2 s-1, where 12 other green and purple sulfur "
                  "strains could not grow",
             src="Overmann, Cypionka & Pfennig 1992, Limnology and Oceanography 37:150, "
                 "doi:10.4319/lo.1992.37.1.0150, p. 151, Fig. 2A", conf="High",
             note="CO2 fixation was measured down to 0.015 in culture (Manske et al. 2005): photosynthesis, not "
                  "demonstrated growth."),
        dict(par=0.00075, sp="Chlorobium phaeobacteroides BS1, Black Sea chemocline (~100 m)",
             cond="In situ, top of the bacterial layer at solar noon in December; 0.0022-0.00075, i.e. "
                  "0.0009-0.0003% of the surface value",
             src="Manske et al. 2005, Applied and Environmental Microbiology 71:8049, "
                 "doi:10.1128/AEM.71.12.8049-8060.2005, abstract, p. 8056, Fig. 1", conf="High",
             note="The same population has been present for at least 16 years, with in-situ doubling times of "
                  "3.1-26 years. Measured with a LI-COR quantum sensor (400-700 nm); the cells harvest the "
                  "blue-green light that reaches them (Overmann et al. 1992).")]),
    ("Sea-ice algae", FLAG, [
        dict(par=7, sp="Nitzschia frigida, Thalassiosira antarctica",
             cond="Lab, continuous light, -4 to -6 C; growth saturated at 7-10",
             src="Aletsee & Jahnke 1992, Polar Biology 11:643 (abstract)", conf="Medium", note=""),
        dict(par=0.17, sp="Ice-algae community, Station Nord, NE Greenland",
             cond="Field under ~1 m snow and ~1 m ice; net growth at <0.17 at noon (0.023% of 750 at the surface)",
             src="Hancke et al. 2018, JGR Oceans 123:985, doi:10.1002/2017JC013263, pp. 6-9", conf="High",
             note="An instantaneous noon value. Older literature commonly gives 2-9, lowest 0.36 (as cited in "
                  "Hancke et al. 2018, p. 7)."),
        dict(par=0.04, sp="Under-ice phytoplankton and ice algae (Pseudo-nitzschia, Nitzschia, Navicula), ~86 N",
             cond="Field, MOSAiC 2020; growth onset at <=0.04 +/- 0.02 as a daily average",
             src="Hoppe et al. 2024, Nature Communications 15:7385, doi:10.1038/s41467-024-51636-8", conf="High",
             note="FLAG: the authors note that mixotrophy and stored reserves were available through the winter, "
                  "though they argue these do not explain the growth. Growth onset, listed here as the least "
                  "light these algae are known to persist under. Theoretical minimum for oxygenic phototrophs "
                  "0.01 (Raven, Kubler & Beardall 2000, J. Mar. Biol. Assoc. UK 80:1, "
                  "doi:10.1017/S0025315499001526).")]),
    ("Deep crustose coralline red algae", FLAG, [
        dict(par=4.2, sp="Crustose Corallinales, 201 m, Penguin Bank, Hawaii",
             cond="In situ PAM fluorometry from a submersible; Ek 4.2 +/- 2 from rapid light curves",
             src="Runcie et al. 2008, European Journal of Phycology 43:377, doi:10.1080/09670260801979303, Results",
             conf="High", note=""),
        None,
        dict(par=0.000158, mol=0.005, sp="Undescribed crustose coralline alga, 268 m, San Salvador, Bahamas",
             cond="Field; 0.0005% of surface light, 0.005 mol m-2 yr-1",
             src="Littler et al. 1985, Science 227:57; Littler et al. 1986, Deep-Sea Research 33:881; via Runcie "
                 "et al. 2008, Table 1 (primary papers not opened)", conf="High (secondary)",
             note="FLAG: whether its metabolism is supported by mixotrophy has been questioned (Raven et al. 2000). "
                  "Kept, flagged. Hancke et al. 2018 (p. 7) cite the same alga at 274 m with a calculated midday "
                  "PAR below 0.02.")]),
]
NOT_FOUND = {("Sun-loving crops", "survival"): "NOT FOUND: no survival threshold was found.",
             ("C3 crops", "survival"): "NOT FOUND. Soybean grew at 10.9% irradiance for 15 days (Fan et al. 2019, "
                                       "BMC Plant Biol. 19:34), a shading test rather than a limit.",
             ("Low-light cyanobacteria", "survival"): "NOT FOUND.",
             ("Marine diatoms", "survival"): "NOT FOUND for a diatom culture; see Sea-ice algae for field values.",
             ("Deep crustose coralline red algae", "growth"):
                 "NOT FOUND: no compensation irradiance has been measured for deep crusts, so no ring is drawn."}
LEVEL_NAME = {"optimal": "Optimal (light saturation)", "growth": "Growth limit (compensation point)",
              "survival": "Survival limit (least light persisted under)"}

REFS = [  # (key, quantity, value, unit, source, confidence)
    ("par", "Earth full-sun PAR at the surface, midday, clear sky", 2000, "umol photons m-2 s-1",
     "Taiz & Zeiger 2010, Plant Physiology 5th ed., ch. 9 ('about 2000')", "High"),
    ("conv", "Photon-to-energy factor for sunlight PAR", 4.57, "umol J-1 (+/- 0.1)",
     "McCree 1972, Agricultural Meteorology 10:443, as quoted by Noriega Gardea et al. 2021, Atmosfera 34(3), "
     "doi:10.20937/atm.52737; Thimijan & Heins 1983, HortScience 18:818", "High"),
    ("tsi", "Total solar irradiance at the top of Earth's atmosphere", 1360.8, "W m-2 (+/- 0.5, solar minimum)",
     "Kopp & Lean 2011, Geophysical Research Letters 38:L01706, doi:10.1029/2010GL045777", "High"),
    ("surf", "Surface global irradiance, reference spectrum", 1000, "W m-2 (AM1.5 global tilted)",
     "ASTM G173-03, via NREL 'Reference Air Mass 1.5 Spectra'. A test standard, not a measured noon value",
     "Medium"),
    ("lux", "Lux to PAR photons, sunlight", 0.0185, "umol m-2 s-1 per lux",
     "Thimijan & Heins 1983, HortScience 18:818, via Apogee Instruments", "Medium"),
]

SCOPE = [
    "SCOPE AND METHOD",
    "Only organisms whose PRIMARY way of gaining energy is photosynthesis from starlight are listed. Left out on "
    "purpose: the green sulfur bacterium GSB1, which lives on geothermal light at a deep-sea hydrothermal vent "
    "(Beatty et al. 2005, PNAS 102:9306, doi:10.1073/pnas.0503674102); purple sulfur bacteria, which also fix CO2 "
    "in the dark (Di Nezio et al. 2021, FEMS Microbiology Ecology 97:fiab010) and of which none tested grew at 0.25 "
    "(Overmann et al. 1992); and mixotrophs, photoheterotrophs and photosynthetic symbioses such as corals, where "
    "light only supplements another energy source. Two kept rows carry a published doubt and say so in Notes.",
    "Levels. Optimal = light saturation, where more light no longer speeds the organism up. Growth limit = the "
    "compensation point, the least light that still gives net growth: this is the level hybrasil draws a ring "
    "at. Survival limit = the least light the organism has been found to persist under. A level no source gives is "
    "left blank and grey.",
    "PAR photons drive the calculation. Thresholds are photosynthetically active photons, 400-700 nm, in umol "
    "photons m-2 s-1. Around another star the ring sits at sqrt(L x k / f) AU, f being the threshold over Earth's "
    "full-sun PAR and k the star's blackbody PAR photon yield per watt relative to the Sun's "
    "(hybrasil/mechanics/photosynthesis.py). The total-energy columns, sqrt(L / f) with no colour term, are "
    "recorded for comparison only and are not what is drawn.",
    "Every threshold was measured beneath Earth's air or water, so every distance assumes starlight thinned the "
    "same way. Noon, instantaneous and daily-average values are mixed in this table; Conditions says which. A noon "
    "value overstates a daily mean.",
]


def plan_rows():
    """[(cells by header, marks)] for the data rows, in tab order (row 2 down)."""
    rows = []
    for org, energy, levels in ORGANISMS:
        for key, lv in zip(("optimal", "growth", "survival"), levels):
            r = {"Organism": org, "Primary energy": energy, "Level": LEVEL_NAME[key]}
            if lv is None:
                r["Notes"] = NOT_FOUND[(org, key)]
                r["_blank"] = True
            else:
                r.update({"Example species": lv["sp"], "PAR (umol photons m-2 s-1)": lv["par"],
                          "Conditions measured": lv["cond"], "Source": lv["src"], "Confidence": lv["conf"],
                          "Notes": lv["note"]})
                if key == "growth":
                    r["Drawn as a ring?"] = "Yes"
                if "lux" in lv:
                    r["_par_note"] = LUX.format(lux=lv["lux"])
                if "mol" in lv:
                    r["_par_note"] = YEAR.format(mol=lv["mol"], v=lv["par"])
            r["_key"] = key
            rows.append(r)
    return rows


STARS = [("Sun", 1.0, 5772.0, "IAU 2015 nominal solar values (Teff 5772 K)"),
         ("Proxima Centauri", 0.00151, 2980.0, "Ribas et al. 2017, A&A 603, A58 (as builtin_systems.py)"),
         ("TRAPPIST-1", 0.0005285766791, 2516.0, "this workbook's Systems tab (as builtin_systems.py)")]


def layout():
    """Every block's rows and the formulas that tie them together: (values, formulas, marks)."""
    rows = plan_rows()
    n = len(rows)
    first_data, last_data = 2, n + 1
    values, formulas = {}, {}
    orange, notes, grey = [], {}, []
    cell = lambda h, r: f"{letter(COL[h])}{r}"
    for i, r in enumerate(rows):
        rr = first_data + i
        for h in HEADERS:
            if h in r:
                values[cell(h, rr)] = r[h]
        if r.get("_blank"):
            grey += [cell(h, rr) for h in HEADERS[4:9]]
        if r.get("_par_note"):
            orange.append(cell("PAR (umol photons m-2 s-1)", rr))
            notes[cell("PAR (umol photons m-2 s-1)", rr)] = r["_par_note"]

    # The blocks under the data: scope, references, then the three stars.
    r0 = last_data + 2
    for i, line in enumerate(SCOPE):
        values[f"A{r0 + i}"] = line
    ref0 = r0 + len(SCOPE) + 1
    values[f"A{ref0}"] = "REFERENCE VALUES"
    ref_at = {}
    for i, (key, qty, v, unit, src, conf) in enumerate(REFS):
        rr = ref0 + 1 + i
        ref_at[key] = f"$E${rr}"
        values.update({f"A{rr}": qty, f"E{rr}": v, f"K{rr}": unit, f"L{rr}": src, f"M{rr}": conf})
    par, conv, tsi = ref_at["par"], ref_at["conv"], ref_at["tsi"]

    E = lambda rr: f"E{rr}"
    for i, r in enumerate(rows):
        rr = first_data + i
        if r.get("_blank"):
            continue
        f_ = {"% of Earth full-sun PAR": f"={E(rr)}/{par}*100",
              "PAR energy (W m-2)": f"={E(rr)}/{conv}",
              "Total-energy equivalent, top of atmosphere (W m-2)": f"={E(rr)}/{par}*{tsi}",
              "Distance from the Sun (AU)": f"=1/SQRT({E(rr)}/{par})"}
        for h, fx in f_.items():
            c = cell(h, rr)
            formulas[c] = fx
            orange.append(c)
        notes[cell("% of Earth full-sun PAR", rr)] = (
            "INFERRED: PAR / 2000 umol m-2 s-1 (Earth full sun, Taiz & Zeiger 2010). The same fraction is the "
            "share of the Sun's total energy, since it is the Sun's own spectrum.")
        notes[cell("PAR energy (W m-2)", rr)] = "INFERRED: PAR / 4.57 umol J-1 (McCree 1972, sunlight)."
        notes[cell("Total-energy equivalent, top of atmosphere (W m-2)", rr)] = (
            "INFERRED: (PAR / 2000) x 1360.8 W m-2 (Kopp & Lean 2011): the total sunlight at the top of the "
            "atmosphere that, thinned as Earth's is, gives this PAR. Assumes the Sun's spectrum.")
        notes[cell("Distance from the Sun (AU)", rr)] = (
            "INFERRED: 1 / sqrt(PAR / 2000) AU, the inverse-square law from Earth's full sun at 1 AU. Assumes an "
            "Earth-like atmosphere and noon full sun at 1 AU.")

    st0 = ref0 + len(REFS) + 2
    values[f"A{st0}"] = "GROWTH LIMITS AROUND THREE STARS (AU): BY PAR PHOTONS (DRAWN) AND BY TOTAL ENERGY"
    values.update({f"A{st0 + 1}": "Star", f"B{st0 + 1}": "Luminosity (L-sun)", f"C{st0 + 1}": "Teff (K)",
                   f"D{st0 + 1}": "PAR photon factor k", f"L{st0 + 1}": "Source of L and Teff"})
    star_at = {}
    for i, (name, lum, teff, src) in enumerate(STARS):
        rr = st0 + 2 + i
        k = par_photon_factor(teff)
        values.update({f"A{rr}": name, f"B{rr}": lum, f"C{rr}": teff, f"D{rr}": round(k, 6), f"L{rr}": src})
        orange.append(f"D{rr}")
        notes[f"D{rr}"] = (("INFERRED: blackbody PAR photons (400-700 nm) per watt at this Teff over the same at "
                            "5772 K, by Planck's law (hybrasil/mechanics/photosynthesis.py). ")
                           + ("WEAK: an M dwarf's molecular bands remove much of its visible light, so a "
                              "blackbody overstates its PAR." if teff < 4000 else "Exactly 1 for the Sun."
                              if teff == 5772.0 else ""))
        star_at[name] = rr
    m0 = st0 + 2 + len(STARS) + 1
    head = ["Organism (growth limit)", "f, fraction of Earth's PAR"]
    for name, *_ in STARS:
        head += [f"{name}, by PAR (drawn)", f"{name}, by total energy"]
    for j, h in enumerate(head):
        values[f"{letter(j)}{m0}"] = h
    growth = [(i, r) for i, r in enumerate(rows) if r["_key"] == "growth" and not r.get("_blank")]
    for j, (i, r) in enumerate(growth):
        rr = m0 + 1 + j
        src = first_data + i
        values[f"A{rr}"] = r["Organism"]
        formulas[f"B{rr}"] = f"=E{src}/{par}"
        orange.append(f"B{rr}")
        notes[f"B{rr}"] = "INFERRED: growth-limit PAR / 2000 umol m-2 s-1."
        for s, (name, *_ ) in enumerate(STARS):
            sr = star_at[name]
            c_par, c_tot = letter(2 + 2 * s), letter(3 + 2 * s)
            formulas[f"{c_par}{rr}"] = f"=SQRT($B${sr}*$D${sr}/B{rr})"
            formulas[f"{c_tot}{rr}"] = f"=SQRT($B${sr}/B{rr})"
            orange += [f"{c_par}{rr}", f"{c_tot}{rr}"]
            notes[f"{c_par}{rr}"] = "INFERRED: sqrt(L x k / f) AU. What hybrasil draws."
            notes[f"{c_tot}{rr}"] = "INFERRED: sqrt(L / f) AU, total energy only, no colour term. Not drawn."
    end_row = m0 + len(growth)
    return dict(rows=rows, values=values, formulas=formulas, orange=orange, notes=notes, grey=grey,
                last_data=last_data, end_row=end_row)


def sp_lines(L):
    return [
        "",
        f"PHOTOSYNTHESIS LIMITS, {DATE.upper()}: NEW TAB, {len(L['rows'])} ROWS ({len(ORGANISMS)} ORGANISMS x 3 "
        "LEVELS) PLUS SCOPE, REFERENCE AND PER-STAR BLOCKS",
        "  WHY: the light Earth's photosynthesisers need, so hybrasil can draw where each star's light falls to "
        "each organism's growth limit (the three.js viewer's Even more features menu).",
        "  SCOPE: only organisms whose primary energy source is photosynthesis from starlight; the exclusions and "
        "their citations are in the tab's SCOPE AND METHOD block.",
        "  SOURCES: every PAR value is from the paper in its row's Source cell, found by web research on "
        f"{DATE} by Claude. Full texts opened: Overmann et al. 1992, Manske et al. 2005, Runcie et al. 2008, "
        "Hancke et al. 2018, Yang & Gao 2012, Hoppe et al. 2024, Becker et al. 2024, Hawco et al. 2020, Johnson et "
        "al. 2000, Parra et al. 2015, Monro et al. 2018. The rest from abstracts or search snippets, rated Medium. "
        "Nothing written from memory; a level no source gave is blank and grey.",
        "  INFERRED (orange), METHOD 1, lux to PAR: lux x 0.0185 umol m-2 s-1 per lux (Thimijan & Heins 1983, "
        "sunlight). Valid for a sunlight spectrum; WEAK under a canopy or in a cave, where the light is greener. "
        "The error is not quantified. Used for three cells: wood sorrel optimal and growth, cave moss survival.",
        "  METHOD 2, annual totals to a flux: mol m-2 yr-1 x 1e6 / 31,557,600 s. Exact arithmetic; the result is a "
        "year-round mean including darkness. Used for Arctic kelp and the Bahamas coralline survival cells.",
        "  METHOD 3, the computed columns: % of full sun = PAR / 2000 (Taiz & Zeiger 2010); PAR energy = PAR / "
        "4.57 (McCree 1972, +/- 0.1); total-energy equivalent = (PAR / 2000) x 1360.8 W m-2 (Kopp & Lean 2011), "
        "which assumes the Sun's spectrum; distance from the Sun = 1 / sqrt(PAR / 2000) AU, inverse square. The "
        "2000 reference itself varies with latitude, season and cloud (Hancke et al. 2018 measured 750-1200 at "
        "81 N), so every distance scales as 1 / sqrt of whatever full sun is taken to be.",
        "  METHOD 4, the PAR photon factor k for another star: blackbody photons 400-700 nm per watt at the star's "
        "Teff over the same at 5772 K, Planck's law integrated by Simpson's rule (converged to 1e-12), in "
        "hybrasil/mechanics/photosynthesis.py. Valid as a blackbody at any Teff; it peaks at about 1.05 near "
        "6900 K. WEAK for M dwarfs: molecular bands remove much of their visible light, so a blackbody overstates "
        "their PAR. No model-atmosphere comparison was made.",
        "  SCATTER: where sources disagree, the row's Conditions or Notes quote the range. The widest: maize "
        "saturation 1800 (field) to ~4700 (lab); kelp compensation ~1 (juvenile growth) against ~30 (adult "
        "photosynthesis, unverified); ice-algae compensation 2-9 (older literature) against <0.17 and <=0.04.",
        "  HOW TO VERIFY: open the DOI in each row's Source cell; the value, page and figure are named there.",
    ]


def legend_lines():
    return [
        f"PHOTOSYNTHESIS LIMITS TAB -- {DATE.upper()}",
        "A new tab: for each Earth photosynthesiser, the light it needs at three levels (optimal, growth limit, "
        "survival limit) as PAR photons, with its source, and how far from the Sun that light falls. hybrasil "
        "draws one ring per organism, at its growth limit, around every star (three.js viewer, Even more features).",
        "It was started from a draft table that put the limits of complex life far too close in. Checked against "
        "the literature, row by row (full sun = 2000 umol m-2 s-1):",
        "  1.0 AU, 100%, optimal for all vascular plants: CONFIRMED (maize saturates at 1800-2000).",
        "  1.5 AU, ~44%, crops and complex flora: CONFIRMED (rice saturates at ~1000, wheat at 1500).",
        "  5.2 AU, ~3.7%, limit for vascular plants, ferns and large algae: CONTRADICTED. 3.7% is near-optimal for "
        "wood sorrel, which still gains at 0.3%; kelp grows at about 1 umol (0.05%).",
        "  9.5 AU, ~1.1%, absolute limit for macroalgae and mosses: CONTRADICTED. Mosses compensate down to 0.27%; "
        "kelps reach 0.18% at their depth limit.",
        "  19.2 AU, ~0.27%, impossible for complex life: CONTRADICTED. Filmy ferns still gain at 3.9 umol (0.2%); "
        "cave flowering plants grow at 0.35 umol (0.02%); a fern gametophyte persists below 0.01%.",
        "  80-100 AU, ~0.01%, absolute limit for single-celled extremophiles: PARTLY. About right for growth in "
        "culture (green sulfur bacteria at 0.25 umol, ~89 AU) and under sea ice (0.17, ~108 AU), but not absolute: "
        "Black Sea green sulfur bacteria have persisted for at least 16 years at 0.00075 umol, ~1,600 AU.",
        "Sources, methods and the inferred (orange) cells are written up on Sources & Provenance under "
        f"'PHOTOSYNTHESIS LIMITS, {DATE.upper()}'.",
    ]


def main():
    L = layout()
    if PLAN:
        for i, r in enumerate(L["rows"], start=2):
            print(f"{i:3} {r['Organism'][:28]:28} {r['_key']:8} {r.get('PAR (umol photons m-2 s-1)', '')!s:9} "
                  f"{r.get('Example species', '')[:40]}")
        print(f"data rows 2..{L['last_data']}, blocks to row {L['end_row']}; {len(L['values'])} values, "
              f"{len(L['formulas'])} formulas, {len(L['orange'])} orange, {len(L['notes'])} notes, "
              f"{len(L['grey'])} grey")
        for k in sorted(L["formulas"], key=lambda c: (int(''.join(ch for ch in c if ch.isdigit())), c))[:6]:
            print("   ", k, L["formulas"][k])
        print("\n".join(sp_lines(L)))
        print("\n".join(legend_lines()))
        return

    API = gs._sheets_api()
    props = {s["properties"]["title"]: s["properties"] for s in
             API.get(spreadsheetId=SID, fields="sheets.properties").execute()["sheets"]}
    assert TAB not in props, f"{TAB} already exists"
    nrows, ncols = L["end_row"] + 1, len(HEADERS)
    res = API.batchUpdate(spreadsheetId=SID, body={"requests": [{"addSheet": {"properties": {
        "title": TAB, "index": props[AFTER]["index"] + 1,
        "gridProperties": {"rowCount": nrows, "columnCount": ncols, "frozenRowCount": 1}}}}]}).execute()
    sid = res["replies"][0]["addSheet"]["properties"]["sheetId"]
    gs.invalidate_cache(SID)

    def rng(r0, r1, c0, c1):
        return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}
    # The header's look from the Planetless tab's header (bold, pale blue, wrapped).
    src = props["Planetless 4+ Stars"]["sheetId"]
    widths = [190, 260, 220, 200, 110, 110, 100, 130, 110, 80, 330, 380, 100, 420]
    reqs = [{"copyPaste": {"source": {"sheetId": src, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0,
                                      "endColumnIndex": 1},
                           "destination": rng(0, 1, 0, ncols), "pasteType": "PASTE_FORMAT"}}]
    for j, w in enumerate(widths):
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS",
                                                             "startIndex": j, "endIndex": j + 1},
                                                   "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    API.batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()

    first, last = f"{q(TAB)}!A1", f"{q(TAB)}!{letter(ncols - 1)}{nrows}"
    gs.update_cells(SID, {f"{q(TAB)}!A1:{letter(ncols - 1)}1": [HEADERS]}, expect={first: "", last: ""})
    vals = {f"{q(TAB)}!{c}": v for c, v in L["values"].items()}
    items = list(vals.items())
    for s in range(0, len(items), 400):
        gs.update_cells(SID, dict(items[s:s + 400]))
    fx = {f"{q(TAB)}!{c}": v for c, v in L["formulas"].items()}
    items = list(fx.items())
    for s in range(0, len(items), 400):
        gs.update_cells(SID, dict(items[s:s + 400]), value_input="USER_ENTERED")

    grey = {"style": "SOLID", "color": gs._hex_to_color(GREY_RULE)}
    reqs = [
        {"updateBorders": {"range": rng(1, L["last_data"], 0, ncols), "top": grey, "bottom": grey, "left": grey,
                           "right": grey, "innerHorizontal": grey, "innerVertical": grey}},
        {"setBasicFilter": {"filter": {"range": rng(0, L["last_data"], 0, ncols)}}},
        {"repeatCell": {"range": rng(1, L["last_data"], 0, ncols),
                        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
    ]
    for c in L["grey"]:
        col = sum((ord(ch) - 64) * 26 ** k for k, ch in enumerate(reversed(''.join(x for x in c if x.isalpha())))) - 1
        row = int(''.join(x for x in c if x.isdigit())) - 1
        reqs.append({"repeatCell": {"range": rng(row, row + 1, col, col + 1),
                                    "cell": {"userEnteredFormat": {"backgroundColor": gs._hex_to_color(GREY_FILL)}},
                                    "fields": "userEnteredFormat.backgroundColor"}})
    API.batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()
    orange = [f"{q(TAB)}!{c}" for c in L["orange"]]
    for s in range(0, len(orange), 200):
        gs.set_border(SID, orange[s:s + 200], gs.INFERRED_BORDER)
    notes = list({f"{q(TAB)}!{c}": v for c, v in L["notes"].items()}.items())
    for s in range(0, len(notes), 300):
        gs.set_note(SID, dict(notes[s:s + 300]))

    # Sources & Provenance: append at the grid's end (never values().append()).
    lines = sp_lines(L)
    meta = API.get(spreadsheetId=SID, ranges=[f"{q(SP)}!A1"], fields="sheets(properties(sheetId,gridProperties))"
                   ).execute()["sheets"][0]["properties"]
    end = meta["gridProperties"]["rowCount"]
    assert gs.read_cells(SID, [f"{q(SP)}!A{end}"])[f"{q(SP)}!A{end}"][0][0].strip()
    sp0, sp1 = end + 1, end + len(lines)
    API.batchUpdate(spreadsheetId=SID, body={"requests": [{"appendDimension": {
        "sheetId": meta["sheetId"], "dimension": "ROWS", "length": len(lines)}}]}).execute()
    gs.update_cells(SID, {f"{q(SP)}!A{sp0}:A{sp1}": [[x] for x in lines]},
                    expect={f"{q(SP)}!A{i}": "" for i in (sp0, sp0 + 1, sp1)})

    # Legend & Notes: after its last line, as recolour.py does.
    note = legend_lines()
    lv = API.values().get(spreadsheetId=SID, range=f"{q(LG)}!A1:A2000").execute().get("values", [])
    lg0 = len(lv) + 2
    lg1 = lg0 + len(note) - 1
    gs.update_cells(SID, {f"{q(LG)}!A{lg0}:A{lg1}": [[x] for x in note]},
                    expect={f"{q(LG)}!A{lg0}": "", f"{q(LG)}!A{lg1}": ""})

    title = gs.rename_workbook(None, gs.versioned_title())
    gs.invalidate_cache(SID)
    log = {"tab": TAB, "sheet_id": sid, "rows": len(L["rows"]), "end_row": L["end_row"],
           "orange": len(L["orange"]), "notes": len(L["notes"]), "sp_rows": [sp0, sp1], "legend_rows": [lg0, lg1],
           "title": title}
    LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
    print("done:", json.dumps(log))


if __name__ == "__main__":
    main()
