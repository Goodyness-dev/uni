"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { ExternalLink, X, Calendar, Lock } from "lucide-react";
import { Fact, DossierFact } from "../lib/types";

interface SourcePillProps {
  id: string; // e.g. "C1", "T2", "P7", "D3"
  detail?: Fact | DossierFact;
  className?: string;
}

export function SourcePill({ id, detail, className = "" }: SourcePillProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pillRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const prefix = id.charAt(0).toUpperCase();

  // Color styles based on source type
  let colorClasses = "text-[#9AA0AE] bg-[#181A20] border-[#262932]";
  let sourceLabel = "Source";

  if (prefix === "C") {
    colorClasses = "text-[#7AA2FF] bg-[rgba(122,162,255,0.12)] border-[#7AA2FF]/30 hover:border-[#7AA2FF]";
    sourceLabel = "CV";
  } else if (prefix === "T") {
    colorClasses = "text-[#B794F6] bg-[rgba(183,148,246,0.12)] border-[#B794F6]/30 hover:border-[#B794F6]";
    sourceLabel = "Transcript";
  } else if (prefix === "P") {
    colorClasses = "text-[#5FD3A0] bg-[rgba(95,211,160,0.12)] border-[#5FD3A0]/30 hover:border-[#5FD3A0]";
    sourceLabel = "Personal Vault";
  } else if (prefix === "D") {
    colorClasses = "text-[#F5A25D] bg-[rgba(245,162,93,0.12)] border-[#F5A25D]/30 hover:border-[#F5A25D]";
    sourceLabel = "Dossier Research";
  }

  // Close on outside click or Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        pillRef.current?.focus();
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        pillRef.current &&
        !pillRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setIsOpen((prev) => !prev);
    }
  };

  const isDossier = prefix === "D" || (detail && "topic" in detail);
  const dossierItem = isDossier ? (detail as DossierFact | undefined) : undefined;
  const userFact = !isDossier ? (detail as Fact | undefined) : undefined;

  return (
    <span className="relative inline-block align-middle mx-1">
      <button
        ref={pillRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        onKeyDown={handleKeyDown}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-label={`Source citation ${id} from ${sourceLabel}`}
        className={`inline-flex items-center justify-center px-1.5 py-0.5 rounded text-[11px] font-mono font-medium border transition-colors cursor-pointer select-none ${colorClasses} ${className}`}
      >
        {id}
      </button>

      {isOpen && (
        <div
          ref={popoverRef}
          role="dialog"
          aria-label={`Source detail for ${id}`}
          className="absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-2 w-72 sm:w-80 p-3 rounded-lg bg-[#181A20] border border-[#353945] shadow-xl text-left"
        >
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#262932]">
            <div className="flex items-center gap-1.5">
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono uppercase font-semibold border ${colorClasses}`}>
                {id}
              </span>
              <span className="text-xs font-medium text-[#ECEDF0]">
                {sourceLabel}
              </span>
              {userFact?.sensitive && (
                <span className="flex items-center gap-0.5 text-[10px] text-[#ffb957]" title="Sensitive detail">
                  <Lock className="w-3 h-3" />
                  <span>Sensitive</span>
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="p-1 rounded text-[#9AA0AE] hover:text-[#ECEDF0] hover:bg-[#262932] transition-colors"
              aria-label="Close popover"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="text-xs text-[#ECEDF0] space-y-2">
            {dossierItem ? (
              <>
                <div className="flex items-center gap-1.5 text-[11px] text-[#9AA0AE]">
                  <span className="px-1.5 py-0.5 rounded bg-[#262932] text-[#ECEDF0] font-mono">
                    {dossierItem.topic}
                  </span>
                  {dossierItem.retrieved_at && (
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {dossierItem.retrieved_at.split(" ")[0]}
                    </span>
                  )}
                </div>
                <p className="leading-relaxed text-[#ECEDF0] font-normal">
                  {dossierItem.text || dossierItem.snippet}
                </p>
                {dossierItem.source_url && (
                  <a
                    href={dossierItem.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] text-[#5b8cff] hover:underline"
                  >
                    <span>View source page</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </>
            ) : userFact ? (
              <>
                <div className="text-[11px] text-[#9AA0AE] uppercase tracking-wider font-mono">
                  Category: {userFact.category}
                </div>
                <p className="leading-relaxed text-[#ECEDF0]">
                  {userFact.text}
                </p>
              </>
            ) : (
              <p className="text-[#9AA0AE] italic text-[11px]">
                Ground truth fact reference {id} recorded in applicant dossier.
              </p>
            )}
          </div>
        </div>
      )}
    </span>
  );
}
