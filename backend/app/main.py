import json, re, secrets, sqlite3, time
from pathlib import Path
from typing import Optional
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import evaluation, vectorstore
from .auth import admin_user, current_user, hash_password, make_token, verify_password
from .config import (ALLOWED_EXTENSIONS, DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, FRONTEND_DIR, MAX_UPLOAD_MB,
                     TOP_K, UPLOAD_DIR)
from .db import db, init_db, log_activity
from .embeddings import get_embedder
from .ingest import process_document
from .llm import llm_available
from .rag import answer_question

app = FastAPI(title="DocQA – RAG Document Question Answering")
init_db()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- schemas ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    bio: Optional[str] = Field(default=None, max_length=500)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    current_password: Optional[str] = None


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[int] = None
    document_ids: Optional[list[int]] = None
    collection: Optional[str] = None
    top_k: int = Field(default=TOP_K, ge=1, le=20)


class DocMetaIn(BaseModel):
    title: Optional[str] = None
    tags: Optional[str] = None
    collection: Optional[str] = None


class EvalIn(BaseModel):
    cases: Optional[list[dict]] = None
    n_synthetic: int = Field(default=10, ge=1, le=50)
    top_k: int = Field(default=TOP_K, ge=1, le=20)
    use_generation: bool = True


# ---------- auth ----------
@app.post("/api/auth/register")
def register(body: RegisterIn):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Invalid email address")
    h, salt = hash_password(body.password)
    with db() as c:
        first = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"] == 0
        try:
            cur = c.execute("INSERT INTO users(email,name,password_hash,salt,role) VALUES(?,?,?,?,?)",
                            (email, body.name.strip(), h, salt, "admin" if first else "user"))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Email already registered")
        uid = cur.lastrowid
    log_activity(uid, "register", email)
    return {"token": make_token(uid), "user": {"id": uid, "email": email, "name": body.name.strip(),
                                               "role": "admin" if first else "user"}}


