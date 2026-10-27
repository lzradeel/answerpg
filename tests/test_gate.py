"""Tests for evaluation.gate: the regression check, score aggregation and the command line.

main() runs against a canned engine with its question set, baseline and report in tmp_path, so
no model or database is involved.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from answerpg.answering import Reply
from answerpg.engine import AnswerResult, RetrievalResult
from answerpg.retrieval import Match
from evaluation.gate import aggregate, check_regressions, main

BASELINE_FILE = "baseline.json"
REPORT_FILE = "results.md"

# Passages from an invented allotment society's handbook, one per source. The gate never reads
# match scores, so they are all left at zero.
TOOL_SHED = Match(
    301, "tool-shed", "Tool shed", "Members can borrow a wheelbarrow from the tool shed.", 0.0
)
WATERING = Match(302, "watering", "Watering", "The water trough is refilled every Monday.", 0.0)
COMPOST = Match(303, "compost", "Compost", "Compost bays are turned on the first Saturday.", 0.0)

WHEELBARROW_QUESTION = "Can members borrow a wheelbarrow from the tool shed?"
TROUGH_QUESTION = "Is the water trough refilled every Monday?"
QUESTIONS = [
    {
        "id": "q1",
        "question": WHEELBARROW_QUESTION,
        "sources": ["tool-shed"],
        "reference": "Members can borrow a wheelbarrow from the tool shed.",
    },
    {
        "id": "q2",
        "question": TROUGH_QUESTION,
        "sources": ["watering"],
        "reference": "The water trough is refilled every Monday.",
    },
]
# What the canned engine returns for each question: its ranking, best first, and its reply.
CANNED = {
    WHEELBARROW_QUESTION: (
        [TOOL_SHED, COMPOST, WATERING],
        "Members can borrow a wheelbarrow from the tool shed [1].",
    ),
    TROUGH_QUESTION: (
        [COMPOST, WATERING, TOOL_SHED],
        "The water trough is refilled every Monday [2].",
    ),
}
# The scores main() gives the canned run at k=2. Both relevant sources make the top two (recall
# 1.0), at ranks 1 and 2 (mrr 0.75). Each reply quotes the passage it cites and repeats its
# reference word for word, and it reuses exactly its question's words, which is all the
# order-blind hashing encoder looks at, so the three answer metrics come out at 1.0.
CANNED_SCORES = {
    "recall@2": 1.0,
    "mrr": 0.75,
    "faithfulness": 1.0,
    "answer_relevance": 1.0,
    "answer_similarity": 1.0,
}


class CannedEngine:
    """Stand-in for AnswerEngine that serves the CANNED rankings and replies and logs each call."""

    backend = SimpleNamespace(name="canned")

    def __init__(self, encoder):
        """Keep the encoder main() scores replies with and start with empty call logs."""
        self.encoder = encoder
        self.answered: list[tuple] = []
        self.retrieved: list[tuple] = []

    def __enter__(self) -> "CannedEngine":
        """Hand back the engine itself, as AnswerEngine does."""
        return self

    def __exit__(self, *exc_info) -> None:
        """Nothing to close."""

    def answer(
        self, question: str, k: int | None = None, mode: str = "hybrid", rerank: bool = True
    ) -> AnswerResult:
        """Return the canned reply along with the top k of the canned ranking."""
        self.answered.append((k, mode, rerank))
        ranking, text = CANNED[question]
        return AnswerResult(Reply(text, [], "canned"), ranking[:k], {"compose": 0.4, "total": 2.5})

    def retrieve(
        self, query: str, k: int | None = None, mode: str = "hybrid", rerank: bool = True
    ) -> RetrievalResult:
        """Return the top k of the canned ranking, as retrieval on its own would."""
        self.retrieved.append((k, mode, rerank))
        ranking, _ = CANNED[query]
        return RetrievalResult(ranking[:k], {"total": 1.5})


def save_baseline(directory: Path, baseline: dict | None) -> None:
    """Write the baseline file into directory; None leaves it absent."""
    if baseline is not None:
        (directory / BASELINE_FILE).write_text(json.dumps(baseline), encoding="utf-8")


def load_baseline(directory: Path) -> dict | None:
    """Read the baseline file back from directory, or None when there is none."""
    path = directory / BASELINE_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def scores_row(
    recall: float, inverse_rank: float, faithfulness: float, relevance: float, similarity: float
) -> dict[str, float]:
    """One question's five scores, keyed the way score_questions keys them."""
    return {
        "recall": recall,
        "inverse_rank": inverse_rank,
        "faithfulness": faithfulness,
        "relevance": relevance,
        "similarity": similarity,
    }


