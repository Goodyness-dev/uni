interface FitScoreProps {
  score: number; // 0 to 100
  variant?: "ring" | "bar";
  size?: "sm" | "md" | "lg";
  className?: string;
  showLabel?: boolean;
}

export function FitScore({
  score,
  variant = "ring",
  size = "md",
  className = "",
  showLabel = false,
}: FitScoreProps) {
  const clampedScore = Math.max(0, Math.min(100, Math.round(score)));

  let colorText = "text-[#9AA0AE]";
  let colorStroke = "#9AA0AE";
  let colorBg = "#181A20";

  if (clampedScore >= 75) {
    colorText = "text-[#49e095]";
    colorStroke = "#49e095";
    colorBg = "rgba(61, 214, 140, 0.12)";
  } else if (clampedScore >= 50) {
    colorText = "text-[#ffb957]";
    colorStroke = "#ffb957";
    colorBg = "rgba(245, 165, 36, 0.12)";
  }

  if (variant === "bar") {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className="flex-1 h-2 rounded-full bg-[#181A20] overflow-hidden border border-[#262932]">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{
              width: `${clampedScore}%`,
              backgroundColor: colorStroke,
            }}
          />
        </div>
        <span className={`text-xs font-mono font-medium ${colorText}`}>
          {clampedScore}%
        </span>
      </div>
    );
  }

  // Ring variant sizes
  const dimensions = {
    sm: { size: 36, stroke: 3, radius: 14, text: "text-[11px]" },
    md: { size: 48, stroke: 4, radius: 19, text: "text-xs" },
    lg: { size: 64, stroke: 5, radius: 26, text: "text-sm" },
  }[size];

  const circumference = 2 * Math.PI * dimensions.radius;
  const strokeDashoffset = circumference - (clampedScore / 100) * circumference;

  return (
    <div className={`inline-flex flex-col items-center gap-1 ${className}`}>
      <div
        className="relative flex items-center justify-center shrink-0 rounded-full"
        style={{ width: dimensions.size, height: dimensions.size, backgroundColor: colorBg }}
      >
        <svg
          width={dimensions.size}
          height={dimensions.size}
          className="transform -rotate-90"
        >
          {/* Background circle */}
          <circle
            cx={dimensions.size / 2}
            cy={dimensions.size / 2}
            r={dimensions.radius}
            stroke="#262932"
            strokeWidth={dimensions.stroke}
            fill="transparent"
          />
          {/* Progress circle */}
          <circle
            cx={dimensions.size / 2}
            cy={dimensions.size / 2}
            r={dimensions.radius}
            stroke={colorStroke}
            strokeWidth={dimensions.stroke}
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-300"
          />
        </svg>
        <span
          className={`absolute font-mono font-semibold ${dimensions.text} ${colorText}`}
        >
          {clampedScore}
        </span>
      </div>
      {showLabel && (
        <span className="text-[10px] font-mono text-[#9AA0AE] uppercase tracking-wider">
          Fit
        </span>
      )}
    </div>
  );
}
