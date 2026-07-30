"""Tests for LLM-oriented page mapping helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.page_mapping import (
    PageMapping,
    _parse_content_start_response,
    convert_page_spec_printed_to_pdf,
    format_pages_with_pdf_index,
    slice_page_edges,
)


class PageMappingTests(unittest.TestCase):
    def test_format_pages(self) -> None:
        block = format_pages_with_pdf_index(
            [{"page": 2, "content": "Table of Contents"}]
        )
        self.assertIn("[PDF_PAGE_INDEX: 2]", block)
        self.assertIn("Table of Contents", block)

    def test_parse_llm_response(self) -> None:
        m = _parse_content_start_response(
            {"printed_page_one_pdf_page": 6, "notes": "ARTICLE I"},
            page_count=100,
        )
        self.assertEqual(m.printed_page_one_pdf_page, 6)
        self.assertEqual(m.offset_pdf_minus_printed, 5)
        self.assertEqual(m.method, "llm_content_start")

    def test_format_pages_snippet(self) -> None:
        long_text = "H" * 150 + "BODY" + "T" * 150
        snippet = slice_page_edges(long_text, edge_chars=100)
        self.assertTrue(snippet.startswith("H" * 100))
        self.assertTrue(snippet.endswith("T" * 100))
        block = format_pages_with_pdf_index([{"page": 3, "content": long_text}])
        self.assertIn("[PDF_PAGE_INDEX: 3]", block)
        self.assertNotIn("BODY", block)

    def test_convert_spec(self) -> None:
        m = PageMapping(
            toc_page_kind="printed",
            printed_page_one_pdf_page=6,
            offset_pdf_minus_printed=5,
            method="llm_content_start",
            confidence="medium",
        )
        self.assertEqual(convert_page_spec_printed_to_pdf("1-3", m), "6-8")


if __name__ == "__main__":
    unittest.main()