@pytest.fixture
def canned_engine(monkeypatch, encoder) -> CannedEngine:
    """Make AnswerEngine.from_config hand main() a CannedEngine, and return that engine."""
    engine = CannedEngine(encoder)
    monkeypatch.setattr("evaluation.gate.AnswerEngine.from_config", lambda config=None: engine)
    return engine


@pytest.fixture
def run_gate(tmp_path, monkeypatch, canned_engine):
    """Return a function that runs main() on the canned engine and gives back its exit status.

    Every run reads the question set from tmp_path, gates against the baseline file there and
    writes its report there too, with k=2 and whatever extra flags the test passes.
    """
    questions = tmp_path / "questions.jsonl"
    lines = [json.dumps(entry) + "\n" for entry in QUESTIONS]
    questions.write_text("".join(lines), encoding="utf-8")
    file_flags = ["--questions", str(questions), "--baseline", str(tmp_path / BASELINE_FILE)]
    file_flags += ["--report", str(tmp_path / REPORT_FILE)]

    def run(*flags: str) -> int:
        """Run main() with these flags after the tmp_path files and k=2; return its status."""
        monkeypatch.setattr(sys, "argv", ["gate", *file_flags, "--k", "2", *flags])
        return main()

    return run


# In floating point 0.9 - 0.06 and 0.26 - 0.02 land a hair above 0.84 and 0.24, so the scores
# sitting on those bounds only pass because check_regressions rounds the bound to six places.
@pytest.mark.parametrize(
    ("baseline", "score", "status"),
    [
        pytest.param({"tolerance": 0.06, "metrics": {"mrr": 0.9}}, 0.84, "ok", id="on-bound"),
        pytest.param({"tolerance": 0.06, "metrics": {"mrr": 0.9}}, 0.839, "FAIL", id="below"),
        pytest.param({"metrics": {"mrr": 0.26}}, 0.24, "ok", id="on-default-bound"),
        pytest.param({"metrics": {"mrr": 0.26}}, 0.239, "FAIL", id="below-default"),
    ],
)
def test_metric_holds_down_to_baseline_minus_tolerance(baseline, score, status):
    """A score on baseline minus tolerance (0.02 by default) is ok; 0.001 below it fails."""
    expected = ([("mrr", baseline["metrics"]["mrr"], score, status)], status == "FAIL")
    assert check_regressions({"mrr": score}, baseline) == expected


def test_metric_missing_from_the_baseline_is_new():
    """A metric the baseline never recorded is "new", has no baseline value and cannot fail."""
    baseline = {"tolerance": 0.02, "metrics": {"recall@5": 0.9}}
    verdicts, failed = check_regressions({"recall@5": 0.91, "answer_similarity": 0.05}, baseline)
    assert verdicts == [("recall@5", 0.9, 0.91, "ok"), ("answer_similarity", None, 0.05, "new")]
    assert not failed


def test_without_a_baseline_every_metric_is_new():
    """With no baseline at all, every metric is "new" and nothing fails."""
    verdicts, failed = check_regressions({"recall@5": 0.4, "mrr": 0.3}, None)
    assert verdicts == [("recall@5", None, 0.4, "new"), ("mrr", None, 0.3, "new")]
    assert not failed


@pytest.mark.parametrize(
    ("faithfulness", "statuses", "failed"),
    [
        pytest.param(0.97, ["ok", "ok", "new"], False, id="all-hold"),
        pytest.param(0.95, ["ok", "FAIL", "new"], True, id="one-fails"),
    ],
)
def test_run_fails_only_when_a_metric_fails(faithfulness, statuses, failed):
    """Metrics that are ok or new leave the run passing; a single FAIL among them fails it."""
    baseline = {"tolerance": 0.02, "metrics": {"recall@5": 0.9, "faithfulness": 0.98}}
    scores = {"recall@5": 0.95, "faithfulness": faithfulness, "mrr": 0.5}
    verdicts, regressed = check_regressions(scores, baseline)
    assert [status for *_, status in verdicts] == statuses
    assert regressed is failed


