import { createV1, useV1 } from "./v1";
import type {
  Application,
  ApplicationSummary,
  AppEvent,
  AppStatus,
  Fact,
  FailureFlags,
  FailureFlagsResponse,
  Gap,
  HealthResponse,
  IntakeRequest,
  IntakeResponse,
  Match,
  Preferences,
  Run,
  RunStatus,
} from "./types";

// Static mock data imports
import mockHealth from "../mocks/health.json";
import mockFacts from "../mocks/facts.json";
import mockIntake from "../mocks/intake.json";
import mockRunLatest from "../mocks/run_latest.json";
import mockRunRunning from "../mocks/run_running.json";
import mockEventsPage1 from "../mocks/events_page1.json";
import mockEventsPage2 from "../mocks/events_page2.json";
import mockMatches from "../mocks/matches.json";
import mockApplications from "../mocks/applications.json";
import mockApplicationAwaiting from "../mocks/application_awaiting.json";
import mockApplicationVerified from "../mocks/application_verified.json";
import mockApplicationSubmitted from "../mocks/application_submitted.json";
import mockApplicationFailed from "../mocks/application_failed.json";
import mockApplicationEarly from "../mocks/application_early.json";
import mockGaps from "../mocks/gaps.json";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const USE_MOCKS = !useV1 && process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

function delay(ms: number = 300): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...(useV1 && typeof window !== "undefined" && sessionStorage.getItem("scholarpilot_api_key") ? { "X-API-Key": sessionStorage.getItem("scholarpilot_api_key")! } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let errorCode = "server_error";
    let errorMessage = `HTTP error ${response.status}`;
    try {
      const errBody = await response.json();
      if (errBody.error) errorCode = errBody.error;
      if (errBody.message) errorMessage = errBody.message;
      if (typeof errBody.detail === "string") errorMessage = errBody.detail;
      else if (errBody.detail?.message) errorMessage = errBody.detail.message;
    } catch {
      // Fallback to response statusText if JSON parsing fails
      if (response.statusText) errorMessage = response.statusText;
    }
    throw new ApiError(response.status, errorCode, errorMessage);
  }

  return response.json() as Promise<T>;
}

const v1 = createV1(request);

export async function getHealth(): Promise<HealthResponse> {
  if (useV1) { return request<HealthResponse>("/health"); }
  if (USE_MOCKS) {
    await delay();
    return mockHealth as HealthResponse;
  }
  return request<HealthResponse>("/api/health");
}

export async function loadDemo(): Promise<IntakeResponse> {
  if (useV1) { throw new ApiError(400, "unsupported", "Demo personas are available through the demo API."); }
  if (USE_MOCKS) {
    await delay();
    return mockIntake as IntakeResponse;
  }
  return request<IntakeResponse>("/api/profile/load_demo", { method: "POST" });
}

