"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/shell/Sidebar";
import { useApp } from "@/lib/app-context";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { opsName, ready } = useApp();
  const router = useRouter();

  useEffect(() => {
    if (ready && !opsName) router.replace("/login");
  }, [ready, opsName, router]);

  if (!ready || !opsName) {
    return <div className="flex h-screen items-center justify-center bg-slate-50 text-sm text-slate-400">Loading…</div>;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
