"""Parse structural macros from generated credit-agreement LaTeX."""

from __future__ import annotations

import re
from typing import Any

from pipeline.merge import flat_nodes_to_tree

STRUCTURAL_MACROS: dict[str, int] = {
    "creditdocumenttitle": 0,
    "creditarticle": 1,
    "creditschedule": 1,
    "creditexhibit": 1,
    "creditsection": 2,
    "creditsubsection": 3,
}

_MACRO_PATTERN = re.compile(
    r"\\(" + "|".join(re.escape(k) for k in STRUCTURAL_MACROS) + r")\s*\{",
    re.MULTILINE,
)


class LatexParseError(ValueError):
    """Raised when LaTeX structure cannot be parsed reliably."""


def _read_braced_argument(text: str, open_brace_index: int) -> tuple[str, int]:
    """Return (argument, index after closing brace) starting at ``{``."""
    if open_brace_index >= len(text) or text[open_brace_index] != "{":
        raise LatexParseError("expected opening brace for macro argument")
    depth = 0
    start = open_brace_index + 1
    i = open_brace_index
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    raise LatexParseError("unbalanced braces in macro argument")


def extract_document_body(tex: str) -> str:
    """Return content between \\begin{document} and \\end{document} if present."""
    begin = tex.find("\\begin{document}")
    end = tex.find("\\end{document}")
    if begin != -1 and end != -1 and end > begin:
        start = begin + len("\\begin{document}")
        return tex[start:end].strip()
    return tex.strip()


def extract_flat_nodes(tex: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Scan *tex* for structural macros.

    Returns (document_title, flat nodes with level >= 1 in document order).
    """
    body = extract_document_body(tex)
    document_title = "Credit Agreement"
    flat: list[dict[str, Any]] = []

    for match in _MACRO_PATTERN.finditer(body):
        name = match.group(1)
        level = STRUCTURAL_MACROS[name]
        brace_idx = match.end() - 1
        try:
            title, _ = _read_braced_argument(body, brace_idx)
        except LatexParseError as e:
            raise LatexParseError(f"failed parsing \\{name}: {e}") from e
        title = title.strip()
        if not title:
            raise LatexParseError(f"empty title for \\{name}")
        if level == 0:
            document_title = title
        else:
            flat.append({"title": title, "level": level})

    return document_title, flat


def parse_latex_structure(tex: str) -> dict[str, Any]:
    """Build nested JSON tree from structural macros in LaTeX."""
    if not tex.strip():
        raise LatexParseError("empty LaTeX document")

    document_title, flat = extract_flat_nodes(tex)
    if not flat and document_title == "Credit Agreement":
        raise LatexParseError("no structural macros found in LaTeX")

    tree = flat_nodes_to_tree(flat, root_title=document_title)
    if tree["level"] != 0:
        raise LatexParseError("invalid root level after merge")
    return tree


def preview_structural_macros(tex: str, limit: int = 8) -> list[dict[str, Any]]:
    """Last N structural nodes for batched rewrite continuation."""
    _, flat = extract_flat_nodes(tex)
    return flat[-limit:]
