"""Benchmark AnswerEngine.answer(): per-stage latency percentiles, token usage and cost."""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from answerpg.engine import AnswerEngine

# Row order of the latency table; a stage that no answer recorded is left out.
REPORTED_STAGES = ["encode", "keyword", "semantic", "fusion", "rerank", "compose", "total"]


def main() -> None:
    """Answer the question set --runs times after an untimed warm-up call and print the stats."""
    parser = argparse.ArgumentParser(
        description="Time each stage of AnswerEngine.answer() and report token usage, cost per "
        "query and sequential throughput."
    )
    parser.add_argument(
        "--runs", type=int, default=5, help="passes over the question set (default: %(default)s)"
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
    args = parser.parse_args()

    raw_lines = args.questions.read_text(encoding="utf-8").splitlines()
    questions = [json.loads(raw)["question"] for raw in raw_lines if raw.strip()]

    with AnswerEngine.from_config() as engine:
        engine.answer(questions[0], k=args.k)  # warm-up, kept out of the measurements
        started = time.perf_counter()
        results = [
            engine.answer(question, k=args.k) for _ in range(args.runs) for question in questions
        ]
        elapsed = time.perf_counter() - started
        backend = engine.backend.name

    print("| stage | median ms | p95 ms | mean ms |")
    print("|---|---:|---:|---:|")
    for stage in REPORTED_STAGES:
        samples = [result.timings_ms[stage] for result in results if stage in result.timings_ms]
        if not samples:
            continue
        p50, p95 = np.percentile(samples, [50, 95])
        print(f"| {stage} | {p50:.1f} | {p95:.1f} | {np.mean(samples):.1f} |")

    replies = [result.reply for result in results]
    models = ", ".join(sorted({reply.model for reply in replies}))
    print(
        f"\n{len(results)} answers from backend {backend} ({models}). Average per query: "
        f"{np.mean([reply.input_tokens for reply in replies]):.0f} input tokens, "
        f"{np.mean([reply.output_tokens for reply in replies]):.0f} output tokens, "
        f"${np.mean([reply.cost_usd for reply in replies]):.6f}. "
        f"Sequential throughput: {len(results) / elapsed:.1f} queries/s."
    )


if __name__ == "__main__":
    main()
