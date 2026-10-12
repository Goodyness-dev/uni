"""Authenticated Neatlogs MCP readback; credentials stay in local configuration."""
import asyncio
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import settings


def decode(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    if "application/json" in response.headers.get("content-type", ""):
        return response.json()
    return json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith("data: ")))


async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    endpoint = (settings.NEATLOGS_ENDPOINT or "https://ingest.neatlogs.com").rstrip("/") + "/mcp"
    if not settings.NEATLOGS_API_KEY:
        raise ValueError("A configured Neatlogs project key is required.")
    headers = {"Authorization": "Bearer " + settings.NEATLOGS_API_KEY, "Accept": "application/json, text/event-stream"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(endpoint, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "scholarpilot-evidence", "version": "1"}}})
        decode(response)
        if response.headers.get("mcp-session-id"):
            headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
        response = await client.post(endpoint, headers=headers, json={"jsonrpc": "2.0", "id": 2,
            "method": "tools/call", "params": {"name": name, "arguments": arguments}})
        envelope = decode(response)
        if "error" in envelope:
            raise ValueError("Neatlogs MCP rejected the operation.")
        return envelope["result"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tool", choices=("get_trace_context", "list_detections", "get_project_analytics", "get_detection_capabilities"))
    parser.add_argument("--trace-id")
    parser.add_argument("--from", dest="from_time")
    parser.add_argument("--to", dest="to_time")
    parser.add_argument("--view", choices=("kpis", "cost", "errors", "time", "tools", "detections"), default="kpis")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    arguments = {"trace_id": args.trace_id} if args.trace_id else {}
    if args.tool == "get_project_analytics":
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        arguments = {"from": args.from_time or today.isoformat(), "to": args.to_time or (today + timedelta(days=1)).isoformat(),
            "view": args.view, "workflow_name": "scholarpilot"}
    result = asyncio.run(call_tool(args.tool, arguments))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Neatlogs response saved; isError=" + str(result.get("isError", False)))
    if result.get("isError"):
        raise SystemExit(2)
