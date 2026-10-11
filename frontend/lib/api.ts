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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

function delay(ms: number = 300): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = {
    "Content-Type": "application/json",
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
    } catch {
      // Fallback to response statusText if JSON parsing fails
      if (response.statusText) errorMessage = response.statusText;
    }
    throw new ApiError(response.status, errorCode, errorMessage);
  }

  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  if (USE_MOCKS) {
    await delay();
    return mockHealth as HealthResponse;
  }
  return request<HealthResponse>("/api/health");
}

export async function loadDemo(): Promise<IntakeResponse> {
  if (USE_MOCKS) {
    await delay();
    return mockIntake as IntakeResponse;
  }
  return request<IntakeResponse>("/api/profile/load_demo", { method: "POST" });
}

export async function intake(req: IntakeRequest): Promise<IntakeResponse> {
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
  if (USE_MOCKS) {
    await delay();
    return mockFacts as { facts: Fact[]; preferences: Preferences | null };
  }
  return request<{ facts: Fact[]; preferences: Preferences | null }>("/api/profile/facts");
}

export async function patchFact(id: string, text: string): Promise<Fact> {
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
  if (USE_MOCKS) {
    await delay();
    return mockRunLatest as Run;
  }
  return request<Run>("/api/runs/latest");
}

export async function getRun(id: string): Promise<Run> {
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
  if (USE_MOCKS) {
    await delay();
    return { run_id: id, status: "running" };
  }
  return request<{ run_id: string; status: RunStatus }>(`/api/runs/${id}/resume`, {
    method: "POST",
  });
}

export async function getMatches(runId?: string): Promise<{ matches: Match[] }> {
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
  if (USE_MOCKS) {
    await delay();
    return mockApplications as { applications: ApplicationSummary[] };
  }
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<{ applications: ApplicationSummary[] }>(`/api/applications${query}`);
}

export async function getApplication(id: string): Promise<Application> {
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
  if (USE_MOCKS) {
    await delay();
    return { status: "submitting" };
  }
  return request<{ status: AppStatus }>(`/api/applications/${id}/handoff/done`, {
    method: "POST",
  });
}

export async function getGaps(runId?: string): Promise<{ gaps: Gap[] }> {
  if (USE_MOCKS) {
    await delay();
    return mockGaps as { gaps: Gap[] };
  }
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return request<{ gaps: Gap[] }>(`/api/gaps${query}`);
}

export async function answerGap(id: string, text: string): Promise<{ fact: Fact }> {
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
  return `${API_BASE}/api/applications/${encodeURIComponent(appId)}/files/${kind}`;
}
