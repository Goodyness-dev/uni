import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { Claim, Fact, DossierFact } from "../lib/types";
import { SourcePill } from "./SourcePill";

interface ClaimRowProps {
  claim: Claim;
  factsMap?: Record<string, Fact | DossierFact>;
  className?: string;
}

export function ClaimRow({ claim, factsMap, className = "" }: ClaimRowProps) {
  const isSupported = claim.verdict === "supported";
  const isPartial = claim.verdict === "partial";
  const isUnsupported = claim.verdict === "unsupported";

  return (
    <div
      className={`p-3 rounded-lg bg-[#181A20] border border-[#262932] flex items-start gap-3 ${className}`}
    >
      {/* Verdict Icon */}
      <div className="mt-0.5 shrink-0">
        {isSupported && (
          <div className="w-5 h-5 rounded-full bg-[rgba(61,214,140,0.12)] flex items-center justify-center text-[#49e095]">
            <CheckCircle2 className="w-4 h-4" />
          </div>
        )}
        {isPartial && (
          <div className="w-5 h-5 rounded-full bg-[rgba(245,165,36,0.12)] flex items-center justify-center text-[#ffb957]">
            <AlertTriangle className="w-4 h-4" />
          </div>
        )}
        {isUnsupported && (
          <div className="w-5 h-5 rounded-full bg-[rgba(248,113,113,0.12)] flex items-center justify-center text-[#F87171]">
            <XCircle className="w-4 h-4" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 flex flex-col gap-1.5">
        <p
          className={`text-xs leading-relaxed ${
            isUnsupported ? "line-through text-[#626877]" : "text-[#ECEDF0]"
          }`}
        >
          {claim.text}
        </p>

        {/* Source Pills & Reason */}
        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
          {claim.source_ids.map((sId) => (
            <SourcePill
              key={sId}
              id={sId}
              detail={factsMap ? factsMap[sId] : undefined}
            />
          ))}

          {claim.reason && (
            <span
              className={`text-[11px] px-2 py-0.5 rounded ${
                isUnsupported
                  ? "bg-[rgba(248,113,113,0.12)] text-[#F87171] border border-[#F87171]/20"
                  : "bg-[#262932] text-[#9AA0AE]"
              }`}
            >
              {claim.reason}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
