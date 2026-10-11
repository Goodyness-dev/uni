"use client";

import { useState } from "react";
import { ChevronDown, Ban } from "lucide-react";
import { Match } from "@/lib/types";

interface IneligibleSectionProps {
  matches: Match[];
}

export function IneligibleSection({ matches }: IneligibleSectionProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (matches.length === 0) return null;

  return (
    <section className="bg-[#121318] rounded-xl border border-[#262932] overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full p-4 flex items-center justify-between text-left hover:bg-[#181A20] transition-colors"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2.5">
          <Ban className="w-4 h-4 text-[#626877]" />
          <span className="text-sm font-medium text-[#ECEDF0]">Not eligible</span>
          <span className="px-1.5 py-0.5 rounded bg-[#181A20] border border-[#262932] text-[11px] font-mono text-[#9AA0AE]">
            {matches.length}
          </span>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-[#9AA0AE] transition-transform duration-200 ${
            isOpen ? "rotate-180" : "rotate-0"
          }`}
        />
      </button>

      {isOpen && (
        <div className="p-4 pt-0 space-y-2 border-t border-[#262932]/60">
          {matches.map((match) => (
            <div
              key={match.application_id || match.listing_id}
              className="p-3 rounded-lg bg-[#181A20] border border-[#262932] flex flex-col gap-1"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-[#ECEDF0] truncate">
                  {match.name}
                </span>
                <span className="text-[11px] font-mono text-[#F87171] bg-[rgba(248,113,113,0.1)] px-2 py-0.5 rounded border border-[#F87171]/20 shrink-0">
                  Disqualified
                </span>
              </div>
              <p className="text-xs text-[#9AA0AE]">
                Failed rule:{" "}
                <span className="text-[#ECEDF0]">
                  {match.failed_rules && match.failed_rules.length > 0
                    ? match.failed_rules.join(", ")
                    : "Eligibility criteria threshold not met"}
                </span>
              </p>
              {match.fit_reason && (
                <p className="text-[11px] text-[#626877] italic mt-0.5">
                  {match.fit_reason}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
