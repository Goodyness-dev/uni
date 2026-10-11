"use client";

import { useState } from "react";
import { AppEvent, AppStatus, Channel, Claim, DossierFact, Edge, Fact } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { ChannelBadge } from "../../components/ChannelBadge";
import { DemoBadge } from "../../components/DemoBadge";
import { FitScore } from "../../components/FitScore";
import { SourcePill } from "../../components/SourcePill";
import { SegmentText } from "../../components/SegmentText";
import { EdgeCard } from "../../components/EdgeCard";
import { ClaimRow } from "../../components/ClaimRow";
import { DossierFactRow } from "../../components/DossierFactRow";
import { TimelineItem } from "../../components/TimelineItem";
import { FileCard } from "../../components/FileCard";
import { StageTracker } from "../../components/StageTracker";
import { StatTile } from "../../components/StatTile";
import { EmptyState } from "../../components/EmptyState";
import { ErrorBanner } from "../../components/ErrorBanner";
import { Skeleton, SkeletonCard } from "../../components/Skeleton";
import { Toast } from "../../components/Toast";

const SAMPLE_FACTS: Record<string, Fact | DossierFact> = {
  C1: {
    id: "C1",
    source: "cv",
    category: "education",
    text: "BSc Computer Engineering, Fictional State University, CGPA 4.30/5.00.",
    sensitive: false,
  },
  T2: {
    id: "T2",
    source: "transcript",
    category: "grade",
    text: "Embedded Systems: Grade A (4.0/4.0).",
    sensitive: false,
  },
  P7: {
    id: "P7",
    source: "vault",
    category: "projects",
    text: "SunTrack: low cost solar panel monitoring system built with ESP32 microcontroller.",
    sensitive: false,
  },
  P8: {
    id: "P8",
    source: "vault",
    category: "hardships",
    text: "Family income was low during second year; tutored students on weekends to pay tuition.",
    sensitive: true,
  },
  D3: {
    id: "D3",
    topic: "lab_focus",
    text: "Dr. Chen's smart grid lab focuses on edge firmware telemetry for renewable energy microgrids.",
    snippet: "edge firmware telemetry for renewable energy microgrids",
    source_url: "https://demo.portal/about/1",
    retrieved_at: "2026/10/11 02:14:00",
  },
};

const SAMPLE_EDGE: Edge = {
  id: "edge_1",
  profile_fact_ids: ["P7"],
  dossier_fact_ids: ["D3"],
  strength: 0.94,
  reason: "SunTrack ESP32 embedded telemetry directly matches Dr. Chen's microgrid edge sensing priorities.",
  use_in: "essay_opening",
  selected: true,
};

const SAMPLE_CLAIMS: Claim[] = [
  {
    id: "claim_1",
    text: "Built a solar telemetry prototype called SunTrack using the ESP32 microcontroller.",
    segment_index: 0,
    section: "essay",
    source_ids: ["P7", "C1"],
    verdict: "supported",
    reason: "Supported by CV project and vault project records.",
    deterministic_pass: true,
    llm_pass: true,
    challenged: false,
    overturned: false,
  },
  {
    id: "claim_2",
    text: "Led a team of five engineers across three regional deployments.",
    segment_index: 1,
    section: "essay",
    source_ids: ["P7"],
    verdict: "partial",
    reason: "Team size not stated in profile vault.",
    deterministic_pass: false,
    llm_pass: true,
    challenged: true,
    overturned: false,
  },
  {
    id: "claim_3",
    text: "Published findings in IEEE Smart Grid Communications Journal.",
    segment_index: 2,
    section: "essay",
    source_ids: [],
    verdict: "unsupported",
    reason: "Removed because no source supported it.",
    deterministic_pass: false,
    llm_pass: false,
    challenged: true,
    overturned: false,
  },
];

const SAMPLE_DOSSIER: DossierFact = {
  id: "D3",
  topic: "lab_focus",
  text: "Dr. Chen's smart grid lab focuses on edge firmware telemetry for renewable energy microgrids.",
  snippet: "edge firmware telemetry for renewable energy microgrids",
  source_url: "https://demo.portal/about/1",
  retrieved_at: "2026/10/11 02:14:00",
};

