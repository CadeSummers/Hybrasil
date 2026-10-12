# Unconfirmed-planet search: status, sources, next steps

**Status (27 September 2026): the search is complete.** A second run on 26–27 September finished every
per-system batch and every catalogue sweep the first run left. Its results and the write are recorded in
**§8** below. The live workbook is now **`hy-brasil-20260927-0850`**. What is left is correcting the
confirmed Planets and Systems rows the agents flagged (§8.4, and `TODO.md`), and keeping the tab current (§5.6).

Sections 1–7 below describe the **first run** (23–24 September) as it stood when halted, and are kept as
written.

**Status (24 September 2026):** the search was halted part-way. Everything it found up to that point is on
the Unconfirmed tab of the live workbook, which is now named **`hy-brasil-20260924-1326`**.

- **Unconfirmed tab:**
  - **Added:** 60 rows (43–102).
  - **Rows 37–41:** the five Gaia astrometric candidates are all refuted. They are now tiered
    `unlikely`, with the reason at the front of column AI.
  - **Nine TOI rows:** each got an update note. Four are now CP, two duplicate confirmed planets,
    and three have hosts known by another name.
- **Sources & Provenance:** the full write-up is in rows 3583–3799. It covers every row's source,
  each inferred method, the known limits, and the claims that were rejected.
- **Not yet done:**
  - **Coverage:** most of the per-system search, 256 of the 316 existing systems.
  - **Systems tab:** done on 24 September 2026 for the 39 new systems and the five Gaia hosts
    (Systems 319–362, Multi-stars 91–94, Sources & Provenance from row 3801). The 33 TOI hosts of
    rows 2–36 still have none.
  - **Snapshot:** re-exported on 24 September 2026 as `data/hy-brasil-20260924-1326.xlsx`.
- **Raw research:** every agent's full record is in `data/unconfirmed_search/`. That includes the
  source URLs, table locators, aliases searched, and the reason for every exclusion.

---

## 1. What the search set out to do

1. **Candidates already in the viewer's models.** These were Planet Nine, alpha Cen A's imaged
   candidate and Proxima c. 55 Cnc g was already on the tab.
2. **Every system on the Systems tab.** Each one was checked for candidates or unconfirmed planets not
   already listed. TRAPPIST-1 i is one example.
3. **Candidate-only systems within 100 ly.** These are systems whose only planets are candidates. They
   were to go on the Unconfirmed tab, and the systems themselves onto the Systems tab.

Research agents worked to a written brief (`data/unconfirmed_search/pack/BRIEF.md`) and wrote only to
local JSON files. One guarded script, written in this session, then made every sheet edit.

**Rules the agents followed:**
- Every number came from a source they opened, with a table or section locator.
- Primary papers were preferred, then catalogues, then Wikipedia. No value on the new rows came from
  Wikipedia.
- "Within 100 ly" means a Gaia DR3 parallax of at least 32.616 mas.
- They did not add:
  - refuted or retracted claims;
  - brown dwarfs, i.e. objects their own authors put above 13 M_Jup;
  - pure dynamical inferences. Planet Nine is the one exception, because the viewer already draws it.

**Tiers** use the tab's existing three words:
- `strong`: a significant detection with no evidence against it.
- `ambiguous`: contested, sitting near the star's rotation or activity period, from a single
  instrument, or from a single epoch.
- `unlikely`: the best current reading is "not a planet", but no paper has formally refuted it.

## 2. Coverage when halted

| Part | Agent | Scope | State |
|---|---|---|---|
| 1 | A01 | Built-in candidates, plus the Sun and alf Cen systems | **Complete** |
| 2 | B01 | 20 systems (55 Cnc A ... bet Pic) | **Complete** |
| 2 | B02 | 20 systems (ups And ... GJ 9827) | **Complete** |
| 2 | B04 | 20 systems (HD 134987 ... HD 114386) | Partial: catalogue checks done, literature search not done, nothing found |
| 2 | B03, B05, B06 | 60 systems | Started; nothing saved to disk |
| 2 | B07–B15 | 180 systems | Started; nothing saved to disk |
| 2 | B16 | 16 systems (K2-415 ... WD 1856+534) | Never launched (concurrency cap) |
| 3 | C01 | TESS TOI table | Partial: all 223 TOIs with no distance crossmatched to Gaia DR3. Dispositions checked. |
| 3 | C02 | Gaia and astrometric candidates | Nearly complete |
| 3 | C03 | OEC and exoplanet.eu catalogue statuses | Partial: OEC done. The exoplanet.eu TAP service was unreachable. |
| 3 | C04 | RV survey papers | Partial: most of the Tuomi et al. 2019 hosts done. Feng 2022, CLS, LCES and CARMENES DR1 only started. |

