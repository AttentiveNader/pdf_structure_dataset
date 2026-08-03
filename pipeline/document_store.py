"""In-memory document store for TOC-guided retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pipeline.page_mapping import identity_mapping
from pipeline.retrieve import get_number_of_pages
from pipeline.toc import parse_document_title


class CreditDocumentStore:
    """PDF path + compact TOC text + optional page cache."""

    def __init__(
        self,
        pdf_path: str | Path,
        *,
        document_title: str = "",
        toc_text: str = "",
        pages: Optional[list[dict[str, Any]]] = None,
        page_mapping: Optional[dict[str, Any]] = None,
        toc_page_numbers_are: str = "pdf",
    ):
        self.path = str(Path(pdf_path).resolve())
        self.doc_name = Path(pdf_path).name
        self.document_title = document_title
        self.toc_text = toc_text
        self.pages = pages
        self.page_mapping = page_mapping or identity_mapping().to_dict()
        self.toc_page_numbers_are = toc_page_numbers_are
        self.page_count = get_number_of_pages(self.path)

    @classmethod
    def from_toc_file(cls, pdf_path: str | Path, toc_path: str | Path) -> "CreditDocumentStore":
        """Load compact TOC text from ``*.toc.txt`` (PDF page indices)."""
        toc_file = Path(toc_path)
        if not toc_file.is_file():
            raise FileNotFoundError(f"TOC file not found: {toc_file}")

        toc_text = toc_file.read_text(encoding="utf-8").strip()
        if not toc_text:
            raise ValueError(f"TOC file is empty: {toc_file}")

        return cls(
            pdf_path=pdf_path,
            document_title=parse_document_title(toc_text),
            toc_text=toc_text,
            page_mapping=identity_mapping().to_dict(),
            toc_page_numbers_are="pdf",
        )

    def as_doc_info(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "doc_name": self.doc_name,
            "document_title": self.document_title,
            "page_count": self.page_count,
            "toc_text": self.toc_text,
            "pages": self.pages,
            "page_mapping": self.page_mapping,
            "toc_page_numbers_are": self.toc_page_numbers_are,
        }

    def preload_pages(self) -> None:
        """Cache all page text for faster retrieval."""
        from pipeline.retrieve import get_pdf_page_content

        nums = list(range(1, self.page_count + 1))
        self.pages = get_pdf_page_content(self.path, nums)
