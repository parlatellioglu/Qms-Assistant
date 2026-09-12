"""Late chunking (phase 2) for parent/child retrieval.

Naive chunking (phase 1) embeds every child chunk in isolation, so a child loses
the surrounding context of its parent. Late chunking fixes that: each PARENT is
run through the transformer ONCE to get contextualized token embeddings, and a
child's dense vector is the mean of the token embeddings that fall inside the
child's character span. The child therefore "sees" its whole parent, while still
being indexed/retrieved as a small unit.

This operates on the HF transformer behind BGE-M3 (the FlagEmbedding wrapper
exposes it as ``BGEM3FlagModel.model.model`` with the tokenizer at
``BGEM3FlagModel.tokenizer``). Only the DOCUMENT child DENSE vectors change here:
they become mean-pooled token spans instead of per-child CLS encodings. The query
is left to BGE-M3's native encoding at search time (a short query needs no parent
context, and the native query empirically retrieves the pooled children better),
and sparse/lexical weights stay per-child, computed by the caller as before.
"""
from typing import List, Tuple

import numpy as np
import torch

# Generous cap: parents are ~2000 chars (well under this), queries far shorter.
MAX_TOKENS = 8192


def _is_special(offset) -> bool:
    """Special tokens (CLS/EOS/pad) carry a zero-width (0, 0) offset mapping."""
    return offset[0] == 0 and offset[1] == 0


def _l2norm(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm > 0 else vec


@torch.no_grad()
def _token_states(hf_model, tokenizer, text: str, max_length: int = MAX_TOKENS):
    """Return (token_hidden_states[seq, hidden], offset_mapping[seq]) for ``text``."""
    enc = tokenizer(
        text,
        return_offsets_mapping=True,
        return_tensors="pt",
        truncation=True,
        max_length=max_length,
    )
    offsets = enc.pop("offset_mapping")[0].tolist()
    device = next(hf_model.parameters()).device
    enc = {k: v.to(device) for k, v in enc.items()}
    out = hf_model(**enc)
    return out.last_hidden_state[0], offsets


def _content_token_indices(offsets) -> List[int]:
    return [i for i, off in enumerate(offsets) if not _is_special(off)]


def _mean_pool_span(hidden, offsets, cstart: int, cend: int) -> np.ndarray:
    """Mean-pool the token hidden states whose char span overlaps [cstart, cend)."""
    idxs = [
        i
        for i, off in enumerate(offsets)
        if not _is_special(off) and off[0] < cend and off[1] > cstart
    ]
    if not idxs:  # span fell entirely on special tokens / mapping gap — degrade safely
        idxs = _content_token_indices(offsets) or list(range(len(offsets)))
    pooled = hidden[idxs].mean(dim=0).float().cpu().numpy()
    return _l2norm(pooled).astype("float32")


def encode_documents_late(
    hf_model,
    tokenizer,
    parent_groups: List[Tuple[str, List[Tuple[str, int, int]]]],
    max_length: int = MAX_TOKENS,
) -> List[np.ndarray]:
    """Late-chunk dense vectors for all children, grouped by parent.

    ``parent_groups`` is ``[(parent_text, [(child_text, cstart, cend), ...]), ...]``.
    Each parent is encoded once; children are mean-pooled from its token states.
    Returns one normalized float32 vector per child, flattened in the same order
    the children appear across ``parent_groups``.
    """
    vectors: List[np.ndarray] = []
    for parent_text, children in parent_groups:
        hidden, offsets = _token_states(hf_model, tokenizer, parent_text, max_length)
        for _child_text, cstart, cend in children:
            vectors.append(_mean_pool_span(hidden, offsets, cstart, cend))
    return vectors
