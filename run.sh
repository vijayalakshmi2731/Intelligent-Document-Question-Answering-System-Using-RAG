#!/usr/bin/env bash
# Starts the FastAPI backend (:8000) and the Next.js frontend (:3000).
# Put your OpenAI key in .env (OPENAI_API_KEY=...) for generated answers.
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
[ -d web/node_modules ] || (cd web && npm install)
(cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACK=$!
trap "kill $BACK 2>/dev/null" EXIT
cd web && npm run dev