export async function intake(req: IntakeRequest): Promise<IntakeResponse> {
  if (useV1) { return v1.intake(req); }
  if (USE_MOCKS) {
    await delay();
    return mockIntake as IntakeResponse;
  }
  return request<IntakeResponse>("/api/profile/intake", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getFacts(): Promise<{ facts: Fact[]; preferences: Preferences | null }> {
  if (useV1) { return v1.getFacts(); }
  if (USE_MOCKS) {
    await delay();
    return mockFacts as { facts: Fact[]; preferences: Preferences | null };
  }
  return request<{ facts: Fact[]; preferences: Preferences | null }>("/api/profile/facts");
}

export async function patchFact(id: string, text: string): Promise<Fact> {
  if (useV1) { throw new ApiError(400, "source_review", "Upload corrected source evidence and review it."); }
  if (USE_MOCKS) {
    await delay();
    const existing = (mockFacts.facts as Fact[]).find((f) => f.id === id);
    return {
      id,
      source: existing?.source || "vault",
      category: existing?.category || "general",
      text,
      sensitive: existing?.sensitive || false,
    };
  }
  return request<Fact>(`/api/profile/facts/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ text }),
  });
}

export async function addFact(category: string, text: string): Promise<Fact> {
  if (useV1) { throw new ApiError(400, "source_review", "Add original evidence through the profile intake."); }
  if (USE_MOCKS) {
    await delay();
    return {
      id: `P${Math.floor(Math.random() * 100) + 20}`,
      source: "vault",
      category,
      text,
      sensitive: false,
    };
  }
  return request<Fact>("/api/profile/facts", {
    method: "POST",
    body: JSON.stringify({ category, text }),
  });
}

export async function startRun(
  mode: "A" | "B" | "Z" = "B",
  topN: number = 2,
  liveResearch: boolean = false
): Promise<{ run_id: string; status: RunStatus }> {
  if (useV1) { if (mode !== "B") throw new ApiError(400, "unsupported", "Production runs support mode B."); return request<{ run_id: string; status: RunStatus }>("/v1/runs", { method: "POST", body: JSON.stringify({ mode, top_n: topN, live_research: liveResearch }) }); }
  if (USE_MOCKS) {
    await delay();
    return { run_id: "run_20261011_001", status: "running" };
  }
  return request<{ run_id: string; status: RunStatus }>("/api/runs", {
    method: "POST",
    body: JSON.stringify({ mode, top_n: topN, live_research: liveResearch }),
  });
}

export async function getLatestRun(): Promise<Run> {
  if (useV1) { return request<Run>("/v1/runs/latest"); }
  if (USE_MOCKS) {
    await delay();
    return mockRunLatest as Run;
  }
  return request<Run>("/api/runs/latest");
}

export async function getRun(id: string): Promise<Run> {
  if (useV1) { return request<Run>(`/v1/runs/${encodeURIComponent(id)}`); }
  if (USE_MOCKS) {
    await delay();
    if (id === "run_running") return mockRunRunning as Run;
    return mockRunLatest as Run;
  }
  return request<Run>(`/api/runs/${id}`);
}

export async function getRunEvents(
  id: string,
  after: number = 0
): Promise<{ events: AppEvent[]; last_event_no: number }> {
  if (useV1) { return request<{ events: AppEvent[]; last_event_no: number }>(`/v1/runs/${encodeURIComponent(id)}/events?after=${after}`); }
  if (USE_MOCKS) {
    await delay();
    if (after >= 5) {
      return mockEventsPage2 as { events: AppEvent[]; last_event_no: number };
    }
    return mockEventsPage1 as { events: AppEvent[]; last_event_no: number };
  }
  return request<{ events: AppEvent[]; last_event_no: number }>(`/api/runs/${id}/events?after=${after}`);
}

export async function resumeRun(id: string): Promise<{ run_id: string; status: RunStatus }> {
  if (useV1) { throw new ApiError(400, "unsupported", "Resume an individual application after completing its handoff."); }
  if (USE_MOCKS) {
    await delay();
    return { run_id: id, status: "running" };
  }
  return request<{ run_id: string; status: RunStatus }>(`/api/runs/${id}/resume`, {
    method: "POST",
  });
}

export async function getMatches(runId?: string): Promise<{ matches: Match[] }> {
  if (useV1) { return v1.getMatches(runId); }
  if (USE_MOCKS) {
    await delay();
    return mockMatches as { matches: Match[] };
  }
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<{ matches: Match[] }>(`/api/matches${query}`);
}

export async function getApplications(
  runId?: string
): Promise<{ applications: ApplicationSummary[] }> {
  if (useV1) { return v1.getApplications(runId); }
  if (USE_MOCKS) {
    await delay();
    return mockApplications as { applications: ApplicationSummary[] };
  }
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<{ applications: ApplicationSummary[] }>(`/api/applications${query}`);
}

export async function getApplication(id: string): Promise<Application> {
  if (useV1) { return v1.getApplication(id); }
  if (USE_MOCKS) {
    await delay();
    if (id === "app_2" || id.includes("awaiting")) {
      return mockApplicationAwaiting as Application;
    }
    if (id === "app_5" || id.includes("failed")) {
      return mockApplicationFailed as Application;
    }
    if (id === "app_4" || id.includes("early")) {
      return mockApplicationEarly as Application;
    }
    if (id.includes("submitted")) {
      return mockApplicationSubmitted as Application;
    }
    return mockApplicationVerified as Application;
  }
  return request<Application>(`/api/applications/${id}`);
}

export async function handoffDone(id: string): Promise<{ status: AppStatus }> {
  if (useV1) { await request(`/v1/applications/${encodeURIComponent(id)}/resume`, { method: "POST" }); return { status: "submitted" }; }
  if (USE_MOCKS) {
    await delay();
    return { status: "submitting" };
  }
  return request<{ status: AppStatus }>(`/api/applications/${id}/handoff/done`, {
    method: "POST",
  });
}

export async function getGaps(runId?: string): Promise<{ gaps: Gap[] }> {
  if (useV1) { throw new ApiError(400, "unsupported", "Gap analysis is not available in v1."); }
  if (USE_MOCKS) {
    await delay();
    return mockGaps as { gaps: Gap[] };
  }
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<{ gaps: Gap[] }>(`/api/gaps${query}`);
}

export async function answerGap(id: string, text: string): Promise<{ fact: Fact }> {
  if (useV1) { throw new ApiError(400, "unsupported", "Upload source evidence through profile intake."); }
  if (USE_MOCKS) {
    await delay();
    return {
      fact: {
        id: `P${Math.floor(Math.random() * 50) + 15}`,
        source: "vault",
        category: "public_policy",
        text,
        sensitive: false,
      },
    };
  }
  return request<{ fact: Fact }>(`/api/gaps/${id}/answer`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function getFlags(): Promise<FailureFlagsResponse> {
  if (useV1) { throw new ApiError(400, "unsupported", "Demo failure controls are disabled in v1."); }
  if (USE_MOCKS) {
    await delay();
    return {
      flags: {
        llm_429: false,
        bad_json: false,
        portal_500: false,
        captcha_wall: false,
        research_down: false,
        smtp_fail: false,
        injection_page: false,
      },
    };
  }
  return request<FailureFlagsResponse>("/api/failure_flags");
}

export async function setFlags(
  flags: Partial<FailureFlags>,
  counts?: Record<string, number>
): Promise<FailureFlagsResponse> {
  if (useV1) { throw new ApiError(400, "unsupported", "Demo failure controls are disabled in v1."); }
  if (USE_MOCKS) {
    await delay();
    return {
      flags: {
        llm_429: false,
        bad_json: false,
        portal_500: false,
        captcha_wall: false,
        research_down: false,
        smtp_fail: false,
        injection_page: false,
        ...flags,
      },
    };
  }
  return request<FailureFlagsResponse>("/api/failure_flags", {
    method: "POST",
    body: JSON.stringify({ flags, counts }),
  });
}

export function fileUrl(appId: string, kind: "cv" | "essay" | "checklist"): string {
  return `${API_BASE}/${useV1 ? "v1" : "api"}/applications/${encodeURIComponent(appId)}/files/${kind}`;
}

export const api = {
  getHealth,
  loadDemo,
  intake,
  getFacts,
  patchFact,
  addFact,
  startRun,
  getLatestRun,
  getRun,
  getRunEvents,
  resumeRun,
  getMatches,
  getApplications,
  getApplication,
  handoffDone,
  getGaps,
  answerGap,
  getFlags,
  setFlags,
  fileUrl,
};


export async function exchangeIdentity(email: string, token: string): Promise<void> {
  const result = await request<{ api_key: string }>("/v1/auth/keys", { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ email }) });
  sessionStorage.setItem("scholarpilot_api_key", result.api_key);
}
export async function reviewPendingEvidence(): Promise<void> { await v1.reviewPendingEvidence(); }
export async function connectDevelopmentIdentity(email: string): Promise<void> {
  const health = await request<HealthResponse>("/health");
  if (!health.demo_mode) throw new ApiError(403, "identity_required", "A verified identity token is required.");
  const result = await request<{ api_key: string }>("/v1/auth/keys", { method: "POST", body: JSON.stringify({ email }) });
  sessionStorage.setItem("scholarpilot_api_key", result.api_key);
}
export async function connectApiKey(key: string): Promise<void> {
  await request("/v1/profile", { headers: { "X-API-Key": key } });
  sessionStorage.setItem("scholarpilot_api_key", key);
}
export async function approveApplication(id: string): Promise<void> { await request(`/v1/applications/${encodeURIComponent(id)}/approve`, { method: "POST" }); }
export async function downloadFile(url: string, name: string): Promise<void> {
  const base = API_BASE || window.location.origin;
  const parsed = new URL(url, base);
  if (parsed.origin !== new URL(base).origin || !parsed.pathname.startsWith("/v1/applications/")) throw new ApiError(400, "invalid_file", "File URL is outside the application API.");
  const key = sessionStorage.getItem("scholarpilot_api_key");
  const response = await fetch(parsed, { headers: key ? { "X-API-Key": key } : {} });
  if (!response.ok) throw new ApiError(response.status, "download_failed", "Package download failed.");
  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a"); link.href = objectUrl; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

export async function getAutopilot(): Promise<boolean> {
  const value = await request<{ mode: "autopilot" | "review" }>("/v1/settings");
  return value.mode === "autopilot";
}
export async function setAutopilot(enabled: boolean): Promise<void> {
  await request("/v1/settings", { method: "PUT", body: JSON.stringify({ mode: enabled ? "autopilot" : "review" }) });
}

export async function continueApplication(id: string): Promise<void> { await request(`/v1/applications/${encodeURIComponent(id)}/continue`, { method: "POST" }); }
export async function withdrawApplication(id: string): Promise<void> { await request(`/v1/applications/${encodeURIComponent(id)}/withdraw`, { method: "POST" }); }

export interface NotificationSettings { notification_email: string | null; telegram_chat_id: string | null; email_notifications: boolean; telegram_notifications: boolean; email_ready: boolean; telegram_ready: boolean }
export async function getNotificationSettings(): Promise<NotificationSettings> { return request("/v1/settings"); }
export async function saveNotificationSettings(value: Pick<NotificationSettings, "notification_email" | "telegram_chat_id" | "email_notifications" | "telegram_notifications">): Promise<void> { await request("/v1/settings", { method: "PUT", body: JSON.stringify(value) }); }
export async function testNotification(channel: "email" | "telegram"): Promise<{job_id: string}> { return request("/v1/settings/test-notification", { method: "POST", body: JSON.stringify({ channel }) }); }
export async function getNotificationTest(id: string): Promise<{status: string; provider_accepted: boolean; reason: string}> { return request(`/v1/settings/test-notification/${encodeURIComponent(id)}`); }

export async function beginVerifiedSignIn(): Promise<void> {
  const value = await request<{ url: string; state: string }>("/v1/auth/authorize");
  sessionStorage.setItem("scholarpilot_oidc_state", value.state); window.location.assign(value.url);
}
export async function finishVerifiedSignIn(code: string, state: string): Promise<void> {
  if (state !== sessionStorage.getItem("scholarpilot_oidc_state")) throw new ApiError(401, "invalid_state", "Sign-in session does not match this browser.");
  sessionStorage.removeItem("scholarpilot_oidc_state");
  const value = await request<{ api_key: string }>("/v1/auth/callback", { method: "POST", body: JSON.stringify({ code, state }) });
  sessionStorage.setItem("scholarpilot_api_key", value.api_key);
}
