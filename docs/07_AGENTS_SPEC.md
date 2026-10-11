# 07_AGENTS_SPEC.md

Exact behavior of every module. Function names, inputs, outputs and algorithms are fixed. Signatures are written as `name(arguments)` followed by `Returns:` (no arrow syntax). Types refer to `05_DATA_MODELS.md`. Prompt text is in `08_PROMPTS.md`. Span rules are in `09_NEATLOGS_SPEC.md`.

General coding rules for every function below:
1. Type hints on all arguments and returns (write return types with the word `Returns` in this document only, in real code use normal Python annotations).
2. Never import an LLM SDK outside `llm.py`.
3. Every agent function is wrapped with the helper from `tracing.py` named in its section.
4. Agents raise the typed errors from `app/errors.py`. The Coordinator catches them.
5. Agents never write to `applications.status` directly. They return data. Only the Coordinator calls `db.set_status`.

## 1. Helpers

### 1.1 `db.py` function list (all open and close their own connection)

1. `init_db()` creates tables and seeds `failure_flags`.
2. `now_str()` returns the current UTC time as `YYYY/MM/DD HH:MM:SS`.
3. `today_date()` returns the current UTC `date`, or the date from `settings.today_override` (format `YYYY/MM/DD`) when set.
4. Facts: `replace_facts(facts)`, `list_facts()`, `get_fact(fact_id)`, `update_fact_text(fact_id, text)`, `add_vault_fact(category, text)` (next `P` id), `set_preferences(prefs)`, `get_preferences()`.
5. Runs: `create_run(mode, top_n, live_research)` returns the new run id (`run_YYYYMMDD_NNN`), `get_run(run_id)`, `latest_run()`, `finish_run(run_id, status, metrics)`, `mark_interrupted_runs()`.
6. Applications: `create_application(run_id, listing_id, channel)` returns id `app_N` (N is the total number of applications plus one), `get_application(app_id)`, `list_applications(run_id)`, `update_application(app_id, **fields)` (JSON fields are dumped automatically), `set_status(app_id, new_status, message, agent="coordinator")` (validates the transition from `04_ARCHITECTURE.md` section 6, writes an event of type `status_changed`, updates `updated_at`, then calls `notify.on_status_change`).
7. Events: `add_event(run_id, application_id, agent, type, message, data=None)` returns the event number, `list_events(run_id, after)`, `list_application_events(app_id)`.
8. Notifications: `add_notification(run_id, application_id, channel, text, sent)`, `list_notifications(app_id)`, `list_unsent_notifications()`, `mark_notification_sent(id)`.
9. Gaps: `add_gap(application_id, criterion, question)`, `list_gaps(run_id)`, `answer_gap(gap_id)`.
10. Flags: `get_flags()`, `set_flag(name, enabled, count)`, `consume_flag(name)` returns True when the flag was active and a use was consumed (decrements `remaining` for counted flags and switches them off at zero; for uncounted flags `captcha_wall` and `injection_page` it returns True without decrementing).
11. Portal: `create_draft(listing_id, idempotency_key, fields)`, `get_draft(draft_id)`, `submit_draft(draft_id)` returns the confirmation code (generates `DEMO` plus 4 digits once, idempotent).
12. Poller: `get_last_update_id()`, `set_last_update_id(n)`.

### 1.2 `llm.py`: `call_llm`

Signature: `call_llm(prompt_name: str, system: str, user: str, schema: type[BaseModel], ctx: RunContext, temperature: float = 0.2, max_tokens: int = 2000)`.
Returns: `LLMResult` (see models).

Create two module level clients at first use (lazy): `primary_client = neatlogs.wrap(OpenAI(base_url=settings.llm_primary_base_url, api_key=settings.llm_primary_api_key))` and the same for the fallback. If an API key is empty, that client is None.

