"""Tests for the process-map extractor (scripts/corpus/build_process_map.py).

These cover the deterministic half of the pipeline — windowing, the
citation-required rule, ordering and the overrides merge — by feeding the stage
functions a stubbed LLM. The extraction *quality* itself needs Ollama and is
checked separately against the SDLC deck, where the expected answer is known.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "corpus"))

import build_process_map as bpm  # noqa: E402


@pytest.fixture
def stub_llm(monkeypatch):
    """Replace the Ollama call with a queue of canned JSON responses."""
    def _install(*responses):
        queue = list(responses)
        monkeypatch.setattr(bpm, "_ollama_json",
                            lambda *a, **k: queue.pop(0) if queue else {})
    return _install


# --------------------------------------------------------------------------- #
# Windowing — citations need a locator that a human can check
# --------------------------------------------------------------------------- #

def test_slide_decks_are_windowed_by_slide():
    doc = {"id": "deck", "text": "\n".join(f"[Slide {i}]\ncontent {i}" for i in range(1, 40))}
    wins = bpm.windows(doc)
    assert wins, "a deck should produce at least one window"
    assert all("slide" in w["locator"] for w in wins)


def test_plain_documents_fall_back_to_line_ranges():
    doc = {"id": "doc", "text": "\n".join(f"line {i}" for i in range(1, 500))}
    wins = bpm.windows(doc)
    assert all(w["locator"].startswith("lines ") for w in wins)


def test_windows_respect_the_size_budget():
    doc = {"id": "doc", "text": "\n".join("x" * 200 for _ in range(200))}
    for win in bpm.windows(doc):
        assert len(win["text"]) <= bpm.WINDOW_CHARS + 400   # +1 overshooting line


# --------------------------------------------------------------------------- #
# The citation rule: no evidence quote, no claim
# --------------------------------------------------------------------------- #

NO_SECTIONS = {"sequence_markers": [], "phase_sections": []}

# Long enough to satisfy the evidence check, so tests exercise the rule they name
# rather than tripping over a too-short quote.
DOC_TEXT = ("the Scoping stage begins after ideation and the Design phase produces DSAD, "
            "then development stage work proceeds to Dev't and testing")


# --------------------------------------------------------------------------- #
# Evidence must be real, not merely present
# --------------------------------------------------------------------------- #

def test_fabricated_evidence_is_rejected():
    """A model that invents a phase invents its quote too — presence is not enough."""
    assert bpm._evidence_holds("the Scoping stage begins after ideation", DOC_TEXT)
    assert not bpm._evidence_holds("Requirements Gathering is the first phase", DOC_TEXT)


def test_trivially_short_evidence_is_rejected():
    assert not bpm._evidence_holds("Design", DOC_TEXT), "a one-word quote matches anything"
    assert not bpm._evidence_holds("", DOC_TEXT)


def test_evidence_check_tolerates_whitespace_and_case():
    assert bpm._evidence_holds("THE   SCOPING\n STAGE  BEGINS after ideation", DOC_TEXT)


# Verbatim slide-23 text and the citations gemma4:e4b actually produced for it.
# Three of these four real policies were being dropped for their punctuation.
SLIDE_23 = (
    "[Slide 23]\n Ideation - Policy\n"
    "IT shall be consulted for projects with significant IT impact (i.e. involves the "
    "creation or enhancement of an IT system). \n"
    "If in Ideation Stage, Rough Order of Magnitude (ROM) contains rough estimates on "
    "technical feasibility, timelines and cost.\n"
    "IT effort shall not take longer than 4 man-hours.  Otherwise, request will be treated "
    "as if in Scoping Stage\n"
    "IT's technical inputs are non-binding and subject to change once project requirements "
    "have been comprehensively studied (during Scoping Stage)"
)


@pytest.mark.parametrize("evidence", [
    "[Slide 23]\n Ideation - Policy\nIT shall be consulted for projects with significant IT impact",
    "[Slide 23]\n... If in Ideation Stage, Rough Order of Magnitude (ROM) contains rough estimates",
    "[Slide 23]\n... IT effort shall not take longer than 4 man-hours.",
    "[Slide 23]\n… IT's technical inputs are non-binding and subject to change",
])
def test_real_quotes_survive_the_models_citation_style(evidence):
    """Slide markers and ellipsis elision are how models cite — not grounds for rejection."""
    assert bpm._evidence_holds(evidence, SLIDE_23)


@pytest.mark.parametrize("evidence", [
    "[Slide 23]\n... IT effort shall not exceed 40 man-hours and requires board approval",
    "[Slide 23]\n... Requirements Gathering is the first phase of the lifecycle",
    "[Slide 23]\n...",                                    # scaffolding only, no content
    "[Slide 23]",
])
def test_fabrications_still_fail_after_loosening(evidence):
    """Tolerating citation style must not become tolerating invention."""
    assert not bpm._evidence_holds(evidence, SLIDE_23)


def test_scaffolding_alone_is_not_evidence():
    assert bpm._evidence_segments("[Slide 23]\n...\n|") == []


def test_invented_phases_are_dropped_even_with_confident_quotes(stub_llm):
    """The regression from the first structure-driven run: empty context -> generic SDLC."""
    stub_llm({"sequence_markers": ["15"], "phase_sections": []},
             {"phases": [
                 {"name": "Requirements Gathering", "order": 1, "evidence": "Requirements Gathering phase"},
                 {"name": "Design", "order": 2, "evidence": "the Design phase produces DSAD"},
             ]})
    doc = {"id": "deck", "text": f"[Slide 15]\n{DOC_TEXT}"}
    phases = bpm.extract_phases(doc)
    assert [p["name"] for p in phases] == ["Design"], "only the verifiable phase survives"


# --------------------------------------------------------------------------- #
# Never extract from empty context
# --------------------------------------------------------------------------- #

def test_markers_parse_whether_or_not_the_title_is_attached():
    assert bpm._marker_id("15") == "15"
    assert bpm._marker_id("15: High Level Solutions Delivery Life Cycle") == "15"
    assert bpm._marker_id(15) == "15"


def test_titled_markers_still_select_their_slides():
    """The parsing bug that selected nothing and yielded an invented lifecycle."""
    doc = {"id": "deck", "text": "[Slide 15]\nlifecycle overview\n[Slide 16]\nother"}
    text = bpm.slice_markers(doc, ["15: High Level Solutions Delivery Life Cycle"])
    assert "lifecycle overview" in text and "other" not in text


def test_empty_selection_skips_extraction_instead_of_inventing(stub_llm, capsys):
    stub_llm({"sequence_markers": ["999"], "phase_sections": []},   # matches no slide
             {"phases": [{"name": "Invented", "order": 1, "evidence": "totally made up quote"}]})
    doc = {"id": "deck", "text": "[Slide 15]\nreal content here that is long enough"}
    assert bpm.extract_phases(doc) == []
    assert "no text selected" in capsys.readouterr().err


def test_phases_without_evidence_are_dropped(stub_llm):
    stub_llm(NO_SECTIONS, {"phases": [
        {"name": "Scoping", "order": 1, "evidence": "the Scoping stage begins after ideation"},
        {"name": "Invented", "order": 2},                    # no evidence
        {"name": "AlsoInvented", "order": 3, "evidence": ""},  # empty evidence
    ]})
    doc = {"id": "d", "text": DOC_TEXT}
    phases = bpm.extract_phases(doc)
    assert [p["name"] for p in phases] == ["Scoping"]


def test_extracted_phases_carry_a_checkable_source(stub_llm):
    stub_llm({"sequence_markers": ["18"], "phase_sections": []},
             {"phases": [{"name": "Design", "order": 2,
                          "evidence": "the Design phase produces DSAD"}]})
    doc = {"id": "SDLC", "text": f"[Slide 18]\n{DOC_TEXT}"}
    phase = bpm.extract_phases(doc)[0]
    source = phase["sources"][0]
    assert source["doc"] == "SDLC" and "18" in source["locator"] and source["quote"]


DETAIL_TEXT = ("the requirements phase produces the SRS and requires a signed TRF "
               "before work may begin on any downstream deliverable")


def _details(*, deliverables=None, entry=None, exit_=None, policies=None, gate=None):
    """Responses for one detail pass, in the order extract_details asks for them."""
    return [{"items": deliverables or []}, {"items": entry or []},
            {"items": exit_ or []}, {"items": policies or []}, {"gate": gate}]


def test_detail_items_without_evidence_are_dropped(stub_llm):
    stub_llm(*_details(
        deliverables=[{"value": "SRS", "evidence": "the requirements phase produces the SRS"},
                      {"value": "Ghost"}],                    # no evidence
        entry=[{"value": "requires a signed TRF", "evidence": "requires a signed TRF"}]))
    phase = {"name": "Requirements", "order": 1, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slide 5", "text": DETAIL_TEXT}])
    assert [d["name"] for d in phase["deliverables"]] == ["SRS"]
    assert phase["entry_criteria"][0]["source"]["locator"] == "slide 5"


def test_paraphrased_values_are_dropped(stub_llm):
    """The prompt asks for the document's wording; a rewrite is not quotable.

    Deliberately strict: a paraphrase may be perfectly faithful, but allowing it
    means the map contains sentences no reader can find in the source document.
    """
    stub_llm(*_details(entry=[{"value": "TRF must be signed first",   # rephrased
                               "evidence": "requires a signed TRF"}]))
    phase = {"name": "Requirements", "order": 1, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slide 5", "text": DETAIL_TEXT}])
    assert phase["entry_criteria"] == []


def test_gate_without_evidence_is_dropped(stub_llm):
    stub_llm(*_details(gate={"value": "G1"}))                 # no evidence
    phase = {"name": "Scoping", "order": 1, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slide 2", "text": DETAIL_TEXT}])
    assert phase["gate"] is None


def test_gate_with_fabricated_evidence_is_dropped(stub_llm):
    stub_llm(*_details(gate={"value": "G1", "evidence": "Gate 1 approves the charter"}))
    phase = {"name": "Scoping", "order": 1, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slide 2", "text": DETAIL_TEXT}])
    assert phase["gate"] is None, "a gate quote absent from the source is not a citation"


def test_each_field_is_asked_for_separately(stub_llm, monkeypatch):
    """One question per call — the five-field schema is what caused the drift."""
    seen = []
    monkeypatch.setattr(bpm, "_ollama_json",
                        lambda prompt, *a, **k: seen.append(prompt) or {"items": []})
    phase = {"name": "Scoping", "order": 1, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slide 2", "text": DETAIL_TEXT}])
    assert len(seen) == len(bpm.DETAIL_FIELDS) + 1, "four field calls plus the gate call"
    for _, _, description in bpm.DETAIL_FIELDS:
        assert any(description in prompt for prompt in seen)


def test_commentary_about_the_document_is_not_an_item(stub_llm, capsys):
    """Asked for Build Case's deliverables, the model answered that there are none."""
    stub_llm(*_details(deliverables=[
        {"value": "None explicitly listed as outputs/artifacts produced by 'Build Case'",
         "evidence": "the requirements phase produces the SRS"},
        {"value": "SRS", "evidence": "the requirements phase produces the SRS"},
    ]))
    phase = {"name": "Build Case", "order": 3, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slides 39-42", "text": DETAIL_TEXT}])
    assert [d["name"] for d in phase["deliverables"]] == ["SRS"]
    assert "dropped commentary" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["SRS", "PMP", "DAR Record"])
