# Project Process Log

## Date
11-06-2026

## Decisions & Actions
- bge-m3 for embeddings using cosine similarity
- introduced metadata tags on simple sample docs
- qdrant for vector db, contains query v, doc vs, doc content metadata
- return using top_k most similar, dense search
- used gemma4:12b initially, but was too slow hence decided to use gemma2:2b for samples

## Future Plans
- Implement hybrid search, merge dense & sparse search
- More data types for samples, eg a priority table
- Try better models, test different prompts
- Try chunking methods

---

## Date
12-06-2026

## Decisions & Actions
- added qdrant's built in sparse search & merged using Reciprocal Rank Fusion
- RRF sums 1 / (k + rank) from both result lists — a document that ranks well in both searches gets a much higher combined score than one that only appears in one
- Added table md and csv + tests

## Future Plans
- Try better models, test different prompts
- Try chunking methods
- Different input types?
- Add long documents to test for chunking

---

## Date
15-06-2026

## Decisions & Actions
- added completed cmmi docs to test context window: very slow, doc format & other formats not tested
- docker compose so docker & backend work at the same time

## Future Plans
- other format inputs
- chunking necessary for faster output & better accuracy
- incomplete cmmi docs to find quality violations
- better model AFTER chunking
- log status (looking at docs etc) & fallback (bulamadım ama genel cevap)
- openrouter gemma4:31b

---

## Date
16-06-2026

## Decisions & Actions
- implemented fallback notice and log
- tried using gemma4:31b on 32GB mac, works better but needs chunking
- implemented parent child chunking & ask_cmmi method (--chunked for chunking --answer for llm answer) & need to index it first

## Future Plans
- Parent child chunking + late chunking merged plan
    - Split documents into parent chunks (e.g., ~2000 chars)
    - Split each parent into child chunks (e.g., ~500 chars with overlap)
    - Encode the entire parent text through the model (late chunking) → child embeddings get context from surrounding text
    - Store child chunks as Qdrant points for retrieval
    - On retrieval, return the parent chunk as LLM context
- Different input files
- incomplete cmmi docs to find quality violations
- better prompt
- openrouter?

---

## Date
17-06-2026

## Decisions & Actions
- implemented late chunking: instead of encoding each child chunk independently (naive), the entire parent text is fed through BGE-M3 in one forward pass. Per-child token spans are mean-pooled from the parent's contextualized hidden states to produce child dense vectors — so each child embedding carries signal from the surrounding parent context. Query encoding stays the same. This is the default; disable with LATE_CHUNKING=0 for a side-by-side comparison.

## Future Plans
- Different input files
- incomplete cmmi docs to find quality violations
- better prompt
- openrouter?

---

## Date
18-06-2026

## Decisions & Actions
- Added single best child scoring for chunking to improve retrieval quality: ranks documents as one entry per doc
- score = best_child + 0.5(sum_children - best_child)
- Implemented xlsx and pptx as input formats
- Improved prompt

## Future Plans
- Incomplete cmmi docs to find quality violations:
    - Where do we check the correct policies?
        - Policy set?
        - Existing documents?
        - LLM judge?
- openrouter?
- make a week by week plan
- start frontend

---

## Date
19-06-2026

## Decisions & Actions
- Changed temperature to 0 for best accuracy for LLM answers
- Implemented frontend starting point & changed /chat to chunked cmmi

## Future Plans
- Incomplete cmmi docs to find quality violations:
    - Where do we check the correct policies?
        - Policy set?
        - Existing documents?
        - LLM judge?
- openrouter?
- make a week by week plan
- improve fronted (search, document view, history etc.)

---

## Date
22-06-2026

## Decisions & Actions
- Added process and time to frontend
- Max context window from 32k to 8k and top_k from 5 to 3, doesnt change speed that much

## Future Plans
- Incomplete cmmi docs to find quality violations:
    - Where do we check the correct policies?
        - Policy set?
        - Existing documents?
        - LLM judge?
- openrouter?
- make a week by week plan
- improve fronted (search, document view, history etc.)
- teknik ama bilmeyenlere yönelik sunum 
- look at notebookllm for inspo

