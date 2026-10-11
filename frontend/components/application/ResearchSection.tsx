"use client";

import { Search, AlertTriangle } from "lucide-react";
import { Dossier } from "@/lib/types";
import { DossierFactRow } from "@/components/DossierFactRow";
import { Skeleton } from "@/components/Skeleton";

interface ResearchSectionProps {
  dossier: Dossier | null;
  loading?: boolean;
}

export function ResearchSection({ dossier, loading = false }: ResearchSectionProps) {
  const facts = dossier?.facts || [];

  return (
    <div className="p-4 rounded-xl bg-[#181A20] border border-[#262932] flex flex-col gap-3">
      <div className="flex items-center justify-between pb-2 border-b border-[#262932]">
        <div>
          <h3 className="text-sm font-semibold text-[#ECEDF0] flex items-center gap-1.5">
            <Search className="w-4 h-4 text-[#F5A25D]" />
            <span>Research (Dossier)</span>
          </h3>
          <p className="text-[11px] text-[#9AA0AE]">
            Verified public facts retrieved about this scholarship
          </p>
        </div>
        {facts.length > 0 && (
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#262932] text-[#ECEDF0]">
            {facts.length} facts
          </span>
        )}
      </div>

      {/* Degraded warning */}
      {dossier?.degraded && (
        <div className="p-3 rounded-lg bg-[rgba(245,165,36,0.12)] border border-[#ffb957]/30 flex items-start gap-2 text-xs text-[#ffb957]">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            We could not reach the programme pages, so no school-specific claims were made.
          </span>
        </div>
      )}

      {loading ? (
        <div className="space-y-2 py-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : facts.length > 0 ? (
        <div className="flex flex-col gap-2 max-h-96 overflow-y-auto pr-1">
          {facts.map((fact) => (
            <DossierFactRow key={fact.id} fact={fact} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-[#9AA0AE] py-3 text-center italic">
          No research dossier facts recorded yet.
        </p>
      )}
    </div>
  );
}
