# Star System Sources

An aggregated list of the sources behind the hybrasil workbook and code. It is for keeping track, not for citing values: every value's own source is on its cell, in its note, or in the workbook's Sources & Provenance tab.

Compiled 7 October 2026 from the workbook snapshot `data/hy-brasil-20261007-1805.xlsx` (every cell and cell note on all tabs) and the repository's code and documentation, by `data/sources/build_sources_md.py`.

## Most Used Sources

The ten institutions whose data the project draws on most, ranked by how many workbook cells, cell notes and repository files name one of their catalogues, missions or services. The count is a rough measure of how often the source is used, not how important it is. Publication venues (arXiv, journals) are left out, because they are how papers are reached, not where the data comes from.

| # | Institution | What we use | Key reference | Mentions |
|---|---|---|---|---|
| 1 | European Space Agency (ESA) | Gaia DR3 / EDR3 / DR2: positions, parallaxes and distances, proper motions, radial velocities, FLAME masses and luminosities, GSP-Phot temperatures, non-single-star orbits, RUWE. Hipparcos: HIP identifiers and the older astrometric baseline behind proper-motion anomalies. | Gaia Collaboration, Vallenari et al. 2023, A&A 674, A1; Gaia Collaboration, Creevey et al. 2023, A&A 674, A26; Gaia Collaboration, Arenou et al. 2023, A&A 674, A34; van Leeuwen 2007, A&A 474, 653 | 7,523 |
| 2 | Centre de Données astronomiques de Strasbourg (CDS), Université de Strasbourg | SIMBAD for spectral types, identifiers and cross-matches; VizieR for published catalogue tables (e.g. Kervella et al. 2022, Cifuentes et al. 2020, Tokovinin 2018). | Wenger et al. 2000, A&AS 143, 9; Ochsenbein et al. 2000, A&AS 143, 23 | 3,882 |
| 3 | NSF NOIRLab / Cerro Tololo Inter-American Observatory | Andrei Tokovinin's Multiple Star Catalog (MSC): stellar hierarchies, companions and star counts, including the Planetless 4+ Stars systems. | Tokovinin 2018, ApJS 235, 6 | 3,163 |
| 4 | NASA TESS mission (MIT) | TESS Objects of Interest (TOI) for planet candidates; TESS Input Catalog v8.2 for stellar masses, temperatures and radii. | Ricker et al. 2015, JATIS 1, 014003; Stassun et al. 2019, AJ 158, 138; Guerrero et al. 2021, ApJS 254, 39 | 1,616 |
| 5 | U.S. Naval Observatory | Washington Double Star Catalog (WDS) separations and position angles; Sixth Catalog of Orbits of Visual Binary Stars (ORB6). | Mason et al. 2001, AJ 122, 3466 | 1,178 |
| 6 | NASA Exoplanet Science Institute (Caltech/IPAC) | NASA Exoplanet Archive (Planetary Systems Composite Parameters: confirmed planets, host luminosities); ExoFOP follow-up records for TESS candidates. | Akeson et al. 2013, PASP 125, 989 | 737 |
| 7 | University of Rochester / NASA JPL (E. Mamajek) | The Pecaut & Mamajek mean dwarf colour-temperature sequence: spectral type to temperature, luminosity and mass where a star has no direct measurement. | Pecaut & Mamajek 2013, ApJS 208, 9 | 720 |
| 8 | University of Toronto | Open Exoplanet Catalogue (OEC): the independent cross-check on every planet mass. | Rein 2012, arXiv:1211.7121 | 540 |
| 9 | Pennsylvania State University | Kopparapu et al. habitable-zone limits (the HZ columns) and the runaway-greenhouse ratio behind each star's colour factor in the solvent bands. | Kopparapu et al. 2013, ApJ 765, 131 | 309 |
| 10 | University of Massachusetts / IPAC | Two Micron All Sky Survey (2MASS) JHK photometry, the K-band input to M-dwarf mass relations. | Skrutskie et al. 2006, AJ 131, 1163 | 263 |

