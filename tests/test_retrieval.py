"""Unit tests for reciprocal rank fusion; no database or model is involved."""

import copy

import pytest

from answerpg.retrieval import Match, fuse_rankings

# Passages from a made-up bakery handbook, keyed by passage id: (source id, title, body).
BAKERY = {
    201: ("starter-care", "Feeding the starter", "Feed the rye starter twice a day."),
    202: ("oven-schedule", "Oven schedule", "The deck oven reaches 250 degrees by half past four."),
    203: ("croissant-folds", "Laminating croissants", "Give croissant dough three single folds."),
    204: ("bagel-boil", "Boiling bagels", "Bagels boil for forty seconds a side in malted water."),
}


def passage(passage_id: int, score: float = 0.0) -> Match:
    """Build the Match for one bakery passage, carrying whatever score its retriever gave it."""
    source_id, title, body = BAKERY[passage_id]
    return Match(passage_id=passage_id, source_id=source_id, title=title, body=body, score=score)


def order_of(fused: list[Match]) -> list[int]:
    """The passage ids of a fused list, in the order fusion returned them."""
    return [item.passage_id for item in fused]


@pytest.mark.parametrize(
    ("k", "expected"),
    [
        pytest.param(60, {201: 1 / 61 + 1 / 62, 203: 1 / 63 + 1 / 61, 202: 1 / 62}, id="k=60"),
        pytest.param(1, {201: 1 / 2 + 1 / 3, 203: 1 / 4 + 1 / 2, 202: 1 / 3}, id="k=1"),
    ],
)
def test_scores_sum_reciprocal_ranks(k, expected):
    """Each passage earns 1/(k + rank) from every ranking that lists it, and the best sum leads."""
    keyword = [passage(201), passage(202), passage(203)]
    semantic = [passage(203), passage(201)]
    fused = fuse_rankings([keyword, semantic], k=k)
    assert {item.passage_id: item.score for item in fused} == pytest.approx(expected)
    assert order_of(fused) == [201, 203, 202]


def test_single_ranking_uses_default_k_of_60():
    """Without an explicit k a lone ranking keeps its order and is rescored 1/61, 1/62, 1/63."""
    fused = fuse_rankings([[passage(204, 0.9), passage(201, 0.4), passage(202, 0.1)]])
    assert order_of(fused) == [204, 201, 202]
    assert [item.score for item in fused] == pytest.approx([1 / 61, 1 / 62, 1 / 63])


def test_shared_passage_appears_once_with_first_fields():
    """A passage both retrievers return is listed once, with the fields it was first seen with."""
    first = passage(203, score=7.25)
    retold = Match(
        passage_id=203,
        source_id="croissant-draft",
        title="Croissant notes",
        body="Fold twice.",
        score=0.4,
    )
    fused = fuse_rankings([[first, passage(201)], [passage(204), retold]])
    assert order_of(fused) == [203, 204, 201]
    merged = fused[0]
    assert (merged.source_id, merged.title, merged.body) == BAKERY[203]
    assert merged.score == pytest.approx(1 / 61 + 1 / 62)


@pytest.mark.parametrize(
    ("ranked_ids", "expected"),
    [
        pytest.param([[201, 202], [203, 204]], [201, 203, 202, 204], id="disjoint"),
        pytest.param([[201, 202], [202, 201]], [201, 202], id="mirrored"),
        pytest.param([[202, 201], [201, 202]], [202, 201], id="mirrored-reversed"),
    ],
)
def test_ties_keep_first_seen_order(ranked_ids, expected):
    """Passages with equal fused scores stay in the order fusion first came across them."""
    rankings = [[passage(passage_id) for passage_id in ranking] for ranking in ranked_ids]
    assert order_of(fuse_rankings(rankings)) == expected


def test_inputs_are_not_mutated():
    """Fusion hands back rescored copies and leaves the caller's rankings exactly as they were."""
    rankings = [[passage(202, 11.5), passage(204, 3.0)], [passage(204, 0.82)]]
    snapshot = copy.deepcopy(rankings)
    fused = fuse_rankings(rankings)
    assert rankings == snapshot
    originals = [item for ranking in rankings for item in ranking]
    for item in fused:
        assert all(item is not original for original in originals)


@pytest.mark.parametrize(
    "rankings", [[], [[]], [[], []]], ids=["no-rankings", "one-empty", "all-empty"]
)
def test_empty_input_fuses_to_empty_list(rankings):
    """No rankings, or rankings with nothing in them, fuse to an empty list."""
    assert fuse_rankings(rankings) == []
