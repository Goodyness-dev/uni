"use client";

import { useState } from "react";
import type { ApplicationSummary, Run } from "@/lib/types";
import { USE_MOCKS } from "@/lib/api";

const fields = [
  ["price", "Single application price ($)", 4.99],
  ["seasonPrice", "Season pass price ($)", 19.99],
  ["reviewMinutes", "Review minutes per application", 5],
  ["hourlyCost", "Reviewer hourly cost ($)", 10],
  ["fixedCost", "Monthly fixed costs ($)", 300],
  ["cash", "Starting cash ($)", 10000],
] as const;
type Field = (typeof fields)[number][0];

export function BusinessPlanningCard({ run, applications }: { run: Run | null; applications: ApplicationSummary[] }) {
  const [values, setValues] = useState<Record<Field, string>>({ price: "4.99", seasonPrice: "19.99", reviewMinutes: "5", hourlyCost: "10", fixedCost: "300", cash: "10000" });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const complete = applications.filter(app => app.status === "submitted" || app.status === "prepared").length;
  const metrics = run?.metrics;
  const coverage = !!run && run.application_ids.length > 0 && run.application_ids.every(id => applications.some(app => app.id === id));
  const measured = !USE_MOCKS && coverage && run?.status === "completed" && !!metrics && metrics.llm_calls > 0 && metrics.tokens_total > 0 && Number.isFinite(metrics.cost_usd) && metrics.cost_usd >= 0 && complete > 0;
  const unitCost = measured && metrics ? metrics.cost_usd / complete : null;
  const valid = fields.every(([key]) => values[key].trim() !== "" && Number.isFinite(Number(values[key])) && Number(values[key]) >= 0);
  const reviewCost = valid ? Number(values.reviewMinutes) / 60 * Number(values.hourlyCost) : null;
  const assumptions = Object.fromEntries(fields.map(([key, label]) => [label, Number(values[key]) ]));
  const evidence = { run_id: run?.run_id ?? null, source: USE_MOCKS ? "demo mocks, not measured evidence" : "ScholarPilot run API", completed_packages: complete, llm_calls: metrics?.llm_calls ?? null, tokens: metrics?.tokens_total ?? null, llm_cost_per_package_usd: unitCost, measurement_status: measured ? "recorded run usage" : "usage unavailable", trace_url: run?.trace_url ?? null };
  const prompt = `Build a native cfo.ai financial Model for ScholarPilot, a verification-first scholarship assistant. Create a Page named ScholarPilot business plan. Inspect existing objects first and preserve unrelated content.
Recorded aggregate evidence: ${JSON.stringify(evidence)}.
Editable planning assumptions, NOT observed financial results: ${JSON.stringify(assumptions)}. Currency USD. Season pass covers up to 10 applications; model full usage. Ask for verified LLM costs when unavailable; never treat unknown as zero. Run cost includes shared pipeline overhead and excludes hosting, acquisition, payments and review.
Use shared Pricing Tier and Cost Category Dimensions, Date.Month, and twelve months. Main is baseline; add Growth and Conservative, asking me for paying users, growth and purchase mix. Ask for Last close, collection timing, payment fees, refunds and free-preview/acquisition costs before conclusions.
Show review unit cost = review minutes / 60 * hourly cost, delivery unit cost = LLM unit cost + review unit cost. Revenue = purchases * tier price. Delivery cost = purchases * applications per purchase * delivery unit cost. Contribution = revenue - delivery cost - payment costs - refunds. Operating cash flow subtracts fixed, acquisition and free-preview costs. Seed cash with starting cash, then carry ending cash forward. Season revenue is pass purchases times pass price, not application count times price.
Compare LLM cost at 0.5x, 1x, 1.5x and review time at 0, 5, 15 minutes. Explain when human review dominates the cost of trustworthy AI. Extra verification rounds need measured costs or clearly labeled assumptions. Show contribution margin, break-even and cash; no runway claim without positive net burn and complete costs.
Validate then save visible formulas, with Date.Month for Forecast. SUM flows, LAST cash, recompute ratios from totals. Read saved tables and verify Single and Season examples and quarterly totals. Label all assumptions and preserve source run/trace links. Do not publish publicly. Real scholarship portals are applicant handoffs; automatic submission is demo-only.`;

  async function copy(): Promise<void> {
    setBusy(true);
    try { await navigator.clipboard.writeText(prompt); setMessage("Copied. Open cfo.ai and paste this into Ari’s chat. Ari will ask for any missing numbers."); }
    catch { setMessage("Clipboard access failed. Download the request below and copy its text into Ari."); }
    finally { setBusy(false); }
  }
  function download(): void {
    const url = URL.createObjectURL(new Blob([prompt], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "ScholarPilot-Ari-request.txt"; link.click(); URL.revokeObjectURL(url);
  }
  return <section className="rounded-xl border border-[#262932] bg-[#121318] p-5 space-y-4">
    <div><p className="text-xs text-[#49e095]">BUSINESS PLANNING · cfo.ai</p><h2 className="text-lg font-semibold text-[#ECEDF0] mt-1">Can ScholarPilot afford to verify every application?</h2><p className="text-sm text-[#9AA0AE] mt-2">Ari is cfo.ai’s finance assistant. We prepare the business question and run evidence; Ari builds the financial model in your cfo.ai workspace.</p></div>
    <div className="rounded-lg bg-[#181A20] p-3 text-sm text-[#ECEDF0]">{unitCost === null ? "Measured LLM cost is unavailable for this run. Ari will ask for it before estimating profit." : `Recorded LLM cost per completed package: $${unitCost.toFixed(6)}`}<p className="text-xs text-[#9AA0AE] mt-1">{complete} completed packages · pipeline overhead included · other service costs excluded</p></div>
    <details><summary className="cursor-pointer text-sm text-[#b2c5ff]">Adjust planning assumptions</summary><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-3">{fields.map(([key, label]) => <label key={key} className="text-xs text-[#9AA0AE]">{label}<input type="number" min="0" step="any" value={values[key]} onChange={event => { setValues(prev => ({ ...prev, [key]: event.target.value })); setMessage(""); }} className="block w-full mt-1 p-2 rounded border border-[#353945] bg-[#181A20] text-[#ECEDF0]" /></label>)}</div><p className="text-xs text-[#9AA0AE] mt-3">All inputs are assumptions. {reviewCost !== null ? `Review alone would cost $${reviewCost.toFixed(2)} per application.` : "Enter valid nonnegative numbers."}</p></details>
    <ol className="list-decimal pl-5 text-sm text-[#9AA0AE] space-y-1"><li>Copy your prepared request.</li><li>Open your finance workspace and paste into Ari’s chat.</li><li>Ari creates the model; inspect pricing, costs and cash together.</li></ol>
    <div className="flex flex-wrap gap-3"><button onClick={copy} disabled={!valid || busy} className="rounded-lg bg-[#5b8cff] px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? "Copying…" : "Copy request for Ari"}</button><a href="https://app.cfo.ai/ayooluwa-cfoai-bdbda6b9/chat/91a6956d-c918-448e-a281-39b1c438006c?panel=page&pageId=99839ceb-266e-4240-997a-82c26898a638" target="_blank" rel="noopener noreferrer" className="rounded-lg border border-[#353945] px-4 py-2 text-sm text-[#ECEDF0]">Open finance workspace ↗</a><button onClick={download} disabled={!valid} className="text-sm text-[#b2c5ff] disabled:opacity-50">Download request</button></div>
    <p className="text-xs text-[#9AA0AE]">Your cfo.ai workspace is available. Updates to Ari are manual; copying or downloading does not sync data.</p>
    {message && <p role="status" className="text-sm text-[#b2c5ff]">{message}</p>}
  </section>;
}
