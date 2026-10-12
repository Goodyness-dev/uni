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
  const [credentialKind, setCredentialKind] = useState<"identity" | "api_key">("api_key");
  const [connected, setConnected] = useState(false);
  const [connectionOpen, setConnectionOpen] = useState(false);
  async function connect(kind: "identity" | "api_key" | "development" = credentialKind) {
    setConnecting(true); setConnectionError("");
    try {
      if (kind === "api_key") await connectApiKey(identityToken);
      else if (kind === "development") await connectDevelopmentIdentity(email);
      else await exchangeIdentity(email, identityToken);
      setIdentityToken(""); window.location.reload();
    }
    catch (error) { setConnectionError(error instanceof Error ? error.message : "Connection failed."); }
    finally { setConnecting(false); }
  }
  async function signIn() {
    setConnecting(true); setConnectionError(""); setConnectionOpen(true);
    try { await beginVerifiedSignIn(); }
    catch (error) { setConnectionError(error instanceof Error ? error.message : "Sign-in unavailable."); setConnecting(false); }
  }
  const [latestRun, setLatestRun] = useState<Run | null>(null);
  useEffect(() => {
    const onRunUpdate = (event: Event) => {
      if (event instanceof CustomEvent && event.detail?.run_id) setLatestRun(event.detail as Run);
    };
    window.addEventListener("scholarpilot-run-updated", onRunUpdate);
    return () => window.removeEventListener("scholarpilot-run-updated", onRunUpdate);
  }, []);
  const [demoMode, setDemoMode] = useState<boolean>(false);
  const isMock = !useV1 && typeof window !== "undefined" && process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

  useEffect(() => {
    let mounted = true;
    api
      .getHealth()
      .then((health) => {
        if (mounted) {
          setDemoMode(health.demo_mode);
          if (health.demo_mode) setEmail(current => current || `tobi.demo+${crypto.randomUUID()}@example.com`);
        }
      })
      .catch(() => {
        if (mounted) setDemoMode(false);
      });

    if (useV1) api.getFacts().then(() => { if (mounted) setConnected(true); })
      .catch(() => { if (mounted) setConnected(false); });

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
        .catch(error => { setConnectionOpen(true); setConnectionError(error instanceof Error ? error.message : "Sign-in failed. Click Sign in to start a fresh session."); });
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
          {useV1 && <div className="relative text-xs">
            <button type="button" aria-expanded={connectionOpen} disabled={connecting} onClick={() => {
              if (connected || demoMode) setConnectionOpen(value => !value);
              else void signIn();
            }} className="rounded bg-[#262932] px-3 py-2 disabled:opacity-50">{connecting ? "Connecting…" : connected ? "Connected · Options" : demoMode ? "Start demo" : "Sign in"}</button>
            {connectionOpen && <div className="absolute right-0 top-10 w-80 max-w-[calc(100vw-2rem)] bg-[#181A20] border border-[#353945] p-4 rounded flex flex-col gap-3 shadow-xl">
              <div className="flex items-center justify-between"><strong>{connected ? "You’re connected" : "Connect to ScholarPilot"}</strong><button type="button" onClick={() => setConnectionOpen(false)} aria-label="Close connection options">Close</button></div>
              {connected && <p className="text-[#49e095]">You can upload your documents and run the agents.</p>}
              {!connected && demoMode && <>
                <p>Create a new local fictional demo session. No password or API key to paste. This does not verify your identity or recover an existing account.</p>
                <label>Demo access email<input type="email" value={email} onChange={e => setEmail(e.target.value)} className="w-full bg-[#0d0e11] p-2" /></label>
                <p className="text-[#9AA0AE]">This generated session address is separate from the contact email in your CV.</p>
                <button type="button" disabled={connecting || !email.trim()} onClick={() => { void connect("development"); }} className="rounded bg-[#5b8cff] p-2 text-white disabled:opacity-50">{connecting ? "Connecting…" : "Start fictional demo"}</button>
              </>}
              {!connected && <button type="button" disabled={connecting} className="rounded border border-[#353945] p-2 text-[#7AA2FF] disabled:opacity-50" onClick={() => { void signIn(); }}>Sign in with verified identity</button>}
              <details><summary className="cursor-pointer text-[#9AA0AE]">Advanced connection options</summary><div className="mt-3 flex flex-col gap-2">
                <label>Connection method<select value={credentialKind} onChange={e => { setCredentialKind(e.target.value as typeof credentialKind); setIdentityToken(""); }} className="w-full bg-[#0d0e11] p-2"><option value="api_key">Existing ScholarPilot API key</option><option value="identity">Identity provider token</option></select></label>
                {credentialKind === "identity" && <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} className="w-full bg-[#0d0e11] p-2" /></label>}
                <label>{credentialKind === "api_key" ? "ScholarPilot API key" : "Identity provider token"}<input type="password" autoComplete="off" value={identityToken} onChange={e => setIdentityToken(e.target.value)} className="w-full bg-[#0d0e11] p-2" /></label>
                <button type="button" disabled={connecting || (credentialKind === "identity" && !email) || !identityToken} onClick={() => { void connect(); }} className="p-2 bg-[#262932] disabled:opacity-50">{connecting ? "Connecting…" : "Connect"}</button>
              </div></details>
              {connectionError && <p role="alert" className="text-[#ff9a9a]">{connectionError}</p>}
            </div>}
          </div>}
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
