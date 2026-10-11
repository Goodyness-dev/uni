import { ReactNode } from "react";
import { FolderOpen } from "lucide-react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`p-8 rounded-xl bg-[#181A20] border border-[#262932] flex flex-col items-center justify-center text-center max-w-md mx-auto ${className}`}
    >
      <div className="w-12 h-12 rounded-full bg-[#262932] flex items-center justify-center text-[#9AA0AE] mb-3">
        {icon || <FolderOpen className="w-6 h-6" />}
      </div>
      <h3 className="text-base font-semibold text-[#ECEDF0] mb-1">
        {title}
      </h3>
      <p className="text-xs text-[#9AA0AE] leading-relaxed mb-4">
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
}
