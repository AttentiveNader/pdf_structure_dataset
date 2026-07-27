"""LLM batched rewrite of Markdown to credit-agreement LaTeX."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from pipeline.batch import split_markdown
from pipeline.latex_merge import (
    assemble_full_document,
    merge_latex_bodies,
    strip_latex_fences,
    validate_latex_body_chunk,
)
from pipeline.latex_parse import preview_structural_macros
from pipeline.latex_prompts import (
    build_latex_rewrite_prompt,
    build_latex_rewrite_repair_prompt,
)


def _call_llm_for_latex(
    prompt: str,
    call_llm: Callable[[str], str],
    *,
    max_retries: int,
    allow_document_wrappers: bool = False,
) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        response = call_llm(prompt)
        chunk = strip_latex_fences(response)
        try:
            validate_latex_body_chunk(
                chunk, allow_document_wrappers=allow_document_wrappers
            )
            return chunk
        except ValueError as e:
            last_error = e
            if attempt >= max_retries:
                break
            prompt = build_latex_rewrite_repair_prompt(prompt, str(e))
    raise ValueError(
        f"Failed to obtain valid LaTeX after {max_retries + 1} attempt(s): {last_error}"
    ) from last_error


def rewrite_to_latex(
    markdown_content: str,
    call_llm: Callable[[str], str],
    *,
    max_retries: int = 2,
    batch_chars: Optional[int] = None,
    batch_overlap: int = 800,
    schema_input: str = "latex_schema.tex",
) -> tuple[str, dict[str, Any]]:
    """
    Convert markdown to a full LaTeX document string and rewrite metadata.
    """
    use_batching = batch_chars is not None and len(markdown_content) > batch_chars
    body_chunks: list[str] = []
    batch_meta: list[dict[str, Any]] = []

    if not use_batching:
        prompt = build_latex_rewrite_prompt(
            markdown_content,
            batch_index=0,
            total_batches=1,
            single_shot=True,
        )
        body = _call_llm_for_latex(
            prompt,
            call_llm,
            max_retries=max_retries,
            allow_document_wrappers=True,
        )
        if "\\begin{document}" in body:
            tex = body if "\\input{" in body else assemble_full_document(
                body.split("\\begin{document}", 1)[-1].rsplit("\\end{document}", 1)[0],
                schema_input=schema_input,
            )
        else:
            tex = assemble_full_document(body, schema_input=schema_input)
        meta = {"batched": False, "rewrite_batches": 1}
        return tex, meta

    batches = split_markdown(
        markdown_content,
        batch_chars,
        overlap_chars=batch_overlap,
    )
    accumulated_body = ""

    for batch in batches:
        continuation: list[dict] = []
        if accumulated_body:
            try:
                continuation = preview_structural_macros(accumulated_body)
            except Exception:
                continuation = []

        prompt = build_latex_rewrite_prompt(
            batch.text,
            batch_index=batch.index,
            total_batches=batch.total,
            continuation_macros=continuation,
        )
        chunk = _call_llm_for_latex(
            prompt, call_llm, max_retries=max_retries, allow_document_wrappers=False
        )
        body_chunks.append(chunk)
        accumulated_body = merge_latex_bodies(body_chunks)
        batch_meta.append(
            {
                "index": batch.index,
                "char_start": batch.char_start,
                "char_end": batch.char_end,
            }
        )

    body = merge_latex_bodies(body_chunks)
    tex = assemble_full_document(body, schema_input=schema_input)
    meta = {
        "batched": True,
        "rewrite_batches": len(batches),
        "batch_chars": batch_chars,
        "batch_overlap": batch_overlap,
        "batches": batch_meta,
    }
    return tex, meta
