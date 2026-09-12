#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ingest a folder of your OWN documents into the assistant's corpus.

The demo corpus is built by scripts/corpus/build_cmmi_corpus.py, which is bound to
*this* project's files: every source file is looked up in a hand-written META table
keyed by exact filename. That is fine for a fixed demo corpus and useless for anyone
else's documents.

This is the general path. Point it at any folder and it will:

  1. find every supported document (.docx .xlsx .pptx .txt .md), recursively
  2. flatten each to text with the SAME extractor the backend uses for uploads
     (backend/services/doc_extract.py), so an ingested file reads exactly like a
     file checked through the Compliance Checker
  3. infer the metadata the retrieval and compliance layers need
  4. write a corpus module — a plain list of dicts, same schema as
     backend/data/cmmi_docs.py
  5. optionally embed and index it into Qdrant

Examples
--------
    # see what would be ingested; write nothing
    .venv/bin/python scripts/ingest.py ~/quality-docs --dry-run

    # build a corpus module from a folder
    .venv/bin/python scripts/ingest.py ~/quality-docs --out backend/data/my_docs.py

    # ...and index it so the assistant answers from it
    QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/ingest.py \
        ~/quality-docs --out backend/data/my_docs.py \
        --index --collection my_quality_docs

    # ...and later add or update just one document, without re-embedding the rest
    QDRANT_URL=http://localhost:6333 .venv/bin/python scripts/ingest.py \
        ~/quality-docs/new-file.docx.d --out backend/data/my_docs.py \
        --index --append --collection my_quality_docs

Connecting it
-------------
Two settings in config.yaml, because they control two different things:

    retrieval.collection : my_quality_docs   # what the ASSISTANT searches
    corpus.module        : data.my_docs      # what the COMPLIANCE CHECKER checks

Set both and restart. The script prints them for you at the end of a run.

Metadata
--------
Retrieval needs very little — a title and the text. The Compliance Checker needs
`doc_kind`, because rules bind to documents through `applies_to.doc_kind`. So
doc_kind is guessed from the filename (an "SRS" in the name -> doc_kind SRS) and
can be set explicitly:

    --kind SRS              every ingested file is an SRS
    --kind-map kinds.json   {"filename substring": "DOC_KIND", ...}

Anything still unknown is left as None rather than guessed, so a document is never
silently checked against the wrong rule set.

Note: this module is written with a top-level `documents` list, which
services/corpus.py recognises — so the file it produces is directly usable as
`corpus.module` with no renaming. Uploading a single file through the Compliance
Checker UI needs neither setting: that path is transient by design and never
stores or indexes the file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from services.doc_extract import SUPPORTED_EXTENSIONS, extract_file  # noqa: E402

# Document kinds recognised from a filename. Longest first so "SAT_PLAN" wins over
# "SAT". Extend freely — this is only a convenience; --kind / --kind-map override it.
FILENAME_KINDS = [
    "SAT_PLAN", "UAT_PLAN", "SAT_CASES", "UAT_CASES", "TECH_RECO",
    "SRS", "DSAD", "PMP", "BUR", "TRF", "URS", "HLD", "SOW", "SDLC",
]

# Folders that never hold source documents.
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}

# A title line should look like a heading, not a table row or a paragraph.
MAX_TITLE_CHARS = 120


def find_documents(root: str) -> list[str]:
    """Every supported document under ``root``, recursively, in stable order."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(filenames):
            if fn.startswith("~$") or fn.startswith("."):
                continue  # Office lock files and dotfiles
            if os.path.splitext(fn)[1].lower() in SUPPORTED_EXTENSIONS:
                found.append(os.path.join(dirpath, fn))
    return found


def make_id(path: str, taken: set[str]) -> str:
    """A stable, readable id from the filename stem, unique within this run."""
    stem = os.path.splitext(os.path.basename(path))[0]
    base = re.sub(r"[^\w.-]+", "-", stem, flags=re.UNICODE).strip("-") or "document"
    candidate, n = base, 2
    while candidate in taken:            # two files with the same stem in different folders
        candidate, n = f"{base}-{n}", n + 1
    taken.add(candidate)
    return candidate


def read_frontmatter(text: str) -> tuple[dict, str]:
    """Split leading YAML frontmatter (``---`` ... ``---``) from the body.

    Documents that already carry metadata are common (the bundled sample docs do),
    and honouring it beats guessing: a declared title or id is authoritative where
    our heuristics are not. Returns ({}, text) unchanged when there is no
    frontmatter or it can't be parsed.
    """
    if not text.lstrip().startswith("---"):
        return {}, text
    try:
        import yaml
        parts = text.lstrip().split("---", 2)
        if len(parts) < 3:
            return {}, text
        meta = yaml.safe_load(parts[1])
        return (meta, parts[2].lstrip()) if isinstance(meta, dict) else ({}, text)
    except Exception:
        return {}, text


# Structural markers the extractors emit ("[Slide 3]", "[Sheet1]") — never a title.
_MARKER = re.compile(r"^\[[^\]]*\]$")


def guess_title(text: str, path: str) -> str:
    """First line that reads like a heading, else the filename stem.

    Extracted text puts table/sheet rows on ' | '-joined lines, so a line
    containing '|' is data, not a title; and the pptx/xlsx extractors prefix
    sections with "[Slide N]" / "[SheetName]" markers. Falling back to the
    filename is safer than promoting a random first row into the title, which
    retrieval weights.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line or "|" in line or len(line) > MAX_TITLE_CHARS:
            continue
        if _MARKER.match(line) or set(line) <= {"-", "=", "_", "*"}:
            continue                    # structural marker or a rule/underline
        return line
    return os.path.splitext(os.path.basename(path))[0]


