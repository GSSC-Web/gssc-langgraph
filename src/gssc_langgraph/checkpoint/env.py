"""Env helpers for selecting the LangGraph checkpointer backend.

Default is in-process MemorySaver (``GSSC_CHECKPOINT_BACKEND`` unset or
``memory``) so local dev stays zero-config. Set ``sqlite`` or ``postgres``
for durable thread state (including specialist ``reviewMemory`` /
``specialistNotes``) that survives process restarts.
"""

from __future__ import annotations

import os
from typing import Literal, Mapping, TypedDict

CHECKPOINT_BACKEND_ENV = "GSSC_CHECKPOINT_BACKEND"
CHECKPOINT_SQLITE_PATH_ENV = "GSSC_CHECKPOINT_SQLITE_PATH"
CHECKPOINT_POSTGRES_URL_ENV = "GSSC_CHECKPOINT_POSTGRES_URL"
CHECKPOINT_POSTGRES_SCHEMA_ENV = "GSSC_CHECKPOINT_POSTGRES_SCHEMA"

# Default on-disk SQLite path when backend=sqlite and no path env is set.
DEFAULT_SQLITE_PATH = ".data/langgraph-checkpoints.sqlite"

CheckpointBackend = Literal["memory", "sqlite", "postgres"]


class MemoryCheckpointConfig(TypedDict):
    backend: Literal["memory"]


class SqliteCheckpointConfig(TypedDict):
    backend: Literal["sqlite"]
    path: str


class PostgresCheckpointConfig(TypedDict):
    backend: Literal["postgres"]
    connectionString: str
    schema: str


CheckpointConfig = MemoryCheckpointConfig | SqliteCheckpointConfig | PostgresCheckpointConfig


def _normalize_backend(raw: str) -> CheckpointBackend | None:
    v = raw.strip().lower()
    if v in ("", "memory", "mem", "inmemory"):
        return "memory"
    if v in ("sqlite", "sqlite3"):
        return "sqlite"
    if v in ("postgres", "postgresql", "pg"):
        return "postgres"
    return None


def resolve_checkpoint_config(
    env: Mapping[str, str] | None = None,
) -> CheckpointConfig:
    """Resolve checkpointer settings from env.

    Raises on unknown backend or missing Postgres URL when ``backend=postgres``.
    """
    source = env if env is not None else os.environ
    raw_backend = source.get(CHECKPOINT_BACKEND_ENV, "")
    backend = _normalize_backend(raw_backend if raw_backend is not None else "")
    if backend is None:
        raise ValueError(
            f"Unsupported {CHECKPOINT_BACKEND_ENV}={raw_backend!r}. "
            "Use memory | sqlite | postgres."
        )

    if backend == "memory":
        return {"backend": "memory"}

    if backend == "sqlite":
        path = (source.get(CHECKPOINT_SQLITE_PATH_ENV) or "").strip() or DEFAULT_SQLITE_PATH
        return {"backend": "sqlite", "path": path}

    connection_string = (source.get(CHECKPOINT_POSTGRES_URL_ENV) or "").strip()
    if not connection_string:
        raise ValueError(
            f"{CHECKPOINT_BACKEND_ENV}=postgres requires {CHECKPOINT_POSTGRES_URL_ENV}"
        )
    schema = (source.get(CHECKPOINT_POSTGRES_SCHEMA_ENV) or "").strip() or "public"
    return {
        "backend": "postgres",
        "connectionString": connection_string,
        "schema": schema,
    }
