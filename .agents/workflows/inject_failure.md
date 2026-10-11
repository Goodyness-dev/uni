When the user types /inject_failure with a flag name (llm_429, bad_json, portal_500, captcha_wall, research_down, smtp_fail, injection_page):
1. Set the flag through POST /api/failure_flags (count 2 for llm_429, 1 for the others that are counted).
2. Start a run for the persona with mode B and top_n 2.
3. Print the application timeline events including failure_injected and recovery_decision.
4. Clear the flag and print the neatlogs trace link if available.
