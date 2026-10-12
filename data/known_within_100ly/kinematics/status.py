# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Where the Known within 100ly motion pipeline stands, and the next thing to run.

    python status.py
"""
from common import BATCHES, BATCH_CAP, MAX_PARALLEL, load, progress

STEPS = [
    ("P0_targets", "python targets.py"),
    ("P1_gaia", "python gaia.py"),
    ("P2_simbad", "python simbad.py"),
    ("P3_write", "python merge.py && python write.py bulk"),
    ("P4_batches", "python merge.py --batch"),
]


def main():
    p = progress()
    for ph, cmd in STEPS:
        s = p["phases"].get(ph, {})
        print(f"{ph:12} {s.get('state', 'pending'):8} {s.get('at', '')}")
        if s.get("state") != "done":
            print(f"\nNEXT: {cmd}   (in data/known_within_100ly/kinematics/)")
            return
    batches = list((load(BATCHES) or {}).get("batches", {}))
    st = {b: p["batches"].get(b, {}).get("state", "pending") for b in batches}
    capped = batches[:BATCH_CAP]
    by = {k: [b for b in capped if st[b] == k] for k in ("done", "partial", "running", "pending")}
    unwritten = [b for b in by["done"] + by["partial"] if not p["batches"][b].get("written")]
    print(f"\nP4 research: {len(batches)} batches, cap {BATCH_CAP}. " + ", ".join(f"{k} {len(v)}" for k, v in by.items()))
    print(f"  RV found so far: {sum(p['batches'].get(b, {}).get('rv', 0) or 0 for b in batches)}; "
          f"past the cap (not to be launched without the user): {batches[BATCH_CAP:]}")
    if by["running"]:
        print(f"  marked running: {by['running']} -- if no agent is alive for them (a new session), relaunch them: "
              "an agent resumes from its own agent_output file.")
    if unwritten:
        print(f"  finished but not yet written to the sheet: {unwritten}")
    nxt = (by["partial"] + by["pending"])[:max(0, MAX_PARALLEL - len(by["running"]))]
    if nxt:
        print(f"\nNEXT: launch agents for {nxt} with the prompt in README.md (python ledger.py launch {' '.join(nxt)})")
    elif unwritten:
        print("\nNEXT: python merge.py && python write.py wave, then mark them written (README.md)")
    elif not by["running"]:
        print(f"\nNEXT: P4 is done to the cap. P5 (plotting) -- see the plan; P5 state: "
              f"{p['phases'].get('P5_plot', {}).get('state', 'pending')}")


if __name__ == "__main__":
    main()
