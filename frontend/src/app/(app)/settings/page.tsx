"use client";

import { Topbar } from "@/components/shell/Topbar";
import { useApp } from "@/lib/app-context";

export default function SettingsPage() {
  const { opsName } = useApp();

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

        <div className="rounded border border-slate-200 bg-white p-5 shadow-subtle">
          <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-slate-500">Integrations</h2>
          <p className="mb-3 text-[13px] text-slate-600">
            This environment runs in <span className="font-semibold">mock mode</span>. Google Calendar, Google Sheets, and
            OpenAI are simulated locally with deterministic adapters so the full workflow runs without external
            credentials. The scheduling engine (hard constraints, scoring, fairness) is identical in both modes.
          </p>
          <ul className="space-y-1.5 text-[13px] text-slate-600">
            <li>
              <span className="font-medium text-slate-800">Google Calendar</span> — mock: invites are simulated; RSVP is driven by the
              &quot;Demo: Simulate SME Response&quot; control on each session.
            </li>
            <li>
              <span className="font-medium text-slate-800">Google Sheets</span> — mock: &quot;Sync Data&quot; loads the bundled synthetic
              dataset (100 SMEs, 50 sessions).
            </li>
            <li>
              <span className="font-medium text-slate-800">OpenAI</span> — mock: semantic expertise nudges and recommendation copy use a
              deterministic local heuristic.
            </li>
          </ul>
          <p className="mt-3 text-[12px] text-slate-400">
            To connect real services, set INTEGRATION_MODE=live and the corresponding credentials in the backend .env file.
          </p>
        </div>
      </div>
    </>
  );
}
