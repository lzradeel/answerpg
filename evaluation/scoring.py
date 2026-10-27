"""Metrics used by the evaluation gate.

Retrieval is scored per source (recall@k and inverse rank); answers are scored for faithfulness
to the passages they cite and for embedding similarity to the question and the reference answer.
"""

import re

import numpy as np

from answerpg.answering import CITE_MARK, NOT_FOUND, remove_citations, tidy_citations
from answerpg.corpus import split_into_sentences
from answerpg.encoders import VectorEncoder

NUMERIC = re.compile(r"\d+(?:[.,]\d+)*")
# Tuned with bge-small against the question set. Unrelated sentences tacked onto genuine answers
# peaked at 0.79, so 0.8 is the lowest cut-off that rejects every one of them, and it still
# accepts 82% of the paraphrased reference sentences.
SUPPORT_THRESHOLD = 0.8


def source_recall(retrieved_docs: list[str], relevant_docs: list[str], k: int) -> float:
    """Fraction of the distinct relevant sources found among the first k retrieved source ids.

    Recall is counted per source, so several passages from one source count once. Returns 0.0
    when there are no relevant sources.
    """
    relevant = set(relevant_docs)
    if not relevant:
        return 0.0
    top_k = set(retrieved_docs[:k])
    return len(relevant & top_k) / len(relevant)


def inverse_rank(retrieved_docs: list[str], relevant_docs: list[str]) -> float:
    """Inverse rank: 1/position (from 1) of the first relevant source id retrieved, 0.0 if none."""
    for position, candidate in enumerate(retrieved_docs, start=1):
        if candidate in relevant_docs:
            return 1 / position
    return 0.0


def _numbers_in(text: str) -> set[str]:
    """Numeric tokens of text with commas stripped, so "1,000" and "1000" compare equal."""
    return {token.replace(",", "") for token in NUMERIC.findall(text)}


def faithfulness_score(
    answer: str,
    contexts: dict[int, str],
    encoder: VectorEncoder,
    threshold: float = SUPPORT_THRESHOLD,
) -> float:
    """Share of answer sentences that are supported by the passages they cite.

    contexts maps citation numbers to passage text. A sentence is supported only if it points at
    one or more passages present in contexts, each numeric token in it also appears in the text
    of those passages, and its embedding reaches a cosine similarity of at least threshold with
    one or more of their sentences. An answer that is just NOT_FOUND (citation markers aside) is
    fully faithful; one without any valid citation scores 0.0.
    """
    if remove_citations(answer) == NOT_FOUND:
        return 1.0
    claims: list[tuple[str, set[int]]] = []
    for sentence in split_into_sentences(tidy_citations(answer)):
        valid_refs = {int(ref) for ref in CITE_MARK.findall(sentence)} & contexts.keys()
        claims.append((remove_citations(sentence), valid_refs))
    cited = sorted(set().union(*(refs for _, refs in claims)))
    if not cited:
        return 0.0

    # One encode call: the claim vectors come first, then one vector per evidence sentence.
    evidence = [
        (ref, sentence) for ref in cited for sentence in split_into_sentences(contexts[ref])
    ]
    vectors = encoder.encode_passages(
        [claim for claim, _ in claims] + [sentence for _, sentence in evidence]
    )
    claim_vectors, evidence_vectors = vectors[: len(claims)], vectors[len(claims) :]
    evidence_refs = np.array([ref for ref, _ in evidence])

    supported = 0
    for (claim, refs), claim_vector in zip(claims, claim_vectors, strict=True):
        if not refs:
            continue
        cited_text = " ".join(contexts[ref] for ref in refs)
        if not _numbers_in(claim) <= _numbers_in(cited_text):
            continue
        from_cited = np.isin(evidence_refs, list(refs))
        if not from_cited.any():
            continue
        if float((evidence_vectors[from_cited] @ claim_vector).max()) >= threshold:
            supported += 1
    return supported / len(claims)


def _pair_similarity(encoder: VectorEncoder, first: str, second: str) -> float:
    """Cosine similarity of two texts embedded in one batch (the encoder returns unit vectors)."""
    first_vector, second_vector = encoder.encode_passages([first, second])
    return float(first_vector @ second_vector)


def relevance_score(question: str, answer: str, encoder: VectorEncoder) -> float:
    """Cosine similarity between the question and the answer without its citation markers."""
    return _pair_similarity(encoder, question, remove_citations(answer))


def similarity_score(reference: str, answer: str, encoder: VectorEncoder) -> float:
    """Cosine similarity between the reference answer and the answer without citation markers."""
    return _pair_similarity(encoder, reference, remove_citations(answer))