The batch lists are in `data/unconfirmed_search/pack/phase2_batches.json`. `B03.json`, `B05.json` and
`B06.json` in `agent_output/` are empty skeletons.

## 3. What was added (Unconfirmed tab rows 43–102)

- **Built-in model candidates (3):**
  - Proxima Cen c (ambiguous)
  - alf Cen A b, the JWST/MIRI S1 detection (ambiguous)
  - Planet Nine (ambiguous; a dynamical inference, kept because the viewer draws it)
- **In systems already on the Systems tab (8):**
  - TRAPPIST-1 i (ambiguous): rests on JWST DDT proposal 12492 (Agol), not on a paper.
  - GJ 667 C d (ambiguous) and GJ 667 C h (unlikely)
  - GJ 887 f (ambiguous)
  - HD 40307 e (unlikely)
  - HD 158259 g (ambiguous)
  - tau Cet e (unlikely)
  - 51 Peg's candidate outer companion (unlikely)
- **In candidate-only systems (49 rows, 39 hosts):**
  - **Strong:** 18 Sco b and TVLM 513-46546 b.
  - **Tuomi et al. 2019 (unrefereed):** GJ 205, GJ 2049, GJ 3325, GJ 397, GJ 529, GJ 553.1, GJ 588,
    GJ 69, GJ 754, GJ 784, GJ 821, GJ 846, GJ 1177.
  - **HADES (Pinamonti et al. 2022):** GJ 1074, GJ 21, GJ 548 A.
  - **Feng et al. 2020:** GJ 620, GJ 911, and GJ 739 b and c.
  - **Mignon et al. 2024:** GJ 654 and GJ 739 d.
  - **RoPES, RedDots, Hirsch et al. 2021, Kennedy et al. 2015, Desort et al. 2009:** HD 161098,
    GJ 729, HD 23439 A, HD 38858, tet Cyg.
  - **Hipparcos–Gaia PMa candidates (Gratton et al. 2024):** HD 92945, HD 45270, iot Hyi, HD 155555.
  - **Also:** G 80-21 b (Gaia RUWE excess), HD 109647 b (RV trend), Wolf 359 b, GJ 300 b,
    GJ 3822 (three signals), GJ 3543 b.
  - **Two TOIs** the earlier TOI pass missed, because the TOI table gives them no distance:
    TOI-4506.01 (PC) and TOI-1256.01 (FP).

The full per-row list with sources is on Sources & Provenance, from row 3583.

**Drawn by `--source catalog`:** every row with a semi-major axis, or with a period and a host mass. Each
is shown dashed as a candidate. Since the Systems rows were added (24 September 2026), 41 of the 44 new
hosts draw. That includes GJ 1177 B b, around B, which orbits A, and four of the five Gaia hosts. These
rows are listed but **not drawn**:
- 51 Peg's outer companion;
- G 80-21 b and HD 109647 b, which have neither a period nor a semi-major axis;
- Gaia DR3 4188996885011268608 (GJ 773 B). It has no host mass, because the only published one is a
  single-star fit to an SB2.

**17 inferred cells** carry an orange border and a hover note:
- semi-major axes from Kepler's third law;
- Planet Nine's period;
- Wolf 359's luminosity, from R²T⁴;
- the two TOI rows' luminosity and semi-major axis.

Habitable-zone bounds use the sheet's own Kopparapu recipe. For hosts already on the Planets tab they
are copied across, so each candidate is computed on the same star as its confirmed neighbours.

**Rejected, with reasons in the JSON:**
- **Refuted, retracted, or actually stellar:**
  - alpha Cen Bb and Barnard's star 2018 b
  - GJ 876 f and g
  - HD 20794 c, HD 26965 b, HD 85512 b and HD 38858 b
  - tau Cet b, c and d; rho CrB d; ups And e
  - Wolf 359 c and AD Leo b
  - eta Cas Ab, BD+20 1790 b and Fomalhaut b
  - five Tuomi 2019 signals later shown to be stellar rotation or companion stars: GJ 361, GJ 880,
    GJ 479, GJ 4303 and GJ 310
- **Brown dwarfs:** HIP 45839 B, HD 184860 b, HD 68017 Ab, HD 104304 b.
- **Dynamical inference only:** Planet Y, Planet X (Siraj et al.), and Lykawka & Ito's Kuiper-belt planet.
- **Could not be traced to a source:** alf Men Ab, bet Cet b.

## 4. Things found that are not candidates (nothing changed; decide separately)

