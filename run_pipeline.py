#!/usr/bin/env python3
"""
Process credit agreement PDFs: Docling -> Markdown -> LLM -> JSON structure.

Plug in your LLM by implementing call_llm below or passing --module path.to:call_llm.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.extract import extract_pdf_to_markdown
from pipeline.context_budget import (
    GPT_OSS_CONTEXT_TOKENS,
    GPT_OSS_REFERENCE_CLI_DEFAULT_TOKENS,
    batch_chars_for_context,
    resolve_batch_settings,
)
from pipeline.structure import extract_structure
DEFAULT_PDF_DIR = ROOT / "pdfs"
DEFAULT_OUTPUT_DIR = ROOT / "output"


def call_llm(prompt: str) -> str:
    """
    Replace this with your LLM API call.

    Must accept a prompt string and return the model's text response.
    """
    raise NotImplementedError(
        "Implement call_llm(prompt: str) -> str in run_pipeline.py "
        "or use --llm module.path:callable"
    )


def _load_callable(spec: str):
    if ":" not in spec:
        raise argparse.ArgumentTypeError(
            "Expected MODULE:CALLABLE, e.g. my_llm.client:call_llm"
        )
    module_name, attr = spec.split(":", 1)
    module = importlib.import_module(module_name)
    fn = getattr(module, attr, None)
    if not callable(fn):
        raise argparse.ArgumentTypeError(f"Not callable: {spec}")
    return fn


def _collect_pdfs(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() != ".pdf":
            raise SystemExit(f"Not a PDF file: {path}")
        return [path]
    if path.is_dir():
        pdfs = sorted(path.glob("*.pdf"))
        if not pdfs:
            raise SystemExit(f"No PDF files in {path}")
        return pdfs
    raise SystemExit(f"Path does not exist: {path}")


def process_pdf(pdf_path: Path, output_dir: Path, llm_fn, *, batch_chars, batch_overlap, root_title) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown = extract_pdf_to_markdown(str(pdf_path))
    print(f"  Markdown: {len(markdown):,} chars")
    structure, extraction_meta = extract_structure(
        markdown,
        llm_fn,
        batch_chars=batch_chars,
        batch_overlap=batch_overlap,
        root_title=root_title,
        return_meta=True,
    )
    if extraction_meta.get("batched"):
        print(f"  LLM batches: {extraction_meta['batch_count']}")

    out_path = output_dir / f"{pdf_path.stem}.json"
    payload = {
        "source_pdf": str(pdf_path.resolve()),
        "markdown_chars": len(markdown),
        "extraction": extraction_meta,
        "structure": structure,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract hierarchical structure from credit agreement PDFs."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(DEFAULT_PDF_DIR),
        help=f"PDF file or directory (default: {DEFAULT_PDF_DIR})",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for JSON files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--llm",
        type=_load_callable,
        default=None,
        help="LLM callable as MODULE:CALLABLE (default: call_llm in this file)",
    )
    parser.add_argument(
        "--batch-chars",
        type=int,
        default=None,
        help=(
            "Max Markdown chars per LLM call (overrides --context-tokens). "
            "0 = single call for entire document."
        ),
    )
    parser.add_argument(
        "--context-tokens",
        type=int,
        default=GPT_OSS_CONTEXT_TOKENS,
        help=(
            "Model context window used to size batches when --batch-chars is unset "
            f"(default: {GPT_OSS_CONTEXT_TOKENS}, gpt-oss native max). "
            f"Use {GPT_OSS_REFERENCE_CLI_DEFAULT_TOKENS} if your gpt-oss server "
            "runs at the reference CLI default (-c 8192)."
        ),
    )
    parser.add_argument(
        "--batch-overlap",
        type=int,
        default=None,
        help="Character overlap between batches (default: derived from batch size)",
    )
    parser.add_argument(
        "--root-title",
        default="Credit Agreement",
        help="Title for the synthesized document root node",
    )
    args = parser.parse_args()

    batch_chars, default_overlap = resolve_batch_settings(
        batch_chars=args.batch_chars,
        context_tokens=args.context_tokens,
    )
    batch_overlap = (
        args.batch_overlap if args.batch_overlap is not None else default_overlap
    )
    if args.batch_chars is None:
        print(
            f"Batch sizing: context_tokens={args.context_tokens} -> "
            f"batch_chars={batch_chars:,}, overlap={batch_overlap:,}"
        )
    llm_fn = args.llm if args.llm is not None else call_llm
    input_path = Path(args.input)
    output_dir = Path(args.output)

    for pdf in _collect_pdfs(input_path):
        print(f"Processing {pdf.name}...")
        out = process_pdf(
            pdf,
            output_dir,
            llm_fn,
            batch_chars=batch_chars,
            batch_overlap=args.batch_overlap,
            root_title=args.root_title,
        )
        print(f"  -> {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
