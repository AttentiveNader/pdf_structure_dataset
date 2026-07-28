from pathlib import Path
from typing import Optional, Tuple

from docling.document_converter import DocumentConverter

PageRange = Tuple[int, int]


def extract_pdf_to_markdown(
    pdf_path: str,
    *,
    page_range: Optional[PageRange] = None,
) -> str:
    """Convert a PDF to Markdown using Docling.

    ``page_range`` is 1-based inclusive, e.g. ``(1, 20)`` for the first 20 pages.
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    converter = DocumentConverter()
    kwargs = {}
    if page_range is not None:
        kwargs["page_range"] = page_range
    result = converter.convert(str(path), **kwargs)
    return result.document.export_to_markdown()
