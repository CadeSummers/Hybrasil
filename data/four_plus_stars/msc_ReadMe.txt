J/ApJS/235/6   Updated Multiple Star Catalog (MSC): Dec 2023   (Tokovinin, 2018)
================================================================================
The updated Multiple Star Catalog.
    Tokovinin A.
   <Astrophys. J. Suppl. Ser., 235, 6 (2018)>
   =2018ApJS..235....6T
================================================================================
ADC_Keywords: Stars, double and multiple; Stars, masses; Spectral types;
              Photometry, infrared; Optical; Proper motions; Radial velocities;
              Parallaxes, trigonometric; Positional data
Keywords: binaries: close ; binaries: general ; binaries: visual ; Catalog

Abstract:
    The catalog of hierarchical stellar systems with three or more
    components is an update of the original 1997 version (Tokovinin,
    1997-1999, J/A+AS/124/75). For 2000 hierarchies, the new Multiple Star
    Catalog (MSC) provides distances, component masses and periods, and
    supplementary information (astrometry, photometry, identifiers,
    orbits, notes). The MSC content and format are explained, and its
    incompleteness and strong observational selection are stressed.
    Nevertheless, the MSC can be used for statistical studies and is a
    valuable source for planning observations of multiple stars. Rare
    classes of stellar hierarchies found in the MSC (with six or seven
    components, extremely eccentric orbits, planar and possibly resonant
    orbits, hosting planets) are briefly presented. High-order hierarchies
    have smaller velocity dispersion compared to triples and are often
    associated with moving groups. The paper concludes with an analysis of
    the ratio of periods and separations between inner and outer
    subsystems. In wide hierarchies, the ratio of semimajor axes,
    estimated statistically, is distributed between 3 and 300, with no
    evidence of dynamically unstable systems.

Description:
    This catalogue is an updated version (December 2023) downloaded at:
    http://www.ctio.noirlab.edu/~atokovin/stars/newmsc-20240101.tar.gz

    Data on 5719 stellar systems of multiplicity 3 to 7 are given. These
    systems are physical and, with little exception, hierarchical. For
    grades 4 (N=2669) and 5 (N=2241), orbital periods are known or
    estimated, while for 809 systems of grade 3 some periods remain
    unknown. Additionally, 760 systems of grades 1 and 2 (refuted or
    unconfirmed hierarchies) are given for reference. A hierarchical
    system consists of several "elementary binaries". For each binary, the
    orbital period and separation are given, as well as components'
    magnitudes, spectral types, and estimated masses. Orbital elements are
    also given when available.

    The present version of the catalogue is the latest update of the
    original 1997 publication (Tokovinin, 1997-1999, J/A+AS/124/75) and
    its continuation in 2018ApJS..235....6T (this catalog).

File Summary:
--------------------------------------------------------------------------------
 FileName    Lrecl  Records   Explanations
--------------------------------------------------------------------------------
ReadMe          80        .   This file
catalog.dat    195    12484   Components table (table 1; comp)
systems.dat    134    14639   Systems table (table 2; sys)
orbits.dat     138     4608   Orbit table (table 4; orb)
notes.dat      111     8858   Notes table; updated by the author
                               (table 5; notes)
--------------------------------------------------------------------------------

