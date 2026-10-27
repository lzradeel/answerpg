<p align="center">
  <img src="docs/banner.svg" width="100%" alt="answerpg: cited answers over your docs from PostgreSQL + pgvector">
</p>

<p align="center">
  <a href="https://github.com/lzradeel/answerpg/actions/workflows/checks.yml"><img src="https://github.com/lzradeel/answerpg/actions/workflows/checks.yml/badge.svg" alt="checks"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL%2017-pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL 17 with pgvector">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose">
</p>

<p align="center">
  <a href="#how-a-question-is-answered">Pipeline</a> ·
  <a href="#quality-gate">Quality gate</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#api">API</a> ·
  <a href="#latency-and-cost">Latency and cost</a> ·
  <a href="#limitations">Limitations</a>
</p>

<p align="center"><sub>recall@5 0.963 · MRR 0.872 · 40-question quality gate in CI · CPU-only reranking</sub></p>

Questions over a document collection are answered by answerpg, and each answer sentence is tied to the passage it was drawn from. Passages are stored, searched and logged in one PostgreSQL database with pgvector, and quality drops are caught by a CI gate before they are merged.

| part | approach |
|---|---|
| Search | BM25 in SQL and pgvector HNSW, fused by rank |
| Reranking | local cross-encoder on the CPU |
| Answers | `[n]` citations, extractive offline or by an Anthropic model |
| Quality gate | 40 questions, 5 metrics, run in CI |
| Tracking | stage timings, tokens and cost, logged in Postgres |

## How a question is answered

```mermaid
flowchart TD
    Q(["question"])
    subgraph PG ["PostgreSQL + pgvector"]
        KW["keyword<br/>BM25 over tsvector"]
        SEM["semantic<br/>HNSW cosine search"]
    end
    Q --> ENC["encode<br/>bge-small-en-v1.5"]
    Q --> KW
    ENC --> SEM
    KW -->|top 40| FUS["fusion<br/>reciprocal rank"]
    SEM -->|top 40| FUS
    FUS -->|top 20| RR["rerank<br/>cross-encoder"]
    RR -->|top 5| CMP{"compose"}
    CMP -->|extractive| ANS(["cited answer"])
    CMP -->|anthropic| ANS
```

One `POST /answer` call is traced below:

```mermaid
sequenceDiagram
    autonumber
    participant C as client
    participant S as FastAPI server
    participant E as AnswerEngine
    participant M as encoders
    participant P as Postgres
    participant B as answer backend
    participant L as request_log
    C->>S: POST /answer
    Note over S: X-API-Token checked if API_TOKEN is set
    S->>E: answer
    E->>M: encode_query
    E->>P: BM25 and HNSW queries
    P-->>E: up to 40 hits each
    E->>E: RRF fusion
    E->>M: relevance of top 20
    E->>B: compose with top 5
    B-->>E: Reply with citations
    E-->>S: AnswerResult with timings
    S->>L: row with timings, tokens, cost
    S-->>C: 200 JSON
```

**BM25 in SQL.** Since BM25 is not provided by `ts_rank`, Okapi BM25 (k1 1.2, b 0.75) is computed by one statement in `answerpg/retrieval.py`; candidates are found through a GIN index, and ties are broken by source and position.

**Fusion and reranking.** Ranks rather than raw scores are combined, since BM25 values and cosine similarities are measured on unrelated scales: `1 / (60 + rank)` is summed over the lists in which a passage is found. The 20 best candidates are then read with the question by a cross-encoder, and the top 5 are kept.

**Citations and backends.** Passages are cited as `[1]` to `[5]`; a marker beyond the retrieved passages is left out of the returned citations. By default, the two sentences closest to the question are quoted from the top three passages, so no network or cost is involved; with `ANSWER_BACKEND=anthropic`, the answer is written from the passages by `claude-opus-5-5` (low effort) or another configured model.

## Storage

```mermaid
erDiagram
    passages {
        bigserial id PK
        text source_id "unique with ordinal"
        text title
        int ordinal
        text body
        int word_count
        tsvector lexemes "generated, GIN index"
        vector embedding "384 dims, HNSW index"
    }
    request_log {
        bigserial id PK
        timestamptz logged_at "indexed"
        text route
        text query
        text model
        real total_ms
        jsonb timings
        int input_tokens
        int output_tokens
        numeric cost_usd
    }
```

