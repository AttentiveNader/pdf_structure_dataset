"""Extract table of contents (with page numbers) via LLM."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional

from pipeline.toc_prompts import build_toc_prompt

_TOC_NODE_KEYS = frozenset({"title", "level", "page", "children"})


def _strip_json_from_response(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _validate_toc_node(node: Any, path: str, *, is_root: bool) -> None:
    if not isinstance(node, dict):
        raise ValueError(f"{path}: expected object")
    missing = _TOC_NODE_KEYS - set(node.keys())
    if missing:
        raise ValueError(f"{path}: missing keys {sorted(missing)}")
    if not isinstance(node["title"], str):
        raise ValueError(f"{path}.title: expected string")
    if not isinstance(node["level"], int):
        raise ValueError(f"{path}.level: expected integer")
    if not isinstance(node["children"], list):
        raise ValueError(f"{path}.children: expected array")

    page = node["page"]
    if is_root:
        if page is not None and not isinstance(page, int):
            raise ValueError(f"{path}.page: root must have null page")
    else:
        if not isinstance(page, int) or page < 1:
            raise ValueError(f"{path}.page: expected integer >= 1")

    for i, child in enumerate(node["children"]):
        _validate_toc_node(child, f"{path}.children[{i}]", is_root=False)


def _validate_toc_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("expected top-level JSON object")
    if "document_title" not in data or "table_of_contents" not in data:
        raise ValueError("missing document_title or table_of_contents")
    if not isinstance(data["document_title"], str):
        raise ValueError("document_title must be a string")
    toc = data["table_of_contents"]
    _validate_toc_node(toc, "table_of_contents", is_root=True)
    return data


def resolve_page_mapping_for_document(
    pdf_path: str,
    *,
    table_of_contents: dict[str, Any],
    page_mapping_hint: Any = None,
) -> "PageMapping":
    from pipeline.page_mapping import resolve_page_mapping

    del table_of_contents
    return resolve_page_mapping(pdf_path, page_mapping_hint=page_mapping_hint)


def extract_toc(
    markdown_content: str,
    call_llm: Callable[[str], str],
    *,
    max_pages: int = 20,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Return parsed TOC JSON from front-matter markdown."""
    prompt = build_toc_prompt(markdown_content, max_pages=max_pages)
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        response = call_llm(prompt)
        raw = _strip_json_from_response(response)
        try:
            data = json.loads(raw)
            return _validate_toc_payload(data)
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
        f"Failed to obtain valid TOC JSON after {max_retries + 1} attempt(s): {last_error}"
    ) from last_error
