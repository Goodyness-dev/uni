"use client";

import { useState, KeyboardEvent } from "react";
import { Preferences } from "../../lib/types";
import { Plus, X } from "lucide-react";

interface PreferencesCardProps {
  preferences: Preferences;
  onChange: (updated: Preferences) => void;
  className?: string;
}

const COMMON_COUNTRIES = [
  "United Kingdom",
  "Germany",
  "Canada",
  "Netherlands",
  "Sweden",
  "United States",
  "France",
  "Australia",
];

export function PreferencesCard({
  preferences,
  onChange,
  className = "",
}: PreferencesCardProps) {
  const [fieldInput, setFieldInput] = useState("");

  const update = <K extends keyof Preferences>(key: K, value: Preferences[K]) => {
    onChange({ ...preferences, [key]: value });
  };

  const addField = () => {
    const trimmed = fieldInput.trim();
    if (trimmed && !preferences.fields.includes(trimmed)) {
      update("fields", [...preferences.fields, trimmed]);
      setFieldInput("");
    }
  };

  const handleFieldKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addField();
    }
  };

  const removeField = (fieldToRemove: string) => {
    update(
      "fields",
      preferences.fields.filter((f) => f !== fieldToRemove)
    );
  };

  const toggleCountry = (country: string) => {
    if (preferences.countries.includes(country)) {
      update(
        "countries",
        preferences.countries.filter((c) => c !== country)
      );
    } else {
      update("countries", [...preferences.countries, country]);
    }
  };

  return (
    <section className={`rounded-xl bg-[#121318] border border-[#262932] p-6 flex flex-col gap-6 ${className}`}>
      {/* Header */}
      <div className="border-b border-[#262932] pb-4">
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-[11px] font-mono uppercase text-[#626877]">Match Parameters</span>
          <span className="text-[#626877]">•</span>
          <span className="text-[11px] font-mono text-[#9AA0AE]">Constraints</span>
        </div>
        <h2 className="text-xl font-semibold tracking-tight text-[#ECEDF0]">What are you looking for</h2>
        <p className="text-xs text-[#9AA0AE] mt-0.5">
          Define boundaries for scholarship discovery and eligibility matching.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Full Name & Email */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[#ECEDF0]">Full Name</label>
          <input
            type="text"
            value={preferences.full_name}
            onChange={(e) => update("full_name", e.target.value)}
            placeholder="e.g. Tobi Adeyemi"
            className="h-10 px-3 rounded-lg bg-[#181A20] border border-[#262932] text-xs text-[#ECEDF0] placeholder-[#626877] focus:outline-none focus:border-[#353945]"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[#ECEDF0]">Email Address</label>
          <input
            type="email"
            value={preferences.email}
            onChange={(e) => update("email", e.target.value)}
            placeholder="e.g. tobi.adeyemi@example.com"
            className="h-10 px-3 rounded-lg bg-[#181A20] border border-[#262932] text-xs text-[#ECEDF0] placeholder-[#626877] focus:outline-none focus:border-[#353945]"
          />
        </div>

        {/* Degree Level */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[#ECEDF0]">Target Degree</label>
          <div className="inline-flex p-0.5 rounded-lg bg-[#181A20] border border-[#262932]">
            {(
              [
                { id: "undergraduate", label: "Undergraduate" },
                { id: "masters", label: "Master's" },
                { id: "phd", label: "PhD" },
              ] as const
            ).map((lvl) => (
              <button
                key={lvl.id}
                type="button"
                onClick={() => update("level", lvl.id)}
                className={`flex-1 py-1.5 px-3 rounded text-xs font-medium transition-colors cursor-pointer ${
                  preferences.level === lvl.id
                    ? "bg-[#121318] border border-[#353945] text-[#ECEDF0] shadow-sm"
                    : "text-[#9AA0AE] hover:text-[#ECEDF0]"
                }`}
              >
                {lvl.label}
              </button>
            ))}
          </div>
        </div>

        {/* Funding & Start Year */}
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[#ECEDF0]">Funding Tier</label>
            <div className="inline-flex p-0.5 rounded-lg bg-[#181A20] border border-[#262932]">
              {(["full", "partial"] as const).map((fund) => (
                <button
                  key={fund}
                  type="button"
                  onClick={() => update("funding", fund)}
                  className={`flex-1 py-1.5 px-2 rounded text-xs font-medium transition-colors capitalize cursor-pointer ${
                    preferences.funding === fund
                      ? "bg-[#121318] border border-[#353945] text-[#ECEDF0]"
                      : "text-[#9AA0AE] hover:text-[#ECEDF0]"
                  }`}
                >
                  {fund}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[#ECEDF0]">Start Year</label>
            <select
              value={preferences.start_year}
              onChange={(e) => update("start_year", parseInt(e.target.value, 10))}
              className="h-10 px-3 rounded-lg bg-[#181A20] border border-[#262932] text-xs text-[#ECEDF0] focus:outline-none focus:border-[#353945]"
            >
              <option value={2025}>2025</option>
              <option value={2026}>2026</option>
              <option value={2027}>2027</option>
            </select>
          </div>
        </div>

        {/* Nationality & GPA */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[#ECEDF0]">Nationality</label>
          <input
            type="text"
            value={preferences.nationality}
            onChange={(e) => update("nationality", e.target.value)}
            placeholder="e.g. Nigeria"
            className="h-10 px-3 rounded-lg bg-[#181A20] border border-[#262932] text-xs text-[#ECEDF0] placeholder-[#626877] focus:outline-none focus:border-[#353945]"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[#ECEDF0]">Cumulative GPA</label>
            <input
              type="number"
              step="0.01"
              value={preferences.gpa}
              onChange={(e) => update("gpa", parseFloat(e.target.value) || 0)}
              className="h-10 px-3 rounded-lg bg-[#181A20] border border-[#262932] text-xs font-mono text-[#ECEDF0] focus:outline-none focus:border-[#353945]"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[#ECEDF0]">GPA Scale</label>
            <input
              type="number"
              step="0.1"
              value={preferences.gpa_scale}
              onChange={(e) => update("gpa_scale", parseFloat(e.target.value) || 0)}
              className="h-10 px-3 rounded-lg bg-[#181A20] border border-[#262932] text-xs font-mono text-[#ECEDF0] focus:outline-none focus:border-[#353945]"
            />
          </div>
        </div>

        {/* Fields of Study Tag Input */}
        <div className="flex flex-col gap-2 md:col-span-2">
          <label className="text-xs font-medium text-[#ECEDF0]">Fields of Study</label>
          <div className="p-2 min-h-12 rounded-lg bg-[#181A20] border border-[#262932] flex flex-wrap items-center gap-2">
            {preferences.fields.map((fld) => (
              <div
                key={fld}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#121318] border border-[#262932] text-xs text-[#ECEDF0]"
              >
                <span>{fld}</span>
                <button
                  type="button"
                  onClick={() => removeField(fld)}
                  className="text-[#626877] hover:text-[#ECEDF0] transition-colors cursor-pointer"
                  aria-label={`Remove ${fld}`}
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
            <div className="flex items-center gap-1 flex-1 min-w-[140px]">
              <input
                type="text"
                value={fieldInput}
                onChange={(e) => setFieldInput(e.target.value)}
                onKeyDown={handleFieldKeyDown}
                placeholder="Add discipline and press Enter..."
                className="bg-transparent border-none text-xs text-[#ECEDF0] placeholder-[#626877] px-2 py-1 focus:outline-none flex-1"
              />
              {fieldInput.trim() && (
                <button
                  type="button"
                  onClick={addField}
                  className="p-1 rounded bg-[#262932] hover:bg-[#353945] text-xs text-[#ECEDF0] cursor-pointer"
                  title="Add field"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Target Destination Countries */}
        <div className="flex flex-col gap-2 md:col-span-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-[#ECEDF0]">Target Destination Countries</label>
            <span className="text-[11px] font-mono text-[#626877]">
              {preferences.countries.length} Selected
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {COMMON_COUNTRIES.map((country) => {
              const selected = preferences.countries.includes(country);
              return (
                <button
                  key={country}
                  type="button"
                  onClick={() => toggleCountry(country)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 cursor-pointer ${
                    selected
                      ? "bg-[#121318] border border-[#353945] text-[#ECEDF0]"
                      : "bg-[#181A20] border border-[#262932] text-[#9AA0AE] hover:text-[#ECEDF0] hover:border-[#353945]"
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      selected ? "bg-[#49e095]" : "bg-[#626877]"
                    }`}
                  />
                  <span>{country}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
