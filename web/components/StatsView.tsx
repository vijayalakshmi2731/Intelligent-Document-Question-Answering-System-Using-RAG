"use client";
import { useEffect, useState } from "react";
import { api, fmtSize } from "@/lib/api";
import { PageHeader, Stat } from "./ui";

export function StatGrid({ s }: { s: any }) {
  const items: [string, any][] = [
    ["Documents", s.documents], ["Ready", s.ready], ["Failed", s.failed], ["Chunks", s.chunks], ["Storage", fmtSize(s.storage_bytes)],
    ["Questions", s.questions], ["Answered", s.answered], ["Unanswered", s.unanswered],
    ["Avg response", `${s.avg_total_ms} ms`], ["Avg retrieval", `${s.avg_retrieval_ms} ms`],
    ["Avg similarity", s.avg_top_score], ["Avg support", `${Math.round(s.avg_support * 100)}%`],
  ];
  return <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{items.map(([l, v]) => <Stat key={l} label={l} value={v} />)}</div>;
}

export default function StatsView() {
  const [s, setS] = useState<any>(null);
  useEffect(() => { api("/stats").then(setS); }, []);
  if (!s) return null;
  return (
    <>
      <PageHeader title="Usage" subtitle="Your documents, questions and system performance." />
      <StatGrid s={s} />
      <div className="card mt-6 p-4 text-sm text-zinc-500">
        <div>Embeddings: <b className="text-zinc-800 dark:text-zinc-200">{s.embedder}</b></div>
        <div className="mt-1">Answer engine: <b className="text-zinc-800 dark:text-zinc-200">{s.llm ? "OpenAI" : "Offline extractive (add OPENAI_API_KEY to .env)"}</b></div>
      </div>
    </>
  );
}
