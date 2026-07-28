"""Tests for footer-based page mapping."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.page_mapping import (
    PageMapping,
    convert_page_spec_printed_to_pdf,
    extract_footer_token,
    parse_footer_page_label,
    roman_to_int,
)


class FooterMappingTests(unittest.TestCase):
    def test_roman(self) -> None:
        self.assertEqual(roman_to_int("iv"), 4)
        self.assertEqual(roman_to_int("xii"), 12)

    def test_parse_labels(self) -> None:
        self.assertEqual(parse_footer_page_label("1"), ("arabic", 1))
        self.assertEqual(parse_footer_page_label("ii"), ("roman", 2))

    def test_extract_footer_token(self) -> None:
        text = "Section 1.01 Defined Terms\n\nSome body text here.\n\n- 1 -"
        self.assertEqual(extract_footer_token(text), "1")
        self.assertEqual(extract_footer_token("Cover page\n\niii"), "iii")

    def test_convert_spec(self) -> None:
        m = PageMapping(
            toc_page_kind="printed",
            printed_page_one_pdf_page=6,
            offset_pdf_minus_printed=5,
            method="footer_scan",
            confidence="high",
        )
        self.assertEqual(convert_page_spec_printed_to_pdf("1-3", m), "6-8")


if __name__ == "__main__":
    unittest.main()
