/**
 * Model-free conversational echo graph with MemorySaver persistence.
 *
 * Demo / integration assistant for multi-turn threads (`thread_id`). Stays
 * free of LLM clients so local `bun run dev` and CI work without API keys.
 * Domain LLM graphs should use the shared helper under `src/llm` and
 * `compileWithMemory` from `src/checkpoint`.
 */
import { Annotation, StateGraph } from "@langchain/langgraph";
import type { RunnableConfig } from "@langchain/core/runnables";
import { compileWithMemory } from "../../checkpoint/index.js";

const ConversationState = Annotation.Root({
  message: Annotation<string>(),
  reply: Annotation<string>(),
  steps: Annotation<string[]>({
    reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
    default: () => [],
  }),
});

type ConversationConfig = RunnableConfig<{ replyPrefix?: string }>;

const respond = async (
  state: typeof ConversationState.State,
  config: ConversationConfig,
): Promise<typeof ConversationState.Update> => {
  const prefix = config.configurable?.replyPrefix ?? "gssc-conversation";
  const text = (state.message ?? "").trim() || "(empty message)";
  return {
    reply: `[${prefix}] received: ${text}`,
    steps: ["respond"],
  };
};

const builder = new StateGraph(ConversationState)
  .addNode("respond", respond)
  .addEdge("__start__", "respond");

export const graph = compileWithMemory(builder, {
  name: "GSSC Conversation",
});
