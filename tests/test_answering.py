"""Tests for answerpg.answering: citation helpers, prompt layout, both backends and make_backend."""

from types import SimpleNamespace

import pytest

from answerpg.answering import (
    DECLINED,
    INSTRUCTIONS,
    NOT_FOUND,
    AnthropicBackend,
    ExtractiveBackend,
    collect_citations,
    estimate_cost,
    make_backend,
    remove_citations,
    render_prompt,
    tidy_citations,
)
from answerpg.retrieval import Match
from answerpg.settings import AppConfig

# Three ranked matches from a public library's help pages, one sentence each.
LIBRARY = [
    Match(101, "loans", "Borrowing", "Members may borrow up to eight books at a time.", 0.92),
    Match(102, "hours", "Hours", "The reading room opens at nine every weekday morning.", 0.85),
    Match(103, "fines", "Fines", "Overdue books accrue a fine of twenty cents per day.", 0.71),
]
# Token usage that every stubbed Anthropic reply reports.
INPUT_TOKENS, OUTPUT_TOKENS = 2500, 400
# Forty eight-character words: long enough that a citation snippet has to cut it short.
FOLIOS = " ".join(f"folio{number:03d}" for number in range(40))


def similarities(encoder, question: str, texts: list[str]) -> list[float]:
    """Score each text against the question the same way ExtractiveBackend scores candidates."""
    scores = encoder.encode_passages(texts) @ encoder.encode_query(question)
    return [float(score) for score in scores]


def stub_backend(
    *texts: str,
    model: str = "claude-opus-5-5",
    served_model: str | None = None,
    stop_reason: str = "end_turn",
) -> tuple[AnthropicBackend, list[dict]]:
    """Build an AnthropicBackend on a fake client; return it with the list of requests it sends.

    The canned reply holds a thinking block followed by one text block per entry in texts.
    """
    sent: list[dict] = []
    blocks = [SimpleNamespace(type="thinking", thinking="Passage 1 covers borrowing.")]
    blocks += [SimpleNamespace(type="text", text=text) for text in texts]
    canned = SimpleNamespace(
        model=served_model or model,
        stop_reason=stop_reason,
        content=blocks,
        usage=SimpleNamespace(input_tokens=INPUT_TOKENS, output_tokens=OUTPUT_TOKENS),
    )

    def create(**request):
        """Log the request and hand back the canned reply."""
        sent.append(request)
        return canned

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return AnthropicBackend(model=model, max_tokens=1024, effort="low", client=client), sent


@pytest.mark.parametrize(
    ("raw", "tidied"),
    [
        ("Open at nine. [2] Closed on Sundays.", "Open at nine [2]. Closed on Sundays."),
        ("Open at nine.[1][2] Closed on Sundays", "Open at nine [1][2]. Closed on Sundays"),
        ("Bring your card! [1] [3]", "Bring your card [1] [3]!"),
        ("Is the archive open late? [3]", "Is the archive open late [3]?"),
        ("Open at nine [1]. Closed on Sundays [2].", "Open at nine [1]. Closed on Sundays [2]."),
    ],
    ids=["after-period", "glued-group", "spaced-group", "question", "already-tidy"],
)
def test_tidy_citations_pulls_markers_before_the_final_punctuation(raw, tidied):
    """Markers after a sentence's final punctuation move in front of it; tidy text is kept."""
    assert tidy_citations(raw) == tidied


@pytest.mark.parametrize(
    ("cited", "plain"),
    [
        ("Open at nine [1][3]. Closed on Sundays [2].", "Open at nine. Closed on Sundays."),
        ("[1] Fines stay small [2] [3]!", "Fines stay small!"),
    ],
)
def test_remove_citations_drops_each_marker_with_the_space_before_it(cited, plain):
    """Every [n] disappears together with the whitespace in front of it."""
    assert remove_citations(cited) == plain