def test_short_deliverable_names_are_not_treated_as_commentary(value):
    """Real deliverables are often shorter than an evidence quote may be."""
    assert bpm._value_grounded(value, f"the phase produces the {value} before review")


def test_one_sentence_is_claimed_by_a_single_field(stub_llm):
    """The same sentence arrived as an exit criterion and again as a policy."""
    shared = "requires a signed TRF"
    stub_llm(*_details(entry=[{"value": shared, "evidence": shared}],
                       exit_=[{"value": shared, "evidence": shared}],
                       policies=[{"value": shared, "evidence": shared}]))
    phase = {"name": "Scoping", "order": 2, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slide 2", "text": DETAIL_TEXT}])
    assert len(phase["entry_criteria"]) == 1
    assert phase["exit_criteria"] == [] and phase["policies"] == []


def test_a_slide_title_inside_the_section_is_not_a_gate(stub_llm):
    """Project Planning's "gate" was "Complete Project Planning" — a slide heading."""
    doc = {"id": "deck", "text": "[Slide 55]\nComplete Project Planning\n[Slide 56]\nbody"}
    assert bpm._is_heading("Complete Project Planning", doc)
    assert not bpm._is_heading("Gate 2: Review of Recommended Supplier", doc)


def test_schema_drift_is_reported_not_swallowed(stub_llm, capsys):
    """The silent loss: content relocated into an invented key vanished without trace."""
    stub_llm({"items": [], "process_details": [{"value": "IT shall be consulted"}]},
             {"items": []}, {"items": []}, {"items": []}, {"gate": None})
    phase = {"name": "Ideation", "order": 1, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slides 20-23", "text": DETAIL_TEXT}])
    assert "process_details" in capsys.readouterr().err, \
        "dropping an unexpected key must be visible, not silent"


# --------------------------------------------------------------------------- #
# Nothing invented when the corpus says nothing
# --------------------------------------------------------------------------- #

def test_silent_corpus_yields_no_phases(stub_llm):
    stub_llm(NO_SECTIONS, {"phases": []})
    phases = bpm.extract_phases({"id": "d", "text": "t"})
    assert phases == [], "a corpus with no lifecycle must not produce an invented one"


def test_malformed_model_output_is_survivable(stub_llm):
    stub_llm({}, {})                                          # model emitted garbage
    assert bpm.extract_phases({"id": "d", "text": "t"}) == []


def test_duplicate_phases_in_one_response_collapse(stub_llm):
    """One authoritative sequence — a name repeated at two granularities is not two phases."""
    stub_llm(NO_SECTIONS, {"phases": [
        {"name": "DEV'T", "order": 8, "evidence": "then development stage work proceeds to Dev't"},
        {"name": "Dev't", "order": 4, "evidence": "development stage work proceeds"},
    ]})
    phases = bpm.extract_phases({"id": "d", "text": DOC_TEXT})
    assert len(phases) == 1 and phases[0]["order"] == 8


# --------------------------------------------------------------------------- #
# Ordering + dedup
# --------------------------------------------------------------------------- #

def test_stated_order_wins_and_unordered_phases_keep_first_seen_order():
    phases = [{"name": "Launch", "order": 5}, {"name": "Unknown", "order": None},
              {"name": "Ideation", "order": 1}, {"name": "AlsoUnknown", "order": None}]
    assert [p["name"] for p in bpm.order_phases(phases)] == \
        ["Ideation", "Launch", "Unknown", "AlsoUnknown"]


@pytest.mark.parametrize("variant", ["DEV'T", "Dev't", "dev t", "DEV T"])
def test_phase_names_normalise_to_one_key(variant):
    assert bpm._norm(variant) == bpm._norm("DEVT")


# --------------------------------------------------------------------------- #
# Section scoping — activities inside a phase must not become phases
# --------------------------------------------------------------------------- #

def test_phase_section_runs_until_the_next_phase_starts():
    """Slides under a phase header belong to that phase, not to the next one."""
    doc = {"id": "deck", "text": "\n".join(
        f"[Slide {i}]\nbody {i}" for i in range(43, 70))}
    phases = [{"name": "Project Planning", "section_marker": "43"},
              {"name": "Procurement", "section_marker": "64"}]
    wins = bpm.phase_windows(phases[0], phases, doc, [])
    text = wins[0]["text"]
    assert "body 53" in text, "activities under the header belong to this phase"
    assert "body 64" not in text, "the next phase's section must not bleed in"


def test_last_phase_section_runs_to_the_end():
    doc = {"id": "deck", "text": "\n".join(f"[Slide {i}]\nbody {i}" for i in range(64, 87))}
    phases = [{"name": "Procurement", "section_marker": "64"}]
    text = bpm.phase_windows(phases[0], phases, doc, [])[0]["text"]
    assert "body 86" in text


@pytest.mark.parametrize("section_name, sequence_name", [
    ("Ideation Phase", "Ideation"),
    ("Procurement Phase", "Procurement"),
    ("Project Planning Phase", "Project Planning"),
    ("Scoping", "Scoping Phase"),                    # stated the other way round
])
def test_section_headers_bind_to_their_sequence_phase(section_name, sequence_name):
    """"Ideation Phase" (header) and "Ideation" (sequence) are one phase, not two."""
    assert bpm._same_phase(section_name, sequence_name)


def test_different_phases_do_not_bind():
    assert not bpm._same_phase("Procurement Phase", "Project Planning")
    assert not bpm._same_phase("Design", "Development")


def test_phase_links_to_its_section_despite_the_phase_suffix(stub_llm):
    """The link that silently failed: every phase came back section=None."""
    stub_llm({"sequence_markers": ["15"],
              "phase_sections": [{"phase": "Ideation Phase", "marker": "20: Ideation Phase"}]},
             {"phases": [{"name": "Ideation", "order": 1,
                          "evidence": "the Scoping stage begins after ideation"}]})
    doc = {"id": "deck", "text": f"[Slide 15]\n{DOC_TEXT}"}
    phase = bpm.extract_phases(doc)[0]
    assert phase["section_marker"] == "20", "section id should be bare, and bound"


def test_unstructured_documents_fall_back_to_name_matching():
    """No section markers anywhere (e.g. a .docx) — match windows mentioning the phase."""
    phase = {"name": "Design", "section_marker": None}
    wins = [{"locator": "lines 1-5", "text": "the design stage"},
            {"locator": "lines 6-9", "text": "unrelated content"}]
    got = bpm.phase_windows(phase, [phase], {"id": "d", "text": "x"}, wins)
    assert [w["locator"] for w in got] == ["lines 1-5"]


def test_phase_named_but_never_detailed_gets_no_details():
    """A sequence can name more phases than the document details.

    The deck details only its first five phases; scavenging name-matched windows
    for the rest gave Launch an entry criterion of "Initiate the Project" and
    attached one gate to three phases.
    """
    detailed = {"name": "Procurement", "section_marker": "64"}
    undetailed = {"name": "Launch", "section_marker": None}
    wins = [{"locator": "slides 30-45", "text": "Initiate the Project ... launch readiness"}]
    got = bpm.phase_windows(undetailed, [detailed, undetailed], {"id": "d", "text": "x"}, wins)
    assert got == [], "a phase the document never details must stay empty"


def test_a_sections_own_heading_is_not_a_gate(stub_llm):
    """Asked what gate ends Ideation, the model answered "Ideation Phase"."""
    text = "Ideation Phase covers idea generation and creation of business concepts"
    stub_llm({"deliverables": [], "entry_criteria": [], "exit_criteria": [],
              "gate": {"name": "Ideation Phase", "evidence": text}, "policies": []})
    phase = {"name": "Ideation", "order": 1, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slides 20-23", "text": text}])
    assert phase["gate"] is None


def test_a_real_gate_in_the_phases_own_section_survives(stub_llm):
    text = ("Scoping concludes with Gate 1: Approval of Technical Recommendation "
            "before the project may proceed")
    stub_llm(*_details(gate={"value": "Gate 1: Approval of Technical Recommendation",
                             "evidence": "Gate 1: Approval of Technical Recommendation"}))
    phase = {"name": "Scoping", "order": 2, "sources": []}
    bpm.extract_details(phase, {"id": "d"}, [{"locator": "slides 24-38", "text": text}])
    assert phase["gate"]["name"].startswith("Gate 1")


# --------------------------------------------------------------------------- #
# Overrides survive a rebuild
# --------------------------------------------------------------------------- #

def _map(document="deck", phases=None):
    return {"processes": [{"document": document, "phases": phases or []}]}


def _write_overrides(tmp_path, monkeypatch, payload):
    path = tmp_path / "process_map.overrides.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(bpm, "OVERRIDES_PATH", str(path))


def test_overrides_patch_and_drop_phases(tmp_path, monkeypatch):
    _write_overrides(tmp_path, monkeypatch, {
        "drop_phases": ["Bogus"],
        "phases": {"Design": {"gate": {"name": "G3 (corrected)"}}},
    })
    result = bpm.apply_overrides(_map(phases=[
        {"name": "Design", "order": 2, "gate": None},
        {"name": "Bogus", "order": 3},
    ]))
    phases = result["processes"][0]["phases"]
    assert [p["name"] for p in phases] == ["Design"], "dropped phases should not survive"
    assert phases[0]["gate"]["name"] == "G3 (corrected)"
    assert phases[0]["overridden"] is True


def test_override_that_matches_nothing_is_reported(tmp_path, monkeypatch, capsys):
    """New docs may rename a phase; a silently inapplicable correction looks applied."""
    _write_overrides(tmp_path, monkeypatch, {
        "drop_phases": ["Gone"],
        "phases": {"Kapsam Belirleme": {"gate": {"name": "G1"}}},
    })
    bpm.apply_overrides(_map(phases=[{"name": "Scoping", "order": 1}]))
    err = capsys.readouterr().err
    assert "Kapsam Belirleme" in err and "Gone" in err


def test_overrides_can_be_scoped_per_process_document(tmp_path, monkeypatch):
    """Two process docs may both have a "Design" phase needing different fixes."""
    _write_overrides(tmp_path, monkeypatch, {"processes": {
        "sdlc": {"phases": {"Design": {"gate": {"name": "G3"}}}},
        "maintenance": {"phases": {"Design": {"gate": {"name": "M2"}}}},
    }})
    result = bpm.apply_overrides({"processes": [
        {"document": "sdlc", "phases": [{"name": "Design", "order": 1}]},
        {"document": "maintenance", "phases": [{"name": "Design", "order": 1}]},
    ]})
    assert result["processes"][0]["phases"][0]["gate"]["name"] == "G3"
    assert result["processes"][1]["phases"][0]["gate"]["name"] == "M2"


def test_missing_overrides_file_is_not_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(bpm, "OVERRIDES_PATH", str(tmp_path / "nope.json"))
    result = bpm.apply_overrides(_map(phases=[{"name": "Design", "order": 1}]))
    assert [p["name"] for p in result["processes"][0]["phases"]] == ["Design"]


# --------------------------------------------------------------------------- #
# Several process documents describe several processes, not one blended one
# --------------------------------------------------------------------------- #

def test_each_process_document_keeps_its_own_lifecycle(monkeypatch, tmp_path):
    """Merging two process docs invents a lifecycle nobody follows."""
    docs = [
        {"id": "sdlc", "path": "x", "text": "[Slide 1]\nScoping then Design in the sdlc flow"},
        {"id": "maintenance", "path": "y", "text": "[Slide 1]\nTriage then Patch in maintenance"},
    ]
    monkeypatch.setattr(bpm, "load_documents", lambda: docs)
    monkeypatch.setattr(bpm, "classify",
                        lambda d: {"process_defining": True, "confidence": 1.0, "reason": ""})
    monkeypatch.setattr(bpm, "extract_phases",
                        lambda d: [{"name": n, "order": i + 1, "sources": [], "section_marker": None}
                                   for i, n in enumerate(
                                       ["Scoping", "Design"] if d["id"] == "sdlc" else ["Triage", "Patch"])])
    monkeypatch.setattr(bpm, "extract_details", lambda *a, **k: None)
    monkeypatch.setattr(bpm, "OVERRIDES_PATH", str(tmp_path / "none.json"))
    monkeypatch.setattr(bpm, "CACHE_PATH", str(tmp_path / "cache.json"))

    result = bpm.build()
    assert [p["document"] for p in result["processes"]] == ["sdlc", "maintenance"]
    assert [p["name"] for p in result["processes"][0]["phases"]] == ["Scoping", "Design"]
    assert [p["name"] for p in result["processes"][1]["phases"]] == ["Triage", "Patch"]


# --------------------------------------------------------------------------- #
# Classification cache
# --------------------------------------------------------------------------- #

def test_unchanged_document_reuses_its_verdict(monkeypatch, tmp_path):
    doc_file = tmp_path / "d.txt"
    doc_file.write_text("content", encoding="utf-8")
    doc = {"id": "d", "path": str(doc_file), "text": "content"}

    calls = []
    monkeypatch.setattr(bpm, "_ollama_json", lambda *a, **k: calls.append(1) or
                        {"process_defining": True, "confidence": 1.0, "reason": "r"})
    monkeypatch.setattr(bpm, "_CACHE", {})

    assert bpm.classify(doc)["process_defining"] is True
    second = bpm.classify(doc)
    assert second["cached"] is True and len(calls) == 1


def test_edited_document_is_reclassified(monkeypatch, tmp_path):
    doc_file = tmp_path / "d.txt"
    doc_file.write_text("content", encoding="utf-8")
    doc = {"id": "d", "path": str(doc_file), "text": "content"}
    monkeypatch.setattr(bpm, "_ollama_json", lambda *a, **k:
                        {"process_defining": True, "confidence": 1.0, "reason": "r"})
    monkeypatch.setattr(bpm, "_CACHE", {})
    bpm.classify(doc)

    doc_file.write_text("different content entirely", encoding="utf-8")
    os.utime(doc_file, (0, 0))
    assert not bpm.classify(doc).get("cached")


def test_failed_classification_is_not_cached(monkeypatch, tmp_path):
    """One bad run must not stick until the file is touched."""
    doc_file = tmp_path / "d.txt"
    doc_file.write_text("content", encoding="utf-8")
    doc = {"id": "d", "path": str(doc_file), "text": "content"}
    monkeypatch.setattr(bpm, "_ollama_json", lambda *a, **k: {})   # call failed
    monkeypatch.setattr(bpm, "_CACHE", {})
    bpm.classify(doc)
    assert bpm._CACHE == {}
