"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Check } from "lucide-react";

interface VaultCardProps {
  vaultSections: Record<string, string>;
  vaultText: string;
  sensitiveConsent: boolean;
  onSectionsChange: (updated: Record<string, string>) => void;
  onVaultTextChange: (text: string) => void;
  onConsentChange: (consent: boolean) => void;
  className?: string;
}

interface SectionDefinition {
  key: string;
  title: string;
  hint: string;
  placeholder: string;
}

const VAULT_SECTION_DEFS: SectionDefinition[] = [
  {
    key: "leadership",
    title: "Leadership",
    hint: "Student government, clubs led, team management, campus initiatives",
    placeholder: "e.g. Led student ACM chapter of 120 members; organized regional hackathon with 400+ attendees...",
  },
  {
    key: "hardships",
    title: "Hardships you have overcome",
    hint: "Financial obstacles, family circumstances, under-resourced background",
    placeholder: "e.g. Self-funded final 2 years of undergraduate study via tutoring 15 hrs/week while maintaining first-class standing...",
  },
  {
    key: "projects",
    title: "Projects",
    hint: "Capstones, software prototypes, hardware builds, technical research",
    placeholder: "e.g. SunTrack: low-cost solar panel monitoring system built with ESP32 microcontroller and wireless sensors...",
  },
  {
    key: "volunteering",
    title: "Volunteering",
    hint: "Role, community organization, hours volunteered, direct social impact",
    placeholder: "e.g. Volunteered as coding instructor at Community Secondary School; taught Python to 40 students over 200 hours...",
  },
  {
    key: "sports",
    title: "Sports and teams",
    hint: "Varsity athletics, intramural captaincy, sportsmanship honors",
    placeholder: "e.g. Captained the FSU football team for 2 seasons; led squad to state semi-finals...",
  },
  {
    key: "certifications",
    title: "Certifications",
    hint: "Industry licenses, professional courses, cloud certifications",
    placeholder: "e.g. AWS Certified Cloud Practitioner; DeepLearning.AI Embedded ML Specialization...",
  },
  {
    key: "awards",
    title: "Awards & Honors",
    hint: "Dean's honor roll, hackathon victories, academic commendations",
    placeholder: "e.g. Dean's List for 2 consecutive academic sessions; 1st Place at National Smart Energy Hackathon 2024...",
  },
  {
    key: "languages",
    title: "Languages",
    hint: "Native tongues, second languages, CEFR/IELTS/TOEFL scores",
    placeholder: "e.g. English (Fluent / C2); Yoruba (Native); French (Beginner / A2)...",
  },
  {
    key: "career_goals",
    title: "Career goals",
    hint: "5-10 year post-graduation vision, target industry, research ambition",
    placeholder: "e.g. Lead edge computing architecture for rural renewable energy microgrids across sub-Saharan Africa...",
  },
  {
    key: "why_abroad",
    title: "Why you want to study abroad",
    hint: "Specialized lab access, global perspective, cross-border research collaboration",
    placeholder: "e.g. Seek hands-on lab access to advanced grid simulation testbeds and international faculty mentorship...",
  },
];

