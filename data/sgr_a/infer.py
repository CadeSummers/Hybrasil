# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Class, Teff and mass for an S-star no paper has typed: from its K magnitude, as a main-sequence dwarf.

    M_K = K - A_K - 5 log10(R0 / 10 pc)

- K: Gillessen et al. 2017, table 3.
- A_K = 2.42 +/- 0.10 toward Sgr A* (r < 0.5"): Fritz et al. 2011, ApJ 737, 73 (2011ApJ...737...73F).
- R0 = 8277 pc: GRAVITY Collaboration 2022, A&A 657, L12.

M_K is then interpolated in the mean dwarf sequence of Pecaut & Mamajek 2013 (ApJS 208, 9; the 2022.04.16 version of
Mamajek's table, cat/EEM_dwarf_UBVIJHK_colors_Teff.txt), giving the nearest spectral type and an interpolated Teff
and mass.

**Valid only for early-type stars.**  The early-type S-stars are B dwarfs (Habibi et al. 2017 find S2 and the other
bright ones on the main sequence, about 6.6 Myr old).  A late-type S-star is a K/M giant of the old nuclear
cluster, whose mass its K magnitude barely constrains.  Such a star gets a class ("late-type giant") and a WEAK
nominal mass of 1.5 M_sun (range 0.8-3), flagged as such.

The scatter is measured, not assumed: `calibrate()` compares the relation with every published mass in research/.
"""
from __future__ import annotations

import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
EEM = HERE / "cat" / "EEM_dwarf_UBVIJHK_colors_Teff.txt"
A_K, A_K_ERR = 2.42, 0.10
A_K_BIB = "2011ApJ...737...73F"
R0_PC = 8277.0
R0_BIB = "2022A&A...657L..12G"
EEM_BIB = "2013ApJS..208....9P"
LATE_MASS, LATE_RANGE = 1.5, (0.8, 3.0)


def dwarf_sequence() -> list[tuple[str, float, float, float]]:
    """(SpT, Teff, M_Ks, Msun) for every dwarf row with all three, brightest first."""
    out, head = [], None
    for line in EEM.read_text().splitlines():
        if line.startswith("#SpT"):
            head = line[1:].split()
            if out:
                break                       # the first table only
            continue
        if head is None or not line.strip() or line.startswith("#"):
            continue
        f = line.split()
        if len(f) < len(head):
            continue
        row = dict(zip(head, f))
        try:
            out.append((row["SpT"], float(row["Teff"]), float(row["M_Ks"]), float(row["Msun"])))
        except (ValueError, KeyError):
            continue
    return sorted(out, key=lambda r: r[2])


def absolute_k(kmag: float, r0_pc: float = R0_PC, a_k: float = A_K) -> float:
    return kmag - a_k - 5.0 * math.log10(r0_pc / 10.0)


def as_dwarf(kmag: float) -> dict:
    """{'spt', 'teff', 'mass', 'mk'} for an early-type S-star of magnitude K."""
    seq = dwarf_sequence()
    mk = absolute_k(kmag)
    if not seq[0][2] <= mk <= seq[-1][2]:
        raise ValueError(f"M_K {mk:.2f} is off the dwarf sequence")
    for (s0, t0, m0, w0), (s1, t1, m1, w1) in zip(seq, seq[1:]):
        if m0 <= mk <= m1:
            f = (mk - m0) / (m1 - m0) if m1 != m0 else 0.0
            # mass and Teff interpolated in log, the way the sequence runs
            teff = 10 ** (math.log10(t0) + f * (math.log10(t1) - math.log10(t0)))
            mass = 10 ** (math.log10(w0) + f * (math.log10(w1) - math.log10(w0)))
            return {"spt": s0 if f < 0.5 else s1, "teff": teff, "mass": mass, "mk": mk}
    raise AssertionError("unreachable")


def mass_range(kmag: float, k_err: float = 0.1) -> tuple[float, float]:
    """The mass the dwarf relation gives at K +/- (k_err + A_K's error, in quadrature)."""
    d = math.hypot(k_err, A_K_ERR)
    return as_dwarf(kmag + d)["mass"], as_dwarf(kmag - d)["mass"]


def calibrate(published: dict[str, tuple[float, float]]) -> dict:
    """{star: (K, published mass)} -> how far the relation lands from each, and the scatter in dex."""
    res = {s: math.log10(as_dwarf(k)["mass"] / m) for s, (k, m) in published.items()}
    n = len(res)
    mean = sum(res.values()) / n if n else 0.0
    rms = math.sqrt(sum(v * v for v in res.values()) / n) if n else 0.0
    return {"n": n, "mean_dex": mean, "rms_dex": rms, "residuals": res}
