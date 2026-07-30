"""Extract table of contents as compact text via LLM."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from pipeline.toc_prompts import build_toc_prompt

if TYPE_CHECKING:
    from pipeline.page_mapping import PageMapping

_ENTRY_RE = re.compile(r"^(\s*)(.+?)\s*\|\s*(\d+)\s*$")


def _strip_fences(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:markdown|text|md)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text


def parse_document_title(toc_text: str) -> str:
    for line in toc_text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return "Credit Agreement"


def validate_toc_text(toc_text: str) -> str:
    text = toc_text.strip()
    if not text:
        raise ValueError("empty TOC text")
    if not any(line.strip().startswith("# ") for line in text.splitlines()):
        raise ValueError("first heading line must be '# Document Title'")
    entries = [ln for ln in text.splitlines() if _ENTRY_RE.match(ln)]
    if not entries and len(text.splitlines()) > 1:
        raise ValueError("no TOC lines matching '{title} | {page}'")
    return text


def apply_page_mapping_to_toc_text(toc_text: str, mapping: "PageMapping") -> str:
    """Rewrite ``| {printed_page}`` suffixes to PDF file page indices."""
    out_lines: list[str] = []
    for line in toc_text.splitlines():
        match = _ENTRY_RE.match(line)
        if match:
            indent, title, page_s = match.group(1), match.group(2), match.group(3)
            pdf_page = mapping.printed_to_pdf(int(page_s))
            out_lines.append(f"{indent}{title} | {pdf_page}")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def extract_toc(
    markdown_content: str,
    call_llm: Callable[[str], str],
    *,
    max_pages: int = 20,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Return ``document_title`` and compact ``toc_text``."""
    prompt = build_toc_prompt(markdown_content, max_pages=max_pages)
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        response = call_llm(prompt)
        raw = _strip_fences(response)
        try:
            toc_text = validate_toc_text(raw)
            return {
                "document_title": parse_document_title(toc_text),
                "toc_text": toc_text,
            }
        except ValueError as e:
            last_error = e
            if attempt >= max_retries:
                break
            prompt = (
                prompt
                + "\n\nYour previous response was invalid: "
                + str(e)
                + "\nReply with plain text only, matching the format above."
            )

    raise ValueError(
        f"Failed to obtain valid TOC text after {max_retries + 1} attempt(s): {last_error}"
    ) from last_error


def resolve_page_mapping_for_document(
    pdf_path: str,
    call_llm: Callable[[str], str],
    *,
    preview_pages: int = 15,
) -> "PageMapping":
    from pipeline.page_mapping import resolve_page_mapping

    return resolve_page_mapping(pdf_path, call_llm, preview_pages=preview_pages)
