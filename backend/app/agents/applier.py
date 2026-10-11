"""Applier agent: handles automated submissions, blocker detection, and human handoff."""
from pathlib import Path
import re
import time
from typing import Any

import httpx

from app.config import settings
from app import db, notify
from app.agents import scout
from app.errors import RunContext, SmtpError
from app.tracing import agent_span, recovery_decision, trace_block


def check_blockers(apply_url: str, ctx: RunContext | None = None) -> list[str]:
    """Scans application page HTML for automation blockers (CAPTCHA, login gate, passwords).

    Returns list of detected blocker types.
    """
    blockers: list[str] = []
    with trace_block("blocker_check", "TOOL", url=apply_url):
        try:
            resp = httpx.get(apply_url, timeout=10.0, follow_redirects=True)
            # Check redirect to login path
            if "/login" in str(resp.url.path).lower() or any("/login" in str(h.url.path).lower() for h in resp.history):
                blockers.append("login_wall")

            html = resp.text.lower()
            # 1. Element id captcha_challenge
            if 'id="captcha_challenge"' in html or "id='captcha_challenge'" in html:
                blockers.append("captcha_challenge")

            # 2. iframe with recaptcha, hcaptcha, or turnstile
            if "<iframe" in html:
                if any(provider in html for provider in ("recaptcha", "hcaptcha", "turnstile")):
                    blockers.append("captcha_iframe")

            # 3. Password input
            if re.search(r'<input[^>]+type=["\']password["\']', html):
                blockers.append("password_input")

        except Exception as e:
            # If network error connecting to portal, treat as blocker / unreachable
            blockers.append(f"unreachable: {str(e)}")

    return blockers