def guess_kind(path: str, kind_map: dict, forced: str | None) -> str | None:
    """doc_kind for a file: --kind wins, then --kind-map, then the filename."""
    if forced:
        return forced
    name = os.path.basename(path)
    for needle, kind in kind_map.items():          # explicit map: substring -> kind
        if needle.lower() in name.lower():
            return kind
    # Normalise separators so "SAT Plan", "SAT-Plan" and "SAT_PLAN" all match the
    # same pattern — real filenames are inconsistent about which one they use.
    upper = re.sub(r"[\s\-.]+", "_", name.upper())
    for kind in sorted(FILENAME_KINDS, key=len, reverse=True):
        if re.search(rf"(?<![A-Z]){re.escape(kind)}(?![A-Z])", upper):
            return kind
    return None                                     # unknown — never guessed


def build_documents(paths: list[str], args, kind_map: dict) -> list[dict]:
    """Extract and describe each file as a corpus document dict."""
    docs, taken = [], set()
    for path in paths:
        try:
            text = extract_file(path)
        except Exception as exc:                    # one unreadable file must not stop the run
            print(f"  SKIP  {os.path.relpath(path, args.source)}  ({type(exc).__name__}: {exc})")
            continue
        if not text.strip():
            print(f"  SKIP  {os.path.relpath(path, args.source)}  (no extractable text)")
            continue

        # A document's own declared metadata beats both our heuristics and the
        # blanket --flag defaults, which apply to the whole run.
        fm, text = read_frontmatter(text)
        pick = lambda key, fallback: fm.get(key) if fm.get(key) is not None else fallback

        title = pick("title", None) or guess_title(text, path)
        # Prepend the title so its terms participate in retrieval, matching what
        # build_cmmi_corpus.py does for the demo corpus.
        content = f"{title}\n{text}" if not text.lstrip().startswith(title) else text
        docs.append({
            "id": str(pick("id", None) or make_id(path, taken)),
            "doc_kind": pick("doc_kind", guess_kind(path, kind_map, args.kind)),
            "title": str(title),
            "department": pick("department", args.department),
            "document_type": pick("document_type", args.document_type),
            "status": pick("status", args.status),
            "version": str(pick("version", args.version)),
            "author": pick("author", args.author),
            # A declared date, else the file's own mtime — a real fact either way.
            "created_date": str(pick("created_date",
                                     dt.date.fromtimestamp(os.path.getmtime(path)).isoformat())),
            "language": pick("language", args.language),
            "tags": list(fm.get("tags") or []),
            "content": content,
            "source_file": os.path.relpath(path, ROOT) if path.startswith(ROOT) else path,
        })
    return _distinguish_titles(docs)


def _distinguish_titles(docs: list[dict]) -> list[dict]:
    """Fall back to the filename for any title shared by several documents.

    A common template puts something identical on the first line of every file (a
    project or company name), which would leave every document with the same title
    — bad in the source cards, and worse for retrieval, where the title text is
    prepended to the content. A repeated title is evidence the heuristic found
    boilerplate rather than a name, so those documents use their filename instead.
    """
    counts: dict[str, int] = {}
    for d in docs:
        counts[d["title"]] = counts.get(d["title"], 0) + 1
    for d in docs:
        if counts[d["title"]] > 1:
            stem = os.path.splitext(os.path.basename(d["source_file"]))[0]
            # Content was built with the old title prepended; rebuild that prefix.
            if d["content"].startswith(d["title"] + "\n"):
                d["content"] = stem + d["content"][len(d["title"]):]
            d["title"] = stem
    return docs


def write_module(out_path: str, docs: list[dict], source: str) -> None:
    """Emit the corpus as an importable Python module (same shape as cmmi_docs.py)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    keys = ["id", "doc_kind", "title", "department", "document_type", "status",
            "version", "author", "created_date", "language", "tags", "content", "source_file"]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write('"""Auto-generated by scripts/ingest.py — do not edit by hand.\n\n')
        f.write(f"Ingested from: {source}\n")
        f.write(f"Generated on:  {dt.date.today().isoformat()}\n\n")
        f.write('Same schema as backend/data/cmmi_docs.py."""\n\n')
        f.write("documents = [\n")
        for doc in docs:
            f.write("    {\n")
            for key in keys:
                f.write(f"        {key!r}: {doc[key]!r},\n")
            f.write("    },\n")
        f.write("]\n")


