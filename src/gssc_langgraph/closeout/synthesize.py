"""
Optional LLM synthesis for closeout_review.

Runs after deterministic checks. Uses create_chat_model (xAI) when a key is
present; otherwise returns a skipped note so the graph stays model-free.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from gssc_langgraph.closeout.types import (
    CloseoutFinding,
    CloseoutSynthesis,
    CloseoutVerdict,
    ProposedMemoryUpdate,
)


class SynthesizeCloseoutInput(TypedDict, total=False):
    verdict: CloseoutVerdict | str
    summary: str
    findings: list[CloseoutFinding]
    gssc5ContextText: str
    kaneoTaskId: str
    prScope: str
    uids: list[str]
    enabled: bool


def _skipped(note: str, summary: str) -> CloseoutSynthesis:
    return {
        "narrativeSummary": summary or "",
        "proposedMemoryUpdates": [],
        "note": note,
    }


def _has_api_key(cfg: Any) -> bool:
    if hasattr(cfg, "has_api_key"):
        return bool(cfg.has_api_key)
    if isinstance(cfg, dict):
        return bool(cfg.get("has_api_key") or cfg.get("hasApiKey"))
    return False


def _extract_json_object(text: str) -> Any:
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    raw = (fenced.group(1) if fenced else text).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model response")
    return json.loads(raw[start : end + 1])


def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part.get("text") or ""))
            elif hasattr(part, "text"):
                parts.append(str(getattr(part, "text", "") or ""))
        return "".join(parts)
    return str(content or "")


def _build_prompt(input_data: SynthesizeCloseoutInput) -> str:
    findings = [
        {
            "check": f.get("check"),
            "severity": f.get("severity"),
            "uid": f.get("uid"),
            "path": f.get("path"),
            "message": f.get("message"),
            "fix": f.get("fix"),
        }
        for f in (input_data.get("findings") or [])[:40]
    ]
    scope: dict[str, Any] = {}
    if input_data.get("kaneoTaskId"):
        scope["kaneoTaskId"] = input_data["kaneoTaskId"]
    if input_data.get("prScope"):
        scope["prScope"] = input_data["prScope"]
    if input_data.get("uids"):
        scope["uids"] = input_data["uids"]

    context = (input_data.get("gssc5ContextText") or "")[:12_000]
    return "\n".join(
        [
            "Produce a short closeout synthesis for a Cursor / Kaneo agent.",
            "Return ONLY a JSON object with keys:",
            "  narrativeSummary: string (2-5 sentences, plain language)",
            "  proposedMemoryUpdates: array of { memoryId, summary, rationale? }",
            "Proposed memory updates are advisory only (gssc5 .agents/memories ids",
            "like backend-arch, public-arch, members-arch — or new:<slug>).",
            "Do not invent FAIL findings; respect the deterministic verdict.",
            "",
            f"verdict: {input_data.get('verdict') or 'UNKNOWN'}",
            f"deterministicSummary: {input_data.get('summary') or '(none)'}",
            f"scope: {json.dumps(scope)}",
            f"findings: {json.dumps(findings)}",
            (
                f"gssc5Context (truncated):\n{context}"
                if context
                else "gssc5Context: (none)"
            ),
        ]
    )


def _parse_synthesis(parsed: Any) -> tuple[str, list[ProposedMemoryUpdate]]:
    if not isinstance(parsed, dict):
        raise ValueError("synthesis JSON must be an object")
    narrative = parsed.get("narrativeSummary")
    if not isinstance(narrative, str) or not narrative.strip():
        raise ValueError("narrativeSummary missing")
    updates_raw = parsed.get("proposedMemoryUpdates") or []
    if not isinstance(updates_raw, list):
        raise ValueError("proposedMemoryUpdates must be an array")
    updates: list[ProposedMemoryUpdate] = []
    for item in updates_raw:
        if not isinstance(item, dict):
            continue
        memory_id = item.get("memoryId")
        summary = item.get("summary")
        if not isinstance(memory_id, str) or not memory_id.strip():
            continue
        if not isinstance(summary, str) or not summary.strip():
            continue
        update: ProposedMemoryUpdate = {
            "memoryId": memory_id,
            "summary": summary,
        }
        rationale = item.get("rationale")
        if isinstance(rationale, str) and rationale:
            update["rationale"] = rationale
        updates.append(update)
    return narrative.strip(), updates


async def synthesize_closeout(
    input_data: SynthesizeCloseoutInput,
) -> CloseoutSynthesis:
    """Optionally call create_chat_model for NL summary + memory proposals."""
    if input_data.get("enabled") is False:
        return _skipped("skipped: disabled", input_data.get("summary") or "")

    from gssc_langgraph.llm import create_chat_model, resolve_llm_config

    cfg = resolve_llm_config()
    if not _has_api_key(cfg):
        return _skipped("skipped: no XAI_API_KEY", input_data.get("summary") or "")

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = create_chat_model(temperature=0)
        messages = [
            SystemMessage(
                content=(
                    "You synthesize closeout_review results. Reply with JSON only."
                )
            ),
            HumanMessage(content=_build_prompt(input_data)),
        ]
        if hasattr(llm, "ainvoke"):
            response = await llm.ainvoke(messages)
        else:
            response = llm.invoke(messages)
        text = _response_text(getattr(response, "content", response))
        narrative, updates = _parse_synthesis(_extract_json_object(text))
        return {
            "narrativeSummary": narrative,
            "proposedMemoryUpdates": updates,
            "note": "ok",
        }
    except Exception as err:  # noqa: BLE001 — surface as skipped note
        return _skipped(f"error: {err}", input_data.get("summary") or "")
