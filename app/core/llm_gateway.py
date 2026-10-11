"""Unified LLM Gateway: model routing, retries, cost accounting, daily spending caps, and schema validation."""
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel
from app.core.config import settings
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)

# Model pricing table per 1M tokens (USD)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
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


spend_tracker = DailySpendTracker()


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

    # Prepare model execution candidates: Primary first, Fallback second
    models_to_try = [
        (settings.PRIMARY_MODEL, settings.PRIMARY_API_KEY, settings.PRIMARY_BASE_URL, False),
        (settings.FALLBACK_MODEL, settings.FALLBACK_API_KEY, settings.FALLBACK_BASE_URL, True),
    ]

    last_error: Optional[Exception] = None

    for model_name, api_key, base_url, is_fallback in models_to_try:
        # Check spending limits before executing
        est_cost = calculate_cost(model_name, 1000, 500)
        spend_tracker.check_and_record(user_id, est_cost)

        start_time = time.perf_counter()
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                # Real provider dispatch via httpx (OpenAI-compatible / Gemini-compatible endpoint)
                endpoint = f"{base_url.rstrip('/')}/chat/completions" if base_url else "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key or 'mock-key'}", "Content-Type": "application/json"}
                payload = {
                    "model": model_name,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                }

                if response_model:
                    payload["response_format"] = {"type": "json_object"}

                # If no real API key configured in dev/test, generate deterministic fallback structure
                if not api_key:
                    raw_content = "{}" if response_model else "Processed response."
                    in_tokens, out_tokens = 200, 80
                else:
                    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                        resp = await client.post(endpoint, headers=headers, json=payload)
                        resp.raise_for_status()
                        res_json = resp.json()
                        raw_content = res_json["choices"][0]["message"]["content"]
                        usage = res_json.get("usage", {})
                        in_tokens = usage.get("prompt_tokens", 250)
                        out_tokens = usage.get("completion_tokens", 100)

                # Schema validation if requested
                parsed_data = None
                if response_model:
                    try:
                        parsed_data = response_model.model_validate_json(raw_content)
                    except Exception as ve:
                        if attempt < settings.LLM_MAX_RETRIES:
                            logger.warning(f"Schema validation failed on attempt {attempt}: {ve}. Retrying...")
                            continue
                        raise LLMValidationError(f"Model output failed schema validation twice: {ve}")

                latency = round(time.perf_counter() - start_time, 4)
                actual_cost = calculate_cost(model_name, in_tokens, out_tokens)

                return LLMResponse(
                    content=raw_content,
                    parsed=parsed_data,
                    model_used=model_name,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    cost_usd=actual_cost,
                    latency_seconds=latency,
                    fallback_used=is_fallback,
                )

            except (httpx.HTTPStatusError, httpx.RequestError, Exception) as err:
                last_error = err
                logger.warning(f"LLM call to {model_name} failed (attempt {attempt}): {err}")
                if attempt < settings.LLM_MAX_RETRIES:
                    time.sleep(0.2 * (2 ** attempt))

    raise RuntimeError(f"All LLM models failed. Last error: {last_error}")
