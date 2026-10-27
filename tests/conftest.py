"""Shared fixtures: an offline stand-in for the embedding model and a client for the live API."""

import re
import zlib

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

from answerpg.server import app
from answerpg.settings import load_config

TOKEN = re.compile(r"[a-z0-9]+")

# Advisory lock that api_client holds for a whole test session. It has to differ from the
# 31415926 that open_pool takes while the app starts: the app asks for that one on a connection
# of its own, so a session already holding it would leave its own app waiting forever.
API_SESSION_LOCK = 27182818


class HashingEncoder:
    """Encoder double that hashes each lower-cased word into one of `dim` count buckets.

    It needs no model download and always gives the same vectors, and texts that share words
    still come out similar, which is all the unit tests ask of an embedding.
    """

    dim = 256

    def _vectorize(self, text: str) -> np.ndarray:
        """Count words into CRC-32 buckets and scale to unit length (a wordless text stays zero)."""
        counts = np.zeros(self.dim, dtype=np.float32)
        for word in TOKEN.findall(text.lower()):
            counts[zlib.crc32(word.encode()) % self.dim] += 1.0
        length = np.linalg.norm(counts)
        return counts / length if length else counts

    def encode_query(self, text: str) -> np.ndarray:
        """Embed a single query string."""
        return self._vectorize(text)

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        """Embed passages as rows of a matrix; the reshape keeps an empty batch at (0, dim)."""
        return np.array([self._vectorize(text) for text in texts]).reshape(len(texts), self.dim)


@pytest.fixture
def encoder() -> HashingEncoder:
    """A hashing encoder for tests that need embeddings without loading a real model."""
    return HashingEncoder()


@pytest.fixture(scope="session")
def api_client():
    """One TestClient over the real app for the whole session, skipped when Postgres is down.

    Test sessions that share a database take turns: each one holds API_SESSION_LOCK on a
    connection of its own until teardown closes it. Two sessions at once would index the same
    sample passages under different ids, equal scores are settled by source_id, and the session
    whose id sorts later would never see its own source cited.
    """
    database_url = load_config().database_url
    try:
        lock_holder = psycopg.connect(database_url, autocommit=True, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip(f"Postgres is not reachable at {database_url}")
    # Leaving this block closes the connection, and with it goes the session-level lock.
    with lock_holder:
        lock_holder.execute("SELECT pg_advisory_lock(%s)", (API_SESSION_LOCK,))
        with TestClient(app) as client:
            yield client
