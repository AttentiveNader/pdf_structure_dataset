"""Merge batched LaTeX body fragments into a full document."""

from __future__ import annotations

import re

_FORBIDDEN_IN_CHUNK = re.compile(
    r"\\documentclass\b|\\usepackage\b|\\input\{latex_schema",
    re.IGNORECASE,
)


def strip_latex_fences(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:latex|tex)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text


def validate_latex_body_chunk(chunk: str, *, allow_document_wrappers: bool = False) -> None:
    if not chunk.strip():
        raise ValueError("empty LaTeX chunk")
    if _FORBIDDEN_IN_CHUNK.search(chunk):
        raise ValueError("chunk must not contain preamble commands (documentclass/usepackage/input)")
    if not allow_document_wrappers:
        if "\\begin{document}" in chunk or "\\end{document}" in chunk:
            raise ValueError("chunk must not contain document environment wrappers")
    depth = 0
    for ch in chunk:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced braces")
    if depth != 0:
        raise ValueError("unbalanced braces")


def _normalize_lines(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.strip().splitlines()]


def dedupe_overlap_lines(prev: str, nxt: str, max_overlap_lines: int = 40) -> str:
    """Drop duplicated lines at batch boundary (from markdown overlap)."""
    prev_lines = _normalize_lines(prev)
    next_lines = _normalize_lines(nxt)
    if not prev_lines or not next_lines:
        return nxt

    max_k = min(max_overlap_lines, len(prev_lines), len(next_lines))
    for k in range(max_k, 0, -1):
        if prev_lines[-k:] == next_lines[:k]:
            return "\n".join(next_lines[k:])
    return nxt


def merge_latex_bodies(chunks: list[str]) -> str:
    if not chunks:
        return ""
    merged = chunks[0].strip()
    for chunk in chunks[1:]:
        piece = chunk.strip()
        if not piece:
            continue
        piece = dedupe_overlap_lines(merged, piece)
        merged = merged.rstrip() + "\n\n" + piece
    return merged.strip()


def assemble_full_document(body: str, *, schema_input: str = "latex_schema.tex") -> str:
    body = body.strip()
    body = strip_latex_fences(body)
    if "\\begin{document}" in body:
        return body
    return (
        f"\\input{{{schema_input}}}\n"
        f"\\begin{{document}}\n"
        f"{body}\n"
        f"\\end{{document}}\n"
    )
