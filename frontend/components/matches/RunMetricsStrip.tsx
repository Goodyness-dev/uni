import { ExternalLink } from "lucide-react";
import { RunMetrics, Match } from "@/lib/types";

interface RunMetricsStripProps {
  metrics: RunMetrics | null;
  traceUrl: string | null;
  matches: Match[];
}

export function RunMetricsStrip({
  metrics,
  traceUrl,
  matches,
}: RunMetricsStripProps) {
  const readyOrSubmittedCount = matches.filter(
    (m) =>
      m.status === "ready" ||
      m.status === "submitted" ||
      m.status === "prepared"
  ).length;

  const needsYouCount = matches.filter(
    (m) => m.status === "awaiting_user"
  ).length;

  const failedCount = matches.filter(
    (m) => m.status === "failed"
  ).length;

  const formatSeconds = (sec: number): string => {
    if (!sec || isNaN(sec)) return "0s";
    const minutes = Math.floor(sec / 60);
    const remainingSec = Math.round(sec % 60);
    if (minutes > 0) {
      return `${minutes}m ${remainingSec}s`;
    }
    return `${remainingSec}s`;
  };

  return (
    <section className="w-full bg-[#121318] rounded-xl border border-[#262932] p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      {/* Status Counters */}
      <div className="flex flex-wrap items-center gap-2.5 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#49e095]" />
          <span className="text-[#ECEDF0] font-medium">
            {readyOrSubmittedCount} submitted or ready
          </span>
        </div>
        <span className="text-[#626877]">•</span>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#ffb957]" />
          <span className="text-[#ffb957] font-medium">
            {needsYouCount} needs you
          </span>
        </div>
        <span className="text-[#626877]">•</span>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#F87171]" />
          <span className="text-[#9AA0AE]">{failedCount} failed</span>
        </div>
      </div>

      {/* Metrics Tiles & View Trace */}
      <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
        {metrics && (
          <>
            <div className="px-2.5 py-1 rounded bg-[#181A20] border border-[#262932]">
              <span className="text-[#626877]">Tokens:</span>{" "}
              <span className="text-[#ECEDF0] font-medium">
                {metrics.tokens_total.toLocaleString()}
              </span>
            </div>

            <div className="px-2.5 py-1 rounded bg-[#181A20] border border-[#262932]">
              <span className="text-[#626877]">Cost:</span>{" "}
              <span className="text-[#ECEDF0] font-medium">
                ${metrics.cost_usd.toFixed(2)}
              </span>
            </div>

            <div className="px-2.5 py-1 rounded bg-[#181A20] border border-[#262932]">
              <span className="text-[#626877]">Time:</span>{" "}
              <span className="text-[#ECEDF0] font-medium">
                {formatSeconds(metrics.latency_seconds)}
              </span>
            </div>

            <div className="px-2.5 py-1 rounded bg-[#181A20] border border-[#262932]">
              <span className="text-[#626877]">Claims checked:</span>{" "}
              <span className="text-[#49e095] font-medium">
                {metrics.claims_total}
              </span>
            </div>

            {metrics.claims_removed > 0 && (
              <div className="px-2.5 py-1 rounded bg-[#181A20] border border-[#F87171]/30">
                <span className="text-[#626877]">Removed:</span>{" "}
                <span className="text-[#F87171] font-medium">
                  {metrics.claims_removed}
                </span>
              </div>
            )}
          </>
        )}

        {/* View Trace Button */}
        {traceUrl && (
          <div className="flex items-center gap-2 ml-auto sm:ml-0">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#181A20] border border-[#5b8cff]/30 text-[11px] text-[#b2c5ff]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#5b8cff] animate-pulse" />
              <span>Traced with neatlogs</span>
            </span>
            <a
              href={traceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2.5 py-1 rounded bg-[#181A20] hover:bg-[#262932] border border-[#5b8cff]/40 text-[#b2c5ff] hover:text-white flex items-center gap-1.5 transition-colors font-medium text-xs"
            >
              <span>View trace</span>
              <ExternalLink className="w-3 h-3 text-[#5b8cff]" />
            </a>
          </div>
        )}
      </div>
    </section>
  );
}