## Other Sources Used

In no particular order.

### Catalogues, archives and services

- Paris Observatory: The Extrasolar Planets Encyclopaedia (exoplanet.eu).
- European Southern Observatory: HARPS, ESPRESSO and SPHERE, through the papers that use them.
- arXiv (Cornell University): preprints of most of the papers below
- NASA Astrophysics Data System (ADS): bibliographic look-ups
- Calar Alto Observatory: CARMENES radial velocities and stellar parameters, through their papers
- W. M. Keck Observatory: HIRES radial velocities, through their papers
- Hipparcos-Gaia Catalog of Accelerations (Brandt 2021) and Kervella et al. proper-motion anomalies
- Ninth Catalogue of Spectroscopic Binary Orbits (SB9), Université Libre de Bruxelles (Pourbaix et al. 2004)
- Fifth Catalogue of Nearby Stars (CNS5), Astronomisches Rechen-Institut, Heidelberg (Golovin et al. 2023)
- Gaia white dwarf catalogue (Gentile Fusillo et al. 2021)
- NASA Kepler mission, through its planet papers
- Pan-STARRS1 and WISE imaging, for companion checks
- JWST and Hubble Space Telescope, through their papers
- NASA JPL Horizons: live osculating elements for the Solar System (--source horizons)
- NASA Scientific Visualization Studio: Deep Star Maps 2020, the background Milky Way
- IAU Working Group on Star Names: proper names
- Wikipedia: a handful of values, each marked with a pink border on the workbook

### Literature

574 papers and catalogues cited by author and year. They are listed alphabetically so an entry is easy to find; the order says nothing about weight. A journal or arXiv reference is given where the workbook writes one next to the citation.


**A**

- Abt 1965, ApJS 11, 429
- Agol et al. 2021, PSJ 2 1
- Ahrer et al. 2021
- Akeson et al. 2021, AJ 162, 14
- Aletsee & Jahnke 1992
- Almenara et al. 2022, A&A 665, A91
- Alonso-Floriano et al. 2015, A&A 577, A128
- Anderson & Francis 2012
- Andrae et al. 2018, A&A 616, A8
- Anglada-Escude et al. 2013, A&A 556
- Anglada-Escude et al. 2014, MNRAS 443, L89
- Anglada-Escudé et al. 2016, Nature 536
- Apps et al. 2010
- Archinal et al. 2018
- Artigau et al. 2022, arXiv:2207.13524
- Asplund et al. 2009
- Astudillo-Defru et al. 2015, A&A 575, A119
- Astudillo-Defru et al. 2017, A&A 602, A88
- Ayers et al. 1980

**B**

- Bailer-Jones & Kreidberg 2026, A&A 708
- Bains et al. 2021
- Balsalobre-Ruza et al. 2025
- Baluev & Beauge 2014, MNRAS 439, 673
- Baraffe et al. 1998
- Bardalez Gagliuffi et al. 2025, ApJL 988, L18
- Barkaoui et al. 2024
- Barnes et al. 2023
- Barros et al. 2023, A&A 673, A4
- Basant et al. 2025, arXiv:2503.08095
- Batygin & Brown 2016, AJ 151, 22
- Batygin et al. 2019
- Bauer et al. 2020
- Beard et al. 2022, ApJ 936, 55
- Beard et al. 2024
- Beard et al. 2025, AJ 170, 279
- Beatty et al. 2005
- Beck & Giles 2005
- Becker et al. 2024
- Beichman et al. 2025
- Ben-Jaffel & Ballester 2014, ApJ 785, L30
- Bendahan-West et al. 2026, MNRAS 546
- Benedict et al. 1999
- Benedict et al. 2016
- Benedict & McArthur 2020
- Benedict et al. 2023, arXiv:2305.11753
- Benest & Duvent 1995
- Bennett et al. 2014
- Berdinas et al. 2016
- Bertini et al. 2023, A&A 671, L2
- Beuzit et al. 2004, A&A 425 997
- Blanco-Pozo et al. 2023
- Bogat et al. 2025, AJ 170, 225
- Boisse et al. 2012
- Bonfils et al. 2011
- Bonfils et al. 2013, A&A 556, A110
- Bonfils et al. 2018, A&A 618, A142
- Bonomo et al. 2026
- Bonsor et al. 2013
- Bortle et al. 2021, AJ 161, 230
- Boulkaboul et al. 2026
- Bourrier et al. 2018, A&A 619, A1
- Bowens-Rubin et al. 2023, AJ 166, 260
- Boyajian et al. 2013, ApJ 771, 40
- Brady et al. 2024, AJ 168, 67
- Brandt et al. 2019
- Brandt 2021, ApJS 254, 42
- Brewer et al. 2016, ApJS 225, 32
- Brewer et al. 2023
- Brown & Schaller 2007, Science 316
- Brown & Batygin 2021, AJ 162, 219
- Brown et al. 2022
- Brown et al. 2024, arXiv:2401.17977
- Brown et al. 2026
- Buczko & Rajczy 1989
- Burgasser 2007, ApJ 658, 617
- Burgasser et al. 2010
- Butler et al. 2015
- Butler et al. 2017, AJ 153, 208

