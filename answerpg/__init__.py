"""answerpg: cited answers to questions about your own sources.

Sources are split into passages and stored in PostgreSQL, where BM25 keyword search and pgvector
similarity search pick the passages an answer backend reads and cites.
"""

__version__ = "0.1.0"
