import { getMatches, getHealth, getFacts, getApplication, getLatestRun } from "../lib/api";
import { parseDate, daysLeft, timeAgo, formatTime, pct } from "../lib/format";

async function runTests() {
  console.log("Running F01 Verification Tests...");

  // 1. Test getMatches()
  const { matches } = await getMatches();
  if (matches.length !== 5) {
    throw new Error(`Expected 5 matches, got ${matches.length}`);
  }
  console.log(`✓ getMatches() returned ${matches.length} matches (3 mock, 2 real)`);

  // 2. Test getHealth()
  const health = await getHealth();
  if (!health.demo_mode) {
    throw new Error("Expected demo_mode to be true in health mock");
  }
  console.log("✓ getHealth() returned status:", health.status, "demo_mode:", health.demo_mode);

  // 3. Test getFacts()
  const { facts, preferences } = await getFacts();
  if (facts.length < 20 || !preferences) {
    throw new Error(`Expected >= 20 facts and preferences, got ${facts.length} facts`);
  }
  console.log(`✓ getFacts() returned ${facts.length} facts for persona ${preferences.full_name}`);

  // 4. Test getApplication() variants and getLatestRun()
  const runLatest = await getLatestRun();
  if (!runLatest.metrics) {
    throw new Error("Expected metrics in latest run mock");
  }
  const appVerified = await getApplication("app_1");
  if (appVerified.verification?.unsupported_final !== 0) {
    throw new Error("Expected unsupported_final to be 0 for verified application");
  }
  const appAwaiting = await getApplication("app_2");
  if (appAwaiting.status !== "awaiting_user" || !appAwaiting.handoff) {
    throw new Error("Expected awaiting_user status with handoff object");
  }
  console.log("✓ getApplication() and getLatestRun() returned successfully");

  // 5. Test format helpers
  const dt = parseDate("2026/10/11 14:30:00");
  if (isNaN(dt.getTime())) throw new Error("parseDate failed");
  const dLeft = daysLeft("2026/12/01");
  const tAgo = timeAgo("2026/10/11 09:00:00");
  const fTime = formatTime("2026/10/11 14:30:00");
  const pctStr = pct(0.85);
  if (pctStr !== "85%") throw new Error(`pct(0.85) returned ${pctStr}`);
  console.log(`✓ format helpers passed (daysLeft: ${dLeft}, timeAgo: ${tAgo}, formatTime: ${fTime})`);

  console.log("\nALL F01 ACCEPTANCE TESTS PASSED!");
}

runTests().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