**C**

- Cadieux et al. 2022, AJ 164 96
- Cadieux et al. 2025
- Capistrant et al. 2024
- Carmona et al. 2025, A&A 700, A222
- Casagrande et al. 2011, A&A 530, A138
- Charpentier et al. 2026
- Che et al. 2011, ApJ 732, 68
- Chen & Kipping 2018
- Chen et al. 2022, AJ 163, 288
- Cheng et al. 2025, Nature 641, 866
- Cifuentes et al. 2020, A&A 642, A115
- Cifuentes et al. 2025
- Cloutier et al. 2019
- Collier et al. 2026
- Conzo et al. 2026
- Cortes-Contreras et al. 2017
- Cortes-Zuleta et al. 2023
- Cortes-Zuleta et al. 2025, A&A 693, A164
- Courcol et al. 2015, A&A 581, A38
- Crida et al. 2018
- Croll et al. 2007
- Cumming et al. 1999
- Curiel et al. 2020, AJ 160, 97
- Curiel et al. 2022, AJ 164, 93

**D**

- D'Antona & Mazzitelli 1997
- Dai et al. 2023
- Dai et al. 2024
- Dalal et al. 2024
- Dalba et al. 2021
- Damasso et al. 2020
- Damasso et al. 2022
- De Furio et al. 2025, ApJ 990, L63
- De Rosa et al. 2019, AJ 158, 225
- Debes et al. 2025, AJ 170, 123
- Deitrick et al. 2015, ApJ 798, 46
- Delfosse et al. 1999, A&A 344, 897
- Delrez et al. 2021
- Demangeon et al. 2021
- Denis et al. 2025
- Deslieres et al. 2025, AJ 169, 182
- Desort et al. 2009, A&A 506, 1469
- Dholakia et al. 2024
- Di Nezio et al. 2021
- Diaz et al. 2016, A&A 585, A134
- DiTomasso et al. 2025, ApJ 979, 214
- Dodson-Robinson et al. 2022, arXiv:2201.13342
- Domingos et al. 2006
- Donati et al. 2023
- Donati et al. 2025
- Dreizler et al. 2020, MNRAS 493, 536
- Dreizler et al. 2024, A&A 684, A117
- Dumusque et al. 2011
- Dunstone et al. 2008
- Dunton & Jodwalis 1988
- Dupuy & Liu 2012, ApJS 201, 19
- Dupuy & Kraus 2013, Science 341, 1492
- Dupuy & Liu 2017, ApJS 231, 15
- Dupuy et al. 2020
- Dupuy et al. 2023, MNRAS 519, 1688
- Duquennoy & Mayor 1991, A&A 248, 485

**E**

