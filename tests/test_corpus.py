"""Tests for sentence splitting, passage packing and loading Markdown sources from a folder."""

from itertools import pairwise

import pytest

from answerpg.corpus import read_markdown_dir, split_into_sentences, split_passages

# One long line of thirty-two five-word sentences from an invented trail log.
TRAIL_LOG = " ".join(f"Cairn {n} marks the path." for n in range(1, 33))


@pytest.fixture
def notes_dir(tmp_path):
    """A folder of hiking notes created out of name order, plus a text file and a subfolder."""
    (tmp_path / "weather.md").write_text(
        "# Mountain weather\n\nStorms often build after midday in July.\n\n"
        "# Lightning\nCome off exposed ridges at the first thunder.\n",
        encoding="utf-8",
    )
    (tmp_path / "huts.md").write_text(
        "## Booking\nMost huts take bookings from April.\n", encoding="utf-8"
    )
    (tmp_path / "gear.txt").write_text("Rope, helmet and harness.\n", encoding="utf-8")
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "routes.md").write_text(
        "# Old routes\n\nThe east gully closed in 2019.\n", encoding="utf-8"
    )
    return tmp_path


def test_line_markers_are_stripped():
    """Heading, bullet, quote, stacked and numbered markers never reach the sentences."""
    text = (
        "# Trail notes\n"
        "## Packing list\n"
        "- Pack spare batteries! Bring a head torch.\n"
        "* Is the ridge path open? Ask the warden.\n"
        "> Snow lingers on the north face.\n"
        "> - Rescue huts carry a radio.\n"
        "1. Check the forecast.\n"
        "2) Leave your route with someone\n"
    )
    assert split_into_sentences(text) == [
        "Trail notes",
        "Packing list",
        "Pack spare batteries!",
        "Bring a head torch.",
        "Is the ridge path open?",
        "Ask the warden.",
        "Snow lingers on the north face.",
        "Rescue huts carry a radio.",
        "Check the forecast.",
        "Leave your route with someone",
    ]


def test_lines_without_word_characters_are_skipped():
    """Blank lines and rules such as --- or * * * yield no sentences."""
    text = "Camp below the tree line.\n\n---\n* * *\n   \nPitch tents before dusk."
    assert split_into_sentences(text) == ["Camp below the tree line.", "Pitch tents before dusk."]


def test_surrounding_whitespace_is_trimmed():
    """Indentation and trailing spaces leave no padded or empty sentences behind."""
    text = "   Fill your bottles.   \n\tStart before sunrise.  "
    assert split_into_sentences(text) == ["Fill your bottles.", "Start before sunrise."]


def test_inline_markdown_is_left_alone():
    """Bold, italic and code spans inside a sentence are kept exactly as written."""
    text = "**Waterproof** boots are a must. Pack *two* spare `socks`."
    assert split_into_sentences(text) == [
        "**Waterproof** boots are a must.",
        "Pack *two* spare `socks`.",
    ]


@pytest.mark.parametrize("abbreviation", ["e.g.", "i.e."])
def test_latin_abbreviations_do_not_end_a_sentence(abbreviation):
    """No break follows e.g. or i.e., while the full stop after them still splits."""
    text = f"Pack light snacks, {abbreviation} dried fruit, for the climb. Then set off."
    assert split_into_sentences(text) == [
        f"Pack light snacks, {abbreviation} dried fruit, for the climb.",
        "Then set off.",
    ]


def test_passages_respect_the_word_limit_and_keep_every_sentence():
    """Without overlap, packing stays under the limit and drops or repeats nothing."""
    passages = split_passages(TRAIL_LOG, word_limit=17, overlap=0)
    assert len(passages) == 11
    assert all(len(passage.split()) <= 17 for passage in passages)
    repacked = [sentence for passage in passages for sentence in split_into_sentences(passage)]
    assert repacked == split_into_sentences(TRAIL_LOG)


def test_headings_remain_their_own_sentences_inside_passages():
    """Unpunctuated headings and list items never fuse with their neighbours in any passage."""
    text = (
        "# Hut opening times\n"
        "- Wardens arrive in May\n"
        "- The winter room never closes\n"
        "## Bookings\n"
        "- Groups book a month ahead"
    )
    passages = split_passages(text, word_limit=12, overlap=0)
    assert [split_into_sentences(passage) for passage in passages] == [
        ["Hut opening times", "Wardens arrive in May", "The winter room never closes"],
        ["Bookings", "Groups book a month ahead"],
    ]


def test_overlap_carries_the_last_sentence_into_the_next_passage():
    """With overlap=1 each passage opens with the sentence that closed the one before it."""
    passages = split_passages(TRAIL_LOG, word_limit=17, overlap=1)
    assert len(passages) > 1
    assert all(len(passage.split()) <= 17 for passage in passages)
    rebuilt = split_into_sentences(passages[0])
    for previous, current in pairwise(passages):
        assert split_into_sentences(current)[0] == split_into_sentences(previous)[-1]
        rebuilt += split_into_sentences(current)[1:]
    assert rebuilt == split_into_sentences(TRAIL_LOG)


def test_sentence_longer_than_the_limit_gets_its_own_passage():
    """An oversized sentence is neither cut nor merged with its neighbours."""
    oversized = (
        "The path winds past " + ", ".join(f"cairn {n}" for n in range(1, 21)) + " to the col."
    )
    assert len(oversized.split()) > 25
    passages = split_passages(
        f"The climb starts gently. {oversized} The summit is flat.", word_limit=25
    )
    assert passages == ["The climb starts gently.", oversized, "The summit is flat."]


@pytest.mark.parametrize(
    "text",
    ["", "   ", "\n\t\n", "> \n## \n* * *\n- \n3. \n"],
    ids=["empty", "spaces", "blank-lines", "markers-only"],
)
def test_text_without_words_yields_no_passages(text):
    """Empty, whitespace-only and marker-only input produce an empty list."""
    assert split_passages(text) == []


def test_tiny_word_limit_never_yields_empty_passages():
    """A limit below every sentence's length gives one non-empty passage per sentence."""
    passages = split_passages(TRAIL_LOG, word_limit=3)
    assert passages == split_into_sentences(TRAIL_LOG)
    assert all(passage.strip() for passage in passages)


def test_only_markdown_files_directly_in_the_folder_load_in_name_order(notes_dir):
    """The .txt file and the subfolder's file are skipped, and the rest sort by file name."""
    assert [source.id for source in read_markdown_dir(notes_dir)] == ["huts", "weather"]


def test_first_top_level_heading_becomes_the_title(notes_dir):
    """The first "# " line is lifted out as the title, while a later one stays in the body."""
    weather = {source.id: source for source in read_markdown_dir(notes_dir)}["weather"]
    assert weather.title == "Mountain weather"
    assert weather.body == (
        "Storms often build after midday in July.\n\n"
        "# Lightning\nCome off exposed ridges at the first thunder."
    )


def test_file_stem_is_the_title_without_a_top_level_heading(notes_dir):
    """A file with no "# " line is titled by its stem and keeps its "## " heading in the body."""
    huts = {source.id: source for source in read_markdown_dir(notes_dir)}["huts"]
    assert huts.title == "huts"
    assert huts.body == "## Booking\nMost huts take bookings from April."
