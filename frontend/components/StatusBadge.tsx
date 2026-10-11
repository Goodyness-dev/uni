import { Check } from "lucide-react";
import { AppStatus } from "../lib/types";
import { statusMeta, StatusTone } from "../lib/status";

interface StatusBadgeProps {
  status: AppStatus;
  reason?: string | null;
  className?: string;
}

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "bg-[#181A20] text-[#9AA0AE] border-[#262932]",
  info: "bg-[#5b8cff]/15 text-[#b2c5ff] border-[#5b8cff]/30",
  success: "bg-[rgba(61,214,140,0.12)] text-[#49e095] border-[#49e095]/30",
  "success-outline": "bg-transparent text-[#49e095] border-[#49e095]/50",
  warning: "bg-[rgba(245,165,36,0.15)] text-[#ffb957] border-[#ffb957]/40",
  danger: "bg-[rgba(248,113,113,0.12)] text-[#F87171] border-[#F87171]/30",
};

export function StatusBadge({ status, reason, className = "" }: StatusBadgeProps) {
  const meta = statusMeta(status);
  const toneClass = TONE_CLASSES[meta.tone];

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${toneClass} ${className}`}
        title={reason ?? undefined}
      >
        {meta.hasCheck && <Check className="w-3.5 h-3.5 shrink-0" />}
        {meta.hasDot && (
          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse shrink-0" />
        )}
        {meta.pulseDot && (
          <span className="w-1.5 h-1.5 rounded-full bg-[#ffb957] animate-ping shrink-0" />
        )}
        <span>{meta.label}</span>
      </span>
      {reason && status === "skipped" && (
        <span className="text-[11px] text-[#9AA0AE] pl-1 font-sans">
          {reason}
        </span>
      )}
    </div>
  );
}