- Edwards 1976, AJ 81, 245
- Eggenberger et al. 2004, A&A 417, 235
- Eggenberger et al. 2007, A&A 474 273
- El-Badry et al. 2021, MNRAS 506, 2269
- Elliott et al. 2024
- Endl et al. 2000, A&A 362, 585
- Endl et al. 2016, ApJ 818, 34
- Endl et al. 2022
- Esmer & Daylan 2025, AJ 170, 322

**F**

- Faherty et al. 2024, Nature 628, 511
- Fan et al. 2019
- Faria et al. 2022, A&A 658
- Farihi et al. 2011
- Farihi et al. 2013, MNRAS 430, 652
- Feiden & Chaboyer 2014
- Feigelson et al. 2006, ApJ 649, L29
- Feng et al. 2017, A&A 605, A103
- Feng et al. 2019, ApJS 242, 25
- Feng et al. 2020, ApJS 246, 11
- Feng et al. 2022, ApJS 262, 21
- Feng et al. 2025, MNRAS 539, 3180
- Feroz & Hobson 2014, MNRAS 437, 3540
- Figueira et al. 2025, A&A 700, A174
- Filippazzo et al. 2015, ApJ 810, 158
- Fischer et al. 2014
- Flores et al. 2018
- Fouque et al. 2018, MNRAS 475, 1960
- Fox & Wiegert 2021
- Frensch et al. 2023
- Fuhrmann et al. 2005, MNRAS 361, 803
- Fuhrmann 2008, MNRAS 384, 173
- Fuhrmann et al. 2014, MNRAS 437, 2303
- Fuhrmann et al. 2016, MNRAS 459, 1682
- Fulton et al. 2015
- Fulton et al. 2016, ApJ 830, 46

**G**

- Gagne et al. 2016, ApJ 822, 40
- Gaia Collaboration, Arenou et al. 2023, A&A 674, A34
- Gaia Collaboration, Creevey et al. 2023, A&A 674, A26
- Gaia Collaboration, Vallenari et al. 2023, A&A 674, A1
- Gaidos et al. 2014, MNRAS 443, 2561
- Garcia-Alvarez et al. 2003, A&A 402, 1073
- Gauza et al. 2012, MNRAS 427, 2457
- Gauza et al. 2015, ApJ 804, 96
- Gebek & Oza 2020, MNRAS 497, 5271
- Geider et al. 1986
- Gentile Fusillo et al. 2021, MNRAS 508, 3877
- Giacalone et al. 2022
- Gianninas et al. 2011, ApJ 743, 138
- Gies et al. 2008, arXiv:0806.3473
- Gies et al. 2020, ApJ 902, 25
- Gillon et al. 2017, Nature 542
- Giovinazzi et al. 2025, AJ 170, 52
- Giovinazzi et al. 2026
- Gizis et al. 2000, MNRAS 311, 385
- Glebocki & Stawikowski 1995
- Goffo et al. 2023
- Goffo et al. 2024
- Golimowski et al. 2004
- Golovin et al. 2023, A&A 670, A19
- Gonzalez-Alvarez et al. 2020, A&A 637, A93
- Gonzalez-Alvarez et al. 2021
- Gonzalez-Alvarez et al. 2023, A&A 675, A141
- Gonzalez-Payo et al. 2024, A&A 689, A302
- Gorrini et al. 2023
- Gozdziewski & Migaszewski 2006
- Grandjean et al. 2021, A&A 650, A39
- Gratton et al. 2024, A&A 685, A119
- Gray et al. 2003, AJ 126, 2048
- Gray et al. 2006, AJ 132, 161
- Gray & Corbally 2009
- Greklek-McKeon et al. 2025
- Greklek-McKeon et al. 2026
- Griffin & Fuhrmann 2013, MNRAS 430, 1390
- Grundahl et al. 2017, ApJ 836, 142
- Guimaraes & Valio 2018, AJ 156, 50
- Gullikson et al. 2015, ApJ 815, 62
- Gupta et al. 2025

**H**