Algorithm:
1. Build `messages = [system message, user message]`.
2. Open the LLM prompt span via `tracing.llm_call_span(prompt_name, system, user, ctx)` (a context manager).
3. `attempt = 0`, `use_fallback = False`, `fallback_used = False`.
4. Loop while True:
   1. `attempt += 1`.
   2. If not `use_fallback` and `db.consume_flag("llm_429")` is True: record event `failure_injected` (data flag `llm_429`) and treat as a `RateLimitError` without calling the provider.
   3. Else call `client.chat.completions.create(model=..., messages=messages, temperature=temperature, max_tokens=max_tokens, response_format={"type": "json_object"})` on the primary (or fallback when `use_fallback`). If the provider rejects `response_format`, retry once without it and remember that for the client.
   4. Map exceptions: `openai.RateLimitError` becomes `RateLimitError`; `openai.APITimeoutError` and `openai.APIConnectionError` become `TimeoutError_`; `openai.NotFoundError` becomes `ModelNotFoundError`; any other `openai.APIStatusError` with status 500 or above becomes `TimeoutError_` (retryable); other status errors become `LLMError`.
   5. On `ModelNotFoundError` from the primary: immediately switch to fallback (no retries) with a recovery decision (trigger `model_not_found`, options `fallback_model`, chosen `fallback_model`).
   6. On `RateLimitError` or `TimeoutError_`: add event `retry`, sleep `settings.retry_sleep_seconds` times 1, 2, 4 for attempts 1, 2, 3. When `attempt` is 2 or more, or when the same error repeated twice, switch to fallback with a recovery decision (trigger `llm_429` or `llm_timeout`, options `retry`, `fallback_model`, chosen `fallback_model`, reason names the repeat count). If already on the fallback and attempts are exhausted (attempt 4 or more) raise the error.
   7. On success read `text = response.choices[0].message.content`.
5. JSON handling:
   1. If `db.consume_flag("bad_json")` is True: truncate `text` to its first half and record `failure_injected`.
   2. `clean = strip_fences(text)` (remove leading and trailing triple backtick fences and a leading word json). Try `json.loads(clean)` then `schema.model_validate(data)`.
   3. On failure: record event `json_repair`, make ONE repair call to the same client with the system prompt `REPAIR_SYSTEM` and the broken text, parse again.
   4. On failure again: make one regeneration call with temperature 0.0 and the original messages. If that fails, raise `BadJSONError`.
6. Compute `tokens_in` and `tokens_out` from `response.usage.prompt_tokens` and `completion_tokens` (sum across all calls made in this function), cost from the price settings for the model used, latency as wall time for the whole function.
7. Set span attributes (section 3 of `09_NEATLOGS_SPEC.md`): `prompt_version`, `model`, `attempt`, `fallback_used`, `json_repaired`, `tokens_in`, `tokens_out`, `cost_usd`.
8. Return `LLMResult(parsed=validated.model_dump(), ...)`.

Tests (fake clients, no network, `retry_sleep_seconds` set to 0): success path; 429 then success; 429 twice then fallback success; both fail raises; bad JSON then repair success; bad JSON twice then regeneration success; flag injection for `llm_429` and `bad_json`; model not found goes straight to fallback.

### 1.3 `sensitive.py`

1. `SENSITIVE_CATEGORIES = {"health", "religion", "disability", "family_income", "immigration"}`.
2. `is_sensitive_text(text)`: lowercase keyword check for these stems: health, medical, illness, disease, disabled, disability, religion, church, mosque, pastor, imam, income, poverty, salary, immigration, visa, refugee. Returns True if any appears as a whole word or stem at a word start.
3. `strip_sensitive(facts, listing, consent)`: Returns a list of facts. Removes every fact where `fact.sensitive` is True or its category is in `SENSITIVE_CATEGORIES`, unless `consent` is True AND the listing's `requires_sensitive` contains that fact's category.
4. `contains_sensitive(output_text)`: Returns the list of matched stems (used by the final output scan and tests).
5. Tests: sensitive fact removed by default; allowed only with consent plus a matching `requires_sensitive`; category based removal; output scan catches stems.

### 1.4 `notify.py`

