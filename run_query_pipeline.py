#!/usr/bin/env python3
"""
TOC-guided document QA (PageIndex-inspired).

Uses table_of_contents JSON (from run_toc_pipeline.py) to navigate the PDF and
answer queries via an LLM agent with retrieval tools:

  get_document / get_document_structure / get_page_content

Inspired by https://github.com/VectifyAI/PageIndex/blob/main/pageindex/retrieve.py
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

from pipeline.document_store import CreditDocumentStore
from pipeline.query_agent import run_query

DEFAULT_TOC_DIR = ROOT / "output_toc"


def call_llm(prompt: str) -> str:
    raise NotImplementedError(
        "Implement call_llm(prompt: str) -> str in run_query_pipeline.py "
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


def _resolve_toc_path(pdf_path: Path, toc_arg: str | None) -> Path:
    if toc_arg:
        toc = Path(toc_arg)
        if not toc.is_file():
            raise SystemExit(f"TOC JSON not found: {toc}")
        return toc
    default = DEFAULT_TOC_DIR / f"{pdf_path.stem}.json"
    if default.is_file():
        return default
    raise SystemExit(
        f"No TOC found at {default}. Run run_toc_pipeline.py first or pass --toc PATH."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Answer questions about a credit agreement using TOC-guided page retrieval."
    )
    parser.add_argument(
        "pdf",
        help="Path to the credit agreement PDF",
    )
    parser.add_argument(
        "--toc",
        default=None,
        help=f"TOC JSON path (default: {DEFAULT_TOC_DIR}/<stem>.json)",
    )
    parser.add_argument(
        "--query",
        "-q",
        default=None,
        help="Question to ask (omit for interactive mode)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=12,
        help="Max agent tool-use steps before failing",
    )
    parser.add_argument(
        "--preload-pages",
        action="store_true",
        help="Cache all PDF page text in memory (faster repeat queries)",
    )
    parser.add_argument(
        "--llm",
        type=_load_callable,
        default=None,
        help="LLM callable as MODULE:CALLABLE",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Optional path to write JSON result (answer + steps)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    toc_path = _resolve_toc_path(pdf_path, args.toc)
    store = CreditDocumentStore.from_toc_json(pdf_path, toc_path)
    if args.preload_pages:
        print(f"Preloading {store.page_count} pages...")
        store.preload_pages()

    llm_fn = args.llm if args.llm is not None else call_llm

    def ask(question: str) -> None:
        print(f"\nQuestion: {question}\n")
        result = run_query(
            store,
            question,
            llm_fn,
            max_steps=args.max_steps,
        )
        print(f"\nAnswer:\n{result.answer}\n")
        if args.output:
            out = Path(args.output)
            out.write_text(
                json.dumps(
                    {
                        "pdf": str(pdf_path.resolve()),
                        "toc": str(toc_path.resolve()),
                        "query": question,
                        "answer": result.answer,
                        "steps": result.steps,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"Wrote {out}")

    if args.query:
        ask(args.query)
        return 0

    print("Interactive mode (empty line to exit).")
    while True:
        try:
            line = input("Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        ask(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
