"""
Map TOC printed page numbers to PDF file page indices.

Uses a dedicated LLM call on the first N PDF pages (each tagged with its file index)
to find where printed page 1 begins.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Optional

from pipeline.page_mapping_prompts import build_content_start_prompt
from pipeline.retrieve import get_number_of_pages, get_pdf_page_content

DEFAULT_PREVIEW_PAGES = 15


@dataclass
class PageMapping:
    """Convert printed TOC pages to 1-based PDF page indices."""

    toc_page_kind: str  # "printed"
    printed_page_one_pdf_page: int
    offset_pdf_minus_printed: int
    method: str  # "llm_content_start" | "identity"
    confidence: str  # "high" | "medium" | "low"
    notes: str = ""

    def printed_to_pdf(self, printed_page: int) -> int:
        return printed_page + self.offset_pdf_minus_printed

    def pdf_to_printed(self, pdf_page: int) -> int:
        return pdf_page - self.offset_pdf_minus_printed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageMapping":
        return cls(
            toc_page_kind=str(data.get("toc_page_kind", "printed")),
            printed_page_one_pdf_page=int(data["printed_page_one_pdf_page"]),
            offset_pdf_minus_printed=int(data["offset_pdf_minus_printed"]),
            method=str(data.get("method", "manual")),
            confidence=str(data.get("confidence", "medium")),
            notes=str(data.get("notes", "")),
        )


def identity_mapping() -> PageMapping:
    return PageMapping(
        toc_page_kind="printed",
        printed_page_one_pdf_page=1,
        offset_pdf_minus_printed=0,
        method="identity",
        confidence="low",
        notes="LLM content-start detection failed; assuming TOC pages match PDF indices.",
    )


def format_pages_with_pdf_index(pages: list[dict[str, Any]]) -> str:
    """Combine page text with PDF index marker at the end of each page block."""
    blocks: list[str] = []
    for item in pages:
        idx = item["page"]
        text = (item.get("content") or "").strip()
        blocks.append(
            f"===== PDF page index {idx} =====\n{text}\n\n[PDF_PAGE_INDEX: {idx}]"
        )
    return "\n\n".join(blocks)


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


def _parse_content_start_response(data: Any, *, page_count: int) -> PageMapping:
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    pdf_one = data.get("printed_page_one_pdf_page")
    if not isinstance(pdf_one, int) or pdf_one < 1 or pdf_one > page_count:
        raise ValueError(
            f"printed_page_one_pdf_page must be int in 1..{page_count}"
        )
    notes = data.get("notes", "")
    if not isinstance(notes, str):
        notes = str(notes)
    offset = pdf_one - 1
    return PageMapping(
        toc_page_kind="printed",
        printed_page_one_pdf_page=pdf_one,
        offset_pdf_minus_printed=offset,
        method="llm_content_start",
        confidence="medium",
        notes=notes or "LLM content-start detection.",
    )


def calibrate_page_mapping_with_llm(
    pdf_path: str,
    call_llm: Callable[[str], str],
    *,
    preview_pages: int = DEFAULT_PREVIEW_PAGES,
    max_retries: int = 2,
) -> PageMapping:
    """Second LLM call: locate PDF page where printed page 1 begins."""
    total = get_number_of_pages(pdf_path)
    n = min(total, preview_pages)
    if n < 1:
        return identity_mapping()

    pages = get_pdf_page_content(pdf_path, list(range(1, n + 1)))
    pages_block = format_pages_with_pdf_index(pages)
    prompt = build_content_start_prompt(pages_block, preview_pages=n)
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        response = call_llm(prompt)
        try:
            data = json.loads(_strip_json(response))
            return _parse_content_start_response(data, page_count=total)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt >= max_retries:
                break
            prompt = (
                prompt
                + "\n\nInvalid response: "
                + str(e)
                + "\nReply with ONLY valid JSON matching the schema."
            )

    raise ValueError(
        f"Content-start LLM failed after {max_retries + 1} attempt(s): {last_error}"
    ) from last_error


def resolve_page_mapping(
    pdf_path: str,
    call_llm: Callable[[str], str],
    *,
    preview_pages: int = DEFAULT_PREVIEW_PAGES,
) -> PageMapping:
    """Run LLM content-start detection; fall back to identity on failure."""
    try:
        return calibrate_page_mapping_with_llm(
            pdf_path, call_llm, preview_pages=preview_pages
        )
    except ValueError:
        return identity_mapping()


def convert_page_spec_printed_to_pdf(
    pages: str,
    mapping: PageMapping,
) -> str:
    """Convert a pages spec from printed numbers to PDF page numbers."""
    parts: list[str] = []
    for part in pages.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = mapping.printed_to_pdf(int(a.strip()))
            end = mapping.printed_to_pdf(int(b.strip()))
            parts.append(f"{start}-{end}")
        else:
            parts.append(str(mapping.printed_to_pdf(int(part))))
    return ",".join(parts)
