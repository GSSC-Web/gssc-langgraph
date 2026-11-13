"""List and load gssc5 skill / memory documents from a checkout root."""

from __future__ import annotations

from pathlib import Path

from gssc_langgraph.gssc5.parse import as_bool, as_string, as_string_list, parse_frontmatter
from gssc_langgraph.gssc5.root import agents_dir
from gssc_langgraph.gssc5.types import Gssc5Doc, Gssc5DocMeta


def list_skills(root: str) -> list[Gssc5DocMeta]:
    skills_root = agents_dir(root) / "skills"
    if not skills_root.exists():
        return []

    out: list[Gssc5DocMeta] = []
    for entry in skills_root.iterdir():
        if not entry.is_dir():
            continue
        skill_path = entry / "SKILL.md"
        if not skill_path.exists():
            continue
        raw = skill_path.read_text(encoding="utf-8")
        meta = parse_frontmatter(raw)["meta"]
        doc_id = as_string(meta.get("id")) or entry.name
        item: Gssc5DocMeta = {
            "id": doc_id,
            "kind": "skill",
            "path": str(skill_path),
            "relPath": f"skills/{entry.name}/SKILL.md",
            "name": as_string(meta.get("name")) or doc_id,
            "description": as_string(meta.get("description")),
            "tags": as_string_list(meta.get("tags")),
            "enabled": as_bool(meta.get("enabled"), True),
        }
        out.append(item)
    return sorted(out, key=lambda m: m["id"])


def list_memories(root: str) -> list[Gssc5DocMeta]:
    memories_root = agents_dir(root) / "memories"
    if not memories_root.exists():
        return []

    out: list[Gssc5DocMeta] = []
    for entry in memories_root.iterdir():
        if not entry.is_file() or not entry.name.endswith(".md"):
            continue
        mem_path = entry
        raw = mem_path.read_text(encoding="utf-8")
        meta = parse_frontmatter(raw)["meta"]
        stem = entry.name[:-3] if entry.name.lower().endswith(".md") else entry.name
        doc_id = as_string(meta.get("id")) or stem
        title = as_string(meta.get("title")) or doc_id
        item: Gssc5DocMeta = {
            "id": doc_id,
            "kind": "memory",
            "path": str(mem_path),
            "relPath": f"memories/{entry.name}",
            "title": title,
            "name": title,
            "tags": as_string_list(meta.get("tags")),
            "importance": as_string(meta.get("importance")),
            "enabled": as_bool(meta.get("enabled"), True),
        }
        out.append(item)
    return sorted(out, key=lambda m: m["id"])


def load_doc(meta: Gssc5DocMeta) -> Gssc5Doc:
    raw = Path(meta["path"]).read_text(encoding="utf-8")
    body = parse_frontmatter(raw)["body"]
    doc: Gssc5Doc = {
        **meta,
        "content": raw,
        "body": body,
    }
    return doc


def load_docs(metas: list[Gssc5DocMeta]) -> list[Gssc5Doc]:
    return [load_doc(m) for m in metas]
