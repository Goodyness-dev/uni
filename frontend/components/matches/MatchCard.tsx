import { useV1 } from "../../lib/v1";
import Link from "next/link";
import { ArrowRight, Eye, AlertTriangle } from "lucide-react";
import { Match } from "@/lib/types";
import { daysLeft } from "@/lib/format";
import { channelLabel } from "@/lib/status";
import { StatusBadge } from "@/components/StatusBadge";
import { DemoBadge } from "@/components/DemoBadge";
import { FitScore } from "@/components/FitScore";

interface MatchCardProps {
  match: Match;
  batchFinished?: boolean;
}

export function MatchCard({ match, batchFinished = false }: MatchCardProps) {
  const days = daysLeft(match.deadline);
  const isUrgent = days <= 14;

  // View application button enabled from status 'researched' onward
  const isEarlyStage = match.status === "found" || match.status === "matched" || match.status === "skipped";
  const canView = !isEarlyStage;
  const isAwaitingUser = match.status === "awaiting_user";

  const ruleEntries: { label: string; pass: boolean }[] = useV1 ? [] : [
    { label: "Country", pass: match.hard_rule_results?.country ?? true },
    { label: "Level", pass: match.hard_rule_results?.level ?? true },
    { label: "GPA", pass: match.hard_rule_results?.gpa ?? true },
    { label: "Field", pass: match.hard_rule_results?.field ?? true },
    { label: "Deadline", pass: match.hard_rule_results?.deadline ?? true },
    { label: "Nationality", pass: match.hard_rule_results?.nationality ?? true },
  ];

  return (
    <article
      className={`bg-[#121318] rounded-xl p-5 border transition-all ${
        isAwaitingUser
          ? "border-[#ffb957]/40 bg-[rgba(245,165,36,0.03)]"
          : "border-[#262932] hover:border-[#353945]"
      }`}
    >
      {/* Title & Status Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-[#ECEDF0] leading-snug">
              {match.name}
            </h2>
            {match.is_mock && <DemoBadge />}
            <StatusBadge status={match.status} />
          </div>
          <p className="text-xs text-[#9AA0AE]">
            {match.country} • {match.level} • {channelLabel(match.channel)}
          </p>
        </div>

        {/* Fit Score Ring */}
        <div className="shrink-0 flex items-center sm:self-start bg-[#181A20] px-3 py-1.5 rounded-lg border border-[#262932]">
          <div className="flex items-center gap-2.5">
            <span className="text-[11px] font-mono text-[#626877] uppercase tracking-wider">
              Fit Score
            </span>
            <FitScore score={match.fit_score} variant="ring" size="sm" />
          </div>
        </div>
      </div>

      {/* Fit Reason */}
      <p className="text-sm text-[#ECEDF0] mb-3 leading-relaxed">
        {match.fit_reason}
      </p>

      {/* Criteria Checks */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {ruleEntries.map((rule) => (
          <span
            key={rule.label}
            className={`px-2 py-0.5 rounded text-[11px] font-mono flex items-center gap-1 border ${
              rule.pass
                ? "bg-[#181A20] border-[#262932] text-[#9AA0AE]"
                : "bg-[rgba(248,113,113,0.1)] border-[#F87171]/30 text-[#F87171]"
            }`}
          >
            <span>{rule.label}</span>
            {rule.pass ? (
              <span className="text-[#49e095] font-bold">✓</span>
            ) : (
              <span className="text-[#F87171] font-bold">✗</span>
            )}
          </span>
        ))}
      </div>

      {/* Awaiting User Warning Callout */}
      {isAwaitingUser && (
        <div className="p-3 rounded-lg bg-[#181A20] border border-[#ffb957]/30 mb-4 flex items-center gap-2.5 text-[#ffb957]">
          <AlertTriangle className="w-4 h-4 shrink-0 text-[#ffb957]" />
          <p className="text-xs text-[#ECEDF0]">
            <span className="font-semibold text-[#ffb957]">Action required:</span>{" "}
            Portal CAPTCHA challenge awaiting your confirmation.
          </p>
        </div>
      )}

      {/* Card Footer */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-[#262932]/60">
        <div className="flex items-center gap-3 text-xs font-mono">
          <span
            className={
              isUrgent ? "text-[#ffb957] font-semibold" : "text-[#ECEDF0] font-medium"
            }
          >
            {days >= 0 ? `${days} days left` : "Deadline passed"}
          </span>
          <span className="text-[#626877]">•</span>
          <span className="text-[#9AA0AE]">{channelLabel(match.channel)}</span>
        </div>

        <div>
          {isAwaitingUser ? (
            <Link
              href={`/handoff/${match.application_id}`}
              className="h-9 px-4 rounded-lg bg-[#ECEDF0] text-[#121316] hover:bg-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-sm"
            >
              <span>Complete handoff</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          ) : canView ? (
            <Link
              href={`/applications/${match.application_id}`}
              className="h-9 px-4 rounded-lg bg-[#181A20] hover:bg-[#292a2d] text-[#ECEDF0] border border-[#262932] hover:border-[#353945] text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
            >
              <span>View application</span>
              <Eye className="w-3.5 h-3.5 text-[#9AA0AE]" />
            </Link>
          ) : (
            <button
              disabled
              type="button"
              className="h-9 px-4 rounded-lg bg-[#181A20] border border-[#262932] text-[#626877] text-xs font-mono flex items-center justify-center gap-1.5 cursor-not-allowed opacity-75"
            >
              {!batchFinished && <span className="w-1.5 h-1.5 rounded-full bg-[#5b8cff] animate-ping mr-1" />}
              <span>{batchFinished ? "Not processed in this batch" : "Waiting for processing..."}</span>
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
