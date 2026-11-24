"use client";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, ChevronDown, MessageSquarePlus, Send, Sparkles, Trash2, TriangleAlert } from "lucide-react";
import { api, Doc, Msg, pct, Source } from "@/lib/api";
import { useToast } from "./ui";

type Conv = { id: number; title: string; updated_at: string };

function Answer({ m }: { m: Msg }) {
  const [open, setOpen] = useState<number | null>(null);
  const parts = m.content.split(/(\[\d+\])/g);
  const sources = m.sources || [];
  const lowConf = m.content.includes("Low confidence");
  return (
    <div className="animate-rise">
      <div className="whitespace-pre-wrap leading-relaxed">
        {parts.map((p, i) => {
          const n = /^\[(\d+)\]$/.exec(p)?.[1];
          return n ? (
            <button key={i} onClick={() => setOpen(open === +n ? null : +n)}
              className="mx-0.5 inline-flex h-5 min-w-5 -translate-y-0.5 items-center justify-center rounded-md bg-brand-100 px-1 text-[11px] font-semibold text-brand-700 hover:bg-brand-500 hover:text-white dark:bg-brand-500/20 dark:text-brand-400">{n}</button>
          ) : <Fragment key={i}>{p}</Fragment>;
        })}
      </div>
      {m.meta?.answered === false && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"><TriangleAlert size={14} /> Not found in your documents</div>
      )}
      {sources.length > 0 && (
        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-zinc-500"><BookOpen size={13} /> Sources</div>
          {sources.map((s: Source) => (
            <div key={s.n} className={`rounded-xl border text-sm transition ${open === s.n ? "border-brand-500 bg-brand-50/50 dark:bg-brand-500/10" : "border-zinc-200 dark:border-zinc-800"} ${s.cited ? "" : "opacity-60"}`}>
              <button className="flex w-full items-center gap-2.5 px-3 py-2 text-left" onClick={() => setOpen(open === s.n ? null : s.n)}>
                <span className="grid h-5 min-w-5 place-items-center rounded-md bg-brand-100 px-1 text-[11px] font-semibold text-brand-700 dark:bg-brand-500/20 dark:text-brand-400">{s.n}</span>
                <span className="min-w-0 flex-1 truncate font-medium">{s.filename}</span>
                <span className="shrink-0 text-xs text-zinc-500">{s.page ? `p.${s.page}` : s.section || ""}</span>
                <span className="shrink-0 rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">{pct(s.score)}</span>
                <ChevronDown size={14} className={`shrink-0 transition ${open === s.n ? "rotate-180" : ""}`} />
              </button>
              {open === s.n && <p className="border-t border-zinc-200 px-3 py-2.5 text-xs leading-relaxed text-zinc-600 dark:border-zinc-800 dark:text-zinc-400">{s.text}</p>}
            </div>
          ))}
        </div>
      )}
      {m.meta?.total_ms != null && (
        <div className="mt-3 flex flex-wrap gap-x-3 text-xs text-zinc-400">
          <span>{m.meta.intent}</span><span>{Math.round(m.meta.total_ms)} ms</span>
          {!lowConf && m.meta.answered && <span>{pct(m.meta.support)} supported</span>}<span>{m.meta.engine}</span>
        </div>
      )}
    </div>
  );
}

const SUGGESTIONS = ["Summarize the main points of my documents", "What are the key terms or definitions?", "List the important dates mentioned"];

