"use client";
import { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

export const Toast = createContext<(m: string) => void>(() => {});
export const useToast = () => useContext(Toast);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null);
  const show = useCallback((m: string) => { setMsg(m); setTimeout(() => setMsg(null), 3500); }, []);
  return (
    <Toast.Provider value={show}>
      {children}
      {msg && <div className="fixed bottom-6 right-6 z-50 animate-rise rounded-xl bg-zinc-900 px-4 py-3 text-sm text-white shadow-xl dark:bg-white dark:text-zinc-900">{msg}</div>}
    </Toast.Provider>
  );
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="card animate-rise p-4">
      <div className="text-2xl font-semibold tracking-tight">{value}</div>
      <div className="mt-0.5 text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      {hint && <div className="mt-1 text-xs text-zinc-400">{hint}</div>}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    ready: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400",
    failed: "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-400",
    processing: "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400",
  };
  const Icon = status === "ready" ? CheckCircle2 : status === "failed" ? XCircle : Loader2;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${map[status] || ""}`}>
      <Icon size={12} className={status === "processing" ? "animate-spin" : ""} /> {status}
    </span>
  );
}

export function Empty({ icon, title, text }: { icon: React.ReactNode; title: string; text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div className="rounded-2xl bg-brand-50 p-3 text-brand-600 dark:bg-brand-500/10">{icon}</div>
      <div className="font-medium">{title}</div>
      {text && <div className="max-w-sm text-sm text-zinc-500">{text}</div>}
    </div>
  );
}

export function Table({ head, children }: { head: string[]; children: React.ReactNode }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full">
        <thead className="border-b border-zinc-200 dark:border-zinc-800"><tr>{head.map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">{children}</tbody>
      </table>
    </div>
  );
}
