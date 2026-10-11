"use client";

import { Sparkles } from "lucide-react";
import { Edge, Fact, DossierFact } from "@/lib/types";
import { EdgeCard } from "@/components/EdgeCard";
import { Skeleton } from "@/components/Skeleton";

interface EvidenceSectionProps {
  edges: Edge[];
  factsMap: Record<string, Fact | DossierFact>;
  loading?: boolean;
}

export function EvidenceSection({ edges, factsMap, loading = false }: EvidenceSectionProps) {
  const selectedEdges = edges?.filter((e) => e.selected) || [];

  return (
    <div className="p-4 rounded-xl bg-[#181A20] border border-[#262932] flex flex-col gap-3">
      <div className="flex items-center justify-between pb-2 border-b border-[#262932]">
        <div>
          <h3 className="text-sm font-semibold text-[#ECEDF0] flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-[#5b8cff]" />
            <span>Evidence used</span>
          </h3>
          <p className="text-[11px] text-[#9AA0AE]">
            Your strongest matched evidence for this scholarship
          </p>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#262932] text-[#ECEDF0]">
          {selectedEdges.length} selected
        </span>
      </div>

      <div className="text-[11px] text-[#9AA0AE] italic">
        Chosen automatically by the agent and checked by the Verifier.
      </div>

      {loading ? (
        <div className="space-y-2 py-2">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : selectedEdges.length > 0 ? (
        <div className="flex flex-col gap-2.5">
          {selectedEdges.map((edge) => (
            <EdgeCard key={edge.id} edge={edge} factsMap={factsMap} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-[#9AA0AE] py-3 text-center italic">
          No edges selected for this application yet.
        </p>
      )}
    </div>
  );
}