1. `send_telegram(text, ctx, reply_markup=None)`: POST to `https://api.telegram.org/bot{token}/sendMessage` with JSON `{"chat_id": ..., "text": ..., "reply_markup": ...}` using `httpx` with a 10 second timeout, inside a TOOL span `send_telegram`. Always writes a `notifications` row first (sent false), then marks it sent on success. On failure logs an event and returns False. Never raises.
2. `send_email(to, subject, body, attachments)`: `smtplib` with STARTTLS, login with the app password, attachments from file paths. Inside a TOOL span `send_email`. Raises `SmtpError` on failure. If `db.consume_flag("smtp_fail")` is True raise `SmtpError("simulated failure")` after recording `failure_injected`.
3. Template functions (exact wording from `05_DATA_MODELS.md` section 7): `tpl_matches_found`, `tpl_researched`, `tpl_edges_used`, `tpl_verified`, `tpl_submitted`, `tpl_prepared`, `tpl_handoff`, `tpl_failed`, `tpl_gap`, `tpl_restricted_briefing`.
4. `on_status_change(app_id, new_status, ctx)`: sends the message for these statuses: `researched`, `verified`, `submitted`, `prepared`, `awaiting_user` (handoff, with the inline keyboard: a Done button with callback data `done:{app_id}` and a URL button Open to the Handoff screen), `failed`. Edge messages are sent by the Coordinator after edges are selected.
5. `retry_unsent()`: tries every unsent notification once (called at the end of a run).
6. `start_poller()`: starts a daemon thread (called in the FastAPI lifespan when a Telegram token exists) that every 3 seconds calls `getUpdates` with `offset = last_update_id + 1` and timeout 0, handles each update, then stores the last update id. For a `callback_query` whose data starts with `done:`, call `applier.resume_after_handoff(app_id)` in the same thread, then call `answerCallbackQuery` with a short text. Wrap the whole loop body in try and except so the thread never dies. Every poll iteration is NOT traced (too noisy); only the handled callback is traced as a TOOL span `telegram_callback`.

## 2. Intake (`agents/intake.py`)

Span helper: `agent_span("intake")`.

Function `run_intake(payload, ctx)`. Returns: dict with `facts` (list of Fact), `counts`, `warnings`.

Steps:
1. CV text: if `cv_text` is non empty use it. Else if `cv_pdf_base64` is present: decode with `base64.b64decode`, read with `pypdf.PdfReader(io.BytesIO(bytes))`, join page texts with newlines. If the extracted text has fewer than 200 characters add the warning "The PDF text looks too short. Paste your CV text instead." and continue with what exists.
2. Chunk each document: split on blank lines and group into chunks of at most 6000 characters.
3. For each chunk call `call_llm("intake_v1", INTAKE_SYSTEM, user_text, IntakeOut, ctx)` where `IntakeOut` is a Pydantic model with `facts: list[IntakeFact]` and `IntakeFact` has `category: str`, `text: str`, `sensitive: bool`.
4. For the Vault: process each non empty section separately, passing the section name in the user text and forcing the category to the section name mapping (sports to `sports`, volunteering to `volunteering`, certifications to `certifications`, leadership to `leadership`, awards to `awards`, projects to `projects`, languages to `languages`, hardships to `hardships`, career_goals to `goals`, why_abroad to `goals`). Free text goes through the generic extraction.
5. Post processing per fact: trim whitespace, drop empty or duplicate texts (normalize by lowercase and collapsed spaces), set `sensitive = True` when the model says so OR `is_sensitive_text(text)` is True OR the category is in the sensitive categories.
6. Deterministic number check: for each fact extract numbers with the regex `\d+(?:\.\d+)?`; every number must appear in the chunk text it came from. A fact that fails is dropped and a warning is added ("Dropped a fact whose numbers were not in the source").
7. Assign ids in order: `C1..` for cv, `T1..` for transcript, `P1..` for vault. Persist with `db.replace_facts`. Persist preferences with `db.set_preferences`.
8. Event `step_completed` with counts.

Tests: fact ids assigned by source, number check drops altered facts (fake LLM returning a changed number), sensitive flag set by keyword, duplicates removed.

## 3. Scout (`agents/scout.py`)

Span helper: `retriever_span("scout")`.

Function `load_listings()`. Returns: list of Listing. Reads `backend/data/listings.json`, validates each entry with `Listing.model_validate`, raises a clear `ValueError` naming the entry id if invalid. Records the query `all listings` and the number returned as retriever attributes.

Function `filter_open(listings, today)`. Returns: list of Listing with deadline on or after `today` (parse with `datetime.strptime(deadline, "%Y/%m/%d").date()`). Expired listings are kept in a second returned list so the Matcher can mark them `skipped` with the reason "deadline passed" (so the UI can show why).

