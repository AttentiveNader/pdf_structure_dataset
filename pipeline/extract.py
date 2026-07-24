from pathlib import Path

from docling.document_converter import DocumentConverter


def extract_pdf_to_markdown(pdf_path: str) -> str:
    """Convert a PDF to Markdown using Docling."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    converter = DocumentConverter()
    result = converter.convert(str(path))
    return result.document.export_to_markdown()
