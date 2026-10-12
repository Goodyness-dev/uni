"""Structured JSON logging with automated PII redaction."""
import contextvars
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# Context variables for distributed tracing
request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
job_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("job_id", default=None)

# Patterns for sensitive field keys and content
SENSITIVE_KEYS = {
    "password", "secret", "token", "api_key", "full_name", "first_name",
    "last_name", "email", "phone", "phone_number", "nin", "bvn", "ssn",
    "id_number", "essay_text", "essay", "statement", "cv_text",
    "transcript", "address", "date_of_birth", "dob", "bank_account",
    "content", "draft_text", "input_text", "user_prompt", "system_prompt"
}

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
NIN_BVN_REGEX = re.compile(r"\b(?:NIN|BVN|National ID|ID)[\s:#_-]*([0-9]{11})\b", re.IGNORECASE)
TOKEN_REGEX = re.compile(r"(Bearer\s+|api_key=|token=)[A-Za-z0-9_\-\.]{12,}", re.IGNORECASE)
API_KEY_REGEX = re.compile(r"\b(?:sp_live_[A-Za-z0-9_]{16,}|sk-[A-Za-z0-9]{16,})\b")


def redact_pii_value(val: Any) -> Any:
    """Recursively redacts PII strings and dictionary keys."""
    if isinstance(val, str):
        # Scrub email, phone, SSN, ID, token, and API key patterns in text
        val = EMAIL_REGEX.sub("[REDACTED_EMAIL]", val)
        val = PHONE_REGEX.sub("[REDACTED_PHONE]", val)
        val = SSN_REGEX.sub("[REDACTED_SSN]", val)
        val = NIN_BVN_REGEX.sub("[REDACTED_ID]", val)
        val = TOKEN_REGEX.sub(r"\1[REDACTED_TOKEN]", val)
        val = API_KEY_REGEX.sub("[REDACTED_KEY]", val)
        return val
    elif isinstance(val, dict):
        cleaned = {}
        for k, v in val.items():
            if str(k).lower() in SENSITIVE_KEYS:
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_pii_value(v)
        return cleaned
    elif isinstance(val, list):
        return [redact_pii_value(item) for item in val]
    return val


class JSONPIIRedactingFormatter(logging.Formatter):
    """Custom logging formatter that renders structured JSON and sanitizes PII."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_pii_value(record.getMessage()),
            "request_id": request_id_ctx.get(),
            "job_id": job_id_ctx.get(),
        }

        # Include custom extra attributes
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_entry["extra"] = redact_pii_value(record.extra)

        if record.exc_info:
            log_entry["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures the root logger with the structured JSON PII redacting handler."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONPIIRedactingFormatter())
    root_logger.addHandler(handler)

    return logging.getLogger("scholarpilot")


logger = logging.getLogger("scholarpilot")
