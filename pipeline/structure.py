from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional, Tuple, Union

from pipeline.batch import MarkdownBatch, split_markdown
from pipeline.context_budget import GPT_OSS_CONTEXT_TOKENS, batch_chars_for_context
from pipeline.merge import flat_nodes_to_tree
from pipeline.prompts import build_chunk_structure_prompt, build_structure_prompt

_REQUIRED_NODE_KEYS = frozenset({"title", "level", "children"})
_DEFAULT_BATCH_CHARS = batch_chars_for_context(GPT_OSS_CONTEXT_TOKENS)


def _strip_json_from_response(text: str) -> str:
    """Extract a JSON object from LLM output (handles fenced code blocks)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _validate_node(node: Any, path: str = "root") -> None:
    if not isinstance(node, dict):
        raise ValueError(f"{path}: expected object, got {type(node).__name__}")
    missing = _REQUIRED_NODE_KEYS - set(node.keys())
    if missing:
        raise ValueError(f"{path}: missing keys {sorted(missing)}")
    if not isinstance(node["title"], str):
        raise ValueError(f"{path}.title: expected string")
    if not isinstance(node["level"], int):
        raise ValueError(f"{path}.level: expected integer")
    if not isinstance(node["children"], list):
        raise ValueError(f"{path}.children: expected array")
    for i, child in enumerate(node["children"]):
        _validate_node(child, f"{path}.children[{i}]")


def _validate_flat_nodes(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object with 'nodes' array")
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("'nodes' must be an array")
    out: list[dict[str, Any]] = []
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"nodes[{i}]: expected object")
        if "title" not in node or "level" not in node:
            raise ValueError(f"nodes[{i}]: missing title or level")
        if not isinstance(node["title"], str):
            raise ValueError(f"nodes[{i}].title: expected string")
        if not isinstance(node["level"], int) or node["level"] < 1:
            raise ValueError(f"nodes[{i}].level: expected integer >= 1")
        out.append({"title": node["title"].strip(), "level": node["level"]})
    return out


def _call_llm_for_json(
    prompt: str,
    call_llm: Callable[[str], str],
    *,
    max_retries: int,
    validate,
) -> Any:
    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        response = call_llm(prompt)
        raw_json = _strip_json_from_response(response)
        try:
            data = json.loads(raw_json)
            validate(data)
            return data
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt >= max_retries:
                break
            prompt = (
                prompt
                + "\n\nYour previous response was invalid: "
                + str(e)
                + "\nReply again with ONLY valid JSON matching the schema."
            )
    raise ValueError(
        f"Failed to obtain valid JSON after {max_retries + 1} attempt(s): {last_error}"
    ) from last_error


def _extract_structure_single(
    markdown_content: str,
    call_llm: Callable[[str], str],
    *,
    max_retries: int,
) -> dict:
    prompt = build_structure_prompt(markdown_content)

    def validate(data: Any) -> None:
        _validate_node(data)

    tree = _call_llm_for_json(
        prompt, call_llm, max_retries=max_retries, validate=validate
    )
    return tree


def _extract_structure_batched(
    markdown_content: str,
    call_llm: Callable[[str], str],
    *,
    max_retries: int,
    batch_chars: int,
    batch_overlap: int,
    root_title: str,
) -> tuple[dict, dict]:
    batches = split_markdown(
        markdown_content,
        batch_chars,
        overlap_chars=batch_overlap,
    )
    all_nodes: list[dict[str, Any]] = []
    batch_meta: list[dict[str, Any]] = []

    for batch in batches:
        prompt = build_chunk_structure_prompt(
            batch.text,
            batch_index=batch.index,
            total_batches=batch.total,
            continuation_nodes=all_nodes,
        )

        def validate(data: Any) -> None:
            _validate_flat_nodes(data)

        payload = _call_llm_for_json(
            prompt, call_llm, max_retries=max_retries, validate=validate
        )
        nodes = _validate_flat_nodes(payload)
        all_nodes.extend(nodes)
        batch_meta.append(
            {
                "index": batch.index,
                "char_start": batch.char_start,
                "char_end": batch.char_end,
                "nodes_found": len(nodes),
            }
        )

    tree = flat_nodes_to_tree(all_nodes, root_title=root_title)
    _validate_node(tree)
    meta = {
        "batched": True,
        "batch_count": len(batches),
        "batch_chars": batch_chars,
        "batch_overlap": batch_overlap,
        "batches": batch_meta,
        "flat_node_count": len(all_nodes),
    }
    return tree, meta


def extract_structure(
    markdown_content: str,
    call_llm: Callable[[str], str],
    *,
    max_retries: int = 2,
    batch_chars: Optional[int] = _DEFAULT_BATCH_CHARS,
    batch_overlap: int = 800,
    root_title: str = "Credit Agreement",
    return_meta: bool = False,
) -> Union[dict, Tuple[dict, dict]]:
    """
    Call the LLM to produce a validated hierarchical structure tree.

    Long documents are split into markdown batches; partial node lists are merged
    into one tree. Set batch_chars to None to send the full document in one call.
    """
    use_batching = batch_chars is not None and len(markdown_content) > batch_chars

    if not use_batching:
        tree = _extract_structure_single(
            markdown_content, call_llm, max_retries=max_retries
        )
        meta = {"batched": False}
        if return_meta:
            return tree, meta
        return tree

    tree, meta = _extract_structure_batched(
        markdown_content,
        call_llm,
        max_retries=max_retries,
        batch_chars=batch_chars,
        batch_overlap=batch_overlap,
        root_title=root_title,
    )
    if return_meta:
        return tree, meta
    return tree
