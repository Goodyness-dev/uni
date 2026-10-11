import { AppStatus, Channel, RunStatus } from "./types";

export type StatusTone = "neutral" | "info" | "success" | "success-outline" | "warning" | "danger";

export interface StatusMeta {
  label: string;
  tone: StatusTone;
  hasDot?: boolean;
  pulseDot?: boolean;
  hasCheck?: boolean;
}

const STATUS_MAP: Record<AppStatus, StatusMeta> = {
  found: { label: "Found", tone: "neutral" },
  matched: { label: "Matched", tone: "info" },
  skipped: { label: "Not eligible", tone: "neutral" },
  researched: { label: "Researched", tone: "info" },
  edges_selected: { label: "Evidence chosen", tone: "info" },
  tailored: { label: "Written", tone: "info" },
  verified: { label: "Verified", tone: "success" },
  ready: { label: "Ready", tone: "success" },
  submitting: { label: "Submitting", tone: "info", hasDot: true },
  awaiting_user: { label: "Needs you", tone: "warning", pulseDot: true },
  submitted: { label: "Submitted", tone: "success", hasCheck: true },
  prepared: { label: "Package ready", tone: "success-outline" },
  unconfirmed: { label: "Unconfirmed", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
};

export function statusMeta(status: AppStatus): StatusMeta {
  return STATUS_MAP[status] ?? { label: status, tone: "neutral" };
}

export function channelLabel(channel: Channel): string {
  switch (channel) {
    case "email":
      return "Email application";
    case "portal_form":
      return "Online form";
    case "portal_captcha":
      return "Online form with CAPTCHA";
    case "package_only":
      return "Prepare only";
    default:
      return channel;
  }
}

export function isFinalStatus(status: AppStatus): boolean {
  return status === "submitted" || status === "prepared" || status === "failed" || status === "skipped";
}

export function isFinalRun(status: RunStatus): boolean {
  return status === "completed" || status === "failed" || status === "interrupted";
}
