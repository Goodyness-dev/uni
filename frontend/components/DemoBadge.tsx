interface DemoBadgeProps {
  label?: string;
  className?: string;
}

export function DemoBadge({ label = "DEMO LISTING", className = "" }: DemoBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded bg-[#181A20] border border-[#262932] text-[10px] font-mono tracking-wider text-[#9AA0AE] uppercase select-none ${className}`}
    >
      {label}
    </span>
  );
}
