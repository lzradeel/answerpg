"""Tests for the evaluation metrics: source-level retrieval scores and answer quality scores."""

import pytest

from answerpg.answering import NOT_FOUND, remove_citations
from evaluation.scoring import (
    faithfulness_score,
    inverse_rank,
    relevance_score,
    similarity_score,
    source_recall,
)

# Help-centre passages for an invented city bike-share scheme, keyed by citation number.
PASSAGES = {
    1: (
        "Day passes cost 6 euros and cover unlimited rides of up to 30 minutes. "
        "Electric bikes add a surcharge of 2 euros per ride."
    ),
    2: "A bike left outside a dock for more than 24 hours is reported as lost.",
}
# Each claim repeats one passage sentence word for word and cites that passage.
DAY_PASS = "Day passes cost 6 euros and cover unlimited rides of up to 30 minutes [1]."
LOST_BIKE = "A bike left outside a dock for more than 24 hours is reported as lost [2]."
# Filled in with a fleet size written with or without a thousands separator.
FLEET_SIZE = "Over the spring season the city fleet grew to {} bikes spread across 85 docks"


def test_recall_counts_each_source_once():
    """Repeated ids for one source, retrieved or relevant, add up to a single source."""
    ranked = ["fares", "fares", "docks", "helmets"]
    assert source_recall(ranked, ["fares", "helmets"], k=2) == 0.5
    assert source_recall(ranked, ["fares", "helmets"], k=4) == 1.0
    assert source_recall(["fares"], ["fares", "fares"], k=1) == 1.0


def test_recall_ignores_sources_ranked_past_k():
    """A relevant source just below the cutoff does not count until k reaches it."""
    ranked = ["docks", "fares", "helmets"]
    assert source_recall(ranked, ["helmets"], k=2) == 0.0
    assert source_recall(ranked, ["helmets"], k=3) == 1.0


def test_recall_is_zero_when_there_is_nothing_to_match():
    """An empty ranking, or a question without relevant sources, scores 0.0."""
    assert source_recall([], ["fares"], k=5) == 0.0
    assert source_recall(["fares"], [], k=1) == 0.0


def test_inverse_rank_uses_the_first_relevant_position():
    """The score is one over the rank of the earliest relevant source; later ones do not matter."""
    assert inverse_rank(["docks", "helmets", "fares"], ["fares", "lockers"]) == pytest.approx(1 / 3)
    assert inverse_rank(["docks", "lockers", "fares"], ["fares", "lockers"]) == 0.5
    assert inverse_rank(["fares"], ["fares"]) == 1.0


def test_inverse_rank_is_zero_without_a_relevant_source():
    """A ranking that never reaches a relevant source, or is empty, scores 0.0."""
    assert inverse_rank(["docks", "helmets"], ["fares"]) == 0.0
    assert inverse_rank([], ["fares"]) == 0.0


def test_cited_and_supported_answer_scores_one(encoder):
    """Every sentence cites a passage that states it, so the whole answer is faithful."""
    assert faithfulness_score(f"{DAY_PASS} {LOST_BIKE}", PASSAGES, encoder) == 1.0


def test_markers_after_the_full_stop_still_count(encoder):
    """Citations written after the closing punctuation stay with the sentence they follow."""
    answer = (
        "Day passes cost 6 euros and cover unlimited rides of up to 30 minutes. [1] "
        "A bike left outside a dock for more than 24 hours is reported as lost. [2]"
    )
    assert faithfulness_score(answer, PASSAGES, encoder) == 1.0


def test_altered_figure_is_unsupported(encoder):
    """A number the cited passage never mentions sinks the sentence, however close the wording."""
    answer = "Day passes cost 9 euros and cover unlimited rides of up to 30 minutes [1]."
    assert faithfulness_score(answer, PASSAGES, encoder) == 0.0
    assert faithfulness_score(answer, PASSAGES, encoder, threshold=0.0) == 0.0