## 4. Matcher (`agents/matcher.py`)

Span helper: `agent_span("matcher")` with a TOOL span `hard_rules` and the LLM span from `llm.py`.

Function `hard_rules(listing, prefs, today)`. Returns: `HardRuleResults`. Rules (exact):
1. `country`: True if `prefs.countries` is empty or the listing country (case insensitive) is in `prefs.countries`.
2. `level`: True if `listing.level` equals `prefs.level`.
3. `gpa`: True if `listing.min_gpa` is 0, else `(prefs.gpa / prefs.gpa_scale) >= (listing.min_gpa / listing.gpa_scale)`.
4. `field`: True if `prefs.fields` is empty, else True if any lowercase preference field is contained in any lowercase listing field or the reverse.
5. `deadline`: True if the listing deadline date is on or after `today`.
6. `nationality`: True if `listing.eligible_nationalities` is empty, else True if `prefs.nationality` (case insensitive) is in the list.

Function `score_fit(listing, facts, ctx)`. Returns: `(fit_score: int, fit_reason: str, missing_criteria: list[str])` using `call_llm("matcher_v1", ...)` with the allowed facts only (after `strip_sensitive`) and the listing criteria text. Clamp the score to 0 to 100.

Function `run_matcher(listings, expired, facts, prefs, run_id, mode, ctx)`. Returns: list of created application ids. For each listing: create the application row (`found`), compute hard rules. If any fails: set status `skipped`, store `failed_rules_json` (names of failed rules) and `fit_reason` like "Not eligible: gpa, nationality". Else score fit, store `fit_score`, `fit_reason`, `hard_rules_json`, set status `matched`. If `missing_criteria` exist, create up to 2 gaps (question text: "This scholarship values {criterion}. Do you have experience with it?"). Send the `matches_found` notification once after all listings are processed.

Tests: GPA normalization (4.3 of 5.0 passes a 3.5 of 4.0 rule: 0.86 versus 0.875 fails; check your numbers), nationality, deadline boundary (today passes), field containment.

## 5. Researcher (`agents/researcher.py`)

Span helper: `agent_span("researcher")`.

Function `build_dossier(listing, live, ctx)`. Returns: `Dossier`.

Order:
1. If `live` is True OR `db.consume_flag` is not used here: check `research_down` with `db.get_flags()["research_down"]` (do not consume, it stays on until switched off). If `live` or `research_down` is on, try `fetch_live(listing, ctx)`.
2. If the live attempt raises `ResearchError` (including simulated by `research_down`): open a `recovery_decision` (trigger `research_unreachable`, options `use_cache`, `degrade_dossier`, chosen `use_cache`, reason "live source failed, a cached dossier with source URLs exists") and fall through to the cache. Add event `research_used_cache`.
3. Cache: if `data/dossier_cache/{listing.id}.json` exists, load into `Dossier(degraded=False)`.
4. If no cache exists: return a degraded `Dossier` with one fact: topic `scholarship_priorities`, text equal to the first 40 words of `listing.criteria_text`, `source_url = listing.source_url`, `snippet` the same first 25 words. `degraded=True`.

Function `fetch_live(listing, ctx)`. Returns: list of `DossierFact`. Steps:
1. If `db.get_flags()["research_down"]` raise `ResearchError("simulated")`.
2. Source selection: if the listing is mock (`is_mock`), fetch `settings.public_base_url + "/portal/about/" + listing.id` with `httpx.get` (10 second timeout, follow no redirects). Else if `settings.crustdata_api_key` is set, use the Crustdata path (stretch task, raise `ResearchError("not configured")` until implemented). Else raise `ResearchError`.
3. Strip HTML to text with regex (remove script and style blocks, remove tags, collapse whitespace) inside a TOOL span `fetch_page`.
4. Injection scan: split into lines, drop any line matching the case insensitive regex `ignore previous|ignore all|disregard|system prompt|you are now|do not tell` and add an event `injection_detected` with the dropped line count. Set span attribute `injection_dropped`. Then wrap the remaining text as `<<<PAGE_TEXT` newline text newline `PAGE_TEXT>>>`.
5. Call `call_llm("researcher_v1", RESEARCHER_SYSTEM, wrapped_text, ResearcherOut, ctx)` where `ResearcherOut` has `facts: list[{topic, text, snippet}]`.
6. Verify each snippet appears in the page text (case insensitive, whitespace collapsed). Drop facts whose snippet is missing (count `snippets_dropped`). Assign ids `D1..`, set `source_url`, `retrieved_at = now_str()`.
7. If zero facts survive raise `ResearchError("no verified facts")`.

