"""
PageIndex-inspired retrieval over credit agreement PDFs + TOC index.

See: https://github.com/VectifyAI/PageIndex/blob/main/pageindex/retrieve.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

try:
    import pypdfium2 as pdfium
except ImportError as e:
    raise ImportError(
        "pypdfium2 is required for page retrieval (install docling or pypdfium2)"
    ) from e


def parse_pages(pages: str) -> list[int]:
    """Parse ``'5-7'``, ``'3,8'``, or ``'12'`` into sorted unique 1-based page numbers."""
    result: list[int] = []
    for part in pages.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s.strip()), int(end_s.strip())
            if start > end:
                raise ValueError(f"Invalid range '{part}': start must be <= end")
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def get_number_of_pages(pdf_path: str | Path) -> int:
    path = Path(pdf_path)
    doc = pdfium.PdfDocument(str(path))
    try:
        return len(doc)
    finally:
        doc.close()


def _extract_page_text(doc: pdfium.PdfDocument, page_num: int) -> str:
    page = doc[page_num - 1]
    textpage = page.get_textpage()
    try:
        return textpage.get_text_range() or ""
    finally:
        textpage.close()
        page.close()


def get_pdf_page_content(
    pdf_path: str | Path,
    page_nums: list[int],
    *,
    cached_pages: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Return ``[{'page': int, 'content': str}, ...]`` for 1-based PDF pages."""
    if cached_pages:
        page_map = {p["page"]: p["content"] for p in cached_pages}
        return [{"page": p, "content": page_map[p]} for p in page_nums if p in page_map]

    path = Path(pdf_path)
    doc = pdfium.PdfDocument(str(path))
    try:
        total = len(doc)
        valid = [p for p in page_nums if 1 <= p <= total]
        return [
            {"page": p, "content": _extract_page_text(doc, p)}
            for p in valid
        ]
    finally:
        doc.close()


def remove_fields(structure: Any, *, fields: list[str]) -> Any:
    """Recursively remove keys from a tree (PageIndex-style token saving)."""
    if isinstance(structure, dict):
        out = {k: v for k, v in structure.items() if k not in fields}
        if "children" in out:
            out["children"] = remove_fields(out["children"], fields=fields)
        return out
    if isinstance(structure, list):
        return [remove_fields(item, fields=fields) for item in structure]
    return structure


def get_document_metadata(doc_info: dict[str, Any]) -> str:
    """JSON metadata: name, title, page count, page mapping."""
    result = {
        "doc_name": doc_info.get("doc_name", ""),
        "document_title": doc_info.get("document_title", ""),
        "type": "pdf",
        "status": "completed",
        "page_count": doc_info.get("page_count"),
        "source_pdf": doc_info.get("path", ""),
        "toc_chars": len(doc_info.get("toc_text") or ""),
    }
    mapping = doc_info.get("page_mapping")
    if mapping:
        result["page_mapping"] = mapping
        result["toc_page_numbers_are"] = "printed"
        result["page_content_pages_are"] = "printed"
        result["conversion"] = (
            "Pass printed TOC page numbers to get_page_content; "
            "they are converted to PDF page indices automatically."
        )
    return json.dumps(result, ensure_ascii=False)


def get_document_structure_json(doc_info: dict[str, Any]) -> str:
    """Compact TOC text for navigation (minimal tokens)."""
    toc = doc_info.get("toc_text")
    if not toc:
        return json.dumps({"error": "no TOC text loaded"})
    return toc


def get_page_content_json(
    doc_info: dict[str, Any],
    pages: str,
) -> str:
    """Retrieve page text; ``pages`` format like ``5-7``, ``3,8``, ``12``."""
    path = doc_info.get("path")
    if not path:
        return json.dumps({"error": "document path not set"})

    page_spec = pages
    mapping = doc_info.get("page_mapping")
    if mapping and isinstance(mapping, dict):
        from pipeline.page_mapping import PageMapping, convert_page_spec_printed_to_pdf

        pm = PageMapping.from_dict(mapping)
        page_spec = convert_page_spec_printed_to_pdf(pages, pm)

    try:
        page_nums = parse_pages(page_spec)
    except (ValueError, AttributeError) as e:
        return json.dumps(
            {
                "error": f"Invalid pages format: {pages!r}. Use '5-7', '3,8', or '12'. {e}"
            }
        )

    try:
        content = get_pdf_page_content(
            path,
            page_nums,
            cached_pages=doc_info.get("pages"),
        )
    except Exception as e:
        return json.dumps({"error": f"Failed to read page content: {e}"})

    if mapping and isinstance(mapping, dict):
        offset = mapping.get("offset_pdf_minus_printed", 0)
        for item in content:
            item["pdf_page"] = item["page"]
            item["printed_page"] = item["page"] - offset
            item["page"] = item["printed_page"]

    return json.dumps(content, ensure_ascii=False)
