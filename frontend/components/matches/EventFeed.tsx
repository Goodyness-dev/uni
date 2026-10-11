"use client";

import { useEffect, useRef, useState, UIEvent } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Compass,
  FileCheck2,
  GitMerge,
  Search,
  Sparkles,
  Send,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { AppEvent } from "@/lib/types";
import { formatTime } from "@/lib/format";

interface EventFeedProps {
  events: AppEvent[];
  isRunning: boolean;
}

export function EventFeed({ events, isRunning }: EventFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [userHasScrolled, setUserHasScrolled] = useState(false);
  const prevEventsCountRef = useRef(events.length);

  // Auto-scroll handler: since newest is at top, if user hasn't scrolled down, keep at scrollTop = 0
  useEffect(() => {
    if (events.length > prevEventsCountRef.current) {
      if (!userHasScrolled && containerRef.current) {
        containerRef.current.scrollTop = 0;
      }
    }
    prevEventsCountRef.current = events.length;
  }, [events.length, userHasScrolled]);

  const handleScroll = (e: UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    if (target.scrollTop > 25) {
      setUserHasScrolled(true);
    } else {
      setUserHasScrolled(false);
    }
  };

  // Sort newest first
  const sortedEvents = [...events].sort((a, b) => b.event_no - a.event_no);

  const getAgentMeta = (agent: string) => {
    switch (agent.toLowerCase()) {
      case "coordinator":
        return {
          label: "Coordinator",
          icon: Bot,
          badgeColor: "bg-[#7AA2FF]/10 text-[#7AA2FF] border-[#7AA2FF]/20",
        };
      case "scout":
        return {
          label: "Scout",
          icon: Compass,
          badgeColor: "bg-[#49e095]/10 text-[#49e095] border-[#49e095]/20",
        };
      case "matcher":
        return {
          label: "Matcher",
          icon: Sparkles,
          badgeColor: "bg-[#F5A25D]/10 text-[#F5A25D] border-[#F5A25D]/20",
        };
      case "researcher":
        return {
          label: "Researcher",
          icon: Search,
          badgeColor: "bg-[#5FD3A0]/10 text-[#5FD3A0] border-[#5FD3A0]/20",
        };
      case "edge_finder":
        return {
          label: "Edge Finder",
          icon: GitMerge,
          badgeColor: "bg-[#b2c5ff]/10 text-[#b2c5ff] border-[#b2c5ff]/20",
        };
      case "tailor":
        return {
          label: "Tailor",
          icon: FileCheck2,
          badgeColor: "bg-[#5b8cff]/10 text-[#5b8cff] border-[#5b8cff]/20",
        };
      case "verifier":
        return {
          label: "Verifier",
          icon: ShieldCheck,
          badgeColor: "bg-[#B794F6]/10 text-[#B794F6] border-[#B794F6]/20",
        };
      case "applier":
        return {
          label: "Applier",
          icon: Send,
          badgeColor: "bg-[#49e095]/10 text-[#49e095] border-[#49e095]/20",
        };
      default:
        return {
          label: agent,
          icon: Activity,
          badgeColor: "bg-[#181A20] text-[#9AA0AE] border-[#262932]",
        };
    }
  };

  return (
    <aside className="bg-[#121318] rounded-xl border border-[#262932] p-4 sticky top-20 flex flex-col max-h-[calc(100vh-6rem)]">
      {/* Feed Header */}
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#262932]">
        <div className="flex items-center gap-2">
          {isRunning ? (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#49e095] opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#49e095]" />
            </span>
          ) : (
            <span className="w-2 h-2 rounded-full bg-[#626877]" />
          )}
          <h3 className="text-sm font-semibold text-[#ECEDF0]">Agent activity</h3>
        </div>
        <div className="flex items-center gap-2">
          {userHasScrolled && (
            <button
              type="button"
              onClick={() => {
                if (containerRef.current) {
                  containerRef.current.scrollTop = 0;
                  setUserHasScrolled(false);
                }
              }}
              className="text-[10px] font-mono text-[#5b8cff] hover:underline"
            >
              Scroll to newest
            </button>
          )}
          <span className="text-[11px] font-mono text-[#626877] tracking-wider uppercase">
            {isRunning ? "LIVE FEED" : "COMPLETED"}
          </span>
        </div>
      </div>

      {/* Events Container */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="overflow-y-auto space-y-2.5 pr-1 flex-1 custom-scrollbar min-h-[300px]"
      >
        {sortedEvents.length === 0 ? (
          <div className="py-12 text-center text-xs text-[#626877] font-mono">
            Waiting for pipeline events...
          </div>
        ) : (
          sortedEvents.map((event) => {
            const meta = getAgentMeta(event.agent);
            const AgentIcon = meta.icon;
            const isRecovery = event.type === "recovery_decision";
            const isRemoved = event.type === "claim_removed";
            const isSubmission = event.type === "submission_confirmed";
            const isWarning =
              event.type.includes("retry") ||
              event.type.includes("warning") ||
              event.type.includes("fallback");

            // Recovery Decision styling
            if (isRecovery) {
              const trigger = (event.data?.trigger as string) || "anomaly";
              const chosen = (event.data?.chosen as string) || "recovery";
              const reason = (event.data?.reason as string) || "";

              return (
                <div
                  key={event.event_no}
                  className="p-3 rounded-lg bg-[rgba(245,165,36,0.06)] border border-[#ffb957]/30 flex flex-col gap-1.5"
                >
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="px-1.5 py-0.5 rounded bg-[rgba(245,165,36,0.15)] text-[#ffb957] font-medium flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Recovery Decision
                    </span>
                    <span className="text-[#626877]">{formatTime(event.at)}</span>
                  </div>
                  <p className="text-xs text-[#ECEDF0] leading-snug">{event.message}</p>
                  <div className="mt-1 pt-1.5 border-t border-[#ffb957]/20 text-[11px] font-mono space-y-0.5 text-[#9AA0AE]">
                    <div className="flex items-center gap-1">
                      <span className="text-[#626877]">Trigger:</span>
                      <span className="text-[#ffb957]">{trigger}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-[#626877]">Decision:</span>
                      <span className="text-[#ECEDF0] font-medium">{chosen}</span>
                    </div>
                    {reason && (
                      <p className="text-[10px] text-[#9AA0AE] italic mt-0.5">
                        &quot;{reason}&quot;
                      </p>
                    )}
                  </div>
                </div>
              );
            }

            // Claim Removed styling
            if (isRemoved) {
              return (
                <div
                  key={event.event_no}
                  className="p-3 rounded-lg bg-[rgba(248,113,113,0.06)] border border-[#F87171]/30 flex flex-col gap-1"
                >
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="px-1.5 py-0.5 rounded bg-[rgba(248,113,113,0.15)] text-[#F87171] font-medium flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" />
                      Claim Removed
                    </span>
                    <span className="text-[#626877]">{formatTime(event.at)}</span>
                  </div>
                  <p className="text-xs text-[#ECEDF0] leading-snug">
                    {event.message}
                  </p>
                  {event.data?.reason ? (
                    <p className="text-[11px] font-mono text-[#F87171]/90 mt-1">
                      Reason: {String(event.data.reason)}
                    </p>
                  ) : null}
                </div>
              );
            }

            // Submission Confirmed styling
            if (isSubmission) {
              return (
                <div
                  key={event.event_no}
                  className="p-3 rounded-lg bg-[rgba(61,214,140,0.06)] border border-[#49e095]/30 flex flex-col gap-1"
                >
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="px-1.5 py-0.5 rounded bg-[rgba(61,214,140,0.15)] text-[#49e095] font-medium flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      Confirmed
                    </span>
                    <span className="text-[#626877]">{formatTime(event.at)}</span>
                  </div>
                  <p className="text-xs text-[#ECEDF0] leading-snug">{event.message}</p>
                </div>
              );
            }

            // Warning / Retry styling
            if (isWarning) {
              return (
                <div
                  key={event.event_no}
                  className="p-3 rounded-lg bg-[rgba(245,165,36,0.06)] border border-[#ffb957]/30 flex flex-col gap-1"
                >
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="px-1.5 py-0.5 rounded bg-[rgba(245,165,36,0.15)] text-[#ffb957] font-medium">
                      Warning / Retry
                    </span>
                    <span className="text-[#626877]">{formatTime(event.at)}</span>
                  </div>
                  <p className="text-xs text-[#ECEDF0] leading-snug">{event.message}</p>
                </div>
              );
            }

            // Standard Event Card
            return (
              <div
                key={event.event_no}
                className="p-3 rounded-lg bg-[#181A20] border border-[#262932] flex flex-col gap-1"
              >
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span
                    className={`px-1.5 py-0.5 rounded border text-[10px] font-medium flex items-center gap-1 ${meta.badgeColor}`}
                  >
                    <AgentIcon className="w-3 h-3" />
                    {meta.label}
                  </span>
                  <span className="text-[#626877]">{formatTime(event.at)}</span>
                </div>
                <p className="text-xs text-[#ECEDF0] leading-snug mt-0.5">
                  {event.message}
                </p>
              </div>
            );
          })
        )}
      </div>

      {/* Terminal Status Bar */}
      <div className="mt-3 pt-3 border-t border-[#262932] flex items-center justify-between text-[#626877] text-[11px] font-mono">
        <span className="flex items-center gap-1.5">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isRunning ? "bg-[#49e095] animate-pulse" : "bg-[#626877]"
            }`}
          />
          {isRunning ? "Stream active" : "Stream closed"}
        </span>
        <span>Buffer: {events.length} events</span>
      </div>
    </aside>
  );
}