export default function ChatView() {
  const toast = useToast();
  const [convs, setConvs] = useState<Conv[]>([]);
  const [cid, setCid] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [scope, setScope] = useState("");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const loadConvs = useCallback(() => api<Conv[]>("/conversations").then(setConvs), []);
  useEffect(() => {
    loadConvs();
    api<Doc[]>("/documents?status=ready").then(setDocs);
  }, [loadConvs]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  async function open(id: number) {
    const c = await api(`/conversations/${id}`);
    setCid(id); setMsgs(c.messages);
  }
  async function del() {
    if (!cid || !confirm("Delete this conversation?")) return;
    await api(`/conversations/${cid}`, { method: "DELETE" });
    setCid(null); setMsgs([]); loadConvs();
  }
  async function ask(text: string) {
    if (!text.trim() || busy) return;
    setQ(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: text }]);
    try {
      const r = await api("/chat", { method: "POST", body: { question: text, conversation_id: cid, document_ids: scope ? [+scope] : null } });
      setCid(r.conversation_id);
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, sources: r.sources, meta: r.meta }]);
      loadConvs();
    } catch (e: any) { toast(e.message); setMsgs((m) => m.slice(0, -1)); setQ(text); }
    setBusy(false);
  }

  return (
    <div className="flex h-full">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-zinc-200 bg-white/60 p-3 dark:border-zinc-800 dark:bg-zinc-900/40 lg:flex">
        <button className="btn-primary mb-3 w-full" onClick={() => { setCid(null); setMsgs([]); }}><MessageSquarePlus size={16} /> New chat</button>
        <div className="flex-1 space-y-0.5 overflow-auto">
          {convs.map((c) => (
            <button key={c.id} onClick={() => open(c.id)} className={`w-full truncate rounded-lg px-3 py-2 text-left text-sm transition ${c.id === cid ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-400" : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800/60"}`}>{c.title}</button>
          ))}
          {!convs.length && <p className="px-3 py-2 text-xs text-zinc-400">No conversations yet</p>}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-zinc-200 bg-white/70 px-4 py-2.5 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/60">
          <select className="input max-w-xs !py-1.5" value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="">All documents ({docs.length})</option>
            {docs.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}
          </select>
          <div className="flex-1" />
          <button className="btn-ghost !py-1.5 lg:hidden" onClick={() => { setCid(null); setMsgs([]); }}><MessageSquarePlus size={16} /></button>
          {cid && <button className="btn-danger !py-1.5" onClick={del}><Trash2 size={15} /></button>}
        </div>

        <div className="flex-1 overflow-auto px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {!msgs.length && (
              <div className="flex flex-col items-center pt-16 text-center animate-rise">
                <div className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-violet-600 text-white shadow-lg shadow-brand-500/30"><Sparkles /></div>
                <h2 className="mt-5 text-2xl font-semibold tracking-tight">What would you like to know?</h2>
                <p className="mt-1.5 text-sm text-zinc-500">{docs.length ? "Answers are grounded in your documents and cite their sources." : "Upload a document first, then ask away."}</p>
                {docs.length > 0 && (
                  <div className="mt-6 flex flex-wrap justify-center gap-2">
                    {SUGGESTIONS.map((s) => <button key={s} onClick={() => ask(s)} className="rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-600 transition hover:border-brand-500 hover:text-brand-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">{s}</button>)}
                  </div>
                )}
              </div>
            )}
            {msgs.map((m, i) => m.role === "user" ? (
              <div key={i} className="flex justify-end animate-rise"><div className="max-w-[85%] rounded-2xl rounded-br-md bg-gradient-to-br from-brand-500 to-violet-600 px-4 py-2.5 text-white shadow-md shadow-brand-500/20">{m.content}</div></div>
            ) : (
              <div key={i} className="flex gap-3">
                <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/15"><Sparkles size={16} /></div>
                <div className="min-w-0 flex-1 pt-0.5"><Answer m={m} /></div>
              </div>
            ))}
            {busy && (
              <div className="flex gap-3"><div className="grid h-8 w-8 place-items-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/15"><Sparkles size={16} className="animate-pulse" /></div>
                <div className="flex items-center gap-1 pt-2">{[0, 1, 2].map((i) => <span key={i} className="h-2 w-2 animate-bounce rounded-full bg-brand-400" style={{ animationDelay: `${i * 120}ms` }} />)}</div></div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="border-t border-zinc-200 bg-white/70 p-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/60">
          <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-zinc-200 bg-white p-2 shadow-soft focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-500/15 dark:border-zinc-700 dark:bg-zinc-900">
            <textarea rows={1} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask a question about your documents…"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(q); } }}
              className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none placeholder:text-zinc-400" />
            <button className="btn-primary !h-10 !w-10 !p-0" disabled={busy || !q.trim()} aria-label="Send"><Send size={16} /></button>
          </div>
        </form>
      </div>
    </div>
  );
}
