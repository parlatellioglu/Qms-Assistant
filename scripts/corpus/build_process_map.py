#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Derive the project lifecycle ("how projects start and progress here") from the
loaded documents and emit it as a build artifact: backend/data/process_map.json.

This is *extraction*, not authoring. Nothing about CMMI, MPR or any particular
phase vocabulary is baked in — whatever lifecycle the loaded documents describe
is the lifecycle that comes out. Point it at a different company's corpus and it
regenerates their process. If the documents don't define a lifecycle at all, it
emits an empty map rather than inventing a plausible one.

Pipeline:
  1. classify   which documents *define* a process (vs. instances of one)
  2. phases     extract the ordered phase list from those documents
  3. details    per phase: deliverables, entry/exit criteria, gate
  4. validate   drop every claim that has no citation
  5. merge      apply backend/data/process_map.overrides.json, if present
Re-run whenever the corpus changes:
    python3 scripts/corpus/build_process_map.py --report

The output is regenerated wholesale; hand-edits belong in the overrides file so
they survive a rebuild.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.doc_extract import SUPPORTED_EXTENSIONS, extract_file  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data")
# Where source documents live, relative to data/. Configurable because a real
# corpus will not arrive in the two folders the CMMI sample happens to use, and a
# document in an unscanned folder is invisible with no error to notice.
SRC_DIRS = [d.strip() for d in
            os.getenv("PROCESS_MAP_SRC_DIRS", "CMMI_completed,CMMI_xlsx_pptx").split(",")
            if d.strip()]
# Output lives under backend/data/ (like cmmi_docs.py) rather than data/: that is
# what the dockerized backend can read, and it is tracked in git, whereas data/ is
# the ignored source-document tree.
BACKEND_DATA_DIR = os.path.join(ROOT, "backend", "data")
OUT_PATH = os.path.join(BACKEND_DATA_DIR, "process_map.json")
OVERRIDES_PATH = os.path.join(BACKEND_DATA_DIR, "process_map.overrides.json")

# The extraction tier is a config knob on purpose: structured pull-out is harder
# than Q&A, so this is the first thing to point at a larger model.
MODEL = os.getenv("PROCESS_MAP_MODEL", os.getenv("LLM_MODEL", "gemma4:e4b"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
WINDOW_CHARS = int(os.getenv("PROCESS_MAP_WINDOW_CHARS", "6000"))


# --------------------------------------------------------------------------- #
# LLM plumbing
# --------------------------------------------------------------------------- #

def _ollama_json(prompt: str, model: str = MODEL, timeout: int = 180) -> dict:
    """One constrained-JSON generation. Returns {} when the model emits garbage.

    Deterministic settings (temperature 0, fixed seed) so a rebuild over an
    unchanged corpus produces an unchanged map — a process map that shifted on
    every run would be unreviewable.
    """
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 42, "num_ctx": 8192},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8")).get("response", "")
        return json.loads(raw) if raw.strip() else {}
    except Exception as exc:                      # noqa: BLE001 - report and skip
        print(f"    ! extraction call failed: {exc}", file=sys.stderr)
        return {}


# --------------------------------------------------------------------------- #
# Source loading + windowing
# --------------------------------------------------------------------------- #

def load_documents() -> List[Dict]:
    """Every supported file under the source dirs, flattened to text.

    Walks subdirectories: real corpora arrive foldered by department or year, and
    a top-level-only scan would skip them silently.
    """
    docs = []
    for sub in SRC_DIRS:
        directory = os.path.join(DATA_DIR, sub)
        if not os.path.isdir(directory):
            print(f"  ! source dir not found: {directory}", file=sys.stderr)
            continue
        for root, _, names in os.walk(directory):
            for name in sorted(names):
                if not name.lower().endswith(SUPPORTED_EXTENSIONS) or name.startswith("~$"):
                    continue
                path = os.path.join(root, name)
                try:
                    text = extract_file(path, name)
                except Exception as exc:          # noqa: BLE001
                    print(f"  ! could not read {name}: {exc}", file=sys.stderr)
                    continue
                if text.strip():
                    docs.append({"id": os.path.splitext(name)[0], "path": path, "text": text})
    return docs


def windows(doc: Dict) -> List[Dict]:
    """Split a document into citable windows.

    Slide decks split on their ``[Slide N]`` markers so a citation can name the
    slide; everything else falls back to line ranges. Either way each window
    carries a human-checkable locator.
    """
    text = doc.get("text") or ""
    out: List[Dict] = []

    if "[Slide " in text:
        chunks = re.split(r"(?=\[Slide \d+\])", text)
        buf, first, last = "", None, None
        for chunk in chunks:
            if not chunk.strip():
                continue
            match = re.match(r"\[Slide (\d+)\]", chunk)
            number = match.group(1) if match else None
            if first is None:
                first = number
            if len(buf) + len(chunk) > WINDOW_CHARS and buf:
                out.append({"locator": _slide_locator(first, last), "text": buf})
                buf, first = chunk, number
            else:
                buf += chunk
            last = number or first
        if buf:
            out.append({"locator": _slide_locator(first, last), "text": buf})
        return out

    lines = text.split("\n")
    buf, start = "", 1
    for i, line in enumerate(lines, start=1):
        if len(buf) + len(line) > WINDOW_CHARS and buf:
            out.append({"locator": f"lines {start}-{i - 1}", "text": buf})
            buf, start = line + "\n", i
        else:
            buf += line + "\n"
    if buf.strip():
        out.append({"locator": f"lines {start}-{len(lines)}", "text": buf})
    return out


def _slide_locator(first: Optional[str], last: Optional[str]) -> str:
    if first and last and first != last:
        return f"slides {first}-{last}"
    return f"slide {first}" if first else "slide ?"


# --------------------------------------------------------------------------- #
# Stage 1 — which documents define a process?
# --------------------------------------------------------------------------- #

CLASSIFY_PROMPT = """You are analysing a corporate document to decide what KIND of document it is.

A document is PROCESS-DEFINING if it describes, in general terms, how projects are
run: lifecycle phases, stages, gates, required deliverables, entry/exit criteria.
A document is an INSTANCE if it is the output of such a process for one specific
project (a filled-in requirements spec, a test plan for one system, a report).

Answer ONLY with JSON:
{{"process_defining": true|false, "confidence": 0.0-1.0, "reason": "<one short sentence>"}}

Document id: {doc_id}
Document text (beginning):
{excerpt}
"""


CACHE_PATH = os.path.join(BACKEND_DATA_DIR, "process_map.cache.json")


def _load_cache() -> Dict:
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: Dict) -> None:
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=1)
    except OSError as exc:                        # noqa: BLE001 - cache is optional
        print(f"  ! could not write cache: {exc}", file=sys.stderr)


