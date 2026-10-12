"""Playwright browser runner for portal form submission, screenshot capture, and blocker detection."""
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.logging import logger
from app.core.runtime import is_demo_portal, submissions_stopped, assert_submission_lease
from app.integrations.demo_portal import read_confirmation

# Directory for storing portal submission and blocker screenshots
SCREENSHOTS_DIR = Path("storage/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class BrowserSubmissionResult(BaseModel):
    """Result of an automated portal submission or blocker encounter."""
    success: bool
    is_blocked: bool = False
    blocker_type: Optional[str] = None  # captcha, login_wall, 2fa_verification, fee_payment, unknown
    blocker_message: Optional[str] = None
    confirmation_ref: Optional[str] = None
    screenshot_paths: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Common blocker signatures across scholarship portals
CAPTCHA_PATTERNS = [
    r"captcha_challenge",
    r"recaptcha",
    r"hcaptcha",
    r"turnstile",
    r"cf-turnstile",
    r"challenge-platform",
    r"arkoselabs",
    r"geetest",
    r"datadome",
    r"perimeterx",
    r"bot detection",
    r"verify you are human",
    r"solve the challenge",
    r"security check",
    r"robot check",
]

LOGIN_WALL_PATTERNS = [
    r"<input[^>]+type=[\"']password[\"']",
    r"sign in to continue",
    r"login required",
    r"please log in to access this application",
    r"session expired",
    r"authentication required",
]

MFA_PATTERNS = [
    r"two-factor",
    r"2-step verification",
    r"enter the 6-digit code",
    r"verification code sent to your phone",
    r"one-time password",
    r"authenticator code",
]

PAYMENT_PATTERNS = [
    r"application fee required",
    r"pay now to submit",
    r"credit card details required",
    r"enter payment method",
]


def detect_blockers(html_content: str, current_url: str = "") -> Optional[Tuple[str, str]]:
    """Analyzes page content and URL to detect human-intervention blockers.
    
    Hard Rule: NEVER bypass, solve, or work around CAPTCHAs, bot checks, or login walls.
    Detect them immediately, stop execution, and hand off to the student.
    """
    # Static error strings in our portal's script are not displayed blockers.
    # Keep rendered markup (including challenge IDs, password inputs and widget attributes).
    content = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", " ", html_content, flags=re.I | re.S)
    lower_content = content.lower()
    lower_url = current_url.lower()

    # 1. Check for CAPTCHA / bot checks
    for pattern in CAPTCHA_PATTERNS:
        if re.search(pattern, lower_content) or re.search(pattern, lower_url):
            return "captcha", f"Automated bot detection or CAPTCHA encountered: '{pattern}'"

    # 2. Check for MFA / 2FA verification
    for pattern in MFA_PATTERNS:
        if re.search(pattern, lower_content):
            return "2fa_verification", f"Two-factor authentication required: '{pattern}'"

    # 3. Check for login walls
    for pattern in LOGIN_WALL_PATTERNS:
        if re.search(pattern, lower_content) or "login" in lower_url:
            return "login_wall", f"Portal login or authentication wall required: '{pattern}'"

    # 4. Check for unexpected payment fees
    for pattern in PAYMENT_PATTERNS:
        if re.search(pattern, lower_content):
            return "fee_payment", f"Application fee or payment wall detected: '{pattern}'"

    return None


def generate_mock_screenshot(step_name: str, directory: Path = SCREENSHOTS_DIR) -> str:
    """Generates a valid lightweight placeholder image file for screenshots in sandbox/test environments."""
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{step_name}_{uuid.uuid4().hex[:8]}.png"
    filepath = directory / filename
    
    # Minimal valid 1x1 transparent PNG binary bytes
    png_1x1 = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00"
        b"\x00IEND\xaeB`\x82"
    )
    with open(filepath, "wb") as f:
        f.write(png_1x1)
    return str(filepath.resolve())


