"use client";

import { beginVerifiedSignIn, finishVerifiedSignIn } from "../lib/api";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles, User } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { exchangeIdentity, connectDevelopmentIdentity, connectApiKey } from "../lib/api";
import { useV1 } from "../lib/v1";
import { api } from "../lib/api";
import { Run } from "../lib/types";

export function TopBar() {
  return <Suspense fallback={<header className="h-14 bg-[#0d0e11]" />}><TopBarContent /></Suspense>;
}

function TopBarContent() {
  const pathname = usePathname();
  const [email, setEmail] = useState("");
  const [identityToken, setIdentityToken] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [credentialKind, setCredentialKind] = useState<"identity" | "api_key" | "development">("identity");
  async function connect() {
    setConnecting(true); setConnectionError("");
    try {
      if (credentialKind === "api_key") await connectApiKey(identityToken);
      else if (credentialKind === "development") await connectDevelopmentIdentity(email);
      else await exchangeIdentity(email, identityToken);
      setIdentityToken(""); window.location.reload();
    }
    catch (error) { setConnectionError(error instanceof Error ? error.message : "Connection failed."); }
    finally { setConnecting(false); }
  }
  const [latestRun, setLatestRun] = useState<Run | null>(null);
  const [demoMode, setDemoMode] = useState<boolean>(true);
  const isMock = !useV1 && typeof window !== "undefined" && process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

  useEffect(() => {
    let mounted = true;
    api
      .getHealth()
      .then((health) => {
        if (mounted) setDemoMode(health.demo_mode);
      })
      .catch(() => {
        if (mounted) setDemoMode(true);
      });

    api
      .getLatestRun()
      .then((run) => {
        if (mounted) setLatestRun(run);
      })
      .catch(() => {
        // Run may not exist yet, ignore
      });
    return () => {
      mounted = false;
    };
  }, [pathname]);

  useEffect(() => {
    if (!useV1) return;
    const parameters = new URLSearchParams(window.location.search);
    const code = parameters.get("code"), state = parameters.get("state");
    if (code && state) {
      window.history.replaceState({}, "", window.location.pathname);
      finishVerifiedSignIn(code, state).then(() => window.location.reload())
        .catch(error => { setConnectionError(error instanceof Error ? error.message : "Sign-in failed."); });
    }
  }, []);

  const handleLoadDemo = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("load-demo-persona"));
    }
  };

  const isRunning = latestRun?.status === "running";

  return (
    <header className="fixed top-0 w-full z-50 bg-[#0d0e11] border-b border-[#262932]" id="topbar">
      <div className="h-14 max-w-[1100px] mx-auto px-4 md:px-6 flex items-center justify-between">
        {/* Brand & Navigation */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-7 h-7 rounded bg-[#5b8cff]/15 border border-[#5b8cff]/30 flex items-center justify-center text-[#b2c5ff] group-hover:border-[#5b8cff]/60 transition-colors">
              <Sparkles className="w-4 h-4 text-[#b2c5ff]" />
            </div>
            <span className="font-semibold text-lg tracking-tight text-[#ECEDF0]">
              ScholarPilot
            </span>
            <span className="px-1.5 py-0.5 rounded bg-[#181A20] border border-[#262932] text-[11px] font-mono uppercase text-[#9AA0AE]">
              Agent
            </span>
          </Link>

          <nav className="flex items-center gap-1" id="nav-tabs">
            <Link
              href="/"
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                pathname === "/"
                  ? "bg-[#181A20] text-[#ECEDF0] border border-[#262932]"
                  : "text-[#9AA0AE] hover:text-[#ECEDF0] hover:bg-[#181A20]"
              }`}
              id="nav-profile-tab"
            >
              Profile
            </Link>
            <Link
              href="/matches"
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                pathname.startsWith("/matches")
                  ? "bg-[#181A20] text-[#ECEDF0] border border-[#262932]"
                  : "text-[#9AA0AE] hover:text-[#ECEDF0] hover:bg-[#181A20]"
              }`}
              id="nav-matches-tab"
            >
              Matches
            </Link>
          </nav>
        </div>

        {/* Status Chip, Connection & Actions */}
        <div className="flex items-center gap-3">
          {/* Active run chip */}
          <div
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#181A20] border border-[#262932]"
            id="run-status-chip"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isRunning ? "bg-[#b2c5ff] animate-pulse" : "bg-[#49e095]"
              }`}
            />
            <span className="text-xs font-mono text-[#ECEDF0]">
              {isRunning ? "Running" : "Idle"}
            </span>
          </div>

          {/* Connection Mode indicator */}
          <div className="flex items-center gap-1.5 px-2 py-0.5">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isMock ? "bg-[#ffb957]" : "bg-[#49e095] animate-pulse"
              }`}
            />
            <span
              className={`text-[11px] font-mono tracking-widest ${
                isMock ? "text-[#ffb957]" : "text-[#49e095]"
              }`}
            >
              {isMock ? "MOCK" : "LIVE"}
            </span>
          </div>

          {/* Load demo persona button (visible when demo_mode is enabled) */}
          {useV1 && <details className="relative text-xs"><summary className="cursor-pointer">Connect identity</summary>
              <button type="button" className="text-xs text-[#7AA2FF]" onClick={() => { void beginVerifiedSignIn().catch(error => setConnectionError(error instanceof Error ? error.message : "Sign-in unavailable.")); }}>Sign in with verified identity</button><div className="absolute right-0 top-8 w-72 bg-[#181A20] border border-[#353945] p-4 rounded flex flex-col gap-2">
            <label>Connection method<select value={credentialKind} onChange={e => { setCredentialKind(e.target.value as typeof credentialKind); setIdentityToken(""); }} className="w-full bg-[#0d0e11] p-2"><option value="identity">Identity provider token</option><option value="api_key">Existing API key</option>{demoMode && <option value="development">New fictional demo identity</option>}</select></label>
            {credentialKind !== "api_key" && <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} className="w-full bg-[#0d0e11] p-2" /></label>}
            {credentialKind !== "development" && <label>{credentialKind === "api_key" ? "API key" : "Identity provider token"}<input type="password" autoComplete="off" value={identityToken} onChange={e => setIdentityToken(e.target.value)} className="w-full bg-[#0d0e11] p-2" /></label>}
            <button disabled={connecting || (credentialKind !== "api_key" && !email) || (credentialKind !== "development" && !identityToken)} onClick={connect} className="p-2 bg-[#262932] disabled:opacity-50">{connecting ? "Connecting…" : "Connect"}</button>
            {connectionError && <p role="alert">{connectionError}</p>}
          </div></details>}
          {demoMode && !useV1 && (
            <button
              type="button"
              onClick={handleLoadDemo}
              className="px-2.5 py-1 rounded bg-[#181A20] hover:bg-[#292a2d] border border-[#262932] hover:border-[#353945] text-[#9AA0AE] hover:text-[#ECEDF0] text-xs font-medium transition-colors cursor-pointer"
              id="btn-load-demo-persona"
            >
              Load demo persona
            </button>
          )}

          <div
            className="w-7 h-7 rounded-full bg-[#5b8cff] flex items-center justify-center text-[#002665]"
            title="Profile"
          >
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    </header>
  );
}
