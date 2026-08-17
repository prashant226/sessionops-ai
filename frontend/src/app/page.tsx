"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/lib/app-context";

export default function RootPage() {
  const router = useRouter();
  const { opsName, ready } = useApp();

  useEffect(() => {
    if (!ready) return;
    router.replace(opsName ? "/overview" : "/login");
  }, [ready, opsName, router]);

  return <div className="flex h-screen items-center justify-center bg-slate-50 text-sm text-slate-400">Loading…</div>;
}
