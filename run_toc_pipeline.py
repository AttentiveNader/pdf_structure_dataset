#!/usr/bin/env python3
"""
Extract table of contents (with page numbers) from the first N pages of credit agreement PDFs.

Docling -> Markdown (page-limited) -> LLM -> JSON TOC tree.
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
from pipeline.toc import extract_toc

DEFAULT_PDF_DIR = ROOT / "pdfs"
DEFAULT_OUTPUT_DIR = ROOT / "output_toc"
DEFAULT_MAX_PAGES = 20


def call_llm(prompt: str) -> str:
    raise NotImplementedError(
        "Implement call_llm(prompt: str) -> str in run_toc_pipeline.py "
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


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    llm_fn,
    *,
    max_pages: int,
    mapping_preview_pages: int = 15,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    page_range = (1, max_pages)
    markdown = extract_pdf_to_markdown(str(pdf_path), page_range=page_range)
    print(f"  Markdown (pages 1–{max_pages}): {len(markdown):,} chars")

    toc_data = extract_toc(markdown, llm_fn, max_pages=max_pages)

    from pipeline.toc import resolve_page_mapping_for_document

    page_mapping = resolve_page_mapping_for_document(
        str(pdf_path.resolve()),
        llm_fn,
        preview_pages=mapping_preview_pages,
    )
    print(
        f"  Page mapping: printed p.1 -> PDF p.{page_mapping.printed_page_one_pdf_page} "
        f"({page_mapping.method}, {page_mapping.confidence})"
    )

    out_path = output_dir / f"{pdf_path.stem}.json"
    payload = {
        "source_pdf": str(pdf_path.resolve()),
        "pages_extracted": {"from": 1, "to": max_pages},
        "markdown_chars": len(markdown),
        "document_title": toc_data["document_title"],
        "page_mapping": page_mapping.to_dict(),
        "table_of_contents": toc_data["table_of_contents"],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract TOC with page numbers from the first pages of credit agreement PDFs."
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
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Number of pages from the start to analyze (default: {DEFAULT_MAX_PAGES})",
    )
    parser.add_argument(
        "--llm",
        type=_load_callable,
        default=None,
        help="LLM callable as MODULE:CALLABLE (default: call_llm in this file)",
    )
    parser.add_argument(
        "--mapping-preview-pages",
        type=int,
        default=15,
        help="PDF pages sent to LLM for printed-page-1 detection (default: 15)",
    )
    args = parser.parse_args()

    if args.max_pages < 1:
        raise SystemExit("--max-pages must be at least 1")
    if args.mapping_preview_pages < 1:
        raise SystemExit("--mapping-preview-pages must be at least 1")

    llm_fn = args.llm if args.llm is not None else call_llm
    input_path = Path(args.input)
    output_dir = Path(args.output)

    for pdf in _collect_pdfs(input_path):
        print(f"Processing {pdf.name}...")
        out = process_pdf(
            pdf,
            output_dir,
            llm_fn,
            max_pages=args.max_pages,
            mapping_preview_pages=args.mapping_preview_pages,
        )
        print(f"  -> {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
