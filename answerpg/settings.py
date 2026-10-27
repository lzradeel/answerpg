"""Runtime settings, read from environment variables and an optional .env file."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Every service setting, each one overridable from the environment.

    A field takes its value from the environment variable with the same name, compared without
    regard to case, so EMBED_DIM sets embed_dim. A .env file in the working directory is read too
    when one exists; exported variables win over it, and any of its keys that match no field are
    ignored instead of failing validation.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://answerpg:answerpg@localhost:5432/answerpg"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384  # width of the vector column, so it must match embed_model's output
    cross_encoder_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    model_dir: str = ".cache/models"  # download cache shared by both models

    # "extractive" runs locally; the other fields in this group only apply to "anthropic".
    answer_backend: Literal["extractive", "anthropic"] = "extractive"
    answer_model: str = "claude-opus-5-5"
    answer_effort: Literal["low", "medium", "high"] = "low"
    answer_max_tokens: int = 2048
    anthropic_api_key: str | None = None

    passage_words: int = 120  # word limit for each passage when sources are indexed
    search_depth: int = 40  # candidates each retriever returns
    rerank_depth: int = 20  # top candidates the cross-encoder re-scores, or k if that is larger
    context_k: int = 5  # matches to return, and to answer from, when a call gives no k

    api_token: str | None = None  # if set, each POST or DELETE call must send it as X-API-Token


@lru_cache
def load_config() -> AppConfig:
    """Return one shared AppConfig, built on the first call and cached from then on.

    The environment and .env are read only once per process, so later changes to them take
    effect only after a restart.
    """
    return AppConfig()
