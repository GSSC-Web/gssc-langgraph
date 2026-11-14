"""Build and truncate v2 GraphResponse envelopes."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from gssc_langgraph.envelope.budgets import (
    HARD_RESPONSE_BYTES,
    MAX_CHAT_ONELINER_CHARS,
    MAX_FINDING_MESSAGE_CHARS,
    MAX_PR_BODY_CHARS,
    MAX_SUMMARY_CHARS,
    TARGET_RESPONSE_BYTES,
    truncate_chars,
    utf8_size,
)
from gssc_langgraph.envelope.types import (
    ContextRef,
    Digest,
    DomainId,
    EnvelopeFinding,
    Friction,
    GraphResponse,
    GraphVerdict,
    NextAction,
    ToolName,
)

_TOOL_SHORT: dict[ToolName, str] = {
    "GSSC_Software_Dev": "SoftDev",
    "GSSC_Test_Development": "TestDev",
    "GSSC_Closeout_Review": "Closeout",
    "GSSC_Health": "Health",
    "GSSC_Conversation": "Conversation",
}


def finding_code_from_check(check: str, *, input_error: bool = False) -> str:
    if input_error or check in {"scope"} and False:
        return "changeset.required"
    return f"check.{check}"


def normalize_findings(
    raw: list[Mapping[str, Any]] | None,
    *,
    default_code: str = "check.unknown",
    input_error_checks: frozenset[str] | None = None,
) -> list[EnvelopeFinding]:
    """Map domain findings → envelope findings with ``code``."""
    input_checks = input_error_checks or frozenset()
    out: list[EnvelopeFinding] = []
    for item in raw or []:
        check = str(item.get("check") or "")
        explicit = item.get("code")
        if explicit:
            code = str(explicit)
        elif check in input_checks:
            code = "changeset.required"
        elif check:
            code = f"check.{check}"
        else:
            code = default_code
        message = str(item.get("message") or "")
        message, was_trunc = truncate_chars(message, MAX_FINDING_MESSAGE_CHARS)
        finding: EnvelopeFinding = {
            "code": code,
            "severity": item.get("severity") or "info",  # type: ignore[typeddict-item]
            "message": message,
        }
        if was_trunc:
            finding["truncated"] = True
        path = item.get("path")
        if path:
            finding["path"] = str(path)
        uid = item.get("uid")
        if uid:
            finding["uid"] = str(uid)
        out.append(finding)
    return out


def build_digest(
    *,
    tool: ToolName,
    verdict: GraphVerdict,
    label: str,
    findings: list[EnvelopeFinding],
    next_actions: list[NextAction],
    summary: str,
) -> Digest:
    short = _TOOL_SHORT.get(tool, tool)
    n = len(findings)
    label_bit = label.strip() or "—"
    one = f"{short} {verdict} · {label_bit} · {n} finding{'s' if n != 1 else ''}"
    one, _ = truncate_chars(one, MAX_CHAT_ONELINER_CHARS)

    lines = [
        f"## {short} {verdict}",
        f"- Label: `{label_bit}`",
        f"- Summary: {summary}",
    ]
    if findings:
        lines.append("- Findings:")
        for f in findings[:8]:
            lines.append(f"  - `{f['code']}` ({f['severity']}): {f['message']}")
        if len(findings) > 8:
            lines.append(f"  - … +{len(findings) - 8} more")
    if next_actions:
        lines.append("- Next:")
        for a in next_actions[:6]:
            detail = a.get("detail") or ""
            suffix = f" — {detail}" if detail else ""
            lines.append(f"  - [{a['owner']}] {a['action']}{suffix}")
    pr_body = "\n".join(lines)
    pr_body, trunc = truncate_chars(pr_body, MAX_PR_BODY_CHARS)
    digest: Digest = {"chatOneLiner": one, "prBodyMarkdown": pr_body}
    if trunc:
        digest["truncated"] = True
    return digest


def build_friction(
    *,
    verdict: GraphVerdict,
    findings: list[EnvelopeFinding],
    label: str,
    tool: ToolName,
) -> Friction:
    blocking = [f for f in findings if f["severity"] == "error"]
    if verdict == "PASS" and not blocking:
        return {"fileOnKaneo": False, "notes": ""}
    short = _TOOL_SHORT.get(tool, tool)
    title = f"{short} {verdict}"
    if label.strip():
        title = f"{title}: {label.strip()[:80]}"
    notes_parts = [f["message"] for f in blocking[:5]] or [
        f["message"] for f in findings[:3]
    ]
    notes = "; ".join(notes_parts)
    notes, _ = truncate_chars(notes, 500)
    return {
        "fileOnKaneo": True,
        "suggestedTitle": title,
        "notes": notes,
    }


def build_next_actions(
    *,
    verdict: GraphVerdict,
    findings: list[EnvelopeFinding],
    tool: ToolName,
) -> list[NextAction]:
    if verdict == "PASS":
        return [{"action": "continue", "owner": "coordinator", "detail": "No blocking findings"}]
    if verdict == "ERROR":
        detail = findings[0]["message"] if findings else "Fix inputs and retry"
        return [
            {
                "action": "retry_with_fixed_input",
                "owner": "worker",
                "detail": detail,
            }
        ]
    # FAIL
    actions: list[NextAction] = []
    for f in findings:
        if f["severity"] != "error":
            continue
        actions.append(
            {
                "action": "fix_finding",
                "owner": "worker",
                "detail": f"{f['code']}: {f['message']}",
            }
        )
        if len(actions) >= 5:
            break
    if not actions:
        actions.append(
            {
                "action": "address_warnings",
                "owner": "worker",
                "detail": f"{tool} returned FAIL",
            }
        )
    return actions


def context_ref_from_bundle(
    bundle: Mapping[str, Any] | None,
    *,
    include_bodies: bool = False,
) -> tuple[ContextRef | None, dict[str, Any] | None]:
    """Build slim ``contextRef``; optionally keep a body-stripped echo."""
    if not bundle:
        return None, None
    root = str(bundle.get("root") or "")
    skills = list(bundle.get("skills") or [])
    memories = list(bundle.get("memories") or [])
    skill_ids = [str(s.get("id") or "") for s in skills if isinstance(s, dict) and s.get("id")]
    memory_ids = [
        str(m.get("id") or "") for m in memories if isinstance(m, dict) and m.get("id")
    ]
    cache_src = f"{root}|{','.join(skill_ids)}|{','.join(memory_ids)}"
    cache_key = hashlib.sha256(cache_src.encode("utf-8")).hexdigest()[:16]
    ref: ContextRef = {
        "root": root,
        "cacheKey": cache_key,
        "skillIds": skill_ids,
        "memoryIds": memory_ids,
    }
    if include_bodies:
        return ref, dict(bundle)
    # Echo meta only (no content/body) for debugging when needed upstream.
    slim_skills = [
        {k: v for k, v in s.items() if k not in ("content", "body")}
        for s in skills
        if isinstance(s, dict)
    ]
    slim_memories = [
        {k: v for k, v in m.items() if k not in ("content", "body")}
        for m in memories
        if isinstance(m, dict)
    ]
    slim = {
        "root": root,
        "query": bundle.get("query") or "",
        "skills": slim_skills,
        "memories": slim_memories,
        "selected": list(bundle.get("selected") or []),
        "note": bundle.get("note") or "",
    }
    return ref, slim


def apply_response_budgets(response: GraphResponse) -> GraphResponse:
    """Prefer dropping narrative payload fields before verdict/findings."""
    size = utf8_size(response)
    if size <= TARGET_RESPONSE_BYTES:
        return response

    payload = dict(response.get("payload") or {})
    dropped = False
    for key in (
        "narrativeSummary",
        "synthesisNote",
        "gssc5ContextText",
        "proposedMemoryUpdates",
        "specialistNotes",
        "reviewMemory",
    ):
        if key in payload:
            payload.pop(key, None)
            dropped = True
        if utf8_size({**response, "payload": payload}) <= TARGET_RESPONSE_BYTES:
            break

    digest = dict(response["digest"])
    if utf8_size({**response, "payload": payload}) > TARGET_RESPONSE_BYTES:
        pr, trunc = truncate_chars(str(digest.get("prBodyMarkdown") or ""), 400)
        digest["prBodyMarkdown"] = pr
        if trunc:
            digest["truncated"] = True
        dropped = True

    summary, s_trunc = truncate_chars(response["summary"], MAX_SUMMARY_CHARS)
    out: GraphResponse = {
        **response,
        "summary": summary,
        "digest": digest,  # type: ignore[typeddict-item]
        "payload": payload,
    }
    if dropped or s_trunc or utf8_size(out) > TARGET_RESPONSE_BYTES:
        out["truncated"] = True

    # Hard cap: strip payload extras aggressively, then findings messages.
    if utf8_size(out) > HARD_RESPONSE_BYTES:
        keep_keys = {
            "plan",
            "commands",
            "testCases",
            "gaps",
            "checksRun",
            "status",
            "service",
            "checkedAt",
            "reply",
            "steps",
        }
        out["payload"] = {k: v for k, v in out["payload"].items() if k in keep_keys}
        out["truncated"] = True
    if utf8_size(out) > HARD_RESPONSE_BYTES:
        slim_findings: list[EnvelopeFinding] = []
        for f in out["findings"][:12]:
            msg, trunc = truncate_chars(f["message"], 80)
            item: EnvelopeFinding = {
                "code": f["code"],
                "severity": f["severity"],
                "message": msg,
            }
            if trunc:
                item["truncated"] = True
            if f.get("path"):
                item["path"] = f["path"]
            slim_findings.append(item)
        out["findings"] = slim_findings
        digest = dict(out["digest"])
        pr, trunc = truncate_chars(str(digest.get("prBodyMarkdown") or ""), 200)
        digest["prBodyMarkdown"] = pr
        if trunc:
            digest["truncated"] = True
        out["digest"] = digest  # type: ignore[typeddict-item]
        out["truncated"] = True
    if utf8_size(out) > HARD_RESPONSE_BYTES:
        # Last resort: empty payload + minimal digest.
        out["payload"] = {}
        out["digest"] = {
            "chatOneLiner": out["digest"]["chatOneLiner"][:120],
            "prBodyMarkdown": f"## {out['tool']} {out['verdict']}\n(truncated)",
            "truncated": True,
        }
        out["truncated"] = True
    return out


def build_graph_response(
    *,
    tool: ToolName,
    verdict: GraphVerdict,
    summary: str,
    findings: list[EnvelopeFinding] | None = None,
    domains: list[DomainId] | None = None,
    payload: dict[str, Any] | None = None,
    label: str = "",
    next_actions: list[NextAction] | None = None,
    context_ref: ContextRef | None = None,
    friction: Friction | None = None,
) -> GraphResponse:
    findings = list(findings or [])
    summary, _ = truncate_chars(summary, MAX_SUMMARY_CHARS)
    actions = next_actions or build_next_actions(
        verdict=verdict, findings=findings, tool=tool
    )
    digest = build_digest(
        tool=tool,
        verdict=verdict,
        label=label,
        findings=findings,
        next_actions=actions,
        summary=summary,
    )
    fr = friction or build_friction(
        verdict=verdict, findings=findings, label=label, tool=tool
    )
    response: GraphResponse = {
        "schemaVersion": "2",
        "tool": tool,
        "label": label or "",
        "verdict": verdict,
        "summary": summary,
        "findings": findings,
        "nextActions": actions,
        "digest": digest,
        "friction": fr,
        "domains": list(domains or []),
        "payload": dict(payload or {}),
    }
    if context_ref is not None:
        response["contextRef"] = context_ref
    return apply_response_budgets(response)
