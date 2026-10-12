"use client";
import { useEffect, useState } from "react";
import { getNotificationSettings, saveNotificationSettings, testNotification, getNotificationTest, NotificationSettings } from "@/lib/api";
export function NotificationControls() {
  const [value, setValue] = useState<NotificationSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [testId, setTestId] = useState<string | null>(null);
  useEffect(() => { let mounted = true; getNotificationSettings().then(v => { if (mounted) setValue(v); }).catch(err => { if (mounted) setMessage(err instanceof Error ? err.message : "Settings unavailable."); }); return () => { mounted = false; }; }, []);
  useEffect(() => {
    if (!testId) return;
    let mounted = true;
    const timer = setInterval(() => { void getNotificationTest(testId).then(result => {
      if (!mounted) return;
      if (["completed", "dead_letter", "failed"].includes(result.status)) {
        setMessage(result.provider_accepted ? "Provider accepted the test message. Check your inbox or Telegram." : "Test delivery failed. Check the destination and provider configuration.");
        setTestId(null);
      }
    }).catch(err => { if (mounted) { setMessage(err instanceof Error ? err.message : "Delivery status unavailable."); setTestId(null); } }); }, 2000);
    return () => { mounted = false; clearInterval(timer); };
  }, [testId]);
  const perform = async (channel?: "email" | "telegram") => {
    if (!value) return;
    setBusy(true); setMessage("");
    try { await saveNotificationSettings({ notification_email: value.notification_email || null, telegram_chat_id: value.telegram_chat_id || null, email_notifications: value.email_notifications, telegram_notifications: value.telegram_notifications });
      if (channel) { const test = await testNotification(channel); setTestId(test.job_id); }
      setMessage(channel ? "Test queued. Delivery requires provider acceptance; queueing alone is not delivery." : "Notification preferences saved.");
    } catch (err) { setMessage(err instanceof Error ? err.message : "Could not save settings."); }
    finally { setBusy(false); }
  };
  return <section className="p-4 rounded-xl border border-[#262932] bg-[#121318] text-xs text-[#ECEDF0] flex flex-col gap-3">
    <h2 className="font-semibold">Notifications</h2>
    {!value ? <p role="status">{message || "Loading notification settings..."}</p> : <>
      <label>Email destination<input aria-label="Notification email" type="email" value={value.notification_email ?? ""} onChange={e => setValue({ ...value, notification_email: e.target.value })} className="ml-2 p-2 rounded bg-[#181A20] border border-[#262932]" /></label>
      <label><input type="checkbox" checked={value.email_notifications} onChange={e => setValue({ ...value, email_notifications: e.target.checked })} /> Email updates — {value.email_ready ? "provider configured" : "provider not configured"}</label>
      <label>Telegram chat ID<input aria-label="Telegram chat ID" value={value.telegram_chat_id ?? ""} onChange={e => setValue({ ...value, telegram_chat_id: e.target.value })} className="ml-2 p-2 rounded bg-[#181A20] border border-[#262932]" /></label>
      <label><input type="checkbox" checked={value.telegram_notifications} onChange={e => setValue({ ...value, telegram_notifications: e.target.checked })} /> Telegram updates — {value.telegram_ready ? "provider configured" : "provider not configured"}</label>
      <div className="flex gap-4"><button disabled={busy} onClick={() => { void perform(); }}>Save destinations</button><button disabled={busy || !value.email_ready} onClick={() => { void perform("email"); }}>Test email</button><button disabled={busy || !value.telegram_ready} onClick={() => { void perform("telegram"); }}>Test Telegram</button></div>
      {message && <p role="status" className="text-[#9AA0AE]">{message}</p>}
    </>}
  </section>;
}
