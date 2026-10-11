"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Fact, Preferences, IntakeRequest } from "../lib/types";
import { api, ApiError } from "../lib/api";
import { DocumentsCard } from "../components/profile/DocumentsCard";
import { PreferencesCard } from "../components/profile/PreferencesCard";
import { VaultCard } from "../components/profile/VaultCard";
import { ParsedFactsCard } from "../components/profile/ParsedFactsCard";
import { StickyActionBar } from "../components/profile/StickyActionBar";
import { ErrorBanner } from "../components/ErrorBanner";
import { Toast } from "../components/Toast";
import { Sparkles, Loader2, AlertCircle } from "lucide-react";

const INITIAL_PREFERENCES: Preferences = {
  full_name: "",
  email: "",
  level: "masters",
  fields: [],
  countries: [],
  funding: "full",
  start_year: 2026,
  nationality: "",
  gpa: 0,
  gpa_scale: 5.0,
  sensitive_consent: false,
};

export default function ProfilePage() {
  const router = useRouter();

  // Documents state
  const [cvText, setCvText] = useState("");
  const [cvPdfBase64, setCvPdfBase64] = useState<string | null>(null);
  const [cvFileName, setCvFileName] = useState<string | null>(null);
  const [cvFileSize, setCvFileSize] = useState<string | null>(null);
  const [transcriptText, setTranscriptText] = useState("");
  const [transcriptFileName, setTranscriptFileName] = useState<string | null>(null);

  // Preferences state
  const [preferences, setPreferences] = useState<Preferences>(INITIAL_PREFERENCES);

  // Vault state
  const [vaultSections, setVaultSections] = useState<Record<string, string>>({});
  const [vaultText, setVaultText] = useState("");

  // Facts & Intake state
  const [facts, setFacts] = useState<Fact[]>([]);
  const [counts, setCounts] = useState<{ cv: number; transcript: number; vault: number }>({
    cv: 0,
    transcript: 0,
    vault: 0,
  });

  // UI status
  const [intakeLoading, setIntakeLoading] = useState(false);
  const [runLoading, setRunLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [conflictWarning, setConflictWarning] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Load Demo Persona Callback
  const handleLoadDemo = useCallback(async () => {
    try {
      setIntakeLoading(true);
      setErrorMsg(null);
      const intakeRes = await api.loadDemo();
      const factsRes = await api.getFacts();

      if (factsRes.preferences) {
        setPreferences({
          ...factsRes.preferences,
          countries: factsRes.preferences.countries.map((c) =>
            c === "UK" ? "United Kingdom" : c
          ),
        });
      }

      setCvFileName("Tobi_Adeyemi_CV_2025.pdf");
      setCvFileSize("142 KB");
      setCvPdfBase64("MOCK_PDF_BASE64_TOKEN");
      setCvText(
        "BSc Computer Engineering, Fictional State University, CGPA 4.30/5.00. Embedded Systems Intern, BrightGrid Solar. Final year capstone: SunTrack low-cost solar monitoring."
      );
      setTranscriptFileName("Official_Transcript_BSc.pdf");
      setTranscriptText(
        "Digital Electronics: Grade A\nEmbedded Systems: Grade A\nData Structures and Algorithms: Grade A\nPower Systems: Grade A\nMachine Learning: Grade B\nFinal Year Project: Grade A"
      );

      setVaultSections({
        sports: "Captained the FSU football team for 2 seasons. Played for FSU university football team for 4 years.",
        volunteering: "Volunteered as a coding teacher at Community Secondary School. Taught Python to 40 students over 200 hours across 2 years.",
        certifications: "Python for Data Science certificate, 2023. Embedded Systems Fundamentals certificate, 2022. First aid certificate, 2022.",
        leadership: "Organized the FSU campus hackathon with 120 participants. Assistant coordinator of the FSU Tech Club 2023-2024.",
        awards: "Dean's list for 2 sessions. Departmental prize for best final year project in 2025.",
        projects: "SunTrack: low cost solar panel monitoring system built with ESP32 microcontroller and wireless sensors. SunTrack web telemetry dashboard in Python.",
        languages: "English (Fluent), Yoruba (Native), basic French.",
        hardships: "Family income was too low to pay full fees in second year, so tutored students on weekends to cover costs.",
        career_goals: "Goal: design low-cost energy monitoring systems that help small businesses in Nigeria use solar power reliably.",
        why_abroad: "Wants a Master's in AI for energy systems because leading research groups on energy forecasting and smart grids are abroad.",
      });

      setFacts(intakeRes.facts || factsRes.facts);
      setCounts(
        intakeRes.counts || {
          cv: (factsRes.facts || []).filter((f) => f.source === "cv").length,
          transcript: (factsRes.facts || []).filter((f) => f.source === "transcript").length,
          vault: (factsRes.facts || []).filter((f) => f.source === "vault").length,
        }
      );

      setToastMessage("Demo persona (Tobi Adeyemi) loaded successfully with 14 ground-truth facts.");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load demo persona");
    } finally {
      setIntakeLoading(false);
    }
  }, []);

  // Window event listener for TopBar "Load demo persona" button
  useEffect(() => {
    const onDemoTrigger = () => {
      handleLoadDemo();
    };
    window.addEventListener("load-demo-persona", onDemoTrigger);
    return () => {
      window.removeEventListener("load-demo-persona", onDemoTrigger);
    };
  }, [handleLoadDemo]);

  // Process / Ingest Documents & Vault
  const handleProcessIntake = async () => {
    try {
      setIntakeLoading(true);
      setErrorMsg(null);

      const req: IntakeRequest = {
        cv_text: cvText.trim() || undefined,
        cv_pdf_base64: cvPdfBase64 || undefined,
        transcript_text: transcriptText.trim() || undefined,
        preferences,
        vault_sections: vaultSections,
        vault_text: vaultText.trim() || undefined,
      };

      const res = await api.intake(req);
      setFacts(res.facts);
      setCounts(res.counts);
      setToastMessage(`Parsed ${res.facts.length} atomic provenance facts.`);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to parse documents");
    } finally {
      setIntakeLoading(false);
    }
  };

  // Patch Fact on blur
  const handlePatchFact = async (id: string, text: string) => {
    try {
      const updated = await api.patchFact(id, text);
      setFacts((prev) => prev.map((f) => (f.id === id ? updated : f)));
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : `Failed to save fact ${id}`);
    }
  };

  // Run Agent
  const handleRunAgent = async (mode: "A" | "B" | "Z", topN: number, liveResearch: boolean) => {
    try {
      setRunLoading(true);
      setErrorMsg(null);
      setConflictWarning(null);

      await api.startRun(mode, topN, liveResearch);
      router.push("/matches");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflictWarning("A pipeline run is already in progress.");
      } else {
        setErrorMsg(err instanceof Error ? err.message : "Failed to start agent run");
      }
    } finally {
      setRunLoading(false);
    }
  };

  return (
    <div className="max-w-[1100px] mx-auto px-4 md:px-6 pb-36 pt-4 flex flex-col gap-8">
      {/* Audit Context Banner */}
      <div className="w-full flex flex-col sm:flex-row sm:items-center justify-between py-2 px-4 rounded bg-[#121318] border border-[#262932] gap-2">
        <div className="flex items-center gap-2 text-xs font-mono text-[#9AA0AE]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#49e095]" />
          <span className="text-[#ECEDF0] font-medium">PROFILE VAULT</span>
          <span className="text-[#626877]">/</span>
          <span>INDEX STATUS: DETERMINISTIC PROVENANCE</span>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono text-[#626877]">
          <span>LATENCY: 12ms</span>
          <span>|</span>
          <span className="text-[#49e095]">STRICT TRUTH GUARD ON</span>
        </div>
      </div>

      {/* Error & Conflict Banners */}
      {errorMsg && (
        <ErrorBanner
          message={errorMsg}
          onRetry={() => setErrorMsg(null)}
        />
      )}

      {conflictWarning && (
        <div className="p-3.5 rounded-lg bg-[rgba(245,165,36,0.1)] border border-[#ffb957]/40 flex items-center justify-between text-xs text-[#ffb957]">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{conflictWarning}</span>
          </div>
          <Link
            href="/matches"
            className="px-3 py-1 rounded bg-[#ffb957]/20 hover:bg-[#ffb957]/30 text-[#ffb957] font-medium transition-colors"
          >
            View Active Matches →
          </Link>
        </div>
      )}

      {/* Card 1: Documents */}
      <DocumentsCard
        cvText={cvText}
        cvFileName={cvFileName}
        cvFileSize={cvFileSize}
        hasCvPdf={!!cvPdfBase64}
        transcriptText={transcriptText}
        transcriptFileName={transcriptFileName}
        onCvPdfChange={(base64, fileName, fileSize) => {
          setCvPdfBase64(base64);
          setCvFileName(fileName);
          setCvFileSize(fileSize);
        }}
        onCvTextChange={setCvText}
        onTranscriptTextChange={setTranscriptText}
      />

      {/* Card 2: Preferences */}
      <PreferencesCard
        preferences={preferences}
        onChange={setPreferences}
      />

      {/* Card 3: Profile Vault */}
      <VaultCard
        vaultSections={vaultSections}
        vaultText={vaultText}
        sensitiveConsent={preferences.sensitive_consent}
        onSectionsChange={setVaultSections}
        onVaultTextChange={setVaultText}
        onConsentChange={(consent) =>
          setPreferences((prev) => ({ ...prev, sensitive_consent: consent }))
        }
      />

      {/* Parse Ingestion Trigger (Visible if facts not yet extracted or updating) */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-[#121318] border border-[#262932]">
        <div>
          <h3 className="text-sm font-semibold text-[#ECEDF0]">Process Documents & Personal Vault</h3>
          <p className="text-xs text-[#9AA0AE] mt-0.5">
            Extract atomic facts with provenance links before initiating scholarship matching.
          </p>
        </div>
        <button
          type="button"
          onClick={handleProcessIntake}
          disabled={intakeLoading}
          className="px-4 py-2 rounded-lg bg-[#181A20] hover:bg-[#262932] border border-[#262932] hover:border-[#353945] text-xs font-medium text-[#ECEDF0] flex items-center gap-2 transition-all cursor-pointer disabled:opacity-50"
        >
          {intakeLoading ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Parsing Facts...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5 text-[#5b8cff]" />
              <span>{facts.length > 0 ? "Re-index Facts" : "Parse Facts"}</span>
            </>
          )}
        </button>
      </div>

      {/* Card 4: Parsed Facts (renders when facts exist) */}
      {facts.length > 0 && (
        <ParsedFactsCard
          facts={facts}
          counts={counts}
          onPatchFact={handlePatchFact}
        />
      )}

      {/* Sticky Action Bar */}
      <StickyActionBar
        factsCount={facts.length}
        onRunAgent={handleRunAgent}
        isRunning={runLoading}
        isDemoMode={true}
      />

      {/* Toast Notification */}
      {toastMessage && (
        <Toast
          message={toastMessage}
          tone="success"
          onDismiss={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