- Hacker et al. 2026
- Halbwachs et al. 2000, A&A 355, 581
- Halbwachs et al. 2023
- Han & Kain 1996
- Han et al. 2018, ApJ 868, 53
- Hancke et al. 2018
- Hara et al. 2020, A&A 636, L6
- Harada et al. 2024
- Harada et al. 2025
- Hardegree-Ullman et al. 2023, AJ 165, 267
- Harrington et al. 1981
- Hartogh et al. 2026
- Haswell et al. 2012
- Hatzes et al. 2022
- Hawco et al. 2020
- Hawthorn et al. 2023, MNRAS 520, 3649
- Heller & Hippke 2024
- Henry et al. 1999, ApJ 512
- Hirsch et al. 2021, AJ 161, 134
- Hobson et al. 2024
- Hoeijmakers et al. 2020, A&A 641, A123
- Holberg et al. 2016, MNRAS 462, 2295
- Hoppe et al. 2024
- Hord et al. 2024
- Horrobin & Rein 2019
- Houdebine et al. 2019, AJ 158, 56
- Houk & Cowley 1975
- Howard & Fulton 2016
- Hoy et al. 2026, Nature 655, 865
- Huang et al. 2025
- Hummel et al. 1998, AJ 116, 2536
- Hurt et al. 2022, AJ 163, 218

**I**

- Inghels et al. 2026
- Izmailov 2019, Astron. Lett. 45, 30

**J**

- Jiang & Tremaine 2010
- Jofré et al. 2015
- Johnson & Wright 1983, ApJS 53 643
- Johnson et al. 2000
- Justesen & Albrecht 2019, A&A 625 A59

**K**

- Kalomeni & Yakut 2025, MNRAS 541, 2553
- Kaminski et al. 2025
- Kane et al. 2024
- Kasting et al. 1993
- Keenan & McNeil 1989
- Kemmer et al. 2020, A&A 642, A236
- Kennedy et al. 2015, MNRAS 449, 3121
- Kenworthy & Mamajek 2015
- Kerr et al. 2022, ApJ 941, 143
- Kervella et al. 2016, A&A 593, A127
- Kervella et al. 2017, A&A 597, A137
- Kervella et al. 2019, A&A 623, A72
- Kervella et al. 2022, A&A 657, A7
- Kiefer et al. 2024
- Kiefer et al. 2025, A&A 702, A77
- King et al. 2010, A&A 510, A99
- Kipping et al. 2015
- Kipping 2020, ApJL 900, L44
- Kipping et al. 2022
- Kipping & Yahalomi 2023
- Kipping & Teachey 2024, arXiv:2401.10333
- Kirkpatrick et al. 2021, ApJS 253, 7
- Kislyakova et al. 2016, MNRAS 461, 988
- Kiyaeva et al. 2015
- Klaassen et al. 2025, RNAAS 9, 326
- Kochukhov & Bagnulo 2006, A&A 450, 763
- Kochukhov & Shulyak 2019, ApJ 873, 69
- Konopacky et al. 2010
- Kopp & Lean 2011
- Kopparapu et al. 2013, ApJ 765, 131
- Kopparapu et al. 2014
- Kral et al. 2026
- Kreidberg et al. 2019, ApJL 877, L15
- Kroft et al. 2026
- Kulmala & Laaksonen 1990
- Kunimoto et al. 2025
- Kurster et al. 1999
- Kuzuhara et al. 2013

**L**