- **Confirmed planets missing from the Planets tab:**
  - **TOI-2267 b, c and d** (Zuniga-Fernandez et al. 2025; d from Greklek-McKeon et al. 2026). At
    73.5 ly this is within 100 ly, but the TOI table carries no distance for it.
  - **Gliese 48 b** (Conzo et al. 2026, 8.2 pc).
  - Four NASA-listed companions of brown-dwarf hosts, all above 13 M_Jup.
- **Planets-tab rows that look wrong:**
  - HD 160691 (mu Ara): c, d and e have periods and masses that don't belong together.
  - HD 96700 c: carries planet d's period.
  - HD 181433 c and d: use the 2009 periods.
  - HD 39091 c, HD 63433 d, HD 48948 b–d: missing a period or a mass.
- **Contested planets on the Planets tab** (NASA flags most as controversial):
  GJ 667 C e/f/g, HD 40307 g, HD 20794 e, HD 219134 f/g, AU Mic e, GJ 3293 d, HD 164922 e, 61 Vir d, and
  tau Cet f/g/h.
- **Systems tab:** HD 142 is a binary but is listed as one star.
- **Viewer built-ins** (`builtin_systems.py`) lag the literature:
  - Planet Nine: drawn at a=700 AU, e=0.6. The latest estimate is a≈500 AU (Brown, Holman & Batygin 2024).
  - alf Cen Ab: drawn on a 1.1 AU circle. Beichman et al. 2025 give a=1.66 AU, e≈0.37.
  - Proxima c: its parameters come from Benedict & McArthur 2020, but it cites Damasso et al. 2020.
- **Code:** the loader draws `unlikely` rows the same as `strong` ones. It may be worth hiding
  `unlikely` rows, or drawing them fainter.

## 5. Plan for next steps

1. **Finish part 2 (256 systems).**
   - Resume batches B03 and B05–B15, finish B04's literature search, and launch B16. Use the same
     brief and batch lists.
   - Run **at most about six agents at once**. Twenty in parallel shared one usage window and none
     finished. Six at a time finished within a window.
   - Keep the rule that agents save after every system.
2. **Finish part 3.**
   - **exoplanet.eu:** retry its statuses (Candidate / Controversial / Unconfirmed) through the
     VO-Paris TAP service, which timed out twice, or through its planet pages.
   - **Survey papers:** finish the tables of Feng et al. 2022, the California Legacy Survey (its
     status C rows), Butler et al. 2017 (LCES: 60 "Candidate" signals) and CARMENES DR1 (Ribas 2023).
   - **ExoFOP community TOIs (CTOIs):** the TOI table does not contain them. Sweep them too.
3. **~~Add the 39 new systems to the Systems tab.~~ Done 24 September 2026**, with the five Gaia hosts
   as well: 44 rows inserted inside the pinned range (now `$2:$363`), and Multi-stars rows for GJ 1177
   A/B and GJ 773 A/B.
   - Host luminosity (N) and HZ distance (O) are **typed** on these rows, not looked up. That was the
     owner's choice, because the Planets-tab lookup cannot see a candidate-only host.
   - The write-up is on Sources & Provenance from row 3801. What is left is Systems rows for the 33
     TOI hosts of rows 2–36.
4. **Rule on the open judgement calls:**
   - **TRAPPIST-1 i:** keep it while it rests on a proposal alone, or wait for a paper?
   - **PMa-only and trend-only rows:** keep them, or move them to a "companion hints" list?
   - **Tuomi et al. 2019:** how far to trust an unrefereed survey.
   - **`unlikely` rows:** hide them in the viewer?
5. **Fix the data errors in §4.** Each fix follows the workbook's own rules: guarded writes, a
   provenance entry, a rename, and a link.
6. **Keep the data current.**
   - Re-pull the TOI table each time the Unconfirmed tab is revisited. Dispositions change: four PC
     rows became CP within a month.
   - Watch for **Gaia DR4** (expected December 2026). Its epoch astrometry will produce new candidates
     around nearby stars, and will re-test the PMa ones.
   - Also watch the ESPRESSO/NIRPS, CARMENES, HPF/NEID and JWST imaging programmes of nearby stars.
7. **~~Re-export the xlsx snapshot.~~ Done 24 September 2026:** `data/hy-brasil-20260924-1326.xlsx`.
   Re-export after every later edit (step 9 of `docs/hybrasil-instructions.md`).

## 6. Sources used

**Databases and services queried:**
- NASA Exoplanet Archive TAP: `toi` (pulled 2026-09-23), `ps`, `pscomppars`, and the removed-targets
  list
- ExoFOP-TESS
- Gaia DR3 via the ESA TAP service (`gaia_source`, `astrophysical_parameters`, `nss_two_body_orbit`),
  plus Gaia DR3 on VizieR (I/355)
