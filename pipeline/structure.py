import json
import re
from typing import Any, Callable, Optional

from pipeline.prompts import build_structure_prompt

_REQUIRED_NODE_KEYS = frozenset({"title", "level", "children"})


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


def extract_structure(
    markdown_content: str,
    call_llm: Callable[[str], str],
    *,
    max_retries: int = 2,
) -> dict:
    """
    Call the LLM to produce a validated hierarchical structure tree.

    Retries on parse/validation errors by appending a short repair instruction.
    """
    prompt = build_structure_prompt(markdown_content)
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        response = call_llm(prompt)
        raw_json = _strip_json_from_response(response)
        try:
            tree = json.loads(raw_json)
            _validate_node(tree)
            return tree
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt >= max_retries:
                break
            prompt = (
                prompt
                + "\n\nYour previous response was invalid: "
                + str(e)
                + "\nReply again with ONLY a single valid JSON object matching the schema."
            )

    raise ValueError(
        f"Failed to obtain valid structure JSON after {max_retries + 1} attempt(s): {last_error}"
    ) from last_error