---

## Date
07-07-2026

## Decisions & Actions
- compliance checker started: rule/policy set primary, hybrid with existing docs + llm-as-judge
- rules as yaml per doc type (backend/rules/srs.yaml), added doc_kind to corpus, 10 SRS rules in 3 tiers (structure/traceability/content)
- compliance engine + report: compliant/violations/missing + weighted score, blocker = non_compliant
- content tier uses gemma4:e4b, structure & traceability deterministic (no llm)
- rules editor in UI (crud /rules), plain language for non-technical users, auto ids

## Future Plans
- rules for other doc types (PMP, SAT, BUR)
- eval set: defect -> expected rule id
- upload doc from UI -> compliance check

---

## Date
10-07-2026

## Decisions & Actions
- put together a small test set to check the compliance checker properly: example documents where i already know what the answer should be, so i can measure whether it's really catching the problems
- some of them are broken on purpose (weak or missing sections), and a few are "tricky but actually fine" so the checker doesn't start raising false alarms
- added a few more rules for the requirements document while i was at it; it still passes cleanly on the correct one
- ran it all and it finds the right issues without false alarms, and gives the same result every time

## Future Plans
- keep this test set as a safety net; later throw harder cases at it (several problems in one doc, longer docs, contradictions)
- do the same rules and examples for the other document types

---

## Date
13-07-2026

## Decisions & Actions
- made it possible to see and switch which ai model the compliance checker uses, right from the interface instead of digging into the settings

## Future Plans
- let people upload a document from the interface and check it
- do the same rules and examples for the other document types

---

## Date
16-07-2026

## Decisions & Actions
- you can now upload your own document straight from the interface and run the compliance check on it (word, excel, powerpoint, plain text)
- decided the uploaded file should only be checked and then deleted — it's never stored or added to the system, for privacy
- wrote example questions for each department to show on the start screen, all based on the real quality documents (nothing made up)

## Future Plans
- give the chat a memory so follow-up questions make sense
- do the same rules and examples for the other document types

---

## Date
17-07-2026

## Decisions & Actions
- gave the chat a memory: it now remembers the earlier questions in the same conversation, so a follow-up like "what were the results?" knows what you mean
- this works both when it looks for documents and when it writes the answer, so the context doesn't get lost either way
- made how many past questions it remembers a single setting, so it's easy to adjust in one place

## Future Plans
- make saved chats stick around properly (not just in the browser)
- maybe let the system rephrase trickier follow-up questions on its own
- do the same rules and examples for the other document types

---

## Date
21-07-2026

## Decisions & Actions
- instead of typing out the project stages by hand, wrote something that reads them straight out of the company's process slides
- had to be careful here: the model only keeps a stage if it's actually written in the document, otherwise it starts inventing them
- the "new project" page now lists these stages; there are 11, but the slides only really explain the first 5, so the rest just show as names, and empty ones honestly say there's no info instead of faking it
- to update it later you just drop the new document in and run it again

## Future Plans
- maybe fill in the last stages from the project plan's milestone table, but that's example data so holding off
- do the same rules and examples for the other document types

---

## Date
22-07-2026

## Decisions & Actions
- did the same thing for roles: pulled each role's responsibilities out of the tables in the documents, dropping the example names, phones and project details so only the general facts stay
- the thinking is that people already know their job title — what's actually useful is the specific detail the documents attach to their role
- the "new project" page now highlights the steps that mention your role; if the documents don't mention a role anywhere, it just doesn't highlight anything rather than guessing

## Future Plans
- later, figure out who prepares and approves each document from the signature sections (skipped for now, too messy)
- do the same rules and examples for the other document types

---

## Date
27-07-2026