def _doc_fingerprint(doc: Dict) -> str:
    """Identity of a document's *content*, so an untouched file reuses its verdict."""
    try:
        stat = os.stat(doc["path"])
        return f"{int(stat.st_mtime)}:{stat.st_size}"
    except (KeyError, OSError):
        return str(len(doc.get("text") or ""))


_CACHE: Dict = {}


def classify(doc: Dict) -> Dict:
    """Is this document the process itself, or one project's paperwork?

    Cached on file mtime+size. Classification is one call per document and the
    answer only changes when the file does, so on a real corpus of hundreds of
    documents this is the difference between a rebuild costing minutes and hours.
    """
    key, fingerprint = doc["id"], _doc_fingerprint(doc)
    hit = _CACHE.get(key)
    if hit and hit.get("fingerprint") == fingerprint:
        return {**hit["verdict"], "cached": True}

    verdict = _ollama_json(CLASSIFY_PROMPT.format(doc_id=doc["id"], excerpt=doc["text"][:WINDOW_CHARS]))
    result = {
        "process_defining": bool(verdict.get("process_defining")),
        "confidence": float(verdict.get("confidence") or 0.0),
        "reason": (verdict.get("reason") or "").strip(),
    }
    # An empty response means the call failed; caching that would make one bad run
    # stick until the file is touched.
    if verdict:
        _CACHE[key] = {"fingerprint": fingerprint, "verdict": result}
    return result


# --------------------------------------------------------------------------- #
# Stage 2 — ordered phase list, driven by document structure
# --------------------------------------------------------------------------- #
# Sliding a window over the document and unioning whatever looks like an ordered
# list of steps does not work, at any window size. Process documents describe
# several different ordered things — the lifecycle at two levels of granularity,
# the management activities inside one phase, supporting process areas — and
# locally they are indistinguishable: "Initiate the Project" reads exactly like a
# phase until you notice it sits between the "Project Planning Phase" and
# "Procurement Phase" headers. Wide windows conflate granularities; narrow ones
# promote activities to phases. Telling them apart needs the document's own
# structure, so that is what these stages read: build an outline, ask which
# sections define the lifecycle, then extract only from those.

