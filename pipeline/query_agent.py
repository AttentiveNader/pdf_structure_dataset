"""Agent loop: LLM + PageIndex-style retrieval tools."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from pipeline.document_store import CreditDocumentStore
from pipeline.query_prompts import build_agent_turn
from pipeline.retrieve import (
    get_document_metadata,
    get_document_structure_json,
    get_page_content_json,
)


@dataclass
class QueryResult:
    answer: str
    steps: list[dict[str, Any]] = field(default_factory=list)


def _strip_json(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def _parse_action(response: str) -> dict[str, Any]:
    raw = _strip_json(response)
    data = json.loads(raw)
    if not isinstance(data, dict) or "action" not in data:
        raise ValueError("JSON must include 'action'")
    action = data["action"]
    if action == "answer":
        if not isinstance(data.get("text"), str):
            raise ValueError("answer requires 'text' string")
    elif action == "tool":
        if data.get("name") not in (
            "get_document",
            "get_document_structure",
            "get_page_content",
        ):
            raise ValueError(f"unknown tool: {data.get('name')}")
    else:
        raise ValueError(f"unknown action: {action}")
    return data


def _dispatch_tool(store: CreditDocumentStore, name: str, arguments: dict[str, Any]) -> str:
    info = store.as_doc_info()
    if name == "get_document":
        return get_document_metadata(info)
    if name == "get_document_structure":
        return get_document_structure_json(info)
    if name == "get_page_content":
        pages = arguments.get("pages", "")
        if not pages:
            return json.dumps({"error": "missing pages argument"})
        return get_page_content_json(info, str(pages))
    return json.dumps({"error": f"unknown tool {name}"})


def run_query(
    store: CreditDocumentStore,
    query: str,
    call_llm: Callable[[str], str],
    *,
    max_steps: int = 12,
) -> QueryResult:
    """Run multi-step TOC-guided QA with ``call_llm(prompt) -> str``."""
    history: list[dict[str, str]] = []
    steps: list[dict[str, Any]] = []
    last_error: Optional[Exception] = None

    for step in range(max_steps):
        prompt = build_agent_turn(query=query, history=history)
        response = call_llm(prompt)
        try:
            action = _parse_action(response)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            history.append(
                {
                    "assistant": response,
                    "tool_result": f"Invalid JSON action: {e}. Reply with a single valid JSON object.",
                }
            )
            continue

        step_record: dict[str, Any] = {"step": step + 1, "action": action}
        steps.append(step_record)

        if action["action"] == "answer":
            return QueryResult(answer=action["text"], steps=steps)

        tool_name = action["name"]
        arguments = action.get("arguments") or {}
        tool_result = _dispatch_tool(store, tool_name, arguments)
        step_record["tool_result"] = tool_result
        history.append({"assistant": response, "tool_result": tool_result})

    raise RuntimeError(
        f"Agent did not answer within {max_steps} steps. Last error: {last_error}"
    )