Test: snippet check drops invented snippets, injection lines dropped, `research_down` falls back to cache and records a recovery decision.

## 6. Edge Finder (`agents/edge_finder.py`)

Span helper: `agent_span("edge_finder")`.

Function `find_edges(listing, dossier, facts, prefs, ctx)`. Returns: `(edges: list[Edge], gaps: list[dict])`.

Steps:
1. `allowed = strip_sensitive(facts, listing, prefs.sensitive_consent)` inside a TOOL span `strip_sensitive`.
2. Build the user text: listing criteria, essay prompt, dossier facts as `D1: text`, applicant facts as `C1: text`.
3. `call_llm("edge_v1", EDGE_SYSTEM, user, EdgeOut, ctx)`.
4. Validate: every `profile_fact_ids` entry must be in `allowed` ids, every `dossier_fact_ids` entry in the dossier ids. Drop edges that fail and add an event `edge_dropped` with the reason. Drop edges with empty id lists.
5. Sort by `strength` descending. Assign ids `E1..`. Mark `selected = True` for edges with `strength >= 0.6`, at most 3. Each selected edge gets an event `edge_selected` with its reason and a neatlogs log line.
6. For model returned gaps (max 2): return them for the Coordinator to store with `db.add_gap`.
7. Degraded dossier rule: if `dossier.degraded` is True, only edges whose `use_in` is `cv_bullet` may be selected (no school specific claims).

Tests: invalid ids dropped, threshold and max 3, sensitive fact never appears in the prompt text (assert on the built user text), degraded rule.

## 7. Tailor (`agents/tailor.py`)

Span helper: `agent_span("tailor")`.

Function `build_sources(listing, facts, dossier, edges, prefs)`. Returns: dict mapping source id to text, containing: every allowed fact referenced by a selected edge, plus all allowed facts with category in `education`, `grades`, `work`, `projects` (core CV facts), plus all dossier facts referenced by selected edges. This dict is the ONLY allowed grounding set and is reused by the Verifier.

Function `tailor_full(listing, sources, edges, prefs, ctx)`. Returns: `TailoredOutput`.
1. Build the user text: the listing name, essay prompt, word limit, the selected edges (reason and `use_in`), and the sources as `id: text` lines.
2. `call_llm("tailor_v1", TAILOR_SYSTEM, user, TailorOut, ctx, temperature=0.5, max_tokens=2500)`.
3. Validation in code: drop segments with empty `source_ids` or any id not in `sources` (event `segment_dropped`). If the essay is empty after validation raise `LLMError`.
4. Word limit: count words in the essay segments. If over `essay_word_limit`, make ONE revision call `tailor_revise_v1` stating the limit. If still over, remove whole segments from the end until under the limit and add an event.
5. Return `TailoredOutput(mode="full", ...)`.

Function `tailor_revise(listing, sources, tailored, problem_segments, ctx)`. Returns: `TailoredOutput`. Calls `call_llm("tailor_revise_v1", ...)` with the problem segments and their reasons, replaces only those segments by index, keeps the rest unchanged.

Function `tailor_notes_only(listing, sources, edges, facts, ctx)`. Returns: `TailoredOutput(mode="notes_only")`. See section 9.

Tests: segments with unknown ids dropped, word limit enforcement, revision replaces only listed segments.

## 8. Verifier (`agents/verifier.py`)

Span helpers: `agent_span("verifier")` for the whole stage, `guardrail("verification_round")` for each audit round, `guardrail("adversarial_challenge")` for the challenger.

### 8.1 Deterministic check

