"""Evaluation gate: answer the question set, score the results and guard against regressions.

Run it as ``python -m evaluation.gate``. It writes a markdown report and exits with status 1 when
a metric drops more than the tolerance below its baseline value, and 0 otherwise (including when
the baseline is being rewritten or does not exist yet).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from answerpg.engine import AnswerEngine, AnswerResult, RetrievalResult
from evaluation import scoring

# Allowed drop below a baseline value when the baseline file does not set its own tolerance.
TOLERANCE_DEFAULT = 0.02
# (label, search mode, rerank) for each retriever measured by --compare.
RETRIEVER_VARIANTS = [
    ("keyword", "keyword", False),
    ("semantic", "semantic", False),
    ("hybrid", "hybrid", False),
    ("hybrid + rerank", "hybrid", True),
]


def read_questions(path: Path) -> list[dict]:
    """Load the question set: one JSON object per line, blank lines ignored."""
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(raw) for raw in raw_lines if raw.strip()]


def _source_ids(result: AnswerResult | RetrievalResult) -> list[str]:
    """Source id of every match, best match first."""
    return [item.source_id for item in result.matches]


def score_questions(
    engine: AnswerEngine, questions: list[dict], k: int, mode: str, rerank: bool
) -> list[dict]:
    """Answer each question and score its retrieval and its reply, returning one row apiece."""
    encoder = engine.encoder
    rows = []
    for entry in questions:
        outcome = engine.answer(entry["question"], k=k, mode=mode, rerank=rerank)
        ranked_sources = _source_ids(outcome)
        # Citation [n] in the reply points at the n-th match, so passages are numbered from 1.
        passages = {ref: item.body for ref, item in enumerate(outcome.matches, start=1)}
        reply = outcome.reply.text
        rows.append(
            {
                "id": entry["id"],
                "question": entry["question"],
                "reply": reply,
                "model": outcome.reply.model,
                "recall": scoring.source_recall(ranked_sources, entry["sources"], k),
                "inverse_rank": scoring.inverse_rank(ranked_sources, entry["sources"]),
                "faithfulness": scoring.faithfulness_score(reply, passages, encoder),
                "relevance": scoring.relevance_score(entry["question"], reply, encoder),
                "similarity": scoring.similarity_score(entry["reference"], reply, encoder),
                "latency_ms": outcome.timings_ms["total"],
                "cost_usd": outcome.reply.cost_usd,
            }
        )
    return rows


def compare_retrievers(engine: AnswerEngine, questions: list[dict], k: int) -> list[tuple]:
    """Run retrieval alone, without answering, for every entry of RETRIEVER_VARIANTS.

    Returns one (label, mean recall@k, mean inverse rank, median latency in ms) tuple per variant.
    """
    comparison = []
    for label, mode, rerank in RETRIEVER_VARIANTS:
        recalls, inverse_ranks, latencies = [], [], []
        for entry in questions:
            outcome = engine.retrieve(entry["question"], k=k, mode=mode, rerank=rerank)
            ranked_sources = _source_ids(outcome)
            recalls.append(scoring.source_recall(ranked_sources, entry["sources"], k))
            inverse_ranks.append(scoring.inverse_rank(ranked_sources, entry["sources"]))
            latencies.append(outcome.timings_ms["total"])
        comparison.append((label, np.mean(recalls), np.mean(inverse_ranks), np.median(latencies)))
    return comparison


def aggregate(rows: list[dict], k: int) -> dict[str, float]:
    """Mean of each metric over all rows, rounded to 3 decimals and keyed by its baseline name.

    mrr is the mean of the per-question inverse ranks.
    """
    row_key_for = {
        f"recall@{k}": "recall",
        "mrr": "inverse_rank",
        "faithfulness": "faithfulness",
        "answer_relevance": "relevance",
        "answer_similarity": "similarity",
    }
    return {
        metric: round(float(np.mean([row[key] for row in rows])), 3)
        for metric, key in row_key_for.items()
    }


def _tolerance_of(baseline: dict | None) -> float:
    """Tolerance recorded in the baseline, falling back to TOLERANCE_DEFAULT."""
    return baseline.get("tolerance", TOLERANCE_DEFAULT) if baseline else TOLERANCE_DEFAULT


def check_regressions(scores: dict[str, float], baseline: dict | None) -> tuple[list[tuple], bool]:
    """Compare every score with the baseline and report whether any metric regressed.

    Returns (metric, baseline value, current value, status) rows and a failure flag. A metric fails
    when it is below its baseline value minus the tolerance; that bound is rounded to six decimals
    so float error cannot fail a score sitting exactly on it. Metrics missing from the baseline are
    marked "new" and never fail.
    """
    tolerance = _tolerance_of(baseline)
    previous = baseline["metrics"] if baseline else {}
    verdicts = []
    for name, value in scores.items():
        base = previous.get(name)
        if base is None:
            status = "new"
        elif value < round(base - tolerance, 6):
            status = "FAIL"
        else:
            status = "ok"
        verdicts.append((name, base, value, status))
    return verdicts, any(status == "FAIL" for *_, status in verdicts)


def summary_markdown(
    config: str, gate_table: list[tuple], rows: list[dict], comparison: list[tuple], k: int
) -> str:
    """Render the head of the report: run settings, gate table, latency and cost, retrievers.

    config is the one-line description of the run shown under the title; the retriever table is
    only added when comparison is non-empty.
    """
    lines = [
        f"# Answer quality report\n\n{config}\n",
        "| metric | baseline | this run | change | status |",
        "|---|---:|---:|---:|---|",
    ]
    for name, base, value, status in gate_table:
        if base is None:
            lines.append(f"| {name} | - | {value:.3f} | - | {status} |")
        else:
            lines.append(f"| {name} | {base:.3f} | {value:.3f} | {value - base:+.3f} | {status} |")
    latencies = [row["latency_ms"] for row in rows]
    mean_cost = np.mean([row["cost_usd"] for row in rows])
    lines.append(
        f"\nEnd-to-end time per question: p50 {np.percentile(latencies, 50):.1f} ms, "
        f"p95 {np.percentile(latencies, 95):.1f} ms. Average cost: ${mean_cost:.6f} per question."
    )
    if comparison:
        lines += [
            f"\n## Retrieval modes side by side\n\n| retriever | recall@{k} | MRR | median ms |",
            "|---|---:|---:|---:|",
        ]
        for label, recall, mrr, median_ms in comparison:
            lines.append(f"| {label} | {recall:.3f} | {mrr:.3f} | {median_ms:.1f} |")
    return "\n".join(lines) + "\n"


def details_markdown(rows: list[dict]) -> str:
    """Render the per-question scores, then every question short of 1.0 on recall or faithfulness.

    Each reply is collapsed onto one line so it stays inside its list item.
    """
    lines = [
        "\n## Scores per question\n",
        "| id | recall | 1/rank | faithfulness | relevance | similarity | ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['recall']:.2f} | {row['inverse_rank']:.2f} "
            f"| {row['faithfulness']:.2f} | {row['relevance']:.3f} | {row['similarity']:.3f} "
            f"| {row['latency_ms']:.1f} |"
        )
    shortfalls = [row for row in rows if row["recall"] < 1 or row["faithfulness"] < 1]
    if shortfalls:
        lines.append("\n## Questions below 1.0 on recall or faithfulness\n")
        for row in shortfalls:
            reply = " ".join(row["reply"].split())
            lines.append(
                f"- **{row['id']}** {row['question']} (recall {row['recall']:.2f}, "
                f"faithfulness {row['faithfulness']:.2f})  \n  Reply: {reply}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    """Run the evaluation from the command line and return the exit status (1 on a regression)."""
    parser = argparse.ArgumentParser(
        description="Answer the question set, score retrieval and answers, write a markdown "
        "report and exit with status 1 if a metric regressed against the baseline."
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path("evaluation/questions.jsonl"),
        help="question set, one JSON object per line (default: %(default)s)",
    )
    parser.add_argument(
        "--k", type=int, default=5, help="passages retrieved per question (default: %(default)s)"
    )
    parser.add_argument(
        "--mode",
        choices=["hybrid", "keyword", "semantic"],
        default="hybrid",
        help="search mode used to answer (default: %(default)s)",
    )
    parser.add_argument(
        "--no-rerank", dest="rerank", action="store_false", help="skip cross-encoder reranking"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("evaluation/baseline.json"),
        help="scores to gate against (default: %(default)s)",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="save this run's scores as the new baseline instead of gating on them",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("evaluation/results.md"),
        help="where to write the markdown report (default: %(default)s)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="also measure retrieval alone for keyword, semantic, hybrid and reranked search",
    )
    args = parser.parse_args()

    questions = read_questions(args.questions)
    with AnswerEngine.from_config() as engine:
        rows = score_questions(engine, questions, args.k, args.mode, args.rerank)
        comparison = compare_retrievers(engine, questions, args.k) if args.compare else []
        backend = engine.backend.name

    scores = aggregate(rows, args.k)
    baseline = json.loads(args.baseline.read_text()) if args.baseline.exists() else None
    verdicts, regressed = check_regressions(scores, baseline)
    models = ", ".join(sorted({row["model"] for row in rows}))
    header = (
        f"Run settings: {len(rows)} questions, k={args.k}, `{args.mode}` retrieval, "
        f"reranking {'on' if args.rerank else 'off'}, answer backend `{backend}` ({models}), "
        f"faithfulness support threshold {scoring.SUPPORT_THRESHOLD}."
    )
    summary = summary_markdown(header, verdicts, rows, comparison, args.k)
    args.report.write_text(summary + details_markdown(rows), encoding="utf-8")
    print(summary)
    print(f"Full report saved to {args.report}")

    if args.write_baseline:
        content = json.dumps({"tolerance": _tolerance_of(baseline), "metrics": scores}, indent=2)
        args.baseline.write_text(content + "\n", encoding="utf-8")
        print(f"New baseline saved to {args.baseline}")
        return 0
    if baseline is None:
        print(f"No baseline found at {args.baseline}, so the regression check was skipped.")
        print("To record one, run: python -m evaluation.gate --write-baseline")
        return 0
    if regressed:
        print("Gate failed: a metric dropped more than the tolerance below its baseline.")
        return 1
    print("Gate passed: no metric dropped more than the tolerance below its baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