def index_documents(docs: list[dict], collection: str, append: bool = False) -> None:
    """Embed and index the documents as parent/child chunks in Qdrant.

    ``append`` adds to an existing collection instead of rebuilding it, replacing
    only these documents' own points. Use it to add or update a few documents
    without re-embedding everything already indexed.
    """
    from services.embedding import EmbeddingService      # heavy import: only when indexing
    svc = EmbeddingService(
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        collection_name=collection,
        index_on_init=False,                             # we drive chunked indexing ourselves
    )
    mode = "late chunking" if svc.late_chunking else "naive per-child"
    verb = "Appending to" if append else "Rebuilding"
    print(f"\n{verb} '{collection}' [{mode}]...")
    n_children, n_parents = svc.index_chunked(docs, recreate=not append)
    print(f"  {n_children} child chunks across {n_parents} parents ({len(docs)} documents).")
    if append:
        total = svc.qdrant.count(collection).count
        print(f"  collection now holds {total} points in total.")


def _module_path(out_path: str) -> str | None:
    """Dotted module path for ``out_path`` as imported from backend/, or None.

    ``corpus.module`` is imported, not read as a file, so only a path under
    backend/ can be named there. Anywhere else there is no valid dotted path and
    the caller should say so rather than print a broken one.
    """
    out_abs = os.path.abspath(out_path)
    backend_abs = os.path.abspath(BACKEND)
    if os.path.commonpath([out_abs, backend_abs]) != backend_abs:
        return None
    rel = os.path.relpath(out_abs, backend_abs)
    if not rel.endswith(".py"):
        return None
    return rel[:-3].replace(os.sep, ".")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ingest a folder of documents into the assistant's corpus.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="folder containing your documents (searched recursively)")
    ap.add_argument("--out", default=None,
                    help="write the corpus module here (default: backend/data/custom_docs.py)")
    ap.add_argument("--index", action="store_true", help="also embed + index into Qdrant")
    ap.add_argument("--append", action="store_true",
                    help="with --index: add to the existing collection instead of rebuilding it. "
                         "Only these documents are re-embedded; their previous points are replaced.")
    ap.add_argument("--collection", default=os.getenv("CHAT_COLLECTION", "custom_docs"),
                    help="Qdrant collection to index into (default: $CHAT_COLLECTION or custom_docs)")
    ap.add_argument("--kind", default=None, help="force one doc_kind for every file (e.g. SRS)")
    ap.add_argument("--kind-map", default=None,
                    help="JSON file mapping a filename substring to a doc_kind")
    ap.add_argument("--department", default=None)
    ap.add_argument("--document-type", default=None,
                    help="policy | procedure | instruction | form | report")
    ap.add_argument("--status", default="published")
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--author", default=None)
    ap.add_argument("--language", default="TR")
    ap.add_argument("--dry-run", action="store_true", help="report what would be ingested; write nothing")
    args = ap.parse_args()

    if not os.path.isdir(args.source):
        return print(f"Not a folder: {args.source}") or 2

    kind_map = {}
    if args.kind_map:
        with open(args.kind_map, encoding="utf-8") as fh:
            kind_map = json.load(fh)

    paths = find_documents(args.source)
    if not paths:
        return print(f"No supported documents under {args.source} "
                     f"(looking for: {', '.join(SUPPORTED_EXTENSIONS)})") or 1

    print(f"Found {len(paths)} document(s) under {args.source}\n")
    docs = build_documents(paths, args, kind_map)
    if not docs:
        return print("Nothing could be extracted.") or 1

    for d in docs:
        kind = d["doc_kind"] or "-"
        print(f"  {d['id'][:28]:28s} {kind:10s} {len(d['content']):6d} chars  {d['title'][:44]}")

    unknown = [d["id"] for d in docs if not d["doc_kind"]]
    if unknown:
        print(f"\n  note: {len(unknown)} document(s) have no doc_kind, so the Compliance "
              f"Checker has no rule set to apply to them.\n"
              f"        Set one with --kind or --kind-map. Retrieval is unaffected.")

    if args.dry_run:
        print("\nDry run — nothing written.")
        return 0

    out = args.out or os.path.join(BACKEND, "data", "custom_docs.py")
    write_module(out, docs, os.path.abspath(args.source))
    print(f"\nWrote {len(docs)} documents to {os.path.relpath(out, ROOT)}")

    if args.index:
        index_documents(docs, args.collection, append=args.append)
        print("\nTo use this corpus, set these in config.yaml, then restart:")
        print(f"  retrieval.collection : {args.collection}      # what the assistant searches")
        module = _module_path(out)
        if module:
            print(f"  corpus.module        : {module}      # what the Compliance Checker checks")
        else:
            # corpus.module is imported, so the file has to live somewhere importable
            # from backend/. Saying so beats printing an unusable dotted path.
            print(f"  corpus.module        : (not importable from backend/)")
            print(f"    The checker imports this module, so move the file under "
                  f"backend/data/ — e.g. --out backend/data/my_docs.py — and set\n"
                  f"    corpus.module: data.my_docs")
    else:
        print("Re-run with --index to embed it into Qdrant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
