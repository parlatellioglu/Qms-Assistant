#!/usr/bin/env bash
# Run the whole app (frontend + backend) with ONE command.
#
#   ./run.sh
#
# Then open  http://127.0.0.1:8013  in your browser.
#
# The local FastAPI backend serves BOTH the API and the frontend SPA, so there is
# no separate frontend server to start. Qdrant runs in Docker (it holds your
# indexed collections); the stale Docker backend container is stopped so it does
# not fight for port 8013. Ollama must be running locally for answers.
set -euo pipefail
cd "$(dirname "$0")"

# Single source of truth: pull the service endpoints (and everything else) from
# config.yaml. Any variable already set in the environment still wins, so you can
# override one run with e.g. `LLM_MODEL=... ./run.sh`. Falls back to the built-in
# defaults if a value isn't in the file. See backend/config.py.
eval "$(cd backend && ../.venv/bin/python config.py --print-env 2>/dev/null || true)"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"

echo "1/3  Qdrant (Docker) — starting if not already up..."
# Non-fatal: if Qdrant is already running (or Docker is mid-startup), don't let a
# transient hiccup here abort the script — the reachability check below is the
# real gate. Needs Docker Desktop to be running.
docker compose up -d qdrant || echo "     (docker compose up atlandı; erişilebilirlik aşağıda kontrol edilecek)"
# Stop the old containerised backend so the local one below owns :8013.
docker compose stop backend >/dev/null 2>&1 || true

echo "2/3  Checks..."
curl -sf -o /dev/null "$QDRANT_URL/collections" \
  && echo "     Qdrant OK ($QDRANT_URL)" \
  || { echo "     ERROR: Qdrant not reachable at $QDRANT_URL"; exit 1; }
curl -sf -o /dev/null "$OLLAMA_URL/api/tags" \
  && echo "     Ollama OK ($OLLAMA_URL)" \
  || echo "     WARNING: Ollama not reachable at $OLLAMA_URL — retrieval will work, but answers will show an error until Ollama is running."

echo "3/3  Backend + frontend on http://127.0.0.1:8013  (Ctrl-C to stop)"
echo "     The embedding model loads on first start; wait for 'Application startup complete', then open the URL."
# The endpoints are exported above; the backend re-reads config.yaml on startup
# too, so no need to hard-code them here.
cd backend
exec ../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8013
