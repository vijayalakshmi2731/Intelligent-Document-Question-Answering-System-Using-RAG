# DocQA – Intelligent Document Question Answering (RAG)

Upload PDF/DOCX/TXT/MD/CSV/HTML documents, then ask questions and get grounded answers with page/section citations.

## Run
Backend: FastAPI (`backend/`). Frontend: Next.js + Tailwind CSS (`web/`).
```bash
cp .env.example .env   # then paste OPENAI_API_KEY (optional)
./run.sh                # backend :8000, frontend http://localhost:3000
```
The first registered user becomes **admin**. Without an API key the system runs in an offline *extractive* mode
(best-matching sentences from retrieved chunks), so the full pipeline still works.

## Pipeline → code
| Step | Module |
|---|---|
| 1 Auth (PBKDF2 + signed tokens, profiles, per-user isolation) | `backend/app/auth.py`, `main.py` |
| 2 Upload / validation / metadata / download / delete | `main.py` |
| 3 Text extraction (PDF per page, DOCX headings, TXT/MD/CSV/HTML; empty-doc detection) | `extract.py` |
| 4 Cleaning + chunking (size/overlap configurable, page & section kept) | `chunking.py` |
| 5 Embeddings (hashing embedder default; `DOCQA_EMBEDDING_BACKEND=st` for sentence-transformers) | `embeddings.py` |
| 6 Vector DB (SQLite + exact cosine, chunk text + metadata) | `vectorstore.py`, `db.py` |
| 7 Query processing / intent / follow-up contextualisation, top-K retrieval | `rag.py` |
| 8 LLM answer generation (OpenAI or extractive fallback) | `llm.py` |
| 9 Source citations + evidence snippets | `rag.py`, UI source cards |
| 10 Chat UI, multiple conversations, history | `web/` |
| 11 RAG evaluation (hit@k, MRR, precision@k, keyword recall, groundedness, off-topic refusal) | `evaluation.py`, Evaluation tab |
| Extra: hallucination control, admin dashboard, analytics, CSV report | `rag.py`, `main.py` |

## Configuration (env)
`DOCQA_TOP_K`, `DOCQA_MIN_RELEVANCE` (refusal threshold), `DOCQA_SUPPORT_THRESHOLD`, `DOCQA_MAX_UPLOAD_MB`,
`DOCQA_DATA_DIR`, `DOCQA_SECRET`, `DOCQA_LLM_MODEL`.

## Tests
`.venv/bin/python -m pytest tests`