def test_collect_citations_resolves_valid_refs_once_in_first_seen_order():
    """Each valid ref resolves once, in first-seen order; 0 and refs past the end are dropped."""
    text = "Ask at the desk [4]. Fines add up [3]. Borrow up to eight [1][3]. Open daily [0]."
    cited = collect_citations(text, LIBRARY)
    assert [(c.ref, c.passage_id, c.source_id) for c in cited] == [
        (3, 103, "fines"),
        (1, 101, "loans"),
    ]
    assert (cited[0].title, cited[0].snippet) == ("Fines", LIBRARY[2].body)


@pytest.mark.parametrize(
    ("body", "snippet"),
    [
        ("x" * 200, "x" * 200),
        ("x" * 201, "x" * 200 + " ..."),
        # Each word takes nine characters with its space, so the limit falls inside folio022.
        (FOLIOS, " ".join(f"folio{number:03d}" for number in range(22)) + " ..."),
    ],
    ids=["exactly-200", "no-space", "cut-at-last-space"],
)
def test_citation_snippet_cuts_long_bodies_at_the_last_space(body, snippet):
    """Bodies over 200 characters end at their last space before the limit, plus " ..."."""
    cited = collect_citations("See the archive [1].", [Match(77, "archive", "Archive", body, 0.5)])
    assert cited[0].snippet == snippet


def test_render_prompt_lists_numbered_passages_then_the_question():
    """Matches become "[n] title" over their body, blank-line separated, with the question last."""
    assert render_prompt("When can I study?", LIBRARY[:2]) == (
        "[1] Borrowing\nMembers may borrow up to eight books at a time.\n\n"
        "[2] Hours\nThe reading room opens at nine every weekday morning.\n\n"
        "Question: When can I study?"
    )


def test_extractive_backend_quotes_the_single_closest_sentence(encoder):
    """With max_sentences=1 the nearest sentence is quoted, its [ref] before the final period."""
    backend = ExtractiveBackend(encoder, max_sentences=1)
    reply = backend.compose("How much is the fine for overdue books?", LIBRARY)
    assert reply.text == "Overdue books accrue a fine of twenty cents per day [3]."
    assert [(c.ref, c.source_id) for c in reply.citations] == [(3, "fines")]
    assert (reply.model, reply.cost_usd) == ("extractive", 0.0)


def test_extractive_backend_orders_quotes_by_rank_not_by_score(encoder):
    """Two quotes follow match rank even when the lower-ranked match scores higher."""
    question = "How many books may members borrow, and what fine do overdue books accrue?"
    loans, hours, fines = similarities(encoder, question, [item.body for item in LIBRARY])
    assert fines > loans > hours
    reply = ExtractiveBackend(encoder).compose(question, LIBRARY)
    assert reply.text == (
        "Members may borrow up to eight books at a time [1]. "
        "Overdue books accrue a fine of twenty cents per day [3]."
    )


def test_extractive_backend_skips_headings_fragments_and_repeats(encoder):
    """Lines without closing punctuation or under five words are skipped; repeats count once."""
    shared = "A loan can be renewed twice unless someone has reserved the book."
    # The heading has five words but no closing punctuation, the fragment only four words, and
    # the last sentence exactly five.
    first = f"How to renew a loan\n{shared}"
    second = f"{shared}\nRenewals are always free.\nEach renewal adds three weeks."
    overlapping = [
        Match(451, "renewals", "Renewals", first, 0.9),
        Match(452, "renewals", "Renewals", second, 0.8),
    ]
    # Allowing more quotes than there are candidates quotes them all, whatever their scores.
    backend = ExtractiveBackend(encoder, max_sentences=5)
    reply = backend.compose("How often can a loan be renewed?", overlapping)
    assert reply.text == (
        "A loan can be renewed twice unless someone has reserved the book [1]. "
        "Each renewal adds three weeks [2]."
    )
    assert [(c.ref, c.passage_id) for c in reply.citations] == [(1, 451), (2, 452)]


