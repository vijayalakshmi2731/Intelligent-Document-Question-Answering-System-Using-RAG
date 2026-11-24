"""LLM generation. Uses OpenAI when OPENAI_API_KEY is set; otherwise an extractive fallback."""
import re
import numpy as np
from .config import LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL
from .embeddings import embed_texts, tokenize

SYSTEM = """You are a document question-answering assistant. Answer ONLY from the numbered context passages provided.
Rules:
- If the passages do not contain the answer, reply exactly: INSUFFICIENT_CONTEXT
- Never use outside knowledge or guess. Do not invent facts, numbers or names.
- Cite supporting passages inline like [1] or [2][3] after each claim.
- Be concise and write in natural language."""

_SENT = re.compile(r"(?<=[.!?])\s+")


def llm_available() -> bool:
    return bool(OPENAI_API_KEY)


def _format_context(chunks):
    return "\n\n".join(
        f"[{i}] (source: {c['filename']}"
        f"{', page ' + str(c['page']) if c['page'] else ''}"
        f"{', section: ' + c['section'] if c['section'] else ''})\n{c['text']}"
        for i, c in enumerate(chunks, 1))


def generate_openai(question, chunks, history):
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    msgs.append({"role": "user", "content": f"Context passages:\n\n{_format_context(chunks)}\n\nQuestion: {question}"})
    r = client.chat.completions.create(model=LLM_MODEL, messages=msgs, temperature=0.1, max_tokens=900)
    return (r.choices[0].message.content or "").strip()


def generate_extractive(question, chunks, max_sents=4):
    """Offline fallback: pick the most question-relevant sentences from the retrieved chunks."""
    cands = []
    for ci, c in enumerate(chunks, 1):
        for s in _SENT.split(c["text"]):
            s = s.strip()
            if len(s) > 25:
                cands.append((ci, s))
    if not cands:
        return "INSUFFICIENT_CONTEXT"
    qv = embed_texts([question])[0]
    sv = embed_texts([s for _, s in cands])
    qt = set(tokenize(question))
    scores = sv @ qv + np.array([0.15 * len(qt & set(tokenize(s))) / (len(qt) or 1) for _, s in cands])
    top = sorted(np.argsort(-scores)[:max_sents])
    if scores[np.argsort(-scores)[0]] < 0.08:
        return "INSUFFICIENT_CONTEXT"
    return " ".join(f"{cands[i][1]} [{cands[i][0]}]" for i in top)


def generate(question, chunks, history):
    if llm_available():
        try:
            return generate_openai(question, chunks, history), "openai:" + LLM_MODEL
        except Exception as e:
            print(f"[llm] OpenAI call failed, using extractive fallback: {e}")
    return generate_extractive(question, chunks), "extractive"
