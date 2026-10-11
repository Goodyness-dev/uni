import { AlertCircle, RefreshCw } from "lucide-react";

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorBanner({ message, onRetry, className = "" }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className={`p-3.5 rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171]/40 flex items-center justify-between gap-3 text-xs text-[#F87171] ${className}`}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <AlertCircle className="w-4 h-4 shrink-0 text-[#F87171]" />
        <span className="leading-relaxed">{message}</span>
      </div>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#F87171]/20 hover:bg-[#F87171]/30 text-[#F87171] font-medium transition-colors shrink-0 cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}
