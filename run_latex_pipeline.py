#!/usr/bin/env python3
"""
Credit agreement PDF → Docling Markdown → LLM LaTeX rewrite → parsed structure.

Optional: compile .tex to PDF with pdflatex/xelatex.
"""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.context_budget import (
    GPT_OSS_CONTEXT_TOKENS,
    GPT_OSS_REFERENCE_CLI_DEFAULT_TOKENS,
    resolve_batch_settings,
)
from pipeline.extract import extract_pdf_to_markdown
from pipeline.latex_rewrite import rewrite_to_latex
from pipeline.latex_structure import extract_structure_from_latex

DEFAULT_PDF_DIR = ROOT / "pdfs"
DEFAULT_OUTPUT_DIR = ROOT / "output_latex"
SCHEMA_SRC = ROOT / "pipeline" / "latex_schema.tex"


def call_llm(prompt: str) -> str:
    raise NotImplementedError(
        "Implement call_llm(prompt: str) -> str in run_latex_pipeline.py "
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


def _ensure_schema(output_dir: Path) -> None:
    dest = output_dir / "latex_schema.tex"
    if not dest.exists():
        shutil.copy2(SCHEMA_SRC, dest)


def _compile_tex(tex_path: Path, engine: str) -> Path:
    build_dir = tex_path.parent
    cmd = [
        engine,
        "-interaction=nonstopmode",
        "-halt-on-error",
        tex_path.name,
    ]
    for _ in range(2):
        result = subprocess.run(
            cmd,
            cwd=build_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{engine} failed:\n{result.stdout}\n{result.stderr}"
            )
    pdf_path = build_dir / f"{tex_path.stem}.pdf"
    if not pdf_path.is_file():
        raise RuntimeError(f"Expected output PDF not found: {pdf_path}")
    return pdf_path


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    llm_fn,
    *,
    batch_chars,
    batch_overlap,
    root_title,
    compile_pdf: bool,
    latex_engine: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_schema(output_dir)

    markdown = extract_pdf_to_markdown(str(pdf_path))
    print(f"  Markdown: {len(markdown):,} chars")

    tex, rewrite_meta = rewrite_to_latex(
        markdown,
        llm_fn,
        batch_chars=batch_chars,
        batch_overlap=batch_overlap,
        schema_input="latex_schema.tex",
    )
    if rewrite_meta.get("batched"):
        print(f"  LaTeX rewrite batches: {rewrite_meta['rewrite_batches']}")

    tex_path = output_dir / f"{pdf_path.stem}.tex"
    tex_path.write_text(tex, encoding="utf-8")

    structure, structure_source, extraction_meta = extract_structure_from_latex(
        tex,
        llm_fn,
        markdown,
        batch_chars=batch_chars,
        batch_overlap=batch_overlap,
        root_title=root_title,
    )
    print(f"  Structure source: {structure_source}")

    compiled_pdf: str | None = None
    if compile_pdf:
        pdf_out = _compile_tex(tex_path, latex_engine)
        compiled_pdf = str(pdf_out.resolve())
        print(f"  Compiled: {compiled_pdf}")

    json_path = output_dir / f"{pdf_path.stem}.json"
    payload = {
        "source_pdf": str(pdf_path.resolve()),
        "markdown_chars": len(markdown),
        "latex_path": str(tex_path.resolve()),
        "structure_source": structure_source,
        "extraction": {**rewrite_meta, **extraction_meta},
        "structure": structure,
    }
    if compiled_pdf:
        payload["compiled_pdf"] = compiled_pdf

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return json_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rewrite credit agreements to LaTeX and extract structure."
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
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--llm",
        type=_load_callable,
        default=None,
        help="LLM callable as MODULE:CALLABLE",
    )
    parser.add_argument(
        "--batch-chars",
        type=int,
        default=None,
        help="Max Markdown chars per rewrite call (0 = no batching)",
    )
    parser.add_argument(
        "--context-tokens",
        type=int,
        default=GPT_OSS_CONTEXT_TOKENS,
        help=(
            f"Context window for batch sizing (default {GPT_OSS_CONTEXT_TOKENS}). "
            f"Use {GPT_OSS_REFERENCE_CLI_DEFAULT_TOKENS} for gpt-oss CLI default."
        ),
    )
    parser.add_argument(
        "--batch-overlap",
        type=int,
        default=None,
        help="Overlap between markdown batches",
    )
    parser.add_argument(
        "--root-title",
        default="Credit Agreement",
        help="Fallback root title for LLM structure extraction",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Run pdflatex/xelatex on each generated .tex (requires LaTeX on PATH)",
    )
    parser.add_argument(
        "--latex-engine",
        default="pdflatex",
        choices=("pdflatex", "xelatex"),
        help="LaTeX engine when --compile is set",
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
            batch_overlap=batch_overlap,
            root_title=args.root_title,
            compile_pdf=args.compile,
            latex_engine=args.latex_engine,
        )
        print(f"  -> {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
