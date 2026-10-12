# ScholarPilot business plan: cfo.ai handoff

Local import bundle implemented; live cfo.ai Model and shared Page not yet created
or verified. Earlier measured token costs, margin, revenue and runway claims were
unsupported by cited evidence and have been withdrawn.

Our business question is how verification and human review affect pricing,
contribution and cash. Single-package $4.99 and ten-application season-pass $19.99
prices are planning assumptions. Real portals remain applicant handoffs.

The cfo folder contains whitelisted aggregate evidence, labeled assumptions and
an Ari brief for native Variables, Dimensions, Main/Growth/Conservative Scenarios
and verification/review sensitivity. No applicant content is exported. Run-level
LLM cost includes shared workflow overhead; it excludes review, hosting,
acquisition and payment costs.

October 11 run files record zero LLM calls/tokens. Unit cost is unavailable, not
zero. Newer metadata-only traces also report zero tokens/cost despite real calls.
Financial conclusions require actual usage and missing cost inputs.

Regenerate from repository root:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/export_cfo.py docs/evidence/run_B_1.json docs/evidence/run_B_2.json docs/evidence/run_B_3.json --output docs/evidence/cfo
```

Attach cfo/run_costs.csv and cfo/model_inputs.json in cfo.ai; send ari_prompt.md.
Supply required inputs; verify saved formulas and representative results; capture
actual Page link, scenarios and source comparison. No cfo.ai connector is available
in this chat. Live sponsor completion remains pending workspace access and inputs.

In-app follow-up: open Matches and use Business planning. The panel automatically
prepares an Ari request from current aggregate run metrics and editable assumptions.
Mock/incomplete usage is never treated as measured cost. Browser verification:
15 review minutes at $10/hour displayed $2.50; copied and downloaded request kept
that value; negative prices disabled export. TypeScript and lint passed. User
confirmed no cfo.ai workspace yet. Live creation requires signup and workspace
access; this UI is an onboarding/export workflow, not an authenticated API sync.

## Live workspace setup — 2026/10/12

User signed into cfo.ai and authorized continuation. Ari created Page
99839ceb-266e-4240-997a-82c26898a638, ScholarPilot business plan, in workspace
ayooluwa-cfoai-bdbda6b9. Native assumption/pricing/break-even tables observed.
Model creation is still running; scenario/cash validation remains pending.
All financial inputs are explicitly planning assumptions. Temporary LLM cost of
$0.01/package is a demo assumption, not measured run cost. No personal applicant
content was sent. Workspace remains private. In-app button now opens this workspace.

Live verification issue: browser observed calculation errors on scenario totals,
review workload/liquidity and break-even timing tables; Canvas runtime/data load
also failed. Ari was explicitly asked to diagnose/repair before claiming completion.
Observed baseline assumptions/pricing/break-even values: review $0.833333/package,
blended contribution $5.096956/purchase, break-even 59 purchases/month. These agree
with hand arithmetic, but are planning outputs only. Cash/scenario totals remain
unverified. Workspace access is a manual deep link, not automatic API sync.

Final live state: Ari confirmed its simplified-layout repair did not restore the
browser tables or Canvas, recorded the unsuccessful recovery, and reported escalation
to cfo.ai engineering. Native Page usability remains externally blocked. Saved
scenario totals from Ari chat agree with independent local arithmetic (see
cfo/forecast_arithmetic_check.json). Main revenue $64,967.88/ending cash $47,844.11;
Growth $444,994.36/$290,269.46; Conservative $11,586.17/$13,791.01. All are assumption
forecasts, not actuals. Proof: cfo/workspace_readback.png. No automatic API sync or
public sharing was added. Frontend TypeScript and lint passed after workspace link.
