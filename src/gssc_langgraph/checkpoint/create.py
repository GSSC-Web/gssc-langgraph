"""Build a LangGraph checkpointer from env (MemorySaver / SqliteSaver /
PostgresSaver).

Memory is the default. SQLite and Postgres use the official
``langgraph.checkpoint.*`` packages so thread state — including specialist
``reviewMemory`` / ``specialistNotes`` — survives Agent Server restarts when
the same ``thread_id`` is reused.

Prefer sync APIs for ``graph.compile(checkpointer=...)``.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from gssc_langgraph.checkpoint.env import (
    CheckpointConfig,
    resolve_checkpoint_config,
)


def create_checkpointer(config: CheckpointConfig) -> Any:
    """Create (and for Postgres/SQLite, ``setup()``) a checkpointer.

    Prefer :func:`create_checkpointer_from_env` at process start.
    """
    if config["backend"] == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    if config["backend"] == "sqlite":
        # SqliteSaver.from_conn_string is a context manager that closes the
        # connection on exit — keep a long-lived connection for the process.
        from langgraph.checkpoint.sqlite import SqliteSaver

        path = config["path"]
        parent = Path(path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()
        return saver

    # postgres
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg import Connection
    from psycopg.rows import dict_row

    # Python PostgresSaver has no schema= kwarg (unlike TS). Apply search_path.
    schema = config.get("schema") or "public"
    conn = Connection.connect(
        config["connectionString"],
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        options=f"-c search_path={schema}",
    )
    saver = PostgresSaver(conn)
    saver.setup()
    return saver


def create_checkpointer_from_env(env: Mapping[str, str] | None = None) -> Any:
    """Resolve env → create the process checkpointer (calls Postgres ``setup()``)."""
    source: Mapping[str, str]
    if env is not None:
        source = env
    else:
        source = os.environ
    return create_checkpointer(resolve_checkpoint_config(source))