- The ESA Gaia (candidate) exoplanet list v20220613 and the Gaia DR3 known-issues page
- SIMBAD (basic and ident)
- TESS Input Catalog v8.2 (VizieR IV/39)
- Washington Double Star catalog (VizieR B/wds)
- The Open Exoplanet Catalogue (GitHub XML)
- exoplanet.eu planet pages. Its TAP service was unreachable.
- The arXiv API
- STScI JWST programme pages
- VizieR tables J/AJ/153/208 (LCES) and J/ApJS/262/21 (Feng 2022)
- The CLS I planet list (github.com/leerosenthalj/CLSI)
- Wikipedia, as a lead only (alpha Centauri Ab); no value came from it

**Papers:**
- **Planet Nine and the outer Solar System:**
  - Batygin & Brown 2016 (AJ 151, 22)
  - Batygin et al. 2019 (Phys. Rep. 805, 1)
  - Brown & Batygin 2021 (AJ 162, 219)
  - Brown, Holman & Batygin 2024 (arXiv:2401.17977)
  - Batygin et al. 2024 (arXiv:2404.11594)
  - Millholland & Laughlin 2017 (AJ 153, 91)
  - Napier et al. 2021 (arXiv:2102.05601)
  - Siraj, Chyba & Tremaine 2025 (ApJ 978; arXiv:2508.14156)
  - Lykawka & Ito 2023 (AJ 166, 118)
  - Phan et al. 2025 (PASA 42, e064)
  - Galiazzo & Finch 2026 (arXiv:2606.00612)
  - Iorio 2026 (Universe 12, 4)
- **alpha Centauri and Proxima:**
  - Wagner et al. 2021 (Nat. Commun. 12, 922)
  - Beichman et al. 2025 and Sanghi et al. 2025 (ApJL; arXiv:2508.03814, 2508.03812)
  - Damasso et al. 2020 (Sci. Adv. 6, eaax7467)
  - Benedict & McArthur 2020 (RNAAS)
  - Kervella et al. 2020 (arXiv:2003.13106)
  - Gratton et al. 2020 (A&A 638, A120)
  - Faria et al. 2022 (A&A 658, A115)
  - Artigau et al. 2022 (arXiv:2207.13524)
  - Suárez Mascareño et al. 2025 (A&A 700, A11)
  - Libralato et al. (arXiv:2512.08533)
- **Existing systems:**
  - Anglada-Escudé et al. 2013 (A&A 556, A126)
  - Feroz & Hobson 2014 (MNRAS 437, 3540)
  - Robertson & Mahadevan 2014 (ApJL 793, L24)
  - Hartogh et al. 2026 (arXiv:2602.08929)
  - Tuomi et al. 2013 (A&A 549, A48)
  - Díaz et al. 2016 (A&A 585, A134)
  - Hara et al. 2020 (A&A 636, L6)
  - Feng et al. 2017 (AJ 154, 135)
  - Figueira et al. 2025 (A&A 700, A174)
  - Morgan et al. 2026 (arXiv:2605.11127)
  - Lubin et al. 2021; Jenkins et al. 2014; Nari et al. 2025 (A&A 693, A297)
  - McArthur et al. 2014 (ApJ 795, 41)
  - Zhao et al. 2026 (ApJS 282, 71)
  - Rosenthal et al. 2021 (ApJS 255, 8)
  - Harada et al. 2025 (SPORES-HWO II)
  - Laliotis et al. 2023 (AJ 165, 176)
- **Astrometry and Gaia:**
  - Curiel et al. 2020 (AJ 160, 97)
  - Marcussen & Albrecht 2023 (AJ 165, 266)
  - Stefansson et al. 2025 (AJ 169, 107)
  - Rogers et al. 2024 (MNRAS 527, 977)
  - Ramírez et al. 2025 (arXiv:2412.06920)
  - Venner et al. 2026 (arXiv:2603.19402)
  - Vrijmoet et al. 2026 (AJ 171, 186)
  - Sahlmann & Gómez 2025 (MNRAS 537, 1130)
  - Gratton et al. 2024 (A&A 685, A119)
  - Lagrange et al. 2025 (arXiv:2501.10488)
  - Kiefer et al. 2024 (arXiv:2409.16993)
  - Kervella et al. 2019/2022
  - Van Zandt et al. 2026 (GEODES I)
  - Feng et al. 2022 (ApJS 262, 21)
