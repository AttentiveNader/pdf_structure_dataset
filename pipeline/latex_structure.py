"""Extract structure from LaTeX with LLM fallback."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from pipeline.latex_parse import LatexParseError, parse_latex_structure
from pipeline.structure import extract_structure


def extract_structure_from_latex(
    tex: str,
    call_llm: Callable[[str], str],
    markdown_fallback: str,
    *,
    max_retries: int = 2,
    batch_chars: Optional[int] = None,
    batch_overlap: int = 800,
    root_title: str = "Credit Agreement",
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """
    Returns (structure_tree, structure_source, extraction_meta).

    structure_source is ``latex_parse`` or ``llm_fallback``.
    """
    try:
        tree = parse_latex_structure(tex)
        return tree, "latex_parse", {"batched": False, "source": "latex_parse"}
    except LatexParseError:
        source = tex.strip() or markdown_fallback
        tree, meta = extract_structure(
            source,
            call_llm,
            max_retries=max_retries,
            batch_chars=batch_chars,
            batch_overlap=batch_overlap,
            root_title=root_title,
            return_meta=True,
        )
        meta = dict(meta)
        meta["source"] = "llm_fallback"
        return tree, "llm_fallback", meta
