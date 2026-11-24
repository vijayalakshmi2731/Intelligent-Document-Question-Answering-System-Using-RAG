"""RAG evaluation: retrieval (hit@k, MRR, precision@k) and answer (keyword recall, groundedness, abstention)."""
import random, re, statistics, time
from . import vectorstore
from .db import db
from .embeddings import embed_texts, tokenize
from .rag import answer_question, _SENT


def synthetic_cases(user_id: int, n=10, seed=7):
    """Build test cases from the user's own chunks: query = a sentence, target = its chunk."""
    with db() as c:
        rows = c.execute("SELECT c.id,c.document_id,c.text,d.filename FROM chunks c JOIN documents d ON d.id=c.document_id "
                         "WHERE c.user_id=? AND d.status='ready'", (user_id,)).fetchall()
    rng = random.Random(seed)
    rng.shuffle(rows)
    cases = []
    for r in rows:
        sents = [s.strip() for s in _SENT.split(r["text"]) if 6 <= len(tokenize(s)) <= 30]
        if not sents:
            continue
        s = rng.choice(sents)
        keywords = [t for t in tokenize(s)][:6]
        cases.append({"question": s, "expected_chunk_id": r["id"], "expected_document": r["filename"],
                      "keywords": keywords, "synthetic": True})
        if len(cases) >= n:
            break
    return cases


def run_evaluation(user_id: int, cases, top_k=5, use_generation=True):
    results, rr, hits_at_k, precisions, recalls, supports, lat = [], [], [], [], [], [], []
    for case in cases:
        q = case["question"]
        t0 = time.perf_counter()
        qvec = embed_texts([q])[0]
        retrieved = vectorstore.search(user_id, qvec, top_k=top_k)
        r_ms = (time.perf_counter() - t0) * 1000
        rank = None
        for i, h in enumerate(retrieved, 1):
            match = (case.get("expected_chunk_id") == h["chunk_id"]) or \
                    (case.get("expected_document") and case["expected_document"] == h["filename"] and
                     (not case.get("keywords") or any(k in h["text"].lower() for k in case["keywords"])))
            if match:
                rank = i
                break
        rr.append(1 / rank if rank else 0.0)
        hits_at_k.append(1.0 if rank else 0.0)
        rel = sum(1 for h in retrieved if case.get("expected_document") in (None, h["filename"]))
        precisions.append(rel / max(1, len(retrieved)))
        row = {"question": q, "rank": rank, "retrieval_ms": round(r_ms, 1),
               "top_score": round(retrieved[0]["score"], 3) if retrieved else 0}
        if use_generation:
            res = answer_question(user_id, q, top_k=top_k)
            ans = res["answer"].lower()
            kws = [k.lower() for k in case.get("keywords", [])]
            kr = sum(1 for k in kws if k in ans) / len(kws) if kws else None
            if kr is not None:
                recalls.append(kr)
            supports.append(res["meta"].get("support", 0.0))
            lat.append(res["meta"]["total_ms"])
            row.update(answer=res["answer"][:300], keyword_recall=kr, support=res["meta"].get("support"),
                       answered=res["meta"]["answered"], total_ms=res["meta"]["total_ms"])
        results.append(row)
    mean = lambda xs: round(statistics.mean(xs), 4) if xs else None
    summary = {"cases": len(cases), "top_k": top_k, f"hit@{top_k}": mean(hits_at_k), "mrr": mean(rr),
               "precision@k": mean(precisions), "keyword_recall": mean(recalls),
               "groundedness": mean(supports), "avg_latency_ms": mean(lat)}
    return {"summary": summary, "results": results}


def unanswerable_check(user_id: int, questions=None):
    """Hallucination control: off-topic questions should be declined."""
    questions = questions or ["What is the airspeed velocity of an unladen swallow?",
                              "Who won the 1998 FIFA World Cup final?",
                              "What is the recipe for chocolate lava cake?"]
    out = [answer_question(user_id, q) for q in questions]
    declined = sum(1 for o in out if not o["meta"]["answered"])
    return {"questions": questions, "declined": declined, "abstention_rate": declined / len(questions)}
