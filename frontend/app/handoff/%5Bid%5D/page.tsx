"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ShieldCheck,
  Lock,
} from "lucide-react";
import { Application } from "@/lib/types";
import { getApplication, handoffDone, fileUrl } from "@/lib/api";
import { FileCard } from "@/components/FileCard";
import { Skeleton } from "@/components/Skeleton";
import { ErrorBanner } from "@/components/ErrorBanner";

type HandoffState = "waiting" | "checking" | "success" | "check_failed" | "not_needed";

export default function HandoffPage() {
  const params = useParams();
  const id = typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : "";

  const [application, setApplication] = useState<Application | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [handoffState, setHandoffState] = useState<HandoffState>("waiting");
  const [confirmationCode, setConfirmationCode] = useState<string | null>(null);

  const checkPollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Poll application data
  const loadApp = useCallback(async () => {
    if (!id) return;
    try {
      const app = await getApplication(id);
      setApplication(app);
      setError(null);

      if (app.status === "submitted" || app.submission?.confirmed) {
        setConfirmationCode(app.submission?.confirmation_code || null);
        setHandoffState("success");
      } else if (app.status !== "awaiting_user" && handoffState === "waiting") {
        setHandoffState("not_needed");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load application";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [id, handoffState]);

  useEffect(() => {
    if (!id) return;
    let isMounted = true;
    let intervalId: NodeJS.Timeout | null = null;

    const execute = async () => {
      try {
        const app = await getApplication(id);
        if (!isMounted) return;
        setApplication(app);
        setError(null);

        if (app.status === "submitted" || app.submission?.confirmed) {
          setConfirmationCode(app.submission?.confirmation_code || null);
          setHandoffState("success");
        } else if (app.status !== "awaiting_user" && handoffState === "waiting") {
          setHandoffState("not_needed");
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : "Failed to load application";
        setError(msg);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    execute();

    if (handoffState === "waiting") {
      intervalId = setInterval(execute, 4000);
    }

    return () => {
      isMounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [id, handoffState]);

  const handleDone = async () => {
    if (!id) return;
    setHandoffState("checking");

    try {
      await handoffDone(id);
    } catch (err) {
      console.error("Handoff done notification error:", err);
    }

    const startTime = Date.now();

    if (checkPollIntervalRef.current) {
      clearInterval(checkPollIntervalRef.current);
    }

    checkPollIntervalRef.current = setInterval(async () => {
      try {
        const updated = await getApplication(id);
        setApplication(updated);

        if (updated.status === "submitted" || updated.submission?.confirmed) {
          if (checkPollIntervalRef.current) {
            clearInterval(checkPollIntervalRef.current);
            checkPollIntervalRef.current = null;
          }
          setConfirmationCode(updated.submission?.confirmation_code || null);
          setHandoffState("success");
          return;
        }

        if (Date.now() - startTime >= 10000) {
          if (checkPollIntervalRef.current) {
            clearInterval(checkPollIntervalRef.current);
            checkPollIntervalRef.current = null;
          }
          setHandoffState("check_failed");
        }
      } catch (e) {
        console.error("Error polling application during check", e);
      }
    }, 1500);
  };

  useEffect(() => {
    return () => {
      if (checkPollIntervalRef.current) {
        clearInterval(checkPollIntervalRef.current);
        checkPollIntervalRef.current = null;
      }
    };
  }, []);

  const scholarshipName = application?.listing?.name || "Scholarship Portal";
  const portalUrl = application?.handoff?.portal_url || "#";
  const unsupportedFinal = application?.verification?.unsupported_final ?? 0;

  return (
    <div className="min-h-screen bg-[#0d0e11] text-[#ECEDF0] flex flex-col font-sans">
      <div className="flex-1 max-w-[560px] w-full mx-auto px-4 py-6 sm:py-10">
        {/* Navigation link */}
        <div className="mb-6">
          <Link
            href={`/applications/${id}`}
            className="inline-flex items-center gap-1.5 text-xs text-[#9AA0AE] hover:text-[#ECEDF0] transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Application Status</span>
          </Link>
        </div>

        {error && (
          <div className="mb-6">
            <ErrorBanner message={error} onRetry={loadApp} />
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !application && (
          <div className="p-6 rounded-xl bg-[#181A20] border border-[#262932] space-y-4">
            <Skeleton className="h-6 w-1/3" />
            <Skeleton className="h-10 w-3/4" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}

        {/* STATE: SUCCESS */}
        {!loading && application && handoffState === "success" && (
          <div className="p-6 sm:p-8 rounded-xl bg-[#181A20] border border-[#49e095]/40 text-center flex flex-col items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-[rgba(61,214,140,0.15)] text-[#49e095] flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8" />
            </div>

            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-[#ECEDF0]">Application Submitted!</h1>
              <p className="text-xs text-[#9AA0AE] mt-1">
                Your submission for <strong className="text-[#ECEDF0]">{scholarshipName}</strong> was confirmed.
              </p>
            </div>

            {confirmationCode && (
              <div className="p-4 rounded-lg bg-[#14171F] border border-[#262932] w-full my-2">
                <span className="text-[11px] font-mono uppercase text-[#9AA0AE] block mb-1">
                  Confirmation Code
                </span>
                <span className="text-2xl font-mono font-bold text-[#49e095] tracking-wider">
                  {confirmationCode}
                </span>
              </div>
            )}

            <Link
              href={`/applications/${id}`}
              className="w-full py-3 px-4 rounded-lg bg-[#5b8cff] hover:bg-[#4375e8] text-white font-semibold text-xs transition-colors flex items-center justify-center gap-2"
            >
              <span>View Application Status</span>
              <ArrowLeft className="w-3.5 h-3.5 rotate-180" />
            </Link>
          </div>
        )}

        {/* STATE: CHECKING */}
        {!loading && application && handoffState === "checking" && (
          <div className="p-8 rounded-xl bg-[#181A20] border border-[#5b8cff]/40 text-center flex flex-col items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-[rgba(91,140,255,0.15)] text-[#5b8cff] flex items-center justify-center">
              <RefreshCw className="w-6 h-6 animate-spin" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#ECEDF0]">Checking Portal Confirmation</h2>
              <p className="text-xs text-[#9AA0AE] mt-1">
                Verifying your submission receipt on the scholarship portal...
              </p>
            </div>
          </div>
        )}

        {/* STATE: CHECK FAILED */}
        {!loading && application && handoffState === "check_failed" && (
          <div className="p-6 rounded-xl bg-[#181A20] border border-[#ffb957]/40 flex flex-col gap-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-[rgba(245,165,36,0.15)] text-[#ffb957] shrink-0 mt-0.5">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#ECEDF0]">
                  We could not see a confirmation yet
                </h3>
                <p className="text-xs text-[#9AA0AE] mt-1 leading-relaxed">
                  Make sure you solved the CAPTCHA and clicked Submit on the portal page. If you already submitted, you can check again.
                </p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-2 pt-2">
              <button
                type="button"
                onClick={handleDone}
                className="flex-1 py-2.5 px-4 rounded-lg bg-[#F59E0B] hover:bg-[#D97706] text-[#14171F] font-semibold text-xs transition-colors"
              >
                Try checking again
              </button>
              <a
                href={portalUrl}
                target="_blank"
                rel="noreferrer"
                className="flex-1 py-2.5 px-4 rounded-lg bg-[#262932] hover:bg-[#353945] text-[#ECEDF0] font-medium text-xs transition-colors flex items-center justify-center gap-1.5"
              >
                <span>Re-open portal draft</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        )}

        {/* STATE: NOT NEEDED */}
        {!loading && application && handoffState === "not_needed" && (
          <div className="p-6 rounded-xl bg-[#181A20] border border-[#262932] text-center flex flex-col items-center gap-3">
            <div className="p-3 rounded-full bg-[#262932] text-[#9AA0AE]">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h2 className="text-base font-semibold text-[#ECEDF0]">Nothing needed right now</h2>
            <p className="text-xs text-[#9AA0AE] max-w-sm">
              This application is currently in status &quot;{application.status}&quot; and does not require manual CAPTCHA verification.
            </p>
            <Link
              href={`/applications/${id}`}
              className="mt-2 py-2 px-4 rounded-lg bg-[#262932] hover:bg-[#353945] text-xs font-medium text-[#ECEDF0] transition-colors"
            >
              Back to Status
            </Link>
          </div>
        )}

        {/* STATE: WAITING (MAIN VIEW) */}
        {!loading && application && handoffState === "waiting" && (
          <div className="flex flex-col gap-6">
            {/* Header badge & title */}
            <div className="flex flex-col gap-1">
              <span className="text-xs font-mono uppercase tracking-wider text-[#ffb957] font-semibold flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5" />
                <span>One quick step needed</span>
              </span>
              <h1 className="text-2xl font-bold text-[#ECEDF0] tracking-tight">
                {scholarshipName}
              </h1>
            </div>

            {/* Explanation card */}
            <div className="p-4 rounded-xl bg-[#181A20] border border-[#262932] text-xs leading-relaxed text-[#ECEDF0]">
              The portal for <strong className="text-[#ECEDF0]">{scholarshipName}</strong> is asking you to solve a CAPTCHA. For your safety and the portal&apos;s rules, only you can do that. Everything else is already filled in.
            </div>

            {/* 3 Step Guide */}
            <div className="flex flex-col gap-3">
              {/* Step 1 */}
              <div className="p-4 rounded-xl bg-[#181A20] border border-[#262932] flex flex-col gap-2.5">
                <div className="flex items-center gap-2.5">
                  <span className="w-6 h-6 rounded-full bg-[#262932] text-[#5b8cff] font-mono text-xs font-bold flex items-center justify-center shrink-0">
                    1
                  </span>
                  <span className="text-sm font-semibold text-[#ECEDF0]">
                    Open the portal page
                  </span>
                </div>
                <p className="text-xs text-[#9AA0AE] pl-8">
                  Your prepared CV summary, essay, and responses are pre-filled in the portal draft.
                </p>
                <div className="pl-8 pt-1">
                  <a
                    href={portalUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#262932] hover:bg-[#353945] border border-[#353945] text-xs font-semibold text-[#ECEDF0] transition-colors w-full sm:w-auto justify-center"
                  >
                    <span>Open portal draft</span>
                    <ExternalLink className="w-3.5 h-3.5 text-[#5b8cff]" />
                  </a>
                </div>
              </div>

              {/* Step 2 */}
              <div className="p-4 rounded-xl bg-[#181A20] border border-[#262932] flex flex-col gap-1.5">
                <div className="flex items-center gap-2.5">
                  <span className="w-6 h-6 rounded-full bg-[#262932] text-[#5b8cff] font-mono text-xs font-bold flex items-center justify-center shrink-0">
                    2
                  </span>
                  <span className="text-sm font-semibold text-[#ECEDF0]">
                    Solve the CAPTCHA and press Submit on that page
                  </span>
                </div>
                <p className="text-xs text-[#9AA0AE] pl-8">
                  Complete the verification challenge at the bottom of the portal and confirm submission.
                </p>
              </div>

              {/* Step 3 */}
              <div className="p-4 rounded-xl bg-[#181A20] border border-[#262932] flex flex-col gap-1.5">
                <div className="flex items-center gap-2.5">
                  <span className="w-6 h-6 rounded-full bg-[#262932] text-[#5b8cff] font-mono text-xs font-bold flex items-center justify-center shrink-0">
                    3
                  </span>
                  <span className="text-sm font-semibold text-[#ECEDF0]">
                    Come back and tap Done
                  </span>
                </div>
                <p className="text-xs text-[#9AA0AE] pl-8">
                  We&apos;ll record the confirmation code and update your application dashboard.
                </p>
              </div>
            </div>

            {/* Primary Action Button */}
            <div className="flex flex-col gap-3 pt-2">
              <button
                type="button"
                onClick={handleDone}
                className="w-full py-3.5 px-4 rounded-xl bg-[#F59E0B] hover:bg-[#D97706] text-[#14171F] font-bold text-sm transition-colors shadow-md flex items-center justify-center gap-2 cursor-pointer"
              >
                <span>Done, I submitted it</span>
              </button>

              <div className="text-center">
                <Link
                  href={`/applications/${id}`}
                  className="text-xs text-[#9AA0AE] hover:text-[#ECEDF0] transition-colors"
                >
                  Skip for now
                </Link>
              </div>
            </div>

            {/* Package Summary */}
            <div className="p-4 rounded-xl bg-[#14171F] border border-[#262932] flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase tracking-wider text-[#9AA0AE]">
                  Ready in Draft
                </span>
                <span className="text-xs font-mono text-[#49e095] flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Checked: {unsupportedFinal} unsupported claims</span>
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <FileCard
                  name="Tailored CV (PDF)"
                  type="pdf"
                  url={fileUrl(id, "cv")}
                />
                <FileCard
                  name="Statement / Essay"
                  type="markdown"
                  url={fileUrl(id, "essay")}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
