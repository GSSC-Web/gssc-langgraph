"""Checkpoint config resolution + SQLite smoke script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from gssc_langgraph.checkpoint import (
    CHECKPOINT_BACKEND_ENV,
    CHECKPOINT_POSTGRES_URL_ENV,
    CHECKPOINT_SQLITE_PATH_ENV,
    resolve_checkpoint_config,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _restore_checkpoint_env() -> None:
    tracked = (
        CHECKPOINT_BACKEND_ENV,
        CHECKPOINT_SQLITE_PATH_ENV,
        CHECKPOINT_POSTGRES_URL_ENV,
    )
    saved = {key: os.environ.get(key) for key in tracked}
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_resolve_checkpoint_config_defaults_to_memory() -> None:
    os.environ.pop(CHECKPOINT_BACKEND_ENV, None)
    assert resolve_checkpoint_config({}) == {"backend": "memory"}


def test_resolve_checkpoint_config_accepts_sqlite_aliases() -> None:
    assert resolve_checkpoint_config({CHECKPOINT_BACKEND_ENV: "sqlite"}) == {
        "backend": "sqlite",
        "path": ".data/langgraph-checkpoints.sqlite",
    }
    assert resolve_checkpoint_config(
        {
            CHECKPOINT_BACKEND_ENV: "SQLITE3",
            CHECKPOINT_SQLITE_PATH_ENV: "/tmp/cp.sqlite",
        }
    ) == {"backend": "sqlite", "path": "/tmp/cp.sqlite"}


def test_resolve_checkpoint_config_requires_postgres_url() -> None:
    with pytest.raises(ValueError, match="GSSC_CHECKPOINT_POSTGRES_URL"):
        resolve_checkpoint_config({CHECKPOINT_BACKEND_ENV: "postgres"})


def test_resolve_checkpoint_config_rejects_unknown_backends() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        resolve_checkpoint_config({CHECKPOINT_BACKEND_ENV: "redis"})


def test_sqlite_checkpointer_smoke_script() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/verify_sqlite_checkpoint.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "ok: sqlite checkpointer" in proc.stdout