@app.post("/api/auth/login")
def login(body: LoginIn):
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),)).fetchone()
    if not u or not verify_password(body.password, u["password_hash"], u["salt"]):
        raise HTTPException(401, "Invalid email or password")
    if not u["active"]:
        raise HTTPException(403, "Account disabled")
    log_activity(u["id"], "login")
    return {"token": make_token(u["id"]),
            "user": {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"]}}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


@app.put("/api/me")
def update_me(body: ProfileIn, user=Depends(current_user)):
    with db() as c:
        if body.name is not None:
            c.execute("UPDATE users SET name=? WHERE id=?", (body.name.strip() or user["name"], user["id"]))
        if body.bio is not None:
            c.execute("UPDATE users SET bio=? WHERE id=?", (body.bio, user["id"]))
        if body.password:
            u = c.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            if not body.current_password or not verify_password(body.current_password, u["password_hash"], u["salt"]):
                raise HTTPException(400, "Current password is incorrect")
            h, s = hash_password(body.password)
            c.execute("UPDATE users SET password_hash=?,salt=? WHERE id=?", (h, s, user["id"]))
    return {"ok": True}


# ---------- documents ----------
def _own_doc(c, doc_id, user):
    d = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not d or (d["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "Document not found")
    return d


def _doc_out(r):
    return {k: r[k] for k in ("id", "filename", "file_type", "size", "status", "error", "pages", "chunk_count",
                              "char_count", "title", "tags", "collection", "chunk_size", "chunk_overlap", "created_at")}


@app.post("/api/documents")
async def upload(background: BackgroundTasks, file: UploadFile = File(...),
                 chunk_size: int = Form(DEFAULT_CHUNK_SIZE), chunk_overlap: int = Form(DEFAULT_CHUNK_OVERLAP),
                 collection: str = Form("default"), tags: str = Form(""), user=Depends(current_user)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    data = await file.read()
    if not data:
        raise HTTPException(400, "File is empty")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB limit")
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise HTTPException(400, "File content is not a valid PDF")
    if ext == ".docx" and not data.startswith(b"PK"):
        raise HTTPException(400, "File content is not a valid DOCX")
    if not 200 <= chunk_size <= 4000 or not 0 <= chunk_overlap < chunk_size:
        raise HTTPException(400, "chunk_size must be 200-4000 and 0 <= overlap < chunk_size")
    stored = f"{secrets.token_hex(12)}{ext}"
    (UPLOAD_DIR / stored).write_bytes(data)
    name = Path(file.filename).name
    with db() as c:
        cur = c.execute("INSERT INTO documents(user_id,filename,stored_name,file_type,size,title,tags,collection,"
                        "chunk_size,chunk_overlap) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (user["id"], name, stored, ext, len(data), Path(name).stem, tags, collection.strip() or "default",
                         chunk_size, chunk_overlap))
        doc_id = cur.lastrowid
    log_activity(user["id"], "upload", name)
    background.add_task(process_document, doc_id)
    return {"id": doc_id, "filename": name, "status": "processing"}


@app.get("/api/documents")
def list_documents(q: str = "", file_type: str = "", status: str = "", collection: str = "",
                   date_from: str = "", date_to: str = "", user=Depends(current_user)):
    sql, args = "SELECT * FROM documents WHERE user_id=?", [user["id"]]
    if q:
        sql += " AND (filename LIKE ? OR title LIKE ? OR tags LIKE ?)"
        args += [f"%{q}%"] * 3
    if file_type:
        sql += " AND file_type=?"; args.append(file_type if file_type.startswith(".") else "." + file_type)
    if status:
        sql += " AND status=?"; args.append(status)
    if collection:
        sql += " AND collection=?"; args.append(collection)
    if date_from:
        sql += " AND date(created_at)>=date(?)"; args.append(date_from)
    if date_to:
        sql += " AND date(created_at)<=date(?)"; args.append(date_to)
    with db() as c:
        rows = c.execute(sql + " ORDER BY id DESC", args).fetchall()
    return [_doc_out(r) for r in rows]


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: int, user=Depends(current_user)):
    with db() as c:
        d = _own_doc(c, doc_id, user)
        chunks = c.execute("SELECT idx,page,section,text FROM chunks WHERE document_id=? ORDER BY idx", (doc_id,)).fetchall()
    return {**_doc_out(d), "chunks": [dict(x) for x in chunks]}


@app.patch("/api/documents/{doc_id}")
def update_document(doc_id: int, body: DocMetaIn, user=Depends(current_user)):
    with db() as c:
        _own_doc(c, doc_id, user)
        for f in ("title", "tags", "collection"):
            v = getattr(body, f)
            if v is not None:
                c.execute(f"UPDATE documents SET {f}=? WHERE id=?", (v.strip(), doc_id))
    return {"ok": True}


@app.get("/api/documents/{doc_id}/download")
def download(doc_id: int, user=Depends(current_user)):
    with db() as c:
        d = _own_doc(c, doc_id, user)
    return FileResponse(UPLOAD_DIR / d["stored_name"], filename=d["filename"])


@app.post("/api/documents/{doc_id}/reindex")
def reindex(doc_id: int, background: BackgroundTasks, chunk_size: Optional[int] = None,
            chunk_overlap: Optional[int] = None, user=Depends(current_user)):
    with db() as c:
        d = _own_doc(c, doc_id, user)
        cs = chunk_size or d["chunk_size"]
        co = chunk_overlap if chunk_overlap is not None else d["chunk_overlap"]
        if not 200 <= cs <= 4000 or not 0 <= co < cs:
            raise HTTPException(400, "Invalid chunk settings")
        c.execute("UPDATE documents SET status='processing',chunk_size=?,chunk_overlap=? WHERE id=?", (cs, co, doc_id))
    background.add_task(process_document, doc_id)
    return {"ok": True}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, user=Depends(current_user)):
    with db() as c:
        d = _own_doc(c, doc_id, user)
        c.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))
        c.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    (UPLOAD_DIR / d["stored_name"]).unlink(missing_ok=True)
    log_activity(user["id"], "delete_document", d["filename"])
    return {"ok": True}


