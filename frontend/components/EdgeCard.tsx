import { ArrowRight, Sparkles } from "lucide-react";
import { Edge, Fact, DossierFact } from "../lib/types";
import { SourcePill } from "./SourcePill";

interface EdgeCardProps {
  edge: Edge;
  userFact?: Fact;
  programmeFact?: DossierFact;
  factsMap?: Record<string, Fact | DossierFact>;
  className?: string;
}

export function EdgeCard({
  edge,
  userFact,
  programmeFact,
  factsMap,
  className = "",
}: EdgeCardProps) {
  const strengthPct = Math.round(
    edge.strength <= 1 ? edge.strength * 100 : edge.strength
  );

  return (
    <div
      className={`p-3.5 rounded-lg bg-[#181A20] border border-[#262932] hover:border-[#353945] transition-colors flex flex-col gap-2.5 ${className}`}
    >
      {/* Header: strength indicator and use_in chip */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Strength meter dots */}
          <div className="flex items-center gap-1" title={`Strength: ${strengthPct}%`}>
            {[20, 40, 60, 80, 100].map((step) => (
              <span
                key={step}
                className={`w-1.5 h-3 rounded-xs ${
                  strengthPct >= step ? "bg-[#49e095]" : "bg-[#262932]"
                }`}
              />
            ))}
          </div>
          <span className="text-xs font-mono text-[#49e095] font-medium">
            {strengthPct}% match
          </span>
        </div>

        {edge.use_in && (
          <span className="px-2 py-0.5 rounded bg-[#262932] text-[#ECEDF0] text-[11px] font-mono border border-[#353945] capitalize">
            Used in: {edge.use_in.replace("_", " ")}
          </span>
        )}
      </div>

      {/* Connection: User Facts -> Programme Facts */}
      <div className="flex items-center gap-2 py-1 flex-wrap">
        <div className="flex items-center gap-1">
          {edge.profile_fact_ids.map((id) => (
            <SourcePill
              key={id}
              id={id}
              detail={userFact?.id === id ? userFact : factsMap ? factsMap[id] : undefined}
            />
          ))}
        </div>
        <ArrowRight className="w-3.5 h-3.5 text-[#9AA0AE]" />
        <div className="flex items-center gap-1">
          {edge.dossier_fact_ids.map((id) => (
            <SourcePill
              key={id}
              id={id}
              detail={programmeFact?.id === id ? programmeFact : factsMap ? factsMap[id] : undefined}
            />
          ))}
        </div>
      </div>

      {/* Reason sentence */}
      <p className="text-xs text-[#ECEDF0] leading-relaxed">
        {edge.reason}
      </p>

      {/* Footer disclaimer badge */}
      <div className="pt-1 flex items-center gap-1.5 text-[10px] text-[#9AA0AE]">
        <Sparkles className="w-3 h-3 text-[#5b8cff]" />
        <span>Chosen automatically by agent & checked by Verifier</span>
      </div>
    </div>
  );
}
