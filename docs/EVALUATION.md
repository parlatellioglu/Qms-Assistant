# Evaluation

How the system's accuracy was measured rather than eyeballed. Three separate layers,
because they fail in different ways: unit tests catch broken logic, the compliance
answer key catches a checker that flags the wrong things, and the retrieval question
set catches an assistant that answers confidently from the wrong document.

---

## 1. Unit and integration tests

`pytest` suite in `tests/`, split by what it needs:

- **Standalone** — chunking, the memory window, the rolling summary, process-map
  extraction, the history store, the compliance engine, the compliance eval gate.
  These run with no services up.
- **Needs the stack** — retrieval accuracy and the end-to-end chat API need Qdrant,
  and Ollama for generation.

The process-map suite is the strictest: it verifies that invented phases,
paraphrased values and fabricated quotes are **dropped**, not merely flagged — the
extractor must refuse to output a claim it cannot cite.

```bash
.venv/bin/python -m pytest -q
```

---

## 2. Compliance accuracy — a labelled answer key

`backend/eval/compliance_cases.yaml` pairs documents with the **expected per-rule
verdict**. The point is measuring **false positives** as well as recall, so the set
deliberately includes compliant documents that a naive checker would flag:

| Case | Why it's in the set |
|---|---|
| `real-srs-baseline` | The approved SRS. Any failure here is a false positive. |
| `reworded-compliant-srs` | Same document, reworded — catches a checker matching on literal strings. |
| `original-draft`, `content-gaps-draft`, `skeleton-draft` | Genuinely broken drafts, each targeting a different tier. |
| `security-missing-audit-log`, `continuity-missing-rpo`, `performance-technical-no-numbers`, `scope-soft-exclusion-compliant` | Borderline cases added as false-positive guards after earlier over-flagging. |

`scripts/query/eval_compliance.py` runs the checker over every case and prints a
per-tier confusion matrix. Positive = a defect flagged.

**Current result** (deterministic tiers, 9 cases × 14 labels):

```
  structure     TP= 11 FP=  0 FN=  0 TN= 52   precision=1.00  recall=1.00
  traceability  TP=  1 FP=  0 FN=  0 TN= 17   precision=1.00  recall=1.00
  ALL           TP= 12 FP=  0 FN=  0 TN= 69   precision=1.00  recall=1.00
```

The 45 content-tier labels are reported **UNGRADED** without `--content` rather than
counted as passes — an un-wired judge must not flatter the score. The harness exits
non-zero on any false positive, negative or error, so it can gate a change to the
rules or the judge prompt. `tests/test_compliance_eval.py` guards this offline.

```bash
.venv/bin/python scripts/query/eval_compliance.py            # deterministic tiers
.venv/bin/python scripts/query/eval_compliance.py --content  # + LLM-as-judge
```

---

## 3. Retrieval quality — a capability-grouped question set

[`TEST-QUESTIONS.md`](TEST-QUESTIONS.md) holds 20 questions, 10 Turkish and 10
English, grouped **by the retrieval behaviour they probe** rather than by department:

| Group | What it tests |
|---|---|
| Pinpoint retrieval | Can it pull an exact list from one section of one document? |
| Broad synthesis | Can it answer a conceptual question across many sources without drowning in one? |
| Cross-document comparison | Can it contrast two plans, or chain four documents together? |
| Procedural / next-step | Can it locate a position in a process and name the correct next stage? |
| Structured data | Can it read an exact value out of a spreadsheet row or an ordered list out of slides? |
| Out-of-scope | Does it say "I couldn't find this" instead of inventing an answer? |

Every question is grounded in the actual indexed documents, so a wrong answer means
retrieval genuinely missed — not that the question was unanswerable. The last group
exists to test the honest fallback, which is easy to lose during prompt tuning.

[`ANSWER-KEY.md`](ANSWER-KEY.md) records the expected answer for each, with the
source document it comes from — except the three out-of-scope questions, whose
correct answer is that the documents do not contain one. `send_test_questions.py` fires the whole set at a running backend and logs
every question, answer and its metadata to `rag_test_logs/`, so a batch can be run
without typing into the UI. That output is gitignored: a transcript is tied to one
corpus, model and prompt version, so a stale one misleads more than it documents.

```bash
python3 send_test_questions.py --url http://localhost:8013
```

---

## 4. Model comparison — and why its results were discarded

Two local models were compared **through the full RAG pipeline**, not as bare models,
so the comparison would reflect what a user actually gets. Because the backend fixes
the model server-side, that means running two backend instances on different ports
and pointing one promptfoo HTTP provider at each (`rag_eval/`).

The two models scored within a point of each other. **Those scores are not published
here, because they turned out to measure two things that were broken.**

**The grader could not see what it was grading.** The rubric asked whether each
answer was "grounded in CMMI/SDLC quality documents", but the provider handed it only
the **answer text** — never the retrieved documents. So it reasoned, in its own words:

> *"Since no such source documents were provided as context..."*

and failed answers that were correct and properly grounded. Reading the transcripts
by hand confirmed the information was in the documents and reported accurately.