Both tables are created at startup if missing. Re-indexing is kept idempotent: a source's old passages are deleted and its new ones inserted in one transaction. One `request_log` row is written per `/retrieve` or `/answer` call, and the rows are summarised by `/usage`.

## Quality gate

```mermaid
flowchart TD
    EV(["push or pull request"]) --> U["unit job<br/>ruff and pytest"]
    U --> IDX["quality job<br/>25 articles indexed"]
    IDX --> RUN["40 questions answered,<br/>retrievers compared"]
    RUN --> CHK{"metric more than 0.02<br/>below baseline?"}
    CHK -->|yes| RED["gate failed, exit 1"]
    CHK -->|no| GREEN["gate passed"]
    RUN -.-> REP["results.md<br/>in job summary"]
```

The 40 questions in `evaluation/questions.jsonl` are put to the 25 articles in `data/articles/`, help pages for an invented product, Wrenfield, in which near-identical figures and neighbouring error codes are deliberately repeated. Scores were measured with hybrid search, reranking, the extractive backend and k = 5:

| metric | measured as | score |
|---|---|---:|
| recall@5 | relevant articles found in the top 5 | 0.963 |
| MRR | 1 / rank of the first relevant hit | 0.872 |
| faithfulness | sentences backed by a cited passage (numbers, cosine 0.8) | 1.000 |
| answer_relevance | cosine of question and answer | 0.798 |
| answer_similarity | cosine of answer and reference | 0.778 |

The gate is failed when any metric is found more than 0.02 below `evaluation/baseline.json`. It is run by `.github/workflows/checks.yml`, its report is written to `evaluation/results.md`, and a new baseline is recorded with `make rebaseline`. Retrieval alone is measured with `make compare`:

| retriever | recall@5 | MRR | p50 ms |
|---|---:|---:|---:|
| keyword | 0.863 | 0.762 | 2.4 |
| semantic | 0.875 | 0.783 | 9.9 |
| hybrid | 0.875 | 0.760 | 12.1 |
| hybrid + rerank | 0.963 | 0.872 | 820.1 |

Without the reranker, semantic search alone is not beaten by fusion (equal recall@5, lower MRR), since good vector hits are crowded out by weak keyword matches; with the cross-encoder, recall@5 is raised by 8.8 points and MRR by 11.2 points, so reranking is kept despite its latency.

## Quickstart

The whole stack is started with `make demo` (Docker Compose v2 is needed): the image is built, Postgres and the API are started, the articles are indexed and a sample question is answered. The models are baked into the image, which is run as a non-root user with two uvicorn workers beside `pgvector/pgvector:pg17`.

For a local install, Python 3.11 to 3.14 is required:

```bash
git clone https://github.com/lzradeel/answerpg.git && cd answerpg
python3 -m venv .venv && source .venv/bin/activate
make install db index serve
```

Postgres is run in Docker by `make db`; without it, any PostgreSQL 17 with pgvector can be used once an `answerpg` role and database (password `answerpg`) are created and `CREATE EXTENSION vector` is run by a superuser. `{"status":"ok","passages":87,"backend":"extractive"}` is then returned by `/healthz`. From Python, the articles are indexed and a question is answered by `python examples/demo.py [question]`.

Two models (about 150 MB) are downloaded into `.cache/models` on first use, after which everything is run offline. LLM answers are enabled with `ANSWER_BACKEND=anthropic` and `ANTHROPIC_API_KEY`; tests and the gate are run with `make test` and `make evaluate`.

## API

| method | path | purpose |
|---|---|---|
| GET | `/healthz` | status, passage count, backend |
| POST | `/sources` | indexing of `{id, title, body}` sources |
| DELETE | `/sources/{source_id}` | removal of a source, 404 if unknown |
| POST | `/retrieve` | matches only; `hybrid`, `keyword` or `semantic`; rerank optional |
| POST | `/answer` | cited answer, timings, tokens and cost; 502 on a model error |
| GET | `/usage?hours=24` | request count, latency percentiles, cost |

