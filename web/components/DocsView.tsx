"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Download, FileText, RefreshCw, Search, Trash2, UploadCloud, X } from "lucide-react";
import { api, download, Doc, fmtSize } from "@/lib/api";
import { Empty, PageHeader, StatusBadge, Table, useToast } from "./ui";

export default function DocsView() {
  const toast = useToast();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [f, setF] = useState({ q: "", file_type: "", status: "", date_from: "" });
  const [opts, setOpts] = useState({ chunk_size: 800, chunk_overlap: 150, collection: "default", tags: "" });
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState("");
  const [detail, setDetail] = useState<any>(null);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api<Doc[]>("/documents?" + new URLSearchParams(f)).then(setDocs), [f]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!docs.some((d) => d.status === "processing")) return;
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [docs, load]);

  async function upload(files: FileList | File[]) {
    for (const file of Array.from(files)) {
      setUploading(file.name);
      const fd = new FormData();
      fd.append("file", file);
      Object.entries(opts).forEach(([k, v]) => fd.append(k, String(v)));
      try { await api("/documents", { method: "POST", body: fd }); } catch (e: any) { toast(`${file.name}: ${e.message}`); }
    }
    setUploading(""); load();
  }
  async function act(kind: string, d: Doc) {
    try {
      if (kind === "del" && confirm(`Delete ${d.filename}?`)) { await api(`/documents/${d.id}`, { method: "DELETE" }); if (detail?.id === d.id) setDetail(null); load(); }
      if (kind === "re") { await api(`/documents/${d.id}/reindex`, { method: "POST" }); load(); }
      if (kind === "dl") await download(`/documents/${d.id}/download`, d.filename);
      if (kind === "view") setDetail(await api(`/documents/${d.id}`));
    } catch (e: any) { toast(e.message); }
  }
  async function saveMeta() {
    await api(`/documents/${detail.id}`, { method: "PATCH", body: { title: detail.title, tags: detail.tags, collection: detail.collection } });
    toast("Saved"); load();
  }

  return (
    <>
      <PageHeader title="Documents" subtitle="Upload files to build your searchable knowledge base." />
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
        onClick={() => input.current?.click()}
        className={`card cursor-pointer border-2 border-dashed p-8 text-center transition ${drag ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10" : "hover:border-brand-400"}`}>
        <input ref={input} type="file" multiple hidden accept=".pdf,.docx,.txt,.md,.csv,.html,.htm" onChange={(e) => e.target.files && upload(e.target.files)} />
        <UploadCloud className="mx-auto text-brand-500" size={32} />
        <div className="mt-2 font-medium">{uploading ? `Uploading ${uploading}…` : "Drop files here or click to browse"}</div>
        <div className="text-sm text-zinc-500">PDF, DOCX, TXT, MD, CSV, HTML · up to 25 MB</div>
      </div>

      <div className="card mt-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        {([["chunk_size", "Chunk size", "number"], ["chunk_overlap", "Overlap", "number"], ["collection", "Collection", "text"], ["tags", "Tags", "text"]] as const).map(([k, l, t]) => (
          <label key={k} className="text-xs font-medium text-zinc-500">{l}
            <input className="input mt-1" type={t} value={(opts as any)[k]} onChange={(e) => setOpts({ ...opts, [k]: t === "number" ? +e.target.value : e.target.value })} />
          </label>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        <div className="relative min-w-52 flex-1"><Search size={16} className="absolute left-3 top-3 text-zinc-400" />
          <input className="input !pl-9" placeholder="Search name or tags…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} /></div>
        <select className="input !w-auto" value={f.file_type} onChange={(e) => setF({ ...f, file_type: e.target.value })}>
          <option value="">Any type</option>{["pdf", "docx", "txt", "md", "csv", "html"].map((t) => <option key={t}>{t}</option>)}</select>
        <select className="input !w-auto" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
          <option value="">Any status</option><option>ready</option><option>processing</option><option>failed</option></select>
        <input className="input !w-auto" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} />
      </div>

      <div className="mt-4">
        {docs.length === 0 ? (
          <div className="card"><Empty icon={<FileText />} title="No documents yet" text="Upload a document to start asking questions." /></div>
        ) : (
          <Table head={["Name", "Type", "Size", "Status", "Pages", "Chunks", "Collection", ""]}>
            {docs.map((d) => (
              <tr key={d.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/40">
                <td className="td"><button className="text-left font-medium hover:text-brand-600" onClick={() => act("view", d)}>{d.filename}</button>
                  {d.tags && <div className="mt-0.5 text-xs text-zinc-400">{d.tags}</div>}</td>
                <td className="td uppercase text-zinc-500">{d.file_type.slice(1)}</td>
                <td className="td text-zinc-500">{fmtSize(d.size)}</td>
                <td className="td"><StatusBadge status={d.status} />{d.error && <div className="mt-1 max-w-56 text-xs text-red-600">{d.error}</div>}</td>
                <td className="td">{d.pages}</td><td className="td">{d.chunk_count}</td>
                <td className="td text-zinc-500">{d.collection}</td>
                <td className="td"><div className="flex justify-end gap-1">
                  <button className="rounded-lg p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800" title="Download" onClick={() => act("dl", d)}><Download size={15} /></button>
                  <button className="rounded-lg p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800" title="Re-index" onClick={() => act("re", d)}><RefreshCw size={15} /></button>
                  <button className="rounded-lg p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40" title="Delete" onClick={() => act("del", d)}><Trash2 size={15} /></button></div></td>
              </tr>
            ))}
          </Table>
        )}
      </div>

      {detail && (
        <div className="card mt-6 animate-rise p-5">
          <div className="flex items-start justify-between"><h3 className="text-lg font-semibold">{detail.filename}</h3>
            <button onClick={() => setDetail(null)}><X size={18} /></button></div>
          <div className="mt-3 grid gap-3 sm:grid-cols-4">
            {(["title", "tags", "collection"] as const).map((k) => (
              <label key={k} className="text-xs font-medium capitalize text-zinc-500">{k}
                <input className="input mt-1" value={detail[k]} onChange={(e) => setDetail({ ...detail, [k]: e.target.value })} /></label>
            ))}
            <div className="flex items-end"><button className="btn-primary w-full" onClick={saveMeta}>Save metadata</button></div>
          </div>
          <p className="mt-3 text-xs text-zinc-500">{detail.chunk_count} chunks · {detail.char_count.toLocaleString()} characters · size {detail.chunk_size} / overlap {detail.chunk_overlap}</p>
          <div className="mt-3 max-h-96 space-y-2 overflow-auto">
            {detail.chunks.slice(0, 40).map((c: any) => (
              <div key={c.idx} className="rounded-xl border border-zinc-200 p-3 text-sm dark:border-zinc-800">
                <div className="mb-1 text-xs font-medium text-brand-600">#{c.idx}{c.page ? ` · page ${c.page}` : ""}{c.section ? ` · ${c.section}` : ""}</div>
                <div className="text-zinc-600 dark:text-zinc-400">{c.text}</div></div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