- Lacedelli et al. 2025
- Lacedelli et al. 2026
- Lagrange et al. 2025, arXiv:2501.10488
- Laliotis et al. 2023, AJ 165, 176
- Lamontagne et al. 2026, A&A 706, A278
- Landman et al. 2024
- Latham et al. 2002, AJ 124, 1144
- Lavie et al. 2023, A&A 673, A69
- Lazzoni et al. 2020
- Lee et al. 2025
- Lee et al. 2026
- Leggett et al. 2014, ApJ 780, 62
- Leggett & Tremblin 2026, arXiv:2606.04294
- Lepine & Bongiorno 2007
- Lepine et al. 2013, AJ 145 102
- Li et al. 2016
- Li et al. 2024, AJ 167, 155
- Liebing et al. 2024
- Lillo-Box et al. 2020, A&A 642, A121
- Limbach et al. 2021
- Limbach et al. 2024
- Limbach et al. 2025, ApJL 984, L28
- Limoges et al. 2015, ApJS 219, 19
- Lindgren et al. 2016
- Littler et al. 1985, Science 227
- Littler et al. 1986
- Liu et al. 2007, ApJ 660, 1507
- Liu et al. 2011, ApJ 740, 108
- Liu et al. 2012, ApJ 758, 57
- Llop-Sayson et al. 2026
- Loth & Bidelman 1998
- Lovell et al. 2022, MNRAS 517, 2546
- Lowrance et al. 2002, ApJ 572, L79
- Luck 2017, AJ 153, 21
- Luhman et al. 2007, ApJ 654, 570
- Luhman et al. 2012
- Luque et al. 2019, A&A 628, A39
- Luque & Palle 2022

**M**

- MacDonald et al. 2026
- Mahadevan et al. 2021
- Makarov et al. 2021, RNAAS 5, 108
- Maldonado et al. 2020, A&A 644, A68
- Maldonado et al. 2021, A&A 651, A93
- Malkov et al. 2012
- Mallorquin et al. 2023, A&A 680 A76
- Mallorquín et al. 2024
- Malogolovets et al. 2007, arXiv:0707.2193
- Mamajek et al. 2010, AJ 139, 919
- Mann et al. 2015, ApJ 804, 64
- Mann et al. 2019, ApJ 871, 63
- Manske et al. 2005
- Maqueo Chew et al. 2026
- Marcussen & Albrecht 2023, AJ 165, 266
- Marfil et al. 2021, A&A 656, A162
- Markager & Sand-Jensen 1992
- Marschall & Proctor 2004
- Mason et al. 1999
- Mason et al. 2001, AJ 122, 3466
- Matthews et al. 2026
- Matvienko et al. 2015, Astron. Lett. 41, 43
- Maxted et al. 2007, MNRAS 376, 919
- Mayor et al. 2004
- McArthur et al. 2010, ApJ 715, 1203
- McArthur et al. 2014, ApJ 795, 41
- McCarthy et al. 1985, ApJ 290, L9
- McCaughrean et al. 2004
- McDonald et al. 2017, MNRAS 471, 770
- Meschiari et al. 2011
- Messina et al. 2015
- Metcalfe et al. 2012, ApJL 748, L10
- Michel & Mugrauer 2021
- Michel & Mugrauer 2023
- Michel & Mugrauer 2024, MNRAS 527, 3183
- Mignon et al. 2023
- Mignon et al. 2024, A&A 689, A32
- Mignon et al. 2025
- Miyazaki et al. 2018
- Monro et al. 2018
- Montet et al. 2015, ApJL 813, L11
- Morales et al. 2009, ApJ 691, 1400
- Morales et al. 2025, A&A 700, A242
- Morgan et al. 1943
- Morgan & Keenan 1973
- Morgan et al. 2026
- Morley et al. 2012
- Moutou et al. 2024
- Moutou et al. 2025
- Moutou et al. 2026
- Mugrauer et al. 2006, AN 327, 321
- Mugrauer & Neuhauser 2007, arXiv:0710.5918
- Mugrauer 2019, MNRAS 490, 5088
- Mugrauer & Michel 2020
- Mullally et al. 2025, AJ 171, 144
- Muller et al. 2024
- Murgas et al. 2024
- Muterspaugh et al. 2010, arXiv:1010.4048

**N**

- Naef et al. 2001, A&A 375 205
- Nagel et al. 2019
- Nagel et al. 2026
- Naponiello et al. 2025
- Nari et al. 2025, A&A 693, A297
- Nari et al. 2026, A&A 709, A123
- Newton et al. 2014, AJ 147 20
- Noriega Gardea et al. 2021

**O**

