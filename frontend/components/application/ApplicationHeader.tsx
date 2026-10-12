"use client";

import { useState } from "react";
import { approveApplication, continueApplication, withdrawApplication } from "@/lib/api";
import { useV1 } from "@/lib/v1";
import Link from "next/link";
import { ArrowLeft, ExternalLink, XCircle, CheckCircle2, ShieldAlert } from "lucide-react";
import { Application } from "@/lib/types";
import { statusStage } from "@/lib/status";
import { daysLeft } from "@/lib/format";
import { StatusBadge } from "@/components/StatusBadge";
import { ChannelBadge } from "@/components/ChannelBadge";
import { DemoBadge } from "@/components/DemoBadge";
import { StageTracker } from "@/components/StageTracker";

interface ApplicationHeaderProps {
  application: Application;
}

export function ApplicationHeader({ application }: ApplicationHeaderProps) {
  const [approvalError, setApprovalError] = useState("");
  const [approving, setApproving] = useState(false);
  const { listing, status, trace_url, handoff, failure_reason, submission, id } = application;

  const daysRemaining = listing?.deadline ? daysLeft(listing.deadline) : null;
  const isUrgent = daysRemaining !== null && daysRemaining <= 14;

  const isCompleted = status === "submitted" || status === "prepared";
  const isFailed = status === "failed";
  const isAwaiting = status === "awaiting_user";

  return (
    <div className="flex flex-col gap-4 mb-6">
      {/* Back button */}
      <div>
        <Link
          href="/matches"
          className="inline-flex items-center gap-1.5 text-xs text-[#9AA0AE] hover:text-[#ECEDF0] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Matches</span>
        </Link>
      </div>

      {/* Main title row */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-4 rounded-xl bg-[#181A20] border border-[#262932]">
        <div className="flex flex-col gap-2 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold text-[#ECEDF0] tracking-tight">
              {listing?.name || id}
            </h1>
            {listing?.is_mock && <DemoBadge />}
            <StatusBadge status={status} />
            {listing?.channel && <ChannelBadge channel={listing.channel} />}
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-[#9AA0AE]">
            {listing?.provider && (
              <span>
                Provider: <strong className="text-[#ECEDF0] font-medium">{listing.provider}</strong>
              </span>
            )}
            {listing?.country && (
              <span>
                Country: <strong className="text-[#ECEDF0] font-medium">{listing.country}</strong>
              </span>
            )}
            {daysRemaining !== null && (
              <span className={`font-mono ${isUrgent ? "text-[#ffb957] font-semibold" : "text-[#9AA0AE]"}`}>
                {daysRemaining > 0
                  ? `${daysRemaining} days left`
                  : daysRemaining === 0
                  ? "Deadline is today"
                  : "Deadline passed"}
              </span>
            )}
          </div>
        </div>

        {/* View trace button & neatlogs badge */}
        {trace_url && (
          <div className="shrink-0 flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#181A20] border border-[#5b8cff]/30 text-[11px] text-[#b2c5ff]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#5b8cff] animate-pulse" />
              <span>Neatlogs instrumentation enabled</span>
            </span>
            <a
              href={trace_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#262932] hover:bg-[#353945] border border-[#353945] text-xs font-medium text-[#7AA2FF] transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>View Neatlogs trace</span>
            </a>
          </div>
        )}
      </div>

      {useV1 && status === "ready" && <div className="text-xs"><button disabled={approving} className="p-3 rounded bg-[#262932] disabled:opacity-50" onClick={async () => { setApproving(true); setApprovalError(""); try { await approveApplication(id); window.location.reload(); } catch (error) { setApprovalError(error instanceof Error ? error.message : "Approval failed."); } finally { setApproving(false); } }}>{approving ? "Approving…" : "Approve reviewed demo application"}</button>{approvalError && <p role="alert">{approvalError}</p>}</div>}
      {/* Stage Tracker */}
      {useV1 && !["submitted", "prepared", "failed", "skipped"].includes(status) && <div className="flex gap-3 text-xs">
        {handoff?.reason === "missing_evidence" && <><Link href="/" className="text-[#7AA2FF]">Upload missing evidence</Link>
          <button disabled={approving} className="text-[#49e095]" onClick={async () => { setApproving(true); try { await continueApplication(id); window.location.reload(); } catch (err) { setApprovalError(err instanceof Error ? err.message : "Could not continue."); } finally { setApproving(false); } }}>Continue agent</button></>}
        <button disabled={approving} className="text-red-300" onClick={async () => { setApproving(true); try { await withdrawApplication(id); window.location.reload(); } catch (err) { setApprovalError(err instanceof Error ? err.message : "Could not stop."); } finally { setApproving(false); } }}>Stop this application</button>
      </div>}
      <StageTracker
        currentStage={statusStage(status)}
        isCompleted={isCompleted}
        isFailed={isFailed}
      />

      {/* Attention banner: awaiting_user */}
      {isAwaiting && (
        <div className="p-4 rounded-xl bg-[rgba(245,158,11,0.12)] border border-[#F59E0B]/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-[#F59E0B]/20 text-[#ffb957] shrink-0 mt-0.5">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#ffb957]">This application needs you</h3>
              <p className="text-xs text-[#ECEDF0] mt-0.5 leading-relaxed">
                {handoff?.instructions ||
                  handoff?.reason ||
                  "The application portal requires you to solve a CAPTCHA or confirm details."}
              </p>
            </div>
          </div>
          <Link
            href={`/handoff/${id}`}
            className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-[#F59E0B] hover:bg-[#D97706] text-[#14171F] font-semibold text-xs transition-colors shrink-0 shadow-sm"
          >
            Open handoff
          </Link>
        </div>
      )}

      {/* Failed banner */}
      {isFailed && (
        <div className="p-4 rounded-xl bg-[rgba(248,113,113,0.12)] border border-[#F87171]/40 flex items-start gap-3">
          <div className="p-2 rounded-lg bg-[#F87171]/20 text-[#F87171] shrink-0 mt-0.5">
            <XCircle className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#F87171]">Application Failed</h3>
            <p className="text-xs text-[#ECEDF0] mt-0.5 leading-relaxed">
              {failure_reason || "An error occurred while preparing or submitting this application."}
            </p>
          </div>
        </div>
      )}

      {/* Submitted card */}
      {status === "submitted" && (
        <div className="p-4 rounded-xl bg-[rgba(61,214,140,0.12)] border border-[#49e095]/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[#49e095]/20 text-[#49e095] shrink-0">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#49e095]">Application Submitted</h3>
              <p className="text-xs text-[#ECEDF0] mt-0.5">
                {submission?.at ? `Confirmed on ${submission.at}` : "Submission confirmed"} via{" "}
                <span className="font-mono text-[#9AA0AE]">{submission?.channel || listing?.channel}</span>
              </p>
            </div>
          </div>
          {submission?.confirmation_code && (
            <div className="px-3 py-1.5 rounded-lg bg-[#181A20] border border-[#262932] text-xs font-mono text-[#ECEDF0]">
              Code: <strong className="text-[#49e095] font-bold">{submission.confirmation_code}</strong>
            </div>
          )}
        </div>
      )}

      {/* Package prepared card */}
      {status === "prepared" && (
        <div className="p-4 rounded-xl bg-[#181A20] border border-[#49e095]/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[#49e095]/10 text-[#49e095] shrink-0">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#ECEDF0]">Package Ready</h3>
              <p className="text-xs text-[#9AA0AE] mt-0.5">
                Your source-based CV, writing material and submission checklist are prepared for review.
              </p>
            </div>
          </div>
          {listing?.source_url && (
            <a
              href={listing.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#262932] hover:bg-[#353945] text-xs font-medium text-[#ECEDF0] border border-[#353945] transition-colors shrink-0"
            >
              <span>Submit on official portal</span>
              <ExternalLink className="w-3.5 h-3.5 text-[#9AA0AE]" />
            </a>
          )}
        </div>
      )}
    </div>
  );
}
