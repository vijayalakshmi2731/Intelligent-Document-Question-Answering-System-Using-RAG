"""Question processing, retrieval, grounded generation, validation."""
import re, time
import numpy as np
from . import vectorstore
from .config import MIN_RELEVANCE, SUPPORT_THRESHOLD, TOP_K
from .embeddings import embed_texts, tokenize
from .llm import generate, llm_available

INSUFFICIENT = ("I couldn't find enough information in your uploaded documents to answer that. "
                "Try rephrasing, or upload a document that covers this topic.")
_FOLLOWUP = re.compile(r"\b(it|its|they|them|their|this|that|these|those|he|she|there|former|latter|above|same)\b", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+")


def preprocess_query(q: str) -> str:
    return re.sub(r"\s+", " ", q).strip()


def detect_intent(q: str) -> str:
    ql = q.lower()
    rules = [("summary", r"\b(summari[sz]e|summary|overview|tl;?dr|gist)\b"),
             ("comparison", r"\b(compare|difference|versus|vs\.?|differ)\b"),
             ("definition", r"^(what is|what are|define|meaning of|who is)\b"),
             ("procedure", r"^(how (do|to|can|should)|steps|procedure)\b"),
             ("reason", r"^why\b"),
             ("list", r"\b(list|enumerate|name all|what are the)\b"),
             ("quantity", r"^(how (many|much|long|often|far)|when|what (year|date|percentage))\b")]
    for name, pat in rules:
        if re.search(pat, ql):
            return name
    return "factual"


def contextualize(question: str, history) -> str:
    """Make short / pronoun-heavy follow-ups self-contained using the previous user turn."""
    prev = [m["content"] for m in history if m["role"] == "user"]
    if prev and (len(tokenize(question)) <= 4 or _FOLLOWUP.search(question)):
        return f"{prev[-1]} {question}"
    return question


def support_score(answer: str, chunks) -> float:
    """Fraction of answer sentences whose content is supported by retrieved text."""
    body = re.sub(r"\[\d+\]", "", answer)
    sents = [s for s in _SENT.split(body) if len(tokenize(s)) >= 3]
    if not sents or not chunks:
        return 0.0
    cvec = embed_texts([c["text"] for c in chunks])
    ctoks = set(t for c in chunks for t in tokenize(c["text"]))
    ok = 0
    for s, v in zip(sents, embed_texts(sents)):
        toks = set(tokenize(s))
        overlap = len(toks & ctoks) / len(toks)
        if float((cvec @ v).max()) >= SUPPORT_THRESHOLD and overlap >= 0.5:
            ok += 1
    return ok / len(sents)


def answer_question(user_id, question, history=(), top_k=TOP_K, document_ids=None, collection=None):
    t0 = time.perf_counter()
    question = preprocess_query(question)
    intent = detect_intent(question)
    search_q = contextualize(question, history)
    qvec = embed_texts([search_q])[0]
    tr = time.perf_counter()
    hits = vectorstore.search(user_id, qvec, top_k=top_k, document_ids=document_ids, collection=collection)
    retrieval_ms = (time.perf_counter() - tr) * 1000
    top_score = hits[0]["score"] if hits else 0.0
    meta = {"intent": intent, "search_query": search_q, "top_score": round(top_score, 4),
            "retrieval_ms": round(retrieval_ms, 1)}

    # with an LLM the model itself refuses (INSUFFICIENT_CONTEXT); the gate only drops clearly unrelated queries
    gate = min(MIN_RELEVANCE, 0.03) if llm_available() else MIN_RELEVANCE
    if not hits or top_score < gate:
        meta.update(answered=False, reason="insufficient_context", support=0.0, engine="none", llm_ms=0.0)
        meta["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return {"answer": INSUFFICIENT, "sources": [], "meta": meta}

    tl = time.perf_counter()
    raw, engine = generate(question, hits, list(history))
    llm_ms = (time.perf_counter() - tl) * 1000

    if "INSUFFICIENT_CONTEXT" in raw:
        meta.update(answered=False, reason="model_declined", support=0.0, engine=engine, llm_ms=round(llm_ms, 1))
        meta["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return {"answer": INSUFFICIENT, "sources": [], "meta": meta}

    cited = {int(n) for n in re.findall(r"\[(\d+)\]", raw)}
    sup = support_score(raw, hits)
    answer = raw
    if sup < 0.4:
        answer += "\n\n⚠️ Low confidence: parts of this answer may not be fully supported by the documents. Please verify against the sources."
    sources = [{
        "n": i, "document_id": h["document_id"], "filename": h["filename"], "page": h["page"],
        "section": h["section"], "score": round(h["score"], 4), "cited": i in cited or not cited,
        "text": h["text"],
    } for i, h in enumerate(hits, 1)]
    meta.update(answered=True, support=round(sup, 3), engine=engine, llm_ms=round(llm_ms, 1),
                total_ms=round((time.perf_counter() - t0) * 1000, 1))
    return {"answer": answer, "sources": sources, "meta": meta}
