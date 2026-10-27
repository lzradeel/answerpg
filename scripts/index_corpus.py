"""Load every markdown article in a folder and store it as embedded passages."""

import argparse
import sys
from pathlib import Path

from answerpg.corpus import read_markdown_dir
from answerpg.engine import AnswerEngine


def main() -> None:
    """Index the folder's .md files, replacing any passages already stored for those sources."""
    parser = argparse.ArgumentParser(
        description="Split markdown files into passages, embed them and store them in Postgres."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("data/articles"),
        help="folder holding the .md files (default: %(default)s)",
    )
    args = parser.parse_args()

    sources = read_markdown_dir(args.path)
    if not sources:
        sys.exit(f"Nothing to index: no .md files in {args.path}")
    with AnswerEngine.from_config() as engine:
        stored = engine.index(sources)
    print(f"Stored {stored} passages from {len(sources)} sources")


if __name__ == "__main__":
    main()
