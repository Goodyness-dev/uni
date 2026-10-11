import { ExternalLink, Calendar } from "lucide-react";
import { DossierFact } from "../lib/types";
import { SourcePill } from "./SourcePill";

interface DossierFactRowProps {
  fact: DossierFact;
  className?: string;
}

export function DossierFactRow({ fact, className = "" }: DossierFactRowProps) {
  const dateFormatted = fact.retrieved_at ? fact.retrieved_at.split(" ")[0] : null;

  return (
    <div
      className={`p-3 rounded-lg bg-[#181A20] border border-[#262932] hover:border-[#353945] transition-colors flex flex-col gap-2 ${className}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SourcePill id={fact.id} detail={fact} />
          <span className="px-2 py-0.5 rounded bg-[#262932] text-[#ECEDF0] text-[11px] font-mono capitalize">
            {fact.topic}
          </span>
        </div>

        {dateFormatted && (
          <div className="flex items-center gap-1 text-[11px] font-mono text-[#9AA0AE]">
            <Calendar className="w-3 h-3" />
            <span>{dateFormatted}</span>
          </div>
        )}
      </div>

      <p className="text-xs text-[#ECEDF0] leading-relaxed">
        {fact.text || fact.snippet}
      </p>

      {fact.source_url && (
        <div className="pt-1">
          <a
            href={fact.source_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[11px] text-[#5b8cff] hover:underline"
          >
            <span>Public source</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      )}
    </div>
  );
}
