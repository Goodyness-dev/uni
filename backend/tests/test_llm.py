import json
import os
import tempfile
import pytest
from pydantic import BaseModel
import httpx

from app import db
from app.config import settings
from app.errors import RunContext, RateLimitError, ModelNotFoundError, BadJSONError
from app.llm import call_llm, set_clients_for_tests


class DummyChoice:
    def __init__(self, content: str):
        self.message = type("Msg", (), {"content": content})()


class DummyUsage:
    def __init__(self, prompt_tokens: int = 10, completion_tokens: int = 20):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class DummyResponse:
    def __init__(self, content: str, prompt_tokens: int = 10, completion_tokens: int = 20):
        self.choices = [DummyChoice(content)]
        self.usage = DummyUsage(prompt_tokens, completion_tokens)


class FakeClient:
    def __init__(self, responses=None, side_effects=None):
        self.responses = list(responses or [])
        self.side_effects = list(side_effects or [])
        self.calls = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.side_effects:
            eff = self.side_effects.pop(0)
            if isinstance(eff, Exception):
                raise eff
        if self.responses:
            return self.responses.pop(0)
        return DummyResponse('{"answer": "default"}')


class OutputModel(BaseModel):
    answer: str


@pytest.fixture(autouse=True)
def temp_db_and_clean_clients():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name
    os.environ["TEST_DB_PATH"] = temp_path
    os.environ["RETRY_SLEEP_SECONDS"] = "0"
    db.init_db()
    yield
    set_clients_for_tests(None, None)
    if os.path.exists(temp_path):
        os.remove(temp_path)
    os.environ.pop("TEST_DB_PATH", None)
    os.environ.pop("RETRY_SLEEP_SECONDS", None)


def test_call_llm_success():
    fake = FakeClient(responses=[DummyResponse('{"answer": "valid_reply"}')])
    set_clients_for_tests(primary=fake, fallback=None)

    ctx = RunContext(run_id="run_test", application_id="app_1")
    result = call_llm("test_prompt", "sys", "usr", OutputModel, ctx)

    assert result.parsed["answer"] == "valid_reply"
    assert result.fallback_used is False
    assert result.tokens_in == 10
    assert result.tokens_out == 20


def test_call_llm_rate_limit_then_fallback():
    rate_err = RateLimitError("rate limited")
    primary = FakeClient(side_effects=[rate_err, rate_err])
    fallback = FakeClient(responses=[DummyResponse('{"answer": "fallback_ok"}')])
    set_clients_for_tests(primary=primary, fallback=fallback)

    ctx = RunContext(run_id="run_test", application_id="app_1")
    result = call_llm("test_prompt", "sys", "usr", OutputModel, ctx)

    assert result.parsed["answer"] == "fallback_ok"
    assert result.fallback_used is True


def test_call_llm_model_not_found_switches_instantly():
    not_found = ModelNotFoundError("model not found")
    primary = FakeClient(side_effects=[not_found])
    fallback = FakeClient(responses=[DummyResponse('{"answer": "fallback_model_ok"}')])
    set_clients_for_tests(primary=primary, fallback=fallback)

    ctx = RunContext(run_id="run_test", application_id="app_1")
    result = call_llm("test_prompt", "sys", "usr", OutputModel, ctx)

    assert result.parsed["answer"] == "fallback_model_ok"
    assert result.fallback_used is True


def test_call_llm_json_repair():
    primary = FakeClient(responses=[
        DummyResponse('{"answer": "half_broken'),
        DummyResponse('{"answer": "repaired"}'),
    ])
    set_clients_for_tests(primary=primary, fallback=None)

    ctx = RunContext(run_id="run_test", application_id="app_1")
    result = call_llm("test_prompt", "sys", "usr", OutputModel, ctx)

    assert result.parsed["answer"] == "repaired"
    assert result.json_repaired is True


def test_call_llm_flag_llm_429_injection():
    db.set_flag("llm_429", enabled=True, count=2)
    fallback = FakeClient(responses=[DummyResponse('{"answer": "saved_by_fallback"}')])
    set_clients_for_tests(primary=FakeClient(), fallback=fallback)

    ctx = RunContext(run_id="run_test", application_id="app_1")
    result = call_llm("test_prompt", "sys", "usr", OutputModel, ctx)

    assert result.parsed["answer"] == "saved_by_fallback"
    assert result.fallback_used is True
