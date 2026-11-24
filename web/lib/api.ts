export type User = { id: number; email: string; name: string; role: string; bio?: string };
export type Doc = {
  id: number; filename: string; file_type: string; size: number; status: "ready" | "processing" | "failed";
  error?: string; pages: number; chunk_count: number; char_count: number; title: string; tags: string;
  collection: string; chunk_size: number; chunk_overlap: number; created_at: string; owner?: string;
};
export type Source = { n: number; document_id: number; filename: string; page: number | null; section: string; score: number; cited: boolean; text: string };
export type Meta = { intent?: string; total_ms?: number; support?: number; engine?: string; answered?: boolean; top_score?: number };
export type Msg = { id?: number; role: "user" | "assistant"; content: string; sources?: Source[]; meta?: Meta };

let token: string | null = typeof window !== "undefined" ? localStorage.getItem("token") : null;
export const setToken = (t: string | null) => {
  token = t;
  if (t) localStorage.setItem("token", t); else localStorage.removeItem("token");
};
export const getToken = () => token;
export let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (f: () => void) => { onUnauthorized = f; };

export async function api<T = any>(path: string, opts: { method?: string; body?: any; raw?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let body = opts.body;
  if (body && !(body instanceof FormData)) { headers["Content-Type"] = "application/json"; body = JSON.stringify(body); }
  const r = await fetch(`/api${path}`, { method: opts.method || "GET", headers, body });
  if (r.status === 401 && token) { onUnauthorized(); throw new Error("Session expired"); }
  if (!r.ok) {
    let d = r.statusText;
    try { const j = await r.json(); d = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    throw new Error(d);
  }
  if (opts.raw) return r as any;
  return r.json();
}

export async function download(path: string, filename: string) {
  const r: Response = await api(path, { raw: true });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob());
  a.download = filename;
  a.click();
}

export const fmtSize = (n: number) => (n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.ceil(n / 1024)) + " KB");
export const pct = (v?: number | null) => (v == null ? "–" : Math.max(0, Math.round(v * 100)) + "%");