def test_extractive_backend_reads_only_the_top_three_matches(encoder):
    """A fourth match is never quoted, even when it holds the closest sentence."""
    wifi = Match(104, "wifi", "Wifi", "Visitors can join the guest wifi with a library card.", 0.4)
    ranked = [*LIBRARY, wifi]
    question = "When does the reading room open, and can visitors join the guest wifi?"
    *top_three, fourth = similarities(encoder, question, [item.body for item in ranked])
    assert fourth > max(top_three)
    reply = ExtractiveBackend(encoder, max_sentences=1).compose(question, ranked)
    assert reply.text == "The reading room opens at nine every weekday morning [2]."


@pytest.mark.parametrize(
    "matches",
    [[], [Match(601, "hours", "Hours", "Holiday hours\nClosed on Sundays.", 0.6)]],
    ids=["no-matches", "nothing-quotable"],
)
def test_extractive_backend_answers_not_found_without_quotable_sentences(encoder, matches):
    """No matches, or matches holding only headings and fragments, give NOT_FOUND."""
    reply = ExtractiveBackend(encoder).compose("When is the library open?", matches)
    assert (reply.text, reply.citations, reply.model) == (NOT_FOUND, [], "extractive")


def test_anthropic_reply_joins_text_blocks_and_prices_usage():
    """The thinking block is skipped; text blocks are joined, trimmed, cited and billed."""
    backend, _ = stub_backend(
        "Members can borrow eight books at once [1].",
        " Overdue books cost twenty cents a day [3].\n",
    )
    reply = backend.compose("What are the borrowing rules?", LIBRARY)
    assert reply.text == (
        "Members can borrow eight books at once [1]. Overdue books cost twenty cents a day [3]."
    )
    assert [(c.ref, c.source_id) for c in reply.citations] == [(1, "loans"), (3, "fines")]
    assert (reply.model, reply.input_tokens, reply.output_tokens) == ("claude-opus-5-5", 2500, 400)
    assert reply.cost_usd == pytest.approx((2500 * 4.00 + 400 * 20.00) / 1_000_000)
    assert reply.cost_usd == pytest.approx(estimate_cost("claude-opus-5-5", 2500, 400))


def test_anthropic_request_sends_instructions_prompt_and_effort():
    """The request carries INSTRUCTIONS, the numbered passages and low effort, no sampling knobs."""
    backend, sent = stub_backend("Members can borrow eight books at once [1].")
    backend.compose("How many books can I borrow?", LIBRARY)
    (request,) = sent
    assert (request["model"], request["max_tokens"]) == ("claude-opus-5-5", 1024)
    assert request["system"] == INSTRUCTIONS
    assert request["messages"][0]["content"].startswith(
        "[1] Borrowing\nMembers may borrow up to eight books at a time."
    )
    prompt = render_prompt("How many books can I borrow?", LIBRARY)
    assert request["messages"] == [{"role": "user", "content": prompt}]
    assert request["output_config"] == {"effort": "low"}
    assert not {"temperature", "top_p", "top_k", "thinking"} & request.keys()


@pytest.mark.parametrize("model", ["claude-opus-5-5", "claude-sonnet-5-5"])
def test_eligible_models_opt_into_server_side_fallback(model):
    """Opus and Sonnet requests send the fallback beta flag with fallbacks set to "default"."""
    backend, sent = stub_backend("Members can borrow eight books at once [1].", model=model)
    backend.compose("How many books can I borrow?", LIBRARY)
    assert sent[0]["betas"] == ["server-side-fallback-2026-07-01"]
    assert sent[0]["fallbacks"] == "default"


def test_haiku_requests_carry_no_fallback_parameters():
    """A model outside FALLBACK_ELIGIBLE sends neither betas nor fallbacks."""
    backend, sent = stub_backend("Fines add up [3].", model="claude-haiku-5-5")
    reply = backend.compose("What does a late book cost?", LIBRARY)
    assert "betas" not in sent[0] and "fallbacks" not in sent[0]
    assert reply.cost_usd == pytest.approx(estimate_cost("claude-haiku-5-5", 2500, 400))


