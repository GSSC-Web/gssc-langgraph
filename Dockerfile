# Minimal image packaging graph code with Bun.
# Prefer `bunx @langchain/langgraph-cli build` for a full Agent Server image
# driven by langgraph.json.
#
# Day-to-day local work:
#   bun install
#   bun run dev

FROM oven/bun:1.4-alpine

WORKDIR /app

COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile || bun install

COPY tsconfig.json langgraph.json ./
COPY src ./src

CMD ["bun", "run", "src/index.ts"]
