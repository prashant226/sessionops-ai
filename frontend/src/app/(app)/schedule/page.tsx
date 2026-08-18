"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, RefreshCw, Sparkles, CalendarSearch, List, LayoutGrid, RotateCcw } from "lucide-react";
import { Topbar } from "@/components/shell/Topbar";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { SessionTable } from "@/components/schedule/SessionTable";
import { CalendarView } from "@/components/schedule/CalendarView";
import { SessionDrawer } from "@/components/schedule/SessionDrawer";
import { GenerateDraftModal } from "@/components/schedule/GenerateDraftModal";
import { FinalReviewModal } from "@/components/schedule/FinalReviewModal";
import { ClipboardCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import { useToast } from "@/lib/toast-context";
import { cn } from "@/lib/utils";
import type { AssignmentOut } from "@/lib/types";
import { CalendarDays } from "lucide-react";

function shiftWeek(weekStart: string, days: number): string {
  const d = new Date(`${weekStart}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function SchedulePageInner() {
  const { weekStart, setWeekStart } = useApp();
  const { push } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [rows, setRows] = useState<AssignmentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"list" | "calendar">("list");
  const [syncing, setSyncing] = useState(false);
  const [rechecking, setRechecking] = useState(false);
  const [genOpen, setGenOpen] = useState(false);
  const [finalReviewOpen, setFinalReviewOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [openAssignmentId, setOpenAssignmentId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listSessions(weekStart);
      setRows(data);
    } catch (err) {
      push("error", "Could not load the schedule", err instanceof ApiError ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [weekStart, push]);

  useEffect(() => {
    load();
  }, [load]);

  // Quietly re-pull every 30s (no spinner, no error toast) so RSVP changes
  // picked up by the backend's background poller (live mode) show up
  // without anyone clicking a button. Harmless no-op in mock mode.
  useEffect(() => {
    const interval = setInterval(() => {
      api.listSessions(weekStart).then(setRows).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, [weekStart]);

  useEffect(() => {
    const sessionParam = searchParams.get("session");
    if (!sessionParam || rows.length === 0) return;
    const match = rows.find((r) => r.session.session_id === sessionParam || r.assignment_id === sessionParam);
    if (match) setOpenAssignmentId(match.assignment_id);
  }, [searchParams, rows]);

  function closeDrawer() {
    setOpenAssignmentId(null);
    router.replace("/schedule");
  }

  async function onReset() {
    setResetting(true);
    try {
      const res = await api.resetWeek(weekStart);
      push("success", "Week reset", `Cleared ${res.cleared} assignment(s). Everything is back to 0.`);
      setResetOpen(false);
      await load();
    } catch (err) {
      push("error", "Could not reset this week", err instanceof ApiError ? err.message : undefined);
    } finally {
      setResetting(false);
    }
  }

  async function onSync() {
    setSyncing(true);
    try {
      await api.sync();
      push("success", "Data synced");
      await load();
    } catch (err) {
      push("error", "We could not sync your data", err instanceof ApiError ? err.message : "Your existing schedule has not been changed.");
    } finally {
      setSyncing(false);
    }
  }

  async function onRecheck() {
    setRechecking(true);
    try {
      const rsvp = await api.syncRsvp(weekStart).catch(() => null);
      if (rsvp && rsvp.updated.length > 0) {
        push("info", "RSVP updates found", `${rsvp.updated.length} SME(s) responded since last check.`);
      }
      const res = await api.recheckAvailability(weekStart);
      if (res.new_conflicts.length > 0) {
        push("warning", "New conflicts found", `${res.new_conflicts.length} assignment(s) now have a calendar conflict.`);
      } else {
        push("success", "No new conflicts", `Checked ${res.checked} active assignment(s).`);
      }
      await load();
    } catch (err) {
      push("error", "Could not re-check availability", err instanceof ApiError ? err.message : undefined);
    } finally {
      setRechecking(false);
    }
  }

  return (
    <>
      <Topbar
        title="Weekly Schedule"
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={onSync} loading={syncing}>
              <RefreshCw size={14} /> Sync
            </Button>
            <Button variant="secondary" size="sm" onClick={onRecheck} loading={rechecking}>
              <CalendarSearch size={14} /> Re-check Availability
            </Button>
            <Button size="sm" onClick={() => setGenOpen(true)}>
              <Sparkles size={14} /> Generate Draft
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setFinalReviewOpen(true)}>
              <ClipboardCheck size={14} /> Final Review
            </Button>
            {rows.length > 0 && (
              <Button variant="outline-danger" size="sm" onClick={() => setResetOpen(true)}>
                <RotateCcw size={14} /> Reset
              </Button>
            )}
          </>
        }
      />
      <div className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              aria-label="Previous week"
              onClick={() => setWeekStart(shiftWeek(weekStart, -7))}
              className="focus-ring flex h-8 w-8 items-center justify-center rounded border border-slate-300 bg-white text-slate-500 hover:bg-slate-50"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="min-w-[180px] text-center text-[13.5px] font-medium text-slate-700">{weekStart}</span>
            <button
              aria-label="Next week"
              onClick={() => setWeekStart(shiftWeek(weekStart, 7))}
              className="focus-ring flex h-8 w-8 items-center justify-center rounded border border-slate-300 bg-white text-slate-500 hover:bg-slate-50"
            >
              <ChevronRight size={16} />
            </button>
          </div>
          <div className="flex rounded border border-slate-300 bg-white p-0.5">
            <button
              onClick={() => setView("list")}
              className={cn("focus-ring flex items-center gap-1.5 rounded px-3 py-1.5 text-[13px] font-medium", view === "list" ? "bg-brand-600 text-white" : "text-slate-500 hover:bg-slate-50")}
            >
              <List size={14} /> Review List
            </button>
            <button
              onClick={() => setView("calendar")}
              className={cn("focus-ring flex items-center gap-1.5 rounded px-3 py-1.5 text-[13px] font-medium", view === "calendar" ? "bg-brand-600 text-white" : "text-slate-500 hover:bg-slate-50")}
            >
              <LayoutGrid size={14} /> Calendar
            </button>
          </div>
        </div>

        {loading ? (
          <div className="h-64 animate-pulse rounded border border-slate-200 bg-white" />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={CalendarDays}
            title="No sessions found for this week"
            description="Sync your session data to continue."
            action={
              <Button onClick={onSync} loading={syncing}>
                <RefreshCw size={14} /> Sync Data
              </Button>
            }
          />
        ) : view === "list" ? (
          <SessionTable rows={rows} onOpen={setOpenAssignmentId} />
        ) : (
          <CalendarView rows={rows} onOpen={setOpenAssignmentId} />
        )}
      </div>

      {openAssignmentId && (
        <SessionDrawer
          assignmentId={openAssignmentId}
          onClose={closeDrawer}
          onChanged={load}
        />
      )}
      <GenerateDraftModal open={genOpen} onClose={() => setGenOpen(false)} weekStart={weekStart} onComplete={load} />
      <FinalReviewModal open={finalReviewOpen} onClose={() => setFinalReviewOpen(false)} weekStart={weekStart} onFinalized={load} />
      <ConfirmModal
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        onConfirm={onReset}
        loading={resetting}
        danger
        title="Reset This Week"
        confirmLabel="Reset to 0"
        description={
          <>
            This clears every assignment for {weekStart} back to a blank slate. Session, SME, and performance
            data is not affected. Any real Google Calendar invites already sent are not deleted -- only the
            app&apos;s own record of them is cleared.
          </>
        }
      />
    </>
  );
}

export default function SchedulePage() {
  return (
    <Suspense fallback={null}>
      <SchedulePageInner />
    </Suspense>
  );
}
