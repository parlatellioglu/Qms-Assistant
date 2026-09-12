"""Pointing the system at your own documents is a setting, not a code edit.

`services/corpus.py` decides which document module the Compliance Checker checks
and which documents traceability rules resolve against. These tests cover the
swap working, the failure modes degrading quietly, and the ingest CLI only
offering a module path that can actually be imported. No services needed.
"""
import importlib
import os
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)


def _reload_corpus(monkeypatch, **env):
    """Reimport services.corpus with the given environment in place.

    The module reads its settings at import time (like the rest of the backend),
    so a test that changes them has to reload it.
    """
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import services.corpus as corpus
    return importlib.reload(corpus)


@pytest.fixture
def custom_module(tmp_path, monkeypatch):
    """A corpus module written the way scripts/ingest.py writes one."""
    pkg = tmp_path / "mycorpus"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "docs.py").write_text(textwrap.dedent('''
        documents = [
            {"id": "DOC-A", "doc_kind": "SRS", "title": "A", "content": "alpha"},
            {"id": "DOC-B", "doc_kind": "PMP", "title": "B", "content": "beta"},
        ]
    '''), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return "mycorpus.docs"


def test_default_is_the_bundled_corpus(monkeypatch):
    corpus = _reload_corpus(monkeypatch, CORPUS_MODULE="data.cmmi_docs")
    docs = corpus.corpus_documents()
    assert docs, "the bundled corpus should load by default"
    assert all("id" in d and "content" in d for d in docs)


def test_a_custom_module_replaces_the_corpus(monkeypatch, custom_module):
    corpus = _reload_corpus(monkeypatch, CORPUS_MODULE=custom_module)
    assert [d["id"] for d in corpus.corpus_documents()] == ["DOC-A", "DOC-B"]


def test_ingest_output_shape_is_accepted(monkeypatch, custom_module):
    """scripts/ingest.py names its list `documents`, not `cmmi_documents`.

    If the loader only recognised the bundled name, every ingested corpus would
    come back empty — and silently, since an empty corpus is a valid state.
    """
    corpus = _reload_corpus(monkeypatch, CORPUS_MODULE=custom_module)
    assert len(corpus.corpus_documents()) == 2


def test_missing_module_degrades_to_empty(monkeypatch):
    """A typo in the setting must not take the API down on import."""
    corpus = _reload_corpus(monkeypatch, CORPUS_MODULE="data.does_not_exist")
    assert corpus.corpus_documents() == []


def test_module_without_a_document_list_degrades_to_empty(monkeypatch, tmp_path):
    (tmp_path / "empty_mod.py").write_text("SOMETHING = 42\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    corpus = _reload_corpus(monkeypatch, CORPUS_MODULE="empty_mod")
    assert corpus.corpus_documents() == []


def test_drafts_are_optional(monkeypatch):
    """A custom corpus normally ships no drafts; that is not an error."""
    corpus = _reload_corpus(monkeypatch, DRAFTS_MODULE="data.no_such_drafts")
    assert corpus.draft_documents() == []


def test_compliance_reads_through_the_setting(monkeypatch, custom_module):
    """The checker must see the configured corpus, not the bundled one."""
    _reload_corpus(monkeypatch, CORPUS_MODULE=custom_module, DRAFTS_MODULE="none")
    import services.compliance as compliance
    importlib.reload(compliance)
    ids = [d["id"] for d in compliance.checkable_documents()]
    assert ids == ["DOC-A", "DOC-B"]
    # restore so later tests in the session see the bundled corpus again
    monkeypatch.setenv("CORPUS_MODULE", "data.cmmi_docs")
    monkeypatch.setenv("DRAFTS_MODULE", "data.cmmi_drafts")
    importlib.reload(importlib.import_module("services.corpus"))
    importlib.reload(compliance)


# --------------------------------------------------------------------------- #
#  The ingest CLI must only print a corpus.module path that can be imported.
# --------------------------------------------------------------------------- #
def _ingest():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ingest", os.path.join(ROOT, "scripts", "ingest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("out, expected", [
    ("backend/data/my_docs.py", "data.my_docs"),
    ("backend/data/sub/my_docs.py", "data.sub.my_docs"),
    ("/tmp/outside-the-repo/my_docs.py", None),   # not importable from backend/
    ("backend/data/my_docs.txt", None),           # not a module
])
def test_module_path_only_when_importable(out, expected):
    assert _ingest()._module_path(out) == expected
