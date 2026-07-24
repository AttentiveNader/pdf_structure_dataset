STRUCTURE_JSON_SCHEMA = """
Each node must be a JSON object with exactly these fields:
- "title": string — the section heading or label as it appears in the document
- "level": integer — depth in the hierarchy (0 = document root, 1 = top-level division, etc.)
- "children": array of nodes (same shape), possibly empty

Return a single root node object (not wrapped in an array).
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
