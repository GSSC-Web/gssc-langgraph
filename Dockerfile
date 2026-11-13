# Minimal image packaging graph code with Python / uv.
# Prefer `uv run langgraph build` / langgraph-cli for a full Agent Server image
# driven by langgraph.json (includes MCP at /mcp).
#
# Day-to-day local work:
#   uv sync --all-extras
#   uv run langgraph dev

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock* README.md ./
COPY src ./src
COPY langgraph.json ./

RUN uv sync --frozen --no-dev || uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
CMD ["langgraph", "dev", "--host", "0.0.0.0", "--port", "2024"]
