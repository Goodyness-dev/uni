"use client";

import { useEffect } from "react";
import { CheckCircle, AlertTriangle, AlertCircle, Info, X } from "lucide-react";

export type ToastTone = "success" | "warning" | "danger" | "info";

export interface ToastProps {
  id?: string;
  message: string;
  tone?: ToastTone;
  onDismiss?: () => void;
  durationMs?: number;
  className?: string;
}

export function Toast({
  message,
  tone = "info",
  onDismiss,
  durationMs = 4000,
  className = "",
}: ToastProps) {
  useEffect(() => {
    if (!durationMs || !onDismiss) return;
    const timer = setTimeout(() => {
      onDismiss();
    }, durationMs);
    return () => clearTimeout(timer);
  }, [durationMs, onDismiss]);

  const toneConfig = {
    success: {
      border: "border-[#49e095]/40",
      bg: "bg-[#181A20]",
      icon: <CheckCircle className="w-4 h-4 text-[#49e095]" />,
    },
    warning: {
      border: "border-[#ffb957]/40",
      bg: "bg-[#181A20]",
      icon: <AlertTriangle className="w-4 h-4 text-[#ffb957]" />,
    },
    danger: {
      border: "border-[#F87171]/40",
      bg: "bg-[#181A20]",
      icon: <AlertCircle className="w-4 h-4 text-[#F87171]" />,
    },
    info: {
      border: "border-[#5b8cff]/40",
      bg: "bg-[#181A20]",
      icon: <Info className="w-4 h-4 text-[#b2c5ff]" />,
    },
  }[tone];

  return (
    <div
      role="status"
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 rounded-lg border shadow-2xl transition-all ${toneConfig.bg} ${toneConfig.border} ${className}`}
    >
      {toneConfig.icon}
      <span className="text-xs text-[#ECEDF0] leading-snug max-w-xs">{message}</span>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="ml-2 p-0.5 rounded text-[#9AA0AE] hover:text-[#ECEDF0] transition-colors"
          aria-label="Dismiss toast"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
