# Resumed unconfirmed search -- orchestration ledger (26-27 Sep 2026)

Rulings (user, 26 Sep): keep TRAPPIST-1 i; PMa/trend-only stay on Unconfirmed (ambiguous);
Tuomi 2019 alone caps at ambiguous (near Prot -> unlikely -> Rejected tab).

## Jobs
| Job | State | Result |
|---|---|---|
| B03 | done | 20 sys; 8 cands (3 amb, 5 unl) |
| B04 | done | 20 sys; 8 cands (2 str, 1 amb, 5 unl); first run missed TOI-6713.01 |
| B05 | done | 20 sys; 3 amb (BD-06 1339 d/e, GJ 3090 d) |
| B06 | done | 20 sys; 7 cands (5 amb, 2 unl) |
| B07 | done | 20 sys; 3 amb |
| B08 | done | 20 sys; 4 cands (3 amb, 1 unl) |
| B09 | done | 20 sys; 4 cands (1 amb, 3 unl) |
| B10 | done | 20 sys; 3 cands (1 str HD 3765 c, 1 amb, 1 unl) |
| B11 | done | 20 sys; 4 cands (3 amb, 1 unl) |
| B12 | done | 20 sys; 7 cands (drop CD-35 2722 b I/II: on Exomoons) |
| B13 | done | 20 sys; 7 cands (4 amb, 3 unl) |
| B14 | done | 20 sys; 10 cands (7 amb, 3 unl) incl. Gl 725 B b |
| B15 | done | 20 sys; 3 cands (1 amb, 2 unl) |
| B16 | done | 16 sys; 6 cands (3 amb, 3 unl) |
| C03 exoplanet.eu retry | running | |
| C04 Feng 2022 + CLS | done | 0 new; 25 carried-over Tuomi records all already on sheet |
| C05 LCES + CARMENES DR1 | done | 5 unl, 3 new systems (unlikely-only hosts) |
| C06 ExoFOP CTOIs | done | 38 CTOIs (26 amb, 12 unl), 30 new systems |
| C07 Systems rows, 25 TOI hosts | done | 3 on Systems already, 22 new_systems |

## For the user's judgement (collected from agents)
- B03: LHS 1678 companion -- authors say "likely a brown dwarf", no mass; excluded.
- B03: Planets-tab period errors: Wolf 1061 d 67.27 d (should be 217.21), YZ Cet b 1.96876 (alias; 2.02087),
  HD 134060 c 1160.9 (1291.56).
- B03: contested confirmed rows: GJ 433 c, GJ 180 c, GJ 3998 b/c.
- B07: contested confirmed rows: DE CVn b (Pulley+2022), alf Tau b (Reichert+2019), GJ 3323 c, nu Oct A b.
- B07: kap CrB c is a trend only (0.4-120 MJup at 8-66 au) -- per ruling, stays ambiguous candidate.
- B07: VHS 1256 distance stale (41.42 ly on sheet; Gaia DR3 ~69 ly), b's mass then 19+/-5 MJup (brown dwarf?).
- B07: missing stellar companions: gam Cep, nu Oct, HD 27442, HD 19994. gam Cep Ab true mass 17.5 MJup (unverified).
- B06: GJ 682 b/c on confirmed tab disowned by discoverers (Tuomi+2019 App A.43); OEC Controversial.
- B06: SYSTEMS DISTANCES WRONG: GJ 411 18.51 ly (Gaia 392.75 mas -> 8.30 ly); GJ 273 19.31 ly (264.13 mas -> 12.35).
  "copied from NASA's inconsistent sy_dist" -- audit ALL Systems distances vs Gaia DR3 (orchestrator task).
- B06: GJ 3929 c confirmed row mixes Kemmer alias period 14.303 d with Beard mass; Beard/NASA 15.04 d.
- B06: GJ 251 c, GJ 15 A b called candidates / contested in literature.
- B06: exoplanet.eu calls GJ 411 d, LTT 1445 A d, GJ 273 d/e Confirmed; NASA none. Tiered by paper.
- ORCHESTRATOR distance audit (distance_audit.csv; 347 Systems rows with a Gaia DR3 id): 7 off by >2%.
  Large: GJ 411 (18.51 vs 8.30 ly), GJ 273 (19.31 vs 12.35), VHS 1256 (41.42 vs 68.99).
  Small (2-4%, bright stars): 7 CMa 64.61 vs 66.77, GJ 3222 59.48 vs 57.67, gam Cep 46 vs 44.98.
  HIP 86221: Gaia source has no parallax. Not systemic.
