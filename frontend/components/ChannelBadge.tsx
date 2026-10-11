import { Mail, Globe, ShieldAlert, Package } from "lucide-react";
import { Channel } from "../lib/types";
import { channelLabel } from "../lib/status";

interface ChannelBadgeProps {
  channel: Channel;
  className?: string;
}

export function ChannelBadge({ channel, className = "" }: ChannelBadgeProps) {
  const label = channelLabel(channel);

  const renderIcon = () => {
    switch (channel) {
      case "email":
        return <Mail className="w-3.5 h-3.5 text-[#7AA2FF]" />;
      case "portal_form":
        return <Globe className="w-3.5 h-3.5 text-[#49e095]" />;
      case "portal_captcha":
        return <ShieldAlert className="w-3.5 h-3.5 text-[#ffb957]" />;
      case "package_only":
        return <Package className="w-3.5 h-3.5 text-[#B794F6]" />;
    }
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#181A20] border border-[#262932] text-xs font-mono text-[#9AA0AE] ${className}`}
    >
      {renderIcon()}
      <span>{label}</span>
    </span>
  );
}
