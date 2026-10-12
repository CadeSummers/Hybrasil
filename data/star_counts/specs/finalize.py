# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Owner's choices of 6 Oct 2026 applied to the research specs: tet Cyg stays on Planetless; APM 89 and GJ 4113 skipped."""
import json, re, shutil
for f in ("A.json", "C.json"):
    shutil.copy(f, "final/" + f)
d1 = json.load(open("D1.json", encoding="utf-8"))
for s in d1:
    if s["system"] == "tet Cyg":
        s["action"] = "systems_only"
        s["rows"] = []
        s.pop("planetless_components", None)
        s.pop("host_overrides", None)
        s["systems_text"] = re.sub(r"\btet Cyg ", "13 Cyg ", s["systems_text"]).replace(
            "13 Cyg A: F3+V (host;", "13 Cyg A (= tet Cyg): F3+V (host;")
        s["stars_note"] = (
            "4 stars since 6 Oct 2026: A, B (BU 1131 B, 2.3 arcsec, 0.35 M-sun; Desort et al. 2009, A&A 506, 1469), "
            "Ea (= WDS E = GJ 765 B, 116 arcsec, common proper motion) and Eb (suspected, MSC 'a,s': Gaia DR3 RUWE 6.2 "
            "and RV variability of E). MSC WDS 19364+5013: AB,E 'Cmp', A,B 'Ch,a', Ea,Eb 'a,s'; the WDS's C, D and F "
            "are optical. The system's rows are on Planetless 4+ Stars as '13 Cyg' and stay there: its only planet "
            "claim, tet Cyg b, is on Rejected candidates (tier unlikely), so it has no live planet or candidate "
            "(owner's decision, 6 Oct 2026, reversing the 4 Oct plan to move it to Multi-stars). Was 2.")
        s["sp_paragraph"] = (
            "Count corrected on Systems only, 2 -> 4, to match its Planetless 4+ Stars rows ('13 Cyg': A, B, Ea, Eb) "
            "and the MSC (WDS 19364+5013: AB,E Cmp; A,B Ch,a; Ea,Eb a,s; WDS C, D, F optical by proper motion). It "
            "stays on Planetless 4+ Stars, not Multi-stars: its only planet claim, tet Cyg b, is on Rejected "
            "candidates (tier unlikely, likely stellar; Desort et al. 2009, A&A 506, 1469). The owner's decision of "
            "4 Oct to move it rested on that candidate and was reversed on 6 Oct. No values inferred.")
        s["flags"] = ["Stays on Planetless; Systems count and System stars text only."]
json.dump(d1, open("final/D1.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
d2 = json.load(open("D2.json", encoding="utf-8"))
for s in d2:
    if s["system"] in ("Gaia DR3 5486916932205092352", "Gaia DR3 2052469973468984192"):
        name = "APM 89" if "5486916932205092352" in s["system"] else "GJ 4113"
        s["action"] = "no_change"
        s["rows"] = []
        for k in ("host_overrides", "host_orange", "host_notes", "systems_text"):
            s.pop(k, None)
        s["stars_note"] = s["stars_note"].replace("Count unchanged. Was 2.", (
            "Count unchanged. Not added to Multi-stars (owner's decision, 6 Oct 2026): with its candidate refuted it "
            "has no live planet or candidate. Was 2."))
        s["sp_paragraph"] = (f"{name}: checked, 2 stars, count unchanged. Its only candidate is on Rejected "
                             "candidates as this binary's own orbit, so by the owner's decision it gets no "
                             "Multi-stars rows; a note on its Stars in system cell says so, with the evidence: " + s["stars_note"])
json.dump(d2, open("final/D2.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("ok")