See also:
 B/wds : The Washington Visual Double Star Catalog (Mason+ 2001-2014)
 B/sb9 : SB9: 9th Catalogue of Spectroscopic Binary Orbits (Pourbaix+ 2004-2014)
 I/311 : Hipparcos, the New Reduction (van Leeuwen, 2007)
 I/345 : Gaia DR2 (Gaia Collaboration, 2018)
 I/350 : Gaia EDR3 (Gaia Collaboration, 2020)
 I/355 : Gaia DR3 Part 1. Main source (Gaia Collaboration, 2022)
 I/357 : Gaia DR3 Part 3. Non-single stars (Gaia Collaboration, 2022)
 J/A+AS/124/75    : Multiple star catalogue (MSC) (Tokovinin 1997-1999)
 J/A+A/384/1030   : Orientation of orbits in triple stars (Sterzik+, 2002)
 J/A+A/450/681    : Companions to close spectroscopic bin. (Tokovinin+, 2006)
 J/MNRAS/389/925  : Triple and quadruple stars (Tokovinin, 2008)
 J/MNRAS/405/1930 : Period changes of EA-, EB- & EW-types binaries (Liao+, 2010)
 J/AJ/140/1657    : PHASES diff. astrometry data. V. (Muterspaugh+, 2010)
 J/ApJS/190/1     : A survey of stellar families (Raghavan+, 2010)
 J/AJ/139/743     : Speckle interferometry in 2008-09 (Tokovinin+, 2010)
 J/A+A/544/L3     : The double eclipsing binary CzeV343 photom. (Cagas+, 2012)
 J/AJ/144/64      : Solar neighborhood. XXVIII. Companions (Dieterich+, 2012)
 J/A+A/542/A78    : BVRI light curves and RV curves of 65 UMa (Zasche+, 2012)
 J/ApJS/208/9     : Intrinsic colors & temperatures of PMS stars (Pecaut+, 2013)
 J/A+A/559/A17    : Barycentric RVs of Gl 586A (Strassmeier+, 2013)
 J/MNRAS/437/1216 : VAST Survey. A-type stars multiplicity (De Rosa+, 2014)
 J/ApJ/790/146    : Planets in Kepler's multi-transiting syst. (Fabrycky+, 2014)
 J/AJ/148/62      : Spectroscopy of HD 5980 (Koenigsberger+, 2014)
 J/ApJS/215/15    : SMaSH+: observations and companion detection (Sana+, 2014)
 J/AJ/147/86      : From binaries to multiples. I. FG-67 (Tokovinin, 2014)
 J/AJ/149/195     : The quadruple system HD 91962 spectrosc. (Tokovinin+, 2015)
 J/MNRAS/455/4136 : Kepler triples (Borkovits+, 2016)
 J/MNRAS/456/2070 : Eccentricity distribution of wide bin. (Tokovinin+, 2016)
 J/ApJ/844/103    : Orbit alignment in triple stars (Tokovinin, 2017)
 J/ApJ/838/54     : Accurate astrom. & RVs of 4 mult. syst. (Tokovinin+, 2017)
 http://www.ctio.noao.edu/~atokovin/stars/ : Multiple Star Catalog (MSC) home

Byte-by-byte Description of file: catalog.dat
--------------------------------------------------------------------------------
   Bytes Format Units   Label     Explanations
--------------------------------------------------------------------------------
   1- 10  A10   ---     ID        WDS code (HHMMm+DDMM; J2000) (G1)
  12- 21  F10.6 deg     RAdeg     Right Ascension in decimal degrees (J2000)
  23- 32  F10.6 deg     DEdeg     Declination in decimal degrees (J2000)
  36- 41  F6.2  mas     plx       [-1.4/742.1] Parallax
  43- 46  A4    ---   r_plx       Reference code for plx (1)
  48- 54  F7.1 mas/yr   pmRA      [-3776/4165] Proper motion in RA
  56- 62  F7.1 mas/yr   pmDE      [-3422/3250] Proper motion in Dec
  64- 69  F6.1 km/s     RV        [-291/1129]? Radial velocity
      72  A1   ---    m_ID        Component label
  74- 80  F7.1 arcsec   Sep       [0.1/31619]?=0 Separation from main component
  82- 89  A8   ---      SpT       MK spectral type
  91- 96  I6   ---      HIP       [25/120005]?=0 Hipparcos number
  98-103  I6   ---      HD        [9/358806]?=0 HD number
 105-109  F5.2 mag      Bmag      [0.1/22]?=0 B-band magnitude
 111-115  F5.2 mag      Vmag      [-0.01/25]?=0 V-band magnitude
 117-121  F5.2 mag      Imag      [-1.1/19]?=0 I_C_-band magnitude
 123-127  F5.2 mag      Jmag      [-2.3/18.3]?=0 J-band magnitude
 129-133  F5.2 mag      Hmag      [-3.3/18.2]?=0 H-band magnitude
 135-139  F5.2 mag      Kmag      [-3.6/18.8]?=0 K-band magnitude
     142  I1   ---      Nc        [0/8] Number of components
     144  I1   ---      Gr        [0/5] Grade (2)
 146-195  A50  ---      OID       Other identifiers
