/**
 * Package entry — domain graphs live under `./graphs/*` and are registered
 * in `langgraph.json`. Add new workflows as sibling folders and wire them
 * into `langgraph.json`.
 */
export { graph as healthGraph } from "./graphs/health/graph.js";
export { graph as sampleAgentGraph } from "./graphs/sample_agent/graph.js";
