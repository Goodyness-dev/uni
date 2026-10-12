# Approved production v1 extension

Authorized by the user on 2026/10/12. The original `/api/*` demo contract remains intact.

## Identity

`POST /v1/auth/keys` retains `{email, scopes}` and its response. In production (and when an Authorization header is supplied in development), require `Authorization: Bearer <OIDC ID token>` issued to the configured client. Validate RS256 signature against a configured HTTPS JWKS endpoint, exact issuer, audience/authorized-party, expiration, issued-at, optional not-before, subject and `email_verified: true`. The request email must equal the verified claim. A token is consumed once through Redis; repeat exchanges fail. Existing inactive users cannot issue keys. Configuration: `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`. No provider credentials are generated or committed.

The browser obtains tokens through the selected identity provider's normal sign-in flow; ScholarPilot never bypasses its login wall. API keys live in browser session storage, not public environment variables or source files.

## Document review

`POST /v1/documents/{id}/verify` accepts `{confirmed: true, facts: [{category, text, source_excerpt}]}`. The caller must own the document. Every excerpt must match extracted source text and each fact must be a literal substring of its excerpt. Store document hash and source provenance in reserved profile metadata. A later file change invalidates evidence. `verified` means applicant-reviewed source alignment, not institutional authenticity certification. Arbitrary profile PUTs cannot create or overwrite reserved evidence metadata.

## Applications

Detail gains `verification` (report or null), `package` (download URLs or null), `trace_url` (actual configured trace link or null) and `handoff` (reason, portal URL, instructions or null). `GET /v1/applications/{id}/files/{kind}` serves only owned managed CV/essay/checklist files. Approval requires a nonempty reviewed draft; unknown portal acceptance cannot be retried through Resume.

Generated content is stored only when judge and independent challenger support each sentence against cited sources. At most two revision passes; remove remaining unsupported sentences. Empty output blocks submission. Restricted/unknown AI-policy scholarships receive original evidence notes for manual writing, not generated essay prose.

## Export and audit

`GET /v1/account/export?include_files=true` optionally includes owned local document bytes in base64, content type and digest, with a bounded aggregate size. Default export retains its record/reference shape. Remote storage references are explicitly reported as unavailable until a reviewed remote-storage adapter exists.

Workflow event UPDATE is denied. DELETE is denied except governed account erasure for the owning user. Audit retention is append-only during normal operation, with an explicit privacy erasure exception; it is not a promise of permanent retention of personal data.

## Frontend

`NEXT_PUBLIC_API_VERSION=v1` selects the typed v1 adapter behind `frontend/lib/api.ts`. The existing four screens remain; authentication controls use the existing top bar. Demo mode/mocks remain available. The adapter must map status, evidence, verification, packages and polling without inventing metrics, eligibility outcomes or source records. Unsupported operations are disabled with a clear state rather than fabricated responses.

## Sources for identity validation

[OpenID Connect ID token validation](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation) and [cryptography RSA signature verification](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/#verification).

## Batch and upload shapes

`POST /v1/documents/upload` accepts `{type, filename, content_base64}` and returns the existing document shape. PDF/UTF-8 text only; no multipart dependency. Limits: 10 MB/document, 50 MB/owner, 40 PDF pages, up to 100 candidate excerpts. Pending excerpts in reserved profile metadata require an explicit applicant review action. Sensitive excerpts are excluded from frontend display and drafting; ordinary PUT cannot forge reviewed records.

`POST /v1/runs` accepts `{mode: "B", top_n: 1..10, live_research: false, tags: []}`. Live research may only be requested when enabled by the operator. Persist actual matched application IDs and process the top N sequentially through a database Job. `GET /v1/runs/latest`, `GET /v1/runs/{id}`, and `GET /v1/runs/{id}/events?after=0` enforce owner access. Run metrics remain null when unavailable. Event cursor is an ordinal snapshot ordered by creation time/UUID, not a durable sequence number; clients should reload the timeline after reconnecting.

Application detail also includes its catalog `listing`. Download URLs are API-relative and require the same ownership/authentication headers; browser downloads fetch a Blob through api.ts. The adapter uses null hard-rule breakdowns where v1 does not supply per-rule evidence and hides that breakdown, rather than inventing successful checks. The demo boolean representation remains accepted.

Approval without an essay/statement is rejected. Automatic submission additionally requires an allowed/disclose AI policy and an owned local demo listing. Resume requires an owned demo draft with authoritative submission confirmation; an absent confirmation returns 409, an unavailable readback returns 503, and neither queues another click. Already-reconciled applications reject repeat Resume.

## Local verification procedure

1. Run migration head on an isolated database; start the root API on a separate origin such as localhost:8001 and its worker with a local Redis broker. Keep the original demo portal on localhost:8000.
2. Configure the identity issuer, audience and HTTPS JWKS URL. Obtain a fresh ID token through that provider's normal sign-in flow and exchange it using the top bar. No token or key belongs in committed environment files.
3. Select v1 through frontend environment configuration, restarting Next after build-time configuration changes. Process fictional source documents, review their excerpts, start a mode-B batch, open its package and approve an allowed demo application.
4. For a blocker, complete the security step and submission yourself in the demo portal. Resume must only read its confirmation and must not create a second submit job.
5. Test owner isolation, read-only keys, altered documents, export with files and package/document erasure. Review broker/schema readiness and actual worker shutdown before considering deployment.

Provider sign-in redirects, live sponsor links, remote object erasure and regulatory certification are not implied by this extension.

## Verified local frontend connection

An empty `NEXT_PUBLIC_API_BASE` uses same-origin requests. With `NEXT_PUBLIC_API_VERSION=v1`, Next rewrites `/v1/*`, `/health` and `/ready` to private `API_BACKEND_URL` (localhost:8001 by default). API keys remain request headers, including file downloads; no key is placed in a URL.

The top bar accepts an existing API key or provider ID token. Only when backend health reports development demo mode, it also offers a new fictional development identity using the existing email bootstrap endpoint. Production still requires verified identity-token issuance. Source review survives reload, and Run remains disabled until source facts have been reviewed.

The local UI-to-worker integration and confirmation readback were exercised with real PostgreSQL/Redis and Chromium. See `PRODUCTION_REPAIR_PLAN.md` and the recorded fictional integration evidence.

## User-authorized Autopilot change (2026/10/12)

No new public fields or endpoints. Existing GET/PUT `/v1/settings` mode (`autopilot`/`review`) now appears as the Profile Autopilot checkbox. Changing mode requires the shared broker so workers receive the pause marker. New-user default remains `autopilot`. Existing application `mode_used` stays a snapshot: a review application is not retroactively approved by enabling Autopilot. Allowed owned-portal agent applications in Autopilot queue submission after source checks; Review or external portals pause.