- **RV surveys and candidate-only systems:**
  - Tuomi et al. 2019 (arXiv:1906.04644)
  - Pinamonti et al. 2022 (A&A 664, A65)
  - Feng et al. 2020 (ApJS 246, 11)
  - Mignon et al. 2024 (A&A 689, A32)
  - Ribas et al. 2023 (A&A 670, A139)
  - Butler et al. 2017 (AJ 153, 208)
  - Astudillo-Defru et al. 2015 (A&A 575, A119)
  - Bowens-Rubin et al. 2023 (AJ 166, 260)
  - Lafarga et al. 2021 (A&A 652, A28)
  - Carleo et al. 2020; Kossakowski et al. 2022
  - Cortés-Zuleta et al. 2023 (A&A 673, A14)
  - Nari et al. 2026 (A&A 709, A123)
  - Brown et al. 2026 (RedDots GJ 729; arXiv:2607.08050)
  - Hirsch et al. 2021 (AJ 161, 134)
  - Kennedy et al. 2015 (MNRAS 449, 3121)
  - Grandjean et al. 2021 (A&A 650, A39)
  - Desort et al. 2009 (A&A)
  - Gáspár & Rieke 2020 (PNAS 117, 9712)
  - Endl et al. 2016 (ApJ 818, 34)
  - dos Santos et al. 2017 (MNRAS 472, 3425)
  - Kane et al. 2025 (AJ 170, 270)
  - Carleo et al. 2018 (A&A 613, A50)
  - Baroch et al. 2021 (A&A 653, A49)
- **Proposals:** JWST DDT 12492 (PI Agol, Cycle 4).

A few journal references in the JSON are marked "recalled, not verified". Check those before citing
them anywhere.

## 7. Files

| Path | What |
|---|---|
| `data/unconfirmed_search/agent_output/*.json` | Each agent's full research record: candidates, new systems, exclusions, coverage, incidental findings |
| `data/unconfirmed_search/pack/BRIEF.md` | The brief every agent worked to |
| `data/unconfirmed_search/pack/phase2_batches.json` | The 16 per-system batches |
| `data/unconfirmed_search/pack/*.csv` | The sheet as the agents saw it on 23 Sep 2026, plus that day's NASA TOI pull |
| `data/unconfirmed_search/pack/hz.py` | The Kopparapu recipe used for the HZ bounds, checked against the Planets tab |

---

## 8. Second run (26–27 September 2026): the search finished

### 8.1 What ran

The same brief, re-issued with a "what changed" section (`data/unconfirmed_search/run2/pack/BRIEF.md`)
and a pack re-exported from the live sheet on 26 September, including the new Rejected candidates tab.
Nineteen agents ran six at a time, as §5 advised; each wrote only its own JSON.

| Agent | Scope | Result |
|---|---|---|
| B03, B05–B16 | Per-system batches never searched by the first run (256 systems) | All complete |
| B04 | The literature search the first run skipped | Complete; it also found TOI-6713.01, which the first run missed |
| C03 | exoplanet.eu Candidate / Controversial / Unconfirmed statuses (all 181 within 30.66 pc) | Complete, through the website's JSON endpoint; its TAP has no status column |
| C04 | Feng et al. 2022 (all 230 rows) and the California Legacy Survey | Complete; no new candidates |
| C05 | LCES (Butler et al. 2017) and CARMENES DR1 (Ribas et al. 2023) | Complete |
| C06 | ExoFOP community TOIs (all 5,137, crossmatched to Gaia DR3) | Complete |
| C07 | Systems data for the TOI hosts that had none | Complete |

The records are in `data/unconfirmed_search/run2/agent_output/`. The merge, dedupe, write plan and the
guarded writer are in `run2/writer/`: `consolidate.py`, `plan.py`, `write.py`, `provenance.py`, with
`plan.json` and `write_log.json` as the record of exactly what was written where. `LEDGER.md` there is the
orchestration log.

**Known coverage limits.**
- SIMBAD and exoplanet.eu's TAP were often unreachable, and the arXiv API rate-limited under six agents.
  So aliases often came from NASA, OEC and the papers themselves, and searches went through arXiv's HTML
  search, OpenAlex and VizieR instead.
- The shared web-search budget ran out part-way through C03, C05, C06 and C07.
- Each agent's coverage notes say what it could not reach.

### 8.2 Owner's rulings (the §5.4 judgement calls, decided 26–27 September)

- **TRAPPIST-1 i:** keep it, `ambiguous`, while it rests on the JWST proposal.
- **PMa-only and trend-only rows:** stay on Unconfirmed as `ambiguous` candidates. There is no separate list.
- **Tuomi et al. 2019 alone:** at best `ambiguous`. A signal near the rotation or activity period is
  `unlikely`, and goes to Rejected.
- **`unlikely` rows:** filed on Rejected candidates, which the viewer never draws.
- **Weak-evidence sweeps** (community TOIs, excess-noise and infrared-excess hints): written, tiered honestly.
- **Kiefer et al. 2025 (GaiaPMEX):** only the four hosts exoplanet.eu lists (13 Ori, EO Psc, CC Eri,
  sig2 UMa B). The catalogue's other 29 hosts within 100 ly are named in `run2/agent_output/C03.json` and
  not written.
