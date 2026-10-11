interface StatTileProps {
  value: string | number;
  label: string;
  subtext?: string;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
  className?: string;
}

export function StatTile({
  value,
  label,
  subtext,
  tone = "neutral",
  className = "",
}: StatTileProps) {
  let valueColor = "text-[#ECEDF0]";
  let borderClass = "border-[#262932]";

  if (tone === "success") {
    valueColor = "text-[#49e095]";
    borderClass = "border-[#49e095]/30";
  } else if (tone === "warning") {
    valueColor = "text-[#ffb957]";
    borderClass = "border-[#ffb957]/30";
  } else if (tone === "danger") {
    valueColor = "text-[#F87171]";
    borderClass = "border-[#F87171]/30";
  } else if (tone === "info") {
    valueColor = "text-[#b2c5ff]";
    borderClass = "border-[#5b8cff]/30";
  }

  return (
    <div
      className={`p-3 rounded-lg bg-[#181A20] border ${borderClass} flex flex-col gap-1 ${className}`}
    >
      <span className="text-[11px] font-mono uppercase tracking-wider text-[#9AA0AE]">
        {label}
      </span>
      <span className={`text-2xl font-mono font-bold tracking-tight ${valueColor}`}>
        {value}
      </span>
      {subtext && (
        <span className="text-[11px] text-[#9AA0AE]">
          {subtext}
        </span>
      )}
    </div>
  );
}
