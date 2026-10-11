import json
import re
import time
from typing import Any
from pydantic import BaseModel, ValidationError

import openai
from openai import OpenAI

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

_primary_client: Any = None
_fallback_client: Any = None
_test_primary: Any = None
_test_fallback: Any = None


def set_clients_for_tests(primary: Any = None, fallback: Any = None) -> None:
    """Injects test clients for unit testing."""
    global _test_primary, _test_fallback
    _test_primary = primary
    _test_fallback = fallback


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
