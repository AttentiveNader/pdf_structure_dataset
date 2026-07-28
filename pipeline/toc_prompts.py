"""Prompts for table-of-contents extraction from credit agreement front matter."""

from __future__ import annotations

TOC_JSON_SCHEMA = """
Return a single JSON object with these fields:
- "document_title": string — title of the agreement if visible, else a short label
- "table_of_contents": a tree node with:
  - "title": string (use "Table of Contents" for the TOC root)
  - "level": integer (0 for TOC root)
  - "page": null for the root, otherwise omit or null only for root
  - "children": array of entries in document order

Each child entry must have:
- "title": string — section title as shown in the TOC
- "level": integer >= 1 (1 = article / major division, 2 = section, etc.)
- "page": integer >= 1 — printed page number from the TOC (required for every entry)
- "children": array of nested entries (same shape), possibly empty

Return ONLY valid JSON — no markdown fences, no commentary.
"""

TOC_EXAMPLE = """
{
  "document_title": "CREDIT AGREEMENT",
  "table_of_contents": {
    "title": "Table of Contents",
    "level": 0,
    "page": null,
    "children": [
      {
        "title": "ARTICLE I Definitions",
        "level": 1,
        "page": 1,
        "children": []
      },
      {
        "title": "ARTICLE II The Credits",
        "level": 1,
        "page": 15,
        "children": [
          {
            "title": "Section 2.01 The Commitments",
            "level": 2,
            "page": 15,
            "children": []
          }
        ]
      }
    ]
  }
}
"""


def build_toc_prompt(markdown_content: str, *, max_pages: int) -> str:
    return f"""You are reading the first {max_pages} pages of a credit agreement PDF (Markdown from automated extraction).

Extract the **Table of Contents** (or equivalent index of articles, sections, schedules, exhibits) exactly as listed, including **page numbers** for each line.

Important:
- Markdown layout may be wrong; use the visible TOC text and page numbers from the document.
- If multiple TOC sections exist, combine into one tree in reading order.
- Use printed page numbers shown in the TOC, not PDF file page indices.
- If no TOC appears in this excerpt, return an empty "children" array and set document_title from the cover if present.

Output schema:
{TOC_JSON_SCHEMA}

Example:
{TOC_EXAMPLE}

--- BEGIN MARKDOWN (first pages) ---

{markdown_content}

--- END MARKDOWN ---
"""
