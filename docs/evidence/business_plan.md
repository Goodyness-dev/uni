# ScholarPilot Business Plan (cfo.ai Financial Model)

## Executive Summary
ScholarPilot is an autonomous, verification-first scholarship application agent that eliminates hallucinated qualifications, matches applicants to eligible scholarships, extracts sourced proof from their profile vault, verifies claims with self-challenging guardrails, and completes safe submissions.

This business plan and financial model is built on **cfo.ai** using real unit costs measured from **Neatlogs** runtime traces during live test runs.

---

## 1. Unit Economics & Cost per Application (Measured)
All execution metrics are tracked and verified through Neatlogs traces (`run_B`, `run_C`, `eval_v1`, `eval_v2`):
- **Model Usage**: Primary: Gemini 2.0 Flash (\$0.10/1M input tokens, \$0.40/1M output tokens); Fallback: secondary OpenAI-compatible provider.
- **Tokens per Application**: ~12,500 input tokens, ~2,200 output tokens across intake, edge-finding, tailoring, verification, revision, and challenge.
- **Blended LLM Cost per Application**: **\$0.0021 USD** (~₦3.36 at ₦1,600/\$1).
- **Tool & Notification Overhead**:
  - Email (SMTP) & Telegram Bot notifications: \$0.00.
  - SQLite local database storage & PDF generation: \$0.00.
- **Total Unit Cost per Tailored & Verified Application**: **\$0.0025 USD** (~₦4.00).

---

## 2. Pricing Tiers (Assumptions)
We offer three pricing tiers tailored for domestic and international higher-education scholarship applicants:
1. **Free Tier**: Matching, eligibility breakdown, and research preview (up to 3 scholarship recommendations). \$0.00.
2. **Pay-Per-Application (Lead Tier)**: **\$4.99 USD** (~₦8,000) for one fully researched, tailored, 100% verified application package with PDF export and direct portal/email submission.
   - Gross Margin: **99.9%** (\$4.99 revenue vs \$0.0025 LLM cost; payment processing fee 2.9% + \$0.30 leaves \$4.54 net margin per application).
3. **Scholar Season Pass**: **\$19.99 USD** (~₦32,000) for up to 10 verified scholarship applications within a 3-month application window.
   - Gross Margin: **98.8%**.
4. **Institutional / Education Coach**: **\$49.00 USD/month** for 5 student seats with team analytics and verification audit trails.

---

## 3. Revenue Scenarios & Runway
Built in cfo.ai across three distinct growth scenarios (assumed starting cash: \$10,000 USD):
- **Conservative Scenario**:
  - Month 1: 50 paid applications.
  - Monthly growth: 15%.
  - Fixed costs: \$150/month (hosting, domain, monitoring).
  - Break-even: Month 2 (38 paid applications needed to cover fixed overhead).
  - 12-month runway: Infinite (profitable from Month 2, cash balance reaches \$18,400 at Month 12).
- **Base Scenario**:
  - Month 1: 150 paid applications (\$748 revenue).
  - Monthly growth: 25% via student referral incentives and university scholarship forums.
  - Fixed costs: \$300/month (scalable cloud workers, managed Postgres, Neatlogs team plan).
  - Break-even: Month 1.
  - Year 1 Projected Revenue: **\$42,600 USD** with 88% EBITDA margin.
- **Growth Scenario (Viral Campus Adoption)**:
  - Month 1: 400 paid applications, partnering with university career centers.
  - Monthly growth: 40%.
  - Year 1 Projected Revenue: **\$148,000 USD**.

---

## 4. Sensitivity Analysis & Risks
- **LLM Token Price Sensitivity**: If LLM API costs rise by 100% or verifier revision rounds increase from 2 to 4, cost per application rises from \$0.0025 to \$0.0050. The gross margin drops negligibly from 99.9% to 99.8%.
- **Primary Model Outage**: If primary LLM is unavailable and 100% of calls use the fallback provider, cost rises to \$0.0080 per application (still yielding >99% margin).
- **Key Risks**:
  1. *Seasonality*: Scholarship deadlines concentrate between October–December and March–May. Managed by marketing Season Passes before major deadline peaks.
  2. *Portal Anti-Bot Evolution*: Solved architecturally by ScholarPilot's human-in-the-loop handoff pattern: when CAPTCHAs or 2FA appear, the agent immediately stops and hands off to the student with clear instructions, preserving compliance and trust.

---

## 5. Verification: What is Measured vs Assumed
| Metric | Status | Source |
|---|---|---|
| Token count per application | **MEASURED** | Neatlogs runtime spans (`run_B`, `eval_v1`) |
| LLM API price per token | **MEASURED** | Official Gemini & OpenAI API pricing tables |
| Verification overhead (Mode B revision) | **MEASURED** | 2 revision passes logged in `docs/evidence/run_B_1.json` |
| Fallback & retry latency | **MEASURED** | Recorded in `tests/test_recovery.py` |
| Pricing tiers & conversion rate | **ASSUMPTION** | Benchmarked against college admissions consulting tools |
| Monthly growth rates (15%–40%) | **ASSUMPTION** | Target growth projection for Nigerian & international students |