async def submit_portal(
    portal_url: str,
    applicant_data: Dict[str, Any],
    draft_content: str,
    credentials: Optional[Dict[str, str]] = None,
    mock_mode: bool = False,
    simulated_blocker: Optional[str] = None,
    screenshots_dir: Path = SCREENSHOTS_DIR,
    storage_state_path: Optional[str] = None,
) -> BrowserSubmissionResult:
    """Executes headless browser form submission for a scholarship application.
    
    Adheres strictly to the following guarantees:
    1. Stops immediately upon detecting CAPTCHAs or auth walls.
    2. Takes screenshots at each milestone step.
    3. Returns parsed confirmation reference upon successful submission.
    """
    screenshots: List[str] = []

    # Early kill switch check
    if await submissions_stopped(applicant_data.get("_owner_id"), autonomous=bool(applicant_data.get("_autonomous"))):
        logger.warning("submit_portal aborted: global kill switch is active.")
        return BrowserSubmissionResult(
            success=False,
            is_blocked=True,
            blocker_type="kill_switch",
            blocker_message="Submission aborted: global kill switch is active.",
            screenshot_paths=screenshots,
            metadata={"portal_url": portal_url},
        )

    # Fast-path for mocked/sandboxed execution (used in tests and synthetic demo runs)
    if mock_mode and settings.ENVIRONMENT == "production":
        raise ValueError("Mock browser mode is prohibited in production.")
    if mock_mode:
        # Step 1: initial load screenshot
        initial_ss = generate_mock_screenshot("portal_loaded", screenshots_dir)
        screenshots.append(initial_ss)

        # Handle simulated blockers
        if simulated_blocker:
            blocker_ss = generate_mock_screenshot(f"blocker_{simulated_blocker}", screenshots_dir)
            screenshots.append(blocker_ss)
            return BrowserSubmissionResult(
                success=False,
                is_blocked=True,
                blocker_type=simulated_blocker,
                blocker_message=f"Human handoff required: simulated {simulated_blocker} encountered.",
                screenshot_paths=screenshots,
                metadata={"portal_url": portal_url},
            )

        # Successful mock submission
        submitted_ss = generate_mock_screenshot("submission_confirmed", screenshots_dir)
        screenshots.append(submitted_ss)
        confirmation_code = f"CONF-2026-{uuid.uuid4().hex[:8].upper()}"

        return BrowserSubmissionResult(
            success=True,
            is_blocked=False,
            confirmation_ref=confirmation_code,
            screenshot_paths=screenshots,
            metadata={"portal_url": portal_url, "mock": True},
        )

    # Real Playwright Runner
    if not is_demo_portal(portal_url):
        raise ValueError("Browser submissions are restricted to the local demo portal.")
    previous_confirmation = await read_confirmation(portal_url)
    if previous_confirmation:
        return BrowserSubmissionResult(success=True, confirmation_ref=previous_confirmation,
            metadata={"portal_url": portal_url, "read_back": True})
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("Playwright unavailable; no submission was attempted.")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            if storage_state_path and os.path.exists(storage_state_path):
                context = await browser.new_context(storage_state=storage_state_path)
            else:
                context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(2000)

            # Navigate to portal
            await page.goto(portal_url, timeout=15000, wait_until="networkidle")
            if not is_demo_portal(page.url):
                raise ValueError("Demo portal redirected outside the permitted submission origin.")

            # 1. Page load screenshot
            load_ss = str((screenshots_dir / f"loaded_{uuid.uuid4().hex[:8]}.png").resolve())
            await page.screenshot(path=load_ss)
            screenshots.append(load_ss)

            # 2. Check for blockers
            content = await page.content()
            blocker = detect_blockers(content, page.url)
            if blocker:
                blocker_type, message = blocker
                state_file = str((screenshots_dir / f"session_state_{uuid.uuid4().hex[:8]}.json").resolve())
                try:
                    await context.storage_state(path=state_file)
                except Exception as err:
                    logger.warning(f"Could not persist browser storage state: {err}")
                    state_file = None

                blocker_ss = str((screenshots_dir / f"blocker_{uuid.uuid4().hex[:8]}.png").resolve())
                await page.screenshot(path=blocker_ss)
                screenshots.append(blocker_ss)
                await browser.close()
                return BrowserSubmissionResult(
                    success=False,
                    is_blocked=True,
                    blocker_type=blocker_type,
                    blocker_message=message,
                    screenshot_paths=screenshots,
                    metadata={"portal_url": portal_url, "url": page.url, "storage_state_path": state_file},
                )

            # 3. Form population
            # Generic field selector mappings
            field_mappings = {
                "first_name": ["input[name*='first']", "input[name*='fname']", "input[id*='first']"],
                "last_name": ["input[name*='last']", "input[name*='lname']", "input[id*='last']"],
                "email": ["input[type='email']", "input[name*='email']", "input[id*='email']"],
                "phone": ["input[type='tel']", "input[name*='phone']", "input[id*='phone']"],
                "gpa": ["input[name*='gpa']", "input[id*='gpa']"],
                "nationality": ["input[name*='nationality']", "input[name*='country']"],
            }

            for key, selectors in field_mappings.items():
                val = applicant_data.get(key)
                if val is not None:
                    for sel in selectors:
                        try:
                            loc = page.locator(sel).first
                            if await loc.count() > 0 and await loc.is_visible():
                                await loc.fill(str(val))
                                break
                        except Exception:
                            continue

            # Populate Statement of Purpose / Essay
            essay_selectors = ["textarea[name*='essay']", "textarea[name*='statement']", "textarea", "div[contenteditable='true']"]
            for sel in essay_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.fill(draft_content)
                        break
                except Exception:
                    continue

            # Step 2 screenshot: Form filled
            filled_ss = str((screenshots_dir / f"filled_{uuid.uuid4().hex[:8]}.png").resolve())
            await page.screenshot(path=filled_ss)
            screenshots.append(filled_ss)

            # Step 3: Submit button
            if await submissions_stopped(applicant_data.get("_owner_id"), autonomous=bool(applicant_data.get("_autonomous"))):
                await browser.close()
                return BrowserSubmissionResult(
                    success=False,
                    is_blocked=True,
                    blocker_type="kill_switch",
                    blocker_message="Submission aborted: global kill switch activated prior to form submission.",
                    screenshot_paths=screenshots,
                    metadata={"portal_url": portal_url},
                )

            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Apply')",
            ]
            submitted = False
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        if await submissions_stopped(applicant_data.get("_owner_id"), autonomous=bool(applicant_data.get("_autonomous"))):
                            await browser.close()
                            return BrowserSubmissionResult(
                                success=False,
                                is_blocked=True,
                                blocker_type="kill_switch",
                                blocker_message="Submission aborted: global kill switch activated prior to form submission.",
                                screenshot_paths=screenshots,
                                metadata={"portal_url": portal_url},
                            )
                        await assert_submission_lease()
                        await btn.click()
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                # If no specific submit button found, raise failed
                await browser.close()
                return BrowserSubmissionResult(
                    success=False,
                    blocker_message="Could not locate submit button on portal form.",
                    screenshot_paths=screenshots,
                    metadata={"portal_url": portal_url},
                )

            # Wait for response / confirmation
            await page.wait_for_load_state("networkidle", timeout=10000)

            # Step 4: Capture post-submit screenshot
            confirm_ss = str((screenshots_dir / f"confirm_{uuid.uuid4().hex[:8]}.png").resolve())
            await page.screenshot(path=confirm_ss)
            screenshots.append(confirm_ss)

            post_content = await page.content()
            blocker = detect_blockers(post_content, page.url)
            if blocker:
                await browser.close()
                return BrowserSubmissionResult(success=False, is_blocked=True,
                    blocker_type=blocker[0], blocker_message=blocker[1],
                    screenshot_paths=screenshots, metadata={"portal_url": portal_url})
            # Extract confirmation code
            confirmation_code = await read_confirmation(portal_url)
            if confirmation_code:
                await browser.close()
                return BrowserSubmissionResult(
                    success=True,
                    is_blocked=False,
                    confirmation_ref=confirmation_code,
                    screenshot_paths=screenshots,
                    metadata={"portal_url": portal_url},
                )
            else:
                await browser.close()
                return BrowserSubmissionResult(
                    success=False,
                    is_blocked=False,
                    blocker_message="Portal submitted but no valid confirmation reference code was found on confirmation page.",
                    screenshot_paths=screenshots,
                    metadata={"portal_url": portal_url},
                )

    except Exception as e:
        logger.error(f"Browser runner execution failed: {e}")
        return BrowserSubmissionResult(
            success=False,
            blocker_message=str(e),
            screenshot_paths=screenshots,
            metadata={"portal_url": portal_url, "error": str(e)},
        )
