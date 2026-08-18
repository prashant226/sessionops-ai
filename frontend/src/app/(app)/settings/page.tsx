"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { Topbar } from "@/components/shell/Topbar";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import { useToast } from "@/lib/toast-context";
import type { DemoConfigOut } from "@/lib/types";

function SettingsInner() {
  const { opsName } = useApp();
  const { push } = useToast();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<{ connected: boolean; account_email: string | null } | null>(null);
  const [demoConfig, setDemoConfig] = useState<DemoConfigOut | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    try {
      setStatus(await api.googleStatus());
    } catch {
      setStatus({ connected: false, account_email: null });
    }
    try {
      setDemoConfig(await api.demoConfig());
    } catch {
      setDemoConfig(null);
    }
  }

  useEffect(() => {
    load();
    const connected = searchParams.get("google_connected");
    const error = searchParams.get("google_error");
    if (connected) {
      push("success", "Google account connected", "Calendar invites and Sheets sync will now use this account.");
      window.history.replaceState({}, "", "/settings");
    } else if (error) {
      push("error", "Could not connect Google account", error);
      window.history.replaceState({}, "", "/settings");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function connect() {
    setLoading(true);
    try {
      const { auth_url } = await api.googleLogin();
      window.location.href = auth_url;
    } catch (err) {
      push("error", "Could not start Google connection", err instanceof ApiError ? err.message : undefined);
      setLoading(false);
    }
  }

  async function disconnect() {
    setLoading(true);
    try {
      await api.googleDisconnect();
      push("info", "Google account disconnected");
      await load();
    } catch (err) {
      push("error", "Could not disconnect", err instanceof ApiError ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Topbar title="Settings" />
      <div className="max-w-2xl p-6">
        <div className="mb-4 rounded border border-slate-200 bg-white p-5 shadow-subtle">
          <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-slate-500">Account</h2>
          <dl className="space-y-2 text-[13px]">
            <div className="flex justify-between">
              <dt className="text-slate-500">Signed in as</dt>
              <dd className="font-medium text-slate-800">{opsName || "Ops Team"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Role</dt>
              <dd className="font-medium text-slate-800">Ops / Curriculum</dd>
            </div>
          </dl>
        </div>

        <div className="mb-4 rounded border border-slate-200 bg-white p-5 shadow-subtle">
          <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-slate-500">Google Account</h2>
          <p className="mb-3 text-[13px] text-slate-600">
            One connected Google account is used to create Calendar events, invite SMEs as attendees, and read
            session/SME data from a Google Sheet. SMEs never need their own connection — they receive a normal
            Calendar invite by email and RSVP directly through Google.
          </p>
          {status === null ? (
            <div className="h-9 w-40 animate-pulse rounded bg-slate-100" />
          ) : status.connected ? (
            <div className="flex items-center justify-between rounded border border-emerald-200 bg-emerald-50 px-3.5 py-3">
              <div className="flex items-center gap-2 text-[13px] text-emerald-800">
                <CheckCircle2 size={16} />
                <div>
                  <p className="font-medium">Connected</p>
                  {status.account_email && <p className="text-[12px] text-emerald-700">{status.account_email}</p>}
                </div>
              </div>
              <Button variant="outline-danger" size="sm" onClick={disconnect} loading={loading}>
                Disconnect
              </Button>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded border border-slate-200 bg-slate-50 px-3.5 py-3">
              <div className="flex items-center gap-2 text-[13px] text-slate-600">
                <XCircle size={16} className="text-slate-400" />
                Not connected
              </div>
              <Button size="sm" onClick={connect} loading={loading}>
                Connect Google Account
              </Button>
            </div>
          )}
        </div>

        {demoConfig?.demo_mode && (
          <div className="mb-4 rounded border border-amber-200 bg-amber-50 p-5">
            <h2 className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-amber-800">Demo Mode</h2>
            <p className="text-[13px] text-amber-900">
              Demo Calendar recipient: <span className="font-mono font-semibold">{demoConfig.demo_calendar_email || "not configured"}</span>
            </p>
            <p className="mt-1.5 text-[12.5px] text-amber-800">
              Every real Calendar invite in this environment is redirected here instead of the SME&apos;s own (synthetic,
              non-real) email, so a real person can receive and respond to invites while testing. Set{" "}
              <span className="font-mono text-[11.5px]">DEMO_MODE=false</span> in the backend .env once SMEs have real
              production emails.
            </p>
          </div>
        )}

        <div className="rounded border border-slate-200 bg-white p-5 shadow-subtle">
          <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-slate-500">Integrations</h2>
          <p className="mb-3 text-[13px] text-slate-600">
            Calendar, Sheets, and OpenAI behavior depend on <span className="font-mono text-[12px]">INTEGRATION_MODE</span> in
            the backend&apos;s <span className="font-mono text-[12px]">.env</span> file. In <span className="font-semibold">mock</span> mode
            everything is simulated locally with deterministic adapters — no external credentials needed. In{" "}
            <span className="font-semibold">live</span> mode, connect your Google account above and the same actions
            (Sync Data, Approve, Send Replacement Invite) call the real APIs instead. The scheduling engine itself
            (hard constraints, scoring, fairness) is identical either way.
          </p>
          <ul className="space-y-1.5 text-[13px] text-slate-600">
            <li>
              <span className="font-medium text-slate-800">Google Calendar</span> — live: creates a real event and sends a real
              invite on Approve / Send Replacement Invite. RSVP is picked up automatically by a background poll (~60s) and
              also immediately via Schedule&rsquo;s Re-check Availability button.
            </li>
            <li>
              <span className="font-medium text-slate-800">Google Sheets</span> — live: &quot;Sync Data&quot; reads your connected Sheet
              (set <span className="font-mono text-[12px]">GOOGLE_SHEETS_SPREADSHEET_ID</span> in the backend .env).
            </li>
            <li>
              <span className="font-medium text-slate-800">OpenAI</span> — live: adds a small semantic-fit nudge and phrasing to
              recommendations when <span className="font-mono text-[12px]">OPENAI_API_KEY</span> is set. Never used for hard
              constraints.
            </li>
          </ul>
        </div>
      </div>
    </>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={null}>
      <SettingsInner />
    </Suspense>
  );
}