@agent_span("applier", role="applier", goal="submit verified scholarship applications")
def apply(app_id: str, ctx: RunContext | None = None) -> str:
    """Applies to a scholarship across portal, email, or package channels.

    Returns one of: 'submitted', 'awaiting_user', 'prepared', 'unconfirmed', 'failed'.
    """
    ctx = ctx or RunContext()
    app = db.get_application(app_id)
    if not app:
        return "failed"

    listing_id = app.get("listing_id", "")
    listing = scout.get_listing(listing_id)
    if not listing:
        return "failed"

    tailored_data = app.get("tailored") or {}
    tailored_mode = tailored_data.get("mode", "full")

    # 1. Channel package_only or notes_only mode -> prepared
    if listing.channel == "package_only" or tailored_mode == "notes_only":
        return "prepared"

    # Extract applicant details from preferences
    prefs = db.get_preferences() or {}
    full_name = prefs.get("full_name") or "Applicant"
    email = prefs.get("email") or "applicant@example.com"

    # 2. Channel: email
    if listing.channel == "email":
        subject = f"Application for {listing.name}: {full_name}"
        body = (
            f"Dear Selection Committee,\n\n"
            f"Please find my application attached.\n\n"
            f"Kind regards,\n"
            f"{full_name}"
        )

        backend_dir = Path(__file__).resolve().parent.parent.parent
        pkg_dir = backend_dir / "data" / "packages" / app_id
        attachments = [
            str(pkg_dir / "cv.pdf"),
            str(pkg_dir / "essay.txt"),
        ]

        target_email = settings.demo_inbox_email or listing.email or "scholarship@demo.local"

        try:
            notify.send_email(
                to=target_email,
                subject=subject,
                body=body,
                attachments=attachments,
                ctx=ctx,
                run_id=ctx.run_id,
                app_id=app_id,
            )
            # Confirmed submission
            code = f"EMAIL{int(time.time()) % 1000000:06d}"
            submission_data = {
                "confirmed": True,
                "confirmation_code": code,
                "channel": "email",
                "at": db.now_str(),
            }
            db.update_application(app_id, submission=submission_data)
            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    app_id,
                    agent="applier",
                    type_="submission_confirmed",
                    message=f"Application submitted via email with code {code}",
                    data={"confirmation_code": code, "channel": "email"},
                )
            return "submitted"

        except SmtpError as e:
            with recovery_decision("smtp_failure", ["retry", "prepare_package"]) as rec:
                rec.decide("prepare_package", "The email could not be sent, so the package is prepared for manual submission.")
                rec.finish("prepared")

            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    app_id,
                    agent="applier",
                    type_="recovery_decision",
                    message="Recovery chosen: prepare_package because The email could not be sent, so the package is prepared for manual submission.",
                    data={"trigger": "smtp_failure", "options": ["retry", "prepare_package"], "chosen": "prepare_package"},
                )
            return "prepared"

    # 3. Channels: portal_form and portal_captcha
    if listing.channel in ("portal_form", "portal_captcha"):
        base_url = settings.public_base_url.rstrip("/")

        # Prepare draft payload
        summary_texts = [s.get("text", "") for s in tailored_data.get("cv_summary", []) if s.get("status") == "supported"]
        essay_texts = [s.get("text", "") for s in tailored_data.get("essay", []) if s.get("status") == "supported"]

        draft_fields = {
            "full_name": full_name,
            "email": email,
            "summary": " ".join(summary_texts),
            "essay": " ".join(essay_texts),
        }

        # 3.1 Create or reuse draft
        try:
            draft_resp = httpx.post(
                f"{base_url}/portal/api/draft",
                json={"listing_id": listing.id, "idempotency_key": app_id, "fields": draft_fields},
                timeout=10.0,
            )
            draft_data = draft_resp.json()
            draft_id = draft_data.get("draft_id", "")
            draft_url = draft_data.get("draft_url", "")
        except Exception as e:
            db.update_application(app_id, failure_reason=f"Portal draft creation failed: {e}")
            return "failed"

        # Check idempotency: already submitted?
        try:
            sub_check = httpx.get(f"{base_url}/portal/api/submissions/{draft_id}", timeout=10.0).json()
            if sub_check.get("submitted"):
                code = sub_check.get("confirmation_code")
                db.update_application(
                    app_id,
                    submission={"confirmed": True, "confirmation_code": code, "channel": listing.channel, "at": db.now_str()},
                )
                return "submitted"
        except Exception:
            pass

        # 3.2 Blocker scan
        apply_url = f"{base_url}/portal/apply/{listing.id}"
        blockers = check_blockers(apply_url, ctx)

        if blockers:
            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    app_id,
                    agent="applier",
                    type_="blocker_detected",
                    message=f"Blocker detected on portal: {', '.join(blockers)}",
                    data={"blockers": blockers},
                )
                if "captcha_wall" in db.get_flags().get("flags", {}) and db.get_flags()["flags"]["captcha_wall"]:
                    db.add_event(ctx.run_id, app_id, agent="applier", type_="failure_injected", message="Injected failure: captcha_wall", data={"flag": "captcha_wall"})

            with recovery_decision("captcha_wall", ["retry", "handoff"]) as rec:
                rec.decide("handoff", "A CAPTCHA can only be solved by the user, so the agent stops and hands off.")
                rec.finish("handed_off")

            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    app_id,
                    agent="applier",
                    type_="recovery_decision",
                    message="Recovery chosen: handoff because A CAPTCHA can only be solved by the user, so the agent stops and hands off.",
                    data={"trigger": "captcha_wall", "options": ["retry", "handoff"], "chosen": "handoff"},
                )

            handoff_payload = {
                "reason": "captcha",
                "portal_url": draft_url,
                "draft_id": draft_id,
                "instructions": "A security verification challenge was detected. Please solve the challenge and tap Done.",
            }
            db.update_application(app_id, handoff=handoff_payload)
            if app.get("status") in ("submitting", "ready"):
                db.set_status(app_id, "awaiting_user", "Blocker detected; awaiting user handoff resolution", agent="applier")
            return "awaiting_user"


        # 3.3 Submit draft with retries on HTTP 500
        max_submit_retries = 3
        submit_res = None

        for attempt in range(1, max_submit_retries + 1):
            try:
                submit_res = httpx.post(f"{base_url}/portal/api/submit", json={"draft_id": draft_id}, timeout=10.0)
                if submit_res.status_code == 200:
                    break
                elif submit_res.status_code == 403:
                    # Captcha challenge required unexpectedly -> treat as blocker
                    handoff_payload = {
                        "reason": "captcha",
                        "portal_url": draft_url,
                        "draft_id": draft_id,
                        "instructions": "Portal required CAPTCHA verification.",
                    }
                    db.update_application(app_id, handoff=handoff_payload)
                    return "awaiting_user"
                elif submit_res.status_code == 500:
                    if ctx.run_id:
                        db.add_event(ctx.run_id, app_id, agent="applier", type_="retry", message=f"Portal 500 on attempt {attempt}, retrying...", data={"attempt": attempt})
                    time.sleep(settings.retry_sleep_seconds * attempt)
            except Exception as e:
                if ctx.run_id:
                    db.add_event(ctx.run_id, app_id, agent="applier", type_="retry", message=f"Network error on attempt {attempt}: {e}", data={"attempt": attempt})
                time.sleep(settings.retry_sleep_seconds * attempt)

        # 3.4 Handle persistent 500 failure
        if submit_res is None or submit_res.status_code != 200:
            chosen = "email_fallback" if listing.email else "prepare_package"
            reason = f"Portal returned an error 3 times, so switching to {chosen}."

            with recovery_decision("portal_500", ["retry", "email_fallback", "prepare_package"]) as rec:
                rec.decide(chosen, reason)
                rec.finish("fallback_used")

            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    app_id,
                    agent="applier",
                    type_="recovery_decision",
                    message=f"Recovery chosen: {chosen} because {reason}",
                    data={"trigger": "portal_500", "options": ["retry", "email_fallback", "prepare_package"], "chosen": chosen},
                )

            if chosen == "email_fallback" and listing.email:
                try:
                    code = f"EMAIL{int(time.time()) % 10000:04d}"
                    email_body = (
                        f"Scholarship application submission for {listing.name}\n\n"
                        f"Applicant: {full_name}\nEmail: {email}\n\n"
                        f"{draft_fields.get('summary', '')}\n\n{draft_fields.get('essay', '')}"
                    )
                    notify.send_email(
                        to=listing.email,
                        subject=f"Application for {listing.name} - {full_name}",
                        body=email_body,
                        attachments=[],
                        ctx=ctx,
                        run_id=ctx.run_id,
                        app_id=app_id,
                    )
                    sub_data = {
                        "confirmed": True,
                        "confirmation_code": code,
                        "channel": "email_fallback",
                        "at": db.now_str(),
                    }
                    db.update_application(app_id, submission=sub_data)
                    return "submitted"
                except Exception:
                    return "prepared"
            return "prepared"


        # 3.5 Confirm submission via polling
        confirmation_code = None
        for poll_round in range(1, 4):
            try:
                sub_data = httpx.get(f"{base_url}/portal/api/submissions/{draft_id}", timeout=5.0).json()
                if sub_data.get("submitted"):
                    confirmation_code = sub_data.get("confirmation_code")
                    break
            except Exception:
                pass
            time.sleep(settings.retry_sleep_seconds)

        if confirmation_code:
            submission_data = {
                "confirmed": True,
                "confirmation_code": confirmation_code,
                "channel": listing.channel,
                "at": db.now_str(),
            }
            db.update_application(app_id, submission=submission_data)
            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    app_id,
                    agent="applier",
                    type_="submission_confirmed",
                    message=f"Portal submission confirmed with code {confirmation_code}",
                    data={"confirmation_code": confirmation_code},
                )
            return "submitted"
        else:
            with recovery_decision("confirmation_missing", ["retry_poll", "mark_unconfirmed"]) as rec:
                rec.decide("mark_unconfirmed", "No confirmation was seen, so the application is marked unconfirmed and the user is told.")
                rec.finish("unconfirmed")

            if ctx.run_id:
                db.add_event(
                    ctx.run_id,
                    app_id,
                    agent="applier",
                    type_="recovery_decision",
                    message="Recovery chosen: mark_unconfirmed because No confirmation was seen, so the application is marked unconfirmed and the user is told.",
                    data={"trigger": "confirmation_missing", "options": ["retry_poll", "mark_unconfirmed"], "chosen": "mark_unconfirmed"},
                )
            return "unconfirmed"

    return "prepared"


