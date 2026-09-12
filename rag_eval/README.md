# Model comparison through the RAG assistant — promptfoo

Compares two local models on the same 20 questions **through the whole assistant**
(retrieval, prompt and grounding included), not as bare models — so the comparison
reflects what a user would actually get.

The backend fixes the answering model server-side (`LLM_MODEL`), so the backend runs
**twice** — one instance per model, on two ports — with one HTTP provider pointed at
each. Retrieval is identical for both; only the answering model differs.

---

## What this eval grades, and why it changed

The first version of this setup asked a single LLM rubric whether each answer was
*"grounded in CMMI/SDLC quality documents"* — while passing the grader **only the
answer text**. The grader never saw the retrieved documents, so it could not verify
grounding, and it failed correct answers with reasoning like:

> *"Since no such source documents were provided as context..."*

Five of twenty questions failed that way, and the resulting scores were not
meaningful. The full write-up is in [`../docs/EVALUATION.md`](../docs/EVALUATION.md).

**What this config does instead:**

1. **Grades against the answer key**, not against groundedness. Every question in
   `promptfooconfig.yaml` carries assertions derived from
   [`../docs/ANSWER-KEY.md`](../docs/ANSWER-KEY.md).
2. **Asserts specific values deterministically** wherever the expected answer has
   one — `AES-256`, `500` TPS, `≤ 2 s`, three failed OTP attempts, masked test data.
   A string or regex match cannot hallucinate, so the questions that previously
   failed are now graded by code rather than by a model.
3. **Uses a rubric only where the answer is open-ended**, and gives it the reference
   answer to compare against — so the grader has something checkable in front of it.
4. **Keeps the shared rubric to what is verifiable from the output alone**: answer
   language matches the question, tone, no self-contradiction, and no invented
   specifics presented as fact.
5. **Tests the honest fallback properly.** The three out-of-scope questions assert
   the fallback notice appears *and* that no URL, repository address or IP was
   invented — a regex, not an opinion. The assistant replies in the language of the
   question, so each asserts the notice in its own language; `tests/test_eval_questions.py`
   fails the suite if an assertion and its question disagree.

Assertion mix: 23 deterministic (19 `icontains`, 4 `javascript`) and 18 rubric
assertions across the 20 questions.

---

## Prerequisites

```bash
# Node.js (for promptfoo) and Ollama installed.
ollama pull gemma4:e4b
ollama pull <the second model you want to compare>
```

Docker (Qdrant) and Ollama must be running, and the project `.venv` installed.

**The collection must be indexed first** — the vector index is not in the repository:

```bash
docker compose up -d qdrant
QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/query/index_cmmi_chunked.py
```

## 1) Start two backend instances

Terminal 1 — model A on port 8013:

```bash
cd <repo>/backend
env QDRANT_URL=http://localhost:6333 \
    OLLAMA_URL=http://localhost:11434 \
    CHAT_COLLECTION=kurumsal_kalite_cmmi_chunked \
    LLM_MODEL=gemma4:e4b \
    ../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8013
```

Terminal 2 — model B on port 8014, identical except `LLM_MODEL` and `--port 8014`.

Wait for `Application startup complete` in both, then verify:

```bash
curl http://localhost:8013/config    # check the "model" field
curl http://localhost:8014/config
```

Update the two `label:` values in `promptfooconfig.yaml` to match the models you
actually started, and the `provider:` on the rubric assertions to a model you have
pulled.

## 2) Run

```bash
cd <repo>/rag_eval
npx promptfoo@latest eval
npx promptfoo@latest view          # side-by-side in the browser
npx promptfoo@latest eval -o results.json    # or .csv / .html
```

---

## Notes

- **Memory.** Two backends means two BGE-M3 instances plus two Ollama models
  resident at once. If that doesn't fit, run them **sequentially**: one backend on
  8013 with model A, `eval -o a.json`; then restart it with model B,
  `eval -o b.json`. Leave a single provider in the config when doing this.
- **Everything stays local.** The rubric grader runs against your local Ollama; no
  data leaves the machine.
- **Questions live in this config**, alongside their assertions, so the two can't
  drift apart. `tests/test_eval_questions.py` checks they stay in step with
  `rag_test_questions.txt`, which the batch runner (`send_test_questions.py`) uses.
- **Latency is high** — expect a couple of minutes per question per model on CPU,
  so a full two-model run is a long coffee break, not a quick check.