def outline(doc: Dict) -> List[Dict]:
    """Section markers with their titles — a table of contents for the document.

    Slide decks give this up cheaply (slide number + first line). Anything else
    falls back to one entry per window, keyed on its locator, so downstream
    stages work the same way regardless of source format.
    """
    text = doc.get("text") or ""
    if "[Slide " in text:
        entries, current = [], None
        for line in text.split("\n"):
            match = re.match(r"\[Slide (\d+)\]", line)
            if match:
                current = match.group(1)
                continue
            if current and line.strip():
                entries.append({"marker": current, "title": line.strip()[:80]})
                current = None
        return entries
    return [{"marker": w["locator"], "title": w["text"].strip().split("\n")[0][:80]}
            for w in windows(doc)]


LOCATE_PROMPT = """Below is the table of contents of a process document, as "<marker>: <title>".

Identify two things:
1. "sequence_markers" — the sections that lay out the OVERALL lifecycle sequence
   (overview/summary sections naming the phases in order). Usually very few.
2. "phase_sections" — sections that BEGIN the detailed treatment of one phase,
   with the phase name as written.

Do NOT list sections that describe activities, policies or supporting processes
*within* a phase — only sections that introduce a phase itself.
If the document defines no lifecycle, return empty lists.

Answer ONLY with JSON:
{{"sequence_markers": ["<marker>", ...],
  "phase_sections": [{{"phase": "<name as written>", "marker": "<marker>"}}]}}

Table of contents of {doc_id}:
{toc}
"""


def locate_process_sections(doc: Dict, entries: List[Dict]) -> Dict:
    """One cheap call over the outline: where is the lifecycle described?"""
    toc = "\n".join(f"{e['marker']}: {e['title']}" for e in entries)
    result = _ollama_json(LOCATE_PROMPT.format(doc_id=doc["id"], toc=toc[:12000]))
    markers = [str(m) for m in (result.get("sequence_markers") or [])]
    sections = [{"phase": (s.get("phase") or "").strip(), "marker": str(s.get("marker") or "")}
                for s in (result.get("phase_sections") or [])
                if (s.get("phase") or "").strip()]
    return {"sequence_markers": markers, "phase_sections": sections}


def slice_markers(doc: Dict, markers: List[str]) -> str:
    """The text of the named sections only (slide decks), else the whole document."""
    text = doc["text"]
    if "[Slide " not in text or not markers:
        return text[:WINDOW_CHARS * 2]
    wanted = {_marker_id(m) for m in markers}
    keep, current = [], None
    for line in text.split("\n"):
        match = re.match(r"\[Slide (\d+)\]", line)
        if match:
            current = match.group(1)
        if current in wanted:
            keep.append(line)
    return "\n".join(keep)


SEQUENCE_PROMPT = """Extract the project lifecycle phase sequence stated in this text.

Rules:
- Give the MOST DETAILED complete sequence the text states. If it shows both a
  high-level and an expanded breakdown, return the expanded one.
- Do not include activities or tasks that happen *within* a phase.
- Keep names exactly as written. Do not translate, normalise or invent.
- "order" is the phase's position, starting at 1.
- If no lifecycle sequence is stated, return {{"phases": []}}.

Answer ONLY with JSON:
{{"phases": [{{"name": "<as written>", "order": <int>, "evidence": "<short quote>"}}]}}

Text ({locator} of {doc_id}):
{window}
"""


def extract_phases(doc: Dict) -> List[Dict]:
    """The document's canonical phase sequence.

    Reads the outline to find where the lifecycle is summarised, then extracts
    the sequence from those sections in a single call, so one authoritative
    ordering comes back instead of one per window.
    """
    entries = outline(doc)
    located = locate_process_sections(doc, entries)
    markers = [_marker_id(m) for m in located["sequence_markers"]]
    locator = f"slides {', '.join(markers)}" if markers else "whole document"

    source_text = slice_markers(doc, markers)
    if not _require_text(source_text, f"{doc['id']} sequence ({locator})"):
        return []

    result = _ollama_json(SEQUENCE_PROMPT.format(
        locator=locator, doc_id=doc["id"], window=source_text))

    phases, seen = [], set()
    for item in result.get("phases") or []:
        name = (item.get("name") or "").strip()
        evidence = (item.get("evidence") or "").strip()
        if not name or _norm(name) in seen:
            continue
        if not _evidence_holds(evidence, source_text):
            print(f"    ~ dropped '{name}': evidence not found in source", file=sys.stderr)
            continue                              # unverifiable claim -> dropped
        seen.add(_norm(name))
        order = item.get("order")
        phases.append({
            "name": name,
            "order": order if isinstance(order, int) else None,
            "sources": [{"doc": doc["id"], "locator": locator, "quote": evidence[:200]}],
            "section_marker": next((_marker_id(s["marker"]) for s in located["phase_sections"]
                                    if _same_phase(s["phase"], name)), None),
        })
    return phases


