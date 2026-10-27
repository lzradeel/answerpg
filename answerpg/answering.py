"""Answer backends: turn a question and its ranked matches into a reply that cites them.

ExtractiveBackend quotes passage sentences offline, while AnthropicBackend has a model write the
answer. Both cite a passage as [n], n being its 1-based rank among the matches, and resolve those
markers with the helpers defined here.
"""

import re
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
import numpy as np

from answerpg.corpus import split_into_sentences
from answerpg.encoders import VectorEncoder
from answerpg.retrieval import Match
from answerpg.settings import AppConfig

# Each model's price on Anthropic's own API: (input, output) dollars per million tokens.
USD_PER_MILLION_TOKENS = {
    "claude-fable-5-1": (10.00, 50.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
# Requests for these models opt into server-side fallback: if the model refuses, the API reruns
# the request on a fallback model within the same call. Other models are sent without it.
FALLBACK_ELIGIBLE = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
NOT_FOUND = "Nothing in the indexed sources answers that question."
DECLINED = "The language model refused to answer this question."
# One citation marker such as [3], capturing the number.
CITE_MARK = re.compile(r"\[(\d+)\]")
# Closing punctuation followed by one or more citation markers, as in "word. [1][2]".
CITES_AFTER_PUNCT = re.compile(r"\s*([.!?])\s*((?:\[\d+\]\s*)*\[\d+\])")

# System prompt sent with every Anthropic request.
INSTRUCTIONS = (
    "Reply in two to four sentences, drawing only on the numbered passages you are given. "
    "Put the numbers of the supporting passages, written as [1] or [2][3], right before each "
    f"sentence's final punctuation. If the passages do not cover it, reply exactly: {NOT_FOUND}"
)


@dataclass
class CitedSource:
    """One cited passage: its [ref] number, passage and source ids, title and a body preview."""

    ref: int
    passage_id: int
    source_id: str
    title: str
    snippet: str


@dataclass
class Reply:
    """An answer and its citations, plus what produced it and the tokens and money it used.

    model holds a model id for Anthropic replies and the backend name for extractive ones.
    """

    text: str
    citations: list[CitedSource]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class AnswerBackend(Protocol):
    """What the engine needs from a backend: a name and a compose method."""

    name: str

    def compose(self, question: str, matches: list[Match]) -> Reply:
        """Answer the question from the ranked matches, citing them by 1-based position."""
        ...


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Price a call in USD from its token counts; models missing from the table cost nothing."""
    input_rate, output_rate = USD_PER_MILLION_TOKENS.get(model, (0.0, 0.0))
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def tidy_citations(text: str) -> str:
    """Move citation markers written after a sentence's final punctuation in front of it.

    "Foo. [1] Bar." becomes "Foo [1]. Bar.", so splitting into sentences keeps every marker with
    the sentence it supports.
    """
    return CITES_AFTER_PUNCT.sub(r" \2\1", text)


def remove_citations(text: str) -> str:
    """Delete every [n] marker along with any whitespace before it, then trim both ends."""
    return re.sub(r"\s*\[\d+\]", "", text).strip()


def collect_citations(text: str, matches: list[Match]) -> list[CitedSource]:
    """Resolve the [n] markers in text to the matches they point at, in order of first mention.

    Each number counts once, and numbers outside 1..len(matches) are dropped. Every kept one
    carries its match's passage and source ids, title and a short preview of the body.
    """
    unique_refs = dict.fromkeys(int(digits) for digits in CITE_MARK.findall(text))
    cited: list[CitedSource] = []
    for number in unique_refs:
        if not 1 <= number <= len(matches):
            continue
        found = matches[number - 1]
        cited.append(
            CitedSource(
                ref=number,
                passage_id=found.passage_id,
                source_id=found.source_id,
                title=found.title,
                snippet=_excerpt(found.body),
            )
        )
    return cited


def _excerpt(text: str, max_chars: int = 200) -> str:
    """Shorten text for a citation preview.

    Text longer than max_chars is cut at the last space before the limit (or at the limit itself
    when there is no space) and ends with " ...".
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " ..."


def render_prompt(question: str, matches: list[Match]) -> str:
    """Lay out the user message: the matches as numbered passages, then the question.

    Passages are numbered from 1 in rank order, each a "[n] title" line followed by its body, with
    blank lines between them; these numbers are what collect_citations later resolves.
    """
    numbered = "\n\n".join(
        f"[{position}] {item.title}\n{item.body}" for position, item in enumerate(matches, 1)
    )
    return f"{numbered}\n\nQuestion: {question}"


def _quotable_sentences(matches: list[Match]) -> dict[str, int]:
    """Map each extractive candidate to the 1-based ref of the first top-three match holding it."""
    ref_of: dict[str, int] = {}
    for position, candidate in enumerate(matches[:3], 1):
        for sentence in split_into_sentences(candidate.body):
            if len(sentence.split()) >= 5 and sentence[-1] in ".!?":
                ref_of.setdefault(sentence, position)
    return ref_of


class ExtractiveBackend:
    """Offline backend that answers by quoting sentences from the top matches, free of charge.

    Candidates are the sentences in the three best matches that have at least five words and
    close with ".", "!" or "?", so headings and list fragments drop out; a sentence repeated by
    overlapping passages is scored once. The max_sentences candidates with the highest cosine
    similarity to the question are quoted in the order they appear, each with its [ref] placed
    just before the closing punctuation.
    """

    name = "extractive"

    def __init__(self, encoder: VectorEncoder, max_sentences: int = 2):
        """Compare sentences with the question through encoder; quote at most max_sentences."""
        self.encoder = encoder
        self.max_sentences = max_sentences

    def compose(self, question: str, matches: list[Match]) -> Reply:
        """Quote and cite the closest candidates, or reply NOT_FOUND when there are none."""
        ref_of = _quotable_sentences(matches)
        if not ref_of:
            return Reply(NOT_FOUND, [], self.name)
        candidates = list(ref_of)
        scores = self.encoder.encode_passages(candidates) @ self.encoder.encode_query(question)
        # The stable sort lets equal scores keep reading order, so the pick is reproducible.
        picked = sorted(np.argsort(-scores, kind="stable")[: self.max_sentences])
        quoted = [candidates[index] for index in picked]
        answer = " ".join(
            f"{sentence[:-1]} [{ref_of[sentence]}]{sentence[-1]}" for sentence in quoted
        )
        return Reply(answer, collect_citations(answer, matches), self.name)


class AnthropicBackend:
    """Backend that has an Anthropic model write the answer from the numbered passages.

    Requests for FALLBACK_ELIGIBLE models opt into server-side fallback. A refusal becomes the
    DECLINED text; otherwise only text blocks make up the answer, so thinking blocks are skipped.
    Cost is priced by the model that served the reply when the table lists it (a fallback can
    answer in place of the configured model), and by the configured model otherwise.
    """

    name = "anthropic"

    def __init__(
        self,
        model: str,
        max_tokens: int,
        effort: str,
        client: anthropic.Anthropic | None = None,
    ):
        """Store the request settings; with no client, use a default one that finds credentials."""
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self.client = client or anthropic.Anthropic()

    def compose(self, question: str, matches: list[Match]) -> Reply:
        """Ask the model for a cited answer; with no matches, reply NOT_FOUND without a call."""
        if not matches:
            return Reply(NOT_FOUND, [], self.model)
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": INSTRUCTIONS,
            "messages": [{"role": "user", "content": render_prompt(question, matches)}],
            "output_config": {"effort": self.effort},
        }
        if self.model in FALLBACK_ELIGIBLE:
            request["betas"] = ["server-side-fallback-2026-07-01"]
            request["fallbacks"] = "default"
        message = self.client.beta.messages.create(**request)
        if message.stop_reason == "refusal":
            answer = DECLINED
        else:
            answer = "".join(part.text for part in message.content if part.type == "text")
        tokens = message.usage
        pricing_model = message.model if message.model in USD_PER_MILLION_TOKENS else self.model
        return Reply(
            text=answer.strip(),
            citations=collect_citations(answer, matches),
            model=message.model,
            input_tokens=tokens.input_tokens,
            output_tokens=tokens.output_tokens,
            cost_usd=estimate_cost(pricing_model, tokens.input_tokens, tokens.output_tokens),
        )


def make_backend(config: AppConfig, encoder: VectorEncoder) -> AnswerBackend:
    """Build the backend config.answer_backend names: "anthropic", or else the extractive one.

    The Anthropic client gets config.anthropic_api_key; when that is empty, the SDK looks for
    credentials on its own.
    """
    if config.answer_backend != "anthropic":
        return ExtractiveBackend(encoder)
    sdk_client = anthropic.Anthropic(api_key=config.anthropic_api_key or None)
    return AnthropicBackend(
        model=config.answer_model,
        max_tokens=config.answer_max_tokens,
        effort=config.answer_effort,
        client=sdk_client,
    )
