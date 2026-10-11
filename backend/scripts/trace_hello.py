import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from openai import OpenAI

from app.config import settings
from app.tracing import (
    init_tracing,
    shutdown_tracing,
    workflow_span,
    agent_span,
    tool_span,
    wrap_client,
    log_event,
)


@tool_span("hello_tool", description="Demonstrates tool span instrumentation")
def run_tool() -> str:
    log_event("Tool invoked successfully")
    return "Hello from tool!"


@agent_span("hello_agent", role="Greeter", goal="Demonstrate nested neatlogs agent span")
def run_agent() -> str:
    tool_result = run_tool()
    log_event("Agent received tool response", tool_result=tool_result)
    return f"Agent finished with: {tool_result}"


@workflow_span("scholarpilot_hello")
def run_hello_workflow() -> None:
    print("Executing hello workflow with neatlogs tracing...")
    agent_result = run_agent()
    print("Agent result:", agent_result)

    if settings.llm_primary_configured:
        print("Calling LLM with primary client wrapped in neatlogs...")
        raw_client = OpenAI(
            base_url=settings.llm_primary_base_url,
            api_key=settings.llm_primary_api_key,
        )
        client = wrap_client(raw_client)
        response = client.chat.completions.create(
            model=settings.llm_primary_model,
            messages=[{"role": "user", "content": "Reply with 'neatlogs hello OK'."}],
            max_tokens=20,
        )
        print("LLM Response:", response.choices[0].message.content)
    else:
        print("Note: LLM_PRIMARY_API_KEY not set in .env. LLM call skipped, spans generated.")


def main() -> None:
    init_tracing(tags=["hello"])
    try:
        run_hello_workflow()
    finally:
        shutdown_tracing()
        print("neatlogs hello trace flushed and finished.")


if __name__ == "__main__":
    main()
