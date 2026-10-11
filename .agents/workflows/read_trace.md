When the user types /read_trace with a tag or trace id:
1. Use the neatlogs MCP tools (or the neatlogs CLI if MCP is unavailable) to find the trace.
2. List GUARDRAIL spans that did not pass, the claims involved, and the slowest and most expensive spans.
3. Propose the smallest fix. Do not change code until the user approves.