--------------------------------------------------------------------------------
Note (1): Reference as follows:
    HIP = trigonometric Hipparcos (I/239) (156+34+3 occurrences)
   Gaia = Gaia DR1 (I/337) parallax (15 occurrences)
    DR2 = Gaia DR2 (I/345) parallax (1168 occurrences)
    DR3 = Gaia DR3 (I/355) or eDR3 (I/350) parallax (9825 occurrences)
   DR3N = Gaia DR3+NSS parallax (673 occurrences)
    ptm = photometric parallax estimate (36 occurrences)
    dyn = dynamical from visual orbit (131 occurrences)
    orb = orbital for visual/SB2 orbit (14 occurrences)
    bib = taken from literature (70 occurrences)
  guess = crude guess (25 occurrences)
Note (2): Grades have the following meaning:
      0 = no grade or secondary component;
      1 = not a triple system;
      2 = uncertain triple or very wide (period >2Myr);
      3 = some undefined period or poorly known distance;
      4 = at least triple, all periods defined;
      5 = At least one orbit, distance known within 10%.
--------------------------------------------------------------------------------

Byte-by-byte Description of file: systems.dat
--------------------------------------------------------------------------------
   Bytes Format Units   Label     Explanations
--------------------------------------------------------------------------------
   1- 10  A10   ---     ID        WDS code (HHMMm+DDMM; J2000) (G1)
  12- 14  A3    ---     Prim      Primary component label
  16- 18  A3    ---     Sec       Secondary component label
  20- 22  A3    ---     Parent    Parent label (1)
  24- 31  A8    ---     Type      Observing technique/status (2)
  33- 42  F10.4 ---     Per       [0.005/15194]?=0 Orbital period
      44  A1    ---   x_Per       Unit of Per (3)
  46- 53  F8.3  ---     Sep       [0.001/8925]?=0 Separation or semimajor axis
      55  A1    ---   x_Sep       Units of Sep
  57- 61  F5.1  deg     PA        [0/888]?=-1 Position angle
  63- 67  F5.2  mag     Vmag1     [-0.01/24.4] V-magnitude of the primary
  69- 73  A5    ---     SpT1      Spectral type of the primary
  75- 79  F5.2  mag     Vmag2     [0.7/25.6]?=0 V-magnitude of the secondary
  81- 85  A5    ---     SpT2      Spectral type of the secondary
  87- 92  F6.2  Msun    Mass1     [0.02/140.6]?=0 Mass of the primary
      94  A1    ---   f_Mass1     Mass estimation code for primary (4)
  97-101  F5.2  Msun    Mass2     [0.01/63]?=0 Mass of the secondary
     103  A1    ---   f_Mass2     Mass estimation code for secondary (4)
 105-134  A30   ---     Comm      Comment (may include OID and bibcodes)
--------------------------------------------------------------------------------
Note (1): The "Parent" points to a component identifier in a higher-level
          system to which the current system belongs and thus codes the
          hierarchy by reference. Two special symbols are used:
    * = root (system at the hiest hierarchical level);
    t = "Trapezium"-type, non-hierarchical.