## Decisions & Actions
- made the chat handle long conversations better. sending the whole history every time gets slow, so it now keeps the recent questions but only a couple of the answers, and squashes the older part into a short "what this chat is about" note that rides along with each question
- this keeps the thread of the conversation without dragging the entire history around; that little summary quietly updates itself in the background as the chat grows, so it stays cheap
- cleaned up how it answers too: no more repeating itself or tacking a summary on the end unless you actually asked for one, and it matches the question — a general question gets a general answer, a specific project keeps its details
- made saved chats stick around: conversations show up in the sidebar to reopen later, each with a delete button, and a reopened chat remembers where it left off
- moved where they're saved from the browser to a small local file on the backend, so history survives clearing the browser and isn't tied to one browser — still entirely on the machine

## Future Plans
- do the same rules and examples for the other document types

---

## Date
30-07-2026

## Decisions & Actions
- started on user profiles (no login yet), just trying the idea out on a separate branch — one example profile per company role
- kept it separate and additive in the database so it doesn't interfere with anything; going back to the main version just ignores it
- you get to it by clicking the profile area in the bottom-left corner, which opens a proper profile page
- the page shows what the documents call that role, how many project stages mention it, and the example questions for that role (which you can click to ask)
- switching profiles switches identity, and the suggested starter questions follow along. names are just placeholders for now, since the real identity is the role

## Future Plans
- swap the placeholder names for real people once there's a login system
- do the same rules and examples for the other document types

---

## Date
05-08-2026

## Decisions & Actions
- fixed a bug where just opening an old chat from the history bumped it up to "today" as if it were new
- now opening a chat only views it — the date changes only when you actually send a new message in it

## Future Plans
- do the same rules and examples for the other document types
- swap the placeholder names for real people once there's a login system

---

## Date
14-08-2026

## Decisions & Actions
- noticed the assistant sometimes answered from the wrong document. dug into it: for each question it was only pulling the top 3 sources, and longer documents whose relevant part is split across several pieces were landing just below that line and never reaching the model
- bumped it from 3 to 5 sources; the borderline long documents now make it in and the answers line up with what's actually written
- added a way to see the exact text the model receives for a question (the instructions, the document context and the question, all together). it writes to a local file, not to the interface — just so i can check what context it had when an answer looks off
- also wrote the compliance rules for the business-requirements (BUR) document, so it's not only the requirements document that gets checked now

## Future Plans
- test the assistant more systematically with a fixed set of questions instead of ad-hoc ones
- keep going on rules for the remaining document types

---

## Date
17-08-2026

## Decisions & Actions
- put together a proper test set for the assistant: 20 questions, half turkish half english, but grouped by what each one is meant to probe rather than by department
- the groups are things like pinpoint questions with one exact answer, broad/general ones, ones that need pulling several documents together, process-flow ones, ones that read the test tables and slides, and a few that are deliberately unanswerable to check it admits when it can't find something
- based every question on the real quality documents, so a wrong answer actually means the retrieval missed rather than the question being made up

## Future Plans
- actually run the assistant through this whole set and record the answers

---

## Date
18-08-2026

## Decisions & Actions
- wrote a small script that fires the whole list of questions at the assistant one after another and saves every question, its answer, and which model produced it into a log file — so i can run a batch without typing them into the interface
- kept the output tidy in its own folder rather than loose in the project (rag_test_logs)

## Future Plans
- use these logs to compare different models on the same questions

---

## Date
19-08-2026

## Decisions & Actions
- set up promptfoo to compare two different local models on the same questions, side by side
- ran each one through the full assistant (retrieval and all), not just the bare model, so the comparison reflects what a user would actually get
- promptfoo chose gemma4:e4b as the better model (gemma4:e4b passed 18/20 tests, muse-glimmer:latest passed 18/20 tests)
- promptfoo's results were incorrect (see promptfoo-results.xlsx), incorrectly failed tests with reason being the information does not exist in the documents but it actually did
- we manually compared both results, both were similar but muse-glimmer had more detail

> [note added later] promptfoo-results.xlsx and the saved transcripts were deleted
> before publishing: the run measured a prompt, corpus and language policy that have
> all since changed, so the numbers describe a system that no longer exists. The
> diagnosis and the corrected harness are in `docs/EVALUATION.md`.

## Future Plans
- run the comparison on the stronger machine and pick a model based on the results
- keep going on rules for the remaining document types