"""Prompts for LLM credit-agreement Markdown → LaTeX rewrite."""

from __future__ import annotations

LATEX_MACRO_RULES = """
Use ONLY these structural macros for headings (required for parsing):
- \\creditdocumenttitle{...} — document title (once, at start)
- \\creditarticle{...} — ARTICLE divisions (level 1)
- \\creditsection{...} — sections (level 2)
- \\creditsubsection{...} — subsections (level 3)
- \\creditschedule{...} — schedules (level 1)
- \\creditexhibit{...} — exhibits (level 1)

Spacing / layout macros (mirror PDF spacing; not in structure tree):
- \\creditvspace{12pt} — vertical gap between blocks
- \\begin{creditindent}{24pt} ... \\end{creditindent} — indented blocks
- \\begin{enumerate} / \\begin{itemize} with numbered clauses

Rules:
- Do NOT emit \\documentclass, \\usepackage, or \\input — preamble is added automatically.
- Do NOT emit \\begin{document} or \\end{document} unless this is the only batch for the full doc.
- Escape LaTeX special characters in body text: # $ % & _ { } ~ ^ \\
- Preserve hierarchy: every ARTICLE/Schedule/Exhibit/Section in the source must use the matching macro.
- Match visual spacing from the PDF using \\creditvspace and creditindent where appropriate.
"""

LATEX_EXAMPLE = r"""
\creditdocumenttitle{CREDIT AGREEMENT}
\creditarticle{ARTICLE I DEFINITIONS}
\creditsection{Section 1.01 Defined Terms}
\creditvspace{6pt}
Body text for defined terms\ldots
\begin{enumerate}
  \item ``Agreement'' means this Credit Agreement\ldots
\end{enumerate}
"""


def _format_macro_continuation(macros: list[dict]) -> str:
    if not macros:
        return ""
    lines = [f'- level {m["level"]}: {m["title"]}' for m in macros]
    return (
        "Structural macros already written (do not repeat unless this excerpt repeats them):\n"
        + "\n".join(lines)
        + "\n\n"
    )


def build_latex_rewrite_prompt(
    markdown_chunk: str,
    *,
    batch_index: int,
    total_batches: int,
    continuation_macros: list[dict] | None = None,
    single_shot: bool = False,
) -> str:
    """Prompt to rewrite a markdown excerpt into LaTeX body content."""
    cont = _format_macro_continuation(continuation_macros or [])
    batch_note = (
        "This is the complete document."
        if single_shot
        else f"This is batch {batch_index + 1} of {total_batches}. Output ONLY the LaTeX body fragment for this excerpt."
    )

    return f"""You are converting a credit agreement from Markdown (automated PDF extraction) into LaTeX.

{batch_note}

The Markdown may have wrong headings or layout — infer the true legal structure and spacing from the text.

{LATEX_MACRO_RULES}

Example fragment:
{LATEX_EXAMPLE}

{cont}Return ONLY valid LaTeX (no markdown fences, no commentary).

--- BEGIN MARKDOWN ---

{markdown_chunk}

--- END MARKDOWN ---
"""


def build_latex_rewrite_repair_prompt(base_prompt: str, error: str) -> str:
    return (
        base_prompt
        + "\n\nYour previous LaTeX was invalid: "
        + error
        + "\nReply again with ONLY valid LaTeX body content matching the macro rules."
    )
