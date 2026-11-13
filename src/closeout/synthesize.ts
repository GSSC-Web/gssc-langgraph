/**
 * Optional LLM synthesis for closeout_review.
 *
 * Runs after deterministic checks. Uses createChatModel (xAI) when a key is
 * present; otherwise returns a skipped note so the graph stays model-free.
 */
import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { z } from "zod";
import { createChatModel, resolveLlmConfig } from "../llm/index.js";
import type {
  CloseoutFinding,
  CloseoutSynthesis,
  CloseoutVerdict,
  ProposedMemoryUpdate,
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

export type SynthesizeCloseoutInput = {
  verdict: CloseoutVerdict | "";
  summary: string;
  findings: CloseoutFinding[];
  gssc5ContextText?: string;
  kaneoTaskId?: string;
  prScope?: string;
  uids?: string[];
  /** Force skip even when a key is present. */
  enabled?: boolean;
};

function skipped(note: string, summary: string): CloseoutSynthesis {
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

function buildPrompt(input: SynthesizeCloseoutInput): string {
  const findings = (input.findings ?? []).slice(0, 40).map((f) => ({
    check: f.check,
    severity: f.severity,
    uid: f.uid,
    path: f.path,
    message: f.message,
    fix: f.fix,
  }));
  const scope = {
    kaneoTaskId: input.kaneoTaskId || undefined,
    prScope: input.prScope || undefined,
    uids: input.uids?.length ? input.uids : undefined,
  };
  const context = (input.gssc5ContextText ?? "").slice(0, 12_000);
  return [
    "Produce a short closeout synthesis for a Cursor / Kaneo agent.",
    "Return ONLY a JSON object with keys:",
    '  narrativeSummary: string (2-5 sentences, plain language)',
    "  proposedMemoryUpdates: array of { memoryId, summary, rationale? }",
    "Proposed memory updates are advisory only (gssc5 .agents/memories ids",
    "like backend-arch, public-arch, members-arch — or new:<slug>).",
    "Do not invent FAIL findings; respect the deterministic verdict.",
    "",
    `verdict: ${input.verdict || "UNKNOWN"}`,
    `deterministicSummary: ${input.summary || "(none)"}`,
    `scope: ${JSON.stringify(scope)}`,
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
export async function synthesizeCloseout(
  input: SynthesizeCloseoutInput,
): Promise<CloseoutSynthesis> {
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
        "You synthesize closeout_review results. Reply with JSON only.",
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
