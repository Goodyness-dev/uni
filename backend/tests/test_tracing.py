from app.tracing import (
    workflow_span,
    agent_span,
    tool_span,
    retriever_span,
    guardrail,
    recovery_decision,
    tracing_enabled,
)


def test_span_decorators_return_value_offline() -> None:
    @workflow_span("test_workflow")
    def sample_workflow(x: int) -> int:
        return x * 2

    @agent_span("test_agent", role="Tester", goal="Test decorator")
    def sample_agent(x: int) -> int:
        return x + 5

    @tool_span("test_tool", description="Test tool")
    def sample_tool(s: str) -> str:
        return f"tool_{s}"

    @retriever_span("test_retriever")
    def sample_retriever() -> list[str]:
        return ["doc1", "doc2"]

    assert sample_workflow(3) == 6
    assert sample_agent(5) == 10
    assert sample_tool("run") == "tool_run"
    assert sample_retriever() == ["doc1", "doc2"]


def test_guardrail_context_manager_offline() -> None:
    with guardrail("test_guardrail") as g:
        g.set_result(passed=True, input_text="claim test", reason="fully verified")
        g.attrs(custom_attr="ok")


def test_recovery_decision_context_manager_offline() -> None:
    with recovery_decision(trigger="llm_429", options=["retry", "fallback"]) as r:
        r.decide(chosen="fallback", reason="rate limit exceeded twice")
        r.finish(outcome="recovered")
