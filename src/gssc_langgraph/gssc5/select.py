"""Select and load relevant skills + memories via keyword scoring."""

from __future__ import annotations

import re
from typing import Any

from gssc_langgraph.gssc5.catalog import list_memories, list_skills, load_doc
from gssc_langgraph.gssc5.types import (
    Gssc5Doc,
    Gssc5DocMeta,
    Gssc5ScoredDoc,
    Gssc5SelectedEntry,
    SelectGssc5Options,
)

_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "of",
        "for",
        "in",
        "on",
        "with",
        "by",
        "is",
        "are",
        "be",
        "as",
        "at",
        "from",
        "this",
        "that",
        "it",
        "its",
        "into",
        "via",
        "use",
        "using",
        "when",
        "before",
        "after",
        "each",
        "per",
        "not",
        "no",
        "vs",
    }
)


def tokenize(text: str) -> list[str]:
    """Tokenize a query for keyword overlap scoring."""
    return [
        t
        for t in (part.strip() for part in re.split(r"[^a-z0-9_@.-]+", text.lower()))
        if len(t) >= 2 and t not in _STOP
    ]


def _haystack(meta: Gssc5DocMeta) -> str:
    parts = [
        meta.get("id"),
        meta.get("name"),
        meta.get("title"),
        meta.get("description"),
        " ".join(meta.get("tags") or []),
        meta.get("importance"),
        meta.get("relPath"),
    ]
    return " ".join(p for p in parts if p).lower()


def score_doc(
    meta: Gssc5DocMeta,
    tokens: list[str],
    prefer_ids: set[str],
) -> Gssc5ScoredDoc:
    reasons: list[str] = []
    score = 0
    hay = _haystack(meta)

    if meta["id"] in prefer_ids:
        score += 10
        reasons.append(f"prefer:{meta['id']}")

    if meta.get("importance") == "high":
        score += 1
        reasons.append("importance:high")

    for token in tokens:
        if meta["id"] == token or token in meta["id"]:
            score += 5
            reasons.append(f"id:{token}")
            continue
        tags = meta.get("tags") or []
        if any(
            t.lower() == token or token in t.lower()
            for t in tags
        ):
            score += 4
            reasons.append(f"tag:{token}")
            continue
        if token in hay:
            score += 2
            reasons.append(f"text:{token}")

    # Lightweight domain heuristics for common gssc5 terms.
    if "closeout" in tokens and "closeout" in meta["id"]:
        score += 3
        reasons.append("heuristic:closeout")
    if (
        "backend" in tokens or "elysia" in tokens or "prisma" in tokens
    ) and meta["id"] == "backend-arch":
        score += 4
        reasons.append("heuristic:backend")
    if (
        "public" in tokens or "angular" in tokens or "frontend" in tokens
    ) and meta["id"] in ("public-arch", "members-arch"):
        score += 3
        reasons.append("heuristic:frontend")
    if (
        "kaneo" in tokens or "ticket" in tokens or "defect" in tokens
    ) and meta["id"].startswith("kaneo-"):
        score += 4
        reasons.append("heuristic:kaneo")

    stub: Gssc5Doc = {
        **meta,
        "content": "",
        "body": "",
    }
    return {
        "doc": stub,
        "score": score,
        "reasons": list(dict.fromkeys(reasons)),
    }


def _pick(
    scored: list[Gssc5ScoredDoc],
    required_ids: list[str],
    max_n: int,
    min_score: float,
    catalog: dict[str, Gssc5DocMeta],
) -> list[Gssc5ScoredDoc]:
    chosen: dict[str, Gssc5ScoredDoc] = {}

    for doc_id in required_ids:
        meta = catalog.get(doc_id)
        if not meta or not meta.get("enabled", True):
            continue
        existing = next((s for s in scored if s["doc"]["id"] == doc_id), None)
        if existing is not None:
            chosen[doc_id] = existing
        else:
            stub: Gssc5Doc = {**meta, "content": "", "body": ""}
            chosen[doc_id] = {
                "doc": stub,
                "score": 100,
                "reasons": [f"require:{doc_id}"],
            }

    ranked = sorted(
        (
            s
            for s in scored
            if s["doc"].get("enabled", True) and s["score"] >= min_score
        ),
        key=lambda s: (-s["score"], s["doc"]["id"]),
    )

    for s in ranked:
        if len(chosen) >= max_n:
            break
        if s["doc"]["id"] not in chosen:
            chosen[s["doc"]["id"]] = s

    return sorted(
        chosen.values(),
        key=lambda s: (-s["score"], s["doc"]["id"]),
    )


def select_and_load(
    root: str,
    options: SelectGssc5Options | None = None,
) -> dict[str, Any]:
    """Select and load relevant skills + memories for a turn/task.

    Practical keyword + preference scoring (no embedding model required).
    """
    opts: SelectGssc5Options = options or {}
    tokens = tokenize(opts.get("query") or "")
    max_skills = opts.get("maxSkills", 3)
    max_memories = opts.get("maxMemories", 2)
    min_score = opts.get("minScore", 1)

    skill_metas = [m for m in list_skills(root) if m.get("enabled", True)]
    memory_metas = [m for m in list_memories(root) if m.get("enabled", True)]

    prefer_skills = set(opts.get("preferSkills") or [])
    prefer_memories = set(opts.get("preferMemories") or [])

    scored_skills = [score_doc(m, tokens, prefer_skills) for m in skill_metas]
    scored_memories = [score_doc(m, tokens, prefer_memories) for m in memory_metas]

    skill_catalog = {m["id"]: m for m in skill_metas}
    memory_catalog = {m["id"]: m for m in memory_metas}

    picked_skills = _pick(
        scored_skills,
        list(opts.get("requireSkills") or []),
        max_skills,
        min_score,
        skill_catalog,
    )
    picked_memories = _pick(
        scored_memories,
        list(opts.get("requireMemories") or []),
        max_memories,
        min_score,
        memory_catalog,
    )

    skills = [load_doc(skill_catalog[s["doc"]["id"]]) for s in picked_skills]
    memories = [load_doc(memory_catalog[s["doc"]["id"]]) for s in picked_memories]

    selected: list[Gssc5SelectedEntry] = [
        *[
            {
                "id": s["doc"]["id"],
                "kind": "skill",
                "score": s["score"],
                "reasons": s["reasons"],
            }
            for s in picked_skills
        ],
        *[
            {
                "id": s["doc"]["id"],
                "kind": "memory",
                "score": s["score"],
                "reasons": s["reasons"],
            }
            for s in picked_memories
        ],
    ]

    return {
        "skills": skills,
        "memories": memories,
        "selected": selected,
    }