@pytest.mark.parametrize(
    ("in_passage", "in_answer"),
    [("1,250", "1250"), ("1250", "1,250")],
    ids=["comma-in-passage", "comma-in-answer"],
)
def test_thousands_separator_does_not_change_a_figure(encoder, in_passage, in_answer):
    """1,250 and 1250 are the same number, whichever side writes the comma."""
    passages = {1: FLEET_SIZE.format(in_passage) + "."}
    answer = FLEET_SIZE.format(in_answer) + " [1]."
    assert faithfulness_score(answer, passages, encoder) == 1.0


def test_uncited_sentence_is_unsupported(encoder):
    """A correct sentence without a marker still counts against the answer."""
    answer = f"{DAY_PASS} A bike left outside a dock for more than 24 hours is reported as lost."
    assert faithfulness_score(answer, PASSAGES, encoder) == 0.5


def test_cited_claim_the_passage_never_makes_is_unsupported(encoder):
    """Pointing at a real passage does not support a claim that passage does not contain."""
    answer = "Helmets can be borrowed from the front desk on request [2]."
    assert faithfulness_score(answer, PASSAGES, encoder) == 0.0


def test_unrelated_sentence_appended_halves_the_score(encoder):
    """A supported sentence followed by an off-topic cited one averages out at 0.5."""
    answer = f"{DAY_PASS} Riders may carry one small pet in the front basket [1]."
    assert faithfulness_score(answer, PASSAGES, encoder) == 0.5


def test_answer_without_any_markers_scores_zero(encoder):
    """Stripping the citations from a faithful answer leaves nothing supported."""
    answer = remove_citations(f"{DAY_PASS} {LOST_BIKE}")
    assert faithfulness_score(answer, PASSAGES, encoder) == 0.0


def test_marker_for_a_missing_passage_scores_zero(encoder):
    """A citation number with no passage behind it supports nothing."""
    answer = "Day passes cost 6 euros and cover unlimited rides of up to 30 minutes [4]."
    assert faithfulness_score(answer, PASSAGES, encoder) == 0.0


def test_not_found_reply_is_fully_faithful(encoder):
    """Declining to answer scores 1.0, even with a stray marker or no passages at all."""
    assert faithfulness_score(NOT_FOUND, PASSAGES, encoder) == 1.0
    assert faithfulness_score(f"{NOT_FOUND} [1]", PASSAGES, encoder) == 1.0
    assert faithfulness_score(NOT_FOUND, {}, encoder) == 1.0


def test_threshold_sets_how_close_a_claim_must_be(encoder):
    """With no bar an off-topic cited claim passes; an unreachable bar rejects an exact copy."""
    off_topic = "Helmets can be borrowed from the front desk on request [2]."
    assert faithfulness_score(off_topic, PASSAGES, encoder, threshold=0.0) == 1.0
    assert faithfulness_score(DAY_PASS, PASSAGES, encoder, threshold=1.5) == 0.0


def test_relevance_favours_the_on_topic_answer(encoder):
    """An answer about the question's subject outscores one about something else."""
    question = "When is a bike reported as lost?"
    on_topic = relevance_score(question, LOST_BIKE, encoder)
    assert on_topic > relevance_score(question, DAY_PASS, encoder)
    assert on_topic == pytest.approx(
        relevance_score(question, remove_citations(LOST_BIKE), encoder)
    )


def test_similarity_to_the_reference_ignores_citations(encoder):
    """An answer equal to the reference apart from its marker scores about 1.0."""
    reference = "A bike left outside a dock for more than 24 hours is reported as lost."
    assert similarity_score(reference, LOST_BIKE, encoder) == pytest.approx(1.0)
    assert similarity_score(reference, f"{reference} [2]", encoder) == pytest.approx(1.0)


def test_similarity_of_an_unrelated_answer_is_low(encoder):
    """An answer on a different subject stays well below 0.5."""
    reference = "A bike left outside a dock for more than 24 hours is reported as lost."
    assert similarity_score(reference, DAY_PASS, encoder) < 0.5
