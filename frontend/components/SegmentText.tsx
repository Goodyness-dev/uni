import { SourcePill } from "./SourcePill";
import { Fact, DossierFact } from "../lib/types";

interface SegmentTextProps {
  text: string;
  sources: string[];
  status?: "supported" | "flagged" | "removed";
  reason?: string;
  factsMap?: Record<string, Fact | DossierFact>;
  showRemoved?: boolean;
  className?: string;
}

export function SegmentText({
  text,
  sources = [],
  status = "supported",
  reason,
  factsMap,
  showRemoved = false,
  className = "",
}: SegmentTextProps) {
  // If removed and not showing removed items, return null
  if (status === "removed" && !showRemoved) {
    return null;
  }

  let textStyle = "text-[#ECEDF0]";
  if (status === "flagged") {
    textStyle = "text-[#ECEDF0] underline decoration-[#ffb957] decoration-wavy underline-offset-4";
  } else if (status === "removed") {
    textStyle = "line-through text-[#626877]";
  }

  return (
    <span className={`inline leading-relaxed ${className}`}>
      <span className={textStyle}>{text}</span>
      {sources.map((sId) => (
        <SourcePill
          key={sId}
          id={sId}
          detail={factsMap ? factsMap[sId] : undefined}
        />
      ))}
      {status === "removed" && reason && (
        <span className="inline-block ml-2 px-1.5 py-0.5 rounded text-[10px] bg-[rgba(248,113,113,0.12)] text-[#F87171] border border-[#F87171]/30 font-sans select-none">
          {reason}
        </span>
      )}
    </span>
  );
}
