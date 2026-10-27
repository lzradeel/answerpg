"""The two local fastembed models: a text embedder and a cross-encoder relevance scorer.

Running python -m answerpg.encoders downloads both into the model cache and runs each once; the
Docker build does this so the image ships with the models already inside.
"""

import numpy as np
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

from answerpg.settings import AppConfig, load_config


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """Return vectors as float32, each scaled to unit length along the last axis.

    Other modules take the dot product of two embeddings as their cosine similarity, which only
    holds for unit vectors. The norm is clamped at 1e-12 so an all-zero vector stays zero instead
    of turning into NaNs through a division by zero.
    """
    floats = np.asarray(vectors, dtype=np.float32)
    lengths = np.linalg.norm(floats, axis=-1, keepdims=True)
    return floats / np.maximum(lengths, 1e-12)


class VectorEncoder:
    """Turns text into unit-length dense vectors with a fastembed embedding model."""

    def __init__(self, model_name: str, cache_dir: str | None = None):
        """Load model_name, downloading it into cache_dir on first use."""
        self.model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)

    def encode_query(self, text: str) -> np.ndarray:
        """Embed one search query and return it as a single vector.

        fastembed embeds queries and passages through separate calls because some models encode
        the two sides differently (with an instruction prefix, for example), so a query has to
        come through here and stored text through encode_passages.
        """
        vector = next(iter(self.model.query_embed(text)))
        return _l2_normalize(vector)

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        """Embed texts with fastembed's passage call and return one row per text.

        texts must not be empty, since there would be no rows to stack into a matrix.
        """
        return _l2_normalize(np.stack(list(self.model.passage_embed(texts))))


class RelevanceScorer:
    """Re-scores candidate passages for a query with a fastembed cross-encoder.

    A cross-encoder reads the query and a passage together, which judges relevance better than
    comparing two separate embeddings but costs one model run per pair, so it only sees the top
    candidates.
    """

    def __init__(self, model_name: str, cache_dir: str | None = None):
        """Load the cross-encoder model_name, downloading it into cache_dir on first use."""
        self.model = TextCrossEncoder(model_name=model_name, cache_dir=cache_dir)

    def relevance(self, query: str, passages: list[str]) -> list[float]:
        """Score each passage against query, in input order; higher means more relevant.

        The scores are unbounded logits rather than probabilities.
        """
        return [float(logit) for logit in self.model.rerank(query, passages)]


def load_encoders(config: AppConfig) -> tuple[VectorEncoder, RelevanceScorer]:
    """Create the embedder and the cross-encoder that config names, both cached in model_dir."""
    return (
        VectorEncoder(config.embed_model, config.model_dir),
        RelevanceScorer(config.cross_encoder_model, config.model_dir),
    )


def _warm_up() -> None:
    """Fetch both configured models if missing, run each once, and print what was loaded."""
    config = load_config()
    text_encoder, cross_encoder = load_encoders(config)
    probe = "warm-up check"
    dimension = text_encoder.encode_query(probe).shape[0]
    cross_encoder.relevance(probe, [probe])
    print(f"Loaded {config.embed_model} ({dimension}-dim vectors) and {config.cross_encoder_model}")


if __name__ == "__main__":
    _warm_up()
