/**
 * Optional LLM synthesis for test_development.
 *
 * Runs after deterministic analysis. Uses createChatModel (xAI) when a key is
 * present; otherwise returns a skipped note so the graph stays usable without
 * XAI_API_KEY.
 */
import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { z } from "zod";
import { createChatModel, resolveLlmConfig } from "../llm/index.js";
import type {
  Finding,
  PlanItem,
  ProposedMemoryUpdate,
  TestDevSynthesis,
  TestDevVerdict,
} from "./types.js";

const ProposedMemoryUpdateSchema = z.object({
  memoryId: z.string().min(1),
  summary: z.string().min(1),
  rationale: z.string().optional(),
});

const SynthesisJsonSchema = z.object({
  narrativeSummary: z.string().min(1),
  proposedMemoryUpdates: z.array(ProposedMemoryUpdateSchema).default([]),
});

export type SynthesizeTestDevInput = {
  verdict: TestDevVerdict | "";
  summary: string;
  findings: Finding[];
  plan?: PlanItem[];
  scopeGraphIds?: string[];
  commands?: string[];
  gssc5ContextText?: string;
  /** Force skip even when a key is present. */
  enabled?: boolean;
};

function skipped(note: string, summary: string): TestDevSynthesis {
  return {
    narrativeSummary: summary || "",
    proposedMemoryUpdates: [],
    note,
  };
}

function extractJsonObject(text: string): unknown {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const raw = (fenced?.[1] ?? text).trim();
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start < 0 || end <= start) {
    throw new Error("no JSON object in model response");
  }
  return JSON.parse(raw.slice(start, end + 1));
}

function buildPrompt(input: SynthesizeTestDevInput): string {
  const findings = (input.findings ?? []).slice(0, 40).map((f) => ({
    check: f.check,
    severity: f.severity,
    contractId: f.contractId,
    graphId: f.graphId,
    path: f.path,
    message: f.message,
    fix: f.fix,
  }));
  const plan = (input.plan ?? []).slice(0, 20).map((p) => ({
    action: p.action,
    graphId: p.graphId,
    contractId: p.contractId,
    path: p.path,
    description: p.description,
  }));
  const context = (input.gssc5ContextText ?? "").slice(0, 12_000);
  return [
    "Produce a short test-development synthesis for a Cursor / Kaneo agent.",
    "Return ONLY a JSON object with keys:",
    "  narrativeSummary: string (2-5 sentences, plain language)",
    "  proposedMemoryUpdates: array of { memoryId, summary, rationale? }",
    "Proposed memory updates are advisory only (gssc5 .agents/memories ids",
    "like backend-arch, public-arch, members-arch — or new:<slug>).",
    "Do not invent FAIL findings; respect the deterministic verdict and plan.",
    "",
    `verdict: ${input.verdict || "UNKNOWN"}`,
    `deterministicSummary: ${input.summary || "(none)"}`,
    `scopeGraphIds: ${JSON.stringify(input.scopeGraphIds ?? [])}`,
    `commands: ${JSON.stringify((input.commands ?? []).slice(0, 10))}`,
    `plan: ${JSON.stringify(plan)}`,
    `findings: ${JSON.stringify(findings)}`,
    context
      ? `gssc5Context (truncated):\n${context}`
      : "gssc5Context: (none)",
  ].join("\n");
}

/**
 * Optionally call createChatModel for a short NL summary + memory proposals.
 * Never throws for missing keys — returns a skipped synthesis instead.
 */
export async function synthesizeTestDev(
  input: SynthesizeTestDevInput,
): Promise<TestDevSynthesis> {
  if (input.enabled === false) {
    return skipped("skipped: disabled", input.summary);
  }

  const cfg = resolveLlmConfig();
  if (!cfg.hasApiKey) {
    return skipped("skipped: no XAI_API_KEY", input.summary);
  }

  try {
    const llm = createChatModel({ temperature: 0 });
    const response = await llm.invoke([
      new SystemMessage(
        "You synthesize test_development results. Reply with JSON only.",
      ),
      new HumanMessage(buildPrompt(input)),
    ]);
    const text =
      typeof response.content === "string"
        ? response.content
        : Array.isArray(response.content)
          ? response.content
              .map((part) =>
                typeof part === "string"
                  ? part
                  : "text" in part
                    ? String(part.text ?? "")
                    : "",
              )
              .join("")
          : String(response.content ?? "");

    const parsed = SynthesisJsonSchema.parse(extractJsonObject(text));
    const proposedMemoryUpdates: ProposedMemoryUpdate[] =
      parsed.proposedMemoryUpdates.map((u) => ({
        memoryId: u.memoryId,
        summary: u.summary,
        rationale: u.rationale,
      }));

    return {
      narrativeSummary: parsed.narrativeSummary.trim(),
      proposedMemoryUpdates,
      note: "ok",
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return skipped(`error: ${message}`, input.summary);
  }
}