const SAMPLE_EVENTS: AppEvent[] = [
  {
    event_no: 1,
    at: "2026/10/11 02:15:30",
    run_id: "run_1",
    application_id: null,
    agent: "Researcher",
    type: "info",
    message: "Found 6 sourced facts from official university portal.",
    data: {},
  },
  {
    event_no: 2,
    at: "2026/10/11 02:16:10",
    run_id: "run_1",
    application_id: "app_1",
    agent: "Submitter",
    type: "recovery_decision",
    message: "Portal error 500 received, retried 3 times with exponential backoff, switched to email submission fallback.",
    data: {
      trigger: "HTTP 500 Internal Error",
      chosen: "Email Package Fallback",
      reason: "Exceeded 3 retry attempts on portal submission",
    },
  },
  {
    event_no: 3,
    at: "2026/10/11 02:17:00",
    run_id: "run_1",
    application_id: "app_1",
    agent: "Verifier",
    type: "warning",
    message: "Removed 1 unsupported claim from essay draft.",
    data: {},
  },
  {
    event_no: 4,
    at: "2026/10/11 02:18:20",
    run_id: "run_1",
    application_id: "app_1",
    agent: "Submitter",
    type: "submitted",
    message: "Application package delivered and confirmed by demo portal. Confirmation: SCHOLAR-9812.",
    data: {},
  },
];

const ALL_STATUSES: AppStatus[] = [
  "found",
  "matched",
  "skipped",
  "researched",
  "edges_selected",
  "tailored",
  "verified",
  "ready",
  "submitting",
  "awaiting_user",
  "submitted",
  "prepared",
  "failed",
];

const ALL_CHANNELS: Channel[] = [
  "email",
  "portal_form",
  "portal_captcha",
  "package_only",
];

