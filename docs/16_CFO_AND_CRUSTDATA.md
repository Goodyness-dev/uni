# 16_CFO_AND_CRUSTDATA.md

How we use cfo.ai (required, plans the business) and Crustdata (optional, research data).

## Part A: cfo.ai

### A1. What it is and what we need from it

cfo.ai sells Ari, an AI finance coworker. You ask a business question and Ari builds or updates a live financial Model (Variables, Dimensions, Scenarios) you can open and change. Pages turn model data into tables, charts and written context, and a Page can be shared read only (you choose the Scenario, you can add a password). Ari is also reachable through MCP, Slack and an API (VERIFY MCP from Antigravity).

Judges score how well we used cfo.ai to plan the business AROUND the agent: pricing, costs, revenue, runway. The plan must be included in the submission.

### A2. Setup (Saturday)

1. Sign up through the hackathon link (cfo.ai/neathacks). A card is required.
2. Immediately cancel the subscription in Settings then Billing. Screenshot the cancelled state. (The Startup plan was about 295 dollars a month as of September 2026, so do not forget this.)
3. Confirm in Discord that the credits arrived.
4. Ask Ari one small test question.

### A3. Inputs we enter (fill after run B and the failure runs)

Every number below needs a source and a date. Costs are MEASURED. Prices and growth are ASSUMPTIONS and are labeled that way in the plan and in the video.

Unit cost inputs (measured):
1. Tokens per application, input and output: ______ / ______ (source: neatlogs run B, tag `run_B`).
2. Primary model price per million tokens, input and output: ______ / ______ (source: provider price page, date ______).
3. Fallback model price per million tokens: ______ / ______.
4. LLM cost per application in USD: ______ (neatlogs Analytics or our `RunMetrics.cost_usd` divided by applications).
5. Share of calls that used the fallback model: ______ percent.
6. Verifier overhead (extra tokens from revision rounds and the Challenger): ______ percent (run B versus run A).
7. Latency per application: ______ seconds.
8. Crustdata credits per scholarship (if live research was measured): ______ and the credit price: ______.
9. Email and Telegram cost per application: 0 (confirm).

Cost structure (assumptions, cite price pages):
1. Hosting per month for a minimal deployment: ______.
2. Browser worker hosting per month (production plan only): ______.
3. Support and review time per month: ______ hours at ______.
4. Payment processing fee percent: ______ (processor: ______).

Pricing tiers to test (assumptions, in USD and Naira at the rate of the day, record the rate and date):
1. Free: matching and research preview only.
2. Per application: ______ USD for one tailored, verified application.
3. Season pass: ______ USD for up to ______ applications over 3 months.
4. Coach plan (stretch): ______ USD per seat per month.

Revenue scenarios (assumptions):
1. Base: paying users in month 1 ______, growth ______ percent per month, applications per paying user ______.
2. Growth: campus ambassadors and university partnerships, growth ______ percent.
3. Conservative: slower growth, more fallback use, lower conversion.
4. Seasonality: most deadlines cluster in a few months, so revenue peaks before deadlines.

Cash and runway:
1. Starting cash for the plan ______ USD (assumption, label it).
2. One time costs ______ USD (legal, privacy review).
3. Monthly fixed costs ______ USD.

### A4. Prompts to paste into Ari (adapt the numbers)

1. "Build a financial model for an AI scholarship application agent. Use these measured unit costs: [paste]. Revenue comes from three tiers: [paste]. Create Base, Growth and Conservative scenarios with these assumptions: [paste]. Show gross margin per tier, monthly revenue and cost, cash, and runway in months for each scenario."
2. "Which pricing tier should we lead with, and why? Show the margin for each."
3. "Test sensitivity: what happens to margin and runway if LLM cost per application goes up or down by 50 percent, and if the verifier needs 3 rounds instead of 2?"
4. "At what number of paying users per month do we break even in each scenario?"
5. "Create a Page named ScholarPilot business plan with: pricing tiers, unit economics, the three scenarios in a chart, runway, and a short written summary of the biggest risks. Make it shareable read only."
6. "Show me how the cost per application number links to its source assumption." (use this on camera, it demonstrates traceability)

### A5. Outputs to capture

1. [ ] The shared read only Page link (add a password only if needed, and put it in the submission if so).
2. [ ] Screenshots of pricing and margin, cost per application, the three scenarios, runway and break even.
3. [ ] `docs/evidence/business_plan.md`: half a page in plain English (who pays, how much, cost per application, margin, runway, biggest risk, which numbers are measured and which are assumptions).
4. [ ] A screenshot showing the neatlogs cost number next to the Model input that uses it.

### A6. Demo coverage for cfo.ai (about 20 seconds)

1. Architecture: neatlogs cost data feeds the Model.
2. Implementation: the inputs and Variables.
3. Runtime: change a price and watch margin and runway update.
4. Reasoning: why that lead tier.
5. Result: margin, runway and the shared Page.

## Part B: Crustdata (optional)

### B1. Facts

1. Crustdata is a data API for companies and people, plus Web Search and Web Fetch. Every request needs the API key and a version header (a date in November 2025, shown in the docs).
2. Web Search (live): one query across web, news, scholar articles, scholar authors, AI overview and social sources. 1 credit per query. The scholar sources suit professor research areas and publications.
3. Web Fetch (live): up to 10 URLs per request, returns page title and HTML. 1 credit per page.
4. The hackathon gives 5,000 credits to everyone participating (confirm how to claim in Discord).

### B2. How we use it (only if time allows, task B28)

1. Per real scholarship (top 2 only): 1 search for the programme and its priorities, 1 or 2 scholar author or article searches for the programme lead, 1 news search, up to 4 page fetches. About 8 credits.
2. The existing rule stays: every dossier fact needs a source URL and a snippet that really appears in the fetched text (checked in code).
3. Cache results into `dossier_cache` so the demo never depends on live calls.
4. Trace each call as a TOOL span (`crustdata_search`, `crustdata_fetch`) with `credits_used`.
5. Failure: if Crustdata fails or credits run out, use the cache (recovery decision `research_unreachable`).

### B3. Rules

1. Never use the human mode option (it tries to get past bot protection, which breaks our rules).
2. Public academic information only. No personal contact details or social profiles of third parties.
3. Prefer search with scholar sources over person profile enrichment.
4. If setup takes more than 45 minutes, skip it. The demo does not need it: mock listings research our own portal pages live, and real listings use cached or degraded dossiers.
5. Add the measured credits per scholarship to the cfo.ai cost inputs.
