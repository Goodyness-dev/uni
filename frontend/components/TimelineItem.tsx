import {
  Search,
  PenTool,
  ShieldCheck,
  Send,
  Cpu,
  RefreshCw,
  GitBranch,
  Clock,
  Sparkles,
} from "lucide-react";
import { AppEvent } from "../lib/types";
import { formatTime } from "../lib/format";

interface TimelineItemProps {
  event: AppEvent;
  className?: string;
}

export function TimelineItem({ event, className = "" }: TimelineItemProps) {
  const isRecovery =
    event.type === "recovery_decision" ||
    event.message.toLowerCase().includes("retry") ||
    event.message.toLowerCase().includes("fallback") ||
    event.message.toLowerCase().includes("switched to") ||
    event.message.toLowerCase().includes("handoff");

  const isWarning =
    event.type === "warning" ||
    event.type === "error" ||
    event.message.toLowerCase().includes("blocked") ||
    event.message.toLowerCase().includes("captcha");

  const isSuccess =
    event.type === "submitted" ||
    event.type === "confirmed" ||
    event.message.toLowerCase().includes("submitted") ||
    event.message.toLowerCase().includes("verified");

  const renderAgentIcon = (agentName?: string) => {
    const name = agentName?.toLowerCase() || "";
    if (name.includes("research")) return <Search className="w-3.5 h-3.5" />;
    if (name.includes("match")) return <Sparkles className="w-3.5 h-3.5" />;
    if (name.includes("edge") || name.includes("evidence"))
      return <GitBranch className="w-3.5 h-3.5" />;
    if (name.includes("writ") || name.includes("tailor"))
      return <PenTool className="w-3.5 h-3.5" />;
    if (name.includes("verif")) return <ShieldCheck className="w-3.5 h-3.5" />;
    if (name.includes("submit") || name.includes("apply"))
      return <Send className="w-3.5 h-3.5" />;
    return <Cpu className="w-3.5 h-3.5" />;
  };

  const formattedTime = formatTime(event.at);

  // Dedicated Card for Recovery Decisions
  if (isRecovery) {
    const trigger = typeof event.data?.trigger === "string" ? event.data.trigger : undefined;
    const chosen = typeof event.data?.chosen === "string" ? event.data.chosen : undefined;
    const reason = typeof event.data?.reason === "string" ? event.data.reason : undefined;

    return (
      <div
        className={`p-3 rounded-lg bg-[rgba(245,165,36,0.08)] border border-[#ffb957]/30 flex flex-col gap-1.5 ${className}`}
      >
        <div className="flex items-center justify-between text-[11px] font-mono text-[#ffb957]">
          <div className="flex items-center gap-1.5 font-semibold">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            <span className="uppercase tracking-wider">Recovery Decision</span>
          </div>
          <span className="text-[#9AA0AE] flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formattedTime}
          </span>
        </div>
        <p className="text-xs text-[#ECEDF0] leading-relaxed">
          {event.message}
        </p>
        {(trigger || chosen || reason) && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 text-[11px] font-mono border-t border-[#ffb957]/20 mt-1">
            {trigger && (
              <div className="bg-[#181A20] p-1.5 rounded border border-[#262932]">
                <span className="text-[#9AA0AE] block text-[10px]">Trigger:</span>
                <span className="text-[#F87171]">{trigger}</span>
              </div>
            )}
            {chosen && (
              <div className="bg-[#181A20] p-1.5 rounded border border-[#262932]">
                <span className="text-[#9AA0AE] block text-[10px]">Chosen:</span>
                <span className="text-[#49e095]">{chosen}</span>
              </div>
            )}
            {reason && (
              <div className="bg-[#181A20] p-1.5 rounded border border-[#262932]">
                <span className="text-[#9AA0AE] block text-[10px]">Reason:</span>
                <span className="text-[#ffb957]">{reason}</span>
              </div>
            )}
          </div>
        )}
        {event.agent && (
          <span className="text-[10px] text-[#9AA0AE] font-mono">
            Triggered by: {event.agent}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      className={`flex items-start gap-3 p-2.5 rounded-lg transition-colors hover:bg-[#181A20] ${
        isWarning
          ? "border-l-2 border-[#ffb957] bg-[rgba(245,165,36,0.04)]"
          : isSuccess
          ? "border-l-2 border-[#49e095] bg-[rgba(61,214,140,0.04)]"
          : "border-l-2 border-[#262932]"
      } ${className}`}
    >
      {/* Agent Icon Badge */}
      <div
        className={`w-6 h-6 rounded-full shrink-0 flex items-center justify-center ${
          isWarning
            ? "bg-[rgba(245,165,36,0.15)] text-[#ffb957]"
            : isSuccess
            ? "bg-[rgba(61,214,140,0.15)] text-[#49e095]"
            : "bg-[#181A20] border border-[#262932] text-[#9AA0AE]"
        }`}
        title={event.agent || "Agent"}
      >
        {renderAgentIcon(event.agent)}
      </div>

      {/* Message & Meta */}
      <div className="flex-1 min-w-0 flex flex-col gap-0.5">
        <div className="flex items-center justify-between text-[11px] text-[#9AA0AE]">
          <span className="font-medium text-[#ECEDF0] truncate">
            {event.agent || "System"}
          </span>
          <span className="font-mono text-[10px] text-[#9AA0AE] shrink-0">
            {formattedTime}
          </span>
        </div>
        <p className="text-xs text-[#ECEDF0] leading-relaxed">
          {event.message}
        </p>
      </div>
    </div>
  );
}
