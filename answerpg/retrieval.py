"""Keyword (BM25) and semantic (pgvector) passage search, and rank fusion of the results."""

from dataclasses import dataclass, replace

import numpy as np
import psycopg

# Okapi BM25 in a single statement. Each distinct query lexeme found in a passage adds
#   idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * word_count / avgdl))
# where idf = ln(1 + (N - df + 0.5) / (df + 0.5)) is Lucene's variant, which stays positive
# even for terms found in most passages. plainto_tsquery joins the lexemes with AND; rewriting
# it to OR lets the GIN index fetch every passage that holds any of them, so `postings` covers
# all of those passages and each df is the term's true corpus count rather than a count over
# passages that matched the whole query. Two passages can easily score the same, so source_id
# and ordinal settle ties and keep the order reproducible from run to run.
BM25_QUERY = """
WITH query_lexemes AS (
    SELECT DISTINCT lexeme FROM unnest(to_tsvector('english', %(query)s))
),
corpus_stats AS (
    SELECT count(*)::float8 AS n, avg(word_count)::float8 AS avgdl FROM passages
),
postings AS (
    SELECT p.id, p.word_count, t.lexeme, cardinality(t.positions) AS tf
    FROM passages p
    CROSS JOIN LATERAL unnest(p.lexemes) AS t
    JOIN query_lexemes q ON q.lexeme = t.lexeme
    WHERE p.lexemes @@ replace(plainto_tsquery('english', %(query)s)::text, ' & ', ' | ')::tsquery
),
term_df AS (
    SELECT lexeme, count(*)::float8 AS df FROM postings GROUP BY lexeme
),
bm25 AS (
    SELECT po.id,
           sum(ln(1 + (cs.n - d.df + 0.5) / (d.df + 0.5))
               * po.tf * (%(k1)s + 1)
               / (po.tf + %(k1)s * (1 - %(b)s + %(b)s * po.word_count / cs.avgdl))) AS score
    FROM postings po
    JOIN term_df d USING (lexeme)
    CROSS JOIN corpus_stats cs
    GROUP BY po.id
)
SELECT p.id, p.source_id, p.title, p.body, b.score
FROM bm25 b JOIN passages p ON p.id = b.id
ORDER BY b.score DESC, p.source_id, p.ordinal
LIMIT %(limit)s
"""

# Nearest passages through the HNSW index. pgvector's <=> is cosine distance, which is
# 1 - cosine similarity, so 1 minus it reports the similarity itself (higher is closer). The
# ORDER BY keeps the bare distance expression because that is the form the index can serve.
ANN_QUERY = """
SELECT id, source_id, title, body, 1 - (embedding <=> %(embedding)s) AS score
FROM passages
ORDER BY embedding <=> %(embedding)s
LIMIT %(limit)s
"""


@dataclass
class Match:
    """A retrieved passage, scored by whichever stage ranked it last."""

    passage_id: int
    source_id: str
    title: str
    body: str
    score: float


def _rows_to_matches(rows: list[tuple]) -> list[Match]:
    """Build Match objects from (id, source_id, title, body, score) rows."""
    return [
        Match(passage_id, source_id, title, body, float(score))
        for passage_id, source_id, title, body, score in rows
    ]


def keyword_search(
    conn: psycopg.Connection, query: str, limit: int, k1: float = 1.2, b: float = 0.75
) -> list[Match]:
    """Return the top `limit` passages for `query` by BM25 score.

    k1 sets how quickly repeats of a term stop adding score; b sets how strongly long passages
    are discounted.
    """
    bindings = {"query": query, "limit": limit, "k1": k1, "b": b}
    return _rows_to_matches(conn.execute(BM25_QUERY, bindings).fetchall())


def semantic_search(conn: psycopg.Connection, embedding: np.ndarray, limit: int) -> list[Match]:
    """Return the `limit` passages nearest to `embedding`, scored by cosine similarity."""
    bindings = {"embedding": embedding, "limit": limit}
    return _rows_to_matches(conn.execute(ANN_QUERY, bindings).fetchall())


def fuse_rankings(rankings: list[list[Match]], k: int = 60) -> list[Match]:
    """Combine several rankings with reciprocal rank fusion.

    A passage at 1-based rank r in a ranking gains 1 / (k + r), summed over every ranking it
    appears in. Each passage comes back once, as a copy of the first Match seen for it carrying
    the fused score, best first; equal scores keep first-seen order.
    """
    fused: dict[int, float] = {}
    first_seen: dict[int, Match] = {}
    for ranking in rankings:
        for rank, entry in enumerate(ranking, start=1):
            passage_id = entry.passage_id
            fused[passage_id] = fused.get(passage_id, 0.0) + 1 / (k + rank)
            first_seen.setdefault(passage_id, entry)
    # sorted() stays stable with reverse=True and dicts iterate in insertion order, so ties
    # come out in the order their passages were first seen.
    best_first = sorted(fused.items(), key=lambda pair: pair[1], reverse=True)
    return [replace(first_seen[passage_id], score=score) for passage_id, score in best_first]
