"use client";
import { useState } from "react";
import { FileSearch, Quote, ShieldCheck, Sparkles } from "lucide-react";
import { api, setToken, User } from "@/lib/api";

export default function AuthScreen({ onAuth }: { onAuth: (u: User) => void }) {
  const [reg, setReg] = useState(false);
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const body = reg ? { ...f, name: f.name || f.email.split("@")[0] } : { email: f.email, password: f.password };
      const r = await api(reg ? "/auth/register" : "/auth/login", { method: "POST", body });
      setToken(r.token);
      onAuth(await api<User>("/me"));
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  const feats = [
    [FileSearch, "Semantic search", "Finds meaning, not just keywords, across all your files."],
    [Quote, "Cited answers", "Every answer links to the page and passage it came from."],
    [ShieldCheck, "Grounded & private", "Declines when the documents don’t contain the answer."],
  ] as const;

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-600 via-violet-600 to-fuchsia-600 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-fuchsia-400/20 blur-3xl" />
        <div className="relative flex items-center gap-2.5 text-xl font-semibold"><Sparkles /> DocQA</div>
        <div className="relative">
          <h2 className="max-w-md text-4xl font-semibold leading-tight tracking-tight">Ask your documents anything.</h2>
          <p className="mt-3 max-w-md text-white/80">Retrieval-augmented answers grounded in your own PDFs, reports and manuals.</p>
          <div className="mt-10 space-y-5">
            {feats.map(([Icon, t, d]) => (
              <div key={t} className="flex gap-4"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/15 backdrop-blur"><Icon size={18} /></div>
                <div><div className="font-medium">{t}</div><div className="text-sm text-white/75">{d}</div></div></div>
            ))}
          </div>
        </div>
        <div className="relative text-sm text-white/60">Retrieval-Augmented Generation</div>
      </div>
      <div className="grid place-items-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm animate-rise">
          <h1 className="text-2xl font-semibold tracking-tight">{reg ? "Create your account" : "Welcome back"}</h1>
          <p className="mt-1 text-sm text-zinc-500">{reg ? "Start asking questions in minutes." : "Sign in to continue."}</p>
          <div className="mt-8 space-y-4">
            {reg && <label className="block text-sm font-medium">Name<input className="input mt-1.5" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoComplete="name" /></label>}
            <label className="block text-sm font-medium">Email<input className="input mt-1.5" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} autoComplete="email" /></label>
            <label className="block text-sm font-medium">Password<input className="input mt-1.5" type="password" required minLength={8} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete={reg ? "new-password" : "current-password"} /></label>
          </div>
          {err && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">{err}</p>}
          <button className="btn-primary mt-6 w-full" disabled={busy}>{busy ? "Please wait…" : reg ? "Create account" : "Sign in"}</button>
          <p className="mt-5 text-center text-sm text-zinc-500">
            {reg ? "Already registered?" : "New here?"}{" "}
            <button type="button" className="font-medium text-brand-600 hover:underline" onClick={() => { setReg(!reg); setErr(""); }}>{reg ? "Sign in" : "Create an account"}</button>
          </p>
        </form>
      </div>
    </div>
  );
}
