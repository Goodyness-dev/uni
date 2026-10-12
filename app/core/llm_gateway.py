"""Unified LLM Gateway: model routing, retries, cost accounting, daily spending caps, and schema validation."""
import json
import time
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel
from app.core.config import settings
from app.core.logging import logger
from app.core.budget import reserve_budget, settle_budget
from app.core.tracing import tool_span, recovery_decision, current_application_id
from app.db.base import AsyncSessionLocal
from app.db.models import ApplicationEvent
from uuid import UUID
from backend.app.llm import provider_completion

T = TypeVar("T", bound=BaseModel)

# Model pricing table per 1M tokens (USD)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "default": {"input": 0.10, "output": 0.40},
}


class LLMSpendLimitExceeded(Exception):
    """Raised when an operation exceeds user or global spending limits."""
    pass


class LLMValidationError(Exception):
    """Raised when LLM output fails schema validation repeatedly."""
    pass


class LLMResponse(BaseModel):
    """Standardized response from the LLM Gateway."""
    content: str
    parsed: Optional[Any] = None
    model_used: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_seconds: float
    fallback_used: bool = False


class DailySpendTracker:
    """Thread-safe in-memory daily spending tracker with day-boundary reset."""
    def __init__(self) -> None:
        self.current_day: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.user_spend: Dict[str, float] = defaultdict(float)
        self.global_spend: float = 0.0

    def _check_reset(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.current_day:
            self.current_day = today
            self.user_spend.clear()
            self.global_spend = 0.0

    def check_and_record(self, user_id: Optional[str], estimated_cost: float) -> None:
        self._check_reset()
        if self.global_spend + estimated_cost > settings.GLOBAL_DAILY_SPEND_CAP_USD:
            raise LLMSpendLimitExceeded(
                f"Global daily LLM spending limit of ${settings.GLOBAL_DAILY_SPEND_CAP_USD:.2f} exceeded."
            )
        if user_id:
            if self.user_spend[user_id] + estimated_cost > settings.USER_DAILY_SPEND_CAP_USD:
                raise LLMSpendLimitExceeded(
                    f"User {user_id} exceeded daily LLM spending limit of ${settings.USER_DAILY_SPEND_CAP_USD:.2f}."
                )
            self.user_spend[user_id] += estimated_cost
        self.global_spend += estimated_cost

    def reconcile(self, user_id: Optional[str], estimated_cost: float, actual_cost: float) -> None:
        """Reconciles actual token spend against the pre-call estimate."""
        self._check_reset()
        diff = actual_cost - estimated_cost
        if user_id:
            self.user_spend[user_id] = max(0.0, self.user_spend[user_id] + diff)
        self.global_spend = max(0.0, self.global_spend + diff)


class ProviderCircuitBreaker:
    """Tracks consecutive provider failures and trips open to prevent cascading timeouts."""
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.last_failure_time: Dict[str, float] = defaultdict(float)

    def is_available(self, provider: str) -> bool:
        if self.failure_counts[provider] >= self.failure_threshold:
            if time.time() - self.last_failure_time[provider] < self.cooldown_seconds:
                return False
            # Reset after cooldown period
            self.failure_counts[provider] = 0
        return True

    def record_success(self, provider: str) -> None:
        self.failure_counts[provider] = 0

    def record_failure(self, provider: str) -> None:
        self.failure_counts[provider] += 1
        self.last_failure_time[provider] = time.time()


spend_tracker = DailySpendTracker()
circuit_breaker = ProviderCircuitBreaker()


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculates call cost in USD based on model pricing."""
    pricing = MODEL_PRICING.get(model_name.lower(), MODEL_PRICING["default"])
    input_cost = (input_tokens / 1_000_000.0) * pricing["input"]
    output_cost = (output_tokens / 1_000_000.0) * pricing["output"]
    return round(input_cost + output_cost, 6)


def sanitize_untrusted_content(text: str) -> str:
    """Sanitizes external web page or portal text to neutralize prompt injection instructions."""
    # Ensure system delimiters are neutralized and encapsulated
    sanitized = text.replace("```", "'''")
    return f"<untrusted_document_content>\n{sanitized}\n</untrusted_document_content>"


@tool_span("model_gateway", description="Provider call without prompt capture")
async def call_llm(
    system_prompt: str,
    user_prompt: str,
    response_model: Optional[Type[T]] = None,
    user_id: Optional[str] = None,
    temperature: float = 0.2,
    mock_response: Optional[str] = None,
) -> LLMResponse:
    """Invokes the LLM Gateway with retries, fallback provider routing, schema validation, and cost tracking."""
    # Emergency kill switch check
    if settings.KILL_SWITCH_ACTIVE:
        raise RuntimeError("Kill switch active: LLM and agent actions are halted.")

    # In mock mode (e.g. testing), return immediately
    if mock_response is not None:
        parsed_obj = None
        if response_model:
            parsed_obj = response_model.model_validate_json(mock_response)
        cost = calculate_cost(settings.PRIMARY_MODEL, 100, 50)
        spend_tracker.check_and_record(user_id, cost)
        return LLMResponse(
            content=mock_response,
            parsed=parsed_obj,
            model_used=settings.PRIMARY_MODEL,
            input_tokens=100,
            output_tokens=50,
            cost_usd=cost,
            latency_seconds=0.05,
            fallback_used=False,
        )

    # Prepare model execution candidates based on active provider (Gemini or Claude)
    active_provider = getattr(settings, "LLM_PROVIDER", "gemini").lower()
    if active_provider == "claude":
        models_to_try = [
            (settings.CLAUDE_MODEL, settings.ANTHROPIC_API_KEY or settings.PRIMARY_API_KEY, "claude", False),
            (settings.GEMINI_MODEL, settings.GEMINI_API_KEY or settings.FALLBACK_API_KEY, "gemini", True),
        ]
    else:  # Gemini default
        models_to_try = [
            (settings.GEMINI_MODEL, settings.GEMINI_API_KEY or settings.PRIMARY_API_KEY, "gemini", False),
            (settings.CLAUDE_MODEL, settings.ANTHROPIC_API_KEY or settings.FALLBACK_API_KEY, "claude", True),
        ]

    if settings.AGENT_ENABLED:
        models_to_try = [(settings.GEMINI_MODEL, settings.GEMINI_API_KEY or settings.PRIMARY_API_KEY, "gemini", False),
            (settings.AGENT_FALLBACK_MODEL, settings.GEMINI_API_KEY or settings.PRIMARY_API_KEY, "gemini_backup", True)]
    last_error: Optional[Exception] = None
    total_in, total_out, total_cost = 0, 0, 0.0
    gateway_started = time.perf_counter()

    for model_name, api_key, provider_type, is_fallback in models_to_try:
        # Check provider circuit breaker
        if not circuit_breaker.is_available(provider_type):
            logger.warning(f"Circuit breaker open for provider '{provider_type}'. Skipping candidate {model_name}.")
            continue

        # Check spending limits before executing
        est_cost = calculate_cost(model_name, 1000, 500)
        if settings.ENVIRONMENT != "production" and not settings.AGENT_ENABLED:
            spend_tracker.check_and_record(user_id, est_cost)

        start_time = time.perf_counter()
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            reservation = None
            billed_cost = None
            try:
                if settings.ENVIRONMENT == "production" or settings.AGENT_ENABLED:
                    if not api_key or model_name.lower() not in MODEL_PRICING:
                        raise ValueError("Production model requires a real key and configured model pricing.")
                    input_bound = len((system_prompt + user_prompt).encode("utf-8")) + 2048
                    reservation = await reserve_budget(user_id, calculate_cost(model_name, input_bound, 4096))
                # If no real API key configured in dev/test, generate deterministic fallback structure
                if not api_key:
                    raise ValueError("No provider key configured; use an explicit mock_response in tests.")
                elif settings.AGENT_ENABLED and provider_type.startswith("gemini"):
                    res_json = await provider_completion(api_key, settings.GEMINI_BASE_URL, model_name,
                        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                        temperature, settings.NEATLOGS_CAPTURE_CONTENT, settings.LLM_TIMEOUT_SECONDS)
                    raw_content = res_json["choices"][0]["message"]["content"]
                    usage = res_json.get("usage") or {}
                    in_tokens, out_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
                elif provider_type == "claude" or "claude" in model_name.lower():
                    # Anthropic Claude Messages API
                    endpoint = f"{settings.CLAUDE_BASE_URL.rstrip('/')}/messages"
                    headers = {
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    }
                    claude_prompt = user_prompt
                    if response_model:
                        claude_prompt += "\nIMPORTANT: Return ONLY a valid JSON object matching the requested schema."

                    payload = {
                        "model": model_name,
                        "max_tokens": 4096,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": claude_prompt}],
                        "temperature": temperature,
                    }
                    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                        resp = await client.post(endpoint, headers=headers, json=payload)
                        resp.raise_for_status()
                        res_json = resp.json()
                        raw_content = res_json["content"][0]["text"]
                        usage = res_json.get("usage", {})
                        in_tokens = usage.get("input_tokens")
                        out_tokens = usage.get("output_tokens")
                else:
                    # Gemini via OpenAI-compatible endpoint
                    endpoint = f"{settings.GEMINI_BASE_URL.rstrip('/')}/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "model": model_name,
                        "temperature": temperature,
                        "max_tokens": 4096,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    }
                    if response_model:
                        payload["response_format"] = {"type": "json_object"}

                    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                        resp = await client.post(endpoint, headers=headers, json=payload)
                        resp.raise_for_status()
                        res_json = resp.json()
                        raw_content = res_json["choices"][0]["message"]["content"]
                        usage = res_json.get("usage", {})
                        in_tokens = usage.get("prompt_tokens")
                        out_tokens = usage.get("completion_tokens")

                if type(in_tokens) is not int or type(out_tokens) is not int or min(in_tokens, out_tokens) < 0:
                    raise ValueError("Provider usage is missing; reservation remains charged, no metrics are invented.")
                billed_cost = calculate_cost(model_name, in_tokens, out_tokens)
                total_in += in_tokens
                total_out += out_tokens
                total_cost += billed_cost
                if reservation:
                    await settle_budget(reservation, billed_cost)
                    reservation = None
                # Schema validation if requested
                parsed_data = None
                if response_model:
                    try:
                        parsed_data = response_model.model_validate_json(raw_content)
                    except Exception as ve:
                        if attempt < settings.LLM_MAX_RETRIES:
                            logger.warning("Provider schema validation failed; output excluded from logs.")
                            continue
                        raise LLMValidationError("Model output failed schema validation; content excluded.") from None

                latency = round(time.perf_counter() - start_time, 4)
                actual_cost = calculate_cost(model_name, in_tokens, out_tokens)

                # Reconcile spend and report circuit breaker success
                if settings.ENVIRONMENT != "production" and not settings.AGENT_ENABLED:
                    spend_tracker.reconcile(user_id, est_cost, actual_cost)
                circuit_breaker.record_success(provider_type)

                return LLMResponse(
                    content=raw_content,
                    parsed=parsed_data,
                    model_used=model_name,
                    input_tokens=total_in,
                    output_tokens=total_out,
                    cost_usd=round(total_cost, 6),
                    latency_seconds=round(time.perf_counter() - gateway_started, 4),
                    fallback_used=is_fallback,
                )

            except (httpx.HTTPStatusError, httpx.RequestError, Exception) as err:
                last_error = err
                logger.warning("Provider call failed; prompt and response excluded from logs.")
                if settings.AGENT_ENABLED:
                    chosen = "retry" if attempt < settings.LLM_MAX_RETRIES else "fallback_model" if not is_fallback else "stop"
                    reason = f"{model_name} failed with {type(err).__name__} on attempt {attempt + 1}; {chosen}."
                    with recovery_decision("provider_failure", ["retry", "fallback_model", "stop"]) as recovery:
                        recovery.decide(chosen, reason)
                        recovery.finish("requested")
                    application_id = current_application_id()
                    if application_id:
                        async with AsyncSessionLocal() as event_session:
                            event_session.add(ApplicationEvent(application_id=UUID(application_id), actor="coordinator",
                                event_type="recovery_decision", payload={"trigger": "provider_failure", "chosen": chosen,
                                "reason": reason, "outcome": "requested", "options": ["retry", "fallback_model", "stop"]}))
                            await event_session.commit()
                if attempt < settings.LLM_MAX_RETRIES:
                    await asyncio.sleep(0.2 * (2 ** attempt))
                else:
                    # Refund estimated cost and trip circuit breaker on final attempt failure
                    if settings.ENVIRONMENT != "production" and not settings.AGENT_ENABLED:
                        spend_tracker.reconcile(user_id, est_cost, 0.0)
                    circuit_breaker.record_failure(provider_type)

    raise RuntimeError("All model providers failed; no generated output is available.") from None


def set_active_llm_provider(provider: str) -> None:
    """Dynamically switches active LLM provider between 'gemini' and 'claude' at runtime."""
    prov = provider.lower()
    if prov not in ("gemini", "claude", "openai"):
        raise ValueError(f"Unsupported LLM provider: {provider}. Must be 'gemini', 'claude', or 'openai'.")
    settings.LLM_PROVIDER = prov
    logger.info(f"Switched active LLM provider to: {settings.LLM_PROVIDER}")
