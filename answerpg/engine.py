"""AnswerEngine: indexes sources into Postgres and answers questions from the stored passages.

Indexing splits each source into passages, embeds them and writes them in one transaction.
Answering runs keyword search, semantic search or both (fusing the two rankings), optionally
re-scores the best candidates with a cross-encoder and passes the survivors to the answer
backend. Every stage is timed so callers can report where the latency went.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Literal

from psycopg_pool import ConnectionPool

from answerpg.answering import AnswerBackend, Reply, make_backend
from answerpg.corpus import Source, split_passages
from answerpg.encoders import RelevanceScorer, VectorEncoder, load_encoders
from answerpg.retrieval import Match, fuse_rankings, keyword_search, semantic_search
from answerpg.settings import AppConfig, load_config
from answerpg.store import open_pool

# "keyword" is BM25 alone, "semantic" is vector search alone, "hybrid" fuses the two.
SearchMode = Literal["hybrid", "keyword", "semantic"]

# Postgres fills in the id and the generated lexemes column itself.
INSERT_PASSAGE = """
INSERT INTO passages (source_id, title, ordinal, body, word_count, embedding)
VALUES (%s, %s, %s, %s, %s, %s)
"""


class Stopwatch:
    """Collects wall-clock milliseconds for the named stages of one request.

    A stage is recorded even if its block raises. Entries are added as blocks finish, so an
    enclosing stage such as "total" lands after the stages nested inside it.
    """

    def __init__(self) -> None:
        """Start with no stages recorded."""
        self.elapsed_ms: dict[str, float] = {}

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        """Time the enclosed block and store it under name, rounded to two decimals."""
        started = time.perf_counter()
        try:
            yield
        finally:
            self.elapsed_ms[name] = round((time.perf_counter() - started) * 1000, 2)


@dataclass
class RetrievalResult:
    """Passages ranked for a query, with the time each stage took in milliseconds."""

    matches: list[Match]
    timings_ms: dict[str, float]


@dataclass
class AnswerResult:
    """A composed reply, the passages it drew on and the per-stage timings in milliseconds."""

    reply: Reply
    matches: list[Match]
    timings_ms: dict[str, float]


class AnswerEngine:
    """Indexes sources and answers questions over them with cited replies.

    The engine owns a connection pool, so call close() or use it as a context manager.
    """

    def __init__(
        self,
        config: AppConfig,
        pool: ConnectionPool,
        encoder: VectorEncoder,
        scorer: RelevanceScorer,
        backend: AnswerBackend,
    ):
        """Wrap parts that are already built; from_config() builds them from settings."""
        self.config = config
        self.pool = pool
        self.encoder = encoder
        self.scorer = scorer
        self.backend = backend

    @classmethod
    def from_config(cls, config: AppConfig | None = None) -> "AnswerEngine":
        """Build a ready engine from config, falling back to load_config() when none is passed.

        Opening the pool creates the schema when it is missing. The encoder goes to the backend
        factory too, because the extractive backend ranks sentences with it.
        """
        config = config or load_config()
        pool = open_pool(config.database_url, config.embed_dim)
        encoder, scorer = load_encoders(config)
        return cls(config, pool, encoder, scorer, make_backend(config, encoder))

    def close(self) -> None:
        """Close the connection pool."""
        self.pool.close()

    def __enter__(self) -> "AnswerEngine":
        """Hand back the engine itself for use in a with block."""
        return self

    def __exit__(self, *exc_info) -> None:
        """Close the pool when the with block ends, whether or not it raised."""
        self.close()

    def index(self, sources: list[Source]) -> int:
        """Split, embed and store the given sources; return how many passages were written.

        Each passage is embedded together with its source title. The passages already stored
        for these source ids are deleted in the same transaction that inserts the new ones, so
        indexing a source again replaces it rather than duplicating it.
        """
        records = self._passage_rows(sources)
        with self.pool.connection() as conn, conn.transaction():
            conn.execute(
                "DELETE FROM passages WHERE source_id = ANY(%s)",
                ([source.id for source in sources],),
            )
            with conn.cursor() as cursor:
                cursor.executemany(INSERT_PASSAGE, records)
        return len(records)

    def _passage_rows(self, sources: list[Source]) -> list[tuple]:
        """Split the sources into passages and build the INSERT_PASSAGE parameters for each."""
        word_limit = self.config.passage_words
        pieces = [
            (source, ordinal, passage)
            for source in sources
            for ordinal, passage in enumerate(split_passages(source.body, word_limit))
        ]
        if not pieces:
            # Nothing to embed, and the encoder cannot stack an empty batch.
            return []
        vectors = self.encoder.encode_passages(
            [f"{source.title}\n{passage}" for source, _, passage in pieces]
        )
        records = []
        for (source, ordinal, passage), vector in zip(pieces, vectors, strict=True):
            # The lexemes column indexes title and body together, so the BM25 length counts both.
            word_count = len(source.title.split()) + len(passage.split())
            records.append((source.id, source.title, ordinal, passage, word_count, vector))
        return records

    def remove(self, source_id: str) -> int:
        """Delete every stored passage of one source and return how many rows were deleted."""
        with self.pool.connection() as conn:
            cursor = conn.execute("DELETE FROM passages WHERE source_id = %s", (source_id,))
            return cursor.rowcount

    def retrieve(
        self, query: str, k: int | None = None, mode: SearchMode = "hybrid", rerank: bool = True
    ) -> RetrievalResult:
        """Find the best passages for a query; k falls back to config.context_k."""
        stopwatch = Stopwatch()
        with stopwatch.measure("total"):
            found = self._collect(query, k or self.config.context_k, mode, rerank, stopwatch)
        return RetrievalResult(found, stopwatch.elapsed_ms)

    def answer(
        self, question: str, k: int | None = None, mode: SearchMode = "hybrid", rerank: bool = True
    ) -> AnswerResult:
        """Retrieve passages for a question and have the backend compose a cited reply.

        Retrieval works as in retrieve(); "compose" times the backend call and "total" spans both.
        """
        stopwatch = Stopwatch()
        with stopwatch.measure("total"):
            found = self._collect(question, k or self.config.context_k, mode, rerank, stopwatch)
            with stopwatch.measure("compose"):
                reply = self.backend.compose(question, found)
        return AnswerResult(reply, found, stopwatch.elapsed_ms)

    def _collect(
        self, query: str, k: int, mode: SearchMode, rerank: bool, stopwatch: Stopwatch
    ) -> list[Match]:
        """Run the search stages for one query and return at most k passages, best first.

        "keyword" runs BM25 only, "semantic" encodes the query and runs vector search only, and
        "hybrid" runs both and merges them with reciprocal rank fusion. Each search fetches up to
        search_depth hits. With rerank on, the top max(k, rerank_depth) candidates are re-scored
        by the cross-encoder; the list is cut to k either way.
        """
        depth = self.config.search_depth
        use_keyword = mode != "semantic"
        use_semantic = mode != "keyword"
        ranked_lists: list[list[Match]] = []
        if use_semantic:
            # Encode before borrowing a connection, so none is held while the model runs.
            with stopwatch.measure("encode"):
                query_vector = self.encoder.encode_query(query)
        with self.pool.connection() as conn:
            if use_keyword:
                with stopwatch.measure("keyword"):
                    ranked_lists.append(keyword_search(conn, query, depth))
            if use_semantic:
                with stopwatch.measure("semantic"):
                    ranked_lists.append(semantic_search(conn, query_vector, depth))
        if mode == "hybrid":
            with stopwatch.measure("fusion"):
                found = fuse_rankings(ranked_lists)
        else:
            found = ranked_lists[0]
        if rerank and found:
            with stopwatch.measure("rerank"):
                found = self._rerank(query, found, k)
        return found[:k]

    def _rerank(self, query: str, ranked: list[Match], k: int) -> list[Match]:
        """Re-score the leading candidates with the cross-encoder and return them best first.

        Taking max(k, rerank_depth) candidates means a k above rerank_depth still gets k
        results. The scorer reads title and body together, the same text the embeddings used.
        """
        shortlist = ranked[: max(k, self.config.rerank_depth)]
        texts = [f"{candidate.title}\n{candidate.body}" for candidate in shortlist]
        ratings = self.scorer.relevance(query, texts)
        rescored = [
            replace(candidate, score=rating)
            for candidate, rating in zip(shortlist, ratings, strict=True)
        ]
        return sorted(rescored, key=lambda candidate: candidate.score, reverse=True)
