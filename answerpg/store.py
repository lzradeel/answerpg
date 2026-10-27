"""Postgres schema, connection pool and request log behind answerpg."""

from decimal import Decimal

import psycopg
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

# Idempotent schema setup, run at startup with {dim} set to the embedding size: the pgvector
# extension, the passages table (a generated English tsvector over title and body with a GIN
# index for keyword search, plus an HNSW cosine index for semantic search) and the request_log
# table that usage_report aggregates.
DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS passages (
    id BIGSERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    ordinal INT NOT NULL,
    body TEXT NOT NULL,
    word_count INT NOT NULL,
    lexemes TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || body)) STORED,
    embedding VECTOR({dim}) NOT NULL,
    UNIQUE (source_id, ordinal)
);
CREATE INDEX IF NOT EXISTS passages_lexemes_idx ON passages USING gin (lexemes);
CREATE INDEX IF NOT EXISTS passages_hnsw_idx ON passages USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS request_log (
    id BIGSERIAL PRIMARY KEY,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    route TEXT NOT NULL,
    query TEXT NOT NULL,
    model TEXT,
    total_ms REAL NOT NULL,
    timings JSONB NOT NULL,
    input_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS request_log_logged_at_idx ON request_log (logged_at);
"""

# Totals for the last `hours` hours: request count, p50/p95/p99 of total_ms, mean and summed cost.
LATENCY_SUMMARY_SQL = """
SELECT count(*),
       percentile_cont(0.5) WITHIN GROUP (ORDER BY total_ms),
       percentile_cont(0.95) WITHIN GROUP (ORDER BY total_ms),
       percentile_cont(0.99) WITHIN GROUP (ORDER BY total_ms),
       avg(cost_usd),
       sum(cost_usd)
FROM request_log
WHERE logged_at > now() - make_interval(hours => %(hours)s)
"""

# p50 and p95 per pipeline stage over the same window: one row for each key of the timings
# JSON except "total", sorted by stage name.
STAGE_BREAKDOWN_SQL = """
SELECT stage.key,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY stage.value::float8),
       percentile_cont(0.95) WITHIN GROUP (ORDER BY stage.value::float8)
FROM request_log, jsonb_each_text(timings) AS stage
WHERE logged_at > now() - make_interval(hours => %(hours)s) AND stage.key <> 'total'
GROUP BY stage.key
ORDER BY stage.key
"""

# One request_log row per API call; total_ms is copied out of the timings for the percentiles.
_INSERT_REQUEST = """
INSERT INTO request_log
    (route, query, model, total_ms, timings, input_tokens, output_tokens, cost_usd)
VALUES
    (%(route)s, %(query)s, %(model)s, %(total_ms)s, %(timings)s,
     %(input_tokens)s, %(output_tokens)s, %(cost_usd)s)
"""


def _init_connection(conn: psycopg.Connection) -> None:
    """Get a freshly opened pool connection ready for vector queries."""
    register_vector(conn)
    # An HNSW index scan stops after hnsw.ef_search candidates, so at the default of 40
    # semantic_search could return fewer rows than search_depth asks for.
    conn.execute("SET hnsw.ef_search = 100")


def open_pool(database_url: str, dim: int) -> ConnectionPool:
    """Create the schema for `dim`-dimensional embeddings if needed, then open the pool."""
    # The bootstrap uses its own connection, before the pool opens any: the pool's configure
    # hook calls register_vector, which looks the vector type up in the catalog and raises if
    # the extension has not been created yet.
    with psycopg.connect(database_url, autocommit=True) as conn:
        # CREATE ... IF NOT EXISTS is not safe when several workers boot at the same moment,
        # so they queue on an advisory lock. It is session-level and is released when this
        # connection closes.
        conn.execute("SELECT pg_advisory_lock(31415926)")
        conn.execute(DDL.format(dim=dim))
    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": True},
        configure=_init_connection,
        open=True,
    )


def record_request(
    pool: ConnectionPool,
    *,
    route: str,
    query: str,
    model: str | None,
    timings: dict[str, float],
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
) -> None:
    """Log one API call to request_log; `timings` must include the "total" stage."""
    row = {
        "route": route,
        "query": query,
        "model": model,
        "total_ms": timings["total"],
        "timings": Jsonb(timings),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }
    with pool.connection() as conn:
        conn.execute(_INSERT_REQUEST, row)


def _round_or_zero(value: Decimal | float | None, digits: int = 2) -> float:
    """Round an aggregate to `digits` places; NULL, which an empty window yields, becomes 0."""
    return round(float(value or 0), digits)


def usage_report(pool: ConnectionPool, hours: int = 24) -> dict:
    """Summarise request_log over the last `hours` hours for GET /usage.

    The result holds the window, the request count, p50/p95/p99 of total latency, p50/p95 per
    stage (milliseconds, two decimals) and the mean and total cost in USD (six decimals). An
    empty window reports zeros and no stages.
    """
    window = {"hours": hours}
    with pool.connection() as conn:
        total_requests, median_ms, p95_ms, p99_ms, mean_cost, cost_sum = conn.execute(
            LATENCY_SUMMARY_SQL, window
        ).fetchone()
        stage_rows = conn.execute(STAGE_BREAKDOWN_SQL, window).fetchall()
    return {
        "hours": hours,
        "requests": total_requests,
        "latency_ms": {
            "p50": _round_or_zero(median_ms),
            "p95": _round_or_zero(p95_ms),
            "p99": _round_or_zero(p99_ms),
        },
        "stages": {
            stage: {"p50": _round_or_zero(stage_p50), "p95": _round_or_zero(stage_p95)}
            for stage, stage_p50, stage_p95 in stage_rows
        },
        "cost_usd": {"avg": _round_or_zero(mean_cost, 6), "total": _round_or_zero(cost_sum, 6)},
    }
