"""FastAPI app exposing the answer engine over HTTP.

A single AnswerEngine is built at startup and shared by all requests. When config.api_token is
set, every POST and DELETE route needs a matching X-API-Token header; /healthz and /usage never
ask for one. /retrieve and /answer write one request_log row per call, and /usage aggregates
those rows.
"""

import secrets
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Annotated

import anthropic
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request

from answerpg.corpus import Source
from answerpg.engine import AnswerEngine
from answerpg.payloads import (
    AnswerRequest,
    AnswerResponse,
    IndexRequest,
    IndexResponse,
    RetrieveRequest,
    RetrieveResponse,
    TokenUsage,
)
from answerpg.store import record_request, usage_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the engine when the app starts, keep it on app.state and close it on shutdown."""
    app.state.engine = AnswerEngine.from_config()
    yield
    app.state.engine.close()


app = FastAPI(title="answerpg", version="0.1.0", lifespan=lifespan)


def current_engine(request: Request) -> AnswerEngine:
    """Return the shared engine that lifespan stored on the application state."""
    return request.app.state.engine


# A handler parameter typed as Engine receives the shared engine through current_engine.
Engine = Annotated[AnswerEngine, Depends(current_engine)]


def check_token(engine: Engine, x_api_token: Annotated[str | None, Header()] = None) -> None:
    """Raise 401 unless the X-API-Token header equals config.api_token.

    Nothing is enforced while api_token is unset. The comparison runs in constant time, so
    response timing does not reveal how much of a guessed token was right.
    """
    configured = engine.config.api_token
    if not configured:
        return
    presented = x_api_token or ""
    if not secrets.compare_digest(presented.encode(), configured.encode()):
        raise HTTPException(status_code=401, detail="A valid X-API-Token header is required")


# Attached to every POST and DELETE route.
guarded = [Depends(check_token)]


@app.get("/healthz")
def healthcheck(engine: Engine) -> dict:
    """Report status "ok", the stored passage count and the active backend's name.

    Needs no token, writes nothing to request_log and raises no HTTP errors of its own.
    """
    with engine.pool.connection() as conn:
        passage_count = conn.execute("SELECT count(*) FROM passages").fetchone()[0]
    return {"status": "ok", "passages": passage_count, "backend": engine.backend.name}


@app.post("/sources", dependencies=guarded)
def index_sources(body: IndexRequest, engine: Engine) -> IndexResponse:
    """Index the posted sources and return how many sources and passages were stored.

    Earlier passages of the same source ids are replaced. Not written to request_log; 401 on a
    bad token and 422 when the body fails validation.
    """
    batch = [Source(entry.id, entry.title, entry.body) for entry in body.sources]
    return IndexResponse(sources=len(batch), passages=engine.index(batch))


@app.delete("/sources/{source_id}", dependencies=guarded)
def remove_source(source_id: str, engine: Engine) -> dict[str, int]:
    """Delete one source's passages and report how many there were as removed_passages.

    404 when the source has nothing stored, 401 on a bad token. Not written to request_log.
    """
    dropped = engine.remove(source_id)
    if not dropped:
        raise HTTPException(status_code=404, detail=f"Source {source_id!r} has no stored passages")
    return {"removed_passages": dropped}


@app.post("/retrieve", dependencies=guarded)
def retrieve(body: RetrieveRequest, engine: Engine) -> RetrieveResponse:
    """Return the ranked matches for a query and the time each stage took, without an answer.

    Logs route "retrieve", the query and the timings to request_log, with no model and zero
    tokens and cost. 401 on a bad token, 422 when the body fails validation.
    """
    outcome = engine.retrieve(body.query, k=body.k, mode=body.mode, rerank=body.rerank)
    record_request(
        engine.pool, route="retrieve", query=body.query, model=None, timings=outcome.timings_ms
    )
    return RetrieveResponse(
        matches=[asdict(item) for item in outcome.matches], timings_ms=outcome.timings_ms
    )


@app.post("/answer", dependencies=guarded)
def answer(body: AnswerRequest, engine: Engine) -> AnswerResponse:
    """Answer a question from the top k passages (hybrid search, reranked) with citations.

    The response carries the text, its citations, the model, token usage, cost and per-stage
    timings. Logs route "answer" with the question, model, timings, tokens and cost to
    request_log. 502 when the Anthropic API call fails (nothing is logged then), 401 on a bad
    token, 422 when the body fails validation.
    """
    try:
        outcome = engine.answer(body.question, k=body.k)
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic API request failed: {exc}") from exc
    composed = outcome.reply
    record_request(
        engine.pool,
        route="answer",
        query=body.question,
        model=composed.model,
        timings=outcome.timings_ms,
        input_tokens=composed.input_tokens,
        output_tokens=composed.output_tokens,
        cost_usd=composed.cost_usd,
    )
    return AnswerResponse(
        answer=composed.text,
        citations=[asdict(cited) for cited in composed.citations],
        model=composed.model,
        usage=TokenUsage(input_tokens=composed.input_tokens, output_tokens=composed.output_tokens),
        cost_usd=composed.cost_usd,
        timings_ms=outcome.timings_ms,
    )


@app.get("/usage")
def usage(engine: Engine, hours: Annotated[int, Query(ge=1, le=720)] = 24) -> dict:
    """Summarize request_log for the past `hours` hours: requests, latency, stage times, cost.

    Needs no token and is not logged itself; 422 when hours falls outside 1 to 720.
    """
    return usage_report(engine.pool, hours)
