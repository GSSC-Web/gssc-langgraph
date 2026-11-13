"""Process-wide default checkpointer selected by ``GSSC_CHECKPOINT_BACKEND``
(default: MemorySaver). For tests / direct ``compile_with_memory`` only — not
for ``langgraph.json`` exports (Agent Server supplies its own saver).

Initialized once at module load so graph
compiles attach the durable saver when configured.
"""

from __future__ import annotations

from typing import Any

from gssc_langgraph.checkpoint.create import create_checkpointer_from_env
from gssc_langgraph.checkpoint.env import resolve_checkpoint_config

# Resolved backend for the shared instance (handy for tests / diagnostics).
shared_checkpoint_config = resolve_checkpoint_config()

# Shared checkpointer used by compile_with_memory / compile_graph({persist})
# unless an explicit checkpointer option is passed.
shared_checkpointer: Any = create_checkpointer_from_env()
