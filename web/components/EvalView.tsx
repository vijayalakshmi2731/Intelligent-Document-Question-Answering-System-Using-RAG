"use client";
import { useState } from "react";
import { Play } from "lucide-react";
import { api, pct } from "@/lib/api";
import { PageHeader, Stat, Table } from "./ui";

export default function EvalView() {
  const [n, setN] = useState(10);
  const [k, setK] = useState(5);
  const [gen, setGen] = useState(true);
  const [custom, setCustom] = useState("");
  const [out, setOut] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function run() {
    setBusy(true); setErr("");
    try {
      const cases = custom.trim() ? JSON.parse(custom) : null;
      setOut(await api("/evaluation/run", { method: "POST", body: { cases, n_synthetic: n, top_k: k, use_generation: gen } }));
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  }
  const s = out?.summary;
  const hk = s && Object.keys(s).find((x) => x.startsWith("hit@"));
  return (
    <>
      <PageHeader title="RAG evaluation" subtitle="Measure retrieval quality, groundedness and refusal behaviour on your own documents." />
      <div className="card flex flex-wrap items-end gap-4 p-4">
        <label className="text-xs font-medium text-zinc-500">Synthetic cases<input className="input mt-1 !w-28" type="number" min={1} max={50} value={n} onChange={(e) => setN(+e.target.value)} /></label>
        <label className="text-xs font-medium text-zinc-500">Top-K<input className="input mt-1 !w-24" type="number" min={1} max={20} value={k} onChange={(e) => setK(+e.target.value)} /></label>
        <label className="flex items-center gap-2 pb-2.5 text-sm"><input type="checkbox" checked={gen} onChange={(e) => setGen(e.target.checked)} className="h-4 w-4 accent-brand-600" /> Include answer generation</label>
        <button className="btn-primary ml-auto" onClick={run} disabled={busy}><Play size={15} /> {busy ? "Running…" : "Run evaluation"}</button>
      </div>
      <details className="card mt-3 p-4"><summary className="cursor-pointer text-sm font-medium">Custom test cases (JSON, optional)</summary>
        <textarea className="input mt-3 font-mono text-xs" rows={5} value={custom} onChange={(e) => setCustom(e.target.value)}
          placeholder='[{"question":"…","expected_document":"file.pdf","keywords":["term"]}]' /></details>
      {err && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40">{err}</p>}
      {out && (
        <div className="mt-6 animate-rise">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Test cases" value={s.cases} />
            <Stat label={hk!} value={pct(s[hk!])} hint="Relevant chunk in top-K" />
            <Stat label="MRR" value={s.mrr} hint="Mean reciprocal rank" />
            <Stat label="Precision@K" value={pct(s["precision@k"])} />
            <Stat label="Keyword recall" value={pct(s.keyword_recall)} hint="Expected terms in answer" />
            <Stat label="Groundedness" value={pct(s.groundedness)} hint="Answer supported by context" />
            <Stat label="Avg latency" value={s.avg_latency_ms == null ? "–" : `${s.avg_latency_ms} ms`} />
            <Stat label="Off-topic refusal" value={out.unanswerable ? pct(out.unanswerable.abstention_rate) : "–"} hint="Hallucination control" />
          </div>
          <div className="mt-6"><Table head={["Question", "Rank", "Top sim", "Recall", "Support"]}>
            {out.results.map((r: any, i: number) => (
              <tr key={i}><td className="td max-w-md">{r.question}</td>
                <td className="td">{r.rank ?? <span className="text-red-600">miss</span>}</td>
                <td className="td">{r.top_score}</td><td className="td">{pct(r.keyword_recall)}</td><td className="td">{pct(r.support)}</td></tr>
            ))}
          </Table></div>
        </div>
      )}
    </>
  );
}
