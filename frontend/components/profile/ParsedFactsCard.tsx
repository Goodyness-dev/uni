"use client";

import { reviewPendingEvidence } from "../../lib/api";
import { useV1 } from "../../lib/v1";
import { useState } from "react";
import { Fact, SourceKind } from "../../lib/types";
import { CheckCircle2, Lock, Sparkles } from "lucide-react";

interface ParsedFactsCardProps {
  facts: Fact[];
  counts: { cv: number; transcript: number; vault: number };
  onPatchFact: (id: string, text: string) => Promise<void>;
  className?: string;
}

export function ParsedFactsCard({
  facts,
  counts,
  onPatchFact,
  className = "",
}: ParsedFactsCardProps) {
  const [reviewError, setReviewError] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [filter, setFilter] = useState<"all" | SourceKind>("all");
  const [editingTexts, setEditingTexts] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);

  const filteredFacts = facts.filter((f) => {
    if (f.sensitive) return false;
    if (filter === "all") return true;
    return f.source === filter;
  });

  const handleTextChange = (id: string, text: string) => {
    setEditingTexts((prev) => ({ ...prev, [id]: text }));
  };

  const handleBlur = async (id: string, originalText: string) => {
    const current = editingTexts[id];
    if (current !== undefined && current !== originalText && current.trim().length > 0) {
      setSavingId(id);
      try {
        await onPatchFact(id, current.trim());
      } finally {
        setSavingId(null);
      }
    }
  };

  return (
    <section className={`rounded-xl bg-[#121318] border border-[#262932] p-6 flex flex-col gap-6 ${className}`}>
      {useV1 && facts.some(f => f.id.startsWith("U_")) && <div className="text-xs flex flex-col gap-2"><p>Read the source facts below. Confirm only if they accurately reproduce your documents.</p><button disabled={reviewing} className="p-2 rounded bg-[#262932] disabled:opacity-50" onClick={async () => { setReviewing(true); setReviewError(""); try { await reviewPendingEvidence(); window.location.reload(); } catch (error) { setReviewError(error instanceof Error ? error.message : "Review failed."); } finally { setReviewing(false); } }}>{reviewing ? "Saving review…" : "Confirm source facts"}</button>{reviewError && <p role="alert">{reviewError}</p>}</div>}
      {/* Header & Filter */}
      <div className="border-b border-[#262932] pb-4 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[11px] font-mono uppercase text-[#626877]">Atomic Provenance</span>
            <span className="text-[#626877]">•</span>
            <span className="text-[11px] font-mono text-[#49e095] flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              {facts.filter(f => !f.sensitive).length} source facts
            </span>
          </div>
          <h2 className="text-xl font-semibold tracking-tight text-[#ECEDF0]">Parsed facts</h2>
          <p className="text-xs font-mono text-[#9AA0AE] mt-1">
            {counts.cv} from CV, {counts.transcript} from transcript, {counts.vault} from your personal file
          </p>
        </div>

        {/* Filter Segment */}
        <div className="inline-flex p-0.5 rounded bg-[#181A20] border border-[#262932] text-xs font-mono">
          <button
            type="button"
            onClick={() => setFilter("all")}
            className={`px-3 py-1 rounded transition-colors cursor-pointer ${
              filter === "all"
                ? "bg-[#121318] text-[#ECEDF0] border border-[#353945]"
                : "text-[#9AA0AE] hover:text-[#ECEDF0]"
            }`}
          >
            All ({facts.length})
          </button>
          <button
            type="button"
            onClick={() => setFilter("cv")}
            className={`px-3 py-1 rounded transition-colors cursor-pointer ${
              filter === "cv"
                ? "bg-[#121318] text-[#7AA2FF] border border-[#353945]"
                : "text-[#9AA0AE] hover:text-[#ECEDF0]"
            }`}
          >
            CV ({counts.cv})
          </button>
          <button
            type="button"
            onClick={() => setFilter("transcript")}
            className={`px-3 py-1 rounded transition-colors cursor-pointer ${
              filter === "transcript"
                ? "bg-[#121318] text-[#B794F6] border border-[#353945]"
                : "text-[#9AA0AE] hover:text-[#ECEDF0]"
            }`}
          >
            Transcript ({counts.transcript})
          </button>
          <button
            type="button"
            onClick={() => setFilter("vault")}
            className={`px-3 py-1 rounded transition-colors cursor-pointer ${
              filter === "vault"
                ? "bg-[#121318] text-[#5FD3A0] border border-[#353945]"
                : "text-[#9AA0AE] hover:text-[#ECEDF0]"
            }`}
          >
            Personal ({counts.vault})
          </button>
        </div>
      </div>

      {/* Fact Rows List */}
      <div className="flex flex-col divide-y divide-[#262932]">
        {filteredFacts.map((fact) => {
          const currentText = editingTexts[fact.id] !== undefined ? editingTexts[fact.id] : fact.text;
          const isSaving = savingId === fact.id;

          let pillColor = "text-[#9AA0AE] bg-[#181A20] border-[#262932]";
          if (fact.source === "cv") {
            pillColor = "text-[#7AA2FF] bg-[rgba(122,162,255,0.12)] border-[#7AA2FF]/30";
          } else if (fact.source === "transcript") {
            pillColor = "text-[#B794F6] bg-[rgba(183,148,246,0.12)] border-[#B794F6]/30";
          } else if (fact.source === "vault") {
            pillColor = "text-[#5FD3A0] bg-[rgba(95,211,160,0.12)] border-[#5FD3A0]/30";
          }

          return (
            <div
              key={fact.id}
              className={`py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 group transition-colors ${
                fact.sensitive ? "bg-[rgba(245,165,36,0.03)] px-2 rounded" : ""
              }`}
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                {/* ID Pill */}
                <span
                  className={`shrink-0 px-2 py-0.5 rounded text-[11px] font-mono border ${pillColor}`}
                >
                  {fact.id}
                </span>

                {/* Category */}
                <span className="shrink-0 w-24 text-[11px] font-mono uppercase text-[#626877] truncate">
                  {fact.category}
                </span>

                {/* Editable Text */}
                <div className="flex-1 min-w-0 relative">
                  <input
                    readOnly={useV1}
                    type="text"
                    value={currentText}
                    onChange={(e) => handleTextChange(fact.id, e.target.value)}
                    onBlur={() => handleBlur(fact.id, fact.text)}
                    className="w-full bg-transparent border-none text-xs text-[#ECEDF0] focus:outline-none focus:bg-[#181A20] focus:border focus:border-[#353945] px-2 py-1 rounded transition-colors"
                  />
                  {isSaving && (
                    <span className="absolute right-2 top-1 text-[10px] font-mono text-[#5b8cff] animate-pulse">
                      Saving...
                    </span>
                  )}
                </div>
              </div>

              {/* Status / Sensitive Badge */}
              <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                {fact.sensitive ? (
                  <div className="relative group/tooltip flex items-center gap-1.5 px-2 py-0.5 rounded bg-[rgba(245,165,36,0.12)] border border-[#ffb957]/30 text-[#ffb957] cursor-help">
                    <Lock className="w-3.5 h-3.5" />
                    <span className="text-[10px] font-mono uppercase tracking-wider">Restricted</span>
                    {/* Tooltip */}
                    <div className="hidden group-hover/tooltip:block absolute bottom-full right-0 mb-2 w-64 p-2.5 rounded-lg bg-[#181A20] border border-[#353945] text-xs text-[#ECEDF0] leading-snug shadow-xl z-30">
                      Not used unless a scholarship requires it and you agreed.
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-[#626877]">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#49e095]" />
                    <span>{useV1 ? (fact.id.startsWith("U_") ? "REVIEW NEEDED" : "SOURCE REVIEWED") : "VERIFIED"}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
