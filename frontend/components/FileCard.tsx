import { FileText, Download } from "lucide-react";

interface FileCardProps {
  name: string;
  type?: "pdf" | "markdown" | "checklist" | "file";
  size?: string;
  url?: string;
  className?: string;
}

export function FileCard({
  name,
  type = "file",
  size,
  url,
  className = "",
}: FileCardProps) {
  const iconColor =
    type === "pdf"
      ? "text-[#7AA2FF]"
      : type === "checklist"
      ? "text-[#49e095]"
      : "text-[#B794F6]";
  return (
    <div
      className={`p-3 rounded-lg bg-[#181A20] border border-[#262932] hover:border-[#353945] transition-colors flex items-center justify-between gap-3 ${className}`}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <div className={`w-8 h-8 rounded bg-[#262932] flex items-center justify-center ${iconColor} shrink-0`}>
          <FileText className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium text-[#ECEDF0] truncate" title={name}>
            {name}
          </p>
          {size && (
            <p className="text-[11px] font-mono text-[#9AA0AE]">{size}</p>
          )}
        </div>
      </div>

      {url ? (
        <a
          href={url}
          download
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#262932] hover:bg-[#353945] text-xs font-medium text-[#ECEDF0] transition-colors shrink-0 cursor-pointer"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Download</span>
        </a>
      ) : (
        <button
          type="button"
          disabled
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#181A20] text-xs font-medium text-[#626877] border border-[#262932] opacity-50 shrink-0 cursor-not-allowed"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Ready</span>
        </button>
      )}
    </div>
  );
}