@app.get("/api/collections")
def collections(user=Depends(current_user)):
    with db() as c:
        rows = c.execute("SELECT collection, COUNT(*) n, SUM(chunk_count) chunks FROM documents WHERE user_id=? "
                         "GROUP BY collection", (user["id"],)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/search")
def search_chunks(q: str, top_k: int = 8, user=Depends(current_user)):
    """Knowledge-base explorer: raw semantic search over chunks."""
    from .embeddings import embed_texts
    hits = vectorstore.search(user["id"], embed_texts([q])[0], top_k=top_k)
    return [{**h, "score": round(h["score"], 4)} for h in hits]


# ---------- chat ----------
@app.get("/api/conversations")
def conversations(user=Depends(current_user)):
    with db() as c:
        rows = c.execute("SELECT id,title,created_at,updated_at FROM conversations WHERE user_id=? "
                         "ORDER BY updated_at DESC, id DESC", (user["id"],)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/conversations")
def new_conversation(user=Depends(current_user)):
    with db() as c:
        cur = c.execute("INSERT INTO conversations(user_id) VALUES(?)", (user["id"],))
    return {"id": cur.lastrowid, "title": "New conversation"}


def _own_conv(c, cid, user):
    r = c.execute("SELECT * FROM conversations WHERE id=? AND user_id=?", (cid, user["id"])).fetchone()
    if not r:
        raise HTTPException(404, "Conversation not found")
    return r


@app.get("/api/conversations/{cid}")
def get_conversation(cid: int, user=Depends(current_user)):
    with db() as c:
        conv = _own_conv(c, cid, user)
        msgs = c.execute("SELECT id,role,content,sources,meta,created_at FROM messages WHERE conversation_id=? ORDER BY id",
                         (cid,)).fetchall()
    return {"id": cid, "title": conv["title"],
            "messages": [{**dict(m), "sources": json.loads(m["sources"]), "meta": json.loads(m["meta"])} for m in msgs]}


@app.patch("/api/conversations/{cid}")
def rename_conversation(cid: int, body: dict, user=Depends(current_user)):
    with db() as c:
        _own_conv(c, cid, user)
        c.execute("UPDATE conversations SET title=? WHERE id=?", (str(body.get("title", ""))[:100] or "Untitled", cid))
    return {"ok": True}


@app.delete("/api/conversations/{cid}")
def delete_conversation(cid: int, user=Depends(current_user)):
    with db() as c:
        _own_conv(c, cid, user)
        c.execute("DELETE FROM conversations WHERE id=?", (cid,))
    return {"ok": True}


@app.post("/api/chat")
def chat(body: ChatIn, user=Depends(current_user)):
    with db() as c:
        if body.conversation_id:
            _own_conv(c, body.conversation_id, user)
            cid = body.conversation_id
        else:
            cid = c.execute("INSERT INTO conversations(user_id,title) VALUES(?,?)",
                            (user["id"], body.question[:60])).lastrowid
        hist = [dict(r) for r in c.execute(
            "SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 6", (cid,)).fetchall()][::-1]
        if not hist:
            c.execute("UPDATE conversations SET title=? WHERE id=? AND title='New conversation'", (body.question[:60], cid))
    result = answer_question(user["id"], body.question, hist, body.top_k, body.document_ids, body.collection)
    m = result["meta"]
    with db() as c:
        c.execute("INSERT INTO messages(conversation_id,role,content) VALUES(?,?,?)", (cid, "user", body.question))
        mid = c.execute("INSERT INTO messages(conversation_id,role,content,sources,meta) VALUES(?,?,?,?,?)",
                        (cid, "assistant", result["answer"], json.dumps(result["sources"]), json.dumps(m))).lastrowid
        c.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (cid,))
        c.execute("INSERT INTO query_log(user_id,question,intent,top_score,retrieval_ms,llm_ms,total_ms,answered,support,engine)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (user["id"], body.question, m["intent"], m["top_score"], m["retrieval_ms"], m.get("llm_ms", 0),
                   m["total_ms"], int(m["answered"]), m.get("support", 0), m.get("engine")))
    return {"conversation_id": cid, "message_id": mid, **result}


# ---------- evaluation ----------
@app.post("/api/evaluation/run")
def run_eval(body: EvalIn, user=Depends(current_user)):
    cases = body.cases or evaluation.synthetic_cases(user["id"], body.n_synthetic)
    if not cases:
        raise HTTPException(400, "No indexed documents to evaluate. Upload documents first.")
    report = evaluation.run_evaluation(user["id"], cases, body.top_k, body.use_generation)
    report["unanswerable"] = evaluation.unanswerable_check(user["id"]) if body.use_generation else None
    return report


# ---------- analytics ----------
def _stats(c, user_id=None):
    w, a = ("WHERE user_id=?", [user_id]) if user_id else ("", [])
    one = lambda sql, args=a: c.execute(sql, args).fetchone()
    q = one(f"SELECT COUNT(*) n, AVG(total_ms) t, AVG(retrieval_ms) r, AVG(llm_ms) l, AVG(top_score) s, "
            f"AVG(CASE WHEN answered=1 THEN support END) sup, SUM(answered) ans FROM query_log {w}")
    d = one(f"SELECT COUNT(*) n, SUM(status='ready') ready, SUM(status='failed') failed, SUM(status='processing') proc,"
            f" COALESCE(SUM(chunk_count),0) chunks, COALESCE(SUM(size),0) bytes FROM documents {w}")
    n = q["n"] or 0
    return {"documents": d["n"], "ready": d["ready"] or 0, "failed": d["failed"] or 0, "processing": d["proc"] or 0,
            "chunks": d["chunks"], "storage_bytes": d["bytes"], "questions": n, "answered": q["ans"] or 0,
            "unanswered": n - (q["ans"] or 0), "avg_total_ms": round(q["t"] or 0, 1),
            "avg_retrieval_ms": round(q["r"] or 0, 1), "avg_llm_ms": round(q["l"] or 0, 1),
            "avg_top_score": round(q["s"] or 0, 3), "avg_support": round(q["sup"] or 0, 3)}