def _norm(name: str) -> str:
    """Fold case, whitespace and punctuation so 'DEV'T' and "Dev't" merge."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _phase_key(name: str) -> str:
    """Normalised phase name with any trailing "Phase"/"Stage" noun dropped.

    A document names the same phase two ways: the sequence overview calls it
    "Ideation" while its section header reads "Ideation Phase". Matching those
    on the raw name leaves every phase unlinked to its own section.
    """
    return re.sub(r"(phase|stage|asamasi|asama)$", "", _norm(name))


def _same_phase(a: str, b: str) -> bool:
    """Do these two names refer to the same phase?"""
    key_a, key_b = _phase_key(a), _phase_key(b)
    if not key_a or not key_b:
        return False
    return key_a == key_b or key_a.startswith(key_b) or key_b.startswith(key_a)


def _marker_id(marker: str) -> str:
    """The bare section id from whatever shape the model returned it in.

    Models answer "15" or "15: High Level Solutions Delivery Life Cycle"
    interchangeably. Matching the second form against a bare slide number
    silently selects nothing, which used to hand the extractor an empty
    document — see ``_require_text``.
    """
    match = re.match(r"\s*(\d+)", str(marker))
    return match.group(1) if match else str(marker).strip()


# An evidence quote shorter than this can't be meaningfully checked against the
# source (a two-word quote matches almost anything), so it is not accepted.
MIN_EVIDENCE_CHARS = 12


def _evidence_segments(evidence: str) -> List[str]:
    """The quotable runs of a citation, with the model's own scaffolding removed.

    Models cite the way a person does: they name the location and elide the dull
    middle — ``"[Slide 23]\\n... IT effort shall not take longer than 4 man-hours"``.
    Neither the marker nor the ellipsis appears in the source, so comparing the
    raw string rejects a perfectly good quote for its punctuation. Split on that
    scaffolding and check the surviving runs.
    """
    text = re.sub(r"\[slide \d+\]", " ", evidence, flags=re.I)
    parts = re.split(r"\.\.\.|…|\n|\|", text)
    return [seg for seg in (re.sub(r"\s+", " ", p).strip().lower() for p in parts)
            if len(seg) >= MIN_EVIDENCE_CHARS]


def _evidence_holds(evidence: str, source_text: str) -> bool:
    """Is this quote actually in the document, or did the model invent it?

    The citation rule is only worth anything if the citation is verified: a model
    that fabricates a phase fabricates its evidence too, so requiring the field to
    be *present* catches nothing. But the check has to reject fabrications without
    also rejecting real quotes — a filter that drops true content is its own kind
    of lie. One substantial run matching the source is the balance: a fabricated
    quote has no such run, an elided real one always does.
    """
    haystack = re.sub(r"\s+", " ", source_text).lower()
    return any(seg in haystack or seg[:80] in haystack
               for seg in _evidence_segments(evidence))


def _require_text(text: str, what: str) -> bool:
    """Refuse to run an extraction prompt against empty context.

    Asking a model to extract a lifecycle from an empty string does not return
    nothing — it returns a confident, generic, entirely invented one.
    """
    if len(text.strip()) < 50:
        print(f"    ! {what}: no text selected — skipping rather than "
              f"extracting from nothing", file=sys.stderr)
        return False
    return True


# --------------------------------------------------------------------------- #
# Stage 3 — per-phase detail
# --------------------------------------------------------------------------- #

# One question per call. Asking for deliverables, entry criteria, exit criteria,
# gate and policies in a single structured response overloads a small model: it
# answered a five-field schema by *inventing a sixth field* ("process_details")
# and relocating most of the content into it, where the parser silently dropped
# it. A uniform one-field {"items": [...]} shape removes that pressure — and the
# lesson matches stage 2, where one focused question beat several overlapping ones.
FIELD_PROMPT = """From the text below, extract {description} for the project phase "{phase}".