export function VaultCard({
  vaultSections,
  vaultText,
  sensitiveConsent,
  onSectionsChange,
  onVaultTextChange,
  onConsentChange,
  className = "",
}: VaultCardProps) {
  const [activeTab, setActiveTab] = useState<"sections" | "free">("sections");
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    leadership: true,
    hardships: true,
  });

  const toggleSection = (key: string) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const updateSectionText = (key: string, text: string) => {
    onSectionsChange({ ...vaultSections, [key]: text });
  };

  const filledCount = VAULT_SECTION_DEFS.filter(
    (def) => (vaultSections[def.key] || "").trim().length > 0
  ).length;
  const filledPct = Math.round((filledCount / VAULT_SECTION_DEFS.length) * 100);

  return (
    <section className={`rounded-xl bg-[#121318] border border-[#262932] p-6 flex flex-col gap-6 ${className}`}>
      {/* Header */}
      <div className="border-b border-[#262932] pb-4 flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-mono uppercase text-[#5FD3A0]">Vault Profile</span>
            <span className="text-[#626877]">•</span>
            <span className="text-[11px] font-mono text-[#626877]">Context Inventory</span>
          </div>
          <span className="text-[11px] font-mono text-[#9AA0AE]">Strict Local Scope</span>
        </div>
        <h2 className="text-xl font-semibold tracking-tight text-[#ECEDF0]">Your personal file</h2>
        <p className="text-xs text-[#9AA0AE] leading-relaxed">
          The more real detail you give, the better the agent can find your strongest evidence. Everything here stays in your account.
        </p>
      </div>

      {/* Mode & Progress Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#181A20] border border-[#262932] p-3.5 rounded-lg">
        <div className="inline-flex p-0.5 rounded bg-[#121318] border border-[#262932]">
          <button
            type="button"
            onClick={() => setActiveTab("sections")}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors cursor-pointer ${
              activeTab === "sections"
                ? "bg-[#181A20] text-[#ECEDF0] border border-[#353945]"
                : "text-[#9AA0AE] hover:text-[#ECEDF0]"
            }`}
          >
            Structured sections
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("free")}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors cursor-pointer ${
              activeTab === "free"
                ? "bg-[#181A20] text-[#ECEDF0] border border-[#353945]"
                : "text-[#9AA0AE] hover:text-[#ECEDF0]"
            }`}
          >
            Paste free text instead
          </button>
        </div>

        {activeTab === "sections" && (
          <div className="flex flex-col sm:items-end gap-1.5">
            <span className="text-[11px] font-mono text-[#ECEDF0]">
              {filledCount} of {VAULT_SECTION_DEFS.length} sections filled ({filledPct}%)
            </span>
            <div className="w-48 h-1.5 bg-[#121318] rounded-full overflow-hidden border border-[#262932]">
              <div
                className="h-full bg-[#49e095] transition-all duration-300"
                style={{ width: `${filledPct}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Tab Content */}
      {activeTab === "sections" ? (
        <div className="flex flex-col gap-2">
          {VAULT_SECTION_DEFS.map((sec) => {
            const isOpen = !!openSections[sec.key];
            const textValue = vaultSections[sec.key] || "";
            const isFilled = textValue.trim().length > 0;

            return (
              <div
                key={sec.key}
                className={`rounded-lg border transition-colors overflow-hidden ${
                  isOpen
                    ? "border-[#353945] bg-[#181A20]"
                    : "border-[#262932] bg-[#181A20]/60 hover:border-[#353945]"
                }`}
              >
                {/* Header row */}
                <button
                  type="button"
                  onClick={() => toggleSection(sec.key)}
                  className="w-full p-3.5 flex items-center justify-between cursor-pointer text-left focus:outline-none"
                >
                  <div className="flex items-center gap-2.5">
                    {isFilled ? (
                      <div className="w-4 h-4 rounded-full bg-[rgba(61,214,140,0.12)] flex items-center justify-center text-[#49e095]">
                        <Check className="w-3 h-3" />
                      </div>
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-[#626877]" />
                    )}
                    <span className="text-xs font-medium text-[#ECEDF0]">
                      {sec.title}
                    </span>
                    {isFilled && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono text-[#5FD3A0] bg-[rgba(95,211,160,0.12)] border border-[#5FD3A0]/30">
                        {textValue.length} chars
                      </span>
                    )}
                  </div>
                  <div className="text-[#9AA0AE]">
                    {isOpen ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </div>
                </button>

                {/* Expanded textarea */}
                {isOpen && (
                  <div className="p-3.5 bg-[#121318] border-t border-[#262932] flex flex-col gap-2">
                    <p className="text-[11px] text-[#9AA0AE] italic">
                      {sec.hint}
                    </p>
                    <textarea
                      rows={2}
                      value={textValue}
                      onChange={(e) => updateSectionText(sec.key, e.target.value)}
                      placeholder={sec.placeholder}
                      className="w-full bg-[#181A20] border border-[#262932] rounded p-2 text-xs text-[#ECEDF0] placeholder-[#626877] focus:outline-none focus:border-[#353945] leading-relaxed resize-y"
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-lg bg-[#181A20] border border-[#262932] p-3 flex flex-col gap-2">
          <p className="text-xs text-[#9AA0AE]">
            Paste all your personal background, achievements, leadership, hardships, and extracurricular notes below. The intake parser will automatically extract and categorize individual facts.
          </p>
          <textarea
            rows={10}
            value={vaultText}
            onChange={(e) => onVaultTextChange(e.target.value)}
            placeholder="e.g. Captained football team for 2 seasons. Volunteered as Python teacher for 200 hours. Self-funded tuition through weekend tutoring..."
            className="w-full bg-[#121318] border border-[#262932] rounded p-3 text-xs text-[#ECEDF0] placeholder-[#626877] focus:outline-none focus:border-[#353945] leading-relaxed resize-y"
          />
        </div>
      )}

      {/* Sensitive Data Guardrail */}
      <div className="pt-4 border-t border-[#262932] flex flex-col gap-2">
        <label className="flex items-start gap-3 cursor-pointer select-none group">
          <input
            type="checkbox"
            checked={sensitiveConsent}
            onChange={(e) => onConsentChange(e.target.checked)}
            className="mt-1 w-4 h-4 rounded bg-[#181A20] border border-[#262932] text-[#5b8cff] focus:ring-0 focus:outline-none cursor-pointer"
          />
          <div className="flex flex-col">
            <span className="text-xs font-medium text-[#ECEDF0] group-hover:text-white transition-colors">
              Only use sensitive details (such as health, religion, family income) if a scholarship explicitly asks for them.
            </span>
            <span className="text-[11px] text-[#9AA0AE] mt-0.5 leading-relaxed">
              Details like health, religion or family income are never used unless a scholarship asks for them and you agreed above.
            </span>
          </div>
        </label>
      </div>
    </section>
  );
}
