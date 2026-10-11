"use client";

import { useState } from "react";
import { History, Bell, ChevronDown, ChevronUp, CheckCircle, Clock } from "lucide-react";
import { AppEvent } from "@/lib/types";
import { TimelineItem } from "@/components/TimelineItem";
import { Skeleton } from "@/components/Skeleton";

interface TimelineSectionProps {
  timeline: AppEvent[];
  notifications?: { at: string; text: string; sent: boolean }[];
  loading?: boolean;
}

export function TimelineSection({
  timeline = [],
  notifications = [],
  loading = false,
}: TimelineSectionProps) {
  const [showNotifications, setShowNotifications] = useState<boolean>(false);

  return (
    <div className="p-4 rounded-xl bg-[#181A20] border border-[#262932] flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-[#262932]">
        <div>
          <h3 className="text-sm font-semibold text-[#ECEDF0] flex items-center gap-1.5">
            <History className="w-4 h-4 text-[#7AA2FF]" />
            <span>Application Timeline</span>
          </h3>
          <p className="text-[11px] text-[#9AA0AE]">
            Lifecycle execution trace & recovery logs
          </p>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#262932] text-[#ECEDF0]">
          {timeline.length} events
        </span>
      </div>

      {/* Collapsible Notifications Sent */}
      {notifications.length > 0 && (
        <div className="p-3 rounded-lg bg-[#14171F] border border-[#262932] flex flex-col gap-2">
          <button
            type="button"
            onClick={() => setShowNotifications(!showNotifications)}
            className="flex items-center justify-between text-xs text-[#ECEDF0] font-medium hover:text-[#7AA2FF] transition-colors"
          >
            <span className="flex items-center gap-2">
              <Bell className="w-3.5 h-3.5 text-[#ffb957]" />
              <span>Notifications sent ({notifications.length})</span>
            </span>
            {showNotifications ? (
              <ChevronUp className="w-4 h-4 text-[#9AA0AE]" />
            ) : (
              <ChevronDown className="w-4 h-4 text-[#9AA0AE]" />
            )}
          </button>

          {showNotifications && (
            <div className="mt-2 space-y-2 border-t border-[#262932] pt-2">
              {notifications.map((notif, idx) => (
                <div
                  key={idx}
                  className="flex items-start justify-between gap-2 p-2 rounded bg-[#181A20] text-xs"
                >
                  <div className="min-w-0">
                    <p className="text-[#ECEDF0] text-[11px]">{notif.text}</p>
                    <span className="text-[10px] font-mono text-[#9AA0AE] flex items-center gap-1 mt-0.5">
                      <Clock className="w-3 h-3" />
                      <span>{notif.at}</span>
                    </span>
                  </div>
                  <span
                    className={`shrink-0 inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded ${
                      notif.sent
                        ? "bg-[rgba(61,214,140,0.12)] text-[#49e095]"
                        : "bg-[rgba(245,165,36,0.12)] text-[#ffb957]"
                    }`}
                  >
                    <CheckCircle className="w-3 h-3" />
                    <span>{notif.sent ? "Sent" : "Pending"}</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Events Stream */}
      {loading ? (
        <div className="space-y-2 py-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : timeline.length > 0 ? (
        <div className="flex flex-col gap-2 max-h-96 overflow-y-auto pr-1">
          {timeline.map((event) => (
            <TimelineItem key={event.event_no} event={event} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-[#9AA0AE] py-3 text-center italic">
          No events recorded for this application yet.
        </p>
      )}
    </div>
  );
}
