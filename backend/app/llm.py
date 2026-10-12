import json
import re
import time
from typing import Any
from pydantic import BaseModel, ValidationError

import openai
from openai import OpenAI

try:
    from app.config import settings
    from app.db import consume_flag, add_event
    from app.errors import (
        RunContext,
        ScholarPilotError,
        RateLimitError,
        TimeoutError_,
        ModelNotFoundError,
        BadJSONError,
    )
    from app.models import LLMResult
    from app.prompts import REPAIR_SYSTEM
    from app.tracing import (
        llm_call_span,
        recovery_decision,
        wrap_client,
        set_attrs,
        log_event,
    )
except ModuleNotFoundError:
    from backend.app.config import settings
    from backend.app.db import consume_flag, add_event
    from backend.app.errors import (
        RunContext,
        ScholarPilotError,
        RateLimitError,
        TimeoutError_,
        ModelNotFoundError,
        BadJSONError,
    )
    from backend.app.models import LLMResult
    from backend.app.prompts import REPAIR_SYSTEM
    from backend.app.tracing import (
        llm_call_span,
        recovery_decision,
        wrap_client,
        set_attrs,
        log_event,
    )

_primary_client: Any = None
_fallback_client: Any = None
_test_primary: Any = None
_test_fallback: Any = None


def set_clients_for_tests(primary: Any = None, fallback: Any = None) -> None:
    """Injects test clients for unit testing."""
    global _test_primary, _test_fallback
    _test_primary = primary
    _test_fallback = fallback


class _DemoMessage:
    def __init__(self, content: str):
        self.content = content


class _DemoChoice:
    def __init__(self, content: str):
        self.message = _DemoMessage(content)


class _DemoUsage:
    def __init__(self, prompt_tokens: int = 150, completion_tokens: int = 80):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _DemoResponse:
    def __init__(self, content: str, p_tok: int = 150, c_tok: int = 80):
        self.choices = [_DemoChoice(content)]
        self.usage = _DemoUsage(p_tok, c_tok)


