"""In-memory document store for TOC-guided retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pipeline.retrieve import get_number_of_pages
from pipeline.page_mapping import identity_mapping


class CreditDocumentStore:
    """
    PageIndex-style document record: PDF path + TOC tree + optional page cache.
    """

    def __init__(
        self,
        pdf_path: str | Path,
        *,
        document_title: str = "",
        table_of_contents: Optional[dict[str, Any]] = None,
        pages: Optional[list[dict[str, Any]]] = None,
        page_mapping: Optional[dict[str, Any]] = None,
    ):
        self.path = str(Path(pdf_path).resolve())
        self.doc_name = Path(pdf_path).name
        self.document_title = document_title
        self.table_of_contents = table_of_contents
        self.pages = pages
        self.page_mapping = page_mapping
        self.page_count = get_number_of_pages(self.path)

    @classmethod
    def from_toc_json(cls, pdf_path: str | Path, toc_json_path: str | Path) -> "CreditDocumentStore":
        data = json.loads(Path(toc_json_path).read_text(encoding="utf-8"))
        pdf_resolved = Path(pdf_path).resolve()
        source = data.get("source_pdf")
        if source and Path(source).resolve() != pdf_resolved:
            pass  # allow override via explicit pdf_path argument
        store = cls(
            pdf_path=pdf_path,
            document_title=data.get("document_title", ""),
            table_of_contents=data.get("table_of_contents"),
            page_mapping=data.get("page_mapping"),
        )
        if store.page_mapping is None:
            store.page_mapping = identity_mapping().to_dict()
        return store

    def as_doc_info(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "doc_name": self.doc_name,
            "document_title": self.document_title,
            "page_count": self.page_count,
            "table_of_contents": self.table_of_contents,
            "pages": self.pages,
            "page_mapping": self.page_mapping,
        }

    def preload_pages(self) -> None:
        """Cache all page text (PageIndex client pattern) for faster retrieval."""
        from pipeline.retrieve import get_pdf_page_content

        nums = list(range(1, self.page_count + 1))
        self.pages = get_pdf_page_content(self.path, nums)
