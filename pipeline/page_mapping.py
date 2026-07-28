"""
Map TOC printed page numbers to PDF file page indices.

Credit agreements put the **printed page number as the last word** on each sheet.
Front matter uses Roman numerals (i, ii, …); body numbering switches to Arabic
starting at 1. TOC entries refer to those Arabic numbers.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import asdict, dataclass
from typing import Any, Literal, Optional

from pipeline.retrieve import get_number_of_pages, get_pdf_page_content

PageKind = Literal["roman", "arabic"]

_ROMAN_RE = re.compile(r"^[IVXLCDM]+$", re.IGNORECASE)
_TRAILING_NUMBER_RE = re.compile(
    r"(?:^|\s)(?:page\s+)?(-?\s*)?(\d+|[ivxlcdm]+)\s*(-?\s*)?$",
    re.IGNORECASE,
)


@dataclass
class PageMapping:
    """Convert printed TOC pages to 1-based PDF page indices."""

    toc_page_kind: str  # "printed"
    printed_page_one_pdf_page: int
    offset_pdf_minus_printed: int
    method: str  # "footer_scan" | "anchor_search" | "llm" | "identity"
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
        notes="Assumes TOC page numbers match PDF page indices.",
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


def parse_footer_page_label(token: str) -> Optional[tuple[PageKind, int]]:
    """Parse last-word footer as Roman or Arabic page label."""
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


def extract_footer_token(page_text: str) -> Optional[str]:
    """
    Read the page number credit agreements print at the bottom — usually the
    last word, often on the last non-empty line (e.g. ``- 1 -`` or ``ii``).
    """
    if not page_text or not page_text.strip():
        return None

    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    if lines:
        last_line = lines[-1]
        match = _TRAILING_NUMBER_RE.search(last_line)
        if match:
            return match.group(2)

    words = page_text.split()
    if not words:
        return None
    return words[-1].strip(".,;:-–— ")


def scan_pdf_footer_labels(
    pdf_path: str,
    *,
    max_pdf_pages: int = 250,
) -> list[tuple[int, Optional[tuple[PageKind, int]]]]:
    """For each PDF page index, parse footer label (roman or arabic)."""
    total = get_number_of_pages(pdf_path)
    load_until = min(total, max_pdf_pages)
    pages = get_pdf_page_content(pdf_path, list(range(1, load_until + 1)))
    out: list[tuple[int, Optional[tuple[PageKind, int]]]] = []
    for item in pages:
        pdf_page = item["page"]
        token = extract_footer_token(item.get("content") or "")
        parsed = parse_footer_page_label(token) if token else None
        out.append((pdf_page, parsed))
    return out


def calibrate_page_mapping_from_footers(
    pdf_path: str,
    *,
    max_pdf_pages: int = 250,
) -> Optional[PageMapping]:
    """
    Find the first PDF page whose footer is Arabic ``1`` after Roman front matter.

    ``offset_pdf_minus_printed = pdf_page - 1`` so TOC printed page maps to PDF.
    """
    labels = scan_pdf_footer_labels(pdf_path, max_pdf_pages=max_pdf_pages)
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
        method="footer_scan",
        confidence=confidence,
        notes=(
            f"Footer scan: {roman_pages} PDF page(s) with Roman labels before "
            f"Arabic page 1 on PDF page {pdf_page_one} "
            f"(offset +{offset})."
        ),
    )


def _normalize_for_match(text: str) -> str:
    text = text.upper()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _title_match(page_text: str, title: str) -> bool:
    if not page_text or not title:
        return False
    norm_page = _normalize_for_match(page_text)
    norm_title = _normalize_for_match(title)
    if len(norm_title) < 6:
        return norm_title in norm_page
    prefix = norm_title[: min(40, len(norm_title))]
    return prefix in norm_page


def _iter_toc_entries(node: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(n: dict[str, Any]) -> None:
        page = n.get("page")
        title = n.get("title")
        level = n.get("level", 0)
        if (
            isinstance(title, str)
            and isinstance(page, int)
            and page >= 1
            and level >= 1
        ):
            out.append({"title": title, "page": page, "level": level})
        for child in n.get("children") or []:
            if isinstance(child, dict):
                walk(child)

    walk(node)
    return out


def calibrate_page_mapping_anchor_search(
    pdf_path: str,
    table_of_contents: dict[str, Any],
    *,
    max_pdf_pages_to_load: int = 150,
    max_offset: int = 40,
) -> PageMapping:
    """Fallback: match TOC titles to PDF body text."""
    entries = _iter_toc_entries(table_of_contents)
    if not entries:
        return identity_mapping()

    total = get_number_of_pages(pdf_path)
    load_until = min(total, max_pdf_pages_to_load)
    page_nums = list(range(1, load_until + 1))
    pages = get_pdf_page_content(pdf_path, page_nums)
    pdf_text = {p["page"]: p["content"] for p in pages}

    deltas: list[int] = []
    for entry in entries[:12]:
        printed = entry["page"]
        title = entry["title"]
        search_max = min(total, printed + max_offset + 10)
        for pdf_p in range(1, search_max + 1):
            if pdf_p not in pdf_text:
                continue
            if _title_match(pdf_text[pdf_p], title):
                deltas.append(pdf_p - printed)
                break

    if not deltas:
        return PageMapping(
            toc_page_kind="printed",
            printed_page_one_pdf_page=1,
            offset_pdf_minus_printed=0,
            method="anchor_search",
            confidence="low",
            notes="No TOC titles matched PDF text; using 1:1 mapping.",
        )

    offset = int(round(statistics.median(deltas)))
    if offset < 0:
        offset = 0

    spread = max(deltas) - min(deltas) if len(deltas) > 1 else 0
    confidence = "high" if spread <= 2 and len(deltas) >= 2 else "medium"
    if len(deltas) == 1:
        confidence = "medium"

    return PageMapping(
        toc_page_kind="printed",
        printed_page_one_pdf_page=1 + offset,
        offset_pdf_minus_printed=offset,
        method="anchor_search",
        confidence=confidence,
        notes=f"Matched {len(deltas)} TOC anchor(s); delta spread={spread}.",
    )


def calibrate_page_mapping(
    pdf_path: str,
    table_of_contents: dict[str, Any],
    **kwargs: Any,
) -> PageMapping:
    """Prefer footer scan; fall back to TOC title anchor search."""
    footer = calibrate_page_mapping_from_footers(pdf_path)
    if footer is not None:
        return footer
    return calibrate_page_mapping_anchor_search(pdf_path, table_of_contents, **kwargs)


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
