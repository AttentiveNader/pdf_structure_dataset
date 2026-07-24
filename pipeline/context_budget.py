"""
Map model context windows to markdown batch sizes (characters).

gpt-oss (20b/120b) natively supports up to 131,072 tokens (~128k). The reference
openai/gpt-oss chat CLI defaults to 8,192 tokens unless you pass -c/--context;
size batches to the context you actually configure at inference time.
"""

from __future__ import annotations

# OpenAI gpt-oss model card / HF config
GPT_OSS_CONTEXT_TOKENS = 131_072
GPT_OSS_REFERENCE_CLI_DEFAULT_TOKENS = 8_192

# Chunk prompt (instructions + schema + continuation) — not the markdown body
PROMPT_OVERHEAD_TOKENS = 2_800
# Room for {"nodes": [...]} JSON in the response
OUTPUT_RESERVE_TOKENS = 4_096
# Legal/markdown text: ~3.5–4 chars/token; use a conservative estimate
CHARS_PER_TOKEN = 3.6


def batch_chars_for_context(context_tokens: int) -> int:
    """
    Max markdown characters to put in one batched LLM call.

    Reserves space for the fixed prompt template and the structured JSON output
    so input + output stay within ``context_tokens``.
    """
    if context_tokens <= 0:
        raise ValueError("context_tokens must be positive")

    content_tokens = (
        context_tokens - PROMPT_OVERHEAD_TOKENS - OUTPUT_RESERVE_TOKENS
    )
    if content_tokens < 512:
        raise ValueError(
            f"context_tokens={context_tokens} is too small; need at least "
            f"{PROMPT_OVERHEAD_TOKENS + OUTPUT_RESERVE_TOKENS + 512}"
        )
    return int(content_tokens * CHARS_PER_TOKEN)


def batch_overlap_for_batch_chars(batch_chars: int) -> int:
    """Overlap between consecutive batches (~4%, clamped)."""
    return max(800, min(4_000, batch_chars // 25))


def resolve_batch_settings(
    *,
    batch_chars: int | None,
    context_tokens: int | None,
) -> tuple[int | None, int]:
    """
    Return (batch_chars, batch_overlap).

    batch_chars None means no batching (single full-document call).
    """
    if batch_chars is not None:
        if batch_chars == 0:
            return None, 800
        return batch_chars, batch_overlap_for_batch_chars(batch_chars)

    tokens = context_tokens if context_tokens is not None else GPT_OSS_CONTEXT_TOKENS
    chars = batch_chars_for_context(tokens)
    return chars, batch_overlap_for_batch_chars(chars)
