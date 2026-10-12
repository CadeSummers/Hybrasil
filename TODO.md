# TODO

Issues noticed while adding 55 Cnc g and drawing multi-star catalog systems
whole (23 September 2026). None of them was fixed in that change.

## Filters that do not span their tab (9 October 2026)

A sort through a tab's basic filter moves only the filter's columns. On 9 Oct 2026 a sort of Planetless 4+ Stars
(filter A:BL of A:BT) left BM:BT behind, and every row carried another star's periastron epoch, position, barycentre
and drawing status until `data/star_counts/realign_planetless_sort.py` put them back. Systems and Multi-stars were
sorted the same day and came through whole, because their filters span every column.

- [x] **Planetless 4+ Stars and Planets filters widened to every column** (9 Oct 2026, `data/star_counts/widen_filters.py`,
  workbook `hy-brasil-20261009-1334`): A:BT and A:AQ, sort order and every cell unchanged. A column added to
  either tab later must go inside the filter too.
- [ ] Check five solvent tabs the same way, and widen any whose filter stops short of used columns: Solvent
  Compatibility Matrix, Vehicle & Redox Requirements, Molecular Currency Assessment, Cosmic Occurrence, Liquid
  Range vs Pressure. Their filters cover only part of a 26-column grid.

## Brown dwarf / red dwarf watch list (7 October 2026)

A star fuses protium, or once did; a brown dwarf is a planet
(`docs/hybrasil-instructions.md` section 6). These objects sit at the
hydrogen-burning limit, about 0.075 M_sun and M7.5-L1, and were kept as stars
when the brown dwarfs were migrated to the planet tabs
(`data/star_counts/migrate_bds.py`). Watch them: a lithium test, a dynamical
mass, or the authors calling one a brown dwarf would make it a planet, and its
system's star count would drop.

- **TVLM 513-46546** (Systems, 0.07 M_sun, M8.5 V): a single host.
- **GJ 569 Ba** (Planetless, 0.07, M8.5 V); its partner Bb is a planet now.
- **GJ 9829 D** (Planetless, 0.1 M_sun but class L1).