- **New Systems rows:** only for a host with a `strong` or `ambiguous` candidate.
- **Errors in the confirmed tabs:** recorded, not fixed in this pass (§8.4).
- **Contested confirmed planets** (28 September): a planet a later paper argues against, with nothing
  rebutting it, moves to Unconfirmed as `ambiguous`. One challenged and then supported, or one its own
  discovery paper calls a candidate, stays confirmed with a note in 'Orbit data source / flags' (§8.5).

### 8.3 What was written (Sources & Provenance rows 4318–4998)

- **151 new candidates.**
  - 89 on Unconfirmed: 1 `strong` (TOI-6284 P=5.24 d) and 88 `ambiguous`. The tab now holds 160.
  - 62 on Rejected candidates, all `unlikely`. The tab now holds 87.
  - Dedupe was by name, by alias, and by host plus period within 2%. 49 agent records were already on
    the sheet, and CD-35 2722 b I/II were dropped as already on the Exomoons tab.
  - Three tiers were changed by the writer: HD 192310 P=24.6 d and HD 3765 c went down to `ambiguous`,
    HD 82943 d to `unlikely`.
- **63 new Systems rows** (363–425), inside the pinned range, which is now `$2:$426`.
  - Kinematics come from Gaia DR3, by the column's own methods.
  - Luminosity and HZ distance are typed, as on the rows added on 24 September.
- **Housekeeping.**
  - TOI-2540.01, TOI-5961.01 and TOI-6662.01, validated by Collier et al. 2026, moved to Planets rows 541–543.
  - TOI-7032.01 (= GJ 523 b) and TOI-6716.01 (= TOI-6716 b) were deleted as duplicates of confirmed planets.
  - Ten TOI hosts were re-hosted onto their Systems names, e.g. TOI-6276 → HIP 56998 and TOI-6713 → HD 104067.
- **Orange cells:** 59, each with a note: 56 Kepler-III semi-major axes and 3 luminosities from R²T⁴.
  29 masses were converted from M_Jup or M☉, with a note. No value came from Wikipedia.
- **Listed but not drawn:** GJ 65 b and 61 Cyg b, whose companion stars have no Multi-stars rows, and every
  row with no orbit (trend, PMa and single-transit rows).
  - A loader fix makes the viewer say so: `Catalog.members()` now lists a planet-host star even when the
    system has no stars-tab rows. Before, GJ 65 b vanished without a note.

### 8.4 Found in the confirmed tabs: recorded, not yet fixed

> **Run 3, 27 Sep 2026** (`hy-brasil-20260927-1700`, S&P lines 5055-5182; `data/unconfirmed_search/run3/`):
> everything below is fixed **except** the contested rows, the brown dwarfs, and the four hosts just
> beyond 100 ly (kept and flagged). Six agents (W1, R1, C1-C3, M1) researched; `run3/writer/write3.py` wrote.
> GJ 229 b / A c went to Rejected as LIKELY ACTIVITY (Deslieres et al. 2025), not as refuted. TOI-4324.01 was
> validated (Collier et al. 2026) and moved to Planets as TOI-4324 b; TOI-4353.01 now has P = 39.8991 d;
> UCAC4 123-150641 b is about 5000 ly away and belongs on no tab.

These are the §4-type findings of the second run, with the agent that found each.
The full evidence is in that agent's `incidental_finds_outside_my_scope`.

- **Rows that are not planets, or have been refuted:**
  - GJ 680 b is a 0.178 M☉ star (Philipot et al. 2023; B13), and HIP 55507 b is the M7.5 star HIP 55507 B
    (Xuan et al. 2024; B11).
  - GJ 229 b and GJ 229 A c are attributed to activity at 3σ (Deslières et al. 2025; B05).
  - HIP 48714 b (= GJ 373 b) and GJ 96 b are refuted by CARMENES DR1 (B12).
  - GJ 682 b and c were disowned by their own discoverers (Tuomi et al. 2019, App. A.43; B06).
  - Kapteyn c is rotation per Bortle et al. 2021 (B15).
- **Contested rows** (resolved 28 September, run 5; see §8.5):
  - GJ 433 c, GJ 180 c, GJ 3998 b/c (B03).
  - DE CVn b, alf Tau b, GJ 3323 c, nu Oct A b (B07).
  - GJ 251 c, GJ 15 A b (B06, C05).
  - BD-06 1339 b, BD-21 397 b (B05).
  - HD 140901 b, HD 1461 c, HD 115404 A b/c (B04).
  - HD 147513 b (B09), eps Eri b (B10), 61 Vir d (C04), RR Cae b (B16), GJ 160.2 b (B11).
  - Called "candidates" by their own papers: HD 177565 b, HD 21411 b, HD 39855 b and GJ 9689 b
    (B09, B12), and Gl 725 A b (B14).