def test_aggregate_rounds_each_mean_to_three_decimals():
    """Each metric is its mean over the questions rounded to three places; mrr averages 1/rank."""
    rows = [
        scores_row(1.0, 1.0, 1.0, 0.9135, 0.8),
        scores_row(0.5, 1 / 2, 0.5, 0.6, 0.75),
        scores_row(0.0, 1 / 3, 1.0, 0.7, 0.7001),
    ]
    assert aggregate(rows, k=5) == {
        "recall@5": 0.5,
        "mrr": 0.611,  # 0.6111...
        "faithfulness": 0.833,  # 0.8333...
        "answer_relevance": 0.738,  # 0.737833...
        "answer_similarity": 0.75,  # 0.750033...
    }


@pytest.mark.parametrize("k", [3, 10])
def test_aggregate_keys_come_in_a_fixed_order_with_k_in_the_recall_label(k):
    """Keys run recall@k, mrr, faithfulness, answer_relevance, answer_similarity."""
    scores = aggregate([scores_row(1.0, 1.0, 1.0, 0.8, 0.7)], k)
    expected = [f"recall@{k}", "mrr", "faithfulness", "answer_relevance", "answer_similarity"]
    assert list(scores) == expected


@pytest.mark.parametrize(
    ("baseline", "status"),
    [
        # The canned run scores mrr 0.75, inside 0.02 of 0.77 but more than that below 0.8.
        pytest.param({"tolerance": 0.02, "metrics": {**CANNED_SCORES, "mrr": 0.77}}, 0, id="holds"),
        pytest.param({"tolerance": 0.02, "metrics": {**CANNED_SCORES, "mrr": 0.8}}, 1, id="drops"),
        pytest.param(None, 0, id="no-baseline"),
    ],
)
def test_main_exits_one_only_on_a_regression(tmp_path, run_gate, baseline, status):
    """main() exits 1 on a regression and 0 otherwise, writing the report but not the baseline."""
    save_baseline(tmp_path, baseline)
    assert run_gate() == status
    assert load_baseline(tmp_path) == baseline
    report = (tmp_path / REPORT_FILE).read_text(encoding="utf-8")
    assert all(metric in report for metric in CANNED_SCORES)


@pytest.mark.parametrize(
    ("old_baseline", "tolerance"),
    [
        # mrr 0.75 is well over 0.05 below 0.9, so this run regresses against the old baseline.
        pytest.param(
            {"tolerance": 0.05, "metrics": {**CANNED_SCORES, "mrr": 0.9}}, 0.05, id="kept"
        ),
        pytest.param({"metrics": CANNED_SCORES}, 0.02, id="no-tolerance-key"),
        pytest.param(None, 0.02, id="no-baseline"),
    ],
)
def test_write_baseline_saves_this_run_and_exits_zero(tmp_path, run_gate, old_baseline, tolerance):
    """--write-baseline exits 0 and saves this run's scores under the old or default tolerance."""
    save_baseline(tmp_path, old_baseline)
    assert run_gate("--write-baseline") == 0
    assert load_baseline(tmp_path) == {"tolerance": tolerance, "metrics": CANNED_SCORES}


def test_main_passes_search_flags_to_the_engine(run_gate, canned_engine):
    """--k, --mode and --no-rerank reach answer(); --compare runs each retriever on its own too."""
    assert run_gate("--mode", "keyword", "--no-rerank", "--compare") == 0
    assert canned_engine.answered == [(2, "keyword", False)] * len(QUESTIONS)
    assert set(canned_engine.retrieved) == {
        (2, "keyword", False),
        (2, "semantic", False),
        (2, "hybrid", False),
        (2, "hybrid", True),
    }
    assert len(canned_engine.retrieved) == 4 * len(QUESTIONS)