Function `deterministic_check(claim_text, source_ids, sources)`. Returns: `bool`. Inside a TOOL span `deterministic_claim_check`.
1. If `source_ids` is empty or any id is not in `sources`: return False.
2. `source_blob = lowercase of the joined texts of the cited sources`.
3. Normalize number words in both the claim and the source blob with this map: one 1, two 2, three 3, four 4, five 5, six 6, seven 7, eight 8, nine 9, ten 10, twelve 12, twenty 20, fifty 50, hundred 100.
4. Extract numbers from the claim with the regex `\d+(?:\.\d+)?`. Each must appear in the source blob as a whole token.
5. Extract capitalized tokens from the claim that are not at the start of a sentence, are longer than 2 characters and are not in the stop list (I, The, A, An, My, In, On, At, And). Each must appear in the source blob (lowercase compare).
6. Return True only if all checks pass.

### 8.2 Audit

Function `audit(tailored, sources, ctx, round_no)`. Returns: `VerificationReport` (a report with claims and verdicts, `rounds` set to `round_no`).
1. Flatten the segments of `cv_summary`, `cv_bullets` and `essay` into a numbered list (skip segments with status `removed`).
2. One LLM call `verifier_extract_v1` returns claims: `{text, section, segment_index}`. Attach the cited `source_ids` of the segment to each claim. If the model returns no claims for a segment, create one claim from the whole segment text.
3. Run `deterministic_check` for each claim.
4. Judge in batches of at most 10 claims with `verifier_judge_v1`. The user text lists each claim with its cited source texts.
5. Verdict: judge `unsupported` gives `unsupported`. Judge `partial` gives `partial`. Judge `supported` and deterministic True gives `supported`. Judge `supported` and deterministic False gives `partial`.
6. `llm_pass` is True when the judge says supported. Set `reason` from the judge.
7. Inside `guardrail("verification_round")`: `passed = (number of claims whose verdict is not supported) equals 0`, input is the claims text, output is the summary line. Set attributes `round`, `claims_checked`, `claims_unsupported`.
8. Return the report with `unsupported_before` equal to the count of non supported claims (the caller keeps the first value).

### 8.3 Challenger

Function `challenge(report, sources, ctx)`. Returns: the same report with `challenged` set True on every supported claim and `overturned` True on those the model overturns, and the list of overturned claims in `overturned_claims`.
1. Only supported claims are challenged. Batch at most 10 claims per `challenger_v1` call.
2. Inside `guardrail("adversarial_challenge")`: `passed = (overturned count equals 0)`. Set `claims_overturned`.
3. For each overturned claim add an event `claim_overturned` (agent `challenger`).

### 8.4 Mode A and mode B entry points

Function `verify_mode_a(tailored, sources, ctx)`. Returns: `(tailored_unchanged, report)`. One `audit` (round 1) then `challenge`, no changes to the text. `unsupported_final` equals `unsupported_before`. Used for run A (measurement only).

Function `verify_mode_b(tailored, sources, listing, ctx)`. Returns: `(tailored_final, report)`.
1. `report1 = audit(tailored, sources, ctx, 1)`. Remember `unsupported_before = report1.unsupported_before`.
2. For revision round `r` in 1 and 2: if the current report has no non supported claims, stop. Else group non supported claims by segment, call `tailor_revise` for those segments, replace them, then `report = audit(new_tailored, sources, ctx, r + 1)`.
3. After the loop, remove every segment that still contains a non supported claim: set the segment `status="removed"`, add a `RemovedClaim` (text and reason), add event `claim_removed`.
4. Run `challenge` on the final supported claims. If any overturned: ONE `tailor_revise` for those segments, one more `audit` limited to those segments, then remove any segment still overturned or unsupported (add `RemovedClaim` entries and events).
5. Final scan: `contains_sensitive` over all remaining text. If it matches, remove those segments (reason "sensitive detail") and add an event.
6. Set `unsupported_final` to the number of non supported claims in the last audit of remaining segments (must be 0). `rounds` equals the number of audits performed.

Tests: deterministic check cases (number mismatch, missing source id, number words), `verify_mode_b` with fake LLM responses that first mark a claim unsupported then supported, removal after two rounds, mode A leaves text unchanged.

## 9. Info and Draft Pack mode (restricted or unknown AI policy)

Triggered when `listing.ai_policy` is `restricted` or `unknown` (the Coordinator chooses `tailor_notes_only` instead of `tailor_full`).