def resume_after_handoff(app_id: str) -> bool:
    """Resumes application after user solved CAPTCHA or external wall."""
    app = db.get_application(app_id)
    if not app:
        return False

    if app.get("status") not in ("awaiting_user", "submitting"):
        return False

    # Set status to submitting if currently awaiting_user
    if app.get("status") == "awaiting_user":
        db.set_status(app_id, "submitting", "Resuming submission after human handoff", agent="coordinator")

    handoff = app.get("handoff") or {}
    draft_id = handoff.get("draft_id")
    if not draft_id:
        return False


    base_url = settings.public_base_url.rstrip("/")
    try:
        resp = httpx.get(f"{base_url}/portal/api/submissions/{draft_id}", timeout=10.0)
        data = resp.json()
        if data.get("submitted"):
            code = data.get("confirmation_code")
            submission_data = {
                "confirmed": True,
                "confirmation_code": code,
                "channel": app.get("channel", "portal_captcha"),
                "at": db.now_str(),
            }
            db.update_application(app_id, submission=submission_data)
            db.set_status(app_id, "submitted", f"Submission confirmed with code {code}", agent="coordinator")
            if app.get("run_id"):
                db.add_event(
                    app["run_id"],
                    app_id,
                    agent="applier",
                    type_="submission_confirmed",
                    message=f"Human handoff resolved; submission confirmed with code {code}",
                    data={"confirmation_code": code},
                )
            return True
        else:
            db.set_status(app_id, "awaiting_user", "Confirmation not found on portal yet", agent="coordinator")
            if app.get("run_id"):
                db.add_event(
                    app["run_id"],
                    app_id,
                    agent="applier",
                    type_="confirmation_not_seen",
                    message="Submission not confirmed on portal yet; remaining in awaiting_user",
                )
            return False
    except Exception as e:
        db.set_status(app_id, "awaiting_user", f"Error checking submission: {e}", agent="coordinator")
        return False
