"""Request and response bodies of the HTTP API, validated by pydantic."""

from typing import Literal

from pydantic import BaseModel, Field


class SourceIn(BaseModel):
    """One source to index: an id, a title and the body text.

    The id, which later names the source in DELETE /sources/{source_id}, is limited to word
    characters, dots and hyphens.
    """

    id: str = Field(min_length=1, max_length=200, pattern=r"^[\w.-]+$")
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class IndexRequest(BaseModel):
    """Body of POST /sources: the sources to index; sending an id again replaces its passages."""

    sources: list[SourceIn] = Field(min_length=1)


class IndexResponse(BaseModel):
    """Reply from POST /sources: how many sources were indexed and how many passages they made."""

    sources: int
    passages: int


class RetrieveRequest(BaseModel):
    """Body of POST /retrieve: the query, how many matches to return, and how to search.

    mode picks keyword search, semantic search or both fused together; rerank re-scores the top
    candidates with the cross-encoder before the best k are kept.
    """

    query: str = Field(min_length=1)
    k: int = Field(5, ge=1, le=50)
    mode: Literal["hybrid", "keyword", "semantic"] = "hybrid"
    rerank: bool = True


class MatchOut(BaseModel):
    """One retrieved passage, the source it belongs to, and its score.

    The score comes from the last ranking step: the cross-encoder when reranking ran, otherwise
    the fused rank score, BM25 or cosine similarity for the hybrid, keyword and semantic modes.
    """

    passage_id: int
    source_id: str
    title: str
    body: str
    score: float


class RetrieveResponse(BaseModel):
    """Reply from POST /retrieve: the matches, best first, and per-stage timings in milliseconds."""

    matches: list[MatchOut]
    timings_ms: dict[str, float]


class AnswerRequest(BaseModel):
    """Body of POST /answer: the question and how many retrieved passages to answer from."""

    question: str = Field(min_length=1)
    k: int = Field(5, ge=1, le=20)


class CitationItem(BaseModel):
    """One passage the answer cites: ref is the n of its [n] marker, snippet a short preview."""

    ref: int
    passage_id: int
    source_id: str
    title: str
    snippet: str


class TokenUsage(BaseModel):
    """Input and output tokens the language model used; both are 0 for the extractive backend."""

    input_tokens: int
    output_tokens: int


class AnswerResponse(BaseModel):
    """Reply from POST /answer: the answer with [n] markers and the passages they point to.

    model is "extractive" for the local backend and the language model's id otherwise; cost_usd
    is estimated from the token usage.
    """

    answer: str
    citations: list[CitationItem]
    model: str
    usage: TokenUsage
    cost_usd: float
    timings_ms: dict[str, float]
