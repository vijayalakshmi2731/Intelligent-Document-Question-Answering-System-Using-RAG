"""SQLite-backed vector store with exact cosine search (numpy)."""
import numpy as np
from .db import db


def add_chunks(document_id: int, user_id: int, chunks, vectors: np.ndarray):
    with db() as c:
        c.executemany(
            "INSERT INTO chunks(document_id,user_id,idx,page,section,text,embedding) VALUES(?,?,?,?,?,?,?)",
            [(document_id, user_id, i, ch["page"], ch["section"], ch["text"], vectors[i].astype(np.float32).tobytes())
             for i, ch in enumerate(chunks)],
        )


def delete_document_chunks(document_id: int):
    with db() as c:
        c.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))


def search(user_id: int, qvec: np.ndarray, top_k=5, document_ids=None, collection=None):
    sql = ("SELECT c.id,c.document_id,c.idx,c.page,c.section,c.text,c.embedding,d.filename,d.collection "
           "FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.user_id=? AND d.status='ready'")
    args = [user_id]
    if document_ids:
        sql += f" AND c.document_id IN ({','.join('?' * len(document_ids))})"
        args += list(document_ids)
    if collection:
        sql += " AND d.collection=?"
        args.append(collection)
    with db() as c:
        rows = c.execute(sql, args).fetchall()
    if not rows:
        return []
    mat = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
    if mat.shape[1] != qvec.shape[0]:
        return []  # index built with a different embedding backend
    scores = mat @ qvec
    order = np.argsort(-scores)[:top_k]
    return [{
        "chunk_id": rows[i]["id"], "document_id": rows[i]["document_id"], "filename": rows[i]["filename"],
        "page": rows[i]["page"], "section": rows[i]["section"], "text": rows[i]["text"],
        "score": float(scores[i]),
    } for i in order]
