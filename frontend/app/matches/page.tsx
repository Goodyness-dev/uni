"use client";
import { useV1 } from "@/lib/v1";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { AlertCircle, AlertTriangle, ArrowRight, Play, RefreshCw } from "lucide-react";
import {
  Run,
  Match,
  ApplicationSummary,
  AppEvent,
  Gap,
  AppStatus,
} from "@/lib/types";
import {
  getLatestRun,
  getRun,
  getRunEvents,
  getMatches,
  getApplications,
  getGaps,
  resumeRun,
} from "@/lib/api";
import { isFinalRun } from "@/lib/status";
import { StageTracker } from "@/components/StageTracker";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { MatchCard } from "@/components/matches/MatchCard";
import { IneligibleSection } from "@/components/matches/IneligibleSection";
import { EventFeed } from "@/components/matches/EventFeed";
import { RunMetricsStrip } from "@/components/matches/RunMetricsStrip";
import { GapQuestionCard } from "@/components/matches/GapQuestionCard";
import { BusinessPlanningCard } from "@/components/matches/BusinessPlanningCard";

function getStageFromStatus(status: AppStatus): number {
  switch (status) {
    case "found":
    case "matched":
    case "skipped":
      return 1;
    case "researched":
      return 2;
    case "edges_selected":
      return 3;
    case "tailored":
      return 4;
    case "verified":
    case "ready":
      return 5;
    case "submitting":
    case "awaiting_user":
    case "submitted":
    case "prepared":
    case "unconfirmed":
    case "failed":
      return 6;
    default:
      return 1;
  }
}

