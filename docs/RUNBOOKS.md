# ScholarPilot Production Incident Runbooks

This document provides step-by-step standard operating procedures (SOPs) for site reliability engineers and operators running ScholarPilot in staging and production.

---

## Runbook 1: Emergency Submission Halt (Kill Switch)

### Trigger
- High error rate on portal submissions (> 5%).
- Partner portal structural change or unexpected anti-bot challenge surge.
- Regulatory or compliance stop order.

### Action
1. **Activate Global Kill Switch immediately**:
   - In container environment:
     ```bash
     export KILL_SWITCH_ACTIVE=true
     # or restart container with environment flag
     docker compose exec api sh -c "export KILL_SWITCH_ACTIVE=true"
     ```
   - In Kubernetes / ConfigMap: Set `KILL_SWITCH_ACTIVE: "true"` and rollout restart deployment.
2. **Verify Halt**:
   - Check application submission logs:
     ```
     grep "KillSwitchActiveError" /var/log/scholarpilot.log
     ```
   - Ensure all pending submissions transition cleanly or stay paused in `approved` / `drafting` state without firing external requests.
3. **Deactivation & Resume**:
   - Once root cause is resolved, reset `KILL_SWITCH_ACTIVE=false`.
   - Queued applications can be resumed via `POST /v1/applications/{id}/resume`.

---

## Runbook 2: LLM Spending Cap Breach & Quota Exhaustion

### Trigger
- User alert or automated alert: `LLMSpendLimitExceeded`.
- Structured log event: `"Daily user LLM spending cap reached"`.

### Impact
- Drafter and Edge Finder agents temporarily paused for affected user (or globally if `GLOBAL_DAILY_CAP` is reached).

### Action
1. **Audit Cost Consumption**:
   - Query the `spend_tracker` metrics or application logs:
     ```bash
     grep "spend_tracker" /var/log/scholarpilot.log | jq .
     ```
2. **Legitimate Surge Adjustment**:
   - For high-volume student batches or scholarship deadlines, update cap in `.env`:
     ```bash
     USER_DAILY_LLM_CAP=2.50
     GLOBAL_DAILY_LLM_CAP=100.00
     ```
3. **Prompt Injection / Loop Check**:
   - Verify if an untrusted portal essay prompt caused infinite drafting loops.
   - Run `sanitize_untrusted_content` audits on recent scholarship intakes.

---

## Runbook 3: CAPTCHA / Anti-Bot Challenge Surges

### Trigger
- Sudden influx of applications transitioning to `needs_human`.
- Notification metric: `blocker_type == 'captcha'`.

### Policy Reminder (Hard Rule)
- **NEVER attempt to bypass, solve, or work around CAPTCHAs programmatically.**
- Detect them, freeze browser, snapshot screenshot, and notify the student.

### Action
1. **Verify Screenshots**:
   - Review captured images in `storage/screenshots/` to confirm valid challenge appearance.
2. **Notify Impacted Students**:
   - Verify Telegram / Webhook dispatch sent human verification alert with portal URL.
3. **Post-Solution Resume**:
   - Once student completes verification, application is resumed via `POST /v1/applications/{id}/resume`.

---

## Runbook 4: Encryption Key Rotation (AES-256 Fernet)

### Trigger
- Scheduled 90-day security key rollover.
- Suspected secret leakage or operator credential rotation.

### Action
1. **Generate New Fernet Key**:
   ```python
   from cryptography.fernet import Fernet
   new_key = Fernet.generate_key().decode()
   ```
2. **Re-encrypt Portal Credentials**:
   - Run migration script decrypting with old `ENCRYPTION_KEY` and encrypting with `NEW_ENCRYPTION_KEY`.
3. **Deploy Config**:
   - Update `ENCRYPTION_KEY` environment variable across API and worker clusters.

---

## Runbook 5: GDPR / NDPR Right to be Forgotten Request

### Trigger
- User requests permanent erasure of personal data or calls `DELETE /v1/account`.

### Action
1. **API Execution**:
   - The user or support operator issues:
     ```bash
     curl -X DELETE https://api.scholarpilot.africa/v1/account \
       -H "X-API-Key: sp_live_..."
     ```
2. **Verification Checklist**:
   - `Profile` record deleted from `profiles` table.
   - `Document` metadata and local file references purged.
   - `Draft` records purged.
   - `User` email replaced with anonymized hash (`purged-...`).
   - Append-only event history preserved for non-PII system accounting.
