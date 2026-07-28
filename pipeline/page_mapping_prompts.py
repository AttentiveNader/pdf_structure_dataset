"""Prompt for LLM detection of where printed page 1 begins in the PDF."""

from __future__ import annotations

CONTENT_START_JSON_SCHEMA = """
Return a single JSON object with:
- "printed_page_one_pdf_page": integer >= 1 — the PDF file page index (1-based) where the
  **main agreement body** begins and printed Arabic page numbering starts at 1
  (after cover, table of contents, and any Roman-numbered front matter).
- "notes": string — one sentence explaining what you saw on that page (e.g. "ARTICLE I with footer 1").

Return ONLY valid JSON — no markdown fences, no commentary.
"""


def build_content_start_prompt(pages_block: str, *, preview_pages: int) -> str:
    return f"""You are analyzing the first {preview_pages} pages of a credit agreement PDF.

Each section is plain text extracted from one PDF page. At the end of each section,
``[PDF_PAGE_INDEX: N]`` is the **actual PDF page number** (1-based file index).

Your task: find the PDF page index where **printed document page 1** begins — the start of
the operative agreement text (typically ARTICLE I or similar), not the cover or TOC.

Clues:
- Front matter often uses Roman numerals or no Arabic "1" yet.
- The body start usually shows Arabic page "1" in the footer or matches the first TOC entry page.
- Use the ``[PDF_PAGE_INDEX: N]`` markers as your answer source (not guessed page numbers from footers alone).

{CONTENT_START_JSON_SCHEMA}

--- BEGIN PAGES ---

{pages_block}

--- END PAGES ---
"""