Function `tailor_notes_only(...)`:
1. `cv_bullets`: choose the original CV and Vault facts to show: all facts referenced by selected edges, then the first facts in categories `education`, `work`, `projects`, up to 8 bullets total. Each bullet text equals the fact text EXACTLY (no LLM rewriting) with `source_ids=[fact id]`.
2. `cv_summary`: empty list. `essay`: empty list.
3. `outline`: one LLM call `outline_v1` returns `{"sections": [{"title": "...", "notes": "...", "fact_ids": ["P7"]}]}`; convert each section to one string `Title: notes (facts: P7, D3)`. These are NOTES, not essay sentences. Validate fact ids exist, drop unknown ids.
4. The Verifier runs `verify_mode_a` style audit on `cv_bullets` only (all should be supported). No Challenger.
5. The Applier produces a package with the CV draft, the outline file and the checklist, status `prepared`.
6. The Telegram message is `tpl_restricted_briefing`:
```
{name}: briefing ready. Deadline {deadline} ({days} days left).
Rule: AI written essays are not allowed or not confirmed, so I did not write yours. I prepared your CV draft, form answers, an essay outline with your own evidence, and a checklist.
Your strongest points: {edge_notes}
Open your pack: {frontend_url}/applications/{id}
Official page: {source_url}
```
7. A second message lists what the programme values (dossier facts with source URLs), gaps and next steps.

## 10. Packager (`agents/packager.py`)

Span helper: `agent_span("packager")`.

Function `build_package(app_id, listing, prefs, tailored, ctx)`. Returns: dict of relative paths.
1. Directory `backend/data/packages/{app_id}/`.
2. `cv.pdf` with `reportlab` (canvas, A4): the name (`prefs.full_name`), the email, the heading Summary with the supported `cv_summary` segment texts, the heading Highlights with the supported `cv_bullets` as lines. Wrap long lines manually at about 90 characters. Only segments with status `supported`.
3. `essay.txt`: supported essay segment texts joined with a space (empty for notes only mode, then the outline lines).
4. `checklist.txt`: the scholarship name, deadline, required documents with a box per item, the official link, the channel instruction (for example "Submit on the portal yourself"), and the AI policy line.
5. Store the dict in `package_json` and return it.

## 11. Applier (`agents/applier.py`)

Span helper: `agent_span("applier")`.

Function `apply(app_id, ctx)`. Returns: one of the strings `submitted`, `awaiting_user`, `prepared`, `unconfirmed`, `failed` (the Coordinator maps these to statuses).

1. Load application, listing, package, tailored text. Set `applicant fields` from prefs and tailored text: `full_name`, `email`, `summary` (summary segments joined), `essay` (essay segments joined).
2. If `listing.channel` is `package_only` OR the application is in notes only mode: return `prepared`.
3. Channel `email`: build subject `Application for {listing.name}: {full_name}` and a fixed body template ("Dear Selection Committee, please find my application attached. Kind regards, {full_name}."), attach `cv.pdf` and `essay.txt`, call `send_email(settings.demo_inbox_email, ...)`. On `SmtpError`: recovery decision (trigger `smtp_failure`, options `retry`, `prepare_package`, chosen `prepare_package`), return `prepared`. On success return `submitted` with confirmation code `EMAIL` plus the message timestamp digits and `confirmed` True.
4. Channels `portal_form` and `portal_captcha`:
   1. Create or reuse the portal draft: `POST {public_base_url}/portal/api/draft` with `idempotency_key=app_id`. Store `draft_id` in `handoff_json`.
   2. `check_blockers(apply_url)`: GET `/portal/apply/{listing_id}` and scan the HTML (inside a TOOL span `blocker_check`). Blockers: the element id `captcha_challenge`, an iframe whose src contains `recaptcha`, `hcaptcha` or `turnstile`, a password input, or an HTTP redirect to a path containing `login`. Returns a list of blocker kinds.
   3. If any blocker: build the handoff (`reason`, `portal_url` equal to the draft URL, `instructions`), record event `blocker_detected` and a recovery decision (trigger `captcha_wall`, options `retry`, `handoff`, chosen `handoff`, reason "a CAPTCHA can only be solved by the user, so the agent stops and hands off"), store `handoff_json`, return `awaiting_user`. Never retry against a blocker.
   4. No blocker: `POST /portal/api/submit` with the draft id. On HTTP 500: retry up to 3 times with the backoff. After 3 failures record a recovery decision (trigger `portal_500`, options `retry`, `email_fallback`, `prepare_package`, chosen `email_fallback` if `listing.email` is not empty else `prepare_package`) and run that fallback. On 403 `captcha_required`: treat as a blocker (go to step 3).
   5. On 200: confirm by `GET /portal/api/submissions/{draft_id}`. If `submitted` is true store the code, return `submitted`. If not confirmed after 3 polls (1 second apart) return `unconfirmed`.