- **Brown dwarfs by true mass** (Feng et al. 2022; C04): HD 111232 c (18.1 M_Jup), HD 153557 d (27.5),
  GJ 676 A c (13.5).
- **Wrong or mixed values:**
  - Wolf 1061 d carries the 67.27 d signal; the planet is 217.21 d (B03).
  - YZ Cet b is at its alias period, 1.96876 d; the true period is 2.02087 d (B03, C05).
  - Periods out of date:
    - HD 134060 c: 1160.9 d on the sheet; 1291.56 d (B03).
    - 14 Her c: 9886 d on the sheet; 15732 d in NASA's table, 52160 d in Benedict 2023 (B04).
  - Hybrid rows that mix two solutions:
    - GJ 1151 c: the refuted 2.018 d period and semi-major axis with the real planet's mass.
      The real planet has P = 389.7 d, a = 0.57 au (B16, C05).
    - HD 99492 c: the refuted 4970 d signal with the real 95.2 d planet's mass (B04).
    - HD 114386 c: 1046 d on the sheet; the real c is 444.0 d (B04 read 444.8; the abstract and the archive say 444.00).
    - GJ 3929 c: Kemmer's alias period with Beard's mass (B06).
    - GJ 9066 c: Feng's period with Quirrenbach's mass (B16).
  - **Fixed 27 Sep 2026** (`hy-brasil-20260927-1413`, S&P lines 5029-5054): Wolf 1061 d, YZ Cet b,
    GJ 1151 c, HD 99492 c and HD 114386 c now carry the archive pscomppars P, a and e. HD 99492 c's a is
    derived (Kepler III) and orange-boxed. Script: `run2/writer/fix_periods.py`.
  - Out-of-date orbits:
    - HD 150706 b: now about 36 yr, 2.4 M_Jup (B08).
    - eps Ind A b: the pre-JWST orbit (B11).
    - HD 204941 b: refitted to 1529 d, 56 M⊕ (B10).
  - Stale or incomplete masses:
    - TOI-2134 c: 58.3 M⊕ (B05).
    - TOI-4438 b: 4.11 M⊕ (B14).
    - TOI-2427 b: mass empty; 5.69 M⊕ (B11).
  - Limits stored as values:
    - GJ 341 b's mass is an upper limit (B12).
    - GJ 508.2 b's period and mass are lower limits (B12).
    - TOI-5388's mass is an upper limit, and its "01" should read b (B15).
  - WD 1856+534 b's "likely brown dwarf" flag is stale: it is a planet (B16).
  - Naming: TOI-836 "01" should read TOI-836 c (B05).
- **Distances.** An audit of all 347 Systems rows with a Gaia DR3 id found 7 off by more than 2%
  (`run2/writer/distance_audit.csv`).
  - Large errors: GJ 411 (18.51 ly on the sheet, 8.30 by Gaia), GJ 273 (19.31 vs 12.35),
    VHS 1256 (41.42 vs 68.99).
    **Fixed 27 Sep 2026** (`hy-brasil-20260927-1408`, S&P lines 5000-5027): column C now holds the
    Gaia DR3 inverted parallax, orange-boxed. The cause was the NASA archive's `sy_dist`, which
    contradicts its own `sy_plx` on all three. Space velocity and motion direction were recomputed.
    Script: `run2/writer/fix_distances.py`.
  - Small, 2–4%, on bright stars: 7 CMa, GJ 3222, gam Cep.
  - HIP 86221 has no Gaia parallax, and may lie beyond 100 ly (B11).
  - HD 8326, GJ 9689 and TOI-1801 lie just beyond 100 ly (B10, B12).
- **Companion stars missing from Multi-stars:**
  - gam Cep, nu Oct, HD 27442, HD 19994 (B07).
  - GJ 86 B, a white dwarf; HD 204941 (B10).
  - HD 86728 / GJ 376 B (B08).
  - HD 46375 B, HD 147513 B, HD 21175 B (B09).
  - HIP 55507 B, HD 147379 / GJ 617 B (B11).
  - TOI-1801 / LP 375-24, Ross 458 B / GJ 494 B (B12, C04).
  - TOI-1452 (B15).
  - 83 Leo A for HD 99492 (C05).
  - The new systems' own companions: HD 6660, HIP 87773, GJ 65 A/B, 61 Cyg B (C07, C03).
