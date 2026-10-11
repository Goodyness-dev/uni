"use client";

import { useState } from "react";
import { Lightbulb, Check, Loader2 } from "lucide-react";
import { Gap } from "@/lib/types";
import { answerGap } from "@/lib/api";

interface GapQuestionCardProps {
  gaps: Gap[];
  onGapAnswered?: (gapId: string) => void;
}

export function GapQuestionCard({ gaps, onGapAnswered }: GapQuestionCardProps) {
  // Only display unanswered gaps
  const activeGaps = gaps.filter((g) => !g.answered);

  if (activeGaps.length === 0) return null;

  return (
    <div className="space-y-4">
      {activeGaps.map((gap) => (
        <SingleGapCard
          key={gap.id}
          gap={gap}
          onSuccess={() => onGapAnswered?.(gap.id)}
        />
      ))}
    </div>
  );
}

function SingleGapCard({
  gap,
  onSuccess,
}: {
  gap: Gap;
  onSuccess: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim() || saving) return;

    setSaving(true);
    setError(null);
    try {
      await answerGap(gap.id, answer.trim());
      setSaved(true);
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save answer";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="bg-[#121318] rounded-xl border border-[#5FD3A0]/30 p-5 bg-[rgba(95,211,160,0.02)]">
      <div className="flex items-center gap-2 mb-1.5">
        <Lightbulb className="w-4 h-4 text-[#5FD3A0]" />
        <span className="text-[11px] font-mono text-[#5FD3A0] uppercase tracking-wider font-semibold">
          Optional Evidence Discovery
        </span>
      </div>

      <h3 className="text-base font-semibold text-[#ECEDF0] mb-1">
        Help the agent find more evidence
      </h3>
      <p className="text-xs text-[#9AA0AE] mb-3 leading-relaxed">
        {gap.question}
      </p>

      {saved ? (
        <div className="flex items-center gap-2 text-xs font-mono text-[#49e095] bg-[rgba(61,214,140,0.1)] p-2.5 rounded-lg border border-[#49e095]/30">
          <Check className="w-4 h-4" />
          <span>Evidence saved to personal file and queued for agents.</span>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            disabled={saving}
            placeholder="e.g. Contributed to open-source repository, served as university rep..."
            className="flex-1 h-10 px-3 rounded-lg bg-[#181A20] border border-[#262932] text-[#ECEDF0] text-xs placeholder:text-[#626877] focus:outline-none focus:border-[#5b8cff] transition-colors"
          />
          <button
            type="submit"
            disabled={saving || !answer.trim()}
            className="h-10 px-4 rounded-lg bg-[#181A20] hover:bg-[#292a2d] text-[#ECEDF0] border border-[#262932] hover:border-[#353945] text-xs font-medium whitespace-nowrap transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-[#5FD3A0]" />
                <span>Saving...</span>
              </>
            ) : (
              <span>Save to personal file</span>
            )}
          </button>
        </form>
      )}

      {error && (
        <p className="text-xs text-[#F87171] font-mono mt-2">{error}</p>
      )}
    </section>
  );
}
