"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api";
import { useApp } from "@/lib/app-context";

export default function LoginPage() {
  const [opsId, setOpsId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { login } = useApp();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.login(opsId, password);
      login(res.ops_name, res.token);
      router.push("/overview");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign in failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded border border-slate-200 bg-white p-8 shadow-panel">
        <div className="mb-6 text-center">
          <div className="mb-2 flex items-center justify-center gap-2">
            <Sparkles size={20} className="text-brand-600" />
            <h1 className="text-xl font-bold text-slate-900">SessionOps AI</h1>
          </div>
          <p className="text-[13px] text-slate-500">AI-assisted SME session scheduling</p>
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="ops_id" className="mb-1 block text-[13px] font-medium text-slate-700">
              Ops ID
            </label>
            <input
              id="ops_id"
              value={opsId}
              onChange={(e) => setOpsId(e.target.value)}
              className="focus-ring h-10 w-full rounded border border-slate-300 px-3 text-sm focus:border-brand-500"
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-[13px] font-medium text-slate-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="focus-ring h-10 w-full rounded border border-slate-300 px-3 text-sm focus:border-brand-500"
              autoComplete="current-password"
              required
            />
          </div>
          {error && (
            <p role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
              {error}
            </p>
          )}
          <Button type="submit" loading={loading} className="w-full">
            Sign In
          </Button>
        </form>
        <p className="mt-5 text-center text-[12px] text-slate-400">Demo environment · Ops ID "ops" · Password "sessionops"</p>
      </div>
    </div>
  );
}