- **Missing Gaia ids:** Kapteyn (B15) and 55 Cnc A (C05). GJ 338 A's row carries B's id (B11).
- **Confirmed planets missing from Planets:**
  - TOI-2427 c (Schmerling et al. 2025; B11).
  - TOI-2267 b/c/d and Gliese 48 b (C04, and already noted in §4).
  - TOI-4324.01, which is CP in the TOI table with no paper yet (C07).
- **Unconfirmed-tab value to check:** TOI-4353.01's 718 d period. Tschudi 2026 finds 39.899 d (C03).

### 8.5 Run 5 (28 September 2026): the contested planets

Writer `data/unconfirmed_search/run5/write5.py` (log `write_log.json`); workbook `hy-brasil-20260928-1315`,
Sources & Provenance rows 5213–5272. Evidence is the run-2 agent records; GJ 251 c was checked against
Beard et al. 2025 the same day.

- **Moved to Unconfirmed, `ambiguous` (11):** GJ 433 c, GJ 180 c, DE CVn b, alf Tau b, BD-06 1339 b,
  HD 140901 b, HD 1461 c, HD 147513 b, 61 Vir d, RR Cae b, GJ 160.2 b. Each row's flags carry the paper
  against it. They are still drawn.
  - Host rows updated: planet count, mass text, and HZ names for GJ 180 and HD 147513.
  - DE CVn, alf Tau, HD 147513, RR Cae and GJ 160.2 have no Planets row left. Their Systems 'Host luminosity'
    and 'HZ distance' were lookups of it, so both are now typed at their previous values, with a cell note.
- **Kept, challenged then supported (8):** GJ 3998 b/c, BD-210397 b, GJ 15 A b, nu Oct A b, eps Eri b,
  HD 115404 A b/c.
- **Kept, a candidate per its discovery paper (7):** GJ 3323 c, HD 177565 b, HD 21411 b, HD 39855 b,
  GJ 9689 b, Gl 725 A b, and GJ 251 c. Beard et al. 2025 argue against rotation but call GJ 251 c a candidate;
  CARMENES DR1's 'rotation' label for 53.65 d is not addressed.

### 8.6 Run 6 (28 September 2026): kinematics for Gliese 48 and TOI-2267 A

Run 3 added these two Systems rows with no RV, proper motion or galactic l/b, so the Nearby Star Motion
view could not place them. `data/unconfirmed_search/run6/write6.py` filled them (workbook
`hy-brasil-20260928-1438`, Sources & Provenance rows 5273–5289), by the column's own rule: Gaia DR3 first.

- **Gliese 48:** RV and proper motion from Gaia DR3. SIMBAD adopts 1.56 km/s against Gaia's 1.34.
- **TOI-2267 A:** proper motion from Gaia DR3, flagged RUWE 13.71, since the pair is unresolved. The RV
  (−19.0 km/s) is from Zuniga-Fernandez et al. 2025, one night of Keck/NIRSPEC; Gaia, CNS5 and SIMBAD have
  none. Its Multi-stars row takes the same values; TOI-2267 B has no astrometry of its own.

### 8.7 Run 7 (28 September 2026): DE CVn recorded as a binary

DE CVn is an eclipsing white dwarf + M3 V pair (P = 8.7 h) with a circumbinary planet, but the workbook held it
as one star, whose row paired the white dwarf's Teff (8000 K, run 4) with the pair's luminosity (0.0172 Lsun).
The red dwarf gives 24 times the white dwarf's light, so the host's bands were computed from light that is not
its own and the red dwarf was not drawn. `data/unconfirmed_search/run7/write7.py` (workbook
`hy-brasil-20260928-1832`, Sources & Provenance rows 5290–5310) records it the way RR Cae is recorded:

- **Multi-stars:** DE CVn A (DA white dwarf, host, 0.51 Msun) and DE CVn B (M3 V, 0.41 Msun), B placed from A
  at a = 2.07 Rsun = 0.00963 au, circular (van den Besselaar et al. 2007, §4.1).
- **Luminosities, orange-boxed:** A = 0.000683, B = 0.0165 Lsun, both from L = R² (Teff/5772 K)⁴ on the
  paper's radii. B's Teff (3400 K) is what Han et al. 2018 adopt for an M3 V, not a fit, so it is WEAK.
  A + B = 0.0172, the figure that was on the row.
- **Systems row:** 2 stars, the star list, `Host luminosity` now A's alone, `Planet-host class` DA+dM.
- **Left alone:** DE CVn b's Unconfirmed `Host luminosity` stays the pair's 0.0172 (with a note), since both
  stars light a circumbinary planet. RR Cae b's is the white dwarf's alone, so the two disagree (`TODO.md`).

