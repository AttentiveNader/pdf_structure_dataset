"""Prompts for compact text TOC extraction."""

from __future__ import annotations

TOC_TEXT_FORMAT = """
Output **plain text only** (no JSON, no markdown code fences).

Line 1: document title prefixed with ``# `` (e.g. ``# CREDIT AGREEMENT``).
Then one TOC entry per line. Hierarchy = 2 spaces indent per level.
Each line ends with printed page number after a pipe:

  {title} | {page}

Example:
# CREDIT AGREEMENT

ARTICLE I - Definitions | 1
  Section 1.01 - Defined Terms | 1
ARTICLE II - The Credits | 15
  Section 2.01 - The Commitments | 15
Schedule 1 - Commitments | 42

Rules:
- Use **printed** page numbers from the TOC (not PDF file page indices).
- Keep titles concise; match the document labels.
- Include schedules/exhibits at the correct level.
- If no TOC is visible, output only ``# {title}`` on line 1 and nothing else.
"""


def build_toc_prompt(markdown_content: str, *, max_pages: int) -> str:
    return f"""You are reading the first {max_pages} pages of a credit agreement PDF (Markdown from automated extraction).

Extract the **Table of Contents** as compact plain text for later LLM navigation.

{TOC_TEXT_FORMAT}

--- BEGIN MARKDOWN (first pages) ---

{markdown_content}

--- END MARKDOWN ---
"""