@pytest.mark.parametrize(
    ("served_model", "priced_as"),
    [
        ("claude-sonnet-5-5", "claude-sonnet-5-5"),
        ("claude-opus-5-5-experimental", "claude-opus-5-5"),
    ],
    ids=["listed", "unlisted"],
)
def test_reply_names_the_serving_model_and_prices_unlisted_ones_as_configured(
    served_model, priced_as
):
    """The serving model is reported; one missing from the price table is billed as configured."""
    backend, _ = stub_backend("Fines add up [3].", served_model=served_model)
    reply = backend.compose("What does a late book cost?", LIBRARY)
    assert reply.model == served_model
    assert reply.cost_usd == pytest.approx(estimate_cost(priced_as, 2500, 400))


def test_refusal_turns_into_the_declined_message():
    """stop_reason "refusal" replaces whatever text came back with DECLINED and no citations."""
    backend, _ = stub_backend("Members can borrow [1]", stop_reason="refusal")
    reply = backend.compose("How many books can I borrow?", LIBRARY)
    assert (reply.text, reply.citations) == (DECLINED, [])


def test_anthropic_backend_sends_nothing_without_matches():
    """With nothing retrieved the backend replies NOT_FOUND and makes no request."""
    backend, sent = stub_backend("Members can borrow eight books at once [1].")
    reply = backend.compose("How many books can I borrow?", [])
    assert (reply.text, reply.citations, sent) == (NOT_FOUND, [], [])


@pytest.mark.parametrize(
    ("model", "usd"),
    [("claude-opus-5-5", 0.018), ("claude-sonnet-5-5", 0.009), ("claude-haiku-5-5", 0.00045)],
)
def test_estimate_cost_applies_per_million_token_rates(model, usd):
    """2,500 input and 400 output tokens cost what the model's per-million rates say."""
    assert estimate_cost(model, input_tokens=2500, output_tokens=400) == pytest.approx(usd)


@pytest.mark.parametrize(
    ("model", "input_usd", "output_usd"),
    [("claude-fable-5-1", 10.00, 50.00), ("claude-opus-5", 5.00, 25.00)],
)
def test_estimate_cost_prices_fable_and_opus_5_per_million_tokens(model, input_usd, output_usd):
    """A million input tokens and a million output tokens each cost the model's listed rate."""
    per_million = (
        estimate_cost(model, input_tokens=1_000_000, output_tokens=0),
        estimate_cost(model, input_tokens=0, output_tokens=1_000_000),
    )
    assert per_million == pytest.approx((input_usd, output_usd))


def test_estimate_cost_is_zero_for_unlisted_models():
    """A model missing from the price table costs nothing."""
    assert estimate_cost("in-house-model", input_tokens=2500, output_tokens=400) == 0.0


def test_make_backend_defaults_to_the_extractive_backend(encoder, monkeypatch):
    """With answer_backend at its default, make_backend quotes passages through the encoder."""
    monkeypatch.delenv("ANSWER_BACKEND", raising=False)
    backend = make_backend(AppConfig(_env_file=None), encoder)
    assert isinstance(backend, ExtractiveBackend)
    assert backend.encoder is encoder
    assert backend.max_sentences == 2


def test_make_backend_builds_the_anthropic_backend_from_config(encoder):
    """answer_backend="anthropic" yields a backend with the configured model, budget and key."""
    config = AppConfig(
        _env_file=None,
        answer_backend="anthropic",
        anthropic_api_key="test-key",
        answer_model="claude-sonnet-5-5",
        answer_max_tokens=640,
        answer_effort="medium",
    )
    backend = make_backend(config, encoder)  # building the SDK client opens no connection
    assert isinstance(backend, AnthropicBackend)
    assert (backend.model, backend.max_tokens) == ("claude-sonnet-5-5", 640)
    assert backend.effort == "medium"
    assert backend.client.api_key == "test-key"
