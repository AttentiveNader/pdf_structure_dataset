"""
Map TOC printed page numbers to PDF file page indices.

Uses the **last word** of each page's extracted text as the printed page label
(Roman numerals in front matter, then Arabic). TOC Arabic pages align via offset
at the first PDF page whose last word is ``1``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal, Optional

from pipeline.retrieve import get_number_of_pages, get_pdf_page_content

PageKind = Literal["roman", "arabic"]

_ROMAN_RE = re.compile(r"^[IVXLCDM]+$", re.IGNORECASE)


@dataclass
class PageMapping:
    """Convert printed TOC pages to 1-based PDF page indices."""

    toc_page_kind: str  # "printed"
    printed_page_one_pdf_page: int
    offset_pdf_minus_printed: int
    method: str  # "last_word" | "llm" | "identity"
    confidence: str  # "high" | "medium" | "low"
    notes: str = ""

    def printed_to_pdf(self, printed_page: int) -> int:
        return printed_page + self.offset_pdf_minus_printed

    def pdf_to_printed(self, pdf_page: int) -> int:
        return pdf_page - self.offset_pdf_minus_printed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageMapping":
        return cls(
            toc_page_kind=str(data.get("toc_page_kind", "printed")),
            printed_page_one_pdf_page=int(data["printed_page_one_pdf_page"]),
            offset_pdf_minus_printed=int(data["offset_pdf_minus_printed"]),
            method=str(data.get("method", "manual")),
            confidence=str(data.get("confidence", "medium")),
            notes=str(data.get("notes", "")),
        )


def identity_mapping() -> PageMapping:
    return PageMapping(
        toc_page_kind="printed",
        printed_page_one_pdf_page=1,
        offset_pdf_minus_printed=0,
        method="identity",
        confidence="low",
        notes="No page labels found; assuming TOC pages match PDF indices.",
    )


def mapping_from_hint(hint: Any) -> Optional[PageMapping]:
    """Build mapping from optional LLM ``page_mapping_hint`` in TOC JSON."""
    if not isinstance(hint, dict):
        return None
    pdf_one = hint.get("printed_page_one_pdf_page")
    if not isinstance(pdf_one, int) or pdf_one < 1:
        return None
    offset = pdf_one - 1
    return PageMapping(
        toc_page_kind="printed",
        printed_page_one_pdf_page=pdf_one,
        offset_pdf_minus_printed=offset,
        method="llm",
        confidence="medium",
        notes=str(hint.get("notes") or "From TOC extraction page_mapping_hint."),
    )


def roman_to_int(value: str) -> Optional[int]:
    value = value.upper()
    if not _ROMAN_RE.match(value):
        return None
    numerals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(value):
        if ch not in numerals:
            return None
        cur = numerals[ch]
        if cur < prev:
            total -= cur
        else:
            total += cur
            prev = cur
    return total if total > 0 else None


def parse_page_label_token(token: str) -> Optional[tuple[PageKind, int]]:
    """Parse last word as Roman or Arabic page label."""
    if not token:
        return None
    token = token.strip().strip(".,;:-–—")
    if not token:
        return None
    if token.isdigit():
        n = int(token)
        return ("arabic", n) if n >= 0 else None
    roman = roman_to_int(token)
    if roman is not None:
        return ("roman", roman)
    return None


def last_word_page_label(page_text: str) -> Optional[tuple[PageKind, int]]:
    """Last word of full page text if it is a page number (Roman or Arabic)."""
    if not page_text or not page_text.strip():
        return None
    words = page_text.split()
    if not words:
        return None
    token = words[-1].strip(".,;:-–— ")
    return parse_page_label_token(token)


def scan_pdf_page_labels(
    pdf_path: str,
    *,
    max_pdf_pages: int = 250,
) -> list[tuple[int, Optional[tuple[PageKind, int]]]]:
    """For each PDF page, label from last word of extracted text."""
    total = get_number_of_pages(pdf_path)
    load_until = min(total, max_pdf_pages)
    pages = get_pdf_page_content(pdf_path, list(range(1, load_until + 1)))
    return [
        (item["page"], last_word_page_label(item.get("content") or ""))
        for item in pages
    ]


def calibrate_page_mapping(
    pdf_path: str,
    *,
    max_pdf_pages: int = 250,
) -> Optional[PageMapping]:
    """
    Find first PDF page whose last word is Arabic ``1`` (after Roman front matter).

    ``offset_pdf_minus_printed = pdf_page - 1``.
    """
    labels = scan_pdf_page_labels(pdf_path, max_pdf_pages=max_pdf_pages)
    if not labels:
        return None

    pdf_page_one: Optional[int] = None
    roman_pages = 0
    for pdf_page, parsed in labels:
        if parsed is None:
            continue
        kind, num = parsed
        if kind == "roman":
            roman_pages += 1
        if kind == "arabic" and num == 1:
            pdf_page_one = pdf_page
            break

    if pdf_page_one is None:
        return None

    offset = pdf_page_one - 1

    verify = 0
    verify_ok = 0
    for pdf_page, parsed in labels:
        if pdf_page < pdf_page_one or parsed is None:
            continue
        kind, num = parsed
        if kind != "arabic":
            continue
        expected = pdf_page - offset
        verify += 1
        if num == expected:
            verify_ok += 1
        if verify >= 8:
            break

    if verify >= 3 and verify_ok == verify:
        confidence = "high"
    elif verify_ok >= 2:
        confidence = "medium"
    else:
        confidence = "medium"

    return PageMapping(
        toc_page_kind="printed",
        printed_page_one_pdf_page=pdf_page_one,
        offset_pdf_minus_printed=offset,
        method="last_word",
        confidence=confidence,
        notes=(
            f"Last-word scan: {roman_pages} PDF page(s) with Roman labels before "
            f"Arabic 1 on PDF page {pdf_page_one} (offset +{offset})."
        ),
    )


def resolve_page_mapping(
    pdf_path: str,
    *,
    page_mapping_hint: Any = None,
) -> PageMapping:
    """Last-word calibration, then LLM hint, then identity."""
    mapped = calibrate_page_mapping(pdf_path)
    if mapped is not None:
        return mapped
    hinted = mapping_from_hint(page_mapping_hint)
    if hinted is not None:
        return hinted
    return identity_mapping()


def convert_page_spec_printed_to_pdf(
    pages: str,
    mapping: PageMapping,
) -> str:
    """Convert a pages spec from printed numbers to PDF page numbers."""
    parts: list[str] = []
    for part in pages.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = mapping.printed_to_pdf(int(a.strip()))
            end = mapping.printed_to_pdf(int(b.strip()))
            parts.append(f"{start}-{end}")
        else:
            parts.append(str(mapping.printed_to_pdf(int(part))))
    return ",".join(parts)
