"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { Application, Fact, DossierFact } from "@/lib/types";
import { getApplication, getFacts } from "@/lib/api";
import { isFinalStatus } from "@/lib/status";
import { ApplicationHeader } from "@/components/application/ApplicationHeader";
import { DocumentsCard } from "@/components/application/DocumentsCard";
import { EvidenceSection } from "@/components/application/EvidenceSection";
import { ResearchSection } from "@/components/application/ResearchSection";
import { VerificationCard } from "@/components/application/VerificationCard";
import { TimelineSection } from "@/components/application/TimelineSection";
import { Skeleton } from "@/components/Skeleton";
import { ErrorBanner } from "@/components/ErrorBanner";
import { EmptyState } from "@/components/EmptyState";

export default function ApplicationDetailPage() {
  const params = useParams();
  const id = typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : "";

  const [application, setApplication] = useState<Application | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [factsMap, setFactsMap] = useState<Record<string, Fact | DossierFact>>({});

  // 1. Fetch applicant facts for source pill popover references
  useEffect(() => {
    getFacts()
      .then((res) => {
        if (res?.facts) {
          setFactsMap((prev) => {
            const next = { ...prev };
            for (const f of res.facts) {
              next[f.id] = f;
            }
            return next;
          });
        }
      })
      .catch((err) => {
        console.error("Failed to load applicant facts map", err);
      });
  }, []);

  // 2. Fetch application and merge dossier facts into factsMap
  const stoppedRef = useRef<boolean>(false);

  const fetchApp = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getApplication(id);
      setApplication(data);
      setError(null);

      // Merge dossier facts into source facts map
      if (data.dossier?.facts) {
        setFactsMap((prev) => {
          const next = { ...prev };
          for (const df of data.dossier!.facts) {
            next[df.id] = df;
          }
          return next;
        });
      }

      if (isFinalStatus(data.status)) {
        stoppedRef.current = true;
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load application data";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [id]);

  // 3. Polling loop: 2s normal, 4s while awaiting_user, stop when final
  useEffect(() => {
    if (!id) return;
    stoppedRef.current = false;
    let isMounted = true;
    let timer: NodeJS.Timeout;

    const poll = async () => {
      if (!isMounted) return;
      await fetchApp();
      if (!isMounted || stoppedRef.current) return;

      const intervalMs = application?.status === "awaiting_user" ? 4000 : 2000;
      timer = setTimeout(poll, intervalMs);
    };

    poll();

    return () => {
      isMounted = false;
      if (timer) clearTimeout(timer);
    };
  }, [id, fetchApp, application?.status]);

  return (
    <div className="min-h-screen bg-[#0d0e11] text-[#ECEDF0] flex flex-col font-sans">
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Error State */}
        {error && (
          <div className="mb-6">
            <ErrorBanner
              message={error}
              onRetry={() => {
                setLoading(true);
                fetchApp();
              }}
            />
          </div>
        )}

        {/* Initial Loading Skeleton */}
        {loading && !application && (
          <div className="flex flex-col gap-6">
            <div className="flex items-center gap-2 text-xs font-mono text-[#5b8cff]">
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Loading application status and verification proof...</span>
            </div>
            <Skeleton className="h-28 w-full rounded-xl" />
            <Skeleton className="h-14 w-full rounded-xl" />
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-7">
                <Skeleton className="h-96 w-full rounded-xl" />
              </div>
              <div className="lg:col-span-5 space-y-4">
                <Skeleton className="h-44 w-full rounded-xl" />
                <Skeleton className="h-44 w-full rounded-xl" />
              </div>
            </div>
          </div>
        )}

        {/* Not Found */}
        {!loading && !application && !error && (
          <EmptyState
            title="Application Not Found"
            description={`Could not find scholarship application with id "${id}".`}
            action={
              <Link
                href="/matches"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#262932] hover:bg-[#353945] text-xs font-medium text-[#ECEDF0] border border-[#353945] transition-colors"
              >
                Back to Matches
              </Link>
            }
          />
        )}

        {/* Main Application Content */}
        {application && (
          <div className="flex flex-col">
            {/* Header with status, badges, trace link, stage tracker, alerts */}
            <ApplicationHeader application={application} />

            {/* Two column layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column (Documents: CV, Essay, Package) */}
              <div className="lg:col-span-7 flex flex-col gap-6">
                <DocumentsCard application={application} factsMap={factsMap} />
              </div>

              {/* Right Column (Evidence, Dossier, Verification, Timeline) */}
              <div className="lg:col-span-5 flex flex-col gap-6">
                {/* 1. Evidence Used (Selected Edges) */}
                <EvidenceSection
                  edges={application.edges}
                  factsMap={factsMap}
                  loading={loading && application.edges.length === 0}
                />

                {/* 2. Research Dossier */}
                <ResearchSection
                  dossier={application.dossier}
                  loading={loading && !application.dossier}
                />

                {/* 3. Verification Report */}
                <VerificationCard
                  report={application.verification}
                  factsMap={factsMap}
                  loading={loading && !application.verification}
                />

                {/* 4. Timeline & Notifications */}
                <TimelineSection
                  timeline={application.timeline}
                  notifications={application.notifications}
                  loading={loading && application.timeline.length === 0}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