export default function MatchesPage() {
  const [run, setRun] = useState<Run | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [applications, setApplications] = useState<ApplicationSummary[]>([]);
  const [events, setEvents] = useState<AppEvent[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollBackoffUntil = useRef(0);
  const overviewApplicationIds = useRef("");
  const [resuming, setResuming] = useState(false);

  const lastEventNoRef = useRef<number>(0);
  const isPollingRef = useRef<boolean>(false);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Initial load
  useEffect(() => {
    let ignore = false;

    async function init() {
      try {
        const latestRun = await getLatestRun();
        if (ignore) return;
        if (!latestRun || !latestRun.run_id) {
          setNotFound(true);
          setLoadingInitial(false);
          return;
        }
        setRun(latestRun);

        // Fetch matches, applications, gaps, events concurrently
        const [matchesRes, appsRes, eventsRes, gapsRes] = await Promise.all([
          getMatches(latestRun.run_id).catch(() => ({ matches: [] })),
          getApplications(latestRun.run_id).catch(() => ({ applications: [] })),
          getRunEvents(latestRun.run_id, 0).catch(() => ({
            events: [],
            last_event_no: 0,
          })),
          getGaps(latestRun.run_id).catch(() => ({ gaps: [] })),
        ]);

        if (ignore) return;
        setMatches(matchesRes.matches || []);
        setApplications(appsRes.applications || []);
        setError(null);
        setEvents(eventsRes.events || []);
        lastEventNoRef.current = eventsRes.last_event_no || 0;
        setGaps(gapsRes.gaps || []);
      } catch (err: unknown) {
        if (ignore) return;
        const is404 =
          typeof err === "object" &&
          err !== null &&
          "status" in err &&
          (err as { status: number }).status === 404;

        if (is404) {
          setNotFound(true);
        } else {
          const msg = err instanceof Error ? err.message : "Failed to load matches";
          setError(msg);
        }
      } finally {
        if (!ignore) {
          setLoadingInitial(false);
        }
      }
    }

    init();

    return () => {
      ignore = true;
    };
  }, []);

  const handleRetry = useCallback(() => {
    setLoadingInitial(true);
    setError(null);
    getLatestRun()
      .then(async (latestRun) => {
        if (!latestRun || !latestRun.run_id) {
          setNotFound(true);
          setLoadingInitial(false);
          return;
        }
        setRun(latestRun);
        const [matchesRes, appsRes, eventsRes, gapsRes] = await Promise.all([
          getMatches(latestRun.run_id).catch(() => ({ matches: [] })),
          getApplications(latestRun.run_id).catch(() => ({ applications: [] })),
          getRunEvents(latestRun.run_id, 0).catch(() => ({
            events: [],
            last_event_no: 0,
          })),
          getGaps(latestRun.run_id).catch(() => ({ gaps: [] })),
        ]);
        setMatches(matchesRes.matches || []);
        setApplications(appsRes.applications || []);
        setEvents(eventsRes.events || []);
        lastEventNoRef.current = eventsRes.last_event_no || 0;
        setGaps(gapsRes.gaps || []);
        setLoadingInitial(false);
      })
      .catch((err) => {
        const msg = err instanceof Error ? err.message : "Failed to load matches";
        setError(msg);
        setLoadingInitial(false);
      });
  }, []);

  // Polling loop
  const runId = run?.run_id;
  const runStatus = run?.status;

  useEffect(() => {
    if (!runId || !runStatus || isFinalRun(runStatus)) {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }

    const pollTick = async () => {
      if (isPollingRef.current || Date.now() < pollBackoffUntil.current) return;
      isPollingRef.current = true;

      try {
        const updatedRun = await getRun(runId);
        setRun(updatedRun);

        // Fetch events with after = lastEventNoRef.current
        const eventsRes = await getRunEvents(runId, lastEventNoRef.current);
        const hasNewEvents = eventsRes.events && eventsRes.events.length > 0;
        if (hasNewEvents) {
          setEvents((prev) => {
            const existingIds = new Set(prev.map((e) => e.event_no));
            const newEvents = eventsRes.events.filter((e) => !existingIds.has(e.event_no));
            return [...prev, ...newEvents];
          });
          lastEventNoRef.current = eventsRes.last_event_no;
        }

        // Fetch matches and applications on each poll
        if (hasNewEvents || updatedRun.application_ids.join() !== overviewApplicationIds.current || isFinalRun(updatedRun.status)) {
        const [matchesRes, appsRes] = await Promise.all([
          getMatches(runId),
          getApplications(runId),
        ]);
        setMatches(matchesRes.matches || []);
        setApplications(appsRes.applications || []);
        overviewApplicationIds.current = updatedRun.application_ids.join();
        }

        // Check if run has reached final state
        setError(null);
        if (isFinalRun(updatedRun.status)) {
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
          // One final fetch for final consistency
          const finalGaps = await getGaps(runId).catch(() => ({ gaps: [] }));
          setGaps(finalGaps.gaps || []);
        }
      } catch (err) {
        if (typeof err === "object" && err !== null && "status" in err && err.status === 429) pollBackoffUntil.current = Date.now() + 60_000;
        setError(err instanceof Error ? `Live progress could not be refreshed: ${err.message}. Retrying automatically.` : "Live progress could not be refreshed. Retrying automatically.");
      } finally {
        isPollingRef.current = false;
      }
    };

    pollTimerRef.current = setInterval(pollTick, 2000);

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [runId, runStatus]);

  // Resume handler for interrupted runs
  const handleResume = async () => {
    if (!run) return;
    setResuming(true);
    try {
      const res = await resumeRun(run.run_id);
      setRun((prev) => (prev ? { ...prev, status: res.status } : null));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to resume run";
      setError(msg);
    } finally {
      setResuming(false);
    }
  };

  // Derive stage from active matches
  const eligibleMatches = matches.filter((m) => m.status !== "skipped");
  const ineligibleMatches = matches.filter((m) => m.status === "skipped");

  const batchComplete = run?.status === "completed";
  const isCompleted = batchComplete && (!useV1 || (applications.length > 0 && applications.every(application => ["submitted", "prepared", "failed", "skipped"].includes(application.status))));
  const isFailed = run?.status === "failed";
  const isInterrupted = run?.status === "interrupted";
  const isRunning = run?.status === "running";

  const currentStage = isCompleted
    ? 6
    : eligibleMatches.length > 0
    ? Math.max(...eligibleMatches.map((m) => getStageFromStatus(m.status)), 1)
    : 1;

  // Render 404 / Empty state
  if (notFound) {
    return (
      <div className="py-16">
        <EmptyState
          title="No scholarship runs found"
          description="Upload your CV, transcript, and vault profile to discover matching scholarships and launch autonomous applications."
          action={
            <Link
              href="/"
              className="h-9 px-4 rounded-lg bg-[#5b8cff] hover:bg-[#4a7ae8] text-white text-xs font-semibold inline-flex items-center gap-1.5 transition-colors"
            >
              <span>Go to Profile & Upload</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          }
        />
        <BusinessPlanningCard run={null} applications={[]} />
      </div>
    );
  }

  // Render initial loading state
  if (loadingInitial) {
    return (
      <div className="space-y-6 py-6">
        <div className="bg-[#121318] rounded-xl p-5 border border-[#262932] space-y-3">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-12 w-full" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8 space-y-4">
            <div className="bg-[#121318] rounded-xl p-6 border border-[#262932] space-y-4">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-16 w-full" />
            </div>
            <div className="bg-[#121318] rounded-xl p-6 border border-[#262932] space-y-4">
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-16 w-full" />
            </div>
          </div>
          <div className="lg:col-span-4">
            <div className="bg-[#121318] rounded-xl p-4 border border-[#262932] space-y-3">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Top Banner: Interrupted Run */}
      {isInterrupted && (
        <div className="p-4 rounded-xl bg-[rgba(245,165,36,0.08)] border border-[#ffb957]/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 text-[#ffb957]">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <div>
              <p className="text-sm font-semibold">Run was interrupted</p>
              <p className="text-xs text-[#ECEDF0]">
                The agent pipeline paused before completion. You can safely resume where it left off.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleResume}
            disabled={resuming}
            className="h-9 px-4 rounded-lg bg-[#ffb957] hover:bg-[#ffaa33] text-[#121316] text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shrink-0"
          >
            {resuming ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-current" />
            )}
            <span>{resuming ? "Resuming..." : "Resume Run"}</span>
          </button>
        </div>
      )}

      {/* Top Banner: General Error */}
      {error && (
        <div className="p-4 rounded-xl bg-[rgba(248,113,113,0.08)] border border-[#F87171]/40 flex items-center justify-between gap-3 text-[#F87171]">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <p className="text-xs font-mono">{error}</p>
          </div>
          <button
            type="button"
            onClick={handleRetry}
            className="text-xs underline hover:text-white"
          >
            Retry
          </button>
        </div>
      )}

      {/* TOP PIPELINE STAGE STEPPER */}
      <section className="w-full bg-[#121318] rounded-xl border border-[#262932] p-4">
        <div className="flex items-center justify-between mb-3 px-1">
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="text-[#626877] uppercase">Pipeline Run</span>
            <span className="text-[#ECEDF0] font-semibold">
              #{run?.run_id || "ACTIVE"}
            </span>
            {run?.mode && (
              <span className="px-1.5 py-0.5 rounded bg-[#181A20] text-[#9AA0AE] text-[10px]">
                Mode {run.mode}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-xs font-mono">
            {isRunning ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-[#5b8cff] animate-pulse" />
                <span className="text-[#b2c5ff]">
                  Stage {currentStage} of 6 active
                </span>
              </>
            ) : isCompleted ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-[#49e095]" />
                <span className="text-[#49e095]">Pipeline complete</span>
              </>
            ) : (
              <span className="text-[#626877]">{useV1 && batchComplete ? "Preparation complete; review pending" : `Status: ${run?.status ?? "unknown"}`}</span>
            )}
          </div>
        </div>

        <StageTracker
          currentStage={currentStage}
          isCompleted={isCompleted}
          isFailed={isFailed}
        />
      </section>

      {/* SUMMARY & METRICS STRIP */}
      <RunMetricsStrip
        metrics={run?.metrics ?? null}
        traceUrl={run?.trace_url ?? null}
        matches={matches}
      />

      {/* MAIN 2-COLUMN WORKSPACE (65% / 35%) */}
      <BusinessPlanningCard run={run} applications={applications} />
      <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: MATCHES (65%) */}
        <div className="lg:col-span-8 space-y-4">
          {eligibleMatches.length === 0 && isRunning ? (
            <div className="bg-[#121318] rounded-xl border border-[#262932] p-8 text-center space-y-3">
              <div className="w-8 h-8 rounded-full bg-[#181A20] border border-[#5b8cff]/30 mx-auto flex items-center justify-center">
                <span className="w-2 h-2 rounded-full bg-[#5b8cff] animate-ping" />
              </div>
              <h3 className="text-base font-semibold text-[#ECEDF0]">
                Looking for scholarships...
              </h3>
              <p className="text-xs text-[#9AA0AE] max-w-sm mx-auto">
                Scout and Matcher are evaluating criteria against your verified profile facts.
              </p>
            </div>
          ) : eligibleMatches.length === 0 && !isRunning ? (
            <div className="bg-[#121318] rounded-xl border border-[#262932] p-8 text-center space-y-3">
              <p className="text-sm text-[#ECEDF0]">
                No scholarships match yet. Try widening countries or fields.
              </p>
              <Link
                href="/"
                className="inline-flex items-center gap-1.5 text-xs text-[#5b8cff] hover:underline"
              >
                <span>Edit preferences on profile</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          ) : (
            eligibleMatches.map((match) => (
              <MatchCard key={match.application_id || match.listing_id} match={match} />
            ))
          )}

          {/* Collapsed Ineligible Section */}
          <IneligibleSection matches={ineligibleMatches} />

          {/* Soft Optional Gap Question Card */}
          <GapQuestionCard
            gaps={gaps}
            onGapAnswered={(answeredId) => {
              setGaps((prev) =>
                prev.map((g) => (g.id === answeredId ? { ...g, answered: true } : g))
              );
            }}
          />
        </div>

        {/* RIGHT COLUMN: LIVE AGENT ACTIVITY (35%) */}
        <div className="lg:col-span-4">
          <EventFeed events={events} isRunning={isRunning} />
        </div>
      </div>
    </div>
  );
}
