/**
 * Minimal health graph for service smoke checks.
 *
 * The LangGraph Agent Server also exposes HTTP `/ok`; this graph is a
 * first-class assistant id (`health`) so gssc5 can call the same
 * threads/runs API used for real workflows.
 */
import { Annotation, StateGraph } from "@langchain/langgraph";

const HealthState = Annotation.Root({
  status: Annotation<string>(),
  service: Annotation<string>(),
  checkedAt: Annotation<string>(),
});

const checkHealth = async (
  _state: typeof HealthState.State,
): Promise<typeof HealthState.Update> => {
  return {
    status: "ok",
    service: "gssc-langgraph",
    checkedAt: new Date().toISOString(),
  };
};

const builder = new StateGraph(HealthState)
  .addNode("checkHealth", checkHealth)
  .addEdge("__start__", "checkHealth");

export const graph = builder.compile();
graph.name = "GSSC Health";
