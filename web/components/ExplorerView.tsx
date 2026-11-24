"use client";
import { useEffect, useState } from "react";
import { Layers, Search } from "lucide-react";
import { api, pct } from "@/lib/api";
import { Empty, PageHeader, Table } from "./ui";

export default function ExplorerView() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[] | null>(null);
  const [cols, setCols] = useState<any[]>([]);
  useEffect(() => { api("/collections").then(setCols); }, []);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setHits(await api("/search?q=" + encodeURIComponent(q) + "&top_k=10"));
  }
  return (
    <>
      <PageHeader title="Knowledge base explorer" subtitle="Semantic search over every indexed chunk." />
      <form onSubmit={search} className="flex gap-2">
        <div className="relative flex-1"><Search size={16} className="absolute left-3.5 top-3.5 text-zinc-400" />
          <input className="input !pl-10" placeholder="Search meaning, not just keywords…" value={q} onChange={(e) => setQ(e.target.value)} required /></div>
        <button className="btn-primary">Search</button>
      </form>
      <div className="mt-6 space-y-3">
        {hits?.length === 0 && <div className="card"><Empty icon={<Search />} title="No matching passages" /></div>}
        {hits?.map((h) => (
          <div key={h.chunk_id} className="card animate-rise p-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{h.filename}</span>
              {h.page && <span className="text-zinc-500">page {h.page}</span>}
              {h.section && <span className="text-zinc-500">· {h.section}</span>}
              <span className="ml-auto rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-400">{pct(h.score)} match</span>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{h.text}</p>
          </div>
        ))}
      </div>
      <h2 className="mb-3 mt-10 flex items-center gap-2 text-lg font-semibold"><Layers size={18} /> Collections</h2>
      <Table head={["Collection", "Documents", "Chunks"]}>
        {cols.map((c) => <tr key={c.collection}><td className="td font-medium">{c.collection}</td><td className="td">{c.n}</td><td className="td">{c.chunks || 0}</td></tr>)}
      </Table>
    </>
  );
}
