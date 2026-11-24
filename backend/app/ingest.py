import time
from pathlib import Path
from . import vectorstore
from .chunking import chunk_units
from .config import UPLOAD_DIR
from .db import db
from .embeddings import embed_texts
from .extract import extract, ExtractionError


def process_document(doc_id: int):
    """Extraction -> chunking -> embeddings -> vector store. Updates document status."""
    with db() as c:
        d = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not d:
        return
    try:
        units = extract(Path(UPLOAD_DIR) / d["stored_name"], d["file_type"])
        chunks = chunk_units(units, d["chunk_size"], d["chunk_overlap"])
        if not chunks:
            raise ExtractionError("No usable text after cleaning")
        vectors = embed_texts([ch["text"] for ch in chunks])
        vectorstore.delete_document_chunks(doc_id)
        vectorstore.add_chunks(doc_id, d["user_id"], chunks, vectors)
        pages = len({u["page"] for u in units if u["page"] is not None}) or len(units)
        with db() as c:
            c.execute("UPDATE documents SET status='ready',error=NULL,pages=?,chunk_count=?,char_count=? WHERE id=?",
                      (pages, len(chunks), sum(len(ch["text"]) for ch in chunks), doc_id))
    except Exception as e:
        with db() as c:
            c.execute("UPDATE documents SET status='failed',error=? WHERE id=?", (str(e)[:500], doc_id))
