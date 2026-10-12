# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIN = str(HERE)
SRC = HERE.parents[1] / "pack" / "BRIEF.md"

s = SRC.read_text(encoding="utf-8")
s, n = re.subn(r"`<scratchpad>\\pack`",
               lambda m: f"`{WIN}\\pack`", s)
assert n == 1, n
s = s.replace("Output directory, referred to as `OUT`: the sibling `...\\scratchpad\\out`",
              f"Output directory, referred to as `OUT`: `{WIN}\\out`")
assert f"{WIN}\\out" in s
s = s.replace("the pack holds today's pull", "the pack holds the 26 September 2026 pull, `toi_nasa_2026-09-26.csv`")
s = s.replace("(the confirmed\n  tab, rows 2-540)", "(the confirmed\n  tab)")

EXTRA = """## What changed since the first run (read this first; 26 September 2026)

This is the **resumed** search. The first run (23-24 September) was halted part-way;
its records are in `PACK/previous_output/*.json`. The pack CSVs were re-exported from
the live sheet on 26 September, so they include everything the first run added.

- **`PACK/rejected_candidates.csv` is new.** The workbook now has a "Rejected
  candidates" tab: 25 candidates examined and turned down (TOI FP/FA, refuted Gaia
  astrometric signals, RV signals shown to be rotation). **Never propose any of them
  as a candidate**, under any alias. If you meet one, record it in
  `considered_not_added` with reason "already on Rejected candidates". If you find
  evidence that reverses a rejection (a later paper confirming it), report that under
  `incidental_finds_outside_my_scope` instead.
- **Keep reporting `unlikely` candidates**, tiered `unlikely` with the reason. The
  writer files them on the Rejected candidates tab, which the viewer never draws.
- **`PACK/unconfirmed_existing.csv`** now has 76 rows (the first run's finds are in
  it). `PACK/systems.csv` has 362 systems, including the 44 added on 24 September.
- **Read your own previous file first if one exists**
  (`PACK/previous_output/<your id>.json`). Do not redo a system it already covered
  unless your instructions say to, and carry its records over into your new output so
  that your file is complete on its own.
- Save to `OUT/<AGENT_ID>.json`, never into `PACK`.

"""
s = s.replace("## Hard rules", EXTRA + "## Hard rules", 1)
(HERE / "pack" / "BRIEF.md").write_text(s, encoding="utf-8")
print(s[:1200])