@app.get("/api/stats")
def my_stats(user=Depends(current_user)):
    with db() as c:
        return {**_stats(c, user["id"]), "llm": llm_available(), "embedder": get_embedder().name}


# ---------- admin ----------
@app.get("/api/admin/stats")
def admin_stats(_=Depends(admin_user)):
    with db() as c:
        s = _stats(c)
        s["users"] = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        s["conversations"] = c.execute("SELECT COUNT(*) n FROM conversations").fetchone()["n"]
        daily = c.execute("SELECT date(created_at) day, COUNT(*) n, AVG(total_ms) ms FROM query_log "
                          "GROUP BY day ORDER BY day DESC LIMIT 14").fetchall()
        intents = c.execute("SELECT intent, COUNT(*) n FROM query_log GROUP BY intent ORDER BY n DESC").fetchall()
    return {**s, "daily": [dict(r) for r in daily][::-1], "intents": [dict(r) for r in intents],
            "llm": llm_available(), "embedder": get_embedder().name}


@app.get("/api/admin/users")
def admin_users(_=Depends(admin_user)):
    with db() as c:
        rows = c.execute("SELECT u.id,u.email,u.name,u.role,u.active,u.created_at,"
                         "(SELECT COUNT(*) FROM documents d WHERE d.user_id=u.id) documents,"
                         "(SELECT COUNT(*) FROM query_log q WHERE q.user_id=u.id) questions FROM users u ORDER BY u.id").fetchall()
    return [dict(r) for r in rows]


@app.patch("/api/admin/users/{uid}")
def admin_update_user(uid: int, body: dict, admin=Depends(admin_user)):
    if uid == admin["id"] and (body.get("active") is False or body.get("role") == "user"):
        raise HTTPException(400, "You cannot demote or disable yourself")
    with db() as c:
        if "active" in body:
            c.execute("UPDATE users SET active=? WHERE id=?", (int(bool(body["active"])), uid))
        if body.get("role") in ("admin", "user"):
            c.execute("UPDATE users SET role=? WHERE id=?", (body["role"], uid))
    return {"ok": True}


@app.delete("/api/admin/users/{uid}")
def admin_delete_user(uid: int, admin=Depends(admin_user)):
    if uid == admin["id"]:
        raise HTTPException(400, "You cannot delete yourself")
    with db() as c:
        for r in c.execute("SELECT stored_name FROM documents WHERE user_id=?", (uid,)).fetchall():
            (UPLOAD_DIR / r["stored_name"]).unlink(missing_ok=True)
        c.execute("DELETE FROM chunks WHERE user_id=?", (uid,))
        c.execute("DELETE FROM users WHERE id=?", (uid,))
    return {"ok": True}


@app.get("/api/admin/documents")
def admin_documents(_=Depends(admin_user)):
    with db() as c:
        rows = c.execute("SELECT d.*, u.email owner FROM documents d JOIN users u ON u.id=d.user_id ORDER BY d.id DESC").fetchall()
    return [{**_doc_out(r), "owner": r["owner"]} for r in rows]


@app.get("/api/admin/queries")
def admin_queries(limit: int = 100, _=Depends(admin_user)):
    with db() as c:
        rows = c.execute("SELECT q.*, u.email FROM query_log q LEFT JOIN users u ON u.id=q.user_id "
                         "ORDER BY q.id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/admin/activity")
def admin_activity(limit: int = 100, _=Depends(admin_user)):
    with db() as c:
        rows = c.execute("SELECT a.*, u.email FROM activity a LEFT JOIN users u ON u.id=a.user_id "
                         "ORDER BY a.id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/admin/report.csv")
def admin_report(_=Depends(admin_user)):
    import csv, io
    from fastapi.responses import Response
    with db() as c:
        rows = c.execute("SELECT q.created_at,u.email,q.question,q.intent,q.top_score,q.retrieval_ms,q.llm_ms,q.total_ms,"
                         "q.answered,q.support,q.engine FROM query_log q LEFT JOIN users u ON u.id=q.user_id ORDER BY q.id").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["created_at", "user", "question", "intent", "top_score", "retrieval_ms", "llm_ms", "total_ms",
                "answered", "support", "engine"])
    for r in rows:
        w.writerow(list(r))
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=usage_report.csv"})


@app.get("/api/health")
def health():
    return {"status": "ok", "llm": llm_available(), "embedder": get_embedder().name}


if FRONTEND_DIR.exists():  # optional legacy static frontend
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
