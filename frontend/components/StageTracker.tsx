import { Check, Hourglass, AlertCircle } from "lucide-react";

const STAGES = [
  { index: 1, name: "Match" },
  { index: 2, name: "Research" },
  { index: 3, name: "Evidence" },
  { index: 4, name: "Write" },
  { index: 5, name: "Verify" },
  { index: 6, name: "Apply" },
];

interface StageTrackerProps {
  currentStage: number; // 1 to 6
  isCompleted?: boolean;
  isFailed?: boolean;
  className?: string;
}

export function StageTracker({
  currentStage,
  isCompleted = false,
  isFailed = false,
  className = "",
}: StageTrackerProps) {
  return (
    <div
      className={`grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 ${className}`}
    >
      {STAGES.map((stage) => {
        const isDone = isCompleted || stage.index < currentStage;
        const isActive = !isCompleted && stage.index === currentStage;

        if (isDone) {
          return (
            <div
              key={stage.index}
              className="flex items-center gap-2 p-2 rounded bg-[#181A20] border border-[#262932]"
            >
              <div className="w-5 h-5 rounded-full bg-[rgba(61,214,140,0.12)] flex items-center justify-center text-[#49e095] shrink-0">
                <Check className="w-3.5 h-3.5 stroke-[2.5]" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-[#ECEDF0] truncate">
                  {stage.index}. {stage.name}
                </p>
                <p className="text-[11px] font-mono text-[#49e095]">Complete</p>
              </div>
            </div>
          );
        }

        if (isActive) {
          if (isFailed) {
            return (
              <div
                key={stage.index}
                className="flex items-center gap-2 p-2 rounded bg-[#181A20] border border-[#F87171]/40"
              >
                <div className="w-5 h-5 rounded-full bg-[rgba(248,113,113,0.12)] flex items-center justify-center text-[#F87171] shrink-0">
                  <AlertCircle className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-[#F87171] truncate">
                    {stage.index}. {stage.name}
                  </p>
                  <p className="text-[11px] font-mono text-[#F87171]">Failed</p>
                </div>
              </div>
            );
          }

          return (
            <div
              key={stage.index}
              className="flex items-center gap-2 p-2 rounded bg-[#181A20] border border-[#5b8cff]/50 shadow-sm shadow-[#5b8cff]/10"
            >
              <div className="w-5 h-5 rounded-full bg-[rgba(91,140,255,0.15)] flex items-center justify-center text-[#b2c5ff] shrink-0">
                <span className="w-2 h-2 rounded-full bg-[#5b8cff] animate-ping" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-[#b2c5ff] truncate">
                  {stage.index}. {stage.name}
                </p>
                <p className="text-[11px] font-mono text-[#5b8cff]">In Progress</p>
              </div>
            </div>
          );
        }

        // Upcoming
        return (
          <div
            key={stage.index}
            className="flex items-center gap-2 p-2 rounded bg-[#181A20]/50 border border-[#262932] opacity-60"
          >
            <div className="w-5 h-5 rounded-full bg-[#181A20] flex items-center justify-center text-[#626877] shrink-0">
              <Hourglass className="w-3 h-3" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-[#9AA0AE] truncate">
                {stage.index}. {stage.name}
              </p>
              <p className="text-[11px] font-mono text-[#626877]">Upcoming</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
