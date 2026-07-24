"""Prompt templates for credit agreement structure extraction."""

from __future__ import annotations

STRUCTURE_JSON_SCHEMA = """
Each node must be a JSON object with exactly these fields:
- "title": string — the section heading or label as it appears in the document
- "level": integer — depth in the hierarchy (0 = document root, 1 = top-level division, etc.)
- "children": array of nodes (same shape), possibly empty

Return a single root node object (not wrapped in an array).
"""

CHUNK_NODES_JSON_SCHEMA = """
Return a JSON object with one field:
- "nodes": array of objects, each with "title" (string) and "level" (integer >= 1)

List structural headings visible in THIS chunk only, in document order.
Use level 1 for top divisions (e.g. ARTICLE), 2 for sections, 3 for subsections, etc.
Do not include a document root node. If no headings appear in this chunk, return {"nodes": []}.
"""

STRUCTURE_EXAMPLE = """
{
  "title": "Credit Agreement",
  "level": 0,
  "children": [
    {
      "title": "Article I - Definitions",
      "level": 1,
      "children": [
        {
          "title": "Section 1.01 - Defined Terms",
          "level": 2,
          "children": []
        }
      ]
    }
  ]
}
"""


def build_structure_prompt(markdown_content: str) -> str:
    """Build the prompt for LLM structure extraction from Docling markdown."""
    return f"""You are analyzing a credit agreement PDF that has been converted to Markdown for reference.

Your task: infer the document's hierarchical structure (articles, sections, subsections, schedules, exhibits, etc.) and return it as a JSON tree.

Important:
- The Markdown below is an automated extraction. Headings, nesting, and formatting may be wrong or incomplete.
- Do not copy the Markdown outline blindly. Use the actual legal structure visible in the text (e.g. "ARTICLE I", "Section 1.01", numbered clauses).
- Include all major structural divisions you can identify. Use concise titles that match or summarize the document labels.
- Return ONLY valid JSON — no markdown fences, no commentary before or after the JSON.

Output schema:
{STRUCTURE_JSON_SCHEMA}

Example shape (your tree should reflect the actual document):
{STRUCTURE_EXAMPLE}

--- BEGIN MARKDOWN (reference only; may be inaccurate) ---

{markdown_content}

--- END MARKDOWN ---
"""


def _format_continuation(nodes: list[dict]) -> str:
    if not nodes:
        return ""
    lines = [f'- level {n["level"]}: {n["title"]}' for n in nodes[-8:]]
    return (
        "The previous chunk ended with these structural headings (for continuity only):\n"
        + "\n".join(lines)
        + "\n\n"
    )


def build_chunk_structure_prompt(
    markdown_chunk: str,
    *,
    batch_index: int,
    total_batches: int,
    continuation_nodes: list[dict] | None = None,
) -> str:
    """Prompt for one markdown batch of a long document."""
    cont = _format_continuation(continuation_nodes or [])
    return f"""You are analyzing a credit agreement PDF (Markdown excerpt). This is batch {batch_index + 1} of {total_batches}.

Your task: list every structural heading (articles, sections, subsections, schedules, exhibits, etc.) that appears in THIS excerpt only.

Important:
- The Markdown is an automated extraction; headings may be wrong. Infer legal structure from labels in the text.
- Do not copy the Markdown outline blindly.
- Do not repeat headings from the continuation list unless they appear again in this excerpt.
- Return ONLY valid JSON — no markdown fences, no commentary.

Output schema:
{CHUNK_NODES_JSON_SCHEMA}

{cont}--- BEGIN MARKDOWN EXCERPT ---

{markdown_chunk}

--- END MARKDOWN EXCERPT ---
"""
