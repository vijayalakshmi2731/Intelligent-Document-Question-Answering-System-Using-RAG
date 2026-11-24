"use client";
import { useCallback, useEffect, useState } from "react";
import { BarChart3, FileText, LogOut, MessageSquare, Moon, Search, ShieldCheck, Sparkles, Sun, Gauge, UserCircle, Menu, X } from "lucide-react";
import { api, getToken, setToken, setUnauthorizedHandler, User } from "@/lib/api";
import { ToastProvider } from "@/components/ui";
import AuthScreen from "@/components/AuthScreen";
import ChatView from "@/components/ChatView";
import DocsView from "@/components/DocsView";
import ExplorerView from "@/components/ExplorerView";
import EvalView from "@/components/EvalView";
import StatsView from "@/components/StatsView";
import ProfileView from "@/components/ProfileView";
import AdminView from "@/components/AdminView";

type View = "chat" | "docs" | "explore" | "eval" | "stats" | "profile" | "admin";
const NAV: { id: View; label: string; icon: any; admin?: boolean }[] = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "docs", label: "Documents", icon: FileText },
  { id: "explore", label: "Explorer", icon: Search },
  { id: "eval", label: "Evaluation", icon: Gauge },
  { id: "stats", label: "Usage", icon: BarChart3 },
  { id: "profile", label: "Profile", icon: UserCircle },
  { id: "admin", label: "Admin", icon: ShieldCheck, admin: true },
];

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [view, setView] = useState<View>("chat");
  const [dark, setDark] = useState(false);
  const [menu, setMenu] = useState(false);

  const logout = useCallback(() => { setToken(null); setUser(null); }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    const d = localStorage.getItem("theme") ? localStorage.getItem("theme") === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    setDark(d);
    if (!getToken()) return setReady(true);
    api<User>("/me").then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
  }, [logout]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  if (!ready) return <div className="grid h-screen place-items-center text-zinc-400">Loading…</div>;
  if (!user) return <ToastProvider><AuthScreen onAuth={setUser} /></ToastProvider>;

  const nav = (
    <>
      <div className="flex items-center gap-2.5 px-2 pb-6">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-600 text-white shadow-lg shadow-brand-500/30"><Sparkles size={18} /></div>
        <span className="text-lg font-semibold tracking-tight">DocQA</span>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.filter((n) => !n.admin || user.role === "admin").map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => { setView(id); setMenu(false); }}
            className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${view === id ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-400" : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800/60"}`}>
            <Icon size={18} /> {label}
          </button>
        ))}
      </nav>
      <div className="mt-auto flex items-center gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-800">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-violet-500 text-sm font-semibold text-white">{user.name[0]?.toUpperCase()}</div>
        <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{user.name}</div><div className="truncate text-xs text-zinc-500">{user.role}</div></div>
        <button className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800" onClick={() => setDark(!dark)} aria-label="Toggle theme">{dark ? <Sun size={16} /> : <Moon size={16} />}</button>
        <button className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800" onClick={logout} aria-label="Log out"><LogOut size={16} /></button>
      </div>
    </>
  );

  return (
    <ToastProvider>
      <div className="flex h-screen">
        <aside className="hidden w-64 shrink-0 flex-col border-r border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 md:flex">{nav}</aside>
        {menu && (
          <div className="fixed inset-0 z-40 md:hidden">
            <div className="absolute inset-0 bg-black/40" onClick={() => setMenu(false)} />
            <aside className="relative flex h-full w-72 flex-col bg-white p-4 dark:bg-zinc-900">{nav}</aside>
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center gap-3 border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900 md:hidden">
            <button onClick={() => setMenu(!menu)} aria-label="Menu">{menu ? <X /> : <Menu />}</button>
            <span className="font-semibold">DocQA</span>
          </header>
          <main className="min-h-0 flex-1 overflow-auto">
            {view === "chat" && <ChatView />}
            {view !== "chat" && (
              <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
                {view === "docs" && <DocsView />}
                {view === "explore" && <ExplorerView />}
                {view === "eval" && <EvalView />}
                {view === "stats" && <StatsView />}
                {view === "profile" && <ProfileView user={user} onUpdate={setUser} />}
                {view === "admin" && user.role === "admin" && <AdminView me={user} />}
              </div>
            )}
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