Note (2): Discovery/observing status codes, comma-separated:
    c = wide, possibly C.P.M. system;
    C = C.P.M. system (sep.>3");
    The following small letters give the criteria used to establish CPM:
        h = hypothetical parallax,
        r = radial velocities,
        p = photometric distances or common parallax,
        m = common proper motion;
    v = close visual or interferometric system (sep.<3");
    V = visual system with computed orbit;
    a = astrometric system (perturbed motion suspected);
    A = astrometric orbit for invisible companion is computed;
    s = possibly spectroscopic system (var. RV or composite sp.);
    S1,S2 = spectroscopic system with computed orbit, single- or double-lined;
    o = occultation binary;
    E = eclipsing binary with known period;
    E* = eclipse time variation;
    e = eclipsing binary, period not known;
    X = optical (qualifiers h,r,m c indicate why optical).
Note (3): Unit as follows:
    d = days;
    y = years;
    k = kiloyears;
    M = Megayears.
Note (4): Code as follows:
    r = given in the original publication
    v = estimated from absolute magnitude
    a = estimated from spectral type or B-V color index from Allen's tables
    s = sum of masses for the sub-system(s)
    q = estimated from primary mass and mass ratio of SB2
    m = minimum secondary mass for SB1
    k = estimated from absolute K or H magnitude
--------------------------------------------------------------------------------

Byte-by-byte Description of file: orbits.dat
--------------------------------------------------------------------------------
   Bytes Format Units   Label   Explanations
--------------------------------------------------------------------------------
   1- 10  A10   ---     ID      WDS code (HHMMm+DDMM; J2000) (G1)
  12- 19  A8    ---     Syst    Primary,Secondary
  22- 32  F11.4 ---     Per     [0/830370]?=-1 Period
  34- 43  F10.4 ---     T       [-499/88500]?=0 Periastron epoch; Besselian year
                                or JD-2400000
  46- 50  F5.3  ---     e       [0.001/8.1]?=0 Eccentricity
  52- 59  F8.4  arcsec  a       [0.0001/205.1]?=0 Semimajor axis
  61- 66  F6.2  deg     Node    [-3.7/360]?=0 Position angle of ascending node
  68- 73  F6.2  deg     LongP   [-90/445]?=0 Longitude of periastron
  75- 80  F6.2  deg     Incl    [2.4/922]?=0 Inclination
  82- 87  F6.2  km/s    K1      [0.01/335]?=0 Primary semi-amplitude
  89- 94  F6.2  km/s    K2      [-25.2/435]?=0 Secondary semi-amplitude
  97-103  F7.2  km/s    V0      [-291/664]?=0 Center of mass velocity
     105  A1    ---     Flag    Component to which the node refers
     107  A1    ---   x_Per     [dy] Units of period (days or years)
 109-138  A30   --      Note    Note; may include bibcode
--------------------------------------------------------------------------------

Byte-by-byte Description of file: notes.dat
--------------------------------------------------------------------------------
   Bytes Format Units Label      Explanations
--------------------------------------------------------------------------------
   1- 10 A10    ---   ID         WDS code (HHMMm+DDMM; J2000) (G1)
  12- 91 A80    ---   Note       Text of the note
  93-111 A19    ---   BibCode    Bibcode of reference
--------------------------------------------------------------------------------

Global note:
Note (G1): This "WDS index" is sometimes different from the index given in
           the Washington Double Stars Catalog (B/wds).
           The systems are <PMSC JHHMMm+DDMM> in Simbad;
           see "PMSC" in the Dictionary of Nomenclature
--------------------------------------------------------------------------------

History:
    * From http://www.ctio.noao.edu/~atokovin/stars/newmsc.tgz
         -- May 2018 release
    * notes.dat and systems.dat tables have been updated by the author
         -- October 2018.
    * 01-Aug-2019: Updated version from the author with 10% more entries and
         some information added or revised
    * 08-Sep-2021: Updated version sent by the author with 1298
         additional systems
    * 08-Jan-2024: Last updated version sent by the author

Acknowledgements:
    Andrei Tokovinin <andrei.tokovinin {at} noirlab.edu>

References:
    Tokovinin A.A.  The MSC.   1997A&AS..124...75T   Cat. J/A+AS/124/75

================================================================================
(End)                    Prepared by [AAS], Emmanuelle Perret [CDS]  17-Aug-2018
