# Run A vs Run B Comparative Evaluation

Comparative analysis of ScholarPilot application generation: **Mode A** (Baseline: single-pass audit without enforcement) versus **Mode B** (Self-healing enforcement loop: iterative audit, revisions, segment removal fallback, challenger, and sensitive post-scan).

Both modes were executed twice on the identical synthetic persona (Adebayo Nnamdi) applying to the same top 2 matched scholarships (`real_one` / Nigerian Women in Tech Merit Award and `mock_captcha_award` / Future Builders STEM Grant).

---

## 1. Summary Comparison (Medians across 2 runs)

| Metric | Mode A (Baseline) | Mode B (Enforced) | Delta / Impact |
| :--- | :---: | :---: | :---: |
| **Total Extracted Claims** | 16 | 16 | 0 |
| **Unsupported Claims (Initial)** | 16 | 16 | 0 |
| **Unsupported Claims (Final Output)** | **16** | **0** | **-100% (16 claims neutralized)** |
| **Removed Claims / Segments** | **0** | **16** | **+16 segments removed** |
| **Overturned by Challenger** | 0 | 0 | 0 |
| **Sourced Personal References** | 1 | 1 | Preserved |
| **Tokens per Application** | 0 (demo client) | 0 (demo client) | 0 |
| **Cost (USD)** | \$0.00 | \$0.00 | \$0.00 |
| **Latency (s)** | 0.00s | 0.00s | 0.00s |
| **Recovery Decisions / Retries** | 0 | 0 | 0 |

---

## 2. Per-Run Breakdown

### Run A (Baseline: No Enforcement)
- **Run A_1** (`run_20261011_007`):
  - Application 1 (`real_one`): 11 unsupported claims audited, 11 left in final output (0 removed).
  - Application 2 (`mock_captcha_award`): 5 unsupported claims audited, 5 left in final output (0 removed).
  - Total unsupported in final output: **16 / 16**.
- **Run A_2** (`run_20261011_008`):
  - Application 1 (`real_one`): 11 unsupported claims audited, 11 left in final output (0 removed).
  - Application 2 (`mock_captcha_award`): 5 unsupported claims audited, 5 left in final output (0 removed).
  - Total unsupported in final output: **16 / 16**.

### Run B (Self-Healing Enforcement Loop)
- **Run B_1** (`run_20261011_009`):
  - Application 1 (`real_one`): 11 unsupported claims audited initially, **0** left in final output (**11 segments removed**).
  - Application 2 (`mock_captcha_award`): 5 unsupported claims audited initially, **0** left in final output (**5 segments removed**).
  - Total unsupported in final output: **0 / 16**.
- **Run B_2** (`run_20261011_010`):
  - Application 1 (`real_one`): 11 unsupported claims audited initially, **0** left in final output (**11 segments removed**).
  - Application 2 (`mock_captcha_award`): 5 unsupported claims audited initially, **0** left in final output (**5 segments removed**).
  - Total unsupported in final output: **0 / 16**.

---

## 3. What We Changed and Why

In Mode A, the Verifier executes a single verification pass (`verify_mode_a`) using `audit()`, logging `GUARDRAIL` results and counting unsupported claims, but it outputs the drafted application without rectifying ungrounded or fabricated statements. As a result, 16 hallucinations/unsupported claims (such as inflated titles, fabricated metrics, or unverified claims from the generative drafting step) remained in the final submissions.

In Mode B (`verify_mode_b`), we instituted an iterative self-healing enforcement loop:
1. **Audit Round 1**: Identifies all ungrounded sentences and non-supported claims.
2. **Targeted Revision Rounds (up to 2 rounds)**: Invokes `tailor_revise` targeting strictly the flagged segment indices to rewrite sentences grounded in verified sources.
3. **Deterministic Removal Fallback**: Any segment retaining unsupported claims after revision is deterministically marked `status = "removed"`, and a structured `RemovedClaim` event is emitted.
4. **Adversarial Challenger**: Cross-examines remaining supported claims against the source dossier to guard against subtle exaggerations.
5. **Sensitive Post-Scan**: Scrubs any newly introduced or residual sensitive personal disclosures.

**Result**: 100% elimination of unsupported claims in the final package (`unsupported_final: 0`), fulfilling ScholarPilot's core hackathon premise: zero unverified claims submitted to scholarship providers.