- B05: GJ 229 b and GJ 229 A c (confirmed tab) rejected at 3 sigma as activity by Deslieres+2025 (AJ 169, 182) -> review move to Rejected.
- B05: BD-06 1339 b contested (Simpson+2022); BD-21 397 b contested (Philipot+2023) but supported by others.
- B05: TOI-6276.03 on Unconfirmed filed under host "TOI-6276" = HIP 56998 (on Systems) -> re-host, don't duplicate.
- B05: naming: confirmed "TOI-836 01" should be TOI-836 c; GJ 229 rows inconsistent. TOI-2134 c mass stale (41.89 -> 58.3, Rescigno+2026).
- B08: HD 168009 / HD 150706 candidates give only P and K -> writer derives m sin i and a (orange). psi1 Dra B c: trend only, nominal a 16.2 au.
- B08: HD 150706 b on confirmed tab stale (5894 d, 861 Me); Xiao+2023: ~36 yr, a ~11.5 au, ~2.4 MJup.
- B08: HD 86728 missing its companion GJ 376 B on Systems/Multi-stars.
- B04: WRITER TIER CHANGE: HD 192310 P=24.6d tiered strong by agent, but K~0.6 m/s near first harmonic of Prot -> ambiguous per brief.
- B04: HD 82943 d, 14 Her d, HD 128311 d masses in MJup (explicit unit field) -> convert.
- B04: disputed confirmed rows: HD 140901 b (NASA controv flag), HD 1461 c, HD 115404 A b/c.
- B04: hybrid confirmed rows: HD 99492 c (refuted 4970 d signal + real 95.2 d planet's mass); HD 114386 c (1046 d vs real 444.8 d, Wu 2026).
- B04: 14 Her c period stale: 9886 d on tab; NASA 15732 d; Benedict 2023 52160 d.
- DEDUPE: TOI-6713.01 (B04, "HD 104067 d") is already on Unconfirmed under host "TOI-6713" = HD 104067 -> re-host
  (same pattern as TOI-6276 = HIP 56998). C07 must map every TOI host to an existing Systems name first.
- B09: HD 147513 b (confirmed) disputed: NASA controversial; Harada+2025 find 528 d vanishes with HARPS.
- B09: HD 177565 b, HD 21411 b, HD 39855 b called "planet candidates" by discovery papers (on confirmed tab).
- B09: HD 147513 candidate mass only in MJup (0.115) -> convert. Missing companions: HD 46375 B, HD 147513 B (WD), HD 21175 B (GJ 3222), HD 164595 (unverified).
- B10: WRITER TIER CHECK: HD 3765 c tiered strong but P ~3x Prot (44.7 d) per its own authors -> consider ambiguous.
- B10: HD 207897 RV trend (2.5 sigma, activity drifts too; TKS <2 sigma) left out; could be unlikely under trend ruling.
- B10: eps Eri c (disk inference) excluded; eps Eri b OEC Controversial.
- B10: GJ 86 missing WD companion GJ 86 B; HD 204941 binary; HD 204941 b refit 1529 d / 56 Me (Ruggieri+2026).
- B10: HD 8326 parallax 32.565 mas -> just OUTSIDE 100 ly, yet on Systems tab.
- B13: GJ 680 b on confirmed tab is a STAR (Philipot+2023: 0.178 Msun at ~32 au) -> Multi-stars as GJ 680 B.
- B13: HIP 79431 c rests on JWST proposal 9091 only (like TRAPPIST-1 i); may be a brown dwarf.
- B13: GJ 649 c mass only in MJup (0.030); GJ 514 63.7 d has only P, K, e -> writer derives.
- B11: CONFIRMED MISSING: TOI-2427 c (Schmerling+2025, A&A 699, A185, P 5.150 d, Msini 6.46 Me). TOI-2427 b mass empty (5.69 Me).
- B11: HIP 55507 b (confirmed) is the M7.5 star HIP 55507 B (Xuan+2024, 88 MJup, ~38 au) -> Rejected + Multi-stars.
- B11: GJ 160.2 b (confirmed, 5.24 d) not confirmed by Feng+2020 nor recovered by Tuomi+2019 -> review.
- B11: HIP 86221 may be beyond 100 ly (Hipparcos 33.91+/-3.88 mas; component C Gaia 31.066 mas = 104.99 ly).
- B11: eps Ind A b orbit pre-JWST (new P 25450 d Sanghi 2026 / 39400 d Matthews 2026, 7.6 MJ); GJ 338 A row has B's Gaia ID; HD 147379 binary with GJ 617 B.
- B12: WRITER DROP: CD-35 2722 b I and b II are already on the Exomoons tab (b I row; b II = its Alternative solution). Not planets.
- B12: HIP 48714 b (= GJ 373 b) and GJ 96 b on confirmed tab refuted by Ribas+2023 (CARMENES DR1 Table 4) -> Rejected?
- B12: GJ 9689 (100.09 ly) and TOI-1801 (100.76 ly) just beyond 100 ly on Gaia DR3. GJ 9689 b called "candidate" by its paper.
- B12: missing companions: TOI-1801 (LP 375-24), Ross 458 B; Ross 458 A mass 0.511 (Feng+2022) vs 0.6 on sheet.
- B12: limits shown as values: GJ 341 b 4 Me is an upper limit; GJ 508.2 b 5300 d / 1.85 MJup are lower limits (astrometric 6.0 MJup).
- B12: agent self-converted MJup->Me for its records (286, 88) -- writer redoes by sheet rule.
- B15: Kapteyn b arguably refuted (Robertson+2015, Bortle+2021) -> tiered unlikely -> Rejected tab. Kapteyn c (confirmed) also rotation per Bortle+2021.
- B15: Kapteyn Systems row missing Gaia DR3 id (4810594479418041856).
- B15: TOI-6716 on sheet TWICE: b on confirmed (validated Scott+2026) and .01 on Unconfirmed -> remove the Unconfirmed row.
- B15: TOI-1452 is a 3.2" binary (not on Multi-stars). TOI-5388 "01" should be b; its 2.2 Me is a 3-sigma upper limit.
- B14: GJ 436 UCF-1.01/.02 excluded as refuted (Controversial on exoplanet.eu/OEC) -> could file on Rejected.
- B14: Gl 725 B b now found (TODO item) -> add. Three Gl 725 B signals named by period due to letter collisions.
- B14: TOI-4438 b mass on sheet 5.4 Me; NASA now 4.11 (Serrano Bell+2026). Gl 725 A b called "planet candidate" by Cortes-Zuleta+2025.
- B16: GJ 1151 c confirmed row mixes refuted 2.018 d / 0.01735 au with real planet's mass; real P 389.7 d, a 0.57 au.
- B16: TOI-7032.01 on BOTH tabs (it is GJ 523 b, Kroft+2026 preprint) -> remove from Unconfirmed.
- B16: WD 1856+534 b "likely BD" flag stale (Limbach+2025 JWST: <~6 MJup, a planet). RR Cae b contested (Pulley+2025).
- B16: GJ 9066 c mixes Feng period with Quirrenbach mass. GJ 1151 curvature: authors lean activity.
- C04: WRITER TIER CHANGE: HD 82943 d (B04 ambiguous) is a CLS Table 7 false positive -> unlikely.
- C04: carried-over first-run candidates (25) are already on Unconfirmed/Rejected, some under other names (GJ 739 b filed as "GJ 739 c") -> writer must drop all.
- C04: brown dwarfs on confirmed tab per Feng 2022 true masses: HD 111232 c 18.1, HD 153557 d 27.5, GJ 680 b 25.1 (a star per B13), GJ 676 A c 13.5 MJup.
- C04: 61 Vir d = CLS yearly systematic. HD 140901 c 572 Me vs Feng 6.28 MJup. Periods shorter than Feng: HD 142 c, 14 Her c, HD 87883 b, bet Pic b, GJ 676 A c.
- C04: CONFIRMED MISSING: 3 records (see C04.json). Ross 458 companion GJ 494 B (88.9 MJup).
- C07: RE-HOST: TOI-6276 -> HIP 56998; TOI-6713 -> HD 104067. REMOVE: TOI-7032.01 (= GJ 523 b, confirmed row 539).
- C07: 22 new Systems rows (TIC v8.2 + Gaia DR3). Names: TOI-2009->HD 6660, TOI-2540->HD 274255, TOI-4328->HD 29086,
  TOI-802->HD 47252, TOI-6978->HD 188559 (or GJ 1247), TOI-4324->HIP 47619, TOI-5961->HIP 114941, TOI-7052->HIP 87773.
- C07: TOI-2540.01, 4324.01, 5961.01, 6662.01 now CP on NASA TOI table (2026-08-25) but no paper/ps entry yet.
- C07: comoving companions: HD 6660 (9.41", DR3 2791782794564103680), HIP 87773 (10.61", DR3 4604269606340411136). TOI-6714 speckle companion, boundness unknown.
- C07: WebSearch budget exhausted mid-run (shared) -> remaining agents may have thin literature coverage.
- C06: CONFIRMED: TOI-2540.01, TOI-5961.01, TOI-6662.01 validated by Collier+2026 (arXiv:2608.21560, Table 3) -> move to Planets. (TOI-4324.01 CP, no paper yet.)
- C06: USER QUESTION: 30 new Systems rows for single, unvetted CTOI detections -- worth it? esp. unlikely-only hosts (2 WDs, LSPM J1835+3259, PM J11117-5620, GJ 114.1).
- C06: GJ 237 record's star data are B's (signal could be A or B, 3.3"). Lean-unlikely: GJ 14, HD 194640, HD 161284 (submitter flags variability).
- C06: GJ 4248 CTOI list distance 16.4 pc vs Gaia 7.67 pc.
- C05: GJ 251 c 53.647 d = CARMENES DR1 "rotation". Wolf 1061 b called an alias of 1.27 d. HD 99492 primary 83 Leo A missing. 55 Cnc A Gaia id missing (704967037090946688).
- C05: its 3 new systems host only unlikely LCES signals (HD 221354, HD 195564, HD 1388) -> same user question as C06.