- O'Brien et al. 2024, MNRAS 527, 8687
- Ould-Elhkim et al. 2025
- Ould-Elhkim et al. 2026, A&A 705, A234
- Overmann et al. 1992
- Oza et al. 2019, ApJ 885, 168
- Oza et al. 2024
- Oza et al. 2025

**P**

- Paegert et al. 2021
- Palle et al. 2023, A&A 678, A80
- Pappert et al. 2025
- Parc et al. 2026, A&A 708 A81
- Parra et al. 2015
- Pasquini et al. 1991
- Pass et al. 2023, AJ 166, 11
- Pecaut & Mamajek 2013, ApJS 208, 9
- Perger et al. 2017, A&A 608, A63
- Perger et al. 2019, A&A 624, A123
- Perrier & Mariotti 1987, ApJ 312
- Perrier et al. 2003
- Philipot et al. 2023, A&A 678, A107
- Pinamonti et al. 2018
- Pinamonti et al. 2022, A&A 664, A65
- Pinamonti et al. 2023
- Pinfield et al. 2006, MNRAS 368, 1281
- Polanski et al. 2024
- Poulsen et al. 2026, AJ 171, 183
- Poultourtzidis et al. 2026
- Pourbaix et al. 2002, A&A 382
- Pourbaix et al. 2004, A&A 424, 727
- Pourbaix & Boffin 2016
- Pozuelos et al. 2020
- Pulley et al. 2022, MNRAS 514, 5725
- Pulley et al. 2025, arXiv:2507.06748

**Q**

- Quirrenbach et al. 2022, A&A 663, A48

**R**

- Ramm et al. 2021, MNRAS 502, 2793
- Rattanamala et al. 2023, MNRAS 523, 5086
- Rau et al. 1973
- Raven et al. 2000
- Reffert & Quirrenbach 2011, A&A 527, A140
- Reichert et al. 2019, A&A 625, A22
- Reid et al. 1995, AJ 110, 1838
- Reid et al. 2004
- Reiners et al. 2018, A&A 612, A49
- Rescigno et al. 2024
- Rescigno et al. 2026, MNRAS 550
- Reyle et al. 2021, A&A 650, A201
- Ribas et al. 2016
- Ribas et al. 2017, A&A 603, A58
- Ribas et al. 2023, A&A 670, A139
- Rich et al. 2016
- Riedel et al. 2018, AJ 156, 49
- Rivera et al. 2010, ApJ 708, 1492
- Robertson & Mahadevan 2014, ApJL 793, L24
- Robertson et al. 2015, ApJL 805, L22
- Robertson et al. 2026
- Rogers et al. 2024, MNRAS 527, 977
- Rojas-Ayala et al. 2012, ApJ 748 93
- Roell et al. 2011
- Romanenko et al. 2025
- Rosenthal et al. 2021, ApJS 255, 8
- Rothermich et al. 2024, AJ 167, 253
- Ruggieri et al. 2026
- Runcie et al. 2008

**S**

- Sahlmann et al. 2011, A&A 525, A95
- Sahlmann et al. 2013, A&A 556, A133
- Sahlmann et al. 2015, A&A 579, A61
- Sanghi et al. 2023, ApJ 959, 63
- Sanghi et al. 2025
- Sanghi et al. 2026, AJ 172, 115
- Santos et al. 2005, A&A 437, 1127
- Saumon et al. 2006
- Saumon & Marley 2008
- Schmerling et al. 2025, A&A 699, A185
- Schneider et al. 2011, A&A 532, A79
- Scholz et al. 2003
- Schönrich et al. 2010, MNRAS 403, 1829
- Schweitzer et al. 2019, A&A 625, A68
- Scott et al. 2026
- Sebastian et al. 2021, A&A 645, A100
- Seidel 2019, A&A 623, A166
- Seidel et al. 2021, arXiv:2107.09530
- Seidel et al. 2023, arXiv:2303.09376
- Serrano Bell et al. 2026
- Shkolnik et al. 2009
- Shporer et al. 2020
- Signor et al. 2026
- Silverstein et al. 2024
- Simpson et al. 2022, AJ 163, 215
- Sion et al. 2009, AJ 138, 1681
- Siraj et al. 2025
- Snellen et al. 2014
- Soederhjelm 1999, A&A 341, 121
- Sokov et al. 2012
- Sousa et al. 2008
- Southworth 2011, MNRAS 417, 2166
- Sperauskas et al. 2019, A&A 626, A31
- Srivastava et al. 2026
- Stalport et al. 2023
- Standing et al. 2026
- Stassun et al. 2017
- Stassun et al. 2019, AJ 158, 138
- Stefanov et al. 2025, arXiv:2503.08405
- Stefánsson et al. 2023
- Stefansson et al. 2025, AJ 169, 107
- Stephenson 1986, AJ 92, 139
- Stock et al. 2020, A&A 636, A119
- Stone et al. 2016
- Stoeva et al. 2026
- Strassmeier & Rice 2000
- Suárez Mascareño et al. 2023
- Suárez Mascareño et al. 2025, A&A 700, A11
- Subasavage et al. 2017, AJ 154, 32
- Sudarsky et al. 2000, ApJ 538, 885
- Sutlieff et al. 2026

