"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Settings2, Loader2 } from "lucide-react";

import { getAutopilot, setAutopilot } from "../../lib/api";
import { useV1 } from "../../lib/v1";

interface StickyActionBarProps {
  factsCount: number;
  onRunAgent: (mode: "A" | "B" | "Z", topN: number, liveResearch: boolean) => Promise<void>;
  isRunning: boolean;
  isDemoMode?: boolean;
  className?: string;
}

export function StickyActionBar({
  factsCount,
  onRunAgent,
  isRunning,
  isDemoMode = true,
  className = "",
}: StickyActionBarProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [mode, setMode] = useState<"A" | "B" | "Z">("B");
  const [topN, setTopN] = useState<number>(2);
  const [liveResearch, setLiveResearch] = useState<boolean>(useV1);

  const [autopilot, setAutopilotValue] = useState(true);
  const [autonomyLoading, setAutonomyLoading] = useState(useV1);
  const [autonomyError, setAutonomyError] = useState<string | null>(null);
  useEffect(() => {
    if (!useV1) return;
    let mounted = true;
    getAutopilot().then(value => { if (mounted) setAutopilotValue(value); })
      .catch(error => { if (mounted) setAutonomyError(error instanceof Error ? error.message : "Autopilot setting could not be loaded."); })
      .finally(() => { if (mounted) setAutonomyLoading(false); });
    return () => { mounted = false; };
  }, []);
  const changeAutopilot = async (enabled: boolean) => {
    setAutonomyLoading(true); setAutonomyError(null);
    try { await setAutopilot(enabled); setAutopilotValue(enabled); }
    catch (error) { setAutonomyError(error instanceof Error ? error.message : "Autopilot setting could not be saved."); }
    finally { setAutonomyLoading(false); }
  };

  const canRun = factsCount > 0 && !isRunning && !autonomyLoading && !autonomyError;

  const handleRun = () => {
    if (canRun) {
      onRunAgent(mode, topN, liveResearch);
    }
  };

  return (
    <aside
      className={`fixed bottom-0 left-0 w-full z-40 bg-[#0d0e11] border-t border-[#262932] shadow-2xl ${className}`}
    >
      <div className="max-w-[1100px] mx-auto px-4 md:px-6 py-3 flex flex-col gap-2">
        {/* Advanced Panel (if toggled) */}
        {showAdvanced && isDemoMode && (
          <div className="p-3 mb-1 rounded-lg bg-[#181A20] border border-[#262932] flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
            <div className="flex items-center gap-4">
              {/* Pipeline Mode */}
              <div className="flex items-center gap-2">
                <span className="text-[#9AA0AE]">Pipeline Mode:</span>
                <div className="inline-flex p-0.5 rounded bg-[#121318] border border-[#262932]">
                  {(useV1 ? ["B"] as const : ["A", "B", "Z"] as const).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setMode(m)}
                      className={`px-2.5 py-0.5 rounded transition-colors cursor-pointer ${
                        mode === m
                          ? "bg-[#262932] text-[#ECEDF0]"
                          : "text-[#626877] hover:text-[#ECEDF0]"
                      }`}
                      title={
                        m === "A"
                          ? "Mode A: Baseline without verification"
                          : m === "B"
                          ? "Mode B: Full verification and recovery"
                          : "Mode Z: Demo stress testing"
                      }
                    >
                      Mode {m}
                    </button>
                  ))}
                </div>
              </div>

              {/* Top N matches */}
              <div className="flex items-center gap-2">
                <span className="text-[#9AA0AE]">Top Scholarships:</span>
                <select
                  value={topN}
                  onChange={(e) => setTopN(parseInt(e.target.value, 10))}
                  className="bg-[#121318] border border-[#262932] rounded px-2 py-0.5 text-xs text-[#ECEDF0] focus:outline-none"
                >
                  <option value={1}>Top 1</option>
                  <option value={2}>Top 2</option>
                  <option value={3}>Top 3</option>
                  <option value={4}>Top 4</option>
                  <option value={5}>Top 5</option>
                </select>
              </div>

              {/* Research Cache */}
              <div className="flex items-center gap-2">
                <span className="text-[#9AA0AE]">Research:</span>
                <button
                  type="button"
                  onClick={() => setLiveResearch(!liveResearch)}
                  className={`px-2 py-0.5 rounded border transition-colors cursor-pointer ${
                    liveResearch
                      ? "bg-[#5b8cff]/20 text-[#b2c5ff] border-[#5b8cff]/40"
                      : "bg-[#121318] text-[#9AA0AE] border-[#262932]"
                  }`}
                >
                  {liveResearch ? "Refresh official sources" : "Stored sources"}
                </button>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowAdvanced(false)}
              className="text-[#626877] hover:text-[#ECEDF0] text-[11px] underline cursor-pointer"
            >
              Close
            </button>
          </div>
        )}

        {/* Action Row */}
        <div className="flex items-center justify-between gap-4">
          {/* Left Facts Counter */}
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                factsCount > 0 ? "bg-[#49e095]" : "bg-[#626877]"
              }`}
            />
            <span className="text-xs font-mono font-medium text-[#ECEDF0]">
              {factsCount} facts ready
            </span>
            <span className="text-[#626877] font-mono text-[11px] hidden sm:inline">
              • Strict Ground Truth
            </span>
          </div>

          {useV1 && <label className="flex items-center gap-2 text-xs text-[#ECEDF0]">
            <input type="checkbox" checked={autopilot} disabled={autonomyLoading} onChange={event => { void changeAutopilot(event.target.checked); }} />
            Autopilot | auto-submit to demo portal
          </label>}
          {/* Right Controls */}
          <div className="flex items-center gap-3">
            {isDemoMode && (
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className={`p-2 rounded bg-[#181A20] border transition-colors cursor-pointer ${
                  showAdvanced ? "border-[#5b8cff] text-[#b2c5ff]" : "border-[#262932] text-[#9AA0AE] hover:text-[#ECEDF0]"
                }`}
                title="Configure run pipeline (Mode A/B/Z, Top N)"
              >
                <Settings2 className="w-4 h-4" />
              </button>
            )}

            {/* Primary Run Button */}
            <button
              type="button"
              disabled={!canRun}
              onClick={handleRun}
              className={`px-5 py-2.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 select-none ${
                canRun
                  ? "bg-[#ECEDF0] hover:bg-white text-[#0B0C0F] cursor-pointer shadow-lg hover:shadow-white/10 active:scale-[0.98]"
                  : "bg-[#1f1f23] text-[#626877] border border-[#262932] cursor-not-allowed opacity-60"
              }`}
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Launching pipeline...</span>
                </>
              ) : (
                <>
                  <span>Run agent</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>

        {autonomyError && <p role="alert" className="text-xs text-red-300">{autonomyError}</p>}
        {/* Privacy Line */}
        <div className="border-t border-[#262932]/50 pt-1 text-center sm:text-left">
          <p className="font-mono text-[10px] text-[#626877] leading-normal">
          Your documents are processed by the backend. When AI drafting is enabled, reviewed source facts may be sent to the configured provider. Autopilot submits verified packages to the demo portal automatically. Turn it off to require review. A submission already accepted by the portal cannot be undone.
          </p>
        </div>
      </div>
    </aside>
  );
}
