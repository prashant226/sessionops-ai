"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CURRENT_WEEK } from "./api";

interface AppContextValue {
  opsName: string | null;
  weekStart: string;
  setWeekStart: (w: string) => void;
  login: (name: string, token: string) => void;
  logout: () => void;
  ready: boolean;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [opsName, setOpsName] = useState<string | null>(null);
  const [weekStart, setWeekStart] = useState<string>(CURRENT_WEEK);
  const [ready, setReady] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const name = typeof window !== "undefined" ? window.localStorage.getItem("sessionops_ops_name") : null;
    setOpsName(name);
    setReady(true);
  }, []);

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
    <AppContext.Provider value={{ opsName, weekStart, setWeekStart, login, logout, ready }}>{children}</AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
