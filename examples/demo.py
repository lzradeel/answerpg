"""Index the bundled articles, then answer one question with citations, timings and cost.

Usage: python examples/demo.py [question words...]
"""

import sys
from pathlib import Path

from answerpg.corpus import read_markdown_dir
from answerpg.engine import AnswerEngine

ARTICLES_DIR = Path(__file__).resolve().parent.parent / "data" / "articles"
SAMPLE_QUESTION = "Which regions can an Enterprise workspace keep its data in?"


def main() -> None:
    """Answer the question given on the command line, or SAMPLE_QUESTION when there is none."""
    question = " ".join(sys.argv[1:]) or SAMPLE_QUESTION
    with AnswerEngine.from_config() as engine:
        stored = engine.index(read_markdown_dir(ARTICLES_DIR))
        result = engine.answer(question)

    reply = result.reply
    print(f"{stored} passages indexed\n\nQuestion: {question}\nAnswer: {reply.text}\n")
    for cited in reply.citations:
        print(f"  [{cited.ref}] {cited.title} ({cited.source_id})")
    timings = ", ".join(f"{stage} {ms:.1f} ms" for stage, ms in result.timings_ms.items())
    print(f"\nTimings: {timings}\nAnswered by {reply.model} at a cost of ${reply.cost_usd:.6f}")


if __name__ == "__main__":
    main()