Rules:
- Extract ONLY what the text states. If it states none, return {{"items": []}}.
- Every item needs an "evidence" quote copied verbatim from the text. No quote, no item.
- Keep the wording as written. Do not translate, summarise or invent.

Answer ONLY with JSON, using exactly these keys:
{{"items": [{{"value": "<the item>", "evidence": "<verbatim quote>"}}]}}

Text ({locator}):
{window}
"""

GATE_PROMPT = """Does the text state a GATE, milestone or formal approval that ends the
project phase "{phase}"?

Rules:
- Only answer with a gate the text explicitly ties to the END of this phase.
- A section heading or the phase's own name is NOT a gate.
- If the text states no such gate, return {{"gate": null}}.
- The "evidence" must be a verbatim quote from the text.

Answer ONLY with JSON:
{{"gate": {{"value": "<gate name>", "evidence": "<verbatim quote>"}}}} or {{"gate": null}}

Text ({locator}):
{window}
"""

# field -> (output key, what to ask the model for)
DETAIL_FIELDS = [
    ("deliverables", "name", "the documents, outputs or artifacts this phase produces"),
    ("entry_criteria", "text", "the conditions that must be met BEFORE this phase can begin"),
    ("exit_criteria", "text", "the conditions that must be met for this phase to be complete"),
    ("policies", "text", "the rules or policies that govern how this phase is carried out"),
]

LIST_FIELDS = [(field, key) for field, key, _ in DETAIL_FIELDS]


def _value_grounded(value: str, source_text: str) -> bool:
    """Is the item itself lifted from the document, or composed about it?

    Distinct from ``_evidence_holds``: a citation needs enough length to be worth
    checking, but an item is often correctly short — "SRS", "PMP", "DAR Record".
    Here presence is the whole test, so no minimum applies.
    """
    haystack = re.sub(r"\s+", " ", source_text).lower()
    needle = re.sub(r"\s+", " ", value).strip().lower()
    return bool(needle) and (needle in haystack or needle[:80] in haystack)


def _is_heading(name: str, doc: Dict) -> bool:
    """Is this the title of a section rather than a gate?

    Asked what gate ends Project Planning, the model answered "Complete Project
    Planning" — the title of a slide inside that section. Checking against the
    document's own headings catches this generically, without teaching the
    extractor that gates here happen to be called "Gate N".
    """
    key = _norm(name)
    return bool(key) and any(_norm(entry["title"]) == key for entry in outline(doc))


def _warn_unexpected_keys(result: Dict, expected: set, context: str) -> None:
    """Surface schema drift instead of silently discarding what it carries.

    A model under schema pressure invents fields. Reading only the keys we asked
    for turns that into invisible data loss — an empty phase that looks like the
    document said nothing.
    """
    extra = set(result) - expected
    if extra:
        print(f"    ~ {context}: model returned unexpected key(s) {sorted(extra)} — "
              f"content there is being dropped", file=sys.stderr)


def phase_windows(phase: Dict, phases: List[Dict], doc: Dict, wins: List[Dict]) -> List[Dict]:
    """The windows belonging to this phase's section of the document.

    When the outline told us where the phase's section starts, the section runs
    to the next phase's start — so the activities under a "Project Planning
    Phase" header are read as that phase's detail rather than as phases of their
    own. Falls back to name matching when the document has no such structure.
    """
    start = phase.get("section_marker")
    if start and start.isdigit():
        later = sorted(int(p["section_marker"]) for p in phases
                       if (p.get("section_marker") or "").isdigit()
                       and int(p["section_marker"]) > int(start))
        end = later[0] if later else 10 ** 6
        markers = [str(n) for n in range(int(start), end)]
        text = slice_markers(doc, markers)
        if text.strip():
            return [{"locator": f"slides {start}-{end - 1 if later else 'end'}", "text": text}]

    # The document has sections, but not for this phase — so it names the phase in
    # its sequence without ever detailing it. Scavenging whatever window happens to
    # mention the word invents attributions: it is how "Launch" acquired an entry
    # criterion of "Initiate the Project" (a Project Planning activity) and how one
    # gate got attached to three different phases. No section, no details.
    if any((p.get("section_marker") or "").isdigit() for p in phases):
        return []
    return [w for w in wins if _norm(phase["name"])[:8] in _norm(w["text"])]


def extract_details(phase: Dict, doc: Dict, wins: List[Dict]) -> None:
    """Fill a phase in place from ``wins``, the windows describing this phase."""
    relevant = wins
    for field, _ in LIST_FIELDS:
        phase.setdefault(field, [])
    phase.setdefault("gate", None)

    for win in relevant:
        if not _require_text(win["text"], f"{phase['name']} detail ({win['locator']})"):
            continue
        source = {"doc": doc["id"], "locator": win["locator"]}

        # One sentence is one fact. Asked separately for criteria and policies,
        # the model files the same sentence under both — "Cost is greater than or
        # equal to 6M PHP" arrived as an exit criterion *and* a policy. Claim each
        # value once, in the first field that reports it.
        claimed = {_norm(existing[k]) for f, k in LIST_FIELDS for existing in phase[f]}

        for field, key, description in DETAIL_FIELDS:
            result = _ollama_json(FIELD_PROMPT.format(
                description=description, phase=phase["name"],
                locator=win["locator"], window=win["text"]))
            _warn_unexpected_keys(result, {"items"}, f"{phase['name']}/{field}")

            for item in result.get("items") or []:
                value = (item.get("value") or "").strip()
                evidence = (item.get("evidence") or "").strip()
                if not value or not _evidence_holds(evidence, win["text"]):
                    continue                      # unverifiable claim -> dropped
                # The value itself must come from the document too. Asked for Build
                # Case's deliverables the model answered "None explicitly listed as
                # outputs/artifacts produced by ..." — prose *about* the document,
                # which the evidence check alone happily accepted as an item.
                if not _value_grounded(value, win["text"]):
                    print(f"    ~ {phase['name']}/{field}: dropped commentary "
                          f"'{value[:50]}'", file=sys.stderr)
                    continue
                if _norm(value) in claimed:
                    continue
                claimed.add(_norm(value))
                phase[field].append({key: value, "source": {**source, "quote": evidence[:200]}})

        if phase["gate"] is None:
            result = _ollama_json(GATE_PROMPT.format(
                phase=phase["name"], locator=win["locator"], window=win["text"]))
            _warn_unexpected_keys(result, {"gate"}, f"{phase['name']}/gate")
            gate = result.get("gate")
            if isinstance(gate, dict):
                name = (gate.get("value") or "").strip()
                evidence = (gate.get("evidence") or "").strip()
                if name and not _is_heading(name, doc) \
                        and not _same_phase(name, phase["name"]) \
                        and _evidence_holds(evidence, win["text"]):
                    phase["gate"] = {"name": name, "source": {**source, "quote": evidence[:200]}}


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def order_phases(phases: List[Dict]) -> List[Dict]:
    """Stated order first, then first-seen order for the rest (stable)."""
    numbered = [p for p in phases if isinstance(p.get("order"), int)]
    rest = [p for p in phases if not isinstance(p.get("order"), int)]
    numbered.sort(key=lambda p: p["order"])
    return numbered + rest


def apply_overrides(process_map: Dict) -> Dict:
    """Hand corrections layered over the generated map, so rebuilds don't clobber them.

    Overrides are keyed by phase name within a named process document. A key that
    matches nothing is reported: new documents may rename a phase, and a silently
    inapplicable correction looks exactly like a correction that was never made.
    """
    if not os.path.exists(OVERRIDES_PATH):
        return process_map
    with open(OVERRIDES_PATH, "r", encoding="utf-8") as fh:
        overrides = json.load(fh)

    for process in process_map["processes"]:
        scoped = (overrides.get("processes") or {}).get(process["document"], overrides)

        # Keep the author's spelling for the warning: they need to find the key
        # they typed, not the normalised form the matcher happens to use.
        drops = {_norm(n): n for n in scoped.get("drop_phases", [])}
        present = {_norm(p["name"]) for p in process["phases"]}
        if drops:
            process["phases"] = [p for p in process["phases"]
                                 if _norm(p["name"]) not in drops]
        for key, original in sorted(drops.items()):
            if key not in present:
                print(f"    ~ overrides: drop_phases '{original}' matches no phase in "
                      f"{process['document']}", file=sys.stderr)

        patches = {_norm(k): (k, v) for k, v in (scoped.get("phases") or {}).items()}
        applied = set()
        for phase in process["phases"]:
            hit = patches.get(_norm(phase["name"]))
            if hit:
                phase.update(hit[1])
                phase["overridden"] = True
                applied.add(_norm(phase["name"]))
        for key, (original, _) in patches.items():
            if key not in applied:
                print(f"    ~ overrides: phase '{original}' matches no phase in "
                      f"{process['document']} — correction not applied", file=sys.stderr)

        process["phases"] = order_phases(process["phases"])

    process_map["overrides_applied"] = True
    return process_map


def build(report: bool = False) -> Dict:
    global _CACHE
    _CACHE = _load_cache()
    docs = load_documents()
    print(f"loaded {len(docs)} documents")

    process_docs = []
    for doc in docs:
        verdict = classify(doc)
        flag = "PROCESS" if verdict["process_defining"] else "instance"
        cached = " (cached)" if verdict.get("cached") else ""
        print(f"  {doc['id']:42s} {flag:8s} ({verdict['confidence']:.2f}){cached} "
              f"{verdict['reason'][:52]}")
        if verdict["process_defining"]:
            process_docs.append(doc)
    _save_cache(_CACHE)

    # One lifecycle per process document. A company's corpus can hold several
    # (an SDLC, a maintenance procedure, a department's own process) and they are
    # genuinely different processes — merging them into one ladder invents a
    # lifecycle nobody follows. Each is extracted only from its own document, so
    # a phase's section markers are never applied to a different file.
    processes = []
    for doc in process_docs:
        wins = windows(doc)
        print(f"\nextracting phases from {doc['id']} ({len(wins)} windows)")
        phases = extract_phases(doc)
        print(f"  {len(phases)} phases: {', '.join(p['name'] for p in phases[:12])}")
        for phase in phases:
            extract_details(phase, doc, phase_windows(phase, phases, doc, wins))
        processes.append({"document": doc["id"], "phases": order_phases(phases)})

    process_map = {
        "generated_by": "scripts/corpus/build_process_map.py",
        "model": MODEL,
        "processes": processes,
    }
    process_map = apply_overrides(process_map)

    if report:
        print_report(process_map)
    return process_map


def print_report(process_map: Dict) -> None:
    processes = process_map.get("processes") or []
    print("\n" + "=" * 70)
    if not processes:
        print("NO LIFECYCLE FOUND — the loaded documents do not define a process.")
        print("=" * 70)
        return

    for process in processes:
        phases = process["phases"]
        undetailed = [p for p in phases if not p.get("gate")
                      and not any(p.get(f) for f, _ in LIST_FIELDS)]
        print(f"{len(phases)} phases from {process['document']}")
        print("=" * 70)
        for i, phase in enumerate(phases, start=1):
            gate = f"  [gate: {phase['gate']['name']}]" if phase.get("gate") else ""
            print(f"\n{i}. {phase['name']}{gate}")
            for field, key in LIST_FIELDS:
                for item in phase.get(field) or []:
                    src = item["source"]
                    print(f"     {field[:8]:8s} {item[key][:58]:58s} ({src['doc']} {src['locator']})")
        if undetailed:
            print(f"\n  ({len(undetailed)} phase(s) named but not detailed: "
                  f"{', '.join(p['name'] for p in undetailed)})")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="print the extracted map")
    parser.add_argument("--dry-run", action="store_true", help="do not write the artifact")
    parser.add_argument("--model", help="override the extraction model")
    parser.add_argument("--src", help="comma-separated source dirs under data/")
    parser.add_argument("--no-cache", action="store_true",
                        help="re-classify every document instead of reusing cached verdicts")
    args = parser.parse_args()

    global MODEL, SRC_DIRS, CACHE_PATH
    if args.model:
        MODEL = args.model
    if args.src:
        SRC_DIRS = [d.strip() for d in args.src.split(",") if d.strip()]
    if args.no_cache:
        CACHE_PATH = os.devnull
    print(f"extraction model: {MODEL}")
    print(f"source dirs: {', '.join(SRC_DIRS)}\n")

    process_map = build(report=args.report)

    if args.dry_run:
        print("\n(dry run — nothing written)")
        return
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(process_map, fh, ensure_ascii=False, indent=2)
    processes = process_map.get("processes") or []
    summary = ", ".join(f"{p['document']}: {len(p['phases'])} phases" for p in processes)
    print(f"\nwrote {OUT_PATH} ({summary or 'no lifecycle found'})")


if __name__ == "__main__":
    main()
