# Assessment policy and published guidance

The app's LOW/MEDIUM/HIGH labels are **prototype asset-presence bands**, and Low/Medium/High review priority is an **application triage heuristic**. They are not military threat, readiness, warning, probability, or analytic-confidence ratings. No operational standard or certification is claimed.

## Guidance reviewed

[ODNI ICD 203, Analytic Standards](https://www.dni.gov/files/documents/ICD/ICD-203.pdf), section D.6.e.(1)-(3), requires explanation of source quality and uncertainty, and separation of evidence, assumptions, and judgments. It distinguishes the confidence behind a judgment from the likelihood of an event. It does not supply this app's numeric aircraft-count cutoffs.

[UK PHIA uncertainty guidance](https://www.gov.uk/government/publications/explaining-uncertainty-in-uk-intelligence-assessment/explaining-uncertainty-in-uk-intelligence-assessment) distinguishes its probability vocabulary from analytical-confidence ratings. Confidence considers the information base, analytical rigor, and complexity/volatility. An object detector's score is not a substitute for that assessment. These frameworks do not establish the app's aircraft presence bands.

**Implementation judgment:** the appropriate improvement is clearer evidence, assumptions, and policy provenance, rather than inventing military cutoffs from aircraft counts. Applying LOW to two aircraft or HIGH to seven remains a local demonstration choice. A valid mission-specific policy would require a defined site, normal inventory and operating patterns, comparable collection conditions, aircraft identity/capability, other sources, analyst judgment, and outcome validation. Those inputs are absent here.

## Current policy: prototype-presence-v1

| Output | Meaning | Rule |
| --- | --- | --- |
| LOW presence | Small detected count in this demonstration | Total <=2 |
| MEDIUM presence | Intermediate detected count | Total 3-6 |
| HIGH presence | Larger detected count | Total >=7 |
| Increased/Decreased/Stable | Aggregate scene-statistic direction | Weighted score >=2, <=-2, or otherwise |
| High review priority | Larger absolute asset-count change | >=2 aircraft or >=4 enabled vehicles |
| Medium review priority | Smaller count or proximity-density change | Any nonzero asset change or >=25 percentage-point density change, after checking High |
| Low review priority | No rule-triggered change | Otherwise |
| Formal analytic confidence | Requires analysis this prototype cannot perform | Not assessed |
| Military threat level | Requires operational context and validated interpretation | Not assessed |

The trend weights remain aircraft=2, vehicles=1, activity rank=2, and proximity density=2. These weights are heuristic, not calibrated probabilities. Unchanged bands and weights preserve behavior while the policy and its limits are made explicit. `assessment_policy.py` centralizes the values; JSON and text exports record the policy snapshot.

## Candidate sensitivity

Known review candidates are included in displayed totals and retained for human confirmation. The app also reports the count-change range obtained by including or excluding those known candidates:

```text
minimum delta = after primary count - before candidate-inclusive total
maximum delta = after candidate-inclusive total - before primary count
```

For nine primary aircraft before and eleven primary plus one candidate after, the displayed total change is +3 and known-candidate sensitivity is +2 to +3. If the range crosses zero, even the direction depends on candidate confirmation.

This is **not a statistical confidence interval** and does not bound unseen aircraft, false positives, cloud-obscured assets, or differences in ground coverage. A High review priority can coexist with provisional counts and unassessed analytic confidence.

## What would justify changing cutoffs

Choose an intended decision and define its consequences; collect labeled imagery representative of that use; establish normal scene inventories and collection conditions; evaluate missed detections and false positives; validate alternative rules on held-out scenes; record analyst review and performance; then version the new policy. Increasing counts alone does not justify claims about military intent or threat.
