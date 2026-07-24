"""Merge flat structural nodes from batched LLM calls into one tree."""

from __future__ import annotations

from __future__ import annotations

from typing import Any


def _node_key(title: str, level: int) -> tuple[str, int]:
    return (title.strip(), level)


def dedupe_flat_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop consecutive duplicate headings (common at batch overlap)."""
    out: list[dict[str, Any]] = []
    prev_key: tuple[str, int] | None = None
    for node in nodes:
        title = node.get("title", "")
        level = node.get("level", 0)
        if not isinstance(title, str) or not isinstance(level, int):
            continue
        key = _node_key(title, level)
        if key == prev_key:
            continue
        out.append({"title": title.strip(), "level": level})
        prev_key = key
    return out


def flat_nodes_to_tree(
    nodes: list[dict[str, Any]],
    *,
    root_title: str = "Credit Agreement",
) -> dict[str, Any]:
    """Build nested JSON tree from an ordered flat list of title/level nodes."""
    flat = dedupe_flat_nodes(nodes)
    if not flat:
        return {"title": root_title, "level": 0, "children": []}

    min_level = min(n["level"] for n in flat)
    if min_level > 0:
        for n in flat:
            n["level"] = n["level"] - min_level + 1

    root: dict[str, Any] = {"title": root_title, "level": 0, "children": []}
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]

    for item in flat:
        level = item["level"]
        if level <= 0:
            continue
        child: dict[str, Any] = {
            "title": item["title"],
            "level": level,
            "children": [],
        }
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1]
        parent["children"].append(child)
        stack.append((level, child))

    return root
