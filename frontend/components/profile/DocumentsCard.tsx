"use client";
import { useRef, useState } from "react";
import { FileText, Upload } from "lucide-react";

interface DocumentsCardProps {
  cvText: string; cvFileName: string | null; cvFileSize: string | null; hasCvPdf: boolean;
  transcriptText: string; transcriptFileName?: string | null; hasTranscriptPdf?: boolean;
  onCvPdfChange: (base64: string | null, fileName: string | null, fileSize: string | null) => void;
  onCvTextChange: (text: string) => void;
  onTranscriptTextChange: (text: string) => void;
  onTranscriptFileChange?: (base64: string | null, name: string | null) => void;
  className?: string;
}
export function DocumentsCard(props: DocumentsCardProps) {
  const cvInput = useRef<HTMLInputElement>(null);
  const transcriptInput = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState("");
  const load = async (file: File, kind: "cv" | "transcript") => {
    setError(""); setLoading(kind);
    try {
      const pdf = file.name.toLowerCase().endsWith(".pdf");
      if (!pdf && !file.name.toLowerCase().endsWith(".txt")) throw new Error("Choose a PDF or UTF-8 text file.");
      if (file.size > 5_000_000 || file.size === 0) throw new Error("Files must be nonempty and no larger than 5 MB.");
      if (pdf) {
        const base64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader(); reader.onerror = () => reject(new Error("The file could not be read."));
          reader.onload = () => resolve(String(reader.result).split(",")[1]); reader.readAsDataURL(file);
        });
        if (kind === "cv") { props.onCvTextChange(""); props.onCvPdfChange(base64, file.name, `${Math.ceil(file.size / 1024)} KB`); }
        else { props.onTranscriptTextChange(""); props.onTranscriptFileChange?.(base64, file.name); }
      } else {
        const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
        if (kind === "cv") { props.onCvPdfChange(null, file.name, `${Math.ceil(file.size / 1024)} KB`); props.onCvTextChange(text); }
        else { props.onTranscriptFileChange?.(null, file.name); props.onTranscriptTextChange(text); }
      }
    } catch (err) { setError(err instanceof Error ? err.message : "Upload could not be read."); }
    finally { setLoading(""); }
  };
  return <section className={`rounded-xl bg-[#121318] border border-[#262932] p-6 flex flex-col gap-4 ${props.className ?? ""}`}>
    <div><h2 className="text-xl text-[#ECEDF0] font-semibold">Documents</h2>
      <p className="text-xs text-[#9AA0AE]">Drop your CV and transcript. Extracted facts need source review before the agent uses them.</p></div>
    <div className="flex gap-4 text-xs text-[#7AA2FF]">
      <a href="/fixtures/tobi_cv.txt" download>Download fictional Tobi CV</a>
      <a href="/fixtures/tobi_transcript.txt" download>Download fictional Tobi transcript</a>
    </div>
    <div className="grid md:grid-cols-2 gap-4">{(["cv", "transcript"] as const).map(kind => {
      const input = kind === "cv" ? cvInput : transcriptInput;
      const name = kind === "cv" ? props.cvFileName : props.transcriptFileName;
      const text = kind === "cv" ? props.cvText : props.transcriptText;
      const isPdf = kind === "cv" ? props.hasCvPdf : props.hasTranscriptPdf;
      return <div key={kind} className="flex flex-col gap-2">
        <h3 className="text-sm text-[#ECEDF0]">{kind === "cv" ? "Curriculum Vitae" : "Academic Transcript"}</h3>
        <button type="button" disabled={!!loading} onClick={() => input.current?.click()}
          onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); const file = event.dataTransfer.files[0]; if (file) void load(file, kind); }}
          className="rounded-lg border-2 border-dashed border-[#262932] bg-[#181A20] p-5 text-xs text-[#9AA0AE] flex items-center justify-center gap-2">
          {name ? <FileText className="w-4 h-4" /> : <Upload className="w-4 h-4" />}
          {loading === kind ? "Reading file..." : name || "Drop PDF or text here, or choose a file"}
        </button>
        <input ref={input} type="file" aria-label={kind === "cv" ? "Upload CV file" : "Upload transcript file"} accept=".pdf,.txt" className="hidden"
          onChange={event => { const file = event.target.files?.[0]; if (file) void load(file, kind); event.target.value = ""; }} />
        {isPdf ? <p className="text-xs text-[#49e095]">PDF loaded. Text will be extracted by the backend.</p> :
          <textarea aria-label={kind === "cv" ? "CV source text" : "Transcript source text"} value={text} placeholder="Or paste your source text"
            onChange={event => kind === "cv" ? props.onCvTextChange(event.target.value) : props.onTranscriptTextChange(event.target.value)}
            className="h-32 rounded bg-[#181A20] border border-[#262932] p-3 text-xs text-[#ECEDF0]" />}
        {name && <button type="button" className="text-xs text-red-300 self-start" onClick={() => {
          if (kind === "cv") { props.onCvPdfChange(null, null, null); props.onCvTextChange(""); }
          else { props.onTranscriptFileChange?.(null, null); props.onTranscriptTextChange(""); }
        }}>Remove file</button>}
      </div>;
    })}</div>
    {error && <p role="alert" className="text-xs text-red-300">{error}</p>}
  </section>;
}
