"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DEFAULT_PERIOD_START, DEFAULT_PERIOD_END } from "./api";

interface AppContextValue {
  opsName: string | null;
  periodStart: string;
  periodEnd: string;
  /** Sets the active schedule period directly, no overlap check. Used after
   * the caller has already resolved any overlap (see SchedulePeriodBar). */
  setPeriod: (start: string, end: string) => void;
  login: (name: string, token: string) => void;
  logout: () => void;
  ready: boolean;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [opsName, setOpsName] = useState<string | null>(null);
  const [periodStart, setPeriodStart] = useState<string>(DEFAULT_PERIOD_START);
  const [periodEnd, setPeriodEnd] = useState<string>(DEFAULT_PERIOD_END);
  const [ready, setReady] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const name = window.localStorage.getItem("sessionops_ops_name");
    setOpsName(name);
    const savedStart = window.localStorage.getItem("sessionops_period_start");
    const savedEnd = window.localStorage.getItem("sessionops_period_end");
    if (savedStart && savedEnd) {
      setPeriodStart(savedStart);
      setPeriodEnd(savedEnd);
    }
    setReady(true);
  }, []);

  function setPeriod(start: string, end: string) {
    setPeriodStart(start);
    setPeriodEnd(end);
    window.localStorage.setItem("sessionops_period_start", start);
    window.localStorage.setItem("sessionops_period_end", end);
  }

  function login(name: string, token: string) {
    window.localStorage.setItem("sessionops_ops_name", name);
    window.localStorage.setItem("sessionops_token", token);
    setOpsName(name);
  }

  function logout() {
    window.localStorage.removeItem("sessionops_ops_name");
    window.localStorage.removeItem("sessionops_token");
    setOpsName(null);
    router.push("/login");
  }

  return (
    <AppContext.Provider value={{ opsName, periodStart, periodEnd, setPeriod, login, logout, ready }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