export default function StyleguidePage() {
  const [showRemoved, setShowRemoved] = useState(false);
  const [showToast, setShowToast] = useState(false);

  return (
    <div className="max-w-[1100px] mx-auto px-4 md:px-6 py-8 space-y-12">
      <div className="border-b border-[#262932] pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-[#ECEDF0]">
          ScholarPilot Component Styleguide
        </h1>
        <p className="text-xs text-[#9AA0AE] mt-1">
          Temporary showcase verifying all shared components and UI states for Task F02.
        </p>
      </div>

      {/* 1. Status Badges */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          1. Status Badges
        </h2>
        <div className="flex flex-wrap gap-2.5 p-4 rounded-xl bg-[#121318] border border-[#262932]">
          {ALL_STATUSES.map((status) => (
            <StatusBadge
              key={status}
              status={status}
              reason={status === "skipped" ? "GPA under 3.5 minimum" : undefined}
            />
          ))}
        </div>
      </section>

      {/* 2. Channel & Demo Badges */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          2. Channel & Demo Badges
        </h2>
        <div className="flex flex-wrap items-center gap-3 p-4 rounded-xl bg-[#121318] border border-[#262932]">
          {ALL_CHANNELS.map((ch) => (
            <ChannelBadge key={ch} channel={ch} />
          ))}
          <DemoBadge />
          <DemoBadge label="DEMO PORTAL" />
        </div>
      </section>

      {/* 3. Fit Score Variants */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          3. Fit Score (Ring & Bar Variants)
        </h2>
        <div className="p-4 rounded-xl bg-[#121318] border border-[#262932] space-y-6">
          <div className="flex items-center gap-6">
            <FitScore score={92} size="lg" showLabel />
            <FitScore score={68} size="md" showLabel />
            <FitScore score={42} size="sm" showLabel />
          </div>
          <div className="space-y-2 max-w-md">
            <FitScore score={92} variant="bar" />
            <FitScore score={68} variant="bar" />
            <FitScore score={42} variant="bar" />
          </div>
        </div>
      </section>

      {/* 4. Source Pills with Popover */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          4. Source Pills (Interactive Popovers on Click or Enter)
        </h2>
        <div className="p-4 rounded-xl bg-[#121318] border border-[#262932] flex items-center gap-3">
          <SourcePill id="C1" detail={SAMPLE_FACTS.C1} />
          <SourcePill id="T2" detail={SAMPLE_FACTS.T2} />
          <SourcePill id="P7" detail={SAMPLE_FACTS.P7} />
          <SourcePill id="P8" detail={SAMPLE_FACTS.P8} />
          <SourcePill id="D3" detail={SAMPLE_FACTS.D3} />
        </div>
      </section>

      {/* 5. Segment Text */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
            5. Segment Text (Supported, Flagged, Removed)
          </h2>
          <button
            type="button"
            onClick={() => setShowRemoved(!showRemoved)}
            className="text-xs text-[#5b8cff] hover:underline cursor-pointer"
          >
            {showRemoved ? "Hide removed claims" : "Show removed claims"}
          </button>
        </div>
        <div className="p-4 rounded-xl bg-[#121318] border border-[#262932] space-y-3 text-sm">
          <div>
            <SegmentText
              text="My undergraduate engineering capstone was the development of SunTrack, an IoT telemetry system for remote solar installations."
              sources={["P7", "C1"]}
              status="supported"
              factsMap={SAMPLE_FACTS}
            />
          </div>
          <div>
            <SegmentText
              text="I oversaw team deployments across 15 separate university facilities."
              sources={["P7"]}
              status="flagged"
              reason="Metric unverified in records"
              factsMap={SAMPLE_FACTS}
            />
          </div>
          <div>
            <SegmentText
              text="Our results were presented at the 2024 International Conference on Renewable Energy."
              sources={[]}
              status="removed"
              reason="Removed because no source supported it."
              showRemoved={showRemoved}
              factsMap={SAMPLE_FACTS}
            />
          </div>
        </div>
      </section>

      {/* 6. Edge Card */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          6. Edge Card (Evidence Bridge)
        </h2>
        <div className="max-w-xl">
          <EdgeCard
            edge={SAMPLE_EDGE}
            userFact={SAMPLE_FACTS.P7 as Fact}
            programmeFact={SAMPLE_FACTS.D3 as DossierFact}
          />
        </div>
      </section>

      {/* 7. Verification Claims */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          7. Claim Rows (Verification Report)
        </h2>
        <div className="space-y-2">
          {SAMPLE_CLAIMS.map((claim, idx) => (
            <ClaimRow key={idx} claim={claim} factsMap={SAMPLE_FACTS} />
          ))}
        </div>
      </section>

      {/* 8. Dossier Fact Row */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          8. Dossier Fact Row (Research Evidence)
        </h2>
        <div className="max-w-xl">
          <DossierFactRow fact={SAMPLE_DOSSIER} />
        </div>
      </section>

      {/* 9. Timeline & Recovery Card */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          9. Timeline Items (With Recovery Decision Card)
        </h2>
        <div className="space-y-2 max-w-xl">
          {SAMPLE_EVENTS.map((event, idx) => (
            <TimelineItem key={idx} event={event} />
          ))}
        </div>
      </section>

      {/* 10. Stage Tracker */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          10. Pipeline Stage Tracker
        </h2>
        <div className="p-4 rounded-xl bg-[#121318] border border-[#262932] space-y-4">
          <div>
            <p className="text-xs text-[#9AA0AE] mb-2 font-mono">Stage 5 Active (Verify)</p>
            <StageTracker currentStage={5} />
          </div>
          <div>
            <p className="text-xs text-[#9AA0AE] mb-2 font-mono">Pipeline Completed</p>
            <StageTracker currentStage={6} isCompleted />
          </div>
        </div>
      </section>

      {/* 11. Stat Tiles */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          11. Stat Tiles
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatTile label="Claims Checked" value={24} tone="neutral" />
          <StatTile label="Supported" value={23} tone="success" subtext="100% truthful" />
          <StatTile label="Removed Claims" value={1} tone="warning" subtext="Fabrications purged" />
          <StatTile label="Unsupported Final" value={0} tone="success" subtext="Target achieved" />
        </div>
      </section>

      {/* 12. File Cards */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          12. File Cards
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-xl">
          <FileCard
            name="tobi_adeyemi_cv.pdf"
            size="142 KB"
            url="/api/files/cv.pdf"
          />
          <FileCard
            name="application_checklist.txt"
            size="8 KB"
            type="checklist"
          />
        </div>
      </section>

      {/* 13. Empty State, Error Banner, Skeleton */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          13. Error Banner, Empty State & Skeleton Loading
        </h2>
        <div className="space-y-4">
          <ErrorBanner
            message="Portal connection timed out after 10s. Switched to fallback retry mechanism."
            onRetry={() => alert("Retrying...")}
          />
          <EmptyState
            title="No scholarships found yet"
            description="Adjust your search criteria or allow the agent to run wide spectrum discovery."
          />
          <div className="max-w-md space-y-2">
            <Skeleton className="h-4 w-36" />
            <SkeletonCard />
          </div>
        </div>
      </section>

      {/* 14. Toast Trigger */}
      <section className="space-y-3">
        <h2 className="text-sm font-mono uppercase tracking-wider text-[#9AA0AE]">
          14. Toast Notification
        </h2>
        <div>
          <button
            type="button"
            onClick={() => setShowToast(true)}
            className="px-3 py-1.5 rounded bg-[#181A20] hover:bg-[#262932] border border-[#262932] text-xs font-medium text-[#ECEDF0] transition-colors cursor-pointer"
          >
            Trigger Sample Toast
          </button>
          {showToast && (
            <Toast
              message="Application package successfully generated and verified."
              tone="success"
              onDismiss={() => setShowToast(false)}
            />
          )}
        </div>
      </section>
    </div>
  );
}
