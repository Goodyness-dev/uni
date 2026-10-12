# ScholarPilot: economics of trustworthy applications

Attach run_costs.csv and model_inputs.json to Ari. Import CSV as source data.
Inspect and reuse existing model objects; preserve unrelated content. Build a
native Model with editable Variables, not a static report. usage_unavailable is
unknown, never free. recorded_usage is pipeline evidence, not billing reconciliation.
Keep filenames, run IDs and trace URLs beside inputs. All supplied assumptions
and scenario values, including payment fees, are unvalidated planning assumptions.
Ask for required_inputs before conclusions. Use USD only.

Create ScholarPilot business plan, with twelve monthly periods, pricing, review
cost, cash and risks. Dimensions: Pricing Tier (Single, Season), Cost Category,
Date.Month. Keep Main baseline; add Growth and Conservative. Ask for Last close;
do not invent Actuals. Ask for purchase mix, refunds, conversion and collection
and recognition timing. Single uses 1 application; Season uses full limit of 10.
Pass revenue is purchases times pass price, never applications times pass price.

Resolve names and validate these formulas before saving:
Review Unit Cost: `Review Minutes` / 60 * `Review Hourly Cost`
Delivery Unit Cost: `Verified LLM Unit Cost` + `Review Unit Cost`
Revenue: Purchases * Price
Delivery Cost: Purchases * `Applications per Purchase` * `Delivery Unit Cost`
Payment Cost: Revenue * `Payment Percent` + Purchases * `Payment Fixed`
Contribution: Revenue - `Delivery Cost` - `Payment Cost` - `Refund Cost`
Contribution Margin: if(Revenue <> 0, Contribution / Revenue, 0)
Operating Cash Flow: Contribution - `Fixed Costs` - `Acquisition Cost` - `Free Preview Cost`
Ending Cash: previous ending cash plus operating cash flow, seeded first month
with Starting Cash. Confirm collection/payment timing before writing cash rules.

Forecast scopes require Date.Month. SUM flows; LAST cash; recompute ratios from
totals. Runway only exists with positive net burn; otherwise not applicable, not
infinite. Break-even needs positive contribution per purchase and explicit tier mix.
Show LLM cost at 0.5x/1x/1.5x and review minutes at 0/5/15. Extra verifier rounds
require measured costs or explicitly assumed multipliers. Our distinctive question:
when does human review dominate trustworthy AI cost?

Read saved tables in all Scenarios. Check one Single and one Season purchase by
hand, reconcile monthly/annual flows and confirm LAST cash. Keep unknowns visible.
Capture real Page link and screenshots only after readback. Ask before public
sharing. ScholarPilot automatically submits only to its demo portal; real portals
are applicant handoffs.