class _DemoCompletions:
    def create(self, **kwargs: Any) -> Any:
        messages = kwargs.get("messages", [])
        sys_msg = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
        user_msg = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        content = "{}"

        if "repair" in sys_msg.lower():
            if "fit_score" in user_msg.lower() or "fit_reason" in user_msg.lower():
                content = json.dumps({
                    "fit_score": 87,
                    "fit_reason": "Applicant qualifications in computer engineering and solar IoT align closely with programme focus.",
                    "strongest_fact_ids": ["C1"],
                    "missing_criteria": []
                })
            else:
                content = user_msg.strip()
                if not content.endswith("}"):
                    if '"' in content and content.count('"') % 2 != 0:
                        content += '"'
                    content += "}"
        elif "convert a personal document" in sys_msg.lower() or "intake" in sys_msg.lower():

            lines = [line.strip() for line in user_msg.splitlines() if line.strip() and not line.startswith("Section:") and len(line.strip()) > 5]
            facts = []
            for line in lines[:10]:
                cat = "education" if "bsc" in line.lower() or "cgpa" in line.lower() else ("work" if "intern" in line.lower() or "firmware" in line.lower() else "projects")
                facts.append({"category": cat, "text": line, "source_line": line})
            content = json.dumps({"facts": facts})
        elif "score how well an applicant fits" in sys_msg.lower() or "matcher" in sys_msg.lower():
            content = json.dumps({
                "fit_score": 87,
                "fit_reason": "Applicant qualifications in computer engineering and solar IoT align closely with programme focus.",
                "strongest_fact_ids": ["C1"],
                "missing_criteria": []
            })
        elif "extract facts about a school" in sys_msg.lower() or "researcher" in sys_msg.lower():
            content = json.dumps({
                "facts": [
                    {
                        "topic": "program_focus",
                        "text": "Masters program focusing on clean renewable energy and smart grid systems.",
                        "snippet": "renewable energy"
                    }
                ]
            })
        elif "strongest evidence for one specific scholarship" in sys_msg.lower() or "find the applicant" in sys_msg.lower():
            content = json.dumps({
                "edges": [
                    {
                        "profile_fact_ids": ["C1"],
                        "dossier_fact_ids": ["D1"],
                        "reason": "Direct experience with solar firmware sensors on BrightGrid project matches smart grid theme.",
                        "use_in": "essay",
                        "strength": 0.88
                    }
                ],
                "gaps": []
            })
        elif "revise specific sentences" in sys_msg.lower():
            content = json.dumps({
                "revisions": [
                    {
                        "section": "essay",
                        "segment_index": 2,
                        "text": "During my 5-month internship at BrightGrid Solar, I focused on testing sensor firmware.",
                        "source_ids": ["C1"]
                    }
                ]
            })
        elif "write parts of a scholarship application" in sys_msg.lower():
            content = json.dumps({
                "cv_summary": [
                    {"text": "BSc Computer Engineering graduate focused on embedded solar monitoring systems.", "source_ids": ["C1"]}
                ],
                "cv_bullets": [
                    {"text": "Developed and verified data logging firmware for 12 solar sensor boards at BrightGrid.", "source_ids": ["C1"]}
                ],
                "essay": [
                    {"text": "I am applying for the scholarship to advance renewable smart grid engineering.", "source_ids": ["D1"]},
                    {"text": "During my time at BrightGrid Solar, I developed firmware for sensor boards.", "source_ids": ["C1"]},
                    {"text": "I bring extensive professional experience spanning years of solar engineering.", "source_ids": ["C1"]}
                ]
            })
        elif "split the numbered application sentences" in sys_msg.lower():
            content = json.dumps({
                "claims": [
                    {"text": "I am applying for the scholarship to advance renewable smart grid engineering.", "section": "essay", "segment_index": 0},
                    {"text": "During my time at BrightGrid Solar, I developed firmware for sensor boards.", "section": "essay", "segment_index": 1},
                    {"text": "I bring extensive professional experience spanning years of solar engineering.", "section": "essay", "segment_index": 2}
                ]
            })
        elif "strict fact checker" in sys_msg.lower():
            # Extract claim IDs from user message
            c_ids = re.findall(r"Claim\s+([A-Za-z0-9_-]+):", user_msg)
            verdicts = []
            for idx, cid in enumerate(c_ids):
                if idx == len(c_ids) - 1:  # last claim has the duration trap
                    verdicts.append({"claim_id": cid, "verdict": "unsupported", "reason": "CV documents a 5-month internship, not multiple years of professional experience."})
                else:
                    verdicts.append({"claim_id": cid, "verdict": "supported", "reason": "Directly supported by source facts."})
            if not verdicts:
                verdicts = [
                    {"claim_id": "CLM1", "verdict": "supported", "reason": "Consistent with programme focus."},
                    {"claim_id": "CLM2", "verdict": "supported", "reason": "Directly supported by BrightGrid internship fact."},
                    {"claim_id": "CLM3", "verdict": "unsupported", "reason": "CV documents a 5-month internship, not multiple years of professional experience."}
                ]
            content = json.dumps({"verdicts": verdicts})
        elif "skeptical scholarship committee" in sys_msg.lower():
            c_ids = re.findall(r"Claim\s+([A-Za-z0-9_-]+):", user_msg)
            challenges = []
            for idx, cid in enumerate(c_ids):
                if idx == 0 and len(c_ids) > 1:
                    challenges.append({"claim_id": cid, "outcome": "overturn", "reason": "Challenger probe marks scope as needing further evidence."})
                else:
                    challenges.append({"claim_id": cid, "outcome": "defend", "reason": "Supported without overreach."})
            if not challenges:
                challenges = [{"claim_id": "CLM1", "outcome": "defend", "reason": "Supported without overreach."}]
            content = json.dumps({"challenges": challenges})
        elif "plan their own essay" in sys_msg.lower():
            content = json.dumps({
                "sections": [
                    {"title": "Introduction", "notes": "State interest in smart grid systems.", "fact_ids": ["D1"]},
                    {"title": "Technical Background", "notes": "Discuss firmware logging work.", "fact_ids": ["C1"]}
                ]
            })

        return _DemoResponse(content)


class _DemoClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _DemoCompletions()})()


def get_primary_client() -> Any:
    global _primary_client
    if _test_primary is not None:
        return _test_primary
    if _primary_client is None:
        if settings.llm_primary_api_key:
            raw = OpenAI(
                base_url=settings.llm_primary_base_url,
                api_key=settings.llm_primary_api_key,
                timeout=10.0,
            )
            _primary_client = wrap_client(raw)
        elif settings.demo_mode:
            _primary_client = _DemoClient()
    return _primary_client



def get_fallback_client() -> Any:
    global _fallback_client
    if _test_fallback is not None:
        return _test_fallback
    if _fallback_client is None:
        if settings.llm_fallback_api_key:
            raw = OpenAI(
                base_url=settings.llm_fallback_base_url,
                api_key=settings.llm_fallback_api_key,
                timeout=10.0,
            )
            _fallback_client = wrap_client(raw)
        elif settings.demo_mode:
            _fallback_client = _DemoClient()
    return _fallback_client



