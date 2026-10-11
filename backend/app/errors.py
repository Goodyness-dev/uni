from dataclasses import dataclass, field


@dataclass
class RunContext:
    run_id: str = ""
    app_id: str | None = None
    application_id: str | None = None
    mode: str = "B"
    listing_id: str | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.application_id and not self.app_id:
            self.app_id = self.application_id
        elif self.app_id and not self.application_id:
            self.application_id = self.app_id




class ScholarPilotError(Exception):
    """Base exception for all ScholarPilot errors."""
    pass


class LLMError(ScholarPilotError):
    """Base exception for all LLM errors."""
    pass


class RateLimitError(LLMError):
    """Raised when an LLM provider returns a 429 rate limit or quota exceeded."""
    pass


class TimeoutError_(LLMError):
    """Raised on LLM provider timeout or 5xx connection failure."""
    pass


class ModelNotFoundError(LLMError):
    """Raised when the specified model ID is rejected by the provider."""
    pass


class BadJSONError(LLMError):
    """Raised when LLM output cannot be parsed or repaired into valid JSON matching schema."""
    pass


class ResearchError(ScholarPilotError):
    """Raised when research source retrieval fails."""
    pass


class SmtpError(ScholarPilotError):
    """Raised when an email transmission fails."""
    pass


class PortalError(ScholarPilotError):
    """Raised when demo portal responds with an HTTP error."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class BlockerDetected(ScholarPilotError):
    """Raised when an automated form blocker (e.g. CAPTCHA, login gate) is encountered."""
    def __init__(self, message: str, blocker_type: str = "captcha", portal_url: str = ""):
        super().__init__(message)
        self.blocker_type = blocker_type
        self.portal_url = portal_url
