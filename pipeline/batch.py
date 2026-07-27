"""Split long Markdown into LLM-sized batches."""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.context_budget import batch_overlap_for_batch_chars

_DEFAULT_OVERLAP_CHARS = 800


@dataclass(frozen=True)
class MarkdownBatch:
    index: int
    total: int
    text: str
    char_start: int
    char_end: int


def split_markdown(
    markdown: str,
    max_chars: int,
    *,
    overlap_chars: int | None = _DEFAULT_OVERLAP_CHARS,
) -> list[MarkdownBatch]:
    """
    Split markdown into batches at most max_chars long.

    Prefers breaks at blank lines; adds overlap between consecutive batches
    so section headings near boundaries are less likely to be missed.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars is None:
        overlap_chars = batch_overlap_for_batch_chars(max_chars)
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be non-negative")
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars")

    text = markdown.strip()
    if not text:
        return [MarkdownBatch(0, 1, "", 0, 0)]

    if len(text) <= max_chars:
        return [MarkdownBatch(0, 1, text, 0, len(text))]

    batches: list[MarkdownBatch] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            window = text[start:end]
            break_at = window.rfind("\n\n")
            if break_at > max_chars // 3:
                end = start + break_at
            else:
                break_at = window.rfind("\n")
                if break_at > max_chars // 3:
                    end = start + break_at

        chunk = text[start:end].strip()
        if chunk:
            batches.append(
                MarkdownBatch(
                    index=len(batches),
                    total=0,
                    text=chunk,
                    char_start=start,
                    char_end=end,
                )
            )

        if end >= n:
            break
        next_start = end - overlap_chars
        if next_start <= start:
            next_start = end
        start = next_start

    total = len(batches)
    return [
        MarkdownBatch(b.index, total, b.text, b.char_start, b.char_end) for b in batches
    ]
