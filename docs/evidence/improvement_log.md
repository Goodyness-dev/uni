# Neatlogs Improvement Log

This log records iterative agent improvements driven by observability insights from Neatlogs traces and guardrails, tracked alongside Entire checkpoints.

---

## Improvement Loop 1: Verifier Self-Healing & Hallucination Elimination

### 1. Metadata
- **Date**: October 11, 2026
- **Runs Analyzed**: `run_20261011_007`, `run_20261011_008` (Tag: `run_A,evidence`)
- **After Runs**: `run_20261011_009`, `run_20261011_010` (Tag: `run_B,evidence`)
- **Neatlogs Project ID**: `72601136-9c61-4e1b-8644-8f9d7a83aedf`
- **Tracing Host**: `https://app.neatlogs.com`
- **Method Note**: Evaluated via Neatlogs SDK trace outputs and run evidence records (`docs/evidence/run_A_1.json` through `run_B_2.json`).

### 2. Trace Finding (The Problem in Run A)
In the baseline Mode A runs, the Coordinator executed Scout -> Matcher -> Researcher -> Edge Finder -> Tailor -> Verifier (`verify_mode_a`).
The Neatlogs `GUARDRAIL` evaluation spans revealed:
- Across 2 scholarship applications (`real_one` and `mock_captcha_award`), exactly **16 claims** in the generated CV summary and essay were classified as `unsupported` or ungrounded against the applicant's intake facts.
- Specifically, the generative Tailor agent had hallucinated leadership titles ("President" instead of Assistant Coordinator) and unverified metrics that lacked source IDs.
- Because `verify_mode_a` performed only an observational audit without active enforcement, all **16 unsupported claims** flowed unchecked into the final package (`unsupported_final: 16`).

### 3. Change Implemented (Task B15)
To eliminate unverified claims, we engineered `verify_mode_b` in `backend/app/agents/verifier.py` and `tailor_revise` in `backend/app/agents/tailor.py`:
1. **Iterative Audit-Revision Loop**: Flagged problem segments are passed to `tailor_revise` with grounding source IDs for up to 2 targeted rewriting rounds.
2. **Deterministic Removal Fallback**: Any segment retaining unsupported claims after 2 revision rounds is deterministically assigned `status = "removed"` and recorded as a typed `RemovedClaim`.
3. **Adversarial Challenger Integration**: Supported claims undergo cross-examination against source dossiers.
4. **Sensitive Post-Scan**: Scrubs any newly introduced sensitive keywords.

### 4. Verification & Metrics (Before vs. After)

| Metric | Before (Run A Baseline) | After (Run B Enforcement) | Improvement |
| :--- | :---: | :---: | :---: |
| **Initial Unsupported Claims** | 16 | 16 | Baseline matched |
| **Final Unsupported Claims** | **16** | **0** | **-100% (Zero Hallucinations)** |
| **Removed Claims / Segments** | 0 | 16 | Persistent hallucinations excised |
| **Personal References Sourced** | 1 | 1 | Real source grounding preserved |

### 5. Git & Entire Tracking
- **Fix Commit**: `154c4cc` (`feat(verifier): mode b self-healing enforcement loop and comparative evidence with neatlogs guardrails [B15] [B16]`)
- **Entire Checkpoint**: Recorded on commit `154c4cc` on branch `main`.