**T**

- Taiz & Zeiger 2010
- Tal-Or et al. 2019
- Tan et al. 2013
- Teachey & Kipping 2018, AJ 155, 36
- Terrien et al. 2015, ApJS 220 16
- Terry et al. 2025, AJ 169, 131
- Tey et al. 2024
- Thimijan & Heins 1983
- Timmermans et al. 2024, A&A 687 A48
- Tokovinin 2018, ApJS 235, 6
- Tokovinin 2020, AJ 159, 265
- Tokovinin et al. 2022, AJ 164, 58
- Tokovinin et al. 2024, AJ 168, 28
- Toledo-Padron et al. 2021, A&A 648, A20
- Torres & Ribas 2002, ApJ 567, 1140
- Torres et al. 2015, ApJ 807, 26
- Torres et al. 2022, ApJ 941, 8
- Trifonov et al. 2018
- Tsai et al. 2023
- Tschudi 2026, arXiv:2607.23781
- Tuomi et al. 2013, A&A 549, A48
- Tuomi et al. 2014, MNRAS 440, L1
- Tuomi et al. 2019, arXiv:1906.04644
- Turner et al. 2026

**U**

- Udry et al. 2019
- Unger et al. 2021
- Unni et al. 2025, arXiv:2504.03974

**V**

- Van Zandt et al. 2026
- Vanderburg et al. 2020
- Venner et al. 2026
- Vrba et al. 2004
- Vrijmoet et al. 2026, AJ 171, 186

**W**

- Wagner et al. 2021
- Wahhaj et al. 2011, ApJ 729, 139
- Waite & Sack 2010
- Wang et al. 2016
- Weisserman et al. 2026, arXiv:2604.07447
- Wenger et al. 2000, A&AS 143, 9
- West et al. 2015, ApJ 812, 3
- Wiegert et al. 2016, arXiv:1607.03038
- Wilson et al. 2006
- Wilson et al. 2016
- Winters et al. 2019, AJ 157 216
- Wittenmyer et al. 2013
- Wittrock et al. 2023
- Wolf et al. 2018, A&A 620, A72
- Wright et al. 2007, ApJ 657, 533
- Wright et al. 2013, AJ 145, 84
- Wright et al. 2016
- Wu et al. 2026, AJ 171, 189

**X**

- Xiao et al. 2023
- Xiao et al. 2024
- Xiao et al. 2026
- Xuan et al. 2024, ApJ 962, 10

**Y**

- Yahalomi et al. 2024, MNRAS 527, 620
- Yalçinkaya et al. 2025
- Yang & Gao 2012
- Yao et al. 2025

**Z**

- Zeng et al. 2022, AJ 164, 188
- Zhao et al. 2026
- Zhou et al. 2020
- Zorec & Royer 2012, A&A 537, A120
- Zucker & Mazeh 2001
- Zúñiga-Fernández et al. 2025, arXiv:2508.14176