**The same rubric also required the answer to match the question's language** — and
at the time the prompt instructed the model to *always answer in Turkish*. Every one
of the ten English questions was therefore answered in Turkish and penalised for it.
That half of the failures was real, but it was measuring a deliberate design choice,
not model quality. The assistant now [answers in the question's
language](ARCHITECTURE.md#42-grounded-generation-and-honest-fallback), so those
results describe behaviour the system no longer has.

Between a grader that could not verify its own criterion and a corpus, prompt and
language policy that have all since changed, the run was worth keeping as a lesson
and worthless as a measurement. The export and the saved transcripts were deleted
rather than shipped with caveats attached.

**Three lessons, all worth more than the scores:**

1. **An LLM judge can only grade what it is shown.** A groundedness rubric needs the
   retrieved context passed to the grader, or it is really grading plausibility.
2. **A judge's failure mode is silent.** It produced confident, well-written reasons
   for verdicts that were wrong. Nothing in the output looked broken.
3. **Check what a failing assertion is actually measuring.** Half of these failures
   were the rubric correctly catching a property of the *system design* rather than
   anything about the model under test.

A rerun is possible but has not been done: the comparison model is an ~18 GB
download and CPU generation runs a couple of minutes per question, so a full
two-model pass is hours of compute for a comparison that was already close. The
harness below is corrected and ready for whenever that is worth spending.

### Running your own comparison

Everything needed to compare two models on the bundled corpus is in the repository.
Both routes need the collection indexed first and Ollama running.

**Automated — pass/fail per assertion.** Start the backend twice, once per model, on
ports 8013 and 8014 (only `LLM_MODEL` differs), then:

```bash
cd rag_eval && npx promptfoo@latest eval && npx promptfoo@latest view
```

Each question is graded by the assertions described below, and `view` shows the two
models side by side per question. `rag_eval/README.md` has the full step-by-step,
including how to run sequentially on one port if two models won't fit in memory.

**By hand — transcripts you read yourself.** The batch runner fires all 20 questions
at one backend and records the answer plus its metadata (which model, whether the
backend considered it grounded, the top score, which documents were retrieved):

```bash
python3 send_test_questions.py --url http://localhost:8013
# restart the backend with the other model, then run it again
```

It writes a readable `.log` and a machine-readable `.jsonl` to `rag_test_logs/`.
Compare the two runs against [`ANSWER-KEY.md`](ANSWER-KEY.md), which gives the
expected answer and, for the 17 answerable questions, **the source document it comes
from** — so a wrong answer tells you whether retrieval fetched the wrong document or
generation misread the right one. Only the Python standard library is needed, so this works on a machine
with no project dependencies installed.

**If you swapped in your own corpus**, the question set and answer key no longer
apply — they are specific to the bundled documents, and so are the deterministic
assertions. You would write your own. The transferable part is the shape:

- **Group questions by the retrieval behaviour they probe**, not by department. The
  six groups in [`TEST-QUESTIONS.md`](TEST-QUESTIONS.md) are a starting template.
- **Include questions the documents genuinely cannot answer.** They are the only
  ones that test the honest fallback, and they are the first thing to break when
  prompts are tuned.
- **Record the source document alongside each expected answer**, so a failure
  localises to retrieval or to generation.
- **Assert exact values deterministically** wherever the expected answer has one;
  reserve the model-graded rubric for genuinely open-ended answers.

### The rewritten harness

`rag_eval/promptfooconfig.yaml` has since been rebuilt around the diagnosis. Rather
than asking a model whether an answer is grounded — which it cannot know from the
answer alone — every question is graded against [`ANSWER-KEY.md`](ANSWER-KEY.md):

- **23 deterministic assertions** (19 `icontains`, 4 `javascript` regex) covering
  every expected value the key specifies: `AES-256`, `500` TPS, `≤ 2 s`, three failed
  OTP attempts, masked test data, the lifecycle phase names. A string match cannot
  hallucinate, so the five questions that previously failed are now graded by code.
- **18 rubric assertions**, used only where the expected answer is genuinely
  open-ended (synthesis and comparison questions), and each one is handed the
  reference answer to compare against instead of an abstract quality bar.
- **The shared rubric now only asserts what is checkable from the output alone**:
  the answer's language matches the question, the tone is professional, it doesn't
  contradict itself, and it doesn't present invented specifics as fact.
- **The three out-of-scope questions assert the fallback properly** — the notice must
  appear *and* a regex must confirm no IP address, repository URL or credential was
  invented alongside it. That's the check the old rubric was least able to make.
  Because the assistant answers in the question's language, each of these asserts the
  notice **in its own language** — the two Turkish questions look for the Turkish
  notice, the English one for the English notice. `tests/test_eval_questions.py`
  cross-checks that pairing, so a mismatched assertion fails the suite rather than
  failing every eval run for the wrong reason.

The numbers above the fold predate this rewrite and were produced by the flawed
harness; they are kept as the record of what happened rather than as a result. A
rerun needs the stack up and a fresh index, since the corpus text has changed since
that run. `tests/test_eval_questions.py` guards the question set against drift
between the harness and the batch runner.
