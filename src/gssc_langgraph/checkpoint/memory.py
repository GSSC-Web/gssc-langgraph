"""Thread-scoped checkpointer helpers for tests and direct invoke.

Default saver is the process-shared instance from env (``MemorySaver`` /
``InMemorySaver`` unless ``GSSC_CHECKPOINT_BACKEND=sqlite|postgres``).

Do **not** attach these savers to ``langgraph.json`` graph exports — Agent
Server rejects custom checkpointers and supplies its own persistence
(``POSTGRES_URI`` for a durable DB). Use :func:`compile_with_memory` only in
pytest helpers or offline scripts that invoke builders directly.
"""

from __future__ import annotations

from typing import Any, TypedDict

from gssc_langgraph.checkpoint.shared import shared_checkpointer

# Alias for shared_checkpointer (historical name used by callers/tests).
memory_saver = shared_checkpointer


def thread_config(
    thread_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a RunnableConfig that keys checkpoints to a thread."""
    extra = dict(extra or {})
    configurable = dict(extra.pop("configurable", None) or {})
    configurable["thread_id"] = thread_id
    return {
        **extra,
        "configurable": configurable,
    }


class CompileGraphOptions(TypedDict, total=False):
    """Options for :func:`compile_graph` / :func:`compile_with_memory`."""

    persist: bool
    checkpointer: Any
    name: str
    description: str


def compile_graph(builder: Any, options: CompileGraphOptions | None = None) -> Any:
    """Compile a StateGraph builder, optionally with a checkpointer.

    Prefer ``compile_with_memory`` for conversational / LLM graphs and for
    specialists that accumulate durable notes. Pure one-shot smoke graphs
    (e.g. ``health``) can keep ``builder.compile()`` or call
    ``compile_graph(builder, {"persist": False, "name": "…"})``.
    """
    opts: CompileGraphOptions = dict(options or {})  # type: ignore[assignment]
    persist = bool(opts.get("persist", False))
    if "checkpointer" in opts:
        checkpointer = opts["checkpointer"]
    else:
        checkpointer = shared_checkpointer if persist else None

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    if "name" in opts and opts["name"] is not None:
        compile_kwargs["name"] = opts["name"]
    if "description" in opts and opts["description"] is not None:
        compile_kwargs["description"] = opts["description"]

    return builder.compile(**compile_kwargs)


def compile_with_memory(
    builder: Any,
    options: CompileGraphOptions | None = None,
) -> Any:
    """Compile with the shared checkpointer for tests / direct invoke.

    Agent Server entrypoints must export ``builder.compile(name=…)`` without
    a checkpointer. Use this helper when a unit test or offline script needs
    ``thread_id`` persistence against an in-process (or env-selected) saver.
    Direct ``invoke`` / ``stream`` calls must pass ``configurable.thread_id``
    (see :func:`thread_config`).
    """
    opts: CompileGraphOptions = dict(options or {})  # type: ignore[assignment]
    opts["persist"] = True
    return compile_graph(builder, opts)
