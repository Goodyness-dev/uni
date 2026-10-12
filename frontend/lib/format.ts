/**
 * Format helpers for ScholarPilot
 * Dates arrive as strings: "YYYY/MM/DD" or "YYYY/MM/DD HH:MM:SS" in UTC.
 */

export function parseDate(s: string): Date {
  if (!s) return new Date();
  // Handle "YYYY/MM/DD HH:MM:SS" or "YYYY/MM/DD"
  const clean = s.trim().replace(/\//g, "-");
  if (/^\d{4}-\d{2}-\d{2}T/.test(clean)) return new Date(clean);
  if (clean.includes(" ")) {
    const [datePart, timePart] = clean.split(" ");
    return new Date(`${datePart}T${timePart}Z`);
  }
  return new Date(`${clean}T00:00:00Z`);
}

/**
 * Returns whole days from today until deadline.
 * Can be 0 or negative if deadline passed.
 */
export function daysLeft(deadline: string): number {
  if (!deadline) return 0;
  const target = parseDate(deadline);
  const now = new Date();
  const utcNow = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const utcTarget = Date.UTC(target.getUTCFullYear(), target.getUTCMonth(), target.getUTCDate());
  const diffMs = utcTarget - utcNow;
  return Math.round(diffMs / (1000 * 60 * 60 * 24));
}

/**
 * Relative time ago string (e.g., "just now", "2m ago", "1h ago", "3d ago")
 */
export function timeAgo(s: string): string {
  if (!s) return "";
  const date = parseDate(s);
  const now = new Date();
  const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

/**
 * Formats time portion as HH:MM:SS (UTC or from string)
 */
export function formatTime(s: string): string {
  if (!s) return "";
  if (s.includes(" ")) {
    const parts = s.trim().split(" ");
    return parts[1] || "";
  }
  const date = parseDate(s);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`;
}

/**
 * Formats a number as a percentage string (e.g. 0.85 -> "85%", 85 -> "85%")
 */
export function pct(n: number): string {
  if (n === null || n === undefined || isNaN(n)) return "0%";
  const val = n <= 1 && n >= 0 ? Math.round(n * 100) : Math.round(n);
  return `${val}%`;
}