Settled 9 Oct 2026 by a literature check (`data/star_counts/settle_watch_list.py`, S&P "WATCH LIST SETTLED BY THE
LITERATURE"):

- **GJ 310.1 Bb is a planet.** It is HD 72946 B, a brown dwarf of 72.4 +/- 1.6 M_Jup and type L5 (Maire et al.
  2020); on Planets round GJ 310.1 Ba.
- **GJ 275.2 Ab is rejected.** It rests on one preliminary 1981 astrometric orbit whose 0.94 yr period sits on the
  parallax's, and Gaia DR3 and two imaging surveys see nothing. It is on Rejected candidates now.
- **HR 1099 Bb is a star.** Its only paper (Tokovinin & Gorynya 2001) gives a minimum mass of 0.07 and types it M.
  Gaia DR3 (RUWE 1.03, constant RV) doubts the orbit itself.
- **GJ 747.2 Bb is a star.** It is hollow, with an assumed mass; nothing but Gaia's RUWE 5.3 for B detects it.

Possible brown dwarfs, flagged 9 Oct 2026 (`fill_missing_lum.py`). These are hollow companions whose assumed mass
(the typical-companion rule's, `infer.py`) is at or below the last mass the Pecaut & Mamajek dwarf sequence
tabulates: **L2V, 0.075 M_sun, log L -3.82**. That row is the baseline. Each takes that row's L, 1.51e-4 L_sun, as
a floor, which is an upper bound if it is a brown dwarf. They stay stars under section 6 for now (owner's decision):

- 2MASS J15472982-2755121 Cb 0.039, ADS 9982 Cb 0.033, 1 Hya Cb 0.039, GJ 3725 Cb 0.066;
- GJ 747.2 Bb 0.072, BD+37 1091 Bb 0.075, CD-52 2036 Bb 0.075.

Settled 7 Oct 2026 and off the list:

- **VHS J125601.92-125723.9 A and B are planets.** Dupuy et al. 2023 give
  74 +/- 4 M_Jup each and call them "possibly brown dwarfs"; no source says
  either fuses hydrogen, and section 6 files the undecided as planets. B is on
  Planets round A, A fills the host columns, the system has no star
  (`data/star_counts/migrate_vhs1256.py`).
- **ksi UMa Bb is a star.** Fuhrmann 2008 make it an ordinary M dwarf of
  0.14 M_sun at i ~ 15 deg; Fuhrmann et al. 2016 suggest a white dwarf from
  Ba's barium. Role, mass and inclination rewritten, barycentres and ksi UMa
  D's period re-derived (`data/star_counts/fix_ksi_uma_bb.py`).

Not on the list, but kept as stars for the same want of evidence: the hollow
companions 2MASS J15472982-2755121 Cb, ADS 9982 Cb, 1 Hya Cb, GJ 3725 Cb and
BD+37 1091 Bb. Their low masses are the typical-companion rule's assumption
(0.3 x the primary's, `data/four_plus_stars/infer.py`), not a measurement.

Found on the way, left alone: alf Gem AB's mass reads 4.93 M_sun against its
pair's 4.94 (A 2.76 + B 2.18), from before the migration; Castor's built-in
copies the cell. The Known within 100ly tab was not touched: its typed counts
(e.g. eps Ind A and HD 3651, 1 confirmed planet each) predate the brown dwarfs'
move to Planets.

## Viewer

- **In the Plotly viewer, a moon's orbit ellipse stays where its planet
  started.** The three.js viewer (the default) moves it with the planet since
  26 September 2026. See rule 5 in `docs/architecture/three-renderer.md`.
  - Plotly frames only update marker traces. Carrying the ellipse would mean
    either putting every moon orbit in every frame (the Solar System: 7 moons
    × 120 frames × 360 points) or restyling it per frame.
  - Either way, it has to go through `updateSceneVisibility()`'s cached
    geometry (`zoom-and-visibility.md`).
  - The trace already carries `meta.follows`, naming its planet.
  - **Solvent bands likewise** (three.js since 8 October 2026). A band's
    trace already carries `meta.body`, its star's marker label. Bands are
    meshes, and frames writing to them by index are how the torus bug
    happened, so any fix must keep the `test_system_switch.py` hazard tests
    meaningful.

- **The Plotly viewer throws a JavaScript error on every system switch.**
  `TypeError: Cannot read properties of undefined (reading '18')`, from
  `prepareFn` inside Plotly's animation code (`plotly-3.4.0.min.js`). Seen
  switching solar → alpha-centauri → 55-cancri → solar → trappist-1 with
  `--renderer plotly`. The code before the change throws the same error, so
  it is not new. The band flat-disc tests still pass through it.
  - The likely suspect is an `animate` call still pending against the
    previous system's traces. That is the same family as the torus-of-beads
    bug in `CLAUDE.md`, so read that section before touching it.
  - The three.js viewer does not throw.

## Unconfirmed-candidate search: finished 27 September 2026, follow-ups

The search is complete; see [`unconfirmed_search.md`](unconfirmed_search.md) §8 and
`data/unconfirmed_search/run2/`. What it left:

- **Confirmed-tab errors: the plainly wrong ones are fixed** (27 Sep 2026, run 3;
  `hy-brasil-20260927-1700`, S&P lines 5055-5182; records in `data/unconfirmed_search/run3/`).
  Nine refuted rows moved to Rejected, 20 orbit rows corrected, 7 distances resolved, 43 star
  rows added to Multi-stars (GJ 65 B and 61 Cyg B among them), six planets added, Gaia ids
  fixed. What is left from `unconfirmed_search.md` section 8.4 is the judgement calls:
  - ~~contested planets (26)~~ **done 28 Sep 2026** (run 5, `hy-brasil-20260928-1315`, S&P 5213-5272;
    `unconfirmed_search.md` §8.5): 11 moved to Unconfirmed as `ambiguous`, 15 kept with a flags note;
  - ~~brown dwarfs by true mass~~ (Feng 2022): HD 111232 c, HD 153557 d, GJ 676 A c stay on Planets. Since
    7 Oct 2026 a brown dwarf is a planet (`docs/hybrasil-instructions.md` §6), so 13 MJ removes nothing;
    the reverse migration of brown-dwarf "stars" is in `data/star_counts/README.md`;
  - **HD 8326, GJ 9689, TOI-1801 lie just beyond 100 ly** (and HIP 86221 probably). Kept
    and flagged in their distance notes by the owner's decision; 7 CMa and gam Cep keep
    Hipparcos distances because Gaia's are perturbed.
  - **Incidental finds, recorded not fixed**, in each run-3 agent's JSON: GJ 86's age
    (11.3 vs ~2.7 Gyr), 61 Cyg A's [Fe/H] sign, host masses for gam Cep, HD 150706,
    HD 27442 and HD 204941, the 14 Her b / GJ 3929 b hybrids, GJ 65's RUWE-12 distance,
    and Feng 2025's corrections to other Feng 2022 companions.
- **Systems-tab gaps filled** (27 Sep 2026, run 4; `hy-brasil-20260927-1851`, S&P 5183-5212;
  `data/unconfirmed_search/run4/`): Stellar Class, Host mass, Effective temp, Luminosity class and
  Host luminosity now have 0 blanks across 427 rows. Follow-ups the research turned up, not yet done:
  - ~~**DE CVn** is a WD + M3V pair with a circumbinary planet but has one star and no Multi-stars rows;
    its luminosity (0.0172) is the pair's, beside the white dwarf's 8000 K, so the star-colour factor is off.~~
    Done 28 Sep 2026, run 7 (`unconfirmed_search.md` §8.7): Multi-stars rows DE CVn A (WD) and B (M3 V).
  - **RR Cae b's host luminosity** (Unconfirmed H) is the white dwarf's alone (0.000655), though the
    planet is circumbinary and RR Cae B is 6x brighter; DE CVn b's carries the pair's. Pick one rule.
  - **Six UPM/LSPM/SCR/LHS stars** have only a photometric type (`~M4`, Sebastian et al. 2021); no
    spectroscopic type is published.
  - **GJ 667 A and HIP 86221** Teff come from blended A+B light (low confidence).
  - Recorded, not fixed: LAWD 37's 7600 K (sources give 7880-8062), WD 2105-820's age (progenitor
    lifetime, not total), WD 2149+021's class text, GJ 237's planet host should read GJ 237 B, GJ 65's
    class is just "M" (M5.5 V published), psi1 Dra A's Gaia id (1651268660203160448) is missing.
- **Tschudi 2026 flags 11 M-dwarf TESS candidates as false positives.** The list is
  only in its machine-readable tables, which nobody has opened. Check them against
  the TOI rows on Unconfirmed; any match moves to Rejected candidates (C03).
- **Van Maanen 2 b and GD 140 b are tiered `ambiguous` on a proper-motion anomaly
  that two catalogues disagree on.** One finds Van Maanen 2's hugely significant and
  the other doesn't; GD 140 is split the same way. Decide which catalogue to trust,
  and move either to Rejected if its anomaly is not significant (C03).
- **Keep it current** (§5.6): re-pull the TOI table whenever the tab is revisited, and
  watch for Gaia DR4 (December 2026).

## Known within 100ly (reference tab, added 28 Sep 2026)

- **Classify the unplotted objects.** Nearby Stellar Motion draws the tab's ~10,200 unplotted rows as one purple
  "Unclassified" layer (`star_motion.UNCLASSIFIED_COLOUR`, behind the ✚ Known within 100 ly button), because
  their `Stellar Class` / `Luminosity class` cells are blank. The data needed to classify them is to hand:
  - SIMBAD spectral types, already fetched for most of them in
    `data/known_within_100ly/kinematics/cat/simbad_*.json` (`sp_type`, `otype`);
  - Gaia DR3 G and BP-RP.

  Once classified, draw each object in its class colour (`spectral_kind()`), in the class groups.
- **Motion columns** (8 Oct 2026, `data/known_within_100ly/kinematics/`; `status.py` says where it stands):
  - **Done:** the bulk Gaia DR3 + SIMBAD pass filled 10,206 rows. 30 literature batches then added 438 RVs and 20 PMs.
  - **Left:** 2,881 rows still have no RV.
    - K031–K033 (the faintest, ~300 rows) await a decision. Yield fell to 1–7 RVs per 100 by K021.
    - Review the decisions in `kinematics/LEDGER.md` ("For the user's judgement"), in particular:
      - blended components: the bulk pass kept Gaia's combined-light RVs, but the agents held them back;
      - DESI DR1's 3–6 km/s offset for late-M dwarfs, and Hsu 2026 (JWST) reading 5–7 km/s low;
      - the misnamed or duplicate rows the agents found (GJ 4378 B, GJ 257 A, GJ 10108 B, GJ 11905 A /
        GJ 11906 B, ...).
- **Tab membership review:** later batches were mostly anonymous G ≈ 19.5–21 Gaia sources toward the bulge
  (RA 255–300°). Many are probably spurious parallaxes rather than objects within 100 ly (e.g. GJ 12699,
  GJ 12151).
  - **Flagged 9 Oct 2026, not cut** (`data/existence/`): 689 objects only Gaia DR3 lists. They have no SIMBAD
    entry and no CNS5 row, and every one has `fidelity_v2` < 0.05. Their `Existence` cell reads
    `unconfirmed: only cited in Gaia DR3`, and the view draws them aquamarine.
  - Open: remove them from the tab (or set them aside) if the owner decides they are not within 100 ly.
    72 more rows have `fidelity_v2` < 0.5 but are listed by SIMBAD or CNS5; they stay purple.
- **Winters et al. 2026 (ApJ 1004, 224) Table 5:** machine-readable only, not yet on VizieR. It holds weighted-mean
  RVs for 15 pc M dwarfs that would improve or add a few rows (GJ 11218 B, GJ 12566, GJ 10537, GJ 10690,
  G 161-7, LP 12-382).

- **Reconcile the tab with what the app plots.** `data/known_within_100ly/` built it from
  `data/Nearby stars within 100 light years.xlsx`; S&P rows 5311-5337 carry the method.
  - **Plotted but not on the tab (38):** the file has no separate entry for them. Decide per
    object: add a row, or record why none exists.
    - Just past 100 ly on Gaia DR3's parallax (Systems says 100.09-100.76 ly): TOI-1801, GJ 9689, HD 8326,
      and LP 375-24, TOI-1801's companion. The Systems tab keeps them; the file's parallax cut drops them.
      Settle one boundary rule for both.
    - Not in Gaia DR3 or CNS5 as a separate source: nu Oct A, and 33 companions, mostly
      unresolved from their primary: alf Cen B, HD 180617 B, LTT 1445 C, LTT 1445 B, GJ 667 B, HD 238090 B, tau Boo B, HD 190360 B, HD 153557 C, HD 149806 B, GJ 900 C, GJ 900 B, RR Cae B, LTT 3780 B, TOI-1450 B, TOI-4336 C, TOI-4336 B, HD 207496 B, HD 199509 B, HD 134606 B, HD 134606 C, GJ 3473 B, HIP 86221 B, HIP 86221 C, GJ 773 Bb, HIP 55507 B, gam Cep B, nu Oct B, HD 19994 B, HD 19994 C, Ross 458 B, TOI-2267 B, DE CVn B.
  - **Matched without a Gaia id (37):** each row's `Gaia DR3 source_id` is blank or disagrees with the file,
    so the match rests on something weaker. Confirm each, then write the Gaia id (or CNS5 id) onto its
    Systems / Multi-stars row so the next rebuild matches it directly.
    - By position (RA/Dec carried to J2016 with the row's proper motion): eps Ind A, G 264-012, TOI-1450 A, TOI-4336 A, psi1 Dra A, BD-210397.
    - By name (GJ + component, or 'Sun'): Sun, Gl 725 B, GJ 15 B, GJ 896 B, GJ 667 C, GJ 414 B, GJ 720 B, GJ 676 B, GJ 3021 B, GJ 9714 B.
    - By SIMBAD identifiers: Proxima Cen, alf Cen A, GJ 667 A, HD 62509, HD 115404 B, HD 140901 B, HD 153557 B, HD 189733 B, alf Ari, alf Tau, 16 Cyg B, 16 Cyg C, HD 18143 C, HD 18143 B, psi1 Dra B, HD 39855 B, G 229-20 B, G 229-20 A, HD 155918 B, HIP 86221, HD 75289 B.
    - Unresolved CNS5 entries took the primary: alf Cen A = 'GJ 559 AB', GJ 667 A = 'GJ 667 AB', so B has no
      row of its own.

## Planetless 4+ Stars (reference tab, added 28 Sep 2026; first named "4+ Stars only")

- **Class and luminosity: filled 29 Sep 2026** (`data/four_plus_stars/fill.py`): 26 published,
  280 inferred from the Pecaut & Mamajek dwarf sequence (orange), 44 blank with a note saying why.
  Left to do:
  - ~~The 44 blanks~~ filled 9 Oct 2026, with the rest of the stars that drew no band. The seven evolved stars
    were split from combined light, and only ksi UMa Bb, GJ 2130 C, GJ 187.2 Ab and HR 1099 Bb are still blank
    here. See "Stars with no luminosity" below.
- **Disputed classes: corrected 29 Sep 2026** (`data/four_plus_stars/classes.py`, S&P 5382–5392).
  Capella A/B → G8III/G0III, GJ 275.2 Ba/Bb → DA, HR 2158 C → F9V, alf2 Lib Ba → F4V; GJ 275.2 Ab's
  'DA' withdrawn (unseen companion). HR 1099 Aa/Ab classes and luminosities swapped, MSC masses kept.
  The Luminosity class formula is now case-sensitive on all three tabs (`dM1` read "White dwarf").
  Left to do:
  - alf Leo Ab reads "No luminosity class"; check what the companion is. (ksi UMa Bb's `WD?`
    was settled 7 Oct 2026: a star, M dwarf or white dwarf; see the watch list.)
  - GJ 275.2 Ba's MSC mass is 0.8 Msun; Limoges 2015 and Holberg 2016 give 0.50–0.63 per
    component. The MSC masses were left alone.
  - GJ 275.2 Aa (G 107-69, M4.0 V) reads 0.19 Msun (MSC); Winters et al. 2021 give 0.147 +/- 0.014. Left alone
    (9 Oct 2026).
  - Teff, age and [Fe/H] are still blank.
- **Planet hosts off the list.** psi1 Dra and GJ 896 (both 4+ systems) were removed because they
  host planets on file; if they are wanted as 4+ systems too, they belong on Multi-stars.
- **Reconcile with Multi-stars.** Systems on both tabs model them differently. Decide which is
  current and carry it across.
- **Draw them.** Castor is drawn (featured, 30 Sep 2026): `orbits.py` added periastron epochs, RA/Dec and
  barycentres to the whole tab, `castor.py` completed Castor from the literature, and `data/hierarchy.py`
  builds any system's rows into bodies with barycentres. Left to do:
  - **Research pass done (30 Sep 2026, `research.py`, `companions.py`):** ORB6 / SB9 / Gaia DR3 checked; 19 orbits
    newer or new, Gaia i/node for 4, photocentre a and two inconsistent periods from Kepler, omega convention for
    every pair, two hypothetical companions added. The Kepler check found no other factor-of-ten period slip.
  - **Inferred pass done (30 Sep 2026, `infer.py`):** every pair now has a complete orbit -- 132 wide pairs face-on
    at today's position angle, 21 SB tilts/nodes assumed, 31 suspected companions typical and hollow. **Drawn:**
    `planetless_loader.py` lists all 81 other systems under High Star Count (Planetless) in the web app.
  - ~~BD+08 2134 Aa-Ab's T~~ done 30 Sep 2026: Fuhrmann 2005's epoch is a paywalled table image, so the pair
    took SB9's Griffin 1991 orbit whole (`bd08_2134.py`).
  - ~~Paper check of 17 Cyg A-B, HR 1099 A-B, iot UMa A-BC~~ done 1 Oct 2026 (`cyg17.py`, S&P 5438–5443): all
    three ORB6 orbits are Izmailov 2019 short-arc fits with no mass constraint (x4.7, x5.6, x2.3 the tab's mass;
    now in `research.py`'s `REJECT_ORB6`). 17 Cyg A-B took Romanenko et al. 2025's AMP orbit (ARep 69, 398;
    solution 1 of two that fit equally, the other in the notes). iot UMa keeps Zhuchkov 2012. HR 1099 keeps
    Hopmann 1964, with its discrepancies noted on Orbit source: dropped from ORB6, mass agreement possibly
    built in, T = 1900.0 exactly, grade 5. Left open: check Hopmann 1964's T and elements against the paper.
  - ~~BD+39 496 Bb, the refuted single brown dwarf of HD 13507~~ done 4 Oct 2026 (`hd13507.py`, S&P 5471–5477):
    replaced by Grandjean et al. 2021's two (b 0.02, c 0.03 M_sun m sin i at 4.2 / 5.4 au), both hollow. B is now
    Bab + Bc, as Castor's C is Cab + Cc. Left open: the MSC's single-orbit fit uses Fischer 2014's Lick RVs,
    which Grandjean did not; a joint fit of all three datasets would settle it.
  - **GJ 570 A-B:** ORB6 Kpp2020f (6489 yr) vs the tab's Hle1994 (2130 yr). Not taken because the periods differ
    by more than research.py's 1.5x match window (not by the year rule). Kpp2020f gives 1.9x the tab's mass at the
    tab's parallax, Hle1994 0.9x.
  - **Izmailov & Khovritchev 2025** (RAA 25, 015016; 850 wide pairs; tables at `izmccd.puldb.ru/vds6/`) is the
    successor to Izmailov 2019 and may reach ORB6. Same method, so check its orbits against the tab's masses before
    taking any: its 17 Cyg A-B (2405 yr, 22.03") needs ~17 M_sun. `research.py`'s Kepler filter catches a
    factor-of-2 failure, but re-run the plan and read the matches whenever ORB6 is refreshed.
  - **The two added companions are doubtful** (GJ 187.2 Ab: SB9 grade 2, no Gaia orbit; GJ 3347 Aa2: likely a Gaia
    SB1 alias of Ab). Check Gaia DR4 when it is out.
  - The CLI (`--source catalog`) and the file page still skip the tab; only `--serve` draws the 81.
  - ~~Offer them in Nearby Stellar Motion, off by default~~ done 1 Oct 2026: the data is on the tab
    (`kinematics.py`, S&P 5444-5451) and the view's **Planetless Systems** button adds the 82, ringed in white
    (docs/architecture/star-motion.md, "The planetless systems, behind a button").
- **The viewer mirrors sky-frame orbits in depth.** It draws published Omega, omega and i with z toward Earth,
  while the published convention puts the ascending node where the star recedes. Sky positions are right, and
  which star is nearer us is reversed -- for every sky-frame system (Alpha Centauri, Upsilon And, 55 Cnc,
  Castor), consistently. Castor's YY Gem, for one, is drawn with Cb behind Ca at primary minimum.
- **Plotly: a page error on every system switch** ("Cannot read properties of undefined (reading 'N')" in
  Plotly's prepareFn), present before Castor (reproduced on e409147 with Alpha Centauri). The browser tests
  do not listen for page errors on the Plotly page, only on the three.js one.
- **Weak periods.** 'Period basis' = "MSC estimate from separation" marks order-of-magnitude
  periods for wide pairs; treat them as such anywhere they are used.

## Catalog workbook

- **Unconfirmed tab, column T: every candidate gets the same radius.**
  Rows 2–41 carry a fixed `=1.031487/'Planets within 100 ly'!$C$544`, so every
  TOI and Gaia candidate reads 1.03 R⊕. The Gaia astrometric rows (37–41) have
  no radius at all; their own flags say so. It looks like a formula filled
  down from one row. Check against the TOI table's `pl_rade` before changing
  anything, and follow `docs/hybrasil-instructions.md`.
- **Gl 725 B has no habitable-zone limits on the sheet.** So Gl 725 B c
  (Planets row 540) shows no HZ position, although its paper places it in B's
  habitable zone (0.45 S⊕). The same is true of 55 Cnc B. Kopparapu limits
  need B's Teff, which is not on file either.
- **GJ 900 A b's orbit is its projected separation.** 12,000 au, from direct
  imaging (Rothermich et al. 2024), is stored as its semi-major axis, and its
  1.26 Myr period is Kepler III on that value. Both are orange and WEAK.
  Replace them if an orbit is ever fitted.
- **1 catalog system still opens as its stars and bands only: HD 109647.**
  The archive does not list its Unconfirmed-tab candidate. On 26 September
  2026 the NASA Exoplanet Archive (`pscomppars`) filled orbits for 95 of the 99
  planet rows that had none, and host masses for six stars that needed one.
  CD-35 2722 b and G 80-21 b were then drawn by hand, and GJ 773 B was split
  into its two stars. Details are on Sources & Provenance, rows 4085–4192.
- **GJ 773 B is drawn as Ba + Bb, an SB2 in a 406 d orbit** (Multi-stars rows
  93 and 95).
  - The orbit is Gaia DR3's.
  - The masses (0.126 M☉ each) assume the two stars are equal, and the 0.678 au
    is Kepler III on those masses. All of it is orange and inferred.
  - Replace it if the SB2 is ever solved.
- **Unconfirmed's tier colours are on the wrong column.** Three conditional
  formats colour `strong` / `ambiguous` / `unlikely` in AH (Tidal-lock
  expectation), not AJ (Confidence tier). They were copied as-is onto the
  Rejected candidates tab. Probably left behind by a column insert.
- **Nine orbits are WEAK, orange-boxed.**
  - GJ 508.2 b's P and a are lower limits.
  - GJ 504 b, Ross 458 c, WD 0806-661 b, HN Peg b, G 196-3 b and CD-35 2722 b
    (67 au, Wahhaj et al. 2011) are stored with a projected separation as their
    semi-major axis.
  - G 80-21 b (Unconfirmed) is drawn at 1.0 au, the geometric middle of the
    0.5–2 au range in Lagrange et al. 2025. It is a placeholder, not a fit.
  - Replace any of them if an orbit is fitted.
- **Separation disagreements, left as published and recorded in Sources &
  Provenance (MULTI-STARS: SEPARATION COLUMNS AQ:AT ADDED):**
  - GJ 667 C: González-Payo et al. 2024 prints 39.515″ / 286.1 au. Gaia DR3
    (32.42″) and WDS 2022 (32.6″) agree with each other. Gaia's value is
    stored.
  - TOI-4336 C: the Role cell says "2900 AU". Gaia DR3 gives 98.50″, which is
    2212 au.
- **HD 134606 C is the weakest separation on the sheet.** Its 5.36 au rests on
  González-Payo's "of the order of 0.2 arcsec", which they read from a
  bimodal Gaia light curve. Nothing has resolved the pair.

## Data consistency

- **55 Cnc g's orbit comes from a different fit than 55 Cnc d's.** The
  featured 55 Cancri draws d from Bourrier et al. 2018 (P = 5574 d), but g
  comes from Moutou et al.'s six-planet fit, where d has P = 4799 d. The two
  orbits cross. d's tilt and node now come from a third fit, Xiao et al. 2026
  (P = 5084 d). Consider moving d to one fit throughout.
- **The catalog marks a loosely fitted orbit as "confirmed".** A
  `semi-major axis` row counts as a solved orbit, so 55 Cnc B (1259
  +826/−431 au) and tau Boo B (221 +138/−62 au) are drawn solid and
  confirmed. Consider an orbit-quality column, or treat large errors as
  hypothetical.
- **55 Cnc B's planets are drawn in B's orbit plane by assumption.** Nothing
  measures their tilt. Replace it if a transit, astrometric orbit or spin-orbit
  constraint ever appears.
- **The same paper is cited with two different years.** The existing 55 Cnc B
  rows call it "Moutou et al. 2026, A&A". The new g entries say "2025, A&A
  accepted" (arXiv v1, 13 Oct 2025). Settle the year and volume once it is
  published.

## Stars with no luminosity, so no solvent band (9 October 2026)

**Filled 9 Oct 2026** (`data/four_plus_stars/fill_missing_lum.py`, `hy-brasil-20261009-1658`, S&P 5674-5692;
research records with a quote for every number in `data/four_plus_stars/lum_research/`). Of the 49:

- 3 published (plain): ups And B, GJ 644 C, HD 23439 Ba;
- 17 derived from published inputs (orange);
- 15 inferred from mass, WEAK (orange): the hypothetical companions, plus HD 23439 Bb;
- 7 floored at the dwarf sequence's last tabulated mass, L2V at 0.075 M_sun, log L -3.82 (orange, WEAK); see the
  watch list;
- 7 left blank, each with a note saying why.

No value came from Wikipedia. ups And B's luminosity is in `builtin_systems.py` too, so the featured system draws
its band stack.

Left blank:

- **nu Oct B:** a white dwarf with no Teff. A cooling-track estimate (~2.3e-4 L_sun) would rest on a press-quoted
  cooling age of ~2 Gyr.
- **ksi UMa Bb:** probably a white dwarf (Fuhrmann et al. 2016), and no Teff exists.
- **HD 151613 B and HD 207496 Bb:** unseen, and their nature is undecided.
- **GJ 2130 C and GJ 187.2 Ab:** the literature doubts both exist; see below.
- **HR 1099 Bb:** its nature is unknown and its orbit is doubted.

What the research turned up, not yet acted on (the cell notes and research records give the evidence):

- **GJ 187.2 Ab: reject?** The 391.7 d orbit (Abt 1965) was not confirmed by Abt & Levy 1974. The RV variation of
  9 Aur A is its own gamma Dor pulsation (Krisciunas et al. 1993, 1995), and the MSC marks it 'false?'.
- **GJ 2130 C: a duplicate?** HST and Gaia see no third star; Winters et al. 2019's third star is the SB2 secondary
  Bb.
- **HR 1099 Bb:** Gaia DR3's RUWE 1.03 and near-constant RV sit badly with an orbit that should wobble B by
  >= 5.8 mas. Revisit the 9 Oct "star" decision.
- **GJ 644 C is GJ 643** (Wolf 629, M3.5 V, near-solar metallicity), the MSC's component C. SIMBAD's "GJ 644 C" is
  vB 8, the MSC's F. Consider renaming the row and dropping the class's "sd".
- **kap Tuc distance:** 75.87 ly is A's Gaia parallax, corrupted by the Aa,Ab orbit (RUWE 10.4). Tokovinin 2020
  adopts 47.66 mas, i.e. 68.4 ly. Aa's L (3.95) is at 68.4 ly.
- **Masses:**
  - ksi UMa Bb is 0.17 (+0.13/-0.05) M_sun (Fuhrmann et al. 2016), not 0.14.
  - HD 149806 Bb is ~0.4 M_sun, not 0.27 (An et al. 2025: B's dynamical mass is 0.829).
  - GJ 376 Bb is confirmed double-lined (Winters et al. 2026, P 945 d, q 1.03), so its separation is ~1.1 AU, not 3.
- **Notes to correct:**
  - HD 207496 Bb's "dark companion": Gaia's 0.199-0.645 range assumes a luminous companion.
  - GJ 684 B's K3 V: its brightness fits K6-K7.
  - HD 142 B's 3922 K: Mugrauer's extinction is implausible at 26 pc, so it is probably ~3750 K.
- **Class is still blank** for the hypothetical companions. fill.py's last tier would infer it from the mass too.