Function `resume_after_handoff(app_id)`. Returns: `bool`.
1. Load the application. If status is not `awaiting_user` return False.
2. Set status `submitting` (event). GET `/portal/api/submissions/{draft_id}`.
3. If submitted: store the confirmation, set status `submitted`, event `submission_confirmed`, return True.
4. Else: set status back to `awaiting_user`, event `confirmation_not_seen`, return False.

Idempotency rules: before any submit, check the submissions endpoint for the draft, if already submitted just read the code (never submit twice).

## 12. Coordinator and scripts

### 12.1 `coordinator.py`

Functions:
1. `execute_run(run_id)`: decorated with `workflow_span("scholarpilot_run")`. Steps in `04_ARCHITECTURE.md` section 5. For each deep application call `run_step` for: `research`, `edges`, `tailor`, `verify`, `package`, `apply` in this order. After `edges`, send the `edges_used` message. After `verify` set status `verified`. After `package` set `ready`. After `apply` map the returned string to a status through `set_status` (`submitting` first when needed). Compute metrics at the end and call `db.finish_run`. Always call `notify.retry_unsent()` at the end.
2. `run_step(ctx, step_name, fn, fallback=None)`: as in `04_ARCHITECTURE.md` section 7.
3. `compute_metrics(run_id)`: as in `05_DATA_MODELS.md` section 8.
4. `start_run_thread(run_id)`: starts the thread with a top level try and except that records a `failed` run and an event with the error text, and never lets the thread die silently.
5. `resume_run(run_id)`: marks the run `running` and starts the thread. `execute_run` skips steps whose outputs already exist (idempotency).

Application ordering: matched applications sorted by `fit_score` descending then `deadline` ascending, the first `top_n` get deep processing, and mock listings are preferred in ties so the demo is deterministic.

Mode handling: mode `A` calls `verify_mode_a`, mode `B` calls `verify_mode_b`, mode `Z` skips research and edges (Tailor uses the core facts and Vault facts directly, no dossier) and calls `verify_mode_a`.

### 12.2 `scripts/run_pipeline.py` (positional arguments, no flags)

Usage: `python scripts/run_pipeline.py B 2 run_B,evidence`
1. Arguments: mode (A, B or Z), top_n (integer), tags (comma separated, optional).
2. Initialize neatlogs through `tracing.init_tracing(tags=tags)` BEFORE importing agents that create clients.
3. If no facts exist, load the synthetic persona (same code as `POST /api/profile/load_demo`).
4. Create the run, call `execute_run(run_id)` synchronously, print the metrics as JSON.
5. Write `docs/evidence/run_{mode}_{n}.json` where n counts existing files. Contents: run id, mode, tags, metrics, per application summary (status, unsupported before and final, removed, overturned), neatlogs trace url if available.
6. Call `neatlogs.flush()` and `neatlogs.shutdown()` at the end.

### 12.3 `scripts/quick_check.py`

1. Import every module in `app`.
2. Run `pytest` via `subprocess.run(["pytest"], cwd=backend_dir)`.
3. Use FastAPI `TestClient` to call `/api/health`.
4. Print `OK` or the first failure and exit with code 1 on failure.

### 12.4 `scripts/seed_persona.py`

Loads `data/synthetic/*` and calls the intake function. Prints counts.

### 12.5 `scripts/eval_runs.py`

Runs mode B three times with tags `eval` and `eval_v1`, prints a table (claims total, unsupported before, unsupported final, overturned, cost, latency, recovery decisions) and exits with code 1 if any final output has an unsupported claim.
