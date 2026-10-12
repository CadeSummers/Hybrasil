# The Orbit Direction column

These scripts added **Orbit Direction** to the workbook's *Planets within 100 ly* (column AR) and *Unconfirmed within 100 ly* (column AQ) tabs on 10 Oct 2026. The workbook was then `hy-brasil-20261010-1828`.

**Why:** nu Oct A b goes round retrograde against its binary, but every catalog planet was drawn coplanar and prograde.

| File | What it is |
|---|---|
| `research/spin.json` | Every planet on the two tabs with a measured or bounded spin-orbit angle (λ, ψ). Each value carries its bibcode and the table or section it is printed in. Sources: TEPCat's obliquity catalogue and the Rossiter–McLaughlin and Doppler-tomography papers |
| `research/orbits.json` | Orbits retrograde or polar against something other than the star's spin: a binary companion, a host binary, the other planets, a debris disk. Each is graded strong, substantial or weak |
| `plan.py` | Decides every cell and writes `plan.json`. It touches nothing |
| `write.py` | The only writer. It adds the column after each tab's last, writes every planet row by name, boxes and notes the inferred cells, corrects two spin-orbit cells, widens both filters, adds the Sources & Provenance rows, and renames the workbook |
| `write_log.json` | The record of the write |

## The cell

**Format:** `<Direction> (vs <reference>; <angle>)`, for example:
- `Polar (vs stellar spin; ψ 103°)`
- `Retrograde (vs binary orbit; 174°)`

Every planet nobody has measured reads `Prograde (assumed)`. That is the model's default, so the cell gets no border.

**Thresholds:** ψ where measured, else |λ|:

| Class | Angle |
|---|---|
| Prograde | under 70° |
| Polar | 70°–110° |
| Retrograde | over 110° |

**Provenance:**
- **Stated by the paper:** a direction the paper states in words gets a plain cell with a `SOURCE:` note. This covers all seven polar and retrograde planets.
- **Classified here:** a direction this project classified from a published angle gets an orange box and an `INFERRED:` note. That is 30 measured-prograde planets, the Solar System's included.
- **Weak or ambiguous:** these stay "assumed", with a note saying what is known. They include gam Cep b, 14 Her b–c, π Men b, AU Mic c, GJ 504 b, 51 Eri b, CD-35 2722 b, AF Lep b, τ Boo b, ups And b, and the candidates alf Cen A b, GJ 65 b and 61 Cyg b.

## The seven, each checked against the paper's own text

| Planet | Orbit Direction | Paper |
|---|---|---|
| GJ 436 b | Polar (vs stellar spin; ψ 103°) | Bourrier et al. 2022, A&A 663, A160: ψ = 103.2 +12.8/−11.5 |
| GJ 3470 b | Polar (vs stellar spin; ψ 95°) | Stefánsson et al. 2022, ApJL 931, L15: ψ = 95 +9/−8 |
| GJ 523 b | Polar (vs stellar spin; ψ ≥ 71°) | Kroft et al. 2026, arXiv:2603.24682: ψ ≥ 71.4, "Likely on a Polar Orbit" |
| GJ 3090 b | Retrograde (vs stellar spin; ψ 136°) | Carteret et al. 2026, A&A 713, L15: ψ = 136 +24/−18 |
| nu Oct A b | Retrograde (vs binary orbit; 174°) | Cefali Signor et al. 2026, A&A 712, A247: i = 174.1° to the binary; Cheng et al. 2025, Nature 641, 866 |
| GJ 896 A b | Retrograde (vs binary orbit; 148°) | Curiel et al. 2022, AJ 164, 93: Φ = 148°, "retrograde configuration" |
| VHS J125601.92-125723.9 b | Retrograde (vs host binary orbit; 118°) | Poon et al. 2024, AJ 168, 270: ψ_AB-o = 118 +12/−16 |

**Spin-orbit cells corrected:**
- GJ 3470 b now has the published ψ = 95 +9/−8. The cell held arXiv v1's 97 +16/−11.
- GJ 3090 b's cell was filled, with Carteret et al. 2026's value.

**Found but not written** (follow-ups):
- TRAPPIST-1 b–g share one λ = −2 +17/−19 (Brady et al. 2023). It supersedes Hirano et al. 2020 in the spin-orbit cells.
- bet Pic b has ψ = 3 ± 5 (Kraus et al. 2020).
- GJ 229 B (Δi ≈ 84°) is on neither planet tab.

## In the model

`hybrasil/data/catalog_loader.py` reads the cell. Two cases:

**Against the star's spin:**
- The planet stays in its plane.
- The star's axis becomes the plane's normal turned by the angle (`_spin_axes`). At 90° it lies in the plane; past 90° it points below the plane.

**Against a binary or the other planets:**
- The planet is drawn inclined by the measured angle to the reference plane, which holds the binary's orbit.
- The star's axis is assumed to follow that orbit, and is drawn dashed.
- `mechanics/orientation.py` counts such a planet's plane, not its sense, so the band and camera still open from above.

**Every axis carries an arrowhead at its north end** (`viz/static_plot.axis_points`).
