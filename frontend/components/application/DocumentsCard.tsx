"use client";

import { useState } from "react";
import { FileText, BookOpen, Package, ExternalLink, Eye, EyeOff } from "lucide-react";
import { Application, Fact, DossierFact } from "@/lib/types";
import { fileUrl } from "@/lib/api";
import { SegmentText } from "@/components/SegmentText";
import { FileCard } from "@/components/FileCard";
import { Skeleton } from "@/components/Skeleton";
import { useV1 } from "@/lib/v1";

interface DocumentsCardProps {
  application: Application;
  factsMap: Record<string, Fact | DossierFact>;
}

export function DocumentsCard({ application, factsMap }: DocumentsCardProps) {
  const [activeTab, setActiveTab] = useState<"cv" | "essay" | "package">("cv");
  const [showRemoved, setShowRemoved] = useState<boolean>(false);

  const { tailored, listing, verification, id } = application;

  // Word count for essay
  const essayText = tailored?.essay?.map((seg) => seg.text).join(" ") || "";
  const essayWords = essayText.trim() ? essayText.trim().split(/\s+/).length : 0;
  const wordLimit = listing?.essay_word_limit || 500;

  // Removed claims count
  const removedCount = verification?.removed_claims?.length || 0;

  return (
    <div className="rounded-xl bg-[#181A20] border border-[#262932] overflow-hidden flex flex-col">
      {/* Tab bar header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#262932] bg-[#14171F]">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setActiveTab("cv")}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeTab === "cv"
                ? "bg-[#262932] text-[#ECEDF0] border border-[#353945]"
                : "text-[#9AA0AE] hover:text-[#ECEDF0] hover:bg-[#181A20]"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>CV</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("essay")}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeTab === "essay"
                ? "bg-[#262932] text-[#ECEDF0] border border-[#353945]"
                : "text-[#9AA0AE] hover:text-[#ECEDF0] hover:bg-[#181A20]"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Essay</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("package")}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeTab === "package"
                ? "bg-[#262932] text-[#ECEDF0] border border-[#353945]"
                : "text-[#9AA0AE] hover:text-[#ECEDF0] hover:bg-[#181A20]"
            }`}
          >
            <Package className="w-3.5 h-3.5" />
            <span>Package</span>
          </button>
        </div>

        {/* Tab specific controls */}
        {activeTab === "cv" && removedCount > 0 && (
          <button
            type="button"
            onClick={() => setShowRemoved(!showRemoved)}
            className="inline-flex items-center gap-1.5 text-xs text-[#9AA0AE] hover:text-[#ECEDF0] transition-colors"
          >
            {showRemoved ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            <span>{showRemoved ? "Hide removed claims" : `Show removed claims (${removedCount})`}</span>
          </button>
        )}

        {activeTab === "essay" && tailored && tailored.mode !== "notes_only" && (
          <div className="flex items-center gap-1.5 text-xs font-mono text-[#9AA0AE]">
            <span className={essayWords > wordLimit ? "text-[#F87171] font-semibold" : "text-[#ECEDF0]"}>
              {essayWords}
            </span>
            <span>/</span>
            <span>{wordLimit} words</span>
          </div>
        )}
      </div>

      {/* Tab contents */}
      <div className="p-5">
        {/* Loading skeleton for early stages */}
        {!tailored && (
          <div className="flex flex-col gap-4 py-6">
            <div className="flex items-center gap-2 text-xs text-[#5b8cff] font-mono">
              <span className="w-2 h-2 rounded-full bg-[#5b8cff] animate-ping" />
              <span>Drafting & tailoring documents in progress...</span>
            </div>
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-16 w-5/6" />
          </div>
        )}

        {/* CV TAB */}
        {tailored && activeTab === "cv" && (
          <div className="flex flex-col gap-6">
            {/* CV Summary */}
            {tailored.cv_summary && tailored.cv_summary.length > 0 && (
              <div className="flex flex-col gap-2">
                <h4 className="text-xs font-mono uppercase tracking-wider text-[#9AA0AE]">
                  Tailored Summary
                </h4>
                <div className="p-3.5 rounded-lg bg-[#14171F] border border-[#262932] text-sm leading-relaxed text-[#ECEDF0]">
                  {tailored.cv_summary.map((segment, idx) => {
                    const removedReason = verification?.removed_claims?.find(
                      (r) => r.text.trim() === segment.text.trim()
                    )?.reason;
                    return (
                      <SegmentText
                        key={idx}
                        text={segment.text}
                        sources={segment.source_ids}
                        status={segment.status}
                        reason={removedReason}
                        factsMap={factsMap}
                        showRemoved={showRemoved}
                        className="mr-1"
                      />
                    );
                  })}
                </div>
              </div>
            )}

            {/* CV Selected Bullets */}
            {tailored.cv_bullets && tailored.cv_bullets.length > 0 && (
              <div className="flex flex-col gap-2">
                <h4 className="text-xs font-mono uppercase tracking-wider text-[#9AA0AE]">
                  Highlighted Experience & Evidence Bullets
                </h4>
                <div className="p-3.5 rounded-lg bg-[#14171F] border border-[#262932] flex flex-col gap-2.5">
                  {tailored.cv_bullets.map((bullet, idx) => {
                    const removedReason = verification?.removed_claims?.find(
                      (r) => r.text.trim() === bullet.text.trim()
                    )?.reason;
                    if (bullet.status === "removed" && !showRemoved) return null;
                    return (
                      <div key={idx} className="flex items-start gap-2 text-sm leading-relaxed">
                        <span className="text-[#5b8cff] mt-1 shrink-0">•</span>
                        <div>
                          <SegmentText
                            text={bullet.text}
                            sources={bullet.source_ids}
                            status={bullet.status}
                            reason={removedReason}
                            factsMap={factsMap}
                            showRemoved={showRemoved}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ESSAY TAB */}
        {tailored && activeTab === "essay" && (
          <div className="flex flex-col gap-4">
            {tailored.mode === "notes_only" ? (
              <div className="flex flex-col gap-3">
                <div className="p-3 rounded-lg bg-[rgba(245,165,36,0.12)] border border-[#ffb957]/30 text-xs text-[#ffb957]">
                  <strong className="font-semibold block mb-0.5">Notes, not essay text</strong>
                  <span>
                    This scholarship&apos;s policy restricts AI-generated essay prose. The agent has prepared an evidence outline and talking points for you.
                  </span>
                </div>
                {tailored.outline && tailored.outline.length > 0 && (
                  <ul className="space-y-2 p-3.5 rounded-lg bg-[#14171F] border border-[#262932]">
                    {tailored.outline.map((point, idx) => (
                      <li key={idx} className="text-sm text-[#ECEDF0] flex items-start gap-2">
                        <span className="text-[#49e095] shrink-0 font-mono text-xs mt-0.5">#{idx + 1}</span>
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {listing?.essay_prompt && (
                  <div className="p-3 rounded-lg bg-[#14171F] border border-[#262932] text-xs text-[#9AA0AE]">
                    <span className="font-mono uppercase tracking-wider text-[11px] block text-[#ECEDF0] mb-1">
                      Prompt
                    </span>
                    <p className="italic text-[#ECEDF0]">{listing.essay_prompt}</p>
                  </div>
                )}

                <div className="p-4 rounded-lg bg-[#14171F] border border-[#262932] text-sm leading-relaxed text-[#ECEDF0] flex flex-col gap-3">
                  {tailored.essay && tailored.essay.length > 0 ? (
                    <div>
                      {tailored.essay.map((segment, idx) => {
                        const removedReason = verification?.removed_claims?.find(
                          (r) => r.text.trim() === segment.text.trim()
                        )?.reason;
                        return (
                          <SegmentText
                            key={idx}
                            text={segment.text}
                            sources={segment.source_ids}
                            status={segment.status}
                            reason={removedReason}
                            factsMap={factsMap}
                            showRemoved={showRemoved}
                            className="mr-1"
                          />
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-[#9AA0AE] italic">No tailored essay generated.</p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* PACKAGE TAB */}
        {activeTab === "package" && (
          <div className="flex flex-col gap-4">
            <p className="text-xs text-[#9AA0AE]">
              Generated application package ready for download and manual submission check.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <FileCard
                name={useV1 ? "Source-based CV.pdf" : "Tailored CV (PDF)"}
                type="pdf"
                size={useV1 ? "Source-reviewed PDF" : "Verified PDF"}
                url={fileUrl(id, "cv")}
              />
              <FileCard
                name={useV1 ? "Application writing.txt" : "Scholarship Essay (TXT)"}
                type="markdown"
                size={useV1 ? "Source-reviewed text" : "Verified TXT"}
                url={fileUrl(id, "essay")}
              />
              <FileCard
                name="Application Checklist (TXT)"
                type="checklist"
                size="Requirements check"
                url={fileUrl(id, "checklist")}
              />
            </div>

            {listing?.source_url && (
              <div className="pt-2 border-t border-[#262932]">
                <a
                  href={listing.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 text-xs text-[#5b8cff] hover:underline"
                >
                  <span>View official scholarship source page</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
