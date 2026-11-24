"use client";
import { useCallback, useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api, download, User } from "@/lib/api";
import { PageHeader, Stat, StatusBadge, Table, useToast } from "./ui";
import { StatGrid } from "./StatsView";

export default function AdminView({ me }: { me: User }) {
  const toast = useToast();
  const [d, setD] = useState<any>(null);
  const load = useCallback(async () => {
    const [stats, users, docs, queries, activity] = await Promise.all(
      ["stats", "users", "documents", "queries", "activity"].map((p) => api("/admin/" + p)));
    setD({ stats, users, docs, queries, activity });
  }, []);
  useEffect(() => { load(); }, [load]);
  if (!d) return null;

  const run = async (fn: () => Promise<any>) => { try { await fn(); load(); } catch (e: any) { toast(e.message); } };
  const s = d.stats;
  return (
    <>
      <PageHeader title="Admin dashboard" subtitle="Users, documents and system activity.">
        <button className="btn-ghost" onClick={() => download("/admin/report.csv", "usage_report.csv")}><Download size={15} /> CSV report</button>
      </PageHeader>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Stat label="Users" value={s.users} /><Stat label="Conversations" value={s.conversations} />
        <Stat label="Embedder" value={<span className="text-base">{s.embedder}</span>} /><Stat label="LLM" value={<span className="text-base">{s.llm ? "OpenAI" : "Extractive"}</span>} /></div>
      <div className="mt-3"><StatGrid s={s} /></div>
      {s.intents.length > 0 && (
        <div className="card mt-4 p-4">
          <div className="mb-3 text-sm font-medium">Question intents</div>
          {s.intents.map((i: any) => (
            <div key={i.intent} className="mb-2 flex items-center gap-3 text-sm">
              <span className="w-24 text-zinc-500">{i.intent}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800"><div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500" style={{ width: `${(i.n / s.questions) * 100}%` }} /></div>
              <span className="w-8 text-right">{i.n}</span>
            </div>
          ))}
        </div>
      )}

      <h2 className="mb-3 mt-10 text-lg font-semibold">Users</h2>
      <Table head={["Name", "Email", "Role", "Docs", "Questions", "Status", ""]}>
        {d.users.map((u: any) => (
          <tr key={u.id}><td className="td font-medium">{u.name}</td><td className="td text-zinc-500">{u.email}</td>
            <td className="td">{u.role}</td><td className="td">{u.documents}</td><td className="td">{u.questions}</td>
            <td className="td">{u.active ? <StatusBadge status="ready" /> : <StatusBadge status="failed" />}</td>
            <td className="td">{u.id !== me.id && (
              <div className="flex justify-end gap-1 text-xs">
                <button className="btn-ghost !px-2.5 !py-1" onClick={() => run(() => api(`/admin/users/${u.id}`, { method: "PATCH", body: { active: !u.active } }))}>{u.active ? "Disable" : "Enable"}</button>
                <button className="btn-ghost !px-2.5 !py-1" onClick={() => run(() => api(`/admin/users/${u.id}`, { method: "PATCH", body: { role: u.role === "admin" ? "user" : "admin" } }))}>Make {u.role === "admin" ? "user" : "admin"}</button>
                <button className="btn-danger !px-2.5 !py-1" onClick={() => confirm("Delete user and all data?") && run(() => api(`/admin/users/${u.id}`, { method: "DELETE" }))}>Delete</button>
              </div>)}</td></tr>
        ))}
      </Table>

      <h2 className="mb-3 mt-10 text-lg font-semibold">All documents</h2>
      <Table head={["File", "Owner", "Status", "Chunks", "Collection", ""]}>
        {d.docs.map((x: any) => (
          <tr key={x.id}><td className="td font-medium">{x.filename}</td><td className="td text-zinc-500">{x.owner}</td>
            <td className="td"><StatusBadge status={x.status} /></td><td className="td">{x.chunk_count}</td><td className="td">{x.collection}</td>
            <td className="td text-right"><button className="btn-danger !px-2.5 !py-1" onClick={() => confirm("Delete document?") && run(() => api(`/documents/${x.id}`, { method: "DELETE" }))}>Delete</button></td></tr>
        ))}
      </Table>

      <h2 className="mb-3 mt-10 text-lg font-semibold">Recent queries</h2>
      <Table head={["When", "User", "Question", "Intent", "Sim", "ms", "Answered"]}>
        {d.queries.map((q: any) => (
          <tr key={q.id}><td className="td whitespace-nowrap text-zinc-500">{q.created_at}</td><td className="td">{q.email}</td><td className="td max-w-xs">{q.question}</td>
            <td className="td">{q.intent}</td><td className="td">{q.top_score}</td><td className="td">{Math.round(q.total_ms)}</td><td className="td">{q.answered ? "yes" : "no"}</td></tr>
        ))}
      </Table>

      <h2 className="mb-3 mt-10 text-lg font-semibold">Activity</h2>
      <Table head={["When", "User", "Action", "Detail"]}>
        {d.activity.map((a: any) => (
          <tr key={a.id}><td className="td whitespace-nowrap text-zinc-500">{a.created_at}</td><td className="td">{a.email}</td><td className="td">{a.action}</td><td className="td text-zinc-500">{a.detail}</td></tr>
        ))}
      </Table>
    </>
  );
}
