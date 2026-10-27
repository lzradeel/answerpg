"""Markdown sources and the rules that split their text into sentences and passages."""

import re
from dataclasses import dataclass
from pathlib import Path

# Whitespace after . ! or ?, unless the text before it ends with "e.g." or "i.e.".
SENTENCE_SPLIT = re.compile(r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<=[.!?])\s+")
# Leading bullet, quote, heading and numbering markers followed by whitespace, even stacked.
BULLET_PREFIX = re.compile(r"^(?:\s*(?:[-*>]|#+|\d+[.)])\s+)+")
# A line without a single word character (a "---" rule, say) holds no sentence.
WORD_CHAR = re.compile(r"\w")


@dataclass
class Source:
    """A document to index: its id, a display title and the body text."""

    id: str
    title: str
    body: str


def read_markdown_dir(directory: Path) -> list[Source]:
    """Load every *.md file directly inside directory (subfolders are skipped), sorted by path.

    The file stem becomes the id. The first line starting with "# " becomes the title and is
    removed from the body: the title is stored beside every passage and searched along with it,
    so keeping the heading would repeat it in the first passage. Without such a line, the stem
    doubles as the title.
    """
    sources = []
    for md_file in sorted(Path(directory).glob("*.md")):
        file_lines = md_file.read_text(encoding="utf-8").splitlines()
        heading_at = next((i for i, row in enumerate(file_lines) if row.startswith("# ")), None)
        title = md_file.stem
        if heading_at is not None:
            title = file_lines.pop(heading_at)[2:].strip()
        sources.append(Source(id=md_file.stem, title=title, body="\n".join(file_lines).strip()))
    return sources


def split_into_sentences(text: str) -> list[str]:
    """Break text into sentences, looking at one line at a time.

    Leading markers are stripped however many are stacked, lines left without a word character
    are dropped, and the rest split after . ! or ? (but not after "e.g." or "i.e."). Lines are
    never joined, so a heading or a list item lacking end punctuation is a sentence by itself.
    """
    sentences = []
    for raw_line in text.splitlines():
        cleaned = BULLET_PREFIX.sub("", raw_line).strip()
        if WORD_CHAR.search(cleaned):
            sentences.extend(SENTENCE_SPLIT.split(cleaned))
    return sentences


def split_passages(text: str, word_limit: int = 120, overlap: int = 1) -> list[str]:
    """Pack whole sentences from text into passages of up to word_limit words.

    The last `overlap` sentences of a passage are repeated at the start of the next one, unless
    they would not fit alongside the sentence that follows; a sentence longer than word_limit
    becomes a passage of its own. Sentences are stored one per line, so running
    split_into_sentences on a passage recovers the sentences it was packed from, and a heading or
    a list item with no closing punctuation cannot fuse with the text that follows it.
    """
    finished: list[str] = []
    draft: list[str] = []
    for sentence in split_into_sentences(text):
        sentence_words = len(sentence.split())
        if draft and _total_words(draft) + sentence_words > word_limit:
            finished.append("\n".join(draft))
            draft = draft[-overlap:] if overlap > 0 else []
            if _total_words(draft) + sentence_words > word_limit:
                draft = []
        draft.append(sentence)
    if draft:
        finished.append("\n".join(draft))
    return finished


def _total_words(sentences: list[str]) -> int:
    """Count the whitespace-separated words in all the given sentences."""
    return sum(len(sentence.split()) for sentence in sentences)
