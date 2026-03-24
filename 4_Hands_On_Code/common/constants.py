"""
constants.py — Hardcoded values that never change across environments.

Use this for: token limits, chunk sizes, retry counts, model names, pricing tables.
These are code, not configuration. They change with code, not with deployment.

For environment-specific values (API keys, endpoints), see config.py.
"""

# --- OpenAI Models ---
DEFAULT_MODEL = "gpt-4o-mini"

# --- Token Limits ---
# gpt-4o-mini context window
MAX_CONTEXT_TOKENS = 128_000

# Safe ceiling for a single completion response
MAX_COMPLETION_TOKENS = 4_096

# --- RAG / Chunking (populated in Week 3) ---
# DEFAULT_CHUNK_SIZE = 512
# DEFAULT_CHUNK_OVERLAP = 50

# --- Retry ---
# MAX_RETRIES = 3
# RETRY_BACKOFF_SECONDS = 2