When `API_TOKEN` is set, a matching `X-API-Token` header is required on POST and DELETE routes (401 otherwise); `/healthz` and `/usage` are left open. This reply to `{"question": "How many API requests per minute does a Business workspace get?"}` was captured:

```json
{"answer": "Team workspaces can make 300 requests per minute [1]. Business workspaces can make 600 requests per minute [1].",
 "citations": [{"ref": 1, "passage_id": 98, "source_id": "api-rate-limits", "title": "API rate limits",
   "snippet": "Rate limits stop bursts of traffic from slowing the API down for everyone.\nLimits apply per workspace and are counted over a rolling 60-second window, across all tokens in that workspace.\nLimits by ..."}],
 "model": "extractive", "usage": {"input_tokens": 0, "output_tokens": 0}, "cost_usd": 0.0,
 "timings_ms": {"encode": 5.6, "keyword": 3.21, "semantic": 1.23, "fusion": 0.16, "rerank": 412.07, "compose": 133.64, "total": 556.07}}
```

## Latency and cost

These timings were recorded by `python scripts/latency.py --runs 2` (40 questions asked twice, extractive backend) on a 4-core Intel i7-1068NG7 with 16 GB of RAM and no GPU, against PostgreSQL 17.11 and pgvector 0.8.7 holding 87 passages:

| stage | p50 ms | p95 ms | mean ms |
|---|---:|---:|---:|
| encode | 6.6 | 16.6 | 8.6 |
| keyword | 3.0 | 7.6 | 3.7 |
| semantic | 1.3 | 3.2 | 1.6 |
| fusion | 0.2 | 0.5 | 0.3 |
| rerank | 640.4 | 1382.0 | 770.6 |
| compose | 232.4 | 501.0 | 270.4 |
| total | 909.2 | 1863.1 | 1055.3 |

Most of the time is taken by reranking on the CPU; accuracy is traded for speed by a lower `RERANK_DEPTH` or `"rerank": false` on `/retrieve`.

| backend | per query | per 1,000 queries |
|---|---:|---:|
| extractive | $0 | $0 |
| claude-haiku-5-5 | $0.000243 | $0.24 |
| claude-sonnet-5-5 | $0.004856 | $4.86 |
| claude-opus-5-5 | $0.009711 | $9.71 |

The model rows assume roughly 930 prompt tokens and 300 completion tokens per question; live requests are priced from the usage reported with each response.

## Configuration

Settings are read from the environment, then from `.env` (see `.env.example`); the defaults are listed below.

```ini
DATABASE_URL=postgresql://answerpg:answerpg@localhost:5432/answerpg
EMBED_MODEL=BAAI/bge-small-en-v1.5
EMBED_DIM=384  # must match EMBED_MODEL
CROSS_ENCODER_MODEL=Xenova/ms-marco-MiniLM-L-6-v2
MODEL_DIR=.cache/models
ANSWER_BACKEND=extractive  # or anthropic
ANSWER_MODEL=claude-opus-5-5
ANSWER_EFFORT=low  # low, medium or high
ANSWER_MAX_TOKENS=2048
ANTHROPIC_API_KEY=
SEARCH_DEPTH=40  # candidates per retriever
RERANK_DEPTH=20  # candidates reranked
CONTEXT_K=5  # k for Python calls without one; HTTP sends k
PASSAGE_WORDS=120  # word limit per passage
API_TOKEN=  # X-API-Token value for POST and DELETE
```

Under Compose, only `ANSWER_BACKEND`, `ANTHROPIC_API_KEY` and `API_TOKEN` are taken from the host.

## Layout

```
answerpg/       service package
evaluation/     question set, scoring, gate, baseline, results
scripts/        index_corpus.py, latency.py
examples/       demo.py
data/articles/  the 25 Wrenfield articles
tests/          unit and API tests
```

## Limitations

- A faithfulness of 1.000 is reached by design with the extractive backend, whose sentences are copied verbatim; the metric is meant for LLM answers.
- Answer quality is approximated with embeddings, since a fee and nondeterminism would be added to CI by an LLM judge.
- Only a small synthetic corpus is covered, so no public benchmark is represented.
- BM25 statistics are recomputed per query, and both models and up to 10 connections are held by every uvicorn worker.