def strip_fences(text: str) -> str:
    """Strips markdown code fences and whitespace from json string."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def call_llm(
    prompt_name: str,
    system: str,
    user: str,
    schema: type[BaseModel],
    ctx: RunContext,
    temperature: float = 0.2,
    max_tokens: int = 2000,
) -> LLMResult:
    """Executes a structured LLM call with retry, fallback, JSON repair, and neatlogs instrumentation."""
    start_time = time.time()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    with llm_call_span(prompt_name, system, user, ctx) as span:
        attempt = 0
        use_fallback = False
        fallback_used = False
        total_tokens_in = 0
        total_tokens_out = 0
        json_repaired = False
        raw_content = ""
        current_model = ""

        while True:
            attempt += 1
            client = get_fallback_client() if use_fallback else get_primary_client()
            current_model = settings.llm_fallback_model if use_fallback else settings.llm_primary_model

            # Check llm_429 failure flag
            if not use_fallback and consume_flag("llm_429"):
                if ctx.run_id:
                    add_event(ctx.run_id, ctx.application_id, "coordinator", "failure_injected", "Simulated rate limit", {"flag": "llm_429"})
                err = RateLimitError("Simulated 429 rate limit")
            else:
                if client is None:
                    # If primary not configured and no fallback, error
                    if not use_fallback and get_fallback_client() is not None:
                        use_fallback = True
                        fallback_used = True
                        continue
                    raise RateLimitError("No configured LLM client available")

                try:
                    call_kwargs: dict[str, Any] = {
                        "model": current_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "response_format": {"type": "json_object"},
                    }
                    try:
                        response = client.chat.completions.create(**call_kwargs)
                    except Exception as e:
                        # Some providers reject response_format
                        if "response_format" in str(e).lower():
                            call_kwargs.pop("response_format", None)
                            response = client.chat.completions.create(**call_kwargs)
                        else:
                            raise e

                    usage = getattr(response, "usage", None)
                    if usage:
                        total_tokens_in += getattr(usage, "prompt_tokens", 0)
                        total_tokens_out += getattr(usage, "completion_tokens", 0)

                    raw_content = response.choices[0].message.content or ""
                    err = None
                except openai.RateLimitError as e:
                    err = RateLimitError(str(e))
                except (openai.APITimeoutError, openai.APIConnectionError) as e:
                    err = TimeoutError_(str(e))
                except openai.NotFoundError as e:
                    err = ModelNotFoundError(str(e))
                except openai.APIStatusError as e:
                    if e.status_code and e.status_code >= 500:
                        err = TimeoutError_(str(e))
                    else:
                        err = ScholarPilotError(str(e))
                except Exception as e:
                    if isinstance(e, (RateLimitError, TimeoutError_, ModelNotFoundError)):
                        err = e
                    else:
                        err = ScholarPilotError(str(e))

            # Handle errors
            if err is not None:
                if isinstance(err, ModelNotFoundError):
                    if not use_fallback and get_fallback_client() is not None:
                        with recovery_decision("model_not_found", ["fallback_model"]) as r:
                            r.decide("fallback_model", "The primary model id was rejected as not found, so using the backup model.")
                            r.finish("switched_to_fallback")
                        if ctx.run_id:
                            add_event(ctx.run_id, ctx.application_id, "coordinator", "llm_fallback", "Switched to fallback model", {"reason": "model_not_found"})
                        use_fallback = True
                        fallback_used = True
                        continue
                    raise err

                if isinstance(err, (RateLimitError, TimeoutError_)):
                    if ctx.run_id:
                        add_event(ctx.run_id, ctx.application_id, "coordinator", "retry", f"Attempt {attempt} failed, retrying", {"attempt": attempt, "error": str(err)})

                    # Sleep backoff
                    sleep_mult = [1, 2, 4][min(attempt - 1, 2)]
                    time.sleep(settings.retry_sleep_seconds * sleep_mult)

                    if attempt >= 2 and not use_fallback and get_fallback_client() is not None:
                        with recovery_decision("llm_429", ["retry", "fallback_model"]) as r:
                            r.decide("fallback_model", f"Rate limited {attempt} times on {settings.llm_primary_model}, switching to backup model.")
                            r.finish("switched_to_fallback")
                        if ctx.run_id:
                            add_event(ctx.run_id, ctx.application_id, "coordinator", "llm_fallback", "Switched to fallback model after retries", {"attempts": attempt})
                        use_fallback = True
                        fallback_used = True
                        continue

                    if attempt >= 4:
                        raise err
                    continue

                raise err

            # Success response obtained
            break

        # Check bad_json failure flag
        if consume_flag("bad_json"):
            if ctx.run_id:
                add_event(ctx.run_id, ctx.application_id, "coordinator", "failure_injected", "Simulated broken JSON truncation", {"flag": "bad_json"})
            raw_content = raw_content[: len(raw_content) // 2]

        # Parse & Validate JSON
        cleaned = strip_fences(raw_content)
        parsed_data = None
        try:
            parsed_data = json.loads(cleaned)
            validated = schema.model_validate(parsed_data)
        except Exception:
            # First repair attempt
            if ctx.run_id:
                add_event(ctx.run_id, ctx.application_id, "coordinator", "json_repair", "Attempting JSON syntax repair", {"attempt": 1})
            json_repaired = True
            repair_client = get_fallback_client() if use_fallback else get_primary_client()
            repair_success = False
            try:
                repair_resp = repair_client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {"role": "system", "content": REPAIR_SYSTEM},
                        {"role": "user", "content": cleaned},
                    ],
                    temperature=0.0,
                    max_tokens=max_tokens,
                )
                r_usage = getattr(repair_resp, "usage", None)
                if r_usage:
                    total_tokens_in += getattr(r_usage, "prompt_tokens", 0)
                    total_tokens_out += getattr(r_usage, "completion_tokens", 0)
                r_content = strip_fences(repair_resp.choices[0].message.content or "")
                parsed_data = json.loads(r_content)
                validated = schema.model_validate(parsed_data)
                repair_success = True
            except Exception:
                repair_success = False

            if not repair_success:
                # Second attempt: regeneration at temp 0.0
                try:
                    regen_resp = repair_client.chat.completions.create(
                        model=current_model,
                        messages=messages,
                        temperature=0.0,
                        max_tokens=max_tokens,
                    )
                    rg_usage = getattr(regen_resp, "usage", None)
                    if rg_usage:
                        total_tokens_in += getattr(rg_usage, "prompt_tokens", 0)
                        total_tokens_out += getattr(rg_usage, "completion_tokens", 0)
                    rg_content = strip_fences(regen_resp.choices[0].message.content or "")
                    parsed_data = json.loads(rg_content)
                    validated = schema.model_validate(parsed_data)
                except Exception as final_err:
                    raise BadJSONError(f"Failed to produce valid JSON: {final_err}")

        # Compute cost & latency
        latency = time.time() - start_time
        if fallback_used:
            in_price = settings.price_fallback_in_per_mtok
            out_price = settings.price_fallback_out_per_mtok
        else:
            in_price = settings.price_primary_in_per_mtok
            out_price = settings.price_primary_out_per_mtok

        cost = (total_tokens_in * in_price / 1_000_000.0) + (total_tokens_out * out_price / 1_000_000.0)

        set_attrs(
            span,
            prompt_version=prompt_name,
            model=current_model,
            attempt=attempt,
            fallback_used=fallback_used,
            json_repaired=json_repaired,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            cost_usd=round(cost, 6),
        )

        return LLMResult(
            parsed=validated.model_dump(),
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            cost_usd=round(cost, 6),
            latency_seconds=round(latency, 3),
            model=current_model,
            fallback_used=fallback_used,
            attempts=attempt,
            json_repaired=json_repaired,
        )


async def provider_completion(api_key: str, base_url: str, model: str, messages: list[dict[str, str]], temperature: float, capture: bool, timeout: float) -> dict[str, Any]:
    """Real async provider transport; SDK imports remain confined to this module."""
    raw = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
    original_create = raw.chat.completions.create

    async def normalized_create(**kwargs: Any) -> Any:
        response = await original_create(**kwargs)
        usage = response.usage
        if usage is not None and isinstance(usage.total_tokens, int) and isinstance(usage.prompt_tokens, int):
            # Gemini-compatible responses may omit thinking tokens from completion_tokens.
            # Normalize BEFORE Neatlogs reads usage so its totals match the provider total.
            billed_output = usage.total_tokens - usage.prompt_tokens
            if billed_output >= usage.completion_tokens:
                usage.completion_tokens = billed_output
        return response

    raw.chat.completions.create = normalized_create
    client = wrap_client(raw)
    try:
        options: dict[str, Any] = {"reasoning_effort": "none"} if model.startswith("gemini-2.5-flash") else {"reasoning_effort": "minimal"} if model.startswith("gemini-3") else {}
        result = await client.chat.completions.create(model=model, messages=messages,
            temperature=temperature, max_tokens=4096, response_format={"type": "json_object"}, **options)
        return result.model_dump()
    finally:
        await raw.close()


def provider_error_status(error: Exception) -> int | None:
    """Expose transport status without importing the model SDK outside this module."""
    if isinstance(error, openai.APIStatusError):
        return error.status_code
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None
