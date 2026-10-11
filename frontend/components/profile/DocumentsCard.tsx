"use client";

import { useState, useRef, ChangeEvent, DragEvent } from "react";
import { FileText, Check, Upload, GraduationCap } from "lucide-react";

interface DocumentsCardProps {
  cvText: string;
  cvFileName: string | null;
  cvFileSize: string | null;
  hasCvPdf: boolean;
  transcriptText: string;
  transcriptFileName?: string | null;
  onCvPdfChange: (base64: string | null, fileName: string | null, fileSize: string | null) => void;
  onCvTextChange: (text: string) => void;
  onTranscriptTextChange: (text: string) => void;
  className?: string;
}

export function DocumentsCard({
  cvText,
  cvFileName,
  cvFileSize,
  hasCvPdf,
  transcriptText,
  transcriptFileName,
  onCvPdfChange,
  onCvTextChange,
  onTranscriptTextChange,
  className = "",
}: DocumentsCardProps) {
  const [cvMode, setCvMode] = useState<"file" | "text">("file");
  const [isDraggingCv, setIsDraggingCv] = useState(false);
  const cvFileInputRef = useRef<HTMLInputElement>(null);

  const handleCvFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please upload a PDF file.");
      return;
    }
    const sizeStr = `${(file.size / 1024).toFixed(0)} KB`;
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.includes(",") ? result.split(",")[1] : result;
      onCvPdfChange(base64, file.name, sizeStr);
    };
    reader.readAsDataURL(file);
  };

  const handleCvDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingCv(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleCvFile(e.dataTransfer.files[0]);
    }
  };

  const handleCvInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleCvFile(e.target.files[0]);
    }
  };

  const clearCvFile = () => {
    onCvPdfChange(null, null, null);
    if (cvFileInputRef.current) cvFileInputRef.current.value = "";
  };

  const ingestedCount = (hasCvPdf || cvText.trim().length > 0 ? 1 : 0) + (transcriptText.trim().length > 0 ? 1 : 0);

  return (
    <section className={`rounded-xl bg-[#121318] border border-[#262932] p-6 flex flex-col gap-6 ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between border-b border-[#262932] pb-4">
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[11px] font-mono uppercase text-[#626877]">Source Ingestion</span>
            <span className="text-[#626877]">•</span>
            <span className="text-[11px] font-mono text-[#7AA2FF]">Stage 01</span>
          </div>
          <h2 className="text-xl font-semibold tracking-tight text-[#ECEDF0]">Documents</h2>
          <p className="text-xs text-[#9AA0AE] mt-0.5">
            Raw unstructured inputs parsed into verifiable provenance records.
          </p>
        </div>
        <span className="px-2 py-0.5 rounded text-[11px] font-mono text-[#49e095] bg-[rgba(61,214,140,0.12)] border border-[#262932]">
          {ingestedCount} Ingested
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* CV Ingestion Box */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs">
            <label className="font-medium text-[#ECEDF0]">Curriculum Vitae (PDF)</label>
            <button
              type="button"
              onClick={() => setCvMode(cvMode === "file" ? "text" : "file")}
              className="text-[#9AA0AE] hover:text-[#ECEDF0] text-[11px] font-mono underline transition-colors cursor-pointer"
            >
              {cvMode === "file" ? "Paste text instead" : "Upload PDF instead"}
            </button>
          </div>

          {cvMode === "file" ? (
            hasCvPdf ? (
              <div className="rounded-lg bg-[#181A20] border border-[#262932] p-4 flex flex-col justify-between h-40">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded bg-[#121318] border border-[#262932] flex items-center justify-center text-[#7AA2FF]">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div className="flex flex-col min-w-0">
                      <span className="text-xs font-medium text-[#ECEDF0] truncate max-w-[180px]">
                        {cvFileName || "Uploaded_CV.pdf"}
                      </span>
                      <span className="text-[11px] font-mono text-[#9AA0AE]">
                        {cvFileSize || "PDF document"} • Base64 ready
                      </span>
                    </div>
                  </div>
                  <div className="w-6 h-6 rounded-full bg-[rgba(61,214,140,0.12)] border border-[#49e095]/30 flex items-center justify-center text-[#49e095]">
                    <Check className="w-4 h-4" />
                  </div>
                </div>
                <div className="flex items-center justify-between border-t border-[#262932] pt-2 text-[11px] font-mono">
                  <span className="text-[#626877]">Status: Loaded</span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => cvFileInputRef.current?.click()}
                      className="text-[#9AA0AE] hover:text-[#ECEDF0] transition-colors cursor-pointer"
                    >
                      Replace
                    </button>
                    <button
                      type="button"
                      onClick={clearCvFile}
                      className="text-[#F87171] hover:underline transition-colors cursor-pointer"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDraggingCv(true);
                }}
                onDragLeave={() => setIsDraggingCv(false)}
                onDrop={handleCvDrop}
                onClick={() => cvFileInputRef.current?.click()}
                className={`rounded-lg bg-[#181A20] border-2 border-dashed ${
                  isDraggingCv ? "border-[#7AA2FF] bg-[#7AA2FF]/5" : "border-[#262932] hover:border-[#353945]"
                } p-4 flex flex-col items-center justify-center h-40 text-center cursor-pointer transition-colors`}
              >
                <div className="w-10 h-10 rounded-full bg-[#262932] flex items-center justify-center text-[#7AA2FF] mb-2">
                  <Upload className="w-5 h-5" />
                </div>
                <p className="text-xs font-medium text-[#ECEDF0]">Drop your CV PDF here or click to browse</p>
                <p className="text-[11px] font-mono text-[#626877] mt-1">PDF format up to 5 MB</p>
                <input
                  ref={cvFileInputRef}
                  type="file"
                  accept="application/pdf"
                  onChange={handleCvInputChange}
                  className="hidden"
                />
              </div>
            )
          ) : (
            <div className="rounded-lg bg-[#181A20] border border-[#262932] p-2 flex flex-col h-40">
              <textarea
                value={cvText}
                onChange={(e) => onCvTextChange(e.target.value)}
                placeholder="Paste the full text of your CV here (education, experience, projects)..."
                className="w-full h-full bg-transparent border-none text-xs text-[#ECEDF0] placeholder-[#626877] focus:outline-none resize-none leading-relaxed p-1"
              />
              <div className="flex items-center justify-between border-t border-[#262932] pt-1 text-[11px] font-mono text-[#626877]">
                <span>{cvText.length} characters</span>
                {cvText.length > 0 && (
                  <span className="text-[#49e095] flex items-center gap-1">
                    <Check className="w-3 h-3" /> Ready
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Transcript Ingestion Box */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs">
            <label className="font-medium text-[#ECEDF0]">Academic Transcript</label>
            <span className="text-[11px] font-mono text-[#B794F6]">
              {transcriptFileName || (transcriptText.length > 0 ? "Course records detected" : "Text or units")}
            </span>
          </div>

          <div className="rounded-lg bg-[#181A20] border border-[#262932] p-2 flex flex-col h-40">
            <div className="flex items-center gap-2 pb-1.5 border-b border-[#262932] px-1 text-[11px] font-mono text-[#9AA0AE]">
              <GraduationCap className="w-3.5 h-3.5 text-[#B794F6]" />
              <span>Paste courses, grades and degrees</span>
            </div>
            <textarea
              value={transcriptText}
              onChange={(e) => onTranscriptTextChange(e.target.value)}
              placeholder="e.g.&#10;Digital Electronics: Grade A (4.0/4.0)&#10;Embedded Systems: Grade A (4.0/4.0)&#10;Computer Architecture: Grade B+&#10;Overall CGPA: 4.30 / 5.00"
              className="w-full flex-1 bg-transparent border-none text-xs text-[#ECEDF0] placeholder-[#626877] focus:outline-none resize-none leading-relaxed p-1.5 font-mono"
            />
            <div className="flex items-center justify-between border-t border-[#262932] pt-1 text-[11px] font-mono text-[#626877]">
              <span>{transcriptText.split("\n").filter((l) => l.trim().length > 0).length} lines entered</span>
              {transcriptText.trim().length > 0 && (
                <span className="text-[#49e095] flex items-center gap-1">
                  <Check className="w-3 h-3" /> Ready
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
