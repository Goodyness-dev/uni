"use client";

import { ShieldCheck, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { VerificationReport, Fact, DossierFact } from "@/lib/types";
import { StatTile } from "@/components/StatTile";
import { ClaimRow } from "@/components/ClaimRow";
import { Skeleton } from "@/components/Skeleton";

interface VerificationCardProps {
  report: VerificationReport | null;
  factsMap: Record<string, Fact | DossierFact>;
  loading?: boolean;
}

export function VerificationCard({ report, factsMap, loading = false }: VerificationCardProps) {
  if (loading || !report) {
    return (
      <div className="p-4 rounded-xl bg-[#181A20] border border-[#262932] flex flex-col gap-3">
        <div className="flex items-center gap-2 text-xs text-[#5b8cff] font-mono">
          <span className="w-2 h-2 rounded-full bg-[#5b8cff] animate-ping" />
          <span>Verification & self-challenge audit pending...</span>
        </div>
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if ("mode" in report && ["extractive", "original_evidence_notes"].includes(String(report.mode))) {
    return <section className="p-4 rounded-xl bg-[#181A20] border border-[#262932] text-xs flex flex-col gap-2">
      <h3 className="text-sm font-semibold">Source review</h3>
      <p>The package uses original source text with deterministic support checks. AI generation and Challenger calls were disabled for this run.</p>
      <p>Review the documents before submitting. Source alignment does not certify document authenticity.</p>
    </section>;
  }

  const {
    claims = [],
    removed_claims = [],
    overturned_claims = [],
    unsupported_final = 0,
    rounds = 1,
  } = report;

  const supportedCount = claims.filter((c) => c.verdict === "supported").length;
  const isAllVerified = unsupported_final === 0;

  return (
    <div className="p-4 rounded-xl bg-[#181A20] border border-[#262932] flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-[#262932]">
        <div>
          <h3 className="text-sm font-semibold text-[#ECEDF0] flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-[#49e095]" />
            <span>Verification Report</span>
          </h3>
          <p className="text-[11px] text-[#9AA0AE]">
            Multi-round hallucination audit & factual self-challenge
          </p>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#262932] text-[#ECEDF0] flex items-center gap-1">
          <RefreshCw className="w-3 h-3 text-[#5b8cff]" />
          <span>{rounds} {rounds === 1 ? "round" : "rounds"}</span>
        </span>
      </div>

      {/* Demo Highlight: All claims verified banner */}
      {isAllVerified ? (
        <div className="p-3.5 rounded-lg bg-[rgba(61,214,140,0.12)] border border-[#49e095]/40 flex items-start gap-2.5">
          <CheckCircle2 className="w-5 h-5 text-[#49e095] shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-bold text-[#49e095] uppercase tracking-wide">
              Retained claims checked
            </h4>
            <p className="text-xs text-[#ECEDF0] mt-0.5 leading-relaxed">
              Retained text passed the configured source checks. Review it before submission.
            </p>
          </div>
        </div>
      ) : (
        <div className="p-3.5 rounded-lg bg-[rgba(248,113,113,0.12)] border border-[#F87171]/40 flex items-start gap-2.5">
          <AlertCircle className="w-5 h-5 text-[#F87171] shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-bold text-[#F87171] uppercase tracking-wide">
              {unsupported_final} Unsupported Claims Found
            </h4>
            <p className="text-xs text-[#ECEDF0] mt-0.5 leading-relaxed">
              The agent has flagged or removed unverified assertions to protect applicant integrity.
            </p>
          </div>
        </div>
      )}

      {/* Summary Stat Tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        <StatTile
          label="Checked"
          value={claims.length}
          tone="neutral"
          className="col-span-1"
        />
        <StatTile
          label="Supported"
          value={supportedCount}
          tone="success"
          className="col-span-1"
        />
        <StatTile
          label="Removed"
          value={removed_claims.length}
          tone={removed_claims.length > 0 ? "warning" : "neutral"}
          className="col-span-1"
        />
        <StatTile
          label="Overturned"
          value={overturned_claims.length}
          tone={overturned_claims.length > 0 ? "info" : "neutral"}
          className="col-span-1"
        />
        <StatTile
          label="Final Unsupp."
          value={unsupported_final}
          tone={unsupported_final === 0 ? "success" : "danger"}
          className="col-span-2 sm:col-span-1"
        />
      </div>

      {/* Overturned by self challenge section */}
      {overturned_claims.length > 0 && (
        <div className="p-3 rounded-lg bg-[rgba(91,140,255,0.08)] border border-[#5b8cff]/30 flex flex-col gap-2">
          <h4 className="text-xs font-mono uppercase tracking-wider text-[#b2c5ff] flex items-center justify-between">
            <span>Overturned by self challenge ({overturned_claims.length})</span>
          </h4>
          <div className="flex flex-col gap-2">
            {overturned_claims.map((oc, idx) => (
              <div key={idx} className="p-2 rounded bg-[#181A20] border border-[#262932] text-xs">
                <p className="text-[#ECEDF0] italic font-mono text-[11px]">&quot;{oc.text}&quot;</p>
                <p className="text-[#b2c5ff] text-[11px] mt-1">Reason: {oc.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Removed claims section */}
      {removed_claims.length > 0 && (
        <div className="p-3 rounded-lg bg-[rgba(248,113,113,0.08)] border border-[#F87171]/20 flex flex-col gap-2">
          <h4 className="text-xs font-mono uppercase tracking-wider text-[#F87171]">
            Claims Removed from Final Documents ({removed_claims.length})
          </h4>
          <div className="flex flex-col gap-2">
            {removed_claims.map((rc, idx) => (
              <div key={idx} className="p-2 rounded bg-[#181A20] border border-[#262932] text-xs">
                <p className="text-[#626877] line-through">&quot;{rc.text}&quot;</p>
                <p className="text-[#F87171] text-[11px] mt-1">{rc.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Claims List */}
      {claims.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-mono uppercase tracking-wider text-[#9AA0AE]">
            Audit Trail ({claims.length} claims)
          </h4>
          <div className="flex flex-col gap-2 max-h-96 overflow-y-auto pr-1">
            {claims.map((claim) => (
              <ClaimRow key={claim.id} claim={claim} factsMap={factsMap} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
